"""
character_select.py — Character/background selection UI.

Allows players to choose their character name, background, and starting
stats before beginning a new game.
"""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING, Dict, List, Tuple

from config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui.panel_window import PanelWindow
from survival.starter_pack import CharacterDefinition, get_starter_pack

from core.state import GameState

if TYPE_CHECKING:
    from core.game import Game


# Background definitions with descriptions and stat bonuses
BACKGROUND_DEFINITIONS: Dict[str, Dict] = {
    "forester": {
        "name": "Forester",
        "description": "Skilled with axe and bow. Starts with woodcutting knowledge.",
        "starter_pack": "forester",
        "stat_bonuses": {"woodcutting": {"harvest_boost": 1, "stamina": 1}},
    },
    "prospector": {
        "name": "Prospector",
        "description": "Knows the earth's secrets. Starts with mining expertise.",
        "starter_pack": "prospector",
        "stat_bonuses": {"mining": {"success_rate": 1, "extra_resources": 1}},
    },
    "scavenger": {
        "name": "Scavenger",
        "description": "Survives on what others discard. Starts with foraging skill.",
        "starter_pack": "scavenger",
        "stat_bonuses": {"foraging": {"harvest_boost": 1, "success_rate": 1}},
    },
    "default": {
        "name": "Default",
        "description": "No special background. Balanced start.",
        "starter_pack": "default",
        "stat_bonuses": {},
    },
}

# Ordered list for selection
BACKGROUND_ORDER: List[str] = ["forester", "prospector", "scavenger", "default"]


