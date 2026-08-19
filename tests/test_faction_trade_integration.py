"""
test_faction_trade_integration.py — Tests for Faction × Trade integration.

Covers:
- Faction price modifier constants and lookup
- get_faction_buy_modifier() / get_faction_sell_modifier() with all statuses
- Full buy/sell flows with faction modifiers applied
- Edge cases: no faction, no FactionSystem wired, unexpected status
- execute_buy with hostile markup
- merchant_plains_1 (no faction) → no discount
"""

import unittest


# ── Helper: create a minimal MerchantNPC ──────────────────────────────


def _make_merchant(faction=None):
    """Create a minimal MerchantNPC for testing."""
    from npc.npc_types import MerchantNPC

    npc = MerchantNPC(
        npc_id=f"merchant_test_{faction if faction else 'unaffiliated'}",
        name="Test Merchant",
        npc_type="merchant",
        world_x=100.0,
        world_y=100.0,
        sprite_key="npc/merchant_male_0",
        faction=faction,
        dialogue_lines=["Hello"],
        behavior="trade",
        patrol_area=(80, 80, 120, 120),
        is_active=True,
        is_recruited=False,
        recruit_behavior=None,
        hostility_level=0.2,
        health=20.0,
        max_health=20.0,
        inventory=[],
        inventory_capacity=10,
        restock_timer=0.0,
        restock_interval=60.0,
        gold=1000,
        price_modifier=1.0,
        commerce_requirement=0,
    )
    return npc


class MockFactionSystem:
    """Minimal FactionSystem mock for testing."""

    def __init__(self, standings=None):
        """
        Args:
            standings: dict of faction_id → status_label string.
                       Valid: "hostile", "suspicious", "neutral", "friendly", "allied".
        """
        if standings is None:
            standings = {}
        self._standings = standings

    def get_status(self, faction_id):
        return self._standings.get(faction_id, "neutral")


class MockIntelligenceSkill:
    """Minimal IntelligenceSkill that returns base prices unchanged."""

    def calculate_buy_price(self, base_price):
        return base_price

    def calculate_sell_price(self, base_price):
        return base_price

    def calculate_sell_price_with_trade(self, base_price):
        return base_price

    def calculate_barter_value(self, player_item_base_price):
        return player_item_base_price

    def get_merchant_inventory_bonus(self):
        return 10


class TestFactionBuyModifier(unittest.TestCase):
    """Test get_faction_buy_modifier() with all faction statuses."""

    def test_get_faction_buy_modifier_no_faction(self):
        """merchant with faction=None → returns 1.0"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction=None)
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem())

        modifier = trade_system.get_faction_buy_modifier(merchant)
        self.assertEqual(modifier, 1.0)

    def test_get_faction_buy_modifier_neutral(self):
        """neutral → 1.0"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "neutral"}))

        modifier = trade_system.get_faction_buy_modifier(merchant)
        self.assertEqual(modifier, 1.0)

    def test_get_faction_buy_modifier_friendly(self):
        """friendly → 0.90"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "friendly"}))

        modifier = trade_system.get_faction_buy_modifier(merchant)
        self.assertEqual(modifier, 0.90)

    def test_get_faction_buy_modifier_allied(self):
        """allied → 0.80"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "allied"}))

        modifier = trade_system.get_faction_buy_modifier(merchant)
        self.assertEqual(modifier, 0.80)

    def test_get_faction_buy_modifier_hostile(self):
        """hostile → 1.15"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "hostile"}))

        modifier = trade_system.get_faction_buy_modifier(merchant)
        self.assertEqual(modifier, 1.15)

    def test_get_faction_buy_modifier_suspicious(self):
        """suspicious → 1.05"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "suspicious"}))

        modifier = trade_system.get_faction_buy_modifier(merchant)
        self.assertEqual(modifier, 1.05)


