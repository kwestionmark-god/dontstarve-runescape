"""
npc_renderer.py — NPC seasonal variant selection.

Maps NPC + season → sprite key / clothing variant.
Render path only; NPC logic stays in npc/ package.
"""

from __future__ import annotations
from typing import Any

# Default NPC seasonal clothing mappings
DEFAULT_NPC_SEASONAL_VARIANTS: dict[str, dict[str, str]] = {
    "merchant": {
        "spring": "merchant_spring",
        "summer": "merchant_summer",
        "autumn": "merchant_autumn",
        "winter": "merchant_winter",
    },
    "quest_giver": {
        "spring": "quest_giver_spring",
        "summer": "quest_giver_summer",
        "autumn": "quest_giver_autumn",
        "winter": "quest_giver_winter",
    },
    "faction_leader": {
        "spring": "faction_leader_spring",
        "summer": "faction_leader_summer",
        "autumn": "faction_leader_autumn",
        "winter": "faction_leader_winter",
    },
    "recruit": {
        "spring": "recruit_spring",
        "summer": "recruit_summer",
        "autumn": "recruit_autumn",
        "winter": "recruit_winter",
    },
}


class NPCRenderer:
    """Selects seasonal sprite keys for NPCs before rendering."""

    def __init__(self, variants: dict[str, dict[str, str]] | None = None) -> None:
        self.variants = variants or DEFAULT_NPC_SEASONAL_VARIANTS

    def get_sprite_key(self, npc_type: str, season: str) -> str:
        """Return the seasonal sprite key for an NPC type."""
        season_map = self.variants.get(npc_type, {})
        return season_map.get(season, npc_type)

    def get_seasonal_color_tint(self, npc_type: str, season: str) -> tuple[int, int, int] | None:
        """Return an optional color tint for seasonal clothing."""
        tints: dict[str, dict[str, tuple[int, int, int]]] = {
            "merchant": {
                "winter": (200, 200, 220),
                "summer": (255, 220, 150),
            },
            "recruit": {
                "winter": (180, 200, 210),
            },
        }
        season_tints = tints.get(npc_type, {})
        return season_tints.get(season, None)
