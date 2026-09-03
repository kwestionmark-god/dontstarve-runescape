"""
quest_system.py — Quest System Core.

Manages quest definitions, progress tracking, acceptance checks,
condition evaluation, and reward distribution. Integrates with
IntelligenceSkill for persuasion checks and with combat/crafting
systems for kill/craft tracking.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skills.intelligence.intelligence import IntelligenceSkill


# ── Dataclasses ───────────────────────────────────────────────────────

@dataclass
class QuestCondition:
    """A single condition that must be satisfied for quest completion."""

    condition_type: str
    target: str
    required_count: int = 1
    current_count: int = 0
    description: str = ""

    def is_satisfied(self) -> bool:
        """Return True if the current count meets or exceeds the required count."""
        return self.current_count >= self.required_count


@dataclass
class QuestDefinition:
    """
    A quest definition loaded from data/quests.json.

    Fields:
        quest_id: Unique identifier for the quest.
        name: Display name of the quest.
        description: Quest description text.
        giver_npc_type: NPC type that gives this quest (e.g. "quest_giver", "faction_leader").
        giver_faction: Faction associated with the quest giver.
        min_commerce: Minimum commerce stat to accept.
        min_persuasion: Minimum persuasion stat to accept.
        min_total_intelligence: Minimum total intelligence skill to accept.
        acceptance_threshold: Base persuasion check threshold (0.0-1.0).
        xp_reward: Intelligence skill XP reward.
        skill_xp_rewards: Dict of skill_name → XP amount.
        recipe_unlocks: List of recipe IDs unlocked on completion.
        gear_unlocks: List of gear IDs unlocked on completion.
        item_rewards: List of [item_id, quantity] pairs.
        conditions: Conditions to complete the quest.
        fail_conditions: Conditions that trigger failure.
        required_faction_status: Faction standing prerequisite ("neutral", "friendly", "suspicious", etc).
        prerequisite_quests: Quest IDs that must be completed first.
        repeatable: Whether the quest can be repeated.
        sprite_key: Sprite key for quest UI display.
    """

    quest_id: str
    name: str
    description: str
    giver_npc_type: str = "quest_giver"
    giver_faction: str = ""
    min_commerce: int = 0
    min_persuasion: int = 0
    min_total_intelligence: int = 0
    acceptance_threshold: float = 0.5
    xp_reward: float = 0.0
    skill_xp_rewards: dict[str, float] = field(default_factory=dict)
    recipe_unlocks: list[str] = field(default_factory=list)
    gear_unlocks: list[str] = field(default_factory=list)
    item_rewards: list[list[str | int]] = field(default_factory=list)
    conditions: list[QuestCondition] = field(default_factory=list)
    fail_conditions: list[QuestCondition] = field(default_factory=list)
    required_faction_status: str | None = None
    prerequisite_quests: list[str] = field(default_factory=list)
    repeatable: bool = False
    sprite_key: str = ""


class QuestState(Enum):
    """Possible states for a quest."""

    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QuestProgress:
    """Tracks the progress of a single quest instance."""

    quest_id: str
    state: "QuestState" = QuestState.AVAILABLE
    giver_npc_id: str = ""
    accepted_at: float = 0.0
    completed_at: float = 0.0
    failed_at: float = 0.0
    fail_reason: str = ""
    conditions: list[QuestCondition] = field(default_factory=list)
    fail_conditions: list[QuestCondition] = field(default_factory=list)
    is_repeatable: bool = False


@dataclass
class QuestEligibilityResult:
    """Result of a quest eligibility check."""

    eligible: bool
    stat_requirements_met: bool
    faction_status_met: bool
    prerequisite_quests_met: bool
    not_already_active: bool
    not_already_completed: bool
    reason: str = ""


@dataclass
class AcceptanceResult:
    """Result of a quest acceptance attempt."""

    success: bool
    quest_id: str
    message: str
    rate: float = 0.0


# ── Quest System ──────────────────────────────────────────────────────

class QuestSystem:
    """
    Core quest management system.

    Tracks quest definitions, player progress, condition evaluation,
    and reward distribution. Integrates with IntelligenceSkill for
    persuasion checks.

    Fields:
        intelligence_skill: Reference to IntelligenceSkill for persuasion checks.
        quest_definitions: All loaded quest definitions (quest_id → QuestDefinition).
        quest_progress: Current quest progress (quest_id → QuestProgress).
        _monster_kill_counts: Monster type → kill count.
        _craft_counts: Recipe ID → craft count.
        _visited_biomes: Set of biome IDs the player has visited.
        _trade_counts: NPC ID → trade count.
        _delivery_counts: Item ID → delivery count.
        _negotiation_counts: Faction ID → negotiation count.
        _combat_faction_counts: Faction ID → combat count.
        _last_tile_x: Last tracked tile X (for biome change detection).
        _last_tile_y: Last tracked tile Y.
    """

    __slots__ = (
        "intelligence_skill",
        "quest_definitions",
        "quest_progress",
        "faction_system",
        "game",
        "_monster_kill_counts",
        "_craft_counts",
        "_visited_biomes",
        "_trade_counts",
        "_delivery_counts",
        "_negotiation_counts",
        "_combat_faction_counts",
        "_last_tile_x",
        "_last_tile_y",
    )

    def __init__(self, intelligence_skill: "IntelligenceSkill") -> None:
        """
        Initialize the quest system.

        Args:
            intelligence_skill: Reference to IntelligenceSkill for persuasion checks.
        """
        self.intelligence_skill: "IntelligenceSkill" = intelligence_skill
        self.quest_definitions: dict[str, QuestDefinition] = {}
        self.quest_progress: dict[str, QuestProgress] = {}
        self._monster_kill_counts: dict[str, int] = {}
        self._craft_counts: dict[str, int] = {}
        self._visited_biomes: set[str] = set()
        self._trade_counts: dict[str, int] = {}
        self._delivery_counts: dict[str, int] = {}
        self._negotiation_counts: dict[str, int] = {}
        self._combat_faction_counts: dict[str, int] = {}
        self._last_tile_x: int | None = None
        self._last_tile_y: int | None = None

    # ── Data Loading ────────────────────────────────────────────────

    def load_quest_data(self) -> int:
        """
        Load quest definitions from data/quests.json.

        Parses each quest entry, including nested QuestCondition objects.

        Returns:
            Number of quests loaded.
        """
        DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
        quest_file = os.path.join(DATA_DIR, "quests.json")

        try:
            with open(quest_file) as f:
                data = json.load(f)
        except FileNotFoundError:
            self.quest_definitions = {}
            return 0
        except json.JSONDecodeError:
            self.quest_definitions = {}
            return 0

        count = 0
        for entry in data.get("quests", []):
            conditions = [QuestCondition(**c) for c in entry.get("conditions", [])]
            fail_conditions = [QuestCondition(**c) for c in entry.get("fail_conditions", [])]

            quest = QuestDefinition(
                quest_id=entry["quest_id"],
                name=entry["name"],
                description=entry["description"],
                giver_npc_type=entry.get("giver_npc_type", "quest_giver"),
                giver_faction=entry.get("giver_faction", ""),
                min_commerce=entry.get("min_commerce", 0),
                min_persuasion=entry.get("min_persuasion", 0),
                min_total_intelligence=entry.get("min_total_intelligence", 0),
                acceptance_threshold=entry.get("acceptance_threshold", 0.5),
                xp_reward=entry.get("xp_reward", 0.0),
                skill_xp_rewards=entry.get("skill_xp_rewards", {}),
                recipe_unlocks=entry.get("recipe_unlocks", []),
                gear_unlocks=entry.get("gear_unlocks", []),
                item_rewards=entry.get("item_rewards", []),
                conditions=conditions,
                fail_conditions=fail_conditions,
                required_faction_status=entry.get("required_faction_status"),
                prerequisite_quests=entry.get("prerequisite_quests", []),
                repeatable=entry.get("repeatable", False),
                sprite_key=entry.get("sprite_key", ""),
            )
            self.quest_definitions[quest.quest_id] = quest
            count += 1

        return count

    # ── Quest Acceptance ────────────────────────────────────────────

    def check_quest_eligibility(
        self, player: object, quest_def: QuestDefinition,
    ) -> QuestEligibilityResult:
        """
        Check if a player meets the requirements for a quest.

        Args:
            player: The player entity.
            quest_def: The quest definition to check.

        Returns:
            QuestEligibilityResult with breakdown of checks.
        """
        # Check if already active
        if quest_def.quest_id in self.quest_progress:
            progress = self.quest_progress[quest_def.quest_id]
            if progress.state == QuestState.ACTIVE:
                return QuestEligibilityResult(
                    eligible=False,
                    stat_requirements_met=True,
                    faction_status_met=True,
                    prerequisite_quests_met=True,
                    not_already_active=False,
                    not_already_completed=True,
                    reason="You are already on this quest.",
                )
            if progress.state == QuestState.COMPLETED and not quest_def.repeatable:
                return QuestEligibilityResult(
                    eligible=False,
                    stat_requirements_met=True,
                    faction_status_met=True,
                    prerequisite_quests_met=True,
                    not_already_active=True,
                    not_already_completed=False,
                    reason="You have already completed this quest.",
                )

        # Check stat requirements
        stat_ok = True
        if hasattr(player, "skill_manager") and player.skill_manager is not None:
            sm = player.skill_manager

            commerce = sm.get_effective_stat("intelligence", "commerce")
            if commerce < quest_def.min_commerce:
                stat_ok = False

            persuasion = sm.get_effective_stat("intelligence", "persuasion")
            if persuasion < quest_def.min_persuasion:
                stat_ok = False

            intel_level = sm.get_skill_level("intelligence")
            if intel_level < quest_def.min_total_intelligence:
                stat_ok = False

        # Check faction status against the quest's faction
        faction_ok = True
        if quest_def.required_faction_status is not None:
            req = quest_def.required_faction_status
            faction_id = quest_def.giver_faction
            current_status = (
                self.faction_system.get_status(faction_id)
                if self.faction_system and faction_id
                else "neutral"
            )
            if not self._status_meets_threshold(current_status, req):
                faction_ok = False

        # Check prerequisite quests
        prereqs_ok = True
        for prereq_id in quest_def.prerequisite_quests:
            if prereq_id in self.quest_progress:
                prereq_progress = self.quest_progress[prereq_id]
                if prereq_progress.state != QuestState.COMPLETED:
                    prereqs_ok = False
                    break
            # If quest doesn't exist in progress, it hasn't been completed
            else:
                prereqs_ok = False
                break

        eligible = stat_ok and faction_ok and prereqs_ok

        if not eligible:
            reasons = []
            if not stat_ok:
                reasons.append("stat requirements")
            if not faction_ok:
                reasons.append("faction standing")
            if not prereqs_ok:
                reasons.append("prerequisite quests")
            reason = "You do not meet the: " + ", ".join(reasons) + "."
        else:
            reason = ""

        return QuestEligibilityResult(
            eligible=eligible,
            stat_requirements_met=stat_ok,
            faction_status_met=faction_ok,
            prerequisite_quests_met=prereqs_ok,
            not_already_active=True,
            not_already_completed=True,
            reason=reason,
        )

    def accept_quest(
        self, player: object, npc: object, quest_id: str,
    ) -> AcceptanceResult:
        """
        Attempt to accept a quest from an NPC.

        Performs eligibility checks and persuasion check via IntelligenceSkill.

        Args:
            player: The player entity.
            npc: The NPC offering the quest.
            quest_id: The quest ID to accept.

        Returns:
            AcceptanceResult with success/failure info.
        """
        quest_def = self.quest_definitions.get(quest_id)
        if quest_def is None:
            return AcceptanceResult(
                success=False,
                quest_id=quest_id,
                message="Quest not found.",
            )

        # Check eligibility
        eligibility = self.check_quest_eligibility(player, quest_def)
        if not eligibility.eligible:
            return AcceptanceResult(
                success=False,
                quest_id=quest_id,
                message=eligibility.reason,
            )

        # Persuasion check via IntelligenceSkill
        check = self.intelligence_skill.check_quest_acceptance(quest_def, player)
        if not check.accepted:
            return AcceptanceResult(
                success=False,
                quest_id=quest_id,
                message=check.message,
                rate=check.rate,
            )

        # Create active progress
        progress = QuestProgress(
            quest_id=quest_id,
            state=QuestState.ACTIVE,
            giver_npc_id=npc.npc_id if hasattr(npc, "npc_id") else "",
            accepted_at=0.0,
            conditions=[QuestCondition(**c.__dict__) for c in quest_def.conditions],
            fail_conditions=[QuestCondition(**c.__dict__) for c in quest_def.fail_conditions],
            is_repeatable=quest_def.repeatable,
        )
        self.quest_progress[quest_id] = progress
        return AcceptanceResult(
            success=True,
            quest_id=quest_id,
            message=f"Quest accepted: {quest_def.name}",
            rate=check.rate,
        )

    # ── Tick / Condition Evaluation ─────────────────────────────────

    def tick(self, dt: float, player: object, tile_map: object) -> None:
        """
        Evaluate quest conditions each frame.

        Tracks biome visits, updates collect_item conditions from inventory,
        checks completion and failure conditions.

        Args:
            dt: Delta time in seconds.
            player: The player entity.
            tile_map: The world TileMap for biome tracking.
        """
        # Biome tracking
        tx = int(player.world_x // 64)
        ty = int(player.world_y // 64)
        if tx != self._last_tile_x or ty != self._last_tile_y:
            tile = tile_map.get_tile(tx, ty)
            if tile and hasattr(tile, "biome") and tile.biome:
                self._visited_biomes.add(tile.biome.id)
            self._last_tile_x = tx
            self._last_tile_y = ty

        # Evaluate active quests
        for quest_id, progress in list(self.quest_progress.items()):
            if progress.state != QuestState.ACTIVE:
                continue

            # Update collect_item conditions from player inventory
            for condition in progress.conditions:
                if condition.condition_type == "collect_item":
                    if hasattr(player, "inventory"):
                        condition.current_count = player.inventory.get_item_quantity(condition.target)
                elif condition.condition_type == "kill_monster":
                    condition.current_count = self._monster_kill_counts.get(condition.target, 0)
                elif condition.condition_type == "visit_location":
                    condition.current_count = 1 if condition.target in self._visited_biomes else 0
                elif condition.condition_type == "craft_item":
                    condition.current_count = self._craft_counts.get(condition.target, 0)
                elif condition.condition_type == "negotiate_faction":
                    condition.current_count = self._negotiation_counts.get(condition.target, 0)
                elif condition.condition_type == "trade_at_location":
                    condition.current_count = self._trade_counts.get(condition.target, 0)
                elif condition.condition_type == "deliver_item":
                    condition.current_count = self._delivery_counts.get(condition.target, 0)

            # Check fail conditions first (immediate)
            for fc in progress.fail_conditions:
                if fc.condition_type == "combat_faction":
                    count = self._combat_faction_counts.get(fc.target, 0)
                    fc.current_count = count
                    if count >= fc.required_count:
                        self.fail_quest(quest_id, "Faction attacked too many times")
                        break

            # Check if all conditions satisfied
            if all(c.is_satisfied() for c in progress.conditions):
                # Pass game reference if available for quest reward wiring
                game_ref = getattr(self, "game", None)
                self.complete_quest(quest_id, player, game_ref)

    # ── Record Events ───────────────────────────────────────────────

    def record_kill(self, monster_id: str) -> None:
        """
        Record a monster kill for quest tracking.

        Args:
            monster_id: The monster type identifier.
        """
        self._monster_kill_counts[monster_id] = self._monster_kill_counts.get(monster_id, 0) + 1

    def record_craft(self, recipe_id: str) -> None:
        """
        Record a craft for quest tracking.

        Args:
            recipe_id: The recipe that was crafted.
        """
        self._craft_counts[recipe_id] = self._craft_counts.get(recipe_id, 0) + 1

    def record_trade(self, npc_id: str) -> None:
        """
        Record a trade for quest tracking.

        Args:
            npc_id: The NPC that was traded with.
        """
        self._trade_counts[npc_id] = self._trade_counts.get(npc_id, 0) + 1

    def record_delivery(self, item_id: str) -> None:
        """
        Record a delivery for quest tracking.

        Args:
            item_id: The item that was delivered.
        """
        self._delivery_counts[item_id] = self._delivery_counts.get(item_id, 0) + 1

    def record_faction_attack(self, faction_id: str) -> None:
        """
        Record a faction combat for quest tracking.

        Args:
            faction_id: The faction that was attacked.
        """
        self._combat_faction_counts[faction_id] = self._combat_faction_counts.get(faction_id, 0) + 1

    def record_negotiation(self, faction_id: str) -> None:
        """
        Record a successful faction negotiation for quest tracking.

        Standing changes are applied by FactionSystem.negotiate() — this
        method only counts the event so standing is never applied twice.

        Args:
            faction_id: The faction that was negotiated with.
        """
        self._negotiation_counts[faction_id] = self._negotiation_counts.get(faction_id, 0) + 1

    # ── Quest Completion ────────────────────────────────────────────

    def complete_quest(
        self, quest_id: str, player: object, game: object,
    ) -> bool:
        """
        Complete a quest and distribute rewards.

        Transitions quest state to COMPLETED and grants:
        1. Skill XP rewards
        2. Recipe unlocks
        3. Gear unlocks
        4. Item rewards

        Args:
            quest_id: The quest to complete.
            player: The player receiving rewards.
            game: Optional game reference (currently unused).

        Returns:
            True if the quest was completed successfully.
        """
        progress = self.quest_progress.get(quest_id)
        if not progress or progress.state != QuestState.ACTIVE:
            return False

        quest_def = self.quest_definitions[quest_id]

        # Mark as completed
        progress.state = QuestState.COMPLETED
        progress.completed_at = 0.0  # could be game.time if passed

        # 1. Skill XP rewards
        if player is not None and hasattr(player, "skill_manager") and player.skill_manager is not None:
            for skill_name, xp_amount in quest_def.skill_xp_rewards.items():
                player.skill_manager.add_xp(skill_name, xp_amount)
            if quest_def.xp_reward > 0:
                player.skill_manager.add_xp("intelligence", quest_def.xp_reward)

        # 2. Recipe unlocks — use game.crafting
        if game is not None and hasattr(game, "crafting") and game.crafting is not None:
            for recipe_id in quest_def.recipe_unlocks:
                game.crafting.unlock_recipe(recipe_id)

        # 3. Gear unlocks — use game.crafting
        if game is not None and hasattr(game, "crafting") and game.crafting is not None:
            for gear_id in quest_def.gear_unlocks:
                game.crafting.unlock_gear(gear_id)

        # Fallback: store on player if game.crafting unavailable
        if player is not None:
            if not hasattr(player, "unlocked_recipes"):
                player.unlocked_recipes = set()
            for recipe_id in quest_def.recipe_unlocks:
                player.unlocked_recipes.add(recipe_id)
            if not hasattr(player, "unlocked_gear"):
                player.unlocked_gear = set()
            for gear_id in quest_def.gear_unlocks:
                player.unlocked_gear.add(gear_id)

        # 4. Item rewards
        if player is not None and hasattr(player, "inventory"):
            for reward in quest_def.item_rewards:
                item_id = reward[0]
                count = int(reward[1])
                if not player.inventory.add_item(item_id, count):
                    if hasattr(player, "action_system") and player.action_system is not None:
                        player.action_system.add_notification(
                            f"Inventory full — quest reward {item_id} x{count} lost!",
                            (255, 150, 100),
                        )

        # 5. Notification
        if player is not None and hasattr(player, "action_system") and player.action_system is not None:
            player.action_system.add_notification(f"Quest completed: {quest_def.name}!", (100, 255, 100))

        return True

    # ── Quest Failure ───────────────────────────────────────────────

    def fail_quest(self, quest_id: str, reason: str = "") -> bool:
        """
        Fail a quest and mark it as FAILED.

        Args:
            quest_id: The quest to fail.
            reason: Optional reason for failure.

        Returns:
            True if the quest was failed successfully.
        """
        progress = self.quest_progress.get(quest_id)
        if not progress or progress.state != QuestState.ACTIVE:
            return False

        quest_def = self.quest_definitions.get(quest_id)
        progress.state = QuestState.FAILED
        progress.failed_at = 0.0
        progress.fail_reason = reason or "Quest failed."

        # Lock recipes that were tied to this quest (if quest_def has recipe_unlocks)
        if quest_def is not None and self.game is not None:
            if hasattr(self.game, "crafting") and self.game.crafting is not None:
                for recipe_id in quest_def.recipe_unlocks:
                    self.game.crafting.lock_recipe(recipe_id)

        # Notify player
        if quest_def is not None:
            # Notification handled by caller if they have player reference
            pass

        return True

    # ── Faction Standing Helpers ────────────────────────────────────

    def _status_meets_threshold(self, current_status: str, required_status: str) -> bool:
        """
        Check if the current standing status meets the required minimum.

        Ordinal order: hostile < suspicious < neutral < friendly < allied

        Args:
            current_status: The player's current standing status (e.g. "friendly").
            required_status: The minimum required status (e.g. "neutral").

        Returns:
            True if current_status >= required_status.
        """
        levels = {
            "hostile": 0,
            "suspicious": 1,
            "neutral": 2,
            "friendly": 3,
            "allied": 4,
        }
        current_ord = levels.get(current_status, 0)
        required_ord = levels.get(required_status, 0)
        return current_ord >= required_ord

    # ── Query Methods ───────────────────────────────────────────────

    def get_active_quests(self) -> list[QuestProgress]:
        """
        Return all active quests.

        Returns:
            List of QuestProgress objects with ACTIVE state.
        """
        return [
            progress
            for progress in self.quest_progress.values()
            if progress.state == QuestState.ACTIVE
        ]

    def get_completed_quests(self) -> list[QuestProgress]:
        """
        Return all completed quests.

        Returns:
            List of QuestProgress objects with COMPLETED state.
        """
        return [
            progress
            for progress in self.quest_progress.values()
            if progress.state == QuestState.COMPLETED
        ]

    def get_available_quests(self) -> list[QuestDefinition]:
        """
        Return all quest definitions that are not yet in progress.

        Returns:
            List of QuestDefinition objects not in any progress state.
        """
        return [
            quest_def
            for quest_def in self.quest_definitions.values()
            if quest_def.quest_id not in self.quest_progress
        ]

    def get_available_quests_for_npc(self, npc_id: str) -> list:
        """Return quest definitions available from a specific QuestGiverNPC.
        Actual scoping is handled at the QuestPanel level via npc.available_quests.
        """
        base = self.get_available_quests()
        return base

    def get_quest_progress(self, quest_id: str) -> QuestProgress | None:
        """
        Get the progress for a specific quest.

        Args:
            quest_id: The quest ID to look up.

        Returns:
            QuestProgress if found, None otherwise.
        """
        return self.quest_progress.get(quest_id)
