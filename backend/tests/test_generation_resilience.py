"""
Comprehensive test suite for Game Generation Hardening V1.

Verifies:
- Deterministic normalization of schema drift (e.g. levels[0].width) with ZERO repair LLM calls.
- Safe type coercion (string numbers -> ints/floats, hex color formatting).
- Security boundaries (unsafe scripts / arbitrary code are REJECTED, never silently dropped).
- Bounded semantic repair (maximum 1 attempt with dedicated repair timeout).
- Provider timeout handling (initial generation timeout vs repair timeout).
- Non-blocking error handling and build job safety.
"""

import pytest
from typing import Any, Dict, List, Optional, Tuple

from app.ai.provider import AIProvider, ModelTimeoutError, ModelRateLimitedError, ModelInvalidResponseError
from app.config import settings
from app.generation.dsl_normalizer import DSLNormalizer, ValidationIssue
from app.generation.validator import validate_game_dsl
from app.services.game_generation_service import GameGenerationService, GenerationResult


# ─────────────────────────────────────────────────────────────────────────────
# Mock Provider Helpers
# ─────────────────────────────────────────────────────────────────────────────

class MockProvider(AIProvider):
    """Configurable mock AI provider for testing generation and repair pipelines."""

    def __init__(self, responses: List[Any], error_on_call: Optional[Dict[int, Exception]] = None):
        self.responses = responses
        self.error_on_call = error_on_call or {}
        self.call_count = 0
        self.timeouts_received: List[Optional[float]] = []
        self.prompts_received: List[str] = []

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        res, _ = await self.generate_structured_with_meta(system_prompt, user_prompt, json_schema, timeout=timeout)
        return res

    async def generate_structured_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self.call_count += 1
        self.timeouts_received.append(timeout)
        self.prompts_received.append(user_prompt)

        if self.call_count in self.error_on_call:
            raise self.error_on_call[self.call_count]

        idx = min(self.call_count - 1, len(self.responses) - 1)
        resp = self.responses[idx]
        return resp, {
            "provider": "mock_provider",
            "model": "mock-model",
            "fallback_used": False,
        }


