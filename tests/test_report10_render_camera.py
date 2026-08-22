"""Discriminating tests for Report 10 (Render & Camera).

Covers two mechanical defects:
  * Fix 1 — camera zoom races to max with no input (wrong initial `zoom_delta`).
  * Fix 2 — interaction prompt ignores tile elevation (vertical misalignment).

Both are tested against *real* behavior (real `Camera.update` / real
`render_proximity_prompt`), not source-text assertions.
"""

import types

import pygame
import pytest
from unittest import mock

from camera import Camera
from input.input_state import InputState
from config import CAMERA_ZOOM_MAX, CAMERA_ZOOM_MIN
from render.sprite_renderer import SpriteRenderer


@pytest.fixture
def camera_with_player():
    cam = Camera(1280, 720, zoom=1.8)
    cam.set_player(types.SimpleNamespace(world_x=0.0, world_y=0.0))
    return cam


def _input(**overrides):
    st = InputState()
    for k, v in overrides.items():
        setattr(st, k, v)
    return st


# ── Fix 1 — camera zoom one-shot semantics ──────────────────────────────

# Discriminating: current code adds 5*zoom per frame at rest → zoom == 3.0, not 1.8.
def test_no_zoom_input_does_not_change_zoom(camera_with_player):
    cam = camera_with_player
    cam.update(0.01, _input())  # neither zoom_in nor zoom_out set
    assert cam.zoom == 1.8


# Discriminating: at-rest the bug forces zoom UP; fix makes zoom_out decrease it.
def test_zoom_out_decreases_zoom(camera_with_player):
    cam = camera_with_player
    cam.update(0.01, _input(zoom_out=True))
    assert cam.zoom < 1.8


# Discriminating: after acting on the one-shot, the camera must consume zoom_out.
def test_zoom_out_is_a_true_one_shot(camera_with_player):
    cam = camera_with_player
    st = _input(zoom_out=True)
    cam.update(0.01, st)
    assert st.zoom_out is False


# Guard (passes before AND after): zoom_in still zooms in and respects the clamp.
def test_zoom_in_still_zooms_in_and_clamps(camera_with_player):
    cam = camera_with_player
    cam.update(0.01, _input(zoom_in=True))
    assert cam.zoom > 1.8
    assert cam.zoom <= CAMERA_ZOOM_MAX


# Guard: clamping bounds still hold after the fix.
def test_zoom_respects_minimum(camera_with_player):
    cam = Camera(1280, 720, zoom=CAMERA_ZOOM_MIN + 0.05)
    cam.set_player(types.SimpleNamespace(world_x=0.0, world_y=0.0))
    for _ in range(5):
        cam.update(0.01, _input(zoom_out=True))
    assert cam.zoom >= CAMERA_ZOOM_MIN - 1e-9


# ── Fix 2 — proximity prompt uses tile elevation ────────────────────────


class _FakeFont:
    """Bypass SysFont (no display needed); returns a surface of known width."""

    def render(self, text, aa, color):
        return pygame.Surface((len(text) * 8, 16))


def _npc(**overrides):
    data = {
        "world_x": 640.0, "world_y": 640.0,
        "npc_type": "merchant", "name": "Bob", "is_recruited": False,
    }
    data.update(overrides)
    return types.SimpleNamespace(**data)


class _BlitRecorder:
    """Captures blit calls. A real `pygame Surface.blit` is read-only and cannot
    be monkeypatched (raises AttributeError), so we drive the prompt with this proxy
    instead of patching the surface."""

    def __init__(self):
        self.calls = []

    def blit(self, surface, rect, *args, **kwargs):
        self.calls.append((surface, rect))
        return rect


def test_proximity_prompt_uses_tile_elevation():
    renderer = SpriteRenderer()
    renderer._font = _FakeFont()

    tile_map = mock.MagicMock()
    tile_map.get_tile_center_height.return_value = 2.5  # non-zero elevation
    renderer.tile_map = tile_map

    cam = Camera(1280, 720, zoom=1.8)
    cam.set_player(types.SimpleNamespace(world_x=0.0, world_y=0.0))

    npc = _npc()

    screen = _BlitRecorder()
    renderer.render_proximity_prompt(screen, npc, cam)

    text_rects = [
        rect
        for (surf, rect) in screen.calls
        if not (surf.get_flags() & pygame.SRCALPHA)   # text surface only; bg is SRCALPHA
    ]
    assert len(text_rects) == 1
    center = text_rects[0].center

    elevation = 2.5 * 8  # get_tile_center_height * Z_SCALE
    expected_y = cam.world_to_screen(npc.world_x, npc.world_y, elevation=elevation)[1] - 40
    flat_y = cam.world_to_screen(npc.world_x, npc.world_y)[1] - 40

    # (a) prompt aligns with the elevation-aware NPC position ...
    assert abs(center[1] - expected_y) < 0.5
    # (b) ... and elevation actually moved it (differs from the flat position).
    assert abs(center[1] - flat_y) > 1.0
