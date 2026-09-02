"""
ui/title_screen.py — Title screen rendering and event handling.

Extracted from core.game.Game in Phase 3.5.8.
"""

from __future__ import annotations

import pygame
import math
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.game import Game

from config import FLAVOR_TEXTS, WINDOW_WIDTH, WINDOW_HEIGHT
from core.state import GameState
from render.font_cache import get_monospace, get_monospace_bold, get_monospace_italic


# Title screen particle system for ambient atmosphere
class TitleParticle:
    """Simple particle for title screen ambiance."""
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size")
    
    def __init__(self, x: float, y: float, vx: float, vy: float, color: tuple, size: float):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = random.uniform(0.5, 1.0)
        self.max_life = self.life
        self.color = color
        self.size = size
    
    def update(self, dt: float) -> bool:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 10 * dt  # Gentle gravity
        self.life -= dt
        return self.life > 0
    
    def draw(self, screen: pygame.Surface) -> None:
        alpha = int(255 * (self.life / self.max_life))
        color = (*self.color[:3], alpha)
        surf = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
        pygame.draw.circle(surf, color, (int(self.size), int(self.size)), int(self.size))
        screen.blit(surf, (int(self.x - self.size), int(self.y - self.size)))


class TitleScreenState:
    """Manages title screen state including particles and animations."""
    
    def __init__(self):
        self.particles: list[TitleParticle] = []
        self.time = 0.0
        self.logo_bob = 0.0
        self._init_particles()
    
    def _init_particles(self) -> None:
        # Create initial ambient particles
        for _ in range(30):
            x = random.uniform(0, WINDOW_WIDTH)
            y = random.uniform(0, WINDOW_HEIGHT)
            vx = random.uniform(-5, 5)
            vy = random.uniform(-15, -5)
            color = random.choice([
                (180, 140, 80),   # Gold
                (120, 100, 60),   # Bronze
                (200, 180, 120),  # Pale gold
            ])
            size = random.uniform(1.5, 3.5)
            self.particles.append(TitleParticle(x, y, vx, vy, color, size))
    
    def update(self, dt: float) -> None:
        self.time += dt
        self.logo_bob = math.sin(self.time * 1.5) * 4
        
        # Update particles
        self.particles = [p for p in self.particles if p.update(dt)]
        
        # Spawn new particles occasionally
        if random.random() < 0.02:
            x = random.uniform(0, WINDOW_WIDTH)
            y = WINDOW_HEIGHT + 10
            vx = random.uniform(-10, 10)
            vy = random.uniform(-25, -15)
            color = random.choice([
                (180, 140, 80),
                (120, 100, 60),
                (200, 180, 120),
            ])
            size = random.uniform(1.5, 3.5)
            self.particles.append(TitleParticle(x, y, vx, vy, color, size))
    
    def draw(self, screen: pygame.Surface) -> None:
        for p in self.particles:
            p.draw(screen)


# Global title screen state
_title_state: TitleScreenState | None = None


def _get_title_state() -> TitleScreenState:
    global _title_state
    if _title_state is None:
        _title_state = TitleScreenState()
    return _title_state


def render_title_screen(game: "Game", screen: pygame.Surface) -> None:
    """
    Render the title screen UI with animated background and polished UI.
    
    Args:
        game: The Game instance (provides seed, save_system).
        screen: The pygame display surface.
    """
    state = _get_title_state()
    
    # Dark gradient background
    _draw_gradient_background(screen)
    
    # Draw ambient particles
    state.draw(screen)
    
    # Decorative corner accents
    _draw_corner_accents(screen, state.time)
    
    # Game title / logo
    _draw_title(screen, state)
    
    # Subtitle / tagline
    _draw_subtitle(screen, state)
    
    # Seed display
    _draw_seed_display(game, screen)
    
    # Save slots
    _draw_save_slots(game, screen)
    
    # Menu buttons
    _draw_menu_buttons(game, screen, state)
    
    # Version / credits
    _draw_footer(screen)
    
    # Flavor text
    _draw_flavor_text(game, screen)


def _draw_gradient_background(screen: pygame.Surface) -> None:
    """Draw a subtle gradient background."""
    width, height = screen.get_size()
    # Create gradient surface
    for y in range(height):
        # Dark blue-black gradient with slight warmth at top
        ratio = y / height
        r = int(15 + ratio * 10)
        g = int(12 + ratio * 8)
        b = int(20 + ratio * 15)
        pygame.draw.line(screen, (r, g, b), (0, y), (width, y))


