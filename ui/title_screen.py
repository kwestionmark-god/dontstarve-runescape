"""
ui/title_screen.py — Title screen rendering and event handling.

Extracted from core.game.Game in Phase 3.5.8.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.game import Game

from config import FLAVOR_TEXTS
from core.state import GameState
from render.font_cache import get_monospace, get_monospace_bold


def render_title_screen(game: "Game", screen: pygame.Surface) -> None:
    """
    Render the title screen UI.

    Stub: draws a dark background with the game title.
    Full implementation will include logo, buttons, seed display.

    Args:
        game: The Game instance (provides seed, save_system).
        screen: The pygame display surface.
    """
    screen.fill((20, 20, 30))  # Dark background

    # Title text (placeholder — font loaded in S1)
    font = get_monospace_bold(48)
    title_surf = font.render("Don't Starve RuneScape", True, (200, 180, 120))
    title_rect = title_surf.get_rect(center=(screen.get_width() // 2, 200))
    screen.blit(title_surf, title_rect)

    # Seed display
    seed_font = get_monospace(24)
    seed_surf = seed_font.render(f"Seed: {game.seed}", True, (150, 150, 150))
    seed_rect = seed_surf.get_rect(center=(screen.get_width() // 2, 280))
    screen.blit(seed_surf, seed_rect)

    # Populate save slots from save system
    if game.save_system:
        game._save_slots = game.save_system.list_slots()

    # Button hints
    hint_font = get_monospace(20)
    new_game = hint_font.render("Press ENTER or SPACE for New Game", True, (200, 200, 200))
    new_game_rect = new_game.get_rect(center=(screen.get_width() // 2, 360))
    screen.blit(new_game, new_game_rect)

    continue_text = hint_font.render("Press C to Continue (if saves exist)", True, (150, 150, 150))
    continue_rect = continue_text.get_rect(center=(screen.get_width() // 2, 400))
    screen.blit(continue_text, continue_rect)


def handle_title_event(game: "Game", event) -> None:
    """Handle events during the TITLE state."""
    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            game.set_state(GameState.LOADING)
        elif event.key == pygame.K_c:
            if game._save_slots:
                game.set_state(GameState.LOADING_SAVE)
