import pytest
from app.generation.dsl_models import GameDSL, PlayerDef, EntityDef, RuleDef, WorldDef, UIDef, GameMetadata
from app.generation.validator import validate_game_dsl
from app.runtime.compatibility import RuntimeCompatibilityValidator


def test_v2_expanded_primitives_validation():
    dsl_dict = {
        "schema_version": "1.0",
        "metadata": {
            "title": "V2 Arena Test",
            "genre": "Action",
            "description": "Testing V2 expanded mechanics",
            "archetype": "shooter",
        },
        "world": {
            "width": 1000,
            "height": 800,
            "gravity": 0,
            "background_color": "#05060a",
            "theme": "neon",
            "wave_count": 4,
            "difficulty_scaling": 1.2,
        },
        "player": {
            "spawn_x": 500,
            "spawn_y": 400,
            "speed": 280,
            "max_health": 120,
            "dash_speed": 650,
            "dash_cooldown": 1.0,
            "stamina": 120,
            "attack_type": "ranged",
            "attack_damage": 30,
            "color": "#00f0ff",
            "weapon_color": "#ffea00",
        },
        "entities": [
            {
                "id": "turret_1",
                "type": "enemy",
                "x": 200,
                "y": 200,
                "width": 28,
                "height": 28,
                "speed": 80,
                "health": 40,
                "behavior": "ranged_attack",
                "damage": 15,
                "fire_rate": 2.0,
                "color": "#ff0055",
                "points": 100,
            },
            {
                "id": "crystal_1",
                "type": "collectible",
                "x": 700,
                "y": 600,
                "width": 20,
                "height": 20,
                "speed": 0,
                "health": 1,
                "behavior": "float",
                "color": "#00ffcc",
                "points": 50,
            },
        ],
        "rules": [
            {
                "id": "r_dash_feedback",
                "trigger": "on_dash",
                "action": "trigger_screen_shake",
                "params": {"intensity": 0.005},
            },
            {
                "id": "r_collect_score",
                "trigger": "on_collect",
                "action": "add_score",
                "params": {"amount": 50},
            },
            {
                "id": "r_enemy_hit",
                "trigger": "on_collide_enemy",
                "action": "damage_player",
                "params": {"damage": 15},
            },
        ],
        "ui": {
            "show_health": True,
            "show_score": True,
            "show_stamina": True,
            "show_wave": True,
            "status_text": "PROTOTYPE LIVE",
        },
    }

    val_res = validate_game_dsl(dsl_dict)
    assert val_res.is_valid is True
    assert val_res.dsl is not None
    assert val_res.dsl.player.dash_speed == 650
    assert val_res.dsl.entities[0].behavior == "ranged_attack"

    compat_res = RuntimeCompatibilityValidator.validate(val_res.dsl)
    assert compat_res.compatible is True


def test_backward_compatibility_with_v1_dsl():
    v1_minimal = {
        "metadata": {
            "title": "V1 Minimal",
            "genre": "Classic",
            "description": "Minimal v1 payload without v2 extra fields",
            "archetype": "survival",
        },
        "player": {
            "spawn_x": 100,
            "spawn_y": 100,
            "speed": 200,
        },
    }

    val_res = validate_game_dsl(v1_minimal)
    assert val_res.is_valid is True
    assert val_res.dsl is not None
    # Check default fallbacks are populated safely
    assert val_res.dsl.player.dash_speed == 600
    assert val_res.dsl.world.theme == "neon"
    assert val_res.dsl.world.width == 800
