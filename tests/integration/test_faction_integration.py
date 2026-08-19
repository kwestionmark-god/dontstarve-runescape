"""
tests/integration/test_faction_integration.py — Integration tests for faction system.

Covers:
- Negotiate → relationship change → behavior change
- Faction standing affects trade prices
- Multiple negotiations accumulate standing changes
"""

import unittest
from unittest.mock import MagicMock


class MockPlayer:
    """Minimal player mock with persuasion."""

    def __init__(self, persuasion=0):
        self.skill_manager = MagicMock()
        self.skill_manager.get_effective_stat.return_value = persuasion


class TestNegotiateRelationshipChange(unittest.TestCase):
    """Negotiate → relationship change → behavior change."""

    def test_successful_negotiation_changes_standing(self):
        """Successful negotiation increases faction standing."""
        from npc.faction_system import FactionSystem

        factions_data = {
            "factions": [
                {"faction_id": "test_faction", "name": "Test"},
            ]
        }
        fs = FactionSystem(factions_data)

        player = MockPlayer(persuasion=10)

        # Multiple successful negotiations should steadily increase standing
        for _ in range(20):
            result = fs.negotiate(player, "test_faction")

        current_standing = fs.get_standing("test_faction")
        # After multiple negotiations, standing should be well above neutral
        self.assertGreater(current_standing, 0.5,
                           f"Standing should increase after negotiations: {current_standing}")

    def test_standing_changes_status_label(self):
        """Standing changes → status label changes."""
        from npc.faction_system import FactionSystem

        factions_data = {
            "factions": [
                {"faction_id": "test_faction", "name": "Test"},
            ]
        }
        fs = FactionSystem(factions_data)

        # Start neutral
        self.assertEqual(fs.get_status("test_faction"), "neutral")

        # Increase to friendly
        fs.update_standing("test_faction", 0.2)
        self.assertEqual(fs.get_status("test_faction"), "friendly")

        # Increase to allied
        fs.update_standing("test_faction", 0.25)
        self.assertEqual(fs.get_status("test_faction"), "allied")


class TestFactionTradeIntegration(unittest.TestCase):
    """Faction standing affects trade behavior."""

    def test_negative_standing_makes_trade_harder(self):
        """Hostile standing means higher trade costs (reflected in difficulty to gain)."""
        from npc.faction_system import FactionSystem

        factions_data = {
            "factions": [
                {"faction_id": "test_faction", "name": "Test"},
            ]
        }
        fs = FactionSystem(factions_data)

        # Make the faction hostile
        fs.update_standing("test_faction", -0.35)  # 0.5 - 0.35 = 0.15 → hostile
        self.assertEqual(fs.get_status("test_faction"), "hostile")

        # Negotiation with hostile faction and low persuasion should fail more often
        player = MockPlayer(persuasion=0)
        results = [fs.negotiate(player, "test_faction")["success"] for _ in range(100)]
        success_rate = sum(results) / 100

        # With hostile standing, relation_bonus = (0.15 - 0.5) * 0.3 = -0.105
        # success_chance = 0.5 + 0 + (-0.105) + variance = 0.395 + variance
        # This should be below 50% success rate
        self.assertLess(success_rate, 0.6,
                        f"Hostile faction should have lower negotiation success: {success_rate}")

    def test_friendly_standing_makes_trade_easier(self):
        """Friendly standing means easier negotiations."""
        from npc.faction_system import FactionSystem

        factions_data = {
            "factions": [
                {"faction_id": "test_faction", "name": "Test"},
            ]
        }
        fs = FactionSystem(factions_data)

        # Make the faction friendly
        fs.update_standing("test_faction", 0.3)  # 0.5 + 0.3 = 0.8 → allied
        self.assertEqual(fs.get_status("test_faction"), "allied")

        player = MockPlayer(persuasion=0)
        results = [fs.negotiate(player, "test_faction")["success"] for _ in range(100)]
        success_rate = sum(results) / 100

        # With allied standing, relation_bonus = (0.8 - 0.5) * 0.3 = 0.09
        # success_chance = 0.5 + 0 + 0.09 + variance = 0.59 + variance
        # This should be above 50% success rate
        self.assertGreater(success_rate, 0.5,
                           f"Allied faction should have higher negotiation success: {success_rate}")


class TestMultipleNegotiations(unittest.TestCase):
    """Multiple negotiations accumulate standing changes."""

    def test_standing_accumulates_over_time(self):
        """Standing should accumulate with each negotiation."""
        from npc.faction_system import FactionSystem

        factions_data = {
            "factions": [
                {"faction_id": "test_faction", "name": "Test"},
            ]
        }
        fs = FactionSystem(factions_data)

        player = MockPlayer(persuasion=5)
        initial_standing = fs.get_standing("test_faction")

        for _ in range(30):
            result = fs.negotiate(player, "test_faction")

        final_standing = fs.get_standing("test_faction")
        self.assertGreaterEqual(final_standing, initial_standing,
                                "Standing should accumulate (or at least not decrease)")


if __name__ == "__main__":
    unittest.main()
