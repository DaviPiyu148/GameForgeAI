"""
Deterministic Game Design Pattern Library (Generation Quality V3).

Defines 10 compact structural design patterns across Campaign, Open World,
Arena, Platformer, Collector, and Action archetypes. These patterns guide
structural progression, encounter escalation, and system composition without
adding extra LLM calls or complex frameworks.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DesignPattern:
    """A structural gameplay flow template governing level progression and system composition."""
    id: str
    name: str
    category: str  # "campaign", "open_world", "arena", "platformer", "collector"
    description: str
    stage_flow: List[str]
    suggested_objectives: List[str]
    suggested_behaviors: List[str]
    recommended_rules: List[str]
    finale_style: str  # "boss", "extraction", "survival_climax", "goal_beacon"


DESIGN_PATTERNS: Dict[str, DesignPattern] = {
    # ── CAMPAIGN PATTERNS ─────────────────────────────────────────────────────
    "CP_PROGRESSIVE_ESCALATION": DesignPattern(
        id="CP_PROGRESSIVE_ESCALATION",
        name="Linear Escalation Campaign",
        category="campaign",
        description="Introduction to core mechanics -> Combining mechanics -> High pressure hazard variation -> Climactic boss confrontation.",
        stage_flow=["Stage 1: Introduction", "Stage 2: Mechanic Combination", "Stage 3: Environmental Pressure", "Stage 4: Climax / Boss"],
        suggested_objectives=["collect_all", "defeat_all", "survive_time", "defeat_all"],
        suggested_behaviors=["patrol", "chase", "ranged_attack", "guard"],
        recommended_rules=["on_collect -> add_score", "on_enemy_defeat -> add_score", "on_collide_enemy -> damage_player"],
        finale_style="boss",
    ),
    "CP_COMBAT_TRAVERSAL": DesignPattern(
        id="CP_COMBAT_TRAVERSAL",
        name="Combat & Traversal Arc",
        category="campaign",
        description="Safe traversal & learning -> Hostile perimeter sweep -> Coordinated enemy skirmish -> High-threat extraction.",
        stage_flow=["Stage 1: Perimeter Sweep", "Stage 2: Skirmish", "Stage 3: Extraction Point"],
        suggested_objectives=["reach_exit", "defeat_all", "reach_exit"],
        suggested_behaviors=["patrol", "ranged_attack", "chase"],
        recommended_rules=["on_reach_goal -> activate_checkpoint", "on_collide_enemy -> damage_player"],
        finale_style="extraction",
    ),

    # ── OPEN WORLD PATTERNS ───────────────────────────────────────────────────
    "OW_ACTIVITY_ESCAPE": DesignPattern(
        id="OW_ACTIVITY_ESCAPE",
        name="District Infiltration & Pursuit Escape",
        category="open_world",
        description="District reconnaissance -> POI contract acceptance -> Faction confrontation -> High-speed vehicular escape under escalating threat.",
        stage_flow=["Recon District", "Execute Infiltration Activity", "Evade Threat Reinforcements", "Safehouse Extraction"],
        suggested_objectives=["delivery", "investigation", "combat"],
        suggested_behaviors=["patrol", "chase", "ranged_attack"],
        recommended_rules=["on_collide_enemy -> damage_player", "on_dash -> speed_boost"],
        finale_style="extraction",
    ),
    "OW_FACTION_REPUTATION": DesignPattern(
        id="OW_FACTION_REPUTATION",
        name="Faction Territory & Operations",
        category="open_world",
        description="Neutral hub exploration -> Faction contract operations -> Hostile sector incursion -> Outpost liberation.",
        stage_flow=["Hub Briefing", "Contested Zone Operation", "Rival Faction Confrontation", "Territory Milestone"],
        suggested_objectives=["delivery", "combat", "patrol"],
        suggested_behaviors=["guard", "patrol", "chase"],
        recommended_rules=["on_enemy_defeat -> add_score", "on_checkpoint -> activate_checkpoint"],
        finale_style="survival_climax",
    ),
    "OW_VEHICULAR_TRAVERSAL": DesignPattern(
        id="OW_VEHICULAR_TRAVERSAL",
        name="High-Speed Courier Highway",
        category="open_world",
        description="Vehicular traversal between distant districts -> Checkpoint milestones -> Roadblock evasion -> Final drop-off.",
        stage_flow=["Depot Departure", "High-Speed Highway Run", "Roadblock Infiltration", "Target Dropoff"],
        suggested_objectives=["delivery", "exploration", "reach_exit"],
        suggested_behaviors=["patrol", "bounce", "chase"],
        recommended_rules=["on_reach_goal -> win_game", "on_collide_enemy -> damage_player"],
        finale_style="extraction",
    ),

    # ── ARENA & SURVIVAL PATTERNS ─────────────────────────────────────────────
    "AR_WAVE_ESCALATION": DesignPattern(
        id="AR_WAVE_ESCALATION",
        name="Escalating Wave Gauntlet",
        category="arena",
        description="Early scouting wave -> Swarm harassment -> Elite ranged pressure -> Overlord climax.",
        stage_flow=["Wave 1: Scout Swarm", "Wave 2: Heavy Pursuit", "Wave 3: Ranged Barrage", "Final Wave: Overlord"],
        suggested_objectives=["survive_time", "defeat_all", "score_target"],
        suggested_behaviors=["chase", "patrol", "ranged_attack"],
        recommended_rules=["on_wave_start -> spawn_wave", "on_enemy_defeat -> add_score", "on_dash -> grant_powerup"],
        finale_style="boss",
    ),
    "AR_RESOURCE_ATTRITION": DesignPattern(
        id="AR_RESOURCE_ATTRITION",
        name="Resource Attrition Survival",
        category="arena",
        description="Constant hazard pressure -> Scavenging life energy pickups -> Tactical kiting -> Timed survival.",
        stage_flow=["Initial Containment", "Depletion Phase", "Surge Phase", "Survival Resolution"],
        suggested_objectives=["survive_time", "collect_all"],
        suggested_behaviors=["bounce", "float", "chase"],
        recommended_rules=["on_collect -> heal_player", "on_hazard_touch -> damage_player", "on_time_limit -> win_game"],
        finale_style="survival_climax",
    ),

    # ── PLATFORMER PATTERNS ───────────────────────────────────────────────────
    "PF_PRECISION_TRAVERSAL": DesignPattern(
        id="PF_PRECISION_TRAVERSAL",
        name="Precision Hazard Platforming",
        category="platformer",
        description="Basic jump cadence -> Moving obstacles & spike hazards -> Vertical ascent -> Beacon extraction.",
        stage_flow=["Stage 1: Fundamentals", "Stage 2: Moving Platforms & Hazards", "Stage 3: Vertical Ascent", "Stage 4: Summit Beacon"],
        suggested_objectives=["reach_exit", "collect_all", "reach_exit"],
        suggested_behaviors=["stationary", "bounce", "patrol"],
        recommended_rules=["on_hazard_touch -> damage_player", "on_reach_goal -> win_game"],
        finale_style="goal_beacon",
    ),

    # ── COLLECTOR PATTERNS ────────────────────────────────────────────────────
    "CO_PATROL_SWEEP": DesignPattern(
        id="CO_PATROL_SWEEP",
        name="Tactical Guardian Sweep",
        category="collector",
        description="Safe node harvesting -> Patrolling sentry evasion -> Speed-boost resource sweep -> Final vault activation.",
        stage_flow=["Outer Perimeter", "Guarded Vault", "Core Chamber"],
        suggested_objectives=["collect_all", "score_target", "reach_exit"],
        suggested_behaviors=["patrol", "float", "guard"],
        recommended_rules=["on_collect -> add_score", "on_score_target -> win_game"],
        finale_style="goal_beacon",
    ),
}


def select_design_pattern(
    archetype: str,
    world_mode: str,
    scale: str,
    has_vehicles: bool = False,
    has_factions: bool = False,
    has_threat: bool = False,
) -> DesignPattern:
    """
    Deterministically selects the most fitting structural design pattern
    based on archetype, world mode, scale, and active capability requirements.
    """
    arch = archetype.lower()
    mode = world_mode.lower()

    if mode == "open_world":
        if has_vehicles and (has_threat or has_factions):
            return DESIGN_PATTERNS["OW_ACTIVITY_ESCAPE"]
        if has_vehicles:
            return DESIGN_PATTERNS["OW_VEHICULAR_TRAVERSAL"]
        if has_factions:
            return DESIGN_PATTERNS["OW_FACTION_REPUTATION"]
        return DESIGN_PATTERNS["OW_ACTIVITY_ESCAPE"]

    if arch == "platformer":
        return DESIGN_PATTERNS["PF_PRECISION_TRAVERSAL"]

    if arch == "collector":
        return DESIGN_PATTERNS["CO_PATROL_SWEEP"]

    if arch == "arena" or (arch == "survival" and scale == "prototype"):
        return DESIGN_PATTERNS["AR_WAVE_ESCALATION"]

    # Campaign & multi-level action/shooter/survival
    if scale in ("standard", "campaign"):
        if arch in ("shooter", "survival"):
            return DESIGN_PATTERNS["CP_PROGRESSIVE_ESCALATION"]
        return DESIGN_PATTERNS["CP_COMBAT_TRAVERSAL"]

    return DESIGN_PATTERNS["CP_PROGRESSIVE_ESCALATION"]
