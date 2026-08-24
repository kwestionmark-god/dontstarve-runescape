"""
test_b12_general_recipes.py — B12: data/recipes.json general-crafting table loads.

The unified RecipeRegistry.load_all() previously loaded a missing
data/recipes.json (silently contributing 0 recipes). These lock that the file
now exists, is parseable, and contributes general-crafting recipes that reach
CraftingSystem via the registry.
"""

import json

import pytest

from crafting.recipe_registry import RecipeRegistry


@pytest.fixture(scope="module")
def registry():
    reg = RecipeRegistry()
    reg.load_all()
    return reg


def test_data_recipes_file_exists_and_is_list():
    data = json.load(open("data/recipes.json"))
    assert isinstance(data.get("recipes"), list)
    assert len(data["recipes"]) >= 4


def test_registry_loads_general_recipes(registry):
    for recipe_id in ("sticks", "charcoal", "grass_rope", "paper"):
        assert registry.get_recipe(recipe_id) is not None


def test_charcoal_requires_campfire(registry):
    r = registry.get_recipe("charcoal")
    assert r.requires_campfire is True
    assert r.output_item == "charcoal"


def test_sticks_output_quantity(registry):
    r = registry.get_recipe("sticks")
    assert r.output_item == "stick"
    assert r.output_quantity == 3


def test_no_duplicate_recipe_ids_across_sources():
    """Every recipes.json must use unique ids; a collision would shadow one."""
    import glob

    seen = {}
    for path in glob.glob("**/recipes.json", recursive=True):
        if "__pycache__" in path:
            continue
        data = json.load(open(path))
        for entry in data.get("recipes", []):
            rid = entry.get("id") or entry.get("recipe_id")
            assert rid not in seen, f"duplicate recipe id {rid} in {path} and {seen[rid]}"
            seen[rid] = path


def test_registry_total_increases_with_data_file():
    """Loading the data table should contribute > 0 recipes now."""
    reg = RecipeRegistry()
    assert len(reg.recipes) == 0  # fresh registry, nothing loaded yet
    n = reg.load_all()
    assert n > 0
    assert len(reg.recipes) >= 4


def test_from_dict_legacy_and_canonical_envelopes_match():
    """The forward-looking canonical envelope loads to the same Recipe shape."""
    from inventory.recipe import Recipe

    legacy = Recipe.from_dict(
        {
            "id": "sticks",
            "name": "Break Sticks",
            "input_items": [["oak_logs", 1]],
            "output_item": "stick",
            "output_quantity": 3,
            "xp_reward": 3.0,
            "processing_chain": "wood_chain",
            "tier": 1,
        }
    )
    canonical = Recipe.from_dict(
        {
            "recipe_id": "sticks",
            "name": "Break Sticks",
            "input": [{"item_id": "oak_logs", "qty": 1}],
            "output": {"item_id": "stick", "qty": 3},
            "xp": 3.0,
            "processing_chain": "wood_chain",
            "tier": 1,
        }
    )
    assert legacy == canonical


def test_from_dict_accepts_dict_input_pairs():
    """Legacy input_items may use [{item_id, qty}] dicts, not just [id, qty] lists."""
    from inventory.recipe import Recipe

    r = Recipe.from_dict(
        {
            "id": "rope",
            "name": "Twist Rope",
            "input_items": [{"item_id": "fibers", "qty": 3}],
            "output_item": "grass_rope",
            "output_quantity": 1,
            "xp_reward": 4.0,
            "processing_chain": "foraging_chain",
            "tier": 1,
        }
    )
    assert r.input_items == [("fibers", 3)]


def test_existing_data_unchanged_after_normalization(registry):
    """Normalization is additive: shipped recipes.json still loads as before."""
    assert registry.get_recipe("sticks").output_quantity == 3
    assert registry.get_recipe("charcoal").requires_campfire is True
    assert registry.get_recipe("grass_rope").input_items == [("fibers", 3)]


# ── Canonical-envelope validation (B12 step 2) ────────────────────────

@pytest.fixture(scope="module")
def known_item_ids():
    """Item ids from data/items.json — the reference universe for inputs."""
    data = json.load(open("data/items.json"))
    items = data["items"] if isinstance(data, dict) else data
    ids = set()
    for it in items:
        for k in ("id", "item_id"):
            if isinstance(it.get(k), str):
                ids.add(it[k])
    return ids


def test_validator_accepts_canonical_envelope():
    """The canonical envelope (recipe_id/input_items/output_item/xp_reward) passes."""
    from inventory.recipe import validate_recipe_dict

    assert validate_recipe_dict(
        {
            "recipe_id": "sticks",
            "name": "Break Sticks",
            "input_items": [["oak_logs", 1]],
            "output_item": "stick",
            "output_quantity": 3,
            "xp_reward": 3.0,
            "processing_chain": "wood_chain",
            "tier": 1,
        }
    ) == []


