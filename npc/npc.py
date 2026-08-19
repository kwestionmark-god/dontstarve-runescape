"""
npc/npc.py — NPC data classes.

Contains NPC and NPCSpawnPoint dataclasses with factory methods for loading
from npcs.json. These dataclasses represent NPC entities and their spawn
locations on the world map.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class NPC:
    """
    NPC entity with stats, position, and behavioral state.

    Fields:
        npc_id: Unique identifier (e.g. "merchant_forest_1").
        name: Display name (e.g. "Old Man Hemlock").
        npc_type: Role type — "merchant", "quest_giver", "faction_leader", "recruit".
        world_x: Current world X position in pixels.
        world_y: Current world Y position in pixels.
        sprite_key: Sprite sheet reference key.
        faction: Faction ID this NPC belongs to, or None.
        dialogue_lines: Default dialogue options list.
        behavior: Current behavior state — "idle", "patrol", "trade", "guard", "assist".
        patrol_area: Bounding box (min_x, min_y, max_x, max_y) or None.
        is_active: Whether this NPC is operational.
        is_recruited: Whether recruited by the player.
        recruit_behavior: Assigned behavior if recruited — "guard", "trader", "assistant", or None.
        hostility_level: 0.0 (friendly) to 1.0 (hostile).
        health: Current HP.
        max_health: Maximum HP.
    """

    npc_id: str
    name: str
    npc_type: str = ""
    world_x: float = 0.0
    world_y: float = 0.0
    sprite_key: str = ""
    faction: Optional[str] = None
    dialogue_lines: List[str] = field(default_factory=list)
    behavior: str = "idle"
    patrol_area: Optional[Tuple[float, float, float, float]] = None
    is_active: bool = True
    is_recruited: bool = False
    recruit_behavior: Optional[str] = None
    hostility_level: float = 0.0
    health: float = 0.0
    max_health: float = 0.0
    assigned_structure_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPC":
        """
        Create an NPC from a JSON dict (from npcs.json).

        Handles type-specific fields by ignoring unknown keys.
        Maps patrol_area list → tuple.
        Maps faction null → None.

        Args:
            data: Parsed JSON dict from npcs.json "npcs" array.

        Returns:
            Fully initialized NPC instance.
        """
        patrol = data.get("patrol_area")
        if patrol is not None:
            patrol = tuple(patrol)

        return cls(
            npc_id=data["npc_id"],
            name=data["name"],
            npc_type=data["npc_type"],
            world_x=float(data.get("world_x", 0)),
            world_y=float(data.get("world_y", 0)),
            sprite_key=data.get("sprite_key", ""),
            faction=data.get("faction"),  # null → None
            dialogue_lines=data.get("dialogue_lines", []),
            behavior=data.get("behavior", "idle"),
            patrol_area=patrol,
            is_active=data.get("is_active", True),
            is_recruited=data.get("is_recruited", False),
            recruit_behavior=data.get("recruit_behavior"),
            hostility_level=float(data.get("hostility_level", 0.0)),
            health=float(data.get("health", 0)),
            max_health=float(data.get("max_health", 0)),
        )

    def get_npc_attack(self) -> int:
        """Calculate NPC combat attack from hostility_level.

        attack = 3 + int(hostility_level * 10).
        """
        return 3 + int(self.hostility_level * 10)

    def get_npc_defence(self) -> int:
        """Calculate NPC combat defence from hostility_level.

        defence = 1 + int(hostility_level * 5).
        """
        return 1 + int(self.hostility_level * 5)


@dataclass
class NPCSpawnPoint:
    """
    A predefined location where NPCs can spawn.

    Fields:
        spawn_id: Unique identifier (e.g. "spawn_forest_1").
        tile_x: Tile X coordinate for spawn location.
        tile_y: Tile Y coordinate for spawn location.
        npc_types: List of NPC types allowed at this spawn point.
        faction: Faction ID for NPCs spawned here, or None.
        biome: Biome ID for this spawn point.
        is_safe_zone: Whether this is a safe zone (no hostile monsters nearby).
        min_distance_from_player: Minimum distance from player (in pixels).
    """

    spawn_id: str
    tile_x: int = 0
    tile_y: int = 0
    npc_types: List[str] = field(default_factory=list)
    faction: Optional[str] = None
    biome: str = ""
    is_safe_zone: bool = False
    min_distance_from_player: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPCSpawnPoint":
        """
        Create an NPCSpawnPoint from a JSON dict (from npcs.json).

        Args:
            data: Parsed JSON dict from npcs.json "spawn_points" array.

        Returns:
            Fully initialized NPCSpawnPoint instance.
        """
        return cls(
            spawn_id=data["spawn_id"],
            tile_x=int(data["tile_x"]),
            tile_y=int(data["tile_y"]),
            npc_types=data.get("npc_types", []),
            faction=data.get("faction"),
            biome=data.get("biome", ""),
            is_safe_zone=data.get("is_safe_zone", False),
            min_distance_from_player=float(data.get("min_distance_from_player", 0)),
        )
