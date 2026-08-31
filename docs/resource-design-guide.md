# Resource Design Guide

**Version:** 1.0  
**Last Updated:** 2026-08-30  
**For:** Game designers adding new resources to `data/resources.json`

---

## Overview

This guide explains how to correctly configure new resources in `resources.json` so they integrate properly with the procedural generation system. The system uses a **rarity-based density clamping** model where each resource's `base_density` is clamped to a predefined range based on its `rarity` tier.

---

## Rarity System

### Rarity Tiers & Density Ranges

| Rarity | Density Range (clamped) | Typical Use | Examples |
|--------|------------------------|-------------|----------|
| **Ubiquitous** | 0.15 – 0.30 | Survival essentials, infinite or near-infinite | `water_source`, `grass_patch` |
| **Common** | 0.08 – 0.15 | Early-game staples, no/few tool requirements | `oak_tree`, `iron_rock`, `berry_bush`, `fiber_plant` |
| **Uncommon** | 0.03 – 0.08 | Mid-game progression, tool-gated | `copper_rock`, `gold_vein`, `tin_rock`, `spruce_tree` |
| **Rare** | 0.01 – 0.03 | Late-game crafting, seasonal or tool-gated | `gemstone`, `void_crystal`, `silk_nest`, `elder_wood` |
| **Epic** | 0.003 – 0.01 | End-game gear, 1-2 seasons only | `mithril_vein`, `ghost_iron_deposit`, `dragonbone` |
| **Legendary** | 0.001 – 0.003 | Ultimate items, single season only | `star_metal`, `ancient_rune`, `celestial_crystal` |

### How Density Clamping Works

```python
# In ResourceNode.effective_density property:
min_d, max_d = RARITY_DENSITY_RANGE[rarity]
clamped = max(min_d, min(max_d, base_density))
return clamped
```

Your `base_density` in JSON acts as a **designer override within the rarity band**. The system clamps it to the min/max for that rarity. This ensures:
- You can fine-tune relative abundance within a tier
- No resource can exceed its tier's bounds (prevents balance breaks)
- Adding new resources won't accidentally make them too common/rare

---

## Required Fields

Every resource in `resources.json` **must** include these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (snake_case, e.g., `iron_rock`) |
| `name` | string | Human-readable name (e.g., "Iron Rock") |
| `biome` | string | Primary biome: `forest`, `plains`, `coastal`, `swamp`, `mountains`, `desert` |
| `tier` | int | Legacy field (1-4), kept for compatibility. Set to 1 for new resources. |
| `rarity` | string | **Required:** One of `ubiquitous`, `common`, `uncommon`, `rare`, `epic`, `legendary` |
| `category` | string | One of: `wood`, `ore`, `herb`, `water`, `stone`, `special` |
| `base_density` | float | Placement weight (will be clamped to rarity range) |
| `yield_item` | string | Item ID produced on harvest (must exist in `items.json`) |
| `yield_quantity` | int | Base quantity per harvest (usually 1) |
| `xp_reward` | float | Skill XP granted on harvest |
| `depletion_count` | int | Harvests before depletion. `-1` = infinite (e.g., water) |
| `regrow_time` | float | Seconds to regrow after full depletion. `0` = instant/no regrow needed |
| `sprite_key` | string | Path to sprite (e.g., `rocks/iron`, `trees/oak`) |
| `requires_tool` | string/null | `"axe"`, `"pickaxe"`, or `null` for no tool |

---

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `biome_affinity` | object | `{}` | Per-biome density multipliers. Keys: biome IDs. Values: float multipliers (default 1.0). |
| `seasons_available` | array | `[]` (all seasons) | List of seasons this resource spawns in. e.g., `["winter"]`, `["spring", "summer"]`. Empty = all seasons. |

---

## Biome Affinity Guide

`biome_affinity` lets you control where a resource prefers to spawn. The multiplier is applied to the clamped density.

