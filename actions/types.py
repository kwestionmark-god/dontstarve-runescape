"""actions.types — Action type and state enums."""

from enum import Enum, auto


class ActionType(Enum):
    """Types of resource interaction actions."""
    WOODCUTTING = auto()
    MINING = auto()
    COOKING = auto()

    @staticmethod
    def get_skill_id(
        action_type: "ActionType", resource=None,
    ) -> str:
        """
        Map an ActionType + resource to a skill ID string.

        Args:
            action_type: The ActionType enum value.
            resource: Optional ResourceNode (used to disambiguate
                WOODCUTTING vs MINING when the action type alone
                is insufficient).

        Returns:
            Skill ID string: "woodcutting", "mining", etc.
        """
        if action_type == ActionType.WOODCUTTING:
            return "woodcutting"
        if action_type == ActionType.MINING:
            return "mining"
        if action_type == ActionType.COOKING:
            return "cooking"
        raise ValueError(f"Unknown ActionType: {action_type}")


class ActionState(Enum):
    """Lifecycle of a single action."""
    IDLE = auto()
    RUNNING = auto()
