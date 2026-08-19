"""
food.py — Food definitions and spoilage management.

Loads food items from data/items.json and provides nutrition values,
spoilage behavior, and cooking skill integration hooks.

Food items have:
- hunger_restoration: How much hunger it restores (0–100)
- hp_restoration: How much HP it restores (negative = damage)
- spoilage_rate: Seconds until the item spoils in inventory (0 = never)
- is_raw: Whether the food is raw (affects cooking skill)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict


@dataclass
class FoodItem:
    """Definition of a food item."""

    item_id: str
    hunger_restoration: float
    hp_restoration: float    # Negative = damage (spoiled food)
    spoilage_rate: float     # Seconds until spoilage completes (0 = never spoils)
    is_raw: bool
    max_stack_size: int
    sprite_key: str
    cooking_base_item: str   # ID of raw food this is cooked from (empty if not cooked)


class FoodRegistry:
    """
    Registry of all food items, loaded from JSON data.

    Provides nutrition values and spoilage info for each food item.
    """

    def __init__(self, items_data: list[dict]) -> None:
        """
        Initialize from JSON data.

        Args:
            items_data: Parsed list of item dicts from items.json.
        """
        self._foods: Dict[str, FoodItem] = {}
        for data in items_data:
            if data.get("is_food", False):
                self._foods[data["id"]] = FoodItem(
                    item_id=data["id"],
                    hunger_restoration=data.get("hunger_restore", 0),
                    hp_restoration=data.get("hp_restore", 0),
                    spoilage_rate=data.get("spoilage_seconds", 0),
                    is_raw=data.get("is_raw", False),
                    max_stack_size=data.get("stack_size", 10),
                    sprite_key=data["sprite_key"],
                    cooking_base_item=data.get("cooking_base_item", ""),
                )

    def get(self, item_id: str) -> FoodItem | None:
        """Look up a food item by ID."""
        return self._foods.get(item_id)

    def all(self) -> list[FoodItem]:
        """Return all registered food items."""
        return list(self._foods.values())

    def is_raw(self, item_id: str) -> bool:
        """Check if an item_id refers to raw food."""
        food = self._foods.get(item_id)
        return food is not None and food.is_raw

    def cooked_from(self, item_id: str) -> str:
        """Get the raw food ID that this cooked item comes from."""
        food = self._foods.get(item_id)
        if food is None:
            return ""
        return food.cooking_base_item
