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
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

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

    # Per-instance resource lookup (reloaded fresh each place()).
    _resource_cache: dict[str, ResourceNode] = field(default_factory=dict, repr=False)
    _available_resources: set[str] = field(default_factory=set, repr=False)

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

    # Clustering bonus
    CLUSTER_BONUS = 0.02

    def place(self, tile_map: TileMap, *, enforce_zones: bool = True, allow_overwrite: bool = False) -> None:
        """
        Place all resource nodes on the tile map.

        Flow:
        1. Load resource definitions and precompute available resources
        2. Precompute spawn distances for progression zones (if enforcing)
        3. Iterate tiles, attempt placement with zone/biome/season checks
        4. Handle vein placement for ore/stone categories

        Args:
            tile_map: The TileMap to place resources on.
            enforce_zones: If True, apply progression zone restrictions.
                Set to False for seasonal re-placement to allow resources
                anywhere in valid biomes.
            allow_overwrite: If True, allow placing seasonal resources on tiles
                that already have a resource (used for seasonal re-placement
                to add winter/summer resources to already-occupied tiles).
        """
        self._resource_cache = ResourcePlacer._load_resource_definitions()
        self._available_resources = self._precompute_available()

        # Precompute spawn distances for progression zones (if enforcing)
        if enforce_zones:
            spawn_x, spawn_y = tile_map.spawn_x, tile_map.spawn_y
            self._tile_distances = {}
            for x in range(tile_map.width):
                for y in range(tile_map.height):
                    dx, dy = x - spawn_x, y - spawn_y
                    self._tile_distances[(x, y)] = math.sqrt(dx * dx + dy * dy)
        else:
            self._tile_distances = {}

        # Track which tiles have been assigned (for vein placement)
        self._assigned_tiles: set[tuple[int, int]] = set()

        for x in range(tile_map.width):
            for y in range(tile_map.height):
                if (x, y) in self._assigned_tiles:
                    continue

                tile = tile_map.tiles[x][y]
                biome_id = tile.biome.id
                if not tile.biome.resource_spawns:
                    continue

                zone = self._get_zone(self._tile_distances.get((x, y), 0)) if enforce_zones else 0

                for resource_id in tile.biome.resource_spawns:
                    if resource_id not in self._available_resources:
                        continue

                    resource = self._resource_cache.get(resource_id)
                    if resource is None:
                        continue

                    # Check if we can place here
                    can_place = tile.resource_node is None
                    if not can_place and allow_overwrite:
                        # Allow overwrite if existing resource is not the same
                        # and the new resource is seasonal (has seasons_available)
                        existing = tile.resource_node
                        if existing.resource_id != resource_id and resource.seasons_available:
                            can_place = True

                    if not can_place:
                        continue

                    # Check progression zone gating (only on initial generation)
                    if enforce_zones:
                        max_zone = self.RARITY_MAX_ZONE.get(resource.rarity, 3)
                        if max_zone < zone:
                            continue  # Too rare for this zone

                    adjusted_density = self._compute_density(
                        resource, tile, biome_id, tile_map, zone
                    )
                    if adjusted_density <= 0:
                        continue

                    if self.rng.random() < adjusted_density:
                        # Check if this resource should form a vein
                        if resource.category in self.VEIN_CATEGORIES:
                            if self._try_place_vein(resource, tile, tile_map, biome_id, zone):
                                continue

                        # Single-tile placement
                        tile.resource_node = replace(resource)
                        self._assigned_tiles.add((x, y))

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