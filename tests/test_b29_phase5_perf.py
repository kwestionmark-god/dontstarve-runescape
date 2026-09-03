"""Phase 5 performance fixes — behavior regression tests.

5.1: TileMap regrow timers tick only a dirty set, not all tiles per frame.
5.9: SkillManager XP table lookup matches the reference summation loop.
"""

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from unittest.mock import MagicMock

import pytest

from actions.action_system import ActionSystem
from actions.active_action import ActiveAction
from actions.types import ActionType
from skills.skill_manager import SkillManager, XP_SCALE_FACTOR
from world.resource_node import ResourceNode
from world.tile_map import TileMap


def _node(**overrides) -> ResourceNode:
    params = dict(
        resource_id="oak_tree",
        biome="forest",
        tier=1,
        rarity="common",
        category="wood",
        base_density=0.05,
        yield_item="wood",
        yield_quantity=1,
        xp_reward=25.0,
        depletion_count=1,
        current_depletions=0,
        regrow_time=10.0,
        sprite_key="tree",
        requires_tool="axe",
        name="Oak Tree",
    )
    params.update(overrides)
    return ResourceNode(**params)


class TestRegrowDirtySet:
    def test_mark_regrowing_enqueues_and_starts_timer(self) -> None:
        tm = TileMap(4, 4, 0, 0)
        assert not tm._regrow_tiles
        node = _node()
        node.current_depletions = node.depletion_count  # depleted
        tm.tiles[2][3].resource_node = node

        tm.mark_regrowing(2, 3)

        assert (2, 3) in tm._regrow_tiles
        assert tm.tiles[2][3].regrow_timer == node.regrow_time
        assert tm.tiles[2][3].depleted

    def test_update_ticks_only_queued_tiles(self) -> None:
        tm = TileMap(4, 4, 0, 0)
        node_a = _node()
        node_a.current_depletions = 1
        tm.tiles[0][0].resource_node = node_a
        node_b = _node()
        node_b.current_depletions = 1
        tm.tiles[3][3].resource_node = node_b

        # Only tile (0,0) is enqueued; (3,3)'s timer must be untouched.
        tm.mark_regrowing(0, 0)
        tm.update(2.0)

        assert tm.tiles[0][0].regrow_timer < node_a.regrow_time
        assert tm.tiles[3][3].regrow_timer == 0.0

    def test_regrown_tile_dequeued(self) -> None:
        tm = TileMap(4, 4, 0, 0)
        node = _node(regrow_time=1.0)
        node.current_depletions = 1
        tm.tiles[1][1].resource_node = node
        tm.mark_regrowing(1, 1)

        tm.update(2.0)  # over the regrow time

        assert (1, 1) not in tm._regrow_tiles
        assert not tm.tiles[1][1].depleted
        assert node.current_depletions == 0

    def test_gathering_completion_marks_tile(self) -> None:
        """5.1: depletion via action completion notifies the TileMap."""
        system = ActionSystem()
        tile_map = MagicMock()
        system.set_tile_map(tile_map)

        node = _node(depletion_count=1, current_depletions=0)
        action = ActiveAction(action_type=ActionType.WOODCUTTING)
        action.resource = node
        action.yield_item = "wood"
        action.yield_quantity = 1
        action.xp_reward = 25.0
        action.stamina_cost = 0.0
        action.success_rate_bonus = 100.0  # guarantee success roll
        action.tile_xy = (7, 9)

        result = system._complete_gathering(action)

        assert result.success
        assert node.is_depleted
        tile_map.mark_regrowing.assert_called_once_with(7, 9)


