"""
tests/test_intelligence_skill.py — Unit tests for IntelligenceSkill.

Covers:
- Commerce: buy price discount, sell price bonus, merchant inventory bonus
- Persuasion: quest acceptance check math, negotiation impact, relationship bonus
- Trade: barter value multiplier
- Recruitment: eligibility checks, max recruits formula
"""

import unittest
from unittest.mock import MagicMock


class MockSkillManager:
    """Minimal SkillManager mock for testing IntelligenceSkill."""

    def __init__(self, sub_stats=None):
        if sub_stats is None:
            sub_stats = {"commerce": 0, "persuasion": 0, "trade": 0}
        self._sub_stats = sub_stats
        self._levels = {"intelligence": 1}

    def get_effective_stat(self, skill_id, sub_stat):
        return self._sub_stats.get(sub_stat, 0)

    def get_skill_level(self, skill_id):
        return self._levels.get(skill_id, 1)


class TestBuyPriceDiscount(unittest.TestCase):
    """Commerce reduces buy price."""

    def test_no_commerce_no_discount(self):
        """Commerce=0 → buy price unchanged."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 0})
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.calculate_buy_price(100), 100)

    def test_commerce_10_discount_20_percent(self):
        """Commerce=10 → -20% discount → buy price = 80."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 10})
        intel = IntelligenceSkill(sm)
        result = intel.calculate_buy_price(100)
        self.assertEqual(result, 80)

    def test_commerce_50_discount_capped_at_50_percent(self):
        """Commerce=50 → max 50% discount → buy price = 50 (not less)."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 50})
        intel = IntelligenceSkill(sm)
        result = intel.calculate_buy_price(100)
        self.assertEqual(result, 50)

    def test_buy_price_minimum_one(self):
        """Buy price minimum is always 1."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 50})
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.calculate_buy_price(1), 1)


class TestSellPriceBonus(unittest.TestCase):
    """Commerce increases sell price."""

    def test_sell_price_no_commerce(self):
        """Commerce=0 → sell price unchanged."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 0})
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.calculate_sell_price(100), 100)

    def test_sell_price_commerce_10(self):
        """Commerce=10 → +10% bonus → sell price = 110."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 10})
        intel = IntelligenceSkill(sm)
        result = intel.calculate_sell_price(100)
        self.assertEqual(result, 110)

    def test_sell_price_capped_at_100_percent_bonus(self):
        """Commerce=100 → max 100% bonus → sell price = 200."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 100})
        intel = IntelligenceSkill(sm)
        result = intel.calculate_sell_price(100)
        self.assertEqual(result, 200)


class TestTradeBarterMultiplier(unittest.TestCase):
    """Trade increases barter value."""

    def test_barter_value_no_trade(self):
        """Trade=0 → barter value equals base price."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"trade": 0})
        intel = IntelligenceSkill(sm)
        result = intel.calculate_barter_value(100)
        self.assertEqual(result, 100)

    def test_barter_value_with_trade_10(self):
        """Trade=10 → +30% barter bonus → value = 130."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"trade": 10})
        intel = IntelligenceSkill(sm)
        result = intel.calculate_barter_value(100)
        self.assertEqual(result, 130)

    def test_barter_value_with_trade_5(self):
        """Trade=5 → +15% barter bonus → value = 115."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"trade": 5})
        intel = IntelligenceSkill(sm)
        result = intel.calculate_barter_value(100)
        self.assertEqual(result, 115)


