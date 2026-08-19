"""
mining.py — Mining skill logic.

Provides yield bonuses, stamina efficiency, and extra-ore chances
based on allocated sub-stats.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager


class MiningSkill:
    """Manages mining skill effects."""

    __slots__ = ("skill_manager",)

    def __init__(self, skill_manager: "SkillManager") -> None:
        self.skill_manager: SkillManager = skill_manager

    # ── Yield Bonus ──────────────────────────────────────────────────

    def calculate_yield(
        self, base_quantity: int, extra_resources_bonus: int = 0,
    ) -> int:
        """
        Calculate final ore yield after skill modifiers.

        Formula:
          base_quantity + extra_resources_bonus deterministic bonus
          + random extra ore (10% chance per extra_resources point, capped 50%)

        Args:
            base_quantity: Base yield from the resource node.
            extra_resources_bonus: Bonus from skill_manager (extra_resources).

        Returns:
            Final yield quantity.
        """
        extra_resources = self.skill_manager.get_effective_stat(
            "mining", "extra_resources"
        )
        yield_ = base_quantity + extra_resources_bonus

        # Random extra ore: 10% chance per extra_resources point, capped at 50%
        extra_chance = min(0.5, extra_resources * 0.10)
        if random.random() < extra_chance:
            yield_ += 1

        return yield_

    # ── Stamina Efficiency ───────────────────────────────────────────

    def get_stamina_cost_modifier(self) -> float:
        """
        Return stamina cost multiplier.

        Formula: max(0.5, 1.0 - stamina * 0.02)

        Each Stamina point reduces cost by 2%, down to a 50% floor.

        Returns:
            Multiplier (0.5–1.0). Lower is better.
        """
        stamina = self.skill_manager.get_effective_stat("mining", "stamina")
        return max(0.5, 1.0 - stamina * 0.02)

    def get_effective_stamina_cost(self, base_cost: float) -> float:
        """
        Return the adjusted stamina cost for a mining action.

        Args:
            base_cost: Base stamina cost from the action.

        Returns:
            Adjusted cost after stamina efficiency modifier.
        """
        return base_cost * self.get_stamina_cost_modifier()

    # ── Success Rate ─────────────────────────────────────────────────

    def get_success_rate_bonus(self) -> float:
        """
        Return success rate bonus in percentage points.

        Each Success Rate point adds 1.0% to the base 50% threshold.

        Returns:
            Bonus percentage points.
        """
        return self.skill_manager.get_effective_stat(
            "mining", "success_rate"
        ) * 1.0

    # ── Descriptor ───────────────────────────────────────────────────

    def get_description(self) -> str:
        """Return a human-readable summary of mining benefits."""
        extra = self.skill_manager.get_effective_stat("mining", "extra_resources")
        stamina = self.skill_manager.get_effective_stat("mining", "stamina")
        success = self.skill_manager.get_effective_stat("mining", "success_rate")
        parts = []
        if extra > 0:
            chance = min(50, extra * 10)
            parts.append(f"+{chance}% extra ore chance")
        if stamina > 0:
            reduction = stamina * 2
            parts.append(f"-{reduction}% stamina cost")
        if success > 0:
            parts.append(f"+{success}%% success rate")
        return " | ".join(parts) if parts else "No stat points allocated"
