"""
capture_shots.py — Headless screenshot harness.

Boots the game off-screen (SDL dummy video driver), loads save slot 0,
drives the camera through a set of (yaw_deg, pitch_deg, zoom) combos, and
renders one frame per combo into --outdir.

Usage:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
        python tools/capture_shots.py --outdir shots --timescale 0
"""

import argparse
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game import Game  # noqa: E402
from core.state import GameState  # noqa: E402

# (label, yaw_deg, pitch_deg, zoom)
COMBOS = [
    ("yaw0_p30", 0, 30, 1.0),
    ("yaw35_p30", 35, 30, 1.0),
    ("yaw110_p30", 110, 30, 1.0),
    ("yaw-40_p30", -40, 30, 1.0),
    ("yaw0_pmin", 0, 5, 1.0),
    ("yaw0_pmax", 0, 60, 1.0),
    ("yaw195_p45", 195, 45, 1.0),
    ("yaw35_zoomed", 35, 30, 2.0),
]


def wait_for_world(game: Game, frames: int = 3600) -> None:
    """Drive the loading state machine until PLAYING or failure."""
    for _ in range(frames):
        game.check_world_gen_complete()
        if game.state == GameState.PLAYING:
            return
        if game.state == GameState.ERROR:
            raise RuntimeError(f"World load failed: {game._world_gen_error}")
        pygame.time.wait(10)
    raise RuntimeError("Timed out waiting for world generation")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="shots")
    parser.add_argument("--slot", type=int, default=0)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((1280, 800))

    game = Game(seed=42)
    game.set_state(GameState.LOADING_SAVE)
    wait_for_world(game)

    # Run a few updates so HUD/particles/lighting settle.
    for _ in range(5):
        game.update(1.0 / 60.0)

    cam = game.camera
    screen = game.screen
    for label, yaw_deg, pitch_deg, zoom in COMBOS:
        cam.yaw = math.radians(yaw_deg)
        cam.pitch = math.radians(pitch_deg)
        cam.zoom = zoom
        game.render_game(screen)
        pygame.image.save(screen, os.path.join(args.outdir, f"{label}.png"))
        print(f"saved {label}.png")

    pygame.quit()


if __name__ == "__main__":
    main()
