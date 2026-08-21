"""
Unit and regression tests for Entity Behavior System V1 and Runtime Compatibility.

Verifies:
- All 8 DSL-supported entity behaviors (stationary, bounce, float, patrol, chase, flee, guard, ranged_attack)
- Entity parameters (speed, damage, fire_rate, patrol_radius, detection_radius, health)
- Runtime compatibility validation across all behaviors
- Rejection of unsupported behaviors and out-of-bounds parameters
"""
import pytest
from pydantic import ValidationError

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
    SUPPORTED_ENTITY_BEHAVIORS,
)


def create_dsl_with_entities(entities: list[EntityDef]) -> GameDSL:
    return GameDSL(
        schema_version="2.0",
        metadata=GameMetadata(
            title="Entity Behavior Test",
            genre="Action",
            description="Testing full entity behavior matrix.",
            archetype="survival",
        ),
        world=WorldDef(width=800, height=600, theme="neon"),
        player=PlayerDef(spawn_x=400, spawn_y=300),
        entities=entities,
        rules=[
            RuleDef(id="r1", trigger="on_collect", action="add_score", params={"amount": 10}),
        ],
        ui=UIDef(show_health=True, show_score=True, status_text="PLAY"),
    )


# -----------------------------------------------------------------------------
# 1. All 8 Behaviors Validation
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("behavior", [
    "stationary",
    "bounce",
    "float",
    "patrol",
    "chase",
    "flee",
    "guard",
    "ranged_attack",
])
def test_all_supported_behaviors_pass_validation(behavior: str):
    """Verify each of the 8 behaviors is valid in Pydantic schema and passes compatibility check."""
    assert behavior in SUPPORTED_ENTITY_BEHAVIORS

    ent = EntityDef(
        id=f"test_{behavior}",
        type="enemy",
        x=200,
        y=200,
        width=24,
        height=24,
        speed=120,
        health=30,
        behavior=behavior,  # type: ignore
        damage=20,
        fire_rate=1.2,
        patrol_radius=150,
        detection_radius=250,
        color="#ff0055",
        points=50,
    )
    dsl = create_dsl_with_entities([ent])
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is True
    assert len(res.errors) == 0


def test_unsupported_behavior_rejected_by_pydantic():
    """Verify unknown or arbitrary behaviors are rejected during schema parsing."""
    with pytest.raises(ValidationError):
        EntityDef(
            id="bad_ent",
            type="enemy",
            x=100,
            y=100,
            behavior="teleport_and_destroy",  # type: ignore
        )


def test_unsupported_behavior_rejected_by_compatibility_validator():
    """Verify runtime compatibility catches unsupported behavior if manually overridden."""
    ent = EntityDef(
        id="ent_hack",
        type="enemy",
        x=100,
        y=100,
        behavior="patrol",
    )
    # Manually bypass pydantic validation for static boundary test
    ent.behavior = "custom_script_behavior"  # type: ignore
    dsl = create_dsl_with_entities([ent])
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is False
    assert any("unsupported behavior 'custom_script_behavior'" in err for err in res.errors)


# -----------------------------------------------------------------------------
# 2. Entity Parameter Bounds & Invariant Validation
# -----------------------------------------------------------------------------

def test_entity_parameter_bounds():
    """Verify numeric bounds on fire_rate, patrol_radius, detection_radius, and speed."""
    # Valid bounds
    ent = EntityDef(
        id="param_test",
        type="enemy",
        x=150,
        y=150,
        speed=800,
        health=1000,
        damage=500,
        fire_rate=0.1,
        patrol_radius=1000,
        detection_radius=1500,
        behavior="ranged_attack",
    )
    assert ent.fire_rate == 0.1
    assert ent.detection_radius == 1500

    # Out of bounds speed
    with pytest.raises(ValidationError):
        EntityDef(id="bad_speed", type="enemy", x=100, y=100, speed=900)

    # Out of bounds fire_rate
    with pytest.raises(ValidationError):
        EntityDef(id="bad_fire", type="enemy", x=100, y=100, fire_rate=0.01)

    # Out of bounds patrol_radius (< 20)
    with pytest.raises(ValidationError):
        EntityDef(id="bad_patrol", type="enemy", x=100, y=100, patrol_radius=10)


def test_entity_id_script_injection_blocked():
    """Verify script injection in entity ID is prohibited."""
    with pytest.raises(ValueError) as exc:
        EntityDef(
            id="<script>alert(1)</script>",
            type="enemy",
            x=100,
            y=100,
        )
    assert "Prohibited script" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. Compatibility Validator Sanity Warnings
# -----------------------------------------------------------------------------

def test_compatibility_validator_emits_warning_for_zero_speed_dynamic_behavior():
    """Verify warning when moving behavior has speed=0."""
    ent = EntityDef(
        id="ent_still_chaser",
        type="enemy",
        x=100,
        y=100,
        speed=0,
        behavior="chase",
    )
    dsl = create_dsl_with_entities([ent])
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is True
    assert any("speed is 0" in warn for warn in res.warnings)


def test_compatibility_validator_emits_warning_for_zero_damage_ranged_attack():
    """Verify warning when ranged_attack has damage=0."""
    ent = EntityDef(
        id="ent_ranged_harmless",
        type="enemy",
        x=100,
        y=100,
        speed=100,
        damage=0,
        behavior="ranged_attack",
    )
    dsl = create_dsl_with_entities([ent])
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is True
    assert any("0 damage" in warn for warn in res.warnings)


# -----------------------------------------------------------------------------
# 4. Multi-Entity Behavior Matrix Integration
# -----------------------------------------------------------------------------

def test_full_behavior_matrix_game_dsl():
    """Verify a complete GameDSL with all 8 behaviors simultaneously compiles cleanly."""
    behaviors = [
        "stationary",
        "bounce",
        "float",
        "patrol",
        "chase",
        "flee",
        "guard",
        "ranged_attack",
    ]
    entities = [
        EntityDef(
            id=f"matrix_ent_{i}",
            type="enemy" if beh != "float" else "collectible",
            x=100 + (i * 70),
            y=120 + ((i % 3) * 80),
            speed=100 + i * 10,
            health=25,
            damage=15,
            behavior=beh,  # type: ignore
            fire_rate=1.5,
            patrol_radius=140,
            detection_radius=260,
        )
        for i, beh in enumerate(behaviors)
    ]
    dsl = create_dsl_with_entities(entities)
    assert len(dsl.entities) == 8
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is True
    assert len(res.errors) == 0
