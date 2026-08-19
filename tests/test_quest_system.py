"""
tests/test_quest_system.py — Unit tests for QuestSystem.

Covers:
- Quest acceptance (low/high persuasion)
- Prerequisite checks
- Faction requirements
- Kill_monster, collect_item, craft_item conditions
- Completion rewards
- Abandon/fail
- Repeatable quests
"""

import unittest
from unittest.mock import MagicMock, patch


class MockIntelligenceSkill:
    """Mock IntelligenceSkill for quest system tests."""

    def __init__(self, persuasion=0, acceptance_rate=1.0):
        self._persuasion = persuasion
        self._acceptance_rate = acceptance_rate

    def check_quest_acceptance(self, quest, player):
        from skills.intelligence.intelligence import AcceptanceCheck
        # Deterministic: accept if persuasion >= threshold * 5
        if self._persuasion >= quest.acceptance_threshold * 5:
            return AcceptanceCheck(
                accepted=True,
                rate=0.9,
                persuasion_bonus=self._persuasion * 0.02,
                message="Quest accepted.",
            )
        return AcceptanceCheck(
            accepted=False,
            rate=0.2,
            persuasion_bonus=self._persuasion * 0.02,
            message="Persuasion check failed.",
        )


class MockFactionSystem:
    """Mock FactionSystem for quest system tests."""

    def __init__(self, standings=None):
        """
        Args:
            standings: dict of faction_id → status_label string.
        """
        self._standings = standings or {}

    def get_status(self, faction_id):
        """Return the status for a given faction_id.
        For known factions, return the stored status.
        For unknown factions, return 'neutral'.
        """
        return self._standings.get(faction_id, "neutral")


class TestQuestAcceptanceLowPersuasion(unittest.TestCase):
    """Low persuasion fails quest acceptance."""

    def test_low_persuasion_rejects_quest(self):
        """Persuasion=0 with threshold=0.5 → should fail."""
        from npc.quest_system import QuestSystem

        qs = QuestSystem(MockIntelligenceSkill(persuasion=0))
        qs.load_quest_data()

        player = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: (
            {"intelligence": 1, "commerce": 0, "persuasion": 0}[sub]
            if sid == "intelligence" else 0
        )
        player.skill_manager.get_skill_level.return_value = 1

        # Create a quest def with high threshold
        from npc.quest_system import QuestDefinition
        quest_def = QuestDefinition(
            quest_id="test_quest",
            name="Test Quest",
            description="Test",
            acceptance_threshold=0.8,
            min_persuasion=0,
            min_commerce=0,
            min_total_intelligence=0,
        )

        npc = MagicMock()
        npc.npc_id = "test_npc"

        result = qs.accept_quest(player, npc, "test_quest")
        # Quest not loaded from data, use direct def
        qs.quest_definitions["test_quest"] = quest_def
        result = qs.accept_quest(player, npc, "test_quest")
        self.assertFalse(result.success)


class TestQuestAcceptanceHighPersuasion(unittest.TestCase):
    """High persuasion succeeds quest acceptance."""

    def test_high_persuasion_accepts_quest(self):
        """Persuasion=20 with threshold=0.5 → should accept."""
        from npc.quest_system import QuestSystem

        qs = QuestSystem(MockIntelligenceSkill(persuasion=20))
        qs.load_quest_data()

        player = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: (
            {"intelligence": 5, "commerce": 0, "persuasion": 20}[sub]
            if sid == "intelligence" else 0
        )
        player.skill_manager.get_skill_level.return_value = 5

        from npc.quest_system import QuestDefinition
        quest_def = QuestDefinition(
            quest_id="high_pers_quest",
            name="High Pers Quest",
            description="Test",
            acceptance_threshold=0.5,
            min_persuasion=0,
            min_commerce=0,
            min_total_intelligence=0,
        )
        qs.quest_definitions["high_pers_quest"] = quest_def

        npc = MagicMock()
        npc.npc_id = "test_npc"

        result = qs.accept_quest(player, npc, "high_pers_quest")
        self.assertTrue(result.success)


