"""
combat/monster.py — Monster base class and AI state machine.

Defines Monster dataclass with stats, loot tables, and an AI state
machine (IDLE → PATROL → CHASE → ATTACK → FLEE).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from core.player import Player


# Base monster stats by ID (Phase 2 defaults)
_MONSTER_HP_TABLE: Dict[str, Dict[str, Any]] = {
    "wolf":         {"hp": 8,  "attack": 3, "defence": 2, "speed": 80,  "xp": 15},
    "bear":         {"hp": 15, "attack": 5, "defence": 4, "speed": 50,  "xp": 25},
    "goblin":       {"hp": 6,  "attack": 4, "defence": 1, "speed": 70,  "xp": 12},
    "poison_frog":  {"hp": 4,  "attack": 3, "defence": 1, "speed": 30,  "xp": 10},
    "crocodile":    {"hp": 12, "attack": 6, "defence": 3, "speed": 40,  "xp": 20},
    "swamp_drake":  {"hp": 10, "attack": 5, "defence": 3, "speed": 60,  "xp": 20},
    "scorpion":     {"hp": 6,  "attack": 4, "defence": 2, "speed": 50,  "xp": 14},
    "sand_worm":    {"hp": 18, "attack": 7, "defence": 3, "speed": 60,  "xp": 30},
    "djinn":        {"hp": 20, "attack": 8, "defence": 5, "speed": 90,  "xp": 40},
    "stone_golem":  {"hp": 30, "attack": 10, "defence": 8, "speed": 20, "xp": 50},
    "eagle":        {"hp": 8,  "attack": 5, "defence": 2, "speed": 120, "xp": 15},
    "cave_troll":   {"hp": 22, "attack": 8, "defence": 5, "speed": 35,  "xp": 35},
    "boar":         {"hp": 10, "attack": 5, "defence": 3, "speed": 70,  "xp": 16},
    "snake":        {"hp": 5,  "attack": 4, "defence": 1, "speed": 90,  "xp": 12},
    "hawk":         {"hp": 4,  "attack": 3, "defence": 1, "speed": 130, "xp": 15},
    "crab":         {"hp": 6,  "attack": 2, "defence": 4, "speed": 40,  "xp": 10},
    "sea_serpent":  {"hp": 14, "attack": 6, "defence": 3, "speed": 80,  "xp": 25},
}


@dataclass
class Monster:
    """
    Monster entity with stats, AI behavior, and loot drops.

    Fields:
        monster_id: Unique identifier (e.g. "wolf").
        name: Display name (e.g. "Wolf").
        biome: The biome this monster spawns in.
        world_x: Current X position in world space.
        world_y: Current Y position in world space.
        hp: Current health points.
        max_hp: Maximum health points.
        attack: Attack damage per hit.
        defence: Damage reduction (1% per point).
        speed: Movement speed in pixels per second.
        aggression_range: Distance (px) at which the monster becomes hostile.
        flee_range: Distance (px) at which the monster flees.
        attack_cooldown: Seconds between monster attacks.
        xp_reward: XP granted on death.
        loot_table: Drops on death — [{"item_id": str, "chance": float}].
        sprite_key: Sprite sheet reference key.
        is_hostile: Whether the monster is always aggressive.
        ai_state: Current AI state — "idle", "patrol", "chase", "attack", "flee".
        attack_cooldown_timer: Countdown until next attack.
    """

    monster_id: str
    name: str
    biome: str
    world_x: float = 0.0
    world_y: float = 0.0
    hp: int = 8
    max_hp: int = 8
    attack: int = 3
    defence: int = 2
    speed: float = 80.0
    aggression_range: float = 150.0
    flee_range: float = 300.0
    attack_cooldown: float = 1.5
    xp_reward: float = 15.0
    loot_table: List[Dict[str, Any]] = field(default_factory=list)
    sprite_key: str = "monster/wolf"
    is_hostile: bool = True
    ai_state: str = "idle"
    attack_cooldown_timer: float = 0.0
    special: str = ""  # "poison", "ranged", "ambush", "aerial"
    # Stats loaded from definition at initialization time
    _attack_range: float = field(default=40.0)

    @classmethod
    def from_def(cls, monster_id: str, biome: str,
                 world_x: float, world_y: float,
                 loot_table: List[Dict[str, Any]] | None = None,
                 special: str = "") -> "Monster":
        """
        Create a Monster from a definition dict.

        Args:
            monster_id: The monster's ID key.
            biome: The biome this monster belongs to.
            world_x: Spawn X position.
            world_y: Spawn Y position.
            loot_table: Optional loot table override.
            special: Optional special behavior tag.

        Returns:
            A fully initialized Monster instance.
        """
        base = _MONSTER_HP_TABLE.get(monster_id, {
            "hp": 10, "attack": 3, "defence": 2,
            "speed": 60, "xp": 15,
        })
        return cls(
            monster_id=monster_id,
            name=monster_id.replace("_", " ").title(),
            biome=biome,
            world_x=world_x,
            world_y=world_y,
            hp=base["hp"],
            max_hp=base["hp"],
            attack=base["attack"],
            defence=base["defence"],
            speed=base["speed"],
            aggression_range=150.0,  # Can be overridden per-def
            flee_range=300.0,
            attack_cooldown=base.get("attack_cooldown", 1.5),
            xp_reward=base["xp"],
            loot_table=loot_table or [],
            sprite_key=f"monster/{monster_id}",
            special=special,
        )

    def take_damage(self, damage: int) -> None:
        """
        Apply damage to this monster.

        Args:
            damage: Amount of damage to deal.
        """
        self.hp = max(0, self.hp - damage)

    def is_alive(self) -> bool:
        """Returns True if the monster has HP > 0."""
        return self.hp > 0

    def heal(self, amount: int) -> None:
        """
        Heal the monster by a number of HP.

        Args:
            amount: HP to restore.
        """
        self.hp = min(self.max_hp, self.hp + amount)

    # ── AI State Machine ────────────────────────────────────────────

    def update_ai(self, player: Player, dt: float) -> None:
        """
        One-frame AI decision cycle.

        Args:
            player: The player entity to react to.
            dt: Delta time in seconds.
        """
        dist = self._distance_to(player)

        # Attack cooldown management
        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= dt
            if self.attack_cooldown_timer <= 0:
                self.attack_cooldown_timer = 0

        # Special behavior triggers (aerial base speed, ambush)
        if self.special == "aerial" and not hasattr(self, "_base_speed"):
            self._base_speed = self.speed

        # Apply special behaviors
        self._apply_special_behavior(player, dt)

        # State transitions
        prev_state = self.ai_state
        if self.ai_state == "idle":
            if dist <= self.aggression_range:
                self.ai_state = "patrol"

        elif self.ai_state == "patrol":
            if dist <= self.aggression_range:
                self.ai_state = "chase"
            elif dist > self.flee_range:
                self.ai_state = "flee"
            # else: continue patrolling (stay in current position for now)

        elif self.ai_state == "chase":
            if dist <= self._attack_range:
                self.ai_state = "attack"
            elif dist > self.flee_range:
                self.ai_state = "flee"
            else:
                # Move toward player
                self._move_toward(player.world_x, player.world_y, dt)

        elif self.ai_state == "attack":
            if dist > self._attack_range * 1.2:
                self.ai_state = "chase"
            elif self.attack_cooldown_timer <= 0:
                # Attack will be handled by CombatSystem (player initiates attacks)
                pass

        elif self.ai_state == "flee":
            self._move_away(player.world_x, player.world_y, dt)
            if dist > self.flee_range * 1.5:
                self.ai_state = "idle"

        # Reset special state when losing engagement
        if prev_state in ("chase", "attack") and self.ai_state in ("idle", "flee"):
            self.reset_special()

    def _distance_to(self, entity: Any) -> float:
        """Calculate Euclidean distance to another entity."""
        dx = entity.world_x - self.world_x
        dy = entity.world_y - self.world_y
        return math.sqrt(dx * dx + dy * dy)

    def _move_toward(self, target_x: float, target_y: float, dt: float) -> None:
        """
        Move this monster toward a target position.

        Args:
            target_x: Target X.
            target_y: Target Y.
            dt: Delta time.
        """
        dx = target_x - self.world_x
        dy = target_y - self.world_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            move_x = (dx / dist) * self.speed * dt
            move_y = (dy / dist) * self.speed * dt
            self.world_x += move_x
            self.world_y += move_y

    def _move_away(self, away_x: float, away_y: float, dt: float) -> None:
        """
        Move this monster away from a position.

        Args:
            away_x: Position to flee from (X).
            away_y: Position to flee from (Y).
            dt: Delta time.
        """
        dx = away_x - self.world_x
        dy = away_y - self.world_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            move_x = -(dx / dist) * self.speed * dt
            move_y = -(dy / dist) * self.speed * dt
            self.world_x += move_x
            self.world_y += move_y

    # ── Special Behaviors ───────────────────────────────────────────

    def _apply_special_behavior(self, player: Player, dt: float) -> None:
        """
        Apply special behavior effects based on the monster's special tag.

        Special tags:
            poison: Inflicts poison DoT (stub — damage +1 on attack).
            ambush: Movement hidden until attack range (effective +30% damage first hit).
            aerial: Moves above ground (elevation bonus, +10 speed, -2 defence).
            ranged: Ranged attacker (effective +50px attack range, -3 speed).

        Args:
            player: The player entity.
            dt: Delta time in seconds.
        """
        if not self.special:
            return

        if self.special == "poison":
            # Poison: on attack, inflict additional 1 damage (DoT stub)
            # Integration point: when this monster attacks, apply poison
            # For now, poison increases attack by 1
            self.attack += 1 if not getattr(self, "_poison_applied", False) else 0
            self._poison_applied = True

        elif self.special == "ambush":
            # Ambush: approach silently until within 60px of player
            # Speed doubled when within aggression_range but > attack_range
            dist = self._distance_to(player)
            if self.aggression_range >= dist > self._attack_range:
                # Ambush bonus: move faster when sneaking
                ambush_speed_boost = 1.5
                self._move_toward(player.world_x, player.world_y, dt * ambush_speed_boost)

        elif self.special == "aerial":
            # Aerial: higher movement speed (+30%), reduced ground defence (-1)
            self.speed = getattr(self, "_base_speed", self.speed) * 1.3
            if not hasattr(self, "_base_defence"):
                self._base_defence = self.defence
            self.defence = max(0, self._base_defence - 1)

        elif self.special == "ranged":
            # Ranged: effective attack range +50px
            if not hasattr(self, "_base_attack_range"):
                self._base_attack_range = self._attack_range
            self._attack_range = 95.0  # Base 40 + 55 extra

    def reset_special(self) -> None:
        """
        Reset special state flags.

        Called when the monster loses sight of the player or
        enters idle/flee state.
        """
        if self.special == "poison":
            self._poison_applied = False
            # Restore base attack
            base = _MONSTER_HP_TABLE.get(self.monster_id, {})
            if base:
                self.attack = base.get("attack", self.attack)
        elif self.special == "aerial":
            if hasattr(self, "_base_speed"):
                self.speed = self._base_speed
            if hasattr(self, "_base_defence"):
                self.defence = self._base_defence
        elif self.special == "ranged":
            if hasattr(self, "_base_attack_range"):
                self._attack_range = self._base_attack_range

