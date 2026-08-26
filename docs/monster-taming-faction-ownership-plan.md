# Monster Taming & Faction Ownership — Design & Phase Plan

*Living plan for the faction/taming scope introduced by `tmp/LIVE-ISSUES.md` #8.*

## 1. What this is (and isn't)

Two **related but independent** features that share the faction system:

1. **Monster taming** — a new skill that lets the player befriend/summon monsters as
   companions. This is the higher-value, more self-contained feature.
2. **Faction-owned monster variants** — a *visual + semantic* marker that some monsters
   "belong" to a faction, so killing them reads as a hostile act ("criminal"). This is a
   smaller, surface-level layer that mostly restates what `hostile_monster_types` already
   implies — see the caveat in §3.

The two only truly intersect at one point: a faction-owned monster that you tame vs. kill
should have opposite diplomatic effects. That intersection is called out explicitly in the
plan so it isn't an accident.

---

## 2. Grounding — what already exists (don't rebuild it)

**Faction system** (`npc/faction_system.py`)
- `get_faction_for_monster(monster_id)` → the faction whose `hostile_monster_types` list
  contains that monster id. Mapping is **purely data-driven**, independent of where the
  monster spawns.
- `update_standing(faction_id, delta)` → clamps to `[0.0, 1.0]`; `0.5` = neutral.
- Data lives in `data/factions.json`. Current entries:
  `forest_villagers []`, `goblins [wolf, goblin]`, `coastal_merchants [sea_serpent]`,
  `desert_djinn [scorpion, sand_worm]`, `swamp_factions [poison_frog, crocodile]`,
  `mountain_clans [stone_golem]`.

**Skill system** (`skills/skill_manager.py`, `skills/<name>/<name>.py`)
- Skills are registered in `_SKILL_DEFAULTS` (skill_id → substat defaults). Adding an entry
  here is what makes a skill live: it becomes a `SkillData` with stat points and OSRS
  leveling.
- Each skill has a matching `*Skill` class exposing methods like
  `get_success_rate_bonus()`, `get_description()`, `calculate_yield(...)`.
- XP: `skill_manager.add_xp(skill_id, xp)`. Allocations:
  `skill_manager.get_effective_stat(skill_id, substat)`.
- Wiring happens in `core/bootstrap.py` (`_build_skill_manager`, then skill instances are
  created and attached to the game).

**Monsters** (`data/monsters.json`, `combat/monster.py`, `combat/combat_system.py`)
- `Monster.from_def(...)` builds a monster from JSON; `spawn_initial_monsters` places them
  near spawn.