class TestSpatialGrid5B:
    """5B: spatial-grid proximity queries match full-scan semantics."""

    def test_grid_query_matches_full_scan(self) -> None:
        import random

        from core.spatial_grid import UniformGrid

        rng = random.Random(7)

        class Pt:
            def __init__(self, x, y):
                self.world_x, self.world_y = x, y

        pts = [Pt(rng.uniform(-5000, 5000), rng.uniform(-5000, 5000)) for _ in range(500)]
        grid = UniformGrid(cell_size=128)
        grid.rebuild(pts, lambda p: p.world_x, lambda p: p.world_y)
        for _ in range(50):
            qx, qy = rng.uniform(-5500, 5500), rng.uniform(-5500, 5500)
            r = rng.uniform(1, 700)
            expect = [p for p in pts
                      if (p.world_x - qx) ** 2 + (p.world_y - qy) ** 2 <= r * r]
            # query_indices is a superset (bucket-clipped); callers filter.
            got = [pts[i] for i in grid.query_indices(qx, qy, r)
                   if (pts[i].world_x - qx) ** 2 + (pts[i].world_y - qy) ** 2 <= r * r]
            assert set(map(id, got)) == set(map(id, expect))

    def test_combat_nearby_uses_grid_same_results(self) -> None:
        from combat.combat_system import CombatSystem

        cs = CombatSystem(player=MagicMock(world_x=0.0, world_y=0.0))

        class M:
            def __init__(self, x, y):
                self.world_x, self.world_y = x, y

            def is_alive(self):
                return True

        cs.monsters = [M(10.0, 0.0), M(500.0, 0.0), M(-20.0, 5.0)]
        nearby = cs.get_nearby_monsters(0.0, 0.0, 100.0)
        assert {round(m.world_x) for m in nearby} == {10, -20}  # bucket order may differ from list order
        alive = cs.get_alive_monsters_in_radius(0.0, 0.0, 100.0)
        assert len(alive) == 2

    def test_npc_proximity_grid_matches_full_scan(self) -> None:
        from npc.npc_system import NPCSystem

        class FakeNPC:
            def __init__(self, x, y):
                self.world_x, self.world_y = x, y
                self.is_active = True

        system = NPCSystem.__new__(NPCSystem)
        system.npcs = [FakeNPC(0.0, 0.0), FakeNPC(64.0, 0.0), FakeNPC(9999.0, 0.0)]
        system._nearby_grid = None
        nearby = system.get_nearby_npcs(0.0, 0.0, 128.0)
        assert [n.world_x for n in nearby] == [0.0, 64.0]
        # Deactivation narrows results after rebuild
        system.npcs[1].is_active = False
        system._nearby_grid = None
        nearby = system.get_nearby_npcs(0.0, 0.0, 128.0)
        assert [n.world_x for n in nearby] == [0.0]


