"""Tests for game_loop.py"""

import pytest


def test_game_loop_uses_config_fps():
    """Verify game_loop.py uses config.TARGET_FPS instead of hardcoded 60"""
    import core.game_loop as gl
    import inspect

    src = inspect.getsource(gl)
    # Should import TARGET_FPS from config
    assert 'from config import TARGET_FPS' in src, "Missing import of TARGET_FPS from config"
    # Should use TARGET_FPS in the tick call
    assert 'tick(TARGET_FPS)' in src or 'tick( TARGET_FPS )' in src, "Should use TARGET_FPS in tick() call"
    # Should NOT have hardcoded 60 in tick()
    assert 'tick(60)' not in src, "Found hardcoded tick(60) - should use TARGET_FPS"


def test_game_loop_imports_target_fps_from_config():
    """Verify the import is present in game_loop.py"""
    import core.game_loop as gl
    import inspect
    src = inspect.getsource(gl)
    assert 'from config import TARGET_FPS' in src or 'config.TARGET_FPS' in src