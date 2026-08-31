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
    from render.lighting_system import LightingSystem


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
    lighting_system : LightingSystem | None
        Phase 6 lighting coordinator (sun direction, ambient level, presets).
    """

    __slots__ = ("tile_map", "screen", "_terrain_cache", "seasonal_renderer", "lighting_system")

    # How much higher-elevation tiles shift upward on screen (px).
    _ELEVATION_SORT_WEIGHT = 0.6

    def __init__(
        self,
        tile_map: "TileMap | None",
        screen: pygame.Surface | None,
        lighting_system: "LightingSystem | None" = None,
    ) -> None:
        self.tile_map = tile_map
        self.screen = screen
        self._terrain_cache: dict[str, pygame.Surface | None] = {}
        self.seasonal_renderer = None  # set externally by bootstrap
        self.lighting_system = lighting_system

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

        # Get lighting state (Phase 6)
        lighting = self.lighting_system
        use_light_angle = lighting is not None and lighting.preset_config.get("multi_light", False)
        use_ao = lighting is not None and lighting.preset_config.get("ao", False)
        use_rim = lighting is not None and lighting.preset_config.get("rim", False)
        use_height_fog = lighting is not None and lighting.preset_config.get("height_fog", False)
        # Clamp values
        rim_exp = 3.0
        rim_strength = 0.25
        light_x, light_y = 0.0, -1.0  # Default NW (screen-space)

        if use_light_angle and lighting is not None:
            lx, ly, lz = lighting.sun_direction
            # Project into 2D slope-shading space (elevation gradient is world X/Y)
            mag = math.sqrt(lx * lx + ly * ly)
            if mag > 0:
                light_x, light_y = lx / mag, ly / mag
            rim_strength = 0.25

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
                    camera.world_to_screen(x * tile_size, y * tile_size, elevation=h_nw * Z_SCALE),
                    camera.world_to_screen((x + 1) * tile_size, y * tile_size, elevation=h_ne * Z_SCALE),
                    camera.world_to_screen((x + 1) * tile_size, (y + 1) * tile_size, elevation=h_se * Z_SCALE),
                    camera.world_to_screen(x * tile_size, (y + 1) * tile_size, elevation=h_sw * Z_SCALE),
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
            player_x = getattr(camera, 'player', None)
            if player_x is not None and hasattr(player_x, 'world_x'):
                dist = math.hypot(tile_cx - player_x.world_x, tile_cy - player_x.world_y)
            else:
                dist = 0.0

            if dist > FOG_CULL_DISTANCE:
                continue

            # ── Compute base fog alpha (linear falloff) ────────────
            fog_alpha = 0
            if player_x is not None and hasattr(player_x, 'world_x'):
                if dist > FOG_FAR_DISTANCE:
                    fog_alpha = 255
                elif dist > FOG_NEAR_DISTANCE:
                    fog_alpha = int(255 * (dist - FOG_NEAR_DISTANCE) / (FOG_FAR_DISTANCE - FOG_NEAR_DISTANCE))

            # Phase 6: Scale fog by precomputed density (volumetric/height fog)
            if use_height_fog and tile.fog_density is not None:
                fog_alpha = int(fog_alpha * tile.fog_density)
                fog_alpha = max(0, min(255, fog_alpha))

            # ── Compute slope shading ───────────────────────────────
            if use_light_angle:
                brightness, slope_mag = tile_map.compute_slope_shading(
                    x, y, light_dir=(light_x, light_y, 0.0)
                )
                # Multiply by ambient and weather levels
                ambient_level = lighting.ambient_level if lighting is not None else 1.0
                weather_light = lighting.weather_light_level if lighting is not None else 1.0
                brightness *= ambient_level * weather_light
            else:
                # Legacy fixed NW shading
                from config import SHADING_STRENGTH
                nw = tile_map.get_raw_corner_elevation(x, y)
                ne = tile_map.get_raw_corner_elevation(x + 1, y)
                sw = tile_map.get_raw_corner_elevation(x, y + 1)
                se = tile_map.get_raw_corner_elevation(x + 1, y + 1)
                grad_x = (ne + se - nw - sw) / 2.0
                grad_y = (sw + se - nw - ne) / 2.0
                slope_mag = math.sqrt(grad_x * grad_x + grad_y * grad_y)
                light_dot = (-1.0 * grad_x) + (-1.0 * grad_y)
                brightness = 1.0 + max(-SHADING_STRENGTH, min(SHADING_STRENGTH, light_dot * SHADING_STRENGTH * 2.0))

            # Try to load terrain sprite
            biome_name = tile.biome.id if tile.biome else "forest"
            terrain_sprite = self._load_terrain_sprite(biome_name)

            if terrain_sprite is not None:
                # Scale terrain sprite by camera zoom
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

                # ── Ambient occlusion overlay ───────────────────────
                if use_ao and tile_map.corner_ao:
                    ao = tile_map.get_tile_ao(x, y)
                    if ao < 0.99:
                        ao_alpha = int((1.0 - ao) * 255)
                        ao_surf = pygame.Surface(terrain_sprite.get_size(), pygame.SRCALPHA)
                        ao_surf.fill((0, 0, 0, ao_alpha))
                        self.screen.blit(ao_surf, rect)

                # ── Rim lighting / fresnel ──────────────────────────
                if use_rim and slope_mag > 0.15:
                    # Compute normal and view factor
                    nx, ny, nz = tile_map.get_surface_normal(x, y)
                    n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
                    if n_len > 0:
                        nz /= n_len
                        # View z from camera pitch
                        view_z = -math.sin(camera.pitch)
                        dot = -nz * view_z
                        rim = max(0.0, 1.0 - dot) ** rim_exp
                        rim_alpha = int(rim * rim_strength * 255)
                        if rim_alpha > 0:
                            rim_surf = pygame.Surface(terrain_sprite.get_size(), pygame.SRCALPHA)
                            rim_surf.fill((255, 255, 255, rim_alpha))
                            self.screen.blit(rim_surf, rect, special_flags=pygame.BLEND_RGBA_ADD)

                # Apply fog overlay
                if fog_alpha > 0:
                    fog_surf = pygame.Surface(terrain_sprite.get_size(), pygame.SRCALPHA)
                    fog_surf.fill(FOG_COLOR + (fog_alpha,))
                    self.screen.blit(fog_surf, rect)
            else:
                # Fallback: colored polygon
                base_color = tile.terrain_color
                if self.seasonal_renderer is not None:
                    base_color = self.seasonal_renderer.get_tile_color(biome_name, base_color)
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
                    min_x = int(min(c[0] for c in corners))
                    min_y = int(min(c[1] for c in corners))
                    max_x = int(max(c[0] for c in corners))
                    max_y = int(max(c[1] for c in corners))
                    fog_surf = pygame.Surface(
                        (max_x - min_x + 1, max_y - min_y + 1),
                        pygame.SRCALPHA,
                    )
                    fog_surf.fill(FOG_COLOR + (fog_alpha,))
                    self.screen.blit(fog_surf, (min_x, min_y))
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
