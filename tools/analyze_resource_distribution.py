#!/usr/bin/env python3
"""
analyze_resource_distribution.py — Designer tool for resource placement analysis.

Simulates N world generations and outputs resource density statistics as CSV.
Used for balancing resource rarities, biome distributions, and seasonal availability.

Usage:
    python -m tools.analyze_resource_distribution --worlds 1000 --output dist.csv
    python -m tools.analyze_resource_distribution --worlds 100 --output dist.csv --season winter
    python -m tools.analyze_resource_distribution --worlds 500 --output dist.csv --biome mountains
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seasons.season_system import SeasonSystem
    from world.tile_map import TileMap

# Ensure we can import from project root
sys.path.insert(0, ".")

from config import MAP_WIDTH, MAP_HEIGHT
from seasons.season_system import SeasonSystem
from world.biome import BiomeRegistry
from world.resource_placer import ResourcePlacer
from world.world_gen import (
    generate, _generate_elevation_map, _generate_moisture_map, classify_biome,
    _build_tile_grid, _build_biome_transitions, _wire_seasonal_replacement, _find_spawn_point,
    NOISE_SCALE, ELEVATION_OCTAVES, MOISTURE_OCTAVES
)
from world.tile_map import TileMap, Tile


@dataclass
class ResourceStats:
    """Aggregated statistics for a single resource across multiple worlds."""
    resource_id: str
    rarity: str
    category: str
    biome: str
    seasons_available: list[str]
    total_count: int = 0
    world_count: int = 0
    min_count: int = sys.maxsize
    max_count: int = 0
    sum_squares: float = 0.0

    def add_world(self, count: int) -> None:
        self.total_count += count
        self.world_count += 1
        self.min_count = min(self.min_count, count)
        self.max_count = max(self.max_count, count)
        self.sum_squares += count * count

    @property
    def mean(self) -> float:
        return self.total_count / self.world_count if self.world_count > 0 else 0.0

    @property
    def std_dev(self) -> float:
        if self.world_count <= 1:
            return 0.0
        mean = self.mean
        variance = (self.sum_squares / self.world_count) - (mean * mean)
        return variance ** 0.5 if variance > 0 else 0.0

    @property
    def density_per_10k_tiles(self) -> float:
        """Expected count per 10,000 tiles (normalized for map size)."""
        # Use default map size for normalization
        tiles_per_world = MAP_WIDTH * MAP_HEIGHT
        return (self.mean / tiles_per_world) * 10000


def build_season_system(season: str | None) -> SeasonSystem | None:
    """Create a SeasonSystem locked to a specific season, or None for all seasons."""
    if season is None:
        return None
    ss = SeasonSystem()
    # Manually set the season
    if season in ss.season_order:
        ss.current_season = season
    return ss


def run_simulation(
    num_worlds: int,
    season: str | None = None,
    biome_filter: str | None = None,
    seed_base: int = 42,
    map_width: int = 128,
    map_height: int = 128,
    player_count: int = 1,
    density_multiplier: float = 1.0,
) -> dict[str, ResourceStats]:
    """
    Run multiple world generations and collect resource placement statistics.

    Args:
        num_worlds: Number of worlds to generate.
        season: Optional season to lock to (spring/summer/autumn/winter).
        biome_filter: Optional biome to filter results (e.g., "mountains").
        seed_base: Base seed; each world uses seed_base + i.
        map_width: Width of generated map in tiles (default: 128 for speed).
        map_height: Height of generated map in tiles (default: 128 for speed).
        player_count: Number of players (for dynamic density scaling).
        density_multiplier: Global density multiplier.

    Returns:
        Dict mapping resource_id -> ResourceStats.
    """
    from data import load_json_list

    biome_data = load_json_list("biomes.json", "biomes")
    biome_registry = BiomeRegistry(biome_data)
    season_system = build_season_system(season)

    # Preload resource definitions for metadata
    all_resources = load_json_list("resources.json", "resources")
    resource_defs = {r["id"]: r for r in all_resources}

    stats: dict[str, ResourceStats] = {}

    for i in range(num_worlds):
        seed = seed_base + i
        
        # Generate world with custom dimensions (faster for analysis)
        elevation_map = _generate_elevation_map(seed, map_width, map_height)
        moisture_map = _generate_moisture_map(seed, map_width, map_height)
        tile_map = _build_tile_grid(elevation_map, moisture_map, biome_registry, map_width, map_height)
        
        # Build biome transitions
        _build_biome_transitions(tile_map, biome_registry)
        
        # Place resources with multiplayer scaling
        placer = ResourcePlacer(
            rng=random.Random(seed), 
            season_system=season_system,
            player_count=player_count,
            density_multiplier=density_multiplier
        )
        placer.place(tile_map)
        
        # Seasonal replacement (if season_system provided)
        if season_system is not None:
            _wire_seasonal_replacement(tile_map, seed, season_system)
        
        # Find spawn point (needed for progression zones)
        spawn_x, spawn_y = _find_spawn_point(tile_map, seed)
        tile_map.spawn_x = spawn_x
        tile_map.spawn_y = spawn_y
        
        # Re-run resource placement with spawn point for zones
        ResourcePlacer(rng=random.Random(seed), season_system=season_system).place(tile_map)

        # Count resources
        world_counts: dict[str, int] = defaultdict(int)
        world_biomes: dict[str, str] = {}

        for x in range(tile_map.width):
            for y in range(tile_map.height):
                tile = tile_map.tiles[x][y]
                if tile.resource_node is not None:
                    rid = tile.resource_node.resource_id
                    if biome_filter is None or tile.biome.id == biome_filter:
                        world_counts[rid] += 1
                        world_biomes[rid] = tile.biome.id

        # Update stats
        for rid, count in world_counts.items():
            if rid not in stats:
                resource_def = resource_defs.get(rid)
                if resource_def:
                    stats[rid] = ResourceStats(
                        resource_id=rid,
                        rarity=resource_def.get("rarity", "common"),
                        category=resource_def.get("category", "special"),
                        biome=world_biomes.get(rid, "unknown"),
                        seasons_available=resource_def.get("seasons_available", []),
                    )
                else:
                    stats[rid] = ResourceStats(
                        resource_id=rid,
                        rarity="unknown",
                        category="unknown",
                        biome=world_biomes.get(rid, "unknown"),
                        seasons_available=[],
                    )
            stats[rid].add_world(count)

        # Also add zero counts for resources that didn't appear in this world
        # but are in our stats from previous worlds
        for rid in stats:
            if rid not in world_counts:
                stats[rid].add_world(0)

        if (i + 1) % 100 == 0:
            print(f"  Generated {i + 1}/{num_worlds} worlds...", file=sys.stderr)

    return stats


def write_csv(stats: dict[str, ResourceStats], output_path: str) -> None:
    """Write statistics to CSV file."""
    fieldnames = [
        "resource_id",
        "rarity",
        "category",
        "primary_biome",
        "seasons_available",
        "worlds_simulated",
        "mean_count",
        "std_dev",
        "min_count",
        "max_count",
        "density_per_10k_tiles",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Sort by rarity order, then by mean count descending
        rarity_order = {
            "ubiquitous": 0,
            "common": 1,
            "uncommon": 2,
            "rare": 3,
            "epic": 4,
            "legendary": 5,
            "unknown": 6,
        }

        sorted_stats = sorted(
            stats.values(),
            key=lambda s: (rarity_order.get(s.rarity, 6), -s.mean)
        )

        for s in sorted_stats:
            writer.writerow({
                "resource_id": s.resource_id,
                "rarity": s.rarity,
                "category": s.category,
                "primary_biome": s.biome,
                "seasons_available": ";".join(s.seasons_available) if s.seasons_available else "all",
                "worlds_simulated": s.world_count,
                "mean_count": round(s.mean, 2),
                "std_dev": round(s.std_dev, 2),
                "min_count": s.min_count if s.min_count != sys.maxsize else 0,
                "max_count": s.max_count,
                "density_per_10k_tiles": round(s.density_per_10k_tiles, 4),
            })


def print_summary(stats: dict[str, ResourceStats]) -> None:
    """Print a summary table to stderr."""
    print("\n=== Resource Distribution Summary ===", file=sys.stderr)
    print(f"{'Resource':<25} {'Rarity':<12} {'Category':<10} {'Biome':<12} {'Mean':>8} {'StdDev':>8} {'Min':>5} {'Max':>5}",
          file=sys.stderr)
    print("-" * 100, file=sys.stderr)

    rarity_order = {
        "ubiquitous": 0, "common": 1, "uncommon": 2,
        "rare": 3, "epic": 4, "legendary": 5, "unknown": 6,
    }
    sorted_stats = sorted(
        stats.values(),
        key=lambda s: (rarity_order.get(s.rarity, 6), -s.mean)
    )

    for s in sorted_stats:
        seasons = ";".join(s.seasons_available) if s.seasons_available else "all"
        print(f"{s.resource_id:<25} {s.rarity:<12} {s.category:<10} {s.biome:<12} "
              f"{s.mean:>8.2f} {s.std_dev:>8.2f} {s.min_count:>5} {s.max_count:>5}  [{seasons}]",
              file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simulate N worlds and output resource density statistics as CSV."
    )
    parser.add_argument(
        "--worlds", "-n", type=int, default=100,
        help="Number of worlds to simulate (default: 100)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default="resource_distribution.csv",
        help="Output CSV file path (default: resource_distribution.csv)"
    )
    parser.add_argument(
        "--season", "-s", type=str, choices=["spring", "summer", "autumn", "winter"],
        help="Lock simulation to a specific season"
    )
    parser.add_argument(
        "--biome", "-b", type=str,
        help="Filter results to a specific biome (forest, plains, coastal, swamp, mountains, desert)"
    )
    parser.add_argument(
        "--seed-base", type=int, default=42,
        help="Base random seed (default: 42)"
    )
    parser.add_argument(
        "--width", type=int, default=128,
        help="Map width in tiles (default: 128 for faster analysis)"
    )
    parser.add_argument(
        "--height", type=int, default=128,
        help="Map height in tiles (default: 128 for faster analysis)"
    )
    parser.add_argument(
        "--players", type=int, default=1,
        help="Number of players for density scaling (default: 1)"
    )
    parser.add_argument(
        "--density-mult", type=float, default=1.0,
        help="Global density multiplier (default: 1.0)"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    if args.quiet:
        import sys as _sys
        _sys.stderr = open("/dev/null", "w")

    print(f"Simulating {args.worlds} worlds ({args.width}x{args.height})...", file=sys.stderr)
    if args.season:
        print(f"  Season locked to: {args.season}", file=sys.stderr)
    if args.biome:
        print(f"  Biome filter: {args.biome}", file=sys.stderr)
    if args.players > 1:
        print(f"  Player count: {args.players} (density scaling enabled)", file=sys.stderr)

    stats = run_simulation(
        args.worlds, args.season, args.biome, args.seed_base,
        args.width, args.height, args.players, args.density_mult
    )
    write_csv(stats, args.output)
    print_summary(stats)

    print(f"\nResults written to: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())