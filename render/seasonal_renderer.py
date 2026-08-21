"""
seasonal_renderer.py — Seasonal terrain color blending.

Supplies palette blend factors, per-biome season colors, and ambient overlay
parameters. Does not own pygame drawing directly; provides colors/hooks for
TileRenderer and SpriteRenderer.
"""

from __future__ import annotations
from typing import Any


# Default biome × season color palettes (RGB tuples)
DEFAULT_PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "forest": {
        "spring": (40, 120, 40),
        "summer": (50, 140, 45),
        "autumn": (160, 100, 30),
        "winter": (180, 190, 200),
    },
    "plains": {
        "spring": (80, 160, 60),
        "summer": (140, 170, 50),
        "autumn": (170, 140, 40),
        "winter": (200, 200, 210),
    },
    "desert": {
        "spring": (210, 185, 130),
        "summer": (220, 195, 140),
        "autumn": (200, 175, 120),
        "winter": (180, 165, 140),
    },
    "mountains": {
        "spring": (120, 130, 140),
        "summer": (130, 140, 130),
        "autumn": (140, 120, 110),
        "winter": (215, 222, 230),
    },
    "coastal": {
        "spring": (120, 172, 192),
        "summer": (92, 160, 192),
        "autumn": (112, 152, 162),
        "winter": (150, 172, 182),
    },
    "swamp": {
        "spring": (92, 122, 72),
        "summer": (82, 112, 62),
        "autumn": (92, 102, 62),
        "winter": (72, 86, 82),
    },
}


class SeasonalRenderer:
    """Blends terrain colors across seasons using Lerp."""

    def __init__(self, palettes: dict[str, dict[str, tuple[int, int, int]]] | None = None) -> None:
        self.palettes = palettes or DEFAULT_PALETTES
        self._blend: float = 0.0
        self._current_season: str = "spring"
        self._previous_season: str | None = None

    def sync(
        self,
        season_progress: float,
        current_season: str,
        previous_season: str | None = None,
    ) -> None:
        """Sync renderer state from season system values."""
        self._current_season = current_season
        self._previous_season = previous_season
        self._blend = 1.0 - season_progress  # 1.0 = start of season, 0.0 = end

    def get_tile_color(self, biome_id: str, base_color: tuple[int, int, int]) -> tuple[int, int, int]:
        """Return the season-blended color for a tile."""
        season_colors = self.palettes.get(biome_id, {})
        if not season_colors:
            return base_color

        current = season_colors.get(self._current_season, base_color)
        if self._previous_season and self._blend > 0.0:
            previous = season_colors.get(self._previous_season, base_color)
            # Lerp between previous and current
            r = int(previous[0] + (current[0] - previous[0]) * (1.0 - self._blend))
            g = int(previous[1] + (current[1] - previous[1]) * (1.0 - self._blend))
            b = int(previous[2] + (current[2] - previous[2]) * (1.0 - self._blend))
            return (r, g, b)

        return current

    def draw_ambient_overlay(
        self,
        screen: Any,
        alpha: int = 40,
        color: tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """Draw a semi-transparent ambient overlay on the screen surface.

        Args:
            screen: Pygame surface to draw on.
            alpha: Overlay alpha (0–255).
            color: Overlay RGB color.
        """
        import pygame

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        screen.blit(overlay, (0, 0))
