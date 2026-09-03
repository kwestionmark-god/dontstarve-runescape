"""
test_b25_phase1_2026_fixes.py — Regression tests for the 2026-09-03 audit,
Phase 1 (crash & progression blockers).

Covers:
- 1.1 InputState missing __slots__ for light_fire/save_game (F/F5 AttributeError)
- 1.2 Title screen checked slot["exists"] while SaveSystem.list_slots uses
      "has_save" (Continue unreachable)
- 1.3 FORAGING actions never completed, permanently locking the action system
- 1.4 Trade buy/sell charged/credited stale totals after quantity truncation
      (gold could go negative / sell-side duplication exploit)
- 1.5 faction_leader quest gating (quests.json faction_leader quests must be
      offered by at least one faction_leader NPC)
- 1.6 open_trade_panel/open_quest_panel bypassed Game.set_state (invisible panels)
- 1.7 Loading a save spawned the initial monster population AND restored the
      saved one (duplication)
"""

import json
from pathlib import Path

import pygame
import pytest

from actions import ActionSystem
from actions.types import ActionType, ActionState
from core.state import GameState
from input.input_manager import InputManager
from input.input_state import InputState
from interactions.npc_flows import NPCFlows
from npc.npc_types import MerchantNPC
from npc.trade_system import TradeSystem


# ── 1.1 InputState slots ────────────────────────────────────────────────────


class TestInputStateSlots:
    def test_light_fire_and_save_game_flags_exist(self):
        """F / F5 key presses must not raise AttributeError."""
        mgr = InputManager()
        mgr._set_input_flag("light_fire", True)
        mgr._set_input_flag("save_game", True)
        assert mgr.input_state.light_fire is True
        assert mgr.input_state.save_game is True

    def test_oneshot_flags_cleared_per_frame(self):
        state = InputState()
        state.light_fire = True
        state.save_game = True
        state.attack = True
        state.clear_frame()
        assert state.light_fire is False
        assert state.save_game is False
        assert state.attack is False


# ── 1.2 Title screen save-slot keys ─────────────────────────────────────────


class _StubSaveSystem:
    def __init__(self, slots):
        self._slots = slots

    def list_slots(self):
        return self._slots


class _StubTitleGame:
    def __init__(self, slots):
        self.save_system = _StubSaveSystem(slots)
        self._save_slots = []
        self.state = GameState.TITLE
        self._transitions = []

    def set_state(self, new_state):
        self._transitions.append(new_state)
        self.state = new_state


class TestTitleScreenSaveSlots:
    SLOTS = [
        {"slot": 0, "has_save": True, "seed": 42, "death_count": 1},
        {"slot": 1, "has_save": False},
    ]

    def test_slot_listing_is_cached(self):
        """_draw_save_slots must not re-read every slot file every frame."""
        game = _StubTitleGame(list(self.SLOTS))
        screen = pygame.Surface((800, 600))

        from ui.title_screen import _draw_save_slots

        _draw_save_slots(game, screen)
        game.save_system = None  # second call must not touch the disk/API
        _draw_save_slots(game, screen)
        assert game._save_slots and game._save_slots[0]["has_save"] is True

    def test_continue_reachable_with_has_save_key(self):
        """C key must reach LOADING_SAVE when list_slots uses 'has_save'."""
        game = _StubTitleGame([])
        game._save_slots = list(self.SLOTS)

        from ui.title_screen import handle_title_event

        handle_title_event(game, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c))
        assert GameState.LOADING_SAVE in game._transitions


# ── 1.3 Foraging completion ─────────────────────────────────────────────────


class _FakeResource:
    def __init__(self):
        self.requires_tool = False
        self.xp_reward = 5.0
        self.yield_item = "berries"
        self.yield_quantity = 2
        self.category = "forage"
        self.is_depleted = False

    def harvest(self):
        return True


class _FakeSkillManager:
    def get_effective_stat(self, skill_id, stat):
        return 0.0


class TestForagingCompletion:
    def test_foraging_completes_and_does_not_lock(self, monkeypatch):
        """A FORAGING action must return a result and reset to IDLE, so the
        action system is usable again afterwards."""
        monkeypatch.setattr("random.random", lambda: 0.0)  # force success
        system = ActionSystem()
        resource = _FakeResource()

        err = system.start_action(
            ActionType.FORAGING, resource, _FakeSkillManager(), None,
        )
        assert err is None
        assert system.active.state == ActionState.RUNNING

        result = None
        for _ in range(120):  # foraging duration is 1.0s at 1/60 ticks
            result = system.update(1 / 60)
            if result is not None:
                break

        assert result is not None, "foraging action never completed"
        assert result.success
        assert system.active.state == ActionState.IDLE

        # The action system must accept a new action afterwards.
        err = system.start_action(
            ActionType.FORAGING, resource, _FakeSkillManager(), None,
        )
        assert err is None


# ── 1.4 Trade stale totals ──────────────────────────────────────────────────


class _MockIntelligenceSkill:
    def calculate_buy_price(self, base_price):
        return base_price

    def calculate_sell_price_with_trade(self, base_price):
        return base_price

    def get_merchant_inventory_bonus(self):
        return 99


class _FakeInventory:
    def __init__(self, gold=0):
        self.gold = gold
        self._qty = {}

    def add_item(self, item_id, quantity):
        self._qty[item_id] = self._qty.get(item_id, 0) + quantity
        return True

    def has_items(self, item_id, quantity):
        return self._qty.get(item_id, 0) >= quantity

    def get_item_quantity(self, item_id):
        return self._qty.get(item_id, 0)

    def remove_item(self, item_id, quantity):
        self._qty[item_id] = self._qty.get(item_id, 0) - quantity


