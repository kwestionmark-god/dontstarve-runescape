"""
Report 9 — Interaction & Input Layer fixes.

Fix 1: cooking a campfire-required recipe through the crafting panel must not crash.
The dispatcher called the nonexistent `game._check_nearby_campfire()` (wrong method
name); the real proximity check is `game._fire_interaction.check_nearby_campfire()`.

Fix 2: the five dead `InteractSystem.open_*_panel` methods (zero callers) are removed,
and `handle_interact` still starts a gathering action.
"""

import types
from unittest import mock

from core.state import GameState
from input.panel_dispatcher import PanelDispatcher
from interactions.interact import InteractSystem
from actions import ActionState, ActionType

DEAD = (
    "open_trade_panel",
    "open_quest_panel",
    "_handle_other_npc_interaction",
    "open_recruit_panel",
    "open_diplomacy_panel",
)


def test_cook_campfire_recipe_does_not_crash():
    # A plain SimpleNamespace means a genuinely-missing attribute raises AttributeError
    # (a MagicMock would auto-create _check_nearby_campfire and mask the crash).
    recipe = types.SimpleNamespace(
        requires_campfire=True, is_food=False, output_item=None,
    )
    calls = {"campfire": False, "cook": False}

    def check_nearby_campfire():
        calls["campfire"] = True
        return True

    def cook(item_id, *a, **k):
        calls["cook"] = True
        return types.SimpleNamespace(success=True, message="cooked")

    player = types.SimpleNamespace(
        world_x=1.0, world_y=2.0,
        action_system=types.SimpleNamespace(add_notification=lambda *a, **k: None),
    )
    game = types.SimpleNamespace(
        crafting=types.SimpleNamespace(get_recipe=lambda rid: recipe, cook=cook),
        inventory=types.SimpleNamespace(),  # _handle_craft_click reads game.inventory at :182 (before the crash site)
        building_system=None, food_registry=None, skill_manager=None,
        player=player,
        _fire_interaction=types.SimpleNamespace(check_nearby_campfire=check_nearby_campfire),
    )

    pd = PanelDispatcher.__new__(PanelDispatcher)
    pd._game = game

    # Drive the real dispatch entry point end-to-end.
    pd.dispatch(GameState.CRAFTING_PANEL, ("craft", "cook_chicken"))

    # After the fix: campfire check ran and cook was invoked.
    assert calls["campfire"] is True
    assert calls["cook"] is True


def test_dead_interact_methods_removed():
    # (b) method-level discriminator — unreachable code has no behavior to call.
    for name in DEAD:
        assert not hasattr(InteractSystem, name)


def test_handle_interact_still_works_after_deletion():
    node = types.SimpleNamespace(requires_tool=None)
    player = types.SimpleNamespace(
        action_system=mock.MagicMock(),
        # SimpleNamespace cannot gain attributes post-construction; pass the mock in.
        find_interactable_resource=mock.MagicMock(
            return_value=(node, 0, 0, 0.0, 0.0),
        ),
    )
    player.action_system.start_action.return_value = None
    game = types.SimpleNamespace(
        player=player, world=object(), inventory=object(),
        skill_manager=object(),
    )
    system = InteractSystem.__new__(InteractSystem)
    system._game = game

    system.handle_interact()

    # (a) behavioral: the real gather path still fires.
    player.find_interactable_resource.assert_called_once()
    player.action_system.start_action.assert_called_once_with(
        ActionType.WOODCUTTING, node, game.skill_manager, game.inventory,
    )
