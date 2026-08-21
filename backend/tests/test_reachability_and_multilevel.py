import pytest
from app.generation.dsl_models import GameDSL, LevelDef, ObjectiveDef, WorldDef, PlayerDef, EntityDef, RuleDef, GameMetadata
from app.generation.reachability import ReachabilityValidator


def test_reachability_validator_nudges_out_of_bounds_spawn():
    world = WorldDef(width=800, height=600)
    # Spawn is outside world (< 32)
    res = ReachabilityValidator.validate_and_repair_level(
        world=world,
        spawn_x=10,
        spawn_y=10,
        player_width=32,
        player_height=32,
        entities=[],
    )
    assert res.repaired is True
    assert res.repaired_spawn is not None
    assert res.repaired_spawn[0] >= 32
    assert res.repaired_spawn[1] >= 32


def test_reachability_validator_nudges_obstacle_overlap():
    world = WorldDef(width=800, height=600)
    # Obstacle overlapping spawn at 400, 300
    obstacle = EntityDef(
        id="wall_1",
        type="obstacle",
        x=380,
        y=280,
        width=100,
        height=100,
        behavior="stationary",
        color="#ffffff",
        points=0,
    )
    res = ReachabilityValidator.validate_and_repair_level(
        world=world,
        spawn_x=400,
        spawn_y=300,
        player_width=32,
        player_height=32,
        entities=[obstacle],
    )
    assert res.repaired is True
    assert res.repaired_spawn is not None
    # Player spawn should be nudged outside obstacle box
    assert not ReachabilityValidator.check_rect_collision(
        res.repaired_spawn[0], res.repaired_spawn[1], 32, 32,
        obstacle.x, obstacle.y, obstacle.width, obstacle.height
    )


def test_multi_level_dsl_schema_validation():
    level1 = LevelDef(
        level_number=1,
        title="Sector A: The Infiltration",
        objective=ObjectiveDef(type="collect_all", target_count=3, description="Collect 3 security chips"),
        entities=[
            EntityDef(
                id="chip_1",
                type="collectible",
                x=150,
                y=150,
                width=20,
                height=20,
                behavior="stationary",
                color="#00f0ff",
                points=50,
            )
        ],
    )
    level2 = LevelDef(
        level_number=2,
        title="Sector B: Core Reactor",
        objective=ObjectiveDef(type="defeat_all", target_count=2, description="Neutralize reactor guardians"),
        entities=[
            EntityDef(
                id="boss_1",
                type="enemy",
                x=500,
                y=300,
                width=40,
                height=40,
                behavior="patrol",
                color="#ff0055",
                points=200,
                health=100,
            )
        ],
    )

    dsl = GameDSL(
        schema_version="3.0",
        metadata=GameMetadata(
            title="Cyber Infiltration Campaign",
            genre="Action",
            description="A multi-stage tactical cyberpunk expedition",
            archetype="survival",
        ),
        levels=[level1, level2],
    )

    assert dsl.schema_version == "3.0"
    assert len(dsl.levels) == 2
    assert dsl.levels[0].title == "Sector A: The Infiltration"
    assert dsl.levels[1].objective.type == "defeat_all"
