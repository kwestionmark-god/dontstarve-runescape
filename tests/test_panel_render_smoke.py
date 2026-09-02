"""Render smoke tests: panels must render without crashing in every state
they can be invoked in (session open/closed, tabs, scrolling)."""

import os
from types import SimpleNamespace

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(scope="module", autouse=True)
def pygame_init():
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1280, 800))
    yield


def _surface():
    return pygame.Surface((1280, 800))


def _trade_item(item_id, buy=10, sell=5, stock=3):
    return SimpleNamespace(item_id=item_id, buy_price=buy, sell_price=sell,
                           stock_quantity=stock)


class _FakeTradeSystem:
    def get_trade_items_for_merchant(self, merchant):
        return [_trade_item(f"item_{i}") for i in range(12)]

    def _find_trade_item_by_item_id(self, item_id):
        return _trade_item(item_id)

    def get_tradeable_player_items(self, inventory):
        return []

    def open_trade(self, player, merchant):
        return SimpleNamespace(name=merchant.name, gold=100)

    def close_trade(self):
        pass


class _FakeInventory:
    gold = 50

    def get_snapshot(self):
        return [{"item_id": "log", "quantity": 3}, None]


def _make_trade_panel():
    from ui.trade_panel import TradePanel

    panel = TradePanel()
    panel.set_trade_system(_FakeTradeSystem())
    panel.set_inventory(_FakeInventory())
    panel._player_ref = SimpleNamespace(inventory=_FakeInventory())
    return panel


def test_trade_panel_renders_with_open_session():
    panel = _make_trade_panel()
    merchant = SimpleNamespace(name="Test Merchant")
    assert panel.open_session(merchant)
    panel.visible = True
    screen = _surface()
    for tab in ("buy", "sell", "barter"):
        panel._tab = tab
        panel.render(screen)


def test_trade_panel_renders_without_session():
    panel = _make_trade_panel()
    panel.visible = True
    panel.render(_surface())


def test_trade_panel_title_shows_merchant_name():
    panel = _make_trade_panel()
    assert panel.title == "Trade"
    panel.open_session(SimpleNamespace(name="Mira the Trader"))
    assert panel.title == "Trade with Mira the Trader"


def test_diplomacy_panel_renders_detail_view():
    from ui.diplomacy_panel import DiplomacyPanel

    panel = DiplomacyPanel()
    panel.faction_system = SimpleNamespace(
        get_info=lambda fid: {
            "name": "Wolf Clan", "hostility": 0.5,
            "description": "A clan.", "monster_types": [],
        },
    )
    panel.visible = True
    panel._selected_faction = "wolf"
    panel.render(_surface())


def test_scrollbar_drag_preserves_grab_offset():
    from ui.panel_window import PanelWindow

    class P(PanelWindow):
        def draw_contents(self, screen, content_rect):
            pass

        def scroll_viewport(self):
            return (100, 300)

    panel = P(x=0, y=0, width=300, height=300, has_scrollbar=True)
    panel.visible = True
    panel.render(_surface())
    assert panel._scrollbar_strip is not None
    strip = panel._scrollbar_strip
    thumb = panel._thumb_rect
    # Grab the thumb in its middle, then drag 0 px: nothing should change.
    grab_y = thumb.y + thumb.height // 2
    panel._start_scroll_drag(grab_y)
    panel._drag_scrollbar(grab_y)
    assert panel._scroll_offset == 0
    # Scroll partway, grab the (moved) thumb, drag a few px: offset moves by
    # only those px worth of travel.
    panel.scroll_by(50)
    thumb = panel._thumb_rect
    grab_y = thumb.y + 3
    panel._start_scroll_drag(grab_y)
    panel._drag_scrollbar(grab_y + 5)
    travel = strip.height - thumb.height
    expected = round(50 + 5 * panel.max_offset / travel)
    assert panel._scroll_offset == expected
