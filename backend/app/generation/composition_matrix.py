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
