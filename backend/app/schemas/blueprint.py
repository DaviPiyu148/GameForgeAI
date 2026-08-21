from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BlueprintObjective(BaseModel):
    """A single stage or top-level objective, presented in plain language."""
    level_number: Optional[int] = None
    type: str
    description: str

    model_config = ConfigDict(extra="ignore")


class GameBlueprint(BaseModel):
    """
    Nontechnical-friendly presentation of a project's design, derived entirely from
    its already-validated GameDesignSpec + GameDSL. This is a computed projection,
    not a stored source of truth -- every field must be traceable to real DSL/runtime
    state, never a fabricated capability the runtime can't back.
    """
    project_id: str
    title: str = Field(..., max_length=100)
    genre: str = Field(..., max_length=50)
    archetype: str
    player_fantasy: str = Field(..., max_length=100)
    theme: str
    # Not tightly bounded: the fallback derivation path concatenates several
    # already-bounded (<=200 char) design-spec fields together, so a strict cap
    # near 200 would spuriously reject a legitimate combined string.
    core_loop: str = Field(..., max_length=700)
    estimated_session_length: str = Field(..., max_length=50)
    level_count: int = Field(..., ge=1, le=5)
    world_area_count: int = Field(..., ge=1, le=5)
    objectives: List[BlueprintObjective] = Field(default_factory=list, max_length=10)
    progression: List[str] = Field(default_factory=list, max_length=5)
    encounter_types: List[str] = Field(default_factory=list, max_length=20)
    enemy_variety: int = Field(0, ge=0)
    # Same rationale as core_loop: may fall back to a design-spec win_condition
    # string or a level completion_message, neither of which is tightly bounded.
    finale: str = Field(..., max_length=400)
    supported_mechanics: List[str] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(extra="ignore")
