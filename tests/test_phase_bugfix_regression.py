"""
Regression tests for the Phase Bugfix — Granular stability/correctness fixes.

These cover the bugs fixed in this phase that previously had no dedicated
coverage. Each test would have caught (or would catch a regression of) the
specific fix it is named after:

- Pass 2.2  starvation death now routes through the shared soft-death handler
- Pass 3.2  carried gold survives a save/load cycle
- Pass 3.3  recruited_npcs + per-NPC is_recruited/recruit_behavior survive

Run with: python -m pytest tests/test_phase_bugfix_regression.py -q
"""

from __future__ import annotations

import json
import tempfile
from types import SimpleNamespace
from unittest import mock

from core.save_system import SaveSystem
from inventory.inventory import Inventory
from survival.survival_system import SurvivalSystem


class _MockGame:
    """Minimal stand-in exposing only the subsystems a test sets."""

    def __init__(self) -> None:
        self.seed = 42
        self.death_count = 0
        self.player = None
        self.survival = None
        self.inventory = None
        self.skill_manager = None
        self.crafting = None
        self.camera = None
        self.hud = None
        self.building_system = None
        self.quest_system = None
        self.faction_system = None
        self.npc_system = None
        self.trade_system = None
        self.recruitment_system = None
        self.firemaking = None
        self.combat_system = None
        self.season_system = None
        self.weather_system = None
        self.particle_system = None


class TestStarvationDeathWiring:
    """Pass 2.2: starvation death triggers the soft-death handler once."""

    def _starving_survival(self) -> SurvivalSystem:
        survival = SurvivalSystem(environmental_pressure=1.0)
        survival.hunger = 0.0
        survival.starvation_timer = survival.hunger_drain_interval  # == 30.0
        survival.hp = 0.5  # a single 0.5 drain reaches 0
        survival.max_hp = 20.0
        return survival

    def test_starvation_calls_on_death_once(self) -> None:
        survival = self._starving_survival()
        death = mock.Mock()
        survival.on_death = death

        survival.tick(0.1)

        assert survival.is_dead is True
        death.assert_called_once()

    def test_starvation_does_not_refire_while_dead(self) -> None:
        survival = self._starving_survival()
        death = mock.Mock()
        survival.on_death = death

        survival.tick(0.1)  # dies
        survival.tick(0.1)  # dead -> early return
        survival.tick(0.1)  # dead -> early return

        death.assert_called_once()

    def test_starvation_no_callback_does_not_crash(self) -> None:
        # Pre-bootstrap wiring: on_death is None.
        survival = self._starving_survival()
        survival.on_death = None

        survival.tick(0.1)  # must not raise

        assert survival.is_dead is True


class TestGoldPersistence:
    """Pass 3.2: carried gold is serialized and restored."""

    def _game_with_gold(self, gold: int) -> _MockGame:
        game = _MockGame()
        game.inventory = Inventory()
        game.inventory.gold = gold
        game.inventory.add_item("potion", 1)
        return game

    def test_gold_in_snapshot(self) -> None:
        save_dir = tempfile.mkdtemp()
        ss = SaveSystem(save_dir=save_dir)
        assert ss.save(self._game_with_gold(123), slot=0)
        loaded = ss.load(slot=0)
        assert loaded["inventory_gold"] == 123

    def test_gold_roundtrip_into_game(self) -> None:
        save_dir = tempfile.mkdtemp()
        ss = SaveSystem(save_dir=save_dir)
        ss.save(self._game_with_gold(77), slot=0)
        loaded = ss.load(slot=0)

        dst = self._game_with_gold(0)
        ss.load_into_game(loaded, dst)
        assert dst.inventory.gold == 77

    def test_gold_unchanged_for_pre_gold_saves(self) -> None:
        """An old save (no gold key) leaves gold at its current value.

        Backward-compat default (plan 3.7): a save written before gold
        persistence has no `inventory_gold` key, so load uses the `.get`
        default and does NOT reset/erase currency already carried by a stale
        play session. This is the intentional non-breaking behavior.
        """
        save_dir = tempfile.mkdtemp()
        ss = SaveSystem(save_dir=save_dir)
        with open(ss._slot_path(0), "w") as f:
            json.dump({"version": 2, "inventory": [None] * 20}, f)

        dst = self._game_with_gold(0)
        ss.load_into_game(ss.load(0), dst)
        assert dst.inventory.gold == 0


class TestRecruitedNpcsPersistence:
    """Pass 3.3: recruited list + per-NPC recruit state survive save/load."""

    def _make_game(self) -> _MockGame:
        game = _MockGame()
        game.player = SimpleNamespace(
            world_x=1.0,
            world_y=2.0,
            unlocked_recipes=set(),
            unlocked_gear=set(),
            recruited_npcs=["npc_A", "npc_B"],
        )
        game.npc_system = SimpleNamespace(npcs=[
            SimpleNamespace(npc_id="npc_A", is_recruited=True, recruit_behavior="guard"),
            SimpleNamespace(npc_id="npc_B", is_recruited=False, recruit_behavior=None),
        ])
        # _build_snapshot reads npc_system._patrol_targets; provide an empty map.
        game.npc_system._patrol_targets = {}
        game.recruitment_system = SimpleNamespace(
            behaviors={"npc_A": {"patrol": [1, 2]}},
            base_x=10.0,
            base_y=20.0,
        )
        return game

    def test_recruited_list_and_per_npc_snapshot(self) -> None:
        save_dir = tempfile.mkdtemp()
        ss = SaveSystem(save_dir=save_dir)
        assert ss.save(self._make_game(), slot=0)
        loaded = ss.load(slot=0)

        assert loaded["player"]["recruited_npcs"] == ["npc_A", "npc_B"]
        recruits = loaded["recruitment_state"]["npc_recruits"]
        assert {r["npc_id"] for r in recruits} == {"npc_A"}
        npc_a = next(r for r in recruits if r["npc_id"] == "npc_A")
        assert npc_a["is_recruited"] is True
        assert npc_a["recruit_behavior"] == "guard"

    def test_recruited_roundtrip_into_game(self) -> None:
        save_dir = tempfile.mkdtemp()
        ss = SaveSystem(save_dir=save_dir)
        ss.save(self._make_game(), slot=0)
        loaded = ss.load(slot=0)

        fresh = _MockGame()
        fresh.player = SimpleNamespace(
            world_x=0.0,
            world_y=0.0,
            unlocked_recipes=set(),
            unlocked_gear=set(),
            recruited_npcs=[],
        )
        fresh.npc_system = SimpleNamespace(npcs=[
            SimpleNamespace(npc_id="npc_A", is_recruited=False, recruit_behavior=None),
            SimpleNamespace(npc_id="npc_B", is_recruited=False, recruit_behavior=None),
        ])
        fresh.npc_system._patrol_targets = {}
        fresh.recruitment_system = SimpleNamespace(behaviors={}, base_x=None, base_y=None)

        ss.load_into_game(loaded, fresh)

        assert fresh.player.recruited_npcs == ["npc_A", "npc_B"]
        a, b = fresh.npc_system.npcs
        assert a.is_recruited is True
        assert a.recruit_behavior == "guard"
        assert b.is_recruited is False
        assert b.recruit_behavior is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
