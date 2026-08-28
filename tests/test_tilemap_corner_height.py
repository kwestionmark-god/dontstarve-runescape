"""Tests for TileMap corner height kernel."""

import pytest
from world.tile_map import TileMap, Tile
from world.biome import Biome


def make_test_tilemap(elevations: list[list[int]]) -> TileMap:
    """Helper to create a TileMap with given elevations (x-major)."""
    width = len(elevations)
    height = len(elevations[0]) if width > 0 else 0
    tm = TileMap(width, height, spawn_x=0, spawn_y=0)
    for x in range(width):
        for y in range(height):
            tm.tiles[x][y] = Tile(x, y, biome=None, elevation=elevations[x][y])
    return tm


def test_corner_height_kernel_symmetry():
    """Verify corner height kernel is symmetric and doesn't double-count."""
    # 17x17: center 13x13 elevation=1, outer=0 — large enough that kernel (±2) 
    # doesn't hit border for any of the 4 corners of the center 2x2 block
    elevations = [[0] * 17 for _ in range(17)]
    for x in range(2, 15):
        for y in range(2, 15):
            elevations[x][y] = 1
    tm = make_test_tilemap(elevations)

    # The 4 corners of the center 2x2 block (at x,y∈{7,8} in 0-indexed)
    # These are symmetric under 90° rotation around the world center (8,8)
    # With 13x13 elevated region, all 4 corners are ≥2 tiles from border
    h1 = tm.get_corner_height(8, 8)  # center of elevated region
    h2 = tm.get_corner_height(7, 8)
    h3 = tm.get_corner_height(8, 7)
    h4 = tm.get_corner_height(7, 7)

    assert abs(h1 - h2) < 0.01, f"Corners should be symmetric: {h1} vs {h2}"
    assert abs(h1 - h3) < 0.01, f"Corners should be symmetric: {h1} vs {h3}"
    assert abs(h1 - h4) < 0.01, f"Corners should be symmetric: {h1} vs {h4}"


def test_corner_height_no_double_count():
    """Verify the four tiles around a corner aren't double-counted."""
    # Single elevated tile at (2,2)
    elevations = [
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]
    tm = make_test_tilemap(elevations)

    # Corner (2,2) touches tiles (1,1), (2,1), (1,2), (2,2)
    # Only (2,2) has elevation 1
    # With correct kernel, that tile gets weight 4, so contribution = 4*1 = 4
    # Total weight = 4*4 + 4*1 + 4*0.25 = 16 + 4 + 1 = 21
    # Expected height = 4 / 21 ≈ 0.1905

    h = tm.get_corner_height(2, 2)
    expected = 4.0 / 21.0
    assert abs(h - expected) < 0.001, f"Expected {expected}, got {h}"


def test_corner_height_uniform_elevation():
    """If all tiles have same elevation, corner height equals that elevation."""
    elevations = [[3] * 5 for _ in range(5)]
    tm = make_test_tilemap(elevations)

    h = tm.get_corner_height(2, 2)
    assert abs(h - 3.0) < 0.001, f"Uniform elevation should give same height: {h}"