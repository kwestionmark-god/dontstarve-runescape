"""Tests for biome boundary blending in the textured terrain path.

The blend is a texture splat over the 3×3 tile neighbourhood: every
tile (this one + 8 neighbours) contributes its terrain sprite — sampled
at the same local coordinates — with a bilinear tent weight
``max(0, 1-|dx|)·max(0, 1-|dy|)``. Border pixels are a 50/50 crossfade
of the two biome textures (mirrored by the neighbour's own bake), and
the function returns the per-pixel blended colour field for the shading
pass.
"""

import numpy as np
import pygame

from render.tile_renderer import TileRenderer


FOREST = (100, 120, 80)
RED = (220, 60, 60)
BLUE = (60, 60, 220)
YELLOW = (200, 200, 50)
ALL_DIRS = ("N", "S", "W", "E", "NW", "NE", "SW", "SE")


def _solid_sprite(size=(64, 64), color=FOREST) -> pygame.Surface:
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill(color + (255,))
    return s


def _renderer_with_sprite():
    screen = pygame.Surface((256, 256))
    renderer = TileRenderer(None, screen)
    renderer._terrain_cache["forest"] = _solid_sprite()
    return renderer


def _colors(**overrides):
    """Full 8-direction colour map, defaulting to the own tile colour."""
    colors = {d: FOREST for d in ALL_DIRS}
    colors.update(overrides)
    return colors


def test_splat_w_neighbour_crossfades_texture():
    """A differing W neighbour's sprite crossfades across the border."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    red = _solid_sprite(color=RED)

    color_field = renderer._bake_biome_blending(
        sprite, FOREST, _colors(W=RED), {"W": red},
    )

    # Border pixel is roughly the 50/50 crossfade of both sprites.
    west = sprite.get_at((0, 32))[:3]
    assert west[0] >= 140, f"W border should be ~half red, got {west}"
    assert west[2] <= 80, f"W border should lose most green-blue, got {west}"

    # Gradient: redness falls off monotonically from the edge inward.
    inner = sprite.get_at((16, 32))[:3]
    centre = sprite.get_at((32, 32))[:3]
    assert west[0] > inner[0] > centre[0], (
        f"blend should fall off monotonically, got west={west} inner={inner} centre={centre}"
    )

    # Far side of the tile is untouched.
    east = sprite.get_at((63, 32))[:3]
    assert abs(east[0] - FOREST[0]) <= 3, f"E edge should be unchanged, got {east}"

    # Colour field present and consistent: centre ≈ own colour.
    assert color_field is not None and color_field.shape == (64, 64, 3)
    assert abs(color_field[32, 32, 0] - FOREST[0]) <= 5, (
        f"centre field should be the own colour, got {color_field[32, 32]}"
    )


def test_splat_is_isotropic():
    """Equal in-tile distances from a differing edge blend equally."""
    renderer = _renderer_with_sprite()
    sprite_w = _solid_sprite()
    renderer._bake_biome_blending(
        sprite_w, FOREST, _colors(W=RED), {"W": _solid_sprite(color=RED)},
    )
    sprite_s = _solid_sprite()
    renderer._bake_biome_blending(
        sprite_s, FOREST, _colors(S=RED), {"S": _solid_sprite(color=RED)},
    )

    a = sprite_w.get_at((8, 32))[:3]
    b = sprite_s.get_at((32, 56))[:3]
    assert abs(a[0] - b[0]) <= 6, f"radial field should be isotropic, got {a} vs {b}"


def test_splat_corner_rounds_when_two_edges_differ():
    """W + N differing: NW corner pulls toward both, rounding the corner."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    renderer._bake_biome_blending(
        sprite, FOREST, _colors(W=RED, N=BLUE),
        {"W": _solid_sprite(color=RED), "N": _solid_sprite(color=BLUE)},
    )

    nw = sprite.get_at((0, 0))[:3]
    assert nw[0] >= 105 and nw[2] >= 95, f"NW corner should mix W+N, got {nw}"

    # Mid-W-edge favours red; mid-N-edge favours blue.
    w_side = sprite.get_at((0, 32))[:3]
    n_side = sprite.get_at((32, 0))[:3]
    assert w_side[0] > w_side[2], f"W side should be red-dominant, got {w_side}"
    assert n_side[2] > n_side[0], f"N side should be blue-dominant, got {n_side}"


