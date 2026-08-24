import pytest
from typing import Any, Dict, Optional
from app.ai.provider import AIProvider, ModelTimeoutError
from app.services.game_generation_service import GameGenerationService
from tests.test_dsl import get_sample_valid_dsl_dict


class MockAIProvider(AIProvider):
    """Mock provider with controllable sequence of responses."""
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.call_count = 0

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.call_count += 1
        if not self.responses:
            raise RuntimeError("No mock response left in queue.")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


@pytest.mark.asyncio
async def test_generation_success_on_first_attempt():
    """Test standard generation succeeding on attempt 1."""
    valid_dsl = get_sample_valid_dsl_dict()
    # Phase 5: pad past the "prototype" tier's 4-entity floor so this pre-Phase-5
    # fixture (2 entities) doesn't trigger a scale-budget repair nudge, which would
    # break this test's specific "succeeds on the very first attempt" assertions
    # (attempts_used == 1, call_count == 1). Uses scale="prototype" explicitly since
    # this test predates and is unrelated to scale tiers.
    valid_dsl["entities"] = valid_dsl["entities"] + [
        {
            "id": "node_2", "type": "collectible", "x": 500, "y": 200,
            "width": 16, "height": 16, "speed": 0, "health": 1,
            "behavior": "float", "color": "#ffff00", "points": 100,
        },
        {
            "id": "drone_2", "type": "enemy", "x": 300, "y": 400,
            "width": 24, "height": 24, "speed": 100, "health": 30,
            "behavior": "patrol", "color": "#ff0055", "points": 50,
        },
    ]
    mock_provider = MockAIProvider([valid_dsl])
    service = GameGenerationService(provider=mock_provider, max_retries=2)

    logs = []
    result = await service.generate_game_dsl(
        prompt="Cyberpunk Dodger",
        scale="prototype",
        emit_log=lambda lvl, msg: logs.append(msg),
    )

    assert result.success is True
    assert result.dsl is not None
    assert result.dsl.metadata.title == "Neon Grid Runner"
    assert result.attempts_used == 1
    assert mock_provider.call_count == 1
    assert any("[AI] Game specification validated successfully" in log for log in logs)


@pytest.mark.asyncio
async def test_generation_repair_succeeds_on_second_attempt():
    """Test invalid 1st output repaired successfully on 2nd attempt."""
    # First response: invalid (missing metadata)
    invalid_dsl = get_sample_valid_dsl_dict()
    del invalid_dsl["metadata"]

    # Second response: fixed valid DSL
    valid_dsl = get_sample_valid_dsl_dict()

    mock_provider = MockAIProvider([invalid_dsl, valid_dsl])
    service = GameGenerationService(provider=mock_provider, max_retries=2)

    logs = []
    result = await service.generate_game_dsl(
        prompt="Cyberpunk Dodger",
        emit_log=lambda lvl, msg: logs.append(msg),
    )

    assert result.success is True
    assert result.dsl is not None
    assert result.attempts_used == 2
    assert mock_provider.call_count == 2
    assert any("Triggering bounded repair loop" in log for log in logs)
    assert any("Game DSL repaired and validated" in log for log in logs)


@pytest.mark.asyncio
async def test_generation_repair_exhausted_fails():
    """Test that retries are bounded and exceed limit returns DSL_REPAIR_EXHAUSTED."""
    # 3 invalid responses (1 initial + 2 retries)
    invalid_dsl = {"schema_version": "1.0", "broken": True}
    mock_provider = MockAIProvider([invalid_dsl, invalid_dsl, invalid_dsl])
    service = GameGenerationService(provider=mock_provider, max_retries=2)

    logs = []
    result = await service.generate_game_dsl(
        prompt="Cyberpunk Dodger",
        emit_log=lambda lvl, msg: logs.append(msg),
    )

    assert result.success is False
    assert result.error_code == "DSL_REPAIR_EXHAUSTED"
    assert result.dsl is None
    assert mock_provider.call_count == 3  # 1 initial + 2 repair retries
    assert any("Bounded repair attempts exhausted" in log for log in logs)


@pytest.mark.asyncio
async def test_generation_handles_provider_timeout():
    """Test that provider timeout is gracefully mapped into failure result."""
    mock_provider = MockAIProvider([ModelTimeoutError(timeout_seconds=10.0)])
    service = GameGenerationService(provider=mock_provider, max_retries=2)

    logs = []
    result = await service.generate_game_dsl(
        prompt="Cyberpunk Dodger",
        emit_log=lambda lvl, msg: logs.append(msg),
    )

    assert result.success is False
    assert result.error_code == "MODEL_TIMEOUT"
    assert any("Model provider failure" in log for log in logs)


@pytest.mark.asyncio
async def test_generation_deterministic_error_compatibility_trigger():
    """Test that prompt containing ERROR triggers demonstration failure without calling AI provider."""
    mock_provider = MockAIProvider([])  # Should not be called
    service = GameGenerationService(provider=mock_provider, max_retries=2)

    logs = []
    result = await service.generate_game_dsl(
        prompt="A space simulation with an ERROR in physics",
        emit_log=lambda lvl, msg: logs.append(msg),
    )

    assert result.success is False
    assert result.error_code == "BUILD_SYNTAX_ERROR"
    assert mock_provider.call_count == 0
    assert any("FATAL_EXCEPTION" in log for log in logs)


def test_generation_prompt_includes_world_mode():
    """Verify that build_generation_prompt explicitly formats world_mode in TARGET CONFIGURATION (HL-002)."""
    from app.ai.prompts import build_generation_prompt

    prompt_linear = build_generation_prompt("Simple game", world_mode="linear")
    assert "- World Architecture Mode (linear):" in prompt_linear

    prompt_ow = build_generation_prompt("Open world sandbox", world_mode="open_world")
    assert "- World Architecture Mode (open_world):" in prompt_ow
    assert "Open World Sandbox" in prompt_ow

    prompt_camp = build_generation_prompt("Campaign game", world_mode="campaign")
    assert "- World Architecture Mode (campaign):" in prompt_camp

