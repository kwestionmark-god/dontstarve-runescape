"""
inventory_panel.py — Inventory display panel (PanelWindow subclass).

Shows the player inventory in a 5×4 grid with gear slots.
Item cells render actual item sprites from the sprite renderer.
Left-click on an item uses/equips it; right-click drops it.
Subclasses PanelWindow for unified chrome, viewport clipping, scrollbar,
keyboard navigation with visible selection, and mouse-wheel scrolling.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from typing import Dict, List, Optional

    from inventory.inventory import Inventory
    from render.sprite_renderer import SpriteRenderer


class InventoryPanel(PanelWindow):
    """
    Inventory panel: 5×4 grid showing player items + gear slots.
    """

    GRID_COLS = 5
    GRID_ROWS = 4
    CELL_SIZE = 48
    GAP = 4
    GEAR_ROW_HEIGHT = 36

    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    CELL_BG = (50, 50, 60)
    CELL_HIGHLIGHT = (70, 70, 90)
    CELL_SELECTED = (90, 90, 120)
    SELECTED_BORDER = (180, 180, 220)

    def __init__(self, sprite_renderer: "SpriteRenderer | None" = None) -> None:
        super().__init__(
            title="Inventory",
            x=200,
            y=100,
            width=5 * (48 + 4) - 4 + 20,  # grid width + padding
            height=36 + 4 * (48 + 4) - 4 + 60,  # gear row + grid + title/footer
            title_height=26,
            footer_height=22,
            has_scrollbar=False,  # inventory grid fits in panel
            show_close=True,
            selection_mode="grid",
            grid_cols=5,
            row_gap=4,
        )
        self.inventory: "Inventory | None" = None
        self.sprite_renderer: "SpriteRenderer | None" = sprite_renderer
        # Runtime rects for click handling
        self._gear_slot_rects: list[tuple[pygame.Rect, str]] = []
        self._item_rects: list[tuple[pygame.Rect, str]] = []  # (rect, item_id)

    def set_inventory(self, inventory: "Inventory") -> None:
        """Set the inventory reference."""
        self.inventory = inventory

    def set_sprite_renderer(self, sprite_renderer: "SpriteRenderer") -> None:
        """Set the sprite renderer for rendering item icons."""
        self.sprite_renderer = sprite_renderer

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable items (only non-empty item cells)."""
        return len(self._item_rects)

    def on_select(self, index: int) -> None:
        """Highlight the selected item."""
        pass

    # ── PanelWindow hooks ────────────────────────────────────────────────

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw inventory grid inside the clipped viewport."""
        self._interactive_rects.clear()
        self._gear_slot_rects.clear()
        self._item_rects.clear()

        if self.inventory is None:
            self._content_total_px = 0
            return

        snapshot = self.inventory.get_snapshot()

        # Count non-empty items and keep selection in range
        num_items = sum(1 for s in snapshot if s is not None)
        if self._selected_index < 0 and num_items > 0:
            self._selected_index = 0
        elif self._selected_index >= num_items:
            self._selected_index = -1

        left = content_rect.x + 10
        gap = self.row_gap
        y = content_rect.y + self._scroll_offset

        # Title is drawn by base class

        # ── Gear slots row ─────────────────────────────────────────
        gear_y = y
        gear_labels = ["W", "A"]  # Weapon, Armor
        for i, label in enumerate(gear_labels):
            gear_x = left + i * (self.CELL_SIZE + self.GAP)
            slot_rect = pygame.Rect(gear_x, gear_y, self.CELL_SIZE, 28)
            self._gear_slot_rects.append((slot_rect, label))
            self._interactive_rects.append((slot_rect, f"gear:{label}"))
            # Gear slot background
            pygame.draw.rect(screen, (60, 50, 70), (gear_x, gear_y, self.CELL_SIZE, 28))
            pygame.draw.rect(screen, (120, 100, 160), (gear_x, gear_y, self.CELL_SIZE, 28), 1)
            # Label
            label_surf = self.font_small.render(label, True, (200, 180, 240))
            label_rect = label_surf.get_rect(center=(gear_x + self.CELL_SIZE // 2, gear_y + 14))
            screen.blit(label_surf, label_rect)

        # ── Inventory grid ─────────────────────────────────────────
        grid_start_y = gear_y + 34
        grid_w = self.GRID_COLS * (self.CELL_SIZE + self.GAP) - self.GAP

        for i, slot_data in enumerate(snapshot):
            row = i // self.GRID_COLS
            col = i % self.GRID_COLS

            cell_x = left + col * (self.CELL_SIZE + self.GAP)
            cell_y = grid_start_y + row * (self.CELL_SIZE + self.GAP)

            # Cell background
            color = self.CELL_HIGHLIGHT if slot_data is not None else self.CELL_BG
            pygame.draw.rect(screen, color, (cell_x, cell_y, self.CELL_SIZE, self.CELL_SIZE))

            if slot_data is not None:
                item_id = slot_data["item_id"]
                item_rect = pygame.Rect(cell_x, cell_y, self.CELL_SIZE, self.CELL_SIZE)
                self._item_rects.append((item_rect, item_id))
                self._interactive_rects.append((item_rect, f"item:{item_id}"))

                # Render item sprite (scaled to fit cell)
                if self.sprite_renderer is not None:
                    sprite = self.sprite_renderer._get_sprite(slot_data.get("sprite_key", item_id))
                    if sprite is not None:
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
                item_idx = len(self._item_rects) - 1
                if item_idx == self._selected_index:
                    pygame.draw.rect(screen, self.CELL_SELECTED, (cell_x + 2, cell_y + 2, self.CELL_SIZE - 4, self.CELL_SIZE - 4), 1)
                    pygame.draw.rect(screen, self.SELECTED_BORDER, (cell_x + 1, cell_y + 1, self.CELL_SIZE - 2, self.CELL_SIZE - 2), 2)

        self._content_total_px = grid_start_y + self.GRID_ROWS * (self.CELL_SIZE + self.GAP) - self.GAP - content_rect.y + 20

    def on_key(self, key: int) -> tuple[str, str] | None:
        """
        Keyboard navigation for the inventory grid.

        Arrow keys / WASD: navigate grid (W/up moves up GRID_COLS, S/down moves down)
        Enter: return ("use", item_id) for the currently selected item
        Delete/Backspace: return ("drop", item_id) for the currently selected item

        Returns None for navigation only; action tuple on action keys.
        """
        # Grid navigation handled by base class via selection_mode="grid"
        if key == pygame.K_RETURN:
            if 0 <= self._selected_index < len(self._item_rects):
                _, item_id = self._item_rects[self._selected_index]
                return ("use", item_id)
        elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if 0 <= self._selected_index < len(self._item_rects):
                _, item_id = self._item_rects[self._selected_index]
                return ("drop", item_id)
        return None

    def on_click(self, x: int, y: int, button: int = 1) -> tuple[str, str] | None:
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

        for rect, payload in self._interactive_rects:
            if rect.collidepoint(x, y):
                if payload.startswith("gear:"):
                    _, label = payload.split(":", 1)
                    return ("gear", label)
                elif payload.startswith("item:"):
                    _, item_id = payload.split(":", 1)
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