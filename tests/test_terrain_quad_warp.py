"""Tests for render/quad_warp.py and the textured-path terrain warp."""

import pygame

from render.quad_warp import warp_sprite_to_quad


def _solid_sprite(w: int = 32, h: int = 32, color=(120, 140, 90)) -> pygame.Surface:
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(color + (255,))
    return s


def test_warp_flat_quad_matches_axis_aligned_blit():
    """A flat (axis-aligned, unshifted) quad reproduces the sprite footprint."""
    sprite = _solid_sprite(32, 16)
    quad = [(0, 0), (32, 0), (32, 16), (0, 16)]
    result = warp_sprite_to_quad(sprite, *quad)
    assert result is not None
    out, ox, oy = result
    assert (ox, oy) == (0, 0)
    # Covering the quad: allowed +2 seam overdraw per strip horizontally.
    assert abs(out.get_width() - 32) <= 2
    assert abs(out.get_height() - 16) <= 2
    # Interior pixels are filled.
    assert out.get_at((out.get_width() // 2, out.get_height() // 2))[:3] == (120, 140, 90)


def test_warp_shifts_output_to_quad_position():
    """Warped surface is positioned at the quad's bounding-box origin."""
    sprite = _solid_sprite(32, 32)
    quad = [(100, 40), (140, 40), (140, 80), (100, 80)]
    out, ox, oy = warp_sprite_to_quad(sprite, *quad)
    assert (ox, oy) == (100, 40)


def test_warp_sloped_quad_stretches_vertical_extent():
    """A quad whose bottom corners sit lower (uphill north edge) yields a
    taller output than the flat footprint — the visual relief effect."""
    sprite = _solid_sprite(32, 16)
    flat_h = warp_sprite_to_quad(sprite, (0, 0), (32, 0), (32, 16), (0, 16))[0].get_height()
    # South corners displaced 24px down (i.e. lower elevation toward camera)
    sloped = warp_sprite_to_quad(sprite, (0, 0), (32, 0), (32, 40), (0, 40))
    assert sloped is not None
    out, ox, oy = sloped
    assert out.get_height() > flat_h + 12
    # Top edge stays anchored at the quad's top.
    assert oy == 0


def test_warp_preserves_source_content_rows():
    """Top of the sprite lands near the top edge of the quad, bottom near
    the bottom — strips map in order."""
    sprite = pygame.Surface((16, 16), pygame.SRCALPHA)
    sprite.fill((255, 0, 0, 255), rect=pygame.Rect(0, 0, 16, 8))      # top half red
    sprite.fill((0, 0, 255, 255), rect=pygame.Rect(0, 8, 16, 8))      # bottom half blue
    out, ox, oy = warp_sprite_to_quad(sprite, (0, 0), (16, 0), (16, 32), (0, 32))
    mid = out.get_width() // 2
    top_px = out.get_at((mid, 2))
    bottom_px = out.get_at((mid, out.get_height() - 4))
    assert top_px.r > 200 and top_px.b < 60, f"top should be red, got {top_px}"
    assert bottom_px.b > 150, f"bottom should be bluish, got {bottom_px}"


def test_warp_degenerate_quad_returns_none():
    """Zero-area quad must not produce a surface (caller falls back)."""
    sprite = _solid_sprite()
    assert warp_sprite_to_quad(sprite, (5, 5), (5, 5), (5, 5), (5, 5)) is None


def test_warp_transparent_regions_stay_transparent():
    """Sprite alpha silhouette is preserved (no opaque fill in corners)."""
    sprite = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(sprite, (90, 160, 80, 255), (16, 16), 12)
    out, _, _ = warp_sprite_to_quad(sprite, (0, 0), (32, 0), (32, 32), (0, 32))
    # Far corner of the output should be fully transparent.
    assert out.get_at((1, 1)).a == 0


def test_textured_cache_key_includes_corner_heights():
    """Tiles with identical shading but different corner heights must not
    share a cached warped sprite."""
    import math
    from unittest import mock
    from render.tile_renderer import TileRenderer

    screen = pygame.Surface((200, 200))
    cam = mock.MagicMock()
    cam.zoom, cam.pitch, cam.yaw = 1.0, 0.5, 0.0
    cam.world_to_screen = lambda wx, wy, elevation=0.0: (wx + 50, wy + 50 - elevation)

    tile_map = mock.MagicMock()
    heights = {(0, 0): 0.0, (1, 0): 0.0, (0, 1): 0.0, (1, 1): 0.0}
    tile_map.get_corner_height = lambda cx, cy: heights.get((cx, cy), 0.0)
    tile_map.get_tile_center_height = lambda tx, ty: math.fsum(
        heights.get((cx, cy), 0.0) for cx in (tx, tx + 1) for cy in (ty, ty + 1)
    ) / 4.0

    renderer = TileRenderer(tile_map, screen)
    sprite = _solid_sprite(64, 64)
    renderer._terrain_cache["forest"] = sprite

    tile = mock.MagicMock()
    tile.terrain_color = (100, 120, 80)

    def render_once():
        renderer._render_tile_textured(
            0, 0, tile, cam, 64, (100, 120, 80), "forest",
            None, None, None, 0, (200, 210, 220), False, 2, True,
        )

    render_once()
    first = set(renderer._xform_cache.keys())
    assert len(first) == 1

    # Raise the south corners — the warped sprite must be rebuilt.
    heights[(0, 1)] = heights[(1, 1)] = 4.0
    render_once()
    keys = set(renderer._xform_cache.keys())
    assert len(keys) == 2, "different corner heights must not share a cache entry"
    assert keys != first
