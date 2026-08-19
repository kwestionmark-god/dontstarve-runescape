# Phase Bugfix — Granular Stability & Correctness Plan

**Created:** 2026-08-18  
**Scope:** Fix real bugs, wiring gaps, persistence holes, test failures, and incomplete soft-death / init-order issues discovered by full codebase trace.  
**Out of scope:** New features, Phase 5 content, visual polish beyond what is required for correctness, AdvancedCraftingSystem.  
**Prerequisite:** Phase 3.5 modularization largely done; Phase 4 seasons/weather/tier gating largely done.  
**Success criteria:** All current pytest suites green; soft death fully correct; save/load round-trips critical state; bootstrap init order correct; no silent `None` subsystem wiring.

---

## Executive summary of findings

A full pass over `core/`, `combat/`, `save_system`, `bootstrap`, `input/`, `npc/`, `world/`, and the test suite (514 passed / **11 failed**) surfaced the following categories:

| Category | Severity | Count (approx.) |
|----------|----------|-----------------|
| Bootstrap / init-order wiring | Critical | 3–4 |
| Soft death incomplete | Critical | 2–3 |
| Save/load persistence gaps | High | 5–7 |
| Dependency / import (tests + world_gen) | High | 1 (+ cascading tests) |
| Stubs that leak into runtime | Medium | 4–6 |
| Dead / duplicate code | Low–Medium | 3–4 |
| Test bitrot after modularization | Medium | 4 |

This plan is ordered so each pass is independently shippable and leaves the suite greener than before.

---

## Pass 0 — Environment & dependency hygiene (do first)

**Goal:** Unblock world generation imports and the 7+ tests that fail solely because of missing deps / wrong import paths.

### 0.1 Install / declare the `noise` dependency

- **Symptom:** `world/world_gen.py` does `import noise` → `ModuleNotFoundError`. Cascades into:
  - `test_seasonal_resource_gating` (4 failures)
  - `test_particle_system` bootstrap integration
  - `test_seasonal_renderer` bootstrap integration
  - `test_sprite_seasonal_tint` bootstrap wiring
  - `test_keyboard_shortcuts::test_game_has_panel_dispatcher`
- **Fix:**
  - Add `noise` (PyPI package, often `noise` or `opensimplex` — verify which API `world_gen.py` expects) to project requirements / install in the environment.
  - If the project intentionally avoids external noise libs, replace with an internal Perlin/simplex implementation under `world/` and update the import.
- **Verify:** `python -c "from world.world_gen import generate"` succeeds; the four seasonal gating tests that import `_place_resources` pass.

### 0.2 Fix modularization-broken test patches

- **Symptom:** `test_npc_dialogue_fix.py` patches `core.game.Game.__init__` but `core` package no longer re-exports `game` the way the test assumes → `AttributeError: module 'core' has no attribute 'game'`.
- **Fix:** Update patches to the real module path (`patch("core.game.Game.__init__", ...)` after ensuring `from core import game` or use `patch.object` on the imported class). Prefer importing `Game` inside the test and patching the class object directly.
- **Verify:** All three `TestNPCDialogueFix` cases pass.

### 0.3 Requirements / README note

- Document the runtime dependency (`noise` or replacement) so CI and new clones do not regress.

**Exit criteria for Pass 0:** 0 import-related failures; full suite runnable without `ModuleNotFoundError`.

---

## Pass 1 — Bootstrap init-order & HUD / renderer wiring (Critical)

**Goal:** Every subsystem that HUD, panels, and combat need is non-`None` after `Bootstrap.initialize()` completes. No silent `None` refs.

### 1.1 HUD constructed before faction / NPC systems

- **Location:** `core/bootstrap.py` → `initialize()` order:
  1. `_build_hud()` (line ~47)
  2. … much later …
  3. `_build_npc_system()` / `_build_faction_system()`
