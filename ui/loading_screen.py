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
            life = random.uniform(0.5, 2.0)
            self.particles.append({
                "x": random.uniform(0, WINDOW_WIDTH),
                "y": random.uniform(0, WINDOW_HEIGHT),
                "vx": random.uniform(-8, 8),
                "vy": random.uniform(-20, -10),
                # max_life must equal life so alpha never exceeds 255
                "life": life,
                "max_life": life,
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
            alpha = max(0, min(255, int(255 * (p["life"] / p["max_life"]))))
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
    stage_rect = stage_surf.get_rect(center=(width // 2, 260))
    screen.blit(stage_surf, stage_rect)


_head_glow_cache: dict[int, pygame.Surface] = {}


def _get_head_glow(radius: int) -> pygame.Surface:
    """Radially fading glow surface placed under the fill's leading edge."""
    surf = _head_glow_cache.get(radius)
    if surf is None:
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for rr in range(radius, 0, -2):
            alpha = int(46 * (1 - rr / radius) ** 2)
            pygame.draw.circle(surf, (210, 230, 140, alpha), (radius, radius), rr)
        _head_glow_cache[radius] = surf
    return surf


def _draw_progress_bar(screen: pygame.Surface, game: "Game", time: float) -> None:
    """Draw the animated progress bar with percentage and stage dots."""
    width = screen.get_width()
    bar_width = 520
    bar_height = 24
    bar_x = (width - bar_width) // 2
    bar_y = 312
    radius = bar_height // 2

    # Recessed well: darker inset with a fine outer border
    pygame.draw.rect(
        screen, (14, 16, 22),
        (bar_x - 2, bar_y - 2, bar_width + 4, bar_height + 4),
        border_radius=radius + 2,
    )
    pygame.draw.rect(
        screen, (46, 50, 62),
        (bar_x - 2, bar_y - 2, bar_width + 4, bar_height + 4),
        1, border_radius=radius + 2,
    )

    # Fill: full-width gradient (green → gold), gloss stripe and animated
    # diagonal flow stripes baked on, then clipped to rounded corners.
    fill_width = int(bar_width * max(0.0, min(1.0, game.loading_progress)))
    if fill_width > 0:
        fill = pygame.Surface((fill_width, bar_height), pygame.SRCALPHA)
        for i in range(fill_width):
            t = i / max(1, bar_width - 1)  # gradient tracks the whole bar, not the fill
            r = int(70 + t * 150)
            g = int(150 + t * 70)
            b = int(90 - t * 20)
            pygame.draw.line(fill, (r, g, b), (i, 0), (i, bar_height))

        gloss = pygame.Surface((fill_width, bar_height // 2), pygame.SRCALPHA)
        gloss.fill((255, 255, 255, 30))
        fill.blit(gloss, (0, 0))

        stripes = pygame.Surface((fill_width, bar_height), pygame.SRCALPHA)
        stripe_x = -((time * 40.0) % 26.0)
        while stripe_x < fill_width:
            pygame.draw.line(stripes, (255, 255, 255, 22),
                             (stripe_x, bar_height), (stripe_x + 13, 0), 6)
            stripe_x += 26.0
        fill.blit(stripes, (0, 0))

        mask = pygame.Surface((fill_width, bar_height), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                         border_radius=radius)
        fill.blit(mask, (0, 0), None, pygame.BLEND_RGBA_MIN)

        # Soft glow under the leading edge
        if game.loading_progress < 1.0:
            glow = _get_head_glow(bar_height * 2)
            gx = bar_x + fill_width
            screen.blit(glow, (gx - bar_height * 2, bar_y + bar_height // 2 - bar_height * 2))

        screen.blit(fill, (bar_x, bar_y))

    # Percentage text
    pct_font = get_monospace_bold(22)
    pct_text = f"{int(game.loading_progress * 100)}%"
    pct_surf = pct_font.render(pct_text, True, (255, 255, 255))
    pct_rect = pct_surf.get_rect(center=(width // 2, bar_y + bar_height + 26))
    screen.blit(pct_surf, pct_rect)

    # Stage segment dots sit between the stage label and the bar
    _draw_progress_segments(screen, bar_x, bar_y - 24, bar_width, game.loading_progress)


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
            radius = 4
        elif seg_progress > 0:
            color = (230, 200, 90)  # In progress (pulses)
            radius = 6
        else:
            color = (56, 58, 70)  # Pending
            radius = 4

        cx = int(seg_center)
        if radius == 6:
            glow = _get_head_glow(12)
            screen.blit(glow, (cx - 12, y - 12))
        pygame.draw.circle(screen, color, (cx, y), radius)
        pygame.draw.circle(screen, (30, 32, 40), (cx, y), radius, 1)


def _draw_flavor_text(game: "Game", screen: pygame.Surface) -> None:
    """Draw rotating flavor text."""
    if not hasattr(game, "_flavor_text") or not game._flavor_text:
        rng = random.Random(game.seed)
        game._flavor_text = rng.choice(FLAVOR_TEXTS)
    
    width, height = screen.get_size()
    font = get_monospace_italic(15)
    flavor_surf = font.render(f"\"{game._flavor_text}\"", True, (120, 110, 90))
    flavor_rect = flavor_surf.get_rect(center=(width // 2, 402))
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
