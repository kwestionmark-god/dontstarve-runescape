"""
Test that wrap_text cache key includes color.
"""

import pytest
import pygame
from ui.panel_window import PanelWindow


@pytest.fixture(scope="module")
def pygame_init():
    """Initialize pygame once for all tests."""
    pygame.init()
    yield
    pygame.quit()


def test_wrap_text_color_cache(pygame_init):
    """Test that different colors produce different cached surfaces."""
    panel = PanelWindow(title="Test", x=0, y=0, width=200, height=200)
    
    text = "This is a test line that will be wrapped"
    max_width = 100
    
    # Wrap with red color
    red_surfaces = panel.wrap_text(text, max_width, color=(255, 0, 0))
    
    # Wrap with blue color
    blue_surfaces = panel.wrap_text(text, max_width, color=(0, 0, 255))
    
    # The surfaces should have different pixel colors
    # Check first surface's pixel color
    red_pixel = red_surfaces[0].get_at((0, 0))
    blue_pixel = blue_surfaces[0].get_at((0, 0))
    
    assert red_pixel[:3] == (255, 0, 0), f"Expected red, got {red_pixel[:3]}"
    assert blue_pixel[:3] == (0, 0, 255), f"Expected blue, got {blue_pixel[:3]}"
    
    # Now wrap again with red - should get cached red surfaces
    red_surfaces2 = panel.wrap_text(text, max_width, color=(255, 0, 0))
    
    # Should be the same objects (cached)
    assert red_surfaces2 is red_surfaces, "Expected cached surfaces for same color"


def test_wrap_text_default_color_cache(pygame_init):
    """Test that default color caching still works."""
    panel = PanelWindow(title="Test", x=0, y=0, width=200, height=200)
    
    text = "Test line"
    max_width = 100
    
    # Wrap with default color (first call)
    surfaces1 = panel.wrap_text(text, max_width)
    
    # Wrap again with default color (should be cached)
    surfaces2 = panel.wrap_text(text, max_width)
    
    assert surfaces2 is surfaces1, "Expected cached surfaces for default color"