- **Symptom:** `HUD.__init__` receives `faction_system=None`, `npc_system=None`. Faction status bar and NPC proximity alert never work until (if ever) something re-wires them. There are **no** `HUD.set_faction_system` / `set_npc_system` methods; values are only set in `__init__`.
- **Fix (choose one, prefer A):**
  - **A (recommended):** Move `_build_hud()` to after `_build_faction_system()` (and after final sprite renderer if possible), **or**
  - **B:** Add `HUD.set_faction_system` / `set_npc_system` / `set_sprite_renderer` and call them at the end of `initialize()` / in `_wire_phase4` or a new `_finalize_hud()`.
- **Also:** `_build_renderers()` runs late and **replaces** `self.game._sprite_renderer`. HUD and inventory panel still hold the early placeholder instance created in `Game.__init__`. Re-wire HUD + inventory panel to the final renderer after `_build_renderers()`.

### 1.2 Double / triple `NPCFlows` construction

- **Locations:**
  - `Game.__init__` → `self._npc_flows = NPCFlows(self)`
  - `Bootstrap._build_npc_flows()` → overwrites `self.game._npc_flows`
  - `InputRouter.__init__` → creates its **own** private `NPCFlows(game)`
- **Symptom:** Router may not share the same flow instance the rest of the game uses; state (open panels, session) can diverge.
- **Fix:** Single owner. Prefer Game/bootstrap as owner; InputRouter receives `game._npc_flows` by reference (or always reads `game._npc_flows`). Remove the local construct in `InputRouter`.

### 1.3 Autosave interval hardcoded

- **Location:** `core/game.py` `update()` — `if self._autosave_timer >= 300.0`
- **Config already has:** `AUTOSAVE_INTERVAL = 300.0`
- **Fix:** Import and use `AUTOSAVE_INTERVAL` from `config`.

### 1.4 `Game.__slots__` vs dynamic attrs

- `_autosave_timer` is not in `__slots__` and is created with `hasattr` / setattr. Either add it to `__slots__` and init to `0.0` in `__init__`, or keep the dynamic pattern deliberately. Prefer slots consistency.

**Exit criteria for Pass 1:**
- After `begin_world_gen` / `load_save` + `initialize()`, `game.hud.faction_system is not None`, `game.hud.npc_system is not None`, and HUD/inventory use the final `SpriteRenderer`.
- Single `NPCFlows` instance shared by router and game.
- Autosave uses config constant.
- Existing smoke + HUD tests still pass; add a small unit test that asserts post-bootstrap HUD refs are non-None.

---

## Pass 2 — Soft death completeness (Critical)

**Goal:** Soft death matches its docstring and is safe under all death sources (combat, starvation).

### 2.1 Missing `deselect_target()` on death

- **Location:** `combat/combat_system.py` → `_on_player_death`
- **Docstring claims:** “Clear monsters and deselect target”
- **Code:** Removes all monsters via `remove_monster` but **never** calls `self.deselect_target()`. If `selected_target` is not cleared inside `remove_monster`, a dangling reference remains.
- **Fix:** Explicitly call `self.deselect_target()` (and set `selected_target = None` if needed) at the start or end of `_on_player_death`.

### 2.2 Starvation death path does not trigger soft death

- **Location:** `survival/survival_system.py` → `take_damage` sets `is_dead = True` and returns `True`.
- **Combat path:** `_monster_counter_attack` checks the return value and calls `_on_player_death()`.
- **Starvation path:** `tick()` → `take_damage(hp_drain)` — return value is **ignored**. Player stays `is_dead=True` with no respawn, no XP penalty, no death_count increment, no save.
- **Fix options:**
  - **A:** Have `Game.update` (or SurvivalSystem callback) detect rising edge of `is_dead` and call into combat/soft-death handler (or a shared `SoftDeathHandler`).
  - **B:** Inject a death callback into SurvivalSystem at bootstrap time (`survival.on_death = combat._on_player_death` or a free function).
- Prefer a single shared soft-death entry point used by combat **and** survival.

### 2.3 Soft death should not leave the player in a permanent dead state mid-tick

- Ensure after soft death: `is_dead is False`, HP/hunger restored to configured fractions, player at spawn, monsters cleared, target deselected, `death_count` incremented, autosave triggered.
- Confirm `skill_manager.apply_xp_penalty` exists and behaves for total XP = 0 (no crash).

