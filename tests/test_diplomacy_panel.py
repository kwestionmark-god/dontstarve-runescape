"""
test_diplomacy_panel.py — Phase 3: Diplomacy panel on the PanelWindow base.

Covers the bounded/wrapped content, the visible scrollbar + mouse-wheel, the
unified keyboard/click routing (Enter/Escape, Negotiate, close), and the single
canonical negotiate path (no double-fire, no dead _execute_negotiation).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from ui.diplomacy_panel import DiplomacyPanel, FactionInfo


@pytest.fixture(autouse=True)
def _pygame():
    pygame.init()


def _session(panel, description=""):
    """Put the panel into an open session with a fake faction leader."""
    panel._player_ref = _player_with_standing(0.5)
    npc = type("NPC", (), {
        "faction_id": "forest_villagers",
        "name": "Elder Mara",
        "npc_id": "elder_mara",
        "npc_type": "faction_leader",
        "is_recruited": False,
    })()
    assert panel.open_session(npc) is True
    panel._faction_info.description = description
    return panel


def _player_with_standing(standing):
    """A fake player whose faction_system reports a fixed standing."""
    faction_system = type("FS", (), {
        "get_standing": staticmethod(lambda _fid: standing),
    })()
    game = type("G", (), {"faction_system": faction_system})()
    return type("P", (), {"game": game})()


def test_renders_without_error_and_is_bounded():
    panel = _session(DiplomacyPanel())
    panel.visible = True
    panel._player_ref = _player_with_standing(0.5)
    screen = pygame.Surface((800, 600))
    panel.render(screen)  # must not raise
    # The content viewport is clipped to the base's content_rect.
    assert panel.content_rect.width < panel.rect.width
    assert panel.content_rect.height <= panel.rect.height
    # set_clip is reset to full surface after render (pygame-ce behavior).
    assert screen.get_clip() == screen.get_rect()


def test_wheel_scrolls_and_clamps():
    panel = _session(DiplomacyPanel())
    panel._player_ref = _player_with_standing(0.5)
    # A tall description makes the content overflow the viewport.
    long_desc = ("The vampires of this realm are notoriously distrustful. " * 40)
    panel._faction_info.description = long_desc
    panel.visible = True
    panel.render(pygame.Surface((800, 600)))
    assert panel.max_offset > 0  # content overflows -> scrollbar active
    before = panel._scroll_offset
    panel.handle_wheel(1)  # wheel delta delivered via the base entry point
    assert panel._scroll_offset == before + 1
    # Scroll to the bottom, then a further delta must clamp.
    panel.scroll_by(10_000)
    assert panel._scroll_offset == panel.max_offset
    panel.handle_wheel(1)
    assert panel._scroll_offset == panel.max_offset


def test_enter_and_esc_route_to_actions():
    panel = _session(DiplomacyPanel())
    assert panel.handle_key(pygame.K_RETURN) == ("negotiate",)
    assert panel.handle_key(pygame.K_KP_ENTER) == ("negotiate",)
    assert panel.handle_key(pygame.K_ESCAPE) == ("close",)
    # Keyboard nav keys are consumed by the base and return None.
    assert panel.handle_key(pygame.K_w) is None
    assert panel.handle_key(pygame.K_UP) is None


def test_mouse_negotiate_and_close_clicks():
    panel = _session(DiplomacyPanel())
    panel.visible = True
    panel._player_ref = _player_with_standing(0.5)
    panel.render(pygame.Surface((800, 600)))

    # Find the negotiate button rect registered during draw.
    negotiate = next(rect for rect, payload in panel._interactive_rects if payload == "negotiate")
    assert panel.handle_click(negotiate.x + 3, negotiate.y + 3) == ("negotiate",)

    # Close button (top-right of the title strip) routes to ("close",).
    cr = panel._close_rect
    assert panel.handle_click(cr.x + 2, cr.y + 2) == ("close",)


def test_selection_highlights_negotiate_button():
    panel = _session(DiplomacyPanel())
    panel._player_ref = _player_with_standing(0.5)
    panel.visible = True
    panel.render(pygame.Surface((800, 600)))
    # The single action is selectable and highlighted once selected.
    assert panel.select_count() == 1
    assert panel._selected_index == 0  # auto-selected on open_session


def test_not_connected_state_renders_without_scrollbar_overflow():
    panel = DiplomacyPanel()
    panel.visible = True
    panel.render(pygame.Surface((800, 600)))
    assert panel._content_total_px <= panel.content_rect.height


# ── Canonical negotiate path (LIVE-ISSUES diplomacy bug) ──────────────────
class _SpyFactionSystem:
    def __init__(self):
        self.calls = 0

    def negotiate(self, player, faction_id):
        self.calls += 1
        return {"success": True, "message": "Negotiation successful!"}


class _SpyQuestSystem:
    def __init__(self):
        self.records = []

    def record_negotiation(self, faction_id):
        self.records.append(faction_id)


def _game_with_spy_flows():
    from interactions.npc_flows import NPCFlows
    from core.state import GameState
    faction_system = _SpyFactionSystem()
    quest_system = _SpyQuestSystem()
    action_system = type("AS", (), {
        "add_notification": lambda self, *a, **k: None,
    })()
    player = type("P", (), {"action_system": action_system})()
    mock_diplomacy_panel = type("P", (), {
        "_faction_info": FactionInfo(
            faction_id="forest_villagers", name="Forest Villagers", leader_name="Elder Mara",
            description="", hostile_monster_types=[], base_hostility=0.5,
        ),
        "close_session": lambda self: None,
    })()
    game = type("G", (), {
        "player": player,
        "faction_system": faction_system,
        "quest_system": quest_system,
        "ERROR_COLOR": (255, 0, 0),
        "SUCCESS_COLOR": (0, 255, 0),
        "_diplomacy_panel": mock_diplomacy_panel,
        "set_state": lambda self, state: None,
    })()
    flows = NPCFlows.__new__(NPCFlows)
    flows._game = game
    return flows, faction_system, quest_system


def test_execute_negotiation_applies_delta_and_records_once():
    """The single canonical negotiate path calls both sides exactly once."""
    flows, faction_system, quest_system = _game_with_spy_flows()
    flows.execute_negotiation()
    assert faction_system.calls == 1          # risked relationship delta applied
    assert quest_system.records == ["forest_villagers"]  # quest progress recorded


def test_handle_diplomacy_action_routes_to_canonical_execute():
    """The (formerly broken) mouse negotiate path is no longer a dead reference."""
    flows, faction_system, _ = _game_with_spy_flows()
    flows.handle_diplomacy_action(("negotiate",))
    assert faction_system.calls == 1


def test_handle_diplomacy_action_close_closes_panel():
    flows, _, _ = _game_with_spy_flows()
    closed = {"value": False}
    flows._close_diplomacy_panel = lambda: closed.__setitem__("value", True)
    flows.handle_diplomacy_action(("close",))
    assert closed["value"] is True


def test_no_dead_execute_negotiation_reference():
    """The dead `_execute_negotiation` method the mouse path used must not exist."""
    from interactions.npc_flows import NPCFlows
    assert not hasattr(NPCFlows, "_execute_negotiation")
