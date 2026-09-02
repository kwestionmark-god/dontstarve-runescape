# Progression Audit — Starting Classes, Skill Gates, and Data Wiring

Date: 2026-09-02

This document reviews whether each starting class can progress from its
starter pack, and records the skill-gating system added to make every skill
have level-based progression.

## The critical findings (pre-fix)

1. **Scavenger (and default) were soft-locked.** Their starter packs contain
   no axe and no pickaxe, and `axe`/`pickaxe` were starter-pack-only items —
   nothing in the game produced them. Every woodcutting and mining path
   (`requiresTool`) was permanently closed to those classes.
2. **Campfire bootstrap deadlock.** The campfire *structure* cost
   `stick×2 + charcoal×1`, but charcoal could only be made by burning logs at
   an existing campfire. First fire was only possible via the crafting
   *recipe* (oak_logs×3 + stone×5) — which again needs an axe.
3. **Level 1 characters could cut Elder Wood and mine Celestial Crystals.**
   No resource or recipe carried any level requirement, so "progression"
   was cosmetic: all 44 resources and most recipes were available from level 1.
4. **Data skeleton had dangling references.**
   - Recipes produced two item ids (`polished_obsidian`, `dragonbone_shard`)
     that did not exist in `items.json`.
   - 22 monster-loot ids (e.g. `goblin_dagger`, `drake_egg`, `troll_club`)
     were dropped by monsters but had no item definitions or sprites.
   - Dozens of authored items (bone/tallow/candle, honey/mead, resin/pitch,
     salt refining, silk fabric, the whole tier-4 legendary gear set) had
     sprites and item defs but **no recipe produced them** — dead ends.

## What was changed

### Skill gates

- `ResourceNode.required_level` (default 1); `ActionSystem.start_action`
  refuses the gather with "You need X level N to harvest …" when the player's
  level is too low (skill inferred from the action type).
- `Recipe.required_skill` / `required_level`; `CraftingSystem.craft()` and
  `cook()` gate on them. Construction-style `skill_requirements` dicts fold
  into the same single gate. The crafting panel shows a blue "Lv N" badge on
  gated recipes.

### Ladders now in data

| Skill | Ladder (selection) |
|---|---|
| Woodcutting | oak/dead 1 → birch 5 → pine 10 → willow 15 → maple 20 → spruce 30 → elder 45 |
| Mining | stone/copper 1 → tin 10 → iron 15 → rare 25 → gold 30 → gem 35 → obsidian/amber 40 → void/moonstone 50 → ghost iron/dragonbone 55 → mithril 60 → star metal 70 → ancient rune 75 → celestial 85 |
| Foraging | basics 1 → wheat/fish/salt/peat 5 → salt crystal 8 → cactus 10 → toxic reed 12 → beehive 20 → silk nest 25 → void essence 60 → phoenix feather 65 |
| Cooking | chicken 1 → fish/tallow 5 → meat 10 → refined salt/honey 12 → mead 20 |
| Metallurgy | copper 1 → iron 5 → bronze 10 (+alloy mastery) → steel 25 → mithril 45 → star metal 60; glass 10 → sheet 15 → obsidian glass 30 |
| Crafting | sticks/rope/planks 1 → stone pickaxe 5 → bone/resin mid 5–25 → silk fabric 25 → legendary gear 45–75 |
| Intelligence | silk 15 → amber 25 → moonstone 35 → dragonbone 40 → void concentrate 45 → phoenix 55 → void elixir 60 → rune 65 → attune/void draught 70 |

### Bootstrap fixes (class viability)

- New resources: **loose_stones** (tool-free stone, foraging 1) and
  **beehive** (honeycomb_raw, foraging 20).
- New recipes: **whittle driftwood → sticks**, **stone axe** (stone×2 +
  stick×2, crafting 1), **stone pickaxe** (stone×3 + stick×2, crafting 5).
  `ActionSystem._find_equipped_tool` already accepts `*_axe`/`*_pickaxe`.
- Campfire structure materials changed to `stick×2 + stone×2` (charcoal is no
  longer required to make the first campfire).

### Combat gear progression (second pass)

Previously, `gear.json` weapons/armor were **unobtainable**: quest
`gear_unlocks` only flagged an id and nothing ever granted the item, and
there were no recipes or sprites. Now every piece is a real crafted item:

- Whittled weapons (crafting 2–5, no station): wooden sword/axe/spear,
  stone sword — the day-one combat kit.
- Leather set from monster drops (crafting 5–8): boots/helmet/armor from
  wolf pelts + bear hide.
- Smithing at the anvil (metallurgy 12–28): bronze sword/chestplate, the
  full iron set (sword/axe/spear/helmet/boots/chestplate), full steel set.
- Equipping is still gated by the existing Combat level requirements in
  `gear.json` (1→15), creating a two-track gate: you must both *make* it
  (metallurgy/crafting) and be *strong enough to wield* it (combat).
- All 21 gear ids are now items in `items.json` with generated icons in
  `assets/sprites/gear/`.

### Dead-end chains wired

- Resin: tap maple sap → refine resin → pitch.
- Bone: grind bone (\u2190 wolf bones) → bone powder → polished bone (feeds
  dragonbone whistle / mithril longsword hafts).
- Candle: render tallow (animal fat) → craft candle.
- Honey: beehive → honeycomb_raw → filtered honey → mead base.
- Glass: sand → molten glass → glass sheet; polished obsidian → obsidian glass.
- Silk: process silk → silk thread → silk fabric → enchanted/phoenix cloaks.
- Tier-4 gear craftable at stations: dragonbone whistle (45), mithril
  longsword (50), silk enchanted cloak (55), phoenix cloak (60),
  ghost iron chestplate (60), rune mithril longsword (65), star metal
  longsword (70), celestial chestplate (75).
- All 22 monster loot ids and both missing recipe outputs now exist in
  `items.json` with generated sprites.

## Per-class walkthrough (day one, level 1)

- **Forester (axe):** chop oak → logs → sticks + planks; forage
  loose_stones → craft stone pickaxe (crafting 5) → mining opens. Food:
  berries → cook at campfire (needs stone; covered). ✅
- **Prospector (pickaxe):** mine stone + copper → smelt copper (metallurgy
  1). For axe: whittle driftwood → sticks, mine stone → craft stone axe. ✅
- **Scavenger (torch, food):** forage berries/fiber/grass/fish; forage
  loose_stones; whittle driftwood → sticks; build campfire; craft stone tools
  → both gathering skills open. ✅
- **Default:** identical to scavenger. ✅

## Known remaining gaps (deliberate scope cut-offs)

- Trade-only items (`*_trade` variants, jewelry) remain merchant/quest-only.
- Metallurgy's alloy-mastery sub-stat gate coexists with the new recipe level
  gate; smelting keeps its own panel flow (`attempt_smelt`).
- `pith.png` is an orphan sprite with no matching item.
