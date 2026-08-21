"""
Phase 5: tests for generation "scale" tiers (app.generation.scale_tiers),
GameplayQualityValidator.validate_scale_budget, the two-tier soft-nudge
behavior wired into GameGenerationService.generate_game_dsl, and scale-aware
prompt construction in app.ai.prompts.build_generation_prompt.
"""
import pytest

from app.ai.prompts import build_generation_prompt
from app.generation.dsl_models import (
    EntityDef,
    GameDSL,
    GameMetadata,
    LevelDef,
    PlayerDef,
    RuleDef,
    UIDef,
    WorldDef,
)
from app.generation.quality_validator import GameplayQualityValidator
from app.generation.scale_tiers import get_scale_budget
from app.services.game_generation_service import GameGenerationService
from tests.test_dsl import get_sample_valid_dsl_dict
from tests.test_game_generation import MockAIProvider

ALL_TIERS = ("prototype", "standard", "campaign")

# Hard schema ceilings from app.generation.dsl_models (never to be exceeded by
# any tier's budget range).
_HARD_MAX_LEVELS = 5
_HARD_MAX_ENTITIES_PER_LEVEL = 30
_HARD_MAX_RULES_PER_LEVEL = 15


# ---------------------------------------------------------------------------
# get_scale_budget()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tier", ALL_TIERS)
def test_get_scale_budget_ranges_are_internally_consistent(tier):
    budget = get_scale_budget(tier)
    assert budget.scale == tier

    min_levels, max_levels = budget.level_count
    min_entities, max_entities = budget.entities_per_level
    min_rules, max_rules = budget.rules_per_level

    assert min_levels <= max_levels
    assert min_entities <= max_entities
    assert min_rules <= max_rules

    # Strictly within the hard schema caps enforced by GameDSL/LevelDef.
    assert max_levels <= _HARD_MAX_LEVELS
    assert max_entities <= _HARD_MAX_ENTITIES_PER_LEVEL
    assert max_rules <= _HARD_MAX_RULES_PER_LEVEL


def test_get_scale_budget_unknown_scale_defaults_to_standard():
    garbage_budget = get_scale_budget("gigantic-mmo-open-world")
    standard_budget = get_scale_budget("standard")
    assert garbage_budget == standard_budget


def test_get_scale_budget_empty_and_blank_default_to_standard():
    standard_budget = get_scale_budget("standard")
    assert get_scale_budget("") == standard_budget
    assert get_scale_budget("   ") == standard_budget


def test_get_scale_budget_does_not_raise_on_garbage_input():
    # Must never raise merely because an unrecognized scale string slipped
    # through on the generation hot path.
    budget = get_scale_budget("!!not-a-real-tier!!")
    assert budget.scale == "standard"


# ---------------------------------------------------------------------------
# GameplayQualityValidator.validate_scale_budget()
# ---------------------------------------------------------------------------

def _entities(n: int, prefix: str = "e") -> list[EntityDef]:
    return [
        EntityDef(id=f"{prefix}{i}", type="collectible", x=50, y=50, behavior="float", speed=0, health=1)
        for i in range(n)
    ]


def _rules(n: int, prefix: str = "r") -> list[RuleDef]:
    triggers = ["on_time_limit", "on_wave_start", "on_dash", "on_checkpoint", "on_hazard_touch"]
    actions = ["heal_player", "spawn_particles", "trigger_screen_shake", "grant_powerup", "knockback_target"]
    return [
        RuleDef(id=f"{prefix}{i}", trigger=triggers[i % len(triggers)], action=actions[i % len(actions)])
        for i in range(n)
    ]


def _budget_test_dsl(entities=None, rules=None, levels=None) -> GameDSL:
    return GameDSL(
        schema_version="3.0",
        metadata=GameMetadata(
            title="Scale Budget Test",
            genre="Action",
            description="Testing scale budget floors.",
            archetype="survival",
        ),
        world=WorldDef(width=800, height=600, theme="neon", wave_count=3),
        player=PlayerDef(spawn_x=400, spawn_y=300),
        entities=entities or [],
        rules=rules or [],
        ui=UIDef(),
        levels=levels or [],
    )


def test_validate_scale_budget_below_minimum_reports_expected_errors():
    # prototype floor: >=4 entities, >=2 rules (implicit single level since no
    # `levels` array is present).
    dsl = _budget_test_dsl(entities=_entities(2), rules=_rules(1))
    errors = GameplayQualityValidator.validate_scale_budget(dsl, "prototype")

    assert any("expects at least 4 entities in level 1" in e for e in errors)
    assert any("expects at least 2 rules in level 1" in e for e in errors)
    # Implicit single level (level_count=1) satisfies prototype's min_levels=1.
    assert not any("level(s)" in e for e in errors)


def test_validate_scale_budget_meeting_exact_minimum_is_clean():
    # Exactly at the prototype floor (boundary equality must pass, not fail).
    dsl = _budget_test_dsl(entities=_entities(4), rules=_rules(2))
    errors = GameplayQualityValidator.validate_scale_budget(dsl, "prototype")
    assert errors == []


def test_validate_scale_budget_all_minimums_met_or_exceeded_produces_zero_errors():
    lvl1 = LevelDef(level_number=1, title="L1", entities=_entities(8), rules=_rules(3))
    lvl2 = LevelDef(level_number=2, title="L2", entities=_entities(9), rules=_rules(4))
    dsl = _budget_test_dsl(levels=[lvl1, lvl2])
    errors = GameplayQualityValidator.validate_scale_budget(dsl, "standard")
    assert errors == []


