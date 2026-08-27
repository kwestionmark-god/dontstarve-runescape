"""
Tests for Report 6 — Building & Construction fixes.

Covers:
- Fix 1: the stale duplicate building/construction.py is deleted/unimportable
- Fix 2: building panel displays the *calculated* HP (calculate_structure_hp)
- Fix 3: redundant local imports removed from building_system.py (math/random)
"""

import importlib.util
import inspect
import types
from unittest import mock

import pygame
import pytest


def _make_font(records=None):
    """A font mock whose ``render`` returns a real Surface (so blit works);
    optionally records the rendered text for assertions."""
    font = mock.MagicMock()

    def _render(text, *args, **kwargs):
        if records is not None:
            records.append(str(text))
        return pygame.Surface((max(1, len(str(text)) * 6), 14))

    font.render.side_effect = _render
    return font


def _campfire_struct_def() -> object:
    """A real StructureDef (portable, common) for building-panel tests."""
    from building.structure import StructureDef

    return StructureDef(
        structure_id="campfire",
        name="Campfire",
        structure_type="portable",
        construction_sub_stat="common",
        hp=30,
        materials=[("stick", 4), ("flint", 1)],
        requires_structure_level=0,
        requires_skill_level=0,
        biome_compatible=["forest"],
    )


# ── Fix 1 ─────────────────────────────────────────────────────────────

def test_building_construction_module_deleted():
    """building.construction can no longer be imported (stale duplicate removed)."""
    assert importlib.util.find_spec("building.construction") is None


# ── Fix 2 ─────────────────────────────────────────────────────────────

def test_panel_displays_calculated_hp_not_base_hp():
    """_render_structure_entry calls calculate_structure_hp and blits the result."""
    from ui.building_panel import BuildingPanel

    struct_def = _campfire_struct_def()

    construction = mock.MagicMock()
    construction.can_place_structure.return_value = (True, "")
    sentinel = 999
    construction.calculate_structure_hp.return_value = sentinel

    fake_bs = types.SimpleNamespace(construction=construction)

    panel = BuildingPanel.__new__(BuildingPanel)
    panel.x = 0
    panel._struct_font = _make_font()
    panel._cached_crafting_level = 0  # for can_place_structure
    panel._structure_rects = []  # initialize for _is_structure_selected

    rendered = []
    panel._hint_font = _make_font(records=rendered)

    surface = pygame.Surface((400, 400))
    # New signature: (screen, struct_def, entry_rect, building_system)
    entry_rect = pygame.Rect(10, 0, 380, 45)
    panel._render_structure_entry(surface, struct_def, entry_rect, fake_bs)

    # (a) the calculator is called once, with the passed struct_def — BARE
    #     assertion (wrapping it in `assert` would swallow the failure).
    construction.calculate_structure_hp.assert_called_once_with(struct_def)
    # (b) the calculated value is actually blitted into the panel (not computed
    #     and discarded).
    assert any(str(sentinel) in t for t in rendered)


# ── Fix 3 ─────────────────────────────────────────────────────────────

def test_redundant_local_imports_removed():
    """math is imported at module level only; no inner shadowing imports remain."""
    import building.building_system as building_system

    module_src = inspect.getsource(building_system)
    assert "import math" in module_src

    monster_src = inspect.getsource(
        building_system.BuildingSystem.monster_attack_structure
    )
    tick_src = inspect.getsource(building_system.BuildingSystem.tick)

    assert not any(
        line.strip() == "import math" for line in monster_src.splitlines()
    )
    assert not any(
        line.strip() == "import random" for line in tick_src.splitlines()
    )
    assert not any(
        line.strip() == "import math" for line in tick_src.splitlines()
    )


def _build_system_with_campfire() -> object:
    """A BuildingSystem with a single low-HP campfire placed at the origin."""
    from building.building_system import BuildingSystem
    from building.structure import Structure
    from inventory.inventory import Inventory
    from skills.construction.construction import Construction
    from skills.skill_manager import SkillManager

    skill_manager = SkillManager()
    construction = Construction(skill_manager)
    building_system = BuildingSystem(
        skill_manager, Inventory(), construction, {"common": {}}
    )

    structure = Structure(
        structure_def=_campfire_struct_def(),
        world_x=0.0,
        world_y=0.0,
        hp=1,
        max_hp=1,
        is_active=True,
        is_portable=True,
    )
    building_system.structures.append(structure)
    return building_system


def test_monster_attack_structure_uses_module_level_math():
    """monster_attack_structure still finds/damages the nearest structure."""
    building_system = _build_system_with_campfire()

    destroyed = building_system.monster_attack_structure(10, 0.0, 0.0)

    assert destroyed is not None
    assert destroyed.structure_def.structure_id == "campfire"
    assert len(building_system.structures) == 0


def _ballista_system_with_in_range_monster():
    """A BuildingSystem with a ready-to-fire ballista and a monster in range."""
    from building.building_system import BuildingSystem
    from building.structure import Structure, StructureDef
    from inventory.inventory import Inventory
    from skills.construction.construction import Construction
    from skills.skill_manager import SkillManager

    skill_manager = SkillManager()
    construction = Construction(skill_manager)
    building_system = BuildingSystem(
        skill_manager, Inventory(), construction, {"offensive": {}}
    )

    ballista = Structure(
        structure_def=StructureDef(
            structure_id="ballista",
            name="Ballista",
            structure_type="fixed",
            construction_sub_stat="offensive",
            hp=100,
            materials=[("stick", 8)],
            requires_structure_level=0,
            requires_skill_level=0,
            biome_compatible=["forest"],
        ),
        world_x=0.0,
        world_y=0.0,
        hp=100,
        max_hp=100,
        is_active=True,
    )
    # Arm it so the fire path runs on the very first tick (reaches math.sqrt).
    ballista._fire_timer = 0.0
    building_system.structures.append(ballista)

    class _Monster:
        world_x = 100.0
        world_y = 0.0

        def is_alive(self) -> bool:
            return True

    class StubCombatSystem:
        monsters = [_Monster()]

        def offensive_structure_hit(self, structure, monster, damage):
            self.hit = (structure, monster, damage)

    return building_system, StubCombatSystem()


def test_tick_offensive_firing_resolves_module_level_math():
    """tick fires an offensive structure, exercising module-level math.sqrt."""
    building_system, combat = _ballista_system_with_in_range_monster()

    building_system.tick(1.0, combat_system=combat)

    assert hasattr(combat, "hit")
    assert combat.hit[2] >= 5  # ballista base damage


def test_tick_skips_non_offensive_structure():
    """tick runs its body without touching combat for a non-offensive structure."""
    building_system = _build_system_with_campfire()

    class StubCombatSystem:
        monsters = []

    building_system.tick(1.0, combat_system=StubCombatSystem())