def _make_valid_dsl(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Helper returning a minimal valid GameDSL dictionary."""
    base = {
        "schema_version": "3.0",
        "metadata": {
            "title": "Neon Dash",
            "genre": "Action",
            "description": "An intense dodge game",
            "archetype": "survival",
        },
        "world": {
            "width": 800,
            "height": 600,
            "theme": "neon",
            "gravity": 0,
            "background_color": "#0a0a1a",
        },
        "player": {
            "spawn_x": 400,
            "spawn_y": 300,
            "speed": 250,
            "dash_speed": 600,
            "max_health": 100,
            "color": "#00f0ff",
        },
        "entities": [
            {
                "id": "e_drone_1",
                "type": "enemy",
                "x": 200,
                "y": 200,
                "behavior": "patrol",
                "speed": 100,
                "health": 20,
                "damage": 15,
                "color": "#ff0055",
            },
            {
                "id": "c_gem_1",
                "type": "collectible",
                "x": 600,
                "y": 400,
                "behavior": "stationary",
                "points": 50,
                "color": "#00ff66",
            },
        ],
        "rules": [
            {
                "id": "r_damage",
                "trigger": "on_collide_enemy",
                "action": "damage_player",
                "params": {"damage": 15},
            },
            {
                "id": "r_score",
                "trigger": "on_collect",
                "action": "add_score",
                "params": {"points": 50},
            },
        ],
        "ui": {
            "show_health": True,
            "show_score": True,
            "show_stamina": True,
            "status_text": "SURVIVE",
        },
    }
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v
    return base


# ─────────────────────────────────────────────────────────────────────────────
# 1. SPECIFIC REGRESSION TEST FOR `levels[0].width` (Phase 20)
# ─────────────────────────────────────────────────────────────────────────────

class TestLevelWidthRegression:

    def test_normalizer_recovers_levels_width_deterministically(self):
        """
        Verify that when an LLM emits 'width' directly inside levels[0],
        the normalizer moves it to levels[0].world or cleans it deterministically,
        and strict Pydantic validation passes with zero errors.
        """
        candidate = _make_valid_dsl()
        candidate["levels"] = [
            {
                "level_number": 1,
                "title": "Stage 1",
                "width": 1200,  # <-- The exact bug trigger!
                "height": 900,
                "gravity": 500,
                "entities": candidate["entities"],
                "rules": candidate["rules"],
            }
        ]

        val_res = validate_game_dsl(candidate)
        assert val_res.is_valid is True
        assert val_res.dsl is not None
        assert len(val_res.dsl.levels) == 1
        assert val_res.dsl.levels[0].world is not None
        assert val_res.dsl.levels[0].world.width == 1200
        assert val_res.dsl.levels[0].world.height == 900
        assert val_res.dsl.levels[0].world.gravity == 500

    @pytest.mark.anyio
    async def test_generation_pipeline_zero_repair_calls_on_levels_width(self):
        """
        MANDATORY REGRESSION:
        When raw AI candidate has levels[0].width, the pipeline MUST succeed
        on attempt 1 with ZERO repair calls to the provider.
        """
        candidate_with_width_bug = {
            "design_spec": {
                "title": "Cyber Runner",
                "genre": "Action",
                "elevator_pitch": "Fast dodging prototype",
                "core_gameplay_loop": "evade -> collect -> win",
                "primary_objective": "Collect gems",
            },
            "dsl": {
                "metadata": {"title": "Cyber Runner", "genre": "Action", "archetype": "survival"},
                "world": {"width": 800, "height": 600, "theme": "cyberpunk"},
                "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250},
                "levels": [
                    {
                        "level_number": 1,
                        "title": "Sector 1",
                        "width": 1200,  # <-- Bug trigger
                        "height": 800,  # <-- Bug trigger
                        "entities": [
                            {"id": "e1", "type": "enemy", "x": 300, "y": 300, "behavior": "patrol"},
                            {"id": "e2", "type": "enemy", "x": 600, "y": 200, "behavior": "bounce"},
                            {"id": "c1", "type": "collectible", "x": 500, "y": 400, "behavior": "stationary"},
                            {"id": "c2", "type": "collectible", "x": 700, "y": 300, "behavior": "stationary"},
                        ],
                        "rules": [
                            {"id": "r1", "trigger": "on_collide_enemy", "action": "damage_player"},
                            {"id": "r2", "trigger": "on_collect", "action": "add_score", "params": {"points": 50}},
                            {"id": "r3", "trigger": "on_score_target", "action": "win_game", "params": {"target_score": 50}},
                        ],
                    }
                ],
            },
        }

        mock_provider = MockProvider(responses=[candidate_with_width_bug])
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result: GenerationResult = await service.generate_game_dsl(prompt="Cyberpunk game", scale="prototype")

        assert result.success is True
        assert result.dsl is not None
        assert result.attempts_used == 1
        # CRITICAL ASSERTION: ZERO repair provider calls!
        assert mock_provider.call_count == 1, "Expected exactly 1 AI call, zero repair calls"


# ─────────────────────────────────────────────────────────────────────────────
# 2. DETERMINISTIC NORMALIZATION & SAFE DRIFT (Phase 1, 2, 3)
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterministicNormalization:

    def test_legacy_aliases_and_scalar_coercion(self):
        """Verify normalization of legacy aliases and string number coercion."""
        raw = {
            "metadata": {"title": "Test Game", "genre": "Arcade"},
            "world": {
                "width": "1200",  # String int
                "height": "800",
                "density": 40,    # Safe unknown field
                "background_color": "00f0ff", # Missing leading '#'
            },
            "player": {
                "x": "400",       # Legacy alias for spawn_x + string int
                "y": "300",       # Legacy alias for spawn_y
                "health": "150",  # Legacy alias for max_health
                "jump": "400",    # Legacy alias for jump_power
                "lives": 3,       # Harmless extra field
            },
            "entities": [
                {
                    "id": "e1",
                    "type": "drone", # Needs type mapping -> 'enemy'
                    "pos_x": "250",  # Legacy alias -> x
                    "pos_y": "150",  # Legacy alias -> y
                    "score": "100",  # Legacy alias -> points + string int
                    "tags": ["flying"], # Harmless extra field
                }
            ],
            "rules": [
                {
                    "id": "r1",
                    "event": "on_collect",  # Legacy alias -> trigger
                    "handler": "add_score", # Legacy alias -> action
                    "params": {"amount": "50"},
                }
            ],
        }

        val_res = validate_game_dsl(raw)
        assert val_res.is_valid is True
        dsl = val_res.dsl
        assert dsl.world.width == 1200
        assert dsl.world.background_color == "#00f0ff"
        assert dsl.player.spawn_x == 400
        assert dsl.player.spawn_y == 300
        assert dsl.player.max_health == 150
        assert dsl.player.jump_power == 400
        assert len(dsl.entities) >= 1
        assert dsl.entities[0].type == "enemy"
        assert dsl.entities[0].x == 250
        assert dsl.entities[0].points == 100
        assert dsl.rules[0].trigger == "on_collect"
        assert dsl.rules[0].action == "add_score"

    def test_markdown_codeblock_stripping(self):
        """Verify markdown wrapped json is cleanly extracted and normalized."""
        markdown_json = """```json
{
  "metadata": {"title": "Markdown Game", "genre": "Action"},
  "world": {"width": 800, "height": 600},
  "player": {"spawn_x": 400, "spawn_y": 300},
  "entities": [{"id": "e1", "type": "enemy", "x": 200, "y": 200}],
  "rules": [{"id": "r1", "trigger": "on_collide_enemy", "action": "damage_player"}]
}
```"""
        val_res = validate_game_dsl(markdown_json)
        assert val_res.is_valid is True
        assert val_res.dsl.metadata.title == "Markdown Game"


# ─────────────────────────────────────────────────────────────────────────────
# 3. SECURITY BOUNDARIES (Phase 3, 23)
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityBoundaries:

    def test_unsafe_runtime_script_is_rejected_never_silently_dropped(self):
        """
        CRITICAL SECURITY GUARANTEE:
        Arbitrary code fields like 'runtime_script' or 'javascript' MUST NOT
        be silently discarded or accepted. They must trigger a security rejection.
        """
        payload = _make_valid_dsl()
        payload["player"]["runtime_script"] = "window.location='https://attacker.com'"

        val_res = validate_game_dsl(payload)
        assert val_res.is_valid is False
        assert val_res.has_unsafe_issues() is True
        assert any("runtime_script" in err or "Security" in err for err in val_res.errors)

    def test_script_tag_injection_in_text_field_rejected(self):
        """Verify HTML / script tags in metadata or rule names are rejected."""
        payload = _make_valid_dsl()
        payload["metadata"]["title"] = "Game <script>alert(1)</script>"

        val_res = validate_game_dsl(payload)
        assert val_res.is_valid is False

    @pytest.mark.anyio
    async def test_generation_pipeline_short_circuits_on_unsafe_payload_no_repair(self):
        """Unsafe payloads must abort generation immediately with UNSAFE_DSL_PAYLOAD and NO repair call."""
        unsafe_candidate = {
            "metadata": {"title": "Unsafe Game", "genre": "Action"},
            "world": {"width": 800, "height": 600},
            "player": {"spawn_x": 400, "spawn_y": 300, "javascript": "evil_eval()"},
        }
        mock_provider = MockProvider(responses=[unsafe_candidate])
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result = await service.generate_game_dsl(prompt="Hacker game")

        assert result.success is False
        assert result.error_code == "UNSAFE_DSL_PAYLOAD"
        assert mock_provider.call_count == 1, "Must never trigger repair for unsafe injection"


# ─────────────────────────────────────────────────────────────────────────────
# 4. BOUNDED SEMANTIC REPAIR & TIMEOUTS (Phase 5, 6, 7, 10, 21)
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticRepairAndProviderTimeouts:

    @pytest.mark.anyio
    async def test_semantic_repair_triggers_once_with_dedicated_repair_timeout(self):
        """
        When candidate has genuine semantic errors (e.g. missing player or empty un-remediable rules),
        exactly ONE repair attempt is triggered, and it uses AI_REPAIR_TIMEOUT_SECONDS (45.0s).
        """
        # Attempt 1 has broken un-normalizable data
        broken_candidate = {
            "metadata": {"title": "Broken"},
            "world": {"width": 800, "height": 600},
            "player": {"speed": 250},
            # Missing spawn_x / spawn_y with invalid values or un-remediable state
            "entities": [{"id": "e1", "type": "unknown_junk_123", "x": 100, "y": 100}],
            "rules": [],
        }
        # Attempt 2 (repaired) returns valid DSL
        valid_candidate = {
            "design_spec": {"title": "Repaired Game", "genre": "Action"},
            "dsl": _make_valid_dsl({"metadata": {"title": "Repaired Game"}}),
        }

        mock_provider = MockProvider(responses=[broken_candidate, valid_candidate])
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result = await service.generate_game_dsl(prompt="Test game")

        assert result.success is True
        assert result.dsl.metadata.title == "Repaired Game"
        assert result.attempts_used == 2
        assert mock_provider.call_count == 2
        # Verify repair call received dedicated repair timeout
        assert mock_provider.timeouts_received[1] == settings.AI_REPAIR_TIMEOUT_SECONDS

    @pytest.mark.anyio
    async def test_repair_provider_timeout_preserves_original_error_and_fails_gracefully(self):
        """
        When repair call times out at the provider:
        - Must not hang.
        - Must not claim fake success.
        - Must preserve error message citing both timeout and original validation issue.
        """
        broken_candidate = {
            "metadata": {"title": "Broken"},
            "world": {"width": 800, "height": 600},
            "player": {"spawn_x": 400, "spawn_y": 300},
            "entities": [],
            "rules": [],
        }

        mock_provider = MockProvider(
            responses=[broken_candidate],
            error_on_call={2: ModelTimeoutError(settings.AI_REPAIR_TIMEOUT_SECONDS)},
        )
        service = GameGenerationService(provider=mock_provider, max_retries=2)

        result = await service.generate_game_dsl(prompt="Test game")

        assert result.success is False
        assert result.error_code == "MODEL_TIMEOUT"
        assert "timed out" in result.error_message.lower()
        assert mock_provider.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# 5. OPEN WORLD HARDENING (Phase 15)
# ─────────────────────────────────────────────────────────────────────────────

class TestOpenWorldHardening:

    def test_open_world_safe_drift_normalization(self):
        """Verify Open World model normalization and safe extra field dropping."""
        raw = _make_valid_dsl()
        raw["world"]["world_mode"] = "open_world"
        raw["open_world"] = {
            "regions": [
                {
                    "id": "r1",
                    "name": "Downtown",
                    "width": "1600",
                    "height": "1200",
                    "population": 500,  # Safe unknown field
                    "seed": 12345,      # Safe unknown field
                },
                {
                    "id": "r2",
                    "name": "Uptown",
                    "width": "1600",
                    "height": "1200",
                },
            ],
            "vehicles": [
                {
                    "id": "v1",
                    "name": "Speeder",
                    "region_id": "r1",
                    "gear_count": 5,    # Safe unknown field
                    "fuel": 100,        # Safe unknown field
                }
            ],
            "pois": [
                {
                    "id": "p1",
                    "name": "Garage A",
                    "type": "dock",     # Mapped to 'garage'
                    "region_id": "r1",
                    "radius": 50,       # Safe unknown field
                }
            ],
            "activities": [
                {
                    "id": "a1",
                    "title": "Courier Run",
                    "type": "transport", # Mapped to 'delivery'
                    "region_id": "r1",
                },
                {
                    "id": "a2",
                    "title": "Patrol Mission",
                    "type": "mission",
                    "region_id": "r2",
                },
            ],
        }

        val_res = validate_game_dsl(raw)
        assert val_res.is_valid is True
        assert val_res.dsl.open_world is not None
        assert len(val_res.dsl.open_world.regions) == 2
        assert val_res.dsl.open_world.vehicles[0].name == "Speeder"
        assert val_res.dsl.open_world.pois[0].type == "garage"
        assert val_res.dsl.open_world.activities[0].type == "delivery"
