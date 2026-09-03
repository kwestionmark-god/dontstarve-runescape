"""
combat/gear.py — Gear system for weapons and armor.

Defines GearItem (weapon/armor with stat bonuses) and PlayerGear
(equipped slots: weapon, armor, tool).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional

from config import DATA_DIR, ITEMS_FILE

if TYPE_CHECKING:
    from typing import Any


@dataclass
class GearItem:
    """
    A piece of gear (weapon or armor).

    Fields:
        item_id: Unique identifier (e.g. "wooden_sword").
        name: Display name.
        gear_type: "weapon" or "armor".
        damage: Weapon damage (0 for armor).
        defence_bonus: Flat Defence bonus (0 for weapons).
        attack_bonus: Flat Attack bonus (0 for armor).
        speed_bonus: Attack speed modifier (negative = faster).
        required_combat_level: Minimum Combat level to equip.
        sprite_key: Sprite sheet reference.
        tier: 1 or 2.
        durability: Durability points (None = infinite, Phase 1 tools).
    """

    item_id: str
    name: str
    gear_type: str  # "weapon" or "armor"
    damage: int = 0
    defence_bonus: int = 0
    attack_bonus: int = 0
    speed_bonus: float = 0.0
    required_combat_level: int = 1
    sprite_key: str = ""
    tier: int = 1
    durability: Optional[int] = None

    # Memoized load: several render paths call load_all() every frame; the
    # JSON is static during play. Keyed by file path so tests can vary it.
    _LOAD_CACHE: ClassVar[Dict[str, Dict[str, "GearItem"]]] = {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GearItem":
        """Create a GearItem from a JSON dict."""
        return cls(
            item_id=data["item_id"],
            name=data["name"],
            gear_type=data["gear_type"],
            damage=data.get("damage", 0),
            defence_bonus=data.get("defence_bonus", 0),
            attack_bonus=data.get("attack_bonus", 0),
            speed_bonus=data.get("speed_bonus", 0.0),
            required_combat_level=data.get("required_combat_level", 1),
            sprite_key=data.get("sprite_key", ""),
            tier=data.get("tier", 1),
            durability=data.get("durability"),
        )

    @classmethod
    def load_all(cls, gear_file: str = os.path.join(DATA_DIR, "gear.json")) -> Dict[str, "GearItem"]:
        """
        Load all gear items from gear.json.

        Args:
            gear_file: Path to the gear JSON file.

        Returns:
            Dict mapping item_id to GearItem.
        """
        cached = cls._LOAD_CACHE.get(gear_file)
        if cached is not None:
            return cached
        gear_map: Dict[str, GearItem] = {}
        with open(gear_file, "r") as f:
            data = json.load(f)
        for category in ("weapons", "armor", "tools"):
            if category in data:
                for item_data in data[category].values():
                    item = cls.from_dict(item_data)
                    gear_map[item.item_id] = item
        cls._LOAD_CACHE[gear_file] = gear_map
        return gear_map


@dataclass
class PlayerGear:
    """
    Player's equipped gear slots.

    Fields:
        weapon: Equipped weapon (or None).
        armor: Equipped body armor (or None).
        tool: Equipped tool — axe/pickaxe (carries over from Phase 1).
    """

    weapon: Optional[GearItem] = None
    armor: Optional[GearItem] = None
    tool: Optional[GearItem] = None

    def get_attack_bonus(self) -> int:
        """Sum of attack bonuses from equipped weapon and armor."""
        bonus = 0
        if self.weapon:
            bonus += self.weapon.attack_bonus
        if self.armor:
            bonus += self.armor.attack_bonus
        return bonus

    def get_defence_bonus(self) -> int:
        """Sum of defence bonuses from equipped weapon and armor."""
        bonus = 0
        if self.weapon:
            bonus += self.weapon.defence_bonus
        if self.armor:
            bonus += self.armor.defence_bonus
        return bonus

    def equip(self, gear_item: GearItem) -> bool:
        """
        Equip a gear item into the appropriate slot.

        Args:
            gear_item: The gear item to equip.

        Returns:
            True if equipped successfully, False if wrong type.
        """
        if gear_item.gear_type == "weapon":
            self.weapon = gear_item
        elif gear_item.gear_type == "armor":
            self.armor = gear_item
        elif gear_item.gear_type == "tool":
            self.tool = gear_item
        else:
            return False
        return True

    def unequip(self, gear_type: str) -> Optional[GearItem]:
        """
        Unequip an item from a specific slot.

        Args:
            gear_type: "weapon", "armor", or "tool".

        Returns:
            The unequipped item, or None if nothing was equipped.
        """
        if gear_type == "weapon":
            item = self.weapon
            self.weapon = None
            return item
        elif gear_type == "armor":
            item = self.armor
            self.armor = None
            return item
        elif gear_type == "tool":
            item = self.tool
            self.tool = None
            return item
        return None

    def get_snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of equipped gear for UI rendering."""
        return {
            "weapon": {
                "item_id": self.weapon.item_id if self.weapon else None,
                "name": self.weapon.name if self.weapon else None,
                "damage": self.weapon.damage if self.weapon else 0,
                "attack_bonus": self.weapon.attack_bonus if self.weapon else 0,
                "defence_bonus": self.weapon.defence_bonus if self.weapon else 0,
                "speed_bonus": self.weapon.speed_bonus if self.weapon else 0.0,
            } if self.weapon else None,
            "armor": {
                "item_id": self.armor.item_id if self.armor else None,
                "name": self.armor.name if self.armor else None,
                "defence_bonus": self.armor.defence_bonus if self.armor else 0,
                "attack_bonus": self.armor.attack_bonus if self.armor else 0,
                "speed_bonus": self.armor.speed_bonus if self.armor else 0.0,
            } if self.armor else None,
            "tool": {
                "item_id": self.tool.item_id if self.tool else None,
                "name": self.tool.name if self.tool else None,
            } if self.tool else None,
        }
