"""
Automated Pytest Suite for Game Generation Pipeline V2.

Verifies:
1. Pre-generation Request Understanding & GameGenerationContract.
2. Rejection of unsupported runtime concepts (e.g. dynamic NPC memory).
3. Requirement coverage matrix & detection of incomplete usage.
4. Cross-system interaction validation (coexistence != interaction).
5. Deterministic depth evaluator across Prototype, Standard, and Campaign scales.
6. Deterministic 10-stage compiler pipeline execution.
7. Safe deterministic auto-repair (implied finale) vs strict schema rejection.
"""

import pytest
from typing import Any, Dict

from app.generation.dsl_models import GameDSL
from app.generation.generation_config import COMPILER_STAGES_V2, QualityFailureCode
from app.generation.generation_contract import (
    RequirementConfidence,
    build_generation_contract,
)
from app.generation.depth_evaluator import GameDepthEvaluator
from app.generation.dsl_normalizer import DSLNormalizer
from app.generation.requirement_coverage import RequirementCoverageMatrix
from app.generation.runtime_capabilities import check_for_unsupported_concepts


def test_request_understanding_contract():
    """Verify build_generation_contract extracts capabilities and distinguishes confidence."""
    prompt = "Create a fast cyberpunk courier game with vehicles, police threat escalation, and neon graphics"
    contract = build_generation_contract(
        prompt=prompt,
        engine="Top-Down Action",
        scale="campaign",
        world_mode="open_world",
    )

    assert "Cyberpunk" in contract.genre
    assert contract.scale == "campaign"
    assert contract.world_mode == "open_world"
    assert "VEHICLES" in contract.required_capabilities
    assert "THREAT_SYSTEM" in contract.required_capabilities

    explicit_names = [r.name for r in contract.explicit_requirements]
    assert "VEHICLES" in explicit_names
    assert "THREAT_SYSTEM" in explicit_names


def test_unsupported_concept_rejection():
    """
    Candidate asks for 'dynamic NPC memory' or 'multiplayer' where no such runtime exists.
    Expected: detected in unsupported_requests with explicit rejection.
    Do NOT silently strip 'memory' and claim generation succeeded.
    """
    prompt = "A fantasy RPG with dynamic NPC memory and persistent dialogue history across sessions"
    unsupported = check_for_unsupported_concepts(prompt)
    assert len(unsupported) > 0
    assert any("npc memory" in u[0].lower() or "memory" in u[0].lower() for u in unsupported)

    contract = build_generation_contract(prompt=prompt)
    assert len(contract.unsupported_requests) > 0

    dsl_fixture = {
        "schema_version": "3.0",
        "metadata": {"title": "Test RPG", "genre": "Fantasy RPG", "description": "Fantasy RPG with memory", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "fantasy", "background_color": "#000000"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 200, "max_health": 100},
        "entities": [{"id": "e1", "type": "enemy", "x": 100, "y": 100, "damage": 10}],
        "rules": [{"id": "r1", "trigger": "on_player_death", "action": "lose_game"}],
    }
    dsl = GameDSL.model_validate(dsl_fixture)
    report = GameDepthEvaluator.evaluate(dsl, contract)
    assert not report.is_acceptable
    assert QualityFailureCode.UNSUPPORTED_CAPABILITY in report.failure_codes


def test_cross_system_interaction_coexistence_is_not_interaction():
    """
    Explicit regression test:
    Prompt: 'Create a cyberpunk open-world courier game with vehicles, factions, hacking, threat escalation, and three districts.'
    Candidate DSL: vehicles present, factions present, threat present, but NO actual interaction between them.
    Expected: Requirement coverage detects incomplete interaction.
    """
    prompt = "Create a cyberpunk open-world courier game with vehicles, factions, hacking, threat escalation, and three districts."
    contract = build_generation_contract(prompt=prompt, world_mode="open_world", scale="campaign")

    # Candidate has disconnected systems (small world, slow vehicle, no activity links)
    disconnected_dsl_dict = {
        "schema_version": "3.0",
        "metadata": {"title": "Cyberpunk Courier Disconnected", "genre": "Cyberpunk Action", "description": "Disconnected open world", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "cyberpunk", "background_color": "#000000"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 400, "max_health": 100},
        "entities": [{"id": "e1", "type": "enemy", "x": 100, "y": 100, "damage": 10}],
        "rules": [{"id": "r1", "trigger": "on_player_death", "action": "lose_game"}],
        "open_world": {
            "regions": [
                {"id": "r1", "name": "District 1", "width": 800, "height": 600},
                {"id": "r2", "name": "District 2", "width": 800, "height": 600},
            ],
            "connections": [{"from_region": "r1", "to_region": "r2", "bidirectional": True, "traversal_types": ["vehicle", "on_foot"]}],
            "pois": [
                {"id": "p1", "region_id": "r1", "name": "POI 1", "type": "terminal", "x": 100, "y": 100},
                {"id": "p2", "region_id": "r2", "name": "POI 2", "type": "terminal", "x": 200, "y": 200},
                {"id": "p3", "region_id": "r1", "name": "POI 3", "type": "terminal", "x": 300, "y": 300},
            ],
            "factions": [
                {"id": "f1", "name": "Syndicate", "initial_reputation": 0},
            ],
            "vehicles": [
                # Vehicle is slower than player speed (400 vs 200 max_speed) -> No traversal advantage!
                {"id": "v1", "region_id": "r1", "name": "Slow Car", "type": "car", "x": 200, "y": 200, "max_speed": 200},
            ],
            "activities": [
                # Generic activity without faction reference or threat link
                {"id": "a1", "region_id": "r1", "title": "Stand Around", "type": "exploration", "description": "Look at sky"},
                {"id": "a2", "region_id": "r2", "title": "Walk Around", "type": "patrol", "description": "Look at ground"},
            ],
            "threat_system": {
                "name": "Threat", "current_level": 0, "max_level": 5, "decay_rate_per_sec": 0.1,
                "escalation_events": [],
                "response_units": [],
            },
        },
    }

    dsl = GameDSL.model_validate(disconnected_dsl_dict)
    statuses, interactions = RequirementCoverageMatrix.evaluate(contract, dsl)

    # Vehicles exist, but vehicle traversal interaction should NOT be verified because vehicle is slower than player
    veh_interaction = next((i for i in interactions if i.relationship_type == "VEHICLE_TO_TRAVERSAL"), None)
    assert veh_interaction is not None
    assert not veh_interaction.verified

    # Threat interaction should NOT be verified because no activities or rules trigger threat
    threat_interaction = next((i for i in interactions if i.relationship_type == "THREAT_TO_ACTIVITY"), None)
    assert threat_interaction is not None
    assert not threat_interaction.verified


