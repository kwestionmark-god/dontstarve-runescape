"""Terrain fog must follow each tile's opaque silhouette.

The textured path used to fill an AABB-inscribed diamond on the warped
sprite's bounding box. At any yaw where the projected tile is a
parallelogram rather than a diamond, that overlay misses the tile and
overlaps neighbours — a checkerboard of stacked/gapped fog. Fog is
composited into the sprite so it covers only opaque terrain pixels and
painter's order overwrites instead of stacking.
"""

import pygame

from render.tile_renderer import TileRenderer


FOG = (135, 206, 235)


def _renderer():
    return TileRenderer(None, pygame.Surface((64, 64)))


def _diamond_sprite(size=64) -> pygame.Surface:
    """Opaque diamond (mid-edge vertices) on a transparent square."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    h = size // 2
    pygame.draw.polygon(s, (80, 100, 70, 255), [
        (h, 0), (size - 1, h), (h, size - 1), (0, h),
    ])
    return s


def _rect_sprite(size=64) -> pygame.Surface:
    """Fully opaque square — AABB corners are terrain, not sky."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    s.fill((80, 100, 70, 255))
    return s


def test_fog_skips_transparent_pixels():
    renderer = _renderer()
    sprite = _diamond_sprite()
    fogged = renderer._composite_sprite_fog(sprite, 180, FOG)

    assert fogged.get_at((0, 0)).a == 0, "AABB corner must stay transparent"
    assert fogged.get_at((63, 0)).a == 0
    assert fogged.get_at((32, 32)).a == 255, "opaque centre must stay opaque"


def test_fog_tints_opaque_pixels_toward_fog_color():
    renderer = _renderer()
    sprite = _diamond_sprite()
    centre = sprite.get_at((32, 32))[:3]
    fogged = renderer._composite_sprite_fog(sprite, 180, FOG)
    out = fogged.get_at((32, 32))[:3]
    # 180/255 ≈ 0.7 of the way from terrain to FOG.
    for i in range(3):
        expected = round(centre[i] * (1 - 180 / 255) + FOG[i] * (180 / 255))
        assert abs(out[i] - expected) <= 3, (
            f"channel {i}: got {out}, expected ~{expected} from {centre}→{FOG}"
        )


def test_fog_covers_opaque_aabb_corners_not_just_a_diamond():
    """A rectangular tile's AABB corners are terrain and must receive fog.

    The old inscribed-diamond overlay left these corners unfogged, which
    is the yaw-0 case of the checkerboard (diamond fog on a square sprite).
    """
    renderer = _renderer()
    sprite = _rect_sprite()
    fogged = renderer._composite_sprite_fog(sprite, 200, FOG)
    corner = fogged.get_at((0, 0))[:3]
    centre = fogged.get_at((32, 32))[:3]
    assert corner[2] > 150, f"AABB corner should be fog-tinted, got {corner}"
    assert abs(corner[0] - centre[0]) <= 2 and abs(corner[2] - centre[2]) <= 2, (
        f"fog must be uniform across opaque pixels, corner={corner} centre={centre}"
    )


def test_zero_alpha_returns_original_pixels():
    renderer = _renderer()
    sprite = _rect_sprite()
    fogged = renderer._composite_sprite_fog(sprite, 0, FOG)
    assert fogged.get_at((32, 32))[:3] == (80, 100, 70)


def test_height_fog_is_applied_once():
    """corner_fog modulates the incoming alpha; the helper must not
    multiply by it again (that was a second 4-corner average on the
    textured path)."""
    renderer = _renderer()
    sprite = _rect_sprite()
    # 100 already includes any height-fog modulation from render().
    fogged = renderer._composite_sprite_fog(sprite, 100, FOG)
    out = fogged.get_at((32, 32))[:3]
    expected_b = round(70 * (1 - 100 / 255) + FOG[2] * (100 / 255))
    assert abs(out[2] - expected_b) <= 3, (
        f"alpha 100 should lerp once, got {out} (blue ~{expected_b})"
    )
