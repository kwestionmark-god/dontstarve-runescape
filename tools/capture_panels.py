"""
capture_panels.py — Headless panel audit harness.

Boots the game off-screen, opens each UI panel via the real GameState
transitions, renders a frame per panel, catches render exceptions, and
saves a screenshot per panel for visual review.

Usage:
    SDL_VIDEODRIVER=dummy python tools/capture_panels.py --outdir shots/panels
"""

import argparse
import os
import sys
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.game import Game
from core.state import GameState
from tools.capture_shots import wait_for_world

# (label, state) — one screenshot per panel state
PANEL_STATES = [
    ("inventory", GameState.INVENTORY_OPEN),
    ("skills", GameState.SKILL_PANEL),
    ("crafting", GameState.CRAFTING_PANEL),
    ("building", GameState.BUILDING_PANEL),
    ("gear", GameState.GEAR_PANEL),
    ("trade", GameState.TRADE_PANEL),
    ("quest", GameState.QUEST_PANEL),
    ("recruit", GameState.RECRUIT_PANEL),
    ("diplomacy", GameState.DIPLOMACY_PANEL),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="shots/panels")
    parser.add_argument("--slot", type=int, default=0)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((1280, 800))

    game = Game(seed=42)
    game.set_state(GameState.LOADING_SAVE)
    wait_for_world(game)
    for _ in range(5):
        game.update(1.0 / 60.0)

    failures = 0
    for label, state in PANEL_STATES:
        try:
            game.set_state(state)
            game.update(1.0 / 60.0)
            game.render(game.screen)
            pygame.image.save(game.screen, os.path.join(args.outdir, f"{label}.png"))
            print(f"ok    {label}")
        except Exception:
            failures += 1
            print(f"FAIL  {label}")
            traceback.print_exc()
        finally:
            try:
                game.set_state(GameState.PLAYING)
            except Exception:
                traceback.print_exc()
    print(f"done: {len(PANEL_STATES) - failures} ok, {failures} failed")
    pygame.quit()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
