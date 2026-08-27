"""
gear_panel.py — Gear management UI (PanelWindow subclass).

Shows equipped gear slots and allows equipping/unequipping
gear items from the player inventory.
Subclasses PanelWindow for unified chrome, viewport clipping, scrollbar,
keyboard navigation with visible selection, and mouse-wheel scrolling.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from combat.gear import GearItem, PlayerGear
    from inventory.inventory import Inventory


class GearPanel(PanelWindow):
    """
    Gear management panel.

    Layout:
    ┌──────────────────────────────────────────┐
    │  Gear (ESC to close)                     │
    ├──────────────────────────────────────────┤
    │  Weapon: [wooden_sword]  [Unequip]       │
    │         Dmg: 2  Spd: +0.0s               │
    │                                          │
    │  Armor:  [leather_armor] [Unequip]       │
    │         Def: 2  Spd: -0.1s               │
    │                                          │
    │  Available gear (click to equip):        │
    │  [wooden_sword] [iron_sword] [leather_..]│
    │  [iron_chestplate] [steel_sword]         │
    └──────────────────────────────────────────┘
    """

    PANEL_WIDTH = 360
    PANEL_HEIGHT = 480
    SLOT_HEIGHT = 60
    ITEM_ROW_HEIGHT = 36
    ITEM_GAP = 4

    BG_COLOR = (30, 30, 45)
    BORDER_COLOR = (100, 100, 140)
    SLOT_BG = (40, 40, 60)
    SLOT_HIGHLIGHT = (60, 60, 90)
    ITEM_BG = (45, 50, 45)
    ITEM_HOVER = (60, 70, 60)
    SLOT_EMPTY_BG = (35, 35, 50)
    BTN_COLOR = (60, 100, 160)
    BTN_HOVER = (80, 130, 200)

    def __init__(self) -> None:
        super().__init__(
            title="Gear",
            x=(WINDOW_WIDTH - 360) // 2,
            y=40,
            width=360,
            height=480,
            title_height=26,
            footer_height=0,
            has_scrollbar=True,
            show_close=True,
            selection_mode="grid",
            grid_cols=3,
            row_gap=4,
        )
        self.visible: bool = False
        # Cached data for rendering (set by game.py before render)
        self._player_gear: Optional["PlayerGear"] = None
        self._inventory: Optional["Inventory"] = None
        self._gear_map: Dict[str, "GearItem"] = {}
        # Runtime rects for click handling
        self._unequip_rects: List[Tuple[str, pygame.Rect]] = []  # (slot_type, rect)
        self._gear_items: List[Tuple[str, "GearItem", pygame.Rect]] = []

        # Font aliases for backward compatibility
        self.font_label = self.font_normal
        self.font_stat = self.font_small
        self.font_btn = self.font_bold

        # Backward compatibility attributes
        self._hovered_item: Optional[str] = None
        self._unequip_weapon_rect: Optional[pygame.Rect] = None
        self._unequip_armor_rect: Optional[pygame.Rect] = None

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable items (unequip buttons + available gear)."""
        count = 0
        if self._player_gear and self._player_gear.weapon:
            count += 1
        if self._player_gear and self._player_gear.armor:
            count += 1
        count += len(self._gear_items)
        return count

    def on_select(self, index: int) -> None:
        """Highlight the selected item."""
        pass

    # ── Data setters (called by game.py) ──────────────────────────────

    def set_data(self, player_gear: "PlayerGear", inventory: "Inventory", gear_map: Dict[str, "GearItem"]) -> None:
        """Set the data needed for rendering."""
        self._player_gear = player_gear
        self._inventory = inventory
        self._gear_map = gear_map

    # ── PanelWindow hooks ──────────────────────────────────────────────

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw gear slots and available items inside the clipped viewport."""
        self._interactive_rects.clear()
        self._unequip_rects.clear()
        self._gear_items.clear()

        if self._player_gear is None or self._inventory is None or self._gear_map is None:
            self._content_total_px = 0
            return

        left = content_rect.x + 10
        gap = self.row_gap
        y = content_rect.y + self._scroll_offset

        # ── Equipped slots ──────────────────────────────────────────
        slot_y = y

        # Weapon slot
        slot_y = self._render_equipped_slot(
            screen, "Weapon", self._player_gear.weapon, slot_y,
            "weapon", left, content_rect.width - 20,
        )
        slot_y += self.SLOT_HEIGHT + 8

        # Armor slot
        slot_y = self._render_equipped_slot(
            screen, "Armor", self._player_gear.armor, slot_y,
            "armor", left, content_rect.width - 20,
        )
        slot_y += self.SLOT_HEIGHT + 16

        # ── Available gear from inventory ───────────────────────────
        header = self.font_label.render("Click item to equip:", True, (170, 170, 200))
        screen.blit(header, (left, slot_y))
        slot_y += 20

        # Collect gear items from inventory
        item_ids = self._get_equippable_items(self._inventory, self._gear_map)
        cols = 3
        cell_w = (content_rect.width - 20) // cols
        cell_h = 32

        for i, item_id in enumerate(item_ids):
            gear_item = self._gear_map[item_id]
            col = i % cols
            row = i // cols

            item_x = left + col * cell_w
            item_y = slot_y + row * cell_h

            rect = pygame.Rect(item_x, item_y, cell_w - 4, cell_h)
            is_selected = self._is_gear_selected(item_id)

            # Check if currently equipped
            is_weapon_equipped = self._player_gear.weapon and self._player_gear.weapon.item_id == item_id
            is_armor_equipped = self._player_gear.armor and self._player_gear.armor.item_id == item_id

            if is_weapon_equipped:
                bg_color = (50, 50, 70)
            elif is_armor_equipped:
                bg_color = (50, 70, 50)
            elif is_selected:
                bg_color = self.ITEM_HOVER
            else:
                bg_color = self.ITEM_BG

            pygame.draw.rect(screen, bg_color, rect, border_radius=2)

            label = self.font_stat.render(gear_item.name, True, (200, 200, 220))
            screen.blit(label, (item_x + 3, item_y + 3))

            bonus = self._get_equipped_bonus_text(gear_item)
            if bonus:
                bonus_surf = self.font_stat.render(bonus, True, (150, 200, 150))
                screen.blit(bonus_surf, (item_x + 3, item_y + 16))

            self._gear_items.append((item_id, gear_item, rect))
            self._interactive_rects.append((rect, f"equip:{item_id}"))

        slot_y += ((len(item_ids) + cols - 1) // cols) * cell_h

        self._content_total_px = slot_y - content_rect.y + 20

    def _render_equipped_slot(
        self,
        screen: pygame.Surface,
        label: str,
        gear_item: Optional["GearItem"],
        y: int,
        slot_type: str,
        left: int,
        width: int,
    ) -> int:
        """Render an equipped gear slot (with or without item). Returns new y position."""
        rect = pygame.Rect(left, y, width, self.SLOT_HEIGHT)
        bg_color = self.SLOT_BG if gear_item else self.SLOT_EMPTY_BG
        is_selected = self._is_slot_selected(slot_type)
        if is_selected:
            bg_color = self.SLOT_HIGHLIGHT
        pygame.draw.rect(screen, bg_color, rect, border_radius=3)

        # Label
        label_surf = self.font_label.render(f"{label}:", True, (170, 170, 200))
        screen.blit(label_surf, (rect.x + 6, rect.y + 3))

        if gear_item:
            # Name
            name_surf = self.font_label.render(gear_item.name, True, (200, 200, 220))
            screen.blit(name_surf, (rect.x + 6, rect.y + 16))

            # Stat bonuses
            stat_text = self._get_equipped_bonus_text(gear_item)
            if stat_text:
                stat_surf = self.font_stat.render(stat_text, True, (150, 200, 150))
                screen.blit(stat_surf, (rect.x + 6, rect.y + 30))

            # Unequip button
            btn_x = rect.right - 60
            btn_w = 54
            btn_h = 20
            is_btn_selected = self._is_unequip_selected(slot_type)
            btn_color = self.BTN_HOVER if is_btn_selected else self.BTN_COLOR
            pygame.draw.rect(screen, btn_color, (btn_x, rect.y + 18, btn_w, btn_h), border_radius=2)
            btn_surf = self.font_btn.render("Unequip", True, (240, 240, 255))
            screen.blit(btn_surf, (btn_x + 4, rect.y + 21))

            unequip_rect = pygame.Rect(btn_x, rect.y + 18, btn_w, btn_h)
            self._unequip_rects.append((slot_type, unequip_rect))
            self._interactive_rects.append((unequip_rect, f"unequip:{slot_type}"))
        else:
            empty_surf = self.font_stat.render("(empty)", True, (120, 120, 140))
            screen.blit(empty_surf, (rect.x + 6, rect.y + 18))

        return y

    def _is_slot_selected(self, slot_type: str) -> bool:
        """Check if a specific slot is the currently selected one."""
        idx = 0
        if self._player_gear and self._player_gear.weapon:
            if slot_type == "weapon":
                return idx == self._selected_index
            idx += 1
        if self._player_gear and self._player_gear.armor:
            if slot_type == "armor":
                return idx == self._selected_index
            idx += 1
        return False

    def _is_unequip_selected(self, slot_type: str) -> bool:
        """Check if a specific unequip button is the currently selected one."""
        idx = 0
        if self._player_gear and self._player_gear.weapon:
            idx += 1  # weapon slot
            if slot_type == "weapon":
                return idx == self._selected_index
        if self._player_gear and self._player_gear.armor:
            idx += 1  # armor slot
            if slot_type == "armor":
                return idx == self._selected_index
        return False

    def _is_gear_selected(self, item_id: str) -> bool:
        """Check if a specific gear item is the currently selected one."""
        idx = 0
        if self._player_gear and self._player_gear.weapon:
            idx += 1  # weapon slot
            idx += 1  # weapon unequip
        if self._player_gear and self._player_gear.armor:
            idx += 1  # armor slot
            idx += 1  # armor unequip
        for i, (iid, _, _) in enumerate(self._gear_items):
            if iid == item_id:
                return idx == self._selected_index
            idx += 1
        return False

    @staticmethod
    def _get_equipped_bonus_text(gear_item: "GearItem") -> str:
        """Return a short stat bonus string for a gear item."""
        parts = []
        if gear_item.damage > 0:
            parts.append(f"Dmg: {gear_item.damage}")
        if gear_item.defence_bonus > 0:
            parts.append(f"Def: +{gear_item.defence_bonus}")
        if gear_item.attack_bonus > 0:
            parts.append(f"Atk: +{gear_item.attack_bonus}")
        if gear_item.speed_bonus != 0.0:
            sign = "+" if gear_item.speed_bonus > 0 else ""
            parts.append(f"Spd: {sign}{gear_item.speed_bonus:.1f}s")
        return " | ".join(parts) if parts else ""

    def _get_equippable_items(
        self, inventory: "Inventory", gear_map: Dict[str, "GearItem"],
    ) -> List[str]:
        """Return item_ids of gear items present in the player's inventory."""
        result = []
        for slot in inventory.slots:
            if slot is not None and slot.item_id and slot.quantity > 0:
                item_id = slot.item_id
                if item_id in gear_map and item_id not in result:
                    result.append(item_id)
        return result

    def on_key(self, key: int) -> str | None:
        """
        Keyboard navigation for the gear panel.

        Arrow keys / WASD: navigate items and unequip buttons
        Enter: return "equip:<item_id>" or "unequip:weapon"/"unequip:armor"

        Returns None for navigation only; action string on Enter.
        """
        # Grid navigation handled by base class
        if key == pygame.K_RETURN:
            if 0 <= self._selected_index < self.select_count():
                # Build the combined list in the same order as select_count
                idx = 0
                # Weapon slot
                if self._player_gear and self._player_gear.weapon:
                    if idx == self._selected_index:
                        return None  # slot itself not actionable
                    idx += 1
                    # Weapon unequip
                    if idx == self._selected_index:
                        return "unequip:weapon"
                    idx += 1
                # Armor slot
                if self._player_gear and self._player_gear.armor:
                    if idx == self._selected_index:
                        return None  # slot itself not actionable
                    idx += 1
                    # Armor unequip
                    if idx == self._selected_index:
                        return "unequip:armor"
                    idx += 1
                # Available gear items
                for item_id, _, _ in self._gear_items:
                    if idx == self._selected_index:
                        return f"equip:{item_id}"
                    idx += 1
        return None

    def on_click(self, x: int, y: int, button: int = 1) -> str | None:
        """
        Handle a click on the gear panel.

        Returns:
            Action string: "equip:<item_id>", "unequip:weapon", "unequip:armor", or None.
        """
        if not self.visible:
            return None

        for rect, payload in self._interactive_rects:
            if rect.collidepoint(x, y):
                return payload

        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Track hovered item for visual feedback and sync keyboard selection."""
        for i, (rect, _payload) in enumerate(self._interactive_rects):
            if rect.collidepoint(mx, my):
                self.select(i)
                # Update backward compatibility hover attribute
                if _payload.startswith("equip:"):
                    self._hovered_item = _payload.split(":", 1)[1]
                elif _payload.startswith("unequip:"):
                    self._hovered_item = f"unequip_{_payload.split(':', 1)[1]}"
                return
        self.select(-1)
        self._hovered_item = None

    # ── Compatibility render (for game.py) ──────────────────────────────

    def render(self, screen: pygame.Surface, player_gear: "PlayerGear", inventory: "Inventory", gear_map: Dict[str, "GearItem"]) -> None:
        """
        Render the gear panel with backward-compatible signature.

        Args:
            screen: The display surface.
            player_gear: The player's equipped gear.
            inventory: The player's inventory.
            gear_map: Dict of item_id -> GearItem from gear.json.
        """
        self.set_data(player_gear, inventory, gear_map)
        super().render(screen)