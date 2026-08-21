"""
ui/building_panel.py — Building placement panel UI.

Displays available structures organized by construction sub-stat category,
shows construction stats, and highlights placement preview.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional

import pygame

from config import TILE_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT

if TYPE_CHECKING:
    from building.building_system import BuildingSystem
    from building.structure import StructureDef
    from skills.skill_manager import SkillManager


class BuildingPanel:
    """
    Building placement panel.

    Shows structure categories (common, defensive, offensive, decorative),
    construction sub-stats, and placement preview.
    """

    def __init__(self) -> None:
        self.visible: bool = False
        self.panel_width: int = 340
        self.panel_height: int = WINDOW_HEIGHT - 60
        self.x: int = (WINDOW_WIDTH - self.panel_width) // 2
        self.y: int = 30
        self.current_tab: str = "common"
        self.selected_structure_id: Optional[str] = None
        self._hovered_structure: Optional[str] = None
        self._selected_structure_index: int = -1
        self._structure_rects: List[tuple[pygame.Rect, str]] = []

        # Font sizes
        self._title_font = pygame.font.SysFont("monospace", 18, bold=True)
        self._struct_font = pygame.font.SysFont("monospace", 13)
        self._stat_font = pygame.font.SysFont("monospace", 12)
        self._hint_font = pygame.font.SysFont("monospace", 11)

    def set_buildings(self, building_system: BuildingSystem) -> None:
        """Set the building system reference."""
        self._building_system = building_system

    def render(
        self,
        screen: pygame.Surface,
        building_system: BuildingSystem,
        skill_manager: SkillManager,
    ) -> None:
        """
        Render the building panel.

        Args:
            screen: The pygame display surface.
            building_system: The building system for structure data.
            skill_manager: The skill manager for stat display.
        """
        # Panel background
        panel_surf = pygame.Surface(
            (self.panel_width, self.panel_height), pygame.SRCALPHA,
        )
        panel_surf.fill((30, 30, 50, 220))

        # Draw panel border
        pygame.draw.rect(
            screen, (100, 100, 140),
            (self.x, self.y, self.panel_width, self.panel_height), 2,
        )
        screen.blit(panel_surf, (self.x, self.y))

        # Title
        title = self._title_font.render("Building (B or ESC to close)", True, (200, 200, 220))
        screen.blit(title, (self.x + 10, self.y + 8))

        # Tab buttons
        tabs = ["common", "defensive", "offensive", "decorative"]
        tab_y = self.y + 35
        tab_width = (self.panel_width - 20) // len(tabs)
        for i, tab in enumerate(tabs):
            tab_x = self.x + 10 + i * tab_width
            is_active = tab == self.current_tab
            colour = (80, 120, 200) if is_active else (60, 60, 80)
            pygame.draw.rect(screen, colour, (tab_x, tab_y, tab_width - 4, 22), border_radius=3)
            if is_active:
                pygame.draw.rect(screen, (140, 160, 220), (tab_x, tab_y, tab_width - 4, 22), 1, border_radius=3)
            label = self._stat_font.render(tab.title(), True, (220, 220, 240))
            screen.blit(label, (tab_x + 4, tab_y + 4))

        # Structure list for current tab
        structures = self._get_structures_for_tab(building_system, self.current_tab)
        struct_y = tab_y + 30
        self._structure_rects = []
        for struct in structures:
            entry_rect = (
                self.x + 10, struct_y,
                self.panel_width - 20, 45,
            )
            self._structure_rects.append((pygame.Rect(*entry_rect), struct.structure_id))
            self._render_structure_entry(screen, struct, struct_y, building_system, skill_manager)
            struct_y += 55

        # Construction sub-stats
        self._render_construction_stats(
            screen, skill_manager, self.x + 10, struct_y + 5,
        )

    def _get_structures_for_tab(
        self, building_system: BuildingSystem, tab: str,
    ) -> List[StructureDef]:
        """Get structure definitions for a tab category."""
        defs = building_system.structure_defs.get(tab, {})
        return list(defs.values())

    def _render_structure_entry(
        self,
        screen: pygame.Surface,
        struct_def: StructureDef,
        y: int,
        building_system: BuildingSystem,
        skill_manager: SkillManager,
    ) -> None:
        """Render a single structure entry."""
        x = self.x + 10
        width = self.panel_width - 20

        # Check if player can build this
        crafting_level = skill_manager.get_skill_level("crafting")
        allowed, reason = building_system.construction.can_place_structure(
            struct_def, crafting_level,
        )

        # Background
        bg_colour = (40, 60, 40) if allowed else (60, 30, 30)
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

    def _render_construction_stats(
        self,
        screen: pygame.Surface,
        skill_manager: SkillManager,
        x: int,
        y: int,
    ) -> None:
        """Render construction sub-stat bars."""
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

            self._hint_font.render(label_text, True, (160, 160, 180))
            pygame.draw.rect(screen, (50, 50, 70), (x, y, bar_width, 8))
            pygame.draw.rect(
                screen, (80, 140, 200),
                (x, y, fill_width, 8),
            )
            text = self._hint_font.render(f"  Lv {level}", True, (200, 200, 220))
            screen.blit(text, (x + bar_width + 5, y - 1))
            y += 14

    def handle_click(self, mx: int, my: int) -> Optional[str]:
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
        tabs = ["common", "defensive", "offensive", "decorative"]
        tab_y = self.y + 35
        tab_width = (self.panel_width - 20) // len(tabs)
        for i, tab in enumerate(tabs):
            tab_x = self.x + 10 + i * tab_width
            if (tab_x <= mx <= tab_x + tab_width - 4 and
                    tab_y <= my <= tab_y + 22):
                self.current_tab = tab
                return None

        # Check structure entry clicks
        if self._building_system is not None:
            structures = self._get_structures_for_tab(
                self._building_system, self.current_tab,
            )
            struct_y = tab_y + 30
            for struct in structures:
                entry_rect = (
                    self.x + 10, struct_y,
                    self.panel_width - 20, 45,
                )
                if (entry_rect[0] <= mx <= entry_rect[0] + entry_rect[2] and
                        entry_rect[1] <= my <= entry_rect[1] + entry_rect[3]):
                    self.selected_structure_id = struct.structure_id
                    return ("select", struct.structure_id)
                struct_y += 55

        # Return ("close",) for clicks within the panel area but outside tabs/structures
        if (self.x <= mx <= self.x + self.panel_width and
                self.y <= my <= self.y + self.panel_height):
            return ("close",)
        return None

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """
        Handle mouse movement for hover feedback on the building panel.

        Args:
            mx: Mouse X coordinate.
            my: Mouse Y coordinate.
        """
        # Current tab hit testing
        tabs = ["common", "defensive", "offensive", "decorative"]
        tab_y = self.y + 35
        tab_width = (self.panel_width - 20) // len(tabs)
        self._hovered_tab = False
        for i, tab in enumerate(tabs):
            tab_x = self.x + 10 + i * tab_width
            if (tab_x <= mx <= tab_x + tab_width - 4 and
                    tab_y <= my <= tab_y + 22):
                self._hovered_tab = True
                return
        # Structure entry hit testing
        if self._building_system is not None:
            structures = self._get_structures_for_tab(self._building_system, self.current_tab)
            struct_y = tab_y + 30
            for struct in structures:
                if (self.x + 10 <= mx <= self.x + self.panel_width - 10 and
                        struct_y <= my <= struct_y + 45):
                    self._hovered_structure = struct.structure_id
                    return
                struct_y += 55
            self._hovered_structure = None

    def handle_key(self, key: int) -> str | None:
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
            self._selected_structure_index = max(-1, self._selected_structure_index - 1)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self._selected_structure_index = min(len(self._structure_rects) - 1, self._selected_structure_index + 1)
        elif key in (pygame.K_a, pygame.K_LEFT):
            self._selected_structure_index = max(-1, self._selected_structure_index - 1)
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self._selected_structure_index = min(len(self._structure_rects) - 1, self._selected_structure_index + 1)
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_structure_index < len(self._structure_rects):
                _, structure_id = self._structure_rects[self._selected_structure_index]
                return f"place:{structure_id}"

        return None

    def handle_close(self) -> tuple:
        """
        Return the close action tuple for the building panel.

        Returns:
            Tuple ("close",).
        """
        return ("close",)
