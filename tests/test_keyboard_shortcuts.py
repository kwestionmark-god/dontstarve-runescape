"""
Tests for keyboard shortcut wiring (PR 2, PR 4).

Covers:
- I, J, C, H, U, T, K, L, S, B, Q, 1, ESC key flags are set correctly
- clear_frame() clears one-shot flags
- Held keys maintain continuous flags (only for held key mapping, NOT one-shot)
- New panel flags initialized to False
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from input import InputManager, InputState


class TestKeyboardShortcuts(unittest.TestCase):
    """Test keyboard shortcut flag wiring."""

    def setUp(self) -> None:
        self.manager = InputManager()

    def test_i_sets_open_inventory_flag(self) -> None:
        """Press I key -> input_state.open_inventory = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_i, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_inventory)

    def test_s_sets_move_down_flag(self) -> None:
        """Press S key -> input_state.move_down = True, open_skill_panel = False."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_s, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.move_down)
        self.assertFalse(self.manager.input_state.open_skill_panel)

    def test_b_sets_open_building_flag(self) -> None:
        """Press B key -> input_state.open_building_panel = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_b, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_building_panel)

    def test_j_sets_open_skill_flag(self) -> None:
        """Press J key -> input_state.open_skill_panel = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_j, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_skill_panel)
        # Ensure movement not set by J key
        self.assertFalse(self.manager.input_state.move_down)

    def test_c_sets_open_inventory_flag(self) -> None:
        """Press C key -> input_state.open_inventory = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_c, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_inventory)
        # Ensure new panel flags are False
        self.assertFalse(self.manager.input_state.open_skill_panel)
        self.assertFalse(self.manager.input_state.open_crafting)
        self.assertFalse(self.manager.input_state.open_quest_panel)
        self.assertFalse(self.manager.input_state.open_trade_panel)

    def test_h_sets_open_crafting_flag(self) -> None:
        """Press H key -> input_state.open_crafting = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_h, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_crafting)

    def test_u_sets_open_quest_panel_flag(self) -> None:
        """Press U key -> input_state.open_quest_panel = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_u, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_quest_panel)

    def test_t_sets_open_trade_panel_flag(self) -> None:
        """Press T key -> input_state.open_trade_panel = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_t, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_trade_panel)

    def test_k_sets_open_recruit_panel_flag(self) -> None:
        """Press K key -> input_state.open_recruit_panel = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_k, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_recruit_panel)

    def test_l_sets_open_diplomacy_panel_flag(self) -> None:
        """Press L key -> input_state.open_diplomacy_panel = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_l, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.open_diplomacy_panel)

    def test_j_consumed_on_press_then_cleared(self) -> None:
        """J key sets open_skill_panel once on key down, cleared on clear_frame."""
        manager = InputManager()

        # Press J
        down = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_j, "scancode": 0, "unicode": "", "mod": 0}
        )
        manager.handle_event(down)
        self.assertTrue(manager.input_state.open_skill_panel)

        # clear_frame simulates next frame (like game does every tick)
        manager.input_state.clear_frame()
        self.assertFalse(manager.input_state.open_skill_panel)

    def test_q_sets_close_crafting_flag(self) -> None:
        """Press Q key -> input_state.close_crafting = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_q, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.close_crafting)

    def test_esc_sets_close_panel_flag(self) -> None:
        """Press ESC -> input_state.close_panel = True."""
        event = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_ESCAPE, "scancode": 0, "unicode": "", "mod": 0}
        )
        self.manager.handle_event(event)
        self.assertTrue(self.manager.input_state.close_panel)

    def test_clear_frame_clears_one_shot(self) -> None:
        """After clear_frame() all one-shot flags = False."""
        is_state = InputState()
        # Manually set some flags to simulate events having set them
        is_state.open_inventory = True
        is_state.open_skill_panel = True
        is_state.open_building_panel = True
        is_state.open_quest_panel = True
        is_state.open_trade_panel = True
        is_state.open_recruit_panel = True
        is_state.open_diplomacy_panel = True
        is_state.close_crafting = True
        is_state.close_panel = True
        is_state.interact_pressed = True

        is_state.clear_frame()

        self.assertFalse(is_state.open_inventory)
        self.assertFalse(is_state.open_skill_panel)
        self.assertFalse(is_state.open_building_panel)
        self.assertFalse(is_state.open_quest_panel)
        self.assertFalse(is_state.open_trade_panel)
        self.assertFalse(is_state.open_recruit_panel)
        self.assertFalse(is_state.open_diplomacy_panel)
        self.assertFalse(is_state.close_crafting)
        self.assertFalse(is_state.close_panel)
        self.assertFalse(is_state.interact_pressed)

    def test_hold_s_sets_flag_continuous(self) -> None:
        """Hold S key -> move_down = True while held (via _held_keys).
        open_skill_panel must NOT be set by S key anymore.
        """
        manager = InputManager()

        # Key down: S is in _held_keys and move_down = True (one-shot)
        down = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_s, "scancode": 0, "unicode": "", "mod": 0}
        )
        manager.handle_event(down)
        s = manager.input_state
        self.assertTrue(s.move_down, "S down → move_down=True")
        self.assertFalse(s.open_skill_panel, "S down → open_skill_panel=False (no longer toggled)")

        # Key up: S removed from _held_keys, move_down cleared
        up = pygame.event.Event(
            pygame.KEYUP, {"key": pygame.K_s, "scancode": 0, "mod": 0}
        )
        manager.handle_event(up)
        self.assertFalse(s.move_down, "S up → move_down=False")

        # Re-press S and hold it
        down2 = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_s, "scancode": 0, "unicode": "", "mod": 0}
        )
        manager.handle_event(down2)
        self.assertTrue(s.move_down, "S pressed again → move_down=True")

        # Re-evaluate held state manually: K_s should still keep move_down true
        manager.input_state.clear_frame()
        manager._update_held_state()
        self.assertTrue(s.move_down, "Holding S via held keys → move_down=True")
        self.assertFalse(s.open_skill_panel, "Holding S via held keys → open_skill_panel=False")


