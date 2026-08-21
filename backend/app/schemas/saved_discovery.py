"""SavedDiscovery request and response schemas for Phase B7."""
from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class SaveDiscoveryRequest(BaseModel):
    """
    Request body for POST /api/saved-discoveries.

    The frontend sends ONLY the catalog identifier.
    Backend resolves all display metadata (title, genres) from the catalog.
    This prevents the frontend from injecting fake metadata.
    """
    steam_app_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Canonical Steam catalog identifier (external_id from discovery results).",
    )

    model_config = ConfigDict(extra="forbid")


class SavedDiscoveryResponse(BaseModel):
    """
    Response for a single saved discovery record.
    Title and genres are resolved server-side from the catalog.
    """
    id: str
    user_id: str
    steam_app_id: str
    title: str
    genres: List[str]
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class SavedDiscoveryListResponse(BaseModel):
    """Collection response for GET /api/saved-discoveries."""
    discoveries: List[SavedDiscoveryResponse]

    model_config = ConfigDict(from_attributes=True)
