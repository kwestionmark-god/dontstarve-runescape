"""
render/lighting_system.py — Central lighting coordinator for Phase 6.

Provides:
- NumPy-accelerated AO bake (once at world-gen)
- NumPy fog density precompute (once at world-gen)
- NumPy per-tile shading computation (once at world-gen or frame update)
- Per-frame lighting params (sun dir, ambient, colors) from SeasonSystem
- Preset-aware feature toggles
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from config import (
    AO_STRENGTH, AO_BLUR_RADIUS, FOG_SCALE_HEIGHT,
    SHADING_PRESETS, DEFAULT_SHADING_PRESET,
    ELEVATION_LEVELS,
)

if TYPE_CHECKING:
    from world.tile_map import TileMap
    from seasons.season_system import SeasonSystem
    from seasons.weather_system import WeatherSystem
    from camera.camera import Camera


class LightingSystem:
    """
    Central lighting state. Owned by Game, updated each frame from SeasonSystem
    and WeatherSystem, consumed by TileRenderer and SpriteRenderer.
    """
    
    __slots__ = (
        "preset", "preset_config",
        "sun_direction", "sun_altitude",
        "ambient_color", "ambient_level",
        "sun_color", "fog_tint",
        "weather_light_level", "cloud_coverage", "lightning_chance",
        "_ao_baked", "_fog_precomputed",
        "weather_system",  # Wired in bootstrap for seasonal lighting updates
    )
    
    def __init__(self, preset: str = DEFAULT_SHADING_PRESET) -> None:
        self.preset = preset
        self.preset_config = SHADING_PRESETS[preset].copy()
        
        # Runtime lighting state (updated per frame)
        self.sun_direction = (0.0, -1.0, 0.0)  # Default NW
        self.sun_altitude = 0.0
        self.ambient_color = (200, 200, 200)
        self.ambient_level = 1.0
        self.sun_color = (255, 255, 255)
        self.fog_tint = (135, 206, 235)
        self.weather_light_level = 1.0
        self.cloud_coverage = 0.0
        self.lightning_chance = 0.0
        self.weather_system: WeatherSystem | None = None
        
        # Cached precomputes
        self._ao_baked = False
        self._fog_precomputed = False
    
    def set_preset(self, preset: str) -> None:
        """Change shading preset at runtime."""
        self.preset = preset
        self.preset_config = SHADING_PRESETS[preset].copy()
    
    def update_from_season(self, season_system: SeasonSystem) -> None:
        """Call once per frame from Game.update()."""
        lp = season_system.get_lighting_params()
        self.sun_direction = lp["sun_direction"]
        self.sun_altitude = lp["sun_altitude"]
        self.ambient_color = lp["ambient_color"]
        self.ambient_level = lp["ambient_level"]
        self.sun_color = lp["sun_color"]
        self.fog_tint = lp["fog_tint"]
    
    def update_from_weather(self, weather_system: WeatherSystem) -> None:
        """Call once per frame from Game.update()."""
        effects = weather_system.get_effects()
        self.weather_light_level = effects.get("light_level", 1.0)
        self.cloud_coverage = effects.get("cloud_coverage", 0.0)
        self.lightning_chance = effects.get("lightning_chance", 0.0)
    
    def get_tile_brightness(self, base_brightness: float, slope_mag: float) -> float:
        """Combine slope shading + ambient + weather."""
        # Apply ambient level (night = darker even on lit slopes)
        b = base_brightness * self.ambient_level
        # Apply weather light level
        b *= self.weather_light_level
        return b
    
    def get_sun_direction_2d(self) -> tuple[float, float]:
        """Return (x, y) for tile_map.compute_slope_shading."""
        return (self.sun_direction[0], self.sun_direction[1])
    
    def get_rim_view_z(self, camera: Camera) -> float:
        """View vector Z component in world space (after yaw)."""
        return -math.sin(camera.pitch)
    
    # ─── Precomputes (world-gen only) ────────────────────────────────
    
    def bake_ambient_occlusion(self, tile_map: TileMap) -> None:
        """
        Pre-compute per-corner AO factor [0.0, 1.0] using the 12-tile kernel.
        1.0 = no occlusion (convex), <1.0 = occluded (concave).
        """
        if self._ao_baked:
            return
        
        w, h = tile_map.width, tile_map.height
        self.corner_ao = np.ones((w + 1, h + 1), dtype=np.float32)
        
        # 12-tile kernel matching get_corner_height in tile_map.py
        kernel_dx = np.array([-1, 0, -1, 0, -2, 1, 2, -1, -2, 2, 2, -2], dtype=np.int32)
        kernel_dy = np.array([-1, -1, 0, 0, -1, -2, 1, 2, -2, -2, 2, 2], dtype=np.int32)
        kernel_w = np.array([4.0, 4.0, 4.0, 4.0, 1.0, 1.0, 1.0, 1.0, 0.25, 0.25, 0.25, 0.25], dtype=np.float32)
        
        # Convert elevation to numpy for fast indexing
        elev = np.zeros((w, h), dtype=np.int32)
        for x in range(w):
            for y in range(h):
                elev[x, y] = tile_map.tiles[x][y].elevation
        
        # First pass: compute raw AO
        corner_ao_raw = np.ones((w + 1, h + 1), dtype=np.float32)
        for cx in range(w + 1):
            for cy in range(h + 1):
                # Reference elevation = average of 4 corner tiles
                ref_elev = 0.0
                ref_count = 0
                for dx, dy in [(-1, -1), (0, -1), (-1, 0), (0, 0)]:
                    tx, ty = cx + dx, cy + dy
                    if 0 <= tx < w and 0 <= ty < h:
                        ref_elev += elev[tx, ty]
                        ref_count += 1
                if ref_count > 0:
                    ref_elev /= ref_count
                
                concave_weight = 0.0
                total_weight = 0.0
                for k in range(12):
                    nx, ny = cx + kernel_dx[k], cy + kernel_dy[k]
                    if 0 <= nx < w and 0 <= ny < h:
                        total_weight += kernel_w[k]
                        if elev[nx, ny] > ref_elev:
                            delta = float(elev[nx, ny] - ref_elev)
                            concave_weight += kernel_w[k] * min(1.0, delta / 2.0)
                
                if total_weight > 0:
                    occlusion = concave_weight / total_weight
                    corner_ao_raw[cx, cy] = max(0.0, 1.0 - occlusion * AO_STRENGTH)
                else:
                    corner_ao_raw[cx, cy] = 1.0
        
        # Blur pass
        if AO_BLUR_RADIUS > 0:
            blurred = np.ones((w + 1, h + 1), dtype=np.float32)
            for cx in range(w + 1):
                for cy in range(h + 1):
                    s = 0.0
                    c = 0
                    for dx in range(-AO_BLUR_RADIUS, AO_BLUR_RADIUS + 1):
                        for dy in range(-AO_BLUR_RADIUS, AO_BLUR_RADIUS + 1):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx <= w and 0 <= ny <= h:
                                s += corner_ao_raw[nx, ny]
                                c += 1
                    blurred[cx, cy] = s / c if c > 0 else 1.0
            corner_ao_raw = blurred
        
        # Convert to list-of-lists for TileMap (list indexing is natural)
        tile_map.corner_ao = corner_ao_raw.tolist()
        self._ao_baked = True
    
    def precompute_fog_density(self, tile_map: TileMap) -> None:
        """Precompute exp(-elev / scale) per tile using NumPy."""
        if self._fog_precomputed:
            return
        
        w, h = tile_map.width, tile_map.height
        elev = np.zeros((w, h), dtype=np.float32)
        for x in range(w):
            for y in range(h):
                elev[x, y] = tile_map.tiles[x][y].elevation
        
        fog_density = np.exp(-elev / FOG_SCALE_HEIGHT)
        
        # Store on tiles for fast per-tile lookup
        for x in range(w):
            for y in range(h):
                tile_map.tiles[x][y].fog_density = float(fog_density[x, y])
        
        self._fog_precomputed = True
    
    def compute_all_shading(
        self, tile_map: TileMap,
        light_x: float, light_y: float, light_z: float
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Vectorized shading for all tiles using NumPy.
        Returns (brightness_grid, slope_mag_grid) as numpy arrays.
        """
        if not self.preset_config.get("multi_light", False):
            return None, None
        
        w, h = tile_map.width, tile_map.height
        elev = np.zeros((w, h), dtype=np.float32)
        for x in range(w):
            for y in range(h):
                elev[x, y] = tile_map.tiles[x][y].elevation
        
        # Compute gradients with numpy vectorization
        nw = elev
        ne = np.roll(elev, -1, axis=0)
        sw = np.roll(elev, -1, axis=1)
        se = np.roll(elev, (-1, -1), axis=(0, 1))
        
        # Handle boundary cases for edge tiles
        nw[0, :] = elev[0, :]
        nw[:, 0] = elev[:, 0]
        ne[w-1, :] = elev[w-1, :]
        ne[:, 0] = elev[:, 0]
        sw[0, :] = elev[0, :]
        sw[:, h-1] = elev[:, h-1]
        se[w-1, :] = elev[w-1, :]
        se[:, h-1] = elev[:, h-1]
        
        grad_x = (ne + se - nw - sw) / 2.0
        grad_y = (sw + se - nw - ne) / 2.0
        
        slope_mag = np.sqrt(grad_x * grad_x + grad_y * grad_y)
        slope_mag = np.minimum(slope_mag / 2.0, 1.0)
        
        light_dot = light_x * grad_x + light_y * grad_y
        brightness = 1.0 + np.clip(light_dot * 0.20 * 2.0, -0.20, 0.20)
        
        return brightness.astype(np.float32), slope_mag.astype(np.float32)


