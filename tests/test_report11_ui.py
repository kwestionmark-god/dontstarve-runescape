import pygame
from types import SimpleNamespace
from unittest.mock import patch

from core.state import GameState


def _build_error_game(state=GameState.ERROR):
    """Real Game with __init__ bypassed; only the attributes the routing/handlers
    read are set. Reuses the proven patch("core.game.Game.__init__") idiom."""
    with patch("core.game.Game.__init__", return_value=None):
        from core.game import Game
        game = Game()
    game.state = state
    game.seed = 42
    game.loading_progress = 1.0
    game.world = None
    game.player = None
    game._input_router = None
    game.camera = None
    game.hud = None
    game._sprite_renderer = None
    return game


def test_error_state_renders_error_message():
    calls = {"loading": 0, "game": 0}

    def spy_loading(g, screen):
        calls["loading"] += 1

    def spy_render_game(self, screen):
        calls["game"] += 1

    with patch("core.game.render_loading_screen", spy_loading), \
         patch("core.game.Game.render_game", spy_render_game):
        _build_error_game(GameState.ERROR).render(SimpleNamespace())

    assert calls["loading"] == 1   # ERROR must now reach render_loading_screen
    assert calls["game"] == 0      # ... and skip render_game (the blank-blue path)


def test_error_state_enter_returns_to_title():
    game = _build_error_game(GameState.ERROR)
    game.handle_event(SimpleNamespace(type=pygame.KEYDOWN, key=pygame.K_RETURN))
    assert game.state == GameState.TITLE
