"""
foraging.py — Foraging skill logic.

Provides bonuses for tool-less resource gathering (berries, herbs, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager


class ForagingSkill:
    """Manages foraging skill effects."""

    __slots__ = ("skill_manager",)

    def __init__(self, skill_manager: "SkillManager") -> None:
        self.skill_manager: SkillManager = skill_manager

    # ── Harvest Bonus ────────────────────────────────────────────────

    def get_harvest_bonus(self) -> float:
        """
        Return harvest quantity bonus multiplier.

        Formula: 1.0 + foraging_harvest * 0.05

        Each Harvest Boost point adds 5% extra yield.

        Returns:
            Yield multiplier (1.0–∞).
        """
        harvest = self.skill_manager.get_effective_stat("foraging", "harvest_boost")
        return 1.0 + harvest * 0.05

    def calculate_harvest(self, base_quantity: int) -> int:
        """
        Calculate final harvest quantity with foraging bonus.

        Args:
            base_quantity: Base output quantity.

        Returns:
            Enhanced output quantity.
        """
        modifier = self.get_harvest_bonus()
        return max(1, round(base_quantity * modifier))

    # ── Success Rate ─────────────────────────────────────────────────

    def get_success_rate(self) -> float:
        """
        Return success rate bonus.

        Formula: foraging_success_rate * 0.02

        Each Success Rate point adds 2% to success chance.

        Returns:
            Success rate bonus (0.0–1.0).
        """
        success = self.skill_manager.get_effective_stat("foraging", "success_rate")
        return success * 0.02

    # ── Stamina ──────────────────────────────────────────────────────

    def get_stamina_reduction(self) -> float:
        """
        Return stamina cost reduction.

        Formula: foraging_stamina * 0.10

        Each Stamina point reduces stamina cost by 10%.

        Returns:
            Reduction factor (0.0–1.0).
        """
        stamina = self.skill_manager.get_effective_stat("foraging", "stamina")
        return min(0.5, stamina * 0.10)

    # ── Descriptor ───────────────────────────────────────────────────

    def get_description(self) -> str:
        """Return a human-readable summary of foraging benefits."""
        harvest = self.skill_manager.get_effective_stat("foraging", "harvest_boost")
        success = self.skill_manager.get_effective_stat("foraging", "success_rate")
        stamina = self.skill_manager.get_effective_stat("foraging", "stamina")
        parts = []
        if harvest > 0:
            bonus = harvest * 5
            parts.append(f"+{bonus}% harvest yield")
        if success > 0:
            bonus = success * 2
            parts.append(f"+{bonus}% success rate")
        if stamina > 0:
            bonus = min(50, stamina * 10)
            parts.append(f"-{bonus}% stamina cost")
        return " | ".join(parts) if parts else "No stat points allocated"