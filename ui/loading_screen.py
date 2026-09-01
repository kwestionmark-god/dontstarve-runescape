"""
ui/loading_screen.py — Loading screen rendering and event handling.

Extracted from core.game.Game in Phase 3.5.9.
"""

from __future__ import annotations

import pygame
import random
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.game import Game

from config import FLAVOR_TEXTS, WINDOW_WIDTH, WINDOW_HEIGHT
from core.state import GameState
from render.font_cache import get_monospace, get_monospace_bold, get_monospace_italic


# Loading screen stage definitions
LOADING_STAGES = [
    (0.00, 0.10, "Initializing world generator..."),
    (0.10, 0.15, "Generating elevation map..."),
    (0.15, 0.20, "Generating moisture map..."),
    (0.20, 0.30, "Simulating hydraulic erosion..."),
    (0.30, 0.40, "Refining biome terrain..."),
    (0.40, 0.50, "Generating rivers and lakes..."),
    (0.50, 0.55, "Detecting cliffs and scree..."),
    (0.55, 0.60, "Building biome grid..."),
    (0.60, 0.65, "Baking corner heights & fog..."),
    (0.65, 0.70, "Baking ambient occlusion..."),
    (0.70, 0.75, "Precomputing fog density..."),
    (0.75, 0.85, "Building biome transitions..."),
    (0.85, 0.95, "Placing resources & veins..."),
    (0.95, 1.00, "Finalizing world..."),
]


class LoadingScreenState:
    """Manages loading screen animations and state."""
    
    def __init__(self):
        self.time = 0.0
        self.particles: list[dict] = []
        self._init_particles()
    
    def _init_particles(self) -> None:
        for _ in range(40):
            self.particles.append({
                "x": random.uniform(0, WINDOW_WIDTH),
                "y": random.uniform(0, WINDOW_HEIGHT),
                "vx": random.uniform(-8, 8),
                "vy": random.uniform(-20, -10),
                "life": random.uniform(0.5, 2.0),
                "max_life": random.uniform(0.5, 2.0),
                "color": random.choice([
                    (80, 180, 100, 100),
                    (100, 160, 200, 100),
                    (180, 150, 80, 100),
                    (160, 100, 100, 100),
                ]),
                "size": random.uniform(2.0, 4.0),
            })
    
    def update(self, dt: float) -> None:
        self.time += dt
        
        # Update particles
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 8 * dt
            p["life"] -= dt
            if p["life"] <= 0:
                p["x"] = random.uniform(0, WINDOW_WIDTH)
                p["y"] = WINDOW_HEIGHT + 20
                p["vx"] = random.uniform(-8, 8)
                p["vy"] = random.uniform(-25, -15)
                p["life"] = random.uniform(0.5, 2.0)
                p["max_life"] = p["life"]
    
    def draw(self, screen: pygame.Surface) -> None:
        for p in self.particles:
            alpha = int(255 * (p["life"] / p["max_life"]))
            color = (*p["color"][:3], alpha)
            surf = pygame.Surface((int(p["size"] * 2), int(p["size"] * 2)), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (int(p["size"]), int(p["size"])), int(p["size"]))
            screen.blit(surf, (int(p["x"] - p["size"]), int(p["y"] - p["size"])))


_loading_state: LoadingScreenState | None = None


def _get_loading_state() -> LoadingScreenState:
    global _loading_state
    if _loading_state is None:
        _loading_state = LoadingScreenState()
    return _loading_state


def _get_current_stage(progress: float) -> str:
    """Get the current loading stage description based on progress."""
    for start, end, desc in LOADING_STAGES:
        if start <= progress < end or (progress >= 1.0 and end == 1.0):
            return desc
    return "Generating world..."


def render_loading_screen(game: "Game", screen: pygame.Surface) -> None:
    """
    Render the loading screen with progress bar and stage info.
    
    Args:
        game: The Game instance (provides loading_progress, seed, state).
        screen: The pygame display surface.
    """
    state = _get_loading_state()
    state.update(1/60)  # Approximate dt for animation
    
    # Dark gradient background
    _draw_gradient_background(screen)
    
    # Draw ambient particles
    state.draw(screen)
    
    # Decorative elements
    _draw_loading_decorations(screen, state.time)
    
    # Loading title
    _draw_loading_title(screen, game, state.time)
    
    # Current stage
    _draw_loading_stage(screen, game)
    
    # Progress bar
    _draw_progress_bar(screen, game, state.time)
    
    # Flavor text
    _draw_flavor_text(game, screen)
    
    # Seed info
    _draw_seed_info(game, screen)
    
    # Tips
    _draw_loading_tip(screen, state.time)
    
    # Error state message
    if game.world is None and game.state == GameState.ERROR:
        _draw_error_message(screen)


