"""
recipe.py — Recipe data structure.

Defines individual crafting recipes with inputs, outputs, requirements,
and XP rewards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Tuple


def _normalize_inputs(source):
    """
    Accept either the legacy ``input_items`` shape ([[item_id, qty], ...]) or
    the forward-looking ``input`` shape ([{"item_id": ..., "qty": ...}, ...]).

    Returns a list of ``(item_id, qty)`` tuples. ``None`` yields an empty list.
    """
    if source is None:
        return []
    normalized = []
    for entry in source:
        if isinstance(entry, dict):
            item_id = entry.get("item_id") or entry.get("item") or entry.get("id")
            qty = entry.get("qty")
            if qty is None:
                qty = entry.get("quantity")
            normalized.append((item_id, qty))
        else:
            normalized.append(tuple(entry))
    return normalized


def _normalize_output(output_item, output_quantity, output):
    """
    Accept the legacy ``output_item``/``output_quantity`` pair or the
    forward-looking ``output`` dict ({item_id, qty}). Returns ``(item_id, qty)``.
    """
    if output is not None:
        item_id = output.get("item_id") or output.get("item") or output.get("id")
        qty = output.get("qty")
        if qty is None:
            qty = output.get("quantity")
        return item_id, qty
    return output_item, output_quantity


# Canonical envelope: the keys every recipe source must provide. Extra keys
# (metallurgy ore/fuel, construction steps/blueprint/…) are tolerated by both
# from_dict and validate_recipe_dict — the unified registry consumes only the
# canonical fields.
CANONICAL_RECIPE_KEYS = (
    "recipe_id",
    "name",
    "input_items",
    "output_item",
    "output_quantity",
    "xp_reward",
    "processing_chain",
    "tier",
)


def collect_input_ids(entry):
    """Return the set of item_ids referenced as inputs in a raw recipe dict."""
    ids = set()
    for pair in entry.get("input_items", []) or []:
        if isinstance(pair, dict):
            item_id = pair.get("item_id") or pair.get("item") or pair.get("id")
            if item_id:
                ids.add(item_id)
        elif isinstance(pair, (list, tuple)) and pair:
            ids.add(pair[0])
    return ids


def validate_recipe_dict(entry):
    """
    Validate a single raw recipe entry against the canonical envelope.

    Tolerates extra source-specific keys but requires every canonical key to be
    present with a compatible type. Returns a list of human-readable error
    strings (empty when the entry is valid).
    """
    errors = []
    if not isinstance(entry, dict):
        return ["entry is not a dict"]

    for key in CANONICAL_RECIPE_KEYS:
        if key not in entry:
            errors.append(f"missing required key '{key}'")

    recipe_id = entry.get("recipe_id", entry.get("id"))
    if not isinstance(recipe_id, str) or not recipe_id:
        errors.append("recipe_id must be a non-empty string")
    if not isinstance(entry.get("name"), str):
        errors.append("name must be a string")

    inputs = entry.get("input_items")
    if not isinstance(inputs, list) or not inputs:
        errors.append("input_items must be a non-empty list")
    else:
        for pair in inputs:
            if isinstance(pair, dict):
                if not (pair.get("item_id") or pair.get("item") or pair.get("id")):
                    errors.append("input dict item missing item_id")
            elif isinstance(pair, (list, tuple)):
                if (
                    len(pair) < 2
                    or not isinstance(pair[0], str)
                    or not isinstance(pair[1], (int, float))
                ):
                    errors.append("input pair must be [item_id, qty]")
            else:
                errors.append("input pair must be [item_id, qty] or {item_id, qty}")

    if not isinstance(entry.get("output_item"), str):
        errors.append("output_item must be a string")
    output_quantity = entry.get("output_quantity")
    if not isinstance(output_quantity, (int, float)) or output_quantity <= 0:
        errors.append("output_quantity must be a positive number")
    if not isinstance(entry.get("xp_reward"), (int, float)):
        errors.append("xp_reward must be a number")
    if not isinstance(entry.get("processing_chain"), str):
        errors.append("processing_chain must be a string")
    if not isinstance(entry.get("tier"), int):
        errors.append("tier must be an int")

    return errors


@dataclass
class Recipe:
    """
    A single crafting recipe.

    Fields:
        recipe_id: unique identifier (e.g. "planks", "charcoal")
        name: human-readable name (e.g. "Craft Planks")
        input_items: list of (item_id, quantity) pairs
        output_item: single output item_id
        output_quantity: quantity produced
        requires_campfire: whether a campfire structure is needed
        requires_structure: structure_id required to craft this recipe
        xp_reward: XP granted on successful craft
        processing_chain: chain identifier (wood_chain, stone_chain, etc.)
        tier: 1–4
        skill_affects_yield: skill name that can boost output (or None)
        is_food: whether the output is a food item
    """

    recipe_id: str
    name: str
    input_items: List[Tuple[str, int]]
    output_item: str
    output_quantity: int
    requires_campfire: bool
    xp_reward: float
    processing_chain: str
    tier: int
    requires_structure: str = ""
    skill_affects_yield: str | None = None
    is_food: bool = False
    quest_unlock: str | None = None
    # Metallurgy-only fields; ignored by every other recipe type (defaults apply).
    base_fuel_cost: int = 1
    requires_alloy_mastery: int = 0

    @staticmethod
    def from_dict(data: dict) -> "Recipe":
        """
        Create a Recipe from JSON data.

        Accepts both the legacy envelope (``id`` / ``input_items`` /
        ``output_item`` / ``output_quantity`` / ``xp_reward``) and the
        forward-looking canonical envelope (``recipe_id`` / ``input`` /
        ``output`` / ``xp``) so fragmented source files load consistently
        through one conversion point — the shape a future unified registry can
        consume directly. Unknown/forward-only keys (``skill``, ``season``) are
        tolerated and ignored for now.

        Args:
            data: Parsed dict from recipes.json.

        Returns:
            A Recipe instance.
        """
        # Determine if output is food by checking items.json
        output_is_food = data.get("is_food", False)

        recipe_id = data["id"] if "id" in data else data["recipe_id"]
        input_items = _normalize_inputs(data.get("input_items", data.get("input")))
        output_item, output_quantity = _normalize_output(
            data.get("output_item"), data.get("output_quantity"), data.get("output"),
        )
        xp_reward = data.get("xp_reward", data.get("xp"))

        return Recipe(
            recipe_id=recipe_id,
            name=data["name"],
            input_items=input_items,
            output_item=output_item,
            output_quantity=output_quantity,
            requires_campfire=data.get("requires_campfire", False),
            requires_structure=data.get("requires_structure", ""),
            xp_reward=xp_reward,
            processing_chain=data["processing_chain"],
            tier=data.get("tier", 1),
            skill_affects_yield=data.get("skill_affects_yield"),
            is_food=output_is_food,
            quest_unlock=data.get("quest_unlock"),
            base_fuel_cost=data.get("base_fuel_cost", 1),
            requires_alloy_mastery=data.get("requires_alloy_mastery", 0),
        )
