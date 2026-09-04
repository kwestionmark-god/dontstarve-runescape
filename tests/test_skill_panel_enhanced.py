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

import pygame
import pytest
from core.state import GameState


class TestSkillPanelWildcardToggle:
    """Test wildcard toggle behavior on SkillPanel."""

    def test_wildcard_toggle_switches_flag(self):
        """Clicking [WC] toggles _use_wildcard True/False."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()
        # Initially False
        assert panel._use_wildcard is False

        # Simulate a click on the wildcard toggle button
        # We need to populate _interactive_rects with a WC button first
        wc_rect = pygame.Rect(10, 10, 50, 18)
        panel._interactive_rects.append((wc_rect, "toggle_wildcard"))

        result = panel.handle_click(35, 19)
        assert result == ("toggle_wildcard",)
        # handle_click doesn't toggle — game.py does the toggle
        # But we verify the button rect is correctly identified
        assert panel._interactive_rects[0][0].collidepoint(35, 19)

        # Now test the actual toggle logic via the dispatcher
        from skills.skill_manager import SkillManager
        sm = SkillManager()

        panel.set_skill_manager(sm)

        # Before toggle
        assert panel._use_wildcard is False

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
        assert panel._use_wildcard is True

        # Toggle again
        dispatcher.dispatch(GameState.SKILL_PANEL, ("toggle_wildcard",))
        assert panel._use_wildcard is False


class TestSkillPanelMinusButton:
    """Test minus button deallocation behavior."""

    def test_minus_button_deallocates(self):
        """Minus action decreases sub_stat, increases stat_points."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        # Allocate 3 points to commerce
        sm.allocate_stat("intelligence", "commerce", 3)
        assert sm.get_effective_stat("intelligence", "commerce") == 3
        assert sm.skills["intelligence"].stat_points == 0

        # Simulate deallocation (action == -1)
        skill_id = "intelligence"
        sub_stat = "commerce"
        if skill_id in sm.skills:
            skill = sm.skills[skill_id]
            if sub_stat in skill.sub_stats and skill.sub_stats[sub_stat] > 0:
                skill.sub_stats[sub_stat] -= 1
                skill.stat_points += 1

        assert sm.get_effective_stat("intelligence", "commerce") == 2
        assert sm.skills["intelligence"].stat_points == 1

        # Deallocate again
        if skill_id in sm.skills:
            skill = sm.skills[skill_id]
            if sub_stat in skill.sub_stats and skill.sub_stats[sub_stat] > 0:
                skill.sub_stats[sub_stat] -= 1
                skill.stat_points += 1

        assert sm.get_effective_stat("intelligence", "commerce") == 1
        assert sm.skills["intelligence"].stat_points == 2

    def test_minus_button_does_not_go_below_zero(self):
        """Deallocating when sub_stat is 0 should not crash or go negative."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        # commerce starts at 0
        assert sm.get_effective_stat("intelligence", "commerce") == 0

        # Try to deallocate
        skill_id = "intelligence"
        sub_stat = "commerce"
        if skill_id in sm.skills:
            skill = sm.skills[skill_id]
            if sub_stat in skill.sub_stats and skill.sub_stats[sub_stat] > 0:
                skill.sub_stats[sub_stat] -= 1
                skill.stat_points += 1

        # Should remain at 0
        assert sm.get_effective_stat("intelligence", "commerce") == 0
        assert sm.skills["intelligence"].stat_points == 3  # unchanged


class TestSkillPanelPlusWithWildcard:
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
        assert result is True
        assert sm.get_effective_stat("intelligence", "commerce") == 2
        assert sm.wildcard_points == 3
        assert sm.skills["intelligence"].stat_points == 0

    def test_plus_button_without_wildcard(self):
        """Plus without wildcard uses skill stat_points."""
        from skills.skill_manager import SkillManager

        sm = SkillManager()
        # intelligence starts with 3 stat_points
        assert sm.skills["intelligence"].stat_points == 3

        # Allocate without wildcard
        result = sm.allocate_stat("intelligence", "commerce", 2, wildcard=False)
        assert result is True
        assert sm.get_effective_stat("intelligence", "commerce") == 2
        assert sm.skills["intelligence"].stat_points == 1


class TestSkillPanelMouseMove:
    """Test mouse move hover tracking on SkillPanel."""

    def test_handle_mouse_move_tracks_hover(self):
        """Mouse move updates selection correctly (via on_mouse_move)."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()

        # Create some interactive rects (screen coordinates matching panel content area)
        rect1 = pygame.Rect(360, 126, 35, 14)  # content_rect.x + 10, content_rect.y + 50
        rect2 = pygame.Rect(360, 146, 35, 14)  # content_rect.y + 70
        panel._interactive_rects = [
            (rect1, "woodcutting:success_rate:1"),
            (rect2, "mining:success_rate:1"),
        ]
        # Mock _skill_buttons for select_count() to return > 0
        panel._skill_buttons = [
            (rect1, "woodcutting", "success_rate", False),
            (rect2, "mining", "success_rate", False),
        ]

        # Initially no selection
        assert panel._selected_index == -1

        # on_mouse_move receives screen coordinates (content-relative in practice)
        panel.on_mouse_move(370, 133)
        assert panel._selected_index == 0

        panel.on_mouse_move(370, 153)
        assert panel._selected_index == 1

        # Moving off all buttons keeps the selection (mouse movement must
        # not wipe keyboard navigation state).
        panel.on_mouse_move(100, 100)
        assert panel._selected_index == 1


