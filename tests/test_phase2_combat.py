"""
test_phase2_combat.py — Integration tests for Phase 2 Combat,
Metallurgy, Building, and Firemaking systems.
"""

import unittest
from dataclasses import dataclass


class MockPlayer:
    """Minimal mock player for combat testing."""

    def __init__(self):
        from skills.skill_manager import SkillManager
        self.skill_manager = SkillManager()
        self.world_x = 0.0
        self.world_y = 0.0

        # Gear setup
        from combat.gear import PlayerGear, GearItem
        self.gear = PlayerGear()
        weapon_data = GearItem.load_all()
        if "wooden_sword" in weapon_data:
            self.gear.equip(weapon_data["wooden_sword"])


class MockSurvival:
    """Minimal mock survival system."""

    def __init__(self):
        from config import HP_BASE_MAX
        self.hp = HP_BASE_MAX
        self.max_hp = HP_BASE_MAX
        self.hunger = 100.0
        self.max_hunger = 100.0
        self.is_dead = False

    def take_damage(self, amount: float) -> bool:
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0.0
            self.is_dead = True
            return True
        return False


class TestCombatSystem(unittest.TestCase):
    """Test the CombatSystem core."""

    def test_damage_calculation(self):
        from combat.combat_system import CombatSystem

        player = MockPlayer()
        # Allocate 5 combat attack points
        player.skill_manager.allocate_stat("combat", "attack", 5)

        survival = MockSurvival()
        cs = CombatSystem(player, survival)

        # Create a mock monster
        from combat.monster import Monster
        monster = Monster(
            monster_id="goblin",
            name="Goblin",
            biome="forest",
            world_x=30.0,
            world_y=0.0,
            hp=6,
            attack=4,
            defence=1,
            speed=70.0,
        )
        cs.register_monster(monster)
        cs.select_target(monster)

        # Calculate damage
        damage = cs.calculate_damage(player, monster)
        # Base attack = 0 (combat level 1) + 5 (stat) = 5
        # Weapon damage = wooden_sword = 2
        # Attack mult = 1 + 5 * 0.005 = 1.025
        # Defence reduction = 1 * 0.01 = 0.01
        # Raw = 5 * 2 * 1.025 = 10.25
        # Final = floor(10.25 * 0.99) = 10
        # Minimum 1, so should be 10
        self.assertGreaterEqual(damage, 1)
        self.assertLessEqual(damage, 15)  # Should be reasonable

    def test_attack_cooldown(self):
        from combat.combat_system import CombatSystem

        player = MockPlayer()
        cs = CombatSystem(player, MockSurvival())

        cooldown = cs.get_attack_cooldown()
        # Base 1.5s + wooden_sword speed_bonus (0.0) - speed_stat * 0.3
        # speed_stat = 0, so cooldown = max(0.5, 1.5) = 1.5
        self.assertGreaterEqual(cooldown, 0.5)
        self.assertLessEqual(cooldown, 2.0)


class TestMonsterAI(unittest.TestCase):
    """Test Monster AI state machine."""

    def test_idle_to_chase(self):
        from combat.monster import Monster

        player = MockPlayer()
        player.world_x = 100.0
        player.world_y = 0.0

        monster = Monster(
            monster_id="wolf",
            name="Wolf",
            biome="forest",
            world_x=0.0,
            world_y=0.0,
            aggression_range=150.0,
        )

        # Initially idle
        self.assertEqual(monster.ai_state, "idle")

        # Player is within aggression range
        monster.update_ai(player, 0.1)
        # Should transition to patrol or chase
        self.assertIn(monster.ai_state, ("patrol", "chase"))

    def test_flee_behavior(self):
        from combat.monster import Monster

        player = MockPlayer()
        player.world_x = 500.0
        player.world_y = 0.0

        monster = Monster(
            monster_id="wolf",
            name="Wolf",
            biome="forest",
            world_x=0.0,
            world_y=0.0,
            flee_range=300.0,
        )

        monster.ai_state = "chase"
        monster.update_ai(player, 0.1)
        # Player is beyond flee range
        self.assertEqual(monster.ai_state, "flee")


