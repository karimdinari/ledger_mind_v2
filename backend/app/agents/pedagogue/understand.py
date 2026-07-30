"""Analyse du message utilisateur dans le chat Éducation (relances, confusion, exemples)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.llm.gemini import chat_json

logger = logging.getLogger(__name__)

QueryIntent = Literal[
    "new_question",
    "followup_clarify",
    "followup_deepen",
    "confused",
    "example_request",
    "thanks",
    "off_topic",
    "unclear",
]

_THANKS = re.compile(
    r"^\s*(?:"
    r"merci(?:\s+(?:beaucoup|bien|infiniment))?"
    r"|ok(?:\s+merci)?"
    r"|super(?:\s+merci)?"
    r"|parfait(?:\s+merci)?"
    r"|c'est\s+bon(?:\s+merci)?"
    r"|bien\s+reçu"
    r"|noté"
    r"|d'accord(?:\s+merci)?"
    r")\s*[!.?…]*\s*$",
    re.I,
)

_CONFUSED = re.compile(
    r"(?:"
    r"je\s+n['']?\s*ai\s+pas\s+compris"
    r"|j['']?ai\s+pas\s+compris"
    r"|pas\s+compris"
    r"|j['']?ai\s+pas\s+capt[ée]"
    r"|je\s+ne\s+comprends\s+pas"
    r"|je\s+comprends\s+pas"
    r"|c['']?est\s+flou"
    r"|c['']?est\s+pas\s+clair"
    r"|tu\s+peux\s+reformuler"
    r"|peux[- ]tu\s+reformuler"
    r"|explique(?:r)?\s+(?:autrement|différemment|plus\s+simplement|mieux)"
    r"|plus\s+simplement"
    r"|en\s+plus\s+simple"
    r"|reformule"
    r"|redis\s+(?:ça|cela)\s+(?:autrement|plus\s+simple)"
    r")",
    re.I,
)

_EXAMPLE = re.compile(
    r"(?:"
    r"un\s+exemple"
    r"|donne(?:z)?\s+(?:moi\s+)?un\s+exemple"
    r"|par\s+exemple"
    r"|concrètement"
    r"|cas\s+concret"
    r"|illustre"
    r"|montre[- ]moi"
    r")",
    re.I,
)

_DEEPEN = re.compile(
    r"(?:"
    r"plus\s+de\s+détails?"
    r"|en\s+détail"
    r"|approfond"
    r"|développe"
    r"|pourquoi\s+(?:ça|cela|est-ce)"
    r"|comment\s+ça\s+marche"
    r"|explique[- ]moi\s+pourquoi"
    r")",
    re.I,
)

_SHORT_FOLLOWUP = re.compile(
    r"^\s*(?:"
    r"et\s+donc\??"
    r"|donc\??"
    r"|du\s+coup\??"
    r"|ok\s+et\??"
    r"|pourquoi\??"
    r"|comment\??"
    r"|c['']?est\s+quoi\??"
    r"|qu['']?est-ce\s+que\??"
    r")\s*$",
    re.I,
)

_OFF_TOPIC = re.compile(
    r"(?:"
    r"météo"
    r"|football"
    r"|recette\s+de"
    r"|qui\s+es[- ]tu"
    r"|quel\s+modèle"
    r"|chatgpt"
    r")",
    re.I,
)

_INSTRUCTION = """Tu analyses un message dans un chat fiscal français (LedgerMind Éducation).

Historique récent (du plus ancien au plus récent) :
{historique}

Nouveau message utilisateur :
{message}

Détermine l'intention :
- "new_question" : nouvelle question fiscale autonome (même courte)
- "confused" : n'a pas compris la dernière réponse, demande reformulation
- "followup_clarify" : précision / simplification sur le même sujet
- "followup_deepen" : veut plus de détails ou le « pourquoi »
- "example_request" : demande un exemple concret
- "thanks" : remerciement sans nouvelle question
- "off_topic" : hors fiscalité française
- "unclear" : ambigu sans historique utile

