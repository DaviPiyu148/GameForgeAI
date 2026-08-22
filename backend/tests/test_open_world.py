import pytest
from app.generation.open_world_models import (
    ActivityDef,
    ActorDef,
    FactionDef,
    OpenWorldDef,
    POIDef,
    RegionDef,
    ThreatResponseUnitDef,
    ThreatSystemDef,
    VehicleDef,
    WorldConnectionDef,
    WorldEventDef,
    WorldTimeDef,
)
from app.generation.dsl_models import GameDSL, GameMetadata, PlayerDef, WorldDef, EntityDef, RuleDef, UIDef
from app.generation.reachability import validate_open_world_connectivity
from app.generation.quality_validator import GameplayQualityValidator
from app.generation.validator import validate_game_dsl
from app.runtime.compatibility import RuntimeCompatibilityValidator


def make_valid_open_world_dsl() -> dict:
    return {
        "schema_version": "2.0",
        "metadata": {
            "title": "Neon Grid Syndicate",
            "genre": "Action",
            "description": "Cyberpunk courier open world sandbox.",
            "archetype": "survival",
        },
        "world": {
            "width": 1600,
            "height": 1200,
            "theme": "cyberpunk",
            "background_color": "#0a0b14",
            "gravity": 0,
            "wave_count": 3,
            "hazard_density": 20,
            "world_mode": "open_world",
        },
        "player": {
            "spawn_x": 400,
            "spawn_y": 300,
            "speed": 260,
            "jump_power": 0,
            "max_health": 100,
            "width": 28,
            "height": 28,
            "color": "#00ffff",
            "dash_speed": 600,
            "dash_cooldown": 1.0,
            "stamina": 100,
            "attack_type": "ranged",
            "attack_damage": 25,
        },
        "entities": [
            {
                "id": "starter_gem",
                "type": "collectible",
                "x": 450,
                "y": 300,
                "width": 20,
                "height": 20,
                "speed": 0,
                "health": 1,
                "behavior": "stationary",
                "color": "#00ffcc",
                "points": 50,
            }
        ],
        "rules": [
            {
                "id": "r_col",
                "trigger": "on_collect",
                "action": "add_score",
                "params": {"amount": 50},
            }
        ],
        "ui": {
            "show_health": True,
            "show_score": True,
            "show_stamina": True,
            "show_wave": True,
            "status_text": "EXPLORE DISTRICTS",
        },
        "open_world": {
            "regions": [
                {
                    "id": "reg_downtown",
                    "name": "Neon Core",
                    "theme": "cyberpunk",
                    "width": 1600,
                    "height": 1200,
                    "danger_level": 2,
                    "controlling_faction": "fac_syndicate",
                    "traversal_connections": ["reg_slums"],
                },
                {
                    "id": "reg_slums",
                    "name": "Underbelly Slums",
                    "theme": "wasteland",
                    "width": 1600,
                    "height": 1200,
                    "danger_level": 4,
                    "controlling_faction": "fac_rebels",
                    "traversal_connections": ["reg_downtown", "reg_harbor"],
                },
                {
                    "id": "reg_harbor",
                    "name": "Orbital Harbor",
                    "theme": "space",
                    "width": 1600,
                    "height": 1200,
                    "danger_level": 7,
                    "controlling_faction": "fac_corps",
                    "traversal_connections": ["reg_slums"],
                },
            ],
            "connections": [
                {
                    "from_region": "reg_downtown",
                    "to_region": "reg_slums",
                    "bidirectional": True,
                    "traversal_types": ["on_foot", "vehicle"],
                },
                {
                    "from_region": "reg_slums",
                    "to_region": "reg_harbor",
                    "bidirectional": True,
                    "traversal_types": ["on_foot", "vehicle"],
                },
            ],
            "factions": [
                {
                    "id": "fac_syndicate",
                    "name": "Neon Syndicate",
                    "initial_reputation": 20,
                    "hostility_threshold": -30,
                    "color": "#00ffcc",
                },
                {
                    "id": "fac_rebels",
                    "name": "Data Rebels",
                    "initial_reputation": 0,
                    "hostility_threshold": -20,
                    "color": "#ff0055",
                },
                {
                    "id": "fac_corps",
                    "name": "OmniCorp Security",
                    "initial_reputation": -10,
                    "hostility_threshold": -40,
                    "color": "#ffff00",
                },
            ],
            "pois": [
                {
                    "id": "poi_garage",
                    "name": "Underground Garage",
                    "type": "garage",
                    "region_id": "reg_downtown",
                    "x": 500,
                    "y": 400,
                },
                {
                    "id": "poi_terminal",
                    "name": "Data Vault",
                    "type": "terminal",
                    "region_id": "reg_slums",
                    "x": 600,
                    "y": 700,
                },
                {
                    "id": "poi_harbor_gate",
                    "name": "Harbor Gate Station",
                    "type": "outpost",
                    "region_id": "reg_harbor",
                    "x": 800,
                    "y": 600,
                },
            ],
            "activities": [
                {
                    "id": "act_delivery_1",
                    "title": "Quantum Drive Courier",
                    "description": "Deliver data payload to the Slums vault.",
                    "type": "delivery",
                    "region_id": "reg_downtown",
                    "start_poi_id": "poi_garage",
                    "target_poi_id": "poi_terminal",
                    "status": "available",
                    "target_count": 1,
                    "rewards": {"score": 500, "credits": 200},
                    "success_consequences": {
                        "reputation_changes": {"fac_syndicate": 15, "fac_corps": -10},
                        "threat_change": 1,
                    },
                },
                {
                    "id": "act_patrol_1",
                    "title": "Slums Recon",
                    "description": "Secure the Underbelly perimeter.",
                    "type": "patrol",
                    "region_id": "reg_slums",
                    "status": "available",
                    "target_count": 3,
                },
            ],
            "vehicles": [
                {
                    "id": "veh_speeder_1",
                    "name": "Interceptor Hovercraft",
                    "type": "hovercraft",
                    "region_id": "reg_downtown",
                    "x": 520,
                    "y": 420,
                    "max_speed": 550,
                    "acceleration": 450,
                    "handling": 3.0,
                    "health": 200,
                    "color": "#00f0ff",
                }
            ],
            "actors": [
                {
                    "id": "actor_fixer_1",
                    "name": "Dexter the Fixer",
                    "archetype": "quest_giver",
                    "faction_id": "fac_syndicate",
                    "region_id": "reg_downtown",
                    "x": 460,
                    "y": 380,
                    "behavior": "stationary",
                    "color": "#00ffff",
                    "gives_activity_id": "act_delivery_1",
                },
                {
                    "id": "actor_patrol_1",
                    "name": "Slums Enforcer",
                    "archetype": "guard",
                    "faction_id": "fac_rebels",
                    "region_id": "reg_slums",
                    "x": 620,
                    "y": 720,
                    "behavior": "patrol",
                    "color": "#ff0055",
                },
            ],
            "threat_system": {
                "name": "Syndicate Alert",
                "current_level": 0,
                "max_level": 5,
                "decay_rate_per_sec": 0.05,
                "response_units": [
                    {
                        "min_threat_level": 2,
                        "archetype": "security",
                        "count": 2,
                        "behavior": "chase",
                    }
                ],
            },
            "time_system": {
                "start_hour": 14,
                "time_scale": 60.0,
                "day_night_cycle": True,
            },
            "events": [
                {
                    "id": "evt_lockdown",
                    "name": "Corpo Lockdown",
                    "type": "security_lockdown",
                    "region_ids": ["reg_slums"],
                    "duration_seconds": 60,
                    "threat_modifier": 2,
                }
            ],
        },
    }


