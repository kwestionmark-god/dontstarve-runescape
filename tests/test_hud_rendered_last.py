"""Regression guard for HUD draw order.

The HUD (health/hunger/faction bars + damage flash) must be drawn *last* in
``Game.render_game`` so it is never occluded by the entity sprites, the
seasonal overlay, or an open panel. If the HUD render is moved earlier than the
panel/entity draws, these tests fail.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _render_game_body() -> list[str]:
    """Return the source lines of ``Game.render_game``'s body.

    Locates the ``def render_game`` line and collects lines until the next
    same-or-shallower-indented ``def``/decorator, which ends the method.
    """
    src = (ROOT / "core" / "game.py").read_text().splitlines()
    start = next(i for i, line in enumerate(src) if line.strip().startswith("def render_game("))
    indent = len(src[start]) - len(src[start].lstrip())
    body = []
    for line in src[start + 1:]:
        if line.strip() == "":
            body.append(line)
            continue
        cur = len(line) - len(line.lstrip())
        if cur <= indent and re.match(r"\s*(def |@)", line):
            break
        body.append(line)
    return body


def _call_line_indices(body: list[str], pattern: str) -> list[int]:
    return [i for i, line in enumerate(body) if re.search(pattern, line)]


def test_single_hud_render_call():
    """The HUD must be rendered exactly once in render_game."""
    body = _render_game_body()
    assert len(_call_line_indices(body, r"self\.hud\.render\(screen\)")) == 1


def test_hud_drawn_after_every_other_draw_call():
    """HUD render must come after every other .render/.draw(screen) call."""
    body = _render_game_body()
    hud_idx = _call_line_indices(body, r"self\.hud\.render\(screen\)")
    assert hud_idx, "expected self.hud.render(screen) in render_game"

    others = [i for i in _call_line_indices(body, r"\.(render|draw)\(screen\)")
              if "self.hud.render" not in body[i]]
    assert others, "expected at least one other draw call to order against"

    assert max(others) < min(hud_idx), (
        f"HUD drawn at body line {min(hud_idx)} but a draw call at body "
        f"line {max(others)} comes later — HUD would be occluded"
    )


def test_panel_groups_render_before_hud():
    """Concrete guard: the open-panel draws precede the HUD draw."""
    body = _render_game_body()
    hud_idx = min(_call_line_indices(body, r"self\.hud\.render\(screen\)"))
    panel_patterns = [r"_inventory_panel.render", r"_diplomacy_panel.render"]
    panel_idx = []
    for pat in panel_patterns:
        hits = _call_line_indices(body, pat)
        assert hits, f"expected a {pat} call to anchor the ordering"
        panel_idx.extend(hits)
    assert max(panel_idx) < hud_idx
