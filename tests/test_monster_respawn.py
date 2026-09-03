"""
tests/test_monster_respawn.py — Phase 1 of monster-taming plan.

Verifies that killing a monster schedules a respawn and that advancing
the timer rebuilds a living instance of the same type.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from combat.combat_system import CombatSystem
from combat.monster import Monster
from skills.skill_manager import SkillManager


class TestMonsterRespawn(unittest.TestCase):
    def _build_combat(self):
        player = SimpleNamespace(
            skill_manager=SkillManager(),
            inventory=SimpleNamespace(add_item=lambda *a, **k: True),
            action_system=None,
            world_x=100.0,
            world_y=100.0,
        )
        combat = CombatSystem(player=player)
        combat.game = SimpleNamespace(quest_system=None, player=player)
        return combat

    def _make_wolf(self, x=200.0, y=200.0):
        return Monster.from_def(
            monster_id="wolf",
            biome="forest",
            world_x=x,
            world_y=y,
            monster_def={
                "name": "Wolf",
                "hp": 8,
                "attack": 3,
                "defence": 2,
                "speed": 80,
                "xp_reward": 15,
                "tamable": True,
                "faction_owned": True,
                "loot_table": [],
            },
        )

    def test_death_schedules_respawn(self):
        combat = self._build_combat()
        wolf = self._make_wolf()
        combat.register_monster(wolf)
        self.assertEqual(len(combat.monsters), 1)

        combat._monster_died(wolf)
        self.assertEqual(len(combat.monsters), 0)
        self.assertTrue(len(combat._respawn_queue) >= 1)

        entry = combat._respawn_queue[0]
        self.assertEqual(entry["monster_id"], "wolf")
        self.assertGreater(entry["timer"], 0)

    def test_tick_advances_and_respawns(self):
        combat = self._build_combat()
        wolf = self._make_wolf()
        combat.register_monster(wolf)
        combat._monster_died(wolf)

        # Force the timer to expire
        combat._respawn_queue[0]["timer"] = 0.01
        combat.tick(0.02)

        # A new living wolf should have appeared
        alive = [m for m in combat.monsters if m.is_alive()]
        self.assertEqual(len(alive), 1)
        self.assertEqual(alive[0].monster_id, "wolf")
        self.assertEqual(len(combat._respawn_queue), 0)

    def test_respawn_cap_per_type(self):
        combat = self._build_combat()
        # Schedule more deaths than the per-type cap
        for i in range(8):
            w = self._make_wolf(x=200 + i * 10)
            combat.register_monster(w)
            combat._monster_died(w)

        # Cap should limit the queue
        wolf_entries = [e for e in combat._respawn_queue if e["monster_id"] == "wolf"]
        self.assertLessEqual(len(wolf_entries), combat.RESPAWN_CAP_PER_TYPE)


if __name__ == "__main__":
    unittest.main()
