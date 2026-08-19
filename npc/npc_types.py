"""
npc/npc_types.py — NPC subtype definitions.

Defines specialized NPC types:
- MerchantItem / MerchantNPC: Trade and commerce NPCs.
- QuestGiverNPC: NPCs that offer quests.
- FactionLeaderNPC: Faction leaders with faction management.
- RecruitNPC: NPCs that can be recruited by the player.

Factory functions and type maps enable polymorphic NPC creation from
JSON data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from npc.npc import NPC

if TYPE_CHECKING:
    from skills.intelligence.intelligence import EligibilityResult


@dataclass
class MerchantItem:
    """An item that a merchant NPC can buy and sell."""

    trade_item_id: str
    item_id: str
    buy_price: int
    sell_price: int
    stock_quantity: int
    max_stock: int
    tier: int = 1
    is_premium: bool = False
    commerce_requirement: int = 0
    biome: str = ""


@dataclass
class MerchantNPC(NPC):
    """
    Merchant NPC that buys and sells items from an inventory.

    Fields:
        npc_type: Always "merchant".
        inventory: List of MerchantItem objects the merchant holds.
        inventory_capacity: Maximum number of different MerchantItems.
        restock_timer: Cooldown for the restock interval (in seconds).
        restock_interval: How often (in seconds) to restock items.
        gold: The gold reserves held by the merchant.
        price_modifier: Multiplier applied to buy/sell prices.
        commerce_requirement: Minimum commerce stat to trade with this merchant.
    """

    npc_type: str = "merchant"
    inventory: List[MerchantItem] = field(default_factory=list)
    inventory_capacity: int = 10
    restock_timer: float = 0.0
    restock_interval: float = 60.0
    gold: int = 0
    price_modifier: float = 1.0
    commerce_requirement: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MerchantNPC":
        """
        Create a MerchantNPC from a JSON dict (from npcs.json).

        Extracts base fields via NPC.from_dict, then type-specific fields.

        Args:
            data: Parsed JSON dict from npcs.json "npcs" array.

        Returns:
            Fully initialized MerchantNPC instance.
        """
        npc = NPC.from_dict(data)
        return cls(
            npc_id=npc.npc_id,
            name=npc.name,
            npc_type=npc.npc_type,
            world_x=npc.world_x,
            world_y=npc.world_y,
            sprite_key=npc.sprite_key,
            faction=npc.faction,
            dialogue_lines=npc.dialogue_lines,
            behavior=npc.behavior,
            patrol_area=npc.patrol_area,
            is_active=npc.is_active,
            is_recruited=npc.is_recruited,
            recruit_behavior=npc.recruit_behavior,
            hostility_level=npc.hostility_level,
            health=npc.health,
            max_health=npc.max_health,
            inventory=[],  # stub — P3-S14 will populate from trade_items.json
            inventory_capacity=data.get("inventory_tier", 10),
            restock_timer=0.0,
            restock_interval=data.get("restock_interval", 60.0),
            gold=data.get("starting_gold", 0),
            price_modifier=data.get("price_modifier", 1.0),
            commerce_requirement=data.get("commerce_requirement", 0),
        )

    def get_trade_items(self) -> List[MerchantItem]:
        """Return a safe copy of the merchant's trade items."""
        return list(self.inventory)

    def on_player_approach(self, player: Any) -> None:
        """Handle the event of a player approaching the merchant.

        Checks proximity and adds a notification if the player is close enough.

        Args:
            player: The player entity.
        """
        from npc.trade_system import TradeSystem

        if hasattr(player, "action_system") and player.action_system is not None:
            distance = player.distance_to(self.world_x, self.world_y)
            if distance <= TradeSystem.PROXIMITY_THRESHOLD:
                player.action_system.add_notification(
                    f"Press E to trade with {self.name}.",
                    (255, 255, 100),
                )

    def on_interact(self, player: Any) -> None:
        """Handle the event of a player interacting with the merchant.

        Placeholder — P3-S7 will connect to UI trade panels.

        Args:
            player: The player entity.
        """
        pass  # stub - P3-S7 will connect to UI trade panels


