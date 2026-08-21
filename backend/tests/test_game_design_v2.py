"""
Unit and integration tests for Game Design Specification V2 and Builder Parameter Compilation.

Verifies:
- GameDesignSpec V2 structured submodels (CoreLoopSpec, ObjectiveSpec, ProgressionPhase)
- Script injection protection across all nested fields
- Compilation & Materialization of Builder parameters (engine, physics, art_density, modules)
- DesignSpec to GameDSL compilation mapping
"""
import pytest
from pydantic import ValidationError

from app.schemas.design_spec import (
    CoreLoopSpec,
    GameDesignSpec,
    ObjectiveSpec,
    ProgressionPhase,
)
from app.services.game_generation_service import GameGenerationService


# -----------------------------------------------------------------------------
# 1. GameDesignSpec V2 Structured Models Validation
# -----------------------------------------------------------------------------

def test_valid_game_design_spec_v2():
    """Verify complete GameDesignSpec V2 parses cleanly with all structured submodels."""
    spec = GameDesignSpec(
        title="Cyber Courier",
        elevator_pitch="Deliver data nodes across a hostile neon district.",
        genre="Action",
        subgenre="Cyberpunk Runner",
        theme="neon",
        visual_style="Vector Neon",
        camera="top_down",
        core_gameplay_loop="evade -> collect -> extract",
        player_role="Courier",
        primary_objective="Collect 3 data nodes and escape",
        secondary_objectives=["Conserve dash stamina"],
        player_abilities=["move", "dash", "shoot"],
        win_conditions=["Gather all data nodes"],
        loss_conditions=["Health depleted"],
        loop_details=CoreLoopSpec(
            player_action="Navigate alleyways to grab data nodes",
            immediate_feedback="Floating scores and energy bursts",
            increasing_pressure="Patrol drones accelerate and shoot",
            progression="Unlock extraction beacon after gathering nodes",
            resolution="Escape to victory zone",
        ),
        objective_details=ObjectiveSpec(
            primary="Collect 3 data nodes and escape",
            supporting=["Avoid drone fire", "Conserve dash stamina"],
            completion_criteria="all_collectibles_gathered",
            failure_condition="player_health_depleted",
        ),
        progression_phases=[
            ProgressionPhase(
                phase="EARLY",
                trigger="Wave 1 start",
                description="Explore quiet alleys",
                runtime_effect="Patrol drones active",
            ),
            ProgressionPhase(
                phase="MID",
                trigger="50% nodes gathered",
                description="Drones escalate pursuit",
                runtime_effect="Chase enemies spawn",
            ),
            ProgressionPhase(
                phase="FINALE",
                trigger="Final node gathered",
                description="Escape under heavy fire",
                runtime_effect="Ranged attack enemies spawn",
            ),
        ],
        rationale=["Top-down camera allows tactical scouting", "Dash provides high-skill evasion"],
    )

    assert spec.title == "Cyber Courier"
    assert spec.loop_details is not None
    assert spec.loop_details.player_action == "Navigate alleyways to grab data nodes"
    assert spec.objective_details is not None
    assert spec.objective_details.primary == "Collect 3 data nodes and escape"
    assert len(spec.progression_phases) == 3
    assert spec.progression_phases[1].phase == "MID"


def test_script_injection_blocked_in_nested_design_spec():
    """Verify script injection in nested design spec fields is rejected."""
    with pytest.raises(ValidationError):
        CoreLoopSpec(
            player_action="<script>alert(1)</script>",
        )

    with pytest.raises(ValidationError):
        ObjectiveSpec(
            primary="Normal objective",
            supporting=["javascript:void(0)"],
        )

    with pytest.raises(ValidationError):
        ProgressionPhase(
            phase="EARLY",
            trigger="eval(danger)",
            description="Phase description",
            runtime_effect="Effect",
        )


# -----------------------------------------------------------------------------
# 2. Builder Parameter Compilation & Propagation
# -----------------------------------------------------------------------------

