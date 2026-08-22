import re
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.design_spec import HEX_COLOR_REGEX, check_for_script_injection

# Runtime-supported Phaser entity behaviors (validated against runtime capability registry)
SUPPORTED_ACTOR_BEHAVIORS = {
    "patrol",
    "chase",
    "stationary",
    "bounce",
    "float",
    "flee",
    "guard",
    "ranged_attack",
}


class RegionDef(BaseModel):
    """A distinct geographical zone or district in an open-world setting."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    theme: str = Field(default="cyberpunk", max_length=50)
    bounds_x: int = Field(0, ge=0, le=100000)
    bounds_y: int = Field(0, ge=0, le=100000)
    width: int = Field(800, ge=400, le=3840)
    height: int = Field(600, ge=300, le=2160)
    danger_level: int = Field(1, ge=1, le=10)
    population_density: int = Field(5, ge=0, le=20)
    controlling_faction: Optional[str] = Field(default=None, max_length=50)
    traversal_connections: List[str] = Field(default_factory=list, max_length=10)
    background_color: Optional[str] = Field(default=None)
    ambient_theme: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name", "theme")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("background_color")
    @classmethod
    def validate_hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not HEX_COLOR_REGEX.match(v):
                raise ValueError(f"Invalid hex color format: '{v}'.")
        return v


class WorldConnectionDef(BaseModel):
    """Traversable link between two regions."""
    from_region: str = Field(..., min_length=1, max_length=50)
    to_region: str = Field(..., min_length=1, max_length=50)
    bidirectional: bool = True
    traversal_types: List[Literal["on_foot", "vehicle", "fast_travel"]] = Field(
        default_factory=lambda: ["on_foot", "vehicle"]
    )
    required_state_key: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("from_region", "to_region")
    @classmethod
    def validate_safe_id(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()


class POIDef(BaseModel):
    """Point of interest within a region (shop, garage, mission giver, safehouse, etc.)."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal[
        "safehouse",
        "shop",
        "garage",
        "outpost",
        "terminal",
        "landmark",
        "hospital",
        "mission_giver",
        "dungeon",
        "station",
        "hideout",
        "arena",
        "resource_node",
    ] = "landmark"
    region_id: str = Field(..., min_length=1, max_length=50)
    x: int = Field(..., ge=0, le=3840)
    y: int = Field(..., ge=0, le=2160)
    icon: Optional[str] = Field(default=None, max_length=50)
    discovered: bool = True
    activity_ids: List[str] = Field(default_factory=list, max_length=10)
    interaction_text: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name", "region_id")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("interaction_text")
    @classmethod
    def validate_interaction(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v


class ActivityPrerequisite(BaseModel):
    """Requirements before an activity can be accepted or started."""
    min_reputation: Dict[str, int] = Field(default_factory=dict)
    required_state: Dict[str, Union[int, float, str, bool]] = Field(default_factory=dict)
    completed_activities: List[str] = Field(default_factory=list, max_length=10)

    model_config = ConfigDict(extra="forbid")

    @field_validator("min_reputation", "required_state")
    @classmethod
    def validate_prereq_dict(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        check_for_script_injection(v)
        return v


class ActivityConsequence(BaseModel):
    """World-state mutations applied upon activity resolution."""
    reputation_changes: Dict[str, int] = Field(default_factory=dict)
    threat_change: int = Field(0, ge=-5, le=5)
    state_mutations: Dict[str, Union[int, float, str, bool]] = Field(default_factory=dict)
    unlock_regions: List[str] = Field(default_factory=list, max_length=5)
    unlock_pois: List[str] = Field(default_factory=list, max_length=10)
    message: Optional[str] = Field(default=None, max_length=150)

    model_config = ConfigDict(extra="forbid")

    @field_validator("state_mutations", "reputation_changes")
    @classmethod
    def validate_conseq_dict(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        check_for_script_injection(v)
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v


class ActivityDef(BaseModel):
    """Structured generic activity or mission definition."""
    id: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=300)
    type: Literal[
        "mission",
        "delivery",
        "race",
        "combat",
        "collection",
        "investigation",
        "escort",
        "patrol",
        "exploration",
        "minigame",
    ] = "mission"
    region_id: Optional[str] = Field(default=None, max_length=50)
    start_poi_id: Optional[str] = Field(default=None, max_length=50)
    target_poi_id: Optional[str] = Field(default=None, max_length=50)
    target_actor_id: Optional[str] = Field(default=None, max_length=50)
    target_count: int = Field(1, ge=1, le=100)
    time_limit_seconds: int = Field(0, ge=0, le=600)
    prerequisites: ActivityPrerequisite = Field(default_factory=ActivityPrerequisite)
    rewards: Dict[str, Union[int, float, str, bool]] = Field(default_factory=dict)
    success_consequences: ActivityConsequence = Field(default_factory=ActivityConsequence)
    failure_consequences: Optional[ActivityConsequence] = None
    status: Literal["available", "active", "completed", "failed", "locked"] = "available"

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "title", "description")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("rewards")
    @classmethod
    def validate_rewards(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        check_for_script_injection(v)
        return v


class ScheduleDef(BaseModel):
    """Coarse NPC schedule slot."""
    start_hour: int = Field(8, ge=0, le=23)
    end_hour: int = Field(18, ge=0, le=23)
    region_id: str = Field(..., min_length=1, max_length=50)
    poi_id: Optional[str] = Field(default=None, max_length=50)
    activity_name: str = Field("idle", max_length=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("region_id", "activity_name")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()


class ActorDef(BaseModel):
    """Generic living world actor (civilian, guard, merchant, quest giver, courier, etc.)."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    archetype: Literal[
        "civilian",
        "guard",
        "security",
        "merchant",
        "quest_giver",
        "hostile",
        "companion",
        "patrol",
        "courier",
    ] = "civilian"
    faction_id: Optional[str] = Field(default=None, max_length=50)
    region_id: str = Field(..., min_length=1, max_length=50)
    x: int = Field(..., ge=0, le=3840)
    y: int = Field(..., ge=0, le=2160)
    width: int = Field(24, ge=8, le=200)
    height: int = Field(24, ge=8, le=200)
    health: int = Field(50, ge=1, le=1000)
    speed: int = Field(80, ge=0, le=500)
    behavior: Literal[
        "patrol",
        "chase",
        "stationary",
        "bounce",
        "float",
        "flee",
        "guard",
        "ranged_attack",
    ] = "patrol"
    color: str = Field("#aaaaaa")
    dialogue: Optional[str] = Field(default=None, max_length=300)
    schedules: List[ScheduleDef] = Field(default_factory=list, max_length=5)
    gives_activity_id: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name", "region_id")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("dialogue")
    @classmethod
    def validate_dialogue(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError(f"Invalid hex color format: '{v}'.")
        return v

    @field_validator("behavior")
    @classmethod
    def validate_supported_behavior(cls, v: str) -> str:
        if v not in SUPPORTED_ACTOR_BEHAVIORS:
            raise ValueError(
                f"Unsupported actor behavior '{v}'. Must be one of {sorted(SUPPORTED_ACTOR_BEHAVIORS)}."
            )
        return v


class FactionDef(BaseModel):
    """Generic faction or group with territory, reputation, and response units."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=300)
    initial_reputation: int = Field(0, ge=-100, le=100)
    hostility_threshold: int = Field(-20, ge=-100, le=100)
    controlled_regions: List[str] = Field(default_factory=list, max_length=10)
    color: str = Field("#ff3366")
    alert_unit_archetype: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError(f"Invalid hex color format: '{v}'.")
        return v


class VehicleDef(BaseModel):
    """Traversable vehicle actor in the open world."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal["car", "bike", "hovercraft", "truck", "speedster", "mount", "cart", "buggy"] = "car"
    region_id: str = Field(..., min_length=1, max_length=50)
    x: int = Field(..., ge=0, le=3840)
    y: int = Field(..., ge=0, le=2160)
    width: int = Field(48, ge=16, le=200)
    height: int = Field(28, ge=12, le=200)
    max_speed: int = Field(450, ge=100, le=1200)
    acceleration: int = Field(400, ge=50, le=1000)
    handling: float = Field(2.5, ge=0.5, le=10.0)
    health: int = Field(200, ge=10, le=2000)
    color: str = Field("#00ffff")
    traversal_mode: Literal["ground", "hover", "water"] = "ground"
    is_occupied: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name", "region_id")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError(f"Invalid hex color format: '{v}'.")
        return v


class ThreatResponseUnitDef(BaseModel):
    """Specification of actor units deployed when threat level is active."""
    min_threat_level: int = Field(1, ge=1, le=5)
    archetype: Literal[
        "civilian",
        "guard",
        "security",
        "merchant",
        "quest_giver",
        "hostile",
        "companion",
        "patrol",
        "courier",
    ] = "security"
    count: int = Field(2, ge=1, le=10)
    faction_id: Optional[str] = Field(default=None, max_length=50)
    behavior: Literal[
        "patrol",
        "chase",
        "stationary",
        "bounce",
        "float",
        "flee",
        "guard",
        "ranged_attack",
    ] = "chase"

    model_config = ConfigDict(extra="forbid")


class ThreatSystemDef(BaseModel):
    """Generic alert / threat escalation framework (levels 0-5)."""
    name: str = Field("Threat Level", max_length=50)
    current_level: int = Field(0, ge=0, le=5)
    max_level: int = Field(5, ge=1, le=5)
    decay_rate_per_sec: float = Field(0.05, ge=0.0, le=1.0)
    escalation_events: List[str] = Field(
        default_factory=lambda: ["on_combat", "on_crime", "on_trespass", "on_alarm"],
        max_length=10,
    )
    response_units: List[ThreatResponseUnitDef] = Field(default_factory=list, max_length=5)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()


class WorldTimeDef(BaseModel):
    """Accelerated deterministic world time."""
    start_hour: int = Field(8, ge=0, le=23)
    time_scale: float = Field(60.0, ge=1.0, le=600.0)
    day_night_cycle: bool = True

    model_config = ConfigDict(extra="forbid")


class WorldEventDef(BaseModel):
    """Dynamic structured world event."""
    id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal[
        "faction_conflict",
        "roadblock",
        "security_lockdown",
        "convoy",
        "storm",
        "market_surge",
        "swarm_attack",
        "festival",
    ] = "security_lockdown"
    region_ids: List[str] = Field(default_factory=list, max_length=6)
    trigger_state_key: Optional[str] = Field(default=None, max_length=50)
    duration_seconds: int = Field(60, ge=5, le=600)
    active: bool = False
    threat_modifier: int = Field(0, ge=-5, le=5)
    danger_modifier: int = Field(0, ge=-5, le=5)
    description: Optional[str] = Field(default=None, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id", "name")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: Optional[str]) -> Optional[str]:
        if v:
            check_for_script_injection(v)
            return v.strip()
        return v


class OpenWorldDef(BaseModel):
    """Authoritative top-level Open World specification."""
    regions: List[RegionDef] = Field(default_factory=list, min_length=2, max_length=6)
    connections: List[WorldConnectionDef] = Field(default_factory=list, max_length=15)
    factions: List[FactionDef] = Field(default_factory=list, min_length=1, max_length=5)
    pois: List[POIDef] = Field(default_factory=list, min_length=3, max_length=25)
    activities: List[ActivityDef] = Field(default_factory=list, min_length=2, max_length=15)
    vehicles: List[VehicleDef] = Field(default_factory=list, min_length=1, max_length=10)
    actors: List[ActorDef] = Field(default_factory=list, max_length=50)
    threat_system: Optional[ThreatSystemDef] = Field(default_factory=ThreatSystemDef)
    time_system: Optional[WorldTimeDef] = Field(default_factory=WorldTimeDef)
    events: List[WorldEventDef] = Field(default_factory=list, max_length=5)
    initial_state: Dict[str, Union[int, float, str, bool]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("initial_state")
    @classmethod
    def validate_initial_state(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(v) > 20:
            raise ValueError("Too many initial world state keys (maximum 20 allowed).")
        check_for_script_injection(v)
        return v