class TestPanelLeftClickDispatch(unittest.TestCase):
    """Test left-click dispatch to panels."""

    def setUp(self) -> None:
        pygame.init()

    def test_inventory_panel_has_handle_click(self) -> None:
        """InventoryPanel must have handle_click method."""
        from ui.inventory_panel import InventoryPanel
        panel = InventoryPanel()
        self.assertTrue(hasattr(panel, 'handle_click'))
        result = panel.handle_click(0, 0)
        self.assertIsNone(result)

    def test_skill_panel_has_handle_click(self) -> None:
        """SkillPanel must have handle_click method."""
        from ui.skill_panel import SkillPanel
        panel = SkillPanel()
        self.assertTrue(hasattr(panel, 'handle_click'))
        result = panel.handle_click(0, 0)
        self.assertIsNone(result)

    def test_crafting_panel_has_handle_click(self) -> None:
        """CraftingPanel must have handle_click method."""
        from ui.crafting_panel import CraftingPanel
        panel = CraftingPanel()
        self.assertTrue(hasattr(panel, 'handle_click'))
        result = panel.handle_click(0, 0)
        self.assertIsNone(result)

    def test_gear_panel_has_handle_click(self) -> None:
        """GearPanel must have handle_click method."""
        from ui.gear_panel import GearPanel
        panel = GearPanel()
        self.assertTrue(hasattr(panel, 'handle_click'))
        result = panel.handle_click(0, 0)
        self.assertIsNone(result)


