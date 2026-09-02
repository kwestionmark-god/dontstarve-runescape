"""
diplomacy_panel.py — Faction diplomacy UI panel for player-NPC interactions.

Phase 3 of docs/panel-ui-refactor-phase-plan.md: ``DiplomacyPanel`` subclasses
the reusable ``PanelWindow`` base and implements only its content layout via
``draw_contents`` — bounded/word-wrapped body text, a visible scrollbar,
keyboard navigation with a visible selection, and mouse-wheel scrolling. The
base owns the chrome, viewport clipping, scrollbar, close button and the
``handle_*`` entry points.

Canonical negotiate path (Phase 3 bug fix, LIVE-ISSUES diplomacy item): Enter /
Space and the mouse "Negotiate" button both return the ``("negotiate",)``
action, which the router / dispatcher funnel through the single
``NPCFlows.execute_negotiation`` — applying the risked faction delta *and*
recording quest progress. There is no longer a double-fire (keyboard ``on_key``
and router flag path both firing) nor the dead ``_execute_negotiation`` mouse
path.
"""

from __future__ import annotations

import os
import json
import pygame
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from npc.npc_types import FactionLeaderNPC


@dataclass
class FactionInfo:
    """Holds the data needed to render a diplomacy panel for one faction."""
    faction_id: str
    name: str
    leader_name: str
    description: str
    hostile_monster_types: list
    base_hostility: float
    negotiation_count: int = 0  # From QuestSystem


