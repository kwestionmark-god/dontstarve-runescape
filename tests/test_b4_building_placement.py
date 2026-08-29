"""
B4 — Building placement is wired into gameplay (Phase 5).

Previously `building_system.place_structure` was only reachable from tests and
selecting a structure only printed a prompt. This suite proves the full
build → consume → XP → place pipeline fires:

- Selecting a structure in the building panel closes the palette and enters
  `build_mode` (a PLAYING sub-state).
- Left-click on the world places the structure (validate + consume + XP + place).
- Right-click / ESC cancels placement; invalid placement stays in mode and
  reports the reason.
- Hotbar clicks still use items (they do not place a structure) in build mode.
- `place_structure` now actually grants construction XP (it computed it before
  but never applied it).
- A ghost preview marker is drawn under the cursor during build mode.
"""

import types
import unittest

import pygame
from core.state import GameState

from building.structure import StructureDef
from building.building_system import BuildingSystem
from inventory.inventory import Inventory
from skills.construction.construction import Construction
from skills.skill_manager import SkillManager


def _shelter_def() -> StructureDef:
    """A fixed common structure costing 3 wood, placeable at crafting 1 (Common 1)."""
    return StructureDef(
        structure_id="test_shelter",
        name="Test Shelter",
        structure_type="fixed",
        construction_sub_stat="common",
        hp=40,
        materials=[("wood", 3)],
        requires_structure_level=1,
        requires_skill_level=0,
        biome_compatible=["plains", "forest"],
    )


class FakeTile:
    def __init__(self, biome_id="plains"):
        self.biome = types.SimpleNamespace(id=biome_id)


class FakeWorld:
    def __init__(self, biome_id="plains"):
        self._biome = biome_id

    def get_tile(self, x, y):
        return FakeTile(self._biome)


class FakeCamera:
    """screen_to_world maps every screen point to a fixed world point."""

    def __init__(self, world_x=0.0, world_y=0.0):
        self._wx, self._wy = world_x, world_y

    def screen_to_world(self, mx, my):
        return (self._wx, self._wy)

    def world_to_screen(self, wx, wy):
        return (wx, wy)


def _player():
    notifications = []
    ps = types.SimpleNamespace(
        add_notification=lambda *a, **k: notifications.append(a)
    )
    return types.SimpleNamespace(
        world_x=0.0, world_y=0.0, action_system=ps, _notifications=notifications
    )


def _building_system(inventory=None):
    skill_manager = SkillManager()
    # Allocate Common Building Tech level 1 to satisfy requires_structure_level=1
    skill_manager.allocate_stat("crafting", "common_building_tech", 1)
    construction = Construction(skill_manager)
    bs = BuildingSystem(
        skill_manager,
        inventory if inventory is not None else Inventory(),
        construction,
        {"common": {"test_shelter": _shelter_def()}},
        game_ref=None,
    )
    return bs, skill_manager


def _router(game):
    from input.router import InputRouter

    r = InputRouter.__new__(InputRouter)
    r._game = game
    r._input_manager = types.SimpleNamespace(
        input_state=types.SimpleNamespace(
            open_inventory=False, open_skill_panel=False, open_crafting=False,
            open_building_panel=False, open_quest_panel=False,
            open_trade_panel=False, open_recruit_panel=False,
            open_diplomacy_panel=False, close_crafting=False, close_panel=False,
            hotbar_slot=0, trade_accept_pressed=False, quest_accept_pressed=False,
            faction_negotiate_pressed=False,
        ),
        handle_event=lambda event: None,
    )
    r._panel_dispatcher = types.SimpleNamespace()
    r._npc_flows = None
    return r


class TestPlaceStructureGrantsXp(unittest.TestCase):
    """The build → consume → XP → place pipeline (unit level)."""

    def test_place_consumes_materials_and_grants_xp(self):
        inv = Inventory()
        inv.add_item("wood", 3)
        bs, skill_manager = _building_system(inv)
        before = skill_manager.skills["crafting"].xp

        result = bs.place_structure(_shelter_def(), 0.0, 0.0, 0.0, 0.0, "plains")

        self.assertTrue(result.success)
        self.assertEqual(len(bs.structures), 1)
        self.assertEqual(bs.structures[0].structure_def.structure_id, "test_shelter")
        self.assertFalse(inv.has_items("wood", 3))  # materials consumed
        self.assertGreater(result.xp_gained, 0.0)
        # XP is now actually granted (it was computed but ignored before).
        self.assertEqual(
            skill_manager.skills["crafting"].xp - before, result.xp_gained
        )

    def test_too_far_does_not_place(self):
        inv = Inventory()
        inv.add_item("wood", 3)
        bs, _ = _building_system(inv)

        result = bs.place_structure(_shelter_def(), 100000.0, 0.0, 0.0, 0.0, "plains")

        self.assertFalse(result.success)
        self.assertIn("Too far", result.message)
        self.assertEqual(len(bs.structures), 0)
        self.assertTrue(inv.has_items("wood", 3))  # nothing consumed


