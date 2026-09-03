"""
test_b28_phase4_ui_polish.py — Regression tests for Phase 4 (UI/input polish).

Covers:
- 4.1 Grid navigation: W/S move by grid columns, A/D by one cell; list mode
      forwards LEFT/RIGHT to on_key (tab-switching panels)
- 4.2 Keyboard Enter "place" in the building panel enters build mode
- 4.3 Clicking a hotbar slot no longer walks the player
- 4.4 Y toggles the quest panel open and closed
- 4.7 Mouse wheel scrolls one row per tick (not one pixel)
- 4.8 cancel == close in the panel dispatcher
- 4.9 ESC from the ERROR screen clears the stale world-gen error
"""

import pygame
import pytest

from core.state import GameState
from ui.panel_window import PanelWindow


# ── 4.1 + 4.7 PanelWindow navigation & wheel ────────────────────────────────


class _GridPanel(PanelWindow):
    def draw_contents(self, screen, rect):
        pass

    def select_count(self):
        return 20

    def __init__(self):
        super().__init__(selection_mode="grid", grid_cols=5, row_height=24)
        self.max_offset_override = 1000
        self.on_key_hits = []

    def on_key(self, key):
        self.on_key_hits.append(key)
        return None


class _ListPanel(PanelWindow):
    def draw_contents(self, screen, rect):
        pass

    def select_count(self):
        return 20

    def __init__(self):
        super().__init__(selection_mode="list", row_height=24)
        self.on_key_hits = []

    def on_key(self, key):
        self.on_key_hits.append(key)
        return None

    def scroll_viewport(self):
        return (10, 100)


class TestGridNavigation:
    def test_w_moves_by_grid_cols(self):
        p = _GridPanel()
        p._selected_index = 10
        p.handle_key(pygame.K_w)
        assert p._selected_index == 5  # up one grid row
        p.handle_key(pygame.K_s)
        assert p._selected_index == 10

    def test_ad_moves_by_one_cell(self):
        p = _GridPanel()
        p._selected_index = 10
        p.handle_key(pygame.K_d)
        assert p._selected_index == 11
        p.handle_key(pygame.K_a)
        assert p._selected_index == 10


class TestListModeKeyPassthrough:
    def test_left_right_reach_on_key_in_list_mode(self):
        p = _ListPanel()
        p.handle_key(pygame.K_LEFT)
        assert pygame.K_LEFT in p.on_key_hits


class TestWheelScroll:
    def test_one_tick_scrolls_one_row(self):
        p = _ListPanel()
        p.handle_wheel(1)  # wheel up → scroll content down (offset decreases)
        assert p._scroll_offset == 0  # already at top
        p.handle_wheel(-1)
        assert p._scroll_offset == p.row_height, (
            f"one wheel tick should scroll one row ({p.row_height}px), "
            f"got {p._scroll_offset}"
        )


# ── 4.2 Keyboard building place ──────────────────────────────────────────────


class TestBuildingKeyboardPlace:
    def test_place_enters_build_mode(self):
        from input.panel_dispatcher import PanelDispatcher

        class G:
            state = GameState.BUILDING_PANEL
            build_mode = False
            _building_pending_id = None
            player = None

            def __init__(self):
                self._building_panel = type("P", (), {
                    "selected_structure_id": None, "visible": True,
                })()
                self.transitions = []

            def set_state(self, s):
                self.state = s

        game = G()
        PanelDispatcher(game)._handle_building_place("campfire")
        assert game.build_mode is True
        assert game._building_pending_id == "campfire"
        assert game.state == GameState.PLAYING


# ── 4.3 Hotbar click must not move the player ────────────────────────────────


class TestHotbarClickNoMove:
    def test_hotbar_click_skips_click_to_move(self):
        from input.router import InputRouter

        hud_rect = pygame.Rect(650, 660, 56, 56)

        class Hud:
            _hotbar_rects = []

            def set_hotbar_selected(self, i):
                pass

        hud = Hud()
        hud._hotbar_rects = [hud_rect]

        moves = []

        class Player:
            def move_to(self, x, y):
                moves.append((x, y))

        class Cam:
            def screen_to_world(self, x, y):
                return (x / 64, y / 64)

        class Game:
            state = GameState.PLAYING
            build_mode = False
            player = Player()
            camera = Cam()
            combat_system = object()
            inventory = None
            _dashboard = None
            _quest_panel = None
            _trade_panel = None
            _recruit_panel = None
            _diplomacy_panel = None
            _building_panel = None
            _inventory_panel = None

        Game.hud = hud

        router = InputRouter(Game(), None, None)
        router._handle_mouse_button_down(
            router._game,
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(660, 680)),
        )
        assert moves == [], "hotbar click should not move the player"


# ── 4.4 Y toggles quest panel ────────────────────────────────────────────────


class TestQuestPanelToggle:
    def test_y_closes_quest_panel(self):
        from input.router import InputRouter
        from input.input_state import InputState

        class QP:
            def __init__(self):
                self.visible = True
                self._selected_quest_id = None

            def close(self):
                self.visible = False

        class Game:
            _dashboard = None

            def __init__(self):
                self.state = GameState.QUEST_PANEL
                self._quest_panel = QP()
                self._trade_panel = None
                self._recruit_panel = None
                self._diplomacy_panel = None
                self._inventory_panel = None
                self._skill_panel = None
                self._crafting_panel = None
                self._building_panel = None
                self._gear_panel = None
                self.player = None
                self.save_system = None
                self.hud = None
                self.build_mode = False
                self._building_pending_id = None

            def set_state(self, s):
                self.state = s

        game = Game()
        router = InputRouter(game, None, None)

        class IM:
            def __init__(self):
                self.input_state = InputState()

        router._input_manager = IM()
        router._handle_keydown(
            game, router._input_manager, None,
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y),
        )
        assert game.state == GameState.PLAYING
        assert game._quest_panel.visible is False


# ── 4.8 cancel delegates to close ────────────────────────────────────────────


class TestCancelIsClose:
    def test_cancel_behaves_like_close(self):
        from input.panel_dispatcher import PanelDispatcher

        class Game:
            def __init__(self):
                self.state = GameState.TRADE_PANEL
                self._trade_panel = type("P", (), {"close": lambda s: None})()
                self._quest_panel = None
                self._recruit_panel = None
                self._diplomacy_panel = None
                self._inventory_panel = None
                self._skill_panel = None
                self._crafting_panel = None
                self._building_panel = None
                self._gear_panel = None
                self._character_select_panel = None

            def set_state(self, s):
                self.state = s

        game = Game()
        PanelDispatcher(game).dispatch(GameState.TRADE_PANEL, ("cancel",))
        assert game.state == GameState.PLAYING


# ── 4.9 ESC from ERROR clears stale error ────────────────────────────────────


class TestErrorRecovery:
    def test_esc_from_error_clears_error(self):
        from ui.loading_screen import handle_loading_event

        class Game:
            def __init__(self):
                self.state = GameState.ERROR
                self._world_gen_error = "boom"
                self.loading_progress = 1.0
                self.world = object()
                self.player = object()

            def set_state(self, s):
                self.state = s

        game = Game()
        handle_loading_event(
            game, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
        )
        assert game.state == GameState.TITLE
        assert game._world_gen_error is None
        assert game.loading_progress == 0.0
        assert game.world is None
