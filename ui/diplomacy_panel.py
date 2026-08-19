"""
diplomacy_panel.py — Faction diplomacy UI panel for player-NPC interactions.

Phase 3, Step 12: Diplomacy Panel UI.
"""

from __future__ import annotations

import os
import json
import pygame
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

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


class DiplomacyPanel:
    """Diplomacy panel: faction interaction UI."""

    # Panel geometry
    PANEL_X = 350
    PANEL_Y = 50
    PANEL_WIDTH = 500
    PANEL_HEIGHT = 400

    # Close button
    CLOSE_X = PANEL_X + PANEL_WIDTH - 28
    CLOSE_Y = PANEL_Y + 5
    CLOSE_SIZE = 22

    # Section positions
    TITLE_Y = 50
    FACTION_INFO_Y = 80
    HOSTILITY_BAR_Y = 140
    MONSTER_LIST_Y = 190
    NEGOTIATE_Y = 300
    STATUS_Y = 340
    STATUS_HEIGHT = 20
    FOOTER_Y = 370

    # Button geometry
    NEGOTIATE_BTN_WIDTH = 140
    NEGOTIATE_BTN_HEIGHT = 30
    NEGOTIATE_BTN_GAP = 10

    # Color palette
    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    CONTENT_BG = (35, 35, 45)
    TEXT_COLOR = (200, 200, 220)
    TEXT_DIM = (150, 150, 170)
    SUCCESS_COLOR = (100, 180, 100)
    ERROR_COLOR = (180, 100, 100)
    WARN_COLOR = (180, 150, 60)
    QTY_BTN = (70, 70, 90)
    QTY_BTN_HOVER = (90, 90, 110)
    NEGOTIATE_BTN = (80, 100, 140)
    NEGOTIATE_BTN_DISABLED = (45, 55, 75)

    # Hostility bar colors
    HOSTILE_COLOR = (180, 60, 60)      # 0.0-0.2
    SUSPICIOUS_COLOR = (180, 120, 40)   # 0.2-0.4
    NEUTRAL_COLOR = (120, 120, 120)     # 0.4-0.6
    FRIENDLY_COLOR = (80, 140, 80)      # 0.6-0.8
    ALLIED_COLOR = (100, 180, 100)      # 0.8-1.0

    # Bar geometry
    HOSTILITY_BAR_WIDTH = 300
    HOSTILITY_BAR_HEIGHT = 20
    HOSTILITY_BAR_Y = 150  # adjusted after bar title

    # Hostility level thresholds (matching existing naming conventions)
    LEVEL_HOSTILE = "hostile"        # base_hostility < 0.2
    LEVEL_SUSPICIOUS = "suspicious"  # base_hostility < 0.4
    LEVEL_NEUTRAL = "neutral"        # base_hostility < 0.6
    LEVEL_FRIENDLY = "friendly"      # base_hostility < 0.8
    LEVEL_ALLIED = "allied"          # base_hostility >= 0.8

    def __init__(self) -> None:
        self.visible: bool = False
        self._player_ref = None
        self._faction_info: "FactionInfo | None" = None
        self._selected_faction_leader = None
        self._hovered_btn: str = ""
        self._status_message: str = ""
        self._status_color: tuple = (200, 200, 220)
        self._button_rects = []
        self._font_title = pygame.font.SysFont("monospace", 14, bold=True)
        self._font_normal = pygame.font.SysFont("monospace", 11)
        self._font_small = pygame.font.SysFont("monospace", 10)
        self._font_bold = pygame.font.SysFont("monospace", 12, bold=True)
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
        self._button_rects = []
        return True

    def close_session(self) -> None:
        self._faction_info = None
        self._selected_faction_leader = None
        self._status_message = ""
        self._button_rects = []

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

    def render(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        px, py, pw, ph = self.PANEL_X, self.PANEL_Y, self.PANEL_WIDTH, self.PANEL_HEIGHT
        pygame.draw.rect(screen, self.BORDER_COLOR, (px, py, pw, ph), 2)
        pygame.draw.rect(screen, (160, 160, 180), (px + 3, py + 3, pw - 6, ph - 6), 1)
        bg_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg_surf.fill((*self.BG_COLOR, 240))
        screen.blit(bg_surf, (px, py))
        if self._faction_info is None:
            self._render_not_connected(screen)
            self._render_close_button(screen)
            return
        info = self._faction_info
        self._render_close_button(screen)
        # Title
        title_surf = self._font_title.render(f"Diplomacy: {info.name}", True, self.TEXT_COLOR)
        screen.blit(title_surf, (px + 10, self.TITLE_Y))
        # Faction info
        faction_text = f"Faction: {info.name}  |  Leader: {info.leader_name}"
        screen.blit(self._font_normal.render(faction_text, True, self.TEXT_COLOR), (px + 10, self.FACTION_INFO_Y))
        desc_text = info.description[:60] + "..." if len(info.description) > 60 else info.description
        screen.blit(self._font_small.render(desc_text, True, self.TEXT_DIM), (px + 10, self.FACTION_INFO_Y + 20))
        # Hostility bar
        self._render_hostility_bar(screen, info)
        # Hostile monsters
        self._render_hostile_monsters(screen, info)
        # Negotiate button
        self._render_negotiate_button(screen)
        # Status bar
        self._render_status_bar(screen)
        # Footer hint
        hint = self._font_small.render("Press ESC to close", True, self.TEXT_DIM)
        hint_x = px + (pw - hint.get_width()) // 2
        hint_y = self.FOOTER_Y
        screen.blit(hint, (hint_x, hint_y))

    def _render_hostility_bar(self, screen, info) -> None:
        y = self.HOSTILITY_BAR_Y
        # Use the faction system's current standing, not the base hostility from data
        relationship_score = 0.5  # default neutral
        if self._player_ref is not None and hasattr(self._player_ref, "game"):
            game = self._player_ref.game
            if game and hasattr(game, "faction_system") and game.faction_system:
                relationship_score = game.faction_system.get_standing(info.faction_id)
        hostility_color = self.get_hostility_color(relationship_score)
        level = self.get_hostility_level(relationship_score)
        # Bar background
        bar_x = self.PANEL_X + 10
        bar_w = self.HOSTILITY_BAR_WIDTH
        bar_h = self.HOSTILITY_BAR_HEIGHT
        pygame.draw.rect(screen, (60, 60, 60), (bar_x, y, bar_w, bar_h))
        # Fill
        fill_w = int(relationship_score * bar_w)
        pygame.draw.rect(screen, hostility_color, (bar_x, y, fill_w, bar_h))
        # Border
        pygame.draw.rect(screen, self.BORDER_COLOR, (bar_x, y, bar_w, bar_h), 1)
        # Label — show relationship score, not hostility level
        status_label = level.upper()
        label = f"Relationship: {relationship_score:.2f} ({status_label})"
        label_surf = self._font_normal.render(label, True, hostility_color)
        screen.blit(label_surf, (bar_x + bar_w + 10, y))

    def _render_hostile_monsters(self, screen, info) -> None:
        y = self.MONSTER_LIST_Y
        header_surf = self._font_bold.render("Associated Monsters:", True, self.TEXT_COLOR)
        screen.blit(header_surf, (self.PANEL_X + 10, y))
        y += 20
        if not info.hostile_monster_types:
            screen.blit(self._font_small.render("None", True, self.TEXT_DIM), (self.PANEL_X + 10, y))
        else:
            for i, monster in enumerate(info.hostile_monster_types):
                display_name = monster.replace("_", " ").title()
                if len(display_name) > 24:
                    display_name = display_name[:24] + "..."
                text = display_name if len(info.hostile_monster_types) > 1 else f"[E] {display_name} controls territory"
                surf = self._font_normal.render(text, True, self.TEXT_DIM)
                screen.blit(surf, (self.PANEL_X + 10, y + i * 16))

    def _render_negotiate_button(self, screen) -> None:
        btn_w = self.NEGOTIATE_BTN_WIDTH
        btn_h = self.NEGOTIATE_BTN_HEIGHT
        btn_x = self.PANEL_X + (self.PANEL_WIDTH - btn_w) // 2
        btn_y = self.NEGOTIATE_Y
        rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
        pygame.draw.rect(screen, self.NEGOTIATE_BTN, rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, rect, 1)
        text_surf = self._font_bold.render("Negotiate", True, (255, 255, 255))
        tx = btn_x + (btn_w - text_surf.get_width()) // 2
        ty = btn_y + (btn_h - text_surf.get_height()) // 2
        screen.blit(text_surf, (tx, ty))
        self._button_rects.append((rect, "negotiate"))

    def _render_status_bar(self, screen) -> None:
        sy = self.STATUS_Y
        sw = self.PANEL_WIDTH - 10
        pygame.draw.rect(screen, self.CONTENT_BG, (self.PANEL_X + 5, sy, sw, self.STATUS_HEIGHT))
        if self._status_message:
            surf = self._font_normal.render(self._status_message, True, self._status_color)
            sx = self.PANEL_X + 10
            screen.blit(surf, (sx, sy + (self.STATUS_HEIGHT - surf.get_height()) // 2))

    def _render_close_button(self, screen) -> None:
        cr = pygame.Rect(self.CLOSE_X, self.CLOSE_Y, self.CLOSE_SIZE, self.CLOSE_SIZE)
        hc = self.QTY_BTN_HOVER if self._hovered_btn == "close" else self.QTY_BTN
        pygame.draw.rect(screen, hc, cr)
        pygame.draw.rect(screen, self.BORDER_COLOR, cr, 1)
        pc = (255, 255, 255)
        p = 5
        pygame.draw.line(screen, pc, (self.CLOSE_X + p, self.CLOSE_Y + p), (self.CLOSE_X + self.CLOSE_SIZE - p, self.CLOSE_Y + self.CLOSE_SIZE - p), 2)
        pygame.draw.line(screen, pc, (self.CLOSE_X + self.CLOSE_SIZE - p, self.CLOSE_Y + p), (self.CLOSE_X + p, self.CLOSE_Y + self.CLOSE_SIZE - p), 2)
        self._button_rects.append((cr, "close"))

    def _render_not_connected(self, screen) -> None:
        msg = self._font_normal.render("No faction selected.", True, (180, 180, 200))
        mx = self.PANEL_X + (self.PANEL_WIDTH - msg.get_width()) // 2
        my = self.PANEL_Y + self.PANEL_HEIGHT // 2 - msg.get_height() // 2
        screen.blit(msg, (mx, my))

    def handle_mouse_move(self, mx: int, my: int) -> None:
        self._hovered_btn = ""
        cr = pygame.Rect(self.CLOSE_X, self.CLOSE_Y, self.CLOSE_SIZE, self.CLOSE_SIZE)
        if cr.collidepoint(mx, my):
            self._hovered_btn = "close"
            return
        for rect, action_id in self._button_rects:
            if rect.collidepoint(mx, my):
                self._hovered_btn = action_id
                return

    def handle_click(self, x: int, y: int) -> tuple:
        cr = pygame.Rect(self.CLOSE_X, self.CLOSE_Y, self.CLOSE_SIZE, self.CLOSE_SIZE)
        if cr.collidepoint(x, y):
            return ("close",)
        for rect, action_id in self._button_rects:
            if rect.collidepoint(x, y):
                if action_id == "negotiate":
                    return ("negotiate",)
        return None

    def handle_key(self, key: int) -> tuple | None:
        """
        Keyboard navigation for the diplomacy panel.

        Enter: return ("negotiate",)
        ESC: return ("close",)

        Returns None for navigation only; action tuple on Enter/ESC.
        """
        if key == pygame.K_RETURN:
            return ("negotiate",)
        elif key == pygame.K_ESCAPE:
            return ("close",)
        return None
