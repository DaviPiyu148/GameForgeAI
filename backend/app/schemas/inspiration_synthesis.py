"""
Inspiration Synthesis request and proposal schemas (Step 4: Discovery -> Inspiration -> Studio).
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.blueprint import BlueprintObjective
from app.schemas.project import BuildParams


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