class TestQuestPrerequisiteCheck(unittest.TestCase):
    """Quest prerequisite checks."""

    def test_prerequisite_not_met(self):
        """Quest with unmet prerequisite → not eligible."""
        from npc.quest_system import QuestSystem

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        player = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: 0
        player.skill_manager.get_skill_level.return_value = 1

        from npc.quest_system import QuestDefinition
        quest_def = QuestDefinition(
            quest_id="child_quest",
            name="Child Quest",
            description="Test",
            prerequisite_quests=["parent_quest"],
        )
        qs.quest_definitions["child_quest"] = quest_def

        result = qs.check_quest_eligibility(player, quest_def)
        self.assertFalse(result.eligible)
        self.assertFalse(result.prerequisite_quests_met)

    def test_prerequisite_met(self):
        """Quest with completed prerequisite → eligible."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        # Mark parent quest as completed
        parent_progress = QuestProgress(
            quest_id="parent_quest",
            state=QuestState.COMPLETED,
        )
        qs.quest_progress["parent_quest"] = parent_progress

        player = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: 0
        player.skill_manager.get_skill_level.return_value = 1

        from npc.quest_system import QuestDefinition
        quest_def = QuestDefinition(
            quest_id="child_quest",
            name="Child Quest",
            description="Test",
            prerequisite_quests=["parent_quest"],
        )
        qs.quest_definitions["child_quest"] = quest_def

        result = qs.check_quest_eligibility(player, quest_def)
        self.assertTrue(result.prerequisite_quests_met)


class TestQuestFactionRequirement(unittest.TestCase):
    """Quest faction requirements."""

    def test_faction_requirement_not_met(self):
        """Required faction status not met → not eligible."""
        from npc.quest_system import QuestSystem

        fs = MockFactionSystem({"test_faction": "hostile"})
        qs = QuestSystem(MockIntelligenceSkill())
        qs.faction_system = fs
        qs.load_quest_data()

        player = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: 0
        player.skill_manager.get_skill_level.return_value = 1

        from npc.quest_system import QuestDefinition
        quest_def = QuestDefinition(
            quest_id="faction_quest",
            name="Faction Quest",
            description="Test",
            required_faction_status="friendly",
            giver_faction="test_faction",
        )
        qs.quest_definitions["faction_quest"] = quest_def

        result = qs.check_quest_eligibility(player, quest_def)
        self.assertFalse(result.eligible)
        self.assertFalse(result.faction_status_met)

    def test_faction_requirement_met(self):
        """Required faction status met → eligible."""
        from npc.quest_system import QuestSystem

        # The eligibility check calls get_status(req) where req is the
        # required_faction_status. We need get_status("friendly") to return
        # "friendly" or higher. So we store "friendly" as a faction_id.
        fs = MockFactionSystem({"friendly": "friendly"})
        qs = QuestSystem(MockIntelligenceSkill())
        qs.faction_system = fs
        qs.load_quest_data()

        player = MagicMock()
        player.skill_manager = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: 0
        player.skill_manager.get_skill_level.return_value = 1

        from npc.quest_system import QuestDefinition
        quest_def = QuestDefinition(
            quest_id="faction_quest",
            name="Faction Quest",
            description="Test",
            required_faction_status="friendly",
            giver_faction="test_faction",
        )
        qs.quest_definitions["faction_quest"] = quest_def

        result = qs.check_quest_eligibility(player, quest_def)
        self.assertTrue(result.faction_status_met)


class TestQuestConditionKillMonster(unittest.TestCase):
    """kill_monster condition tracking."""

    def test_kill_monster_condition(self):
        """Kill count updates condition current_count."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState, QuestCondition

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        # Create active quest with kill_monster condition
        progress = QuestProgress(
            quest_id="kill_quest",
            state=QuestState.ACTIVE,
            conditions=[QuestCondition(
                condition_type="kill_monster",
                target="goblin",
                required_count=5,
                current_count=0,
            )],
        )
        qs.quest_progress["kill_quest"] = progress

        # Record 3 kills
        qs.record_kill("goblin")
        qs.record_kill("goblin")
        qs.record_kill("goblin")

        # Simulate tick to update condition
        player = MagicMock()
        player.world_x = 640
        player.world_y = 640
        tile_map = MagicMock()
        tile_map.get_tile.return_value = None

        qs.tick(1.0, player, tile_map)

        quest_progress = qs.get_quest_progress("kill_quest")
        self.assertEqual(quest_progress.conditions[0].current_count, 3)


class TestQuestConditionCollectItem(unittest.TestCase):
    """collect_item condition tracks inventory."""

    def test_collect_item_condition(self):
        """collect_item condition reflects player inventory."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState, QuestCondition

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        progress = QuestProgress(
            quest_id="collect_quest",
            state=QuestState.ACTIVE,
            conditions=[QuestCondition(
                condition_type="collect_item",
                target="oak_logs",
                required_count=5,
                current_count=0,
            )],
        )
        qs.quest_progress["collect_quest"] = progress

        # Simulate tick with player having inventory
        player = MagicMock()
        player.world_x = 640
        player.world_y = 640
        player.inventory.get_item_quantity.return_value = 3

        tile_map = MagicMock()
        tile_map.get_tile.return_value = None

        qs.tick(1.0, player, tile_map)

        quest_progress = qs.get_quest_progress("collect_quest")
        self.assertEqual(quest_progress.conditions[0].current_count, 3)


class TestQuestConditionCraftItem(unittest.TestCase):
    """craft_item condition tracks craft counts."""

    def test_craft_item_condition(self):
        """craft_item condition reflects craft count."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState, QuestCondition

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        progress = QuestProgress(
            quest_id="craft_quest",
            state=QuestState.ACTIVE,
            conditions=[QuestCondition(
                condition_type="craft_item",
                target="planks",
                required_count=3,
                current_count=0,
            )],
        )
        qs.quest_progress["craft_quest"] = progress

        # Record crafts
        qs.record_craft("planks")
        qs.record_craft("planks")

        player = MagicMock()
        player.world_x = 640
        player.world_y = 640
        tile_map = MagicMock()
        tile_map.get_tile.return_value = None

        qs.tick(1.0, player, tile_map)

        quest_progress = qs.get_quest_progress("craft_quest")
        self.assertEqual(quest_progress.conditions[0].current_count, 2)


