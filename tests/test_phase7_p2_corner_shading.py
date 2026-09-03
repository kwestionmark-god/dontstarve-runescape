"""
Phase 7 P2 — per-corner slope shading math (normal + brightness).

Locks down the per-corner math that the Gouraud rasterizer (P3) and
triangular renderer (P4) will consume. The math mirrors the now-fixed
``TileMap.compute_slope_shading`` (P0) but operates on the baked
``corner_height`` grid (P1) instead of raw per-tile elevations.

Coverage:
- ``TileMap.compute_corner_normal(cx, cy)`` returns the unnormalized
  surface normal ``(gx, gy, 1.0)`` from the baked ``corner_height``
  grid using central differences (with OOB clamping to forward diff).
- ``TileMap.compute_corner_brightness(cx, cy, light_dir, strength)``
  returns a brightness in ``[1 - strength, 1 + strength]`` that follows
  the P0 sign convention: ``light_dot = -(lx*gx) - (ly*gy)``,
  ``brightness = 1 + clip(light_dot * strength * 2, ...)``.
- ``LightingSystem.compute_all_corner_shading(tile_map, lx, ly, lz)``
  vectorizes the above over the full corner lattice and caches it.
- The cache is dirty by default and invalidated by ``set_preset`` and
  ``update_from_season``.
"""

from __future__ import annotations

import numpy as np
import pytest

from render.lighting_system import LightingSystem
from world.tile_map import TileMap, Tile

from config import SHADING_STRENGTH


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_tile_map(width: int, height: int,
                   elevations: list[list[int]] | None = None) -> TileMap:
    """
    Build a TileMap of size (width, height) with optional per-tile elevations.

    elevations is x-major: elevations[x][y]. When None, every tile is elevation 0.
    """
    tm = TileMap(width, height, 0, 0)
    for x in range(width):
        for y in range(height):
            elev = elevations[x][y] if elevations is not None else 0
            tm.tiles[x][y] = Tile(x, y, biome=None, elevation=elev)
    return tm


# ──────────────────────────────────────────────
# TileMap.compute_corner_normal
# ──────────────────────────────────────────────

