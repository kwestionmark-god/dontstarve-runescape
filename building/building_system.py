"""
building/building_system.py — Building engine.

Manages structure placement, removal, pickup, and validation.
Integrates with inventory for material consumption and with
Construction for sub-stat checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from config import TILE_SIZE

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager
    from inventory.inventory import Inventory

from building.structure import Structure, StructureDef
from skills.construction.construction import Construction


@dataclass
class BuildResult:
    """Result of a structure placement attempt."""
    success: bool
    structure: Optional[Structure] = None
    xp_gained: float = 0.0
    message: str = ""


@dataclass
class RemoveResult:
    """Result of a structure removal attempt."""
    success: bool
    materials_returned: List[Tuple[str, int]] = field(default_factory=list)
    message: str = ""


class BuildingSystem:
    """
    Manages structure placement, removal, and state.

    Fields:
        skill_manager: Reference to the skill manager.
        construction: Construction sub-stat manager.
        structures: All placed structures on the map.
        inventory: Player's inventory (for material checks).
    """

    __slots__ = (
        "skill_manager",
        "construction",
        "structures",
        "inventory",
        "structure_defs",
        "npc_assignments",
        "_game_ref",
    )

    def __init__(
        self,
        skill_manager: SkillManager,
        inventory: Inventory,
        construction: Construction,
        structure_defs: Dict[str, Dict[str, StructureDef]],
        game_ref: object | None = None,
    ) -> None:
        self.skill_manager: SkillManager = skill_manager
        self.construction: Construction = construction
        self.structures: List[Structure] = []
        self.inventory: Inventory = inventory
        self.structure_defs: Dict[str, Dict[str, StructureDef]] = structure_defs

        # NPC-structure assignments: structure_id → npc_id
        self.npc_assignments: Dict[str, str] = {}
        self._game_ref: object | None = game_ref

    # ── Placement ───────────────────────────────────────────────────

    def place_structure(
        self,
        struct_def: StructureDef,
        world_x: float,
        world_y: float,
        player_world_x: float,
        player_world_y: float,
        biome_id: str,
    ) -> BuildResult:
        """
        Attempt to place a structure at a world position.

        Validation:
        1. Within 3 tiles of the player
        2. Target tile must be empty
        3. Biome must be compatible
        4. Player must have required materials
        5. Construction sub-stat level check
        6. Crafting skill level check

        Args:
            struct_def: The structure blueprint.
            world_x: X position in pixels.
            world_y: Y position in pixels.
            player_world_x: Player's X position.
            player_world_y: Player's Y position.
            biome_id: The biome ID of the target tile.

        Returns:
            BuildResult with success/failure info.
        """
        # 1. Within 3 tiles of player
        dist = math.sqrt(
            (world_x - player_world_x) ** 2 + (world_y - player_world_y) ** 2
        )
        if dist > 3 * TILE_SIZE:
            return BuildResult(success=False, message="Too far from player.")

        # 2. Check for existing structure at position
        for existing in self.structures:
            if (
                math.isclose(existing.world_x, world_x, abs_tol=TILE_SIZE)
                and math.isclose(existing.world_y, world_y, abs_tol=TILE_SIZE)
            ):
                return BuildResult(success=False, message="Tile already occupied.")

        # 2b. Check if player or NPCs occupy the target tile
        if self._game_ref is not None:
            player = getattr(self._game_ref, "player", None)
            if player is not None:
                if (
                    math.isclose(player.world_x, world_x, abs_tol=TILE_SIZE)
                    and math.isclose(player.world_y, world_y, abs_tol=TILE_SIZE)
                ):
                    return BuildResult(success=False, message="Player occupies this tile.")
            # Check NPC positions
            npc_system = getattr(self._game_ref, "npc_system", None)
            if npc_system is not None:
                for npc in npc_system.npcs:
                    if not npc.is_active:
                        continue
                    npc_x = getattr(npc, "world_x", None)
                    npc_y = getattr(npc, "world_y", None)
                    if npc_x is not None and npc_y is not None:
                        if (
                            math.isclose(npc_x, world_x, abs_tol=TILE_SIZE)
                            and math.isclose(npc_y, world_y, abs_tol=TILE_SIZE)
                        ):
                            return BuildResult(
                                success=False,
                                message=f"{npc.name} occupies this tile.",
                            )

        # 3. Biome compatibility
        if struct_def.biome_compatible and biome_id not in struct_def.biome_compatible:
            return BuildResult(
                success=False,
                message=f"Not compatible with {biome_id} biome.",
            )

        # 4. Materials check
        for item_id, qty in struct_def.materials:
            if not self.inventory.has_items(item_id, qty):
                return BuildResult(
                    success=False,
                    message=f"Missing: {item_id} (need {qty}).",
                )

        # 5 & 6. Construction sub-stat and Crafting level checks
        crafting_level = self.skill_manager.get_skill_level("crafting")
        allowed, reason = self.construction.can_place_structure(
            struct_def, crafting_level
        )
        if not allowed:
            return BuildResult(success=False, message=reason)

        # Calculate HP with Construction bonuses
        calculated_hp = self.construction.calculate_structure_hp(struct_def)

        # Consume materials
        for item_id, qty in struct_def.materials:
            self.inventory.remove_item(item_id, qty)

        # Create structure
        structure = Structure(
            structure_def=struct_def,
            world_x=world_x,
            world_y=world_y,
            hp=calculated_hp,
            max_hp=calculated_hp,
            is_active=True,
            is_portable=struct_def.structure_type == "portable",
        )

        self.structures.append(structure)

        # Grant Construction XP based on structure complexity
        xp_gained = self._calculate_construction_xp(struct_def)

        return BuildResult(
            success=True,
            structure=structure,
            xp_gained=xp_gained,
            message=f"You build a {struct_def.name}.",
        )

    def _calculate_construction_xp(self, struct_def: StructureDef) -> float:
        """
        Calculate Construction XP granted for placing a structure.

        XP scales with structure HP and tier.

        Args:
            struct_def: The structure blueprint.

        Returns:
            XP granted.
        """
        base_xp = struct_def.hp * 0.5
        if struct_def.structure_type == "portable":
            base_xp *= 0.5
        elif struct_def.structure_type == "fixed":
            base_xp *= 1.5
        return base_xp

    # ── Removal / Pickup ────────────────────────────────────────────

    def pickup_structure(self, structure: Structure) -> RemoveResult:
        """
        Pick up a portable structure, returning materials to inventory.

        Args:
            structure: The structure to pick up.

        Returns:
            RemoveResult with materials returned.
        """
        if not structure.is_portable:
            return RemoveResult(
                success=False,
                message="Cannot pick up fixed structures.",
            )

        return_rate = self.construction.get_material_return_rate(structure.structure_def)

        materials_returned: List[Tuple[str, int]] = []
        for item_id, qty in structure.structure_def.materials:
            returned_qty = max(1, int(qty * return_rate))
            self.inventory.add_item(item_id, returned_qty)
            materials_returned.append((item_id, returned_qty))

        # Clean up NPC assignment when structure is picked up
        self._cleanup_npc_assignment_on_removal(structure)
        self.structures.remove(structure)

        return RemoveResult(
            success=True,
            materials_returned=materials_returned,
            message=f"Picked up {structure.structure_def.name}.",
        )

    def remove_structure(self, structure: Structure) -> RemoveResult:
        """
        Destroy/demolish a structure (no material return for fixed).

        Args:
            structure: The structure to remove.

        Returns:
            RemoveResult with partial materials (if any).
        """
        return_rate = self.construction.get_material_return_rate(structure.structure_def)

        materials_returned: List[Tuple[str, int]] = []
        for item_id, qty in structure.structure_def.materials:
            returned_qty = max(1, int(qty * return_rate))
            self.inventory.add_item(item_id, returned_qty)
            materials_returned.append((item_id, returned_qty))

        # Clean up NPC assignment when structure is destroyed
        self._cleanup_npc_assignment_on_removal(structure)
        self.structures.remove(structure)

        return RemoveResult(
            success=True,
            materials_returned=materials_returned,
            message=f"Removed {structure.structure_def.name}.",
        )

    # ── Monster Interaction ─────────────────────────────────────────

    def monster_attack_structure(
        self, monster_attack: int, monster_world_x: float, monster_world_y: float,
    ) -> Optional[Structure]:
        """
        Find and damage the nearest structure to a monster.

        Called by CombatSystem when a monster attacks.

        Args:
            monster_attack: The monster's attack stat (damage).
            monster_world_x: Monster's X position (for nearest structure lookup).
            monster_world_y: Monster's Y position.

        Returns:
            The destroyed structure if it died, or None if no structure was
            within range / attacked structure survives.
        """
        if not self.structures:
            return None

        # Find the closest structure to the monster
        best = None
        best_dist = float("inf")
        for s in self.structures:
            dist = math.sqrt((s.world_x - monster_world_x) ** 2 + (s.world_y - monster_world_y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = s

        if best is None:
            return None

        destroyed = best.take_damage(monster_attack)

        if destroyed:
            # Drop partial materials
            return_rate = self.construction.get_material_return_rate(best.structure_def)
            for item_id, qty in best.structure_def.materials:
                returned_qty = max(1, int(qty * return_rate))
                self.inventory.add_item(item_id, returned_qty)
            # Clean up NPC assignment when structure is destroyed by monster
            self._cleanup_npc_assignment_on_removal(best)
            self.structures.remove(best)
            return best

        return None

    # ── Queries ─────────────────────────────────────────────────────

    def get_structures_at(
        self, world_x: float, world_y: float
    ) -> List[Structure]:
        """Return structures on a specific tile (pixel coords)."""
        result = []
        for s in self.structures:
            if (
                math.isclose(s.world_x, world_x, abs_tol=TILE_SIZE)
                and math.isclose(s.world_y, world_y, abs_tol=TILE_SIZE)
            ):
                result.append(s)
        return result

    def get_all_structures(self) -> List[Structure]:
        """Return all structures."""
        return list(self.structures)

    def tick(self, dt: float, combat_system=None) -> None:
        """
        Update all structures: check for monster attacks and fire damage.

        Monster attack check: for each monster in attack range of a structure,
        attempt to damage the nearest structure.

        Offensive structure firing: ballistas and trebuchets periodically
        attack the nearest monster in range based on their Offensive Building
        Tech damage stat.

        Fire damage: if a fire is within radius of a burnable structure,
        deal damage each second.

        Args:
            dt: Delta time.
            combat_system: Optional CombatSystem reference for offensive structure targeting.
        """
        if combat_system is None:
            return

        # Offensive structure firing
        for structure in self.structures:
            if not structure.is_active:
                continue

            struct_id = structure.structure_def.structure_id
            if struct_id not in ("ballista", "trebuchet"):
                continue

            # Attack cooldown per structure (ballista: 2s, trebuchet: 4s)
            cooldown = 2.0 if struct_id == "ballista" else 4.0
            if not hasattr(structure, "_fire_timer"):
                structure._fire_timer = cooldown  # Fire immediately on first tick

            structure._fire_timer -= dt
            if structure._fire_timer > 0:
                continue

            # Find nearest monster to this offensive structure
            best_monster = None
            best_dist = float("inf")
            attack_range = 200.0 if struct_id == "ballista" else 300.0  # px

            for monster in combat_system.monsters:
                if not monster.is_alive():
                    continue
                dist = math.sqrt(
                    (monster.world_x - structure.world_x) ** 2 +
                    (monster.world_y - structure.world_y) ** 2
                )
                if dist <= attack_range and dist < best_dist:
                    best_dist = dist
                    best_monster = monster

            if best_monster is None:
                structure._fire_timer = cooldown
                continue

            # Calculate damage: base + offensive_building_tech × multiplier
            offensive_level = self.skill_manager.get_effective_stat(
                "crafting", "offensive_building_tech"
            )

            if struct_id == "ballista":
                base_damage = 5
                multiplier = 2
            else:  # trebuchet
                base_damage = 10
                multiplier = 3

            damage = base_damage + offensive_level * multiplier

            # Delegate damage handling to CombatSystem
            combat_system.offensive_structure_hit(structure, best_monster, damage)

            structure._fire_timer = cooldown

    # ── NPC-Structure Assignment ────────────────────────────────────

    def _is_guard_post(self, structure: Structure) -> bool:
        """Check if a structure qualifies as a guard post."""
        return (
            structure.structure_def.construction_sub_stat == "offensive"
            or structure.structure_def.structure_id == "stone_wall_tower"
        )

    def assign_npc_to_structure(
        self, structure_id: str, npc_id: str
    ) -> tuple[bool, str]:
        """
        Assign a recruited guard NPC to a guard post structure.

        Args:
            structure_id: The structure's structure_id (e.g., "ballista").
            npc_id: The NPC's unique identifier.

        Returns:
            (success, message) tuple.
        """
        # 1. Find the structure by ID in self.structures
        structure = None
        for s in self.structures:
            if s.structure_def.structure_id == structure_id:
                structure = s
                break
        if structure is None:
            return (False, f"Structure '{structure_id}' not found.")

        # 2. Check if structure is a valid guard post
        if not self._is_guard_post(structure):
            return (False, f"Structure '{structure_id}' is not a guard post.")

        # 3. Check if structure already has an NPC assigned (one guard per structure)
        if structure.assigned_npc_id is not None:
            return (
                False,
                f"Structure already assigned to NPC '{structure.assigned_npc_id}'.",
            )

        # 4. Check if NPC already has a different structure assigned
        for existing_struct_id, existing_npc_id in list(
            self.npc_assignments.items()
        ):
            if existing_npc_id == npc_id:
                old_struct_id = existing_struct_id
                # Unassign from old structure first
                old_struct = None
                for s in self.structures:
                    if s.structure_def.structure_id == old_struct_id:
                        old_struct = s
                        break
                if old_struct:
                    old_struct.assigned_npc_id = None
                del self.npc_assignments[old_struct_id]
                break

        # 5. Perform assignment
        structure.assigned_npc_id = npc_id
        self.npc_assignments[structure_id] = npc_id

        # 6. Update NPC.assigned_structure_id via game reference
        if hasattr(self, "_game_ref") and self._game_ref and self._game_ref.npc_system:
            for npc in self._game_ref.npc_system.npcs:
                if npc.npc_id == npc_id:
                    npc.assigned_structure_id = structure_id
                    break

        return (True, f"Guard assigned to {structure.structure_def.name}.")

    def unassign_npc(self, npc_id: str) -> tuple[bool, str]:
        """
        Remove an NPC's assignment to any structure.

        Args:
            npc_id: The NPC's unique identifier.

        Returns:
            (success, message) tuple.
        """
        for struct_id, assigned_npc in list(self.npc_assignments.items()):
            if assigned_npc == npc_id:
                # Find and clear structure assignment
                for s in self.structures:
                    if s.structure_def.structure_id == struct_id:
                        s.assigned_npc_id = None
                        break
                del self.npc_assignments[struct_id]

                # Clear NPC field
                if (
                    hasattr(self, "_game_ref")
                    and self._game_ref
                    and self._game_ref.npc_system
                ):
                    for npc in self._game_ref.npc_system.npcs:
                        if npc.npc_id == npc_id:
                            npc.assigned_structure_id = None
                            break

                return (True, f"Guard unassigned from structure.")
        return (False, f"No structure assigned to NPC '{npc_id}'.")

    def get_guard_posts(self) -> List[Structure]:
        """
        Return all active guard post structures.

        Guard posts: offensive structures (ballista, trebuchet) + stone_wall_tower.
        """
        guard_post_ids = {"ballista", "trebuchet", "stone_wall_tower"}
        return [
            s
            for s in self.structures
            if s.structure_def.structure_id in guard_post_ids and s.is_active
        ]

    def get_assigned_structure(self, npc_id: str) -> Optional[Structure]:
        """
        Get the Structure assigned to an NPC, or None.

        Args:
            npc_id: The NPC's unique identifier.

        Returns:
            The assigned Structure, or None if not assigned.
        """
        for struct_id, assigned_npc in self.npc_assignments.items():
            if assigned_npc == npc_id:
                for s in self.structures:
                    if s.structure_def.structure_id == struct_id:
                        return s
        return None

    def _cleanup_npc_assignment_on_removal(self, structure: Structure) -> None:
        """Clean up NPC assignment when a structure is destroyed or picked up."""
        npc_id = structure.assigned_npc_id
        if npc_id is not None:
            struct_id = structure.structure_def.structure_id
            if struct_id in self.npc_assignments:
                del self.npc_assignments[struct_id]
            structure.assigned_npc_id = None
            # Clear NPC field
            if (
                hasattr(self, "_game_ref")
                and self._game_ref
                and self._game_ref.npc_system
            ):
                for npc in self._game_ref.npc_system.npcs:
                    if npc.npc_id == npc_id:
                        npc.assigned_structure_id = None
                        break
