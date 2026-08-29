"""
config/keybindings.py — Single source of truth for all keybindings.

Maps action names to pygame key constants.
Used by InputManager, InputRouter, and UI panels for hints.
"""

from __future__ import annotations

import pygame
from core.state import GameState


# ─── Keybinding Constants ──────────────────────────────────────────────

# Gameplay actions (used by InputManager)
KEYBIND_ACTIONS = {
    # Movement
    "move_up": pygame.K_w,
    "move_down": pygame.K_s,
    "move_left": pygame.K_a,
    "move_right": pygame.K_d,
    # Panels
    "open_inventory": pygame.K_c,
    "open_inventory_alt": pygame.K_i,
    "open_skill_panel": pygame.K_TAB,
    "open_crafting": pygame.K_h,
    "open_building_panel": pygame.K_b,
    "open_quest_panel": pygame.K_u,
    "open_trade_panel": pygame.K_t,
    "open_recruit_panel": pygame.K_k,
    "open_diplomacy_panel": pygame.K_l,
    "open_gear_panel": pygame.K_g,
    "close_crafting": pygame.K_q,
    "close_panel": pygame.K_ESCAPE,
    # Interaction
    "interact": pygame.K_e,
    "confirm": pygame.K_RETURN,
    "confirm_alt": pygame.K_SPACE,
    "light_fire": pygame.K_f,
    "attack": pygame.K_j,
    # Camera
    "orbit_ccw": pygame.K_LEFT,
    "orbit_cw": pygame.K_RIGHT,
    "orbit_tilt_up": pygame.K_UP,
    "orbit_tilt_down": pygame.K_DOWN,
    "orbit_tilt_up_alt": pygame.K_PAGEUP,
    "orbit_tilt_down_alt": pygame.K_PAGEDOWN,
    # Hotbar (1-8)
    "hotbar_1": pygame.K_1,
    "hotbar_2": pygame.K_2,
    "hotbar_3": pygame.K_3,
    "hotbar_4": pygame.K_4,
    "hotbar_5": pygame.K_5,
    "hotbar_6": pygame.K_6,
    "hotbar_7": pygame.K_7,
    "hotbar_8": pygame.K_8,
    # Save
    "save_game": pygame.K_F5,
    # Quest-specific (one-shot)
    "quest_accept": pygame.K_RETURN,
    "faction_negotiate": pygame.K_RETURN,
    "trade_accept": pygame.K_RETURN,
}

# Panel-specific keybinds (used by panels for hints)
# These are actions that only apply when a specific panel is open
KEYBIND_PANEL_ACTIONS = {
    GameState.INVENTORY_OPEN: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Use item
    ],
    GameState.SKILL_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Allocate stat
    ],
    GameState.CRAFTING_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Craft item
        "confirm",   # Craft
    ],
    GameState.BUILDING_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Select structure
    ],
    GameState.GEAR_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
    ],
    GameState.TRADE_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Buy/sell
        "confirm",   # Accept trade
    ],
    GameState.QUEST_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Accept quest
        "confirm",   # Accept quest
    ],
    GameState.RECRUIT_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Recruit
    ],
    GameState.DIPLOMACY_PANEL: [
        "move_up", "move_down", "move_left", "move_right",
        "close_panel",
        "interact",  # Negotiate
        "confirm",   # Accept
    ],
}

# Human-readable names for UI hints
KEYBIND_DISPLAY_NAMES = {
    "move_up": "W",
    "move_down": "S",
    "move_left": "A",
    "move_right": "D",
    "open_inventory": "C",
    "open_skill_panel": "TAB",
    "open_crafting": "H",
    "open_building_panel": "B",
    "open_quest_panel": "U",
    "open_trade_panel": "T",
    "open_recruit_panel": "K",
    "open_diplomacy_panel": "L",
    "open_gear_panel": "G",
    "close_crafting": "Q",
    "close_panel": "ESC",
    "interact": "E",
    "confirm": "ENTER",
    "confirm_alt": "SPACE",
    "light_fire": "F",
    "attack": "J",
    "orbit_ccw": "←",
    "orbit_cw": "→",
    "orbit_tilt_up": "↑",
    "orbit_tilt_down": "↓",
    "orbit_tilt_up_alt": "PGUP",
    "orbit_tilt_down_alt": "PGDN",
    "hotbar_1": "1",
    "hotbar_2": "2",
    "hotbar_3": "3",
    "hotbar_4": "4",
    "hotbar_5": "5",
    "hotbar_6": "6",
    "hotbar_7": "7",
    "hotbar_8": "8",
    "save_game": "F5",
    "quest_accept": "ENTER",
    "faction_negotiate": "ENTER",
    "trade_accept": "ENTER",
}


def get_key_for_action(action: str) -> int:
    """Get the pygame key constant for a given action name."""
    return KEYBIND_ACTIONS.get(action, 0)


def get_actions_for_panel(state: GameState) -> list[str]:
    """Get the list of action names available in a panel state."""
    return KEYBIND_PANEL_ACTIONS.get(state, [])


def get_display_name(action: str) -> str:
    """Get the human-readable display name for an action."""
    return KEYBIND_DISPLAY_NAMES.get(action, action.upper())