"""
inventory/ — Player inventory management and recipe definitions.

Moved from crafting/ in Phase 3.5.4.
"""

from inventory.inventory import Inventory, InventorySlot
from inventory.recipe import Recipe

__all__ = ["Inventory", "InventorySlot", "Recipe"]
