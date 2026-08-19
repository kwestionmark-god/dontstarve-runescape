"""
Tests for Smooth Elevation Rendering:
- get_corner_height interpolation correctness
- get_tile_center_height convenience method
"""

from world.tile_map import TileMap, Tile


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_tile_map(elevations: dict[tuple[int, int], int],
                   width: int = 5, height: int = 5) -> TileMap:
    """
    Create a TileMap and set elevations from a dict.

    Parameters
    ----------
    elevations : dict[(x, y), elevation]
        Mapping of tile coordinates to elevation values.
    width, height : int
        Dimensions of the tile map.

    Returns
    -------
    TileMap
        A tile map with the specified elevations.
    """
    tm = TileMap(width, height, 0, 0)
    for (x, y), elev in elevations.items():
        tile = tm.get_tile(x, y)
        if tile is not None:
            tile.elevation = elev
    return tm


# ──────────────────────────────────────────────
# Test cases
# ──────────────────────────────────────────────

def test_flat_area_no_variation():
    """All tiles at elevation 0 → every corner should be 0.0."""
    elevations = {(x, y): 0 for x in range(5) for y in range(5)}
    tm = _make_tile_map(elevations)

    # Check several corners (including corners of edge tiles)
    for cx in range(6):
        for cy in range(6):
            h = tm.get_corner_height(cx, cy)
            assert h == 0.0, f"Corner ({cx}, {cy}) should be 0.0, got {h}"


def test_single_hill_gradient_decay():
    """Single tile at elevation 7 → corners should decay outward."""
    elevations = {(2, 2): 7}
    tm = _make_tile_map(elevations, width=5, height=5)

    # Corner (2, 2): self tile (2,2) has weight 4 → h = 28/21 ≈ 1.33
    h_center = tm.get_corner_height(2, 2)
    assert 1.2 < h_center < 1.5, f"Center corner should be ~1.33, got {h_center}"

    # Corner (3, 2): (2,2) is self tile (weight 4) + ortho (weight 1) → h = 35/21 ≈ 1.67
    h_close = tm.get_corner_height(3, 2)
    assert 1.5 < h_close < 1.8, f"Close corner should be ~1.67, got {h_close}"

    # Corner (1, 1): (2,2) is diag neighbor (weight 0.25) → h = 1.75/21 ≈ 0.08
    h_far = tm.get_corner_height(1, 1)
    assert 0.05 < h_far < 0.15, f"Far corner should be ~0.08, got {h_far}"

    # Verify gradient: h_close > h_center > h_far
    assert h_close > h_center, f"Close corner ({h_close}) should be > center ({h_center})"
    assert h_center > h_far, f"Center corner ({h_center}) should be > far ({h_far})"


def test_corner_between_different_elevations():
    """Corner between elev 1 and elev 7 should be a weighted average, not 0 or 7."""
    # NW=7, SE=1, others=0
    elevations = {
        (2, 2): 7,   # NW of corner (3, 3)
        (3, 3): 1,   # SE of corner (3, 3)
    }
    tm = _make_tile_map(elevations, width=5, height=5)

    h = tm.get_corner_height(3, 3)

    # The four tiles around corner (3,3):
    # NW tile (2,2)=7, NE tile (3,2)=0, SW tile (2,3)=0, SE tile (3,3)=1
    # self-weight=4*7+4*1=32 from self, plus ortho/diag contributions
    # Should be strictly between 0 and 7 (closer to a weighted average)
    assert 0.0 < h < 7.0, f"Corner height should be between 0 and 7, got {h}"

    # Verify it is a weighted average: not dominated by one side
    # With weights 4+4+4+4 for self tiles: 28+4=32, plus neighbor weights
    # The value should reflect both contributions
    assert h > 1.0, f"Corner should be pulled above 1 by the elev-7 tile, got {h}"
    assert h < 4.0, f"Corner should be pulled below 4 by the elev-1 tile, got {h}"


def test_out_of_bounds_treated_as_zero():
    """Corner near map edge where some neighbors are out of bounds should still compute without error."""
    # Small map: only tile (0, 0) at elevation 5
    elevations = {(0, 0): 5}
    tm = _make_tile_map(elevations, width=2, height=2)

    # Corner (-1, -1) — most neighbors are out of bounds
    # Should not raise, and should return a small value (only tile (0,0) contributes)
    h = tm.get_corner_height(-1, -1)
    assert isinstance(h, float), f"Corner height should be float, got {type(h)}"
    assert 0.0 <= h < 5.0, f"Out-of-bounds corner should be < self elevation, got {h}"

    # Corner (2, 2) — same, near edge
    h = tm.get_corner_height(2, 2)
    assert isinstance(h, float), f"Corner height should be float, got {type(h)}"
    assert 0.0 <= h < 5.0, f"Edge corner should be < self elevation, got {h}"


def test_tile_center_height_equals_corner_average():
    """Verify get_tile_center_height matches manual average of four corners."""
    elevations = {
        (0, 0): 0,
        (1, 0): 0,
        (0, 1): 0,
        (1, 1): 0,
        (2, 0): 7,
        (0, 2): 7,
        (2, 2): 7,
    }
    tm = _make_tile_map(elevations, width=3, height=3)

    # Manual average of four corners for tile (1, 1)
    h_nw = tm.get_corner_height(1, 1)
    h_ne = tm.get_corner_height(2, 1)
    h_sw = tm.get_corner_height(1, 2)
    h_se = tm.get_corner_height(2, 2)
    manual_avg = (h_nw + h_ne + h_sw + h_se) / 4.0

    # Convenience method
    center_h = tm.get_tile_center_height(1, 1)

    assert abs(center_h - manual_avg) < 1e-9, (
        f"Center height ({center_h}) should equal manual avg ({manual_avg})"
    )
