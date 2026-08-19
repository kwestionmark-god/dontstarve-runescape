"""
tests/test_extended_input.py — Verify P3-S21 extended input flags and handlers.

Covers:
- F1: New InputState flags initialized to False
- F2: E key sets interact + interact_npc (continuous + pressed)
- F3: Enter/Space sets trade_accept, quest_accept, faction_negotiate (continuous + pressed)
- F4: clear_frame clears all _pressed flags
- F5: _on_key_up clears Enter/Space confirm flags
- F6: _update_held_state re-evaluates movement / orbit / tilt from _held_keys
"""

import unittest
import pygame


class InputStateNewFlagsInitialized(unittest.TestCase):
    """F1: New P3-S21 InputState flags initialized to False."""

    def _fresh_manager(self):
        """Helper to return a pristine InputManager."""
        from input import InputManager

        pygame.init()  # ensure constants available
        manager = InputManager()
        # Drain initial events just to keep pygame clean (harmless).
        manager.input_state.clear_frame()
        return manager

    # ---- interact_npc continuous flags ----

    def test_interact_npc_initialized_false(self):
        """InputState.interact_npc must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.interact_npc)

    def test_interact_npc_pressed_initialized_false(self):
        """InputState.interact_npc_pressed must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.interact_npc_pressed)

    # ---- trade_confirm continuous flags ----

    def test_trade_accept_initialized_false(self):
        """InputState.trade_accept must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.trade_accept)

    def test_trade_accept_pressed_initialized_false(self):
        """InputState.trade_accept_pressed must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.trade_accept_pressed)

    # ---- quest_confirm flags ----

    def test_quest_accept_initialized_false(self):
        """InputState.quest_accept must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.quest_accept)

    def test_quest_accept_pressed_initialized_false(self):
        """InputState.quest_accept_pressed must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.quest_accept_pressed)

    # ---- faction_confirm flags ----

    def test_faction_negotiate_initialized_false(self):
        """InputState.faction_negotiate must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.faction_negotiate)

    def test_faction_negotiate_pressed_initialized_false(self):
        """InputState.faction_negotiate_pressed must be False by default."""
        m = self._fresh_manager()
        self.assertFalse(m.input_state.faction_negotiate_pressed)

    # ---- total flag count sanity ----

    def test_all_new_flags_false_on_fresh_state(self):
        """All 8 new P3-S21 flags must be False on a fresh InputState."""
        m = self._fresh_manager()
        s = m.input_state
        flags = [
            s.interact_npc, s.interact_npc_pressed,
            s.trade_accept, s.trade_accept_pressed,
            s.quest_accept, s.quest_accept_pressed,
            s.faction_negotiate, s.faction_negotiate_pressed,
        ]
        self.assertEqual(sum(flags), 0, "All new flags should be False")


class InputStateEKeySetsInteractNPC(unittest.TestCase):
    """F2: E key sets both interact and interact_npc flags."""

    def _fresh_manager(self):
        from input import InputManager

        pygame.init()
        return InputManager()

    def test_e_key_sets_interact(self):
        """K_e should set input_state.interact = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact)

    def test_e_key_sets_interact_pressed(self):
        """K_e should set input_state.interact_pressed = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_pressed)

    def test_e_key_sets_interact_npc(self):
        """K_e should set input_state.interact_npc = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_npc)

    def test_e_key_sets_interact_npc_pressed(self):
        """K_e should set input_state.interact_npc_pressed = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_npc_pressed)

    def test_e_key_sets_all_four_flags_together(self):
        """K_e must set interact, interact_pressed, interact_npc, interact_npc_pressed."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        s = m.input_state
        self.assertTrue(s.interact)
        self.assertTrue(s.interact_pressed)
        self.assertTrue(s.interact_npc)
        self.assertTrue(s.interact_npc_pressed)


