"""
interactions/interact.py — Player interaction with resources.

Extracted from Game._handle_interact. Handles the E-key resource-gather
flow only; NPC panel routing lives in interactions/npc_flows.py (NPCFlows).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from actions import ActionState, ActionType
from core.state import GameState

if TYPE_CHECKING:
    from core.game import Game


class InteractSystem:
    """Handles the E-key resource-gather (handle_interact) flow only."""

    def __init__(self, game: "Game") -> None:
        self._game = game

    def handle_interact(self) -> None:
        """Handle E key interact: find nearest resource and start action."""
        game = self._game
        if (
            game.player is None
            or game.world is None
            or game.inventory is None
            or game.skill_manager is None
        ):
            return

        action_sys = game.player.action_system
        if action_sys is None:
            return

        # If already performing an action, check if it's cooking (recipe-based)
        if action_sys.active.state == ActionState.RUNNING:
            return  # Already busy

        # Find nearest interactable resource
        node, tx, ty, node_x, node_y = game.player.find_interactable_resource(
            game.world, radius=128.0,
        )

        if node is not None:
            # Determine action type based on resource tool requirement
            if node.requires_tool == "axe":
                action_type = ActionType.WOODCUTTING
            elif node.requires_tool == "pickaxe":
                action_type = ActionType.MINING
            else:
                # No tool requirement — forage (berries, herbs, etc.)
                # Map to woodcutting XP for Phase 1
                action_type = ActionType.WOODCUTTING

            # Delegate action construction to ActionSystem
            error = action_sys.start_action(
                action_type, node, game.skill_manager, game.inventory,
            )
            if error:
                action_sys.add_notification(error, game.ERROR_COLOR)

