"""
tests/test_npc_system.py — Unit tests for NPCSystem.

Covers:
- NPC spawn placement at walkable tiles
- Proximity detection (nearest NPC within 128px)
- NPC movement toward target
- Patrol behavior (stays in patrol area)
- Interaction range (128-pixel)
- Multiple NPCs proximity (closest selected)
"""

import unittest
import math
from unittest.mock import MagicMock, Mock


class MockTile:
    """Minimal tile mock for NPCSystem tests."""

    def __init__(self, biome=None, resource_node=None):
        self.biome = biome
        self.resource_node = resource_node
        self.elevation = 0


class MockBiome:
    """Minimal biome mock."""
    def __init__(self, id="test_biome"):
        self.id = id
        self.environmental_pressure = 1.0


class MockTileMap:
    """Minimal TileMap mock for NPCSystem tests."""

    def __init__(self, tiles=None, spawn_x=10, spawn_y=10):
        self.tiles = tiles or {}
        self.spawn_x = spawn_x
        self.spawn_y = spawn_y
        self.width = 50
        self.height = 50

    def get_tile(self, x, y):
        return self.tiles.get((x, y))


class TestNPCSpawnPlacement(unittest.TestCase):
    """NPCs spawn at walkable tiles."""

    def test_spawn_at_walkable_tile(self):
        """NPC should spawn at a walkable tile (no resource node)."""
        from npc.npc_system import NPCSystem

        # Create a walkable tile
        tile = MockTile(biome=MockBiome(), resource_node=None)
        tiles = {(10, 10): tile}
        tile_map = MockTileMap(tiles=tiles, spawn_x=10, spawn_y=10)

        npc_system = NPCSystem(tile_map)
        # spawn_npcs loads from npcs.json — with no spawn points, no NPCs spawned
        self.assertEqual(len(npc_system.npcs), 0)

    def test_walkable_tile_has_biome_no_resource(self):
        """Walkable tile must have biome and no resource node."""
        from npc.npc_system import NPCSystem

        tile_walkable = MockTile(biome=MockBiome(), resource_node=None)
        tile_blocked = MockTile(biome=MockBiome(), resource_node=MagicMock())
        tile_no_biome = MockTile(biome=None, resource_node=None)

        tiles = {
            (10, 10): tile_walkable,
            (11, 11): tile_blocked,
            (12, 12): tile_no_biome,
        }
        tile_map = MockTileMap(tiles=tiles)
        npc_system = NPCSystem(tile_map)

        # _is_walkable_tile should return True only for walkable
        self.assertTrue(npc_system._is_walkable_tile(tile_walkable))
        self.assertFalse(npc_system._is_walkable_tile(tile_blocked))
        self.assertFalse(npc_system._is_walkable_tile(tile_no_biome))


class TestNPCProximityDetection(unittest.TestCase):
    """Nearest NPC within 128px."""

    def test_proximity_within_range(self):
        """NPC within 128px should be detected."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        # Create an NPC close to origin
        npc = NPC(
            npc_id="test_npc",
            name="Test NPC",
            npc_type="merchant",
            world_x=50.0,
            world_y=50.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        npc_system.npcs.append(npc)

        # Player at origin
        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.check_proximity(player)
        self.assertIsNotNone(nearby)
        self.assertEqual(nearby.npc_id, "test_npc")

    def test_proximity_outside_range(self):
        """NPC beyond 128px should not be detected."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        npc = NPC(
            npc_id="far_npc",
            name="Far NPC",
            npc_type="merchant",
            world_x=200.0,
            world_y=200.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        npc_system.npcs.append(npc)

        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.check_proximity(player)
        self.assertIsNone(nearby)