class InputStateEnterSpaceSetsConfirmFlags(unittest.TestCase):
    """F3: Enter / Space set trade_accept, quest_accept, faction_negotiate."""

    def _fresh_manager(self):
        from input import InputManager

        pygame.init()
        return InputManager()

    # ---- Enter key ----

    def test_enter_sets_trade_accept(self):
        """K_RETURN should set trade_accept = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.trade_accept)

    def test_enter_sets_trade_accept_pressed(self):
        """K_RETURN should set trade_accept_pressed = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.trade_accept_pressed)

    def test_enter_sets_quest_accept(self):
        """K_RETURN should set quest_accept = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.quest_accept)

    def test_enter_sets_quest_accept_pressed(self):
        """K_RETURN should set quest_accept_pressed = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.quest_accept_pressed)

    def test_enter_sets_faction_negotiate(self):
        """K_RETURN should set faction_negotiate = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.faction_negotiate)

    def test_enter_sets_faction_negotiate_pressed(self):
        """K_RETURN should set faction_negotiate_pressed = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.faction_negotiate_pressed)

    def test_enter_sets_interact_npc(self):
        """K_RETURN should also set interact_npc = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_npc)

    def test_enter_sets_all_confirm_flags(self):
        """K_RETURN must set all 6 confirm / npc flags simultaneously."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        s = m.input_state
        for flag_name in ("trade_accept", "quest_accept",
                          "faction_negotiate", "interact_npc",
                          "trade_accept_pressed", "quest_accept_pressed",
                          "faction_negotiate_pressed", "interact_npc_pressed"):
            self.assertTrue(getattr(s, flag_name), flag_name)

    def test_enter_sets_interact_npc_pressed(self):
        """K_RETURN should set interact_npc_pressed = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_npc_pressed)

    # ---- Space key ----

    def test_space_sets_trade_accept(self):
        """K_SPACE should set trade_accept = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE})
        m.handle_event(event)
        self.assertTrue(m.input_state.trade_accept)

    def test_space_sets_quest_accept(self):
        """K_SPACE should set quest_accept = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE})
        m.handle_event(event)
        self.assertTrue(m.input_state.quest_accept)

    def test_space_sets_faction_negotiate(self):
        """K_SPACE should set faction_negotiate = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE})
        m.handle_event(event)
        self.assertTrue(m.input_state.faction_negotiate)

    def test_space_sets_interact_npc(self):
        """K_SPACE should also set interact_npc = True."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_npc)

    def test_space_sets_all_confirm_flags(self):
        """K_SPACE must set all 6 confirm / npc flags simultaneously."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE})
        m.handle_event(event)
        s = m.input_state
        for flag_name in ("trade_accept", "quest_accept",
                          "faction_negotiate", "interact_npc",
                          "trade_accept_pressed", "quest_accept_pressed",
                          "faction_negotiate_pressed", "interact_npc_pressed"):
            self.assertTrue(getattr(s, flag_name), flag_name)


