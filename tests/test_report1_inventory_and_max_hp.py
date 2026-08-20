"""
Report 1 (core/input) verification tests.

Covers the two confirmed fixes:
- Fix 1 (CRITICAL): the complete food-eat/equip `_handle_inventory_use` is now
  the sole definition in input/panel_dispatcher.py (the generic `"Used {item_id}"`
  stub that shadowed it is removed).
- Fix 2 (MEDIUM): structure `max_hp` is persisted and restored distinctly from
  `hp` in core/save_system.py, and old saves without `max_hp` still round-trip
  (backward compatibility).
"""

import pytest
from unittest import mock

from core.save_system import SaveSystem
from input.panel_dispatcher import PanelDispatcher
import data as data_mod
from core.state import GameState


# --------------------------------------------------------------------------- #
# Fix 2 — Structure max_hp persistence / restore round trip
# --------------------------------------------------------------------------- #
def test_structure_max_hp_roundtrip(tmp_path):
    class FakeDef:
        structure_id = "campfire"
        hp = 100

    class FakeStruct:
        def __init__(self, sid, hp, max_hp):
            self.structure_def = FakeDef()
            self.world_x = 0.0
            self.world_y = 0.0
            self.hp = hp
            self.max_hp = max_hp
            self.is_active = True

    class FakeBS:
        def __init__(self):
            # dict-of-dicts: category -> {structure_id: StructureDef}
            self.structure_defs = {"camp": {"campfire": FakeDef()}}
            self.structures = []

        def get_all_structures(self):
            return self.structures

    class G:
        player = None
        survival = None
        inventory = None
        skill_manager = None
        firemaking = None
        faction_system = None
        quest_system = None
        npc_system = None
        recruitment_system = None
        season_system = None
        weather_system = None
        _save_slots = []
        _flavor_text = ""
        state = None
        seed = 42
        death_count = 0

        def __init__(self):
            self.building_system = FakeBS()

    g = G()
    g.building_system.structures.append(FakeStruct("campfire", 60, 100))

    ss = SaveSystem(save_dir=str(tmp_path))
    assert ss.save(g, slot=0) is True

    loaded = ss.load(0)
    # Round trip preserves the true max_hp and the (independently stored) hp.
    assert loaded["structures"][0]["max_hp"] == 100
    assert loaded["structures"][0]["hp"] == 60

    # Backward-compat: an old save lacking `max_hp` restores to full struct HP.
    loaded["structures"][0].pop("max_hp", None)
    g2 = G()
    g2.building_system.structures = []
    ss.load_into_game(loaded, g2)
    assert g2.building_system.structures[0].max_hp == 100
    assert g2.building_system.structures[0].hp == 60


# --------------------------------------------------------------------------- #
# Fix 1 — Complete inventory-use handler is live (food + equippable branches)
# --------------------------------------------------------------------------- #
class _ActionSystem:
    def __init__(self):
        self.notifications = []

    def add_notification(self, message, color=None):
        self.notifications.append(message)


class _Player:
    def __init__(self):
        self.action_system = _ActionSystem()


class _Inventory:
    def __init__(self, quantities=None):
        self._qty = dict(quantities or {})
        self.removed = []
        self.equipped = []

    def get_item_quantity(self, item_id):
        return self._qty.get(item_id, 0)

    def remove_item(self, item_id, count):
        self._qty[item_id] = self._qty.get(item_id, 0) - count
        self.removed.append((item_id, count))
        return True

    def equip_item(self, item_id):
        self.equipped.append(item_id)
        return True


class _Food:
    pass


class _FoodRegistry:
    def __init__(self, foods=None):
        self._foods = dict(foods or {})

    def get(self, item_id):
        return self._foods.get(item_id)


class _Survival:
    def __init__(self):
        self.eat_calls = []

    def eat(self, food):
        self.eat_calls.append(food)
        return "Ate food"


def _make_game(foods=None, quantities=None, items_data=None):
    game = mock.MagicMock()
    game.player = _Player()
    game.inventory = _Inventory(quantities)
    game.food_registry = _FoodRegistry(foods)
    game.survival = _Survival()
    if items_data is not None:
        game._items_data = items_data
    return game


def _patch_items(monkeypatch, items_data):
    def fake_load_json_list(filename, key=""):
        return items_data
    monkeypatch.setattr(data_mod, "load_json_list", fake_load_json_list)


def test_dispatch_use_eats_food(monkeypatch):
    food = _Food()
    game = _make_game(foods={"apple": food}, quantities={"apple": 3})
    dispatcher = PanelDispatcher(game)

    dispatcher.dispatch(GameState.INVENTORY_OPEN, ("use", "apple"))

    assert len(game.survival.eat_calls) == 1
    assert game.survival.eat_calls[0] is food
    assert ("apple", 1) in game.inventory.removed
    # The old generic stub message must no longer be produced.
    assert all(msg != "Used apple." for msg in game.player.action_system.notifications)


def test_dispatch_use_equips_equippable(monkeypatch):
    monkeypatch.setattr(data_mod, "load_json_list", lambda *a, **k: [])
    items_data = [{"id": "wooden_axe", "name": "Wooden Axe", "is_equippable": True}]
    _patch_items(monkeypatch, items_data)
    game = _make_game(foods={}, quantities={"wooden_axe": 1})
    dispatcher = PanelDispatcher(game)

    dispatcher.dispatch(GameState.INVENTORY_OPEN, ("use", "wooden_axe"))

    assert game.inventory.equipped == ["wooden_axe"]
    assert game.survival.eat_calls == []


def test_dispatch_use_no_food_generic(monkeypatch):
    # Non-food item (registry yields None): should hit generic-use notification
    # (only valid when not equippable either), not survival.eat / equip_item.
    monkeypatch.setattr(data_mod, "load_json_list", lambda *a, **k: [])
    game = _make_game(foods={}, quantities={"stick": 1})
    dispatcher = PanelDispatcher(game)

    dispatcher.dispatch(GameState.INVENTORY_OPEN, ("use", "stick"))

    assert game.survival.eat_calls == []
    assert game.inventory.equipped == []
    assert game.player.action_system.notifications == ["Used stick."]
