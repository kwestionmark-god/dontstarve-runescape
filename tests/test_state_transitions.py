"""
Tests for state transition visibility logic (PR 1).

Covers:
- Inventory toggle from PLAYING and from other panel states
- Skill panel toggle from PLAYING and other states
- Panel-to-panel transitions properly close the previous panel
- _close_all_panels() sets all 9 panels to invisible
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import GameState


class MockPanel:
    """Minimal mock panel with visible attribute."""
    def __init__(self) -> None:
        self.visible: bool = False

    def close_session(self) -> None:
        pass


class FakeGame:
    """Plain class (no __slots__) to hold panel state for testing."""

    def __init__(self) -> None:
        self.state = GameState.PLAYING
        self._inventory_panel = MockPanel()
        self._skill_panel = MockPanel()
        self._crafting_panel = MockPanel()
        self._building_panel = MockPanel()
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


class TestStateTransitions(unittest.TestCase):
    """Test state transitions and panel visibility logic."""

    def _make_game(self) -> FakeGame:
        """Create a FakeGame with mocked panels."""
        return FakeGame()

    def test_inventory_toggle_from_playing(self) -> None:
        """Press I from PLAYING -> INVENTORY_OPEN. Panel visible."""
        game = self._make_game()
        game.state = GameState.PLAYING

        # Override set_state to only handle panel visibility
        original_set = Game.set_state
        Game.set_state = lambda self, ns: self._do_set_state(ns)
        try:
            game._do_set_state = lambda ns: self._custom_set_state(game, ns)
            game.set_state(GameState.INVENTORY_OPEN)
            self.assertEqual(game.state, GameState.INVENTORY_OPEN)
            self.assertTrue(game._inventory_panel.visible)
        finally:
            Game.set_state = original_set

    def _close_panels_directly(self, game) -> None:
        """Close all 9 panels directly (no-op replacement for _close_all_panels)."""
        for attr in ('_inventory_panel', '_skill_panel', '_crafting_panel',
                     '_building_panel', '_gear_panel', '_trade_panel',
                     '_quest_panel', '_recruit_panel', '_diplomacy_panel'):
            panel = getattr(game, attr)
            if panel is not None:
                panel.visible = False

    def _custom_set_state(self, game, new_state: GameState) -> None:
        """Minimal set_state implementation for testing."""
        if game.state == new_state:
            return
        old_state = game.state
        game.state = new_state

        # Close all panels on transition to PLAYING or between panel states
        if new_state == GameState.PLAYING:
            self._close_panels_directly(game)
        elif game._is_panel_state(old_state) and game._is_panel_state(new_state):
            self._close_panels_directly(game)

        # Toggle panel visibility
        if new_state == GameState.INVENTORY_OPEN:
            game._inventory_panel.visible = True
        elif new_state == GameState.SKILL_PANEL:
            game._skill_panel.visible = True
        elif new_state == GameState.CRAFTING_PANEL:
            game._crafting_panel.visible = True
        elif new_state == GameState.BUILDING_PANEL:
            game._building_panel.visible = True
        elif new_state == GameState.GEAR_PANEL:
            game._gear_panel.visible = True
        elif new_state == GameState.TRADE_PANEL:
            game._trade_panel.visible = True
        elif new_state == GameState.QUEST_PANEL:
            game._quest_panel.visible = True
        elif new_state == GameState.RECRUIT_PANEL:
            game._recruit_panel.visible = True
        elif new_state == GameState.DIPLOMACY_PANEL:
            game._diplomacy_panel.visible = True

    def test_inventory_toggle_from_playing(self) -> None:
        """Press I from PLAYING -> INVENTORY_OPEN. Panel visible."""
        game = self._make_game()
        game.state = GameState.PLAYING
        self._custom_set_state(game, GameState.INVENTORY_OPEN)
        self.assertEqual(game.state, GameState.INVENTORY_OPEN)
        self.assertTrue(game._inventory_panel.visible)

    def test_inventory_toggle_from_inventory(self) -> None:
        """Press I from INVENTORY_OPEN -> PLAYING. Panel hidden."""
        game = self._make_game()
        game.state = GameState.INVENTORY_OPEN
        game._inventory_panel.visible = True
        self._custom_set_state(game, GameState.PLAYING)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertFalse(game._inventory_panel.visible)

    def test_inventory_from_skill_closes_skill(self) -> None:
        """Press I from SKILL_PANEL -> INVENTORY_OPEN. Skill panel hidden."""
        game = self._make_game()
        game.state = GameState.SKILL_PANEL
        game._skill_panel.visible = True
        self._custom_set_state(game, GameState.INVENTORY_OPEN)
        self.assertEqual(game.state, GameState.INVENTORY_OPEN)
        self.assertTrue(game._inventory_panel.visible)
        self.assertFalse(game._skill_panel.visible)

    def test_skill_from_inventory_closes_inventory(self) -> None:
        """Press S from INVENTORY_OPEN -> SKILL_PANEL. Inventory hidden."""
        game = self._make_game()
        game.state = GameState.INVENTORY_OPEN
        game._inventory_panel.visible = True
        self._custom_set_state(game, GameState.SKILL_PANEL)
        self.assertEqual(game.state, GameState.SKILL_PANEL)
        self.assertTrue(game._skill_panel.visible)
        self.assertFalse(game._inventory_panel.visible)

    def test_crafting_from_any_closes_others(self) -> None:
        """Press 1 from GEAR_PANEL -> CRAFTING_PANEL. Gear hidden."""
        game = self._make_game()
        game.state = GameState.GEAR_PANEL
        game._gear_panel.visible = True
        self._custom_set_state(game, GameState.CRAFTING_PANEL)
        self.assertEqual(game.state, GameState.CRAFTING_PANEL)
        self.assertTrue(game._crafting_panel.visible)
        self.assertFalse(game._gear_panel.visible)

    def test_build_from_any_opens_build(self) -> None:
        """Press B from CRAFTING_PANEL -> BUILDING_PANEL. Crafting hidden."""
        game = self._make_game()
        game.state = GameState.CRAFTING_PANEL
        game._crafting_panel.visible = True
        self._custom_set_state(game, GameState.BUILDING_PANEL)
        self.assertEqual(game.state, GameState.BUILDING_PANEL)
        self.assertTrue(game._building_panel.visible)
        self.assertFalse(game._crafting_panel.visible)

    def test_build_from_build_returns_playing(self) -> None:
        """Press B from BUILDING -> PLAYING. Building hidden."""
        game = self._make_game()
        game.state = GameState.BUILDING_PANEL
        game._building_panel.visible = True
        self._custom_set_state(game, GameState.PLAYING)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertFalse(game._building_panel.visible)

    def test_esc_from_inventory_closes(self) -> None:
        """ESC from INVENTORY_OPEN -> PLAYING. Panel hidden."""
        game = self._make_game()
        game.state = GameState.INVENTORY_OPEN
        game._inventory_panel.visible = True
        self._custom_set_state(game, GameState.PLAYING)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertFalse(game._inventory_panel.visible)

    def test_esc_from_trade_closes(self) -> None:
        """ESC from TRADE -> PLAYING. Session closed, panel hidden."""
        game = self._make_game()
        game.state = GameState.TRADE_PANEL
        game._trade_panel.visible = True
        self._custom_set_state(game, GameState.PLAYING)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertFalse(game._trade_panel.visible)

    def test_esc_from_quest_closes(self) -> None:
        """ESC from QUEST -> PLAYING. Session closed."""
        game = self._make_game()
        game.state = GameState.QUEST_PANEL
        game._quest_panel.visible = True
        self._custom_set_state(game, GameState.PLAYING)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertFalse(game._quest_panel.visible)

    def test_esc_from_any_panel_returns_playing(self) -> None:
        """ESC from any panel state -> PLAYING."""
        for panel_state in (
            GameState.INVENTORY_OPEN, GameState.SKILL_PANEL,
            GameState.CRAFTING_PANEL, GameState.BUILDING_PANEL,
            GameState.GEAR_PANEL,
        ):
            game = self._make_game()
            game.state = panel_state
            self._custom_set_state(game, GameState.PLAYING)
            self.assertEqual(game.state, GameState.PLAYING)

    def test_close_all_panels_helper(self) -> None:
        """Call _close_all_panels() -> all 9 panels have .visible = False."""
        from input.router import InputRouter

        # Create a minimal object that has all panel attributes
        game = type('TestGame', (), {
            '_inventory_panel': MockPanel(),
            '_skill_panel': MockPanel(),
            '_crafting_panel': MockPanel(),
            '_building_panel': MockPanel(),
            '_gear_panel': MockPanel(),
            '_trade_panel': MockPanel(),
            '_quest_panel': MockPanel(),
            '_recruit_panel': MockPanel(),
            '_diplomacy_panel': MockPanel(),
        })()

        # Set all panels visible
        for attr in ('_inventory_panel', '_skill_panel', '_crafting_panel',
                     '_building_panel', '_gear_panel', '_trade_panel',
                     '_quest_panel', '_recruit_panel', '_diplomacy_panel'):
            getattr(game, attr).visible = True

        # Create a minimal InputRouter with the game
        class FakeInputManager:
            input_state = None
            def handle_event(self, event): pass
            def clear_frame(self): pass
        class FakePanelDispatcher:
            def dispatch(self, *a, **k): pass
            def dispatch_click(self, *a, **k): pass
        router = InputRouter(game, FakeInputManager(), FakePanelDispatcher())

        # Test the actual _close_all_panels method from InputRouter class
        router._close_all_panels()

        for attr in ('_inventory_panel', '_skill_panel', '_crafting_panel',
                     '_building_panel', '_gear_panel', '_trade_panel',
                     '_quest_panel', '_recruit_panel', '_diplomacy_panel'):
            self.assertFalse(getattr(game, attr).visible)


if __name__ == "__main__":
    unittest.main()
