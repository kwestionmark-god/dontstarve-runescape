"""
character_select.py — Character/background selection UI.

Allows players to choose their character name, background, and starting
stats before beginning a new game.
"""

from __future__ import annotations

import pygame
import math
import random
from typing import TYPE_CHECKING, Dict, List, Tuple

from config import WINDOW_WIDTH, WINDOW_HEIGHT
from ui.panel_window import PanelWindow
from survival.starter_pack import CharacterDefinition, get_starter_pack
from render.font_cache import get_monospace, get_monospace_bold, get_monospace_italic

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
        "icon": "axe",
        "color": (100, 180, 100),
    },
    "prospector": {
        "name": "Prospector",
        "description": "Knows the earth's secrets. Starts with mining expertise.",
        "starter_pack": "prospector",
        "stat_bonuses": {"mining": {"success_rate": 1, "extra_resources": 1}},
        "icon": "pickaxe",
        "color": (180, 150, 80),
    },
    "scavenger": {
        "name": "Scavenger",
        "description": "Survives on what others discard. Starts with foraging skill.",
        "starter_pack": "scavenger",
        "stat_bonuses": {"foraging": {"harvest_boost": 1, "success_rate": 1}},
        "icon": "torch",
        "color": (180, 100, 100),
    },
    "default": {
        "name": "Default",
        "description": "No special background. Balanced start.",
        "starter_pack": "default",
        "stat_bonuses": {},
        "icon": "sword",
        "color": (150, 150, 150),
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

    PANEL_WIDTH = 540
    PANEL_HEIGHT = 560
    CARD_WIDTH = 150
    CARD_HEIGHT = 150
    CARD_GAP = 18

    BG_COLOR = (20, 20, 30)
    BORDER_COLOR = (100, 100, 140)
    CARD_BG = (35, 35, 50)
    CARD_HOVER = (55, 55, 75)
    CARD_SELECTED = (70, 100, 60)
    BTN_COLOR = (60, 100, 160)
    BTN_HOVER = (80, 130, 200)
    TEXT_COLOR = (220, 220, 230)
    TEXT_DIM = (140, 140, 160)
    INPUT_BG = (30, 30, 40)
    INPUT_ACTIVE = (45, 45, 60)

    def __init__(self) -> None:
        super().__init__(
            title="Character Selection",
            x=(WINDOW_WIDTH - 540) // 2,
            y=20,
            width=540,
            height=560,
            title_height=30,
            footer_height=0,
            has_scrollbar=False,
            show_close=True,
            selection_mode="grid",
            grid_cols=3,
            row_gap=18,
        )
        self.visible: bool = False
        self._selected_background: str = "forester"
        self._player_name: str = ""
        self._name_active: bool = False
        self._name_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._card_rects: List[Tuple[str, pygame.Rect]] = []
        self._start_btn_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._desc_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self._on_confirm_callback = None
        self._time: float = 0.0
        self._bg_particles: list[dict] = []
        self._init_bg_particles()

    def _init_bg_particles(self) -> None:
        """Initialize background particles for ambient effect."""
        for _ in range(15):
            self._bg_particles.append({
                "x": random.uniform(0, self.PANEL_WIDTH),
                "y": random.uniform(0, self.PANEL_HEIGHT),
                "vx": random.uniform(-3, 3),
                "vy": random.uniform(-8, -2),
                "life": random.uniform(0.5, 1.5),
                "max_life": random.uniform(0.5, 1.5),
                "color": random.choice([
                    (100, 180, 100, 80),
                    (180, 150, 80, 80),
                    (180, 100, 100, 80),
                    (150, 150, 150, 60),
                ]),
                "size": random.uniform(1.5, 3.0),
            })

    def set_confirm_callback(self, callback) -> None:
        """Set callback when START GAME is clicked. Receives CharacterDefinition."""
        self._on_confirm_callback = callback

    def scroll_viewport(self) -> Tuple[int, int]:
        return 1, 1

    def select_count(self) -> int:
        # Name input + 3 background cards + start button
        return 5

    def update(self, dt: float) -> None:
        """Update animations and particles."""
        self._time += dt
        
        # Update background particles
        for p in self._bg_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 5 * dt
            p["life"] -= dt
            if p["life"] <= 0:
                # Respawn at bottom
                p["x"] = random.uniform(0, self.PANEL_WIDTH)
                p["y"] = self.PANEL_HEIGHT + 10
                p["vx"] = random.uniform(-3, 3)
                p["vy"] = random.uniform(-15, -8)
                p["life"] = random.uniform(0.5, 1.5)
                p["max_life"] = p["life"]

    def draw_contents(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw character selection UI inside the clipped viewport."""
        self._interactive_rects.clear()
        self._card_rects.clear()

        # Draw background particles
        self._draw_bg_particles(screen, content_rect)

        left = content_rect.x + 20
        y = content_rect.y + 10

        # Player name input
        name_label = self.font_normal.render("Character Name:", True, self.TEXT_COLOR)
        screen.blit(name_label, (left, y))
        y += 24

        name_rect = pygame.Rect(left, y, content_rect.width - 40, 34)
        self._name_rect = name_rect
        bg_color = self.INPUT_ACTIVE if self._name_active else self.INPUT_BG
        pygame.draw.rect(screen, bg_color, name_rect, border_radius=4)
        border_color = (120, 160, 220) if self._name_active else self.BORDER_COLOR
        pygame.draw.rect(screen, border_color, name_rect, 2, border_radius=4)

        # Render name text (or placeholder)
        display_name = self._player_name if self._player_name else "Enter name..."
        name_color = self.TEXT_COLOR if self._player_name else self.TEXT_DIM
        name_surf = self.font_normal.render(display_name, True, name_color)
        screen.blit(name_surf, (name_rect.x + 10, name_rect.y + 6))

        # Blinking cursor when active
        if self._name_active and int(self._time * 2) % 2 == 0:
            cursor_x = name_rect.x + 10 + name_surf.get_width() + 2
            pygame.draw.line(screen, (200, 220, 255), (cursor_x, name_rect.y + 6), (cursor_x, name_rect.y + 26), 2)

        self._interactive_rects.append((name_rect, "name_input"))
        y += 42

        # Background selection header
        bg_label = self.font_normal.render("Select Background:", True, self.TEXT_COLOR)
        screen.blit(bg_label, (left, y))
        y += 30

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

            # Card background with selection glow
            if is_selected:
                card_bg = self.CARD_SELECTED
                # Pulsing glow
                glow_alpha = int(40 + 20 * math.sin(self._time * 4))
                glow_surf = pygame.Surface((self.CARD_WIDTH + 8, self.CARD_HEIGHT + 8), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*bg_def["color"][:3], glow_alpha), (0, 0, self.CARD_WIDTH + 8, self.CARD_HEIGHT + 8), border_radius=9)
                screen.blit(glow_surf, (card_rect.x - 4, card_rect.y - 4))
            elif is_hovered:
                card_bg = self.CARD_HOVER
            else:
                card_bg = self.CARD_BG

            pygame.draw.rect(screen, card_bg, card_rect, border_radius=6)
            border_c = bg_def["color"] if is_selected else self.BORDER_COLOR
            pygame.draw.rect(screen, border_c, card_rect, 2 if is_selected else 1, border_radius=6)

            # Background icon area
            icon_y = card_rect.y + 12
            self._draw_background_icon(screen, bg_def, card_rect.centerx, icon_y, is_selected)

            # Background name
            name_surf = self.font_bold.render(bg_def["name"], True, self.TEXT_COLOR)
            name_rect = name_surf.get_rect(centerx=card_rect.centerx, y=icon_y + 32)
            screen.blit(name_surf, name_rect)

            # Starter items
            tool, torch, food = get_starter_pack(bg_def["starter_pack"])
            items_text = f"[{tool}] + [{torch}] + [{food}]"
            items_surf = self.font_small.render(items_text, True, self.TEXT_DIM)
            items_rect = items_surf.get_rect(centerx=card_rect.centerx, y=name_rect.bottom + 6)
            screen.blit(items_surf, items_rect)

            # Stat bonuses
            bonus_y = items_rect.bottom + 8
            for skill_id, bonuses in bg_def["stat_bonuses"].items():
                for sub_stat, points in bonuses.items():
                    bonus_text = f"+{points} {skill_id}.{sub_stat}"
                    bonus_surf = self.font_small.render(bonus_text, True, (130, 200, 130))
                    bonus_rect = bonus_surf.get_rect(centerx=card_rect.centerx, y=bonus_y)
                    screen.blit(bonus_surf, bonus_rect)
                    bonus_y += 16

            self._card_rects.append((bg_id, card_rect))
            self._interactive_rects.append((card_rect, f"background:{bg_id}"))

        y += self.CARD_HEIGHT + 24

        # Description area for selected background
        self._draw_background_details(screen, content_rect, left, y)

    def _draw_bg_particles(self, screen: pygame.Surface, content_rect: pygame.Rect) -> None:
        """Draw ambient background particles."""
        clip_rect = content_rect
        for p in self._bg_particles:
            px = content_rect.x + p["x"]
            py = content_rect.y + p["y"]
            if clip_rect.collidepoint(px, py):
                alpha = int(255 * (p["life"] / p["max_life"]))
                color = (*p["color"][:3], alpha)
                surf = pygame.Surface((int(p["size"] * 2), int(p["size"] * 2)), pygame.SRCALPHA)
                pygame.draw.circle(surf, color, (int(p["size"]), int(p["size"])), int(p["size"]))
                screen.blit(surf, (int(px - p["size"]), int(py - p["size"])))

    def _draw_background_icon(self, screen: pygame.Surface, bg_def: dict, cx: int, y: int, selected: bool) -> None:
        """Draw a stylized icon for the background."""
        icon_type = bg_def["icon"]
        color = bg_def["color"] if selected else tuple(c // 2 for c in bg_def["color"][:3])
        size = 24 if selected else 20
        
        if icon_type == "axe":
            # Draw axe
            pygame.draw.rect(screen, color, (cx - 2, y, 4, size), border_radius=2)
            pygame.draw.rect(screen, color, (cx - 10, y + 2, 18, 4), border_radius=2)
        elif icon_type == "pickaxe":
            # Draw pickaxe
            pygame.draw.line(screen, color, (cx - 10, y + size), (cx + 10, y), 4)
            pygame.draw.line(screen, color, (cx, y - 2), (cx + 8, y + 8), 4)
        elif icon_type == "torch":
            # Draw torch
            pygame.draw.rect(screen, (120, 80, 40), (cx - 3, y + 4, 6, size - 4), border_radius=3)
            # Flame
            for i in range(3):
                flame_x = cx + random.randint(-4, 4)
                flame_y = y - i * 4
                flame_surf = pygame.Surface((10, 10), pygame.SRCALPHA)
                pygame.draw.circle(flame_surf, (255, 150, 50, 180), (5, 5), 5 - i)
                screen.blit(flame_surf, (flame_x - 5, flame_y - 5))
        else:  # sword/default
            pygame.draw.rect(screen, color, (cx - 2, y + 2, 4, size), border_radius=2)
            pygame.draw.rect(screen, color, (cx - 8, y, 16, 4), border_radius=2)
            pygame.draw.polygon(screen, color, [(cx, y - 6), (cx - 4, y), (cx + 4, y)])

    def _draw_background_details(self, screen: pygame.Surface, content_rect: pygame.Rect, left: int, y: int) -> None:
        """Draw detailed info for the selected background."""
        selected_def = BACKGROUND_DEFINITIONS[self._selected_background]
        
        # Description header
        desc_label = self.font_normal.render("Background Details:", True, self.TEXT_COLOR)
        screen.blit(desc_label, (left, y))
        y += 24

        # Full description (wrapped)
        desc_lines = self._wrap_description(selected_def["description"], content_rect.width - 40)
        for line in desc_lines:
            line_surf = self.font_normal.render(line, True, self.TEXT_DIM)
            screen.blit(line_surf, (left + 5, y))
            y += 20

        y += 8

        # Stat bonuses summary
        if selected_def["stat_bonuses"]:
            bonus_label = self.font_normal.render("Starting Stat Bonuses:", True, self.TEXT_COLOR)
            screen.blit(bonus_label, (left, y))
            y += 22
            for skill_id, bonuses in selected_def["stat_bonuses"].items():
                for sub_stat, points in bonuses.items():
                    bonus_text = f"  +{points} {skill_id.capitalize()}.{sub_stat.replace('_', ' ').title()}"
                    bonus_surf = self.font_small.render(bonus_text, True, (130, 200, 130))
                    screen.blit(bonus_surf, (left + 10, y))
                    y += 18

        # Starter pack preview
        y += 8
        pack_label = self.font_normal.render("Starting Equipment:", True, self.TEXT_COLOR)
        screen.blit(pack_label, (left, y))
        y += 22
        
        tool, torch, food = get_starter_pack(selected_def["starter_pack"])
        for item_name, item_color in [(tool, (180, 150, 80)), (torch, (255, 150, 50)), (food, (100, 200, 100))]:
            item_surf = self.font_small.render(f"  • {item_name}", True, item_color)
            screen.blit(item_surf, (left + 10, y))
            y += 18

        y += 10

        # Start button
        btn_width = 240
        btn_height = 48
        btn_x = left + (content_rect.width - 40 - btn_width) // 2
        start_rect = pygame.Rect(btn_x, y, btn_width, btn_height)
        self._start_btn_rect = start_rect

        can_start = len(self._player_name.strip()) > 0
        btn_color = self.BTN_COLOR if can_start else (50, 50, 60)
        btn_hover = self.BTN_HOVER if can_start else (50, 50, 60)

        is_btn_hovered = start_rect.collidepoint(pygame.mouse.get_pos())
        final_color = btn_hover if is_btn_hovered else btn_color

        # Button background with subtle gradient
        pygame.draw.rect(screen, final_color, start_rect, border_radius=6)
        # Highlight
        highlight_rect = pygame.Rect(start_rect.x, start_rect.y, start_rect.width, start_rect.height // 2)
        highlight_surf = pygame.Surface((start_rect.width, start_rect.height // 2), pygame.SRCALPHA)
        pygame.draw.rect(highlight_surf, (255, 255, 255, 30), (0, 0, start_rect.width, start_rect.height // 2), border_radius=6)
        # Only top half rounded
        screen.blit(highlight_surf, (start_rect.x, start_rect.y))
        
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
    # Draw animated background behind panel
    _draw_character_select_background(screen, game)
    
    # This function can be called from game.py during CHARACTER_SELECT state
    if game._character_select_panel:
        game._character_select_panel.update(game.dt)  # Update animations
        game._character_select_panel.render(screen)


def _draw_character_select_background(screen: pygame.Surface, game: "Game") -> None:
    """Draw animated background for character select screen."""
    # Dark gradient
    width, height = screen.get_size()
    for y in range(height):
        ratio = y / height
        r = int(18 + ratio * 12)
        g = int(15 + ratio * 10)
        b = int(25 + ratio * 15)
        pygame.draw.line(screen, (r, g, b), (0, y), (width, y))
    
    # Subtle geometric pattern
    time = pygame.time.get_ticks() / 1000.0
    for i in range(6):
        x = (width // 6) * i + int(math.sin(time + i) * 20)
        y = height // 2 + int(math.cos(time * 0.7 + i) * 40)
        alpha = int(30 + 20 * math.sin(time * 2 + i))
        color = (100, 140, 180, alpha)
        surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(surf, color, (2, 2), 2)
        screen.blit(surf, (x - 2, y - 2))
    
    # Title text
    font = get_monospace_bold(32)
    title_surf = font.render("Create Your Character", True, (200, 180, 130))
    title_rect = title_surf.get_rect(center=(width // 2, 50))
    screen.blit(title_surf, title_rect)
    
    # Subtitle
    font_small = get_monospace(16)
    sub_surf = font_small.render("Choose a background that defines your early survival strategy", True, (130, 120, 100))
    sub_rect = sub_surf.get_rect(center=(width // 2, 90))
    screen.blit(sub_surf, sub_rect)


def handle_character_select_event(game: "Game", event) -> None:
    """Handle events during CHARACTER_SELECT state."""
    if game._character_select_panel:
        result = None
        # Delegate keyboard events to the panel's handle_key method
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Close character select, return to title
                game.set_state(GameState.TITLE)
            elif event.key == pygame.K_RETURN:
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
        elif result == ("close",) or (isinstance(result, tuple) and result[0] == "close"):
            game.set_state(GameState.TITLE)