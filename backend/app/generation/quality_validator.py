import math
from dataclasses import dataclass, field
from typing import List, Optional
from app.generation.dsl_models import EntityDef, GameDSL
from app.generation.scale_tiers import get_scale_budget


@dataclass
class QualityValidationResult:
    """Result of deterministic gameplay quality validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def get_summary(self) -> str:
        if not self.errors:
            return "Gameplay quality validation passed."
        return "\n".join(f"- {e}" for e in self.errors)


class GameplayQualityValidator:
    """
    Deterministic validator that checks game design coherence, fairness,
    reachability, progression, and structural completeness before browser execution.
    """

    @classmethod
    def validate(cls, dsl: GameDSL) -> QualityValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        px = dsl.player.spawn_x
        py = dsl.player.spawn_y
        p_health = dsl.player.max_health
        p_speed = dsl.player.speed
        p_dash = dsl.player.dash_speed
        archetype = dsl.metadata.archetype.lower()

        # 1. Player Spawn Clearance
        # Ensure player is not spawned directly on top of a hazard or enemy (>= 60px)
        for ent in dsl.entities:
            dist = math.hypot(px - ent.x, py - ent.y)
            if ent.type in ("hazard", "enemy") and dist < 60:
                errors.append(
                    f"Immediate death hazard: Player spawned at ({px}, {py}) too close to {ent.type} '{ent.id}' at ({ent.x}, {ent.y}) (distance {dist:.1f}px < 60px)."
                )

        # 2. Objective & Win Condition Validation
        all_entities = list(dsl.entities) + [e for lvl in dsl.levels for e in lvl.entities]
        all_rules = list(dsl.rules) + [r for lvl in dsl.levels for r in lvl.rules]
        win_rules = [r for r in all_rules if r.action == "win_game"]
        has_collectibles = any(e.type == "collectible" for e in all_entities)
        has_enemies = any(e.type == "enemy" for e in all_entities)

        if archetype == "collector":
            if not has_collectibles:
                errors.append("Collector archetype requires at least one collectible entity in the world.")
            if not win_rules:
                warnings.append("Collector archetype has no explicit win_game rule; will clear upon collecting all items.")

        elif archetype == "platformer":
            if dsl.world.gravity <= 0:
                errors.append("Platformer archetype requires world.gravity > 0 for jump/fall mechanics.")
            if dsl.player.jump_power <= 0:
                errors.append("Platformer archetype requires player.jump_power > 0 for vertical navigation.")
            goal_win = any(r.trigger == "on_reach_goal" for r in win_rules)
            has_goal_entity = any(e.type == "collectible" and "goal" in e.id.lower() for e in dsl.entities)
            if not goal_win and not has_goal_entity and not win_rules:
                warnings.append("Platformer archetype has no on_reach_goal win condition or goal entity; recommended to place a goal exit.")

        elif archetype in ("survival", "shooter", "arena"):
            if not has_enemies and dsl.world.wave_count <= 1:
                errors.append(f"{archetype.capitalize()} archetype requires active enemy entities or wave spawning for gameplay pressure.")

        # 3. Rule Triggers & Entity Dependencies
        for rule in dsl.rules:
            if rule.trigger == "on_collect" and not has_collectibles:
                errors.append("Rule with trigger 'on_collect' exists, but no collectible entities are spawned in the world.")
            if rule.trigger == "on_collide_enemy" and not has_enemies and dsl.world.wave_count <= 1:
                warnings.append("Rule with trigger 'on_collide_enemy' exists, but no enemy entities are present.")

        # 4. Fairness and Damage Bounds
        damage_rules = [r for r in dsl.rules if r.action == "damage_player"]
        for rule in damage_rules:
            dmg = rule.params.get("damage", 15)
            if isinstance(dmg, (int, float)) and dmg >= p_health:
                warnings.append(f"High lethality: Rule '{rule.id}' deals {dmg} damage, which instantly depletes player max health ({p_health}).")

        for ent in dsl.entities:
            if ent.type == "enemy":
                if ent.damage >= p_health and p_dash == 0:
                    warnings.append(f"High lethality: Enemy '{ent.id}' deals fatal damage ({ent.damage} >= {p_health} HP) without dash mobility.")
                if ent.behavior in ("chase", "flee", "bounce", "patrol", "guard") and ent.speed == 0:
                    errors.append(f"Dead entity logic: Enemy '{ent.id}' has moving behavior '{ent.behavior}' but speed is 0.")
                if ent.behavior == "ranged_attack" and ent.fire_rate <= 0:
                    errors.append(f"Invalid combat timing: Ranged enemy '{ent.id}' has fire_rate <= 0.")

        # 5. Locomotion and Speed Balance
        for ent in dsl.entities:
            if ent.type == "enemy" and ent.speed > p_speed * 1.8 and p_dash == 0:
                warnings.append(
                    f"Enemy '{ent.id}' speed ({ent.speed}) is significantly faster than player speed ({p_speed}) without dash mobility."
                )

        # 6. Progression & Session Bounds
        if not all_rules:
            errors.append("Game has zero interaction rules. At least 1-2 gameplay rules are required.")
        if len(all_rules) > 30:
            errors.append(f"Total rule count ({len(all_rules)}) exceeds maximum safe capacity (30).")
        if dsl.world.wave_count < 1 or dsl.world.wave_count > 10:
            errors.append(f"Wave count ({dsl.world.wave_count}) outside valid range (1-10).")

        # 7. Boss Fairness & Telegraph Compatibility (Phase 5).
        # Scoped per entity list (top-level dsl.entities, then each campaign level's
        # own entities), matching how reachability validation iterates dsl.levels --
        # a boss is only compared against the OTHER enemies sharing its own level, not
        # enemies from a different level entirely.
        entity_scopes: List[List[EntityDef]] = [dsl.entities] + [lvl.entities for lvl in dsl.levels]
        for ents in entity_scopes:
            non_boss_enemy_healths = [e.health for e in ents if e.type == "enemy" and not e.is_boss]
            max_non_boss_health = max(non_boss_enemy_healths) if non_boss_enemy_healths else 0

            for ent in ents:
                if ent.is_boss:
                    # Boss must meaningfully outclass the toughest regular enemy sharing
                    # its level (>= 2x), or clear a flat 150 HP floor when it is the only
                    # enemy present. (EntityDef itself also enforces a flat >=150 floor,
                    # but that single-entity validator has no visibility into siblings --
                    # this is the scope-aware, stricter check.)
                    required_health = max(150, max_non_boss_health * 2) if non_boss_enemy_healths else 150
                    if ent.health < required_health:
                        errors.append(
                            f"Boss fairness: Boss entity '{ent.id}' has health {ent.health}, which does not "
                            f"sufficiently exceed other enemies in its level (requires >= {required_health})."
                        )

                # Telegraph is only meaningful for a discrete, timed attack event that a
                # visible wind-up window can precede -- today only 'ranged_attack'
                # behavior fires such a discrete event; other behaviors (patrol/chase/
                # stationary/bounce/float/flee/guard) have no equivalent attack beat for
                # a telegraph to announce.
                if ent.telegraph_ms > 0 and ent.behavior != "ranged_attack":
                    errors.append(
                        f"Invalid telegraph: Entity '{ent.id}' sets telegraph_ms={ent.telegraph_ms} but has "
                        f"behavior '{ent.behavior}' (telegraph_ms only applies to 'ranged_attack' behavior)."
                    )

        # 8. Open World Gameplay Validation (Phase 6)
        if dsl.open_world:
            ow = dsl.open_world
            region_ids = {r.id for r in ow.regions}
            poi_ids = {p.id for p in ow.pois}
            faction_ids = {f.id for f in ow.factions}
            activity_ids = {a.id for a in ow.activities}

            # Budget checks
            if len(ow.regions) < 2 or len(ow.regions) > 6:
                errors.append(f"Open world region count ({len(ow.regions)}) must be between 2 and 6.")
            if len(ow.connections) > 15:
                errors.append(f"Open world connection count ({len(ow.connections)}) exceeds maximum budget (15).")
            if len(ow.pois) < 3 or len(ow.pois) > 25:
                errors.append(f"Open world POI count ({len(ow.pois)}) must be between 3 and 25.")
            if len(ow.vehicles) < 1 or len(ow.vehicles) > 10:
                errors.append(f"Open world vehicle count ({len(ow.vehicles)}) must be between 1 and 10.")
            if len(ow.factions) < 1 or len(ow.factions) > 5:
                errors.append(f"Open world faction count ({len(ow.factions)}) must be between 1 and 5.")
            if len(ow.activities) < 2 or len(ow.activities) > 15:
                errors.append(f"Open world activity count ({len(ow.activities)}) must be between 2 and 15.")
            if len(ow.actors) > 50:
                errors.append(f"Open world actor count ({len(ow.actors)}) exceeds maximum budget (50).")
            if len(ow.events) > 5:
                errors.append(f"Open world event count ({len(ow.events)}) exceeds maximum budget (5).")

            # Reference integrity
            for p in ow.pois:
                if p.region_id not in region_ids:
                    errors.append(f"POI '{p.id}' references nonexistent region '{p.region_id}'.")

            for v in ow.vehicles:
                if v.region_id not in region_ids:
                    errors.append(f"Vehicle '{v.id}' references nonexistent region '{v.region_id}'.")

            for a in ow.actors:
                if a.region_id not in region_ids:
                    errors.append(f"Actor '{a.id}' references nonexistent region '{a.region_id}'.")
                if a.faction_id and a.faction_id not in faction_ids:
                    errors.append(f"Actor '{a.id}' references nonexistent faction '{a.faction_id}'.")

            for act in ow.activities:
                if act.region_id and act.region_id not in region_ids:
                    errors.append(f"Activity '{act.id}' references nonexistent region '{act.region_id}'.")
                if act.start_poi_id and act.start_poi_id not in poi_ids:
                    errors.append(f"Activity '{act.id}' references nonexistent start POI '{act.start_poi_id}'.")
                if act.target_poi_id and act.target_poi_id not in poi_ids:
                    errors.append(f"Activity '{act.id}' references nonexistent target POI '{act.target_poi_id}'.")

            has_avail_activity = any(a.status == "available" for a in ow.activities)
            if not has_avail_activity:
                warnings.append("No open world activities marked 'available' at start; player will have no active missions.")

        return QualityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def validate_scale_budget(cls, dsl: GameDSL, scale: str) -> List[str]:
        """
        Check a validated GameDSL against the requested scale tier's structural
        budget (level count, entities/level, rules/level from
        app.generation.scale_tiers.get_scale_budget). Returns a list of "below
        tier minimum" error-shaped strings.

        Deliberately floor-only: this never flags exceeding a tier's maximum --
        the hard schema ceilings (GameDSL.levels max_length=5, LevelDef.entities
        max_length=30, LevelDef.rules max_length=15) already bound that, and
        `validate()` above's own rule-count check covers the top-level ceiling.
        This method only nudges a DSL that came in UNDER a tier's target floor.

        Caller contract (see GameGenerationService.generate_game_dsl): the errors
        returned here are a soft, first-attempt-only nudge fed into the bounded
        AI repair loop -- never a hard, permanently-blocking error. A DSL that is
        still under-target after repair is accepted with the shortfall treated as
        a warning, not a build failure ("a slightly-off tier is not worth a hard
        failure").
        """
        budget = get_scale_budget(scale)
        errors: List[str] = []

        levels = dsl.levels
        level_count = len(levels) if levels else 1
        min_levels, _max_levels = budget.level_count
        if level_count < min_levels:
            errors.append(
                f"Scale tier '{scale}' expects at least {min_levels} level(s), but the generated game has {level_count}."
            )

        # A DSL with no `levels` campaign array (single-stage prototype) is
        # evaluated against its top-level entities/rules as an implicit single level.
        level_entity_lists = [lvl.entities for lvl in levels] if levels else [dsl.entities]
        level_rule_lists = [lvl.rules for lvl in levels] if levels else [dsl.rules]

        min_entities, _max_entities = budget.entities_per_level
        for idx, ents in enumerate(level_entity_lists, start=1):
            if len(ents) < min_entities:
                errors.append(
                    f"Scale tier '{scale}' expects at least {min_entities} entities in level {idx}, but it has {len(ents)}."
                )

        min_rules, _max_rules = budget.rules_per_level
        for idx, rules in enumerate(level_rule_lists, start=1):
            if len(rules) < min_rules:
                errors.append(
                    f"Scale tier '{scale}' expects at least {min_rules} rules in level {idx}, but it has {len(rules)}."
                )

        return errors
