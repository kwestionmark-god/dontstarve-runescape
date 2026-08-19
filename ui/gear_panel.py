"""
gear_panel.py — Gear management UI.

Shows equipped gear slots and allows equipping/unequipping
gear items from the player inventory.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from config import WINDOW_WIDTH, WINDOW_HEIGHT

if TYPE_CHECKING:
    from combat.gear import GearItem, PlayerGear
    from inventory.inventory import Inventory


class GearPanel:
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
    PANEL_X = (WINDOW_WIDTH - PANEL_WIDTH) // 2
    PANEL_Y = 40

    BG_COLOR = (30, 30, 45)
    BORDER_COLOR = (100, 100, 140)
    SLOT_BG = (40, 40, 60)
    SLOT_HIGHLIGHT = (60, 60, 90)
    ITEM_BG = (45, 50, 45)
    ITEM_HOVER = (60, 70, 60)
    SLOT_EMPTY_BG = (35, 35, 50)
    BTN_COLOR = (60, 100, 160)
    BTN_HOVER = (80, 130, 200)

    SLOT_HEIGHT = 60
    ITEM_ROW_HEIGHT = 36
    ITEM_GAP = 4

    def __init__(self) -> None:
        self.visible: bool = False
        self.font_title = pygame.font.SysFont("monospace", 16, bold=True)
        self.font_label = pygame.font.SysFont("monospace", 12)
        self.font_stat = pygame.font.SysFont("monospace", 11)
        self.font_btn = pygame.font.SysFont("monospace", 11, bold=True)

        # Slot info rectangles for click detection
        self._weapon_rect: Optional[pygame.Rect] = None
        self._armor_rect: Optional[pygame.Rect] = None
        self._unequip_weapon_rect: Optional[pygame.Rect] = None
        self._unequip_armor_rect: Optional[pygame.Rect] = None

        # Available gear item rectangles
        self._gear_items: List[Tuple[str, GearItem, pygame.Rect]] = []
        self._unequip_rects: List[tuple[str, pygame.Rect]] = []  # (slot_type, rect)

        # Hover state
        self._hovered_item: Optional[str] = None

        # Keyboard selection
        self._selected_gear_index: int = -1

    def render(
        self,
        screen: pygame.Surface,
        player_gear: "PlayerGear",
        inventory: "Inventory",
        gear_map: Dict[str, "GearItem"],
    ) -> None:
        """
        Render the gear panel.

        Args:
            screen: The display surface.
            player_gear: The player's equipped gear.
            inventory: The player's inventory.
            gear_map: Dict of item_id -> GearItem from gear.json.
        """
        panel_w = self.PANEL_WIDTH
        panel_h = self.PANEL_HEIGHT
        panel_x = self.PANEL_X
        panel_y = self.PANEL_Y

        # Background
        pygame.draw.rect(screen, self.BORDER_COLOR, (panel_x, panel_y, panel_w, panel_h), 2)
        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((*self.BG_COLOR, 230))
        screen.blit(bg, (panel_x, panel_y))

        # Title
        title = self.font_title.render("Gear (G or ESC to close)", True, (200, 200, 220))
        screen.blit(title, (panel_x + 10, panel_y + 8))

        # ── Equipped slots ──────────────────────────────────────────
        slot_y = panel_y + 40

        # Weapon slot
        self._render_equipped_slot(
            screen, "Weapon", player_gear.weapon, slot_y,
            "weapon", panel_x, panel_w,
        )
        self._weapon_rect = pygame.Rect(
            panel_x + 5, slot_y, panel_w - 10, self.SLOT_HEIGHT,
        )
        slot_y += self.SLOT_HEIGHT + 8

        # Armor slot
        self._render_equipped_slot(
            screen, "Armor", player_gear.armor, slot_y,
            "armor", panel_x, panel_w,
        )
        self._armor_rect = pygame.Rect(
            panel_x + 5, slot_y, panel_w - 10, self.SLOT_HEIGHT,
        )
        slot_y += self.SLOT_HEIGHT + 16

        # ── Available gear from inventory ───────────────────────────
        self._gear_items = []
        available_gear_y = slot_y

        header = self.font_label.render("Click item to equip:", True, (170, 170, 200))
        screen.blit(header, (panel_x + 10, available_gear_y))
        available_gear_y += 20

        # Collect gear items from inventory
        item_ids = self._get_equippable_items(inventory, gear_map)
        cols = 3
        cell_w = (panel_w - 20) // cols
        cell_h = 32

        for i, item_id in enumerate(item_ids):
            gear_item = gear_map[item_id]
            col = i % cols
            row = i // cols

            item_x = panel_x + 10 + col * cell_w
            item_y = available_gear_y + row * cell_h

            # Check if hovered
            rect = pygame.Rect(item_x, item_y, cell_w - 4, cell_h)
            is_hovered = self._hovered_item == item_id

            bg_color = self.ITEM_HOVER if is_hovered else self.ITEM_BG
            pygame.draw.rect(screen, bg_color, rect, border_radius=2)

            if item_id == (player_gear.weapon and player_gear.weapon.item_id):
                # Currently equipped as weapon — dim
                pygame.draw.rect(screen, (50, 50, 70), rect, border_radius=2)
            elif item_id == (player_gear.armor and player_gear.armor.item_id):
                pygame.draw.rect(screen, (50, 70, 50), rect, border_radius=2)

            label = self.font_stat.render(gear_item.name, True, (200, 200, 220))
            screen.blit(label, (item_x + 3, item_y + 3))

            bonus = self._get_equipped_bonus_text(gear_item)
            if bonus:
                bonus_surf = self.font_stat.render(bonus, True, (150, 200, 150))
                screen.blit(bonus_surf, (item_x + 3, item_y + 16))

            self._gear_items.append((item_id, gear_item, rect))

    def _render_equipped_slot(
        self,
        screen: pygame.Surface,
        label: str,
        gear_item: Optional["GearItem"],
        y: int,
        slot_type: str,
        panel_x: int,
        panel_w: int,
    ) -> None:
        """Render an equipped gear slot (with or without item)."""
        rect = pygame.Rect(panel_x + 5, y, panel_w - 10, self.SLOT_HEIGHT)
        bg_color = self.SLOT_BG if gear_item else self.SLOT_EMPTY_BG
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
            is_hover = self._hovered_item == f"unequip_{slot_type}"
            btn_color = self.BTN_HOVER if is_hover else self.BTN_COLOR
            pygame.draw.rect(screen, btn_color, (btn_x, rect.y + 18, btn_w, 20), border_radius=2)
            btn_surf = self.font_btn.render("Unequip", True, (240, 240, 255))
            screen.blit(btn_surf, (btn_x + 4, rect.y + 21))

            self._unequip_weapon_rect = (
                pygame.Rect(btn_x, rect.y + 18, btn_w, 20)
                if slot_type == "weapon"
                else None
            )
            self._unequip_armor_rect = (
                pygame.Rect(btn_x, rect.y + 18, btn_w, 20)
                if slot_type == "armor"
                else None
            )
            # Track unequip rects for keyboard navigation
            if slot_type == "weapon" and self._unequip_weapon_rect:
                self._unequip_rects.append(("weapon", self._unequip_weapon_rect))
            elif slot_type == "armor" and self._unequip_armor_rect:
                self._unequip_rects.append(("armor", self._unequip_armor_rect))
        else:
            empty_surf = self.font_stat.render("(empty)", True, (120, 120, 140))
            screen.blit(empty_surf, (rect.x + 6, rect.y + 18))

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
        """
        Return item_ids of gear items present in the player's inventory.
        """
        result = []
        for slot in inventory.slots:
            if slot is not None and slot.item_id and slot.quantity > 0:
                item_id = slot.item_id
                if item_id in gear_map and item_id not in result:
                    result.append(item_id)
        return result

    def handle_click(self, mx: int, my: int) -> Optional[str]:
        """
        Handle a click on the gear panel.

        Returns:
            Action string: "equip:<item_id>", "unequip:weapon", "unequip:armor", or None.
        """
        if not self.visible:
            return None

        # Check unequip weapon button
        if self._unequip_weapon_rect and self._unequip_weapon_rect.collidepoint(mx, my):
            return "unequip:weapon"

        # Check unequip armor button
        if self._unequip_armor_rect and self._unequip_armor_rect.collidepoint(mx, my):
            return "unequip:armor"

        # Check gear item clicks
        for item_id, gear_item, rect in self._gear_items:
            if rect.collidepoint(mx, my):
                return f"equip:{item_id}"

        return None

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Track hovered item for visual feedback and sync keyboard selection."""
        self._hovered_item = None
        # Build full item list: unequip slots first, then available items
        self._build_all_item_entries(mx, my)

    def _build_all_item_entries(self, mx: int, my: int) -> None:
        """
        Build a combined list of all interactive items for keyboard navigation.
        Also tracks hover state.
        """
        all_entries: List[tuple[str, str, pygame.Rect]] = []  # (action_prefix, item_id, rect)

        # Unequip weapon
        if self._unequip_weapon_rect:
            all_entries.append(("unequip", "weapon", self._unequip_weapon_rect))
        # Unequip armor
        if self._unequip_armor_rect:
            all_entries.append(("unequip", "armor", self._unequip_armor_rect))
        # Available gear items
        for item_id, gear_item, rect in self._gear_items:
            all_entries.append(("equip", item_id, rect))

        # Sync hover and selection
        self._hovered_item = None
        self._selected_gear_index = -1
        for i, (action_prefix, item_id, rect) in enumerate(all_entries):
            if rect.collidepoint(mx, my):
                self._hovered_item = item_id if action_prefix == "equip" else f"unequip_{item_id}"
                self._selected_gear_index = i
                return

    def handle_key(self, key: int) -> str | None:
        """
        Keyboard navigation for the gear panel.

        Arrow keys / WASD: navigate items and unequip buttons
        Enter: return "equip:<item_id>" or "unequip:weapon"/"unequip:armor"

        Returns None for navigation only; action string on Enter.
        """
        # Build combined list of all entries
        all_entries: List[tuple[str, str, pygame.Rect]] = []
        if self._unequip_weapon_rect:
            all_entries.append(("unequip", "weapon", self._unequip_weapon_rect))
        if self._unequip_armor_rect:
            all_entries.append(("unequip", "armor", self._unequip_armor_rect))
        for item_id, gear_item, rect in self._gear_items:
            all_entries.append(("equip", item_id, rect))

        if key in (pygame.K_w, pygame.K_UP):
            self._selected_gear_index = max(-1, self._selected_gear_index - 1)
        elif key in (pygame.K_s, pygame.K_DOWN):
            self._selected_gear_index = min(len(all_entries) - 1, self._selected_gear_index + 1)
        elif key in (pygame.K_a, pygame.K_LEFT):
            self._selected_gear_index = max(-1, self._selected_gear_index - 1)
        elif key in (pygame.K_d, pygame.K_RIGHT):
            self._selected_gear_index = min(len(all_entries) - 1, self._selected_gear_index + 1)
        elif key == pygame.K_RETURN:
            if 0 <= self._selected_gear_index < len(all_entries):
                action_prefix, item_id, _rect = all_entries[self._selected_gear_index]
                if action_prefix == "equip":
                    return f"equip:{item_id}"
                return f"unequip:{item_id}"
        return None
