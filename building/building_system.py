"""
building/building_system.py — Building engine.

Manages structure placement, removal, pickup, and validation.
Integrates with inventory for material consumption and with
Construction for sub-stat checks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

from config import TILE_SIZE


def _tile_coords(world_x: float, world_y: float) -> Tuple[int, int]:
    """Convert world pixel coordinates to tile coordinates."""
    return (int(world_x // TILE_SIZE), int(world_y // TILE_SIZE))

if TYPE_CHECKING:
    from skills.skill_manager import SkillManager
    from inventory.inventory import Inventory

from building.item_drop import ItemDrop
from building.structure import Structure, StructureDef, StructureDefRegistry
from skills.construction.construction import Construction

# Type alias for backward compatibility
StructureDefsDict = Dict[str, Dict[str, StructureDef]]
StructureDefsSource = Union[StructureDefsDict, StructureDefRegistry]


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
        "item_drops",
        "_game_ref",
        "_next_instance_id",
    )

    def __init__(
        self,
        skill_manager: SkillManager,
        inventory: Inventory,
        construction: Construction,
        structure_defs: StructureDefsSource,
        game_ref: object | None = None,
    ) -> None:
        self.skill_manager: SkillManager = skill_manager
        self.construction: Construction = construction
        self.structures: List[Structure] = []
        self.inventory: Inventory = inventory
        self.structure_defs: StructureDefsSource = structure_defs
        self.item_drops: List[ItemDrop] = []

        # NPC-structure assignments: structure instance_id → npc_id
        self.npc_assignments: Dict[int, str] = {}
        self._game_ref: object | None = game_ref
        self._next_instance_id: int = 1

    def _get_structure_def(self, category: str, structure_id: str) -> Optional[StructureDef]:
        """Get a structure definition by category and ID, works with both dict and registry."""
        if isinstance(self.structure_defs, StructureDefRegistry):
            return self.structure_defs.get_structure(category, structure_id)
        return self.structure_defs.get(category, {}).get(structure_id)

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
        target_tile = _tile_coords(world_x, world_y)
        for existing in self.structures:
            if _tile_coords(existing.world_x, existing.world_y) == target_tile:
                return BuildResult(success=False, message="Tile already occupied.")

        # 2b. Check if player or NPCs occupy the target tile
        if self._game_ref is not None:
            player = getattr(self._game_ref, "player", None)
            if player is not None:
                if _tile_coords(player.world_x, player.world_y) == target_tile:
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
                        if _tile_coords(npc_x, npc_y) == target_tile:
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
        structure.instance_id = self._next_instance_id
        self._next_instance_id += 1

        self.structures.append(structure)

        # Grant Construction XP based on structure complexity.
        # Construction sub-stats live under the Crafting skill, so XP is
        # granted through the crafting skill (mirrors combat granting combat XP).
        xp_gained = self._calculate_construction_xp(struct_def)
        if xp_gained > 0:
            self.skill_manager.add_xp("crafting", xp_gained)

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
        Pick up a portable structure, refunding materials per the shared
        building-tech return rule (portable = 100%).

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

        # Return rate comes from the shared building-tech rule
        # (portable = 100%, fixed = 50%, defensive = 30%).
        return_rate = self.construction.get_material_return_rate(structure.structure_def)

        materials_returned: List[Tuple[str, int]] = []
        for item_id, qty in structure.structure_def.materials:
            returned_qty = max(1, int(qty * return_rate))
            if not self.inventory.add_item(item_id, returned_qty):
                # Inventory full - drop remaining items on the ground
                drop = ItemDrop(
                    item_id=item_id,
                    quantity=returned_qty,
                    world_x=structure.world_x,
                    world_y=structure.world_y,
                    lifetime=300.0,
                    created_at=0.0,
                )
                self.item_drops.append(drop)
            else:
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
        Destroy/demolish a structure (0% material return).

        Args:
            structure: The structure to remove.

        Returns:
            RemoveResult with no materials returned.
        """
        # Demolition returns 0% of materials
        return_rate = 0.0

        # Clean up NPC assignment when structure is destroyed
        self._cleanup_npc_assignment_on_removal(structure)
        self.structures.remove(structure)

        return RemoveResult(
            success=True,
            materials_returned=[],
            message=f"Demolished {structure.structure_def.name}.",
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

        # Only structures actually near the monster can be attacked
        # (1.5 tiles); monsters must not damage structures map-wide.
        max_range = TILE_SIZE * 1.5

        # Find the closest structure to the monster
        best = None
        best_dist = float("inf")
        for s in self.structures:
            dist = math.sqrt((s.world_x - monster_world_x) ** 2 + (s.world_y - monster_world_y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = s

        if best is None or best_dist > max_range:
            return None

        destroyed = best.take_damage(monster_attack)

        if destroyed:
            # Drop partial materials on the ground as ItemDrop entities
            return_rate = self.construction.get_material_return_rate(best.structure_def)
            for item_id, qty in best.structure_def.materials:
                returned_qty = max(1, int(qty * return_rate))
                drop = ItemDrop(
                    item_id=item_id,
                    quantity=returned_qty,
                    world_x=best.world_x,
                    world_y=best.world_y,
                    lifetime=300.0,  # 5 minutes
                    created_at=0.0,
                )
                self.item_drops.append(drop)
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
        target_tile = _tile_coords(world_x, world_y)
        result = []
        for s in self.structures:
            if _tile_coords(s.world_x, s.world_y) == target_tile:
                result.append(s)
        return result

    def get_all_structures(self) -> List[Structure]:
        """Return all structures."""
        return list(self.structures)

    def get_item_drops_near(
        self, player_x: float, player_y: float, radius: float = 64.0
    ) -> List[ItemDrop]:
        """
        Return item drops within pickup range of the player.

        Args:
            player_x: Player's X position.
            player_y: Player's Y position.
            radius: Pickup radius in pixels (default 1 tile).

        Returns:
            List of ItemDrop entities within range.
        """
        result = []
        for drop in self.item_drops:
            dx = drop.world_x - player_x
            dy = drop.world_y - player_y
            if dx * dx + dy * dy <= radius * radius:
                result.append(drop)
        return result

    def pickup_item_drop(self, drop: ItemDrop) -> bool:
        """
        Pick up an item drop, adding it to inventory.

        Args:
            drop: The ItemDrop to pick up.

        Returns:
            True if picked up successfully, False if inventory full.
        """
        if not self.inventory.add_item(drop.item_id, drop.quantity):
            return False
        if drop in self.item_drops:
            self.item_drops.remove(drop)
        return True

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
            structure.fire_timer -= dt
            if structure.fire_timer > 0:
                continue

            # Find nearest monster to this offensive structure
            best_monster = None
            best_dist_sq = float("inf")
            attack_range = 200.0 if struct_id == "ballista" else 300.0  # px
            attack_range_sq = attack_range * attack_range

            if hasattr(combat_system, "get_alive_monsters_in_radius"):
                candidates = combat_system.get_alive_monsters_in_radius(
                    structure.world_x, structure.world_y, attack_range,
                )
            else:
                candidates = [m for m in combat_system.monsters if m.is_alive()]
            for monster in candidates:
                dx = monster.world_x - structure.world_x
                dy = monster.world_y - structure.world_y
                dist_sq = dx * dx + dy * dy
                if dist_sq <= attack_range_sq and dist_sq < best_dist_sq:
                    best_dist_sq = dist_sq
                    best_monster = monster

            if best_monster is None:
                structure.fire_timer = cooldown
                continue

            from skills.building_tech import calculate_offensive_damage

            # Calculate damage using shared formula
            if struct_id == "ballista":
                base_damage = 5
                multiplier = 2
            else:  # trebuchet
                base_damage = 10
                multiplier = 3

            damage = calculate_offensive_damage(base_damage, multiplier, self.skill_manager)

            # Delegate damage handling to CombatSystem
            combat_system.offensive_structure_hit(structure, best_monster, damage)

            structure.fire_timer = cooldown

        # Update item drops: tick lifetime and remove expired
        self.item_drops = [drop for drop in self.item_drops if not drop.tick(dt)]

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
        # 1. Find the first UNASSIGNED structure of that type (a second
        # ballista of the same type must remain assignable).
        structure = None
        for s in self.structures:
            if (
                s.structure_def.structure_id == structure_id
                and s.assigned_npc_id is None
            ):
                structure = s
                break
        if structure is None:
            return (False, f"Structure '{structure_id}' not found (or all assigned).")

        # 2. Check if structure is a valid guard post
        if not self._is_guard_post(structure):
            return (False, f"Structure '{structure_id}' is not a guard post.")

        # 3. Check if NPC already has a different structure assigned
        for existing_key, existing_npc_id in list(
            self.npc_assignments.items()
        ):
            if existing_npc_id == npc_id:
                old_struct = self._structure_by_instance_key(existing_key)
                if old_struct:
                    old_struct.assigned_npc_id = None
                del self.npc_assignments[existing_key]
                break

        # 4. Perform assignment (keyed by instance so same-type structures
        # are independent)
        key = self._instance_key(structure)
        structure.assigned_npc_id = npc_id
        self.npc_assignments[key] = npc_id

        # 5. Update NPC.assigned_structure_id via game reference
        if hasattr(self, "_game_ref") and self._game_ref and self._game_ref.npc_system:
            for npc in self._game_ref.npc_system.npcs:
                if npc.npc_id == npc_id:
                    npc.assigned_structure_id = key
                    break

        return (True, f"Guard assigned to {structure.structure_def.name}.")

    @staticmethod
    def _instance_key(structure: Structure) -> str:
        """Assignment key: '<structure_id>#<instance_id>' (unique per structure)."""
        return f"{structure.structure_def.structure_id}#{structure.instance_id}"

    def _structure_by_instance_key(self, key: str) -> Optional[Structure]:
        """Resolve an assignment key back to its Structure instance."""
        for s in self.structures:
            if self._instance_key(s) == key:
                return s
        return None

    def unassign_npc(self, npc_id: str) -> tuple[bool, str]:
        """
        Remove an NPC's assignment to any structure.

        Args:
            npc_id: The NPC's unique identifier.

        Returns:
            (success, message) tuple.
        """
        for struct_key, assigned_npc in list(self.npc_assignments.items()):
            if assigned_npc == npc_id:
                # Find and clear structure assignment
                struct = self._structure_by_instance_key(struct_key)
                if struct is not None:
                    struct.assigned_npc_id = None
                del self.npc_assignments[struct_key]

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
        for struct_key, assigned_npc in self.npc_assignments.items():
            if assigned_npc == npc_id:
                return self._structure_by_instance_key(struct_key)
        return None

    def _cleanup_npc_assignment_on_removal(self, structure: Structure) -> None:
        """Clean up NPC assignment when a structure is destroyed or picked up."""
        npc_id = structure.assigned_npc_id
        if npc_id is not None:
            key = self._instance_key(structure)
            if key in self.npc_assignments:
                del self.npc_assignments[key]
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
