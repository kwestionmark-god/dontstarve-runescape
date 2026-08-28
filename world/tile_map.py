"""
tile_map.py — Tile map data structure.

A 2D grid representing the world. Each cell has biome, elevation,
and resource info. Used by the renderer and all game systems.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Tuple

from config import SHADING_STRENGTH

if TYPE_CHECKING:
    from world.biome import Biome
    from world.resource_node import ResourceNode


class Tile:
    """A single tile in the world grid."""

    __slots__ = (
        "x", "y", "biome", "elevation",
        "resource_node", "depleted", "regrow_timer",
        "terrain_color",
    )

    def __init__(
        self,
        x: int,
        y: int,
        biome: Biome | None,
        elevation: int,
    ) -> None:
        self.x = x
        self.y = y
        self.biome = biome
        self.elevation = elevation
        self.resource_node: ResourceNode | None = None
        self.depleted = False
        self.regrow_timer = 0.0  # Seconds until regrowth (0 if not regrowing)
        self.terrain_color = (128, 128, 128)  # Default grey (placeholder)

    def update(self, dt: float, regrowth_mod: float = 1.0) -> None:
        """
        Update tile state each frame.

        Handles depletion-to-regrow transition and regrowth timer countdown.

        When a resource node is depleted, this tile's regrow_timer is set
        to the node's regrow_time (from JSON). The timer counts down each
        frame, scaled by the seasonal regrowth modifier. When it reaches 0,
        the node regrows.

        Args:
            dt: Delta time in seconds.
            regrowth_mod: Seasonal regrowth multiplier (e.g. 1.5 in spring,
                0.4 in winter). Passed from TileMap.update().
        """
        # If this tile was marked regrowing, countdown
        if self.regrow_timer > 0:
            self.regrow_timer -= dt * regrowth_mod
            if self.regrow_timer <= 0:
                self.regrow_timer = 0
                if self.resource_node is not None:
                    self.resource_node.start_regrow()
                    self.depleted = False
                    return

        # If node just became depleted, start regrow timer
        if (
            self.resource_node is not None
            and self.resource_node.is_depleted
            and self.regrow_timer <= 0
        ):
            self.regrow_timer = self.resource_node.regrow_time
            self.depleted = True


class TileMap:
    """
    2D grid of tiles representing the world.

    Indexed as tiles[x][y] for column-major access.
    """

    __slots__ = ("width", "height", "tiles", "spawn_x", "spawn_y", "_season_system")

    def __init__(
        self,
        width: int,
        height: int,
        spawn_x: int,
        spawn_y: int,
    ) -> None:
        self.width = width
        self.height = height
        self.spawn_x = spawn_x
        self.spawn_y = spawn_y
        self._season_system: object | None = None

        # Build grid column-major: tiles[x][y]
        # Tiles are initialized with placeholder biome; actual biome
        # is assigned during world generation in _build_tile_grid.
        self.tiles: list[list[Tile]] = []
        for x in range(width):
            column: list[Tile] = []
            for y in range(height):
                column.append(Tile(x, y, None, 0))  # Placeholder biome
            self.tiles.append(column)

    @property
    def season_system(self) -> object | None:
        """Getter for season_system (set by bootstrap)."""
        return self._season_system

    @season_system.setter
    def season_system(self, value: object | None) -> None:
        """Setter for season_system (set by bootstrap)."""
        self._season_system = value

    def get_tile(self, x: int, y: int) -> Tile | None:
        """
        Get a tile by grid coordinates.

        Returns None if coordinates are out of bounds.
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[x][y]
        return None

    def get_neighbor(self, tile: Tile, direction: str) -> Tile | None:
        """
        Get a neighboring tile.

        Args:
            tile: The base tile.
            direction: "north", "south", "east", "west".

        Returns:
            The neighboring tile, or None if out of bounds.
        """
        dx, dy = 0, 0
        if direction == "north":
            dy = -1
        elif direction == "south":
            dy = 1
        elif direction == "east":
            dx = 1
        elif direction == "west":
            dx = -1
        return self.get_tile(tile.x + dx, tile.y + dy)

    def update(self, dt: float) -> None:
        """
        Update all tiles each frame.

        Handles regrowth timers and any tile-level state changes.
        Applies seasonal regrowth modifier when a SeasonSystem is wired.
        """
        regrowth_mod = 1.0
        if self._season_system is not None:
            try:
                regrowth_mod = self._season_system.get_survival_modifiers().get("regrowth", 1.0)
            except Exception:
                pass
        for x in range(self.width):
            for y in range(self.height):
                self.tiles[x][y].update(dt, regrowth_mod)

    def get_tile_at_pixel(self, pixel_x: float, pixel_y: float, tile_size: int) -> Tile | None:
        """
        Convert pixel coordinates to a tile.

        Args:
            pixel_x: X coordinate in pixels.
            pixel_y: Y coordinate in pixels.
            tile_size: Size of each tile in pixels.

        Returns:
            The tile at the given pixel position, or None.
        """
        tx = int(pixel_x // tile_size)
        ty = int(pixel_y // tile_size)
        return self.get_tile(tx, ty)

    def get_corner_height(self, cx: int, cy: int) -> float:
        """
        Compute the interpolated height at corner (cx, cy).

        The corner sits between four tiles. Height is a weighted average
        of the elevation values of surrounding tiles using a rotationally
        symmetric kernel (12 unique tiles, no overlap).

        Kernel:
            4 center tiles (the 2x2 around corner): weight 4 each
            4 ortho neighbors (90° rotation orbit): weight 1 each
            4 diag neighbors (90° rotation orbit): weight 0.25 each

        Out-of-bounds tiles are treated as elevation 0 (cliff edge).

        Returns:
            The interpolated corner height as a float.
        """
        # Rotationally symmetric kernel around corner (cx, cy).
        # Orbit 1 (center 2x2): (-1,-1), (0,-1), (-1,0), (0,0) — weight 4
        # Orbit 2 (ortho): (-2,-1), (1,-2), (2,1), (-1,2) — weight 1
        # Orbit 3 (diag):  (-2,-2), (2,-2), (2,2), (-2,2) — weight 0.25
        kernel = [
            # Center 2x2 (the 4 corner tiles)
            (-1, -1, 4.0), (0, -1, 4.0), (-1, 0, 4.0), (0, 0, 4.0),
            # Ortho orbit (90° rotation symmetric)
            (-2, -1, 1.0), (1, -2, 1.0), (2, 1, 1.0), (-1, 2, 1.0),
            # Diag orbit (corners of square around center)
            (-2, -2, 0.25), (2, -2, 0.25), (2, 2, 0.25), (-2, 2, 0.25),
        ]

        total_weight = 0.0
        total_height = 0.0
        for dx, dy, weight in kernel:
            tx, ty = cx + dx, cy + dy
            tile = self.get_tile(tx, ty)
            if tile is not None:
                total_height += tile.elevation * weight
            total_weight += weight

        return total_height / total_weight

    def get_tile_center_height(self, x: int, y: int) -> float:
        """
        Compute the average height of the four corners of a tile.

        Convenience method for placing sprites on terrain surface.

        Returns:
            The average corner height as a float.
        """
        return (
            self.get_corner_height(x, y) +
            self.get_corner_height(x + 1, y) +
            self.get_corner_height(x, y + 1) +
            self.get_corner_height(x + 1, y + 1)
        ) / 4.0

    def get_raw_corner_elevation(self, cx: int, cy: int) -> float:
        """
        Compute the raw (non-smoothed) average elevation at corner (cx, cy).

        The corner sits between four tiles. This method averages the
        ``tile.elevation`` of those four tiles directly, without the
        Gaussian-like smoothing of ``get_corner_height()``.

        Out-of-bounds tiles are treated as elevation 0.

        Returns:
            The average raw elevation as a float.
        """
        neighbor_offsets = [(-1, -1), (0, -1), (-1, 0), (0, 0)]
        total = 0.0
        count = 0
        for dx, dy in neighbor_offsets:
            tile = self.get_tile(cx + dx, cy + dy)
            if tile is not None:
                total += tile.elevation
                count += 1
        return total / count if count > 0 else 0.0

    def compute_slope_shading(self, x: int, y: int) -> Tuple[float, float]:
        """
        Compute slope-based brightness factor and slope magnitude for a tile.

        Uses raw corner elevations to determine the gradient of the terrain
        around this tile, then computes a brightness modifier based on a
        fixed light direction from the north-west (screen-space).

        Args:
            x: Tile grid column.
            y: Tile grid row.

        Returns:
            ``(brightness_factor, slope_magnitude)`` where:
            - ``brightness_factor``: 0.75–1.25 (1.0 = no shading)
            - ``slope_magnitude``: 0.0–1.0 (steepness of the slope)
        """
        # Raw average elevation at each corner of the tile
        nw = self.get_raw_corner_elevation(x, y)
        ne = self.get_raw_corner_elevation(x + 1, y)
        sw = self.get_raw_corner_elevation(x, y + 1)
        se = self.get_raw_corner_elevation(x + 1, y + 1)

        # Slope gradient using all four corners (central difference)
        # grad_x = (east edge avg - west edge avg)
        # grad_y = (south edge avg - north edge avg)
        grad_x = (ne + se - nw - sw) / 2.0
        grad_y = (sw + se - nw - ne) / 2.0

        # Slope magnitude (0 = flat, 1+ = very steep)
        slope_mag = math.sqrt(grad_x * grad_x + grad_y * grad_y)

        # Light direction from north-west (screen-space: -1, -1)
        # Dot product of gradient with light direction
        light_dot = (-1.0 * grad_x) + (-1.0 * grad_y)

        # Normalize light response: slopes facing the light (NW) brighten,
        # slopes facing away (SE) darken. Clamp to [-SHADING_STRENGTH, +SHADING_STRENGTH] range.
        brightness = 1.0 + max(-SHADING_STRENGTH, min(SHADING_STRENGTH, light_dot * SHADING_STRENGTH * 2.0))

        return (brightness, min(slope_mag / 2.0, 1.0))

    def has_structure_nearby(
        self,
        tx: int,
        ty: int,
        search_radius: int,
        structure_resource_id: str,
    ) -> bool:
        """
        Check if a structure resource node exists near the given tile.

        Searches a square area of radius ``search_radius`` around
        ``(tx, ty)`` for a resource node matching ``structure_resource_id``.

        Args:
            tx: Tile X coordinate.
            ty: Tile Y coordinate.
            search_radius: Number of tiles to search in each direction.
            structure_resource_id: The resource_id to match (e.g. "campfire").

        Returns:
            True if a matching structure node is found within range.
        """
        for dx in range(-search_radius, search_radius + 1):
            for dy in range(-search_radius, search_radius + 1):
                nx, ny = tx + dx, ty + dy
                tile = self.get_tile(nx, ny)
                if tile is None:
                    continue
                node = tile.resource_node
                if node is not None and node.resource_id == structure_resource_id:
                    return True
        return False
