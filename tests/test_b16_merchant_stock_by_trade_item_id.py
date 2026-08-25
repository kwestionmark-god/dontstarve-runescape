"""
test_b16_merchant_stock_by_trade_item_id.py — merchant stock restore matches on
trade_item_id, not array index.

The save system stored each merchant slot as ``{trade_item_id, stock_quantity}``
but restored by enumerating the live inventory by index, so a changed item order
sent stock to the wrong slots (data-integrity bug). Restore now matches on
``trade_item_id`` via ``SaveSystem._restore_merchant_stock``.
"""

from types import SimpleNamespace

import pytest

from core.save_system import SaveSystem
from npc.npc_types import MerchantNPC, MerchantItem


def _merchant_item(tid, stock):
    return MerchantItem(trade_item_id=tid, item_id=tid, buy_price=1, sell_price=1,
                        stock_quantity=0, max_stock=10)


def _merchant(items):
    return MerchantNPC(npc_id="merchant_1", name="Shop", inventory=list(items))


def test_restore_matches_by_trade_item_id_not_index():
    # Live inventory order is [a, b, c]; saved order is the shuffle [c, a, b].
    merchant = _merchant([
        _merchant_item("a", 0),
        _merchant_item("b", 0),
        _merchant_item("c", 0),
    ])
    saved = [
        {"trade_item_id": "c", "stock_quantity": 12},
        {"trade_item_id": "a", "stock_quantity": 7},
        {"trade_item_id": "b", "stock_quantity": 40},
    ]
    SaveSystem._restore_merchant_stock(merchant, saved)

    # trade_item_id map: a->7, b->40, c->12
    id_map = {a.trade_item_id: a.stock_quantity for a in merchant.inventory}
    assert id_map == {"a": 7, "b": 40, "c": 12}

    # Discriminator: a naive index map would have produced a different result.
    live_order = [a.trade_item_id for a in merchant.inventory]
    naive_map = {live_order[i]: saved[i]["stock_quantity"] for i in range(len(saved))}
    assert naive_map != id_map


def test_restore_ignores_saved_item_missing_from_live_inventory():
    merchant = _merchant([_merchant_item("a", 0), _merchant_item("b", 0)])
    saved = [
        {"trade_item_id": "a", "stock_quantity": 5},
        {"trade_item_id": "ghost", "stock_quantity": 99},  # not in live inventory
    ]
    # No exception; existing slots restored, unknown item skipped.
    SaveSystem._restore_merchant_stock(merchant, saved)
    id_map = {a.trade_item_id: a.stock_quantity for a in merchant.inventory}
    assert id_map == {"a": 5, "b": 0}


def test_build_snapshot_emits_trade_item_id():
    merchant = _merchant([
        _merchant_item("a", 5),
        _merchant_item("b", 3),
    ])
    game = SimpleNamespace(
        seed=42, death_count=0, player=None, inventory=None, skill_manager=None,
        survival=None, building_system=None, firemaking=None, faction_system=None,
        npc_system=SimpleNamespace(npcs=[merchant], _patrol_targets={}),
        quest_system=None, recruitment_system=None,
    )
    snap = SaveSystem()._build_snapshot(game)
    entries = snap["merchant_economy"]
    assert len(entries) == 1
    ids = {e["trade_item_id"] for e in entries[0]["inventory"]}
    assert ids == {"a", "b"}
