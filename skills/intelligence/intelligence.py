"""
intelligence.py — Intelligence skill logic.

Handles commerce (buy/sell prices, merchant inventory),
persuasion (quest acceptance checks), and trade (bartering,
sell value enhancement).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager
    from core.player import Player


# ── Module-level constants ──────────────────────────────────────────

COMMERCE_BUY_MOD = 0.02          # -2% buy price per Commerce point
COMMERCE_SELL_MOD = 0.01         # +1% sell price per Commerce point
COMMERCE_INVENTORY_MOD = 3       # +3 merchant inventory items per Commerce point
PERSUASION_ACCEPTANCE_MOD = 0.02 # +2% quest acceptance per Persuasion point
TRADE_SELL_VALUE_MOD = 0.02      # +2% item sell value per Trade point
TRADE_BARTER_MOD = 0.03          # +3% barter rate per Trade point

# Impact descriptions for Intelligence sub-stats
COMMERCE_DESCRIPTION = "\u22122% buy / +1% sell"
PERSUASION_DESCRIPTION = "+2% quest acceptance"
TRADE_DESCRIPTION = "+3% barter / +2% sell value"


# ── Dataclasses ─────────────────────────────────────────────────────

@dataclass
class AcceptanceCheck:
    """Result of a quest acceptance persuasion check."""
    accepted: bool
    rate: float               # 0.0-1.0, higher = more likely to succeed
    persuasion_bonus: float
    message: str


@dataclass
class EligibilityResult:
    """Result of a recruitment eligibility check."""
    eligible: bool
    commerce_ok: bool
    persuasion_ok: bool
    slot_available: bool
    composite_ok: bool
    message: str


@dataclass
class BarterResult:
    """Result of a bartering attempt."""
    success: bool
    value: int
    message: str


# ── Intelligence Skill ──────────────────────────────────────────────

class IntelligenceSkill:
    """Manages commerce, persuasion, and trade sub-stat calculations."""

    __slots__ = ("skill_manager",)

    def __init__(self, skill_manager: SkillManager) -> None:
        self.skill_manager: SkillManager = skill_manager

    # ── Commerce Pricing ──────────────────────────────────────────

    def calculate_buy_price(self, base_price: int) -> int:
        """
        Calculate the discounted buy price based on Commerce stat.

        Args:
            base_price: Base price before commerce modifier.

        Returns:
            Discounted price (minimum 1).
        """
        commerce = self.skill_manager.get_effective_stat("intelligence", "commerce")
        modifier = -(commerce * COMMERCE_BUY_MOD)
        modifier = max(-0.50, modifier)  # Cap at 50% discount
        return max(1, round(base_price * (1 + modifier)))

    def calculate_sell_price(self, base_price: int) -> int:
        """
        Calculate the enhanced sell price based on Commerce stat.

        Args:
            base_price: Base price before commerce modifier.

        Returns:
            Enhanced price (minimum 1).
        """
        commerce = self.skill_manager.get_effective_stat("intelligence", "commerce")
        modifier = commerce * COMMERCE_SELL_MOD
        modifier = min(modifier, 1.0)  # Cap at 100% bonus
        return max(1, round(base_price * (1 + modifier)))

    def calculate_sell_price_with_trade(self, base_price: int) -> int:
        """
        Calculate sell price enhanced by both Commerce and Trade stats.

        Args:
            base_price: Base price before modifiers.

        Returns:
            Enhanced price (minimum 1).
        """
        trade = self.skill_manager.get_effective_stat("intelligence", "trade")
        trade_modifier = trade * TRADE_SELL_VALUE_MOD
        base_sell = self.calculate_sell_price(base_price)
        return max(1, round(base_sell * (1 + trade_modifier)))

    # ── Persuasion / Quest Acceptance ─────────────────────────────

    def check_quest_acceptance(self, quest, player) -> AcceptanceCheck:
        """
        Check whether a quest is accepted based on Persuasion stat.

        Args:
            quest: Quest object with an ``acceptance_threshold`` attribute (0.0-1.0).
            player: Player object (unused in formula, reserved for future checks).

        Returns:
            AcceptanceCheck with acceptance result and rate.
        """
        persuasion = self.skill_manager.get_effective_stat("intelligence", "persuasion")
        persuasion_bonus = persuasion * PERSUASION_ACCEPTANCE_MOD
        variance = random.uniform(-0.1, 0.1)
        effective_threshold = max(0.0, min(1.0, quest.acceptance_threshold - persuasion_bonus + variance))
        accepted = effective_threshold <= 0.5
        rate = 1.0 - effective_threshold
        message = self._generate_acceptance_message(accepted, effective_threshold)
        return AcceptanceCheck(
            accepted=accepted,
            rate=rate,
            persuasion_bonus=persuasion_bonus,
            message=message,
        )

    # ── Bartering ─────────────────────────────────────────────────

    def calculate_barter_value(self, player_item_base_price: int) -> int:
        """
        Calculate the enhanced barter value based on Trade stat.

        Args:
            player_item_base_price: Base price of the player's item.

        Returns:
            Enhanced barter value.
        """
        trade = self.skill_manager.get_effective_stat("intelligence", "trade")
        modifier = 1.0 + trade * TRADE_BARTER_MOD
        return round(player_item_base_price * modifier)

    def try_barter(
        self,
        player_item_base_price: int,
        merchant_offer_base_price: int,
    ) -> BarterResult:
        """
        Attempt a barter between a player item and a merchant offer.

        Args:
            player_item_base_price: Base price of the item offered by the player.
            merchant_offer_base_price: Base price of the item offered by the merchant.

        Returns:
            BarterResult indicating success and effective values.
        """
        fair_player_value = self.calculate_barter_value(player_item_base_price)

        success = fair_player_value >= merchant_offer_base_price
        message = (
            f"Fair barter value: {fair_player_value}. "
            + ("Trade accepted." if success else "Trade rejected.")
        )
        return BarterResult(success=success, value=fair_player_value, message=message)

    # ── Merchant Inventory ────────────────────────────────────────

    def get_merchant_inventory_bonus(self) -> int:
        """
        Return the bonus number of merchant inventory slots.

        Returns:
            Bonus inventory size = 10 + commerce * 3.
        """
        commerce = self.skill_manager.get_effective_stat("intelligence", "commerce")
        return 10 + commerce * COMMERCE_INVENTORY_MOD

    # ── NPC Recruitment ───────────────────────────────────────────

    def get_max_recruits(self) -> int:
        """
        Return the maximum number of NPCs the player can recruit.

        Formula: max(1, intelligence_level // 5 + 1).

        Returns:
            Maximum recruit count.
        """
        intel_level = self.skill_manager.get_skill_level("intelligence")
        return max(1, intel_level // 5 + 1)

    def is_recruitment_eligible(self, npc, player) -> EligibilityResult:
        """
        Check whether the player is eligible to recruit an NPC.

        Args:
            npc: NPC object with optional requirement attributes:
                 ``commerce_requirement`` / ``recruit_commerce_requirement``,
                 ``persuasion_requirement`` / ``recruit_persuasion_requirement``,
                 ``composite_requirement`` / ``recruit_composite_stat``.
            player: Player object (unused in formula, reserved for future checks).

        Returns:
            EligibilityResult with breakdown of which checks passed/failed.
        """
        commerce = self.skill_manager.get_effective_stat("intelligence", "commerce")
        persuasion = self.skill_manager.get_effective_stat("intelligence", "persuasion")

        commerce_ok = commerce >= getattr(
            npc, "commerce_requirement", getattr(npc, "recruit_commerce_requirement", 0)
        )
        persuasion_ok = persuasion >= getattr(
            npc, "persuasion_requirement", getattr(npc, "recruit_persuasion_requirement", 0)
        )
        composite_ok = (commerce + persuasion) >= getattr(
            npc, "composite_requirement", getattr(npc, "recruit_composite_stat", 0)
        )
        slot_available = self._get_available_recruit_slots(player) > 0
        eligible = commerce_ok and persuasion_ok and composite_ok and slot_available

        message = self._generate_recruitment_message(
            eligible, commerce_ok, persuasion_ok, composite_ok, slot_available,
        )
        return EligibilityResult(
            eligible=eligible,
            commerce_ok=commerce_ok,
            persuasion_ok=persuasion_ok,
            slot_available=slot_available,
            composite_ok=composite_ok,
            message=message,
        )

    # ── Internal Helpers ──────────────────────────────────────────

    def _get_available_recruit_slots(self, player=None):
        max_recruits = self.get_max_recruits()
        if player is None:
            return max_recruits
        recruited_count = len(getattr(player, "recruited_npcs", []))
        return max(0, max_recruits - recruited_count)

    def _generate_acceptance_message(self, accepted: bool, effective_threshold: float) -> str:
        """Generate a human-readable message for a quest acceptance check."""
        if accepted:
            return "Quest accepted successfully."
        shortfall = effective_threshold - 0.5
        return f"Persuasion check failed. Need {(shortfall * 100):.0f}% more persuasion."

    def _generate_recruitment_message(
        self,
        eligible: bool,
        commerce_ok: bool,
        persuasion_ok: bool,
        composite_ok: bool,
        slot_available: bool,
    ) -> str:
        """Generate a human-readable message for a recruitment eligibility check."""
        if eligible:
            return "You are eligible to recruit this NPC."
        reasons = []
        if not commerce_ok:
            reasons.append("Insufficient commerce")
        if not persuasion_ok:
            reasons.append("Insufficient persuasion")
        if not composite_ok:
            reasons.append("Insufficient composite stat")
        if not slot_available:
            reasons.append("No recruit slots available")
        return "Recruitment failed: " + "; ".join(reasons) + "."