def _draw_gradient_background(screen: pygame.Surface) -> None:
    """Draw a subtle gradient background."""
    width, height = screen.get_size()
    for y in range(height):
        ratio = y / height
        r = int(15 + ratio * 10)
        g = int(12 + ratio * 8)
        b = int(20 + ratio * 15)
        pygame.draw.line(screen, (r, g, b), (0, y), (width, y))


def _draw_loading_decorations(screen: pygame.Surface, time: float) -> None:
    """Draw decorative elements on loading screen."""
    width, height = screen.get_size()
    
    # Corner brackets with pulse
    pulse = (math.sin(time * 1.2) + 1) * 0.5
    accent_color = (100, 160, 200, int(60 + pulse * 40))
    
    # Top-left
    pygame.draw.line(screen, accent_color[:3], (50, 50), (120, 50), 3)
    pygame.draw.line(screen, accent_color[:3], (50, 50), (50, 120), 3)
    # Top-right
    pygame.draw.line(screen, accent_color[:3], (width - 50, 50), (width - 120, 50), 3)
    pygame.draw.line(screen, accent_color[:3], (width - 50, 50), (width - 50, 120), 3)
    # Bottom-left
    pygame.draw.line(screen, accent_color[:3], (50, height - 50), (120, height - 50), 3)
    pygame.draw.line(screen, accent_color[:3], (50, height - 50), (50, height - 120), 3)
    # Bottom-right
    pygame.draw.line(screen, accent_color[:3], (width - 50, height - 50), (width - 120, height - 50), 3)
    pygame.draw.line(screen, accent_color[:3], (width - 50, height - 50), (width - 50, height - 120), 3)


