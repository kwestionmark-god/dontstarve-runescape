"""
Report 4 — Skills System: discriminating regression tests for the four fixes.

Covers:
- Fix 1: gathering success_rate stat no longer inverted (spending points helps)
- Fix 2: smelting grants XP exactly once (no double grant in the click handler)
- Fix 3: wildcard_points survive a save -> load round-trip (and old saves default to 0)
- Fix 4: metallurgy fuel cost + alloy-mastery gate flow from authored recipes.json
"""

import json
from pathlib import Path
from unittest import mock

import pytest

from actions import ActionSystem
from actions.active_action import ActiveAction
from actions.types import ActionType, ActionState
from inventory.recipe import Recipe
from skills.skill_manager import SkillManager
from skills.metallurgy.metallurgy import MetallurgySkill


# ── Fix 1 — Invert the gathering success-rate stat ──────────────────────────


class _FakeResource:
    """Minimal ResourceNode stand-in for start_action / _complete_gathering."""

    def __init__(self) -> None:
        self.requires_tool = False
        self.xp_reward = 15.0
        self.yield_item = "logs"
        self.yield_quantity = 2
        self.category = "wood"
        self.is_depleted = False
        self._depleted = False

    def harvest(self) -> bool:
        """Return False if depleted (here: never depleted)."""
        return not self._depleted


class _FakeSkillManager:
    """Return a fixed success_rate regardless of which stat is queried."""

    def __init__(self, success_rate: float) -> None:
        self._success_rate = success_rate

    def get_effective_stat(self, skill_id, stat) -> float:
        if stat == "success_rate":
            return self._success_rate
        return 0

    def add_xp(self, *_a, **_k) -> None:
        pass


class TestFix1GatheringSuccessRate:
    """Spending woodcutting success_rate points must make harvesting easier."""

    def test_start_action_records_negated_bonus(self) -> None:
        """With success_rate == 10, start_action must store bonus == -10.0."""
        sm = _FakeSkillManager(10)
        system = ActionSystem()
        resource = _FakeResource()
        inventory = mock.MagicMock()

        system.start_action(
            ActionType.WOODCUTTING, resource, sm, inventory,
        )

        assert system.active.state == ActionState.RUNNING
        assert system.active.success_rate_bonus == -10.0

    def test_positive_stat_makes_gather_succeed_at_roll_50(self) -> None:
        """A +10 success_rate raises the threshold to 60, so a 50 roll succeeds.

        Discriminating: under the buggy inversion the threshold is 40 and the
        same roll fails. We pin random to 0.5 (== 50) so the outcome is
        deterministic and hinges entirely on the sign of the stat.
        """
        sm = _FakeSkillManager(10)
        system = ActionSystem()
        resource = _FakeResource()
        inventory = mock.MagicMock()

        system.start_action(
            ActionType.WOODCUTTING, resource, sm, inventory,
        )

        with mock.patch("random.random", return_value=0.5):
            result = system._complete_action()

        assert result is not None and result.success, f"expected a success result, got {result}"

    def test_negative_stat_still_hardens_the_roll(self) -> None:
        """ sanity check: a -10 success_rate lowers the threshold to 40, so a 50
        roll must fail (proves the sign tracks the stat in both directions)."""
        sm = _FakeSkillManager(-10)
        system = ActionSystem()
        resource = _FakeResource()
        inventory = mock.MagicMock()

        system.start_action(
            ActionType.WOODCUTTING, resource, sm, inventory,
        )
        assert system.active.success_rate_bonus == 10.0

        with mock.patch("random.random", return_value=0.5):
            result = system._complete_action()

        assert result is not None and not result.success


# ── Fix 2 — Smelting grants XP exactly once ──────────────────────────────────