def test_open_world_pydantic_schema_validation():
    """Test that valid open-world structure parses cleanly into Pydantic models."""
    raw = make_valid_open_world_dsl()
    dsl = GameDSL.model_validate(raw)

    assert dsl.open_world is not None
    assert len(dsl.open_world.regions) == 3
    assert len(dsl.open_world.factions) == 3
    assert len(dsl.open_world.pois) == 3
    assert len(dsl.open_world.vehicles) == 1
    assert len(dsl.open_world.actors) == 2
    assert dsl.open_world.vehicles[0].name == "Interceptor Hovercraft"
    assert dsl.open_world.vehicles[0].max_speed == 550
    assert dsl.open_world.actors[0].behavior == "stationary"
    assert dsl.open_world.actors[1].behavior == "patrol"


def test_reachability_bfs_connected_graph():
    """Test BFS reachability on a fully connected region graph."""
    raw = make_valid_open_world_dsl()
    ow = OpenWorldDef.model_validate(raw["open_world"])

    res = validate_open_world_connectivity(ow)
    assert res.all_reachable is True
    assert len(res.reachable_regions) == 3
    assert len(res.unreachable_regions) == 0


def test_reachability_bfs_disconnected_auto_repair():
    """Test that disconnected regions are detected and sequential bridge connections are generated."""
    raw = make_valid_open_world_dsl()
    # Add an isolated island region with no connections
    raw["open_world"]["regions"].append({
        "id": "reg_island",
        "name": "Isolated Outpost",
        "theme": "wasteland",
        "width": 1600,
        "height": 1200,
        "danger_level": 8,
    })
    ow = OpenWorldDef.model_validate(raw["open_world"])

    res = validate_open_world_connectivity(ow)
    assert res.all_reachable is False
    assert "reg_island" in res.unreachable_regions

    # After normalization / repair
    norm_res = validate_game_dsl(raw)
    assert norm_res.is_valid is True
    assert norm_res.dsl is not None
    assert len(norm_res.dsl.open_world.regions) == 4
    # Check that reg_island is now connected
    connected_res = validate_open_world_connectivity(norm_res.dsl.open_world)
    assert connected_res.all_reachable is True


