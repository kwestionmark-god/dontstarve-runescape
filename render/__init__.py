"""
render/__init__.py — 2.5D terrain and sprite rendering.

Exports:
    TileRenderer  — terrain tile rendering with elevation depth sorting.
    SpriteRenderer — billboard sprites (player + resources).
"""

from render.tile_renderer import TileRenderer
from render.sprite_renderer import SpriteRenderer
from render.seasonal_renderer import SeasonalRenderer
from render.particle_system import ParticleSystem
from render.npc_renderer import NPCRenderer

__all__ = ["TileRenderer", "SpriteRenderer", "SeasonalRenderer", "ParticleSystem", "NPCRenderer"]
