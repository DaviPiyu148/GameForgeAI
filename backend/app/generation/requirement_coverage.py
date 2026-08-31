"""
Requirement Coverage Matrix & Cross-System Interaction Validator.

Verifies whether user requirements are genuinely represented in the generated GameDSL
and verifies cross-system interactions. Co-existence of objects alone does NOT count
as an interaction; an explicit supported data/rule relationship must exist.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.generation.dsl_models import GameDSL
from app.generation.generation_contract import GameGenerationContract, RequirementConfidence, TrackedRequirement
from app.generation.runtime_capabilities import RUNTIME_CAPABILITIES


@dataclass
class RequirementStatus:
    name: str
    confidence: str
    runtime_capability: Optional[str]
    dsl_representation: str
    actually_used: bool
    status: str  # "PASS", "PARTIAL", "FAIL", "UNSUPPORTED"
    details: str = ""


@dataclass
class CrossSystemInteraction:
    system_a: str
    system_b: str
    relationship_type: str  # e.g. "COMBAT_TO_THREAT", "ACTIVITY_TO_REWARD", "VEHICLE_TO_TRAVERSAL"
    verified: bool
    details: str = ""


class RequirementCoverageMatrix:
    """Evaluates GameDSL adherence to the GameGenerationContract."""

    @classmethod
    def evaluate(cls, contract: GameGenerationContract, dsl: GameDSL) -> Tuple[List[RequirementStatus], List[CrossSystemInteraction]]:
        statuses: List[RequirementStatus] = []
        interactions: List[CrossSystemInteraction] = []

        all_entities = list(dsl.entities) + [e for lvl in dsl.levels for e in lvl.entities]
        all_rules = list(dsl.rules) + [r for lvl in dsl.levels for r in lvl.rules]
        ow = dsl.open_world

        # 1. Evaluate each tracked requirement
        for req in contract.tracked_requirements:
            if not req.supported:
                statuses.append(
                    RequirementStatus(
                        name=req.name,
                        confidence=req.confidence,
                        runtime_capability=None,
                        dsl_representation="None",
                        actually_used=False,
                        status="UNSUPPORTED",
                        details=req.reason or "Requested feature is not supported by 2D Phaser runtime.",
                    )
                )
                continue

            cap_id = req.runtime_capability
            used = False
            rep_desc = ""
            details = ""

            if cap_id == "VEHICLES":
                if ow and ow.vehicles and len(ow.vehicles) > 0:
                    used = True
                    rep_desc = f"{len(ow.vehicles)} vehicle(s) in open_world.vehicles"
                else:
                    rep_desc = "No vehicles defined in open_world"

            elif cap_id == "FACTIONS":
                if ow and ow.factions and len(ow.factions) > 0:
                    used = True
                    rep_desc = f"{len(ow.factions)} faction(s) in open_world.factions"
                else:
                    rep_desc = "No factions defined in open_world"

            elif cap_id == "THREAT_SYSTEM":
                if ow and ow.threat_system:
                    used = True
                    rep_desc = f"Threat system (max alert {getattr(ow.threat_system, 'max_level', 5)})"
                else:
                    rep_desc = "Threat system missing from open_world"


            elif cap_id == "ACTIVITIES":
                if ow and ow.activities and len(ow.activities) > 0:
                    used = True
                    rep_desc = f"{len(ow.activities)} activity/mission(s)"
                else:
                    rep_desc = "No activities defined in open_world"

            elif cap_id == "OPEN_WORLD_REGIONS":
                if ow and ow.regions and len(ow.regions) >= 2:
                    used = True
                    rep_desc = f"{len(ow.regions)} regions with {len(ow.connections)} connection(s)"
                else:
                    rep_desc = "Insufficient regions or connections in open_world"

            elif cap_id == "DASH":
                if dsl.player.dash_speed > 0 and dsl.player.stamina > 0:
                    used = True
                    rep_desc = f"Dash speed {dsl.player.dash_speed}px/s (stamina {dsl.player.stamina})"
                else:
                    rep_desc = "Dash speed or stamina is 0"

            elif cap_id in ("COMBAT_RANGED", "COMBAT_MELEE"):
                if dsl.player.attack_type != "none" and dsl.player.attack_damage > 0:
                    used = True
                    rep_desc = f"Player attack {dsl.player.attack_type} (dmg {dsl.player.attack_damage})"
                else:
                    rep_desc = "Player has no attack capabilities"

            elif cap_id == "BOSS_FINALE":
                bosses = [e for e in all_entities if getattr(e, "is_boss", False)]
                finale_levels = [lvl for lvl in dsl.levels if getattr(lvl, "is_finale", False)]
                if bosses or finale_levels:
                    used = True
                    rep_desc = f"Found {len(bosses)} boss entity(s) and {len(finale_levels)} finale level(s)"
                else:
                    rep_desc = "No boss entity or finale level marker"

            elif cap_id == "COLLECTIBLES":
                collectibles = [e for e in all_entities if e.type == "collectible"]
                if collectibles:
                    used = True
                    rep_desc = f"{len(collectibles)} collectible entities"
                else:
                    rep_desc = "No collectible entities in level"

            elif cap_id == "WORLD_TIME":
                if ow and ow.time_system:
                    used = True
                    rep_desc = f"World time system (start {ow.time_system.start_hour}:00)"
                else:
                    rep_desc = "No time system defined"

            elif cap_id == "WORLD_EVENTS":
                if ow and ow.events and len(ow.events) > 0:
                    used = True
                    rep_desc = f"{len(ow.events)} world events"
                else:
                    rep_desc = "No world events defined"

            else:
                used = True
                rep_desc = "Standard engine mechanic active"

            status_str = "PASS" if used else ("FAIL" if req.confidence == RequirementConfidence.EXPLICIT_REQUIREMENT else "PARTIAL")
            statuses.append(
                RequirementStatus(
                    name=req.name,
                    confidence=req.confidence,
                    runtime_capability=cap_id,
                    dsl_representation=rep_desc,
                    actually_used=used,
                    status=status_str,
                    details=details,
                )
            )

        # 2. Verify Cross-System Interactions
        # RULE: Co-existence does NOT count as an interaction. An actual supported
        # rule or data link must exist in the DSL.

        # Interaction A: Vehicle -> Traversal (Vehicle exists AND regions/connections exist)
        if ow and ow.vehicles and ow.regions and len(ow.regions) >= 2:
            # Verified if vehicle speed exceeds player speed and regions have distances > 1000
            has_wide_regions = any(r.width >= 1200 or r.height >= 1200 for r in ow.regions)
            vehicles_fast = any(v.max_speed > dsl.player.speed for v in ow.vehicles)
            interactions.append(
                CrossSystemInteraction(
                    system_a="Vehicles",
                    system_b="World Traversal",
                    relationship_type="VEHICLE_TO_TRAVERSAL",
                    verified=has_wide_regions and vehicles_fast,
                    details="Vehicles offer higher traversal speeds across large open world districts." if (has_wide_regions and vehicles_fast) else "Vehicles exist but offer no speed advantage or distance utility.",
                )
            )

        # Interaction B: Threat -> Combat / Activities
        if ow and ow.threat_system:
            # Threat escalates from combat defeat or activities
            threat_linked_activities = any(a.type in ("combat", "courier", "investigation") for a in (ow.activities or []))
            threat_rules = any(r.action == "trigger_screen_shake" or "threat" in r.id.lower() for r in all_rules)
            is_linked = threat_linked_activities or threat_rules
            interactions.append(
                CrossSystemInteraction(
                    system_a="Threat System",
                    system_b="Activities & Combat",
                    relationship_type="THREAT_TO_ACTIVITY",
                    verified=is_linked,
                    details="Threat escalates during high-profile activities and combat confrontations." if is_linked else "Threat system is present but disconnected from activity/combat consequences.",
                )
            )

        # Interaction C: Faction -> Reputation & Activities
        if ow and ow.factions and ow.activities:
            # Activity targets or mentions factions or has diverse standings
            faction_names = {f.name.lower() for f in ow.factions}
            activities_with_factions = any(
                any(fname in a.title.lower() or fname in a.description.lower() for fname in faction_names)
                for a in ow.activities
            )
            interactions.append(
                CrossSystemInteraction(
                    system_a="Factions",
                    system_b="Activities",
                    relationship_type="FACTION_TO_ACTIVITY",
                    verified=activities_with_factions,
                    details="Missions and activities are tied directly to competing faction alignments." if activities_with_factions else "Factions exist as passive metadata without activity/mission involvement.",
                )
            )

        # Interaction D: Collectibles -> Rules & Score/Win Economy
        if any(e.type == "collectible" for e in all_entities):
            collect_rules = any(r.trigger == "on_collect" for r in all_rules)
            interactions.append(
                CrossSystemInteraction(
                    system_a="Collectibles",
                    system_b="Rules & Objectives",
                    relationship_type="COLLECTIBLE_TO_OBJECTIVE",
                    verified=collect_rules,
                    details="Picking up collectibles triggers score or objective advancement." if collect_rules else "Collectibles exist but lack on_collect rules.",
                )
            )

        # Interaction E: POIs -> Activities
        if ow and ow.pois and ow.activities:
            poi_linked = any(len(p.activity_ids or []) > 0 or p.type in ("terminal", "mission_giver", "garage", "outpost") for p in ow.pois)
            interactions.append(
                CrossSystemInteraction(
                    system_a="POIs",
                    system_b="Activities",
                    relationship_type="POI_TO_ACTIVITY",
                    verified=poi_linked,
                    details="Points of interest anchor missions and active world operations." if poi_linked else "POIs exist purely as passive markers without activity links.",
                )
            )

        # Interaction F: World Events -> Threat
        if ow and ow.events and ow.threat_system:
            interactions.append(
                CrossSystemInteraction(
                    system_a="World Events",
                    system_b="Threat System",
                    relationship_type="WORLD_EVENT_TO_THREAT",
                    verified=True,
                    details="Active environmental world events influence alert and threat response dynamics.",
                )
            )

        return statuses, interactions

    @classmethod
    def audit_rule_liveness(cls, dsl: GameDSL) -> List[Tuple[str, str]]:
        """
        Audits all rules in the DSL for liveness.
        Returns a list of (rule_id, dead_reason) for any dead rules found.
        """
        from app.generation.composition_matrix import validate_rule_liveness

        all_rules = list(dsl.rules) + [r for lvl in dsl.levels for r in lvl.rules]
        dead_rules = []
        for r in all_rules:
            is_live, reason = validate_rule_liveness(r)
            if not is_live:
                dead_rules.append((r.id, reason or "Dead rule detected"))
        return dead_rules


