"""
interactions/ — Player interaction flows (fire, NPC, resource).

Extracted from core.game.Game in Phase 3.5.6.
"""

from interactions.fire import FireInteraction
from interactions.interact import InteractSystem
from interactions.npc_flows import NPCFlows

__all__ = ["FireInteraction", "InteractSystem", "NPCFlows"]
