"""
fire_entity.py — FireEntity dataclass.

Moved from skills/firemaking.py as part of skill package reorganization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class FireEntity:
    """
    An active fire entity on the map.

    Fields:
        fire_id: Unique identifier.
        world_x: X position in world space.
        world_y: Y position in world space.
        fuel_items: Remaining fuel — [(item_id, quantity)].
        burn_duration_total: Total planned burn time in seconds.
        burn_duration_remaining: Seconds of burn time left.
        radius_tiles: Radius in tiles this fire illuminates/warms.
        heat_output: Heat intensity multiplier.
        is_active: Whether the fire is still burning.
        sprite_key: Sprite reference for rendering.
    """

    fire_id: str
    world_x: float
    world_y: float
    fuel_items: List[Tuple[str, int]]
    burn_duration_total: float
    burn_duration_remaining: float
    radius_tiles: float
    heat_output: float
    is_active: bool = True
    sprite_key: str = "campfire_fire"
