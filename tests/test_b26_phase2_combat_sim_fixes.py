"""
test_b26_phase2_combat_sim_fixes.py — Regression tests for the 2026-09-03
audit, Phase 2 (combat/quest simulation correctness).

Covers:
- 2.1 Hostile monsters initiate attacks (previously only counter-attacked,
      and ranged monsters could never even counter)
- 2.2 Hostile faction NPCs must be within melee range to hit the player
      (previously sniped from FACTION_AGGRESSION_RANGE = 150px)
- 2.3 Faction/turret kills no longer penalize the player's faction standing
- 2.4 record_trade / record_delivery / record_faction_attack are wired
- 2.5 required_faction_status compares the quest's giver_faction standing
      (previously passed the status label as a faction id)
- 2.6 Enter in trade/quest panels fires once (router accept handler returns
      before panel key dispatch)
- 2.7 Negotiation standing applied once, only on success
"""

from combat.combat_system import CombatSystem
from combat.monster import Monster
from npc.faction_system import FactionSystem
from npc.quest_system import QuestSystem
from npc.npc_types import MerchantNPC
from npc.trade_system import TradeSystem


# ── Shared fakes ─────────────────────────────────────────────────────────────


class _SkillManager:
    def get_effective_stat(self, skill_id, stat):
        return 0.0

    def get_skill_level(self, skill_id):
        return 99

    def add_xp(self, *a, **k):
        pass

    def add_xp_with_notification(self, *a, **k):
        return []


class _Survival:
    def __init__(self):
        self.hp = 100.0
        self.taken = []

    def take_damage(self, amount):
        self.hp -= amount
        self.taken.append(amount)
        return False


class _Gear:
    def get_defence_bonus(self):
        return 0


class _Player:
    def __init__(self, x=0.0, y=0.0):
        self.world_x = x
        self.world_y = y
        self.skill_manager = _SkillManager()
        self.gear = _Gear()
        self.action_system = None

    def distance_to(self, x, y):
        import math
        return math.hypot(self.world_x - x, self.world_y - y)


def _monster(x=0.0, y=0.0, hostile=True, attack=10):
    return Monster(
        monster_id="goblin",
        name="Goblin",
        biome="forest",
        world_x=x,
        world_y=y,
        hp=50,
        attack=attack,
        defence=0,
        speed=50.0,
        is_hostile=hostile,
    )


# ── 2.1 Monster-initiated attacks ────────────────────────────────────────────


class TestMonsterInitiatesAttacks:
    def test_hostile_monster_in_attack_range_hits_player(self):
        player = _Player(x=0.0, y=0.0)
        survival = _Survival()
        player.action_system = type("AS", (), {"survival": survival})()
        cs = CombatSystem(player, survival)
        monster = _monster(x=20.0, y=0.0)  # within default 40px attack range
        cs.register_monster(monster)

        # Monster sees the player and engages
        monster.update_ai(player, 0.0)  # idle → chase path runs
        for _ in range(5):
            cs.tick(0.016)

        assert monster.ai_state == "attack"
        assert survival.taken, "monster never attacked the player"
        assert monster.attack_cooldown_timer > 0

    def test_non_hostile_monster_does_not_initiate(self):
        player = _Player(x=0.0, y=0.0)
        survival = _Survival()
        player.action_system = type("AS", (), {"survival": survival})()
        cs = CombatSystem(player, survival)
        monster = _monster(x=20.0, y=0.0, hostile=False)
        monster.ai_state = "attack"
        monster.attack_cooldown_timer = 0.0
        cs.register_monster(monster)

        cs.tick(0.016)
        assert survival.taken == []


# ── 2.2 Faction NPC melee range gate ─────────────────────────────────────────


class _StubCombatSystem:
    def __init__(self):
        self.monsters = []
        self.damage_numbers = []

    def get_nearby_monsters(self, x, y, r):
        return []


class _StubNPCSystem:
    def __init__(self, npcs):
        self.npcs = npcs


class _StubActionSystem:
    def __init__(self, survival):
        self.survival = survival

    def add_notification(self, *a, **k):
        pass


class _FactionNPC:
    def __init__(self, x, y):
        self.npc_id = "leader_1"
        self.npc_type = "faction_leader"
        self.world_x = x
        self.world_y = y
        self.faction = "goblins"
        self.faction_strength = 1.0
        self.is_active = True
        self.is_recruited = False