@dataclass
class QuestGiverNPC(NPC):
    """
    NPC that offers quests to the player.

    Fields:
        npc_type: Always "quest_giver".
        available_quests: List of quest IDs currently available from this NPC.
        completed_quests: List of quest IDs the player has completed via this NPC.
        dialogue_override: Custom dialogue lines keyed by dialogue option.
    """

    npc_type: str = "quest_giver"
    available_quests: List[str] = field(default_factory=list)
    completed_quests: List[str] = field(default_factory=list)
    dialogue_override: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuestGiverNPC":
        """
        Create a QuestGiverNPC from a JSON dict (from npcs.json).

        Args:
            data: Parsed JSON dict from npcs.json "npcs" array.

        Returns:
            Fully initialized QuestGiverNPC instance.
        """
        npc = NPC.from_dict(data)
        return cls(
            npc_id=npc.npc_id,
            name=npc.name,
            npc_type=npc.npc_type,
            world_x=npc.world_x,
            world_y=npc.world_y,
            sprite_key=npc.sprite_key,
            faction=npc.faction,
            dialogue_lines=npc.dialogue_lines,
            behavior=npc.behavior,
            patrol_area=npc.patrol_area,
            is_active=npc.is_active,
            is_recruited=npc.is_recruited,
            recruit_behavior=npc.recruit_behavior,
            hostility_level=npc.hostility_level,
            health=npc.health,
            max_health=npc.max_health,
            available_quests=data.get("available_quest_ids", []),
            completed_quests=[],
            dialogue_override={},
        )

    def get_available_quests(self, player: Any) -> List[str]:
        """Return a safe copy of available quests."""
        return list(self.available_quests)

    def check_quest_eligibility(self, player: Any, quest_id: str) -> bool:
        """
        Check if the player is eligible for a quest via the quest system.

        Args:
            player: The player entity.
            quest_id: The quest ID to check.

        Returns:
            True if the quest is available and the player has an action system.
        """
        if not self._is_local_quest(quest_id):
            return False
        if not hasattr(player, "action_system") or player.action_system is None:
            return False
        return True

    def on_player_approach(self, player: Any) -> None:
        """Handle the event of a player approaching the quest giver.

        Shows a proximity notification when the player is within interaction range.
        Mirrors MerchantNPC.on_player_approach() pattern.
        """
        from npc.trade_system import TradeSystem

        if hasattr(player, "action_system") and player.action_system is not None:
            distance = player.distance_to(self.world_x, self.world_y)
            if distance <= TradeSystem.PROXIMITY_THRESHOLD:
                player.action_system.add_notification(
                    f"Press E to talk to {self.name}.",
                    (100, 140, 200),  # Blue tint to differentiate from merchant (yellow)
                )

    def on_interact(self, player: Any) -> None:
        """Handle interaction — panel opened by Game layer, not here."""
        pass

    def _is_local_quest(self, quest_id: str) -> bool:
        """Check if a quest is offered by this NPC."""
        return quest_id in self.available_quests

@dataclass
class FactionLeaderNPC(NPC):
    """
    Leader of a faction, with faction management capabilities.

    Fields:
        npc_type: Always "faction_leader".
        faction_id: The faction this NPC leads.
        faction_strength: Relative strength of the faction (0.0–1.0+).
        faction_members: NPCs that are members of this faction.
        negotiation_success_rate: Base rate for successful negotiations.
        hostile_monster_types: Monster types hostile to this faction.
    """

    npc_type: str = "faction_leader"
    faction_id: str = ""
    faction_strength: float = 1.0
    faction_members: List[NPC] = field(default_factory=list)
    negotiation_success_rate: float = 0.5
    hostile_monster_types: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FactionLeaderNPC":
        """
        Create a FactionLeaderNPC from a JSON dict (from npcs.json).

        Args:
            data: Parsed JSON dict from npcs.json "npcs" array.

        Returns:
            Fully initialized FactionLeaderNPC instance.
        """
        npc = NPC.from_dict(data)
        return cls(
            npc_id=npc.npc_id,
            name=npc.name,
            npc_type=npc.npc_type,
            world_x=npc.world_x,
            world_y=npc.world_y,
            sprite_key=npc.sprite_key,
            faction=npc.faction,
            dialogue_lines=npc.dialogue_lines,
            behavior=npc.behavior,
            patrol_area=npc.patrol_area,
            is_active=npc.is_active,
            is_recruited=npc.is_recruited,
            recruit_behavior=npc.recruit_behavior,
            hostility_level=npc.hostility_level,
            health=npc.health,
            max_health=npc.max_health,
            faction_id=data.get("faction_id", ""),
            faction_strength=data.get("faction_strength", 1.0),
            faction_members=[],
            negotiation_success_rate=1.0 - data.get("hostility_level", 0.5),
            hostile_monster_types=data.get("hostile_monster_types", []),
        )

    def get_faction_info(self, player: Any) -> Dict[str, Any]:
        """
        Return faction information for the player.

        Args:
            player: The player entity.

        Returns:
            Dict with faction_id, faction_strength, and hostile_monster_types.
        """
        return {
            "faction_id": self.faction_id,
            "faction_strength": self.faction_strength,
            "hostile_monster_types": list(self.hostile_monster_types),
        }

    def on_player_approach(self, player: Any) -> None:
        """Show proximity notification for faction leader."""
        from npc.trade_system import TradeSystem
        if hasattr(player, "action_system") and player.action_system is not None:
            distance = player.distance_to(self.world_x, self.world_y)
            if distance <= TradeSystem.PROXIMITY_THRESHOLD:
                player.action_system.add_notification(
                    f"Press E to speak with {self.name}.",
                    (200, 100, 100),  # Red tint to match faction leader
                )

    def on_interact(self, player: Any) -> None:
        """Handle interaction — panel opened by Game layer, not here."""
        pass  # Panel opening handled by Game._open_diplomacy_panel


