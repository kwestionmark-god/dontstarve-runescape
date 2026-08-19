"""
firemaking/ — Firemaking skill package.

Handles fire creation, burn duration/radius/intensity stats,
and fire entity management.
"""

from skills.firemaking.firemaking import FiremakingSkill
from skills.firemaking.fire_entity import FireEntity

__all__ = ["FiremakingSkill", "FireEntity"]