### Recommended Affinity Patterns

**Forest Wood:**
```json
"biome_affinity": {
  "forest": 1.5,
  "plains": 0.5,
  "coastal": 0.3,
  "mountains": 0.2,
  "swamp": 0.1,
  "desert": 0.0
}
```

**Mountain Ore:**
```json
"biome_affinity": {
  "mountains": 2.0,
  "desert": 0.5,
  "forest": 0.1,
  "plains": 0.1,
  "coastal": 0.1,
  "swamp": 0.1
}
```

**Coastal Special:**
```json
"biome_affinity": {
  "coastal": 2.0,
  "swamp": 0.5,
  "plains": 0.1,
  "forest": 0.0,
  "mountains": 0.0,
  "desert": 0.0
}
```

**Swamp Herb:**
```json
"biome_affinity": {
  "swamp": 2.0,
  "forest": 0.3,
  "coastal": 0.2,
  "plains": 0.1,
  "mountains": 0.0,
  "desert": 0.0
}
```

**Ubiquitous (Water/Grass):**
```json
"biome_affinity": {
  "plains": 2.0,
  "forest": 1.0,
  "coastal": 1.0,
  "swamp": 1.2,
  "mountains": 0.5,
  "desert": 0.3
}
```

### Tips
- Use `0.0` for biomes where the resource should **never** spawn
- Use `1.0` as baseline (neutral)
- Use `> 1.0` for preferred biomes (max recommended: `2.0`)
- Resources **must** be listed in the biome's `resource_spawns` in `biomes.json` to spawn there at all — `biome_affinity` only adjusts density within allowed biomes

---

## Seasonal Availability

Use `seasons_available` to gate resources to specific seasons. The system applies **seasonal compensation**: when in-season, density is multiplied by `4 / num_seasons`.

| Seasons | Compensation Multiplier | Example |
|---------|------------------------|---------|
| All 4 (empty) | 1.0x | `oak_tree`, `iron_rock` |
| 3 seasons | 1.33x | `void_crystal` (not winter) |
| 2 seasons | 2.0x | `silk_nest` (spring, summer) |
| 1 season | 4.0x | `mithril_vein` (winter only) |

### Seasonal Design Guidelines

- **Common/Uncommon:** Usually available all seasons or 3 seasons
- **Rare:** Often 2-3 seasons (e.g., `silk_nest`: spring/summer)
- **Epic:** Typically 1-2 seasons (e.g., `mithril_vein`: winter only)
- **Legendary:** Almost always 1 season (e.g., `star_metal`: winter)

This ensures players have a reason to play through all seasons and plan their progression.

---

## Regrowth Time Guidelines

Regrowth time should correlate with rarity — rarer resources take longer to regrow.

| Rarity | Typical Regrow Range | Notes |
|--------|---------------------|-------|
| Ubiquitous | 0 – 60s | `grass_patch`: 60s, `water_source`: 0s (infinite) |
| Common | 90 – 300s | Trees: 180-220s, Ore: 300s |
| Uncommon | 200 – 600s | Copper/Tin: 300s, Gold: 600s |
| Rare | 900 – 2000s | Gemstone: 900s, Void Crystal: 1500s |
| Epic | 1200 – 2500s | Mithril: 1500s, Phoenix Feather: 2500s |
| Legendary | 2000 – 2500s+ | Star Metal: 2000s, Ancient Rune: 2500s |

### Depletion Count Guidelines

| Resource Type | Typical Depletion | Examples |
|--------------|-------------------|----------|
| Infinite (water) | -1 | `water_source` |
| High-yield (grass, stone) | 5-8 | `grass_patch`: 5, `stone_quarry`: 8 |
| Standard (trees, ore) | 3-5 | `oak_tree`: 4, `iron_rock`: 5 |
| Low-yield (gems, special) | 1-3 | `gemstone`: 2, `silk_nest`: 3 |
| Single-harvest | 1 | `phoenix_feather`: 1, `ancient_rune`: 1 |

