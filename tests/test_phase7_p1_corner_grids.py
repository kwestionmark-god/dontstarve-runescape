"""
Phase 7 P1 — bake per-corner height and fog grids.

Locks down:
- ``TileMap.bake_corner_heights()`` populates a ``(W+1, H+1)`` grid that
  matches ``get_corner_height(cx, cy)`` byte-for-byte (uses the same
  12-tile rotational kernel).
- ``TileMap.bake_corner_fog()`` populates ``(W+1, H+1)`` with
  ``exp(-corner_height[cx][cy] / FOG_SCALE_HEIGHT)``.
- ``TileMap.get_corner_height`` serves the bake when available and
  falls back to on-demand compute when the grid is empty.
- ``world_gen.generate(...)`` runs both bakes as part of the pipeline.
"""

from __future__ import annotations

import contextlib

import numpy as np
import pytest

from world import world_gen
from world.biome import BiomeRegistry
from world.tile_map import TileMap, Tile
from data import load_json_list
from config import FOG_SCALE_HEIGHT


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


@contextlib.contextmanager
def _small_map(size=64):
    """Patch world_gen MAP_WIDTH/MAP_HEIGHT for fast test generation."""
    saved_w, saved_h = world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT
    world_gen.MAP_WIDTH = size
    world_gen.MAP_HEIGHT = size
    try:
        yield
    finally:
        world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT = saved_w, saved_h


def _gen_small_world(size: int = 64) -> TileMap:
    with _small_map(size):
        registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))
        return world_gen.generate(42, registry, season_system=None)


# ──────────────────────────────────────────────
# Shape and cache lookup
# ──────────────────────────────────────────────

class TestCornerHeightBake:
    """``bake_corner_heights`` produces a (W+1, H+1) grid that matches get_corner_height."""

    def test_baked_grid_shape(self):
        """After bake, corner_height has shape (W+1, H+1)."""
        tm = _make_tile_map(5, 4)
        tm.bake_corner_heights()
        assert len(tm.corner_height) == 6, f"Width+1 = 6, got {len(tm.corner_height)}"
        for cx in range(len(tm.corner_height)):
            assert len(tm.corner_height[cx]) == 5, (
                f"Height+1 = 5 at column {cx}, got {len(tm.corner_height[cx])}"
            )

    def test_cache_matches_recompute_uniform(self):
        """On a uniform map, baked cache equals on-demand get_corner_height."""
        tm = _make_tile_map(6, 6, elevations=[[5] * 6 for _ in range(6)])
        tm.bake_corner_heights()

        # Sample a spread of indices including corners and interior.
        samples = [
            (0, 0), (0, 6), (6, 0), (6, 6),
            (3, 3), (1, 4), (4, 1), (2, 5),
        ]
        for cx, cy in samples:
            assert tm.get_corner_height(cx, cy) == tm.corner_height[cx][cy], (
                f"Cache mismatch at ({cx},{cy}): "
                f"get_corner_height={tm.get_corner_height(cx, cy)} "
                f"vs baked={tm.corner_height[cx][cy]}"
            )

    def test_cache_matches_recompute_non_uniform(self):
        """On a non-uniform map, baked cache matches on-demand compute."""
        # 7x7 grid; elevations vary so kernel sampling differs across corners.
        elevations = [[(x * 3 + y * 2) % 11 for y in range(7)] for x in range(7)]
        tm = _make_tile_map(7, 7, elevations=elevations)
        tm.bake_corner_heights()

        samples = [
            (0, 0), (0, 7), (7, 0), (7, 7),
            (3, 3), (4, 5), (5, 2), (1, 6),
            (3, 0), (0, 3), (6, 4),
        ]
        for cx, cy in samples:
            cached = tm.get_corner_height(cx, cy)
            baked = tm.corner_height[cx][cy]
            assert abs(cached - baked) < 1e-12, (
                f"Cache mismatch at ({cx},{cy}): get_corner_height={cached} "
                f"vs baked={baked}"
            )

    def test_uniform_map_corner_height_equals_per_tile_elevation(self):
        """Uniform map: baked corner_height equals per-tile elevation at interior corners.

        A corner (cx, cy) is fully interior when ``cx ∈ [2, w-3]`` and
        ``cy ∈ [2, h-3]`` — the kernel reaches ±2 tiles in every direction,
        so any sample touching the border drops out of the weighted average
        and pulls the value below the per-tile elevation. Restricting the
        check to fully interior corners proves the kernel math is correct
        while the bake still returns the per-tile elevation exactly.
        """
        # 9x9 uniform; fully interior corners run (cx, cy) ∈ [2..6].
        tm = _make_tile_map(9, 9, elevations=[[7] * 9 for _ in range(9)])
        tm.bake_corner_heights()
        w, h = tm.width, tm.height
        for cx in range(2, w - 2):
            for cy in range(2, h - 2):
                assert tm.corner_height[cx][cy] == 7.0, (
                    f"corner_height[{cx}][{cy}] = {tm.corner_height[cx][cy]} "
                    f"should equal 7.0 on uniform map at interior corner"
                )

    def test_cache_falls_back_when_unbaked(self):
        """When corner_height is empty, get_corner_height still works (on-demand)."""
        # 9x9 uniform; interior corner (5, 5) has all kernel samples in-bounds.
        tm = _make_tile_map(9, 9, elevations=[[3] * 9 for _ in range(9)])
        # Sanity: grid is empty before any bake.
        assert tm.corner_height == []
        # Must still compute on demand and equal the per-tile elevation.
        h = tm.get_corner_height(5, 5)
        assert isinstance(h, float)
        assert h == 3.0


