"""
firemaking.py — Firemaking skill logic.

Handles fire creation, burn duration/radius/intensity stats,
and fire entity management. Fires provide warmth, light, and
monster deterrence.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from skills.firemaking.fire_entity import FireEntity

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager
    from inventory.inventory import Inventory


_SKILL_DATA_DIR = Path(__file__).parent / "data"


def _load_fuel_table() -> dict[str, tuple[float, float]]:
    """Load fuel table from the package data JSON."""
    path = _SKILL_DATA_DIR / "fuel_table.json"
    data = json.loads(path.read_text())
    return {
        k: (v["burn_seconds"], v["heat_multiplier"])
        for k, v in data["fuel_table"].items()
    }


_FUEL_TABLE = _load_fuel_table()


@dataclass
class FireResult:
    """Result of a fire-lighting attempt."""
    success: bool
    fire: Optional[FireEntity] = None
    xp_gained: float = 0.0
    message: str = ""


class FiremakingSkill:
    """
    Manages fire creation, maintenance, and effects.

    Fields:
        skill_manager: Reference to the skill manager.
        active_fires: All active fire entities on the map.
    """

    __slots__ = ("skill_manager", "active_fires")

    def __init__(self, skill_manager: SkillManager) -> None:
        self.skill_manager: SkillManager = skill_manager
        self.active_fires: List[FireEntity] = []

    # ── Lighting Fires ──────────────────────────────────────────────

    def light_fire(
        self,
        fuel_items: List[Tuple[str, int]],
        inventory: Inventory,
        world_x: float,
        world_y: float,
    ) -> FireResult:
        """
        Light a fire at a world position using the given fuel.

        Flow:
        1. Calculate fire properties from stats
        2. Determine total burn duration from fuel + Burn Duration stat
        3. Determine radius from Radius stat
        4. Determine intensity from Intensity stat
        5. Consume fuel from inventory
        6. Create FireEntity
        7. Grant Firemaking XP

        Args:
            fuel_items: List of (item_id, quantity) to consume as fuel.
            inventory: The player's inventory.
            world_x: X position for the fire.
            world_y: Y position for the fire.

        Returns:
            FireResult with success/failure info.
        """
        # Get stat values
        burn_duration_stat = self.skill_manager.get_effective_stat(
            "firemaking", "burn_duration"
        )
        radius_stat = self.skill_manager.get_effective_stat(
            "firemaking", "radius"
        )
        intensity_stat = self.skill_manager.get_effective_stat(
            "firemaking", "intensity"
        )

        # Calculate total burn duration from fuel
        total_burn = 0.0
        for item_id, qty in fuel_items:
            fuel_info = _FUEL_TABLE.get(item_id)
            if fuel_info is not None:
                duration, _ = fuel_info
                total_burn += duration * qty
            else:
                # Unknown fuel: treat as stick
                total_burn += 15.0 * qty

        # Apply Burn Duration stat bonus (+10 sec per point)
        total_burn += burn_duration_stat * 10.0

        # Determine radius (base 1 tile + 0.5 per Radius stat point)
        radius = 1.0 + radius_stat * 0.5

        # Determine intensity (base 1.0 × 1.05 per Intensity stat point)
        intensity = 1.0 * (1.0 + intensity_stat * 0.05)

        # Consume fuel from inventory
        for item_id, qty in fuel_items:
            if not inventory.has_items(item_id, qty):
                return FireResult(
                    success=False,
                    message=f"Insufficient fuel: need {qty}x {item_id}.",
                )

        for item_id, qty in fuel_items:
            inventory.remove_item(item_id, qty)

        # Create fire entity
        fire_id = f"fire_{int(time.time())}_{len(self.active_fires)}"
        fire = FireEntity(
            fire_id=fire_id,
            world_x=world_x,
            world_y=world_y,
            fuel_items=list(fuel_items),
            burn_duration_total=total_burn,
            burn_duration_remaining=total_burn,
            radius_tiles=radius,
            heat_output=intensity,
            is_active=True,
            sprite_key="campfire_fire",
        )

        self.active_fires.append(fire)

        # Calculate XP: base XP from fuel + radius bonus
        xp_gained = self._calculate_fire_xp(fuel_items, radius)

        return FireResult(
            success=True,
            fire=fire,
            xp_gained=xp_gained,
            message=f"You light a fire. It will burn for {total_burn:.0f} seconds.",
        )

    def _calculate_fire_xp(self, fuel_items: List[Tuple[str, int]], radius: float) -> float:
        """
        Calculate XP granted for lighting a fire.

        XP based on fuel type and radius bonus.

        Args:
            fuel_items: The fuel consumed.
            radius: Fire radius in tiles.

        Returns:
            XP granted.
        """
        total_xp = 0.0
        for item_id, qty in fuel_items:
            base_xp = {
                "stick": 5,
                "log": 10,
                "oak_logs": 10,
                "charcoal": 15,
                "plank": 8,
                "planks": 8,
            }.get(item_id, 5)
            radius_bonus = int(radius * {
                "stick": 2,
                "log": 3,
                "oak_logs": 3,
                "charcoal": 5,
                "plank": 2,
                "planks": 2,
            }.get(item_id, 2))
            total_xp += (base_xp + radius_bonus) * qty
        return total_xp

    # ── Fire Tick ───────────────────────────────────────────────────

    def tick(self, dt: float) -> None:
        """
        Update all active fires.

        Decrements burn timers. When a fire runs out of time,
        it becomes inactive and is removed.

        Also handles monster deterrence: monsters within fire radius
        flee from the fire.

        Args:
            dt: Delta time in seconds.
        """
        for fire in self.active_fires:
            if not fire.is_active:
                continue

            fire.burn_duration_remaining -= dt
            if fire.burn_duration_remaining <= 0:
                fire.is_active = False

        # Remove dead fires
        self.active_fires = [f for f in self.active_fires if f.is_active]

    # ── Fire Queries ────────────────────────────────────────────────

    def get_active_fires(self) -> List[FireEntity]:
        """Return all active fire entities."""
        return [f for f in self.active_fires if f.is_active]

    def get_fires_in_radius(self, world_x: float, world_y: float, radius_px: float) -> List[FireEntity]:
        """
        Find active fires within a radius of a world position.

        Args:
            world_x: X coordinate.
            world_y: Y coordinate.
            radius_px: Search radius in pixels.

        Returns:
            List of active fires within range.
        """
        import math
        result = []
        for fire in self.active_fires:
            if not fire.is_active:
                continue
            dx = fire.world_x - world_x
            dy = fire.world_y - world_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius_px:
                result.append(fire)
        return result

    def is_near_fire(self, world_x: float, world_y: float, min_radius_px: float) -> bool:
        """
        Check if a position is near any active fire.

        Args:
            world_x: X coordinate.
            world_y: Y coordinate.
            min_radius_px: Minimum fire radius to consider.

        Returns:
            True if near an active fire.
        """
        return len(self.get_fires_in_radius(world_x, world_y, min_radius_px)) > 0
