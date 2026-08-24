"""Robustness tests for the Phase 3 data validator (Report 12).

The validator's contract is to *report* cross-reference integrity problems and
exit 1 on error. On HEAD it instead raises an uncaught ``KeyError`` when a
record is missing a required key (``npcs.json`` faction / a spawn point tile).
These tests monkeypatch ``load_json`` to strip one key from an otherwise-valid
envelope built from the REAL ``npcs.json`` and assert the validator reports the
missing key (clean line + ``SystemExit(1)``) instead of crashing.
"""
import os
import sys
import json
import unittest
import io
import contextlib

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
)
import validate_phase3_data as v  # noqa: E402

REAL_LOAD = v.load_json
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

STRIP = None


def _envelope(strip_key):
    # Build from the REAL npcs.json so every cross-ref stays consistent
    # (faction values are real faction_ids / null, world coords land in a
    # spawn_point, npc_type is a valid enum, spawn biome/npc_types valid).
    # Only `strip_key` is removed -> the ONLY base-vs-after difference.
    with open(os.path.join(DATA, "npcs.json")) as f:
        data = json.load(f)
    if strip_key == "faction":
        del data["npcs"][0]["faction"]  # hits the faction guard (~line 67)
    elif strip_key == "tile_x":
        del data["spawn_points"][0]["tile_x"]  # hits the spawn guard (~line 31)
    return data


def fake_load(path):
    if os.path.basename(path).endswith("npcs.json"):
        return _envelope(STRIP)
    return REAL_LOAD(path)  # items/biomes/factions/quests/trade_items stay real


class ValidatorRobustness(unittest.TestCase):
    def _run(self, strip_key):
        global STRIP
        STRIP = strip_key
        v.load_json = fake_load
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            with self.assertRaises(SystemExit) as cm:
                v.main()
        v.load_json = REAL_LOAD
        return cm.exception.code, buf.getvalue()

    def test_missing_npc_faction_is_reported_not_raised(self):
        code, out = self._run("faction")
        self.assertEqual(code, 1)
        self.assertIn("missing 'faction'", out)

    def test_missing_spawn_tile_is_reported_not_raised(self):
        code, out = self._run("tile_x")
        self.assertEqual(code, 1)
        self.assertIn("missing 'tile_x'", out)


if __name__ == "__main__":
    unittest.main()