class TestSelectEntersBuildMode(unittest.TestCase):
    """Selecting a structure closes the panel and enters build_mode."""

    def test_select_enters_build_mode_and_closes_panel(self):
        notifications = []
        panel = types.SimpleNamespace(visible=True)
        player = types.SimpleNamespace(
            world_x=0.0, world_y=0.0,
            action_system=types.SimpleNamespace(
                add_notification=lambda *a, **k: notifications.append(a)
            ),
        )
        # set_state is watched via a stub that records the resulting state.
        state_box = {"state": GameState.BUILDING_PANEL}

        game = types.SimpleNamespace(
            _building_panel=panel,
            player=player,
            build_mode=False,
            _building_pending_id=None,
            building_system=types.SimpleNamespace(
                structure_defs={"common": {"test_shelter": _shelter_def()}}
            ),
            set_state=lambda s: state_box.__setitem__("state", s),
        )

        from input.panel_dispatcher import PanelDispatcher

        PanelDispatcher(game).dispatch_click(
            GameState.BUILDING_PANEL, "building", ("select", "test_shelter")
        )

        self.assertTrue(game.build_mode)
        self.assertEqual(game._building_pending_id, "test_shelter")
        self.assertFalse(panel.visible)
        self.assertEqual(state_box["state"], GameState.PLAYING)


class TestBuildPlacementRouter(unittest.TestCase):
    """End-to-end: the router translates mouse/key input into placement."""

    def _game(self, *, camera, inventory, build_mode=True, pending="test_shelter", hud=None,
              survival=None, food_registry=None):
        bs, _ = _building_system(inventory)
        return types.SimpleNamespace(
            state=GameState.PLAYING,
            build_mode=build_mode,
            _building_pending_id=pending,
            _building_panel=None,
            building_system=bs,
            player=_player(),
            camera=camera,
            world=FakeWorld(),
            hud=hud,
            inventory=inventory,
            survival=survival,
            food_registry=food_registry,
            combat_system=None,
        )

    def _mouse(self, button, pos):
        return types.SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=button, pos=pos)

    def test_left_click_places_structure(self):
        inv = Inventory()
        inv.add_item("wood", 3)
        game = self._game(camera=FakeCamera(0.0, 0.0), inventory=inv)
        router = _router(game)

        router.handle(self._mouse(1, (0, 0)))

        self.assertEqual(len(game.building_system.structures), 1)
        self.assertFalse(inv.has_items("wood", 3))
        self.assertTrue(game.build_mode)  # stays in mode (allow chaining)
        self.assertTrue(
            any("build" in str(msg[0]).lower() for msg in game.player._notifications)
        )

    def test_right_click_cancels_build_mode(self):
        inv = Inventory()
        inv.add_item("wood", 3)
        game = self._game(camera=FakeCamera(0.0, 0.0), inventory=inv)
        router = _router(game)

        router.handle(self._mouse(3, (0, 0)))

        self.assertFalse(game.build_mode)
        self.assertIsNone(game._building_pending_id)
        self.assertEqual(len(game.building_system.structures), 0)

    def test_esc_cancels_build_mode(self):
        inv = Inventory()
        inv.add_item("wood", 3)
        game = self._game(camera=FakeCamera(0.0, 0.0), inventory=inv)
        router = _router(game)

        router.handle(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_ESCAPE))

        self.assertFalse(game.build_mode)
        self.assertIsNone(game._building_pending_id)

    def test_invalid_placement_stays_in_mode(self):
        inv = Inventory()
        inv.add_item("wood", 3)
        game = self._game(camera=FakeCamera(100000.0, 0.0), inventory=inv)
        router = _router(game)

        router.handle(self._mouse(1, (0, 0)))

        self.assertTrue(game.build_mode)  # stays in mode on failure
        self.assertEqual(len(game.building_system.structures), 0)
        self.assertTrue(inv.has_items("wood", 3))  # nothing consumed
        self.assertTrue(
            any("far" in str(msg[0]).lower() for msg in game.player._notifications)
        )

    def test_hotbar_click_uses_item_not_place(self):
        import pygame as pg

        inv = Inventory()
        inv.add_item("wood", 1)

        class StubHud:
            _hotbar_rects = [pg.Rect(0, 0, 50, 50)]

            def set_hotbar_selected(self, i):
                pass

        game = self._game(
            camera=FakeCamera(0.0, 0.0),
            inventory=inv,
            hud=StubHud(),
            survival=types.SimpleNamespace(),
            food_registry=types.SimpleNamespace(get=lambda iid: None),
        )
        router = _router(game)

        # Cursor sits on the hotbar rect → item path, not placement.
        router.handle(self._mouse(1, (25, 25)))

        self.assertEqual(len(game.building_system.structures), 0)  # did not place
        self.assertTrue(
            any("Used" in str(msg[0]) for msg in game.player._notifications)
        )

    def test_no_pending_cancels_on_click(self):
        inv = Inventory()
        inv.add_item("wood", 3)
        game = self._game(camera=FakeCamera(0.0, 0.0), inventory=inv, pending=None)
        router = _router(game)

        router.handle(self._mouse(1, (0, 0)))

        self.assertFalse(game.build_mode)


class TestBuildGhostRender(unittest.TestCase):
    """A ghost marker is drawn under the cursor during build mode."""

    def test_render_build_ghost_no_crash(self):
        from core.game import Game

        game = Game.__new__(Game)
        game.build_mode = True
        game._build_cursor = (32, 32)
        game.camera = FakeCamera(0.0, 0.0)
        game.world = FakeWorld()

        screen = types.SimpleNamespace(blit=lambda *a, **k: None)
        game._render_build_ghost(screen)  # must not raise

    def test_render_build_ghost_skips_off_map(self):
        from core.game import Game

        game = Game.__new__(Game)
        game.build_mode = True
        game._build_cursor = (-10, -10)
        game.camera = FakeCamera(0.0, 0.0)
        game.world = FakeWorld()

        screen = types.SimpleNamespace(blit=lambda *a, **k: None)
        game._render_build_ghost(screen)  # out-of-bounds tile → no-op


if __name__ == "__main__":
    unittest.main()
