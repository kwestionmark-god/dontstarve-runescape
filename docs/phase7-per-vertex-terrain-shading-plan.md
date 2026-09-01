# Phase 7: Per-Vertex Terrain Shading (Triangular Gouraud) — Implementation Plan

**Date:** 2026-08-31
**Author:** Grok
**Status:** Planning complete — ready for implementation
**Scope:** 7 phases (P0–P6), replacing flat per-tile terrain shading with smooth per-corner (triangle-interpolated) shading

---

## Problem statement

Terrain is currently rendered as a single flat-shaded quad per tile:

- The 4 corners of each tile are *geometrically* displaced by interpolated
  elevation (`TileMap.get_corner_height`), so the surface silhouette is already
  smooth.
- But **lighting is piecewise-constant per tile**: one `brightness`, `slope_mag`,
  `AO`, `fog`, and rim value is computed at the tile center and applied as a
  uniform overlay over the whole tile.

The result is visibly "low-def" stepped shading at tile edges — the exact flat-vs-Gouraud
problem from classic polygon rendering. This plan replaces the flat per-tile scalar with
**per-corner (per-vertex) values interpolated across a triangle mesh**, so elevation,
slope shading, ambient occlusion, and fog blend continuously across tile corners/edges.

---

## Summary

| Phase | Deliverable | Primary files | Effort |
|-------|-------------|---------------|--------|
| P0 | Fix pre-existing shading-call bug; baseline tests | `world/tile_map.py`, `render/tile_renderer.py`, `tests/` | S |
| P1 | Bake per-corner height/AO/fog grids once at world-gen | `world/tile_map.py`, `render/lighting_system.py`, `world/world_gen.py` | M |
| P2 | Per-corner slope-shading math (corner normal + corner brightness) | `world/tile_map.py`, `render/lighting_system.py` | M |
| P3 | Software Gouraud triangle rasterizer | `render/gouraud.py` (new) | M |
| P4 | Integrate triangular path into `TileRenderer` | `render/tile_renderer.py` | M |
| P5 | Presets, LOD, performance knobs | `config/constants.py`, `render/tile_renderer.py`, `render/lighting_system.py` | M |
| P6 | Tests + headless render verification | `tests/` | M |

**Total estimated effort:** ~6–8 focused sessions.

---

## Current state (verified 2026-08-31)

Key facts that shape the plan, with their `file:line` locations:

- `world/tile_map.py:190` — `get_corner_height(cx, cy)` uses a 12-tile
  rotationally-symmetric kernel to return a smoothed, float corner height.
  It is **recomputed per tile per frame**: `render/tile_renderer.py:117-120` calls
  it 4× for every visible tile, each call scanning 12 tiles.
- `world/tile_map.py:248` — `get_raw_corner_elevation(cx, cy)` returns the plain
  4-tile average; used only by shading math, not for geometry.
- `world/tile_map.py:271` — `compute_slope_shading(x, y)` computes a
  **tile-center** gradient and returns one `(brightness, slope_mag)` per tile.
- `world/tile_map.py:312` — `get_surface_normal(x, y)` is also tile-center.
- `world/tile_map.py:326` — `bake_ambient_occlusion()` already bakes a
  per-corner AO grid `corner_ao` of shape `(w+1) × (h+1)`, but
  `get_tile_ao()` (line 415) collapses it back to a per-tile scalar.
- `render/tile_renderer.py:60` — `render()` draws each tile as a flat quad:
  either a terrain sprite blit plus a **full-tile** flat tint overlay for each
  lighting term (lines 171–258), or a flat `pygame.draw.polygon` fallback
  (lines 260–287).
- `config/constants.py:18` — `TILE_SUBDIVISIONS = 2` is a **dead constant**
  (no consumers anywhere) left over from an earlier sub-tile idea; this plan
  gives it a real meaning in P4/P5.
- `config/constants.py:18` `ELEVATION_LEVELS`, `:26` `Z_SCALE`, `:140`
  `SHADING_STRENGTH` — tuning constants reused below.

### Pre-existing bug found during investigation

`render/tile_renderer.py:172-174` calls:

```python
brightness, slope_mag = tile_map.compute_slope_shading(
    x, y, light_dir=(light_x, light_y, 0.0)
)
```

but `world/tile_map.py:271` declares `def compute_slope_shading(self, x, y)`
with **no** `light_dir` parameter. This raises `TypeError` whenever
`multi_light` shading is active (the `"realistic"` preset). The default
`"stylized"` preset has `multi_light: False`, which is why it hasn't surfaced.
P0 fixes it before any triangular work touches the same function.

---

## Shared design decisions

### 1. One per-corner scalar grid, `(w+1) × (h+1)`

