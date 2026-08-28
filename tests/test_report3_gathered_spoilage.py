import pytest
from actions.action_system import ActionSystem
from actions.action_result import ActionResult
from actions.types import ActionType
from inventory.inventory import Inventory

# process_completion unconditionally calls skill_manager.add_xp_with_notification(...)
# AFTER the spoilage logic, so the mock MUST expose it (object() crashes with AttributeError).
class FakeSkillManager:
    def add_xp_with_notification(self, skill_id, xp, cb=None):
        pass

class FakeFood:
    def __init__(self):
        self._f = {
            "berries": type("F", (), {"spoilage_rate": 900.0})(),
            "water": type("F", (), {"spoilage_rate": 0.0})(),   # spoilage_seconds == 0
        }
    def get(self, item_id): return self._f.get(item_id)


def test_gathered_berry_gets_spoilage():
    sm = FakeSkillManager()
    sys = ActionSystem()
    inv = Inventory()
    assert inv.add_item("berries", 1)            # landing path
    result = ActionResult(success=True, item_id="berries", quantity=1, xp=10.0)
    sys.process_completion(result, inv, sm, food_registry=FakeFood())
    assert any(s.spoilage_remaining == 900.0 for s in inv.slots if s)
    # A non-food yield (oak_logs) must NOT get spoilage.
    inv2 = Inventory()
    result2 = ActionResult(success=True, item_id="oak_logs", quantity=3, xp=25.0)
    sys.process_completion(result2, inv2, sm, food_registry=FakeFood())
    assert all((s is None or s.spoilage_remaining is None) for s in inv2.slots if s)
    # food_registry=None (e.g. older callers) must not crash and sets no timer.
    inv3 = Inventory()
    result3 = ActionResult(success=True, item_id="berries", quantity=1, xp=10.0)
    sys.process_completion(result3, inv3, sm, None)
    assert all((s is None or s.spoilage_remaining is None) for s in inv3.slots if s)
    # A food with spoilage_seconds == 0 (water) must NOT get a timer (> 0 guard).
    inv_w = Inventory()
    result_w = ActionResult(success=True, item_id="water", quantity=1, xp=10.0)
    sys.process_completion(result_w, inv_w, sm, food_registry=FakeFood())
    assert all((s is None or s.spoilage_remaining is None) for s in inv_w.slots if s)
    # A full inventory lands nothing and sets NO spoilage (add_item -> False branch).
    inv_full = Inventory()
    inv_full.set_stack_size("oak_logs", 1)  # fill every slot (default stack 28 would only use 8)
    for _ in range(200):
        inv_full.add_item("oak_logs", 1)
    result_full = ActionResult(success=True, item_id="berries", quantity=5, xp=10.0)
    sys.process_completion(result_full, inv_full, sm, food_registry=FakeFood())
    assert all((s is None or s.spoilage_remaining is None) for s in inv_full.slots if s)