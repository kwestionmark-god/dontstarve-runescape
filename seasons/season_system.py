"""
season_system.py — Season cycle management.

Owns season identity, progress within season, transitions, and query APIs.
Does NOT own pygame drawing or input.
"""

from __future__ import annotations
from typing import Any
import math

# Defaults (can be overridden from config)
DEFAULT_SEASON_DURATION = 600.0
DEFAULT_SEASON_TRANSITION = 30.0
DEFAULT_SEASON_ORDER = ("spring", "summer", "autumn", "winter")
DEFAULT_SEASON_TRANSITIONS = {
    "spring": "summer",
    "summer": "autumn",
    "autumn": "winter",
    "winter": "spring",
}

# Default survival modifiers per season
# Keys: hunger_drain, regrowth, foraging, spoilage, cold, heat
DEFAULT_SURVIVAL_MODIFIERS: dict[str, dict[str, float]] = {
    "spring": {"hunger_drain": 1.0, "regrowth": 1.5, "foraging": 1.2, "spoilage": 1.0, "cold": 0.0, "heat": 0.0},
    "summer": {"hunger_drain": 1.2, "regrowth": 1.0, "foraging": 0.9, "spoilage": 1.3, "cold": 0.0, "heat": 1.0},
    "autumn": {"hunger_drain": 1.1, "regrowth": 0.8, "foraging": 1.3, "spoilage": 1.1, "cold": 0.3, "heat": 0.0},
    "winter": {"hunger_drain": 1.3, "regrowth": 0.4, "foraging": 0.6, "spoilage": 0.7, "cold": 1.0, "heat": 0.0},
}

# Default resource category multipliers per season
DEFAULT_RESOURCE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "spring": {"herbs": 1.2, "water": 1.1, "wood": 1.0, "stone": 1.0, "ore": 0.9},
    "summer": {"herbs": 1.0, "water": 0.8, "wood": 1.1, "stone": 1.0, "ore": 1.0},
    "autumn": {"herbs": 1.3, "water": 1.0, "wood": 0.9, "stone": 1.1, "ore": 1.0},
    "winter": {"herbs": 0.5, "water": 0.6, "wood": 0.7, "stone": 1.0, "ore": 0.8},
}

# Day/night cycle defaults
DEFAULT_DAY_DURATION = 1200.0        # Full day/night cycle (20 min)
DEFAULT_SUNRISE_HOUR = 6.0           # Time-of-day 0.25
DEFAULT_SUNSET_HOUR = 18.0           # Time-of-day 0.75
DEFAULT_SUN_ALTITUDE_MIN = -30.0     # Degrees at midnight
DEFAULT_SUN_ALTITUDE_MAX = 30.0      # Degrees at noon
DEFAULT_SUN_AZIMUTH = 45.0           # Degrees from north (0=N, 90=E)
DEFAULT_NIGHT_AMBIENT_LEVEL = 0.15   # Minimum ambient at night (0-1)
DEFAULT_DAY_AMBIENT_LEVEL = 0.45     # Maximum ambient at noon (0-1)

# Seasonal lighting profiles
DEFAULT_SEASON_LIGHTING: dict[str, dict[str, tuple[int, int, int]]] = {
    "spring":  {"ambient": (230, 240, 220), "sun_color": (255, 240, 200), "fog_tint": (180, 210, 190)},
    "summer":  {"ambient": (245, 235, 210), "sun_color": (255, 245, 220), "fog_tint": (200, 190, 160)},
    "autumn":  {"ambient": (235, 220, 190), "sun_color": (255, 200, 140), "fog_tint": (180, 160, 130)},
    "winter":  {"ambient": (200, 220, 240), "sun_color": (220, 235, 255), "fog_tint": (160, 180, 200)},
}