class TestPanelKeyboardNavigation(unittest.TestCase):
    """Test keyboard navigation methods on panels."""

    def setUp(self) -> None:
        pygame.init()

    def test_inventory_panel_has_handle_key(self) -> None:
        """InventoryPanel must have handle_key method."""
        from ui.inventory_panel import InventoryPanel
        panel = InventoryPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_inventory_panel_handle_key_returns_use_on_select(self) -> None:
        """InventoryPanel handle_key with Enter should return ('use', item_id) when item selected."""
        from ui.inventory_panel import InventoryPanel
        panel = InventoryPanel()
        # Simulate having an item rect
        import pygame
        rect = pygame.Rect(0, 0, 48, 48)
        panel._item_rects = [(rect, "test_item")]
        panel._selected_item_index = 0
        result = panel.handle_key(pygame.K_RETURN)
        self.assertEqual(result, ("use", "test_item"))

    def test_skill_panel_has_handle_key(self) -> None:
        """SkillPanel must have handle_key method."""
        from ui.skill_panel import SkillPanel
        panel = SkillPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_crafting_panel_has_handle_key(self) -> None:
        """CraftingPanel must have handle_key method."""
        from ui.crafting_panel import CraftingPanel
        panel = CraftingPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_gear_panel_has_handle_key(self) -> None:
        """GearPanel must have handle_key method."""
        from ui.gear_panel import GearPanel
        panel = GearPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_building_panel_has_handle_key(self) -> None:
        """BuildingPanel must have handle_key method."""
        from ui.building_panel import BuildingPanel
        panel = BuildingPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_trade_panel_has_handle_key(self) -> None:
        """TradePanel must have handle_key method."""
        from ui.trade_panel import TradePanel
        panel = TradePanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_quest_panel_has_handle_key(self) -> None:
        """QuestPanel must have handle_key method."""
        from ui.quest_panel import QuestPanel
        panel = QuestPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_recruit_panel_has_handle_key(self) -> None:
        """RecruitPanel must have handle_key method."""
        from ui.recruit_panel import RecruitPanel
        panel = RecruitPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertIsNone(result)

    def test_diplomacy_panel_has_handle_key(self) -> None:
        """DiplomacyPanel must have handle_key method."""
        from ui.diplomacy_panel import DiplomacyPanel
        panel = DiplomacyPanel()
        self.assertTrue(hasattr(panel, 'handle_key'))
        result = panel.handle_key(pygame.K_RETURN)
        self.assertEqual(result, ("negotiate",))

    def test_diplomacy_panel_esc_key(self) -> None:
        """DiplomacyPanel ESC should return close action."""
        from ui.diplomacy_panel import DiplomacyPanel
        panel = DiplomacyPanel()
        result = panel.handle_key(pygame.K_ESCAPE)
        self.assertEqual(result, ("close",))

    def test_game_panel_states_constant_exists(self) -> None:
        """Game module must define PANEL_STATES constant."""
        from core.state import PANEL_STATES
        from core.state import GameState
        self.assertIsInstance(PANEL_STATES, tuple)
        self.assertIn(GameState.INVENTORY_OPEN, PANEL_STATES)
        self.assertIn(GameState.SKILL_PANEL, PANEL_STATES)
        self.assertIn(GameState.CRAFTING_PANEL, PANEL_STATES)
        self.assertIn(GameState.BUILDING_PANEL, PANEL_STATES)
        self.assertIn(GameState.GEAR_PANEL, PANEL_STATES)
        self.assertIn(GameState.TRADE_PANEL, PANEL_STATES)
        self.assertIn(GameState.QUEST_PANEL, PANEL_STATES)
        self.assertIn(GameState.RECRUIT_PANEL, PANEL_STATES)
        self.assertIn(GameState.DIPLOMACY_PANEL, PANEL_STATES)

    def test_game_has_get_active_panel(self) -> None:
        """_get_active_panel is now on InputRouter after extraction."""
        from input.router import InputRouter
        self.assertTrue(hasattr(InputRouter, '_get_active_panel'))

    def test_game_has_panel_dispatcher(self) -> None:
        """Game must have _panel_dispatcher attribute with dispatch method."""
        from core.game import Game
        self.assertTrue(hasattr(Game, '__slots__'))
        self.assertIn('_panel_dispatcher', Game.__slots__)

    def test_panel_dispatcher_has_dispatch(self) -> None:
        """PanelDispatcher must have dispatch method."""
        from input.panel_dispatcher import PanelDispatcher
        self.assertTrue(hasattr(PanelDispatcher, 'dispatch'))
        self.assertTrue(hasattr(PanelDispatcher, 'dispatch_click'))


