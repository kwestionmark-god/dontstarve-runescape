"""
inventory.py — Player inventory management.

Manages the player's carried items in a 20-slot grid.
Each slot tracks item_id, quantity, spoilage timer, and equipment state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List, Optional, Tuple


@dataclass
class InventorySlot:
    """A single inventory slot."""

    item_id: str | None = None
    quantity: int = 0
    spoilage_remaining: float | None = None  # None = not perishable
    is_equipped: bool = False


class Inventory:
    """
    Player's carried items in a 20-slot grid.

    Fields:
        max_slots: 20 (fixed)
        slots: list of InventorySlot | None
        gold: currency (Phase 1 stub: always 0)
    """

    __slots__ = ("max_slots", "slots", "gold", "_stack_sizes")

    def __init__(self) -> None:
        self.max_slots: int = 20
        self.slots: List[Optional[InventorySlot]] = [None] * self.max_slots
        self.gold: int = 0
        self._stack_sizes: Dict[str, int] = {}  # item_id → max stack size

    def set_stack_size(self, item_id: str, max_stack: int) -> None:
        """
        Register the maximum stack size for an item type.

        Called when items.json data is loaded.

        Args:
            item_id: The item identifier.
            max_stack: Maximum quantity per stack.
        """
        self._stack_sizes[item_id] = max_stack

    def _get_max_stack(self, item_id: str) -> int:
        """Get the max stack size for an item. Defaults to 28 if unknown."""
        return self._stack_sizes.get(item_id, 28)

    # ── Item Operations ────────────────────────────────────────────

    def add_item(self, item_id: str, quantity: int) -> bool:
        """
        Add items to inventory. Stacks into existing slots first,
        then uses empty slots.

        Args:
            item_id: The item to add.
            quantity: Amount to add.

        Returns:
            True if all items were added, False if inventory is full.
        """
        if quantity <= 0:
            return True

        remaining = quantity

        # First: stack into existing slots of the same item
        max_stack = self._get_max_stack(item_id)
        for slot in self.slots:
            if slot is not None and slot.item_id == item_id:
                space = max_stack - slot.quantity
                if space > 0:
                    added = min(remaining, space)
                    slot.quantity += added
                    remaining -= added
                    if remaining <= 0:
                        return True

        # Then: use empty slots
        while remaining > 0:
            slot_idx = self._find_empty_slot()
            if slot_idx is None:
                # Inventory full — return items back
                return False
            slot = self.slots[slot_idx]
            if slot is None:
                slot = InventorySlot(item_id=item_id, quantity=remaining)
                self.slots[slot_idx] = slot
                remaining = 0

        return True

    def remove_item(self, item_id: str, quantity: int) -> bool:
        """
        Remove items from inventory.

        Args:
            item_id: The item to remove.
            quantity: Amount to remove.

        Returns:
            True if all items were removed, False if insufficient.
        """
        if quantity <= 0:
            return True

        if not self.has_items(item_id, quantity):
            return False

        remaining = quantity
        for slot in self.slots:
            if slot is None or slot.item_id != item_id:
                continue
            remove_amount = min(remaining, slot.quantity)
            slot.quantity -= remove_amount
            remaining -= remove_amount
            if slot.quantity <= 0:
                slot.item_id = None
                slot.quantity = 0
                slot.spoilage_remaining = None
                slot.is_equipped = False
            if remaining <= 0:
                return True

        return True

    def has_items(self, item_id: str, quantity: int) -> bool:
        """
        Check if the player has at least `quantity` of an item.

        Args:
            item_id: The item to check.
            quantity: Amount required.

        Returns:
            True if the player has enough.
        """
        if quantity <= 0:
            return True
        total = sum(
            slot.quantity
            for slot in self.slots
            if slot is not None and slot.item_id == item_id
        )
        return total >= quantity

    def get_item_quantity(self, item_id: str) -> int:
        """
        Get total quantity of an item across all slots.

        Args:
            item_id: The item to query.

        Returns:
            Total quantity (0 if not present).
        """
        return sum(
            slot.quantity
            for slot in self.slots
            if slot is not None and slot.item_id == item_id
        )

    # ── Slot Operations ────────────────────────────────────────────

    def _find_empty_slot(self) -> Optional[int]:
        """Return the index of the first empty slot, or None."""
        for i, slot in enumerate(self.slots):
            if slot is None or (slot.item_id is None and slot.quantity == 0):
                return i
        return None

    def find_item_slot(self, item_id: str) -> Optional[int]:
        """
        Return the index of the first slot containing the given item.

        Args:
            item_id: The item to find.

        Returns:
            Slot index or None.
        """
        for i, slot in enumerate(self.slots):
            if slot is not None and slot.item_id == item_id:
                return i
        return None

    def equip_item(self, item_id: str) -> bool:
        """
        Equip an item (mark it in the equipped slot).

        Unequips any previous item of the same type first.

        Args:
            item_id: The item to equip.

        Returns:
            True if equipped successfully.
        """
        # Unequip any existing item of same type
        for slot in self.slots:
            if slot is not None and slot.item_id == item_id and slot.is_equipped:
                slot.is_equipped = False

        # Find and equip
        for slot in self.slots:
            if slot is not None and slot.item_id == item_id:
                slot.is_equipped = True
                return True

        return False

    def unequip_all(self) -> None:
        """Unequip all items."""
        for slot in self.slots:
            if slot is not None:
                slot.is_equipped = False

    # ── Tick / Spoilage ────────────────────────────────────────────

    def tick(self, dt: float) -> List[str]:
        """
        Process spoilage for perishable items. Removes spoiled items.

        Args:
            dt: Delta time in seconds.

        Returns:
            List of feedback messages for spoiled items.
        """
        messages: List[str] = []
        for slot in self.slots:
            if slot is None or slot.spoilage_remaining is None:
                continue
            slot.spoilage_remaining -= dt
            if slot.spoilage_remaining <= 0:
                messages.append(f"{slot.item_id} spoiled and disappeared.")
                slot.item_id = None
                slot.quantity = 0
                slot.spoilage_remaining = None
        return messages

    def set_spoilage(self, item_id: str, seconds: float) -> bool:
        """
        Set spoilage timer on all slots of an item type.

        Called when an item is first added and has a non-zero
        spoilage rate from the food registry.

        Args:
            item_id: The item to set spoilage on.
            seconds: Seconds until spoilage.

        Returns:
            True if any slots were updated.
        """
        updated = False
        for slot in self.slots:
            if slot is not None and slot.item_id == item_id:
                slot.spoilage_remaining = seconds
                updated = True
        return updated

    # ── Snapshots ──────────────────────────────────────────────────

    def get_snapshot(self) -> List[Dict[str, object]]:
        """
        Return a frozen snapshot of inventory for UI rendering.

        Returns:
            List of slot dicts (20 entries, None for empty slots).
        """
        result: List[Dict[str, object]] = []
        for slot in self.slots:
            if slot is None or (slot.item_id is None and slot.quantity == 0):
                result.append(None)
            else:
                result.append({
                    "item_id": slot.item_id,
                    "quantity": slot.quantity,
                    "spoilage_remaining": slot.spoilage_remaining,
                    "is_equipped": slot.is_equipped,
                })
        return result

    def count_non_empty(self) -> int:
        """Returns the number of non-empty slots."""
        return sum(
            1 for slot in self.slots
            if slot is not None and slot.item_id is not None and slot.quantity > 0
        )
