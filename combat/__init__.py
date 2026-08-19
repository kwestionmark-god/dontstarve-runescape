"""
combat/__init__.py — Combat system package.

Provides:
    CombatSystem  — Real-time combat engine
    Monster       — Monster base class + AI state machine
    GearItem      — Weapon/armor definitions
    PlayerGear    — Player gear slots
"""

from combat.combat_system import CombatSystem, AttackResult
from combat.monster import Monster
from combat.gear import GearItem, PlayerGear

__all__ = [
    "CombatSystem",
    "AttackResult",
    "Monster",
    "GearItem",
    "PlayerGear",
]
