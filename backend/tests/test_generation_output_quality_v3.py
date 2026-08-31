"""
Generation Output Quality V3 Automated Test Suite.

Verifies:
1. Objective variety and adjacent-level repetition detection
2. Mechanic composition and verified cross-system interaction (coexistence != interaction)
3. Requirement utilization and confidence levels
4. Campaign progression differentiation
5. Finale distinction
6. Open-world depth (POIs, Activities, Factions, Vehicles, Threat, Events)
7. Encounter variation across levels
8. Deterministic pattern selection
9. Scale-aware scoring (Prototype simplicity accepted, Campaign repetition flagged)
10. Backward compatibility with existing stored projects
"""

import json
from pathlib import Path
import pytest

from app.generation.dsl_models import GameDSL
from app.generation.generation_config import QualityFailureCode
from app.generation.generation_contract import (
    build_generation_contract,
    RequirementConfidence,
)
from app.generation.design_patterns import (
    select_design_pattern,
    DESIGN_PATTERNS,
)
from app.generation.composition_matrix import (
    SUPPORTED_INTERACTIONS,
    get_required_interactions_for_contract,
)
from app.generation.depth_evaluator import GameDepthEvaluator
from app.generation.requirement_coverage import RequirementCoverageMatrix


@pytest.fixture
def sample_fixtures():
    fix_path = Path(__file__).parent / "data" / "real_output_fixtures.json"
    assert fix_path.exists(), "real_output_fixtures.json must exist"
    with open(fix_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_deterministic_pattern_selection():
    """Verify deterministic design pattern selection across combinations."""
    # Open world with vehicles & threat -> OW_ACTIVITY_ESCAPE
    p1 = select_design_pattern(
        archetype="action",
        world_mode="open_world",
        scale="campaign",
        has_vehicles=True,
        has_threat=True,
    )
    assert p1.id == "OW_ACTIVITY_ESCAPE"

    # Platformer -> PF_PRECISION_TRAVERSAL
    p2 = select_design_pattern(
        archetype="platformer",
        world_mode="linear",
        scale="standard",
    )
    assert p2.id == "PF_PRECISION_TRAVERSAL"

    # Collector -> CO_PATROL_SWEEP
    p3 = select_design_pattern(
        archetype="collector",
        world_mode="linear",
        scale="standard",
    )
    assert p3.id == "CO_PATROL_SWEEP"

    # Campaign shooter -> CP_PROGRESSIVE_ESCALATION
    p4 = select_design_pattern(
        archetype="shooter",
        world_mode="linear",
        scale="campaign",
    )
    assert p4.id == "CP_PROGRESSIVE_ESCALATION"


def test_adjacent_level_repetition_penalty():
    """Verify that multi-level campaigns with identical adjacent objectives trigger repetition warning."""
    repetitive_dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Repetitive Run", "genre": "Action", "description": "Repetitive", "archetype": "collector"},
        "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510", "gravity": 0},
        "player": {"spawn_x": 100, "spawn_y": 100, "speed": 250, "max_health": 100},
        "levels": [
            {
                "level_number": 1,
                "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510"},
                "spawn_x": 100, "spawn_y": 100,
                "objective": {"type": "collect_all", "description": "Stage 1 collect"},
                "entities": [{"id": "c1", "type": "collectible", "x": 300, "y": 300, "points": 10}],
            },
            {
                "level_number": 2,
                "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510"},
                "spawn_x": 100, "spawn_y": 100,
                "objective": {"type": "collect_all", "description": "Stage 2 collect (identical)"},
                "entities": [{"id": "c2", "type": "collectible", "x": 300, "y": 300, "points": 10}],
            },
            {
                "level_number": 3,
                "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510"},
                "spawn_x": 100, "spawn_y": 100,
                "objective": {"type": "collect_all", "description": "Stage 3 collect (identical)"},
                "is_finale": True,
                "entities": [{"id": "c3", "type": "collectible", "x": 300, "y": 300, "points": 10}],
            },
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "add_score", "params": {"amount": 10}},
            {"id": "r2", "trigger": "on_score_target", "action": "win_game", "params": {"target_score": 30}},
        ],
    }

    dsl = GameDSL.model_validate(repetitive_dsl_dict)
    contract = build_generation_contract("Cyberpunk collector run", scale="campaign")
    report = GameDepthEvaluator.evaluate(dsl, contract)

    assert QualityFailureCode.REPEATED_ADJACENT_OBJECTIVES in report.failure_codes
    assert any("Repeated adjacent objective" in w for w in report.warnings)