def test_validate_scale_budget_no_levels_array_evaluated_as_implicit_single_level():
    # Per the docstring: a DSL with no `levels` campaign array is evaluated
    # against its top-level entities/rules as an implicit single level.
    dsl = _budget_test_dsl(entities=_entities(3), rules=_rules(1))
    errors = GameplayQualityValidator.validate_scale_budget(dsl, "prototype")
    assert any("in level 1" in e for e in errors)


def test_validate_scale_budget_level_count_floor_isolated():
    # A single explicit level that itself meets its entity/rule floors, but the
    # tier (standard) wants at least 2 levels total -> only the level-count
    # error should fire, nothing about entities/rules.
    lvl = LevelDef(level_number=1, title="Only Level", entities=_entities(8), rules=_rules(3))
    dsl = _budget_test_dsl(levels=[lvl])
    errors = GameplayQualityValidator.validate_scale_budget(dsl, "standard")
    assert len(errors) == 1
    assert "expects at least 2 level(s)" in errors[0]


# ---------------------------------------------------------------------------
# GameGenerationService.generate_game_dsl(..., scale=...) end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_game_dsl_scale_met_on_first_attempt_no_repair():
    """A first response already meeting the tier's minimums succeeds outright."""
    valid_dsl = get_sample_valid_dsl_dict()
    # Pad past prototype's 4-entity floor (base fixture has 2 entities, 2 rules;
    # rules already meets prototype's 2-rule floor).
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
        emit_log=lambda lvl, msg: logs.append((lvl, msg)),
    )

    assert result.success is True
    assert result.attempts_used == 1
    assert mock_provider.call_count == 1
    assert not any("Triggering bounded repair loop" in msg for _, msg in logs)


@pytest.mark.asyncio
async def test_generate_game_dsl_scale_shortfall_does_not_block_second_pass_success():
    """
    A first response below the tier's minimums triggers the bounded repair loop
    (budget shortfall gets exactly one nudge). A second (repair) response that is
    STILL below the tier's minimums, but otherwise schema/quality-valid, must
    still succeed -- the shortfall is accepted with a warning, not a hard failure.
    """
    first_response = get_sample_valid_dsl_dict()  # 2 entities: below prototype's 4-entity floor
    second_response = get_sample_valid_dsl_dict()  # still 2 entities: still below floor

    mock_provider = MockAIProvider([first_response, second_response])
    service = GameGenerationService(provider=mock_provider, max_retries=2)

    logs = []
    result = await service.generate_game_dsl(
        prompt="Cyberpunk Dodger",
        scale="prototype",
        emit_log=lambda lvl, msg: logs.append((lvl, msg)),
    )

    assert result.success is True
    assert result.attempts_used == 2
    assert mock_provider.call_count == 2
    # The precise "accepted with a warning" post-repair log line.
    assert any(
        lvl == "WARNING" and "still under target after repair" in msg and "prototype" in msg
        for lvl, msg in logs
    )


@pytest.mark.asyncio
async def test_generate_game_dsl_schema_invalid_first_response_still_repairs_normally_with_scale():
    """
    Budget errors are only ever computed for a schema-VALID candidate (see
    GameGenerationService.generate_game_dsl), so a first response that is
    schema-invalid for an unrelated reason must still go through the ordinary
    repair flow driven by the real schema error -- budget checking never runs
    as a separate parallel path that could interfere. A second response that
    fixes the schema issue but is still below the tier's floor must succeed,
    with the shortfall folded in only as a warning.
    """
    invalid_dsl = get_sample_valid_dsl_dict()
    del invalid_dsl["metadata"]  # schema-invalid; also happens to be below the entity floor

    valid_but_below_floor_dsl = get_sample_valid_dsl_dict()  # schema/quality-valid, 2 entities

    mock_provider = MockAIProvider([invalid_dsl, valid_but_below_floor_dsl])
    service = GameGenerationService(provider=mock_provider, max_retries=2)

    logs = []
    result = await service.generate_game_dsl(
        prompt="Cyberpunk Dodger",
        scale="prototype",
        emit_log=lambda lvl, msg: logs.append((lvl, msg)),
    )

    assert result.success is True
    assert result.attempts_used == 2
    assert mock_provider.call_count == 2
    assert any("Triggering bounded repair loop" in msg for _, msg in logs)
    assert any(
        lvl == "WARNING" and "still under target after repair" in msg
        for lvl, msg in logs
    )


# ---------------------------------------------------------------------------
# build_generation_prompt(..., scale=...)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scale", ALL_TIERS)
def test_build_generation_prompt_reflects_scale_budget_numbers(scale):
    budget = get_scale_budget(scale)
    min_e, max_e = budget.entities_per_level
    min_r, max_r = budget.rules_per_level
    min_l, max_l = budget.level_count

    prompt_text = build_generation_prompt(prompt="A neon runner game", scale=scale)

    assert f"Scale Tier ({scale})" in prompt_text
    assert f"{min_e}-{max_e}" in prompt_text
    assert f"{min_r}-{max_r}" in prompt_text
    assert f"{min_l}-{max_l}" in prompt_text

    # All three current tiers permit more than one level, so the multi-level
    # INTRODUCTION -> ... -> FINALE guidance must appear.
    if max_l > 1:
        assert "INTRODUCTION" in prompt_text
        assert "FINALE" in prompt_text
        assert f"Generate {min_l} to {max_l} levels" in prompt_text


def test_build_generation_prompt_default_scale_is_standard():
    default_text = build_generation_prompt(prompt="A neon runner game")
    standard_text = build_generation_prompt(prompt="A neon runner game", scale="standard")
    assert default_text == standard_text
