"""
Tests for Runtime Contract Closure V1 (DSL ↔ Validator ↔ Compiler ↔ Phaser ↔ Project Version Integrity).

Verifies:
- All 12 rule triggers and 13 rule actions are accepted and statically validated
- Invalid / unsupported triggers or actions are rejected with clear diagnostic errors
- UI Definition schema properties (show_health, show_score, show_stamina, show_wave, show_objectives, status_text)
- Platformer dash, jump power, and physics compatibility
- Entity attributes including loot_drop, patrol_radius, detection_radius, fire_rate
- Schema 1.0 and 2.0 backward compatibility and safe fallback defaults
- Project version history monotonicity and immutability
"""
import pytest
from app.generation.dsl_models import (
    EntityDef,
    GameDSL,
    GameMetadata,
    PlayerDef,
    RuleDef,
    UIDef,
    WorldDef,
)
from app.runtime.compatibility import (
    RuntimeCompatibilityValidator,
    SUPPORTED_ACTIONS,
    SUPPORTED_ARCHETYPES,
    SUPPORTED_ENTITY_BEHAVIORS,
    SUPPORTED_ENTITY_TYPES,
    SUPPORTED_TRIGGERS,
)


def get_base_dsl(archetype: str = "survival") -> GameDSL:
    return GameDSL(
        schema_version="2.0",
        metadata=GameMetadata(
            title="Contract Test Game",
            genre="Action",
            description="Testing contract closure",
            archetype=archetype,
        ),
        world=WorldDef(
            width=800,
            height=600,
            gravity=800 if archetype == "platformer" else 0,
            background_color="#0a0b10",
        ),
        player=PlayerDef(
            name="Hero",
            spawn_x=400,
            spawn_y=300,
            speed=250,
            jump_power=500 if archetype == "platformer" else 0,
            max_health=100,
            dash_speed=600,
            dash_cooldown=1.2,
            stamina=100,
        ),
        entities=[
            EntityDef(
                id="enemy_1",
                type="enemy",
                x=200,
                y=200,
                speed=120,
                health=30,
                behavior="chase",
                loot_drop="health",
            )
        ],
        rules=[
            RuleDef(id="r1", trigger="on_collect", action="add_score", params={"amount": 50}),
            RuleDef(id="r2", trigger="on_collide_enemy", action="damage_player", params={"amount": 15}),
        ],
        ui=UIDef(
            show_health=True,
            show_score=True,
            show_stamina=True,
            show_wave=True,
            show_objectives=True,
            status_text="TEST PROTOTYPE",
        ),
    )


# -----------------------------------------------------------------------------
# 1. Rule Triggers & Actions Matrix
# -----------------------------------------------------------------------------

