"""
generate_sprites.py — Procedural sprite generator for Don't Starve RuneScape.

Generates all sprite PNGs using pygame primitives (simple shapes),
saving them to assets/sprites/. Run from project root:

    python tools/generate_sprites.py

All sprites use a consistent pixel-art aesthetic built from
basic geometric shapes (rectangles, circles, polygons).
"""

import os
import pygame

# ── Configuration ─────────────────────────────────────────────────────

OUTPUT_ROOT = "assets/sprites"
BASE_COLOR = (255, 255, 255)  # Transparent background marker (will be made transparent)

# Sprite sizes
PLAYER_SIZE = 16
RESOURCE_SIZE = 16
TREE_SIZE = 32
ROCK_SIZE = 16
MONSTER_SIZE = 16
STRUCTURE_SIZE = 16
NPC_SIZE = 16
TERRAIN_SIZE = 64  # Terrain tiles are larger (full tile)


def ensure_dir(path: str) -> None:
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def save_surface(path: str, surface: pygame.Surface) -> None:
    """Save surface as PNG with transparency."""
    ensure_dir(os.path.dirname(path))
    # Convert to RGBA for transparency
    surface = surface.convert_alpha()
    pygame.image.save(surface, path)
    print(f"  Saved: {path}")


# ── Drawing Helpers ───────────────────────────────────────────────────

def draw_pixel_art(surface: pygame.Surface, pixels: list[list[int]], palette: dict[int, tuple[int, int, int]], scale: int = 1) -> None:
    """
    Draw pixel art from a grid of color indices.
    
    Args:
        surface: Pygame surface to draw on.
        pixels: 2D list of integer color indices (0 = transparent).
        palette: Dict mapping index -> (r, g, b) tuple.
        scale: Pixel scale factor (each pixel drawn as scale×scale block).
    """
    w = len(pixels[0]) if pixels else 0
    h = len(pixels)
    for y in range(h):
        for x in range(w):
            color_idx = pixels[y][x]
            if color_idx != 0 and color_idx in palette:
                color = palette[color_idx]
                for dy in range(scale):
                    for dx in range(scale):
                        px = x * scale + dx
                        py = y * scale + dy
                        if px < surface.get_width() and py < surface.get_height():
                            surface.set_at((px, py), color + (255,))


def circle(surface: pygame.Surface, center: tuple[int, int], radius: int, color: tuple[int, int, int], outline: bool = False, outline_width: int = 1, outline_color: tuple[int, int, int] | None = None):
    """Draw a filled or outlined circle using simple points (pixel-art friendly)."""
    r = radius
    cx, cy = center
    if outline:
        oc = outline_color or color
        for angle in range(360):
            import math
            ax = int(cx + r * math.cos(math.radians(angle)))
            ay = int(cy - r * math.sin(math.radians(angle)))
            if 0 <= ax < surface.get_width() and 0 <= ay < surface.get_height():
                surface.set_at((ax, ay), oc)
    else:
        # Filled circle using scanline approach
        for y in range(max(0, cy - r), min(surface.get_height(), cy + r + 1)):
            for x in range(max(0, cx - r), min(surface.get_width(), cx + r + 1)):
                dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if dist <= r:
                    surface.set_at((x, y), color)


def rectangle(surface: pygame.Surface, rect: tuple[int, int, int, int], color: tuple[int, int, int]):
    """Draw a filled rectangle."""
    x, y, w, h = rect
    for dy in range(h):
        for dx in range(w):
            px, py = x + dx, y + dy
            if 0 <= px < surface.get_width() and 0 <= py < surface.get_height():
                surface.set_at((px, py), color)


def polygon(surface: pygame.Surface, points: list[tuple[int, int]], color: tuple[int, int, int]):
    """Draw a filled polygon using simple rasterization."""
    import math

    def point_in_polygon(px, py, poly):
        n = len(poly)
        inside = False
        x1, y1 = poly[n - 1]
        for i in range(n):
            x2, y2 = poly[i]
            if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1) + x1):
                inside = not inside
            x1, y1 = x2, y2
        return inside

    w, h = surface.get_width(), surface.get_height()
    for py in range(h):
        for px in range(w):
            if point_in_polygon(px, py, points):
                surface.set_at((px, py), color)


def add_bark_texture(surface: pygame.Surface, x: int, y: int, w: int, h: int, dark: tuple[int, int, int], light: tuple[int, int, int]) -> None:
    """Add small bark texture dots to a trunk area."""
    for ty in range(y, min(y + h, surface.get_height()), 2):
        for tx in range(x, min(x + w, surface.get_width()), 2):
            if (tx + ty) % 4 == 0:
                surface.set_at((tx, ty), light)
            elif (tx + ty) % 4 == 1:
                surface.set_at((tx, ty), dark)


def add_leaf_clustering(surface: pygame.Surface, cx: int, cy: int, radius: int, dark: tuple[int, int, int], mid: tuple[int, int, int], light: tuple[int, int, int], count: int = 6) -> None:
    """Add random leaf variation spots to create depth."""
    import random
    random.seed(hash((cx, cy, radius)))
    for _ in range(count):
        lx = cx + random.randint(-radius // 2, radius // 2)
        ly = cy + random.randint(-radius // 2, radius // 2)
        spot = random.choice([dark, mid, light])
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                px, py = lx + dx, ly + dy
                if 0 <= px < surface.get_width() and 0 <= py < surface.get_height():
                    dist = ((px - lx) ** 2 + (py - ly) ** 2) ** 0.5
                    if dist <= 1:
                        surface.set_at((px, py), spot)


# ── Player Sprites ────────────────────────────────────────────────────

def generate_player_sprites() -> None:
    """Generate player idle and walk sprites."""
    print("\n=== Generating Player Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "player")

    # Palette
    PALETTE = {
        1: (139, 90, 43),    # Brown (hair, boots, belt)
        2: (34, 139, 34),    # Green (tunic)
        3: (255, 220, 180),  # Skin tone (face)
        4: (60, 40, 30),     # Dark brown (hair details)
        5: (20, 20, 20),     # Black (eyes)
        6: (160, 120, 60),   # Light brown (belt buckle)
    }

    # Idle frame 0: Facing forward
    idle_0 = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE), pygame.SRCALPHA)
    # Head (circle)
    circle(idle_0, (8, 5), 3, PALETTE[3])
    # Hair
    circle(idle_0, (8, 4), 3, PALETTE[1])
    circle(idle_0, (7, 3), 2, PALETTE[4])
    # Eyes
    idle_0.set_at((6, 5), PALETTE[5])
    idle_0.set_at((10, 5), PALETTE[5])
    # Body (rectangle)
    rectangle(idle_0, (6, 8, 4, 5), PALETTE[2])
    # Belt
    rectangle(idle_0, (6, 12, 4, 1), PALETTE[1])
    idle_0.set_at((7, 12), PALETTE[6])
    idle_0.set_at((8, 12), PALETTE[6])
    # Boots
    rectangle(idle_0, (6, 14, 1, 2), PALETTE[1])
    rectangle(idle_0, (9, 14, 1, 2), PALETTE[1])
    save_surface(os.path.join(output_dir, "idle_0.png"), idle_0)

    # Idle frame 1: Slight variation
    idle_1 = idle_0.copy()
    save_surface(os.path.join(output_dir, "idle_1.png"), idle_1)

    # Idle frame 2: Slight variation 2
    idle_2 = idle_0.copy()
    save_surface(os.path.join(output_dir, "idle_2.png"), idle_2)

    # Idle frame 3: Slight variation 3
    idle_3 = idle_0.copy()
    save_surface(os.path.join(output_dir, "idle_3.png"), idle_3)

    # Walk frame 0: Left foot forward
    walk_0 = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE), pygame.SRCALPHA)
    walk_0.blit(idle_0, (0, 0))
    # Shift left boot forward
    walk_0.set_at((5, 15), PALETTE[1])
    walk_0.set_at((5, 14), PALETTE[1])
    # Remove right boot slightly
    walk_0.set_at((10, 15), (0, 0, 0, 0))
    save_surface(os.path.join(output_dir, "walk_0.png"), walk_0)

    # Walk frame 1: Right foot forward
    walk_1 = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE), pygame.SRCALPHA)
    walk_1.blit(idle_0, (0, 0))
    walk_1.set_at((11, 15), PALETTE[1])
    walk_1.set_at((11, 14), PALETTE[1])
    walk_1.set_at((6, 15), (0, 0, 0, 0))
    save_surface(os.path.join(output_dir, "walk_1.png"), walk_1)

    # Walk frame 2: Left foot forward (mid-step)
    walk_2 = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE), pygame.SRCALPHA)
    walk_2.blit(idle_0, (0, 0))
    walk_2.set_at((5, 15), PALETTE[1])
    walk_2.set_at((4, 15), PALETTE[1])
    save_surface(os.path.join(output_dir, "walk_2.png"), walk_2)

    # Walk frame 3: Right foot forward (mid-step)
    walk_3 = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE), pygame.SRCALPHA)
    walk_3.blit(idle_0, (0, 0))
    walk_3.set_at((11, 15), PALETTE[1])
    walk_3.set_at((12, 15), PALETTE[1])
    save_surface(os.path.join(output_dir, "walk_3.png"), walk_3)

    print("  Generated 8 player sprites (4 idle + 4 walk)")


# ── Tree Sprites ──────────────────────────────────────────────────────

def generate_tree_sprites() -> None:
    """Generate tree and bush sprites with detailed biome-specific variants."""
    print("\n=== Generating Tree Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "trees")

    # ── Pine Tree (32x32) ──
    # Tall, conical shape with layered tiers — forest/mountain
    pine = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (90, 60, 30),     # Dark brown (trunk)
        2: (30, 60, 30),     # Very dark green (shadows)
        3: (40, 80, 40),     # Dark green (base)
        4: (50, 100, 50),    # Medium green (mid tier)
        5: (60, 120, 60),    # Light green (top tier)
        6: (80, 140, 70),    # Bright green (sunlit tips)
    }
    # Trunk with bark texture
    rectangle(pine, (14, 22, 4, 10), PALETTE[1])
    add_bark_texture(pine, 14, 22, 4, 10, (70, 45, 20), (100, 70, 35))
    # Tier 1 (bottom) - widest
    circle(pine, (16, 16), 11, PALETTE[3])
    circle(pine, (12, 15), 7, PALETTE[2])
    circle(pine, (20, 15), 7, PALETTE[2])
    # Tier 2 (middle)
    circle(pine, (16, 12), 9, PALETTE[4])
    circle(pine, (13, 11), 5, PALETTE[3])
    circle(pine, (19, 11), 5, PALETTE[3])
    # Tier 3 (top)
    circle(pine, (16, 9), 7, PALETTE[5])
    circle(pine, (14, 8), 4, PALETTE[4])
    circle(pine, (18, 8), 4, PALETTE[4])
    # Sunlit tip
    circle(pine, (16, 7), 3, PALETTE[6])
    pine.set_at((15, 6), PALETTE[6])
    pine.set_at((17, 6), PALETTE[6])
    pine.set_at((16, 5), PALETTE[5])
    add_leaf_clustering(pine, 16, 11, 6, PALETTE[2], PALETTE[4], PALETTE[5])
    save_surface(os.path.join(output_dir, "pine.png"), pine)

    # ── Maple Tree (32x32) ──
    # Broad, rounded canopy with autumn reds/oranges — forest
    maple = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 70, 40),    # Brown (trunk)
        2: (160, 50, 40),    # Deep red (shadow)
        3: (200, 80, 40),    # Orange-red (base)
        4: (220, 120, 50),   # Orange (mid)
        5: (230, 150, 60),   # Golden orange (highlight)
        6: (240, 180, 80),   # Yellow-gold (sunlit)
    }
    # Trunk
    rectangle(maple, (14, 20, 4, 12), PALETTE[1])
    add_bark_texture(maple, 14, 20, 4, 12, (80, 55, 30), (120, 85, 50))
    # Broad canopy (multiple overlapping circles)
    circle(maple, (16, 13), 10, PALETTE[2])
    circle(maple, (11, 11), 7, PALETTE[3])
    circle(maple, (21, 11), 7, PALETTE[3])
    circle(maple, (14, 10), 6, PALETTE[4])
    circle(maple, (18, 10), 6, PALETTE[4])
    circle(maple, (16, 9), 5, PALETTE[5])
    # Sunlit patches
    circle(maple, (13, 8), 3, PALETTE[6])
    circle(maple, (19, 8), 3, PALETTE[6])
    maple.set_at((16, 7), PALETTE[6])
    maple.set_at((15, 6), PALETTE[5])
    maple.set_at((17, 6), PALETTE[5])
    # Autumn leaf variation
    add_leaf_clustering(maple, 16, 11, 5, PALETTE[2], PALETTE[4], PALETTE[6], 8)
    # A few darker red spots for depth
    maple.set_at((12, 14), PALETTE[2])
    maple.set_at((20, 13), PALETTE[2])
    maple.set_at((16, 15), PALETTE[2])
    save_surface(os.path.join(output_dir, "maple.png"), maple)

    # ── Spruce Tree (32x32) ──
    # Very narrow, tall conical shape — mountain biome
    spruce = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 55, 30),     # Dark brown (trunk)
        2: (25, 55, 25),     # Very dark green (shadow)
        3: (35, 75, 35),     # Dark green
        4: (45, 95, 45),     # Medium green
        5: (55, 115, 55),    # Light green
        6: (75, 135, 65),    # Bright green (tips)
    }
    # Thin trunk
    rectangle(spruce, (15, 22, 2, 10), PALETTE[1])
    add_bark_texture(spruce, 15, 22, 2, 10, (60, 40, 20), (90, 65, 35))
    # Very narrow tiers (taller, thinner than pine)
    # Tier 1
    circle(spruce, (16, 17), 7, PALETTE[3])
    circle(spruce, (13, 16), 4, PALETTE[2])
    circle(spruce, (19, 16), 4, PALETTE[2])
    # Tier 2
    circle(spruce, (16, 14), 6, PALETTE[4])
    circle(spruce, (14, 13), 3, PALETTE[3])
    circle(spruce, (18, 13), 3, PALETTE[3])
    # Tier 3
    circle(spruce, (16, 11), 5, PALETTE[5])
    circle(spruce, (15, 10), 2, PALETTE[4])
    circle(spruce, (17, 10), 2, PALETTE[4])
    # Top
    circle(spruce, (16, 9), 3, PALETTE[6])
    spruce.set_at((16, 8), PALETTE[6])
    spruce.set_at((15, 7), PALETTE[5])
    spruce.set_at((17, 7), PALETTE[5])
    spruce.set_at((16, 6), PALETTE[6])
    add_leaf_clustering(spruce, 16, 13, 4, PALETTE[2], PALETTE[4], PALETTE[5], 5)
    save_surface(os.path.join(output_dir, "spruce.png"), spruce)

    # ── Willow Tree (32x32) ──
    # Wide canopy with drooping branches — swamp
    willow = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 85, 50),    # Olive-brown (trunk)
        2: (45, 70, 35),     # Dark olive-green (shadow)
        3: (55, 90, 40),     # Medium olive-green
        4: (70, 110, 50),    # Light olive-green
        5: (85, 130, 55),    # Bright green-yellow (highlights)
        6: (60, 80, 45),     # Dark hanging tendrils
    }
    # Thick, slightly curved trunk (drawn as thicker rectangle with slight lean)
    rectangle(willow, (14, 20, 4, 12), PALETTE[1])
    rectangle(willow, (13, 20, 1, 6), PALETTE[1])  # Lean left at top
    add_bark_texture(willow, 13, 20, 5, 12, (80, 65, 35), (115, 95, 55))
    # Wide, rounded canopy (wider than oak)
    circle(willow, (16, 13), 10, PALETTE[2])
    circle(willow, (12, 11), 7, PALETTE[3])
    circle(willow, (20, 11), 7, PALETTE[3])
    circle(willow, (16, 10), 7, PALETTE[4])
    circle(willow, (10, 12), 4, PALETTE[3])
    circle(willow, (22, 12), 4, PALETTE[3])
    # Highlights
    circle(willow, (14, 9), 4, PALETTE[5])
    circle(willow, (18, 9), 4, PALETTE[5])
    willow.set_at((16, 8), PALETTE[5])
    # Drooping tendrils (hanging branches) — key willow feature
    for tx in [6, 8, 10, 14, 18, 22, 24, 26]:
        tendril_len = 4 + ((tx * 7) % 4)  # Varying lengths
        for ty in range(18, min(18 + tendril_len, 32)):
            willow.set_at((tx, ty), PALETTE[6])
        # Tendril tip (slightly lighter)
        tip = min(18 + tendril_len, 31)
        willow.set_at((tx, tip), (70, 90, 50))
    # Dark variation spots
    add_leaf_clustering(willow, 16, 12, 5, PALETTE[2], PALETTE[3], PALETTE[4], 6)
    save_surface(os.path.join(output_dir, "willow.png"), willow)

    # ── Birch Tree (32x32) ──
    # White/light bark, yellow-green canopy — forest edge
    birch = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 215, 200),   # White-grey (bark)
        2: (180, 175, 160),   # Dark grey (bark marks)
        3: (90, 60, 30),      # Dark brown (trunk base)
        4: (60, 100, 40),     # Dark yellow-green (shadow)
        5: (80, 130, 50),     # Medium yellow-green
        6: (100, 160, 60),    # Light yellow-green
        7: (130, 190, 80),    # Bright lime (sunlit)
    }
    # White trunk with dark horizontal marks
    rectangle(birch, (14, 20, 4, 12), PALETTE[1])
    add_bark_texture(birch, 14, 20, 4, 12, PALETTE[2], PALETTE[1])
    # Dark horizontal bark marks (birch characteristic)
    for mark_y in [22, 24, 26, 28]:
        mark_w = 2 + ((mark_y * 3) % 2)
        rectangle(birch, (13, mark_y, mark_w + 2, 1), PALETTE[2])
    # Base dark
    rectangle(birch, (14, 28, 4, 4), PALETTE[3])
    # Light, airy canopy
    circle(birch, (16, 13), 9, PALETTE[4])
    circle(birch, (12, 11), 6, PALETTE[5])
    circle(birch, (20, 11), 6, PALETTE[5])
    circle(birch, (16, 10), 6, PALETTE[6])
    circle(birch, (14, 9), 4, PALETTE[7])
    circle(birch, (18, 9), 4, PALETTE[7])
    # Sunlit top
    birch.set_at((16, 8), PALETTE[7])
    birch.set_at((15, 7), PALETTE[6])
    birch.set_at((17, 7), PALETTE[6])
    # Light variation
    add_leaf_clustering(birch, 16, 11, 5, PALETTE[4], PALETTE[6], PALETTE[7], 5)
    save_surface(os.path.join(output_dir, "birch.png"), birch)

    # ── Dead Tree (32x32) ──
    # Gnarled, leafless — desert/coastal
    dead = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (70, 50, 30),     # Dark brown (main trunk)
        2: (90, 65, 40),     # Medium brown
        3: (110, 85, 55),    # Light brown (highlights)
        4: (50, 35, 20),     # Very dark brown (shadows)
        5: (130, 100, 60),   # Pale highlight
    }
    # Main trunk (slightly irregular)
    rectangle(dead, (14, 18, 4, 14), PALETTE[1])
    # Trunk texture
    add_bark_texture(dead, 14, 18, 4, 14, PALETTE[4], PALETTE[3])
    # Left branch (gnarled, angled up)
    rectangle(dead, (12, 18, 2, 1), PALETTE[1])
    rectangle(dead, (11, 17, 1, 1), PALETTE[1])
    rectangle(dead, (10, 16, 1, 1), PALETTE[2])
    rectangle(dead, (9, 15, 1, 1), PALETTE[2])
    rectangle(dead, (9, 14, 1, 1), PALETTE[3])
    # Right branch (thicker, angled up)
    rectangle(dead, (16, 18, 3, 1), PALETTE[1])
    rectangle(dead, (18, 17, 2, 1), PALETTE[2])
    rectangle(dead, (19, 16, 1, 1), PALETTE[2])
    rectangle(dead, (20, 15, 1, 1), PALETTE[3])
    # Top branch (split)
    rectangle(dead, (14, 17, 1, 1), PALETTE[1])
    rectangle(dead, (15, 16, 1, 1), PALETTE[2])
    rectangle(dead, (16, 16, 1, 1), PALETTE[2])
    rectangle(dead, (17, 15, 1, 1), PALETTE[3])
    # Small twigs
    dead.set_at((8, 14), PALETTE[2])
    dead.set_at((21, 14), PALETTE[2])
    dead.set_at((10, 13), PALETTE[3])
    dead.set_at((19, 13), PALETTE[3])
    # Dark hollow spots
    dead.set_at((15, 22), PALETTE[4])
    dead.set_at((16, 23), PALETTE[4])
    dead.set_at((15, 25), PALETTE[4])
    # Highlights on branches
    dead.set_at((9, 15), PALETTE[5])
    dead.set_at((20, 15), PALETTE[5])
    dead.set_at((17, 15), PALETTE[5])
    save_surface(os.path.join(output_dir, "dead_tree.png"), dead)

    # ── Improved Oak Tree (32x32) ──
    # Enhanced version of the original with more detail
    oak = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (139, 90, 43),    # Brown (trunk)
        2: (34, 100, 34),    # Dark green (shadow)
        3: (50, 140, 50),    # Medium green
        4: (70, 160, 70),    # Light green
        5: (90, 175, 80),    # Bright green (sunlit)
        6: (25, 75, 25),     # Very dark green (deep shadow)
    }
    # Trunk with bark texture
    rectangle(oak, (13, 20, 6, 12), PALETTE[1])
    add_bark_texture(oak, 13, 20, 6, 12, (110, 70, 35), (160, 105, 50))
    # Roots (small extensions at base)
    rectangle(oak, (11, 29, 2, 2), PALETTE[1])
    rectangle(oak, (19, 29, 2, 2), PALETTE[1])
    oak.set_at((12, 29), PALETTE[1])
    oak.set_at((18, 29), PALETTE[1])
    # Main canopy
    circle(oak, (16, 12), 10, PALETTE[2])
    # Shadow areas (depth)
    circle(oak, (11, 12), 5, PALETTE[6])
    circle(oak, (19, 13), 4, PALETTE[6])
    # Mid layers
    circle(oak, (12, 10), 7, PALETTE[3])
    circle(oak, (20, 10), 7, PALETTE[3])
    circle(oak, (16, 10), 6, PALETTE[3])
    # Light layers
    circle(oak, (14, 8), 5, PALETTE[4])
    circle(oak, (18, 8), 5, PALETTE[4])
    # Sunlit top
    circle(oak, (16, 7), 4, PALETTE[5])
    oak.set_at((15, 6), PALETTE[5])
    oak.set_at((17, 6), PALETTE[5])
    oak.set_at((16, 5), PALETTE[4])
    # Leaf clustering for depth
    add_leaf_clustering(oak, 16, 11, 5, PALETTE[2], PALETTE[4], PALETTE[5], 7)
    # Dark variation spots
    oak.set_at((14, 14), PALETTE[6])
    oak.set_at((18, 13), PALETTE[6])
    oak.set_at((10, 11), PALETTE[6])
    save_surface(os.path.join(output_dir, "oak.png"), oak)

    # ── Berry Bush (16x16) ──
    # Enhanced with more berries and detail
    bush = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (34, 100, 34),    # Green (bush)
        2: (50, 130, 50),    # Light green (highlights)
        3: (220, 50, 50),    # Red (berries)
        4: (20, 70, 20),     # Dark green (shadow)
        5: (240, 80, 80),    # Bright red (ripe berries)
    }
    # Shadow base
    circle(bush, (8, 10), 6, PALETTE[4])
    # Bush body
    circle(bush, (8, 10), 6, PALETTE[1])
    circle(bush, (6, 9), 4, PALETTE[2])
    circle(bush, (10, 9), 4, PALETTE[2])
    circle(bush, (8, 8), 3, PALETTE[2])
    # Berries — more of them, with bright variation
    circle(bush, (4, 9), 1, PALETTE[3])
    circle(bush, (5, 8), 1, PALETTE[5])
    circle(bush, (9, 8), 1, PALETTE[3])
    circle(bush, (11, 10), 1, PALETTE[5])
    circle(bush, (7, 11), 1, PALETTE[3])
    circle(bush, (10, 11), 1, PALETTE[3])
    circle(bush, (6, 10), 1, PALETTE[5])
    circle(bush, (12, 9), 1, PALETTE[3])
    circle(bush, (8, 7), 1, PALETTE[5])
    save_surface(os.path.join(output_dir, "berry_bush.png"), bush)

    print("  Generated 7 tree sprites (oak, pine, maple, spruce, willow, birch, dead_tree) + berry_bush")


# ── Rock/Ore Sprites ──────────────────────────────────────────────────

