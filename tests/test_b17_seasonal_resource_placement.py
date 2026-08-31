"""Regression guard for season-gated resource placement (issue #1).

The world is generated once in spring, at which point ``ResourcePlacer`` only
places resources available that season. Season-gated resources (e.g. winter's
``mithril_vein``, summer's ``celestial_crystal``) were excluded at placement
time and therefore never appeared — permanently unobtainable.

The fix re-runs resource placement when the season changes, so in-season-only
resources are added onto the existing map (existing nodes are preserved). These
tests assert that behavior.
"""

import contextlib

import pytest

from data import load_json_list
from seasons.season_system import SeasonSystem
from world import world_gen
from world.biome import BiomeRegistry

# Small map so generation is fast and deterministic.
# Increased to 128 to generate sufficient elevation range for mountain biomes
_SMALL = 128


@contextlib.contextmanager
def _small_map():
    saved_w, saved_h = world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT
    world_gen.MAP_WIDTH = _SMALL
    world_gen.MAP_HEIGHT = _SMALL
    try:
        yield
    finally:
        world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT = saved_w, saved_h


def _count(tm, resource_id):
    return sum(
        1
        for x in range(tm.width)
        for y in range(tm.height)
        if tm.tiles[x][y].resource_node is not None
        and tm.tiles[x][y].resource_node.resource_id == resource_id
    )


def _advance_to(ss, target):
    """Tick the season system forward until current_season == target."""
    for _ in range(8):
        if ss.current_season == target:
            return
        ss.tick(ss.season_duration + 1)
    assert ss.current_season == target, f"did not reach {target}"


def test_spring_excluded_resource_is_absent_at_generation():
    """A winter-only resource is not placed when the world is generated in spring."""
    with _small_map():
        registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))
        ss = SeasonSystem()  # defaults to spring
        tm = world_gen.generate(42, registry, ss)
        assert ss.current_season == "spring"
        # mithril_vein is winter-only and spawned by the mountains biome.
        assert _count(tm, "mithril_vein") == 0


def test_spring_inclusive_resource_is_reachable_at_generation():
    """Spring-inclusive resources ARE placed at generation (regression baseline)."""
    with _small_map():
        registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))
        ss = SeasonSystem()
        tm = world_gen.generate(42, registry, ss)
        # void_crystal is available spring/summer/autumn.
        assert _count(tm, "void_crystal") > 0


def test_winter_resource_appears_after_season_change():
    """Winter-only resources get placed once the season reaches winter."""
    with _small_map():
        registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))
        ss = SeasonSystem()
        tm = world_gen.generate(42, registry, ss)
        assert _count(tm, "mithril_vein") == 0  # absent in spring

        _advance_to(ss, "winter")
        assert ss.current_season == "winter"
        assert _count(tm, "mithril_vein") > 0  # placed by re-placement


def test_inclusive_resource_still_reachable_after_season_change():
    """Re-placement must not remove already-placed (spring-inclusive) resources."""
    with _small_map():
        registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))
        ss = SeasonSystem()
        tm = world_gen.generate(42, registry, ss)
        before = _count(tm, "void_crystal")
        assert before > 0

        _advance_to(ss, "winter")
        assert _count(tm, "void_crystal") >= before


def test_replacement_wired_exactly_once():
    """The season-change callback must be registered exactly once per generation."""
    with _small_map():
        registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))
        ss = SeasonSystem()
        world_gen.generate(42, registry, ss)
        registered = [
            cb
            for cb in ss._on_season_changed
            if getattr(cb, "__name__", "") == "_replace_on_season_change"
        ]
        assert len(registered) == 1
