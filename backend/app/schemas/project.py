from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

ProjectStatus = Literal["PLAYABLE", "COMPILING", "ERROR"]


class BuildParams(BaseModel):
    """Build specifications parameters schema."""
    engine: str = Field(default="Top-Down Action", min_length=1, max_length=100)
    art_density: int = Field(default=50, ge=0, le=100, alias="artDensity")
    physics: int = Field(default=80, ge=0, le=100)
    modules: List[str] = Field(default_factory=list, max_length=50)

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class ProjectCreate(BaseModel):
    """Schema for project creation request."""
    title: str = Field(..., min_length=1, max_length=255)
    genre: str = Field(default="Generated Concept", max_length=100)
    prompt: str = Field(..., min_length=1)
    status: Optional[ProjectStatus] = Field(default="PLAYABLE")
    parameters: BuildParams = Field(default_factory=BuildParams)
    design_spec: Optional[Dict[str, Any]] = Field(default=None, alias="designSpec")
    game_dsl: Optional[Dict[str, Any]] = Field(default=None, alias="gameDsl")
    runtime_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="runtimeMetadata")
    current_version: int = Field(default=1, alias="currentVersion")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


class ProjectUpdate(BaseModel):
    """Schema for updating permitted project fields."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    genre: Optional[str] = Field(default=None, max_length=100)
    prompt: Optional[str] = Field(default=None, min_length=1)
    parameters: Optional[BuildParams] = Field(default=None)
    design_spec: Optional[Dict[str, Any]] = Field(default=None, alias="designSpec")
    game_dsl: Optional[Dict[str, Any]] = Field(default=None, alias="gameDsl")
    runtime_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="runtimeMetadata")
    current_version: Optional[int] = Field(default=None, alias="currentVersion")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class ProjectResponse(BaseModel):
    """Frontend-compatible project response schema."""
    id: str
    title: str
    genre: str
    status: ProjectStatus
    last_modified: str = Field(..., alias="lastModified")
    parameters: BuildParams
    prompt: str
    design_spec: Optional[Dict[str, Any]] = Field(default=None, alias="designSpec")
    game_dsl: Optional[Dict[str, Any]] = Field(default=None, alias="gameDsl")
    runtime_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="runtimeMetadata")
    current_version: int = Field(default=1, alias="currentVersion")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        serialize_by_alias=True,
    )


class ProjectListResponse(BaseModel):
    """Collection response schema for projects."""
    projects: List[ProjectResponse]

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        serialize_by_alias=True,
    )