def generate_rock_sprites() -> None:
    """Generate rock and ore sprites — distinct shape per resource."""
    print("\n=== Generating Rock/Ore Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "rocks")

    # Iron Rock (16x16) — angular, rough metallic boulder
    iron = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (95, 95, 105),    # Iron grey (base)
        2: (70, 70, 80),     # Dark iron (shadow)
        3: (130, 130, 145),  # Light iron (highlight)
        4: (155, 155, 165),  # Metallic specks
        5: (110, 110, 120),  # Mid iron
    }
    # Angular rock body (irregular polygon)
    polygon(iron, [(4, 10), (6, 5), (10, 4), (13, 7), (14, 11), (12, 14), (6, 15), (3, 13)], PALETTE[1])
    polygon(iron, [(5, 11), (7, 7), (10, 6), (12, 9), (11, 13), (7, 14)], PALETTE[5])
    # Iron specks / metallic flecks
    iron.set_at((5, 8), PALETTE[4])
    iron.set_at((8, 6), PALETTE[4])
    iron.set_at((11, 9), PALETTE[4])
    iron.set_at((6, 12), PALETTE[4])
    # Shadow edge
    polygon(iron, [(4, 10), (6, 5), (7, 6), (5, 11)], PALETTE[2])
    save_surface(os.path.join(output_dir, "iron.png"), iron)

    # Copper Rock (16x16) — chunky reddish-brown with copper streaks
    copper = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (130, 85, 55),    # Copper brown (base)
        2: (95, 65, 40),     # Dark copper (shadow)
        3: (195, 125, 75),   # Copper vein
        4: (215, 150, 90),   # Bright copper (highlight)
        5: (110, 80, 50),    # Mid copper
    }
    # Chunky rounded rock
    circle(copper, (8, 10), 6, PALETTE[1])
    circle(copper, (6, 9), 4, PALETTE[2])
    # Copper vein streaks (wavy lines)
    copper.set_at((5, 7), PALETTE[3])
    copper.set_at((6, 6), PALETTE[3])
    copper.set_at((7, 5), PALETTE[3])
    copper.set_at((8, 5), PALETTE[4])
    copper.set_at((9, 6), PALETTE[3])
    copper.set_at((10, 7), PALETTE[3])
    copper.set_at((11, 8), PALETTE[3])
    copper.set_at((7, 11), PALETTE[4])
    copper.set_at((10, 12), PALETTE[4])
    save_surface(os.path.join(output_dir, "copper.png"), copper)

    # Gold Vein (16x16) — dark rock with prominent golden vein
    gold = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (85, 80, 75),     # Dark rock base
        2: (60, 55, 50),     # Very dark rock
        3: (210, 175, 35),   # Gold vein
        4: (245, 205, 55),   # Bright gold
        5: (105, 100, 95),   # Mid rock
    }
    # Dark angular rock
    polygon(gold, [(3, 11), (5, 5), (9, 4), (13, 6), (14, 10), (13, 14), (7, 15), (4, 13)], PALETTE[1])
    polygon(gold, [(5, 11), (7, 6), (10, 5), (12, 8), (11, 13), (7, 14)], PALETTE[5])
    # Prominent gold vein (zigzag)
    gold.set_at((5, 8), PALETTE[3])
    gold.set_at((6, 7), PALETTE[4])
    gold.set_at((7, 8), PALETTE[3])
    gold.set_at((8, 7), PALETTE[4])
    gold.set_at((9, 8), PALETTE[3])
    gold.set_at((10, 9), PALETTE[3])
    gold.set_at((11, 8), PALETTE[4])
    gold.set_at((7, 11), PALETTE[3])
    gold.set_at((9, 12), PALETTE[4])
    save_surface(os.path.join(output_dir, "gold.png"), gold)

    # Stone (16x16) — rough grey cobble, simple and utilitarian
    stone = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (125, 125, 135),  # Stone grey
        2: (95, 95, 105),    # Dark stone
        3: (155, 155, 165),  # Light stone
        4: (110, 110, 120),  # Mid stone
    }
    # Rough cobble shape
    circle(stone, (8, 10), 6, PALETTE[1])
    circle(stone, (6, 9), 4, PALETTE[2])
    circle(stone, (10, 9), 4, PALETTE[3])
    # Surface texture dots
    stone.set_at((5, 8), PALETTE[4])
    stone.set_at((9, 7), PALETTE[3])
    stone.set_at((12, 10), PALETTE[2])
    stone.set_at((7, 13), PALETTE[3])
    save_surface(os.path.join(output_dir, "stone.png"), stone)

    # Gemstone (16x16) — crystal protruding from rock matrix
    gem = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (90, 85, 95),     # Grey rock matrix
        2: (65, 60, 70),     # Dark matrix
        3: (190, 90, 210),   # Purple gem
        4: (225, 135, 245),  # Bright gem facet
        5: (130, 80, 160),   # Mid gem
    }
    # Rock matrix (background)
    circle(gem, (8, 11), 5, PALETTE[1])
    circle(gem, (6, 10), 3, PALETTE[2])
    # Large crystal facet (prominent diamond)
    polygon(gem, [(8, 3), (12, 7), (8, 12), (4, 7)], PALETTE[3])
    # Facet highlights
    polygon(gem, [(8, 4), (10, 7), (8, 10), (6, 7)], PALETTE[5])
    gem.set_at((8, 6), PALETTE[4])
    gem.set_at((7, 8), PALETTE[4])
    save_surface(os.path.join(output_dir, "gem.png"), gem)

    # Rare Ore (16x16) — dark rock with purple crystalline growths
    rare_ore = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (70, 60, 80),     # Dark purple rock
        2: (50, 40, 60),     # Very dark rock
        3: (175, 90, 215),   # Purple crystals
        4: (205, 130, 240),  # Bright crystal
        5: (100, 80, 120),   # Mid purple
    }
    # Dark angular rock base
    polygon(rare_ore, [(3, 11), (5, 5), (10, 4), (13, 7), (14, 11), (12, 14), (6, 15), (4, 13)], PALETTE[1])
    polygon(rare_ore, [(5, 11), (7, 6), (10, 5), (12, 8), (11, 13), (7, 14)], PALETTE[5])
    # Crystal growths (small faceted clusters)
    polygon(rare_ore, [(5, 6), (7, 4), (6, 8)], PALETTE[3])
    polygon(rare_ore, [(10, 5), (12, 4), (11, 8)], PALETTE[3])
    rare_ore.set_at((6, 5), PALETTE[4])
    rare_ore.set_at((11, 5), PALETTE[4])
    rare_ore.set_at((8, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "rare.png"), rare_ore)

    # Tin Rock (16x16) — blue-grey metallic rock with tin luster
    tin = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (105, 110, 120),  # Tin grey-blue
        2: (80, 85, 95),     # Dark tin
        3: (145, 155, 170),  # Tin highlight
        4: (170, 180, 195),  # Bright tin luster
        5: (120, 125, 135),  # Mid tin
    }
    # Smooth metallic rock
    circle(tin, (8, 10), 6, PALETTE[1])
    circle(tin, (6, 9), 4, PALETTE[2])
    circle(tin, (10, 9), 4, PALETTE[5])
    # Tin luster streaks
    tin.set_at((5, 8), PALETTE[4])
    tin.set_at((7, 7), PALETTE[3])
    tin.set_at((11, 8), PALETTE[4])
    tin.set_at((9, 12), PALETTE[3])
    save_surface(os.path.join(output_dir, "tin.png"), tin)

    print("  Generated 7 rock/ore sprites (iron, copper, gold, stone, gem, rare, tin)")


# ── World Resource Sprites ────────────────────────────────────────────

def generate_world_sprites() -> None:
    """Generate world resource sprites (herbs, grass, etc.)."""
    print("\n=== Generating World Resource Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "world")

    # Herb (16x16)
    herb = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (34, 120, 34),    # Green (leaves)
        2: (50, 150, 50),    # Light green (highlights)
        3: (80, 60, 40),     # Brown (stem)
    }
    # Stem
    rectangle(herb, (7, 10, 2, 5), PALETTE[3])
    # Leaves (circles)
    circle(herb, (6, 9), 3, PALETTE[1])
    circle(herb, (10, 9), 3, PALETTE[2])
    circle(herb, (8, 7), 2, PALETTE[1])
    save_surface(os.path.join(output_dir, "herb.png"), herb)

    # Grass Patch (16x16)
    grass = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 130, 50),    # Green (grass blades)
        2: (70, 160, 70),    # Light green (tips)
    }
    # Grass tufts (thin rectangles)
    rectangle(grass, (5, 10, 1, 6), PALETTE[1])
    rectangle(grass, (7, 9, 1, 7), PALETTE[1])
    rectangle(grass, (9, 10, 1, 6), PALETTE[1])
    rectangle(grass, (11, 11, 1, 5), PALETTE[1])
    # Tips
    rectangle(grass, (5, 9, 1, 1), PALETTE[2])
    rectangle(grass, (7, 8, 1, 1), PALETTE[2])
    rectangle(grass, (9, 9, 1, 1), PALETTE[2])
    rectangle(grass, (11, 10, 1, 1), PALETTE[2])
    save_surface(os.path.join(output_dir, "grass.png"), grass)

    # Fiber Plant (16x16)
    fiber = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (140, 130, 80),   # Tan (fibers)
        2: (160, 150, 100),  # Light tan (highlights)
        3: (80, 60, 40),     # Brown (base)
    }
    # Base
    rectangle(fiber, (6, 12, 4, 3), PALETTE[3])
    # Fibers (vertical lines)
    rectangle(fiber, (7, 6, 1, 6), PALETTE[1])
    rectangle(fiber, (9, 6, 1, 6), PALETTE[1])
    rectangle(fiber, (8, 7, 1, 5), PALETTE[2])
    save_surface(os.path.join(output_dir, "fiber.png"), fiber)

    # Wheat Field (16x16)
    wheat = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 180, 80),   # Wheat (golden)
        2: (220, 200, 100),  # Light wheat (head)
        3: (80, 60, 40),     # Brown (stem)
    }
    # Stems
    rectangle(wheat, (5, 10, 1, 6), PALETTE[3])
    rectangle(wheat, (8, 9, 1, 7), PALETTE[3])
    rectangle(wheat, (11, 10, 1, 6), PALETTE[3])
    # Wheat heads (circles)
    circle(wheat, (5, 9), 2, PALETTE[1])
    circle(wheat, (5, 8), 1, PALETTE[2])
    circle(wheat, (8, 8), 2, PALETTE[1])
    circle(wheat, (8, 7), 1, PALETTE[2])
    circle(wheat, (11, 9), 2, PALETTE[1])
    circle(wheat, (11, 8), 1, PALETTE[2])
    save_surface(os.path.join(output_dir, "wheat.png"), wheat)

    # Water Source (16x16)
    water = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 120, 200),   # Blue (water)
        2: (80, 150, 230),   # Light blue (shimmer)
        3: (40, 100, 180),   # Dark blue (edges)
    }
    # Water pool (ellipse via circles)
    circle(water, (8, 9), 6, PALETTE[1])
    circle(water, (8, 8), 5, PALETTE[2])
    circle(water, (8, 10), 5, PALETTE[3])
    # Shimmer
    water.set_at((6, 8), (200, 220, 255))
    water.set_at((10, 9), (200, 220, 255))
    save_surface(os.path.join(output_dir, "water.png"), water)

    # Driftwood (16x16)
    driftwood = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (160, 130, 90),   # Light brown (wood)
        2: (130, 100, 70),   # Dark brown (shadows)
    }
    # Driftwood (curved log shape)
    rectangle(driftwood, (3, 8, 10, 2), PALETTE[1])
    rectangle(driftwood, (4, 9, 8, 1), PALETTE[2])
    rectangle(driftwood, (5, 7, 3, 1), PALETTE[1])
    save_surface(os.path.join(output_dir, "driftwood.png"), driftwood)

    # Shell Beach (16x16)
    shell = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (240, 230, 200),  # Shell white
        2: (220, 200, 170),  # Shell cream
        3: (200, 180, 150),  # Shell edge
    }
    # Shell (half-circle)
    for y in range(16):
        for x in range(16):
            dist = ((x - 8) ** 2 + (y - 10) ** 2) ** 0.5
            if dist <= 5 and y <= 10:
                shell.set_at((x, y), PALETTE[1])
    shell.set_at((6, 9), PALETTE[2])
    shell.set_at((10, 9), PALETTE[2])
    save_surface(os.path.join(output_dir, "shell.png"), shell)

    # Fish Spot (16x16)
    fish = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 180, 200),  # Silver (fish body)
        2: (150, 150, 170),  # Dark silver (shadows)
        3: (60, 120, 200),   # Blue (water hint)
    }
    # Water background
    circle(fish, (8, 9), 6, PALETTE[3])
    # Fish (oval)
    circle(fish, (8, 9), 3, PALETTE[1])
    fish.set_at((7, 9), PALETTE[2])
    fish.set_at((9, 9), PALETTE[2])
    save_surface(os.path.join(output_dir, "fish.png"), fish)

    # Salt Deposit (16x16)
    salt = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 230, 240),  # White (salt)
        2: (200, 200, 210),  # Light grey (edges)
    }
    # Salt crystals (small squares)
    rectangle(salt, (5, 8, 2, 2), PALETTE[1])
    rectangle(salt, (9, 7, 2, 2), PALETTE[1])
    rectangle(salt, (7, 10, 2, 2), PALETTE[1])
    salt.set_at((6, 9), PALETTE[2])
    salt.set_at((10, 8), PALETTE[2])
    save_surface(os.path.join(output_dir, "salt.png"), salt)

    # Peat Mound (16x16)
    peat = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 40, 30),     # Dark brown (peat)
        2: (80, 60, 40),     # Medium brown (highlights)
    }
    circle(peat, (8, 10), 5, PALETTE[1])
    circle(peat, (7, 9), 3, PALETTE[2])
    save_surface(os.path.join(output_dir, "peat.png"), peat)

    # Toxic Reed (16x16)
    toxic_reed = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 120, 40),    # Toxic green (stem)
        2: (100, 150, 50),   # Bright green (tips)
    }
    rectangle(toxic_reed, (7, 4, 1, 11), PALETTE[1])
    rectangle(toxic_reed, (9, 5, 1, 10), PALETTE[1])
    rectangle(toxic_reed, (6, 3, 1, 9), PALETTE[1])
    # Tips
    toxic_reed.set_at((7, 4), PALETTE[2])
    toxic_reed.set_at((9, 5), PALETTE[2])
    toxic_reed.set_at((6, 3), PALETTE[2])
    save_surface(os.path.join(output_dir, "toxic_reed.png"), toxic_reed)

    # Sand Deposit (16x16)
    sand = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (210, 190, 140),  # Sand yellow
        2: (190, 170, 120),  # Dark sand
    }
    circle(sand, (8, 10), 5, PALETTE[1])
    sand.set_at((6, 9), PALETTE[2])
    sand.set_at((10, 10), PALETTE[2])
    save_surface(os.path.join(output_dir, "sand.png"), sand)

    # Salt Crystal (16x16)
    salt_crystal = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 220, 250),  # White-blue (crystal)
        2: (180, 180, 220),  # Grey-blue (shadows)
    }
    # Crystal (tall diamond)
    polygon(salt_crystal, [(8, 3), (11, 8), (8, 14), (5, 8)], PALETTE[1])
    salt_crystal.set_at((8, 7), PALETTE[2])
    save_surface(os.path.join(output_dir, "salt_crystal.png"), salt_crystal)

    # Cactus (16x16)
    cactus = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (40, 120, 40),    # Green (cactus body)
        2: (60, 150, 60),    # Light green (highlights)
    }
    # Main body
    rectangle(cactus, (6, 4, 4, 11), PALETTE[1])
    # Arms
    rectangle(cactus, (4, 7, 2, 4), PALETTE[1])
    rectangle(cactus, (10, 8, 2, 3), PALETTE[1])
    # Highlights
    rectangle(cactus, (7, 5, 1, 9), PALETTE[2])
    save_surface(os.path.join(output_dir, "cactus.png"), cactus)

    print("  Generated 15 world resource sprites")


# ── Monster Sprites ───────────────────────────────────────────────────

