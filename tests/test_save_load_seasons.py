"""
Tests for Phase 4: Save/load season and weather round-trip.

Covers:
- S4e: Game snapshot includes season and weather keys
- S4f: Loaded snapshot restores season and weather correctly
- S4g: Particle system sync is called after load
"""

import pytest
import json
import os
import tempfile
from unittest import mock

from seasons.season_system import SeasonSystem
from seasons.weather_system import WeatherSystem
from core.save_system import SaveSystem
from render.particle_system import ParticleSystem


class MockGame:
    """Minimal mock game for save/load tests."""

    def __init__(self) -> None:
        self.seed = 42
        self.death_count = 0
        self.player = None
        self.survival = None
        self.inventory = None
        self.skill_manager = None
        self.crafting = None
        self.camera = None
        self.hud = None
        self.building_system = None
        self.quest_system = None
        self.faction_system = None
        self.npc_system = None
        self.trade_system = None
        self.recruitment_system = None
        self.firemaking = None
        self.combat_system = None
        self.season_system: SeasonSystem | None = None
        self.weather_system: WeatherSystem | None = None
        self.particle_system: ParticleSystem | None = None
        self._save_slots: list[dict] = []
        self._flavor_text = ""
        self.state = None


class TestSaveSnapshotSeasonWeather:
    """S4e: Snapshot includes season and weather keys."""

    def test_snapshot_contains_season_key(self) -> None:
        """_build_snapshot should include 'season' key when season_system exists."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "autumn"
        season.season_progress = 0.75
        season.season_elapsed = 450.0
        game.season_system = season

        save_system = SaveSystem(save_dir=tempfile.mkdtemp())
        snapshot = save_system._build_snapshot(game)

        assert "season" in snapshot
        assert snapshot["season"] is not None
        assert snapshot["season"]["current"] == "autumn"
        assert snapshot["season"]["progress"] == 0.75
        assert snapshot["season"]["elapsed"] == 450.0

    def test_snapshot_contains_weather_key(self) -> None:
        """_build_snapshot should include 'weather' key when weather_system exists."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0

        season = SeasonSystem()
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=42)
        weather.current_weather = "rain"
        weather.weather_timer = 30.0
        weather.weather_history = ["clear", "rain"]
        game.weather_system = weather

        save_system = SaveSystem(save_dir=tempfile.mkdtemp())
        snapshot = save_system._build_snapshot(game)

        assert "weather" in snapshot
        assert snapshot["weather"] is not None
        assert snapshot["weather"]["current"] == "rain"
        assert snapshot["weather"]["timer"] == 30.0
        assert snapshot["weather"]["history"] == ["clear", "rain"]

    def test_snapshot_without_season_system(self) -> None:
        """_build_snapshot should set season=None when no season_system."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0
        game.season_system = None

        save_system = SaveSystem(save_dir=tempfile.mkdtemp())
        snapshot = save_system._build_snapshot(game)

        assert "season" in snapshot
        assert snapshot["season"] is None

    def test_snapshot_without_weather_system(self) -> None:
        """_build_snapshot should set weather=None when no weather_system."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0
        game.weather_system = None

        save_system = SaveSystem(save_dir=tempfile.mkdtemp())
        snapshot = save_system._build_snapshot(game)

        assert "weather" in snapshot
        assert snapshot["weather"] is None


