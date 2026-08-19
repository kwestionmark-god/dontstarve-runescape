"""
recipe_registry.py — Unified recipe registry.

Loads recipes from all JSON sources into a single lookup table.
Provides filtering by chain, tier, skill, and quest unlock status.

Sources:
  - data/recipes.json          (general crafting — loaded by CraftingSystem)
  - skills/metallurgy/data/recipes.json  (smelting — loaded by MetallurgySkill)
  - skills/cooking/data/recipes.json     (cooking — loaded by CookingSkill)
  - skills/intelligence/data/recipes.json (enchanting/processing — loaded here)
  - skills/construction/data/recipes.json (construction — loaded by CraftingSystem)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from inventory.recipe import Recipe

if TYPE_CHECKING:
    pass


_SKILL_DATA_DIRS: list[Path] = [
    Path("skills/metallurgy/data"),
    Path("skills/cooking/data"),
    Path("skills/intelligence/data"),
    Path("skills/construction/data"),
]


class RecipeRegistry:
    """
    Unified registry of all crafting recipes.

    Fields:
        recipes: dict of recipe_id → Recipe
        completed_recipes: set of recipe_ids crafted at least once
        locked_recipes: set of recipe_ids locked behind quests
        unlocked_gear: set of gear_ids unlocked by quests
    """

    __slots__ = ("recipes", "completed_recipes", "locked_recipes", "unlocked_gear")

    def __init__(self) -> None:
        self.recipes: dict[str, Recipe] = {}
        self.completed_recipes: set[str] = set()
        self.locked_recipes: set[str] = set()
        self.unlocked_gear: set[str] = set()

    def load_all(self) -> int:
        """
        Load recipes from all JSON sources.

        Returns:
            Total number of recipes loaded.
        """
        count = 0
        count += self._load_from_dir(Path("data"), "recipes.json")
        for data_dir in _SKILL_DATA_DIRS:
            count += self._load_from_dir(data_dir, "recipes.json")
        return count

    def _load_from_dir(self, directory: Path, filename: str) -> int:
        """
        Load recipes from a single JSON file.

        Args:
            directory: Directory containing the JSON file.
            filename: JSON filename.

        Returns:
            Number of recipes loaded from this file.
        """
        path = directory / filename
        if not path.exists():
            return 0
        try:
            import json
            data = json.loads(path.read_text())
            loaded = 0
            for entry in data.get("recipes", []):
                recipe = Recipe.from_dict(entry)
                self.recipes[recipe.recipe_id] = recipe
                if recipe.quest_unlock is not None:
                    self.locked_recipes.add(recipe.recipe_id)
                loaded += 1
            return loaded
        except Exception:
            return 0

    # ── Recipe Queries ─────────────────────────────────────────────

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """Look up a recipe by ID."""
        return self.recipes.get(recipe_id)

    def get_available_recipes(
        self,
    ) -> List[Recipe]:
        """
        Return all recipes not locked behind quests.

        Returns:
            List of available Recipe instances.
        """
        return [
            r for r in self.recipes.values()
            if r.quest_unlock is None or r.recipe_id not in self.locked_recipes
        ]

    def get_recipes_for_chain(self, chain: str) -> List[Recipe]:
        """
        Return recipes belonging to a processing chain.

        Args:
            chain: Chain identifier (e.g. "wood_chain", "metallurgy_iron").

        Returns:
            List of recipes in the chain.
        """
        return [r for r in self.recipes.values() if r.processing_chain == chain]

    def get_recipes_for_tier(self, tier: int) -> List[Recipe]:
        """
        Return recipes of a specific tier.

        Args:
            tier: Tier number (1–4).

        Returns:
            List of recipes matching the tier.
        """
        return [r for r in self.recipes.values() if r.tier == tier]

    def get_recipes_for_skill(self, skill: str) -> List[Recipe]:
        """
        Return recipes affected by a given skill.

        Args:
            skill: Skill name (e.g. "cooking", "intelligence").

        Returns:
            List of recipes where skill_affects_yield matches.
        """
        return [
            r for r in self.recipes.values()
            if r.skill_affects_yield == skill
        ]

    # ── Lock / Unlock ───────────────────────────────────────────────

    def unlock_recipe(self, recipe_id: str) -> bool:
        """
        Unlock a recipe for crafting. Returns True if successful.

        Args:
            recipe_id: The recipe to unlock.

        Returns:
            True if the recipe was (or already was) unlocked.
        """
        if recipe_id not in self.locked_recipes:
            return False
        self.locked_recipes.discard(recipe_id)
        return True

    def lock_recipe(self, recipe_id: str) -> bool:
        """
        Lock a recipe behind a quest. Returns True if successful.

        Args:
            recipe_id: The recipe to lock.

        Returns:
            True if the recipe was (or already was) locked.
        """
        if recipe_id in self.locked_recipes:
            return True
        if recipe_id in self.recipes:
            self.locked_recipes.add(recipe_id)
            return True
        return False

    def unlock_gear(self, gear_id: str) -> bool:
        """
        Unlock a gear item by quest reward.

        Args:
            gear_id: The gear item to unlock.

        Returns:
            True if the gear was unlocked.
        """
        self.unlocked_gear.add(gear_id)
        return True

    def is_recipe_locked(self, recipe_id: str) -> bool:
        """Check if a recipe is locked behind a quest."""
        return recipe_id in self.locked_recipes

    # ── Completion Tracking ────────────────────────────────────────

    def process_chain_complete(self, recipe_id: str) -> bool:
        """
        Mark a recipe as completed for progression tracking.

        Args:
            recipe_id: The recipe that was completed.

        Returns:
            True if marked, False if unknown.
        """
        if recipe_id not in self.recipes:
            return False
        self.completed_recipes.add(recipe_id)
        return True
