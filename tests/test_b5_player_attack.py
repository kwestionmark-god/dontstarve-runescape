"""
test_b5_player_attack.py — B5: player melee attack is invokable via input.

B5: `.player_attack()` existed (with monster counter-attacks already wired in)
but had no non-test caller and no attack key. The fix binds the `J` key in the
input router to `combat_system.player_attack(dt)`, auto-locking the nearest
monster when none is targeted, and surfaces the result as a HUD notification.

These tests exercise the REAL CombatSystem engine (same setup as
test_phase2_combat.py), proving the combat loop itself is sound and that the
cooldown gates spam while monsters counter-attack.
"""

import types
import unittest

import pygame
from core.state import GameState


class FakeMonster:
    """Minimal monster supporting the player_attack code path."""

    def __init__(self, world_x, world_y, hp=1000, attack=10, monster_id="wolf"):
        self.world_x = world_x
        self.world_y = world_y
        self.hp = hp
        self.max_hp = hp
        self.attack = attack
        self.defence = 0
        self.name = "Wolf"
        self.attack_cooldown = 1.5
        self.attack_cooldown_timer = 0.0
        self.monster_id = monster_id
        self.xp_reward = 5
        self.loot_table = []

    def is_alive(self):
        return self.hp > 0

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        return not self.is_alive()


class MockPlayer:
    def __init__(self):
        from skills.skill_manager import SkillManager
        self.skill_manager = SkillManager()
        self.world_x = 0.0
        self.world_y = 0.0
        from combat.gear import PlayerGear
        self.gear = PlayerGear()


class MockSurvival:
    def __init__(self, hp=100):
        self.hp = float(hp)
        self.max_hp = float(hp)
        self.hunger = 100.0
        self.max_hunger = 100.0
        self.is_dead = False

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        return self.hp <= 0


def _combat():
    from combat.combat_system import CombatSystem
    return CombatSystem(MockPlayer(), MockSurvival(hp=100))


class TestPlayerAttack(unittest.TestCase):
    def test_attack_hits_target(self):
        cs = _combat()
        monster = FakeMonster(20.0, 0.0)  # 20px away, within 40px melee range
        cs.monsters.append(monster)
        cs.select_target(monster)

        result = cs.player_attack(0.0)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.damage_dealt, 1)
        self.assertLess(monster.hp, monster.max_hp)  # took damage
        self.assertTrue(monster.is_alive())
        self.assertIn("hit", result.message)

    def test_attack_gated_by_cooldown(self):
        cs = _combat()
        cs.monsters.append(FakeMonster(20.0, 0.0))
        cs.select_target(cs.monsters[0])

        first = cs.player_attack(0.0)
        self.assertIsNotNone(first)  # cooldown was 0 → attack lands (AttackResult)
        self.assertGreater(cs.player_attack_cooldown, 0.0)  # cooldown now armed

        second = cs.player_attack(0.0)
        self.assertIsNone(second)  # still on cooldown → no attack

    def test_no_target_returns_none(self):
        cs = _combat()
        result = cs.player_attack(0.0)
        self.assertIsNone(result)
        self.assertIsNone(cs.selected_target)

    def test_out_of_range_returns_none(self):
        cs = _combat()
        cs.monsters.append(FakeMonster(500.0, 0.0))  # far away
        cs.select_target(cs.monsters[0])
        result = cs.player_attack(0.0)
        self.assertIsNone(result)

    def test_monster_counter_attacks_player(self):
        cs = _combat()
        monster = FakeMonster(20.0, 0.0, attack=20)
        monster.attack_cooldown_timer = 0.0  # ready to counter
        cs.monsters.append(monster)
        cs.select_target(monster)

        hp_before = cs.survival.hp
        result = cs.player_attack(0.0)

        self.assertIsNotNone(result)
        self.assertGreater(result.damage_taken, 0)  # monster hit back
        self.assertLess(cs.survival.hp, hp_before)  # player took damage

    def test_monster_death_grants_kill_message(self):
        cs = _combat()
        monster = FakeMonster(20.0, 0.0, hp=1)  # dies to the first hit
        cs.monsters.append(monster)
        cs.select_target(monster)

        result = cs.player_attack(0.0)
        self.assertIsNotNone(result)
        self.assertTrue(result.monster_died)
        self.assertIn("killed", result.message)
        self.assertNotIn(monster, cs.monsters)