# ─── Module-level helpers ────────────────────────────────────────────


def compute_sun_direction(time_of_day: float, azimuth_deg: float = 45.0,
                          alt_min: float = -30.0, alt_max: float = 30.0) -> tuple[tuple[float, float, float], float]:
    """
    Compute 3D sun direction and altitude from time_of_day [0, 1).
    Returns (sun_dir_xyz, sun_altitude_rad).
    """
    t = time_of_day
    # Altitude: -30° at midnight (0), 0° at sunrise (0.25), +30° at noon (0.5),
    # 0° at sunset (0.75), -30° at midnight (1.0)
    if t < 0.25:
        sun_alt_deg = alt_min + (alt_max - alt_min) * (t / 0.25)
    elif t < 0.5:
        sun_alt_deg = (alt_max - alt_min) * ((t - 0.25) / 0.25)
    elif t < 0.75:
        sun_alt_deg = (alt_max - alt_min) * (1.0 - (t - 0.5) / 0.25)
    else:
        sun_alt_deg = alt_min * ((t - 0.75) / 0.25)
    
    sun_alt = math.radians(sun_alt_deg)
    azimuth = math.radians(azimuth_deg)
    
    sun_dir = (
        math.cos(sun_alt) * math.sin(azimuth),
        math.cos(sun_alt) * math.cos(azimuth),
        math.sin(sun_alt),
    )
    return sun_dir, sun_alt


def compute_ambient_level(time_of_day: float,
                          night_level: float = 0.15, day_level: float = 0.45) -> float:
    """Smooth ambient lerp with dawn/dusk transitions."""
    t = time_of_day
    # Day fraction: 1.0 at noon, 0.0 at midnight, smooth transitions
    if 0.125 <= t <= 0.375:
        day_frac = (t - 0.125) / 0.25
    elif 0.625 <= t <= 0.875:
        day_frac = 1.0 - (t - 0.625) / 0.25
    elif 0.25 < t < 0.625:
        day_frac = 1.0
    else:
        day_frac = 0.0
    return night_level + day_frac * (day_level - night_level)