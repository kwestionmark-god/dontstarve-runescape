# Phase — Depleted Resource Sprites & Tree Regrowth Phases

**Created:** 2026-08-18  
**Scope:** Visual states for depleted resource nodes (all harvestable resources) and multi-stage regrowth sprites for trees, wired into `SpriteRenderer` and generated via the existing procedural pipeline.  
**Out of scope:** Persisting depleted nodes across save/load (still the known v1 limitation); new resource types; seasonal tint overhaul; animation frames beyond discrete growth stages; particle harvest FX.  
**Prerequisite:** Current `ResourceNode` + `Tile.regrow_timer` logic; `tools/generate_sprites.py`; `render/sprite_renderer.py` resource path. Prefer completing Pass 0–2 of the granular bugfix plan first so the suite is stable, but this phase does not depend on soft-death or save gold.  
**Success criteria:** Every depletable resource shows a clear depleted visual instead of vanishing or a generic grey circle; trees progress through distinct regrowth stages while the timer runs; full mature sprite returns when regrowth completes; placeholders remain only as fallback; existing tests stay green and new renderer/unit coverage is added.

---

## Design goals

1. **Readability at a glance** — Players should immediately see that a node is gone (stump / rubble / bare patch) vs still harvestable.
2. **Tree identity during recovery** — Oaks, pines, elder wood, etc. should not all look identical while regrowing; stages should still read as “that tree type recovering.”
3. **Minimal data churn** — Prefer a predictable sprite-key naming convention over exploding `resources.json` with many new fields. Optional override fields are fine for special cases.
4. **Procedural consistency** — All new art stays in `tools/generate_sprites.py` so assets remain regenerable and style-matched.
5. **Graceful fallback** — Missing stage sprite → previous stage or mature sprite → existing geometric placeholder (never hard crash).

---

## Current state (baseline)

| Area | Behaviour today |
|------|-----------------|
| `ResourceNode` | `current_depletions`, `depletion_count`, `is_depleted`, `regrow_time`, single `sprite_key` |
| `Tile` | `depleted` flag + `regrow_timer` countdown; on 0 calls `resource_node.start_regrow()` and clears `depleted` |
| `SpriteRenderer.render_resource` | Loads `node.sprite_key`; if sprite exists **and** not depleted → draw full sprite; else draws a small grey “stump/rubble” circle placeholder |
| Assets | Mature trees (`trees/oak.png`, …), `trees/dead_tree.png` already generated; no per-resource depleted keys; no sapling/young stages |
| Infinite nodes | `water_source` has `depletion_count: -1` — never depleted; no depleted sprite required |

**Known related bug (document, optional fix in this phase):**  
`ResourceNode.start_regrow()` currently sets `current_depletions = self.depletion_count`, which leaves `is_depleted == True` after the timer fires. Tile sets `depleted = False`, so renderer and node disagree. Correct behaviour should reset `current_depletions = 0` (or equivalent) when regrowth completes. Include a one-line fix in Pass 2 if touching that path.

---

## Resource inventory (applicable targets)

### Trees / wood (regrowth stages + depleted)

| `resource_id` | Mature sprite_key | Notes |
|---------------|-------------------|--------|
| `oak_tree` | `trees/oak` | Tier 1, primary tree |
| `elder_wood` | `trees/elder_wood` | Tier 4 |
| `berry_bush` | `trees/berry_bush` | Bush; depleted = bare bush, regrowth optional simpler 2-stage |

Asset-only trees already generated but not yet in `resources.json` (future-proof the generator):  
`birch`, `maple`, `pine`, `spruce`, `willow`. Generate depleted + growth stages for these too so later content drops in cleanly.

### Rocks / ores (depleted only — rubble / cracked vein)

All `rocks/*` keys:  
`iron`, `copper`, `gold`, `stone`, `gem`, `rare`, `tin`, `void_crystal`, `obsidian`, `mithril`, `amber`, `moonstone`, `ghost_iron`, `star_metal`, `ancient_rune`, `celestial_crystal`.