def generate_monster_sprites() -> None:
    """Generate monster sprites."""
    print("\n=== Generating Monster Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "monster")

    monsters = {
        "wolf": {
            "colors": [(160, 160, 160), (130, 130, 130), (200, 200, 200)],
            "desc": "grey wolf, oval body, pointed ears",
        },
        "bear": {
            "colors": [(100, 60, 30), (80, 50, 25), (120, 80, 40)],
            "desc": "brown bear, larger oval body, small round ears",
        },
        "goblin": {
            "colors": [(60, 140, 60), (50, 120, 50), (80, 160, 80)],
            "desc": "green goblin, small body, pointed ears",
        },
        "poison_frog": {
            "colors": [(180, 220, 50), (150, 200, 40), (200, 240, 70)],
            "desc": "bright green/yellow frog, small round",
        },
        "crocodile": {
            "colors": [(50, 100, 50), (40, 80, 40), (70, 120, 70)],
            "desc": "dark green crocodile, elongated body",
        },
        "swamp_drake": {
            "colors": [(80, 120, 80), (60, 100, 60), (100, 140, 100)],
            "desc": "swamp drake, dragon-like, small wings",
        },
        "scorpion": {
            "colors": [(180, 140, 50), (150, 120, 40), (200, 160, 60)],
            "desc": "brown scorpion, oval body, curved tail",
        },
        "sand_worm": {
            "colors": [(200, 180, 120), (180, 160, 100), (220, 200, 140)],
            "desc": "sand worm, segmented, curved",
        },
        "djinn": {
            "colors": [(200, 150, 50), (180, 130, 40), (220, 170, 70)],
            "desc": "djinn, mystical, floating, ethereal",
        },
        "stone_golem": {
            "colors": [(140, 140, 150), (120, 120, 130), (160, 160, 170)],
            "desc": "stone golem, blocky, large",
        },
        "eagle": {
            "colors": [(120, 80, 40), (100, 70, 30), (140, 100, 50)],
            "desc": "eagle, wings spread, brown",
        },
        "cave_troll": {
            "colors": [(100, 110, 80), (80, 90, 70), (120, 130, 100)],
            "desc": "cave troll, large, greenish grey",
        },
        "boar": {
            "colors": [(120, 80, 50), (100, 70, 40), (140, 100, 60)],
            "desc": "boar, brown, tusks",
        },
        "snake": {
            "colors": [(80, 160, 60), (70, 140, 50), (100, 180, 80)],
            "desc": "snake, coiled, green",
        },
        "hawk": {
            "colors": [(140, 120, 80), (120, 100, 70), (160, 140, 100)],
            "desc": "hawk, light brown, wings spread",
        },
        "crab": {
            "colors": [(200, 100, 80), (180, 80, 60), (220, 120, 100)],
            "desc": "crab, red, pincers, round body",
        },
        "sea_serpent": {
            "colors": [(50, 100, 160), (40, 80, 140), (70, 120, 180)],
            "desc": "sea serpent, blue, long wavy body",
        },
    }

    for name, info in monsters.items():
        sprite = pygame.Surface((MONSTER_SIZE, MONSTER_SIZE), pygame.SRCALPHA)
        c1, c2, c3 = info["colors"]
        
        cx, cy = 8, 9

        # Generic body (oval)
        circle(sprite, (cx, cy), 5, c1)
        circle(sprite, (cx - 1, cy - 1), 3, c2)
        circle(sprite, (cx + 1, cy - 1), 3, c3)
        
        # Eyes
        sprite.set_at((6, 8), (255, 255, 255))
        sprite.set_at((10, 8), (255, 255, 255))
        sprite.set_at((6, 8), (0, 0, 0))
        sprite.set_at((10, 8), (0, 0, 0))
        
        # Add monster-specific features
        if name == "wolf":
            # Pointed ears
            sprite.set_at((5, 5), c1)
            sprite.set_at((11, 5), c1)
            sprite.set_at((5, 6), c1)
            sprite.set_at((11, 6), c1)
        elif name == "bear":
            # Small round ears
            circle(sprite, (5, 5), 2, c1)
            circle(sprite, (11, 5), 2, c1)
        elif name == "goblin":
            # Pointed ears
            sprite.set_at((4, 6), c1)
            sprite.set_at((12, 6), c1)
            sprite.set_at((4, 7), c1)
            sprite.set_at((12, 7), c1)
        elif name == "crocodile":
            # Elongated snout
            rectangle(sprite, (12, 8, 3, 2), c1)
        elif name == "scorpion":
            # Curved tail
            sprite.set_at((8, 14), c1)
            sprite.set_at((9, 15), c1)
            sprite.set_at((10, 15), c1)
        elif name == "crab":
            # Pincers
            sprite.set_at((2, 8), c1)
            sprite.set_at((14, 8), c1)
            sprite.set_at((2, 9), c1)
            sprite.set_at((14, 9), c1)
        elif name == "eagle" or name == "hawk":
            # Wings spread
            sprite.set_at((2, 7), c1)
            sprite.set_at((3, 8), c1)
            sprite.set_at((13, 7), c1)
            sprite.set_at((14, 8), c1)
        elif name == "snake":
            # Coiled shape (wavy line)
            sprite.set_at((5, 13), c1)
            sprite.set_at((7, 14), c1)
            sprite.set_at((9, 13), c1)
            sprite.set_at((11, 14), c1)
        elif name == "stone_golem":
            # Blocky shape
            rectangle(sprite, (4, 6, 8, 8), c1)
        
        save_surface(os.path.join(output_dir, f"{name}.png"), sprite)

    print(f"  Generated 17 monster sprites")


# ── Structure Sprites ─────────────────────────────────────────────────

def generate_structure_sprites() -> None:
    """Generate structure sprites."""
    print("\n=== Generating Structure Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "structure")

    structures = {
        "campfire": {
            "colors": [(139, 90, 43), (255, 140, 20), (255, 200, 50), (100, 80, 60)],
            "desc": "campfire with logs and flames",
        },
        "chest": {
            "colors": [(160, 120, 60), (140, 100, 50), (200, 180, 100), (180, 140, 70)],
            "desc": "wooden chest with gold lock",
        },
        "furnace": {
            "colors": [(100, 100, 110), (80, 80, 90), (120, 120, 130), (200, 100, 30)],
            "desc": "stone furnace with fire inside",
        },
        "cooking_station": {
            "colors": [(120, 100, 80), (100, 80, 60), (140, 120, 100), (80, 60, 40)],
            "desc": "cooking station with grill",
        },
        "drying_rack": {
            "colors": [(140, 120, 80), (120, 100, 60), (160, 140, 100)],
            "desc": "wooden drying rack",
        },
        "smelter": {
            "colors": [(90, 90, 100), (70, 70, 80), (110, 110, 120), (200, 120, 40)],
            "desc": "smelter with molten metal",
        },
        "stone_wall": {
            "colors": [(130, 130, 140), (110, 110, 120), (150, 150, 160), (90, 90, 100)],
            "desc": "stone wall with blocks",
        },
        "wooden_gate": {
            "colors": [(140, 100, 50), (120, 80, 40), (160, 120, 60)],
            "desc": "wooden gate",
        },
        "iron_gate": {
            "colors": [(100, 100, 110), (80, 80, 90), (120, 120, 130)],
            "desc": "iron gate",
        },
        "wall_tower": {
            "colors": [(140, 140, 150), (120, 120, 130), (160, 160, 170), (100, 100, 110)],
            "desc": "stone tower",
        },
        "wooden_trap": {
            "colors": [(120, 90, 40), (100, 80, 30), (140, 110, 50)],
            "desc": "wooden spike trap",
        },
        "iron_trap": {
            "colors": [(80, 80, 90), (70, 70, 80), (100, 100, 110)],
            "desc": "iron spike trap",
        },
        "ballista": {
            "colors": [(120, 100, 60), (100, 80, 50), (140, 120, 80), (100, 100, 110)],
            "desc": "ballista siege weapon",
        },
        "trebuchet": {
            "colors": [(100, 90, 60), (80, 70, 50), (120, 110, 80)],
            "desc": "trebuchet siege engine",
        },
        "tapestry": {
            "colors": [(160, 100, 160), (140, 80, 140), (180, 120, 180)],
            "desc": "purple tapestry",
        },
        "lantern": {
            "colors": [(200, 180, 100), (180, 160, 80), (220, 200, 120), (255, 220, 100)],
            "desc": "lantern with glow",
        },
        "garden_plot": {
            "colors": [(80, 140, 60), (60, 120, 50), (100, 160, 80), (100, 80, 60)],
            "desc": "garden with green plants",
        },
        "stone_bench": {
            "colors": [(130, 130, 140), (110, 110, 120), (150, 150, 160)],
            "desc": "stone bench",
        },
    }

    for name, info in structures.items():
        sprite = pygame.Surface((STRUCTURE_SIZE, STRUCTURE_SIZE), pygame.SRCALPHA)
        colors = info["colors"]
        c1 = colors[0]
        c2 = colors[1] if len(colors) > 1 else c1
        c3 = colors[2] if len(colors) > 2 else c1
        extras = colors[3:] if len(colors) > 3 else []
        
        # Draw base rectangle (body)
        rect_y = 8 if name == "stone_wall" or name == "wall_tower" else 7
        rect_h = 10 if name in ("stone_wall", "wall_tower") else 9
        rectangle(sprite, (3, rect_y, 10, rect_h), c1)
        
        # Add details based on type
        if name == "campfire":
            # Logs at base
            log_color = extras[0] if len(extras) > 0 else c2
            rectangle(sprite, (4, 11, 8, 2), log_color)
            # Flames
            circle(sprite, (8, 8), 3, c2)
            circle(sprite, (8, 7), 2, c3)
        elif name == "chest":
            # Lid line
            rectangle(sprite, (3, 9, 10, 1), c2)
            # Gold lock
            lock_color = extras[0] if len(extras) > 0 else c3
            sprite.set_at((8, 9), lock_color)
            sprite.set_at((8, 10), lock_color)
        elif name == "furnace":
            # Fire opening
            fire_color = extras[0] if len(extras) > 0 else c2
            rectangle(sprite, (6, 10, 4, 3), fire_color)
            circle(sprite, (8, 11), 1, c3)
        elif name == "stone_wall" or name == "wall_tower":
            # Stone block pattern
            rectangle(sprite, (3, 8, 10, 1), c2)
            rectangle(sprite, (3, 12, 10, 1), c2)
            rectangle(sprite, (7, 8, 1, 6), c2)
        elif name == "lantern":
            # Lantern body
            rectangle(sprite, (6, 6, 4, 6), c1)
            # Glow
            glow_color = extras[0] if len(extras) > 0 else c3
            circle(sprite, (8, 9), 2, glow_color)
        elif name in ("wooden_gate", "iron_gate"):
            # Gate bars
            rectangle(sprite, (4, 6, 1, 10), c2)
            rectangle(sprite, (7, 6, 1, 10), c2)
            rectangle(sprite, (11, 6, 1, 10), c2)
        elif name == "garden_plot":
            # Soil
            soil_color = extras[0] if len(extras) > 0 else (100, 80, 60)
            rectangle(sprite, (3, 10, 10, 4), soil_color)
            # Plants
            rectangle(sprite, (5, 6, 1, 5), c1)
            rectangle(sprite, (8, 7, 1, 4), c3)
            rectangle(sprite, (11, 6, 1, 5), c1)
        else:
            # Generic highlight
            rectangle(sprite, (4, rect_y, 1, rect_h), c3)
        
        save_surface(os.path.join(output_dir, f"{name}.png"), sprite)

    print(f"  Generated 18 structure sprites")


# ── NPC Sprites ───────────────────────────────────────────────────────

def generate_npc_sprites() -> None:
    """Generate NPC sprites."""
    print("\n=== Generating NPC Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "npcs")

    npc_types = {
        "merchant": (100, 180, 100),   # Green
        "quest_giver": (100, 140, 200), # Blue
        "faction_leader": (200, 100, 100), # Red
        "recruit": (200, 180, 80),      # Yellow
    }

    for npc_name, color in npc_types.items():
        sprite = pygame.Surface((NPC_SIZE, NPC_SIZE), pygame.SRCALPHA)
        
        # Head
        circle(sprite, (8, 5), 3, (255, 220, 180))
        circle(sprite, (8, 4), 3, (139, 90, 43))  # Hair
        
        # Eyes
        sprite.set_at((6, 5), (30, 30, 30))
        sprite.set_at((10, 5), (30, 30, 30))
        
        # Body
        rectangle(sprite, (6, 8, 4, 5), color)
        
        # Belt
        rectangle(sprite, (6, 12, 4, 1), (100, 80, 60))
        
        # Boots
        rectangle(sprite, (6, 14, 1, 2), (80, 60, 40))
        rectangle(sprite, (9, 14, 1, 2), (80, 60, 40))
        
        save_surface(os.path.join(output_dir, f"{npc_name}.png"), sprite)

    print(f"  Generated 4 NPC sprites")


# ── Terrain Sprites ───────────────────────────────────────────────────

def generate_terrain_sprites() -> None:
    """Generate terrain tile sprites."""
    print("\n=== Generating Terrain Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "terrain")

    biomes = {
        "forest": (50, 120, 50),     # Green
        "plains": (140, 160, 80),    # Yellow-green
        "coastal": (210, 190, 140),  # Sand
        "swamp": (60, 80, 50),       # Dark green-brown
        "mountains": (120, 120, 130), # Grey
        "desert": (210, 180, 120),   # Yellow sand
    }

    for biome_name, base_color in biomes.items():
        tile = pygame.Surface((TERRAIN_SIZE, TERRAIN_SIZE), pygame.SRCALPHA)
        
        # Base fill
        rectangle(tile, (0, 0, TERRAIN_SIZE, TERRAIN_SIZE), base_color)
        
        # Add variation (darker/lighter patches)
        import random
        random.seed(hash(biome_name))  # Deterministic per biome
        for _ in range(20):
            x = random.randint(0, TERRAIN_SIZE - 8)
            y = random.randint(0, TERRAIN_SIZE - 8)
            w = random.randint(4, 12)
            h = random.randint(4, 12)
            variation = tuple(max(0, min(255, c + random.randint(-20, 20))) for c in base_color)
            rectangle(tile, (x, y, w, h), variation)
        
        # Add some texture details
        if biome_name == "forest":
            # Tree shadows (darker circles)
            for _ in range(5):
                x = random.randint(5, TERRAIN_SIZE - 15)
                y = random.randint(5, TERRAIN_SIZE - 15)
                circle(tile, (x, y), random.randint(3, 6), (40, 100, 40))
        elif biome_name == "coastal":
            # Sand grains (lighter dots)
            for _ in range(30):
                x = random.randint(0, TERRAIN_SIZE - 1)
                y = random.randint(0, TERRAIN_SIZE - 1)
                tile.set_at((x, y), (220, 200, 160))
        elif biome_name == "mountains":
            # Rock patches
            for _ in range(8):
                x = random.randint(0, TERRAIN_SIZE - 10)
                y = random.randint(0, TERRAIN_SIZE - 10)
                rectangle(tile, (x, y, random.randint(5, 10), random.randint(5, 10)), (100, 100, 110))
        elif biome_name == "swamp":
            # Water reflections
            for _ in range(10):
                x = random.randint(0, TERRAIN_SIZE - 8)
                y = random.randint(0, TERRAIN_SIZE - 8)
                rectangle(tile, (x, y, random.randint(4, 8), 2), (80, 100, 80))
        elif biome_name == "desert":
            # Dune shadows
            for _ in range(15):
                x = random.randint(0, TERRAIN_SIZE - 10)
                y = random.randint(0, TERRAIN_SIZE - 10)
                rectangle(tile, (x, y, random.randint(8, 15), random.randint(2, 4)), (190, 160, 100))
        
        save_surface(os.path.join(output_dir, f"{biome_name}.png"), tile)

    print(f"  Generated 6 terrain sprites")


# ── Item Sprites ──────────────────────────────────────────────────────

def generate_item_sprites() -> None:
    """Generate item sprites for inventory/crafting display."""
    print("\n=== Generating Item Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "items")

    # ── Helper: Draw a generic item outline ──
    def draw_item_outline(surface, cx, cy, radius, color):
        """Draw a small circle outline for item backgrounds."""
        for angle in range(0, 360, 8):
            import math
            ax = int(cx + radius * math.cos(math.radians(angle)))
            ay = int(cy + radius * math.sin(math.radians(angle)))
            if 0 <= ax < surface.get_width() and 0 <= ay < surface.get_height():
                surface.set_at((ax, ay), color)

    # ── Helper: Draw a generic item background circle ──
    def draw_item_bg(surface, cx, cy, radius, color):
        """Draw a filled circle as item background."""
        for y in range(max(0, cy - radius), min(surface.get_height(), cy + radius + 1)):
            for x in range(max(0, cx - radius), min(surface.get_width(), cx + radius + 1)):
                dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if dist <= radius:
                    surface.set_at((x, y), color)

    # ── Tool: Axe (16x16) ──
    axe = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (139, 90, 43),    # Brown (handle)
        2: (100, 70, 35),    # Dark brown (handle shadow)
        3: (140, 140, 150),  # Steel (head)
        4: (170, 170, 180),  # Light steel (edge)
        5: (100, 100, 110),  # Dark steel
    }
    # Handle
    rectangle(axe, (8, 6, 2, 8), PALETTE[1])
    rectangle(axe, (8, 10, 2, 4), PALETTE[2])
    # Head
    rectangle(axe, (4, 4, 6, 3), PALETTE[3])
    rectangle(axe, (4, 4, 1, 3), PALETTE[4])  # Edge highlight
    rectangle(axe, (9, 4, 1, 3), PALETTE[5])  # Shadow side
    # Curved blade shape
    axe.set_at((5, 3), PALETTE[3])
    axe.set_at((6, 3), PALETTE[4])
    axe.set_at((7, 3), PALETTE[3])
    axe.set_at((5, 8), PALETTE[3])
    save_surface(os.path.join(output_dir, "axe.png"), axe)

    # ── Tool: Pickaxe (16x16) ──
    pick = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (139, 90, 43),    # Brown (handle)
        2: (100, 70, 35),    # Dark brown
        3: (140, 140, 150),  # Steel
        4: (170, 170, 180),  # Light steel
        5: (100, 100, 110),  # Dark steel
    }
    # Handle
    rectangle(pick, (7, 5, 2, 9), PALETTE[1])
    rectangle(pick, (7, 8, 2, 5), PALETTE[2])
    # Horizontal head (Y shape)
    rectangle(pick, (3, 3, 10, 2), PALETTE[3])
    # Left tip (pointed)
    pick.set_at((3, 2), PALETTE[4])
    pick.set_at((3, 3), PALETTE[4])
    pick.set_at((4, 2), PALETTE[3])
    # Right tip (pointed)
    pick.set_at((12, 2), PALETTE[4])
    pick.set_at((12, 3), PALETTE[4])
    pick.set_at((11, 2), PALETTE[3])
    # Center connector
    rectangle(pick, (7, 2, 2, 3), PALETTE[5])
    # Highlight edge
    pick.set_at((5, 3), PALETTE[4])
    pick.set_at((9, 3), PALETTE[4])
    save_surface(os.path.join(output_dir, "pickaxe.png"), pick)

    # ── Log: Oak Logs (16x16) ──
    logs = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (139, 90, 43),    # Brown (log)
        2: (110, 70, 35),    # Dark brown
        3: (160, 105, 50),   # Light brown
        4: (80, 50, 25),     # Very dark (end grain)
    }
    # Log body (horizontal)
    rectangle(logs, (3, 7, 10, 4), PALETTE[1])
    rectangle(logs, (3, 9, 10, 2), PALETTE[2])
    # End grain circles
    circle(logs, (3, 9), 2, PALETTE[4])
    circle(logs, (3, 8), 1, PALETTE[3])
    # Bark texture
    logs.set_at((5, 7), PALETTE[3])
    logs.set_at((8, 7), PALETTE[3])
    logs.set_at((10, 8), PALETTE[3])
    save_surface(os.path.join(output_dir, "logs_oak.png"), logs)

    # ── Planks (16x16) ──
    planks = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 140, 70),    # Light wood
        2: (160, 120, 60),    # Medium wood
        3: (140, 100, 50),    # Dark wood
        4: (200, 160, 80),    # Highlight
    }
    # Plank lines
    rectangle(planks, (2, 4, 12, 8), PALETTE[1])
    rectangle(planks, (2, 8, 12, 1), PALETTE[3])
    rectangle(planks, (2, 10, 12, 1), PALETTE[3])
    rectangle(planks, (2, 12, 12, 1), PALETTE[3])
    # Wood grain
    planks.set_at((4, 5), PALETTE[4])
    planks.set_at((8, 6), PALETTE[4])
    planks.set_at((6, 9), PALETTE[4])
    planks.set_at((10, 11), PALETTE[4])
    save_surface(os.path.join(output_dir, "planks.png"), planks)

    # ── Stick (16x16) ──
    stick = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (120, 80, 40),    # Brown
        2: (100, 65, 30),    # Dark brown
        3: (140, 100, 50),   # Light brown
    }
    # Diagonal stick
    for i in range(12):
        x = 3 + i
        y = 13 - i
        if 0 <= x < 16 and 0 <= y < 16:
            stick.set_at((x, y), PALETTE[1])
            if y + 1 < 16:
                stick.set_at((x, y + 1), PALETTE[2])
    stick.set_at((14, 1), PALETTE[3])  # Tip
    stick.set_at((3, 13), PALETTE[2])  # Base
    save_surface(os.path.join(output_dir, "stick.png"), stick)

    # ── Charcoal (16x16) ──
    charcoal = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (30, 30, 35),     # Very dark grey
        2: (50, 50, 55),     # Dark grey
        3: (20, 20, 25),     # Near black
    }
    # Charcoal chunk (irregular)
    circle(charcoal, (8, 9), 5, PALETTE[1])
    circle(charcoal, (7, 8), 3, PALETTE[2])
    circle(charcoal, (9, 10), 2, PALETTE[2])
    charcoal.set_at((8, 8), PALETTE[3])
    charcoal.set_at((6, 9), PALETTE[3])
    charcoal.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "charcoal.png"), charcoal)

    # ── Fired Brick (16x16) ──
    brick = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 80, 50),    # Red-brown
        2: (160, 65, 40),    # Dark red
        3: (200, 100, 60),   # Light red
        4: (140, 55, 35),    # Very dark
    }
    # Brick rectangle
    rectangle(brick, (2, 5, 12, 7), PALETTE[1])
    rectangle(brick, (2, 10, 12, 1), PALETTE[4])  # Bottom shadow
    rectangle(brick, (2, 5, 12, 1), PALETTE[3])  # Top highlight
    # Mortar lines
    rectangle(brick, (6, 5, 1, 7), PALETTE[2])
    rectangle(brick, (10, 5, 1, 7), PALETTE[2])
    brick.set_at((4, 8), PALETTE[3])
    brick.set_at((8, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "brick.png"), brick)

    # ── Cobblestone (16x16) ──
    cobble = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (120, 120, 130),   # Grey
        2: (100, 100, 110),   # Dark grey
        3: (140, 140, 150),   # Light grey
        4: (80, 80, 90),      # Very dark
    }
    # Cluster of rounded stones
    circle(cobble, (5, 7), 3, PALETTE[1])
    circle(cobble, (10, 6), 3, PALETTE[1])
    circle(cobble, (8, 11), 3, PALETTE[2])
    circle(cobble, (4, 11), 2, PALETTE[2])
    circle(cobble, (12, 10), 2, PALETTE[1])
    # Highlights
    cobble.set_at((5, 6), PALETTE[3])
    cobble.set_at((10, 5), PALETTE[3])
    cobble.set_at((8, 10), PALETTE[3])
    # Shadow gaps
    cobble.set_at((7, 8), PALETTE[4])
    cobble.set_at((11, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "cobblestone.png"), cobble)

    # ── Sand (16x16) ──
    sand_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (210, 190, 140),  # Sand yellow
        2: (190, 170, 120),  # Dark sand
        3: (230, 210, 160),  # Light sand
    }
    # Pile of sand
    circle(sand_item, (8, 10), 5, PALETTE[1])
    circle(sand_item, (7, 9), 3, PALETTE[3])
    circle(sand_item, (9, 10), 2, PALETTE[2])
    sand_item.set_at((6, 10), PALETTE[3])
    sand_item.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "sand.png"), sand_item)

    # ── Ingots (generic function) ──
    def make_ingot(filename, name_color, highlight_color, shadow_color):
        ingot = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
        PALETTE = {
            1: name_color,
            2: highlight_color,
            3: shadow_color,
            4: (80, 80, 90),  # Dark grey base
        }
        # Ingot shape (trapezoid-ish)
        rectangle(ingot, (4, 8, 8, 5), PALETTE[4])
        rectangle(ingot, (4, 8, 8, 1), PALETTE[1])  # Top surface
        rectangle(ingot, (4, 10, 1, 3), PALETTE[2])  # Left highlight
        rectangle(ingot, (11, 10, 1, 3), PALETTE[3])  # Right shadow
        # Top edge
        ingot.set_at((5, 7), PALETTE[2])
        ingot.set_at((6, 7), PALETTE[2])
        ingot.set_at((9, 7), PALETTE[1])
        ingot.set_at((10, 7), PALETTE[1])
        save_surface(os.path.join(output_dir, filename), ingot)

    make_ingot("ingot_iron.png", (140, 140, 155), (170, 170, 185), (110, 110, 120))
    make_ingot("ingot_copper.png", (180, 120, 80), (200, 140, 90), (150, 100, 60))
    make_ingot("ingot_bronze.png", (180, 150, 100), (200, 170, 120), (150, 125, 80))
    make_ingot("ingot_steel.png", (120, 130, 150), (150, 160, 180), (90, 100, 120))
    make_ingot("ingot_iron_raw.png", (130, 130, 140), (155, 155, 165), (100, 100, 110))

    # ── Raw Fish (16x16) ──
    fish_raw = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 180, 200),  # Silver
        2: (150, 150, 170),  # Dark silver
        3: (120, 130, 160),  # Blue tint
        4: (200, 200, 220),  # Highlight
    }
    # Fish body (oval)
    circle(fish_raw, (8, 9), 4, PALETTE[1])
    circle(fish_raw, (7, 8), 3, PALETTE[2])
    # Tail
    fish_raw.set_at((3, 8), PALETTE[1])
    fish_raw.set_at((3, 9), PALETTE[2])
    fish_raw.set_at((4, 7), PALETTE[1])
    fish_raw.set_at((4, 10), PALETTE[2])
    # Eye
    fish_raw.set_at((11, 8), (30, 30, 30))
    fish_raw.set_at((11, 9), (30, 30, 30))
    # Scale highlights
    fish_raw.set_at((7, 8), PALETTE[4])
    fish_raw.set_at((9, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "fish_raw.png"), fish_raw)

    # ── Cooked Fish (16x16) ──
    fish_cooked = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 160, 100),  # Golden brown
        2: (180, 130, 70),   # Dark golden
        3: (220, 180, 120),  # Light golden
        4: (160, 100, 50),   # Very dark
    }
    circle(fish_cooked, (8, 9), 4, PALETTE[1])
    circle(fish_cooked, (7, 8), 3, PALETTE[2])
    fish_cooked.set_at((3, 8), PALETTE[1])
    fish_cooked.set_at((3, 9), PALETTE[2])
    fish_cooked.set_at((4, 7), PALETTE[1])
    fish_cooked.set_at((11, 8), (40, 30, 20))  # Eye
    fish_cooked.set_at((8, 7), PALETTE[3])
    fish_cooked.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "fish_cooked.png"), fish_cooked)

    # ── Cooked Chicken (16x16) ──
    chicken_cooked = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (210, 170, 100),  # Golden brown
        2: (190, 140, 70),   # Dark golden
        3: (230, 190, 120),  # Light golden
    }
    # Drumstick shape
    rectangle(chicken_cooked, (5, 10, 6, 3), PALETTE[1])
    circle(chicken_cooked, (10, 11), 4, PALETTE[1])
    circle(chicken_cooked, (10, 11), 3, PALETTE[2])
    circle(chicken_cooked, (11, 10), 2, PALETTE[3])
    # Bone
    rectangle(chicken_cooked, (3, 9, 3, 2), PALETTE[3])
    chicken_cooked.set_at((5, 8), PALETTE[3])
    chicken_cooked.set_at((2, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "chicken_cooked.png"), chicken_cooked)

    # ── Cooked Meat (16x16) ──
    meat_cooked = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 100, 60),   # Brown
        2: (150, 80, 45),    # Dark brown
        3: (200, 120, 70),   # Light brown
        4: (130, 65, 35),    # Very dark
    }
    rectangle(meat_cooked, (3, 6, 10, 6), PALETTE[1])
    rectangle(meat_cooked, (3, 10, 10, 1), PALETTE[4])
    circle(meat_cooked, (8, 9), 4, PALETTE[1])
    circle(meat_cooked, (7, 8), 3, PALETTE[2])
    meat_cooked.set_at((6, 7), PALETTE[3])
    meat_cooked.set_at((10, 8), PALETTE[3])
    meat_cooked.set_at((8, 11), PALETTE[3])
    save_surface(os.path.join(output_dir, "meat_cooked.png"), meat_cooked)

    # ── Raw Chicken (16x16) ──
    chicken_raw = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 200, 180),  # Pale pink
        2: (200, 180, 160),  # Darker pink
        3: (240, 220, 200),  # Light pink
        4: (180, 160, 140),  # Very dark pink
    }
    circle(chicken_raw, (8, 9), 4, PALETTE[1])
    circle(chicken_raw, (7, 8), 3, PALETTE[2])
    rectangle(chicken_raw, (3, 8, 3, 3), PALETTE[2])
    chicken_raw.set_at((11, 8), PALETTE[3])
    chicken_raw.set_at((7, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "chicken_raw.png"), chicken_raw)

    # ── Raw Meat (16x16) ──
    meat_raw = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 100, 100),  # Red
        2: (170, 80, 80),    # Dark red
        3: (220, 120, 120),  # Light red
    }
    rectangle(meat_raw, (3, 6, 10, 6), PALETTE[1])
    circle(meat_raw, (8, 9), 4, PALETTE[1])
    circle(meat_raw, (7, 8), 3, PALETTE[2])
    meat_raw.set_at((6, 7), PALETTE[3])
    meat_raw.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "meat_raw.png"), meat_raw)

    # ── Boar Meat (16x16) ──
    meat_boar = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 80, 80),    # Dark red
        2: (150, 60, 60),    # Very dark red
        3: (200, 100, 100),  # Light red
    }
    rectangle(meat_boar, (3, 6, 10, 6), PALETTE[1])
    circle(meat_boar, (8, 9), 4, PALETTE[1])
    circle(meat_boar, (7, 8), 3, PALETTE[2])
    meat_boar.set_at((6, 7), PALETTE[3])
    meat_boar.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "meat_boar_raw.png"), meat_boar)

    # ── Crab Meat (16x16) ──
    meat_crab = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (240, 230, 220),  # White
        2: (220, 210, 200),  # Off-white
        3: (200, 190, 180),  # Darker off-white
    }
    circle(meat_crab, (8, 9), 4, PALETTE[1])
    circle(meat_crab, (7, 8), 3, PALETTE[2])
    meat_crab.set_at((6, 7), PALETTE[3])
    meat_crab.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "meat_crab_raw.png"), meat_crab)

    # ── Berries (16x16) ──
    berries = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 50, 50),    # Red
        2: (170, 40, 40),    # Dark red
        3: (230, 80, 80),    # Bright red
    }
    # Cluster of berries
    circle(berries, (6, 8), 2, PALETTE[1])
    circle(berries, (9, 7), 2, PALETTE[1])
    circle(berries, (7, 11), 2, PALETTE[1])
    circle(berries, (10, 10), 2, PALETTE[1])
    circle(berries, (8, 9), 1, PALETTE[2])
    # Highlights
    berries.set_at((6, 7), PALETTE[3])
    berries.set_at((9, 6), PALETTE[3])
    berries.set_at((7, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "berries.png"), berries)

    # ── Herb (item version) (16x16) ──
    herb_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (34, 120, 34),    # Green
        2: (50, 150, 50),    # Light green
        3: (80, 60, 40),     # Brown (stem)
    }
    rectangle(herb_item, (7, 5, 2, 8), PALETTE[3])
    circle(herb_item, (6, 6), 2, PALETTE[1])
    circle(herb_item, (10, 6), 2, PALETTE[2])
    circle(herb_item, (8, 4), 2, PALETTE[1])
    herb_item.set_at((6, 5), PALETTE[2])
    herb_item.set_at((10, 5), PALETTE[2])
    save_surface(os.path.join(output_dir, "herb.png"), herb_item)

    # ── Fibers (16x16) ──
    fibers = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (140, 130, 80),   # Tan
        2: (160, 150, 100),  # Light tan
        3: (120, 110, 70),   # Dark tan
    }
    # Bundle of fibers
    rectangle(fibers, (6, 4, 1, 10), PALETTE[1])
    rectangle(fibers, (8, 4, 1, 10), PALETTE[1])
    rectangle(fibers, (10, 4, 1, 10), PALETTE[1])
    rectangle(fibers, (7, 5, 1, 8), PALETTE[2])
    rectangle(fibers, (9, 5, 1, 8), PALETTE[2])
    # Wrap at bottom
    rectangle(fibers, (5, 12, 7, 2), PALETTE[3])
    save_surface(os.path.join(output_dir, "fibers.png"), fibers)

    # ── Grass (16x16) ──
    grass_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 130, 50),    # Green
        2: (70, 160, 70),    # Light green
        3: (40, 110, 40),    # Dark green
    }
    # Grass bundle
    rectangle(grass_item, (5, 4, 1, 10), PALETTE[1])
    rectangle(grass_item, (7, 4, 1, 10), PALETTE[1])
    rectangle(grass_item, (9, 4, 1, 10), PALETTE[1])
    rectangle(grass_item, (11, 4, 1, 10), PALETTE[1])
    rectangle(grass_item, (6, 5, 1, 8), PALETTE[2])
    rectangle(grass_item, (8, 5, 1, 8), PALETTE[2])
    rectangle(grass_item, (10, 5, 1, 8), PALETTE[2])
    # Tips
    grass_item.set_at((5, 4), PALETTE[2])
    grass_item.set_at((7, 4), PALETTE[2])
    grass_item.set_at((9, 4), PALETTE[2])
    grass_item.set_at((11, 4), PALETTE[2])
    # Tie at bottom
    rectangle(grass_item, (5, 13, 7, 2), PALETTE[3])
    save_surface(os.path.join(output_dir, "grass.png"), grass_item)

    # ── Wheat (16x16) ──
    wheat_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 180, 80),   # Golden
        2: (220, 200, 100),  # Light golden
        3: (80, 60, 40),     # Brown (stem)
    }
    rectangle(wheat_item, (7, 4, 2, 10), PALETTE[3])
    circle(wheat_item, (8, 4), 3, PALETTE[1])
    circle(wheat_item, (8, 3), 2, PALETTE[2])
    wheat_item.set_at((8, 2), PALETTE[2])
    save_surface(os.path.join(output_dir, "wheat.png"), wheat_item)

    # ── Water (16x16) ──
    water_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 120, 200),   # Blue
        2: (80, 150, 230),   # Light blue
        3: (40, 100, 180),   # Dark blue
    }
    # Water drop/bottle shape
    circle(water_item, (8, 9), 5, PALETTE[1])
    circle(water_item, (8, 8), 4, PALETTE[2])
    circle(water_item, (8, 10), 4, PALETTE[3])
    water_item.set_at((6, 8), (200, 220, 255))
    water_item.set_at((10, 9), (200, 220, 255))
    save_surface(os.path.join(output_dir, "water.png"), water_item)

    # ── Driftwood (16x16) ──
    driftwood_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (160, 130, 90),   # Light brown
        2: (130, 100, 70),   # Dark brown
        3: (180, 150, 100),  # Highlight
    }
    rectangle(driftwood_item, (3, 7, 10, 2), PALETTE[1])
    rectangle(driftwood_item, (4, 8, 8, 1), PALETTE[2])
    driftwood_item.set_at((5, 7), PALETTE[3])
    driftwood_item.set_at((9, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "driftwood.png"), driftwood_item)

    # ── Shells (16x16) ──
    shells = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (240, 230, 200),  # Shell white
        2: (220, 200, 170),  # Cream
        3: (200, 180, 150),  # Edge
    }
    # Half-circle shell
    for y in range(16):
        for x in range(16):
            dist = ((x - 8) ** 2 + (y - 10) ** 2) ** 0.5
            if dist <= 5 and y <= 10:
                shells.set_at((x, y), PALETTE[1])
    shells.set_at((6, 9), PALETTE[2])
    shells.set_at((10, 9), PALETTE[2])
    shells.set_at((8, 8), PALETTE[3])
    save_surface(os.path.join(output_dir, "shells.png"), shells)

    # ── Salt (16x16) ──
    salt_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 230, 240),  # White
        2: (200, 200, 210),  # Light grey
    }
    rectangle(salt_item, (5, 8, 2, 2), PALETTE[1])
    rectangle(salt_item, (9, 7, 2, 2), PALETTE[1])
    rectangle(salt_item, (7, 10, 2, 2), PALETTE[1])
    salt_item.set_at((6, 9), PALETTE[2])
    salt_item.set_at((10, 8), PALETTE[2])
    save_surface(os.path.join(output_dir, "salt.png"), salt_item)

    # ── Peat (16x16) ──
    peat_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 40, 30),     # Dark brown
        2: (80, 60, 40),     # Medium brown
    }
    circle(peat_item, (8, 10), 5, PALETTE[1])
    circle(peat_item, (7, 9), 3, PALETTE[2])
    save_surface(os.path.join(output_dir, "peat.png"), peat_item)

    # ── Toxic Reed (16x16) ──
    toxic_reed_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 120, 40),    # Toxic green
        2: (100, 150, 50),   # Bright green
    }
    rectangle(toxic_reed_item, (7, 4, 1, 11), PALETTE[1])
    rectangle(toxic_reed_item, (9, 5, 1, 10), PALETTE[1])
    rectangle(toxic_reed_item, (6, 3, 1, 9), PALETTE[1])
    toxic_reed_item.set_at((7, 4), PALETTE[2])
    toxic_reed_item.set_at((9, 5), PALETTE[2])
    toxic_reed_item.set_at((6, 3), PALETTE[2])
    save_surface(os.path.join(output_dir, "toxic_reed.png"), toxic_reed_item)

    # ── Ore Sprites ──
    def make_ore(filename, name_color, highlight_color):
        ore = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
        PALETTE = {
            1: (100, 100, 110),  # Grey rock
            2: (80, 80, 90),     # Dark grey
            3: name_color,
            4: highlight_color,
        }
        circle(ore, (8, 9), 5, PALETTE[1])
        circle(ore, (7, 8), 3, PALETTE[2])
        circle(ore, (9, 9), 3, PALETTE[3])
        ore.set_at((8, 7), PALETTE[4])
        ore.set_at((10, 10), PALETTE[4])
        save_surface(os.path.join(output_dir, filename), ore)

    make_ore("ore_iron.png", (160, 160, 170), (180, 180, 190))
    make_ore("ore_copper.png", (180, 120, 80), (200, 140, 90))
    make_ore("ore_gold.png", (220, 180, 40), (240, 200, 60))
    make_ore("ore_tin.png", (150, 160, 170), (170, 180, 190))
    make_ore("ore_rare.png", (180, 100, 220), (200, 140, 240))

    # ── Gemstone (16x16) ──
    gem = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 100, 220),  # Purple
        2: (230, 140, 250),  # Bright purple
        3: (170, 80, 190),   # Dark purple
    }
    polygon(gem, [(8, 4), (12, 8), (8, 13), (4, 8)], PALETTE[1])
    gem.set_at((8, 8), PALETTE[2])
    gem.set_at((7, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "gemstone.png"), gem)

    # ── Raw Gemstone ──
    gem_raw = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 180, 190),  # Grey rock
        2: (200, 100, 220),  # Purple hint
        3: (230, 140, 250),  # Bright
    }
    circle(gem_raw, (8, 9), 5, PALETTE[1])
    polygon(gem_raw, [(8, 5), (11, 9), (8, 13), (5, 9)], PALETTE[2])
    gem_raw.set_at((8, 8), PALETTE[3])
    save_surface(os.path.join(output_dir, "gemstone_raw.png"), gem_raw)

    # ── Monster Drop: Wolf Pelt (16x16) ──
    pelt_wolf = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (160, 160, 160),  # Grey
        2: (130, 130, 130),  # Dark grey
        3: (180, 180, 180),  # Light grey
    }
    rectangle(pelt_wolf, (3, 4, 10, 9), PALETTE[1])
    rectangle(pelt_wolf, (3, 10, 10, 2), PALETTE[2])
    pelt_wolf.set_at((5, 5), PALETTE[3])
    pelt_wolf.set_at((9, 6), PALETTE[3])
    # Fur texture
    for fx in range(4, 12):
        for fy in range(5, 10):
            if (fx + fy) % 3 == 0:
                pelt_wolf.set_at((fx, fy), PALETTE[3])
    save_surface(os.path.join(output_dir, "pelt_wolf.png"), pelt_wolf)

    # ── Monster Drop: Wolf Bone (16x16) ──
    bone_wolf = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 215, 200),  # Bone white
        2: (200, 195, 180),  # Dark bone
        3: (240, 235, 220),  # Highlight
    }
    # Bone shape (dumbbell)
    rectangle(bone_wolf, (5, 7, 6, 3), PALETTE[1])
    circle(bone_wolf, (5, 7), 2, PALETTE[1])
    circle(bone_wolf, (5, 10), 2, PALETTE[1])
    circle(bone_wolf, (11, 7), 2, PALETTE[1])
    circle(bone_wolf, (11, 10), 2, PALETTE[1])
    bone_wolf.set_at((6, 7), PALETTE[3])
    bone_wolf.set_at((6, 10), PALETTE[3])
    bone_wolf.set_at((10, 7), PALETTE[3])
    bone_wolf.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "bone_wolf.png"), bone_wolf)

    # ── Monster Drop: Bear Hide (16x16) ──
    hide_bear = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 60, 30),    # Brown
        2: (80, 50, 25),     # Dark brown
        3: (120, 80, 40),    # Light brown
    }
    rectangle(hide_bear, (3, 4, 10, 10), PALETTE[1])
    rectangle(hide_bear, (3, 10, 10, 3), PALETTE[2])
    hide_bear.set_at((5, 5), PALETTE[3])
    hide_bear.set_at((9, 6), PALETTE[3])
    save_surface(os.path.join(output_dir, "hide_bear.png"), hide_bear)

    # ── Monster Drop: Bear Claw (16x16) ──
    claw_bear = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 50, 40),     # Dark
        2: (80, 70, 55),     # Medium
        3: (100, 90, 70),    # Light
    }
    # Curved claw
    for i in range(10):
        x = 6 + i
        y = 14 - i
        if 0 <= x < 16 and 0 <= y < 16:
            claw_bear.set_at((x, y), PALETTE[1])
            if y + 1 < 16:
                claw_bear.set_at((x, y + 1), PALETTE[2])
    claw_bear.set_at((15, 4), PALETTE[3])  # Tip
    claw_bear.set_at((6, 14), PALETTE[2])  # Base
    save_surface(os.path.join(output_dir, "claw_bear.png"), claw_bear)

    # ── Monster Drop: Poison Gland (16x16) ──
    gland_poison = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 220, 50),   # Toxic green
        2: (150, 200, 40),   # Darker green
        3: (200, 240, 70),   # Bright green
    }
    circle(gland_poison, (8, 9), 4, PALETTE[1])
    circle(gland_poison, (7, 8), 3, PALETTE[2])
    gland_poison.set_at((8, 7), PALETTE[3])
    gland_poison.set_at((6, 9), PALETTE[3])
    gland_poison.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "gland_poison.png"), gland_poison)

    # ── Monster Drop: Scorpion Carapace (16x16) ──
    carapace_scorpion = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 140, 50),   # Brown
        2: (150, 120, 40),   # Dark brown
        3: (200, 160, 60),   # Light brown
    }
    circle(carapace_scorpion, (8, 9), 5, PALETTE[1])
    circle(carapace_scorpion, (7, 8), 3, PALETTE[2])
    carapace_scorpion.set_at((6, 7), PALETTE[3])
    carapace_scorpion.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "carapace_scorpion.png"), carapace_scorpion)

    # ── Monster Drop: Golem Core (16x16) ──
    core_golem = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (140, 140, 150),  # Grey
        2: (120, 120, 130),  # Dark grey
        3: (160, 160, 170),  # Light grey
        4: (100, 200, 255),  # Glowing blue (core)
    }
    rectangle(core_golem, (4, 5, 8, 8), PALETTE[1])
    rectangle(core_golem, (4, 5, 8, 1), PALETTE[3])
    rectangle(core_golem, (4, 12, 8, 1), PALETTE[2])
    # Glowing core
    circle(core_golem, (8, 9), 2, PALETTE[4])
    core_golem.set_at((8, 8), PALETTE[4])
    core_golem.set_at((8, 10), PALETTE[4])
    core_golem.set_at((7, 9), PALETTE[4])
    core_golem.set_at((9, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "core_golem.png"), core_golem)

    # ── Monster Drop: Eagle Feather Pack (16x16) ──
    feather_pack = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (120, 80, 40),    # Brown
        2: (100, 70, 30),    # Dark brown
        3: (140, 100, 50),   # Light brown
    }
    # Feathers (lines)
    rectangle(feather_pack, (8, 3, 1, 11), PALETTE[1])
    rectangle(feather_pack, (6, 4, 1, 10), PALETTE[1])
    rectangle(feather_pack, (10, 4, 1, 10), PALETTE[1])
    # Quills
    feather_pack.set_at((8, 3), PALETTE[3])
    feather_pack.set_at((6, 4), PALETTE[3])
    feather_pack.set_at((10, 4), PALETTE[3])
    save_surface(os.path.join(output_dir, "feather_pack.png"), feather_pack)

    # ── Torch (16x16) ──
    torch = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (139, 90, 43),    # Brown (stick)
        2: (255, 140, 20),   # Orange (flame)
        3: (255, 200, 50),   # Yellow (flame core)
        4: (100, 65, 30),    # Dark brown
    }
    rectangle(torch, (7, 7, 2, 9), PALETTE[1])
    rectangle(torch, (7, 10, 2, 5), PALETTE[4])
    # Flame
    circle(torch, (8, 6), 3, PALETTE[2])
    circle(torch, (8, 5), 2, PALETTE[3])
    torch.set_at((8, 4), PALETTE[3])
    save_surface(os.path.join(output_dir, "torch.png"), torch)

    # ── Ash (16x16) ──
    ash = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (150, 150, 155),  # Grey
        2: (130, 130, 135),  # Dark grey
        3: (170, 170, 175),  # Light grey
    }
    circle(ash, (8, 10), 5, PALETTE[1])
    circle(ash, (7, 9), 3, PALETTE[3])
    ash.set_at((9, 10), PALETTE[2])
    ash.set_at((6, 11), PALETTE[2])
    save_surface(os.path.join(output_dir, "ash.png"), ash)

    # ── Tree Sap (16x16) ──
    sap = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (210, 180, 80),   # Amber
        2: (190, 160, 60),   # Dark amber
        3: (230, 200, 100),  # Light amber
    }
    circle(sap, (8, 9), 4, PALETTE[1])
    circle(sap, (7, 8), 3, PALETTE[2])
    sap.set_at((8, 7), PALETTE[3])
    sap.set_at((6, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "sap.png"), sap)

    # ── Polished Bone (16x16) ──
    bone_polished = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 225, 210),  # Clean white
        2: (210, 205, 190),  # Slightly dark
        3: (245, 240, 225),  # Highlight
    }
    rectangle(bone_polished, (5, 7, 6, 3), PALETTE[1])
    circle(bone_polished, (5, 7), 2, PALETTE[1])
    circle(bone_polished, (5, 10), 2, PALETTE[1])
    circle(bone_polished, (11, 7), 2, PALETTE[1])
    circle(bone_polished, (11, 10), 2, PALETTE[1])
    bone_polished.set_at((6, 7), PALETTE[3])
    bone_polished.set_at((6, 10), PALETTE[3])
    bone_polished.set_at((10, 7), PALETTE[3])
    bone_polished.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "bone_polished.png"), bone_polished)

    # ── Bone Powder (16x16) ──
    bone_powder = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 215, 200),  # Off-white
        2: (200, 195, 180),  # Darker
        3: (235, 230, 215),  # Light
    }
    circle(bone_powder, (8, 10), 5, PALETTE[1])
    circle(bone_powder, (7, 9), 3, PALETTE[3])
    bone_powder.set_at((9, 10), PALETTE[2])
    save_surface(os.path.join(output_dir, "bone_powder.png"), bone_powder)

    # ── Refined Resin (16x16) ──
    resin = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 160, 60),   # Amber
        2: (180, 140, 50),   # Dark amber
        3: (220, 180, 80),   # Light amber
    }
    rectangle(resin, (4, 6, 8, 7), PALETTE[1])
    rectangle(resin, (4, 11, 8, 1), PALETTE[2])
    resin.set_at((5, 6), PALETTE[3])
    resin.set_at((9, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "resin.png"), resin)

    # ── Pitch (16x16) ──
    pitch = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (40, 35, 30),     # Very dark
        2: (30, 25, 20),     # Near black
        3: (60, 50, 40),     # Slightly lighter
    }
    circle(pitch, (8, 9), 5, PALETTE[1])
    circle(pitch, (7, 8), 3, PALETTE[3])
    pitch.set_at((8, 7), PALETTE[3])
    pitch.set_at((6, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "pitch.png"), pitch)

    # ── Candle (16x16) ──
    candle = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 220, 180),  # Cream
        2: (210, 200, 160),  # Dark cream
        3: (255, 200, 50),   # Flame
        4: (255, 140, 20),   # Orange flame
    }
    rectangle(candle, (6, 8, 4, 7), PALETTE[1])
    rectangle(candle, (6, 12, 4, 2), PALETTE[2])
    # Wick
    rectangle(candle, (7, 6, 2, 2), (60, 50, 40))
    # Flame
    circle(candle, (8, 5), 2, PALETTE[4])
    candle.set_at((8, 4), PALETTE[3])
    save_surface(os.path.join(output_dir, "candle.png"), candle)

    # ── Honey Filtered (16x16) ──
    honey = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 180, 50),   # Golden
        2: (200, 160, 40),   # Dark golden
        3: (240, 200, 70),   # Light golden
    }
    circle(honey, (8, 9), 5, PALETTE[1])
    circle(honey, (7, 8), 3, PALETTE[2])
    honey.set_at((8, 7), PALETTE[3])
    honey.set_at((6, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "honey_filtered.png"), honey)

    # ── Reed (16x16) ──
    reed = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (140, 130, 80),   # Tan
        2: (120, 110, 70),   # Dark tan
        3: (160, 150, 100),  # Light tan
    }
    rectangle(reed, (7, 3, 2, 12), PALETTE[1])
    rectangle(reed, (7, 8, 2, 6), PALETTE[2])
    reed.set_at((8, 4), PALETTE[3])
    save_surface(os.path.join(output_dir, "reed.png"), reed)

    # ── Paper (16x16) ──
    paper = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 225, 210),  # Off-white
        2: (210, 205, 190),  # Slightly dark
        3: (245, 240, 225),  # Highlight
    }
    rectangle(paper, (3, 4, 10, 9), PALETTE[1])
    rectangle(paper, (3, 11, 10, 1), PALETTE[2])
    paper.set_at((4, 5), PALETTE[3])
    paper.set_at((11, 5), PALETTE[3])
    save_surface(os.path.join(output_dir, "paper.png"), paper)

    # ── Honeycomb (16x16) ──
    honeycomb = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 180, 50),   # Golden
        2: (200, 160, 40),   # Dark golden
        3: (240, 200, 70),   # Light golden
    }
    # Hexagonal pattern
    circle(honeycomb, (6, 8), 3, PALETTE[1])
    circle(honeycomb, (10, 8), 3, PALETTE[1])
    circle(honeycomb, (8, 11), 3, PALETTE[1])
    circle(honeycomb, (6, 11), 2, PALETTE[2])
    circle(honeycomb, (10, 11), 2, PALETTE[2])
    # Wax sheen
    honeycomb.set_at((6, 7), PALETTE[3])
    honeycomb.set_at((10, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "honeycomb.png"), honeycomb)

    # ── Gold Coin (16x16) ──
    gold_coin = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 180, 40),   # Gold
        2: (200, 160, 30),   # Dark gold
        3: (240, 200, 60),   # Bright gold
    }
    circle(gold_coin, (8, 9), 6, PALETTE[1])
    circle(gold_coin, (8, 9), 5, PALETTE[2])
    circle(gold_coin, (8, 9), 3, PALETTE[3])
    gold_coin.set_at((6, 7), PALETTE[3])
    gold_coin.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "gold.png"), gold_coin)

    # ── Healing Herbs (16x16) ──
    healing_herbs = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 150, 50),    # Green
        2: (70, 180, 70),    # Light green
        3: (34, 120, 34),    # Dark green
    }
    rectangle(healing_herbs, (7, 5, 2, 8), (80, 60, 40))  # Stem
    circle(healing_herbs, (6, 6), 2, PALETTE[1])
    circle(healing_herbs, (10, 6), 2, PALETTE[1])
    circle(healing_herbs, (8, 4), 2, PALETTE[2])
    healing_herbs.set_at((8, 3), PALETTE[2])
    # Pink sparkle for "healing" effect
    healing_herbs.set_at((6, 6), (200, 150, 180))
    save_surface(os.path.join(output_dir, "healing_herbs.png"), healing_herbs)

    # ── Berry Jar (16x16) ──
    berry_jar = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 50, 50),    # Red (berries)
        2: (200, 70, 70),    # Light red
        3: (220, 220, 230),  # Glass
        4: (200, 200, 210),  # Glass highlight
    }
    # Jar body
    rectangle(berry_jar, (5, 6, 6, 8), PALETTE[3])
    rectangle(berry_jar, (5, 10, 6, 4), PALETTE[1])
    # Jar neck
    rectangle(berry_jar, (6, 4, 4, 3), PALETTE[3])
    rectangle(berry_jar, (6, 6, 4, 1), PALETTE[4])
    # Lid
    rectangle(berry_jar, (5, 3, 6, 1), (160, 120, 60))
    save_surface(os.path.join(output_dir, "berry_jar.png"), berry_jar)

    # ── Wheat Bundle (16x16) ──
    wheat_bundle = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 180, 80),   # Golden
        2: (220, 200, 100),  # Light golden
        3: (80, 60, 40),     # Brown (tie)
    }
    rectangle(wheat_bundle, (6, 3, 2, 12), PALETTE[1])
    rectangle(wheat_bundle, (8, 3, 2, 12), PALETTE[1])
    circle(wheat_bundle, (7, 3), 2, PALETTE[2])
    circle(wheat_bundle, (9, 3), 2, PALETTE[2])
    rectangle(wheat_bundle, (5, 10, 6, 2), PALETTE[3])
    save_surface(os.path.join(output_dir, "wheat_bundle.png"), wheat_bundle)

    # ── Grass Rope (16x16) ──
    grass_rope = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 140, 60),    # Green
        2: (50, 120, 50),    # Dark green
        3: (80, 160, 80),    # Light green
    }
    # Twisted rope
    for i in range(12):
        x = 3 + i
        y = 8 + ((i * 2) % 3) - 1
        if 0 <= x < 16 and 0 <= y < 16:
            grass_rope.set_at((x, y), PALETTE[1])
            if y + 1 < 16:
                grass_rope.set_at((x, y + 1), PALETTE[2])
    grass_rope.set_at((4, 7), PALETTE[3])
    grass_rope.set_at((14, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "grass_rope.png"), grass_rope)

    # ── Salt Block (16x16) ──
    salt_block = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 230, 240),  # White
        2: (200, 200, 210),  # Light grey
        3: (240, 240, 250),  # Highlight
    }
    rectangle(salt_block, (3, 5, 10, 7), PALETTE[1])
    rectangle(salt_block, (3, 5, 10, 1), PALETTE[3])
    rectangle(salt_block, (3, 10, 10, 1), PALETTE[2])
    save_surface(os.path.join(output_dir, "salt_block.png"), salt_block)

    # ── Salt (item version) ──
    salt_item2 = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 230, 240),  # White
        2: (200, 200, 210),  # Light grey
    }
    rectangle(salt_item2, (5, 8, 2, 2), PALETTE[1])
    rectangle(salt_item2, (9, 7, 2, 2), PALETTE[1])
    rectangle(salt_item2, (7, 10, 2, 2), PALETTE[1])
    salt_item2.set_at((6, 9), PALETTE[2])
    salt_item2.set_at((10, 8), PALETTE[2])
    save_surface(os.path.join(output_dir, "salt.png"), salt_item2)

    # ── Evaporated Salt (16x16) ──
    salt_evaporated = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (240, 240, 250),  # Very white
        2: (220, 220, 230),  # Slightly dark
    }
    # Flaky salt
    for fy in range(5, 14):
        for fx in range(4, 13):
            if (fx + fy) % 3 == 0:
                salt_evaporated.set_at((fx, fy), PALETTE[1])
    salt_evaporated.set_at((6, 7), PALETTE[2])
    salt_evaporated.set_at((10, 11), PALETTE[2])
    save_surface(os.path.join(output_dir, "salt_evaporated.png"), salt_evaporated)

    # ── Refined Salt (16x16) ──
    salt_refined = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (235, 235, 245),  # Pure white
        2: (215, 215, 225),  # Slightly dark
    }
    rectangle(salt_refined, (4, 5, 8, 8), PALETTE[1])
    rectangle(salt_refined, (4, 5, 8, 1), PALETTE[2])
    save_surface(os.path.join(output_dir, "salt_refined.png"), salt_refined)

    # ── Rendered Tallow (16x16) ──
    tallow = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 215, 200),  # Off-white/yellow
        2: (200, 195, 180),  # Slightly dark
        3: (240, 235, 220),  # Highlight
    }
    circle(tallow, (8, 9), 5, PALETTE[1])
    circle(tallow, (7, 8), 3, PALETTE[2])
    tallow.set_at((8, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "tallow.png"), tallow)

    # ── Peat Block (16x16) ──
    peat_block = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 40, 30),     # Dark brown
        2: (80, 60, 40),     # Medium brown
        3: (50, 35, 25),     # Very dark
    }
    rectangle(peat_block, (3, 5, 10, 8), PALETTE[1])
    rectangle(peat_block, (3, 5, 10, 1), PALETTE[2])
    rectangle(peat_block, (3, 10, 10, 1), PALETTE[3])
    save_surface(os.path.join(output_dir, "peat_block.png"), peat_block)

    # ── Shell Necklace (16x16) ──
    shell_necklace = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (240, 230, 200),  # Shell white
        2: (220, 200, 170),  # Cream
        3: (200, 180, 150),  # Edge
    }
    # Necklace curve
    shell_necklace.set_at((4, 10), PALETTE[1])
    shell_necklace.set_at((5, 9), PALETTE[1])
    shell_necklace.set_at((6, 8), PALETTE[1])
    shell_necklace.set_at((7, 7), PALETTE[1])
    shell_necklace.set_at((8, 7), PALETTE[1])
    shell_necklace.set_at((9, 7), PALETTE[1])
    shell_necklace.set_at((10, 8), PALETTE[1])
    shell_necklace.set_at((11, 9), PALETTE[1])
    shell_necklace.set_at((12, 10), PALETTE[1])
    # Shell details
    shell_necklace.set_at((7, 7), PALETTE[2])
    shell_necklace.set_at((8, 7), PALETTE[2])
    shell_necklace.set_at((9, 7), PALETTE[2])
    # String
    shell_necklace.set_at((6, 8), (100, 80, 60))
    shell_necklace.set_at((10, 8), (100, 80, 60))
    save_surface(os.path.join(output_dir, "shell_necklace.png"), shell_necklace)

    # ── Dried Fish (16x16) ──
    fish_dried = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 150, 100),  # Tan
        2: (160, 130, 80),   # Dark tan
        3: (200, 170, 120),  # Light tan
    }
    circle(fish_dried, (8, 9), 4, PALETTE[1])
    circle(fish_dried, (7, 8), 3, PALETTE[2])
    fish_dried.set_at((3, 8), PALETTE[1])
    fish_dried.set_at((3, 9), PALETTE[2])
    fish_dried.set_at((11, 8), PALETTE[3])
    save_surface(os.path.join(output_dir, "fish_dried.png"), fish_dried)

    # ── Poison Antidote (16x16) ──
    antidote = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 220, 230),  # White bottle
        2: (200, 200, 210),  # Slightly dark
        3: (180, 220, 180),  # Green liquid
        4: (100, 180, 100),  # Dark green
    }
    # Bottle
    rectangle(antidote, (6, 4, 4, 3), PALETTE[1])  # Neck
    rectangle(antidote, (5, 7, 6, 7), PALETTE[1])  # Body
    rectangle(antidote, (5, 10, 6, 4), PALETTE[3])  # Liquid
    rectangle(antidote, (5, 14, 6, 1), PALETTE[4])  # Bottom
    # Cap
    rectangle(antidote, (6, 3, 4, 1), (80, 80, 90))
    # Label
    antidote.set_at((6, 10), PALETTE[2])
    antidote.set_at((10, 11), PALETTE[2])
    save_surface(os.path.join(output_dir, "antidote.png"), antidote)

    # ── Mead (16x16) ──
    mead = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 170, 60),   # Golden
        2: (180, 150, 50),   # Dark golden
        3: (220, 190, 80),   # Light golden
    }
    rectangle(mead, (5, 5, 6, 8), (220, 220, 230))  # Bottle
    rectangle(mead, (5, 3, 6, 3), (220, 220, 230))  # Neck
    rectangle(mead, (5, 8, 6, 5), PALETTE[1])  # Liquid
    rectangle(mead, (5, 12, 6, 1), PALETTE[2])  # Bottom
    mead.set_at((6, 6), PALETTE[3])
    save_surface(os.path.join(output_dir, "mead.png"), mead)

    # ── Pressed Papyrus (16x16) ──
    papyrus = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (210, 195, 150),  # Tan
        2: (190, 175, 130),  # Dark tan
        3: (230, 215, 170),  # Light tan
    }
    rectangle(papyrus, (3, 4, 10, 9), PALETTE[1])
    rectangle(papyrus, (3, 4, 10, 1), PALETTE[3])
    rectangle(papyrus, (3, 11, 10, 1), PALETTE[2])
    # Lines (text)
    rectangle(papyrus, (4, 6, 8, 1), PALETTE[2])
    rectangle(papyrus, (4, 8, 6, 1), PALETTE[2])
    rectangle(papyrus, (4, 10, 7, 1), PALETTE[2])
    save_surface(os.path.join(output_dir, "papyrus.png"), papyrus)

    # ── Sand Glass (16x16) ──
    sand_glass = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (210, 190, 140),  # Sand
        2: (190, 170, 120),  # Dark sand
        3: (220, 220, 230),  # Glass
        4: (200, 200, 210),  # Glass edge
    }
    # Hourglass shape
    rectangle(sand_glass, (6, 3, 4, 2), PALETTE[3])  # Top cap
    rectangle(sand_glass, (6, 11, 4, 2), PALETTE[3])  # Bottom cap
    # Glass body
    rectangle(sand_glass, (7, 4, 2, 3), PALETTE[3])  # Top narrow
    rectangle(sand_glass, (5, 7, 6, 1), PALETTE[3])  # Top wide
    rectangle(sand_glass, (5, 8, 6, 1), PALETTE[3])  # Bottom wide
    rectangle(sand_glass, (7, 9, 2, 3), PALETTE[3])  # Bottom narrow
    # Sand
    rectangle(sand_glass, (6, 7, 4, 1), PALETTE[1])
    rectangle(sand_glass, (6, 9, 4, 1), PALETTE[2])
    save_surface(os.path.join(output_dir, "sand_glass.png"), sand_glass)

    # ── Glass Sheet (16x16) ──
    glass_sheet = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 220, 240),  # Light blue glass
        2: (180, 200, 220),  # Slightly dark
        3: (220, 240, 255),  # Highlight
    }
    rectangle(glass_sheet, (3, 4, 10, 9), PALETTE[1])
    rectangle(glass_sheet, (3, 4, 10, 1), PALETTE[3])
    rectangle(glass_sheet, (3, 11, 10, 1), PALETTE[2])
    rectangle(glass_sheet, (3, 5, 1, 8), PALETTE[3])
    glass_sheet.set_at((5, 6), PALETTE[3])
    glass_sheet.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "glass_sheet.png"), glass_sheet)

    # ── Molten Glass (16x16) ──
    molten_glass = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 220, 240),  # Glass
        2: (255, 180, 50),   # Orange glow
        3: (255, 220, 100),  # Bright orange
    }
    circle(molten_glass, (8, 9), 5, PALETTE[1])
    circle(molten_glass, (8, 9), 4, PALETTE[2])
    circle(molten_glass, (8, 9), 2, PALETTE[3])
    molten_glass.set_at((6, 7), PALETTE[3])
    molten_glass.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "molten_glass.png"), molten_glass)

    # ── Diamond Ring (16x16) ──
    diamond_ring = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 200, 210),  # Silver band
        2: (180, 180, 190),  # Dark silver
        3: (200, 100, 220),  # Diamond purple
        4: (230, 140, 250),  # Diamond sparkle
    }
    # Band (half circle)
    for angle in range(180, 360):
        import math
        ax = int(8 + 4 * math.cos(math.radians(angle)))
        ay = int(10 + 4 * math.sin(math.radians(angle)))
        if 0 <= ax < 16 and 0 <= ay < 16:
            diamond_ring.set_at((ax, ay), PALETTE[1])
    diamond_ring.set_at((7, 13), PALETTE[2])
    diamond_ring.set_at((9, 13), PALETTE[2])
    # Diamond on top
    polygon(diamond_ring, [(8, 3), (10, 6), (8, 8), (6, 6)], PALETTE[3])
    diamond_ring.set_at((8, 5), PALETTE[4])
    save_surface(os.path.join(output_dir, "diamond_ring.png"), diamond_ring)

    # ── Enchanted Amulet (16x16) ──
    amulet = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (140, 120, 80),   # Gold
        2: (120, 100, 60),   # Dark gold
        3: (200, 100, 220),  # Magic purple gem
        4: (230, 140, 250),  # Sparkle
        5: (80, 120, 160),   # String
    }
    # String
    rectangle(amulet, (7, 3, 2, 3), PALETTE[5])
    # Pendant
    circle(amulet, (8, 10), 5, PALETTE[1])
    circle(amulet, (8, 10), 4, PALETTE[2])
    # Gem in center
    polygon(amulet, [(8, 7), (11, 10), (8, 14), (5, 10)], PALETTE[3])
    amulet.set_at((8, 10), PALETTE[4])
    save_surface(os.path.join(output_dir, "amulet.png"), amulet)

    # ── Djinn Essence (16x16) ──
    djinn_essence = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 150, 50),   # Gold
        2: (180, 130, 40),   # Dark gold
        3: (220, 170, 70),   # Light gold
        4: (255, 220, 100),  # Bright
    }
    rectangle(djinn_essence, (5, 5, 6, 8), (220, 220, 230))  # Bottle
    rectangle(djinn_essence, (6, 3, 4, 3), (220, 220, 230))  # Neck
    rectangle(djinn_essence, (5, 7, 6, 5), PALETTE[1])  # Liquid
    rectangle(djinn_essence, (5, 11, 6, 1), PALETTE[2])  # Bottom
    djinn_essence.set_at((6, 6), PALETTE[3])
    djinn_essence.set_at((8, 5), PALETTE[4])  # Sparkle
    save_surface(os.path.join(output_dir, "djinn_essence.png"), djinn_essence)

    # ── Goblin Trophy (16x16) ──
    trophy_goblin = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 140, 60),    # Green
        2: (50, 120, 50),    # Dark green
        3: (80, 160, 80),    # Light green
    }
    # Skull-like shape
    circle(trophy_goblin, (8, 8), 4, PALETTE[1])
    circle(trophy_goblin, (7, 7), 3, PALETTE[2])
    trophy_goblin.set_at((6, 7), (30, 30, 30))  # Eye
    trophy_goblin.set_at((10, 7), (30, 30, 30))  # Eye
    trophy_goblin.set_at((7, 9), PALETTE[3])
    trophy_goblin.set_at((9, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "trophy_goblin.png"), trophy_goblin)

    # ── Serpent Scale (16x16) ──
    scale_serpent = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 100, 160),   # Blue
        2: (40, 80, 140),    # Dark blue
        3: (70, 120, 180),   # Light blue
    }
    # Scale (teardrop shape)
    circle(scale_serpent, (8, 7), 4, PALETTE[1])
    circle(scale_serpent, (7, 6), 3, PALETTE[2])
    scale_serpent.set_at((8, 5), PALETTE[3])
    scale_serpent.set_at((6, 7), PALETTE[3])
    # Pointed bottom
    scale_serpent.set_at((8, 11), PALETTE[1])
    scale_serpent.set_at((7, 12), PALETTE[2])
    scale_serpent.set_at((9, 12), PALETTE[2])
    save_surface(os.path.join(output_dir, "scale_serpent.png"), scale_serpent)

    # ── Cactus Fiber (16x16) ──
    cactus_fiber = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 140, 80),   # Green-tan
        2: (80, 120, 60),    # Dark green-tan
        3: (120, 160, 100),  # Light green-tan
    }
    rectangle(cactus_fiber, (7, 3, 2, 12), PALETTE[1])
    rectangle(cactus_fiber, (8, 4, 1, 10), PALETTE[3])
    cactus_fiber.set_at((7, 3), PALETTE[3])
    save_surface(os.path.join(output_dir, "cactus_fiber.png"), cactus_fiber)

    # ── Dried Scorpion Tail (16x16) ──
    scorpion_tail_dried = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 140, 50),   # Brown
        2: (150, 120, 40),   # Dark brown
        3: (200, 160, 60),   # Light brown
    }
    # Curved tail
    scorpion_tail_dried.set_at((5, 12), PALETTE[1])
    scorpion_tail_dried.set_at((6, 11), PALETTE[1])
    scorpion_tail_dried.set_at((7, 10), PALETTE[1])
    scorpion_tail_dried.set_at((8, 9), PALETTE[1])
    scorpion_tail_dried.set_at((9, 8), PALETTE[1])
    scorpion_tail_dried.set_at((10, 8), PALETTE[1])
    scorpion_tail_dried.set_at((10, 7), PALETTE[3])  # Tail tip/ stinger
    scorpion_tail_dried.set_at((9, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "scorpion_tail_dried.png"), scorpion_tail_dried)

    # ── Stamen/Pith ── (using common fiber base but brown)
    pith = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (120, 100, 70),   # Brown-tan
        2: (100, 80, 55),    # Darker
        3: (140, 120, 90),   # Lighter
    }
    rectangle(pith, (6, 3, 2, 12), PALETTE[1])
    rectangle(pith, (8, 3, 2, 12), PALETTE[1])
    rectangle(pith, (7, 4, 2, 10), PALETTE[2])
    pith.set_at((6, 3), PALETTE[3])
    pith.set_at((10, 3), PALETTE[3])
    save_surface(os.path.join(output_dir, "pith.png"), pith)

    # ── Refine Resin (16x16) ──
    resin_refined = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 180, 80),   # Bright amber
        2: (200, 160, 60),   # Dark amber
        3: (240, 200, 100),  # Highlight
    }
    circle(resin_refined, (8, 9), 4, PALETTE[1])
    circle(resin_refined, (7, 8), 3, PALETTE[2])
    resin_refined.set_at((8, 7), PALETTE[3])
    resin_refined.set_at((6, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "resin_refined.png"), resin_refined)

    print("  Generated 80+ item sprites")