Elevation/lighting is defined on the **corner lattice** (one vertex per tile corner),
not per tile. We bake these NumPy-accelerated grids once at world-gen and only
recompute the light-dependent ones when the light direction changes:

| Grid | Shape | Values | Recompute trigger |
|------|-------|--------|-------------------|
| `corner_height` | `(w+1)×(h+1)` | smoothed elevation (existing kernel) | once at gen |
| `corner_brightness` | `(w+1)×(h+1)` | slope shading 0.55–1.45 | sun/season change |
| `corner_ao` | `(w+1)×(h+1)` | 0–1 (already exists) | once at gen |
| `corner_fog` | `(w+1)×(h+1)` | fog density `exp(-h / FOG_SCALE_HEIGHT)` | once at gen |

`get_corner_height` becomes a cached lookup after the bake, keeping every existing
test's semantics identical.

### 2. Quad → two triangles

Each tile quad is split along a fixed diagonal (`NW→SE`) into two triangles. The
current single-quad draw folds when the 4 interpolated corner heights are not
coplanar (they generally aren't); two triangles remove that artifact and are the
standard heightfield fix.

### 3. Software Gouraud rasterizer (pure pygame)

`pygame.draw.polygon` and `pygame.gfxdraw` only do flat fills — neither interpolates
vertex colors. P3 adds a small software Gouraud triangle rasterizer (scanline
interpolation) under `render/gouraud.py`. It is the shared primitive for the
polygon path; the sprite path reuses the same per-corner values via sub-tile
interpolation (P4 decision below).

### 4. Sprite-path decision (recommended default)

The terrain sprite path currently blits a textured square with flat tint overlays.

- **Recommended:** keep the biome sprite for texture, but replace the single
  per-tile tint overlay with a `TILE_SUBDIVISIONS × TILE_SUBDIVISIONS` sub-tile grid
  whose per-vertex values are bilinearly interpolated from the 4 corners. This
  approximates Gouraud shading while preserving existing art.
- **Cleaner geometry (optional flag):** render true Gouraud triangles with the
  biome base color (drops the sprite). Both consumers share the P1/P2 grids.

To keep the plan deterministic, P4 implements the **true triangle path** as the
authoritative renderer and gates the sprite/sub-tile path behind a preset flag
(`terrain_style: "textured" | "flat"`). "textured" = current sprite + sub-tile
interpolation; "flat" = base color + true triangles.

### 5. NumPy at bake time, cheap lookup at render time

Per-frame render must not recompute kernels. World-gen bakes the grids (vectorized);
each visible corner reads an O(1) array value. Brightness/fog recompute only when
`sun_direction`, season, or weather `light_level` changes since the previous frame.

---

## Phase P0 — Fix the pre-existing shading contract + baseline tests

**Goal:** Repair the `compute_slope_shading(light_dir=...)` mismatch so the
`"realistic"` preset renders, then lock it with a regression test.

**Files:**
- Modify: `world/tile_map.py:271-310`
- Modify: `render/tile_renderer.py:164-190`
- Create: `tests/test_phase7_p0_slope_shading_contract.py`

**Changes:**
1. Add `light_dir: tuple[float, float, float] | None = None` to
   `compute_slope_shading`. When `None`, keep the legacy fixed-NW math exactly.
2. Parameterize the light dot product by `light_dir` (world X/Y only, matching the
   current elevation-gradient convention).
3. Leave `TILE_SUBDIVISIONS` in place (it becomes live in P4/P5).

**Key interface after P0:**
```python
def compute_slope_shading(
    self, x: int, y: int,
    light_dir: tuple[float, float, float] | None = None,
) -> Tuple[float, float]:
    ...
```

**Test guidance:** assert `compute_slope_shading(..., light_dir=(1.0, 0.0, 0.0))`
returns a different brightness than the default NW direction on a known slope; and
assert legacy (no `light_dir`) output equals the pre-change values on a fixed map.

---

## Phase P1 — Bake the per-corner grids

**Goal:** Move corner values from "compute per tile per frame" to "bake once at
world-gen."

**Files:**
- Modify: `world/tile_map.py` (add bake methods + `__slots__` entries)
- Modify: `render/lighting_system.py` (NumPy-accelerated `bake_corner_heights`,
  `bake_corner_fog`)
- Modify: `world/world_gen.py:227-231` (call bake after tile grid is built)
- Test: `tests/test_phase7_p1_corner_grids.py`

**Changes:**
1. Add `TileMap.corner_height: list[list[float]]`; bake with the **exact** existing
   12-tile kernel (including out-of-bounds-as-zero and total-weight normalization)
   so `get_corner_height` output is unchanged.
2. `get_corner_height(cx, cy)` reads the baked grid when available, falling back to
   on-demand compute otherwise (guards against any path that calls it before bake).
3. Add `TileMap.corner_fog` baked from `exp(-h / FOG_SCALE_HEIGHT)` using baked
   corner heights (not per-tile elevation).
4. Reuse/keep `corner_ao` (already baked) — no migration needed.

**Key interfaces after P1:**
```python
def bake_corner_heights(self) -> None: ...
def bake_corner_fog(self) -> None: ...
```

**Test guidance:** corner height grid must equal `get_corner_height` for a sample of
indices; `corner_fog[cx][cy]` strictly decreases as `corner_height` increases; grids
have shape `(w+1, h+1)`.

---

## Phase P2 — Per-corner slope shading math

**Goal:** Replace the tile-center gradient with a per-vertex gradient/normal evaluated
on the baked corner-height field, so shading is continuous across shared corners.

**Files:**
- Modify: `world/tile_map.py` (corner normal + corner brightness)
- Modify: `render/lighting_system.py` (vectorized `compute_all_corner_shading`)
- Create: `tests/test_phase7_p2_corner_shading.py`

**Changes:**
1. Add `compute_corner_normal(cx, cy) -> (gx, gy, 1.0)` as a central difference of
   the baked `corner_height` grid (with edge clamping, matching the existing
   OOB-as-zero convention at the boundary).
2. Add `compute_corner_brightness(cx, cy, light_dir, strength)` that reuses the
   existing sign convention from `compute_slope_shading`, but is evaluated at the
   corner rather than the tile center.
3. `LightingSystem.compute_all_corner_shading(tile_map, light_x, light_y, light_z)`
   returns `(brightness_grid, normal_grid)` of shape `(w+1, h+1)` (NumPy).

**Key interfaces after P2:**
```python
def compute_corner_normal(self, cx: int, cy: int) -> tuple[float, float, float]: ...
def compute_corner_brightness(
    self, cx: int, cy: int,
    light_dir: tuple[float, float, float], strength: float,
) -> float: ...
```

**Test guidance:** on a uniform map, every corner brightness equals 1.0; on a linear
ramp, corner brightness is constant along lines perpendicular to the light; on two
adjacent tiles, the shared corner yields the **same** brightness from either tile
(continuity check).

---

## Phase P3 — Software Gouraud triangle rasterizer

**Goal:** A reusable, correct, deterministic triangle fill that interpolates RGB across
the triangle in pygame.

**Files:**
- Create: `render/gouraud.py`
- Create: `tests/test_phase7_p3_gouraud.py`

**Key interface:**
```python
def fill_triangle(
    surface: pygame.Surface,
    p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float],
    c0: tuple[int, int, int], c1: tuple[int, int, int], c2: tuple[int, int, int],
) -> None:
    """Scanline-fill `surface` with Gouraud-interpolated vertex colors."""
```

**Changes:**
1. Sort vertices by screen Y; split into a flat-bottom and flat-top triangle.
2. Interpolate edge colors and per-scanline horizontal colors; write with
   `surface.set_at` (correct) and later optimize with a per-tile scratch `Surface`
   plus `pygame.surfarray` if profiling demands it.
3. Accept integer screen coordinates; caller handles sub-pixel snapping.

**Test guidance (deterministic):**
- Flat-top triangle with all three colors equal → fills a solid region.
- A triangle with corner colors that differ must have strictly >1 distinct color in
  the interior (proves interpolation, not flat fill).
- The 1-px degenerate triangle (two coincident vertices) must not raise.

---

## Phase P4 — Integrate the triangular path into `TileRenderer`

**Goal:** Drive terrain rendering from per-corner grids and the Gouraud rasterizer,
with continuity across tile edges.

**Files:**
- Modify: `render/tile_renderer.py` (draw path + per-vertex attribute fetch)
- Create: `tests/test_phase7_p4_render_integration.py`

**Changes:**
1. Replace the 4 on-the-fly `get_corner_height` calls with reads from
   `tile_map.corner_height`.
2. Compute each vertex's screen position from `camera.world_to_screen(..., elevation=h * Z_SCALE)`
   exactly as today (keeps geometry identical).
3. Per-vertex color = `biome_base_color * corner_brightness * corner_ao`, then apply
   per-vertex fog (distance-attenuated `fog_alpha` modulated by `corner_fog`) and
   per-vertex rim (using `compute_corner_normal`).
4. Split each tile into two triangles across the `NW→SE` diagonal and call
   `clear`-then-`fill_triangle`. Draw back-to-front using the existing depth sort.
5. `terrain_style` flag (P5) chooses:
   - `"flat"`: true Gouraud triangles with biome base color.
   - `"textured"`: keep the biome sprite; replace the flat tint overlay with a
     `TILE_SUBDIVISIONS × TILE_SUBDIVISIONS` sub-tile tint grid bilinearly sampled
     from the 4 corner values (all lighting terms), then blit the tinted tile.

**Test guidance:** a headless render (SDL dummy) of a small tile map with the `"flat"`
style must not crash and must produce a non-uniform surface; verify two adjacent tiles
share the same color at the shared edge by sampling pixels along the boundary.

---

## Phase P5 — Presets, LOD, and performance knobs

**Goal:** Make the new shading configurable and keep the frame budget flat.

**Files:**
- Modify: `config/constants.py` (extend `SHADING_PRESETS`)
- Modify: `render/tile_renderer.py` (read knobs)
- Modify: `render/lighting_system.py` (recompute-on-change)

**Changes:**
1. Add to every preset: `terrain_style` (`"textured" | "flat"`) and
   `terrain_subdiv` (2–4). Repurpose `TILE_SUBDIVISIONS = 2` as the default
   `terrain_subdiv`.
2. Cache the per-frame light vector and full-corner `brightness/normal` grids; only
   recompute when `sun_direction`, season, or weather `light_level` changes.
3. Optional LOD: beyond `FOG_CULL_DISTANCE * 0.66`, fall back to the flat single-tile
   shading (the old path) to save time; below it use Gouraud.

**Test guidance:** preset toggles gate correctly; recompute is skipped when the light
vector is unchanged across two `render()` calls (assert via a call counter).

---

## Phase P6 — Tests and headless verification

**Files:**
- Create: `tests/test_phase7_p6_integration.py`

**Coverage:**
- Flat terrain → uniform corner brightness/AO/fog, uniform rendered output.
- Concave corner → `corner_ao < 1.0` and the rendered triangle shows the darkening.
- Shared-edge continuity for brightness, AO, and fog.
- `"stylized" | "realistic" | "performance"` presets each render headless without
  raising under `SDL_VIDEODRIVER=dummy`.
- Regression: `compute_slope_shading` still matches legacy output when `light_dir`
  is omitted.

**Verification note (no browser available):** this is a Pygame **desktop** app, so the
browser-verification rule does not apply. Closest substitute = headless pytest
(which is how the existing 683-test suite runs) plus a headless composite render
asserting the Gouraud output is non-uniform and crash-free. Manual visual check
requires `python main.py --seed 42` on a display; that remains for a human playtest
and is called out in the rollout checklist.

---

## Performance notes

- **Bake cost:** `corner_height`/`corner_fog`/`corner_brightness` are one-time
  `O((w+1)(h+1))` NumPy passes — negligible at world-gen for a 512×512 map.
- **Render cost:** per visible tile, 4 array reads + color solve for 4 vertices and
  1–2 triangle fills (or `terrain_subdiv²` flat sub-tints in textured mode). No
  12-tile kernel scan per frame anymore — that is a **net win** versus today's
  per-tile `get_corner_height ×4`.
- **Gouraud rasterizer:** pure-Python scanline is the risk point. Mitigation: tiny
  per-tile scratch surface, integer-coordinate snapping, and the P5 LOD fallback.
  If profiling shows it is too slow, drop to `terrain_subdiv` sub-tint in textured
  mode (the recommended default).

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Pure-Python Gouraud too slow at 60 FPS | Default preset uses `terrain_style="textured"` (sub-tile tint grid, blit-based); LOD fallback past 66% fog cull |
| Signed shading/normal mismatch produces inverted slopes | Reuse the exact legacy dot-product convention; P0 regression test locks legacy values |
| Boundary corners (index 0 / w) behave differently than interior | Bake uses the same OOB-as-zero kernel; central differences clamp at edges; dedicated boundary tests |
| Terrain sprite flat-blit vs triangle geometry look inconsistent across styles | Make `terrain_style` explicit in presets; default keeps sprites so current look is preserved |
| `get_corner_height` consumers break when it becomes a cached lookup | Keep on-demand fallback; keep all existing smooth-elevation/corner tests green unmodified |

---

## Rollout checklist

1. [ ] P0: fix `compute_slope_shading` contract + regression test
2. [ ] P1: bake `corner_height` + `corner_fog`; wire into `world_gen.generate`
3. [ ] P2: corner normal + corner brightness math + NumPy grid
4. [ ] P3: `render/gouraud.py` fill outside-in (correct, then fast)
5. [ ] P4: triangular render path + textured sub-tile path behind flag
6. [ ] P5: preset knobs, recompute-on-change, LOD fallback
7. [ ] P6: full test suite (`python -m pytest -q`) + headless render smoke
8. [ ] Manual visual playtest: `python main.py --seed 42` across all three presets