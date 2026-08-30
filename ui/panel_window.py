"""
panel_window.py — base class for the game's UI panels.

Provides a single, importable, configurable "panel window" that owns the
chrome + viewport + interaction model shared by every panel. Concrete panels
subclass it and implement only their content layout via
``draw_contents(screen, content_rect)`` — this is what lets the nine panels
"mirror" each other instead of each hand-rolling the same double border,
clipping viewport, scrollbar, scroll offset and selection nav.

See docs/panel-ui-refactor-phase-plan.md for the full refactor plan.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Tuple

    Surface = pygame.types.Surface
    Font = pygame.types.Font
    Rect = pygame.types.Rect

from render.font_cache import get_font


# Sentinel returned by _scrollbar_hit when the click lands on the thumb
# (as opposed to an int page-delta for a track click).
SCROLLBAR_DRAG = object()


class PanelWindow:
    """
    Bounded, scrollable, keyboard-navigable panel window.

    The base owns everything that is identical across panels:

    * chrome — translucent background + double-line border, title, optional
      close button;
    * a **content viewport** clipped with ``screen.set_clip`` so rows never
      paint past the window;
    * a visible scrollbar whose thumb is sized/positioned by the
      ``visible / total`` ratio;
    * a clamped scroll offset and ``scroll_by``;
    * a selection controller with a single clamp helper that supports both
      single-column (``list``) and grid (``selection_mode='grid'``) nav;
    * a word-wrap helper and a shared font registry.

    A panel owns only its content:

    * ``draw_contents(screen, content_rect)`` — REQUIRED; draw this panel's
      rows/items inside the clipped viewport;
    * ``scroll_viewport() -> (visible_units, total_units)`` — for scrollbar
      sizing (default ``(1, 1)``);
    * ``select_count() -> int`` — number of selectable items (for nav clamp);
    * ``on_key(key) -> tuple | None`` / ``on_click(x, y, button) -> tuple |
      None`` / ``on_mouse_move(x, y)`` / ``on_scroll(delta)`` — panel-specific
      hooks, all defaulting to no-ops.

    Render contract (:meth:`render`):

    .. code-block:: python

        draw_chrome()
        screen.set_clip(content_rect)
        draw_contents(screen, content_rect)
        screen.set_clip(None)
        draw_scrollbar()
    """

    # ── Defaults (overridable per-panel via constructor kwargs) ──────────
    DEFAULT_TITLE = "Panel"
    DEFAULT_X = 250
    DEFAULT_Y = 30
    DEFAULT_WIDTH = 460
    DEFAULT_HEIGHT = 580

    TITLE_HEIGHT = 26          # reserved strip at the top for the title/close
    FOOTER_HEIGHT = 0          # reserved strip at the bottom (status/hint)

    # Interaction geometry
    ROW_HEIGHT = 20
    ROW_GAP = 4
    SCROLLBAR_WIDTH = 8
    CLOSE_SIZE = 22
    GRID_COLS = 1

    # ── Color palette (OSRS-ish dark; override per panel) ────────────────
    COLOR_BG = (30, 30, 40)
    COLOR_BORDER = (100, 100, 120)
    COLOR_BORDER_LIGHT = (160, 160, 180)
    CONTENT_BG = (35, 35, 45)
    TITLE_COLOR = (200, 200, 220)
    ROW_BG = (45, 45, 55)
    ROW_SELECTED = (75, 60, 85)
    TEXT_COLOR = (200, 200, 220)
    TEXT_DIM = (150, 150, 170)
    SCROLLBAR_BG = (30, 30, 35)
    SCROLLBAR_THUMB = (80, 80, 100)

    def __init__(
        self,
        *,
        title: str = DEFAULT_TITLE,
        x: int = DEFAULT_X,
        y: int = DEFAULT_Y,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        title_height: int = TITLE_HEIGHT,
        footer_height: int = FOOTER_HEIGHT,
        show_close: bool = True,
        has_scrollbar: bool = True,
        selection_mode: str = "list",
        grid_cols: int = 1,
        row_height: int = ROW_HEIGHT,
        row_gap: int = ROW_GAP,
        scrollbar_width: int = SCROLLBAR_WIDTH,
        bg_alpha: int = 240,
    ) -> None:
        """
        Configure the window chrome and geometry.

        Args:
            title: Title text in the top bar.
            x, y, width, height: Outer panel rectangle.
            title_height: Reserved px at the top for the title/close button.
            footer_height: Reserved px at the bottom for a status/hint row (0
                unless the panel opts in via ``draw_footer``).
            show_close: Draw the close (X) button in the top-right.
            has_scrollbar: Reserve a scrollbar strip inside the viewport.
            selection_mode: ``"list"`` (single column) or ``"grid"``
                (``grid_cols`` columns).
            grid_cols: Columns when ``selection_mode == "grid"``.
            row_height, row_gap: Row geometry used by the default helpers.
            scrollbar_width: Width of the scrollbar strip.
            bg_alpha: Alpha channel for the translucent background surface.
        """
        # Runtime state (mirrors the per-panel state the router already reads)
        self.visible: bool = False
        self._hovered: str = ""
        self._scroll_offset: int = 0
        self._selected_index: int = -1
        # Scrollbar interaction (Phase 2)
        self._thumb_rect: Optional[Rect] = None
        self._scrollbar_dragging: bool = False
        self._drag_start_y: int = 0
        self._drag_start_offset: int = 0
        # Cache of interactive (Rect, payload) tuples built during draw_contents
        self._interactive_rects: list = []

        # Config
        self.title = title
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.title_height = title_height
        self.footer_height = footer_height
        self.show_close = show_close
        self.has_scrollbar = has_scrollbar
        self.selection_mode = selection_mode
        self.grid_cols = max(1, grid_cols)
        self.row_height = row_height
        self.row_gap = row_gap
        self.scrollbar_width = scrollbar_width
        self.bg_alpha = bg_alpha

        # Compute geometry once. The content viewport spans the full panel
        # width minus the scrollbar strip (when present); it sits between the
        # reserved title strip (top) and footer strip (bottom).
        self.rect = pygame.Rect(x, y, width, height)
        content_top = y + title_height
        content_bottom = y + height - footer_height
        content_h = max(0, content_bottom - content_top)
        self.content_rect = pygame.Rect(x, content_top, width, content_h)

        # Scrollbar strip: the rightmost strip *inside* the content viewport.
        # Content is drawn up to (but not over) this strip.
        if has_scrollbar:
            self._scrollbar_strip = pygame.Rect(
                x + width - scrollbar_width, content_top, scrollbar_width, content_h,
            )
            self.content_rect.width -= scrollbar_width
        else:
            self._scrollbar_strip = None

        self._close_rect = pygame.Rect(
            x + width - self.CLOSE_SIZE - 4, y + 4,
            self.CLOSE_SIZE, self.CLOSE_SIZE,
        )

        # Wrap-text cache keyed by (text, max_width, size, bold)
        self._wrap_cache: dict = {}

    # ── Fonts (shared, cached) ───────────────────────────────────────────
    @property
    def font_title(self) -> Font:
        return get_font("monospace", 14, bold=True)

    @property
    def font_normal(self) -> Font:
        return get_font("monospace", 11)

    @property
    def font_small(self) -> Font:
        return get_font("monospace", 10)

    @property
    def font_bold(self) -> Font:
        return get_font("monospace", 12, bold=True)

    # ── Scroll ───────────────────────────────────────────────────────────
    def scroll_viewport(self) -> Tuple[int, int]:
        """
        Return ``(visible_units, total_units)`` for scrollbar sizing.

        Panels override this; the default (1, 1) yields a full-size thumb and
        no scrollbar.
        """
        return 1, 1

    @property
    def max_offset(self) -> int:
        """Maximum valid scroll offset (0 when content fits)."""
        visible, total = self.scroll_viewport()
        return max(0, total - visible)

    def scroll_by(self, delta: int) -> None:
        """Clamp the scroll offset by ``delta`` and notify ``on_scroll``."""
        self._scroll_offset = self._clamp_offset(self._scroll_offset + delta)
        self.on_scroll(delta)

    def _clamp_offset(self, offset: int) -> int:
        return max(0, min(offset, self.max_offset))

    # ── Selection ────────────────────────────────────────────────────────
    def select(self, index: int) -> None:
        """
        Move the selection to ``index`` (clamped to ``[-1, select_count()-1]``).

        Wraps the ``[-1, n-1]`` idiom used across panels into one helper and
        only fires ``on_select`` when the value actually changes.
        """
        prev = self._selected_index
        n = self.select_count()
        if n <= 0:
            self._selected_index = -1
            return
        if index < -1:
            index = -1
        if index >= n:
            index = n - 1
        self._selected_index = index
        if self._selected_index != prev:
            self.on_select(self._selected_index)

    def select_count(self) -> int:
        """Number of selectable items; panels override (default 0)."""
        return 0

    def on_select(self, index: int) -> None:
        """Called when the selection index changes. Default no-op."""

    # ── Text wrapping ────────────────────────────────────────────────────
    def wrap_text(
        self,
        text: str,
        max_width: int,
        color: Optional[tuple] = None,
        font: Optional[Font] = None,
    ) -> list:
        """
        Word-wrap ``text`` to ``max_width`` px and return pre-rendered lines.

        Caches by ``(text, max_width, size, bold)``. Lines are returned as
        ``pygame.Surface`` objects so a panel can simply blit them; an empty
        line becomes an empty surface of the correct height.
        """
        font = font or self.font_normal
        color = color if color is not None else self.TEXT_COLOR
        key = (text, max_width, font.get_height(), font.get_bold(), color)
        cached = self._wrap_cache.get(key)
        if cached is not None:
            return cached

        lines: list = []
        for paragraph in (text or "").split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                trial = current + " " + word
                if font.size(trial)[0] <= max_width:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            lines.append(current)

        surfaces = [
            font.render(line, True, color) for line in lines
        ]
        self._wrap_cache[key] = surfaces
        return surfaces

    # ── Highlight helpers ────────────────────────────────────────────────
    def draw_row(self, screen: Surface, row_rect: Rect, selected: bool = False) -> None:
        """Draw a single list row (selected rows use the base highlight color)."""
        color = self.ROW_SELECTED if selected else self.ROW_BG
        pygame.draw.rect(screen, color, row_rect)

    def draw_selected_row(self, screen: Surface, row_rect: Rect) -> None:
        """Draw the uniformly-colored selection highlight for a row."""
        pygame.draw.rect(screen, self.ROW_SELECTED, row_rect)

    # ── Public input entry points (match the router's existing calls) ────
    def handle_mouse_move(self, mx: int, my: int) -> None:
        """
        Track hover (close button / scrollbar / interactive rects), then
        delegate to ``on_mouse_move``.
        """
        self._hovered = ""
        if self.show_close and self._close_rect.collidepoint(mx, my):
            self._hovered = "close"
            return
        if self._scrollbar_hit(mx, my) is not None:
            self._hovered = "scrollbar"
        for _rect, _payload in self._interactive_rects:
            if _rect.collidepoint(mx, my):
                self._hovered = "content"
                break
        if self._scrollbar_dragging:
            self._drag_scrollbar(my)
        self.on_mouse_move(mx, my)

    def handle_mouse_up(self) -> None:
        """End a scrollbar drag. Called by the router on MOUSEBUTTONUP."""
        self._scrollbar_dragging = False

    def handle_key(self, key: int) -> Optional[tuple]:
        """
        Keyboard nav: arrow / WASD move the selection; page keys scroll.

        All other keys are delegated to ``on_key``; navigation-only keys
        return ``None``.
        """
        if key in (pygame.K_w, pygame.K_UP):
            self.select(self._selected_index - 1)
            return None
        if key in (pygame.K_s, pygame.K_DOWN):
            self.select(self._selected_index + 1)
            return None
        if key in (pygame.K_a, pygame.K_LEFT):
            self.select(self._selected_index - self.grid_cols)
            return None
        if key in (pygame.K_d, pygame.K_RIGHT):
            self.select(self._selected_index + self.grid_cols)
            return None
        return self.on_key(key)

    def handle_wheel(self, delta: int) -> None:
        """Deliver a mouse-wheel delta to the panel (clamped by the base)."""
        self.scroll_by(delta)

    def handle_click(self, x: int, y: int, button: int = 1) -> Optional[tuple]:
        """
        Route a click: close button / scrollbar first, then ``on_click``.

        Returns an action tuple, or ``None`` for a scroll / non-action click.
        """
        if self.show_close and self._close_rect.collidepoint(x, y):
            return ("close",)
        hit = self._scrollbar_hit(x, y)
        if hit is SCROLLBAR_DRAG:
            self._start_scroll_drag(y)
            return None
        if isinstance(hit, int):
            self.scroll_by(hit)
            return None
        return self.on_click(x, y, button)

    # ── Scrollbar interaction (click-to-page + thumb drag) ───────────────
    def _page_delta(self) -> int:
        """Scroll one page — the number of visible units."""
        visible, _ = self.scroll_viewport()
        return max(1, visible)

    def _scrollbar_hit(self, x: int, y: int):
        """
        Classify a point against the scrollbar:

        * ``SCROLLBAR_DRAG`` if it lands on the thumb;
        * an int page delta for a click in the track above/below the thumb;
        * ``None`` if it is outside the scrollbar strip.
        """
        strip = self._scrollbar_strip
        if strip is None:
            return None
        if not (strip.x <= x <= strip.x + strip.width
                and strip.y <= y <= strip.y + strip.height):
            return None
        thumb = self._thumb_rect
        if thumb is not None and thumb.x <= x <= thumb.x + thumb.width \
                and thumb.y <= y <= thumb.y + thumb.height:
            return SCROLLBAR_DRAG
        if thumb is not None:
            if y < thumb.y:
                return -self._page_delta()
            if y > thumb.y + thumb.height:
                return self._page_delta()
        return None

    def _start_scroll_drag(self, y: int) -> None:
        """Begin dragging the thumb from the given screen-y."""
        self._scrollbar_dragging = True
        self._drag_start_y = y
        self._drag_start_offset = self._scroll_offset

    def _drag_scrollbar(self, y: int) -> None:
        """Reposition the offset from the thumb's vertical position."""
        strip = self._scrollbar_strip
        thumb = self._thumb_rect
        if strip is None or thumb is None:
            return
        travel = strip.height - thumb.height
        if travel <= 0:
            return
        frac = max(0.0, min(1.0, (y - strip.y) / travel))
        self._scroll_offset = self._clamp_offset(round(frac * self.max_offset))

    # ── Panel hooks (defaults: no-op) ────────────────────────────────────
    def draw_contents(self, screen: Surface, content_rect: Rect) -> None:
        """
        Draw this panel's content inside the clipped viewport.

        REQUIRED — override in subclasses.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement draw_contents()"
        )

    def on_key(self, key: int) -> Optional[tuple]:
        """Panel-specific keyboard handling. Default no-op."""

    def on_click(self, x: int, y: int, button: int = 1) -> Optional[tuple]:
        """Panel-specific click handling. Default no-op."""

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Panel-specific mouse-move handling. Default no-op."""

    def on_scroll(self, delta: int) -> None:
        """Panel-specific scroll notification. Default no-op."""

    def close(self) -> None:
        """
        Close the panel and perform any necessary cleanup.

        Default implementation just hides the panel. Panels that manage
        external session state (e.g., NPC interactions) should override
        this to clean up their session before hiding.
        """
        self.visible = False

    # ── Rendering ────────────────────────────────────────────────────────
    def render(self, screen: Surface) -> None:
        """
        Render the complete panel window.

        Implements the uniform contract: chrome → clipped content →
        scrollbar. Returns immediately if the panel is hidden.
        """
        if not self.visible:
            return

        self._draw_chrome(screen)
        screen.set_clip(self.content_rect)
        self.draw_contents(screen, self.content_rect)
        screen.set_clip(None)
        if self.has_scrollbar:
            self._draw_scrollbar(screen)

    def _draw_chrome(self, screen: Surface) -> None:
        """Translucent background + double-line border + title + close."""
        px, py, pw, ph = self.rect

        # Double-line border (OSRS-style)
        pygame.draw.rect(screen, self.COLOR_BORDER, (px, py, pw, ph), 2)
        pygame.draw.rect(screen, self.COLOR_BORDER_LIGHT,
                         (px + 3, py + 3, pw - 6, ph - 6), 1)

        # Translucent fill
        bg_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg_surf.fill((*self.COLOR_BG, self.bg_alpha))
        screen.blit(bg_surf, (px, py))

        # Title
        title_surf = self.font_title.render(self.title, True, self.TITLE_COLOR)
        screen.blit(title_surf, (px + 10, py + (self.title_height - title_surf.get_height()) // 2))

        # Close button
        if self.show_close:
            self._draw_close_button(screen)

    def _draw_close_button(self, screen: Surface) -> None:
        """Draw the (X) close button; register its rect for hit-testing."""
        color = self.ROW_SELECTED if self._hovered == "close" else self.ROW_BG
        pygame.draw.rect(screen, color, self._close_rect)
        pygame.draw.rect(screen, self.COLOR_BORDER, self._close_rect, 1)
        pc = (255, 255, 255)
        p = 5
        pygame.draw.line(screen, pc,
                         (self._close_rect.x + p, self._close_rect.y + p),
                         (self._close_rect.x + self._close_rect.width - p,
                          self._close_rect.y + self._close_rect.height - p), 2)
        pygame.draw.line(screen, pc,
                         (self._close_rect.x + self._close_rect.width - p, self._close_rect.y + p),
                         (self._close_rect.x + p, self._close_rect.y + self._close_rect.height - p), 2)

    def _draw_scrollbar(self, screen: Surface) -> None:
        """
        Draw the scrollbar background and a thumb sized/positioned by the
        visible/total ratio, remembering ``thumb_rect`` for click/drag hits.
        """
        strip = self._scrollbar_strip
        if strip is None:
            return
        pygame.draw.rect(screen, self.SCROLLBAR_BG, strip)

        visible, total = self.scroll_viewport()
        if total <= visible:
            return
        thumb_h = max(20, int(strip.height * visible / total))
        max_offset = self.max_offset
        thumb_ratio = self._scroll_offset / max_offset if max_offset > 0 else 0
        thumb_y = strip.y + int(thumb_ratio * (strip.height - thumb_h))
        self._thumb_rect = pygame.Rect(strip.x, thumb_y, strip.width, thumb_h)
        pygame.draw.rect(screen, self.SCROLLBAR_THUMB, self._thumb_rect)