### 2.4 Tests

- Unit test: combat kill → soft death sequence assertions.
- Unit test: starve to 0 HP → same sequence (after wiring).
- Unit test: `death_count` increments and appears in save snapshot.

**Exit criteria for Pass 2:** Both combat and starvation deaths run the full soft-death sequence; no dangling `selected_target`; tests green.

---

## Pass 3 — Save / load persistence gaps (High)

**Goal:** Critical player-progress state survives a save → quit → load cycle. Document remaining intentional limitations.

### 3.1 Known intentional limitation (document, do not “fix” yet)

- **Depleted resource nodes are not persisted.** World is regenerated from seed; structures and fires are overlaid. This is the established v1 design.
- **Action:** Add a short comment in `save_system.py` / plan note so future work does not treat this as an accidental bug. Optional future ticket: “v2 resource overlay” (list of depleted node coordinates + timers).

### 3.2 Player gold not saved

- `Inventory.gold` exists (stub, always 0) but `_build_snapshot` / `load_into_game` never touch it.
- **Fix:** Serialize `inventory.gold` in snapshot; restore on load. Even while gold economy is incomplete, persistence must be correct so later features do not silently reset currency.

### 3.3 Player `recruited_npcs` list not saved

- `Player.recruited_npcs: list[str]` is runtime state.
- Save restores `recruitment_state.behaviors` and partially re-links, but does **not** restore `player.recruited_npcs` or reliably set `npc.is_recruited = True` for all recruited IDs.
- **Fix:**
  - Snapshot: `player.recruited_npcs`, and per-NPC `is_recruited` + `recruit_behavior`.
  - Load: restore list on player; for each ID, find NPC and set `is_recruited` / behavior; rebuild recruitment system behavior map consistently.

### 3.4 Monster population not saved

- On load, `_spawn_initial_monsters` runs again (fresh RNG from seed+1). Acceptable for v1 if documented; otherwise optional: persist monster positions/HP for closer continuity.
- **Decision for this pass:** Document as known limitation; do not block on it.

### 3.5 Fire entity restore edge cases

- Restored fires set `burn_duration_total = burn_remaining` (both equal remaining). Acceptable for display, but any code that assumes `total >= remaining` and uses progress fraction may show 100% fuel always.
- **Fix:** Persist both total and remaining if the entity supports it; otherwise leave as-is and note.

### 3.6 Season/weather already persisted (verify only)

- Snapshot and load already handle season + weather. Add a regression test if not already covered by `test_save_load_seasons.py` (suite has this file — confirm still green after other changes).

### 3.7 Save versioning

- `SAVE_VERSION = 2`; v1→v2 migration is a no-op version bump.
- When adding gold / recruited_npcs fields, either keep version 2 with `.get` defaults or bump to 3 with an explicit migrator. Prefer `.get` defaults for non-breaking additions.

**Exit criteria for Pass 3:**
- Save → load preserves: skills, survival, inventory (+ gold), gear, position, unlocked recipes/gear, structures, fires, faction standing, quest progress, season/weather, **recruited NPC set**.
- Documented limitations listed in this plan and/or code comments.
- `test_save_load_seasons` + new recruitment/gold round-trip tests pass.

---

## Pass 4 — Input router & panel dispatcher correctness (Medium–High)

**Goal:** Keyboard shortcuts and E-key NPC interactions work without bitrot from Phase 3.5 extraction.

### 4.1 Empty `pass` branches in router

- `input/router.py` has bare `pass` for some key groups (e.g. I/S/1 handling left empty while InputState flags drive the real logic). Confirm this is intentional (flags set by InputManager, then consumed) and not a dead path that leaves keys non-functional.
- **Audit:** For every key documented in `test_keyboard_shortcuts.py`, verify InputManager sets a flag **and** router consumes it exactly once.

### 4.2 NPC dialogue / E-key flows

- After fixing test patches (Pass 0.2), confirm runtime path: proximity → E → correct panel (trade / quest / recruit / diplomacy) via `NPCFlows` / panel dispatcher.
- Ensure router uses the shared `game._npc_flows` (Pass 1.2).

