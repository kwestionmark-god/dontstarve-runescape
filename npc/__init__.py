"""
npc/__init__.py — NPC package.

Exports the core NPC types and specialized NPC subclasses for use
by the NPC system and game.
"""

from npc.npc import NPC, NPCSpawnPoint
from npc.npc_types import (
    MerchantItem,
    MerchantNPC,
    QuestGiverNPC,
    FactionLeaderNPC,
    RecruitNPC,
    NPC_TYPE_MAP,
    create_npc_from_dict,
)
from npc.trade_system import (
    TradeSystem,
    TradeSession,
    TradeResult,
    BarterResult,
)
from npc.quest_system import (
    QuestSystem,
    QuestState,
    QuestDefinition,
    QuestProgress,
    QuestCondition,
    AcceptanceResult,
)
from npc.faction_system import (
    FactionSystem,
)
from npc.recruitment import (
    RecruitmentSystem,
)

__all__ = [
    "NPC",
    "NPCSpawnPoint",
    "MerchantItem",
    "MerchantNPC",
    "QuestGiverNPC",
    "FactionLeaderNPC",
    "RecruitNPC",
    "NPC_TYPE_MAP",
    "create_npc_from_dict",
    "TradeSystem",
    "TradeSession",
    "TradeResult",
    "BarterResult",
    "QuestSystem",
    "QuestState",
    "QuestDefinition",
    "QuestProgress",
    "QuestCondition",
    "AcceptanceResult",
    "FactionSystem",
    "RecruitmentSystem",
]
