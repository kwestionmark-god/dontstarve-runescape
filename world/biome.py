"""
biome.py — Biome definitions and classification.

Loads biome data from data/biomes.json and provides biome lookup by ID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Tuple

    BiomeColor = Tuple[int, int, int]  # RGB


@dataclass
class Biome:
    """A single biome definition."""

    id: str
    name: str
    mega_cluster: str          # "temperate", "extreme", "dangerous"
    environmental_pressure: float   # Multiplier on survival drain (0.0–1.0+)
    starting_safety: bool      # True if valid spawn area
    elevation_range: Tuple[int, int]
    terrain_colors: dict       # elevation (str) → RGB tuple
    resource_spawns: list      # resource IDs native to this biome

    def get_terrain_color(self, elevation: int) -> BiomeColor:
        """Return the RGB terrain color for a given elevation level."""
        color = self.terrain_colors.get(str(elevation))
        if isinstance(color, (tuple, list)):
            return tuple(color)
        return (128, 128, 128)  # Fallback grey


class BiomeRegistry:
    """Registry of all biomes, loaded from JSON."""

    def __init__(self, biome_data: list[dict]) -> None:
        """
        Initialize from JSON data.

        Args:
            biome_data: Parsed list of biome dicts from biomes.json.
        """
        self._biomes: dict[str, Biome] = {}
        for data in biome_data:
            biome = Biome(
                id=data["id"],
                name=data["name"],
                mega_cluster=data["mega_cluster"],
                environmental_pressure=data["environmental_pressure"],
                starting_safety=data["starting_safety"],
                elevation_range=tuple(data["elevation_range"]),
                terrain_colors=data["terrain_colors"],
                resource_spawns=data["resource_spawns"],
            )
            self._biomes[biome.id] = biome

    def get(self, biome_id: str, default: Biome | None = None) -> Biome | None:
        """Look up a biome by ID, returning default if not found."""
        return self._biomes.get(biome_id, default)

    def all(self) -> list[Biome]:
        """Return all biomes."""
        return list(self._biomes.values())

    def by_mega_cluster(self, cluster: str) -> list[Biome]:
        """Return biomes belonging to a mega-cluster."""
        return [b for b in self._biomes.values() if b.mega_cluster == cluster]
