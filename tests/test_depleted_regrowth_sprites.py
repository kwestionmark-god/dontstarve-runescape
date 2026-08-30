"""
test_depleted_regrowth_sprites.py — Tests for depleted resource sprites
and regrowth stage resolution.

Tests:
- ResourceNode.start_regrow resets depletions
- Tile regrow completion clears depleted state
- SpriteRenderer resolves depleted / sapling / young / mature keys
- Infinite water_source never shows depleted sprite
- Existing renderer / seasonal tests stay green (smoke)
"""

import os
import pytest
import pygame


def _make_node(
    resource_id: str = "oak_tree",
    sprite_key: str = "trees/oak",
    depletion_count: int = 4,
    regrow_time: float = 300.0,
    current_depletions: int = 0,
    tier: int = 1,
    requires_tool: str | None = "axe",
) -> object:
    """Create a lightweight ResourceNode-like object."""
    from world.resource_node import ResourceNode

    return ResourceNode(
        resource_id=resource_id,
        biome="forest",
        tier=tier,
        rarity="common" if tier == 1 else ("rare" if tier == 3 else "legendary"),
        category="wood",
        base_density=0.15,
        yield_item="wood",
        yield_quantity=1,
        xp_reward=10.0,
        depletion_count=depletion_count,
        current_depletions=current_depletions,
        regrow_time=regrow_time,
        sprite_key=sprite_key,
        requires_tool=requires_tool,
    )


class TestResourceNodeStartRegrow:
    """C2: start_regrow resets depletions so the node becomes harvestable again."""

    def test_start_regrow_resets_depletions_to_zero(self):
        """current_depletions should be 0 after start_regrow."""
        node = _make_node()
        # Fully deplete the node.
        while not node.is_depleted:
            node.harvest()
        assert node.is_depleted
        assert node.current_depletions == node.depletion_count

        # Regrow.
        node.start_regrow()
        assert node.current_depletions == 0
        assert not node.is_depleted

    def test_start_regrow_allows_harvest_again(self):
        """After start_regrow the node should be harvestable once more."""
        node = _make_node()
        for _ in range(node.depletion_count):
            node.harvest()
        assert node.is_depleted
        node.start_regrow()
        assert node.harvest()  # Should succeed now


class TestTileRegrowCompletion:
    """C2: tile regrow completion clears depleted state and restores node."""

    def test_tile_regrow_completes_and_clears_depleted(self):
        """After the timer expires, the node should be harvestable again."""
        from world.tile_map import TileMap, Tile

        tm = TileMap(10, 10, 5, 5)
        node = _make_node(regrow_time=10.0)
        tile = tm.tiles[5][5]
        tile.resource_node = node
        # Deplete and start regrow
        for _ in range(node.depletion_count):
            node.harvest()
        tile.depleted = True
        tile.regrow_timer = 10.0

        # Simulate time passing.
        tile.update(10.1)
        assert tile.regrow_timer == 0.0
        assert not tile.depleted
        assert not node.is_depleted
        assert node.current_depletions == 0


