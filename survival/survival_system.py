"""
survival_system.py — Hunger + HP management.

Tracks and updates hunger and HP meters. Handles hunger drain,
starvation HP drain, food consumption, damage, and healing.

Survival continues ticking during panel states — survival tension
is always present once the game is in PLAYING mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import (
    HUNGER_DRAIN_INTERVAL,
    HUNGER_DRAIN_RATE,
    STARVATION_HP_DRAIN_RATE,
    HP_BASE_MAX,
)

if TYPE_CHECKING:
    from survival.food import FoodItem
    from world.tile_map import Tile


class SurvivalSystem:
    """
    Tracks and updates hunger and HP meters.

    Fields:
        hunger: 0.0 (starving) to 100.0 (full)
        max_hunger: 100.0 (constant)
        hp: 0.0 (dead) to max_hp
        max_hp: starts at HP_BASE_MAX, can increase via skills/gear
        starvation_timer: accumulator; when >= 1.0 and hunger == 0, drain HP
        is_dead: True once hp <= 0
        environmental_pressure: biome multiplier on survival drain (0.0+)
    """

    __slots__ = (
        "hunger",
        "max_hunger",
        "hp",
        "max_hp",
        "starvation_timer",
        "is_dead",
        "on_death",
        "environmental_pressure",
        "hunger_drain_interval",
        "hunger_drain_rate",
        "starvation_hp_drain_rate",
        "_last_env_pressure",
        "_season_hunger_mod",
        "_season_system",
        "weather_system",
    )

    def __init__(
        self,
        environmental_pressure: float = 1.0,
    ) -> None:
        """
        Initialize survival system.

        Args:
            environmental_pressure: Biome multiplier on survival drain.
                0.5 = half drain (safe biome), 1.0 = normal, 1.5+ = harsh.
        """
        self.hunger: float = 100.0
        self.max_hunger: float = 100.0
        self.hp: float = HP_BASE_MAX
        self.max_hp: float = HP_BASE_MAX
        self.starvation_timer: float = 0.0
        self.is_dead: bool = False
        # Optional death callback injected by bootstrap once combat exists.
        # Routes starvation death into the shared soft-death handler.
        self.on_death = None
        self.environmental_pressure = environmental_pressure
        self.hunger_drain_interval: float = HUNGER_DRAIN_INTERVAL
        self.hunger_drain_rate: float = HUNGER_DRAIN_RATE
        self.starvation_hp_drain_rate: float = STARVATION_HP_DRAIN_RATE
        self._last_env_pressure: float = environmental_pressure

        # Phase 4: optional SeasonSystem reference (set by bootstrap)
        self._season_system: object | None = None
        self._season_hunger_mod: float = 1.0
        # WeatherSystem reference for gameplay effects (set by bootstrap)
        self.weather_system: object | None = None

    def tick(self, dt: float) -> None:
        """
        Called every frame. Handles hunger drain and starvation HP drain.

        Hunger drains at a constant rate. When hunger reaches 0,
        HP begins draining due to starvation.

        Environmental pressure from the player's biome scales all
        survival drain rates (higher pressure = faster drain).

        Args:
            dt: Delta time in seconds.
        """
        if self.is_dead:
            return

        # ── Apply seasonal modifiers ────────────────────────────────
        self._update_season_modifiers()

        # ── Hunger drain ────────────────────────────────────────────
        if self.hunger > 0:
            # Drain 1 point every HUNGER_DRAIN_INTERVAL seconds,
            # scaled by environmental pressure and seasonal hunger modifier
            drain_rate = self.hunger_drain_rate * self.environmental_pressure * self._season_hunger_mod
            self.hunger -= drain_rate * (dt / self.hunger_drain_interval)
            self.hunger = max(0.0, self.hunger)

        # ── Starvation HP drain ─────────────────────────────────────
        if self.hunger <= 0:
            self.starvation_timer += dt
            if self.starvation_timer >= self.hunger_drain_interval:
                self.starvation_timer -= self.hunger_drain_interval
                hp_drain = self.starvation_hp_drain_rate * self.environmental_pressure
                if self.take_damage(hp_drain):
                    # Starvation killed the player. Run the shared soft-death
                    # handler (injected by bootstrap). tick() early-returns on
                    # is_dead, so this fires once per death, not every frame.
                    if self.on_death is not None:
                        self.on_death()

    def eat(self, food_item: "FoodItem") -> str:
        """
        Consume a FoodItem to restore hunger and optionally HP.

        Reads nutrition values from the FoodItem. Applies spoilage
        effects (negative hp_restore from spoiled food).

        Args:
            food_item: A FoodItem with nutrition values.

        Returns:
            Result string for player feedback.
        """
        if self.is_dead:
            return "You are dead."

        old_hunger = self.hunger
        old_hp = self.hp

        # Restore hunger (capped at max)
        self.hunger = min(self.max_hunger, self.hunger + food_item.hunger_restoration)
        hunger_gained = self.hunger - old_hunger

        # Restore/damage HP
        if food_item.hp_restoration != 0.0:
            self.hp = max(0.0, min(self.max_hp, self.hp + food_item.hp_restoration))

        # Feedback
        if food_item.hp_restoration > 0:
            return f"You eat it. Hunger +{hunger_gained:.0f}, HP +{food_item.hp_restoration:.0f}."
        elif food_item.hp_restoration < 0:
            return f"You eat it. Hunger +{hunger_gained:.0f}, HP {food_item.hp_restoration:.0f}."
        else:
            return f"You eat it. Hunger +{hunger_gained:.0f}."

    def take_damage(self, amount: float) -> bool:
        """
        Reduce HP by amount. Triggers death if hp <= 0.

        Args:
            amount: Damage to deal.

        Returns:
            True if the player died.
        """
        if self.is_dead:
            return False

        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0.0
            self.is_dead = True
            return True
        return False

    def heal(self, amount: float) -> None:
        """
        Restore HP (capped at max_hp).

        Args:
            amount: HP to restore.
        """
        if self.is_dead:
            return
        self.hp = min(self.max_hp, self.hp + amount)

    def get_hunger_percent(self) -> float:
        """Returns hunger/max_hunger as a 0–1 ratio."""
        return self.hunger / self.max_hunger

    def get_hp_percent(self) -> float:
        """Returns hp/max_hp as a 0–1 ratio."""
        return self.hp / self.max_hp

    def update_from_tile(self, tile: "Tile | None") -> None:
        """
        Update environmental pressure based on the current tile's biome.

        If the tile's biome pressure differs from the last recorded pressure,
        update both the current pressure and the last pressure tracker.

        Args:
            tile: The current tile the player is standing on (may be None).
        """
        if tile is None or tile.biome is None:
            return

        new_pressure = tile.biome.environmental_pressure
        if new_pressure != self._last_env_pressure:
            self.environmental_pressure = new_pressure
            self._last_env_pressure = new_pressure

    def _update_season_modifiers(self) -> None:
        """Apply seasonal survival modifiers if SeasonSystem is wired."""
        if self._season_system is None:
            self._season_hunger_mod = 1.0
            return

        mods = self._season_system.get_survival_modifiers()
        self._season_hunger_mod = mods.get("hunger_drain", 1.0)

    @property
    def season_system(self) -> object | None:
        """Getter for season_system (set by bootstrap)."""
        return self._season_system

    @season_system.setter
    def season_system(self, value: object | None) -> None:
        """Setter for season_system (set by bootstrap)."""
        self._season_system = value

    def get_weather_effects(self) -> dict[str, float]:
        """Return current weather gameplay effects."""
        if self.weather_system is not None:
            return self.weather_system.get_effects()
        return {}

    @property
    def weather_visibility(self) -> float:
        """Return weather visibility multiplier (0.0–1.0)."""
        return self.get_weather_effects().get("visibility", 1.0)

    @property
    def weather_movement_speed(self) -> float:
        """Return weather movement speed multiplier (0.0–1.0)."""
        return self.get_weather_effects().get("movement_speed", 1.0)

    @property
    def weather_outdoor_crafting(self) -> float:
        """Return weather outdoor crafting multiplier (0.0–1.0)."""
        return self.get_weather_effects().get("outdoor_crafting", 1.0)

    @property
    def weather_spawn_mod(self) -> float:
        """Return weather spawn modifier (0.0+)."""
        return self.get_weather_effects().get("spawn_mod", 1.0)
