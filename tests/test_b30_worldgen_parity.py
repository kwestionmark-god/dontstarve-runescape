"""Phase 5C: world-gen vectorization parity + determinism tests.

- pnoise2_grid must match noise.pnoise2(octaves=1) exactly (bitwise).
- World generation must be deterministic across processes (PYTHONHASHSEED).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestNoiseParity:
    @pytest.mark.parametrize("base", [0, 3, 42, 542, 1042, 2042, 5042])
    def test_pnoise2_grid_matches_c_extension(self, base: int) -> None:
        import noise

        from world.noise_np import pnoise2_grid

        rng = np.random.default_rng(base)
        xs = rng.uniform(-300, 300, size=5000)
        ys = rng.uniform(-300, 300, size=5000)
        got = pnoise2_grid(xs, ys, 10000.0, 10000.0, base)
        ref = np.array(
            [noise.pnoise2(float(x), float(y), octaves=1, repeatx=10000, repeaty=10000, base=base)
             for x, y in zip(xs, ys)],
            dtype=np.float32,
        )
        assert np.array_equal(got, ref)


def _fingerprint(size: int, seed: int, hashseed: str) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO
    env["SDL_VIDEODRIVER"] = "dummy"
    env["PYTHONHASHSEED"] = hashseed
    out = subprocess.run(
        [sys.executable, "-c", f"""
import json, sys
sys.path.insert(0, {REPO!r})
import world.world_gen as world_gen
from data import load_json_list
from world.biome import BiomeRegistry
world_gen.MAP_WIDTH = {size}; world_gen.MAP_HEIGHT = {size}
tm = world_gen.generate({seed}, BiomeRegistry(load_json_list("biomes.json", "biomes")))
biomes = []
nodes = []
blends = []
for x in range(tm.width):
    for y in range(tm.height):
        t = tm.tiles[x][y]
        biomes.append(t.biome.id if t.biome else None)
        if t.blended_spawns:
            blends.append((t.blended_spawns, x, y))
        if t.resource_node:
            nodes.append((x, y, t.resource_node.resource_id))
print(json.dumps([biomes, nodes, blends, tm.spawn_x, tm.spawn_y]))
"""],
        capture_output=True, text=True, env=env, cwd=REPO, timeout=300,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    # last line is the JSON (first lines are pygame's banner)
    return json.loads(out.stdout.strip().splitlines()[-1])


class TestWorldDeterminism:
    def test_same_seed_identical_worlds_across_hash_seeds(self) -> None:
        a = _fingerprint(64, 42, "1")
        b = _fingerprint(64, 42, "12345")
        assert a == b

    def test_different_seed_differs(self) -> None:
        a = _fingerprint(64, 42, "1")
        b = _fingerprint(64, 43, "1")
        assert a != b