def _draw_loading_title(screen: pygame.Surface, game: "Game", time: float) -> None:
    """Draw the loading title with animation."""
    width = screen.get_width()
    
    # Title shadow
    font = get_monospace_bold(44)
    label = "Loading Save..." if game.state == GameState.LOADING_SAVE else "Generating World..."
    shadow_surf = font.render(label, True, (15, 12, 10))
    shadow_rect = shadow_surf.get_rect(center=(width // 2 + 2, 162))
    screen.blit(shadow_surf, shadow_rect)
    
    # Main title with subtle color shift
    color_shift = int(10 * math.sin(time * 2))
    title_color = (220 + color_shift, 190 + color_shift // 2, 130)
    title_surf = font.render(label, True, title_color)
    title_rect = title_surf.get_rect(center=(width // 2, 160))
    screen.blit(title_surf, title_rect)
    
    # Subtitle
    sub_font = get_monospace_italic(14)
    sub_text = "Procedurally generating your unique survival adventure"
    sub_surf = sub_font.render(sub_text, True, (130, 120, 100))
    sub_rect = sub_surf.get_rect(center=(width // 2, 205))
    screen.blit(sub_surf, sub_rect)


def _draw_loading_stage(screen: pygame.Surface, game: "Game") -> None:
    """Draw the current loading stage description."""
    width = screen.get_width()
    stage = _get_current_stage(game.loading_progress)
    
    font = get_monospace(16)
    # Pulse the stage text slightly
    stage_surf = font.render(stage, True, (180, 180, 200))
    stage_rect = stage_surf.get_rect(center=(width // 2, 240))
    screen.blit(stage_surf, stage_rect)


def _draw_progress_bar(screen: pygame.Surface, game: "Game", time: float) -> None:
    """Draw an animated progress bar with percentage."""
    width = screen.get_width()
    bar_width = 500
    bar_height = 28
    bar_x = (width - bar_width) // 2
    bar_y = 280
    
    # Progress bar background
    pygame.draw.rect(screen, (35, 35, 45), (bar_x, bar_y, bar_width, bar_height), border_radius=14)
    pygame.draw.rect(screen, (80, 80, 100), (bar_x, bar_y, bar_width, bar_height), 2, border_radius=14)
    
    # Progress bar fill with gradient effect
    fill_width = int(bar_width * game.loading_progress)
    if fill_width > 0:
        # Create gradient fill
        fill_surf = pygame.Surface((fill_width, bar_height), pygame.SRCALPHA)
        for x in range(fill_width):
            ratio = x / max(1, fill_width - 1)
            # Green to gold gradient
            r = int(80 + ratio * 100)
            g = int(180 + ratio * 50)
            b = int(80 - ratio * 30)
            pygame.draw.line(fill_surf, (r, g, b, 255), (x, 0), (x, bar_height))
        # Round the left side
        pygame.draw.rect(fill_surf, (0, 0, 0, 0), (0, 0, fill_width, bar_height), border_radius=14)
        # Actually draw with rounded corners by using the surface as mask
        screen.blit(fill_surf, (bar_x, bar_y))
        # Draw rounded end cap on the right side of fill
        if fill_width > bar_height:
            cap_x = bar_x + fill_width - bar_height // 2
            pygame.draw.circle(screen, (180, 230, 100), (cap_x, bar_y + bar_height // 2), bar_height // 2)
    
    # Animated shine sweep
    if game.loading_progress > 0 and game.loading_progress < 1.0:
        shine_x = bar_x + int((bar_width * 0.5) * (1 + math.sin(time * 3)))
        if bar_x < shine_x < bar_x + fill_width:
            shine_surf = pygame.Surface((60, bar_height), pygame.SRCALPHA)
            for x in range(60):
                alpha = int(80 * (1 - abs(x - 30) / 30))
                pygame.draw.line(shine_surf, (255, 255, 255, alpha), (x, 0), (x, bar_height))
            screen.blit(shine_surf, (shine_x - 30, bar_y))
    
    # Percentage text
    pct_font = get_monospace_bold(22)
    pct_text = f"{int(game.loading_progress * 100)}%"
    pct_surf = pct_font.render(pct_text, True, (255, 255, 255))
    pct_rect = pct_surf.get_rect(center=(width // 2, bar_y + bar_height + 30))
    screen.blit(pct_surf, pct_rect)
    
    # Progress segments indicators
    _draw_progress_segments(screen, bar_x, bar_y - 35, bar_width, game.loading_progress)


def _draw_progress_segments(screen: pygame.Surface, x: int, y: int, width: int, progress: float) -> None:
    """Draw small segment indicators for major loading phases."""
    segment_count = len(LOADING_STAGES)
    segment_width = width / segment_count
    
    for i, (start, end, _) in enumerate(LOADING_STAGES):
        seg_x = x + i * segment_width
        seg_center = seg_x + segment_width / 2
        seg_progress = (progress - start) / max(0.001, end - start)
        seg_progress = max(0, min(1, seg_progress))
        
        # Segment dot
        if seg_progress >= 1.0:
            color = (80, 200, 100)  # Complete
        elif seg_progress > 0:
            color = (200, 180, 80)  # In progress
        else:
            color = (70, 70, 80)  # Pending
        
        pygame.draw.circle(screen, color, (int(seg_center), y), 5)
        pygame.draw.circle(screen, (40, 40, 50), (int(seg_center), y), 5, 1)


def _draw_flavor_text(game: "Game", screen: pygame.Surface) -> None:
    """Draw rotating flavor text."""
    if not hasattr(game, "_flavor_text") or not game._flavor_text:
        rng = random.Random(game.seed)
        game._flavor_text = rng.choice(FLAVOR_TEXTS)
    
    width, height = screen.get_size()
    font = get_monospace_italic(15)
    flavor_surf = font.render(f"\"{game._flavor_text}\"", True, (120, 110, 90))
    flavor_rect = flavor_surf.get_rect(center=(width // 2, 380))
    screen.blit(flavor_surf, flavor_rect)


def _draw_seed_info(game: "Game", screen: pygame.Surface) -> None:
    """Draw the world seed."""
    width, height = screen.get_size()
    font = get_monospace(14)
    seed_text = f"World Seed: {game.seed}"
    seed_surf = font.render(seed_text, True, (100, 95, 85))
    seed_rect = seed_surf.get_rect(center=(width // 2, height - 80))
    screen.blit(seed_surf, seed_rect)


def _draw_loading_tip(screen: pygame.Surface, time: float) -> None:
    """Draw a rotating loading tip."""
    tips = [
        "Tip: Forester background gives woodcutting bonuses",
        "Tip: Prospector background gives mining bonuses", 
        "Tip: Scavenger background gives foraging bonuses",
        "Tip: Press TAB in-game to toggle skill panel",
        "Tip: Press I to open inventory, C for crafting",
        "Tip: Right-click to cancel building placement",
        "Tip: Campfires provide warmth and cook food",
        "Tip: Monsters drop loot based on biome",
        "Tip: Seasons affect resource availability",
        "Tip: Factions remember your actions",
    ]
    tip_index = int(time / 4) % len(tips)
    
    width, height = screen.get_size()
    font = get_monospace(13)
    tip_surf = font.render(tips[tip_index], True, (90, 100, 120))
    tip_rect = tip_surf.get_rect(center=(width // 2, height - 45))
    screen.blit(tip_surf, tip_rect)


def _draw_error_message(screen: pygame.Surface) -> None:
    """Draw error state message."""
    width, height = screen.get_size()
    font = get_monospace_bold(24)
    error_surf = font.render(
        "World generation failed.", True, (255, 100, 100),
    )
    error_rect = error_surf.get_rect(center=(width // 2, height // 2 - 20))
    screen.blit(error_surf, error_rect)
    
    hint_font = get_monospace(16)
    hint_surf = hint_font.render(
        "Press Enter or Escape to return to title.", True, (180, 180, 180),
    )
    hint_rect = hint_surf.get_rect(center=(width // 2, height // 2 + 30))
    screen.blit(hint_surf, hint_rect)


def handle_loading_event(game: "Game", event) -> None:
    """Handle events during loading and error states."""
    if game.state == GameState.ERROR:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            game.state = GameState.TITLE
            game.world = None
            game.player = None
    # LOADING and LOADING_SAVE: no input needed
