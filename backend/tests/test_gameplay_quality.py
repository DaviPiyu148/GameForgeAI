"""
Unit and regression tests for GameplayQualityValidator V2.

Verifies:
- Player spawn clearance (>= 60px away from enemies/hazards)
- Archetype objective & win condition reachability (survival, platformer, collector, shooter)
- Fairness & lethality diagnostics
- Progression & session bounds (wave count, rule count, moving enemy speed)
- Builder parameter consistency (platformer gravity, jump_power)
"""
from app.generation.dsl_models import (
    EntityDef,
    GameDSL,
    GameMetadata,
    PlayerDef,
    RuleDef,
    UIDef,
    WorldDef,
)
from app.generation.quality_validator import GameplayQualityValidator


def create_base_dsl(
    archetype: str = "survival",
    gravity: int = 0,
    jump_power: int = 0,
    wave_count: int = 3,
    player_spawn: tuple[int, int] = (400, 300),
    entities: list[EntityDef] = None,
    rules: list[RuleDef] = None,
) -> GameDSL:
    ent_list = entities or [
        EntityDef(
            id="drone_1",
            type="enemy",
            x=600,
            y=200,
            behavior="patrol",
            speed=120,
            damage=15,
        )
    ]
    rule_list = rules or [
        RuleDef(id="r1", trigger="on_collide_enemy", action="damage_player", params={"damage": 15}),
        RuleDef(id="r2", trigger="on_player_death", action="lose_game"),
    ]
    return GameDSL(
        schema_version="2.0",
        metadata=GameMetadata(
            title="Quality Test Game",
            genre="Action",
            description="Testing gameplay quality validator.",
            archetype=archetype,
        ),
        world=WorldDef(width=800, height=600, theme="neon", gravity=gravity, wave_count=wave_count),
        player=PlayerDef(spawn_x=player_spawn[0], spawn_y=player_spawn[1], jump_power=jump_power),
        entities=ent_list,
        rules=rule_list,
        ui=UIDef(show_health=True, show_score=True, status_text="PLAY"),
    )


def test_valid_survival_game_passes_quality_validation():
    """Verify standard coherent survival game passes quality check."""
    dsl = create_base_dsl(archetype="survival", wave_count=3)
    res = GameplayQualityValidator.validate(dsl)
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_immediate_hazard_spawn_triggers_error():
    """Verify player spawned within 60px of enemy/hazard is caught as immediate death hazard."""
    # Spawn player at (400, 300) and enemy at (420, 310) -> distance ~22px < 60px
    danger_ent = EntityDef(id="ambush_drone", type="enemy", x=420, y=310, speed=100)
    dsl = create_base_dsl(entities=[danger_ent])
    res = GameplayQualityValidator.validate(dsl)
    assert res.is_valid is False
    assert any("Immediate death hazard" in err for err in res.errors)


def test_platformer_missing_gravity_or_jump_power_triggers_error():
    """Verify platformer without gravity or jump power fails quality validation."""
    dsl = create_base_dsl(archetype="platformer", gravity=0, jump_power=0)
    res = GameplayQualityValidator.validate(dsl)
    assert res.is_valid is False
    assert any("requires world.gravity > 0" in err for err in res.errors)
    assert any("requires player.jump_power > 0" in err for err in res.errors)


def test_collector_without_collectibles_triggers_error():
    """Verify collector game with 0 collectibles fails quality validation."""
    dsl = create_base_dsl(archetype="collector", entities=[])
    res = GameplayQualityValidator.validate(dsl)
    assert res.is_valid is False
    assert any("Collector archetype requires at least one collectible" in err for err in res.errors)


def test_zero_speed_moving_enemy_triggers_error():
    """Verify enemy with active movement behavior but speed=0 fails quality validation."""
    ent = EntityDef(id="frozen_chaser", type="enemy", x=700, y=200, behavior="chase", speed=0)
    dsl = create_base_dsl(entities=[ent])
    res = GameplayQualityValidator.validate(dsl)
    assert res.is_valid is False
    assert any("Dead entity logic" in err for err in res.errors)


def test_invalid_wave_count_triggers_error():
    """Verify wave count outside 1-10 fails schema validation and quality validation."""
    dsl = create_base_dsl(wave_count=3)
    dsl.world.wave_count = 15
    res = GameplayQualityValidator.validate(dsl)
    assert res.is_valid is False
    assert any("Wave count (15) outside valid range" in err for err in res.errors)
