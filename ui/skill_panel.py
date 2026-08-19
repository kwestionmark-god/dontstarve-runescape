"""
skill_panel.py — Skill list + stat allocation UI.

Shows all 3 active skills, their levels, XP progress, and unspent stat points.
Allows stat allocation via click buttons.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List, Optional

    from skills.skill_manager import SkillManager


class SkillPanel:
    """
    Skill panel: Shows all skills with XP progress and stat allocation.

    Layout:
    ┌──────────────────────────────────────────────┐
    │  ┌─ Woodcutting ─────────────────────────┐   │
    │  │ Level: 5    XP: 1,250 / 3,347        │   │
    │  │ Progress: ████████░░░░░░░░░░░░░░ 37% │   │
    │  │ Unspent Points: 15                    │   │
    │  │  Success Rate: [████░░] 3 pts [ + ]  │   │
    │  │  Harvest Boost: [██░░░░] 2 pts [ + ] │   │
    │  │  Stamina: [██████░░░░] 5 pts [ + ]   │   │
    │  └───────────────────────────────────────┘   │
    │  Wildcard Points: 0    [Escape to close]    │
    └──────────────────────────────────────────────┘
    """

    PANEL_X = 150
    PANEL_Y = 50
    PANEL_WIDTH = 500
    CARD_HEIGHT = 120
    CARD_GAP = 10

    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    CARD_BG = (40, 40, 50)
    PROGRESS_COLOR = (100, 180, 100)
    BUTTON_COLOR = (80, 120, 80)
    BUTTON_HOVER = (100, 150, 100)

    # Intelligence color coding
    COMMERCE_COLOR = (78, 106, 62)      # Green
    PERSUASION_COLOR = (184, 168, 64)    # Gold
    TRADE_COLOR = (62, 168, 158)         # Teal

    # Minus button colors
    MINUS_BTN_COLOR = (120, 80, 80)
    MINUS_BTN_HOVER = (150, 100, 100)

    # Wildcard toggle
    WILD_CARD_COLOR = (120, 120, 80)
    WILD_CARD_ACTIVE = (180, 180, 120)

    def __init__(self) -> None:
        self.skill_manager: "SkillManager | None" = None
        self.font_small = pygame.font.SysFont("monospace", 11)
        self.font = pygame.font.SysFont("monospace", 13)
        self.font_bold = pygame.font.SysFont("monospace", 14, bold=True)
        self.visible = False
        self._button_rects: List[tuple[pygame.Rect, str, str]] = []
        self._skill_buttons: List[tuple[pygame.Rect, str, str, bool]] = []  # (rect, label, sub_stat, is_minus)
        self._hovered_btn: str = ""
        self._use_wildcard: bool = False  # Toggle for wildcard allocation
        self._selected_skill_row: int = -1

    def set_skill_manager(self, skill_manager: "SkillManager") -> None:
        """Set the skill manager reference."""
        self.skill_manager = skill_manager

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Track which button the mouse is hovering over and sync selection."""
        self._hovered_btn = ""
        # Use _skill_buttons if populated, fall back to _button_rects for compatibility
        buttons = self._skill_buttons if self._skill_buttons else self._button_rects
        for i, item in enumerate(buttons):
            rect = item[0]
            if rect.collidepoint(mx, my):
                label = item[1]
                self._hovered_btn = label
                if len(item) == 4:
                    self._selected_skill_row = i
                return
        # Don't reset selection when not hovering

    def _format_xp(self, xp: float) -> str:
        """Format XP with commas."""
        return f"{int(xp):,}"

    def _draw_progress_bar(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
        width: int,
        height: int,
        percent: float,
        color: tuple[int, int, int] = (100, 180, 100),
    ) -> None:
        """Draw a simple progress bar."""
        # Background
        pygame.draw.rect(screen, (60, 60, 60), (x, y, width, height))
        # Fill
        fill_w = int(width * max(0.0, min(1.0, percent)))
        if fill_w > 0:
            pygame.draw.rect(screen, color, (x, y, fill_w, height))

    def _draw_sub_stat_bar(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
        width: int,
        height: int,
        points: int,
        max_points: int,
        color: tuple[int, int, int],
    ) -> None:
        """Draw a colored bar showing sub-stat allocation."""
        # Draw background track
        pygame.draw.rect(screen, (50, 50, 50), (x, y, width, height))
        # Draw filled portion
        if max_points > 0:
            fill_w = int(width * min(points / max_points, 1.0))
            if fill_w > 0:
                pygame.draw.rect(screen, color, (x, y, fill_w, height))
        # Draw border
        pygame.draw.rect(screen, (100, 100, 120), (x, y, width, height), 1)

    def render(self, screen: pygame.Surface) -> None:
        """
        Render the skill panel.

        Args:
            screen: The display surface.
        """
        if not self.visible or self.skill_manager is None:
            return

        snapshot = self.skill_manager.get_snapshot()
        self._button_rects = []
        self._skill_buttons = []

        panel_x = self.PANEL_X
        panel_y = self.PANEL_Y

        # Panel background (tall enough for all 6 skills)
        panel_full_height = 500
        pygame.draw.rect(screen, self.BG_COLOR, (panel_x, panel_y, self.PANEL_WIDTH, panel_full_height))
        pygame.draw.rect(screen, self.BORDER_COLOR, (panel_x, panel_y, self.PANEL_WIDTH, panel_full_height), 2)

        # Create clipping rect for panel content to prevent overflow
        panel_clip = pygame.Rect(panel_x, panel_y, self.PANEL_WIDTH, panel_full_height)

        # Title
        title = self.font_bold.render("Skills", True, (200, 200, 220))
        title_x = panel_x + (self.PANEL_WIDTH - title.get_width()) // 2
        screen.blit(title, (title_x, panel_y + 8))

        y_offset = panel_y + 35

        for skill_id, data in snapshot.items():
            level = data["level"]
            xp = data["xp"]
            stat_points = data["stat_points"]
            xp_progress = data["xp_progress"]
            sub_stats = data["sub_stats"]

            # Skill header
            name = skill_id.replace("_", " ").title()
            header = f"{name} (Lvl {level})"
            header_surf = self.font_bold.render(header, True, (200, 180, 120))
            screen.blit(header_surf, (panel_x + 10, y_offset))

            # XP progress
            xp_str = f"{self._format_xp(xp)}"
            next_xp = self.skill_manager.get_xp_for_level(level + 1) if level < 99 else None
            if next_xp is not None:
                xp_str += f" / {self._format_xp(next_xp)}"
            xp_surf = self.font.render(xp_str, True, (180, 180, 200))
            screen.blit(xp_surf, (panel_x + 180, y_offset))

            # Progress bar
            bar_w = 200
            bar_h = 8
            bar_x = panel_x + 10
            bar_y = y_offset + 22
            self._draw_progress_bar(screen, bar_x, bar_y, bar_w, bar_h, xp_progress)

            # Progress text
            pct_str = f"{int(xp_progress * 100)}%"
            pct_surf = self.font_small.render(pct_str, True, (150, 150, 170))
            pct_x = bar_x + bar_w + 5
            screen.blit(pct_surf, (pct_x, bar_y + 1))

            # Unspent points
            pts_str = f"Points: {stat_points}"
            pts_surf = self.font.render(pts_str, True, (150, 150, 170))
            pts_x = panel_x + 10
            pts_y = y_offset + 40
            screen.blit(pts_surf, (pts_x, pts_y))

            # Sub-stat bars and allocate buttons
            sy = y_offset + 55
            if skill_id == "intelligence":
                # ── Intelligence-specific rendering ──
                sub_stat_colors = {
                    "commerce": self.COMMERCE_COLOR,
                    "persuasion": self.PERSUASION_COLOR,
                    "trade": self.TRADE_COLOR,
                }
                # Import impact descriptions
                try:
                    from skills.intelligence.intelligence import (
                        COMMERCE_DESCRIPTION,
                        PERSUASION_DESCRIPTION,
                        TRADE_DESCRIPTION,
                    )
                except ImportError:
                    COMMERCE_DESCRIPTION = PERSUASION_DESCRIPTION = TRADE_DESCRIPTION = ""
                impact_map = {
                    "commerce": COMMERCE_DESCRIPTION,
                    "persuasion": PERSUASION_DESCRIPTION,
                    "trade": TRADE_DESCRIPTION,
                }

                bar_w = 160
                bar_h = 10
                btn_w = 16
                btn_h = 14

                for sub_stat, points in sub_stats.items():
                    stat_name = sub_stat.replace("_", " ").title()
                    color = sub_stat_colors.get(sub_stat, (150, 150, 170))

                    # Sub-stat label
                    stat_label = f"{stat_name}: {points}pts"
                    label_surf = self.font_small.render(stat_label, True, color)
                    screen.blit(label_surf, (pts_x, sy))

                    # Sub-stat allocation bar
                    bar_x = pts_x
                    bar_y = sy + 12
                    self._draw_sub_stat_bar(screen, bar_x, bar_y, bar_w, bar_h, points, 20, color)

                    # Impact text — truncate to fit panel width
                    impact_text = impact_map.get(sub_stat, "")
                    if impact_text:
                        max_chars = max(1, (panel_clip.width - pts_x - 10) // max(1, self.font_small.size("A")[0]))
                        if len(impact_text) > max_chars:
                            impact_text = impact_text[:max_chars - 1] + "…"
                        impact_surf = self.font_small.render(impact_text, True, (160, 160, 180))
                        screen.blit(impact_surf, (pts_x, bar_y + bar_h + 2))

                    # Plus and Minus buttons side by side
                    plus_btn_x = panel_x + self.PANEL_WIDTH - 50
                    minus_btn_x = plus_btn_x - btn_w - 2
                    btn_y = sy - 2

                    # Plus button
                    plus_rect = pygame.Rect(plus_btn_x, btn_y, btn_w, btn_h)
                    is_hovered = self._hovered_btn == f"{skill_id}_{sub_stat}_plus"
                    plus_color = self.BUTTON_HOVER if is_hovered else self.BUTTON_COLOR
                    pygame.draw.rect(screen, plus_color, plus_rect)
                    pygame.draw.rect(screen, self.BORDER_COLOR, plus_rect, 1)
                    plus_text = self.font_small.render("+", True, (255, 255, 255))
                    pt_x = plus_btn_x + (btn_w - plus_text.get_width()) // 2
                    pt_y = btn_y + (btn_h - plus_text.get_height()) // 2
                    screen.blit(plus_text, (pt_x, pt_y))
                    self._button_rects.append((plus_rect, skill_id, sub_stat))
                    self._skill_buttons.append((plus_rect, skill_id, sub_stat, False))

                    # Minus button
                    minus_rect = pygame.Rect(minus_btn_x, btn_y, btn_w, btn_h)
                    is_minus_hovered = self._hovered_btn == f"{skill_id}_{sub_stat}_minus"
                    minus_color = self.MINUS_BTN_HOVER if is_minus_hovered else self.MINUS_BTN_COLOR
                    pygame.draw.rect(screen, minus_color, minus_rect)
                    pygame.draw.rect(screen, self.BORDER_COLOR, minus_rect, 1)
                    minus_text = self.font_small.render("\u2212", True, (255, 255, 255))
                    mt_x = minus_btn_x + (btn_w - minus_text.get_width()) // 2
                    mt_y = btn_y + (btn_h - minus_text.get_height()) // 2
                    screen.blit(minus_text, (mt_x, mt_y))
                    self._button_rects.append((minus_rect, skill_id, f"_{sub_stat}"))
                    self._skill_buttons.append((minus_rect, skill_id, sub_stat, True))

                    sy += 48

                # Wildcard toggle button and summary line
                wc_btn_x = panel_x + 10
                wc_btn_y = sy + 5
                wc_btn_w = 50
                wc_btn_h = 18
                wc_rect = pygame.Rect(wc_btn_x, wc_btn_y, wc_btn_w, wc_btn_h)
                wc_color = self.WILD_CARD_ACTIVE if self._use_wildcard else self.WILD_CARD_COLOR
                # Visual feedback: glow effect when wildcard is active
                if self._use_wildcard:
                    glow_rect = wc_rect.inflate(4, 4)
                    glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                    glow_surf.fill((200, 200, 150, 80))
                    screen.blit(glow_surf, glow_rect.topleft)
                    pygame.draw.rect(screen, (220, 220, 180), glow_rect, 1)
                pygame.draw.rect(screen, wc_color, wc_rect)
                pygame.draw.rect(screen, self.BORDER_COLOR, wc_rect, 1)
                wc_text = self.font_small.render("[WC]", True, (255, 255, 255))
                wc_tx = wc_btn_x + (wc_btn_w - wc_text.get_width()) // 2
                wc_ty = wc_btn_y + (wc_btn_h - wc_text.get_height()) // 2
                screen.blit(wc_text, (wc_tx, wc_ty))
                self._button_rects.append((wc_rect, "toggle_wildcard", ""))
                self._skill_buttons.append((wc_rect, "toggle_wildcard", "", False))

                # Summary line: "Total: X / Y points"
                total_allocated = sum(sub_stats.values())
                max_points = 20  # reasonable cap for display
                summary_text = f"Total: {total_allocated} / {max_points} points"
                summary_surf = self.font_small.render(summary_text, True, (200, 200, 150))
                screen.blit(summary_surf, (wc_btn_x + wc_btn_w + 8, wc_btn_y + 2))
            else:
                # ── Standard rendering for non-Intelligence skills ──
                for sub_stat, points in sub_stats.items():
                    stat_name = sub_stat.replace("_", " ").title()
                    stat_label = f"{stat_name}: [{points}pts]"
                    label_surf = self.font_small.render(stat_label, True, (180, 180, 200))
                    screen.blit(label_surf, (pts_x, sy))

                    # Allocate button
                    btn_x = panel_x + self.PANEL_WIDTH - 50
                    btn_y = sy - 2
                    btn_w = 35
                    btn_h = 14
                    btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                    self._button_rects.append((btn_rect, skill_id, sub_stat))
                    self._skill_buttons.append((btn_rect, skill_id, sub_stat, False))
                    color = self.BUTTON_COLOR if stat_points > 0 else (60, 60, 60)
                    pygame.draw.rect(screen, color, btn_rect)
                    pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
                    btn_text = self.font_small.render("+", True, (255, 255, 255))
                    btn_tx = btn_x + (btn_w - btn_text.get_width()) // 2
                    btn_ty = btn_y + (btn_h - btn_text.get_height()) // 2
                    screen.blit(btn_text, (btn_tx, btn_ty))

                    sy += 16

            y_offset += self.CARD_HEIGHT + self.CARD_GAP

        # Wildcard points
        wc_str = f"Wildcard Points: {self.skill_manager.wildcard_points}"
        wc_surf = self.font.render(wc_str, True, (200, 200, 150))
        wc_x = panel_x + (self.PANEL_WIDTH - wc_surf.get_width()) // 2
        wc_y = y_offset + 5
        screen.blit(wc_surf, (wc_x, wc_y))

        # Close hint
        hint = self.font_small.render("Press ESC or J to close", True, (150, 150, 170))
        hint_x = panel_x + (self.PANEL_WIDTH - hint.get_width()) // 2
        hint_y = panel_y + panel_full_height - 20
        screen.blit(hint, (hint_x, hint_y))

    def handle_key(self, key: int) -> tuple[str, ...] | None:
        """
        Keyboard navigation for the skill panel.

        Arrow keys / WASD: navigate skill buttons
        Enter: return (label, sub_stat, 1) for + button, (label, sub_stat, -1) for - button
        + key: direct allocation (+1)
        - key: direct deallocation (-1)

        Returns None for navigation only; action tuple on Enter or +/- keys.
        """
        if key in (pygame.K_w, pygame.K_UP):
            self._selected_skill_row = max(-1, self._selected_skill_row - 1)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self._selected_skill_row = min(len(self._skill_buttons) - 1, self._selected_skill_row + 1)
        elif key in (pygame.K_a, pygame.K_LEFT):
            self._selected_skill_row = max(-1, self._selected_skill_row - 1)
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self._selected_skill_row = min(len(self._skill_buttons) - 1, self._selected_skill_row + 1)
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_skill_row < len(self._skill_buttons):
                _, label, sub_stat, is_minus = self._skill_buttons[self._selected_skill_row]
                if label == "toggle_wildcard":
                    return ("toggle_wildcard",)
                if is_minus:
                    return (label, sub_stat, -1)
                return (label, sub_stat, 1)
        elif key == pygame.K_PLUS or key == pygame.K_KP_PLUS:
            # Direct allocation on currently selected button
            if 0 <= self._selected_skill_row < len(self._skill_buttons):
                _, label, sub_stat, is_minus = self._skill_buttons[self._selected_skill_row]
                if label != "toggle_wildcard" and not is_minus:
                    return (label, sub_stat, 1)
        elif key == pygame.K_MINUS or key == pygame.K_KP_MINUS:
            # Direct deallocation on currently selected button
            if 0 <= self._selected_skill_row < len(self._skill_buttons):
                _, label, sub_stat, is_minus = self._skill_buttons[self._selected_skill_row]
                if label != "toggle_wildcard" and is_minus:
                    return (label, sub_stat, -1)
        return None

    def handle_click(self, x: int, y: int) -> tuple[str, ...] | None:
        """
        Handle a click on an allocate button.

        Args:
            x: Click X coordinate.
            y: Click Y coordinate.

        Returns:
            Action tuple:
                - ("toggle_wildcard",) for wildcard toggle click
                - (skill_id, sub_stat, -1) for deallocation (minus button)
                - (skill_id, sub_stat, 1) for allocation (plus button)
                - None otherwise.
        """
        for btn_rect, label, sub_stat in self._button_rects:
            if btn_rect.collidepoint(x, y):
                # Wildcard toggle button
                if label == "toggle_wildcard":
                    return ("toggle_wildcard",)

                # Minus button: sub_stat starts with underscore
                if sub_stat.startswith("_"):
                    return (label, sub_stat[1:], -1)

                # Plus button
                return (label, sub_stat, 1)
        return None
