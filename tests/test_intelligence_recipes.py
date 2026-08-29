"""
Tests for Phase 4: Intelligence recipe parsing and loading.

Covers:
- R4c: All 8 intelligence recipes parse and load correctly
- R4d: Recipe fields are populated from JSON
"""

import pytest
import json
from pathlib import Path

from inventory.recipe import Recipe
from crafting.crafting_system import CraftingSystem
from crafting.recipe_registry import RecipeRegistry


# Expected intelligence recipe IDs from the plan
EXPECTED_RECIPE_IDS = [
    "process_silk",
    "process_amber",
    "process_moonstone",
    "process_dragonbone",
    "concentrate_void_essence",
    "weave_phoenix_feather",
    "inscribe_ancient_rune",
    "attune_celestial_crystal",
]


class TestIntelligenceRecipeParsing:
    """R4c: All 8 intelligence recipes parse and load."""

    def test_recipes_json_exists(self) -> None:
        """Intelligence recipes.json should exist."""
        path = Path("skills/intelligence/data/recipes.json")
        assert path.exists(), "skills/intelligence/data/recipes.json must exist"

    def test_recipes_json_is_valid(self) -> None:
        """Intelligence recipes.json should be valid JSON."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        assert "recipes" in data
        assert isinstance(data["recipes"], list)
        assert len(data["recipes"]) == 8, f"Expected 8 recipes, got {len(data['recipes'])}"

    @pytest.mark.parametrize("recipe_id", EXPECTED_RECIPE_IDS)
    def test_recipe_exists_in_json(self, recipe_id: str) -> None:
        """Each expected intelligence recipe should be present in JSON."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        ids = [r.get("recipe_id", r.get("id")) for r in data["recipes"]]
        assert recipe_id in ids, f"Missing intelligence recipe: {recipe_id}"

    def test_process_silk_parses(self) -> None:
        """process_silk should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "process_silk"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "process_silk"
        assert recipe.name == "Process Silk"
        assert recipe.output_item == "silk_thread"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 40.0
        assert recipe.processing_chain == "intelligence_silk"
        assert recipe.tier == 3
        assert recipe.skill_affects_yield == "intelligence"

    def test_process_amber_parses(self) -> None:
        """process_amber should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "process_amber"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "process_amber"
        assert recipe.output_item == "polished_amber"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 50.0
        assert recipe.processing_chain == "intelligence_amber"
        assert recipe.skill_affects_yield == "intelligence"

    def test_process_moonstone_parses(self) -> None:
        """process_moonstone should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "process_moonstone"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "process_moonstone"
        assert recipe.output_item == "moonstone_essence"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 55.0
        assert recipe.processing_chain == "intelligence_moonstone"
        assert recipe.skill_affects_yield == "intelligence"

    def test_process_dragonbone_parses(self) -> None:
        """process_dragonbone should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "process_dragonbone"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "process_dragonbone"
        assert recipe.output_item == "dragonbone_shard"
        assert recipe.output_quantity == 2
        assert recipe.xp_reward == 60.0
        assert recipe.processing_chain == "intelligence_dragonbone"
        assert recipe.skill_affects_yield == "intelligence"

    def test_concentrate_void_essence_parses(self) -> None:
        """concentrate_void_essence should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "concentrate_void_essence"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "concentrate_void_essence"
        assert recipe.output_item == "void_essence_concentrate"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 80.0
        assert recipe.processing_chain == "intelligence_void"
        assert recipe.tier == 4
        assert recipe.skill_affects_yield == "intelligence"

    def test_weave_phoenix_feather_parses(self) -> None:
        """weave_phoenix_feather should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "weave_phoenix_feather"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "weave_phoenix_feather"
        assert recipe.output_item == "phoenix_cloth"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 90.0
        assert recipe.processing_chain == "intelligence_phoenix"
        assert recipe.tier == 4
        assert recipe.skill_affects_yield == "intelligence"

    def test_inscribe_ancient_rune_parses(self) -> None:
        """inscribe_ancient_rune should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "inscribe_ancient_rune"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "inscribe_ancient_rune"
        assert recipe.output_item == "rune_stone"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 100.0
        assert recipe.processing_chain == "intelligence_rune"
        assert recipe.tier == 4
        assert recipe.skill_affects_yield == "intelligence"

    def test_attune_celestial_crystal_parses(self) -> None:
        """attune_celestial_crystal should parse correctly."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "attune_celestial_crystal"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "attune_celestial_crystal"
        assert recipe.output_item == "attuned_celestial_crystal"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 110.0
        assert recipe.processing_chain == "intelligence_celestial"
        assert recipe.tier == 4
        assert recipe.skill_affects_yield == "intelligence"


class TestIntelligenceRecipeLoading:
    """R4d: All intelligence recipes load into CraftingSystem."""

    def test_all_intelligence_recipes_load(self) -> None:
        """All 8 intelligence recipes should load into CraftingSystem."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem(recipe_registry=RecipeRegistry())
        count = cs.load_recipes(recipes_data)
        assert count == 8, f"Expected 8 recipes, loaded {count}"

    def test_new_recipes_are_registered(self) -> None:
        """All 8 new intelligence recipes should be in the crafting system."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem(recipe_registry=RecipeRegistry())
        cs.load_recipes(recipes_data)

        for recipe_id in EXPECTED_RECIPE_IDS:
            recipe = cs.get_recipe(recipe_id)
            assert recipe is not None, f"Recipe {recipe_id} not found in CraftingSystem"
            assert recipe.recipe_id == recipe_id
            assert recipe.skill_affects_yield == "intelligence"

    def test_recipes_have_correct_chains(self) -> None:
        """Each intelligence recipe should have the expected processing_chain."""
        path = Path("skills/intelligence/data/recipes.json")
        with open(path) as f:
            data = json.load(f)

        chain_map = {
            "process_silk": "intelligence_silk",
            "process_amber": "intelligence_amber",
            "process_moonstone": "intelligence_moonstone",
            "process_dragonbone": "intelligence_dragonbone",
            "concentrate_void_essence": "intelligence_void",
            "weave_phoenix_feather": "intelligence_phoenix",
            "inscribe_ancient_rune": "intelligence_rune",
            "attune_celestial_crystal": "intelligence_celestial",
        }

        cs = CraftingSystem(recipe_registry=RecipeRegistry())
        cs.load_recipes(data["recipes"])

        for recipe_id, expected_chain in chain_map.items():
            recipe = cs.get_recipe(recipe_id)
            assert recipe is not None
            assert recipe.processing_chain == expected_chain, (
                f"{recipe_id}: expected chain {expected_chain}, got {recipe.processing_chain}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
