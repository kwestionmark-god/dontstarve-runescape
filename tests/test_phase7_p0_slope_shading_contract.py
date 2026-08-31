"""
Phase 7 P0 — compute_slope_shading contract fix.

Locks down:
- ``compute_slope_shading(x, y)`` (no ``light_dir``) returns the legacy
  fixed-NW brightness byte-for-byte.
- ``compute_slope_shading(x, y, light_dir=(1.0, 0.0, 0.0))`` produces a
  *different* brightness than the legacy NW default on a known slope.
- ``compute_slope_shading(x, y, light_dir=(-1.0, 0.0, 0.0))`` produces the
  *opposite* response to ``(1.0, 0.0, 0.0)`` on the same slope.

This contract exists because ``render.tile_renderer`` calls the method
with a ``light_dir`` keyword under the ``"realistic"`` shading preset,
which previously raised ``TypeError``.
"""

from __future__ import annotations

import math

from world.tile_map import TileMap

from config import SHADING_STRENGTH


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_slope_tile_map(width: int = 4, height: int = 4) -> TileMap:
    """
    Build a TileMap with a linear east-rising slope: elevations[x][y] = x.

    At tile (0, 0) the four raw corner elevations are:
        NW=0, NE=1, SW=0, SE=1

    So the surface gradient is (grad_x=1.0, grad_y=0.0) — purely eastward.
    """
    tm = TileMap(width, height, 0, 0)
    for x in range(width):
        for y in range(height):
            tm.tiles[x][y].elevation = x
    return tm


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

class TestComputeSlopeShadingContract:
    """compute_slope_shading signature + light_dir behavior contract."""

    def test_legacy_call_no_light_dir_matches_nw_math(self):
        """Regression: legacy call (no light_dir) is byte-for-byte identical.

        Use tile (1, 1) (interior) so no edge-tile averaging distorts the
        corner elevations. On this interior tile the gradient is exactly
        (1.0, 0.0). Fixed NW light (-1, -1) →
        light_dot = -1.0 → clamped to -SHADING_STRENGTH → brightness = 0.8.
        Slope magnitude = sqrt(1.0) = 1.0 → min(0.5, 1.0) = 0.5.
        """
        tm = _make_slope_tile_map()
        brightness, slope_mag = tm.compute_slope_shading(1, 1)

        # Legacy expected value: clamped at -SHADING_STRENGTH
        expected = 1.0 + (-SHADING_STRENGTH)
        assert abs(brightness - expected) < 1e-12, (
            f"Legacy brightness must match fixed-NW math byte-for-byte; "
            f"expected {expected}, got {brightness}"
        )
        assert abs(slope_mag - 0.5) < 1e-12, (
            f"Slope magnitude should be min(sqrt(1.0)/2.0, 1.0) = 0.5; got {slope_mag}"
        )

    def test_flat_tile_legacy_call_is_unchanged(self):
        """Regression: flat tile → brightness exactly 1.0 (no shading)."""
        tm = TileMap(4, 4, 0, 0)
        # All elevations default to 0 → flat
        brightness, slope_mag = tm.compute_slope_shading(1, 1)
        assert brightness == 1.0, f"Flat tile brightness should be 1.0, got {brightness}"
        assert slope_mag == 0.0, f"Flat tile slope_mag should be 0.0, got {slope_mag}"

    def test_light_dir_east_differs_from_default_nw(self):
        """light_dir=(+1, 0, 0) brightens an east-rising slope; default NW darkens it."""
        tm = _make_slope_tile_map()

        legacy_brightness, _ = tm.compute_slope_shading(1, 1)
        east_brightness, _ = tm.compute_slope_shading(1, 1, light_dir=(1.0, 0.0, 0.0))

        assert east_brightness > legacy_brightness, (
            f"East light should brighten east-facing slope; "
            f"legacy={legacy_brightness}, east={east_brightness}"
        )

        # Specifically: east light dot = +1.0 → clamped to +SHADING_STRENGTH → 1.2
        expected_east = 1.0 + SHADING_STRENGTH
        assert abs(east_brightness - expected_east) < 1e-12, (
            f"East-light brightness must clamp at +SHADING_STRENGTH; "
            f"expected {expected_east}, got {east_brightness}"
        )

    def test_light_dir_east_vs_west_are_opposite(self):
        """Flipping light_dir sign flips the brightness offset from the neutral."""
        tm = _make_slope_tile_map()

        east_brightness, _ = tm.compute_slope_shading(1, 1, light_dir=(1.0, 0.0, 0.0))
        west_brightness, _ = tm.compute_slope_shading(1, 1, light_dir=(-1.0, 0.0, 0.0))

        # They should be symmetric around 1.0
        midpoint = (east_brightness + west_brightness) / 2.0
        assert abs(midpoint - 1.0) < 1e-12, (
            f"East/West brightness should be symmetric around 1.0; midpoint={midpoint}"
        )

        # Specifically:
        #   east:  1.0 + SHADING_STRENGTH = 1.2
        #   west:  1.0 - SHADING_STRENGTH = 0.8
        assert abs(east_brightness - (1.0 + SHADING_STRENGTH)) < 1e-12
        assert abs(west_brightness - (1.0 - SHADING_STRENGTH)) < 1e-12