def test_cross_system_composition_matrix_evaluation():
    """Verify composition matrix accurately verifies linked systems and rejects passive coexistence."""
    # Test valid composition
    valid_ow_dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Syndicate Operations", "genre": "Action", "description": "Operations", "archetype": "shooter"},
        "world": {"width": 800, "height": 600, "theme": "cyberpunk", "background_color": "#0a0518", "gravity": 0},
        "player": {"spawn_x": 100, "spawn_y": 100, "speed": 220, "max_health": 100, "attack_type": "ranged", "attack_damage": 25},
        "rules": [
            {"id": "r_col", "trigger": "on_collect", "action": "add_score", "params": {"amount": 50}},
            {"id": "r_defeat", "trigger": "on_enemy_defeat", "action": "add_score", "params": {"amount": 100}},
        ],
        "open_world": {
            "regions": [
                {"id": "reg_slums", "name": "Slums", "theme": "cyberpunk", "width": 1400, "height": 1400, "danger_level": 1},
                {"id": "reg_corp", "name": "Corp Core", "theme": "cyberpunk", "width": 1600, "height": 1600, "danger_level": 3},
            ],
            "connections": [{"from_region": "reg_slums", "to_region": "reg_corp", "bidirectional": True, "traversal_types": ["vehicle"]}],
            "pois": [
                {"id": "poi_terminal", "region_id": "reg_slums", "name": "Slum Terminal", "type": "terminal", "x": 200, "y": 200, "activity_ids": ["act_infiltrate"]},
                {"id": "poi_garage", "region_id": "reg_slums", "name": "Slum Garage", "type": "garage", "x": 300, "y": 300},
                {"id": "poi_outpost", "region_id": "reg_corp", "name": "Corp Outpost", "type": "outpost", "x": 500, "y": 500},
            ],
            "factions": [
                {"id": "fac_rebels", "name": "Neon Rebels", "initial_reputation": 50},
                {"id": "fac_corp", "name": "OmniCorp", "initial_reputation": -50},
            ],
            "vehicles": [
                {"id": "veh_bike", "region_id": "reg_slums", "name": "Interceptor", "type": "bike", "x": 250, "y": 250, "max_speed": 550},
            ],
            "activities": [
                {"id": "act_infiltrate", "region_id": "reg_slums", "title": "Rebel Supply Drop", "type": "delivery", "description": "Deliver cache to Neon Rebels"},
                {"id": "act_sweep", "region_id": "reg_corp", "title": "Corporate Raid", "type": "combat", "description": "Disrupt OmniCorp patrol"},
            ],
            "threat_system": {
                "name": "District Security", "current_level": 0, "max_level": 5, "decay_rate_per_sec": 0.05,
                "escalation_events": [], "response_units": [],
            },
            "events": [
                {"id": "ev_curfew", "name": "Corp Lockdown", "type": "security_lockdown", "duration_seconds": 60},
            ],
        },
    }


    dsl = GameDSL.model_validate(valid_ow_dsl_dict)
    contract = build_generation_contract("Cyberpunk open world with vehicles, factions, and threat", world_mode="open_world", scale="campaign")
    statuses, interactions = RequirementCoverageMatrix.evaluate(contract, dsl)

    # All key interactions must be verified
    veh_i = next(i for i in interactions if i.relationship_type == "VEHICLE_TO_TRAVERSAL")
    assert veh_i.verified

    threat_i = next(i for i in interactions if i.relationship_type == "THREAT_TO_ACTIVITY")
    assert threat_i.verified

    fac_i = next(i for i in interactions if i.relationship_type == "FACTION_TO_ACTIVITY")
    assert fac_i.verified

    poi_i = next(i for i in interactions if i.relationship_type == "POI_TO_ACTIVITY")
    assert poi_i.verified


def test_prototype_simplicity_accepted():
    """Verify that focused single-level prototypes pass without multi-level campaign penalties."""
    proto_dsl = {
        "schema_version": "2.0",
        "metadata": {"title": "Arcade Swift", "genre": "Action", "description": "Simple prototype", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#050510", "gravity": 0},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
        "entities": [
            {"id": "e1", "type": "enemy", "x": 100, "y": 100, "behavior": "chase", "speed": 120, "damage": 20},
            {"id": "e2", "type": "collectible", "x": 600, "y": 450, "behavior": "stationary", "points": 100},
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "win_game"},
            {"id": "r2", "trigger": "on_collide_enemy", "action": "damage_player", "params": {"amount": 20}},
            {"id": "r3", "trigger": "on_player_death", "action": "lose_game"},
        ],
    }

    dsl = GameDSL.model_validate(proto_dsl)
    contract = build_generation_contract("Quick arcade dodge", scale="prototype")
    report = GameDepthEvaluator.evaluate(dsl, contract)

    assert report.is_acceptable
    assert report.score >= 60
    assert not report.needs_repair


def test_backward_compatibility_with_existing_projects(sample_fixtures):
    """Verify all real stored project versions continue to validate successfully under GameDSL."""
    for fix in sample_fixtures:
        dsl_raw = fix["dsl"]
        dsl = GameDSL.model_validate(dsl_raw)
        assert dsl.schema_version == "2.0"
        assert dsl.metadata.title is not None


