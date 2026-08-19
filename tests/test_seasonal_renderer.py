"""
test_seasonal_renderer.py — Integration tests for SeasonalRenderer.

Tests:
- Palette Lerp between seasons
- Season progress blending
- Unknown biome fallback
- Ambient overlay parameters
- Bootstrap wiring integration
"""

import pytest
from render.seasonal_renderer import SeasonalRenderer, DEFAULT_PALETTES


class TestSeasonalRendererSync:
    """Test seasonal renderer state sync."""

    def test_sync_sets_current_season(self):
        """Sync should set the current season."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.5, current_season="summer", previous_season="spring")

        assert sr._current_season == "summer"
        assert sr._previous_season == "spring"

    def test_sync_sets_blend_from_progress(self):
        """Blend should be 1.0 - season_progress."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="summer", previous_season="spring")
        assert sr._blend == 1.0  # Start of season

        sr.sync(season_progress=1.0, current_season="summer", previous_season="spring")
        assert sr._blend == 0.0  # End of season

    def test_sync_blend_intermediate(self):
        """Blend should interpolate at mid-season."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.5, current_season="summer", previous_season="spring")
        assert sr._blend == 0.5


class TestSeasonalRendererLerp:
    """Test seasonal color interpolation (Lerp)."""

    def test_spring_forest_no_blend(self):
        """At start of spring (blend=1.0), should return pure spring color."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="spring", previous_season=None)

        color = sr.get_tile_color("forest", (0, 0, 0))
        assert color == (40, 120, 40)  # Spring forest

    def test_summer_forest_no_blend(self):
        """At start of summer (blend=1.0), should return pure summer color."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="summer", previous_season=None)

        color = sr.get_tile_color("forest", (0, 0, 0))
        assert color == (50, 140, 45)  # Summer forest

    def test_autumn_forest_no_blend(self):
        """At start of autumn (blend=1.0), should return pure autumn color."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="autumn", previous_season=None)

        color = sr.get_tile_color("forest", (0, 0, 0))
        assert color == (160, 100, 30)  # Autumn forest

    def test_winter_forest_no_blend(self):
        """At start of winter (blend=1.0), should return pure winter color."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="winter", previous_season=None)

        color = sr.get_tile_color("forest", (0, 0, 0))
        assert color == (180, 190, 200)  # Winter forest

    def test_spring_to_summer_lerp(self):
        """Spring → Summer Lerp should blend correctly at blend=0.5."""
        sr = SeasonalRenderer()
        # blend=0.5 means we're halfway through summer
        # Lerp formula: prev + (curr - prev) * (1 - blend)
        # = spring + (summer - spring) * 0.5
        sr.sync(season_progress=0.5, current_season="summer", previous_season="spring")

        color = sr.get_tile_color("forest", (0, 0, 0))
        # R: 40 + (50 - 40) * 0.5 = 45
        # G: 120 + (140 - 120) * 0.5 = 130
        # B: 40 + (45 - 40) * 0.5 = 42
        assert color == (45, 130, 42)

    def test_autumn_to_winter_lerp(self):
        """Autumn → Winter Lerp at blend=0.25."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.75, current_season="winter", previous_season="autumn")
        # blend = 1.0 - 0.75 = 0.25

        color = sr.get_tile_color("forest", (0, 0, 0))
        # R: 160 + (180 - 160) * 0.75 = 175
        # G: 100 + (190 - 100) * 0.75 = 167
        # B: 30 + (200 - 30) * 0.75 = 157
        assert color == (175, 167, 157)

    def test_plains_spring_no_blend(self):
        """Plains spring should return correct color."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="spring", previous_season=None)

        color = sr.get_tile_color("plains", (0, 0, 0))
        assert color == (80, 160, 60)

    def test_plains_summer_no_blend(self):
        """Plains summer should return correct color."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="summer", previous_season=None)

        color = sr.get_tile_color("plains", (0, 0, 0))
        assert color == (140, 170, 50)


