"""
resource_placer.py — Resource placement engine.

Encapsulates the logic for placing resource nodes on the tile map:
  - Loading resource definitions from resources.json
  - Precomputing season-filtered resource lists
  - Density-based random placement with rarity clamping
  - Biome affinity weighting
  - Progression zones (distance-from-spawn rarity gating)
  - Vein/cluster placement for ore/stone
  - Seasonal availability gating and compensation
  - Clustering bonus for same-biome resources
  - Analytics hooks for placement telemetry
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import numpy as np

from config import RARITY_DENSITY_RANGE
from world.resource_node import ResourceNode

if TYPE_CHECKING:
    from seasons.season_system import SeasonSystem
    from world.tile_map import TileMap


@dataclass
class ResourcePlacer:
    """
    Places resource nodes on a TileMap using density-based random placement.

    Features:
        - Rarity-based density clamping (via ResourceNode.effective_density)
        - Biome affinity weighting (resource.biome_affinity)
        - Progression zones (rarity gated by distance from spawn)
        - Vein placement for ore/stone (multi-tile clusters)
        - Seasonal compensation (density boost for season-gated resources)
        - Clustering bonus for adjacent same-resource tiles
        - Analytics hooks for placement telemetry
        - Dynamic density scaling for multiplayer (player_count * density_multiplier)

    Fields:
        rng: Random instance seeded for deterministic placement.
        season_system: Optional SeasonSystem for seasonal gating.
        _resource_cache: Per-instance lookup of resource_id → ResourceNode
            (reloaded fresh each place()).
        _available_resources: Precomputed set of resource IDs available this season.
        _tile_distances: Precomputed distance from spawn for each tile.
    """

    rng: random.Random
    season_system: object | None = None
    player_count: int = 1
    density_multiplier: float = 1.0

    # Per-instance resource lookup (reloaded fresh each place()).
    _resource_cache: dict[str, ResourceNode] = field(default_factory=dict, repr=False)
    _available_resources: set[str] = field(default_factory=set, repr=False)
    # Analytics: resource_id -> number of nodes placed in current generation
    _placement_counts: dict[str, int] = field(default_factory=dict, repr=False)

    # Progression zone configuration: rarity -> max zone index
    # Zone 0: 0-30 tiles from spawn (common only)
    # Zone 1: 30-80 tiles (uncommon)
    # Zone 2: 80-150 tiles (rare)
    # Zone 3: 150+ tiles (epic, legendary)
    RARITY_MAX_ZONE: dict[str, int] = field(
        default_factory=lambda: {
            "ubiquitous": 3,
            "common": 3,
            "uncommon": 2,
            "rare": 1,
            "epic": 0,
            "legendary": 0,
        },
        repr=False,
    )

    # Zone boundaries (distance from spawn in tiles)
    ZONE_BOUNDARIES: tuple[int, ...] = (30, 80, 150)

    # Vein placement config
    VEIN_CATEGORIES: frozenset[str] = field(
        default_factory=lambda: frozenset({"ore", "stone"}), repr=False
    )
    VEIN_SIZE_RANGE: tuple[int, int] = (3, 7)

    # Poisson disc sampling for common/ubiquitous resources
    POISSON_RADIUS: dict[str, int] = field(
        default_factory=lambda: {
            "ubiquitous": 3,
            "common": 4,
        },
        repr=False,
    )

    # Clustering bonus
    CLUSTER_BONUS = 0.02

    # Maximum fraction of tiles that may hold a resource node. Placement
    # stops adding nodes beyond this so the map never saturates visually,
    # even across repeated seasonal re-placements.
    MAX_TILE_OCCUPANCY = 0.40

    def place(self, tile_map: TileMap, *, enforce_zones: bool = True, allow_overwrite: bool = False,
              previous_season: str | None = None) -> None:
        """
        Place all resource nodes on the tile map.

        Flow:
        1. Load resource definitions and precompute available resources
        2. Precompute spawn distances for progression zones (if enforcing)
        3. **Poisson disc pass**: Place common/ubiquitous resources with even distribution
        3. Iterate tiles, attempt placement with zone/biome/season checks
        4. Handle vein placement for ore/stone categories

        Args:
            tile_map: The TileMap to place resources on.
            enforce_zones: If True, apply progression zone restrictions.
                Set to False for seasonal re-placement to allow resources
                anywhere in valid biomes.
            allow_overwrite: Kept for API compatibility; occupied tiles are
                never overwritten — seasonal re-placement fills empty tiles
                only.
            previous_season: When set (seasonal re-placement), only resources
                unavailable in that season but available now are placed, so a
                season rollover cannot re-densify tiles already eligible for
                the previous season's resources.
        """
        self._resource_cache = ResourcePlacer._load_resource_definitions()
        self._available_resources = self._precompute_available()
        if previous_season is not None:
            # Only place newly-in-season resources; everything available in
            # the previous season has already had its placement chance.
            self._available_resources = {
                rid for rid in self._available_resources
                if (r := self._resource_cache[rid]).seasons_available
                and previous_season not in r.seasons_available
            }
        # Reset analytics counter for this generation
        self._placement_counts = {}

        # Occupancy accounting for the global density cap
        self._occupied_tiles = sum(
            1 for x in range(tile_map.width) for y in range(tile_map.height)
            if tile_map.tiles[x][y] is not None and tile_map.tiles[x][y].resource_node is not None
        )
        self._total_tiles = tile_map.width * tile_map.height

        # Precompute spawn distances for progression zones (if enforcing)
        if enforce_zones:
            spawn_x, spawn_y = tile_map.spawn_x, tile_map.spawn_y
            # Vectorized distance computation with NumPy
            xs = np.arange(tile_map.width) - spawn_x
            ys = np.arange(tile_map.height) - spawn_y
            dist_grid = np.sqrt(xs[:, None] ** 2 + ys[None, :] ** 2)
            # Convert to dict for compatibility with existing lookups
            self._tile_distances = {
                (x, y): float(dist_grid[x, y])
                for x in range(tile_map.width)
                for y in range(tile_map.height)
            }
        else:
            self._tile_distances = {}

        # Track which tiles have been assigned (for vein placement)
        self._assigned_tiles: set[tuple[int, int]] = set()

        # --- Landmark resources pass: guaranteed special nodes per biome region ---
        if enforce_zones:
            self._landmark_pass(tile_map)

        # --- Poisson disc pass for common/ubiquitous resources ---
        if enforce_zones:
            self._poisson_disc_pass(tile_map)

        # Precompute available resources per biome to avoid dict lookups in hot loop
        biome_available_resources: dict[str, list[ResourceNode]] = {}
        for biome_id in set(tile_map.tiles[x][y].biome.id for x in range(tile_map.width) for y in range(tile_map.height) if tile_map.tiles[x][y].biome is not None):
            biome_obj = tile_map.tiles[0][0].biome.__class__.__bases__[0]  # dummy to get type
            # Find a tile with this biome to get its resource_spawns
            spawns = []
            for x in range(tile_map.width):
                for y in range(tile_map.height):
                    t = tile_map.tiles[x][y]
                    if t.biome is not None and t.biome.id == biome_id:
                        spawns = t.biome.resource_spawns
                        break
                if spawns:
                    break
            if spawns:
                avail = [self._resource_cache[r] for r in spawns if r in self._available_resources and self._resource_cache.get(r) is not None]
                biome_available_resources[biome_id] = avail

        # Precompute zones for all tiles if enforcing zones
        tile_zones: dict[tuple[int, int], int] = {}
        if enforce_zones:
            for x in range(tile_map.width):
                for y in range(tile_map.height):
                    tile_zones[(x, y)] = self._get_zone(self._tile_distances.get((x, y), 0))

        # Cache frequently accessed attributes locally
        rarity_max_zone = self.RARITY_MAX_ZONE
        vein_categories = self.VEIN_CATEGORIES
        assigned_tiles = self._assigned_tiles
        rng = self.rng
        compute_density = self._compute_density
        try_place_vein = self._try_place_vein
        record_placement = self._record_placement

        for x in range(tile_map.width):
            for y in range(tile_map.height):
                if (x, y) in assigned_tiles:
                    continue

                # Global density cap: never let resources saturate the map
                if self._at_occupancy_cap():
                    continue

                tile = tile_map.tiles[x][y]
                biome_id = tile.biome.id
                
                # Get precomputed available resources for this biome
                avail_resources = biome_available_resources.get(biome_id)
                if not avail_resources:
                    continue

                zone = tile_zones.get((x, y), 0) if enforce_zones else 0

                # Check if tile is empty (for non-overwrite mode)
                tile_empty = tile.resource_node is None
                
                if not tile_empty:
                    # Existing nodes are always preserved: seasonal
                    # re-placement only fills empty tiles, it never evicts
                    # resources from previous seasons.
                    continue

                for resource in avail_resources:
                    # Check if we can place here
                    can_place = tile_empty

                    if not can_place:
                        continue

                    # Check progression zone gating (only on initial generation)
                    if enforce_zones:
                        max_zone = rarity_max_zone.get(resource.rarity, 3)
                        if max_zone < zone:
                            continue  # Too rare for this zone

                    adjusted_density = compute_density(resource, tile, biome_id, tile_map, zone)
                    if adjusted_density <= 0:
                        continue

                    if rng.random() < adjusted_density:
                        # Check if this resource should form a vein
                        if resource.category in vein_categories:
                            if try_place_vein(resource, tile, tile_map, biome_id, zone):
                                record_placement(resource.resource_id)
                                continue

                        # Single-tile placement
                        tile.resource_node = replace(resource)
                        assigned_tiles.add((x, y))
                        record_placement(resource.resource_id)

    def _landmark_pass(self, tile_map: TileMap) -> None:
        """
        Place landmark resources - guaranteed special nodes per biome region.
        
        Identifies distinct biome regions using flood fill, then places
        one landmark resource (rare/epic/legendary) per region.
        """
        # Define landmark resources per biome (rare/epic/legendary that define the biome)
        LANDMARK_RESOURCES = {
            "forest": ["silk_nest", "elder_wood", "phoenix_feather"],
            "plains": ["water_source"],
            "coastal": ["celestial_crystal", "driftwood"],
            "swamp": ["dragonbone", "void_essence", "reed_bed"],
            "mountains": ["star_metal", "ancient_rune", "mithril_vein", "ghost_iron_deposit", "void_crystal", "obsidian_vein"],
            "desert": ["amber_deposit", "dead_tree", "rare_ore"],
        }
        
        visited = [[False] * tile_map.height for _ in range(tile_map.width)]
        
        for x in range(tile_map.width):
            for y in range(tile_map.height):
                if visited[x][y] or tile_map.tiles[x][y].biome is None:
                    continue
                
                biome_id = tile_map.tiles[x][y].biome.id
                landmarks = LANDMARK_RESOURCES.get(biome_id, [])
                if not landmarks:
                    continue
                
                # Flood fill to find this biome region
                region_tiles = []
                stack = [(x, y)]
                while stack:
                    cx, cy = stack.pop()
                    if visited[cx][cy]:
                        continue
                    visited[cx][cy] = True
                    tile = tile_map.tiles[cx][cy]
                    if tile.biome is None or tile.biome.id != biome_id:
                        continue
                    region_tiles.append((cx, cy))
                    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < tile_map.width and 0 <= ny < tile_map.height:
                            if not visited[nx][ny]:
                                stack.append((nx, ny))
                
                if len(region_tiles) < 10:  # Too small for a landmark
                    continue
                
                # Pick a landmark resource
                landmark_id = self.rng.choice(landmarks)
                resource = self._resource_cache.get(landmark_id)
                if resource is None:
                    continue
                
                # Pick a central tile in the region
                cx, cy = region_tiles[len(region_tiles) // 2]
                tile = tile_map.tiles[cx][cy]
                
                # Only place if tile is empty
                if tile.resource_node is not None:
                    # Find nearby empty tile
                    placed = False
                    for rx, ry in region_tiles:
                        t = tile_map.tiles[rx][ry]
                        if t.resource_node is None:
                            t.resource_node = replace(resource)
                            self._assigned_tiles.add((rx, ry))
                            placed = True
                            break
                    if not placed:
                        continue
                    self._record_placement(resource.resource_id)
                else:
                    tile.resource_node = replace(resource)
                    self._assigned_tiles.add((cx, cy))
                    self._record_placement(resource.resource_id)

    def _poisson_disc_pass(self, tile_map: TileMap) -> None:
        """
        Place common/ubiquitous resources using Bridson's Poisson disc algorithm
        with spatial grid for O(n) performance.
        
        This runs as a separate pass before regular placement to ensure
        common resources are evenly distributed.
        """
        # Collect common/ubiquitous resources per biome
        biome_resources: dict[str, list[str]] = {}
        for x in range(tile_map.width):
            for y in range(tile_map.height):
                tile = tile_map.tiles[x][y]
                biome_id = tile.biome.id
                if biome_id not in biome_resources:
                    biome_resources[biome_id] = []
                for res_id in tile.biome.resource_spawns:
                    if res_id not in self._available_resources:
                        continue
                    resource = self._resource_cache.get(res_id)
                    if resource and resource.rarity in ("ubiquitous", "common"):
                        biome_resources[biome_id].append(res_id)
        
        # Deduplicate
        for biome_id, res_list in biome_resources.items():
            biome_resources[biome_id] = list(set(res_list))
        
        # For each biome, place resources using Bridson's Poisson disc
        for biome_id, res_list in biome_resources.items():
            if not res_list:
                continue
            
            # Collect all candidate tiles of this biome
            candidates = []
            for x in range(tile_map.width):
                for y in range(tile_map.height):
                    tile = tile_map.tiles[x][y]
                    if tile.biome.id == biome_id and tile.resource_node is None:
                        candidates.append((x, y))
            
            if not candidates:
                continue
            
            # Use the smallest Poisson radius among these resources
            min_radius = min(self.POISSON_RADIUS.get(r, 4) for r in res_list)
            min_dist_sq = min_radius * min_radius
            
            # Spatial grid cell size = min_radius / sqrt(2)
            # Ensures at most one point per cell, and only need to check 3x3 neighbors
            cell_size = max(1, int(min_radius / math.sqrt(2)))
            grid_w = (tile_map.width + cell_size - 1) // cell_size
            grid_h = (tile_map.height + cell_size - 1) // cell_size
            grid: list[list[tuple[int, int] | None]] = [
                [None] * grid_h for _ in range(grid_w)
            ]
            
            self.rng.shuffle(candidates)

            for x, y in candidates:
                # Global density cap
                if self._at_occupancy_cap():
                    break

                # Check 3x3 neighboring grid cells for existing points
                gx, gy = x // cell_size, y // cell_size
                too_close = False
                
                for dx in (-1, 0, 1):
                    nx = gx + dx
                    if nx < 0 or nx >= grid_w:
                        continue
                    for dy in (-1, 0, 1):
                        ny = gy + dy
                        if ny < 0 or ny >= grid_h:
                            continue
                        other = grid[nx][ny]
                        if other is not None:
                            px, py = other
                            if (x - px) * (x - px) + (y - py) * (y - py) < min_dist_sq:
                                too_close = True
                                break
                    if too_close:
                        break
                
                if too_close:
                    continue
                
                # Try to place one of the resources
                tile = tile_map.tiles[x][y]
                if tile.resource_node is not None:
                    continue
                
                # Pick a random resource from the list
                resource_id = self.rng.choice(res_list)
                resource = self._resource_cache.get(resource_id)
                if resource is None:
                    continue
                
                # Compute density with zone 0 (center)
                density = self._compute_density(resource, tile, biome_id, tile_map, 0)
                if density <= 0:
                    continue
                
                if self.rng.random() < density:
                    tile.resource_node = replace(resource)
                    self._assigned_tiles.add((x, y))
                    grid[gx][gy] = (x, y)
                    self._record_placement(resource.resource_id)

    def _get_zone(self, distance: float) -> int:
        """Get progression zone index from spawn distance."""
        for i, boundary in enumerate(self.ZONE_BOUNDARIES):
            if distance < boundary:
                return i
        return len(self.ZONE_BOUNDARIES)

    def _precompute_available(self) -> set[str]:
        """Build the set of resource IDs available in the current season."""
        if self.season_system is None:
            return set(self._resource_cache.keys())

        available = set()
        for resource in self._resource_cache.values():
            if self._is_seasonally_available(resource):
                available.add(resource.resource_id)
        return available

    def _is_seasonally_available(self, resource: ResourceNode) -> bool:
        """Check if a resource is available in the current season."""
        # Primary gate: seasons_available field on the resource
        if resource.seasons_available:
            if self.season_system is None:
                return True
            if self.season_system.current_season not in resource.seasons_available:
                return False

        # Fallback: runtime availability dict (for dynamic overrides)
        if self.season_system is None:
            return True
        try:
            return self.season_system.is_resource_available(resource.resource_id)
        except Exception:
            return True

    def _compute_density(
        self,
        resource: ResourceNode,
        tile: object,
        biome_id: str,
        tile_map: "TileMap",
        zone: int,
    ) -> float:
        """
        Compute the effective placement density for a resource on a tile.

        Factors:
        1. Base effective_density (rarity-clamped)
        2. Biome affinity (resource.biome_affinity.get(biome_id, 1.0))
        3. Seasonal multiplier (season_system.get_resource_multiplier)
        4. Seasonal compensation (boost for season-gated resources in-season)
        5. Clustering bonus (adjacent same-resource)
        6. Zone density falloff (higher zones = slightly lower density)

        Args:
            resource: The ResourceNode being considered.
            tile: The Tile being considered for placement.
            biome_id: The biome ID of the tile.
            tile_map: The TileMap for neighbor lookups.
            zone: The progression zone index (0-3).

        Returns:
            Adjusted density (0.0–1.0+).
        """
        density = resource.effective_density

        # Biome affinity (default 1.0)
        density *= resource.biome_affinity.get(biome_id, 1.0)

        # Seasonal multiplier
        if self.season_system is not None:
            try:
                density *= self.season_system.get_resource_multiplier(resource.category)
            except Exception:
                pass

        # Seasonal compensation: boost density for season-gated resources when in-season
        if resource.seasons_available and self.season_system is not None:
            if self.season_system.current_season in resource.seasons_available:
                density *= 4.0 / len(resource.seasons_available)

        # Zone density falloff: further zones get slightly lower density
        # (compensates for larger area, keeps total counts balanced)
        zone_multipliers = (1.0, 0.9, 0.8, 0.7)
        if zone < len(zone_multipliers):
            density *= zone_multipliers[zone]

        # Dynamic density scaling for multiplayer
        # Scale by player_count * density_multiplier, but cap to avoid overcrowding
        if self.player_count > 1:
            scale = self.player_count * self.density_multiplier
            # Cap scaling: max 2x for 4 players, sqrt scaling for more
            if scale > 2.0:
                scale = 1.0 + (scale - 1.0) * 0.5  # Diminishing returns
            density *= scale

        # Clustering bonus
        density += self._get_clustering_bonus(tile, resource.resource_id, tile_map)

        return density

    def _get_clustering_bonus(
        self, tile: object, resource_id: str, tile_map: "TileMap",
    ) -> float:
        """Return density bonus if an orthogonal neighbor has the same resource."""
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        for dx, dy in directions:
            neighbor = tile_map.get_tile(tile.x + dx, tile.y + dy)
            if neighbor is not None and neighbor.resource_node is not None:
                if neighbor.resource_node.resource_id == resource_id:
                    return self.CLUSTER_BONUS
        return 0.0

    def _try_place_vein(
        self,
        resource: ResourceNode,
        start_tile: object,
        tile_map: "TileMap",
        biome_id: str,
        zone: int,
    ) -> bool:
        """
        Attempt to place a multi-tile vein for ore/stone resources.

        Uses a random walk to place 3-7 connected tiles of the same resource.
        Returns True if vein was placed, False otherwise.

        Args:
            resource: The ResourceNode to place.
            start_tile: The starting tile for the vein.
            tile_map: The TileMap.
            biome_id: The biome ID.
            zone: The progression zone index.

        Returns:
            True if vein was successfully placed (3+ tiles).
        """
        vein_size = self.rng.randint(*self.VEIN_SIZE_RANGE)
        vein_tiles = [start_tile]
        current = start_tile

        for _ in range(vein_size - 1):
            # Find valid neighbors (same biome, unassigned, no resource)
            neighbors = []
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = current.x + dx, current.y + dy
                if (nx, ny) in self._assigned_tiles:
                    continue
                neighbor = tile_map.get_tile(nx, ny)
                if neighbor is None:
                    continue
                if neighbor.resource_node is not None:
                    continue
                if neighbor.biome.id != biome_id:
                    continue
                # Check zone gating for this neighbor too
                n_zone = self._get_zone(self._tile_distances.get((nx, ny), 0))
                max_zone = self.RARITY_MAX_ZONE.get(resource.rarity, 3)
                if max_zone < n_zone:
                    continue
                neighbors.append(neighbor)

            if not neighbors:
                break

            # Prefer continuing in same direction (weighted random)
            # For simplicity, just pick random neighbor
            current = self.rng.choice(neighbors)
            vein_tiles.append(current)

        # Only place if we got at least 3 tiles
        if len(vein_tiles) >= 3:
            for t in vein_tiles:
                t.resource_node = replace(resource)
                self._assigned_tiles.add((t.x, t.y))
            self._record_placement(resource.resource_id, len(vein_tiles))
            return True

        return False

    @staticmethod
    def _load_resource_definitions() -> dict[str, ResourceNode]:
        """
        Load resource definitions from resources.json into a lookup dict.

        Always returns a fresh dict (no shared class-level state), so callers
        get an independent, per-call result.

        Returns:
            Dict mapping resource_id → ResourceNode. Empty dict (with a
            warning) if the data file cannot be read.
        """
        try:
            from data import load_json_list
            all_resources = load_json_list("resources.json", "resources")
            return {
                r["id"]: ResourceNode.from_dict(r, r.get("biome", "forest"))
                for r in all_resources
            }
        except Exception:
            import sys
            import traceback
            print(
                "Warning: failed to load resources.json; no resources will be placed.",
                file=sys.stderr,
            )
            traceback.print_exc()
            return {}

    def _record_placement(self, resource_id: str, count: int = 1) -> None:
        """Record a resource placement for analytics and occupancy tracking."""
        self._placement_counts[resource_id] = self._placement_counts.get(resource_id, 0) + count
        self._occupied_tiles = getattr(self, "_occupied_tiles", 0) + count

    def _at_occupancy_cap(self) -> bool:
        """Return True once the map holds the maximum allowed resource density."""
        total = getattr(self, "_total_tiles", 0)
        if total <= 0:
            return False
        return self._occupied_tiles >= self.MAX_TILE_OCCUPANCY * total

    def get_placement_counts(self) -> dict[str, int]:
        """Return a copy of the placement counts for this generation."""
        return dict(self._placement_counts)