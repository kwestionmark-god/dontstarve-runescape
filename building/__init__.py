"""
building/__init__.py — Building system package.

Provides:
    BuildingSystem  — Structure placement, validation, and removal
    Structure       — Structure entity with HP and state
    Construction    — Construction sub-stat management
"""

from building.building_system import BuildingSystem, BuildResult
from building.structure import Structure, StructureDef
from skills.construction.construction import Construction

__all__ = [
    "BuildingSystem",
    "BuildResult",
    "Structure",
    "StructureDef",
    "Construction",
]