Shared fallback: `rocks/rubble.png` if a per-ore depleted sprite is missing.

### World / plant / other (depleted only)

| Family | Examples | Depleted visual intent |
|--------|----------|-------------------------|
| Soft plant | `herb`, `fiber_plant`, `grass_patch`, `wheat_field`, `toxic_reed` | Cut / bare patch, short stems |
| Bush-like | `cactus`, `silk_nest` | Empty / desiccated form |
| Coastal | `driftwood`, `shell_beach`, `fish_spot`, `salt_deposit`, `salt_crystal` | Scoured shore / empty pool marker |
| Ground | `peat_mound`, `sand_deposit` | Flattened mound / depression |
| Rare / special | `dragonbone`, `void_essence`, `phoenix_feather` | Faded residual or cracked remnant |

**Exclude:** `water_source` (infinite).

---

## Naming convention (canonical)

Adopt a strict suffix scheme so the renderer can derive keys without JSON changes:

```
{base_sprite_key}.png                 → mature / full
{base_sprite_key}_depleted.png        → fully depleted
{base_sprite_key}_sapling.png         → trees only, early regrowth (~0–40% progress)
{base_sprite_key}_young.png           → trees only, mid regrowth (~40–80% progress)
```

Examples:
- `trees/oak` → `trees/oak_depleted.png`, `trees/oak_sapling.png`, `trees/oak_young.png`
- `rocks/iron` → `rocks/iron_depleted.png`
- `world/grass` → `world/grass_depleted.png`

Shared fallbacks (always generated):
- `trees/stump.png` — generic tree depleted if per-type missing
- `trees/sapling_generic.png` / `trees/young_generic.png` — optional shared growth if per-type missing
- `rocks/rubble.png` — generic rock depleted
- `world/depleted_patch.png` — generic plant/soft resource depleted

Optional JSON overrides (only if a resource needs a non-derivable key later):

```json
"sprite_key_depleted": "trees/stump",
"sprite_key_sapling": "trees/oak_sapling",
"sprite_key_young": "trees/oak_young"
```

v1 of this phase does **not** require adding these fields; convention-first is enough.

---

## Growth progress mapping (trees)

While `tile.regrow_timer > 0` and the node is a tree:

```
progress = 1.0 - (regrow_timer / regrow_time)   # 0 just depleted → 1 just about to finish

if progress < 0.40:   sapling sprite
elif progress < 0.80: young sprite
else:                 young sprite still, or optional “almost mature” if we add a 4th stage later
```

When timer hits 0 and depletions reset → mature sprite.

Berry bushes can use a simpler 2-stage map (depleted → young/regrowing → mature) if full 3 stages look redundant at 16×16.

Non-trees do **not** show intermediate growth stages in this phase (instant visual flip from depleted → mature on timer end). That keeps scope bounded; a later “plant regrowth phases” ticket can mirror the tree approach.

---

## Passes

### Pass 0 — Spec lock & inventory

**Goal:** Freeze the list of keys and stage counts so generation and renderer work from one source of truth.

- Add a short table (this document + optional `docs/superpowers/plans/asset-depleted-regrowth-checklist.md` if desired) listing every `resource_id` → required PNG paths.
- Decide once: per-tree unique stages vs shared stump + unique canopy stages. **Recommendation:** unique stump/sapling/young per tree type that already has a mature sprite; shared fallbacks only when missing.
- Confirm `berry_bush` stage count (2 vs 3).
- Note the `start_regrow` reset bug for Pass 2.

**Exit criteria:** Checklist complete; no ambiguity about which files will exist.

---

### Pass 1 — Procedural sprite generation

**Goal:** Extend `tools/generate_sprites.py` so a clean re-run produces every required depleted and tree-stage asset.

#### 1.1 Trees (`generate_tree_sprites`)

For each mature tree already drawn (`oak`, `pine`, `maple`, `spruce`, `willow`, `birch`, `elder_wood`):

