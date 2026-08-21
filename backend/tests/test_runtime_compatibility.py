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
    SUPPORTED_ARCHETYPES,
)
from app.runtime.metadata import (
    DSL_SCHEMA_VERSION,
    PHASER_VERSION,
    RENDERER_VERSION,
    generate_runtime_metadata,
    generate_seed_from_input,
)


def create_sample_dsl(archetype: str = "survival") -> GameDSL:
    return GameDSL(
        schema_version="1.0",
        metadata=GameMetadata(
            title="Test Prototype",
            genre="Action",
            description="Testing runtime compatibility.",
            archetype=archetype,  # type: ignore
        ),
        world=WorldDef(
            width=800,
            height=600,
            gravity=0 if archetype != "platformer" else 600,
            background_color="#0a0b10",
            theme="cyberpunk",
        ),
        player=PlayerDef(
            spawn_x=400,
            spawn_y=300,
            speed=200,
            jump_power=400 if archetype == "platformer" else 0,
            max_health=100,
            width=32,
            height=32,
            color="#00f0ff",
        ),
        entities=[
            EntityDef(
                id="enemy_1",
                type="enemy",
                x=100,
                y=100,
                width=24,
                height=24,
                speed=120,
                health=20,
                behavior="chase" if archetype == "survival" else "patrol",
                color="#ff0055",
                points=10,
            ),
            EntityDef(
                id="coin_1",
                type="collectible",
                x=500,
                y=300,
                width=20,
                height=20,
                speed=0,
                health=1,
                behavior="stationary",
                color="#ffe600",
                points=25,
            ),
        ],
        rules=[
            RuleDef(
                id="rule_collect",
                trigger="on_collect",
                action="add_score",
                params={"amount": 25},
            ),
            RuleDef(
                id="rule_damage",
                trigger="on_collide_enemy",
                action="damage_player",
                params={"amount": 15},
            ),
        ],
        ui=UIDef(
            show_health=True,
            show_score=True,
            status_text="SURVIVE THE SWARM",
        ),
    )


def test_core_archetypes_are_compatible():
    """Verify that all core supported archetypes pass compatibility validation."""
    for arch in ["survival", "shooter", "platformer", "collector"]:
        dsl = create_sample_dsl(archetype=arch)
        res = RuntimeCompatibilityValidator.validate(dsl)
        assert res.compatible is True
        assert res.archetype == arch
        assert len(res.errors) == 0


def test_invalid_entity_type_is_rejected():
    """Verify that unsupported entity types fail compatibility validation."""
    dsl = create_sample_dsl(archetype="survival")
    # Manually bypass pydantic validation for testing validator boundary
    dsl.entities[0].type = "unsupported_boss"  # type: ignore
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is False
    assert any("unsupported type" in e for e in res.errors)


def test_invalid_trigger_or_action_is_rejected():
    """Verify that unsupported triggers or actions are rejected."""
    dsl = create_sample_dsl(archetype="survival")
    dsl.rules[0].trigger = "on_laser_strike"  # type: ignore
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is False
    assert any("unsupported trigger" in e for e in res.errors)


def test_excessive_entity_count_is_rejected():
    """Verify entity limits (<= 30 entities)."""
    dsl = create_sample_dsl(archetype="survival")
    # Construct 35 entities
    dsl.entities = [
        EntityDef(
            id=f"e_{i}",
            type="enemy",
            x=100 + (i * 10) % 600,
            y=100 + (i * 10) % 400,
            width=20,
            height=20,
            speed=50,
            health=10,
            behavior="stationary",
            color="#ff0000",
            points=5,
        )
        for i in range(35)
    ]
    res = RuntimeCompatibilityValidator.validate(dsl)
    assert res.compatible is False
    assert any("Entity count" in e for e in res.errors)


def test_runtime_metadata_generation():
    """Verify deterministic metadata provider."""
    meta = generate_runtime_metadata(seed_source="test_build_uuid_123")
    assert meta["rendererVersion"] == RENDERER_VERSION
    assert meta["phaserVersion"] == PHASER_VERSION
    assert meta["dslSchemaVersion"] == DSL_SCHEMA_VERSION
    assert isinstance(meta["seed"], int)

    # Determinism check
    meta2 = generate_runtime_metadata(seed_source="test_build_uuid_123")
    assert meta["seed"] == meta2["seed"]

    # Different seed for different source
    meta3 = generate_runtime_metadata(seed_source="different_build_uuid")
    assert meta["seed"] != meta3["seed"]