# ── World/Campfire Sprite ─────────────────────────────────────────────

def generate_campfire_sprite() -> None:
    """Generate the world/campfire sprite for the campfire item."""
    print("\n=== Generating Campfire World Sprite ===")
    output_dir = os.path.join(OUTPUT_ROOT, "world")

    campfire = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (139, 90, 43),    # Brown (logs)
        2: (255, 140, 20),   # Orange (flame)
        3: (255, 200, 50),   # Yellow (flame core)
        4: (100, 80, 60),    # Dark brown (base)
        5: (255, 100, 10),   # Deep orange (base flame)
    }
    # Log base (crossed logs)
    rectangle(campfire, (4, 11, 8, 2), PALETTE[4])
    rectangle(campfire, (5, 10, 6, 1), PALETTE[1])
    rectangle(campfire, (6, 12, 4, 1), PALETTE[1])
    # Flames
    circle(campfire, (8, 9), 3, PALETTE[2])
    circle(campfire, (8, 8), 2, PALETTE[3])
    campfire.set_at((8, 7), PALETTE[3])
    campfire.set_at((7, 9), PALETTE[5])
    campfire.set_at((9, 9), PALETTE[5])
    save_surface(os.path.join(output_dir, "campfire.png"), campfire)


# ── World Terrain Sub-Assets ─────────────────────────────────────────

