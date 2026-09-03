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


# ── Vectorized noise grids (exact float-order replicas of the scalar loops) ──

def _fbm_grid(xs: "np.ndarray", ys: "np.ndarray", scale: float, octaves: int,
              persistence: float, lacunarity: float, seed: int) -> "np.ndarray":
    """Vectorized _fbm_noise over a coordinate grid. float64 accumulate,
    matching the Python loop's arithmetic order bit-for-bit."""
    from world.noise_np import pnoise2_grid

    value = np.zeros(xs.shape, dtype=np.float64)
    amplitude = 1.0
    frequency = scale
    for _ in range(octaves):
        n = pnoise2_grid(xs * frequency, ys * frequency, 10000.0, 10000.0, seed)
        value += amplitude * n.astype(np.float64)
        amplitude *= persistence
        frequency *= lacunarity
    return value


def _ridge_grid(xs: "np.ndarray", ys: "np.ndarray", scale: float, octaves: int,
                persistence: float, lacunarity: float, seed: int) -> "np.ndarray":
    """Vectorized _ridge_noise over a coordinate grid (float64)."""
    from world.noise_np import pnoise2_grid

    value = np.zeros(xs.shape, dtype=np.float64)
    amplitude = 1.0
    frequency = scale
    for _ in range(octaves):
        n = pnoise2_grid(xs * frequency, ys * frequency, 10000.0, 10000.0, seed).astype(np.float64)
        n = 1.0 - 2.0 * np.abs(n)
        value += amplitude * n
        amplitude *= persistence
        frequency *= lacunarity
    return value


def _coord_grid(width: int, height: int) -> tuple["np.ndarray", "np.ndarray"]:
    """float64 coordinate grids with column-major layout: grid[x, y]."""
    xs, ys = np.meshgrid(
        np.arange(width, dtype=np.float64),
        np.arange(height, dtype=np.float64),
        indexing="ij",
    )
    return xs, ys


