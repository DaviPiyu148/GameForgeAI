"""
Project Inspirations API router (Phase Step 2: Discovery -> Inspiration -> Studio).

POST   /api/projects/{project_id}/inspirations                -> attach inspiration (owner only)
GET    /api/projects/{project_id}/inspirations                -> list inspirations (owner only)
DELETE /api/projects/{project_id}/inspirations/{steam_app_id} -> detach inspiration (owner only)

Security Invariants:
- All endpoints require authentication via get_current_user().
- Ownership verified via project_service._get_owned_project() (IDOR protection returns 404).
- Request body only accepts canonical steam_app_id (extra="forbid").
- Metadata snapshot is resolved server-side.
- Duplicate attachment returns 409 Conflict.
"""
import logging
import uuid
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.project_inspiration import (
    AttachInspirationRequest,
    ProjectInspirationListResponse,
    ProjectInspirationResponse,
)
from app.services.project_service import ProjectNotFoundError
from app.services.project_inspiration_service import (
    DuplicateInspirationError,
    InspirationNotFoundError,
    ProjectInspirationService,
    project_inspiration_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/inspirations", tags=["Project Inspirations"])


def _error(code: str, message: str, status_code: int) -> JSONResponse:
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


@router.post(
    "",
    response_model=ProjectInspirationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a game discovery as inspiration to an owned project",
)
def attach_inspiration(
    project_id: str,
    data: AttachInspirationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectInspirationService = Depends(lambda: project_inspiration_service),
) -> ProjectInspirationResponse:
    """
    Attach a game to a project as design inspiration.
    Server resolves metadata from catalog and creates an immutable snapshot.
    Returns 409 if already attached. Ownership required.
    """
    try:
        return service.attach_inspiration(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            data=data,
        )
    except ProjectNotFoundError as e:
        return _error("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except DuplicateInspirationError as e:
        return _error("ALREADY_INSPIRED", str(e), status.HTTP_409_CONFLICT)  # type: ignore
    except Exception as e:
        logger.exception("Failed to attach inspiration for project %s", project_id)
        return _error("INSPIRATION_FAILED", "Failed to attach inspiration. Please try again.", status.HTTP_500_INTERNAL_SERVER_ERROR)  # type: ignore


@router.get(
    "",
    response_model=ProjectInspirationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all inspirations attached to an owned project",
)
def list_inspirations(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectInspirationService = Depends(lambda: project_inspiration_service),
) -> ProjectInspirationListResponse:
    """List inspirations for an owned project, newest first."""
    try:
        return service.list_inspirations(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
        )
    except ProjectNotFoundError as e:
        return _error("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except Exception as e:
        logger.exception("Failed to list inspirations for project %s", project_id)
        return _error("INSPIRATION_LIST_FAILED", "Failed to list inspirations.", status.HTTP_500_INTERNAL_SERVER_ERROR)  # type: ignore


@router.delete(
    "/{steam_app_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Detach an inspiration from an owned project",
)
def detach_inspiration(
    project_id: str,
    steam_app_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ProjectInspirationService = Depends(lambda: project_inspiration_service),
) -> None:
    """
    Detach a game inspiration from an owned project by steam_app_id.
    Returns 204 No Content on success, 404 if project or inspiration not found.
    """
    try:
        service.detach_inspiration(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            steam_app_id=steam_app_id,
        )
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
    except ProjectNotFoundError as e:
        return _error("PROJECT_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except InspirationNotFoundError as e:
        return _error("INSPIRATION_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore
    except Exception as e:
        logger.exception("Failed to detach inspiration for project %s game %s", project_id, steam_app_id)
        return _error("INSPIRATION_DELETE_FAILED", "Failed to detach inspiration.", status.HTTP_500_INTERNAL_SERVER_ERROR)  # type: ignore
