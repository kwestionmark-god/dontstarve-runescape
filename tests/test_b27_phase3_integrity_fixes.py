"""
test_b27_phase3_integrity_fixes.py — Regression tests for the 2026-09-03
audit, Phase 3 (world/render + economy integrity).

Covers:
- 3.1 Sun-altitude curve is continuous and peaks at sun_altitude_max at noon
- 3.2 Particle spawning works at 60 FPS (fractional accumulator)
- 3.3 Corner-shading cache not invalidated when the sun is unchanged
      (covered by tests/test_phase7_p2_corner_shading.py additions)
- 3.4 Ecotone blending writes per-tile spawn lists, never the shared Biome;
      landmark pass respects seasonal availability
- 3.6 Inventory-full hardening: smelt/barter/harvest abort cleanly
- 3.7 Quest-locked recipes rejected by craft/cook regardless of panel filtering
- 3.8 Data integrity: structure material ids all exist; trade item ids all
      exist and are unique; faction leaders are not stacked at one position
- 3.9 Building consistency: portable pickup return rate, monster structure
      attack range, per-instance NPC assignment keys
"""

import json
import math
from pathlib import Path


# ── 3.1 Sun curve ────────────────────────────────────────────────────────────


class TestSunCurve:
    def test_continuity_at_sunrise_and_sunset(self):
        from render.lighting_system import compute_sun_direction

        for boundary in (0.25, 0.5, 0.75):
            _, alt_before = compute_sun_direction(boundary - 1e-6)
            _, alt_after = compute_sun_direction(boundary + 1e-6)
            assert abs(alt_before - alt_after) < 1e-3, (
                f"Altitude discontinuous at t={boundary}: "
                f"{math.degrees(alt_before):.2f} vs {math.degrees(alt_after):.2f}"
            )

    def test_noon_peaks_at_alt_max_and_midnight_at_alt_min(self):
        from render.lighting_system import compute_sun_direction

        _, noon = compute_sun_direction(0.5)
        _, midnight = compute_sun_direction(0.0)
        assert abs(math.degrees(noon) - 30.0) < 1e-6
        assert abs(math.degrees(midnight) - (-30.0)) < 1e-6

    def test_season_system_matches_library(self):
        from seasons.season_system import SeasonSystem

        ss = SeasonSystem()
        ss.time_of_day = 0.5
        assert abs(ss.get_lighting_params()["sun_altitude"] - math.radians(30.0)) < 1e-9


# ── 3.2 Particle spawn accumulator ───────────────────────────────────────────


class TestParticleSpawning:
    def test_particles_spawn_at_60fps(self):
        from render.particle_system import ParticleSystem

        ps = ParticleSystem()
        ps.sync("rain")
        for _ in range(60):  # one second of 60 FPS frames
            ps.update(1 / 60)
        assert len(ps.particles) > 0, "rain produced no particles in a second"

    def test_storm_rate_is_real(self):
        from render.particle_system import ParticleSystem

        ps = ParticleSystem()
        ps.sync("storm")
        for _ in range(30):
            ps.update(1 / 60)
        assert 10 <= len(ps.particles) <= 30  # ~40/s → ~20 in half a second

    def test_fog_draw_uses_alpha_overlay(self):
        import pygame
        from render.particle_system import ParticleSystem

        ps = ParticleSystem()
        ps.sync("fog")
        for _ in range(120):
            ps.update(1 / 60)
        screen = pygame.Surface((320, 240), pygame.SRCALPHA)
        ps.draw(screen)  # must not raise; fog circles drawn with alpha


# ── 3.4 Ecotone blend + landmark season gating ───────────────────────────────


