"""
resource_node.py — Resource node definitions.

Represents a harvestable resource on the map (tree, rock, etc.).
Created from JSON data and placed on tiles during world generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import RARITY_DENSITY_RANGE


@dataclass
class ResourceNode:
    """A harvestable resource on a tile."""

    resource_id: str         # "oak_tree", "iron_rock", etc.
    biome: str               # Biome this resource belongs to
    tier: int                # 1–4 (legacy, kept for compatibility)
    rarity: str              # "ubiquitous", "common", "uncommon", "rare", "epic", "legendary"
    category: str            # "wood", "ore", "herb", "water", "stone", "special"
    base_density: float      # Base placement density (from resources.json)
    yield_item: str          # Item produced when harvested
    yield_quantity: int      # Base quantity per harvest (from resources.json)
    xp_reward: float         # XP granted on harvest
    depletion_count: int     # How many times can be harvested before depletion
    current_depletions: int  # Current depletion level (starts at 0)
    regrow_time: float       # Seconds to regrow after depletion
    sprite_key: str          # Sprite sheet reference
    requires_tool: str | None  # Tool required (e.g., "axe", "pickaxe")
    name: str = ""           # Human-readable name (e.g. "Oak Tree")
    seasons_available: list[str] = field(default_factory=list)  # Seasons this resource spawns in; empty = all seasons
    biome_affinity: dict[str, float] = field(default_factory=dict)  # Biome ID -> density multiplier

    @property
    def effective_density(self) -> float:
        """Density clamped to rarity band.

        The base_density from JSON is clamped to the min/max range for this
        resource's rarity tier, ensuring consistent spawn rates regardless of
        arbitrary base_density values.
        """
        min_d, max_d = RARITY_DENSITY_RANGE.get(self.rarity, (0.01, 0.05))
        return max(min_d, min(max_d, self.base_density))

    @property
    def is_depleted(self) -> bool:
        """True if the resource has been harvested to its limit.

        A ``depletion_count`` of 0 or less marks the resource as unending
        (e.g. ``water_source``): it can never be depleted. This honors the
        ``-1 = infinite`` convention that world data uses for water.
        """
        if self.depletion_count <= 0:
            return False
        return self.current_depletions >= self.depletion_count

    @property
    def remaining_depletions(self) -> int:
        """How many more harvests are available.

        Returns a large sentinel (999999) for infinite resources (depletion_count <= 0)
        so callers don't misinterpret '0 remaining' as exhausted.
        """
        if self.depletion_count <= 0:
            return 999999  # Infinite resource
        return max(0, self.depletion_count - self.current_depletions)

    def harvest(self) -> bool:
        """
        Attempt to harvest this resource.

        Returns True if harvest was successful, False if depleted.
        """
        if self.is_depleted:
            return False
        self.current_depletions += 1
        return True

    def start_regrow(self) -> None:
        """Reset harvest state after the regrowth timer completes.

        Restores the node to fully harvestable: zero out depletions so
        ``is_depleted`` becomes False and the mature sprite can be drawn.
        """
        self.current_depletions = 0

    def growth_stage(self, regrow_timer: float) -> str:
        """Return the regrowth stage name for rendering.

        Args:
            regrow_timer: Current remaining regrow timer (seconds).

        Returns:
            One of ``'mature'``, ``'sapling'``, ``'young'``, ``'depleted'``.
            Nodes with no regrow time or already finished return ``'mature'``.
        """
        if self.regrow_time <= 0:
            return "mature"
        progress = 1.0 - (regrow_timer / self.regrow_time)
        if progress < 0.40:
            return "sapling"
        elif progress < 0.80:
            return "young"
        return "mature"

    @staticmethod
    def from_dict(data: dict, biome_id: str) -> "ResourceNode":
        """
        Create a ResourceNode from JSON data.

        Args:
            data: Parsed dict from resources.json.
            biome_id: The biome this resource belongs to.

        Returns:
            A ResourceNode instance with initial depletions set.
        """
        return ResourceNode(
            resource_id=data["id"],
            name=data.get("name", data["id"]),
            biome=biome_id,
            tier=data["tier"],
            rarity=data.get("rarity", "common"),
            category=data.get("category", "special"),
            base_density=data.get("base_density", 0.05),
            yield_item=data["yield_item"],
            yield_quantity=data.get("yield_quantity", 1),
            xp_reward=data["xp_reward"],
            depletion_count=data["depletion_count"],
            current_depletions=0,
            regrow_time=data["regrow_time"],
            sprite_key=data["sprite_key"],
            requires_tool=data.get("requires_tool"),
            seasons_available=data.get("seasons_available", []),
            biome_affinity=data.get("biome_affinity", {}),
        )
