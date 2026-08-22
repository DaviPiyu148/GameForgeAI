from typing import Callable, List, Optional, Tuple

from app.generation.dsl_models import EntityDef, GameDSL, RuleDef
from app.schemas.blueprint import BlueprintObjective, GameBlueprint
from app.schemas.design_spec import GameDesignSpec

# Mechanic name -> predicate(dsl). A mechanic only appears in a blueprint's
# `supported_mechanics` when its predicate is true against the ACTUAL validated
# DSL -- this is the enforcement mechanism for the "never display a capability the
# runtime can't back" guarantee. Deliberately absent: "Vehicles", "Boss Fights",
# "Wanted System" -- those runtime capabilities don't exist until later phases of
# the roadmap (Phase 5 boss/finale, Phase 6 living-world vehicles/wanted).
_MECHANIC_PREDICATES: List[Tuple[str, Callable[[GameDSL], bool]]] = [
    ("Dash Mobility", lambda dsl: dsl.player.dash_speed > 0),
    ("Ranged Combat", lambda dsl: dsl.player.attack_type == "ranged"),
    ("Melee Combat", lambda dsl: dsl.player.attack_type == "melee"),
    ("Area Attack", lambda dsl: dsl.player.attack_type == "aoe"),
    ("Wave Spawning", lambda dsl: dsl.world.wave_count > 1),
    ("Powerups", lambda dsl: any(r.action == "grant_powerup" for r in _all_rules(dsl))),
    ("Checkpoints", lambda dsl: any(r.trigger == "on_checkpoint" for r in _all_rules(dsl))),
    ("Ranged Enemies", lambda dsl: any(e.behavior == "ranged_attack" for e in _all_entities(dsl))),
    ("Patrol Enemies", lambda dsl: any(e.behavior == "patrol" for e in _all_entities(dsl))),
    ("Pursuit Enemies", lambda dsl: any(e.behavior == "chase" for e in _all_entities(dsl))),
    ("Hazards", lambda dsl: any(e.type == "hazard" for e in _all_entities(dsl))),
    ("Platforming", lambda dsl: dsl.world.gravity > 0 and dsl.player.jump_power > 0),
    ("Multi-Stage Campaign", lambda dsl: len(dsl.levels) > 1),
    # Phase 6: Generalized Open World Runtime Capabilities
    ("Open World Traversal", lambda dsl: dsl.open_world is not None and len(dsl.open_world.regions) >= 2),
    ("Ground Vehicles", lambda dsl: dsl.open_world is not None and len(dsl.open_world.vehicles) > 0),
    ("Dynamic Threat System", lambda dsl: dsl.open_world is not None and dsl.open_world.threat_system is not None),
    ("Faction Dynamics", lambda dsl: dsl.open_world is not None and len(dsl.open_world.factions) > 0),
    ("World Events", lambda dsl: dsl.open_world is not None and len(dsl.open_world.events) > 0),
    ("Scheduled NPCs", lambda dsl: dsl.open_world is not None and any(len(a.schedules) > 0 for a in dsl.open_world.actors)),
]


def _all_entities(dsl: GameDSL) -> List[EntityDef]:
    """Entities across the top-level DSL plus every level (campaign-aware)."""
    entities = list(dsl.entities)
    for lvl in dsl.levels:
        entities.extend(lvl.entities)
    return entities


def _all_rules(dsl: GameDSL) -> List[RuleDef]:
    """Rules across the top-level DSL plus every level (campaign-aware)."""
    rules = list(dsl.rules)
    for lvl in dsl.levels:
        rules.extend(lvl.rules)
    return rules