class TestFix2NoDoubleXpGrant:
    """The dispatcher must not grant metallurgy XP in addition to attempt_smelt."""

    def test_dispatcher_double_grant_block_removed(self) -> None:
        """The two-line double-grant block must be gone from the click handler."""
        from input.panel_dispatcher import PanelDispatcher

        src = inspect_getsource(PanelDispatcher._handle_smelt_click)
        assert "self.skill_manager.add_xp(\"metallurgy\"" not in src
        assert 'add_xp("metallurgy"' not in src

    def test_attempt_smelt_still_grants_internal_xp(self) -> None:
        """attempt_smelt must remain the single source of the XP grant."""
        from skills.metallurgy.metallurgy import MetallurgySkill

        src = inspect_getsource(MetallurgySkill.attempt_smelt)
        assert "add_xp" in src, "attempt_smelt should still grant XP internally"


def inspect_getsource(fn):
    """Small helper: inspect.getsource without importing inspect at module top."""
    import inspect

    return inspect.getsource(fn)


# ── Fix 3 — Persist & restore wildcard_points ────────────────────────────────


class _MockGame:
    """Minimal game exposing a SkillManager.

    Unset subsystem attributes resolve to None so save/load can run against a
    partial game without a full Game instance.
    """

    def __init__(self) -> None:
        self.seed = 0
        self.death_count = 0
        self.player = None
        self.inventory = None
        self.skill_manager = SkillManager()
        self.survival = None
        self.building_system = None
        self.firemaking = None

    def __getattr__(self, name):
        # Only called when normal lookup fails.
        return None


class TestFix3WildcardPointsRoundTrip:
    """wildcard_points must survive save -> load and old saves default to 0."""

    def _save_dir(self):
        import tempfile

        return tempfile.mkdtemp()

    def test_wildcard_points_round_trip(self) -> None:
        from core.save_system import SaveSystem

        save_system = SaveSystem(save_dir=self._save_dir())

        source = _MockGame()
        source.skill_manager.wildcard_points = 7
        assert save_system.save(source, slot=0)

        fresh = _MockGame()
        fresh.skill_manager.wildcard_points = 0
        loaded = save_system.load(slot=0)
        save_system.load_into_game(loaded, fresh)

        assert fresh.skill_manager.wildcard_points == 7

    def test_missing_key_defaults_to_zero(self) -> None:
        """An older save without the key must restore 0, not raise."""
        from core.save_system import SaveSystem

        save_system = SaveSystem(save_dir=self._save_dir())

        fresh = _MockGame()
        fresh.skill_manager.wildcard_points = 3
        save_system.load_into_game({"skills": {}}, fresh)

        assert fresh.skill_manager.wildcard_points == 0


# ── Fix 4 — Metallurgy fuel cost + alloy-mastery from authored data ──────────


class TestFix4MetallurgyDataRestored:
    """The registry path must carry base_fuel_cost / requires_alloy_mastery
    from data/recipes.json instead of hardcoding 1 / 0."""

    def _registry_from_json(self):
        path = Path("skills/metallurgy/data/recipes.json")
        with open(path) as f:
            data = json.load(f)
        recipes = {}
        for entry in data["recipes"]:
            r = Recipe.from_dict(entry)
            if r.processing_chain.startswith("metallurgy_"):
                recipes[r.recipe_id] = r
        return recipes

    def test_steel_recipe_preserves_fuel_and_alloy_gate(self) -> None:
        """smelt_steel (authored fuel=2, alloy=2) must survive the registry path."""
        registry = self._registry_from_json()
        skill = MetallurgySkill(SkillManager(), recipe_registry=mock.MagicMock(
            recipes=registry))
        recipes = skill._get_smelt_recipes()

        steel = recipes["smelt_steel"]
        assert steel.base_fuel_cost == 2
        assert steel.requires_alloy_mastery == 2

    def test_iron_recipe_stays_at_one(self) -> None:
        """A base_fuel_cost=1 recipe must remain 1 (no over-inflation)."""
        registry = self._registry_from_json()
        skill = MetallurgySkill(SkillManager(), recipe_registry=mock.MagicMock(
            recipes=registry))
        recipes = skill._get_smelt_recipes()

        iron = recipes["smelt_iron"]
        assert iron.base_fuel_cost == 1
        assert iron.requires_alloy_mastery == 0
