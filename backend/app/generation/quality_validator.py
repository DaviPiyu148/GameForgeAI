import math
from dataclasses import dataclass, field
from typing import List, Optional
from app.generation.dsl_models import GameDSL


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

        return QualityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
