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

# Pixels each quad is dilated outward so neighbouring tiles overlap and
# rounding never opens seams. Back-to-front painter's order resolves the
# overlap.
TILE_OVERLAP = 2.0

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
    # Dilate the quad: push each corner away from the centroid so the
    # tile slightly overpaints its neighbours' edges (stitching).
    cx = (p_nw[0] + p_ne[0] + p_se[0] + p_sw[0]) * 0.25
    cy = (p_nw[1] + p_ne[1] + p_se[1] + p_sw[1]) * 0.25

    def dilate(p):
        dx, dy = p[0] - cx, p[1] - cy
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return p
        k = (d + TILE_OVERLAP) / d
        return (cx + dx * k, cy + dy * k)

    p_nw, p_ne, p_se, p_sw = dilate(p_nw), dilate(p_ne), dilate(p_se), dilate(p_sw)

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
    import numpy as np

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

    src_rgb = pygame.surfarray.array3d(sprite)      # (w, h, 3)
    src_alpha = pygame.surfarray.array_alpha(sprite)  # (w, h)

    # Intersect every scanline with every edge in one vectorized pass.
    # Scanlines are anchored to the output surface extent (lo/hi can
    # exceed it by one due to independent truncation of min/max).
    out_w, out_h = out.get_size()
    n_scan = out_h if axis == 1 else out_w
    s = np.arange(int(lo), int(lo) + n_scan)

    # Edge geometry as (4, n_scan) arrays; NaN marks scanlines an edge
    # does not touch.
    a_ax = np.empty(4)
    b_ax = np.empty(4)
    a_ot = np.empty(4)
    b_ot = np.empty(4)
    mode = np.empty(4, dtype=np.int8)  # 0=tex 0, 1=tex t, 2=tex 1
    for e, (a, b, m) in enumerate(edges):
        a_ax[e] = a[axis]
        b_ax[e] = b[axis]
        a_ot[e] = a[other]
        b_ot[e] = b[other]
        mode[e] = 1 if m == "t" else (0 if m == "0" else 2)
    span = b_ax - a_ax
    small = np.abs(span) < 1e-9
    span = np.where(small, 1.0, span)
    t = (s[None, :] - a_ax[:, None]) / span[:, None]
    valid = (~small)[:, None] & (t >= 0.0) & (t <= 1.0)
    perp = a_ot[:, None] + (b_ot - a_ot)[:, None] * t
    texc = np.where(mode[:, None] == 1, t,
                    np.where(mode[:, None] == 0, 0.0, 1.0))
    perp_min = np.where(valid, perp, np.inf)
    perp_max = np.where(valid, perp, -np.inf)

    lo_idx = np.argmin(perp_min, axis=0)
    hi_idx = np.argmax(perp_max, axis=0)
    cols_scan = np.arange(n_scan)
    perp_lo = perp_min[lo_idx, cols_scan]
    perp_hi = perp_max[hi_idx, cols_scan]
    tex_lo = texc[lo_idx, cols_scan]
    tex_hi = texc[hi_idx, cols_scan]
    ok = valid.sum(axis=0) >= 2

    # 1px overdraw on both sides so rounding seams between tiles are
    # covered by painter's order instead of letting the sky through.
    i0 = np.clip(perp_lo - perp_off, -1e6, 1e6).astype(np.int64) - 1
    i1 = np.clip(perp_hi - perp_off, -1e6, 1e6).astype(np.int64) + 2
    ok &= np.isfinite(perp_lo) & np.isfinite(perp_hi)
    ok &= i1 > i0

    if not np.any(ok):
        return

    src_len = src_h if axis == 1 else src_w
    src_i = np.clip(((tex_lo + tex_hi) * 0.5 * src_len).astype(np.int64),
                    0, src_len - 1)

    seg_w = np.maximum(i1 - i0, 1)

    if axis == 1:
        # Scanline s is a row; perpendicular extent runs along x.
        rel = np.arange(out_w)[None, :] - i0[:, None]
        mask = ok[:, None] & (rel >= 0) & (rel < seg_w[:, None])
        cols = np.clip((rel * src_w) // seg_w[:, None], 0, src_w - 1)
        # surfarray layout is (x, y): scanline rows run along axis 1.
        rgb = src_rgb[cols, src_i[:, None]].transpose(1, 0, 2)
        alpha = src_alpha[cols, src_i[:, None]].transpose(1, 0)
        alpha[~mask.T] = 0
    else:
        # Scanline s is a column; perpendicular extent runs along y.
        rel = np.arange(out_h)[None, :] - i0[:, None]
        mask = ok[:, None] & (rel >= 0) & (rel < seg_w[:, None])
        rows_idx = np.clip((rel * src_h) // seg_w[:, None], 0, src_h - 1)
        cols = np.broadcast_to(src_i[:, None], rows_idx.shape)
        rgb = src_rgb[cols, rows_idx]
        alpha = src_alpha[cols, rows_idx]
        alpha[~mask] = 0

    pygame.surfarray.blit_array(out, rgb)
    px_alpha = pygame.surfarray.pixels_alpha(out)
    px_alpha[:, :] = alpha
    del px_alpha