class TestGouraudBatching:
    """5.2: batched scanline writes must match the per-pixel reference output."""

    def test_pixel_parity_with_reference_algorithm(self) -> None:
        import os

        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame

        pygame.init()
        from render.gouraud import fill_triangle

        def reference(surface, pts, cols):
            w, h = surface.get_size()
            verts = sorted(zip(pts, cols), key=lambda v: v[0][1])
            (x0, y0), c0 = verts[0]
            (x1, y1), c1 = verts[1]
            (x2, y2), c2 = verts[2]
            if abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)) < 1e-12:
                return

            def lerp(ca, cb, t):
                return tuple(max(0, min(255, round(a + (b - a) * t))) for a, b in zip(ca, cb))

            def scan(y, xlo, xro, cl, cr):
                if y < 0 or y >= h:
                    return
                xl, xr = round(xlo), round(xro)
                if xl > xr:
                    xl, xr, cl, cr = xr, xl, cr, cl
                if xr < 0 or xl >= w:
                    return
                xlc, xrc = max(0, xl), min(w - 1, xr)
                if xlc > xrc:
                    return
                sw = xr - xl
                if sw == 0:
                    surface.set_at((xlc, y), cl + (255,))
                    return
                for x in range(xlc, xrc + 1):
                    surface.set_at((x, y), lerp(cl, cr, (x - xl) / sw) + (255,))

            if y1 != y0:
                for y in range(max(0, int(y0)), min(h - 1, int(y1)) + 1):
                    tl = max(0.0, min(1.0, (y - y0) / (y1 - y0)))
                    tr = max(0.0, min(1.0, (y - y0) / (y2 - y0)))
                    xl = x0 + (x1 - x0) * tl
                    xr = x0 + (x2 - x0) * tr
                    cl, cr = lerp(c0, c1, tl), lerp(c0, c2, tr)
                    if xl > xr:
                        xl, xr, cl, cr = xr, xl, cr, cl
                    scan(y, xl, xr, cl, cr)
            if y2 != y1:
                for y in range(max(0, int(y1)), min(h - 1, int(y2)) + 1):
                    tl = max(0.0, min(1.0, (y - y1) / (y2 - y1)))
                    tr = max(0.0, min(1.0, (y - y0) / (y2 - y0)))
                    xl = x1 + (x2 - x1) * tl
                    xr = x0 + (x2 - x0) * tr
                    cl, cr = lerp(c1, c2, tl), lerp(c0, c2, tr)
                    if xl > xr:
                        xl, xr, cl, cr = xr, xl, cr, cl
                    scan(y, xl, xr, cl, cr)

        import random

        random.seed(42)
        for _ in range(20):
            pts = [(random.uniform(-5, 65), random.uniform(-5, 65)) for _ in range(3)]
            cols = [tuple(random.randint(0, 255) for _ in range(3)) for _ in range(3)]
            for flags in (0, pygame.SRCALPHA):
                a = pygame.Surface((64, 64), flags)
                b = pygame.Surface((64, 64), flags)
                reference(a, pts, cols)
                fill_triangle(b, *pts, *cols)
                for y in range(64):
                    for x in range(64):
                        assert a.get_at((x, y)) == b.get_at((x, y)), (x, y, pts)
        # Note: intentionally no pygame.quit() — quitting uninitializes the
        # font module and breaks later tests in the same session.


class TestCameraTrigCache:
    """5.10: cached yaw/pitch trig must track angle changes exactly."""

    def _camera(self):
        from camera.camera import Camera

        cam = Camera(800, 600)

        class _P:
            world_x = 1000.0
            world_y = 2000.0

        cam.player = _P()
        return cam

    def test_world_to_screen_matches_direct_math(self) -> None:
        cam = self._camera()
        for yaw, pitch in [(0.0, 0.5), (1.1, 0.4), (2.7, 0.55), (0.0, 0.52)]:
            cam.yaw = yaw
            cam.pitch = pitch
            got = cam.world_to_screen(1200.0, 1800.0, elevation=3.0)
            # Same call twice must hit the cache and still agree.
            again = cam.world_to_screen(1200.0, 1800.0, elevation=3.0)
            assert got == again
            dx, dy = 1200.0 - 1000.0, 1800.0 - 2000.0
            cy, sy, tp, sp = math.cos(yaw), math.sin(yaw), math.tan(pitch), math.sin(pitch)
            exp_x = 400 + (dx * cy - dy * sy) * cam.zoom
            exp_y = 300 + ((dx * sy + dy * cy) * tp - 3.0 * sp) * cam.zoom
            assert got == (exp_x, exp_y)

    def test_screen_to_world_roundtrip_after_angle_change(self) -> None:
        cam = self._camera()
        for yaw, pitch in [(0.3, 0.5), (1.9, 0.35)]:
            cam.yaw = yaw
            cam.pitch = pitch
            sx, sy = cam.world_to_screen(1500.0, 1500.0)
            wx, wy = cam.screen_to_world(sx, sy)
            assert wx == pytest.approx(1500.0, abs=1e-6)
            assert wy == pytest.approx(1500.0, abs=1e-6)


class TestGearLoadCache:
    """5.4: GearItem.load_all memoizes per path (was re-parsing per frame)."""

    def test_load_all_returns_cached_dict(self) -> None:
        from combat.gear import GearItem

        a = GearItem.load_all()
        b = GearItem.load_all()
        assert a is b
        assert a  # non-empty


