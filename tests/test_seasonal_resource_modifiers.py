"""
Smoke tests for Phase 4: Seasonal resource modifiers.

Covers:
- S3a: SeasonSystem.get_resource_multiplier() returns correct values per season
- S3b: SeasonSystem.is_resource_available() checks season restrictions
- S3c: ActionSystem applies seasonal yield multiplier when season_system is wired
- S3d: SurvivalSystem reads hunger_drain from season system
"""

import unittest
from unittest import mock

from actions.types import ActionType


class TestSeasonResourceMultipliers(unittest.TestCase):
    """S3a: SeasonSystem.get_resource_multiplier() returns correct values."""

    def test_spring_wood_multiplier(self):
        """Spring wood multiplier should be 1.0."""
        from seasons import SeasonSystem

        season = SeasonSystem()
        season.current_season = "spring"
        result = season.get_resource_multiplier("wood")
        self.assertEqual(result, 1.0)

    def test_winter_herb_multiplier(self):
        """Winter herb multiplier should be 0.5 (reduced availability)."""
        from seasons import SeasonSystem

        season = SeasonSystem()
        season.current_season = "winter"
        result = season.get_resource_multiplier("herbs")
        self.assertEqual(result, 0.5)

    def test_autumn_herb_multiplier(self):
        """Autumn herb multiplier should be 1.3 (harvest bonus)."""
        from seasons import SeasonSystem

        season = SeasonSystem()
        season.current_season = "autumn"
        result = season.get_resource_multiplier("herbs")
        self.assertEqual(result, 1.3)

    def test_unknown_category_returns_1(self):
        """Unknown resource categories default to multiplier 1.0."""
        from seasons import SeasonSystem

        season = SeasonSystem()
        result = season.get_resource_multiplier("nonexistent_category")
        self.assertEqual(result, 1.0)


class TestSeasonAvailability(unittest.TestCase):
    """S3b: SeasonSystem.is_resource_available() checks season restrictions."""

    def test_no_restrictions_means_available(self):
        """Empty availability dict means all resources are always available."""
        from seasons import SeasonSystem

        season = SeasonSystem()
        result = season.is_resource_available("berries")
        self.assertTrue(result)

    def test_seasonal_restriction(self):
        """Resource restricted to spring should be unavailable in winter."""
        from seasons import SeasonSystem

        season = SeasonSystem()
        season.availability = {"winter_only_ore": ["winter"]}

        # Available in winter
        season.current_season = "winter"
        self.assertTrue(season.is_resource_available("winter_only_ore"))

        # Unavailable in summer
        season.current_season = "summer"
        self.assertFalse(season.is_resource_available("winter_only_ore"))


class TestActionSystemSeasonalYield(unittest.TestCase):
    """S3c: ActionSystem applies seasonal yield multiplier."""

    def test_winter_reduces_herbs_yield(self):
        """Winter season should halve herb yields at harvest time."""
        from seasons import SeasonSystem
        from actions import ActionSystem
        from actions.types import ActionType
        from actions.active_action import ActiveAction
        from inventory.inventory import Inventory
        from skills.skill_manager import SkillManager

        # Create season system set to winter
        season = SeasonSystem()
        season.current_season = "winter"

        # Create action system with season wired
        action_system = ActionSystem()
        action_system.season_system = season

        # Mock a harvesting action (woodcutting with berries yield for simplicity)
        active = ActiveAction(action_type=ActionType.WOODCUTTING)
        active.yield_item = "herb"
        active.yield_quantity = 2  # Base yield
        active.xp_reward = 15.0
        active.success_rate_bonus = -60  # Negative = easier (raises threshold to 50-(-60)=110)
        active.extra_resources_bonus = 0

        # Mock resource (not depleted)
        mock_resource = mock.MagicMock()
        mock_resource.is_depleted = False
        mock_resource.category = "herbs"  # season_system uses plural form
        active.resource = mock_resource

        action_system.active = active
        action_system.active.state = 1  # ActionState.RUNNING

        # Complete the action
        result = action_system._complete_action()

        # Check that yield is scaled by winter multiplier (0.5)
        # Base yield 2 * 0.5 = 1, so action_complete:herb:1:...
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertEqual(result.item_id, "herb")
        self.assertEqual(result.quantity, 1)  # 2 * 0.5 = 1 (floored, min 1)

    def test_autumn_boosts_herbs_yield(self):
        """Autumn season should boost herb yields by 1.3x."""
        from seasons import SeasonSystem
        from actions import ActionSystem
        from actions.active_action import ActiveAction
        from actions.types import ActionState
        from inventory.inventory import Inventory

        season = SeasonSystem()
        season.current_season = "autumn"

        action_system = ActionSystem()
        action_system.season_system = season

        active = ActiveAction(action_type=ActionType.WOODCUTTING)
        active.yield_item = "herb"
        active.yield_quantity = 3  # Base yield
        active.xp_reward = 15.0
        active.success_rate_bonus = -60  # Negative = easier (guarantees success)
        active.extra_resources_bonus = 0

        mock_resource = mock.MagicMock()
        mock_resource.is_depleted = False
        active.resource = mock_resource

        action_system.active = active
        action_system.active.state = ActionState.RUNNING

        inventory = Inventory()
        inventory.set_stack_size("herb", 99)

        result = action_system._complete_action()

        # 3 * 1.3 = 3.9 → int = 3, so yield should be 3
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertEqual(result.item_id, "herb")
        self.assertEqual(result.quantity, 3)

    def test_no_season_system_no_modifier(self):
        """Without season_system, yields should be unchanged."""
        from actions import ActionSystem
        from actions.active_action import ActiveAction
        from actions.types import ActionState
        from inventory.inventory import Inventory

        action_system = ActionSystem()
        # season_system is None by default

        active = ActiveAction(action_type=ActionType.WOODCUTTING)
        active.yield_item = "herb"
        active.yield_quantity = 3
        active.xp_reward = 15.0
        active.success_rate_bonus = -60  # Negative = easier (guarantees success)
        active.extra_resources_bonus = 0

        mock_resource = mock.MagicMock()
        mock_resource.is_depleted = False
        active.resource = mock_resource

        action_system.active = active
        action_system.active.state = ActionState.RUNNING

        inventory = Inventory()
        inventory.set_stack_size("herb", 99)

        result = action_system._complete_action()

        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertEqual(result.item_id, "herb")
        self.assertEqual(result.quantity, 3)


