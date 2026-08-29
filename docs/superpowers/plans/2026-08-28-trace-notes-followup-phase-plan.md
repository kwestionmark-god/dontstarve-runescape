# TRACE-NOTES Follow-Up Phase Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every remaining open finding from `tmp/TRACE-NOTES.md` (excluding the 12 fixes already applied in the working tree per §13 of that document) through a sequenced, independently testable set of phases.

**Architecture:** The 48+ remaining findings cluster into 11 logical phases by subsystem. Each phase targets one architectural boundary (core loop, world/seasons, actions/survival, inventory/crafting, skills/building, combat/trade/quest, interactions/input, render/performance, test coverage, data/UI polish, features). Phases are ordered to fix wiring/correctness before polish, and to isolate subsystems with no shared state so they can be executed in parallel once their designs are locked.

**Tech Stack:** Python 3.10+, pygame 2.6+, noise (Perlin), pytest, dataclasses, typing. No new dependencies.

**Spec:** `tmp/TRACE-NOTES.md` (this plan argues from the trace; executors read both).

---

## Global Constraints

- Python 3.10+ (builtin generics `list[int]`, union `X | None` syntax)
- All changes must keep the full pytest suite green (currently 716 passed)
- No silent failures: every error path must surface a notification or log
- Determinism: world generation, weather, fire IDs, and combat must be seed-reproducible
- Data-driven: hardcoded tables (fuel→XP, skill formulas) move to JSON/registry
- Single source of truth: config constants, registry query methods, keybinding map
- `__slots__` classes stay slotted; new fields declared explicitly
- All new code paths covered by at least one unit or integration test

---

## Phase A — Core Loop & Bootstrap Hygiene (S, ~2–3h, zero risk)

*Unblocks clean init order; no behavioural change to gameplay.*

### A.1 `game_loop.py` uses `config.TARGET_FPS` instead of hardcoded `60`

**Files:**
- Modify: `core/game_loop.py:22`
- Test: `tests/test_game_loop.py` (new or extend)

**Interfaces:**
- Consumes: `config.TARGET_FPS` (int)
- Produces: None (behavioural parity at default)

- [ ] **Step 1: Write the failing test**
```python
# tests/test_game_loop.py
def test_game_loop_uses_config_fps(monkeypatch):
    import config
    import core.game_loop as gl
    original_tick = gl.pygame.time.Clock.tick
    captured = {}
    def spy(self, fps):
        captured['fps'] = fps
        return original_tick(self, fps)
    monkeypatch.setattr(gl.pygame.time.Clock, 'tick', spy)
    # minimal game mock
    class MockGame:
        clock = gl.pygame.time.Clock()
        running = True
        def tick(self, dt): self.running = False
        def handle_events(self): pass
        def render(self): pass
    gl.run(MockGame())
    assert captured['fps'] == config.TARGET_FPS
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_game_loop.py::test_game_loop_uses_config_fps -v`
Expected: FAIL (hardcoded 60)

- [ ] **Step 3: Write minimal implementation**
```python
# core/game_loop.py:22
# before: dt = game.clock.tick(60) / 1000.0
dt = game.clock.tick(TARGET_FPS) / 1000.0
```
Add `from config import TARGET_FPS` at module top.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_game_loop.py::test_game_loop_uses_config_fps -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add core/game_loop.py tests/test_game_loop.py
git commit -m "fix: game_loop uses config.TARGET_FPS instead of hardcoded 60"
```

---

### A.2 `Bootstrap.initialize` decouples from `CombatSystem._on_player_death` (private)

**Files:**
- Modify: `core/bootstrap.py:65`
- Modify: `combat/combat_system.py` (add public setter)
- Test: `tests/test_bootstrap_wiring.py`

**Interfaces:**
- `CombatSystem.set_player_death_handler(callable) -> None`
- `SurvivalSystem.on_death` remains the callback slot

- [ ] **Step 1: Write the failing test**
```python
# tests/test_bootstrap_wiring.py
def test_bootstrap_uses_public_death_handler_setter():
    from core.bootstrap import Bootstrap
    from combat.combat_system import CombatSystem
    # Verify public API exists
    assert hasattr(CombatSystem, 'set_player_death_handler')
    # Verify it's called during bootstrap (spy)
```

- [ ] **Step 2: Add public setter to CombatSystem**
```python
# combat/combat_system.py
def set_player_death_handler(self, handler):
    """Public API for bootstrap to wire the death callback."""
    self._player_death_handler = handler

# In _on_player_death, also call self._player_death_handler if set
```

- [ ] **Step 3: Update bootstrap to use public setter**
```python
# core/bootstrap.py:65
# before: self.game.survival.on_death = self.game.combat_system._on_player_death
self.game.combat_system.set_player_death_handler(self.game.survival.on_death)
# survival.on_death is set later in _build_survival or similar; ensure order
```

- [ ] **Step 4: Run tests**
Run: `pytest tests/test_bootstrap_wiring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

---

### A.3 HUD built after its dependencies (single-phase construction)

**Files:**
- Modify: `core/bootstrap.py` (reorder `_build_hud` after `_build_faction_system`, `_build_npc_system`, `_build_renderers`)
- Test: `tests/test_hud_wiring.py`

