import pytest
from pydantic import ValidationError
from app.generation.dsl_models import (
    EntityDef,
    GameDSL,
    GameMetadata,
    PlayerDef,
    RuleDef,
    UIDef,
    WorldDef,
)
from app.generation.validator import validate_game_dsl


def get_sample_valid_dsl_dict():
    """Return a standard valid Game DSL payload."""
    return {
        "schema_version": "1.0",
        "metadata": {
            "title": "Neon Grid Runner",
            "genre": "Arcade",
            "description": "Dodge hazards and collect energy nodes in a cybernetic grid.",
            "archetype": "survival",
        },
        "world": {
            "width": 800,
            "height": 600,
            "gravity": 0,
            "background_color": "#0a0b10",
            "theme": "cyberpunk",
        },
        "player": {
            "spawn_x": 400,
            "spawn_y": 300,
            "speed": 300,
            "jump_power": 0,
            "max_health": 100,
            "width": 32,
            "height": 32,
            "color": "#00f0ff",
        },
        "entities": [
            {
                "id": "drone_1",
                "type": "enemy",
                "x": 200,
                "y": 150,
                "width": 24,
                "height": 24,
                "speed": 120,
                "health": 30,
                "behavior": "patrol",
                "color": "#ff0055",
                "points": 50,
            },
            {
                "id": "node_1",
                "type": "collectible",
                "x": 600,
                "y": 450,
                "width": 16,
                "height": 16,
                "speed": 0,
                "health": 1,
                "behavior": "float",
                "color": "#ffff00",
                "points": 100,
            },
        ],
        "rules": [
            {
                "id": "rule_collect",
                "trigger": "on_collect",
                "action": "add_score",
                "params": {"amount": 100},
            },
            {
                "id": "rule_damage",
                "trigger": "on_collide_enemy",
                "action": "damage_player",
                "params": {"amount": 25},
            },
        ],
        "ui": {
            "show_health": True,
            "show_score": True,
            "status_text": "SURVIVE THE GRID",
        },
    }


def test_valid_game_dsl_accepted():
    """Test valid Game DSL schema validation."""
    data = get_sample_valid_dsl_dict()
    result = validate_game_dsl(data)
    assert result.is_valid is True
    assert result.dsl is not None
    assert result.dsl.metadata.title == "Neon Grid Runner"
    assert result.dsl.schema_version == "1.0"
    assert len(result.dsl.entities) == 2
    assert len(result.dsl.rules) == 2


def test_missing_required_fields_rejected():
    """Test rejection when required top-level metadata or fields are missing."""
    data = get_sample_valid_dsl_dict()
    del data["metadata"]

    result = validate_game_dsl(data)
    assert result.is_valid is False
    assert any("metadata" in err for err in result.errors)


def test_out_of_range_values_rejected():
    """Test boundary validation on numeric parameters."""
    data = get_sample_valid_dsl_dict()
    # Invalid world width < 400
    data["world"]["width"] = 200
    # Invalid player speed < 10
    data["player"]["speed"] = 2

    result = validate_game_dsl(data)
    assert result.is_valid is False
    assert len(result.errors) >= 2


def test_invalid_color_format_rejected():
    """Test hex color regex enforcement."""
    data = get_sample_valid_dsl_dict()
    data["world"]["background_color"] = "darkblue"  # Non-hex string

    result = validate_game_dsl(data)
    assert result.is_valid is False
    assert any("background_color" in err for err in result.errors)


def test_unsupported_enum_values_rejected():
    """Test rejection of unsupported archetypes, themes, or triggers."""
    data = get_sample_valid_dsl_dict()
    data["metadata"]["archetype"] = "open_world_rpg"  # Unsupported
    data["rules"][0]["trigger"] = "on_teleport"       # Unsupported

    result = validate_game_dsl(data)
    assert result.is_valid is False
    assert len(result.errors) >= 2


def test_oversized_entities_array_rejected():
    """Test maximum array constraint (> 30 entities)."""
    data = get_sample_valid_dsl_dict()
    data["entities"] = [
        {
            "id": f"ent_{i}",
            "type": "enemy",
            "x": 100,
            "y": 100,
            "width": 20,
            "height": 20,
            "speed": 50,
            "health": 10,
            "behavior": "patrol",
            "color": "#ff0000",
            "points": 10,
        }
        for i in range(35)
    ]

    result = validate_game_dsl(data)
    assert result.is_valid is False
    assert any("entities" in err for err in result.errors)


def test_security_script_injection_rejected():
    """Security test: Reject executable script payloads or injection markers."""
    data = get_sample_valid_dsl_dict()
    data["metadata"]["title"] = "<script>alert('pwned')</script>"

    result = validate_game_dsl(data)
    assert result.is_valid is False
    assert any("Prohibited script" in err for err in result.errors)

    # Test javascript: in rule params
    data2 = get_sample_valid_dsl_dict()
    data2["rules"][0]["params"] = {"callback": "javascript:window.stealCookies()"}
    result2 = validate_game_dsl(data2)
    assert result2.is_valid is False


def test_forbidden_extra_fields_rejected():
    """Test that arbitrary extra fields like 'script' or 'code' are rejected."""
    data = get_sample_valid_dsl_dict()
    data["script"] = "function update() { console.log('hack'); }"

    result = validate_game_dsl(data)
    assert result.is_valid is False
    assert any("Extra inputs are not permitted" in err or "script" in err for err in result.errors)


def test_cross_field_coordinate_clamping():
    """Test player and entity position clamping when outside world bounds."""
    data = get_sample_valid_dsl_dict()
    data["world"]["width"] = 800
    data["world"]["height"] = 600
    data["player"]["spawn_x"] = 1500  # Outside world width

    result = validate_game_dsl(data)
    assert result.is_valid is True
    assert result.dsl is not None
    # Clamped to middle of world width
    assert result.dsl.player.spawn_x == 400


def test_boss_phases_out_of_range_rejected():
    """Phase 5: EntityDef.boss_phases must be within [1, 2]."""
    with pytest.raises(ValidationError):
        EntityDef(id="e_phases_low", x=10, y=10, boss_phases=0)
    with pytest.raises(ValidationError):
        EntityDef(id="e_phases_high", x=10, y=10, boss_phases=3)


def test_telegraph_ms_out_of_range_rejected():
    """Phase 5: EntityDef.telegraph_ms must be within [0, 2000]."""
    with pytest.raises(ValidationError):
        EntityDef(id="e_telegraph_low", x=10, y=10, telegraph_ms=-1)
    with pytest.raises(ValidationError):
        EntityDef(id="e_telegraph_high", x=10, y=10, telegraph_ms=2001)
