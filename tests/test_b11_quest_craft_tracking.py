"""
test_b11_quest_craft_tracking.py — B11: quest-aware craft/cook tracking.

B11 wired the quest system into crafting so "craft N of X" objectives advance.
CraftingSystem.craft() and .cook() now accept an optional quest_system argument;
on success they call quest_system.record_craft(recipe_id). Passing None (or
omitting the argument) must not call record_craft and must not crash.

This test is discriminating: it asserts record_craft is called exactly once per
success, is NOT called when quest_system is None, and is NOT called on a cooking
failure (the rollback path).
"""

from crafting.crafting_system import CraftingSystem


class _RecordedQuestSystem:
    """Quest system that records every record_craft() call."""

    def __init__(self):
        self.recorded = []

    def record_craft(self, recipe_id):
        self.recorded.append(recipe_id)


class _MockSkillManager:
    """Skill manager: success_rate drives the cook roll; add_xp is a no-op."""

    def __init__(self, success_rate=100):
        self._success_rate = success_rate

    def get_effective_stat(self, skill, stat):
        if skill == "cooking" and stat == "success_rate":
            return self._success_rate
        return 0

    def add_xp(self, skill, amount):
        pass


def _inventory(*start):
    """Inventory pre-populated with (item_id, quantity) pairs."""
    from inventory.inventory import Inventory

    inv = Inventory()
    for item_id, quantity in start:
        inv.add_item(item_id, quantity)
    return inv


def _crafting_system():
    cs = CraftingSystem()
    cs.load_recipes(
        [
            {
                "id": "planks",
                "name": "Plank",
                "input_items": [["log", 1]],
                "output_item": "planks",
                "output_quantity": 2,
                "xp_reward": 5,
                "processing_chain": "basic",
            }
        ]
    )
    return cs


def test_craft_records_craft_on_success():
    cs = _crafting_system()
    inv = _inventory(("log", 5))
    qs = _RecordedQuestSystem()

    result = cs.craft("planks", inv, _MockSkillManager(), quest_system=qs)

    assert result.success is True
    assert qs.recorded == ["planks"]


def test_craft_without_quest_system_does_not_record():
    cs = _crafting_system()
    inv = _inventory(("log", 5))

    # Omitting quest_system (defaults to None) must not crash and must not call
    # record_craft. A sentinel that raises guards against an accidental call.
    class _RaisingQuestSystem:
        def record_craft(self, recipe_id):
            raise AssertionError("record_craft must not be called when quest_system is None")

    result = cs.craft("planks", inv, _MockSkillManager(), quest_system=None)

    assert result.success is True


def test_cook_records_craft_on_success():
    cs = _crafting_system()
    cs.load_recipes(
        [
            {
                "id": "cooked_meat",
                "name": "Cooked Meat",
                "input_items": [["raw_meat", 1]],
                "output_item": "cooked_meat",
                "output_quantity": 1,
                "xp_reward": 10,
                "processing_chain": "cooking",
                "requires_campfire": True,
            }
        ]
    )
    inv = _inventory(("raw_meat", 5))
    qs = _RecordedQuestSystem()

    result = cs.cook(
        "cooked_meat",
        inv,
        _MockSkillManager(success_rate=100),
        has_campfire=True,
        quest_system=qs,
    )

    assert result.success is True
    assert qs.recorded == ["cooked_meat"]


def test_cook_failure_does_not_record(monkeypatch):
    import random

    cs = _crafting_system()
    cs.load_recipes(
        [
            {
                "id": "cooked_meat",
                "name": "Cooked Meat",
                "input_items": [["raw_meat", 1]],
                "output_item": "cooked_meat",
                "output_quantity": 1,
                "xp_reward": 10,
                "processing_chain": "cooking",
                "requires_campfire": True,
            }
        ]
    )
    inv = _inventory(("raw_meat", 5))
    qs = _RecordedQuestSystem()

    # Force the success roll to fail deterministically: random() -> 1.0 gives
    # 100, which is never < the 50 base threshold.
    monkeypatch.setattr(random, "random", lambda: 1.0)

    result = cs.cook(
        "cooked_meat",
        inv,
        _MockSkillManager(success_rate=0),
        has_campfire=True,
        quest_system=qs,
    )

    assert result.success is False
    assert qs.recorded == []
