"""
test_b7_water_harvestable.py — B7: renewable "water" resource must be harvestable.

The ``water_source`` record uses ``depletion_count = -1`` to mean "unending".
``is_depleted`` must honor that convention (never depleted) so the harvest
gate in ``action_system`` accepts water. Finite resources are unaffected.
"""

import pytest

from world.resource_node import ResourceNode


def _water() -> ResourceNode:
    return ResourceNode(
        resource_id="water_source",
        biome="forest",
        tier=1,
        rarity="ubiquitous",
        category="water",
        base_density=0.1,
        yield_item="water_bucket",
        yield_quantity=1,
        xp_reward=1.0,
        depletion_count=-1,
        current_depletions=0,
        regrow_time=0.0,
        sprite_key="world/water",
        requires_tool=None,
    )


def _finite(count: int = 3) -> ResourceNode:
    return ResourceNode(
        resource_id="oak_tree",
        biome="forest",
        tier=1,
        rarity="common",
        category="wood",
        base_density=0.15,
        yield_item="logs",
        yield_quantity=1,
        xp_reward=5.0,
        depletion_count=count,
        current_depletions=0,
        regrow_time=100.0,
        sprite_key="trees/oak",
        requires_tool="axe",
    )


def test_water_is_never_depleted():
    node = _water()
    assert node.is_depleted is False
    # Even an arbitrarily high depletion counter must not count water as done.
    node.current_depletions = 10_000
    assert node.is_depleted is False


def test_water_is_harvestable_repeatedly():
    node = _water()
    for _ in range(50):
        assert node.harvest() is True


def test_water_zero_depletion_count_is_unending():
    # Convention applies to 0 as well as negative.
    node = _water()
    node.depletion_count = 0
    assert node.is_depleted is False
    assert node.harvest() is True


def test_finite_node_still_depletes():
    node = _finite()
    assert node.is_depleted is False
    assert node.remaining_depletions == 3
    for _ in range(3):  # exactly `depletion_count` harvests allowed
        assert node.harvest() is True
    assert node.is_depleted is True
    assert node.harvest() is False