class DiplomacyPanel(PanelWindow):
    """Diplomacy panel: faction interaction UI (subclass of PanelWindow)."""

    # ── Palette (kept from the pre-refactor panel; shared ones match the base) ─
    TEXT_COLOR = (200, 200, 220)
    TEXT_DIM = (150, 150, 170)
    SUCCESS_COLOR = (100, 180, 100)
    ERROR_COLOR = (180, 100, 100)
    WARN_COLOR = (180, 150, 60)

    # Hostility/relationship bar colors
    HOSTILE_COLOR = (180, 60, 60)      # 0.0-0.2
    SUSPICIOUS_COLOR = (180, 120, 40)  # 0.2-0.4
    NEUTRAL_COLOR = (120, 120, 120)    # 0.4-0.6
    FRIENDLY_COLOR = (80, 140, 80)     # 0.6-0.8
    ALLIED_COLOR = (100, 180, 100)     # 0.8-1.0

    # Negotiate button geometry (px)
    NEGOTIATE_BTN_WIDTH = 140
    NEGOTIATE_BTN_HEIGHT = 30
    NEGOTIATE_BTN = (70, 70, 90)  # idle button color

    # Status bar height (px)
    STATUS_HEIGHT = 20

    # Hostility level thresholds (matching existing naming conventions)
    LEVEL_HOSTILE = "hostile"        # base_hostility < 0.2
    LEVEL_SUSPICIOUS = "suspicious"  # base_hostility < 0.4
    LEVEL_NEUTRAL = "neutral"        # base_hostility < 0.6
    LEVEL_FRIENDLY = "friendly"      # base_hostility < 0.8
    LEVEL_ALLIED = "allied"          # base_hostility >= 0.8

    # ── Session lifecycle ────────────────────────────────────────────────
    def __init__(self) -> None:
        super().__init__(
            title="Diplomacy",
            x=350,
            y=50,
            width=500,
            height=400,
            title_height=26,
            footer_height=0,
            has_scrollbar=True,
            show_close=True,
            selection_mode="list",
            row_gap=4,
        )
        self._player_ref = None
        self._faction_info: "FactionInfo | None" = None
        self._selected_faction_leader = None
        self._status_message: str = ""
        self._status_color: tuple = (200, 200, 220)
        # Total content height in px, set during draw_contents so the base can
        # size the scrollbar thumb (visible / total).
        self._content_total_px = 0
        self._faction_data: dict = {}
        self._load_faction_data()

    def set_player(self, player) -> None:
        self._player_ref = player

    def open_session(self, npc: "FactionLeaderNPC") -> bool:
        """Open a diplomacy session with the given faction leader."""
        if self._player_ref is None:
            self._set_status("Player not available.", self.ERROR_COLOR)
            return False
        faction_id = npc.faction_id
        faction = self._faction_data.get(faction_id)
        if faction is None:
            self._set_status(f"Faction '{faction_id}' not found.", self.ERROR_COLOR)
            return False
        leader_name = npc.name
        description = faction.get("description", "")
        hostile_monster_types = faction.get("hostile_monster_types", [])
        base_hostility = faction.get("base_hostility", 0.5)
        self._faction_info = FactionInfo(
            faction_id=faction_id,
            name=faction.get("name", faction_id),
            leader_name=leader_name,
            description=description,
            hostile_monster_types=hostile_monster_types,
            base_hostility=base_hostility,
        )
        self._selected_faction_leader = npc
        self._status_message = ""
        self._content_total_px = 0
        # The single "Negotiate" action is selectable once a session exists.
        self.select(0)
        return True

    def close(self) -> None:
        """Close the diplomacy panel and clean up session state."""
        self.close_session()
        super().close()

    def close_session(self) -> None:
        self._faction_info = None
        self._selected_faction_leader = None
        self._status_message = ""
        self._content_total_px = 0

    def _set_status(self, message: str, color: tuple = None) -> None:
        self._status_message = message
        if color is not None:
            self._status_color = color

    def _load_faction_data(self) -> None:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        filepath = os.path.join(data_dir, "factions.json")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            for faction in data.get("factions", []):
                fid = faction.get("faction_id", "")
                if fid:
                    self._faction_data[fid] = faction
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # ── Relationship / hostility helpers ─────────────────────────────────
    def get_hostility_color(self, hostility: float) -> tuple:
        if hostility < 0.2:
            return self.HOSTILE_COLOR
        elif hostility < 0.4:
            return self.SUSPICIOUS_COLOR
        elif hostility < 0.6:
            return self.NEUTRAL_COLOR
        elif hostility < 0.8:
            return self.FRIENDLY_COLOR
        else:
            return self.ALLIED_COLOR

    def get_hostility_level(self, hostility: float) -> str:
        if hostility < 0.2:
            return self.LEVEL_HOSTILE
        elif hostility < 0.4:
            return self.LEVEL_SUSPICIOUS
        elif hostility < 0.6:
            return self.LEVEL_NEUTRAL
        elif hostility < 0.8:
            return self.LEVEL_FRIENDLY
        else:
            return self.LEVEL_ALLIED

    def _read_relationship(self) -> float:
        """Current relationship score (0.0-1.0) for the open faction."""
        if self._player_ref is not None and hasattr(self._player_ref, "game"):
            game = self._player_ref.game
            if game is not None and hasattr(game, "faction_system") and game.faction_system:
                return game.faction_system.get_standing(self._faction_info.faction_id)
        return 0.5

    # ── PanelWindow hooks ────────────────────────────────────────────────
    def scroll_viewport(self):
        """(visible_units, total_units) — here expressed in pixels."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self):
        """One selectable action (the Negotiate button) when a session is open."""
        return 1 if self._faction_info is not None else 0

    def on_key(self, key: int):
        # Keyboard nav (WASD / arrows) is handled by the base before this.
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return ("negotiate",)
        if key == pygame.K_ESCAPE:
            return ("close",)
        return None

    def on_click(self, x: int, y: int, button: int = 1):
        for rect, payload in self._interactive_rects:
            if payload == "negotiate" and rect.collidepoint(x, y):
                return ("negotiate",)
        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        # The base already tracks hover over interactive rects; the negotiate
        # highlight follows keyboard selection, so nothing extra is needed.
        pass

    # ── Content drawing (the panel owns only this) ───────────────────────
    def draw_contents(self, screen, content_rect):
        self._interactive_rects.clear()
        info = self._faction_info
        if info is None:
            self._draw_not_connected(screen, content_rect)
            self._content_total_px = 0
            return

        left = content_rect.x + 10
        gap = self.row_gap
        y = content_rect.y - self._scroll_offset

        # Faction info line
        info_text = f"Faction: {info.name}  |  Leader: {info.leader_name}"
        surf = self.font_normal.render(info_text, True, self.TEXT_COLOR)
        screen.blit(surf, (left, y))
        y += surf.get_height() + gap

        # Description (word-wrapped, so it can never run off the right edge)
        for dsurf in self.wrap_text(info.description, content_rect.width - 20, self.TEXT_DIM):
            screen.blit(dsurf, (left, y))
            y += dsurf.get_height()
        y += gap

        # Relationship bar
        y = self._draw_relationship_bar(screen, content_rect, y, left) + gap

        # Associated monsters
        y = self._draw_monster_list(screen, content_rect, y, left, info, gap)

        # Negotiate button (single selectable action)
        btn_w = self.NEGOTIATE_BTN_WIDTH
        btn_h = self.NEGOTIATE_BTN_HEIGHT
        btn_x = content_rect.x + (content_rect.width - btn_w) // 2
        btn_y = y
        btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        color = self.ROW_SELECTED if self._selected_index == 0 else self.NEGOTIATE_BTN
        pygame.draw.rect(screen, color, btn_rect)
        pygame.draw.rect(screen, self.COLOR_BORDER, btn_rect, 1)
        text_surf = self.font_bold.render("Negotiate", True, (255, 255, 255))
        screen.blit(
            text_surf,
            (btn_x + (btn_w - text_surf.get_width()) // 2,
             btn_y + (btn_h - text_surf.get_height()) // 2),
        )
        self._interactive_rects.append((btn_rect, "negotiate"))
        y += btn_h + gap

        # Status bar
        self._draw_status_bar(screen, content_rect, y)
        y += self.STATUS_HEIGHT + gap

        # Footer hint
        hint = self.font_small.render("Press ESC to close", True, self.TEXT_DIM)
        hint_x = content_rect.x + (content_rect.width - hint.get_width()) // 2
        screen.blit(hint, (hint_x, y))

        self._content_total_px = y - content_rect.y

    def _draw_relationship_bar(self, screen, content_rect, y, left):
        bar_w = 300
        bar_h = 20
        score = self._read_relationship()
        color = self.get_hostility_color(score)
        level = self.get_hostility_level(score)
        pygame.draw.rect(screen, (60, 60, 60), (left, y, bar_w, bar_h))
        fill_w = int(score * bar_w)
        pygame.draw.rect(screen, color, (left, y, fill_w, bar_h))
        pygame.draw.rect(screen, self.COLOR_BORDER, (left, y, bar_w, bar_h), 1)
        label = f"Relationship: {score:.2f} ({level.upper()})"
        label_surf = self.font_normal.render(label, True, color)
        screen.blit(label_surf, (left, y + bar_h))
        return y + bar_h + label_surf.get_height()

    def _draw_monster_list(self, screen, content_rect, y, left, info, gap):
        header = self.font_bold.render("Associated Monsters:", True, self.TEXT_COLOR)
        screen.blit(header, (left, y))
        y += header.get_height() + gap
        monsters = info.hostile_monster_types
        if not monsters:
            none_surf = self.font_small.render("None", True, self.TEXT_DIM)
            screen.blit(none_surf, (left, y))
            y += none_surf.get_height()
        else:
            for monster in monsters:
                display = monster.replace("_", " ").title()
                for msurf in self.wrap_text(display, content_rect.width - 20, self.TEXT_DIM):
                    screen.blit(msurf, (left, y))
                    y += msurf.get_height()
        y += gap
        return y

    def _draw_status_bar(self, screen, content_rect, y):
        sw = content_rect.width - 10
        pygame.draw.rect(screen, self.CONTENT_BG, (content_rect.x + 5, y, sw, self.STATUS_HEIGHT))
        if self._status_message:
            surf = self.font_normal.render(self._status_message, True, self._status_color)
            screen.blit(surf, (content_rect.x + 10,
                               y + (self.STATUS_HEIGHT - surf.get_height()) // 2))

    def _draw_not_connected(self, screen, content_rect):
        msg = self.font_normal.render("No faction selected.", True, (180, 180, 200))
        mx = content_rect.x + (content_rect.width - msg.get_width()) // 2
        my = content_rect.y + (content_rect.height - msg.get_height()) // 2
        screen.blit(msg, (mx, my))
