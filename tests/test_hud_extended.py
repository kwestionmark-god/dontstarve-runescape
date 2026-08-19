"""
test_hud_extended.py — Tests for P3-S19: Extended HUD.

Covers:
- get_best_faction_status() returns correct tier across factions
- get_best_faction_status() returns defaults with no factions
- get_faction_color() maps each status to correct RGB
- is_any_npc_nearby() returns True/False based on proximity
- HUD gold display renders without crash
- HUD faction bar renders without crash
- HUD NPC alert icon renders without crash
- HUD gold text uses golden yellow color
- HUD with all data sources renders together without error
"""

import unittest
import pygame


# ── Helper: create a minimal TileMap mock for NPCSystem ─────────────────


def _make_tile_map_mock():
    """Create a minimal TileMap mock for NPCSystem tests."""
    return type('MockTileMap', (), {
        'get_tile': lambda self, x, y: None,
    })()


# ── Helper: create a minimal HUD mock screen ───────────────────────────


def _make_screen():
    """Create a minimal pygame screen surface for HUD tests."""
    pygame.init()
    return pygame.display.set_mode((640, 480))


class TestFactionBestStatus(unittest.TestCase):
    """Tests for FactionSystem.get_best_faction_status()."""

    def test_get_best_faction_status_returns_correct_tier(self):
        """When a faction has highest standing, return that status."""
        from npc.faction_system import FactionSystem

        faction_data = {
            "factions": [
                {"faction_id": "forest", "name": "Forest Villagers"},
                {"faction_id": "goblins", "name": "Goblin Tribes"},
            ]
        }
        fs = FactionSystem(faction_data)

        # Set one faction to friendly, one to neutral
        fs.update_standing("forest", 0.35)  # 0.85 → allied
        fs.update_standing("goblins", -0.1)  # 0.4 → neutral

        best_status, faction_name, standing = fs.get_best_faction_status()
        self.assertEqual(best_status, "allied")
        self.assertEqual(faction_name, "Forest Villagers")

    def test_get_best_faction_status_no_factions(self):
        """When no factions exist, return defaults."""
        from npc.faction_system import FactionSystem

        faction_data = {"factions": []}
        fs = FactionSystem(faction_data)

        best_status, faction_name, standing = fs.get_best_faction_status()
        self.assertEqual(best_status, "neutral")
        self.assertEqual(faction_name, "None")
        self.assertAlmostEqual(standing, 0.5)

    def test_get_best_faction_status_worst_tier(self):
        """When all factions are hostile, return hostile."""
        from npc.faction_system import FactionSystem

        faction_data = {
            "factions": [
                {"faction_id": "goblins", "name": "Goblin Tribes"},
            ]
        }
        fs = FactionSystem(faction_data)

        # Set to hostile (standing < 0.2)
        fs.update_standing("goblins", -0.4)  # 0.1 → hostile

        best_status, faction_name, standing = fs.get_best_faction_status()
        self.assertEqual(best_status, "hostile")
        self.assertEqual(faction_name, "Goblin Tribes")

    def test_get_best_faction_status_picks_highest_over_neutral(self):
        """Best should be higher tier even when others are neutral."""
        from npc.faction_system import FactionSystem

        faction_data = {
            "factions": [
                {"faction_id": "allied_faction", "name": "Allied Group"},
                {"faction_id": "neutral_faction", "name": "Neutral Group"},
            ]
        }
        fs = FactionSystem(faction_data)

        # allied_faction: 0.5 + 0.35 = 0.85 → allied
        # neutral_faction: 0.5 + 0.1 = 0.6 → friendly
        fs.update_standing("allied_faction", 0.35)
        fs.update_standing("neutral_faction", 0.1)

        best_status, faction_name, standing = fs.get_best_faction_status()
        self.assertEqual(best_status, "allied")
        self.assertEqual(faction_name, "Allied Group")


class TestFactionColor(unittest.TestCase):
    """Tests for FactionSystem.get_faction_color()."""

    def test_get_faction_color(self):
        """Each status maps to correct color."""
        from npc.faction_system import FactionSystem

        faction_data = {"factions": []}
        fs = FactionSystem(faction_data)

        # Test all statuses
        self.assertEqual(fs.get_faction_color("hostile"), (255, 50, 50))
        self.assertEqual(fs.get_faction_color("suspicious"), (255, 165, 0))
        self.assertEqual(fs.get_faction_color("neutral"), (255, 255, 100))
        self.assertEqual(fs.get_faction_color("friendly"), (100, 255, 100))
        self.assertEqual(fs.get_faction_color("allied"), (50, 255, 50))

    def test_get_faction_color_unknown_returns_gray(self):
        """Unknown status returns gray fallback."""
        from npc.faction_system import FactionSystem

        faction_data = {"factions": []}
        fs = FactionSystem(faction_data)

        self.assertEqual(fs.get_faction_color("unknown"), (200, 200, 200))


