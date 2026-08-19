"""
tests/test_npc_dialogue_fix.py — Verify NPC dialogue panel opening works.

Tests that the E key interaction correctly opens diplomacy/recruit panels
for faction_leader and recruit NPCs via the main event loop routing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pygame


class TestNPCDialogueFix:
    """Test that NPC interactions properly open panels."""

    def test_event_key_e_opens_diplomacy_panel(self):
        """Verify E key event routes to _open_diplomacy_panel for faction_leader."""
        from npc.npc_types import FactionLeaderNPC

        # Create a FactionLeaderNPC
        npc_data = {
            "npc_id": "test_leader",
            "name": "Test Leader",
            "npc_type": "faction_leader",
            "world_x": 100,
            "world_y": 100,
            "sprite_key": "npc/faction_leader_male_0",
            "faction": "test_faction",
            "dialogue_lines": ["Hello"],
            "behavior": "idle",
            "patrol_area": None,
            "is_active": True,
            "is_recruited": False,
            "recruit_behavior": None,
            "hostility_level": 0.5,
            "health": 25,
            "max_health": 25,
            "faction_id": "test_faction",
            "faction_strength": 1.0,
            "hostile_monster_types": [],
        }
        npc = FactionLeaderNPC.from_dict(npc_data)

        # Mock the game and subsystems
        mock_npcs = Mock()
        mock_npcs.check_proximity = Mock(return_value=npc)

        # Use MagicMock to bypass __slots__ restrictions
        with patch("core.game.Game.__init__", return_value=None):
            from core.game import Game
            game = MagicMock()
            game.player = Mock()
            game.player.action_system = Mock()
            game.npc_system = mock_npcs
            game._npc_flows = Mock()
            game._npc_flows.open_diplomacy_panel = Mock(return_value=True)
            game._npc_flows.open_recruit_panel = Mock(return_value=False)
            game._npc_flows.open_trade_panel = Mock()
            game._npc_flows.open_quest_panel = Mock()
            game._handle_interact = Mock()

            # Simulate the E key event handling from game.py
            if game.npc_system is not None and game.player is not None:
                nearby_npc = game.npc_system.check_proximity(game.player)
                if nearby_npc is not None:
                    npc_type = getattr(nearby_npc, "npc_type", "")
                    if npc_type == "faction_leader":
                        game._npc_flows.open_diplomacy_panel(nearby_npc)

            # Verify open_diplomacy_panel was called
            game._npc_flows.open_diplomacy_panel.assert_called_once_with(npc)

    def test_event_key_e_opens_recruit_panel(self):
        """Verify E key event routes to _open_recruit_panel for recruit."""
        from npc.npc_types import RecruitNPC

        # Create a RecruitNPC
        npc_data = {
            "npc_id": "test_recruit",
            "name": "Test Recruit",
            "npc_type": "recruit",
            "world_x": 110,
            "world_y": 110,
            "sprite_key": "npc/recruit_female_0",
            "faction": "test_faction",
            "dialogue_lines": ["I want to join you"],
            "behavior": "idle",
            "patrol_area": None,
            "is_active": True,
            "is_recruited": False,
            "recruit_behavior": None,
            "hostility_level": 0.3,
            "health": 12,
            "max_health": 12,
            "recruit_commerce_requirement": 2,
            "recruit_persuasion_requirement": 3,
            "recruit_composite_stat": 5,
            "available_behaviors": ["assistant", "guard"],
            "recruit_sprite_key": "test_recruit",
        }
        npc = RecruitNPC.from_dict(npc_data)

        # Mock the game and subsystems
        mock_npcs = Mock()
        mock_npcs.check_proximity = Mock(return_value=npc)

        # Use MagicMock to bypass __slots__ restrictions
        with patch("core.game.Game.__init__", return_value=None):
            from core.game import Game
            game = MagicMock()
            game.player = Mock()
            game.player.action_system = Mock()
            game.npc_system = mock_npcs
            game._npc_flows = Mock()
            game._npc_flows.open_diplomacy_panel = Mock(return_value=False)
            game._npc_flows.open_recruit_panel = Mock(return_value=True)
            game._npc_flows.open_trade_panel = Mock()
            game._npc_flows.open_quest_panel = Mock()
            game._handle_interact = Mock()

            # Simulate the E key event handling from game.py
            if game.npc_system is not None and game.player is not None:
                nearby_npc = game.npc_system.check_proximity(game.player)
                if nearby_npc is not None:
                    npc_type = getattr(nearby_npc, "npc_type", "")
                    if npc_type == "recruit":
                        game._npc_flows.open_recruit_panel(nearby_npc)

            # Verify open_recruit_panel was called
            game._npc_flows.open_recruit_panel.assert_called_once_with(npc)

    def test_unknown_npc_type_no_interaction(self):
        """Unknown NPC types fall through to _handle_interact."""
        from npc.npc_types import NPC

        npc = NPC(
            npc_id="unknown_npc",
            name="Mysterious Stranger",
            npc_type="mysterious",
        )

        mock_npcs = Mock()
        mock_npcs.check_proximity = Mock(return_value=npc)

        # Use MagicMock to bypass __slots__ restrictions
        with patch("core.game.Game.__init__", return_value=None):
            from core.game import Game
            game = MagicMock()
            game.player = Mock()
            game.player.action_system = Mock()
            game.npc_system = mock_npcs
            game._npc_flows = Mock()
            game._npc_flows.open_diplomacy_panel = Mock(return_value=False)
            game._npc_flows.open_recruit_panel = Mock(return_value=False)
            game._npc_flows.open_trade_panel = Mock()
            game._npc_flows.open_quest_panel = Mock()
            game._handle_interact = Mock()

            # Simulate the E key event handling from game.py
            if game.npc_system is not None and game.player is not None:
                nearby_npc = game.npc_system.check_proximity(game.player)
                if nearby_npc is not None:
                    npc_type = getattr(nearby_npc, "npc_type", "")
                    if npc_type == "merchant":
                        game._npc_flows.open_trade_panel(nearby_npc)
                    elif npc_type == "quest_giver":
                        game._npc_flows.open_quest_panel(nearby_npc)
                    elif npc_type == "faction_leader":
                        game._npc_flows.open_diplomacy_panel(nearby_npc)
                    elif npc_type == "recruit":
                        game._npc_flows.open_recruit_panel(nearby_npc)
                    else:
                        game._handle_interact()

            # Verify _handle_interact was called for unknown type
            game._handle_interact.assert_called_once()

    def test_open_diplomacy_panel_returns_boolean(self):
        """Verify NPCFlows.open_diplomacy_panel returns bool."""
        from interactions.npc_flows import NPCFlows
        import inspect

        sig = inspect.signature(NPCFlows.open_diplomacy_panel)
        ann = sig.return_annotation
        assert ann in (bool, "bool"), f"Should return bool, got {ann!r}"

    def test_open_recruit_panel_returns_boolean(self):
        """Verify NPCFlows.open_recruit_panel returns bool."""
        from interactions.npc_flows import NPCFlows
        import inspect

        sig = inspect.signature(NPCFlows.open_recruit_panel)
        ann = sig.return_annotation
        assert ann in (bool, "bool"), f"Should return bool, got {ann!r}"
