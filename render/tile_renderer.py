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
    Z_SCALE, TERRAIN_HEIGHT_SCALE, FOG_CULL_DISTANCE, FOG_COLOR, TILE_SUBDIVISIONS, SHADING_STRENGTH,
    fog_alpha_for_distance,
)
from render.gouraud import fill_triangle
from render.quad_warp import warp_sprite_to_quad
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
        lod_fallback_dist = FOG_CULL_DISTANCE * 0.8
        use_lod = False
        if lighting is not None and lighting.preset_config.get("terrain_lod", True):
            use_lod = True

        # Terrain subdivision from preset (for textured mode)
        terrain_subdiv = TILE_SUBDIVISIONS
        terrain_warp = True
        biome_blend = True
        if lighting is not None:
            terrain_subdiv = lighting.preset_config.get("terrain_subdiv", TILE_SUBDIVISIONS)
            terrain_warp = lighting.preset_config.get("terrain_warp", True)
            biome_blend = lighting.preset_config.get("biome_blend", True)

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

        # Render a margin beyond the projected view rect: elevated tiles shift
        # upward on screen and rotated sprites extend past their axis-aligned
        # footprint, so without a margin the window edges show bare sky.
        edge_margin_tiles = 2
        x_min = max(0, int(left // tile_size) - edge_margin_tiles)
        x_max = min(tile_map.width, int(right // tile_size) + 1 + edge_margin_tiles)
        y_min = max(0, int(top // tile_size) - edge_margin_tiles)
        y_max = min(tile_map.height, int(bottom // tile_size) + 1 + edge_margin_tiles)

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
                tile_fog_alpha[(x, y)] = fog_alpha_for_distance(dist)  # -1 = culled
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
                    terrain_warp,
                    biome_blend,
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
        p_nw = camera.world_to_screen(x * tile_size, y * tile_size, elevation=h_nw * Z_SCALE * TERRAIN_HEIGHT_SCALE)
        p_ne = camera.world_to_screen((x + 1) * tile_size, y * tile_size, elevation=h_ne * Z_SCALE * TERRAIN_HEIGHT_SCALE)
        p_se = camera.world_to_screen((x + 1) * tile_size, (y + 1) * tile_size, elevation=h_se * Z_SCALE * TERRAIN_HEIGHT_SCALE)
        p_sw = camera.world_to_screen(x * tile_size, (y + 1) * tile_size, elevation=h_sw * Z_SCALE * TERRAIN_HEIGHT_SCALE)

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

        # Subtle wireframe highlight. pygame.draw ignores the color's alpha
        # on surfaces without per-pixel alpha, so draw onto an overlay.
        if fog_alpha < 200:
            highlight_alpha = max(0, 32 - fog_alpha)
            if highlight_alpha > 0:
                xs = [p_nw[0], p_ne[0], p_se[0], p_sw[0]]
                ys = [p_nw[1], p_ne[1], p_se[1], p_sw[1]]
                ow = int(max(xs) - min(xs)) + 2
                oh = int(max(ys) - min(ys)) + 2
                if ow > 0 and oh > 0:
                    overlay = pygame.Surface((ow, oh), pygame.SRCALPHA)
                    pts = [(px - min(xs), py - min(ys)) for px, py in (p_nw, p_ne, p_se, p_sw)]
                    pygame.draw.polygon(overlay, (0, 0, 0, highlight_alpha), pts, 1)
                    self.screen.blit(overlay, (min(xs), min(ys)))

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
        terrain_warp: bool = True,
        biome_blend: bool = True,
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
                camera.world_to_screen(x * tile_size, y * tile_size, elevation=h_nw * Z_SCALE * TERRAIN_HEIGHT_SCALE),
                camera.world_to_screen((x + 1) * tile_size, y * tile_size, elevation=h_ne * Z_SCALE * TERRAIN_HEIGHT_SCALE),
                camera.world_to_screen((x + 1) * tile_size, (y + 1) * tile_size, elevation=h_se * Z_SCALE * TERRAIN_HEIGHT_SCALE),
                camera.world_to_screen(x * tile_size, (y + 1) * tile_size, elevation=h_sw * Z_SCALE * TERRAIN_HEIGHT_SCALE),
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

        # Biome boundary blending: gather all 8 neighbours' terrain colors
        # (seasonally tinted, like this tile) so the sprite can fade
        # toward them as a smooth radial gradient. Same-biome or missing
        # neighbours record this tile's own colour, so the blend field is
        # symmetric: the "other biome" share of a pixel is exactly how far
        # the pixel's influence region dips into a differing neighbour,
        # which crosses the tile edge and dissolves the square border.
        blend_colors = None
        blend_biomes = None
        if biome_blend:
            this_biome_id = tile.biome.id if tile.biome else "forest"
            edges = {
                "N":  (x, y - 1),  "S":  (x, y + 1),
                "W":  (x - 1, y),  "E":  (x + 1, y),
                "NW": (x - 1, y - 1), "NE": (x + 1, y - 1),
                "SW": (x - 1, y + 1), "SE": (x + 1, y + 1),
            }
            differs = False
            colors: dict[str, tuple[int, int, int]] = {}
            biomes: dict[str, str] = {}
            for dname, (nx, ny) in edges.items():
                ntile = self.tile_map.get_tile(nx, ny)
                if (ntile is None
                        or (ntile.biome.id if ntile.biome else "forest") == this_biome_id):
                    colors[dname] = tuple(int(c) for c in base_color)
                    continue
                nbiome_id = ntile.biome.id if ntile.biome else "forest"
                ncolor = ntile.terrain_color
                if not isinstance(ncolor, (tuple, list)) or len(ncolor) != 3:
                    colors[dname] = tuple(int(c) for c in base_color)
                    continue
                if self.seasonal_renderer is not None:
                    ncolor = self.seasonal_renderer.get_tile_color(nbiome_id, ncolor)
                ncolor = tuple(int(c) for c in ncolor)
                if ncolor != tuple(int(c) for c in base_color):
                    differs = True
                colors[dname] = ncolor
                biomes[dname] = nbiome_id
            if differs:
                blend_colors = colors
                blend_biomes = biomes

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
                tuple(sorted(blend_colors.items())) if blend_colors else None,
            )
        else:
            shade_key = (
                None,
                tuple(sorted(blend_colors.items())) if blend_colors else None,
            )

        # Elevation-displaced corner quad: warping the sprite onto this
        # quad makes the terrain surface visibly drape over the
        # heightfield instead of floating as flat, undistorted sprites.
        h_nw = self.tile_map.get_corner_height(x, y)
        h_ne = self.tile_map.get_corner_height(x + 1, y)
        h_se = self.tile_map.get_corner_height(x + 1, y + 1)
        h_sw = self.tile_map.get_corner_height(x, y + 1)
        p_nw = p_ne = p_se = p_sw = None
        height_key = None
        if terrain_warp:
            p_nw = camera.world_to_screen(x * tile_size, y * tile_size, elevation=h_nw * Z_SCALE * TERRAIN_HEIGHT_SCALE)
            p_ne = camera.world_to_screen((x + 1) * tile_size, y * tile_size, elevation=h_ne * Z_SCALE * TERRAIN_HEIGHT_SCALE)
            p_se = camera.world_to_screen((x + 1) * tile_size, (y + 1) * tile_size, elevation=h_se * Z_SCALE * TERRAIN_HEIGHT_SCALE)
            p_sw = camera.world_to_screen(x * tile_size, (y + 1) * tile_size, elevation=h_sw * Z_SCALE * TERRAIN_HEIGHT_SCALE)
            # Quarter-level quantization so smooth camera motion doesn't
            # thrash the cache; heights change only when the world does.
            height_key = (int(h_nw * 4), int(h_ne * 4), int(h_sw * 4), int(h_se * 4))

        tkey = (
            x, y, biome_name, shade_key, height_key,
            int(yaw * 720), int(zoom * 200), int(pitch_factor * 500),
        )
        cached = self._xform_cache.get(tkey)
        if cached is None:
            sprite = terrain_sprite
            # First crossfade neighbouring biome textures across tile
            # borders (splatting), then bake per-corner brightness/AO as
            # sub-tile multiplicative shading using the per-pixel blended
            # colour field so the light multiply stays hue-correct at
            # borders.
            if corner_brightness is not None or blend_colors:
                sprite = terrain_sprite.copy()
                color_field = None
                if blend_colors:
                    blend_sprites = {
                        d: self._load_terrain_sprite(biome_id)
                        for d, biome_id in (blend_biomes or {}).items()
                    }
                    color_field = self._bake_biome_blending(
                        sprite, tuple(base_color), blend_colors, blend_sprites,
                    )
                if corner_brightness is not None:
                    self._bake_subtile_shading(
                        sprite, x, y, base_color,
                        corner_brightness, corner_ao, terrain_subdiv,
                        color_field,
                    )

            # Rotate by yaw, then squash vertically by tan(pitch)
            cos_y = math.cos(yaw)
            sin_y = math.sin(yaw)
            axis_aligned = abs(sin_y) < 0.01 and cos_y > 0
            if p_nw is not None:
                # Warp mode: the quad is already yaw-rotated in screen
                # space, so the source must stay un-rotated — strip rows
                # are parameterized along the tile's local axes, not the
                # rotated diamond's. Neighbouring tiles share corner
                # heights exactly, so no +4 margin is needed.
                scaled_w = max(1, int(round(sprite.get_width() * zoom)))
                scaled_h = max(1, int(round(sprite.get_height() * zoom * pitch_factor)))
                sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
            elif axis_aligned:
                scaled_w = max(1, int(round(sprite.get_width() * zoom)) + 4)
                scaled_h = max(1, int(round(sprite.get_height() * zoom * pitch_factor)) + 4)
                sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
            else:
                # Camera yaw maps world +X to the right/down (clockwise on
                # screen), and pygame rotates counterclockwise-positive, so
                # the angle is negated.
                rotated = pygame.transform.rotate(sprite, -math.degrees(yaw))
                bbox = sprite.get_width() * (abs(cos_y) + abs(sin_y))
                # +4 px: tiles are painted back-to-front, so the front tile's
                # solid interior covers the anti-aliased fringe of its
                # neighbours instead of letting the background bleed through.
                # Neighbouring tiles also shift vertically by their elevation
                # difference, so the overdraw must exceed that shift.
                scaled_w = max(1, int(round(bbox * zoom)) + 4)
                scaled_h = max(1, int(round(bbox * zoom * pitch_factor)) + 4)
                sprite = pygame.transform.smoothscale(rotated, (scaled_w, scaled_h))

            base_w, base_h = sprite.get_size()
            dx = dy = 0
            if p_nw is not None:
                warped = warp_sprite_to_quad(sprite, p_nw, p_ne, p_se, p_sw)
                if warped is not None:
                    sprite, wx, wy = warped
                    # Blit delta is stored relative to where the flat blit
                    # would have gone, so camera panning (a pure screen
                    # translation) keeps the cache valid.
                    tile_center_x = x * 64 + 32
                    tile_center_y = y * 64 + 32
                    avg_height = self.tile_map.get_tile_center_height(x, y)
                    cx, cy = camera.world_to_screen(
                        tile_center_x, tile_center_y,
                        elevation=avg_height * Z_SCALE * TERRAIN_HEIGHT_SCALE,
                    )
                    flat_x = int(cx) - base_w // 2
                    flat_y = int(cy) - base_h // 2
                    dx, dy = wx - flat_x, wy - flat_y

            if len(self._xform_cache) > 4096:
                self._xform_cache.clear()
            cached = (sprite, base_w, base_h, dx, dy)
            self._xform_cache[tkey] = cached

        sprite, base_w, base_h, dx, dy = cached

        # Draw centered on the projected tile center, plus the warp delta.
        tile_center_x = x * 64 + 32
        tile_center_y = y * 64 + 32
        avg_height = self.tile_map.get_tile_center_height(x, y)
        screen_x, screen_y = camera.world_to_screen(
            tile_center_x, tile_center_y, elevation=avg_height * Z_SCALE * TERRAIN_HEIGHT_SCALE,
        )
        rect = pygame.Rect(
            int(screen_x) - base_w // 2 + dx,
            int(screen_y) - base_h // 2 + dy,
            sprite.get_width(),
            sprite.get_height(),
        )
        # Fog is composited into a copy so (a) it follows the warped
        # sprite's opaque silhouette instead of an AABB diamond and
        # (b) player motion doesn't invalidate the transform cache.
        # Height-fog already modulated ``fog_alpha`` in ``render()``.
        if fog_alpha > 0:
            sprite = self._composite_sprite_fog(sprite, fog_alpha, fog_color)
        self.screen.blit(sprite, rect)

    def _bake_subtile_shading(
        self,
        sprite: pygame.Surface,
        x: int, y: int,
        base_color: tuple[int, int, int],
        corner_brightness: "np.ndarray",
        corner_ao: list[list[float]] | None,
        terrain_subdiv: int,
        color_field: "np.ndarray | None" = None,
    ) -> None:
        """Multiply per-corner shading into the tile sprite per pixel.

        Bilinear interpolation is evaluated on the full pixel grid (not a
        coarse sub-tile fill), so shading is continuous inside a tile AND
        across tile borders — corners are shared between neighbours.

        When ``color_field`` ((w, h, 3) float array) is provided — the
        blended biome colour output of the splat pass — it replaces the
        scalar ``base_color`` so border pixels are tinted by their local
        biome mixture rather than this tile's biome colour.
        """
        import numpy as np

        w, h = sprite.get_size()

        b_nw = float(corner_brightness[x, y])
        b_ne = float(corner_brightness[x + 1, y])
        b_sw = float(corner_brightness[x, y + 1])
        b_se = float(corner_brightness[x + 1, y + 1])

        ao_nw = ao_ne = ao_sw = ao_se = 1.0
        if corner_ao:
            ao_nw = corner_ao[x][y]
            ao_ne = corner_ao[x + 1][y]
            ao_sw = corner_ao[x][y + 1]
            ao_se = corner_ao[x + 1][y + 1]

        # fx/fy per pixel, sampled at pixel centers: (w,) and (h,) vectors.
        fx = (np.arange(w) + 0.5) / w
        fy = (np.arange(h) + 0.5) / h
        # Bilinear on the (w, h) grid: shade[i, j] at fx[i], fy[j].
        b_top = b_nw * (1 - fx) + b_ne * fx
        b_bot = b_sw * (1 - fx) + b_se * fx
        ao_top = ao_nw * (1 - fx) + ao_ne * fx
        ao_bot = ao_sw * (1 - fx) + ao_se * fx
        b = b_top[:, None] * (1 - fy)[None, :] + b_bot[:, None] * fy[None, :]
        ao = ao_top[:, None] * (1 - fy)[None, :] + ao_bot[:, None] * fy[None, :]

        shade_light = (b * ao)[..., None]  # (w, h, 1)
        if color_field is not None:
            base = color_field
        else:
            base = np.asarray(base_color, dtype=np.float32)[None, None, :]
        color = np.clip(base * shade_light, 0, 255).astype(np.uint8)
        shade = pygame.Surface((w, h))
        pygame.surfarray.blit_array(shade, color)
        # RGB-only multiply so terrain alpha (sprite silhouette) is untouched.
        sprite.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def _composite_sprite_fog(
        self,
        sprite: pygame.Surface,
        alpha: int,
        color: tuple[int, int, int],
    ) -> pygame.Surface:
        """Composite distance fog into a sprite's opaque pixels.

        Transparent pixels stay transparent, so fog cannot miss a sheared
        tile or stack over a neighbour through the AABB. ``alpha`` is the
        already-modulated (distance × height) value from ``render()``.
        Returns ``sprite`` unchanged when alpha is 0; otherwise a copy.
        """
        if alpha <= 0:
            return sprite
        import numpy as np

        alpha = max(0, min(255, int(alpha)))
        out = sprite.copy()
        fog = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        fog.fill((*color, alpha))
        mask = pygame.surfarray.array_alpha(sprite)
        fog_a = pygame.surfarray.pixels_alpha(fog)
        fog_a[:, :] = (mask.astype(np.uint16) * alpha // 255).astype(np.uint8)
        del fog_a
        out.blit(fog, (0, 0))
        return out

    # Tile-space centres of the 8 neighbours relative to this tile.
    _NEIGHBOUR_CENTRES = {
        "N": (0.5, -0.5), "S": (0.5, 1.5),
        "W": (-0.5, 0.5), "E": (1.5, 0.5),
        "NW": (-0.5, -0.5), "NE": (1.5, -0.5),
        "SW": (-0.5, 1.5), "SE": (1.5, 1.5),
    }

    def _bake_biome_blending(
        self,
        sprite: pygame.Surface,
        own_color: tuple[int, int, int],
        blend_colors: dict[str, tuple[int, int, int]],
        blend_sprites: "dict[str, pygame.Surface | None] | None" = None,
    ) -> "np.ndarray | None":
        """Crossfade neighbouring biomes' textures across tile borders.

        Each pixel is the bilinear-tent mix of the 3×3 neighbourhood:
        a tile at centre ``(cx, cy)`` contributes
        ``max(0, 1-|dx|)·max(0, 1-|dy|)``. That is 50/50 at a shared
        edge (matched by the neighbour's mirrored bake), 25% each at a
        four-biome corner, and 100% this tile at the centre — so the
        square grid dissolves without tinting interiors. Each
        contributing tile supplies its own sprite, sampled at the same
        local UV (terrain sprites tile). Same-biome neighbours reuse
        this tile's texture rather than a flat fill, so the orthogonal
        edge opposite a biome change does not wash out.

        ``blend_colors`` must contain all 8 direction keys; directions
        whose neighbour shares this tile's biome (or is missing) carry
        ``own_color``. ``blend_sprites`` maps differing directions to
        the neighbour biome's raw terrain sprite; missing sprites fall
        back to the flat ``blend_colors`` entry. RGB-only; sprite alpha
        is preserved.

        Returns the per-pixel blended biome colour field ((w, h, 3)
        float array) for the shading pass, so border pixels are tinted by
        their local biome mixture rather than this tile's biome colour.
        Returns None when there is nothing to blend.
        """
        import numpy as np

        if not blend_colors:
            return None

        own_rgb = np.asarray(own_color, dtype=np.float32)
        if all(np.array_equal(np.asarray(c, dtype=np.float32), own_rgb)
               for c in blend_colors.values()):
            return None

        w, h = sprite.get_size()
        if w == 0 or h == 0:
            return None

        # Pixel-centre positions in tile units: x ∈ [0, 1] across the
        # tile, so own-centre is (0.5, 0.5) and neighbours sit one tile
        # away.
        fx = (np.arange(w) + 0.5) / w  # (w,)
        fy = (np.arange(h) + 0.5) / h  # (h,)
        fx_col = fx[:, None]          # (w, 1)
        fy_row = fy[None, :]          # (1, h)

        def tent_at(cx: float, cy: float) -> np.ndarray:
            wx = np.maximum(0.0, 1.0 - np.abs(fx_col - cx))
            wy = np.maximum(0.0, 1.0 - np.abs(fy_row - cy))
            return wx * wy

        own_field = tent_at(0.5, 0.5)                   # (w, h)
        total = own_field
        weighted_color = own_field[..., None] * own_rgb

        pixels = pygame.surfarray.array3d(sprite).astype(np.float32)
        acc = own_field[..., None] * pixels

        for dname, (cx, cy) in self._NEIGHBOUR_CENTRES.items():
            color = blend_colors.get(dname)
            if color is None:
                continue
            f = tent_at(cx, cy)
            total = total + f
            color_arr = np.asarray(color, dtype=np.float32)
            weighted_color = weighted_color + f[..., None] * color_arr
            nb_sprite = (blend_sprites or {}).get(dname)
            nb_pixels = None
            if nb_sprite is not None and nb_sprite.get_size() == (w, h):
                nb_pixels = pygame.surfarray.array3d(nb_sprite).astype(np.float32)
            if nb_pixels is None:
                # Same-biome (or missing) neighbours keep this tile's
                # texture so the opposite edge does not flatten.
                if np.allclose(color_arr, own_rgb):
                    nb_pixels = pixels
                else:
                    nb_pixels = np.broadcast_to(color_arr, (w, h, 3)).copy()
            acc = acc + f[..., None] * nb_pixels

        total = np.maximum(total[..., None], 1e-6)      # (w, h, 1)

        # Write back RGB through the view so sprite alpha is preserved.
        view = pygame.surfarray.pixels3d(sprite)
        view[...] = np.clip(acc / total, 0, 255).astype(np.uint8)
        del view

        return weighted_color / total                   # (w, h, 3)

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