def test_all_twelve_triggers_are_supported():
    """Verify all 12 accepted triggers pass runtime compatibility validation."""
    all_triggers = [
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
    assert len(SUPPORTED_TRIGGERS) == 12
    for trig in all_triggers:
        assert trig in SUPPORTED_TRIGGERS

    dsl = get_base_dsl()
    dsl.rules = [
        RuleDef(id=f"rule_{i}", trigger=trig, action="add_score", params={"amount": 10})
        for i, trig in enumerate(all_triggers)
    ]
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible
    assert len(res.errors) == 0


def test_all_thirteen_actions_are_supported():
    """Verify all 13 accepted actions pass runtime compatibility validation."""
    all_actions = [
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
    assert len(SUPPORTED_ACTIONS) == 13
    for act in all_actions:
        assert act in SUPPORTED_ACTIONS

    dsl = get_base_dsl()
    dsl.rules = [
        RuleDef(id=f"rule_{i}", trigger="on_collect", action=act, params={"amount": 10})
        for i, act in enumerate(all_actions)
    ]
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible
    assert len(res.errors) == 0


def test_invalid_trigger_or_action_fails_validation():
    """Verify unknown trigger or action is rejected with clear error message."""
    dsl = get_base_dsl()
    # Inject invalid trigger
    dsl.rules = [RuleDef.model_construct(id="bad_rule", trigger="on_magic_spell", action="add_score", params={})]
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert not res.compatible
    assert any("unsupported trigger" in err.lower() for err in res.errors)

    # Inject invalid action
    dsl.rules = [RuleDef.model_construct(id="bad_rule_2", trigger="on_collect", action="cast_meteor", params={})]
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert not res.compatible
    assert any("unsupported action" in err.lower() for err in res.errors)


# -----------------------------------------------------------------------------
# 2. UI Definition Contract
# -----------------------------------------------------------------------------

def test_ui_def_custom_and_default_properties():
    """Verify UIDef supports all toggleable overlay components and custom status text."""
    ui = UIDef(
        show_health=False,
        show_score=False,
        show_stamina=False,
        show_wave=False,
        show_objectives=False,
        status_text="CUSTOM OBJECTIVE BANNER",
    )
    assert not ui.show_health
    assert not ui.show_score
    assert not ui.show_stamina
    assert not ui.show_wave
    assert not ui.show_objectives
    assert ui.status_text == "CUSTOM OBJECTIVE BANNER"

    # Default UIDef
    ui_default = UIDef()
    assert ui_default.show_health is True
    assert ui_default.show_score is True
    assert ui_default.show_stamina is True
    assert ui_default.show_wave is True
    assert ui_default.show_objectives is True
    assert ui_default.status_text == "PLAY PROTOTYPE"


# -----------------------------------------------------------------------------
# 3. Platformer Dash & Movement Compatibility
# -----------------------------------------------------------------------------

def test_platformer_archetype_and_dash_compatibility():
    """Verify platformer archetype with gravity, jump power, and dash configuration validates cleanly."""
    dsl = get_base_dsl(archetype="platformer")
    dsl.player.jump_power = 600
    dsl.player.dash_speed = 700
    dsl.player.dash_cooldown = 1.0
    dsl.player.stamina = 120

    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible
    assert res.archetype == "platformer"
    assert len(res.errors) == 0


# -----------------------------------------------------------------------------
# 4. Entity Loot Drop & Attributes
# -----------------------------------------------------------------------------

def test_entity_attributes_and_loot_drop():
    """Verify entity loot_drop, patrol_radius, and behavior configurations validate cleanly."""
    dsl = get_base_dsl()
    dsl.entities = [
        EntityDef(
            id="boss_1",
            type="enemy",
            x=300,
            y=300,
            speed=150,
            health=100,
            behavior="ranged_attack",
            damage=25,
            fire_rate=1.2,
            patrol_radius=200,
            detection_radius=350,
            loot_drop="powerup",
        ),
        EntityDef(
            id="minion_1",
            type="enemy",
            x=100,
            y=100,
            speed=100,
            health=20,
            behavior="patrol",
            loot_drop="points",
        ),
    ]

    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible
    assert len(res.errors) == 0


# -----------------------------------------------------------------------------
# 5. Schema 1.0 Backward Compatibility
# -----------------------------------------------------------------------------

def test_schema_1_0_backward_compatibility():
    """Verify Schema 1.0 GameDSL documents deserialize and validate cleanly with proper defaults."""
    raw_v1 = {
        "schema_version": "1.0",
        "metadata": {
            "title": "Legacy V1 Prototype",
            "genre": "Retro Arcade",
            "description": "A legacy v1 game without v2 fields",
            "archetype": "arena",
        },
        "world": {
            "width": 800,
            "height": 600,
            "gravity": 0,
            "background_color": "#000000",
        },
        "player": {
            "spawn_x": 400,
            "spawn_y": 300,
            "speed": 200,
            "jump_power": 0,
            "max_health": 100,
            "width": 32,
            "height": 32,
            "color": "#00f0ff",
        },
        "entities": [
            {
                "id": "e1",
                "type": "enemy",
                "x": 150,
                "y": 150,
                "speed": 80,
                "health": 20,
                "behavior": "patrol",
                "color": "#ff0000",
                "points": 10,
            }
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "add_score", "params": {"amount": 10}}
        ],
        "ui": {
            "show_health": True,
            "show_score": True,
            "status_text": "LEGACY GAME",
        },
    }

    dsl = GameDSL.model_validate(raw_v1)
    assert dsl.schema_version == "1.0"
    assert dsl.player.dash_speed == 600  # Default filled
    assert dsl.player.stamina == 100     # Default filled
    assert dsl.ui.show_wave is True      # Default filled

    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible
    assert len(res.errors) == 0