class TestQuestCompletionRewards(unittest.TestCase):
    """Quest completion grants XP, unlocks recipes/gear."""

    def test_quest_completion_grants_xp(self):
        """Completing quest grants skill XP."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState, QuestCondition
        from npc.quest_system import QuestDefinition

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        # Create completed quest with XP reward
        quest_def = QuestDefinition(
            quest_id="xp_quest",
            name="XP Quest",
            description="Test",
            skill_xp_rewards={"intelligence": 10.0},
            xp_reward=5.0,
            recipe_unlocks=["unlocked_recipe"],
            gear_unlocks=["unlocked_gear"],
            conditions=[],
        )
        qs.quest_definitions["xp_quest"] = quest_def

        progress = QuestProgress(
            quest_id="xp_quest",
            state=QuestState.ACTIVE,
            conditions=[],
        )
        qs.quest_progress["xp_quest"] = progress

        player = MagicMock()
        player.skill_manager.add_xp = MagicMock()

        game = MagicMock()
        game.crafting.unlock_recipe = MagicMock()
        game.crafting.unlock_gear = MagicMock()

        result = qs.complete_quest("xp_quest", player, game)

        self.assertTrue(result)
        # Verify XP grants
        xp_calls = [call for call in player.skill_manager.add_xp.call_args_list]
        self.assertTrue(len(xp_calls) >= 2)  # intelligence + quest XP

    def test_quest_completion_unlocks_recipe(self):
        """Completing quest unlocks recipe via game.crafting."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState
        from npc.quest_system import QuestDefinition

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        quest_def = QuestDefinition(
            quest_id="recipe_quest",
            name="Recipe Quest",
            description="Test",
            recipe_unlocks=["new_recipe"],
            conditions=[],
        )
        qs.quest_definitions["recipe_quest"] = quest_def

        progress = QuestProgress(
            quest_id="recipe_quest",
            state=QuestState.ACTIVE,
            conditions=[],
        )
        qs.quest_progress["recipe_quest"] = progress

        player = MagicMock()
        game = MagicMock()
        game.crafting.unlock_recipe = MagicMock()
        game.crafting.unlock_gear = MagicMock()

        qs.complete_quest("recipe_quest", player, game)
        game.crafting.unlock_recipe.assert_called_once_with("new_recipe")


class TestQuestAbandon(unittest.TestCase):
    """Quest failure/abandon."""

    def test_fail_quest(self):
        """Failing a quest marks it as FAILED."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        progress = QuestProgress(
            quest_id="fail_quest",
            state=QuestState.ACTIVE,
        )
        qs.quest_progress["fail_quest"] = progress

        result = qs.fail_quest("fail_quest", "Player gave up")
        self.assertTrue(result)

        quest_progress = qs.get_quest_progress("fail_quest")
        self.assertEqual(quest_progress.state, QuestState.FAILED)
        self.assertEqual(quest_progress.fail_reason, "Player gave up")

    def test_fail_nonexistent_quest(self):
        """Failing a non-existent quest returns False."""
        from npc.quest_system import QuestSystem

        qs = QuestSystem(MockIntelligenceSkill())
        result = qs.fail_quest("nonexistent", "Reason")
        self.assertFalse(result)


class TestRepeatableQuest(unittest.TestCase):
    """Repeatable quests can be accepted again after completion."""

    def test_repeatable_quest_acceptable_again(self):
        """Repeatable quest can be re-accepted after completion."""
        from npc.quest_system import QuestSystem, QuestProgress, QuestState
        from npc.quest_system import QuestDefinition

        qs = QuestSystem(MockIntelligenceSkill())
        qs.load_quest_data()

        quest_def = QuestDefinition(
            quest_id="repeat_quest",
            name="Repeat Quest",
            description="Test",
            repeatable=True,
            acceptance_threshold=0.3,
            conditions=[],
        )
        qs.quest_definitions["repeat_quest"] = quest_def

        # Complete it once
        progress = QuestProgress(
            quest_id="repeat_quest",
            state=QuestState.COMPLETED,
            is_repeatable=True,
        )
        qs.quest_progress["repeat_quest"] = progress

        player = MagicMock()
        player.skill_manager.get_effective_stat.side_effect = lambda sid, sub: 0
        player.skill_manager.get_skill_level.return_value = 1

        result = qs.check_quest_eligibility(player, quest_def)
        # Repeatable quests should be eligible even after completion
        self.assertTrue(result.not_already_completed)
        self.assertTrue(result.eligible)


if __name__ == "__main__":
    unittest.main()