class CharacterSelectPanel(PanelWindow):
    """
    Character/background selection panel.

    Layout:
    ┌──────────────────────────────────────────┐
    │  Character Selection (ESC to cancel)     │
    ├──────────────────────────────────────────┤
    │  Name: [________________]                │
    │                                          │
    │  Select Background:                      │
    │  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
    │  │Forester │ │Prospect.│ │Scavenger│    │
    │  │[axe]    │ │[pickaxe]│ │[torch]  │    │
    │  │Wood+    │ │Min+     │ │Forag+   │    │
    │  └─────────┘ └─────────┘ └─────────┘    │
    │                                          │
    │  [START GAME]                           │
    └──────────────────────────────────────────┘
    """

    PANEL_WIDTH = 500
    PANEL_HEIGHT = 520
    CARD_WIDTH = 140
    CARD_HEIGHT = 130
    CARD_GAP = 15

    BG_COLOR = (25, 25, 35)
    BORDER_COLOR = (100, 100, 140)
    CARD_BG = (40, 40, 55)
    CARD_HOVER = (60, 60, 80)
    CARD_SELECTED = (80, 100, 60)
    BTN_COLOR = (60, 100, 160)
    BTN_HOVER = (80, 130, 200)
    TEXT_COLOR = (200, 200, 220)
    TEXT_DIM = (150, 150, 170)
    INPUT_BG = (35, 35, 45)
    INPUT_ACTIVE = (50, 50, 65)

    def __init__(self) -> None:
        super().__init__(
            title="Character Selection",
            x=(WINDOW_WIDTH - 500) // 2,
            y=30,
            width=500,
            height=520,
            title_height=26,
            footer_height=0,
            has_scrollbar=False,
            show_close=True,
            selection_mode="grid",
            grid_cols=3,
            row_gap=15,
        )
        self.visible: bool = False
        self._selected_background: str = "default"
        self._player_name: str = ""
        self._name_active: bool = False
        self._name_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._card_rects: List[Tuple[str, pygame.Rect]] = []
        self._start_btn_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._desc_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._on_confirm_callback = None

    def set_confirm_callback(self, callback) -> None:
        """Set callback when START GAME is clicked. Receives CharacterDefinition."""
        self._on_confirm_callback = callback

    def scroll_viewport(self) -> Tuple[int, int]:
        return 1, 1

    def select_count(self) -> int:
        # Name input + 3 background cards + start button
        return 5

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw character selection UI inside the clipped viewport."""
        self._interactive_rects.clear()
        self._card_rects.clear()

        left = content_rect.x + 20
        y = content_rect.y + 10

        # Player name input
        name_label = self.font_normal.render("Character Name:", True, self.TEXT_COLOR)
        screen.blit(name_label, (left, y))
        y += 22

        name_rect = pygame.Rect(left, y, content_rect.width - 40, 30)
        self._name_rect = name_rect
        bg_color = self.INPUT_ACTIVE if self._name_active else self.INPUT_BG
        pygame.draw.rect(screen, bg_color, name_rect, border_radius=3)
        pygame.draw.rect(screen, self.BORDER_COLOR, name_rect, 1, border_radius=3)

        # Render name text (or placeholder)
        display_name = self._player_name if self._player_name else "Enter name..."
        name_color = self.TEXT_COLOR if self._player_name else self.TEXT_DIM
        name_surf = self.font_normal.render(display_name, True, name_color)
        screen.blit(name_surf, (name_rect.x + 8, name_rect.y + 5))

        self._interactive_rects.append((name_rect, "name_input"))
        y += 40

        # Background selection header
        bg_label = self.font_normal.render("Select Background:", True, self.TEXT_COLOR)
        screen.blit(bg_label, (left, y))
        y += 28

        # Background cards
        total_cards_width = 3 * self.CARD_WIDTH + 2 * self.CARD_GAP
        start_x = left + (content_rect.width - 40 - total_cards_width) // 2

        for i, bg_id in enumerate(BACKGROUND_ORDER):
            if i >= 3:  # Only show 3 main backgrounds (default is hidden)
                break

            bg_def = BACKGROUND_DEFINITIONS[bg_id]
            card_x = start_x + i * (self.CARD_WIDTH + self.CARD_GAP)
            card_rect = pygame.Rect(card_x, y, self.CARD_WIDTH, self.CARD_HEIGHT)

            is_selected = bg_id == self._selected_background
            is_hovered = self._is_card_hovered(bg_id)

            if is_selected:
                card_bg = self.CARD_SELECTED
            elif is_hovered:
                card_bg = self.CARD_HOVER
            else:
                card_bg = self.CARD_BG

            pygame.draw.rect(screen, card_bg, card_rect, border_radius=5)
            pygame.draw.rect(screen, self.BORDER_COLOR, card_rect, 1, border_radius=5)

            # Background name
            name_surf = self.font_normal.render(bg_def["name"], True, self.TEXT_COLOR)
            screen.blit(name_surf, (card_rect.x + 10, card_rect.y + 8))

            # Starter item icon (text representation)
            tool, torch, food = get_starter_pack(bg_def["starter_pack"])
            items_text = f"[{tool}] + [{torch}] + [{food}]"
            items_surf = self.font_small.render(items_text, True, self.TEXT_DIM)
            screen.blit(items_surf, (card_rect.x + 10, card_rect.y + 30))

            # Stat bonuses
            bonus_y = 52
            for skill_id, bonuses in bg_def["stat_bonuses"].items():
                for sub_stat, points in bonuses.items():
                    bonus_text = f"+{points} {skill_id}.{sub_stat}"
                    bonus_surf = self.font_small.render(bonus_text, True, (150, 200, 150))
                    screen.blit(bonus_surf, (card_rect.x + 10, card_rect.y + bonus_y))
                    bonus_y += 14

            # Description
            desc_surf = self.font_small.render(bg_def["description"], True, self.TEXT_DIM)
            # Wrap description if needed
            desc_lines = self._wrap_description(bg_def["description"], self.CARD_WIDTH - 20)
            for j, line in enumerate(desc_lines[:2]):
                line_surf = self.font_small.render(line, True, self.TEXT_DIM)
                screen.blit(line_surf, (card_rect.x + 10, card_rect.y + 70 + j * 14))

            self._card_rects.append((bg_id, card_rect))
            self._interactive_rects.append((card_rect, f"background:{bg_id}"))

        y += self.CARD_HEIGHT + 20

        # Description area for selected background
        desc_label = self.font_normal.render("Background Details:", True, self.TEXT_COLOR)
        screen.blit(desc_label, (left, y))
        y += 22

        selected_def = BACKGROUND_DEFINITIONS[self._selected_background]
        desc_lines = self._wrap_description(selected_def["description"], content_rect.width - 40)
        for line in desc_lines[:3]:
            line_surf = self.font_small.render(line, True, self.TEXT_DIM)
            screen.blit(line_surf, (left + 5, y))
            y += 16

        y += 10

        # Stat bonuses summary
        if selected_def["stat_bonuses"]:
            bonus_label = self.font_normal.render("Starting Stat Bonuses:", True, self.TEXT_COLOR)
            screen.blit(bonus_label, (left, y))
            y += 20
            for skill_id, bonuses in selected_def["stat_bonuses"].items():
                for sub_stat, points in bonuses.items():
                    bonus_text = f"  +{points} {skill_id}.{sub_stat}"
                    bonus_surf = self.font_small.render(bonus_text, True, (150, 200, 150))
                    screen.blit(bonus_surf, (left + 10, y))
                    y += 16

        y += 10

        # Start button
        btn_width = 200
        btn_height = 40
        btn_x = left + (content_rect.width - 40 - btn_width) // 2
        start_rect = pygame.Rect(btn_x, y, btn_width, btn_height)
        self._start_btn_rect = start_rect

        can_start = len(self._player_name.strip()) > 0
        btn_color = self.BTN_COLOR if can_start else (60, 60, 80)
        btn_hover = self.BTN_HOVER if can_start else (60, 60, 80)

        is_btn_hovered = start_rect.collidepoint(pygame.mouse.get_pos())
        final_color = btn_hover if is_btn_hovered else btn_color

        pygame.draw.rect(screen, final_color, start_rect, border_radius=4)
        btn_text = self.font_bold.render("START GAME", True, (240, 240, 255))
        text_rect = btn_text.get_rect(center=start_rect.center)
        screen.blit(btn_text, text_rect)

        if can_start:
            self._interactive_rects.append((start_rect, "start_game"))

    def _is_card_hovered(self, bg_id: str) -> bool:
        for card_id, rect in self._card_rects:
            if card_id == bg_id and rect.collidepoint(pygame.mouse.get_pos()):
                return True
        return False

    def _wrap_description(self, text: str, max_width: int) -> List[str]:
        """Wrap text to fit within max_width."""
        words = text.split()
        if not words:
            return [""]

        lines = []
        current = words[0]
        for word in words[1:]:
            trial = current + " " + word
            if self.font_small.size(trial)[0] <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def on_key(self, key: int) -> str | None:
        """Handle keyboard input."""
        # Handle name input
        if self._name_active:
            if key == pygame.K_RETURN:
                self._name_active = False
                return None
            elif key == pygame.K_BACKSPACE:
                self._player_name = self._player_name[:-1]
                return None
            elif key == pygame.K_ESCAPE:
                self._name_active = False
                return None
            else:
                # Add character (limit to reasonable length)
                if len(self._player_name) < 20:
                    # Only allow printable characters
                    try:
                        char = pygame.key.name(key)
                        if len(char) == 1 and char.isprintable():
                            self._player_name += char
                    except Exception:
                        pass
                return None

        # Background selection with arrow keys
        if key in (pygame.K_LEFT, pygame.K_a):
            idx = BACKGROUND_ORDER.index(self._selected_background)
            self._selected_background = BACKGROUND_ORDER[(idx - 1) % 3]  # Only 3 main
            return None
        if key in (pygame.K_RIGHT, pygame.K_d):
            idx = BACKGROUND_ORDER.index(self._selected_background)
            self._selected_background = BACKGROUND_ORDER[(idx + 1) % 3]
            return None

        if key == pygame.K_TAB:
            self._name_active = not self._name_active
            return None

        return None

    def on_click(self, x: int, y: int, button: int = 1) -> str | None:
        """Handle mouse clicks."""
        for rect, payload in self._interactive_rects:
            if rect.collidepoint(x, y):
                if payload == "name_input":
                    self._name_active = True
                    return None
                elif payload.startswith("background:"):
                    self._selected_background = payload.split(":", 1)[1]
                    return None
                elif payload == "start_game":
                    return "start_game"
        return None

    def on_mouse_move(self, mx: int, my: int) -> None:
        """Track hover for visual feedback."""
        # Selection via keyboard is not used here, hover is visual only
        pass

    def get_character_definition(self) -> CharacterDefinition:
        """Build CharacterDefinition from current selections."""
        char_def = CharacterDefinition()
        char_def.name = self._player_name.strip() or "Player"
        char_def.background = self._selected_background

        # Get starting stats from background
        bg_def = BACKGROUND_DEFINITIONS[self._selected_background]
        char_def.starting_stats = bg_def["stat_bonuses"]
        char_def.starter_pack_id = bg_def["starter_pack"]

        return char_def


def render_character_select(game: "Game", screen: pygame.Surface) -> None:
    """Render the character selection screen (title screen integration)."""
    # This function can be called from game.py during CHARACTER_SELECT state
    if game._character_select_panel:
        game._character_select_panel.render(screen)


def handle_character_select_event(game: "Game", event) -> None:
    """Handle events during CHARACTER_SELECT state."""
    if game._character_select_panel:
        result = None
        # Delegate keyboard events to the panel's handle_key method
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                # Check if we can start the game (name is non-empty)
                can_start = len(game._character_select_panel._player_name.strip()) > 0
                if can_start:
                    result = "start_game"
                else:
                    # If no name, just hide name input if active
                    game._character_select_panel._name_active = False
            else:
                result = game._character_select_panel.handle_key(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            result = game._character_select_panel.handle_click(event.pos[0], event.pos[1])
        elif event.type == pygame.MOUSEMOTION:
            game._character_select_panel.handle_mouse_move(event.pos[0], event.pos[1])
        else:
            return
        
        if result == "start_game":
            char_def = game._character_select_panel.get_character_definition()
            game._pending_character_def = char_def
            game.set_state(GameState.LOADING)