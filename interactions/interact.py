"""
interactions/interact.py — Player interaction with resources and NPCs.

Extracted from Game._handle_interact, _open_*_panel methods, and
_handle_other_npc_interaction. Handles resource gathering actions,
NPC proximity routing, and panel state transitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from actions import ActionState, ActionType
from core.state import GameState

if TYPE_CHECKING:
    from core.game import Game


class InteractSystem:
    """Handles all player interaction flows: resources, NPCs, panels."""

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

    def open_trade_panel(self, merchant) -> None:
        """Open the trade panel with the given merchant."""
        game = self._game
        if game._trade_panel is None or game.player is None:
            return

        game._trade_panel._player_ref = game.player
        opened = game._trade_panel.open_session(merchant)
        if opened:
            game.state = GameState.TRADE_PANEL
        else:
            if game.player.action_system is not None:
                game.player.action_system.add_notification(
                    "Cannot trade right now.", (255, 150, 100),
                )

    def open_quest_panel(self, npc) -> None:
        """Open the quest panel scoped to the given QuestGiverNPC."""
        game = self._game
        if game._quest_panel is None or game.player is None:
            return
        game._quest_panel.set_player(game.player)
        opened = game._quest_panel.open_session(npc)
        if opened:
            game.state = GameState.QUEST_PANEL
        else:
            if game.player is not None and game.player.action_system is not None:
                game.player.action_system.add_notification(
                    f"{npc.name} has no quests available right now.",
                    (180, 150, 60),
                )

    def _handle_other_npc_interaction(self, npc) -> None:
        """Handle interaction with unknown NPC types."""
        game = self._game
        if game.player is None or game.player.action_system is None:
            return
        npc_type = getattr(npc, "npc_type", "unknown")
        game.player.action_system.add_notification(
            f"{npc.name} ({npc_type}) — No interaction available.",
            (150, 150, 170),
        )

    # ── Recruitment helpers ─────────────────────────────────────────

    def open_recruit_panel(self, npc) -> bool:
        if self._game._recruit_panel is None or self._game.player is None:
            return False
        from npc.npc_types import RecruitNPC
        if not isinstance(npc, RecruitNPC):
            return False
        if not self._game._recruit_panel.open_session(npc):
            if self._game.player.action_system is not None:
                self._game.player.action_system.add_notification(
                    f"Cannot recruit {npc.name}.", self._game.ERROR_COLOR,
                )
            return False
        self._game._recruit_panel.visible = True
        self._game._recruit_panel._player_ref = self._game.player
        if self._game.player.action_system is not None:
            self._game.player.action_system.add_notification(
                f"Recruitment: {npc.name} — Press ESC to close",
                (100, 180, 100),
            )
        self._game.set_state(GameState.RECRUIT_PANEL)
        return True

    def open_diplomacy_panel(self, npc) -> bool:
        if self._game._diplomacy_panel is None or self._game.player is None:
            return False
        from npc.npc_types import FactionLeaderNPC
        if not isinstance(npc, FactionLeaderNPC):
            return False
        if not self._game._diplomacy_panel.open_session(npc):
            if self._game.player.action_system is not None:
                self._game.player.action_system.add_notification(
                    f"Cannot access diplomacy for {npc.name}.",
                    self._game.ERROR_COLOR,
                )
            return False
        # Ensure the panel is marked as visible before changing state
        self._game._diplomacy_panel.visible = True
        self._game._diplomacy_panel._player_ref = self._game.player
        if self._game.player.action_system is not None:
            self._game.player.action_system.add_notification(
                f"Diplomacy: {npc.name} — Press ESC to close",
                (100, 180, 100),
            )
        self._game.set_state(GameState.DIPLOMACY_PANEL)
        return True
