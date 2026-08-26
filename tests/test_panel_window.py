"""
test_panel_window.py — Phase 1: PanelWindow base-class scaffold.

Verifies the base renders without error, implements the render contract
(set_clip active during draw_contents, cleared after), and that the scroll,
selection and text-wrap primitives behave.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from ui.panel_window import PanelWindow


class DummyPanel(PanelWindow):
    """Minimal PanelWindow subclass that draws a few rows."""

    def __init__(self, **kwargs):
        kwargs.setdefault("title", "Test")
        kwargs.setdefault("width", 200)
        kwargs.setdefault("height", 200)
        super().__init__(**kwargs)
        self.drawn_clip = None
        self.on_select_calls = []

    def scroll_viewport(self):
        return self._visible, self._total

    def select_count(self):
        return self._total

    def on_select(self, index):
        self.on_select_calls.append(index)

    def draw_contents(self, screen, content_rect):
        # Capture the clip state while the viewport is active.
        self.drawn_clip = screen.get_clip()
        # Draw a couple of rows inside the clipped viewport.
        for i in range(min(3, self._total)):
            row = pygame.Rect(content_rect.x, content_rect.y + i * 20,
                              content_rect.width, 20)
            pygame.draw.rect(screen, (60, 60, 80), row)


class BarePanel(PanelWindow):
    """Subclass that does not override draw_contents."""


@pytest.fixture(autouse=True)
def _pygame():
    pygame.init()


def _panel(**kwargs):
    visible = kwargs.pop("_visible", 4)
    total = kwargs.pop("_total", 10)
    p = DummyPanel(**kwargs)
    p._visible = visible
    p._total = total
    return p


def test_renders_without_error():
    panel = _panel()
    panel.visible = True
    screen = pygame.Surface((800, 600))
    panel.render(screen)  # must not raise


def test_hidden_panel_does_not_render():
    panel = _panel()
    panel.visible = False
    screen = pygame.Surface((800, 600))
    panel.render(screen)
    assert panel.drawn_clip is None  # draw_contents never ran


def test_clip_active_during_draw_then_cleared():
    panel = _panel()
    panel.visible = True
    screen = pygame.Surface((800, 600))
    before = screen.get_clip()  # full surface (no clip)
    panel.render(screen)
    # set_clip was active and matched content_rect while drawing...
    assert panel.drawn_clip == panel.content_rect
    assert panel.drawn_clip is not None
    # ...and reset to no-clip afterwards (contract: set_clip(None)).
    assert screen.get_clip() == before


def test_close_rect_within_bounds():
    panel = _panel(x=250, y=30, width=460, height=580)
    r = panel._close_rect
    assert r.x + r.width <= panel.rect.x + panel.rect.width
    assert r.y + r.height <= panel.rect.y + panel.rect.height


def test_scroll_by_clamps():
    panel = _panel(_visible=4, _total=10)  # max_offset = 6
    assert panel.max_offset == 6
    panel.scroll_by(100)
    assert panel._scroll_offset == 6
    panel.scroll_by(-100)
    assert panel._scroll_offset == 0
    panel.scroll_by(3)
    assert panel._scroll_offset == 3


def test_selection_clamp_and_notify():
    panel = _panel(_visible=4, _total=5)  # select_count == 5
    panel.select(-10)
    assert panel._selected_index == -1
    assert panel.on_select_calls == []
    panel.select(2)
    assert panel._selected_index == 2
    assert panel.on_select_calls == [2]
    panel.select(100)
    assert panel._selected_index == 4


def test_wrap_text_multiline_and_bounded():
    panel = _panel()
    long_text = "the quick brown fox jumps over the lazy dog " * 8
    lines = panel.wrap_text(long_text, max_width=120)
    assert len(lines) > 1
    for surf in lines:
        assert surf.get_width() <= 120


def test_wrap_text_empty_is_single_line():
    panel = _panel()
    lines = panel.wrap_text("", max_width=120)
    assert len(lines) == 1


def test_unimplemented_draw_contents_raises():
    panel = BarePanel()
    screen = pygame.Surface((800, 600))
    with pytest.raises(NotImplementedError):
        panel.draw_contents(screen, panel.content_rect)


def test_scrollbar_strip_absent_when_disabled():
    panel = _panel(has_scrollbar=False)
    assert panel._scrollbar_strip is None
    # rendering with no scrollbar must not raise
    screen = pygame.Surface((800, 600))
    panel.render(screen)


def test_grid_selection_moves_by_columns():
    panel = _panel(_visible=4, _total=9)
    panel.grid_cols = 3
    panel.select(0)
    panel.handle_key(pygame.K_d)  # move right by one column
    assert panel._selected_index == 3
    panel.handle_key(pygame.K_a)  # move left by one column
    assert panel._selected_index == 0