def test_actor_unsupported_behavior_normalization():
    """Test that unsupported behavior (e.g. 'wander' or 'sleep') is normalized to supported 'patrol'."""
    raw = make_valid_open_world_dsl()
    raw["open_world"]["actors"][0]["behavior"] = "wander"

    norm_res = validate_game_dsl(raw)
    assert norm_res.is_valid is True
    assert norm_res.dsl is not None
    # Behavior must be normalized to 'patrol'
    assert norm_res.dsl.open_world.actors[0].behavior in ["patrol", "stationary", "chase", "guard"]


def test_runtime_compatibility_validator_open_world():
    """Test runtime compatibility validation for open-world games."""
    raw = make_valid_open_world_dsl()
    dsl = GameDSL.model_validate(raw)

    compat = RuntimeCompatibilityValidator.validate(dsl)
    assert compat.compatible is True
    assert len(compat.errors) == 0


def test_quality_validator_budget_enforcement():
    """Test GameplayQualityValidator enforces open world budget bounds."""
    raw = make_valid_open_world_dsl()
    dsl = GameDSL.model_validate(raw)

    q_res = GameplayQualityValidator.validate(dsl)
    assert q_res.is_valid is True
    assert len(q_res.errors) == 0


def test_cross_genre_blueprints():
    """Test cross-genre open world generation fixtures across diverse themes."""
    genres = [
        ("Fantasy Realm", "dungeon", ["Enchanted Forest", "Dragon Peak", "Elven Sanctum"]),
        ("Zombie Survival", "wasteland", ["Quarantine Zone", "Ruined Metro", "Survivor Camp"]),
        ("Sci-Fi Colony", "space", ["Dome Alpha", "Mining Sector", "Hydroponics Bay"]),
    ]

    for title, theme, region_names in genres:
        raw = make_valid_open_world_dsl()
        raw["metadata"]["title"] = title
        raw["world"]["theme"] = theme
        raw["open_world"]["regions"] = [
            {
                "id": f"reg_{i}",
                "name": name,
                "theme": theme,
                "width": 1600,
                "height": 1200,
                "danger_level": i + 1,
            }
            for i, name in enumerate(region_names)
        ]
        raw["open_world"]["connections"] = [
            {"from_region": "reg_0", "to_region": "reg_1", "bidirectional": True},
            {"from_region": "reg_1", "to_region": "reg_2", "bidirectional": True},
        ]
        # Re-link POIs, actors, vehicles to reg_0
        for p in raw["open_world"]["pois"]:
            p["region_id"] = "reg_0"
        for a in raw["open_world"]["actors"]:
            a["region_id"] = "reg_0"
        for v in raw["open_world"]["vehicles"]:
            v["region_id"] = "reg_0"

        val_res = validate_game_dsl(raw)
        assert val_res.is_valid is True, f"Failed for genre {title}: {val_res.errors}"
        compat = RuntimeCompatibilityValidator.validate(val_res.dsl)
        assert compat.compatible is True, f"Incompatible for genre {title}: {compat.errors}"
