"""
Phase 4: Remix pipeline tests -- service-level (AI pipeline) and API-level
(ownership, versioning, request validation).
"""
import copy
import pytest
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

from app.ai.provider import AIProvider
from app.ai.prompts import build_remix_prompt
from app.services.game_generation_service import GameGenerationService, GenerationResult
from app.models.user import User
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.auth.password import hash_password
from app.auth.tokens import create_access_token
from tests.test_dsl import get_sample_valid_dsl_dict


class MockAIProvider(AIProvider):
    """Mock provider with a controllable sequence of responses (reused test double
    pattern from tests/test_game_generation.py)."""
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.call_count = 0

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        self.call_count += 1
        if not self.responses:
            raise RuntimeError("No mock response left in queue.")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _sample_spec_dict() -> Dict[str, Any]:
    return {
        "title": "Neon Grid Runner",
        "elevator_pitch": "Dodge hazards and collect nodes.",
        "genre": "Arcade",
        "core_gameplay_loop": "evade -> collect -> survive",
        "player_role": "Runner",
        "primary_objective": "Collect all nodes",
    }


def _envelope(dsl_dict: Dict[str, Any], spec_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"design_spec": spec_dict or _sample_spec_dict(), "dsl": dsl_dict}


class TestApplyRemixService:
    @pytest.mark.asyncio
    async def test_increase_difficulty_directionally_raises_difficulty_scaling(self):
        base_dsl = get_sample_valid_dsl_dict()
        remixed_dsl = copy.deepcopy(base_dsl)
        remixed_dsl["world"]["difficulty_scaling"] = 2.5

        mock_provider = MockAIProvider([_envelope(remixed_dsl)])
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result = await service.apply_remix(
            current_dsl=base_dsl,
            design_spec=_sample_spec_dict(),
            intents=[{"type": "increase_difficulty", "strength": 0.7}],
        )
        assert result.success is True
        assert result.dsl.world.difficulty_scaling == 2.5
        assert result.dsl.world.difficulty_scaling > 1.0  # default

    @pytest.mark.asyncio
    async def test_add_levels_clamped_when_cap_already_reached(self):
        base_dsl = get_sample_valid_dsl_dict()
        # 5 minimal levels: the hard schema cap.
        base_dsl["levels"] = [
            {"level_number": i, "title": f"Stage {i}", "entities": []}
            for i in range(1, 6)
        ]
        mock_provider = MockAIProvider([_envelope(base_dsl)])
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result = await service.apply_remix(
            current_dsl=base_dsl,
            design_spec=_sample_spec_dict(),
            intents=[{"type": "add_levels", "strength": 0.5}],
        )
        assert result.success is True
        assert result.provider_meta.get("remix_clamped_note") is not None
        assert "cap" in result.provider_meta["remix_clamped_note"].lower()

    @pytest.mark.asyncio
    async def test_invalid_candidate_triggers_bounded_repair_then_succeeds(self):
        base_dsl = get_sample_valid_dsl_dict()
        invalid_dsl = copy.deepcopy(base_dsl)
        del invalid_dsl["metadata"]

        valid_dsl = copy.deepcopy(base_dsl)
        valid_dsl["player"]["speed"] = 320

        mock_provider = MockAIProvider([_envelope(invalid_dsl), _envelope(valid_dsl)])
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result = await service.apply_remix(
            current_dsl=base_dsl,
            design_spec=_sample_spec_dict(),
            intents=[{"type": "faster_pace", "strength": 0.5}],
        )
        assert result.success is True
        assert result.dsl.player.speed == 320
        assert result.attempts_used == 2

    @pytest.mark.asyncio
    async def test_repair_exhausted_returns_failure(self):
        base_dsl = get_sample_valid_dsl_dict()
        invalid_dsl = copy.deepcopy(base_dsl)
        del invalid_dsl["metadata"]

        # 1 initial + 2 retries, all invalid.
        mock_provider = MockAIProvider([
            _envelope(invalid_dsl), _envelope(invalid_dsl), _envelope(invalid_dsl),
        ])
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result = await service.apply_remix(
            current_dsl=base_dsl,
            design_spec=_sample_spec_dict(),
            intents=[{"type": "more_enemies", "strength": 0.5}],
        )
        assert result.success is False
        assert result.error_code == "REMIX_REPAIR_EXHAUSTED"

    def test_personalization_is_secondary_and_never_overrides_explicit_intent(self):
        """The remix prompt must frame Game DNA strictly as secondary flavor, with
        the explicit remix request stated as taking absolute precedence."""
        base_dsl = get_sample_valid_dsl_dict()
        prompt = build_remix_prompt(
            current_dsl=base_dsl,
            design_spec=_sample_spec_dict(),
            intents=[{"type": "faster_pace", "strength": 0.8}],
            personalization={
                "has_sufficient_data": True,
                "preferred_genres": ["RPG"],
                "confidence": "high",
            },
        )
        assert "Increase pacing" in prompt
        assert "RPG" in prompt
        assert "ALWAYS take absolute precedence" in prompt


