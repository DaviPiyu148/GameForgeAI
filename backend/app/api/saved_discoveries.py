"""
Saved Discoveries API routes (Phase B7).

GET    /api/saved-discoveries       → authenticated — list user's saved games
POST   /api/saved-discoveries       → authenticated — save a discovery
DELETE /api/saved-discoveries/{id}  → authenticated, owner only — remove a save

Security notes:
- All endpoints require authentication via get_current_user().
- user_id always sourced from the JWT token — never from request body.
- Owner mismatch on DELETE returns 404 (indistinguishable from not-found, IDOR protection).
- Catalog metadata resolved server-side; frontend cannot inject fake titles/genres.
"""
import uuid
import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.rate_limit import check_save_rate
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.saved_discovery import (
    SaveDiscoveryRequest,
    SavedDiscoveryListResponse,
    SavedDiscoveryResponse,
)
from app.services.saved_discovery_service import (
    DuplicateSaveError,
    SavedDiscoveryNotFoundError,
    saved_discovery_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saved-discoveries", tags=["Saved Discoveries"])


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": str(uuid.uuid4())}},
    )


@router.get("", response_model=SavedDiscoveryListResponse)
async def list_saved_discoveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all saved discoveries for the authenticated user."""
    return saved_discovery_service.list_saved(db, current_user.id)


@router.post("", response_model=SavedDiscoveryResponse, status_code=201)
async def save_discovery(
    data: SaveDiscoveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save a game discovery to the user's bookmarks.
    Rate limit: 50 saves per user per hour.
    Returns 409 if the game is already saved.
    """
    if not check_save_rate(current_user.id):
        return _error("RATE_LIMITED", "Save rate limit exceeded. Please try again later.", 429)

    try:
        saved = saved_discovery_service.save_discovery(db, current_user.id, data)

        # Grant XP and record genre preference signal for bookmarking a game
        try:
            from app.services.progression_service import progression_service
            from app.services.preference_service import preference_service

            progression_service.grant_xp(
                db=db,
                user_id=current_user.id,
                event_type="SAVE_DISCOVERY",
                source_ref=data.steam_app_id,
            )

            # Record genre preference
            genres = saved.genres or []
            preference_service.record_signal(
                db=db,
                user_id=current_user.id,
                raw_genres_or_tags=genres or [saved.title],
                weight=3.0,
                source="save_discovery",
            )
        except Exception as pe:
            logger.warning(f"Telemetry tracking failed on save_discovery for user {current_user.id}: {pe}")

        return saved
    except DuplicateSaveError:
        return _error("ALREADY_SAVED", "This game is already in your saved discoveries.", 409)
    except Exception:
        logger.exception("Failed to save discovery")
        return _error("SAVE_FAILED", "Failed to save discovery. Please try again.", 500)


@router.delete("/{record_id}", status_code=204)
async def delete_saved_discovery(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a saved discovery from the user's bookmarks.
    Owner mismatch returns 404 (same as not-found) to prevent IDOR enumeration.
    """
    try:
        saved_discovery_service.delete_saved(db, current_user.id, record_id)
        return JSONResponse(status_code=204, content=None)
    except SavedDiscoveryNotFoundError:
        return _error("SAVED_DISCOVERY_NOT_FOUND", f"Saved discovery '{record_id}' not found.", 404)
