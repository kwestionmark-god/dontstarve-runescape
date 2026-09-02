"""
skill_panel.py — Skill list + stat allocation UI (PanelWindow subclass).

Shows all skills with XP progress and stat allocation.
Subclasses PanelWindow for unified chrome, viewport clipping, scrollbar,
keyboard navigation with visible selection, and mouse-wheel scrolling.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from typing import Dict, List, Optional

    from skills.skill_manager import SkillManager


class SkillPanel(PanelWindow):
    """
    Skill panel: Shows all skills with XP progress and stat allocation.
    """

    # Color palette (shared with base where possible)
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
        super().__init__(
            title="Skills",
            x=240,   # clear of the HUD column (HUD spans to ~x=216)
            y=50,
            width=500,
            height=580,
            title_height=26,
            footer_height=22,
            has_scrollbar=True,
            show_close=True,
            selection_mode="list",
            row_gap=4,
        )
        self.skill_manager: "SkillManager | None" = None
        self._use_wildcard: bool = False
        # Runtime button rects: (rect, skill_id, sub_stat, is_minus)
        self._skill_buttons: list[tuple[pygame.Rect, str, str, bool]] = []

    def set_skill_manager(self, skill_manager: "SkillManager") -> None:
        """Set the skill manager reference."""
        self.skill_manager = skill_manager

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable items (all buttons across all skills)."""
        return len(self._skill_buttons)

    def on_select(self, index: int) -> None:
        """Highlight the selected button."""
        # Base draws selection highlight via draw_selected_row; we just track index.
        pass

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

    # ── PanelWindow hooks ────────────────────────────────────────────────

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw skill cards inside the clipped viewport."""
        self._interactive_rects.clear()
        self._skill_buttons.clear()

        if self.skill_manager is None:
            self._content_total_px = 0
            return

        snapshot = self.skill_manager.get_snapshot()
        left = content_rect.x + 10
        gap = self.row_gap
        y = content_rect.y - self._scroll_offset

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
            screen.blit(header_surf, (left, y))

            # XP progress
            xp_str = f"{self._format_xp(xp)}"
            next_xp = self.skill_manager.get_xp_for_level(level + 1) if level < 99 else None
            if next_xp is not None:
                xp_str += f" / {self._format_xp(next_xp)}"
            xp_surf = self.font_normal.render(xp_str, True, (180, 180, 200))
            screen.blit(xp_surf, (left + 170, y))

            # Progress bar
            bar_w = 200
            bar_h = 8
            bar_x = left
            bar_y = y + 22
            self._draw_progress_bar(screen, bar_x, bar_y, bar_w, bar_h, xp_progress)

            # Progress text
            pct_str = f"{int(xp_progress * 100)}%"
            pct_surf = self.font_small.render(pct_str, True, (150, 150, 170))
            pct_x = bar_x + bar_w + 5
            screen.blit(pct_surf, (pct_x, bar_y + 1))

            # Unspent points
            pts_str = f"Points: {stat_points}"
            pts_surf = self.font_normal.render(pts_str, True, (150, 150, 170))
            pts_x = left
            pts_y = y + 40
            screen.blit(pts_surf, (pts_x, pts_y))

            # Sub-stat bars and allocate buttons
            sy = y + 55
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
                        max_chars = max(1, (content_rect.width - pts_x - 10) // max(1, self.font_small.size("A")[0]))
                        if len(impact_text) > max_chars:
                            impact_text = impact_text[:max_chars - 1] + "…"
                        impact_surf = self.font_small.render(impact_text, True, (160, 160, 180))
                        screen.blit(impact_surf, (pts_x, bar_y + bar_h + 2))

                    # Plus and Minus buttons side by side
                    plus_btn_x = content_rect.x + content_rect.width - 50
                    minus_btn_x = plus_btn_x - btn_w - 2
                    btn_y = sy - 2

                    # Plus button
                    plus_rect = pygame.Rect(plus_btn_x, btn_y, btn_w, btn_h)
                    is_selected = self._is_button_selected(skill_id, sub_stat, False)
                    plus_color = self.BUTTON_HOVER if is_selected else self.BUTTON_COLOR
                    pygame.draw.rect(screen, plus_color, plus_rect)
                    pygame.draw.rect(screen, self.COLOR_BORDER, plus_rect, 1)
                    plus_text = self.font_small.render("+", True, (255, 255, 255))
                    pt_x = plus_btn_x + (btn_w - plus_text.get_width()) // 2
                    pt_y = btn_y + (btn_h - plus_text.get_height()) // 2
                    screen.blit(plus_text, (pt_x, pt_y))
                    self._interactive_rects.append((plus_rect, f"{skill_id}:{sub_stat}:1"))
                    self._skill_buttons.append((plus_rect, skill_id, sub_stat, False))

                    # Minus button
                    minus_rect = pygame.Rect(minus_btn_x, btn_y, btn_w, btn_h)
                    is_minus_selected = self._is_button_selected(skill_id, sub_stat, True)
                    minus_color = self.MINUS_BTN_HOVER if is_minus_selected else self.MINUS_BTN_COLOR
                    pygame.draw.rect(screen, minus_color, minus_rect)
                    pygame.draw.rect(screen, self.COLOR_BORDER, minus_rect, 1)
                    minus_text = self.font_small.render("\u2212", True, (255, 255, 255))
                    mt_x = minus_btn_x + (btn_w - minus_text.get_width()) // 2
                    mt_y = btn_y + (btn_h - minus_text.get_height()) // 2
                    screen.blit(minus_text, (mt_x, mt_y))
                    self._interactive_rects.append((minus_rect, f"{skill_id}:{sub_stat}:-1"))
                    self._skill_buttons.append((minus_rect, skill_id, sub_stat, True))

                    sy += 48

                # Wildcard toggle button and summary line
                wc_btn_x = left
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
                pygame.draw.rect(screen, self.COLOR_BORDER, wc_rect, 1)
                wc_text = self.font_small.render("[WC]", True, (255, 255, 255))
                wc_tx = wc_btn_x + (wc_btn_w - wc_text.get_width()) // 2
                wc_ty = wc_btn_y + (wc_btn_h - wc_text.get_height()) // 2
                screen.blit(wc_text, (wc_tx, wc_ty))
                self._interactive_rects.append((wc_rect, "toggle_wildcard"))
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
                    btn_x = content_rect.x + content_rect.width - 50
                    btn_y = sy - 2
                    btn_w = 35
                    btn_h = 14
                    btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                    is_selected = self._is_button_selected(skill_id, sub_stat, False)
                    color = self.BUTTON_HOVER if is_selected else (self.BUTTON_COLOR if stat_points > 0 else (60, 60, 60))
                    pygame.draw.rect(screen, color, btn_rect)
                    pygame.draw.rect(screen, self.COLOR_BORDER, btn_rect, 1)
                    btn_text = self.font_small.render("+", True, (255, 255, 255))
                    btn_tx = btn_x + (btn_w - btn_text.get_width()) // 2
                    btn_ty = btn_y + (btn_h - btn_text.get_height()) // 2
                    screen.blit(btn_text, (btn_tx, btn_ty))
                    self._interactive_rects.append((btn_rect, f"{skill_id}:{sub_stat}:1"))
                    self._skill_buttons.append((btn_rect, skill_id, sub_stat, False))

                    sy += 16

            y += 120 + gap  # CARD_HEIGHT + CARD_GAP

        # Wildcard points
        wc_str = f"Wildcard Points: {self.skill_manager.wildcard_points}"
        wc_surf = self.font_normal.render(wc_str, True, (200, 200, 150))
        wc_x = content_rect.x + (content_rect.width - wc_surf.get_width()) // 2
        wc_y = y + 5
        screen.blit(wc_surf, (wc_x, wc_y))

        # Footer hint
        hint = self.font_small.render("Press ESC or Tab to close", True, (150, 150, 170))
        hint_x = content_rect.x + (content_rect.width - hint.get_width()) // 2
        hint_y = content_rect.y + content_rect.height - 20
        screen.blit(hint, (hint_x, hint_y))

        self._content_total_px = y - content_rect.y + 30

    def _is_button_selected(self, skill_id: str, sub_stat: str, is_minus: bool) -> bool:
        """Check if a specific button is the currently selected one."""
        for i, (_, sid, sstat, iminus) in enumerate(self._skill_buttons):
            if sid == skill_id and sstat == sub_stat and iminus == is_minus:
                return i == self._selected_index
        return False

    def on_key(self, key: int):
        """Handle panel-specific keys: Enter to activate, +/- for direct alloc."""
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if 0 <= self._selected_index < len(self._skill_buttons):
                _, label, sub_stat, is_minus = self._skill_buttons[self._selected_index]
                if label == "toggle_wildcard":
                    return ("toggle_wildcard",)
                if is_minus:
                    return (label, sub_stat, -1)
                return (label, sub_stat, 1)
        elif key == pygame.K_PLUS or key == pygame.K_KP_PLUS:
            if 0 <= self._selected_index < len(self._skill_buttons):
                _, label, sub_stat, is_minus = self._skill_buttons[self._selected_index]
                if label != "toggle_wildcard" and not is_minus:
                    return (label, sub_stat, 1)
        elif key == pygame.K_MINUS or key == pygame.K_KP_MINUS:
            if 0 <= self._selected_index < len(self._skill_buttons):
                _, label, sub_stat, is_minus = self._skill_buttons[self._selected_index]
                if label != "toggle_wildcard" and is_minus:
                    return (label, sub_stat, -1)
        return None

    def on_click(self, x: int, y: int, button: int = 1):
        """Handle clicks on skill buttons."""
        for rect, payload in self._interactive_rects:
            if rect.collidepoint(x, y):
                if payload == "toggle_wildcard":
                    return ("toggle_wildcard",)
                # Parse payload: "skill_id:sub_stat:delta"
                try:
                    skill_id, sub_stat, delta_str = payload.split(":")
                    delta = int(delta_str)
                    return (skill_id, sub_stat, delta)
                except ValueError:
                    pass
        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Sync selection index on hover over buttons."""
        # Base already tracks hover; we just sync selection for visual feedback
        for i, (rect, _payload) in enumerate(self._interactive_rects):
            if rect.collidepoint(mx, my):
                self.select(i)
                return
        # Not hovering over any button: clear selection
        self.select(-1)