def _generate_base_elevation(seed: int, width: int, height: int) -> list[list[float]]:
    """Generate base elevation using combined Perlin + Ridge noise with domain warping.

    Vectorized replica of the original per-tile loop (same float ops in the
    same order, so results are bitwise identical).
    """
    from config import ELEVATION_LEVELS

    xs, ys = _coord_grid(width, height)

    # Domain warp
    wx = xs + _fbm_grid(xs, ys, DOMAIN_WARP_SCALE, DOMAIN_WARP_OCTAVES, 0.5, 2.0, seed + 1000) * DOMAIN_WARP_AMPLITUDE
    wy = ys + _fbm_grid(xs, ys, DOMAIN_WARP_SCALE, DOMAIN_WARP_OCTAVES, 0.5, 2.0, seed + 2000) * DOMAIN_WARP_AMPLITUDE

    base = _fbm_grid(wx, wy, NOISE_SCALE, ELEVATION_OCTAVES, 0.5, 2.0, seed)
    ridge = _ridge_grid(wx, wy, RIDGE_NOISE_SCALE, RIDGE_OCTAVES, RIDGE_PERSISTENCE, RIDGE_LACUNARITY, seed + 500)

    combined = 0.85 * base + 0.15 * ridge
    combined = combined - 0.2
    normalized = (combined + 1.0) / 2.0
    elev = (normalized * ELEVATION_LEVELS).astype(np.int64)
    np.clip(elev, 0, ELEVATION_LEVELS - 1, out=elev)
    return elev.tolist()


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
    from world.noise_np import pnoise2_grid

    xs, ys = _coord_grid(width, height)
    # C-side octaves>1 loop (float32 freq/repeat accumulation), replicated.
    x32 = (xs * MOISTURE_SCALE + 100.0).astype(np.float32)
    y32 = (ys * MOISTURE_SCALE + 100.0).astype(np.float32)
    freq = np.float32(1.0)
    amp = np.float32(1.0)
    max_total = np.float32(0.0)
    total = np.zeros(x32.shape, dtype=np.float32)
    for _ in range(MOISTURE_OCTAVES):
        n = pnoise2_grid(
            x32 * freq, y32 * freq,
            np.float32(1024.0) * freq, np.float32(1024.0) * freq,
            seed + 1,
        )
        total += n * amp
        max_total += amp
        freq = np.float32(freq * np.float32(2.0))
        amp = np.float32(amp * np.float32(0.5))
    value = (total / max_total).astype(np.float64) * MOISTURE_RANGE_MULTIPLIER
    moisture = (value + 1.0) / 2.0
    np.clip(moisture, 0.0, 1.0, out=moisture)
    return moisture.tolist()


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
    
    # (Cliff/scree detection was removed: its result was never consumed and
    # its scree extension used the module-global RNG, breaking determinism.)
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
            ).place(tile_map, enforce_zones=False, allow_overwrite=True,
                    previous_season=_previous_season)
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
    from config import ELEVATION_LEVELS

    # First pass: classify initial biomes (vectorized decision tree matching
    # classify_biome() case-structure exactly).
    biome_map = _classify_biome_grid(elevation, moisture, width, height)

    elev_arr = np.asarray(elevation, dtype=np.int64)
    refined = elev_arr.copy()
    xs, ys = _coord_grid(width, height)

    # Second pass: apply biome-specific noise refinement, one vectorized
    # pass per distinct parameter set (identical float64 op order as the
    # original nested loop).
    groups: dict[tuple, list[str]] = {}
    for biome_id, params in BIOME_NOISE_PARAMS.items():
        groups.setdefault(tuple(sorted(params.items())), []).append(biome_id)

    for params_key, biome_ids in groups.items():
        mask = np.isin(biome_map, biome_ids)
        if not mask.any():
            continue
        params = BIOME_NOISE_PARAMS[biome_ids[0]]
        detail_scale = params.get("scale", NOISE_SCALE)
        detail_octaves = params.get("octaves", ELEVATION_OCTAVES)
        detail_persistence = params.get("persistence", 0.5)
        detail_lacunarity = params.get("lacunarity", 2.0)
        ridge_weight = params.get("ridge_weight", 0.0)
        warp_amp = params.get("domain_warp", 0.0)

        if warp_amp > 0:
            wx = xs + _fbm_grid(xs, ys, DOMAIN_WARP_SCALE, DOMAIN_WARP_OCTAVES, 0.5, 2.0, seed + 3000 + 1000) * warp_amp
            wy = ys + _fbm_grid(xs, ys, DOMAIN_WARP_SCALE, DOMAIN_WARP_OCTAVES, 0.5, 2.0, seed + 3000 + 2000) * warp_amp
        else:
            wx, wy = xs, ys

        detail = _fbm_grid(wx, wy, detail_scale, detail_octaves, detail_persistence, detail_lacunarity, seed + 4000)

        if ridge_weight > 0:
            ridge = _ridge_grid(wx, wy, RIDGE_NOISE_SCALE, RIDGE_OCTAVES, RIDGE_PERSISTENCE, RIDGE_LACUNARITY, seed + 5000)
            combined = (1.0 - ridge_weight) * detail + ridge_weight * ridge
        else:
            combined = detail

        normalized = (combined + 1.0) / 2.0
        detail_elev = (normalized * (ELEVATION_LEVELS - 1)).astype(np.int64)
        merged = (0.8 * elev_arr + 0.2 * detail_elev).astype(np.int64)
        np.clip(merged, 0, ELEVATION_LEVELS - 1, out=merged)
        refined = np.where(mask, merged, refined)

    return refined.tolist()


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
    
    # Per-tile downhill neighbor lists with normalized slope weights are
    # rebuilt whenever elevations change — the update order is strict
    # Gauss-Seidel (x-major scan), so this pass cannot be vectorized without
    # changing results; we micro-optimize the scalar loop instead.
    evap_keep = 1.0 - EROSION_EVAPORATION

    for iteration in range(EROSION_ITERATIONS):
        # Add rain (flat, no loop branch)
        for col in water:
            for y in range(height):
                col[y] += EROSION_RAIN_AMOUNT

        # Flow water and transport sediment
        for x in range(width):
            ecol = elev[x]
            wcol = water[x]
            scol = sediment[x]
            for y in range(height):
                w_xy = wcol[y]
                if w_xy <= 0:
                    continue

                current_height = ecol[y]

                # Find neighbors and calculate slopes
                slopes = []
                slopes_append = slopes.append
                total_slope = 0.0
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        slope = current_height - elev[nx][ny]
                        if slope > 0:
                            dist = 1.0 if dx == 0 or dy == 0 else 1.414
                            slope /= dist
                            slopes_append((nx, ny, slope))
                            total_slope += slope

                if total_slope > 0:
                    # Distribute water and sediment downhill
                    for nx, ny, slope in slopes:
                        flow = w_xy * (slope / total_slope)
                        sediment_capacity = flow * slope * EROSION_SEDIMENT_CAPACITY_FACTOR * EROSION_GRAVITY

                        if scol[y] > sediment_capacity:
                            # Deposit excess sediment
                            deposit = min(scol[y] - sediment_capacity, scol[y])
                            ecol[y] += deposit
                            scol[y] -= deposit
                        elif scol[y] < sediment_capacity:
                            # Erode terrain
                            erode = min(sediment_capacity - scol[y], current_height * EROSION_SOLUBILITY)
                            ecol[y] -= erode
                            scol[y] += erode

                        # Move water
                        water[nx][ny] += flow
                        w_xy -= flow
                    wcol[y] = w_xy

        # Evaporate water
        for x in range(width):
            wcol = water[x]
            scol = sediment[x]
            ecol = elev[x]
            for y in range(height):
                w_xy = wcol[y] * evap_keep
                if w_xy < 0.001:
                    wcol[y] = 0.0
                    # Deposit remaining sediment
                    if scol[y] > 0:
                        ecol[y] += scol[y]
                        scol[y] = 0.0
                else:
                    wcol[y] = w_xy
    
    # Convert back to int
    result = [[0] * height for _ in range(width)]
    for x in range(width):
        for y in range(height):
            result[x][y] = max(0, min(ELEVATION_LEVELS - 1, int(elev[x][y])))
    
    return result