### 4.3 Panel open/close + `set_state` side effects

- `Game.set_state` opens panel visibility flags and sometimes closes all panels when switching. Audit transitions TITLE ↔ LOADING ↔ PLAYING and panel ↔ panel for double-close or missing `visible = False`.

**Exit criteria for Pass 4:** Keyboard shortcut tests and NPC dialogue tests green; manual smoke of I/J/C/H/U/T/K/L/S/B/Q/1/ESC and E-near-NPC.

---

## Pass 5 — Stub cleanup & low-hanging correctness (Medium)

**Goal:** Remove or quarantine stubs that can confuse runtime or future contributors. Do **not** implement full skill systems here.

### 5.1 Skill package stubs

- `skills/cooking/cooking.py`, `skills/crafting/crafting.py`, `skills/mining/mining.py`, `skills/woodcutting/woodcutting.py` are empty stubs (“No logic yet”).
- Cooking recipes already load via CraftingSystem; woodcutting/mining actions live in ActionSystem.
- **Fix:** Clarify in module docstrings that logic lives elsewhere; or thin-wrap ActionSystem/CraftingSystem so `game.cooking` is not a pure no-op if anything calls it. Avoid half-implementations.

### 5.2 Poison DoT stub

- `combat/monster.py` — poison currently adds +1 damage on attack (“DoT stub”).
- **Fix:** Either implement a minimal timed DoT on the player/survival, or rename/document as “poison on-hit bonus” so it is not a lie. Prefer small real DoT if cheap.

### 5.3 Duplicate `PANEL_STATES` in `core/state.py`

- The tuple is defined **twice** identically. Remove the duplicate.

### 5.4 Config comment “Combat (stub — Phase 2)”

- Combat is no longer a stub. Update the comment to avoid misleading maintainers.

### 5.5 Inventory gold comment

- After Pass 3 saves gold, update “Phase 1 stub: always 0” if gold can become non-zero through trade.

**Exit criteria for Pass 5:** No duplicate definitions; comments match reality; poison behavior is intentional and tested or explicitly deferred with a ticket note.

---

## Pass 6 — Rendering & visual correctness (Medium, limited)

**Goal:** Only bugs that affect correctness or cause crashes; not full art polish.

### 6.1 Placeholder-heavy paths

- `SpriteRenderer` falls back to colored rectangles when assets missing. Ensure missing-asset path never crashes (already mostly safe). Optional: log once per missing key to aid asset pipeline.

### 6.2 Seasonal tint wiring

- After Pass 0 (`noise`) and Pass 1 (renderer rebuild), re-verify `test_sprite_seasonal_tint` and seasonal renderer bootstrap tests.
- Confirm `_wire_phase4` assigns `seasonal_renderer` to **both** tile and sprite renderers **after** final renderer construction.

### 6.3 Particle system

- Bootstrap creates `ParticleSystem` and syncs weather. Confirm load path re-syncs after weather restore (already present in `load_into_game` — keep covered by tests).

**Exit criteria for Pass 6:** Seasonal/particle bootstrap tests green; no render exceptions on missing sprites.

---

## Pass 7 — Test suite green & regression harness (Mandatory close-out)

**Goal:** Full suite green; add targeted regression tests for bugs fixed in this phase.

### 7.1 Fix remaining failures

- After Passes 0–6, re-run full suite. Expected remaining failures should be zero; if any remain, triage into this phase or a follow-up ticket.

### 7.2 New regression tests (minimum set)

| Test | Covers |
|------|--------|
| `test_bootstrap_hud_refs_non_none` | Pass 1 HUD/faction/npc/renderer |
| `test_soft_death_combat` | Pass 2 combat path |
| `test_soft_death_starvation` | Pass 2 starvation path |
| `test_save_load_gold` | Pass 3 gold |
| `test_save_load_recruited_npcs` | Pass 3 recruitment |
| `test_autosave_uses_config_interval` | Pass 1.3 (optional, if easy) |

### 7.3 Smoke path

- Keep `tests/test_smoke.py` as the fast gate. Extend only if a bug requires it.

