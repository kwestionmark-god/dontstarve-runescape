"""
npc/recruitment.py — Recruitment behavior management.

Manages recruited NPCs, their behavior loops (guard/trader/assistant),
base position tracking, and cross-system integration (combat, trade,
survival, inventory).

Phase 3, Step 14: Recruit Behavior AI.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from npc.npc import NPC
    from combat.monster import Monster
    from world.resource_node import ResourceNode


class RecruitmentSystem:
    """
    Manages recruited NPCs, their behaviors, base assignment, and AI updates.

    Fields:
        game: Reference to the Game instance.
        intelligence_skill: Reference to IntelligenceSkill (slot limits).
        base_x, base_y: Player's base center position.
        behaviors: Dict mapping npc_id -> behavior state dict.
        _behavior_timer: Accumulator for 0.5s behavior tick interval.

    Behavior state dict per NPC:
        {
            "target": (x, y),           # Current movement target
            "substate": "patrol",       # Guard: patrol/combat/returning
            "combat_target": None,      # Currently targeted monster (guards)
            "trade_timer": 0.0,         # Cooldown for next trade (traders)
            "trade_cooldown": 30.0,     # Seconds between trades
            "follow_timer": 0.0,        # Cooldown for resource check (assistants)
            "gather_cooldown": 15.0,    # Seconds between gathers
        }
    """

    # ── Constants ──────────────────────────────────────────────────

    GUARD_PATROL_RADIUS = 100      # px from base center for patrol waypoints
    GUARD_COMBAT_RANGE = 150       # px to detect monsters
    GUARD_COMBAT_MELEE = 40        # px melee range for attacking
    GUARD_RETREAT_HP_THRESHOLD = 0.3  # retreat at 30% HP
    GUARD_RETURN_RADIUS = 50       # px to consider "at base"

    TRADER_TRADE_INTERVAL = 30.0   # seconds between trades
    TRADER_TRADE_RANGE = 200       # px to reach merchant
    TRADER_RETURN_RADIUS = 50      # px to consider "at base"

    ASSISTANT_FOLLOW_DISTANCE = 80 # px to maintain from player
    ASSISTANT_GATHER_RANGE = 30    # px to gather from resource
    ASSISTANT_HEAL_THRESHOLD = 0.7 # heal when player HP < 70%
    ASSISTANT_HEAL_AMOUNT = 8.0    # HP restored per healing offer
    ASSISTANT_HEAL_INTERVAL = 10.0 # seconds between healing offers

    BEHAVIOR_TICK_INTERVAL = 0.5   # behavior decision tick rate

    __slots__ = (
        "game",
        "intelligence_skill",
        "base_x", "base_y",
        "behaviors",
        "_behavior_timer",
        "_building_system",
    )

    def __init__(self, game) -> None:
        """
        Initialize the recruitment system.

        Args:
            game: The Game instance (provides access to all subsystems).
        """
        self.game = game
        self.intelligence_skill = game.intelligence  # IntelligenceSkill
        self.base_x: Optional[float] = None
        self.base_y: Optional[float] = None
        self.behaviors: Dict[str, dict] = {}  # npc_id -> state dict
        self._behavior_timer: float = 0.0
        self._building_system: Optional[object] = None

        # Initialize base position at world spawn
        if game.world is not None:
            spawn_tile_x = game.world.spawn_x
            spawn_tile_y = game.world.spawn_y
            self.base_x = spawn_tile_x * 64 + 32
            self.base_y = spawn_tile_y * 64 + 32

    # ── Core Tick ──────────────────────────────────────────────────

    def tick(self, dt: float) -> None:
        """
        Main behavior tick -- dispatches to behavior-specific handlers.

        Runs at BEHAVIOR_TICK_INTERVAL (0.5s) to prevent twitchy AI.
        Movement still updates every frame via NPCSystem.

        Args:
            dt: Delta time in seconds.
        """
        self._behavior_timer += dt
        if self._behavior_timer < self.BEHAVIOR_TICK_INTERVAL:
            return
        self._behavior_timer = 0.0

        if self.game.player is None:
            return

        # Dispatch to each recruited NPC's behavior handler
        for npc_id, state in list(self.behaviors.items()):
            npc = self._find_npc(npc_id)
            if npc is None or not npc.is_recruited:
                # Clean up stale entries
                del self.behaviors[npc_id]
                continue

            behavior = npc.recruit_behavior
            if behavior == "guard":
                self._guard_behavior(npc, state, dt)
            elif behavior == "trader":
                self._trader_behavior(npc, state, dt)
            elif behavior == "assistant":
                self._assistant_behavior(npc, state, dt)

    # ── Helper: NPC Lookup ─────────────────────────────────────────

    def _find_npc(self, npc_id: str) -> Optional[NPC]:
        """Find an NPC by ID in the NPCSystem's NPC list."""
        if self.game.npc_system is None:
            return None
        for npc in self.game.npc_system.npcs:
            if npc.npc_id == npc_id:
                return npc
        return None

    # ── Helper: Distance ───────────────────────────────────────────

    @staticmethod
    def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
        """Euclidean distance between two points."""
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # ── Helper: Move Toward (delegates to NPCSystem) ───────────────

    def _move_toward(self, npc: NPC, target_x: float, target_y: float, dt: float) -> None:
        """
        Move an NPC toward a target position.

        Delegates to NPCSystem._move_toward() for consistency with
        all other NPC movement in the game.

        Args:
            npc: The NPC to move.
            target_x: Target X coordinate.
            target_y: Target Y coordinate.
            dt: Delta time in seconds.
        """
        dx = target_x - npc.world_x
        dy = target_y - npc.world_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            # Get speed from NPCSystem (behavior-aware)
            speed = self.game.npc_system._get_npc_speed(npc)
            move_x = (dx / dist) * speed * dt
            move_y = (dy / dist) * speed * dt
            npc.world_x += move_x
            npc.world_y += move_y

    # ── Helper: Patrol Waypoint ────────────────────────────────────

    def _get_patrol_waypoint(self, base_x: float, base_y: float,
                             radius: float) -> Tuple[float, float]:
        """
        Get a random patrol waypoint within `radius` of the base center.

        Uses a simple polar coordinate approach for a circular patrol area.

        Args:
            base_x: Base center X.
            base_y: Base center Y.
            radius: Patrol radius in pixels.

        Returns:
            (waypoint_x, waypoint_y) in world coordinates.
        """
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, radius)
        return (
            base_x + math.cos(angle) * r,
            base_y + math.sin(angle) * r,
        )

    # ── Guard Patrol Center ────────────────────────────────────────

    def _get_guard_patrol_center(self, npc: NPC) -> Tuple[float, float]:
        """
        Get the patrol center for a guard NPC.

        Priority:
        1. Assigned guard post structure position (if has building_system reference)
        2. base_x/base_y (spawn position, fallback)

        Returns:
            (patrol_center_x, patrol_center_y) in world coordinates.
        """
        if self._building_system is not None:
            structure = self._building_system.get_assigned_structure(npc.npc_id)
            if structure is not None and structure.is_active:
                return (structure.world_x, structure.world_y)
        if self.base_x is not None and self.base_y is not None:
            return (self.base_x, self.base_y)
        return (0.0, 0.0)  # Ultimate fallback

    # ── Guard Behavior ─────────────────────────────────────────────

    def _guard_behavior(self, npc: NPC, state: dict, dt: float) -> None:
        """
        Guard NPC behavior loop.

        States:
            "patrol" -> Patrol base perimeter, look for threats
            "combat" -> Chase and attack nearest hostile monster
            "returning" -> Return to base after combat ends

        Args:
            npc: The guard NPC.
            state: Behavior state dict for this NPC.
            dt: Delta time in seconds.
        """
        patrol_center_x, patrol_center_y = self._get_guard_patrol_center(npc)
        if patrol_center_x == 0.0 and patrol_center_y == 0.0:
            return

        substate = state.get("substate", "patrol")
        combat_target = state.get("combat_target")

        # ── Substate: patrol ──────────────────────────────────────
        if substate == "patrol":
            target = state.get("target")
            if isinstance(target, (list, tuple)):
                target_x, target_y = target[0], target[1]
            else:
                target_x = patrol_center_x
                target_y = patrol_center_y

            # If no current target, pick a new patrol waypoint
            if "target" not in state:
                px, py = self._get_patrol_waypoint(
                    patrol_center_x, patrol_center_y, self.GUARD_PATROL_RADIUS,
                )
                state["target"] = (px, py)
                target_x, target_y = px, py

            # Check for hostile monsters in guard range
            nearby_hostiles = self._get_guard_threats(npc)

            if nearby_hostiles:
                # Transition to combat
                nearest = min(nearby_hostiles,
                              key=lambda m: self._distance(npc.world_x, npc.world_y,
                                                           m.world_x, m.world_y))
                substate = "combat"
                state["substate"] = substate
                state["combat_target"] = nearest.monster_id
                combat_target = nearest

                # Check if we can already attack
                dist_to_monster = self._distance(
                    npc.world_x, npc.world_y, nearest.world_x, nearest.world_y,
                )
                if dist_to_monster <= self.GUARD_COMBAT_MELEE:
                    self._guard_attack(npc, nearest)
                else:
                    # Move toward monster
                    self._move_toward(npc, nearest.world_x, nearest.world_y, dt)
            else:
                # No threats -- move toward patrol waypoint
                self._move_toward(npc, target_x, target_y, dt)

                # Check if we've reached waypoint (2px tolerance)
                reached = self._distance(npc.world_x, npc.world_y, target_x, target_y) < 2.0
                if reached:
                    del state["target"]  # Clear so a new waypoint is picked next tick

        # ── Substate: combat ──────────────────────────────────────
        elif substate == "combat":
            # Retreat if critically wounded (only during combat, not patrol)
            if npc.health > 0 and npc.max_health > 0:
                hp_ratio = npc.health / npc.max_health
                if hp_ratio < self.GUARD_RETREAT_HP_THRESHOLD:
                    substate = "returning"
                    state["substate"] = substate
                    state["combat_target"] = None
                    combat_target = None

            if combat_target is not None:
                monster = self._find_monster_by_id(combat_target)
                if monster is None or not monster.is_alive():
                    # Target dead -- transition to returning
                    substate = "returning"
                    state["substate"] = substate
                    state["combat_target"] = None
                    combat_target = None
                else:
                    dist_to_monster = self._distance(
                        npc.world_x, npc.world_y, monster.world_x, monster.world_y,
                    )
                    if dist_to_monster <= self.GUARD_COMBAT_MELEE:
                        # Attack
                        self._guard_attack(npc, monster)
                    else:
                        # Chase
                        self._move_toward(npc, monster.world_x, monster.world_y, dt)
            else:
                # No combat target -- transition to returning
                substate = "returning"
                state["substate"] = substate

        # ── Substate: returning ───────────────────────────────────
        elif substate == "returning":
            self._move_toward(npc, patrol_center_x, patrol_center_y, dt)

            # Check if back at base
            dist_to_base = self._distance(
                npc.world_x, npc.world_y, patrol_center_x, patrol_center_y,
            )
            if dist_to_base < self.GUARD_RETURN_RADIUS:
                substate = "patrol"
                state["substate"] = substate
                state["combat_target"] = None
                combat_target = None

    def _get_guard_threats(self, npc: NPC) -> List["Monster"]:
        """
        Get hostile monsters within guard range of the NPC.

        Filters to monsters that are alive and hostile.

        Args:
            npc: The guard NPC.

        Returns:
            List of hostile Monster objects within GUARD_COMBAT_RANGE.
        """
        if self.game.combat_system is None:
            return []

        nearby = self.game.combat_system.get_nearby_monsters(
            npc.world_x, npc.world_y, self.GUARD_COMBAT_RANGE,
        )
        # Filter: alive and hostile
        return [m for m in nearby if m.is_alive() and m.is_hostile]

    def _find_monster_by_id(self, monster_id: str) -> Optional["Monster"]:
        """Find a monster by its monster_id in the combat system."""
        if self.game.combat_system is None:
            return None
        for monster in self.game.combat_system.monsters:
            if monster.monster_id == monster_id:
                return monster
        return None

    def _guard_attack(self, npc: NPC, monster: "Monster") -> None:
        """
        Execute a guard attack on a monster.

        Uses CombatSystem.npc_attack() for damage calculation and
        applies damage numbers for visual feedback.

        Args:
            npc: The attacking guard NPC.
            monster: The target monster.
        """
        if self.game.combat_system is None:
            return

        damage = self.game.combat_system.npc_attack(npc, monster)
        # Damage number and XP are handled by CombatSystem.npc_attack() — no duplicates

        # Check for monster counter-attack
        if monster.attack_cooldown_timer <= 0:
            monster_attack = monster.attack * 0.5  # 50% of monster attack
            npc_defence = npc.get_npc_defence()
            defence_reduction = npc_defence * 0.01
            counter_damage = max(1, int(monster_attack * (1 - defence_reduction)))
            self.game.combat_system.npc_take_damage(npc, counter_damage)
            monster.attack_cooldown_timer = monster.attack_cooldown

    # ── Trader Behavior ────────────────────────────────────────────

    def _trader_behavior(self, npc: NPC, state: dict, dt: float) -> None:
        """
        Trader NPC behavior loop.

        States:
            "idle" -> Waiting for trade cooldown, then find merchant
            "traveling_to_merchant" -> Move to nearest merchant
            "trading" -> Execute trade at merchant
            "traveling_to_base" -> Return to base with purchased items

        Args:
            npc: The trader NPC.
            state: Behavior state dict for this NPC.
            dt: Delta time in seconds.
        """
        if self.base_x is None or self.base_y is None:
            return

        substate = state.get("substate", "idle")
        trade_timer = state.get("trade_timer", 0.0)

        # ── Substate: idle (wait for trade cooldown) ──────────────
        if substate == "idle":
            trade_timer += dt
            state["trade_timer"] = trade_timer

            if trade_timer >= self.TRADER_TRADE_INTERVAL:
                # Find nearest merchant
                merchant = self._find_nearest_merchant(npc)
                if merchant is not None:
                    trade_timer = 0.0
                    state["trade_timer"] = trade_timer
                    substate = "traveling_to_merchant"
                    state["substate"] = substate
                    state["target_merchant_id"] = merchant.npc_id

        # ── Substate: traveling to merchant ───────────────────────
        elif substate == "traveling_to_merchant":
            target_merchant_id = state.get("target_merchant_id")
            target_merchant = None
            if self.game.npc_system is not None:
                for n in self.game.npc_system.npcs:
                    if n.npc_id == target_merchant_id:
                        target_merchant = n
                        break

            if target_merchant is None:
                # Merchant disappeared -- reset to idle
                substate = "idle"
                state["substate"] = substate
                if "target_merchant_id" in state:
                    del state["target_merchant_id"]
            else:
                dist = self._distance(
                    npc.world_x, npc.world_y,
                    target_merchant.world_x, target_merchant.world_y,
                )
                if dist <= self.TRADER_TRADE_RANGE:
                    # Arrived at merchant -- execute trade
                    self._trader_execute_trade(npc, target_merchant)
                    substate = "traveling_to_base"
                    state["substate"] = substate
                else:
                    # Move toward merchant
                    self._move_toward(npc, target_merchant.world_x, target_merchant.world_y, dt)

        # ── Substate: traveling to base ───────────────────────────
        elif substate == "traveling_to_base":
            self._move_toward(npc, self.base_x, self.base_y, dt)

            # Check if back at base
            dist_to_base = self._distance(
                npc.world_x, npc.world_y, self.base_x, self.base_y,
            )
            if dist_to_base < self.TRADER_RETURN_RADIUS:
                substate = "idle"
                state["substate"] = substate

    def _find_nearest_merchant(self, npc: NPC) -> Optional[NPC]:
        """
        Find the nearest merchant NPC to the given recruit.

        Searches all NPCs in NPCSystem for type "merchant".

        Args:
            npc: The trader NPC to find a merchant from.

        Returns:
            Nearest merchant NPC, or None.
        """
        if self.game.npc_system is None:
            return None

        from npc.npc_types import MerchantNPC

        best_merchant = None
        best_dist = float("inf")

        for other_npc in self.game.npc_system.npcs:
            if not isinstance(other_npc, MerchantNPC):
                continue
            if other_npc.npc_id == npc.npc_id:
                continue  # Don't trade with yourself

            dist = self._distance(
                npc.world_x, npc.world_y,
                other_npc.world_x, other_npc.world_y,
            )
            if dist < best_dist:
                best_dist = dist
                best_merchant = other_npc

        return best_merchant if best_merchant is not None else None

    def _trader_execute_trade(self, trader_npc: NPC, merchant: NPC) -> None:
        """
        Execute a trade: buy one item from the merchant using player gold.

        Selects the cheapest available item from the merchant's inventory
        that the player doesn't already have excess of.

        Args:
            trader_npc: The trader NPC executing the trade.
            merchant: The merchant NPC to buy from.
        """
        from npc.npc_types import MerchantNPC

        if self.game.trade_system is None:
            return

        if not isinstance(merchant, MerchantNPC):
            return

        # Check if a trade session is already active (avoid conflict with UI trading)
        if self.game.trade_system.active_session is not None and \
           self.game.trade_system.active_session.is_active:
            return

        # Check if merchant has any stock
        if not merchant.inventory:
            return

        # Find an item to buy: prefer items with stock > 0
        items_to_buy = [
            item for item in merchant.inventory
            if item.stock_quantity > 0
        ]

        if not items_to_buy:
            return

        # Buy the cheapest item (by buy_price)
        items_to_buy.sort(key=lambda item: item.buy_price)
        target_item = items_to_buy[0]

        # Open a trade session for the trader
        if self.game.player is None:
            return

        session = self.game.trade_system.open_trade(self.game.player, merchant)
        if session is None:
            return  # Cannot open trade

        # Execute buy
        result = self.game.trade_system.execute_buy(
            target_item.trade_item_id, 1,  # Buy 1 unit
        )

        if result.success and result.item_id not in (None, ""):
            if hasattr(self.game.player, "action_system") and self.game.player.action_system:
                self.game.player.action_system.add_notification(
                    f"{trader_npc.name} traded 1x {target_item.item_id} for {result.gold_changed} gold.",
                    (100, 255, 100),
                )
        else:
            # Not enough gold or no stock -- just log it
            if hasattr(self.game.player, "action_system") and self.game.player.action_system:
                self.game.player.action_system.add_notification(
                    result.message, (255, 200, 50),
                )

        # Close the trade session
        self.game.trade_system.close_trade()

    # ── Assistant Behavior ─────────────────────────────────────────

    def _assistant_behavior(self, npc: NPC, state: dict, dt: float) -> None:
        """
        Assistant NPC behavior loop.

        States:
            "following" -> Follow player at ASSISTANT_FOLLOW_DISTANCE
            "gathering" -> Gather from nearby resource node
            "healing" -> Offer healing item to player

        Args:
            npc: The assistant NPC.
            state: Behavior state dict for this NPC.
            dt: Delta time in seconds.
        """
        if self.game.player is None:
            return

        player = self.game.player
        substate = state.get("substate", "following")
        follow_timer = state.get("follow_timer", 0.0)
        heal_timer = state.get("heal_timer", 0.0)

        # ── Substate: following ───────────────────────────────────
        if substate == "following":
            # Follow player at moderate distance
            dist_to_player = self._distance(
                npc.world_x, npc.world_y,
                player.world_x, player.world_y,
            )

            if dist_to_player > self.ASSISTANT_FOLLOW_DISTANCE:
                # Move toward player
                self._move_toward(npc, player.world_x, player.world_y, dt)
            else:
                # Within follow distance -- check for resources
                follow_timer += dt
                if follow_timer >= 2.0:  # Check resources every 2 seconds
                    follow_timer = 0.0
                    state["follow_timer"] = follow_timer

                    # Find nearby resources
                    resources = self._find_nearby_resources(
                        player.world_x, player.world_y,
                        self.ASSISTANT_GATHER_RANGE,
                    )
                    if resources:
                        # Try to gather from the nearest one
                        self._assistant_gather(npc, resources[0])
                        state["substate"] = "gathering"
                        substate = "gathering"

            # Check for healing opportunity
            heal_timer += dt
            if heal_timer >= self.ASSISTANT_HEAL_INTERVAL:
                heal_timer = 0.0
                state["heal_timer"] = heal_timer

                if player.action_system is not None and player.action_system.survival is not None:
                    survival = player.action_system.survival
                    if survival.hp < survival.max_hp * self.ASSISTANT_HEAL_THRESHOLD:
                        if self._assistant_has_healing_item(npc):
                            self._assistant_heal_player(npc)
                            state["substate"] = "healing"
                            substate = "healing"

        # ── Substate: gathering ───────────────────────────────────
        elif substate == "gathering":
            # After gathering, return to following
            state["substate"] = "following"
            substate = "following"

        # ── Substate: healing ─────────────────────────────────────
        elif substate == "healing":
            # After healing, return to following
            state["substate"] = "following"
            substate = "following"

    def _find_nearby_resources(
        self, world_x: float, world_y: float, radius: float,
    ) -> List["ResourceNode"]:
        """
        Find resource nodes near a world position.

        Searches the tile grid for non-depleted resource nodes within range.

        Args:
            world_x: Center X coordinate.
            world_y: Center Y coordinate.
            radius: Search radius in pixels.

        Returns:
            List of ResourceNode objects within range, sorted by distance.
        """
        if self.game.world is None:
            return []

        tx, ty = int(world_x // 64), int(world_y // 64)
        search_radius_tiles = int(radius // 64) + 2
        tile_size = 64

        best: List[tuple[float, "ResourceNode"]] = []

        for dx in range(-search_radius_tiles, search_radius_tiles + 1):
            for dy in range(-search_radius_tiles, search_radius_tiles + 1):
                nx, ny = tx + dx, ty + dy
                tile = self.game.world.get_tile(nx, ny)
                if tile is None:
                    continue
                node = tile.resource_node
                if node is None:
                    continue
                if node.is_depleted and node.regrow_time <= 0:
                    continue

                node_x = nx * tile_size + tile_size // 2
                node_y = ny * tile_size + tile_size // 2
                dist = math.sqrt((node_x - world_x) ** 2 + (node_y - world_y) ** 2)
                if dist <= radius:
                    best.append((dist, node))

        best.sort(key=lambda x: x[0])
        return [node for _, node in best]

    def _assistant_gather(self, npc: NPC, resource: "ResourceNode") -> None:
        """
        Assistant attempts to gather from a resource node.

        Simplified gathering: 80% success rate, no tool/stamina check.
        Yields directly into player.inventory.

        Args:
            npc: The assistant NPC attempting the gather.
            resource: The ResourceNode to harvest.
        """
        # 80% success rate
        if random.random() > 0.80:
            if hasattr(self.game.player, "action_system") and self.game.player.action_system:
                self.game.player.action_system.add_notification(
                    f"Assistant failed to gather from {resource.resource_id}.",
                    (255, 200, 50),
                )
            return

        # Harvest the resource
        if not resource.harvest():
            return  # Resource is depleted

        # Add yield to player inventory
        if self.game.inventory is not None:
            success = self.game.inventory.add_item(resource.yield_item, 1)
            if success:
                if hasattr(self.game.player, "action_system") and self.game.player.action_system:
                    self.game.player.action_system.add_notification(
                        f"Assistant gathered 1x {resource.yield_item}!",
                        (100, 255, 100),
                    )
            else:
                if hasattr(self.game.player, "action_system") and self.game.player.action_system:
                    self.game.player.action_system.add_notification(
                        "Assistant's gather failed -- inventory full.",
                        (255, 100, 100),
                    )

    def _assistant_has_healing_item(self, npc: NPC) -> bool:
        """
        Check if the assistant NPC has a healing item available.

        Checks the player's inventory for healing items that the assistant
        can "carry" (we use a simplified model: assistant has access to
        player's healing items when needed).

        Healing items: herb, healing_herbs, berries, water (items with
        hp_restore > 0 in the food registry).

        Returns:
            True if a healing item is available.
        """
        if self.game.inventory is None:
            return False

        # Check for known healing items
        healing_items = ["herb", "healing_herbs", "berries", "water"]
        for item_id in healing_items:
            if self.game.inventory.has_items(item_id, 1):
                return True
        return False

    def _assistant_heal_player(self, npc: NPC) -> None:
        """
        Assistant offers a healing item to the player.

        Uses the first available healing item from the player's inventory.
        Applies healing through the SurvivalSystem.

        Args:
            npc: The assistant NPC offering healing.
        """
        if (
            self.game.player is None
            or self.game.player.action_system is None
            or self.game.player.action_system.survival is None
        ):
            return

        survival = self.game.player.action_system.survival
        inventory = self.game.inventory

        # Determine the healing item to use
        healing_items = ["herb", "healing_herbs", "berries", "water"]
        used_item = None
        for item_id in healing_items:
            if inventory.has_items(item_id, 1):
                used_item = item_id
                break

        if used_item is None:
            return

        # Heal the player
        survival.heal(self.ASSISTANT_HEAL_AMOUNT)
        inventory.remove_item(used_item, 1)
        if hasattr(self.game.player, "action_system") and self.game.player.action_system:
            self.game.player.action_system.add_notification(
                f"Assistant used {used_item} to heal you for {self.ASSISTANT_HEAL_AMOUNT:.0f} HP!",
                (100, 255, 100),
            )

    # ── Slot Management ────────────────────────────────────────────

    def get_max_recruits(self) -> int:
        """
        Return the maximum number of NPCs the player can recruit.

        Formula: max(1, intelligence_level // 5 + 1).

        Returns:
            Maximum recruit count.
        """
        return self.intelligence_skill.get_max_recruits()

    def get_used_slots(self) -> int:
        """
        Return the number of currently used recruit slots.

        Returns:
            Number of recruited NPCs.
        """
        if self.game.player is None:
            return 0
        return len(self.game.player.recruited_npcs)

    def get_available_slots(self) -> int:
        """
        Return the number of available recruit slots.

        Returns:
            Available slots (0 if full).
        """
        return max(0, self.get_max_recruits() - self.get_used_slots())

    def is_slot_available(self) -> bool:
        """
        Check if the player can recruit more NPCs.

        Returns:
            True if there are available slots.
        """
        return self.get_available_slots() > 0

    # ── Recruitment Integration ────────────────────────────────────

    def on_recruit(self, npc_id: str, behavior: str) -> None:
        """
        Called when a new NPC is recruited.

        Initializes the behavior state for this recruit and ensures
        the base position is set.

        Args:
            npc_id: The NPC's unique identifier.
            behavior: The assigned behavior ("guard", "trader", "assistant").
        """
        # Ensure base position is set
        if self.base_x is None and self.game.world is not None:
            self.base_x = self.game.world.spawn_x * 64 + 32
            self.base_y = self.game.world.spawn_y * 64 + 32

        # Initialize behavior state with patrol center (for guards)
        if behavior == "guard":
            patrol_center_x, patrol_center_y = self._get_guard_patrol_center(
                self._find_npc(npc_id),
            )
            initial_target = (patrol_center_x, patrol_center_y)
        else:
            initial_target = (self.base_x, self.base_y)

        self.behaviors[npc_id] = {
            "target": initial_target,
            "substate": "patrol" if behavior == "guard" else "idle" if behavior == "trader" else "following",
            "combat_target": None,
            "trade_timer": 0.0,
            "trade_cooldown": self.TRADER_TRADE_INTERVAL,
            "follow_timer": 0.0,
            "heal_timer": 0.0,
        }

    def on_dismiss(self, npc_id: str) -> None:
        """
        Called when a recruit is dismissed.

        Cleans up the behavior state for this NPC and unassigns
        any structure assignment.

        Args:
            npc_id: The NPC's unique identifier.
        """
        if npc_id in self.behaviors:
            del self.behaviors[npc_id]
        # Unassign from any structure
        if self._building_system is not None:
            self._building_system.unassign_npc(npc_id)

    def get_recruit_list(self) -> List[NPC]:
        """
        Return all currently recruited NPCs.

        Returns:
            List of NPC objects that are recruited.
        """
        result = []
        if self.game.npc_system is None:
            return result
        for npc in self.game.npc_system.npcs:
            if npc.is_recruited:
                result.append(npc)
        return result
