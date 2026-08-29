"""
crafting_system.py — Crafting engine.

Manages all processing chains, recipe lookups, validation, and
execution. Consumes materials from inventory and produces output items.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Optional, Tuple

    from skills.skill_manager import SkillManager
    from inventory.inventory import Inventory

# Runtime imports
from typing import Dict
from inventory.recipe import Recipe, validate_recipe_dict


def _chain_to_skill(processing_chain: str) -> str:
    """
    Map a processing chain to the registered skill that earns XP for its
    recipes. Used as the XP-routing default when a recipe does not set
    ``skill_affects_yield``; prevents every generic recipe from awarding
    woodcutting XP.
    """
    chain = (processing_chain or "").lower()
    if chain.startswith("wood"):
        return "woodcutting"
    return "crafting"


class CraftResult:
    """Result of a craft attempt."""

    def __init__(
        self,
        success: bool,
        item_id: str = "",
        quantity: int = 0,
        xp_gained: float = 0.0,
        message: str = "",
    ) -> None:
        self.success = success
        self.item_id = item_id
        self.quantity = quantity
        self.xp_gained = xp_gained
        self.message = message


class CraftingSystem:
    """
    Manages crafting recipes, validation, and execution.

    Delegates recipe storage and queries to a RecipeRegistry.

    Fields:
        _registry: RecipeRegistry holding all recipes
        completed_recipes: set of recipe_ids that have been crafted at least once
        locked_recipes: set of recipe_ids locked behind quests
        unlocked_gear: set of gear_ids unlocked by quests
    """

    __slots__ = ("_registry", "completed_recipes", "locked_recipes", "unlocked_gear")

    def __init__(self, recipe_registry) -> None:
        if recipe_registry is None:
            raise ValueError("CraftingSystem requires a RecipeRegistry")
        self._registry = recipe_registry
        self.completed_recipes: set[str] = set()
        self.locked_recipes: set[str] = set()
        self.unlocked_gear: set[str] = set()

    @property
    def recipes(self) -> Dict[str, Recipe]:
        """Return the recipe store from the registry."""
        return self._registry.recipes

    def load_recipes(self, recipes_data: list[dict]) -> int:
        """
        Load recipes from JSON data into the registry.

        Validates each recipe before loading (malformed recipes are skipped).

        Args:
            recipes_data: Parsed list of recipe dicts from recipes.json.

        Returns:
            Number of recipes loaded.
        """
        count = 0
        for data in recipes_data:
            errors = validate_recipe_dict(data)
            if errors:
                import logging
                logging.warning("Skipping invalid recipe: %s", "; ".join(errors))
                continue
            recipe = Recipe.from_dict(data)
            self._registry.recipes[recipe.recipe_id] = recipe
            if recipe.quest_unlock is not None:
                self._registry.locked_recipes.add(recipe.recipe_id)
            count += 1
        return count

    # ── Recipe Queries ─────────────────────────────────────────────

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """Look up a recipe by ID."""
        return self._registry.get_recipe(recipe_id)

    def get_available_recipes(
        self, skill_manager: Optional[SkillManager] = None,
    ) -> List[Recipe]:
        """
        Return all recipes not locked behind quests.

        Phase 2+: filter by skill levels, structures, etc.

        Args:
            skill_manager: Optional skill manager for level-based filtering.
        """
        return self._registry.get_available_recipes()

    def get_recipes_for_chain(self, chain: str) -> List[Recipe]:
        """
        Return recipes belonging to a processing chain.

        Args:
            chain: Chain identifier (e.g. "wood_chain", "stone_chain").

        Returns:
            List of recipes in the chain.
        """
        return self._registry.get_recipes_for_chain(chain)

    def is_recipe_locked(self, recipe_id: str) -> bool:
        """Check if a recipe is locked behind a quest."""
        return self._registry.is_recipe_locked(recipe_id)

    # ── Validation ─────────────────────────────────────────────────

    def validate_recipe(self, recipe_id: str, inventory: Inventory) -> bool:
        """
        Check if the player has all required materials for a recipe.

        Args:
            recipe_id: The recipe to validate.
            inventory: The player's inventory.

        Returns:
            True if all materials are available.
        """
        recipe = self._registry.get_recipe(recipe_id)
        if recipe is None:
            return False
        for item_id, quantity in recipe.input_items:
            if not inventory.has_items(item_id, quantity):
                return False
        return True

    def get_material_status(
        self, recipe_id: str, inventory: Inventory
    ) -> List[Tuple[str, int, int]]:
        """
        Get material availability for a recipe.

        Returns:
            List of (item_id, required, available) tuples.
        """
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            return []
        status: List[Tuple[str, int, int]] = []
        for item_id, required in recipe.input_items:
            available = inventory.get_item_quantity(item_id)
            status.append((item_id, required, available))
        return status

    def get_recipes_for_skill(self, skill: str) -> List[Recipe]:
        """
        Return recipes affected by a given skill.

        Filters recipes where skill_affects_yield matches the skill name.

        Args:
            skill: Skill name (e.g. "cooking").

        Returns:
            List of recipes affected by the skill.
        """
        return [
            r for r in self.recipes.values()
            if r.skill_affects_yield == skill
        ]

    def unlock_recipe(self, recipe_id: str) -> bool:
        """
        Unlock a recipe for crafting. Returns True if successful.

        Idempotent: unlocking an already-unlocked recipe is a no-op.
        Silently ignores unknown recipe IDs.

        Args:
            recipe_id: The recipe to unlock.

        Returns:
            True if the recipe was (or already was) unlocked.
        """
        return self._registry.unlock_recipe(recipe_id)

    def lock_recipe(self, recipe_id: str) -> bool:
        """
        Lock a recipe behind a quest. Returns True if successful.

        Idempotent: locking an already-locked recipe is a no-op.
        Silently ignores unknown recipe IDs.

        Args:
            recipe_id: The recipe to lock.

        Returns:
            True if the recipe was (or already was) locked.
        """
        return self._registry.lock_recipe(recipe_id)

    def unlock_gear(self, gear_id: str) -> bool:
        """
        Unlock a gear item by quest reward. Returns True if successful.

        Handles non-existent gear IDs gracefully (always returns True).

        Args:
            gear_id: The gear item to unlock.

        Returns:
            True if the gear was unlocked.
        """
        self.unlocked_gear.add(gear_id)
        return True

    def process_chain_complete(self, recipe_id: str) -> bool:
        """
        Mark a recipe's completion for progression tracking.

        Called after a successful craft to register the recipe as
        completed in the player's progression.

        Args:
            recipe_id: The recipe that was completed.

        Returns:
            True if the recipe was marked, False if unknown.
        """
        if recipe_id not in self.recipes:
            return False
        self.completed_recipes.add(recipe_id)
        return True

    # ── Execution ──────────────────────────────────────────────────

    def craft(
        self,
        recipe_id: str,
        inventory: Inventory,
        skill_manager: Optional[SkillManager] = None,
        structures: list | None = None,
        player_pos: tuple[float, float] | None = None,
        quest_system: Optional[object] = None,
        spoilage_seconds: float | None = None,
    ) -> CraftResult:
        """
        Execute a craft: validate, consume materials, produce output.

        Args:
            recipe_id: The recipe to craft.
            inventory: The player's inventory.
            skill_manager: Optional skill manager for XP granting.
            structures: Optional list of placed Structure instances.
            player_pos: Optional (player_x, player_y) in pixels for station checks.
            quest_system: Optional quest system; on success its record_craft()
                is called so "craft N of X" quest objectives can advance.
            spoilage_seconds: Optional spoilage timer for the output item (if perishable).

        Returns:
            CraftResult with success/failure info.
        """
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            return CraftResult(success=False, message="Unknown recipe.")

        # Station proximity validation
        if structures and player_pos and recipe.requires_structure:
            from utils.structure_utils import is_structure_nearby

            player_x, player_y = player_pos
            if not is_structure_nearby(structures, player_x, player_y, recipe.requires_structure):
                return CraftResult(
                    success=False,
                    message=f"You need to be near a {recipe.requires_structure} to craft this.",
                )

        if not self.validate_recipe(recipe_id, inventory):
            return CraftResult(success=False, message="Missing materials.")

        # Check capacity before consuming so a full inventory reports
        # "inventory full" instead of silently losing the materials.
        if not inventory.can_add(recipe.output_item, recipe.output_quantity):
            return CraftResult(success=False, message="Your inventory is full.")

        # Consume materials
        for item_id, quantity in recipe.input_items:
            inventory.remove_item(item_id, quantity)

        # Produce output (spoilage applied to new stacks only)
        inventory.add_item(recipe.output_item, recipe.output_quantity, spoilage_seconds=spoilage_seconds)

        # Grant XP to the relevant skill based on recipe. Fall back to the
        # skill implied by the processing chain when the recipe does not set
        # skill_affects_yield, so generic recipes stop awarding woodcutting XP.
        xp_gained = recipe.xp_reward
        if skill_manager is not None:
            skill_id = recipe.skill_affects_yield or _chain_to_skill(recipe.processing_chain)
            skill_manager.add_xp(skill_id, xp_gained)

        # Mark completed
        self.completed_recipes.add(recipe_id)

        # Quest system craft tracking (optional; quest_system.record_craft).
        if quest_system is not None:
            quest_system.record_craft(recipe_id)

        return CraftResult(
            success=True,
            item_id=recipe.output_item,
            quantity=recipe.output_quantity,
            xp_gained=xp_gained,
            message=f"Crafted {recipe.output_quantity}x {recipe.name}.",
        )

    def cook(
        self,
        recipe_id: str,
        inventory: Inventory,
        skill_manager: Optional[SkillManager] = None,
        has_campfire: bool = False,
        structures: list | None = None,
        player_pos: tuple[float, float] | None = None,
        quest_system: Optional[object] = None,
        spoilage_seconds: float | None = None,
    ) -> CraftResult:
        """
        Execute a cooking recipe with success/failure based on Cooking skill.

        Unlike regular crafting, cooking has:
        - Campfire requirement validation
        - Station proximity validation
        - Success rate based on Cooking success_rate sub-stat
        - Failure preserves raw materials (doesn't destroy them)
        - Spoilage timer set on success

        Args:
            recipe_id: The cooking recipe to execute.
            inventory: The player's inventory.
            skill_manager: Optional skill manager for XP and stat lookup.
            has_campfire: Whether the player is near a campfire.
            structures: Optional list of placed Structure instances.
            player_pos: Optional (player_x, player_y) in pixels for station checks.
            quest_system: Optional quest system; on success its record_craft()
                is called so "craft N of X" quest objectives can advance.
            spoilage_seconds: Optional spoilage timer for the output item (if perishable).

        Returns:
            CraftResult with success/failure info.
        """
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            return CraftResult(success=False, message="Unknown recipe.")

        # Station proximity validation
        if structures and player_pos and recipe.requires_structure:
            from utils.structure_utils import is_structure_nearby

            player_x, player_y = player_pos
            if not is_structure_nearby(structures, player_x, player_y, recipe.requires_structure):
                return CraftResult(
                    success=False,
                    message=f"You need to be near a {recipe.requires_structure} to cook this.",
                )

        # Check campfire requirement
        if recipe.requires_campfire and not has_campfire:
            return CraftResult(success=False, message="You need a campfire to cook this.")

        # Check materials
        if not self.validate_recipe(recipe_id, inventory):
            return CraftResult(success=False, message="Missing materials.")

        # Refuse when there is no room for the result, so a full inventory
        # reports "inventory full" rather than silently dropping the cooked item.
        if not inventory.can_add(recipe.output_item, recipe.output_quantity):
            return CraftResult(success=False, message="Your inventory is full.")

        # Save inventory state for rollback on failure
        saved_slots = inventory.snapshot()

        # Cooking success roll: base 50% + cooking success_rate * 2% per point
        import random
        success_threshold = 50.0
        if skill_manager is not None:
            cooking_success = skill_manager.get_effective_stat("cooking", "success_rate")
            success_threshold += cooking_success * 2.0

        if random.random() * 100 < success_threshold:
            # Success — consume materials and produce output
            for item_id, quantity in recipe.input_items:
                inventory.remove_item(item_id, quantity)
            inventory.add_item(recipe.output_item, recipe.output_quantity, spoilage_seconds=spoilage_seconds)

            # Grant XP to Cooking skill
            xp_gained = recipe.xp_reward
            if skill_manager is not None:
                skill_manager.add_xp("cooking", xp_gained)

            self.completed_recipes.add(recipe_id)

            if quest_system is not None:
                quest_system.record_craft(recipe_id)

            return CraftResult(
                success=True,
                item_id=recipe.output_item,
                quantity=recipe.output_quantity,
                xp_gained=xp_gained,
                message=f"Crafted {recipe.output_quantity}x {recipe.name}.",
            )

        else:
            # Failure — rollback materials (preserve raw items)
            inventory.slots = saved_slots
            return CraftResult(
                success=False,
                message="The cooking failed. The raw ingredients are preserved.",
            )
