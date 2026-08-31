"""
Centralized Runtime Capability Registry for GameForge AI.

Defines the contract of supported Phaser runtime capabilities.
The AI generation pipeline references this registry to constrain generated mechanics,
and validators reject hallucinated or unsupported mechanics.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class RuntimeCapability:
    """Canonical contract describing a Phaser runtime capability."""
    identifier: str
    name: str
    supported: bool
    runtime_owner: str  # e.g., "GameScene", "VehicleManager", "ThreatManager", etc.
    description: str
    required_dsl_fields: List[str] = field(default_factory=list)
    compatible_archetypes: List[str] = field(default_factory=list)
    incompatible_archetypes: List[str] = field(default_factory=list)
    known_limitations: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Canonical Capability Registry (Allowlist)
# ─────────────────────────────────────────────────────────────────────────────

RUNTIME_CAPABILITIES: Dict[str, RuntimeCapability] = {
    # Core Mechanics
    "MOVEMENT": RuntimeCapability(
        identifier="MOVEMENT",
        name="2D Locomotion",
        supported=True,
        runtime_owner="GameScene",
        description="Omnidirectional 2D keyboard movement with velocity and damping",
        required_dsl_fields=["player.speed", "player.spawn_x", "player.spawn_y"],
        compatible_archetypes=["survival", "shooter", "runner", "platformer", "arena", "collector"],
    ),
    "PLATFORMING_JUMP": RuntimeCapability(
        identifier="PLATFORMING_JUMP",
        name="Gravity & Vertical Jump",
        supported=True,
        runtime_owner="GameScene",
        description="Arcade physics gravity and vertical jump velocity",
        required_dsl_fields=["world.gravity", "player.jump_power"],
        compatible_archetypes=["platformer", "runner"],
        incompatible_archetypes=["survival", "arena"],
        known_limitations=["Requires world.gravity > 0 and player.jump_power > 0"],
    ),
    "DASH": RuntimeCapability(
        identifier="DASH",
        name="Dash Mobility",
        supported=True,
        runtime_owner="GameScene",
        description="High-velocity burst evasion with stamina consumption and cooldown",
        required_dsl_fields=["player.dash_speed", "player.dash_cooldown", "player.stamina"],
        compatible_archetypes=["survival", "shooter", "arena", "platformer", "collector"],
    ),
    "COMBAT_RANGED": RuntimeCapability(
        identifier="COMBAT_RANGED",
        name="Ranged Projectile Combat",
        supported=True,
        runtime_owner="GameScene",
        description="Point-and-click or directional projectile shooting",
        required_dsl_fields=["player.attack_type", "player.attack_damage", "player.attack_cooldown"],
        compatible_archetypes=["shooter", "survival", "arena"],
    ),
    "COMBAT_MELEE": RuntimeCapability(
        identifier="COMBAT_MELEE",
        name="Melee Swing Combat",
        supported=True,
        runtime_owner="GameScene",
        description="Close-quarters sweep damage hitbox",
        required_dsl_fields=["player.attack_type", "player.attack_damage"],
        compatible_archetypes=["survival", "arena", "collector", "platformer"],
    ),
    "COLLECTIBLES": RuntimeCapability(
        identifier="COLLECTIBLES",
        name="Collectible Resource Nodes",
        supported=True,
        runtime_owner="GameScene",
        description="Pickup entities granting score, stamina, or satisfying collection goals",
        required_dsl_fields=["entities[type=collectible]"],
        compatible_archetypes=["collector", "survival", "platformer", "runner", "shooter", "arena"],
    ),
    "ENEMY_WAVES": RuntimeCapability(
        identifier="ENEMY_WAVES",
        name="Escalating Enemy Waves",
        supported=True,
        runtime_owner="GameScene",
        description="Time or kill-based wave spawning with dynamic scaling",
        required_dsl_fields=["world.wave_count", "entities[type=enemy]"],
        compatible_archetypes=["survival", "arena", "shooter"],
    ),
    "BOSS_FINALE": RuntimeCapability(
        identifier="BOSS_FINALE",
        name="Multi-Phase Boss Encounter",
        supported=True,
        runtime_owner="GameScene",
        description="High-health boss with telegraph banners, attack phases, and health bar HUD",
        required_dsl_fields=["entities[is_boss=true]"],
        compatible_archetypes=["survival", "shooter", "arena", "platformer"],
        known_limitations=["Boss health must be >= 150"],
    ),
    "CAMPAIGN_LEVELS": RuntimeCapability(
        identifier="CAMPAIGN_LEVELS",
        name="Multi-Level Campaign Progression",
        supported=True,
        runtime_owner="GameScene",
        description="Sequential level progression with distinctive layouts, themes, and goals",
        required_dsl_fields=["levels"],
        compatible_archetypes=["survival", "shooter", "platformer", "arena", "collector"],
        known_limitations=["Max 5 levels per schema cap"],
    ),

    # Open World Subsystems (7 Dedicated Managers)
    "OPEN_WORLD_REGIONS": RuntimeCapability(
        identifier="OPEN_WORLD_REGIONS",
        name="Multi-District Open World Map",
        supported=True,
        runtime_owner="RegionManager",
        description="Connected districts with seamless boundary traversal and distinct danger levels",
        required_dsl_fields=["open_world.regions", "open_world.connections"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
        known_limitations=["Max 6 regions per budget ceiling"],
    ),
    "VEHICLES": RuntimeCapability(
        identifier="VEHICLES",
        name="Drivable Vehicles",
        supported=True,
        runtime_owner="VehicleManager",
        description="Mountable cars, buggies, hovercrafts with speed and handling physics",
        required_dsl_fields=["open_world.vehicles"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
        known_limitations=["Player mounts/dismounts using 'E' key in proximity"],
    ),
    "POIS": RuntimeCapability(
        identifier="POIS",
        name="Points of Interest",
        supported=True,
        runtime_owner="WorldManager",
        description="Static world landmarks: safehouses, terminals, garages, outposts",
        required_dsl_fields=["open_world.pois"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
    ),
    "ACTIVITIES": RuntimeCapability(
        identifier="ACTIVITIES",
        name="Dynamic Missions & Tasks",
        supported=True,
        runtime_owner="ActivityManager",
        description="In-world missions: deliveries, investigations, combat clears, courier runs",
        required_dsl_fields=["open_world.activities"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
    ),
    "FACTIONS": RuntimeCapability(
        identifier="FACTIONS",
        name="Faction Reputation & Hostility",
        supported=True,
        runtime_owner="FactionManager",
        description="Dynamic faction standings (-100 to +100) affecting NPC hostility",
        required_dsl_fields=["open_world.factions"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
    ),
    "THREAT_SYSTEM": RuntimeCapability(
        identifier="THREAT_SYSTEM",
        name="Escalating Threat & Alert Level",
        supported=True,
        runtime_owner="ThreatManager",
        description="Alert meter (0-5) with decay and reinforcement response units",
        required_dsl_fields=["open_world.threat_system"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
    ),
    "WORLD_TIME": RuntimeCapability(
        identifier="WORLD_TIME",
        name="Day / Night Time Cycle",
        supported=True,
        runtime_owner="WorldManager",
        description="In-game time clock and lighting progression",
        required_dsl_fields=["open_world.time_system"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
    ),
    "WORLD_EVENTS": RuntimeCapability(
        identifier="WORLD_EVENTS",
        name="Dynamic World Events",
        supported=True,
        runtime_owner="WorldEventManager",
        description="Periodic regional events (sandstorms, security sweeps, supply drops)",
        required_dsl_fields=["open_world.events"],
        compatible_archetypes=["survival", "shooter", "arena", "collector"],
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Known Unsupported Concepts Registry (Hard rejection/warning)
# ─────────────────────────────────────────────────────────────────────────────

UNSUPPORTED_CONCEPTS: Dict[str, str] = {
    "dynamic NPC memory": "The 2D Arcade runtime uses deterministic state machines; long-term LLM NPC memory is unsupported.",
    "npc memory": "Persistent conversational NPC memory is unsupported in the Phaser runtime.",
    "multiplayer": "Multiplayer networking / WebSockets are not part of the local single-player Arcade engine.",
    "3d": "The runtime is strictly 2D Arcade Physics; 3D meshes/cameras are unsupported.",
    "voice chat": "Real-time audio chat is unsupported.",
    "procedural quest generation": "Quests must be defined within the ActivityDef schema; arbitrary scripted quests are unsupported.",
    "arbitrary javascript": "Execution of arbitrary client scripts is prohibited by the GameForge security constitution.",
    "skill trees": "XP/skill tree progression graphs are not currently supported in GameDSL schemas.",
    "inventory management": "Complex grid inventory / equipment slots are unsupported; use collectibles and status flags.",
}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def get_supported_capabilities() -> Dict[str, RuntimeCapability]:
    """Return all supported runtime capabilities."""
    return {k: v for k, v in RUNTIME_CAPABILITIES.items() if v.supported}


def is_capability_supported(identifier: str) -> bool:
    """Check if a capability identifier is in the supported registry."""
    cap = RUNTIME_CAPABILITIES.get(identifier.upper())
    return cap is not None and cap.supported


def check_for_unsupported_concepts(prompt: str) -> List[Tuple[str, str]]:
    """Scan prompt for explicit requests for unsupported engine capabilities."""
    lower_prompt = prompt.lower()
    violations: List[Tuple[str, str]] = []
    for concept, reason in UNSUPPORTED_CONCEPTS.items():
        if concept in lower_prompt:
            violations.append((concept, reason))
    return violations
