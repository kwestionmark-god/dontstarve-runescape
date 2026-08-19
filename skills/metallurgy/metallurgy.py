"""
metallurgy.py — Metallurgy skill logic.

Handles smelting ores into ingots, alloy creation (bronze, steel),
fuel cost efficiency, and tool durability bonuses.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager
    from inventory.inventory import Inventory


@dataclass
class SmeltRecipe:
    """A smelting recipe definition."""
    recipe_id: str
    name: str = ""
    ore_item: str = ""
    fuel_item: str = ""
    extra_input: Optional[str] = None  # e.g. tin_ore for bronze
    extra_quantity: int = 0
    output_item: str = ""
    output_quantity: int = 1
    xp_reward: float = 0.0
    base_fuel_cost: int = 1
    requires_alloy_mastery: int = 0


_SKILL_DATA_DIR = Path(__file__).parent / "data"


def _load_smelt_recipes() -> dict[str, "SmeltRecipe"]:
    """Load smelt recipes from the package data JSON."""
    path = _SKILL_DATA_DIR / "recipes.json"
    data = json.loads(path.read_text())
    recipes: dict[str, SmeltRecipe] = {}
    for entry in data["recipes"]:
        recipes[entry["recipe_id"]] = SmeltRecipe(
            recipe_id=entry["recipe_id"],
            name=entry.get("name", entry["recipe_id"]),
            ore_item=entry["ore_item"],
            fuel_item=entry["fuel_item"],
            extra_input=entry.get("extra_input"),
            extra_quantity=entry.get("extra_quantity", 0),
            output_item=entry["output_item"],
            output_quantity=entry.get("output_quantity", 1),
            xp_reward=entry.get("xp_reward", 0.0),
            base_fuel_cost=entry.get("base_fuel_cost", 1),
            requires_alloy_mastery=entry.get("requires_alloy_mastery", 0),
        )
    return recipes


_SMELT_RECIPES = _load_smelt_recipes()


@dataclass
class SmeltResult:
    """Result of a smelting attempt."""
    success: bool
    output_item: Optional[str] = None
    xp_gained: float = 0.0
    message: str = ""


class MetallurgySkill:
    """
    Manages metallurgy skill logic: smelting, alloy creation,
    fuel efficiency, and tool durability.

    Loads smelt recipes from RecipeRegistry when provided,
    falling back to the built-in loader for backward compatibility.
    """

    __slots__ = ("skill_manager", "_registry")

    def __init__(self, skill_manager: SkillManager, recipe_registry=None) -> None:
        self.skill_manager: SkillManager = skill_manager
        self._registry = recipe_registry

    def _get_smelt_recipes(self) -> dict[str, "SmeltRecipe"]:
        """
        Return smelt recipes, loaded from RecipeRegistry when available.

        Falls back to the built-in _SMELT_RECIPES loader.
        """
        if self._registry is not None:
            from inventory.recipe import Recipe
            recipes: dict[str, SmeltRecipe] = {}
            for recipe in self._registry.recipes.values():
                if recipe.processing_chain.startswith("metallurgy_"):
                    recipes[recipe.recipe_id] = SmeltRecipe(
                        recipe_id=recipe.recipe_id,
                        name=recipe.name,
                        ore_item=recipe.input_items[0][0] if recipe.input_items else "",
                        fuel_item=recipe.input_items[1][0] if len(recipe.input_items) > 1 else "charcoal",
                        extra_input=recipe.input_items[2][0] if len(recipe.input_items) > 2 else None,
                        extra_quantity=recipe.input_items[2][1] if len(recipe.input_items) > 2 else 0,
                        output_item=recipe.output_item,
                        output_quantity=recipe.output_quantity,
                        xp_reward=recipe.xp_reward,
                        base_fuel_cost=1,
                        requires_alloy_mastery=0,
                    )
            return recipes
        return _SMELT_RECIPES

    # ── Smelting ────────────────────────────────────────────────────

    def attempt_smelt(
        self,
        recipe_id: str,
        inventory: Inventory,
        player_world_x: float = 0.0,
        player_world_y: float = 0.0,
        structures: List = None,
    ) -> SmeltResult:
        """
        Attempt to smelt ore at an active smelter/furnace.

        Flow:
        1. Verify recipe exists and check alloy mastery
        2. Calculate fuel cost with Smelt Efficiency discount
        3. Check materials in inventory
        4. Roll smelt success (50% + efficiency × 2%, capped 95%)
        5. On success: consume fuel + ore, produce output, grant XP
        6. On failure: consume fuel only, preserve ore

        Args:
            recipe_id: The smelt recipe to execute.
            inventory: The player's inventory.

        Returns:
            SmeltResult with success/failure info.
        """
        recipe = self._get_smelt_recipes().get(recipe_id)
        if recipe is None:
            return SmeltResult(success=False, message="Unknown smelt recipe.")

        # Check proximity to smelter/furnace
        if structures:
            import math
            smelter_nearby = False
            for struct in structures:
                if struct.structure_def.structure_id in ("smelter", "furnace") and struct.is_active:
                    dist = math.sqrt(
                        (struct.world_x - player_world_x) ** 2 +
                        (struct.world_y - player_world_y) ** 2
                    )
                    if dist <= 3 * 64:  # Within 3 tiles
                        smelter_nearby = True
                        break
            if not smelter_nearby:
                return SmeltResult(
                    success=False,
                    message="Must be near a smelter or furnace to smelt.",
                )

        # Check Alloy Mastery requirement
        alloy_level = self.skill_manager.get_effective_stat(
            "metallurgy", "alloy_mastery"
        )
        if alloy_level < recipe.requires_alloy_mastery:
            return SmeltResult(
                success=False,
                message=f"Need Alloy Mastery level {recipe.requires_alloy_mastery}.",
            )

        # Calculate fuel cost with Smelt Efficiency discount
        fuel_cost = self.get_effective_fuel_cost(recipe.base_fuel_cost)

        # Check fuel in inventory
        if not inventory.has_items(recipe.fuel_item, fuel_cost):
            return SmeltResult(success=False, message="Not enough fuel.")

        # Check ore in inventory
        if not inventory.has_items(recipe.ore_item, 1):
            return SmeltResult(success=False, message="Not enough ore.")

        # Check extra input (e.g. tin_ore for bronze)
        if recipe.extra_input and not inventory.has_items(
            recipe.extra_input, recipe.extra_quantity
        ):
            return SmeltResult(success=False, message="Not enough extra material.")

        # Calculate smelt success rate
        smelt_efficiency = self.skill_manager.get_effective_stat(
            "metallurgy", "smelt_efficiency"
        )
        success_rate = min(50.0 + smelt_efficiency * 2.0, 95.0)

        # RNG check
        if random.random() * 100 > success_rate:
            # Failed: fuel consumed, ore preserved
            inventory.remove_item(recipe.fuel_item, fuel_cost)
            return SmeltResult(
                success=False,
                message=f"Smelting failed. Fuel consumed, ore preserved.",
            )

        # Success: consume fuel + ore, produce output
        inventory.remove_item(recipe.fuel_item, fuel_cost)
        inventory.remove_item(recipe.ore_item, 1)

        if recipe.extra_input:
            inventory.remove_item(recipe.extra_input, recipe.extra_quantity)

        inventory.add_item(recipe.output_item, recipe.output_quantity)

        # Grant XP
        self.skill_manager.add_xp("metallurgy", recipe.xp_reward)

        return SmeltResult(
            success=True,
            output_item=recipe.output_item,
            xp_gained=recipe.xp_reward,
            message=f"Successfully smelted {recipe.output_item}.",
        )

    def get_effective_fuel_cost(self, base_cost: int) -> int:
        """
        Calculate effective fuel cost with Smelt Efficiency discount.

        Formula: max(1, floor(base_cost × (1 - smelt_efficiency × 0.10)))

        Args:
            base_cost: Base fuel cost for the recipe.

        Returns:
            Effective fuel cost after discount.
        """
        efficiency = self.skill_manager.get_effective_stat(
            "metallurgy", "smelt_efficiency"
        )
        discount = efficiency * 0.10
        return max(1, int(base_cost * (1 - discount)))

    # ── Tool Durability ─────────────────────────────────────────────

    def calculate_tool_lifespan_multiplier(self) -> float:
        """
        Calculate tool durability multiplier.

        Formula: 1.0 + tool_durability_stat × 0.10

        Examples:
            Tool Durability 5:  1.0 + 0.5 = 1.5× lifespan
            Tool Durability 10: 1.0 + 1.0 = 2.0× lifespan

        Returns:
            Lifespan multiplier.
        """
        stat = self.skill_manager.get_effective_stat(
            "metallurgy", "tool_durability"
        )
        return 1.0 + stat * 0.10

    def apply_tool_usage(self, tool_base_uses: int) -> int:
        """
        Calculate the effective remaining uses for a tool.

        Formula: base_uses × tool_lifespan_multiplier

        Args:
            tool_base_uses: Base number of uses for the tool type.

        Returns:
            Effective remaining uses.
        """
        multiplier = self.calculate_tool_lifespan_multiplier()
        return int(tool_base_uses * multiplier)

    # ── Recipe Queries ──────────────────────────────────────────────

    def get_smelt_recipes(self) -> List[SmeltRecipe]:
        """Return all available smelt recipes."""
        return list(self._get_smelt_recipes().values())

    def get_unlocked_recipes(self) -> List[SmeltRecipe]:
        """Return smelt recipes unlocked by current Alloy Mastery level."""
        alloy_level = self.skill_manager.get_effective_stat(
            "metallurgy", "alloy_mastery"
        )
        return [r for r in self._get_smelt_recipes().values() if r.requires_alloy_mastery <= alloy_level]

    def has_recipe_unlocked(self, recipe_id: str) -> bool:
        """Check if a specific smelt recipe is unlocked."""
        recipe = self._get_smelt_recipes().get(recipe_id)
        if recipe is None:
            return False
        alloy_level = self.skill_manager.get_effective_stat(
            "metallurgy", "alloy_mastery"
        )
        return alloy_level >= recipe.requires_alloy_mastery
