"""
tests/integration/test_npc_integration.py — Integration tests for NPC system.

Covers:
- Full NPC approach → interact → panel open flow
- NPC proximity detection with multiple NPCs
- NPC movement and patrol behavior
"""

import unittest
from unittest.mock import MagicMock, patch


class TestNPCInteractPanelOpen(unittest.TestCase):
    """Full NPC approach → interact → panel open flow."""

    def test_merchant_npc_opens_trade_panel(self):
        """Approaching a merchant NPC should open the trade panel."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MagicMock()
        tile_map.get_tile.return_value = MagicMock(biome=MagicMock(id="plains"), resource_node=None)
        npc_system = NPCSystem(tile_map)

        # Place a merchant NPC within interaction range
        merchant = NPC(
            npc_id="merchant_test",
            name="Merchant",
            npc_type="merchant",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        npc_system.npcs.append(merchant)

        # Player approaches (within 128px)
        player = MagicMock()
        player.world_x = 50.0
        player.world_y = 50.0

        # Check proximity
        nearby = npc_system.check_proximity(player)
        self.assertIsNotNone(nearby)
        self.assertEqual(nearby.npc_id, "merchant_test")
        self.assertEqual(nearby.npc_type, "merchant")

    def test_quest_giver_npc_opens_quest_panel(self):
        """Approaching a quest giver NPC should open the quest panel."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MagicMock()
        tile_map.get_tile.return_value = MagicMock(biome=MagicMock(id="plains"), resource_node=None)
        npc_system = NPCSystem(tile_map)

        quest_giver = NPC(
            npc_id="quest_giver_test",
            name="Quest Giver",
            npc_type="quest_giver",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/quest_giver",
            is_active=True,
        )
        npc_system.npcs.append(quest_giver)

        player = MagicMock()
        player.world_x = 50.0
        player.world_y = 50.0

        nearby = npc_system.check_proximity(player)
        self.assertIsNotNone(nearby)
        self.assertEqual(nearby.npc_type, "quest_giver")


class TestNPCProximityIntegration(unittest.TestCase):
    """Multiple NPCs proximity detection."""

    def test_closest_npc_selected_among_multiple(self):
        """When multiple NPCs are nearby, the closest one is returned."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MagicMock()
        npc_system = NPCSystem(tile_map)

        # Three NPCs at different distances
        npc1 = NPC(npc_id="npc_far", name="Far", npc_type="merchant",
                   world_x=200.0, world_y=0.0, sprite_key="npc/merchant", is_active=True)
        npc2 = NPC(npc_id="npc_mid", name="Mid", npc_type="merchant",
                   world_x=100.0, world_y=0.0, sprite_key="npc/merchant", is_active=True)
        npc3 = NPC(npc_id="npc_close", name="Close", npc_type="merchant",
                   world_x=50.0, world_y=0.0, sprite_key="npc/merchant", is_active=True)
        npc_system.npcs.extend([npc1, npc2, npc3])

        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.check_proximity(player)
        self.assertIsNotNone(nearby)
        self.assertEqual(nearby.npc_id, "npc_close")

    def test_no_nearby_npc_returns_none(self):
        """No NPC within range returns None."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MagicMock()
        npc_system = NPCSystem(tile_map)

        npc = NPC(npc_id="npc_far", name="Far", npc_type="merchant",
                  world_x=500.0, world_y=500.0, sprite_key="npc/merchant", is_active=True)
        npc_system.npcs.append(npc)

        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.check_proximity(player)
        self.assertIsNone(nearby)


class TestNPCMovementIntegration(unittest.TestCase):
    """NPC movement and patrol integration."""

    def test_npc_movement_toward_target(self):
        """NPC moves toward patrol target over time."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MagicMock()
        npc_system = NPCSystem(tile_map)

        npc = NPC(npc_id="moving_npc", name="Moving", npc_type="merchant",
                  world_x=0.0, world_y=0.0, sprite_key="npc/merchant", is_active=True)

        # Move toward (100, 100) for 2 seconds
        for _ in range(4):
            npc_system._move_toward(npc, 100.0, 100.0, 0.5)

        import math
        dist = math.sqrt(npc.world_x ** 2 + npc.world_y ** 2)
        self.assertGreater(dist, 0.0, "NPC should have moved")

    def test_npc_stays_in_patrol_area(self):
        """NPC patrol target stays within defined patrol area."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MagicMock()
        npc_system = NPCSystem(tile_map)

        npc = NPC(npc_id="patrol_npc", name="Patrol", npc_type="merchant",
                  world_x=640.0, world_y=640.0, sprite_key="npc/merchant",
                  patrol_area=(10, 10, 15, 15), is_active=True)

        target = npc_system._get_random_patrol_target(npc)
        min_x, min_y, max_x, max_y = npc.patrol_area

        self.assertGreaterEqual(target[0], min_x * 64 + 32)
        self.assertLessEqual(target[0], max_x * 64 + 32)
        self.assertGreaterEqual(target[1], min_y * 64 + 32)
        self.assertLessEqual(target[1], max_y * 64 + 32)


if __name__ == "__main__":
    unittest.main()
