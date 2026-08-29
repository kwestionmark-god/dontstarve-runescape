"""
building_tech.py — Shared building tech formulas.

Single source of truth for:
- Structure HP calculation (Construction class & BuildingSystem)
- Offensive structure damage calculation (BuildingSystem)
- Material return rates (Construction class & BuildingSystem)
- Crafting skill building tech bonuses (CraftingSkill)

All building tech stats are tracked under the Crafting skill:
    - common_building_tech
    - defensive_building_tech
    - offensive_building_tech
    - decorative_building_tech
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager
    from building.structure import StructureDef

# ─── Building Tech Stat Names ────────────────────────────────────────

BUILDING_TECH_STATS = (
    "common_building_tech",
    "defensive_building_tech",
    "offensive_building_tech",
    "decorative_building_tech",
)

BUILDING_TECH_NAMES: dict[str, str] = {
    "common_building_tech": "Common Building",
    "defensive_building_tech": "Defensive Building",
    "offensive_building_tech": "Offensive Building",
    "decorative_building_tech": "Decorative Building",
}

# ─── HP Calculation ──────────────────────────────────────────────────

def calculate_structure_hp(
    base_hp: int,
    construction_sub_stat: str,
    skill_manager: "SkillManager",
) -> int:
    """
    Calculate structure HP with Construction stat bonuses.

    Args:
        base_hp: Base HP from structure definition.
        construction_sub_stat: One of "common", "defensive", "offensive", "decorative".
        skill_manager: SkillManager to query Crafting sub-stats.

    Returns:
        Calculated HP with stat bonuses applied.
    """
    if construction_sub_stat == "defensive":
        level = skill_manager.get_effective_stat("crafting", "defensive_building_tech")
        return base_hp + level * 5
    elif construction_sub_stat == "common":
        level = skill_manager.get_effective_stat("crafting", "common_building_tech")
        return base_hp + level * 2
    elif construction_sub_stat == "offensive":
        level = skill_manager.get_effective_stat("crafting", "offensive_building_tech")
        return base_hp + level * 3
    elif construction_sub_stat == "decorative":
        level = skill_manager.get_effective_stat("crafting", "decorative_building_tech")
        return base_hp + level * 1
    return base_hp


def calculate_structure_hp_from_def(
    struct_def: "StructureDef",
    skill_manager: "SkillManager",
) -> int:
    """
    Calculate structure HP from a StructureDef.

    Args:
        struct_def: Structure definition with hp and construction_sub_stat.
        skill_manager: SkillManager to query Crafting sub-stats.

    Returns:
        Calculated HP with stat bonuses applied.
    """
    return calculate_structure_hp(
        struct_def.hp,
        struct_def.construction_sub_stat,
        skill_manager,
    )

# ─── Offensive Structure Damage ──────────────────────────────────────

def calculate_offensive_damage(
    base_damage: float,
    multiplier: float,
    skill_manager: "SkillManager",
) -> float:
    """
    Calculate offensive structure damage with building tech bonus.

    Formula: base_damage + offensive_building_tech_level * multiplier

    Args:
        base_damage: Base damage of the offensive structure.
        multiplier: Damage multiplier per offensive_building_tech point.
        skill_manager: SkillManager to query Crafting sub-stats.

    Returns:
        Total damage with stat bonus.
    """
    offensive_level = skill_manager.get_effective_stat(
        "crafting", "offensive_building_tech"
    )
    return base_damage + offensive_level * multiplier

# ─── Material Return Rate ────────────────────────────────────────────

def get_material_return_rate(
    structure_type: str,
    construction_sub_stat: str,
) -> float:
    """
    Get material return rate for picking up/destroying a structure.

    Args:
        structure_type: "portable" or "fixed".
        construction_sub_stat: One of "common", "defensive", "offensive", "decorative".

    Returns:
        Return rate as fraction (0.0–1.0).
    """
    if structure_type == "portable":
        return 1.0
    elif construction_sub_stat == "defensive":
        return 0.3
    else:
        return 0.5

# ─── Crafting Skill Building Tech Bonuses ────────────────────────────

def get_building_tech_level(
    skill_manager: "SkillManager",
    tech_type: str,
) -> int:
    """
    Get allocated points for a building tech stat.

    Args:
        skill_manager: SkillManager to query.
        tech_type: One of BUILDING_TECH_STATS.

    Returns:
        Allocated points (0 if not found).
    """
    return skill_manager.get_effective_stat("crafting", tech_type)


def get_building_tech_bonus(
    skill_manager: "SkillManager",
    tech_type: str,
) -> float:
    """
    Get building tech bonus multiplier.

    Formula: 1.0 + points * 0.10 (each point = 10% bonus)

    Args:
        skill_manager: SkillManager to query.
        tech_type: One of BUILDING_TECH_STATS.

    Returns:
        Bonus multiplier (1.0+).
    """
    points = get_building_tech_level(skill_manager, tech_type)
    return 1.0 + points * 0.10


def get_all_building_tech_bonuses(
    skill_manager: "SkillManager",
) -> dict[str, float]:
    """
    Return all building tech bonuses as displayable name → multiplier.

    Returns:
        Dict of display_name → bonus_multiplier.
    """
    return {
        BUILDING_TECH_NAMES[k]: get_building_tech_bonus(skill_manager, k)
        for k in BUILDING_TECH_STATS
    }