def test_validator_tolerates_source_specific_keys():
    """Metallurgy smelt fields and construction multi-step keys are extra, ignored."""
    from inventory.recipe import validate_recipe_dict

    metallurgy = {
        "recipe_id": "smelt_iron",
        "name": "Smelt Iron",
        "input_items": [["iron_ore", 1], ["charcoal", 1]],
        "output_item": "smelted_iron_ingot",
        "output_quantity": 1,
        "xp_reward": 60.0,
        "processing_chain": "metallurgy_iron",
        "tier": 1,
        "requires_campfire": True,
        "ore_item": "iron_ore",
        "fuel_item": "charcoal",
        "extra_input": None,
        "extra_quantity": 0,
        "base_fuel_cost": 1,
        "requires_alloy_mastery": 0,
    }
    construction = {
        "recipe_id": "shape_elder_wood",
        "name": "Shape Elder Wood",
        "input_items": [["elder_wood", 2]],
        "output_item": "elder_wood_planks",
        "output_quantity": 2,
        "xp_reward": 50.0,
        "processing_chain": "legendary_wood_chain",
        "tier": 4,
        "skill_affects_yield": "crafting",
        "requires_structure": "crafting_station",
        "quality_eligible": True,
        "steps": [{"station": "crafting_station", "inputs": {}, "time": 15.0}],
        "skill_requirements": {"crafting": 40},
        "blueprint_id": "bp_shape_elder_wood",
        "enchantment_slots": 0,
    }
    assert validate_recipe_dict(metallurgy) == []
    assert validate_recipe_dict(construction) == []


def test_validator_rejects_missing_and_malformed():
    from inventory.recipe import validate_recipe_dict

    assert any("recipe_id" in e for e in validate_recipe_dict({"name": "X"}))
    assert any("input_items" in e for e in validate_recipe_dict(
        {"recipe_id": "x", "name": "X", "output_item": "b",
         "output_quantity": 1, "xp_reward": 1, "processing_chain": "c", "tier": 1}))
    assert any("input pair" in e for e in validate_recipe_dict(
        {"recipe_id": "x", "name": "X", "input_items": [["a"]],
         "output_item": "b", "output_quantity": 1, "xp_reward": 1,
         "processing_chain": "c", "tier": 1}))
    assert any("input dict" in e for e in validate_recipe_dict(
        {"recipe_id": "x", "name": "X", "input_items": [{"qty": 1}],
         "output_item": "b", "output_quantity": 1, "xp_reward": 1,
         "processing_chain": "c", "tier": 1}))
    assert any("output_quantity" in e for e in validate_recipe_dict(
        {"recipe_id": "x", "name": "X", "input_items": [["a", 1]],
         "output_item": "b", "output_quantity": 0, "xp_reward": 1,
         "processing_chain": "c", "tier": 1}))
    assert any("tier" in e for e in validate_recipe_dict(
        {"recipe_id": "x", "name": "X", "input_items": [["a", 1]],
         "output_item": "b", "output_quantity": 1, "xp_reward": 1,
         "processing_chain": "c", "tier": "high"}))


def test_registry_load_from_dir_skips_invalid(tmp_path):
    """_load_from_dir skips malformed entries but keeps the valid siblings."""
    from crafting.recipe_registry import RecipeRegistry

    (tmp_path / "recipes.json").write_text(json.dumps({
        "recipes": [
            {"recipe_id": "broken", "name": "Broken"},  # too few keys
            {
                "recipe_id": "sticks", "name": "Break Sticks",
                "input_items": [["oak_logs", 1]], "output_item": "stick",
                "output_quantity": 3, "xp_reward": 3.0,
                "processing_chain": "wood_chain", "tier": 1,
            },
        ]
    }))
    reg = RecipeRegistry()
    n = reg._load_from_dir(tmp_path, "recipes.json")
    assert n == 1
    assert reg.get_recipe("sticks") is not None
    assert reg.get_recipe("broken") is None


def test_all_input_references_resolve(known_item_ids):
    """Every consumed input item_id exists in items.json (output orphans allowed)."""
    import glob

    from inventory.recipe import collect_input_ids

    missing = {}
    for path in glob.glob("**/recipes.json", recursive=True):
        if "__pycache__" in path:
            continue
        data = json.load(open(path))
        for entry in data.get("recipes", []):
            for item_id in collect_input_ids(entry):
                if item_id not in known_item_ids:
                    missing.setdefault(item_id, path)
    assert missing == {}, f"unresolved input references: {missing}"