class _StubGame:
    def __init__(self, player, npcs):
        self.player = player
        self.combat_system = _StubCombatSystem()
        self.npc_system = _StubNPCSystem(npcs)


class TestFactionMeleeGate:
    FACTIONS = {"factions": [{
        "faction_id": "goblins", "name": "Goblins",
        "territory_biomes": ["forest"], "hostile_monster_types": [],
        "hostility": 0.8, "leader_npc_id": "leader_1",
    }]}

    def _setup(self, player_x):
        player = _Player(x=player_x, y=0.0)
        survival = _Survival()
        player.action_system = _StubActionSystem(survival)
        npc = _FactionNPC(x=0.0, y=0.0)
        game = _StubGame(player, [npc])
        fs = FactionSystem(self.FACTIONS)
        fs.game = game
        fs._standing["goblins"] = 0.0  # maximally hostile
        return fs, survival

    def test_no_damage_beyond_melee_range(self):
        fs, survival = self._setup(player_x=100.0)  # inside 150 aggro, outside 40 melee
        fs.update_faction_npc_behavior(0.016)
        assert survival.taken == []

    def test_damage_within_melee_range(self):
        fs, survival = self._setup(player_x=20.0)
        fs.update_faction_npc_behavior(0.016)
        assert survival.taken, "hostile faction NPC in melee range did not attack"


# ── 2.3 Kill credit ──────────────────────────────────────────────────────────


class TestKillCredit:
    def _setup(self):
        player = _Player()
        survival = _Survival()
        cs = CombatSystem(player, survival)
        fs = FactionSystem({"factions": [{
            "faction_id": "goblins", "name": "Goblins",
            "territory_biomes": ["forest"], "hostile_monster_types": ["goblin"],
            "hostility": 0.8, "leader_npc_id": "leader_1",
        }]})
        cs.faction_system = fs
        return cs, fs

    def test_player_kill_penalizes_standing(self):
        cs, fs = self._setup()
        monster = _monster()
        monster.hp = 0
        cs._monster_died(monster, killed_by_player=True)
        assert fs.get_standing("goblins") < 0.5

    def test_faction_or_turret_kill_does_not_penalize_player(self):
        cs, fs = self._setup()
        monster = _monster()
        monster.hp = 0
        cs._monster_died(monster, killed_by_player=False)
        assert fs.get_standing("goblins") == 0.5


# ── 2.4 Quest tracker wiring ─────────────────────────────────────────────────


class _RecordingQuestSystem:
    def __init__(self):
        self.trades = []
        self.deliveries = []
        self.faction_attacks = []

    def record_trade(self, npc_id):
        self.trades.append(npc_id)

    def record_delivery(self, item_id):
        self.deliveries.append(item_id)

    def record_faction_attack(self, faction_id):
        self.faction_attacks.append(faction_id)


class _IntSkill:
    def calculate_buy_price(self, p):
        return p

    def calculate_sell_price_with_trade(self, p):
        return p

    def get_merchant_inventory_bonus(self):
        return 99


class _TradeInventory:
    def __init__(self, gold=1000):
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


def _merchant():
    return MerchantNPC(
        npc_id="merchant_forest_1", name="Forest Trader", npc_type="merchant",
        world_x=0.0, world_y=0.0, sprite_key="npc/merchant_forest",
        faction=None, dialogue_lines=[], behavior="trade",
        patrol_area=(0, 0, 10, 10), is_active=True, is_recruited=False,
        recruit_behavior=None, hostility_level=0.0, health=100.0,
        max_health=100.0, inventory_capacity=10, restock_timer=0.0,
        restock_interval=60.0, gold=1000, price_modifier=1.0,
        commerce_requirement=0,
    )


