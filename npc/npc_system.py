"""
npc/npc_system.py — NPC spawning, movement, and proximity detection.

Manages NPC entities placed on the world map. Handles:
- Loading spawn points from npcs.json
- Placing NPCs at walkable tiles near spawn locations
- Movement (wander/patrol) per frame
- Proximity detection for player interaction
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, List, Optional, Tuple

from data import load_json
from npc.npc import NPC, NPCSpawnPoint
from npc.npc_types import create_npc_from_dict

if TYPE_CHECKING:
    from npc.recruitment import RecruitmentSystem

if TYPE_CHECKING:
    from world.tile_map import TileMap, Tile


class NPCSystem:
    """
    Manages NPC spawning, movement, and proximity detection.

    This is the **base NPC system** — behavior-specific logic
    (trade dialogs, patrols, quest triggers, combat responses) is
    implemented in subsequent Phase 3 tasks.

    Behavior stubs (tick returns no-op per-type for P3-S3).

    Fields:
        spawn_points: All spawn points loaded from npcs.json.
        npcs: Active NPCs placed on the world map.
        tile_map: Tile map for placement validation (walkability check).
    """

    PROXIMITY_RANGE: float = 128.0          # 2 tiles @ 64px per tile
    SPEED_MERCHANT: float = 40.0
    SPEED_QUEST_GIVER: float = 35.0
    SPEED_FACTION_LEADER: float = 50.0
    SPEED_RECRUIT: float = 45.0
    SPEED_GUARD: float = 60.0
    SPEED_TRADER: float = 55.0
    SPEED_ASSISTANT: float = 70.0
    MONSTER_EXCLUSION_RADIUS_TILES: int = 3  # Don't spawn within 3 tiles of monsters

    __slots__ = (
        "spawn_points",
        "npcs",
        "tile_map",
        "_patrol_targets",
        "game",
    )

    def __init__(self, tile_map: "TileMap") -> None:
        """
        Initialize the NPC system.

        Args:
            tile_map: The world's TileMap for placement validation.
        """
        self.spawn_points: List[NPCSpawnPoint] = []
        self.npcs: List[NPC] = []
        self.tile_map: "TileMap" = tile_map
        self._patrol_targets: dict[str, Tuple[float, float]] = {}  # npc.id → (x, y)
        self.game: object = None  # Reference to Game instance (set by Game._initialize_subsystems)
        self.load_spawn_points()

    def load_spawn_points(self) -> None:
        """
        Load spawn points from npcs.json.

        Parses the "spawn_points" array and creates NPCSpawnPoint
        instances. Called once during __init__.
        """
        data = load_json("npcs.json")
        spawn_data = data.get("spawn_points", [])
        self.spawn_points = [NPCSpawnPoint.from_dict(s) for s in spawn_data]

    def spawn_npcs(self) -> None:
        """
        Place NPCs at spawn points on walkable tiles.

        Rules:
        1. For each spawn point, find a walkable tile near the spawn coords.
        2. Convert tile coords to pixel: (tile_x * 64 + 32, tile_y * 64 + 32).
        3. Exclude tiles within 3 tiles of any monster (check combat_system.monsters).
        4. Skip spawn points that are unsafe (is_safe_zone=False) if hostile monsters
           exist within 3 tile radius.
        5. Place NPCs matching the spawn point's npc_types.
        """
        # 1. Load all NPC definitions from npcs.json
        data = load_json("npcs.json")
        npc_definitions = data.get("npcs", [])

        # 2. Group NPCs by their spawn location (tile_x, tile_y)
        npc_defs_by_position: dict[Tuple[int, int], List[NPC]] = {}
        for def_data in npc_definitions:
            npc = create_npc_from_dict(def_data)
            tx, ty = int(npc.world_x), int(npc.world_y)
            if (tx, ty) not in npc_defs_by_position:
                npc_defs_by_position[(tx, ty)] = []
            npc_defs_by_position[(tx, ty)].append(npc)

        # 3. Place each NPC at its defined position
        for (tx, ty), npcs_at_pos in npc_defs_by_position.items():
            pixel_x = tx * 64 + 32
            pixel_y = ty * 64 + 32

            # Check walkability
            tile = self.tile_map.get_tile(tx, ty)
            if not self._is_walkable_tile(tile):
                # Attempt nearest walkable neighbor (search out to radius 2)
                nearest = self._find_nearby_walkable(tx, ty)
                if nearest is not None:
                    tx, ty = nearest
                    pixel_x = tx * 64 + 32
                    pixel_y = ty * 64 + 32
                else:
                    continue  # No walkable tile found, skip

            # Check monster exclusion (3 tiles = 192px)
            if self._is_near_monster(tx, ty):
                continue

            # Place NPCs at this position
            for npc in npcs_at_pos:
                npc.world_x = pixel_x
                npc.world_y = pixel_y
                self.npcs.append(npc)

    def tick(self, dt: float) -> None:
        """
        Update all active NPCs each frame.

        For P3-S3, movement is applied (wander/patrol). Behavior-specific
        logic (trade, quest, combat) is stubbed — returns no-op.

        Patrol targets persist across frames: NPCs travel toward a
        random waypoint within their patrol area. When the NPC reaches
        its target (within 2 px tolerance), a new waypoint is picked
        to prevent "freeze" jitter that occurred when generating a
        fresh random target every tick.

        Args:
            dt: Delta time in seconds.
        """
        for npc in self.npcs:
            if not npc.is_active:
                continue

            if not hasattr(npc, "id"):
                # Backward compatibility — generate a safe key from world position
                npc.id = f"npc_{npc.world_x}_{npc.world_y}"

            # Movement: wander within patrol area or idle
            if npc.patrol_area is not None:
                npc_id = npc.id
                if npc_id not in self._patrol_targets:
                    # Pick a new target for this NPC
                    self._patrol_targets[npc_id] = self._get_random_patrol_target(npc)

                target_x, target_y = self._patrol_targets[npc_id]
                self._move_toward(npc, target_x, target_y, dt)

                # When reached, clear target so a new one is picked next tick
                dist = math.sqrt(
                    (target_x - npc.world_x) ** 2 + (target_y - npc.world_y) ** 2,
                )
                if dist < 2.0:
                    del self._patrol_targets[npc_id]
            else:
                # Idle — no movement; clean up any stale target
                npc_id = getattr(npc, "id", None)
                if npc_id and npc_id in self._patrol_targets:
                    del self._patrol_targets[npc_id]

    def check_proximity(self, player: object) -> Optional[NPC]:
        """
        Find the nearest NPC within interaction range of the player.

        Returns the closest NPC within PROXIMITY_RANGE (128px).
        Returns None if no NPC is nearby.

        Args:
            player: The player entity to check proximity against.

        Returns:
            The nearest active NPC, or None.
        """
        nearby = self.get_nearby_npcs(
            player.world_x, player.world_y, self.PROXIMITY_RANGE,
        )
        return nearby[0] if nearby else None

    def get_nearby_npcs(
        self, world_x: float, world_y: float, radius: float,
    ) -> List[NPC]:
        """
        Find all active NPCs within a radius of a world position.

        Returns the nearest NPC first (sorted by distance).

        Args:
            world_x: X coordinate.
            world_y: Y coordinate.
            radius: Search radius in pixels.

        Returns:
            List of nearby active NPCs, sorted by distance (nearest first).
        """
        result: list[Tuple[float, NPC]] = []
        for npc in self.npcs:
            if not npc.is_active:
                continue
            dx = npc.world_x - world_x
            dy = npc.world_y - world_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius:
                result.append((dist, npc))

        # Sort by distance, nearest first
        result.sort(key=lambda x: x[0])
        return [npc for _, npc in result]

    def is_any_npc_nearby(
        self, world_x: float, world_y: float, radius: float = PROXIMITY_RANGE,
    ) -> bool:
        """Check if any active NPC is within radius of a world position."""
        return len(self.get_nearby_npcs(world_x, world_y, radius)) > 0

    def tick_faction_npcs(self, dt: float) -> None:
        """
        Update faction NPC behavior via FactionSystem.

        Delegates to FactionSystem.update_faction_npc_behavior() for
        monster hunting and player hostility. Also applies faction NPC
        movement targets set by FactionSystem.

        Args:
            dt: Delta time in seconds.
        """
        if self.game is None or self.game.faction_system is None:
            return

        # Delegate behavior to FactionSystem
        self.game.faction_system.update_faction_npc_behavior(dt)

        # Apply faction NPC movement targets
        for npc in self.npcs:
            if not npc.is_active:
                continue
            if npc.npc_type != "faction_leader":
                continue
            if getattr(npc, 'is_recruited', False):
                continue

            npc_id = getattr(npc, 'npc_id', str(npc.world_x))
            movement_target = self.game.faction_system._faction_npc_movement.get(npc_id)
            if movement_target is not None:
                target_x, target_y = movement_target
                self._move_toward(npc, target_x, target_y, dt)

    def assign_npc_to_structure(
        self, npc_id: str, structure_id: str
    ) -> tuple[bool, str]:
        """
        Assign an NPC to a guard post structure.

        Delegates to BuildingSystem.assign_npc_to_structure() with a
        _game_ref back-reference so assignments propagate both ways.

        Args:
            npc_id: The NPC's unique identifier.
            structure_id: The target guard post's structure_id.

        Returns:
            (success, message) tuple.
        """
        if self.game is None or not hasattr(self.game, "building_system"):
            return (False, "Game or BuildingSystem not available.")
        building = self.game.building_system
        if building is None:
            return (False, "BuildingSystem not available.")
        # Wire back-reference so BuildingSystem can update NPC fields
        if not hasattr(building, "_game_ref"):
            building._game_ref = self.game
        return building.assign_npc_to_structure(structure_id, npc_id)

    def get_npc_structure(self, npc_id: str) -> Optional[object]:
        """
        Get the structure assigned to an NPC.

        Args:
            npc_id: The NPC's unique identifier.

        Returns:
            The assigned Structure, or None.
        """
        if self.game is None or not hasattr(self.game, "building_system"):
            return None
        building = self.game.building_system
        if building is None:
            return None
        return building.get_assigned_structure(npc_id)

    def unassign_npc(self, npc_id: str) -> tuple[bool, str]:
        """
        Unassign an NPC from any structure.

        Args:
            npc_id: The NPC's unique identifier.

        Returns:
            (success, message) tuple.
        """
        if self.game is None or not hasattr(self.game, "building_system"):
            return (False, "Game or BuildingSystem not available.")
        building = self.game.building_system
        if building is None:
            return (False, "BuildingSystem not available.")
        return building.unassign_npc(npc_id)

    def remove_dead_npc(self, npc: "NPC") -> None:
        """
        Remove a dead NPC from the active NPC list.

        Called by CombatSystem._on_npc_death() when an NPC reaches 0 HP.

        Args:
            npc: The dead NPC to remove.
        """
        if npc in self.npcs:
            self.npcs.remove(npc)

    def _move_toward(
        self, npc: NPC, target_x: float, target_y: float, dt: float,
    ) -> None:
        """
        Move an NPC toward a target position using vector normalization.

        Follows the exact pattern from Monster._move_toward in combat/monster.py:
            dx = target_x - npc.world_x
            dy = target_y - npc.world_y
            dist = sqrt(dx*dx + dy*dy)
            if dist > 0:
                npc.world_x += (dx / dist) * speed * dt
                npc.world_y += (dy / dist) * speed * dt

        Args:
            npc: The NPC to move.
            target_x: Target X coordinate.
            target_y: Target Y coordinate.
            dt: Delta time in seconds.
        """
        dx = target_x - npc.world_x
        dy = target_y - npc.world_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            speed = self._get_npc_speed(npc)
            move_x = (dx / dist) * speed * dt
            move_y = (dy / dist) * speed * dt
            npc.world_x += move_x
            npc.world_y += move_y

    def _get_npc_speed(self, npc: NPC) -> float:
        """
        Get movement speed for an NPC.

        For recruited NPCs, returns behavior-specific speed:
        - guard: 60px/s
        - trader: 55px/s
        - assistant: 70px/s
        - other recruits: 45px/s (default)

        Args:
            npc: The NPC to get speed for.

        Returns:
            Speed in pixels per second.
        """
        if npc.npc_type == "recruit" and npc.recruit_behavior:
            behavior_speeds = {
                "guard": self.SPEED_GUARD,
                "trader": self.SPEED_TRADER,
                "assistant": self.SPEED_ASSISTANT,
            }
            return behavior_speeds.get(npc.recruit_behavior, self.SPEED_RECRUIT)
        speeds = {
            "merchant": self.SPEED_MERCHANT,
            "quest_giver": self.SPEED_QUEST_GIVER,
            "faction_leader": self.SPEED_FACTION_LEADER,
            "recruit": self.SPEED_RECRUIT,
        }
        return speeds.get(npc.npc_type, 30.0)  # Default fallback

    def _is_walkable_tile(self, tile: "Tile | None") -> bool:
        """
        Check if a tile is walkable for NPC placement.

        A tile is walkable if:
        - It exists (not None)
        - It has a biome (not uninitialized)
        - It does NOT have a resource node (resources block NPC placement)

        Args:
            tile: The tile to check.

        Returns:
            True if the tile is walkable.
        """
        if tile is None:
            return False
        if tile.biome is None:
            return False
        if tile.resource_node is not None:
            return False
        return True

    def _find_nearby_walkable(
        self, tile_x: int, tile_y: int, max_radius: int = 2,
    ) -> Optional[Tuple[int, int]]:
        """
        Find the nearest walkable tile within a radius.

        Searches outward in a spiral pattern from the target tile.

        Args:
            tile_x: Center X coordinate.
            tile_y: Center Y coordinate.
            max_radius: Maximum search radius in tiles.

        Returns:
            (tile_x, tile_y) of nearest walkable tile, or None.
        """
        rng = random.Random(tile_x * 1000 + tile_y)
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        rng.shuffle(directions)

        for r in range(1, max_radius + 1):
            for dx, dy in directions:
                nx, ny = tile_x + dx * r, tile_y + dy * r
                tile = self.tile_map.get_tile(nx, ny)
                if self._is_walkable_tile(tile):
                    return (nx, ny)
        return None

    def _is_near_monster(self, tile_x: int, tile_y: int) -> bool:
        """
        Check if any monster is within MONSTER_EXCLUSION_RADIUS_TILES of a tile.

        Used to prevent NPC spawning on top of / near hostile monsters.

        Args:
            tile_x: Tile X coordinate.
            tile_y: Tile Y coordinate.

        Returns:
            True if a monster is within the exclusion radius.
        """
        game = self.game
        if game is None:
            return False
        combat_system = getattr(game, "combat_system", None)
        if combat_system is None:
            return False
        monsters = getattr(combat_system, "monsters", None)
        if not monsters:
            return False

        radius_px = self.MONSTER_EXCLUSION_RADIUS_TILES * 64
        tile_cx = tile_x * 64 + 32
        tile_cy = tile_y * 64 + 32
        limit_sq = radius_px * radius_px
        for monster in monsters:
            mx = getattr(monster, "world_x", None)
            my = getattr(monster, "world_y", None)
            if mx is None or my is None:
                continue
            dx = mx - tile_cx
            dy = my - tile_cy
            if dx * dx + dy * dy <= limit_sq:
                return True
        return False

    def _get_random_patrol_target(self, npc: NPC) -> Tuple[float, float]:
        """
        Get a random target within the NPC's patrol area.

        Args:
            npc: The NPC whose patrol area to use.

        Returns:
            (target_x, target_y) in world pixel coordinates.
        """
        if npc.patrol_area is None:
            return (npc.world_x, npc.world_y)
        min_x, min_y, max_x, max_y = npc.patrol_area
        tx = random.randint(min_x, max_x)
        ty = random.randint(min_y, max_y)
        return (tx * 64 + 32, ty * 64 + 32)
