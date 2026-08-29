"""
save_system.py — Minimal save/load system.

Serializes game state to JSON files in a `saves/` directory.
Supports multiple save slots, autosave, and manual F5 save.
"""

import json
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from core.game import Game


class SaveSystem:
    """Manages save/load operations for the game."""

    SAVE_VERSION = 2

    @staticmethod
    def _migrate_v1_to_v2(save_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate a v1 save to v2. No data changes — only version bump."""
        save_data["version"] = 2
        return save_data

    def __init__(self, save_dir: str = "saves", slot_count: int = 10) -> None:
        """
        Initialize the save system.

        Args:
            save_dir: Directory to store save files.
            slot_count: Number of available save slots.
        """
        self.save_dir = save_dir
        self.slot_count = slot_count
        os.makedirs(save_dir, exist_ok=True)

    def _slot_path(self, slot: int) -> str:
        """Return the file path for a given save slot."""
        return os.path.join(self.save_dir, f"slot_{slot}.json")

    def save(self, game: "Game", slot: int = 0) -> bool:
        """
        Serialize game state to JSON. Returns False on failure.

        Args:
            game: The current Game instance.
            slot: Save slot number (0-based).

        Returns:
            True if save succeeded, False on failure.
        """
        try:
            snapshot = self._build_snapshot(game)
            path = self._slot_path(slot)
            with open(path, "w") as f:
                json.dump(snapshot, f, indent=2)
            return True
        except Exception as e:
            print(f"Save failed: {e}")
            return False

    def load(self, slot: int = 0) -> Optional[Dict[str, Any]]:
        """
        Load save dict from disk. Returns None if slot is empty.

        Args:
            slot: Save slot number (0-based).

        Returns:
            The save dict, or None if no save exists.
        """
        path = self._slot_path(slot)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def _restore_merchant_stock(npc, saved_inventory: list) -> None:
        """
        Restore stock levels on a merchant's inventory.

        Matches each saved entry to a live slot by ``trade_item_id`` rather
        than by array index, so stock lands on the correct slot even when the
        live inventory order differs from the saved order.
        """
        for slot_data in saved_inventory:
            trade_id = slot_data.get("trade_item_id")
            stock = slot_data.get("stock_quantity", 10)
            for slot in npc.inventory:
                if getattr(slot, "trade_item_id", None) == trade_id:
                    slot.stock_quantity = stock
                    break

    def load_into_game(self, save_data: Dict[str, Any], game: "Game") -> None:
        """
        Restore save data into an existing Game instance.

        Restore order: skills -> survival -> inventory -> gear -> position -> structures -> fires.

        Args:
            save_data: The loaded save dict.
            game: The Game instance to restore into.
        """
        # Migration shim: bump v1 saves to v2 (no data changes)
        if save_data.get("version") == 1:
            save_data = self._migrate_v1_to_v2(save_data)

        # 1. Restore skills
        if "skills" in save_data and game.skill_manager:
            for skill_id, skill_data in save_data["skills"].items():
                if skill_id in game.skill_manager.skills:
                    skill = game.skill_manager.skills[skill_id]
                    skill.level = skill_data.get("level", 1)
                    skill.xp = skill_data.get("xp", 0.0)
                    skill.stat_points = skill_data.get("stat_points", 0)
                    if "sub_stats" in skill_data:
                        skill.sub_stats = dict(skill_data["sub_stats"])

        # Wildcard points live on the SkillManager, not per-skill. Older saves
        # omit the key, so default to 0.
        if game.skill_manager is not None:
            game.skill_manager.wildcard_points = save_data.get("wildcard_points", 0)

        # 2. Restore survival
        if "survival" in save_data and save_data["survival"] and game.survival:
            surv = save_data["survival"]
            game.survival.hp = surv.get("hp", game.survival.hp)
            game.survival.max_hp = surv.get("max_hp", game.survival.max_hp)
            game.survival.hunger = surv.get("hunger", game.survival.hunger)
            game.survival.environmental_pressure = surv.get(
                "environmental_pressure", game.survival.environmental_pressure
            )
            # is_dead is intentionally not restored: death is soft-by-design
            # (_on_player_death respawns the player with partial HP, then saves
            # with is_dead=False), so a saved game always represents an alive
            # player. Respawn-alive on reload is intended (see tmp/LIVE-ISSUES #4).
            game.survival.is_dead = False

        # 3. Restore inventory
        if "inventory" in save_data and game.inventory:
            saved_slots = save_data["inventory"]
            for i, slot_data in enumerate(saved_slots):
                if i >= game.inventory.max_slots:
                    break
                if slot_data is None:
                    game.inventory.slots[i] = None
                else:
                    from inventory.inventory import InventorySlot
                    game.inventory.slots[i] = InventorySlot(
                        item_id=slot_data.get("item_id"),
                        quantity=slot_data.get("quantity", 0),
                        spoilage_remaining=slot_data.get("spoilage_remaining"),
                        is_equipped=slot_data.get("is_equipped", False),
                    )
            # Restore carried gold currency.
            game.inventory.gold = save_data.get("inventory_gold", game.inventory.gold)

        # 4. Restore gear
        if "player" in save_data and save_data["player"].get("gear"):
            gear_data = save_data["player"]["gear"]
            if game.player and game.player.gear:
                from combat.gear import GearItem
                gear_map = GearItem.load_all()

                if gear_data.get("weapon"):
                    weapon_id = gear_data["weapon"]["item_id"]
                    if weapon_id and weapon_id in gear_map:
                        game.player.gear.weapon = gear_map[weapon_id]
                    else:
                        game.player.gear.weapon = None

                if gear_data.get("armor"):
                    armor_id = gear_data["armor"]["item_id"]
                    if armor_id and armor_id in gear_map:
                        game.player.gear.armor = gear_map[armor_id]
                    else:
                        game.player.gear.armor = None

                if gear_data.get("tool"):
                    tool_id = gear_data["tool"]["item_id"]
                    if tool_id and tool_id in gear_map:
                        game.player.gear.tool = gear_map[tool_id]
                    else:
                        game.player.gear.tool = None

        # 5. Restore player position
        if "player" in save_data:
            player_data = save_data["player"]
            if game.player:
                game.player.world_x = player_data.get("world_x", game.player.world_x)
                game.player.world_y = player_data.get("world_y", game.player.world_y)

        # 5.5 Restore quest unlock state (S17)
        if "player" in save_data and game.player:
            player_data = save_data["player"]
            game.player.unlocked_recipes = set(player_data.get("unlocked_recipes", []))
            game.player.unlocked_gear = set(player_data.get("unlocked_gear", []))
            game.player.recruited_npcs = list(player_data.get("recruited_npcs", []))

        # 6. Restore structures.
        # Known limitation (v1): depleted world resource nodes are NOT
        # persisted. The world is regenerated from seed on load and
        # structures/fires are overlaid on top. See plan
        # phase-bugfix-granular (3.1) for the v2 resource-overlay follow-up.
        if "structures" in save_data and game.building_system:
            from building.structure import Structure, StructureDef
            for struct_data in save_data["structures"]:
                struct_id = struct_data.get("structure_id", "")
                # Find the structure def
                for category_defs in game.building_system.structure_defs.values():
                    if struct_id in category_defs:
                        struct_def = category_defs[struct_id]
                        structure = Structure(
                            structure_def=struct_def,
                            world_x=struct_data.get("world_x", 0.0),
                            world_y=struct_data.get("world_y", 0.0),
                            hp=struct_data.get("hp", struct_def.hp),
                            max_hp=struct_data.get("max_hp", struct_def.hp),
                            is_active=struct_data.get("is_active", True),
                        )
                        game.building_system.structures.append(structure)
                        break

        # 6b. Restore resource nodes (depletion state, regrowth timers)
        if "resource_nodes" in save_data and game.world:
            from world.resource_node import ResourceNode
            from world.resource_placer import ResourcePlacer
            import dataclasses
            resource_cache = ResourcePlacer._load_resource_definitions()
            for node_data in save_data["resource_nodes"]:
                x = node_data.get("x", 0)
                y = node_data.get("y", 0)
                resource_id = node_data.get("resource_id", "")
                current_depletions = node_data.get("current_depletions", 0)
                depleted = node_data.get("depleted", False)
                regrow_timer = node_data.get("regrow_timer", 0.0)
                
                tile = game.world.get_tile(x, y)
                if tile is None:
                    continue
                
                if resource_id in resource_cache:
                    # Create a copy of the resource node with saved depletion state
                    node = resource_cache[resource_id]
                    tile.resource_node = dataclasses.replace(node, current_depletions=current_depletions)
                    tile.depleted = depleted
                    tile.regrow_timer = regrow_timer
                else:
                    # Resource definition not found (maybe removed from data)
                    tile.resource_node = None
                    tile.depleted = False
                    tile.regrow_timer = 0.0

        # 6.5 Restore NPC-structure assignments (P3-S16)
            assignments = save_data["npc_structure_assignments"]
            for npc_id, structure_id in assignments.items():
                # Set the NPC's field
                if game.npc_system:
                    for npc in game.npc_system.npcs:
                        if npc.npc_id == npc_id:
                            npc.assigned_structure_id = structure_id
                            break

                # Re-establish in building_system's assignment map
                if game.building_system:
                    game.building_system.npc_assignments[structure_id] = npc_id
                    for s in game.building_system.structures:
                        if s.structure_def.structure_id == structure_id:
                            s.assigned_npc_id = npc_id
                            break

        # 7. Restore active fires
        if "active_fires" in save_data and game.firemaking:
            from skills.firemaking.fire_entity import FireEntity
            for fire_data in save_data["active_fires"]:
                fire = FireEntity(
                    fire_id=fire_data.get("fire_id", f"fire_restored_{len(game.firemaking.active_fires)}"),
                    world_x=fire_data.get("world_x", 0.0),
                    world_y=fire_data.get("world_y", 0.0),
                    fuel_items=fire_data.get("fuel_items", []),
                    # Preserve total planned burn time across loads so the
                    # remaining/total ratio survives a reload. Falls back to
                    # burn_remaining for saves written before this field existed.
                    burn_duration_total=fire_data.get(
                        "burn_duration_total", fire_data.get("burn_remaining", 0.0)
                    ),
                    burn_duration_remaining=fire_data.get("burn_remaining", 0.0),
                    radius_tiles=1.0,
                    heat_output=1.0,
                    is_active=fire_data.get("burn_remaining", 0.0) > 0,
                )
                game.firemaking.active_fires.append(fire)

        # 8. Restore faction standing (P3-S13)
        if "faction_standing" in save_data and game.faction_system:
            game.faction_system.load_snapshot(save_data["faction_standing"])

        # 8.5 Restore quest progress (P3-S23)
        if "quest_progress" in save_data and save_data["quest_progress"] and game.quest_system:
            from npc.quest_system import QuestProgress, QuestCondition, QuestState
            for qid, qdata in save_data["quest_progress"].items():
                state_str = qdata.get("state", "available")
                try:
                    state = QuestState(state_str)
                except ValueError:
                    state = QuestState.AVAILABLE
                conditions = [
                    QuestCondition(
                        condition_type=c.get("condition_type", ""),
                        target=c.get("target", ""),
                        required_count=c.get("required_count", 1),
                        current_count=c.get("current_count", 0),
                        description=c.get("description", ""),
                    )
                    for c in qdata.get("conditions", [])
                ]
                fail_conditions = [
                    QuestCondition(
                        condition_type=fc.get("condition_type", ""),
                        target=fc.get("target", ""),
                        required_count=fc.get("required_count", 1),
                        current_count=fc.get("current_count", 0),
                        description=fc.get("description", ""),
                    )
                    for fc in qdata.get("fail_conditions", [])
                ]
                progress = QuestProgress(
                    quest_id=qdata.get("quest_id", qid),
                    state=state,
                    giver_npc_id=qdata.get("giver_npc_id", ""),
                    accepted_at=qdata.get("accepted_at", 0.0),
                    completed_at=qdata.get("completed_at", 0.0),
                    failed_at=qdata.get("failed_at", 0.0),
                    fail_reason=qdata.get("fail_reason", ""),
                    is_repeatable=qdata.get("is_repeatable", False),
                    conditions=conditions,
                    fail_conditions=fail_conditions,
                )
                game.quest_system.quest_progress[qid] = progress

        # 8.6 Restore faction interaction history / quest tracking (P3-S23)
        if "quest_tracking" in save_data and save_data["quest_tracking"] and game.quest_system:
            qt = save_data["quest_tracking"]
            qs = game.quest_system
            qs._monster_kill_counts = dict(qt.get("monster_kill_counts", {}))
            qs._craft_counts = dict(qt.get("craft_counts", {}))
            qs._visited_biomes = set(qt.get("visited_biomes", []))
            qs._trade_counts = dict(qt.get("trade_counts", {}))
            qs._delivery_counts = dict(qt.get("delivery_counts", {}))
            qs._negotiation_counts = dict(qt.get("negotiation_counts", {}))
            qs._combat_faction_counts = dict(qt.get("combat_faction_counts", {}))

        # 8.7 Restore merchant economy (P3-S23)
        if "merchant_economy" in save_data and save_data["merchant_economy"]:
            from npc.npc_types import MerchantNPC
            for mdata in save_data["merchant_economy"]:
                if game.npc_system is not None:
                    for npc in game.npc_system.npcs:
                        if npc.npc_id == mdata.get("npc_id"):
                            if isinstance(npc, MerchantNPC):
                                npc.gold = mdata.get("gold", npc.gold)
                                # Restore stock by matching trade_item_id (not by index)
                                # so stock lands on the right slot even if the live
                                # inventory order changed after the save.
                                self._restore_merchant_stock(npc, mdata.get("inventory", []))

        # 8.8 Restore recruitment behavioral state (P3-S23)
        if "recruitment_state" in save_data and save_data["recruitment_state"] and game.recruitment_system:
            rs_data = save_data["recruitment_state"]
            rs = game.recruitment_system
            # Restore base position
            if "base_x" in rs_data and rs.base_x is None:
                rs.base_x = rs_data["base_x"]
                rs.base_y = rs_data["base_y"]
            # Restore per-NPC recruit state (is_recruited + assigned behavior).
            # Runs before the behaviors loop below so recruit-flagged NPCs are
            # recognized when matching behavior entries.
            if game.npc_system is not None:
                for npc_recruit in rs_data.get("npc_recruits", []):
                    for npc in game.npc_system.npcs:
                        if npc.npc_id == npc_recruit.get("npc_id"):
                            npc.is_recruited = npc_recruit.get("is_recruited", False)
                            npc.recruit_behavior = npc_recruit.get("recruit_behavior")
                            break
            # Restore behavior states
            for npc_id, behavior_data in rs_data.get("behaviors", {}).items():
                if npc_id not in rs.behaviors:
                    # Check if NPC still exists
                    if game.npc_system is not None:
                        for npc in game.npc_system.npcs:
                            if npc.npc_id == npc_id and npc.is_recruited:
                                rs.behaviors[npc_id] = behavior_data
                                break

        # 8.9 Restore NPC patrol state (P3-S23)
        if "npc_patrol_state" in save_data and save_data["npc_patrol_state"] and game.npc_system:
            for npc_id, target in save_data["npc_patrol_state"].items():
                if isinstance(target, (list, tuple)) and len(target) == 2:
                    game.npc_system._patrol_targets[npc_id] = (target[0], target[1])

        # Restore season state
        if "season" in save_data and save_data["season"] and game.season_system:
            season_data = save_data["season"]
            game.season_system.current_season = season_data.get("current", "spring")
            game.season_system.season_progress = season_data.get("progress", 0.0)
            game.season_system.season_elapsed = season_data.get("elapsed", 0.0)
            game.season_system.previous_season = season_data.get("previous")
            game.season_system.transition_blend = season_data.get("transition_blend", 0.0)
            game.season_system.survival_modifiers = season_data.get(
                "survival_modifiers", game.season_system.survival_modifiers
            )
            game.season_system.resource_multipliers = season_data.get(
                "resource_multipliers", game.season_system.resource_multipliers
            )
            game.season_system.availability = season_data.get(
                "availability", game.season_system.availability
            )

        # Restore weather state
        if "weather" in save_data and save_data["weather"] and game.weather_system:
            weather_data = save_data["weather"]
            game.weather_system.current_weather = weather_data.get("current", "clear")
            game.weather_system.weather_timer = weather_data.get("timer", 0.0)
            game.weather_system.weather_history = weather_data.get("history", [])

        # Re-sync particle system after load
        if hasattr(game, "particle_system") and game.particle_system is not None:
            game.particle_system.sync(game.weather_system.current_weather)

    def list_slots(self) -> List[Dict[str, Any]]:
        """
        Return list of slot info dicts.

        Returns:
            List of {slot, has_save, seed, death_count} dicts.
        """
        result: List[Dict[str, Any]] = []
        for i in range(self.slot_count):
            data = self.load(i)
            if data:
                result.append({
                    "slot": i,
                    "has_save": True,
                    "seed": data.get("seed"),
                    "death_count": data.get("death_count", 0),
                })
            else:
                result.append({"slot": i, "has_save": False})
        return result

    def has_save(self, slot: int) -> bool:
        """Check if a save exists in the given slot."""
        return self.load(slot) is not None

    def _build_snapshot(self, game: "Game") -> Dict[str, Any]:
        """
        Build a save dict from the current Game state.

        Guards all null subsystems to handle partial game states.

        Args:
            game: The current Game instance.

        Returns:
            A serializable dict representing the game state.
        """
        snapshot: Dict[str, Any] = {
            "version": self.SAVE_VERSION,
            "seed": game.seed,
            "death_count": game.death_count,
        }

        # Player position + gear
        if game.player:
            player_data: Dict[str, Any] = {
                "world_x": game.player.world_x,
                "world_y": game.player.world_y,
            }
            if hasattr(game.player, "gear") and game.player.gear:
                player_data["gear"] = game.player.gear.get_snapshot()
            # Quest unlock state (S17)
            player_data["unlocked_recipes"] = list(getattr(game.player, "unlocked_recipes", set()))
            player_data["unlocked_gear"] = list(getattr(game.player, "unlocked_gear", set()))
            player_data["recruited_npcs"] = list(getattr(game.player, "recruited_npcs", []))
            snapshot["player"] = player_data
        else:
            snapshot["player"] = {"world_x": 0, "world_y": 0, "gear": None}

        # Inventory
        if game.inventory:
            snapshot["inventory"] = game.inventory.get_snapshot()
            snapshot["inventory_gold"] = game.inventory.gold
        else:
            snapshot["inventory"] = [None] * 20
            snapshot["inventory_gold"] = 0

        # Skills (guard null)
        if game.skill_manager:
            snapshot["skills"] = {}
            for skill_id, skill in game.skill_manager.skills.items():
                snapshot["skills"][skill_id] = {
                    "level": skill.level,
                    "xp": skill.xp,
                    "stat_points": skill.stat_points,
                    "sub_stats": dict(skill.sub_stats),
                }
            # Wildcard points live on the SkillManager, not per-skill
            snapshot["wildcard_points"] = game.skill_manager.wildcard_points
        else:
            snapshot["skills"] = {}

        # Survival (guard null)
        if game.survival:
            snapshot["survival"] = {
                "hp": game.survival.hp,
                "max_hp": game.survival.max_hp,
                "hunger": game.survival.hunger,
                "environmental_pressure": game.survival.environmental_pressure,
            }
        else:
            snapshot["survival"] = None

        # Structures (guard null)
        structures: List[Dict[str, Any]] = []
        if game.building_system:
            for s in game.building_system.get_all_structures():
                if s.is_active:
                    structures.append({
                        "structure_id": s.structure_def.structure_id if hasattr(s, "structure_def") else "unknown",
                        "world_x": s.world_x,
                        "world_y": s.world_y,
                        "hp": s.hp if hasattr(s, "hp") else 0,
                        "max_hp": getattr(s, "max_hp", s.hp if hasattr(s, "hp") else 0),
                        "is_active": s.is_active,
                    })
        snapshot["structures"] = structures

        # Resource nodes (depletion state, regrowth timers)
        resource_nodes: List[Dict[str, Any]] = []
        if game.world:
            for x in range(game.world.width):
                for y in range(game.world.height):
                    tile = game.world.get_tile(x, y)
                    if tile and tile.resource_node is not None:
                        node = tile.resource_node
                        resource_nodes.append({
                            "x": x,
                            "y": y,
                            "resource_id": node.resource_id,
                            "current_depletions": node.current_depletions,
                            "depleted": tile.depleted,
                            "regrow_timer": tile.regrow_timer,
                        })
        snapshot["resource_nodes"] = resource_nodes

        # Active fires (guard null)
        fires: List[Dict[str, Any]] = []
        if game.firemaking:
            for f in game.firemaking.get_active_fires():
                fires.append({
                    "fire_id": getattr(f, "fire_id", "unknown"),
                    "world_x": f.world_x,
                    "world_y": f.world_y,
                    "burn_remaining": getattr(f, "burn_duration_remaining", 0.0),
                    "burn_duration_total": getattr(f, "burn_duration_total", 0.0),
                    "fuel_items": getattr(f, "fuel_items", []),
                })
        snapshot["active_fires"] = fires

        # Faction standing (P3-S13)
        if hasattr(game, "faction_system") and game.faction_system:
            snapshot["faction_standing"] = game.faction_system.get_snapshot()
        else:
            snapshot["faction_standing"] = {}

        # NPC-structure assignments (P3-S16)
        npc_structure_assignments = {}
        if hasattr(game, "npc_system") and game.npc_system:
            for npc in game.npc_system.npcs:
                if hasattr(npc, "assigned_structure_id") and npc.assigned_structure_id:
                    npc_structure_assignments[npc.npc_id] = npc.assigned_structure_id
        if npc_structure_assignments:
            snapshot["npc_structure_assignments"] = npc_structure_assignments
        else:
            snapshot["npc_structure_assignments"] = {}

        # Quest progress (P3-S23)
        if hasattr(game, "quest_system") and game.quest_system:
            qs = game.quest_system
            quest_progress_data = {}
            for qid, progress in qs.quest_progress.items():
                quest_progress_data[qid] = {
                    "quest_id": progress.quest_id,
                    "state": progress.state.value if hasattr(progress.state, "value") else str(progress.state),
                    "giver_npc_id": progress.giver_npc_id,
                    "accepted_at": progress.accepted_at,
                    "completed_at": progress.completed_at,
                    "failed_at": progress.failed_at,
                    "fail_reason": progress.fail_reason,
                    "is_repeatable": progress.is_repeatable,
                    "conditions": [
                        {
                            "condition_type": c.condition_type,
                            "target": c.target,
                            "required_count": c.required_count,
                            "current_count": c.current_count,
                            "description": c.description,
                        }
                        for c in progress.conditions
                    ],
                    "fail_conditions": [
                        {
                            "condition_type": fc.condition_type,
                            "target": fc.target,
                            "required_count": fc.required_count,
                            "current_count": fc.current_count,
                            "description": fc.description,
                        }
                        for fc in progress.fail_conditions
                    ],
                }
            snapshot["quest_progress"] = quest_progress_data
        else:
            snapshot["quest_progress"] = {}

        # Faction interaction history / quest tracking (P3-S23)
        if hasattr(game, "quest_system") and game.quest_system:
            qs = game.quest_system
            snapshot["quest_tracking"] = {
                "monster_kill_counts": dict(getattr(qs, "_monster_kill_counts", {})),
                "craft_counts": dict(getattr(qs, "_craft_counts", {})),
                "visited_biomes": list(getattr(qs, "_visited_biomes", set())),
                "trade_counts": dict(getattr(qs, "_trade_counts", {})),
                "delivery_counts": dict(getattr(qs, "_delivery_counts", {})),
                "negotiation_counts": dict(getattr(qs, "_negotiation_counts", {})),
                "combat_faction_counts": dict(getattr(qs, "_combat_faction_counts", {})),
            }
        else:
            snapshot["quest_tracking"] = {}

        # Merchant economy — gold reserves and inventory stock (P3-S23)
        merchant_economy = []
        if hasattr(game, "npc_system") and game.npc_system:
            from npc.npc_types import MerchantNPC
            for npc in game.npc_system.npcs:
                if isinstance(npc, MerchantNPC):
                    merchant_economy.append({
                        "npc_id": npc.npc_id,
                        "gold": npc.gold,
                        "inventory": [
                            {
                                "trade_item_id": item.trade_item_id,
                                "stock_quantity": item.stock_quantity,
                            }
                            for item in npc.inventory
                        ],
                    })
        snapshot["merchant_economy"] = merchant_economy

        # Recruitment behavioral state (P3-S23)
        if hasattr(game, "recruitment_system") and game.recruitment_system:
            rs = game.recruitment_system
            snapshot["recruitment_state"] = {
                "behaviors": dict(getattr(rs, "behaviors", {})),
            }
            # Persist per-NPC recruit state (is_recruited + assigned behavior).
            # Saved here rather than in the player block because it is NPC-system
            # state; the recruited-id list lives in the player block.
            if game.npc_system is not None:
                snapshot["recruitment_state"]["npc_recruits"] = [
                    {
                        "npc_id": npc.npc_id,
                        "is_recruited": getattr(npc, "is_recruited", False),
                        "recruit_behavior": getattr(npc, "recruit_behavior", None),
                    }
                    for npc in game.npc_system.npcs
                    if getattr(npc, "is_recruited", False)
                ]
            # Restore base position if known
            if rs.base_x is not None and rs.base_y is not None:
                snapshot["recruitment_state"]["base_x"] = rs.base_x
                snapshot["recruitment_state"]["base_y"] = rs.base_y
        else:
            snapshot["recruitment_state"] = {}

        # NPC patrol state (P3-S23)
        patrol_state = {}
        if hasattr(game, "npc_system") and game.npc_system:
            for npc_id, target in game.npc_system._patrol_targets.items():
                patrol_state[npc_id] = list(target)
        snapshot["npc_patrol_state"] = patrol_state

        # Season state
        if hasattr(game, "season_system") and game.season_system:
            snapshot["season"] = game.season_system.to_dict()
        else:
            snapshot["season"] = None

        # Weather state
        if hasattr(game, "weather_system") and game.weather_system:
            snapshot["weather"] = game.weather_system.to_dict()
        else:
            snapshot["weather"] = None

        return snapshot
