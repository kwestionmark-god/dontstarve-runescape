"""
crafting_panel.py — Crafting menu UI.

Shows available recipes filtered by the player's inventory.
Click a recipe to craft it.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from utils.structure_utils import is_structure_nearby

if TYPE_CHECKING:
    from typing import Dict, List, Optional, Tuple

    from crafting.crafting_system import CraftingSystem
    from inventory.inventory import Inventory


class CraftingPanel:
    """
    Crafting panel: Shows recipes grouped by processing chain.

    Layout:
    ┌──────────────────────────────────────────┐
    │  ┌─ Wood Chain ──────────────────────┐   │
    │  │ [Planks]  Need: logs[3/3]  ✓      │   │
    │  │ [Charcoal]  Need: logs[1/3]  ✓    │   │
    │  └────────────────────────────────────┘   │
    │  ┌─ Stone Chain ───────────────────┐     │
    │  │ [Chert]  Need: stone[1/5]  ✓    │   │
    │  └──────────────────────────────────┘   │
    │  Press ESC or Q to close               │
    └──────────────────────────────────────────┘
    """

    PANEL_X = 300
    PANEL_Y = 50
    PANEL_WIDTH = 450

    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    CHAIN_BG = (35, 35, 45)
    RECIPE_BG = (45, 45, 55)
    AVAILABLE_COLOR = (100, 180, 100)
    UNAVAILABLE_COLOR = (180, 100, 100)
    BUTTON_COLOR = (80, 120, 80)
    BUTTON_HOVER = (100, 150, 100)

    def __init__(self) -> None:
        self.crafting: "CraftingSystem | None" = None
        self.inventory: "Inventory | None" = None
        self.metallurgy: object | None = None
        self.font_small = pygame.font.SysFont("monospace", 11)
        self.font = pygame.font.SysFont("monospace", 13)
        self.font_bold = pygame.font.SysFont("monospace", 14, bold=True)
        self.visible = False
        self._recipe_rects: List[tuple[pygame.Rect, str]] = []  # (rect, recipe_id)
        self._smelt_rects: List[tuple[pygame.Rect, str]] = []  # (rect, smelt_id)
        self._all_recipe_rects: List[tuple[pygame.Rect, str]] = []  # (rect, recipe_id) for all craft+smelt
        self._selected_recipe_index: int = -1
        # Station proximity data — set by game when panel opens
        self._structures: list | None = None
        self._player_x: float = 0.0
        self._player_y: float = 0.0

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

    def render(self, screen: pygame.Surface) -> None:
        """
        Render the crafting panel.

        Args:
            screen: The display surface.
        """
        if not self.visible or self.crafting is None or self.inventory is None:
            return

        self._recipe_rects = []
        self._smelt_rects = []
        self._all_recipe_rects = []

        panel_x = self.PANEL_X
        panel_y = self.PANEL_Y

        # Panel background
        pygame.draw.rect(screen, self.BG_COLOR, (panel_x, panel_y, self.PANEL_WIDTH, 500))
        pygame.draw.rect(screen, self.BORDER_COLOR, (panel_x, panel_y, self.PANEL_WIDTH, 500), 2)

        # Title
        title = self.font_bold.render("Crafting", True, (200, 200, 220))
        title_x = panel_x + (self.PANEL_WIDTH - title.get_width()) // 2
        screen.blit(title, (title_x, panel_y + 8))

        y_offset = panel_y + 35

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
            screen.blit(chain_surf, (panel_x + 10, y_offset))
            y_offset += 22

            # Chain background
            chain_h = len(recipes) * 32 + 10
            pygame.draw.rect(
                screen, self.CHAIN_BG,
                (panel_x + 5, y_offset - 22, self.PANEL_WIDTH - 10, chain_h),
            )

            for recipe in recipes:
                # Recipe row
                row_y = y_offset
                row_h = 30

                # Check if recipe is locked behind a quest
                is_locked = (
                    self.crafting.is_recipe_locked(recipe.recipe_id)
                    if self.crafting is not None
                    else False
                )

                # Recipe name — dim if locked
                name_color = (160, 160, 170) if is_locked else (220, 220, 220)
                name_surf = self.font.render(recipe.name, True, name_color)
                screen.blit(name_surf, (panel_x + 15, row_y + 8))

                # Locked indicator
                if is_locked:
                    lock_surf = self.font.render("\U0001f512", True, (200, 180, 50))
                    screen.blit(lock_surf, (panel_x + 15 + name_surf.get_width() + 8, row_y + 8))

                # Material status
                status_x = panel_x + 160
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
                btn_x = panel_x + self.PANEL_WIDTH - 70
                btn_y = row_y + 5
                btn_w = 60
                btn_h = 20
                btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                self._recipe_rects.append((btn_rect, recipe.recipe_id))

                # Check station proximity for recipes that require one
                requires_structure = getattr(recipe, "requires_structure", None)
                station_missing = False
                station_name = ""
                if (
                    requires_structure
                    and self._structures is not None
                    and not is_structure_nearby(
                        self._structures, self._player_x, self._player_y, requires_structure,
                    )
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
                pygame.draw.rect(screen, btn_color, btn_rect)
                pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
                btn_tx = btn_x + (btn_w - btn_text.get_width()) // 2
                btn_ty = btn_y + (btn_h - btn_text.get_height()) // 2
                screen.blit(btn_text, (btn_tx, btn_ty))

                y_offset += row_h + 2

                # Track in combined list
                self._all_recipe_rects.append((btn_rect, recipe.recipe_id))

            y_offset += 8

        # ── Smelting Recipes (Phase 2) ─────────────────────────────
        if self.metallurgy is not None:
            smelt_header = self.font_bold.render("Smelting", True, (180, 160, 120))
            screen.blit(smelt_header, (panel_x + 10, y_offset))
            y_offset += 22

            # Chain background
            pygame.draw.rect(
                screen, self.CHAIN_BG,
                (panel_x + 5, y_offset - 22, self.PANEL_WIDTH - 10, 6),
            )
            y_offset += 4

            unlocked_recipes = self.metallurgy.get_unlocked_recipes()
            for smelt_recipe in unlocked_recipes:
                row_y = y_offset
                row_h = 30

                # Recipe name
                name_surf = self.font.render(smelt_recipe.name.replace("_", " ").title(), True, (220, 220, 220))
                screen.blit(name_surf, (panel_x + 15, row_y + 8))

                # Material status
                status_x = panel_x + 160
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
                btn_x = panel_x + self.PANEL_WIDTH - 70
                btn_y = row_y + 5
                btn_w = 60
                btn_h = 20
                btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                self._smelt_rects.append((btn_rect, smelt_recipe.recipe_id))
                color = self.BUTTON_COLOR if can_smelt else (60, 60, 60)
                pygame.draw.rect(screen, color, btn_rect)
                pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
                btn_text = self.font_small.render("Smelt", True, (255, 255, 255))
                btn_tx = btn_x + (btn_w - btn_text.get_width()) // 2
                btn_ty = btn_y + (btn_h - btn_text.get_height()) // 2
                screen.blit(btn_text, (btn_tx, btn_ty))

                y_offset += row_h + 2

                # Track in combined list
                self._all_recipe_rects.append((btn_rect, smelt_recipe.recipe_id))

            y_offset += 8

        # Close hint
        hint = self.font_small.render("Press ESC or H to close", True, (150, 150, 170))
        hint_x = panel_x + (self.PANEL_WIDTH - hint.get_width()) // 2
        hint_y = panel_y + 490
        screen.blit(hint, (hint_x, hint_y))

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

    def handle_click(self, x: int, y: int) -> tuple[str, str] | None:
        """
        Handle a click on a craft or smelt button.

        Returns:
            ("craft", recipe_id) for regular crafts,
            ("smelt", smelt_id) for metallurgy smelts, or None.
        """
        for btn_rect, smelt_id in self._smelt_rects:
            if btn_rect.collidepoint(x, y):
                return ("smelt", smelt_id)
        for btn_rect, recipe_id in self._recipe_rects:
            if btn_rect.collidepoint(x, y):
                return ("craft", recipe_id)
        return None

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Sync selection index on hover over recipe/smelt buttons."""
        for i, (rect, _recipe_id) in enumerate(self._all_recipe_rects):
            if rect.collidepoint(mx, my):
                self._selected_recipe_index = i
                return
        # Don't reset selection when not hovering

    def handle_key(self, key: int) -> tuple[str, str] | None:
        """
        Keyboard navigation for the crafting panel recipe list.

        Arrow keys / WASD: navigate recipe list
        Enter: return ("craft", recipe_id) or ("smelt", recipe_id) based on which rect was hit

        Returns None for navigation only; action tuple on Enter.
        """
        if key in (pygame.K_w, pygame.K_UP):
            self._selected_recipe_index = max(-1, self._selected_recipe_index - 1)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self._selected_recipe_index = min(len(self._all_recipe_rects) - 1, self._selected_recipe_index + 1)
        elif key in (pygame.K_a, pygame.K_LEFT):
            self._selected_recipe_index = max(-1, self._selected_recipe_index - 1)
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self._selected_recipe_index = min(len(self._all_recipe_rects) - 1, self._selected_recipe_index + 1)
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_recipe_index < len(self._all_recipe_rects):
                _, recipe_id = self._all_recipe_rects[self._selected_recipe_index]
                # Determine if it's a smelt recipe or regular craft
                is_smelt = any(sid == recipe_id for _, sid in self._smelt_rects)
                if is_smelt:
                    return ("smelt", recipe_id)
                return ("craft", recipe_id)
        return None
