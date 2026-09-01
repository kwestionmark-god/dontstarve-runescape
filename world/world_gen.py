"""
world_gen.py — Procedural generation engine.

Generates the entire world map at game start using Perlin noise
for terrain elevation and biome assignment.

Flow:
1. Generate elevation map (Perlin noise + ridge noise + domain warping)
2. Generate moisture map (independent noise layer)
3. Classify biomes per tile (elevation + moisture thresholds + biome-specific noise)
4. Build biome transition zones (ecotones)
5. Place resource nodes via ResourcePlacer (density-based, season-gated)
6. Find spawn point (Temperate biome, safe elevation, resource-rich)

Resource placement uses data-driven densities from resources.json:
  - Each resource has a base_density field
  - Rarity scaling via RARITY_DENSITY_RANGE clamping
  - Biome affinity weights from resource.biome_affinity
  - Progression zones gate rarity by distance from spawn
  - Seasonal multipliers from SeasonSystem
  - Vein placement for ore/stone clusters
  - Poisson disc for common resources
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import noise
import numpy as np

from config import (
    MAP_WIDTH as _CFG_MAP_WIDTH, MAP_HEIGHT as _CFG_MAP_HEIGHT,
    TILE_SUBDIVISIONS, ELEVATION_LEVELS,
    NOISE_SCALE, ELEVATION_OCTAVES, MOISTURE_OCTAVES, MOISTURE_SCALE, MOISTURE_RANGE_MULTIPLIER,
    RIDGE_NOISE_SCALE, RIDGE_OCTAVES, RIDGE_LACUNARITY, RIDGE_PERSISTENCE,
    DOMAIN_WARP_SCALE, DOMAIN_WARP_OCTAVES, DOMAIN_WARP_AMPLITUDE,
    BIOME_NOISE_PARAMS,
)

# Module-level constants that can be patched by tests.
# Default to config values but can be overridden.
MAP_WIDTH = _CFG_MAP_WIDTH
MAP_HEIGHT = _CFG_MAP_HEIGHT
from world.biome import BiomeRegistry
from world.tile_map import TileMap, Tile
from world.resource_placer import ResourcePlacer

if TYPE_CHECKING:
    from typing import Tuple


def _fbm_noise(x: float, y: float, scale: float, octaves: int, persistence: float, lacunarity: float, seed: int) -> float:
    """Fractional Brownian Motion noise using noise.pnoise2."""
    value = 0.0
    amplitude = 1.0
    frequency = scale
    for _ in range(octaves):
        value += amplitude * noise.pnoise2(
            x * frequency, y * frequency,
            octaves=1,
            persistence=persistence,
            lacunarity=lacunarity,
            repeatx=10000, repeaty=10000,
            base=seed,
        )
        amplitude *= persistence
        frequency *= lacunarity
    return value


def _ridge_noise(x: float, y: float, scale: float, octaves: int, persistence: float, lacunarity: float, seed: int, offset: float = 1.0) -> float:
    """Ridgeline noise: creates sharp ridges and valleys by inverting absolute noise.
    
    Output range: [-1, 1] where 1.0 = ridges, -1.0 = valleys.
    """
    value = 0.0
    amplitude = 1.0
    frequency = scale
    for _ in range(octaves):
        n = noise.pnoise2(
            x * frequency, y * frequency,
            octaves=1,
            persistence=persistence,
            lacunarity=lacunarity,
            repeatx=10000, repeaty=10000,
            base=seed,
        )
        # Ridge: invert absolute value to create sharp ridges
        # Map from [0, 1] to [-1, 1]: 1.0 - 2.0 * abs(n)
        n = 1.0 - 2.0 * abs(n)
        value += amplitude * n
        amplitude *= persistence
        frequency *= lacunarity
    return value


def _domain_warp(x: int, y: int, seed: int, scale: float, octaves: int, amplitude: float) -> tuple[float, float]:
    """Domain warping: distorts coordinate space for geological variation."""
    # Use two independent noise channels for x and y warp
    warp_x = _fbm_noise(x, y, scale, octaves, 0.5, 2.0, seed + 1000) * amplitude
    warp_y = _fbm_noise(x, y, scale, octaves, 0.5, 2.0, seed + 2000) * amplitude
    return x + warp_x, y + warp_y


def _generate_base_elevation(seed: int, width: int, height: int) -> list[list[float]]:
    """Generate base elevation using combined Perlin + Ridge noise with domain warping."""
    elev = [[0.0] * height for _ in range(width)]
    
    for y in range(height):
        for x in range(width):
            # Apply domain warping to coordinates
            wx, wy = _domain_warp(x, y, seed, DOMAIN_WARP_SCALE, DOMAIN_WARP_OCTAVES, DOMAIN_WARP_AMPLITUDE)
            
            # Base Perlin noise (continental shape)
            base = _fbm_noise(wx, wy, NOISE_SCALE, ELEVATION_OCTAVES, 0.5, 2.0, seed)
            
            # Ridge noise (mountain ridges, sharp features)
            ridge = _ridge_noise(wx, wy, RIDGE_NOISE_SCALE, RIDGE_OCTAVES, RIDGE_PERSISTENCE, RIDGE_LACUNARITY, seed + 500)
            
            # Combine: base provides large-scale shape, ridges add detail
            # Weight: 85% base, 15% ridge (further reduced ridge influence)
            combined = 0.85 * base + 0.15 * ridge
            
            # Add a stronger negative bias to center elevation around middle (16 for 32 levels)
            # and spread more towards lower elevations
            combined -= 0.2
            
            # Normalize to 0-1, then scale to elevation levels (0 to ELEVATION_LEVELS-1)
            normalized = (combined + 1.0) / 2.0
            from config import ELEVATION_LEVELS
            elev[x][y] = max(0, min(ELEVATION_LEVELS - 1, int(normalized * ELEVATION_LEVELS)))
    
    return elev


def _generate_elevation_map(seed: int, width: int | None = None, height: int | None = None) -> list[list[float]]:
    """
    Generate a 2D elevation map using combined Perlin + Ridge noise with domain warping.

    Returns elevation values normalized to 0–1, then mapped to 0–(ELEVATION_LEVELS-1).

    Args:
        seed: Random seed for noise generation.
        width: Map width in tiles (default: module-level MAP_WIDTH).
        height: Map height in tiles (default: module-level MAP_HEIGHT).

    Returns:
        2D list of elevation integers (0–ELEVATION_LEVELS-1).
    """
    if width is None:
        width = MAP_WIDTH
    if height is None:
        height = MAP_HEIGHT
    return _generate_base_elevation(seed, width, height)


def _generate_moisture_map(seed: int, width: int | None = None, height: int | None = None) -> list[list[float]]:
    """
    Generate a 2D moisture map using independent Perlin noise.

    Uses a +100 offset on coordinates to prevent correlation with
    elevation noise, ensuring organic biome variation.

    Args:
        seed: Random seed for noise generation.
        width: Map width in tiles (default: MAP_WIDTH).
        height: Map height in tiles (default: MAP_HEIGHT).

    Returns:
        2D list of moisture values (0.0–1.0).
    """
    moisture = [[0.0] * height for _ in range(width)]

    for y in range(height):
        for x in range(width):
            value = noise.pnoise2(
                x * MOISTURE_SCALE + 100,
                y * MOISTURE_SCALE + 100,
                octaves=MOISTURE_OCTAVES,
                base=seed + 1,
            )
            # Apply range multiplier to expand moisture variation
            value *= MOISTURE_RANGE_MULTIPLIER
            moisture[x][y] = max(0.0, min(1.0, (value + 1.0) / 2.0))

    return moisture


def generate(
    seed: int,
    biome_registry: BiomeRegistry,
    season_system: object | None = None,
    progress_callback: object | None = None,
) -> TileMap:
    """
    Main entry point — generate a complete TileMap from seed and biomes.

    Args:
        seed: Deterministic seed for procedural generation.
        biome_registry: Registry of available biomes loaded from JSON.
        season_system: Optional SeasonSystem for seasonal resource gating.
        progress_callback: Optional callable(progress: float) -> None, called with 0.0-1.0.

    Returns:
        A fully constructed TileMap with biomes, resources, and spawn point.
    """
    def _report(progress: float) -> None:
        if progress_callback is not None:
            progress_callback(progress)

    # Use module-level MAP_WIDTH/MAP_HEIGHT (may be patched by tests)
    width = MAP_WIDTH
    height = MAP_HEIGHT
    
    # Generate base elevation with ridge noise and domain warping
    _report(0.05)
    elevation_map = _generate_elevation_map(seed, width, height)
    _report(0.10)
    moisture_map = _generate_moisture_map(seed, width, height)
    _report(0.15)
    
    # Apply hydraulic erosion simulation
    from config import EROSION_ITERATIONS
    if EROSION_ITERATIONS > 0:
        elevation_map = _simulate_erosion(elevation_map, width, height, seed)
    _report(0.30)
    
    # Apply biome-specific noise refinement
    elevation_map = _apply_biome_noise(elevation_map, moisture_map, width, height, seed)
    _report(0.40)
    
    # Generate water bodies (rivers, lakes, coastal smoothing)
    from config import RIVER_THRESHOLD, LAKE_MIN_SIZE
    water_map = _generate_water_bodies(elevation_map, moisture_map, width, height, seed, RIVER_THRESHOLD, LAKE_MIN_SIZE)
    _report(0.50)
    
    # Detect cliffs and generate scree slopes
    from config import CLIFF_THRESHOLD
    cliff_mask, scree_map = _detect_cliffs_and_scree(elevation_map, width, height, CLIFF_THRESHOLD)
    _report(0.55)
    
    # Build tile grid with biomes
    tile_map = _build_tile_grid(elevation_map, moisture_map, biome_registry, width, height, water_map)
    _report(0.60)

    # Bake per-corner height + fog grids (Phase 7 P1).
    # Heights must be baked first because fog reads from them.
    tile_map.bake_corner_heights()
    tile_map.bake_corner_fog()
    _report(0.65)

    # Bake ambient occlusion (Phase 6.2)
    tile_map.bake_ambient_occlusion()
    _report(0.70)
    
    # Precompute fog density for volumetric fog (Phase 6.5)
    from render.lighting_system import LightingSystem
    _lighting_sys = LightingSystem()
    _lighting_sys.precompute_fog_density(tile_map)
    _report(0.75)
    
    # Build biome transition zones (ecotones) - blend resource spawns at biome borders
    from data import load_json_list
    resource_defs = {r["id"]: r for r in load_json_list("resources.json", "resources")}
    _build_biome_transitions(tile_map, biome_registry, resource_defs)
    _report(0.85)
    
    # Place resources with progression zones, veins, seasonal gating
    ResourcePlacer(rng=random.Random(seed), season_system=season_system).place(tile_map)
    _report(0.95)
    
    # Seasonal gating would otherwise leave in-season-only resources unplaced:
    # the world is generated once in spring, so winter/summer/autumn resources
    # are excluded at placement time and never appear. Re-run placement on each
    # season rollover so newly-in-season resources are added (existing nodes are
    # preserved), then let the spawn-point search ignore the extra resources.
    _wire_seasonal_replacement(tile_map, seed, season_system)
    spawn_x, spawn_y = _find_spawn_point(tile_map, seed)
    tile_map.spawn_x = spawn_x
    tile_map.spawn_y = spawn_y
    _report(1.0)

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
            ).place(tile_map, enforce_zones=False, allow_overwrite=True)
        except Exception:
            # A failed placement must not disrupt the season cycle.
            return

    season_system.on_season_changed(_replace_on_season_change)


def _apply_biome_noise(elevation: list[list[int]], moisture: list[list[float]], width: int, height: int, seed: int) -> list[list[int]]:
    """
    Refine elevation using biome-specific noise parameters.
    
    After initial biome classification, apply biome-specific noise to create
    more distinctive terrain features per biome type.
    """
    # First pass: classify initial biomes
    biome_map = [[None] * height for _ in range(width)]
    for y in range(height):
        for x in range(width):
            biome_map[x][y] = classify_biome(elevation[x][y], moisture[x][y])
    
    # Second pass: apply biome-specific noise refinement
    refined = [[0] * height for _ in range(width)]
    for y in range(height):
        for x in range(width):
            biome_id = biome_map[x][y]
            params = BIOME_NOISE_PARAMS.get(biome_id, {})
            
            if not params:
                refined[x][y] = elevation[x][y]
                continue
            
            # Generate biome-specific detail noise
            detail_scale = params.get("scale", NOISE_SCALE)
            detail_octaves = params.get("octaves", ELEVATION_OCTAVES)
            detail_persistence = params.get("persistence", 0.5)
            detail_lacunarity = params.get("lacunarity", 2.0)
            ridge_weight = params.get("ridge_weight", 0.0)
            warp_amp = params.get("domain_warp", 0.0)
            
            # Apply domain warping if specified
            if warp_amp > 0:
                wx, wy = _domain_warp(x, y, seed + 3000, DOMAIN_WARP_SCALE, DOMAIN_WARP_OCTAVES, warp_amp)
            else:
                wx, wy = x, y
            
            # Base detail noise
            detail = _fbm_noise(wx, wy, detail_scale, detail_octaves, detail_persistence, detail_lacunarity, seed + 4000)
            
            # Add ridge noise if specified
            if ridge_weight > 0:
                ridge = _ridge_noise(wx, wy, RIDGE_NOISE_SCALE, RIDGE_OCTAVES, RIDGE_PERSISTENCE, RIDGE_LACUNARITY, seed + 5000)
                combined = (1.0 - ridge_weight) * detail + ridge_weight * ridge
            else:
                combined = detail
            
            # Normalize and blend with base elevation (subtle refinement)
            normalized = (combined + 1.0) / 2.0
            from config import ELEVATION_LEVELS
            detail_elev = int(normalized * (ELEVATION_LEVELS - 1))
            
            # Blend: 80% base elevation, 20% biome-specific detail
            refined[x][y] = int(0.8 * elevation[x][y] + 0.2 * detail_elev)
            refined[x][y] = max(0, min(ELEVATION_LEVELS - 1, refined[x][y]))
    
    return refined


def _simulate_erosion(elevation: list[list[int]], width: int, height: int, seed: int) -> list[list[int]]:
    """
    Hydraulic erosion simulation using cellular automaton.
    
    Simulates water flow, sediment transport, and deposition over multiple iterations.
    Creates realistic river valleys, alluvial fans, and talus slopes.
    
    Args:
        elevation: 2D elevation grid (0-ELEVATION_LEVELS-1).
        width: Map width.
        height: Map height.
        seed: Random seed for deterministic simulation.
    
    Returns:
        Eroded elevation grid.
    """
    from config import (
        EROSION_ITERATIONS, EROSION_RAIN_AMOUNT, EROSION_SOLUBILITY,
        EROSION_EVAPORATION, EROSION_GRAVITY, EROSION_SEDIMENT_CAPACITY_FACTOR,
        ELEVATION_LEVELS
    )
    
    # Convert to float for simulation
    elev = [[float(elevation[x][y]) for y in range(height)] for x in range(width)]
    water = [[0.0] * height for _ in range(width)]
    sediment = [[0.0] * height for _ in range(width)]
    
    # Directions: 8-connected neighbors
    directions = [
        (-1, -1), (0, -1), (1, -1),
        (-1,  0),         (1,  0),
        (-1,  1), (0,  1), (1,  1),
    ]
    
    for iteration in range(EROSION_ITERATIONS):
        # Add rain
        for x in range(width):
            for y in range(height):
                water[x][y] += EROSION_RAIN_AMOUNT
        
        # Flow water and transport sediment
        for x in range(width):
            for y in range(height):
                if water[x][y] <= 0:
                    continue
                
                current_height = elev[x][y]
                
                # Find neighbors and calculate slopes
                slopes = []
                total_slope = 0.0
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        neighbor_height = elev[nx][ny]
                        slope = current_height - neighbor_height
                        if slope > 0:
                            dist = 1.0 if dx == 0 or dy == 0 else 1.414
                            slope /= dist
                            slopes.append((nx, ny, slope))
                            total_slope += slope
                
                if total_slope > 0:
                    # Distribute water and sediment downhill
                    for nx, ny, slope in slopes:
                        flow = water[x][y] * (slope / total_slope)
                        sediment_capacity = flow * slope * EROSION_SEDIMENT_CAPACITY_FACTOR * EROSION_GRAVITY
                        
                        if sediment[x][y] > sediment_capacity:
                            # Deposit excess sediment
                            deposit = min(sediment[x][y] - sediment_capacity, sediment[x][y])
                            elev[x][y] += deposit
                            sediment[x][y] -= deposit
                        elif sediment[x][y] < sediment_capacity:
                            # Erode terrain
                            erode = min(sediment_capacity - sediment[x][y], current_height * EROSION_SOLUBILITY)
                            elev[x][y] -= erode
                            sediment[x][y] += erode
                        
                        # Move water
                        water[nx][ny] += flow
                        water[x][y] -= flow
        
        # Evaporate water
        for x in range(width):
            for y in range(height):
                water[x][y] *= (1.0 - EROSION_EVAPORATION)
                if water[x][y] < 0.001:
                    water[x][y] = 0.0
                    # Deposit remaining sediment
                    if sediment[x][y] > 0:
                        elev[x][y] += sediment[x][y]
                        sediment[x][y] = 0.0
    
    # Convert back to int
    result = [[0] * height for _ in range(width)]
    for x in range(width):
        for y in range(height):
            result[x][y] = max(0, min(ELEVATION_LEVELS - 1, int(elev[x][y])))
    
    return result


def classify_biome(elevation: int, moisture: float, is_water: bool = False) -> str:
    """
    Classify a biome from elevation and moisture values.

    Classification logic (updated for 32 elevation levels):
    1. Very high elevation (>= 26): Always Mountains (peaks)
    2. High elevation (20-25): Mountains, or Desert if very dry
    3. Mid-high elevation (14-19): Mountains (wet), Forest (moderate), Plains (dry), Desert (arid)
    4. Mid elevation (8-13): Forest (wet), Swamp (very wet), Plains (moderate), Desert (dry)
    5. Low elevation (4-7): Coastal (wet), Forest (moderate), Plains (dry), Desert (arid)
    6. Very low elevation (0-3): Coastal (wet), Desert (arid)
    Water tiles are classified as "water" biome.

    Args:
        elevation: Integer elevation (0–31).
        moisture: Float moisture value (0.0–1.0).
        is_water: Whether this tile is a water body.

    Returns:
        Biome ID string.
    """
    # Water tiles get water biome
    if is_water:
        return "water"
    # Very high peaks
    if elevation >= 26:
        return "mountains"
    # High elevation plateaus and peaks
    elif elevation >= 20:
        if moisture < 0.15:
            return "desert"
        elif moisture < 0.35:
            return "plains"
        elif moisture < 0.7:
            return "mountains"
        else:
            return "mountains"  # High wet peaks
    # Mid-high elevation
    elif elevation >= 14:
        if moisture < 0.15:
            return "desert"
        elif moisture < 0.3:
            return "plains"
        elif moisture < 0.6:
            return "forest"
        elif moisture < 0.8:
            return "mountains"
        else:
            return "swamp"  # Very wet high areas = alpine wetlands
    # Mid elevation
    elif elevation >= 8:
        if moisture < 0.2:
            return "desert"
        elif moisture < 0.35:
            return "plains"
        elif moisture < 0.55:
            return "forest"
        elif moisture < 0.75:
            return "swamp"
        else:
            return "swamp"
    # Low elevation - coastal at moderate moisture (moisture is independent of elevation)
    elif elevation >= 4:
        if moisture < 0.2:
            return "desert"
        elif moisture < 0.35:
            return "plains"
        elif moisture < 0.4:
            return "forest"
        else:
            return "coastal"  # Coastal at higher moisture, no swamp at low elevations
    # Very low elevation (coastal areas) - very low threshold since moisture is independent
    else:
        if moisture < 0.25:
            return "desert"
        elif moisture < 0.4:
            return "plains"
        else:
            return "coastal"


def _detect_cliffs_and_scree(
    elevation: list[list[int]], width: int, height: int, cliff_threshold: float
) -> tuple[list[list[bool]], list[list[bool]]]:
    """
    Detect cliffs and generate scree slope mask.
    
    A cliff is detected when elevation difference between adjacent tiles exceeds the threshold.
    Scree slopes are generated on the downhill side of cliffs (the lower elevation tile).
    
    Args:
        elevation: 2D elevation grid.
        width: Map width.
        height: Map height.
        cliff_threshold: Minimum elevation delta to consider a cliff.
    
    Returns:
        Tuple of (cliff_mask, scree_mask) where each is a 2D boolean grid.
    """
    cliff_mask = [[False] * height for _ in range(width)]
    scree_mask = [[False] * height for _ in range(width)]
    
    # 4-connected directions for cliff detection
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    
    # First pass: detect cliffs
    for x in range(width):
        for y in range(height):
            current_elev = elevation[x][y]
            
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor_elev = elevation[nx][ny]
                    delta = current_elev - neighbor_elev
                    
                    if delta >= cliff_threshold:
                        # Current tile is a cliff face (higher than neighbor)
                        cliff_mask[x][y] = True
                        # Neighbor is the scree slope (downhill side)
                        scree_mask[nx][ny] = True
                    elif delta <= -cliff_threshold:
                        # Neighbor is a cliff face
                        cliff_mask[nx][ny] = True
                        # Current tile is scree
                        scree_mask[x][y] = True
    
    # Second pass: extend scree slopes slightly for more natural appearance
    # Scree extends 1-2 tiles further downhill from the immediate base
    for x in range(width):
        for y in range(height):
            if scree_mask[x][y]:
                current_elev = elevation[x][y]
                # Find the steepest downhill neighbor and extend scree there
                steepest_slope = 0.0
                steepest_nx, steepest_ny = -1, -1
                
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        slope = current_elev - elevation[nx][ny]
                        if slope > steepest_slope:
                            steepest_slope = slope
                            steepest_nx, steepest_ny = nx, ny
                
                if steepest_nx >= 0 and steepest_slope > 0:
                    # 50% chance to extend scree one more tile
                    import random
                    if random.random() < 0.5:
                        scree_mask[steepest_nx][steepest_ny] = True
    
    return cliff_mask, scree_mask


def _generate_water_bodies(
    elevation: list[list[int]],
    moisture: list[list[float]],
    width: int,
    height: int,
    seed: int,
    river_threshold: float,
    lake_min_size: int,
) -> list[list[bool]]:
    """
    Generate water bodies: rivers from flow accumulation, lakes in depressions,
    and coastal smoothing.
    
    Args:
        elevation: 2D elevation grid.
        moisture: 2D moisture grid.
        width: Map width.
        height: Map height.
        seed: Random seed.
        river_threshold: Flow accumulation threshold for river formation.
        lake_min_size: Minimum connected tiles for a lake.
    
    Returns:
        2D boolean water mask (True = water).
    """
    # Initialize water mask
    water = [[False] * height for _ in range(width)]
    
    # Compute flow accumulation using D8 flow direction
    flow_accum = _compute_flow_accumulation(elevation, width, height)
    
    # 1. Rivers: tiles with flow accumulation above threshold
    for x in range(width):
        for y in range(height):
            if flow_accum[x][y] >= river_threshold:
                water[x][y] = True
    
    # 2. Lakes: find depressions (local minima) and fill them
    lake_mask = _find_and_fill_lakes(elevation, width, height, lake_min_size)
    for x in range(width):
        for y in range(height):
            if lake_mask[x][y]:
                water[x][y] = True
    
    # 3. Coastal smoothing: add water at very low elevations near edges
    _apply_coastal_smoothing(water, elevation, width, height)
    
    # 4. Connect nearby water bodies (ensure rivers reach lakes/coast)
    water = _connect_water_bodies(water, elevation, width, height)
    
    return water


def _compute_flow_accumulation(elevation: list[list[int]], width: int, height: int) -> list[list[float]]:
    """
    Compute flow accumulation using D8 flow direction algorithm.
    
    Each tile flows to its steepest downhill neighbor (or stays if flat).
    Accumulation counts how many UPSTREAM tiles flow into each tile
    (not including the tile itself).
    
    Args:
        elevation: 2D elevation grid.
        width: Map width.
        height: Map height.
    
    Returns:
        2D flow accumulation grid (float).
    """
    # D8 directions: (dx, dy) for 8 neighbors
    directions = [
        (-1, -1), (0, -1), (1, -1),
        (-1,  0),         (1,  0),
        (-1,  1), (0,  1), (1,  1),
    ]
    
    # Step 1: Find flow direction for each tile
    flow_dir = [[None] * height for _ in range(width)]
    
    for x in range(width):
        for y in range(height):
            current_elev = elevation[x][y]
            steepest_slope = 0.0
            best_dir = None
            
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor_elev = elevation[nx][ny]
                    slope = current_elev - neighbor_elev
                    if slope > steepest_slope:
                        steepest_slope = slope
                        best_dir = (dx, dy)
            
            flow_dir[x][y] = best_dir
    
    # Step 2: Compute flow accumulation (number of UPSTREAM tiles draining to each tile)
    # Use topological sort approach: process from highest to lowest elevation
    tiles_by_elev = []
    for x in range(width):
        for y in range(height):
            tiles_by_elev.append((elevation[x][y], x, y))
    tiles_by_elev.sort(reverse=True)
    
    # Initialize accumulation: each tile starts with 0 (only upstream contributors)
    accum = [[0.0] * height for _ in range(width)]
    
    # Each tile contributes 1 unit of "rain" to its downhill neighbor
    # Process from high to low: each tile passes its (accum + 1) to downhill neighbor
    for _, x, y in tiles_by_elev:
        dir = flow_dir[x][y]
        if dir is not None:
            dx, dy = dir
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height:
                # This tile contributes 1 (itself) + its upstream accumulation
                accum[nx][ny] += accum[x][y] + 1.0
    
    return accum


def _find_and_fill_lakes(
    elevation: list[list[int]], width: int, height: int, min_size: int
) -> list[list[bool]]:
    """
    Find small, closed depressions (potholes, kettle lakes) and fill them as lakes.
    
    Uses a priority-flood approach: only fills depressions that are fully enclosed
    by higher terrain AND don't touch the map boundary (which represents ocean).
    
    Args:
        elevation: 2D elevation grid.
        width: Map width.
        height: Map height.
        min_size: Minimum connected component size to be a lake.
    
    Returns:
        2D boolean lake mask.
    """
    lake_mask = [[False] * height for _ in range(width)]
    
    # 8-connected directions
    directions = [
        (-1, -1), (0, -1), (1, -1),
        (-1,  0),         (1,  0),
        (-1,  1), (0,  1), (1,  1),
    ]
    
    visited = [[False] * height for _ in range(width)]
    
    # Process each tile as potential depression seed
    for x in range(width):
        for y in range(height):
            if visited[x][y]:
                continue
            
            # Flood fill from this tile to find connected component at similar elevation
            basin = []
            stack = [(x, y)]
            basin_elev = elevation[x][y]
            touches_edge = False
            spill_elev = None
            
            while stack:
                cx, cy = stack.pop()
                if visited[cx][cy]:
                    continue
                visited[cx][cy] = True
                basin.append((cx, cy))
                
                # Check if touches map edge (drains to ocean)
                if cx == 0 or cx == width - 1 or cy == 0 or cy == height - 1:
                    touches_edge = True
                
                # Check 8 neighbors
                for dx, dy in directions:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        if visited[nx][ny]:
                            continue
                        neighbor_elev = elevation[nx][ny]
                        # Include in basin if within 1 elevation level (small depressions only)
                        if neighbor_elev <= basin_elev + 1:
                            stack.append((nx, ny))
                        else:
                            # Neighbor is higher - potential spill point
                            if spill_elev is None or neighbor_elev < spill_elev:
                                spill_elev = neighbor_elev
                    else:
                        # Off-map = drains to ocean
                        touches_edge = True
            
            # Only form a lake if:
            # 1. Basin doesn't touch map edge (not connected to ocean)
            # 2. Has a spill point higher than basin floor (closed depression)
            # 3. Basin is large enough but not too large (max 200 tiles for small lakes)
            # 4. Basin elevation is not too high (lakes form at lower elevations)
            if (not touches_edge and 
                spill_elev is not None and 
                spill_elev > basin_elev and
                min_size <= len(basin) <= 200 and
                basin_elev < 20):  # Lakes only at lower elevations
                for bx, by in basin:
                    lake_mask[bx][by] = True
    
    return lake_mask


def _apply_coastal_smoothing(
    water: list[list[bool]], elevation: list[list[int]], width: int, height: int
) -> None:
    """
    Apply coastal smoothing: add water at very low elevations near map edges
    and smooth transitions between land and water.
    
    Args:
        water: 2D water mask (modified in place).
        elevation: 2D elevation grid.
        width: Map width.
        height: Map height.
    """
    # Add water at very low elevations (0-2) near map edges
    edge_margin = 4
    coastal_elevation_threshold = 2
    
    for x in range(width):
        for y in range(height):
            # Check if near map edge
            near_edge = (x < edge_margin or x >= width - edge_margin or
                        y < edge_margin or y >= height - edge_margin)
            
            if near_edge and elevation[x][y] <= coastal_elevation_threshold:
                water[x][y] = True
    
    # Smooth water boundaries: if a tile has 5+ water neighbors, make it water
    # (run once for subtle smoothing)
    new_water = [row[:] for row in water]
    for x in range(width):
        for y in range(height):
            if water[x][y]:
                continue
            # Count water neighbors (8-connected)
            water_neighbors = 0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and water[nx][ny]:
                        water_neighbors += 1
            if water_neighbors >= 5:  # Majority of neighbors are water
                new_water[x][y] = True
    water[:] = new_water


def _connect_water_bodies(
    water: list[list[bool]], elevation: list[list[int]], width: int, height: int
) -> list[list[bool]]:
    """
    Connect nearby water bodies by finding paths downhill between them.
    
    Ensures rivers flow to lakes and coast.
    
    Args:
        water: 2D water mask.
        elevation: 2D elevation grid.
        width: Map width.
        height: Map height.
    
    Returns:
        Updated water mask.
    """
    # Find all water tiles
    water_tiles = [(x, y) for x in range(width) for y in range(height) if water[x][y]]
    
    if not water_tiles:
        return water
    
    # For each water tile, trace downhill to find other water bodies
    # and connect them if close
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0),
                  (-1, -1), (1, -1), (-1, 1), (1, 1)]
    
    new_water = [row[:] for row in water]
    
    for wx, wy in water_tiles:
        current_elev = elevation[wx][wy]
        
        # Trace downhill up to 20 steps
        cx, cy = wx, wy
        for _ in range(20):
            # Find steepest downhill neighbor
            steepest_slope = 0.0
            best_nx, best_ny = -1, -1
            
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < width and 0 <= ny < height:
                    slope = current_elev - elevation[nx][ny]
                    if slope > steepest_slope:
                        steepest_slope = slope
                        best_nx, best_ny = nx, ny
            
            if best_nx < 0 or steepest_slope <= 0:
                break  # Flat or local minimum
            
            cx, cy = best_nx, best_ny
            current_elev = elevation[cx][cy]
            
            # If we hit another water body, connect the path
            if water[cx][cy]:
                # Connect the path (already water)
                break
            
            # Add as river if we're flowing significantly
            if steepest_slope > 0.5:
                new_water[cx][cy] = True
    
    return new_water


def _build_tile_grid(
    elevation_map: list[list[int]],
    moisture_map: list[list[float]],
    biome_registry: BiomeRegistry,
    width: int = MAP_WIDTH,
    height: int = MAP_HEIGHT,
    water_map: list[list[bool]] | None = None,
) -> TileMap:
    """
    Build the TileMap grid from elevation and moisture maps.

    Each tile gets its biome, elevation, and terrain color assigned.

    Args:
        elevation_map: 2D elevation grid (0–31).
        moisture_map: 2D moisture grid (0.0–1.0).
        biome_registry: Registry of biome definitions.
        width: Map width in tiles (default: MAP_WIDTH).
        height: Map height in tiles (default: MAP_HEIGHT).
        water_map: Optional 2D water mask for water-aware biome classification.

    Returns:
        A partially-constructed TileMap with tiles initialized.
    """
    tile_map = TileMap(width, height, 0, 0)

    for x in range(width):
        for y in range(height):
            elevation = elevation_map[x][y]
            moisture = moisture_map[x][y]
            is_water = water_map[x][y] if water_map else False
            biome_id = classify_biome(elevation, moisture, is_water)
            biome = biome_registry.get(biome_id)

            tile = Tile(x, y, biome, elevation)
            tile.terrain_color = biome.get_terrain_color(elevation)
            tile_map.tiles[x][y] = tile

    return tile_map


def _build_biome_transitions(
    tile_map: TileMap,
    biome_registry: BiomeRegistry,
    resource_defs: dict[str, dict] | None = None,
) -> None:
    """
    Build biome transition zones (ecotones) by blending resource spawn lists
    at biome borders.

    Only processes tiles at biome borders and their neighbors within the
    transition radius, reducing work from O(n * r^2) to O(border * r^2)
    where border is typically 10-15% of tiles.

    Args:
        tile_map: The TileMap with biomes already assigned.
        biome_registry: Registry of biome definitions for looking up spawn lists.
        resource_defs: Optional dict of resource_id -> resource data (from resources.json).
            If provided, biome affinity is checked to prevent inappropriate resources
            from spawning in biome transition zones.
    """
    TRANSITION_RADIUS = 2
    MIN_AFFINITY_THRESHOLD = 0.05  # Only blend resources with at least this affinity

    # Load resource definitions if not provided
    if resource_defs is None:
        from data import load_json_list
        resource_defs = {r["id"]: r for r in load_json_list("resources.json", "resources")}

    # Step 1: Identify border tiles (tiles with at least one different-biome neighbor)
    border_tiles: list[tuple[int, int]] = []
    for x in range(tile_map.width):
        for y in range(tile_map.height):
            tile = tile_map.tiles[x][y]
            if tile.biome is None:
                continue
            current_id = tile.biome.id
            # Check 4-connected neighbors for different biome
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                neighbor = tile_map.get_tile(x + dx, y + dy)
                if neighbor is not None and neighbor.biome is not None:
                    if neighbor.biome.id != current_id:
                        border_tiles.append((x, y))
                        break

    # Step 2: Collect all tiles within transition radius of borders
    tiles_to_process: set[tuple[int, int]] = set()
    for bx, by in border_tiles:
        for dx in range(-TRANSITION_RADIUS, TRANSITION_RADIUS + 1):
            for dy in range(-TRANSITION_RADIUS, TRANSITION_RADIUS + 1):
                x, y = bx + dx, by + dy
                if 0 <= x < tile_map.width and 0 <= y < tile_map.height:
                    tiles_to_process.add((x, y))

    # Step 3: Precompute blended spawn lists for biome pairs (cached)
    blended_cache: dict[tuple[str, str], list[str]] = {}

    # Step 4: Only process tiles near biome borders
    for x, y in tiles_to_process:
        tile = tile_map.tiles[x][y]
        if tile.biome is None:
            continue
        
        current_biome_id = tile.biome.id
        neighbor_biomes: set[str] = set()

        # Check all neighbors within transition radius
        for dx in range(-TRANSITION_RADIUS, TRANSITION_RADIUS + 1):
            for dy in range(-TRANSITION_RADIUS, TRANSITION_RADIUS + 1):
                if dx == 0 and dy == 0:
                    continue
                neighbor = tile_map.get_tile(x + dx, y + dy)
                if neighbor is not None and neighbor.biome is not None:
                    neighbor_biomes.add(neighbor.biome.id)

        # If we have neighboring biomes different from current, blend
        other_biomes = neighbor_biomes - {current_biome_id}
        if not other_biomes:
            continue

        # Build blended spawn list (use cache for biome pairs)
        base_spawns = set(tile.biome.resource_spawns)
        for other_id in other_biomes:
            cache_key = tuple(sorted((current_biome_id, other_id)))
            if cache_key in blended_cache:
                base_spawns.update(blended_cache[cache_key])
                continue
            
            other_biome = biome_registry.get(other_id)
            if other_biome is None:
                continue
            # Add resources from other biome that aren't already in base,
            # but only if they have reasonable affinity for the current biome
            added = []
            for res_id in other_biome.resource_spawns:
                if res_id in base_spawns:
                    continue
                # Check biome affinity
                res_data = resource_defs.get(res_id)
                if res_data is None:
                    continue
                affinity = res_data.get("biome_affinity", {}).get(current_biome_id, 1.0)
                if affinity >= MIN_AFFINITY_THRESHOLD:
                    added.append(res_id)
            blended_cache[cache_key] = added
            base_spawns.update(added)

        # Update tile's biome resource_spawns with blended list
        tile.biome.resource_spawns = list(base_spawns)


def _has_swamp_neighbor(tile_map: TileMap, x: int, y: int) -> bool:
    """Check if any adjacent tile is in the swamp biome."""
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    for dx, dy in directions:
        neighbor = tile_map.get_tile(x + dx, y + dy)
        if neighbor is not None and neighbor.biome.id == "swamp":
            return True
    return False


def _build_resource_integral_image(tile_map: TileMap) -> np.ndarray:
    """
    Build a summed-area table (integral image) for resource nodes.
    
    Allows O(1) rectangular sum queries instead of O(radius^2) loops.
    
    Returns:
        2D numpy array of shape (width+1, height+1) where integral[y, x]
        contains the sum of resources in rectangle (0,0) to (x-1, y-1).
    """
    integral = np.zeros((tile_map.width + 1, tile_map.height + 1), dtype=np.int32)
    
    for x in range(tile_map.width):
        row_sum = 0
        for y in range(tile_map.height):
            has_resource = 1 if tile_map.tiles[x][y].resource_node is not None else 0
            row_sum += has_resource
            integral[x + 1, y + 1] = integral[x, y + 1] + row_sum
    
    return integral


def _count_resources_in_rect(integral: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> int:
    """
    Count resources in rectangle [x1, x2) x [y1, y2) using integral image.
    
    Args:
        integral: Summed-area table from _build_resource_integral_image
        x1, y1: Inclusive top-left corner
        x2, y2: Exclusive bottom-right corner
        
    Returns:
        Resource count in rectangle
    """
    # Clamp to valid range
    x1 = max(0, min(x1, integral.shape[0] - 1))
    y1 = max(0, min(y1, integral.shape[1] - 1))
    x2 = max(0, min(x2, integral.shape[0] - 1))
    y2 = max(0, min(y2, integral.shape[1] - 1))
    
    return (
        integral[x2, y2] - integral[x1, y2] - integral[x2, y1] + integral[x1, y1]
    )


def _count_nearby_resources(tile_map: TileMap, x: int, y: int, radius: int = 3, integral: np.ndarray | None = None) -> int:
    """
    Count resource nodes within a square radius of the given tile.
    
    If integral image is provided, uses O(1) query; otherwise falls back to loop.
    
    Args:
        tile_map: The TileMap.
        x: Tile X coordinate.
        y: Tile Y coordinate.
        radius: Search radius in tiles (square area).
        integral: Optional precomputed integral image for O(1) queries.
        
    Returns:
        Number of resource nodes within range.
    """
    if integral is not None:
        x1, y1 = x - radius, y - radius
        x2, y2 = x + radius + 1, y + radius + 1
        return _count_resources_in_rect(integral, x1, y1, x2, y2)
    
    # Fallback: original loop-based method
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
    
    # Build integral image for O(1) resource counting
    integral = _build_resource_integral_image(tile_map)
    
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

            resource_score = _count_nearby_resources(tile_map, x, y, radius=3, integral=integral)
            candidates.append((x, y, resource_score))

    if not candidates:
        for x in range(tile_map.width):
            for y in range(tile_map.height):
                tile = tile_map.tiles[x][y]
                if tile.biome.mega_cluster == "temperate" and 1 <= tile.elevation <= 3:
                    resource_score = _count_nearby_resources(tile_map, x, y, radius=3, integral=integral)
                    candidates.append((x, y, resource_score))

    if not candidates:
        return (MAP_WIDTH // 2, MAP_HEIGHT // 2)

    # Sort by resource score descending, then shuffle within same score tier
    candidates.sort(key=lambda c: -c[2])
    best_score = candidates[0][2]
    top_candidates = [(x, y) for x, y, score in candidates if score == best_score]
    rng.shuffle(top_candidates)
    return top_candidates[0]
