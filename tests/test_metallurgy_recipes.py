"""
Tests for Phase 4: Metallurgy recipe parsing and loading.

Covers:
- R4a: New metallurgy recipes parse and load correctly
- R4b: Recipe fields are populated from JSON
"""

import pytest
import json
from pathlib import Path

from inventory.recipe import Recipe
from crafting.crafting_system import CraftingSystem


# Expected metallurgy recipe IDs from the plan
EXPECTED_RECIPE_IDS = [
    "smelt_mithril",
    "purify_ghost_iron",
    "smelt_star_metal",
    "refine_obsidian",
    "refine_void_crystal",
]


class TestMetallurgyRecipeParsing:
    """R4a: New metallurgy recipes parse and load."""

    def test_recipes_json_exists(self) -> None:
        """Metallurgy recipes.json should exist."""
        path = Path("skills/metallurgy/data/recipes.json")
        assert path.exists(), "skills/metallurgy/data/recipes.json must exist"

    def test_recipes_json_is_valid(self) -> None:
        """Metallurgy recipes.json should be valid JSON."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        assert "recipes" in data
        assert isinstance(data["recipes"], list)

    @pytest.mark.parametrize("recipe_id", EXPECTED_RECIPE_IDS)
    def test_recipe_exists_in_json(self, recipe_id: str) -> None:
        """Each expected metallurgy recipe should be present in JSON."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        ids = [r.get("recipe_id", r.get("id")) for r in data["recipes"]]
        assert recipe_id in ids, f"Missing metallurgy recipe: {recipe_id}"

    def test_recipe_from_dict_parses_mithril(self) -> None:
        """smelt_mithril recipe should parse correctly via Recipe.from_dict."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "smelt_mithril" or r.get("id") == "smelt_mithril"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "smelt_mithril"
        assert recipe.name == "Smelt Mithril"
        assert recipe.output_item == "mithril_ingot"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 80.0
        assert recipe.processing_chain == "metallurgy_mithril"
        assert recipe.tier == 3

    def test_recipe_from_dict_parses_purify_ghost_iron(self) -> None:
        """purify_ghost_iron recipe should parse correctly."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "purify_ghost_iron" or r.get("id") == "purify_ghost_iron"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "purify_ghost_iron"
        assert recipe.output_item == "refined_ghost_iron"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 70.0

    def test_recipe_from_dict_parses_smelt_star_metal(self) -> None:
        """smelt_star_metal recipe should parse correctly."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "smelt_star_metal" or r.get("id") == "smelt_star_metal"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "smelt_star_metal"
        assert recipe.output_item == "star_metal_ingot"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 100.0
        assert recipe.tier == 4

    def test_recipe_from_dict_parses_refine_obsidian(self) -> None:
        """refine_obsidian recipe should parse correctly."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "refine_obsidian" or r.get("id") == "refine_obsidian"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "refine_obsidian"
        assert recipe.output_item == "polished_obsidian"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 60.0

    def test_recipe_from_dict_parses_refine_void_crystal(self) -> None:
        """refine_void_crystal recipe should parse correctly."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipe_data = next(
            (r for r in data["recipes"] if r.get("recipe_id") == "refine_void_crystal" or r.get("id") == "refine_void_crystal"),
            None,
        )
        assert recipe_data is not None

        recipe = Recipe.from_dict(recipe_data)
        assert recipe.recipe_id == "refine_void_crystal"
        assert recipe.output_item == "polished_void_crystal"
        assert recipe.output_quantity == 1
        assert recipe.xp_reward == 70.0


class TestMetallurgyRecipeLoading:
    """R4b: All metallurgy recipes load into CraftingSystem."""

    def test_all_metallurgy_recipes_load(self) -> None:
        """All metallurgy recipes should load into CraftingSystem."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem()
        count = cs.load_recipes(recipes_data)
        assert count == len(recipes_data), (
            f"Expected {len(recipes_data)} recipes, loaded {count}"
        )

    def test_new_recipes_are_registered(self) -> None:
        """All 5 new metallurgy recipes should be in the crafting system."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem()
        cs.load_recipes(recipes_data)

        for recipe_id in EXPECTED_RECIPE_IDS:
            recipe = cs.get_recipe(recipe_id)
            assert recipe is not None, f"Recipe {recipe_id} not found in CraftingSystem"
            assert recipe.recipe_id == recipe_id

    def test_existing_recipes_still_load(self) -> None:
        """Existing metallurgy recipes should still load alongside new ones."""
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes_data = data["recipes"]

        cs = CraftingSystem()
        cs.load_recipes(recipes_data)

        # Verify legacy recipes still present
        for legacy_id in ("smelt_iron", "smelt_copper", "smelt_bronze", "smelt_steel"):
            recipe = cs.get_recipe(legacy_id)
            assert recipe is not None, f"Legacy recipe {legacy_id} missing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
