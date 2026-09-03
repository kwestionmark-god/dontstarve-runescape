"""Tests for weather spawn_mod wiring in CombatSystem.spawn_initial_monsters."""
import unittest
from unittest.mock import MagicMock

from combat.combat_system import CombatSystem


def _make_biome_data(n: int) -> dict:
    return {f"monster_{i}": {"hp": 10} for i in range(n)}


def _spawn(weather_effects):
    player = MagicMock()
    cs = CombatSystem(player, survival=None)
    if weather_effects is not None:
        ws = MagicMock()
        ws.get_effects.return_value = weather_effects
        cs.weather_system = ws
    cs.spawn_initial_monsters(
        _make_biome_data(10),
        spawn_world_x=0.0,
        spawn_world_y=0.0,
        spawn_radius_px=500.0,
        rng_seed=42,
    )
    return cs


class TestWeatherSpawnMod(unittest.TestCase):
    def test_default_count_without_weather(self):
        cs = _spawn(None)
        self.assertEqual(len(cs.monsters), 5)

    def test_spawn_mod_scales_count_down(self):
        cs = _spawn({"spawn_mod": 0.5})
        self.assertEqual(len(cs.monsters), 2)  # round(5 * 0.5) = 2 (round-half-even)

    def test_spawn_mod_scales_count_up(self):
        cs = _spawn({"spawn_mod": 2.0})
        self.assertEqual(len(cs.monsters), 10)  # capped at available data

    def test_spawn_mod_zero_spawns_minimum_one(self):
        cs = _spawn({"spawn_mod": 0.0})
        self.assertEqual(len(cs.monsters), 1)


if __name__ == "__main__":
    unittest.main()
