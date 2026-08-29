"""
input_manager.py — InputManager class.

Translates Pygame events into InputState changes. Holds persistent
held-key states and single-frame triggered events.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from config.keybindings import KEYBIND_ACTIONS
from input.input_state import InputState

if TYPE_CHECKING:
    from typing import Tuple


class InputManager:
    """
    Translates Pygame events into InputState changes.

    Holds persistent held-key states and single-frame triggered events.
    Keybindings are sourced from config.keybindings.KEYBIND_ACTIONS.
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

        # Map key to action using config
        for action, action_key in KEYBIND_ACTIONS.items():
            if key == action_key:
                self._set_input_flag(action, True)
                break

        # Special cases that need multiple flags set
        if key == pygame.K_e:
            self.input_state.interact = True
            self.input_state.interact_pressed = True
            self.input_state.interact_npc = True
            self.input_state.interact_npc_pressed = True
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.input_state.trade_accept = True
            self.input_state.trade_accept_pressed = True
            self.input_state.quest_accept = True
            self.input_state.quest_accept_pressed = True
            self.input_state.faction_negotiate = True
            self.input_state.faction_negotiate_pressed = True
            self.input_state.interact_npc = True
            self.input_state.interact_npc_pressed = True
        elif key == pygame.K_SPACE:
            self.input_state.trade_accept = True
            self.input_state.trade_accept_pressed = True
            self.input_state.quest_accept = True
            self.input_state.quest_accept_pressed = True
            self.input_state.faction_negotiate = True
            self.input_state.faction_negotiate_pressed = True
            self.input_state.interact_npc = True
            self.input_state.interact_npc_pressed = True

    def _set_input_flag(self, action: str, value: bool) -> None:
        """Set an InputState flag by action name."""
        if action == "move_up":
            self.input_state.move_up = value
        elif action == "move_down":
            self.input_state.move_down = value
        elif action == "move_left":
            self.input_state.move_left = value
        elif action == "move_right":
            self.input_state.move_right = value
        elif action == "open_building_panel":
            self.input_state.open_building_panel = value
        elif action == "open_skill_panel":
            self.input_state.open_skill_panel = value
        elif action == "open_inventory":
            self.input_state.open_inventory = value
        elif action == "open_inventory_alt":
            self.input_state.open_inventory = value
        elif action == "open_crafting":
            self.input_state.open_crafting = value
        elif action == "open_quest_panel":
            self.input_state.open_quest_panel = value
        elif action == "open_trade_panel":
            self.input_state.open_trade_panel = value
        elif action == "open_recruit_panel":
            self.input_state.open_recruit_panel = value
        elif action == "open_diplomacy_panel":
            self.input_state.open_diplomacy_panel = value
        elif action == "close_crafting":
            self.input_state.close_crafting = value
        elif action == "close_panel":
            self.input_state.close_panel = value
        elif action == "interact":
            self.input_state.interact = value
        elif action == "confirm":
            self.input_state.trade_accept = value
            self.input_state.quest_accept = value
            self.input_state.faction_negotiate = value
            self.input_state.interact_npc = value
        elif action == "confirm_alt":
            self.input_state.trade_accept = value
            self.input_state.quest_accept = value
            self.input_state.faction_negotiate = value
            self.input_state.interact_npc = value
        elif action == "light_fire":
            self.input_state.light_fire = value
        elif action == "attack":
            self.input_state.attack = value
        elif action == "orbit_ccw":
            self.input_state.orbit_ccw = value
        elif action == "orbit_cw":
            self.input_state.orbit_cw = value
        elif action == "orbit_tilt_up":
            self.input_state.orbit_tilt_up = value
        elif action == "orbit_tilt_down":
            self.input_state.orbit_tilt_down = value
        elif action == "hotbar_1":
            self.input_state.hotbar_slot = 1
        elif action == "hotbar_2":
            self.input_state.hotbar_slot = 2
        elif action == "hotbar_3":
            self.input_state.hotbar_slot = 3
        elif action == "hotbar_4":
            self.input_state.hotbar_slot = 4
        elif action == "hotbar_5":
            self.input_state.hotbar_slot = 5
        elif action == "hotbar_6":
            self.input_state.hotbar_slot = 6
        elif action == "hotbar_7":
            self.input_state.hotbar_slot = 7
        elif action == "hotbar_8":
            self.input_state.hotbar_slot = 8
        elif action == "save_game":
            self.input_state.save_game = value

    def _on_key_up(self, key: int) -> None:
        """Handle a key release — re-evaluate based on held keys."""
        self._held_keys.discard(key)
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

        self.input_state.move_up = KEYBIND_ACTIONS["move_up"] in held
        self.input_state.move_down = KEYBIND_ACTIONS["move_down"] in held
        self.input_state.move_left = KEYBIND_ACTIONS["move_left"] in held
        self.input_state.move_right = KEYBIND_ACTIONS["move_right"] in held
        # Left arrow → orbit CCW
        self.input_state.orbit_ccw = KEYBIND_ACTIONS["orbit_ccw"] in held
        self.input_state.orbit_cw = (
            KEYBIND_ACTIONS["orbit_cw"] in held
            or pygame.K_RSHIFT in held
            or pygame.K_RCTRL in held
            or self._mouse_held_button == 3
        )
        self.input_state.orbit_tilt_up = bool(held & {KEYBIND_ACTIONS["orbit_tilt_up"], KEYBIND_ACTIONS["orbit_tilt_up_alt"]})
        self.input_state.orbit_tilt_down = bool(held & {KEYBIND_ACTIONS["orbit_tilt_down"], KEYBIND_ACTIONS["orbit_tilt_down_alt"]})
        self.input_state.open_crafting = KEYBIND_ACTIONS["open_crafting"] in held

        if KEYBIND_ACTIONS["interact"] in held:
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