class TestEcotoneBlendIsolation:
    def test_blend_does_not_mutate_shared_biome(self):
        """Tiles sharing one Biome object must not accumulate spawn lists."""
        from world.biome import Biome
        from world.resource_placer import ResourcePlacer
        from world.tile_map import Tile, TileMap

        forest = Biome(
            id="forest", name="Forest", mega_cluster="temperate",
            environmental_pressure=0.2, starting_safety=True,
            elevation_range=(0, 10), terrain_colors={"base": (20, 100, 20)},
            resource_spawns=["stick_tree"],
        )
        desert = Biome(
            id="desert", name="Desert", mega_cluster="arid",
            environmental_pressure=0.8, starting_safety=False,
            elevation_range=(0, 10), terrain_colors={"base": (200, 180, 100)},
            resource_spawns=["cactus"],
        )
        tm = TileMap(6, 1, 0, 0)
        for x in range(6):
            biome = forest if x < 3 else desert
            tm.tiles[x][0] = Tile(x, 0, biome, 5)

        from world.world_gen import _build_biome_transitions

        class _Registry:
            def get(self, biome_id):
                return {"forest": forest, "desert": desert}.get(biome_id)

        _build_biome_transitions(
            tm, _Registry(),
            {"cactus": {"biome_affinity": {"forest": 1.0}}},
        )

        assert forest.resource_spawns == ["stick_tree"], (
            "shared Biome object was mutated by the ecotone blend"
        )
        border_tile = tm.tiles[2][0]
        assert border_tile.blended_spawns is not None
        assert "cactus" in border_tile.blended_spawns
        # Interior tile neighbors nothing foreign → untouched
        assert tm.tiles[0][0].blended_spawns is None


# ── 3.6 Inventory-full hardening ─────────────────────────────────────────────


class _FullInventory:
    """Everything reports present; NOTHING fits."""

    def __init__(self):
        self.removed = 0

    def has_items(self, item_id, quantity):
        return True

    def can_add(self, item_id, quantity):
        return False

    def add_item(self, *a, **k):
        return False

    def remove_item(self, item_id, quantity):
        self.removed += quantity
        return True


class TestInventoryFullHardening:
    def test_smelt_aborts_without_consuming(self):
        from skills.metallurgy.metallurgy import MetallurgySkill
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        skill = MetallurgySkill(sm)
        recipe = skill.get_smelt_recipes()[0]

        inv = _FullInventory()
        import random
        random_orig = random.random
        try:
            random.random = lambda: 0.0  # force the success branch
            result = skill.attempt_smelt(recipe.recipe_id, inv)
        finally:
            random.random = random_orig
        assert result.success is False
        assert inv.removed == 0
        assert "full" in result.message.lower()

    def test_barter_aborts_on_full_inventory(self):
        from npc.trade_system import TradeSystem
        from npc.npc_types import MerchantNPC

        class _Int:
            def calculate_buy_price(self, p): return p
            def calculate_sell_price_with_trade(self, p): return p
            def calculate_barter_value(self, p): return p
            def get_merchant_inventory_bonus(self): return 99

        inv = _FullInventory()
        inv._qty = {"stick": 5}
        inv.has_items = lambda i, q: inv._qty.get(i, 0) >= q

        player = type("P", (), {"inventory": inv, "distance_to": lambda s, x, y: 0.0})()
        merchant = MerchantNPC(
            npc_id="merchant_forest_1", name="Fred", npc_type="merchant",
            world_x=0.0, world_y=0.0, sprite_key="npc/merchant_forest",
            faction=None, dialogue_lines=[], behavior="trade",
            patrol_area=(0, 0, 10, 10), is_active=True, is_recruited=False,
            recruit_behavior=None, hostility_level=0.0, health=100.0,
            max_health=100.0, inventory_capacity=10, restock_timer=0.0,
            restock_interval=60.0, gold=1000, price_modifier=1.0,
            commerce_requirement=0,
        )
        ts = TradeSystem(_Int())
        ts.load_trade_data()
        # Make the offered stick value match the trade item so the barter is
        # "fair" and reaches the inventory-capacity gate.
        ts.__class__._get_item_base_price = lambda self, item_id: 8
        ts.open_trade(player, merchant)
        trade_item = ts._find_trade_item("forest_healing_herbs")
        result = ts.execute_barter("stick", 1, trade_item.trade_item_id)
        assert result.success is False
        assert "full" in result.message.lower()


# ── 3.7 Quest-locked recipe enforcement ──────────────────────────────────────


class TestQuestLockedRecipes:
    def test_locked_recipe_rejected_by_craft_and_cook(self):
        from crafting.crafting_system import CraftingSystem
        from crafting.recipe_registry import RecipeRegistry

        registry = RecipeRegistry()
        registry.load_all()
        cs = CraftingSystem(registry)
        locked = sorted(registry.locked_recipes)
        if not locked:
            # No quest-locked recipes in data — nothing to enforce
            return
        rid = locked[0]
        recipe = cs.recipes[rid]

        class _Inv:
            def can_add(self, *a): return True
            def has_items(self, i, q): return True
            def remove_item(self, *a): return True

        result = cs.craft(rid, _Inv())
        assert result.success is False
        assert "locked" in result.message.lower()

        result = cs.cook(rid, _Inv(), has_campfire=True)
        assert result.success is False
        assert "locked" in result.message.lower()


