"""actions.active_action — ActiveAction dataclass for tracking running actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from actions.types import ActionState

if TYPE_CHECKING:
    from world.resource_node import ResourceNode


@dataclass
class ActiveAction:
    """
    Tracks the currently running action on the player.

    Fields:
        action_type: What kind of action (woodcutting/mining/cooking)
        state: IDLE, RUNNING
        duration: Total time the action takes (seconds)
        elapsed: Time spent so far
        resource: The resource node being interacted with (None for cooking)
        recipe_id: The recipe being cooked (None for woodcutting/mining)
        stamina_cost: Stamina consumed per action tick
        xp_reward: XP granted on success
        yield_item: Item produced on success
        yield_quantity: How many items produced
        success_rate_bonus: Bonus from skill sub-stat (percentage points)
        extra_resources_bonus: Bonus from skill sub-stat (extra roll chance)
        required_tool: Tool type needed ("axe", "pickaxe", or None)
        cooldown: Cooldown after failure (seconds)
    """
    action_type: "ActionType"
    state: ActionState = ActionState.IDLE
    duration: float = 0.0
    elapsed: float = 0.0
    resource: Optional[ResourceNode] = None
    recipe_id: Optional[str] = None
    stamina_cost: float = 3.0
    xp_reward: float = 0.0
    yield_item: str = ""
    yield_quantity: int = 1
    success_rate_bonus: float = 0.0
    extra_resources_bonus: float = 0.0
    required_tool: Optional[str] = None
    cooldown: float = 0.0

    @property
    def progress(self) -> float:
        """Action progress as 0.0–1.0 ratio."""
        if self.duration <= 0:
            return 0.0
        return min(1.0, self.elapsed / self.duration)

    @property
    def is_busy(self) -> bool:
        """True while the player cannot perform other actions."""
        return self.state == ActionState.RUNNING