class TestQuestAcceptanceCalculation(unittest.TestCase):
    """Persuasion check math."""

    def test_high_persuasion_accepts_low_threshold(self):
        """Persuasion=20 with threshold=0.2 → should accept (bonus=0.4)."""
        from skills.intelligence.intelligence import IntelligenceSkill
        from dataclasses import dataclass

        @dataclass
        class MockQuest:
            acceptance_threshold = 0.2

        sm = MockSkillManager({"persuasion": 20})
        intel = IntelligenceSkill(sm)
        quest = MockQuest()
        player = MagicMock()

        # With persuasion=20, bonus = 20*0.02 = 0.4
        # effective_threshold = 0.2 - 0.4 + variance(-0.1 to 0.1) = -0.3 to -0.1
        # Since threshold <= 0.5, accepted = True
        results = [intel.check_quest_acceptance(quest, player).accepted for _ in range(50)]
        # With high persuasion, acceptance should be very likely
        self.assertTrue(sum(results) > 40, "High persuasion should accept most of the time")

    def test_low_persuasion_rejects_low_threshold(self):
        """Persuasion=0 with threshold=0.9 → should fail (no bonus, high threshold)."""
        from skills.intelligence.intelligence import IntelligenceSkill
        from dataclasses import dataclass

        @dataclass
        class MockQuest:
            acceptance_threshold = 0.9

        sm = MockSkillManager({"persuasion": 0})
        intel = IntelligenceSkill(sm)
        quest = MockQuest()
        player = MagicMock()

        results = [intel.check_quest_acceptance(quest, player).accepted for _ in range(50)]
        # With persuasion=0, effective_threshold = 0.9 + variance(-0.1 to 0.1) = 0.8 to 1.0
        # threshold > 0.5, accepted = False
        self.assertTrue(sum(results) < 10, "Low persuasion should reject high-threshold quests most of the time")

    def test_persuasion_bonus_in_result(self):
        """Persuasion=10 → persuasion_bonus should be 0.2."""
        from skills.intelligence.intelligence import IntelligenceSkill
        from dataclasses import dataclass

        @dataclass
        class MockQuest:
            acceptance_threshold = 0.5

        sm = MockSkillManager({"persuasion": 10})
        intel = IntelligenceSkill(sm)
        quest = MockQuest()
        player = MagicMock()
        result = intel.check_quest_acceptance(quest, player)
        self.assertEqual(result.persuasion_bonus, 0.2)


class TestMerchantInventoryBonus(unittest.TestCase):
    """Commerce adds merchant inventory slots."""

    def test_inventory_bonus_no_commerce(self):
        """Commerce=0 → 10 base slots."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 0})
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.get_merchant_inventory_bonus(), 10)

    def test_inventory_bonus_commerce_5(self):
        """Commerce=5 → 10 + 5*3 = 25 slots."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 5})
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.get_merchant_inventory_bonus(), 25)

    def test_inventory_bonus_commerce_10(self):
        """Commerce=10 → 10 + 10*3 = 40 slots."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 10})
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.get_merchant_inventory_bonus(), 40)


class TestRecruitmentEligibility(unittest.TestCase):
    """Recruitment eligibility checks."""

    def test_eligible_with_all_requirements_met(self):
        """Commerce, persuasion, composite, slots → eligible=True."""
        from skills.intelligence.intelligence import IntelligenceSkill

        class MockNPC:
            commerce_requirement = 2
            persuasion_requirement = 1
            composite_requirement = 5

        class MockPlayer:
            recruited_npcs = []
            skill_manager = MagicMock()
            skill_manager.get_effective_stat.side_effect = lambda sid, sub: (
                {"commerce": 5, "persuasion": 4}[sub] if sid == "intelligence" else 0
            )

        sm = MockSkillManager({"commerce": 5, "persuasion": 4})
        intel = IntelligenceSkill(sm)
        player = MockPlayer()
        result = intel.is_recruitment_eligible(MockNPC(), player)
        self.assertTrue(result.eligible)

    def test_eligible_fails_insufficient_commerce(self):
        """Commerce too low → eligible=False."""
        from skills.intelligence.intelligence import IntelligenceSkill

        class MockNPC:
            commerce_requirement = 10
            persuasion_requirement = 0
            composite_requirement = 0

        class MockPlayer:
            recruited_npcs = []
            skill_manager = MagicMock()

        sm = MockSkillManager({"commerce": 3, "persuasion": 0})
        intel = IntelligenceSkill(sm)
        player = MockPlayer()
        result = intel.is_recruitment_eligible(MockNPC(), player)
        self.assertFalse(result.eligible)
        self.assertFalse(result.commerce_ok)


class TestMaxRecruitsFormula(unittest.TestCase):
    """Max recruits = floor(Intel/5) + 1."""

    def test_max_recruits_level_1(self):
        """Intel level 1 → max(1, 1//5 + 1) = 1."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 0, "persuasion": 0, "trade": 0})
        sm._levels = {"intelligence": 1}
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.get_max_recruits(), 1)

    def test_max_recruits_level_5(self):
        """Intel level 5 → max(1, 5//5 + 1) = 2."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 0, "persuasion": 0, "trade": 0})
        sm._levels = {"intelligence": 5}
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.get_max_recruits(), 2)

    def test_max_recruits_level_10(self):
        """Intel level 10 → max(1, 10//5 + 1) = 3."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 0, "persuasion": 0, "trade": 0})
        sm._levels = {"intelligence": 10}
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.get_max_recruits(), 3)

    def test_max_recruits_level_15(self):
        """Intel level 15 → max(1, 15//5 + 1) = 4."""
        from skills.intelligence.intelligence import IntelligenceSkill
        sm = MockSkillManager({"commerce": 0, "persuasion": 0, "trade": 0})
        sm._levels = {"intelligence": 15}
        intel = IntelligenceSkill(sm)
        self.assertEqual(intel.get_max_recruits(), 4)