class ClearFrameClearsPressedFlags(unittest.TestCase):
    """F4: clear_frame clears all _pressed one-shot flags."""

    def _fresh_manager(self):
        from input import InputManager

        pygame.init()
        return InputManager()

    def test_clear_frame_clears_interact_pressed(self):
        """clear_frame should clear interact_pressed."""
        m = self._fresh_manager()
        pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        # manually trigger — need a real event via handle_event
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_pressed)
        m.input_state.clear_frame()
        self.assertFalse(m.input_state.interact_pressed)

    def test_clear_frame_clears_interact_npc_pressed(self):
        """clear_frame should clear interact_npc_pressed."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        self.assertTrue(m.input_state.interact_npc_pressed)
        m.input_state.clear_frame()
        self.assertFalse(m.input_state.interact_npc_pressed)

    def test_clear_frame_clears_trade_accept_pressed(self):
        """clear_frame should clear trade_accept_pressed."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.trade_accept_pressed)
        m.input_state.clear_frame()
        self.assertFalse(m.input_state.trade_accept_pressed)

    def test_clear_frame_clears_quest_accept_pressed(self):
        """clear_frame should clear quest_accept_pressed."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.quest_accept_pressed)
        m.input_state.clear_frame()
        self.assertFalse(m.input_state.quest_accept_pressed)

    def test_clear_frame_clears_faction_negotiate_pressed(self):
        """clear_frame should clear faction_negotiate_pressed."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event)
        self.assertTrue(m.input_state.faction_negotiate_pressed)
        m.input_state.clear_frame()
        self.assertFalse(m.input_state.faction_negotiate_pressed)

    def test_clear_frame_clears_all_pressed_flags(self):
        """clear_frame must zero out all 8 _pressed flags."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e})
        m.handle_event(event)
        event2 = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(event2)
        m.input_state.clear_frame()
        s = m.input_state
        pressed_flags = [
            s.interact_pressed, s.interact_npc_pressed,
            s.trade_accept_pressed, s.quest_accept_pressed,
            s.faction_negotiate_pressed,
        ]
        self.assertEqual(sum(pressed_flags), 0, "All _pressed flags should be False")

    def test_clear_frame_preserves_held_states(self):
        """clear_frame must NOT reset held-key states (move_up, etc.)."""
        m = self._fresh_manager()
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_w})
        m.handle_event(event)
        self.assertTrue(m.input_state.move_up)
        m.input_state.clear_frame()
        self.assertTrue(m.input_state.move_up)
        self.assertTrue(m.input_state.move_up)


class OnKeyUpClearsEnterSpaceFlags(unittest.TestCase):
    """F5: _on_key_up for Enter/Space clears confirm flags + interact_npc."""

    def _fresh_manager(self):
        from input import InputManager

        pygame.init()
        return InputManager()

    def test_up_enter_clears_trade_accept(self):
        """K_RETURN release should set trade_accept = False."""
        m = self._fresh_manager()
        down = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        m.handle_event(down)
        self.assertTrue(m.input_state.trade_accept)
        up = pygame.event.Event(pygame.KEYUP, {"key": pygame.K_RETURN})
        m.handle_event(up)
        self.assertFalse(m.input_state.trade_accept)

    def test_up_enter_clears_quest_accept(self):
        """K_RETURN release should set quest_accept = False."""
        m = self._fresh_manager()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN}))
        self.assertTrue(m.input_state.quest_accept)
        m.handle_event(pygame.event.Event(pygame.KEYUP, {"key": pygame.K_RETURN}))
        self.assertFalse(m.input_state.quest_accept)

    def test_up_enter_clears_faction_negotiate(self):
        """K_RETURN release should set faction_negotiate = False."""
        m = self._fresh_manager()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN}))
        self.assertTrue(m.input_state.faction_negotiate)
        m.handle_event(pygame.event.Event(pygame.KEYUP, {"key": pygame.K_RETURN}))
        self.assertFalse(m.input_state.faction_negotiate)

    def test_up_enter_clears_interact_npc(self):
        """K_RETURN release should set interact_npc = False."""
        m = self._fresh_manager()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN}))
        self.assertTrue(m.input_state.interact_npc)
        m.handle_event(pygame.event.Event(pygame.KEYUP, {"key": pygame.K_RETURN}))
        self.assertFalse(m.input_state.interact_npc)

    def test_up_space_clears_all_confirm_flags(self):
        """K_SPACE release should clear trade/quest/faction/interact_npc."""
        m = self._fresh_manager()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE}))
        s = m.input_state
        for name in ("trade_accept", "quest_accept", "faction_negotiate",
                      "interact_npc"):
            self.assertTrue(getattr(s, name))
        m.handle_event(pygame.event.Event(pygame.KEYUP, {"key": pygame.K_SPACE}))
        for name in ("trade_accept", "quest_accept", "faction_negotiate",
                      "interact_npc"):
            self.assertFalse(getattr(s, name))

    def test_up_enter_clears_all_confirm_flags(self):
        """K_RETURN release should clear trade/quest/faction/interact_npc."""
        m = self._fresh_manager()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN}))
        s = m.input_state
        for name in ("trade_accept", "quest_accept", "faction_negotiate",
                      "interact_npc"):
            self.assertTrue(getattr(s, name))
        m.handle_event(pygame.event.Event(pygame.KEYUP, {"key": pygame.K_RETURN}))
        for name in ("trade_accept", "quest_accept", "faction_negotiate",
                      "interact_npc"):
            self.assertFalse(getattr(s, name))


class PanelToggleKeysNotInHeldState(unittest.TestCase):
    """Verify panel toggle keys (J, U, T, K, L) are NOT in _update_held_state."""

    def _fresh_manager(self):
        from input import InputManager

        pygame.init()
        return InputManager()

    def test_j_not_in_held_state(self):
        """K_j should NOT set open_skill_panel via _update_held_state()."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_j)
        m._update_held_state()
        self.assertFalse(m.input_state.open_skill_panel)

    def test_u_not_in_held_state(self):
        """K_u should NOT set open_quest_panel via _update_held_state()."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_u)
        m._update_held_state()
        self.assertFalse(m.input_state.open_quest_panel)

    def test_t_not_in_held_state(self):
        """K_t should NOT set open_trade_panel via _update_held_state()."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_t)
        m._update_held_state()
        self.assertFalse(m.input_state.open_trade_panel)

    def test_k_not_in_held_state(self):
        """K_k should NOT set open_recruit_panel via _update_held_state()."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_k)
        m._update_held_state()
        self.assertFalse(m.input_state.open_recruit_panel)

    def test_l_not_in_held_state(self):
        """K_l should NOT set open_diplomacy_panel via _update_held_state()."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_l)
        m._update_held_state()
        self.assertFalse(m.input_state.open_diplomacy_panel)