| Stage | Visual intent (pixel-art, same palette family) |
|-------|-----------------------------------------------|
| `_depleted` | Stump / cut trunk, roots, no canopy (or sparse dead branches). Can reuse / refine existing `dead_tree` motifs. |
| `_sapling` | Short stem + small leaf cluster or needle tuft; clearly “growing.” |
| `_young` | Half-height trunk, partial canopy; reads as immature version of the mature tree. |

Also generate:
- `trees/stump.png` (shared fallback)
- `berry_bush_depleted.png` (bare twigs / empty bush)
- Optional `berry_bush_young.png` if using 2–3 stage bush regrowth

#### 1.2 Rocks (`generate_rock_sprites`)

For each rock/ore:
- `_depleted`: lower profile, cracks, missing ore colour accent, greyed rubble silhouette.
- Shared `rocks/rubble.png`.

#### 1.3 World resources (`generate_world_sprites` or equivalent)

For each non-infinite world resource:
- `_depleted`: cut grass, empty herb stems, scoured sand, dry peat, empty fish ripple mark, etc.
- Shared `world/depleted_patch.png`.

#### 1.4 Generator hygiene

- Keep sizes consistent (`TREE_SIZE` 32, `ROCK_SIZE` / world 16).
- Print a summary line: “Generated N depleted + M growth-stage sprites.”
- Do not delete mature sprites; only add files.
- Update `assets/sprites/README.md` structure section to document the new suffixes and fallbacks.

**Exit criteria:** `python tools/generate_sprites.py` succeeds; all listed paths exist on disk; visual spot-check of a few keys (oak stages, iron_depleted, grass_depleted) looks intentional, not broken.

---

### Pass 2 — Data model & regrowth correctness (small)

**Goal:** Renderer can query growth progress; regrowth actually restores harvestability.

#### 2.1 Fix `start_regrow`

In `world/resource_node.py`:

```python
def start_regrow(self) -> None:
    """Reset harvest state after the regrowth timer completes."""
    self.current_depletions = 0
```

(Remove the line that set `current_depletions = depletion_count`.)

#### 2.2 Optional helper on `ResourceNode` or renderer-side pure function

```python
def growth_stage(self, regrow_timer: float) -> str:
    """Return 'depleted' | 'sapling' | 'young' | 'mature' for tree rendering."""
```

Prefer keeping stage math in the renderer (or a tiny `render/resource_visuals.py`) so `ResourceNode` stays data-focused. Either is fine if documented.

#### 2.3 Family detection

Reuse / extend existing `_resource_family(node)` in `SpriteRenderer` so trees are reliably classified (sprite_key prefix `trees/` or known tree ids).

**Exit criteria:** Unit test: deplete oak → timer counts down → after completion `is_depleted is False` and `current_depletions == 0`. Existing harvest tests still pass.

---

### Pass 3 — Renderer selection logic

**Goal:** `render_resource` chooses the correct surface for every state.

#### 3.1 Key resolution algorithm

```
base = node.sprite_key

if node.is_depleted or tile.depleted:
    if family == "tree" and regrow_timer > 0:
        stage = progress_to_stage(regrow_timer, node.regrow_time)  # sapling | young
        key = f"{base}_{stage}"
        sprite = load(key) or load(f"trees/{stage}_generic") or load(f"{base}_depleted") or load("trees/stump")
    else:
        key = f"{base}_depleted"
        sprite = load(key) or family_fallback(family)  # stump / rubble / depleted_patch
else:
    key = base  # mature
    sprite = load(key)
```

If still `None`, fall through to today’s geometric placeholder (but depleted branch should rarely hit this after Pass 1).

#### 3.2 Signature / call-site

`render_resource` already receives `tile_x, tile_y`. Prefer reading `tile_map.tiles[tile_x][tile_y].regrow_timer` (and `.depleted`) when `tile_map` is set, rather than only trusting `node.is_depleted`. That keeps timer-driven stages accurate.

#### 3.3 Zoom / fog / seasonal tint

