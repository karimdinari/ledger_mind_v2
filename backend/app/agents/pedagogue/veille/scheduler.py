"""Orchestration de la veille dynamique — VERSION MCP (pedagogue corpus).

Consomme les serveurs MCP (legifrance, bofip, web-sources, docs-officiels). Chaque
nouveauté est résumée par Mistral, classée, puis ré-ingérée dans le corpus vectoriel
pédagogue. Contrôle aussi les seuils de seuils.yaml contre les sources officielles
(signale les écarts sans écraser le fichier).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

import httpx

from app.agents.guidance.roadmap import seuils as S
from app.agents.pedagogue.rag.ingest import ingest_document
from app.config import settings
from app.mcp import client as mcp

log = logging.getLogger("veille")

MOTS_CLES = (
    "influence commerciale influenceur micro-entreprise franchise TVA "
    "benefices non commerciaux"
)
_dernier_rapport: dict = {"nouveautes": [], "date": None, "seuils": []}
MISTRAL_BASE = "https://api.mistral.ai/v1"


def _valeur_presente(valeur: int, texte: str) -> bool:
    compact = re.sub(r"[\s .]", "", texte or "")
    return re.search(rf"(?<!\d){int(valeur)}(?!\d)", compact) is not None


def _cibles_seuils() -> list[dict]:
    micro = S.bloc("micro")
    tva = S.bloc("tva_franchise")
    return [
        {"label": "Plafond micro-BNC", "valeur": int(micro["bnc"]["seuil"]), "source": micro["bnc"]["source"]},
        {
            "label": "Plafond micro-BIC vente",
            "valeur": int(micro["bic_vente"]["seuil"]),
            "source": micro["bic_vente"]["source"],
        },
        {
            "label": "Franchise TVA services (base)",
            "valeur": int(tva["services"]["seuil_base"]),
            "source": tva["services"]["source"],
        },
        {
            "label": "Franchise TVA services (majoré)",
            "valeur": int(tva["services"]["seuil_majore"]),
            "source": tva["services"]["source"],
        },
        {
            "label": "Franchise TVA vente (base)",
            "valeur": int(tva["vente"]["seuil_base"]),
            "source": tva["vente"]["source"],
        },
    ]


async def verifier_seuils() -> list[dict]:
    """Contrôle chaque valeur de seuils.yaml contre sa source officielle via MCP."""
    resultats = []
    for cible in _cibles_seuils():
        statut, detail = "inaccessible", ""
        try:
            page = await mcp.call_tool(
                "docs-officiels", "fetch_page", {"cle_ou_url": cible["source"]}
            )
            texte = page.get("texte", "") if isinstance(page, dict) else ""
            if texte:
                statut = "confirme" if _valeur_presente(cible["valeur"], texte) else "ecart_possible"
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)
        if statut != "confirme":
            log.warning(
                "Veille seuils — %s (%s) : %s %s",
                cible["label"],
                cible["valeur"],
                statut,
                detail,
            )
        resultats.append({**cible, "statut": statut, "detail": detail})
    return resultats


async def _resumer_et_classer(titre: str, texte: str) -> dict:
    systeme = (
        "Tu analyses une publication fiscale/juridique francaise. Reponds en JSON strict : "
        '{"resume":"3 phrases max","concerne":["influenceur"|"freelance"|"tous"],'
        '"impact":"concret pour un createur","pertinent":true|false}. '
        "pertinent=false si le texte ne concerne pas les createurs/independants."
    )
    if not settings.mistral_api_key:
        return {
            "resume": (texte or "")[:280],
            "concerne": ["tous"],
            "impact": "",
            "pertinent": True,
        }
    try:
        payload = {
            "model": settings.pedagogue_mistral_model,
            "messages": [
                {"role": "system", "content": systeme},
                {"role": "user", "content": f"Titre : {titre}\n\nTexte : {texte[:6000]}"},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{MISTRAL_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {settings.mistral_api_key}"},
                json=payload,
            )
            r.raise_for_status()
            out = r.json()["choices"][0]["message"]["content"]
        return json.loads(out)
    except Exception as exc:  # noqa: BLE001
        return {
            "resume": "",
            "concerne": ["tous"],
            "impact": "",
            "pertinent": True,
            "erreur": str(exc),
        }


async def _collecter() -> list[dict]:
    items: list[dict] = []

    try:
        res = await mcp.call_tool(
            "legifrance", "legifrance_search", {"mots_cles": MOTS_CLES, "taille": 8}
        )
        for r in res.get("resultats", []):
            items.append(
                {
                    "titre": r["titre"],
                    "url": r["url"],
                    "source": "Legifrance",
                    "texte": r["titre"],
                    "autorite": 1,
                    "concerne": None,
                }
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("MCP legifrance indisponible : %s", exc)

    try:
        res = await mcp.call_tool(
            "bofip",
            "bofip_search",
            {"requete": "avantages en nature revenus non commerciaux", "limite": 4},
        )
        for d in res.get("documents", []):
            items.append(
                {
                    "titre": d["titre"],
                    "url": d["url"],
                    "source": "BOFiP",
                    "texte": d["extrait"],
                    "autorite": 2,
                    "concerne": ["tous"],
                }
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("MCP bofip indisponible : %s", exc)

    try:
        res = await mcp.call_tool("web-sources", "check_updates", {})
        for n in res.get("nouveautes", []):
            if "erreur" in n:
                continue
            items.append(
                {
                    "titre": f"MAJ {n['source']}",
                    "url": n["url"],
                    "source": n["source"],
                    "texte": n["texte"],
                    "autorite": 2,
                    "concerne": n.get("concerne", ["tous"]),
                }
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("MCP web-sources indisponible : %s", exc)

    for cle, autorite in (
        ("impots_actualites", 2),
        ("loi_finances_2026", 1),
        ("boss_avantages_nature", 2),
    ):
        try:
            n = await mcp.call_tool("docs-officiels", "fetch_page", {"cle_ou_url": cle})
            if n.get("texte"):
                items.append(
                    {
                        "titre": f"{n.get('source', 'DGFiP')} — {cle}",
                        "url": n["url"],
                        "source": n.get("source", "DGFiP"),
                        "texte": n["texte"],
                        "autorite": autorite,
                        "concerne": n.get("concerne", ["tous"]),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("MCP docs-officiels (%s) indisponible : %s", cle, exc)

    return items


async def run_veille() -> dict:
    candidats = await _collecter()
    rapport = []
    for c in candidats:
        analyse = await _resumer_et_classer(c["titre"], c["texte"])
        if not analyse.get("pertinent", True):
            continue
        concerne = analyse.get("concerne") or c.get("concerne") or ["tous"]
        ingest_document(
            text=c["texte"],
            source=c["source"],
            titre=c["titre"],
            url=c["url"],
            type_doc="actualite",
            autorite=c.get("autorite", 2),
            concerne=concerne,
        )
        rapport.append(
            {
                "titre": c["titre"],
                "source": c["source"],
                "url": c["url"],
                "resume": analyse.get("resume", ""),
                "impact": analyse.get("impact", ""),
                "concerne": concerne,
            }
        )

    seuils_verif = await verifier_seuils()
    ecarts = [s for s in seuils_verif if s["statut"] == "ecart_possible"]

    global _dernier_rapport
    _dernier_rapport = {
        "nouveautes": rapport,
        "seuils": seuils_verif,
        "seuils_ecarts": len(ecarts),
        "date": datetime.now().isoformat(),
    }
    log.info(
        "Veille MCP terminee : %d nouveaute(s), %d ecart(s) de seuil signale(s)",
        len(rapport),
        len(ecarts),
    )
    return _dernier_rapport


def dernier_rapport() -> dict:
    return _dernier_rapport


def start_scheduler():
    """Optional APScheduler cron. Returns None if disabled or apscheduler missing."""
    if not settings.veille_enabled:
        return None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        log.warning("apscheduler non installé — veille planifiée désactivée")
        return None
    sched = AsyncIOScheduler()
    sched.add_job(run_veille, "cron", hour=settings.veille_cron_hour, id="veille_quotidienne")
    sched.start()
    log.info("Scheduler de veille MCP demarre (tous les jours a %sh)", settings.veille_cron_hour)
    return sched
