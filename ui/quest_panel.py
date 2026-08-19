"""
quest_panel.py — Quest Journal UI panel.

Displays available, active, and completed quests with condition progress bars,
Accept buttons, and status messages. Integrates with QuestSystem (P3-S9)
and does not duplicate quest business logic.

Phase 3, Step 9: Quest Panel UI.
"""

from __future__ import annotations

import json
import os

import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from npc.quest_system import QuestSystem, QuestProgress, QuestDefinition
    from npc.npc_types import QuestGiverNPC
    from core.player import Player


class QuestPanel:
    """
    Quest Journal panel: Available / Active / Completed quest display.

    Layout (exact pixels):
    ┌────────────────────────────────────────────────────────────────────┐
    │  Quest Journal                                       [X]           │  y=45-65
    ├────────────────────────────────────────────────────────────────────┤
    │   [Available]  [Active]  [Completed]                            │  y=70-92
    ├────────────────────────────────────────────────────────────────────┤
    │  ┌──────────────────────────────────────────────────────────────┐│
    │  │  Timber Collection                                           ││
    │  │  Old Man Hemlock needs wood...                               ││
    │  │    [████████░░] 4/5 oak logs   (collect_item)               ││
    │  │  Requirements: Persuasion 1, Commerce 0, Intelligence 1     ││
    │  │                                              [Accept]        ││
    │  └──────────────────────────────────────────────────────────────┘│
    │  ┌──────────────────────────────────────────────────────────────┐│
    │  │  (scrollable content, up to 4 rows)                        ││
    │  └──────────────────────────────────────────────────────────────┘│
    │                                                                  │
    │  Scrollbar (y=435-445)                                          │
    │                                                                  │
    │  Status: Selected: Timber Collection — 4/5 oak logs             ││  y=540-565
    │  Press ESC or Y to close                                        ││  y=560-575
    └────────────────────────────────────────────────────────────────────┘

    Returns action tuples from handle_click:
        ("close",) — close quest panel
        ("accept_quest", quest_id) — attempt to accept quest
    """

    # Panel geometry
    PANEL_X = 250
    PANEL_Y = 30
    PANEL_WIDTH = 460
    PANEL_HEIGHT = 580

    # Title bar
    TITLE_Y = 45
    TITLE_HEIGHT = 20

    # Close button
    CLOSE_X = PANEL_X + PANEL_WIDTH - 28
    CLOSE_Y = PANEL_Y + 5
    CLOSE_SIZE = 22

    # Tab bar
    TAB_Y = 70
    TAB_HEIGHT = 22
    TAB_WIDTH = 120
    TAB_GAP = 2
    TAB_X_START = PANEL_X + (PANEL_WIDTH - (3 * TAB_WIDTH + 2 * TAB_GAP)) // 2

    # Content area (scrollable, 340px usable)
    CONTENT_X = PANEL_X + 10
    CONTENT_Y = 95
    CONTENT_WIDTH = PANEL_WIDTH - 20
    CONTENT_MAX_HEIGHT = 340
    MAX_VISIBLE_QUESTS = 4
    QUEST_ROW_HEIGHT = 72
    QUEST_ROW_GAP = 4

    # Status bar
    STATUS_Y = 540
    STATUS_HEIGHT = 25

    # Footer hint
    FOOTER_Y = 560
    FOOTER_HEIGHT = 15

    # Color palette (matches TradePanel)
    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    CONTENT_BG = (35, 35, 45)
    ROW_BG = (45, 45, 55)
    ROW_HIGHLIGHT = (65, 65, 85)
    ROW_SELECTED = (75, 60, 85)
    TEXT_COLOR = (200, 200, 220)
    TEXT_DIM = (150, 150, 170)
    SUCCESS_COLOR = (100, 180, 100)
    ERROR_COLOR = (180, 100, 100)
    WARN_COLOR = (180, 150, 60)
    TAB_ACTIVE = (60, 80, 120)
    TAB_INACTIVE = (40, 40, 55)
    QTY_BTN = (70, 70, 90)
    QTY_BTN_HOVER = (90, 90, 110)
    PROGRESS_COLOR = (100, 180, 100)
    PROGRESS_COLOR_INCOMPLETE = (180, 100, 100)
    ACCEPT_BTN = (60, 130, 80)
    ACCEPT_BTN_DISABLED = (45, 65, 45)

    # Condition detail sub-height within quest row
    CONDITION_GAP = 1

    def __init__(self) -> None:
        """Initialize the quest panel with default state and fonts."""
        # Visibility
        self.visible: bool = False

        # Wiring
        self.quest_system: "QuestSystem | None" = None
        self._player_ref: "Player | None" = None

        # Tab state
        self._tab: str = "available"  # "available" | "active" | "completed"
        self._hovered_tab: str = ""

        # Scroll
        self._scroll_offset: int = 0

        # Selected quest within visible rows (for potential expand/details view)
        self._selected_quest_id: str | None = None
        self._selected_quest_index: int = -1

        # Status message
        self._status_message: str = ""
        self._status_color: tuple[int, int, int] = (200, 200, 220)

        # Rect caches (populated each render)
        self._tab_rects: list[tuple[pygame.Rect, str]] = []
        self._button_rects: list[tuple[pygame.Rect, str]] = []
        self._quest_rects: list[tuple[pygame.Rect, str]] = []  # (rect, quest_id)

        # Fonts
        self.font_title = pygame.font.SysFont("monospace", 14, bold=True)
        self.font_normal = pygame.font.SysFont("monospace", 11)
        self.font_small = pygame.font.SysFont("monospace", 10)
        self.font_bold = pygame.font.SysFont("monospace", 12, bold=True)

        # Item name lookup cache
        self._item_names: dict[str, str] = {}

        # NPC scope (for QuestGiverNPC sessions)
        self._giver_npc: "QuestGiverNPC | None" = None  # QuestGiverNPC reference for scoping
        self._giver_npc_id: str = ""  # NPC ID for tracking

    # ── Wiring ────────────────────────────────────────────────────────

    def set_quest_system(self, qs: "QuestSystem") -> None:
        """Wire the QuestSystem reference."""
        self.quest_system = qs

    def set_player(self, player: "Player") -> None:
        """Wire the Player reference (for eligibility checks)."""
        self._player_ref = player

    # ── Session management ────────────────────────────────────────────

    def open_session(self, npc: "QuestGiverNPC | None" = None) -> bool:
        """
        Activate panel, load quest data, reset state.

        When npc is provided, scopes the Available tab to only that NPC's quests
        (E key NPC interaction path). When npc is None, opens the global quest
        journal (Y key toggle path).

        Args:
            npc: Optional QuestGiverNPC to scope the panel to.

        Returns:
            True if session opened successfully, False otherwise.
        """
        if self.quest_system is None:
            self._set_status("Quest system not available.", self.ERROR_COLOR)
            return False

        if npc is not None:
            if not hasattr(npc, "available_quests") or not npc.available_quests:
                self._set_status(f"{npc.name} has no quests available.", self.WARN_COLOR)
                return False
            self._giver_npc = npc
            self._giver_npc_id = npc.npc_id

        self._reset_quest_state()
        self._load_item_names()
        return True

    def close_session(self) -> None:
        """Reset all runtime state (scroll, selection, status). Clear NPC scope."""
        self._giver_npc = None
        self._giver_npc_id = ""
        self._reset_quest_state()
        self._status_message = ""

    def _reset_quest_state(self) -> None:
        """Clear scroll_offset, selected_quest_id, status, rects."""
        self._scroll_offset = 0
        self._selected_quest_id = None
        self._status_message = ""
        self._status_color = (200, 200, 220)
        self._tab_rects = []
        self._button_rects = []
        self._quest_rects = []

    # ── Item name loading ─────────────────────────────────────────────

    def _load_item_names(self) -> None:
        """Load item name mappings from items.json."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        filepath = os.path.join(data_dir, "items.json")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            for item in data.get("items", []):
                item_id = item.get("id", "")
                name = item.get("name", item_id)
                if item_id:
                    self._item_names[item_id] = name
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _get_item_name(self, item_id: str) -> str:
        """Get the display name for an item ID, falling back to item_id."""
        return self._item_names.get(item_id, item_id)

    # ── Status helpers ────────────────────────────────────────────────

    def _set_status(self, message: str, color: tuple[int, int, int] | None = None) -> None:
        """Set the status bar message and color."""
        self._status_message = message
        if color is not None:
            self._status_color = color

    # ── Rendering ─────────────────────────────────────────────────────

    def render(self, screen: pygame.Surface) -> None:
        """
        Render the complete quest panel.

        Args:
            screen: The display surface.
        """
        if not self.visible:
            return

        panel_x = self.PANEL_X
        panel_y = self.PANEL_Y
        panel_w = self.PANEL_WIDTH
        panel_h = self.PANEL_HEIGHT

        # Panel background — OSRS-style double-line border
        pygame.draw.rect(screen, self.BORDER_COLOR, (panel_x, panel_y, panel_w, panel_h), 2)
        pygame.draw.rect(screen, (160, 160, 180), (panel_x + 3, panel_y + 3, panel_w - 6, panel_h - 6), 1)
        bg_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg_surf.fill((*self.BG_COLOR, 240))
        screen.blit(bg_surf, (panel_x, panel_y))

        if self.quest_system is None:
            self._render_not_connected(screen)
        else:
            self._render_title(screen)
            self._render_close_button(screen)
            self._render_tabs(screen)
            self._render_content(screen)
            self._render_status_bar(screen)
            self._render_close_hint(screen)

    def _render_title(self, screen: pygame.Surface) -> None:
        """Render the panel title: 'Quest Journal'."""
        title_text = "Quest Journal"
        title_surf = self.font_title.render(title_text, True, self.TEXT_COLOR)
        title_x = self.PANEL_X + 10
        title_y = self.TITLE_Y
        screen.blit(title_surf, (title_x, title_y))

    def _render_close_button(self, screen: pygame.Surface) -> None:
        """Render the close (X) button in the top-right corner."""
        close_rect = pygame.Rect(
            self.CLOSE_X, self.CLOSE_Y,
            self.CLOSE_SIZE, self.CLOSE_SIZE,
        )
        hover_color = self.QTY_BTN_HOVER if self._hovered_tab == "close" else self.QTY_BTN
        pygame.draw.rect(screen, hover_color, close_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, close_rect, 1)

        # Draw X
        line_color = (255, 255, 255)
        padding = 5
        pygame.draw.line(
            screen, line_color,
            (self.CLOSE_X + padding, self.CLOSE_Y + padding),
            (self.CLOSE_X + self.CLOSE_SIZE - padding, self.CLOSE_Y + self.CLOSE_SIZE - padding),
            2,
        )
        pygame.draw.line(
            screen, line_color,
            (self.CLOSE_X + self.CLOSE_SIZE - padding, self.CLOSE_Y + padding),
            (self.CLOSE_X + padding, self.CLOSE_Y + self.CLOSE_SIZE - padding),
            2,
        )

        self._button_rects.append((close_rect, "close"))

    def _render_tabs(self, screen: pygame.Surface) -> None:
        """Render the Available / Active / Completed tab bar."""
        tabs = [("Available", "available"), ("Active", "active"), ("Completed", "completed")]
        self._tab_rects = []

        for label, tab_id in tabs:
            x = self.TAB_X_START
            # Offset for each tab
            idx = tabs.index((label, tab_id))
            x += idx * (self.TAB_WIDTH + self.TAB_GAP)

            is_active = self._tab == tab_id
            tab_color = self.TAB_ACTIVE if is_active else self.TAB_INACTIVE

            tab_rect = pygame.Rect(x, self.TAB_Y, self.TAB_WIDTH, self.TAB_HEIGHT)
            pygame.draw.rect(screen, tab_color, tab_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, tab_rect, 1)

            label_surf = self.font_small.render(label, True, self.TEXT_COLOR)
            lx = x + (self.TAB_WIDTH - label_surf.get_width()) // 2
            ly = self.TAB_Y + (self.TAB_HEIGHT - label_surf.get_height()) // 2
            screen.blit(label_surf, (lx, ly))

            self._tab_rects.append((tab_rect, tab_id))

    def _render_content(self, screen: pygame.Surface) -> None:
        """Dispatch to tab-specific renderers."""
        # Content area background
        pygame.draw.rect(
            screen, self.CONTENT_BG,
            (self.CONTENT_X, self.CONTENT_Y, self.CONTENT_WIDTH, self.CONTENT_MAX_HEIGHT),
        )

        if self._tab == "available":
            self._render_available_tab(screen)
        elif self._tab == "active":
            self._render_active_tab(screen)
        elif self._tab == "completed":
            self._render_completed_tab(screen)

        # Draw scrollbar if needed
        self._render_scrollbar(screen)

    def _render_scrollbar(self, screen: pygame.Surface) -> None:
        """Render a simple vertical scrollbar if content overflows."""
        quests = self._get_current_quests()
        if len(quests) <= self.MAX_VISIBLE_QUESTS:
            return

        scroll_x = self.CONTENT_X + self.CONTENT_WIDTH - 8
        scroll_y = self.CONTENT_Y
        scroll_h = self.CONTENT_MAX_HEIGHT
        scroll_w = 8

        # Scrollbar background
        pygame.draw.rect(screen, (30, 30, 35), (scroll_x, scroll_y, scroll_w, scroll_h))

        # Calculate thumb height based on visible fraction
        visible_ratio = self.MAX_VISIBLE_QUESTS / len(quests)
        thumb_h = max(20, int(scroll_h * visible_ratio))

        # Calculate thumb position
        max_offset = max(0, len(quests) - self.MAX_VISIBLE_QUESTS)
        thumb_ratio = self._scroll_offset / max_offset if max_offset > 0 else 0
        thumb_y = scroll_y + int(thumb_ratio * (scroll_h - thumb_h))

        pygame.draw.rect(screen, (80, 80, 100), (scroll_x, thumb_y, scroll_w, thumb_h))

    def _get_current_quests(self) -> list:
        """Return the quest list for the current tab."""
        if self.quest_system is None:
            return []
        if self._tab == "available":
            return self.quest_system.get_available_quests()
        elif self._tab == "active":
            return self.quest_system.get_active_quests()
        elif self._tab == "completed":
            return self.quest_system.get_completed_quests()
        return []

    def _render_available_tab(self, screen: pygame.Surface) -> None:
        """Render available quests with Accept buttons, filtered by NPC if scoped."""
        if self.quest_system is None or self._player_ref is None:
            return
        if self._giver_npc is not None:
            quest_ids = self._giver_npc.available_quests
            all_quests = self.quest_system.get_available_quests()
            quests = [q for q in all_quests if q.quest_id in quest_ids]
        else:
            quests = self.quest_system.get_available_quests()
        if not quests:
            if self._giver_npc is not None:
                self._set_status(f"{self._giver_npc.name} has no available quests.", self.WARN_COLOR)
            return

        self._render_quest_list(screen, quests, is_available=True)

    def _render_active_tab(self, screen: pygame.Surface) -> None:
        """Render active quests with condition progress bars."""
        if self.quest_system is None:
            return

        quests = self.quest_system.get_active_quests()
        if not quests:
            return

        self._render_quest_list(screen, quests, is_available=False)

    def _render_completed_tab(self, screen: pygame.Surface) -> None:
        """Render completed quests (no progress, just name + reward info)."""
        if self.quest_system is None:
            return

        quests = self.quest_system.get_completed_quests()
        if not quests:
            return

        self._render_quest_list(screen, quests, is_available=False)

    def _render_quest_list(self, screen: pygame.Surface, quests: list, is_available: bool = False) -> None:
        """Render a list of quests with scrolling."""
        panel_x = self.PANEL_X
        content_x = self.CONTENT_X
        content_y = self.CONTENT_Y
        content_w = self.CONTENT_WIDTH

        # Clamp scroll offset
        max_offset = max(0, len(quests) - self.MAX_VISIBLE_QUESTS)
        self._scroll_offset = min(self._scroll_offset, max_offset)
        self._scroll_offset = max(0, self._scroll_offset)

        visible_quests = quests[self._scroll_offset:self._scroll_offset + self.MAX_VISIBLE_QUESTS]

        self._quest_rects = []

        for i, quest in enumerate(visible_quests):
            row_y = content_y + i * (self.QUEST_ROW_HEIGHT + self.QUEST_ROW_GAP)

            # Determine quest_id and quest_def
            if is_available:
                # quest is a QuestDefinition
                quest_def = quest
                quest_id = quest_def.quest_id
                quest_progress = None
            else:
                # quest is a QuestProgress
                quest_progress = quest
                quest_id = quest_progress.quest_id
                quest_def = self.quest_system.quest_definitions.get(quest_id) if self.quest_system else None

            is_selected = self._selected_quest_id == quest_id
            row_color = self.ROW_SELECTED if is_selected else self.ROW_BG
            pygame.draw.rect(
                screen, row_color,
                (content_x, row_y, content_w, self.QUEST_ROW_HEIGHT),
            )

            # Quest name
            name = quest_def.name if quest_def else quest_id
            name_surf = self.font_bold.render(name, True, self.TEXT_COLOR)
            screen.blit(name_surf, (content_x + 4, row_y + 2))

            # Description (truncated to fit)
            desc = quest_def.description if quest_def else ""
            desc_surf = None
            if desc:
                desc_surf = self.font_small.render(desc, True, self.TEXT_DIM)
                if desc_surf.get_width() > content_w - 8:
                    max_chars = max(1, (content_w - 8) // 6)
                    desc_short = desc[:max_chars - 3] + "..."
                    desc_surf = self.font_small.render(desc_short, True, self.TEXT_DIM)

            if desc_surf:
                screen.blit(desc_surf, (content_x + 4, row_y + 16))

            # Conditions
            conditions_start_y = row_y + 30
            conditions = quest_progress.conditions if quest_progress and quest_progress.conditions else []
            if not conditions and is_available and quest_def:
                conditions = quest_def.conditions

            cond_y = conditions_start_y
            for cond in conditions:
                cond_y = self._render_condition_bar(screen, cond, cond_y, indent=10)
                cond_y += self.CONDITION_GAP

            # Requirements line (for available quests)
            if is_available and quest_def:
                req_y = max(cond_y, row_y + 52)
                pers = quest_def.min_persuasion
                comm = quest_def.min_commerce
                intel = quest_def.min_total_intelligence
                req_text = f"Requirements: Persuasion {pers}, Commerce {comm}, Intelligence {intel}"
                req_surf = self.font_small.render(req_text, True, self.TEXT_DIM)
                screen.blit(req_surf, (content_x + 4, req_y))

            # Accept button (for available quests)
            if is_available and quest_def:
                btn_y = max(cond_y, row_y + 54)
                if btn_y + 14 < row_y + self.QUEST_ROW_HEIGHT:
                    eligible = self._check_eligibility(quest_def)
                    btn_color = self.ACCEPT_BTN if eligible else self.ACCEPT_BTN_DISABLED
                    btn_w = 60
                    btn_h = 14
                    btn_x = content_x + content_w - btn_w - 4
                    btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                    pygame.draw.rect(screen, btn_color, btn_rect)
                    pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
                    btn_text = self.font_small.render("Accept", True, (255, 255, 255) if eligible else (150, 150, 170))
                    tx = btn_x + (btn_w - btn_text.get_width()) // 2
                    ty = btn_y + (btn_h - btn_text.get_height()) // 2
                    screen.blit(btn_text, (tx, ty))
                    self._button_rects.append((btn_rect, f"accept_{quest_id}"))

            # Store quest rect for click detection
            quest_rect = pygame.Rect(content_x, row_y, content_w, self.QUEST_ROW_HEIGHT)
            self._quest_rects.append((quest_rect, quest_id))

    def _render_condition_bar(
        self, screen: pygame.Surface, condition, y: int, indent: int = 10,
    ) -> int:
        """Render a single condition progress bar. Returns the y position after the bar."""
        content_x = self.CONTENT_X
        content_w = self.CONTENT_WIDTH

        bar_w = int(content_w * 0.6)
        bar_x = content_x + indent
        bar_y = y + 2
        bar_h = 10
        border_h = bar_h + 2

        current = getattr(condition, 'current_count', 0)
        required = getattr(condition, 'required_count', 1)

        # Progress ratio
        ratio = min(1.0, current / required) if required > 0 else 1.0
        fill_w = int(bar_w * ratio)

        # Bar background
        pygame.draw.rect(
            screen, (50, 50, 60),
            (bar_x, bar_y, bar_w, bar_h),
        )

        # Progress fill
        progress_color = self.PROGRESS_COLOR if ratio >= 1.0 else self.PROGRESS_COLOR_INCOMPLETE
        if fill_w > 0:
            pygame.draw.rect(
                screen, progress_color,
                (bar_x, bar_y, fill_w, bar_h),
            )

        # Border
        pygame.draw.rect(screen, self.BORDER_COLOR, (bar_x, bar_y, bar_w, bar_h), 1)

        # Condition text
        item_name = self._get_item_name(condition.target)
        cond_type = getattr(condition, 'condition_type', '')
        desc = getattr(condition, 'description', '')
        if desc:
            text = f"{desc}"
        else:
            text = f"{current}/{required} {item_name} ({cond_type})"

        text_surf = self.font_small.render(text, True, self.TEXT_COLOR)
        text_x = bar_x + bar_w + 4
        text_y = bar_y + (bar_h - text_surf.get_height()) // 2
        screen.blit(text_surf, (text_x, text_y))

        return y + border_h

    def _check_eligibility(self, quest_def: "QuestDefinition") -> bool:
        """Check if the player is eligible for a quest."""
        if self.quest_system is None or self._player_ref is None:
            return False
        result = self.quest_system.check_quest_eligibility(self._player_ref, quest_def)
        return result.eligible

    def _render_status_bar(self, screen: pygame.Surface) -> None:
        """Render the status message bar."""
        status_y = self.STATUS_Y
        status_w = self.CONTENT_WIDTH

        pygame.draw.rect(
            screen, self.CONTENT_BG,
            (self.CONTENT_X, status_y, status_w, self.STATUS_HEIGHT),
        )

        if self._status_message:
            status_surf = self.font_normal.render(self._status_message, True, self._status_color)
            sx = self.CONTENT_X + 10
            sy = status_y + (self.STATUS_HEIGHT - status_surf.get_height()) // 2
            screen.blit(status_surf, (sx, sy))

    def _render_close_hint(self, screen: pygame.Surface) -> None:
        """Render 'Press ESC or Y to close' hint."""
        hint = self.font_small.render("Press ESC or U to close", True, self.TEXT_DIM)
        hint_x = self.PANEL_X + (self.PANEL_WIDTH - hint.get_width()) // 2
        hint_y = self.FOOTER_Y
        screen.blit(hint, (hint_x, hint_y))

    def _render_not_connected(self, screen: pygame.Surface) -> None:
        """Render fallback message when quest system is not initialized."""
        panel_x = self.PANEL_X
        panel_y = self.PANEL_Y

        msg = self.font_normal.render("Quest system not initialized.", True, (180, 180, 200))
        mx = panel_x + (self.PANEL_WIDTH - msg.get_width()) // 2
        my = panel_y + self.PANEL_HEIGHT // 2 - msg.get_height() // 2
        screen.blit(msg, (mx, my))

    # ── Input handling ────────────────────────────────────────────────

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Track hovered tab, hover states for Accept buttons, and quest selection.

        Args:
            mx: Mouse X coordinate.
            my: Mouse Y coordinate.
        """
        self._hovered_tab = ""

        # Close button
        close_rect = pygame.Rect(
            self.CLOSE_X, self.CLOSE_Y,
            self.CLOSE_SIZE, self.CLOSE_SIZE,
        )
        if close_rect.collidepoint(mx, my):
            self._hovered_tab = "close"
            return

        # Tab buttons
        for tab_rect, tab_id in self._tab_rects:
            if tab_rect.collidepoint(mx, my):
                self._hovered_tab = f"tab_{tab_id}"
                return

        # Quest rows
        for idx, (quest_rect, quest_id) in enumerate(self._quest_rects):
            if quest_rect.collidepoint(mx, my):
                self._selected_quest_index = idx
                self._selected_quest_id = quest_id
                return
        # Don't reset selection when not hovering quest rows

    def handle_key(self, key: int) -> tuple[str, ...] | None:
        """
        Keyboard navigation for the quest panel.

        Tab / Left / Right: switch tabs
        Arrow keys / WASD: navigate quest list
        Enter: return ("accept_quest", quest_id)

        Returns None for navigation only; action tuple on Enter.
        """
        tabs = ["available", "active", "completed"]
        current_idx = tabs.index(self._tab)

        # Tab switching
        if key == pygame.K_TAB:
            new_idx = (current_idx + 1) % len(tabs)
            self._tab = tabs[new_idx]
            self._scroll_offset = 0
            self._selected_quest_id = None
            self._selected_quest_index = -1
            self._set_status("")
            return None
        elif key == pygame.K_LEFT and current_idx > 0:
            self._tab = tabs[current_idx - 1]
            self._scroll_offset = 0
            self._selected_quest_id = None
            self._selected_quest_index = -1
            self._set_status("")
            return None
        elif key == pygame.K_RIGHT and current_idx < len(tabs) - 1:
            self._tab = tabs[current_idx + 1]
            self._scroll_offset = 0
            self._selected_quest_id = None
            self._selected_quest_index = -1
            self._set_status("")
            return None

        # Quest navigation
        quests = self._get_current_quests()
        max_offset = max(0, len(quests) - self.MAX_VISIBLE_QUESTS)
        self._scroll_offset = min(self._scroll_offset, max_offset)

        if key in (pygame.K_w, pygame.K_UP):
            self._selected_quest_index = max(-1, self._selected_quest_index - 1)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self._selected_quest_index = min(len(quests) - 1, self._selected_quest_index + 1)
        elif key in (pygame.K_a, pygame.K_LEFT):
            self._selected_quest_index = max(-1, self._selected_quest_index - 1)
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self._selected_quest_index = min(len(quests) - 1, self._selected_quest_index + 1)
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_quest_index < len(quests):
                quest = quests[self._selected_quest_index]
                if hasattr(quest, 'quest_id'):
                    return ("accept_quest", quest.quest_id)
                return ("accept_quest", quest.quest_id)

        return None

    def handle_click(self, x: int, y: int) -> tuple[str, ...] | None:
        """
        Handle a mouse click on the quest panel.

        Routes clicks to the appropriate action based on which rect was hit.

        Args:
            x: Mouse X coordinate.
            y: Mouse Y coordinate.

        Returns:
            Action tuple, or None if the click was not on an actionable element.
        """
        # Check close button first
        close_rect = pygame.Rect(
            self.CLOSE_X, self.CLOSE_Y,
            self.CLOSE_SIZE, self.CLOSE_SIZE,
        )
        if close_rect.collidepoint(x, y):
            return ("close",)

        # Check tab clicks
        for tab_rect, tab_id in self._tab_rects:
            if tab_rect.collidepoint(x, y):
                self._tab = tab_id
                self._scroll_offset = 0
                self._selected_quest_id = None
                self._set_status("")
                return None

        # Check Accept buttons
        for btn_rect, action_id in self._button_rects:
            if btn_rect.collidepoint(x, y):
                if action_id.startswith("accept_"):
                    quest_id = action_id[7:]  # Strip "accept_"
                    return ("accept_quest", quest_id)
                return None

        # Check quest row clicks (for selection)
        for idx, (quest_rect, quest_id) in enumerate(self._quest_rects):
            if quest_rect.collidepoint(x, y):
                self._selected_quest_id = quest_id
                self._selected_quest_index = idx
                # Update status message
                self._set_status(f"Selected: {quest_id}")
                return None

        return None