class SeasonSystem:
    """Manages the four-season cycle, progress, transitions, and time-of-day."""

    def __init__(
        self,
        seed: int = 42,
        season_duration: float = DEFAULT_SEASON_DURATION,
        season_transition: float = DEFAULT_SEASON_TRANSITION,
        season_order: tuple[str, ...] = DEFAULT_SEASON_ORDER,
        season_transitions: dict[str, str] | None = None,
        survival_modifiers: dict[str, dict[str, float]] | None = None,
        resource_multipliers: dict[str, dict[str, float]] | None = None,
        day_duration: float = DEFAULT_DAY_DURATION,
        sunrise_hour: float = DEFAULT_SUNRISE_HOUR,
        sunset_hour: float = DEFAULT_SUNSET_HOUR,
        sun_altitude_min: float = DEFAULT_SUN_ALTITUDE_MIN,
        sun_altitude_max: float = DEFAULT_SUN_ALTITUDE_MAX,
        sun_azimuth: float = DEFAULT_SUN_AZIMUTH,
        night_ambient_level: float = DEFAULT_NIGHT_AMBIENT_LEVEL,
        day_ambient_level: float = DEFAULT_DAY_AMBIENT_LEVEL,
        season_lighting: dict[str, dict[str, tuple[int, int, int]]] | None = None,
    ) -> None:
        self.seed = seed
        self.season_duration = season_duration
        self.season_transition = season_transition
        self.season_order = season_order
        self.season_transitions = season_transitions if season_transitions is not None else DEFAULT_SEASON_TRANSITIONS

        self.current_season: str = season_order[0]
        self.season_progress: float = 0.0
        self.season_elapsed: float = 0.0
        self.transition_blend: float = 0.0
        self.previous_season: str | None = None

        # Survival and resource modifiers
        self.survival_modifiers: dict[str, dict[str, float]] = (
            survival_modifiers if survival_modifiers is not None else DEFAULT_SURVIVAL_MODIFIERS
        )
        self.resource_multipliers: dict[str, dict[str, float]] = (
            resource_multipliers if resource_multipliers is not None else DEFAULT_RESOURCE_MULTIPLIERS
        )
        self.availability: dict[str, list[str]] = {}

        # Day/night cycle
        self.day_duration = day_duration
        self.sunrise_hour = sunrise_hour
        self.sunset_hour = sunset_hour
        self.sun_altitude_min = sun_altitude_min
        self.sun_altitude_max = sun_altitude_max
        self.sun_azimuth = sun_azimuth
        self.night_ambient_level = night_ambient_level
        self.day_ambient_level = day_ambient_level
        self.season_lighting = season_lighting if season_lighting is not None else DEFAULT_SEASON_LIGHTING

        # Time-of-day state
        self.time_of_day: float = 0.5  # Start at noon
        self.day_elapsed: float = self.day_duration * 0.5

        # Season-change callbacks
        self._on_season_changed: list[callable] = []

    def tick(self, dt: float) -> None:
        """Advance elapsed/progress; handle season rollover; update time-of-day."""
        # Season tick
        self.season_elapsed += dt
        self.season_progress = min(self.season_elapsed / self.season_duration, 1.0)

        if self.season_elapsed >= self.season_duration and self.transition_blend <= 0.0:
            self._on_season_rollover()

        if self.transition_blend > 0.0:
            self.transition_blend = max(0.0, self.transition_blend - dt / self.season_transition)

        # Time-of-day tick (independent of season)
        self.day_elapsed = (self.day_elapsed + dt) % self.day_duration
        self.time_of_day = self.day_elapsed / self.day_duration

    def _on_season_rollover(self) -> None:
        """Handle transition to the next season."""
        self.previous_season = self.current_season
        next_season = self.season_transitions.get(self.current_season, self.season_order[0])
        self.current_season = next_season
        self.season_elapsed = 0.0
        self.season_progress = 0.0
        self.transition_blend = 1.0

        for callback in self._on_season_changed:
            try:
                callback(self.current_season, self.previous_season)
            except Exception:
                pass

    def get_survival_modifiers(self) -> dict[str, float]:
        """Return survival modifiers for the current season."""
        if self.survival_modifiers:
            return self.survival_modifiers.get(self.current_season, {})
        return {
            "hunger_drain": 1.0,
            "regrowth": 1.0,
            "foraging": 1.0,
            "spoilage": 1.0,
            "cold": 0.0,
            "heat": 0.0,
        }

    def get_resource_multiplier(self, category: str) -> float:
        """Return spawn/yield scalar for a resource category."""
        if self.resource_multipliers:
            season_data = self.resource_multipliers.get(self.current_season, {})
            return season_data.get(category, 1.0)
        return 1.0

    def is_resource_available(self, resource_id: str) -> bool:
        """Check if a resource is available in the current season."""
        if not self.availability:
            return True
        allowed_seasons = self.availability.get(resource_id, [])
        if not allowed_seasons:
            return True
        return self.current_season in allowed_seasons

    def on_season_changed(self, callback: callable) -> None:
        """Register a callback to be called when a season changes."""
        self._on_season_changed.append(callback)

    def get_lighting_params(self) -> dict:
        """
        Returns lighting parameters for current season + time-of-day.
        
        Returns dict with:
            sun_direction: (x, y, z) world-space unit vector
            sun_altitude: radians
            ambient_color: (r, g, b)
            ambient_level: 0.0-1.0
            sun_color: (r, g, b)
            fog_tint: (r, g, b)
        """
        profile = self.season_lighting[self.current_season]
        t = self.time_of_day

        # Canonical solar math lives in render.lighting_system (single source).
        from render.lighting_system import compute_ambient_level, compute_sun_direction

        sun_dir, sun_alt = compute_sun_direction(
            t, self.sun_azimuth, self.sun_altitude_min, self.sun_altitude_max,
        )
        ambient_level = compute_ambient_level(
            t, self.night_ambient_level, self.day_ambient_level,
        )
        
        return {
            "sun_direction": sun_dir,
            "sun_altitude": sun_alt,
            "ambient_color": profile["ambient"],
            "ambient_level": ambient_level,
            "sun_color": profile["sun_color"],
            "fog_tint": profile["fog_tint"],
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize season state for save/load."""
        return {
            "current": self.current_season,
            "progress": self.season_progress,
            "elapsed": self.season_elapsed,
            "previous": self.previous_season,
            "transition_blend": self.transition_blend,
            "time_of_day": self.time_of_day,
            "day_elapsed": self.day_elapsed,
            "survival_modifiers": self.survival_modifiers,
            "resource_multipliers": self.resource_multipliers,
            "availability": self.availability,
        }