class TestNegotiationSuccessRate(unittest.TestCase):
    """Persuasion impacts negotiation success."""

    def _make_player(self, persuasion):
        """Helper to create a player mock with given persuasion."""
        from unittest.mock import MagicMock
        player = MagicMock()
        player.skill_manager.get_effective_stat.return_value = persuasion
        return player

    def test_high_persuasion_higher_success_chance(self):
        """High persuasion increases base_success_bonus → more success."""
        from npc.faction_system import FactionSystem

        # Fresh FactionSystem for high persuasion
        fs_high = FactionSystem({"factions": [{"faction_id": "test_faction", "name": "Test"}]})
        high_pers = self._make_player(15)
        high_results = [fs_high.negotiate(high_pers, "test_faction")["success"] for _ in range(200)]
        high_success = sum(high_results)

        # Fresh FactionSystem for zero persuasion
        fs_zero = FactionSystem({"factions": [{"faction_id": "test_faction", "name": "Test"}]})
        zero_pers = self._make_player(0)
        zero_results = [fs_zero.negotiate(zero_pers, "test_faction")["success"] for _ in range(200)]
        zero_success = sum(zero_results)

        self.assertGreater(high_success, zero_success,
                           f"High persuasion ({high_success}/200) should beat zero ({zero_success}/200)")


class TestRelationshipBonus(unittest.TestCase):
    """Persuasion bonus to relationship gain on negotiation."""

    def _make_player(self, persuasion):
        """Helper to create a player mock with given persuasion."""
        from unittest.mock import MagicMock
        player = MagicMock()
        player.skill_manager.get_effective_stat.return_value = persuasion
        return player

    def test_success_gains_relationship(self):
        """Successful negotiation increases standing."""
        from npc.faction_system import FactionSystem

        factions_data = {"factions": [{"faction_id": "test_faction", "name": "Test"}]}
        fs = FactionSystem(factions_data)

        high_pers = self._make_player(20)
        initial = fs.get_standing("test_faction")
        result = fs.negotiate(high_pers, "test_faction")

        if result["success"]:
            new = fs.get_standing("test_faction")
            self.assertGreaterEqual(new, initial,
                                    "Successful negotiation should increase or maintain standing")

    def test_delta_formula(self):
        """Delta = 0.05 + persuasion * 0.005 on success."""
        from npc.faction_system import FactionSystem

        factions_data = {"factions": [{"faction_id": "test_faction", "name": "Test"}]}
        fs = FactionSystem(factions_data)

        pers_10 = self._make_player(10)
        # Run multiple times to find a success case
        for _ in range(200):
            result = fs.negotiate(pers_10, "test_faction")
            if result["success"]:
                expected_delta = 0.05 + 10 * 0.005  # = 0.10
                self.assertAlmostEqual(result["delta"], expected_delta,
                                       places=3,
                                       msg="Delta should match formula on success")
                return
        self.fail("No successful negotiation found in 200 attempts")


if __name__ == "__main__":
    unittest.main()
