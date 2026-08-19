"""
npc/faction_system.py — Faction Standing / Reputation System.

Manages player faction relationships as float values (0.0–1.0).
Tracks standing per faction, maps to status labels, and provides
monster-to-faction lookup for combat integration.

This is the **central authority** for faction standing — no other
system stores or mutates standing values directly.

Fields:
    _faction_data: Parsed factions.json dict (factions -> hostile_monster_types).
    _standing: faction_id -> float (0.0-1.0) standing map.
    _monsters_to_factions: monster_id -> faction_id reverse lookup map.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import math
    from npc.npc import NPC
    from combat.monster import Monster


# Standing thresholds (must match ui/diplomacy_panel.py constants)
_STANDING_HOSTILE_MAX = 0.2
_STANDING_SUSPICIOUS_MAX = 0.4
_STANDING_NEUTRAL_MAX = 0.6
_STANDING_FRIENDLY_MAX = 0.8

# HUD faction status bar color map (class-level for method access)
class _BarColorLookup:
    HOSTILE = (255, 50, 50)
    SUSPICIOUS = (255, 165, 0)
    NEUTRAL = (255, 255, 100)
    FRIENDLY = (100, 255, 100)
    ALLIED = (50, 255, 50)


class FactionSystem:
    """
    Central authority for player faction standing/reputation.

    Manages standing values per faction (float 0.0-1.0), maps to
    status labels, and provides monster-to-faction lookup for combat integration.

    Default standing for unknown factions: neutral (0.5).
    """

    # Faction NPC behavior constants
    FACTION_COMBAT_RANGE: float = 150.0      # px to detect hostile monsters
    FACTION_COMBAT_MELEE: float = 40.0       # px melee range for attacking
    FACTION_AGGRESSION_RANGE: float = 150.0  # px to detect player for aggression
    FACTION_ASSIST_RANGE: float = 150.0      # px to assist player against hostiles
    FACTION_NPC_COOLDOWN: float = 2.0        # seconds between faction NPC attacks

    __slots__ = (
        "_faction_data",
        "_standing",
        "_monsters_to_factions",
        "_faction_ids",
        "_faction_npc_cooldowns",
        "_faction_npc_movement",
        "game",
    )

    def __init__(self, faction_data: dict) -> None:
        """
        Initialize from factions.json parsed data.

        Args:
            faction_data: Dict with "factions" key containing list of faction dicts
                          (from data/factions.json).
        """
        self._faction_data: dict = {}
        self._standing: Dict[str, float] = {}
        self._monsters_to_factions: Dict[str, str] = {}
        self._faction_ids: List[str] = []

        for faction in faction_data.get("factions", []):
            fid = faction["faction_id"]
            self._faction_data[fid] = faction
            self._faction_ids.append(fid)
            # Initialize to neutral
            self._standing[fid] = 0.5

            # Build monster->faction reverse map
            for monster_type in faction.get("hostile_monster_types", []):
                self._monsters_to_factions[monster_type] = fid

        # Faction NPC behavior state
        self._faction_npc_cooldowns: Dict[str, float] = {}  # npc_id → remaining cooldown
        self._faction_npc_movement: Dict[str, Tuple[float, float]] = {}  # npc_id → (target_x, target_y)

        # Game reference for behavior system
        self.game: object = None  # Reference to Game instance (set by Game._initialize_subsystems)

    # --- Query methods ---

    def get_standing(self, faction_id: str) -> float:
        """Get standing for a faction. Unknown factions return neutral (0.5)."""
        return self._standing.get(faction_id, 0.5)

    def update_standing(self, faction_id: str, delta: float) -> None:
        """Update standing for a faction. Clamped to [0.0, 1.0]."""
        if faction_id not in self._standing:
            self._standing[faction_id] = 0.5
        self._standing[faction_id] = max(0.0, min(1.0, self._standing[faction_id] + delta))

    def get_status(self, faction_id: str) -> str:
        """Get the status label for a faction's standing."""
        return self._standing_to_status(self.get_standing(faction_id))

    def _standing_to_status(self, standing: float) -> str:
        """Convert a standing float to a status label string."""
        if standing >= 0.8:
            return "allied"
        elif standing >= 0.6:
            return "friendly"
        elif standing >= 0.4:
            return "neutral"
        elif standing >= 0.2:
            return "suspicious"
        else:
            return "hostile"

    def get_faction_for_monster(self, monster_id: str) -> Optional[str]:
        """Get the faction associated with a monster type. Returns None if not associated."""
        return self._monsters_to_factions.get(monster_id)

    def get_all_faction_ids(self) -> list[str]:
        """Return all known faction IDs."""
        return list(self._faction_ids)

    def get_faction_data(self, faction_id: str) -> Optional[dict]:
        """Get the raw faction data dict for a faction."""
        return self._faction_data.get(faction_id)

    def get_best_faction_status(self) -> tuple:
        """
        Return the player's best faction status across all factions.
        Returns (status_label, faction_name, standing).
        """
        best_status = None
        best_standing = 0.0
        best_name = "None"
        status_order = {"allied": 4, "friendly": 3, "neutral": 2, "suspicious": 1, "hostile": 0}
        for fid in self._faction_ids:
            standing = self.get_standing(fid)
            status = self._standing_to_status(standing)
            if best_status is None or status_order.get(status, 0) > status_order.get(best_status, 0):
                best_status = status
                best_standing = standing
                best_name = self._faction_data.get(fid, {}).get("name", fid)
        if best_status is None:
            return "neutral", "None", 0.5
        return best_status, best_name, best_standing

    def get_faction_color(self, status: str) -> tuple:
        """Get the RGB color for a faction status."""
        color_map = {
            "hostile": _BarColorLookup.HOSTILE,
            "suspicious": _BarColorLookup.SUSPICIOUS,
            "neutral": _BarColorLookup.NEUTRAL,
            "friendly": _BarColorLookup.FRIENDLY,
            "allied": _BarColorLookup.ALLIED,
        }
        return color_map.get(status, (200, 200, 200))

    # --- Serialization ---

    def get_snapshot(self) -> Dict[str, float]:
        """Return a serializable dict of faction_id -> standing."""
        return dict(self._standing)

    def load_snapshot(self, snapshot: Dict[str, float]) -> None:
        """Restore standing from a save snapshot."""
        for fid, standing in snapshot.items():
            self._standing[fid] = max(0.0, min(1.0, standing))

    # ── Faction NPC Behavior ──────────────────────────────────────

    @staticmethod
    def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
        """Euclidean distance between two points."""
        import math
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def update_faction_npc_behavior(self, dt: float) -> None:
        """
        Main behavior tick for faction NPCs. Called from Game.update()
        via NPCSystem.tick_faction_npcs().

        For each non-recruited faction NPC:
        1. Hunt monsters matching this faction's hostile_monster_types
        2. Check player standing → attack player if hostile, assist if allied
        3. Move toward targets (monsters or player)

        Args:
            dt: Delta time in seconds.
        """
        if self.game is None or self.game.combat_system is None:
            return

        # Get all faction leader NPCs from NPCSystem
        if self.game.npc_system is None:
            return

        for npc in self.game.npc_system.npcs:
            if not npc.is_active:
                continue
            if npc.npc_type != "faction_leader":
                continue
            if getattr(npc, 'is_recruited', False):
                continue  # Recruited NPCs handled by RecruitmentSystem

            # Track movement target for this NPC
            npc_id = getattr(npc, 'npc_id', str(npc.world_x))
            movement_target = self._faction_npc_movement.get(npc_id)

            # Check for hostile monsters to hunt
            hostile_monsters = self.get_hostile_monsters(npc)
            if hostile_monsters:
                nearest = min(hostile_monsters,
                              key=lambda m: self._distance(npc.world_x, npc.world_y,
                                                           m.world_x, m.world_y))
                dist = self._distance(npc.world_x, npc.world_y,
                                      nearest.world_x, nearest.world_y)

                if dist <= self.FACTION_COMBAT_MELEE:
                    # Attack if in melee range and not on cooldown
                    if self._faction_npc_cooldowns.get(npc_id, 0) <= 0:
                        self.faction_npc_attack(npc, nearest)
                else:
                    # Chase the monster
                    self._faction_npc_movement[npc_id] = (nearest.world_x, nearest.world_y)
                continue

            # Check player hostility
            if self.is_player_hostile_to_faction(npc):
                player = self.game.player
                if player is not None:
                    dist = self._distance(npc.world_x, npc.world_y,
                                          player.world_x, player.world_y)
                    if dist <= self.FACTION_AGGRESSION_RANGE:
                        if self._faction_npc_cooldowns.get(npc_id, 0) <= 0:
                            # Attack player (apply through SurvivalSystem)
                            self._attack_player(npc, player)
                        else:
                            # Chase player
                            self._faction_npc_movement[npc_id] = (player.world_x, player.world_y)
                        continue

            # Check if allied — assist player against any hostile monster
            if self.is_player_allied_to_faction(npc):
                player = self.game.player
                if player is not None:
                    nearby_hostiles = self.game.combat_system.get_nearby_monsters(
                        player.world_x, player.world_y, self.FACTION_ASSIST_RANGE,
                    )
                    nearby_hostiles = [m for m in nearby_hostiles
                                       if m.is_alive() and m.is_hostile]
                    if nearby_hostiles:
                        nearest = min(nearby_hostiles,
                                      key=lambda m: self._distance(npc.world_x, npc.world_y,
                                                                    m.world_x, m.world_y))
                        dist = self._distance(npc.world_x, npc.world_y,
                                              nearest.world_x, nearest.world_y)
                        if dist <= self.FACTION_COMBAT_MELEE:
                            if self._faction_npc_cooldowns.get(npc_id, 0) <= 0:
                                self.faction_npc_attack(npc, nearest)
                        else:
                            self._faction_npc_movement[npc_id] = (nearest.world_x, nearest.world_y)
                        continue

            # No threats — clear movement target (return to patrol via NPCSystem.tick())
            if npc_id in self._faction_npc_movement:
                del self._faction_npc_movement[npc_id]

        # Clean up cooldowns
        self._clean_cooldowns(dt)

    def get_hostile_monsters(self, npc: "NPC") -> List["Monster"]:
        """
        Find monsters matching this faction NPC's hostile_monster_types
        within combat range.

        Args:
            npc: The faction NPC.

        Returns:
            List of hostile Monster objects within FACTION_COMBAT_RANGE.
        """
        if self.game is None or self.game.combat_system is None:
            return []

        # Get the faction data to find hostile monster types
        faction_id = getattr(npc, 'faction', None)
        if faction_id is None:
            return []

        faction_data = self._faction_data.get(faction_id)
        if faction_data is None:
            return []

        hostile_types = faction_data.get("hostile_monster_types", [])
        if not hostile_types:
            return []  # This faction has no hostile monster types

        # Find all monsters in range
        nearby = self.game.combat_system.get_nearby_monsters(
            npc.world_x, npc.world_y, self.FACTION_COMBAT_RANGE,
        )

        # Filter: alive and matches hostile_monster_types
        return [m for m in nearby if m.is_alive()
                and getattr(m, 'monster_id', None) in hostile_types]

    def is_player_hostile_to_faction(self, npc: "NPC") -> bool:
        """
        Check if the player has hostile standing with this NPC's faction.

        Args:
            npc: The faction NPC to check.

        Returns:
            True if player standing < hostile threshold (0.2).
        """
        faction_id = getattr(npc, 'faction', None)
        if faction_id is None:
            return False
        return self.get_status(faction_id) == "hostile"

    def is_player_allied_to_faction(self, npc: "NPC") -> bool:
        """
        Check if the player has allied standing with this NPC's faction.

        Args:
            npc: The faction NPC to check.

        Returns:
            True if player standing >= allied threshold (0.8).
        """
        faction_id = getattr(npc, 'faction', None)
        if faction_id is None:
            return False
        return self.get_status(faction_id) == "allied"

    def faction_npc_attack(self, npc: "NPC", monster: "Monster") -> int:
        """
        Execute a faction NPC attack on a monster.

        Uses faction_strength-based attack calculation. Spawns faction-colored
        damage number. Sets per-NPC cooldown.

        Args:
            npc: The attacking faction NPC.
            monster: The target Monster.

        Returns:
            Damage dealt (0 if on cooldown or target dead).
        """
        if not monster.is_alive():
            return 0

        npc_id = getattr(npc, 'npc_id', str(npc.world_x))

        # Check per-NPC cooldown
        if self._faction_npc_cooldowns.get(npc_id, 0) > 0:
            return 0

        # Calculate faction attack (faction_strength-based)
        faction_strength = getattr(npc, 'faction_strength', 1.0)
        faction_attack = 3 + int(faction_strength * 10)
        attack_mult = 1.0 + faction_attack * 0.005
        monster_defence = monster.defence
        defence_reduction = monster_defence * 0.01
        raw_damage = faction_attack * attack_mult
        damage = max(1, int(raw_damage * (1 - defence_reduction)))

        # Apply damage
        monster.take_damage(damage)

        # Spawn faction-colored damage number (cyan)
        if self.game is not None and self.game.combat_system is not None:
            from combat.combat_system import DamageNumber
            self.game.combat_system.damage_numbers.append(DamageNumber(
                value=damage,
                world_x=monster.world_x,
                world_y=monster.world_y - 10,
                timer=2.0,
                color=(50, 200, 255),  # Cyan — faction NPC attack color
            ))

        # Grant player XP for faction-assisted combat
        if self.game is not None and self.game.player is not None:
            if hasattr(self.game.player, 'skill_manager') and self.game.player.skill_manager:
                self.game.player.skill_manager.add_xp("combat", 1.0)

        # Check monster death
        if not monster.is_alive() and self.game is not None:
            cs = getattr(self.game, 'combat_system', None)
            if cs is not None:
                cs._monster_died(monster)

        # Set cooldown (2.0s for faction NPCs)
        self._faction_npc_cooldowns[npc_id] = 2.0

        return damage

    def _attack_player(self, npc: "NPC", player: object) -> None:
        """
        Faction NPC attacks the player.

        Applies damage through SurvivalSystem. Spawns yellow damage number.
        Sets per-NPC cooldown.

        Args:
            npc: The attacking faction NPC.
            player: The player being attacked.
        """
        if self.game is None or self.game.player is None:
            return

        npc_id = getattr(npc, 'npc_id', str(npc.world_x))

        # Calculate attack (same as faction_npc_attack formula)
        faction_strength = getattr(npc, 'faction_strength', 1.0)
        faction_attack = 3 + int(faction_strength * 10)

        # Player defence reduces incoming damage
        player_defence = 0
        if hasattr(player, 'gear') and player.gear is not None:
            from combat.gear import PlayerGear
            if isinstance(player.gear, PlayerGear):
                player_defence = player.gear.get_defence_bonus()
        if hasattr(player, 'skill_manager') and player.skill_manager is not None:
            player_defence += player.skill_manager.get_effective_stat("combat", "defence")

        defence_reduction = player_defence * 0.01
        raw_damage = faction_attack * 0.5  # Faction NPCs weaker than player
        damage = max(1, int(raw_damage * (1 - defence_reduction)))

        # Apply damage through SurvivalSystem
        if hasattr(player, 'action_system') and player.action_system is not None:
            survival = getattr(player.action_system, 'survival', None)
            if survival is not None:
                survival.take_damage(damage)

        # Spawn yellow damage number (player taking damage)
        if self.game.combat_system is not None:
            from combat.combat_system import DamageNumber
            self.game.combat_system.damage_numbers.append(DamageNumber(
                value=-damage,
                world_x=player.world_x,
                world_y=player.world_y - 10,
                timer=2.0,
                color=(200, 200, 50),  # Yellow — player damage
            ))

        # Set cooldown
        self._faction_npc_cooldowns[npc_id] = 2.0

    def negotiate(self, player, faction_id: str) -> dict:
        """
        Attempt a negotiation with a faction.

        Persuasion check + relationship update.

        Args:
            player: The player entity.
            faction_id: The faction to negotiate with.

        Returns:
            Dict with 'success', 'message', 'new_standing', 'delta'.
        """
        persuasion = 0
        if player is not None and hasattr(player, "skill_manager") and player.skill_manager:
            persuasion = player.skill_manager.get_effective_stat("intelligence", "persuasion")

        current_standing = self.get_standing(faction_id)
        relation = current_standing  # 0.0-1.0

        # Base success chance
        base_success = 0.5
        persuasion_bonus = persuasion * 0.015
        relation_bonus = (relation - 0.5) * 0.3  # positive if friendly, negative if hostile
        variance = random.uniform(-0.15, 0.15)

        success_chance = base_success + persuasion_bonus + relation_bonus + variance
        success = success_chance >= 0.5

        if success:
            delta = 0.05 + persuasion * 0.005
            delta = min(delta, 0.2)  # cap per negotiation
            self.update_standing(faction_id, delta)
            new_standing = self.get_standing(faction_id)
            message = f"Negotiation successful! Standing improved to {new_standing:.2f}."
            return {
                "success": True,
                "message": message,
                "new_standing": new_standing,
                "delta": delta,
            }
        else:
            delta = -0.03
            self.update_standing(faction_id, delta)
            new_standing = self.get_standing(faction_id)
            message = f"Negotiation failed. Standing decreased to {new_standing:.2f}."
            return {
                "success": False,
                "message": message,
                "new_standing": new_standing,
                "delta": delta,
            }

    def _clean_cooldowns(self, dt: float) -> None:
        """
        Decrement faction NPC cooldowns and remove expired entries.

        Args:
            dt: Delta time in seconds.
        """
        for key in list(self._faction_npc_cooldowns.keys()):
            if self._faction_npc_cooldowns[key] > 0:
                self._faction_npc_cooldowns[key] -= dt
            else:
                del self._faction_npc_cooldowns[key]
