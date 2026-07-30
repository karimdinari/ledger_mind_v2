"""Orchestrator API — intake/guidance sessions + roadmap checklist/PDF/bascule."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.agents.guidance import finalize_diagnostic
from app.agents.guidance.options import options_bascule
from app.agents.guidance.roadmap.pdf import roadmap_to_pdf
from app.agents.intake.agent import finalize_profile
from app.agents.orchestrator import orchestrator_turn, start_orchestrator
from app.api.deps import get_current_user, get_current_user_optional
from app.core.session_store import (
    async_delete_session,
    async_get_session,
    async_list_sessions_for_user,
    async_rename_session,
    async_save_session,
)
from app.schemas.auth import UserPublic
from app.schemas.orchestrator import (
    DiagnosticProfile,
    OrchestratorStartRequest,
    OrchestratorTurnRequest,
    OrchestratorTurnResponse,
    UserProfile,
)

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


class SessionDetail(BaseModel):
    session_id: str
    phase: str
    branch: str
    user_id: str | None = None
    profile: UserProfile
    diagnostic_profile: DiagnosticProfile | None = None
    roadmap: dict[str, Any] | None = None
    roadmap_checked: dict[str, bool] = Field(default_factory=dict)
    options: dict[str, Any] | None = None
    title: str | None = None


class SessionSummary(BaseModel):
    session_id: str
    branch: str | None = None
    phase: str | None = None
    updated_at: str = ""
    title: str | None = None


class RoadmapStateRequest(BaseModel):
    checked: dict[str, bool] = Field(default_factory=dict)


class ChoixParcoursRequest(BaseModel):
    choix: Literal["micro", "societe"]


class PatchDiagnosticRequest(BaseModel):
    """Partial update of the guidance diagnostic profile (live editable panel)."""

    activite: str | None = None
    ca_estime_annuel: float | None = None
    vend_produits: bool | None = None
    recoit_cadeaux: bool | None = None
    type_activite: str | None = None
    premiere_annee: bool | None = None
    jours_activite: int | None = None
    anciennete: str | None = None
    ca_n_1_au_dessus_seuil: bool | None = None
    ca_n_2_au_dessus_seuil: bool | None = None
    situation_actuelle: str | None = None
    ca_prestations: float | None = None
    ca_vente: float | None = None
    choix_parcours: str | None = None
    rebuild_roadmap: bool = True


class PatchIntakeProfileRequest(BaseModel):
    """Partial update of intake UserProfile (HITL confirmation panel)."""

    activity_types: list[str] | None = None
    has_secondary_activity: bool | None = None
    secondary_activity_types: list[str] | None = None
    main_activity_commercial: bool | None = None
    revenue_sources: list[str] | None = None
    currencies: list[str] | None = None
    estimated_monthly_revenue: str | None = None
    estimated_annual_revenue: str | None = None
    revenue_variability: Literal["stable", "spiky", "unknown"] | None = None
    invoices_already_issued: bool | None = None
    first_income_date: str | None = None
    has_recurring_contracts: bool | None = None
    in_kind_gifts: bool | None = None
    international_clients: bool | None = None
    reclassify: bool = True


class RenameSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class RoadmapFromProfilRequest(BaseModel):
    """Standalone roadmap build (compat with old POST /roadmap)."""

    profil: dict[str, Any]


def _assert_owner(state, user: UserPublic | None) -> None:
    if state.user_id and (user is None or user.id != state.user_id):
        raise HTTPException(status_code=403, detail="Cette session ne vous appartient pas.")


@router.post("/start", response_model=OrchestratorTurnResponse)
async def start(
    payload: OrchestratorStartRequest,
    user: UserPublic = Depends(get_current_user),
):
    use_diagnostic = payload.skip_verification or payload.branch == "guidance"
    if not use_diagnostic and (not payload.siret or not payload.siret.strip()):
        raise HTTPException(
            status_code=400,
            detail=(
                "Un numéro SIRET ou SIREN est requis pour créer un profil. "
                "Utilisez le diagnostic de régularisation si vous n'êtes pas encore immatriculé."
            ),
        )
    try:
        return await start_orchestrator(
            payload.siret,
            payload.company_name,
            skip_verification=payload.skip_verification or payload.branch == "guidance",
            branch=payload.branch,
            user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/turn", response_model=OrchestratorTurnResponse)
async def turn(
    payload: OrchestratorTurnRequest,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    state = await async_get_session(payload.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {payload.session_id}")
    _assert_owner(state, user)
    try:
        return await orchestrator_turn(payload.session_id, payload.user_answer)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/my-sessions", response_model=list[SessionSummary])
async def my_sessions(user: UserPublic = Depends(get_current_user)):
    rows = await async_list_sessions_for_user(user.id)
    return [SessionSummary(**row) for row in rows]


@router.get("/session/{session_id}", response_model=UserProfile)
async def get_session_profile(
    session_id: str,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    return state.profile


_INTAKE_EDITABLE = (
    "activity_types",
    "has_secondary_activity",
    "secondary_activity_types",
    "main_activity_commercial",
    "revenue_sources",
    "currencies",
    "estimated_monthly_revenue",
    "estimated_annual_revenue",
    "revenue_variability",
    "invoices_already_issued",
    "first_income_date",
    "has_recurring_contracts",
    "in_kind_gifts",
    "international_clients",
)


@router.patch("/session/{session_id}/profile", response_model=SessionDetail)
async def patch_intake_profile(
    session_id: str,
    payload: PatchIntakeProfileRequest,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    """HITL confirmation — edit intake answers and optionally re-run tax classification."""
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)

    data = payload.model_dump(exclude_unset=True)
    reclassify = bool(data.pop("reclassify", True))
    profile_data = state.profile.model_dump(mode="json")
    for key in _INTAKE_EDITABLE:
        if key in data:
            profile_data[key] = data[key]
    state.profile = UserProfile.model_validate(profile_data)
    if reclassify:
        state.profile = finalize_profile(state.profile)
    await async_save_session(session_id, state)

    opts = options_bascule(
        state.diagnostic_profile.model_dump(mode="json"),
        state.roadmap,
    )
    return SessionDetail(
        session_id=state.session_id,
        phase=state.phase,
        branch=state.branch,
        user_id=state.user_id,
        profile=state.profile,
        diagnostic_profile=state.diagnostic_profile,
        roadmap=state.roadmap,
        roadmap_checked=state.roadmap_checked or {},
        options=opts,
        title=state.title,
    )


@router.get("/session/{session_id}/detail", response_model=SessionDetail)
async def get_session_detail(
    session_id: str,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    opts = options_bascule(
        state.diagnostic_profile.model_dump(mode="json"),
        state.roadmap,
    )
    return SessionDetail(
        session_id=state.session_id,
        phase=state.phase,
        branch=state.branch,
        user_id=state.user_id,
        profile=state.profile,
        diagnostic_profile=state.diagnostic_profile,
        roadmap=state.roadmap,
        roadmap_checked=state.roadmap_checked or {},
        options=opts,
        title=state.title,
    )


@router.get("/session/{session_id}/roadmap")
async def get_session_roadmap(
    session_id: str,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    if state.roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not available for this session")
    return state.roadmap


@router.get("/session/{session_id}/roadmap/state")
async def get_roadmap_state(
    session_id: str,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    return {
        "session_id": session_id,
        "roadmap": state.roadmap,
        "checked": state.roadmap_checked or {},
    }


@router.put("/session/{session_id}/roadmap/state")
async def put_roadmap_state(
    session_id: str,
    payload: RoadmapStateRequest,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    state.roadmap_checked = {str(k): bool(v) for k, v in (payload.checked or {}).items()}
    await async_save_session(session_id, state)
    return {"session_id": session_id, "checked": state.roadmap_checked}


@router.post("/session/{session_id}/choix-parcours", response_model=SessionDetail)
async def choix_parcours(
    session_id: str,
    payload: ChoixParcoursRequest,
    user: UserPublic = Depends(get_current_user),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    if state.branch != "guidance":
        raise HTTPException(status_code=400, detail="Choix de parcours disponible uniquement en guidance.")
    state.diagnostic_profile.choix_parcours = payload.choix
    result = await finalize_diagnostic(state.diagnostic_profile, state.profile)
    state.diagnostic_profile = result.diagnostic_profile
    state.profile = result.profile
    state.roadmap = result.roadmap
    etape_ids = {
        e.get("id") for e in (state.roadmap or {}).get("etapes") or [] if isinstance(e, dict)
    }
    state.roadmap_checked = {
        k: v for k, v in (state.roadmap_checked or {}).items() if k in etape_ids
    }
    await async_save_session(session_id, state)
    opts = options_bascule(
        state.diagnostic_profile.model_dump(mode="json"),
        state.roadmap,
    )
    return SessionDetail(
        session_id=state.session_id,
        phase=state.phase,
        branch=state.branch,
        user_id=state.user_id,
        profile=state.profile,
        diagnostic_profile=state.diagnostic_profile,
        roadmap=state.roadmap,
        roadmap_checked=state.roadmap_checked or {},
        options=opts,
        title=state.title,
    )


@router.patch("/session/{session_id}/diagnostic-profile", response_model=SessionDetail)
async def patch_diagnostic_profile(
    session_id: str,
    payload: PatchDiagnosticRequest,
    user: UserPublic = Depends(get_current_user),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    data = payload.model_dump(exclude_unset=True)
    rebuild = data.pop("rebuild_roadmap", True)
    diag = state.diagnostic_profile.model_dump(mode="json")
    for k, v in data.items():
        diag[k] = v
    state.diagnostic_profile = DiagnosticProfile.model_validate(diag)
    if rebuild:
        result = await finalize_diagnostic(state.diagnostic_profile, state.profile)
        state.diagnostic_profile = result.diagnostic_profile
        state.profile = result.profile
        state.roadmap = result.roadmap
        if state.phase in ("diagnostic_questions", "diagnostic_roadmap", "done"):
            state.phase = "diagnostic_roadmap"
    await async_save_session(session_id, state)
    opts = options_bascule(
        state.diagnostic_profile.model_dump(mode="json"),
        state.roadmap,
    )
    return SessionDetail(
        session_id=state.session_id,
        phase=state.phase,
        branch=state.branch,
        user_id=state.user_id,
        profile=state.profile,
        diagnostic_profile=state.diagnostic_profile,
        roadmap=state.roadmap,
        roadmap_checked=state.roadmap_checked or {},
        options=opts,
        title=state.title,
    )


@router.post("/session/{session_id}/roadmap/pdf")
async def session_roadmap_pdf(
    session_id: str,
    user: UserPublic | None = Depends(get_current_user_optional),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    if not state.roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not available for this session")
    try:
        pdf = roadmap_to_pdf(state.roadmap)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}") from e
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=roadmap_ledgermind.pdf"},
    )


@router.post("/roadmap")
async def roadmap_from_profil(
    payload: RoadmapFromProfilRequest,
    _user: UserPublic = Depends(get_current_user),
):
    from app.agents.guidance.roadmap.parcours import build_roadmap

    return build_roadmap(payload.profil or {})


@router.post("/roadmap/pdf")
async def roadmap_pdf_from_profil(
    payload: RoadmapFromProfilRequest,
    _user: UserPublic = Depends(get_current_user),
):
    from app.agents.guidance.roadmap.parcours import build_roadmap

    roadmap = build_roadmap(payload.profil or {})
    try:
        pdf = roadmap_to_pdf(roadmap)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}") from e
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=roadmap_ledgermind.pdf"},
    )


@router.patch("/session/{session_id}/rename")
async def rename_session(
    session_id: str,
    payload: RenameSessionRequest,
    user: UserPublic = Depends(get_current_user),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    ok = await async_rename_session(session_id, payload.title)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True, "session_id": session_id, "title": payload.title.strip()[:120]}


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user: UserPublic = Depends(get_current_user),
):
    state = await async_get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    _assert_owner(state, user)
    await async_delete_session(session_id)
    return {"ok": True}