**Exit criteria for Pass 7:** `pytest tests/ -q` → 0 failed. Document final pass counts in this file’s changelog section.

---

## Pass 8 — Documentation & memory update

1. Update this plan’s “Status” / changelog when each pass lands.
2. Record durable facts in project memory (init-order fix, soft-death shared handler, save fields added, known v1 resource limitation still true).
3. If a `docs/superpowers/plans/` index exists later, link this plan.

---

## Suggested implementation order (granular checklist)

```
[ ] Pass 0.1  noise dependency or internal replacement
[ ] Pass 0.2  fix test_npc_dialogue_fix patches
[ ] Pass 0.3  document dependency
[ ] Pass 1.1  HUD / faction / npc / renderer init order
[ ] Pass 1.2  single NPCFlows instance
[ ] Pass 1.3  AUTOSAVE_INTERVAL from config
[ ] Pass 1.4  _autosave_timer slots consistency
[ ] Pass 2.1  deselect_target on soft death
[ ] Pass 2.2  starvation → soft death wiring
[ ] Pass 2.3  soft death invariant assertions + tests
[ ] Pass 3.1  document resource non-persistence
[ ] Pass 3.2  save/load inventory.gold
[ ] Pass 3.3  save/load recruited_npcs + is_recruited
[ ] Pass 3.5  fire total vs remaining (if cheap)
[ ] Pass 4.1  audit router key paths vs tests
[ ] Pass 4.2  E-key NPC flows with shared NPCFlows
[ ] Pass 4.3  panel set_state transitions
[ ] Pass 5.1  skill stub docstrings / thin wrappers
[ ] Pass 5.2  poison behavior clarify or minimal DoT
[ ] Pass 5.3  remove duplicate PANEL_STATES
[ ] Pass 5.4  config combat comment
[ ] Pass 6.x  seasonal/particle wiring verification
[ ] Pass 7    full suite green + regression tests
[ ] Pass 8    docs + project memory
```

---

## Explicit non-goals (do not expand scope)

- Implementing full Cooking / Mining / Woodcutting skill classes beyond what ActionSystem already does.
- Persisting every depleted resource node (v2 feature).
- New biomes, new monster types, new UI panels.
- Performance optimization of 512×512 world gen.
- Replacing placeholder sprites with final art.

---

## Risk notes

- **Init-order changes** can break tests that construct partial Games. Prefer additive setters + final `_finalize_wiring()` if reordering `initialize()` is too disruptive.
- **Soft-death from starvation** must not re-enter death handling every frame while `is_dead` is true; use a rising-edge or clear `is_dead` inside the handler before any further ticks.
- **Save format:** Prefer backward-compatible `.get` defaults over a forced version bump unless fields are mandatory.

---

## Trace evidence (key file references)

| Issue | Primary locations |
|-------|-------------------|
| HUD before faction/NPC | `core/bootstrap.py` `initialize()` order; `_build_hud` vs `_build_npc_system` / `_build_faction_system` |
| Sprite renderer replaced late | `Game.__init__` placeholder; `_build_renderers()` |
| Soft death missing deselect | `combat/combat_system.py` `_on_player_death` |
| Starvation ignores death return | `survival/survival_system.py` `tick` / `take_damage`; no caller of soft death |
| Gold not in snapshot | `core/save_system.py` `_build_snapshot` / `load_into_game`; `inventory/inventory.py` |
| recruited_npcs not in snapshot | `core/player.py`; `save_system.py` recruitment_state only |
| Resource depletion not saved | `save_system.py` (no resource overlay); world regen in `load_save` |
| `noise` missing | `world/world_gen.py` line ~20; cascading tests |
| NPC dialogue test paths | `tests/test_npc_dialogue_fix.py` |
| Duplicate PANEL_STATES | `core/state.py` |
| Autosave magic number | `core/game.py` `update` |
| Multi NPCFlows | `Game.__init__`, `Bootstrap._build_npc_flows`, `InputRouter.__init__` |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-08-18 | Initial plan from full codebase + test-suite trace (11 failures catalogued). |

---

*End of phase-bugfix-granular plan.*