@pytest.fixture
def remix_client(client, db_session):
    user = User(
        email="remix_tester@example.com",
        username="remixtester",
        password_hash=hash_password("ValidPass123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(user.id)

    other_user = User(
        email="remix_other@example.com",
        username="remixother",
        password_hash=hash_password("ValidPass123!"),
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    base_dsl = get_sample_valid_dsl_dict()
    project = Project(
        user_id=user.id,
        title="Remix Test Project",
        prompt="Cyberpunk action test",
        status="PLAYABLE",
        game_dsl=base_dsl,
        current_version=1,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    v1 = ProjectVersion(
        project_id=project.id,
        version_number=1,
        game_dsl=project.game_dsl,
        change_summary="Initial generated prototype",
    )
    db_session.add(v1)
    db_session.commit()

    return client, user, token, other_user, project


class TestRemixAPI:
    def test_apply_remix_bumps_version_and_preserves_old_version(self, remix_client):
        client, user, token, other_user, project = remix_client
        headers = {"Authorization": f"Bearer {token}"}

        # Capture the pre-remix value up front: `project` is the same SQLAlchemy
        # identity-mapped object the service mutates in place, so reading
        # `project.game_dsl` AFTER the remix call would reflect the new state too.
        original_speed = project.game_dsl["player"]["speed"]
        remixed_dsl = copy.deepcopy(project.game_dsl)
        remixed_dsl["player"]["speed"] = 350

        from app.generation.dsl_models import GameDSL
        mock_dsl = GameDSL.model_validate(remixed_dsl)

        with patch(
            "app.services.project_service.game_generation_service.apply_remix",
            new_callable=AsyncMock,
        ) as mock_apply:
            mock_apply.return_value = GenerationResult(success=True, dsl=mock_dsl, attempts_used=1)
            res = client.post(
                f"/api/projects/{project.id}/remix",
                json={"intents": [{"type": "faster_pace", "strength": 0.6}]},
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert data["version_number"] == 2
            assert data["game_dsl"]["player"]["speed"] == 350
            assert "blueprint" in data

        ver_res = client.get(f"/api/projects/{project.id}/versions", headers=headers)
        assert ver_res.status_code == 200
        versions = ver_res.json()
        assert len(versions) == 2
        v1 = next(v for v in versions if v["version_number"] == 1)
        v2 = next(v for v in versions if v["version_number"] == 2)
        # Old version must remain byte-identical -- immutability guarantee.
        assert v1["game_dsl"]["player"]["speed"] == original_speed
        assert v2["game_dsl"]["player"]["speed"] == 350
        assert v2["remix_intent"][0]["type"] == "faster_pace"
        assert v1["remix_intent"] is None

    def test_remix_cross_user_returns_404(self, remix_client):
        client, user, token, other_user, project = remix_client
        other_token = create_access_token(other_user.id)
        res = client.post(
            f"/api/projects/{project.id}/remix",
            json={"intents": [{"type": "faster_pace"}]},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert res.status_code == 404

    def test_remix_invalid_intent_type_rejected(self, remix_client):
        client, user, token, other_user, project = remix_client
        res = client.post(
            f"/api/projects/{project.id}/remix",
            json={"intents": [{"type": "add_boss"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    def test_remix_duplicate_intent_types_rejected(self, remix_client):
        client, user, token, other_user, project = remix_client
        res = client.post(
            f"/api/projects/{project.id}/remix",
            json={"intents": [{"type": "faster_pace"}, {"type": "faster_pace"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    def test_remix_mutually_exclusive_intents_rejected(self, remix_client):
        client, user, token, other_user, project = remix_client
        res = client.post(
            f"/api/projects/{project.id}/remix",
            json={"intents": [{"type": "increase_difficulty"}, {"type": "decrease_difficulty"}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    def test_remix_more_than_three_intents_rejected(self, remix_client):
        client, user, token, other_user, project = remix_client
        res = client.post(
            f"/api/projects/{project.id}/remix",
            json={"intents": [
                {"type": "faster_pace"}, {"type": "more_enemies"},
                {"type": "more_story"}, {"type": "change_theme"},
            ]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 422

    def test_remix_failure_returns_400(self, remix_client):
        client, user, token, other_user, project = remix_client
        with patch(
            "app.services.project_service.game_generation_service.apply_remix",
            new_callable=AsyncMock,
        ) as mock_apply:
            mock_apply.return_value = GenerationResult(success=False, error_message="AI unavailable")
            res = client.post(
                f"/api/projects/{project.id}/remix",
                json={"intents": [{"type": "faster_pace"}]},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 400