**Interfaces:**
- `HUD.__init__` receives all non-None refs directly

- [ ] **Step 1: Write the failing test**
```python
# tests/test_hud_wiring.py
def test_hud_has_real_refs_after_bootstrap():
    from core.bootstrap import Bootstrap
    from core.game import Game
    game = Game()
    Bootstrap(game).initialize()
    assert game.hud.faction_system is not None
    assert game.hud.npc_system is not None
    assert game.hud.sprite_renderer is not None
```

- [ ] **Step 2: Reorder bootstrap methods**
Move `_build_hud()` call to after `_build_faction_system()`, `_build_npc_system()`, and `_build_renderers()`. Remove `_finalize_hud()` if it becomes empty.

- [ ] **Step 3: Run test**
Run: `pytest tests/test_hud_wiring.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

---

### A.4 Replace hardcoded `64` with `config.TILE_SIZE` (4–5 sites)

**Files:**
- Modify: `core/bootstrap.py` (`_spawn_initial_monsters`)
- Modify: `core/game.py` (`render_game` view-rect, `_render_build_ghost` note)
- Modify: `core/player.py` (`find_interactable_resource`)
- Test: `tests/test_tile_size_constant.py`

**Interfaces:**
- Consumes: `config.TILE_SIZE`

- [ ] **Step 1: Write test asserting no hardcoded 64 in these paths**
```python
# tests/test_tile_size_constant.py
def test_no_hardcoded_tile_size_in_bootstrap_and_game():
    import ast, inspect
    for mod_path in ['core/bootstrap.py', 'core/game.py', 'core/player.py']:
        src = open(mod_path).read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == 64:
                # allow in comments/docstrings by checking context
                raise AssertionError(f"Hardcoded 64 found in {mod_path}")
```

- [ ] **Step 2: Replace each occurrence with `TILE_SIZE` import**

- [ ] **Step 3: Run test**
Run: `pytest tests/test_tile_size_constant.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

---

### A.5 Collapse `Player.moving` / `is_moving` to one flag

**Files:**
- Modify: `core/player.py` (remove one, update all references)
- Test: `tests/test_player_movement_flags.py`

- [ ] **Step 1: Audit references** (grep shows both used; keep `moving`, drop `is_moving`)
- [ ] **Step 2: Write test for movement state transitions**
- [ ] **Step 3: Implement removal**
- [ ] **Step 4: Run full suite**
- [ ] **Step 5: Commit**

---

### A.6 `Player.take_damage` direct survival reference

**Files:**
- Modify: `core/player.py` (add `self.survival` in `__init__`/`__slots__`)
- Modify: `core/bootstrap.py` (wire `player.survival = game.survival`)
- Test: `tests/test_player_survival_ref.py`

---

### A.7 Remove dead `Game._combat_panel` slot

**Files:**
- Modify: `core/game.py` (remove from `__slots__`)
- Test: grep confirms no references

---

### A.8 `render_game` depth-sort entities (visual correctness)

**Files:**
- Modify: `core/game.py` (`render_game` — collect all drawables, sort by world_y + height, single pass)
- Test: `tests/test_render_order.py` (snapshot or ordering assertion)

---

### A.9 `render_game` uses `config.FOG_COLOR` for sky fill

**Files:**
- Modify: `core/game.py` (replace `(135, 206, 235)` with `FOG_COLOR`)
- Test: `tests/test_render_constants.py`

---

### A.10 `main.py` imports `pygame` at module top

**Files:**
- Modify: `main.py` (move import to top, keep `pygame.quit()`/`sys.exit()` in `finally`)

---

### A.11 `requirements.txt` and `world_gen.py` docstrings: Perlin not simplex

**Files:**
- Modify: `requirements.txt` comment
- Modify: `world/world_gen.py` module docstring and `_generate_elevation_map` docstring
- Test: grep for "simplex" returns zero hits in these files

---

## Phase B — World & Seasons Correctness (M, ~4–6h)

*Fixes terrain sampling bugs, season/weather wiring, and data-model smells.*

### B.1 `TileMap.get_corner_height` kernel rewrite (fixes asymmetric weights)

**Files:**
- Modify: `world/tile_map.py:188-227`
- Test: `tests/test_tilemap_corner_height.py` (golden master or symmetry assertion)

**Design:** Implement the documented kernel (NW/NE/SW/SE weight 4, ortho 1, diag 0.25) without double-counting. Iterate a 3×3 window around the corner with explicit weight matrix.

---

### B.2 `TileMap.compute_slope_shading` includes SE corner in gradient

**Files:**
- Modify: `world/tile_map.py` (use `(se - nw)` for both axes or proper 2D gradient)
- Test: `tests/test_slope_shading.py`

---

### B.3 `ResourceNode.TIER_DENSITY_MULTIPLIER` → `ClassVar[dict[int, float]]`

**Files:**
- Modify: `world/resource_placer.py` (import `ClassVar` from typing)
- Test: `tests/test_resource_node_classvar.py` (verify class access)

---

### B.4 `ResourceNode.remaining_depletions` for infinite nodes returns `inf` or large sentinel