def generate_terrain_subassets() -> None:
    """Generate terrain overlay sprites (trees/terrain overlay layer)."""
    print("\n=== Generating World Terrain Sub-Assets ===")
    output_dir = os.path.join(OUTPUT_ROOT, "world", "terrain")

    # Tree shadow overlay (64x64)
    tree_shadow = pygame.Surface((64, 64), pygame.SRCALPHA)
    PALETTE = {
        1: (30, 60, 30),     # Dark shadow
        2: (40, 70, 40),     # Slightly lighter
    }
    # Multiple tree shadows
    circle(tree_shadow, (16, 20), 10, PALETTE[1])
    circle(tree_shadow, (48, 18), 10, PALETTE[1])
    circle(tree_shadow, (32, 40), 8, PALETTE[1])
    circle(tree_shadow, (16, 20), 8, PALETTE[2])
    circle(tree_shadow, (48, 18), 8, PALETTE[2])
    circle(tree_shadow, (32, 40), 6, PALETTE[2])
    save_surface(os.path.join(output_dir, "tree_shadow.png"), tree_shadow)

    # Water shimmer (64x64)
    water_overlay = pygame.Surface((64, 64), pygame.SRCALPHA)
    PALETTE = {
        1: (60, 120, 200),   # Blue
        2: (80, 150, 230),   # Light blue
    }
    water_overlay.fill((0, 0, 0, 0))  # Transparent base
    # Wave pattern
    for wx in range(0, 64, 8):
        for wy in range(0, 64, 8):
            if (wx + wy) % 16 == 0:
                circle(water_overlay, (wx + 4, wy + 4), 3, PALETTE[2])
    save_surface(os.path.join(output_dir, "water_shimmer.png"), water_overlay)

    # Grass overlay (64x64)
    grass_overlay = pygame.Surface((64, 64), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 130, 50),    # Green
        2: (70, 160, 70),    # Light green
    }
    for gx in range(0, 64, 6):
        for gy in range(0, 64, 6):
            if (gx + gy) % 10 == 0:
                grass_overlay.set_at((gx, gy), PALETTE[1])
                grass_overlay.set_at((gx + 1, gy - 1), PALETTE[2])
    save_surface(os.path.join(output_dir, "grass_overlay.png"), grass_overlay)

    print("  Generated 3 terrain sub-asset sprites")


# ── Tier 3/4 Rock/Ore Sprites ────────────────────────────────────────

def generate_tier3_rock_sprites() -> None:
    """Generate tier 3/4 rock and ore sprites — each with unique visual identity."""
    print("\n=== Generating Tier 3/4 Rock/Ore Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "rocks")

    # Void Crystal (16x16) — jagged dark purple crystal cluster
    void_crystal = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 30, 75),     # Deep void purple (base)
        2: (35, 20, 55),     # Very dark void
        3: (130, 70, 195),   # Void crystal
        4: (175, 110, 235),  # Bright void glow
        5: (85, 50, 130),    # Mid purple
    }
    # Jagged crystal cluster (sharp geometric)
    polygon(void_crystal, [(6, 5), (8, 3), (10, 5), (11, 8), (9, 12), (7, 14), (5, 12), (4, 8)], PALETTE[1])
    polygon(void_crystal, [(7, 6), (8, 4), (9, 6), (10, 9), (8, 13), (6, 11)], PALETTE[5])
    # Crystal facets (sharp triangles)
    polygon(void_crystal, [(8, 3), (10, 7), (8, 9)], PALETTE[3])
    polygon(void_crystal, [(6, 6), (8, 8), (5, 10)], PALETTE[3])
    polygon(void_crystal, [(10, 6), (12, 9), (9, 10)], PALETTE[3])
    # Glow nodes
    void_crystal.set_at((8, 5), PALETTE[4])
    void_crystal.set_at((6, 8), PALETTE[4])
    void_crystal.set_at((10, 8), PALETTE[4])
    save_surface(os.path.join(output_dir, "void_crystal.png"), void_crystal)

    # Obsidian (16x16) — sharp volcanic glass with fracture lines
    obsidian = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (25, 22, 28),     # Near-black glass
        2: (15, 12, 18),     # Very dark
        3: (65, 60, 72),     # Glass sheen
        4: (105, 100, 115),  # Highlight
        5: (45, 40, 50),     # Mid dark
    }
    # Sharp angular glass shape
    polygon(obsidian, [(3, 10), (5, 4), (9, 3), (13, 5), (14, 9), (13, 14), (8, 15), (4, 13)], PALETTE[1])
    polygon(obsidian, [(5, 10), (7, 5), (10, 4), (12, 7), (11, 13), (7, 14)], PALETTE[5])
    # Glassy fracture lines (sharp diagonal cracks)
    obsidian.set_at((6, 5), PALETTE[3])
    obsidian.set_at((7, 4), PALETTE[4])
    obsidian.set_at((8, 5), PALETTE[3])
    obsidian.set_at((9, 6), PALETTE[3])
    obsidian.set_at((5, 9), PALETTE[3])
    obsidian.set_at((6, 10), PALETTE[4])
    obsidian.set_at((10, 10), PALETTE[3])
    obsidian.set_at((11, 11), PALETTE[3])
    obsidian.set_at((8, 13), PALETTE[3])
    save_surface(os.path.join(output_dir, "obsidian.png"), obsidian)

    # Mithril (16x16) — flowing silvery-blue metallic ore
    mithril = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (95, 105, 118),   # Grey rock base
        2: (75, 85, 98),     # Dark grey shadow
        3: (95, 155, 215),   # Mithril blue veins
        4: (135, 185, 250),  # Bright mithril glow
        5: (125, 165, 195),  # Mid blue
    }
    # Rock base
    circle(mithril, (8, 10), 6, PALETTE[1])
    circle(mithril, (6, 9), 4, PALETTE[2])
    circle(mithril, (10, 9), 4, PALETTE[5])
    # Flowing mithril veins (curved paths via pixel chain)
    mithril.set_at((5, 7), PALETTE[3])
    mithril.set_at((6, 6), PALETTE[3])
    mithril.set_at((7, 5), PALETTE[4])
    mithril.set_at((8, 5), PALETTE[3])
    mithril.set_at((9, 6), PALETTE[3])
    mithril.set_at((10, 7), PALETTE[3])
    mithril.set_at((11, 8), PALETTE[3])
    mithril.set_at((6, 11), PALETTE[3])
    mithril.set_at((7, 12), PALETTE[4])
    mithril.set_at((9, 12), PALETTE[3])
    mithril.set_at((10, 11), PALETTE[3])
    save_surface(os.path.join(output_dir, "mithril.png"), mithril)

    # Ghost Iron (16x16) — pale spectral metal with ethereal veins
    ghost_iron = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (125, 130, 138),  # Pale spectral grey
        2: (95, 100, 108),   # Dark spectral
        3: (175, 180, 198),  # Ghost iron veins
        4: (205, 210, 228),  # Bright ghost glow
        5: (145, 150, 162),  # Mid pale
    }
    # Ethereal rock shape
    circle(ghost_iron, (8, 10), 6, PALETTE[1])
    circle(ghost_iron, (6, 9), 4, PALETTE[2])
    circle(ghost_iron, (10, 9), 4, PALETTE[5])
    # Ghostly vein patterns (dotted, ethereal)
    for gx, gy in [(5, 7), (6, 6), (7, 5), (8, 5), (9, 6), (10, 7), (11, 8)]:
        ghost_iron.set_at((gx, gy), PALETTE[3])
    ghost_iron.set_at((7, 11), PALETTE[4])
    ghost_iron.set_at((9, 12), PALETTE[4])
    ghost_iron.set_at((8, 8), PALETTE[4])
    save_surface(os.path.join(output_dir, "ghost_iron.png"), ghost_iron)

    # Star Metal (16x16) — cosmic golden ore with star-like facets
    star_metal = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (105, 95, 75),    # Brownish cosmic rock
        2: (80, 70, 50),     # Dark shadow
        3: (215, 175, 55),   # Star metal gold
        4: (250, 205, 75),   # Bright star sparkle
        5: (185, 150, 45),   # Mid gold
    }
    # Cosmic rock base
    polygon(star_metal, [(3, 11), (5, 5), (10, 4), (13, 7), (14, 11), (12, 14), (6, 15), (4, 13)], PALETTE[1])
    polygon(star_metal, [(5, 11), (7, 6), (10, 5), (12, 8), (11, 13), (7, 14)], PALETTE[5])
    # Star-like facets (4-pointed star shapes)
    star_metal.set_at((8, 5), PALETTE[4])
    star_metal.set_at((7, 6), PALETTE[3])
    star_metal.set_at((9, 6), PALETTE[3])
    star_metal.set_at((8, 7), PALETTE[3])
    star_metal.set_at((7, 9), PALETTE[3])
    star_metal.set_at((9, 9), PALETTE[3])
    star_metal.set_at((8, 10), PALETTE[4])
    star_metal.set_at((6, 11), PALETTE[3])
    star_metal.set_at((10, 11), PALETTE[3])
    star_metal.set_at((8, 12), PALETTE[3])
    save_surface(os.path.join(output_dir, "star_metal.png"), star_metal)

    # Ancient Rune (16x16) — stone tablet with glowing runic inscriptions
    ancient_rune = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (85, 90, 98),     # Weathered stone
        2: (65, 70, 78),     # Dark shadow
        3: (75, 155, 115),   # Rune green glow
        4: (115, 215, 155),  # Bright rune
        5: (105, 115, 125),  # Mid stone
    }
    # Stone tablet (rectangular with rounded edges)
    rectangle(ancient_rune, (4, 4, 8, 11), PALETTE[1])
    rectangle(ancient_rune, (5, 5, 6, 9), PALETTE[5])
    rectangle(ancient_rune, (4, 4, 8, 1), PALETTE[2])
    rectangle(ancient_rune, (4, 4, 1, 11), PALETTE[2])
    # Runic inscriptions (glowing pixel patterns)
    # Top row runes
    ancient_rune.set_at((5, 6), PALETTE[3])
    ancient_rune.set_at((6, 6), PALETTE[4])
    ancient_rune.set_at((7, 6), PALETTE[3])
    ancient_rune.set_at((9, 6), PALETTE[3])
    ancient_rune.set_at((10, 6), PALETTE[4])
    ancient_rune.set_at((11, 6), PALETTE[3])
    # Middle row
    ancient_rune.set_at((5, 8), PALETTE[3])
    ancient_rune.set_at((7, 8), PALETTE[4])
    ancient_rune.set_at((9, 8), PALETTE[3])
    ancient_rune.set_at((11, 8), PALETTE[3])
    # Bottom row
    ancient_rune.set_at((6, 10), PALETTE[3])
    ancient_rune.set_at((8, 10), PALETTE[4])
    ancient_rune.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "ancient_rune.png"), ancient_rune)

    # Amber (16x16) — translucent fossil resin with inclusions
    amber = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (175, 115, 35),   # Amber brown
        2: (145, 95, 25),    # Dark amber
        3: (225, 165, 45),   # Bright amber
        4: (250, 195, 65),   # Golden glow
        5: (195, 140, 40),   # Mid amber
    }
    # Organic amber shape (rounded, slightly irregular)
    circle(amber, (8, 9), 6, PALETTE[1])
    circle(amber, (6, 8), 4, PALETTE[2])
    circle(amber, (10, 8), 4, PALETTE[5])
    # Fossil inclusions (tiny dots inside)
    amber.set_at((6, 7), PALETTE[4])
    amber.set_at((7, 6), PALETTE[3])
    amber.set_at((9, 6), PALETTE[4])
    amber.set_at((10, 7), PALETTE[3])
    amber.set_at((7, 10), PALETTE[3])
    amber.set_at((9, 10), PALETTE[4])
    amber.set_at((8, 12), PALETTE[3])
    # Surface glow
    amber.set_at((8, 5), PALETTE[4])
    save_surface(os.path.join(output_dir, "amber.png"), amber)

    # Moonstone (16x16) — pale blue-white crystal with moon glow
    moonstone = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (155, 165, 182),  # Pale grey-blue
        2: (125, 135, 152),  # Dark shadow
        3: (175, 195, 228),  # Moonstone crystal
        4: (205, 222, 252),  # Bright moon glow
        5: (145, 165, 192),  # Mid blue
    }
    # Crystal cluster shape
    polygon(moonstone, [(5, 6), (7, 3), (10, 3), (12, 6), (11, 11), (8, 14), (5, 12)], PALETTE[1])
    polygon(moonstone, [(6, 7), (8, 4), (10, 5), (11, 8), (9, 13), (6, 11)], PALETTE[5])
    # Crystal facets
    polygon(moonstone, [(8, 3), (10, 6), (8, 10), (6, 6)], PALETTE[3])
    moonstone.set_at((8, 5), PALETTE[4])
    moonstone.set_at((7, 7), PALETTE[4])
    moonstone.set_at((9, 7), PALETTE[4])
    moonstone.set_at((8, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "moonstone.png"), moonstone)

    # Celestial Crystal (16x16) — multi-faceted prismatic crystal
    celestial_crystal = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (75, 55, 115),    # Deep violet base
        2: (55, 40, 85),     # Very dark violet
        3: (155, 95, 215),   # Celestial purple
        4: (195, 145, 250),  # Bright celestial glow
        5: (115, 75, 175),   # Mid violet
    }
    # Prismatic crystal (tall, multi-faceted)
    polygon(celestial_crystal, [(6, 4), (8, 2), (10, 4), (12, 7), (11, 12), (8, 15), (5, 12), (4, 7)], PALETTE[1])
    polygon(celestial_crystal, [(7, 5), (8, 3), (9, 5), (11, 8), (9, 14), (7, 11)], PALETTE[5])
    # Prismatic facets (rainbow-like triangles)
    polygon(celestial_crystal, [(8, 2), (10, 6), (8, 8)], PALETTE[3])
    polygon(celestial_crystal, [(6, 5), (8, 7), (5, 9)], PALETTE[3])
    polygon(celestial_crystal, [(10, 5), (12, 8), (9, 9)], PALETTE[3])
    # Glow nodes on facets
    celestial_crystal.set_at((8, 4), PALETTE[4])
    celestial_crystal.set_at((6, 7), PALETTE[4])
    celestial_crystal.set_at((10, 7), PALETTE[4])
    celestial_crystal.set_at((8, 10), PALETTE[4])
    save_surface(os.path.join(output_dir, "celestial_crystal.png"), celestial_crystal)

    print("  Generated 9 tier 3/4 rock/ore sprites")


# ── Tier 3/4 World Resource Sprites ──────────────────────────────────

def generate_tier3_world_sprites() -> None:
    """Generate tier 3/4 world resource sprites — distinct visuals per type."""
    print("\n=== Generating Tier 3/4 World Resource Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "world")

    # Dragon Bone (16x16) — massive fossilized bone with joint ends
    dragon_bone = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (205, 195, 175),  # Bone white
        2: (175, 165, 145),  # Dark bone
        3: (230, 220, 200),  # Highlight
        4: (150, 140, 120),  # Very dark
        5: (185, 175, 155),  # Mid bone
    }
    # Main shaft (thick, slightly curved)
    rectangle(dragon_bone, (4, 6, 8, 5), PALETTE[1])
    # Joint ends (larger rounded caps)
    circle(dragon_bone, (4, 6), 3, PALETTE[1])
    circle(dragon_bone, (4, 6), 2, PALETTE[3])
    circle(dragon_bone, (4, 11), 3, PALETTE[1])
    circle(dragon_bone, (4, 11), 2, PALETTE[3])
    circle(dragon_bone, (12, 6), 3, PALETTE[1])
    circle(dragon_bone, (12, 6), 2, PALETTE[3])
    circle(dragon_bone, (12, 11), 3, PALETTE[1])
    circle(dragon_bone, (12, 11), 2, PALETTE[3])
    # Inner shaft detail (medullary cavity lines)
    rectangle(dragon_bone, (5, 7, 6, 1), PALETTE[2])
    rectangle(dragon_bone, (5, 10, 6, 1), PALETTE[2])
    rectangle(dragon_bone, (6, 8, 4, 1), PALETTE[5])
    # Weathering cracks
    dragon_bone.set_at((6, 8), PALETTE[4])
    dragon_bone.set_at((10, 9), PALETTE[4])
    dragon_bone.set_at((7, 10), PALETTE[4])
    save_surface(os.path.join(output_dir, "dragonbone.png"), dragon_bone)

    # Phoenix Feather (16x16) — fiery gradient feather with barbs
    phoenix_feather = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (210, 70, 15),    # Fire orange (body)
        2: (190, 50, 5),     # Dark fire orange
        3: (250, 150, 25),   # Bright flame
        4: (255, 195, 55),   # Golden highlight
        5: (170, 30, 0),     # Deep red
        6: (255, 220, 80),   # Yellow tip
    }
    # Feather body (asymmetric teardrop shape)
    for fy in range(2, 14):
        if fy < 5:
            w = 1
            cx = 8
        elif fy < 9:
            w = 2
            cx = 8 + ((fy % 3) - 1)
        else:
            w = 1 + ((fy % 2))
            cx = 8 + ((fy % 4) - 1)
        for fx in range(cx - w, cx + w + 1):
            if 0 <= fx < 16:
                phoenix_feather.set_at((fx, fy), PALETTE[1])
    # Quill (dark center line)
    rectangle(phoenix_feather, (8, 2, 1, 12), PALETTE[2])
    # Barb highlights (flame-like streaks on sides)
    phoenix_feather.set_at((7, 4), PALETTE[3])
    phoenix_feather.set_at((9, 5), PALETTE[4])
    phoenix_feather.set_at((6, 6), PALETTE[3])
    phoenix_feather.set_at((9, 7), PALETTE[4])
    phoenix_feather.set_at((7, 8), PALETTE[3])
    phoenix_feather.set_at((10, 9), PALETTE[3])
    phoenix_feather.set_at((7, 10), PALETTE[4])
    phoenix_feather.set_at((9, 11), PALETTE[3])
    phoenix_feather.set_at((8, 12), PALETTE[5])
    # Bright tip
    phoenix_feather.set_at((8, 2), PALETTE[6])
    phoenix_feather.set_at((7, 3), PALETTE[4])
    phoenix_feather.set_at((9, 3), PALETTE[4])
    save_surface(os.path.join(output_dir, "phoenix_feather.png"), phoenix_feather)

    # Silk Nest (16x16) — layered silk web with cocoon center
    silk_nest = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (195, 190, 175),  # Silk white
        2: (175, 170, 155),  # Dark silk
        3: (215, 210, 195),  # Bright silk
        4: (150, 145, 130),  # Very dark
        5: (225, 220, 205),  # Glow silk
    }
    # Outer web ring
    for angle in range(0, 360, 25):
        import math
        for r in range(2, 6):
            sx = int(8 + r * math.cos(math.radians(angle)))
            sy = int(8 + r * math.sin(math.radians(angle)))
            if 0 <= sx < 16 and 0 <= sy < 16:
                silk_nest.set_at((sx, sy), PALETTE[1])
    # Radial threads
    for angle in range(0, 360, 45):
        import math
        for r in range(2, 6):
            sx = int(8 + r * math.cos(math.radians(angle)))
            sy = int(8 + r * math.sin(math.radians(angle)))
            if 0 <= sx < 16 and 0 <= sy < 16:
                silk_nest.set_at((sx, sy), PALETTE[2])
    # Dense cocoon center
    circle(silk_nest, (8, 8), 3, PALETTE[3])
    circle(silk_nest, (8, 8), 2, PALETTE[5])
    silk_nest.set_at((8, 7), PALETTE[5])
    silk_nest.set_at((8, 9), PALETTE[5])
    save_surface(os.path.join(output_dir, "silk_nest.png"), silk_nest)

    # Void Essence (16x16) — swirling dark purple energy orb
    void_essence = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (45, 25, 75),     # Deep void purple
        2: (30, 15, 50),     # Very dark void
        3: (95, 55, 155),    # Void purple swirl
        4: (145, 95, 215),   # Bright void glow
        5: (65, 40, 100),    # Mid void
        6: (180, 130, 245),  # Outer glow
    }
    # Outer glow aura
    circle(void_essence, (8, 8), 6, PALETTE[1])
    circle(void_essence, (8, 8), 5, PALETTE[2])
    # Swirling tendrils (offset circles creating motion)
    circle(void_essence, (7, 7), 3, PALETTE[3])
    circle(void_essence, (9, 9), 3, PALETTE[5])
    circle(void_essence, (6, 8), 2, PALETTE[3])
    circle(void_essence, (10, 8), 2, PALETTE[5])
    circle(void_essence, (8, 6), 2, PALETTE[3])
    circle(void_essence, (8, 10), 2, PALETTE[5])
    # Core glow
    circle(void_essence, (8, 8), 2, PALETTE[4])
    void_essence.set_at((7, 7), PALETTE[4])
    void_essence.set_at((9, 9), PALETTE[4])
    void_essence.set_at((8, 5), PALETTE[6])
    void_essence.set_at((8, 11), PALETTE[6])
    save_surface(os.path.join(output_dir, "void_essence.png"), void_essence)

    print("  Generated 4 tier 3/4 world resource sprites")


# ── Elder Wood Tree ──────────────────────────────────────────────────

def generate_elder_wood_tree() -> None:
    """Generate the elder wood tree sprite (32x32)."""
    print("\n=== Generating Elder Wood Tree Sprite ===")
    output_dir = os.path.join(OUTPUT_ROOT, "trees")

    elder_wood = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 60, 40),     # Dark brown (trunk)
        2: (60, 45, 30),     # Very dark brown (shadow)
        3: (40, 80, 50),     # Deep forest green (shadow)
        4: (50, 100, 60),    # Medium green
        5: (70, 130, 70),    # Light green
        6: (90, 155, 80),    # Bright green (sunlit)
        7: (100, 170, 90),   # Very bright (tips)
    }
    # Thick ancient trunk
    rectangle(elder_wood, (13, 20, 6, 12), PALETTE[1])
    add_bark_texture(elder_wood, 13, 20, 6, 12, (60, 45, 30), (100, 75, 50))
    # Root flares
    rectangle(elder_wood, (11, 29, 3, 2), PALETTE[1])
    rectangle(elder_wood, (18, 29, 3, 2), PALETTE[1])
    # Massive ancient canopy (wider than oak)
    circle(elder_wood, (16, 12), 11, PALETTE[3])
    circle(elder_wood, (10, 11), 7, PALETTE[3])
    circle(elder_wood, (22, 11), 7, PALETTE[3])
    circle(elder_wood, (13, 10), 6, PALETTE[4])
    circle(elder_wood, (19, 10), 6, PALETTE[4])
    circle(elder_wood, (16, 9), 6, PALETTE[4])
    # Light layers
    circle(elder_wood, (14, 8), 5, PALETTE[5])
    circle(elder_wood, (18, 8), 5, PALETTE[5])
    circle(elder_wood, (16, 7), 4, PALETTE[6])
    # Sunlit crown
    circle(elder_wood, (16, 6), 3, PALETTE[7])
    elder_wood.set_at((15, 5), PALETTE[6])
    elder_wood.set_at((17, 5), PALETTE[6])
    elder_wood.set_at((16, 4), PALETTE[7])
    # Leaf clustering
    add_leaf_clustering(elder_wood, 16, 10, 6, PALETTE[3], PALETTE[5], PALETTE[6], 8)
    # Dark shadow patches
    elder_wood.set_at((12, 13), PALETTE[3])
    elder_wood.set_at((20, 12), PALETTE[3])
    elder_wood.set_at((16, 14), PALETTE[3])
    save_surface(os.path.join(output_dir, "elder_wood.png"), elder_wood)
    print("  Saved: " + os.path.join(output_dir, "elder_wood.png"))


# ── Tier 3/4 Item Sprites ────────────────────────────────────────────

