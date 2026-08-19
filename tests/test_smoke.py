"""
Smoke tests for Phase 1/2 Quality & Correctness plan.

Covers:
- C1: Starter pack init (isolated)
- C2: Save/load round-trip
- C3: Soft death → meters at 50%, death count, respawn
"""

import unittest
import tempfile


class TestSmokeStarterPack(unittest.TestCase):
    """C1: Starter pack init (isolated)."""

    def test_default_pack_gives_three_items(self):
        """A fresh inventory with default starter pack should have torch, berries, raw_fish."""
        from inventory.inventory import Inventory
        from survival.starter_pack import apply_starter_pack, CharacterDefinition

        inv = Inventory()
        inv.set_stack_size("torch", 1)
        inv.set_stack_size("berries", 28)
        inv.set_stack_size("raw_fish", 28)

        result = apply_starter_pack(inv, "default")
        self.assertTrue(result)
        self.assertGreater(inv.get_item_quantity("torch"), 0)
        self.assertGreater(inv.get_item_quantity("berries"), 0)
        self.assertGreater(inv.get_item_quantity("raw_fish"), 0)
        self.assertEqual(inv.count_non_empty(), 3)

    def test_prospector_pack_equips_tool(self):
        """Prospector pack should add axe and not crash on equip."""
        from inventory.inventory import Inventory
        from survival.starter_pack import apply_starter_pack

        inv = Inventory()
        inv.set_stack_size("pickaxe", 1)
        inv.set_stack_size("torch", 1)
        inv.set_stack_size("raw_meat", 28)

        result = apply_starter_pack(inv, "prospector")
        self.assertTrue(result)
        self.assertGreater(inv.get_item_quantity("pickaxe"), 0)


class TestSmokeSaveLoad(unittest.TestCase):
    """C2: Save/load round-trip."""

    def test_save_load_preserves_inventory(self):
        """Saving and reloading should preserve inventory state."""
        from core.save_system import SaveSystem
        from inventory.inventory import Inventory

        save_dir = tempfile.mkdtemp()
        ss = SaveSystem(save_dir=save_dir)

        inv = Inventory()
        inv.set_stack_size("stone", 28)
        inv.add_item("stone", 10)

        # Use SaveSystem.save with a minimal fake Game
        game = type('FakeGame', (), {
            'seed': 42, 'death_count': 0,
            'inventory': inv,
            'player': type('FakePlayer', (), {
                'world_x': 100.0, 'world_y': 200.0,
                'gear': None,
            })(),
            'skill_manager': None,
            'survival': None,
            'building_system': type('FakeBuilding', (), {'get_all_structures': lambda self: []})(),
            'firemaking': type('FakeFire', (), {'get_active_fires': lambda self: []})(),
        })()

        self.assertTrue(ss.save(game, slot=0))
        loaded = ss.load(slot=0)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["inventory"][0]["item_id"], "stone")
        self.assertEqual(loaded["inventory"][0]["quantity"], 10)


class TestSmokeSoftDeath(unittest.TestCase):
    """C3: Soft death → meters at 50%, death count, respawn."""

    def test_soft_death_respawn_and_counters(self):
        """Soft death should reset meters to 50%, increment death count, keep player alive."""
        from config import HP_BASE_MAX, DEATH_RESTORE_HP_FRACTION, DEATH_RESTORE_HUNGER_FRACTION
        from core.player import Player
        from combat.gear import PlayerGear
        from skills.skill_manager import SkillManager
        from survival.survival_system import SurvivalSystem
        from combat.combat_system import CombatSystem

        player = Player(0.0, 0.0)
        player.gear = PlayerGear()
        player.skill_manager = SkillManager()

        # Use real SurvivalSystem, not a mock
        survival = SurvivalSystem(environmental_pressure=1.0)

        # Mock game for death_count and save
        game = type('MockGame', (), {
            'death_count': 0,
            'world': type('MockWorld', (), {'spawn_x': 50, 'spawn_y': 50})(),
            'save_system': None,  # No save in this test
        })()

        cs = CombatSystem(player, survival, game=game)

        # Trigger death — deal enough damage to kill (HP starts at HP_BASE_MAX = 20)
        survival.take_damage(HP_BASE_MAX)
        self.assertTrue(survival.is_dead)

        # Run death sequence
        cs._on_player_death()

        # Verify
        self.assertEqual(game.death_count, 1)
        self.assertAlmostEqual(survival.hp, HP_BASE_MAX * DEATH_RESTORE_HP_FRACTION)
        self.assertAlmostEqual(survival.hunger, 100.0 * DEATH_RESTORE_HUNGER_FRACTION)
        self.assertFalse(survival.is_dead)
        # Player should have moved to spawn
        self.assertAlmostEqual(player.world_x, 50 * 64 + 32)
        self.assertAlmostEqual(player.world_y, 50 * 64 + 32)


if __name__ == "__main__":
    unittest.main()