---

## Complete Example: Adding a New Resource

### Example: "Silver Vein" (Uncommon Ore)

```json
{
  "id": "silver_vein",
  "name": "Silver Vein",
  "biome": "mountains",
  "tier": 1,
  "rarity": "uncommon",
  "category": "ore",
  "base_density": 0.04,
  "yield_item": "silver_ore",
  "yield_quantity": 1,
  "xp_reward": 40.0,
  "depletion_count": 4,
  "regrow_time": 400.0,
  "sprite_key": "rocks/silver",
  "requires_tool": "pickaxe",
  "biome_affinity": {
    "mountains": 2.0,
    "desert": 0.4,
    "forest": 0.1,
    "plains": 0.1,
    "coastal": 0.1,
    "swamp": 0.1
  },
  "seasons_available": ["spring", "summer", "autumn"]
}
```

### Checklist Before Committing

- [ ] `id` is unique and snake_case
- [ ] `name` is human-readable
- [ ] `biome` matches one of the 6 biome IDs
- [ ] `rarity` is one of the 6 valid tiers
- [ ] `category` is one of: `wood`, `ore`, `herb`, `water`, `stone`, `special`
- [ ] `base_density` falls within the rarity's clamp range (see table above)
- [ ] `yield_item` exists in `data/items.json`
- [ ] `sprite_key` has a corresponding sprite in `assets/sprites/`
- [ ] `requires_tool` is `"axe"`, `"pickaxe"`, or `null`
- [ ] `biome_affinity` includes all 6 biomes with reasonable multipliers
- [ ] `seasons_available` is either empty (all) or lists valid seasons
- [ ] Add `id` to the appropriate biome's `resource_spawns` in `data/biomes.json`
- [ ] Add item definition to `data/items.json` if new
- [ ] Add recipe(s) using the yield item to `data/recipes.json` if applicable
- [ ] Run `python -m tools.analyze_resource_distribution --worlds 100` to verify distribution

---

## Testing Your Resource

### Quick Test (10 worlds)
```bash
python -m tools.analyze_resource_distribution --worlds 10 --output test.csv
```

### Full Balance Test (1000 worlds)
```bash
python -m tools.analyze_resource_distribution --worlds 1000 --output dist.csv
```

### Test Specific Season
```bash
python -m tools.analyze_resource_distribution --worlds 100 --season winter --output winter.csv
```

### Test Specific Biome
```bash
python -m tools.analyze_resource_distribution --worlds 100 --biome mountains --output mountains.csv
```

### Test Multiplayer Scaling
```bash
python -m tools.analyze_resource_distribution --worlds 50 --players 4 --output mp4.csv
```

### Interpreting Output

The CSV includes:
- `mean_count`: Average nodes per world (128x128 test map)
- `density_per_10k_tiles`: Normalized density for comparison
- `std_dev`: Variance across worlds (lower = more consistent)
- `min_count` / `max_count`: Range observed

Compare your new resource's `density_per_10k_tiles` against others in the same rarity tier.

---

## Integration Points

### 1. items.json
Add the yield item:
```json
{
  "id": "silver_ore",
  "name": "Silver Ore",
  "description": "Shiny silver ore, valuable for crafting.",
  "stack_size": 100,
  "sprite_key": "items/silver_ore",
  "value": 50
}
```

### 2. biomes.json
Add to mountain biome's resource_spawns:
```json
{
  "id": "mountains",
  "resource_spawns": [..., "silver_vein"]
}
```

### 3. recipes.json (if craftable)
```json
{
  "id": "silver_bar",
  "name": "Silver Bar",
  "skill": "metallurgy",
  "level_required": 20,
  "ingredients": [
    {"item": "silver_ore", "quantity": 2},
    {"item": "coal", "quantity": 1}
  ],
  "result": {"item": "silver_bar", "quantity": 1},
  "xp_reward": 25.0
}
```

