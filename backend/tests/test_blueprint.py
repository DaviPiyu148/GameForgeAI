"""
Phase 4: Game Blueprint derivation and API tests.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.models.user import User
from app.models.project import Project
from app.auth.password import hash_password
from app.auth.tokens import create_access_token
from app.generation.dsl_models import GameDSL, LevelDef, ObjectiveDef, EntityDef
from app.generation.blueprint import build_game_blueprint
from app.schemas.design_spec import GameDesignSpec


BASE_DSL = {
    "schema_version": "3.0",
    "metadata": {"title": "Neon Courier", "genre": "Action", "description": "A courier game.", "archetype": "survival"},
    "world": {"width": 800, "height": 600, "theme": "neon", "wave_count": 3},
    "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "dash_speed": 600, "attack_type": "ranged"},
    "entities": [
        {"id": "drone_1", "type": "enemy", "x": 650, "y": 150, "behavior": "patrol"},
        {"id": "drone_2", "type": "enemy", "x": 100, "y": 500, "behavior": "chase"},
    ],
    "rules": [{"id": "r1", "trigger": "on_collide_enemy", "action": "damage_player"}],
}


def _single_level_dsl() -> GameDSL:
    return GameDSL.model_validate(BASE_DSL)


def _multi_level_dsl() -> GameDSL:
    data = dict(BASE_DSL)
    data["levels"] = [
        {
            "level_number": 1,
            "title": "Sector A",
            "objective": {"type": "collect_all", "description": "Collect all chips"},
            "entities": [{"id": "e1", "type": "enemy", "x": 100, "y": 100, "behavior": "patrol"}],
            "completion_message": "SECTOR A CLEAR",
        },
        {
            "level_number": 2,
            "title": "Final Extraction",
            "objective": {"type": "reach_exit", "description": "Reach the extraction point"},
            "entities": [{"id": "e2", "type": "enemy", "x": 200, "y": 200, "behavior": "ranged_attack"}],
            "completion_message": "EXTRACTION COMPLETE",
        },
    ]
    return GameDSL.model_validate(data)


class TestBlueprintDerivation:
    def test_single_level_blueprint_fields(self):
        dsl = _single_level_dsl()
        bp = build_game_blueprint("proj_1", dsl, design_spec=None)
        assert bp.title == "Neon Courier"
        assert bp.level_count == 1
        assert bp.world_area_count == 1
        assert "Ranged Combat" in bp.supported_mechanics
        assert "Dash Mobility" in bp.supported_mechanics
        assert bp.enemy_variety == 2

    def test_multi_level_blueprint_reflects_all_levels(self):
        dsl = _multi_level_dsl()
        bp = build_game_blueprint("proj_2", dsl, design_spec=None)
        assert bp.level_count == 2
        assert bp.world_area_count == 2
        assert len(bp.objectives) == 2
        assert bp.objectives[0].level_number == 1
        assert bp.objectives[1].level_number == 2
        assert bp.finale == "EXTRACTION COMPLETE"
        assert "Ranged Enemies" in bp.supported_mechanics
        assert "Patrol Enemies" in bp.supported_mechanics
        # enemy_variety must count entities across ALL levels, not just top-level
        assert bp.enemy_variety == 2 + 2

    def test_blueprint_never_claims_unsupported_capabilities(self):
        """Vehicles and boss fights are not implemented yet (Phase 5/6) and must
        never appear in a blueprint, no matter how the DSL is shaped."""
        dsl = _multi_level_dsl()
        bp = build_game_blueprint("proj_3", dsl, design_spec=None)
        for forbidden in ("Vehicles", "Vehicle", "Boss Fight", "Boss", "Wanted System", "Police"):
            assert forbidden not in bp.supported_mechanics

    def test_blueprint_uses_design_spec_when_available(self):
        dsl = _single_level_dsl()
        spec = GameDesignSpec.model_validate({
            "title": "Neon Courier",
            "elevator_pitch": "Deliver data across a neon city.",
            "genre": "Action / Adventure",
            "core_gameplay_loop": "Explore -> Deliver -> Escape",
            "player_role": "Data Courier",
            "primary_objective": "Deliver all packages",
            "estimated_session_length": "4-5 minutes",
        })
        bp = build_game_blueprint("proj_4", dsl, design_spec=spec)
        assert bp.genre == "Action / Adventure"
        assert bp.core_loop == "Explore -> Deliver -> Escape"
        assert bp.player_fantasy == "Data Courier"
        assert bp.estimated_session_length == "4-5 minutes"

    def test_no_mechanic_predicate_ever_yields_vehicles_or_boss(self):
        """Even a maximally 'busy' DSL must never surface an unimplemented mechanic name."""
        data = dict(BASE_DSL)
        data["player"]["attack_type"] = "aoe"
        data["world"]["gravity"] = 600
        data["player"]["jump_power"] = 500
        data["rules"].append({"id": "r2", "trigger": "on_checkpoint", "action": "grant_powerup"})
        dsl = GameDSL.model_validate(data)
        bp = build_game_blueprint("proj_5", dsl, design_spec=None)
        assert all(m not in ("Vehicles", "Boss Fights") for m in bp.supported_mechanics)


@pytest.fixture
def blueprint_client(client, db_session):
    user = User(
        email="blueprint_tester@example.com",
        username="blueprinttester",
        password_hash=hash_password("ValidPass123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(user.id)

    other_user = User(
        email="blueprint_other@example.com",
        username="blueprintother",
        password_hash=hash_password("ValidPass123!"),
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    project = Project(
        user_id=user.id,
        title="Neon Courier",
        prompt="A neon delivery game",
        status="PLAYABLE",
        game_dsl=BASE_DSL,
        current_version=1,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return client, user, token, other_user, project


class TestBlueprintAPI:
    def test_get_blueprint_success(self, blueprint_client):
        client, user, token, other_user, project = blueprint_client
        res = client.get(f"/api/projects/{project.id}/blueprint", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Neon Courier"
        assert data["level_count"] == 1
        assert "Vehicles" not in data["supported_mechanics"]

    def test_get_blueprint_cross_user_returns_404(self, blueprint_client):
        client, user, token, other_user, project = blueprint_client
        other_token = create_access_token(other_user.id)
        res = client.get(f"/api/projects/{project.id}/blueprint", headers={"Authorization": f"Bearer {other_token}"})
        assert res.status_code == 404

    def test_get_blueprint_missing_project_returns_404(self, blueprint_client):
        client, user, token, other_user, project = blueprint_client
        res = client.get("/api/projects/does-not-exist/blueprint", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404