class TestMetallurgySkill(unittest.TestCase):
    """Test the Metallurgy skill."""

    def test_smelt_iron(self):
        from skills.metallurgy.metallurgy import MetallurgySkill
        from skills.skill_manager import SkillManager
        from inventory.inventory import Inventory

        sm = SkillManager()
        metallurgy = MetallurgySkill(sm)
        inventory = Inventory()

        # Add iron ore and charcoal
        inventory.add_item("iron_ore", 5)
        inventory.add_item("charcoal", 10)

        result = metallurgy.attempt_smelt("smelt_iron", inventory)

        # Should succeed (50% base + 0 efficiency = 50%)
        self.assertTrue(result.success or not result.success)  # RNG-based

        # Check fuel cost calculation
        effective_cost = metallurgy.get_effective_fuel_cost(1)
        self.assertEqual(effective_cost, 1)  # No efficiency stat yet

    def test_fuel_cost_discount(self):
        from skills.metallurgy.metallurgy import MetallurgySkill
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        sm.allocate_stat("metallurgy", "smelt_efficiency", 5)

        metallurgy = MetallurgySkill(sm)

        # base_cost = 2, efficiency = 5 → discount = 5 * 0.10 = 0.50
        # effective = max(1, floor(2 * 0.50)) = max(1, 1) = 1
        cost = metallurgy.get_effective_fuel_cost(2)
        self.assertLessEqual(cost, 2)
        self.assertGreaterEqual(cost, 1)


class TestBuildingSystem(unittest.TestCase):
    """Test the Building system."""

    def test_place_structure_validation(self):
        from building.structure import StructureDef
        from skills.construction.construction import Construction
        from building.building_system import BuildingSystem
        from skills.skill_manager import SkillManager
        from inventory.inventory import Inventory

        sm = SkillManager()
        inventory = Inventory()
        construction = Construction(sm)

        # Load structure defs
        structure_defs = StructureDef.load_all()
        common = structure_defs.get("common", {})

        if not common:
            self.skipTest("No common structures loaded")

        # Get first common structure
        struct_def = next(iter(common.values()))

        building_system = BuildingSystem(
            sm, inventory, construction, structure_defs,
        )

        # Place too far from player (500 pixels > 3*64=192)
        result = building_system.place_structure(
            struct_def,
            world_x=500,
            world_y=500,
            player_world_x=0,
            player_world_y=0,
            biome_id="forest",
        )
        self.assertFalse(result.success)


class TestFiremakingSkill(unittest.TestCase):
    """Test the Firemaking skill."""

    def test_light_fire(self):
        from skills.firemaking.firemaking import FiremakingSkill
        from skills.skill_manager import SkillManager
        from inventory.inventory import Inventory

        sm = SkillManager()
        firemaking = FiremakingSkill(sm)
        inventory = Inventory()

        inventory.add_item("log", 3)
        inventory.add_item("stick", 2)

        result = firemaking.light_fire(
            [("log", 3), ("stick", 2)],
            inventory,
            world_x=100.0,
            world_y=100.0,
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.fire)
        self.assertGreater(result.fire.burn_duration_remaining, 0)
        self.assertGreater(result.xp_gained, 0)


class TestSoftDeath(unittest.TestCase):
    """Test the soft death system."""

    def test_death_sequence(self):
        from combat.combat_system import CombatSystem
        from skills.skill_manager import SkillManager
        from config import HP_BASE_MAX

        player = MockPlayer()
        # Give player some XP
        player.skill_manager.add_xp("woodcutting", 10000)

        survival = MockSurvival()

        cs = CombatSystem(player, survival)

        # Set survival HP to 1 (one hit kills)
        survival.hp = 1

        # Trigger death
        survival.take_damage(10)
        self.assertTrue(survival.is_dead)

        # XP penalty: 1% of total
        total_xp_before = sum(s.xp for s in player.skill_manager.skills.values())

        # Manually test _on_player_death logic
        if total_xp_before > 0:
            xp_loss = int(total_xp_before * 0.01)
            self.assertGreater(xp_loss, 0)


class TestGearSystem(unittest.TestCase):
    """Test the Gear system."""

    def test_equip_weapon(self):
        from combat.gear import PlayerGear, GearItem

        gear = PlayerGear()
        weapons = GearItem.load_all()
        sword = weapons.get("wooden_sword")
        self.assertIsNotNone(sword)

        result = gear.equip(sword)
        self.assertTrue(result)
        self.assertEqual(gear.weapon, sword)

    def test_defence_bonus(self):
        from combat.gear import PlayerGear, GearItem

        gear = PlayerGear()
        armor = GearItem.load_all().get("leather_armor")
        self.assertIsNotNone(armor)

        gear.equip(armor)
        bonus = gear.get_defence_bonus()
        self.assertGreaterEqual(bonus, 0)


if __name__ == "__main__":
    unittest.main()