Règles :
- Messages courts (« je n'ai pas compris », « un exemple ? », « pourquoi ? ») avec historique → intent de suivi, PAS new_question.
- "search_query" : requête RAG en français pour retrouver les bons extraits (sujet réel, pas le message court).
  Pour un suivi, reformule à partir de la question initiale + dernier échange.
- "sujet" : thème en 3-8 mots (ex. « seuils micro-entreprise 2025 »).
- "consigne_reponse" : consigne courte pour l'assistant (ex. « Reformule avec un exemple chiffré simple »).
- "reponse_directe" : uniquement pour thanks/off_topic sans besoin de corpus ; sinon null.

Réponds UNIQUEMENT en JSON :
{{"intent":"confused","search_query":"seuils micro-entreprise franchise TVA","sujet":"seuils micro","consigne_reponse":"Reformule simplement avec un exemple","reponse_directe":null}}
"""


@dataclass
class QueryAnalysis:
    intent: QueryIntent
    search_query: str
    sujet: str | None = None
    consigne_reponse: str | None = None
    reponse_directe: str | None = None


def _normaliser_historique(historique: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in historique or []:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append({"role": str(role), "content": content})
    return out[-12:]


def _derniere_question_utilisateur(historique: list[dict[str, str]]) -> str | None:
    for m in reversed(historique):
        if m["role"] == "user":
            return m["content"]
    return None


def _premiere_question_utilisateur(historique: list[dict[str, str]]) -> str | None:
    for m in historique:
        if m["role"] == "user":
            return m["content"]
    return None


def _formater_historique_txt(historique: list[dict[str, str]]) -> str:
    if not historique:
        return "(vide)"
    lines = []
    for m in historique[-8:]:
        who = "Utilisateur" if m["role"] == "user" else "Assistant"
        lines.append(f"{who} : {m['content'][:600]}")
    return "\n".join(lines)


def _analyse_regex(message: str, historique: list[dict[str, str]]) -> QueryAnalysis | None:
    msg = message.strip()
    low = msg.lower()
    has_hist = len(historique) >= 2
    sujet = _premiere_question_utilisateur(historique) or _derniere_question_utilisateur(historique)

    if _THANKS.match(msg):
        return QueryAnalysis(
            intent="thanks",
            search_query=msg,
            reponse_directe=(
                "Je vous en prie. Si une autre question fiscale vous vient, je suis là pour vous expliquer."
            ),
        )

    if _OFF_TOPIC.search(low):
        return QueryAnalysis(
            intent="off_topic",
            search_query=msg,
            reponse_directe=(
                "Je suis spécialisé dans la fiscalité française des créateurs et freelances. "
                "Posez-moi une question sur la micro-entreprise, la TVA, les seuils ou votre statut."
            ),
        )

    if not has_hist:
        return None

    base_query = sujet or msg

    if _CONFUSED.search(low):
        return QueryAnalysis(
            intent="confused",
            search_query=base_query,
            sujet=base_query[:80],
            consigne_reponse=(
                "L'utilisateur n'a pas compris. Reformule ta dernière explication plus simplement, "
                "en 2 ou 3 phrases courtes, avec un exemple concret si possible. Ne dis pas « je n'ai pas compris votre question »."
            ),
        )

    if _EXAMPLE.search(low):
        return QueryAnalysis(
            intent="example_request",
            search_query=base_query,
            sujet=base_query[:80],
            consigne_reponse=(
                "Donne un exemple chiffré et concret lié au sujet en cours, en restant dans les faits des extraits."
            ),
        )

    if _DEEPEN.search(low) or _SHORT_FOLLOWUP.match(msg):
        return QueryAnalysis(
            intent="followup_deepen" if _DEEPEN.search(low) else "followup_clarify",
            search_query=base_query,
            sujet=base_query[:80],
            consigne_reponse=(
                "Complète ou précise ta réponse précédente sur le même sujet, sans répéter mot pour mot."
            ),
        )

    if len(msg) <= 40 and not re.search(r"\b(micro|tva|bic|bnc|siret|urssaf|impôt|fiscal|ca|charges)\b", low):
        return QueryAnalysis(
            intent="followup_clarify",
            search_query=base_query,
            sujet=base_query[:80],
            consigne_reponse="Réponds en lien direct avec l'échange précédent.",
        )

    return None


async def analyse_query(
    message: str,
    historique: list[dict[str, Any]] | None = None,
) -> QueryAnalysis:
    """Classify user message; derive RAG search query and response instructions."""
    msg = (message or "").strip()
    hist = _normaliser_historique(historique)

    hit = _analyse_regex(msg, hist)
    if hit is not None:
        return hit

    if len(hist) < 2:
        return QueryAnalysis(intent="new_question", search_query=msg)

    try:
        data = await chat_json(
            _INSTRUCTION.format(historique=_formater_historique_txt(hist), message=msg),
            temperature=0.0,
            max_tokens=400,
        )
        intent = data.get("intent", "new_question")
        if intent not in (
            "new_question",
            "followup_clarify",
            "followup_deepen",
            "confused",
            "example_request",
            "thanks",
            "off_topic",
            "unclear",
        ):
            intent = "new_question"

        search_query = (data.get("search_query") or msg).strip() or msg
        directe = data.get("reponse_directe")
        if isinstance(directe, str):
            directe = directe.strip() or None
        else:
            directe = None

        return QueryAnalysis(
            intent=intent,  # type: ignore[arg-type]
            search_query=search_query,
            sujet=(data.get("sujet") or None) if isinstance(data.get("sujet"), str) else None,
            consigne_reponse=(
                data.get("consigne_reponse") if isinstance(data.get("consigne_reponse"), str) else None
            ),
            reponse_directe=directe,
        )
    except Exception as e:
        logger.warning("Pedagogue query analysis LLM failed: %s", e)
        sujet = _derniere_question_utilisateur(hist) or msg
        return QueryAnalysis(intent="new_question", search_query=sujet)