class TestFactionSellModifier(unittest.TestCase):
    """Test get_faction_sell_modifier() with all faction statuses."""

    def test_get_faction_sell_modifier_no_faction(self):
        """merchant with faction=None → returns 1.0"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction=None)
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem())

        modifier = trade_system.get_faction_sell_modifier(merchant)
        self.assertEqual(modifier, 1.0)

    def test_get_faction_sell_modifier_hostile(self):
        """hostile → 0.85"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "hostile"}))

        modifier = trade_system.get_faction_sell_modifier(merchant)
        self.assertEqual(modifier, 0.85)

    def test_get_faction_sell_modifier_friendly(self):
        """friendly → 1.10"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "friendly"}))

        modifier = trade_system.get_faction_sell_modifier(merchant)
        self.assertEqual(modifier, 1.10)

    def test_get_faction_sell_modifier_allied(self):
        """allied → 1.20"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "allied"}))

        modifier = trade_system.get_faction_sell_modifier(merchant)
        self.assertEqual(modifier, 1.20)

    def test_get_faction_sell_modifier_unknown_status(self):
        """Unexpected status → defaults to 1.0"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        trade_system.set_faction_system(MockFactionSystem({"test_faction": "unknown_status"}))

        modifier = trade_system.get_faction_sell_modifier(merchant)
        self.assertEqual(modifier, 1.0)


class TestFactionNoSystem(unittest.TestCase):
    """Test fallback when FactionSystem is not wired."""

    def test_buy_price_no_faction_system(self):
        """no FactionSystem wired → falls back to 1.0"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        # Do NOT call set_faction_system

        modifier = trade_system.get_faction_buy_modifier(merchant)
        self.assertEqual(modifier, 1.0)

    def test_sell_price_no_faction_system(self):
        """no FactionSystem wired → sell modifier falls back to 1.0"""
        from npc.trade_system import TradeSystem

        merchant = _make_merchant(faction="test_faction")
        trade_system = TradeSystem(MockIntelligenceSkill())
        # Do NOT call set_faction_system

        modifier = trade_system.get_faction_sell_modifier(merchant)
        self.assertEqual(modifier, 1.0)


def _make_test_trade_system(intelligence_skill, faction_system=None):
    """Create a testable TradeSystem subclass that overrides internal methods.

    Uses subclassing (not __slots__ instance assignment) to bypass __slots__
    on TradeSystem.
    """
    from npc.trade_system import TradeSystem

    class _TestTradeSystem(TradeSystem):
        """Subclass that overrides internal methods for testing."""
        _test_trade_item = None
        _test_stock = 10
        _test_sell_trade_item = None
        _test_increment_called = False

        def _find_trade_item(self, trade_item_id):
            return self._test_trade_item

        def _get_stock_for_merchant(self, merchant, trade_item_id):
            return self._test_stock

        def _find_trade_item_by_item_id(self, item_id):
            return self._test_sell_trade_item

        def _increment_stock_for_merchant(self, merchant, trade_item_id, increment):
            self._test_increment_called = True

    ts = _TestTradeSystem(intelligence_skill)
    if faction_system is not None:
        ts.set_faction_system(faction_system)
    return ts


class TestFullBuyFlow(unittest.TestCase):
    """Test full buy flow with Commerce + Allied faction discount."""

    def test_buy_price_with_faction_discount(self):
        """Full buy flow with Allied → 20% discount on top of commerce price."""
        from npc.trade_system import TradeSession
        from dataclasses import dataclass

        @dataclass
        class MockTradeItem:
            item_id: str = "herb"
            buy_price: int = 100

        @dataclass
        class MockInventory:
            gold: int = 5000

            def add_item(self, item_id, quantity):
                return True

        @dataclass
        class MockPlayer:
            inventory: MockInventory = None

            def __post_init__(self):
                if self.inventory is None:
                    self.inventory = MockInventory()

            def distance_to(self, x, y):
                return 0.0

        merchant = _make_merchant(faction="allied_faction")
        trade_system = _make_test_trade_system(
            MockIntelligenceSkill(),
            MockFactionSystem({"allied_faction": "allied"}),
        )

        player = MockPlayer()
        session = TradeSession(merchant=merchant, player=player, is_active=True)
        trade_system.active_session = session

        trade_system._test_trade_item = MockTradeItem(buy_price=100)

        result = trade_system.execute_buy("herb", 1)

        # Expected: base=100, commerce=100 (no commerce skill), faction=allied(0.80) → 80
        self.assertTrue(result.success)
        self.assertEqual(result.gold_changed, 80)  # 100 * 0.80 = 80


class TestFullSellFlow(unittest.TestCase):
    """Test full sell flow with Trade + Friendly faction enhancement."""

    def test_sell_price_with_faction_enhancement(self):
        """Full sell flow with Friendly → 10% enhanced sell price."""
        from npc.trade_system import TradeSession
        from dataclasses import dataclass

        @dataclass
        class MockTradeItem:
            trade_item_id: str = "herb_trade"
            item_id: str = "herb"
            sell_price: int = 100

        @dataclass
        class MockInventory:
            gold: int = 5000

            def add_item(self, item_id, quantity):
                return True

            def has_items(self, item_id, quantity):
                return True

            def get_item_quantity(self, item_id):
                return quantity

            def remove_item(self, item_id, quantity):
                return True

        @dataclass
        class MockPlayer:
            inventory: MockInventory = None

            def __post_init__(self):
                if self.inventory is None:
                    self.inventory = MockInventory()

            def distance_to(self, x, y):
                return 0.0

        merchant = _make_merchant(faction="friendly_faction")
        trade_system = _make_test_trade_system(
            MockIntelligenceSkill(),
            MockFactionSystem({"friendly_faction": "friendly"}),
        )

        player = MockPlayer()
        session = TradeSession(merchant=merchant, player=player, is_active=True)
        trade_system.active_session = session

        trade_system._test_sell_trade_item = MockTradeItem(sell_price=100)

        result = trade_system.execute_sell("herb", 1)

        # Expected: base=100, commerce_sell=100, trade=100, faction=friendly(1.10) → 110
        self.assertTrue(result.success)
        self.assertEqual(result.gold_changed, 110)  # 100 * 1.10 = 110
        self.assertTrue(trade_system._test_increment_called)


