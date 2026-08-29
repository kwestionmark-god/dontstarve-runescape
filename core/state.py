"""
state.py — Game state machine.

Manages discrete game states. Only one active at a time.
"""

from enum import Enum, auto


class GameState(Enum):
    """Discrete game states. Only one is active at any moment."""

    TITLE = "title"
    """Title screen UI. Game entry state."""

    LOADING = "loading"
    """Procedural world generation in progress. Loading screen rendered."""

    LOADING_SAVE = "loading_save"
    """Save file loading in progress. Shows 'Loading save...' message."""

    PLAYING = "playing"
    """Main gameplay loop running. World rendered, systems update."""

    INVENTORY_OPEN = "inventory"
    """Inventory panel is open. Update logic frozen (except hunger drain)."""

    SKILL_PANEL = "skill_panel"
    """Skill panel is open. Update logic frozen (except hunger drain)."""

    CRAFTING_PANEL = "crafting"
    """Crafting panel is open. Update logic frozen (except hunger drain)."""

    BUILDING_PANEL = "building"
    """Building placement panel is open. Update logic frozen (except hunger drain)."""

    GEAR_PANEL = "gear"
    """Gear management panel is open. Update logic frozen (except hunger drain)."""

    TRADE_PANEL = "trade"
    """Trade panel is open. Player is interacting with a merchant NPC."""

    QUEST_PANEL = "quest_panel"
    """Quest panel is open. Update logic frozen (except hunger drain)."""

    RECRUIT_PANEL = "recruit_panel"
    """Recruit panel is open. Player is recruiting an NPC."""

    DIPLOMACY_PANEL = "diplomacy_panel"
    """Diplomacy panel is open. Player is interacting with a faction leader."""

    ERROR = "error"
    """World generation or save load failed. Shows error message."""


# PANEL_STATES — all panel-open states where update logic is frozen
PANEL_STATES = (
    GameState.INVENTORY_OPEN, GameState.SKILL_PANEL, GameState.CRAFTING_PANEL,
    GameState.BUILDING_PANEL, GameState.GEAR_PANEL, GameState.TRADE_PANEL,
    GameState.QUEST_PANEL, GameState.RECRUIT_PANEL, GameState.DIPLOMACY_PANEL,
)
