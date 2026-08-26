"""
test_panel_scrollbar.py — Phase 2: interactive scrollbar + wheel delivery.

Covers the base-class scrollbar interaction (thumb hit = drag, track click =
page, thumb rect stored during draw) and the router's MOUSEWHEEL branch
(deliver to the active panel; cancel the pending camera zoom; leave zoom
intact when no panel is open).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from core.state import GameState
from input.input_manager import InputManager
from input.router import InputRouter
from ui.panel_window import PanelWindow, SCROLLBAR_DRAG


class ScrollingPanel(PanelWindow):
    """Panel that reports a tall list so the scrollbar is active."""

    def __init__(self, total=20, visible=4, **kwargs):
        kwargs.setdefault("title", "Scroll")
        kwargs.setdefault("width", 200)
        kwargs.setdefault("height", 300)
        super().__init__(**kwargs)
        self._total = total
        self._visible = visible
        self.deltas = []

    def scroll_viewport(self):
        return self._visible, self._total

    def select_count(self):
        return self._total

    def on_scroll(self, delta):
        self.deltas.append(delta)

    def draw_contents(self, screen, content_rect):
        pass


@pytest.fixture(autouse=True)
def _pygame():
    pygame.init()


def _panel(**kwargs):
    p = ScrollingPanel(**kwargs)
    p.visible = True
    # Draw once so thumb_rect exists for hit-testing.
    p.render(pygame.Surface((800, 600)))
    return p


def test_thumb_rect_stored_after_render():
    p = _panel()
    assert p._thumb_rect is not None
    strip = p._scrollbar_strip
    assert p._thumb_rect.x == strip.x
    assert p._thumb_rect.width == strip.width


def test_track_above_click_pages_up():
    p = _panel()
    p.scroll_by(p.max_offset)  # thumb slides to the bottom of the strip
    p.render(pygame.Surface((800, 600)))
    thumb = p._thumb_rect
    strip = p._scrollbar_strip
    y = thumb.y - 10  # a point in the track above the thumb
    if y < strip.y:
        y = strip.y + 2
    hit = p._scrollbar_hit(strip.x + 1, y)
    assert hit == -p._page_delta()


def test_track_below_click_pages_down():
    p = _panel()
    thumb = p._thumb_rect
    strip = p._scrollbar_strip
    y = strip.y + strip.height - 2  # bottom of the strip, below the thumb
    hit = p._scrollbar_hit(strip.x + 1, y)
    assert hit == p._page_delta()


def test_click_outside_scrollbar_is_none():
    p = _panel()
    assert p._scrollbar_hit(0, 0) is None


def test_handle_click_on_thumb_starts_drag():
    p = _panel()
    thumb = p._thumb_rect
    result = p.handle_click(thumb.x + 1, thumb.y + thumb.height // 2)
    assert result is None
    assert p._scrollbar_dragging is True


def test_handle_click_track_pages_and_returns_none():
    p = _panel()
    p._scroll_offset = 0
    strip = p._scrollbar_strip
    # Click near the bottom of the strip (below the top-positioned thumb).
    result = p.handle_click(strip.x + 1, strip.y + strip.height - 2)
    assert result is None
    assert p._scroll_offset == p._page_delta()


def test_drag_moves_offset_with_mouse_y():
    p = _panel()
    thumb = p._thumb_rect
    strip = p._scrollbar_strip
    # Start the drag in the middle.
    p._start_scroll_drag(strip.y + strip.height // 2)
    p._drag_scrollbar(strip.y + strip.height - 5)
    assert p._scroll_offset > 0
    assert p._scroll_offset <= p.max_offset


def test_mouse_up_ends_drag():
    p = _panel()
    p._scrollbar_dragging = True
    p.handle_mouse_up()
    assert p._scrollbar_dragging is False


def test_page_delta_is_visible_units():
    p = _panel(total=20, visible=4)
    assert p._page_delta() == 4


# ── Router MOUSEWHEEL delivery ───────────────────────────────────────────
class _RecordingPanel:
    def __init__(self):
        self.deltas = []

    def handle_wheel(self, delta):
        self.deltas.append(delta)


def _router(state=GameState.QUEST_PANEL, panel=None):
    im = InputManager()
    game = type("G", (), {
        "state": state,
        "_inventory_panel": None, "_skill_panel": None, "_crafting_panel": None,
        "_building_panel": None, "_gear_panel": None, "_trade_panel": None,
        "_quest_panel": panel, "_recruit_panel": None, "_diplomacy_panel": None,
    })()
    rd = InputRouter(game, im, None)
    return rd, im, game


def test_wheel_delivers_to_active_panel():
    panel = _RecordingPanel()
    rd, _, _ = _router(panel=panel)
    rd.handle(pygame.event.Event(pygame.MOUSEWHEEL, y=1, x=0))
    assert panel.deltas == [1]


def test_wheel_cancels_pending_zoom_when_panel_open():
    panel = _RecordingPanel()
    rd, im, _ = _router(panel=panel)
    im.input_state.zoom_in = True
    rd.handle(pygame.event.Event(pygame.MOUSEWHEEL, y=1, x=0))
    # Panel owns the wheel while open — the pending camera zoom is cancelled.
    assert im.input_state.zoom_in is False
    assert im.input_state.zoom_out is False


def test_wheel_leaves_zoom_when_no_panel_open():
    rd, im, _ = _router()  # no panel -> zoom is preserved for the camera
    im.input_state.zoom_out = True
    rd.handle(pygame.event.Event(pygame.MOUSEWHEEL, y=-1, x=0))
    assert im.input_state.zoom_out is True
