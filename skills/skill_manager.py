"""
skill_manager.py — XP tracking, level-up, and stat allocation.

Implements the OSRS XP formula, skill levels (1–99), stat point
awarding, and per-skill sub-stat allocation.

Phase 1 active skills: Woodcutting, Mining, Cooking
Phase 2 active skills: Combat, Metallurgy, Firemaking
Phase 3 skills: Intelligence
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from config import (
    HP_BASE_MAX,
    PLAYER_HP_PER_COMBAT_LEVEL,
    XP_SCALE_FACTOR,
    STAT_POINTS_PER_LEVEL,
    WILDCARD_INTERVAL,
)

if TYPE_CHECKING:
    from typing import Dict


# Phase 1: default sub-stats for each skill with base allocations
_SKILL_DEFAULTS: Dict[str, Dict[str, int]] = {
    "woodcutting": {"success_rate": 0, "harvest_boost": 0, "stamina": 0},
    "mining": {"success_rate": 0, "extra_resources": 0, "stamina": 0},
    "cooking": {"success_rate": 0, "nutrition": 0, "spoilage_reduction": 0},
    "foraging": {"success_rate": 0, "harvest_boost": 0, "stamina": 0},
    # Phase 2 skills
    "crafting": {
        "item_quality": 0,
        "processing_speed": 0,
        "common_building_tech": 0,
        "defensive_building_tech": 0,
        "offensive_building_tech": 0,
        "decorative_building_tech": 0,
    },
    "combat": {"attack": 0, "defence": 0, "speed": 0},
    "metallurgy": {
        "alloy_mastery": 0,
        "smelt_efficiency": 0,
        "tool_durability": 0,
    },
    "firemaking": {
        "burn_duration": 0,
        "radius": 0,
        "intensity": 0,
    },
    # Phase 3 skills
    "intelligence": {
        "commerce": 0,
        "persuasion": 0,
        "trade": 0,
    },
}

# Starting stat points at level 1: 3 per spec formula (level * 3)
_STARTING_STAT_POINTS = STAT_POINTS_PER_LEVEL


@dataclass
class SkillData:
    """
    Persistent data for a single skill.

    Fields:
        skill_id: e.g. "woodcutting", "mining", "cooking"
        level: 1–99, starts at 1
        xp: total XP accumulated (cumulative from level 1)
        stat_points: unspent stat points (3 per level, starting at 3 for level 1)
        sub_stats: sub-stat name → allocated points
    """

    skill_id: str
    level: int = 1
    xp: float = 0.0
    stat_points: int = _STARTING_STAT_POINTS  # 3 at level 1 per spec formula
    sub_stats: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure sub_stats has all defaults for this skill."""
        if not self.sub_stats:
            defaults = _SKILL_DEFAULTS.get(self.skill_id, {})
            self.sub_stats = dict(defaults)


