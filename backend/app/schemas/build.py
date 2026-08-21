from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.project import BuildParams

BuildStatus = Literal["QUEUED", "RUNNING", "VALIDATING", "SUCCESS", "ERROR", "CANCELLED"]


class BuildCreate(BaseModel):
    """Schema for requesting a new game build."""
    prompt: str = Field(..., min_length=1, max_length=5000)
    parameters: BuildParams = Field(default_factory=BuildParams)

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class BuildResponse(BaseModel):
    """Authoritative response schema for build status."""
    build_id: str
    status: BuildStatus
    project_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    game_dsl: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class BuildLogEntry(BaseModel):
    """Schema for individual build log entries."""
    sequence: int = Field(..., alias="sequence")
    level: str = "INFO"
    message: str
    timestamp: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        serialize_by_alias=True,
    )


class BuildLogListResponse(BaseModel):
    """Collection response schema for build logs."""
    build_id: str
    logs: List[BuildLogEntry]

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        serialize_by_alias=True,
    )


class BuildEvent(BaseModel):
    """Structured event for SSE streaming."""
    event: Literal["status", "log"]
    data: Dict[str, Any]
