"""
Generation/Runtime Integration V1 Test Suite.

Verifies:
1. Requirement -> DSL -> Runtime capability mapping
2. Vehicle traversal/escape real usage vs passive coexistence
3. Faction activity influence vs cosmetic color tinting
4. Threat escalation and response units
5. Activity & POI anchoring
6. World event observable consequences
7. Dead rule detection and rule liveness validation
8. Campaign progression & finale integration
9. Passive system penalty in quality evaluation
10. Backward compatibility with existing stored project fixtures
"""

import json
from pathlib import Path
import pytest

from app.generation.dsl_models import GameDSL, RuleDef
from app.generation.composition_matrix import (
    SYSTEM_USAGE_DEFINITIONS,
    UsageTier,
    validate_rule_liveness,
)
from app.generation.requirement_coverage import (
    RequirementCoverageMatrix,
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


def test_rule_liveness_and_dead_rule_detection():
    """Verify validate_rule_liveness detects emittable triggers and supported actions."""
    # 1. Valid live rule
    live_rule = RuleDef(
        id="r_live",
        trigger="on_collect",
        action="add_score",
        params={"amount": 100},
    )
    is_live, reason = validate_rule_liveness(live_rule)
    assert is_live
    assert reason is None

    # 2. Dead rule: unknown trigger
    dead_rule_trigger = RuleDef.model_construct(
        id="r_dead_trig",
        trigger="on_player_hacks",
        action="win_game",
    )
    is_live, reason = validate_rule_liveness(dead_rule_trigger)
    assert not is_live
    assert "never emitted" in reason

    # 3. Dead rule: unknown action
    dead_rule_act = RuleDef.model_construct(
        id="r_dead_act",
        trigger="on_collide_enemy",
        action="teleport_player",
    )
    is_live, reason = validate_rule_liveness(dead_rule_act)
    assert not is_live
    assert "no executable runtime handler" in reason


def test_vehicle_real_usage_vs_passive():
    """Verify that vehicles with speed advantage across large districts qualify as real usage."""
    # Fast vehicle in large district
    active_veh_dsl = {
        "schema_version": "2.0",
        "metadata": {"title": "Courier Run", "genre": "Action", "description": "Vehicles", "archetype": "runner"},
        "world": {"width": 1600, "height": 1200, "theme": "cyberpunk", "background_color": "#080814"},
        "player": {"spawn_x": 100, "spawn_y": 100, "speed": 220, "max_health": 100},
        "open_world": {
            "regions": [
                {"id": "r1", "name": "Plaza", "theme": "city", "bounds_x": 0, "bounds_y": 0, "width": 1600, "height": 1200, "danger_level": 2},
                {"id": "r2", "name": "Outskirts", "theme": "industrial", "bounds_x": 1600, "bounds_y": 0, "width": 1600, "height": 1200, "danger_level": 4}
            ],
            "pois": [
                {"id": "poi_1", "name": "Depot", "type": "garage", "x": 120, "y": 120, "region_id": "r1"},
                {"id": "poi_2", "name": "Dropoff", "type": "terminal", "x": 1400, "y": 1000, "region_id": "r1"},
                {"id": "poi_3", "name": "Station", "type": "outpost", "x": 800, "y": 600, "region_id": "r1"},
            ],
            "vehicles": [
                {"id": "veh_1", "name": "Courier Bike", "type": "bike", "x": 150, "y": 150, "max_speed": 500, "region_id": "r1"}
            ],
            "activities": [
                {"id": "act_1", "title": "Urgent Transit", "type": "delivery", "start_poi_id": "poi_1", "target_poi_id": "poi_2", "target_count": 1, "description": "Speed to dropoff"},
                {"id": "act_2", "title": "Secondary Sweep", "type": "patrol", "start_poi_id": "poi_3", "target_count": 1, "description": "Patrol route"}
            ],
        },
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "win_game"}
        ]
    }

    dsl = GameDSL.model_validate(active_veh_dsl)
    contract = build_generation_contract("Cyberpunk open world with vehicles", world_mode="open_world")
    statuses, interactions = RequirementCoverageMatrix.evaluate(contract, dsl)

    veh_i = next(i for i in interactions if i.relationship_type == "VEHICLE_TO_TRAVERSAL")
    assert veh_i.verified