def test_builder_parameter_compilation_platformer():
    """Verify 2D Platformer profile configures gravity, jump_power, and goal rules."""
    service = GameGenerationService(provider=None)

    raw_dsl = {
        "metadata": {"title": "Jump Test", "genre": "Platformer", "description": "Jump", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "neon", "gravity": 0},
        # speed/dash_speed intentionally absent (not merely 0) so physics propagation
        # is expected to fill them in from the physics parameter, below.
        "player": {"spawn_x": 100, "spawn_y": 400, "jump_power": 0},
        "entities": [],
        "rules": [],
    }

    compiled = service._compile_and_propagate_parameters(
        dsl_dict=raw_dsl,
        spec_dict={"primary_objective": "Reach the beacon"},
        engine="2D Platformer",
        art_density=80,
        physics=90,
        modules=["Combat & Dash Mobility"],
    )

    # Invariant: Platformer profile forces platformer archetype, positive gravity, positive jump power
    assert compiled["metadata"]["archetype"] == "platformer"
    assert compiled["world"]["gravity"] > 0
    assert compiled["player"]["jump_power"] > 0
    assert any(r["trigger"] == "on_reach_goal" for r in compiled["rules"])
    # Physics 90 -> high player speed and dash (fields were absent, so physics fills them in)
    assert compiled["player"]["speed"] > 250
    assert compiled["player"]["dash_speed"] > 600
    # Art density 80 -> hazard density ~50
    assert compiled["world"]["hazard_density"] == int(10 + (80 / 100) * 50)
    # Combat module active
    assert compiled["player"]["attack_type"] == "ranged"
    assert compiled["player"]["attack_damage"] >= 25


def test_physics_propagation_preserves_explicit_player_values():
    """
    Regression: an AI-generated (or otherwise explicitly set) player.speed/dash_speed
    must be preserved as-is, even if it happens to equal the prompt template's few-shot
    example values (250 / 600) — physics propagation must only fill in values that are
    truly absent or non-positive, never overwrite a present, valid, positive value.
    """
    service = GameGenerationService(provider=None)

    raw_dsl = {
        "metadata": {"title": "Explicit Speed Test", "genre": "Action", "description": "D", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "neon", "gravity": 0},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250, "dash_speed": 600},
        "entities": [],
        "rules": [],
    }

    compiled = service._compile_and_propagate_parameters(
        dsl_dict=raw_dsl,
        spec_dict=None,
        engine="Top-Down Action",
        art_density=50,
        physics=90,
        modules=[],
    )

    # Even with a high physics setting, explicit legitimate values are untouched.
    assert compiled["player"]["speed"] == 250
    assert compiled["player"]["dash_speed"] == 600


def test_builder_parameter_compilation_arena_survival():
    """Verify Arena Survival profile configures wave count, zero gravity, and resource economy."""
    service = GameGenerationService(provider=None)

    raw_dsl = {
        "metadata": {"title": "Arena Test", "genre": "Action", "description": "Survive", "archetype": "platformer"},
        "world": {"width": 800, "height": 600, "theme": "cyberpunk", "gravity": 600, "wave_count": 1},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250},
        "entities": [{"id": "gem1", "type": "collectible", "x": 200, "y": 200}],
        "rules": [],
    }

    compiled = service._compile_and_propagate_parameters(
        dsl_dict=raw_dsl,
        spec_dict={"primary_objective": "Survive all waves"},
        engine="Arena Survival",
        art_density=30,
        physics=40,
        modules=["Resource & Score Economy", "Combat & Dash Mobility"],
    )

    # Invariant: Arena survival sets archetype survival, gravity 0, wave_count >= 3
    assert compiled["metadata"]["archetype"] == "survival"
    assert compiled["world"]["gravity"] == 0
    assert compiled["world"]["wave_count"] >= 3
    # Resource module added score rule for existing collectible
    assert any(r["trigger"] == "on_collect" and r["action"] == "add_score" for r in compiled["rules"])
    assert compiled["ui"]["show_score"] is True
