"""Tests for bootstrap wiring."""

import pytest


def test_bootstrap_uses_public_death_handler_setter():
    """Verify CombatSystem has public set_player_death_handler method."""
    from combat.combat_system import CombatSystem
    assert hasattr(CombatSystem, 'set_player_death_handler'), "CombatSystem missing public set_player_death_handler"


def test_combat_system_death_handler_called():
    """Verify the death handler is called when _on_player_death is invoked."""
    from combat.combat_system import CombatSystem
    from core.player import Player
    from survival.survival_system import SurvivalSystem

    class MockGame:
        pass

    class MockPlayer:
        def __init__(self):
            self.skill_manager = None
            self.action_system = None
            self.world_x = 0
            self.world_y = 0

    class MockSurvival:
        def __init__(self):
            self.max_hp = 100
            self.max_hunger = 100
            self.hp = 100
            self.hunger = 100
            self.is_dead = False

    # Create real instances
    player = MockPlayer()
    survival = MockSurvival()
    game = MockGame()
    game.death_count = 0
    game.world = type('obj', (object,), {'spawn_x': 0, 'spawn_y': 0})()
    game.save_system = None

    combat = CombatSystem(
        player=player,
        survival=survival,
        building_system=None,
        firemaking=None,
        game=game,
        faction_system=None,
    )

    # Track if handler was called
    called = {'value': False}
    def test_handler():
        called['value'] = True

    combat.set_player_death_handler(test_handler)
    combat._on_player_death()

    assert called['value'], "Death handler was not called"