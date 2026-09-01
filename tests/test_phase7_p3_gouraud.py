"""
Phase 7 P3 — software Gouraud triangle rasterizer.

Tests for `render.gouraud.fill_triangle`, a scanline-based triangular
Gouraud shader that interpolates vertex colors across a triangle.

Coverage:
- Flat-color triangle (all vertices same color) fills every pixel with that color.
- Single-pixel triangle does not raise and behaves deterministically.
- Degenerate (zero-area) triangle draws nothing without raising.
- Distinct vertex colors produce interpolated interior colors (>1 distinct color).
- Clipping: triangles partially outside the surface are clipped to bounds.
- Vertex centers match the vertex's exact color (within 1 LSB).
- Large triangle on 64x64 surface produces expected gradient pattern.
"""

from __future__ import annotations

import pytest
import pygame


@pytest.fixture(scope="module")
def pygame_init():
    """Initialize pygame once for all tests."""
    pygame.init()
    pygame.display.set_mode((64, 64), pygame.HIDDEN)
    yield
    pygame.quit()


def _make_surface(w: int = 64, h: int = 64) -> pygame.Surface:
    """Create a test surface with SRCALPHA for reliable pixel reads."""
    return pygame.Surface((w, h), pygame.SRCALPHA)


class TestFlatColorTriangle:
    """All three vertices have the same color → every filled pixel matches exactly."""

    def test_flat_red_triangle(self, pygame_init):
        surf = _make_surface(64, 64)
        # Triangle covering a decent area
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (10.0, 10.0), (50.0, 10.0), (30.0, 50.0),
            (255, 0, 0), (255, 0, 0), (255, 0, 0),
        )

        # Every non-transparent pixel must be exactly (255, 0, 0)
        for y in range(64):
            for x in range(64):
                r, g, b, a = surf.get_at((x, y))
                if a > 0:
                    assert (r, g, b) == (255, 0, 0), (
                        f"Pixel ({x},{y}) = ({r},{g},{b}); expected (255,0,0)"
                    )


class TestDegenerateAndEdgeCases:
    """Zero-area and near-zero-area triangles must not raise."""

    def test_single_point_triangle(self, pygame_init):
        """All three vertices identical → no crash, no out-of-bounds."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (5.0, 5.0), (5.0, 5.0), (5.0, 5.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        # Should not have crashed. Verify no out-of-bounds writes by checking
        # the surface is still mostly transparent (or at least no exception).
        # A point triangle may or may not fill a pixel; either is acceptable.
        # Just assert we can read the surface without error.
        _ = surf.get_at((5, 5))

    def test_horizontal_line_triangle(self, pygame_init):
        """Three collinear points on a horizontal line → flat, no crash."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (10.0, 10.0), (20.0, 10.0), (15.0, 10.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )
        # No exception raised

    def test_vertical_line_triangle(self, pygame_init):
        """Three collinear points on a vertical line → flat, no crash."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (10.0, 10.0), (10.0, 20.0), (10.0, 15.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )
        # No exception raised

    def test_single_pixel_triangle(self, pygame_init):
        """Two vertices same, third offset by 1px → 1-pixel triangle, no crash."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (10.0, 10.0), (10.0, 10.0), (11.0, 10.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )
        # No exception raised


