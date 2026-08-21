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
        win_rules = [r for r in dsl.rules if r.action == "win_game"]
        has_collectibles = any(e.type == "collectible" for e in dsl.entities)
        has_enemies = any(e.type == "enemy" for e in dsl.entities)

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
        if not dsl.rules:
            errors.append("Game has zero interaction rules. At least 1-2 gameplay rules are required.")
        if len(dsl.rules) > 15:
            errors.append(f"Rule count ({len(dsl.rules)}) exceeds maximum safe capacity (15).")
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
