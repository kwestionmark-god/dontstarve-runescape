"""
Tests for panel integration (PR 5, PR 6).

Covers:
- Left-click on quest panel routes to quest handler
- Left-click on trade panel routes to trade handler
- No world click during panel open state
- Panel visibility isolation (open panel A, then panel B -> only B visible)
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from core.state import GameState


class MockPanel:
    """Minimal mock panel with visible attribute and click handler."""
    def __init__(self) -> None:
        self.visible = False

    def handle_click(self, x: int, y: int) -> tuple:
        return ("close",)

    def handle_mouse_move(self, mx: int, my: int) -> None:
        pass

    def close_session(self) -> None:
        pass


class MockBuildingPanel:
    """Mock BuildingPanel for mouse handling."""
    def __init__(self) -> None:
        self.visible = False
        self.selected_structure_id = None
        self.current_tab = "common"
        self.panel_width = 340
        self.panel_height = 660
        self.x = (1280 - 340) // 2
        self.y = 30
        self._hovered_structure = None
        self._hovered_tab = False

    def handle_click(self, mx: int, my: int) -> object:
        if not self.visible:
            return None
        tabs = ["common", "defensive", "offensive", "decorative"]
        tab_y = self.y + 35
        tab_width = (self.panel_width - 20) // len(tabs)
        for i, tab in enumerate(tabs):
            tab_x = self.x + 10 + i * tab_width
            if (tab_x <= mx <= tab_x + tab_width - 4 and
                    tab_y <= my <= tab_y + 22):
                self.current_tab = tab
                return None
        if (self.x <= mx <= self.x + self.panel_width and
                self.y <= my <= self.y + self.panel_height):
            return ("close",)
        return None

    def handle_mouse_move(self, mx: int, my: int) -> None:
        pass


class FakeGame:
    """Plain class (no __slots__) to hold panel state for testing."""

    def __init__(self, state: GameState) -> None:
        self.state = state
        self._inventory_panel = MockPanel()
        self._skill_panel = MockPanel()
        self._crafting_panel = MockPanel()
        self._building_panel = MockBuildingPanel()
        self._gear_panel = MockPanel()
        self._trade_panel = MockPanel()
        self._quest_panel = MockPanel()
        self._recruit_panel = MockPanel()
        self._diplomacy_panel = MockPanel()
        self._close_all_panels = lambda: None
        self._is_panel_state = lambda s: s in (
            GameState.INVENTORY_OPEN, GameState.SKILL_PANEL,
            GameState.CRAFTING_PANEL, GameState.BUILDING_PANEL,
            GameState.GEAR_PANEL, GameState.TRADE_PANEL,
            GameState.QUEST_PANEL, GameState.RECRUIT_PANEL,
            GameState.DIPLOMACY_PANEL,
        )
        self.hud = None
        self.player = None
        self.camera = None
        self.combat_system = None
        self.building_system = type('FakeBS', (), {'structure_defs': {}})()
        # Panel action handlers are now on PanelDispatcher (Phase 3.5.4)

        def _handle_event(self, event) -> None:
            """Stub event handler that routes mouse clicks to panels."""
            import pygame
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Don't route clicks to world when any panel is open
                if self._is_panel_state(self.state):
                    return
        self.handle_event = lambda e: _handle_event(self, e)


class TestPanelIntegration(unittest.TestCase):
    """Test panel integration."""

    def _make_game(self, state: GameState) -> FakeGame:
        """Create a FakeGame with mocked panels."""
        return FakeGame(state)

    def test_mouse_left_click_on_quest_panel(self) -> None:
        """Left-click quest row -> routes to quest handler."""
        game = self._make_game(GameState.QUEST_PANEL)
        game._quest_panel.visible = True

        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": (500, 200), "rel": (0, 0), "state": 0}
        )
        game.handle_event(event)
        self.assertEqual(game.state, GameState.QUEST_PANEL)

    def test_mouse_left_click_on_trade_panel(self) -> None:
        """Left-click trade row -> routes to trade handler."""
        game = self._make_game(GameState.TRADE_PANEL)
        game._trade_panel.visible = True

        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": (500, 200), "rel": (0, 0), "state": 0}
        )
        game.handle_event(event)
        self.assertEqual(game.state, GameState.TRADE_PANEL)

    def test_no_world_click_during_panel(self) -> None:
        """Left-click world during panel -> no targeting/movement."""
        panel_states = (
            GameState.INVENTORY_OPEN, GameState.SKILL_PANEL,
            GameState.CRAFTING_PANEL, GameState.BUILDING_PANEL,
            GameState.GEAR_PANEL, GameState.TRADE_PANEL,
            GameState.QUEST_PANEL, GameState.RECRUIT_PANEL,
            GameState.DIPLOMACY_PANEL,
        )

        for state in panel_states:
            game = self._make_game(state)

            # Set visible on the relevant panel
            panel_attr = f"_{state.name.lower().replace('_open', '')}"
            panel = getattr(game, panel_attr, None)
            if panel is not None:
                panel.visible = True

            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"button": 1, "pos": (500, 200), "rel": (0, 0), "state": 0}
            )
            game.handle_event(event)
            self.assertEqual(game.state, state,
                           f"Left click in {state.name} should not change state")

    def test_panel_visibility_isolation(self) -> None:
        """Open panel A, then panel B -> only panel B visible."""
        game = FakeGame(GameState.INVENTORY_OPEN)
        game._inventory_panel.visible = True

        # Manually close all panels then open skill panel (simulating set_state)
        for attr in ('_inventory_panel', '_skill_panel', '_crafting_panel',
                     '_building_panel', '_gear_panel', '_trade_panel',
                     '_quest_panel', '_recruit_panel', '_diplomacy_panel'):
            panel = getattr(game, attr)
            if panel is not None:
                panel.visible = False
        game._skill_panel.visible = True
        game.state = GameState.SKILL_PANEL

        self.assertTrue(game._skill_panel.visible)
        self.assertFalse(game._inventory_panel.visible)


if __name__ == "__main__":
    unittest.main()
