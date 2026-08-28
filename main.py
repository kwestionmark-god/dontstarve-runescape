"""
main.py — Entry point for Don't Starve RuneScape.

Bootstraps the Game instance and starts the main event loop.
World generation is deferred until the player initiates from the title screen.
"""

import sys
import argparse
import pygame

from core.game import Game
from core.game_loop import run


def main() -> None:
    """Parse arguments, create the Game, and start the loop."""
    parser = argparse.ArgumentParser(description="Don't Starve RuneScape")
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="World generation seed (default: 42)",
    )
    args = parser.parse_args()

    game = Game(seed=args.seed)
    try:
        run(game)
    finally:
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    main()
