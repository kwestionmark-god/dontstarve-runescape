"""
tests/test_monster_taming_flags.py — Phase 0 of monster-taming plan.

Asserts every monster definition carries safe defaults for the new
tamable / faction_owned flags, and that Monster.from_def stores them.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from combat.monster import Monster


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "monsters.json"


class TestMonsterTamingFlags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_PATH, encoding="utf-8") as fh:
            cls.raw = json.load(fh)
        cls.monsters = cls.raw["monsters"]

    def test_every_monster_has_flags(self):
        missing = []
        for biome, entries in self.monsters.items():
            for mid, mdef in entries.items():
                if "tamable" not in mdef or "faction_owned" not in mdef:
                    missing.append(f"{biome}/{mid}")
        self.assertEqual(missing, [], f"Missing flags: {missing}")

    def test_flags_are_boolean(self):
        for biome, entries in self.monsters.items():
            for mid, mdef in entries.items():
                self.assertIsInstance(mdef["tamable"], bool, f"{mid}.tamable")
                self.assertIsInstance(mdef["faction_owned"], bool, f"{mid}.faction_owned")

    def test_from_def_stores_flags(self):
        # Pick a known tamable + owned monster
        wolf_def = self.monsters["forest"]["wolf"]
        m = Monster.from_def(
            monster_id="wolf",
            biome="forest",
            world_x=0.0,
            world_y=0.0,
            monster_def=wolf_def,
        )
        self.assertTrue(getattr(m, "tamable", False))
        self.assertTrue(getattr(m, "faction_owned", False))

        # Non-tamable, non-owned
        drake_def = self.monsters["swamp"]["swamp_drake"]
        d = Monster.from_def(
            monster_id="swamp_drake",
            biome="swamp",
            world_x=0.0,
            world_y=0.0,
            monster_def=drake_def,
        )
        self.assertFalse(getattr(d, "tamable", True))
        self.assertFalse(getattr(d, "faction_owned", True))

    def test_defaults_when_flags_absent(self):
        # Backward-compat: definitions without the keys still load
        m = Monster.from_def(
            monster_id="wolf",
            biome="forest",
            world_x=10.0,
            world_y=20.0,
            monster_def={"name": "Wolf", "hp": 8},
        )
        self.assertFalse(getattr(m, "tamable", True))  # safe default False
        self.assertFalse(getattr(m, "faction_owned", True))


if __name__ == "__main__":
    unittest.main()
