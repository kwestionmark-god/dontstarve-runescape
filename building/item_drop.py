"""
item_drop.py — Ground item drop entities.

Represents items dropped on the ground that can be picked up by the player.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


@dataclass(slots=True)
class ItemDrop:
    """
    An item dropped on the ground.

    Fields:
        item_id: The item identifier.
        quantity: Number of items in this drop.
        world_x: X position in world pixels.
        world_y: Y position in world pixels.
        lifetime: Time until despawn (seconds). None = no despawn.
        created_at: Timestamp for lifetime tracking.
    """
    item_id: str
    quantity: int
    world_x: float
    world_y: float
    lifetime: float | None = 300.0  # 5 minutes default
    created_at: float = 0.0  # Set when added to the world

    def tick(self, dt: float) -> bool:
        """
        Update the item drop lifetime.

        Args:
            dt: Delta time in seconds.

        Returns:
            True if the drop should be removed (expired), False otherwise.
        """
        if self.lifetime is None:
            return False
        self.lifetime -= dt
        return self.lifetime <= 0

    def is_pickupable_by(self, player_x: float, player_y: float, radius: float = 64.0) -> bool:
        """
        Check if the player is close enough to pick up this drop.

        Args:
            player_x: Player's X position.
            player_y: Player's Y position.
            radius: Pickup radius in pixels (default 1 tile).

        Returns:
            True if within pickup range.
        """
        dx = self.world_x - player_x
        dy = self.world_y - player_y
        return dx * dx + dy * dy <= radius * radius