class TestQuestTrackerWiring:
    def test_buy_records_trade(self):
        qs = _RecordingQuestSystem()
        ts = TradeSystem(_IntSkill())
        ts.load_trade_data()
        ts.set_quest_system(qs)
        player = _Player()
        player.inventory = _TradeInventory()
        ts.open_trade(player, _merchant())
        result = ts.execute_buy("forest_healing_herbs", 1)
        assert result.success
        assert qs.trades == ["merchant_forest_1"]

    def test_sell_records_trade_and_delivery(self):
        qs = _RecordingQuestSystem()
        ts = TradeSystem(_IntSkill())
        ts.load_trade_data()
        ts.set_quest_system(qs)
        player = _Player()
        player.inventory = _TradeInventory()
        ts.open_trade(player, _merchant())
        player.inventory.add_item("healing_herbs", 3)
        result = ts.execute_sell("healing_herbs", 2)
        assert result.success
        assert qs.trades == ["merchant_forest_1"]
        assert qs.deliveries == ["healing_herbs"]

    def test_damaging_faction_npc_records_faction_attack(self):
        qs = _RecordingQuestSystem()
        player = _Player()
        survival = _Survival()
        cs = CombatSystem(player, survival)
        cs.game = type("G", (), {"quest_system": qs})()

        npc = _FactionNPC(x=0.0, y=0.0)
        npc.health = 100.0
        cs.npc_take_damage(npc, 5)
        assert qs.faction_attacks == ["goblins"]

    def test_npc_damage_does_not_clear_monster_target(self):
        player = _Player()
        survival = _Survival()
        cs = CombatSystem(player, survival)
        cs.game = type("G", (), {"quest_system": None})()
        monster = _monster()
        cs.register_monster(monster)
        cs.select_target(monster)

        npc = _FactionNPC(x=0.0, y=0.0)
        npc.health = 100.0
        cs.npc_take_damage(npc, 5)
        assert cs.selected_target is monster


# ── 2.5 Faction-status eligibility ───────────────────────────────────────────


class TestFactionStatusEligibility:
    def _quest_def(self):
        qs = QuestSystem(_IntSkill())
        qs.load_quest_data()
        return qs, qs.quest_definitions["goblin_diplomacy"]

    def test_status_checked_against_giver_faction(self):
        qs, qd = self._quest_def()
        fs = FactionSystem({"factions": [{
            "faction_id": "goblins", "name": "Goblins",
            "territory_biomes": ["forest"], "hostile_monster_types": [],
            "hostility": 0.8, "leader_npc_id": "leader_1",
        }]})
        qs.faction_system = fs

        player = _Player()

        # "suspicious" required; neutral 0.5 standing = "neutral" should meet
        # or fail per _status_meets_threshold ordinal rules — the point is the
        # check consults the goblins faction, not a faction literally named
        # "suspicious".
        fs._standing["goblins"] = 0.0  # hostile: must fail the "suspicious" gate
        result = qs.check_quest_eligibility(player, qd)
        assert result.faction_status_met is False

        fs._standing["goblins"] = 1.0  # allied: must pass
        result = qs.check_quest_eligibility(player, qd)
        assert result.faction_status_met is True


# ── 2.6 Enter fires once in trade/quest panels ───────────────────────────────


class TestEnterDoubleFire:
    def test_enter_routes_to_accept_handler_only(self):
        import pygame
        from core.state import GameState
        from input.router import InputRouter

        router = InputRouter(None, None, None)
        calls = {"accept": 0, "panel": 0}

        from input.input_state import InputState

        class _IM:
            def __init__(self):
                self.input_state = InputState()

        router._input_manager = _IM()

        class Flows:
            def handle_trade_accept_keyboard(self):
                calls["accept"] += 1

        class Panel:
            def handle_key(self, key):
                calls["panel"] += 1
                return ("buy", "x", 1)

        class Game:
            state = GameState.TRADE_PANEL
            _trade_panel = Panel()

        game = Game()
        router._npc_flows = Flows()
        router._input_manager.input_state.trade_accept_pressed = True

        class Dispatcher:
            def __init__(self):
                self.dispatched = []

            def dispatch(self, state, action):
                self.dispatched.append(action)

        dispatcher = Dispatcher()
        router._handle_keydown(
            game, router._input_manager, dispatcher,
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN),
        )

        assert calls["accept"] == 1
        assert calls["panel"] == 0
        assert dispatcher.dispatched == []


# ── 2.7 Negotiation standing applied once ────────────────────────────────────


class TestNegotiationStanding:
    def test_record_negotiation_does_not_touch_standing(self):
        qs = QuestSystem(_IntSkill())

        class FS:
            def __init__(self):
                self.changes = []

            def update_standing(self, fid, delta):
                self.changes.append((fid, delta))

        fs = FS()
        qs.faction_system = fs
        qs.record_negotiation("goblins")
        assert fs.changes == [], "record_negotiation must not mutate standing"
        assert qs._negotiation_counts["goblins"] == 1