def generate_tier3_item_sprites() -> None:
    """Generate tier 3/4 item sprites."""
    print("\n=== Generating Tier 3/4 Item Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "items")

    # ── Mithril Ingot ──
    mithril_ingot = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 160, 220),  # Mithril blue
        2: (140, 190, 255),  # Bright highlight
        3: (70, 120, 180),   # Dark mithril
        4: (80, 80, 90),     # Dark base
    }
    rectangle(mithril_ingot, (4, 8, 8, 5), PALETTE[4])
    rectangle(mithril_ingot, (4, 8, 8, 1), PALETTE[1])
    rectangle(mithril_ingot, (4, 10, 1, 3), PALETTE[2])
    rectangle(mithril_ingot, (11, 10, 1, 3), PALETTE[3])
    mithril_ingot.set_at((5, 7), PALETTE[2])
    mithril_ingot.set_at((6, 7), PALETTE[2])
    save_surface(os.path.join(output_dir, "mithril_ingot.png"), mithril_ingot)

    # ── Star Metal Ingot ──
    star_metal_ingot = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 180, 60),   # Star gold
        2: (255, 210, 80),   # Bright star
        3: (190, 150, 40),   # Dark star
        4: (80, 80, 90),     # Dark base
    }
    rectangle(star_metal_ingot, (4, 8, 8, 5), PALETTE[4])
    rectangle(star_metal_ingot, (4, 8, 8, 1), PALETTE[1])
    rectangle(star_metal_ingot, (4, 10, 1, 3), PALETTE[2])
    rectangle(star_metal_ingot, (11, 10, 1, 3), PALETTE[3])
    star_metal_ingot.set_at((5, 7), PALETTE[2])
    star_metal_ingot.set_at((6, 7), PALETTE[2])
    save_surface(os.path.join(output_dir, "star_metal_ingot.png"), star_metal_ingot)

    # ── Refined Ghost Iron ──
    refined_ghost_iron = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 185, 200),  # Ghost iron
        2: (210, 215, 230),  # Bright ghost
        3: (150, 155, 170),  # Dark ghost
        4: (80, 80, 90),     # Dark base
    }
    rectangle(refined_ghost_iron, (4, 8, 8, 5), PALETTE[4])
    rectangle(refined_ghost_iron, (4, 8, 8, 1), PALETTE[1])
    rectangle(refined_ghost_iron, (4, 10, 1, 3), PALETTE[2])
    rectangle(refined_ghost_iron, (11, 10, 1, 3), PALETTE[3])
    refined_ghost_iron.set_at((5, 7), PALETTE[2])
    save_surface(os.path.join(output_dir, "refined_ghost_iron.png"), refined_ghost_iron)

    # ── Mithril Longsword ──
    mithril_longsword = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 160, 220),  # Mithril blue (blade)
        2: (140, 190, 255),  # Bright edge
        3: (70, 120, 180),   # Dark mithril
        4: (139, 90, 43),    # Brown (handle)
        5: (100, 70, 35),    # Dark brown
    }
    # Blade
    rectangle(mithril_longsword, (7, 2, 2, 8), PALETTE[1])
    rectangle(mithril_longsword, (7, 2, 1, 8), PALETTE[2])  # Edge highlight
    rectangle(mithril_longsword, (9, 2, 1, 8), PALETTE[3])  # Shadow
    # Blade tip
    mithril_longsword.set_at((8, 1), PALETTE[2])
    mithril_longsword.set_at((7, 1), PALETTE[1])
    mithril_longsword.set_at((9, 1), PALETTE[1])
    # Crossguard
    rectangle(mithril_longsword, (5, 10, 6, 1), PALETTE[1])
    # Handle
    rectangle(mithril_longsword, (7, 11, 2, 4), PALETTE[4])
    rectangle(mithril_longsword, (7, 13, 2, 2), PALETTE[5])
    # Pommel
    mithril_longsword.set_at((8, 15), PALETTE[1])
    save_surface(os.path.join(output_dir, "mithril_longsword.png"), mithril_longsword)

    # ── Star Metal Longsword ──
    star_metal_longsword = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 180, 60),   # Star gold (blade)
        2: (255, 210, 80),   # Bright edge
        3: (190, 150, 40),   # Dark star
        4: (139, 90, 43),    # Brown (handle)
        5: (100, 70, 35),    # Dark brown
    }
    rectangle(star_metal_longsword, (7, 2, 2, 8), PALETTE[1])
    rectangle(star_metal_longsword, (7, 2, 1, 8), PALETTE[2])
    rectangle(star_metal_longsword, (9, 2, 1, 8), PALETTE[3])
    star_metal_longsword.set_at((8, 1), PALETTE[2])
    star_metal_longsword.set_at((7, 1), PALETTE[1])
    star_metal_longsword.set_at((9, 1), PALETTE[1])
    rectangle(star_metal_longsword, (5, 10, 6, 1), PALETTE[1])
    rectangle(star_metal_longsword, (7, 11, 2, 4), PALETTE[4])
    rectangle(star_metal_longsword, (7, 13, 2, 2), PALETTE[5])
    star_metal_longsword.set_at((8, 15), PALETTE[1])
    save_surface(os.path.join(output_dir, "star_metal_longsword.png"), star_metal_longsword)

    # ── Rune Mithril Longsword ──
    rune_mithril_longsword = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 160, 220),  # Mithril blue (blade)
        2: (140, 190, 255),  # Bright edge
        3: (70, 120, 180),   # Dark mithril
        4: (80, 160, 120),   # Rune green (inscriptions)
        5: (120, 220, 160),  # Bright rune glow
        6: (139, 90, 43),    # Brown (handle)
        7: (100, 70, 35),    # Dark brown
    }
    rectangle(rune_mithril_longsword, (7, 2, 2, 8), PALETTE[1])
    rectangle(rune_mithril_longsword, (7, 2, 1, 8), PALETTE[2])
    rectangle(rune_mithril_longsword, (9, 2, 1, 8), PALETTE[3])
    rune_mithril_longsword.set_at((8, 1), PALETTE[2])
    rune_mithril_longsword.set_at((7, 1), PALETTE[1])
    rune_mithril_longsword.set_at((9, 1), PALETTE[1])
    # Rune inscriptions on blade
    rune_mithril_longsword.set_at((8, 3), PALETTE[4])
    rune_mithril_longsword.set_at((8, 5), PALETTE[5])
    rune_mithril_longsword.set_at((8, 7), PALETTE[4])
    rectangle(rune_mithril_longsword, (5, 10, 6, 1), PALETTE[1])
    rectangle(rune_mithril_longsword, (7, 11, 2, 4), PALETTE[6])
    rectangle(rune_mithril_longsword, (7, 13, 2, 2), PALETTE[7])
    rune_mithril_longsword.set_at((8, 15), PALETTE[1])
    save_surface(os.path.join(output_dir, "rune_mithril_longsword.png"), rune_mithril_longsword)

    # ── Ghost Iron Chestplate ──
    ghost_iron_chestplate = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 185, 200),  # Ghost iron
        2: (210, 215, 230),  # Bright highlight
        3: (150, 155, 170),  # Dark ghost
        4: (120, 125, 140),  # Shadow
    }
    # Chestplate body (V-shape)
    rectangle(ghost_iron_chestplate, (4, 5, 8, 8), PALETTE[1])
    rectangle(ghost_iron_chestplate, (4, 5, 8, 1), PALETTE[2])  # Top highlight
    rectangle(ghost_iron_chestplate, (4, 12, 8, 1), PALETTE[3])  # Bottom shadow
    rectangle(ghost_iron_chestplate, (4, 5, 1, 8), PALETTE[2])  # Left edge
    # Chest detail (center line)
    rectangle(ghost_iron_chestplate, (7, 5, 2, 8), PALETTE[4])
    # Shoulder bumps
    circle(ghost_iron_chestplate, (5, 5), 2, PALETTE[1])
    circle(ghost_iron_chestplate, (11, 5), 2, PALETTE[1])
    save_surface(os.path.join(output_dir, "ghost_iron_chestplate.png"), ghost_iron_chestplate)

    # ── Celestial Chestplate ──
    celestial_chestplate = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (160, 100, 220),  # Celestial purple
        2: (200, 150, 255),  # Bright celestial
        3: (120, 80, 180),   # Dark celestial
        4: (100, 60, 150),   # Deep shadow
    }
    rectangle(celestial_chestplate, (4, 5, 8, 8), PALETTE[1])
    rectangle(celestial_chestplate, (4, 5, 8, 1), PALETTE[2])
    rectangle(celestial_chestplate, (4, 12, 8, 1), PALETTE[3])
    rectangle(celestial_chestplate, (4, 5, 1, 8), PALETTE[2])
    rectangle(celestial_chestplate, (7, 5, 2, 8), PALETTE[4])
    circle(celestial_chestplate, (5, 5), 2, PALETTE[1])
    circle(celestial_chestplate, (11, 5), 2, PALETTE[1])
    # Celestial gem in center
    polygon(celestial_chestplate, [(8, 7), (10, 9), (8, 11), (6, 9)], PALETTE[2])
    celestial_chestplate.set_at((8, 9), PALETTE[2])
    save_surface(os.path.join(output_dir, "celestial_chestplate.png"), celestial_chestplate)

    # ── Polished Void Crystal ──
    polished_void_crystal = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 60, 160),   # Void purple
        2: (150, 100, 220),  # Bright void
        3: (70, 40, 120),    # Dark void
        4: (180, 130, 255),  # Sparkle
    }
    # Polished crystal (diamond shape)
    polygon(polished_void_crystal, [(8, 3), (12, 8), (8, 14), (4, 8)], PALETTE[1])
    polygon(polished_void_crystal, [(8, 5), (10, 8), (8, 12), (6, 8)], PALETTE[2])
    polished_void_crystal.set_at((8, 7), PALETTE[4])
    polished_void_crystal.set_at((7, 9), PALETTE[4])
    polished_void_crystal.set_at((9, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "polished_void_crystal.png"), polished_void_crystal)

    # ── Polished Amber ──
    polished_amber = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 145, 45),   # Amber
        2: (240, 185, 60),   # Bright amber
        3: (170, 120, 35),   # Dark amber
        4: (255, 210, 80),   # Golden sparkle
    }
    polygon(polished_amber, [(8, 3), (12, 8), (8, 14), (4, 8)], PALETTE[1])
    polygon(polished_amber, [(8, 5), (10, 8), (8, 12), (6, 8)], PALETTE[2])
    polished_amber.set_at((8, 6), PALETTE[4])
    polished_amber.set_at((7, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "polished_amber.png"), polished_amber)

    # ── Polished Dragonbone ──
    polished_dragonbone = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 210, 190),  # Bone white
        2: (240, 230, 210),  # Highlight
        3: (190, 180, 160),  # Dark bone
        4: (170, 160, 140),  # Very dark
    }
    rectangle(polished_dragonbone, (4, 6, 8, 4), PALETTE[1])
    circle(polished_dragonbone, (4, 6), 3, PALETTE[1])
    circle(polished_dragonbone, (4, 10), 3, PALETTE[1])
    circle(polished_dragonbone, (12, 6), 3, PALETTE[1])
    circle(polished_dragonbone, (12, 10), 3, PALETTE[1])
    polished_dragonbone.set_at((5, 6), PALETTE[2])
    polished_dragonbone.set_at((5, 10), PALETTE[2])
    polished_dragonbone.set_at((11, 6), PALETTE[2])
    polished_dragonbone.set_at((11, 10), PALETTE[2])
    rectangle(polished_dragonbone, (5, 7, 6, 1), PALETTE[3])
    rectangle(polished_dragonbone, (5, 9, 6, 1), PALETTE[3])
    save_surface(os.path.join(output_dir, "polished_dragonbone.png"), polished_dragonbone)

    # ── Bone Dragon (monster drop) ──
    bone_dragon = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 160, 130),  # Dragon bone (tannish)
        2: (150, 130, 100),  # Dark dragon bone
        3: (200, 180, 150),  # Highlight
        4: (130, 110, 80),   # Very dark
    }
    # Large jagged dragon bone
    rectangle(bone_dragon, (3, 6, 10, 4), PALETTE[1])
    circle(bone_dragon, (3, 6), 3, PALETTE[1])
    circle(bone_dragon, (3, 10), 3, PALETTE[1])
    circle(bone_dragon, (13, 6), 3, PALETTE[1])
    circle(bone_dragon, (13, 10), 3, PALETTE[1])
    bone_dragon.set_at((4, 6), PALETTE[3])
    bone_dragon.set_at((4, 10), PALETTE[3])
    bone_dragon.set_at((12, 6), PALETTE[3])
    bone_dragon.set_at((12, 10), PALETTE[3])
    # Ridge
    rectangle(bone_dragon, (4, 7, 8, 1), PALETTE[2])
    rectangle(bone_dragon, (4, 9, 8, 1), PALETTE[2])
    # Spikes
    bone_dragon.set_at((6, 5), PALETTE[1])
    bone_dragon.set_at((8, 5), PALETTE[3])
    bone_dragon.set_at((10, 5), PALETTE[1])
    save_surface(os.path.join(output_dir, "bone_dragon.png"), bone_dragon)

    # ── Ancient Rune (item) ──
    ancient_rune_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 160, 120),   # Rune green
        2: (120, 220, 160),  # Bright rune glow
        3: (60, 120, 90),    # Dark rune
        4: (40, 80, 60),     # Very dark
    }
    # Rune stone shape
    polygon(ancient_rune_item, [(8, 3), (12, 7), (11, 13), (8, 15), (5, 13), (4, 7)], PALETTE[3])
    polygon(ancient_rune_item, [(8, 5), (10, 8), (9, 12), (8, 13), (7, 12), (6, 8)], PALETTE[1])
    # Glowing runes
    ancient_rune_item.set_at((8, 6), PALETTE[2])
    ancient_rune_item.set_at((7, 9), PALETTE[2])
    ancient_rune_item.set_at((9, 9), PALETTE[2])
    ancient_rune_item.set_at((8, 11), PALETTE[2])
    save_surface(os.path.join(output_dir, "ancient_rune.png"), ancient_rune_item)

    # ── Amber (item) ──
    amber_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 145, 45),   # Amber
        2: (240, 185, 60),   # Bright
        3: (170, 120, 35),   # Dark
    }
    polygon(amber_item, [(8, 3), (12, 7), (11, 13), (8, 15), (5, 13), (4, 7)], PALETTE[1])
    polygon(amber_item, [(8, 5), (10, 8), (9, 12), (8, 13), (7, 12), (6, 8)], PALETTE[2])
    amber_item.set_at((8, 6), PALETTE[2])
    save_surface(os.path.join(output_dir, "amber.png"), amber_item)

    # ── Moonstone (item) ──
    moonstone_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 200, 230),  # Moonstone blue
        2: (210, 225, 255),  # Bright moon
        3: (150, 170, 200),  # Dark moon
    }
    polygon(moonstone_item, [(8, 3), (12, 7), (11, 13), (8, 15), (5, 13), (4, 7)], PALETTE[1])
    polygon(moonstone_item, [(8, 5), (10, 8), (9, 12), (8, 13), (7, 12), (6, 8)], PALETTE[2])
    moonstone_item.set_at((8, 6), PALETTE[2])
    save_surface(os.path.join(output_dir, "moonstone.png"), moonstone_item)

    # ── Celestial Crystal (item) ──
    celestial_crystal_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (160, 100, 220),  # Celestial purple
        2: (200, 150, 255),  # Bright
        3: (120, 80, 180),   # Dark
    }
    polygon(celestial_crystal_item, [(8, 2), (12, 6), (11, 13), (8, 15), (5, 13), (4, 6)], PALETTE[1])
    polygon(celestial_crystal_item, [(8, 4), (10, 7), (9, 12), (8, 13), (7, 12), (6, 7)], PALETTE[2])
    celestial_crystal_item.set_at((8, 5), PALETTE[2])
    celestial_crystal_item.set_at((7, 8), PALETTE[2])
    celestial_crystal_item.set_at((9, 8), PALETTE[2])
    save_surface(os.path.join(output_dir, "celestial_crystal.png"), celestial_crystal_item)

    # ── Attuned Celestial Crystal ──
    attuned_celestial_crystal = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (160, 100, 220),  # Celestial purple
        2: (200, 150, 255),  # Bright
        3: (120, 80, 180),   # Dark
        4: (230, 200, 255),  # Extra sparkle
    }
    polygon(attuned_celestial_crystal, [(8, 2), (12, 6), (11, 13), (8, 15), (5, 13), (4, 6)], PALETTE[1])
    polygon(attuned_celestial_crystal, [(8, 4), (10, 7), (9, 12), (8, 13), (7, 12), (6, 7)], PALETTE[2])
    attuned_celestial_crystal.set_at((8, 5), PALETTE[4])
    attuned_celestial_crystal.set_at((7, 8), PALETTE[4])
    attuned_celestial_crystal.set_at((9, 8), PALETTE[4])
    attuned_celestial_crystal.set_at((8, 10), PALETTE[4])
    save_surface(os.path.join(output_dir, "attuned_celestial_crystal.png"), attuned_celestial_crystal)

    # ── Void Essence (item) ──
    void_essence_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 30, 80),     # Deep void
        2: (100, 60, 160),   # Void purple
        3: (150, 100, 220),  # Bright void
        4: (200, 150, 255),  # Sparkle
    }
    circle(void_essence_item, (8, 8), 5, PALETTE[1])
    circle(void_essence_item, (7, 7), 3, PALETTE[2])
    circle(void_essence_item, (9, 9), 3, PALETTE[2])
    void_essence_item.set_at((7, 7), PALETTE[3])
    void_essence_item.set_at((9, 9), PALETTE[3])
    void_essence_item.set_at((8, 5), PALETTE[4])
    void_essence_item.set_at((8, 11), PALETTE[4])
    save_surface(os.path.join(output_dir, "void_essence.png"), void_essence_item)

    # ── Void Essence Concentrate ──
    void_essence_concentrate = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (40, 20, 70),     # Very deep void
        2: (80, 50, 140),    # Void purple
        3: (130, 90, 200),   # Bright void
        4: (180, 130, 255),  # Intense sparkle
    }
    circle(void_essence_concentrate, (8, 8), 5, PALETTE[1])
    circle(void_essence_concentrate, (7, 7), 3, PALETTE[2])
    circle(void_essence_concentrate, (9, 9), 3, PALETTE[2])
    void_essence_concentrate.set_at((7, 7), PALETTE[3])
    void_essence_concentrate.set_at((9, 9), PALETTE[3])
    void_essence_concentrate.set_at((8, 5), PALETTE[4])
    void_essence_concentrate.set_at((8, 11), PALETTE[4])
    void_essence_concentrate.set_at((6, 8), PALETTE[4])
    void_essence_concentrate.set_at((10, 8), PALETTE[4])
    save_surface(os.path.join(output_dir, "void_essence_concentrate.png"), void_essence_concentrate)

    # ── Crystal Void ──
    crystal_void = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (40, 25, 65),     # Deep void
        2: (90, 55, 150),    # Void purple
        3: (140, 100, 210),  # Bright crystal
        4: (190, 150, 255),  # Sparkle
    }
    # Void crystal shape (angular)
    polygon(crystal_void, [(8, 2), (12, 6), (11, 14), (8, 15), (5, 14), (4, 6)], PALETTE[1])
    polygon(crystal_void, [(8, 4), (10, 7), (9, 13), (8, 14), (7, 13), (6, 7)], PALETTE[2])
    polygon(crystal_void, [(8, 6), (9, 8), (8, 12), (7, 8)], PALETTE[3])
    crystal_void.set_at((8, 7), PALETTE[4])
    crystal_void.set_at((7, 9), PALETTE[4])
    crystal_void.set_at((9, 9), PALETTE[4])
    save_surface(os.path.join(output_dir, "crystal_void.png"), crystal_void)

    # ── Obsidian (item) ──
    obsidian_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (30, 28, 32),     # Near-black
        2: (70, 65, 75),     # Glass sheen
        3: (110, 105, 120),  # Highlight
    }
    polygon(obsidian_item, [(8, 3), (12, 7), (11, 13), (8, 15), (5, 13), (4, 7)], PALETTE[1])
    polygon(obsidian_item, [(8, 5), (10, 8), (9, 12), (8, 13), (7, 12), (6, 8)], PALETTE[2])
    obsidian_item.set_at((8, 6), PALETTE[3])
    obsidian_item.set_at((7, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "obsidian.png"), obsidian_item)

    # ── Obsidian Glass ──
    obsidian_glass = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (50, 48, 55),     # Dark glass
        2: (90, 85, 100),    # Glass sheen
        3: (140, 135, 155),  # Bright highlight
    }
    rectangle(obsidian_glass, (3, 4, 10, 9), PALETTE[1])
    rectangle(obsidian_glass, (3, 4, 10, 1), PALETTE[2])
    rectangle(obsidian_glass, (3, 11, 10, 1), PALETTE[1])
    rectangle(obsidian_glass, (3, 5, 1, 8), PALETTE[2])
    obsidian_glass.set_at((5, 6), PALETTE[3])
    obsidian_glass.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "obsidian_glass.png"), obsidian_glass)

    # ── Rune Stone ──
    rune_stone = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (90, 95, 100),    # Stone grey
        2: (80, 160, 120),   # Rune green
        3: (120, 220, 160),  # Bright rune
        4: (70, 75, 80),     # Dark stone
    }
    circle(rune_stone, (8, 9), 5, PALETTE[1])
    circle(rune_stone, (6, 8), 3, PALETTE[4])
    # Rune marks
    rune_stone.set_at((6, 6), PALETTE[2])
    rune_stone.set_at((7, 6), PALETTE[3])
    rune_stone.set_at((8, 6), PALETTE[2])
    rune_stone.set_at((10, 6), PALETTE[2])
    rune_stone.set_at((11, 6), PALETTE[3])
    rune_stone.set_at((6, 9), PALETTE[2])
    rune_stone.set_at((8, 9), PALETTE[3])
    rune_stone.set_at((10, 9), PALETTE[2])
    save_surface(os.path.join(output_dir, "rune_stone.png"), rune_stone)

    # ── Silk (item) ──
    silk_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 215, 200),  # Silky white
        2: (200, 195, 180),  # Dark silk
        3: (240, 235, 220),  # Bright silk
    }
    # Woven silk threads
    rectangle(silk_item, (3, 5, 10, 2), PALETTE[1])
    rectangle(silk_item, (3, 8, 10, 2), PALETTE[1])
    rectangle(silk_item, (3, 11, 10, 2), PALETTE[1])
    rectangle(silk_item, (4, 6, 8, 1), PALETTE[2])
    rectangle(silk_item, (4, 9, 8, 1), PALETTE[2])
    rectangle(silk_item, (4, 12, 8, 1), PALETTE[2])
    silk_item.set_at((5, 5), PALETTE[3])
    silk_item.set_at((7, 8), PALETTE[3])
    silk_item.set_at((9, 11), PALETTE[3])
    save_surface(os.path.join(output_dir, "silk.png"), silk_item)

    # ── Silk Thread ──
    silk_thread = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 215, 200),  # Silk white
        2: (200, 195, 180),  # Dark
        3: (240, 235, 220),  # Bright
    }
    # Coiled thread
    for angle in range(0, 360, 15):
        import math
        r = 3 + (angle % 30) * 0.1
        sx = int(8 + r * math.cos(math.radians(angle)))
        sy = int(8 + r * math.sin(math.radians(angle)))
        if 0 <= sx < 16 and 0 <= sy < 16:
            silk_thread.set_at((sx, sy), PALETTE[1])
    silk_thread.set_at((8, 8), PALETTE[3])
    save_surface(os.path.join(output_dir, "silk_thread.png"), silk_thread)

    # ── Silk Fabric ──
    silk_fabric = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (230, 225, 210),  # Fine silk
        2: (210, 205, 190),  # Weave shadow
        3: (245, 240, 225),  # Bright weave
    }
    rectangle(silk_fabric, (3, 4, 10, 9), PALETTE[1])
    # Weave pattern
    for wy in range(4, 13, 2):
        rectangle(silk_fabric, (3, wy, 10, 1), PALETTE[2])
    for wx in range(3, 13, 2):
        rectangle(silk_fabric, (wx, 4, 1, 9), PALETTE[2])
    silk_fabric.set_at((4, 5), PALETTE[3])
    silk_fabric.set_at((8, 7), PALETTE[3])
    silk_fabric.set_at((11, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "silk_fabric.png"), silk_fabric)

    # ── Phoenix Cloth ──
    phoenix_cloth = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 100, 30),   # Fire orange
        2: (200, 80, 20),    # Dark fire
        3: (255, 160, 50),   # Bright flame
        4: (180, 60, 10),    # Deep red
    }
    rectangle(phoenix_cloth, (3, 4, 10, 9), PALETTE[1])
    rectangle(phoenix_cloth, (3, 4, 10, 1), PALETTE[3])
    rectangle(phoenix_cloth, (3, 11, 10, 1), PALETTE[2])
    # Flame pattern
    for fx in range(4, 12):
        for fy in range(5, 12):
            if (fx + fy) % 4 == 0:
                phoenix_cloth.set_at((fx, fy), PALETTE[3])
            elif (fx + fy) % 4 == 2:
                phoenix_cloth.set_at((fx, fy), PALETTE[4])
    save_surface(os.path.join(output_dir, "phoenix_cloth.png"), phoenix_cloth)

    # ── Phoenix Cloak ──
    phoenix_cloak = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 100, 30),   # Fire orange
        2: (200, 80, 20),    # Dark fire
        3: (255, 160, 50),   # Bright flame
        4: (180, 60, 10),    # Deep red
        5: (255, 200, 80),   # Golden highlight
    }
    # Cloak shape (wider at bottom)
    rectangle(phoenix_cloak, (4, 4, 8, 3), PALETTE[1])
    rectangle(phoenix_cloak, (3, 7, 10, 3), PALETTE[1])
    rectangle(phoenix_cloak, (2, 10, 12, 3), PALETTE[1])
    rectangle(phoenix_cloak, (4, 4, 8, 1), PALETTE[3])
    rectangle(phoenix_cloak, (3, 7, 10, 1), PALETTE[3])
    rectangle(phoenix_cloak, (2, 10, 12, 1), PALETTE[3])
    # Flame details
    phoenix_cloak.set_at((5, 5), PALETTE[5])
    phoenix_cloak.set_at((10, 8), PALETTE[5])
    phoenix_cloak.set_at((4, 11), PALETTE[5])
    save_surface(os.path.join(output_dir, "phoenix_cloak.png"), phoenix_cloak)

    # ── Silk Enchanted Cloak ──
    silk_enchanted_cloak = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 215, 200),  # Silk white
        2: (200, 195, 180),  # Dark silk
        3: (160, 100, 220),  # Enchantment purple
        4: (200, 150, 255),  # Bright enchant
        5: (240, 235, 220),  # Bright silk
    }
    rectangle(silk_enchanted_cloak, (4, 4, 8, 3), PALETTE[1])
    rectangle(silk_enchanted_cloak, (3, 7, 10, 3), PALETTE[1])
    rectangle(silk_enchanted_cloak, (2, 10, 12, 3), PALETTE[1])
    rectangle(silk_enchanted_cloak, (4, 4, 8, 1), PALETTE[5])
    rectangle(silk_enchanted_cloak, (3, 7, 10, 1), PALETTE[5])
    rectangle(silk_enchanted_cloak, (2, 10, 12, 1), PALETTE[5])
    # Enchantment sparkles
    silk_enchanted_cloak.set_at((5, 5), PALETTE[4])
    silk_enchanted_cloak.set_at((10, 8), PALETTE[4])
    silk_enchanted_cloak.set_at((4, 11), PALETTE[4])
    silk_enchanted_cloak.set_at((8, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "silk_enchanted_cloak.png"), silk_enchanted_cloak)

    # ── Elder Wood ──
    elder_wood_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 60, 40),     # Dark wood
        2: (60, 45, 30),     # Very dark
        3: (100, 75, 50),    # Light wood
        4: (120, 90, 60),    # Highlight
    }
    rectangle(elder_wood_item, (3, 6, 10, 5), PALETTE[1])
    rectangle(elder_wood_item, (3, 8, 10, 2), PALETTE[2])
    rectangle(elder_wood_item, (3, 6, 10, 1), PALETTE[3])
    # Bark texture
    elder_wood_item.set_at((5, 7), PALETTE[4])
    elder_wood_item.set_at((8, 7), PALETTE[4])
    elder_wood_item.set_at((10, 8), PALETTE[4])
    save_surface(os.path.join(output_dir, "elder_wood.png"), elder_wood_item)

    # ── Elder Wood Planks ──
    elder_wood_planks = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (120, 90, 60),    # Light wood
        2: (100, 75, 50),    # Medium wood
        3: (140, 110, 70),   # Highlight
        4: (80, 60, 40),     # Dark
    }
    rectangle(elder_wood_planks, (2, 5, 12, 6), PALETTE[1])
    rectangle(elder_wood_planks, (2, 5, 12, 1), PALETTE[3])
    rectangle(elder_wood_planks, (2, 9, 12, 1), PALETTE[2])
    # Plank lines
    rectangle(elder_wood_planks, (6, 5, 1, 6), PALETTE[4])
    rectangle(elder_wood_planks, (10, 5, 1, 6), PALETTE[4])
    save_surface(os.path.join(output_dir, "elder_wood_planks.png"), elder_wood_planks)

    # ── Elder Wood Staff ──
    elder_wood_staff = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 60, 40),     # Dark wood
        2: (100, 75, 50),    # Medium wood
        3: (120, 90, 60),    # Light wood
        4: (160, 100, 220),  # Celestial glow
        5: (200, 150, 255),  # Bright glow
    }
    # Staff shaft
    rectangle(elder_wood_staff, (7, 3, 2, 11), PALETTE[1])
    rectangle(elder_wood_staff, (7, 3, 1, 11), PALETTE[3])  # Highlight
    # Crystal on top
    polygon(elder_wood_staff, [(8, 1), (10, 4), (8, 6), (6, 4)], PALETTE[4])
    polygon(elder_wood_staff, [(8, 2), (9, 4), (8, 5), (7, 4)], PALETTE[5])
    save_surface(os.path.join(output_dir, "elder_wood_staff.png"), elder_wood_staff)

    # ── Dragonbone Whistle ──
    dragonbone_whistle = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (200, 190, 170),  # Bone white
        2: (180, 170, 150),  # Dark bone
        3: (220, 210, 190),  # Highlight
        4: (160, 150, 130),  # Very dark
    }
    # Whistle shape (tube with hole)
    rectangle(dragonbone_whistle, (5, 6, 6, 4), PALETTE[1])
    circle(dragonbone_whistle, (5, 8), 2, PALETTE[1])
    circle(dragonbone_whistle, (11, 8), 2, PALETTE[1])
    # Mouth hole
    circle(dragonbone_whistle, (11, 8), 1, PALETTE[4])
    # Finger hole
    dragonbone_whistle.set_at((7, 8), PALETTE[4])
    # Highlight
    dragonbone_whistle.set_at((6, 6), PALETTE[3])
    dragonbone_whistle.set_at((8, 7), PALETTE[3])
    save_surface(os.path.join(output_dir, "dragonbone_whistle.png"), dragonbone_whistle)

    # ── Moonstone Essence ──
    moonstone_essence = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 200, 230),  # Moonstone blue
        2: (210, 225, 255),  # Bright moon
        3: (150, 170, 200),  # Dark moon
    }
    circle(moonstone_essence, (8, 8), 5, PALETTE[1])
    circle(moonstone_essence, (7, 7), 3, PALETTE[2])
    circle(moonstone_essence, (9, 9), 3, PALETTE[3])
    moonstone_essence.set_at((8, 5), PALETTE[2])
    moonstone_essence.set_at((6, 8), PALETTE[2])
    save_surface(os.path.join(output_dir, "moonstone_essence.png"), moonstone_essence)

    # ── Void Draught ──
    void_draught = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 220, 230),  # Bottle white
        2: (200, 200, 210),  # Slightly dark
        3: (80, 50, 130),    # Void purple liquid
        4: (120, 80, 180),   # Dark void
        5: (150, 100, 220),  # Bright void
    }
    rectangle(void_draught, (6, 4, 4, 3), PALETTE[1])  # Neck
    rectangle(void_draught, (5, 7, 6, 7), PALETTE[1])  # Body
    rectangle(void_draught, (5, 10, 6, 4), PALETTE[3])  # Liquid
    rectangle(void_draught, (5, 14, 6, 1), PALETTE[4])  # Bottom
    rectangle(void_draught, (6, 3, 4, 1), (80, 80, 90))  # Cap
    void_draught.set_at((6, 10), PALETTE[5])
    void_draught.set_at((8, 9), PALETTE[5])
    save_surface(os.path.join(output_dir, "void_draught.png"), void_draught)

    # ── Void Elixir ──
    void_elixir = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 220, 230),  # Bottle white
        2: (200, 200, 210),  # Slightly dark
        3: (100, 60, 160),   # Bright void
        4: (150, 100, 220),  # Very bright void
        5: (70, 40, 120),    # Dark void
    }
    rectangle(void_elixir, (6, 4, 4, 3), PALETTE[1])  # Neck
    rectangle(void_elixir, (5, 7, 6, 7), PALETTE[1])  # Body
    rectangle(void_elixir, (5, 10, 6, 4), PALETTE[3])  # Liquid
    rectangle(void_elixir, (5, 14, 6, 1), PALETTE[5])  # Bottom
    rectangle(void_elixir, (6, 3, 4, 1), (80, 80, 90))  # Cap
    void_elixir.set_at((6, 10), PALETTE[4])
    void_elixir.set_at((8, 9), PALETTE[4])
    void_elixir.set_at((7, 11), PALETTE[4])
    save_surface(os.path.join(output_dir, "void_elixir.png"), void_elixir)

    # ── Cactus Flesh ──
    cactus_flesh = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (80, 140, 80),    # Green flesh
        2: (60, 120, 60),    # Dark green
        3: (100, 160, 100),  # Light green
    }
    # Cactus slice
    rectangle(cactus_flesh, (4, 5, 8, 7), PALETTE[1])
    rectangle(cactus_flesh, (4, 5, 8, 1), PALETTE[3])
    rectangle(cactus_flesh, (4, 10, 8, 1), PALETTE[2])
    # Inner texture
    cactus_flesh.set_at((6, 7), PALETTE[3])
    cactus_flesh.set_at((8, 8), PALETTE[3])
    cactus_flesh.set_at((10, 9), PALETTE[3])
    save_surface(os.path.join(output_dir, "cactus_flesh.png"), cactus_flesh)

    # ── Ground Moonstone ──
    ground_moonstone = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (160, 170, 185),  # Pale grey-blue
        2: (130, 140, 155),  # Dark
        3: (180, 200, 230),  # Moonstone
        4: (210, 225, 255),  # Bright
    }
    circle(ground_moonstone, (8, 9), 5, PALETTE[1])
    circle(ground_moonstone, (6, 8), 3, PALETTE[2])
    circle(ground_moonstone, (10, 8), 3, PALETTE[3])
    ground_moonstone.set_at((8, 7), PALETTE[4])
    ground_moonstone.set_at((7, 10), PALETTE[4])
    save_surface(os.path.join(output_dir, "ground_moonstone.png"), ground_moonstone)

    # ── Ore Ghost Iron ──
    ore_ghost_iron = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (130, 135, 140),  # Pale grey rock
        2: (100, 105, 110),  # Dark shadow
        3: (180, 185, 200),  # Ghost iron veins
        4: (210, 215, 230),  # Bright
    }
    circle(ore_ghost_iron, (8, 9), 5, PALETTE[1])
    circle(ore_ghost_iron, (6, 8), 3, PALETTE[2])
    circle(ore_ghost_iron, (10, 8), 3, PALETTE[3])
    ore_ghost_iron.set_at((8, 7), PALETTE[4])
    ore_ghost_iron.set_at((7, 10), PALETTE[4])
    save_surface(os.path.join(output_dir, "ore_ghost_iron.png"), ore_ghost_iron)

    # ── Ore Mithril ──
    ore_mithril = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (100, 110, 120),  # Grey rock
        2: (80, 90, 100),    # Dark shadow
        3: (100, 160, 220),  # Mithril veins
        4: (140, 190, 255),  # Bright
    }
    circle(ore_mithril, (8, 9), 5, PALETTE[1])
    circle(ore_mithril, (6, 8), 3, PALETTE[2])
    circle(ore_mithril, (10, 8), 3, PALETTE[3])
    ore_mithril.set_at((8, 7), PALETTE[4])
    ore_mithril.set_at((9, 10), PALETTE[4])
    save_surface(os.path.join(output_dir, "ore_mithril.png"), ore_mithril)

    # ── Star Metal (item) ──
    star_metal_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 180, 60),   # Star gold
        2: (255, 210, 80),   # Bright
        3: (190, 150, 40),   # Dark
    }
    polygon(star_metal_item, [(8, 3), (12, 7), (11, 13), (8, 15), (5, 13), (4, 7)], PALETTE[1])
    polygon(star_metal_item, [(8, 5), (10, 8), (9, 12), (8, 13), (7, 12), (6, 8)], PALETTE[2])
    star_metal_item.set_at((8, 6), PALETTE[2])
    save_surface(os.path.join(output_dir, "star_metal.png"), star_metal_item)

    # ── Phoenix Feather (item) ──
    phoenix_feather_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (220, 80, 20),    # Fire orange
        2: (200, 60, 10),    # Dark fire
        3: (255, 160, 30),   # Bright flame
        4: (255, 200, 60),   # Golden
    }
    for fy in range(3, 14):
        width = 1 + ((fy * 3) % 2)
        cx = 8 + ((fy * 2) % 3) - 1
        for fx in range(cx - width, cx + width + 1):
            if 0 <= fx < 16:
                phoenix_feather_item.set_at((fx, fy), PALETTE[1])
    rectangle(phoenix_feather_item, (8, 2, 1, 13), PALETTE[2])
    phoenix_feather_item.set_at((7, 4), PALETTE[3])
    phoenix_feather_item.set_at((9, 5), PALETTE[4])
    phoenix_feather_item.set_at((7, 7), PALETTE[3])
    phoenix_feather_item.set_at((9, 9), PALETTE[4])
    phoenix_feather_item.set_at((7, 11), PALETTE[3])
    phoenix_feather_item.set_at((8, 3), PALETTE[4])
    save_surface(os.path.join(output_dir, "phoenix_feather.png"), phoenix_feather_item)

    # ── Fat Animal (food) ──
    fat_animal = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (180, 100, 60),   # Brown meat
        2: (150, 80, 45),    # Dark brown
        3: (200, 120, 70),   # Light brown
    }
    rectangle(fat_animal, (4, 7, 8, 5), PALETTE[1])
    rectangle(fat_animal, (4, 9, 8, 2), PALETTE[2])
    rectangle(fat_animal, (4, 7, 8, 1), PALETTE[3])
    fat_animal.set_at((6, 8), PALETTE[3])
    fat_animal.set_at((10, 10), PALETTE[3])
    save_surface(os.path.join(output_dir, "fat_animal.png"), fat_animal)

    # ── Chert ──
    chert = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (140, 130, 120),  # Tan-grey rock
        2: (110, 100, 90),   # Dark
        3: (170, 160, 150),  # Light
    }
    circle(chert, (8, 9), 5, PALETTE[1])
    circle(chert, (6, 8), 3, PALETTE[2])
    circle(chert, (10, 8), 3, PALETTE[3])
    chert.set_at((8, 7), PALETTE[3])
    chert.set_at((11, 9), PALETTE[2])
    save_surface(os.path.join(output_dir, "chert.png"), chert)

    # ── Stone (item) ──
    stone_item = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    PALETTE = {
        1: (130, 130, 140),  # Medium grey
        2: (100, 100, 110),  # Dark
        3: (160, 160, 170),  # Light
    }
    circle(stone_item, (8, 9), 5, PALETTE[1])
    circle(stone_item, (6, 8), 3, PALETTE[2])
    circle(stone_item, (10, 9), 3, PALETTE[3])
    stone_item.set_at((8, 7), PALETTE[3])
    stone_item.set_at((11, 8), PALETTE[2])
    save_surface(os.path.join(output_dir, "stone.png"), stone_item)

    print("  Generated 40+ tier 3/4 item sprites")


