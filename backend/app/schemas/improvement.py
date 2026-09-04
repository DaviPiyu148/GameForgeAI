from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ImprovementFieldChange(BaseModel):
    """Field-level diff description for an applied playtest recommendation."""
    field_name: str = Field(..., alias="fieldName")
    previous_value: Any = Field(..., alias="previousValue")
    new_value: Any = Field(..., alias="newValue")
    recommendation_id: Optional[str] = Field(default=None, alias="recommendationId")
    description: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        serialize_by_alias=True,
    )


class ImprovementApplyRequest(BaseModel):
    """Payload to apply approved recommendations to a project."""
    selected_recommendations: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        alias="recommendations",
        description="List of selected playtest recommendations to apply.",
    )
    session_id: Optional[str] = Field(
        default=None,
        alias="sessionId",
        description="Source playtest session ID for provenance and staleness verification.",
    )
    base_version_number: Optional[int] = Field(
        default=None,
        ge=1,
        alias="baseVersionNumber",
        description="Optimistic locking base version number.",
    )
    user_notes: Optional[str] = Field(
        None,
        max_length=500,
        alias="userNotes",
        description="Optional developer notes explaining patch rationale.",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class ImprovementApplyResponse(BaseModel):
    """Result of applying improvement patch."""
    project_id: str = Field(..., alias="projectId")
    previous_version_number: int = Field(..., alias="previousVersionNumber")
    new_version_number: int = Field(..., alias="newVersionNumber")
    version_number: Optional[int] = Field(default=None, alias="version_number")
    game_dsl: Dict[str, Any] = Field(..., alias="gameDsl")
    design_spec: Optional[Dict[str, Any]] = Field(default=None, alias="designSpec")
    change_summary: str = Field(..., alias="changeSummary")
    changes: List[ImprovementFieldChange] = Field(default_factory=list)
    source_session_id: Optional[str] = Field(default=None, alias="sourceSessionId")
    status: str = "SUCCESS"
    message: str = "Playtest improvements applied successfully as a new version."

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        serialize_by_alias=True,
    )

