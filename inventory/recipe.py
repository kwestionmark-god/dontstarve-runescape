"""
recipe.py — Recipe data structure.

Defines individual crafting recipes with inputs, outputs, requirements,
and XP rewards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Tuple


@dataclass
class Recipe:
    """
    A single crafting recipe.

    Fields:
        recipe_id: unique identifier (e.g. "planks", "charcoal")
        name: human-readable name (e.g. "Craft Planks")
        input_items: list of (item_id, quantity) pairs
        output_item: single output item_id
        output_quantity: quantity produced
        requires_campfire: whether a campfire structure is needed
        requires_structure: structure_id required to craft this recipe
        xp_reward: XP granted on successful craft
        processing_chain: chain identifier (wood_chain, stone_chain, etc.)
        tier: 1–4
        skill_affects_yield: skill name that can boost output (or None)
        is_food: whether the output is a food item
    """

    recipe_id: str
    name: str
    input_items: List[Tuple[str, int]]
    output_item: str
    output_quantity: int
    requires_campfire: bool
    xp_reward: float
    processing_chain: str
    tier: int
    requires_structure: str = ""
    skill_affects_yield: str | None = None
    is_food: bool = False
    quest_unlock: str | None = None
    # Metallurgy-only fields; ignored by every other recipe type (defaults apply).
    base_fuel_cost: int = 1
    requires_alloy_mastery: int = 0

    @staticmethod
    def from_dict(data: dict) -> "Recipe":
        """
        Create a Recipe from JSON data.

        Args:
            data: Parsed dict from recipes.json.

        Returns:
            A Recipe instance.
        """
        # Determine if output is food by checking items.json
        output_is_food = data.get("is_food", False)

        return Recipe(
            recipe_id=data["id"] if "id" in data else data["recipe_id"],
            name=data["name"],
            input_items=[tuple(pair) for pair in data["input_items"]],
            output_item=data["output_item"],
            output_quantity=data["output_quantity"],
            requires_campfire=data.get("requires_campfire", False),
            requires_structure=data.get("requires_structure", ""),
            xp_reward=data["xp_reward"],
            processing_chain=data["processing_chain"],
            tier=data.get("tier", 1),
            skill_affects_yield=data.get("skill_affects_yield"),
            is_food=output_is_food,
            quest_unlock=data.get("quest_unlock"),
            base_fuel_cost=data.get("base_fuel_cost", 1),
            requires_alloy_mastery=data.get("requires_alloy_mastery", 0),
        )
