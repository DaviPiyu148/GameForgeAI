from dataclasses import dataclass, field
from typing import List, Optional
from app.generation.dsl_models import GameDSL


# Documented Capability Matrix Boundaries (V2 Expanded)
SUPPORTED_ARCHETYPES = {"survival", "shooter", "platformer", "collector", "runner", "arena"}
SUPPORTED_ENTITY_TYPES = {"enemy", "collectible", "obstacle", "platform", "hazard"}
SUPPORTED_ENTITY_BEHAVIORS = {
    "patrol",
    "chase",
    "stationary",
    "bounce",
    "float",
    "flee",
    "guard",
    "ranged_attack",
}
SUPPORTED_TRIGGERS = {
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
SUPPORTED_ACTIONS = {
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


@dataclass
class CompatibilityResult:
    """Outcome of static runtime compatibility validation."""
    compatible: bool
    archetype: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class RuntimeCompatibilityValidator:
    """
    Statically validates whether a valid GameDSL document complies with
    the Phaser 2D renderer capability matrix.
    
    Note: This validates capability compatibility only; browser execution
    and scene bootstrapping occur separately in TypeScript / Phaser.
    """

    @classmethod
    def validate(cls, dsl: GameDSL) -> CompatibilityResult:
        errors: List[str] = []
        warnings: List[str] = []

        archetype = dsl.metadata.archetype.lower()
        if archetype not in SUPPORTED_ARCHETYPES:
            errors.append(f"Unsupported archetype '{archetype}'. Supported: {sorted(list(SUPPORTED_ARCHETYPES))}")

        # World bounds validation
        if dsl.world.width < 400 or dsl.world.width > 3840:
            errors.append(f"World width {dsl.world.width} outside supported range (400-3840)")
        if dsl.world.height < 300 or dsl.world.height > 2160:
            errors.append(f"World height {dsl.world.height} outside supported range (300-2160)")

        # Platformer specific checks
        if archetype == "platformer" and dsl.world.gravity == 0:
            warnings.append("Platformer archetype configured with 0 gravity; standard platformer jumping requires gravity.")

        # Player spawn bounds
        if dsl.player.spawn_x > dsl.world.width or dsl.player.spawn_y > dsl.world.height:
            errors.append("Player spawn position exceeds world dimensions.")

        # Entity checks
        if len(dsl.entities) > 30:
            errors.append(f"Entity count ({len(dsl.entities)}) exceeds maximum capacity (30)")

        for ent in dsl.entities:
            if ent.type not in SUPPORTED_ENTITY_TYPES:
                errors.append(f"Entity '{ent.id}' has unsupported type '{ent.type}'.")
            if ent.behavior not in SUPPORTED_ENTITY_BEHAVIORS:
                errors.append(f"Entity '{ent.id}' has unsupported behavior '{ent.behavior}'.")
            if ent.x > dsl.world.width or ent.y > dsl.world.height:
                errors.append(f"Entity '{ent.id}' spawn ({ent.x}, {ent.y}) exceeds world dimensions ({dsl.world.width}, {dsl.world.height}).")

            # Behavior specific sanity checks
            if ent.behavior in {"chase", "flee", "bounce", "patrol", "guard"} and ent.speed == 0:
                warnings.append(f"Entity '{ent.id}' configured with active behavior '{ent.behavior}' but speed is 0.")
            if ent.behavior == "ranged_attack" and ent.damage == 0:
                warnings.append(f"Entity '{ent.id}' has 'ranged_attack' behavior with 0 damage.")

        # Rule checks
        if len(dsl.rules) > 20:
            errors.append(f"Rule count ({len(dsl.rules)}) exceeds maximum capacity (20)")

        for rule in dsl.rules:
            if rule.trigger not in SUPPORTED_TRIGGERS:
                errors.append(f"Rule '{rule.id}' has unsupported trigger '{rule.trigger}'.")
            if rule.action not in SUPPORTED_ACTIONS:
                errors.append(f"Rule '{rule.id}' has unsupported action '{rule.action}'.")

        # Open World capability matrix checks (Phase 6)
        if dsl.open_world:
            ow = dsl.open_world
            if len(ow.regions) < 2 or len(ow.regions) > 6:
                errors.append(f"Open world region count ({len(ow.regions)}) outside supported range (2-6).")
            if len(ow.vehicles) < 1 or len(ow.vehicles) > 10:
                errors.append(f"Open world vehicle count ({len(ow.vehicles)}) outside supported range (1-10).")

            for actor in ow.actors:
                if actor.behavior not in SUPPORTED_ENTITY_BEHAVIORS:
                    errors.append(
                        f"Actor '{actor.id}' has unsupported behavior '{actor.behavior}'. Must be in {sorted(list(SUPPORTED_ENTITY_BEHAVIORS))}."
                    )

            if ow.threat_system:
                for resp in ow.threat_system.response_units:
                    if resp.behavior not in SUPPORTED_ENTITY_BEHAVIORS:
                        errors.append(
                            f"Threat response unit has unsupported behavior '{resp.behavior}'. Must be in {sorted(list(SUPPORTED_ENTITY_BEHAVIORS))}."
                        )

        return CompatibilityResult(
            compatible=len(errors) == 0,
            archetype=archetype,
            errors=errors,
            warnings=warnings,
        )
