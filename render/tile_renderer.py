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
from config import (
    Z_SCALE, FOG_NEAR_DISTANCE, FOG_FAR_DISTANCE, FOG_CULL_DISTANCE, FOG_COLOR,
    TILE_SUBDIVISIONS, SHADING_STRENGTH,
)
from render.gouraud import fill_triangle
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

    __slots__ = ("tile_map", "screen", "_terrain_cache", "seasonal_renderer", "lighting_system",
                 "_xform_cache")

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
        # Transformed (shaded + rotated + scaled) sprite cache, keyed per
        # tile. Rebuilt only when a tile's shading values or the camera
        # transform change — a static camera reuses everything.
        self._xform_cache: dict = {}
        self.seasonal_renderer = None  # set externally by bootstrap
        self.lighting_system = lighting_system

    # ── Rendering ──────────────────────────────────────────────────────

    def render(self, camera: "Any | None") -> None:
        """
        Render all visible terrain tiles using per-vertex Gouraud shading.

        Each tile is split into two triangles (NW-SE diagonal) and shaded
        by interpolating per-corner brightness, AO, and fog across the
        triangle. Falls back to the flat per-tile path when per-corner
        grids are not baked.
        """
        tile_map = self.tile_map
        if tile_map is None or camera is None:
            return

        lighting = self.lighting_system
        use_ao = lighting is not None and lighting.preset_config.get("ao", False)
        use_rim = lighting is not None and lighting.preset_config.get("rim", False)
        use_height_fog = lighting is not None and lighting.preset_config.get("height_fog", False)

        # Light direction for per-corner shading
        light_x, light_y, light_z = 0.0, -1.0, 0.0  # Default NW
        if lighting is not None:
            lx, ly, lz = lighting.sun_direction
            mag = math.sqrt(lx * lx + ly * ly)
            if mag > 0:
                light_x, light_y, light_z = lx / mag, ly / mag, lz / mag

        # Per-corner shading from LightingSystem cache (Phase 7 P2)
        corner_brightness = None
        corner_normal = None
        if lighting is not None and tile_map.corner_height:
            corner_brightness, corner_normal = lighting.compute_all_corner_shading(
                tile_map, light_x, light_y, light_z
            )

        # Terrain style from preset: "flat" = Gouraud triangles,
        # "textured" = sprite + sub-tile interpolation.
        terrain_style = "textured"
        if lighting is not None:
            terrain_style = lighting.preset_config.get("terrain_style", "textured")

        # LOD threshold: beyond this fraction of fog cull distance, fall back to flat
        lod_fallback_dist = FOG_CULL_DISTANCE * 0.66
        use_lod = False
        if lighting is not None and lighting.preset_config.get("terrain_lod", True):
            use_lod = True

        # Terrain subdivision from preset (for textured mode)
        terrain_subdiv = TILE_SUBDIVISIONS
        if lighting is not None:
            terrain_subdiv = lighting.preset_config.get("terrain_subdiv", TILE_SUBDIVISIONS)

        left, top, right, bottom = camera.get_view_rect()
        if left == right or top == bottom:
            return

        tile_size = 64

        # Precompute player position for fog/distance culling
        player = getattr(camera, 'player', None)
        player_pos = None
        if player is not None and hasattr(player, 'world_x'):
            player_pos = (player.world_x, player.world_y)

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

                # Corner heights for depth sort (use baked or fallback)
                if tile_map.corner_height:
                    h_nw = tile_map.corner_height[x][y]
                    h_ne = tile_map.corner_height[x + 1][y]
                    h_sw = tile_map.corner_height[x][y + 1]
                    h_se = tile_map.corner_height[x + 1][y + 1]
                else:
                    h_nw = tile_map.get_corner_height(x, y)
                    h_ne = tile_map.get_corner_height(x + 1, y)
                    h_sw = tile_map.get_corner_height(x, y + 1)
                    h_se = tile_map.get_corner_height(x + 1, y + 1)

                avg_corner_h = (h_nw + h_ne + h_sw + h_se) / 4.0
                # Depth along the camera's view axis (yaw-rotated Y) so
                # back-to-front order stays correct when the camera rotates.
                cos_yaw = math.cos(camera.yaw) if hasattr(camera, "yaw") else 1.0
                sin_yaw = math.sin(camera.yaw) if hasattr(camera, "yaw") else 0.0
                depth = y * cos_yaw + x * sin_yaw + avg_corner_h * 0.5

                tiles_to_render.append((depth, x, y))

        # Sort back-to-front (largest depth first).
        tiles_to_render.sort(key=lambda t: t[0], reverse=True)

        # Cache base fog alpha per tile (distance only, not elevation)
        tile_fog_alpha = {}
        if player_pos:
            px, py = player_pos
            for _depth, x, y in tiles_to_render:
                tile_cx = x * tile_size + tile_size / 2
                tile_cy = y * tile_size + tile_size / 2
                dist = math.hypot(tile_cx - px, tile_cy - py)
                if dist > FOG_CULL_DISTANCE:
                    tile_fog_alpha[(x, y)] = -1  # Culled
                elif dist > FOG_FAR_DISTANCE:
                    tile_fog_alpha[(x, y)] = 255
                elif dist > FOG_NEAR_DISTANCE:
                    tile_fog_alpha[(x, y)] = int(
                        255 * (dist - FOG_NEAR_DISTANCE) / (FOG_FAR_DISTANCE - FOG_NEAR_DISTANCE)
                    )
                else:
                    tile_fog_alpha[(x, y)] = 0
        else:
            for _depth, x, y in tiles_to_render:
                tile_fog_alpha[(x, y)] = 0

        # ── Draw tiles ──────────────────────────────────────────────
        for _depth, x, y in tiles_to_render:
            tile = tile_map.tiles[x][y]
            if tile is None:
                continue

            fog_alpha = tile_fog_alpha.get((x, y), 0)
            if fog_alpha < 0:
                continue  # Culled

            # LOD: fall back to flat rendering beyond lod_fallback_dist
            use_gouraud = (terrain_style == "flat" and corner_brightness is not None)
            if use_lod and player_pos:
                tile_cx = x * tile_size + tile_size / 2
                tile_cy = y * tile_size + tile_size / 2
                dist = math.hypot(tile_cx - player_pos[0], tile_cy - player_pos[1])
                if dist > lod_fallback_dist:
                    use_gouraud = False

            # Per-tile fog modulation by corner_fog density (Phase 7 P1)
            if use_height_fog and tile_map.corner_fog:
                # Average the 4 corner fog densities
                c_fog = (
                    tile_map.corner_fog[x][y] +
                    tile_map.corner_fog[x + 1][y] +
                    tile_map.corner_fog[x][y + 1] +
                    tile_map.corner_fog[x + 1][y + 1]
                ) / 4.0
                fog_alpha = int(fog_alpha * c_fog)
                fog_alpha = max(0, min(255, fog_alpha))

            # Base biome color
            biome_name = tile.biome.id if tile.biome else "forest"
            base_color = tile.terrain_color
            if self.seasonal_renderer is not None:
                base_color = self.seasonal_renderer.get_tile_color(biome_name, base_color)

            # ── Choose rendering path ───────────────────────────────
            if use_gouraud:
                self._render_tile_gouraud(
                    x, y, tile, camera, tile_size,
                    base_color, corner_brightness, corner_normal,
                    tile_map.corner_ao if use_ao else None,
                    fog_alpha, FOG_COLOR,
                    use_rim, camera.pitch if hasattr(camera, "pitch") else 0.0,
                )
            else:
                # Textured path: sprite + sub-tile interpolation (or flat fallback)
                self._render_tile_textured(
                    x, y, tile, camera, tile_size,
                    base_color, biome_name,
                    corner_brightness, tile_map.corner_ao if use_ao else None,
                    tile_map.corner_fog if use_height_fog else None,
                    fog_alpha, FOG_COLOR,
                    use_rim,
                    terrain_subdiv,
                )

    def _render_tile_gouraud(
        self,
        x: int, y: int, tile: Tile, camera: "Any", tile_size: int,
        base_color: tuple[int, int, int],
        corner_brightness: "np.ndarray",
        corner_normal: "np.ndarray | None",
        corner_ao: list[list[float]] | None,
        fog_alpha: int, fog_color: tuple[int, int, int],
        use_rim: bool, camera_pitch: float,
    ) -> None:
        """Render a tile as two Gouraud-shaded triangles using per-corner values."""
        # Read per-corner values from precomputed grids
        # Corner indices: NW=(x,y), NE=(x+1,y), SW=(x,y+1), SE=(x+1,y+1)
        b_nw = corner_brightness[x, y]
        b_ne = corner_brightness[x + 1, y]
        b_sw = corner_brightness[x, y + 1]
        b_se = corner_brightness[x + 1, y + 1]

        ao_nw = ao_ne = ao_sw = ao_se = 1.0
        if corner_ao:
            ao_nw = corner_ao[x][y]
            ao_ne = corner_ao[x + 1][y]
            ao_sw = corner_ao[x][y + 1]
            ao_se = corner_ao[x + 1][y + 1]

        # Corner heights for vertex positions
        h_nw = self.tile_map.corner_height[x][y]
        h_ne = self.tile_map.corner_height[x + 1][y]
        h_sw = self.tile_map.corner_height[x][y + 1]
        h_se = self.tile_map.corner_height[x + 1][y + 1]

        # Compute screen positions of the 4 corners
        p_nw = camera.world_to_screen(x * tile_size, y * tile_size, elevation=h_nw * Z_SCALE)
        p_ne = camera.world_to_screen((x + 1) * tile_size, y * tile_size, elevation=h_ne * Z_SCALE)
        p_se = camera.world_to_screen((x + 1) * tile_size, (y + 1) * tile_size, elevation=h_se * Z_SCALE)
        p_sw = camera.world_to_screen(x * tile_size, (y + 1) * tile_size, elevation=h_sw * Z_SCALE)

        # Per-vertex colors: base_color * brightness * AO
        def vertex_color(b, ao):
            r = int(base_color[0] * b * ao)
            g = int(base_color[1] * b * ao)
            b_ = int(base_color[2] * b * ao)
            return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b_)))

        c_nw = vertex_color(b_nw, ao_nw)
        c_ne = vertex_color(b_ne, ao_ne)
        c_sw = vertex_color(b_sw, ao_sw)
        c_se = vertex_color(b_se, ao_se)

        # Split quad into two triangles: NW-NE-SE and NW-SE-SW
        fill_triangle(self.screen, p_nw, p_ne, p_se, c_nw, c_ne, c_se)
        fill_triangle(self.screen, p_nw, p_se, p_sw, c_nw, c_se, c_sw)

        # Rim lighting: draw additive pass per triangle (simplified - use avg rim per tile)
        if use_rim and corner_normal is not None:
            self._render_rim_gouraud(
                x, y, tile_size, camera, camera_pitch,
                corner_normal, base_color, c_nw, c_ne, c_se, c_sw,
                p_nw, p_ne, p_se, p_sw
            )

        # Fog overlay as a separate blended pass (uniform per tile for now)
        if fog_alpha > 0:
            self._apply_fog_to_quad(p_nw, p_ne, p_se, p_sw, fog_alpha, fog_color)

        # Subtle wireframe highlight
        if fog_alpha < 200:
            highlight_alpha = max(0, 32 - fog_alpha)
            pygame.draw.polygon(self.screen, (0, 0, 0, highlight_alpha), [p_nw, p_ne, p_se, p_sw], 1)

    def _render_rim_gouraud(
        self,
        x: int, y: int, tile_size: int, camera: "Any", camera_pitch: float,
        corner_normal: "np.ndarray", base_color: tuple[int, int, int],
        c_nw, c_ne, c_se, c_sw,
        p_nw, p_ne, p_se, p_sw
    ) -> None:
        """Additive rim lighting pass for Gouraud triangles (simplified)."""
        # Compute average rim factor per vertex, then do additive fill
        rim_exp = 3.0
        rim_strength = 0.25
        view_z = -math.sin(camera_pitch)

        def rim_factor_at(cx, cy):
            nx, ny, nz = corner_normal[cx, cy]
            n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n_len == 0:
                return 0.0
            nz_n = nz / n_len
            dot = -nz_n * view_z
            rim = max(0.0, 1.0 - dot) ** rim_exp
            return int(rim * rim_strength * 255)

        r_nw = rim_factor_at(x, y)
        r_ne = rim_factor_at(x + 1, y)
        r_se = rim_factor_at(x + 1, y + 1)
        r_sw = rim_factor_at(x, y + 1)

        if r_nw == 0 and r_ne == 0 and r_se == 0 and r_sw == 0:
            return

        # Rim color is white additive
        rc_nw = (r_nw, r_nw, r_nw)
        rc_ne = (r_ne, r_ne, r_ne)
        rc_se = (r_se, r_se, r_se)
        rc_sw = (r_sw, r_sw, r_sw)

        # Draw additive rim triangles
        fill_triangle(self.screen, p_nw, p_ne, p_se, rc_nw, rc_ne, rc_se)
        fill_triangle(self.screen, p_nw, p_se, p_sw, rc_nw, rc_se, rc_sw)

    def _apply_fog_to_quad(
        self,
        p0: tuple[float, float], p1: tuple[float, float],
        p2: tuple[float, float], p3: tuple[float, float],
        alpha: int, color: tuple[int, int, int],
    ) -> None:
        """Draw a fog overlay over a quad by filling two triangles with alpha."""
        fog_surf = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        fog_c = color + (alpha,)
        fill_triangle(fog_surf, p0, p1, p2, fog_c, fog_c, fog_c)
        fill_triangle(fog_surf, p0, p2, p3, fog_c, fog_c, fog_c)
        self.screen.blit(fog_surf, (0, 0))

    def _render_tile_textured(
        self,
        x: int, y: int, tile: Tile, camera: "Any", tile_size: int,
        base_color: tuple[int, int, int], biome_name: str,
        corner_brightness: "np.ndarray | None",
        corner_ao: list[list[float]] | None,
        corner_fog: list[list[float]] | None,
        fog_alpha: int, fog_color: tuple[int, int, int],
        use_rim: bool,
        terrain_subdiv: int = TILE_SUBDIVISIONS,
    ) -> None:
        """Render tile using biome sprite with sub-tile interpolated shading."""
        # Load terrain sprite
        terrain_sprite = self._load_terrain_sprite(biome_name)
        if terrain_sprite is None:
            # Fallback to flat polygon
            if corner_brightness is not None:
                b = corner_brightness[x, y]
                r = int(base_color[0] * b)
                g = int(base_color[1] * b)
                b_ = int(base_color[2] * b)
                color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b_)))
            else:
                color = base_color
            # Get corner positions for flat quad
            h_nw = self.tile_map.get_corner_height(x, y)
            h_ne = self.tile_map.get_corner_height(x + 1, y)
            h_se = self.tile_map.get_corner_height(x + 1, y + 1)
            h_sw = self.tile_map.get_corner_height(x, y + 1)
            corners = [
                camera.world_to_screen(x * tile_size, y * tile_size, elevation=h_nw * Z_SCALE),
                camera.world_to_screen((x + 1) * tile_size, y * tile_size, elevation=h_ne * Z_SCALE),
                camera.world_to_screen((x + 1) * tile_size, (y + 1) * tile_size, elevation=h_se * Z_SCALE),
                camera.world_to_screen(x * tile_size, (y + 1) * tile_size, elevation=h_sw * Z_SCALE),
            ]
            pygame.draw.polygon(self.screen, color, corners)
            if fog_alpha > 0:
                self._apply_fog_to_quad(*corners, fog_alpha, fog_color)
            return

        # Camera projection: the world→screen map for a tile is
        #   screen = rotate(yaw) then vertical-scale by tan(pitch), plus zoom.
        # Bake shading into the sprite, then apply the same transform so
        # each tile covers exactly its projected footprint (no gasket gaps
        # when the camera rotates). The fully transformed sprite is cached
        # per tile and rebuilt only when its shading or the camera changes.
        zoom = camera.zoom if hasattr(camera, "zoom") else 1.0
        pitch_factor = math.tan(camera.pitch) if hasattr(camera, "pitch") else 1.0
        yaw = camera.yaw if hasattr(camera, "yaw") else 0.0

        # Quantized shading signature for the cache key (1/32 steps)
        if corner_brightness is not None:
            ao0 = corner_ao[x][y] if corner_ao else 1.0
            ao1 = corner_ao[x + 1][y] if corner_ao else 1.0
            ao2 = corner_ao[x][y + 1] if corner_ao else 1.0
            ao3 = corner_ao[x + 1][y + 1] if corner_ao else 1.0
            shade_key = (
                int(corner_brightness[x, y] * ao0 * 32),
                int(corner_brightness[x + 1, y] * ao1 * 32),
                int(corner_brightness[x, y + 1] * ao2 * 32),
                int(corner_brightness[x + 1, y + 1] * ao3 * 32),
                base_color,
            )
        else:
            shade_key = None

        tkey = (
            x, y, biome_name, shade_key,
            int(yaw * 720), int(zoom * 200), int(pitch_factor * 500),
        )
        sprite = self._xform_cache.get(tkey)
        if sprite is None:
            sprite = terrain_sprite
            # Bake per-corner brightness/AO as sub-tile multiplicative shading
            if corner_brightness is not None:
                sprite = terrain_sprite.copy()
                self._bake_subtile_shading(
                    sprite, x, y, base_color,
                    corner_brightness, corner_ao, terrain_subdiv,
                )

            # Rotate by yaw, then squash vertically by tan(pitch)
            cos_y = math.cos(yaw)
            sin_y = math.sin(yaw)
            axis_aligned = abs(sin_y) < 0.01 and cos_y > 0
            if axis_aligned:
                scaled_w = max(1, int(round(sprite.get_width() * zoom)) + 2)
                scaled_h = max(1, int(round(sprite.get_height() * zoom * pitch_factor)) + 2)
                sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
            else:
                # Camera yaw maps world +X to the right/down (clockwise on
                # screen), and pygame rotates counterclockwise-positive, so
                # the angle is negated.
                rotated = pygame.transform.rotate(sprite, -math.degrees(yaw))
                bbox = sprite.get_width() * (abs(cos_y) + abs(sin_y))
                # +2 px: tiles are painted back-to-front, so the front tile's
                # solid interior covers the anti-aliased fringe of its
                # neighbours instead of letting the background bleed through.
                scaled_w = max(1, int(round(bbox * zoom)) + 2)
                scaled_h = max(1, int(round(bbox * zoom * pitch_factor)) + 2)
                sprite = pygame.transform.smoothscale(rotated, (scaled_w, scaled_h))

            if len(self._xform_cache) > 4096:
                self._xform_cache.clear()
            self._xform_cache[tkey] = sprite

        # Draw centered on the projected tile center
        tile_center_x = x * 64 + 32
        tile_center_y = y * 64 + 32
        avg_height = self.tile_map.get_tile_center_height(x, y)
        screen_x, screen_y = camera.world_to_screen(
            tile_center_x, tile_center_y, elevation=avg_height * Z_SCALE,
        )
        rect = sprite.get_rect(center=(int(screen_x), int(screen_y)))
        self.screen.blit(sprite, rect)

        # Fog overlay drawn as a screen-space quad so player movement (which
        # changes fog_alpha) doesn't invalidate the sprite cache.
        if fog_alpha > 0:
            eff_alpha = fog_alpha
            if corner_fog:
                eff_alpha = int(fog_alpha * (
                    corner_fog[x][y] + corner_fog[x + 1][y]
                    + corner_fog[x][y + 1] + corner_fog[x + 1][y + 1]
                ) / 4.0)
                eff_alpha = max(0, min(255, eff_alpha))
            if eff_alpha > 0:
                fog_surf = pygame.Surface(rect.size, pygame.SRCALPHA)
                # Diamond approximating the (sheared) tile footprint so fog
                # doesn't bleed over neighbouring tiles through the rotated
                # sprite's transparent corners.
                w2, h2 = rect.width // 2, rect.height // 2
                pygame.draw.polygon(
                    fog_surf, fog_color + (eff_alpha,),
                    [(w2, 0), (rect.width, h2), (w2, rect.height), (0, h2)],
                )
                self.screen.blit(fog_surf, rect)

    def _bake_subtile_shading(
        self,
        sprite: pygame.Surface,
        x: int, y: int,
        base_color: tuple[int, int, int],
        corner_brightness: "np.ndarray",
        corner_ao: list[list[float]] | None,
        terrain_subdiv: int,
    ) -> None:
        """Multiply per-corner shading into the tile sprite via a sub-tile grid."""
        subdiv = max(2, terrain_subdiv)
        w, h = sprite.get_size()
        sw = w / subdiv
        sh = h / subdiv

        b_nw = corner_brightness[x, y]
        b_ne = corner_brightness[x + 1, y]
        b_sw = corner_brightness[x, y + 1]
        b_se = corner_brightness[x + 1, y + 1]

        ao_nw = ao_ne = ao_sw = ao_se = 1.0
        if corner_ao:
            ao_nw = corner_ao[x][y]
            ao_ne = corner_ao[x + 1][y]
            ao_sw = corner_ao[x][y + 1]
            ao_se = corner_ao[x + 1][y + 1]

        for ix in range(subdiv):
            for iy in range(subdiv):
                fx = (ix + 0.5) / subdiv
                fy = (iy + 0.5) / subdiv
                b_top = b_nw * (1 - fx) + b_ne * fx
                b_bot = b_sw * (1 - fx) + b_se * fx
                b = b_top * (1 - fy) + b_bot * fy
                ao_top = ao_nw * (1 - fx) + ao_ne * fx
                ao_bot = ao_sw * (1 - fx) + ao_se * fx
                ao = ao_top * (1 - fy) + ao_bot * fy

                # Multiply sprite pixels by base_color * brightness * AO
                # (same tint math the on-screen overlay previously used)
                r = max(0, min(255, int(base_color[0] * b * ao)))
                g = max(0, min(255, int(base_color[1] * b * ao)))
                bb = max(0, min(255, int(base_color[2] * b * ao)))
                sub_rect = pygame.Rect(
                    int(ix * sw), int(iy * sh),
                    max(1, int(sw) + 1), max(1, int(sh) + 1),
                )
                sprite.fill((r, g, bb), rect=sub_rect,
                            special_flags=pygame.BLEND_RGBA_MULT)

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