**Files:**
- Modify: `world/resource_placer.py` (property `remaining_depletions`)
- Test: `tests/test_infinite_resource_remaining.py`

---

### B.5 `TileMap.has_structure_nearby` removed or redirected to `BuildingSystem`

**Files:**
- Modify: `world/tile_map.py` (remove method or delegate)
- Verify: no callers remain (grep)

---

### B.6 `BiomeRegistry.get` adds `.get(id, default)` overload

**Files:**
- Modify: `world/biome.py` (add classmethod `get` with default)
- Test: `tests/test_biome_registry_get.py`

---

### B.7 `SeasonSystem.__init__` falsy-default guards (`if x is None`)

**Files:**
- Modify: `seasons/season_system.py:57,66,67`
- Test: `tests/test_season_system_empty_dict.py` (passing `{}` preserves emptiness)

---

### B.8 Remove dead `SeasonSystem.from_dict` / `WeatherSystem.from_dict`

**Files:**
- Modify: `seasons/season_system.py`, `seasons/weather_system.py` (delete methods)
- Verify: `save_system.load_into_game` doesn't call them (already manual)

---

### B.9 Remove `config.WEATHER_WEIGHTS` / `WEATHER_CHANGE_INTERVAL` duplicates

**Files:**
- Modify: `config.py` (delete lines, keep imports from seasons if needed)
- Test: `tests/test_config_no_weather_duplicates.py`

---

### B.10 `WeatherSystem` seeds RNG from game seed (not hardcoded 42)

**Files:**
- Modify: `seasons/weather_system.py` (`__init__` accepts `seed`, uses it)
- Modify: `core/bootstrap.py` (pass `game.seed` when constructing)
- Test: `tests/test_weather_seed_determinism.py` (two worlds same seed → same weather sequence)

---

### B.11 Wire `WeatherSystem.get_effects()` multipliers into gameplay

**Files:**
- Modify: `seasons/weather_system.py` (ensure `get_effects` returns dict)
- Modify: `survival/survival_system.py` (apply movement/visibility modifiers)
- Modify: `actions/action_system.py` (apply outdoor-crafting/spawn multipliers)
- Modify: `npc/faction_system.py` or `combat/combat_system.py` (spawn multipliers)
- Test: `tests/test_weather_gameplay_effects.py` (integration: weather change → stat change observable)

---

## Phase C — Actions & Survival Systems (M, ~4–5h)

*Fixes stamina, action protocol, survival edge cases, and skill callback hygiene.*

### C.1 `ActionType.SUCCESS` / `FAILURE` enum values removed or used

**Files:**
- Modify: `actions/action_system.py` (drop unused enum members or wire them)
- Test: `tests/test_action_type_enum.py`

---

### C.2 `ActiveAction.is_busy` excludes `IDLE` state

**Files:**
- Modify: `actions/action_system.py` (property: `return self.state == ActionType.RUNNING`)

---

### C.3 `StaminaPool` converted to `@dataclass` with `__slots__` and `__init__`

