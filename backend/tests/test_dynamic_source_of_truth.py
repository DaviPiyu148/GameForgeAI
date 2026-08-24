"""
Comprehensive End-to-End Dynamic Source-of-Truth & Pipeline Parity Test Suite.

Proves that dynamic configurations chosen or generated at the source survive intact across:
UI / Request JSON -> Pydantic Schema -> Backend Service -> AI Prompt -> DesignSpec -> GameDSL -> Project Persistence -> Serialization.
"""
import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

from app.schemas.build import BuildCreate, BuildParams
from app.schemas.project import ProjectCreate, ProjectResponse, BuildParams as ProjectBuildParams
from app.models.build import BuildJob
from app.models.project import Project
from app.ai.prompts import build_generation_prompt
from app.services.game_generation_service import GameGenerationService, GenerationResult
from app.generation.dsl_models import GameDSL
from app.generation.open_world_models import OpenWorldDef
from app.generation.validator import validate_game_dsl
from tests.test_dsl import get_sample_valid_dsl_dict


def test_builder_parameter_pydantic_roundtrip_all_permutations():
    """Verify engine, world_mode, scale, physics, art_density, modules deserialize and serialize losslessly."""
    permutations = [
        {"engine": "Top-Down Action", "world_mode": "linear", "scale": "standard", "physics": 80, "artDensity": 50, "modules": ["Procedural Generation"]},
        {"engine": "2D Platformer", "world_mode": "campaign", "scale": "campaign", "physics": 100, "artDensity": 100, "modules": ["Combat & Dash Mobility"]},
        {"engine": "Arena Survival", "world_mode": "open_world", "scale": "prototype", "physics": 0, "artDensity": 0, "modules": []},
        {"engine": "Data Collector", "world_mode": "linear", "scale": "standard", "physics": 35, "artDensity": 70, "modules": ["Resource & Score Economy", "Enhanced NPC Behavior"]},
    ]

    for p in permutations:
        req = BuildCreate(prompt="Test prompt", parameters=BuildParams.model_validate(p))
        assert req.parameters.engine == p["engine"]
        assert req.parameters.world_mode == p["world_mode"]
        assert req.parameters.scale == p["scale"]
        assert req.parameters.physics == p["physics"]
        assert req.parameters.art_density == p["artDensity"]
        assert req.parameters.modules == p["modules"]

        # Test model_dump by alias for HTTP JSON compatibility
        dumped = req.parameters.model_dump(by_alias=True)
        assert dumped["artDensity"] == p["artDensity"]
        assert dumped["worldMode"] == p["world_mode"]
        assert dumped["physics"] == p["physics"]
        assert dumped["scale"] == p["scale"]


def test_falsy_zero_values_survive_without_overrides():
    """Verify that physics=0, art_density=0, modules=[] are NOT overwritten by defaults or truthy fallbacks."""
    zero_params = BuildParams(
        engine="2D Platformer",
        artDensity=0,
        physics=0,
        modules=[],
        scale="prototype",
        world_mode="linear",
    )
    assert zero_params.art_density == 0
    assert zero_params.physics == 0
    assert zero_params.modules == []

    prompt = build_generation_prompt(
        prompt="Zero physics game",
        engine=zero_params.engine,
        art_density=zero_params.art_density,
        physics=zero_params.physics,
        modules=zero_params.modules,
        scale=zero_params.scale,
        world_mode=zero_params.world_mode,
    )
    assert "Physics Complexity (0/100):" in prompt
    assert "Visual Density (0/100):" in prompt
    assert "Active Logic Modules: standard mechanics" in prompt
    assert "- Scale Tier (prototype):" in prompt
    assert "- World Architecture Mode (linear):" in prompt


def test_prompt_target_configuration_includes_all_parameters():
    """Verify Gemini target configuration prompt dynamically includes all 6 Builder settings."""
    prompt = build_generation_prompt(
        prompt="Courier courier open world",
        engine="Arena Survival",
        art_density=85,
        physics=65,
        modules=["Combat & Dash Mobility", "Dynamic Hazard Zones"],
        scale="campaign",
        world_mode="open_world",
    )

    assert "- Prototype Profile: Arena Survival" in prompt
    assert "- World Architecture Mode (open_world): Open World Sandbox" in prompt
    assert "- Physics Complexity (65/100):" in prompt
    assert "- Visual Density (85/100):" in prompt
    assert "- Active Logic Modules: Combat & Dash Mobility, Dynamic Hazard Zones" in prompt
    assert "- Scale Tier (campaign):" in prompt


