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
    """Definition of a food item (holds only food-specific data)."""

    item_id: str
    hunger_restoration: float
    hp_restoration: float    # Negative = damage (spoiled food)
    spoilage_rate: float     # Seconds until spoilage completes (0 = never spoils)
    is_raw: bool
    cooking_base_item: str   # ID of raw food this is cooked from (empty if not cooked)

    def get_stack_size(self, items_data: dict[str, dict]) -> int:
        """Get max stack size from item data."""
        item = items_data.get(self.item_id)
        return item.get("stack_size", 10) if item else 10

    def get_sprite_key(self, items_data: dict[str, dict]) -> str:
        """Get sprite key from item data."""
        item = items_data.get(self.item_id)
        return item.get("sprite_key", "") if item else ""


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
        self._items_data: Dict[str, dict] = {item["id"]: item for item in items_data}
        self._foods: Dict[str, FoodItem] = {}
        for data in items_data:
            if data.get("is_food", False):
                self._foods[data["id"]] = FoodItem(
                    item_id=data["id"],
                    hunger_restoration=data.get("hunger_restore", 0),
                    hp_restoration=data.get("hp_restore", 0),
                    spoilage_rate=data.get("spoilage_seconds", 0),
                    is_raw=data.get("is_raw", False),
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

    def get_stack_size(self, item_id: str) -> int:
        """Get max stack size for an item (from item data)."""
        item = self._items_data.get(item_id)
        return item.get("stack_size", 10) if item else 10

    def get_sprite_key(self, item_id: str) -> str:
        """Get sprite key for an item (from item data)."""
        item = self._items_data.get(item_id)
        return item.get("sprite_key", "") if item else ""