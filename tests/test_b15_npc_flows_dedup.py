"""
test_b15_npc_flows_dedup.py — B15: NPCFlows is a single shared instance.

Previously NPCFlows was constructed in four places (Game.__init__,
Bootstrap._build_npc_flows, InputRouter.__init__, PanelDispatcher.__init__).
NPCFlows holds no state beyond a reference to `game`, so all four were
equivalent wrappers; the dedup keeps Game._npc_flows as the single owner and
has the router and panel_dispatcher share it.
"""

import pytest


class _FakeGame:
    def __init__(self):
        # The single, shared NPCFlows "owner" (sentinel here).
        self._npc_flows = object()


def test_router_and_dispatcher_share_single_npc_flows():
    from input.router import InputRouter
    from input.panel_dispatcher import PanelDispatcher

    game = _FakeGame()
    router = InputRouter(game, object(), None)
    dispatcher = PanelDispatcher(game)

    assert router._npc_flows is game._npc_flows
    assert dispatcher._npc_flows is game._npc_flows


def test_game_without_npc_flows_yields_safe_none():
    """A game without _npc_flows set must not raise at construction time."""

    class _PlainGame:
        pass

    from input.router import InputRouter
    from input.panel_dispatcher import PanelDispatcher

    game = _PlainGame()
    router = InputRouter(game, object(), None)
    dispatcher = PanelDispatcher(game)
    assert router._npc_flows is None
    assert dispatcher._npc_flows is None


def test_bootstrap_no_longer_constructs_npc_flows():
    """Bootstrap._build_npc_flows was removed; only Game.__init__ builds it."""
    import inspect

    from core.bootstrap import Bootstrap

    assert not hasattr(Bootstrap, "_build_npc_flows")