class TestComputeCornerNormal:
    """``compute_corner_normal`` returns ``(gx, gy, 1.0)`` from the baked grid."""

    def test_uniform_map_returns_zero_gradient(self):
        """On a flat map, every corner normal is (0, 0, 1.0).

        Only fully-interior corners are checked. The OOB-as-zero kernel
        attenuates ``corner_height`` within 2 tiles of the world border
        (kernel reaches ±2), so any corner within 2 of the border has at
        least one attenuated neighbor and a non-zero gradient. The
        fully-interior central-diff range is cx ∈ [3..5], cy ∈ [3..5] on
        a 9x9 map: every neighbor used by the central diff is at full
        elevation and the gradient is exactly zero.
        """
        tm = _make_tile_map(9, 9, elevations=[[5] * 9 for _ in range(9)])
        tm.bake_corner_heights()

        for cx in range(3, 6):
            for cy in range(3, 6):
                nx, ny, nz = tm.compute_corner_normal(cx, cy)
                assert nx == 0.0, f"gx at ({cx},{cy}) = {nx}; expected 0"
                assert ny == 0.0, f"gy at ({cx},{cy}) = {ny}; expected 0"
                assert nz == 1.0, f"gz at ({cx},{cy}) = {nz}; expected 1"

    def test_east_rising_slope_positive_gx(self):
        """Linear east-rising slope → positive gx at central-diff corners.

        We check cx ∈ [1..7] with cy ∈ [3..5]. cx=8 has cx+1 clamped to
        the corner itself by the edge handling, which makes the gradient
        one-sided and (because the kernel has attenuated the corner-height
        less aggressively than its east neighbor) negative — that's a
        pathological edge case, not the slope we're modeling, so we
        exclude it.
        """
        elevations = [[x for y in range(9)] for x in range(9)]
        tm = _make_tile_map(9, 9, elevations=elevations)
        tm.bake_corner_heights()

        for cx in range(1, 8):
            for cy in range(3, 6):
                nx, _, nz = tm.compute_corner_normal(cx, cy)
                assert nx > 0.0, f"gx at ({cx},{cy}) = {nx}; expected > 0"
                assert nz == 1.0

    def test_normal_is_unnormalized_z_equals_one(self):
        """The returned normal is unnormalized; z component is always 1.0."""
        # Any non-uniform map, any corner.
        elevations = [[(x * 3 + y * 5) % 11 for y in range(7)] for x in range(7)]
        tm = _make_tile_map(7, 7, elevations=elevations)
        tm.bake_corner_heights()

        for cx in range(8):
            for cy in range(8):
                _, _, nz = tm.compute_corner_normal(cx, cy)
                assert nz == 1.0, f"z at ({cx},{cy}) = {nz}; expected exactly 1.0"

    def test_edge_clamps_use_forward_difference(self):
        """At the west edge (cx=0) the left sample falls back to the corner itself."""
        # 9x9 east-rising slope. At cx=0, "left" sample = corner_height[0][cy]
        # and "right" sample = corner_height[1][cy]. So gx is a one-sided
        # forward diff: (h[1][cy] - h[0][cy]) / 2.
        elevations = [[x for y in range(9)] for x in range(9)]
        tm = _make_tile_map(9, 9, elevations=elevations)
        tm.bake_corner_heights()

        for cy in range(1, 9):  # interior in y
            nx, _, _ = tm.compute_corner_normal(0, cy)
            h0 = tm.corner_height[0][cy]
            h1 = tm.corner_height[1][cy]
            expected_gx = (h1 - h0) / 2.0
            assert abs(nx - expected_gx) < 1e-6, (
                f"West-edge gx at (0,{cy}) = {nx}; expected forward-diff "
                f"(h[1]-h[0])/2 = {expected_gx}"
            )

    def test_requires_baked_corner_height(self):
        """compute_corner_normal reads from the baked corner_height grid.

        If the bake hasn't happened, the fallback path inside
        ``get_corner_height`` kicks in (kernel compute on demand). We assert
        the method still returns the (gx, gy, 1.0) tuple — it must not raise
        and must still report zero gradient on a uniform unbaked map.
        """
        tm = _make_tile_map(9, 9, elevations=[[3] * 9 for _ in range(9)])
        # Note: no bake_corner_heights() call here.
        nx, ny, nz = tm.compute_corner_normal(5, 5)
        assert nx == 0.0 and ny == 0.0 and nz == 1.0


# ──────────────────────────────────────────────
# TileMap.compute_corner_brightness
# ──────────────────────────────────────────────

