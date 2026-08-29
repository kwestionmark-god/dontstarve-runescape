"""
test_craft_inventory_capacity.py — silent loot/craft drop on full inventory.

Fixes for the "silent drop" data-loss bugs:
- CraftingSystem.craft / .cook used to ignore Inventory.add_item's return, so
  a full inventory silently consumed materials and produced nothing (craft) or
  silently dropped the crafted item (cook). They now short-circuit with an
  "inventory full" message BEFORE consuming.
- CombatSystem._monster_died ignored add_item's return on loot drops; it now
  notifies when loot is lost.

This test is discriminating: it asserts that materials are *not* consumed when
the output cannot fit (the old code consumed them), and that the "full"
message surfaces instead of silent loss.
"""

import random
from types import SimpleNamespace

import pytest

from crafting.crafting_system import CraftingSystem, _chain_to_skill
from inventory.inventory import Inventory
from inventory.recipe import Recipe
from skills.skill_manager import SkillManager


@pytest.fixture
def system():
    from crafting.recipe_registry import RecipeRegistry
    return CraftingSystem(recipe_registry=RecipeRegistry())


def _recipe(rid, chain, inputs, out, qty=1, xp=4.0):
    return Recipe.from_dict({
        "recipe_id": rid,
        "name": rid,
        "input_items": inputs,
        "output_item": out,
        "output_quantity": qty,
        "xp_reward": xp,
        "processing_chain": chain,
        "tier": 1,
        "requires_campfire": chain == "cooking_chain",
    })


def _slot(item_id, quantity):
    return SimpleNamespace(item_id=item_id, quantity=quantity,
                           spoilage_remaining=None, is_equipped=False)


def _full_with_inputs(input_id, input_qty, fill_id="stone"):
    """
    Inventory that holds `input_qty` of input_id (so validation passes) but has
    NO empty slots, so the crafted output cannot fit.
    """
    inv = Inventory()
    inv.set_stack_size(fill_id, 28)
    inv.slots[0] = _slot(input_id, input_qty)
    for i in range(1, inv.max_slots):
        inv.slots[i] = _slot(fill_id, 28)
    return inv


def _empty_with_input(input_id, input_qty):
    """Inventory with the input present and room to spare for output."""
    inv = Inventory()
    inv.slots[0] = _slot(input_id, input_qty)
    return inv


def test_chain_to_skill_mapping():
    assert _chain_to_skill("wood_chain") == "woodcutting"
    assert _chain_to_skill("foraging_chain") == "crafting"
    assert _chain_to_skill(None) == "crafting"


def test_can_add_predicts_add_item():
    inv = Inventory()
    assert inv.can_add("wood", 5) is True
    assert inv.can_add("wood", 0) is True

    full = _full_with_inputs("stone", 1)  # 20 slots all occupied
    assert full.can_add("wood", 1) is False
    # add_item agrees: a 20-slot full grid returns False
    assert full.add_item("wood", 1) is False

    # A slot emptied by remove_item (non-None, item_id None) is reusable:
    # can_add must agree with add_item that the item fits there.
    inv2 = Inventory()
    inv2.set_stack_size("wood", 28)
    inv2.slots[0] = _slot("stone", 28)
    inv2.slots[1] = _slot("wood", 0)  # freed slot (item_id None would be empty)
    inv2.slots[1].item_id = None
    assert inv2.can_add("wood", 5) is True
    assert inv2.add_item("wood", 5) is True
    assert inv2.get_item_quantity("wood") == 5


def test_craft_full_inventory_does_not_consume(system):
    system._registry.recipes = {"grass_rope": _recipe("grass_rope", "foraging_chain",
                                              [["fibers", 3]], "grass_rope", 1)}
    inv = _full_with_inputs("fibers", 3)
    skill = SkillManager()

    result = system.craft("grass_rope", inv, skill_manager=skill)

    assert result.success is False
    assert "full" in result.message.lower()
    # CRITICAL: materials must NOT be consumed when the output cannot fit
    # (the pre-fix code removed the materials and produced nothing).
    assert inv.get_item_quantity("fibers") == 3
    assert inv.get_item_quantity("grass_rope") == 0
    # No woodcutting XP should be granted either (regression guard).
    assert skill.skills["woodcutting"].xp == 0


def test_craft_exact_fit_success_and_woodcutting_xp(system):
    system._registry.recipes = {"sticks": _recipe("sticks", "wood_chain",
                                          [["oak_logs", 1]], "stick", 3, 3.0)}
    inv = _empty_with_input("oak_logs", 1)
    inv.set_stack_size("stick", 28)
    skill = SkillManager()

    result = system.craft("sticks", inv, skill_manager=skill)

    assert result.success is True
    assert inv.get_item_quantity("stick") == 3
    # wood_chain routes to woodcutting (a real, registered skill)
    assert skill.skills["woodcutting"].xp == 3.0


def test_craft_foraging_grants_crafting_not_woodcutting(system):
    system._registry.recipes = {"paper": _recipe("paper", "foraging_chain",
                                        [["reed", 2]], "paper", 1)}
    inv = _empty_with_input("reed", 2)
    inv.set_stack_size("paper", 28)
    skill = SkillManager()

    result = system.craft("paper", inv, skill_manager=skill)

    assert result.success is True
    assert inv.get_item_quantity("paper") == 1
    assert skill.skills["crafting"].xp == 4.0
    assert skill.skills["woodcutting"].xp == 0.0


def test_cook_full_inventory_does_not_consume(system):
    system._registry.recipes = {"cook_bole": _recipe("cook_bole", "cooking_chain",
                                            [["trout", 1]], "cooked_trout", 1, xp=10)}
    inv = _full_with_inputs("trout", 1)
    skill = SkillManager()

    result = system.cook("cook_bole", inv, skill_manager=skill, has_campfire=True)

    assert result.success is False
    assert "full" in result.message.lower()
    # Raw ingredients preserved (not consumed) when there is no room.
    assert inv.get_item_quantity("trout") == 1


def test_combat_loot_lost_notifies():
    random.seed(1234)  # deterministic loot rolls
    inv = _full_with_inputs("stone", 1)
    player = SimpleNamespace(skill_manager=SkillManager(), inventory=inv,
                             action_system=None)
    from combat.combat_system import CombatSystem
    combat = CombatSystem(player=player)

    notifications = []
    player.action_system = SimpleNamespace(
        add_notification=lambda msg, color=(255, 255, 255): notifications.append(msg)
    )

    monster = SimpleNamespace(xp_reward=5, monster_id="goblin",
                              loot_table=[{"item_id": "bone", "chance": 1.0},
                                          {"item_id": "coins", "chance": 1.0}],
                              is_alive=lambda: True)
    combat.monsters.append(monster)
    combat.selected_target = monster

    combat._monster_died(monster)

    # Every loot entry would not fit into a 20-slot full grid -> loss reported.
    assert any("loot" in n.lower() for n in notifications)
    # XP still granted regardless of loot outcome.
    assert player.skill_manager.skills["combat"].xp == 5.0
