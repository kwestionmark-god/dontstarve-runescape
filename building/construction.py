"""
building/construction.py — Construction sub-stat management.

Manages the Construction sub-stats tracked under the Crafting skill.
Handles structure HP bonuses and placement permission checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager
    from building.structure import StructureDef


class Construction:
    """
    Manages Construction sub-stats and structure HP calculations.

    Construction sub-stats are tracked under the Crafting skill:
        - common_building_tech
        - defensive_building_tech
        - offensive_building_tech
        - decorative_building_tech
    """

    __slots__ = ("skill_manager",)

    def __init__(self, skill_manager: SkillManager) -> None:
        self.skill_manager: SkillManager = skill_manager

    # ── Placement Checks ────────────────────────────────────────────

    def can_place_structure(self, struct_def: StructureDef, crafting_level: int) -> tuple[bool, str]:
        """
        Check if the player can place a structure based on Construction stats.

        Args:
            struct_def: The structure blueprint.
            crafting_level: Current Crafting skill level.

        Returns:
            (is_allowed, reason_if_denied).
        """
        # Check Construction sub-stat level
        sub_stat = struct_def.construction_sub_stat
        level = self.skill_manager.get_effective_stat("crafting", sub_stat)

        if level < struct_def.requires_structure_level:
            return False, (
                f"Need {sub_stat.replace('_', ' ').title()} level "
                f"{struct_def.requires_structure_level}."
            )

        # Check Crafting skill level
        if crafting_level < struct_def.requires_skill_level:
            return False, f"Need Crafting level {struct_def.requires_skill_level}."

        return True, ""

    def calculate_structure_hp(self, struct_def: StructureDef) -> int:
        """
        Calculate the HP of a structure with Construction stat bonuses.

        Common structures: base_hp + common_level × 2
        Defensive structures: base_hp + defensive_level × 5

        Args:
            struct_def: The structure blueprint.

        Returns:
            Calculated HP.
        """
        base_hp = struct_def.hp

        sub_stat = struct_def.construction_sub_stat
        if sub_stat == "defensive":
            defensive_level = self.skill_manager.get_effective_stat(
                "crafting", "defensive_building_tech"
            )
            base_hp += defensive_level * 5
        elif sub_stat == "common":
            common_level = self.skill_manager.get_effective_stat(
                "crafting", "common_building_tech"
            )
            base_hp += common_level * 2
        elif sub_stat == "offensive":
            offensive_level = self.skill_manager.get_effective_stat(
                "crafting", "offensive_building_tech"
            )
            base_hp += offensive_level * 3
        elif sub_stat == "decorative":
            decorative_level = self.skill_manager.get_effective_stat(
                "crafting", "decorative_building_tech"
            )
            base_hp += decorative_level * 1

        return base_hp

    def get_material_return_rate(self, struct_def: StructureDef) -> float:
        """
        Get the material return rate when picking up or destroying a structure.

        Portable structures: 100% return
        Fixed structures: 50% return (furnace, smelter, cooking station, garden, bench)
        Defensive fixed structures: 30% return (walls, gates)

        Args:
            struct_def: The structure blueprint.

        Returns:
            Return rate as a fraction (0.0–1.0).
        """
        if struct_def.structure_type == "portable":
            return 1.0
        elif struct_def.construction_sub_stat == "defensive":
            return 0.3
        else:
            return 0.5