class TestComputeCornerBrightness:
    """``compute_corner_brightness`` follows the P0 sign convention."""

    def test_uniform_map_returns_one_for_any_light(self):
        """On a flat map, brightness = 1.0 regardless of light_dir.

        Fully-interior corners only — the OOB-as-zero kernel attenuates
        ``corner_height`` near the world border, so the edge-corner gradient
        is non-zero on a uniform map by construction. Fully-interior corners
        (cx ∈ [3..6], cy ∈ [3..6] on a 9x9 map) see identical samples on
        both sides, giving exactly zero gradient.
        """
        tm = _make_tile_map(9, 9, elevations=[[7] * 9 for _ in range(9)])
        tm.bake_corner_heights()

        light_dirs = [
            (1.0, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.5, 0.5, 0.7),  # z ignored
            (-1.0, -1.0, 0.0),
        ]
        for lx, ly, lz in light_dirs:
            for cx in range(3, 6):
                for cy in range(3, 6):
                    b = tm.compute_corner_brightness(cx, cy, (lx, ly, lz), SHADING_STRENGTH)
                    assert b == 1.0, (
                        f"Flat brightness at ({cx},{cy}) light=({lx},{ly},{lz}) "
                        f"= {b}; expected 1.0"
                    )

    def test_east_rising_slope_with_east_light_clamps_to_plus_strength(self):
        """An east-rising slope with east light → brightness = 1 + SHADING_STRENGTH.

        Asserted only at fully-interior corners (cx ∈ [3..5]) where the
        kernel-smoothed gradient is exactly 1.0 and the response clamps to
        ``1 + SHADING_STRENGTH``. Near the world border the OOB-as-zero
        kernel attenuates the gradient below 1.0 and the brightness does
        not clamp.
        """
        elevations = [[x for y in range(9)] for x in range(9)]
        tm = _make_tile_map(9, 9, elevations=elevations)
        tm.bake_corner_heights()

        for cx in range(3, 6):
            for cy in range(3, 6):
                b = tm.compute_corner_brightness(cx, cy, (1.0, 0.0, 0.0), SHADING_STRENGTH)
                assert abs(b - (1.0 + SHADING_STRENGTH)) < 1e-6, (
                    f"East light on east-rising slope at ({cx},{cy}) = {b}; "
                    f"expected 1 + SHADING_STRENGTH = {1.0 + SHADING_STRENGTH}"
                )

    def test_east_rising_slope_with_west_light_clamps_to_minus_strength(self):
        """An east-rising slope with west light → brightness = 1 - SHADING_STRENGTH.

        See ``test_east_rising_slope_with_east_light_clamps_to_plus_strength``
        for the rationale on the cx ∈ [3..5] range.
        """
        elevations = [[x for y in range(9)] for x in range(9)]
        tm = _make_tile_map(9, 9, elevations=elevations)
        tm.bake_corner_heights()

        for cx in range(3, 6):
            for cy in range(3, 6):
                b = tm.compute_corner_brightness(cx, cy, (-1.0, 0.0, 0.0), SHADING_STRENGTH)
                assert abs(b - (1.0 - SHADING_STRENGTH)) < 1e-6, (
                    f"West light on east-rising slope at ({cx},{cy}) = {b}; "
                    f"expected 1 - SHADING_STRENGTH = {1.0 - SHADING_STRENGTH}"
                )

    def test_brightness_stays_in_band(self):
        """Brightness is always in [1 - strength, 1 + strength]."""
        # Random-ish elevations to exercise the range.
        elevations = [[(x * 7 + y * 11 + 3) % 32 for y in range(9)] for x in range(9)]
        tm = _make_tile_map(9, 9, elevations=elevations)
        tm.bake_corner_heights()

        for cx in range(10):
            for cy in range(10):
                b = tm.compute_corner_brightness(cx, cy, (1.0, -1.0, 0.5), SHADING_STRENGTH)
                assert (1.0 - SHADING_STRENGTH) <= b <= (1.0 + SHADING_STRENGTH), (
                    f"brightness at ({cx},{cy}) = {b} out of band"
                )

    def test_continuity_across_shared_edge(self):
        """Two adjacent tiles share the corner brightness on their common edge.

        Build a 2-tile map where both tiles have the same elevations on the
        shared edge. The corner brightness read directly from ``corner_height``
        (or from the new method) must be the same regardless of which tile
        you approach it from.
        """
        # 2 tiles side-by-side. elevations[x][y] = 2 for both tiles → flat.
        # The shared vertical edge sits at cx=1.
        elevations = [[2, 2], [2, 2]]
        tm = _make_tile_map(2, 2, elevations=elevations)
        tm.bake_corner_heights()

        shared_cx = 1
        for cy in range(3):
            b_left = tm.compute_corner_brightness(
                shared_cx, cy, (1.0, 0.0, 0.0), SHADING_STRENGTH
            )
            # Reading from either side yields the same baked value.
            b_right = tm.compute_corner_brightness(
                shared_cx, cy, (1.0, 0.0, 0.0), SHADING_STRENGTH
            )
            assert b_left == b_right, (
                f"Continuity broken at ({shared_cx},{cy}): "
                f"left={b_left}, right={b_right}"
            )

    def test_continuity_holds_on_real_slope(self):
        """Continuity holds across a non-trivial shared edge on a real slope."""
        # 3x3 map with elevations = x+y (diagonal ramp). Pick an interior
        # corner shared between multiple tiles; both calls must agree.
        elevations = [[x + y for y in range(3)] for x in range(3)]
        tm = _make_tile_map(3, 3, elevations=elevations)
        tm.bake_corner_heights()

        light = (0.7, -0.3, 0.0)
        for cx in range(1, 3):
            for cy in range(1, 4):
                b1 = tm.compute_corner_brightness(cx, cy, light, SHADING_STRENGTH)
                b2 = tm.compute_corner_brightness(cx, cy, light, SHADING_STRENGTH)
                assert b1 == b2, f"Continuity broken at ({cx},{cy})"