def build_game_blueprint(
    project_id: str,
    dsl: GameDSL,
    design_spec: Optional[GameDesignSpec],
) -> GameBlueprint:
    """
    Derive a nontechnical-friendly Game Blueprint purely from already-validated
    GameDesignSpec + GameDSL data. This is a computed projection, not a new source
    of truth -- every field here must be traceable to real DSL/runtime state.
    """
    levels = dsl.levels
    open_world = dsl.open_world

    if open_world and len(open_world.regions) > 0:
        level_count = len(open_world.regions)
        world_area_count = len(open_world.regions)
    elif levels:
        level_count = len(levels)
        world_area_count = len(levels)
    else:
        level_count = 1
        world_area_count = 1

    objectives: List[BlueprintObjective] = []
    if open_world and open_world.activities:
        for idx, act in enumerate(open_world.activities[:5], 1):
            objectives.append(BlueprintObjective(
                level_number=idx,
                type=act.type,
                description=f"{act.title}: {act.description}",
            ))
    elif levels:
        for lvl in levels:
            objectives.append(BlueprintObjective(
                level_number=lvl.level_number,
                type=lvl.objective.type,
                description=lvl.objective.description,
            ))
    elif design_spec and design_spec.primary_objective:
        objectives.append(BlueprintObjective(type="primary", description=design_spec.primary_objective))
        for sec in (design_spec.secondary_objectives or [])[:3]:
            objectives.append(BlueprintObjective(type="secondary", description=sec))

    progression: List[str] = []
    if open_world and open_world.factions:
        progression.append(f"Factions: {', '.join(f.name for f in open_world.factions[:3])}")
        if open_world.threat_system:
            progression.append(f"Threat system: {open_world.threat_system.name} (0-5)")
    elif design_spec and design_spec.progression_phases:
        for phase in design_spec.progression_phases:
            progression.append(f"{phase.phase}: {phase.description}")
    elif design_spec and design_spec.difficulty_curve:
        progression.append(f"Difficulty curve: {design_spec.difficulty_curve}")

    entities = _all_entities(dsl)
    enemy_entities = [e for e in entities if e.type == "enemy"]
    encounter_types_set = {e.behavior for e in enemy_entities}
    if open_world:
        for act in open_world.actors:
            if act.archetype in ("hostile", "guard", "security"):
                encounter_types_set.add(act.behavior)
    encounter_types = sorted(encounter_types_set)
    enemy_variety = len({e.id for e in enemy_entities}) + (len(open_world.actors) if open_world else 0)

    if open_world and open_world.activities:
        primary_act = next((a for a in open_world.activities if a.type == "mission"), open_world.activities[0])
        finale = f"Complete objective: {primary_act.title}"
    elif levels and len(levels) > 1:
        explicit_finale = next((lvl for lvl in levels if lvl.is_finale), None)
        finale_level = explicit_finale or levels[-1]
        finale = finale_level.completion_message or finale_level.title
    elif design_spec and design_spec.win_conditions:
        finale = design_spec.win_conditions[0]
    else:
        finale = "Complete the primary objective"

    if design_spec and design_spec.core_gameplay_loop:
        core_loop = design_spec.core_gameplay_loop
    elif design_spec and design_spec.loop_details:
        ld = design_spec.loop_details
        core_loop = f"{ld.player_action} -> {ld.progression} -> {ld.resolution}"
    elif open_world:
        core_loop = "Explore Regions -> Undertake Activities -> Navigate Factions & Threats"
    else:
        core_loop = "Explore -> Act -> Survive"

    supported_mechanics = [name for name, predicate in _MECHANIC_PREDICATES if predicate(dsl)]

    return GameBlueprint(
        project_id=project_id,
        title=dsl.metadata.title,
        genre=(design_spec.genre if design_spec else dsl.metadata.genre),
        archetype=dsl.metadata.archetype,
        player_fantasy=(design_spec.player_role if design_spec else "Player"),
        theme=(design_spec.theme if design_spec else dsl.world.theme),
        core_loop=core_loop,
        estimated_session_length=(design_spec.estimated_session_length if design_spec else "5-10 minutes" if open_world else "2-3 minutes"),
        level_count=level_count,
        world_area_count=world_area_count,
        objectives=objectives,
        progression=progression,
        encounter_types=encounter_types,
        enemy_variety=enemy_variety,
        finale=finale,
        supported_mechanics=supported_mechanics,
    )