**Files:**
- Modify: `actions/stamina.py` (full rewrite as dataclass)
- Test: `tests/test_stamina_pool_dataclass.py` (two independent pools don't share class attrs)

---

### C.4 `StaminaPool.consume` boundary: `<` not `<=` (exact stamina = success)

**Files:**
- Modify: `actions/stamina.py:28` (`if self.current < amount:`)
- Test: `tests/test_stamina_boundary.py` (3.0 stamina, cost 3.0 → succeeds)

---

### C.5 `ActionSystem._complete_cooking` removed or wired (dead stub)

**Files:**
- Modify: `actions/action_system.py` (remove method, verify no callers)
- Verify: `CraftingSystem.cook` is the only cook path (panel dispatcher)

---

### C.6 Replace string-protocol completion with `ActionResult` dataclass

**Files:**
- Create: `actions/action_result.py` (`@dataclass ActionResult: success: bool; item_id: str; quantity: int; xp: int; message: str`)
- Modify: `actions/action_system.py` (`update` returns `ActionResult | None`, `process_completion` consumes it)
- Test: `tests/test_action_result_dataclass.py`

---

### C.7 `success_rate_bonus` stored as positive points (subtract in roll)

**Files:**
- Modify: `actions/action_system.py` (invert sign at storage site, adjust roll)
- Test: `tests/test_success_rate_bonus_sign.py`

---

### C.8 `ActionType.get_skill_id` unreachable fallback removed

**Files:**
- Modify: `actions/action_system.py` (delete fallback branch)
- Test: `tests/test_action_type_skill_id.py` (covers all enum members)

---

### C.9 `SkillManager` notification callback → return value

**Files:**
- Modify: `actions/action_system.py` (`process_completion` returns `list[str]` notifications)
- Modify: `skills/skill_manager.py` (`add_xp_with_notification` returns messages)
- Test: `tests/test_skill_notification_return.py`

---

### C.10 `SurvivalSystem.tick` calls `on_death()` — verify `_on_player_death` takes no args

**Files:**
- Verify: `combat/combat_system.py:353` signature is `def _on_player_death(self) -> None:`
- If signature changes, update both sides
- Test: `tests/test_death_callback_signature.py`

---

### C.11 `SurvivalSystem.update_from_tile` default biome handling

**Files:**
- Modify: `survival/survival_system.py` (log warning or apply neutral pressure on `None`)
- Test: `tests/test_survival_none_biome.py`

---

### C.12 `SurvivalSystem.get_hunger_percent` / `get_hp_percent` zero-guard

**Files:**
- Modify: `survival/survival_system.py` (return 0.0 or 1.0 if max == 0)
- Test: `tests/test_survival_zero_max.py`

---

### C.13 `FoodRegistry`/`FoodItem` reference `Item` instead of duplicating fields

**Files:**
- Modify: `survival/food.py` (`FoodItem` holds `item_id` reference, delegates `stack_size`, `sprite_key`)
- Modify: `survival/survival_system.py` (lookup via `game.item_registry` or similar)
- Test: `tests/test_food_item_dedupe.py`

---

### C.14 Character/background selection UI (starter_pack integration) — **Feature**

**Files:**
- Create: `ui/character_select.py` (PanelWindow subclass)
- Modify: `core/bootstrap.py` (show panel before `begin_world_gen`)
- Modify: `core/game.py` (new `GameState.CHARACTER_SELECT`)
- Modify: `data/character_backgrounds.json` (define 3+ backgrounds with stat bonuses)
- Test: `tests/test_character_select_ui.py`

---

## Phase D — Inventory & Crafting Polish (M, ~3–4h)

*Removes duplication, fixes edge cases, centralizes spoilage.*

### D.1 `Inventory.can_add` becomes dry-run of `add_item` loop

**Files:**
- Modify: `inventory/inventory.py` (extract `_try_add_stacking` helper used by both)
- Test: `tests/test_inventory_can_add_dryrun.py` (exhaustive: exact stack, multi-slot, partial)

---

### D.2 `Inventory.equip_item` enforces slot-type grouping (weapon/armor/tool)

**Files:**
- Modify: `inventory/inventory.py` (add `equip_slot_type` to item data or `GearItem` lookup)
- Test: `tests/test_inventory_equip_slot_type.py`

---

### D.3 `Inventory.set_spoilage` per-quantity (new stack gets fresh timer)

**Files:**
- Modify: `inventory/inventory.py` (track spoilage per-stack, not per-item-id)
- Test: `tests/test_inventory_spoilage_per_stack.py`

---

### D.4 `Inventory.remove_item` single empty representation (`None` only)

**Files:**
- Modify: `inventory/inventory.py` (slot = `None` when quantity reaches 0)
- Modify: `inventory/inventory.py` (`get_snapshot` simplified)
- Test: `tests/test_inventory_empty_slot_repr.py`

---

### D.5 `Inventory.gold` wired or removed (player economy)

**Files:**
- Modify: `inventory/inventory.py` (add `gold` property with setter, default 0)
- Modify: `npc/trade_system.py` (use `player.inventory.gold` — already does)
- Test: `tests/test_inventory_gold.py` (earn/spend roundtrip)

---

### D.6 `CraftingSystem.craft` remove dead `backed_up` dict

**Files:**
- Modify: `crafting/crafting_system.py:337-341` (delete lines)
- Test: `tests/test_craft_no_backed_up.py` (cook failure still rolls back via `saved_slots`)

---

### D.7 `CraftingSystem.cook` deep copy or snapshot for rollback safety

**Files:**
- Modify: `crafting/crafting_system.py` (`saved_slots = [slot.copy() for slot in inventory.slots]` or `inventory.snapshot()`)
- Add `Inventory.snapshot() -> list[InventorySlot]` method
- Test: `tests/test_craft_cook_rollback_safety.py`

---

### D.8 Single spoilage ownership: `Inventory.add_item` applies spoilage for food

**Files:**
- Modify: `inventory/inventory.py` (`add_item` checks `food_registry`, sets spoilage on new stacks)
- Modify: `actions/action_system.py` (remove spoilage set in `process_completion`)
- Modify: `input/panel_dispatcher.py` (remove spoilage set in craft/cook handlers)
- Test: `tests/test_spoilage_single_owner.py` (gathered, crafted, cooked all have spoilage)

---

### D.9 `CraftingSystem` delegates all recipe queries to `RecipeRegistry`

**Files:**
- Modify: `crafting/crafting_system.py` (drop local `_recipes`, `_recipe_index`, query methods)
- Modify: `crafting/recipe_registry.py` (ensure all query methods exist)
- Test: `tests/test_crafting_delegates_to_registry.py`

---

### D.10 `Recipe.from_dict` validation via `RecipeRegistry._load_from_dir` path only

**Files:**
- Modify: `crafting/recipe_registry.py` (`load_recipes` validates before `from_dict`)
- Modify: `crafting/crafting_system.py` (`load_recipes` removed or delegates)
- Test: `tests/test_recipe_validation.py` (malformed recipe rejected at load)

---

### D.11 Remove dead `config.LOADING_SCREEN_DURATION` import from `crafting_system.py`

**Files:**
- Modify: `crafting/crafting_system.py` (delete import)

---

### D.12 `_chain_to_skill` comprehensive mapping (all chains → correct skill)

**Files:**
- Modify: `crafting/crafting_system.py:25-35` (add `stone`→`mining`, `ore`→`mining`, `metallurgy`→`metallurgy`, `cooking`→`cooking`, `intelligence`→`intelligence`, `construction`→`construction`, `foraging`→`foraging`)
- Add `foraging` skill if missing (see Phase K.4)
- Test: `tests/test_chain_to_skill_comprehensive.py`

---

## Phase E — Skills & Building Polish (L, ~1–2 days)

*Deduplication, capacity checks, determinism, and the CookingSkill wiring.*

### E.1 Deduplicate building-tech logic: single `BuildingTechMixin` or module

**Files:**
- Create: `skills/building_tech.py` (shared formulas: `get_level`, `get_bonus`, `get_damage`)
- Modify: `skills/construction/construction.py` (import and use)
- Modify: `skills/crafting/crafting.py` (import and use)
- Modify: `building/building_system.py` (import and use for offensive damage)
- Test: `tests/test_building_tech_single_source.py`

---

### E.2 `BuildingSystem.pickup_structure` vs `remove_structure` unified or differentiated

**Files:**
- Modify: `building/building_system.py` (decide: keep `remove_structure` with 0% return, `pickup_structure` with 50%)
- Test: `tests/test_building_pickup_vs_remove.py`

---

### E.3 `BuildingSystem.monster_attack_structure` loot to ground (not player inventory)

**Files:**
- Modify: `building/building_system.py` (spawn `ItemDrop` entities or drop on tile)
- Test: `tests/test_monster_destroy_structure_loot.py`

---

### E.4 `BuildingSystem._fire_timer` declared field on `Structure` dataclass

**Files:**
- Modify: `building/building_system.py` (add `fire_timer: float = 0.0` to `Structure`)
- Modify: `building/building_system.py` (remove `hasattr`/`setattr` dynamic access)
- Test: `tests/test_structure_fire_timer_field.py`

---

### E.5 `BuildingSystem.place_structure` occupancy check sub-tile precision

**Files:**
- Modify: `building/building_system.py` (check tile coordinates, not pixel radius)
- Test: `tests/test_building_placement_adjacent.py`

---

### E.6 `MetallurgySkill.attempt_smelt` capacity check before consuming

**Files:**
- Modify: `skills/metallurgy/metallurgy.py:148-216` (add `if not inventory.can_add(recipe.output_item, recipe.output_quantity): return SmeltResult(success=False, message="Inventory full.")` before any `remove_item`)
- Test: `tests/test_smelt_inventory_full.py` (ore + fuel preserved, no output)

---

### E.7 `MetallurgySkill` loads `SmeltRecipe` from registry (not re-derived)

**Files:**
- Create: `data/smelt_recipes.json` (canonical smelt fields: ore, fuel, extra, output, xp, alloy_req)
- Modify: `skills/metallurgy/metallurgy.py` (`RecipeRegistry` loads smelt recipes; `_get_smelt_recipes` returns them directly)
- Test: `tests/test_smelt_recipe_registry.py`

---

### E.8 `_SMELT_RECIPES` / `_FUEL_TABLE` lazy-loaded (module-level function)

**Files:**
- Modify: `skills/metallurgy/metallurgy.py` (replace top-level `json.loads` with `_load_smelt_recipes()` / `_load_fuel_table()` called on first use)
- Test: `tests/test_metallurgy_lazy_load.py` (import doesn't hit disk)

---

### E.9 `firemaking.py` deterministic `fire_id` (counter or seed-derived)

**Files:**
- Modify: `skills/firemaking/firemaking.py` (module-level `_fire_counter = 0`; `fire_id = f"fire_{_fire_counter}"; _fire_counter += 1`)
- Test: `tests/test_fire_id_determinism.py` (same seed → same fire IDs)

---

### E.10 `_calculate_fire_xp` reads from `data/fuel_table.json` (data-driven)

**Files:**
- Modify: `data/fuel_table.json` (add `xp_per_unit` to each fuel entry)
- Modify: `skills/firemaking/firemaking.py` (`_calculate_fire_xp` reads from loaded fuel table)
- Test: `tests/test_fire_xp_data_driven.py`

---

### E.11 `FiremakingSkill.light_fire` single-pass consume (`remove_item` validates)

**Files:**
- Modify: `skills/firemaking/firemaking.py` (replace two-pass with `if not inventory.remove_item(fuel, 1): return fail`)

---

### E.12 `SkillManager` imports `Callable`, `Dict` at runtime (not only `TYPE_CHECKING`)

**Files:**
- Modify: `skills/skill_manager.py:16-27` (move imports out of `TYPE_CHECKING`)
- Test: `tests/test_skill_manager_runtime_annotations.py` (`typing.get_type_hints` works)

---

### E.13 `SkillManager.allocate_stat` validates `sub_stat` exists for skill

**Files:**
- Modify: `skills/skill_manager.py:352-380` (check `sub_stat in self._skill_defs[skill_id].sub_stats`)
- Test: `tests/test_allocate_stat_validation.py` (typo returns False)

---

### E.14 `SkillManager` drops duplicate query methods, exposes `RecipeRegistry`

**Files:**
- Modify: `skills/skill_manager.py` (remove `get_recipe`, `get_available_recipes`, etc.; add `self.recipe_registry` property)
- Test: `tests/test_skill_manager_delegates_recipes.py`

---

### E.15 Parameterized `GatheringSkill` base class (replaces 4 stub classes)

**Files:**
- Create: `skills/gathering.py` (`class GatheringSkill: ...` with `skill_id`, `yield_formula`, `stamina_formula`, `success_formula`, `description` as config)
- Modify: `skills/woodcutting/woodcutting.py`, `skills/mining/mining.py`, `skills/crafting/crafting.py`, `skills/cooking/cooking.py` (subclass `GatheringSkill`)
- Test: `tests/test_gathering_skill_base.py` (each skill computes distinct values)

---

### E.16 Wire `CookingSkill` into `CraftingSystem.cook` (success/nutrition/spoilage)

**Files:**
- Modify: `crafting/crafting_system.py` (`cook` calls `cooking_skill.get_success_rate_bonus()`, `cooking_skill.calculate_nutrition()`, `cooking_skill.get_spoilage_modifier()`)
- Modify: `skills/cooking/cooking.py` (ensure methods are public and tested)
- Test: `tests/test_cooking_skill_wired.py` (cooking level affects success rate, nutrition, spoilage)

---

## Phase F — Combat, Trade & Quest Fixes (M-L, ~1–2 days)

*Correctness fixes for damage, death, trade semantics, and quest wiring.*

### F.1 `CombatSystem.calculate_damage` additive: `(base_attack + weapon_damage) * mult`

**Files:**
- Modify: `combat/combat_system.py:172-200` (change formula)
- Test: `tests/test_damage_formula.py` (fresh player with weapon deals >1 damage)

---

### F.2 `CombatSystem.tick` fire-deterrence cleanup (remove dead branch)

**Files:**
- Modify: `combat/combat_system.py` (simplify `if not monster.is_alive(): pass` block)

---

### F.3 `_on_player_death` uses `TILE_SIZE` not hardcoded 64

**Files:**
- Modify: `combat/combat_system.py:370` (`spawn_x * TILE_SIZE + TILE_SIZE // 2`)
- Test: `tests/test_death_respawn_tile_size.py`

---

### F.4 `_on_player_death` monster removal: configurable (not all)

**Files:**
- Modify: `combat/combat_system.py` (add config `DEATH_CLEAR_MONSTERS_RADIUS` or `DEATH_CLEAR_ALL_MONSTERS`)
- Test: `tests/test_death_monster_clearing.py`

---

### F.5 `Monster` declares all dynamic attributes as dataclass fields

**Files:**
- Modify: `combat/monster.py` (add `_base_stats`, `_base_speed`, `_base_defence`, `_base_attack_range`, `_poison_applied` with defaults)
- Test: `tests/test_monster_slots.py` (no `__dict__` growth)

---

### F.6 `Monster.from_def` removes dead `"xp"` fallback key

**Files:**
- Modify: `combat/monster.py` (use only `xp_reward`)
- Test: `tests/test_monster_xp_key.py`

---

### F.7 `CombatSystem.get_attack_cooldown` removes duplicate `base_cooldown` assignment

**Files:**
- Modify: `combat/combat_system.py` (single assignment)

---

### F.8 `TradeSystem.execute_buy` stock truncation semantics aligned with gold

**Files:**
- Modify: `npc/trade_system.py:305-310` (when `current_stock < quantity`, set `quantity = current_stock` and proceed — don't force buy-all if player only wanted some)
- Test: `tests/test_trade_buy_stock_truncation.py` (player requests 10, stock 3 → buys 3, not forced to buy all 3 if gold allows 10)

---

### F.9 `TradeSystem.execute_barter` fair quantity (player gives what merchant receives)

**Files:**
- Modify: `npc/trade_system.py:560-580` (`give_quantity = min(player_quantity, merchant_stock)`; both sides exchange same quantity)
- Test: `tests/test_barter_fair_quantity.py`

---

### F.10 Trade/Restock concurrency: restock triggers on empty stock regardless of gold

**Files:**
- Modify: `npc/trade_system.py` (restock condition: `current_stock == 0` or `gold <= 0`)
- Test: `tests/test_trade_restock_semantics.py`

---

### F.11 `TradeSystem._extract_biome_from_npc_id` robust parsing (regex or split with validation)

**Files:**
- Modify: `npc/trade_system.py` (use `re.match(r'merchant_(\w+)_\d+', npc_id)`)
- Test: `tests/test_trade_biome_extraction.py` (various NPC id formats)

---

### F.12 Quest system wired into `CraftingSystem.craft`/`cook` (record_craft)

**Files:**
- Modify: `crafting/crafting_system.py` (pass `quest_system` through, already has optional param at line 358)
- Modify: `input/panel_dispatcher.py` (pass `game.quest_system` when calling `craft`/`cook`)
- Test: `tests/test_quest_craft_tracking.py` (`collect_item` quest advances on craft)

---

## Phase G — Interactions & Input Cleanup (S-M, ~3–4h)

*Hotbar, foraging action, skill allocation policy, keybinding consolidation.*

### G.1 Tool-less resources → `ForagingAction` / `foraging` skill (feature)

**Files:**
- Create: `actions/foraging.py` (new `ActionType.FORAGING`, `ForagingSkill` or `GatheringSkill` variant)
- Modify: `interactions/interact.py` (map herbs/berries/water to `FORAGING`)
- Modify: `skills/__init__.py` (register foraging skill)
- Test: `tests/test_foraging_action.py` (XP goes to foraging, not woodcutting)

---

### G.2 `PanelDispatcher._handle_skill_allocation` refund policy unified

**Files:**
- Modify: `input/panel_dispatcher.py:100-140` (remove direct `skill.sub_stats[sub_stat] -= 1`; call `skill_manager.allocate_stat(skill_id, sub_stat, -1, wildcard=True)` or add `refund_stat` method)
- Test: `tests/test_skill_allocation_refund.py` (refund uses same validation as allocate)

---

### G.3 Remove dead no-op keys in `router._handle_keydown` (K_i, K_s, K_1)

**Files:**
- Modify: `input/router.py` (delete lines)

---

### G.4 `_handle_hotbar` caches `items.json` / `food_registry` at init

**Files:**
- Modify: `input/router.py` (`__init__` loads item data once; `_handle_hotbar` uses cache)

---

### G.5 Consolidate keybindings: single `config/keybindings.py` source

**Files:**
- Create: `config/keybindings.py` (`KEYBINDINGS: dict[GameState, dict[str, int]]` mapping action→key)
- Modify: `input/input_manager.py` (builds binds from config)
- Modify: `input/router.py` (reads from config)
- Modify: `ui/panel_window.py` or panels (hints read from config)
- Test: `tests/test_keybinding_single_source.py` (no drift between input_manager and router)

---

### G.6 `InputState.hotbar_slot` clear-on-release removed (redundant)

**Files:**
- Modify: `input/input_manager.py` (remove `K_1`–`K_8` from `_on_key_up` handling)

---

### G.7 `camera.py` docstring aligned with config (pitch range, yaw keys)

**Files:**
- Modify: `camera/camera.py` (docstring: pitch 5°–35°, yaw ←/→ only)

---

## Phase H — Render & Performance (M, ~4–5h)

*Animation, caching, deduplication, seasonal variation.*

### H.1 Player animation clock (walk/idle frames 0–3)

**Files:**
- Modify: `render/sprite_renderer.py` (`render_player` tracks `animation_timer`, cycles frames)
- Modify: `core/game.py` (pass `dt` to render or use global clock)
- Test: `tests/test_player_animation.py` (frame changes over time)

---

### H.2 Sprite cache stores zoomed variants per `(sprite_key, zoom)` key

**Files:**
- Modify: `render/sprite_renderer.py` (`_sprite_cache` key includes `zoom`; `pygame.transform.scale` cached)
- Test: `tests/test_sprite_cache_zoom.py` (same sprite at same zoom returns cached surface)

---

### H.3 Shared `_billboard` helper for `render_resource`/`render_npc`/`render_monster`/`render_fire`

**Files:**
- Modify: `render/sprite_renderer.py` (extract `_draw_billboard(screen, world_x, world_y, sprite, ...)` handling tile height → screen → fog → zoom → tint)
- Modify: each `render_*` to call helper
- Test: `tests/test_billboard_helper.py` (output matches old per-method rendering)

---

### H.4 `_get_season_tint` varies by season (Summer vs Winter different)

**Files:**
- Modify: `render/sprite_renderer.py` (read `season_system.current_season`, return season-appropriate tint)
- Test: `tests/test_seasonal_tint_variation.py`

---

### H.5 Module-level font cache (single `pygame.font.SysFont` instance)

**Files:**
- Create: `render/fonts.py` (`get_font(name, size, bold) -> Font` with LRU cache)
- Modify: `core/game.py` (damage numbers use `get_font`)
- Modify: `ui/panel_window.py` (uses font cache)
- Test: `tests/test_font_cache.py` (same params returns same object)

---

## Phase I — Test Coverage & Wiring Smoke Test (M, ~3–4h)

*Closes the mock-vs-reality gap documented in §9.*

### I.1 Wiring smoke test: real `Bootstrap.initialize()` + real objects

**Files:**
- Create: `tests/integration/test_wiring_smoke.py`
- Test exercises: monster kill → loot in inventory, trade buy/sell, craft failure notification, hotbar press, structure placement with real `data/structures.json`, recruited NPC render

---

### I.2 Replace `SimpleNamespace`/`MagicMock` Player/Inventory in key tests

**Files:**
- Modify: `tests/test_faction_trade_integration.py`
- Modify: `tests/integration/test_quest_integration.py`
- (Use real `Player` with `inventory` wired, real `Inventory`)

---

### I.3 `test_b4_building_placement.py` fixture uses real `requires_structure_level >= 1`

**Files:**
- Modify: `tests/test_b4_building_placement.py` (fixture structures have `requires_structure_level=1`)

---

### I.4 Add recruited NPC render test (real display + asset)

**Files:**
- Create: `tests/integration/test_recruit_npc_render.py` (uses `pygame.display.set_mode` headless or `pygame.Surface`)

---

### I.5 Add hotbar key press test through real `InputRouter` + `InputManager`

**Files:**
- Create: `tests/integration/test_hotbar_keys.py`

---

## Phase J — Data & UI Polish (S, ~2–3h)

*Cache keys, recipe data, loading conventions.*

### J.1 `PanelWindow.wrap_text` cache key includes `color`

**Files:**
- Modify: `ui/panel_window.py:302` (`key = (text, max_width, font.get_height(), font.get_bold(), color)`)
- Test: `tests/test_wrap_text_color_cache.py`

---

### J.2 Recipe data: add `skill_affects_yield` to all chains

**Files:**
- Modify: `data/recipes.json` (add field to every recipe: `wood_chain`→`woodcutting`, `foraging_chain`→`foraging`, `metallurgy_*`→`metallurgy`, `cooking_chain`→`cooking`, `stone_chain`→`mining`, `construction_chain`→`construction`)
- Test: `tools/validate_phase3_data.py` (already checks cross-refs; run it)

---

### J.3 Unify JSON loading: all subsystems use `data.load_json`

**Files:**
- Modify: `npc/trade_system.py`, `npc/quest_system.py` (replace custom `os.path.join` loads with `from data import load_json`)
- Test: `tests/test_data_load_unified.py` (missing file raises at bootstrap)

---

### J.4 Run `tools/validate_phase3_data.py` in CI / test suite

**Files:**
- Modify: `.github/workflows/ci.yml` or `pytest.ini` (add `tools/validate_phase3_data.py` as test)
- Test: `python tools/validate_phase3_data.py` passes

---

## Phase K — Feature Work (L, multi-day, independent)

*From §11 "Recommended Next Steps" — each is a standalone feature.*

### K.1 Character / background selection on title screen

(See Phase A.14 — same work)

---

### K.2 Persist depleted resource nodes (v2 resource overlay)

**Files:**
- Modify: `save/save_system.py` (serialize `Tile.depleted` + `Tile.regrow_timer` + per-tile `ResourceNode` state)
- Modify: `world/tile_map.py` (deserialize)
- Modify: `world/resource_placer.py` (restore per-tile nodes on load)
- Test: `tests/test_resource_depletion_persist.py` (save → load → depleted state preserved)

---

### K.3 Persist monster population

**Files:**
- Modify: `save/save_system.py` (serialize `CombatSystem.monsters` state)
- Modify: `combat/combat_system.py` (deserialize)
- Test: `tests/test_monster_population_persist.py`

---

### K.4 Weather gameplay effects (movement/visibility/crafting/spawn multipliers)

(See Phase B.11 — same work)

---

### K.5 Animation clock (player/monster/NPC idle frames)

(See Phase H.1 — same work)

---

### K.6 Keybinding registry (single config-driven source)

(See Phase G.5 — same work)

---

### K.7 Combat damage formula fix + gear `tool` slot equip

**Files:**
- Modify: `combat/combat_system.py` (additive formula — Phase F.1)
- Modify: `input/panel_dispatcher.py` `_handle_gear_action` (handle `gear_type == "tool"`)
- Modify: `combat/gear.py` (ensure `GearItem.gear_type` can be `"tool"`)
- Test: `tests/test_gear_tool_slot.py`

---

## Cross-Phase Dependency Graph

```
A (Core Hygiene) ──┬──→ B (World/Seasons)
                   ├──→ C (Actions/Survival)
                   ├──→ D (Inventory/Crafting)
                   ├──→ E (Skills/Building) ← needs C.16 (CookingSkill)
                   ├──→ F (Combat/Trade)    ← needs A.2 (death handler), E.6 (smelt capacity)
                   ├──→ G (Input)           ← needs A.4 (TILE_SIZE)
                   ├──→ H (Render)          ← needs A.4, E.9 (fire_id)
                   ├──→ I (Tests)           ← needs all wiring fixes (A–G)
                   └──→ J (Data/UI)         ← needs D.12 (chain mapping), E.15 (gathering skill)

K (Features) independent; each can start after its prerequisite phase:
  K.1 needs A.14
  K.2 needs B (resource model stable)
  K.3 needs F (combat system stable)
  K.4 needs B.11
  K.5 needs H.1
  K.6 needs G.5
  K.7 needs F.1 + G.5
```

## Recommended Execution Order

1. **Phase A** (unblocks everything, ~3h)
2. **Phases B, C, D, G** in parallel (independent subsystems, ~1 day total)
3. **Phase E** (depends on C.16, D.12; ~1.5 days)
4. **Phase F** (depends on A, E; ~1.5 days)
5. **Phase H** (depends on A, E; ~0.5 day)
6. **Phase I** (depends on A–G; ~0.5 day)
7. **Phase J** (depends on D, E; ~0.5 day)
8. **Phase K** features (independent, schedule as capacity allows)

## Exit Criteria

- All 716+ tests pass
- `tools/validate_phase3_data.py` passes
- Wiring smoke test (`test_wiring_smoke.py`) passes
- No hardcoded 64, no "simplex" in docstrings, no dead code in modified files
- `typing.get_type_hints` works on all modified modules
- All trace-note findings either resolved in this plan or explicitly deferred to Phase K with issue reference