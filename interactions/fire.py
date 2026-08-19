"""
interactions/fire.py — Fire lighting and campfire proximity checks.

Extracted from Game._handle_light_fire and Game._check_nearby_campfire.
"""

from __future__ import annotations

from config import FIRE_INTERACTION_RADIUS_TILES, CAMPFIRE_SEARCH_RADIUS_TILES


class FireInteraction:
    """Handles fire-related player interactions."""

    def __init__(self, game) -> None:  # Game instance for subsystem access
        self._game = game

    def handle_light_fire(self) -> None:
        """Light a fire at the player's current position."""
        game = self._game
        if (
            game.firemaking is None
            or game.inventory is None
            or game.player is None
        ):
            return

        # Check if there's already a fire near the player (1 tile radius)
        nearby_fires = game.firemaking.get_fires_in_radius(
            game.player.world_x, game.player.world_y,
            64 * FIRE_INTERACTION_RADIUS_TILES,
        )
        if nearby_fires:
            if game.player.action_system is not None:
                game.player.action_system.add_notification(
                    "Fire already burning here!",
                    (255, 200, 100),
                )
            return

        # Find available fuel (charcoal preferred, then logs, then sticks)
        fuel_queue: list[tuple[str, int]] = []
        preferred_fuel = ["charcoal", "log", "oak_logs"]
        for fuel_item in preferred_fuel:
            qty = game.inventory.get_item_quantity(fuel_item)
            if qty > 0:
                fuel_queue.append((fuel_item, qty))
                if qty > 2:
                    # Use up to 2 units of preferred fuel
                    fuel_queue = [(fuel_item, min(2, qty))]
                    break

        if not fuel_queue:
            if game.player.action_system is not None:
                game.player.action_system.add_notification(
                    "No fuel available. Need charcoal, logs, or sticks.",
                    (255, 150, 100),
                )
            return

        # Light the fire
        result = game.firemaking.light_fire(
            fuel_queue,
            game.inventory,
            game.player.world_x,
            game.player.world_y,
        )

        if result.success:
            if game.player.action_system is not None:
                game.player.action_system.add_notification(result.message)
            # Grant firemaking XP
            if game.skill_manager is not None:
                game.skill_manager.add_xp("firemaking", result.xp_gained)
        else:
            if game.player.action_system is not None:
                game.player.action_system.add_notification(result.message, (255, 150, 100))

    def check_nearby_campfire(self) -> bool:
        """Check if player is near a campfire structure tile."""
        game = self._game
        if game.world is None:
            return False
        tx, ty = game.player.get_tile_position()
        return game.world.has_structure_nearby(
            tx, ty, CAMPFIRE_SEARCH_RADIUS_TILES, "campfire",
        )