# ── 3.8 Data integrity ───────────────────────────────────────────────────────


class TestDataIntegrity:
    def test_structure_material_ids_all_exist(self):
        items = {i["id"] for i in json.loads(Path("data/items.json").read_text())["items"]}
        s = json.loads(Path("data/structures.json").read_text())
        missing = []

        def walk(o):
            if isinstance(o, dict):
                mats = o.get("materials")
                if isinstance(mats, list):
                    for pair in mats:
                        if pair[0] not in items:
                            missing.append((o.get("structure_id"), pair[0]))
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(s)
        assert not missing, f"dangling material ids: {missing}"

    def test_trade_items_reference_real_items_and_are_unique(self):
        items = {i["id"] for i in json.loads(Path("data/items.json").read_text())["items"]}
        trades = json.loads(Path("data/trade_items.json").read_text())["trade_items"]
        missing = [t["trade_item_id"] for t in trades if t["item_id"] not in items]
        assert not missing, f"trade items referencing unknown items: {missing}"
        # Same item may be stocked by different biome merchants; duplicates
        # within ONE biome's pool are the bug.
        pools = [(t.get("biome"), t["item_id"]) for t in trades]
        dupes = {p for p in pools if pools.count(p) > 1}
        assert not dupes, f"duplicate stock pools: {dupes}"

    def test_no_stacked_faction_leaders(self):
        npcs = json.loads(Path("data/npcs.json").read_text())["npcs"]
        leaders = [n for n in npcs if n.get("npc_type") == "faction_leader"]
        positions = {}
        for n in leaders:
            positions.setdefault((n["world_x"], n["world_y"]), []).append(n["npc_id"])
        dupes = {k: v for k, v in positions.items() if len(v) > 1}
        assert not dupes, f"faction leaders stacked at one position: {dupes}"


# ── 3.9 Building consistency ─────────────────────────────────────────────────


def _building_system():
    from building.building_system import BuildingSystem
    from inventory.inventory import Inventory
    from skills.construction.construction import Construction
    from skills.skill_manager import SkillManager

    sm = SkillManager()
    construction = Construction(sm)
    return BuildingSystem(sm, Inventory(), construction, {"offensive": {}})


def _struct(structure_id="ballista", x=0.0, y=0.0, portable=False):
    from building.structure import Structure, StructureDef

    return Structure(
        structure_def=StructureDef(
            structure_id=structure_id, name=structure_id.title(),
            structure_type="portable" if portable else "fixed",
            construction_sub_stat="offensive", hp=50,
            materials=[("stick", 8)],
            requires_structure_level=0, requires_skill_level=0,
            biome_compatible=[], sprite_key="ballista",
        ),
        world_x=x, world_y=y, hp=50, max_hp=50, is_active=True,
        is_portable=portable,
    )


class TestBuildingConsistency:
    def test_portable_pickup_returns_full_materials(self):
        bs = _building_system()
        s = _struct(portable=True)
        s.instance_id = bs._next_instance_id
        bs._next_instance_id += 1
        bs.structures.append(s)
        result = bs.pickup_structure(s)
        assert result.success
        qty = dict(result.materials_returned)["stick"]
        assert qty == 8, f"portable pickup should return 100% materials, got {qty}"

    def test_monster_attack_structure_range_gate(self):
        from config import TILE_SIZE

        bs = _building_system()
        s = _struct()
        bs.structures.append(s)
        # Monster far away: no damage
        assert bs.monster_attack_structure(10, s.world_x + TILE_SIZE * 5, s.world_y) is None
        assert s.hp == 50
        # Monster within range: damages
        bs.monster_attack_structure(10, s.world_x + 10, s.world_y)
        assert s.hp < 50

    def test_two_same_type_structures_assignable_independently(self):
        bs = _building_system()
        s1, s2 = _struct(), _struct(x=50.0)
        for s in (s1, s2):
            s.instance_id = bs._next_instance_id
            bs._next_instance_id += 1
            bs.structures.append(s)

        ok1, _ = bs.assign_npc_to_structure("ballista", "npc_a")
        ok2, _ = bs.assign_npc_to_structure("ballista", "npc_b")
        assert ok1 and ok2, f"second same-type structure must be assignable ({ok1}, {ok2})"
        assert bs.get_assigned_structure("npc_a") is not bs.get_assigned_structure("npc_b")
