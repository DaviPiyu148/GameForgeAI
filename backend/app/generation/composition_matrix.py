"""
Canonical Cross-System Composition Matrix (Generation Quality V3).

Defines the single source of truth for supported cross-system interactions in GameForge AI.
Co-existence of objects alone is strictly insufficient; an actual supported data or rule
relationship must link them. This matrix is shared across prompt generation, requirement
coverage verification, and depth evaluation.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class SupportedInteraction:
    """Defines a verified relationship between two subsystems in Phaser Arcade 2D."""
    interaction_id: str
    system_a: str
    system_b: str
    relationship_type: str
    description: str
    required_condition: str


SUPPORTED_INTERACTIONS: Dict[str, SupportedInteraction] = {
    "VEHICLE_TO_TRAVERSAL": SupportedInteraction(
        interaction_id="VEHICLE_TO_TRAVERSAL",
        system_a="Vehicles",
        system_b="World Traversal",
        relationship_type="VEHICLE_TO_TRAVERSAL",
        description="Vehicles provide higher speed (max_speed > player.speed) across large open-world districts (width/height >= 1000px).",
        required_condition="vehicle.max_speed > player.speed AND any region dimensions >= 1000",
    ),
    "THREAT_TO_ACTIVITY": SupportedInteraction(
        interaction_id="THREAT_TO_ACTIVITY",
        system_a="Threat System",
        system_b="Activities & Combat",
        relationship_type="THREAT_TO_ACTIVITY",
        description="Hostile activity completion or combat engagements escalate district threat/alert levels.",
        required_condition="activity type in ('combat', 'courier', 'delivery', 'investigation') OR rules with 'threat' / 'screen_shake'",
    ),
    "FACTION_TO_ACTIVITY": SupportedInteraction(
        interaction_id="FACTION_TO_ACTIVITY",
        system_a="Factions",
        system_b="Activities & Missions",
        relationship_type="FACTION_TO_ACTIVITY",
        description="Open-world activities or missions directly name or target registered factions.",
        required_condition="activity.title or activity.description contains faction name",
    ),
    "COLLECTIBLE_TO_OBJECTIVE": SupportedInteraction(
        interaction_id="COLLECTIBLE_TO_OBJECTIVE",
        system_a="Collectibles",
        system_b="Objectives & Rules",
        relationship_type="COLLECTIBLE_TO_OBJECTIVE",
        description="Gathering collectibles advances score or triggers objective stage completion.",
        required_condition="rule with trigger='on_collect' AND action in ('add_score', 'win_game', 'heal_player')",
    ),
    "POI_TO_ACTIVITY": SupportedInteraction(
        interaction_id="POI_TO_ACTIVITY",
        system_a="POIs",
        system_b="Activities",
        relationship_type="POI_TO_ACTIVITY",
        description="POIs anchor activities via activity_ids references or shared region coordinates.",
        required_condition="poi.activity_ids non-empty OR poi type in ('terminal', 'mission_giver', 'garage', 'outpost')",
    ),
    "WORLD_EVENT_TO_THREAT": SupportedInteraction(
        interaction_id="WORLD_EVENT_TO_THREAT",
        system_a="World Events",
        system_b="Threat System",
        relationship_type="WORLD_EVENT_TO_THREAT",
        description="Active environmental world events mutate district threat conditions or trigger reinforcement sweeps.",
        required_condition="world_event present AND threat_system present",
    ),
    "COMBAT_TO_PROGRESSION": SupportedInteraction(
        interaction_id="COMBAT_TO_PROGRESSION",
        system_a="Combat",
        system_b="Rules & Progression",
        relationship_type="COMBAT_TO_PROGRESSION",
        description="Defeating enemies rewards score or unlocks level exit/boss resolution.",
        required_condition="rule with trigger='on_enemy_defeat' OR objective.type in ('defeat_all', 'score_target')",
    ),
}


def get_required_interactions_for_contract(
    has_vehicles: bool = False,
    has_threat: bool = False,
    has_factions: bool = False,
    has_activities: bool = False,
    has_collectibles: bool = False,
    has_pois: bool = False,
    has_events: bool = False,
) -> List[SupportedInteraction]:
    """Returns the list of cross-system interactions that must be verified if features are active."""
    required = []
    if has_vehicles:
        required.append(SUPPORTED_INTERACTIONS["VEHICLE_TO_TRAVERSAL"])
    if has_threat and (has_activities or True):
        required.append(SUPPORTED_INTERACTIONS["THREAT_TO_ACTIVITY"])
    if has_factions and has_activities:
        required.append(SUPPORTED_INTERACTIONS["FACTION_TO_ACTIVITY"])
    if has_collectibles:
        required.append(SUPPORTED_INTERACTIONS["COLLECTIBLE_TO_OBJECTIVE"])
    if has_pois and has_activities:
        required.append(SUPPORTED_INTERACTIONS["POI_TO_ACTIVITY"])
    if has_events and has_threat:
        required.append(SUPPORTED_INTERACTIONS["WORLD_EVENT_TO_THREAT"])
    return required


from enum import Enum

class UsageTier(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    PASSIVE = "PASSIVE"
    DEAD = "DEAD"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class SystemUsageDefinition:
    """Canonical contract defining what constitutes real usage for a system."""
    system: str
    runtime_owner: str
    minimum_real_usage: str
    valid_interactions: List[str]
    player_facing_consequence: str


SYSTEM_USAGE_DEFINITIONS: Dict[str, SystemUsageDefinition] = {
    "Vehicles": SystemUsageDefinition(
        system="Vehicles",
        runtime_owner="VehicleManager",
        minimum_real_usage="Vehicle provides higher speed than on-foot player across large district dimensions (>= 1000px).",
        valid_interactions=["VEHICLE_TO_TRAVERSAL", "VEHICLE_ESCAPE"],
        player_facing_consequence="Player traverses distant POIs or escapes hostile pursuit at speeds unattainable on foot.",
    ),
    "Factions": SystemUsageDefinition(
        system="Factions",
        runtime_owner="FactionManager",
        minimum_real_usage="Factions are explicitly named in activities or provide contextual mission objectives.",
        valid_interactions=["FACTION_TO_ACTIVITY"],
        player_facing_consequence="Player confronts or aids distinct factions in territorial operations.",
    ),
    "Threat": SystemUsageDefinition(
        system="Threat System",
        runtime_owner="ThreatManager",
        minimum_real_usage="Hostile actions escalate alert level and dispatch reinforcement units.",
        valid_interactions=["THREAT_TO_ACTIVITY", "WORLD_EVENT_TO_THREAT"],
        player_facing_consequence="Player observes escalating response units and audible/visual tension as alert levels climb.",
    ),
    "Activities": SystemUsageDefinition(
        system="Activities",
        runtime_owner="ActivityManager",
        minimum_real_usage="Activities anchor to specific POIs with distinct delivery, combat, or investigation objectives.",
        valid_interactions=["POI_TO_ACTIVITY", "FACTION_TO_ACTIVITY"],
        player_facing_consequence="Player accepts and completes localized missions rewarding score and progressing world state.",
    ),
    "POIs": SystemUsageDefinition(
        system="POIs",
        runtime_owner="RegionManager",
        minimum_real_usage="POIs anchor activities, serve as garage vehicle spawns, or act as goal extraction terminals.",
        valid_interactions=["POI_TO_ACTIVITY"],
        player_facing_consequence="Player navigates toward recognizable stations with interactive gameplay prompts.",
    ),
    "World Events": SystemUsageDefinition(
        system="World Events",
        runtime_owner="WorldEventManager",
        minimum_real_usage="Events trigger visible alert banners, environmental state changes, or threat modifications.",
        valid_interactions=["WORLD_EVENT_TO_THREAT"],
        player_facing_consequence="Player must adapt to sudden environmental emergencies like city lockdowns or storms.",
    ),
    "Boss Finale": SystemUsageDefinition(
        system="Boss Finale",
        runtime_owner="GameScene",
        minimum_real_usage="Final level features an entity with is_boss=True, health >= 150, and multi-phase threshold.",
        valid_interactions=["COMBAT_TO_PROGRESSION"],
        player_facing_consequence="Player faces a climax encounter featuring distinct silhouettes, high health, and phase shifts.",
    ),
}


# Valid runtime trigger emitters supported by GameScene and managers
SUPPORTED_RUNTIME_TRIGGERS: Set[str] = {
    "on_collect",
    "on_collide_enemy",
    "on_reach_goal",
    "on_score_target",
    "on_time_limit",
    "on_player_death",
    "on_wave_start",
    "on_dash",
    "on_hazard_touch",
    "on_enemy_defeat",
    "on_checkpoint",
    "on_powerup_expire",
}

# Valid runtime action handlers supported by GameScene
SUPPORTED_RUNTIME_ACTIONS: Set[str] = {
    "add_score",
    "damage_player",
    "heal_player",
    "win_game",
    "lose_game",
    "spawn_entity",
    "speed_boost",
    "trigger_screen_shake",
    "spawn_wave",
    "grant_powerup",
    "activate_checkpoint",
    "spawn_particles",
    "knockback_target",
}


def validate_rule_liveness(rule_def: Any) -> Tuple[bool, Optional[str]]:
    """
    Validates whether a generated RuleDef is live (emittable and executable).
    Returns (is_live, dead_reason).
    """
    trigger = getattr(rule_def, "trigger", "")
    action = getattr(rule_def, "action", "")

    if trigger not in SUPPORTED_RUNTIME_TRIGGERS:
        return False, f"Trigger '{trigger}' is never emitted by runtime."

    if action not in SUPPORTED_RUNTIME_ACTIONS:
        return False, f"Action '{action}' has no executable runtime handler."

    # Validate target parameters for specific actions
    params = getattr(rule_def, "params", {}) or {}
    if action == "grant_powerup" and "type" not in params:
        return False, "Action 'grant_powerup' missing required 'type' param."

    if action == "activate_checkpoint" and "id" not in params and "checkpoint_id" not in params:
        return False, "Action 'activate_checkpoint' missing required 'id' param."

    return True, None