def _draw_corner_accents(screen: pygame.Surface, time: float) -> None:
    """Draw decorative corner accents that pulse gently."""
    width, height = screen.get_size()
    pulse = (math.sin(time * 0.8) + 1) * 0.5  # 0 to 1
    
    accent_color = (180, 140, 80, int(60 + pulse * 40))
    
    # Top-left corner
    _draw_corner_bracket(screen, 40, 40, 1, 1, accent_color)
    # Top-right corner
    _draw_corner_bracket(screen, width - 40, 40, -1, 1, accent_color)
    # Bottom-left corner
    _draw_corner_bracket(screen, 40, height - 40, 1, -1, accent_color)
    # Bottom-right corner
    _draw_corner_bracket(screen, width - 40, height - 40, -1, -1, accent_color)


def _draw_corner_bracket(screen: pygame.Surface, x: int, y: int, dx: int, dy: int, color) -> None:
    """Draw a decorative bracket at a corner."""
    length = 40
    thickness = 2
    # Horizontal
    pygame.draw.line(screen, color[:3], (x, y), (x + dx * length, y), thickness)
    # Vertical
    pygame.draw.line(screen, color[:3], (x, y), (x, y + dy * length), thickness)


def _draw_title(screen: pygame.Surface, state: TitleScreenState) -> None:
    """Draw the main game title with bob animation."""
    width = screen.get_width()
    y_pos = 140 + state.logo_bob
    
    # Title shadow
    font = get_monospace_bold(56)
    shadow_surf = font.render("Don't Starve RuneScape", True, (20, 15, 10))
    shadow_rect = shadow_surf.get_rect(center=(width // 2 + 3, y_pos + 3))
    screen.blit(shadow_surf, shadow_rect)
    
    # Main title with gradient-like effect
    title_surf = font.render("Don't Starve RuneScape", True, (220, 190, 130))
    title_rect = title_surf.get_rect(center=(width // 2, y_pos))
    screen.blit(title_surf, title_rect)
    
    # Subtle highlight on top
    highlight_surf = font.render("Don't Starve RuneScape", True, (255, 230, 180))
    highlight_rect = highlight_surf.get_rect(center=(width // 2, y_pos - 1))
    # Only draw top half for highlight effect
    screen.blit(highlight_surf, highlight_rect, area=pygame.Rect(0, 0, highlight_surf.get_width(), highlight_surf.get_height() // 2))


def _draw_subtitle(screen: pygame.Surface, state: TitleScreenState) -> None:
    """Draw the subtitle/tagline."""
    width = screen.get_width()
    y_pos = 200 + state.logo_bob * 0.5
    
    font = get_monospace_italic(18)
    pulse = (math.sin(state.time * 2) + 1) * 0.5
    alpha = int(140 + pulse * 60)
    color = (160, 140, 100, alpha)
    
    sub_surf = font.render("A survival adventure in a procedurally generated world", True, color[:3])
    sub_rect = sub_surf.get_rect(center=(width // 2, y_pos))
    screen.blit(sub_surf, sub_rect)


def _draw_seed_display(game: "Game", screen: pygame.Surface) -> None:
    """Draw the world seed display."""
    width = screen.get_width()
    y_pos = 250
    
    font = get_monospace(16)
    seed_text = f"World Seed: {game.seed}"
    seed_surf = font.render(seed_text, True, (120, 110, 90))
    seed_rect = seed_surf.get_rect(center=(width // 2, y_pos))
    screen.blit(seed_surf, seed_rect)


def _draw_save_slots(game: "Game", screen: pygame.Surface) -> None:
    """Draw available save slots."""
    if not game.save_system:
        return
    
    # Populate save slots
    game._save_slots = game.save_system.list_slots()
    if not game._save_slots:
        return
    
    width = screen.get_width()
    y_start = 280
    
    font = get_monospace(14)
    label_surf = font.render("Available Saves:", True, (140, 130, 110))
    label_rect = label_surf.get_rect(center=(width // 2, y_start))
    screen.blit(label_surf, label_rect)
    
    for i, slot in enumerate(game._save_slots[:3]):  # Show max 3
        y = y_start + 22 + i * 20
        if slot.get("exists"):
            slot_text = f"  Slot {slot['slot']}: Day {slot.get('day', 1)} • {slot.get('playtime', '0:00')}"
            color = (160, 150, 120)
        else:
            slot_text = f"  Slot {slot['slot']}: Empty"
            color = (80, 75, 65)
        slot_surf = font.render(slot_text, True, color)
        slot_rect = slot_surf.get_rect(center=(width // 2, y))
        screen.blit(slot_surf, slot_rect)


def _draw_menu_buttons(game: "Game", screen: pygame.Surface, state: TitleScreenState) -> None:
    """Draw the main menu buttons."""
    width = screen.get_width()
    y_start = 420
    
    font = get_monospace_bold(22)
    hint_font = get_monospace(16)
    
    # New Game button
    btn_y = y_start
    btn_color = (70, 110, 160)
    pulse = (math.sin(state.time * 3) + 1) * 0.5
    btn_color = tuple(min(255, c + int(pulse * 30)) for c in btn_color)
    
    new_game_surf = font.render("NEW GAME", True, (240, 240, 255))
    new_game_rect = new_game_surf.get_rect(center=(width // 2, btn_y))
    # Button background
    bg_rect = new_game_rect.inflate(40, 16)
    pygame.draw.rect(screen, btn_color, bg_rect, border_radius=6)
    pygame.draw.rect(screen, (120, 160, 220), bg_rect, 2, border_radius=6)
    screen.blit(new_game_surf, new_game_rect)
    
    # Continue hint
    continue_y = btn_y + 50
    continue_surf = hint_font.render("Press ENTER or SPACE", True, (140, 160, 200))
    continue_rect = continue_surf.get_rect(center=(width // 2, continue_y))
    screen.blit(continue_surf, continue_rect)
    
    # Continue button (if saves exist)
    if game._save_slots and any(s.get("exists") for s in game._save_slots):
        cont_y = continue_y + 35
        cont_color = (80, 140, 80)
        cont_surf = font.render("CONTINUE", True, (220, 255, 220))
        cont_rect = cont_surf.get_rect(center=(width // 2, cont_y))
        bg_rect = cont_rect.inflate(40, 16)
        pygame.draw.rect(screen, cont_color, bg_rect, border_radius=6)
        pygame.draw.rect(screen, (120, 200, 120), bg_rect, 2, border_radius=6)
        screen.blit(cont_surf, cont_rect)
        
        key_hint = hint_font.render("Press C", True, (140, 200, 140))
        key_rect = key_hint.get_rect(center=(width // 2, cont_y + 30))
        screen.blit(key_hint, key_rect)
    else:
        # Show disabled continue
        cont_y = continue_y + 35
        cont_surf = font.render("CONTINUE", True, (80, 80, 80))
        cont_rect = cont_surf.get_rect(center=(width // 2, cont_y))
        bg_rect = cont_rect.inflate(40, 16)
        pygame.draw.rect(screen, (50, 50, 50), bg_rect, border_radius=6)
        pygame.draw.rect(screen, (70, 70, 70), bg_rect, 2, border_radius=6)
        screen.blit(cont_surf, cont_rect)
        
        key_hint = hint_font.render("Press C (requires existing save)", True, (80, 80, 80))
        key_rect = key_hint.get_rect(center=(width // 2, cont_y + 30))
        screen.blit(key_hint, key_rect)
    
    # Quit hint
    quit_y = cont_y + 60 if 'cont_y' in locals() else continue_y + 85
    quit_surf = hint_font.render("Press ESC to Quit", True, (100, 90, 80))
    quit_rect = quit_surf.get_rect(center=(width // 2, quit_y))
    screen.blit(quit_surf, quit_rect)


def _draw_footer(screen: pygame.Surface) -> None:
    """Draw version and credits at bottom."""
    width, height = screen.get_size()
    font = get_monospace(12)
    version_surf = font.render("v0.1.0-alpha  |  Don't Starve RuneScape Fan Project", True, (60, 55, 50))
    version_rect = version_surf.get_rect(center=(width // 2, height - 20))
    screen.blit(version_surf, version_rect)


def _draw_flavor_text(game: "Game", screen: pygame.Surface) -> None:
    """Draw rotating flavor text at bottom."""
    if not hasattr(game, "_flavor_text") or not game._flavor_text:
        rng = random.Random(game.seed + int(pygame.time.get_ticks() / 10000))
        game._flavor_text = rng.choice(FLAVOR_TEXTS)
    
    width, height = screen.get_size()
    font = get_monospace_italic(13)
    flavor_surf = font.render(game._flavor_text, True, (100, 90, 80))
    flavor_rect = flavor_surf.get_rect(center=(width // 2, height - 45))
    screen.blit(flavor_surf, flavor_rect)


def handle_title_event(game: "Game", event) -> None:
    """Handle events during the TITLE state."""
    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            game.set_state(GameState.CHARACTER_SELECT)
        elif event.key == pygame.K_c:
            if game._save_slots and any(s.get("exists") for s in game._save_slots):
                game.set_state(GameState.LOADING_SAVE)
        elif event.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
