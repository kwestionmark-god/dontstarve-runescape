"""
tile_map.py — Tile map data structure.

A 2D grid representing the world. Each cell has biome, elevation,
and resource info. Used by the renderer and all game systems.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Tuple

import numpy as np

from config import FOG_SCALE_HEIGHT, SHADING_STRENGTH

if TYPE_CHECKING:
    from world.biome import Biome
    from world.resource_node import ResourceNode


class Tile:
    """A single tile in the world grid."""

    __slots__ = (
        "x", "y", "biome", "elevation",
        "resource_node", "depleted", "regrow_timer",
        "terrain_color", "fog_density",
        "blended_spawns",
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
        self.fog_density: float = 1.0  # Precomputed exp(-elev / scale) for volumetric fog
        # Per-tile ecotone blend of spawnable resource ids (border tiles only);
        # None = use biome.resource_spawns. Set by world_gen._build_biome_transitions.
        self.blended_spawns: list[str] | None = None

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

    __slots__ = (
        "width", "height", "tiles", "spawn_x", "spawn_y", "_season_system",
        "corner_ao", "corner_height", "corner_fog", "tile_center_height",
        "_regrow_tiles", "_elev_np",
    )

    def elevation_grid(self) -> "np.ndarray":
        """Int32 elevation array shared by all bake passes.

        Built once (the world gen bakes previously rebuilt this 512×512
        grid in four separate loops). Regenerate only if tiles change —
        elevation is immutable during play today.
        """
        if self._elev_np is None:
            self._elev_np = np.array(
                [[t.elevation for t in col] for col in self.tiles],
                dtype=np.int32,
            )
        return self._elev_np

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
        self.corner_ao: list[list[float]] = []  # (width+1) x (height+1) AO factors per corner
        self.corner_height: list[list[float]] = []  # (width+1) x (height+1) smoothed corner heights
        self.corner_fog: list[list[float]] = []  # (width+1) x (height+1) exp(-h/scale) per corner
        self.tile_center_height: list[list[float]] = []  # (width) x (height) tile center heights
        # Tiles with an active regrow timer — the only tiles update() ticks
        # (enqueued on depletion / save restore, dequeued on regrow).
        self._regrow_tiles: set[tuple[int, int]] = set()
        self._elev_np = None  # shared elevation ndarray cache (bakes)

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

    def mark_regrowing(self, x: int, y: int) -> None:
        """
        Enqueue a tile into the regrow timer set.

        Called when a resource node depletes (action system) or when a
        regrow timer is restored from a save. Idempotent.
        """
        tile = self.get_tile(x, y)
        if tile is None:
            return
        if (
            tile.resource_node is not None
            and tile.resource_node.is_depleted
            and tile.regrow_timer <= 0
        ):
            tile.regrow_timer = tile.resource_node.regrow_time
            tile.depleted = True
        if tile.regrow_timer > 0:
            self._regrow_tiles.add((x, y))

    def update(self, dt: float) -> None:
        """
        Tick only tiles with an active regrow timer.

        Handles regrowth timers and any tile-level state changes.
        Applies seasonal regrowth modifier when a SeasonSystem is wired.
        Previously this visited all 512×512 tiles every frame; only tiles
        in _regrow_tiles do work, so the full map is no longer scanned.
        """
        if not self._regrow_tiles:
            return
        regrowth_mod = 1.0
        if self._season_system is not None:
            try:
                regrowth_mod = self._season_system.get_survival_modifiers().get("regrowth", 1.0)
            except Exception:
                pass
        done = []
        for x, y in self._regrow_tiles:
            tile = self.tiles[x][y]
            tile.update(dt, regrowth_mod)
            if tile.regrow_timer <= 0 and not tile.depleted:
                done.append((x, y))
        for key in done:
            self._regrow_tiles.discard(key)

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
        Compute (or look up) the interpolated height at corner (cx, cy).

        When ``self.corner_height`` has been populated by
        ``bake_corner_heights()`` (and the index is in bounds for that
        grid), this returns the cached value. Otherwise it falls back to
        the on-demand 12-tile kernel compute so any caller that bypasses
        the bake (e.g. tests on tiny maps, edge cases) keeps working.

        Kernel (when computing on demand):
            4 center tiles (the 2x2 around corner): weight 4 each
            4 ortho neighbors (90° rotation orbit): weight 1 each
            4 diag neighbors (90° rotation orbit): weight 0.25 each

        Out-of-bounds tiles are treated as elevation 0 (cliff edge).

        Returns:
            The interpolated corner height as a float.
        """
        # Fast path: serve from the baked grid when available and in range.
        grid = self.corner_height
        if grid and 0 <= cx < len(grid) and 0 <= cy < len(grid[0]):
            return grid[cx][cy]

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
        Return the pre-baked center height of a tile.

        Reads from ``self.tile_center_height`` (populated by
        ``bake_corner_heights()``) for O(1) access. Falls back to the
        4-corner average if the bake hasn't run.
        """
        grid = self.tile_center_height
        if grid and 0 <= x < len(grid) and 0 <= y < len(grid[0]):
            return grid[x][y]
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

    def compute_slope_shading(
        self,
        x: int,
        y: int,
        light_dir: tuple[float, float, float] | None = None,
    ) -> Tuple[float, float]:
        """
        Compute slope-based brightness factor and slope magnitude for a tile.

        Uses raw corner elevations to determine the gradient of the terrain
        around this tile, then computes a brightness modifier based on the
        dot product of that gradient with a light direction.

        Args:
            x: Tile grid column.
            y: Tile grid row.
            light_dir: Optional ``(lx, ly, lz)`` light vector. When ``None``
                (default), the legacy fixed north-west light ``(-1, -1)`` is
                used and the math is byte-for-byte identical to the original
                implementation. When provided, the first two components
                parameterize the light direction (z is ignored here; the
                gradient lives in the x/y plane).

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

        # Light direction. None → legacy fixed NW (-1, -1) for byte-for-byte
        # parity with the original implementation.
        if light_dir is None:
            lx, ly = -1.0, -1.0
        else:
            lx, ly = light_dir[0], light_dir[1]

        # Dot product of gradient with light direction
        light_dot = (lx * grad_x) + (ly * grad_y)

        # Normalize light response: slopes facing the light brighten,
        # slopes facing away darken. Clamp to [-SHADING_STRENGTH, +SHADING_STRENGTH] range.
        brightness = 1.0 + max(-SHADING_STRENGTH, min(SHADING_STRENGTH, light_dot * SHADING_STRENGTH * 2.0))

        return (brightness, min(slope_mag / 2.0, 1.0))

    def get_surface_normal(self, x: int, y: int) -> tuple[float, float, float]:
        """
        Returns unnormalized surface normal (grad_x, grad_y, 1.0) for tile center.

        Used for rim/fresnel lighting.
        """
        nw = self.get_raw_corner_elevation(x, y)
        ne = self.get_raw_corner_elevation(x + 1, y)
        sw = self.get_raw_corner_elevation(x, y + 1)
        se = self.get_raw_corner_elevation(x + 1, y + 1)
        grad_x = (ne + se - nw - sw) / 2.0
        grad_y = (sw + se - nw - ne) / 2.0
        return (grad_x, grad_y, 1.0)

    def compute_corner_normal(self, cx: int, cy: int) -> tuple[float, float, float]:
        """
        Compute the unnormalized surface normal at a corner lattice point.

        Reads from the baked ``corner_height`` grid (``(W+1) x (H+1)``)
        populated by ``bake_corner_heights``. Falls back to on-demand
        ``get_corner_height`` samples when the grid is empty.

        Uses central differences of ``corner_height``:
            gx = (corner_height[cx+1][cy]  - corner_height[cx-1][cy]) / 2
            gy = (corner_height[cx][cy+1]  - corner_height[cx][cy-1]) / 2

        Edge clamping: at the west edge (cx-1 < 0) the "left" sample falls
        back to ``corner_height[cx][cy]`` (forward difference). Symmetric
        handling at east, north, and south edges. This matches the OOB-as-
        zero semantics used elsewhere — at the very corner of the world
        there's no neighbor, so we treat the self-sample as a zero gradient.

        Returns:
            ``(gx, gy, 1.0)`` — unnormalized normal pointing "up" out of
            the terrain (z component is constant 1.0 by convention).
        """
        h_cx_cy = self.get_corner_height(cx, cy)

        # Edge-clamped horizontal samples.
        if cx - 1 < 0:
            h_left = h_cx_cy
        else:
            h_left = self.get_corner_height(cx - 1, cy)

        # width+1 columns in corner_height, last valid index is ``width``.
        if cx + 1 > self.width:
            h_right = h_cx_cy
        else:
            h_right = self.get_corner_height(cx + 1, cy)

        # Edge-clamped vertical samples.
        if cy - 1 < 0:
            h_up = h_cx_cy
        else:
            h_up = self.get_corner_height(cx, cy - 1)

        # height+1 rows in corner_height, last valid index is ``height``.
        if cy + 1 > self.height:
            h_down = h_cx_cy
        else:
            h_down = self.get_corner_height(cx, cy + 1)

        gx = (h_right - h_left) / 2.0
        gy = (h_down - h_up) / 2.0
        return (gx, gy, 1.0)

    def compute_corner_brightness(
        self,
        cx: int,
        cy: int,
        light_dir: tuple[float, float, float] | tuple[float, float],
        strength: float,
    ) -> float:
        """
        Compute slope-based brightness at a corner lattice point.

        Mirrors the P0-fixed ``compute_slope_shading`` sign convention
        exactly: brightness = 1 + clip(light_dot * strength * 2,
                                       -strength, +strength) where
        ``light_dot = (lx * gx) + (ly * gy)``. Slopes whose gradient points
        toward the light brighten; slopes facing away darken. The z
        component of ``light_dir``, if any, is ignored — brightness is a
        function of the elevation gradient projected onto the 2D light
        direction.

        Args:
            cx: Corner lattice column.
            cy: Corner lattice row.
            light_dir: 2- or 3-tuple ``(lx, ly, [lz])``.
            strength: Clamp range (typically ``SHADING_STRENGTH``).

        Returns:
            Brightness in ``[1 - strength, 1 + strength]``.
        """
        gx, gy, _ = self.compute_corner_normal(cx, cy)
        lx = light_dir[0]
        ly = light_dir[1]
        light_dot = (lx * gx) + (ly * gy)
        # Clip into [-strength, +strength] and scale into brightness space.
        clipped = max(-strength, min(strength, light_dot * strength * 2.0))
        return 1.0 + clipped

    def bake_ambient_occlusion(self) -> None:
        """
        Pre-compute per-corner AO factor [0.0, 1.0] using the 12-tile kernel.
        1.0 = no occlusion (convex), <1.0 = occluded (concave).
        Stores result in self.corner_ao as (width+1) x (height+1) grid.
        
        Vectorized over the corner grid (was ~260k×(12+49) scalar iterations).
        Window sums add in the same (dx, dy) order as the original loops with
        zeros for OOB samples, which is float-exact (adding 0.0 never changes
        a float64 accumulator).
        """
        import numpy as np

        from config import AO_STRENGTH, AO_BLUR_RADIUS

        w, h = self.width, self.height

        # 12-tile kernel matching get_corner_height
        kernel = [
            (-1, -1, 4.0), (0, -1, 4.0), (-1, 0, 4.0), (0, 0, 4.0),
            (-2, -1, 1.0), (1, -2, 1.0), (2, 1, 1.0), (-1, 2, 1.0),
            (-2, -2, 0.25), (2, -2, 0.25), (2, 2, 0.25), (-2, 2, 0.25),
        ]

        elev = self.elevation_grid().astype(np.float64)
        # Corners are (w+1)x(h+1); pad so OOB reads are 0.
        pes = np.pad(elev, 3)
        pones = np.pad(np.ones_like(elev), 3)

        # Reference height: mean of the 4 claw tiles, in the original order.
        ref_sum = np.zeros((w + 1, h + 1))
        ref_cnt = np.zeros((w + 1, h + 1))
        for dx, dy in ((-1, -1), (0, -1), (-1, 0), (0, 0)):
            ref_sum += pes[3 + dx : 3 + dx + w + 1, 3 + dy : 3 + dy + h + 1]
            ref_cnt += pones[3 + dx : 3 + dx + w + 1, 3 + dy : 3 + dy + h + 1]
        ref_elev = np.where(ref_cnt > 0, ref_sum / np.where(ref_cnt > 0, ref_cnt, 1.0), 0.0)

        concave = np.zeros((w + 1, h + 1))
        total_weight = np.zeros((w + 1, h + 1))
        for dx, dy, weight in kernel:
            s_sl = pes[3 + dx : 3 + dx + w + 1, 3 + dy : 3 + dy + h + 1]
            inb = pones[3 + dx : 3 + dx + w + 1, 3 + dy : 3 + dy + h + 1] > 0
            total_weight += np.where(inb, weight, 0.0)
            delta = s_sl - ref_elev
            concave += np.where(s_sl > ref_elev, weight * np.minimum(1.0, delta / 2.0), 0.0)

        ao = np.where(
            total_weight > 0,
            np.maximum(0.0, 1.0 - (concave / np.where(total_weight > 0, total_weight, 1.0)) * AO_STRENGTH),
            1.0,
        )

        if AO_BLUR_RADIUS > 0:
            R = AO_BLUR_RADIUS
            pao = np.pad(ao, R)
            pcnt = np.pad(np.ones((w + 1, h + 1)), R)
            s = np.zeros_like(ao)
            c = np.zeros_like(ao)
            for dx in range(-R, R + 1):
                for dy in range(-R, R + 1):
                    s += pao[R + dx : R + dx + w + 1, R + dy : R + dy + h + 1]
                    c += pcnt[R + dx : R + dx + w + 1, R + dy : R + dy + h + 1]
            ao = np.where(c > 0, s / np.where(c > 0, c, 1.0), 1.0)

        self.corner_ao = ao.tolist()


    def bake_corner_heights(self) -> None:
        """
        Pre-compute the smoothed corner-height grid using the 12-tile kernel.

        Populates ``self.corner_height`` as a ``(width+1) x (height+1)`` list
        of lists. The kernel, OOB-as-zero handling, and total-weight
        normalization are byte-for-byte identical to ``get_corner_height``,
        so consumers (and existing tests) see no change in values.
        """
        w, h = self.width, self.height

        # 12-tile kernel matching get_corner_height (center, ortho, diag orbits).
        kernel_dx = np.array([-1, 0, -1, 0, -2, 1, 2, -1, -2, 2, 2, -2], dtype=np.int32)
        kernel_dy = np.array([-1, -1, 0, 0, -1, -2, 1, 2, -2, -2, 2, 2], dtype=np.int32)
        kernel_w = np.array(
            [4.0, 4.0, 4.0, 4.0, 1.0, 1.0, 1.0, 1.0, 0.25, 0.25, 0.25, 0.25],
            dtype=np.float32,
        )
        total_weight = float(kernel_w.sum())

        # Elevations as a NumPy grid; corner samples are the 12 kernel offsets
        # over a (w+1, h+1) grid, so pad to (w+7, h+7) and OOB-as-zero is the
        # pad value (matching get_corner_height's semantics).
        elev = self.elevation_grid().astype(np.float32)
        pe = np.pad(elev, 3)

        # Accumulate in kernel order (float32), replicating np.dot's per-corner
        # weighted sum; float32 adds are exact-same-op so results match the
        # old per-corner loop bit-for-bit on this platform.
        grid = np.zeros((w + 1, h + 1), dtype=np.float32)
        for dx, dy, wgt in zip(kernel_dx, kernel_dy, kernel_w):
            s_sl = pe[3 + dx : 3 + dx + w + 1, 3 + dy : 3 + dy + h + 1]
            # Mask true OOB samples: pad value is already 0, but the pad also
            # stands in for real blobs at +3; the window reads exactly the
            # kernel footprint, so slices are correct as-is.
            grid += s_sl * np.float32(wgt)
        grid /= np.float32(total_weight)

        # Convert to list-of-lists for natural Python indexing.
        self.corner_height = grid.tolist()

        # Tile center heights: average of the 4 corners of each tile.
        # (w, h) grid, matching tile indices.
        self.tile_center_height = (
            grid[:-1, :-1] + grid[1:, :-1] + grid[:-1, 1:] + grid[1:, 1:]
        ) * 0.25
        self.tile_center_height = self.tile_center_height.tolist()

    def bake_corner_fog(self) -> None:
        """
        Pre-compute per-corner fog density ``exp(-corner_height / FOG_SCALE_HEIGHT)``.

        Populates ``self.corner_fog`` as a ``(width+1) x (height+1)`` list of
        lists. Reads from ``self.corner_height``, which must already be
        populated by ``bake_corner_heights()``.
        """
        if not self.corner_height:
            raise ValueError(
                "bake_corner_fog() requires bake_corner_heights() to run first"
            )

        grid = np.array(self.corner_height, dtype=np.float32)
        fog = np.exp(-grid / FOG_SCALE_HEIGHT)
        self.corner_fog = fog.tolist()

    def get_tile_ao(self, x: int, y: int) -> float:
        """Bilinear interpolation of 4 corner AO values for a tile."""
        if not self.corner_ao:
            return 1.0
        return (
            self.corner_ao[x][y] + self.corner_ao[x + 1][y] +
            self.corner_ao[x][y + 1] + self.corner_ao[x + 1][y + 1]
        ) / 4.0
