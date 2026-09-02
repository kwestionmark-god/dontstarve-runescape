"""
render/quad_warp.py — Approximate sprite-to-quad warp for terrain tiles.

pygame has no native perspective/affine quad blit, so a tile sprite is
drawn onto its projected (elevation-displaced) corner quad by slicing it
into horizontal strips. Each strip spans the quad between the two side
edges at parameters t0..t1 and is drawn as a scaled copy of the matching
source rows. With back-to-front painter's order and small overdraw the
strip seams are invisible, and the terrain surface visibly drapes over
the heightfield instead of floating as flat, undistorted sprites.
"""

from __future__ import annotations

import pygame

# Number of horizontal strips per warped tile. Higher = smoother curves,
# lower = fewer scale+blit calls per tile.
WARP_STRIPS = 6


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def warp_sprite_to_quad(
    sprite: pygame.Surface,
    p_nw: tuple[float, float],
    p_ne: tuple[float, float],
    p_se: tuple[float, float],
    p_sw: tuple[float, float],
    strips: int = WARP_STRIPS,
) -> tuple[pygame.Surface, int, int] | None:
    """
    Warp `sprite` (a north-up, yaw-rotated, pitch-squashed tile image)
    into the screen-space quad formed by the four projected corners.

    Returns (surface, offset_x, offset_y) where offset is the blit
    position of the returned surface, or None if the quad is degenerate
    (caller should fall back to a plain blit).
    """
    min_x = min(p_nw[0], p_ne[0], p_se[0], p_sw[0])
    min_y = min(p_nw[1], p_ne[1], p_se[1], p_sw[1])
    max_x = max(p_nw[0], p_ne[0], p_se[0], p_sw[0])
    max_y = max(p_nw[1], p_ne[1], p_se[1], p_sw[1])
    out_w = int(max_x - min_x) + 1
    out_h = int(max_y - min_y) + 1
    if out_w <= 1 or out_h <= 1:
        return None

    src_w, src_h = sprite.get_size()
    # Source rows must stay inside the unrotated footprint; the caller's
    # sprite carries a few pixels of overdraw margin beyond the tile.
    strip_h = max(1, src_h // strips)

    out = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
    for i in range(strips):
        t1 = (i + 1) / strips
        # Side-edge points at the strip's bottom parameter (overlap the
        # previous strip's top by drawing from the same src row band).
        l1 = _lerp(p_nw, p_sw, t1)
        r1 = _lerp(p_ne, p_se, t1)
        if i == 0:
            l0, r0 = p_nw, p_ne
        else:
            t0 = i / strips
            l0 = _lerp(p_nw, p_sw, t0)
            r0 = _lerp(p_ne, p_se, t0)

        x_left = min(l0[0], l1[0])
        x_right = max(r0[0], r1[0])
        y_top = min(l0[1], r0[1])
        y_bot = max(l1[1], r1[1])

        band_w = int(x_right - x_left) + 2  # +2: hide strip seams
        band_h = int(y_bot - y_top) + 2
        if band_w <= 0 or band_h <= 0:
            continue

        y0 = i * strip_h
        # Last strip takes the remainder of the source rows.
        y1 = src_h if i == strips - 1 else (i + 1) * strip_h
        if y1 <= y0:
            continue
        band_src = sprite.subsurface((0, y0, src_w, y1 - y0))
        band = pygame.transform.smoothscale(band_src, (band_w, band_h))
        out.blit(band, (int(x_left - min_x), int(y_top - min_y)))

    return out, int(min_x), int(min_y)
