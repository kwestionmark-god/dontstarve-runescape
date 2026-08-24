"""
test_b6_merchant_stock_population.py — B6: merchant stock is populated on trade.

B6: `generate_merchant_inventory` existed but was never called, so every
MerchantNPC kept an empty inventory and `execute_buy` failed with "No stock
remaining". The fix populates the merchant's inventory in `open_trade` (guarded
so re-opens don't refill already-consumed stock).

This integration test exercises the REAL TradeSystem against real
data/trade_items.json (forest biome, "forest_healing_herbs"), verifying:
  - opening trade populates an empty inventory,
  - a buy reduces stock AND player gold,
  - a sell increases stock AND player gold,
  - restock refills stock to max_stock,
  - re-opening trade does NOT refill consumed stock (guards the regression
    where an unguarded regenerate would undo purchases).
"""

from npc.npc_types import MerchantNPC
from npc.trade_system import TradeSystem


class _MockIntelligenceSkill:
    """Returns base prices unchanged; generous inventory bonus."""

    def calculate_buy_price(self, base_price):
        return base_price

    def calculate_sell_price_with_trade(self, base_price):
        return base_price

    def get_merchant_inventory_bonus(self):
        return 99


class _FakeInventory:
    """Minimal inventory: always accepts items, tracks gold + quantities."""

    def __init__(self, gold=1000):
        self.gold = gold
        self._qty = {}

    def add_item(self, item_id, quantity):
        self._qty[item_id] = self._qty.get(item_id, 0) + quantity
        return True

    def has_items(self, item_id, quantity):
        return self._qty.get(item_id, 0) >= quantity

    def get_item_quantity(self, item_id):
        return self._qty.get(item_id, 0)

    def remove_item(self, item_id, quantity):
        self._qty[item_id] = self._qty.get(item_id, 0) - quantity


class _FakePlayer:
    def __init__(self, inventory):
        self.inventory = inventory

    def distance_to(self, x, y):
        return 0.0


def _merchant():
    # npc_id "merchant_forest_1" → biome "forest" (9 items in trade_items.json).
    # commerce_requirement 0 so can_trade_with skips the skill_manager lookup.
    return MerchantNPC(
        npc_id="merchant_forest_1",
        name="Forest Trader",
        npc_type="merchant",
        world_x=100.0,
        world_y=100.0,
        sprite_key="npc/merchant_forest",
        faction=None,
        dialogue_lines=["Welcome."],
        behavior="trade",
        patrol_area=(80, 80, 120, 120),
        is_active=True,
        is_recruited=False,
        recruit_behavior=None,
        hostility_level=0.0,
        health=100.0,
        max_health=100.0,
        inventory_capacity=10,
        restock_timer=0.0,
        restock_interval=60.0,
        gold=1000,
        price_modifier=1.0,
        commerce_requirement=0,
    )


def _system():
    ts = TradeSystem(_MockIntelligenceSkill())
    ts.load_trade_data()
    return ts


TRADE_ITEM = "forest_healing_herbs"
ITEM_ID = "healing_herbs"


def test_open_trade_populates_empty_inventory():
    ts = _system()
    merchant = _merchant()
    assert merchant.inventory == []  # from_dict stub

    player = _FakePlayer(_FakeInventory(gold=1000))
    session = ts.open_trade(player, merchant)

    assert session is not None
    assert len(merchant.inventory) > 0
    # All generated items are forest-biome definitions copied from trade_items.json.
    assert all(item.biome == "forest" for item in merchant.inventory)
    ids = {item.trade_item_id for item in merchant.inventory}
    assert TRADE_ITEM in ids


def test_buy_reduces_stock_and_gold():
    ts = _system()
    merchant = _merchant()
    player = _FakePlayer(_FakeInventory(gold=1000))

    session = ts.open_trade(player, merchant)
    before = ts._get_stock_for_merchant(merchant, TRADE_ITEM)
    gold_before = player.inventory.gold

    result = ts.execute_buy(TRADE_ITEM, 1)

    assert result.success is True
    assert ts._get_stock_for_merchant(merchant, TRADE_ITEM) == before - 1
    assert player.inventory.gold == gold_before - result.gold_changed
    assert result.gold_changed > 0
    # Item landed in the player's inventory.
    assert player.inventory.get_item_quantity(ITEM_ID) >= 1


def test_sell_increases_stock_and_gold():
    ts = _system()
    merchant = _merchant()
    player = _FakeInventory(gold=100)  # player gold
    player = _FakePlayer(player)

    session = ts.open_trade(player, merchant)
    ts.execute_buy(TRADE_ITEM, 1)          # get one in inventory
    stock_before = ts._get_stock_for_merchant(merchant, TRADE_ITEM)
    gold_before = player.inventory.gold

    result = ts.execute_sell(ITEM_ID, 1)

    assert result.success is True
    assert ts._get_stock_for_merchant(merchant, TRADE_ITEM) == stock_before + 1
    assert player.inventory.gold == gold_before + result.gold_changed


def test_restock_refills_to_max_stock():
    ts = _system()
    merchant = _merchant()
    player = _FakePlayer(_FakeInventory(gold=1000))

    session = ts.open_trade(player, merchant)
    # Drain the stock to zero.
    for _ in range(50):
        if ts._get_stock_for_merchant(merchant, TRADE_ITEM) <= 0:
            break
        ts.execute_buy(TRADE_ITEM, 1)

    assert ts._get_stock_for_merchant(merchant, TRADE_ITEM) == 0

    ts.restock_merchant(merchant)
    max_stock = next(
        i.max_stock for i in merchant.inventory if i.trade_item_id == TRADE_ITEM
    )
    assert ts._get_stock_for_merchant(merchant, TRADE_ITEM) == max_stock


def test_reopen_does_not_refill_consumed_stock():
    """Guard check: a second open must not restore stock spent on the first."""
    ts = _system()
    merchant = _merchant()
    player = _FakePlayer(_FakeInventory(gold=1000))

    ts.open_trade(player, merchant)
    ts.execute_buy(TRADE_ITEM, 1)
    stock_after_first = ts._get_stock_for_merchant(merchant, TRADE_ITEM)
    assert stock_after_first > 0

    ts.open_trade(player, merchant)  # reopen the same merchant
    stock_after_reopen = ts._get_stock_for_merchant(merchant, TRADE_ITEM)

    assert stock_after_reopen == stock_after_first
