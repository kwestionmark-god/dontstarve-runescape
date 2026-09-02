"""Render the loading screen headlessly at sample progress values."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import WINDOW_WIDTH, WINDOW_HEIGHT  # noqa: E402
from core.state import GameState  # noqa: E402
from ui.loading_screen import render_loading_screen  # noqa: E402


class _FakeGame:
    def __init__(self, progress):
        self.loading_progress = progress
        self.seed = 42
        self.state = GameState.LOADING
        self.world = None


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "shots/loading"
    os.makedirs(outdir, exist_ok=True)
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    # Advance the particle time so the scene isn't empty
    import ui.loading_screen as ls
    for p, label in [(0.36, "p36"), (0.72, "p72")]:
        for _ in range(90):
            ls._get_loading_state().update(1 / 60)
        game = _FakeGame(p)
        render_loading_screen(game, screen)
        pygame.image.save(screen, os.path.join(outdir, f"loading_{label}.png"))
        print("saved", label)


if __name__ == "__main__":
    main()
