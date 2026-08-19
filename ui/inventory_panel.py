"""
inventory_panel.py — Inventory display panel.

Shows the player inventory in a 5×4 grid with gear slots.
Item cells render actual item sprites from the sprite renderer.
Left-click on an item uses/equips it; right-click drops it.
"""

from __future__ import annotations

import pygame
from core.state import GameState, PANEL_STATES
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List, Optional

    from inventory.inventory import Inventory
    from render.sprite_renderer import SpriteRenderer


class InventoryPanel:
    """
    Inventory panel: 5×4 grid showing player items + gear slots.

    Layout:
    ┌──────────────────────────────────────────┐
    │ [W: ][A: ] Gear slots (weapon, armor)    │
    │ [ ][item][ ][item][ ]                   │
    │ [item][ ][ ][ ][item]                   │
    │ [ ][ ][item][ ][ ]                      │
    │ [ ][ ][ ][item][ ]                      │
    └──────────────────────────────────────────┘
    Press ESC or I to close.
    """

    GRID_COLS = 5
    GRID_ROWS = 4
    CELL_SIZE = 48
    GAP = 4
    PANEL_X = 200
    PANEL_Y = 100

    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    CELL_BG = (50, 50, 60)
    CELL_HIGHLIGHT = (70, 70, 90)
    CELL_SELECTED = (90, 90, 120)
    SELECTED_BORDER = (180, 180, 220)
    GEAR_ROW_HEIGHT = 36

    def __init__(self, sprite_renderer: "SpriteRenderer | None" = None) -> None:
        self.inventory: "Inventory | None" = None
        self.sprite_renderer: "SpriteRenderer | None" = sprite_renderer
        self.font_small = pygame.font.SysFont("monospace", 12)
        self.font_bold = pygame.font.SysFont("monospace", 14, bold=True)
        self.visible = False
        # Cache clickable rects so handle_click doesn't need to recompute layout
        self._gear_slot_rects: List[tuple[pygame.Rect, str]] = []
        self._item_rects: List[tuple[pygame.Rect, str]] = []  # (rect, item_id)
        self._selected_item_index: int = -1

    def set_inventory(self, inventory: "Inventory") -> None:
        """Set the inventory reference."""
        self.inventory = inventory

    def set_sprite_renderer(self, sprite_renderer: "SpriteRenderer") -> None:
        """Set the sprite renderer for rendering item icons."""
        self.sprite_renderer = sprite_renderer

    def render(self, screen: pygame.Surface) -> None:
        """
        Render the inventory panel with gear slots and item sprites.

        Args:
            screen: The display surface.
        """
        if not self.visible or self.inventory is None:
            return

        snapshot = self.inventory.get_snapshot()

        self._item_rects = []

        # Count non-empty items and keep selection in range
        num_items = sum(1 for s in snapshot if s is not None)
        if self._selected_item_index < 0 and num_items > 0:
            self._selected_item_index = 0
        elif self._selected_item_index >= num_items:
            self._selected_item_index = -1

        panel_width = self.GRID_COLS * (self.CELL_SIZE + self.GAP) - self.GAP
        panel_height = self.GEAR_ROW_HEIGHT + self.GRID_ROWS * (self.CELL_SIZE + self.GAP) - self.GAP + 40
        panel_x = self.PANEL_X
        panel_y = self.PANEL_Y

        # Panel background
        pygame.draw.rect(screen, self.BG_COLOR, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(screen, self.BORDER_COLOR, (panel_x, panel_y, panel_width, panel_height), 2)

        # Title
        title = self.font_bold.render("Inventory", True, (200, 200, 220))
        title_x = panel_x + (panel_width - title.get_width()) // 2
        title_y = panel_y + 8
        screen.blit(title, (title_x, title_y))

        # ── Gear slots row ─────────────────────────────────────────
        gear_y = panel_y + 30
        gear_labels = ["W", "A"]  # Weapon, Armor
        self._gear_slot_rects = []
        for i, label in enumerate(gear_labels):
            gear_x = panel_x + i * (self.CELL_SIZE + self.GAP)
            slot_rect = pygame.Rect(gear_x, gear_y, self.CELL_SIZE, 28)
            self._gear_slot_rects.append((slot_rect, label))
            # Gear slot background
            pygame.draw.rect(screen, (60, 50, 70), (gear_x, gear_y, self.CELL_SIZE, 28))
            pygame.draw.rect(screen, (120, 100, 160), (gear_x, gear_y, self.CELL_SIZE, 28), 1)
            # Label
            label_surf = self.font_small.render(label, True, (200, 180, 240))
            label_rect = label_surf.get_rect(center=(gear_x + self.CELL_SIZE // 2, gear_y + 14))
            screen.blit(label_surf, label_rect)

        # ── Inventory grid ─────────────────────────────────────────
        grid_start_y = gear_y + 34

        for i, slot_data in enumerate(snapshot):
            row = i // self.GRID_COLS
            col = i % self.GRID_COLS

            cell_x = panel_x + col * (self.CELL_SIZE + self.GAP)
            cell_y = grid_start_y + row * (self.CELL_SIZE + self.GAP)

            # Cell background
            color = self.CELL_HIGHLIGHT if slot_data is not None else self.CELL_BG
            pygame.draw.rect(screen, color, (cell_x, cell_y, self.CELL_SIZE, self.CELL_SIZE))

            if slot_data is not None:
                item_id = slot_data["item_id"]
                item_rect = pygame.Rect(cell_x, cell_y, self.CELL_SIZE, self.CELL_SIZE)
                self._item_rects.append((item_rect, item_id))

                # Render item sprite (scaled to fit cell)
                if self.sprite_renderer is not None:
                    sprite = self.sprite_renderer._get_sprite(slot_data.get("sprite_key", item_id))
                    if sprite is not None:
                        # Scale sprite to fit within cell with small margin
                        margin = 6
                        avail_w = self.CELL_SIZE - margin * 2
                        avail_h = self.CELL_SIZE - margin * 2
                        sw = sprite.get_width()
                        sh = sprite.get_height()
                        scale = min(avail_w / sw, avail_h / sh) if sw > 0 and sh > 0 else 1.0
                        new_w = max(1, int(sw * scale))
                        new_h = max(1, int(sh * scale))
                        sprite = pygame.transform.scale(sprite, (new_w, new_h))
                        sx = cell_x + (self.CELL_SIZE - new_w) // 2
                        sy = cell_y + (self.CELL_SIZE - new_h) // 2
                        screen.blit(sprite, (sx, sy))

                # Quantity
                qty = str(slot_data["quantity"])
                qty_surf = self.font_small.render(qty, True, (255, 255, 150))
                qty_x = cell_x + self.CELL_SIZE - qty_surf.get_width() - 2
                qty_y = cell_y + self.CELL_SIZE - qty_surf.get_height() - 2
                screen.blit(qty_surf, (qty_x, qty_y))

                # Equipped indicator
                if slot_data.get("is_equipped", False):
                    pygame.draw.rect(screen, (100, 180, 100), (cell_x, cell_y, self.CELL_SIZE, self.CELL_SIZE), 2)

                # Selected item highlight (visible selection state)
                if i == self._selected_item_index:
                    pygame.draw.rect(screen, self.CELL_SELECTED, (cell_x + 2, cell_y + 2, self.CELL_SIZE - 4, self.CELL_SIZE - 4), 1)
                    pygame.draw.rect(screen, self.SELECTED_BORDER, (cell_x + 1, cell_y + 1, self.CELL_SIZE - 2, self.CELL_SIZE - 2), 2)

        # Close hint
        hint = self.font_small.render("Press ESC or C to close", True, (150, 150, 170))
        hint_x = panel_x + (panel_width - hint.get_width()) // 2
        hint_y = panel_y + panel_height + 10
        screen.blit(hint, (hint_x, hint_y))

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Sync selection index on hover over item cells."""
        for i, (rect, _item_id) in enumerate(self._item_rects):
            if rect.collidepoint(mx, my):
                self._selected_item_index = i
                return
        # If not hovering any item, don't reset selection — keep it until navigation

    def handle_key(self, key: int) -> tuple[str, str] | None:
        """
        Keyboard navigation for the inventory grid.

        Arrow keys / WASD: navigate grid (W/up moves up GRID_COLS, S/down moves down)
        Enter: return ("use", item_id) for the currently selected item
        Delete/Backspace: return ("drop", item_id) for the currently selected item

        Returns None for navigation only; action tuple on action keys.
        """
        # Map key codes for movement
        if key in (pygame.K_w, pygame.K_UP):
            self._selected_item_index = max(-1, self._selected_item_index - self.GRID_COLS)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self._selected_item_index = min(len(self._item_rects) - 1, self._selected_item_index + self.GRID_COLS)
        elif key in (pygame.K_a, pygame.K_LEFT):
            self._selected_item_index = max(-1, self._selected_item_index - 1)
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self._selected_item_index = min(len(self._item_rects) - 1, self._selected_item_index + 1)
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_item_index < len(self._item_rects):
                _, item_id = self._item_rects[self._selected_item_index]
                return ("use", item_id)
        elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if 0 <= self._selected_item_index < len(self._item_rects):
                _, item_id = self._item_rects[self._selected_item_index]
                return ("drop", item_id)
        return None

    def handle_click(self, x: int, y: int, button: int = 1) -> tuple[str, str] | None:
        """
        Handle a click on the inventory panel.

        Args:
            x: Click X coordinate (screen space).
            y: Click Y coordinate (screen space).
            button: Mouse button — 1 = left, 2 = right, 3 = right.

        Returns:
            ("use", item_id) for left-click on item cells,
            ("drop", item_id) for right-click on item cells,
            ("gear", "weapon") / ("gear", "armor") for gear slot clicks.
            None for clicks outside interactive areas.
        """
        if not self.visible:
            return None

        # Check gear slot clicks (both buttons)
        for slot_rect, label in self._gear_slot_rects:
            if slot_rect.collidepoint(x, y):
                return ("gear", label)

        # Check item cell clicks
        for rect, item_id in self._item_rects:
            if rect.collidepoint(x, y):
                if button in (2, 3):
                    return ("drop", item_id)
                return ("use", item_id)

        return None

    def get_item_at(self, x: int, y: int) -> str | None:
        """Return the item_id at the given coordinates, or None."""
        if not self.visible:
            return None
        for rect, item_id in self._item_rects:
            if rect.collidepoint(x, y):
                return item_id
        return None