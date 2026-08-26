# Phase Plan — Reusable Panel Window (bounded text, scrollbar, wheel + keyboard selection)

**Goal.** Standardize the nine game UI panels on a single importable, configurable
`PanelWindow` base class that gives every panel, uniformly:

1. **Bounded content** — text and rows never paint past the panel window (via
   `screen.set_clip`), and long body text is word-wrapped instead of single-line
   truncated.
2. **A visible, interactive scrollbar** — thumb sized/positioned by `visible/total`,
   clickable, draggable, plus page-up/page-down.
3. **Mouse-wheel scrolling** — real `pygame.MOUSEWHEEL` events reach the active panel
   (currently dead) and are clamped to the content bounds.
4. **Keyboard navigation with a visible selection** — a single, uniformly-drawn focus
   highlight driven by WASD / arrow keys, clamped to the (possibly scrolled) content.

**Why a separate plan.** This touches every panel, the router, the input manager, and
the render contract — a refactor too large for `tmp/IMPLEMENTATION-PLAN.md`. It is
phased so each step is independently testable and the suite stays green.

---

## 1. Current state (traced 2026-08-25)

### 1.1 No shared base exists
Only `input/panel_dispatcher.py:10 (PanelDispatcher, logic-only)` is shared. Each of the
nine panels is a standalone class that hand-rolls the same chrome, geometry, rect-cache,
hover, selection, `handle_mouse_move`, `handle_key`, `handle_click` scaffolding.

Panels are instantiated in `core/bootstrap.py`, shown via `game.set_state()`
(`core/game.py:147-172`), and each has a `GameState` (`core/state.py:52-62`). The router
routes input to them:
- **KEYDOWN** → `router.py:176-182` calls `active_panel.handle_key(key)` → dispatched.
- **click** → per-`GameState` `if/elif` in `router._handle_mouse_button_down` (`router.py:432`)
  → `dispatch_click`.
- **`render(screen)`** — seven panels use this; **`BuildingPanel.render(self, screen, bs, sm)`**
  (`ui/building_panel.py:54`) and **`GearPanel.render(self, screen, pg, inv, gm)`**
  (`ui/gear_panel.py:84`) break the contract and are called directly in `game.py:317-319`.

### 1.2 What each panel has today (the gap)

| Panel | `_scroll_offset` | Scrollbar drawn | Mouse-wheel | Selection tracked | Selection **drawn** |
|-------|:---:|:---:|:---:|:---:|:---:|
| Quest   | yes (`:134`) | yes (decorative, `:362`) | **no** | yes (`:137`) | **yes** |
| Trade   | yes (`:123`) | **no** | **no** | yes (`:112-116`) | **yes** |
| Inventory | **none** | **no** | **no** | yes (`:60`) | yes (`:171`) |
| Skill   | **none** | **no** | **no** | yes (`:72`) | **no** (invisible) |
| Crafting | **none** | **no** | **no** | yes (`:62`) | **no** (invisible) |
| Building | **none** | **no** | **no** | yes (`:38`) | **no** (invisible) |
| Gear    | **none** | **no** | **no** | yes (`:81`) | hover-only |
| Recruit | **uninit'd** (`router.py:541` would `AttributeError`) | **no** | **no** | yes (`:114`) | partial |
| Diplomacy | **none** (`router.py:544` guards `pass`) | **no** | **no** | **none** | **no** |

### 1.3 Confirmed missing machinery (full-repo grep)
- **`set_clip` / `Rect.clip`:** none anywhere. Overflow rows currently paint past the
  window (over the status bar/footer).
- **Mouse-wheel delivery:** `input_manager.py:50-51` is the only `MOUSEWHEEL` handler and
  it maps the delta to **dead** `zoom_in`/`zoom_out` flags (`input_manager.py:201-204`) that
  nothing reads. `router.py` has **no `MOUSEWHEEL` branch**; its `_handle_scroll`
  (`router.py:523-546`) only fires on legacy buttons `4/5` (dead on `pygame==2.6.1`, where a
  wheel emits `button==0`), clamps only to `max(0, …)`, ignores `event.y`, and always moves
  ±1. **Real wheel scrolling is entirely unwired.**
