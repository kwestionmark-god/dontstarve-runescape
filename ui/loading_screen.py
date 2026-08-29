"""
ui/loading_screen.py — Loading screen rendering and event handling.

Extracted from core.game.Game in Phase 3.5.9.
"""

from __future__ import annotations

import pygame
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.game import Game

from config import FLAVOR_TEXTS
from core.state import GameState
from render.font_cache import get_monospace, get_monospace_bold, get_monospace_italic


def render_loading_screen(game: "Game", screen: pygame.Surface) -> None:
    """
    Render the loading screen with progress bar.

    Shows a loading message and a progress bar filled
    proportionally to game.loading_progress (0.0 → 1.0).

    Args:
        game: The Game instance (provides loading_progress, seed, state).
        screen: The pygame display surface.
    """
    screen.fill((30, 30, 40))  # Slightly lighter dark

    # Loading text
    font = get_monospace_bold(36)
    if game.state == GameState.LOADING_SAVE:
        label = "Loading save..."
    else:
        label = "Generating world..."
    label_surf = font.render(label, True, (200, 200, 200))
    label_rect = label_surf.get_rect(center=(screen.get_width() // 2, 250))
    screen.blit(label_surf, label_rect)

    # Flavor text
    if not hasattr(game, "_flavor_text"):
        rng = random.Random(game.seed)
        game._flavor_text = rng.choice(FLAVOR_TEXTS)
    flavor_font = get_monospace_italic(16)
    flavor_surf = flavor_font.render(game._flavor_text, True, (150, 150, 170))
    flavor_rect = flavor_surf.get_rect(center=(screen.get_width() // 2, 290))
    screen.blit(flavor_surf, flavor_rect)

    # Progress bar background
    bar_width = 400
    bar_height = 20
    bar_x = (screen.get_width() - bar_width) // 2
    bar_y = 320
    pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_width, bar_height))

    # Progress bar fill
    fill_width = int(bar_width * game.loading_progress)
    pygame.draw.rect(screen, (80, 180, 80), (bar_x, bar_y, fill_width, bar_height))

    # Border
    pygame.draw.rect(screen, (120, 120, 120), (bar_x, bar_y, bar_width, bar_height), 2)

    # Percentage
    pct_font = get_monospace(18)
    pct_surf = pct_font.render(f"{int(game.loading_progress * 100)}%", True, (255, 255, 255))
    pct_rect = pct_surf.get_rect(center=(screen.get_width() // 2, 360))
    screen.blit(pct_surf, pct_rect)

    # Error state message
    if game.world is None and game.state == GameState.ERROR:
        error_font = get_monospace(24)
        error_surf = error_font.render(
            "World generation failed. Press Enter or Escape to return.", True, (255, 100, 100),
        )
        error_rect = error_surf.get_rect(center=(screen.get_width() // 2, 400))
        screen.blit(error_surf, error_rect)


def handle_loading_event(game: "Game", event) -> None:
    """Handle events during loading and error states."""
    if game.state == GameState.ERROR:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            game.state = GameState.TITLE
            game.world = None
            game.player = None
    # LOADING and LOADING_SAVE: no input needed
