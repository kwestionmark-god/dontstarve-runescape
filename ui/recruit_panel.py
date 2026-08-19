"""
recruit_panel.py — Recruitment UI panel for player-NPC interactions.

Phase 3, Step 11: Recruitment Panel UI.
"""

from __future__ import annotations

import os
import json
import pygame
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

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


class RecruitPanel:
    """Recruit panel: NPC recruitment UI."""

    # Panel geometry
    PANEL_X = 400
    PANEL_Y = 60
    PANEL_WIDTH = 460
    PANEL_HEIGHT = 330

    # Close button
    CLOSE_X = PANEL_X + PANEL_WIDTH - 28
    CLOSE_Y = PANEL_Y + 5
    CLOSE_SIZE = 22

    # Section positions
    INFO_Y = 50
    REQUIREMENTS_Y = 80
    SLOT_INFO_Y = 140
    BEHAVIOR_HEADER_Y = 160
    BEHAVIOR_START_Y = 175
    BEHAVIOR_ROW_HEIGHT = 18
    DIALOGUE_Y = 205
    ACTION_Y = 240
    STATUS_Y = 275
    STATUS_HEIGHT = 20

    # Button geometry
    ACTION_BTN_WIDTH = 100
    ACTION_BTN_HEIGHT = 28
    ACTION_BTN_GAP = 10

    # Guard post section
    STRUCTURE_HEADER_Y_OFFSET = 0  # computed dynamically after behavior
    STRUCTURE_ROW_HEIGHT = 16
    STRUCTURE_MAX_ROWS = 3

    # Color palette
    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    CONTENT_BG = (35, 35, 45)
    TEXT_COLOR = (200, 200, 220)
    TEXT_DIM = (150, 150, 170)
    SUCCESS_COLOR = (100, 180, 100)
    ERROR_COLOR = (180, 100, 100)
    TAB_ACTIVE = (60, 80, 120)
    TAB_INACTIVE = (40, 40, 55)
    QTY_BTN = (70, 70, 90)
    QTY_BTN_HOVER = (90, 90, 110)
    RECRUIT_BTN = (80, 140, 80)
    RECRUIT_BTN_DISABLED = (45, 65, 45)
    CANCEL_BTN = (140, 100, 80)
    RADIO_SELECTED = (100, 160, 100)
    RADIO_UNSELECTED = (70, 70, 90)

    def __init__(self) -> None:
        self.visible: bool = False
        self._player_ref: "Player | None" = None
        self._recruit_info: "RecruitInfo | None" = None
        self._selected_behavior: str = ""
        self._selected_structure_id: Optional[str] = None
        self._guard_posts: list[dict] = []
        self._structure_rects: list[tuple[pygame.Rect, str]] = []
        self._structure_section_y: int = 0
        self._hovered_btn: str = ""
        self._status_message: str = ""
        self._status_color: tuple[int, int, int] = (200, 200, 220)
        self._button_rects: list[tuple[pygame.Rect, str]] = []
        self._behavior_rects: list[tuple[pygame.Rect, str]] = []
        self._structure_rects: list[tuple[pygame.Rect, str]] = []
        self.font_title = pygame.font.SysFont("monospace", 14, bold=True)
        self.font_normal = pygame.font.SysFont("monospace", 11)
        self.font_small = pygame.font.SysFont("monospace", 10)
        self.font_bold = pygame.font.SysFont("monospace", 12, bold=True)
        self._faction_names: dict[str, str] = {}
        self._load_faction_names()

        # Keyboard navigation
        self._selected_behavior: str = ""
        self._selected_structure_id: Optional[str] = None
        self._selected_nav_index: int = -1
        self._nav_items: list[tuple[str, str, pygame.Rect]] = []  # (type, value, rect)

    def set_player(self, player: "Player") -> None:
        self._player_ref = player

    def open_session(self, npc: "RecruitNPC") -> bool:
        if self._player_ref is None:
            self._set_status("Player not available.", self.ERROR_COLOR)
            return False
        from skills.intelligence.intelligence import IntelligenceSkill
        intelligence = IntelligenceSkill(self._player_ref.action_system.skill_manager)
        eligibility = intelligence.is_recruitment_eligible(npc, self._player_ref)
        commerce = self._player_ref.action_system.skill_manager.get_effective_stat("intelligence", "commerce")
        persuasion = self._player_ref.action_system.skill_manager.get_effective_stat("intelligence", "persuasion")
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
        self._button_rects = []
        self._behavior_rects = []
        self._structure_rects = []

        # Check if this NPC already has an assigned structure
        if self._recruit_info and self._recruit_info.npc:
            game = getattr(self._player_ref, "game", None)
            if game and hasattr(game, "npc_system") and game.npc_system:
                struct = game.npc_system.get_npc_structure(self._recruit_info.npc.npc_id)
                if struct:
                    self._selected_structure_id = struct.structure_def.structure_id

        self._load_guard_post_info()
        return True

    def close_session(self) -> None:
        self._recruit_info = None
        self._selected_behavior = ""
        self._status_message = ""
        self._button_rects = []
        self._behavior_rects = []

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
                fid = faction.get("id", "")
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

    def render(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        panel_x = self.PANEL_X
        panel_y = self.PANEL_Y
        panel_w = self.PANEL_WIDTH
        panel_h = self.PANEL_HEIGHT
        pygame.draw.rect(screen, self.BORDER_COLOR, (panel_x, panel_y, panel_w, panel_h), 2)
        pygame.draw.rect(screen, (160, 160, 180), (panel_x + 3, panel_y + 3, panel_w - 6, panel_h - 6), 1)
        bg_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg_surf.fill((*self.BG_COLOR, 240))
        screen.blit(bg_surf, (panel_x, panel_y))
        if self._recruit_info is None:
            self._render_not_connected(screen)
            self._render_close_button(screen)
            return
        info = self._recruit_info
        npc = info.npc
        self._render_close_button(screen)
        title_surf = self.font_title.render(f"Recruit {npc.name}", True, self.TEXT_COLOR)
        screen.blit(title_surf, (panel_x + 10, self.PANEL_Y + 5))
        faction_name = self._get_faction_name(npc.faction)
        status_text = "Eligible" if info.eligibility.eligible else "Not Eligible"
        status_color = self.SUCCESS_COLOR if info.eligibility.eligible else self.ERROR_COLOR
        row_text = f"Faction: {faction_name}     Status: {status_text}"
        row_surf = self.font_normal.render(row_text, True, status_color)
        screen.blit(row_surf, (panel_x + 10, self.INFO_Y))
        self._render_stat_requirements(screen, info)
        self._render_slot_info(screen, info)
        if len(npc.available_behaviors) > 1:
            self._render_behavior_selection(screen, npc)
        self._render_guard_structure_assignment(screen)
        self._render_dialogue(screen, npc)
        self._render_action_buttons(screen, info)
        self._render_status_bar(screen)

        # Build combined nav list for keyboard navigation
        self._nav_items = []
        # Behaviors
        for rect, behavior in self._behavior_rects:
            self._nav_items.append(("behavior", behavior, rect))
        # Structures
        for rect, struct_id in self._structure_rects:
            self._nav_items.append(("structure", struct_id, rect))
        # Action buttons
        for rect, action_id in self._button_rects:
            self._nav_items.append(("action", action_id, rect))

    def _render_stat_requirements(self, screen, info) -> None:
        y = self.REQUIREMENTS_Y
        commerce_req = info.npc.recruit_commerce_requirement
        persuasion_req = info.npc.recruit_persuasion_requirement
        composite_req = info.npc.recruit_composite_stat
        commerce_ok = info.player_commerce >= commerce_req
        commerce_color = self.SUCCESS_COLOR if commerce_ok else self.ERROR_COLOR
        commerce_text = f"Commerce: {commerce_req}  (You have: {info.player_commerce})  {'OK' if commerce_ok else 'FAIL'}"
        screen.blit(self.font_normal.render(commerce_text, True, commerce_color), (self.PANEL_X + 10, y))
        y += 18
        persuasion_ok = info.player_persuasion >= persuasion_req
        persuasion_color = self.SUCCESS_COLOR if persuasion_ok else self.ERROR_COLOR
        persuasion_text = f"Persuasion: {persuasion_req}  (You have: {info.player_persuasion})  {'OK' if persuasion_ok else 'FAIL'}"
        screen.blit(self.font_normal.render(persuasion_text, True, persuasion_color), (self.PANEL_X + 10, y))
        y += 18
        composite_ok = info.player_composite >= composite_req
        composite_color = self.SUCCESS_COLOR if composite_ok else self.ERROR_COLOR
        composite_text = f"Composite: {composite_req}  (You have: {info.player_composite})  {'OK' if composite_ok else 'FAIL'}"
        screen.blit(self.font_normal.render(composite_text, True, composite_color), (self.PANEL_X + 10, y))

    def _render_slot_info(self, screen, info) -> None:
        slot_color = self.SUCCESS_COLOR if info.available_slots > 0 else self.ERROR_COLOR
        slot_text = f"Recruit Slots: {info.available_slots} / {info.max_recruits}"
        screen.blit(self.font_normal.render(slot_text, True, slot_color), (self.PANEL_X + 10, self.SLOT_INFO_Y))

    def _render_behavior_selection(self, screen, npc) -> None:
        x = self.PANEL_X + 10
        y = self.BEHAVIOR_HEADER_Y
        header_surf = self.font_bold.render("Behavior Selection:", True, self.TEXT_COLOR)
        screen.blit(header_surf, (x, y))
        y += 18
        for i, behavior in enumerate(npc.available_behaviors):
            row_y = y + i * self.BEHAVIOR_ROW_HEIGHT
            is_selected = self._selected_behavior == behavior
            circle_x = x + 4
            circle_y = row_y + 6
            circle_r = 6
            circle_color = self.RADIO_SELECTED if is_selected else self.RADIO_UNSELECTED
            pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r)
            if is_selected:
                pygame.draw.circle(screen, self.BG_COLOR, (circle_x, circle_y), circle_r - 2)
                pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r - 2, 2)
            label_surf = self.font_normal.render(behavior.capitalize(), True, self.TEXT_COLOR)
            screen.blit(label_surf, (x + 20, row_y))
            rect = pygame.Rect(x, row_y, 120, self.BEHAVIOR_ROW_HEIGHT)
            self._behavior_rects.append((rect, behavior))

    def _render_guard_structure_assignment(self, screen) -> None:
        """
        Render guard post structure assignment section.
        Only shown when selected behavior is 'guard'.
        """
        if self._recruit_info is None or self._recruit_info.npc is None:
            return
        if self._selected_behavior != "guard":
            return
        if not self._guard_posts:
            self._set_status("No guard posts available. Build a ballista, trebuchet, or wall tower.", self.TEXT_DIM)
            return

        x = self.PANEL_X + 10
        y = self.BEHAVIOR_HEADER_Y + 18 + len(self._recruit_info.npc.available_behaviors) * self.BEHAVIOR_ROW_HEIGHT + 8
        self._structure_section_y = y
        header_surf = self.font_bold.render("Guard Posts:", True, self.TEXT_COLOR)
        screen.blit(header_surf, (x, y))
        y += 18

        for i, post in enumerate(self._guard_posts):
            if i >= self.STRUCTURE_MAX_ROWS:
                break
            row_y = y + i * self.STRUCTURE_ROW_HEIGHT
            is_selected = self._selected_structure_id == post["id"]
            circle_x = x + 4
            circle_y = row_y + 6
            circle_r = 5
            circle_color = self.RADIO_SELECTED if is_selected else self.RADIO_UNSELECTED
            pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r)
            if is_selected:
                pygame.draw.circle(screen, self.BG_COLOR, (circle_x, circle_y), circle_r - 2)
                pygame.draw.circle(screen, circle_color, (circle_x, circle_y), circle_r - 2, 2)

            label = f"{post['name']} ({post['x']},{post['y']})"
            if post["assigned"]:
                label += " [Assigned]"
            label_surf = self.font_normal.render(label, True, self.TEXT_DIM if post["assigned"] else self.TEXT_COLOR)
            screen.blit(label_surf, (x + 20, row_y))

            rect = pygame.Rect(x, row_y, 200, self.STRUCTURE_ROW_HEIGHT)
            self._structure_rects.append((rect, post["id"]))

    def _render_dialogue(self, screen, npc) -> None:
        dialogue_lines = npc.dialogue_lines
        if not dialogue_lines:
            return
        y = self.DIALOGUE_Y
        max_chars_per_line = 52
        for i, line in enumerate(dialogue_lines[:2]):
            if len(line) > max_chars_per_line:
                line = line[:max_chars_per_line - 3] + "..."
            screen.blit(self.font_normal.render(line, True, self.TEXT_DIM), (self.PANEL_X + 10, y + i * 16))

    def _render_action_buttons(self, screen, info) -> None:
        panel_x = self.PANEL_X
        action_y = self.ACTION_Y
        btn_w = self.ACTION_BTN_WIDTH
        btn_h = self.ACTION_BTN_HEIGHT
        total_w = 2 * btn_w + self.ACTION_BTN_GAP
        start_x = panel_x + (self.PANEL_WIDTH - total_w) // 2
        recruit_enabled = info.eligibility.eligible and (len(info.npc.available_behaviors) <= 1 or self._selected_behavior != "")
        recruit_color = self.RECRUIT_BTN if recruit_enabled else self.RECRUIT_BTN_DISABLED
        recruit_rect = pygame.Rect(start_x, action_y, btn_w, btn_h)
        pygame.draw.rect(screen, recruit_color, recruit_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, recruit_rect, 1)
        recruit_text = self.font_bold.render("Recruit", True, (255, 255, 255) if recruit_enabled else (120, 120, 140))
        rx = start_x + (btn_w - recruit_text.get_width()) // 2
        ry = action_y + (btn_h - recruit_text.get_height()) // 2
        screen.blit(recruit_text, (rx, ry))
        self._button_rects.append((recruit_rect, "recruit"))
        cancel_x = start_x + btn_w + self.ACTION_BTN_GAP
        cancel_rect = pygame.Rect(cancel_x, action_y, btn_w, btn_h)
        pygame.draw.rect(screen, self.CANCEL_BTN, cancel_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, cancel_rect, 1)
        cancel_text = self.font_bold.render("Cancel", True, (255, 255, 255))
        cx = cancel_x + (btn_w - cancel_text.get_width()) // 2
        cy = action_y + (btn_h - cancel_text.get_height()) // 2
        screen.blit(cancel_text, (cx, cy))
        self._button_rects.append((cancel_rect, "cancel"))
        hint = self.font_small.render("Press ESC to close", True, self.TEXT_DIM)
        hint_x = panel_x + (self.PANEL_WIDTH - hint.get_width()) // 2
        hint_y = action_y + btn_h + 5
        screen.blit(hint, (hint_x, hint_y))

    def _render_status_bar(self, screen) -> None:
        status_y = self.STATUS_Y
        status_w = self.PANEL_WIDTH - 10
        pygame.draw.rect(screen, self.CONTENT_BG, (self.PANEL_X + 5, status_y, status_w, self.STATUS_HEIGHT))
        if self._status_message:
            status_surf = self.font_normal.render(self._status_message, True, self._status_color)
            sx = self.PANEL_X + 10
            sy = status_y + (self.STATUS_HEIGHT - status_surf.get_height()) // 2
            screen.blit(status_surf, (sx, sy))

    def _render_close_button(self, screen) -> None:
        close_rect = pygame.Rect(self.CLOSE_X, self.CLOSE_Y, self.CLOSE_SIZE, self.CLOSE_SIZE)
        hover_color = self.QTY_BTN_HOVER if self._hovered_btn == "close" else self.QTY_BTN
        pygame.draw.rect(screen, hover_color, close_rect)
        pygame.draw.rect(screen, self.BORDER_COLOR, close_rect, 1)
        line_color = (255, 255, 255)
        padding = 5
        pygame.draw.line(screen, line_color, (self.CLOSE_X + padding, self.CLOSE_Y + padding), (self.CLOSE_X + self.CLOSE_SIZE - padding, self.CLOSE_Y + self.CLOSE_SIZE - padding), 2)
        pygame.draw.line(screen, line_color, (self.CLOSE_X + self.CLOSE_SIZE - padding, self.CLOSE_Y + padding), (self.CLOSE_X + padding, self.CLOSE_Y + self.CLOSE_SIZE - padding), 2)
        self._button_rects.append((close_rect, "close"))

    def _render_not_connected(self, screen) -> None:
        msg = self.font_normal.render("No NPC selected.", True, (180, 180, 200))
        mx = self.PANEL_X + (self.PANEL_WIDTH - msg.get_width()) // 2
        my = self.PANEL_Y + self.PANEL_HEIGHT // 2 - msg.get_height() // 2
        screen.blit(msg, (mx, my))

    def handle_mouse_move(self, mx: int, my: int) -> None:
        self._hovered_btn = ""
        close_rect = pygame.Rect(self.CLOSE_X, self.CLOSE_Y, self.CLOSE_SIZE, self.CLOSE_SIZE)
        if close_rect.collidepoint(mx, my):
            self._hovered_btn = "close"
            return
        for rect, struct_id in self._structure_rects:
            if rect.collidepoint(mx, my):
                self._hovered_btn = struct_id
                return
        for btn_rect, action_id in self._button_rects:
            if btn_rect.collidepoint(mx, my):
                self._hovered_btn = action_id
                return

    def handle_key(self, key: int) -> tuple[str, ...] | None:
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
            self._selected_nav_index = max(-1, self._selected_nav_index - 1)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self._selected_nav_index = min(len(self._nav_items) - 1, self._selected_nav_index + 1)
        elif key in (pygame.K_a, pygame.K_LEFT):
            self._selected_nav_index = max(-1, self._selected_nav_index - 1)
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self._selected_nav_index = min(len(self._nav_items) - 1, self._selected_nav_index + 1)
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_nav_index < len(self._nav_items):
                item_type, value, _rect = self._nav_items[self._selected_nav_index]
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

    def handle_click(self, x: int, y: int) -> tuple[str, ...] | None:
        close_rect = pygame.Rect(self.CLOSE_X, self.CLOSE_Y, self.CLOSE_SIZE, self.CLOSE_SIZE)
        if close_rect.collidepoint(x, y):
            return ("close",)
        for rect, struct_id in self._structure_rects:
            if rect.collidepoint(x, y):
                if self._recruit_info and self._recruit_info.npc is None:
                    return None
                if self._selected_behavior == "guard":
                    self._selected_structure_id = struct_id
                    self._set_status(f"Selected guard post: {struct_id}")
                    return None
        for rect, behavior in self._behavior_rects:
            if rect.collidepoint(x, y):
                self._selected_behavior = behavior
                self._set_status(f"Selected behavior: {behavior}")
                return None
        for btn_rect, action_id in self._button_rects:
            if btn_rect.collidepoint(x, y):
                if action_id == "recruit":
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
                elif action_id == "cancel":
                    return ("cancel",)
        return None
