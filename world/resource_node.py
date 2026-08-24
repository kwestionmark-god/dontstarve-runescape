"""
resource_node.py — Resource node definitions.

Represents a harvestable resource on the map (tree, rock, etc.).
Created from JSON data and placed on tiles during world generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResourceNode:
    """A harvestable resource on a tile."""

    resource_id: str         # "oak_tree", "iron_rock", etc.
    biome: str               # Biome this resource belongs to
    tier: int                # 1–4
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

    # Tier-based density multiplier
    TIER_DENSITY_MULTIPLIER: dict[int, float] = field(
        default_factory=lambda: {1: 1.0, 2: 0.7, 3: 0.4, 4: 0.2},
        repr=False,
    )

    @property
    def effective_density(self) -> float:
        """Density adjusted by tier."""
        return self.base_density * self.TIER_DENSITY_MULTIPLIER.get(self.tier, 1.0)

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
        """How many more harvests are available."""
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
        )
