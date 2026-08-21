from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.blueprint import GameBlueprint


class RemixIntentType(str, Enum):
    """
    Closed catalog of structured remix intents. Limited to what the current
    DSL/runtime capabilities actually support -- "add_boss" and "more_vehicles"
    are deliberately absent: boss encounters and vehicles are future-phase
    runtime capabilities that don't exist yet, and offering them here would
    violate the same "no fake capabilities" rule the Blueprint enforces.
    """
    INCREASE_COMBAT = "increase_combat"
    INCREASE_EXPLORATION = "increase_exploration"
    INCREASE_DIFFICULTY = "increase_difficulty"
    DECREASE_DIFFICULTY = "decrease_difficulty"
    ADD_LEVELS = "add_levels"
    MORE_STORY = "more_story"
    FASTER_PACE = "faster_pace"
    MORE_ENEMIES = "more_enemies"
    CHANGE_THEME = "change_theme"


# User-facing label for each intent, kept server-side so the wire contract (enum
# value) stays stable even if displayed copy changes later.
REMIX_INTENT_LABELS: Dict[str, str] = {
    RemixIntentType.INCREASE_COMBAT.value: "More Combat",
    RemixIntentType.INCREASE_EXPLORATION.value: "More Exploration",
    RemixIntentType.INCREASE_DIFFICULTY.value: "Harder",
    RemixIntentType.DECREASE_DIFFICULTY.value: "Easier",
    RemixIntentType.ADD_LEVELS.value: "Add 2 Levels",
    RemixIntentType.MORE_STORY.value: "More Story",
    RemixIntentType.FASTER_PACE.value: "Faster Pace",
    RemixIntentType.MORE_ENEMIES.value: "More Enemies",
    RemixIntentType.CHANGE_THEME.value: "Different Theme",
}

# Intent pairs that contradict each other -- selecting both in one request is
# rejected rather than silently letting one arbitrarily win.
_MUTUALLY_EXCLUSIVE_PAIRS: List[set] = [
    {RemixIntentType.INCREASE_DIFFICULTY.value, RemixIntentType.DECREASE_DIFFICULTY.value},
]


class RemixIntent(BaseModel):
    """A single structured remix intent -- the only vocabulary the remix AI prompt may act on."""
    type: RemixIntentType
    strength: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class RemixApplyRequest(BaseModel):
    """Payload to apply structured remix intents to a project, creating a new version."""
    intents: List[RemixIntent] = Field(..., min_length=1, max_length=3)

    model_config = ConfigDict(extra="ignore")

    @field_validator("intents")
    @classmethod
    def validate_intents(cls, v: List[RemixIntent]) -> List[RemixIntent]:
        types = [i.type.value for i in v]
        if len(types) != len(set(types)):
            raise ValueError("Duplicate remix intent types are not allowed in a single request.")
        type_set = set(types)
        for pair in _MUTUALLY_EXCLUSIVE_PAIRS:
            if pair.issubset(type_set):
                raise ValueError(f"Mutually exclusive remix intents selected: {sorted(pair)}.")
        return v


class RemixApplyResponse(BaseModel):
    """Result of applying a structured remix -- a new immutable ProjectVersion is created."""
    project_id: str
    version_number: int
    game_dsl: Dict[str, Any]
    design_spec: Optional[Dict[str, Any]] = None
    blueprint: GameBlueprint
    change_summary: str
    status: str = "SUCCESS"

    model_config = ConfigDict(extra="ignore")