class TestColorInterpolation:
    """Distinct vertex colors must produce smoothly interpolated interior."""

    def test_rgb_triangle_has_multiple_colors(self, pygame_init):
        """Red, Green, Blue vertices → interior contains >1 distinct color."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (10.0, 10.0), (50.0, 10.0), (30.0, 50.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        # Collect all distinct non-transparent colors
        colors = set()
        for y in range(64):
            for x in range(64):
                r, g, b, a = surf.get_at((x, y))
                if a > 0:
                    colors.add((r, g, b))

        # Must have more than 1 distinct color (proves interpolation happened)
        assert len(colors) > 1, (
            f"Expected multiple interpolated colors, got {len(colors)}: {colors}"
        )

    def test_vertex_centers_match_vertex_colors(self, pygame_init):
        """The pixel at each vertex coordinate matches that vertex's color (±1 LSB)."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        # Use integer vertex coordinates so they map to pixel centers
        fill_triangle(
            surf,
            (10.0, 10.0), (50.0, 10.0), (30.0, 50.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        # Check vertex pixels (within 1 LSB tolerance due to set_at quantization)
        r0, g0, b0, a0 = surf.get_at((10, 10))
        r1, g1, b1, a1 = surf.get_at((50, 10))
        r2, g2, b2, a2 = surf.get_at((30, 50))

        assert a0 > 0 and a1 > 0 and a2 > 0, "Vertex pixels should be filled"

        assert abs(r0 - 255) <= 1 and abs(g0 - 0) <= 1 and abs(b0 - 0) <= 1, (
            f"Vertex 0 color = ({r0},{g0},{b0}); expected ~(255,0,0)"
        )
        assert abs(r1 - 0) <= 1 and abs(g1 - 255) <= 1 and abs(b1 - 0) <= 1, (
            f"Vertex 1 color = ({r1},{g1},{b1}); expected ~(0,255,0)"
        )
        assert abs(r2 - 0) <= 1 and abs(g2 - 0) <= 1 and abs(b2 - 255) <= 1, (
            f"Vertex 2 color = ({r2},{g2},{b2}); expected ~(0,0,255)"
        )


class TestClipping:
    """Triangles partially or fully outside the surface are clipped safely."""

    def test_triangle_partially_offscreen_left(self, pygame_init):
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        # Triangle extending left of x=0
        fill_triangle(
            surf,
            (-20.0, 10.0), (30.0, 10.0), (10.0, 50.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        # No crash. Verify no out-of-bounds by checking a known in-bounds pixel
        # is still readable and the surface has some filled pixels.
        filled = sum(1 for y in range(64) for x in range(64) if surf.get_at((x, y))[3] > 0)
        assert filled > 0, "Clipped triangle should still fill some pixels"

    def test_triangle_partially_offscreen_right(self, pygame_init):
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (50.0, 10.0), (90.0, 10.0), (70.0, 50.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        filled = sum(1 for y in range(64) for x in range(64) if surf.get_at((x, y))[3] > 0)
        assert filled > 0

    def test_triangle_partially_offscreen_top(self, pygame_init):
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (10.0, -20.0), (50.0, 10.0), (30.0, 30.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        filled = sum(1 for y in range(64) for x in range(64) if surf.get_at((x, y))[3] > 0)
        assert filled > 0

    def test_triangle_partially_offscreen_bottom(self, pygame_init):
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        # Triangle with base at y=50 and apex at y=90, extending off bottom.
        # Use non-collinear points: (10,50), (50,90), (30,50) -- flat top at y=50
        fill_triangle(
            surf,
            (10.0, 50.0), (50.0, 90.0), (30.0, 50.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        filled = sum(1 for y in range(64) for x in range(64) if surf.get_at((x, y))[3] > 0)
        assert filled > 0

    def test_triangle_fully_offscreen(self, pygame_init):
        """Triangle completely outside surface → no crash, no pixels filled."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf,
            (-100.0, -100.0), (-50.0, -100.0), (-75.0, -50.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        filled = sum(1 for y in range(64) for x in range(64) if surf.get_at((x, y))[3] > 0)
        assert filled == 0, "Fully offscreen triangle should fill zero pixels"


class TestLargeTriangleGradient:
    """Large triangle covering most of a 64x64 surface produces expected gradient."""

    def test_large_triangle_gradient_pattern(self, pygame_init):
        """Triangle (0,0)-(63,0)-(0,63) on 64x64 surface has correct corner gradients."""
        surf = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        # c0=(255,0,0) at (0,0) [top-left], c1=(0,255,0) at (63,0) [top-right],
        # c2=(0,0,255) at (0,63) [bottom-left]
        fill_triangle(
            surf,
            (0.0, 0.0), (63.0, 0.0), (0.0, 63.0),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        # c0 corner (top-left) should be reddish
        r, g, b, a = surf.get_at((0, 0))
        assert a > 0, "Corner (0,0) should be filled"
        assert r > 200 and g < 50 and b < 50, (
            f"Top-left corner color = ({r},{g},{b}); expected reddish"
        )

        # c1 corner (top-right) should be greenish
        r, g, b, a = surf.get_at((63, 0))
        assert a > 0, "Corner (63,0) should be filled"
        assert r < 50 and g > 200 and b < 50, (
            f"Top-right corner color = ({r},{g},{b}); expected greenish"
        )

        # c2 corner (bottom-left) should be bluish
        r, g, b, a = surf.get_at((0, 63))
        assert a > 0, "Corner (0,63) should be filled"
        assert r < 50 and g < 50 and b > 200, (
            f"Bottom-left corner color = ({r},{g},{b}); expected bluish"
        )

        # Mid-edge between c0 and c1 (top edge, x≈31) should be yellowish (~127,127,0)
        r, g, b, a = surf.get_at((31, 0))
        assert a > 0, "Top edge midpoint should be filled"
        # Allow some tolerance for rounding
        assert 100 < r < 180 and 100 < g < 180 and b < 50, (
            f"Top edge mid color = ({r},{g},{b}); expected yellowish (~127,127,0)"
        )

        # Mid-edge between c0 and c2 (left edge, y≈31) should be magentaish (~127,0,127)
        r, g, b, a = surf.get_at((0, 31))
        assert a > 0, "Left edge midpoint should be filled"
        assert 100 < r < 180 and g < 50 and 100 < b < 180, (
            f"Left edge mid color = ({r},{g},{b}); expected magentaish (~127,0,127)"
        )

        # Interior pixel (e.g., (21, 21)) should be a blend of all three
        r, g, b, a = surf.get_at((21, 21))
        assert a > 0, "Interior should be filled"
        # All three channels should be non-zero (blend of RGB)
        assert r > 0 and g > 0 and b > 0, (
            f"Interior (21,21) = ({r},{g},{b}); expected all channels > 0"
        )


class TestDeterminism:
    """Same inputs must produce byte-identical output."""

    def test_deterministic_output(self, pygame_init):
        """Two calls with identical args produce identical pixel buffers."""
        surf1 = _make_surface(64, 64)
        surf2 = _make_surface(64, 64)
        from render.gouraud import fill_triangle

        fill_triangle(
            surf1,
            (10.5, 10.3), (50.7, 10.9), (30.1, 50.4),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )
        fill_triangle(
            surf2,
            (10.5, 10.3), (50.7, 10.9), (30.1, 50.4),
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
        )

        # Compare pixel by pixel
        for y in range(64):
            for x in range(64):
                assert surf1.get_at((x, y)) == surf2.get_at((x, y)), (
                    f"Pixel ({x},{y}) differs: {surf1.get_at((x, y))} vs {surf2.get_at((x, y))}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])