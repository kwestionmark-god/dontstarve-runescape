"""
Tests for Phase 4: Construction recipe parsing and loading.

Covers:
- R4e: Elder wood construction recipes parse and load correctly
"""

import pytest
import json
from pathlib import Path

from inventory.recipe import Recipe
from crafting.crafting_system import CraftingSystem


EXPECTED_RECIPE_IDS = [
    "shape_elder_wood",
    "elder_wood_staff",
]


class TestConstructionRecipeParsing:
    """R4e: Elder wood construction recipes parse and load."""

    def test_recipes_json_exists(self) -> None:
        """Construction recipes.json should exist."""
        path = Path("skills/construction/data/recipes.json")
        assert path.exists(), "skills/construction/data/recipes.json must exist"

    def test_recipes_json_is_valid(self) -> None:
        """Construction recipes.json should be valid JSON."""
        path = Path("skills/construction/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        assert "recipes" in data
        assert isinstance(data["recipes"], list)

    @pytest.mark.parametrize("recipe_id", EXPECTED_RECIPE_IDS)
    def test_recipe_exists_in_json(self, recipe_id: str) -> None:
        """Each expected construction recipe should be present in JSON."""
        path = Path("skills/construction/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        ids = [r.get("recipe_id", r.get("id")) for r in data["recipes"]]
        assert recipe_id in ids, f"Missing construction recipe: {recipe_id}"

    def test_shape_elder_wood_parses(self) -> None:
        """shape_elder_wood should parse correctly."""
        path = Path("skills/construction/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "shape_elder_wood" or r.get("id") == "shape_elder_wood"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "shape_elder_wood"
        assert recipe.name == "Shape Elder Wood"
        assert recipe.output_item == "elder_wood_planks"
        assert recipe.output_quantity == 2
        assert recipe.xp_reward == 50.0
        assert recipe.processing_chain == "legendary_wood_chain"
        assert recipe.tier == 4
        assert recipe.skill_affects_yield == "crafting"
        assert recipe.requires_structure == "crafting_station"

    def test_elder_wood_staff_parses(self) -> None:
        """elder_wood_staff should parse correctly."""
        path = Path("skills/construction/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "elder_wood_staff" or r.get("id") == "elder_wood_staff"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "elder_wood_staff"
        assert recipe.name == "Elder Wood Staff"
        assert recipe.output_item == "elder_wood_staff"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 150.0
        assert recipe.processing_chain == "legendary_wood_chain"
        assert recipe.tier == 4
        assert recipe.skill_affects_yield == "intelligence"
        assert recipe.requires_structure == "arcane_table"

    def test_existing_recipes_still_parse(self) -> None:
        """Existing construction recipes (planks, etc.) should still parse."""
        path = Path("skills/construction/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem()
        count = cs.load_recipes(recipes_data)
        assert count > 0, "Should have at least one recipe"

        # Verify legacy recipes still present
        for legacy_id in ("planks", "chert", "craft_stick", "campfire"):
            recipe = cs.get_recipe(legacy_id)
            assert recipe is not None, f"Legacy recipe {legacy_id} missing"


class TestConstructionRecipeLoading:
    """Construction recipes load into CraftingSystem."""

    def test_all_construction_recipes_load(self) -> None:
        """All construction recipes should load into CraftingSystem."""
        path = Path("skills/construction/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem()
        count = cs.load_recipes(recipes_data)
        assert count == len(recipes_data), (
            f"Expected {len(recipes_data)} recipes, loaded {count}"
        )

    def test_elder_wood_recipes_are_registered(self) -> None:
        """Both elder wood recipes should be in the crafting system."""
        path = Path("skills/construction/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem()
        cs.load_recipes(recipes_data)

        for recipe_id in EXPECTED_RECIPE_IDS:
            recipe = cs.get_recipe(recipe_id)
            assert recipe is not None, f"Recipe {recipe_id} not found in CraftingSystem"
            assert recipe.recipe_id == recipe_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
