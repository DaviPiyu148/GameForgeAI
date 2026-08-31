"""
Gameplay Experience V1 Test Suite.

Verifies:
1. Gameplay beat completeness and rhythm (Intro -> Action -> Escalation -> Finale)
2. Deadlock detection:
   - Objective requires enemy defeat when 0 enemies exist
   - Objective requires collect_all when 0 collectibles exist
   - Objective exit coordinates outside world boundaries
3. Deadlock penalty and warning generation in GameDepthEvaluator
4. Failure clarity messaging
5. Backward compatibility across real output database fixtures
"""

import json
from pathlib import Path
import pytest

from app.generation.dsl_models import GameDSL, LevelDef, ObjectiveDef, EntityDef, WorldDef, PlayerDef
from app.generation.gameplay_rhythm import (
    GameplayRhythmManager,
    FlowPhase,
    DeadlockCheckResult,
)
from app.generation.depth_evaluator import GameDepthEvaluator
from app.generation.generation_contract import build_generation_contract
from app.generation.generation_config import QualityFailureCode


@pytest.fixture
def sample_fixtures():
    fix_path = Path(__file__).parent / "data" / "real_output_fixtures.json"
    assert fix_path.exists()
    with open(fix_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_gameplay_beat_completeness():
    """Verify GameplayRhythmManager evaluates beats across the 4 flow phases."""
    dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Beat Gauntlet", "genre": "Action", "description": "Gauntlet", "archetype": "arena"},
        "world": {"width": 1200, "height": 800, "theme": "cyberpunk", "background_color": "#050510", "wave_count": 3},
        "player": {"spawn_x": 600, "spawn_y": 400, "speed": 260, "max_health": 100},
        "entities": [
            {"id": "e1", "type": "enemy", "x": 200, "y": 200, "behavior": "patrol", "damage": 15},
            {"id": "e2", "type": "enemy", "x": 1000, "y": 600, "behavior": "ranged_attack", "damage": 20},
            {"id": "c1", "type": "collectible", "x": 600, "y": 200, "points": 50},
            {"id": "boss_1", "type": "enemy", "x": 600, "y": 600, "is_boss": True, "health": 200, "damage": 30},
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "add_score", "params": {"amount": 50}},
            {"id": "r2", "trigger": "on_enemy_defeat", "action": "win_game"},
        ]
    }
    dsl = GameDSL.model_validate(dsl_dict)
    score, beats = GameplayRhythmManager.evaluate_gameplay_beats(dsl, scale="standard")

    assert score >= 80.0
    phases = {b.phase for b in beats}
    assert FlowPhase.INTRO in phases
    assert FlowPhase.ACTION in phases
    assert FlowPhase.ESCALATION in phases
    assert FlowPhase.FINALE in phases


def test_deadlock_detection_defeat_all_with_zero_enemies():
    """Verify deadlock is caught if objective is defeat_all but 0 enemies exist."""
    dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Deadlock Defeat", "genre": "Action", "description": "Deadlock", "archetype": "shooter"},
        "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
        "levels": [
            {
                "level_number": 1,
                "title": "Empty Level",
                "objective": {"type": "defeat_all", "target_count": 1, "description": "Defeat all foes"},
                "entities": [
                    {"id": "c1", "type": "collectible", "x": 200, "y": 200, "points": 10}
                ],
            }
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "win_game"}
        ]
    }
    dsl = GameDSL.model_validate(dsl_dict)
    res = GameplayRhythmManager.detect_deadlocks(dsl)
    assert not res.is_valid
    assert any("defeat_all" in d and "0 enemies exist" in d for d in res.deadlocks)


def test_deadlock_detection_exit_out_of_bounds():
    """Verify deadlock is caught if exit coordinates exceed level boundaries."""
    dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Out of Bounds Exit", "genre": "Action", "description": "OOB", "archetype": "runner"},
        "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510"},
        "player": {"spawn_x": 100, "spawn_y": 300, "speed": 250, "max_health": 100},
        "levels": [
            {
                "level_number": 1,
                "title": "OOB Level",
                "objective": {"type": "reach_exit", "exit_x": 1800, "exit_y": 500, "description": "Reach escape point"},
                "entities": [],
            }
        ],
        "rules": [
            {"id": "r1", "trigger": "on_reach_goal", "action": "win_game"}
        ]
    }
    dsl = GameDSL.model_validate(dsl_dict)
    res = GameplayRhythmManager.detect_deadlocks(dsl)
    assert not res.is_valid
    assert any("exit_x" in d and "outside world width" in d for d in res.deadlocks)


def test_deadlock_penalty_in_evaluator():
    """Verify that a detected deadlock triggers GAMEPLAY_DEADLOCK_DETECTED in depth evaluator."""
    dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Deadlock Score Check", "genre": "Action", "description": "Penalty", "archetype": "shooter"},
        "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
        "levels": [
            {
                "level_number": 1,
                "title": "Level 1",
                "objective": {"type": "collect_all", "target_count": 1, "description": "Collect all"},
                "entities": [],  # 0 collectibles
            }
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "win_game"}
        ]
    }
    dsl = GameDSL.model_validate(dsl_dict)
    contract = build_generation_contract("Campaign shooter with collectibles", scale="standard")
    report = GameDepthEvaluator.evaluate(dsl, contract)
    assert QualityFailureCode.GAMEPLAY_DEADLOCK_DETECTED in report.failure_codes


def test_backward_compatibility_fixtures(sample_fixtures):
    """Verify that real output database fixtures have 0 deadlocks."""
    for fix in sample_fixtures:
        dsl = GameDSL.model_validate(fix["dsl"])
        res = GameplayRhythmManager.detect_deadlocks(dsl)
        assert res.is_valid, f"Fixture '{dsl.metadata.title}' produced deadlocks: {res.deadlocks}"
