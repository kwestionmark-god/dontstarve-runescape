"""Utility functions for structure-based gameplay."""

from __future__ import annotations

import math

from config import TILE_SIZE

STATION_INTERACTION_RADIUS = 3  # tiles


def find_nearby_structures(
    structures,
    player_world_x: float,
    player_world_y: float,
    target_ids: list[str] | None = None,
    radius: int | None = None,
) -> list:
    """
    Find placed structures near the player.

    Args:
        structures: list of Structure instances from building_system.get_all_structures().
        player_world_x: player's world X position in pixels.
        player_world_y: player's world Y position in pixels.
        target_ids: optional list of structure_ids to filter by.
        radius: optional radius in tiles (default: STATION_INTERACTION_RADIUS).

    Returns:
        list of matching Structure instances within range.
    """
    if not structures:
        return []

    if radius is None:
        radius = STATION_INTERACTION_RADIUS

    radius_px = radius * TILE_SIZE
    nearby: list = []

    for struct in structures:
        dist = math.sqrt(
            (struct.world_x - player_world_x) ** 2
            + (struct.world_y - player_world_y) ** 2
        )
        if dist <= radius_px:
            if target_ids is None or struct.structure_def.structure_id in target_ids:
                nearby.append(struct)

    return nearby


def is_structure_nearby(
    structures,
    player_world_x: float,
    player_world_y: float,
    target_id: str,
    radius: int | None = None,
) -> bool:
    """
    Check if a specific structure type is near the player.

    Args:
        structures: list of Structure instances.
        player_world_x: player's world X position in pixels.
        player_world_y: player's world Y position in pixels.
        target_id: structure_id to check proximity for.
        radius: optional radius in tiles.

    Returns:
        True if at least one matching structure is within range.
    """
    return len(find_nearby_structures(structures, player_world_x, player_world_y, [target_id], radius)) > 0
