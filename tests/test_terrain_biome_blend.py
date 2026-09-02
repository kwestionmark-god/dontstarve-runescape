"""Tests for biome boundary blending in the textured terrain path."""

import pygame

from render.tile_renderer import TileRenderer


def _solid_sprite(size=(64, 64), color=(100, 120, 80)) -> pygame.Surface:
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill(color + (255,))
    return s


def _renderer_with_sprite():
    screen = pygame.Surface((256, 256))
    renderer = TileRenderer(None, screen)
    renderer._terrain_cache["forest"] = _solid_sprite()
    return renderer


def test_blend_pulls_edge_toward_neighbor_color():
    """Pixels at the shared edge move toward the neighbour's color."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    before_w = sprite.get_at((0, sprite.get_height() // 2))[:3]

    renderer._bake_biome_blending(sprite, {"W": (220, 60, 60)})

    edge = sprite.get_at((0, sprite.get_height() // 2))[:3]
    center = sprite.get_at((sprite.get_width() // 2, sprite.get_height() // 2))[:3]
    assert before_w == (100, 120, 80)
    # Edge pulled substantially toward red.
    assert edge[0] > 140, f"edge should redden toward neighbour, got {edge}"
    # Center essentially untouched (blend reach is the outer third).
    dr = abs(center[0] - 100)
    assert dr < 10, f"center should be (almost) unchanged, got {center}"


def test_blend_two_edges_meet_at_corner():
    """A corner bordered by two differing biomes blends from both sides."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    renderer._bake_biome_blending(sprite, {"W": (220, 60, 60), "N": (60, 60, 220)})

    sw = sprite.get_at((1, 1))[:3]  # NW corner region
    # Should show both red (from W) and blue (from N) contributions.
    assert sw[0] > 100 and sw[2] > 100, f"corner should mix both neighbours, got {sw}"


def test_blend_preserves_alpha():
    """Alpha silhouette must not be modified by the blend pass."""
    sprite = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(sprite, (100, 120, 80, 255), (16, 16, 32, 32))
    renderer = _renderer_with_sprite()
    renderer._bake_biome_blending(sprite, {"N": (200, 200, 200)})
    assert sprite.get_at((0, 0)).a == 0, "transparent corner must stay transparent"
    assert sprite.get_at((32, 32)).a == 255


def test_blend_no_op_with_empty_colors():
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    renderer._bake_biome_blending(sprite, {})
    assert sprite.get_at((0, 0))[:3] == (100, 120, 80)
    assert sprite.get_at((32, 32))[:3] == (100, 120, 80)
