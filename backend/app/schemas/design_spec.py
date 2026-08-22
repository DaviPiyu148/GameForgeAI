import re
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX_COLOR_REGEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

PROHIBITED_SCRIPT_PATTERNS = [
    r"javascript:",
    r"<script",
    r"eval\(",
    r"new\s+Function",
    r"__proto__",
    r"\.constructor\b",
    r"\[\s*['\"]constructor['\"]\s*\]",
    # `process.` narrowed to an actual property/method access (e.g. `process.env`,
    # `process.exit(`) — the un-narrowed `process\.` false-positived on ordinary prose
    # like "Master the crafting process. Then defend your base."
    r"process\.\w",
    r"require\(",
    # `import` narrowed to actual JS import syntax (dynamic `import(...)` or a static
    # `import ... from '...'` statement) — the un-narrowed `import\s+` false-positived
    # on ordinary imperative sentences like "Import ancient relics to unlock secrets".
    r"import\s*\(",
    r"import\s+[\w*{}\s,]+\s+from\s+['\"]",
]


def check_for_script_injection(value: Any) -> None:
    """Recursively verify no executable code or injection strings exist in text fields."""
    if isinstance(value, str):
        for pattern in PROHIBITED_SCRIPT_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValueError(f"Prohibited script or code execution detected: '{value}'")
    elif isinstance(value, dict):
        for k, v in value.items():
            check_for_script_injection(k)
            check_for_script_injection(v)
    elif isinstance(value, list):
        for item in value:
            check_for_script_injection(item)


class CoreLoopSpec(BaseModel):
    """Machine-readable breakdown of the micro-gameplay loop."""
    player_action: str = Field(..., min_length=1, max_length=200)
    immediate_feedback: str = Field(default="Floating score banners, particle bursts, and camera shake", max_length=200)
    increasing_pressure: str = Field(default="Escalating enemy pursuit speed and wave counts", max_length=200)
    progression: str = Field(default="Wave clear progression and stamina/health conservation", max_length=200)
    resolution: str = Field(default="Clear all objectives or waves to win", max_length=200)

    model_config = ConfigDict(extra="ignore")

    @field_validator("player_action", "immediate_feedback", "increasing_pressure", "progression", "resolution")
    @classmethod
    def validate_safe_loop_text(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v


class ObjectiveSpec(BaseModel):
    """Structured primary and supporting gameplay objectives."""
    primary: str = Field(..., min_length=1, max_length=200)
    supporting: List[str] = Field(default_factory=list, max_length=4)
    completion_criteria: str = Field(default="all_collectibles_gathered_or_waves_cleared", max_length=100)
    failure_condition: str = Field(default="player_health_depleted", max_length=100)

    model_config = ConfigDict(extra="ignore")

    @field_validator("primary", "completion_criteria", "failure_condition")
    @classmethod
    def validate_safe_obj_text(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v

    @field_validator("supporting")
    @classmethod
    def validate_safe_supporting(cls, v: List[str]) -> List[str]:
        cleaned = []
        for item in v:
            if isinstance(item, str):
                check_for_script_injection(item)
                cleaned.append(item.strip())
        return cleaned


class ProgressionPhase(BaseModel):
    """Structured pacing phase (EARLY, MID, FINALE)."""
    phase: Literal["EARLY", "MID", "FINALE"] = "EARLY"
    trigger: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=200)
    runtime_effect: str = Field(..., min_length=1, max_length=200)

    model_config = ConfigDict(extra="ignore")

    @field_validator("trigger", "description", "runtime_effect")
    @classmethod
    def validate_safe_phase_text(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v


class GameDesignSpec(BaseModel):
    """
    Structured Game Design Specification V2.
    
    Acts as an explicit intermediate design layer between natural-language user concepts
    and executable Phaser Game DSL schemas.
    """
    title: str = Field(..., min_length=1, max_length=100)
    elevator_pitch: str = Field(..., min_length=1, max_length=300)
    genre: str = Field(..., min_length=1, max_length=50)
    subgenre: Optional[str] = Field(default="Arcade", max_length=50)
    theme: Literal["cyberpunk", "retro_arcade", "dungeon", "space", "neon", "minimal"] = "neon"
    visual_style: str = Field(default="Stylized procedural vector arcade", max_length=100)
    camera: Literal["top_down", "side_view", "fixed_arena"] = "top_down"
    core_gameplay_loop: str = Field(..., min_length=1, max_length=200)
    player_role: str = Field(..., min_length=1, max_length=100)
    primary_objective: str = Field(..., min_length=1, max_length=200)
    secondary_objectives: List[str] = Field(default_factory=list, max_length=5)
    player_abilities: List[str] = Field(default_factory=lambda: ["move", "dash", "shoot"], max_length=6)
    enemy_archetypes: List[Dict[str, Any]] = Field(default_factory=list, max_length=6)
    hazards: List[Dict[str, Any]] = Field(default_factory=list, max_length=6)
    collectibles: List[Dict[str, Any]] = Field(default_factory=list, max_length=6)
    progression: Dict[str, Any] = Field(default_factory=dict)
    difficulty_curve: Literal["gentle", "escalating", "challenging"] = "escalating"
    win_conditions: List[str] = Field(default_factory=list, max_length=3)
    loss_conditions: List[str] = Field(default_factory=lambda: ["player_health_depleted"], max_length=3)
    level_structure: Dict[str, Any] = Field(default_factory=dict)
    estimated_session_length: str = Field(default="2-3 minutes", max_length=50)
    selected_modules: List[str] = Field(default_factory=list)
    rationale: List[str] = Field(default_factory=list, max_length=6)

    # V2 Structured Extensions
    loop_details: Optional[CoreLoopSpec] = None
    objective_details: Optional[ObjectiveSpec] = None
    progression_phases: List[ProgressionPhase] = Field(default_factory=list, max_length=5)

    # Phase 6: World Mode & Open World Structure
    world_mode: Literal["linear", "campaign", "open_world"] = "linear"
    open_world_structure: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="ignore")

    @field_validator(
        "title",
        "elevator_pitch",
        "genre",
        "subgenre",
        "visual_style",
        "core_gameplay_loop",
        "player_role",
        "primary_objective",
        "estimated_session_length",
    )
    @classmethod
    def validate_safe_text(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v

    @field_validator("secondary_objectives", "player_abilities", "win_conditions", "loss_conditions", "rationale")
    @classmethod
    def validate_string_list(cls, v: List[str]) -> List[str]:
        cleaned = []
        for item in v:
            if isinstance(item, str):
                check_for_script_injection(item)
                cleaned.append(item.strip())
        return cleaned
