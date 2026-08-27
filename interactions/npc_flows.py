"""
interactions/npc_flows.py — NPC panel open/close/execute flows.

Contains all logic for opening trade/quest/recruit/diplomacy panels,
executing their actions, and handling keyboard confirmations.
Extracted from input/router.py and input/panel_dispatcher.py (Phase 3.5.5).
"""

from __future__ import annotations

from core.state import GameState
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.game import Game
    from npc.npc_types import RecruitNPC, FactionLeaderNPC


class NPCFlows:
    """Handles NPC panel open/close/execute flows."""

    def __init__(self, game: "Game") -> None:
        """
        Args:
            game: The Game instance providing all subsystem references.
        """
        self._game = game

    # ── Panel open methods (migrated from router.py) ──────────────────

    def open_trade_panel(self, merchant) -> None:
        """Open the trade panel with the given merchant."""
        if self._game._trade_panel is None or self._game.player is None:
            return

        self._game._trade_panel._player_ref = self._game.player
        opened = self._game._trade_panel.open_session(merchant)
        if opened:
            self._game.state = GameState.TRADE_PANEL
        else:
            if self._game.player.action_system is not None:
                self._game.player.action_system.add_notification(
                    "Cannot trade right now.", (255, 150, 100)
                )

    def open_quest_panel(self, npc) -> None:
        """Open the quest panel scoped to the given NPC."""
        if self._game._quest_panel is None or self._game.player is None:
            return
        self._game._quest_panel.set_player(self._game.player)
        opened = self._game._quest_panel.open_session(npc)
        if opened:
            self._game.state = GameState.QUEST_PANEL
        else:
            if self._game.player is not None and self._game.player.action_system is not None:
                self._game.player.action_system.add_notification(
                    f"{npc.name} has no quests available right now.",
                    (180, 150, 60),
                )

    def open_recruit_panel(self, npc) -> bool:
        """Open the recruit panel for the given NPC."""
        from npc.npc_types import RecruitNPC

        if self._game._recruit_panel is None or self._game.player is None:
            return False
        if not isinstance(npc, RecruitNPC):
            return False
        if not self._game._recruit_panel.open_session(npc):
            if self._game.player.action_system is not None:
                self._game.player.action_system.add_notification(
                    f"Cannot recruit {npc.name}.", self._game.ERROR_COLOR
                )
            return False
        self._game._recruit_panel.visible = True
        self._game._recruit_panel._player_ref = self._game.player
        if self._game.player.action_system is not None:
            self._game.player.action_system.add_notification(
                f"Recruitment: {npc.name} -- Press ESC to close",
                (100, 180, 100),
            )
        self._game.set_state(GameState.RECRUIT_PANEL)
        return True

    def open_diplomacy_panel(self, npc) -> bool:
        """Open the diplomacy panel for the given NPC."""
        from npc.npc_types import FactionLeaderNPC

        if self._game._diplomacy_panel is None or self._game.player is None:
            return False
        if not isinstance(npc, FactionLeaderNPC):
            return False
        if not self._game._diplomacy_panel.open_session(npc):
            if self._game.player.action_system is not None:
                self._game.player.action_system.add_notification(
                    f"Cannot access diplomacy for {npc.name}.", self._game.ERROR_COLOR
                )
            return False
        self._game._diplomacy_panel.visible = True
        self._game._diplomacy_panel._player_ref = self._game.player
        if self._game.player.action_system is not None:
            self._game.player.action_system.add_notification(
                f"Diplomacy: {npc.name} -- Press ESC to close",
                (100, 180, 100),
            )
        self._game.set_state(GameState.DIPLOMACY_PANEL)
        return True

    # ── Action handlers (migrated from panel_dispatcher.py) ───────────

    def handle_trade_action(self, action: tuple) -> None:
        """
        Route a trade action to the appropriate TradeSystem method.

        Args:
            action: Tuple of (action_type, ...params).
        """
        game = self._game

        if action[0] == "close":
            game._trade_panel.close_session()
            game._trade_panel.visible = False
            game.state = GameState.PLAYING
            return

        if game.player is None or game.player.action_system is None:
            return

        if action[0] == "buy":
            _, trade_item_id, quantity = action
            result = game.trade_system.execute_buy(trade_item_id, quantity)
            color = (100, 255, 100) if result.success else (255, 100, 100)
            game.player.action_system.add_notification(result.message, color)

        elif action[0] == "sell":
            _, item_id, quantity = action
            result = game.trade_system.execute_sell(item_id, quantity)
            color = (100, 255, 100) if result.success else (255, 100, 100)
            game.player.action_system.add_notification(result.message, color)

        elif action[0] == "barter":
            _, player_item_id, player_qty, merchant_trade_item_id = action
            result = game.trade_system.execute_barter(player_item_id, player_qty, merchant_trade_item_id)
            color = (100, 255, 100) if result.success else (255, 100, 100)
            game.player.action_system.add_notification(result.message, color)

    def handle_quest_action(self, action: tuple[str, ...]) -> None:
        """Process quest panel action tuples."""
        game = self._game

        if action[0] == "close":
            if game._quest_panel is not None:
                game._quest_panel.close_session()
            game.set_state(GameState.PLAYING)
            return

        if action[0] == "accept_quest" and len(action) >= 2:
            quest_id = action[1]
            if game.quest_system is not None and game.player is not None:
                if game.npc_system is not None:
                    nearby = game.npc_system.check_proximity(game.player)
                    if nearby is not None:
                        # Type validation: ensure NPC is a QuestGiverNPC
                        npc_type = getattr(nearby, "npc_type", "")
                        if npc_type != "quest_giver":
                            if game.player is not None:
                                action_sys = game.player.action_system
                                if action_sys is not None:
                                    action_sys.add_notification(
                                        "This NPC cannot offer quests.",
                                        (180, 100, 100),
                                    )
                            game.set_state(GameState.PLAYING)
                            return

                        # Verify the quest is actually offered by this NPC
                        if hasattr(nearby, "available_quests") and quest_id not in nearby.available_quests:
                            if game.player is not None:
                                action_sys = game.player.action_system
                                if action_sys is not None:
                                    action_sys.add_notification(
                                        f"{nearby.name} does not offer this quest.",
                                        (180, 100, 100),
                                    )
                            game.set_state(GameState.PLAYING)
                            return

                        result = game.quest_system.accept_quest(game.player, nearby, quest_id)
                        if game.player is not None:
                            action_sys = game.player.action_system
                            if action_sys is not None:
                                if result.success:
                                    action_sys.add_notification(result.message, (100, 255, 100))
                                else:
                                    action_sys.add_notification(result.message, (180, 100, 100))
                        game.set_state(GameState.PLAYING)
                    else:
                        if game.player is not None:
                            action_sys = game.player.action_system
                            if action_sys is not None:
                                action_sys.add_notification("No quest giver nearby.", (180, 100, 100))
                        game.set_state(GameState.PLAYING)

    def handle_recruit_action(self, action) -> None:
        """Handle recruit panel action tuples."""
        game = self._game

        if action[0] == "recruit" and len(action) >= 3:
            npc_id = action[1]
            behavior = action[2]
            structure_id = action[3] if len(action) >= 4 else None
            self._execute_recruitment(npc_id, behavior, structure_id)
        elif action[0] in ("cancel", "close"):
            if action[0] == "cancel" and len(action) >= 2:
                npc_id = action[1]
                self._execute_dismissal(npc_id)
            self._close_recruit_panel()

    def handle_diplomacy_action(self, action) -> None:
        """Handle diplomacy panel action tuples (single canonical path)."""
        game = self._game

        if action[0] == "negotiate":
            self.execute_negotiation()
        elif action[0] in ("cancel", "close"):
            self._close_diplomacy_panel()

    # ── Execute methods (migrated from panel_dispatcher.py) ───────────

    def execute_recruitment(self, npc_id, behavior, structure_id=None) -> None:
        """Execute recruitment of an NPC."""
        game = self._game

        target_npc = None
        if game.npc_system is not None:
            for npc in game.npc_system.npcs:
                if npc.npc_id == npc_id:
                    target_npc = npc
                    break
        if target_npc is None:
            if game.player and game.player.action_system:
                game.player.action_system.add_notification(f"NPC '{npc_id}' not found.", game.ERROR_COLOR)
            self._close_recruit_panel()
            return
        target_npc.is_recruited = True
        target_npc.recruit_behavior = behavior
        target_npc.assign_behavior(behavior)  # Initialize HP for guards
        game.player.add_recruit(npc_id)
        # Wire into RecruitmentSystem
        if game.recruitment_system is not None:
            game.recruitment_system.on_recruit(npc_id, behavior)
        # Assign guard to structure if a structure_id is provided
        if structure_id and game.npc_system is not None:
            result_msg = game.npc_system.assign_npc_to_structure(npc_id, structure_id)
            if result_msg[0]:
                game.player.action_system.add_notification(result_msg[1], (100, 255, 100))
            else:
                game.player.action_system.add_notification(result_msg[1], (255, 150, 100))
        game.player.action_system.add_notification(f"You recruited {target_npc.name} as {behavior}!", (100, 255, 100))
        self._close_recruit_panel()

    def execute_dismissal(self, npc_id) -> None:
        """Dismiss a recruited NPC and clean up recruitment state."""
        game = self._game

        if game.player is None or game.npc_system is None:
            return

        target_npc = None
        for npc in game.npc_system.npcs:
            if npc.npc_id == npc_id:
                target_npc = npc
                break
        if target_npc is None:
            return

        target_npc.is_recruited = False
        target_npc.recruit_behavior = None
        game.player.remove_recruit(npc_id)
        if game.recruitment_system is not None:
            game.recruitment_system.on_dismiss(npc_id)
        if game.player.action_system:
            game.player.action_system.add_notification(
                f"You dismissed {target_npc.name}.", (255, 200, 100),
            )

    def execute_negotiation(self) -> None:
        """
        Canonical faction negotiation — one path for both keyboard and mouse.

        Applies the risked relationship delta (``faction_system.negotiate``)
        and records quest progress (``quest_system.record_negotiation``). This
        replaces the former double-fire, where a single Enter/Space triggered
        both ``handle_faction_negotiate_keyboard`` and ``execute_negotiation``
        (and where the mouse "Negotiate" button referenced a nonexistent
        ``_execute_negotiation``).
        """
        game = self._game

        if game.player is None or game.player.action_system is None:
            return
        if game._diplomacy_panel is None or game._diplomacy_panel._faction_info is None:
            return
        faction_id = game._diplomacy_panel._faction_info.faction_id
        if game.faction_system is not None and game.player is not None:
            result = game.faction_system.negotiate(game.player, faction_id)
            if game.player.action_system is not None:
                game.player.action_system.add_notification(
                    result.get("message", "Negotiation attempted."),
                    (100, 255, 100) if result.get("success") else (180, 100, 100),
                )
        if game.quest_system is not None:
            game.quest_system.record_negotiation(faction_id)
        self.close_diplomacy_panel()

    # ── Close methods (migrated from panel_dispatcher.py) ─────────────

    def close_recruit_panel(self) -> None:
        """Close the recruit panel and return to PLAYING."""
        game = self._game
        if game._recruit_panel is not None:
            game._recruit_panel.close_session()
        game.set_state(GameState.PLAYING)

    def close_diplomacy_panel(self) -> None:
        """Close the diplomacy panel and return to PLAYING."""
        game = self._game
        if game._diplomacy_panel is not None:
            game._diplomacy_panel.close_session()
        game.set_state(GameState.PLAYING)

    # ── Keyboard confirm handlers (migrated from panel_dispatcher.py) ─

    def handle_trade_accept_keyboard(self) -> None:
        """Handle Enter/Space in trade panel: execute current buy/sell/barter selection."""
        game = self._game

        if game._trade_panel is None or game._trade_panel._trade_session is None:
            return

        tab = game._trade_panel._tab
        player = game.player

        if tab == "buy" and game._trade_panel._selected_merchant_idx >= 0:
            items = game._trade_panel.trade_system.get_trade_items_for_merchant(
                game._trade_panel._trade_session,
            )
            if 0 <= game._trade_panel._selected_merchant_idx < len(items):
                item = items[game._trade_panel._selected_merchant_idx]
                result = game.trade_system.execute_buy(
                    item.trade_item_id, game._trade_panel._buy_quantity,
                )
                if player and player.action_system:
                    player.action_system.add_notification(
                        result.message,
                        (100, 255, 100) if result.success else (255, 100, 100),
                    )

        elif tab == "sell" and game._trade_panel._selected_player_idx >= 0:
            sellable_items = game._trade_panel._collect_sellable_items()
            if 0 <= game._trade_panel._selected_player_idx < len(sellable_items):
                _, item_id, quantity, sell_price = sellable_items[
                    game._trade_panel._selected_player_idx
                ]
                result = game.trade_system.execute_sell(
                    item_id, game._trade_panel._sell_quantity,
                )
                if player and player.action_system:
                    player.action_system.add_notification(
                        result.message,
                        (100, 255, 100) if result.success else (255, 100, 100),
                    )

        elif tab == "barter":
            sellable_items = game._trade_panel._collect_sellable_items()
            if (
                game._trade_panel._selected_player_idx is not None
                and 0 <= game._trade_panel._selected_player_idx < len(sellable_items)
            ):
                _, player_item_id, player_qty, _ = sellable_items[
                    game._trade_panel._selected_player_idx
                ]
                if (
                    game._trade_panel._selected_merchant_idx is not None
                    and game._trade_panel._trade_session is not None
                ):
                    items = game._trade_panel.trade_system.get_trade_items_for_merchant(
                        game._trade_panel._trade_session,
                    )
                    if 0 <= game._trade_panel._selected_merchant_idx < len(items):
                        merchant_item = items[game._trade_panel._selected_merchant_idx]
                        result = game.trade_system.execute_barter(
                            player_item_id, 1, merchant_item.trade_item_id,
                        )
                        if player and player.action_system:
                            player.action_system.add_notification(
                                result.message,
                                (100, 255, 100) if result.success else (255, 100, 100),
                            )

        # Close trade panel after any keyboard trade action
        if game._trade_panel is not None:
            game._trade_panel.visible = False
            game.set_state(GameState.PLAYING)

    def handle_quest_accept_keyboard(self) -> None:
        """Handle Enter/Space in quest panel: accept the selected quest."""
        game = self._game

        if game._quest_panel is None or game._quest_panel._selected_quest_id is None:
            return

        quest_id = game._quest_panel._selected_quest_id
        player = game.player

        if game.quest_system is not None and player is not None:
            if game.npc_system is not None:
                nearby = game.npc_system.check_proximity(player)
                if nearby is not None:
                    npc_type = getattr(nearby, "npc_type", "")
                    if npc_type != "quest_giver":
                        if player.action_system:
                            player.action_system.add_notification(
                                "This NPC cannot offer quests.", (180, 100, 100),
                            )
                        return

                    if (
                        hasattr(nearby, "available_quests")
                        and quest_id not in nearby.available_quests
                    ):
                        if player.action_system:
                            player.action_system.add_notification(
                                f"{nearby.name} does not offer this quest.",
                                (180, 100, 100),
                            )
                        return

                    result = game.quest_system.accept_quest(player, nearby, quest_id)
                    if player.action_system:
                        player.action_system.add_notification(
                            result.message,
                            (100, 255, 100) if result.success else (180, 100, 100),
                        )
                else:
                    if player.action_system:
                        player.action_system.add_notification(
                            "No NPC found near you to offer this quest.", (200, 150, 100),
                        )

        # Close quest panel after keyboard accept
        if game._quest_panel is not None:
            game._quest_panel.visible = False
            game.set_state(GameState.PLAYING)
