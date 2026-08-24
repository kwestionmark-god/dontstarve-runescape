"""
test_b21_is_near_monster.py — B21: _is_near_monster is a real proximity check.

Previously this returned False unconditionally (a stub), so NPC placement never
excluded tiles near monsters. It now measures the Euclidean distance from a
tile's center to every monster's world position against the exclusion radius,
and guards the None combat_system / None game cases (NPCSystem is built before
combat_system exists during bootstrap).
"""

import math


class _MockTileMap:
    def get_tile(self, x, y):
        return None


def _npc_with_game(combat_system=None):
    from npc.npc_system import NPCSystem

    ns = NPCSystem(_MockTileMap())

    class _Game:
        pass

    ns.game = _Game()
    ns.game.combat_system = combat_system
    return ns


def _monster(wx, wy):
    class _Monster:
        def __init__(self):
            self.world_x = wx
            self.world_y = wy

    return _Monster()


class _Monsters:
    def __init__(self, list_):
        self.monsters = list_


def _center_tile(tile):
    """Pixel center of a tile (matches spawn placement math)."""
    return tile * 64 + 32


def test_monster_within_radius_returns_true():
    # Monster sitting exactly on tile (10, 10).
    cs = _Monsters([_monster(_center_tile(10), _center_tile(10))])
    ns = _npc_with_game(cs)
    assert ns._is_near_monster(10, 10) is True


def test_monster_two_away_within_radius_returns_true():
    # Monster on tile (12, 10) — 2 tiles east, still inside the 3-tile radius.
    cs = _Monsters([_monster(_center_tile(12), _center_tile(10))])
    ns = _npc_with_game(cs)
    assert ns._is_near_monster(10, 10) is True


def test_monster_far_away_returns_false():
    cs = _Monsters([_monster(_center_tile(10), _center_tile(10))])
    ns = _npc_with_game(cs)
    assert ns._is_near_monster(25, 25) is False


def test_no_monsters_returns_false():
    ns = _npc_with_game(_Monsters([]))
    assert ns._is_near_monster(10, 10) is False


def test_none_game_returns_false():
    from npc.npc_system import NPCSystem

    ns = NPCSystem(_MockTileMap())  # game defaults to None
    assert ns._is_near_monster(10, 10) is False


def test_none_combat_system_returns_false():
    ns = _npc_with_game(None)
    assert ns._is_near_monster(10, 10) is False
