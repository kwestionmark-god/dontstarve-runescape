"""
weather_system.py — Weather state machine.

Manages weather state, weights by season/biome, effect queries, and forecast history.
Depends on SeasonSystem for the current season lookup; does not own pygame drawing.
"""

from __future__ import annotations
import random
from typing import Any

from config import WEATHER_CHANGE_INTERVAL, WEATHER_WEIGHTS, CLOUD_SHADOW_STRENGTH, LIGHTNING_FLASH_DURATION_MS, LIGHTNING_FLASH_ALPHA

DEFAULT_WEATHER_TYPES = ("clear", "rain", "snow", "storm", "fog")


class WeatherSystem:
    """Weather state machine with seasonal weights and forecast."""

    def __init__(
        self,
        season_system: "SeasonSystem | None" = None,
        seed: int = 42,
        weather_types: tuple[str, ...] = DEFAULT_WEATHER_TYPES,
        change_interval: float = WEATHER_CHANGE_INTERVAL,
        spawn_weights: dict[str, tuple[float, ...]] | None = None,
    ) -> None:
        self.season_system = season_system
        self.seed = seed
        self._rng = random.Random(seed)
        self.weather_types = weather_types
        self.change_interval = change_interval

        # Season → biome → weights mapping (optional; falls back to config.WEATHER_WEIGHTS)
        self.spawn_weights: dict[str, tuple[float, ...]] = spawn_weights or {}

        self.current_weather: str = "clear"
        self.weather_timer: float = 0.0
        self.weather_history: list[str] = []

    def tick(self, dt: float) -> None:
        """Countdown; roll weather when timer expires."""
        self.weather_timer += dt
        if self.weather_timer >= self.change_interval:
            self.weather_timer = 0.0
            self._roll_weather()

    def _roll_weather(self) -> None:
        """Roll new weather based on current season weights."""
        if self.season_system is None:
            self.current_weather = self._rng.choices(
                self.weather_types, weights=[1.0] * len(self.weather_types), k=1
            )[0]
        else:
            season = self.season_system.current_season
            weights = (self.spawn_weights or WEATHER_WEIGHTS).get(season)
            if weights is not None and sum(weights) > 0:
                self.current_weather = self._rng.choices(
                    self.weather_types, weights=weights, k=1
                )[0]
            else:
                self.current_weather = self.weather_types[0]  # Default: clear
        self.weather_history.append(self.current_weather)
        if len(self.weather_history) > 10:
            self.weather_history.pop(0)

    def get_effects(self) -> dict[str, float]:
        """Return weather effects as multipliers (including lighting)."""
        effects: dict[str, float] = {
            "movement_speed": 1.0,
            "visibility": 1.0,
            "outdoor_crafting": 1.0,
            "spawn_mod": 1.0,
            "light_level": 1.0,
            "cloud_coverage": 0.0,
            "rain_intensity": 0.0,
            "lightning_chance": 0.0,
        }
        if self.current_weather == "rain":
            effects["movement_speed"] = 0.9
            effects["visibility"] = 0.85
            effects["outdoor_crafting"] = 0.0
            effects["spawn_mod"] = 1.2
            effects["light_level"] = 0.7
            effects["cloud_coverage"] = 0.8
            effects["rain_intensity"] = 0.6
        elif self.current_weather == "snow":
            effects["movement_speed"] = 0.8
            effects["visibility"] = 0.70
            effects["outdoor_crafting"] = 0.0
            effects["spawn_mod"] = 0.7
            effects["light_level"] = 1.1   # Snow brightens
            effects["cloud_coverage"] = 0.9
        elif self.current_weather == "storm":
            effects["movement_speed"] = 0.7
            effects["visibility"] = 0.50
            effects["outdoor_crafting"] = 0.3
            effects["spawn_mod"] = 0.5
            effects["light_level"] = 0.4
            effects["cloud_coverage"] = 1.0
            effects["rain_intensity"] = 1.0
            effects["lightning_chance"] = 0.02   # Per frame at 60fps ≈ 1.2/sec
        elif self.current_weather == "fog":
            effects["movement_speed"] = 0.9
            effects["visibility"] = 0.40
            effects["outdoor_crafting"] = 1.0
            effects["spawn_mod"] = 1.1
            effects["light_level"] = 0.85
            effects["cloud_coverage"] = 0.3
        return effects

    def set_season_system(
        self, season_system: "SeasonSystem | None",
    ) -> None:
        """Set or replace the season system reference (set by bootstrap)."""
        self.season_system = season_system

    def get_forecast(self, n: int = 3) -> list[str]:
        """Return recent weather history (last n entries)."""
        return self.weather_history[-n:]

    def to_dict(self) -> dict[str, Any]:
        """Serialize weather state for save/load."""
        return {
            "current": self.current_weather,
            "timer": self.weather_timer,
            "history": self.weather_history,
        }