class TestSaveLoadRoundTrip:
    """S4f: Save and load restores season and weather correctly."""

    def test_save_and_load_restores_autumn_rain(self) -> None:
        """Save with autumn/rain should restore to autumn/rain."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "autumn"
        season.season_progress = 0.5
        season.season_elapsed = 300.0
        season.previous_season = "summer"
        season.transition_blend = 0.0
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=42)
        weather.current_weather = "rain"
        weather.weather_timer = 60.0
        weather.weather_history = ["clear", "rain"]
        game.weather_system = weather

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)

        # Save
        success = save_system.save(game, slot=0)
        assert success, "Save should succeed"

        # Load
        loaded_data = save_system.load(slot=0)
        assert loaded_data is not None

        # Verify keys present
        assert "season" in loaded_data
        assert "weather" in loaded_data

        # Verify season values
        assert loaded_data["season"]["current"] == "autumn"
        assert loaded_data["season"]["progress"] == 0.5
        assert loaded_data["season"]["elapsed"] == 300.0
        assert loaded_data["season"]["previous"] == "summer"

        # Verify weather values
        assert loaded_data["weather"]["current"] == "rain"
        assert loaded_data["weather"]["timer"] == 60.0
        assert loaded_data["weather"]["history"] == ["clear", "rain"]

    def test_save_and_load_restores_winter_snow(self) -> None:
        """Save with winter/snow should restore to winter/snow."""
        game = MockGame()
        game.seed = 99
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "winter"
        season.season_progress = 0.25
        season.season_elapsed = 150.0
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=99)
        weather.current_weather = "snow"
        weather.weather_timer = 0.0
        game.weather_system = weather

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)

        save_system.save(game, slot=0)
        loaded_data = save_system.load(slot=0)

        assert loaded_data is not None
        assert loaded_data["season"]["current"] == "winter"
        assert loaded_data["season"]["progress"] == 0.25
        assert loaded_data["weather"]["current"] == "snow"

    def test_save_and_load_restores_spring_clear(self) -> None:
        """Save with spring/clear should restore to spring/clear."""
        game = MockGame()
        game.seed = 7
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "spring"
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=7)
        weather.current_weather = "clear"
        game.weather_system = weather

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)

        save_system.save(game, slot=0)
        loaded_data = save_system.load(slot=0)

        assert loaded_data is not None
        assert loaded_data["season"]["current"] == "spring"
        assert loaded_data["weather"]["current"] == "clear"


class TestLoadIntoGame:
    """S4f/S4g: load_into_game restores season/weather and syncs particles."""

    def test_load_into_game_restores_season(self) -> None:
        """load_into_game should restore season_system state."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "autumn"
        season.season_progress = 0.8
        season.season_elapsed = 480.0
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=42)
        weather.current_weather = "rain"
        weather.weather_timer = 60.0
        game.weather_system = weather

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)
        save_system.save(game, slot=0)

        # Create a fresh game with default season
        fresh_game = MockGame()
        fresh_game.seed = 42
        fresh_game.death_count = 0
        fresh_season = SeasonSystem()
        fresh_season.current_season = "spring"
        fresh_game.season_system = fresh_season
        fresh_weather = WeatherSystem(season_system=fresh_season, seed=42)
        fresh_weather.current_weather = "clear"
        fresh_game.weather_system = fresh_weather

        # Load into fresh game
        loaded_data = save_system.load(slot=0)
        save_system.load_into_game(loaded_data, fresh_game)

        # Verify season restored
        assert fresh_game.season_system.current_season == "autumn"
        assert fresh_game.season_system.season_progress == 0.8
        assert fresh_game.season_system.season_elapsed == 480.0

        # Verify weather restored
        assert fresh_game.weather_system.current_weather == "rain"
        assert fresh_game.weather_system.weather_timer == 60.0  # Restored from save

    def test_load_into_game_syncs_particle_system(self) -> None:
        """load_into_game should call particle_system.sync after restoring weather."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "winter"
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=42)
        weather.current_weather = "snow"
        game.weather_system = weather

        ps = ParticleSystem()
        ps.sync("clear")  # Start with clear
        game.particle_system = ps

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)
        save_system.save(game, slot=0)

        # Fresh game
        fresh_game = MockGame()
        fresh_game.seed = 42
        fresh_game.death_count = 0
        fresh_season = SeasonSystem()
        fresh_game.season_system = fresh_season
        fresh_weather = WeatherSystem(season_system=fresh_season, seed=42)
        fresh_weather.current_weather = "clear"
        fresh_game.weather_system = fresh_weather
        fresh_ps = ParticleSystem()
        fresh_ps.sync("clear")
        fresh_game.particle_system = fresh_ps

        loaded_data = save_system.load(slot=0)
        save_system.load_into_game(loaded_data, fresh_game)

        # Particle system should be synced to the loaded weather
        assert fresh_game.particle_system.current_weather == "snow"
        assert fresh_game.particle_system._spawn_rate == 10  # snow spawn rate

    def test_load_into_game_no_particle_system_no_error(self) -> None:
        """load_into_game should not error when particle_system is None."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "autumn"
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=42)
        weather.current_weather = "rain"
        game.weather_system = weather

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)
        save_system.save(game, slot=0)

        fresh_game = MockGame()
        fresh_game.seed = 42
        fresh_game.death_count = 0
        fresh_season = SeasonSystem()
        fresh_game.season_system = fresh_season
        fresh_weather = WeatherSystem(season_system=fresh_season, seed=42)
        fresh_game.weather_system = fresh_weather
        fresh_game.particle_system = None  # No particle system

        loaded_data = save_system.load(slot=0)
        # Should not raise
        save_system.load_into_game(loaded_data, fresh_game)

        # Season and weather should still be restored
        assert fresh_game.season_system.current_season == "autumn"
        assert fresh_game.weather_system.current_weather == "rain"

    def test_load_into_game_no_season_system_no_error(self) -> None:
        """load_into_game should not error when season_system is None."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0
        game.season_system = None
        game.weather_system = None

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)
        save_system.save(game, slot=0)

        fresh_game = MockGame()
        fresh_game.seed = 42
        fresh_game.death_count = 0
        fresh_game.season_system = None
        fresh_game.weather_system = None

        loaded_data = save_system.load(slot=0)
        # Should not raise
        save_system.load_into_game(loaded_data, fresh_game)


class TestSaveFileFormat:
    """Verify the saved JSON file structure."""

    def test_saved_file_contains_expected_keys(self) -> None:
        """The saved JSON file should contain season and weather keys."""
        game = MockGame()
        game.seed = 42
        game.death_count = 0

        season = SeasonSystem()
        season.current_season = "autumn"
        game.season_system = season

        weather = WeatherSystem(season_system=season, seed=42)
        weather.current_weather = "rain"
        game.weather_system = weather

        save_dir = tempfile.mkdtemp()
        save_system = SaveSystem(save_dir=save_dir)
        save_system.save(game, slot=0)

        # Read the raw JSON file
        import json
        save_path = os.path.join(save_dir, "slot_0.json")
        with open(save_path, "r") as f:
            raw = json.load(f)

        assert "season" in raw
        assert "weather" in raw
        assert raw["season"]["current"] == "autumn"
        assert raw["weather"]["current"] == "rain"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
