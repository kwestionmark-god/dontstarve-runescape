"""actions.action_result — ActionResult dataclass for typed action completion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ActionResult:
    """
    Structured result of a completed action.

    Replaces string-protocol messages like "action_complete:item:qty:xp"
    with a typed, self-documenting object.

    Fields:
        success: Whether the action succeeded
        item_id: Item produced (empty string if no item)
        quantity: Quantity produced (0 if no item)
        xp: XP granted
        message: Human-readable feedback message
    """
    success: bool
    item_id: str = ""
    quantity: int = 0
    xp: float = 0.0
    message: str = ""