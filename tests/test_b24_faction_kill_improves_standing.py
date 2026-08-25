"""
tests/test_b24_faction_kill_improves_standing.py — LIVE-ISSUES #8.

Killing a faction-associated monster must IMPROVE relations with that faction.
These monsters respawn, so hunting them removes a rival/threat the faction also
deals with; defeating them improves standing (and the on-screen feedback), rather
than worsening it.
"""

import unittest
from types import SimpleNamespace

from skills.skill_manager import SkillManager
from npc.faction_system import FactionSystem
from combat.combat_system import CombatSystem


class TestFactionKillStanding(unittest.TestCase):
    def _build(self):
        player = SimpleNamespace(
            skill_manager=SkillManager(),
            inventory=SimpleNamespace(add_item=lambda *a, **k: True),
            action_system=None,
        )
        factions_data = {
            "factions": [
                {
                    "faction_id": "goblins",
                    "name": "Goblins",
                    "hostile_monster_types": ["wolf", "goblin"],
                }
            ]
        }
        fs = FactionSystem(factions_data)
        combat = CombatSystem(player=player, faction_system=fs)
        notifications = []
        player.action_system = SimpleNamespace(
            add_notification=lambda msg, color=(255, 255, 255): notifications.append((msg, color))
        )
        game = SimpleNamespace(quest_system=None, player=player)
        combat.game = game
        return combat, player, notifications

    def _dead_monster(self, monster_id, name):
        return SimpleNamespace(
            xp_reward=5, monster_id=monster_id, name=name,
            loot_table=[], is_alive=lambda: True,
        )

    def test_get_faction_for_monster_maps_hostile_types(self):
        combat, _, _ = self._build()
        self.assertEqual(combat.faction_system.get_faction_for_monster("goblin"), "goblins")
        self.assertIsNone(combat.faction_system.get_faction_for_monster("rabbit"))

    def test_killing_faction_monster_improves_standing(self):
        combat, _, notifications = self._build()
        self.assertAlmostEqual(combat.faction_system.get_standing("goblins"), 0.5)

        monster = self._dead_monster("goblin", "Goblin")
        combat.monsters.append(monster)
        combat.selected_target = monster
        combat._monster_died(monster)

        # Defeating the monster improves relations above neutral.
        self.assertGreater(combat.faction_system.get_standing("goblins"), 0.5)
        # Positive, on-screen feedback that names the faction.
        msgs = [m for m, _ in notifications]
        self.assertTrue(any("improved relations" in m.lower() for m in msgs), msgs)
        self.assertTrue(any("goblins" in m.lower() for m in msgs), msgs)

    def test_killing_non_faction_monster_untouched(self):
        combat, _, notifications = self._build()
        monster = self._dead_monster("rabbit", "Rabbit")
        combat.monsters.append(monster)
        combat.selected_target = monster
        combat._monster_died(monster)

        self.assertEqual(combat.faction_system.get_standing("goblins"), 0.5)
        self.assertEqual(notifications, [])


if __name__ == "__main__":
    unittest.main()
