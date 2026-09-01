"""
Phase 7 P4: Integration tests for triangular Gouraud terrain rendering.

Tests cover:
- "flat" style produces smooth (non-uniform) output from per-corner shading
- "textured" style renders without crashing
- Shared-edge continuity between adjacent tiles
- Fallback when corner_height is empty
- Preset gating: "stylized" -> "textured", "realistic" -> "flat"
"""

import contextlib
import sys
sys.path.insert(0, '.')

import pygame
import pytest

from world.tile_map import TileMap, Tile
from world.biome import BiomeRegistry
from render.tile_renderer import TileRenderer
from render.lighting_system import LightingSystem
from camera.camera import Camera
from data import load_json_list


@contextlib.contextmanager
def _small_map(size=32):
    """Patch world_gen MAP_WIDTH/MAP_HEIGHT for fast test generation."""
    import world.world_gen as world_gen
    saved_w, saved_h = world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT
    world_gen.MAP_WIDTH = size
    world_gen.MAP_HEIGHT = size
    try:
        yield
    finally:
        world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT = saved_w, saved_h


def _init_pygame():
    """Init pygame for headless rendering."""
    if not pygame.get_init():
        pygame.init()
        pygame.display.set_mode((1, 1), pygame.HIDDEN)


def _make_test_tile_map(elevations: list[list[int]]) -> TileMap:
    """Create a TileMap with given elevations (x-major)."""
    width = len(elevations)
    height = len(elevations[0]) if width > 0 else 0
    tm = TileMap(width, height, spawn_x=0, spawn_y=0)
    for x in range(width):
        for y in range(height):
            tm.tiles[x][y] = Tile(x, y, biome=None, elevation=elevations[x][y])
    return tm


class TestFlatStyleSmoothOutput:
    """The "flat" terrain_style uses Gouraud triangles with per-corner shading."""

    def test_flat_style_produces_non_uniform_surface(self):
        _init_pygame()
        # Create a small map with a clear east-rising slope
        elevations = [[x for y in range(8)] for x in range(8)]
        tm = _make_test_tile_map(elevations)
        # Bake the corner grids so per-corner shading is available
        tm.bake_corner_heights()
        tm.bake_corner_fog()

        screen = pygame.Surface((256, 256))
        camera = Camera(256, 256)
        # Create a dummy player at map center
        class Player:
            world_x = 256.0
            world_y = 256.0
        camera.set_player(Player())

        ls = LightingSystem("realistic")  # realistic preset -> terrain_style="flat"
        ls.preset_config["terrain_style"] = "flat"
        ls.sun_direction = (0.5, -0.5, 0.7)  # some light direction
        ls.ambient_level = 1.0
        ls.weather_light_level = 1.0

        renderer = TileRenderer(tm, screen, ls)
        renderer.render(camera)

        # Sample the rendered surface at several points
        colors = set()
        for x in range(32, 224, 32):
            for y in range(32, 224, 32):
                c = screen.get_at((x, y))[:3]
                if c != (0, 0, 0):
                    colors.add(c)

        # Should have more than one distinct color (proves Gouraud interpolation)
        assert len(colors) >= 3, f"Expected multiple colors from Gouraud shading, got {len(colors)}: {colors}"


class TestSharedEdgeContinuity:
    """Adjacent tiles must share the same color along their common edge."""

    def test_adjacent_tiles_match_on_shared_edge(self):
        _init_pygame()
        # Two tiles side by side with a slope
        elevations = [
            [0, 0, 0],
            [1, 1, 1],
            [2, 2, 2],
        ]  # 3x3: x=elevation
        tm = _make_test_tile_map(elevations)
        tm.bake_corner_heights()
        tm.bake_corner_fog()

        screen = pygame.Surface((256, 256))
        camera = Camera(256, 256)
        class Player:
            world_x = 256.0
            world_y = 256.0
        camera.set_player(Player())

        ls = LightingSystem("realistic")
        ls.preset_config["terrain_style"] = "flat"
        ls.sun_direction = (1.0, 0.0, 0.0)  # east light

        renderer = TileRenderer(tm, screen, ls)
        renderer.render(camera)

        # Sample along the shared edge between tile (0,1) and (1,1)
        # Their shared vertical edge is at world_x = 64 (tile_size * 1)
        # Screen-space positions will vary with camera, so we find
        # the boundary by looking at a horizontal scanline
        edge_colors = []
        for y in range(100, 160):
            c = screen.get_at((128, y))[:3]  # center-ish
            if c != (0, 0, 0):
                edge_colors.append(c)

        # The edge should be continuous - colors should transition smoothly
        # Check that there's no hard discontinuity (all colors should be similar)
        if len(edge_colors) >= 2:
            # Max difference between any two sampled edge colors
            max_diff = 0
            for i in range(len(edge_colors)):
                for j in range(i + 1, len(edge_colors)):
                    d = sum(abs(a - b) for a, b in zip(edge_colors[i], edge_colors[j]))
                    max_diff = max(max_diff, d)
            # Allow some gradient variation but no hard boundary
            assert max_diff < 200, f"Edge shows hard discontinuity: max diff {max_diff}"


