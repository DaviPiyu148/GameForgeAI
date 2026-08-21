"""
Phase 5: tests for boss/finale DSL primitives (EntityDef.is_boss/boss_phases/
telegraph_ms, LevelDef.is_finale), the new boss-fairness and telegraph-
compatibility checks in GameplayQualityValidator.validate(), and the
explicit-finale-marker preference in app.generation.blueprint.build_game_blueprint.
"""
import pytest
from pydantic import ValidationError

from app.generation.blueprint import build_game_blueprint
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
from app.generation.validator import validate_game_dsl
from tests.test_dsl import get_sample_valid_dsl_dict
from tests.test_gameplay_quality import create_base_dsl


# ---------------------------------------------------------------------------
# EntityDef.is_boss / boss_phases / telegraph_ms -- single-entity floor & defaults
# ---------------------------------------------------------------------------

def test_boss_entity_at_health_floor_succeeds():
    ent = EntityDef(id="boss_ok", x=100, y=100, is_boss=True, health=150)
    assert ent.is_boss is True
    assert ent.health == 150


def test_boss_entity_below_health_floor_raises_validation_error():
    with pytest.raises(ValidationError):
        EntityDef(id="boss_weak", x=100, y=100, is_boss=True, health=149)


def test_non_boss_entity_unaffected_by_boss_health_floor():
    ent = EntityDef(id="grunt", x=100, y=100, is_boss=False, health=1)
    assert ent.is_boss is False
    assert ent.health == 1


def test_entity_and_level_new_field_defaults_are_backward_compatible():
    ent = EntityDef(id="e1", x=10, y=10)
    assert ent.is_boss is False
    assert ent.boss_phases == 1
    assert ent.telegraph_ms == 0

    lvl = LevelDef()
    assert lvl.is_finale is False


# ---------------------------------------------------------------------------
# GameplayQualityValidator.validate() -- boss fairness (scope-aware, >= 2x or 150 floor)
# ---------------------------------------------------------------------------

def test_boss_fairness_fails_when_boss_under_2x_strongest_non_boss_in_scope():
    grunt = EntityDef(id="grunt", type="enemy", x=600, y=200, behavior="patrol", health=100)
    boss = EntityDef(id="boss_1", type="enemy", x=300, y=500, behavior="patrol", health=150, is_boss=True)
    dsl = create_base_dsl(entities=[grunt, boss])

    res = GameplayQualityValidator.validate(dsl)

    assert res.is_valid is False
    assert any("Boss fairness" in e and "boss_1" in e for e in res.errors)


def test_boss_fairness_passes_when_boss_meets_2x_or_150_bar():
    grunt = EntityDef(id="grunt", type="enemy", x=600, y=200, behavior="patrol", health=100)
    boss = EntityDef(id="boss_1", type="enemy", x=300, y=500, behavior="patrol", health=200, is_boss=True)
    dsl = create_base_dsl(entities=[grunt, boss])

    res = GameplayQualityValidator.validate(dsl)

    assert res.is_valid is True
    assert not any("Boss fairness" in e for e in res.errors)


def test_boss_fairness_is_scope_isolated_across_levels():
    """A weak boss in level 1 is not excused by a strong regular enemy in level 2."""
    boss_lvl1 = EntityDef(id="boss_lvl1", type="enemy", x=650, y=150, behavior="patrol", health=150, is_boss=True)
    grunt_lvl1 = EntityDef(id="grunt_lvl1", type="enemy", x=200, y=500, behavior="patrol", health=100)
    strong_lvl2 = EntityDef(id="strong_lvl2", type="enemy", x=200, y=500, behavior="patrol", health=500)

    level1 = LevelDef(level_number=1, title="Stage 1", entities=[boss_lvl1, grunt_lvl1], rules=[])
    level2 = LevelDef(level_number=2, title="Stage 2", entities=[strong_lvl2], rules=[])

    dsl = GameDSL(
        schema_version="3.0",
        metadata=GameMetadata(
            title="Scope Isolation Test",
            genre="Action",
            description="Boss fairness scope isolation test.",
            archetype="survival",
        ),
        world=WorldDef(width=800, height=600, theme="neon", wave_count=3),
        player=PlayerDef(spawn_x=400, spawn_y=300),
        entities=[],
        rules=[RuleDef(id="r1", trigger="on_player_death", action="lose_game")],
        ui=UIDef(),
        levels=[level1, level2],
    )

    res = GameplayQualityValidator.validate(dsl)

    assert res.is_valid is False
    fairness_errors = [e for e in res.errors if "Boss fairness" in e]
    assert len(fairness_errors) == 1
    assert "boss_lvl1" in fairness_errors[0]
    assert "strong_lvl2" not in fairness_errors[0]


