"""
game_loop.py — Main Pygame event loop.

Drives the game clock, processes events, and delegates update/render
to the Game instance. Skips update during TITLE and LOADING states.
"""

import pygame

from config import TARGET_FPS
from core.state import GameState


def run(game) -> None:
    """
    Run the main game loop.

    Args:
        game: A Game instance (from core.game).
    """
    running = True
    while running:
        dt = game.clock.tick(TARGET_FPS) / 1000.0  # FPS cap from config, dt in seconds

        # ── Event handling ──────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            game.handle_event(event)

        # ── Update: skip during TITLE and LOADING states ────────────
        if game.state not in (GameState.TITLE, GameState.LOADING, GameState.LOADING_SAVE):
            game.update(dt)

        # ── Render: dispatch based on state ─────────────────────────
        game.render(game.screen)
        pygame.display.flip()
