# Asset Checklist: Depleted Resource Sprites & Regrowth Stages

This checklist freezes the list of sprite keys that this phase must exist on disk.

**Convention:** `{base}.png` = mature, `{base}_depleted.png` = depleted,
`{base}_sapling.png` / `{base}_young.png` = tree regrowth stages.

All files live under `assets/sprites/`.

---

## Trees / wood (regrowth stages + depleted)

Every tree that has a mature sprite gets depleted, sapling, and young variants.

| resource_id | base sprite_key | Required files |
|---|---|---|
| oak_tree | trees/oak | trees/oak_depleted.png, trees/oak_sapling.png, trees/oak_young.png |
| elder_wood | trees/elder_wood | trees/elder_wood_depleted.png, trees/elder_wood_sapling.png, trees/elder_wood_young.png |
| berry_bush | trees/berry_bush | trees/berry_bush_depleted.png, trees/berry_bush_young.png (2-stage) |
| pine | trees/pine | trees/pine_depleted.png, trees/pine_sapling.png, trees/pine_young.png |
| maple | trees/maple | trees/maple_depleted.png, trees/maple_sapling.png, trees/maple_young.png |
| spruce | trees/spruce | trees/spruce_depleted.png, trees/spruce_sapling.png, trees/spruce_young.png |
| willow | trees/willow | trees/willow_depleted.png, trees/willow_sapling.png, trees/willow_young.png |
| birch | trees/birch | trees/birch_depleted.png, trees/birch_sapling.png, trees/birch_young.png |

### Shared fallbacks (always generated)
- trees/stump.png — generic tree depleted
- trees/sapling_generic.png — shared early regrowth
- trees/young_generic.png — shared mid regrowth

---

## Rocks / ores (depleted only)

| base sprite_key | Required depleted file |
|---|---|
| rocks/iron | rocks/iron_depleted.png |
| rocks/copper | rocks/copper_depleted.png |
| rocks/gold | rocks/gold_depleted.png |
| rocks/stone | rocks/stone_depleted.png |
| rocks/gem | rocks/gem_depleted.png |
| rocks/rare | rocks/rare_depleted.png |
| rocks/tin | rocks/tin_depleted.png |
| rocks/void_crystal | rocks/void_crystal_depleted.png |
| rocks/obsidian | rocks/obsidian_depleted.png |
| rocks/mithril | rocks/mithril_depleted.png |
| rocks/amber | rocks/amber_depleted.png |
| rocks/moonstone | rocks/moonstone_depleted.png |
| rocks/ghost_iron | rocks/ghost_iron_depleted.png |
| rocks/star_metal | rocks/star_metal_depleted.png |
| rocks/ancient_rune | rocks/ancient_rune_depleted.png |
| rocks/celestial_crystal | rocks/celestial_crystal_depleted.png |

### Shared fallback
- rocks/rubble.png

---

## World / plant / other (depleted only)

| base sprite_key | Depleted visual intent |
|---|---|
| world/herb | Cut / bare patch, short stems |
| world/fiber | Cut / bare patch |
| world/grass | Bare patch, short stems |
| world/wheat | Cut wheat stubble |
| world/driftwood | Scoured shore / empty |
| world/shell | Empty / scoured shell |
| world/fish | Empty pool ripple mark |
| world/salt | Empty / desiccated |
| world/salt_crystal | Empty / cracked |
| world/peat | Flattened mound / depression |
| world/toxic_reed | Cut / bare patch |
| world/sand | Flattened mound / depression |
| world/cactus | Empty / desiccated form |
| world/silk_nest | Empty / desiccated |
| world/dragonbone | Faded residual |
| world/void_essence | Faded residual |
| world/phoenix_feather | Faded residual |

### Shared fallback
- world/depleted_patch.png

---

## Exclude
- `water_source` (world/water, `depletion_count: -1`) — infinite; no depleted sprite.
- `trees/dead_tree.png` — already exists; not a harvestable resource node.

## Total file count
- Tree stages: 8 trees × 3 (depleted+sapling+young) + 2 shared = 26 files (berry bush has 2 stages, no sapling, but the fallback still created). Adjust: oak,elder_wood,pine,maple,spruce,willow,birch = 7×3=21, berry_bush=2, fallbacks=3 → 26.
- Rock depleted: 16 files + 1 rubble = 17.
- World depleted: 19 files + 1 patch = 20.
- Grand total: ~63 new PNG files.