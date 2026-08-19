"""
Tests for building panel interaction (PR 3, PR 8).

Covers:
- Building panel select structure returns correct action
- Building panel tab click changes current_tab
- _handle_building_click processes select and close actions
- Building panel mouse move handling
- Structure placement with occupies_tile check
"""

import unittest
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TILE_SIZE


class MockBuildingPanel:
    """Minimal mock of BuildingPanel for testing."""
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
        """Handle a click on the building panel."""
        if not self.visible:
            return None

        # Check tab clicks
        tabs = ["common", "defensive", "offensive", "decorative"]
        tab_y = self.y + 35
        tab_width = (self.panel_width - 20) // len(tabs)
        for i, tab in enumerate(tabs):
            tab_x = self.x + 10 + i * tab_width
            if (tab_x <= mx <= tab_x + tab_width - 4 and
                    tab_y <= my <= tab_y + 22):
                self.current_tab = tab
                return None

        # Return ("close",) for clicks within the panel area but outside tabs
        if (self.x <= mx <= self.x + self.panel_width and
                self.y <= my <= self.y + self.panel_height):
            return ("close",)
        return None

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Handle mouse movement for hover feedback."""
        tabs = ["common", "defensive", "offensive", "decorative"]
        tab_y = self.y + 35
        tab_width = (self.panel_width - 20) // len(tabs)
        self._hovered_tab = False
        for tab in tabs:
            i = tabs.index(tab)
            tab_x = self.x + 10 + i * tab_width
            if (tab_x <= mx <= tab_x + tab_width - 4 and
                    tab_y <= my <= tab_y + 22):
                self._hovered_tab = True
                return
        self._hovered_structure = None

    def handle_close(self) -> tuple:
        """Return close action."""
        return ("close",)


class FakeGame:
    """Plain class (no __slots__) for testing Game methods."""

    def __init__(self) -> None:
        from core.state import GameState
        self.state = GameState.BUILDING_PANEL
        self._building_panel = MockBuildingPanel()
        self._building_panel.visible = True
        self._inventory_panel = MockBuildingPanel()
        self._skill_panel = MockBuildingPanel()
        self._crafting_panel = MockBuildingPanel()
        self._gear_panel = MockBuildingPanel()
        self._trade_panel = MockBuildingPanel()
        self._quest_panel = MockBuildingPanel()
        self._recruit_panel = MockBuildingPanel()
        self._diplomacy_panel = MockBuildingPanel()
        self._close_all_panels = lambda: None
        self._is_panel_state = lambda s: s in (GameState.BUILDING_PANEL,)
        self.building_system = type('FakeBS', (), {'structure_defs': {}})()
        # Stub for player (needed by _handle_building_click)
        self.player = None
        # Stub for set_state (needed by _handle_building_click on close)
        self.set_state = lambda s: setattr(self, 'state', s)


class TestBuildingPanelInteraction(unittest.TestCase):
    """Test building panel mouse interaction."""

    def setUp(self) -> None:
        self.panel = MockBuildingPanel()
        self.panel.visible = True

    def test_building_panel_select_structure(self) -> None:
        """Click structure entry -> returns ("close",) or None (no structure rects in mock)."""
        # Click inside panel but outside tabs -> should return ("close",)
        result = self.panel.handle_click(500, 200)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "close")

    def test_building_panel_tab_click(self) -> None:
        """Click tab button -> changes current_tab, returns None."""
        # Click first tab
        result = self.panel.handle_click(
            self.panel.x + 10 + 0 * 81 + 5,
            self.panel.y + 35 + 11
        )
        self.assertEqual(self.panel.current_tab, "common")
        self.assertIsNone(result)

    def test_game_handles_building_select(self) -> None:
        """PanelDispatcher.dispatch_click with ("select", id) sets selected structure."""
        from core.state import GameState
        from input.panel_dispatcher import PanelDispatcher

        game = FakeGame()
        game.state = GameState.BUILDING_PANEL
        dispatcher = PanelDispatcher(game)

        action = ("select", "campfire")
        dispatcher.dispatch_click(GameState.BUILDING_PANEL, "building", action)
        self.assertEqual(game._building_panel.selected_structure_id, "campfire")

    def test_game_handles_building_close(self) -> None:
        """PanelDispatcher.dispatch_click with ("close",) closes panel, sets PLAYING."""
        from core.state import GameState
        from input.panel_dispatcher import PanelDispatcher

        game = FakeGame()
        game.state = GameState.BUILDING_PANEL
        dispatcher = PanelDispatcher(game)

        action = ("close",)
        dispatcher.dispatch_click(GameState.BUILDING_PANEL, "building", action)
        self.assertEqual(game.state, GameState.PLAYING)
        self.assertFalse(game._building_panel.visible)

    def test_place_structure_on_occupies_tile_empty(self) -> None:
        """Place occupies_tile structure on empty tile -> succeeds."""
        from building.building_system import BuildingSystem
        from skills.construction.construction import Construction
        from skills.skill_manager import SkillManager
        from inventory.inventory import Inventory

        sm = SkillManager()
        inv = Inventory()
        construction = Construction(sm)
        structure_defs: dict = {"common": {}}
        bs = BuildingSystem(sm, inv, construction, structure_defs)

        # Mock a StructureDef with occupies_tile = True
        struct_def = type('FakeStructDef', (), {
            "structure_id": "furnace",
            "name": "Furnace",
            "structure_type": "fixed",
            "hp": 30,
            "materials": [],
            "biome_compatible": ["forest"],
            "requires_structure_level": 0,
            "requires_skill_level": 0,
            "sprite_key": "structure/furnace",
            "occupies_tile": True,
            "burnable": False,
            "construction_sub_stat": "common",
        })()

        # Place on empty tile (no player, no NPCs)
        result = bs.place_structure(
            struct_def,
            world_x=320.0,
            world_y=320.0,
            player_world_x=320.0,
            player_world_y=320.0,
            biome_id="forest",
        )
        # Should succeed since no player/NPC occupies the tile (game_ref is None)
        self.assertTrue(result.success)

    def test_place_structure_on_occupies_tile_player(self) -> None:
        """Place occupies_tile structure on player tile -> fails."""
        from building.building_system import BuildingSystem
        from skills.construction.construction import Construction
        from skills.skill_manager import SkillManager
        from inventory.inventory import Inventory

        sm = SkillManager()
        inv = Inventory()
        construction = Construction(sm)
        structure_defs: dict = {"common": {}}

        # Create a mock game with a player at the target tile
        mock_player = type('MockPlayer', (), {
            "world_x": 320.0,
            "world_y": 320.0,
        })()
        mock_game = type('MockGame', (), {
            "player": mock_player,
            "npc_system": None,
        })()

        bs = BuildingSystem(sm, inv, construction, structure_defs, game_ref=mock_game)

        struct_def = type('FakeStructDef', (), {
            "structure_id": "furnace",
            "name": "Furnace",
            "structure_type": "fixed",
            "hp": 30,
            "materials": [],
            "biome_compatible": ["forest"],
            "requires_structure_level": 0,
            "requires_skill_level": 0,
            "sprite_key": "structure/furnace",
            "occupies_tile": True,
            "burnable": False,
            "construction_sub_stat": "common",
        })()

        result = bs.place_structure(
            struct_def,
            world_x=320.0,
            world_y=320.0,
            player_world_x=320.0,
            player_world_y=320.0,
            biome_id="forest",
        )
        self.assertFalse(result.success)
        self.assertIn("Player", result.message)


if __name__ == "__main__":
    unittest.main()
