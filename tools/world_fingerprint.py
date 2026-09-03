"""tools/world_fingerprint.py — snapshot a generated world for parity checks.

Generates a world (small map override for speed) and writes a deterministic
JSON fingerprint covering every stage output 5C/5D must preserve:

- elevation + moisture (raw stage outputs, exact repr)
- per-tile biome ids and blended_spawns (sorted — set-order independent)
- resource node placements (resource_id, depletion, position)
- baked corner grids (heights, fog, AO)
- spawn point

Usage:
    python tools/world_fingerprint.py --size 128 --seed 42 --out tmp/fp.json
    python tools/world_fingerprint.py --size 128 --seed 42 --check tmp/fp.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

import world.tile_map as tile_map_mod
import world.world_gen as world_gen


def _snapshot(tile_map, elevation, moisture) -> dict:
    w, h = tile_map.width, tile_map.height
    biome_ids = []
    blended = []
    nodes = []
    for x in range(w):
        for y in range(h):
            tile = tile_map.tiles[x][y]
            biome_ids.append(tile.biome.id if tile.biome else "∅")
            blended.append(sorted(tile.blended_spawns) if tile.blended_spawns else None)
            n = tile.resource_node
            if n is not None:
                nodes.append([x, y, n.resource_id, n.current_depletions, n.regrow_time])
    return {
        "elevation": [[repr(v) for v in col] for col in elevation],
        "moisture": [[repr(v) for v in col] for col in moisture],
        "biomes": biome_ids,
        "blended": blended,
        "nodes": nodes,
        "corner_height": [[repr(v) for v in col] for col in tile_map.corner_height],
        "corner_fog": [[repr(v) for v in col] for col in tile_map.corner_fog],
        "corner_ao": [[repr(v) for v in col] for col in tile_map.corner_ao],
        "spawn": [tile_map.spawn_x, tile_map.spawn_y],
    }


def build_fingerprint(size: int, seed: int) -> dict:
    from data import load_json_list
    from world.biome import BiomeRegistry

    world_gen.MAP_WIDTH = size
    world_gen.MAP_HEIGHT = size
    registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))

    # Capture raw stage outputs for exact comparison.
    elevation = world_gen._generate_elevation_map(seed, size, size)
    moisture = world_gen._generate_moisture_map(seed, size, size)
    # Continue the full pipeline (recomputes the stages identically).
    tile_map = world_gen.generate(seed, registry)
    return _snapshot(tile_map, elevation, moisture)


def _diff(a: dict, b: dict, key: str) -> str | None:
    if a[key] == b[key]:
        return None
    if key in ("elevation", "moisture", "corner_height", "corner_fog", "corner_ao"):
        for x, (ca, cb) in enumerate(zip(a[key], b[key])):
            for y, (va, vb) in enumerate(zip(ca, cb)):
                if va != vb:
                    return f"{key} differs at ({x},{y}): {va} vs {vb}"
        return f"{key} shape differs"
    if key in ("biomes", "blended", "nodes"):
        for i, (va, vb) in enumerate(zip(a[key], b[key])):
            if va != vb:
                return f"{key} differs at index {i}: {va} vs {vb}"
        return f"{key} length differs"
    return f"{key} differs: {a[key]} vs {b[key]}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--size", type=int, default=128)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default=None, help="write fingerprint JSON")
    p.add_argument("--check", default=None, help="compare against a fingerprint JSON")
    args = p.parse_args()

    fp = build_fingerprint(args.size, args.seed)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(fp, f)
        digest = hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()[:16]
        print(f"fingerprint written to {args.out} (sha256:{digest})")
        return 0

    if args.check:
        with open(args.check) as f:
            ref = json.load(f)
        bad = False
        for key in ref:
            msg = _diff(ref, fp, key)
            if msg:
                print(f"MISMATCH: {msg}")
                bad = True
        if bad:
            return 1
        print("fingerprint matches")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