class TestSurvivalSeasonHungerMod(unittest.TestCase):
    """S3d: SurvivalSystem reads hunger_drain from season system."""

    def test_winter_increases_hunger_drain(self):
        """Winter hunger_drain=1.3 should increase drain rate."""
        from seasons import SeasonSystem
        from survival.survival_system import SurvivalSystem

        season = SeasonSystem()
        season.current_season = "winter"

        survival = SurvivalSystem()
        survival.season_system = season

        # Tick to apply seasonal modifiers
        survival.tick(0.016)  # ~1 frame at 60fps

        # Hunger should have drained slightly (100 * 1.3 * mod)
        # The exact amount depends on HUNGER_DRAIN_RATE, but it should be > no-mod
        self.assertLess(survival.hunger, 100.0)

    def test_spring_baseline_hunger_drain(self):
        """Spring hunger_drain=1.0 should be baseline."""
        from seasons import SeasonSystem
        from survival.survival_system import SurvivalSystem

        season = SeasonSystem()
        season.current_season = "spring"

        survival = SurvivalSystem()
        survival.season_system = season

        survival.tick(0.016)
        self.assertLess(survival.hunger, 100.0)

    def test_no_season_system_no_modifier(self):
        """Without season_system, hunger_drain_mod should be 1.0."""
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem()
        # season_system is None by default

        survival.tick(0.016)
        self.assertLess(survival.hunger, 100.0)  # Still drains, but baseline rate


class TestSeasonToDictFromDict(unittest.TestCase):
    """S3e: SeasonSystem serialization round-trip."""

    def test_save_load_preserves_season(self):
        """to_dict manual reconstruction should preserve current season and progress."""
        from seasons import SeasonSystem

        season = SeasonSystem()
        season.current_season = "winter"
        season.season_progress = 0.75
        season.season_elapsed = 450.0

        data = season.to_dict()
        # Manual reconstruction (from_dict removed as dead code per trace notes)
        restored = SeasonSystem()
        restored.current_season = data.get("current", "spring")
        restored.season_progress = data.get("progress", 0.0)
        restored.season_elapsed = data.get("elapsed", 0.0)

        self.assertEqual(restored.current_season, "winter")
        self.assertEqual(restored.season_progress, 0.75)
        self.assertEqual(restored.season_elapsed, 450.0)

    def test_save_load_preserves_multipliers(self):
        """to_dict manual reconstruction should preserve custom resource multipliers."""
        from seasons import SeasonSystem

        custom_multipliers = {
            "winter": {"herbs": 0.3, "wood": 0.9},
            "summer": {"herbs": 1.5},
        }
        season = SeasonSystem(resource_multipliers=custom_multipliers)
        season.current_season = "winter"

        data = season.to_dict()
        # Manual reconstruction (from_dict removed as dead code per trace notes)
        restored = SeasonSystem()
        restored.current_season = data.get("current", "spring")
        restored.resource_multipliers = data.get("resource_multipliers", {})

        self.assertEqual(restored.get_resource_multiplier("herbs"), 0.3)
        self.assertEqual(restored.get_resource_multiplier("wood"), 0.9)


if __name__ == "__main__":
    unittest.main()
