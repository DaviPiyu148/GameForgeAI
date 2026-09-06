"""
Profile APIs for user personalization preferences and gamification progression.

GET /api/profile/progress     → authenticated — user XP, level, and recent progression events
GET /api/profile/preferences  → authenticated — behavioral genre affinity distribution
"""
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.rate_limit import check_preference_mutate_rate
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.profile import (
    OnboardingPreferencesRequest,
    ResetPreferencesResponse,
    UserPreferencesResponse,
    UserProgressResponse,
)

from app.services.preference_service import preference_service
from app.services.progression_service import progression_service

router = APIRouter(prefix="/profile", tags=["Profile & Personalization"])


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": str(uuid.uuid4())}},
    )


@router.get("/progress", response_model=UserProgressResponse)
async def get_user_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve server-authoritative XP and level progression status."""
    return progression_service.get_progress_response(db, current_user.id)


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve calculated genre preferences derived from behavioral telemetry."""
    return preference_service.get_preferences(db, current_user.id)


@router.post("/preferences/onboard", response_model=UserPreferencesResponse)
async def onboard_user_preferences(
    request: OnboardingPreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Establish bounded initial Game DNA preferences for a new or returning user."""
    if not check_preference_mutate_rate(current_user.id):
        return _error(
            "RATE_LIMITED",
            "Preference mutation rate limit exceeded (maximum 20 operations per hour). Please try again later.",
            429,
        )

    return preference_service.onboard_preferences(
        db=db,
        user_id=current_user.id,
        genres=request.genres,
        enjoyments=request.enjoyments,
        avoidances=request.avoidances,
    )


@router.post("/preferences/reset", response_model=ResetPreferencesResponse)
async def reset_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset Game DNA preference signals without deleting saves, projects, or progression."""
    if not check_preference_mutate_rate(current_user.id):
        return _error(
            "RATE_LIMITED",
            "Preference mutation rate limit exceeded (maximum 20 operations per hour). Please try again later.",
            429,
        )

    preference_service.reset_preferences(db, current_user.id)
    return ResetPreferencesResponse(
        status="success",
        message="Game DNA preferences have been reset.",
        user_id=current_user.id,
    )

