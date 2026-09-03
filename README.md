# Don't Starve RuneScape

A Python + Pygame survival game — a hybrid of *Don't Starve*'s survival
mechanics and *RuneScape*'s skill / RPG progression.

You gather resources, manage hunger and health, level up skills, craft and
smelt items, build structures, fight monsters, and trade with or recruit NPCs,
resolve quests, and manage faction standing — all over a procedurally
generated world with a seasonal cycle and weather. The game is top-down and
tile-based, rendered by Pygame at 60 FPS inside a single instance.

- **Data-driven content** — items, resources, monsters, gear, structures,
  NPCs, quests, factions, trade items and recipes live in `data/*.json`
  (plus per-skill recipe tables) and are loaded at runtime.
- **Single `Game` instance** — one central object aggregates every subsystem;
  a frame loop drives `update` → `render`, and a small state machine selects
  the active screen/panel.
- **Curated feature set** — most subsystems are implemented end to end, but a
  handful of gameplay paths are stubbed or not yet wired into the input layer
  (see [Known bugs & issues](#known-bugs--issues) and
  [Known limitations](#known-limitations)).

---

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Running](#running)
- [Testing](#testing)
- [Project overview](#project-overview)
- [Architecture](#architecture)
- [Subsystem reference](#system-reference)
  - [core / config / main](#1-core-config--main)
  - [world / seasons](#2-world--seasons)
  - [actions / survival](#3-actions--survival)
  - [skills](#4-skills)
  - [crafting / inventory](#5-crafting--inventory)
  - [building / utils](#6-building--utils)
  - [combat](#7-combat)
  - [npc](#8-npc)
  - [interactions / input](#9-interactions--input)
  - [render / camera](#10-render--camera)
  - [ui](#11-ui)
  - [data / tests / tools / assets](#12-data--tests--tools--assets)
- [Data files](#data-files)
- [Assets](#assets)
- [Tools](#tools)
- [Known bugs & issues](#known-bugs--issues)
- [Known limitations](#known-limitations)

---

## Requirements

- **Python 3.10+**
- Third-party runtime dependencies (declared in `requirements.txt`):
  - [`noise`](https://pypi.org/project/noise/) `1.2.2` — noise used by
    `world/world_gen.py` for procedural terrain generation. This is the only
    non-stdlib dependency and is required at world-generation time.
  - `pygame` `2.6.1` — the game engine (display, input, sprites, audio).

> A fresh clone without these raises `ModuleNotFoundError` (usually `noise`) at
> world-generation, so install the requirements before running the game.

### Installation

```bash
pip install -r requirements.txt
```

### Running

```bash
python main.py --seed 42
```

`--seed` (default `42`) controls procedural world generation; a fixed seed
makes worlds reproducible. The game boots to a title screen; the world is
generated asynchronously once you start from there.

### Testing

The test suite is designed to run **without a display** (no Pygame window):

```bash
python -m pytest -q
```

> At the time of writing, the suite reports **926 tests collected** (all
> passing; verified 2026-09-03). The September 2026 reliability audit and its
> fixes are tracked in `tmp/PHASE-PLAN-2026-09.md` (Phases 1–4 complete;
> Phase 5 = performance + GPU/parallel world-gen pending).
>
> The suite runs headless: with or without `SDL_VIDEODRIVER=dummy`. A
> session-scoped fixture in `tests/conftest.py` initializes Pygame once for
> the entire run.

---

## Project overview

The repository is organized as a set of focused packages, each owning one
aspect of the game. The entry point is `main.py`, which constructs a single
`Game` instance and hands it to the game loop.

| Directory | Responsibility |
|-----------|----------------|
| `main.py` | CLI entry point (`argparse`, `--seed`) and loop start |
| `config.py` | Module-level configuration constants (window size, FPS, radii, autosave interval, flavor text, …) |
| `core/` | The `Game` state container, main loop, `Player` model, save/load, the state machine, and bootstrap wiring |
| `world/` | Procedural world generation, biome registry, tile map, resource nodes, resource placement |
| `seasons/` | Season and weather systems (survival/resource modifiers, visual tints, weather effects) |
| `actions/` | The action system (woodcutting/mining progress + completion), notifications, stamina, action enums |
| `survival/` | HP/hunger survival ticks, food registry, starter pack |
| `skills/` | Skill manager and skill subpackages (see below) |
| `crafting/` | Crafting system and recipe registry |
| `inventory/` | Inventory model, item/recipe helpers |
| `building/` | Building system, construction, structures |
| `combat/` | Combat system, monsters, gear, combat UI |
| `npc/` | NPCs, factions, quests, recruitment, trade |
| `interactions/` | Interaction system, fire, NPC dialogue flows |
| `input/` | Input manager, input state, panel dispatcher, input router |
| `render/` | Sprite/tile/NPC renderers, particle system, seasonal renderer |
| `camera/` | Camera (yaw/pan) |
| `ui/` | UI panels, HUD, title screen, loading screen |
| `utils/` | Small shared helpers (e.g. structure utilities) |
| `data/` | Data-driven JSON content (items, resources, monsters, NPCs, gear, quests, factions, structures, recipes, trade, biomes, recruit definitions) |
| `assets/` | Procedurally generated PNG sprites (terrain, trees, rocks, monsters, NPCs, player, items, structures, world, UI, fonts) |
| `tests/` | pytest suite (unit + integration) |
| `tools/` | Asset generation and validation scripts |

---

## Architecture

- **Single instance.** `core/game.py:Game` is the one central object; it
  aggregates every subsystem (world, player, survival, skills, crafting,
  inventory, camera, HUD, save system, input, combat, NPCs, factions, quests,
  building, fire, seasons, weather, particles, renderers) and exposes
  `update(dt)`, `render(screen)`, and `handle_event(event)`.
- **Main loop.** `core/game_loop.py` drives the loop at `TARGET_FPS`, calling
  `update` → `render` and dispatching events via `handle_event`. `main.py` is
  the thin CLI wrapper (`argparse` + `run(game)`).
- **State machine.** `core/state.py` defines the `GameState` machine
  (TITLE → LOADING → PLAYING, plus one state per panel and ERROR).
  `Game.set_state` toggles panel visibility and drives bootstrap transitions;
  `PANEL_STATES` freezes most gameplay logic while a menu is open.
- **Lazy wiring.** `core/bootstrap.py` builds subsystems in strict dependency
  order and owns async world generation + save loading. `Game.__init__` does
  only a minimal Pygame setup plus lightweight collaborators; the heavy
  subsystems are created during world generation / save load, so the game
  starts in a deliberately "half-wired" state.
- **Data-driven.** `data/__init__.py` provides `load_json` / `load_json_list`;
  systems read `data/*.json` at runtime rather than hard-coding content. Each
  file uses a `_description`/`_note` metadata envelope followed by a keyed
  collection of records.
- **Procedural world.** `world/world_gen.py` uses `noise` (a Perlin
  `pnoise2` variant — see the note below) to generate elevation/moisture,
  classify biomes, build the tile grid, place resources, and pick a spawn
  point. Generation is fully deterministic per seed.
- **Seasons/weather.** `seasons/` drive survival/resource modifiers and a
  seasonal-tint / weather particle layer consumed by `render/`.

### One nuance on the noise library

`requirements.txt` and the `world_gen.py` docstrings describe the terrain noise
as *simplex*. The installed `noise==1.2.2` package's `pnoise2` is **Perlin**
noise (the `p` prefix denotes its periodic family), not simplex. The
documentation is misleading, though functionally irrelevant.

---

## System reference

Each subsection below summarizes one subsystem group: what it does, the key
components and file map, the data flow, and notable integration points.

### 1. core / config / main

`core/` is the central nervous system. It does not implement gameplay
mechanics; it aggregates every subsystem, drives the frame loop, manages the
discrete state machine, and handles save/load.

| File | Responsibility |
|------|----------------|
| `core/game.py` | Central `Game` aggregator: holds every subsystem, owns `update`/`render`/`handle_event`/`set_state`/`get_snapshot` |
| `core/game_loop.py` | The single `run(game)` Pygame loop (event/update/render, 60 FPS) |
| `core/player.py` | `Player` model: smooth movement (WASD camera-relative + click-to-move), tile position, proximity, damage delegation |
| `core/save_system.py` | JSON save/load, autosave, slot listing, snapshot build, restore-order restore |
| `core/state.py` | `GameState` enum (lifecycle + panels) + `PANEL_STATES` |
| `core/bootstrap.py` | Ordered factory: `initialize()` builds & wires all subsystems; `begin_world_gen`/`load_save`/`on_world_gen_complete` orchestrate the two world-entry paths |
| `config.py` | All tuning constants + data-file paths (single source of magic numbers) |
| `main.py` | argparse (`--seed`), construct `Game`, start loop |

**Key signatures.** `Game.set_state(state)`, `Game.update(dt)`,
`Game.render(screen)`, `Game.handle_event(event)`;
`Bootstrap.initialize()`; `Bootstrap.begin_world_gen()`,
`Bootstrap.load_save()`;
`SaveSystem.save(game, slot=0)`, `load(slot=0)`,
`load_into_game(save_data, game)`, `list_slots()`.

**Frame tick order (`Game.update`, PLAYING).** `survival.tick` and
`inventory.tick` run unconditionally (hunger still drains, spoilage still
progresses, under panels); the rest — `world`/`player`/`actions`/`camera`/
`combat`/`fire`/`building`/`npc`/`trade`/`quest`/`seasons`/`weather`/particles
— are gated on `PLAYING`. Autosave fires every `AUTOSAVE_INTERVAL` (300 s).

### 2. world / seasons

`world/` builds the 512×512 tile map **once at start** (regenerated from the
seed on save load); `seasons/` tick **every frame** as runtime atmospheres.

`world/world_gen.py`: a noise → elevation/moisture → biome-classification →
tile-grid → resource-placement → spawn-point pipeline under one
`generate(seed, biome_registry, season_system) -> TileMap`. Elevation is
clamped to 0–7; biomes are classified by hardcoded elevation/moisture
thresholds. `world/resource_placer.py` density-places resources with seasonal
gating and a clustering bonus.

`world/tile_map.py`: a column-major grid of `Tile` objects implementing the
depletion→regrowth state machine, elevation interpolation, slope shading, and
season-driven regrowth. `world/resource_node.py` is the harvestable model
(density/tier math, depletion, regrowth, growth stages).

`seasons/season_system.py`: the four-season cycle (spring→summer→autumn→winter)
with progress/transition state, survival & resource modifier lookups, and a
runtime availability-override mechanism. `seasons/weather_system.py`: a small
weather state machine that rolls on a timer and exposes effect multipliers.

**Data flow.** `bootstrap` loads `data/biomes.json`/`resources.json`, builds a
`BiomeRegistry` and `SeasonSystem` (before generation so tier-3/4 resource
gating is consistent), generates the world, then wires seasons/weather into
`survival`, `actions`, `TileMap`, and the render/particle systems.

### 3. actions / survival

`actions/` is the player resource-interaction layer: the full lifecycle of a
gathering action (woodcutting/mining) from interact to yield, validated and
orchestrated but not the place where skill math or inventory live.

`actions/action_system.py`: `start_action` validates prerequisites (tool,
state), builds an `ActiveAction`, advances it frame-by-frame, rolls success,
and emits a machine-readable `action_complete:{item}:{qty}:{xp}` message that
`core.game` applies to the inventory and skill manager. `actions/stamina.py`
models per-gather stamina, a 5 s exhaustion penalty, and regen.

`survival/`: `SurvivalSystem` tracks HP and hunger and turns "hunger == 0" into
a slow HP drain that can kill the player. `survival/food.py` describes what
eating does; `survival/starter_pack.py` seeds the player's first inventory
(forester/prospector/scavenger/default).

**Data flow.** `InteractSystem.handle_interact` (interactions) →
`action_system.start_action` → `Game.update` calls `update` →
`process_completion` → `inventory.add_item` + `skill_manager.add_xp`. Starvation
death routes through `survival.on_death`, which bootstrap injects as the
combat system's shared soft-death handler.

### 4. skills

`skills/` is the RPG backbone: XP/level tracking for 8 skill tracks using the
Old-Runescape (OSRS) XP formula, per-skill sub-stats, and a stat-point economy
(3 points per level + 1 wildcard per 5 total levels, non-refundable).

`skills/skill_manager.py`: `SkillData` (level 1–99, xp, stat_points, sub_stats)
and `SkillManager` (`add_xp`, `get_effective_stat`, `allocate_stat`,
`get_snapshot`, stat/wildcard awarding). `_SKILL_DEFAULTS` is the canonical set
of tracked skills and their sub-stats.

**Implemented vs. stub — the key structural fact.** The eight skill packages
fall into three categories:

| Package | `XxxSkill` class | Wired at runtime? | Where the real logic lives |
|---------|------------------|-------------------|----------------------------|
| `woodcutting/` | `WoodcuttingSkill` — implemented | **No** — never instantiated | `actions/action_system.py::_complete_gathering` |
| `mining/` | `MiningSkill` — implemented | **No** — never instantiated | `actions/action_system.py::_complete_gathering` |
| `crafting/` | `CraftingSkill` — implemented | **No** — never instantiated | `crafting/crafting_system.py` |
| `cooking/` | `CookingSkill` — implemented | Instantiated, but methods never called | `crafting/crafting_system.py::CookingSystem.cook` |
| `metallurgy/` | `MetallurgySkill` — implemented | **Yes** | `skills/metallurgy/metallurgy.py` |
| `firemaking/` | `FiremakingSkill` + `FireEntity` — implemented | **Yes** | `skills/firemaking/` |
| `intelligence/` | `IntelligenceSkill` — implemented | **Yes** | `skills/intelligence/intelligence.py` |
| `construction/` | `Construction` — implemented | **Yes** | `skills/construction/construction.py` |

So `woodcutting`, `mining`, `crafting`, and `cooking` ship fully-implemented,
documented classes that nobody invokes at runtime — the `__init__.py` files for
three of them even label them "stub", while the classes inside them are real.
The real gathering logic lives in `actions/`; the real cooking/crafting logic
lives in `crafting/`.

`construction` sub-stats are stored *under the Crafting skill* (the
`*_building_tech` stats), not as their own skill.

### 5. crafting / inventory

`inventory/` models what the player carries: a 20-slot grid, per-item stack
sizes, equipment flags, and per-item spoilage timers. `crafting/` turns input
items into output items.

`inventory/inventory.py`: `InventorySlot` (`item_id`, `quantity`,
`spoilage_remaining`, `is_equipped`); `Inventory` (`add_item` stacks into
existing slots first, `remove_item`, `has_items`, `equip_item`, `set_spoilage`,
`get_snapshot` — a frozen 20-slot list for UI).

`crafting/crafting_system.py`: the craft/cook engine. `craft()` is
deterministic (validate → consume → produce → award XP); `cook()` is
probabilistic (rolls `50 + success_rate×2`, and rolls back ingredients on
failure). `crafting/recipe_registry.py` is the unified loader/aggregator of
every `Recipe` across all data dirs.

**Data flow.** `bootstrap` builds one `RecipeRegistry`, loads the skill recipe
dirs into it, then `CraftingSystem(recipe_registry=registry)`. The crafting
panel click routes through `input/panel_dispatcher._handle_craft_click`
(deciding craft vs cook vs smelt), which applies spoilage for food and grants
XP.

### 6. building / utils

`building/` is the structure lifecycle engine: placement, removal/pickup,
HP/damage, offensive firing, and NPC guard assignment.

`building/structure.py`: `StructureDef` (blueprint) + `Structure` (placed,
HP-bearing instance). `building/building_system.py`: `place_structure`
(single placement entry point with distance/occupancy/biome/materials/level
gates), `pickup_structure`/`remove_structure`, the tick loop, NPC assignment,
and monster interaction. `skills/construction/construction.py`: the
construction sub-stat manager (placement gating, HP bonuses, material-return
rates) — the canonical copy of a class that is also stale-duplicated at
`building/construction.py` (unused dead code). `utils/structure_utils.py`:
shared proximity helpers (`is_structure_nearby`, `STATION_INTERACTION_RADIUS`).

**Offensive structures.** `building_system.tick` fires ballistas/trebuchets at
nearest monsters, delegating all damage and death handling to
`combat_system.offensive_structure_hit` — offensive firing is gated on a live
combat system being present.

### 7. combat

`combat/` is the real-time combat engine. It owns the active monster list, the
current target, floating damage numbers, and attack cooldowns.

`combat/combat_system.py`: `CombatSystem` — targeting, damage math, cooldowns,
player/NPC attacks, the shared soft-death handler `_on_player_death`, monster
registration/spawning, and the frame tick. `combat/monster.py`: a `Monster`
dataclass with an AI state machine and special behavior tags (poison/ambush/
aerial/ranged). `combat/gear.py`: `GearItem` + `PlayerGear` (weapon/armor/tool
slots + equip/unequip). `combat/combat_ui.py`: floating damage-number rendering.

**Data flow.** `bootstrap` builds `PlayerGear` (player starts unequipped) and a
`CombatSystem`, then wires `survival.on_death = combat._on_player_death` and
spawns starting monsters per the loaded `data/monsters.json` (biome lookup).
`input/router.py` selects targets on left-click; `input/panel_dispatcher.py`
handles gear equip.

### 8. npc

`npc/` implements every non-player entity and the four systems around them:

- **NPC model & spawning** (`npc.py`, `npc_system.py`, `npc_types.py`)
- **Factions & standing** (`faction_system.py`) — central standing authority,
  HUD color, faction-leader combat AI, negotiation math
- **Quests** (`quest_system.py`) — data-driven definitions, condition
  evaluation, acceptance, rewards
- **Trade** (`trade_system.py`) — buy/sell/barter with `IntelligenceSkill`
  pricing plus faction modifiers
- **Recruitment** (`recruitment.py`) — recruited NPC AI (guard/trader/assistant)

All four systems are fed by `skills/intelligence/intelligence.py` (commerce,
persuasion, trade pricing, recruitment eligibility).

**Data flow.** `bootstrap` builds NPC/trade/quest/recruitment/faction systems in
order and cross-links them. `core/game.update` ticks them in a fixed order
(NPC movement → recruits → faction leaders → trade restock → quest tracking).
`interactions/npc_flows.py` is the façade that routes NPC-panel action tuples
into the subsystems.

### 9. interactions / input

This is the front door of gameplay: raw Pygame events → normalized input →
routing → subsystem calls.

`input/input_state.py` + `input/input_manager.py`: translate `pygame` events
into a per-frame `InputState` snapshot (held movement/camera flags survive
frames; one-shot panel/interact/zoom flags last one frame). `input/router.py`:
the event router (panel toggles, hotbar, E-interact, F-fire, save, mouse
routing). `input/panel_dispatcher.py`: the typed-action hub (`dispatch`
keyboard, `dispatch_click` mouse) mapping actions to concrete subsystem calls.

`interactions/interact.py`: the E-key resource-gather flow;
`interactions/fire.py`: lighting fires + campfire proximity checks;
`interactions/npc_flows.py`: NPC panel open/close/execute façade over
trade/quest/recruit/diplomacy.

**Data flow (a sample path).** A keyboard key sets an `InputState` flag; the
router reads it, calls `game.set_state` to open/close a panel, then forwards
the event to the active panel and routes the returned action tuple through the
dispatcher into the relevant subsystem.

### 10. render / camera

`render/` owns everything drawn for the playing state; `camera/` owns the
player-centered orbital transform all renderers depend on.

`camera/camera.py`: an orbital camera with independent yaw (orbit), pitch
(tilt), zoom, and pan; `world_to_screen`/`screen_to_world` and a view rect for
culling. `render/tile_renderer.py`: 2.5D terrain quads with elevation-displaced
corners, depth sorting, slope shading, fog, and the seasonal tile-color hook.
`render/sprite_renderer.py`: billboard sprites (player/resources/monsters/
NPCs/fires/structures) with zoom scaling, seasonal tint, fog, and
depletion/regrowth sprite resolution. `render/particle_system.py`: screen-space
weather particles. `render/seasonal_renderer.py`: season palette data +
per-season tile-color lerp + a full-screen ambient overlay.

**Frame render pass (`core/game.py::render_game`).** Sky fill → terrain →
resources → player → HUD → monsters → NPCs → structures → fires → weather
particles → seasonal overlay → combat damage numbers → open UI panels.

### 11. ui

`ui/` is the presentation layer: the always-on HUD, the title/loading screens,
and the player-facing menus. Panels render game state into primitive pygame draws and
emit plain action tuples; they contain **no game logic** (all rules live in the
corresponding subsystem).

Panels: `InventoryPanel`, `SkillPanel`, `CraftingPanel`, `BuildingPanel`,
`GearPanel`, `TradePanel`, `QuestPanel`, `RecruitPanel`, `DiplomacyPanel`.
NPC panels are session-based (`open_session`/`close_session`); the five data
panels re-read live state every `render()`. `ui/hud.py` is the one always-visible
overlay (hunger/HP/faction/stamina bars, gold, notifications, hotbar, damage
flash, season/weather).

**Unified tabbed dashboard.** The five character menus (Inventory, Skills,
Crafting, Building, Gear) are hosted as tabs in one fixed-size window
(`ui/dashboard_panel.py`, state `GameState.DASHBOARD_OPEN`). `I`/`C`/`TAB`/`B`/`G`
open the dashboard at their tab; the same key or ESC closes; `←/→` (or `A`/`D`,
or clicking a tab) switch tabs. The dashboard repositions the existing panel
instances into the shared frame, so scroll position and selections survive
tab switches. NPC panels (trade/quest/recruit/diplomacy) remain separate
session-scoped windows.

**Unified panel contract.** All panels subclass `ui.panel_window.PanelWindow`,
a single reusable base class that provides:

- **Chrome & viewport** — translucent background + double-line border, title,
  optional close button; a clipped content viewport (`screen.set_clip`)
  guarantees rows never paint past the window.
- **Scrollbar** — thumb sized/positioned by `visible/total` ratio; clickable,
  draggable, plus page-up/page-down and mouse-wheel scrolling.
- **Keyboard navigation** — a single, uniformly-drawn focus highlight driven by
  WASD/arrow keys, clamped to the (possibly scrolled) content. `selection_mode`
  supports both list (`step=1`) and grid (`step=cols`) layouts.
- **Text wrapping** — `wrap_text(text, max_width)` word-wraps to the viewport
  width so body text never runs off the right edge.
- **Font registry** — shared `SysFont` cache (title/normal/small/bold) so
  panels don't instantiate their own fonts.

Concrete panels implement only `draw_contents(screen, content_rect)` and a
few small hooks (`scroll_viewport`, `select_count`, `on_key`, `on_click`,
`on_mouse_move`). The render contract is uniform:

```
draw_chrome()
screen.set_clip(content_rect)
draw_contents(screen, content_rect)
screen.set_clip(None)
draw_scrollbar()
```

This replaces the former divergent `BuildingPanel.render(self, screen, bs, sm)`
and `GearPanel.render(self, screen, pg, inv, gm)` signatures with the
standard `render(screen)` call.

### 12. data / tests / tools / assets

`data/` is the content backbone. Every file uses a **metadata + keyed-records
envelope** (`_description`/`_note` stripped by consumers). Most files are a
list under a key; `monsters.json`, `gear.json`, and `structures.json` are
dict-of-dicts. `npcs.json` is the only file with a second top-level array
(`spawn_points`).

`data/__init__.py`: the shared loader (`load_json` / `load_json_list`). Many
systems bypass it and read JSON directly via a module-relative `DATA_DIR` —
there is no single "load this file" entry point.

`tests/`: a **926-test** pytest suite (runnable under `pytest`), mostly
headless. A session-scoped fixture in `tests/conftest.py` initializes Pygame
once for the entire run. `tests/integration/` cross-module flows (full quest
accept→track→complete→reward, faction/NPC integration). `tools/`: `generate_sprites.py`
(procedural PNG generation), `validate_phase3_data.py` (cross-reference
validator), `check_init_hygiene.py` (`__init__.py` linter). `assets/sprites/`:
the generated PNG output with a documented naming/fallback scheme.

---

## Data files

All content lives in `data/` as JSON, plus per-skill recipe tables under
`skills/*/data/`.

| File | Records | Contents |
|------|---------|----------|
| `data/biomes.json` | `biomes` (6) | Biome defs for world gen: elevation range, terrain colors, environmental pressure, starting safety, resource spawns |
| `data/resources.json` | `resources` (37) | Resource-node defs: biome, tier, category, density, yield, xp, depletion, regrow, sprite key, tool requirement, seasons |
| `data/items.json` | `items` (138) | Item defs: stack size, equippable/food flags, spoilage, hunger/hp restore, sprite key |
| `data/monsters.json` | monsters (per biome) | Per-biome monster AI/stats/loot: hp/attack/defence/speed, ranges, loot table |
| `data/gear.json` | weapons (11), armor (10) | Weapons/armor bonuses: damage, attack/defence/speed bonus, required combat level, tier |
| `data/structures.json` | structures (4 cats) | Building defs grouped by sub-stat: materials, level req, biome compatibility, occupies tile |
| `data/npcs.json` | npcs (20) + spawn points (15) | NPC defs + spawn points: type, faction, dialogue, behavior, health, price modifier |
| `data/quests.json` | quests (12) | Quest defs: thresholds, conditions/fail-conditions, rewards, faction requirements |
| `data/factions.json` | factions (6) | Faction defs: leader npc, territory biomes, hostility, hostile monster types |
| `data/trade_items.json` | trade_items (43) | Merchant trade entries: buy/sell price, stock, tier, commerce requirement |
| `data/recruit_definitions.json` | recruits (3) | Optional recruit overrides: stat requirements, behaviors, intel range |
| `skills/*/data/` | recipes | Skill-driven recipes (metallurgy, cooking, intelligence, construction) + firemaking fuel table |

---

## Assets

Sprites are generated procedurally by `tools/generate_sprites.py` under
`assets/sprites/` (terrain, trees, rocks, monsters, NPCs, player, items,
structures, world). Trees and depletable resources support
`_depleted` / `_sapling` / `_young` sprite variants with shared fallbacks
(`stump.png`, `rubble.png`, `depleted_patch.png`, …).

> `tools/generate_sprites.py` is ~4,975 lines of hand-drawn primitives and is
> **not** data-driven: adding a resource in JSON does not generate a matching
> sprite. Leaf-clustering positions seed randomness from a per-process `hash()`,
> so regeneration is not guaranteed reproducible.

---

## Tools

- `tools/generate_sprites.py` — regenerates all PNG sprites.
- `tools/check_init_hygiene.py` — validates `__init__.py` hygiene (no class
  defs, ≤10-line functions, ≤80 lines).
- `tools/validate_phase3_data.py` — cross-reference integrity validator for
  Phase 3 data (items, biomes, factions, npcs, quests, trade items); exits
  non-zero on error.

---

## Known bugs & issues

The following are curated from the subsystem documentation pass. Severity is
the documentation author's assessment; "confirmed" means the code path was
traced. Each cites `file:line`. Already-fixed items are retained for history.
The current, actively-maintained ledger is `tmp/PHASE-PLAN-2026-09.md`
(September 2026 audit: 4 phases of fixes shipped, phase 5 = performance +
GPU world-gen pending).

### Still live

- 🟡 **[seasons] Weather multipliers are rolled but never applied.** `weather_system.py`
  `get_effects()` (movement/visibility/outdoor-crafting/spawn multipliers) is only
  consumed by the test suite. Weather cycles and drives particles + the HUD icon,
  but no gameplay system applies the multipliers. (Scheduled in Phase 4 of the
  September 2026 plan.)
- 🟡 **[cooking] Cooking skill math is never applied.** `skills/cooking/cooking.py` is
  instantiated (`core/bootstrap.py:229`) but none of its math methods
  (`calculate_nutrition`, `get_spoilage_modifier`, `get_success_rate_bonus`, …) have
  callers (see [Known limitations](#known-limitations)).

### Fixed (September 2026 audit — Phases 1–4)

- Crash blockers: F/F5 `AttributeError`; title-screen Continue never loading;
  foraging permanently locking the action system; trade gold stale-total
  dupe; faction-leader quests unacceptably gated; invisible trade/quest
  panels; monsters duplicated on save load; build-panel scroll crash
  (`StructureDefRegistry` vs dict). Regression tests: `tests/test_b25_*`,
  `tests/test_b26_*`, `tests/test_b27_*`, `tests/test_dashboard.py`,
  `tests/test_b28_*`.
- Combat/quest sim: monsters initiate attacks; faction melee gating;
  kill-credit-based standing; quest trade/delivery/faction-attack tracking
  wired; faction-status eligibility fixed vs `giver_faction`.
- World/economy: day/night sun-altitude curve; particle spawning + fog alpha;
  corner-shading cache fix; per-tile ecotone blends; landmark seasonal
  gating; inventory-full hardening; quest-locked recipe enforcement;
  structures/trade/npc data integrity; portable 100% pickup; structure
  attack range; per-instance guard assignment.
- UI: unified tabbed **dashboard** replaces the five character-menu windows.

### Fixed in earlier cycles (history)

Re-verified against live code; fixed as noted. Retained here for history — see
`tmp/LIVE-ISSUES.md` for the full, actively-maintained ledger.

- 🟢 **[seasons] Seasonal resources can be permanently unobtainable** (#1). — **RESOLVED**
  `world_gen.generate()` now registers a one-time `on_season_changed` callback that
  re-runs `ResourcePlacer.place()` additively on season change. `26a4eae`.
- 🟢 **[crafting] Foraging recipes grant woodcutting XP** (#7). — **RESOLVED**
  `craft()` now routes generic-craft XP to the recipe's processing-chain skill instead
  of hard-defaulting to `woodcutting`. `7332d5c`.
- 🟢 **[combat] Loot is silently dropped when the inventory is full** (#2). — **RESOLVED**
  `_monster_died` checks `add_item(...)` and reports "Inventory full — some loot was lost."
  `7332d5c`.
- 🟢 **[save] Merchant stock restored by array index** (#3). — **RESOLVED**
  `_restore_merchant_stock` matches slots on `trade_item_id` rather than position. `70d9ce6`.
- 🟢 **[render] HUD drawn before gameplay sprites** (#5). — **RESOLVED**
  `core/game.py` now renders `self.hud.render(screen)` last. `c7ba09e`.
- 🟢 **[seasons] Seasonal renderer covers only 3 of 6 biomes** — **RESOLVED** in live code:
  all six biomes (`forest, plains, desert, mountains, coastal, swamp`) now have full
  4-season palettes (`render/seasonal_renderer.py`).

### Resolved (historical)

- 🟢 **[building] Building placement is not wired into gameplay.** — **RESOLVED**
  (Phase 5, 2026-08-23). Selecting a structure enters `build_mode` (a PLAYING
  sub-state, not a new `GameState`); left-click places via
  `building_system.place_structure` (validate → consume materials → grant
  crafting XP → place), right-click/ESC cancels, invalid placement reports the
  reason and stays in mode. Construction XP is now granted.
  `tests/test_b4_building_placement.py` (11).
- 🟢 **[combat] Player melee attack is never invoked during gameplay.** — **RESOLVED**
  (Phase 4, 2026-08-23). `J` calls `combat_system.player_attack()` while PLAYING;
  `auto_lock_target` locks the nearest alive monster when none is targeted;
  monster counter-attacks are enabled (and the death-path `None` crash was
  fixed). The skill panel was rebound from `J` to `TAB` (hint updated).
  `tests/test_b5_player_attack.py` (15).
- 🟢 **`data/recipes.json` general-crafting table is missing.** — **RESOLVED**
  (Phase 1, 2026-08-23). `data/recipes.json` created (4 recipes: sticks,
  charcoal, grass_rope, paper), loaded via `recipe_registry.py:62` into the
  unified registry. `tests/test_b12_general_recipes.py`.
- 🟢 **`data/recipes.json` docstring references a non-existent file.** — **RESOLVED**
  (Phase 1, 2026-08-23); the file now exists and `recipe_registry.py` loads it.

### Low priority

- 🔵 **Stale `.pyc` files** in `skills/__pycache__/` for source that no longer exists.
- 🔵 **Panel shortcut hints contradict wired keys** (e.g. inventory hint says "C to close"
  but C opens crafting).

---

## Known limitations

These are **intentional v1 design choices**, not bugs.

- **Depleted resource nodes are not persisted across save/load (v1).** The
  world is regenerated from the seed on load; depleted nodes are not
  re-applied. A planned v2 "resource overlay" would persist depleted-node
  coordinates + regrowth timers.
- **Monster population is not saved (v1).** A fresh (seed-derived) monster
  population spawns on load.
- **`PLAYER_HP_PER_COMBAT_LEVEL = 1` is an explicit stub** (`config.py:84`).
- **Foraging maps to Woodcutting XP** (Phase-1 placeholder).
- **Some skill subpackages are stubs.** `cooking`, `crafting`, `mining`, and
  `woodcutting` skill classes are thin/no-op stubs in the wiring; their actual
  logic lives in `actions/` (woodcutting/mining) and `crafting_system.py`
  (cooking/crafting). The full skill surface is managed by
  `skills/skill_manager.py`.
