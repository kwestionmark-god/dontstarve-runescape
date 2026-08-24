"""
input_manager.py — InputManager class.

Translates Pygame events into InputState changes. Holds persistent
held-key states and single-frame triggered events.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from input.input_state import InputState

if TYPE_CHECKING:
    from typing import Tuple


class InputManager:
    """
    Translates Pygame events into InputState changes.

    Holds persistent held-key states and single-frame triggered events.
    """

    __slots__ = ("screen_rect", "_mouse_held_button", "_held_keys", "input_state")

    def __init__(self) -> None:
        self.input_state = InputState()
        self._mouse_held_button: int = 0  # 0 = none
        self._held_keys: set[int] = set()

    def handle_event(self, event: pygame.event.Event) -> None:
        """
        Process a Pygame event and update InputState.

        Args:
            event: A pygame.event.Event instance.
        """
        if event.type == pygame.KEYDOWN:
            self._on_key_down(event.key)
        elif event.type == pygame.KEYUP:
            self._on_key_up(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_mouse_down(event.button, event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._on_mouse_up(event.button)
        elif event.type == pygame.MOUSEMOTION:
            self._on_mouse_motion(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            self._on_mouse_wheel(event.y)

    def _on_key_down(self, key: int) -> None:
        """Handle a key press."""
        self._held_keys.add(key)

        # WASD only for player movement
        if key == pygame.K_w:
            self.input_state.move_up = True
        elif key == pygame.K_s:
            self.input_state.move_down = True
        elif key == pygame.K_a:
            self.input_state.move_left = True
        elif key == pygame.K_d:
            self.input_state.move_right = True
        elif key == pygame.K_b:
            self.input_state.open_building_panel = True
        elif key == pygame.K_TAB:
            self.input_state.open_skill_panel = True
        elif key == pygame.K_c:
            self.input_state.open_inventory = True
        elif key == pygame.K_h:
            self.input_state.open_crafting = True
        elif key == pygame.K_u:
            self.input_state.open_quest_panel = True
        elif key == pygame.K_t:
            self.input_state.open_trade_panel = True
        elif key == pygame.K_k:
            self.input_state.open_recruit_panel = True
        elif key == pygame.K_l:
            self.input_state.open_diplomacy_panel = True

        # Arrow keys → camera orbital controls
        elif key == pygame.K_LEFT:
            self.input_state.orbit_ccw = True
        elif key == pygame.K_RIGHT:
            self.input_state.orbit_cw = True
        elif key in (pygame.K_UP, pygame.K_PAGEUP):
            self.input_state.orbit_tilt_up = True
        elif key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
            self.input_state.orbit_tilt_down = True

        elif key == pygame.K_e:
            self.input_state.interact = True
            self.input_state.interact_pressed = True
            # P3-S21: Explicit INTERACT_NPC flag
            self.input_state.interact_npc = True
            self.input_state.interact_npc_pressed = True
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            # Enter is context-sensitive confirm in any panel
            self.input_state.trade_accept = True
            self.input_state.trade_accept_pressed = True
            self.input_state.quest_accept = True
            self.input_state.quest_accept_pressed = True
            self.input_state.faction_negotiate = True
            self.input_state.faction_negotiate_pressed = True
            # Also set interact_npc (some keyboards share enter+interact)
            self.input_state.interact_npc = True
            self.input_state.interact_npc_pressed = True
        elif key == pygame.K_SPACE:
            # Same as Enter (alternative confirm key)
            self.input_state.trade_accept = True
            self.input_state.trade_accept_pressed = True
            self.input_state.quest_accept = True
            self.input_state.quest_accept_pressed = True
            self.input_state.faction_negotiate = True
            self.input_state.faction_negotiate_pressed = True
            self.input_state.interact_npc = True
            self.input_state.interact_npc_pressed = True
        elif key == pygame.K_i:
            self.input_state.open_inventory = True
        elif key == pygame.K_q:
            self.input_state.close_crafting = True
        elif pygame.K_1 <= key <= pygame.K_8:
            # Hotbar slots 1–8
            self.input_state.hotbar_slot = key - pygame.K_1 + 1
        elif key == pygame.K_ESCAPE:
            self.input_state.close_panel = True

    def _on_key_up(self, key: int) -> None:
        """Handle a key release — re-evaluate based on held keys."""
        self._held_keys.discard(key)
        # Clear hotbar one-shot on any key release
        if pygame.K_1 <= key <= pygame.K_8:
            self.input_state.hotbar_slot = 0
        # P3-S21: Reset continuous flags when Enter/Space released
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.input_state.trade_accept = False
            self.input_state.quest_accept = False
            self.input_state.faction_negotiate = False
            self.input_state.interact_npc = False
        elif key == pygame.K_SPACE:
            self.input_state.trade_accept = False
            self.input_state.quest_accept = False
            self.input_state.faction_negotiate = False
            self.input_state.interact_npc = False
        self._update_held_state()

    def _update_held_state(self) -> None:
        """Re-evaluate all movement / orbit / tilt flags from _held_keys."""
        held = self._held_keys

        self.input_state.move_up = pygame.K_w in held
        self.input_state.move_down = pygame.K_s in held
        self.input_state.move_left = pygame.K_a in held
        self.input_state.move_right = pygame.K_d in held
        # Left arrow → orbit CCW
        self.input_state.orbit_ccw = pygame.K_LEFT in held
        self.input_state.orbit_cw = (
            pygame.K_RIGHT in held
            or pygame.K_RSHIFT in held
            or pygame.K_RCTRL in held
            or self._mouse_held_button == 3
        )
        self.input_state.orbit_tilt_up = bool(held & {pygame.K_UP, pygame.K_PAGEUP})
        self.input_state.orbit_tilt_down = bool(held & {pygame.K_DOWN, pygame.K_PAGEDOWN})
        self.input_state.open_crafting = pygame.K_h in held

        if pygame.K_e in held:
            # E held → continuous interact flags stay True
            self.input_state.interact = True
            self.input_state.interact_npc = True
        else:
            # E released → clear continuous interact flags
            self.input_state.interact = False
            self.input_state.interact_pressed = False
            self.input_state.interact_npc = False
            self.input_state.interact_npc_pressed = False

    def _on_mouse_down(self, button: int, pos: Tuple[int, int]) -> None:
        """Handle mouse button press."""
        if button == 1:  # Left click — click-to-move
            self.input_state.click_to_move = True
            self.input_state.click_to_move_pos = pos
        elif button == 3:  # Right click — orbit CW (held)
            self._mouse_held_button = button
            self.input_state.orbit_cw = True

    def _on_mouse_up(self, button: int) -> None:
        """Handle mouse button release."""
        if button == self._mouse_held_button:
            self._mouse_held_button = 0
            # Right-click orbit CW ends
            self.input_state.orbit_cw = False

    def _on_mouse_motion(self, pos: Tuple[int, int]) -> None:
        """Handle mouse movement during right-click hold."""
        if self._mouse_held_button == 3:
            self.input_state.orbit_cw = True

    def _on_mouse_wheel(self, dy: int) -> None:
        """Handle mouse wheel scroll (one-shot flags for zoom)."""
        if dy > 0:
            self.input_state.zoom_in = True
        elif dy < 0:
            self.input_state.zoom_out = True

    def clear_frame(self) -> None:
        """Clear per-frame flags."""
        self.input_state.clear_frame()