class TestExecuteBuyHostileMarkup(unittest.TestCase):
    """Test execute_buy with hostile faction → 15% increase."""

    def test_execute_buy_faction_hostile_markup(self):
        """hostile → 15% price increase on buy."""
        from npc.trade_system import TradeSession
        from dataclasses import dataclass

        @dataclass
        class MockTradeItem:
            item_id: str = "herb"
            buy_price: int = 100

        @dataclass
        class MockInventory:
            gold: int = 5000

            def add_item(self, item_id, quantity):
                return True

        @dataclass
        class MockPlayer:
            inventory: MockInventory = None

            def __post_init__(self):
                if self.inventory is None:
                    self.inventory = MockInventory()

            def distance_to(self, x, y):
                return 0.0

        merchant = _make_merchant(faction="hostile_faction")
        trade_system = _make_test_trade_system(
            MockIntelligenceSkill(),
            MockFactionSystem({"hostile_faction": "hostile"}),
        )

        player = MockPlayer()
        session = TradeSession(merchant=merchant, player=player, is_active=True)
        trade_system.active_session = session

        trade_system._test_trade_item = MockTradeItem(buy_price=100)

        result = trade_system.execute_buy("herb", 1)

        # Expected: base=100, commerce=100, faction=hostile(1.15) → 115
        self.assertTrue(result.success)
        self.assertEqual(result.gold_changed, 115)  # 100 * 1.15 = 115


class TestMerchantPlainsNoDiscount(unittest.TestCase):
    """Test merchant_plains_1 (no faction) → no discount."""

    def test_merchant_plains_no_discount(self):
        """merchant_plains_1 has faction=null → modifier is 1.0, no discount."""
        from npc.trade_system import TradeSession
        from dataclasses import dataclass

        @dataclass
        class MockTradeItem:
            item_id: str = "wheat"
            buy_price: int = 50

        @dataclass
        class MockInventory:
            gold: int = 5000

            def add_item(self, item_id, quantity):
                return True

        @dataclass
        class MockPlayer:
            inventory: MockInventory = None

            def __post_init__(self):
                if self.inventory is None:
                    self.inventory = MockInventory()

            def distance_to(self, x, y):
                return 0.0

        # Simulate merchant_plains_1 which has faction: null
        merchant = _make_merchant(faction=None)
        merchant.npc_id = "merchant_plains_1"
        trade_system = _make_test_trade_system(
            MockIntelligenceSkill(),
            MockFactionSystem(),
        )

        player = MockPlayer()
        session = TradeSession(merchant=merchant, player=player, is_active=True)
        trade_system.active_session = session

        trade_system._test_trade_item = MockTradeItem(buy_price=50)

        result = trade_system.execute_buy("wheat", 1)

        # Expected: base=50, commerce=50, faction=1.0 (no faction) → 50
        self.assertTrue(result.success)
        self.assertEqual(result.gold_changed, 50)  # 50 * 1.0 = 50


class TestMinimumPrice(unittest.TestCase):
    """Test that minimum price is always 1 (max(1, ...))."""

    def test_buy_price_minimum_one(self):
        """Even with extreme modifiers, buy price >= 1."""
        from npc.trade_system import TradeSession
        from dataclasses import dataclass

        @dataclass
        class MockTradeItem:
            item_id: str = "item"
            buy_price: int = 1

        @dataclass
        class MockInventory:
            gold: int = 100

            def add_item(self, item_id, quantity):
                return True

        @dataclass
        class MockPlayer:
            inventory: MockInventory = None

            def __post_init__(self):
                if self.inventory is None:
                    self.inventory = MockInventory()

            def distance_to(self, x, y):
                return 0.0

        merchant = _make_merchant(faction="hostile_faction")
        trade_system = _make_test_trade_system(
            MockIntelligenceSkill(),
            MockFactionSystem({"hostile_faction": "hostile"}),
        )

        player = MockPlayer()
        session = TradeSession(merchant=merchant, player=player, is_active=True)
        trade_system.active_session = session

        trade_system._test_trade_item = MockTradeItem(buy_price=1)

        result = trade_system.execute_buy("item", 1)

        # Expected: base=1, commerce=1, faction=hostile(1.15) → round(1.15) = 1
        self.assertTrue(result.success)
        self.assertEqual(result.gold_changed, 1)


if __name__ == "__main__":
    unittest.main()
