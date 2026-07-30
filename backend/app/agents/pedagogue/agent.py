"""Pedagogue agent — fiscal Q&A grounded on RAG corpus with MCP BOFiP fallback."""
from __future__ import annotations

import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.pedagogue.rag.retriever import search
from app.agents.pedagogue.understand import QueryAnalysis, analyse_query, _normaliser_historique
from app.config import settings
from app.mcp import client as mcp

MISTRAL_BASE = "https://api.mistral.ai/v1"

_MOTS_VIDES = frozenset({
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "me", "te", "se",
    "le", "la", "les", "un", "une", "des", "du", "de", "ce", "cet", "cette", "ces",
    "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses", "et", "ou", "mais",
    "donc", "car", "que", "qui", "quoi", "dont", "au", "aux", "en", "dans", "sur",
    "sous", "par", "pour", "avec", "sans", "chez", "vers", "dois", "doit", "est",
    "sont", "ai", "as", "avons", "avez", "ont", "etre", "avoir", "faire", "si", "ne",
    "pas", "plus", "moins", "tres", "bien", "quel", "quelle", "quels", "quelles",
    "comment", "quand", "combien", "puis", "cas", "aussi", "leur", "leurs",
})

SYSTEME = """Tu es l'assistant pédagogique fiscal de LedgerMind, spécialisé dans la fiscalité
française des créateurs de contenu, influenceurs et freelances. Tu es accessible même aux
personnes non immatriculées.

RÈGLES ABSOLUES :
- Réponds à partir des extraits de corpus fournis, en t'appuyant sur les PRINCIPES GÉNÉRAUX
  qu'ils énoncent, même si aucun extrait ne traite le cas EXACT de la question. Commence
  DIRECTEMENT par la réponse, sans phrase d'excuse préalable.
- Cite tes sources entre crochets [Source — Titre].
- Ne refuse QUE si AUCUN extrait n'est pertinent pour la question. Dans ce seul cas, dis :
  "Je n'ai pas de source fiable sur ce point dans ma base ; vérifiez auprès de impots.gouv.fr
  ou d'un expert-comptable."
- N'INVENTE JAMAIS un chiffre, un seuil, un taux, une date ou un article de loi absent des
  extraits. Si un détail chiffré précis manque, signale-le EN FIN de réponse.
- Tu vulgarises : phrases courtes, pas de jargon sans le définir, exemples concrets.
- Tu ne donnes pas de conseil fiscal engageant : tu informes et tu orientes.
- Si une source est signalée comme potentiellement périmée, ajoute un avertissement de fraîcheur.
- Vouvoiement. Ton professionnel, clair, rassurant.
- RÉGIME (micro / société / à arbitrer) : si une POSITION DÉTERMINISTE SUR LE RÉGIME t'est fournie,
  elle fait autorité (calculée par l'outil à partir des seuils officiels et de la règle de
  tolérance N-1/N-2). Aligne-toi STRICTEMENT dessus : n'affirme jamais une conclusion de régime
  différente. En particulier, un CA qui dépasse le plafond micro une seule année n'exclut PAS du
  micro (sortie seulement après 2 années consécutives) : ne réponds donc jamais « impossible » ou
  « pas adapté » de façon couperet si la position déterministe indique « à arbitrer » / bascule.

FORMAT DE SORTIE (OBLIGATOIRE) :
- Texte brut uniquement, prêt à afficher tel quel.
- Aucun markdown : pas de # ## ###, pas de **, __, *, `, ni de blocs de code.
- Aucun guillemet décoratif en série ("" ""), ni tirets de liste markdown (- item).
- Pas d'emoji. Pas de titres. Pas de tableaux.
- Structure en paragraphes courts (2 à 4), éventuellement des phrases numérotées
  « 1. … 2. … » en texte simple si une énumération est utile.
- Les seules crochets autorisés sont les citations de sources [Source — Titre].

CONVERSATION (relances utilisateur) :
- L'historique et la consigne de tour te disent si l'utilisateur pose une NOUVELLE question ou fait un SUIVI
  (« je n'ai pas compris », « un exemple », « pourquoi », « plus simple », etc.).
- En cas de suivi : reste sur le MÊME sujet que l'échange précédent ; ne traite pas le message court isolément.
- Si l'utilisateur n'a pas compris : reformule plus simplement, sans t'excuser d'abord, avec un exemple concret si utile.
- Si il demande un exemple : cas chiffré simplifié, ancré dans les extraits.
- Si il demande plus de détails : complète sans recopier ta réponse précédente mot pour mot.
- Ne réponds jamais « je n'ai pas de source » pour une relance si les extraits couvrent déjà le sujet en cours.

TROIS DIMENSIONS À COUVRIR (cadeaux, dotations, gifting) : fiscal, social, impact seuils.
CATÉGORIE BNC / BIC : dépend de la NATURE de l'activité, jamais du statut juridique.
"""


def _mots_cles(question: str) -> str:
    q = re.sub(r"[^\w\sàâäéèêëîïôöùûüç-]", " ", question.lower())
    mots: list[str] = []
    for mot in re.split(r"[\s-]+", q):
        if len(mot) >= 3 and mot not in _MOTS_VIDES and mot not in mots:
            mots.append(mot)
    return " ".join(mots)


_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]"
)


