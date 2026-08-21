from __future__ import annotations

from core.state import GameState
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.game import Game


class PanelDispatcher:

    def __init__(self, game: "Game") -> None:
        self._game = game
        from interactions.npc_flows import NPCFlows
        self._npc_flows = NPCFlows(game)

    def dispatch(self, state: "GameState", action: tuple | str) -> None:
        if isinstance(action, tuple) and action[0] == "close":
            self._handle_close(state); return
        if isinstance(action, tuple) and action[0] == "cancel":
            self._handle_cancel(state); return
        if isinstance(action, tuple) and action[0] == "use" and state == GameState.INVENTORY_OPEN:
            self._handle_inventory_use(action[1]); return
        if isinstance(action, tuple) and action[0] == "drop" and state == GameState.INVENTORY_OPEN:
            self._handle_inventory_drop(action[1]); return
        if isinstance(action, tuple) and len(action) == 1 and action[0] == "toggle_wildcard" and state == GameState.SKILL_PANEL:
            self._handle_skill_allocation(*action); return
        if isinstance(action, tuple) and len(action) >= 3 and state == GameState.SKILL_PANEL:
            self._handle_skill_allocation(*action); return
        if isinstance(action, tuple) and len(action) >= 2 and state == GameState.CRAFTING_PANEL:
            self._handle_craft_click(action[0], action[1]); return
        if isinstance(action, str) and state == GameState.BUILDING_PANEL and action.startswith("place:"):
            self._handle_building_place(action[6:]); return
        if isinstance(action, str) and state == GameState.GEAR_PANEL and ":" in action:
            self._handle_gear_action(action); return
        if isinstance(action, tuple) and state == GameState.TRADE_PANEL and action[0] in ("buy", "sell"):
            self._npc_flows.handle_trade_action(action); return
        if isinstance(action, tuple) and len(action) >= 2 and action[0] == "accept_quest" and state == GameState.QUEST_PANEL:
            self._npc_flows.handle_quest_action(action); return
        if isinstance(action, tuple) and state == GameState.RECRUIT_PANEL and action[0] == "recruit":
            npc_id = action[1]; behavior = action[2]
            structure_id = action[3] if len(action) >= 4 else None
            self._npc_flows.execute_recruitment(npc_id, behavior, structure_id); return
        if isinstance(action, tuple) and action[0] == "negotiate" and state == GameState.DIPLOMACY_PANEL:
            self._npc_flows.execute_negotiation(); return

    def dispatch_click(self, state: "GameState", panel_name: str, action) -> None:
        if panel_name == "inventory" and action is not None:
            self._handle_inventory_click(action[0], action[1])
        elif panel_name == "skill" and action is not None:
            self._handle_skill_allocation(*action)
        elif panel_name == "crafting" and action is not None:
            self._handle_craft_click(action[0], action[1])
        elif panel_name == "gear" and action is not None:
            self._handle_gear_action(action)
        elif panel_name == "building" and action is not None:
            if action[0] == "select":
                self._handle_building_select(action[1])
            elif action[0] == "close":
                self._handle_building_close()
        elif panel_name == "trade" and action is not None:
            self._npc_flows.handle_trade_action(action)
        elif panel_name == "quest" and action is not None:
            self._npc_flows.handle_quest_action(action)
        elif panel_name == "recruit" and action is not None:
            self._npc_flows.handle_recruit_action(action)
        elif panel_name == "diplomacy" and action is not None:
            self._npc_flows.handle_diplomacy_action(action)

    def _handle_inventory_use(self, item_id: str) -> None:
        """Use/equip an inventory item (keyboard Enter or left-click)."""
        game = self._game
        if game.player is None or game.inventory is None or game.player.action_system is None:
            return
        if game.inventory.get_item_quantity(item_id) <= 0:
            game.player.action_system.add_notification(
                f"Cannot use {item_id}.", (255, 100, 100),
            )
            return

        # Food → eat it
        food_item = None
        if game.food_registry is not None:
            food_item = game.food_registry.get(item_id)
        if food_item is not None:
            result = game.survival.eat(food_item)
            game.player.action_system.add_notification(result, (100, 255, 100))
            game.inventory.remove_item(item_id, 1)
            return

        # Equippable tool → equip it
        from data import load_json_list
        items_data = load_json_list("items.json", "items")
        for item_def in items_data:
            if item_def.get("id") == item_id and item_def.get("is_equippable", False):
                if game.inventory.equip_item(item_id):
                    game.player.action_system.add_notification(
                        f"Equipped {item_def.get('name', item_id)}.", (100, 180, 255),
                    )
                return

        # Everything else → generic use notification
        item_name = next(
            (d.get("name", item_id) for d in items_data if d.get("id") == item_id),
            item_id,
        )
        game.player.action_system.add_notification(f"Used {item_name}.", (200, 200, 220))

    def _handle_inventory_drop(self, item_id: str) -> None:
        """Drop an inventory item (right-click or Delete/Backspace)."""
        game = self._game
        if game.inventory is None or game.player is None or game.player.action_system is None:
            return
        if game.inventory.get_item_quantity(item_id) <= 0:
            game.player.action_system.add_notification(
                f"Cannot drop {item_id}.", (255, 100, 100),
            )
            return
        removed = game.inventory.remove_item(item_id, 1)
        if removed:
            game.player.action_system.add_notification(
                f"Dropped {item_id}.", (255, 150, 100),
            )
        else:
            game.player.action_system.add_notification(
                f"Cannot drop {item_id}.", (255, 100, 100),
            )

    def _handle_close(self, state: "GameState") -> None:
        game = self._game
        if state == GameState.TRADE_PANEL and game._trade_panel is not None:
            game._trade_panel.close_session()
        elif state == GameState.QUEST_PANEL and game._quest_panel is not None:
            game._quest_panel.close_session()
        elif state == GameState.RECRUIT_PANEL:
            self._npc_flows.close_recruit_panel()
        elif state == GameState.DIPLOMACY_PANEL:
            self._npc_flows.close_diplomacy_panel()
        else:
            game.set_state(GameState.PLAYING)

    def _handle_cancel(self, state: "GameState") -> None:
        game = self._game
        if state == GameState.RECRUIT_PANEL:
            self._npc_flows.close_recruit_panel()
        elif state == GameState.DIPLOMACY_PANEL:
            self._npc_flows.close_diplomacy_panel()
        else:
            game.set_state(GameState.PLAYING)

    def _handle_skill_allocation(self, *args) -> None:
        game = self._game
        if not args:
            return
        if len(args) == 1 and args[0] == "toggle_wildcard":
            if game._skill_panel is not None:
                game._skill_panel._use_wildcard = not game._skill_panel._use_wildcard
            return
        if len(args) != 3:
            return
        skill_id: str = args[0]
        sub_stat: str = args[1]
        points: int = args[2]
        if game.skill_manager is None:
            return
        if points > 0:
            use_wildcard = (game._skill_panel is not None and
                            game._skill_panel._use_wildcard)
            game.skill_manager.allocate_stat(skill_id, sub_stat, points, wildcard=use_wildcard)
        elif points < 0:
            if skill_id in game.skill_manager.skills:
                skill = game.skill_manager.skills[skill_id]
                if sub_stat in skill.sub_stats and skill.sub_stats[sub_stat] > 0:
                    skill.sub_stats[sub_stat] -= 1
                    skill.stat_points += 1

    def _handle_craft_click(self, btn_type: str, item_id: str) -> None:
        game = self._game
        if btn_type == "smelt":
            self._handle_smelt_click(item_id)
            return
        if game.crafting is None or game.inventory is None:
            return
        recipe = game.crafting.get_recipe(item_id)
        if recipe is None:
            return
        structures = game.building_system.get_all_structures() if game.building_system else []
        player_x = game.player.world_x if game.player else 0.0
        player_y = game.player.world_y if game.player else 0.0
        if recipe.requires_campfire:
            has_campfire = game._check_nearby_campfire()
            result = game.crafting.cook(item_id, game.inventory, game.skill_manager,
                has_campfire, structures=structures, player_pos=(player_x, player_y))
        else:
            result = game.crafting.craft(item_id, game.inventory, game.skill_manager,
                structures=structures, player_pos=(player_x, player_y))
        if not result.success:
            return
        if (game.food_registry is not None and recipe.is_food and
            recipe.output_item is not None):
            food = game.food_registry.get(recipe.output_item)
            if food and food.spoilage_rate > 0:
                game.inventory.set_spoilage(recipe.output_item, food.spoilage_rate)
        if game.player is not None and game.player.action_system is not None:
            game.player.action_system.add_notification(result.message)

    def _handle_smelt_click(self, recipe_id: str) -> None:
        game = self._game
        if game.metallurgy is None or game.inventory is None:
            return
        player_x = game.player.world_x if game.player else 0.0
        player_y = game.player.world_y if game.player else 0.0
        structures = game.building_system.get_all_structures() if game.building_system else []
        result = game.metallurgy.attempt_smelt(recipe_id, game.inventory,
            player_world_x=player_x, player_world_y=player_y,
            structures=structures)
        if game.player is not None and game.player.action_system is not None:
            color = (100, 255, 100) if result.success else (255, 150, 100)
            game.player.action_system.add_notification(result.message, color)

    def _handle_gear_action(self, action: str) -> None:
        game = self._game
        if game.player is None or game.inventory is None:
            return
        gear = game.player.gear
        if gear is None:
            return
        if action.startswith("equip:"):
            item_id = action[6:]
            from combat.gear import GearItem
            gear_map = GearItem.load_all()
            gear_item = gear_map.get(item_id)
            if gear_item is None:
                return
            combat_level = game.skill_manager.get_skill_level("combat")
            if combat_level < gear_item.required_combat_level:
                if game.player.action_system is not None:
                    game.player.action_system.add_notification(
                        f"Need Combat level {gear_item.required_combat_level} to equip {gear_item.name}.",
                        (255, 150, 100))
                return
            if gear_item.gear_type == "weapon":
                gear.unequip("weapon")
            elif gear_item.gear_type == "armor":
                gear.unequip("armor")
            gear.equip(gear_item)
            if game.player.action_system is not None:
                game.player.action_system.add_notification(
                    f"Equipped {gear_item.name}.",
                    (100, 255, 100))
        elif action.startswith("unequip:"):
            slot_type = action[9:]
            old_item = gear.unequip(slot_type)
            if old_item is not None and game.player.action_system is not None:
                game.player.action_system.add_notification(
                    f"Unequipped {old_item.name}.",
                    (200, 200, 150))

    def _handle_building_select(self, structure_id: str) -> None:
        game = self._game
        if game._building_panel is not None:
            game._building_panel.selected_structure_id = structure_id
        self._notify_building_select(game, structure_id)

    def _handle_building_place(self, structure_id: str) -> None:
        game = self._game
        if game._building_panel is not None:
            game._building_panel.selected_structure_id = structure_id
        self._notify_building_select(game, structure_id)

    def _notify_building_select(self, game: "Game", structure_id: str) -> None:
        if game.player is None or game.player.action_system is None:
            return
        struct_def = None
        for cat in game.building_system.structure_defs.values():
            if structure_id in cat:
                struct_def = cat[structure_id]
                break
        if struct_def is not None:
            game.player.action_system.add_notification(
                f"Selected: {struct_def.name}. Click on map to place.",
                (200, 200, 220),
            )

    def _handle_building_close(self) -> None:
        self._game._building_panel.visible = False
        self._game.set_state(GameState.PLAYING)

    def _handle_inventory_click(self, action: str, detail: str) -> None:
        game = self._game
        if action == "gear":
            game.set_state(GameState.GEAR_PANEL)
        elif action == "close":
            game.set_state(GameState.PLAYING)
        elif action == "use":
            self._handle_inventory_use(detail)
        elif action == "drop":
            self._handle_inventory_drop(detail)

 
