"""Education / pedagogue API — standalone RAG Q&A + MCP + veille + conversation memory."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents.guidance.questions import to_roadmap_profil
from app.agents.guidance.roadmap.parcours import verdict_regime
from app.agents.pedagogue import answer as pedagogue_answer
from app.agents.pedagogue.rag import vectorstore
from app.agents.pedagogue.rag.ingest import ingest_document
from app.agents.pedagogue.veille import dernier_rapport, run_veille
from app.api.deps import get_current_user, get_current_user_optional
from app.core import education_store
from app.mcp import client as mcp
from app.schemas.auth import UserPublic
from app.schemas.orchestrator import DiagnosticProfile

router = APIRouter(prefix="/api/education", tags=["education"])


class EducationAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    concerne: str | None = None
    historique: list[dict[str, Any]] | None = None
    conversation_id: str | None = None
    # Optional override; otherwise derived from user's guidance agent_context
    profil: dict[str, Any] | None = None
    use_guidance_context: bool = True


class EducationSource(BaseModel):
    source: str | None = None
    titre: str | None = None
    url: str | None = None
    date_publication: str | None = None
    score: float | None = None
    perime: bool = False


class EducationAskResponse(BaseModel):
    answer: str
    sources: list[EducationSource]
    freshness_warning: bool = False
    corpus_empty: bool = False
    bofip_live_used: bool = False
    conversation_id: str | None = None
    regime_verdict: str | None = None


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


def _guidance_profil_and_verdict(user: UserPublic) -> tuple[dict | None, dict | None]:
    snap = user.agent_context.guidance
    profil: dict | None = None
    if snap.diagnostic_profile and isinstance(snap.diagnostic_profile, dict):
        try:
            diag = DiagnosticProfile.model_validate(snap.diagnostic_profile)
            profil = to_roadmap_profil(diag)
        except Exception:
            profil = dict(snap.diagnostic_profile)
    elif snap.profile and isinstance(snap.profile, dict):
        profil = dict(snap.profile)

    if not profil:
        return None, None

    # Prefer compact roadmap-shaped keys
    if "ca_estime_annuel" not in profil and profil.get("estimated_annual_revenue"):
        raw = str(profil.get("estimated_annual_revenue") or "").replace(" ", "").replace("€", "")
        try:
            profil["ca_estime_annuel"] = float(raw)
        except ValueError:
            pass

    verdict = None
    try:
        verdict = verdict_regime(profil)
    except Exception:
        # Fallback from stored roadmap bandeau if analyser fails
        rm = snap.roadmap if isinstance(snap.roadmap, dict) else None
        if rm:
            verdict = {
                "parcours": rm.get("parcours"),
                "phrase": (rm.get("bandeau") or {}).get("texte") or rm.get("regime_recommande") or "",
                "durabilite": rm.get("durabilite"),
                "categorie": rm.get("categorie"),
            }
    return profil, verdict


@router.get("/rag/status")
async def rag_status(_user: UserPublic | None = Depends(get_current_user_optional)):
    return {"corpus_chunks": vectorstore.count()}


@router.post("/ask", response_model=EducationAskResponse)
async def ask(
    payload: EducationAskRequest,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    profil = payload.profil
    regime = None
    if user is not None and payload.use_guidance_context:
        ctx_profil, regime = _guidance_profil_and_verdict(user)
        if profil is None:
            profil = ctx_profil

    conversation_id = payload.conversation_id
    historique = list(payload.historique or [])

    if user is None:
        # Public education: full agent, no account required — answers are not persisted.
        conversation_id = None
    elif conversation_id:
        existing = await education_store.async_get_conversation(conversation_id)
        if existing is None or existing.get("user_id") != user.id:
            raise HTTPException(status_code=404, detail="Conversation introuvable.")
        if not historique:
            historique = [
                {"role": m["role"], "content": m["content"]}
                for m in (existing.get("messages") or [])
                if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
            ]

    try:
        result = await pedagogue_answer(
            payload.question.strip(),
            concerne=payload.concerne,
            historique=historique,
            profil=profil,
            regime_verdict=regime,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    sources = result.get("sources", [])

    if user is not None:
        if not conversation_id:
            conversation_id = await education_store.async_create_conversation(
                user_id=user.id,
                title=payload.question.strip()[:80],
            )
        await education_store.async_append_messages(
            conversation_id,
            user_content=payload.question.strip(),
            assistant_content=result["reponse"],
            sources=sources,
            title_hint=None,
        )

    return EducationAskResponse(
        answer=result["reponse"],
        sources=[EducationSource(**s) for s in sources],
        freshness_warning=bool(result.get("avertissement_fraicheur")),
        corpus_empty=bool(result.get("corpus_vide")),
        bofip_live_used=bool(result.get("bofip_live_utilise")),
        conversation_id=conversation_id,
        regime_verdict=result.get("regime_verdict"),
    )


@router.get("/conversations")
async def list_conversations(user: UserPublic = Depends(get_current_user)):
    return {"conversations": await education_store.async_list_conversations(user.id)}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: UserPublic = Depends(get_current_user)):
    row = await education_store.async_get_conversation(conversation_id)
    if row is None or row.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    return row


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    payload: RenameRequest,
    user: UserPublic = Depends(get_current_user),
):
    row = await education_store.async_get_conversation(conversation_id)
    if row is None or row.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    await education_store.async_rename_conversation(conversation_id, payload.title)
    return {"ok": True, "id": conversation_id, "title": payload.title.strip()[:120]}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: UserPublic = Depends(get_current_user)):
    row = await education_store.async_get_conversation(conversation_id)
    if row is None or row.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable.")
    await education_store.async_delete_conversation(conversation_id)
    return {"ok": True}


@router.get("/mcp/tools")
async def mcp_tools(_user: UserPublic = Depends(get_current_user)):
    out: dict[str, Any] = {}
    for server in ("legifrance", "bofip", "web-sources", "entreprises", "docs-officiels"):
        try:
            out[server] = await mcp.list_tools(server)
        except Exception as exc:
            out[server] = {"erreur": str(exc)}
    return out


@router.post("/mcp/ingest-bofip")
async def mcp_ingest_bofip(
    requete: str = Query(..., min_length=2),
    limite: int = Query(5, ge=1, le=20),
    _user: UserPublic = Depends(get_current_user),
):
    res = await mcp.call_tool("bofip", "bofip_search", {"requete": requete, "limite": limite})
    total = 0
    for d in res.get("documents", []):
        if d.get("extrait"):
            total += ingest_document(
                text=d["extrait"],
                source="BOFiP",
                titre=d["titre"],
                url=d["url"],
                type_doc="doctrine",
                autorite=2,
                concerne=["tous"],
            )
    return {"documents_trouves": len(res.get("documents", [])), "chunks_ingeres": total}


@router.post("/veille/run")
async def veille_run(_user: UserPublic = Depends(get_current_user)):
    try:
        return await run_veille()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/veille/last")
async def veille_last(_user: UserPublic = Depends(get_current_user)):
    return dernier_rapport()
