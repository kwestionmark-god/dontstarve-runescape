"""
input_state.py — InputState class.

Snapshot of current input state. Queried each frame by Player and Camera.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Tuple


class InputState:
    """
    Snapshot of current input state.

    Queried each frame by Player and Camera. Updated by InputManager
    from Pygame events.
    """

    __slots__ = (
        "move_up", "move_down", "move_left", "move_right",
        "interact", "interact_pressed",
        "interact_npc", "interact_npc_pressed",
        "open_inventory", "open_skill_panel", "open_crafting",
        "orbit_cw", "orbit_ccw",
        "orbit_tilt_up", "orbit_tilt_down",
        "zoom_in", "zoom_out",  # One-shot: set by wheel, cleared each frame
        "close_panel",
        "open_building_panel",
        "close_crafting",
        "open_quest_panel", "open_trade_panel", "open_recruit_panel", "open_diplomacy_panel",
        "click_to_move", "click_to_move_pos",
        "trade_accept", "trade_accept_pressed",
        "quest_accept", "quest_accept_pressed",
        "faction_negotiate", "faction_negotiate_pressed",
        "hotbar_slot",  # 1-8 one-shot flag for hotbar key presses
    )

    def __init__(self) -> None:
        # Movement
        self.move_up = False
        self.move_down = False
        self.move_left = False
        self.move_right = False

        # Actions
        self.interact = False
        self.interact_pressed = False  # True for exactly one frame

        # P3-S21: Explicit INTERACT_NPC flag
        self.interact_npc = False
        self.interact_npc_pressed = False

        # Panel toggles
        self.open_inventory = False
        self.open_skill_panel = False
        self.open_crafting = False
        self.open_building_panel = False
        self.open_quest_panel = False
        self.open_trade_panel = False
        self.open_recruit_panel = False
        self.open_diplomacy_panel = False

        # Camera controls
        self.orbit_cw = False
        self.orbit_ccw = False

        # Vertical orbit tilt (up/down arrows: tilt from top-down toward side-view)
        self.orbit_tilt_up = False
        self.orbit_tilt_down = False

        # Zoom
        self.zoom_in = False
        self.zoom_out = False

        # UI
        self.close_panel = False
        self.close_crafting = False

        # P3-S21: Keyboard confirm actions in panels
        self.trade_accept = False
        self.trade_accept_pressed = False
        self.quest_accept = False
        self.quest_accept_pressed = False
        self.faction_negotiate = False
        self.faction_negotiate_pressed = False

        # Mouse click-to-move
        self.click_to_move = False
        self.click_to_move_pos: Tuple[int, int] = (0, 0)

        # Hotbar (one-shot: set by key press, cleared each frame)
        self.hotbar_slot = 0  # 0 = none, 1-8 = slot pressed

    def clear_frame(self) -> None:
        """
        Reset per-frame / one-shot flags.

        Called once per frame. Does NOT reset held-key states
        (move_up, move_down, move_left, move_right, orbit_cw, orbit_ccw,
        orbit_tilt_up, orbit_tilt_down).
        """
        self.interact_pressed = False
        # P3-S21: Clear one-shot panel confirm flags
        self.interact_npc_pressed = False
        self.trade_accept_pressed = False
        self.quest_accept_pressed = False
        self.faction_negotiate_pressed = False
        self.click_to_move = False
        self.click_to_move_pos = (0, 0)
        self.close_panel = False
        self.open_inventory = False
        self.open_skill_panel = False
        self.open_crafting = False
        self.open_building_panel = False
        self.close_crafting = False
        self.open_quest_panel = False
        self.open_trade_panel = False
        self.open_recruit_panel = False
        self.open_diplomacy_panel = False
        # Zoom one-shots (set by wheel, cleared each frame)
        self.zoom_in = False
        self.zoom_out = False

        # Hotbar one-shot (set by key press, cleared each frame)
        self.hotbar_slot = 0
