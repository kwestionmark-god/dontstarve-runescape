"""
building/structure.py — Structure definitions and entities.

Defines StructureDef (blueprint) and Structure (placed instance
with HP, fuel, and state tracking).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from config import DATA_DIR

if TYPE_CHECKING:
    from typing import Any


@dataclass
class StructureDef:
    """
    Blueprint for a placeable structure.

    Fields:
        structure_id: Unique identifier (e.g. "stone_wall").
        name: Display name.
        structure_type: "portable", "fixed", or "advanced".
        construction_sub_stat: Sub-stat category —
            "common", "defensive", "offensive", "decorative".
        hp: Base health points.
        materials: Required materials — [(item_id, quantity)].
        requires_structure_level: Required Construction sub-stat level.
        requires_skill_level: Required Crafting skill level.
        biome_compatible: Biome IDs where this structure can be placed.
        sprite_key: Sprite sheet reference.
        occupies_tile: True if movement is blocked on this tile.
        burnable: True if the structure can be destroyed by fire.
    """

    structure_id: str
    name: str
    structure_type: str  # "portable", "fixed", "advanced"
    construction_sub_stat: str  # "common", "defensive", "offensive", "decorative"
    hp: int
    materials: List[Tuple[str, int]]
    requires_structure_level: int
    requires_skill_level: int
    biome_compatible: List[str]
    sprite_key: str = ""
    occupies_tile: bool = False
    burnable: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructureDef":
        """Create a StructureDef from a JSON dict."""
        raw_materials = data.get("materials", [])
        if raw_materials and isinstance(raw_materials[0], dict):
            # Format: [{"item_id": ..., "quantity": ...}]
            materials = [
                (item["item_id"], item["quantity"])
                for item in raw_materials
            ]
        else:
            # Format: [["stick", 2], ["charcoal", 1]]
            materials = [
                (item[0], item[1])
                for item in raw_materials
            ]
        return cls(
            structure_id=data["structure_id"],
            name=data["name"],
            structure_type=data["structure_type"],
            construction_sub_stat=data["construction_sub_stat"],
            hp=data["hp"],
            materials=materials,
            requires_structure_level=data["requires_structure_level"],
            requires_skill_level=data["requires_skill_level"],
            biome_compatible=data.get("biome_compatible", []),
            sprite_key=data.get("sprite_key", ""),
            occupies_tile=data.get("occupies_tile", False),
            burnable=data.get("burnable", False),
        )

    @classmethod
    def load_all(
        cls,
        structures_file: str = os.path.join(DATA_DIR, "structures.json"),
    ) -> Dict[str, Dict[str, "StructureDef"]]:
        """
        Load all structure definitions from structures.json.

        Returns:
            Dict mapping category → (structure_id → StructureDef).
        """
        result: Dict[str, Dict[str, StructureDef]] = {}
        with open(structures_file, "r") as f:
            data = json.load(f)
        for category in ("common", "defensive", "offensive", "decorative"):
            if category in data.get("structures", {}):
                result[category] = {}
                for item_data in data["structures"][category].values():
                    item = cls.from_dict(item_data)
                    result[category][item.structure_id] = item
        return result


@dataclass
class Structure:
    """
    A placed structure instance.

    Fields:
        structure_def: The blueprint for this structure.
        world_x: X position (grid position, in pixels).
        world_y: Y position (in pixels).
        hp: Current HP (modified by Construction stats at placement).
        max_hp: Maximum HP.
        is_active: Whether the structure is operational.
        fuel_items: Fuel for campfires/furnaces — [(item_id, qty)].
        is_portable: True if the structure can be picked up.
    """

    structure_def: StructureDef
    world_x: float
    world_y: float
    hp: int
    max_hp: int
    is_active: bool = True
    fuel_items: Optional[List[Tuple[str, int]]] = None
    is_portable: bool = False
    assigned_npc_id: Optional[str] = None

    def take_damage(self, damage: int) -> bool:
        """
        Apply damage to this structure.

        Args:
            damage: Amount of damage to deal.

        Returns:
            True if the structure was destroyed.
        """
        self.hp = max(0, self.hp - damage)
        if self.hp <= 0:
            self.is_active = False
            return True
        return False

    def is_alive(self) -> bool:
        """Returns True if the structure has HP > 0."""
        return self.hp > 0

    def heal(self, amount: int) -> None:
        """Restore HP on this structure."""
        self.hp = min(self.max_hp, self.hp + amount)