---

## Common Mistakes to Avoid

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| `rarity` typo (e.g., "comon") | Falls back to "common" range | Use exact values from table |
| `base_density` outside clamp range | Silently clamped, your intent lost | Set within min/max for your rarity |
| Missing from biome's `resource_spawns` | Never spawns anywhere | Add to `data/biomes.json` |
| `yield_item` not in items.json | Harvest yields nothing / errors | Add item definition first |
| `sprite_key` path wrong | Invisible/pink resource node | Verify path in `assets/sprites/` |
| No `biome_affinity` | Uses 1.0 everywhere (may spawn in wrong biomes) | Always provide full affinity object |
| `seasons_available` with invalid season | Resource never spawns | Use: spring, summer, autumn, winter |

---

## Density Reference: Existing Resources by Rarity

### Ubiquitous (0.15–0.30)
- `water_source`: 0.02 (clamped to 0.15) — infinite, essential
- `grass_patch`: 0.20 — high density, fast regrow

### Common (0.08–0.15)
- `oak_tree`: 0.12, `birch_tree`: 0.12, `maple_tree`: 0.10, `pine_tree`: 0.08
- `iron_rock`: 0.08, `stone_quarry`: 0.10, `sand_deposit`: 0.12
- `berry_bush`: 0.10, `fiber_plant`: 0.12, `herb`: 0.08, `reed_bed`: 0.12
- `driftwood`: 0.08, `shell_beach`: 0.10, `wheat_field`: 0.08
- `peat_mound`: 0.12, `toxic_reed`: 0.10

### Uncommon (0.03–0.08)
- `copper_rock`: 0.05, `tin_rock`: 0.06, `gold_vein`: 0.02
- `salt_deposit`: 0.03, `salt_crystal`: 0.05, `cactus`: 0.08
- `fish_spot`: 0.05, `rare_ore`: 0.02
- `spruce_tree`: 0.08, `willow_tree`: 0.06, `dead_tree`: 0.03

### Rare (0.01–0.03)
- `gemstone`: 0.01, `void_crystal`: 0.01, `obsidian_vein`: 0.01
- `moonstone_deposit`: 0.01, `silk_nest`: 0.02, `elder_wood`: 0.01

### Epic (0.003–0.01)
- `mithril_vein`: 0.01, `ghost_iron_deposit`: 0.01
- `dragonbone`: 0.02, `amber_deposit`: 0.02
- `void_essence`: 0.005, `phoenix_feather`: 0.005

### Legendary (0.001–0.003)
- `star_metal`: 0.01 (clamped to 0.003), `ancient_rune`: 0.005, `celestial_crystal`: 0.005

---

## Advanced: Landmark Resources

Resources placed via the **landmark system** (guaranteed 1 per biome region) are defined in `resource_placer.py` in `LANDMARK_RESOURCES`. To make your resource a landmark, add it to the appropriate biome's list:

```python
LANDMARK_RESOURCES = {
    "mountains": ["star_metal", "ancient_rune", "your_new_resource"],
    ...
}
```

Landmark resources should be **Rare, Epic, or Legendary** and define the biome's identity.

---

## Appendix: Density Clamp Constants (config/constants.py)

```python
RARITY_DENSITY_RANGE = {
    "ubiquitous": (0.15, 0.30),
    "common":     (0.08, 0.15),
    "uncommon":   (0.03, 0.08),
    "rare":       (0.01, 0.03),
    "epic":       (0.003, 0.01),
    "legendary":  (0.001, 0.003),
}
```

To adjust global density bands, modify these values and re-run the analysis tool.

---

## Support

For questions about resource design or balance, run the analysis tool and compare your resource's output against existing resources in the same rarity tier. The tool output shows exactly how the system will place your resource across worlds, seasons, and biomes.