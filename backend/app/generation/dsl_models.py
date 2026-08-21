import re
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.design_spec import GameDesignSpec, check_for_script_injection, HEX_COLOR_REGEX


class GameMetadata(BaseModel):
    """Metadata describing the generated game concept."""
    title: str = Field(..., min_length=1, max_length=100)
    genre: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=500)
    archetype: Literal["survival", "shooter", "runner", "platformer", "arena", "collector"] = "survival"

    model_config = ConfigDict(extra="ignore")

    @field_validator("title", "genre", "description")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()


class WorldDef(BaseModel):
    """Environment and world boundaries for the Phaser 2D canvas."""
    width: int = Field(800, ge=400, le=3840)
    height: int = Field(600, ge=300, le=2160)
    gravity: int = Field(0, ge=0, le=2000)
    background_color: str = Field("#0a0b10")
    theme: Literal["cyberpunk", "retro_arcade", "dungeon", "space", "neon", "minimal"] = "neon"
    difficulty_scaling: float = Field(1.0, ge=0.5, le=5.0)
    wave_count: int = Field(3, ge=1, le=10)
    procedural_seed: Optional[int] = None
    hazard_density: int = Field(30, ge=0, le=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("background_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError(f"Invalid hex color format: '{v}'. Must be e.g. #000 or #00ff00.")
        return v


class PlayerDef(BaseModel):
    """Player avatar spawn, locomotion, combat, and vitality parameters."""
    name: Optional[str] = Field(default="Player", max_length=50)
    spawn_x: int = Field(400, ge=0, le=3840)
    spawn_y: int = Field(300, ge=0, le=2160)
    speed: int = Field(250, ge=10, le=1000)
    jump_power: int = Field(0, ge=0, le=1500)
    max_health: int = Field(100, ge=1, le=1000)
    width: int = Field(32, ge=8, le=200)
    height: int = Field(32, ge=8, le=200)
    color: str = Field("#00f0ff")

    # V2 Expanded Mechanics
    dash_speed: int = Field(600, ge=0, le=1500)
    dash_cooldown: float = Field(1.2, ge=0.0, le=10.0)
    stamina: int = Field(100, ge=0, le=500)
    attack_type: Literal["melee", "ranged", "aoe", "none"] = "ranged"
    attack_damage: int = Field(25, ge=1, le=500)
    attack_cooldown: float = Field(0.25, ge=0.05, le=5.0)
    weapon_color: str = Field("#ffea00")

    model_config = ConfigDict(extra="forbid")

    @field_validator("color", "weapon_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError(f"Invalid hex color format: '{v}'.")
        return v


class EntityDef(BaseModel):
    """Interactive entity (enemy, collectible, obstacle, platform, hazard) in the game world."""
    id: str = Field(..., min_length=1, max_length=50)
    type: Literal["enemy", "collectible", "obstacle", "platform", "hazard"] = "enemy"
    x: int = Field(..., ge=0, le=3840)
    y: int = Field(..., ge=0, le=2160)
    width: int = Field(24, ge=4, le=500)
    height: int = Field(24, ge=4, le=500)
    speed: int = Field(100, ge=0, le=800)
    health: int = Field(20, ge=0, le=1000)
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
    color: str = Field("#ff0055")
    points: int = Field(10, ge=0, le=10000)

    # V2 Expanded Entity Attributes
    damage: int = Field(15, ge=0, le=500)
    fire_rate: float = Field(1.5, ge=0.1, le=10.0)
    patrol_radius: int = Field(150, ge=20, le=1000)
    detection_radius: int = Field(250, ge=20, le=1500)
    loot_drop: Optional[str] = None

    # Phase 5: Boss/Finale Attributes. Safe defaults (is_boss=False, boss_phases=1,
    # telegraph_ms=0) mean every pre-Phase-5 DSL (schema 1.0/2.0/3.0, no boss fields
    # present) still validates unchanged -- none of these are required fields.
    is_boss: bool = False
    boss_phases: int = Field(1, ge=1, le=2)
    telegraph_ms: int = Field(0, ge=0, le=2000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not HEX_COLOR_REGEX.match(v):
            raise ValueError(f"Invalid hex color format: '{v}'.")
        return v

    @model_validator(mode="after")
    def validate_boss_health(self) -> "EntityDef":
        # A boss must be a meaningful health-pool threat on its own terms; the
        # stronger scope-aware comparison against sibling enemies (>= 2x the
        # strongest non-boss enemy in the same entity list) is enforced separately
        # in GameplayQualityValidator.validate(), which has access to the full
        # entity list this single-entity validator does not.
        if self.is_boss and self.health < 150:
            raise ValueError(
                f"Boss entity '{self.id}' has health {self.health}, below the minimum required boss health (150)."
            )
        return self


class RuleDef(BaseModel):
    """Gameplay mechanics and event-driven trigger/action rules."""
    id: str = Field(..., min_length=1, max_length=50)
    trigger: Literal[
        "on_collect",
        "on_collide_enemy",
        "on_reach_goal",
        "on_score_target",
        "on_time_limit",
        "on_player_death",
        "on_wave_start",
        "on_dash",
        "on_hazard_touch",
        "on_enemy_defeat",
        "on_checkpoint",
        "on_powerup_expire",
    ]
    action: Literal[
        "add_score",
        "damage_player",
        "heal_player",
        "win_game",
        "lose_game",
        "spawn_entity",
        "speed_boost",
        "trigger_screen_shake",
        "spawn_wave",
        "grant_powerup",
        "activate_checkpoint",
        "spawn_particles",
        "knockback_target",
    ]
    params: Dict[str, Union[int, float, str, bool]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()

    @field_validator("params")
    @classmethod
    def validate_params(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(v) > 15:
            raise ValueError("Too many rule parameters (maximum 15 allowed).")
        check_for_script_injection(v)
        return v


class UIDef(BaseModel):
    """Overlay heads-up display options."""
    show_health: bool = True
    show_score: bool = True
    show_stamina: bool = True
    show_wave: bool = True
    show_objectives: bool = True
    status_text: str = Field("PLAY PROTOTYPE", max_length=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("status_text")
    @classmethod
    def validate_status_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()


class ObjectiveDef(BaseModel):
    """Structured gameplay completion criteria for a stage or game."""
    type: Literal["collect_all", "defeat_all", "reach_exit", "survive_time", "score_target"] = "collect_all"
    target_count: int = Field(1, ge=1, le=100)
    target_score: int = Field(100, ge=0, le=100000)
    time_limit_seconds: int = Field(0, ge=0, le=600)
    exit_x: Optional[int] = Field(None, ge=0, le=3840)
    exit_y: Optional[int] = Field(None, ge=0, le=2160)
    description: str = Field("Complete stage objective", max_length=150)

    model_config = ConfigDict(extra="forbid")

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()


class LevelDef(BaseModel):
    """Structured stage/level specification in a multi-level campaign game."""
    level_number: int = Field(1, ge=1, le=10)
    title: str = Field("Stage 1", min_length=1, max_length=100)
    theme: Optional[Literal["cyberpunk", "retro_arcade", "dungeon", "space", "neon", "minimal"]] = None
    world: Optional[WorldDef] = None
    spawn_x: Optional[int] = Field(None, ge=0, le=3840)
    spawn_y: Optional[int] = Field(None, ge=0, le=2160)
    objective: ObjectiveDef = Field(default_factory=ObjectiveDef)
    entities: List[EntityDef] = Field(default_factory=list, max_length=30)
    rules: List[RuleDef] = Field(default_factory=list, max_length=15)
    completion_message: str = Field("STAGE COMPLETE!", max_length=100)

    # Phase 5: explicit finale marker. Defaults to False so every existing DSL
    # (which predates this field) still validates unchanged.
    is_finale: bool = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "completion_message")
    @classmethod
    def validate_safe_text(cls, v: str) -> str:
        check_for_script_injection(v)
        return v.strip()


class GameDSL(BaseModel):
    """
    Authoritative top-level Game DSL Schema.
    
    This is the strict safety boundary between natural language AI generation
    and Phaser 2D browser execution.
    """
    schema_version: Literal["1.0", "2.0", "3.0"] = "3.0"
    metadata: GameMetadata
    world: WorldDef = Field(default_factory=WorldDef)
    player: PlayerDef = Field(default_factory=PlayerDef)
    entities: List[EntityDef] = Field(default_factory=list, max_length=30)
    rules: List[RuleDef] = Field(default_factory=list, max_length=20)
    ui: UIDef = Field(default_factory=UIDef)
    design_spec: Optional[GameDesignSpec] = None

    # V3 Multi-Level / Multi-Stage Campaign Support (bounded to 5 levels max)
    levels: List[LevelDef] = Field(default_factory=list, max_length=5)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_cross_field_consistency(self) -> "GameDSL":
        # Check that player spawn is within world boundaries
        if self.player.spawn_x > self.world.width:
            self.player.spawn_x = self.world.width // 2
        if self.player.spawn_y > self.world.height:
            self.player.spawn_y = self.world.height // 2

        # Check that entity positions are bounded by world
        for ent in self.entities:
            if ent.x > self.world.width:
                ent.x = max(0, self.world.width - ent.width)
            if ent.y > self.world.height:
                ent.y = max(0, self.world.height - ent.height)

        # Cross-field validations across multi-level campaign if present
        for lvl in self.levels:
            lvl_world = lvl.world or self.world
            if lvl.spawn_x is not None and lvl.spawn_x > lvl_world.width:
                lvl.spawn_x = lvl_world.width // 2
            if lvl.spawn_y is not None and lvl.spawn_y > lvl_world.height:
                lvl.spawn_y = lvl_world.height // 2

            for ent in lvl.entities:
                if ent.x > lvl_world.width:
                    ent.x = max(0, lvl_world.width - ent.width)
                if ent.y > lvl_world.height:
                    ent.y = max(0, lvl_world.height - ent.height)

        return self
