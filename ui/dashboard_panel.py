"""dashboard_panel.py — Unified tabbed menu ("dashboard").

One fixed-size window hosting the character-menu panels (inventory, skills,
crafting, building, gear) as tabs. The hosted panels are the SAME instances
the Game already owns — the dashboard repositions them into the shared rect
and delegates input/rendering to the active tab, so all panel state (scroll
position, selection, sessions) survives tab switches.

Keys: LEFT/RIGHT (or A/D) cycle tabs; tab-specific keys are forwarded to the
active child. The router owns open/close (each panel key opens its tab;
pressing it again or ESC closes).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import pygame

from ui.panel_window import PanelWindow
from render.font_cache import get_font

# Canonical dashboard geometry (fixed, generous); positioned by center().
DASHBOARD_WIDTH = 880
DASHBOARD_HEIGHT = 560

# Tab order is also the LEFT/RIGHT cycle order.
TAB_ORDER: List[str] = ["inventory", "skills", "crafting", "building", "gear"]

TAB_LABELS: Dict[str, str] = {
    "inventory": "Inventory",
    "skills": "Skills",
    "crafting": "Crafting",
    "building": "Building",
    "gear": "Gear",
}

# dispatch_click panel names per tab (used by the router).
TAB_DISPATCH_NAMES: Dict[str, str] = {
    "inventory": "inventory",
    "skills": "skill",
    "crafting": "crafting",
    "building": "building",
    "gear": "gear",
}

TAB_HEIGHT = 26


class DashboardPanel(PanelWindow):
    """One window, five tabs. Holds references; does not own panel state."""

    def __init__(self) -> None:
        super().__init__(
            title="", x=0, y=0, width=DASHBOARD_WIDTH, height=DASHBOARD_HEIGHT,
            title_height=0, show_close=False, has_scrollbar=False,
        )
        self.active_tab: str = "inventory"
        # tab_id -> (child panel, render callable)
        self._tabs: Dict[str, Tuple["PanelWindow", Callable]] = {}
        self._tab_rects: List[Tuple[str, pygame.Rect]] = []

    # ── Wiring ───────────────────────────────────────────────────────────

    def register_tab(
        self, tab_id: str, panel: "PanelWindow", render_fn: Callable,
    ) -> None:
        """Attach an existing panel + its render callable to a tab."""
        self._tabs[tab_id] = (panel, render_fn)
        self._layout_tabs()
        self._position_child(tab_id)

    def center(self, screen_w: int, screen_h: int) -> None:
        """Center the dashboard (and all children) on the screen."""
        self.reposition(
            (screen_w - DASHBOARD_WIDTH) // 2,
            (screen_h - DASHBOARD_HEIGHT) // 2,
            DASHBOARD_WIDTH, DASHBOARD_HEIGHT,
        )
        self._layout_tabs()
        for tab_id in list(self._tabs):
            self._position_child(tab_id)

    def _layout_tabs(self) -> None:
        """Compute tab button rects across the top of the window."""
        self._tab_rects.clear()
        if not self._tabs:
            return
        count = len(TAB_ORDER)
        tab_w = self.width // count
        for i, tab_id in enumerate(TAB_ORDER):
            self._tab_rects.append((
                tab_id,
                pygame.Rect(self.x + i * tab_w, self.y, tab_w, TAB_HEIGHT),
            ))

    def _position_child(self, tab_id: str) -> None:
        """Move the child panel into the dashboard frame (below tab strip)."""
        tab = self._tabs.get(tab_id)
        if tab is None:
            return
        panel, _ = tab
        panel.reposition(
            self.x, self.y + TAB_HEIGHT,
            self.width, self.height - TAB_HEIGHT,
        )

    # ── Tab control ──────────────────────────────────────────────────────

    def set_active(self, tab_id: str) -> None:
        """Activate a tab (no-op if unknown)."""
        if tab_id not in self._tabs and self._tabs:
            tab_id = self.active_tab
        if self.active_tab in self._tabs:
            old, _ = self._tabs[self.active_tab]
            old.visible = False
        self.active_tab = tab_id
        if tab_id in self._tabs:
            panel, _ = self._tabs[tab_id]
            self._position_child(tab_id)
            panel.visible = True

    def cycle(self, direction: int) -> None:
        """Cycle tabs: direction +1 = right, -1 = left."""
        idx = TAB_ORDER.index(self.active_tab) if self.active_tab in TAB_ORDER else 0
        self.set_active(TAB_ORDER[(idx + direction) % len(TAB_ORDER)])

    def active_dispatch_name(self) -> str:
        """The dispatch_click panel name for the active tab."""
        return TAB_DISPATCH_NAMES[self.active_tab]

    # ── Input ────────────────────────────────────────────────────────────

    def handle_key(self, key: int):
        """LEFT/RIGHT (A/D) switch tabs; everything else goes to the child."""
        if key in (pygame.K_RIGHT, pygame.K_d):
            self.cycle(1)
            return None
        if key in (pygame.K_LEFT, pygame.K_a):
            self.cycle(-1)
            return None
        tab = self._tabs.get(self.active_tab)
        if tab is None:
            return None
        return tab[0].handle_key(key)

    def handle_click(self, x: int, y: int, button: int = 1):
        """Tab strip first, then delegate to the active child."""
        for tab_id, rect in self._tab_rects:
            if rect.collidepoint(x, y):
                self.set_active(tab_id)
                return None
        tab = self._tabs.get(self.active_tab)
        if tab is None:
            return None
        return tab[0].handle_click(x, y, button)

    def handle_mouse_move(self, mx: int, my: int) -> None:
        tab = self._tabs.get(self.active_tab)
        if tab is not None:
            tab[0].handle_mouse_move(mx, my)

    def handle_mouse_up(self) -> None:
        tab = self._tabs.get(self.active_tab)
        if tab is not None and hasattr(tab[0], "handle_mouse_up"):
            tab[0].handle_mouse_up()

    def handle_wheel(self, delta: int) -> None:
        tab = self._tabs.get(self.active_tab)
        if tab is not None and hasattr(tab[0], "handle_wheel"):
            tab[0].handle_wheel(delta)

    def close(self) -> None:
        self.visible = False
        for panel, _ in self._tabs.values():
            panel.visible = False

    # ── Rendering ────────────────────────────────────────────────────────

    def render(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        self._draw_frame(screen)
        self._draw_tabs(screen)
        tab = self._tabs.get(self.active_tab)
        if tab is not None:
            _, render_fn = tab
            render_fn(screen)

    def draw_contents(self, screen, content_rect) -> None:
        # Unused — render() is fully custom (chrome + tabs + child).
        pass

    def _draw_frame(self, screen: pygame.Surface) -> None:
        bg = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        bg.fill((*self.COLOR_BG, self.bg_alpha))
        screen.blit(bg, (self.x, self.y))
        pygame.draw.rect(
            screen, self.COLOR_BORDER, (self.x, self.y, self.width, self.height), 2,
        )

    def _draw_tabs(self, screen: pygame.Surface) -> None:
        font = get_font("monospace", 13, bold=True)
        for tab_id, rect in self._tab_rects:
            active = tab_id == self.active_tab
            fill = (70, 85, 110) if active else (40, 45, 58)
            pygame.draw.rect(screen, fill, rect)
            pygame.draw.rect(screen, self.COLOR_BORDER, rect, 1)
            label = TAB_LABELS.get(tab_id, tab_id)
            surf = font.render(
                label, True, (240, 240, 255) if active else (150, 150, 165),
            )
            screen.blit(surf, surf.get_rect(center=rect.center))
