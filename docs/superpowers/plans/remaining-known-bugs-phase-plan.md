# Phase Plan — Remaining Known Bugs

Derived from the README "Known bugs & issues" ledger (25 items) after a
per-bug code trace against the current tree. **12 were found effectively
resolved** (Report 1–11 fixes); **13 remained**. This plan sequenced those 13;
**13 are now resolved** (Phases 0–5); **0 remain**.

Resolved-at-a-glance (not re-worked here): success_rate inversion (actions),
campfire-cook crash (input), shadowed inventory use (input), weapon
`attack_bonus` applied (combat), double smelt XP (metallurgy), gathered+cooked
spoilage (actions/input), weather clear-lock (weather), structure `max_hp`
persistence (save), 3-of-6-biome seasonal render, ranged `reset_special`,
camera zoom, `wildcard_points` save. (See the audit for line-level evidence.)

---

## No remaining bugs

Resolved by earlier phases: B5 (melee attack, Phase 4), B4 (building placement,
Phase 5), B6 (merchant stock, Phase 3), B7 (water, Phase 1), B11/B15/B21 (wiring,
Phase 2), B12/B13/B22 (data, Phase 1), B23/B24/B25 (hygiene, Phase 0).

Effort scale: **S** < 1h, **M** ~0.5 day, **L** ~1–2 days (includes design + tests).

---

## Phasing rationale

- Group by subsystem to minimize churn and keep each phase independently testable.
- Order by risk: hygiene → data correctness → wiring correctness → gameplay loops.
- The three gameplay loops (economy / combat / construction) are **independent
  subsystems** with no shared state, so they are candidates for parallel
  implementation once their designs are locked.

---

## Phase 0 — Hygiene & documentation (S, zero risk)

Unblocks clean docs; no behavioral change.

- **B24** `Game.get_snapshot()` — remove the method (save system builds its own
  snapshot; all other `get_snapshot` belong to other objects). If a consumer is
  desired later, wire it then.
- **B25** Panel shortcut hints — correct rendered hint text to match wired keys
  (`I` close inventory; `Q` close crafting; `H`? verify crafting bind).
- **B23** Stale `.pyc` — clear `skills/__pycache__` package-level leftovers.
- **B22** `recipes.json` docstring — reconcile with the Phase 1 B12 decision.

Verify: `tools/check_init_hygiene.py`, `python -m pytest -q`.

---

## Phase 1 — Data correctness (M)

- **B7** Water unharvestable — make `ResourceNode.is_depleted` treat
  `depletion_count <= 0` as "never depleted" (preserves the `-1 = infinite`
  convention) **or** flip the water record to a positive `depletion_count`.
  Prefer the `is_depleted` fix so the convention is honored everywhere. **S**
- **B12** Missing `data/recipes.json` — **Decision A** (see below): either create
  a minimal general-crafting table, or drop general crafting and remove the dead
  load path (and B22 docstring). **M**
- **B13** Cooking skill math — **Decision B** (see below): wire
  `CookingSkill` into `cook()` (e.g. success-rate modifier) **or** leave as a
  documented v1 limitation. **M**

Verify: `tools/validate_phase3_data.py`, water-harvest test, cooking test.

---

## Phase 2 — System wiring correctness (M)

- **B15** `NPCFlows` duplicate — instantiate once (bootstrap) and drop the
  `Game.__init__` / router / panel_dispatcher instantiations (keep the one the
  router/dispatcher already receive). **S**
- **B21** `_is_near_monster` stub — implement a real proximity check over
  `game.combat_system.monsters` (the P3-S3/P3-S4 scaffolding the comment
  references is present). **M**
