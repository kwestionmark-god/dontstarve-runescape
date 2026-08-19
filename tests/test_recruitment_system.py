"""
tests/test_recruitment_system.py — Unit tests for RecruitmentSystem.

Covers:
- Commerce eligibility
- Persuasion eligibility
- Slot limit
- Guard, trader, assistant behavior initialization
- Dismiss
"""

import unittest
from unittest.mock import MagicMock, PropertyMock


class TestRecruitmentEligibilityCommerce(unittest.TestCase):
    """Recruitment eligibility checks commerce requirement."""

    def test_eligible_with_sufficient_commerce(self):
        """Commerce >= requirement → eligible."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()
        game.intelligence._sub_stats = {"commerce": 10, "persuasion": 5, "trade": 0}
        game.intelligence._levels = {"intelligence": 10}
        game.intelligence.get_effective_stat = lambda sid, sub: game.intelligence._sub_stats.get(sub, 0)
        game.intelligence.get_skill_level = lambda sid: game.intelligence._levels.get(sid, 1)

        class MockPlayer:
            recruited_npcs = []
            skill_manager = MagicMock()
            skill_manager.get_effective_stat = lambda sid, sub: game.intelligence._sub_stats.get(sub, 0)
            skill_manager.get_skill_level = lambda sid: game.intelligence._levels.get(sid, 1)

        rs = RecruitmentSystem(game)
        rs.intelligence_skill = game.intelligence

        class MockNPC:
            commerce_requirement = 5
            persuasion_requirement = 0
            composite_requirement = 0

        player = MockPlayer()
        result = game.intelligence.is_recruitment_eligible(MockNPC(), player)
        self.assertTrue(result.eligible)
        self.assertTrue(result.commerce_ok)

    def test_ineligible_without_sufficient_commerce(self):
        """Commerce < requirement → ineligible."""
        from skills.intelligence.intelligence import IntelligenceSkill

        class MockSkillManager:
            _sub_stats = {"commerce": 2, "persuasion": 0, "trade": 0}
            _levels = {"intelligence": 1}

            def get_effective_stat(self, sid, sub):
                return self._sub_stats.get(sub, 0)

            def get_skill_level(self, sid):
                return self._levels.get(sid, 1)

        sm = MockSkillManager()
        intel = IntelligenceSkill(sm)

        class MockNPC:
            commerce_requirement = 10
            persuasion_requirement = 0
            composite_requirement = 0

        class MockPlayer:
            recruited_npcs = []
            skill_manager = sm

        result = intel.is_recruitment_eligible(MockNPC(), MockPlayer())
        self.assertFalse(result.eligible)
        self.assertFalse(result.commerce_ok)


class TestRecruitmentEligibilityPersuasion(unittest.TestCase):
    """Recruitment eligibility checks persuasion requirement."""

    def test_eligible_with_sufficient_persuasion(self):
        """Persuasion >= requirement → eligible."""
        from skills.intelligence.intelligence import IntelligenceSkill

        class MockSkillManager:
            _sub_stats = {"commerce": 5, "persuasion": 10, "trade": 0}
            _levels = {"intelligence": 10}

            def get_effective_stat(self, sid, sub):
                return self._sub_stats.get(sub, 0)

            def get_skill_level(self, sid):
                return self._levels.get(sid, 1)

        sm = MockSkillManager()
        intel = IntelligenceSkill(sm)

        class MockNPC:
            commerce_requirement = 0
            persuasion_requirement = 5
            composite_requirement = 0

        class MockPlayer:
            recruited_npcs = []
            skill_manager = sm

        result = intel.is_recruitment_eligible(MockNPC(), MockPlayer())
        self.assertTrue(result.eligible)
        self.assertTrue(result.persuasion_ok)

    def test_ineligible_without_sufficient_persuasion(self):
        """Persuasion < requirement → ineligible."""
        from skills.intelligence.intelligence import IntelligenceSkill

        class MockSkillManager:
            _sub_stats = {"commerce": 0, "persuasion": 2, "trade": 0}
            _levels = {"intelligence": 1}

            def get_effective_stat(self, sid, sub):
                return self._sub_stats.get(sub, 0)

            def get_skill_level(self, sid):
                return self._levels.get(sid, 1)

        sm = MockSkillManager()
        intel = IntelligenceSkill(sm)

        class MockNPC:
            commerce_requirement = 0
            persuasion_requirement = 10
            composite_requirement = 0

        class MockPlayer:
            recruited_npcs = []
            skill_manager = sm

        result = intel.is_recruitment_eligible(MockNPC(), MockPlayer())
        self.assertFalse(result.eligible)
        self.assertFalse(result.persuasion_ok)


class TestRecruitmentSlotLimit(unittest.TestCase):
    """Slot limit formula."""

    def test_max_recruits_formula(self):
        """max(1, intel_level // 5 + 1)."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()
        class MockIntel:
            def get_max_recruits(self):
                # Formula: max(1, level // 5 + 1)
                intel_level = 7  # Example level
                return max(1, intel_level // 5 + 1)

        game.intelligence = MockIntel()

        rs = RecruitmentSystem(game)

        max_slots = rs.get_max_recruits()
        self.assertEqual(max_slots, max(1, 7 // 5 + 1))  # max(1, 2) = 2
        self.assertEqual(max_slots, 2)

    def test_get_available_slots(self):
        """Available = max_recruits - used_slots."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()

        class MockIntel:
            def get_max_recruits(self):
                return 3

        class MockPlayer:
            recruited_npcs = ["npc_1", "npc_2"]  # 2 used

        game.intelligence = MockIntel()
        game.player = MockPlayer()
        game.npc_system = None

        rs = RecruitmentSystem(game)

        self.assertEqual(rs.get_max_recruits(), 3)
        self.assertEqual(rs.get_used_slots(), 2)
        self.assertEqual(rs.get_available_slots(), 1)
        self.assertTrue(rs.is_slot_available())

    def test_no_available_slots(self):
        """When slots are full, is_slot_available returns False."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()

        class MockIntel:
            def get_max_recruits(self):
                return 2

        class MockPlayer:
            recruited_npcs = ["npc_1", "npc_2"]  # Full

        game.intelligence = MockIntel()
        game.player = MockPlayer()
        game.npc_system = None

        rs = RecruitmentSystem(game)

        self.assertEqual(rs.get_available_slots(), 0)
        self.assertFalse(rs.is_slot_available())


class TestRecruitBehaviorGuard(unittest.TestCase):
    """Guard behavior state initialization."""

    def test_guard_initial_state(self):
        """Guard recruit initializes with patrol substate."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()
        game.world = MagicMock()
        game.world.spawn_x = 10
        game.world.spawn_y = 10
        game.intelligence = MagicMock()
        game.intelligence.get_max_recruits.return_value = 5

        rs = RecruitmentSystem(game)
        # Override base position
        rs.base_x = 672.0  # 10*64+32
        rs.base_y = 672.0

        # Mock game.npc_system so _find_npc can find the NPC
        mock_npc = MagicMock()
        mock_npc.npc_id = "guard_1"
        mock_npc.is_recruited = True

        game.npc_system = MagicMock()
        game.npc_system.npcs = [mock_npc]

        rs.on_recruit("guard_1", "guard")

        self.assertIn("guard_1", rs.behaviors)
        self.assertEqual(rs.behaviors["guard_1"]["substate"], "patrol")
        self.assertEqual(rs.behaviors["guard_1"]["trade_timer"], 0.0)


class TestRecruitBehaviorTrader(unittest.TestCase):
    """Trader behavior state initialization."""

    def test_trader_initial_state(self):
        """Trader recruit initializes with idle substate."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()
        game.world = MagicMock()
        game.world.spawn_x = 10
        game.world.spawn_y = 10
        game.intelligence = MagicMock()
        game.intelligence.get_max_recruits.return_value = 5

        rs = RecruitmentSystem(game)
        rs.base_x = 672.0
        rs.base_y = 672.0

        mock_npc = MagicMock()
        mock_npc.npc_id = "trader_1"
        mock_npc.is_recruited = True

        game.npc_system = MagicMock()
        game.npc_system.npcs = [mock_npc]

        rs.on_recruit("trader_1", "trader")

        self.assertIn("trader_1", rs.behaviors)
        self.assertEqual(rs.behaviors["trader_1"]["substate"], "idle")
        self.assertIn("trade_timer", rs.behaviors["trader_1"])


class TestRecruitBehaviorAssistant(unittest.TestCase):
    """Assistant behavior state initialization."""

    def test_assistant_initial_state(self):
        """Assistant recruit initializes with following substate."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()
        game.world = MagicMock()
        game.world.spawn_x = 10
        game.world.spawn_y = 10
        game.intelligence = MagicMock()
        game.intelligence.get_max_recruits.return_value = 5

        rs = RecruitmentSystem(game)
        rs.base_x = 672.0
        rs.base_y = 672.0

        mock_npc = MagicMock()
        mock_npc.npc_id = "assistant_1"
        mock_npc.is_recruited = True

        game.npc_system = MagicMock()
        game.npc_system.npcs = [mock_npc]

        rs.on_recruit("assistant_1", "assistant")

        self.assertIn("assistant_1", rs.behaviors)
        self.assertEqual(rs.behaviors["assistant_1"]["substate"], "following")


class TestRecruitDismiss(unittest.TestCase):
    """Recruit dismissal cleans up state."""

    def test_dismiss_removes_behavior(self):
        """on_dismiss removes behavior state."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()
        rs = RecruitmentSystem(game)
        rs._building_system = None  # Ensure building system is None to avoid errors

        # Set up a behavior
        rs.behaviors["npc_1"] = {
            "target": (100, 100),
            "substate": "patrol",
        }

        rs.on_dismiss("npc_1")

        self.assertNotIn("npc_1", rs.behaviors)

    def test_dismiss_nonexistent_npc(self):
        """on_dismiss on non-existent NPC is a no-op."""
        from npc.recruitment import RecruitmentSystem

        game = MagicMock()
        rs = RecruitmentSystem(game)

        # Should not raise
        rs.on_dismiss("nonexistent_npc")
        self.assertEqual(len(rs.behaviors), 0)


if __name__ == "__main__":
    unittest.main()
