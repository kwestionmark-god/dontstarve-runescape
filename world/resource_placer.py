"""
resource_placer.py — Resource placement engine.

Encapsulates the logic for placing resource nodes on the tile map:
  - Loading resource definitions from resources.json
  - Precomputing season-filtered resource lists
  - Density-based random placement with tier scaling
  - Seasonal availability gating (both static and runtime)
  - Clustering bonus for same-biome resources

The ResourcePlacer is created once per world generation with a seed and
optional SeasonSystem, then used to place all resources on the map.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from world.resource_node import ResourceNode

if TYPE_CHECKING:
    from seasons.season_system import SeasonSystem
    from world.tile_map import TileMap


@dataclass
class ResourcePlacer:
    """
    Places resource nodes on a TileMap using density-based random placement.

    Fields:
        rng: Random instance seeded for deterministic placement.
        season_system: Optional SeasonSystem for seasonal gating.
        _resource_cache: Per-instance lookup of resource_id → ResourceNode
            (reloaded fresh each place()).
        _available_resources: Precomputed set of resource IDs available this season.
    """

    rng: random.Random
    season_system: object | None = None

    # Per-instance resource lookup (reloaded fresh each place()).
    _resource_cache: dict[str, ResourceNode] = field(default_factory=dict, repr=False)
    _available_resources: set[str] = field(default_factory=set, repr=False)

    # Clustering bonus: same-biome adjacent resources get a slight density boost
    CLUSTER_BONUS = 0.02

 
    def place(self, tile_map: TileMap) -> None:
        """
        Place all resource nodes on the tile map.

        Precomputes the set of seasonally-available resources, then iterates
        every tile and attempts placement for each resource in that tile's
        biome spawn list.

        Args:
            tile_map: The TileMap to place resources on.
        """
        self._resource_cache = ResourcePlacer._load_resource_definitions()
        self._available_resources = self._precompute_available()

        for x in range(tile_map.width):
            for y in range(tile_map.height):
                tile = tile_map.tiles[x][y]
                biome_id = tile.biome.id
                if not tile.biome.resource_spawns:
                    continue

                for resource_id in tile.biome.resource_spawns:
                    if resource_id not in self._available_resources:
                        continue

                    resource = self._resource_cache.get(resource_id)
                    if resource is None:
                        continue

                    if tile.resource_node is not None:
                        continue

                    adjusted_density = self._compute_density(resource, tile, biome_id, tile_map)
                    if adjusted_density <= 0:
                        continue

                    if self.rng.random() < adjusted_density:
                        tile.resource_node = resource

    def _precompute_available(self) -> set[str]:
        """
        Build the set of resource IDs available in the current season.

        A resource is available if:
          1. It has no seasons_available gate, OR
          2. Its seasons_available includes the current season, AND
          3. The runtime availability dict (if any) permits it.

        Returns:
            Set of resource IDs available this season.
        """
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

    def _get_clustering_bonus(
        self, tile: object, resource_id: str, tile_map: "TileMap",
    ) -> float:
        """
        Return a small density bonus if an adjacent tile has the same resource.

        This creates natural resource clusters rather than purely random scatter.

        Args:
            tile: The tile being evaluated.
            resource_id: The resource ID to check neighbors for.
            tile_map: The TileMap for neighbor lookups.

        Returns:
            Bonus density (0.0 or CLUSTER_BONUS).
        """
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        for dx, dy in directions:
            neighbor = tile_map.get_tile(tile.x + dx, tile.y + dy)
            if neighbor is not None and neighbor.resource_node is not None:
                if neighbor.resource_node.resource_id == resource_id:
                    return self.CLUSTER_BONUS
        return 0.0

    def _compute_density(
        self, resource: ResourceNode, tile: object, biome_id: str, tile_map: "TileMap",
    ) -> float:
        """
        Compute the effective placement density for a resource on a tile.

        Density = base effective_density × seasonal_multiplier × clustering_bonus

        Args:
            resource: The ResourceNode being considered.
            tile: The Tile being considered for placement.
            biome_id: The biome ID of the tile.
            tile_map: The TileMap for neighbor lookups.

        Returns:
            Adjusted density (0.0–1.0+).
        """
        density = resource.effective_density

        # Seasonal multiplier
        if self.season_system is not None:
            try:
                density *= self.season_system.get_resource_multiplier(resource.category)
            except Exception:
                pass

        # Clustering bonus: if an adjacent tile already has this same resource,
        # add a small density boost to encourage natural clusters.
        density += self._get_clustering_bonus(tile, resource.resource_id, tile_map)

        return density

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