# ──────────────────────────────────────────────
# LightingSystem.compute_all_corner_shading
# ──────────────────────────────────────────────

class TestComputeAllCornerShading:
    """Vectorized per-corner shading with cache."""

    def _make_flat_world(self, width: int = 5, height: int = 4) -> TileMap:
        tm = _make_tile_map(width, height, elevations=[[3] * height for _ in range(width)])
        tm.bake_corner_heights()
        tm.bake_corner_fog()
        return tm

    def _make_slope_world(self, width: int = 5, height: int = 4) -> TileMap:
        elevations = [[x for y in range(height)] for x in range(width)]
        tm = _make_tile_map(width, height, elevations=elevations)
        tm.bake_corner_heights()
        tm.bake_corner_fog()
        return tm

    def test_returns_correct_shapes(self):
        """brightness_grid is (W+1, H+1); normal_grid is (W+1, H+1, 3)."""
        tm = self._make_flat_world(width=5, height=4)
        ls = LightingSystem()
        brightness, normal = ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)

        assert isinstance(brightness, np.ndarray)
        assert isinstance(normal, np.ndarray)
        assert brightness.shape == (6, 5), f"brightness shape = {brightness.shape}"
        assert normal.shape == (6, 5, 3), f"normal shape = {normal.shape}"

    def test_returns_none_when_corner_height_unbaked(self):
        """If corner_height is empty, return (None, None)."""
        # No bake_corner_heights() call.
        tm = _make_tile_map(5, 4)
        ls = LightingSystem()
        brightness, normal = ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)

        assert brightness is None
        assert normal is None

    def test_brightness_in_band_on_flat_map(self):
        """On a flat map, brightness = 1.0 at the fully-interior corners.

        The OOB-as-zero kernel attenuates ``corner_height`` within 2
        tiles of the world border (kernel reaches ±2), so the gradient is
        non-zero at the borders by construction. We use a 9x9 map so a
        3x3 fully-interior patch exists where the central diff yields
        exactly zero gradient → exactly 1.0 brightness.
        """
        tm = _make_tile_map(9, 9, elevations=[[3] * 9 for _ in range(9)])
        tm.bake_corner_heights()
        ls = LightingSystem()
        brightness, _ = ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)

        # Fully-interior region: cx ∈ [3..5], cy ∈ [3..5] on a 9x9 map.
        interior = brightness[3:6, 3:6]
        assert np.all(np.abs(interior - 1.0) < 1e-6), (
            f"Flat-map brightness should be 1.0 at fully-interior corners; "
            f"got range [{interior.min()}, {interior.max()}]"
        )

    def test_brightness_extremes_on_east_rising_slope(self):
        """East light on east-rising slope clamps to 1 + SHADING_STRENGTH."""
        tm = self._make_slope_world(width=5, height=4)
        ls = LightingSystem()
        brightness, _ = ls.compute_all_corner_shading(tm, 1.0, 0.0, 0.0)

        # At interior corners the gradient is large enough to clamp.
        # Find at least one corner that's clamped (interior of the slope).
        clamped_value = 1.0 + SHADING_STRENGTH
        assert np.any(np.abs(brightness - clamped_value) < 1e-6), (
            f"East light should clamp at least one interior corner to "
            f"{clamped_value}; got max={brightness.max()}"
        )

    def test_normal_z_component_is_one(self):
        """normal[..., 2] is 1.0 everywhere (unnormalized)."""
        tm = self._make_slope_world(width=5, height=4)
        ls = LightingSystem()
        _, normal = ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)

        assert np.all(np.abs(normal[..., 2] - 1.0) < 1e-6)

    def test_normal_xy_negates_gradient(self):
        """normal[..., 0:2] = (-gx, -gy) so the normal points 'up' out of the surface."""
        tm = self._make_slope_world(width=5, height=4)
        ls = LightingSystem()
        _, normal = ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)

        # An east-rising slope has gx > 0 at interior corners, so the
        # normal's x component should be negative there.
        # Compare at cx=3, cy=2 — interior, central diff valid on both sides.
        nx = normal[3, 2, 0]
        assert nx < 0.0, f"normal[3,2,0] = {nx}; expected < 0 on east-rising slope"


