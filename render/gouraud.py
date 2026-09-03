"""
render/gouraud.py — Software Gouraud triangle rasterizer for pygame.

Provides a scanline-based triangular Gouraud shader that interpolates
vertex colors across a triangle. This is the primitive used by the
per-vertex terrain renderer (Phase 7 P4) to draw two triangles per tile.

Algorithm: Sort vertices by Y. Split into a flat-bottom half and a
flat-top half. For each scanline, compute interpolated colors at the
left and right edges and fill the row between them using one
``pygame.PixelArray`` row-slice write per scanline.
"""

from __future__ import annotations

import pygame


def fill_triangle(
    surface: pygame.Surface,
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    c0: tuple[int, int, int],
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
) -> None:
    """
    Fill `surface` with the triangle (p0, p1, p2), interpolating vertex
    colors c0/c1/c2 across the triangle.

    Algorithm: scanline-based. Sort vertices by Y. For a generic
    (non-degenerate, non-flat) triangle, split into a flat-bottom half
    and a flat-top half; for each scanline inside, compute the
    interpolated color at the left and right edge and fill the row
    between them.

    Coordinate handling:
    - Treat incoming floats as subpixel coordinates; snap the starting X
      to int with `round()`.
    - Clip the triangle to the surface rect (in pygame coords; +Y goes down).
    - A degenerate triangle (zero area) must not raise — silently draw nothing.
    - A 1-pixel triangle must not crash.

    Color interpolation:
    - Colors are RGB tuples of ints. Interpolate channel-by-channel
      linearly in barycentric/scanline fashion.
    - Round to nearest int at each pixel (don't accumulate rounding error
      across the triangle — recompute from the canonical scanline-end values).

    Note: If profiling shows this is too slow, replace with a per-scanline
    `pygame.Surface.fill`-style band write — but keep the same semantics.
    """
    # Surface bounds for clipping
    surf_w = surface.get_width()
    surf_h = surface.get_height()
    if surf_w == 0 or surf_h == 0:
        return

    # Pack vertices and colors together for sorting
    verts = [(p0[0], p0[1], c0), (p1[0], p1[1], c1), (p2[0], p2[1], c2)]

    # Sort by Y coordinate (ascending: top to bottom in pygame coords)
    verts.sort(key=lambda v: v[1])
    (x0, y0, c0), (x1, y1, c1), (x2, y2, c2) = verts

    # Check for degenerate triangle (zero area)
    # Area = 0.5 * |(x1-x0)*(y2-y0) - (x2-x0)*(y1-y0)|
    area2 = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area2) < 1e-12:
        # Degenerate (collinear or coincident vertices) — draw nothing
        return

    # One PixelArray shared by all scanlines of this triangle — per-scanline
    # (or per-pixel) surface writes dominate the rasterizer's cost otherwise.
    _pa = None

    # Helper to interpolate color between two vertices at parameter t in [0, 1]
    def lerp_color(ca: tuple[int, int, int], cb: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        r = round(ca[0] + (cb[0] - ca[0]) * t)
        g = round(ca[1] + (cb[1] - ca[1]) * t)
        b = round(ca[2] + (cb[2] - ca[2]) * t)
        # Clamp to valid range
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    # Helper to draw a horizontal scanline from x_left to x_right (inclusive)
    # at integer y, with colors cl and cr at the endpoints.
    def draw_scanline(y: int, x_left: float, x_right: float, cl: tuple[int, int, int], cr: tuple[int, int, int]) -> None:
        # Clip Y to surface bounds
        if y < 0 or y >= surf_h:
            return

        # Round X coordinates to pixel centers
        xl = round(x_left)
        xr = round(x_right)

        # Ensure xl <= xr
        if xl > xr:
            xl, xr = xr, xl
            cl, cr = cr, cl

        # Clip X to surface bounds
        if xr < 0 or xl >= surf_w:
            return
        xl_clipped = max(0, xl)
        xr_clipped = min(surf_w - 1, xr)

        if xl_clipped > xr_clipped:
            return

        # If the span is a single pixel, just use the left color (or average)
        span_width = xr - xl
        if span_width == 0:
            _pa[xl_clipped : xl_clipped + 1, y] = [cl]
            return

        # Interpolate color across the scanline, then write the whole row in
        # one PixelArray assignment — per-pixel set_at() calls dominate the
        # cost of this rasterizer, so batch the row into a single C-level copy.
        row = []
        append = row.append
        clr, clg, clb = cl
        crr, crg, crb = cr
        for x in range(xl_clipped, xr_clipped + 1):
            # Recompute t from canonical endpoints to avoid accumulated error
            t = (x - xl) / span_width
            r = round(clr + (crr - clr) * t)
            g = round(clg + (crg - clg) * t)
            b = round(clb + (crb - clb) * t)
            append((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))
        _pa[xl_clipped : xr_clipped + 1, y] = row

    _pa = pygame.PixelArray(surface)

    # Flat-bottom triangle: y0 <= y1 == y2 (but we handle y1 < y2 generally)
    # The split point is at y1. Top half: y0 to y1. Bottom half: y1 to y2.

    # Top half (flat bottom at y1)
    if y1 != y0:
        # Inverse slopes for left and right edges
        # Left edge: (x0, y0) to (x1, y1)
        # Right edge: (x0, y0) to (x2, y2) — but we need to determine which is left/right
        # Actually, we need to find the X on the long edge (x0,y0)-(x2,y2) at each y
        inv_slope_left = (x1 - x0) / (y1 - y0) if y1 != y0 else 0.0
        inv_slope_right = (x2 - x0) / (y2 - y0) if y2 != y0 else 0.0

        # Determine which is actually left/right at the start
        # At y0, both edges start at x0. At y0+1, compare x positions.
        # But since we sorted by Y, we know the middle vertex is at y1.
        # The left edge goes from (x0,y0) to (x1,y1), right edge from (x0,y0) to (x2,y2)
        # UNLESS the middle vertex is to the right of the long edge, in which
        # case the roles swap. We handle this by computing both X positions
        # at each scanline and taking min/max.

        y_start = max(0, int(y0))
        y_end = min(surf_h - 1, int(y1))

        for y in range(y_start, y_end + 1):
            # Compute t along each edge
            t_left = (y - y0) / (y1 - y0) if y1 != y0 else 0.0
            t_right = (y - y0) / (y2 - y0) if y2 != y0 else 0.0

            # Clamp t to [0, 1]
            t_left = max(0.0, min(1.0, t_left))
            t_right = max(0.0, min(1.0, t_right))

            # X positions on left and right edges
            x_left = x0 + (x1 - x0) * t_left
            x_right = x0 + (x2 - x0) * t_right

            # Colors at left and right edges
            cl = lerp_color(c0, c1, t_left)
            cr = lerp_color(c0, c2, t_right)

            # Ensure left <= right
            if x_left > x_right:
                x_left, x_right = x_right, x_left
                cl, cr = cr, cl

            draw_scanline(y, x_left, x_right, cl, cr)

    # Bottom half (flat top at y1)
    if y2 != y1:
        # Left edge: (x1, y1) to (x2, y2)
        # Right edge: (x0, y0) to (x2, y2) — the long edge
        y_start = max(0, int(y1))
        y_end = min(surf_h - 1, int(y2))

        for y in range(y_start, y_end + 1):
            # Compute t along each edge
            t_left = (y - y1) / (y2 - y1) if y2 != y1 else 0.0
            t_right = (y - y0) / (y2 - y0) if y2 != y0 else 0.0

            t_left = max(0.0, min(1.0, t_left))
            t_right = max(0.0, min(1.0, t_right))

            x_left = x1 + (x2 - x1) * t_left
            x_right = x0 + (x2 - x0) * t_right

            cl = lerp_color(c1, c2, t_left)
            cr = lerp_color(c0, c2, t_right)

            if x_left > x_right:
                x_left, x_right = x_right, x_left
                cl, cr = cr, cl

            draw_scanline(y, x_left, x_right, cl, cr)

    _pa.close()


if __name__ == "__main__":
    # Quick manual test
    pygame.init()
    screen = pygame.display.set_mode((64, 64))
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)

    fill_triangle(surf, (10, 10), (50, 10), (30, 50), (255, 0, 0), (0, 255, 0), (0, 0, 255))

    screen.blit(surf, (0, 0))
    pygame.display.flip()

    import time
    time.sleep(2)
    pygame.quit()