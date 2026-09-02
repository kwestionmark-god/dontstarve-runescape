"""
capture_relief.py — Capture the real game world at its steepest terrain.

Loads save slot 0 like tools/capture_shots.py, then finds the 3x3 tile
neighbourhood with the largest baked corner-height spread, moves the
player there, and renders a few camera angles.

Usage:
    python tools/capture_relief.py --outdir shots/relief
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
from tools.capture_shots import wait_for_world  # noqa: E402


def steepest_spot(game: Game, radius: int = 2) -> tuple[int, int]:
    tm = game.world
    ch = tm.corner_height
    best, best_spread = (tm.width // 2, tm.height // 2), -1.0
    for x in range(2, tm.width - 2, 2):
        for y in range(2, tm.height - 2, 2):
            vals = [ch[x + dx][y + dy]
                    for dx in range(-radius, radius + 1)
                    for dy in range(-radius, radius + 1)]
            spread = max(vals) - min(vals)
            if spread > best_spread:
                best_spread = spread
                best = (x, y)
    # Water/beach tiles ruin readability; keep best regardless.
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="shots/relief")
    parser.add_argument("--slot", type=int, default=0)
    args = parser.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    pygame.init()
    pygame.display.set_mode((1280, 800))

    game = Game(seed=42)
    game.set_state(GameState.LOADING_SAVE)
    wait_for_world(game)
    for _ in enumerate(range(5)):
        game.update(1.0 / 60.0)

    tx, ty = steepest_spot(game)
    game.player.world_x = tx * 64 + 32
    game.player.world_y = ty * 64 + 32
    print(f"steepest spot: tile ({tx}, {ty})")

    cam = game.camera
    screen = game.screen
    for label, yaw_deg, pitch_deg, zoom in [
        ("yaw0", 0, 30, 1.2),
        ("yaw35", 35, 30, 1.2),
        ("yaw35_steps", 35, 50, 1.6),
        ("yaw180", 180, 30, 1.2),
    ]:
        cam.yaw = math.radians(yaw_deg)
        cam.pitch = math.radians(pitch_deg)
        cam.zoom = zoom
        game.render_game(screen)
        pygame.image.save(screen, os.path.join(args.outdir, f"{label}.png"))
        print(f"saved {label}.png")

    pygame.quit()


if __name__ == "__main__":
    main()