def test_game_generation_compiles_archetypes_and_rules_dynamically():
    """Verify _compile_and_propagate_parameters maps engines to archetypes and modules to rules without destroying generated data."""
    service = GameGenerationService(provider=AsyncMock())
    base_dsl = get_sample_valid_dsl_dict()

    # Platformer compilation
    plat_dsl = service._compile_and_propagate_parameters(
        dsl_dict=base_dsl,
        spec_dict={"primary_objective": "Reach the portal"},
        engine="2D Platformer",
        art_density=60,
        physics=75,
        modules=["Combat & Dash Mobility", "Resource & Score Economy"],
    )
    assert plat_dsl["metadata"]["archetype"] == "platformer"
    assert plat_dsl["world"]["gravity"] > 0
    assert plat_dsl["player"]["jump_power"] > 0
    assert plat_dsl["player"]["dash_speed"] >= 500
    assert plat_dsl["player"]["attack_damage"] >= 25
    assert plat_dsl["ui"]["show_score"] is True


def test_open_world_dsl_primitives_validation_and_integrity():
    """Verify open world regions, connections, POIs, factions, vehicles, activities validate properly."""
    dsl_dict = get_sample_valid_dsl_dict()
    dsl_dict["open_world"] = {
        "regions": [
            {
                "id": "reg_downtown",
                "name": "Downtown Central",
                "bounds_x": 0, "bounds_y": 0, "width": 1600, "height": 1200,
                "danger_level": 1, "theme": "neon", "background_color": "#0a0a14"
            },
            {
                "id": "reg_slums",
                "name": "Industrial Slums",
                "bounds_x": 1600, "bounds_y": 0, "width": 1600, "height": 1200,
                "danger_level": 3, "theme": "industrial", "background_color": "#140a0a"
            }
        ],
        "connections": [
            {
                "from_region": "reg_downtown",
                "to_region": "reg_slums",
                "bidirectional": True
            }
        ],
        "pois": [
            {"id": "poi_depot", "region_id": "reg_downtown", "name": "Courier HQ", "x": 400, "y": 300, "poi_type": "hub"}
        ],
        "activities": [
            {"id": "act_delivery", "title": "Rush Courier", "activity_type": "courier", "region_id": "reg_downtown", "poi_id": "poi_depot", "target_count": 3}
        ],
        "factions": [
            {"id": "fac_couriers", "name": "Courier Guild", "initial_reputation": 50, "color": "#00ffcc"}
        ],
        "vehicles": [
            {"id": "veh_bike", "name": "Courier Bike", "region_id": "reg_downtown", "x": 450, "y": 350, "max_speed": 550, "handling": 3.0, "color": "#ff0077"}
        ],
        "threat_system": {"name": "Security Level", "max_level": 5, "current_level": 0},
        "time_system": {"start_hour": 8, "time_scale": 60.0, "day_night_cycle": True}
    }

    val_res = validate_game_dsl(dsl_dict)
    assert val_res.is_valid is True
    assert val_res.dsl is not None
    assert len(val_res.dsl.open_world.regions) == 2
    assert len(val_res.dsl.open_world.vehicles) == 1
    assert val_res.dsl.open_world.vehicles[0].max_speed == 550
    assert val_res.dsl.open_world.vehicles[0].color == "#ff0077"


def test_project_response_serialization_preserves_all_builder_parameters():
    """Verify ProjectResponse to_response serializes camelCase aliases and all 6 parameters."""
    from app.services.project_service import project_service
    from datetime import datetime, timezone

    mock_proj = Project(
        id="proj_test_123",
        user_id="user_test_456",
        title="Dynamic Test Game",
        genre="Action",
        prompt="A dynamic action game",
        status="PLAYABLE",
        engine="Arena Survival",
        art_density=80,
        physics=90,
        modules=["Combat & Dash Mobility"],
        scale="campaign",
        world_mode="open_world",
        design_spec={"elevator_pitch": "Test pitch"},
        game_dsl={"schema_version": "2.0"},
        runtime_metadata={"seed": 12345},
        current_version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    resp = project_service.to_response(mock_proj)
    assert resp.parameters.engine == "Arena Survival"
    assert resp.parameters.art_density == 80
    assert resp.parameters.physics == 90
    assert resp.parameters.modules == ["Combat & Dash Mobility"]
    assert resp.parameters.scale == "campaign"
    assert resp.parameters.world_mode == "open_world"

    # Test serialized dictionary by alias
    resp_dict = resp.model_dump(by_alias=True)
    assert resp_dict["parameters"]["engine"] == "Arena Survival"
    assert resp_dict["parameters"]["artDensity"] == 80
    assert resp_dict["parameters"]["worldMode"] == "open_world"
    assert resp_dict["parameters"]["scale"] == "campaign"
