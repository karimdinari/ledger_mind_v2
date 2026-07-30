"""Live BOFiP search fallback when local corpus similarity is weak."""
from __future__ import annotations

import re

import httpx

BASE = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/bofip-vigueur/records"


def _strip_html(html: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", html or "")
    return " ".join(txt.split())


async def bofip_search(requete: str, limite: int = 3) -> list[dict]:
    params = {"where": f'search(*, "{requete}")', "limit": min(limite, 20)}
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.get(BASE, params=params)
        if r.status_code != 200:
            r = await client.get(BASE, params={"q": requete, "limit": min(limite, 20)})
        r.raise_for_status()
        data = r.json()

    documents = []
    for rec in data.get("results", []):
        titre = rec.get("titre") or rec.get("title") or "Document BOFiP"
        ident = rec.get("identifiant_juridique") or rec.get("permalien") or rec.get("id") or ""
        contenu = rec.get("contenu") or rec.get("contenu_html") or rec.get("content") or ""
        documents.append(
            {
                "titre": titre,
                "extrait": _strip_html(contenu)[:1500],
                "url": rec.get("permalien")
                or (f"https://bofip.impots.gouv.fr/bofip/{ident}" if ident else "https://bofip.impots.gouv.fr"),
            }
        )
    return documents