- **Respawn is not currently implemented** anywhere in combat. This is the hard blocker for
  a taming loop (you can't "hunt a respawning rival" if monsters never come back).

---

## 3. Decision log

- **#8 (corrected):** defeating a faction-associated monster **worsens** relations.
  Associated types (via `hostile_monster_types` → `get_faction_for_monster`) are treated
  as faction-linked; killing them is a hostile act. Implemented in
  `combat/combat_system.py::_monster_died` (`update_standing(faction, -0.10)` +
  "worsened relations" message). Test:
  `tests/test_b24_faction_kill_worsens_standing.py`.
  (Earlier commit b7c7113 inverted this to improve; that polarity was wrong for
  owned/associated semantics and has been restored.)
- **Caveat / future path:** improving relations for *wild* kills inside faction territory
  is a separate idea and is **not** implemented yet (no territory check on kill). When
  explicit `faction_owned` flags land, those also worsen standing — same baseline as the
  current associated map, just more explicit. See Phase 3.

---

## 4. Phased plan

### Phase 0 — Foundations (small, de-risks everything)
Objective: establish the data model for ownership + taming so later phases are pure wiring.

- Add to `data/monsters.json` per-monster flags (guard against unknown keys):
  - `tamable: bool` — can this monster be befriended.
  - `faction_owned: bool` — does this monster count as a faction's property (killing = bad).
- Decide the source of truth for "which faction owns X": reuse
  `faction_system._monsters_to_factions` (derived from `hostile_monster_types`), or add an
  explicit `owned_by` to the monster def. **Recommend the latter** so "associates"
  (`tamable`) and "property" (`faction_owned`) are decoupled.
- Acceptance: a loader test asserts every monster def has safe defaults for the new keys.
- Tests: `tests/test_bXX_monster_def_flags.py`.

### Phase 1 — Monster respawn (blocker for taming)
Objective: monsters reappear after death on a timer, so hunting has meaning and taming has a
loop.

- Add a respawn registry in `combat_system` (monster_id → respawn timer). On
  `_monster_died`, schedule respawn; on timer expiry, rebuild the monster via
  `Monster.from_def` at a valid spawn point near existing territory (reuse biome/region
  data already consumed by `spawn_initial_monsters`).
- Per-faction respawn cap so a region doesn't overflow.
- Acceptance: kill a monster, advance time, confirm it respawns once; a faction's monsters
  stay within its respawn budget.
- Tests: drive `_monster_died` + a manual timer advance (no real-time waits).

### Phase 2 — Taming skill (core feature)
Objective: a first-class skill that makes taming a progression loop, not a one-off.

- Register `"taming"` in `_SKILL_DEFAULTS` with sub-stats, e.g.
  `taming_success`, `creature_loyalty`, `taming_cooldown`.
- Add `skills/taming/taming.py` (`TamingSkill`) with `get_success_rate_bonus()` and
  `get_description()`, mirroring `WoodcuttingSkill`/`IntelligenceSkill`.
- Wire it in `core/bootstrap.py` (attach `TamingSkill` to the game like other skills).
- Taming action: a new interact/use action (likely under the action or interaction system —
  confirm the existing interact surface) that, when used on a `tamable` alive monster, rolls
  success against `get_effective_stat("taming", "taming_success")`. On success, the monster
  becomes a **companion** (follows player, optional combat aid). Grant taming XP on attempt.
- Companion state: a lightweight holder on the player (`tamed_comp: Monster | None` +
  position/keep-alive). Reuse `register_monster` / existing companion-follow patterns if any
  exist; otherwise a minimal version.
- Acceptance: level-1 taming has a low success rate; investing `taming_success` raises it;
  a successful tame yields a following companion; XP is awarded.
- Tests: unit-test `TamingSkill.get_success_rate_bonus` + a tame attempt with a mocked
  monster (deterministic RNG seed).

### Phase 3 — Faction-ownership visual markers ("criminal")
Objective: make ownership legible at a glance — a **cosmetic** change first.

- Sprite/paint overlay: tint or draw a small faction glyph on faction-owned monsters
  (`faction_owned: true`). Keep it additive over existing monster rendering — don't touch the
  base sprite.
- Kill-relationship rule: owned (and current associated) kills **worsen** standing. Route
  explicit `faction_owned` through the same `_monster_died` branch so the rule is keyed
  on the flag rather than only the type map.
- Optional later: *wild* kills inside faction territory could *improve* standing — that is
  a distinct check (territory + non-owned) and is not part of this phase.
- Acceptance: owned monsters show the marker; killing one decreases standing.
- Tests: render-path assertion (marker present) + `_monster_died` standing assertion.

### Phase 4 — Integration & persistence
Objective: make taming and ownership first-class citizens end-to-end.

- Save/load: persist `tamed_comp` (monster_id, position, loyalty) and any per-companion
  state in `save_system` (mirror the survival/gear restore pattern already there).
- Diplomacy panel (`ui/diplomacy_panel.py`): surface owned monsters and current standing
  cleanly; consider showing tamable monsters as a distinct category.
- Companion gameplay: basic follow + optional defensive reaction (reuse NPC-guard cooldown
  logic if applicable).
- Acceptance: tame a companion, reload, companion persists; diplomacy panel reflects owned
  monsters.
- Tests: save→load round-trip of a tamed companion.

### Phase 5 — Polish (optional)
- Loyalty decay / bonding over time, taming cooldowns scaling with skill, faction-relation
  events when a companion kills an owned monster, unique tameable variants with distinct
  sprites.

---

## 5. Scope guardrails

- **Phase 1 before Phase 2.** No respawn = no meaningful taming loop. Don't skip it.
- **Ownership is an exception, not the default.** `tamable` ≠ `faction_owned`. Most
  tamable monsters should stay neutral (killing them = fine or even good); only explicitly
  owned ones are "criminal."
- **Visual layer is additive.** Ownership markers and tame tints never rewrite base sprites.
- **Small commits.** Each phase = focused commit + discriminating test, matching the
  procedural-commit cadence used for #1–#8.

---

## 6. Open questions for the author

1. Should owned monsters be **explicitly listed** (`owned_by: <faction>`) or **derived**
   from `hostile_monster_types`? (Recommend explicit — keeps tamable vs. property decoupled.)
2. How many monsters should be tamable at launch — a curated short list, or all `tamable`
   defs? (Recommend a curated list to bound sprite/art scope.)
3. Companion behavior depth: pure follower, or follower + combat aid? (Recommend follower
   first; combat aid is Phase 5.)
4. Does taming need a crafting item (e.g., "treat") as a consumable cost, or is it a pure
   skill check? (Recommend a cheap consumable to add an economic loop.)
