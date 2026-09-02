"""
Projects API router with ownership enforcement, playtest telemetry, AI analysis, and versioning.

All routes require authentication via get_current_user().
user_id is sourced exclusively from the JWT token — never from request body.
IDOR protection: owner mismatch on GET/PATCH returns 404 (not 403).
"""
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.project import (
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.playtest import (
    PlaytestCreate,
    PlaytestSessionResponse,
    PlaytestAnalysisResponse,
)
from app.schemas.improvement import (
    ImprovementApplyRequest,
    ImprovementApplyResponse,
)
from app.schemas.blueprint import GameBlueprint
from app.schemas.remix import RemixApplyRequest, RemixApplyResponse
from app.services.project_service import (
    PlaytestNotFoundError,
    ProjectNotFoundError,
    ProjectService,
    project_service,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def make_error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """Helper to return consistent structured error envelopes."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@router.get(
    "",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="List authenticated user's Game Projects",
)
def list_projects(
    limit: int = Query(default=100, ge=1, le=500, description="Max projects to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> ProjectListResponse:
    """List the authenticated user's projects (ordered newest first)."""
    projects = service.list_projects(db, user_id=current_user.id, limit=limit, offset=offset)
    return ProjectListResponse(projects=projects)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Game Project by ID",
)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> ProjectResponse:
    """Retrieve a single project by ID. Returns 404 if not found or not owned by requester."""
    try:
        return service.get_project(db, project_id, user_id=current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update editable Game Project fields",
)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> ProjectResponse:
    """Update permitted fields (title, genre, prompt, parameters). Ownership required."""
    try:
        return service.update_project(db, project_id, data, user_id=current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a Game Project",
)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> None:
    """Permanently delete an owned project and all its version/playtest rows.
    Returns 204 No Content on success, 404 if not found or not owned by requester.
    """
    try:
        service.delete_project(db, project_id, user_id=current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.post(
    "/{project_id}/duplicate",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a Game Project (snapshot copy, fresh version history)",
)
def duplicate_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> ProjectResponse:
    """Create an independent snapshot copy of an owned project with a fresh v1 version
    history. The copy inherits the original's current playable configuration and DSL
    but none of its playtest sessions, build jobs, or telemetry history.
    Returns 201 Created on success, 404 if not found or not owned by requester.
    """
    try:
        return service.duplicate_project(db, project_id, user_id=current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


# -----------------------------------------------------------------------------
# Playtest & Telemetry Endpoints
# -----------------------------------------------------------------------------

@router.post(
    "/{project_id}/playtests",
    response_model=PlaytestSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a completed playtest session and telemetry",
)
def record_playtest(
    project_id: str,
    data: PlaytestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> PlaytestSessionResponse:
    """Record playtest summary and telemetry. Enforces ownership."""
    try:
        session_res = service.create_playtest_session(db, project_id, current_user.id, data)        # Grant PLAYTEST XP and record preferences & milestone evaluation
        try:
            from app.services.progression_service import progression_service
            from app.services.preference_service import preference_service

            is_win = getattr(data, "outcome", "").upper() == "WON"
            progression_service.grant_xp(
                db=db,
                user_id=current_user.id,
                event_type="PLAYTEST",
                source_ref=session_res.id,
            )
            if is_win:
                progression_service.grant_xp(
                    db=db,
                    user_id=current_user.id,
                    event_type="PLAYTEST_WIN",
                    source_ref=session_res.id,
                )

            progression_service.evaluate_milestones(
                db=db,
                user_id=current_user.id,
                trigger_event="PLAYTEST_WIN" if is_win else "PLAYTEST",
                context={"outcome": "WIN" if is_win else "LOSS", "session_id": session_res.id},
            )

            # Retrieve project to get genre
            proj = service.get_project(db, project_id, current_user.id)
            if proj:
                preference_service.record_signal(
                    db=db,
                    user_id=current_user.id,
                    raw_genres_or_tags=[proj.genre, proj.title],
                    weight=8.0,
                    source="playtest",
                )
        except Exception as pe:
            logger.warning(f"Telemetry tracking failed on playtest for user {current_user.id}: {pe}")

        return session_res
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.get(
    "/{project_id}/playtests",
    response_model=List[PlaytestSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List playtest sessions for a project",
)
def list_playtests(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> List[PlaytestSessionResponse]:
    """List all recorded playtest sessions for a project. Enforces ownership."""
    try:
        return service.list_playtest_sessions(db, project_id, current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.get(
    "/{project_id}/playtests/{session_id}",
    response_model=PlaytestSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single playtest session",
)
def get_playtest_session(
    project_id: str,
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> PlaytestSessionResponse:
    """Retrieve details and recorded telemetry for a single playtest session."""
    try:
        return service.get_playtest_session(db, project_id, session_id, current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except PlaytestNotFoundError as e:
        return make_error_response("PLAYTEST_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.post(
    "/{project_id}/analyze-playtest",
    response_model=PlaytestAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI Playtest Critique on gameplay telemetry",
)
async def analyze_playtest(
    project_id: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> PlaytestAnalysisResponse:
    """Trigger AI analysis on playtest telemetry."""
    session_id = payload.get("session_id") if payload else None
    telemetry = payload.get("telemetry") if payload else None
    try:
        analysis_res = await service.analyze_playtest_session(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            session_id=session_id,
            telemetry_payload=telemetry,
        )

        try:
            from app.services.progression_service import progression_service
            progression_service.grant_xp(
                db=db,
                user_id=current_user.id,
                event_type="AI_ANALYSIS",
                source_ref=session_id or project_id,
            )
            progression_service.evaluate_milestones(
                db=db,
                user_id=current_user.id,
                trigger_event="AI_ANALYSIS",
                context={"session_id": session_id, "project_id": project_id},
            )
        except Exception as pe:
            logger.warning(f"Telemetry tracking failed on AI analysis for user {current_user.id}: {pe}")

        return analysis_res
    except (ProjectNotFoundError, PlaytestNotFoundError) as e:
        return make_error_response("NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except Exception:
        logger.exception("AI playtest analysis failed for project_id=%s", project_id)
        return make_error_response(
            "ANALYSIS_FAILED",
            "AI playtest analysis is currently unavailable. Please try again shortly.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )  # type: ignore


@router.post(
    "/{project_id}/improvements",
    response_model=ImprovementApplyResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply approved AI recommendations as a versioned DSL patch",
)
async def apply_improvements(
    project_id: str,
    data: ImprovementApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> ImprovementApplyResponse:
    """Apply approved improvement recommendations to create a new project version."""
    try:
        imp_res = await service.apply_project_improvement(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            data=data,
        )

        try:
            from app.services.progression_service import progression_service
            progression_service.grant_xp(
                db=db,
                user_id=current_user.id,
                event_type="IMPROVE_GAME",
                source_ref=f"{project_id}_v{imp_res.new_version_number}",
            )
            progression_service.evaluate_milestones(
                db=db,
                user_id=current_user.id,
                trigger_event="IMPROVE_GAME",
                context={"project_id": project_id, "version": imp_res.new_version_number},
            )
        except Exception as pe:
            logger.warning(f"Telemetry tracking failed on project improvement for user {current_user.id}: {pe}")

        return imp_res
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except Exception as e:
        return make_error_response("IMPROVEMENT_FAILED", str(e), status.HTTP_400_BAD_REQUEST)  # type: ignore


@router.get(
    "/{project_id}/blueprint",
    response_model=GameBlueprint,
    status_code=status.HTTP_200_OK,
    summary="Get the nontechnical-friendly Game Blueprint for a project",
)
def get_project_blueprint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> GameBlueprint:
    """Derive and return the Game Blueprint (title, genre, core loop, levels, objectives,
    progression, supported mechanics, finale) for an owned project."""
    try:
        return service.get_project_blueprint(db, project_id, current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except ValueError as e:
        return make_error_response("BLUEPRINT_UNAVAILABLE", str(e), status.HTTP_400_BAD_REQUEST)  # type: ignore


@router.post(
    "/{project_id}/remix",
    response_model=RemixApplyResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply structured remix intents as a new versioned project remix",
)
async def apply_remix(
    project_id: str,
    data: RemixApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> RemixApplyResponse:
    """Apply approved structured remix intents to create a new immutable project version."""
    try:
        remix_res = await service.apply_project_remix(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            data=data,
        )

        try:
            from app.services.progression_service import progression_service
            progression_service.grant_xp(
                db=db,
                user_id=current_user.id,
                event_type="IMPROVE_GAME",
                source_ref=f"{project_id}_v{remix_res.version_number}",
            )
            progression_service.evaluate_milestones(
                db=db,
                user_id=current_user.id,
                trigger_event="IMPROVE_GAME",
                context={"project_id": project_id, "version": remix_res.version_number, "remix": True},
            )
        except Exception as pe:
            logger.warning(f"Telemetry tracking failed on project remix for user {current_user.id}: {pe}")

        return remix_res
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except Exception as e:
        return make_error_response("REMIX_FAILED", str(e), status.HTTP_400_BAD_REQUEST)  # type: ignore


@router.get(
    "/{project_id}/versions",
    status_code=status.HTTP_200_OK,
    summary="List revision history of a project",
)
def list_versions(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> List[Dict[str, Any]]:
    """List project versions."""
    try:
        return service.list_project_versions(db, project_id, current_user.id)
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.post(
    "/{project_id}/restore",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore a historical version as a new immutable vN+1 version",
)
def restore_version(
    project_id: str,
    target_version_number: int = Query(..., ge=1, description="Historical version number to restore"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(lambda: project_service),
) -> ProjectResponse:
    """Restore an older ProjectVersion into a new forward vN+1 version without modifying history."""
    try:
        return service.restore_project_version(
            db, project_id, current_user.id, target_version_number
        )
    except ProjectNotFoundError as e:
        return make_error_response("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except ValueError as e:
        return make_error_response("VERSION_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore

