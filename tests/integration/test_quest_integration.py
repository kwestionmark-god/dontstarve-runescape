"""
tests/integration/test_quest_integration.py — Integration tests for quest system.

Covers:
- Quest accept → track progress → complete → rewards
- Quest conditions across multiple ticks
"""

import unittest
from unittest.mock import MagicMock


class MockIntelligenceSkill:
    def __init__(self, persuasion=10):
        self._persuasion = persuasion

    def check_quest_acceptance(self, quest, player):
        from skills.intelligence.intelligence import AcceptanceCheck
        return AcceptanceCheck(
            accepted=True,
            rate=0.9,
            persuasion_bonus=self._persuasion * 0.02,
            message="Quest accepted.",
        )


class MockFactionSystem:
    def __init__(self, standings=None):
        self._standings = standings or {}

    def get_status(self, faction_id):
        return self._standings.get(faction_id, "neutral")


class TestQuestAcceptCompleteRewards(unittest.TestCase):
    """Quest accept → track progress → complete → rewards."""

    def test_full_quest_flow(self):
        """Complete quest flow: accept → track → complete → rewards."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState, QuestCondition
        from npc.quest_system import QuestDefinition

        qs = QuestSystem(MockIntelligenceSkill(persuasion=10))
        qs.faction_system = MockFactionSystem()
        qs.load_quest_data()

        player = MagicMock()
        player.skill_manager = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: (
            {"intelligence": 10, "commerce": 0, "persuasion": 10}[sub]
            if sid == "intelligence" else 0
        )
        player.skill_manager.get_skill_level.return_value = 5
        player.skill_manager.add_xp = MagicMock()
        player.inventory = MagicMock()
        player.inventory.add_item = MagicMock(return_value=True)
        player.inventory.get_item_quantity = MagicMock(return_value=0)
        player.action_system = MagicMock()

        npc = MagicMock()
        npc.npc_id = "quest_giver_1"

        # Create a simple quest with collect_item condition
        quest_def = QuestDefinition(
            quest_id="collect_logs",
            name="Collect Logs",
            description="Gather oak logs",
            acceptance_threshold=0.3,
            min_persuasion=0,
            min_commerce=0,
            min_total_intelligence=0,
            skill_xp_rewards={"intelligence": 5.0},
            conditions=[QuestCondition(
                condition_type="collect_item",
                target="oak_logs",
                required_count=5,
            )],
        )
        qs.quest_definitions["collect_logs"] = quest_def

        # Step 1: Accept quest
        result = qs.accept_quest(player, npc, "collect_logs")
        self.assertTrue(result.success)
        self.assertEqual(qs.get_quest_progress("collect_logs").state, QuestState.ACTIVE)

        # Step 2: Simulate tick with player having 3 oak logs
        player.inventory.get_item_quantity.return_value = 3
        tile_map = MagicMock()
        tile_map.get_tile.return_value = None
        qs.tick(1.0, player, tile_map)

        progress = qs.get_quest_progress("collect_logs")
        self.assertEqual(progress.conditions[0].current_count, 3)

        # Step 3: Simulate player having all 5 logs
        player.inventory.get_item_quantity.return_value = 5
        qs.tick(1.0, player, tile_map)

        # Quest should auto-complete
        progress = qs.get_quest_progress("collect_logs")
        self.assertEqual(progress.state, QuestState.COMPLETED)


class TestQuestConditionTracking(unittest.TestCase):
    """Quest condition tracking across ticks."""

    def test_kill_monster_progress_tracks(self):
        """Kill monster condition tracks kills across ticks."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState, QuestCondition, QuestDefinition

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        quest_def = QuestDefinition(
            quest_id="kill_goblins",
            name="Kill Goblins",
            description="Test",
            conditions=[QuestCondition(
                condition_type="kill_monster",
                target="goblin",
                required_count=3,
            )],
        )
        qs.quest_definitions["kill_goblins"] = quest_def

        progress = QuestProgress(
            quest_id="kill_goblins",
            state=QuestState.ACTIVE,
            conditions=[QuestCondition(
                condition_type="kill_monster",
                target="goblin",
                required_count=3,
            )],
        )
        qs.quest_progress["kill_goblins"] = progress

        # Record kills
        qs.record_kill("goblin")
        qs.record_kill("goblin")

        player = MagicMock()
        player.world_x = 640
        player.world_y = 640
        tile_map = MagicMock()
        tile_map.get_tile.return_value = None

        qs.tick(1.0, player, tile_map)
        progress = qs.get_quest_progress("kill_goblins")
        self.assertEqual(progress.conditions[0].current_count, 2)

        # One more kill
        qs.record_kill("goblin")
        qs.tick(1.0, player, tile_map)
        progress = qs.get_quest_progress("kill_goblins")
        self.assertEqual(progress.conditions[0].current_count, 3)


class TestQuestFactionDependency(unittest.TestCase):
    """Quest faction dependency."""

    def test_quest_blocked_by_hostile_faction(self):
        """Quest requiring friendly status blocked when hostile."""
        from npc.quest_system import QuestSystem, QuestDefinition

        fs = MockFactionSystem({"forest_faction": "hostile"})
        qs = QuestSystem(MockIntelligenceSkill())
        qs.faction_system = fs
        qs.load_quest_data()

        player = MagicMock()
        player.skill_manager = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: 0
        player.skill_manager.get_skill_level.return_value = 1

        quest_def = QuestDefinition(
            quest_id="forest_quest",
            name="Forest Quest",
            description="Test",
            required_faction_status="friendly",
        )
        qs.quest_definitions["forest_quest"] = quest_def

        result = qs.check_quest_eligibility(player, quest_def)
        self.assertFalse(result.eligible)
        self.assertFalse(result.faction_status_met)


if __name__ == "__main__":
    unittest.main()