class TestNPCMovement(unittest.TestCase):
    """NPC moves toward target."""

    def test_npc_moves_toward_target(self):
        """NPC position should change toward target."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        npc = NPC(
            npc_id="moving_npc",
            name="Moving NPC",
            npc_type="merchant",
            world_x=0.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=True,
        )

        # Move toward (100, 100) for 1 second
        npc_system._move_toward(npc, 100.0, 100.0, 1.0)

        # NPC should have moved closer
        dist = math.sqrt(npc.world_x ** 2 + npc.world_y ** 2)
        self.assertGreater(dist, 0.0, "NPC should have moved")
        self.assertLess(dist, 142.0, "NPC should not have reached target in 1s at merchant speed")


class TestNPCPatrolBehavior(unittest.TestCase):
    """NPC stays in patrol area."""

    def test_patrol_target_within_patrol_area(self):
        """Random patrol target should be within the NPC's patrol area."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        npc = NPC(
            npc_id="patrol_npc",
            name="Patrol NPC",
            npc_type="merchant",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/merchant",
            patrol_area=(80, 80, 120, 120),
            is_active=True,
        )

        target = npc_system._get_random_patrol_target(npc)
        min_x, min_y, max_x, max_y = npc.patrol_area

        # Target should be in tile coords * 64 + 32 range
        self.assertGreaterEqual(target[0], min_x * 64 + 32)
        self.assertLessEqual(target[0], max_x * 64 + 32)
        self.assertGreaterEqual(target[1], min_y * 64 + 32)
        self.assertLessEqual(target[1], max_y * 64 + 32)

    def test_no_patrol_area_returns_current_position(self):
        """NPC without patrol area returns current position."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        npc = NPC(
            npc_id="idle_npc",
            name="Idle NPC",
            npc_type="merchant",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/merchant",
            patrol_area=None,
            is_active=True,
        )

        target = npc_system._get_random_patrol_target(npc)
        self.assertEqual(target, (100.0, 100.0))


class TestNPCInteractionRange(unittest.TestCase):
    """128-pixel interaction range."""

    def test_proximity_range_constant(self):
        """PROXIMITY_RANGE should be 128.0."""
        from npc.npc_system import NPCSystem
        self.assertEqual(NPCSystem.PROXIMITY_RANGE, 128.0)

    def test_exact_128px_is_detected(self):
        """NPC exactly at 128px should be detected (<= range)."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        npc = NPC(
            npc_id="edge_npc",
            name="Edge NPC",
            npc_type="merchant",
            world_x=128.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        npc_system.npcs.append(npc)

        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.check_proximity(player)
        self.assertIsNotNone(nearby)

    def test_129px_is_not_detected(self):
        """NPC at 129px should not be detected (> range)."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        npc = NPC(
            npc_id="edge_npc",
            name="Edge NPC",
            npc_type="merchant",
            world_x=129.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        npc_system.npcs.append(npc)

        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.check_proximity(player)
        self.assertIsNone(nearby)


class TestMultipleNPCsProximity(unittest.TestCase):
    """Closest NPC selected when multiple are near."""

    def test_nearest_npc_returned_first(self):
        """get_nearby_npcs should return NPCs sorted by distance."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        # NPC at distance 50
        npc1 = NPC(
            npc_id="close_npc",
            name="Close NPC",
            npc_type="merchant",
            world_x=50.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        # NPC at distance 100
        npc2 = NPC(
            npc_id="far_npc",
            name="Far NPC",
            npc_type="merchant",
            world_x=100.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        # NPC at distance 30 (even closer)
        npc3 = NPC(
            npc_id="very_close_npc",
            name="Very Close NPC",
            npc_type="merchant",
            world_x=30.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        npc_system.npcs.extend([npc1, npc2, npc3])

        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.get_nearby_npcs(0, 0, 200)
        self.assertEqual(len(nearby), 3)
        self.assertEqual(nearby[0].npc_id, "very_close_npc")
        self.assertEqual(nearby[1].npc_id, "close_npc")
        self.assertEqual(nearby[2].npc_id, "far_npc")

    def test_inactive_npc_not_returned(self):
        """Inactive NPCs should not appear in proximity results."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = MockTileMap()
        npc_system = NPCSystem(tile_map)

        active_npc = NPC(
            npc_id="active",
            name="Active",
            npc_type="merchant",
            world_x=50.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=True,
        )
        inactive_npc = NPC(
            npc_id="inactive",
            name="Inactive",
            npc_type="merchant",
            world_x=30.0,
            world_y=0.0,
            sprite_key="npc/merchant",
            is_active=False,
        )
        npc_system.npcs.extend([active_npc, inactive_npc])

        player = MagicMock()
        player.world_x = 0.0
        player.world_y = 0.0

        nearby = npc_system.get_nearby_npcs(0, 0, 200)
        self.assertEqual(len(nearby), 1)
        self.assertEqual(nearby[0].npc_id, "active")


if __name__ == "__main__":
    unittest.main()
