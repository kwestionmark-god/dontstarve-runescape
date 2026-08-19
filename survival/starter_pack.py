"""
starter_pack.py — Player starting equipment and character backgrounds.

Provides:
- CharacterDefinition: background + starting stats dataclass
- StarterPack: predefined equipment bundles
- apply_starter_pack: function that populates inventory at game start
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from typing import Dict
    from inventory.inventory import Inventory


@dataclass
class CharacterDefinition:
    """
    Player character definition for future background selection.

    Fields:
        name: Player's chosen name (empty = default)
        background: Character background (e.g. "forester", "prospector")
        starting_stats: Initial stat allocations (skill_id → {sub_stat: points})
        starter_pack_id: Which starter pack to use
    """
    name: str = ""
    background: str = ""  # "" = default/null background
    starting_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    starter_pack_id: str = "default"


# Starter pack definitions: (tool_item, torch_item, food_item)
# 3 variants per design doc
_STARTER_PACKS: Dict[str, Tuple[str, str, str]] = {
    "forester": ("axe", "torch", "berries"),
    "prospector": ("pickaxe", "torch", "raw_meat"),
    "scavenger": ("torch", "berries", "raw_fish"),
    "default": ("torch", "berries", "raw_fish"),
}


def get_starter_pack(pack_id: str) -> Tuple[str, str, str]:
    """
    Get the starter pack items for a given pack ID.

    Args:
        pack_id: One of "forester", "prospector", "scavenger", "default".

    Returns:
        (tool_item, torch_item, food_item) tuple.
    """
    return _STARTER_PACKS.get(pack_id, _STARTER_PACKS["default"])


def apply_starter_pack(
    inventory: Inventory,
    pack_id: str = "default",
) -> bool:
    """
    Apply a starter pack to the player's inventory.

    Adds the tool, torch, and food items from the selected pack.
    Items are stacked into existing slots or placed in empty slots.

    Args:
        inventory: The player's inventory to populate.
        pack_id: Which starter pack to apply.

    Returns:
        True if all items were added successfully.
    """
    tool_item, torch_item, food_item = get_starter_pack(pack_id)

    success = True
    success = success and inventory.add_item(tool_item, 1)
    success = success and inventory.add_item(torch_item, 1)
    success = success and inventory.add_item(food_item, 1)

    # Auto-equip the tool
    if tool_item:
        inventory.equip_item(tool_item)

    return success