def _nettoyer_reponse(texte: str) -> str:
    """Strip markdown / decorative clutter; keep plain professional prose."""
    t = (texte or "").strip()
    if not t:
        return t
    t = re.sub(r"```[\s\S]*?```", " ", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"__([^_]+)__", r"\1", t)
    t = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", t)
    t = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", t)
    t = re.sub(r"(?m)^\s*[-•*]\s+", "", t)
    t = re.sub(r'"{2,}', '"', t)
    t = re.sub(r"'{2,}", "'", t)
    t = _EMOJI.sub("", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def _chat(messages: list[dict], *, temperature: float = 0.0, max_tokens: int = 2000) -> str:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is required for pedagogue answers")
    payload = {
        "model": settings.pedagogue_mistral_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        r = await client.post(
            f"{MISTRAL_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def answer(
    question: str,
    *,
    concerne: str | None = None,
    profil: dict | None = None,
    historique: list[dict] | None = None,
    regime_verdict: dict | None = None,
) -> dict:
    """Answer a fiscal question using local RAG + MCP BOFiP live fallback."""
    hist = _normaliser_historique(historique)
    analysis = await analyse_query(question, hist)

    if analysis.reponse_directe and analysis.intent in ("thanks", "off_topic"):
        return {
            "reponse": _nettoyer_reponse(analysis.reponse_directe),
            "sources": [],
            "avertissement_fraicheur": False,
            "corpus_vide": False,
            "intent": analysis.intent,
        }

    if analysis.intent == "confused" and not hist:
        return {
            "reponse": _nettoyer_reponse(
                "Je peux reformuler plus simplement, mais je n'ai pas encore de réponse précédente "
                "dans cette conversation. Posez votre question fiscale et je vous l'expliquerai étape par étape."
            ),
            "sources": [],
            "avertissement_fraicheur": False,
            "corpus_vide": False,
            "intent": analysis.intent,
        }

    requete_rag = analysis.search_query.strip() or question.strip()
    r = search(requete_rag, k=8, concerne=concerne)

    if r["corpus_vide"]:
        return {
            "reponse": (
                "Ma base documentaire est vide pour l'instant. "
                "Lancez l'ingestion du corpus (python -m scripts.seed_pedagogue_corpus) puis réessayez."
            ),
            "sources": [],
            "avertissement_fraicheur": False,
            "corpus_vide": True,
        }

    hits = list(r["hits"])
    meilleure_sim = hits[0].get("similarite", 0.0) if hits else 0.0
    bofip_live: list[dict] = []
    if meilleure_sim < 0.80:
        requete_bofip = _mots_cles(requete_rag)
        if requete_bofip:
            try:
                res = await mcp.call_tool(
                    "bofip", "bofip_search", {"requete": requete_bofip, "limite": 3}
                )
                for d in res.get("documents", []):
                    if d.get("extrait"):
                        bofip_live.append(
                            {
                                "source": "BOFiP (live)",
                                "titre": d["titre"],
                                "url": d["url"],
                                "texte": d["extrait"],
                                "date_publication": "en vigueur",
                                "score": 0.78,
                                "similarite": 0.78,
                                "perime": False,
                            }
                        )
            except Exception:
                pass

    hits = (hits[:7] + bofip_live[:1]) if bofip_live else hits[:8]

    extraits = "\n\n---\n\n".join(
        f"[{h['source']} — {h['titre']}] (publié {h['date_publication']})\n{h['texte']}"
        for h in hits
    )

    verdict_txt = ""
    if regime_verdict:
        verdict_txt = (
            "\n\nPOSITION DÉTERMINISTE SUR LE RÉGIME (fait officiel calculé par l'outil, fait "
            "autorité, à respecter sans le contredire ; NE la cite PAS comme une source, cite les "
            f"extraits du corpus) : parcours = {regime_verdict.get('parcours')}. "
            f"{regime_verdict.get('phrase', '')}"
        )

    tour_txt = _tour_instruction(analysis, question)

    messages: list[dict] = [{"role": "system", "content": SYSTEME}]
    for h in hist[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append(
        {
            "role": "user",
            "content": (
                f"Message actuel : {question}\n\n"
                f"{tour_txt}\n"
                f"Profil compact (contexte, jamais une source) : {profil or {}}\n"
                f"{verdict_txt}\n\n"
                f"Extraits du corpus :\n{extraits}"
            ),
        },
    )
    reponse = _nettoyer_reponse(await _chat(messages))

    return {
        "reponse": reponse,
        "sources": [
            {
                "source": h["source"],
                "titre": h["titre"],
                "url": h["url"],
                "date_publication": h["date_publication"],
                "score": h["score"],
                "perime": h["perime"],
            }
            for h in hits[:6]
        ],
        "avertissement_fraicheur": r["au_moins_un_perime"],
        "corpus_vide": False,
        "bofip_live_utilise": bool(bofip_live),
        "regime_verdict": regime_verdict.get("parcours") if regime_verdict else None,
        "intent": analysis.intent,
    }


def _tour_instruction(analysis: QueryAnalysis, question: str) -> str:
    labels = {
        "new_question": "Nouvelle question fiscale.",
        "confused": "Relance : l'utilisateur n'a pas compris — reformule simplement.",
        "followup_clarify": "Relance : précision ou simplification sur le même sujet.",
        "followup_deepen": "Relance : l'utilisateur veut plus de détails ou le pourquoi.",
        "example_request": "Relance : l'utilisateur demande un exemple concret.",
        "unclear": "Message ambigu — réponds en lien avec l'historique si possible.",
        "thanks": "",
        "off_topic": "",
    }
    parts = [f"Type de message : {labels.get(analysis.intent, 'Question.')}"]
    if analysis.sujet:
        parts.append(f"Sujet de la conversation : {analysis.sujet}")
    if analysis.consigne_reponse:
        parts.append(f"Consigne : {analysis.consigne_reponse}")
    if analysis.intent != "new_question":
        parts.append(f"Requête documentaire utilisée : {analysis.search_query}")
    return "\n".join(parts)