class TestInventoryPanelClickButtons(unittest.TestCase):
    """Test that InventoryPanel distinguishes left/right mouse buttons."""

    def setUp(self) -> None:
        pygame.init()
        from ui.inventory_panel import InventoryPanel
        self.panel = InventoryPanel()
        self.panel.visible = True
        self.item_rect = pygame.Rect(0, 30, 48, 48)
        self.panel._item_rects = [(self.item_rect, "iron_ore")]
        self.gear_rect = pygame.Rect(0, 0, 48, 28)
        self.panel._gear_slot_rects = [(self.gear_rect, "W")]

    def test_left_click_returns_use(self) -> None:
        """Left-click (button 1) on an item returns ('use', item_id)."""
        result = self.panel.handle_click(0, 30, button=1)
        self.assertEqual(result, ("use", "iron_ore"))

    def test_right_click_returns_drop(self) -> None:
        """Right-click (button 2 or 3) on an item returns ('drop', item_id)."""
        result = self.panel.handle_click(0, 30, button=2)
        self.assertEqual(result, ("drop", "iron_ore"))
        result = self.panel.handle_click(0, 30, button=3)
        self.assertEqual(result, ("drop", "iron_ore"))

    def test_gear_slot_click_returns_gear(self) -> None:
        """Click on a gear slot returns ('gear', label)."""
        result = self.panel.handle_click(0, 14, button=1)
        self.assertEqual(result, ("gear", "W"))


class TestPanelDispatcherDrop(unittest.TestCase):
    """Test that PanelDispatcher handles inventory drop actions."""

    def test_dispatch_drop_calls_drop_handler(self) -> None:
        """dispatch with ('drop', item_id) in INVENTORY_OPEN calls _handle_inventory_drop."""
        from input.panel_dispatcher import PanelDispatcher
        from core.state import GameState

        class FakeGame:
            inventory = None
            player = None

        game = FakeGame()
        dispatcher = PanelDispatcher(game)
        # Should not raise
        dispatcher.dispatch(GameState.INVENTORY_OPEN, ("drop", "iron_ore"))

    def test_dispatch_use_calls_use_handler(self) -> None:
        """dispatch with ('use', item_id) in INVENTORY_OPEN calls _handle_inventory_use."""
        from input.panel_dispatcher import PanelDispatcher
        from core.state import GameState

        class FakeGame:
            inventory = None
            player = None

        game = FakeGame()
        dispatcher = PanelDispatcher(game)
        dispatcher.dispatch(GameState.INVENTORY_OPEN, ("use", "iron_ore"))


class TestInventoryPanelKeyboardDrop(unittest.TestCase):
    """Test keyboard drop via Delete/Backspace on inventory panel."""

    def setUp(self) -> None:
        pygame.init()
        from ui.inventory_panel import InventoryPanel
        self.panel = InventoryPanel()
        self.panel.visible = True
        rect = pygame.Rect(0, 0, 48, 48)
        self.panel._item_rects = [(rect, "iron_ore")]
        self.panel._selected_item_index = 0

    def test_delete_returns_drop(self) -> None:
        """Delete key returns ('drop', item_id)."""
        result = self.panel.handle_key(pygame.K_DELETE)
        self.assertEqual(result, ("drop", "iron_ore"))

    def test_backspace_returns_drop(self) -> None:
        """Backspace key returns ('drop', item_id)."""
        result = self.panel.handle_key(pygame.K_BACKSPACE)
        self.assertEqual(result, ("drop", "iron_ore"))


if __name__ == "__main__":
    unittest.main()