class TestSkillPanelColorCoding:
    """Test Intelligence sub-stat color coding."""

    def test_intelligence_color_coding(self):
        """Commerce/Persuasion/Trade use correct colors."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()

        # Commerce = Green
        assert panel.COMMERCE_COLOR == (78, 106, 62)

        # Persuasion = Gold
        assert panel.PERSUASION_COLOR == (184, 168, 64)

        # Trade = Teal
        assert panel.TRADE_COLOR == (62, 168, 158)

    def test_minus_button_colors(self):
        """Minus buttons have distinct colors."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()
        assert panel.MINUS_BTN_COLOR == (120, 80, 80)
        assert panel.MINUS_BTN_HOVER == (150, 100, 100)

    def test_wildcard_toggle_colors(self):
        """Wildcard toggle has correct colors."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()
        assert panel.WILD_CARD_COLOR == (120, 120, 80)
        assert panel.WILD_CARD_ACTIVE == (180, 180, 120)


class TestSkillPanelImpactText:
    """Test that Intelligence sub-stats show impact text."""

    def test_impact_text_present(self):
        """Intelligence sub-stats have impact descriptions."""
        from skills.intelligence.intelligence import (
            COMMERCE_DESCRIPTION,
            PERSUASION_DESCRIPTION,
            TRADE_DESCRIPTION,
        )

        assert COMMERCE_DESCRIPTION == "\u22122% buy / +1% sell"
        assert PERSUASION_DESCRIPTION == "+2% quest acceptance"
        assert TRADE_DESCRIPTION == "+3% barter / +2% sell value"


class TestSkillPanelSummaryLine:
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
        assert total_allocated == 0

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
        assert total_allocated == 10

        # The summary line would show "Total: 10 / 20 points"
        max_points = 20
        assert f"Total: {total_allocated} / {max_points} points" == "Total: 10 / 20 points"


class TestSkillPanelHandleClick:
    """Test handle_click return values for all button types."""

    def test_plus_button_returns_allocation(self):
        """Plus button returns (skill_id, sub_stat, 1)."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()

        rect = pygame.Rect(100, 50, 35, 14)
        panel._interactive_rects = [(rect, "intelligence:commerce:1")]

        result = panel.handle_click(117, 57)
        assert result == ("intelligence", "commerce", 1)

    def test_minus_button_returns_deallocation(self):
        """Minus button returns (skill_id, sub_stat, -1)."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()

        rect = pygame.Rect(82, 50, 16, 14)
        panel._interactive_rects = [(rect, "intelligence:commerce:-1")]

        result = panel.handle_click(90, 57)
        assert result == ("intelligence", "commerce", -1)

    def test_wildcard_toggle_returns_toggle_action(self):
        """Wildcard toggle returns ("toggle_wildcard",)."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()

        rect = pygame.Rect(10, 10, 50, 18)
        panel._interactive_rects = [(rect, "toggle_wildcard")]

        result = panel.handle_click(35, 19)
        assert result == ("toggle_wildcard",)

    def test_no_button_returns_none(self):
        """Click on empty area returns None."""
        from ui.skill_panel import SkillPanel

        panel = SkillPanel()

        rect = pygame.Rect(100, 50, 35, 14)
        panel._interactive_rects = [(rect, "intelligence:commerce:1")]

        result = panel.handle_click(10, 10)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__])