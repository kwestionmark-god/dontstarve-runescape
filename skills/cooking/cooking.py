"""
cooking.py — Cooking skill logic.

Provides nutrition bonuses, spoilage reduction, and success rate
modifiers for cooking actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager


class CookingSkill:
    """Manages cooking skill effects.

    V1 limitation (B13): the math here (nutrition bonus, spoilage reduction,
    success-rate modifier) is implemented but not yet wired into
    ``CraftingSystem.cook``. ``CookingSkill`` is instantiated by bootstrap but
    its methods are currently unreferenced from the cook flow. Wire it into
    ``cook`` when cooking progression is prioritized; the methods are stable
    and only need a call site.
    """

    __slots__ = ("skill_manager",)

    def __init__(self, skill_manager: "SkillManager") -> None:
        self.skill_manager: SkillManager = skill_manager

    # ── Nutrition Bonus ──────────────────────────────────────────────

    def calculate_nutrition(self, base_nutrition: float) -> float:
        """
        Calculate final nutrition value for cooked food.

        Formula: base_nutrition × (1 + nutrition * 0.10)

        Each Nutrition point adds 10% to food nutrition, capped at 300%.

        Args:
            base_nutrition: Base nutrition value from the food item.

        Returns:
            Enhanced nutrition value.
        """
        nutrition = self.skill_manager.get_effective_stat("cooking", "nutrition")
        modifier = min(3.0, nutrition * 0.10)  # Cap at +300%
        return base_nutrition * (1.0 + modifier)

    # ── Spoilage Reduction ───────────────────────────────────────────

    def get_spoilage_modifier(self) -> float:
        """
        Return spoilage time multiplier.

        Formula: max(0.2, 1.0 - spoilage_reduction * 0.05)

        Each Spoilage Reduction point reduces spoilage rate by 5%,
        down to a 20% floor (5× longer shelf life).

        Returns:
            Multiplier (0.2–1.0). Lower is better (slower spoilage).
        """
        spoilage = self.skill_manager.get_effective_stat(
            "cooking", "spoilage_reduction"
        )
        return max(0.2, 1.0 - spoilage * 0.05)

    def get_effective_spoilage_time(self, base_spoilage_time: float) -> float:
        """
        Return the adjusted spoilage timer for a cooked food item.

        Args:
            base_spoilage_time: Base spoilage time in seconds.

        Returns:
            Extended spoilage time after reduction modifier.
        """
        return base_spoilage_time / self.get_spoilage_modifier()

    # ── Success Rate ─────────────────────────────────────────────────

    def get_success_rate_bonus(self) -> float:
        """
        Return additional success rate bonus for cooking.

        Each Success Rate point adds 2.0% to the base 50% threshold.

        Returns:
            Bonus percentage points (to be added to the 50% base).
        """
        return self.skill_manager.get_effective_stat(
            "cooking", "success_rate"
        ) * 2.0

    # ── Descriptor ───────────────────────────────────────────────────

    def get_description(self) -> str:
        """Return a human-readable summary of cooking benefits."""
        nutrition = self.skill_manager.get_effective_stat("cooking", "nutrition")
        spoilage = self.skill_manager.get_effective_stat("cooking", "spoilage_reduction")
        success = self.skill_manager.get_effective_stat("cooking", "success_rate")
        parts = []
        if nutrition > 0:
            bonus = nutrition * 10
            parts.append(f"+{bonus}% food nutrition")
        if spoilage > 0:
            reduction = spoilage * 5
            parts.append(f"-{reduction}% spoilage rate")
        if success > 0:
            parts.append(f"+{success * 2:.0f}%% success rate")
        return " | ".join(parts) if parts else "No stat points allocated"
