"""
combat/combat_system.py — Real-time combat engine.

Manages combat interactions, monster targeting, damage calculation,
attack cooldowns, and combat state. Integrates with SurvivalSystem
for player HP tracking and with SkillManager for stat lookups.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from config import (
    COMBAT_BASE_ATTACK_COOLDOWN,
    COMBAT_DAMAGE_NUMBER_RISE_RATE,
    COMBAT_SPEED_STAT_COOLDOWN_REDUCTION,
    DEATH_XP_PENALTY_FRACTION,
    DEATH_RESTORE_HP_FRACTION,
    DEATH_RESTORE_HUNGER_FRACTION,
)

if TYPE_CHECKING:
    from typing import Dict, List, Optional

    from core.player import Player
    from npc.npc import NPC
    from combat.monster import Monster


@dataclass
class AttackResult:
    """Result of a combat exchange between attacker and defender."""
    damage_dealt: int
    damage_taken: int
    monster_died: bool
    player_stunned: bool = False
    message: str = ""


@dataclass
class DamageNumber:
    """Floating damage text rendered during combat."""
    value: int
    world_x: float = 0.0
    world_y: float = 0.0
    timer: float = 2.0
    color: tuple = (255, 50, 50)
    offset_y: float = 0.0


class CombatSystem:
    """
    Real-time combat engine.

    Fields:
        player: Reference to the player entity.
        survival: Reference to the survival system for damage/death handling.
        monsters: List of active monsters on the map.
        selected_target: Currently targeted monster (None = no target).
        damage_numbers: Floating damage text for UI rendering.
        player_attack_cooldown: Timer until next player attack.
        combat_log: Recent combat events for UI display.
        _npc_attack_cooldowns: Per-NPC attack cooldown tracking.
    """

    __slots__ = (
        "player",
        "survival",
        "building_system",
        "firemaking",
        "game",
        "faction_system",
        "monsters",
        "selected_target",
        "damage_numbers",
        "player_attack_cooldown",
        "combat_log",
        "_npc_attack_cooldowns",
    )

    def __init__(
        self, player: Player, survival=None, building_system=None, firemaking=None,
        game=None, faction_system=None,
    ) -> None:
        self.player: Player = player
        self.survival = survival
        self.monsters: List[Monster] = []
        self.selected_target: Optional[Monster] = None
        self.damage_numbers: List[DamageNumber] = []
        self.player_attack_cooldown: float = 0.0
        self.combat_log: List[str] = []
        self.building_system = building_system
        self.firemaking = firemaking
        self.game = game
        self.faction_system = faction_system

        # Per-NPC attack cooldown tracking (guards and recruited NPCs)
        self._npc_attack_cooldowns: Dict[str, float] = {}  # npc_id → remaining cooldown

    # ── Targeting ───────────────────────────────────────────────────

    def select_target(self, monster: Monster) -> None:
        """
        Set the player's combat target.

        Args:
            monster: The monster to target.
        """
        self.selected_target = monster

    def deselect_target(self) -> None:
        """Clear the current combat target."""
        self.selected_target = None

    def get_nearby_monsters(self, world_x: float, world_y: float, radius: float) -> List[Monster]:
        """
        Find monsters within a radius of a world position.

        Args:
            world_x: X coordinate.
            world_y: Y coordinate.
            radius: Search radius in pixels.

        Returns:
            List of monsters within range.
        """
        import math
        result = []
        for monster in self.monsters:
            dx = monster.world_x - world_x
            dy = monster.world_y - world_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius:
                result.append(monster)
        return result

    # ── Damage Calculation ──────────────────────────────────────────

    def calculate_damage(self, attacker: Player, defender: Monster) -> int:
        """
        Calculate damage dealt by attacker to defender.

        Damage = max(1, floor(
            attacker_attack * weapon_damage * attack_multiplier
            * (1 - defender_defence_reduction)
        ))

        Args:
            attacker: The attacking entity (player).
            defender: The defending entity (monster).

        Returns:
            Calculated damage (minimum 1).
        """
        base_attack = self.player.skill_manager.get_effective_stat(
            "combat", "attack"
        )
        if self.player.gear:
            base_attack += self.player.gear.get_attack_bonus()
        weapon_damage = self._get_weapon_damage()
        attack_mult = 1.0 + base_attack * 0.005  # +0.5% per point

        # Monster defence reduces damage by 1% per point
        monster_defence = defender.defence
        defence_reduction = monster_defence * 0.01

        raw_damage = base_attack * weapon_damage * attack_mult
        damage = max(1, int(raw_damage * (1 - defence_reduction)))

        return damage

    def _get_weapon_damage(self) -> int:
        """Get the damage value of the player's equipped weapon."""
        gear = self.player.gear
        if gear and gear.weapon:
            return gear.weapon.damage
        return 1  # Fists

    def get_attack_cooldown(self) -> float:
        """
        Calculate the player's attack cooldown.

        Cooldown = base_cooldown - (speed_stat * 0.3)
        Base cooldown = 1.5 seconds (unarmed)
        Speed stat reduces cooldown by 0.3s per point (capped at 0.5s minimum)

        Returns:
            Attack cooldown in seconds.
        """
        base_cooldown = COMBAT_BASE_ATTACK_COOLDOWN  # Default unarmed
        if self.player.gear and self.player.gear.weapon:
            base_cooldown = COMBAT_BASE_ATTACK_COOLDOWN  # All weapons share base 1.5s
            # Weapon speed_bonus is applied as a flat modifier
            base_cooldown += self.player.gear.weapon.speed_bonus

        speed_stat = self.player.skill_manager.get_effective_stat(
            "combat", "speed"
        )
        cooldown = base_cooldown - (speed_stat * COMBAT_SPEED_STAT_COOLDOWN_REDUCTION)
        return max(0.5, cooldown)

    # ── Player Attack ──────────────────────────────────────────────

    def player_attack(self, dt: float) -> Optional[AttackResult]:
        """
        Execute the player's attack on the selected target.

        Args:
            dt: Delta time in seconds.

        Returns:
            AttackResult if an attack was performed, None if on cooldown.
        """
        if self.player_attack_cooldown > 0:
            self.player_attack_cooldown -= dt
            return None

        if not self.selected_target or not self.selected_target.is_alive():
            self.deselect_target()
            return None

        # Verify player is in attack range (~40 pixels melee)
        dist = self._distance_to_target()
        if dist > 40.0:
            self.combat_log.append("Too far away!")
            return None

        # Calculate damage
        damage = self.calculate_damage(self.player, self.selected_target)

        # Apply damage to monster
        self.selected_target.take_damage(damage)

        # Spawn damage number
        self.damage_numbers.append(DamageNumber(
            value=damage,
            world_x=self.selected_target.world_x,
            world_y=self.selected_target.world_y - 10,
            timer=2.0,
            color=(255, 50, 50),
        ))

        # Grant 1 XP per hit (minor engagement XP)
        self.player.skill_manager.add_xp("combat", 1.0)

        # Check monster death
        if not self.selected_target.is_alive():
            self._monster_died(self.selected_target)
            msg = f"You killed the {self.selected_target.name}!"
            self.combat_log.append(msg)
            return AttackResult(damage_dealt=damage, damage_taken=0, monster_died=True, message=msg)

        # Set cooldown
        self.player_attack_cooldown = self.get_attack_cooldown()

        # Monster counter-attack
        monster_damage = 0
        if self.selected_target.attack_cooldown_timer <= 0 and dist <= 40.0:
            monster_damage = self._monster_counter_attack()
            self.selected_target.attack_cooldown_timer = self.selected_target.attack_cooldown

        msg = f"You hit the {self.selected_target.name} for {damage} damage!"
        if monster_damage > 0:
            msg += f" It hits back for {monster_damage}!"

        return AttackResult(
            damage_dealt=damage,
            damage_taken=monster_damage,
            monster_died=False,
            message=msg,
        )

    def _monster_counter_attack(self) -> int:
        """
        Execute monster counter-attack on the player.

        Damage is applied through the SurvivalSystem (which handles
        death detection). If the player dies, a soft-death sequence
        is triggered: XP penalty, respawn with 50% HP/hunger, monster
        drops are kept.

        Returns:
            Damage dealt to the player.
        """
        if not self.selected_target:
            return 0

        # Calculate damage monster deals to player (inverted direction)
        # Monster attack * 0.5 (monsters are weaker than player stats)
        base_monster_attack = self.selected_target.attack

        # Player defence reduces damage
        player_defence = self._get_player_defence()
        defence_reduction = player_defence * 0.01

        raw_damage = base_monster_attack * 0.5
        damage = max(1, int(raw_damage * (1 - defence_reduction)))

        # Apply damage through survival system (handles death)
        if self.survival is not None:
            player_died = self.survival.take_damage(damage)
            if player_died:
                self._on_player_death()
        else:
            # Fallback: direct player HP reduction (Phase 1 compat)
            self.player.take_damage(damage)

        # Spawn damage number (yellow for player damage)
        self.damage_numbers.append(DamageNumber(
            value=-damage,
            world_x=self.player.world_x,
            world_y=self.player.world_y - 10,
            timer=2.0,
            color=(200, 200, 50),
        ))

        return damage

    def _on_player_death(self) -> None:
        """
        Handle player soft death.

        Sequence:
        1. Apply XP penalty across all skills
        2. Restore HP/hunger using config fractions
        3. Increment death count
        4. Respawn at spawn point
        5. Clear monsters and deselect target
        6. Save after death
        """
        # XP penalty
        if self.player.skill_manager is not None:
            total_xp = sum(s.xp for s in self.player.skill_manager.skills.values())
            xp_loss = int(total_xp * DEATH_XP_PENALTY_FRACTION)
            self.player.skill_manager.apply_xp_penalty(xp_loss)

        # Restore HP/hunger using config constants
        if self.survival is not None:
            self.survival.is_dead = False
            self.survival.hp = self.survival.max_hp * DEATH_RESTORE_HP_FRACTION
            self.survival.hunger = self.survival.max_hunger * DEATH_RESTORE_HUNGER_FRACTION

        # Death counter
        if hasattr(self.player, "action_system") and self.player.action_system is not None:
            self.player.action_system.add_notification(
                "You have died! Respawned with 50% HP and Hunger. 1% XP lost.",
                (255, 100, 100),
            )

        self.combat_log.append("Player died — soft death sequence triggered.")

        # Increment death count and save
        if hasattr(self.game, "death_count"):
            self.game.death_count += 1

        # Respawn at spawn
        if hasattr(self.game, "world") and self.game.world is not None:
            self.player.world_x = self.game.world.spawn_x * 64 + 32
            self.player.world_y = self.game.world.spawn_y * 64 + 32

        # Save after death
        if hasattr(self.game, "save_system") and self.game.save_system:
            self.game.save_system.save(self.game, slot=0)

        # Remove all monsters from map
        for monster in self.monsters[:]:
            self.remove_monster(monster)

    # ── NPC Combat ────────────────────────────────────────────────

    def npc_attack(self, npc: "NPC", target: "Monster") -> int:
        """
        Execute an NPC attack on a monster.

        Includes per-NPC cooldown, damage number spawning, and death handling.

        Args:
            npc: The attacking NPC.
            target: The Monster being attacked.

        Returns:
            Damage dealt (0 if on cooldown or target dead).
        """
        # 1. Check per-NPC cooldown
        npc_id = getattr(npc, 'npc_id', str(npc.world_x))
        cooldown_key = f"npc_{npc_id}"
        if self._npc_attack_cooldowns.get(cooldown_key, 0) > 0:
            return 0  # On cooldown, skip

        if not target.is_alive():
            return 0

        # 2. Calculate damage
        npc_attack_val = npc.get_npc_attack()
        attack_mult = 1.0 + npc_attack_val * 0.005  # +0.5% per point

        # Monster defence reduces damage by 1% per point
        monster_defence = target.defence
        defence_reduction = monster_defence * 0.01

        raw_damage = npc_attack_val * attack_mult
        damage = max(1, int(raw_damage * (1 - defence_reduction)))

        # 3. Apply damage to monster
        target.take_damage(damage)

        # 4. Spawn damage number (red — same as player attack)
        self.damage_numbers.append(DamageNumber(
            value=damage,
            world_x=target.world_x,
            world_y=target.world_y - 10,
            timer=2.0,
            color=(255, 50, 50),
        ))

        # 5. Grant player XP for NPC-assisted combat
        if self.player is not None and self.player.skill_manager is not None:
            self.player.skill_manager.add_xp("combat", 1.0)

        # 6. Check monster death
        if not target.is_alive():
            self._monster_died(target)

        # 7. Set cooldown (1.5s default — monster attack cadence)
        npc_cooldown = 1.5  # Consistent monster-like cadence for NPCs
        self._npc_attack_cooldowns[cooldown_key] = npc_cooldown

        return damage

    def npc_take_damage(self, npc: "NPC", amount: int) -> None:
        """
        Apply damage to an NPC and handle NPC death.

        Args:
            npc: The NPC taking damage.
            amount: Damage to apply.
        """
        npc.health -= amount
        if npc.health < 0:
            npc.health = 0

        # Spawn damage number (yellow — same as player taking damage)
        self.damage_numbers.append(DamageNumber(
            value=-amount,
            world_x=npc.world_x,
            world_y=npc.world_y - 10,
            timer=2.0,
            color=(200, 200, 50),
        ))

        # Handle NPC death
        if npc.health <= 0:
            self._on_npc_death(npc)

        # Deselect target
        self.deselect_target()
        self.selected_target = None

    def _on_npc_death(self, npc: "NPC") -> None:
        """
        Handle NPC death: notify RecruitmentSystem (for guards) and
        notify NPCSystem (for faction NPCs).

        Args:
            npc: The dead NPC.
        """
        npc_id = getattr(npc, 'npc_id', 'unknown')

        # Notify RecruitmentSystem — dismiss guard from behavior tracking
        if hasattr(self, 'game') and self.game is not None:
            rs = getattr(self.game, 'recruitment_system', None)
            if rs is not None and npc_id in rs.behaviors:
                rs.on_dismiss(npc_id)

            # Notify NPCSystem — remove dead NPC from active list
            ns = getattr(self.game, 'npc_system', None)
            if ns is not None:
                ns.remove_dead_npc(npc)

    def get_npc_attack_cooldown(self, npc: "NPC") -> float:
        """
        Get the remaining cooldown for an NPC's attack.

        Args:
            npc: The NPC to check.

        Returns:
            Remaining cooldown in seconds (0 if none).
        """
        npc_id = getattr(npc, 'npc_id', str(npc.world_x))
        cooldown_key = f"npc_{npc_id}"
        return self._npc_attack_cooldowns.get(cooldown_key, 0.0)

    def _get_player_defence(self) -> int:
        """Get the player's effective defence stat including gear bonuses."""
        base = self.player.skill_manager.get_effective_stat("combat", "defence")
        if self.player.gear:
            base += self.player.gear.get_defence_bonus()
        return base

    def _distance_to_target(self) -> float:
        """Calculate distance to the selected target."""
        if not self.selected_target:
            return float("inf")
        import math
        dx = self.selected_target.world_x - self.player.world_x
        dy = self.selected_target.world_y - self.player.world_y
        return math.sqrt(dx * dx + dy * dy)

    def _monster_died(self, monster: Monster) -> None:
        """
        Handle monster death: drop loot, grant XP, remove from list.

        Args:
            monster: The dead monster.
        """
        # Grant XP for kill
        xp_reward = monster.xp_reward
        self.player.skill_manager.add_xp("combat", xp_reward)

        # Drop loot
        for drop in monster.loot_table:
            import random
            if random.random() < drop["chance"]:
                self.player.inventory.add_item(drop["item_id"], 1)

        # Remove from active monsters
        if monster in self.monsters:
            self.monsters.remove(monster)

        # Deselect if targeting this monster
        if self.selected_target == monster:
            self.deselect_target()

        # Quest system kill tracking
        if hasattr(self, "game") and self.game is not None:
            qs = getattr(self.game, "quest_system", None)
            if qs is not None and monster.monster_id:
                qs.record_kill(monster.monster_id)

        # Faction standing: check if this monster is associated with any faction
        if self.faction_system is not None and monster.monster_id:
            faction_id = self.faction_system.get_faction_for_monster(monster.monster_id)
            if faction_id is not None:
                self.faction_system.update_standing(faction_id, -0.10)
                if self.game is not None and self.game.player is not None:
                    action_sys = self.game.player.action_system if hasattr(self.game.player, "action_system") else None
                    if action_sys is not None:
                        faction_name = faction_id.replace("_", " ")
                        action_sys.add_notification(
                            f"Killing {monster.name} worsened relations with {faction_name}.",
                            (255, 150, 100),
                        )

    # ── Monster Registration ────────────────────────────────────────

    def register_monster(self, monster: Monster) -> None:
        """
        Spawn a new monster in the combat system.

        Args:
            monster: The monster to add.
        """
        self.monsters.append(monster)

    def remove_monster(self, monster: Monster) -> None:
        """
        Remove a monster from the combat system.

        Args:
            monster: The monster to remove.
        """
        if monster in self.monsters:
            self.monsters.remove(monster)
        if self.selected_target == monster:
            self.deselect_target()

    # ── Initial Monster Spawning ──────────────────────────────────

    def spawn_initial_monsters(
        self,
        biome_monster_data: dict,
        spawn_world_x: float,
        spawn_world_y: float,
        spawn_radius_px: float,
        rng_seed: int,
        biome_id: str = "generic",
    ) -> None:
        """
        Spawn initial monsters on the map for the current biome.

        Called during game initialisation (after world gen completes).
        Each monster is placed at a random angle/distance near spawn.

        Args:
            biome_monster_data: Dict of monster_id → monster_definition for
                the player's starting biome (loaded from monsters.json).
            spawn_world_x: World X position of the spawn point (pixels).
            spawn_world_y: World Y position of the spawn point (pixels).
            spawn_radius_px: Maximum spawn distance from spawn point (pixels).
            rng_seed: Seed for the random number generator (ensures reproducibility).
            biome_id: Biome identifier used for the monster's biome label.
        """
        import math
        import random

        if not biome_monster_data:
            return

        rng = random.Random(rng_seed)
        num_to_spawn = min(len(biome_monster_data), 5)

        monster_ids = list(biome_monster_data.keys())
        selected = rng.sample(monster_ids, num_to_spawn)

        for mid in selected:
            m_def = biome_monster_data[mid]
            angle = rng.uniform(0, 2 * 3.14159)
            dist = rng.uniform(64, spawn_radius_px)
            mx = spawn_world_x + math.cos(angle) * dist
            my = spawn_world_y + math.sin(angle) * dist

            loot_table = m_def.get("loot_table", [])

            from combat.monster import Monster
            monster = Monster.from_def(
                monster_id=mid,
                biome=biome_id,
                world_x=mx,
                world_y=my,
                loot_table=loot_table,
                special=m_def.get("special", ""),
            )

            # Override aggression/flee ranges from def
            if "aggression_range" in m_def:
                monster.aggression_range = m_def["aggression_range"]
            if "flee_range" in m_def:
                monster.flee_range = m_def["flee_range"]

            self.register_monster(monster)

    # ── Tick / Update ───────────────────────────────────────────────

    def tick(self, dt: float) -> None:
        """
        Main combat tick — runs every frame during gameplay.

        Updates monster AI, attack cooldowns, damage number timers,
        monster structure attacks, and fire deterrence.

        Args:
            dt: Delta time in seconds.
        """
        # Update player attack cooldown
        if self.player_attack_cooldown > 0:
            self.player_attack_cooldown -= dt

        # Update monster AI
        for monster in self.monsters:
            if monster.is_alive():
                monster.update_ai(self.player, dt)

                # Monster structure attacks (if monster is attacking and near structure)
                if (
                    monster.ai_state == "attack"
                    and self.building_system is not None
                ):
                    # Monsters occasionally attack nearby structures
                    import random
                    if random.random() < 0.02:  # ~2% chance per frame during attack
                        destroyed = self.building_system.monster_attack_structure(
                            monster.attack, monster.world_x, monster.world_y,
                        )
                        if destroyed:
                            self.combat_log.append(
                                f"{monster.name} destroyed a {destroyed.structure_def.name}!"
                            )

                # Fire deterrence: monsters flee from fires
                if (
                    self.firemaking is not None
                    and not monster.is_alive()
                ):
                    pass  # Dead monsters don't flee
                elif self.firemaking is not None:
                    fires = self.firemaking.get_fires_in_radius(
                        monster.world_x, monster.world_y, 200.0,
                    )
                    for fire in fires:
                        if fire.heat_output > 1.0:  # Strong fires deter monsters
                            # Move monster away from fire
                            import math
                            dx = monster.world_x - fire.world_x
                            dy = monster.world_y - fire.world_y
                            dist = math.sqrt(dx * dx + dy * dy)
                            if dist > 0:
                                monster.world_x += (dx / dist) * monster.speed * dt * 0.5
                                monster.world_y += (dy / dist) * monster.speed * dt * 0.5
                            if monster.ai_state == "attack":
                                monster.ai_state = "flee"

        # Update damage number timers
        for dn in self.damage_numbers:
            dn.timer -= dt
            dn.offset_y += dt * COMBAT_DAMAGE_NUMBER_RISE_RATE  # Damage number rise rate

        # Remove expired damage numbers
        self.damage_numbers = [dn for dn in self.damage_numbers if dn.timer > 0]

        # Update monster attack cooldowns
        for monster in self.monsters:
            if monster.attack_cooldown_timer > 0:
                monster.attack_cooldown_timer -= dt

        # Clean up NPC attack cooldowns (guards/faction NPCs)
        for key in list(self._npc_attack_cooldowns.keys()):
            if self._npc_attack_cooldowns[key] > 0:
                self._npc_attack_cooldowns[key] -= dt
            else:
                del self._npc_attack_cooldowns[key]

    # ── Snapshots ───────────────────────────────────────────────────

    def get_target_snapshot(self) -> Optional[dict]:
        """
        Return a snapshot of the current target's state for UI rendering.

        Returns:
            Dict with monster state info, or None if no target.
        """
        if not self.selected_target or not self.selected_target.is_alive():
            return None
        return {
            "name": self.selected_target.name,
            "hp": self.selected_target.hp,
            "max_hp": self.selected_target.max_hp,
            "hp_percent": self.selected_target.hp / self.selected_target.max_hp,
        }

    def offensive_structure_hit(
        self, structure: object, monster: object, damage: int,
    ) -> None:
        """
        Handle damage dealt by an offensive structure (ballista/trebuchet).

        Spawns a damage number (gold color) and checks for monster death.

        Args:
            structure: The offensive structure that fired.
            monster: The monster that was hit.
            damage: The amount of damage dealt.
        """
        # Spawn golden damage number (turret damage)
        self.damage_numbers.append(DamageNumber(
            value=damage,
            world_x=monster.world_x,
            world_y=monster.world_y - 15,
            timer=2.0,
            color=(255, 200, 50),
        ))

        monster.take_damage(damage)

        # Check if monster died
        if not monster.is_alive():
            self._monster_died(monster)
            struct_name = structure.structure_def.name if hasattr(structure, "structure_def") else "Turret"
            self.combat_log.append(f"{struct_name} destroyed the {monster.name}!")
