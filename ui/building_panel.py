"""
ui/building_panel.py — Building placement panel UI (PanelWindow subclass).

Displays available structures organized by construction sub-stat category,
shows construction stats, and highlights placement preview.
Subclasses PanelWindow for unified chrome, viewport clipping, scrollbar,
keyboard navigation with visible selection, and mouse-wheel scrolling.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional

import pygame

from config import TILE_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT
from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from building.building_system import BuildingSystem
    from building.structure import StructureDef
    from skills.skill_manager import SkillManager


class BuildingPanel(PanelWindow):
    """
    Building placement panel.

    Shows structure categories (common, defensive, offensive, decorative),
    construction sub-stats, and placement preview.
    """

    def __init__(self) -> None:
        super().__init__(
            title="Building",
            x=(WINDOW_WIDTH - 340) // 2,
            y=30,
            width=340,
            height=WINDOW_HEIGHT - 60,
            title_height=26,
            footer_height=0,
            has_scrollbar=True,
            show_close=True,
            selection_mode="list",
            row_gap=10,
        )
        self.visible: bool = False
        self.current_tab: str = "common"
        self.selected_structure_id: Optional[str] = None
        self._hovered_structure: Optional[str] = None
        self._structure_rects: List[tuple[pygame.Rect, str]] = []
        self._tab_rects: List[tuple[pygame.Rect, str]] = []
        self._stat_bar_rects: List[tuple[pygame.Rect, str]] = []

        # Font sizes (use base fonts)
        self._title_font = self.font_bold
        self._struct_font = self.font_normal
        self._stat_font = self.font_normal
        self._hint_font = self.font_small

        self._building_system: Optional["BuildingSystem"] = None

    def set_buildings(self, building_system: "BuildingSystem") -> None:
        """Set the building system reference."""
        self._building_system = building_system

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable items (structure entries)."""
        return len(self._structure_rects)

    def on_select(self, index: int) -> None:
        """Highlight the selected structure."""
        pass

    # ── PanelWindow hooks ────────────────────────────────────────────────

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw structure entries and stats inside the clipped viewport."""
        self._interactive_rects.clear()
        self._structure_rects.clear()
        self._tab_rects.clear()
        self._stat_bar_rects.clear()

        if self._building_system is None:
            self._content_total_px = 0
            return

        left = content_rect.x + 10
        gap = self.row_gap
        y = content_rect.y - self._scroll_offset

        # Tab buttons
        tabs = ["common", "defensive", "offensive", "decorative"]
        tab_y = y
        tab_width = (content_rect.width - 20) // len(tabs)
        for i, tab in enumerate(tabs):
            tab_x = left + i * tab_width
            is_active = tab == self.current_tab
            colour = (80, 120, 200) if is_active else (60, 60, 80)
            tab_rect = pygame.Rect(tab_x, tab_y, tab_width - 4, 22)
            pygame.draw.rect(screen, colour, tab_rect, border_radius=3)
            if is_active:
                pygame.draw.rect(screen, (140, 160, 220), tab_rect, 1, border_radius=3)
            label = self._stat_font.render(tab.title(), True, (220, 220, 240))
            screen.blit(label, (tab_x + 4, tab_y + 4))
            self._tab_rects.append((tab_rect, tab))
            self._interactive_rects.append((tab_rect, f"tab:{tab}"))
        y = tab_y + 30

        # Structure list for current tab
        structures = self._get_structures_for_tab(self._building_system, self.current_tab)
        for struct in structures:
            entry_rect = pygame.Rect(left, y, content_rect.width - 20, 45)
            self._structure_rects.append((entry_rect, struct.structure_id))
            self._render_structure_entry(screen, struct, entry_rect, self._building_system)
            self._interactive_rects.append((entry_rect, f"structure:{struct.structure_id}"))
            y += 55

        # Construction sub-stats
        y = self._render_construction_stats(
            screen, left, y,
        )

        self._content_total_px = y - content_rect.y + 20

    def _get_structures_for_tab(
        self, building_system: "BuildingSystem", tab: str,
    ) -> List["StructureDef"]:
        """Get structure definitions for a tab category."""
        defs = building_system.structure_defs.get(tab, {})
        return list(defs.values())

    def _render_structure_entry(
        self,
        screen: pygame.Surface,
        struct_def: "StructureDef",
        entry_rect: pygame.Rect,
        building_system: "BuildingSystem",
    ) -> None:
        """Render a single structure entry."""
        x = entry_rect.x
        y = entry_rect.y
        width = entry_rect.width

        # Check if player can build this (need skill_manager from game context)
        # This will be set by the game when opening the panel
        crafting_level = getattr(self, "_cached_crafting_level", 0)
        allowed, reason = building_system.construction.can_place_structure(
            struct_def, crafting_level,
        )

        # Background
        bg_colour = (40, 60, 40) if allowed else (60, 30, 30)
        is_selected = self._is_structure_selected(struct_def.structure_id)
        if is_selected:
            bg_colour = (60, 80, 60) if allowed else (80, 40, 40)
        pygame.draw.rect(
            screen, bg_colour, (x, y, width, 45), border_radius=3,
        )

        # Name
        name_colour = (200, 200, 220) if allowed else (150, 100, 100)
        name = self._struct_font.render(struct_def.name, True, name_colour)
        screen.blit(name, (x + 5, y + 3))

        # Materials
        mat_text = ", ".join(f"{qty}x {item}" for item, qty in struct_def.materials[:3])
        mat = self._hint_font.render(mat_text, True, (160, 160, 180))
        screen.blit(mat, (x + 5, y + 18))

        # HP and type (display the placed HP, i.e. with Construction bonuses)
        placed_hp = building_system.construction.calculate_structure_hp(struct_def)
        hp_text = f"HP: {placed_hp} | {struct_def.structure_type}"
        hp = self._hint_font.render(hp_text, True, (140, 140, 160))
        screen.blit(hp, (x + 5, y + 32))

    def _is_structure_selected(self, structure_id: str) -> bool:
        """Check if a specific structure is the currently selected one."""
        for i, (_, sid) in enumerate(self._structure_rects):
            if sid == structure_id:
                return i == self._selected_index
        return False

    def _render_construction_stats(
        self,
        screen: pygame.Surface,
        x: int,
        y: int,
    ) -> int:
        """Render construction sub-stat bars. Returns new y position."""
        # Need skill_manager from game context
        skill_manager = getattr(self, "_cached_skill_manager", None)
        if skill_manager is None:
            return y

        stats = [
            ("Common", "common_building_tech"),
            ("Defensive", "defensive_building_tech"),
            ("Offensive", "offensive_building_tech"),
            ("Decorative", "decorative_building_tech"),
        ]

        label = self._stat_font.render("Construction Sub-Stats:", True, (180, 180, 200))
        screen.blit(label, (x, y))
        y += 20
        for label_text, stat_name in stats:
            level = skill_manager.get_effective_stat("crafting", stat_name)
            bar_width = 120
            fill_width = min(bar_width, level * 10)

            stat_label = self._hint_font.render(label_text, True, (160, 160, 180))
            screen.blit(stat_label, (x, y))
            pygame.draw.rect(screen, (50, 50, 70), (x, y, bar_width, 8))
            pygame.draw.rect(
                screen, (80, 140, 200),
                (x, y, fill_width, 8),
            )
            text = self._hint_font.render(f"  Lv {level}", True, (200, 200, 220))
            screen.blit(text, (x + bar_width + 5, y - 1))
            y += 14
        return y

    def on_key(self, key: int) -> str | None:
        """
        Keyboard navigation for the building panel.

        Tab / Left / Right arrows: switch tabs
        Arrow keys / WASD: navigate structure list
        Enter: return "place:<structure_id>" for selected structure

        Returns None for navigation only; action string on Enter.
        """
        tabs = ["common", "defensive", "offensive", "decorative"]
        current_idx = tabs.index(self.current_tab)

        # Tab switching
        if key == pygame.K_TAB:
            new_idx = (current_idx + 1) % len(tabs)
            self.current_tab = tabs[new_idx]
            self._selected_structure_index = -1
            return None
        elif key == pygame.K_LEFT and current_idx > 0:
            self.current_tab = tabs[current_idx - 1]
            self._selected_structure_index = -1
            return None
        elif key == pygame.K_RIGHT and current_idx < len(tabs) - 1:
            self.current_tab = tabs[current_idx + 1]
            self._selected_structure_index = -1
            return None

        # Structure navigation
        if key in (pygame.K_w, pygame.K_UP):
            self.select(max(-1, self._selected_index - 1))
            return None
        elif key in (pygame.K_s, pygame.K_DOWN):
            self.select(min(len(self._structure_rects) - 1, self._selected_index + 1))
            return None
        elif key in (pygame.K_a, pygame.K_LEFT):
            self.select(max(-1, self._selected_index - 1))
            return None
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self.select(min(len(self._structure_rects) - 1, self._selected_index + 1))
            return None
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_index < len(self._structure_rects):
                _, structure_id = self._structure_rects[self._selected_index]
                return f"place:{structure_id}"

        return None

    def on_click(self, x: int, y: int, button: int = 1) -> Optional[str]:
        """
        Handle a click on the building panel.

        Args:
            mx: Mouse X coordinate.
            my: Mouse Y coordinate.

        Returns:
            Selected structure_id, or None.
        """
        if not self.visible:
            return None

        # Check tab clicks
        for tab_rect, tab in self._tab_rects:
            if tab_rect.collidepoint(x, y):
                self.current_tab = tab
                return None

        # Check structure entry clicks
        for entry_rect, struct_id in self._structure_rects:
            if entry_rect.collidepoint(x, y):
                self.selected_structure_id = struct_id
                return ("select", struct_id)

        # Return ("close",) for clicks within the panel area but outside tabs/structures
        if (self.content_rect.x <= x <= self.content_rect.x + self.content_rect.width and
                self.content_rect.y <= y <= self.content_rect.y + self.content_rect.height):
            return ("close",)
        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Handle mouse movement for hover feedback."""
        # Check tab hits
        for tab_rect, tab in self._tab_rects:
            if tab_rect.collidepoint(mx, my):
                self._hovered_tab = True
                return
        # Structure entry hit testing
        for entry_rect, struct_id in self._structure_rects:
            if entry_rect.collidepoint(mx, my):
                self._hovered_structure = struct_id
                return
        self._hovered_structure = None

    def handle_close(self) -> tuple:
        """
        Return the close action tuple for the building panel.

        Returns:
            Tuple ("close",).
        """
        return ("close",)

    # Compatibility methods for game.py render call
    def render(self, screen: pygame.Surface, building_system=None, skill_manager=None) -> None:
        """
        Render the building panel with optional backward-compatible args.

        Args:
            screen: The pygame display surface.
            building_system: The building system for structure data (optional, uses cached).
            skill_manager: The skill manager for stat display (optional, uses cached).
        """
        # Cache for draw_contents
        if building_system is not None:
            self._building_system = building_system
        if skill_manager is not None:
            self._cached_skill_manager = skill_manager
            self._cached_crafting_level = skill_manager.get_skill_level("crafting")
        # Call base render
        super().render(screen)