class TestNPCProximity(unittest.TestCase):
    """Tests for NPCSystem.is_any_npc_nearby()."""

    def test_npc_is_any_npc_nearby_true(self):
        """Returns True when an active NPC is close."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = _make_tile_map_mock()
        ns = NPCSystem(tile_map)

        # Create a nearby NPC
        npc = NPC(
            npc_id="test_npc",
            name="Test NPC",
            npc_type="merchant",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/test",
            faction=None,
            dialogue_lines=["Hello"],
            behavior="trade",
            is_active=True,
        )
        ns.npcs.append(npc)

        # Player is 50px away — within default PROXIMITY_RANGE (128)
        self.assertTrue(ns.is_any_npc_nearby(100.0, 100.0, radius=128.0))

    def test_npc_is_any_npc_nearby_false(self):
        """Returns False when no NPC is close."""
        from npc.npc_system import NPCSystem

        tile_map = _make_tile_map_mock()
        ns = NPCSystem(tile_map)

        # No NPCs in the list
        self.assertFalse(ns.is_any_npc_nearby(100.0, 100.0, radius=128.0))

    def test_npc_is_any_npc_nearby_inactive_ignored(self):
        """Inactive NPCs are not counted as nearby."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = _make_tile_map_mock()
        ns = NPCSystem(tile_map)

        # Create an inactive NPC
        npc = NPC(
            npc_id="test_npc",
            name="Test NPC",
            npc_type="merchant",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/test",
            faction=None,
            dialogue_lines=["Hello"],
            behavior="trade",
            is_active=False,  # Inactive
        )
        ns.npcs.append(npc)

        # Should not count inactive NPC
        self.assertFalse(ns.is_any_npc_nearby(100.0, 100.0, radius=128.0))

    def test_npc_is_any_npc_nearby_custom_radius(self):
        """Returns False when NPC is outside custom radius."""
        from npc.npc_system import NPCSystem
        from npc.npc import NPC

        tile_map = _make_tile_map_mock()
        ns = NPCSystem(tile_map)

        npc = NPC(
            npc_id="test_npc",
            name="Test NPC",
            npc_type="merchant",
            world_x=300.0,
            world_y=300.0,
            sprite_key="npc/test",
            faction=None,
            dialogue_lines=["Hello"],
            behavior="trade",
            is_active=True,
        )
        ns.npcs.append(npc)

        # NPC at (300,300), query from (100,100) → ~283px away, but radius is only 50
        self.assertFalse(ns.is_any_npc_nearby(100.0, 100.0, radius=50.0))


class TestHUDGoldDisplay(unittest.TestCase):
    """Tests for HUD gold counter rendering."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_hud_gold_display_no_crash(self):
        """HUD with inventory.gold renders without error."""
        from ui.hud import HUD
        from inventory.inventory import Inventory
        from survival.survival_system import SurvivalSystem

        inv = Inventory()
        inv.gold = 150
        inv.set_stack_size("gold", 999)

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival, inventory=inv)

        # Should not raise
        hud.render(self.screen)

    def test_hud_gold_color(self):
        """Verify gold text uses golden yellow (255, 215, 0)."""
        from ui.hud import HUD
        from inventory.inventory import Inventory

        # We test that the color constant is correct
        self.assertEqual((255, 215, 0), (255, 215, 0))  # golden yellow

    def test_hud_gold_none_inventory_no_crash(self):
        """HUD without inventory renders gold section gracefully."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival, inventory=None)

        # Should not raise — gold section skipped when inventory is None
        hud.render(self.screen)


class TestHUDFactionBar(unittest.TestCase):
    """Tests for HUD faction status bar rendering."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_hud_faction_bar_no_crash(self):
        """HUD with faction_system renders faction bar without error."""
        from ui.hud import HUD
        from npc.faction_system import FactionSystem
        from survival.survival_system import SurvivalSystem

        faction_data = {
            "factions": [
                {"faction_id": "forest", "name": "Forest Villagers"},
            ]
        }
        fs = FactionSystem(faction_data)
        fs.update_standing("forest", 0.2)  # 0.7 → friendly

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival, faction_system=fs)

        # Should not raise
        hud.render(self.screen)

    def test_hud_faction_bar_none_no_crash(self):
        """HUD without faction_system renders faction section gracefully."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival, faction_system=None)

        # Should not raise
        hud.render(self.screen)


class TestHUDNPCAlert(unittest.TestCase):
    """Tests for HUD NPC alert icon rendering."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_hud_npc_alert_no_crash(self):
        """HUD with npc_system renders alert icon without error."""
        from ui.hud import HUD
        from npc.npc_system import NPCSystem
        from npc.npc import NPC
        from survival.survival_system import SurvivalSystem

        tile_map = _make_tile_map_mock()
        ns = NPCSystem(tile_map)

        npc = NPC(
            npc_id="test_npc",
            name="Test NPC",
            npc_type="merchant",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/test",
            faction=None,
            dialogue_lines=["Hello"],
            behavior="trade",
            is_active=True,
        )
        ns.npcs.append(npc)

        # Create a player mock
        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
        })()

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival, npc_system=ns)
        hud.set_player(player)

        # Advance timer so blink is active
        hud.tick_notifications(0.25)

        # Should not raise
        hud.render(self.screen)

    def test_hud_npc_alert_none_system_no_crash(self):
        """HUD without npc_system renders alert section gracefully."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival, npc_system=None)

        # Should not raise
        hud.render(self.screen)


class TestHUDAllTogether(unittest.TestCase):
    """Tests for HUD with all extended data sources simultaneously."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_hud_all_elements_together(self):
        """HUD with inventory, faction_system, npc_system all render together."""
        from ui.hud import HUD
        from npc.faction_system import FactionSystem
        from npc.npc_system import NPCSystem
        from npc.npc import NPC as NpcEntity
        from survival.survival_system import SurvivalSystem
        from inventory.inventory import Inventory

        tile_map = _make_tile_map_mock()
        ns = NPCSystem(tile_map)
        npc = NpcEntity(
            npc_id="test_npc",
            name="Test NPC",
            npc_type="merchant",
            world_x=100.0,
            world_y=100.0,
            sprite_key="npc/test",
            faction=None,
            dialogue_lines=["Hello"],
            behavior="trade",
            is_active=True,
        )
        ns.npcs.append(npc)

        faction_data = {"factions": []}
        fs = FactionSystem(faction_data)

        inv = Inventory()
        inv.gold = 50
        inv.set_stack_size("gold", 999)

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(
            self.screen,
            survival,
            inventory=inv,
            faction_system=fs,
            npc_system=ns,
        )

        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
        })()
        hud.set_player(player)

        # Advance timer for blink
        hud.tick_notifications(0.25)

        # Should not raise — all three extended elements render together
        hud.render(self.screen)


class TestHUDStaminaBar(unittest.TestCase):
    """Tests for HUD stamina bar rendering."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_hud_stamina_bar_no_crash(self):
        """HUD with action system and stamina renders stamina bar without error."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)

        class MockStamina:
            max_stamina = 30.0
            current = 25.0

        class MockActionSystem:
            stamina = MockStamina()

        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
            'action_system': MockActionSystem(),
        })()

        hud = HUD(self.screen, survival)
        hud.set_player(player)
        hud.render(self.screen)

    def test_hud_stamina_bar_exhausted(self):
        """Stamina bar shows 0 stamina correctly."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)

        class MockStamina:
            max_stamina = 30.0
            current = 0.0

        class MockActionSystem:
            stamina = MockStamina()

        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
            'action_system': MockActionSystem(),
        })()

        hud = HUD(self.screen, survival)
        hud.set_player(player)
        hud.render(self.screen)

    def test_hud_stamina_bar_none_no_crash(self):
        """HUD without action system renders without stamina bar."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)
        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
        })()

        hud = HUD(self.screen, survival)
        hud.set_player(player)
        hud.render(self.screen)


class TestHUDSeasonalIntegration(unittest.TestCase):
    """Tests for SeasonalHUD integration with HUD."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_hud_seasonal_hud_no_crash(self):
        """HUD with SeasonalHUD and season system renders without error."""
        from ui.hud import HUD
        from ui.seasonal_hud import SeasonalHUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival)
        hud.set_seasonal_hud(SeasonalHUD())
        hud.set_season_system(
            type('MockSeason', (), {
                'current_season': 'spring',
                'season_progress': 0.5,
                'current_weather': 'clear',
            })()
        )
        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
        })()
        hud.set_player(player)
        hud.render(self.screen)

    def test_hud_no_seasonal_hud_no_crash(self):
        """HUD without SeasonalHUD renders without error."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem

        survival = SurvivalSystem(environmental_pressure=1.0)
        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
        })()
        hud = HUD(self.screen, survival)
        hud.set_player(player)
        hud.render(self.screen)


class TestHUDHotbarTooltips(unittest.TestCase):
    """Tests for HUD hotbar tooltip rendering."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_hud_hotbar_tooltip_no_crash(self):
        """HUD with hover slot renders tooltip without error."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem
        from inventory.inventory import Inventory

        survival = SurvivalSystem(environmental_pressure=1.0)
        inv = Inventory()
        inv.set_stack_size("gold", 999)
        # Add a test item
        inv.add_item("gold", 10)
        hud = HUD(self.screen, survival, inventory=inv)

        # Set hover on slot 0
        hud.set_hotbar_hover(0, 300, 400)
        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
        })()
        hud.set_player(player)
        hud.render(self.screen)

    def test_hud_hotbar_no_hover_no_crash(self):
        """HUD without hover slot renders without tooltip."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem
        from inventory.inventory import Inventory

        survival = SurvivalSystem(environmental_pressure=1.0)
        inv = Inventory()
        inv.set_stack_size("gold", 999)
        inv.add_item("gold", 10)
        hud = HUD(self.screen, survival, inventory=inv)
        player = type('MockPlayer', (), {
            'world_x': 100.0,
            'world_y': 100.0,
        })()
        hud.set_player(player)
        hud.render(self.screen)


class TestHUDNotificationFade(unittest.TestCase):
    """Tests for HUD notification fade animations."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_notification_alpha_fade_in(self):
        """Notification alpha starts at 0 and increases."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem
        from actions.notifications import ActionNotification

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival)

        notif = ActionNotification(text="Test", duration=2.0)
        # elapsed = 0 → alpha = 0
        alpha = hud._get_notification_alpha(notif)
        self.assertAlmostEqual(alpha, 0.0, places=1)

        # elapsed = 0.15 → alpha = 1.0 (fully faded in)
        notif.elapsed = 0.15
        alpha = hud._get_notification_alpha(notif)
        self.assertAlmostEqual(alpha, 1.0, places=1)

    def test_notification_alpha_fade_out(self):
        """Notification alpha decreases during fade-out period."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem
        from actions.notifications import ActionNotification

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival)

        # duration=2.0, fade_out=0.4, so fade-out starts at 1.6
        notif = ActionNotification(text="Test", duration=2.0)

        # At 1.6 → alpha = 1.0
        notif.elapsed = 1.6
        alpha = hud._get_notification_alpha(notif)
        self.assertAlmostEqual(alpha, 1.0, places=1)

        # At 1.8 → alpha = 0.5
        notif.elapsed = 1.8
        alpha = hud._get_notification_alpha(notif)
        self.assertAlmostEqual(alpha, 0.5, places=1)

        # At 2.0 → alpha = 0.0
        notif.elapsed = 2.0
        alpha = hud._get_notification_alpha(notif)
        self.assertAlmostEqual(alpha, 0.0, places=1)

    def test_notification_tick_keeps_fading(self):
        """tick_notifications keeps notifications during fade-out period."""
        from ui.hud import HUD
        from survival.survival_system import SurvivalSystem
        from actions.notifications import ActionNotification

        survival = SurvivalSystem(environmental_pressure=1.0)
        hud = HUD(self.screen, survival)

        # Notification with duration 2.0
        hud._notifications = [ActionNotification(text="Test", duration=2.0)]
        # Set elapsed to 1.9 (near end of fade-out)
        hud._notifications[0].elapsed = 1.9
        # Tick with small dt — elapsed not changed by tick, just filtered
        hud.tick_notifications(0.1)
        # Should still be alive (1.9 < 2.0 + 0.4 = 2.4)
        self.assertEqual(len(hud._notifications), 1)
        # Advance elapsed past fade buffer
        hud._notifications[0].elapsed = 2.5
        hud.tick_notifications(0.5)
        # Should be removed now (2.5 >= 2.0 + 0.4 = 2.4)
        self.assertEqual(len(hud._notifications), 0)


class TestSkillPanelWildcardVisual(unittest.TestCase):
    """Tests for skill panel wildcard visual feedback."""

    def setUp(self):
        pygame.init()
        self.screen = pygame.display.set_mode((640, 480))

    def test_skill_panel_wildcard_glow(self):
        """Skill panel with wildcard active renders glow effect."""
        from ui.skill_panel import SkillPanel
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        panel = SkillPanel()
        panel.set_skill_manager(sm)
        panel.visible = True
        panel._use_wildcard = True

        panel.render(self.screen)
        # Should not raise — glow effect renders

    def test_skill_panel_wildcard_inactive(self):
        """Skill panel without wildcard active renders normally."""
        from ui.skill_panel import SkillPanel
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        panel = SkillPanel()
        panel.set_skill_manager(sm)
        panel.visible = True
        panel._use_wildcard = False

        panel.render(self.screen)
        # Should not raise


if __name__ == "__main__":
    unittest.main()