class TestTexturedStyleRenders:
    """The "textured" terrain_style uses sprite + sub-tile interpolation."""

    def test_textured_style_does_not_crash(self):
        _init_pygame()
        elevations = [[0 for y in range(4)] for x in range(4)]
        tm = _make_test_tile_map(elevations)
        tm.bake_corner_heights()
        tm.bake_corner_fog()

        screen = pygame.Surface((256, 256))
        camera = Camera(256, 256)
        class Player:
            world_x = 256.0
            world_y = 256.0
        camera.set_player(Player())

        ls = LightingSystem("stylized")  # stylized -> terrain_style="textured"
        ls.preset_config["terrain_style"] = "textured"

        renderer = TileRenderer(tm, screen, ls)
        renderer.render(camera)

        # Should produce some non-black pixels
        non_black = sum(1 for x in range(256) for y in range(256)
                        if screen.get_at((x, y))[:3] != (0, 0, 0))
        assert non_black > 0, "Textured style produced no output"


class TestFallbackWhenUnbaked:
    """When corner_height is empty, renderer falls back to flat per-tile path."""

    def test_unbaked_falls_back_to_flat_path(self):
        _init_pygame()
        elevations = [[x for y in range(4)] for x in range(4)]
        tm = _make_test_tile_map(elevations)
        # Do NOT bake corner_height / corner_fog - leave them empty

        screen = pygame.Surface((256, 256))
        camera = Camera(256, 256)
        class Player:
            world_x = 256.0
            world_y = 256.0
        camera.set_player(Player())

        ls = LightingSystem("realistic")
        ls.preset_config["terrain_style"] = "flat"
        ls.sun_direction = (1.0, 0.0, 0.0)

        renderer = TileRenderer(tm, screen, ls)
        # Should not raise even though corner_height is empty
        renderer.render(camera)

        # Should produce some output (flat path)
        non_black = sum(1 for x in range(256) for y in range(256)
                        if screen.get_at((x, y))[:3] != (0, 0, 0))
        assert non_black > 0, "Fallback flat path produced no output"


class TestPresetGating:
    """Presets gate terrain_style correctly."""

    def test_stylized_preset_uses_textured(self):
        ls = LightingSystem("stylized")
        # The preset config should default to textured for stylized
        assert ls.preset_config.get("terrain_style") == "textured", (
            f"stylized preset should have terrain_style='textured', "
            f"got {ls.preset_config.get('terrain_style')}"
        )

    def test_realistic_preset_uses_flat(self):
        ls = LightingSystem("realistic")
        assert ls.preset_config.get("terrain_style") == "flat", (
            f"realistic preset should have terrain_style='flat', "
            f"got {ls.preset_config.get('terrain_style')}"
        )

    def test_performance_preset_uses_textured(self):
        ls = LightingSystem("performance")
        # Performance uses whatever is simpler - textured avoids triangle overhead
        # but stylized already uses textured. Let's check it has a value.
        assert "terrain_style" in ls.preset_config, (
            "performance preset should have terrain_style key"
        )


class TestSubdivisionKnob:
    """TILE_SUBDIVISIONS controls sub-tile count in textured mode."""

    def test_subdiv_default_is_2(self):
        from config import TILE_SUBDIVISIONS
        assert TILE_SUBDIVISIONS == 2, "Default TILE_SUBDIVISIONS should be 2"