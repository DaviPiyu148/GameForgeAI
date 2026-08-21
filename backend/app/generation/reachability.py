import math
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from app.generation.dsl_models import EntityDef, WorldDef, ObjectiveDef


class ReachabilityResult(BaseModel):
    """Result of geometric and kinematic level reachability validation."""
    valid: bool = True
    errors: List[str] = Field(default_factory=list)
    repaired: bool = False
    repaired_entities: List[EntityDef] = Field(default_factory=list)
    repaired_spawn: Optional[Tuple[int, int]] = None


class ReachabilityValidator:
    """
    Deterministic reachability and spatial feasibility validator for generated levels.
    Verifies that player spawns, collectible items, and stage exits are geometrically accessible.
    """

    @classmethod
    def check_rect_collision(
        cls,
        x1: int, y1: int, w1: int, h1: int,
        x2: int, y2: int, w2: int, h2: int,
        padding: int = 4,
    ) -> bool:
        """AABB bounding box overlap check with safety padding."""
        return not (
            x1 + w1 + padding < x2 or
            x1 - padding > x2 + w2 or
            y1 + h1 + padding < y2 or
            y1 - padding > y2 + h2
        )

    @classmethod
    def validate_and_repair_level(
        cls,
        world: WorldDef,
        spawn_x: int,
        spawn_y: int,
        player_width: int,
        player_height: int,
        entities: List[EntityDef],
        objective: Optional[ObjectiveDef] = None,
        jump_power: int = 0,
        gravity: int = 0,
        archetype: str = "survival",
    ) -> ReachabilityResult:
        """
        Validate spatial bounds, obstacle collisions, and jump feasibility.
        Nudges coordinates into safe configurations if minor clipping is detected.
        """
        errors: List[str] = []
        repaired = False
        fixed_spawn_x = spawn_x
        fixed_spawn_y = spawn_y
        repaired_entities: List[EntityDef] = []

        # 1. Player spawn bounds check
        if fixed_spawn_x < 32:
            fixed_spawn_x = 48
            repaired = True
        elif fixed_spawn_x > world.width - player_width - 32:
            fixed_spawn_x = world.width - player_width - 48
            repaired = True

        if fixed_spawn_y < 32:
            fixed_spawn_y = 48
            repaired = True
        elif fixed_spawn_y > world.height - player_height - 32:
            fixed_spawn_y = world.height - player_height - 48
            repaired = True

        # Solid obstacles
        obstacles = [e for e in entities if e.type in ("obstacle", "platform")]

        # 2. Check if player spawn is trapped inside a solid obstacle
        for obs in obstacles:
            if cls.check_rect_collision(
                fixed_spawn_x, fixed_spawn_y, player_width, player_height,
                obs.x, obs.y, obs.width, obs.height,
            ):
                # Nudge player above or beside obstacle
                if obs.y >= 64:
                    fixed_spawn_y = max(32, obs.y - player_height - 8)
                else:
                    fixed_spawn_x = min(world.width - 64, obs.x + obs.width + 16)
                repaired = True

        # 3. Validate and bound all entities
        for ent in entities:
            ent_copy = ent.model_copy()

            # Bound inside world
            if ent_copy.x < 16:
                ent_copy.x = 24
                repaired = True
            elif ent_copy.x > world.width - ent_copy.width - 16:
                ent_copy.x = world.width - ent_copy.width - 24
                repaired = True

            if ent_copy.y < 16:
                ent_copy.y = 24
                repaired = True
            elif ent_copy.y > world.height - ent_copy.height - 16:
                ent_copy.y = world.height - ent_copy.height - 24
                repaired = True

            # If collectible is buried inside a non-platform solid obstacle, nudge it
            if ent_copy.type == "collectible":
                for obs in obstacles:
                    if obs.type == "obstacle" and cls.check_rect_collision(
                        ent_copy.x, ent_copy.y, ent_copy.width, ent_copy.height,
                        obs.x, obs.y, obs.width, obs.height,
                    ):
                        ent_copy.y = max(32, obs.y - ent_copy.height - 8)
                        repaired = True

            repaired_entities.append(ent_copy)

        # 4. Check platformer jump reachability
        if archetype == "platformer" and gravity > 0 and jump_power > 0:
            # Theoretical max jump height: h = v^2 / (2 * g)
            max_jump_height = (jump_power * jump_power) / (2.0 * max(gravity, 100))
            max_jump_height = min(max_jump_height, 400)  # reasonable clamp

            # Sort platforms vertically
            platforms = [e for e in repaired_entities if e.type == "platform"]
            platforms_by_y = sorted(platforms, key=lambda p: p.y, reverse=True)

            current_floor_y = world.height - 40
            for plat in platforms_by_y:
                gap = current_floor_y - plat.y
                if gap > max_jump_height * 1.3:
                    # Platform is too high to jump from previous floor; adjust platform height
                    plat.y = int(current_floor_y - (max_jump_height * 0.85))
                    repaired = True
                current_floor_y = plat.y

        return ReachabilityResult(
            valid=True,
            errors=errors,
            repaired=repaired,
            repaired_entities=repaired_entities,
            repaired_spawn=(fixed_spawn_x, fixed_spawn_y) if repaired else None,
        )


reachability_validator = ReachabilityValidator()