- **B11** Quest craft tracking — wire the quest system into `craft()`. Lowest
  risk: pass `quest_system` into `cook()`/`craft()` as an optional arg (matches
  the existing `skill_manager`/`structures` pattern) rather than attaching
  `self.game`. **M**

  Companion fix surfaced by B11's test: `craft()` passed the `Recipe` object
  (not `recipe_id`) to `validate_recipe`, which does `self.recipes.get(...)` —
  `Recipe` is a `@dataclass` (unhashable), so `craft()` raised `TypeError` and
  its quest tracking was unreachable. Now passes `recipe_id` (matching
  `validate_recipe`'s own contract and the crafting-panel call site).

Verify: NPCFlows singleton test, spawn-avoidance test, craft→`record_craft`
discriminating test. Full suite green.

---

## Phase 3 — Economy loop (L, needs design)

- **B6** Merchant stock — `generate_merchant_inventory` existed but was never
  called, so every `MerchantNPC` kept an empty inventory and every buy failed
  with "No stock remaining". Fix: populate `merchant.inventory` in `open_trade`
  (biome-filtered + intelligence bonus), guarded by "already populated" so a
  merchant that already sold stock is not refilled on every reopen. The panel
  display (`get_trade_items_for_merchant`, from `trade_items.json`) already
  shares the same biome filter, so definitions and actual stock now correspond.
  **M**

Verify: integration test against real `data/trade_items.json` — buy reduces
stock + gold, sell increases stock + gold, restock refills to `max_stock`,
reopen does not refill consumed stock; full suite green.

---

## Phase 4 — Combat loop (L, needs design) — RESOLVED

- **B5** Player melee attack — **RESOLVED (2026-08-23)**. Bound `J` to
  `combat_system.player_attack()` in `input/router.py` (`_handle_attack`, gated
  to `state == PLAYING`). `player_attack` already ran the full loop (damage,
  death, counter-attack). Also:
  - Fixed a latent crash in the death path: `_monster_died()` deselects the
    target, then the caller read `self.selected_target.name` → `NoneType`.
    Now captures `slain` first.
  - Added `CombatSystem.auto_lock_target()` so `J` locks the nearest alive
    monster when none is targeted (usable without a prior click).
  - **Rebound the skill panel from `J` to `TAB`** (was `input_manager.K_j`);
    `J` is now attack. Updated the skill-panel hint to "Press ESC or Tab to
    close" (`input/input_manager.py`, `ui/skill_panel.py`).

Verify: `tests/test_b5_player_attack.py` (15 tests) — attack hits target +
cooldown gates spam + monster counter-attacks + death message; `J` triggers the
attack through the router while PLAYING and is a no-op elsewhere; `TAB` opens
the skill panel and `J` no longer does; full suite green (633 → 635).

---

## Phase 5 — Construction loop (L, needs design) — RESOLVED

- **B4** Building placement — **RESOLVED (2026-08-23)**. Implemented as a
  `build_mode` flag (a PLAYING sub-state, not a new `GameState`), per locked
  decision #2:
  - `input/router.py` — left-click in `build_mode` calls
    `building_system.place_structure` (validate → consume → XP → place);
    right-click / ESC cancels; invalid placement reports the reason and stays
    in mode; hotbar clicks still use items; opening the building panel resets
    `build_mode`. `_handle_hotbar_click` was factored out so the hotbar path
    is shared between the normal and placement flows.
  - `input/panel_dispatcher.py` — selecting a structure closes the palette and
    enters `build_mode` (`game.build_mode = True`, `game._building_pending_id`).
  - `core/game.py` — added `build_mode` / `_building_pending_id` /
    `_build_cursor` state; tracks the cursor in `_handle_mouse_move`; renders a
    translucent ghost marker under the cursor in `render_game`.
  - `building/building_system.py` — `place_structure` now actually grants
    construction XP via `skill_manager.add_xp("crafting", xp_gained)` (it
    computed `xp_gained` before but never applied it).

Verify: `tests/test_b4_building_placement.py` (11 tests) — place flow
(materials consumed, XP granted, structure placed with calculated HP);
select → `build_mode` + palette closes; right-click / ESC cancel; invalid
placement stays in mode and reports the reason; hotbar click uses the item
instead of placing; ghost render is crash-free. Full suite green.

---

## Locked decisions (confirmed 2026-08-23)

1. **B5 attack input** — dedicated key **`J`** attacks the current target;
   **monster counter-attacks enabled** (their AI already supports it).
2. **B4 placement** — implement as a **`build_mode` flag** (not a new
   `GameState`). Rationale: a `BUILD` enum value would force edits to ~15
   `state == PLAYING` gates in `Game.update()` plus render/event routing and
   risks freezing the world; a flag keeps `state == PLAYING` (world unchanged)
   and only changes input routing + rendering. UX: open building panel → select
   a structure enters `build_mode` (ghost preview follows cursor); **left-click
   places** at the tile (hotbar clicks still use items), **right-click / ESC
   cancels** placement; invalid placement shows the reason and stays in mode.
3. **B6 stock** — auto-populate on trade-open via `generate_merchant_inventory`.
4. **B12 recipes.json** — create a **small general-crafting table** (~4–6
   recipes). Design it with future data restructuring in mind (see below).
5. **B13 cooking** — leave `CookingSkill` as a documented v1 limitation
   (lowest risk); the cook engine already lives in `CraftingSystem.cook`.
6. **B24 get_snapshot** — remove (redundant with the save system's own
   snapshot).

### B12 data-structure forward note

Items/structures/recipes handling is acknowledged as a messy v1 surface. The
new `data/recipes.json` general-crafting table should be written so it can
later be folded into a unified recipe model without churn:

- Use the same `_description`/`_note` metadata envelope as `data/*.json`.
- One recipe record: `{ recipe_id, name, input: [{item_id, qty}], output:
  {item_id, qty}, xp, skill?, requires_structure?, season? }`.
- Keep it loadable through the existing `RecipeRegistry` path so no call sites
  change now, but structure the JSON so a future unified registry can consume
  it directly.

**Step 2 — done (2026-08-24).** Collapsed the drift that remained across the
five `recipes.json` sources into one canonical envelope, without touching any
call sites (all five feed one `Recipe` dataclass through
`RecipeRegistry._load_from_dir` → `Recipe.from_dict`):

- Standardized the id key to `recipe_id` everywhere — `data/`, `metallurgy/`
  (dropped redundant `id`), `cooking/`, `construction/` (renamed `id`→`recipe_id`);
  `intelligence/` already used `recipe_id`.
- Added `inventory/recipe.py::validate_recipe_dict` + `CANONICAL_RECIPE_KEYS`
  (shared validator). It enforces the canonical keys/types and tolerates
  source-specific extras (metallurgy ore/fuel fields, construction
  steps/skill_requirements/blueprint_id/enchantment_slots) that `from_dict`
  already ignores.
- `RecipeRegistry._load_from_dir` now skips+logs malformed entries instead of
  silently producing a wrong set.
- Guardrail test asserts every *input* reference resolves in `items.json`
  (output-only "future product" refs like `polished_obsidian` are allowed).
- Verify: `tests/test_b12_general_recipes.py` (14). Full suite 654 passed.

---

## Suggested rollout

- Run Phases 0–2 sequentially (fast, low-risk, build confidence).
- Lock designs for Phase 3–5 via decisions 1–6 above, then implement the three
  loops in parallel (independent subsystems — good fan-out for subagents).
- Every phase ends with discriminating tests + a full `pytest -q` run, matching
  the repo's TDD convention.
