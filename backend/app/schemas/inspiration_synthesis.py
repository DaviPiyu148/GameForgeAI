"""
Inspiration Synthesis request and proposal schemas (Step 4: Discovery -> Inspiration -> Studio).
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.blueprint import BlueprintObjective, GameBlueprint
from app.schemas.project import BuildParams, ProjectResponse


class SourceAttribution(BaseModel):
    """Traces a proposed design element back to its contributing inspiration(s)."""
    element: str
    category: str
    source_steam_app_ids: List[str] = Field(default_factory=list, alias="sourceSteamAppIds")
    source_titles: List[str] = Field(default_factory=list, alias="sourceTitles")
    trigger_attributes: List[str] = Field(default_factory=list, alias="triggerAttributes")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class SynthesisConflict(BaseModel):
    """Represents an incompatibility between inspiration attributes requiring review."""
    field: str
    description: str
    conflicting_sources: List[str] = Field(default_factory=list, alias="conflictingSources")
    options: List[str] = Field(default_factory=list)
    resolution_status: Literal["UNRESOLVED", "RESOLVED_BY_PROJECT_CONTEXT"] = Field(
        default="UNRESOLVED", alias="resolutionStatus"
    )
    resolved_value: Optional[str] = Field(default=None, alias="resolvedValue")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class InspirationSynthesisProposal(BaseModel):
    """
    Strongly-typed deterministic design proposal synthesized from 2–5 inspirations.
    This is a structured proposal for developer review; NOT automatically applied to Blueprint.
    """
    project_id: str = Field(..., alias="projectId")
    inspiration_count: int = Field(..., alias="inspirationCount")
    source_titles: List[str] = Field(default_factory=list, alias="sourceTitles")

    proposed_title: str = Field(..., alias="proposedTitle")
    proposed_genre: str = Field(..., alias="proposedGenre")
    proposed_archetype: str = Field(..., alias="proposedArchetype")
    proposed_theme: str = Field(..., alias="proposedTheme")
    proposed_player_modes: List[str] = Field(default_factory=list, alias="proposedPlayerModes")
    proposed_mechanics: List[str] = Field(default_factory=list, alias="proposedMechanics")

    gameplay_loop: str = Field(..., alias="gameplayLoop")
    progression_direction: str = Field(..., alias="progressionDirection")
    design_objectives: List[BlueprintObjective] = Field(default_factory=list, alias="designObjectives")
    recommended_parameters: BuildParams = Field(..., alias="recommendedParameters")

    shared_anchors: List[str] = Field(default_factory=list, alias="sharedAnchors")
    complementary_anchors: List[str] = Field(default_factory=list, alias="complementaryAnchors")
    conflicts: List[SynthesisConflict] = Field(default_factory=list)
    source_attribution: List[SourceAttribution] = Field(default_factory=list, alias="sourceAttribution")

    is_single_source_dominant: bool = Field(default=False, alias="isSingleSourceDominant")
    dominant_source_title: Optional[str] = Field(default=None, alias="dominantSourceTitle")

    confidence: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"
    confidence_explanation: str = Field(..., alias="confidenceExplanation")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class BlueprintFieldChange(BaseModel):
    """Represents a specific field change made by applying the proposal."""
    field_name: str = Field(..., alias="fieldName")
    previous_value: Any = Field(..., alias="previousValue")
    new_value: Any = Field(..., alias="newValue")
    source_attribution: Optional[str] = Field(default=None, alias="sourceAttribution")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ApplySynthesisProposalRequest(BaseModel):
    """
    Request payload to apply an approved inspiration synthesis proposal to the Blueprint.
    Client supplies base_version_number for optimistic concurrency, conflict_resolutions
    for any unresolved conflicts, and optional field decision overrides.
    """
    base_version_number: int = Field(..., alias="baseVersionNumber", ge=1)
    conflict_resolutions: Dict[str, str] = Field(default_factory=dict, alias="conflictResolutions")
    field_decisions: Dict[str, Literal["APPLY_PROPOSAL", "KEEP_CURRENT"]] = Field(
        default_factory=dict, alias="fieldDecisions"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class ApplySynthesisProposalResponse(BaseModel):
    """Response returned upon successfully versioning the project with the proposal applied."""
    project_id: str = Field(..., alias="projectId")
    previous_version_number: int = Field(..., alias="previousVersionNumber")
    new_version_number: int = Field(..., alias="newVersionNumber")
    change_summary: str = Field(..., alias="changeSummary")
    changes: List[BlueprintFieldChange] = Field(default_factory=list)
    project: ProjectResponse
    blueprint: GameBlueprint
    status: Literal["SUCCESS"] = "SUCCESS"

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )

