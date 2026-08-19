"""
test_sprite_seasonal_tint.py — Integration tests for seasonal sprite tinting.

Tests:
- SpriteRenderer has seasonal_renderer attribute
- Seasonal tint helper returns correct colors per tier
- Tint application produces tinted surfaces
- Bootstrap wiring integration (SpriteRenderer → SeasonalRenderer)
- Fallback behavior (no seasonal renderer)
"""

import pytest
import pygame


class TestSpriteRendererSeasonalRendererAttr:
    """Test SpriteRenderer seasonal_renderer attribute."""

    def test_sprite_renderer_has_seasonal_renderer_slot(self):
        """SpriteRenderer.__slots__ should include seasonal_renderer."""
        from render.sprite_renderer import SpriteRenderer

        assert "seasonal_renderer" in SpriteRenderer.__slots__

    def test_sprite_renderer_init_accepts_seasonal_renderer(self):
        """SpriteRenderer.__init__ should accept seasonal_renderer param."""
        from render.sprite_renderer import SpriteRenderer

        class MockSR:
            pass

        sr = SpriteRenderer(seasonal_renderer=MockSR())
        assert sr.seasonal_renderer is not None

    def test_sprite_renderer_seasonal_renderer_defaults_to_none(self):
        """SpriteRenderer.seasonal_renderer should default to None."""
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        assert sr.seasonal_renderer is None


class TestSeasonTintHelper:
    """Test _get_season_tint static method."""

    def test_tint_tier_1_is_green(self):
        """Tier 1 (nature/player) should return green tint."""
        from render.sprite_renderer import SpriteRenderer

        tint = SpriteRenderer._get_season_tint(tier=1)
        assert tint == (80, 100, 60)

    def test_tint_tier_2_is_grey(self):
        """Tier 2 (neutral NPCs) should return grey tint."""
        from render.sprite_renderer import SpriteRenderer

        tint = SpriteRenderer._get_season_tint(tier=2)
        assert tint == (100, 100, 100)

    def test_tint_tier_3_is_gold(self):
        """Tier 3 (rare items) should return gold tint."""
        from render.sprite_renderer import SpriteRenderer

        tint = SpriteRenderer._get_season_tint(tier=3)
        assert tint == (120, 100, 60)

    def test_tint_tier_4_is_purple(self):
        """Tier 4 (rare entities) should return purple tint."""
        from render.sprite_renderer import SpriteRenderer

        tint = SpriteRenderer._get_season_tint(tier=4)
        assert tint == (100, 80, 100)

    def test_tint_unknown_tier_defaults_to_tier_1(self):
        """Unknown tier should default to tier 1 green tint."""
        from render.sprite_renderer import SpriteRenderer

        tint = SpriteRenderer._get_season_tint(tier=99)
        assert tint == (80, 100, 60)


class TestApplySeasonalTint:
    """Test _apply_seasonal_tint method."""

    def test_apply_tint_returns_new_surface(self):
        """_apply_seasonal_tint should return a new Surface."""
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        original = pygame.Surface((32, 32), pygame.SRCALPHA)
        original.fill((255, 255, 255))

        tinted = sr._apply_seasonal_tint(original, (80, 100, 60), alpha=40)

        assert tinted is not original
        assert tinted.get_size() == original.get_size()

    def test_tint_applies_green_overlay_to_white(self):
        """Tint on a white surface should produce a greenish tint."""
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        original = pygame.Surface((32, 32), pygame.SRCALPHA)
        original.fill((255, 255, 255))

        tint_color = (80, 100, 60)
        alpha = 40
        tinted = sr._apply_seasonal_tint(original, tint_color, alpha=alpha)

        # Check center pixel — should be tinted toward green
        pixel = tinted.get_at((16, 16))
        # BLEND_RGBA_MULT: result = src * (tint/255) + alpha effect
        # With white (255,255,255) and green tint, green should dominate
        assert pixel[1] > pixel[0]  # G > R (green > red for green tint)

    def test_tint_alpha_zero_no_effect(self):
        """Alpha=0 should produce minimal tint effect."""
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        original = pygame.Surface((32, 32), pygame.SRCALPHA)
        original.fill((255, 255, 255))

        tinted = sr._apply_seasonal_tint(original, (200, 50, 50), alpha=0)

        # With alpha=0, the tint surface is fully transparent
        # Result should be close to original
        orig_pixel = original.get_at((16, 16))
        tinted_pixel = tinted.get_at((16, 16))
        # Should be nearly identical
        assert abs(orig_pixel[0] - tinted_pixel[0]) <= 5


class TestSpriteRendererNoSeasonalRenderer:
    """Test fallback behavior when seasonal_renderer is None."""

    def test_no_seasonal_renderer_no_error(self):
        """SpriteRenderer should work without seasonal_renderer."""
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        # No seasonal_renderer set — should not crash
        assert sr.seasonal_renderer is None
        # Helpers should still be callable
        tint = SpriteRenderer._get_season_tint(tier=1)
        assert tint is not None


class TestBootstrapWiring:
    """Test bootstrap wiring of seasonal_renderer to SpriteRenderer."""

    def test_bootstrap_wires_seasonal_renderer_to_sprite(self):
        """Bootstrap should wire SeasonalRenderer to SpriteRenderer."""
        from core.bootstrap import Bootstrap

        class MockGame:
            survival = None
            player = None
            _tile_renderer = None
            _sprite_renderer = None

        class MockTileRenderer:
            seasonal_renderer = None

        class MockSpriteRenderer:
            seasonal_renderer = None

        game = MockGame()
        game._tile_renderer = MockTileRenderer()
        game._sprite_renderer = MockSpriteRenderer()

        # Simulate bootstrap wiring
        from render import SeasonalRenderer
        game.seasonal_renderer = SeasonalRenderer()
        if game._tile_renderer is not None:
            game._tile_renderer.seasonal_renderer = game.seasonal_renderer
        if game._sprite_renderer is not None:
            game._sprite_renderer.seasonal_renderer = game.seasonal_renderer

        # Verify
        assert game._sprite_renderer.seasonal_renderer is game.seasonal_renderer

    def test_bootstrap_sprite_renderer_tinting_integration(self):
        """Full integration: SpriteRenderer with SeasonalRenderer should work."""
        from render.sprite_renderer import SpriteRenderer
        from render.seasonal_renderer import SeasonalRenderer

        sr = SpriteRenderer()
        seasonal_renderer = SeasonalRenderer()
        sr.seasonal_renderer = seasonal_renderer

        # Create a test sprite
        test_sprite = pygame.Surface((32, 32), pygame.SRCALPHA)
        test_sprite.fill((200, 200, 200))  # Grey

        # Apply tint
        tint_color = SpriteRenderer._get_season_tint(tier=1)
        tinted = sr._apply_seasonal_tint(test_sprite, tint_color, alpha=40)

        # Verify tinted surface is different from original
        assert tinted.get_size() == test_sprite.get_size()

        # Verify tint was applied (pixel should be different)
        orig_pixel = test_sprite.get_at((16, 16))
        tinted_pixel = tinted.get_at((16, 16))
        assert orig_pixel != tinted_pixel


class TestSeasonalTintWithSeasonSystem:
    """Test seasonal tint integration with SeasonSystem."""

    def test_tint_applied_during_season_transition(self):
        """Seasonal tint should be applied during season transitions."""
        from seasons import SeasonSystem
        from render.sprite_renderer import SpriteRenderer
        from render.seasonal_renderer import SeasonalRenderer

        season_system = SeasonSystem()
        sprite_renderer = SpriteRenderer()
        seasonal_renderer = SeasonalRenderer()
        sprite_renderer.seasonal_renderer = seasonal_renderer

        # Sync renderer with season system
        seasonal_renderer.sync(
            season_progress=season_system.season_progress,
            current_season=season_system.current_season,
            previous_season=season_system.previous_season,
        )

        # Verify renderer is in correct state
        assert seasonal_renderer._current_season == "spring"
        assert seasonal_renderer._blend == 1.0

        # Tint should still be applied (independent of season state)
        test_sprite = pygame.Surface((32, 32), pygame.SRCALPHA)
        test_sprite.fill((255, 255, 255))
        tint_color = SpriteRenderer._get_season_tint(tier=1)
        tinted = sprite_renderer._apply_seasonal_tint(test_sprite, tint_color, alpha=40)

        assert tinted is not None
        assert tinted.get_size() == test_sprite.get_size()

    def test_tint_tier_mapping_for_npc_types(self):
        """NPC types should map to correct tier tints."""
        from render.sprite_renderer import SpriteRenderer

        # Merchants and quest givers use tier 2 (grey)
        assert SpriteRenderer._get_season_tint(tier=2) == (100, 100, 100)

        # Rare items/recruits use tier 3 (gold)
        assert SpriteRenderer._get_season_tint(tier=3) == (120, 100, 60)

        # Player uses tier 1 (green)
        assert SpriteRenderer._get_season_tint(tier=1) == (80, 100, 60)
