# Procedural Generation System — Investigation & Phase Plan

**Date:** 2026-08-29  
**Author:** Grok Investigation  
**Status:** Documentation Complete — Phase Plan Proposed

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current System Architecture](#current-system-architecture)
3. [Data Model Analysis](#data-model-analysis)
4. [Identified Problems](#identified-problems)
5. [Resource Value Assessment](#resource-value-assessment)
6. [Proposed Phase Plan](#proposed-phase-plan)
7. [Implementation Details](#implementation-details)
8. [Testing Strategy](#testing-strategy)

---

## Executive Summary

The current procedural generation system uses a **tier-based density multiplier** (Tier 1=1.0x, Tier 2=0.7x, Tier 3=0.4x, Tier 4=0.2x) combined with per-resource `base_density` values. However, the tier system is **effectively broken**:

- **No Tier 2 resources exist** in `resources.json`
- **Tier assignments are arbitrary** — `gold_vein` (50 XP, rare ore) is Tier 1 same as `oak_tree` (25 XP, common wood)
- **Density values don't correlate with resource value** — high-value late-game resources can be more common than early-game staples
- **Seasonal gating** works correctly but operates independently of rarity

This document proposes replacing the broken tier system with a **value-based rarity system** that maps each resource's effective "worth" (XP + crafting utility + tool gate + seasonal availability) to explicit rarity bands with calibrated density ranges.

---

## Current System Architecture

### File Structure

| File | Responsibility |
|------|----------------|
| `world/world_gen.py` | Main entry: noise → biomes → resource placement → spawn point |
| `world/resource_placer.py` | Density-based placement with seasonal gating & clustering |
| `world/resource_node.py` | Resource definition, `effective_density` property (tier × base) |
| `world/biome.py` | Biome definitions + `resource_spawns` lists |
| `world/tile_map.py` | Tile grid, regrowth timers, elevation queries |
| `data/resources.json` | 57 resource definitions |
| `data/biomes.json` | 6 biome definitions with spawn lists |
| `seasons/season_system.py` | Seasonal multipliers & availability gates |

### Generation Flow

```
generate(seed, biome_registry, season_system)
    ├── _generate_elevation_map()      # Perlin noise → 0-7 elevation
    ├── _generate_moisture_map()       # Independent Perlin → 0.0-1.0 moisture
    ├── classify_biome()               # elevation + moisture → biome_id
    ├── _build_tile_grid()             # TileMap with biome/elevation/color
    ├── ResourcePlacer(...).place()    # ← CORE PLACEMENT LOGIC
    ├── _wire_seasonal_replacement()   # Re-run placement on season change
    └── _find_spawn_point()            # Temperate, elev 1-3, resource-rich
```

### ResourcePlacer.place() — Core Algorithm

```python
for each tile (x, y):
    biome_id = tile.biome.id
    for resource_id in biome.resource_spawns:
        if resource_id not in available_this_season: continue
        resource = cache[resource_id]
        if tile already has resource: continue
        
        density = resource.effective_density           # base_density × TIER_MULTIPLIER[tier]
        density *= season_system.get_resource_multiplier(resource.category)  # seasonal
        density += clustering_bonus(tile, resource_id) # 0.02 if same resource adjacent
        
        if rng.random() < density:
            tile.resource_node = copy(resource)
```

### Tier Density Multipliers (Module Constant)

```python
TIER_DENSITY_MULTIPLIER = {1: 1.0, 2: 0.7, 3: 0.4, 4: 0.2}
```

### Seasonal Multipliers (from SeasonSystem)

| Category | Spring | Summer | Autumn | Winter |
|----------|--------|--------|--------|--------|
| herbs    | 1.2    | 1.0    | 1.3    | 0.5    |
| water    | 1.1    | 0.8    | 1.0    | 0.6    |
| wood     | 1.0    | 1.1    | 0.9    | 0.7    |
| stone    | 1.0    | 1.0    | 1.1    | 1.0    |
| ore      | 0.9    | 1.0    | 1.0    | 0.8    |

---

## Data Model Analysis

### Resource Categories & Counts (from `resources.json`)

| Category | Count | Tier 1 | Tier 3 | Tier 4 |
|----------|-------|--------|--------|--------|
| wood     | 11    | 9      | 0      | 2      |
| ore      | 14    | 8      | 4      | 2      |
| herb     | 10    | 8      | 0      | 0      |
| water    | 2     | 2      | 0      | 0      |
| stone    | 3     | 3      | 0      | 0      |
| special  | 25    | 18     | 3      | 4      |
| **Total**| **65**| **46** | **7**  | **8**  |

### Tier Distribution — **The Core Problem**

```
Tier 1: 46 resources (71%) — includes both oak_tree AND gold_vein + 6 new trees
Tier 2: 0 resources  (0%)  — EMPTY TIER
Tier 3: 7 resources  (11%) — void_crystal, obsidian_vein, dragonbone, mithril_vein, silk_nest, amber_deposit, moonstone_deposit, ghost_iron_deposit
Tier 4: 8 resources  (12%) — star_metal, void_essence, phoenix_feather, ancient_rune, elder_wood, celestial_crystal, (etc.)
```

**Tier 2 is completely unused.** The tier system was clearly designed for 4 tiers but only 3 are populated, and the Tier 1 bucket is a dumping ground for everything from "Grass Patch" (5 XP) to "Gold Vein" (50 XP). The 6 new tree variants (all Tier 1) further exacerbate the Tier 1 overcrowding.

### Resource Value Indicators (Current)

Each resource has multiple value signals that are **not** used for spawn rarity:

| Field | Purpose | Range in Data |
|-------|---------|---------------|
| `xp_reward` | Skill XP on harvest | 5.0 – 120.0 |
| `yield_quantity` | Items per harvest | 1 (mostly) |
| `depletion_count` | Harvests before regrow | -1 (infinite) – 8 |
| `regrow_time` | Seconds to regrow | 0 – 2500 |
| `requires_tool` | Tool gate (axe/pickaxe/none) | axe, pickaxe, null |
| `seasons_available` | Seasonal gate | [], or 1-3 seasons |
| `category` | Seasonal multiplier bucket | wood, ore, herb, water, stone, special |
| `base_density` | Raw placement weight | 0.005 – 0.20 |

### Biome Resource Lists

| Biome | Mega-Cluster | Resources (count) | Notable |
|-------|--------------|-------------------|---------|
| forest | temperate | 13 | oak, birch, maple, pine, berry, herb, fiber, silk_nest(T3), phoenix_feather(T4), elder_wood(T4) |
| plains | temperate | 3 | grass, wheat, water |
| coastal | temperate | 5 | driftwood, shell, fish, salt, celestial_crystal(T4) |
| swamp | dangerous | 8 | peat, toxic_reed, herb, water, willow, reed_bed, dragonbone(T3), void_essence(T4) |
| mountains | extreme | 14 | iron, copper, tin, gold, stone, gem, spruce, void_crystal(T3), obsidian(T3), mithril(T3), moonstone(T3), ghost_iron(T3), star_metal(T4), ancient_rune(T4) |
| desert | extreme | 6 | sand, salt_crystal, cactus, rare_ore, amber_deposit(T3), dead_tree |

**Mountains biome has 13 resources** — the most by far — including 6 tier 3/4 resources. This creates a "mountains = late game" dynamic but with no spawn control beyond density.

---

## Identified Problems

### P1: Broken Tier System (Critical)
- **Tier 2 empty** — 4-tier design with only 3 tiers used
- **Tier 1 overloaded** — 70% of resources share the same density multiplier
- **No semantic meaning** — Tier doesn't correlate with progression, value, or rarity

### P2: No Value-Based Rarity (Critical)
- `gold_vein` (50 XP, pickaxe, 3 depletions, 600s regrow, base_density=0.02) = Tier 1 (1.0x) → effective 0.02
- `oak_tree` (25 XP, axe, 4 depletions, 180s regrow, base_density=0.15) = Tier 1 (1.0x) → effective 0.15
- `gemstone` (60 XP, pickaxe, 2 depletions, 900s regrow, base_density=0.01) = Tier 1 (1.0x) → effective 0.01
- **Result:** Gemstone is 15× rarer than oak but same "tier" — tier tells you nothing

### P3: base_density Is Arbitrary (High)
- Values range 0.005–0.20 with no documented calibration
- No formula linking density to value indicators
- Designer must guess numbers; playtest reveals problems late

### P4: Seasonal Gating ≠ Rarity (Medium)
- Winter-only resources (mithril, star_metal, ghost_iron, ancient_rune) get placed 25% of the year
- But their *density* when placed is unchanged — a winter-only Tier 4 resource at 0.005 base is still ultra-rare even in winter
- No "seasonal compensation" — resources available fewer seasons don't get density boosts

### P5: Clustering Is Weak (Low)
- Only 0.02 bonus for orthogonal same-resource neighbor
- No support for: biome-transition clusters, resource veins, gradient distributions
- Single-tile placement — no multi-tile nodes (large trees, ore veins)

### P6: No Progression-Aware Spawning (Medium)
- Spawn point searches for "resource-rich" but doesn't ensure early-game resources nearby
- Late-game resources (star_metal) can spawn near start if mountains biome reaches low elevation
- No "starter zone" guarantee

### P7: No Multi-Tile/Veins (Low)
- All resources are single-tile
- Real ore veins, tree clusters, water bodies would feel more natural

### P8: Heightmap & Shading Limitations (Medium)
- **Elevation resolution too coarse**: Only 8 elevation levels (0–7) from Perlin noise quantization, limiting terrain variety
- **No ridgeline/valley detection**: Perlin noise creates smooth hills but no sharp geological features
- **Shading is flat**: Simple NW light dot product with single `SHADING_STRENGTH` constant; no ambient occlusion, no rim lighting, no seasonal variation
- **No erosion simulation**: Terrain lacks realistic water flow patterns, alluvial fans, scree slopes
- **Cliff/ledge rendering missing**: Sharp elevation changes (delta > 2) render as smooth slopes instead of visible cliffs
- **No biome-specific terrain texturing**: All biomes use same noise parameters; mountains should be jagged, plains smooth
- **Elevation-band biome classification is rigid**: Hard thresholds create visible biome boundaries instead of natural transitions

---

## Resource Value Assessment

### Proposed Value Formula

```
Effective_Value = Base_Value × Tool_Gate × Season_Availability × Regrowth_Penalty

Base_Value = xp_reward × yield_quantity × (1 / depletion_count)  [infinite = 1.0]
Tool_Gate = 1.5 if requires_tool else 1.0  (tool = progression gate)
Season_Availability = 4 / len(seasons_available) if seasons_available else 1.0
Regrowth_Penalty = min(1.0, 300 / regrow_time)  (fast regrow = more available)
```

### Calculated Value Tiers (Approximate)

| Resource | XP | Tool | Seasons | Regrow | Base_Value | Effective_Value | Proposed Rarity |
|----------|-----|------|---------|--------|------------|-----------------|-----------------|
| grass_patch | 5 | none | all | 60s | 25 | ~15 | **Common** |
| water_source | 0 | none | all | 0s (∞) | ∞ | ∞ | **Ubiquitous** (special) |
| oak_tree | 25 | axe | all | 180s | 25 | ~25 | **Common** |
| iron_rock | 35 | pickaxe | all | 300s | 35 | ~52 | **Common** |
| gold_vein | 50 | pickaxe | all | 600s | 50 | ~75 | **Uncommon** |
| gemstone | 60 | pickaxe | all | 900s | 60 | ~90 | **Uncommon** |
| silk_nest | 55 | none | Sp,Su | 900s | 55 | ~110 | **Rare** |
| void_crystal | 80 | pickaxe | Sp,Su,Au | 1500s | 80 | ~160 | **Rare** |
| mithril_vein | 80 | pickaxe | Wi only | 1500s | 80 | ~320 | **Epic** |
| star_metal | 100 | pickaxe | Wi only | 2000s | 100 | ~400 | **Epic** |
| void_essence | 110 | none | Au,Wi | 2200s | 110 | ~440 | **Epic** |
| phoenix_feather | 90 | none | Sp only | 2500s | 90 | ~360 | **Epic** |
| ancient_rune | 120 | pickaxe | Wi only | 2500s | 120 | ~480 | **Legendary** |
| elder_wood | 95 | axe | Sp,Su | 2000s | 95 | ~190 | **Rare** |
| celestial_crystal | 115 | pickaxe | Su only | 2500s | 115 | ~460 | **Legendary** |

### Proposed Rarity Bands

| Rarity | Density Range | Example Resources | Seasons Available | Typical Use |
|--------|---------------|-------------------|-------------------|-------------|
| **Ubiquitous** | 0.15–0.30 | water_source, grass_patch | All | Survival basics |
| **Common** | 0.08–0.15 | oak_tree, iron_rock, fiber_plant, berry_bush | All | Early game staples |
| **Uncommon** | 0.03–0.08 | copper_rock, gold_vein, gemstone, tin_rock | All | Mid-game progression |
| **Rare** | 0.01–0.03 | void_crystal, obsidian_vein, silk_nest, elder_wood, moonstone | 2-3 seasons | Late-game crafting |
| **Epic** | 0.003–0.01 | mithril_vein, ghost_iron, dragonbone, void_essence, phoenix_feather | 1-2 seasons | End-game gear |
| **Legendary** | 0.001–0.003 | star_metal, ancient_rune, celestial_crystal | 1 season | Ultimate items |

---

## Proposed Phase Plan

### Phase 1: Data Model Refactor (Foundation)
**Goal:** Replace tier system with explicit rarity system in data files.

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Add `rarity` field to each resource in `resources.json` (enum: ubiquitous, common, uncommon, rare, epic, legendary) | `data/resources.json` |
| 1.2 | Remove `tier` field from resources (or deprecate) | `data/resources.json` |
| 1.3 | Add `rarity_density_range` config in `config/constants.py` mapping rarity → (min_density, max_density) | `config/constants.py` |
| 1.4 | Update `ResourceNode.from_dict()` to read `rarity` and compute `effective_density` from calibrated range | `world/resource_node.py` |
| 1.5 | Remove `TIER_DENSITY_MULTIPLIER` constant | `world/resource_node.py` |

**Validation:** All 57 resources have sensible rarity assignments; density falls in expected range.

---

### Phase 2: Placement Engine Overhaul (Core)
**Goal:** New placement algorithm using rarity bands + biome affinity + progression zones.

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Replace `ResourcePlacer._compute_density()` with rarity-based density lookup | `world/resource_placer.py` |
| 2.2 | Add biome affinity weights: each resource gets `biome_affinity: dict[biome_id, float]` (default 1.0) | `data/resources.json`, `world/resource_placer.py` |
| 2.3 | Implement **progression zones**: inner ring (spawn ±30 tiles) = common-only; mid ring = +uncommon; outer = +rare/epic | `world/world_gen.py`, `world/resource_placer.py` |
| 2.4 | Add **vein/cluster placement** for ore/stone: place 2-5 adjacent tiles as a group | `world/resource_placer.py` |
| 2.5 | Seasonal compensation: resources with `seasons_available` get density × (4 / num_seasons) when in-season | `world/resource_placer.py` |

**Validation:** Distribution heatmaps show expected gradients; starter zone has ≥90% common resources.

---

### Phase 3: Advanced World Gen Features (Polish)
**Goal:** Natural-feeling worlds with varied resource distributions.

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | **Biome transition zones**: blend resource lists at biome borders (e.g., forest→mountains transition has both wood + ore) | `world/world_gen.py`, `world/resource_placer.py` |
| 3.2 | **Resource veins**: multi-tile placement for ore/stone (3-7 tiles in rough line/blob) | `world/resource_placer.py`, `world/resource_node.py` |
| 3.3 | **Poisson disc sampling** for common resources (prevents clumping, ensures coverage) | `world/resource_placer.py` |
| 3.4 | **Landmark resources**: guaranteed 1-2 special nodes per biome region (e.g., one ancient_rune per mountains region) | `world/world_gen.py` |
| 3.5 | **Config-driven density profiles**: "casual", "standard", "hardcore" presets in constants | `config/constants.py` |

**Validation:** Visual inspection of generated maps; resource counts per biome match design targets.

---

### Phase 4: Integration & Balancing (Live Ops)
**Goal:** Tuning based on playtest data; tooling for designers.

| Task | Description | Files |
|------|-------------|-------|
| 4.1 | **Analytics hook**: log resource placement counts per world gen for telemetry | `world/resource_placer.py` |
| 4.2 | **Designer tool**: CLI script to simulate 1000 worlds and output resource density CSV | `tools/analyze_resource_distribution.py` |
| 4.3 | **Dynamic density scaling**: adjust global density multiplier based on player count (future MP) | `world/resource_placer.py` |
| 4.4 | **Regrowth tuning**: tie regrow_time to rarity (rarer = slower regrow) — already mostly true | `data/resources.json` |
| 4.5 | **Documentation**: write designer guide for adding new resources with correct rarity | `docs/resource-design-guide.md` |

**Validation:** Playtest feedback; analytics show target resources/player/hour.

---

### Phase 5: Heightmap & Terrain Generation Overhaul
**Goal:** Realistic, varied terrain with geological features.

| Task | Description | Files |
|------|-------------|-------|
| 5.1 | **Multi-octave elevation with ridgeline preservation**: Use domain-warping + ridge noise for sharp ridges/valleys; separate base elevation from detail noise | `world/world_gen.py` |
| 5.2 | **Erosion simulation (hydraulic/thermal)**: Fast GPU-style cellular automaton for water flow, sediment transport, talus formation; run 10-50 iterations post-generation | `world/world_gen.py` (new `erosion.py`) |
| 5.3 | **Biome-specific noise parameters**: Mountains = high frequency + ridged; Plains = low frequency + billow; Swamps = low elevation + high moisture; Deserts = dune noise | `world/world_gen.py`, `config/constants.py` |
| 5.4 | **Soft biome transitions**: Replace hard elevation thresholds with weighted blending using moisture + elevation gradients; add ecotone biome variants | `world/world_gen.py`, `world/biome.py` |
| 5.5 | **Cliff/ledge detection**: Tag elevation deltas > 2 for special rendering; add scree/scree slope tiles at cliff bases | `world/tile_map.py`, `render/tile_renderer.py` |
| 5.6 | **Water body generation**: River networks from erosion flow maps; lakes in depressions; coastal smoothing | `world/world_gen.py` |
| 5.7 | **Configurable elevation resolution**: 16/32/64 levels via `ELEVATION_LEVELS` config; auto-scale Z_SCALE | `config/constants.py`, `world/tile_map.py` |

**Validation:** Generated worlds show distinct geological features; biome boundaries feel organic; cliffs render correctly.

---

### Phase 6: Advanced Shading & Lighting
**Goal:** Cinematic terrain lighting with depth and atmosphere.

| Task | Description | Files |
|------|-------------|-------|
| 6.1 | **Multi-directional lighting**: Replace single NW light with configurable sun position (time-of-day); add ambient sky light | `world/tile_map.py`, `config/constants.py` |
| 6.2 | **Ambient occlusion (SSAO-style)**: Pre-bake corner occlusion from elevation neighbors; store per-tile AO factor | `world/tile_map.py`, `render/tile_renderer.py` |
| 6.3 | **Rim lighting / fresnel**: Brighten slopes facing camera at grazing angles for depth perception | `render/tile_renderer.py` |
| 6.4 | **Seasonal lighting variation**: Winter = cooler, lower sun; Summer = warmer, higher sun; Autumn = golden hour tint | `seasons/season_system.py`, `world/tile_map.py` |
| 6.5 | **Volumetric fog integration**: Fog density varies with elevation (valleys foggier); height-based fog planes | `render/tile_renderer.py`, `seasons/weather_system.py` |
| 6.6 | **Dynamic weather lighting**: Cloud shadows, rain darkening, snow brightening; lightning flashes | `render/tile_renderer.py`, `seasons/weather_system.py` |
| 6.7 | **Configurable shading presets**: "stylized", "realistic", "performance" presets in constants | `config/constants.py` |

**Validation:** Terrain reads clearly at all zoom levels; seasonal mood conveyed through lighting; performance within budget.

### Phase 1 — Code Changes

#### `data/resources.json` — Add `rarity` Field

```json
{
  "id": "oak_tree",
  "rarity": "common",
  "base_density": 0.12,
  ...
},
{
  "id": "gold_vein",
  "rarity": "uncommon",
  "base_density": 0.05,
  ...
},
{
  "id": "mithril_vein",
  "rarity": "epic",
  "base_density": 0.005,
  "seasons_available": ["winter"],
  ...
}
```

> **Note:** `base_density` becomes a *designer-tunable override within the rarity band*. The system clamps it to the band's min/max.

#### `config/constants.py` — Rarity Density Bands

```python
# Rarity → (min_density, max_density) for base_density clamping
RARITY_DENSITY_RANGE = {
    "ubiquitous": (0.15, 0.30),   # water, grass
    "common":     (0.08, 0.15),   # oak, iron, fiber, berry
    "uncommon":   (0.03, 0.08),   # copper, gold, gem, tin
    "rare":       (0.01, 0.03),   # void_crystal, obsidian, silk, elder_wood, moonstone
    "epic":       (0.003, 0.01),  # mithril, ghost_iron, dragonbone, void_essence, phoenix
    "legendary":  (0.001, 0.003), # star_metal, ancient_rune, celestial_crystal
}
```

#### `world/resource_node.py` — New `effective_density`

```python
from config import RARITY_DENSITY_RANGE

@dataclass
class ResourceNode:
    # ... existing fields ...
    rarity: str = "common"  # NEW: ubiquitous, common, uncommon, rare, epic, legendary
    biome_affinity: dict[str, float] = field(default_factory=dict)  # NEW
    
    @property
    def effective_density(self) -> float:
        """Density clamped to rarity band, scaled by biome affinity."""
        min_d, max_d = RARITY_DENSITY_RANGE.get(self.rarity, (0.01, 0.05))
        # Clamp base_density to rarity band
        clamped = max(min_d, min(max_d, self.base_density))
        return clamped
```

#### `world/resource_placer.py` — Updated `_compute_density`

```python
def _compute_density(self, resource: ResourceNode, tile: Tile, biome_id: str, tile_map: TileMap) -> float:
    density = resource.effective_density
    
    # Biome affinity (default 1.0)
    density *= resource.biome_affinity.get(biome_id, 1.0)
    
    # Seasonal multiplier
    if self.season_system is not None:
        try:
            density *= self.season_system.get_resource_multiplier(resource.category)
        except Exception:
            pass
    
    # Seasonal compensation: boost density for season-gated resources when in-season
    if resource.seasons_available and self.season_system is not None:
        if self.season_system.current_season in resource.seasons_available:
            density *= (4.0 / len(resource.seasons_available))  # 4 seasons total
    
    # Clustering bonus
    density += self._get_clustering_bonus(tile, resource.resource_id, tile_map)
    
    return density
```

---

### Phase 2 — Progression Zones

#### Concept: Distance-from-Spawn Gating

```
Spawn Point (0,0)
    │
    ├─ Zone 0: 0-30 tiles   → Common + Ubiquitous only
    ├─ Zone 1: 30-80 tiles  → + Uncommon
    ├─ Zone 2: 80-150 tiles → + Rare
    └─ Zone 3: 150+ tiles   → + Epic + Legendary
```

#### Implementation in `ResourcePlacer.place()`

```python
def place(self, tile_map: TileMap) -> None:
    # Precompute spawn distance for each tile
    spawn_x, spawn_y = tile_map.spawn_x, tile_map.spawn_y
    tile_distances = {}
    for x in range(tile_map.width):
        for y in range(tile_map.height):
            dx, dy = x - spawn_x, y - spawn_y
            tile_distances[(x, y)] = math.sqrt(dx*dx + dy*dy)
    
    # Rarity → max zone
    RARITY_MAX_ZONE = {
        "ubiquitous": 3, "common": 3, "uncommon": 2, 
        "rare": 1, "epic": 0, "legendary": 0
    }
    
    for x in range(tile_map.width):
        for y in range(tile_map.height):
            tile = tile_map.tiles[x][y]
            dist = tile_distances[(x, y)]
            zone = 0 if dist < 30 else 1 if dist < 80 else 2 if dist < 150 else 3
            
            for resource_id in tile.biome.resource_spawns:
                resource = self._resource_cache[resource_id]
                if RARITY_MAX_ZONE.get(resource.rarity, 3) < zone:
                    continue  # Too rare for this zone
                # ... placement logic ...
```

---

### Phase 3 — Vein/Cluster Placement

#### Multi-Tile Vein Algorithm (for ore/stone categories)

```python
def _try_place_vein(self, resource: ResourceNode, start_tile: Tile, tile_map: TileMap) -> bool:
    """Place a vein of 3-7 connected tiles for ore/stone resources."""
    if resource.category not in ("ore", "stone"):
        return False
    
    vein_size = self.rng.randint(3, 7)
    vein_tiles = [start_tile]
    current = start_tile
    
    for _ in range(vein_size - 1):
        # Random walk: prefer continuing direction, avoid doubling back
        neighbors = tile_map.get_neighbors(current)
        valid = [n for n in neighbors 
                 if n.resource_node is None 
                 and n.biome.id == current.biome.id]
        if not valid:
            break
        current = self.rng.choice(valid)
        vein_tiles.append(current)
    
    if len(vein_tiles) >= 3:
        for t in vein_tiles:
            t.resource_node = replace(resource)
        return True
    return False
```

---

## Testing Strategy

### Unit Tests (Add to `tests/`)

| Test | Description |
|------|-------------|
| `test_rarity_density_clamping` | Verify `effective_density` clamps to rarity band |
| `test_biome_affinity_modifies_density` | Resource with affinity=2.0 in preferred biome gets 2× density |
| `test_progression_zones_block_rare_near_spawn` | No epic/legendary within 30 tiles of spawn |
| `test_seasonal_compensation_boost` | Winter-only resource in winter gets 4× density boost |
| `test_vein_placement_creates_multi_tile_nodes` | Ore veins place 3-7 connected tiles |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_resource_distribution_heatmap` | Generate 100 worlds, verify per-rarity counts match targets ±20% |
| `test_starter_zone_resources` | Spawn area has ≥5 common wood, ≥3 common ore, ≥1 water within 20 tiles |
| `test_biome_transition_blending` | Forest→mountains border has both wood and ore resources |
| `test_seasonal_availability_cycle` | All 14 season-gated resources appear in their season over 4-season cycle |

### Designer Tools

```bash
# tools/analyze_resource_distribution.py
python -m tools.analyze_resource_distribution --worlds 1000 --output dist.csv
# Output: rarity, biome, season, mean_count, std_dev, min, max
```

---

## Migration Checklist

- [ ] Phase 1: Update all 65 resources in `resources.json` with `rarity` field
- [ ] Phase 1: Add `RARITY_DENSITY_RANGE` to `config/constants.py`
- [ ] Phase 1: Update `ResourceNode` dataclass and `from_dict()`
- [ ] Phase 1: Remove `TIER_DENSITY_MULTIPLIER` and `tier` field usage
- [ ] Phase 2: Rewrite `ResourcePlacer._compute_density()`
- [ ] Phase 2: Add biome affinity to resources.json (optional, can default to 1.0)
- [ ] Phase 2: Implement progression zones in `ResourcePlacer.place()`
- [ ] Phase 2: Add vein placement for ore/stone
- [ ] Phase 3: Add biome transition blending
- [ ] Phase 3: Add Poisson disc for common resources
- [ ] Phase 3: Add landmark guaranteed placement
- [ ] Phase 4: Add analytics hooks and designer analysis tool
- [ ] Phase 5: Multi-octave elevation with ridgeline preservation
- [ ] Phase 5: Erosion simulation (hydraulic/thermal)
- [ ] Phase 5: Biome-specific noise parameters
- [ ] Phase 5: Soft biome transitions with ecotones
- [ ] Phase 5: Cliff/ledge detection and rendering
- [ ] Phase 5: Water body generation (rivers, lakes)
- [ ] Phase 5: Configurable elevation resolution
- [ ] Phase 6: Multi-directional lighting + time-of-day
- [ ] Phase 6: Ambient occlusion (SSAO-style)
- [ ] Phase 6: Rim lighting / fresnel
- [ ] Phase 6: Seasonal lighting variation
- [ ] Phase 6: Volumetric fog integration
- [ ] Phase 6: Dynamic weather lighting
- [ ] Phase 6: Configurable shading presets
- [ ] All phases: Run full test suite, verify no regressions
- [ ] All phases: Playtest 5+ worlds, verify feel

---

## Appendix: Current Resource Rarity Assignments (Proposed)

| Resource | Current Tier | Proposed Rarity | Reasoning |
|----------|--------------|-----------------|-----------|
| water_source | 1 | ubiquitous | Infinite, essential, no tool |
| grass_patch | 1 | ubiquitous | High density (0.20), fast regrow, no tool |
| oak_tree | 1 | common | Staple wood, axe gate, good regrow |
| **birch_tree** | **1** | **common** | **Forest variety, white bark, paper crafts** |
| **maple_tree** | **1** | **common** | **Syrup potential, fine crafts** |
| **pine_tree** | **1** | **common** | **Resinous, bow crafting** |
| fiber_plant | 1 | common | High density (0.12), no tool, fast regrow |
| berry_bush | 1 | common | Food source, no tool, medium regrow |
| herb | 1 | common | Crafting staple, no tool |
| driftwood | 1 | common | Coastal wood, no tool |
| iron_rock | 1 | common | Staple ore, pickaxe gate |
| copper_rock | 1 | uncommon | Mid-game ore, lower density (0.05) |
| tin_rock | 1 | uncommon | Bronze ingredient, density 0.06 |
| stone_quarry | 1 | common | High depletion (8), density 0.10 |
| sand_deposit | 1 | common | Desert staple, high density (0.12) |
| peat_mound | 1 | common | Swamp fuel, density 0.12 |
| toxic_reed | 1 | common | Swamp herb, density 0.10 |
| salt_deposit | 1 | uncommon | Coastal, density 0.03 |
| salt_crystal | 1 | uncommon | Desert, density 0.05 |
| cactus | 1 | uncommon | Desert food, density 0.08 |
| fish_spot | 1 | uncommon | Coastal food, density 0.05 |
| shell_beach | 1 | common | Coastal crafting, density 0.10 |
| gold_vein | 1 | uncommon | Valuable ore, low density (0.02) |
| rare_ore | 1 | uncommon | Desert ore, density 0.02 |
| gemstone | 1 | rare | Very low density (0.01), high XP (60) |
| **spruce_tree** | **1** | **uncommon** | **High-altitude, durable wood** |
| **willow_tree** | **1** | **uncommon** | **Swamp/coastal, flexible wood** |
| **dead_tree** | **1** | **uncommon** | **Desert rare, direct charcoal source** |
| **reed_bed** | **1** | **common** | **Swamp herb, paper crafting unlock** |
| void_crystal | 3 | rare | T3, 3 seasons, density 0.01 |
| obsidian_vein | 3 | rare | T3, 2 seasons, density 0.01 |
| moonstone_deposit | 3 | rare | T3, all seasons, density 0.01 |
| silk_nest | 3 | rare | T3, 2 seasons, no tool, density 0.02 |
| elder_wood | 4 | rare | T4, 2 seasons, axe, density 0.01 |
| dragonbone | 3 | epic | T3, 2 seasons, pickaxe, density 0.02 |
| mithril_vein | 3 | epic | T3, winter only, density 0.01 |
| ghost_iron_deposit | 3 | epic | T3, winter only, density 0.01 |
| amber_deposit | 3 | epic | T3, 2 seasons, density 0.02 |
| void_essence | 4 | epic | T4, 2 seasons, very low density (0.005) |
| phoenix_feather | 4 | epic | T4, spring only, density 0.005 |
| star_metal | 4 | legendary | T4, winter only, density 0.01 |
| ancient_rune | 4 | legendary | T4, winter only, density 0.005 |
| celestial_crystal | 4 | legendary | T4, summer only, density 0.005 |

---

## Next Steps

1. **Review this document** — confirm rarity assignments match your design intent
2. **Prioritize phases** — Phase 1+2 are critical; Phase 3+4 are polish; Phase 5+6 are major visual upgrades
3. **Assign ownership** — who updates `resources.json` (65 entries)?
4. **Create tracking issues** — one per phase for project management
5. **Schedule playtest** — after Phase 2 complete, before Phase 3
6. **Prototype heightmap** — Phase 5 needs R&D for erosion algorithm performance

---

*End of Investigation Document*