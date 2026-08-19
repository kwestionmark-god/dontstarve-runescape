"""
combat/combat_ui.py — Combat UI rendering.

Handles floating damage numbers and monster health bar rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import pygame

    from camera import Camera
    from combat.combat_system import DamageNumber


def render_damage_numbers(
    screen: pygame.Surface,
    damage_numbers: List[DamageNumber],
    camera: Camera,
    font: pygame.font.Font,
) -> None:
    """
    Render floating damage numbers.

    Numbers rise over time and fade out over 2 seconds.
    Positive values (player dealing damage) are red.
    Negative values (player taking damage) are yellow.

    Args:
        screen: The pygame display surface.
        damage_numbers: List of active DamageNumber objects.
        camera: The current camera.
        font: Font for rendering text.
    """
    for dn in damage_numbers:
        if dn.timer <= 0:
            continue

        # Convert world position to screen position
        screen_x, screen_y = camera.world_to_screen(dn.world_x, dn.world_y)

        # Rising animation
        rise_offset = (2.0 - dn.timer) * 30  # 30px per second rising
        screen_y -= rise_offset

        # Fade based on timer
        alpha = int(255 * (dn.timer / 2.0))

        # Render text
        text = f"+{dn.value}" if dn.value > 0 else str(dn.value)
        rendered_text = font.render(text, True, dn.color)

        # Apply alpha by drawing to a temporary surface
        text_with_alpha = rendered_text.copy()
        text_with_alpha.set_alpha(alpha)

        screen.blit(
            text_with_alpha,
            (
                screen_x - rendered_text.get_width() // 2,
                screen_y - rendered_text.get_height() // 2,
            ),
        )
