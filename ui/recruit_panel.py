"""
recruit_panel.py — Recruitment UI panel for player-NPC interactions (PanelWindow subclass).

Subclasses PanelWindow for unified chrome, viewport clipping, scrollbar,
keyboard navigation with visible selection, and mouse-wheel scrolling.
"""

from __future__ import annotations

import os
import json
import pygame
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from npc.npc_types import RecruitNPC
    from skills.intelligence.intelligence import EligibilityResult
    from core.player import Player


@dataclass
class RecruitInfo:
    """Holds the data needed to render a recruit panel for one NPC."""
    npc: "RecruitNPC"
    eligibility: "EligibilityResult"
    player_commerce: int = 0
    player_persuasion: int = 0
    player_composite: int = 0
    max_recruits: int = 0
    available_slots: int = 0


class RecruitPanel(PanelWindow):
    """Recruit panel: NPC recruitment UI."""

    # Panel geometry
    PANEL_X = 400
    PANEL_Y = 60
    PANEL_WIDTH = 460
    PANEL_HEIGHT = 330

    # Button geometry
    ACTION_BTN_WIDTH = 100
    ACTION_BTN_HEIGHT = 28
    ACTION_BTN_GAP = 10

    # Guard post section
    STRUCTURE_HEADER_Y_OFFSET = 0  # computed dynamically after behavior
    STRUCTURE_ROW_HEIGHT = 16
    STRUCTURE_MAX_ROWS = 3

    # Color palette (shared with base where possible)
    TEXT_COLOR = (200, 200, 220)
    TEXT_DIM = (150, 150, 170)
    SUCCESS_COLOR = (100, 180, 100)
    ERROR_COLOR = (180, 100, 100)
    TAB_ACTIVE = (60, 80, 120)
    TAB_INACTIVE = (40, 40, 55)
    RECRUIT_BTN = (80, 140, 80)
    RECRUIT_BTN_DISABLED = (45, 65, 45)
    CANCEL_BTN = (140, 100, 80)
    RADIO_SELECTED = (100, 160, 100)
    RADIO_UNSELECTED = (70, 70, 90)

    def __init__(self) -> None:
        super().__init__(
            title="Recruit",
            x=400,
            y=60,
            width=460,
            height=330,
            title_height=26,
            footer_height=22,
            has_scrollbar=True,
            show_close=True,
            selection_mode="list",
            row_gap=4,
        )
        self._player_ref: "Player | None" = None
        self._recruit_info: "RecruitInfo | None" = None
        self._selected_behavior: str = ""
        self._selected_structure_id: Optional[str] = None
        self._guard_posts: list[dict] = []
        self._structure_section_y: int = 0
        self._status_message: str = ""
        self._status_color: tuple[int, int, int] = (200, 200, 220)
        self._faction_names: dict[str, str] = {}
        self._load_faction_names()

        # Keyboard navigation
        self._selected_nav_index: int = -1
        self._nav_items: list[tuple[str, str, pygame.Rect]] = []  # (type, value, rect)

    def set_player(self, player: "Player") -> None:
        self._player_ref = player

    def open_session(self, npc: "RecruitNPC") -> bool:
        if self._player_ref is None:
            self._set_status("Player not available.", self.ERROR_COLOR)
            return False
        # SkillManager lives on the Player (player.skill_manager) — NOT on the
        # action system. The action system only holds survival/stamina.
        skill_manager = getattr(self._player_ref, "skill_manager", None)
        if skill_manager is None:
            self._set_status("Skill manager not available.", self.ERROR_COLOR)
            return False
        from skills.intelligence.intelligence import IntelligenceSkill
        intelligence = IntelligenceSkill(skill_manager)
        eligibility = intelligence.is_recruitment_eligible(npc, self._player_ref)
        commerce = skill_manager.get_effective_stat("intelligence", "commerce")
        persuasion = skill_manager.get_effective_stat("intelligence", "persuasion")
        self._recruit_info = RecruitInfo(
            npc=npc,
            eligibility=eligibility,
            player_commerce=commerce,
            player_persuasion=persuasion,
            player_composite=commerce + persuasion,
            max_recruits=intelligence.get_max_recruits(),
            available_slots=intelligence._get_available_recruit_slots(self._player_ref),
        )
        if len(npc.available_behaviors) == 1:
            self._selected_behavior = npc.available_behaviors[0]
        else:
            self._selected_behavior = ""
        self._selected_structure_id = None
        self._status_message = ""

        # Check if this NPC already has an assigned structure
        if self._recruit_info and self._recruit_info.npc:
            game = getattr(self._player_ref, "game", None)
            if game and hasattr(game, "npc_system") and game.npc_system:
                struct = game.npc_system.get_npc_structure(self._recruit_info.npc.npc_id)
                if struct:
                    self._selected_structure_id = struct.structure_def.structure_id

        self._load_guard_post_info()
        return True

    def close(self) -> None:
        """Close the recruit panel and clean up session state."""
        self.close_session()
        super().close()

    def close_session(self) -> None:
        self._recruit_info = None
        self._selected_behavior = ""
        self._status_message = ""

    def _set_status(self, message: str, color: tuple[int, int, int] | None = None) -> None:
        self._status_message = message
        if color is not None:
            self._status_color = color

    def _load_faction_names(self) -> None:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        filepath = os.path.join(data_dir, "factions.json")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            for faction in data.get("factions", []):
                fid = faction.get("faction_id", "")
                name = faction.get("name", fid)
                if fid:
                    self._faction_names[fid] = name
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _get_faction_name(self, faction_id: str) -> str:
        return self._faction_names.get(faction_id, faction_id or "Unknown")

    def _load_guard_post_info(self) -> None:
        """Load guard post structures from BuildingSystem for the current session."""
        if self._player_ref is None:
            self._guard_posts = []
            return
        game = getattr(self._player_ref, "game", None)
        if game is None or not hasattr(game, "building_system"):
            self._guard_posts = []
            return
        building = game.building_system
        if building is None:
            self._guard_posts = []
            return

        self._guard_posts = []
        for struct in building.get_guard_posts():
            self._guard_posts.append(
                {
                    "id": struct.structure_def.structure_id,
                    "name": struct.structure_def.name,
                    "x": int(struct.world_x // 64),
                    "y": int(struct.world_y // 64),
                    "assigned": struct.assigned_npc_id is not None,
                }
            )

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable items (behaviors + structures + actions)."""
        return len(self._nav_items)

    def on_select(self, index: int) -> None:
        """Highlight the selected item."""
        pass

    # ── PanelWindow hooks ────────────────────────────────────────────────

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        self._interactive_rects.clear()
        self._nav_items.clear()

        if self._recruit_info is None:
            self._draw_not_connected(screen, content_rect)
            self._content_total_px = 0
            return

        info = self._recruit_info
        npc = info.npc
        left = content_rect.x + 10
        gap = self.row_gap
        y = content_rect.y + self._scroll_offset

        # Title
        title_surf = self.font_bold.render(f"Recruit {npc.name}", True, self.TEXT_COLOR)
        screen.blit(title_surf, (left, content_rect.y + 5))

        faction_name = self._get_faction_name(npc.faction)
        status_text = "Eligible" if info.eligibility.eligible else "Not Eligible"
        status_color = self.SUCCESS_COLOR if info.eligibility.eligible else self.ERROR_COLOR
        row_text = f"Faction: {faction_name}     Status: {status_text}"
        row_surf = self.font_normal.render(row_text, True, status_color)
        screen.blit(row_surf, (left, y))
        y += 22

        # Stat requirements
        y = self._render_stat_requirements(screen, info, left, y) + gap

        # Slot info
        slot_color = self.SUCCESS_COLOR if info.available_slots > 0 else self.ERROR_COLOR
        slot_text = f"Recruit Slots: {info.available_slots} / {info.max_recruits}"
        slot_surf = self.font_normal.render(slot_text, True, slot_color)
        screen.blit(slot_surf, (left, y))
        y += 22

        # Behavior selection
        if len(npc.available_behaviors) > 1:
            y = self._render_behavior_selection(screen, npc, left, y) + gap

        # Guard structure assignment
        y = self._render_guard_structure_assignment(screen, left, y) + gap

        # Dialogue
        y = self._render_dialogue(screen, npc, left, y) + gap

        # Action buttons
        y = self._render_action_buttons(screen, info, content_rect, y) + gap

        # Footer hint
        hint = self.font_small.render("Press ESC to close", True, self.TEXT_DIM)
        hint_x = content_rect.x + (content_rect.width - hint.get_width()) // 2
        screen.blit(hint, (hint_x, y))

        self._content_total_px = y - content_rect.y + 20

    def _render_stat_requirements(self, screen, info, left, y):
        commerce_req = info.npc.recruit_commerce_requirement
        persuasion_req = info.npc.recruit_persuasion_requirement
        composite_req = info.npc.recruit_composite_stat
        commerce_ok = info.player_commerce >= commerce_req
        commerce_color = self.SUCCESS_COLOR if commerce_ok else self.ERROR_COLOR
        commerce_text = f"Commerce: {commerce_req}  (You have: {info.player_commerce})  {'OK' if commerce_ok else 'FAIL'}"
        screen.blit(self.font_normal.render(commerce_text, True, commerce_color), (left, y))
        y += 18
        persuasion_ok = info.player_persuasion >= persuasion_req
        persuasion_color = self.SUCCESS_COLOR if persuasion_ok else self.ERROR_COLOR
        persuasion_text = f"Persuasion: {persuasion_req}  (You have: {info.player_persuasion})  {'OK' if persuasion_ok else 'FAIL'}"
        screen.blit(self.font_normal.render(persuasion_text, True, persuasion_color), (left, y))
        y += 18
        composite_ok = info.player_composite >= composite_req
        composite_color = self.SUCCESS_COLOR if composite_ok else self.ERROR_COLOR
        composite_text = f"Composite: {composite_req}  (You have: {info.player_composite})  {'OK' if composite_ok else 'FAIL'}"
        screen.blit(self.font_normal.render(composite_text, True, composite_color), (left, y))
        return y

    def _render_behavior_selection(self, screen, npc, left, y):
        header_surf = self.font_bold.render("Behavior Selection:", True, self.TEXT_COLOR)
        screen.blit(header_surf, (left, y))
        y += 18
        for i, behavior in enumerate(npc.available_behaviors):
            row_y = y + i * 18
            is_selected = self._selected_behavior == behavior
            circle_x = left + 4
            circle_y = row_y + 6
            circle_r = 6
            circle_color = self.RADIO_SELECTED if is_selected else self.RADIO_UNSELECTED
            pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r)
            if is_selected:
                pygame.draw.circle(screen, (35, 35, 45), (circle_x, circle_y), circle_r - 2)
                pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r - 2, 2)
            label_surf = self.font_normal.render(behavior.capitalize(), True, self.TEXT_COLOR)
            screen.blit(label_surf, (left + 20, row_y))
            rect = pygame.Rect(left, row_y, 120, 18)
            self._interactive_rects.append((rect, f"behavior:{behavior}"))
            self._nav_items.append(("behavior", behavior, rect))
        y += len(npc.available_behaviors) * 18
        return y

    def _render_guard_structure_assignment(self, screen, left, y):
        """Render guard post structure assignment section. Only shown when selected behavior is 'guard'."""
        if self._recruit_info is None or self._recruit_info.npc is None:
            return y
        if self._selected_behavior != "guard":
            return y
        if not self._guard_posts:
            self._set_status("No guard posts available. Build a ballista, trebuchet, or wall tower.", self.TEXT_DIM)
            return y

        self._structure_section_y = y
        header_surf = self.font_bold.render("Guard Posts:", True, self.TEXT_COLOR)
        screen.blit(header_surf, (left, y))
        y += 18

        for i, post in enumerate(self._guard_posts):
            if i >= self.STRUCTURE_MAX_ROWS:
                break
            row_y = y + i * self.STRUCTURE_ROW_HEIGHT
            is_selected = self._selected_structure_id == post["id"]
            circle_x = left + 4
            circle_y = row_y + 6
            circle_r = 5
            circle_color = self.RADIO_SELECTED if is_selected else self.RADIO_UNSELECTED
            pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r)
            if is_selected:
                pygame.draw.circle(screen, (35, 35, 45), (circle_x, circle_y), circle_r - 2)
                pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r - 2, 2)

            label = f"{post['name']} ({post['x']},{post['y']})"
            if post["assigned"]:
                label += " [Assigned]"
            label_surf = self.font_normal.render(label, True, self.TEXT_DIM if post["assigned"] else self.TEXT_COLOR)
            screen.blit(label_surf, (left + 20, row_y))

            rect = pygame.Rect(left, row_y, 200, self.STRUCTURE_ROW_HEIGHT)
            self._interactive_rects.append((rect, f"structure:{post['id']}"))
            self._nav_items.append(("structure", post["id"], rect))

        y += min(len(self._guard_posts), self.STRUCTURE_MAX_ROWS) * self.STRUCTURE_ROW_HEIGHT
        return y

    def _render_dialogue(self, screen, npc, left, y):
        dialogue_lines = npc.dialogue_lines
        if not dialogue_lines:
            return y
        max_chars_per_line = 52
        for i, line in enumerate(dialogue_lines[:2]):
            if len(line) > max_chars_per_line:
                line = line[:max_chars_per_line - 3] + "..."
            screen.blit(self.font_normal.render(line, True, self.TEXT_DIM), (left, y + i * 16))
        y += 32
        return y

    def _render_action_buttons(self, screen, info, content_rect, y):
        btn_w = self.ACTION_BTN_WIDTH
        btn_h = self.ACTION_BTN_HEIGHT
        total_w = 2 * btn_w + self.ACTION_BTN_GAP
        start_x = content_rect.x + (content_rect.width - total_w) // 2
        recruit_enabled = info.eligibility.eligible and (len(info.npc.available_behaviors) <= 1 or self._selected_behavior != "")
        recruit_color = self.RECRUIT_BTN if recruit_enabled else self.RECRUIT_BTN_DISABLED
        recruit_rect = pygame.Rect(start_x, y, btn_w, btn_h)
        pygame.draw.rect(screen, recruit_color, recruit_rect)
        pygame.draw.rect(screen, self.COLOR_BORDER, recruit_rect, 1)
        recruit_text = self.font_bold.render("Recruit", True, (255, 255, 255) if recruit_enabled else (120, 120, 140))
        rx = start_x + (btn_w - recruit_text.get_width()) // 2
        ry = y + (btn_h - recruit_text.get_height()) // 2
        screen.blit(recruit_text, (rx, ry))
        self._interactive_rects.append((recruit_rect, "action:recruit"))
        self._nav_items.append(("action", "recruit", recruit_rect))
        cancel_x = start_x + btn_w + self.ACTION_BTN_GAP
        cancel_rect = pygame.Rect(cancel_x, y, btn_w, btn_h)
        pygame.draw.rect(screen, self.CANCEL_BTN, cancel_rect)
        pygame.draw.rect(screen, self.COLOR_BORDER, cancel_rect, 1)
        cancel_text = self.font_bold.render("Cancel", True, (255, 255, 255))
        cx = cancel_x + (btn_w - cancel_text.get_width()) // 2
        cy = y + (btn_h - cancel_text.get_height()) // 2
        screen.blit(cancel_text, (cx, cy))
        self._interactive_rects.append((cancel_rect, "action:cancel"))
        self._nav_items.append(("action", "cancel", cancel_rect))
        y += btn_h + 5
        return y

    def _draw_not_connected(self, screen, content_rect):
        msg = self.font_normal.render("No NPC selected.", True, (180, 180, 200))
        mx = content_rect.x + (content_rect.width - msg.get_width()) // 2
        my = content_rect.y + (content_rect.height - msg.get_height()) // 2
        screen.blit(msg, (mx, my))

    def on_key(self, key: int) -> tuple[str, ...] | None:
        """
        Keyboard navigation for the recruit panel.

        Arrow keys / WASD: navigate behaviors, structures, and action buttons
        Enter: return ("recruit", npc_id, behavior, structure_id) or ("recruit", npc_id, behavior)
        ESC: return ("cancel",)

        Returns None for navigation only; action tuple on Enter/ESC.
        """
        if self._recruit_info is None or self._recruit_info.npc is None:
            return None

        npc_id = self._recruit_info.npc.npc_id

        if key == pygame.K_ESCAPE:
            return ("cancel",)

        if key in (pygame.K_w, pygame.K_UP):
            self.select(max(-1, self._selected_index - 1))
            return None
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.select(min(len(self._nav_items) - 1, self._selected_index + 1))
            return None
        elif key in (pygame.K_a, pygame.K_LEFT):
            self.select(max(-1, self._selected_index - 1))
            return None
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self.select(min(len(self._nav_items) - 1, self._selected_index + 1))
            return None
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_index < len(self._nav_items):
                item_type, value, _rect = self._nav_items[self._selected_index]
                if item_type == "action" and value == "cancel":
                    return ("cancel",)
                if item_type == "action" and value == "recruit":
                    behavior = self._selected_behavior
                    if not behavior and len(self._recruit_info.npc.available_behaviors) == 1:
                        behavior = self._recruit_info.npc.available_behaviors[0]
                    if behavior:
                        if self._selected_structure_id:
                            return ("recruit", npc_id, behavior, self._selected_structure_id)
                        return ("recruit", npc_id, behavior)
                    self._set_status("No behavior selected.", self.ERROR_COLOR)
                    return None
                if item_type == "behavior":
                    self._selected_behavior = value
                    self._set_status(f"Selected behavior: {value}")
                    return None
                if item_type == "structure":
                    self._selected_structure_id = value
                    self._set_status(f"Selected guard post: {value}")
                    return None
        return None

    def on_click(self, x: int, y: int, button: int = 1) -> tuple[str, ...] | None:
        for rect, payload in self._interactive_rects:
            if rect.collidepoint(x, y):
                if payload.startswith("behavior:"):
                    behavior = payload.split(":", 1)[1]
                    self._selected_behavior = behavior
                    self._set_status(f"Selected behavior: {behavior}")
                    return None
                elif payload.startswith("structure:"):
                    struct_id = payload.split(":", 1)[1]
                    if self._recruit_info and self._recruit_info.npc is None:
                        return None
                    if self._selected_behavior == "guard":
                        self._selected_structure_id = struct_id
                        self._set_status(f"Selected guard post: {struct_id}")
                        return None
                elif payload == "action:recruit":
                    if self._recruit_info is None or self._recruit_info.npc is None:
                        return None
                    behavior = self._selected_behavior
                    if not behavior and len(self._recruit_info.npc.available_behaviors) == 1:
                        behavior = self._recruit_info.npc.available_behaviors[0]
                    if behavior:
                        if self._selected_structure_id:
                            return (
                                "recruit",
                                self._recruit_info.npc.npc_id,
                                behavior,
                                self._selected_structure_id,
                            )
                        return ("recruit", self._recruit_info.npc.npc_id, behavior)
                    self._set_status("No behavior selected.", self.ERROR_COLOR)
                    return None
                elif payload == "action:cancel":
                    return ("cancel",)
        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Sync selection index on hover over behaviors, structures, and action buttons."""
        for i, (rect, _payload) in enumerate(self._interactive_rects):
            if rect.collidepoint(mx, my):
                self.select(i)
                return
        self.select(-1)