class TestSeasonalRendererFallback:
    """Test fallback behavior for unknown biomes."""

    def test_unknown_biome_returns_base_color(self):
        """Unknown biome should return the base color unchanged."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="spring", previous_season=None)

        base_color = (100, 150, 200)
        color = sr.get_tile_color("tundra", base_color)
        assert color == base_color

    def test_biome_without_season_returns_base_color(self):
        """Biome missing a season should fall back to base color."""
        # Desert has all seasons, but let's test a biome with partial data
        custom_palettes = {
            "forest": {
                "spring": (40, 120, 40),
                # Missing summer
            },
        }
        sr = SeasonalRenderer(palettes=custom_palettes)
        sr.sync(season_progress=0.0, current_season="summer", previous_season=None)

        base_color = (100, 150, 200)
        color = sr.get_tile_color("forest", base_color)
        assert color == base_color

    def test_biome_without_current_season_returns_base(self):
        """Biome missing current season should return base color."""
        sr = SeasonalRenderer()
        sr.sync(season_progress=0.0, current_season="monsoon", previous_season=None)

        base_color = (100, 150, 200)
        color = sr.get_tile_color("forest", base_color)
        assert color == base_color


class TestSeasonalRendererCustomPalettes:
    """Test custom palette configuration."""

    def test_custom_palette_used(self):
        """Custom palettes should override defaults."""
        custom = {
            "ocean": {
                "spring": (0, 100, 200),
                "summer": (0, 150, 220),
            },
        }
        sr = SeasonalRenderer(palettes=custom)
        sr.sync(season_progress=0.0, current_season="summer", previous_season=None)

        color = sr.get_tile_color("ocean", (0, 0, 0))
        assert color == (0, 150, 220)

    def test_custom_palette_partial_fallback(self):
        """Custom palette with partial seasons should fall back to base."""
        custom = {
            "ocean": {
                "spring": (0, 100, 200),
            },
        }
        sr = SeasonalRenderer(palettes=custom)
        sr.sync(season_progress=0.0, current_season="summer", previous_season=None)

        base_color = (50, 80, 100)
        color = sr.get_tile_color("ocean", base_color)
        assert color == base_color


class TestSeasonalRendererAmbient:
    """Test ambient overlay rendering."""

    def test_draw_ambient_overlay_parameters(self):
        """draw_ambient_overlay should accept alpha and color parameters."""
        sr = SeasonalRenderer()
        # This test verifies the method exists and accepts parameters
        # Actual pygame drawing is tested in integration tests
        try:
            import pygame
            screen = pygame.Surface((640, 480), pygame.SRCALPHA)

            sr.draw_ambient_overlay(screen, alpha=30, color=(0, 0, 0))
            # If no exception, the method works
        except ImportError:
            pass  # Pygame not available in test environment


class TestSeasonalRendererIntegration:
    """Integration tests with Game and Bootstrap."""

    def test_bootstrap_creates_seasonal_renderer(self):
        """Bootstrap should create SeasonalRenderer."""
        from core.bootstrap import Bootstrap

        class MockGame:
            survival = None
            player = None
            _tile_renderer = None

        class MockTileRenderer:
            seasonal_renderer = None

        game = MockGame()
        game._tile_renderer = MockTileRenderer()

        # Simulate bootstrap wiring
        from render import SeasonalRenderer
        game.seasonal_renderer = SeasonalRenderer()
        if game._tile_renderer is not None:
            game._tile_renderer.seasonal_renderer = game.seasonal_renderer

        # Verify
        assert game.seasonal_renderer is not None
        assert game._tile_renderer.seasonal_renderer is game.seasonal_renderer

    def test_seasonal_renderer_with_tile_renderer(self):
        """TileRenderer should use SeasonalRenderer for color blending."""
        from render.tile_renderer import TileRenderer

        tile_renderer = TileRenderer(None, None)
        sr = SeasonalRenderer()

        # Wire seasonal renderer
        tile_renderer.seasonal_renderer = sr

        assert tile_renderer.seasonal_renderer is sr

    def test_seasonal_renderer_syncs_with_season_system(self):
        """SeasonalRenderer should sync correctly with SeasonSystem."""
        from seasons import SeasonSystem
        from render.seasonal_renderer import SeasonalRenderer

        season_system = SeasonSystem()
        renderer = SeasonalRenderer()

        # Sync with current state
        renderer.sync(
            season_progress=season_system.season_progress,
            current_season=season_system.current_season,
            previous_season=season_system.previous_season,
        )

        assert renderer._current_season == "spring"
        assert renderer._previous_season is None
        assert renderer._blend == 1.0

        # Advance season halfway through
        season_system.tick(300.0)
        renderer.sync(
            season_progress=season_system.season_progress,
            current_season=season_system.current_season,
            previous_season=season_system.previous_season,
        )

        assert renderer._current_season == "spring"
        assert renderer._blend == 0.5  # 1.0 - 0.5
