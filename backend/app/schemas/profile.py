from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class XPEventItem(BaseModel):
    """Single discrete XP award record."""
    id: str
    event_type: str
    xp_amount: int
    source_reference: Optional[str] = None
    created_at: datetime


class UserProgressResponse(BaseModel):
    """Server-authoritative user progression and XP status."""
    user_id: str
    total_xp: int = Field(default=0, ge=0)
    current_level: int = Field(default=1, ge=1)
    current_level_base_xp: int = Field(default=0, ge=0)
    next_level_xp: int = Field(default=100, ge=1)
    xp_into_level: int = Field(default=0, ge=0)
    xp_needed_for_next: int = Field(default=100, ge=1)
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    recent_events: List[XPEventItem] = Field(default_factory=list)


class GenreAffinityItem(BaseModel):
    """Itemized genre affinity score and relative percentage."""
    genre: str
    score: float = Field(ge=0.0)
    percentage: float = Field(ge=0.0, le=100.0)
    interaction_count: int = Field(default=1, ge=1)
    affinity_tier: str = Field(default="Emerging")  # "High", "Moderate", "Emerging"


class UserPreferencesResponse(BaseModel):
    """User genre preferences derived from behavioral telemetry."""
    user_id: str
    top_genres: List[GenreAffinityItem] = Field(default_factory=list)
    total_interactions: int = Field(default=0, ge=0)
    strongest_match: Optional[str] = None
    has_sufficient_data: bool = False


class AvatarUploadResponse(BaseModel):
    """Response returned upon successful profile avatar upload or deletion."""
    avatar_url: Optional[str] = None
    message: str