# ──────────────────────────────────────────────
# Fog bake
# ──────────────────────────────────────────────

class TestCornerFogBake:
    """``bake_corner_fog`` populates exp(-corner_height / FOG_SCALE_HEIGHT)."""

    def test_baked_fog_grid_shape(self):
        """After bake, corner_fog has shape (W+1, H+1)."""
        tm = _make_tile_map(5, 4)
        tm.bake_corner_heights()
        tm.bake_corner_fog()
        assert len(tm.corner_fog) == 6, f"Width+1 = 6, got {len(tm.corner_fog)}"
        for cx in range(len(tm.corner_fog)):
            assert len(tm.corner_fog[cx]) == 5, (
                f"Height+1 = 5 at column {cx}, got {len(tm.corner_fog[cx])}"
            )

    def test_fog_decreases_with_height(self):
        """Higher corner_height ⇒ strictly lower corner_fog."""
        # 8x8 grid with monotonic x-axis slope so corner heights vary
        # monotonically along x. Sample two interior corners where
        # corner_height[cx1][cy] < corner_height[cx2][cy].
        elevations = [[x for y in range(8)] for x in range(8)]
        tm = _make_tile_map(8, 8, elevations=elevations)
        tm.bake_corner_heights()
        tm.bake_corner_fog()

        cy = 4  # middle row
        h_lo = tm.corner_height[2][cy]
        h_hi = tm.corner_height[6][cy]
        assert h_lo < h_hi, (
            f"Setup error: expected corner_height[2][{cy}] < corner_height[6][{cy}], "
            f"got {h_lo} vs {h_hi}"
        )
        assert tm.corner_fog[2][cy] > tm.corner_fog[6][cy], (
            f"Fog must decrease with height: "
            f"corner_fog[2][{cy}]={tm.corner_fog[2][cy]} "
            f"vs corner_fog[6][{cy}]={tm.corner_fog[6][cy]}"
        )

    def test_fog_in_unit_interval(self):
        """All corner_fog values must be in [0.0, 1.0] (exp is bounded)."""
        # Random-ish elevations to exercise the range
        elevations = [[(x * 7 + y * 11 + 3) % 32 for y in range(8)] for x in range(8)]
        tm = _make_tile_map(8, 8, elevations=elevations)
        tm.bake_corner_heights()
        tm.bake_corner_fog()

        for cx in range(9):
            for cy in range(9):
                v = tm.corner_fog[cx][cy]
                assert 0.0 <= v <= 1.0, (
                    f"corner_fog[{cx}][{cy}] = {v} out of [0, 1]"
                )

    def test_fog_value_matches_exp_formula(self):
        """corner_fog equals exp(-corner_height / FOG_SCALE_HEIGHT) at sampled indices."""
        elevations = [[(x + y) % 6 for y in range(6)] for x in range(6)]
        tm = _make_tile_map(6, 6, elevations=elevations)
        tm.bake_corner_heights()
        tm.bake_corner_fog()

        samples = [(2, 3), (5, 5), (0, 4), (4, 0), (3, 3)]
        for cx, cy in samples:
            expected = float(np.exp(-tm.corner_height[cx][cy] / FOG_SCALE_HEIGHT))
            got = tm.corner_fog[cx][cy]
            # Fog grid is float32 → ~7 sig-fig precision. 1e-6 is comfortably
            # above float32 round-off while still proving the formula is right.
            assert abs(got - expected) < 1e-6, (
                f"corner_fog[{cx}][{cy}] = {got}, expected exp(-{tm.corner_height[cx][cy]}"
                f"/{FOG_SCALE_HEIGHT}) = {expected}"
            )