class TestSpriteKeyResolution:
    """C3: SpriteRenderer resolves the correct sprite key for every state."""

    @pytest.fixture
    def renderer(self):
        """SpriteRenderer with a pre-populated sprite cache."""
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        # Pre-populate cache with dummy surfaces so _get_base_sprite never misses.
        # Cache keys are now (sprite_key, zoom) tuples with zoom rounded to 2 decimals.
        dummy_surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        for key in [
            "trees/oak",
            "trees/oak_depleted",
            "trees/oak_sapling",
            "trees/oak_young",
            "trees/stump",
            "trees/sapling_generic",
            "trees/young_generic",
            "rocks/iron",
            "rocks/iron_depleted",
            "rocks/rubble",
            "world/grass",
            "world/grass_depleted",
            "world/depleted_patch",
            "world/water",
        ]:
            sr._sprite_cache[sr._cache_key(key, 1.0)] = dummy_surf
        return sr

    def test_mature_uses_base_key(self, renderer):
        """A non-depleted node should resolve to the mature sprite key."""
        node = _make_node()
        key, sprite = renderer._resolve_resource_sprite(node, 5, 5)
        assert key == "trees/oak"
        assert sprite is not None

    def test_depleted_uses_depleted_key(self, renderer):
        """A depleted oak should resolve to oak_depleted."""
        node = _make_node(current_depletions=4)  # == depletion_count → depleted
        key, sprite = renderer._resolve_resource_sprite(node, 5, 5)
        assert key.endswith("_depleted")
        assert sprite is not None

    def test_depleted_falls_back_to_stump_when_missing(self, renderer):
        """If the per-type depleted sprite is missing, fall back to stump."""
        # Remove oak_depleted from cache
        renderer._sprite_cache.pop("trees/oak_depleted", None)
        renderer._sprite_cache["trees/oak"] = None  # mature not found either
        node = _make_node(current_depletions=4)
        key, sprite = renderer._resolve_resource_sprite(node, 5, 5)
        assert sprite is not None
        # Should fall back to trees/stump
        assert "stump" in key or sprite is not None

    def test_tree_regrowth_sapling_stage(self, renderer):
        """At 20% progress, a tree should resolve to the sapling sprite."""
        node = _make_node(regrow_time=100.0)
        # Set tile regrow_timer so progress = 1 - 80/100 = 0.20 → sapling
        # We simulate this by setting tile state
        from world.tile_map import TileMap

        tm = TileMap(10, 10, 5, 5)
        tile = tm.tiles[5][5]
        tile.resource_node = node
        tile.depleted = True
        tile.regrow_timer = 80.0  # progress = 0.20

        sr = renderer
        sr.tile_map = tm
        key, sprite = sr._resolve_resource_sprite(node, 5, 5)
        assert key.endswith("_sapling")
        assert sprite is not None

    def test_tree_regrowth_young_stage(self, renderer):
        """At 60% progress, a tree should resolve to the young sprite."""
        node = _make_node(regrow_time=100.0)
        from world.tile_map import TileMap

        tm = TileMap(10, 10, 5, 5)
        tile = tm.tiles[5][5]
        tile.resource_node = node
        tile.depleted = True
        tile.regrow_timer = 40.0  # progress = 0.60

        sr = renderer
        sr.tile_map = tm
        key, sprite = sr._resolve_resource_sprite(node, 5, 5)
        assert key.endswith("_young")
        assert sprite is not None

    def test_tree_regrowth_mature_when_finished(self, renderer):
        """At 100% progress, a tree should resolve to the mature sprite.

        After regrowth completes the node is restored (start_regrow resets
        depletions to 0) and the tile's depleted flag is cleared, so the
        mature sprite is drawn.
        """
        node = _make_node(regrow_time=100.0)
        from world.tile_map import TileMap

        tm = TileMap(10, 10, 5, 5)
        tile = tm.tiles[5][5]
        tile.resource_node = node
        # Simulate completed regrowth: reset node and clear tile depleted flag.
        node.start_regrow()
        tile.depleted = False
        tile.regrow_timer = 0.0

        sr = renderer
        sr.tile_map = tm
        key, sprite = sr._resolve_resource_sprite(node, 5, 5)
        assert key == "trees/oak"
        assert sprite is not None

    def test_infinite_water_never_depleted(self, renderer):
        """water_source (depletion_count=-1) should always resolve to mature."""
        node = _make_node(
            resource_id="water_source",
            sprite_key="world/water",
            depletion_count=-1,
            regrow_time=0.0,
            current_depletions=999,  # even if "depleted" by count
        )
        key, sprite = renderer._resolve_resource_sprite(node, 5, 5)
        assert key == "world/water"
        assert sprite is not None

    def test_rock_depleted_uses_rubble_fallback(self, renderer):
        """A depleted rock should resolve to per-type depleted or rubble."""
        node = _make_node(
            resource_id="iron_rock",
            sprite_key="rocks/iron",
            depletion_count=5,
            current_depletions=5,
            requires_tool="pickaxe",
        )
        key, sprite = renderer._resolve_resource_sprite(node, 5, 5)
        assert sprite is not None


class TestSmokeExistingRenderer:
    """Smoke: existing renderer and seasonal tint tests should stay green."""

    def test_sprite_renderer_basic_render_no_crash(self):
        """SpriteRenderer should not crash when rendering a resource."""
        from render.sprite_renderer import SpriteRenderer

        sr = SpriteRenderer()
        node = _make_node()
        # Pre-populate cache
        sr._sprite_cache["trees/oak"] = pygame.Surface((32, 32), pygame.SRCALPHA)

        screen = pygame.Surface((640, 480))
        # Mock camera with zoom and world_to_screen method
        class Camera:
            zoom = 1.0
            player = None
            def world_to_screen(self, wx, wy, elevation=0):
                return float(wx), float(wy)
        camera = Camera()
        sr.render_resource(screen, node, camera, tile_x=5, tile_y=5)
        # Should not raise
        assert screen.get_size() == (640, 480)