def test_splat_diag_neighbour_pulls_corner():
    """A differing NW diagonal neighbour's texture tints the NW corner."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    renderer._bake_biome_blending(
        sprite, FOREST, _colors(NW=YELLOW), {"NW": _solid_sprite(color=YELLOW)},
    )

    nw = sprite.get_at((0, 0))[:3]
    assert nw[0] > FOREST[0] + 5 and nw[1] > FOREST[1] + 5, (
        f"NW corner should pull toward yellow, got {nw}"
    )

    se = sprite.get_at((63, 63))[:3]
    assert abs(se[0] - FOREST[0]) <= 3 and abs(se[1] - FOREST[1]) <= 3, (
        f"SE corner should be unchanged, got {se}"
    )


def test_splat_centre_near_unchanged():
    """The tile centre stays (almost) its native texture."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    renderer._bake_biome_blending(
        sprite,
        FOREST,
        _colors(W=RED, N=BLUE, NW=YELLOW),
        {
            "W": _solid_sprite(color=RED),
            "N": _solid_sprite(color=BLUE),
            "NW": _solid_sprite(color=YELLOW),
        },
    )
    centre = sprite.get_at((32, 32))[:3]
    for got, want in zip(centre, FOREST):
        assert abs(got - want) <= 8, f"centre should stay near {FOREST}, got {centre}"


def test_splat_missing_sprite_falls_back_to_flat_colour():
    """A neighbour without a sprite contributes its flat biome colour."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    color_field = renderer._bake_biome_blending(
        sprite, FOREST, _colors(W=RED), {"W": None},
    )
    west = sprite.get_at((0, 32))[:3]
    assert west[0] >= 140, f"W border should redden via flat colour, got {west}"
    assert color_field is not None


def test_splat_preserves_alpha():
    """Alpha silhouette must not be modified by the splat pass."""
    sprite = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(sprite, (100, 120, 80, 255), (16, 16, 32, 32))
    renderer = _renderer_with_sprite()
    renderer._bake_biome_blending(
        sprite, FOREST, _colors(N=RED), {"N": _solid_sprite(color=RED)},
    )
    assert sprite.get_at((0, 0)).a == 0, "transparent corner must stay transparent"
    assert sprite.get_at((32, 32)).a == 255


def test_splat_no_op_returns_none():
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    assert renderer._bake_biome_blending(sprite, FOREST, {}) is None
    assert sprite.get_at((0, 0))[:3] == FOREST

    sprite = _solid_sprite()
    assert renderer._bake_biome_blending(sprite, FOREST, _colors()) is None
    assert sprite.get_at((32, 32))[:3] == FOREST


def test_splat_quarter_tile_still_shows_neighbour():
    """Bilinear tent keeps a real neighbour share a quarter-tile in.

    The old circular RBF (k=32, r=0.5) had already decayed to ~12% by
    16px, so biome borders still read as a square grid. At u=0.25 the
    tent is 25% neighbour → red channel ≈ 130 on a forest/red pair.
    """
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    renderer._bake_biome_blending(
        sprite, FOREST, _colors(W=RED), {"W": _solid_sprite(color=RED)},
    )
    inner = sprite.get_at((16, 32))[:3]
    assert inner[0] >= 124, (
        f"16px from W edge should still show neighbour, got {inner}"
    )
    centre = sprite.get_at((32, 32))[:3]
    assert inner[0] > centre[0], (
        f"neighbour share must fall toward centre, inner={inner} centre={centre}"
    )


def test_splat_same_biome_neighbour_keeps_texture():
    """A same-biome neighbour contributes this tile's texture, not a flat
    fill — otherwise the orthogonal edge opposite a biome change washes
    out to solid colour and seams against the unblended neighbour."""
    renderer = _renderer_with_sprite()
    sprite = _solid_sprite()
    # Distinct stripe along the north edge of the own texture.
    pygame.draw.rect(sprite, (20, 200, 20, 255), (0, 0, 64, 4))
    renderer._bake_biome_blending(
        sprite, FOREST, _colors(W=RED), {"W": _solid_sprite(color=RED)},
    )
    north = sprite.get_at((32, 1))[:3]
    # Flat-colour fallback for the same-biome N neighbour would 50/50 the
    # stripe with FOREST green (≈160). Sampling this tile's texture for
    # that neighbour keeps the stripe intact.
    assert north[1] >= 185, (
        f"N edge (same-biome) should keep the green stripe, got {north}"
    )