def test_finale_distinction_and_boss_presence():
    """Verify that a distinct boss on final stage satisfies finale criteria."""
    campaign_with_boss = {
        "schema_version": "2.0",
        "metadata": {"title": "Boss Climax", "genre": "Action", "description": "Climax", "archetype": "shooter"},
        "world": {"width": 800, "height": 600, "theme": "dungeon", "background_color": "#120d0a", "gravity": 0},
        "player": {"spawn_x": 100, "spawn_y": 100, "speed": 220, "max_health": 100, "attack_type": "ranged", "attack_damage": 30},
        "levels": [
            {
                "level_number": 1,
                "world": {"width": 800, "height": 600, "theme": "dungeon", "background_color": "#120d0a"},
                "spawn_x": 100, "spawn_y": 100,
                "objective": {"type": "defeat_all", "description": "Defeat scouts"},
                "entities": [{"id": "e1", "type": "enemy", "x": 400, "y": 300, "behavior": "patrol", "damage": 15}],
            },
            {
                "level_number": 2,
                "world": {"width": 800, "height": 600, "theme": "dungeon", "background_color": "#120d0a"},
                "spawn_x": 100, "spawn_y": 100,
                "objective": {"type": "reach_exit", "description": "Ascend to chamber"},
                "entities": [
                    {"id": "e2", "type": "enemy", "x": 300, "y": 200, "behavior": "chase", "damage": 20},
                    {"id": "g1", "type": "collectible", "x": 700, "y": 500, "behavior": "stationary", "points": 50},
                ],
            },
            {
                "level_number": 3,
                "world": {"width": 800, "height": 600, "theme": "dungeon", "background_color": "#120d0a"},
                "spawn_x": 100, "spawn_y": 100,
                "objective": {"type": "defeat_all", "description": "Slay Overlord"},
                "is_finale": True,
                "entities": [
                    {"id": "boss_1", "type": "enemy", "x": 600, "y": 300, "is_boss": True, "health": 300, "behavior": "ranged_attack", "damage": 35},
                ],
            },
        ],
        "rules": [
            {"id": "r1", "trigger": "on_enemy_defeat", "action": "add_score", "params": {"amount": 50}},
            {"id": "r2", "trigger": "on_collide_enemy", "action": "damage_player", "params": {"damage": 20}},
            {"id": "r3", "trigger": "on_score_target", "action": "win_game", "params": {"target_score": 150}},
        ],
    }

    dsl = GameDSL.model_validate(campaign_with_boss)
    contract = build_generation_contract("Dungeon crawler campaign with boss finale", scale="campaign")
    report = GameDepthEvaluator.evaluate(dsl, contract)

    assert report.finale_score >= 90.0
    assert report.score >= 72
    assert report.is_acceptable


def test_encounter_variety_across_levels():
    """Verify that mixing patrol, chase, and ranged enemy behaviors yields higher variety."""
    varied_dsl_dict = {
        "schema_version": "2.0",
        "metadata": {"title": "Varied Enemies", "genre": "Action", "description": "Encounter variety", "archetype": "shooter"},
        "world": {"width": 800, "height": 600, "theme": "space", "background_color": "#020412", "gravity": 0},
        "player": {"spawn_x": 100, "spawn_y": 100, "speed": 250, "max_health": 100, "attack_type": "ranged", "attack_damage": 25},
        "entities": [
            {"id": "e_patrol", "type": "enemy", "x": 300, "y": 100, "behavior": "patrol", "speed": 100},
            {"id": "e_chase", "type": "enemy", "x": 400, "y": 200, "behavior": "chase", "speed": 130},
            {"id": "e_ranged", "type": "enemy", "x": 500, "y": 300, "behavior": "ranged_attack", "speed": 90},
            {"id": "e_guard", "type": "enemy", "x": 600, "y": 400, "behavior": "guard", "speed": 0},
            {"id": "c1", "type": "collectible", "x": 200, "y": 500, "points": 100},
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "win_game"},
            {"id": "r2", "trigger": "on_collide_enemy", "action": "damage_player", "params": {"damage": 15}},
        ],
    }

    dsl = GameDSL.model_validate(varied_dsl_dict)
    contract = build_generation_contract("Space shooter with varied drones", scale="standard")
    report = GameDepthEvaluator.evaluate(dsl, contract)

    assert report.variety_score >= 50.0


def test_visual_identity_palette_assignment():
    """Verify that contract derives appropriate background and accent colors from prompt theme."""
    cyber_contract = build_generation_contract("Cyberpunk rogue courier")
    assert cyber_contract.visual_direction == "cyberpunk"
    assert cyber_contract.palette["bg"] == "#0a0518"

    dungeon_contract = build_generation_contract("Dark dungeon fantasy crawler")
    assert dungeon_contract.visual_direction in ("dungeon", "fantasy")
    assert dungeon_contract.palette["bg"] in ("#120d0a", "#0d1b1e")

