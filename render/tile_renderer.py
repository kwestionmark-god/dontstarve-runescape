"""
tile_renderer.py — 2.5D terrain rendering.

Renders the tile map with elevation-based Y-offsets for a pseudo-3D
effect. Tiles are sorted back-to-front by screen-space depth so that
higher-elevation terrain properly occludes lower terrain behind it.

Usage:
    tile_renderer = TileRenderer(tile_map, camera, screen)
    tile_renderer.render()
"""

from __future__ import annotations

import math
import pygame
from config import Z_SCALE, FOG_NEAR_DISTANCE, FOG_FAR_DISTANCE, FOG_CULL_DISTANCE, FOG_COLOR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from world.tile_map import TileMap


class TileRenderer:
    """
    Renders terrain tiles with elevation-based 2.5D depth.

    Parameters
    ----------
    tile_map : TileMap
        The generated tile map (set ``None`` when deinit).
    screen : pygame.Surface | None
        Display surface for ``screen_to_world`` lookup (can be ``None``
        for direct camera math).
    """

    __slots__ = ("tile_map", "screen", "_terrain_cache", "seasonal_renderer")

    # How much higher-elevation tiles shift upward on screen (px).
    _ELEVATION_SORT_WEIGHT = 0.6  # Blend of world-y and elevation for depth sort

    def __init__(
        self,
        tile_map: "TileMap | None",
        screen: Any,
    ) -> None:
        """
        Parameters
        ----------
        tile_map : TileMap | None
            The tile map (set ``None`` to disable rendering).
        screen : pygame.Surface
            Display surface for ``screen_to_world`` lookup.
        """
        self.tile_map = tile_map
        self.screen = screen
        self._terrain_cache: dict[str, pygame.Surface | None] = {}

    # ── Rendering ──────────────────────────────────────────────────────

    def render(self, camera: "Any | None") -> None:
        """
        Render all visible terrain tiles as smooth 4-point quads.

        Each tile is drawn as a single quad whose corners are displaced
        vertically by interpolated elevation, producing seamless terrain.
        Tiles are sorted back-to-front by average Z depth.

        Parameters
        ----------
        camera : Camera | None
            The orbital camera for coordinate transforms.
        """
        tile_map = self.tile_map
        if tile_map is None or camera is None:
            return

        left, top, right, bottom = camera.get_view_rect()
        if left == right or top == bottom:
            return

        tile_size = 64

        # ── Collect visible tiles with depth ────────────────────────
        tiles_to_render: list[tuple[float, int, int]] = []

        x_min = max(0, int(left // tile_size))
        x_max = min(tile_map.width, int(right // tile_size) + 1)
        y_min = max(0, int(top // tile_size))
        y_max = min(tile_map.height, int(bottom // tile_size) + 1)

        for x in range(x_min, x_max):
            for y in range(y_min, y_max):
                tile = tile_map.tiles[x][y]
                if tile is None:
                    continue

                # Compute corner heights
                h_nw = tile_map.get_corner_height(x, y)
                h_ne = tile_map.get_corner_height(x + 1, y)
                h_sw = tile_map.get_corner_height(x, y + 1)
                h_se = tile_map.get_corner_height(x + 1, y + 1)

                # Depth sort by average Z of the quad
                avg_corner_h = (h_nw + h_ne + h_sw + h_se) / 4.0
                depth = y + avg_corner_h * 0.5

                # Convert corners to screen space
                corners = [
                    camera.world_to_screen(x * tile_size, y * tile_size, elevation=h_nw * Z_SCALE),   # NW
                    camera.world_to_screen((x + 1) * tile_size, y * tile_size, elevation=h_ne * Z_SCALE),  # NE
                    camera.world_to_screen((x + 1) * tile_size, (y + 1) * tile_size, elevation=h_se * Z_SCALE),  # SE
                    camera.world_to_screen(x * tile_size, (y + 1) * tile_size, elevation=h_sw * Z_SCALE),   # SW
                ]

                tiles_to_render.append((depth, x, y, corners))

        # Sort back-to-front (largest depth first).
        tiles_to_render.sort(key=lambda t: t[0], reverse=True)

        # ── Draw tiles ──────────────────────────────────────────────
        for _depth, x, y, corners in tiles_to_render:
            tile = tile_map.tiles[x][y]
            if tile is None:
                continue

            # ── LOD: skip tiles beyond fog cull distance ────────────
            tile_cx = x * tile_size + tile_size / 2
            tile_cy = y * tile_size + tile_size / 2
            # Camera needs player reference; try to get player position
            player_x = getattr(camera, 'player', None)
            if player_x is not None and hasattr(player_x, 'world_x'):
                dist = math.hypot(tile_cx - player_x.world_x, tile_cy - player_x.world_y)
            else:
                dist = 0.0

            if dist > FOG_CULL_DISTANCE:
                continue  # LOD cull: too far to render

            # Compute fog alpha (0 = fully visible, 255 = fully fogged)
            fog_alpha = 0
            if player_x is not None and hasattr(player_x, 'world_x'):
                if dist > FOG_FAR_DISTANCE:
                    fog_alpha = 255
                elif dist > FOG_NEAR_DISTANCE:
                    fog_alpha = int(255 * (dist - FOG_NEAR_DISTANCE) / (FOG_FAR_DISTANCE - FOG_NEAR_DISTANCE))

            # ── Compute slope shading ───────────────────────────────
            brightness, _slope_mag = tile_map.compute_slope_shading(x, y)

            # Try to load terrain sprite
            biome_name = tile.biome.id if tile.biome else "forest"
            terrain_sprite = self._load_terrain_sprite(biome_name)

            if terrain_sprite is not None:
                # Scale terrain sprite by camera zoom so tiles stay seamless
                zoom = camera.zoom if hasattr(camera, "zoom") else 1.0
                if zoom != 1.0:
                    scaled_w = max(1, int(terrain_sprite.get_width() * zoom))
                    scaled_h = max(1, int(terrain_sprite.get_height() * zoom))
                    terrain_sprite = pygame.transform.scale(terrain_sprite, (scaled_w, scaled_h))

                # Draw terrain sprite centered on tile
                tile_center_x = x * 64 + 32
                tile_center_y = y * 64 + 32
                avg_height = tile_map.get_tile_center_height(x, y)
                screen_x, screen_y = camera.world_to_screen(
                    tile_center_x, tile_center_y,
                    elevation=avg_height * Z_SCALE,
                )
                rect = terrain_sprite.get_rect(center=(int(screen_x), int(screen_y)))
                self.screen.blit(terrain_sprite, rect)

                # ── Slope shading overlay (BLEND_RGBA_MULT) ───────────
                # Skip trivial brightness values (flat terrain).
                if abs(brightness - 1.0) > 0.01:
                    shade_val = int(abs(1.0 - brightness) * 255)
                    shade_surf = pygame.Surface(
                        terrain_sprite.get_size(), pygame.SRCALPHA,
                    )
                    shade_surf.fill((shade_val, shade_val, shade_val, shade_val))
                    self.screen.blit(
                        shade_surf, rect,
                        special_flags=pygame.BLEND_RGBA_MULT,
                    )

                # Apply fog overlay if needed
                if fog_alpha > 0:
                    fog_surf = pygame.Surface(terrain_sprite.get_size(), pygame.SRCALPHA)
                    fog_surf.fill(FOG_COLOR + (fog_alpha,))
                    self.screen.blit(fog_surf, rect)
            else:
                # Fallback: colored polygon
                # Apply slope shading to terrain color, with seasonal blending
                base_color = tile.terrain_color
                if (
                    self.seasonal_renderer is not None
                ):
                    base_color = self.seasonal_renderer.get_tile_color(
                        biome_name, base_color,
                    )
                r = int(base_color[0] * brightness)
                g = int(base_color[1] * brightness)
                b = int(base_color[2] * brightness)
                color = (
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                )
                pygame.draw.polygon(self.screen, color, corners)

                # Apply fog overlay to polygon
                if fog_alpha > 0:
                    fog_surf = pygame.Surface(
                        (int(max(c[0] for c in corners)) - int(min(c[0] for c in corners)) + 1,
                         int(max(c[1] for c in corners)) - int(min(c[1] for c in corners)) + 1),
                        pygame.SRCALPHA,
                    )
                    fog_surf.fill(FOG_COLOR + (fog_alpha,))
                    offset_x = int(min(c[0] for c in corners))
                    offset_y = int(min(c[1] for c in corners))
                    self.screen.blit(fog_surf, (offset_x, offset_y))

            # Subtle edge highlight for tile grid visibility (skip if fully fogged).
            if fog_alpha < 200:
                highlight_alpha = max(0, 32 - fog_alpha)
                pygame.draw.polygon(self.screen, (0, 0, 0, highlight_alpha), corners, 1)

    # ── Terrain sprite loading ───────────────────────────────────────

    def _load_terrain_sprite(self, biome_name: str) -> pygame.Surface | None:
        """
        Load a terrain sprite for a biome.
        
        Args:
            biome_name: Biome identifier (e.g. 'forest', 'plains').
            
        Returns:
            The loaded terrain sprite, or None if not found.
        """
        if biome_name in self._terrain_cache:
            return self._terrain_cache[biome_name]

        sprite_key = f"terrain/{biome_name}"
        try:
            path = f"assets/sprites/{sprite_key}.png"
            surf = pygame.image.load(path)
            surf = surf.convert_alpha()
        except (pygame.error, FileNotFoundError):
            surf = None

        self._terrain_cache[biome_name] = surf
        return surf
