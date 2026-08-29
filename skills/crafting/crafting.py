"""
crafting.py — Crafting skill logic.

Provides processing speed bonuses, item quality modifiers,
and building tech bonuses based on allocated sub-stats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from skills.building_tech import (
    BUILDING_TECH_STATS,
    BUILDING_TECH_NAMES,
    get_building_tech_level,
    get_building_tech_bonus,
    get_all_building_tech_bonuses,
)

if TYPE_CHECKING:
    from typing import Dict

    from skills.skill_manager import SkillManager


class CraftingSkill:
    """Manages crafting skill effects."""

    __slots__ = ("skill_manager",)

    def __init__(self, skill_manager: "SkillManager") -> None:
        self.skill_manager: SkillManager = skill_manager

    # ── Processing Speed ─────────────────────────────────────────────

    def get_processing_speed_modifier(self) -> float:
        """
        Return processing speed multiplier.

        Formula: 1.0 + processing_speed * 0.05

        Each Processing Speed point reduces craft time by 5%.

        Returns:
            Time multiplier (0.5–∞). Lower is faster.
            e.g. speed 5 → 1.0 / 1.25 = 0.8× time (20% faster)
        """
        speed = self.skill_manager.get_effective_stat("crafting", "processing_speed")
        return 1.0 / (1.0 + speed * 0.05)

    def get_effective_craft_time(self, base_time: float) -> float:
        """
        Return the adjusted craft time.

        Args:
            base_time: Base craft time in seconds.

        Returns:
            Reduced craft time after speed modifier.
        """
        return base_time * self.get_processing_speed_modifier()

    # ── Item Quality ─────────────────────────────────────────────────

    def get_quality_bonus(self) -> float:
        """
        Return item quality bonus.

        Each Item Quality point adds 5% to output value/quality.
        Cap: +50% at 10 points.

        Returns:
            Quality multiplier (1.0–1.5).
        """
        quality = self.skill_manager.get_effective_stat("crafting", "item_quality")
        return 1.0 + min(0.5, quality * 0.05)

    def calculate_output_value(self, base_value: int) -> int:
        """
        Calculate final output value with quality bonus.

        Args:
            base_value: Base output quantity or value.

        Returns:
            Enhanced output value.
        """
        modifier = self.get_quality_bonus()
        return max(1, round(base_value * modifier))

    # ── Building Tech ────────────────────────────────────────────────

    def get_building_tech_level(self, tech_type: str) -> int:
        """
        Return the allocated points for a building tech stat.

        Delegates to skills.building_tech.

        Args:
            tech_type: One of the building tech stat names.

        Returns:
            Allocated points (0 if not found).
        """
        return get_building_tech_level(self.skill_manager, tech_type)

    def get_building_tech_bonus(self, tech_type: str) -> float:
        """
        Return the bonus multiplier for a building tech stat.

        Delegates to skills.building_tech.

        Formula: 1.0 + points * 0.10

        Each point adds 10% to the corresponding building category.

        Args:
            tech_type: One of the building tech stat names.

        Returns:
            Bonus multiplier (1.0–∞).
        """
        return get_building_tech_bonus(self.skill_manager, tech_type)

    def get_all_building_tech(self) -> Dict[str, float]:
        """
        Return all building tech bonuses.

        Delegates to skills.building_tech.

        Returns:
            Dict of tech_name → bonus multiplier.
        """
        return get_all_building_tech_bonuses(self.skill_manager)

    # ── Descriptor ───────────────────────────────────────────────────

    def get_description(self) -> str:
        """Return a human-readable summary of crafting benefits."""
        speed = self.skill_manager.get_effective_stat("crafting", "processing_speed")
        quality = self.skill_manager.get_effective_stat("crafting", "item_quality")
        parts = []
        if speed > 0:
            bonus = speed * 5
            parts.append(f"{bonus}% faster crafting")
        if quality > 0:
            bonus = min(50, quality * 5)
            parts.append(f"+{bonus}% item quality")
        for tech in BUILDING_TECH_STATS:
            points = self.get_building_tech_level(tech)
            if points > 0:
                name = BUILDING_TECH_NAMES[tech].replace(" ", "_")
                bonus = points * 10
                parts.append(f"+{bonus}% {name}")
        return " | ".join(parts) if parts else "No stat points allocated"