class UpdateHeldStateReEvaluates(unittest.TestCase):
    """F6: _update_held_state re-evaluates movement / orbit / tilt from _held_keys."""

    def _fresh_manager(self):
        from input import InputManager

        pygame.init()
        return InputManager()

    # ---- WASD movement ----

    def test_w_held_sets_move_up(self):
        """K_w in _held_keys → move_up = True."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_w)
        m._update_held_state()
        self.assertTrue(m.input_state.move_up)

    def test_s_held_sets_move_down(self):
        """K_s in _held_keys → move_down = True."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_s)
        m._update_held_state()
        self.assertTrue(m.input_state.move_down)

    def test_a_held_sets_move_left(self):
        """K_a in _held_keys → move_left = True."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_a)
        m._update_held_state()
        self.assertTrue(m.input_state.move_left)

    def test_d_held_sets_move_right(self):
        """K_d in _held_keys → move_right = True."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_d)
        m._update_held_state()
        self.assertTrue(m.input_state.move_right)

    def test_wasd_combined(self):
        """Holding WASD should set all four movement flags."""
        m = self._fresh_manager()
        for k in (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d):
            m._held_keys.add(k)
        m._update_held_state()
        s = m.input_state
        self.assertTrue(s.move_up)
        self.assertTrue(s.move_down)
        self.assertTrue(s.move_left)
        self.assertTrue(s.move_right)

    # ---- Arrow keys → orbit / tilt ----

    def test_left_arrow_sets_orbit_ccw(self):
        """K_LEFT in _held_keys → orbit_ccw = True."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_LEFT)
        m._update_held_state()
        self.assertTrue(m.input_state.orbit_ccw)

    def test_right_click_sets_orbit_cw(self):
        """Mouse button 3 (right-click) → orbit_cw = True."""
        m = self._fresh_manager()
        m._on_mouse_down(3, (0, 0))
        m._update_held_state()
        self.assertTrue(m.input_state.orbit_cw)

    def test_up_arrow_sets_orbit_tilt_up(self):
        """K_UP in _held_keys → orbit_tilt_up = True."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_UP)
        m._update_held_state()
        self.assertTrue(m.input_state.orbit_tilt_up)

    def test_down_arrow_sets_orbit_tilt_down(self):
        """K_DOWN in _held_keys → orbit_tilt_down = True."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_DOWN)
        m._update_held_state()
        self.assertTrue(m.input_state.orbit_tilt_down)

    def test_pageup_sets_orbit_tilt_up(self):
        """K_PAGEUP also maps to orbit_tilt_up."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_PAGEUP)
        m._update_held_state()
        self.assertTrue(m.input_state.orbit_tilt_up)

    def test_pagedown_sets_orbit_tilt_down(self):
        """K_PAGEDOWN also maps to orbit_tilt_down."""
        m = self._fresh_manager()
        m._held_keys.add(pygame.K_PAGEDOWN)
        m._update_held_state()
        self.assertTrue(m.input_state.orbit_tilt_down)


class EKeyReleasedResetsInteractAndNPCFlags(unittest.TestCase):
    """Verify K_e release resets interact, interact_pressed, interact_npc via _update_held_state."""

    def test_e_up_clears_interact_and_npc(self):
        """Releasing K_e should clear interact, interact_pressed, interact_npc."""
        from input import InputManager

        pygame.init()
        m = InputManager()
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e}))
        s = m.input_state
        self.assertTrue(s.interact)
        self.assertTrue(s.interact_pressed)
        self.assertTrue(s.interact_npc)
        m.handle_event(pygame.event.Event(pygame.KEYUP, {"key": pygame.K_e}))
        self.assertFalse(s.interact)
        self.assertFalse(s.interact_pressed)
        self.assertFalse(s.interact_npc)


if __name__ == "__main__":
    unittest.main()
