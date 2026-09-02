"""
render/quad_warp.py — Approximate sprite-to-quad warp for terrain tiles.

pygame has no native perspective/affine quad blit, so a tile sprite is
drawn onto its projected (elevation-displaced) corner quad with a
scanline mapper: each scanline's intersection with the quad is one
texture-mapped segment (a scaled row or column of the source sprite),
so every pixel inside the quad is covered exactly once regardless of
camera yaw. The scan axis follows the quad's orientation — horizontal
scanlines when the tile's side edges are near-vertical on screen,
vertical scanlines when they are near-horizontal — so warped tiles stay
seamless at any rotation, not just near 0°.
"""

from __future__ import annotations

import math

import pygame

# Each edge as (p0, p1, v_fn-style constant/param). For row scanning the
# "v" texture coordinate along an edge is: t on the two side edges, 0 on
# the top edge, 1 on the bottom edge. For column scanning, symmetric u.


def warp_sprite_to_quad(
    sprite: pygame.Surface,
    p_nw: tuple[float, float],
    p_ne: tuple[float, float],
    p_se: tuple[float, float],
    p_sw: tuple[float, float],
) -> tuple[pygame.Surface, int, int] | None:
    """
    Warp `sprite` (un-rotated tile image, already scaled for zoom/pitch)
    into the screen-space quad formed by the four projected corners.

    Returns (surface, offset_x, offset_y) where offset is the blit
    position of the returned surface, or None if the quad is degenerate.
    """
    min_x = min(p_nw[0], p_ne[0], p_se[0], p_sw[0])
    min_y = min(p_nw[1], p_ne[1], p_se[1], p_sw[1])
    max_x = max(p_nw[0], p_ne[0], p_se[0], p_sw[0])
    max_y = max(p_nw[1], p_ne[1], p_se[1], p_sw[1])
    out_w = int(max_x - min_x) + 1
    out_h = int(max_y - min_y) + 1
    if out_w <= 2 or out_h <= 2:
        return None

    out = pygame.Surface((out_w, out_h), pygame.SRCALPHA)

    # Pick the scan axis from the side edges' (NW→SW, NE→SE) dominant
    # direction: if they move mostly in screen-y, scan rows; otherwise
    # scan columns. Keeps each segment near-perpendicular to its own
    # extent at any yaw.
    side_dy = abs(p_sw[1] - p_nw[1]) + abs(p_se[1] - p_ne[1])
    side_dx = abs(p_sw[0] - p_nw[0]) + abs(p_se[0] - p_ne[0])
    if side_dy >= side_dx:
        # Row scanning; edges carry (a, b, tx_fn) where tx_fn(t) = v.
        edges = [
            (p_nw, p_sw, "t"),   # west edge:  v = t
            (p_ne, p_se, "t"),   # east edge:  v = t
            (p_nw, p_ne, "0"),   # north edge: v = 0
            (p_sw, p_se, "1"),   # south edge: v = 1
        ]
        _scan(out, sprite, edges, axis=1, lo=int(min_y), hi=int(max_y),
              off_x=min_x, off_y=min_y,
              n_rows=max(1, round(
                  (math.dist(p_nw, p_sw) + math.dist(p_ne, p_se)) * 0.5)))
    else:
        # Column scanning; edges carry u.
        edges = [
            (p_nw, p_ne, "t"),   # north edge: u = t
            (p_sw, p_se, "t"),   # south edge: u = t
            (p_nw, p_sw, "0"),   # west edge:  u = 0
            (p_ne, p_se, "1"),   # east edge:  u = 1
        ]
        _scan(out, sprite, edges, axis=0, lo=int(min_x), hi=int(max_x),
              off_x=min_x, off_y=min_y,
              n_rows=max(1, round(
                  (math.dist(p_nw, p_ne) + math.dist(p_sw, p_se)) * 0.5)))
    return out, int(min_x), int(min_y)


def _scan(out, sprite, edges, axis, lo, hi, off_x, off_y, n_rows) -> None:
    """
    For each scanline coordinate s in [lo, hi] along `axis` (1=y rows,
    0=x columns), intersect with every quad edge, and draw the segment
    between the outermost intersections as a scaled source row/column.

    The source is first smoothly pre-scaled along the scan axis to
    `n_rows` entries so compressed terrain doesn't show banding from
    snapping scanline texcoords to the original 64 source rows.
    """
    src_w, src_h = sprite.get_size()
    if axis == 1 and n_rows != src_h:
        sprite = pygame.transform.smoothscale(sprite, (src_w, n_rows))
        src_h = n_rows
    elif axis == 0 and n_rows != src_w:
        sprite = pygame.transform.smoothscale(sprite, (n_rows, src_h))
        src_w = n_rows
    other = 1 - axis  # the coordinate perpendicular to the scanline
    # For rows (axis=1): perpendicular is x (offset off_x), scanline is y.
    perp_off = off_x if axis == 1 else off_y
    scan_off = off_y if axis == 1 else off_x

    for s in range(lo, hi + 1):
        hits = []  # (perp_coord, texcoord)
        for a, b, mode in edges:
            span = b[axis] - a[axis]
            if abs(span) < 1e-9:
                continue
            t = (s - a[axis]) / span
            if t < 0.0 or t > 1.0:
                continue
            perp = a[other] + (b[other] - a[other]) * t
            tex = t if mode == "t" else (0.0 if mode == "0" else 1.0)
            hits.append((perp, tex))
        if len(hits) < 2:
            continue
        hits.sort()
        (p0, v0), (p1, v1) = hits[0], hits[-1]
        # 1px overdraw on both sides so rounding seams between tiles are
        # covered by painter's order instead of letting the sky through.
        i0 = int(p0 - perp_off) - 1
        i1 = int(p1 - perp_off) + 2
        if i1 - i0 <= 0:
            continue
        tex = (v0 + v1) * 0.5
        if axis == 1:
            src_i = min(src_h - 1, max(0, int(tex * src_h)))
            strip = sprite.subsurface((0, src_i, src_w, 1))
            seg = pygame.transform.scale(strip, (i1 - i0, 1))
            out.blit(seg, (i0, s - int(scan_off)))
        else:
            src_i = min(src_w - 1, max(0, int(tex * src_w)))
            strip = sprite.subsurface((src_i, 0, 1, src_h))
            seg = pygame.transform.scale(strip, (1, i1 - i0))
            out.blit(seg, (s - int(scan_off), i0))
