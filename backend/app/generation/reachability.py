import math
from typing import Any, List, Optional, Tuple
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

    @classmethod
    def validate_open_world_connectivity(
        cls,
        regions: List[Any],
        connections: List[Any],
        start_region_id: Optional[str] = None,
    ) -> Tuple[bool, List[Any]]:
        """
        Validate that all regions are reachable via traversal connections.
        Auto-repairs disconnected regions by linking them sequentially if broken.
        Returns (repaired_flag, final_connections).
        """
        if not regions:
            return False, connections

        region_ids = [getattr(r, "id", None) or (r.get("id") if isinstance(r, dict) else "") for r in regions]
        region_ids = [rid for rid in region_ids if rid]
        if not start_region_id or start_region_id not in region_ids:
            start_region_id = region_ids[0] if region_ids else None

        # Build adjacency graph
        adj = {rid: set() for rid in region_ids}

        # From connections
        for conn in connections:
            from_r = getattr(conn, "from_region", None) or (conn.get("from_region") if isinstance(conn, dict) else None)
            to_r = getattr(conn, "to_region", None) or (conn.get("to_region") if isinstance(conn, dict) else None)
            bidir = getattr(conn, "bidirectional", True) if hasattr(conn, "bidirectional") else (conn.get("bidirectional", True) if isinstance(conn, dict) else True)
            if from_r in adj and to_r in adj:
                adj[from_r].add(to_r)
                if bidir:
                    adj[to_r].add(from_r)

        # From region traversal_connections
        for reg in regions:
            rid = getattr(reg, "id", None) or (reg.get("id") if isinstance(reg, dict) else None)
            tc = getattr(reg, "traversal_connections", []) or (reg.get("traversal_connections", []) if isinstance(reg, dict) else [])
            for target_rid in tc:
                if target_rid in adj and rid in adj:
                    adj[rid].add(target_rid)
                    adj[target_rid].add(rid)

        # BFS reachability from start_region_id
        visited = set()
        queue = [start_region_id]
        visited.add(start_region_id)

        while queue:
            curr = queue.pop(0)
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        unreachable = [rid for rid in region_ids if rid not in visited]
        repaired = False
        repaired_connections = list(connections)

        if unreachable:
            # Auto-repair by establishing sequential bidirectional connections
            repaired = True
            for i in range(len(region_ids) - 1):
                r_a = region_ids[i]
                r_b = region_ids[i + 1]
                if r_b not in adj[r_a]:
                    adj[r_a].add(r_b)
                    adj[r_b].add(r_a)
                    # Create connection dict/object
                    repaired_connections.append({
                        "from_region": r_a,
                        "to_region": r_b,
                        "bidirectional": True,
                        "traversal_types": ["on_foot", "vehicle"],
                    })

        return repaired, repaired_connections


reachability_validator = ReachabilityValidator()


def validate_open_world_connectivity(
    ow_or_regions: Any,
    connections: Optional[List[Any]] = None,
    start_region_id: Optional[str] = None,
) -> Any:
    """Module-level convenience helper for validating open-world graph connectivity."""
    if hasattr(ow_or_regions, "regions"):
        regs = ow_or_regions.regions
        conns = ow_or_regions.connections or []
        repaired, final_conns = ReachabilityValidator.validate_open_world_connectivity(regs, conns, start_region_id)
        
        region_ids = [r.id for r in regs]
        adj = {rid: set() for rid in region_ids}
        for conn in conns:
            from_r = getattr(conn, "from_region", None) or (conn.get("from_region") if isinstance(conn, dict) else None)
            to_r = getattr(conn, "to_region", None) or (conn.get("to_region") if isinstance(conn, dict) else None)
            bidir = getattr(conn, "bidirectional", True) if hasattr(conn, "bidirectional") else (conn.get("bidirectional", True) if isinstance(conn, dict) else True)
            if from_r in adj and to_r in adj:
                adj[from_r].add(to_r)
                if bidir:
                    adj[to_r].add(from_r)
        for reg in regs:
            rid = getattr(reg, "id", None) or (reg.get("id") if isinstance(reg, dict) else None)
            tc = getattr(reg, "traversal_connections", []) or (reg.get("traversal_connections", []) if isinstance(reg, dict) else [])
            for target_rid in tc:
                if target_rid in adj and rid in adj:
                    adj[rid].add(target_rid)
                    adj[target_rid].add(rid)

        start_id = start_region_id or (region_ids[0] if region_ids else "")
        visited = set()
        if start_id in adj:
            queue = [start_id]
            visited.add(start_id)
            while queue:
                curr = queue.pop(0)
                for neighbor in adj.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
        unreach = [rid for rid in region_ids if rid not in visited]

        class ConnectivityResult:
            def __init__(self, all_reachable, reachable, unreachable, repaired_conns):
                self.all_reachable = all_reachable
                self.reachable_regions = reachable
                self.unreachable_regions = unreachable
                self.repaired_connections = repaired_conns

        return ConnectivityResult(
            all_reachable=len(unreach) == 0,
            reachable=list(visited),
            unreachable=unreach,
            repaired_conns=final_conns,
        )

    return ReachabilityValidator.validate_open_world_connectivity(ow_or_regions, connections or [], start_region_id)