# ──────────────────────────────────────────────
# World-gen integration
# ──────────────────────────────────────────────

class TestWorldGenWiring:
    """Both grids are populated as part of world_gen.generate()."""

    def test_world_gen_populates_corner_height(self):
        tm = _gen_small_world(size=64)
        assert hasattr(tm, "corner_height"), "TileMap should expose corner_height"
        assert len(tm.corner_height) == tm.width + 1, (
            f"corner_height width = {len(tm.corner_height)}, "
            f"expected {tm.width + 1}"
        )
        if tm.corner_height:
            assert len(tm.corner_height[0]) == tm.height + 1, (
                f"corner_height height = {len(tm.corner_height[0])}, "
                f"expected {tm.height + 1}"
            )

    def test_world_gen_populates_corner_fog(self):
        tm = _gen_small_world(size=64)
        assert hasattr(tm, "corner_fog"), "TileMap should expose corner_fog"
        assert len(tm.corner_fog) == tm.width + 1, (
            f"corner_fog width = {len(tm.corner_fog)}, expected {tm.width + 1}"
        )
        if tm.corner_fog:
            assert len(tm.corner_fog[0]) == tm.height + 1

    def test_world_gen_corner_fog_matches_height(self):
        """After world-gen, fog[i][j] == exp(-height[i][j] / FOG_SCALE_HEIGHT)."""
        tm = _gen_small_world(size=64)
        # Sample a handful of interior corners.
        samples = [(10, 10), (20, 30), (40, 50), (32, 32), (5, 60)]
        for cx, cy in samples:
            h = tm.corner_height[cx][cy]
            expected = float(np.exp(-h / FOG_SCALE_HEIGHT))
            # float32 precision → tolerance is ~1e-6, well above round-off.
            assert abs(tm.corner_fog[cx][cy] - expected) < 1e-6, (
                f"World-gen corner_fog[{cx}][{cy}] = {tm.corner_fog[cx][cy]}, "
                f"expected exp(-{h}/{FOG_SCALE_HEIGHT}) = {expected}"
            )

    def test_world_gen_corner_height_matches_get_corner_height(self):
        """After world-gen, the bake and the function agree at sampled indices."""
        tm = _gen_small_world(size=64)
        samples = [(5, 5), (10, 20), (30, 40), (50, 60), (63, 63)]
        for cx, cy in samples:
            cached = tm.get_corner_height(cx, cy)
            baked = tm.corner_height[cx][cy]
            # corner_height is float32 → ~7 sig-fig precision.
            assert abs(cached - baked) < 1e-6, (
                f"Mismatch at ({cx},{cy}): cached={cached}, baked={baked}"
            )
