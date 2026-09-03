from __future__ import annotations

import pygame
from config import TILE_SIZE
from core.state import GameState, PANEL_STATES
from typing import TYPE_CHECKING
from data import load_json_list

if TYPE_CHECKING:
    from core.game import Game
    from input.input_manager import InputManager
    from input.panel_dispatcher import PanelDispatcher


class InputRouter:

    def __init__(
        self,
        game: "Game",
        input_manager: "InputManager",
        panel_dispatcher: "PanelDispatcher",
    ) -> None:
        self._game = game
        self._input_manager = input_manager
        self._panel_dispatcher = panel_dispatcher
        # B15: reuse the shared, single-owned Game._npc_flows (router and
        # panel_dispatcher no longer construct their own NPCFlows).
        self._npc_flows = getattr(game, "_npc_flows", None)
        # Cache items.json and food registry for hotbar handling
        self._items_cache = load_json_list("items.json", "items")
        self._food_registry = getattr(game, "food_registry", None)

    def _ensure_caches(self, game: "Game") -> None:
        """Lazy-initialize caches if not already set (for tests/mocks)."""
        if not hasattr(self, "_items_cache") or self._items_cache is None:
            self._items_cache = load_json_list("items.json", "items")
        if not hasattr(self, "_food_registry") or self._food_registry is None:
            self._food_registry = getattr(game, "food_registry", None)

    def handle(self, event: pygame.event.Event) -> None:
        game = self._game
        input_manager = self._input_manager
        panel_dispatcher = self._panel_dispatcher

        # Forward all events to InputManager for held-key / one-shot state
        if input_manager is not None:
            input_manager.handle_event(event)

        if event.type == pygame.KEYDOWN:
            self._handle_keydown(game, input_manager, panel_dispatcher, event)
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_move(game, event.pos[0], event.pos[1])
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_button_down(game, event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_up(game)
        elif event.type == pygame.MOUSEWHEEL:
            self._handle_wheel(game, event)

    def _handle_keydown(
        self,
        game: "Game",
        input_manager: "InputManager",
        panel_dispatcher: "PanelDispatcher",
        event,
    ) -> None:
        is_state = input_manager.input_state

        # Build mode (a PLAYING sub-state): ESC cancels placement. State stays
        # PLAYING, so the panel toggles below are no-ops here.
        if (
            getattr(game, "build_mode", False)
            and game.state == GameState.PLAYING
            and event.key == pygame.K_ESCAPE
        ):
            self._cancel_build_mode(game)

        # Read InputState flags to actually control panels
        # Only process panel open/close flags when in PLAYING state,
        # or when the flag matches the current panel (for toggling).
        # This prevents TAB from opening skill panel while quest panel is open.
        if game.state in PANEL_STATES:
            # In a panel state, only process the flag for the CURRENT panel (toggle close)
            # Skip all other panel open flags
            current_panel_flag = {
                GameState.INVENTORY_OPEN: 'open_inventory',
                GameState.SKILL_PANEL: 'open_skill_panel',
                GameState.CRAFTING_PANEL: 'open_crafting',
                GameState.BUILDING_PANEL: 'open_building_panel',
                GameState.GEAR_PANEL: 'open_inventory',  # G key, not a flag
                GameState.TRADE_PANEL: 'open_trade_panel',
                GameState.QUEST_PANEL: 'open_quest_panel',
                GameState.RECRUIT_PANEL: 'open_recruit_panel',
                GameState.DIPLOMACY_PANEL: 'open_diplomacy_panel',
            }.get(game.state)
            
            # Clear flags for other panels to prevent interference
            for flag_name in ['open_inventory', 'open_skill_panel', 'open_crafting', 
                              'open_building_panel', 'open_quest_panel', 'open_trade_panel',
                              'open_recruit_panel', 'open_diplomacy_panel']:
                if flag_name != current_panel_flag:
                    setattr(is_state, flag_name, False)
        
        # Now process panel flags (for PLAYING/TITLE, all flags processed;
        # for panel states, only the current panel's flag remains set)
        if is_state.open_inventory:
            is_state.open_inventory = False
            if game.state == GameState.INVENTORY_OPEN:
                game.set_state(GameState.PLAYING)
            else:
                game.set_state(GameState.INVENTORY_OPEN)
        elif is_state.open_skill_panel:
            is_state.open_skill_panel = False
            if game.state == GameState.SKILL_PANEL:
                game.set_state(GameState.PLAYING)
            else:
                game.set_state(GameState.SKILL_PANEL)
        elif is_state.open_crafting:
            is_state.open_crafting = False
            if game.state == GameState.CRAFTING_PANEL:
                game.set_state(GameState.PLAYING)
            elif game.state not in (
                GameState.INVENTORY_OPEN, GameState.SKILL_PANEL
            ):
                game.set_state(GameState.CRAFTING_PANEL)
        elif is_state.open_building_panel:
            is_state.open_building_panel = False
            if game.state == GameState.BUILDING_PANEL:
                game.set_state(GameState.PLAYING)
            else:
                # A fresh selection intent supersedes any active placement.
                if game.build_mode:
                    game.build_mode = False
                    game._building_pending_id = None
                game.set_state(GameState.BUILDING_PANEL)
        elif is_state.open_quest_panel:
            is_state.open_quest_panel = False
            if game.state == GameState.QUEST_PANEL:
                game.set_state(GameState.PLAYING)
            else:
                game.set_state(GameState.QUEST_PANEL)
        elif is_state.open_trade_panel:
            is_state.open_trade_panel = False
            if game.state == GameState.TRADE_PANEL:
                game.set_state(GameState.PLAYING)
            else:
                game.set_state(GameState.TRADE_PANEL)
        elif is_state.open_recruit_panel:
            is_state.open_recruit_panel = False
            if game.state == GameState.RECRUIT_PANEL:
                game.set_state(GameState.PLAYING)
            else:
                game.set_state(GameState.RECRUIT_PANEL)
        elif is_state.open_diplomacy_panel:
            is_state.open_diplomacy_panel = False
            if game.state == GameState.DIPLOMACY_PANEL:
                game.set_state(GameState.PLAYING)
            else:
                game.set_state(GameState.DIPLOMACY_PANEL)

        # Q key: close crafting panel
        if is_state.close_crafting and game.state == GameState.CRAFTING_PANEL:
            is_state.close_crafting = False
            if game._crafting_panel is not None:
                game._crafting_panel.visible = False
            game.set_state(GameState.PLAYING)

        if event.key == pygame.K_g and game.state == GameState.PLAYING:
            if game.state != GameState.GEAR_PANEL:
                game.set_state(GameState.GEAR_PANEL)
            else:
                game.set_state(GameState.PLAYING)
        elif event.key == pygame.K_y and game.state == GameState.PLAYING:
            if game.state != GameState.QUEST_PANEL:
                game.set_state(GameState.QUEST_PANEL)
            else:
                game.set_state(GameState.PLAYING)
        elif event.key == pygame.K_f and game.state == GameState.PLAYING:
            self._handle_light_fire(game)
        elif event.key == pygame.K_j and game.state == GameState.PLAYING:
            self._handle_attack(game)
        elif event.key == pygame.K_ESCAPE:
            if is_state.close_panel and game.state != GameState.PLAYING:
                is_state.close_panel = False
                # Use the unified close() method on the active panel
                panel_map = {
                    GameState.TRADE_PANEL: game._trade_panel,
                    GameState.QUEST_PANEL: game._quest_panel,
                    GameState.RECRUIT_PANEL: game._recruit_panel,
                    GameState.DIPLOMACY_PANEL: game._diplomacy_panel,
                    GameState.INVENTORY_OPEN: game._inventory_panel,
                    GameState.SKILL_PANEL: game._skill_panel,
                    GameState.CRAFTING_PANEL: game._crafting_panel,
                    GameState.BUILDING_PANEL: game._building_panel,
                    GameState.GEAR_PANEL: game._gear_panel,
                }
                panel = panel_map.get(game.state)
                if panel is not None:
                    panel.close()
                game.set_state(GameState.PLAYING)
        elif event.key == pygame.K_F5:
            if game.save_system:
                game.save_system.save(game, slot=0)
            if game.player is not None and game.player.action_system is not None:
                game.player.action_system.add_notification("Game saved (F5).", (100, 255, 100))
        if is_state.hotbar_slot and game.state == GameState.PLAYING:
            slot = is_state.hotbar_slot  # Capture BEFORE clearing the one-shot
            is_state.hotbar_slot = 0
            self._handle_hotbar(game, slot)
        elif event.key == pygame.K_e and game.state == GameState.PLAYING:
            self._handle_e_interact(game)

        if is_state.trade_accept_pressed and game.state == GameState.TRADE_PANEL:
            is_state.trade_accept_pressed = False
            self._npc_flows.handle_trade_accept_keyboard()
            return
        if is_state.quest_accept_pressed and game.state == GameState.QUEST_PANEL:
            is_state.quest_accept_pressed = False
            self._npc_flows.handle_quest_accept_keyboard()
            return

        # Diplomacy negotiate is handled by the panel's unified on_key ->
        # dispatch path below (single canonical negotiate, no double-fire).

        if game.state in PANEL_STATES:
            active_panel = self._get_active_panel(game)
            if active_panel and hasattr(active_panel, 'handle_key'):
                result = active_panel.handle_key(event.key)
                if result is not None:
                    panel_dispatcher.dispatch(game.state, result)

    def _handle_e_interact(self, game: "Game") -> None:
        if game.npc_system is not None and game.player is not None:
            nearby_npc = game.npc_system.check_proximity(game.player)
            if nearby_npc is not None:
                npc_type = getattr(nearby_npc, "npc_type", "")
                if npc_type == "merchant":
                    self._npc_flows.open_trade_panel(nearby_npc)
                elif npc_type == "quest_giver":
                    self._npc_flows.open_quest_panel(nearby_npc)
                elif npc_type == "faction_leader":
                    # Faction leaders with quests open quest panel; others open diplomacy
                    if getattr(nearby_npc, "available_quests", None):
                        self._npc_flows.open_quest_panel(nearby_npc)
                    else:
                        self._npc_flows.open_diplomacy_panel(nearby_npc)
                elif npc_type == "recruit":
                    self._npc_flows.open_recruit_panel(nearby_npc)
                else:
                    self._handle_interact(game)
            else:
                self._handle_interact(game)
        else:
            self._handle_interact(game)

    def _handle_hotbar(self, game: "Game", slot: int) -> None:
        """Handle a hotbar slot key press (1-8)."""
        self._ensure_caches(game)
        if game.inventory is None or game.survival is None:
            return
        if slot < 1 or slot > 8:
            return

        # Find the slot index: hotbar maps to first N non-empty inventory slots
        non_empty = []
        for i, inv_slot in enumerate(game.inventory.slots):
            if inv_slot is not None and inv_slot.item_id is not None and inv_slot.quantity > 0:
                non_empty.append(i)
            if len(non_empty) >= 8:
                break

        if slot > len(non_empty):
            return

        inv_idx = non_empty[slot - 1]
        inv_slot = game.inventory.slots[inv_idx]
        if inv_slot is None or inv_slot.item_id is None:
            return

        item_id = inv_slot.item_id

        # Food → eat it (use cached food registry)
        food_item = self._food_registry.get(item_id) if self._food_registry else None
        if food_item is not None:
            result = game.survival.eat(food_item)
            if game.player is not None and game.player.action_system is not None:
                game.player.action_system.add_notification(result, (100, 255, 100))
            # Remove one from inventory
            game.inventory.remove_item(item_id, 1)
            return

        # Equippable tool → equip it (use cached items.json)
        for item_def in self._items_cache:
            if item_def.get("id") == item_id and item_def.get("is_equippable", False):
                if game.inventory.equip_item(item_id):
                    if game.player is not None and game.player.action_system is not None:
                        game.player.action_system.add_notification(
                            f"Equipped {item_def.get('name', item_id)}.", (100, 180, 255),
                        )
                return

        # Everything else → generic use notification (use cached items.json)
        if game.player is not None and game.player.action_system is not None:
            item_name = next(
                (d.get("name", item_id) for d in self._items_cache if d.get("id") == item_id),
                item_id,
            )
            game.player.action_system.add_notification(f"Used {item_name}.", (200, 200, 220))

    def _handle_hotbar_click(self, game, mx, my):
        """Left-click on a hotbar slot: select the slot and use its item.
        Shared with build mode so hotbar clicks still consume items while placing."""
        if game.hud is None:
            return
        rects = getattr(game.hud, "_hotbar_rects", [])
        for i, rect in enumerate(rects):
            if rect.collidepoint(mx, my):
                game.hud.set_hotbar_selected(i)
                if (
                    game.inventory is not None
                    and game.survival is not None
                    and game.food_registry is not None
                ):
                    self._handle_hotbar(game, i + 1)
                return

    def _hotbar_hit(self, game, mx, my):
        """True if (mx, my) falls on a hotbar slot rect."""
        if game.hud is None:
            return False
        for rect in getattr(game.hud, "_hotbar_rects", []):
            if rect.collidepoint(mx, my):
                return True
        return False

    def _handle_build_placement(self, game, mx, my):
        """Left-click while in build mode: hotbar clicks still use items,
        anything else attempts to place the pending structure at the tile
        under the cursor."""
        if self._hotbar_hit(game, mx, my):
            self._handle_hotbar_click(game, mx, my)
            return
        self._do_build_placement(game, mx, my)

    def _resolve_struct_def(self, game, structure_id):
        """Resolve a pending structure_id to its StructureDef, or None."""
        if game.building_system is None:
            return None
        for cat in game.building_system.structure_defs.values():
            if structure_id in cat:
                return cat[structure_id]
        return None

    def _do_build_placement(self, game, mx, my):
        """Validate and place the pending structure at the cursor's tile.
        Stays in build mode on both success and failure; only cancel keys
        (right-click / ESC) leave placement mode."""
        pending = getattr(game, "_building_pending_id", None)
        if (
            pending is None
            or game.building_system is None
            or game.camera is None
            or game.world is None
        ):
            self._cancel_build_mode(game)
            return

        struct_def = self._resolve_struct_def(game, pending)
        if struct_def is None:
            self._cancel_build_mode(game)
            return

        world_x, world_y = game.camera.screen_to_world(mx, my)
        tile = game.world.get_tile(int(world_x // TILE_SIZE), int(world_y // TILE_SIZE))
        biome_id = tile.biome.id if (tile is not None and tile.biome is not None) else "unknown"

        player = game.player
        px = player.world_x if player is not None else 0.0
        py = player.world_y if player is not None else 0.0

        result = game.building_system.place_structure(
            struct_def, world_x, world_y, px, py, biome_id,
        )
        ps = getattr(player, "action_system", None)
        if ps is not None:
            color = (100, 255, 100) if result.success else (255, 150, 100)
            ps.add_notification(result.message, color)

    def _cancel_build_mode(self, game):
        """Exit placement mode and clear the pending structure."""
        game.build_mode = False
        game._building_pending_id = None
        ps = getattr(game.player, "action_system", None)
        if ps is not None:
            ps.add_notification("Placement cancelled.", (200, 200, 220))

    def _close_all_panels(self) -> None:
        game = self._game
        panel_map = {
            GameState.INVENTORY_OPEN: game._inventory_panel,
            GameState.SKILL_PANEL: game._skill_panel,
            GameState.CRAFTING_PANEL: game._crafting_panel,
            GameState.BUILDING_PANEL: game._building_panel,
            GameState.GEAR_PANEL: game._gear_panel,
            GameState.TRADE_PANEL: game._trade_panel,
            GameState.QUEST_PANEL: game._quest_panel,
            GameState.RECRUIT_PANEL: game._recruit_panel,
            GameState.DIPLOMACY_PANEL: game._diplomacy_panel,
            GameState.CHARACTER_SELECT: game._character_select_panel,
        }
        for panel in panel_map.values():
            if panel is not None:
                panel.close()

    def _is_panel_state(self, state: GameState) -> bool:
        return state in PANEL_STATES

    def _handle_light_fire(self, game: "Game") -> None:
        if game._fire_interaction is not None:
            game._fire_interaction.handle_light_fire()

    def _handle_attack(self, game: "Game") -> None:
        """J key: melee-attack the current target (auto-locks nearest if none)."""
        combat_system = getattr(game, "combat_system", None)
        if combat_system is None:
            return

        # Usable without a prior click: lock the nearest monster if untargeted.
        if (
            combat_system.selected_target is None
            or not combat_system.selected_target.is_alive()
        ):
            combat_system.auto_lock_target()

        # dt is 0 here; combat_system.tick() decrements the cooldown per frame.
        result = combat_system.player_attack(0.0)
        if (
            result is not None
            and game.player is not None
            and game.player.action_system is not None
        ):
            game.player.action_system.add_notification(result.message, (255, 180, 80))

    def _handle_interact(self, game: "Game") -> None:
        if game._interact_system is not None:
            game._interact_system.handle_interact()

    def _handle_mouse_move(self, game: "Game", mx: int, my: int) -> None:
        # Hotbar hover (always, when playing)
        if game.state == GameState.PLAYING and game.hud is not None:
            rects = getattr(game.hud, "_hotbar_rects", [])
            hovered = -1
            for i, rect in enumerate(rects):
                if rect.collidepoint(mx, my):
                    hovered = i
                    break
            game.hud.set_hotbar_hover(hovered, mx, my)
        if game.state == GameState.INVENTORY_OPEN and game._inventory_panel is not None:
            game._inventory_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.CRAFTING_PANEL and game._crafting_panel is not None:
            game._crafting_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.GEAR_PANEL and game._gear_panel is not None:
            game._gear_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.TRADE_PANEL and game._trade_panel is not None:
            game._trade_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.QUEST_PANEL and game._quest_panel is not None:
            game._quest_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.RECRUIT_PANEL and game._recruit_panel is not None:
            game._recruit_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.DIPLOMACY_PANEL and game._diplomacy_panel is not None:
            game._diplomacy_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.SKILL_PANEL and game._skill_panel is not None:
            game._skill_panel.handle_mouse_move(mx, my)
        elif game.state == GameState.BUILDING_PANEL and game._building_panel is not None:
            game._building_panel.handle_mouse_move(mx, my)

        # Track cursor for the build-mode ghost preview (a PLAYING sub-state).
        if getattr(game, "build_mode", False) and game.state == GameState.PLAYING:
            game._build_cursor = (mx, my)

    def _handle_mouse_button_down(self, game: "Game", event) -> None:
        # Placement mode (a PLAYING sub-state) takes precedence: left-click
        # places the pending structure (hotbar clicks still use items),
        # right-click cancels.
        if getattr(game, "build_mode", False) and game.state == GameState.PLAYING:
            if event.button in (2, 3):
                self._cancel_build_mode(game)
            elif event.button == 1:
                self._handle_build_placement(game, event.pos[0], event.pos[1])
            return

        # Quest panel handles all mouse buttons
        if game.state == GameState.QUEST_PANEL and game._quest_panel is not None:
            result = game._quest_panel.handle_click(event.pos[0], event.pos[1])
            if result is not None:
                self._panel_dispatcher.dispatch_click(game.state, "quest", result)
            return
        # Trade panel
        elif game.state == GameState.TRADE_PANEL and game._trade_panel is not None:
            result = game._trade_panel.handle_click(event.pos[0], event.pos[1])
            if result is not None:
                self._panel_dispatcher.dispatch_click(game.state, "trade", result)
            return
        # Recruit panel
        elif game.state == GameState.RECRUIT_PANEL and game._recruit_panel is not None:
            result = game._recruit_panel.handle_click(event.pos[0], event.pos[1])
            if result is not None:
                self._panel_dispatcher.dispatch_click(game.state, "recruit", result)
            return
        # Diplomacy panel
        elif game.state == GameState.DIPLOMACY_PANEL and game._diplomacy_panel is not None:
            result = game._diplomacy_panel.handle_click(event.pos[0], event.pos[1])
            if result is not None:
                self._panel_dispatcher.dispatch_click(game.state, "diplomacy", result)
            return
        # Building panel
        elif game.state == GameState.BUILDING_PANEL and game._building_panel is not None:
            result = game._building_panel.handle_click(event.pos[0], event.pos[1])
            if result is not None:
                self._panel_dispatcher.dispatch_click(game.state, "building", result)
            return

        if event.button == 1:
            # Inventory panel left-click: use/equip items
            if game.state == GameState.INVENTORY_OPEN and game._inventory_panel is not None:
                result = game._inventory_panel.handle_click(
                    event.pos[0], event.pos[1], 1,
                )
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "inventory", result)
                return
            elif game.state == GameState.SKILL_PANEL and game._skill_panel is not None:
                result = game._skill_panel.handle_click(event.pos[0], event.pos[1])
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "skill", result)
                return
            elif game.state == GameState.CRAFTING_PANEL and game._crafting_panel is not None:
                result = game._crafting_panel.handle_click(event.pos[0], event.pos[1])
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "crafting", result)
                return
            elif game.state == GameState.GEAR_PANEL and game._gear_panel is not None:
                result = game._gear_panel.handle_click(event.pos[0], event.pos[1])
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "gear", result)
                return
            elif game.state == GameState.PLAYING:
                self._handle_hotbar_click(game, event.pos[0], event.pos[1])
                # Click-to-move / attack
                if (
                    game.player is not None
                    and game.camera is not None
                    and game.combat_system is not None
                ):
                    screen_x, screen_y = event.pos
                    world_x, world_y = game.camera.screen_to_world(screen_x, screen_y)

                    nearby = game.combat_system.get_nearby_monsters(
                        world_x, world_y, 30.0,
                    )
                    if nearby:
                        game.combat_system.select_target(nearby[0])
                    else:
                        game.player.move_to(world_x, world_y)
        elif event.button in (2, 3):
            if game.state == GameState.INVENTORY_OPEN and game._inventory_panel is not None:
                result = game._inventory_panel.handle_click(
                    event.pos[0], event.pos[1], event.button,
                )
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "inventory", result)
                return
            elif game.state == GameState.SKILL_PANEL and game._skill_panel is not None:
                result = game._skill_panel.handle_click(event.pos[0], event.pos[1])
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "skill", result)
                return
            elif game.state == GameState.CRAFTING_PANEL and game._crafting_panel is not None:
                result = game._crafting_panel.handle_click(event.pos[0], event.pos[1])
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "crafting", result)
                return
            elif game.state == GameState.GEAR_PANEL and game._gear_panel is not None:
                result = game._gear_panel.handle_click(event.pos[0], event.pos[1])
                if result is not None:
                    self._panel_dispatcher.dispatch_click(game.state, "gear", result)
                return

    def _handle_wheel(self, game: "Game", event) -> None:
        """
        Mouse-wheel delivery.

        While a panel is open the panel owns the wheel: the delta is delivered
        to it (clamped by the base) and the pending camera-zoom one-shots are
        cancelled. When no panel is open the wheel zooms the camera via the
        zoom_in/zoom_out flags the InputManager set for this event.
        """
        active_panel = self._get_active_panel(game)
        if active_panel is not None and hasattr(active_panel, "handle_wheel"):
            active_panel.handle_wheel(event.y)
            if self._input_manager is not None:
                st = self._input_manager.input_state
                st.zoom_in = False
                st.zoom_out = False

    def _handle_mouse_up(self, game: "Game") -> None:
        """Forward mouse-button-up to the active panel (ends a scrollbar drag)."""
        active_panel = self._get_active_panel(game)
        if active_panel is not None and hasattr(active_panel, "handle_mouse_up"):
            active_panel.handle_mouse_up()

    def _get_active_panel(self, game: "Game") -> object | None:
        panel_map = {
            GameState.INVENTORY_OPEN: game._inventory_panel,
            GameState.SKILL_PANEL: game._skill_panel,
            GameState.CRAFTING_PANEL: game._crafting_panel,
            GameState.BUILDING_PANEL: game._building_panel,
            GameState.GEAR_PANEL: game._gear_panel,
            GameState.TRADE_PANEL: game._trade_panel,
            GameState.QUEST_PANEL: game._quest_panel,
            GameState.RECRUIT_PANEL: game._recruit_panel,
            GameState.DIPLOMACY_PANEL: game._diplomacy_panel,
        }
        return panel_map.get(game.state)
