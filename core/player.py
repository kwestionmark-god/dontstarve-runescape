"""
player.py — Player entity.

Handles smooth non-grid-locked movement with sub-tile precision.
Supports both WASD/arrow key continuous movement and mouse click-to-move.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from config import PLAYER_MOVEMENT_SPEED, MAP_WIDTH, MAP_HEIGHT, TILE_SIZE

if TYPE_CHECKING:
    from typing import Tuple
    from input.input_state import InputState


class Player:
    """
    Player entity with smooth movement and sub-tile precision.

    Movement modes:
    - WASD: Continuous movement in pressed direction
    - Mouse click: Move to clicked world position (stops when reached)
    - Both modes can be used simultaneously (WASD overrides click target)

    Camera panning:
    - Arrow keys: Pan the camera view (left/right = horizontal, up/down = vertical)
    """

    __slots__ = (
        "world_x", "world_y", "speed", "target_x", "target_y",
        "moving", "is_moving", "action_system", "gear", "skill_manager",
        "recruited_npcs", "base_x", "base_y",
        "unlocked_recipes", "unlocked_gear",
    )

    def __init__(self, world_x: float, world_y: float) -> None:
        """
        Initialize player at world position.

        Args:
            world_x: Starting X coordinate in pixels (float).
            world_y: Starting Y coordinate in pixels (float).
        """
        self.world_x = world_x
        self.world_y = world_y
        self.speed = PLAYER_MOVEMENT_SPEED  # Pixels per second
        self.target_x = world_x
        self.target_y = world_y
        self.moving = False
        self.is_moving = False  # True if currently in motion
        self.action_system: "ActionSystem | None" = None
        self.gear = None
        self.recruited_npcs: list[str] = []
        self.base_x: "float | None" = None  # Base center X for recruit behavior tracking
        self.base_y: "float | None" = None  # Base center Y for recruit behavior tracking
        self.unlocked_recipes: set[str] = set()
        self.unlocked_gear: set[str] = set()

    def move_to(self, world_x: float, world_y: float) -> None:
        """
        Set a click-to-move target.

        Args:
            world_x: Target X coordinate in pixels.
            world_y: Target Y coordinate in pixels.
        """
        self.target_x = world_x
        self.target_y = world_y
        self.moving = True

    def apply_key_input(self, input_state: InputState, dt: float,
                        camera_yaw: float = 0.0) -> None:
        """
        Handle WASD keyboard movement.

        Normalizes diagonal movement to maintain constant speed.
        Movement is relative to the camera's yaw — WASD directions
        rotate with the camera so "forward" always matches the
        camera's viewing direction.

        Clamps to map bounds. Arrow keys control camera rotation
        (left/right = orbit, up/down = tilt).

        Args:
            input_state: Current input state.
            dt: Delta time in seconds.
            camera_yaw: Camera yaw in radians (0=default, π/2=rotated 90°).
                        When zero, W=S screen up, S=screen down.
                        When non-zero, W=S "up" relative to the camera's
                        rotation (the opposite direction the camera is
                        facing from the player).
        """
        dx, dy = 0.0, 0.0
        if input_state.move_up:
            dy -= 1.0
        if input_state.move_down:
            dy += 1.0
        if input_state.move_left:
            dx -= 1.0
        if input_state.move_right:
            dx += 1.0

        # Normalize diagonal movement
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            dx /= length
            dy /= length

        # Rotate movement vector by camera yaw so WASD is camera-relative.
        # The camera's yaw rotates the *view* around the player; to move
        # "forward" in camera space we rotate the input vector by -yaw
        # (the inverse rotation) so the player moves in the direction the
        # camera is looking, not in screen-space directions.
        if camera_yaw != 0.0:
            cy = math.cos(-camera_yaw)
            sy = math.sin(-camera_yaw)
            rotated_x = dx * cy - dy * sy
            rotated_y = dx * sy + dy * cy
            dx, dy = rotated_x, rotated_y

        self.world_x += dx * self.speed * dt
        self.world_y += dy * self.speed * dt

        # Clamp to map bounds
        max_x = MAP_WIDTH * TILE_SIZE
        max_y = MAP_HEIGHT * TILE_SIZE
        self.world_x = max(0.0, min(self.world_x, max_x))
        self.world_y = max(0.0, min(self.world_y, max_y))

    def update(self, dt: float) -> None:
        """
        Move toward click-to-move target position.

        Called every frame. Does nothing if not moving.
        Stops when within 2px of target.

        Args:
            dt: Delta time in seconds.
        """
        if not self.moving:
            self.is_moving = False
            return

        dx = self.target_x - self.world_x
        dy = self.target_y - self.world_y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 2.0:  # Reached target (2px tolerance)
            self.moving = False
            self.is_moving = False
            return

        # Move toward target at full speed
        dx /= distance
        dy /= distance
        self.world_x += dx * self.speed * dt
        self.world_y += dy * self.speed * dt

        # Clamp to map bounds
        max_x = MAP_WIDTH * TILE_SIZE
        max_y = MAP_HEIGHT * TILE_SIZE
        self.world_x = max(0.0, min(self.world_x, max_x))
        self.world_y = max(0.0, min(self.world_y, max_y))

        self.is_moving = True

    def get_tile_position(self) -> Tuple[int, int]:
        """
        Get the current tile position (grid coordinates).

        Returns:
            (tile_x, tile_y) in grid coordinates.
        """
        tile_size = TILE_SIZE
        return (int(self.world_x // tile_size), int(self.world_y // tile_size))

    def distance_to(self, other_x: float, other_y: float) -> float:
        """
        Calculate distance to a world position.

        Args:
            other_x: Target X coordinate.
            other_y: Target Y coordinate.

        Returns:
            Euclidean distance in pixels.
        """
        dx = self.world_x - other_x
        dy = self.world_y - other_y
        return math.sqrt(dx * dx + dy * dy)

    def is_near(self, other_x: float, other_y: float, radius: float) -> bool:
        """
        Check if player is within radius of a world position.

        Args:
            other_x: Target X coordinate.
            other_y: Target Y coordinate.
            radius: Distance threshold in pixels.

        Returns:
            True if within range.
        """
        return self.distance_to(other_x, other_y) <= radius

    def take_damage(self, amount: float) -> bool:
        """
        Apply damage to the player via the survival system.

        Args:
            amount: Damage to deal.

        Returns:
            True if the player died.
        """
        if self.action_system is not None and self.action_system.survival is not None:
            return self.action_system.survival.take_damage(amount)
        return False

    def add_recruit(self, npc_id: str) -> None:
        """Add an NPC to the player's recruited crew."""
        if npc_id not in self.recruited_npcs:
            self.recruited_npcs.append(npc_id)

    def remove_recruit(self, npc_id: str) -> None:
        """Remove an NPC from the player's recruited crew."""
        if npc_id in self.recruited_npcs:
            self.recruited_npcs.remove(npc_id)

    def set_base_position(self, x: float, y: float) -> None:
        """Set the player's base position for recruit behavior tracking."""
        self.base_x = x
        self.base_y = y

    def find_interactable_resource(
        self, world, radius: float = 128.0,
    ) -> tuple:
        """
        Find the nearest interactable resource node near the player.

        Searches the visible tile area for resource nodes that the player
        can interact with (not depleted, within range).

        Args:
            world: The TileMap to search.
            radius: Search radius in pixels.

        Returns:
            (resource_node, tile_x, tile_y, node_world_x, node_world_y)
            or (None, ...) if no interactable resource found.
        """
        if world is None:
            return (None, 0, 0, 0.0, 0.0)

        tx, ty = self.get_tile_position()
        best = None
        best_dist = radius
        tile_size = 64

        # Search in a small radius around the player
        search_radius_tiles = int(radius // tile_size) + 2

        for dx in range(-search_radius_tiles, search_radius_tiles + 1):
            for dy in range(-search_radius_tiles, search_radius_tiles + 1):
                nx, ny = tx + dx, ty + dy
                tile = world.get_tile(nx, ny)
                if tile is None:
                    continue
                node = tile.resource_node
                if node is None:
                    continue
                if node.is_depleted and node.regrow_time <= 0:
                    continue
                # Calculate center of tile
                node_x = nx * tile_size + tile_size // 2
                node_y = ny * tile_size + tile_size // 2
                dist = self.distance_to(node_x, node_y)
                if dist < best_dist:
                    best_dist = dist
                    best = (node, nx, ny, node_x, node_y)

        if best is None:
            return (None, 0, 0, 0.0, 0.0)
        return best
