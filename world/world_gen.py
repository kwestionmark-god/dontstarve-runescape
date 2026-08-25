"""
world_gen.py — Procedural generation engine.

Generates the entire world map at game start using simplex noise
for terrain elevation and biome assignment.

Flow:
1. Generate elevation map (simplex noise)
2. Generate moisture map (independent noise layer)
3. Classify biomes per tile (elevation + moisture thresholds)
4. Place resource nodes via ResourcePlacer (density-based, season-gated)
5. Find spawn point (Temperate biome, safe elevation, resource-rich)

Resource placement uses data-driven densities from resources.json:
  - Each resource has a base_density field
  - Tier scaling: tier 1 = 1.0x, tier 2 = 0.7x, tier 3 = 0.4x, tier 4 = 0.2x
  - Seasonal multipliers from SeasonSystem are applied at placement time
  - Clustering bonus encourages same-biome resource groups
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import noise

from config import MAP_WIDTH, MAP_HEIGHT, TILE_SUBDIVISIONS
from world.biome import BiomeRegistry
from world.tile_map import TileMap, Tile
from world.resource_placer import ResourcePlacer

if TYPE_CHECKING:
    from typing import Tuple


# Noise configuration
NOISE_SCALE = 0.005       # Controls "zoom" of noise features
ELEVATION_OCTAVES = 4     # Number of noise layers for detail
MOISTURE_OCTAVES = 3


def generate(seed: int, biome_registry: BiomeRegistry, season_system: object | None = None) -> TileMap:
    """
    Main entry point — generate a complete TileMap from seed and biomes.

    Args:
        seed: Deterministic seed for procedural generation.
        biome_registry: Registry of available biomes loaded from JSON.
        season_system: Optional SeasonSystem for seasonal resource gating.

    Returns:
        A fully constructed TileMap with biomes, resources, and spawn point.
    """
    elevation_map = _generate_elevation_map(seed)
    moisture_map = _generate_moisture_map(seed)
    tile_map = _build_tile_grid(elevation_map, moisture_map, biome_registry)
    ResourcePlacer(rng=random.Random(seed), season_system=season_system).place(tile_map)
    # Seasonal gating would otherwise leave in-season-only resources unplaced:
    # the world is generated once in spring, so winter/summer/autumn resources
    # are excluded at placement time and never appear. Re-run placement on each
    # season rollover so newly-in-season resources are added (existing nodes are
    # preserved), then let the spawn-point search ignore the extra resources.
    _wire_seasonal_replacement(tile_map, seed, season_system)
    spawn_x, spawn_y = _find_spawn_point(tile_map, seed)
    tile_map.spawn_x = spawn_x
    tile_map.spawn_y = spawn_y

    return tile_map


def _wire_seasonal_replacement(
    tile_map: "TileMap", seed: int, season_system: object | None
) -> None:
    """Re-run resource placement when the season changes.

    The world is generated once in spring, at which point ``ResourcePlacer``
    only places resources available that season. Season-gated resources
    (e.g. winter's mithril_vein/ghost_iron_deposit/star_metal/ancient_rune,
    summer's celestial_crystal/amber_deposit, autumn+winter's dragonbone/
    void_essence) would otherwise never be placed and be permanently
    unobtainable. Re-running placement on each season rollover ADDS the
    newly-in-season resources onto the existing map; already-placed nodes are
    preserved, so the original spring-inclusive set (void_crystal, silk_nest,
    elder_wood, obsidian_vein) stays reachable.

    Args:
        tile_map: The generated map to place onto.
        seed: Deterministic seed for the re-placement RNG.
        season_system: Optional SeasonSystem; the callback is a no-op if absent.
    """
    if season_system is None or getattr(season_system, "_resource_placer_wired", False):
        return
    season_system._resource_placer_wired = True

    def _replace_on_season_change(_new_season: str, _previous_season: str) -> None:
        try:
            ResourcePlacer(
                rng=random.Random(seed), season_system=season_system
            ).place(tile_map)
        except Exception:
            # A failed placement must not disrupt the season cycle.
            return

    season_system.on_season_changed(_replace_on_season_change)


def _generate_elevation_map(seed: int) -> list[list[float]]:
    """
    Generate a 2D elevation map using simplex noise.

    Returns elevation values normalized to 0–1, then mapped to 0–7.

    Args:
        seed: Random seed for noise generation.

    Returns:
        2D list of elevation integers (0–7).
    """
    elev = [[0.0] * MAP_HEIGHT for _ in range(MAP_WIDTH)]

    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            value = noise.pnoise2(
                x * NOISE_SCALE, y * NOISE_SCALE,
                octaves=ELEVATION_OCTAVES,
                persistence=0.5,
                lacunarity=2.0,
                repeatx=MAP_WIDTH,
                repeaty=MAP_HEIGHT,
                base=seed,
            )
            normalized = (value + 1.0) / 2.0
            elev[x][y] = max(0, min(7, int(normalized * 8)))

    return elev


def _generate_moisture_map(seed: int) -> list[list[float]]:
    """
    Generate a 2D moisture map using independent simplex noise.

    Uses a +100 offset on coordinates to prevent correlation with
    elevation noise, ensuring organic biome variation.

    Args:
        seed: Random seed for noise generation.

    Returns:
        2D list of moisture values (0.0–1.0).
    """
    moisture = [[0.0] * MAP_HEIGHT for _ in range(MAP_WIDTH)]

    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            value = noise.pnoise2(
                x * NOISE_SCALE * 1.5 + 100,
                y * NOISE_SCALE * 1.5 + 100,
                octaves=MOISTURE_OCTAVES,
                base=seed + 1,
            )
            moisture[x][y] = (value + 1.0) / 2.0

    return moisture


def classify_biome(elevation: int, moisture: float) -> str:
    """
    Classify a biome from elevation and moisture values.

    Classification logic:
    1. Elevation >= 6: Always Mountains (peaks)
    2. Low elevation (<= 1): Coastal if wet, Desert if dry
    3. Mid-low (2-3): Desert (very dry), Plains (moderate), Forest (moderate-high)
    4. Mid-high (4-5): Mountains (if elevation >= 4), Plains/Forest (if lower moisture)
    5. High moisture + mid elevation: Swamp (wet lowlands)

    Args:
        elevation: Integer elevation (0–7).
        moisture: Float moisture value (0.0–1.0).

    Returns:
        Biome ID string.
    """
    if elevation >= 6:
        return "mountains"
    elif elevation >= 4 and moisture < 0.3:
        return "desert"
    elif elevation >= 4:
        return "mountains"
    elif elevation <= 1 and moisture < 0.3:
        return "desert"
    elif elevation <= 1:
        return "coastal"
    elif moisture < 0.25:
        return "desert"
    elif moisture < 0.4:
        return "plains"
    elif moisture < 0.7:
        return "forest"
    else:
        return "swamp"


def _build_tile_grid(
    elevation_map: list[list[int]],
    moisture_map: list[list[float]],
    biome_registry: BiomeRegistry,
) -> TileMap:
    """
    Build the TileMap grid from elevation and moisture maps.

    Each tile gets its biome, elevation, and terrain color assigned.

    Args:
        elevation_map: 2D elevation grid (0–7).
        moisture_map: 2D moisture grid (0.0–1.0).
        biome_registry: Registry of biome definitions.

    Returns:
        A partially-constructed TileMap with tiles initialized.
    """
    tile_map = TileMap(MAP_WIDTH, MAP_HEIGHT, 0, 0)

    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            elevation = elevation_map[x][y]
            moisture = moisture_map[x][y]
            biome_id = classify_biome(elevation, moisture)
            biome = biome_registry.get(biome_id)

            tile = Tile(x, y, biome, elevation)
            tile.terrain_color = biome.get_terrain_color(elevation)
            tile_map.tiles[x][y] = tile

    return tile_map


def _has_swamp_neighbor(tile_map: TileMap, x: int, y: int) -> bool:
    """Check if any adjacent tile is in the swamp biome."""
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    for dx, dy in directions:
        neighbor = tile_map.get_tile(x + dx, y + dy)
        if neighbor is not None and neighbor.biome.id == "swamp":
            return True
    return False


def _count_nearby_resources(tile_map: TileMap, x: int, y: int, radius: int = 3) -> int:
    """
    Count resource nodes within a square radius of the given tile.

    Used to score spawn candidates — prefer areas with more resources
    nearby so players don't spawn in barren zones.

    Args:
        tile_map: The TileMap.
        x: Tile X coordinate.
        y: Tile Y coordinate.
        radius: Search radius in tiles (square area).

    Returns:
        Number of resource nodes within range.
    """
    count = 0
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            neighbor = tile_map.get_tile(x + dx, y + dy)
            if neighbor is not None and neighbor.resource_node is not None:
                count += 1
    return count


def _find_spawn_point(tile_map: TileMap, seed: int) -> Tuple[int, int]:
    """
    Find a valid starting position for the player.

    Rules:
    - Must be in Temperate biome (forest, plains, coastal)
    - Must not be adjacent to a swamp tile
    - Prefer elevation 1–3 (not too high, not beach)
    - Prefer tiles with more nearby resources (resource-rich spawn)

    Args:
        tile_map: The generated TileMap.
        seed: Random seed for shuffle (different world order each game).

    Returns:
        (x, y) spawn coordinates in the Temperate biome.
    """
    rng = random.Random(seed + 999)
    candidates = []

    for x in range(tile_map.width):
        for y in range(tile_map.height):
            tile = tile_map.tiles[x][y]

            if tile.biome.mega_cluster != "temperate":
                continue

            if tile.elevation < 1 or tile.elevation > 3:
                continue

            if _has_swamp_neighbor(tile_map, x, y):
                continue

            resource_score = _count_nearby_resources(tile_map, x, y)
            candidates.append((x, y, resource_score))

    if not candidates:
        for x in range(tile_map.width):
            for y in range(tile_map.height):
                tile = tile_map.tiles[x][y]
                if tile.biome.mega_cluster == "temperate" and 1 <= tile.elevation <= 3:
                    resource_score = _count_nearby_resources(tile_map, x, y)
                    candidates.append((x, y, resource_score))

    if not candidates:
        return (MAP_WIDTH // 2, MAP_HEIGHT // 2)

    # Sort by resource score descending, then shuffle within same score tier
    candidates.sort(key=lambda c: -c[2])
    best_score = candidates[0][2]
    top_candidates = [(x, y) for x, y, score in candidates if score == best_score]
    rng.shuffle(top_candidates)
    return top_candidates[0]
