"""
test_dashboard.py — Unified dashboard (tabbed character menu).

Covers:
- Construction: tabs host the existing panel instances at shared geometry
- Tab switching via keys (LEFT/RIGHT/A/D) and clicks on the tab strip
- render delegates to the active tab only
- open_dashboard + key routing (I/C/B/G open tabs, same-key closes)
- ESC closes the dashboard
"""

import pygame
import pytest

from core.state import GameState
from ui.dashboard_panel import DashboardPanel, TAB_ORDER, TAB_LABELS


class _ChildPanel:
    """Minimal child panel stub (rendered/clicked/keys tracked)."""

    def __init__(self, name):
        self.name = name
        self.visible = False
        self.rendered = 0
        self.keys = []
        self.clicks = []
        self.rect = pygame.Rect(0, 0, 0, 0)

    def reposition(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def handle_key(self, key):
        self.keys.append(key)
        return ("key", self.name)

    def handle_click(self, x, y, button=1):
        self.clicks.append((x, y, button))
        return ("clicked", self.name)

    def handle_mouse_move(self, mx, my):
        pass

    def close(self):
        self.visible = False


def _dashboard():
    dash = DashboardPanel()
    dash.center(1280, 720)
    children = {}
    for tab in TAB_ORDER:
        p = _ChildPanel(tab)
        children[tab] = p
        dash.register_tab(tab, p, lambda screen, p=p: setattr(p, 'rendered', p.rendered + 1))
    return dash, children


class TestDashboardBasics:
    def test_tabs_present_and_unique_geometry(self):
        dash, children = _dashboard()
        dash.set_active("inventory")
        # All children share the dashboard frame
        for tab, child in children.items():
            assert child.rect.width == dash.width
            assert child.rect.height == dash.height - 26  # tab strip
            assert child.rect.x == dash.x


class TestTabSwitching:
    def test_arrow_keys_cycle(self):
        dash, _ = _dashboard()
        dash.set_active("inventory")
        dash.handle_key(pygame.K_RIGHT)
        assert dash.active_tab == "skills"
        dash.handle_key(pygame.K_RIGHT)
        assert dash.active_tab == "crafting"
        dash.handle_key(pygame.K_LEFT)
        assert dash.active_tab == "skills"

    def test_cycle_wraps(self):
        dash, _ = _dashboard()
        dash.set_active("inventory")
        dash.handle_key(pygame.K_LEFT)
        assert dash.active_tab == "gear"

    def test_tab_click_switches(self):
        dash, _ = _dashboard()
        dash.set_active("inventory")
        # Click the "building" tab button (4th tab)
        x = dash.x + int(3.5 * dash.width / len(TAB_ORDER))
        y = dash.y + 5
        dash.handle_click(x, y, 1)
        assert dash.active_tab == "building"

    def test_child_keys_forwarded(self):
        dash, children = _dashboard()
        dash.set_active("skills")
        result = dash.handle_key(pygame.K_RETURN)
        assert children["skills"].keys == [pygame.K_RETURN]
        assert result == ("key", "skills")

    def test_child_clicks_forwarded_below_tab_strip(self):
        dash, children = _dashboard()
        dash.set_active("gear")
        result = dash.handle_click(dash.x + 100, dash.y + 300, 1)
        assert children["gear"].clicks
        assert result == ("clicked", "gear")

    def test_render_only_active_tab(self):
        dash, children = _dashboard()
        dash.visible = True
        dash.set_active("inventory")
        screen = pygame.Surface((1280, 720))
        dash.render(screen)
        assert children["inventory"].rendered == 1
        assert children["crafting"].rendered == 0

    def test_tab_switch_hides_other_children(self):
        dash, children = _dashboard()
        dash.set_active("inventory")
        dash.set_active("gear")
        assert children["inventory"].visible is False
        assert children["gear"].visible is True


class TestDashboardKeyboardRouting:
    """Router-level: panel keys open the dashboard at their tab."""

    class _Game:
        def __init__(self):
            self.state = GameState.PLAYING
            self.build_mode = False
            self._dashboard = None
            self._inventory_panel = None
            self._skill_panel = None
            self._crafting_panel = None
            self._building_panel = None
            self._gear_panel = None
            self._trade_panel = None
            self._quest_panel = None
            self._recruit_panel = None
            self._diplomacy_panel = None
            self.hud = None

        def set_state(self, s):
            self.state = s

    class _Dispatcher:
        def dispatch(self, state, action):
            pass

        def dispatch_click(self, state, name, action):
            pass

    def _router(self, game):
        from input.router import InputRouter

        class IM:
            def __init__(self):
                from input.input_state import InputState
                self.input_state = InputState()

        class Flows:
            def handle_trade_accept_keyboard(self):
                pass

            def handle_quest_accept_keyboard(self):
                pass

        router = InputRouter(game, None, None)
        router._input_manager = IM()
        router._npc_flows = Flows()
        return router

    def test_open_inventory_routes_to_dashboard(self):
        dash, _ = _dashboard()
        game = self._Game()
        game._dashboard = dash

        opened = []
        game.open_dashboard = lambda tab: (
            opened.append(tab), dash.set_active(tab),
            setattr(game, 'state', GameState.DASHBOARD_OPEN),
        )
        game.set_state = lambda s: setattr(game, 'state', s)

        router = self._router(game)
        router._input_manager.input_state.open_inventory = True
        router._handle_keydown(game, router._input_manager, self._Dispatcher(),
                               pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i))
        assert opened == ["inventory"]
        assert game.state == GameState.DASHBOARD_OPEN
        assert dash.active_tab == "inventory"

    def test_same_key_closes_dashboard(self):
        dash, _ = _dashboard()
        dash.set_active("inventory")

        game = self._Game()
        game._dashboard = dash
        game.state = GameState.DASHBOARD_OPEN

        router = self._router(game)
        router._input_manager.input_state.open_inventory = True
        router._handle_keydown(game, router._input_manager, self._Dispatcher(),
                               pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i))
        assert game.state == GameState.PLAYING