class SkillManager:
    """
    Tracks XP, levels, and stat points across all active skills.

    Uses the OSRS XP formula:
        xp_to_go_from(L) = floor((L + 300 * 2^(L/7)) / XP_SCALE_FACTOR)

    Stat points: 3 per skill level, 1 wildcard per 5 total skill levels.
    """

    __slots__ = ("skills", "wildcard_points")

    def __init__(self) -> None:
        """
        Initialize with Phase 1 skills at level 1, 0 XP.
        """
        self.skills: Dict[str, SkillData] = {}
        for skill_id in _SKILL_DEFAULTS:
            self.skills[skill_id] = SkillData(skill_id=skill_id)
        self.wildcard_points: int = 0

    # ── XP & Leveling ───────────────────────────────────────────────

    @staticmethod
    def get_xp_for_level(level: int) -> int:
        """
        Returns total XP required to reach the given level (1-indexed).

        Also known as get_total_xp_to_level — cumulative XP from level 1
        up to (but not including) the given level.

        OSRS formula: sum over L=1..level-1 of floor((L + 300 * 2^(L/7)) / 4)

        Args:
            level: Target level (1–99).

        Returns:
            Cumulative XP from level 1 up to (but not including) this level.
            Level 1 returns 0.
        """
        if level <= 1:
            return 0
        total_xp = 0
        for L in range(1, level):
            total_xp += math.floor((L + 300 * math.pow(2, L / 7)) / XP_SCALE_FACTOR)
        return total_xp

    @staticmethod
    def xp_to_advance_from(level: int) -> int:
        """
        Returns XP needed to go from current level to the next.

        Args:
            level: Current level (1–98).

        Returns:
            XP needed to reach level + 1.
        """
        return math.floor((level + 300 * math.pow(2, level / 7)) / XP_SCALE_FACTOR)

    # Alias for spec compatibility
    get_total_xp_to_level = get_xp_for_level

    def add_xp(self, skill_id: str, xp_amount: float) -> int | None:
        """
        Add XP to a skill. Checks for level-up.

        If the skill levels up, awards stat points and checks for
        wildcard points.

        Args:
            skill_id: The skill to grant XP to.
            xp_amount: Amount of XP to add.

        Returns:
            New level if leveled up, None if no level-up occurred.
        """
        if skill_id not in self.skills:
            return None

        skill = self.skills[skill_id]
        previous_level = skill.level
        skill.xp += xp_amount

        # Check for level-up (max level 99)
        while skill.level < 99:
            xp_needed = self.get_xp_for_level(skill.level + 1)
            if skill.xp >= xp_needed:
                skill.level += 1
                self.award_stat_points(skill_id, skill.level)
                self._check_wildcard()
            else:
                break

        # Return new level only if it actually changed
        if skill.level > previous_level:
            return skill.level
        return None

    def add_xp_with_notification(
        self,
        skill_id: str,
        xp_amount: float,
    ) -> list[str]:
        """
        Add XP to a skill and return level-up notification messages.

        Args:
            skill_id: The skill to grant XP to.
            xp_amount: Amount of XP to add.

        Returns:
            List of notification messages (empty if no level-up).
        """
        new_level = self.add_xp(skill_id, xp_amount)
        messages: list[str] = []
        if new_level is not None:
            skill_name = skill_id.replace("_", " ").title()
            messages.append(f"{skill_name} level {new_level}!")
        return messages

    def get_xp_progress(self, skill_id: str) -> float:
        """
        Returns XP progress toward next level as a 0–1 ratio.

        Args:
            skill_id: The skill to query.

        Returns:
            0.0 (at current level) to 1.0 (at next level).
            1.0 if already at level 99.
        """
        if skill_id not in self.skills:
            return 1.0

        skill = self.skills[skill_id]
        if skill.level >= 99:
            return 1.0

        xp_at_level = self.get_xp_for_level(skill.level)
        xp_needed = self.get_xp_for_level(skill.level + 1)
        xp_in_level = skill.xp - xp_at_level
        xp_for_next = xp_needed - xp_at_level

        if xp_for_next == 0:
            return 1.0

        return min(1.0, max(0.0, xp_in_level / xp_for_next))

    # ── Stat Points ─────────────────────────────────────────────────

    def award_stat_points(self, skill_id: str, new_level: int) -> int:
        """
        Award 3 stat points for reaching a new skill level.

        Args:
            skill_id: The skill that leveled up.
            new_level: The new skill level.

        Returns:
            Number of stat points awarded (always 3).
        """
        points = STAT_POINTS_PER_LEVEL
        if skill_id in self.skills:
            self.skills[skill_id].stat_points += points
        return points

    def award_wildcard_points(self) -> int:
        """
        Manually award wildcard points based on total skill levels.

        Called after add_xp triggers level-ups. Awards 1 wildcard
        point per 5 total skill levels.

        Returns:
            Number of wildcard points awarded.
        """
        total_levels = self.get_total_skill_levels()
        expected = total_levels // WILDCARD_INTERVAL
        gained = expected - self.wildcard_points
        if gained > 0:
            self.wildcard_points = expected
        return gained

    def _check_wildcard(self) -> None:
        """Check and award wildcard points if needed."""
        self.award_wildcard_points()

    def get_total_skill_levels(self) -> int:
        """Returns the sum of all skill levels."""
        return sum(s.level for s in self.skills.values())

    def get_skill_level(self, skill_id: str) -> int:
        """
        Returns the level of a skill, or 0 if the skill is not registered.

        Args:
            skill_id: The skill to query.

        Returns:
            Skill level (1–99) or 0 if skill not found.
        """
        if skill_id not in self.skills:
            return 0
        return self.skills[skill_id].level

    def has_skill(self, skill_id: str) -> bool:
        """Returns True if the skill is registered."""
        return skill_id in self.skills

    def get_max_hp(self) -> float:
        """
        Returns max HP = base HP + Combat level bonus.

        Each Combat level grants PLAYER_HP_PER_COMBAT_LEVEL HP.

        Returns:
            Total max HP.
        """
        base = HP_BASE_MAX
        combat_level = self.get_skill_level("combat")
        return base + (combat_level * PLAYER_HP_PER_COMBAT_LEVEL)

    def apply_xp_penalty(self, total_xp_loss: int) -> None:
        """
        Apply an XP penalty across all skills proportionally.

        Called on soft death: loses 1% of total accumulated XP.

        Args:
            total_xp_loss: Total XP to remove across all skills.
        """
        total_xp = sum(s.xp for s in self.skills.values())
        if total_xp <= 0:
            return
        for skill in self.skills.values():
            share = skill.xp / total_xp
            loss = int(total_xp_loss * share)
            skill.xp = max(0, skill.xp - loss)

    def get_effective_stat(self, skill_id: str, sub_stat: str) -> int:
        """
        Returns the total allocated points for a sub-stat.

        Args:
            skill_id: The skill to query.
            sub_stat: The sub-stat name.

        Returns:
            Total allocated points (0 if skill/sub-stat doesn't exist).
        """
        if skill_id not in self.skills:
            return 0
        return self.skills[skill_id].sub_stats.get(sub_stat, 0)

    # ── Allocation ──────────────────────────────────────────────────

    def allocate_stat(
        self,
        skill_id: str,
        sub_stat: str,
        points: int,
        wildcard: bool = False,
    ) -> bool:
        """
        Spend stat points on a sub-stat. No refunds.

        Args:
            skill_id: The skill to allocate points to.
            sub_stat: The sub-stat name.
            points: Number of points to spend (>= 1).
            wildcard: Whether to use wildcard points (False = skill-specific).

        Returns:
            True if allocation succeeded, False if insufficient points.
        """
        if points < 1:
            return False

        if skill_id not in self.skills:
            return False

        skill = self.skills[skill_id]

        if wildcard:
            if self.wildcard_points < points:
                return False
            self.wildcard_points -= points
        else:
            if skill.stat_points < points:
                return False
            skill.stat_points -= points

        skill.sub_stats[sub_stat] = skill.sub_stats.get(sub_stat, 0) + points
        return True

    def refund_stat(
        self,
        skill_id: str,
        sub_stat: str,
        points: int = 1,
    ) -> bool:
        """
        Refund stat points from a sub-stat.

        Args:
            skill_id: The skill to refund points from.
            sub_stat: The sub-stat name.
            points: Number of points to refund (default 1).

        Returns:
            True if refund succeeded, False if sub-stat has insufficient points.
        """
        if points < 1:
            return False

        if skill_id not in self.skills:
            return False

        skill = self.skills[skill_id]

        current = skill.sub_stats.get(sub_stat, 0)
        if current < points:
            return False

        skill.sub_stats[sub_stat] = current - points
        skill.stat_points += points
        return True

    # ── State Snapshots ─────────────────────────────────────────────

    def get_snapshot(self) -> Dict[str, object]:
        """
        Return a frozen snapshot of all skill data for UI rendering.

        Returns:
            Dict mapping skill_id to skill snapshot dicts.
        """
        return {
            sid: {
                "level": s.level,
                "xp": s.xp,
                "stat_points": s.stat_points,
                "sub_stats": dict(s.sub_stats),
                "xp_progress": self.get_xp_progress(sid),
            }
            for sid, s in self.skills.items()
        }
