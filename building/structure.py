"""
building/structure.py — Structure definitions and entities.

Defines StructureDef (blueprint) and Structure (placed instance
with HP, fuel, and state tracking).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Tuple

from config import DATA_DIR

if TYPE_CHECKING:
    from typing import Any

StructureType = Literal["portable", "fixed", "advanced"]
ConstructionSubStat = Literal["common", "defensive", "offensive", "decorative"]

# ─── Validation ──────────────────────────────────────────────────────

CANONICAL_STRUCTURE_KEYS = (
    "structure_id",
    "name",
    "structure_type",
    "construction_sub_stat",
    "hp",
    "materials",
    "requires_structure_level",
    "requires_skill_level",
    "biome_compatible",
    "sprite_key",
    "occupies_tile",
    "burnable",
)

VALID_STRUCTURE_TYPES: set[str] = {"portable", "fixed", "advanced"}
VALID_CONSTRUCTION_SUB_STATS: set[str] = {"common", "defensive", "offensive", "decorative"}


def validate_structure_def_dict(entry: dict[str, Any]) -> list[str]:
    """
    Validate a single raw structure entry against the canonical envelope.

    Returns a list of human-readable error strings (empty when the entry is valid).
    """
    errors = []
    if not isinstance(entry, dict):
        return ["entry is not a dict"]

    for key in CANONICAL_STRUCTURE_KEYS:
        if key not in entry:
            errors.append(f"missing required key '{key}'")

    structure_id = entry.get("structure_id")
    if not isinstance(structure_id, str) or not structure_id:
        errors.append("structure_id must be a non-empty string")

    if not isinstance(entry.get("name"), str):
        errors.append("name must be a string")

    structure_type = entry.get("structure_type")
    if structure_type not in VALID_STRUCTURE_TYPES:
        errors.append(f"structure_type must be one of {sorted(VALID_STRUCTURE_TYPES)}")

    construction_sub_stat = entry.get("construction_sub_stat")
    if construction_sub_stat not in VALID_CONSTRUCTION_SUB_STATS:
        errors.append(f"construction_sub_stat must be one of {sorted(VALID_CONSTRUCTION_SUB_STATS)}")

    hp = entry.get("hp")
    if not isinstance(hp, int) or hp <= 0:
        errors.append("hp must be a positive integer")

    materials = entry.get("materials")
    if not isinstance(materials, list):
        errors.append("materials must be a list")
    else:
        for i, mat in enumerate(materials):
            if isinstance(mat, dict):
                if not mat.get("item_id") or not isinstance(mat.get("quantity"), int):
                    errors.append(f"material[{i}] dict must have item_id (str) and quantity (int)")
            elif isinstance(mat, (list, tuple)):
                if len(mat) != 2 or not isinstance(mat[0], str) or not isinstance(mat[1], int):
                    errors.append(f"material[{i}] pair must be [item_id, qty]")
            else:
                errors.append(f"material[{i}] must be [item_id, qty] or {{item_id, qty}}")

    if not isinstance(entry.get("requires_structure_level"), int):
        errors.append("requires_structure_level must be an int")
    if not isinstance(entry.get("requires_skill_level"), int):
        errors.append("requires_skill_level must be an int")

    biome_compatible = entry.get("biome_compatible")
    if biome_compatible is not None and not isinstance(biome_compatible, list):
        errors.append("biome_compatible must be a list or null")

    sprite_key = entry.get("sprite_key")
    if sprite_key is not None and not isinstance(sprite_key, str):
        errors.append("sprite_key must be a string or null")

    occupies_tile = entry.get("occupies_tile")
    if occupies_tile is not None and not isinstance(occupies_tile, bool):
        errors.append("occupies_tile must be a bool or null")

    burnable = entry.get("burnable")
    if burnable is not None and not isinstance(burnable, bool):
        errors.append("burnable must be a bool or null")

    return errors


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
    structure_type: StructureType
    construction_sub_stat: ConstructionSubStat
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
        """Create a StructureDef from a JSON dict (assumes validation already passed)."""
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
    def from_validated_dict(cls, data: Dict[str, Any]) -> Optional["StructureDef"]:
        """Create a StructureDef from a JSON dict, validating first."""
        errors = validate_structure_def_dict(data)
        if errors:
            logging.warning("Skipping invalid structure: %s", "; ".join(errors))
            return None
        return cls.from_dict(data)

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


class StructureDefRegistry:
    """
    Unified registry of all structure definitions.

    Loads structures from JSON sources with validation.
    Provides filtering by category.
    """

    __slots__ = ("structures",)

    def __init__(self) -> None:
        self.structures: Dict[str, Dict[str, StructureDef]] = {
            "common": {},
            "defensive": {},
            "offensive": {},
            "decorative": {},
        }

    def load_all(self, structures_file: str = os.path.join(DATA_DIR, "structures.json")) -> int:
        """
        Load all structure definitions from structures.json with validation.

        Args:
            structures_file: Path to structures.json.

        Returns:
            Total number of structures loaded.
        """
        count = 0
        try:
            with open(structures_file, "r") as f:
                data = json.load(f)
            for category in ("common", "defensive", "offensive", "decorative"):
                if category in data.get("structures", {}):
                    for item_data in data["structures"][category].values():
                        item = StructureDef.from_validated_dict(item_data)
                        if item is not None:
                            # Validate category matches construction_sub_stat
                            if item.construction_sub_stat != category:
                                logging.warning(
                                    "Structure %s in category '%s' has construction_sub_stat '%s', skipping",
                                    item.structure_id, category, item.construction_sub_stat,
                                )
                                continue
                            self.structures[category][item.structure_id] = item
                            count += 1
        except Exception:
            logging.exception("Failed to load structures from %s", structures_file)
        return count

    def get_structure(self, category: str, structure_id: str) -> Optional[StructureDef]:
        """Look up a structure by category and ID."""
        return self.structures.get(category, {}).get(structure_id)

    def get_all_structures(self) -> Dict[str, Dict[str, StructureDef]]:
        """Return all structures grouped by category."""
        return self.structures

    def get_structures_by_category(self, category: str) -> Dict[str, StructureDef]:
        """Return all structures in a specific category."""
        return self.structures.get(category, {})


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
        fire_timer: Timer for offensive structure firing (ballista/trebuchet).
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
    fire_timer: float = 0.0
    instance_id: int = 0  # Unique per placed structure; 0 = unassigned

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
