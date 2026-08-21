"""
Report 5 — Crafting & Inventory fixes.

Fix 1 surfaces malformed recipe JSON with a diagnostic log so a single typo in any
recipe source no longer produces zero recipes with no trace.
"""

from unittest import mock

from crafting.recipe_registry import RecipeRegistry


def test_malformed_recipe_json_logs_and_returns_zero(tmp_path):
    reg = RecipeRegistry()
    bad = tmp_path / "recipes.json"
    bad.write_text("{ this is not valid json ")

    with mock.patch("logging.exception") as exc:
        loaded = reg._load_from_dir(tmp_path, "recipes.json")

    # Buggy code path: swallowed → no recipe loaded.
    assert loaded == 0
    # Fixed: exactly one diagnostic is emitted for the offending file.
    exc.assert_called_once()
    # The diagnostic names the file for triage.
    joined = " ".join(str(a) for a in exc.call_args.args)
    assert "recipes.json" in joined


def test_valid_recipe_json_does_not_log(tmp_path):
    reg = RecipeRegistry()
    good = tmp_path / "recipes.json"
    good.write_text('{"recipes": []}')

    with mock.patch("logging.exception") as exc:
        loaded = reg._load_from_dir(tmp_path, "recipes.json")

    # Valid files stay quiet — the happy path must not emit diagnostics.
    assert loaded == 0
    exc.assert_not_called()
