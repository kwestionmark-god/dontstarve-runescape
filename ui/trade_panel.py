"""
trade_panel.py — Trade UI panel for player-merchant interactions (PanelWindow subclass).

Provides a full-featured panel for buying, selling, and bartering
with merchant NPCs. Delegates all transaction logic to TradeSystem
and does not duplicate business rules.
Subclasses PanelWindow for unified chrome, viewport clipping, scrollbar,
keyboard navigation with visible selection, and mouse-wheel scrolling.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING, List, Optional, Tuple

from ui.panel_window import PanelWindow

if TYPE_CHECKING:
    from npc.trade_system import TradeSystem, TradeSession
    from npc.npc_types import MerchantNPC
    from inventory.inventory import Inventory
    from core.player import Player


class TradePanel(PanelWindow):
    """
    Trade panel: Buy / Sell / Barter UI for merchant interactions.

    Layout:
    ┌────────────────────────────────────────────────────────────────────┐
    │  Trade with [Merchant Name]                              [X]       │
    ├────────────────────────────────────────────────────────────────────┤
    │  [Buy]  [Sell]  [Barter]                                         │
    ├────────────────────────────────────────────────────────────────────┤
    │  Merchant inventory (buy tab)   Player inventory (sell tab)       │
    │  [item] [price] [qty +/-] [Buy]  [item] [sell price] [Sell]      │
    │  ...                              ...                            │
    ├────────────────────────────────────────────────────────────────────┤
    │  Action area (tab-specific buttons)                               │
    ├────────────────────────────────────────────────────────────────────┤
    │  Status message                                                   │
    ├────────────────────────────────────────────────────────────────────┤
    │  Player Gold: XXX   Merchant Gold: XXX                            │
    └────────────────────────────────────────────────────────────────────┘

    Returns action tuples from handle_click:
        ("close",) — close trade panel
        ("buy", trade_item_id, quantity) — execute buy
        ("sell", item_id, quantity) — execute sell
        ("barter", player_item_id, player_qty, merchant_trade_item_id) — execute barter
    """

    # Panel geometry
    PANEL_WIDTH = 520
    PANEL_HEIGHT = 500

    # Content area
    CONTENT_Y = 95
    CONTENT_HEIGHT = 245
    ROW_HEIGHT = 24
    ROW_GAP = 2

    # Action area
    ACTION_Y = 345
    ACTION_HEIGHT = 75

    # Status bar
    STATUS_Y = 425
    STATUS_HEIGHT = 25

    # Gold display
    GOLD_Y = 455
    GOLD_HEIGHT = 25

    # Color palette (shared with base where possible)
    BG_COLOR = (30, 30, 40)
    BORDER_COLOR = (100, 100, 120)
    ROW_BG = (45, 45, 55)
    ROW_HIGHLIGHT = (65, 65, 85)
    TEXT_COLOR = (200, 200, 220)
    SUCCESS_COLOR = (100, 180, 100)
    ERROR_COLOR = (180, 100, 100)
    TAB_ACTIVE = (60, 80, 120)
    TAB_INACTIVE = (40, 40, 55)
    BUY_BTN = (80, 140, 80)
    SELL_BTN = (140, 100, 80)
    BARTER_BTN = (100, 80, 140)
    QTY_BTN = (70, 70, 90)
    QTY_BTN_HOVER = (90, 90, 110)

    def __init__(self) -> None:
        super().__init__(
            title="Trade",
            x=380,
            y=40,
            width=520,
            height=500,
            title_height=26,
            footer_height=25,
            has_scrollbar=True,
            show_close=True,
            selection_mode="list",
            row_gap=2,
        )
        self.visible: bool = False
        self.trade_system: "TradeSystem | None" = None
        self.inventory: "Inventory | None" = None
        self._trade_session: "TradeSession | None" = None
        self._tab: str = "buy"  # "buy" | "sell" | "barter"
        self._selected_merchant_idx: int = -1
        self._selected_player_idx: int = -1
        self._buy_quantity: int = 1
        self._sell_quantity: int = 1
        self._barter_player_qty: int = 1
        self._barter_merchant_idx: int = -1
        self._status_message: str = ""
        self._status_color: tuple[int, int, int] = (200, 200, 220)
        self._player_ref: "Player | None" = None
        self._hovered_btn: str = ""

        # Runtime rects for click handling
        self._merchant_rects: list[tuple[pygame.Rect, int]] = []
        self._player_rects: list[tuple[pygame.Rect, int]] = []
        self._button_rects: list[tuple[pygame.Rect, str]] = []
        self._tab_rects: list[tuple[pygame.Rect, str]] = []

        # Item name lookup cache
        self._item_names: dict[str, str] = {}
        self._load_item_names()

    # ── Wiring ────────────────────────────────────────────────────────

    def set_trade_system(self, ts: "TradeSystem") -> None:
        """Wire the TradeSystem reference."""
        self.trade_system = ts

    def set_inventory(self, inv: "Inventory") -> None:
        """Wire the Inventory reference."""
        self.inventory = inv

    # ── Session management ────────────────────────────────────────────

    def open_session(self, merchant: "MerchantNPC") -> bool:
        """
        Open a trade session with the given merchant.

        Args:
            merchant: The MerchantNPC to trade with.

        Returns:
            True if session opened successfully, False otherwise.
        """
        if self.trade_system is None:
            self._set_status("Trade system not available.", self.ERROR_COLOR)
            return False

        if self._player_ref is None:
            self._set_status("Cannot open session: player not available.", self.ERROR_COLOR)
            return False

        session = self.trade_system.open_trade(self._player_ref, merchant)
        if session is None:
            self._set_status("Cannot trade with this merchant.", self.ERROR_COLOR)
            return False

        self._trade_session = session
        self._tab = "buy"
        self._selected_merchant_idx = -1
        self._selected_player_idx = -1
        self._buy_quantity = 1
        self._sell_quantity = 1
        self._barter_player_qty = 1
        self._barter_merchant_idx = -1
        self._scroll_offset = 0
        self._status_message = ""
        self._merchant_rects = []
        self._player_rects = []
        self._button_rects = []
        self._tab_rects = []

        return True

    def close_session(self) -> None:
        """Close the current trade session and reset all state."""
        if self.trade_system is not None:
            self.trade_system.close_trade()
        self._trade_session = None
        self._reset_trade_state()
        self._status_message = ""

    def _reset_trade_state(self) -> None:
        """Clear selection and quantity state."""
        self._selected_merchant_idx = -1
        self._selected_player_idx = -1
        self._buy_quantity = 1
        self._sell_quantity = 1
        self._barter_player_qty = 1
        self._barter_merchant_idx = -1
        self._scroll_offset = 0
        self._merchant_rects = []
        self._player_rects = []
        self._button_rects = []
        self._tab_rects = []

    # ── PanelWindow hooks ──────────────────────────────────────────────

    def scroll_viewport(self):
        """Return (visible_px, total_px) for scrollbar sizing."""
        visible = max(1, self.content_rect.height)
        total = max(visible, self._content_total_px)
        return visible, total

    def select_count(self) -> int:
        """Number of selectable items (depends on active tab)."""
        if self._trade_session is None or self.trade_system is None:
            return 0
        if self._tab == "buy":
            items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
            return len(items)
        elif self._tab == "sell":
            return len(self._collect_sellable_items())
        elif self._tab == "barter":
            # In barter, we select from merchant items on the right
            if self._trade_session is None:
                return 0
            items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
            return len(items)
        return 0

    def on_select(self, index: int) -> None:
        """Highlight the selected item."""
        pass

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw trade panel content inside the clipped viewport."""
        self._interactive_rects.clear()
        self._merchant_rects.clear()
        self._player_rects.clear()
        self._button_rects.clear()
        self._tab_rects.clear()

        if self._trade_session is None or self.trade_system is None:
            self._render_not_connected(screen, content_rect)
            self._content_total_px = 0
            return

        panel_x = content_rect.x
        panel_y = content_rect.y - self._scroll_offset  # Adjust for scroll
        content_x = panel_x + 5
        content_w = 200
        content_y = self.CONTENT_Y

        # Title
        merchant = self._trade_session
        title_text = f"Trade with {merchant.name}"
        title_surf = self.font_bold.render(title_text, True, self.TEXT_COLOR)
        screen.blit(title_surf, (panel_x + 10, self.PANEL_Y + 5))

        # Tabs
        tabs = [("Buy", "buy"), ("Sell", "sell"), ("Barter", "barter")]
        tab_positions = {
            "buy": content_x + 205,
            "sell": content_x + 205 + 65 + 5,
            "barter": content_x + 205 + 65 + 5 + 65 + 5,
        }
        for label, tab_id in tabs:
            x = tab_positions[tab_id]
            is_active = self._tab == tab_id
            tab_color = self.TAB_ACTIVE if is_active else self.TAB_INACTIVE
            tab_rect = pygame.Rect(x, self.TAB_Y, self.TAB_WIDTH, self.TAB_HEIGHT)
            pygame.draw.rect(screen, tab_color, tab_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, tab_rect, 1)
            label_surf = self.font_small.render(label, True, self.TEXT_COLOR)
            lx = x + (self.TAB_WIDTH - label_surf.get_width()) // 2
            ly = self.TAB_Y + (self.TAB_HEIGHT - label_surf.get_height()) // 2
            screen.blit(label_surf, (lx, ly))
            self._tab_rects.append((tab_rect, tab_id))
            self._interactive_rects.append((tab_rect, f"tab:{tab_id}"))

        # Gold display
        self._render_gold_display(screen)

        # Render active tab content
        if self._tab == "buy":
            self._render_buy_tab(screen, content_x, content_w, content_y)
        elif self._tab == "sell":
            self._render_sell_tab(screen, content_x, content_w, content_y)
        elif self._tab == "barter":
            self._render_barter_tab(screen)

        # Action area
        self._render_action_area(screen, content_rect)

        # Status bar
        self._render_status_bar(screen, content_rect)

        # Footer hint
        hint = self.font_small.render("Press ESC to close", True, (150, 150, 170))
        hint_x = content_rect.x + (content_rect.width - hint.get_width()) // 2
        hint_y = content_rect.y + content_rect.height - 20
        screen.blit(hint, (hint_x, hint_y))

        self._content_total_px = content_rect.height + 50  # Approximate

    def _render_gold_display(self, screen: pygame.Surface) -> None:
        """Render player and merchant gold display."""
        if self._player_ref is None or self._trade_session is None:
            return

        player_gold = self._player_ref.inventory.gold if self._player_ref.inventory else 0
        merchant_gold = self._trade_session.gold

        player_text = f"Player Gold: {player_gold}"
        merchant_text = f"Merchant Gold: {merchant_gold}"

        player_surf = self.font_normal.render(player_text, True, (255, 220, 100))
        merchant_surf = self.font_normal.render(merchant_text, True, (255, 220, 100))

        screen.blit(player_surf, (self.PANEL_X + 10, self.GOLD_Y))
        screen.blit(merchant_surf, (self.PANEL_X + 250, self.GOLD_Y))

    def _render_buy_tab(self, screen: pygame.Surface, content_x: int, content_w: int, content_y: int) -> None:
        """Render the buy tab showing merchant inventory."""
        merchant = self._trade_session
        items = self.trade_system.get_trade_items_for_merchant(merchant)
        if not items:
            return

        max_rows = 9
        visible_items = items[self._scroll_offset:self._scroll_offset + max_rows]

        # Draw content area background
        pygame.draw.rect(
            screen, (35, 35, 45),
            (content_x, content_y, content_w, self.CONTENT_HEIGHT),
        )

        for i, item in enumerate(visible_items):
            row_idx = self._scroll_offset + i
            row_y = content_y + i * (self.ROW_HEIGHT + self.ROW_GAP)
            is_selected = row_idx == self._selected_merchant_idx

            row_color = self.ROW_HIGHLIGHT if is_selected else self.ROW_BG
            pygame.draw.rect(
                screen, row_color,
                (content_x, row_y, content_w, self.ROW_HEIGHT),
            )

            # Item name (left)
            item_name = self._get_item_name(item.item_id)
            name_surf = self.font_normal.render(item_name, True, self.TEXT_COLOR)
            screen.blit(name_surf, (content_x + 4, row_y + 4))

            # Buy price + stock (center)
            price_text = f"{item.buy_price}g [{item.stock_quantity}]"
            price_surf = self.font_small.render(price_text, True, (180, 180, 200))
            screen.blit(price_surf, (content_x + 60, row_y + 4))

            # Quantity controls
            btn_w = 12
            btn_h = self.ROW_HEIGHT - 4
            qty_y = row_y + 2

            minus_rect = pygame.Rect(content_x + 140, qty_y, btn_w, btn_h)
            minus_color = self.QTY_BTN_HOVER if self._hovered_btn == f"minus_buy_{row_idx}" else self.QTY_BTN
            pygame.draw.rect(screen, minus_color, minus_rect)
            minus_text = self.font_small.render("-", True, (255, 255, 255))
            mx = content_x + 140 + (btn_w - minus_text.get_width()) // 2
            my = qty_y + (btn_h - minus_text.get_height()) // 2
            screen.blit(minus_text, (mx, my))

            qty_text = str(max(1, self._buy_quantity))
            qty_surf = self.font_small.render(qty_text, True, (255, 255, 150))
            screen.blit(qty_surf, (content_x + 155, row_y + 4))

            plus_rect = pygame.Rect(content_x + 175, qty_y, btn_w, btn_h)
            plus_color = self.QTY_BTN_HOVER if self._hovered_btn == f"plus_buy_{row_idx}" else self.QTY_BTN
            pygame.draw.rect(screen, plus_color, plus_rect)
            plus_text = self.font_small.render("+", True, (255, 255, 255))
            px = content_x + 175 + (btn_w - plus_text.get_width()) // 2
            py = qty_y + (btn_h - plus_text.get_height()) // 2
            screen.blit(plus_text, (px, py))

            # Buy button
            buy_btn_w = 40
            buy_rect = pygame.Rect(content_x + content_w - buy_btn_w - 4, qty_y, buy_btn_w, btn_h)
            pygame.draw.rect(screen, self.BUY_BTN, buy_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, buy_rect, 1)
            buy_text = self.font_small.render("Buy", True, (255, 255, 255))
            bx = content_x + content_w - buy_btn_w - 4 + (buy_btn_w - buy_text.get_width()) // 2
            by = qty_y + (btn_h - buy_text.get_height()) // 2
            screen.blit(buy_text, (bx, by))

            # Store rects for click detection
            self._merchant_rects.append((minus_rect, row_idx))
            self._merchant_rects.append((plus_rect, row_idx))
            self._button_rects.append((buy_rect, f"buy_{row_idx}"))
            self._interactive_rects.append((minus_rect, f"minus_buy_{row_idx}"))
            self._interactive_rects.append((plus_rect, f"plus_buy_{row_idx}"))
            self._interactive_rects.append((buy_rect, f"buy_action_{row_idx}"))

    def _render_sell_tab(self, screen: pygame.Surface, content_x: int, content_w: int, content_y: int) -> None:
        """Render the sell tab showing player inventory items."""
        if self.inventory is None or self.trade_system is None:
            return

        max_rows = 9

        pygame.draw.rect(
            screen, (35, 35, 45),
            (content_x, content_y, content_w, self.CONTENT_HEIGHT),
        )

        sellable_items = self._collect_sellable_items()
        visible_items = sellable_items[self._scroll_offset:self._scroll_offset + max_rows]

        for i, (slot_idx, item_id, quantity, sell_price) in enumerate(visible_items):
            row_idx = self._scroll_offset + i
            row_y = content_y + i * (self.ROW_HEIGHT + self.ROW_GAP)
            is_selected = row_idx == self._selected_player_idx

            row_color = self.ROW_HIGHLIGHT if is_selected else self.ROW_BG
            pygame.draw.rect(
                screen, row_color,
                (content_x, row_y, content_w, self.ROW_HEIGHT),
            )

            item_name = self._get_item_name(item_id)
            name_surf = self.font_normal.render(item_name, True, self.TEXT_COLOR)
            screen.blit(name_surf, (content_x + 4, row_y + 4))

            price_text = f"{sell_price}g [{quantity}]"
            price_surf = self.font_small.render(price_text, True, (180, 180, 200))
            screen.blit(price_surf, (content_x + 80, row_y + 4))

            qty_text = str(max(1, self._sell_quantity))
            qty_surf = self.font_small.render(qty_text, True, (255, 255, 150))
            screen.blit(qty_surf, (content_x + 145, row_y + 4))

            sell_btn_w = 40
            sell_rect = pygame.Rect(content_x + content_w - sell_btn_w - 4, row_y + 2, sell_btn_w, self.ROW_HEIGHT - 4)
            pygame.draw.rect(screen, self.SELL_BTN, sell_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, sell_rect, 1)
            sell_text = self.font_small.render("Sell", True, (255, 255, 255))
            sx = content_x + content_w - sell_btn_w - 4 + (sell_btn_w - sell_text.get_width()) // 2
            sy = row_y + 2 + (self.ROW_HEIGHT - 4 - sell_text.get_height()) // 2
            screen.blit(sell_text, (sx, sy))

            self._player_rects.append((sell_rect, row_idx))
            self._button_rects.append((sell_rect, f"sell_{row_idx}"))
            self._interactive_rects.append((sell_rect, f"sell_action_{row_idx}"))

    def _render_barter_tab(self, screen: pygame.Surface) -> None:
        """Render the barter tab with player offering and merchant receiving sections."""
        if self.inventory is None or self.trade_system is None:
            return

        merchant = self._trade_session
        if merchant is None:
            return

        items = self.trade_system.get_trade_items_for_merchant(merchant)

        panel_x = self.PANEL_X
        content_y = self.CONTENT_Y

        # ── Player items (offering) — left side ──
        left_x = panel_x + 5
        left_w = 245
        left_h = self.CONTENT_HEIGHT

        pygame.draw.rect(screen, (35, 35, 45), (left_x, content_y, left_w, left_h))

        header_surf = self.font_bold.render("Your Offer", True, (180, 160, 120))
        screen.blit(header_surf, (left_x + 4, content_y + 2))

        snapshot = self.inventory.get_snapshot()
        player_items = []
        for slot_idx, slot_data in enumerate(snapshot):
            if slot_data is None:
                continue
            item_id = slot_data.get("item_id", "")
            quantity = slot_data.get("quantity", 0)
            if item_id and quantity > 0:
                trade_item = self.trade_system._find_trade_item_by_item_id(item_id)
                if trade_item is not None:
                    player_items.append((slot_idx, item_id, quantity, trade_item.sell_price))

        max_rows = 8
        visible_player = player_items[self._scroll_offset:self._scroll_offset + max_rows]

        for i, (slot_idx, item_id, quantity, sell_price) in enumerate(visible_player):
            row_y = content_y + 18 + i * (self.ROW_HEIGHT + self.ROW_GAP)

            row_color = self.ROW_BG
            pygame.draw.rect(
                screen, row_color,
                (left_x + 2, row_y, left_w - 4, self.ROW_HEIGHT),
            )

            item_name = self._get_item_name(item_id)
            name_surf = self.font_normal.render(item_name, True, self.TEXT_COLOR)
            screen.blit(name_surf, (left_x + 4, row_y + 4))

            value_text = f"{sell_price}g [{quantity}]"
            value_surf = self.font_small.render(value_text, True, (180, 180, 200))
            screen.blit(value_surf, (left_x + 100, row_y + 4))

            btn_w = 12
            btn_h = self.ROW_HEIGHT - 4
            qty_y = row_y + 2

            minus_rect = pygame.Rect(left_x + 155, qty_y, btn_w, btn_h)
            minus_color = self.QTY_BTN_HOVER if self._hovered_btn == f"minus_barter_{slot_idx}" else self.QTY_BTN
            pygame.draw.rect(screen, minus_color, minus_rect)
            minus_text = self.font_small.render("-", True, (255, 255, 255))
            mx = left_x + 155 + (btn_w - minus_text.get_width()) // 2
            my = qty_y + (btn_h - minus_text.get_height()) // 2
            screen.blit(minus_text, (mx, my))

            qty_text = str(max(1, self._barter_player_qty))
            qty_surf = self.font_small.render(qty_text, True, (255, 255, 150))
            screen.blit(qty_surf, (left_x + 170, row_y + 4))

            plus_rect = pygame.Rect(left_x + 190, qty_y, btn_w, btn_h)
            plus_color = self.QTY_BTN_HOVER if self._hovered_btn == f"plus_barter_{slot_idx}" else self.QTY_BTN
            pygame.draw.rect(screen, plus_color, plus_rect)
            plus_text = self.font_small.render("+", True, (255, 255, 255))
            px = left_x + 190 + (btn_w - plus_text.get_width()) // 2
            py = qty_y + (btn_h - plus_text.get_height()) // 2
            screen.blit(plus_text, (px, py))

            if slot_idx == self._barter_merchant_idx:
                pygame.draw.rect(screen, (80, 100, 80), (left_x + 2, row_y, left_w - 4, self.ROW_HEIGHT), 1)

            self._player_rects.append((minus_rect, slot_idx))
            self._player_rects.append((plus_rect, slot_idx))
            self._interactive_rects.append((minus_rect, f"minus_barter_{slot_idx}"))
            self._interactive_rects.append((plus_rect, f"plus_barter_{slot_idx}"))

        # ── Merchant items (receiving) — right side ──
        right_x = panel_x + 260
        right_w = 245

        pygame.draw.rect(screen, (35, 35, 45), (right_x, content_y, right_w, left_h))

        header_surf = self.font_bold.render("Receive", True, (180, 160, 120))
        screen.blit(header_surf, (right_x + 4, content_y + 2))

        max_rows = 8
        visible_merchant = items[self._scroll_offset:self._scroll_offset + max_rows]

        for i, item in enumerate(visible_merchant):
            row_y = content_y + 18 + i * (self.ROW_HEIGHT + self.ROW_GAP)
            is_selected = i == self._barter_merchant_idx

            row_color = self.ROW_HIGHLIGHT if is_selected else self.ROW_BG
            pygame.draw.rect(
                screen, row_color,
                (right_x + 2, row_y, right_w - 4, self.ROW_HEIGHT),
            )

            item_name = self._get_item_name(item.item_id)
            name_surf = self.font_normal.render(item_name, True, self.TEXT_COLOR)
            screen.blit(name_surf, (right_x + 4, row_y + 4))

            stock_text = f"{item.buy_price}g [{item.stock_quantity}]"
            stock_surf = self.font_small.render(stock_text, True, (180, 180, 200))
            screen.blit(stock_surf, (right_x + 100, row_y + 4))

            click_rect = pygame.Rect(right_x + 2, row_y, right_w - 4, self.ROW_HEIGHT)
            self._merchant_rects.append((click_rect, i))
            self._interactive_rects.append((click_rect, f"barter_select_{i}"))

    def _render_action_area(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Render tab-specific action buttons."""
        panel_x = self.PANEL_X
        action_y = self.ACTION_Y
        action_w = self.PANEL_WIDTH - 10

        if self._tab == "buy" and self._selected_merchant_idx >= 0 and self._trade_session is not None:
            btn_w = 100
            btn_h = 28
            btn_x = panel_x + (action_w - btn_w) // 2
            btn_rect = pygame.Rect(btn_x, action_y, btn_w, btn_h)
            pygame.draw.rect(screen, self.BUY_BTN, btn_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
            btn_text = self.font_bold.render("Buy", True, (255, 255, 255))
            tx = btn_x + (btn_w - btn_text.get_width()) // 2
            ty = action_y + (btn_h - btn_text.get_height()) // 2
            screen.blit(btn_text, (tx, ty))
            self._button_rects.append((btn_rect, "buy_action"))
            self._interactive_rects.append((btn_rect, "buy_action"))

        elif self._tab == "sell" and self._selected_player_idx >= 0:
            btn_w = 100
            btn_h = 28
            btn_x = panel_x + (action_w - btn_w) // 2
            btn_rect = pygame.Rect(btn_x, action_y, btn_w, btn_h)
            pygame.draw.rect(screen, self.SELL_BTN, btn_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
            btn_text = self.font_bold.render("Sell", True, (255, 255, 255))
            tx = btn_x + (btn_w - btn_text.get_width()) // 2
            ty = action_y + (btn_h - btn_text.get_height()) // 2
            screen.blit(btn_text, (tx, ty))
            self._button_rects.append((btn_rect, "sell_action"))
            self._interactive_rects.append((btn_rect, "sell_action"))

        elif self._tab == "barter":
            has_selection = self._selected_player_idx >= 0 and self._selected_merchant_idx >= -1
            barter_ready = False

            if self.inventory is not None:
                player_ready = False
                snapshot = self.inventory.get_snapshot()
                for slot_idx in range(len(snapshot)):
                    if slot_idx == self._selected_player_idx and snapshot[slot_idx] is not None:
                        player_ready = True
                        break

                if self._trade_session is not None and self.trade_system is not None:
                    items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
                    if 0 <= self._selected_merchant_idx < len(items):
                        barter_ready = player_ready

            btn_w = 120
            btn_h = 28
            btn_x = panel_x + (action_w - btn_w) // 2
            btn_color = self.BARTER_BTN if barter_ready else (50, 40, 60)
            btn_rect = pygame.Rect(btn_x, action_y, btn_w, btn_h)
            pygame.draw.rect(screen, btn_color, btn_rect)
            pygame.draw.rect(screen, self.BORDER_COLOR, btn_rect, 1)
            btn_text = self.font_bold.render("Barter", True, (255, 255, 255) if barter_ready else (120, 120, 140))
            tx = btn_x + (btn_w - btn_text.get_width()) // 2
            ty = action_y + (btn_h - btn_text.get_height()) // 2
            screen.blit(btn_text, (tx, ty))
            self._button_rects.append((btn_rect, "barter_action"))
            self._interactive_rects.append((btn_rect, "barter_action"))

    def _render_status_bar(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Render the status message bar."""
        panel_x = self.PANEL_X
        status_y = self.STATUS_Y
        status_w = self.PANEL_WIDTH - 10

        pygame.draw.rect(screen, (35, 35, 45), (panel_x + 5, status_y, status_w, self.STATUS_HEIGHT))

        if self._status_message:
            status_surf = self.font_normal.render(self._status_message, True, self._status_color)
            sx = panel_x + 10
            sy = status_y + (self.STATUS_HEIGHT - status_surf.get_height()) // 2
            screen.blit(status_surf, (sx, sy))

    def _render_not_connected(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Render fallback message when no trade session is active."""
        msg = self.font_normal.render("Not connected to a merchant.", True, (180, 180, 200))
        mx = content_rect.x + (content_rect.width - msg.get_width()) // 2
        my = content_rect.y + (content_rect.height - msg.get_height()) // 2
        screen.blit(msg, (mx, my))

        hint = self.font_small.render("Stand near a merchant and press E to trade.", True, (150, 150, 170))
        hx = content_rect.x + (content_rect.width - hint.get_width()) // 2
        hy = my + msg.get_height() + 15
        screen.blit(hint, (hx, hy))

    # ── Input handling ────────────────────────────────────────────────

    def on_key(self, key: int) -> tuple[str, ...] | None:
        """
        Keyboard navigation for the trade panel.

        Tab / Left / Right: switch tabs
        Arrow keys / WASD: navigate trade rows
        Enter: return ("buy", item_id, qty) or ("sell", item_id, qty)
        +/- keys: adjust quantity

        Returns None for navigation only; action tuple on Enter.
        """
        if self._trade_session is None or self.trade_system is None:
            return None

        tabs = ["buy", "sell", "barter"]
        current_idx = tabs.index(self._tab)

        # Tab switching
        if key == pygame.K_TAB:
            new_idx = (current_idx + 1) % len(tabs)
            self._tab = tabs[new_idx]
            self._scroll_offset = 0
            self._selected_merchant_idx = -1
            self._selected_player_idx = -1
            self._barter_merchant_idx = -1
            return None
        elif key == pygame.K_LEFT and current_idx > 0:
            self._tab = tabs[current_idx - 1]
            self._scroll_offset = 0
            self._selected_merchant_idx = -1
            self._selected_player_idx = -1
            self._barter_merchant_idx = -1
            return None
        elif key == pygame.K_RIGHT and current_idx < len(tabs) - 1:
            self._tab = tabs[current_idx + 1]
            self._scroll_offset = 0
            self._selected_merchant_idx = -1
            self._selected_player_idx = -1
            self._barter_merchant_idx = -1
            return None

        # Quantity adjustment
        if self._tab == "buy" and key in (pygame.K_PLUS, pygame.K_KP_PLUS):
            items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
            if 0 <= self._selected_merchant_idx < len(items):
                self._buy_quantity = min(items[self._selected_merchant_idx].stock_quantity, self._buy_quantity + 1)
                return None
        elif self._tab == "buy" and key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._buy_quantity = max(1, self._buy_quantity - 1)
            return None
        elif self._tab == "sell" and key in (pygame.K_PLUS, pygame.K_KP_PLUS):
            self._sell_quantity = min(99, self._sell_quantity + 1)
            return None
        elif self._tab == "sell" and key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._sell_quantity = max(1, self._sell_quantity - 1)
            return None

        # Row navigation and Enter
        if self._tab == "buy":
            items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
            if key in (pygame.K_w, pygame.K_UP):
                self.select(max(-1, self._selected_index - 1))
                self._selected_merchant_idx = self._selected_index
                return None
            elif key in (pygame.K_s, pygame.K_DOWN):
                self.select(min(len(items) - 1, self._selected_index + 1))
                self._selected_merchant_idx = self._selected_index
                return None
            elif key == pygame.K_RETURN:
                if 0 <= self._selected_merchant_idx < len(items):
                    item = items[self._selected_merchant_idx]
                    return ("buy", item.trade_item_id, self._buy_quantity)

        elif self._tab == "sell":
            sellable_items = self._collect_sellable_items()
            if key in (pygame.K_w, pygame.K_UP):
                self.select(max(-1, self._selected_index - 1))
                self._selected_player_idx = self._selected_index
                return None
            elif key in (pygame.K_s, pygame.K_DOWN):
                self.select(min(len(sellable_items) - 1, self._selected_index + 1))
                self._selected_player_idx = self._selected_index
                return None
            elif key == pygame.K_RETURN:
                if 0 <= self._selected_player_idx < len(sellable_items):
                    _, item_id, _, _ = sellable_items[self._selected_player_idx]
                    return ("sell", item_id, self._sell_quantity)

        return None

    def on_click(self, x: int, y: int, button: int = 1) -> tuple[str, ...] | None:
        """
        Handle a mouse click on the trade panel.

        Routes clicks to the appropriate action based on which rect was hit.
        """
        # Check close button first
        close_rect = pygame.Rect(
            self.CLOSE_X, self.CLOSE_Y,
            self.CLOSE_SIZE, self.CLOSE_SIZE,
        )
        if close_rect.collidepoint(x, y):
            return ("close",)

        # Check tab clicks
        for tab_rect, tab_id in self._tab_rects:
            if tab_rect.collidepoint(x, y):
                self._tab = tab_id
                self._scroll_offset = 0
                self._selected_merchant_idx = -1
                self._selected_player_idx = -1
                self._barter_merchant_idx = -1
                self._set_status("")
                return None

        # Check action buttons
        for btn_rect, action_id in self._button_rects:
            if btn_rect.collidepoint(x, y):
                return self._resolve_action(action_id)

        # Check merchant inventory clicks (buy tab)
        if self._tab == "buy":
            for rect, row_idx in self._merchant_rects:
                if rect.collidepoint(x, y):
                    return self._resolve_merchant_click(row_idx, x, y)

        # Check player inventory clicks (sell tab)
        if self._tab == "sell":
            for rect, row_idx in self._player_rects:
                if rect.collidepoint(x, y):
                    return self._resolve_player_click(row_idx, x, y)

        # Check barter tab clicks
        if self._tab == "barter":
            for rect, slot_idx in self._player_rects:
                if rect.collidepoint(x, y):
                    return self._resolve_barter_player_click(slot_idx, x, y)

            for rect, merchant_idx in self._merchant_rects:
                if rect.collidepoint(x, y):
                    self._selected_merchant_idx = merchant_idx
                    self._set_status(f"Selected to receive: {self._get_item_name(self._get_merchant_item_id(merchant_idx))}")
                    return None

        return None

    def _resolve_action(self, action_id: str) -> tuple[str, ...] | None:
        """Resolve an action button ID into a trade action tuple."""
        if action_id == "close":
            return ("close",)

        elif action_id == "buy_action":
            if self._selected_merchant_idx < 0 or self._trade_session is None:
                return None
            items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
            if 0 <= self._selected_merchant_idx < len(items):
                item = items[self._selected_merchant_idx]
                return ("buy", item.trade_item_id, self._buy_quantity)

        elif action_id == "sell_action":
            if self._selected_player_idx < 0 or self.inventory is None or self.trade_system is None:
                return None
            sellable_items = self._collect_sellable_items()
            if 0 <= self._selected_player_idx < len(sellable_items):
                slot_idx, item_id, quantity, sell_price = sellable_items[self._selected_player_idx]
                return ("sell", item_id, self._sell_quantity)

        elif action_id == "barter_action":
            if self.inventory is None or self._trade_session is None or self.trade_system is None:
                return None
            player_items = self._collect_sellable_items()
            if 0 <= self._selected_player_idx < len(player_items):
                slot_idx, player_item_id, player_qty, sell_price = player_items[self._selected_player_idx]
                items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
                if 0 <= self._selected_merchant_idx < len(items):
                    merchant_item = items[self._selected_merchant_idx]
                    return ("barter", player_item_id, self._barter_player_qty, merchant_item.trade_item_id)

        return None

    def _resolve_merchant_click(self, row_idx: int, x: int, y: int) -> tuple[str, ...] | None:
        """Resolve a click on a merchant inventory row (buy tab)."""
        if self._trade_session is None:
            return None
        items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
        if row_idx < 0 or row_idx >= len(items):
            return None

        item = items[row_idx]
        content_x = self.PANEL_X + 5

        if content_x + 140 <= x <= content_x + 152:
            self._buy_quantity = max(1, self._buy_quantity - 1)
            return None

        if content_x + 175 <= x <= content_x + 187:
            max_stock = item.stock_quantity
            self._buy_quantity = min(max_stock, self._buy_quantity + 1)
            return None

        buy_btn_w = 40
        buy_btn_x = content_x + 200 - buy_btn_w - 4
        if buy_btn_x <= x <= buy_btn_x + buy_btn_w:
            return ("buy", item.trade_item_id, self._buy_quantity)

        self._selected_merchant_idx = row_idx
        self._buy_quantity = min(item.stock_quantity, 1)
        self._set_status(f"Selected: {self._get_item_name(item.item_id)} — {item.buy_price}g each")
        return None

    def _resolve_player_click(self, row_idx: int, x: int, y: int) -> tuple[str, ...] | None:
        """Resolve a click on a player inventory row (sell tab)."""
        sellable_items = self._collect_sellable_items()
        if row_idx < 0 or row_idx >= len(sellable_items):
            return None

        slot_idx, item_id, quantity, sell_price = sellable_items[row_idx]
        content_x = self.PANEL_X + 5
        sell_btn_w = 40
        sell_btn_x = content_x + 200 - sell_btn_w - 4
        if sell_btn_x <= x <= sell_btn_x + sell_btn_w:
            return ("sell", item_id, self._sell_quantity)

        self._selected_player_idx = row_idx
        self._sell_quantity = min(quantity, 1)
        self._set_status(f"Selected: {self._get_item_name(item_id)} — sell for {sell_price}g each")
        return None

    def _resolve_barter_player_click(self, slot_idx: int, x: int, y: int) -> tuple[str, ...] | None:
        """Resolve a click on a player item in barter tab."""
        if self.inventory is None:
            return None
        snapshot = self.inventory.get_snapshot()
        if slot_idx < 0 or slot_idx >= len(snapshot):
            return None

        slot_data = snapshot[slot_idx]
        if slot_data is None:
            return None

        item_id = slot_data.get("item_id", "")
        quantity = slot_data.get("quantity", 0)
        if not item_id or quantity <= 0:
            return None

        content_x = self.PANEL_X + 5

        if content_x + 155 <= x <= content_x + 167:
            self._barter_player_qty = max(1, self._barter_player_qty - 1)
            return None

        if content_x + 190 <= x <= content_x + 202:
            self._barter_player_qty = min(quantity, self._barter_player_qty + 1)
            return None

        self._selected_player_idx = slot_idx
        self._barter_player_qty = min(quantity, 1)
        self._set_status(f"Offering: {self._get_item_name(item_id)} x{self._barter_player_qty}")
        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Track hovered button for visual feedback and sync keyboard selection."""
        self._hovered_btn = ""

        # Check tab buttons
        for tab_rect, tab_id in self._tab_rects:
            if tab_rect.collidepoint(mx, my):
                self._hovered_btn = f"tab_{tab_id}"
                return

        # Check interactive rects
        for i, (rect, payload) in enumerate(self._interactive_rects):
            if rect.collidepoint(mx, my):
                self._hovered_btn = payload
                self.select(i)
                return
        self.select(-1)

    # ── Helpers ───────────────────────────────────────────────────────

    def _collect_sellable_items(self) -> list[tuple[int, str, int, int]]:
        """Collect sellable items from player inventory."""
        if self.inventory is None or self.trade_system is None:
            return []

        snapshot = self.inventory.get_snapshot()
        items = []
        for slot_idx, slot_data in enumerate(snapshot):
            if slot_data is None:
                continue
            item_id = slot_data.get("item_id", "")
            quantity = slot_data.get("quantity", 0)
            if item_id and quantity > 0:
                trade_item = self.trade_system._find_trade_item_by_item_id(item_id)
                if trade_item is not None:
                    items.append((slot_idx, item_id, quantity, trade_item.sell_price))
        return items

    def _get_merchant_item_id(self, merchant_idx: int) -> str:
        """Get the item_id for a merchant inventory entry by index."""
        if self._trade_session is None or self.trade_system is None:
            return ""
        items = self.trade_system.get_trade_items_for_merchant(self._trade_session)
        if 0 <= merchant_idx < len(items):
            return items[merchant_idx].item_id
        return ""

    def _load_item_names(self) -> None:
        """Load item name mappings from items.json."""
        import json
        import os
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        filepath = os.path.join(data_dir, "items.json")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            for item in data.get("items", []):
                item_id = item.get("id", "")
                name = item.get("name", item_id)
                if item_id:
                    self._item_names[item_id] = name
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _get_item_name(self, item_id: str) -> str:
        """Get the display name for an item ID, falling back to item_id."""
        return self._item_names.get(item_id, item_id)

    def _set_status(self, message: str, color: tuple[int, int, int] | None = None) -> None:
        """Set the status bar message and color."""
        self._status_message = message
        if color is not None:
            self._status_color = color

    # ── Compatibility methods (for game.py) ────────────────────────────

    def render(self, screen: pygame.Surface) -> None:
        """Render the trade panel (compatibility wrapper)."""
        super().render(screen)

    def handle_mouse_move(self, mx: int, my: int) -> None:
        """Track hovered button for visual feedback."""
        self.on_mouse_move(mx, my)

    def handle_click(self, x: int, y: int) -> tuple[str, ...] | None:
        """Handle a click on the trade panel (compatibility wrapper)."""
        return self.on_click(x, y)

    def handle_key(self, key: int) -> tuple[str, ...] | None:
        """Keyboard navigation (compatibility wrapper)."""
        return self.on_key(key)