# ── Tier 3/4 Structure Sprites ───────────────────────────────────────

def generate_tier3_structure_sprites() -> None:
    """Generate tier 3/4 structure sprites."""
    print("\n=== Generating Tier 3/4 Structure Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "structure")

    structures = {
        "crafting_station": {
            "colors": [(140, 120, 80), (120, 100, 60), (160, 140, 100), (100, 80, 50)],
            "desc": "crafting station with tools",
        },
        "forge": {
            "colors": [(100, 100, 110), (80, 80, 90), (120, 120, 130), (255, 120, 30)],
            "desc": "forge with fire and anvil",
        },
        "anvil": {
            "colors": [(80, 80, 90), (70, 70, 80), (100, 100, 110), (130, 130, 140)],
            "desc": "iron anvil",
        },
        "arcane_table": {
            "colors": [(100, 80, 140), (80, 60, 120), (140, 110, 180), (180, 140, 220)],
            "desc": "arcane table with glowing runes",
        },
        "loom": {
            "colors": [(140, 120, 80), (120, 100, 60), (160, 140, 100), (180, 170, 140)],
            "desc": "wooden loom",
        },
        "crystal_table": {
            "colors": [(140, 100, 200), (120, 80, 180), (170, 130, 230), (200, 160, 255)],
            "desc": "crystal table with glowing gems",
        },
        "alchemy_table": {
            "colors": [(120, 100, 80), (100, 80, 60), (140, 120, 100), (180, 160, 120)],
            "desc": "alchemy table with potions",
        },
    }

    for name, info in structures.items():
        sprite = pygame.Surface((STRUCTURE_SIZE, STRUCTURE_SIZE), pygame.SRCALPHA)
        colors = info["colors"]
        c1 = colors[0]
        c2 = colors[1] if len(colors) > 1 else c1
        c3 = colors[2] if len(colors) > 2 else c1
        extras = colors[3:] if len(colors) > 3 else []

        # Draw base (table/workbench shape)
        rectangle(sprite, (2, 8, 12, 7), c1)
        rectangle(sprite, (2, 8, 12, 1), c3)  # Top highlight
        rectangle(sprite, (2, 14, 12, 1), c2)  # Bottom shadow
        rectangle(sprite, (2, 8, 1, 7), c3)   # Left edge
        rectangle(sprite, (13, 8, 1, 7), c2)  # Right edge

        if name == "crafting_station":
            # Tools on table
            rectangle(sprite, (4, 5, 1, 4), c2)    # Hammer handle
            rectangle(sprite, (3, 4, 3, 1), c3)    # Hammer head
            rectangle(sprite, (10, 5, 1, 4), c2)   # Wrench handle
            rectangle(sprite, (9, 4, 3, 1), c3)    # Wrench head
        elif name == "forge":
            # Fire box
            rectangle(sprite, (5, 10, 6, 4), c2)
            # Flames
            circle(sprite, (8, 9), 2, extras[0] if extras else (255, 100, 20))
            circle(sprite, (8, 8), 1, extras[1] if len(extras) > 1 else (255, 200, 50))
            # Anvil on right
            rectangle(sprite, (11, 9, 3, 2), c3)
            rectangle(sprite, (11, 7, 3, 1), c3)
        elif name == "anvil":
            # Anvil top
            rectangle(sprite, (4, 7, 8, 2), c3)
            # Anvil body
            rectangle(sprite, (5, 9, 6, 4), c2)
            # Anvil base
            rectangle(sprite, (4, 13, 8, 2), c1)
            # Highlight
            sprite.set_at((6, 7), c3)
            sprite.set_at((10, 7), c3)
        elif name == "arcane_table":
            # Glowing runes on table surface
            arcane_color = extras[0] if extras else (180, 140, 220)
            sprite.set_at((5, 9), arcane_color)
            sprite.set_at((7, 9), arcane_color)
            sprite.set_at((9, 9), arcane_color)
            sprite.set_at((11, 9), arcane_color)
            sprite.set_at((6, 11), arcane_color)
            sprite.set_at((10, 11), arcane_color)
            sprite.set_at((8, 10), arcane_color)
            # Book/parchment
            rectangle(sprite, (6, 5, 4, 3), c2)
            rectangle(sprite, (6, 5, 4, 1), c3)
        elif name == "loom":
            # Vertical frame
            rectangle(sprite, (4, 3, 1, 10), c2)
            rectangle(sprite, (11, 3, 1, 10), c2)
            # Horizontal beams
            rectangle(sprite, (4, 3, 8, 1), c3)
            rectangle(sprite, (4, 12, 8, 1), c2)
            # Thread (vertical lines)
            for tx in [6, 8, 10]:
                rectangle(sprite, (tx, 4, 1, 8), c1)
        elif name == "crystal_table":
            # Table surface
            rectangle(sprite, (3, 7, 10, 2), c2)
            # Glowing crystals
            crystal_color = extras[0] if extras else (200, 160, 255)
            polygon(sprite, [(5, 5), (6, 7), (5, 8), (4, 7)], crystal_color)
            polygon(sprite, [(8, 4), (9, 6), (8, 8), (7, 6)], crystal_color)
            polygon(sprite, [(11, 5), (12, 7), (11, 8), (10, 7)], crystal_color)
            # Sparkles
            sprite.set_at((5, 5), crystal_color)
            sprite.set_at((8, 4), crystal_color)
            sprite.set_at((11, 5), crystal_color)
        elif name == "alchemy_table":
            # Potion bottles
            rectangle(sprite, (4, 6, 2, 4), (220, 220, 230))
            rectangle(sprite, (4, 8, 2, 2), c1)
            rectangle(sprite, (10, 6, 2, 4), (220, 220, 230))
            rectangle(sprite, (10, 8, 2, 2), c2)
            # Scroll/parchment
            rectangle(sprite, (6, 9, 4, 3), c3)
            rectangle(sprite, (6, 9, 4, 1), extras[0] if extras else (200, 180, 140))

        save_surface(os.path.join(output_dir, f"{name}.png"), sprite)

    print("  Generated 7 tier 3/4 structure sprites")




# ── Depleted & Growth-Stage Sprite Generators ────────────────────────

# ── Per-tree-type palettes for depleted/sapling/young ─────────────────

def _oak_depleted_palette():
    return {1: (110, 75, 35), 2: (80, 55, 25), 3: (145, 100, 50), 4: (50, 35, 15), 5: (95, 65, 30)}

def _pine_depleted_palette():
    return {1: (75, 50, 25), 2: (50, 35, 18), 3: (105, 75, 35), 4: (35, 25, 12), 5: (60, 42, 20)}

def _maple_depleted_palette():
    return {1: (85, 60, 30), 2: (60, 42, 22), 3: (115, 80, 40), 4: (40, 28, 14), 5: (70, 50, 25)}

def _spruce_depleted_palette():
    return {1: (65, 45, 22), 2: (42, 30, 15), 3: (92, 65, 30), 4: (28, 20, 10), 5: (52, 38, 18)}

def _willow_depleted_palette():
    return {1: (85, 72, 40), 2: (58, 48, 28), 3: (115, 95, 55), 4: (38, 30, 18), 5: (70, 58, 32)}

def _birch_depleted_palette():
    return {1: (195, 190, 175), 2: (155, 150, 135), 3: (220, 215, 200), 4: (120, 115, 100), 5: (175, 170, 155)}

def _elder_wood_depleted_palette():
    return {1: (65, 48, 30), 2: (45, 33, 20), 3: (90, 68, 40), 4: (30, 22, 12), 5: (55, 40, 25)}

_DEPLETED_PALETTES = {
    "oak": _oak_depleted_palette,
    "pine": _pine_depleted_palette,
    "maple": _maple_depleted_palette,
    "spruce": _spruce_depleted_palette,
    "willow": _willow_depleted_palette,
    "birch": _birch_depleted_palette,
    "elder_wood": _elder_wood_depleted_palette,
}

def _tree_depleted_palette():
    return {1: (100, 70, 35), 2: (70, 50, 22), 3: (130, 90, 45), 4: (45, 32, 15), 5: (85, 60, 28)}

def _tree_sapling_palette():
    return {1: (100, 70, 35), 2: (35, 75, 30), 3: (50, 110, 45), 4: (70, 135, 55), 5: (90, 155, 65)}

def _tree_young_palette():
    return {1: (110, 75, 38), 2: (32, 85, 32), 3: (48, 125, 48), 4: (68, 150, 62), 5: (88, 170, 75)}

# ── Depleted & Growth-Stage Sprite Generators ────────────────────────


def generate_tree_depleted_sprites() -> None:
    """Generate depleted (stump) sprites — distinct per tree type."""
    print("\n=== Generating Tree Depleted Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "trees")

    trees = ["oak", "pine", "maple", "spruce", "willow", "birch", "elder_wood"]

    for name in trees:
        surf = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
        p = _DEPLETED_PALETTES[name]()

        if name == "oak":
            # Wide, thick stump with ring lines — matches broad oak trunk
            rectangle(surf, (11, 20, 10, 12), p[1])
            rectangle(surf, (12, 21, 8, 10), p[5])
            rectangle(surf, (12, 20, 8, 2), p[3])  # cut surface
            rectangle(surf, (13, 23, 6, 1), p[2])  # ring line
            rectangle(surf, (13, 26, 6, 1), p[2])  # ring line
            rectangle(surf, (9, 29, 3, 2), p[1])   # root flare left
            rectangle(surf, (20, 29, 3, 2), p[1])  # root flare right
            rectangle(surf, (14, 27, 4, 3), p[4])  # hollow
            # Dead branch stubs
            rectangle(surf, (12, 18, 1, 3), p[2])
            rectangle(surf, (17, 18, 1, 2), p[2])
            surf.set_at((13, 19), p[3])
            surf.set_at((18, 19), p[3])

        elif name == "pine":
            # Narrower stump, pointed — matches conical pine shape
            rectangle(surf, (13, 20, 6, 12), p[1])
            rectangle(surf, (14, 21, 4, 10), p[5])
            rectangle(surf, (14, 20, 4, 2), p[3])
            rectangle(surf, (10, 28, 2, 3), p[2])   # root left
            rectangle(surf, (20, 28, 2, 3), p[2])   # root right
            rectangle(surf, (15, 26, 2, 3), p[4])
            # One dead branch
            rectangle(surf, (12, 18, 1, 3), p[2])
            rectangle(surf, (11, 17, 1, 1), p[2])
            surf.set_at((15, 19), p[3])

        elif name == "maple":
            # Wide stump with reddish-brown tones — matches autumn maple
            rectangle(surf, (11, 20, 10, 12), p[1])
            rectangle(surf, (12, 21, 8, 10), p[5])
            rectangle(surf, (12, 20, 8, 2), p[3])
            rectangle(surf, (13, 24, 6, 1), p[2])
            rectangle(surf, (9, 29, 3, 2), p[1])
            rectangle(surf, (20, 29, 3, 2), p[1])
            rectangle(surf, (14, 27, 4, 3), p[4])
            rectangle(surf, (13, 18, 1, 3), p[2])
            rectangle(surf, (18, 18, 1, 2), p[2])
            surf.set_at((14, 19), p[3])
            surf.set_at((17, 19), p[3])

        elif name == "spruce":
            # Very narrow, tall stump — matches tall thin spruce
            rectangle(surf, (14, 20, 4, 12), p[1])
            rectangle(surf, (15, 21, 2, 10), p[5])
            rectangle(surf, (15, 20, 2, 2), p[3])
            rectangle(surf, (12, 28, 2, 3), p[2])
            rectangle(surf, (20, 28, 2, 3), p[2])
            rectangle(surf, (15, 26, 2, 3), p[4])
            rectangle(surf, (13, 18, 1, 3), p[2])
            surf.set_at((16, 19), p[3])

        elif name == "willow":
            # Gnarlly stump with drooping tendril stubs — matches willow
            rectangle(surf, (11, 20, 10, 12), p[1])
            rectangle(surf, (12, 21, 8, 10), p[5])
            rectangle(surf, (12, 20, 8, 2), p[3])
            rectangle(surf, (9, 29, 4, 2), p[1])
            rectangle(surf, (19, 29, 4, 2), p[1])
            rectangle(surf, (14, 27, 4, 3), p[4])
            # Dead drooping branch stubs
            rectangle(surf, (10, 18, 1, 4), p[2])
            rectangle(surf, (13, 17, 1, 4), p[2])
            rectangle(surf, (19, 17, 1, 4), p[2])
            rectangle(surf, (22, 18, 1, 3), p[2])
            for ty in [21, 22]:
                surf.set_at((10, ty), (70, 90, 50))
                surf.set_at((22, ty), (70, 90, 50))
            surf.set_at((15, 19), p[3])

        elif name == "birch":
            # White-grey stump with dark horizontal marks — matches birch bark
            rectangle(surf, (11, 20, 10, 12), p[1])
            rectangle(surf, (12, 21, 8, 10), p[5])
            rectangle(surf, (12, 20, 8, 2), p[3])
            for my in [23, 25, 27]:
                rectangle(surf, (12, my, 3, 1), p[2])
            rectangle(surf, (9, 29, 3, 2), p[2])
            rectangle(surf, (20, 29, 3, 2), p[2])
            rectangle(surf, (14, 27, 4, 3), p[4])
            rectangle(surf, (13, 18, 1, 3), p[2])
            rectangle(surf, (18, 18, 1, 2), p[2])
            surf.set_at((14, 19), p[3])

        elif name == "elder_wood":
            # Massive ancient stump, very thick — matches elder wood
            rectangle(surf, (10, 20, 12, 12), p[1])
            rectangle(surf, (11, 21, 10, 10), p[5])
            rectangle(surf, (11, 20, 10, 2), p[3])
            rectangle(surf, (12, 24, 8, 1), p[2])
            rectangle(surf, (12, 27, 8, 1), p[2])
            rectangle(surf, (8, 29, 4, 2), p[1])
            rectangle(surf, (20, 29, 4, 2), p[1])
            rectangle(surf, (14, 27, 4, 3), p[4])
            rectangle(surf, (11, 18, 1, 3), p[2])
            rectangle(surf, (20, 18, 1, 3), p[2])
            surf.set_at((13, 19), p[3])
            surf.set_at((19, 19), p[3])

        save_surface(os.path.join(output_dir, f"{name}_depleted.png"), surf)

    print("  Generated depleted sprites for 7 trees")

    # Berry bush: 2-stage regrowth (depleted → young → mature)
    bush_depleted = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    bp = {
        1: (80, 60, 30),     # Bare wood (twigs)
        2: (50, 40, 20),     # Dark wood (shadow)
        3: (100, 80, 50),    # Light wood (highlight)
    }
    # Empty bush frame (twigs sticking out)
    rectangle(bush_depleted, (4, 8, 8, 4), bp[1])
    rectangle(bush_depleted, (5, 7, 1, 6), bp[1])
    rectangle(bush_depleted, (11, 7, 1, 6), bp[1])
    rectangle(bush_depleted, (6, 9, 3, 1), bp[2])
    rectangle(bush_depleted, (9, 9, 3, 1), bp[2])
    bush_depleted.set_at((6, 8), bp[3])
    save_surface(os.path.join(output_dir, "berry_bush_depleted.png"), bush_depleted)

    # Berry bush young: small regrowing bush with leaf cluster
    bush_young = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    byp = {
        1: (34, 100, 34),    # Green (bush)
        2: (50, 130, 50),    # Light green (highlights)
        3: (220, 50, 50),    # Red (berries)
        4: (20, 70, 20),     # Dark green (shadow)
    }
    circle(bush_young, (8, 10), 6, byp[4])
    circle(bush_young, (8, 10), 5, byp[1])
    circle(bush_young, (6, 9), 3, byp[2])
    circle(bush_young, (10, 9), 3, byp[2])
    bush_young.set_at((7, 9), byp[3])
    bush_young.set_at((9, 10), byp[3])
    save_surface(os.path.join(output_dir, "berry_bush_young.png"), bush_young)


def _oak_sapling_palette():
    return {1: (120, 80, 35), 2: (30, 85, 30), 3: (45, 125, 45), 4: (65, 150, 60), 5: (85, 170, 75)}

def _pine_sapling_palette():
    return {1: (80, 55, 25), 2: (25, 55, 25), 3: (35, 75, 35), 4: (45, 95, 45), 5: (65, 120, 55)}

def _maple_sapling_palette():
    return {1: (100, 70, 35), 2: (140, 45, 35), 3: (180, 70, 35), 4: (200, 110, 45), 5: (220, 145, 55)}

def _spruce_sapling_palette():
    return {1: (70, 48, 22), 2: (20, 50, 20), 3: (30, 70, 30), 4: (40, 90, 40), 5: (60, 115, 50)}

def _willow_sapling_palette():
    return {1: (95, 80, 45), 2: (40, 65, 30), 3: (50, 85, 35), 4: (65, 105, 45), 5: (80, 125, 50)}

def _birch_sapling_palette():
    return {1: (210, 205, 190), 2: (55, 95, 35), 3: (75, 125, 45), 4: (95, 155, 55), 5: (125, 185, 75)}

def _elder_wood_sapling_palette():
    return {1: (75, 55, 30), 2: (35, 70, 40), 3: (45, 90, 50), 4: (60, 120, 60), 5: (80, 145, 75)}

_SAPLING_PALETTES = {
    "oak": _oak_sapling_palette,
    "pine": _pine_sapling_palette,
    "maple": _maple_sapling_palette,
    "spruce": _spruce_sapling_palette,
    "willow": _willow_sapling_palette,
    "birch": _birch_sapling_palette,
    "elder_wood": _elder_wood_sapling_palette,
}


def _oak_young_palette():
    return {1: (130, 85, 40), 2: (30, 90, 30), 3: (45, 130, 45), 4: (65, 155, 65), 5: (85, 175, 80)}

def _pine_young_palette():
    return {1: (85, 58, 28), 2: (28, 58, 28), 3: (38, 78, 38), 4: (48, 100, 48), 5: (68, 125, 58)}

def _maple_young_palette():
    return {1: (105, 72, 38), 2: (150, 50, 40), 3: (190, 80, 40), 4: (210, 120, 50), 5: (230, 155, 60)}

def _spruce_young_palette():
    return {1: (75, 52, 25), 2: (22, 52, 22), 3: (32, 72, 32), 4: (42, 92, 42), 5: (62, 118, 52)}

def _willow_young_palette():
    return {1: (98, 82, 48), 2: (42, 68, 32), 3: (52, 88, 38), 4: (68, 110, 48), 5: (82, 130, 55)}

def _birch_young_palette():
    return {1: (215, 210, 195), 2: (58, 98, 38), 3: (78, 128, 48), 4: (98, 158, 58), 5: (128, 188, 78)}

def _elder_wood_young_palette():
    return {1: (80, 58, 32), 2: (38, 72, 42), 3: (48, 95, 52), 4: (62, 125, 62), 5: (82, 150, 78)}

_YOUNG_PALETTES = {
    "oak": _oak_young_palette,
    "pine": _pine_young_palette,
    "maple": _maple_young_palette,
    "spruce": _spruce_young_palette,
    "willow": _willow_young_palette,
    "birch": _birch_young_palette,
    "elder_wood": _elder_wood_young_palette,
}


def generate_tree_growth_sprites() -> None:
    """Generate sapling and young regrowth sprites — distinct per tree type."""
    print("\n=== Generating Tree Growth-Stage Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "trees")

    trees = ["oak", "pine", "maple", "spruce", "willow", "birch", "elder_wood"]

    for name in trees:
        # ── Sapling ──
        sap = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
        sp = _SAPLING_PALETTES[name]()

        if name == "oak":
            # Sturdy short trunk + rounded young canopy
            rectangle(sap, (14, 16, 4, 12), sp[1])
            rectangle(sap, (15, 17, 2, 10), sp[4])
            circle(sap, (16, 11), 7, sp[2])
            circle(sap, (12, 10), 5, sp[3])
            circle(sap, (20, 10), 5, sp[3])
            circle(sap, (16, 8), 4, sp[4])
            sap.set_at((16, 6), sp[5])
            sap.set_at((15, 7), sp[5])
            sap.set_at((17, 7), sp[5])

        elif name == "pine":
            # Conical sapling — tiered needle clusters
            rectangle(sap, (15, 16, 2, 12), sp[1])
            circle(sap, (16, 14), 6, sp[3])
            circle(sap, (16, 11), 5, sp[4])
            circle(sap, (16, 8), 4, sp[5])
            sap.set_at((16, 6), sp[5])
            sap.set_at((15, 7), sp[4])
            sap.set_at((17, 7), sp[4])

        elif name == "maple":
            # Broad rounded sapling — autumn colors
            rectangle(sap, (14, 16, 4, 12), sp[1])
            rectangle(sap, (15, 17, 2, 10), sp[4])
            circle(sap, (16, 11), 7, sp[2])
            circle(sap, (12, 10), 5, sp[3])
            circle(sap, (20, 10), 5, sp[3])
            circle(sap, (16, 8), 4, sp[4])
            sap.set_at((14, 7), sp[5])
            sap.set_at((18, 7), sp[5])
            sap.set_at((16, 6), sp[5])

        elif name == "spruce":
            # Very narrow tall sapling
            rectangle(sap, (15, 16, 2, 12), sp[1])
            circle(sap, (16, 15), 5, sp[3])
            circle(sap, (16, 12), 4, sp[4])
            circle(sap, (16, 9), 3, sp[5])
            sap.set_at((16, 7), sp[5])
            sap.set_at((16, 6), sp[5])

        elif name == "willow":
            # Drooping sapling — wide canopy with hanging tendrils
            rectangle(sap, (14, 16, 4, 12), sp[1])
            rectangle(sap, (13, 16, 1, 8), sp[1])
            circle(sap, (16, 11), 7, sp[2])
            circle(sap, (12, 10), 5, sp[3])
            circle(sap, (20, 10), 5, sp[3])
            circle(sap, (16, 8), 4, sp[4])
            # Tiny drooping tendrils
            for tx in [8, 10, 22, 24]:
                for ty in range(17, min(22, 32)):
                    sap.set_at((tx, ty), (60, 80, 45))
            sap.set_at((16, 6), sp[5])

        elif name == "birch":
            # White-barked sapling with light canopy
            rectangle(sap, (14, 16, 4, 12), sp[1])
            rectangle(sap, (15, 17, 2, 10), sp[4])
            for my in [19, 21, 23]:
                rectangle(sap, (14, my, 2, 1), sp[2])
            circle(sap, (16, 11), 7, sp[2])
            circle(sap, (12, 10), 5, sp[3])
            circle(sap, (20, 10), 5, sp[3])
            circle(sap, (16, 8), 4, sp[4])
            sap.set_at((16, 6), sp[5])
            sap.set_at((15, 7), sp[5])
            sap.set_at((17, 7), sp[5])

        elif name == "elder_wood":
            # Thick ancient sapling — massive trunk, wide canopy
            rectangle(sap, (13, 16, 6, 12), sp[1])
            rectangle(sap, (14, 17, 4, 10), sp[4])
            circle(sap, (16, 11), 8, sp[2])
            circle(sap, (11, 10), 5, sp[3])
            circle(sap, (21, 10), 5, sp[3])
            circle(sap, (16, 8), 5, sp[4])
            sap.set_at((16, 6), sp[5])
            sap.set_at((15, 7), sp[5])
            sap.set_at((17, 7), sp[5])

        save_surface(os.path.join(output_dir, f"{name}_sapling.png"), sap)

        # ── Young ──
        young = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
        yp = _YOUNG_PALETTES[name]()

        if name == "oak":
            rectangle(young, (13, 18, 6, 10), yp[1])
            rectangle(young, (14, 19, 4, 8), yp[4])
            circle(young, (16, 11), 8, yp[2])
            circle(young, (11, 10), 5, yp[3])
            circle(young, (21, 10), 5, yp[3])
            circle(young, (16, 9), 4, yp[4])
            circle(young, (16, 8), 3, yp[5])
            young.set_at((15, 7), yp[5])
            young.set_at((17, 7), yp[5])

        elif name == "pine":
            rectangle(young, (14, 18, 4, 10), yp[1])
            rectangle(young, (15, 19, 2, 8), yp[4])
            circle(young, (16, 13), 7, yp[3])
            circle(young, (16, 10), 6, yp[4])
            circle(young, (16, 7), 4, yp[5])
            young.set_at((16, 5), yp[5])
            young.set_at((15, 6), yp[4])
            young.set_at((17, 6), yp[4])

        elif name == "maple":
            rectangle(young, (13, 18, 6, 10), yp[1])
            rectangle(young, (14, 19, 4, 8), yp[4])
            circle(young, (16, 11), 8, yp[2])
            circle(young, (11, 10), 5, yp[3])
            circle(young, (21, 10), 5, yp[3])
            circle(young, (16, 9), 4, yp[4])
            circle(young, (16, 8), 3, yp[5])
            young.set_at((14, 7), yp[5])
            young.set_at((18, 7), yp[5])
            young.set_at((16, 6), yp[5])

        elif name == "spruce":
            rectangle(young, (15, 18, 2, 10), yp[1])
            rectangle(young, (15, 19, 1, 8), yp[4])
            circle(young, (16, 14), 6, yp[3])
            circle(young, (16, 11), 5, yp[4])
            circle(young, (16, 8), 3, yp[5])
            young.set_at((16, 6), yp[5])
            young.set_at((16, 5), yp[5])

        elif name == "willow":
            rectangle(young, (13, 18, 6, 10), yp[1])
            rectangle(young, (12, 18, 1, 8), yp[1])
            circle(young, (16, 11), 8, yp[2])
            circle(young, (11, 10), 5, yp[3])
            circle(young, (21, 10), 5, yp[3])
            circle(young, (16, 9), 4, yp[4])
            # Drooping tendrils
            for tx in [7, 9, 23, 25]:
                for ty in range(18, min(24, 32)):
                    young.set_at((tx, ty), (60, 80, 45))
            young.set_at((16, 7), yp[5])

        elif name == "birch":
            rectangle(young, (13, 18, 6, 10), yp[1])
            rectangle(young, (14, 19, 4, 8), yp[4])
            for my in [20, 22, 24]:
                rectangle(young, (13, my, 3, 1), yp[2])
            circle(young, (16, 11), 8, yp[2])
            circle(young, (11, 10), 5, yp[3])
            circle(young, (21, 10), 5, yp[3])
            circle(young, (16, 9), 4, yp[4])
            circle(young, (16, 8), 3, yp[5])
            young.set_at((15, 7), yp[5])
            young.set_at((17, 7), yp[5])

        elif name == "elder_wood":
            rectangle(young, (12, 18, 8, 10), yp[1])
            rectangle(young, (13, 19, 6, 8), yp[4])
            circle(young, (16, 11), 9, yp[2])
            circle(young, (10, 10), 5, yp[3])
            circle(young, (22, 10), 5, yp[3])
            circle(young, (16, 9), 5, yp[4])
            circle(young, (16, 8), 3, yp[5])
            young.set_at((15, 7), yp[5])
            young.set_at((17, 7), yp[5])

        save_surface(os.path.join(output_dir, f"{name}_young.png"), young)

    print("  Generated sapling + young sprites for 7 trees")


def generate_rock_depleted_sprites() -> None:
    """Generate depleted rock/ore sprites — distinct weathered rubble per type."""
    print("\n=== Generating Rock Depleted Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "rocks")

    # ── Tier 1 depleted ──────────────────────────────────────────────────

    # Iron depleted — rusted, crumbled metallic rubble
    iron_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (100, 75, 55), 2: (75, 55, 40), 3: (130, 100, 75), 4: (155, 120, 90)}
    polygon(iron_d, [(3, 11), (5, 6), (9, 5), (12, 8), (13, 12), (11, 14), (6, 15), (4, 13)], p[1])
    polygon(iron_d, [(5, 11), (7, 7), (9, 6), (11, 9), (9, 13), (6, 14)], p[2])
    iron_d.set_at((6, 8), p[3])
    iron_d.set_at((9, 9), p[3])
    iron_d.set_at((7, 12), p[4])
    save_surface(os.path.join(output_dir, "iron_depleted.png"), iron_d)

    # Copper depleted — oxidized greenish-copper rubble
    copper_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (90, 80, 60), 2: (65, 58, 42), 3: (120, 110, 80), 4: (80, 100, 70)}
    circle(copper_d, (8, 10), 5, p[1])
    circle(copper_d, (6, 9), 3, p[2])
    circle(copper_d, (10, 9), 3, p[3])
    copper_d.set_at((7, 8), p[4])
    copper_d.set_at((9, 11), p[4])
    copper_d.set_at((8, 7), p[3])
    save_surface(os.path.join(output_dir, "copper_depleted.png"), copper_d)

    # Gold depleted — panned-out gravel with faint gold flecks
    gold_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (95, 88, 78), 2: (70, 63, 55), 3: (135, 125, 110), 4: (195, 165, 45)}
    polygon(gold_d, [(3, 11), (5, 6), (10, 5), (13, 8), (14, 12), (12, 14), (6, 15), (4, 13)], p[1])
    polygon(gold_d, [(5, 11), (7, 7), (10, 6), (12, 9), (10, 13), (6, 14)], p[2])
    gold_d.set_at((7, 9), p[3])
    gold_d.set_at((10, 10), p[3])
    gold_d.set_at((8, 12), p[4])  # faint gold fleck
    save_surface(os.path.join(output_dir, "gold_depleted.png"), gold_d)

    # Stone depleted — cracked grey cobble
    stone_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (110, 110, 120), 2: (80, 80, 90), 3: (140, 140, 150)}
    circle(stone_d, (8, 10), 5, p[1])
    circle(stone_d, (6, 9), 3, p[2])
    circle(stone_d, (10, 9), 3, p[3])
    stone_d.set_at((7, 8), p[2])
    stone_d.set_at((9, 11), p[2])
    stone_d.set_at((8, 7), p[3])
    save_surface(os.path.join(output_dir, "stone_depleted.png"), stone_d)

    # Gem depleted — cracked matrix with dull crystal fragment
    gem_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (85, 80, 90), 2: (60, 55, 65), 3: (120, 115, 125), 4: (160, 75, 180)}
    circle(gem_d, (8, 11), 5, p[1])
    circle(gem_d, (6, 10), 3, p[2])
    polygon(gem_d, [(7, 7), (9, 5), (10, 8), (7, 9)], p[4])  # dull crystal shard
    gem_d.set_at((8, 8), p[3])
    save_surface(os.path.join(output_dir, "gem_depleted.png"), gem_d)

    # Rare depleted — dark rock with faded purple crystal remnants
    rare_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (60, 50, 70), 2: (40, 30, 50), 3: (90, 75, 100), 4: (140, 70, 170)}
    polygon(rare_d, [(3, 11), (5, 6), (10, 5), (13, 8), (14, 12), (12, 14), (6, 15), (4, 13)], p[1])
    polygon(rare_d, [(5, 11), (7, 7), (10, 6), (12, 9), (10, 13), (6, 14)], p[2])
    rare_d.set_at((6, 7), p[4])
    rare_d.set_at((10, 7), p[4])
    rare_d.set_at((8, 10), p[3])
    save_surface(os.path.join(output_dir, "rare_depleted.png"), rare_d)

    # Tin depleted — dull blue-grey metallic scrap
    tin_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (95, 100, 110), 2: (70, 75, 85), 3: (130, 140, 155), 4: (155, 165, 180)}
    circle(tin_d, (8, 10), 5, p[1])
    circle(tin_d, (6, 9), 3, p[2])
    circle(tin_d, (10, 9), 3, p[3])
    tin_d.set_at((7, 8), p[4])
    tin_d.set_at((9, 11), p[3])
    save_surface(os.path.join(output_dir, "tin_depleted.png"), tin_d)

    # ── Tier 3/4 depleted ────────────────────────────────────────────────

    # Void crystal depleted — shattered dark crystal shards
    vc_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (45, 28, 68), 2: (30, 18, 48), 3: (80, 45, 120), 4: (120, 75, 175)}
    polygon(vc_d, [(4, 10), (6, 5), (9, 4), (11, 7), (12, 11), (10, 14), (6, 15), (4, 13)], p[1])
    polygon(vc_d, [(5, 10), (7, 6), (9, 5), (10, 8), (9, 13), (6, 14)], p[2])
    vc_d.set_at((7, 7), p[4])
    vc_d.set_at((9, 9), p[3])
    save_surface(os.path.join(output_dir, "void_crystal_depleted.png"), vc_d)

    # Obsidian depleted — shattered glass fragments
    obs_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (22, 20, 25), 2: (12, 10, 14), 3: (55, 50, 60), 4: (85, 80, 95)}
    polygon(obs_d, [(3, 10), (5, 5), (9, 4), (12, 7), (13, 11), (11, 14), (7, 15), (4, 13)], p[1])
    polygon(obs_d, [(5, 10), (7, 6), (9, 5), (11, 8), (10, 13), (6, 14)], p[2])
    obs_d.set_at((6, 6), p[3])
    obs_d.set_at((8, 8), p[4])
    obs_d.set_at((10, 10), p[3])
    save_surface(os.path.join(output_dir, "obsidian_depleted.png"), obs_d)

    # Mithril depleted — dull blue-grey ore scrap
    mith_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (85, 95, 108), 2: (65, 75, 88), 3: (115, 145, 195), 4: (125, 170, 225)}
    circle(mith_d, (8, 10), 5, p[1])
    circle(mith_d, (6, 9), 3, p[2])
    circle(mith_d, (10, 9), 3, p[3])
    mith_d.set_at((7, 8), p[4])
    mith_d.set_at((9, 11), p[3])
    save_surface(os.path.join(output_dir, "mithril_depleted.png"), mith_d)

    # Ghost iron depleted — faded spectral metal
    gi_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (110, 115, 125), 2: (80, 85, 95), 3: (150, 155, 170), 4: (180, 185, 200)}
    circle(gi_d, (8, 10), 5, p[1])
    circle(gi_d, (6, 9), 3, p[2])
    circle(gi_d, (10, 9), 3, p[3])
    gi_d.set_at((7, 8), p[4])
    gi_d.set_at((9, 11), p[3])
    save_surface(os.path.join(output_dir, "ghost_iron_depleted.png"), gi_d)

    # Star metal depleted — dim cosmic rock
    sm_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (90, 80, 65), 2: (65, 55, 40), 3: (175, 140, 40), 4: (215, 175, 60)}
    polygon(sm_d, [(3, 11), (5, 6), (10, 5), (13, 8), (14, 12), (12, 14), (6, 15), (4, 13)], p[1])
    polygon(sm_d, [(5, 11), (7, 7), (10, 6), (12, 9), (10, 13), (6, 14)], p[2])
    sm_d.set_at((8, 9), p[3])
    sm_d.set_at((7, 11), p[4])
    save_surface(os.path.join(output_dir, "star_metal_depleted.png"), sm_d)

    # Ancient rune depleted — cracked weathered tablet
    ar_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (70, 75, 82), 2: (50, 55, 62), 3: (95, 100, 110), 4: (60, 120, 90)}
    rectangle(ar_d, (4, 4, 8, 11), p[1])
    rectangle(ar_d, (5, 5, 6, 9), p[2])
    ar_d.set_at((6, 7), p[4])
    ar_d.set_at((8, 8), p[3])
    ar_d.set_at((10, 7), p[4])
    ar_d.set_at((7, 10), p[3])
    ar_d.set_at((9, 10), p[4])
    save_surface(os.path.join(output_dir, "ancient_rune_depleted.png"), ar_d)

    # Amber depleted — dull fossil resin
    am_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (140, 95, 30), 2: (110, 75, 20), 3: (180, 130, 40), 4: (210, 160, 55)}
    circle(am_d, (8, 10), 5, p[1])
    circle(am_d, (6, 9), 3, p[2])
    circle(am_d, (10, 9), 3, p[3])
    am_d.set_at((8, 8), p[4])
    am_d.set_at((7, 11), p[3])
    save_surface(os.path.join(output_dir, "amber_depleted.png"), am_d)

    # Moonstone depleted — cracked pale crystal
    ms_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (135, 145, 162), 2: (105, 115, 132), 3: (150, 170, 200), 4: (180, 195, 225)}
    polygon(ms_d, [(5, 6), (7, 3), (10, 3), (12, 6), (11, 11), (8, 14), (5, 12)], p[1])
    polygon(ms_d, [(6, 7), (8, 4), (10, 5), (11, 8), (9, 13), (6, 11)], p[2])
    ms_d.set_at((8, 6), p[4])
    ms_d.set_at((7, 8), p[3])
    save_surface(os.path.join(output_dir, "moonstone_depleted.png"), ms_d)

    # Celestial crystal depleted — shattered prismatic shards
    cc_d = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (60, 45, 90), 2: (40, 30, 65), 3: (100, 65, 150), 4: (145, 105, 200)}
    polygon(cc_d, [(5, 5), (7, 3), (10, 4), (11, 8), (10, 12), (8, 15), (5, 12), (4, 7)], p[1])
    polygon(cc_d, [(6, 6), (8, 4), (9, 6), (10, 9), (8, 14), (6, 11)], p[2])
    cc_d.set_at((7, 7), p[4])
    cc_d.set_at((9, 9), p[3])
    save_surface(os.path.join(output_dir, "celestial_crystal_depleted.png"), cc_d)

    print("  Generated depleted sprites for 16 rock/ore types")