class TestAutoLockTarget(unittest.TestCase):
    def test_auto_lock_selects_nearest(self):
        cs = _combat()
        cs.monsters.append(FakeMonster(100.0, 0.0))   # 100px
        cs.monsters.append(FakeMonster(30.0, 0.0))    # 30px  <- nearest
        self.assertTrue(cs.auto_lock_target())
        self.assertEqual(cs.selected_target.world_x, 30.0)

    def test_auto_lock_ignores_dead(self):
        cs = _combat()
        dead = FakeMonster(20.0, 0.0)
        dead.hp = 0
        cs.monsters.append(dead)
        cs.monsters.append(FakeMonster(50.0, 0.0))
        self.assertTrue(cs.auto_lock_target())
        self.assertEqual(cs.selected_target.world_x, 50.0)

    def test_auto_lock_keeps_existing_alive_target(self):
        cs = _combat()
        far = FakeMonster(2000.0, 0.0)  # outside auto-lock radius
        cs.monsters.append(far)
        cs.monsters.append(FakeMonster(30.0, 0.0))  # nearer, but inside radius
        cs.select_target(far)  # manual selection of the far target
        self.assertFalse(cs.auto_lock_target())  # left untouched
        self.assertIs(cs.selected_target, far)

    def test_auto_lock_returns_false_when_none_in_range(self):
        cs = _combat()
        cs.monsters.append(FakeMonster(10000.0, 0.0))  # far outside 128px
        self.assertFalse(cs.auto_lock_target())
        self.assertIsNone(cs.selected_target)


class TestAttackKeyWiring(unittest.TestCase):
    """Prove the J keydown is wired to combat_system.player_attack via the router."""

    def _router(self, game):
        from input.router import InputRouter
        router = InputRouter.__new__(InputRouter)
        router._game = game
        router._input_manager = types.SimpleNamespace(
            input_state=types.SimpleNamespace(
                open_inventory=False, open_skill_panel=False, open_crafting=False,
                open_building_panel=False, open_quest_panel=False,
                open_trade_panel=False, open_recruit_panel=False,
                open_diplomacy_panel=False, close_crafting=False, close_panel=False,
                hotbar_slot=0, trade_accept_pressed=False, quest_accept_pressed=False,
                faction_negotiate_pressed=False,
            ),
            handle_event=lambda event: None,
        )
        router._panel_dispatcher = types.SimpleNamespace()
        router._npc_flows = None
        return router

    def test_j_key_triggers_attack(self):
        cs = _combat()
        monster = FakeMonster(30.0, 0.0)  # within auto-lock AND melee range
        cs.monsters.append(monster)

        notifications = []
        game = types.SimpleNamespace(
            state=GameState.PLAYING, combat_system=cs,
            player=types.SimpleNamespace(
                world_x=0.0, world_y=0.0,
                action_system=types.SimpleNamespace(
                    add_notification=lambda *a, **k: notifications.append(a),
                ),
            ),
        )
        router = self._router(game)

        router.handle(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_j))

        self.assertEqual(cs.selected_target, monster)  # auto-locked
        self.assertGreater(cs.player_attack_cooldown, 0.0)  # attack landed
        self.assertLess(monster.hp, monster.max_hp)  # took damage
        self.assertTrue(notifications)  # HUD notification surfaced

    def test_j_key_no_combat_system_is_noop(self):
        game = types.SimpleNamespace(
            state=GameState.PLAYING, combat_system=None,
            player=types.SimpleNamespace(action_system=None),
        )
        router = self._router(game)
        # Must not raise when combat_system is absent.
        router.handle(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_j))

    def test_j_key_ignored_outside_playing(self):
        cs = _combat()
        cs.monsters.append(FakeMonster(30.0, 0.0))
        game = types.SimpleNamespace(
            state=GameState.ERROR, combat_system=cs,
            player=types.SimpleNamespace(
                world_x=0.0, world_y=0.0,
                action_system=types.SimpleNamespace(add_notification=lambda *a, **k: None),
            ),
        )
        router = self._router(game)
        router.handle(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_j))
        # Attack key only fires while PLAYING.
        self.assertIsNone(cs.selected_target)


class TestSkillPanelRebind(unittest.TestCase):
    """B5 successor: skill panel moves from J to Tab (J is now attack)."""

    def test_tab_opens_skill_panel(self):
        from input.input_manager import InputManager
        im = InputManager()
        im.handle_event(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_TAB))
        self.assertTrue(im.input_state.open_skill_panel)

    def test_j_no_longer_opens_skill_panel(self):
        from input.input_manager import InputManager
        im = InputManager()
        im.handle_event(types.SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_j))
        self.assertFalse(im.input_state.open_skill_panel)


if __name__ == "__main__":
    unittest.main()