@dataclass
class RecruitNPC(NPC):
    """
    NPC that can be recruited by the player.

    Fields:
        npc_type: Always "recruit".
        recruit_commerce_requirement: Commerce stat needed to recruit.
        recruit_persuasion_requirement: Persuasion stat needed to recruit.
        recruit_composite_stat: Combined stat requirement.
        available_behaviors: List of behaviors this recruit can perform.
        recruit_sprite_key: Optional alternate sprite for the recruited state.
    """

    npc_type: str = "recruit"
    recruit_commerce_requirement: int = 0
    recruit_persuasion_requirement: int = 0
    recruit_composite_stat: int = 0
    available_behaviors: List[str] = field(default_factory=list)
    recruit_sprite_key: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecruitNPC":
        """
        Create a RecruitNPC from a JSON dict (from npcs.json).

        Args:
            data: Parsed JSON dict from npcs.json "npcs" array.

        Returns:
            Fully initialized RecruitNPC instance.
        """
        npc = NPC.from_dict(data)
        return cls(
            npc_id=npc.npc_id,
            name=npc.name,
            npc_type=npc.npc_type,
            world_x=npc.world_x,
            world_y=npc.world_y,
            sprite_key=npc.sprite_key,
            faction=npc.faction,
            dialogue_lines=npc.dialogue_lines,
            behavior=npc.behavior,
            patrol_area=npc.patrol_area,
            is_active=npc.is_active,
            is_recruited=npc.is_recruited,
            recruit_behavior=npc.recruit_behavior,
            hostility_level=npc.hostility_level,
            health=npc.health,
            max_health=npc.max_health,
            recruit_commerce_requirement=data.get("recruit_commerce_requirement", 0),
            recruit_persuasion_requirement=data.get("recruit_persuasion_requirement", 0),
            recruit_composite_stat=data.get("recruit_composite_stat", 0),
            available_behaviors=data.get("available_behaviors", []),
            recruit_sprite_key=data.get("recruit_sprite_key", ""),
        )

    def is_recruitment_eligible(self, player: Any) -> EligibilityResult:
        """
        Check if the player is eligible to recruit this NPC.

        Args:
            player: The player entity.

        Returns:
            EligibilityResult indicating eligibility status.
        """
        from skills.intelligence.intelligence import IntelligenceSkill
        if not hasattr(player, "action_system") or player.action_system is None:
            from skills.intelligence.intelligence import EligibilityResult
            return EligibilityResult(
                eligible=False, commerce_ok=False, persuasion_ok=False,
                slot_available=False, composite_ok=False,
                message="No action system available."
            )
        action_system = player.action_system
        if not hasattr(action_system, "skill_manager") or action_system.skill_manager is None:
            from skills.intelligence.intelligence import EligibilityResult
            return EligibilityResult(
                eligible=False, commerce_ok=False, persuasion_ok=False,
                slot_available=False, composite_ok=False,
                message="Skill manager not available."
            )
        skill_manager = action_system.skill_manager
        intelligence = IntelligenceSkill(skill_manager)
        return intelligence.is_recruitment_eligible(self, player)

    def assign_behavior(self, behavior: str) -> None:
        """
        Assign a behavior to this recruit.

        Also initializes combat HP if recruit has no HP set yet.

        Args:
            behavior: The behavior to assign (e.g. "guard", "trader", "assistant").
        """
        self.recruit_behavior = behavior

        # Initialize combat HP if recruit has no HP set yet
        if self.health <= 0 and self.max_health > 0:
            self.health = self.max_health

    def on_player_approach(self, player: Any) -> None:
        """Handle the event of a player approaching the recruit."""
        from npc.trade_system import TradeSystem
        if hasattr(player, "action_system") and player.action_system is not None:
            distance = player.distance_to(self.world_x, self.world_y)
            if distance <= TradeSystem.PROXIMITY_THRESHOLD:
                player.action_system.add_notification(
                    f"Press E to recruit {self.name}.",
                    (255, 220, 100),  # Gold color
                )

    def on_interact(self, player: Any) -> None:
        """Handle the event of a player interacting with the recruit."""
        pass  # stub - P3-S13


# Type map for polymorphic NPC creation
NPC_TYPE_MAP: Dict[str, type] = {
    "merchant": MerchantNPC,
    "quest_giver": QuestGiverNPC,
    "faction_leader": FactionLeaderNPC,
    "recruit": RecruitNPC,
}


def create_npc_from_dict(data: Dict[str, Any]) -> NPC:
    """
    Create an NPC instance based on the npc_type field in the data dict.

    Looks up the NPC type in NPC_TYPE_MAP and calls from_dict on the
    appropriate subclass. Falls back to base NPC class for unknown types.

    Args:
        data: Parsed JSON dict from npcs.json "npcs" array.

    Returns:
        An NPC subclass instance (MerchantNPC, QuestGiverNPC, FactionLeaderNPC,
        RecruitNPC, or NPC for unknown types).
    """
    npc_type = data.get("npc_type", "merchant")
    cls = NPC_TYPE_MAP.get(npc_type, NPC)
    return cls.from_dict(data)
