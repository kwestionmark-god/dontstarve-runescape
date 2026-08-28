"""
season_system.py — Season cycle management.

Owns season identity, progress within season, transitions, and query APIs.
Does NOT own pygame drawing or input.
"""

from __future__ import annotations
from typing import Any

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


class SeasonSystem:
    """Manages the four-season cycle, progress, and transitions."""

    def __init__(
        self,
        seed: int = 42,
        season_duration: float = DEFAULT_SEASON_DURATION,
        season_transition: float = DEFAULT_SEASON_TRANSITION,
        season_order: tuple[str, ...] = DEFAULT_SEASON_ORDER,
        season_transitions: dict[str, str] | None = None,
        survival_modifiers: dict[str, dict[str, float]] | None = None,
        resource_multipliers: dict[str, dict[str, float]] | None = None,
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

        # Survival and resource modifiers (use defaults if not provided)
        self.survival_modifiers: dict[str, dict[str, float]] = (
            survival_modifiers if survival_modifiers is not None else DEFAULT_SURVIVAL_MODIFIERS
        )
        self.resource_multipliers: dict[str, dict[str, float]] = (
            resource_multipliers if resource_multipliers is not None else DEFAULT_RESOURCE_MULTIPLIERS
        )
        self.availability: dict[str, list[str]] = {}

        # Season-change callbacks (registered by other systems)
        self._on_season_changed: list[callable] = []

    def tick(self, dt: float) -> None:
        """Advance elapsed/progress; handle season rollover; update transition_blend."""
        self.season_elapsed += dt
        self.season_progress = min(self.season_elapsed / self.season_duration, 1.0)

        if self.season_elapsed >= self.season_duration and self.transition_blend <= 0.0:
            self._on_season_rollover()

        # Animate transition blend back to 0 after rollover
        if self.transition_blend > 0.0:
            self.transition_blend = max(0.0, self.transition_blend - dt / self.season_transition)

    def _on_season_rollover(self) -> None:
        """Handle transition to the next season."""
        self.previous_season = self.current_season
        next_season = self.season_transitions.get(self.current_season, self.season_order[0])
        self.current_season = next_season
        self.season_elapsed = 0.0
        self.season_progress = 0.0
        self.transition_blend = 1.0

        # Fire season-change callbacks
        for callback in self._on_season_changed:
            try:
                callback(self.current_season, self.previous_season)
            except Exception:
                pass  # Don't let callback errors break the season cycle

    def get_survival_modifiers(self) -> dict[str, float]:
        """Return survival modifiers for the current season."""
        if self.survival_modifiers:
            return self.survival_modifiers.get(self.current_season, {})
        # Default modifiers
        return {
            "hunger_drain": 1.0,
            "regrowth": 1.0,
            "foraging": 1.0,
            "spoilage": 1.0,
            "cold": 0.0,
            "heat": 0.0,
        }

    def get_resource_multiplier(self, category: str) -> float:
        """Return spawn/yield scalar for a resource category.

        Looks up the category directly in the season's resource_multipliers.
        Valid categories: 'wood', 'ore', 'herb', 'water', 'stone', 'special'.
        Falls back to 1.0 for unknown categories.

        Args:
            category: The resource category (e.g. 'wood', 'ore', 'herb').

        Returns:
            Density/yield multiplier for the current season.
        """
        if self.resource_multipliers:
            season_data = self.resource_multipliers.get(self.current_season, {})
            return season_data.get(category, 1.0)
        return 1.0

    def is_resource_available(self, resource_id: str) -> bool:
        """Check if a resource is available in the current season.

        This is a runtime override mechanism. The primary season gate is
        the ``seasons_available`` field on each ResourceNode in resources.json.
        This method checks the ``availability`` dict for dynamic overrides
        (e.g. events, quests, or developer testing).

        Args:
            resource_id: The resource ID to check.

        Returns:
            True if available, False otherwise.
        """
        if not self.availability:
            return True
        allowed_seasons = self.availability.get(resource_id, [])
        if not allowed_seasons:
            return True
        return self.current_season in allowed_seasons

    def on_season_changed(self, callback: callable) -> None:
        """Register a callback to be called when a season changes.

        Args:
            callback: Function that receives (new_season, previous_season).
        """
        self._on_season_changed.append(callback)

    def to_dict(self) -> dict[str, Any]:
        """Serialize season state for save/load."""
        return {
            "current": self.current_season,
            "progress": self.season_progress,
            "elapsed": self.season_elapsed,
            "previous": self.previous_season,
            "transition_blend": self.transition_blend,
            "survival_modifiers": self.survival_modifiers,
            "resource_multipliers": self.resource_multipliers,
            "availability": self.availability,
        }
