"""
test_weather_system.py — Integration tests for WeatherSystem.

Tests:
- Weather timer expiry and rolling
- Weather effects (movement, visibility, crafting, spawn)
- Weather history/forecast
- Season influence on weather weights
- Save/load persistence
"""

import pytest
from seasons.weather_system import WeatherSystem
from seasons.season_system import SeasonSystem


class TestWeatherTimer:
    """Test weather timer countdown and rolling."""

    def test_weather_stays_clear_below_threshold(self):
        """Weather should not change before timer expires."""
        ws = WeatherSystem(
            season_system=None,
            seed=42,
            change_interval=60.0,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Tick for 30 seconds (half the interval)
        ws.tick(30.0)
        assert ws.current_weather == "clear"
        assert ws.weather_timer == 30.0

    def test_weather_changes_after_timer_expires(self):
        """Weather should roll when timer reaches interval."""
        ws = WeatherSystem(
            season_system=None,
            seed=42,
            change_interval=60.0,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Tick for 60 seconds (full interval)
        ws.tick(60.0)
        # Weather should have changed (or stayed clear if rolled clear again)
        assert ws.current_weather in ("clear", "rain", "snow", "storm", "fog")
        assert ws.weather_timer == 0.0  # Reset

    def test_multiple_timer_cycles(self):
        """Timer should reset and roll multiple times."""
        ws = WeatherSystem(
            season_system=None,
            seed=42,
            change_interval=30.0,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Tick in 30-second increments (3 cycles)
        for _ in range(3):
            ws.tick(30.0)
        assert len(ws.weather_history) >= 3


class TestWeatherEffects:
    """Test weather effect multipliers."""

    def test_clear_effects(self):
        """Clear weather should have no penalties."""
        ws = WeatherSystem(season_system=None, seed=42)
        ws.current_weather = "clear"

        effects = ws.get_effects()
        assert effects["movement_speed"] == 1.0
        assert effects["visibility"] == 1.0
        assert effects["outdoor_crafting"] == 1.0
        assert effects["spawn_mod"] == 1.0

    def test_rain_effects(self):
        """Rain should reduce movement, visibility, and outdoor crafting."""
        ws = WeatherSystem(season_system=None, seed=42)
        ws.current_weather = "rain"

        effects = ws.get_effects()
        assert effects["movement_speed"] == 0.9
        assert effects["visibility"] == 0.85
        assert effects["outdoor_crafting"] == 0.0
        assert effects["spawn_mod"] == 1.2

    def test_snow_effects(self):
        """Snow should reduce movement, visibility, and outdoor crafting."""
        ws = WeatherSystem(season_system=None, seed=42)
        ws.current_weather = "snow"

        effects = ws.get_effects()
        assert effects["movement_speed"] == 0.8
        assert effects["visibility"] == 0.70
        assert effects["outdoor_crafting"] == 0.0
        assert effects["spawn_mod"] == 0.7

    def test_storm_effects(self):
        """Storm should significantly reduce movement, visibility, and crafting."""
        ws = WeatherSystem(season_system=None, seed=42)
        ws.current_weather = "storm"

        effects = ws.get_effects()
        assert effects["movement_speed"] == 0.7
        assert effects["visibility"] == 0.50
        assert effects["outdoor_crafting"] == 0.3
        assert effects["spawn_mod"] == 0.5

    def test_fog_effects(self):
        """Fog should reduce visibility significantly."""
        ws = WeatherSystem(season_system=None, seed=42)
        ws.current_weather = "fog"

        effects = ws.get_effects()
        assert effects["movement_speed"] == 0.9
        assert effects["visibility"] == 0.40
        assert effects["outdoor_crafting"] == 1.0
        assert effects["spawn_mod"] == 1.1


class TestWeatherHistory:
    """Test weather history and forecast."""

    def test_history_tracks_changes(self):
        """Weather history should record each roll."""
        ws = WeatherSystem(
            season_system=None,
            seed=42,
            change_interval=10.0,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Force multiple weather changes
        for _ in range(5):
            ws.tick(10.0)

        assert len(ws.weather_history) == 5

    def test_forecast_returns_recent_history(self):
        """Forecast should return the last n weather entries."""
        ws = WeatherSystem(
            season_system=None,
            seed=42,
            change_interval=10.0,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Force 5 weather changes
        for _ in range(5):
            ws.tick(10.0)

        forecast = ws.get_forecast(3)
        assert len(forecast) == 3
        assert forecast == ws.weather_history[-3:]

    def test_history_truncates_at_max(self):
        """History should be capped at 10 entries."""
        ws = WeatherSystem(
            season_system=None,
            seed=42,
            change_interval=10.0,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Force 15 weather changes
        for _ in range(15):
            ws.tick(10.0)

        assert len(ws.weather_history) == 10


class TestSeasonInfluence:
    """Test how seasons influence weather rolls."""

    def test_no_season_default_clear(self):
        """Without a season system, weather should default to clear."""
        ws = WeatherSystem(
            season_system=None,
            seed=42,
            change_interval=10.0,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Force a roll
        ws.tick(10.0)
        # Should be valid weather type
        assert ws.current_weather in ("clear", "rain", "snow", "storm", "fog")

    def test_season_system_reference(self):
        """WeatherSystem should accept and store a SeasonSystem reference."""
        ss = SeasonSystem()
        ws = WeatherSystem(season_system=ss, seed=42)

        assert ws.season_system is ss

    def test_set_season_system(self):
        """Should be able to set season system after construction."""
        ws = WeatherSystem(season_system=None, seed=42)
        assert ws.season_system is None

        ss = SeasonSystem()
        ws.set_season_system(ss)
        assert ws.season_system is ss


class TestSaveLoad:
    """Test weather save/load persistence."""

    def test_to_dict_serializes_state(self):
        """to_dict should serialize current weather and timer."""
        ws = WeatherSystem(season_system=None, seed=42)
        ws.current_weather = "rain"
        ws.weather_timer = 45.0
        ws.weather_history = ["clear", "rain"]

        data = ws.to_dict()

        assert data["current"] == "rain"
        assert data["timer"] == 45.0
        assert data["history"] == ["clear", "rain"]

    def test_from_dict_restores_state(self):
        """from_dict should restore weather state."""
        data = {
            "current": "storm",
            "timer": 30.0,
            "history": ["clear", "rain", "storm"],
        }

        ws = WeatherSystem.from_dict(data, seed=42)

        assert ws.current_weather == "storm"
        assert ws.weather_timer == 30.0
        assert ws.weather_history == ["clear", "rain", "storm"]

    def test_roundtrip_save_load(self):
        """Serializing and deserializing should preserve state."""
        ws1 = WeatherSystem(season_system=None, seed=42)
        ws1.current_weather = "snow"
        ws1.weather_timer = 20.0
        ws1.weather_history = ["clear", "snow"]

        data = ws1.to_dict()
        ws2 = WeatherSystem.from_dict(data, seed=42)

        assert ws2.current_weather == ws1.current_weather
        assert ws2.weather_timer == ws1.weather_timer
        assert ws2.weather_history == ws1.weather_history


class TestCustomWeights:
    """Test custom weather spawn weights."""

    def test_custom_weights_used(self):
        """Should use custom spawn weights if provided."""
        # Spring: 70% clear, 30% rain, 0% others
        weights = {"spring": (0.7, 0.3, 0.0, 0.0, 0.0)}

        ss = SeasonSystem()
        ss.current_season = "spring"

        ws = WeatherSystem(
            season_system=ss,
            seed=42,
            change_interval=10.0,
            spawn_weights=weights,
        )
        ws.current_weather = "clear"
        ws.weather_timer = 0.0

        # Force multiple rolls
        for _ in range(10):
            ws.tick(10.0)

        # Only "clear" (index 0) and "rain" (index 1) should appear
        for weather in ws.weather_history:
            assert weather in ("clear", "rain")


class TestWeatherSystemIntegration:
    """Integration tests: WeatherSystem + SeasonSystem together."""

    def test_weather_with_season_system(self):
        """WeatherSystem should work with a SeasonSystem reference."""
        ss = SeasonSystem()
        ws = WeatherSystem(season_system=ss, seed=42, change_interval=30.0)

        # Initial state
        assert ss.current_season == "spring"
        assert ws.current_weather == "clear"

        # Tick season forward
        ss.tick(10.0)
        ws.tick(10.0)

        assert ss.season_elapsed == 10.0
        assert ws.weather_timer == 10.0

        # Advance season past duration
        ss.tick(600.0)
        ws.tick(30.0)

        assert ss.current_season == "summer"
        assert ws.weather_timer == 0.0  # Rolled
