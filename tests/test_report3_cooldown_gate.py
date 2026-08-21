from actions.action_system import ActionSystem
from actions.types import ActionType, ActionState

def make_completed_fail():
    s = ActionSystem()
    s.active.state = ActionState.IDLE
    s.active.cooldown = 2.0          # simulate a just-finished failed gather
    return s

def test_start_action_blocked_during_cooldown():
    s = make_completed_fail()
    err = s.start_action(ActionType.WOODCUTTING, None, object(), object())
    assert err is not None          # blocked during cooldown
    assert s.active.state == ActionState.IDLE  # not reset to RUNNING

def test_start_action_allowed_after_cooldown():
    s = make_completed_fail()
    s.update(2.1)                    # update() decrements cooldown while idle
    assert s.active.cooldown <= 0.0  # update() clamps state but leaves cooldown <= 0 (never resets to exactly 0)
    # With cooldown cleared, a fresh gather is no longer blocked by the cooldown guard.
    err = s.start_action(ActionType.WOODCUTTING, None, object(), object())
    assert err != "You must wait a moment before acting again."  # not a cooldown block

def test_success_is_never_blocked():          # Fix 2 core safety property
    s = ActionSystem()
    s.active.state = ActionState.IDLE
    s.active.cooldown = 0.0                    # after a SUCCESS, cooldown stays 0
    err = s.start_action(ActionType.WOODCUTTING, None, object(), object())
    assert err != "You must wait a moment before acting again."  # cooldown 0 -> not blocked

def test_full_lifecycle_block_then_allow():
    s = make_completed_fail()
    assert s.start_action(ActionType.WOODCUTTING, None, object(), object()) is not None  # blocked
    s.update(2.1)                              # penalty elapses
    err = s.start_action(ActionType.WOODCUTTING, None, object(), object())
    assert err != "You must wait a moment before acting again."  # allowed again
