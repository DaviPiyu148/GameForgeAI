"""ProjectInspiration request and response schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AttachInspirationRequest(BaseModel):
    """
    Request body for POST /api/projects/{project_id}/inspirations.

    Accepts ONLY the canonical Steam catalog identifier.
    All metadata is resolved server-side from the catalog to ensure data integrity.
    """
    steam_app_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        alias="steamAppId",
        description="Canonical Steam catalog identifier (external_id).",
    )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )


class ProjectInspirationResponse(BaseModel):
    """
    Response schema for a persisted project inspiration record.
    Represents an immutable historical snapshot captured at attach time.
    """
    id: str
    project_id: str = Field(..., alias="projectId")
    steam_app_id: str = Field(..., alias="steamAppId")
    title: str
    cover_url: Optional[str] = Field(default=None, alias="coverUrl")
    genres: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    player_modes: List[str] = Field(default_factory=list, alias="playerModes")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ProjectInspirationListResponse(BaseModel):
    """Collection response schema for project inspirations."""
    inspirations: List[ProjectInspirationResponse]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )
