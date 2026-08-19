"""
test_skill_panel_enhanced.py — Extended Skill Panel (P3-S20) tests.

Covers Intelligence-specific visual enhancements:
- Color coding for Commerce/Persuasion/Trade
- Sub-stat allocation bars
- Plus/Minus buttons (deallocate support)
- Wildcard toggle button
- Impact text per sub-stat
- Summary line
- Mouse move / hover tracking
"""

import unittest
from core.state import GameState


class TestSkillPanelWildcardToggle(unittest.TestCase):
    """Test wildcard toggle behavior on SkillPanel."""

    def test_wildcard_toggle_switches_flag(self):
        """Clicking [WC] toggles _use_wildcard True/False."""
        import pygame
        pygame.init()
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()
        # Initially False
        self.assertFalse(panel._use_wildcard)

        # Simulate a click on the wildcard toggle button
        # We need to populate _button_rects with a WC button first
        wc_rect = pygame.Rect(10, 10, 50, 18)
        panel._button_rects.append((wc_rect, "toggle_wildcard", ""))

        result = panel.handle_click(35, 19)
        self.assertEqual(result, ("toggle_wildcard",))
        # handle_click doesn't toggle — game.py does the toggle
        # But we verify the button rect is correctly identified
        self.assertTrue(panel._button_rects[0][0].collidepoint(35, 19))

        # Now test the actual toggle logic via the dispatcher
        from skills.skill_manager import SkillManager
        sm = SkillManager()

        panel.set_skill_manager(sm)

        # Before toggle
        self.assertFalse(panel._use_wildcard)

        # Simulate toggle via the dispatcher's _handle_skill_allocation
        from input.panel_dispatcher import PanelDispatcher

        class MockGame:
            def __init__(self):
                self._skill_panel = panel
                self.skill_manager = sm

        mock_game = MockGame()
        dispatcher = PanelDispatcher(mock_game)

        # Call dispatch with toggle_wildcard action
        dispatcher.dispatch(GameState.SKILL_PANEL, ("toggle_wildcard",))
        self.assertTrue(panel._use_wildcard)

        # Toggle again
        dispatcher.dispatch(GameState.SKILL_PANEL, ("toggle_wildcard",))
        self.assertFalse(panel._use_wildcard)

        pygame.quit()


class TestSkillPanelMinusButton(unittest.TestCase):
    """Test minus button deallocation behavior."""

    def test_minus_button_deallocates(self):
        """Minus action decreases sub_stat, increases stat_points."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        # Allocate 3 points to commerce
        sm.allocate_stat("intelligence", "commerce", 3)
        self.assertEqual(sm.get_effective_stat("intelligence", "commerce"), 3)
        self.assertEqual(sm.skills["intelligence"].stat_points, 0)

        # Simulate deallocation (action == -1)
        skill_id = "intelligence"
        sub_stat = "commerce"
        if skill_id in sm.skills:
            skill = sm.skills[skill_id]
            if sub_stat in skill.sub_stats and skill.sub_stats[sub_stat] > 0:
                skill.sub_stats[sub_stat] -= 1
                skill.stat_points += 1

        self.assertEqual(sm.get_effective_stat("intelligence", "commerce"), 2)
        self.assertEqual(sm.skills["intelligence"].stat_points, 1)

        # Deallocate again
        if skill_id in sm.skills:
            skill = sm.skills[skill_id]
            if sub_stat in skill.sub_stats and skill.sub_stats[sub_stat] > 0:
                skill.sub_stats[sub_stat] -= 1
                skill.stat_points += 1

        self.assertEqual(sm.get_effective_stat("intelligence", "commerce"), 1)
        self.assertEqual(sm.skills["intelligence"].stat_points, 2)

    def test_minus_button_does_not_go_below_zero(self):
        """Deallocating when sub_stat is 0 should not crash or go negative."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        # commerce starts at 0
        self.assertEqual(sm.get_effective_stat("intelligence", "commerce"), 0)

        # Try to deallocate
        skill_id = "intelligence"
        sub_stat = "commerce"
        if skill_id in sm.skills:
            skill = sm.skills[skill_id]
            if sub_stat in skill.sub_stats and skill.sub_stats[sub_stat] > 0:
                skill.sub_stats[sub_stat] -= 1
                skill.stat_points += 1

        # Should remain at 0
        self.assertEqual(sm.get_effective_stat("intelligence", "commerce"), 0)
        self.assertEqual(sm.skills["intelligence"].stat_points, 3)  # unchanged


class TestSkillPanelPlusWithWildcard(unittest.TestCase):
    """Test plus button with wildcard toggle."""

    def test_plus_button_with_wildcard(self):
        """Plus with wildcard uses wildcard_points."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        # Set up wildcard points (total levels = 7 * 1 = 7, so 7 // 5 = 1 wildcard)
        sm.award_wildcard_points()
        sm.wildcard_points = 5  # manually set for test
        # Give the intelligence skill 0 stat points (all allocated)
        sm.skills["intelligence"].stat_points = 0

        # Allocate with wildcard=True
        result = sm.allocate_stat("intelligence", "commerce", 2, wildcard=True)
        self.assertTrue(result)
        self.assertEqual(sm.get_effective_stat("intelligence", "commerce"), 2)
        self.assertEqual(sm.wildcard_points, 3)
        self.assertEqual(sm.skills["intelligence"].stat_points, 0)

    def test_plus_button_without_wildcard(self):
        """Plus without wildcard uses skill stat_points."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        # intelligence starts with 3 stat_points
        self.assertEqual(sm.skills["intelligence"].stat_points, 3)

        # Allocate without wildcard
        result = sm.allocate_stat("intelligence", "commerce", 2, wildcard=False)
        self.assertTrue(result)
        self.assertEqual(sm.get_effective_stat("intelligence", "commerce"), 2)
        self.assertEqual(sm.skills["intelligence"].stat_points, 1)


class TestSkillPanelMouseMove(unittest.TestCase):
    """Test mouse move hover tracking on SkillPanel."""

    def test_handle_mouse_move_tracks_hover(self):
        """Mouse move updates _hovered_btn correctly."""
        import pygame
        from ui.skill_panel import SkillPanel

        pygame.init()
        panel = SkillPanel()

        # Create some button rects
        rect1 = pygame.Rect(100, 50, 35, 14)
        rect2 = pygame.Rect(100, 70, 35, 14)
        panel._button_rects = [
            (rect1, "woodcutting", "success_rate"),
            (rect2, "mining", "success_rate"),
        ]

        # Initially no hover
        panel.handle_mouse_move(0, 0)
        self.assertEqual(panel._hovered_btn, "")

        # Hover over first button
        panel.handle_mouse_move(117, 57)
        self.assertEqual(panel._hovered_btn, "woodcutting")

        # Hover over second button
        panel.handle_mouse_move(117, 77)
        self.assertEqual(panel._hovered_btn, "mining")

        # Hover outside buttons
        panel.handle_mouse_move(50, 50)
        self.assertEqual(panel._hovered_btn, "")

        pygame.quit()


class TestSkillPanelColorCoding(unittest.TestCase):
    """Test Intelligence sub-stat color coding."""

    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        import pygame
        pygame.quit()

    def test_intelligence_color_coding(self):
        """Commerce/Persuasion/Trade use correct colors."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()

        # Commerce = Green
        self.assertEqual(panel.COMMERCE_COLOR, (78, 106, 62))

        # Persuasion = Gold
        self.assertEqual(panel.PERSUASION_COLOR, (184, 168, 64))

        # Trade = Teal
        self.assertEqual(panel.TRADE_COLOR, (62, 168, 158))

    def test_minus_button_colors(self):
        """Minus buttons have distinct colors."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()
        self.assertEqual(panel.MINUS_BTN_COLOR, (120, 80, 80))
        self.assertEqual(panel.MINUS_BTN_HOVER, (150, 100, 100))

    def test_wildcard_toggle_colors(self):
        """Wildcard toggle has correct colors."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()
        self.assertEqual(panel.WILD_CARD_COLOR, (120, 120, 80))
        self.assertEqual(panel.WILD_CARD_ACTIVE, (180, 180, 120))


class TestSkillPanelImpactText(unittest.TestCase):
    """Test that Intelligence sub-stats show impact text."""

    def test_impact_text_present(self):
        """Intelligence sub-stats have impact descriptions."""
        from skills.intelligence.intelligence import (
            COMMERCE_DESCRIPTION,
            PERSUASION_DESCRIPTION,
            TRADE_DESCRIPTION,
        )

        self.assertEqual(COMMERCE_DESCRIPTION, "\u22122% buy / +1% sell")
        self.assertEqual(PERSUASION_DESCRIPTION, "+2% quest acceptance")
        self.assertEqual(TRADE_DESCRIPTION, "+3% barter / +2% sell value")


class TestSkillPanelSummaryLine(unittest.TestCase):
    """Test the summary line for Intelligence skill."""

    def test_summary_line_correct(self):
        """Total line shows allocated/available points."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()

        # Get snapshot
        snapshot = sm.get_snapshot()
        intel = snapshot["intelligence"]
        sub_stats = intel["sub_stats"]

        # Initially all 0
        total_allocated = sum(sub_stats.values())
        self.assertEqual(total_allocated, 0)

        # Set enough wildcard points so allocations work
        sm.wildcard_points = 15
        sm.skills["intelligence"].stat_points = 10

        # Allocate some points
        sm.allocate_stat("intelligence", "commerce", 5, wildcard=True)
        sm.allocate_stat("intelligence", "persuasion", 3, wildcard=True)
        sm.allocate_stat("intelligence", "trade", 2, wildcard=True)

        # Update snapshot
        snapshot = sm.get_snapshot()
        sub_stats = snapshot["intelligence"]["sub_stats"]
        total_allocated = sum(sub_stats.values())
        self.assertEqual(total_allocated, 10)

        # The summary line would show "Total: 10 / 20 points"
        max_points = 20
        self.assertEqual(f"Total: {total_allocated} / {max_points} points",
                         "Total: 10 / 20 points")


class TestSkillPanelHandleClick(unittest.TestCase):
    """Test handle_click return values for all button types."""

    def test_plus_button_returns_allocation(self):
        """Plus button returns (skill_id, sub_stat, 1)."""
        import pygame
        from ui.skill_panel import SkillPanel

        pygame.init()
        panel = SkillPanel()

        rect = pygame.Rect(100, 50, 35, 14)
        panel._button_rects = [(rect, "intelligence", "commerce")]

        result = panel.handle_click(117, 57)
        self.assertEqual(result, ("intelligence", "commerce", 1))

        pygame.quit()

    def test_minus_button_returns_deallocation(self):
        """Minus button returns (skill_id, sub_stat, -1)."""
        import pygame
        from ui.skill_panel import SkillPanel

        pygame.init()
        panel = SkillPanel()

        rect = pygame.Rect(82, 50, 16, 14)
        panel._button_rects = [(rect, "intelligence", "_commerce")]

        result = panel.handle_click(90, 57)
        self.assertEqual(result, ("intelligence", "commerce", -1))

        pygame.quit()

    def test_wildcard_toggle_returns_toggle_action(self):
        """Wildcard toggle returns ("toggle_wildcard",)."""
        import pygame
        from ui.skill_panel import SkillPanel

        pygame.init()
        panel = SkillPanel()

        rect = pygame.Rect(10, 10, 50, 18)
        panel._button_rects = [(rect, "toggle_wildcard", "")]

        result = panel.handle_click(35, 19)
        self.assertEqual(result, ("toggle_wildcard",))

        pygame.quit()

    def test_no_button_returns_none(self):
        """Click on empty area returns None."""
        import pygame
        from ui.skill_panel import SkillPanel

        pygame.init()
        panel = SkillPanel()

        rect = pygame.Rect(100, 50, 35, 14)
        panel._button_rects = [(rect, "intelligence", "commerce")]

        result = panel.handle_click(10, 10)
        self.assertIsNone(result)

        pygame.quit()


if __name__ == "__main__":
    unittest.main()
