"""
Tests for data integration (PR 9).

Covers:
- Recipes have valid quest_unlock fields
- Structures have proper occupies_tile booleans
- Crafting system can lock and unlock recipes
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import load_json_list


class TestDataIntegration(unittest.TestCase):
    """Test data file integrity and recipe locking."""

    def test_recipe_has_quest_unlock_field(self) -> None:
        """Parse all recipes -> each with quest_unlock has a valid quest ID string."""
        import json
        from pathlib import Path

        # Load from skill package JSONs
        skill_dirs = [
            Path("skills/construction/data"),
            Path("skills/cooking/data"),
            Path("skills/metallurgy/data"),
            Path("skills/intelligence/data"),
        ]
        all_recipes = []
        for d in skill_dirs:
            f = d / "recipes.json"
            if f.exists():
                with open(f) as fh:
                    all_recipes.extend(json.load(fh).get("recipes", []))

        self.assertGreater(len(all_recipes), 0, "Should have recipes from skill packages")

        quest_unlock_recipes = [r for r in all_recipes if r.get("quest_unlock") is not None]
        self.assertGreater(len(quest_unlock_recipes), 0, "Some recipes should have quest_unlock")

        for recipe in quest_unlock_recipes:
            self.assertIsInstance(
                recipe["quest_unlock"], str,
                f"quest_unlock for {recipe.get('id', 'unknown')} should be a string",
            )
            self.assertTrue(len(recipe["quest_unlock"]) > 0)

    def test_structure_occupies_tile_field(self) -> None:
        """Parse all structures -> occupies_tile is boolean for each."""
        structures_data = load_json_list("structures.json", "structures")
        self.assertGreater(len(structures_data), 0, "structures.json should have structures")

        # structures_data is a dict of category -> {struct_id: def}
        for category, structures in structures_data.items():
            for struct_id, struct_def in structures.items():
                self.assertIn(
                    "occupies_tile", struct_def,
                    f"Structure {struct_id} in {category} should have occupies_tile",
                )
                self.assertIsInstance(
                    struct_def["occupies_tile"], bool,
                    f"occupies_tile for {struct_id} should be boolean",
                )

        # Verify at least some structures have occupies_tile = True
        has_occupying = False
        for category, structures in structures_data.items():
            for struct_id, struct_def in structures.items():
                if struct_def.get("occupies_tile") is True:
                    has_occupying = True
                    break
            if has_occupying:
                break
        self.assertTrue(has_occupying, "At least one structure should have occupies_tile=True")

    def test_crafting_system_can_lock_unlock_recipe(self) -> None:
        """Lock/unlock a recipe -> is_recipe_locked reflects state."""
        import json
        from crafting.crafting_system import CraftingSystem
        from crafting.recipe_registry import RecipeRegistry
        from pathlib import Path

        registry = RecipeRegistry()
        cs = CraftingSystem(recipe_registry=registry)

        # Load recipes from skill package JSONs (skip metallurgy — different schema)
        skill_dirs = [
            Path("skills/construction/data"),
            Path("skills/cooking/data"),
            Path("skills/intelligence/data"),
        ]
        all_recipes = []
        for d in skill_dirs:
            f = d / "recipes.json"
            if f.exists():
                with open(f) as fh:
                    all_recipes.extend(json.load(fh).get("recipes", []))

        count = cs.load_recipes(all_recipes)
        self.assertGreater(count, 0)

        # Find a recipe with quest_unlock (should be locked initially)
        locked_recipe_id = None
        for recipe in cs.recipes.values():
            if recipe.quest_unlock is not None:
                locked_recipe_id = recipe.recipe_id
                break

        self.assertIsNotNone(locked_recipe_id, "Should find at least one locked recipe")

        # Verify it's locked
        self.assertTrue(cs.is_recipe_locked(locked_recipe_id))

        # Verify locked recipes are excluded from available_recipes
        available = cs.get_available_recipes()
        available_ids = {r.recipe_id for r in available}
        self.assertNotIn(locked_recipe_id, available_ids)

        # Unlock it
        result = cs.unlock_recipe(locked_recipe_id)
        self.assertTrue(result)
        self.assertFalse(cs.is_recipe_locked(locked_recipe_id))

        # After unlock, should be in available
        available = cs.get_available_recipes()
        available_ids = {r.recipe_id for r in available}
        self.assertIn(locked_recipe_id, available_ids)

        # Lock it again
        cs.lock_recipe(locked_recipe_id)
        self.assertTrue(cs.is_recipe_locked(locked_recipe_id))

        # After re-lock, should be excluded again
        available = cs.get_available_recipes()
        available_ids = {r.recipe_id for r in available}
        self.assertNotIn(locked_recipe_id, available_ids)

        # Unlock again
        cs.unlock_recipe(locked_recipe_id)
        self.assertFalse(cs.is_recipe_locked(locked_recipe_id))


if __name__ == "__main__":
    unittest.main()
