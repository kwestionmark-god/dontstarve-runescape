"""
Skill level-gate tests: resource harvesting and recipe crafting must respect
required_level / required_skill requirements.

Covers:
- ActionSystem.start_action refuses nodes above the player's skill level.
- CraftingSystem.craft / cook refuse recipes above the player's skill level.
- ResourceNode.from_dict reads required_level from resources.json.
- Recipe.from_dict folds skill_requirements dicts into required_skill/level.
"""

import json

import pytest

from actions import ActionSystem
from actions.types import ActionType
from crafting.recipe_registry import RecipeRegistry
from crafting.crafting_system import CraftingSystem
from inventory.inventory import Inventory
from inventory.recipe import Recipe
from skills.skill_manager import SkillManager
from world.resource_node import ResourceNode


def _make_node(**overrides) -> ResourceNode:
    data = {
        "id": "elder_wood",
        "name": "Elder Wood",
        "tier": 4,
        "rarity": "rare",
        "category": "wood",
        "base_density": 0.01,
        "yield_item": "elder_wood",
        "yield_quantity": 1,
        "xp_reward": 95.0,
        "depletion_count": 2,
        "regrow_time": 2000.0,
        "sprite_key": "trees/elder_wood",
        "requires_tool": "axe",
        "required_level": 45,
    }
    data.update(overrides)
    return ResourceNode.from_dict(data, biome_id="forest")


class TestResourceLevelGate:
    def test_from_dict_defaults_to_one(self):
        data = {
            "id": "oak_tree", "tier": 1, "yield_item": "oak_logs",
            "xp_reward": 25.0, "depletion_count": 4, "regrow_time": 180.0,
            "sprite_key": "trees/oak", "requires_tool": "axe",
        }
        assert ResourceNode.from_dict(data, "forest").required_level == 1

    def test_from_dict_reads_required_level(self):
        assert _make_node().required_level == 45

    def test_start_action_blocks_below_level(self):
        inv = Inventory()
        inv.add_item("axe", 1)
        sm = SkillManager()
        asys = ActionSystem()
        err = asys.start_action(
            ActionType.WOODCUTTING, _make_node(), sm, inv,
        )
        assert err is not None
        assert "Woodcutting level 45" in err

    def test_start_action_allows_at_level(self):
        inv = Inventory()
        inv.add_item("axe", 1)
        sm = SkillManager()
        sm.skills["woodcutting"].level = 45
        asys = ActionSystem()
        err = asys.start_action(
            ActionType.WOODCUTTING, _make_node(), sm, inv,
        )
        assert err is None

    def test_foraging_gate_uses_foraging_skill(self):
        inv = Inventory()
        sm = SkillManager()
        node = _make_node(id="silk_nest", name="Silk Nest",
                          requires_tool=None, required_level=25)
        asys = ActionSystem()
        err = asys.start_action(ActionType.FORAGING, node, sm, inv)
        assert err is not None
        assert "Foraging level 25" in err


class TestRecipeLevelGate:
    def _setup(self, required_skill="crafting", required_level=20,
               chain="test_chain", cooking=False):
        reg = RecipeRegistry()
        entry = {
            "recipe_id": "gated_recipe",
            "name": "Gated Recipe",
            "input_items": [["stick", 1]],
            "output_item": "ash",
            "output_quantity": 1,
            "xp_reward": 5,
            "processing_chain": chain,
            "tier": 1,
            "requires_campfire": False,
            "required_skill": required_skill,
            "required_level": required_level,
        }
        reg.recipes["gated_recipe"] = Recipe.from_dict(entry)
        cs = CraftingSystem(reg)
        inv = Inventory()
        inv.add_item("stick", 5)
        sm = SkillManager()
        return cs, inv, sm

    def test_craft_blocked_below_level(self):
        cs, inv, sm = self._setup()
        result = cs.craft("gated_recipe", inv, sm)
        assert not result.success
        assert "Crafting level 20" in result.message

    def test_craft_allowed_at_level(self):
        cs, inv, sm = self._setup()
        sm.skills["crafting"].level = 20
        result = cs.craft("gated_recipe", inv, sm)
        assert result.success

    def test_craft_allowed_without_skill_manager(self):
        cs, inv, _ = self._setup()
        result = cs.craft("gated_recipe", inv, None)
        assert result.success

    def test_cook_blocked_below_level(self):
        cs, inv, sm = self._setup(required_skill="cooking", required_level=12,
                                  chain="food_chain")
        result = cs.cook("gated_recipe", inv, sm)
        assert not result.success
        assert "Cooking level 12" in result.message

    def test_skill_requirements_dict_folds_into_gate(self):
        entry = {
            "recipe_id": "r", "name": "R",
            "input_items": [["stick", 1]],
            "output_item": "ash", "output_quantity": 1,
            "xp_reward": 5, "processing_chain": "c", "tier": 1,
            "requires_campfire": False,
            "skill_requirements": {"crafting": 40, "intelligence": 45},
        }
        recipe = Recipe.from_dict(entry)
        assert recipe.required_skill == "intelligence"
        assert recipe.required_level == 45

    def test_no_gate_by_default(self):
        entry = {
            "recipe_id": "r", "name": "R",
            "input_items": [["stick", 1]],
            "output_item": "ash", "output_quantity": 1,
            "xp_reward": 5, "processing_chain": "c", "tier": 1,
            "requires_campfire": False,
        }
        recipe = Recipe.from_dict(entry)
        assert recipe.required_skill is None
        assert recipe.required_level == 1


class TestDataLadders:
    """Authored data must carry the level ladder end to end."""

    def test_resources_json_has_required_levels(self):
        with open("data/resources.json") as f:
            resources = json.load(f)["resources"]
        by_id = {r["id"]: r for r in resources}
        assert by_id["elder_wood"]["required_level"] == 45
        assert by_id["celestial_crystal"]["required_level"] == 85
        assert by_id["oak_tree"]["required_level"] == 1
        # Every tool-gated node must declare a level
        for r in resources:
            if r.get("requires_tool"):
                assert "required_level" in r, r["id"]

    def test_all_recipe_item_refs_resolve(self):
        reg = RecipeRegistry()
        reg.load_all()
        with open("data/items.json") as f:
            item_ids = {i["id"] for i in json.load(f)["items"]}
        for recipe in reg.recipes.values():
            assert recipe.output_item in item_ids, recipe.recipe_id
            for item_id, _ in recipe.input_items:
                assert item_id in item_ids, recipe.recipe_id
