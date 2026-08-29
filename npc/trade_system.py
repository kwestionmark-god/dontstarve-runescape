"""
trade_system.py — Core trade system for merchant NPC interactions.

Handles buying, selling, and bartering between the player and merchant NPCs.
Integrates with the IntelligenceSkill pricing formulas (commerce, trade, barter).

Phase 3, Step 6: Trade System Core.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from core.player import Player
    from npc.npc_types import MerchantItem

from npc.npc_types import MerchantNPC  # runtime import for isinstance()

# ── Module-level constants ──────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Faction-based price modifiers (multiplied by commerce/trade price)
FACTION_BUY_MODIFIERS = {
    "hostile": 1.15,    # 15% price markup
    "suspicious": 1.05, # 5% price markup
    "neutral": 1.0,     # no change
    "friendly": 0.90,   # 10% discount
    "allied": 0.80,     # 20% discount
}

FACTION_SELL_MODIFIERS = {
    "hostile": 0.85,    # 15% reduced sell price
    "suspicious": 0.95, # 5% reduced sell price
    "neutral": 1.0,     # no change
    "friendly": 1.10,   # 10% enhanced sell price
    "allied": 1.20,     # 20% enhanced sell price
}


# ── Dataclasses ─────────────────────────────────────────────────────

@dataclass
class TradeSession:
    """Active trade interaction between player and merchant NPC."""

    merchant: "MerchantNPC"
    player: "Player"
    player_offer: dict[str, int] = field(default_factory=dict)
    merchant_offer: dict[str, int] = field(default_factory=dict)
    is_active: bool = False
    barter_mode: bool = False


@dataclass
class TradeResult:
    """Result of a buy or sell transaction."""

    success: bool
    item_id: str
    quantity: int
    gold_changed: int
    player_gold_before: int
    player_gold_after: int
    merchant_gold_before: int
    merchant_gold_after: int
    message: str


@dataclass
class BarterResult:
    """Result of an item-for-item barter transaction."""

    success: bool
    player_item_id: str
    player_item_quantity: int
    merchant_item_id: str
    merchant_item_quantity: int
    fair_value: int
    price_difference: int
    is_fair: bool
    message: str


# ── Trade System ────────────────────────────────────────────────────

class TradeSystem:
    """
    Core trade system managing buy/sell/barter transactions with merchants.

    Integrates with IntelligenceSkill pricing formulas for commerce (buy/sell)
    and trade (sell value enhancement, barter value enhancement).

    Fields:
        trade_items: All trade item definitions loaded from trade_items.json.
        active_session: Currently active trade session, or None.
        intelligence_skill: Reference to the IntelligenceSkill for pricing.
        tick_timer: Cooldown timer for restock checks.
    """

    PROXIMITY_THRESHOLD: float = 128.0
    BANKRUPT_RESTOCK_RATE: int = 10
    BARTER_FAIRNESS_TOLERANCE: float = 0.25
    TRADE_TICK_INTERVAL: float = 1.0

    __slots__ = (
        "trade_items",
        "active_session",
        "intelligence_skill",
        "tick_timer",
        "_npc_system",
        "_faction_system",
    )

    def __init__(self, intelligence_skill: "IntelligenceSkill") -> None:
        """
        Initialize the trade system.

        Args:
            intelligence_skill: Reference to the IntelligenceSkill for pricing.
        """
        self.intelligence_skill: "IntelligenceSkill" = intelligence_skill
        self.trade_items: List[MerchantItem] = []
        self.active_session: Optional[TradeSession] = None
        self.tick_timer: float = 0.0
        self._npc_system: Any = None
        self._faction_system: Any = None

    def set_npc_system(self, npc_system: Any) -> None:
        """
        Register a reference to NPCSystem for accessing all merchants.

        Required so that tick() can restock all bankrupt merchants,
        not just the one in the active trade session.

        Args:
            npc_system: The NPCSystem instance.
        """
        self._npc_system = npc_system

    def set_faction_system(self, faction_system: Any) -> None:
        """Register a reference to FactionSystem for faction-based pricing."""
        self._faction_system = faction_system

    def load_trade_data(self) -> None:
        """
        Load trade item definitions from trade_items.json.

        Parses the JSON data and creates MerchantItem objects.
        Called once during game initialization.
        """
        filepath = os.path.join(DATA_DIR, "trade_items.json")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            self.trade_items: list["MerchantItem"] = []
            return
        except json.JSONDecodeError:
            self.trade_items: list["MerchantItem"] = []
            return

        raw_items = data.get("trade_items", [])
        self.trade_items: list["MerchantItem"] = [
            self._make_merchant_item(item)
            for item in raw_items
        ]

    def open_trade(self, player: "Player", merchant: "MerchantNPC") -> Optional[TradeSession]:
        """
        Open a trade session with a merchant NPC.

        Checks proximity and returns a TradeSession if conditions are met.

        Args:
            player: The player entity.
            merchant: The merchant NPC to trade with.

        Returns:
            TradeSession if trade can be opened, None otherwise.
        """
        if not self.can_trade_with(player, merchant):
            return None

        if not isinstance(merchant, MerchantNPC):
            return None

        # B6: merchants are created with an empty inventory (see
        # MerchantNPC.from_dict), so generate a biome-filtered, stock-bearing
        # inventory before trading. Guarded by "already populated" so a merchant
        # that has already sold some stock is not refilled on every reopen.
        if not merchant.inventory:
            self.generate_merchant_inventory(merchant)

        session = TradeSession(
            merchant=merchant,
            player=player,
            is_active=True,
            barter_mode=False,
        )
        self.active_session = session
        return session

    def close_trade(self) -> bool:
        """
        Close the current active trade session.

        Returns:
            False if no active session was open, True otherwise.
        """
        if self.active_session is None or not self.active_session.is_active:
            return False

        self.active_session.is_active = False
        self.active_session = None
        return True

    def tick(self, dt: float) -> None:
        """
        Periodic trade system tick — manages bankrupt merchant restock timer.

        Checks for bankrupt merchants and restocks them on schedule.

        Args:
            dt: Delta time in seconds.
        """
        self.tick_timer += dt
        if self.tick_timer >= self.BANKRUPT_RESTOCK_RATE:
            self.tick_timer = 0.0
            # Restock all bankrupt merchants
            self._tick_all_merchants()

    def _tick_all_merchants(self) -> None:
        """Restock all merchants needing restock accessible via NPCSystem or active session."""
        # Priority: use NPCSystem's NPC registry if available
        if self._npc_system is not None:
            all_npcs = getattr(self._npc_system, "npcs", [])
            for npc in all_npcs:
                if isinstance(npc, MerchantNPC) and self.needs_restock(npc):
                    self.restock_merchant(npc)
            return

        # Fallback: only restock the active session merchant
        if self.active_session is not None and self.active_session.is_active:
            merchant = self.active_session.merchant
            if self.needs_restock(merchant):
                self.restock_merchant(merchant)

    def execute_buy(self, trade_item_id: str, quantity: int) -> TradeResult:
        """
        Player buys an item from the merchant.

        Uses IntelligenceSkill.calculate_buy_price() for pricing.
        Checks stock availability and gold sufficiency.

        Args:
            trade_item_id: The trade_item_id of the item to buy.
            quantity: Number of items to buy.

        Returns:
            TradeResult with transaction outcome.
        """
        if self.active_session is None or not self.active_session.is_active:
            return TradeResult(
                success=False,
                item_id=trade_item_id,
                quantity=quantity,
                gold_changed=0,
                player_gold_before=self.active_session.player.inventory.gold
                if self.active_session else 0,
                player_gold_after=0,
                merchant_gold_before=self.active_session.merchant.gold
                if self.active_session else 0,
                merchant_gold_after=0,
                message="No active trade session.",
            )

        session = self.active_session
        merchant = session.merchant
        player = session.player

        # Find the trade item
        trade_item = self._find_trade_item(trade_item_id)
        if trade_item is None:
            return TradeResult(
                success=False,
                item_id=trade_item_id,
                quantity=quantity,
                gold_changed=0,
                player_gold_before=player.inventory.gold,
                player_gold_after=player.inventory.gold,
                merchant_gold_before=merchant.gold,
                merchant_gold_after=merchant.gold,
                message=f"Trade item '{trade_item_id}' not found.",
            )

        # Check stock
        current_stock = self._get_stock_for_merchant(merchant, trade_item_id)
        if current_stock <= 0:
            return TradeResult(
                success=False,
                item_id=trade_item_id,
                quantity=0,
                gold_changed=0,
                player_gold_before=player.inventory.gold,
                player_gold_after=player.inventory.gold,
                merchant_gold_before=merchant.gold,
                merchant_gold_after=merchant.gold,
                message=f"No stock remaining for '{trade_item_id}'.",
            )
        if current_stock < quantity:
            quantity = current_stock  # Truncate to available stock

        # Check player gold
        base_price = trade_item.buy_price
        commerce_price = self.intelligence_skill.calculate_buy_price(base_price)
        faction_buy_modifier = self.get_faction_buy_modifier(merchant)
        buy_price = max(1, int(round(commerce_price * faction_buy_modifier)))
        total_cost = buy_price * quantity

        player_gold_before = player.inventory.gold
        merchant_gold_before = merchant.gold

        if player_gold_before < total_cost:
            # Try buying as much as possible
            affordable = player_gold_before // buy_price if buy_price > 0 else 0
            if affordable <= 0:
                return TradeResult(
                    success=False,
                    item_id=trade_item_id,
                    quantity=0,
                    gold_changed=0,
                    player_gold_before=player_gold_before,
                    player_gold_after=player_gold_before,
                    merchant_gold_before=merchant_gold_before,
                    merchant_gold_after=merchant_gold_before,
                    message=f"Not enough gold. Need {total_cost}, have {player_gold_before}.",
                )
            quantity = affordable

        # Execute transaction
        player.inventory.gold -= total_cost
        merchant.gold += total_cost

        # Add item to player inventory
        if not player.inventory.add_item(trade_item.item_id, quantity):
            # Inventory full — refund
            player.inventory.gold += total_cost
            merchant.gold -= total_cost
            return TradeResult(
                success=False,
                item_id=trade_item_id,
                quantity=0,
                gold_changed=0,
                player_gold_before=player_gold_before,
                player_gold_after=player_gold_before,
                merchant_gold_before=merchant_gold_before,
                merchant_gold_after=merchant_gold_before,
                message="Inventory full — item not added.",
            )

        # Reduce merchant stock
        self._set_stock_for_merchant(merchant, trade_item_id, current_stock - quantity)

        return TradeResult(
            success=True,
            item_id=trade_item.item_id,
            quantity=quantity,
            gold_changed=total_cost,
            player_gold_before=player_gold_before,
            player_gold_after=player.inventory.gold,
            merchant_gold_before=merchant_gold_before,
            merchant_gold_after=merchant.gold,
            message=f"Bought {quantity}x {trade_item.item_id} for {total_cost} gold.",
        )

    def execute_sell(self, item_id: str, quantity: int) -> TradeResult:
        """
        Player sells an item to the merchant.

        Uses IntelligenceSkill.calculate_sell_price_with_trade() for pricing.
        Checks player inventory for the item.

        Args:
            item_id: The item_id to sell.
            quantity: Number of items to sell.

        Returns:
            TradeResult with transaction outcome.
        """
        if self.active_session is None or not self.active_session.is_active:
            return TradeResult(
                success=False,
                item_id=item_id,
                quantity=quantity,
                gold_changed=0,
                player_gold_before=self.active_session.player.inventory.gold
                if self.active_session else 0,
                player_gold_after=0,
                merchant_gold_before=self.active_session.merchant.gold
                if self.active_session else 0,
                merchant_gold_after=0,
                message="No active trade session.",
            )

        session = self.active_session
        merchant = session.merchant
        player = session.player

        # Check player has the item
        if not player.inventory.has_items(item_id, quantity):
            available = player.inventory.get_item_quantity(item_id)
            if available <= 0:
                return TradeResult(
                    success=False,
                    item_id=item_id,
                    quantity=0,
                    gold_changed=0,
                    player_gold_before=player.inventory.gold,
                    player_gold_after=player.inventory.gold,
                    merchant_gold_before=merchant.gold,
                    merchant_gold_after=merchant.gold,
                    message=f"You don't have any '{item_id}'.",
                )
            quantity = available

        # Find the trade item to get base price
        trade_item = self._find_trade_item_by_item_id(item_id)
        if trade_item is None:
            return TradeResult(
                success=False,
                item_id=item_id,
                quantity=quantity,
                gold_changed=0,
                player_gold_before=player.inventory.gold,
                player_gold_after=player.inventory.gold,
                merchant_gold_before=merchant.gold,
                merchant_gold_after=merchant.gold,
                message=f"No trade data for item '{item_id}'.",
            )

        # Calculate sell price with trade bonus
        base_price = trade_item.sell_price
        commerce_trade_price = self.intelligence_skill.calculate_sell_price_with_trade(base_price)
        faction_sell_modifier = self.get_faction_sell_modifier(merchant)
        sell_price = max(1, int(round(commerce_trade_price * faction_sell_modifier)))
        total_revenue = sell_price * quantity

        # Check merchant gold
        merchant_gold_before = merchant.gold
        if merchant_gold_before < total_revenue:
            # Sell what merchant can afford
            affordable = merchant_gold_before // sell_price if sell_price > 0 else 0
            if affordable <= 0:
                return TradeResult(
                    success=False,
                    item_id=item_id,
                    quantity=0,
                    gold_changed=0,
                    player_gold_before=player.inventory.gold,
                    player_gold_after=player.inventory.gold,
                    merchant_gold_before=merchant_gold_before,
                    merchant_gold_after=merchant_gold_before,
                    message=f"Merchant cannot afford this trade. Has {merchant_gold_before} gold.",
                )
            quantity = affordable

        # Execute transaction
        player.inventory.gold += total_revenue
        merchant.gold -= total_revenue
        player.inventory.remove_item(item_id, quantity)

        # Increase merchant stock
        self._increment_stock_for_merchant(merchant, trade_item.trade_item_id, quantity)

        return TradeResult(
            success=True,
            item_id=item_id,
            quantity=quantity,
            gold_changed=total_revenue,
            player_gold_before=player.inventory.gold - total_revenue,
            player_gold_after=player.inventory.gold,
            merchant_gold_before=merchant_gold_before,
            merchant_gold_after=merchant.gold,
            message=f"Sold {quantity}x {item_id} for {total_revenue} gold.",
        )

    def execute_barter(
        self,
        player_item_id: str,
        player_quantity: int,
        trade_item_id: str,
    ) -> BarterResult:
        """
        Execute an item-for-item barter transaction.

        Uses IntelligenceSkill.calculate_barter_value() for the player's item
        and compares against the merchant item's base buy price.

        Args:
            player_item_id: The item_id the player offers.
            player_quantity: Number of player items offered.
            trade_item_id: The trade_item_id the player wants from the merchant.

        Returns:
            BarterResult with transaction outcome.
        """
        if self.active_session is None or not self.active_session.is_active:
            return BarterResult(
                success=False,
                player_item_id=player_item_id,
                player_item_quantity=player_quantity,
                merchant_item_id=trade_item_id,
                merchant_item_quantity=0,
                fair_value=0,
                price_difference=0,
                is_fair=False,
                message="No active trade session.",
            )

        session = self.active_session
        merchant = session.merchant
        player = session.player

        # Find the trade item the player wants
        trade_item = self._find_trade_item(trade_item_id)
        if trade_item is None:
            return BarterResult(
                success=False,
                player_item_id=player_item_id,
                player_item_quantity=player_quantity,
                merchant_item_id=trade_item_id,
                merchant_item_quantity=0,
                fair_value=0,
                price_difference=0,
                is_fair=False,
                message=f"Trade item '{trade_item_id}' not found.",
            )

        # Check player has the item
        if not player.inventory.has_items(player_item_id, player_quantity):
            return BarterResult(
                success=False,
                player_item_id=player_item_id,
                player_item_quantity=player_quantity,
                merchant_item_id=trade_item_id,
                merchant_item_quantity=0,
                fair_value=0,
                price_difference=0,
                is_fair=False,
                message=f"You don't have any '{player_item_id}'.",
            )

        # Check merchant stock
        merchant_stock = self._get_stock_for_merchant(merchant, trade_item_id)
        if merchant_stock <= 0:
            return BarterResult(
                success=False,
                player_item_id=player_item_id,
                player_item_quantity=player_quantity,
                merchant_item_id=trade_item_id,
                merchant_item_quantity=0,
                fair_value=0,
                price_difference=0,
                is_fair=False,
                message=f"No stock remaining for '{trade_item_id}'.",
            )

        # Calculate barter values
        # Look up player's offered item from items.json via data/items.json
        player_item_base_price = self._get_item_base_price(player_item_id)
        if player_item_base_price is None:
            return BarterResult(
                success=False,
                player_item_id=player_item_id,
                player_item_quantity=player_quantity,
                merchant_item_id=trade_item.item_id,
                merchant_item_quantity=0,
                fair_value=0,
                price_difference=0,
                is_fair=False,
                message=f"Unknown item '{player_item_id}' — cannot calculate barter value.",
            )
        barter_value = self.intelligence_skill.calculate_barter_value(player_item_base_price)
        merchant_offer_base_price = trade_item.buy_price

        # Determine fairness — apply faction modifier to merchant's effective price
        faction_buy_modifier = self.get_faction_buy_modifier(merchant)
        effective_merchant_price = max(1, int(round(merchant_offer_base_price * faction_buy_modifier)))
        price_difference = abs(barter_value - effective_merchant_price)
        tolerance = effective_merchant_price * self.BARTER_FAIRNESS_TOLERANCE
        is_fair = price_difference <= tolerance

        if not is_fair:
            return BarterResult(
                success=False,
                player_item_id=player_item_id,
                player_item_quantity=player_quantity,
                merchant_item_id=trade_item_id,
                merchant_item_quantity=0,
                fair_value=barter_value,
                price_difference=price_difference,
                is_fair=False,
                message=f"Barter is not fair. Your offer valued at {barter_value}, "
                        f"merchant wants {effective_merchant_price}. "
                        f"Tolerance: {int(tolerance)}.",
            )

        # Execute barter — give player item, remove from merchant stock, give trade item to player
        player.inventory.remove_item(player_item_id, player_quantity)
        # Fair barter: both sides exchange the same quantity
        give_quantity = min(player_quantity, merchant_stock)
        player.inventory.add_item(trade_item.item_id, give_quantity)
        self._set_stock_for_merchant(merchant, trade_item_id, merchant_stock - give_quantity)

        return BarterResult(
            success=True,
            player_item_id=player_item_id,
            player_item_quantity=player_quantity,
            merchant_item_id=trade_item.item_id,
            merchant_item_quantity=give_quantity,
            fair_value=barter_value,
            price_difference=price_difference,
            is_fair=True,
            message=f"Fair barter! Traded {player_quantity}x {player_item_id} for {give_quantity}x {trade_item.item_id}.",
        )

    def get_trade_items_for_merchant(self, merchant: "MerchantNPC") -> List[MerchantItem]:
        """
        Get trade items filtered by the merchant's biome.

        Args:
            merchant: The merchant NPC to filter items for.

        Returns:
            List of MerchantItem objects matching the merchant's biome.
        """
        biome = self._extract_biome_from_npc_id(merchant.npc_id)
        if not biome:
            return list(self.trade_items)

        return [
            item for item in self.trade_items
            if item.biome == biome
        ]

    def generate_merchant_inventory(self, merchant: "MerchantNPC") -> List[MerchantItem]:
        """
        Create initial inventory for a merchant based on their biome.

        Args:
            merchant: The merchant NPC to generate inventory for.

        Returns:
            List of MerchantItem objects for the merchant's inventory.
        """
        biome_items = self.get_trade_items_for_merchant(merchant)

        # Apply intelligence-based inventory bonus
        inventory_bonus = self.intelligence_skill.get_merchant_inventory_bonus()
        limit = min(inventory_bonus, len(biome_items), merchant.inventory_capacity)

        inventory = []
        for item in biome_items[:limit]:
            # Copy with fresh stock quantities
            inventory.append(
                self._make_merchant_item({
                    "trade_item_id": item.trade_item_id,
                    "item_id": item.item_id,
                    "buy_price": item.buy_price,
                    "sell_price": item.sell_price,
                    "stock_quantity": item.stock_quantity,
                    "max_stock": item.max_stock,
                    "tier": item.tier,
                    "is_premium": item.is_premium,
                    "commerce_requirement": item.commerce_requirement,
                    "biome": item.biome,
                })
            )

        merchant.inventory = inventory
        return list(inventory)

    def restock_merchant(self, merchant: "MerchantNPC") -> None:
        """
        Refill stock quantities for a merchant's inventory.

        Restocks items that have been sold down, up to their max_stock.
        Triggered when merchant is bankrupt (gold <= 0) OR when any item has empty stock.

        Args:
            merchant: The merchant NPC to restock.
        """
        for item in merchant.inventory:
            if item.stock_quantity < item.max_stock:
                item.stock_quantity = item.max_stock

    def needs_restock(self, merchant: "MerchantNPC") -> bool:
        """
        Check if a merchant needs restocking.

        Restock triggers when:
        - Merchant is bankrupt (gold <= 0), OR
        - Any item has empty stock (stock_quantity == 0)

        Args:
            merchant: The merchant NPC to check.

        Returns:
            True if restock is needed.
        """
        if merchant.gold <= 0:
            return True
        return any(item.stock_quantity == 0 for item in merchant.inventory)

    def update_merchant_gold(self, merchant: "MerchantNPC", gold_change: int) -> None:
        """
        Update a merchant's gold reserves and check for restock need.

        Args:
            merchant: The merchant NPC to update.
            gold_change: Amount to add (positive) or subtract (negative).
        """
        merchant.gold += gold_change
        if self.needs_restock(merchant):
            # Merchant needs restock (bankrupt or empty stock) — restock items
            self.restock_merchant(merchant)

    def is_merchant_bankrupt(self, merchant: "MerchantNPC") -> bool:
        """
        Check if a merchant has run out of gold.

        Args:
            merchant: The merchant NPC to check.

        Returns:
            True if merchant gold <= 0.
        """
        return merchant.gold <= 0

    def can_trade_with(self, player: "Player", merchant: "MerchantNPC") -> bool:
        """
        Check if the player can trade with a merchant.

        Checks proximity and commerce requirements.

        Args:
            player: The player entity.
            merchant: The merchant NPC to check.

        Returns:
            True if trade conditions are met.
        """
        # Check proximity
        distance = player.distance_to(merchant.world_x, merchant.world_y)
        if distance > self.PROXIMITY_THRESHOLD:
            return False

        # Check commerce requirement
        if merchant.commerce_requirement > 0:
            commerce = self.intelligence_skill.skill_manager.get_effective_stat(
                "intelligence", "commerce",
            )
            if commerce < merchant.commerce_requirement:
                return False

        return True

    # ── Faction Pricing ──────────────────────────────────────────────

    def _get_merchant_faction(self, merchant: "MerchantNPC") -> Optional[str]:
        """Get the faction ID of a merchant NPC, or None if unaffiliated."""
        return getattr(merchant, 'faction', None)

    def get_faction_buy_modifier(self, merchant: "MerchantNPC") -> float:
        """Get the faction-based buy price modifier for a merchant.

        Returns 1.0 for unaffiliated merchants or when FactionSystem is unavailable.
        """
        faction_id = self._get_merchant_faction(merchant)
        if faction_id is None:
            return 1.0
        if self._faction_system is None:
            return 1.0
        status = self._faction_system.get_status(faction_id)
        return FACTION_BUY_MODIFIERS.get(status, 1.0)

    def get_faction_sell_modifier(self, merchant: "MerchantNPC") -> float:
        """Get the faction-based sell price modifier for a merchant.

        Returns 1.0 for unaffiliated merchants or when FactionSystem is unavailable.
        """
        faction_id = self._get_merchant_faction(merchant)
        if faction_id is None:
            return 1.0
        if self._faction_system is None:
            return 1.0
        status = self._faction_system.get_status(faction_id)
        return FACTION_SELL_MODIFIERS.get(status, 1.0)

    # ── Internal Helpers ──────────────────────────────────────────

    def _get_item_base_price(self, item_id: str) -> Optional[int]:
        """
        Look up the base price of an item for barter valuation.

        Prices only exist in trade_items.json (items.json carries no price
        fields), so the canonical price for an arbitrary player item is the
        trade-item entry with a matching ``item_id``. Returns None when there
        is no trade data for the requested item.

        Args:
            item_id: The item_id to look up.

        Returns:
            Base buy price as int, or None if not found.
        """
        trade_item = self._find_trade_item_by_item_id(item_id)
        if trade_item is None:
            return None
        return trade_item.buy_price

    def _make_merchant_item(self, raw: dict) -> "MerchantItem":
        """
        Construct a MerchantItem from raw JSON data.

        Uses the canonical MerchantItem from npc_types.

        Args:
            raw: Parsed dict from trade_items.json.

        Returns:
            MerchantItem instance.
        """
        from npc.npc_types import MerchantItem as _MerchantItem

        return _MerchantItem(
            trade_item_id=raw["trade_item_id"],
            item_id=raw["item_id"],
            buy_price=raw["buy_price"],
            sell_price=raw["sell_price"],
            stock_quantity=raw["stock_quantity"],
            max_stock=raw["max_stock"],
            tier=raw.get("tier", 1),
            is_premium=raw.get("is_premium", False),
            commerce_requirement=raw.get("commerce_requirement", 0),
            biome=raw.get("biome", ""),
        )

    def _find_trade_item(self, trade_item_id: str) -> Optional[MerchantItem]:
        """Find a trade item by its trade_item_id."""
        for item in self.trade_items:
            if item.trade_item_id == trade_item_id:
                return item
        return None

    def _find_trade_item_by_item_id(self, item_id: str) -> Optional[MerchantItem]:
        """Find a trade item by its item_id.

        If multiple items share the same item_id (e.g. across biomes),
        prefer the one matching the active session's biome.
        """
        if self.active_session is not None:
            preferred_biome = self._extract_biome_from_npc_id(
                self.active_session.merchant.npc_id,
            )
        else:
            preferred_biome = ""

        # First pass: prefer matching biome
        if preferred_biome:
            for item in self.trade_items:
                if item.item_id == item_id and item.biome == preferred_biome:
                    return item

        # Second pass: any match
        for item in self.trade_items:
            if item.item_id == item_id:
                return item

        return None

    def _extract_biome_from_npc_id(self, npc_id: str) -> str:
        """
        Extract biome from NPC ID.

        NPC IDs follow patterns like 'merchant_forest_1', 'merchant_plains_1'.
        Extracts biome using regex pattern matching.

        Args:
            npc_id: The NPC's ID string.

        Returns:
            Biome string (e.g., "forest", "plains"), or empty string.
        """
        import re
        match = re.match(r'merchant_(\w+)_\d+', npc_id)
        if match:
            return match.group(1)
        return ""

    def _get_stock_for_merchant(
        self, merchant: "MerchantNPC", trade_item_id: str,
    ) -> int:
        """
        Get current stock for a trade item in a merchant's inventory.

        Args:
            merchant: The merchant NPC.
            trade_item_id: The trade_item_id to query.

        Returns:
            Current stock quantity (0 if not found).
        """
        for item in merchant.inventory:
            if item.trade_item_id == trade_item_id:
                return item.stock_quantity
        return 0

    def _set_stock_for_merchant(
        self, merchant: "MerchantNPC", trade_item_id: str, quantity: int,
    ) -> None:
        """
        Set stock for a trade item in a merchant's inventory.

        Args:
            merchant: The merchant NPC.
            trade_item_id: The trade_item_id to update.
            quantity: New stock quantity.
        """
        for item in merchant.inventory:
            if item.trade_item_id == trade_item_id:
                item.stock_quantity = max(0, quantity)
                return

    def _increment_stock_for_merchant(
        self, merchant: "MerchantNPC", trade_item_id: str, increment: int,
    ) -> None:
        """
        Increment stock for a trade item in a merchant's inventory.

        Args:
            merchant: The merchant NPC.
            trade_item_id: The trade_item_id to update.
            increment: Amount to add.
        """
        for item in merchant.inventory:
            if item.trade_item_id == trade_item_id:
                item.stock_quantity = min(item.max_stock, item.stock_quantity + increment)
                return
