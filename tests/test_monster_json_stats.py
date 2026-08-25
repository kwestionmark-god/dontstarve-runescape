"""
Tests for LIVE-ISSUES #14: Monster combat stats must come from data/monsters.json.

`Monster.from_def` previously read combat stats (hp/attack/defence/speed/xp) and
AI ranges from a hardcoded table, ignoring the per-monster definition. These tests
lock in that the definition dict wins, with the built-in table as fallback.
"""

import unittest

from combat.monster import Monster


class MonsterJsonStatsTest(unittest.TestCase):
    def test_combat_stats_come_from_def(self):
        """Combat stats are taken from the def, not the built-in table."""
        monster_def = {
            "hp": 99, "attack": 42, "defence": 7, "speed": 250,
            "xp_reward": 77, "aggression_range": 210, "flee_range": 420,
            "attack_cooldown": 0.9, "is_hostile": True,
            "name": "Test Beast", "sprite_key": "monster/test",
        }
        m = Monster.from_def("test_beast", "forest", 0.0, 0.0, monster_def=monster_def)
        self.assertEqual(m.hp, 99)
        self.assertEqual(m.max_hp, 99)
        self.assertEqual(m.attack, 42)
        self.assertEqual(m.defence, 7)
        self.assertEqual(m.speed, 250.0)
        self.assertEqual(m.xp_reward, 77.0)
        self.assertEqual(m.aggression_range, 210.0)
        self.assertEqual(m.flee_range, 420.0)
        self.assertAlmostEqual(m.attack_cooldown, 0.9)
        self.assertEqual(m.name, "Test Beast")
        self.assertEqual(m.sprite_key, "monster/test")

    def test_is_hostile_read_from_def(self):
        """is_hostile is honored from the def (e.g. crab is not aggressive)."""
        m = Monster.from_def("crab", "coastal", 0.0, 0.0,
                             monster_def={"is_hostile": False})
        self.assertFalse(m.is_hostile)

    def test_loot_table_and_special_read_from_def(self):
        loot = [{"item_id": "shard", "chance": 0.5}]
        m = Monster.from_def("x", "forest", 0.0, 0.0, monster_def={
            "loot_table": loot, "special": "poison"})
        self.assertEqual(m.loot_table, loot)
        self.assertEqual(m.special, "poison")

    def test_falls_back_to_table_when_no_def(self):
        """Without a def, stats come from the built-in table (back-compat)."""
        m = Monster.from_def("wolf", "forest", 0.0, 0.0)
        self.assertEqual(m.hp, 8)
        self.assertEqual(m.attack, 3)
        self.assertEqual(m.defence, 2)
        self.assertEqual(m.speed, 80.0)
        self.assertEqual(m.aggression_range, 150.0)
        self.assertEqual(m.flee_range, 300.0)
        self.assertEqual(m.attack_cooldown, 1.5)

    def test_reset_special_restores_def_base_attack(self):
        """Poison restore uses the def's base attack, not the table's."""
        monster_def = {"hp": 50, "attack": 30, "defence": 5, "speed": 100}
        m = Monster.from_def("boss", "desert", 0.0, 0.0,
                             special="poison", monster_def=monster_def)
        self.assertEqual(m.attack, 30)
        m.attack = 31  # simulate poison +1
        m.reset_special()
        self.assertEqual(m.attack, 30)  # restored to def base, not table's 6


if __name__ == "__main__":
    unittest.main()
