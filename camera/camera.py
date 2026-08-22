"""
camera.py — Orbital camera with separate yaw/pitch.

Player-centered camera with:
- yaw (horizontal orbit): Q/E or ←/→ arrows
  Controls which compass direction the camera is viewing from (0=below player, π=above).
- pitch (vertical tilt): ↑/↓ arrows
  Tilts within a 30°–60° isometric range.
- zoom: mouse wheel
- pan: PAGEUP/PAGEDOWN (manual offset)

The two axes are independent — yaw rotates the view around the player,
pitch tilts the camera height, giving true 2.5D orbital control.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from config import (
    CAMERA_ZOOM_MIN, CAMERA_ZOOM_MAX, CAMERA_ZOOM_DEFAULT,
    CAMERA_ORBIT_SPEED, CAMERA_TILT_SPEED, CAMERA_PITCH_MIN, CAMERA_PITCH_MAX,
)

if TYPE_CHECKING:
    from typing import Tuple
    from input.input_state import InputState


class Camera:
    """
    Player-centered camera with separate yaw and pitch orbit axes.

    The camera always centers on the player.

    Yaw (horizontal orbit, radians: -2π…2π):
        - 0   → looking from "below" (player's south)
        - π/2 → looking from "right" (player's east)
        - π   → looking from "above" (player's north)
        - 3π/2 → looking from "left" (player's west)

    Pitch (vertical tilt, radians: 30°…60°):
        - 30° → elevated isometric
        - 60° → steep isometric

    Both axes are independent and can be combined freely.
    """

    __slots__ = (
        "player", "yaw", "pitch", "zoom",
        "screen_width", "screen_height",
        "pan_x", "pan_y",
        "_prev_mouse_x", "_prev_mouse_y", "_mouse_held",
    )

    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        zoom: float = CAMERA_ZOOM_DEFAULT,
    ) -> None:
        """
        Initialize the camera.

        Args:
            screen_width: Display width in pixels.
            screen_height: Display height in pixels.
            zoom: Initial zoom level (0.5–2.0).
        """
        self.player: object | None = None  # Player reference (set by Game)
        self.yaw: float = 0.0             # Radians: 0=below, π/2=right, π=above
        self.pitch: float = math.radians(30.0)  # Radians: 30°–60° isometric range
        self.zoom: float = zoom
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.pan_x: float = 0.0           # Horizontal pan offset (px)
        self.pan_y: float = 0.0           # Vertical pan offset (px)
        self._prev_mouse_x = 0.0
        self._prev_mouse_y = 0.0
        self._mouse_held = False

    def set_player(self, player: object) -> None:
        """Set the camera's target player."""
        self.player = player

    def update(self, dt: float, input_state: InputState) -> None:
        """
        Update camera based on input state.

        Yaw (horizontal orbit): ←/→ arrows
        Pitch (vertical tilt): ↑/↓ arrows
        Zoom: mouse wheel

        Args:
            dt: Delta time in seconds.
            input_state: Current input state.
        """
        if self.player is None:
            return

        # ── Yaw (horizontal orbit) ────────────────────────────────
        yaw_delta = 0.0
        if input_state.orbit_cw:
            yaw_delta += CAMERA_ORBIT_SPEED
        if input_state.orbit_ccw:
            yaw_delta -= CAMERA_ORBIT_SPEED

        if yaw_delta != 0.0:
            self.yaw += math.radians(yaw_delta) * dt

        # ── Pitch (vertical tilt) ─────────────────────────────────
        pitch_delta = 0.0
        if input_state.orbit_tilt_up:
            pitch_delta += CAMERA_TILT_SPEED
        if input_state.orbit_tilt_down:
            pitch_delta -= CAMERA_TILT_SPEED

        if pitch_delta != 0.0:
            self.pitch += math.radians(pitch_delta) * dt
            # Clamp to [30°, 60°] — isometric range
            self.pitch = max(math.radians(CAMERA_PITCH_MIN),
                             min(self.pitch, math.radians(CAMERA_PITCH_MAX)))

        # ── Zoom (delta from mouse wheel) ─────────────────────────
        zoom_delta = 0.0
        if input_state.zoom_in:
            zoom_delta += 1.0
        if input_state.zoom_out:
            zoom_delta -= 1.0

        if zoom_delta != 0.0:
            zoom_delta_px = zoom_delta * 2.5 * self.zoom
            new_zoom = self.zoom + zoom_delta_px
            new_zoom = max(CAMERA_ZOOM_MIN, min(new_zoom, CAMERA_ZOOM_MAX))
            self.zoom = new_zoom
            # Consume the one-shot trigger
            if zoom_delta > 0:
                input_state.zoom_in = False
            else:
                input_state.zoom_out = False

        # ── Manual pan (PAGEUP/PAGEDOWN → pitch) ──────────────────
        # PAGEUP/PAGEDOWN now control pitch (vertical tilt) directly.
        # Manual pan offsets (pan_x/pan_y) are available for other
        # input methods (e.g. mouse drag) but not currently bound.

    def world_to_screen(
        self,
        world_x: float,
        world_y: float,
        elevation: float = 0,
    ) -> Tuple[float, float]:
        """
        Convert world coordinates to screen coordinates.

        Two-step transformation:
        1. **Yaw** — rotates the (dx, dy) offset around the player,
           determining which compass direction the camera faces.
        2. **Pitch** — stretches the Y offset by tan(pitch) to create
           2.5D depth perspective (flat at 0°, exaggerated at π/2°).
        3. **Elevation** — pushes higher objects up on screen
           by elevation * sin(pitch).

        Args:
            world_x: World X coordinate in pixels.
            world_y: World Y coordinate in pixels.
            elevation: Tile elevation offset (default 0).

        Returns:
            (screen_x, screen_y) tuple.
        """
        if self.player is None:
            return (world_x, world_y)

        # Offset from player
        dx = world_x - self.player.world_x
        dy = world_y - self.player.world_y

        # 1. Yaw: horizontal rotation around player (orbital yaw)
        cy = math.cos(self.yaw)
        sy = math.sin(self.yaw)
        yaw_x = dx * cy - dy * sy
        yaw_y = dx * sy + dy * cy

        # 2. Pitch: stretch world_Y for 2.5D perspective
        tp = math.tan(self.pitch)
        screen_x = (self.screen_width / 2 + yaw_x * self.zoom + self.pan_x)
        screen_y = (self.screen_height / 2 + yaw_y * tp * self.zoom
                    + self.pan_y - elevation * math.sin(self.pitch))

        return (screen_x, screen_y)

    def screen_to_world(
        self,
        screen_x: float,
        screen_y: float,
    ) -> Tuple[float, float]:
        """
        Convert screen coordinates to world coordinates.

        Reverse of world_to_screen:
        1. Undo pitch scaling (divide by tan(pitch))
        2. Undo yaw rotation (rotate by -yaw)

        Args:
            screen_x: Screen X coordinate in pixels.
            screen_y: Screen Y coordinate in pixels.

        Returns:
            (world_x, world_y) tuple.
        """
        if self.player is None:
            return (screen_x, screen_y)

        # Undo pan and zoom
        dx = (screen_x - self.pan_x - self.screen_width / 2) / self.zoom
        dy = (screen_y - self.pan_y - self.screen_height / 2) / self.zoom

        # Undo pitch scaling (tan(pitch) factor on world_y)
        tp = math.tan(self.pitch)
        if tp > 1e-6:
            dy = dy / tp
        else:
            # At top-down, pitch=0, all world_y collapses to center.
            # Set to 0 to avoid NaN — click-to-move will still work
            # for left/right targets since yaw affects dx directly.
            dy = 0.0

        # Undo yaw rotation
        cy = math.cos(-self.yaw)
        sy = math.sin(-self.yaw)
        world_dx = dx * cy - dy * sy
        world_dy = dx * sy + dy * cy

        return (self.player.world_x + world_dx, self.player.world_y + world_dy)

    def get_view_rect(self) -> Tuple[float, float, float, float]:
        """
        Get the visible world rectangle.

        Returns the world coordinates of the four corners of the
        camera's view, accounting for yaw, pitch, and zoom.

        Returns:
            (left, top, right, bottom) in world coordinates.
        """
        corners = [
            (0, 0),
            (self.screen_width, 0),
            (self.screen_width, self.screen_height),
            (0, self.screen_height),
        ]
        world_corners = [self.screen_to_world(x, y) for x, y in corners]
        left = min(x for x, y in world_corners)
        right = max(x for x, y in world_corners)
        top = min(y for x, y in world_corners)
        bottom = max(y for x, y in world_corners)
        return (left, top, right, bottom)
