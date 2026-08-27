"""
quest_panel.py — Quest Journal UI panel (PanelWindow subclass).

Displays available, active, and completed quests with condition progress bars,
Accept buttons, and status messages. Integrates with QuestSystem and does not
duplicate quest business logic.
Subclasses PanelWindow for unified chrome, viewport clipping, scrollbar,
keyboard navigation with visible selection, and mouse-wheel scrolling.
"""

from __future__ import annotations

import json
import os

import pygame
from typing import TYPE_CHECKING

from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from npc.quest_system import QuestSystem, QuestProgress, QuestDefinition
    from npc.npc_types import QuestGiverNPC
    from core.player import Player


class QuestPanel(PanelWindow):
    """
    Quest Journal panel: Available / Active / Completed quest display.

    Layout:
    ┌────────────────────────────────────────────────────────────────────┐
    │  Quest Journal                                       [X]           │
    ├────────────────────────────────────────────────────────────────────┤
    │   [Available]  [Active]  [Completed]                            │
    ├────────────────────────────────────────────────────────────────────┤
    │  ┌──────────────────────────────────────────────────────────────┐│
    │  │  Timber Collection                                           ││
    │  │  Old Man Hemlock needs wood...                               ││
    │  │    [████████░░] 4/5 oak logs   (collect_item)               ││
    │  │  Requirements: Persuasion 1, Commerce 0, Intelligence 1     ││
    │  │                                              [Accept]        ││
    │  └──────────────────────────────────────────────────────────────┘│
    │  (scrollable content, up to 4 rows)                              │
    │  Scrollbar                                                       │
    │                                                                  │
    │  Status: Selected: Timber Collection — 4/5 oak logs             │
    │  Press ESC or U to close                                         │
    └────────────────────────────────────────────────────────────────────┘

    Returns action tuples from handle_click:
        ("close",) — close quest panel
        ("accept_quest", quest_id) — attempt to accept quest
    """

    # Panel geometry (passed to base __init__)
    PANEL_WIDTH = 460
    PANEL_HEIGHT = 580

    # Content area constants (for layout within content_rect)
    CONTENT_MAX_HEIGHT = 340
    MAX_VISIBLE_QUESTS = 4
    QUEST_ROW_HEIGHT = 72
    QUEST_ROW_GAP = 4

    # Tab bar constants
    TAB_Y = 70
    TAB_HEIGHT = 22
    TAB_WIDTH = 120
    TAB_GAP = 2

    # Status bar
    STATUS_HEIGHT = 25
    STATUS_Y = 540

    # Footer hint
    FOOTER_HEIGHT = 15
    FOOTER_Y = 560

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
        super().__init__(
            title="Quest Journal",
            x=250,
            y=30,
            width=460,
            height=580,
            title_height=26,
            footer_height=40,  # status bar + footer hint
            has_scrollbar=True,
            show_close=True,
            selection_mode="list",
            row_gap=4,
        )
        self.visible: bool = False

        # Wiring
        self.quest_system: "QuestSystem | None" = None
        self._player_ref: "Player | None" = None

        # Tab state
        self._tab: str = "available"  # "available" | "active" | "completed"
        self._hovered_tab: str = ""

        # Scroll
        self._scroll_offset: int = 0

        # Selected quest
        self._selected_quest_id: str | None = None
        self._selected_quest_index: int = -1

        # Status message
        self._status_message: str = ""
        self._status_color: tuple[int, int, int] = (200, 200, 220)

        # Rect caches (populated each render)
        self._tab_rects: list[tuple[pygame.Rect, str]] = []
        self._button_rects: list[tuple[pygame.Rect, str]] = []
        self._quest_rects: list[tuple[pygame.Rect, str]] = []  # (rect, quest_id)

        # NPC scope (for QuestGiverNPC sessions)
        self._giver_npc: "QuestGiverNPC | None" = None
        self._giver_npc_id: str = ""

        # Item name lookup cache
        self._item_names: dict[str, str] = {}
        self._load_item_names()

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

    # ── PanelWindow hooks ─────────────────────────────────────────────

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable quests in current tab."""
        quests = self._get_current_quests()
        return len(quests)

    def on_select(self, index: int) -> None:
        """Highlight the selected quest."""
        pass

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw quest panel content inside the clipped viewport."""
        self._interactive_rects.clear()
        self._tab_rects.clear()
        self._button_rects.clear()
        self._quest_rects.clear()

        if self.quest_system is None:
            self._render_not_connected(screen, content_rect)
            self._content_total_px = 0
            return

        # Use content_rect for all positioning
        left = content_rect.x + 10
        right = content_rect.x + content_rect.width - 10
        content_w = content_rect.width - 20
        top = content_rect.y
        bottom = content_rect.y + content_rect.height

        # Title (drawn by base class chrome, but we can add extra title here if needed)
        # The base class draws the title in the title bar

        # Tabs - positioned relative to content_rect
        tabs = [("Available", "available"), ("Active", "active"), ("Completed", "completed")]
        tab_x_start = left + (content_w - (3 * self.TAB_WIDTH + 2 * self.TAB_GAP)) // 2
        tab_y = self.TAB_Y  # Absolute Y since tabs are in title area
        for label, tab_id in tabs:
            x = tab_x_start + tabs.index((label, tab_id)) * (self.TAB_WIDTH + self.TAB_GAP)
            is_active = self._tab == tab_id
            tab_color = self.TAB_ACTIVE if is_active else self.TAB_INACTIVE
            tab_rect = pygame.Rect(x, tab_y, self.TAB_WIDTH, self.TAB_HEIGHT)
            pygame.draw.rect(screen, tab_color, tab_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, tab_rect, 1)
            label_surf = self.font_small.render(label, True, self.TEXT_COLOR)
            lx = x + (self.TAB_WIDTH - label_surf.get_width()) // 2
            ly = tab_y + (self.TAB_HEIGHT - label_surf.get_height()) // 2
            screen.blit(label_surf, (lx, ly))
            self._tab_rects.append((tab_rect, tab_id))
            self._interactive_rects.append((tab_rect, f"tab:{tab_id}"))

        # Content area background - use content_rect for scrollable area
        content_area_y = self.CONTENT_Y  # Absolute Y for content start
        content_area_h = self.CONTENT_MAX_HEIGHT
        pygame.draw.rect(
            screen, self.CONTENT_BG,
            (left, content_area_y, content_w, content_area_h),
        )

        # Render tab-specific content
        if self._tab == "available":
            self._render_available_tab(screen, left, content_area_y, content_w)
        elif self._tab == "active":
            self._render_active_tab(screen, left, content_area_y, content_w)
        elif self._tab == "completed":
            self._render_completed_tab(screen, left, content_area_y, content_w)

        # Status bar
        self._render_status_bar(screen)

        # Footer hint
        hint = self.font_small.render("Press ESC or U to close", True, self.TEXT_DIM)
        hint_x = self.rect.x + (self.rect.width - hint.get_width()) // 2
        hint_y = self.FOOTER_Y
        screen.blit(hint, (hint_x, hint_y))

        self._content_total_px = content_area_h + 50

    def _render_available_tab(self, screen: pygame.Surface, left: int, top: int, content_w: int) -> None:
        """Render available quests with Accept buttons, filtered by NPC if scoped."""
        if self._player_ref is None:
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

        self._render_quest_list(screen, quests, left, top, content_w, is_available=True)

    def _render_active_tab(self, screen: pygame.Surface, left: int, top: int, content_w: int) -> None:
        """Render active quests with condition progress bars."""
        quests = self.quest_system.get_active_quests()
        if not quests:
            return
        self._render_quest_list(screen, quests, left, top, content_w, is_available=False)

    def _render_completed_tab(self, screen: pygame.Surface, left: int, top: int, content_w: int) -> None:
        """Render completed quests (no progress, just name + reward info)."""
        quests = self.quest_system.get_completed_quests()
        if not quests:
            return
        self._render_quest_list(screen, quests, left, top, content_w, is_available=False)

    def _render_quest_list(self, screen: pygame.Surface, quests: list, left: int, top: int, content_w: int, is_available: bool = False) -> None:
        """Render a list of quests with scrolling."""
        # Clamp scroll offset
        max_offset = max(0, len(quests) - self.MAX_VISIBLE_QUESTS)
        self._scroll_offset = min(self._scroll_offset, max_offset)
        self._scroll_offset = max(0, self._scroll_offset)

        visible_quests = quests[self._scroll_offset:self._scroll_offset + self.MAX_VISIBLE_QUESTS]

        for i, quest in enumerate(visible_quests):
            row_y = top + i * (self.QUEST_ROW_HEIGHT + self.QUEST_ROW_GAP)

            # Determine quest_id and quest_def
            if is_available:
                quest_def = quest
                quest_id = quest_def.quest_id
                quest_progress = None
            else:
                quest_progress = quest
                quest_id = quest_progress.quest_id
                quest_def = self.quest_system.quest_definitions.get(quest_id) if self.quest_system else None

            is_selected = self._selected_quest_id == quest_id
            row_color = self.ROW_SELECTED if is_selected else self.ROW_BG
            pygame.draw.rect(
                screen, row_color,
                (left, row_y, content_w, self.QUEST_ROW_HEIGHT),
            )

            # Quest name
            name = quest_def.name if quest_def else quest_id
            name_surf = self.font_bold.render(name, True, self.TEXT_COLOR)
            screen.blit(name_surf, (left + 4, row_y + 2))

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
                screen.blit(desc_surf, (left + 4, row_y + 16))

            # Conditions
            conditions_start_y = row_y + 30
            conditions = quest_progress.conditions if quest_progress and quest_progress.conditions else []
            if not conditions and is_available and quest_def:
                conditions = quest_def.conditions

            cond_y = conditions_start_y
            for cond in conditions:
                cond_y = self._render_condition_bar(screen, cond, cond_y, left, content_w)
                cond_y += self.CONDITION_GAP

            # Requirements line (for available quests)
            if is_available and quest_def:
                req_y = max(cond_y, row_y + 52)
                pers = quest_def.min_persuasion
                comm = quest_def.min_commerce
                intel = quest_def.min_total_intelligence
                req_text = f"Requirements: Persuasion {pers}, Commerce {comm}, Intelligence {intel}"
                req_surf = self.font_small.render(req_text, True, self.TEXT_DIM)
                screen.blit(req_surf, (left + 4, req_y))

            # Accept button (for available quests)
            if is_available and quest_def:
                btn_y = max(cond_y, row_y + 54)
                if btn_y + 14 < row_y + self.QUEST_ROW_HEIGHT:
                    eligible = self._check_eligibility(quest_def)
                    btn_color = self.ACCEPT_BTN if eligible else self.ACCEPT_BTN_DISABLED
                    btn_w = 60
                    btn_h = 14
                    btn_x = left + content_w - btn_w - 4
                    btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                    pygame.draw.rect(screen, btn_color, btn_rect)
                    pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
                    btn_text = self.font_small.render("Accept", True, (255, 255, 255) if eligible else (150, 150, 170))
                    tx = btn_x + (btn_w - btn_text.get_width()) // 2
                    ty = btn_y + (btn_h - btn_text.get_height()) // 2
                    screen.blit(btn_text, (tx, ty))
                    self._button_rects.append((btn_rect, f"accept_{quest_id}"))
                    self._interactive_rects.append((btn_rect, f"accept_{quest_id}"))

            # Store quest rect for click detection
            quest_rect = pygame.Rect(left, row_y, content_w, self.QUEST_ROW_HEIGHT)
            self._quest_rects.append((quest_rect, quest_id))
            self._interactive_rects.append((quest_rect, f"quest:{quest_id}"))

    def _render_condition_bar(
        self, screen: pygame.Surface, condition, y: int, left: int, content_w: int,
    ) -> int:
        """Render a single condition progress bar. Returns the y position after the bar."""
        bar_w = int(content_w * 0.6)
        bar_x = left + 10
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
        status_w = self.rect.width - 20

        pygame.draw.rect(
            screen, self.CONTENT_BG,
            (self.rect.x + 10, status_y, status_w, self.STATUS_HEIGHT),
        )

        if self._status_message:
            status_surf = self.font_normal.render(self._status_message, True, self._status_color)
            sx = self.rect.x + 20
            sy = status_y + (self.STATUS_HEIGHT - status_surf.get_height()) // 2
            screen.blit(status_surf, (sx, sy))

    def _render_not_connected(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Render fallback message when quest system is not initialized."""
        msg = self.font_normal.render("Quest system not initialized.", True, (180, 180, 200))
        mx = content_rect.x + (content_rect.width - msg.get_width()) // 2
        my = content_rect.y + (content_rect.height - msg.get_height()) // 2
        screen.blit(msg, (mx, my))

    # ── Input handling ────────────────────────────────────────────────

    def on_key(self, key: int) -> tuple[str, ...] | None:
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
            self.select(max(-1, self._selected_index - 1))
            self._selected_quest_index = self._selected_index
            return None
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.select(min(len(quests) - 1, self._selected_index + 1))
            self._selected_quest_index = self._selected_index
            return None
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_quest_index < len(quests):
                quest = quests[self._selected_quest_index]
                return ("accept_quest", quest.quest_id)

        return None

    def on_click(self, x: int, y: int, button: int = 1) -> tuple[str, ...] | None:
        """
        Handle a mouse click on the quest panel.

        Routes clicks to the appropriate action based on which rect was hit.
        """
        # Check close button first (base class handles this, but we check tabs/buttons first)
        # Check tab clicks
        for tab_rect, tab_id in self._tab_rects:
            if tab_rect.collidepoint(x, y):
                self._tab = tab_id
                self._scroll_offset = 0
                self._selected_quest_id = None
                self._selected_quest_index = -1
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

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Track hovered tab, hover states for Accept buttons, and quest selection."""
        self._hovered_tab = ""

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

    # ── Compatibility methods (for game.py) ──────────────────────────

    def render(self, screen: pygame.Surface) -> None:
        """Render the quest panel (compatibility wrapper)."""
        super().render(screen)

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Track hovered tab, hover states for Accept buttons, and quest selection."""
        self.on_mouse_move(mx, my)

    def handle_click(self, x: int, y: int) -> tuple[str, ...] | None:
        """Handle a click on the quest panel (compatibility wrapper)."""
        return self.on_click(x, y)

    def handle_key(self, key: int) -> tuple[str, ...] | None:
        """Keyboard navigation (compatibility wrapper)."""
        return self.on_key(key)