"""Profile a continuous yaw pan: render N frames while sweeping yaw."""

import cProfile
import math
import os
import pstats
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game import Game  # noqa: E402
from core.state import GameState  # noqa: E402
from tools.capture_shots import wait_for_world  # noqa: E402

FRAMES = 40


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1280, 800))

    game = Game(seed=42)
    game.set_state(GameState.LOADING_SAVE)
    wait_for_world(game)
    for _ in range(5):
        game.update(1.0 / 60.0)

    cam = game.camera
    screen = game.screen

    # Warmup: settle caches at yaw 0.
    cam.yaw = 0.0
    game.render_game(screen)

    import time
    t0 = time.perf_counter()
    for i in range(FRAMES):
        cam.yaw += math.radians(90.0) * (1.0 / 60.0)
        game.render_game(screen)
    wall = time.perf_counter() - t0
    print(f"Wall (no profiler): {wall * 1000 / FRAMES:.2f} ms/frame")

    prof = cProfile.Profile()
    prof.enable()
    for i in range(FRAMES):
        # ~90 deg/s like CAMERA_ORBIT_SPEED
        cam.yaw += math.radians(90.0) * (1.0 / 60.0)
        game.render_game(screen)
    prof.disable()

    stats = pstats.Stats(prof)
    stats.sort_stats("cumulative").print_stats(25)
    total = stats.total_tt
    print(f"\nTotal: {total * 1000:.1f} ms for {FRAMES} frames "
          f"= {total * 1000 / FRAMES:.2f} ms/frame")


if __name__ == "__main__":
    main()