# ---------------------------------------------------------------------------
# GameplayQualityValidator.validate() -- telegraph compatibility
# ---------------------------------------------------------------------------

def test_telegraph_allowed_on_ranged_attack_behavior():
    ent = EntityDef(id="turret", type="enemy", x=600, y=200, behavior="ranged_attack", telegraph_ms=500, fire_rate=1.0, health=40)
    dsl = create_base_dsl(entities=[ent])

    res = GameplayQualityValidator.validate(dsl)

    assert res.is_valid is True
    assert not any("Invalid telegraph" in e for e in res.errors)


def test_telegraph_rejected_on_non_ranged_behavior():
    ent = EntityDef(id="patroller", type="enemy", x=600, y=200, behavior="patrol", telegraph_ms=500, health=40)
    dsl = create_base_dsl(entities=[ent])

    res = GameplayQualityValidator.validate(dsl)

    assert res.is_valid is False
    assert any("Invalid telegraph" in e and "patroller" in e for e in res.errors)


def test_telegraph_zero_never_triggers_check_regardless_of_behavior():
    ent = EntityDef(id="patroller2", type="enemy", x=600, y=200, behavior="patrol", telegraph_ms=0, health=40)
    dsl = create_base_dsl(entities=[ent])

    res = GameplayQualityValidator.validate(dsl)

    assert res.is_valid is True
    assert not any("Invalid telegraph" in e for e in res.errors)


# ---------------------------------------------------------------------------
# build_game_blueprint() -- explicit is_finale marker preferred over last-level heuristic
# ---------------------------------------------------------------------------

_BASE_DSL_DICT = {
    "schema_version": "3.0",
    "metadata": {"title": "Boss Finale Test", "genre": "Action", "description": "A finale marker test game.", "archetype": "survival"},
    "world": {"width": 800, "height": 600, "theme": "neon", "wave_count": 3},
    "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "dash_speed": 600, "attack_type": "ranged"},
    "entities": [],
    "rules": [{"id": "r1", "trigger": "on_collide_enemy", "action": "damage_player"}],
}


def _three_level_dsl(finale_level_number: "int | None") -> GameDSL:
    data = dict(_BASE_DSL_DICT)
    levels = []
    for n, title in ((1, "Opening"), (2, "Middle"), (3, "Closing")):
        levels.append({
            "level_number": n,
            "title": title,
            "objective": {"type": "reach_exit", "description": f"Clear {title}"},
            "entities": [{"id": f"e{n}", "type": "enemy", "x": 100, "y": 100, "behavior": "patrol"}],
            "completion_message": f"{title.upper()} COMPLETE",
            "is_finale": (n == finale_level_number),
        })
    data["levels"] = levels
    return GameDSL.model_validate(data)


def test_explicit_finale_marker_overrides_last_level_heuristic():
    """A NON-last level explicitly marked is_finale=True drives the blueprint's finale."""
    dsl = _three_level_dsl(finale_level_number=2)  # middle level, not the last
    bp = build_game_blueprint("proj_finale_explicit", dsl, design_spec=None)
    assert bp.finale == "MIDDLE COMPLETE"


def test_no_explicit_finale_falls_back_to_last_level_heuristic():
    """With no level marked is_finale, the last-level heuristic still applies (no regression)."""
    dsl = _three_level_dsl(finale_level_number=None)  # none marked
    bp = build_game_blueprint("proj_finale_fallback", dsl, design_spec=None)
    assert bp.finale == "CLOSING COMPLETE"


# ---------------------------------------------------------------------------
# Backward compatibility: pre-Phase-5 DSL (no boss/finale fields anywhere)
# ---------------------------------------------------------------------------

def test_pre_phase5_dsl_dict_still_validates_end_to_end():
    data = get_sample_valid_dsl_dict()
    val_res = validate_game_dsl(data)

    assert val_res.is_valid is True
    assert val_res.dsl is not None
    assert all(not e.is_boss for e in val_res.dsl.entities)

    quality_res = GameplayQualityValidator.validate(val_res.dsl)
    assert quality_res.is_valid is True