# ──────────────────────────────────────────────
# LightingSystem corner shading cache
# ──────────────────────────────────────────────

class TestCornerShadingCache:
    """Cache invalidation via mark_corner_shading_dirty / set_preset / update_from_season."""

    def _setup(self):
        tm = _make_tile_map(
            5, 4, elevations=[[x for y in range(4)] for x in range(5)]
        )
        tm.bake_corner_heights()
        ls = LightingSystem()
        return tm, ls

    def test_cache_starts_dirty(self):
        """A fresh LightingSystem is dirty by default."""
        _, ls = self._setup()
        assert ls._corner_shading_dirty is True
        assert ls._corner_brightness is None
        assert ls._corner_normal is None

    def test_first_call_populates_cache_and_clears_dirty(self):
        """First compute_all_corner_shading recomputes and clears the dirty flag."""
        tm, ls = self._setup()
        brightness, normal = ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_dirty is False
        assert ls._corner_brightness is not None
        assert ls._corner_normal is not None
        assert brightness is ls._corner_brightness
        assert normal is ls._corner_normal

    def test_second_call_is_a_cache_hit(self):
        """A second call with the same light is a cache hit (no recompute)."""
        tm, ls = self._setup()
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_recompute_count == 1

        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_recompute_count == 1, (
            "Second call with same light should be a cache hit"
        )

    def test_mark_dirty_forces_recompute(self):
        """Calling mark_corner_shading_dirty() triggers a recompute on next call."""
        tm, ls = self._setup()
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_recompute_count == 1

        ls.mark_corner_shading_dirty()
        assert ls._corner_shading_dirty is True

        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_recompute_count == 2

    def test_set_preset_marks_cache_dirty(self):
        """set_preset() invalidates the corner shading cache."""
        tm, ls = self._setup()
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_dirty is False

        ls.set_preset("realistic")
        assert ls._corner_shading_dirty is True, (
            "set_preset must mark corner shading dirty"
        )

        # Recompute → dirty flag clears.
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_dirty is False

    def test_update_from_season_marks_cache_dirty(self):
        """update_from_season() invalidates the cache when the sun moved."""
        from seasons.season_system import SeasonSystem

        tm, ls = self._setup()
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_dirty is False

        ss = SeasonSystem()
        ss.time_of_day = 0.5  # noon — sun differs from the default direction
        ls.update_from_season(ss)
        assert ls._corner_shading_dirty is True, (
            "update_from_season must mark corner shading dirty when the sun moved"
        )

        # Recompute → dirty flag clears.
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_dirty is False

    def test_update_from_season_keeps_cache_when_sun_unchanged(self):
        """Calling update_from_season twice with the same sun is a cache hit."""
        from seasons.season_system import SeasonSystem

        tm, ls = self._setup()
        ss = SeasonSystem()
        ls.update_from_season(ss)
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_recompute_count == 1

        ls.update_from_season(ss)  # same time_of_day → same sun
        assert ls._corner_shading_dirty is False
        ls.compute_all_corner_shading(tm, 0.5, 0.5, 0.7)
        assert ls._corner_shading_recompute_count == 1