Apply the same zoom, fog overlay, and seasonal tint path used for mature sprites to stage sprites so they do not look “flat” relative to the world.

#### 3.4 Partial depletion (optional stretch)

For nodes with `depletion_count > 1`, intermediate harvests could slightly tint or scale the mature sprite. **Out of scope for v1** unless it is trivial; full stages only kick in after full depletion.

**Exit criteria:** Manual or automated visual test: chop oak → stump/depleted appears → over time sapling → young → mature; mine iron → rubble; cut grass → bare patch; water never changes.

---

### Pass 4 — Tests

**Goal:** Lock behaviour so modularization and future content do not regress visuals or regrowth.

| Test | Asserts |
|------|---------|
| `test_resource_node_start_regrow_resets_depletions` | `current_depletions == 0` after `start_regrow` |
| `test_tile_regrow_completes_and_clears_depleted` | After timer expiry, node harvestable again |
| `test_sprite_key_resolution_depleted` | Given depleted oak, resolver returns a key ending in `_depleted` or stump fallback |
| `test_sprite_key_resolution_tree_stages` | At 20% / 60% / 100% progress, stages are sapling / young / mature |
| `test_infinite_water_never_depleted_sprite` | water_source path always mature key |
| Smoke: existing renderer / seasonal tests still pass | No regressions |

Prefer pure functions for key resolution so tests do not need a full pygame display.

**Exit criteria:** New tests green; full suite no new failures attributable to this phase.

---

### Pass 5 — Documentation & polish

- Update `assets/sprites/README.md` with suffix convention, fallback list, and regeneration command.
- One-paragraph note in this plan’s “Done when” or a short changelog entry under `docs/` if the project keeps one.
- Optional: comment in `sprite_renderer.py` pointing at the naming convention so future contributors do not invent parallel schemes.

**Exit criteria:** Docs match disk and code.

---

## Implementation order (recommended)

1. Pass 0 (checklist) — minutes  
2. Pass 1 (generate all PNGs) — main art work  
3. Pass 2 (fix `start_regrow` + helpers) — small, unblocks correct mature return  
4. Pass 3 (renderer) — player-visible change  
5. Pass 4 (tests)  
6. Pass 5 (docs)

Each pass should leave the game runnable; Pass 1 alone is safe (unused files on disk).

---

## Effort & risk notes

| Risk | Mitigation |
|------|------------|
| Too many unique sprites to maintain | Shared fallbacks + generator functions parameterized by palette |
| 16×16 stages hard to distinguish | Prefer silhouette change (height, canopy radius) over subtle colour shifts |
| Renderer misses tile timer | Always prefer `tile.regrow_timer` when `tile_map` available |
| Save/load still resets depleted nodes | Unchanged v1 limitation; document only. Future “resource overlay” phase can persist coordinates + timers and will reuse these sprites automatically |
| `start_regrow` bug masks mature return | Fixed in Pass 2 before relying on visual round-trip |

---

## Done when

- [ ] Every depletable resource in `data/resources.json` has a depleted sprite (or intentional shared fallback) on disk  
- [ ] Every tree with a mature sprite has `_depleted`, `_sapling`, and `_young` (or documented 2-stage exception for berry bush)  
- [ ] `SpriteRenderer` selects stage/depleted/mature correctly from node + tile timer  
- [ ] `start_regrow` resets harvestability  
- [ ] Tests cover resolution + regrow reset  
- [ ] `generate_sprites.py` + README updated  
- [ ] Suite green relative to pre-phase baseline  

---

## Follow-ups (explicitly not this phase)

- Persist depleted node coordinates + remaining `regrow_timer` in save snapshots (v2 resource overlay).  
- Intermediate “damaged but not depleted” visuals for multi-hit nodes.  
- Animated growth or harvest chop frames.  
- Plant/bush multi-stage regrowth parity with trees.  
- Hooking asset-only trees (`birch`, `pine`, …) into `resources.json` as real harvestable nodes.