- **Text wrapping:** none. Only manual, monospace char-truncation (`quest_panel.py:483`,
  `skill_panel.py:255`). No multi-line wrapping.
- **Scrollbar interaction:** the one scrollbar (`quest_panel.py:362-385`) is purely
  decorative — no thumb hit-test, drag, or click-to-page anywhere.
- **`PAGEDOWN`/`PAGEUP`:** consumed by camera pitch (`input_manager.py:88-90`); never scroll
  a panel.
- **Text:** no `wrap_text`, no shared font registry (every panel builds its own `SysFont`).
- **Selection nav:** the `(-1, len-1)` clamp idiom + WASD/arrow movement is copied verbatim
  in every `handle_key`; there is no shared helper or shared focus model.
- **Coordinates:** panels build screen-space rects and hit-test with `collidepoint` using
  raw `event.pos`; no screen→panel-local conversion exists.

**Net:** only `QuestPanel` bundles all four wants, and even it lacks wheel + interactive
thumb + `set_clip` + text-wrap. Everything else is missing ≥2 of the 4.

---

## 2. Design

### 2.1 Where the class lives
`ui/panel_window.py` — `class PanelWindow`. Importable and reusable by any panel (and by
future panels). Concrete panels subclass it.

### 2.2 What the base owns (universal) vs. what panels own (content)
The base owns the **chrome + viewport + interaction model**; the panel owns **only its
content layout** via one overridable hook. This is what makes panels "mirror" each other
without duplicating the window machinery.

**Base-owned (configurable via constructor):**
- Window chrome: translucent bg surface + double border, title, optional close button.
- **Content viewport** `content_rect` + `screen.set_clip(content_rect)` during content
  draw, `set_clip(None)` after. This is the bounding mechanism — no manual truncation
  needed.
- Scrollbar: thumb from `visible_ratio` (quest pattern `:362`) **+** stored `thumb_rect`,
  click-to-page, drag, and page-up/down.
- Scroll offset state + clamping (`0 .. max_offset`) + `scroll_by(n)`.
- Selection controller: `_selected_index` with a single clamp helper supporting both
  single-column (`step=1`) and grid (`step=cols`) navigation.
- Text helper: `wrap_text(text, max_width) -> list[Surface]` (word-wrap to the viewport
  width) so body text can never run off the right edge.
- Shared font registry (title / normal / small / bold), created once, not per panel.
- Cached interactive-rect list (`list[(Rect, payload)]`) for `collidepoint`.

**Panel-owned (subclass implements):**
- `draw_contents(screen, content_rect)` — draws this panel's rows/items **inside the
  clipped viewport**, using base helpers (`row_rect(i)`, `wrap_text()`, `draw_selected(i)`).
- Optional overrides: `on_scroll(delta)`, `on_key(key) -> tuple|None`,
  `on_click(x, y, button) -> tuple|None`, `on_mouse_move(x, y)`. For simple list panels the
  base supplies sensible defaults (single-column nav + default scrollbar), so a panel like
  Diplomacy can be ported with almost no subclass code.

### 2.3 Uniform render contract
`PanelWindow.render(screen)`:
```
draw_window_chrome()
screen.set_clip(self.content_rect)
self.draw_contents(screen, self.content_rect)
screen.set_clip(None)
draw_scrollbar()
```
This replaces Building/Gear's `render(self, screen, ...)` with
`render(screen) + draw_contents(...)`; `game.py:317-319` then call `render(screen)` like the
others. The router's `_get_active_panel().render(screen)` stays uniform.