def _classify_biome_grid(elevation, moisture, width: int, height: int) -> "np.ndarray":
    """Vectorized classify_biome(): returns an object array [x][y] of biome ids.

    Mirrors the nested if/elif thresholds of the scalar version exactly
    (both compare the same float64 moisture values).
    """
    elev = np.asarray(elevation)
    moist = np.asarray(moisture, dtype=np.float64)
    out = np.empty(elev.shape, dtype=object)

    m = elev >= 26
    out[m] = "mountains"

    m = (elev >= 20) & (elev < 26)
    sel = m
    out[sel & (moist < 0.15)] = "desert"
    out[sel & (moist >= 0.15) & (moist < 0.35)] = "plains"
    out[sel & (moist >= 0.35)] = "mountains"

    m = (elev >= 14) & (elev < 20)
    sel = m
    out[sel & (moist < 0.15)] = "desert"
    out[sel & (moist >= 0.15) & (moist < 0.3)] = "plains"
    out[sel & (moist >= 0.3) & (moist < 0.6)] = "forest"
    out[sel & (moist >= 0.6) & (moist < 0.8)] = "mountains"
    out[sel & (moist >= 0.8)] = "swamp"

    m = (elev >= 8) & (elev < 14)
    sel = m
    out[sel & (moist < 0.2)] = "desert"
    out[sel & (moist >= 0.2) & (moist < 0.35)] = "plains"
    out[sel & (moist >= 0.35)] = "forest"  # <0.55/0.75 branches both swamp below
    out[sel & (moist >= 0.55)] = "swamp"

    m = (elev >= 4) & (elev < 8)
    sel = m
    out[sel & (moist < 0.2)] = "desert"
    out[sel & (moist >= 0.2) & (moist < 0.35)] = "plains"
    out[sel & (moist >= 0.35) & (moist < 0.4)] = "forest"
    out[sel & (moist >= 0.4)] = "coastal"

    m = elev < 4
    sel = m
    out[sel & (moist < 0.25)] = "desert"
    out[sel & (moist >= 0.25) & (moist < 0.4)] = "plains"
    out[sel & (moist >= 0.4)] = "coastal"

    return out


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

    # Vectorized implementation: identical blend content as the scalar
    # version, computed per unique (own biome, neighbor-biome set) combo.

    w, h = tile_map.width, tile_map.height

    # Integer biome-id grid (None → -1).
    id_to_ix: dict[str, int] = {}
    grid = np.full((w, h), -1, dtype=np.int64)
    tiles = tile_map.tiles
    for x in range(w):
        col = tiles[x]
        for y in range(h):
            b = col[y].biome
            if b is not None:
                ix = id_to_ix.get(b.id)
                if ix is None:
                    ix = len(id_to_ix)
                    id_to_ix[b.id] = ix
                grid[x, y] = ix
    ix_to_id = [None] * len(id_to_ix)
    for bid, ix in id_to_ix.items():
        ix_to_id[ix] = bid
    n_biomes = len(id_to_ix)
    if n_biomes > 60:
        raise RuntimeError("too many biomes for ecotone bitmask")

    R = TRANSITION_RADIUS
    padded = np.full((w + 2 * R, h + 2 * R), -1, dtype=np.int64)
    padded[R : R + w, R : R + h] = grid

    # Border tiles: any 4-connected neighbor with a different biome id.
    border = np.zeros((w, h), dtype=bool)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        nb = padded[R + dx : R + dx + w, R + dy : R + dy + h]
        border |= (nb != grid) & (nb != -1) & (grid != -1)

    # Process mask: square dilation of borders by R (5×5 neighborhood).
    padded_border = np.pad(border, R)
    process = np.zeros((w, h), dtype=bool)
    for dx in range(-R, R + 1):
        for dy in range(-R, R + 1):
            process |= padded_border[R + dx : R + dx + w, R + dy : R + dy + h]

    # Per-tile neighbor-biome presence bitset over the 5×5 neighborhood.
    keys = grid.astype(np.int64) << n_biomes
    for b in range(n_biomes):
        pres = np.zeros((w, h), dtype=bool)
        for dx in range(-R, R + 1):
            for dy in range(-R, R + 1):
                pres |= padded[R + dx : R + dx + w, R + dy : R + dy + h] == b
        keys |= pres.astype(np.int64) << b

    # Blend content per (own biome, other biome) pair — cache keyed on the
    # pair, filtered against the tile's own spawn list only (never against a
    # growing merged set: that made results depend on set iteration order
    # and therefore on PYTHONHASHSEED).
    blended_cache: dict[tuple[str, str], list[str]] = {}

    def _pair_added(current_biome_id: str, other_id: str, own_spawns: set) -> list[str]:
        added = blended_cache.get((current_biome_id, other_id))
        if added is not None:
            return added
        added = []
        other_biome = biome_registry.get(other_id)
        if other_biome is not None:
            for res_id in other_biome.resource_spawns:
                if res_id in own_spawns:
                    continue
                res_data = resource_defs.get(res_id)
                if res_data is None:
                    continue
                affinity = res_data.get("biome_affinity", {}).get(current_biome_id, 1.0)
                if affinity >= MIN_AFFINITY_THRESHOLD:
                    added.append(res_id)
        blended_cache[(current_biome_id, other_id)] = added
        return added

    sel = process & (grid != -1)
    if not sel.any():
        return

    for k in np.unique(keys[sel]):
        own_ix = int(k) >> n_biomes
        other_bits = int(k) & ((1 << n_biomes) - 1)
        other_ixs = [b for b in range(n_biomes) if other_bits & (1 << b) and b != own_ix]
        if not other_ixs:
            continue
        current_biome_id = ix_to_id[own_ix]
        own_spawns = set(biome_registry.get(current_biome_id).resource_spawns)
        merged = set(own_spawns)
        for b in other_ixs:
            merged.update(_pair_added(current_biome_id, ix_to_id[b], own_spawns))
        blended = sorted(merged)

        # Assign to every tile with this combo. Sorted so downstream resource
        # placement (which consumes the list in order, feeding the RNG) is
        # identical in every process.
        combo = np.nonzero(sel & (keys == k))
        for x, y in zip(combo[0].tolist(), combo[1].tolist()):
            tiles[x][y].blended_spawns = blended


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