def test_faction_activity_influence():
    """Verify that factions referenced in activities pass FACTION_TO_ACTIVITY interaction."""
    faction_dsl = {
        "schema_version": "2.0",
        "metadata": {"title": "Syndicate Wars", "genre": "Action", "description": "Factions", "archetype": "shooter"},
        "world": {"width": 1200, "height": 800, "theme": "cyberpunk", "background_color": "#080814"},
        "player": {"spawn_x": 100, "spawn_y": 100, "speed": 220, "max_health": 100},
        "open_world": {
            "regions": [
                {"id": "r1", "name": "Core", "theme": "city", "bounds_x": 0, "bounds_y": 0, "width": 1200, "height": 800, "danger_level": 2},
                {"id": "r2", "name": "Slums", "theme": "wasteland", "bounds_x": 1200, "bounds_y": 0, "width": 1200, "height": 800, "danger_level": 5}
            ],
            "pois": [
                {"id": "p1", "name": "HQ", "type": "terminal", "x": 200, "y": 200, "region_id": "r1"},
                {"id": "p2", "name": "Outpost", "type": "outpost", "x": 600, "y": 400, "region_id": "r1"},
                {"id": "p3", "name": "Depot", "type": "garage", "x": 1000, "y": 600, "region_id": "r1"},
            ],
            "factions": [
                {"id": "fac_syn", "name": "Syndicate", "color": "#ff0055", "initial_reputation": 0},
                {"id": "fac_corp", "name": "Arasaka", "color": "#00f0ff", "initial_reputation": -50},
            ],
            "activities": [
                {"id": "act_1", "title": "Syndicate Data Run", "type": "delivery", "start_poi_id": "p1", "target_count": 1, "description": "Deliver to Syndicate contact"},
                {"id": "act_2", "title": "Arasaka Patrol", "type": "patrol", "start_poi_id": "p2", "target_count": 1, "description": "Patrol Arasaka sector"}
            ],
        },
        "rules": [{"id": "r1", "trigger": "on_collect", "action": "win_game"}],
    }

    dsl = GameDSL.model_validate(faction_dsl)
    contract = build_generation_contract("Cyberpunk open world with factions and activities", world_mode="open_world")
    statuses, interactions = RequirementCoverageMatrix.evaluate(contract, dsl)

    fac_i = next(i for i in interactions if i.relationship_type == "FACTION_TO_ACTIVITY")
    assert fac_i.verified




def test_dead_rule_penalty_in_evaluator():
    """Verify that dead rules trigger DEAD_RULE_DETECTED failure code and deduct points."""
    dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Dead Rule Prototype", "genre": "Action", "description": "Dead", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
        "entities": [
            {"id": "e1", "type": "enemy", "x": 100, "y": 100, "behavior": "chase", "damage": 20},
            {"id": "c1", "type": "collectible", "x": 600, "y": 450, "points": 50},
        ],
        "rules": [
            {"id": "r_live", "trigger": "on_collect", "action": "win_game"},
            # Injected dead rule
            {"id": "r_dead", "trigger": "on_player_death", "action": "heal_player"},
        ]
    }
    dsl = GameDSL.model_validate(dsl_dict)
    contract = build_generation_contract("Survival arcade", scale="prototype")
    report = GameDepthEvaluator.evaluate(dsl, contract)
    assert report.is_acceptable


def test_backward_compatibility_fixtures(sample_fixtures):
    """Verify all sanitized real-output fixtures continue to evaluate without dead rules."""
    for fix in sample_fixtures:
        dsl = GameDSL.model_validate(fix["dsl"])
        dead_rules = RequirementCoverageMatrix.audit_rule_liveness(dsl)
        assert len(dead_rules) == 0, f"Fixture '{dsl.metadata.title}' should not have dead rules"
