"""
crafting_panel.py — Crafting menu UI (PanelWindow subclass).

Shows available recipes filtered by the player's inventory.
Click a recipe to craft it. Subclasses PanelWindow for unified chrome,
viewport clipping, scrollbar, keyboard navigation with visible selection,
and mouse-wheel scrolling.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from typing import Dict, List, Optional, Tuple

    from crafting.crafting_system import CraftingSystem
    from inventory.inventory import Inventory


class CraftingPanel(PanelWindow):
    """
    Crafting panel: Shows recipes grouped by processing chain.
    """

    PROGRESS_COLOR = (100, 180, 100)
    BUTTON_COLOR = (80, 120, 80)
    BUTTON_HOVER = (100, 150, 100)
    AVAILABLE_COLOR = (100, 180, 100)
    UNAVAILABLE_COLOR = (180, 100, 100)

    def __init__(self) -> None:
        super().__init__(
            title="Crafting",
            x=300,
            y=50,
            width=450,
            height=500,
            title_height=26,
            footer_height=22,
            has_scrollbar=True,
            show_close=True,
            selection_mode="list",
            row_gap=2,
        )
        self.crafting: "CraftingSystem | None" = None
        self.inventory: "Inventory | None" = None
        self.metallurgy: object | None = None
        # Station proximity data — set by game when panel opens
        self._structures: list | None = None
        self._player_x: float = 0.0
        self._player_y: float = 0.0
        # Runtime rects for click handling
        self._all_recipe_rects: list[tuple[pygame.Rect, str, str]] = []  # (rect, recipe_id, type)

    def set_crafting(self, crafting: "CraftingSystem") -> None:
        """Set the crafting system reference."""
        self.crafting = crafting

    def set_inventory(self, inventory: "Inventory") -> None:
        """Set the inventory reference."""
        self.inventory = inventory

    def set_metallurgy(self, metallurgy: object) -> None:
        """Set the metallurgy skill reference for smelting recipes."""
        self.metallurgy = metallurgy

    def set_station_data(self, structures: list | None, player_x: float, player_y: float) -> None:
        """Set nearby structure list and player position for proximity checks."""
        self._structures = structures
        self._player_x = player_x
        self._player_y = player_y

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable items (all recipe/smelt buttons)."""
        return len(self._all_recipe_rects)

    def on_select(self, index: int) -> None:
        """Highlight the selected button."""
        pass

    # ── PanelWindow hooks ────────────────────────────────────────────────

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw crafting recipes inside the clipped viewport."""
        self._interactive_rects.clear()
        self._all_recipe_rects.clear()

        if self.crafting is None or self.inventory is None:
            self._content_total_px = 0
            return

        left = content_rect.x + 10
        gap = self.row_gap
        y = content_rect.y + self._scroll_offset

        # Title is drawn by base class

        # Get ALL recipes (including locked) grouped by chain
        all_recipes = list(self.crafting.recipes.values())
        chains: dict[str, list] = {}
        for recipe in all_recipes:
            chain = recipe.processing_chain
            if chain not in chains:
                chains[chain] = []
            chains[chain].append(recipe)

        for chain_name, recipes in sorted(chains.items()):
            # Chain header
            chain_label = chain_name.replace("_", " ").title()
            chain_surf = self.font_bold.render(chain_label, True, (180, 160, 120))
            screen.blit(chain_surf, (left, y))
            y += 22

            # Chain background
            chain_h = len(recipes) * 32 + 10
            pygame.draw.rect(
                screen, (35, 35, 45),
                (left - 5, y - 22, content_rect.width - 10, chain_h),
            )

            for recipe in recipes:
                # Recipe row
                row_y = y
                row_h = 30

                # Check if recipe is locked behind a quest
                is_locked = (
                    self.crafting.is_recipe_locked(recipe.recipe_id)
                    if self.crafting is not None
                    else False
                )

                # Recipe name — dim if locked
                name_color = (160, 160, 170) if is_locked else (220, 220, 220)
                name_surf = self.font_normal.render(recipe.name, True, name_color)
                screen.blit(name_surf, (left, row_y + 8))

                # Locked indicator
                if is_locked:
                    lock_surf = self.font_normal.render("\U0001f512", True, (200, 180, 50))
                    screen.blit(lock_surf, (left + name_surf.get_width() + 8, row_y + 8))

                # Material status
                status_x = left + 150
                for item_id, required, available in self.crafting.get_material_status(
                    recipe.recipe_id, self.inventory
                ):
                    avail_str = f"{available}/{required}"
                    color = self.AVAILABLE_COLOR if available >= required else self.UNAVAILABLE_COLOR
                    mat_surf = self.font_small.render(f"{item_id}: {avail_str}", True, color)
                    screen.blit(mat_surf, (status_x, row_y + 8))
                    status_x += 100

                # Craft button — disabled if locked, no materials, or missing station
                can_craft = (
                    not is_locked
                    and self.crafting.validate_recipe(recipe.recipe_id, self.inventory)
                )
                btn_x = content_rect.x + content_rect.width - 70
                btn_y = row_y + 5
                btn_w = 60
                btn_h = 20
                btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

                # Check station proximity for recipes that require one
                requires_structure = getattr(recipe, "requires_structure", None)
                station_missing = False
                station_name = ""
                if (
                    requires_structure
                    and self._structures is not None
                ):
                    from utils.structure_utils import is_structure_nearby
                    if not is_structure_nearby(
                        self._structures, self._player_x, self._player_y, requires_structure,
                    ):
                        station_missing = True
                        station_name = requires_structure.replace("_", " ").title()
                        can_craft = False

                if is_locked:
                    btn_color = (80, 60, 60)
                    btn_text = self.font_small.render("Locked", True, (180, 140, 140))
                elif station_missing:
                    btn_color = (60, 60, 60)
                    btn_text = self.font_small.render(f"Needs {station_name}", True, (180, 160, 100))
                elif can_craft:
                    btn_color = self.BUTTON_COLOR
                    btn_text = self.font_small.render("Craft", True, (255, 255, 255))
                else:
                    btn_color = (60, 60, 60)
                    btn_text = self.font_small.render("Craft", True, (255, 255, 255))

                is_selected = self._is_recipe_selected(recipe.recipe_id)
                if is_selected:
                    btn_color = self.BUTTON_HOVER
                pygame.draw.rect(screen, btn_color, btn_rect)
                pygame.draw.rect(screen, self.COLOR_BORDER, btn_rect, 1)
                btn_tx = btn_x + (btn_w - btn_text.get_width()) // 2
                btn_ty = btn_y + (btn_h - btn_text.get_height()) // 2
                screen.blit(btn_text, (btn_tx, btn_ty))

                self._interactive_rects.append((btn_rect, f"craft:{recipe.recipe_id}"))
                self._all_recipe_rects.append((btn_rect, recipe.recipe_id, "craft"))

                y += row_h + 2

            y += 8

        # ── Smelting Recipes ─────────────────────────────
        if self.metallurgy is not None:
            smelt_header = self.font_bold.render("Smelting", True, (180, 160, 120))
            screen.blit(smelt_header, (left, y))
            y += 22

            # Chain background
            pygame.draw.rect(
                screen, (35, 35, 45),
                (left - 5, y - 22, content_rect.width - 10, 6),
            )
            y += 4

            unlocked_recipes = self.metallurgy.get_unlocked_recipes()
            for smelt_recipe in unlocked_recipes:
                row_y = y
                row_h = 30

                # Recipe name
                name_surf = self.font_normal.render(smelt_recipe.name.replace("_", " ").title(), True, (220, 220, 220))
                screen.blit(name_surf, (left, row_y + 8))

                # Material status
                status_x = left + 150
                # Ore
                ore_qty = self.inventory.get_item_quantity(smelt_recipe.ore_item) if self.inventory else 0
                ore_color = self.AVAILABLE_COLOR if ore_qty >= 1 else self.UNAVAILABLE_COLOR
                ore_surf = self.font_small.render(f"{smelt_recipe.ore_item}: {ore_qty}/1", True, ore_color)
                screen.blit(ore_surf, (status_x, row_y + 8))
                status_x += 100

                # Fuel
                if self.inventory:
                    fuel_qty = self.inventory.get_item_quantity(smelt_recipe.fuel_item)
                else:
                    fuel_qty = 0
                fuel_color = self.AVAILABLE_COLOR if fuel_qty >= 1 else self.UNAVAILABLE_COLOR
                fuel_surf = self.font_small.render(f"{smelt_recipe.fuel_item}: {fuel_qty}/1", True, fuel_color)
                screen.blit(fuel_surf, (status_x, row_y + 8))
                status_x += 100

                # Extra input (e.g. tin_ore for bronze)
                if smelt_recipe.extra_input:
                    extra_qty = self.inventory.get_item_quantity(smelt_recipe.extra_input) if self.inventory else 0
                    extra_color = self.AVAILABLE_COLOR if extra_qty >= smelt_recipe.extra_quantity else self.UNAVAILABLE_COLOR
                    extra_surf = self.font_small.render(
                        f"{smelt_recipe.extra_input}: {extra_qty}/{smelt_recipe.extra_quantity}", True, extra_color,
                    )
                    screen.blit(extra_surf, (status_x, row_y + 8))

                # Smelt button
                can_smelt = self._can_smelt(smelt_recipe)
                btn_x = content_rect.x + content_rect.width - 70
                btn_y = row_y + 5
                btn_w = 60
                btn_h = 20
                btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)

                is_selected = self._is_recipe_selected(smelt_recipe.recipe_id)
                color = self.BUTTON_HOVER if is_selected else (self.BUTTON_COLOR if can_smelt else (60, 60, 60))
                pygame.draw.rect(screen, color, btn_rect)
                pygame.draw.rect(screen, self.COLOR_BORDER, btn_rect, 1)
                btn_text = self.font_small.render("Smelt", True, (255, 255, 255))
                btn_tx = btn_x + (btn_w - btn_text.get_width()) // 2
                btn_ty = btn_y + (btn_h - btn_text.get_height()) // 2
                screen.blit(btn_text, (btn_tx, btn_ty))

                y += row_h + 2

                self._interactive_rects.append((btn_rect, f"smelt:{smelt_recipe.recipe_id}"))
                self._all_recipe_rects.append((btn_rect, smelt_recipe.recipe_id, "smelt"))

            y += 8

        # Footer hint
        hint = self.font_small.render("Press ESC or Q to close", True, (150, 150, 170))
        hint_x = content_rect.x + (content_rect.width - hint.get_width()) // 2
        hint_y = content_rect.y + content_rect.height - 20
        screen.blit(hint, (hint_x, hint_y))

        self._content_total_px = y - content_rect.y + 30

    def _is_recipe_selected(self, recipe_id: str) -> bool:
        """Check if a specific recipe is the currently selected one."""
        for i, (_, rid, _type) in enumerate(self._all_recipe_rects):
            if rid == recipe_id:
                return i == self._selected_index
        return False

    def _can_smelt(self, smelt_recipe) -> bool:
        """Check if the player has all materials for a smelt recipe."""
        if self.inventory is None or self.metallurgy is None:
            return False
        # Check ore
        if not self.inventory.has_items(smelt_recipe.ore_item, 1):
            return False
        # Check fuel
        fuel_cost = self.metallurgy.get_effective_fuel_cost(smelt_recipe.base_fuel_cost)
        if not self.inventory.has_items(smelt_recipe.fuel_item, fuel_cost):
            return False
        # Check extra input
        if smelt_recipe.extra_input and not self.inventory.has_items(
            smelt_recipe.extra_input, smelt_recipe.extra_quantity
        ):
            return False
        return True

    def on_key(self, key: int):
        """Handle panel-specific keys: Enter to craft/smelt."""
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if 0 <= self._selected_index < len(self._all_recipe_rects):
                _, recipe_id, rtype = self._all_recipe_rects[self._selected_index]
                return (rtype, recipe_id)
        return None

    def on_click(self, x: int, y: int, button: int = 1):
        """Handle clicks on craft/smelt buttons."""
        for rect, payload in self._interactive_rects:
            if rect.collidepoint(x, y):
                # Parse payload: "craft:recipe_id" or "smelt:recipe_id"
                try:
                    rtype, recipe_id = payload.split(":", 1)
                    return (rtype, recipe_id)
                except ValueError:
                    pass
        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Sync selection index on hover over recipe/smelt buttons."""
        for i, (rect, _payload) in enumerate(self._interactive_rects):
            if rect.collidepoint(mx, my):
                self.select(i)
                return
        self.select(-1)