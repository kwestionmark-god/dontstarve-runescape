"""
seasonal_hud.py — Season and weather HUD helpers.

Provides season name/progress display, weather icon, and forecast tooltip.
Designed to be composed with HUD, not to replace it.
"""

from __future__ import annotations
import pygame

DEFAULT_HUD_SEASON_BAR_HEIGHT = 16
DEFAULT_HUD_SEASON_BAR_WIDTH = 200

# Season display colors
SEASON_COLORS = {
    "spring": (80, 200, 80),
    "summer": (240, 200, 50),
    "autumn": (200, 120, 40),
    "winter": (160, 200, 240),
}

# Weather icon characters (using simple text symbols)
WEATHER_ICONS = {
    "clear": "☀",
    "rain": "☂",
    "snow": "❄",
    "storm": "⚡",
    "fog": "☁",
}


class SeasonalHUD:
    """HUD helpers for displaying season and weather info."""

    def __init__(
        self,
        bar_width: int = DEFAULT_HUD_SEASON_BAR_WIDTH,
        bar_height: int = DEFAULT_HUD_SEASON_BAR_HEIGHT,
    ) -> None:
        self.bar_width = bar_width
        self.bar_height = bar_height
        self._font_small = pygame.font.SysFont("monospace", 14)
        self._font_medium = pygame.font.SysFont("monospace", 16)

    def render_season_bar(
        self,
        screen: any,
        season: str,
        progress: float,
        x: int = 10,
        y: int = 10,
    ) -> None:
        """Render a season progress bar in the top-left corner."""
        color = SEASON_COLORS.get(season, (200, 200, 200))

        # Background
        pygame.draw.rect(screen, (40, 40, 50), (x, y, self.bar_width, self.bar_height))
        # Fill
        fill_w = int(self.bar_width * progress)
        pygame.draw.rect(screen, color, (x, y, fill_w, self.bar_height))
        # Border
        pygame.draw.rect(screen, (150, 150, 160), (x, y, self.bar_width, self.bar_height), 1)

        # Season label
        label = self._font_small.render(season.capitalize(), True, (255, 255, 255))
        screen.blit(label, (x + 4, y + 2))

    def render_weather_icon(
        self,
        screen: any,
        weather: str,
        x: int = 10,
        y: int = 30,
    ) -> None:
        """Render a weather icon next to the season bar."""
        icon = WEATHER_ICONS.get(weather, "?")
        color = (200, 200, 200)
        surf = self._font_medium.render(icon, True, color)
        screen.blit(surf, (x, y))

    def render_forecast_tooltip(
        self,
        screen: any,
        forecast: list[str],
        x: int = 10,
        y: int = 50,
    ) -> None:
        """Render a small weather forecast (last 3 weather entries)."""
        if not forecast:
            return

        font = self._font_small
        for i, weather in enumerate(forecast[-3:]):
            icon = WEATHER_ICONS.get(weather, "?")
            surf = font.render(f"{icon}", True, (180, 180, 180))
            screen.blit(surf, (x + i * 16, y))