def test_deterministic_compiler_stages_count():
    """Verify that the compiler stage sequence defines exactly 10 stages."""
    assert len(COMPILER_STAGES_V2) == 10
    stage_names = [s[1] for s in COMPILER_STAGES_V2]
    assert stage_names == [
        "Understanding game request",
        "Building game design",
        "Mapping runtime capabilities",
        "Generating GameDSL",
        "Schema validation",
        "Gameplay quality",
        "Deterministic normalization/repair",
        "Runtime compilation",
        "Runtime verification",
        "Build complete",
    ]


def test_scale_aware_quality_evaluator():
    """Verify quality score thresholds and scale expectations for Prototype vs Campaign."""
    prompt_proto = "A simple dodge prototype"
    contract_proto = build_generation_contract(prompt=prompt_proto, scale="prototype")

    proto_dsl_dict = {
        "schema_version": "3.0",
        "metadata": {"title": "Proto Dodge", "genre": "Action", "description": "Simple proto dodge", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "neon", "background_color": "#000000"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100, "dash_speed": 500, "stamina": 100},
        "entities": [
            {"id": "e1", "type": "enemy", "x": 100, "y": 100, "damage": 10, "behavior": "chase"},
            {"id": "c1", "type": "collectible", "x": 200, "y": 200, "points": 100},
        ],
        "rules": [
            {"id": "r1", "trigger": "on_collect", "action": "add_score", "params": {"amount": 100}},
            {"id": "r2", "trigger": "on_score_target", "action": "win_game", "params": {"target_score": 100}},
            {"id": "r3", "trigger": "on_player_death", "action": "lose_game"},
        ],
    }
    dsl_proto = GameDSL.model_validate(proto_dsl_dict)

    report_proto = GameDepthEvaluator.evaluate(dsl_proto, contract_proto)
    assert report_proto.is_acceptable
    assert report_proto.score >= 60

    # The same single-level prototype evaluated against a Campaign contract should flag insufficient levels
    contract_campaign = build_generation_contract(prompt="A deep campaign adventure", scale="campaign")
    report_campaign = GameDepthEvaluator.evaluate(dsl_proto, contract_campaign)
    assert not report_campaign.is_acceptable
    assert QualityFailureCode.INSUFFICIENT_LEVEL_DEPTH in report_campaign.failure_codes


def test_unambiguous_auto_repair_implied_finale():
    """Verify deterministic auto-repair derives implied finale on the final level of a multi-level campaign."""
    raw_candidate = {
        "schema_version": "3.0",
        "metadata": {"title": "Two Level Game", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "cyberpunk", "background_color": "#000000"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
        "levels": [
            {"level_number": 1, "is_finale": False, "entities": [], "rules": []},
            {"level_number": 2, "is_finale": False, "entities": [], "rules": []},
        ],
    }
    normalized, issues = DSLNormalizer.normalize(raw_candidate)
    assert normalized is not None
    assert normalized["levels"][1]["is_finale"] is True
    assert any("Derived unambiguous finale marker" in i.message for i in issues)


def test_security_rejection_of_script_injection():
    """Verify strict rejection of candidate containing executable or script payloads."""
    malicious_candidate = {
        "schema_version": "3.0",
        "metadata": {"title": "<script>alert(1)</script>", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "cyberpunk", "background_color": "#000000"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "max_health": 100},
        "entities": [],
        "rules": [],
    }
    normalized, issues = DSLNormalizer.normalize(malicious_candidate)
    assert normalized is None
    assert any(i.repairability == "UNSAFE" for i in issues)