class _FakePlayer:
    def __init__(self, inventory):
        self.inventory = inventory

    def distance_to(self, x, y):
        return 0.0


def _merchant(gold):
    return MerchantNPC(
        npc_id="merchant_forest_1",
        name="Forest Trader",
        npc_type="merchant",
        world_x=100.0,
        world_y=100.0,
        sprite_key="npc/merchant_forest",
        faction=None,
        dialogue_lines=["Welcome."],
        behavior="trade",
        patrol_area=(80, 80, 120, 120),
        is_active=True,
        is_recruited=False,
        recruit_behavior=None,
        hostility_level=0.0,
        health=100.0,
        max_health=100.0,
        inventory_capacity=10,
        restock_timer=0.0,
        restock_interval=60.0,
        gold=gold,
        price_modifier=1.0,
        commerce_requirement=0,
    )


def _trade_system():
    ts = TradeSystem(_MockIntelligenceSkill())
    ts.load_trade_data()
    return ts


TRADE_ITEM = "forest_healing_herbs"
ITEM_ID = "healing_herbs"


class TestTradeStaleTotals:
    def test_buy_charges_only_truncated_quantity(self):
        """Buying more than affordable must charge for what was bought."""
        ts = _trade_system()
        merchant = _merchant(gold=1000)
        trade_item = ts._find_trade_item(TRADE_ITEM)
        price = trade_item.buy_price

        player = _FakePlayer(_FakeInventory(gold=price + 1))  # affords exactly 1
        ts.open_trade(player, merchant)

        result = ts.execute_buy(TRADE_ITEM, 5)
        assert result.success
        assert player.inventory.gold == 1  # one unit charged, not five
        assert result.gold_changed == price

    def test_sell_credits_only_truncated_quantity(self):
        """If the merchant can't afford the whole stack, credit only what sold."""
        ts = _trade_system()
        trade_item = ts._find_trade_item(TRADE_ITEM)
        sell_price = trade_item.sell_price
        merchant = _merchant(gold=sell_price)  # can afford exactly 1

        player = _FakePlayer(_FakeInventory(gold=0))
        ts.open_trade(player, merchant)
        player.inventory.add_item(ITEM_ID, 5)

        result = ts.execute_sell(ITEM_ID, 5)
        assert result.success
        assert player.inventory.gold == sell_price  # one unit paid, not five
        assert player.inventory.get_item_quantity(ITEM_ID) == 4


# ── 1.5 Faction-leader quest data ────────────────────────────────────────────


class TestFactionLeaderQuestData:
    def test_faction_leader_quests_are_offered_by_a_npc(self):
        """Every quest gated on giver_npc_type=faction_leader must be listed in
        at least one faction_leader NPC's available_quest_ids, or it is
        unacceptably unreachable."""
        npcs = json.loads(Path("data/npcs.json").read_text())["npcs"]
        quests = json.loads(Path("data/quests.json").read_text())["quests"]

        offered = set()
        for npc in npcs:
            if npc.get("npc_type") == "faction_leader":
                offered.update(npc.get("available_quest_ids", []))

        leader_quests = {
            q["quest_id"]
            for q in quests
            if q.get("giver_npc_type", "quest_giver") == "faction_leader"
        }
        missing = leader_quests - offered
        assert not missing, f"faction-leader quests offered by nobody: {missing}"


# ── 1.6 Panel open goes through set_state ────────────────────────────────────


class _StubPanel:
    def __init__(self):
        self.visible = False
        self.player_set = False

    def set_player(self, player):
        self.player_set = True

    def open_session(self, npc):
        return True

    def close(self):
        self.visible = False


class _StubGame:
    def __init__(self):
        self.state = GameState.PLAYING
        self.player = object()
        self._quest_panel = _StubPanel()
        self._trade_panel = _StubPanel()
        self.set_state_calls = []

    def set_state(self, new_state):
        self.set_state_calls.append(new_state)
        self.state = new_state
        if new_state == GameState.QUEST_PANEL:
            self._quest_panel.visible = True
        elif new_state == GameState.TRADE_PANEL:
            self._trade_panel.visible = True


class TestPanelOpenViaSetState:
    def test_open_quest_panel_uses_set_state(self):
        game = _StubGame()
        NPCFlows(game).open_quest_panel(object())
        assert GameState.QUEST_PANEL in game.set_state_calls
        assert game._quest_panel.visible is True

    def test_open_trade_panel_uses_set_state(self):
        game = _StubGame()
        NPCFlows(game).open_trade_panel(object())
        assert GameState.TRADE_PANEL in game.set_state_calls
        assert game._trade_panel.visible is True


# ── 1.7 No initial monster spawn on save load ────────────────────────────────


class TestNoMonsterDuplicationOnLoad:
    def test_initialize_skips_initial_spawn_when_requested(self):
        from core.bootstrap import Bootstrap

        class _G:
            survival = None
            combat_system = None

        bootstrap = Bootstrap(game=_G(), biome_registry=None)
        spawned = []
        bootstrap._spawn_initial_monsters = lambda: spawned.append(True)
        for name in dir(Bootstrap):
            if name.startswith("_build_") or name.startswith("_wire_"):
                setattr(bootstrap, name, lambda *a, **k: None)

        bootstrap.initialize(skip_initial_spawn=True)
        assert spawned == []

        bootstrap.initialize(skip_initial_spawn=False)
        assert spawned == [True]