class TestSpriteFogCache:
    """5.6: fog overlay surfaces are cached on quantized alpha buckets."""

    def test_overlay_reused_for_same_bucket(self) -> None:
        import pygame

        pygame.init()
        from render.sprite_renderer import SpriteRenderer, _FOG_OVERLAY_CACHE

        screen = pygame.Surface((64, 64))
        _FOG_OVERLAY_CACHE.clear()
        rect = pygame.Rect(0, 0, 10, 10)
        SpriteRenderer._apply_fog_overlay(screen, rect, 30)
        size_after_first = len(_FOG_OVERLAY_CACHE)
        # Same bucket (30//8*8 == 24), different raw alpha: no new surface.
        SpriteRenderer._apply_fog_overlay(screen, rect, 26)
        assert len(_FOG_OVERLAY_CACHE) == size_after_first

    def test_tint_cache_reuses_surface(self) -> None:
        import pygame

        pygame.init()
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        sprite = pygame.Surface((8, 8), pygame.SRCALPHA)
        a = sr._apply_seasonal_tint(sprite, (10, 20, 30), 40)
        b = sr._apply_seasonal_tint(sprite, (10, 20, 30), 40)
        assert a is b


class TestAmbientOverlayCache:
    """5.7: ambient overlay surface recreated only when key changes."""

    def test_overlay_surface_reused(self) -> None:
        import pygame

        pygame.init()
        from render.seasonal_renderer import SeasonalRenderer

        screen = pygame.Surface((64, 64))
        sr = SeasonalRenderer()
        sr.draw_ambient_overlay(screen, alpha=20)
        first = sr._ambient_overlay
        sr.draw_ambient_overlay(screen, alpha=20)
        assert sr._ambient_overlay is first
        sr.draw_ambient_overlay(screen, alpha=30)
        assert sr._ambient_overlay is not first


class TestXformCacheHit:
    """5B: textured-tile cache hits must not crash (regression: plain dicts
    have no move_to_end)."""

    def test_second_render_of_same_tile_hits_cache(self) -> None:
        import pygame

        pygame.init()
        # Terrain sprite loading uses convert_alpha(), which needs a real
        # display surface (dummy SDL driver is fine).
        pygame.display.set_mode((64, 64))
        from world.tile_map import TileMap
        from render.tile_renderer import TileRenderer

        tm = TileMap(8, 8, 0, 0)
        for x in range(8):
            for y in range(8):
                tm.tiles[x][y].elevation = 1
        tm.bake_corner_heights()
        tm.bake_corner_fog()

        screen = pygame.Surface((320, 240))
        renderer = TileRenderer(tm, screen, lighting_system=None)

        class FakeCam:
            yaw = 0.0
            pitch = 0.5
            zoom = 1.0
            player = type("P", (), {"world_x": 4 * 64.0, "world_y": 4 * 64.0})()
            screen_width = 320
            screen_height = 240
            pan_x = 0.0
            pan_y = 0.0

            def get_view_rect(self):
                return (-128.0, -128.0, 8 * 64 + 128, 8 * 64 + 128)

            def world_to_screen(self, wx, wy, elevation=0):
                return (wx - 4 * 64 + 160, (wy - 4 * 64) * 0.5 + 120 - elevation)

        renderer.render(FakeCam())
        n1 = len(renderer._xform_cache)
        renderer.render(FakeCam())  # second pass hits the cache
        assert n1 > 0  # textured path populated cache (else test is vacuous)


class TestXpTable:
    def _reference(self, level: int) -> int:
        total = 0
        for L in range(1, level):
            total += math.floor((L + 300 * math.pow(2, L / 7)) / XP_SCALE_FACTOR)
        return total

    def test_table_matches_reference_levels_1_to_99(self) -> None:
        for level in range(1, 100):
            assert SkillManager.get_xp_for_level(level) == self._reference(level)

    def test_level_1_is_zero_and_monotonic(self) -> None:
        assert SkillManager.get_xp_for_level(1) == 0
        values = [SkillManager.get_xp_for_level(l) for l in range(1, 100)]
        assert all(b >= a for a, b in zip(values, values[1:]))
