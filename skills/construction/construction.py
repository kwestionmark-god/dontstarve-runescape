"""
construction.py — Construction sub-stat management.

Manages the Construction sub-stats tracked under the Crafting skill.
Handles structure HP bonuses and placement permission checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from skills.building_tech import (
    calculate_structure_hp_from_def,
    get_material_return_rate,
)

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

    def __init__(self, skill_manager: "SkillManager") -> None:
        self.skill_manager: SkillManager = skill_manager

    # ── Placement Checks ────────────────────────────────────────────

    def can_place_structure(self, struct_def: "StructureDef", crafting_level: int) -> tuple[bool, str]:
        """
        Check if the player can place a structure based on Construction stats.

        Args:
            struct_def: The structure blueprint.
            crafting_level: Current Crafting skill level.

        Returns:
            (is_allowed, reason_if_denied).
        """
        # Check Construction sub-stat level. structures.json stores the SHORT
        # category name ("common"/"defensive"/"offensive"/"decorative"), while
        # the SkillManager tracks the LONG sub-stat keys
        # ("common_building_tech", ...) — map the short name to the real key.
        short_name = struct_def.construction_sub_stat
        stat_key = f"{short_name}_building_tech"
        level = self.skill_manager.get_effective_stat("crafting", stat_key)

        if level < struct_def.requires_structure_level:
            return False, (
                f"Need {short_name.replace('_', ' ').title()} level "
                f"{struct_def.requires_structure_level}."
            )

        # Check Crafting skill level
        if crafting_level < struct_def.requires_skill_level:
            return False, f"Need Crafting level {struct_def.requires_skill_level}."

        return True, ""

    def calculate_structure_hp(self, struct_def: "StructureDef") -> int:
        """
        Calculate the HP of a structure with Construction stat bonuses.

        Delegates to skills.building_tech for the shared formula.

        Args:
            struct_def: The structure blueprint.

        Returns:
            Calculated HP.
        """
        return calculate_structure_hp_from_def(struct_def, self.skill_manager)

    def get_material_return_rate(self, struct_def: "StructureDef") -> float:
        """
        Get the material return rate when picking up or destroying a structure.

        Delegates to skills.building_tech for the shared formula.

        Portable structures: 100% return
        Fixed structures: 50% return (furnace, smelter, cooking station, garden, bench)
        Defensive fixed structures: 30% return (walls, gates)

        Args:
            struct_def: The structure blueprint.

        Returns:
            Return rate as a fraction (0.0–1.0).
        """
        return get_material_return_rate(
            struct_def.structure_type,
            struct_def.construction_sub_stat,
        )
