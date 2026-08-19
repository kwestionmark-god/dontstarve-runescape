"""
skills/ — Per-skill packages.

Each skill has its own package with data files.
"""

from skills.metallurgy.metallurgy import MetallurgySkill, SmeltRecipe, SmeltResult
from skills.firemaking.firemaking import FiremakingSkill
from skills.firemaking.fire_entity import FireEntity
from skills.intelligence.intelligence import IntelligenceSkill
from skills.cooking.cooking import CookingSkill
from skills.construction.construction import Construction

__all__ = [
    "MetallurgySkill", "SmeltRecipe", "SmeltResult",
    "FiremakingSkill", "FireEntity",
    "IntelligenceSkill",
    "CookingSkill",
    "Construction",
]
