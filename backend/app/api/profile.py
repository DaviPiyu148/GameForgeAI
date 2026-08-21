"""
Profile APIs for user personalization preferences and gamification progression.

GET /api/profile/progress     → authenticated — user XP, level, and recent progression events
GET /api/profile/preferences  → authenticated — behavioral genre affinity distribution
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.profile import UserPreferencesResponse, UserProgressResponse
from app.services.preference_service import preference_service
from app.services.progression_service import progression_service

router = APIRouter(prefix="/profile", tags=["Profile & Personalization"])


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
