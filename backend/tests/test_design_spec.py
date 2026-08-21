import pytest
from app.schemas.design_spec import GameDesignSpec, check_for_script_injection
from app.ai.prompts import build_generation_prompt, build_playtest_analysis_prompt, build_improvement_prompt


def test_game_design_spec_valid():
    spec = GameDesignSpec(
        title="Neon Cyber Courier",
        elevator_pitch="Deliver contraband across dangerous rooftops while dodging hunter drones.",
        genre="Action Arcade",
        subgenre="Cyberpunk",
        theme="cyberpunk",
        visual_style="Neon high-contrast vector",
        camera="top_down",
        core_gameplay_loop="evade -> collect -> sprint -> reach beacon",
        player_role="Cyber Courier",
        primary_objective="Deliver 3 data packages to the extraction pad",
        secondary_objectives=["Avoid taking more than 50 damage"],
        player_abilities=["move", "dash", "shoot"],
        difficulty_curve="escalating",
        win_conditions=["all_packages_delivered"],
        loss_conditions=["player_health_depleted"],
        estimated_session_length="2-3 minutes",
        rationale=["Survival fits evasion theme", "Dash provides responsive dodging"],
    )
    assert spec.title == "Neon Cyber Courier"
    assert spec.theme == "cyberpunk"
    assert len(spec.rationale) == 2


def test_game_design_spec_script_injection_rejection():
    with pytest.raises(ValueError, match="Prohibited script"):
        GameDesignSpec(
            title="Safe Title",
            elevator_pitch="<script>alert(1)</script>",
            genre="Action",
            core_gameplay_loop="loop",
            player_role="Player",
            primary_objective="Win",
        )


@pytest.mark.parametrize(
    "malicious_text",
    [
        "process.env.SECRET_KEY",
        "process.exit(1)",
        "import('malicious-module')",
        "import { evil } from 'bad-package'",
        "require('child_process')",
        "javascript:alert(1)",
        "x.__proto__.polluted = true",
    ],
)
def test_script_injection_still_rejects_genuine_malicious_patterns(malicious_text):
    """The narrowed process./import regexes must still catch real JS injection shapes."""
    with pytest.raises(ValueError, match="Prohibited script"):
        GameDesignSpec(
            title="Safe Title",
            elevator_pitch=malicious_text,
            genre="Action",
            core_gameplay_loop="loop",
            player_role="Player",
            primary_objective="Win",
        )


@pytest.mark.parametrize(
    "legitimate_text",
    [
        "Master the crafting process. Then defend your base from raiders.",
        "Import ancient relics to unlock secrets of the lost city.",
        "The build process rewards patient exploration and resource management.",
        "Players must import strategy from prior runs to survive longer.",
    ],
)
def test_script_injection_no_longer_rejects_ordinary_prose(legitimate_text):
    """Regression: the narrowed process./import regexes must not false-positive on prose."""
    spec = GameDesignSpec(
        title="Safe Title",
        elevator_pitch=legitimate_text,
        genre="Action",
        core_gameplay_loop="loop",
        player_role="Player",
        primary_objective="Win",
    )
    assert spec.elevator_pitch == legitimate_text


def test_build_generation_prompt_with_parameters():
    prompt = build_generation_prompt(
        prompt="Cyberpunk drone survival",
        engine="Top-Down Action",
        art_density=85,
        physics=90,
        modules=["Combat & Dash Mobility", "Procedural Generation"],
    )
    assert "Cyberpunk drone survival" in prompt
    assert "Top-Down Action" in prompt
    assert "Rich Procedural Details" in prompt
    assert "High/Dynamic" in prompt
    assert "Combat & Dash Mobility" in prompt


def test_build_playtest_analysis_prompt():
    prompt = build_playtest_analysis_prompt(
        design_spec={"title": "Cyber Arena", "genre": "Shooter", "theme": "neon"},
        dsl={"entities": [{}, {}], "rules": [{}]},
        telemetry={"duration_seconds": 95, "score": 450, "damage_taken": 30, "outcome": "WON"},
    )
    assert "Cyber Arena" in prompt
    assert "Duration: 95s" in prompt
    assert "Score: 450" in prompt
