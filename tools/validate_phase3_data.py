"""Validate Phase 3 data files for cross-reference integrity."""
import json
import sys
import os


def load_json(path):
    with open(path) as f:
        return json.load(f)


def main():
    errors = []
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load all files
    items = load_json(os.path.join(base_dir, "data", "items.json"))
    biomes = load_json(os.path.join(base_dir, "data", "biomes.json"))
    factions = load_json(os.path.join(base_dir, "data", "factions.json"))
    npcs = load_json(os.path.join(base_dir, "data", "npcs.json"))
    quests = load_json(os.path.join(base_dir, "data", "quests.json"))
    trade_items = load_json(os.path.join(base_dir, "data", "trade_items.json"))

    # Build lookup sets
    item_ids = {item["id"] for item in items["items"]}
    biome_ids = {b["id"] for b in biomes["biomes"]}
    faction_ids = {f["faction_id"] for f in factions["factions"]}
    faction_leader_ids = {f["leader_npc_id"] for f in factions["factions"]}
    npc_ids = {n["npc_id"] for n in npcs["npcs"]}
    quest_ids = {q["quest_id"] for q in quests["quests"]}
    spawn_point_coords = set()
    for sp in npcs["spawn_points"]:
        if "tile_x" in sp and "tile_y" in sp:
            spawn_point_coords.add((sp["tile_x"], sp["tile_y"]))
        else:
            if "tile_x" not in sp:
                errors.append(f"spawn_point {sp.get('spawn_id', '?')}: missing 'tile_x' field")
            if "tile_y" not in sp:
                errors.append(f"spawn_point {sp.get('spawn_id', '?')}: missing 'tile_y' field")

    print("=== Loaded files successfully ===")
    print(f"  items: {len(items['items'])} items")
    print(f"  biomes: {len(biomes['biomes'])} biomes")
    print(f"  factions: {len(factions['factions'])} factions")
    print(f"  npcs: {len(npcs['npcs'])} NPCs, {len(npcs['spawn_points'])} spawn points")
    print(f"  quests: {len(quests['quests'])} quests")
    print(f"  trade_items: {len(trade_items['trade_items'])} trade items")
    print()

    # Validate factions
    print("--- Validating factions ---")
    for f in factions["factions"]:
        # Leader must exist as npc_id with npc_type "faction_leader"
        if f["leader_npc_id"] not in npc_ids:
            errors.append(f"faction {f['faction_id']} leader {f['leader_npc_id']} not in npcs.json")
        for biome in f["territory_biomes"]:
            if biome not in biome_ids:
                errors.append(f"faction {f['faction_id']} has unknown biome {biome}")
        for monster in f["hostile_monster_types"]:
            pass  # Would need monsters.json loaded too
    print(f"  Checked {len(factions['factions'])} factions")

    # Validate npcs
    print("--- Validating NPCs ---")
    for n in npcs["npcs"]:
        # health <= max_health (P3-I05)
        if n.get("health", 0) > n.get("max_health", 0):
            errors.append(f"npc {n['npc_id']}: health {n['health']} > max_health {n.get('max_health')}")
        # Both health and max_health must exist (P3-I05)
        if "health" not in n:
            errors.append(f"npc {n['npc_id']}: missing 'health' field (P3-I05)")
        if "max_health" not in n:
            errors.append(f"npc {n['npc_id']}: missing 'max_health' field (P3-I05)")
        # faction references faction_ids (or is None)
        if "faction" not in n:
            errors.append(f"npc {n['npc_id']}: missing 'faction' field")
        else:
            if n["faction"] is not None and n["faction"] not in faction_ids:
                errors.append(f"npc {n['npc_id']}: faction {n['faction']} not in factions.json")
        # npc_type must be valid enum
        valid_types = {"merchant", "quest_giver", "faction_leader", "recruit"}
        if n["npc_type"] not in valid_types:
            errors.append(f"npc {n['npc_id']}: invalid type {n['npc_type']}")
        # spawn point coords must match a spawn_point
        coords = (n["world_x"], n["world_y"])
        if coords not in spawn_point_coords:
            errors.append(f"npc {n['npc_id']} at {coords} not in any spawn_point")
        # quest_giver available_quest_ids must exist
        if n["npc_type"] == "quest_giver":
            for qid in n.get("available_quest_ids", []):
                if qid not in quest_ids:
                    errors.append(f"npc {n['npc_id']}: quest {qid} not in quests.json")
    print(f"  Checked {len(npcs['npcs'])} NPCs")

    # Validate quests
    print("--- Validating quests ---")
    valid_condition_types = {
        "kill_monster", "collect_item", "craft_item", "visit_location",
        "reach_level", "negotiate_faction", "combat_faction",
        "deliver_item", "trade_at_location"
    }
    for q in quests["quests"]:
        # giver_npc_type must not be "merchant" (P3-I04)
        if q["giver_npc_type"] == "merchant":
            errors.append(f"quest {q['quest_id']}: giver_npc_type is 'merchant' (P3-I04)")
        # skill_xp_rewards must use "intelligence", not "trade" (P3-I02)
        for skill_key in q.get("skill_xp_rewards", {}):
            if skill_key == "trade":
                errors.append(f"quest {q['quest_id']}: skill_xp_rewards has 'trade' instead of 'intelligence' (P3-I02)")
        # condition types must be valid (P3-I01)
        for cond in q["conditions"]:
            if cond["condition_type"] not in valid_condition_types:
                errors.append(f"quest {q['quest_id']}: unknown condition_type {cond['condition_type']} (P3-I01)")
        for cond in q.get("fail_conditions", []):
            if cond["condition_type"] not in valid_condition_types:
                errors.append(f"quest {q['quest_id']}: fail_condition unknown type {cond['condition_type']} (P3-I01)")
        # prerequisites must reference quests.json
        for prereq in q.get("prerequisite_quests", []):
            if prereq not in quest_ids:
                errors.append(f"quest {q['quest_id']}: prerequisite {prereq} not in quests.json")
        # item rewards must reference items.json
        for item_reward in q.get("item_rewards", []):
            if isinstance(item_reward, list) and len(item_reward) >= 1:
                item_id = item_reward[0]
                if item_id not in item_ids:
                    errors.append(f"quest {q['quest_id']}: item reward {item_id} not in items.json")
        # faction references must be valid
        if q.get("giver_faction") and q["giver_faction"] not in faction_ids:
            errors.append(f"quest {q['quest_id']}: giver_faction {q['giver_faction']} not in factions.json")
    print(f"  Checked {len(quests['quests'])} quests")

    # Track which condition types are used
    used_condition_types = set()
    for q in quests["quests"]:
        for cond in q["conditions"]:
            used_condition_types.add(cond["condition_type"])
        for cond in q.get("fail_conditions", []):
            used_condition_types.add(cond["condition_type"])
    print(f"  Condition types used: {sorted(used_condition_types)}")
    missing_types = valid_condition_types - used_condition_types
    if missing_types:
        print(f"  NOTE: Condition types NOT used: {sorted(missing_types)}")

    # Validate trade items
    print("--- Validating trade items ---")
    for ti in trade_items["trade_items"]:
        if ti["item_id"] not in item_ids:
            errors.append(f"trade_item {ti['trade_item_id']}: item_id {ti['item_id']} not in items.json")
        if ti["biome"] not in biome_ids:
            errors.append(f"trade_item {ti['trade_item_id']}: biome {ti['biome']} not in biomes.json")
        if ti["buy_price"] <= ti["sell_price"]:
            errors.append(f"trade_item {ti['trade_item_id']}: buy_price {ti['buy_price']} <= sell_price {ti['sell_price']}")
        if ti["stock_quantity"] > ti["max_stock"]:
            errors.append(f"trade_item {ti['trade_item_id']}: stock > max_stock")
        if ti["is_premium"] and ti["commerce_requirement"] == 0:
            errors.append(f"trade_item {ti['trade_item_id']}: premium but commerce_requirement = 0")
    print(f"  Checked {len(trade_items['trade_items'])} trade items")

    # Validate spawn points
    print("--- Validating spawn points ---")
    valid_biomes = {"forest", "plains", "coastal", "swamp", "mountains", "desert"}
    valid_types = {"merchant", "quest_giver", "faction_leader", "recruit"}
    for sp in npcs["spawn_points"]:
        if sp["biome"] not in valid_biomes:
            errors.append(f"spawn_point {sp['spawn_id']}: invalid biome {sp['biome']}")
        for ntype in sp["npc_types"]:
            if ntype not in valid_types:
                errors.append(f"spawn_point {sp['spawn_id']}: invalid npc_type {ntype}")
    print(f"  Checked {len(npcs['spawn_points'])} spawn points")

    # Report
    print()
    if errors:
        print(f"FAILED: {len(errors)} errors found:")
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("All Phase 3 data files validated successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
