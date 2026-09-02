"""
capture_warp_check.py — Synthetic terrain render check for the quad warp.

Builds a small TileMap with gentle rolling terraces, renders it through
the real TileRenderer.render() (depth-sorted textured path) once with
terrain_warp off and once on, and saves one screenshot per combo.

Usage:
    SDL_VIDEODRIVER=dummy python tools/capture_warp_check.py --outdir shots/warp
"""

import argparse
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from camera.camera import Camera  # noqa: E402
from render.tile_renderer import TileRenderer  # noqa: E402
from world.tile_map import TileMap  # noqa: E402


class _Player:
    def __init__(self, x, y):
        self.world_x = x
        self.world_y = y


def build_map() -> TileMap:
    size = 20
    tm = TileMap(size, size, spawn_x=size // 2, spawn_y=size // 2)
    for x in range(size):
        for y in range(size):
            # Rolling hills: broad sine bumps plus small terraces — big
            # enough relief to see, gentle enough to stay readable.
            elev = int(6 + 5 * math.sin(x / 4.0) + 4 * math.cos(y / 5.0)
                       + 6 * math.sin((x + y) / 7.0))
            tile = tm.tiles[x][y]
            tile.elevation = max(0, elev)
            tile.terrain_color = (88, 132, 72)
    tm.bake_corner_heights()
    return tm


class _WarpToggle:
    """Lighting-system stand-in that only carries preset flags."""

    def __init__(self, warp: bool):
        self.preset_config = {
            "terrain_style": "textured", "terrain_subdiv": 2,
            "terrain_lod": False, "terrain_warp": warp,
            "ao": False, "rim": False, "height_fog": False,
        }
        self.sun_direction = (-0.5, -1.0, 0.7)

    def compute_all_corner_shading(self, tile_map, lx, ly, lz):
        return None, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="shots/warp")
    args = parser.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    pygame.init()
    pygame.display.set_mode((800, 600))

    tm = build_map()
    cam = Camera(800, 600)
    cam.set_player(_Player(7 * 64, 9 * 64))
    cam.zoom = 1.6
    cam.pitch = math.radians(30)

    for warp in (False, True):
        for yaw_deg in (0, 35):
            screen = pygame.Surface((800, 600))
            screen.fill((35, 45, 60))
            cam.yaw = math.radians(yaw_deg)
            renderer = TileRenderer(tm, screen, lighting_system=_WarpToggle(warp))
            renderer.render(cam)
            name = f"warp{int(warp)}_yaw{yaw_deg}.png"
            pygame.image.save(screen, os.path.join(args.outdir, name))
            print(f"saved {name}")

    pygame.quit()


if __name__ == "__main__":
    main()