def generate_world_depleted_sprites() -> None:
    """Generate depleted world resource sprites."""
    print("\n=== Generating World Depleted Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "world")

    # herb_depleted — bare stems
    herb = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (90, 70, 40), 2: (120, 95, 55), 3: (60, 45, 30)}
    rectangle(herb, (7, 11, 2, 4), p[1])
    rectangle(herb, (9, 12, 2, 3), p[1])
    rectangle(herb, (8, 12, 1, 2), p[2])
    save_surface(os.path.join(output_dir, "herb_depleted.png"), herb)

    # fiber_depleted — cut fibers (shorter)
    fiber = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (100, 90, 50), 2: (80, 70, 40), 3: (130, 120, 80)}
    rectangle(fiber, (7, 13, 1, 3), p[1])
    rectangle(fiber, (9, 13, 1, 3), p[1])
    rectangle(fiber, (8, 13, 1, 2), p[3])
    save_surface(os.path.join(output_dir, "fiber_depleted.png"), fiber)

    # grass_depleted — bare patch
    grass = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (120, 100, 60), 2: (150, 130, 80)}
    rectangle(grass, (5, 12, 1, 3), p[1])
    rectangle(grass, (7, 12, 1, 3), p[1])
    rectangle(grass, (9, 12, 1, 3), p[1])
    rectangle(grass, (11, 12, 1, 3), p[1])
    save_surface(os.path.join(output_dir, "grass_depleted.png"), grass)

    # wheat_depleted — stubble
    wheat = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (150, 130, 70), 2: (180, 160, 90)}
    rectangle(wheat, (5, 12, 1, 3), p[1])
    rectangle(wheat, (8, 12, 1, 3), p[1])
    rectangle(wheat, (11, 12, 1, 3), p[1])
    save_surface(os.path.join(output_dir, "wheat_depleted.png"), wheat)

    # driftwood_depleted — scoured shore mark
    drift = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (180, 170, 150), 2: (150, 140, 120)}
    rectangle(drift, (4, 11, 8, 1), p[1])
    drift.set_at((6, 11), p[2])
    drift.set_at((9, 11), p[2])
    save_surface(os.path.join(output_dir, "driftwood_depleted.png"), drift)

    # shell_depleted — empty scoured shell
    shell = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (200, 190, 170), 2: (180, 170, 150)}
    for y in range(16):
        for x in range(16):
            dist = ((x - 8) ** 2 + (y - 10) ** 2) ** 0.5
            if dist <= 4 and y <= 10:
                shell.set_at((x, y), p[1])
    save_surface(os.path.join(output_dir, "shell_depleted.png"), shell)

    # fish_depleted — empty pool ripple mark
    fish = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (160, 160, 180), 2: (100, 120, 160)}
    circle(fish, (8, 9), 5, p[1])
    circle(fish, (8, 9), 3, p[2])
    # Ripple marks
    fish.set_at((6, 9), p[1])
    fish.set_at((10, 9), p[1])
    save_surface(os.path.join(output_dir, "fish_depleted.png"), fish)

    # salt_depleted — desiccated crust
    salt = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (220, 220, 230), 2: (190, 190, 200)}
    rectangle(salt, (4, 9, 8, 2), p[1])
    salt.set_at((6, 9), p[2])
    salt.set_at((10, 9), p[2])
    save_surface(os.path.join(output_dir, "salt_depleted.png"), salt)

    # salt_crystal_depleted — cracked empty crystal
    sc = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (190, 190, 220), 2: (160, 160, 200)}
    polygon(sc, [(8, 4), (10, 8), (8, 13), (6, 8)], p[1])
    sc.set_at((8, 7), p[2])
    save_surface(os.path.join(output_dir, "salt_crystal_depleted.png"), sc)

    # peat_depleted — flattened mound
    peat = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (80, 60, 40), 2: (60, 40, 30)}
    circle(peat, (8, 11), 4, p[1])
    circle(peat, (7, 10), 2, p[2])
    save_surface(os.path.join(output_dir, "peat_depleted.png"), peat)

    # toxic_reed_depleted — cut bare stems
    tr = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (100, 80, 40), 2: (80, 60, 30)}
    rectangle(tr, (7, 11, 1, 4), p[1])
    rectangle(tr, (9, 11, 1, 4), p[1])
    rectangle(tr, (6, 11, 1, 3), p[1])
    save_surface(os.path.join(output_dir, "toxic_reed_depleted.png"), tr)

    # sand_depleted — flattened depression
    sand = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (180, 160, 120), 2: (160, 140, 100)}
    circle(sand, (8, 11), 4, p[1])
    circle(sand, (8, 11), 2, p[2])
    save_surface(os.path.join(output_dir, "sand_depleted.png"), sand)

    # cactus_depleted — desiccated shrivel
    cactus = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (100, 80, 40), 2: (80, 60, 30)}
    rectangle(cactus, (6, 6, 4, 8), p[1])
    rectangle(cactus, (7, 7, 2, 6), p[2])
    save_surface(os.path.join(output_dir, "cactus_depleted.png"), cactus)

    # silk_nest_depleted — empty desiccated nest
    silk = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (170, 165, 150), 2: (150, 145, 130)}
    for angle in range(0, 360, 45):
        import math
        for r in range(2, 5):
            sx = int(8 + r * math.cos(math.radians(angle)))
            sy = int(8 + r * math.sin(math.radians(angle)))
            if 0 <= sx < 16 and 0 <= sy < 16:
                silk.set_at((sx, sy), p[1])
    save_surface(os.path.join(output_dir, "silk_nest_depleted.png"), silk)

    # dragonbone_depleted — faded residual
    db = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (180, 170, 150), 2: (160, 150, 130)}
    rectangle(db, (5, 7, 6, 3), p[1])
    db.set_at((6, 8), p[2])
    db.set_at((10, 8), p[2])
    save_surface(os.path.join(output_dir, "dragonbone_depleted.png"), db)

    # void_essence_depleted — faded residual
    ve = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (70, 45, 110), 2: (50, 30, 80)}
    circle(ve, (8, 8), 4, p[1])
    circle(ve, (7, 7), 2, p[2])
    save_surface(os.path.join(output_dir, "void_essence_depleted.png"), ve)

    # phoenix_feather_depleted — faded residual
    pf = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (180, 60, 20), 2: (150, 40, 10)}
    for fy in range(3, 14):
        width = 1
        cx = 8 + ((fy * 2) % 3) - 1
        for fx in range(cx - width, cx + width + 1):
            if 0 <= fx < 16:
                pf.set_at((fx, fy), p[1])
    rectangle(pf, (8, 2, 1, 13), p[2])
    save_surface(os.path.join(output_dir, "phoenix_feather_depleted.png"), pf)

    print("  Generated 17 depleted world resource sprites")


def _make_stump_surf(name: str, p: dict[int, tuple[int, int, int]]) -> pygame.Surface:
    """Draw a generic tree stump sprite using the given palette."""
    surf = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    rectangle(surf, (12, 20, 8, 12), p[1])
    rectangle(surf, (13, 21, 6, 10), p[5])
    rectangle(surf, (13, 20, 6, 2), p[3])
    rectangle(surf, (14, 24, 4, 1), p[2])
    rectangle(surf, (14, 27, 4, 1), p[2])
    rectangle(surf, (10, 29, 3, 2), p[1])
    rectangle(surf, (19, 29, 3, 2), p[1])
    rectangle(surf, (11, 18, 1, 3), p[2])
    rectangle(surf, (18, 18, 1, 2), p[2])
    return surf

def generate_shared_fallbacks() -> None:
    """Generate shared fallback sprites."""
    print("\n=== Generating Shared Fallback Sprites ===")
    output_dir = os.path.join(OUTPUT_ROOT, "trees")

    stump_p = _tree_depleted_palette()
    # Generic stump
    stump = _make_stump_surf("stump", stump_p)
    save_surface(os.path.join(output_dir, "stump.png"), stump)

    sapling_p = _tree_sapling_palette()
    # Generic sapling
    gsap = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    rectangle(gsap, (15, 14, 2, 14), sapling_p[2])
    rectangle(gsap, (15, 14, 1, 14), sapling_p[3])
    circle(gsap, (16, 12), 6, sapling_p[3])
    circle(gsap, (13, 11), 4, sapling_p[4])
    circle(gsap, (19, 11), 4, sapling_p[4])
    circle(gsap, (16, 9), 3, sapling_p[5])
    gsap.set_at((16, 8), sapling_p[5])
    save_surface(os.path.join(output_dir, "sapling_generic.png"), gsap)

    young_p = _tree_young_palette()
    # Generic young
    gyoung = pygame.Surface((TREE_SIZE, TREE_SIZE), pygame.SRCALPHA)
    rectangle(gyoung, (13, 18, 6, 10), young_p[1])
    rectangle(gyoung, (14, 19, 4, 8), young_p[4])
    circle(gyoung, (16, 11), 8, young_p[2])
    circle(gyoung, (12, 10), 5, young_p[3])
    circle(gyoung, (20, 10), 5, young_p[3])
    circle(gyoung, (16, 9), 4, young_p[4])
    circle(gyoung, (16, 8), 3, young_p[5])
    save_surface(os.path.join(output_dir, "young_generic.png"), gyoung)

    # Generic rock rubble
    rubble_dir = os.path.join(OUTPUT_ROOT, "rocks")
    rubble = pygame.Surface((ROCK_SIZE, ROCK_SIZE), pygame.SRCALPHA)
    p = {1: (100, 95, 90), 2: (70, 65, 60), 3: (140, 135, 130)}
    circle(rubble, (8, 9), 5, p[1])
    circle(rubble, (6, 8), 3, p[2])
    circle(rubble, (10, 8), 3, p[3])
    rubble.set_at((7, 7), p[2])
    rubble.set_at((9, 8), p[2])
    rubble.set_at((8, 11), p[2])
    save_surface(os.path.join(rubble_dir, "rubble.png"), rubble)

    # Generic world depleted patch
    patch_dir = os.path.join(OUTPUT_ROOT, "world")
    patch = pygame.Surface((RESOURCE_SIZE, RESOURCE_SIZE), pygame.SRCALPHA)
    p = {1: (120, 100, 60), 2: (150, 130, 80)}
    circle(patch, (8, 9), 5, p[1])
    circle(patch, (7, 8), 3, p[2])
    save_surface(os.path.join(patch_dir, "depleted_patch.png"), patch)

    print("  Generated 5 shared fallback sprites")


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    """Generate all sprites."""
    print("Initializing pygame...")
    pygame.init()
    # Create a dummy display surface so convert_alpha() works
    pygame.display.set_mode((1, 1))

    print("\nGenerating sprites for Don't Starve RuneScape...")

    generate_player_sprites()
    generate_tree_sprites()
    generate_rock_sprites()
    generate_world_sprites()
    generate_monster_sprites()
    generate_structure_sprites()
    generate_npc_sprites()
    generate_terrain_sprites()
    generate_item_sprites()
    generate_campfire_sprite()
    generate_terrain_subassets()

    # Tier 3/4 content
    generate_tier3_rock_sprites()
    generate_tier3_world_sprites()
    generate_elder_wood_tree()
    generate_tier3_item_sprites()
    generate_tier3_structure_sprites()

    # Depleted & growth-stage sprites (this phase)
    generate_tree_depleted_sprites()
    generate_tree_growth_sprites()
    generate_rock_depleted_sprites()
    generate_world_depleted_sprites()
    generate_shared_fallbacks()

    print("\n=== All sprites generated! ===")
    print(f"Output directory: {OUTPUT_ROOT}/")

    pygame.quit()


if __name__ == "__main__":
    main()