### 2.4 Wheel delivery (the one router fix that enables everything)
On `pygame==2.6.1` a wheel emits `pygame.MOUSEWHEEL` with `event.y` = ±1 and `button==0`.
- Add a `MOUSEWHEEL` branch in `router.py:handle` (after the existing key/mouse branches).
- When a panel is active, call `active_panel.scroll_by(event.y)` (clamped by the base);
  otherwise fall through to camera zoom.
- Keep camera zoom working: decide whether wheel **also** zooms while a panel is open
  *(open decision #1)*. Camera pitch still owns `PAGEDOWN`/`PAGEUP` *(open decision #2)*.
- Delete the dead legacy-button `4/5` `_handle_scroll` path (it can't fire and would
  `AttributeError` on panels lacking `_scroll_offset`).

### 2.5 Config surface (constructor kwargs)
`title`, `x, y, width, height`, color dict (`bg/border/title/row-bg/row-selected/
scrollbar`), `max_visible` rows, `row_height`, `row_gap`, `show_close`, `selection_mode`
(`list` | `grid` with `grid_cols`), `has_scrollbar`, and which chrome rows to reserve
(title height, tabs area). This is the "variable settings for other panels" the panels
need — a grid panel (inventory/gear) sets `selection_mode='grid'`; a text panel (diplomacy)
sets a tall wrap region; a list panel (skill/crafting/building/recruit) gets the default
single-column nav + scrollbar.

---

## 3. Phases

Each phase ends with `python -m pytest -q` green (683 currently). The base class is
usable by new panels from the end of **Phase 1**; existing panels are migrated in order of
increasing layout complexity (lowest risk first).

### Phase 1 — Base class scaffold + non-breaking render contract
Create `ui/panel_window.py`:
- Configurable chrome (bg, double border, title, close), font registry, viewport +
  `set_clip` management, `draw_contents` hook, `max_offset`/`scroll_by`, `wrap_text`,
  selection-clamp helper, rect-cache builder.
- `render(screen)` implementing the contract in §2.3.
- **Non-breaking:** panels keep their current `render(screen)` signature; the base is a
  drop-in the *next* phase adopts.
- Test: instantiate the base with dummy content and assert it renders without error and
  that `set_clip` is active during `draw_contents`.

### Phase 2 — Mouse-wheel delivery (enabler)
- Add the `MOUSEWHEEL` branch in `router.py` (§2.4) routing to `active_panel.scroll_by`
  when a panel is active; keep camera zoom; delete the dead legacy `_handle_scroll`.
- Base adds interactive scrollbar (thumb `Rect` stored, click-to-page, drag) — decorative
  base is not enough anymore; tests assert wheel deltas clamp and a click on the thumb
  region pages.
- Test: wheel → active panel scrolls and clamps; wheel with no panel → camera zoom path.

### Phase 3 — Port the simplest panel (Diplomacy)
Diplomacy has no selection, no scroll, no wheel today — the smallest, clearest win.
- Subclass `PanelWindow`; implement `draw_contents` (bounded, wrapped body text + buttons).
- Gains: bounded/wrapped text, scrollbar if long, keyboard nav + visible selection on its
  action buttons, mouse-wheel.
- **Cleans up the live diplomacy bug** (#8): fold the double-fire / broken `_execute_negotiation`
  mouse path into the base's unified `on_click`/`on_key` contract so there is one canonical
  negotiate path. *(See `tmp/LIVE-ISSUES.md` diplomacy item / `tmp/IMPLEMENTATION-PLAN.md` §P2.)*
- Test: diplomacy renders bounded, wheel scrolls, Enter/Escape route correctly, no
  `AttributeError` on mouse negotiate.

### Phase 4 — List-style panels (Skill, Crafting, Building, Recruit)
These already track a selection index but **don't draw it** — the base now draws it.
- Port each; they mainly add `draw_contents` and drop their inline clamp/idle code.
- **Building**: unify `render(self, screen, bs, sm)` → `render(screen) + draw_contents`;
  update `game.py:317`. Same for **Gear** (`game.py:319`).
- **Recruit**: fixes the missing `_scroll_offset` (was an `AttributeError` waiting to
  happen at `router.py:541`).
- Test: each panel draws a visible selection, scrolls with wheel + keys, and selection
  never runs past the clipped bounds.

### Phase 5 — Grid + multi-list panels (Inventory, Gear-grid, Trade)
Inventory/gear are 2D grids; trade has two parallel lists + tabs.
- `selection_mode='grid'` (`grid_cols`) gives grid nav; `draw_contents` handles the custom
  layout. Trade reuses the base for each list region + its own tab chrome.
- These already scroll by row count without clip in places; the base's viewport fixes that.
- Test: grid keyboard nav wraps correctly, all rows clipped, scrollbar present when the
  grid overflows.

### Phase 6 — Housekeeping
- Remove per-panel `SysFont` instantiation in favor of the base registry (measure no
  perf regression — fonts are cached).
- Delete the dead legacy `_handle_scroll` and any now-unused per-panel `_scroll_offset`
  that the base supersedes.
- Update `README.md` "UI" section (§11) to note the unified `PanelWindow` contract and the
  uniform `render(screen)` + `draw_contents` hook.
- Final full suite run.

---

## 4. Risks & mitigation

| Risk | Mitigation |
|------|------------|
| Refactoring 9 working panels breaks existing tests | One panel per phase; suite green before moving on; base tested standalone in Phase 1. |
| Building/Gear divergent `render` signatures | Unified in Phase 4 via `draw_contents`; `game.py` call sites updated there. |
| Wheel path conflicting with camera zoom / existing zoom flags | One `MOUSEWHEEL` branch, panel-vs-camera gated by active-panel state; camera zoom preserved and tested. |
| Grid panels don't fit a row-scroll model | `selection_mode='grid'` variant + panel-specific `draw_contents`; base stays layout-agnostic. |
| TAB key ambiguity (quest/trade cycle own tabs vs `K_TAB`→open skill at `input_manager.py:66`) | Resolve per-panel in open decision #2; base never claims a global TAB. |
| Text-wrap perf on long descriptions | `wrap_text` caches by (text, width); measure in Phase 6. |

---

## 5. Open decisions (need the author)

1. **Wheel during an open panel — also zoom the (frozen) camera, or panel-exclusive?**
   Recommend: panel-exclusive while a panel is active; zoom otherwise.
2. **`PAGEDOWN`/`PAGEUP` and global TAB** — repurpose `PAGEDOWN`/`PAGEUP` for panel page
   scroll when a panel is active (currently camera pitch)? Define per-panel TAB semantics.
3. **Migration strategy** — refactor existing panels onto `PanelWindow` (recommended,
   phased) **vs.** keep them and let only *new* panels use the base. Refactor gives the
   bounded-text/scrollbar/selection win to all nine now; the pure-reuse option is lower
   risk but leaves the current panels unchanged.
4. **Selection nav keys** — standardize on WASD/arrows across all panels (Quest already
   uses them); confirm no panel needs a different keymap.
5. **Close/hint row** — keep Quest's status bar + "close hint" as panel-specific content,
   or promote them into the base (trade/quest both have them)?

---

## 6. Acceptance criteria (final)
- All nine panels subclass `PanelWindow`; every panel's `render(screen)` is uniform;
  Building/Gear no longer use the extra-arg render signatures.
- Every panel bounds content with `set_clip`; long body text is word-wrapped, never runs
  off the right edge.
- Every list/scrollable panel draws a visible scrollbar; mouse-wheel and page-up/down
  scroll it; a click/drag on the thumb pages.
- Every panel exposes keyboard navigation with a uniformly-drawn visible selection that
  stays within the clipped bounds while scrolling.
- `python -m pytest -q` green; README §11 updated.
