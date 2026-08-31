# Phase 6: Advanced Shading & Lighting — Implementation Plan

**Date:** 2026-08-30  
**Author:** Grok  
**Status:** Planning Complete — Ready for Implementation  
**Scope:** All 7 tasks (6.1–6.7), balanced quality/performance

---

## Summary

| Task | Description | Primary Files | Effort |
|------|-------------|---------------|--------|
| 6.1 | Multi-directional lighting + time-of-day + ambient sky | `tile_map.py`, `tile_renderer.py`, `seasonal_renderer.py`, `config/constants.py`, `seasons/season_system.py` | M |
| 6.2 | Ambient occlusion (SSAO-style, pre-baked per-corner) | `world/tile_map.py`, `render/tile_renderer.py` | L |
| 6.3 | Rim lighting / fresnel | `render/tile_renderer.py`, `camera/camera.py` | S |
| 6.4 | Seasonal lighting variation | `seasons/season_system.py`, `render/seasonal_renderer.py`, `tile_renderer.py` | M |
| 6.5 | Volumetric fog (elevation-based) | `render/tile_renderer.py`, `render/sprite_renderer.py`, `world/tile_map.py`, `config/constants.py` | M |
| 6.6 | Dynamic weather lighting | `seasons/weather_system.py`, `render/tile_renderer.py`, `render/sprite_renderer.py`, `render/particle_system.py` | M |
| 6.7 | Configurable shading presets | `config/constants.py`, `core/game.py`, `core/bootstrap.py`, `render/tile_renderer.py`, `render/sprite_renderer.py`, `render/particle_system.py` | S |

**Total estimated effort:** ~10-12 focused sessions

---

## Shared Design Decisions

### 1. Time-of-day model (6.1, 6.4)
- Add `time_of_day: float` to `SeasonSystem` in `[0.0, 1.0)` where `0.0 = midnight`, `0.25 = sunrise`, `0.5 = noon`, `0.75 = sunset`. Progress via `tick(dt)` using `DAY_DURATION_SECONDS = 1200.0` (20 min day, 10 min night).
- Sun angle (radians from horizontal) = `lerp(sunrise_angle, sunset_angle, time_of_day)` with `sunrise_angle = math.radians(-30)`, `sunset_angle = math.radians(30)`. At night, sun is below horizon (negative angle).
- `LIGHT_DIRECTION` becomes a computed 3D vector from sun azimuth + altitude. Replaces the hardcoded `(-1, -1)` in `tile_map.py:302-303`.

### 2. Ambient occlusion model (6.2)
- Pre-bake **per-corner AO factor** into `TileMap` at world-gen time (one-time `O(width * height * 12)`).
- Use the existing 12-tile kernel from `get_corner_height` (lines 209-215). For each corner, AO = `1.0 - (concave_weight / total_weight)` where `concave_weight` = sum of weights from neighbors **higher** than the corner's 2x2 average.
- Store as `tile_map.corner_ao: list[list[float]]` (size `(width+1) x (height+1)`). Interpolate 4 corners per tile at render time.
- Apply AO as a multiplicative `BLEND_RGBA_MULT` overlay (same technique as slope shading at lines 177-186 of `tile_renderer.py`).

### 3. Rim/fresnel model (6.3)
- Camera view vector in world space after yaw rotation = `(0, 0, -sin(pitch))`. Surface normal from `grad_x, grad_y` (already computed in `compute_slope_shading`). Rim factor = `1.0 - max(0, dot(normal, view))^k` with `k=3` for sharpness. Apply as additive brightening overlay (separate from AO/slope shading).

### 4. Seasonal lighting params (6.4)
Extend `SeasonSystem` with a per-season **lighting profile** dict:
```python
SEASON_LIGHTING = {
    "spring":  {"ambient": (230, 240, 220), "sun_color": (255, 240, 200), "fog_tint": (180, 210, 190)},
    "summer":  {"ambient": (245, 235, 210), "sun_color": (255, 245, 220), "fog_tint": (200, 190, 160)},
    "autumn":  {"ambient": (235, 220, 190), "sun_color": (255, 200, 140), "fog_tint": (180, 160, 130)},
    "winter":  {"ambient": (200, 220, 240), "sun_color": (220, 235, 255), "fog_tint": (160, 180, 200)},
}
```
`ambient` drives `SeasonalRenderer.draw_ambient_overlay` color/alpha. `sun_color` multiplies directional light. `fog_tint` replaces `FOG_COLOR` dynamically.

### 5. Volumetric fog (6.5)
- Fog density = `base_density * exp(-elevation / scale_height)` with `scale_height ≈ 8.0` (tiles). So valleys (low elevation) get denser fog.
- Replace per-tile uniform fog overlay with a **4-corner gradient** in the polygon branch (and sprite branch via per-vertex alpha if we promote to a shader-like approach; for pygame-ce, render 4 triangles with interpolated alpha).
- Height fog planes: add `FOG_HEIGHT_PLANES = [(height, color, density_mult)]` to config — optional for atmosphere layers.

### 6. Weather lighting (6.6)
- Extend `WeatherSystem.get_effects()` to include `light_level`, `cloud_coverage`, `rain_intensity`, `lightning_chance`.
- `lightning_chance` triggers a global screen flash (white overlay with `alpha=180` for 50ms) in `render_game` between particles and HUD.
- Cloud shadows: add a low-frequency noise mask (Perlin) for shadow strips that scroll with wind. Cheap — one 1-bit mask per frame, BLEND_RGBA_MULT over tiles.

### 7. Shading presets (6.7)
Three tiers controlled by `Game.shading_preset: str`:

| Feature | stylized (default) | realistic | performance |
|---------|-------------------|-----------|-------------|
| Slope shading | ✅ | ✅ | ❌ |
| AO overlay | ❌ | ✅ | ❌ |
| Rim lighting | ❌ | ✅ | ❌ |
| Multi-directional light | ❌ | ✅ | ❌ (fixed NW) |
| Volumetric fog | ❌ | ✅ (full) | ❌ (uniform only) |
| Height fog variation | ❌ | ✅ | ❌ |
| Weather lighting | ❌ | ✅ | ❌ |
| Lightning flash | ❌ | ✅ | ❌ |
| Particle cap | 500 | 500 | 150 |
| Fog cull distance | 1700 | 1700 | 1000 |
| Ambient overlay alpha | 20 | 40 | 0 |
| Sky fill | solid FOG_COLOR | gradient | solid FOG_COLOR |

---

## Detailed Task Plans

---

### 6.1 Multi-directional Lighting + Time-of-Day + Ambient Sky

**Goal:** Replace fixed NW light with configurable sun position driven by time-of-day and season.

#### Files & Changes

**A. `config/constants.py`** — add new constants after line 149 (`FOG_COLOR`):
```python
# ─── Phase 6: Lighting ──────────────────────────────────────────────────

# Time-of-day
DAY_DURATION_SECONDS = 1200.0        # Full day/night cycle (20 min day + night)
SUNRISE_HOUR = 6.0                   # Time-of-day 0.25
SUNSET_HOUR = 18.0                   # Time-of-day 0.75
SUN_ALTITUDE_RANGE = (-30.0, 30.0)   # Degrees: min at midnight, max at noon
SUN_AZIMUTH = 45.0                   # Degrees: from north (0=N, 90=E). Matches current NW light.
NIGHT_AMBIENT_LEVEL = 0.15           # Minimum ambient at night (0–1)
DAY_AMBIENT_LEVEL = 0.45             # Maximum ambient at noon (0–1)

# Ambient occlusion
AO_STRENGTH = 0.35                   # Max AO darkening (0–1)
AO_BLUR_RADIUS = 1                   # Tiles to blur AO across (0=sharp)

# Rim lighting
RIM_STRENGTH = 0.25                  # Max rim brightening (0–1)
RIM_EXPONENT = 3.0                   # Fresnel sharpness

# Height fog
FOG_SCALE_HEIGHT = 8.0               # Elevation scale for density falloff
FOG_HEIGHT_PLANES = []               # Optional: [(height, color, density_mult), ...]

# Weather lighting
CLOUD_SHADOW_STRENGTH = 0.20         # Max cloud shadow darkening
LIGHTNING_FLASH_DURATION_MS = 50     # Screen flash duration
LIGHTNING_FLASH_ALPHA = 180          # 0–255

# Shading presets
SHADING_PRESETS = {
    "stylized": {
        "slope_shading": True,
        "ao": False,
        "rim": False,
        "multi_light": False,
        "volumetric_fog": False,
        "height_fog": False,
        "weather_lighting": False,
        "lightning": False,
        "particle_cap": 500,
        "fog_cull_distance": 1700,
        "ambient_overlay_alpha": 20,
        "sky_mode": "solid",
    },
    "realistic": {
        "slope_shading": True,
        "ao": True,
        "rim": True,
        "multi_light": True,
        "volumetric_fog": True,
        "height_fog": True,
        "weather_lighting": True,
        "lightning": True,
        "particle_cap": 500,
        "fog_cull_distance": 1700,
        "ambient_overlay_alpha": 40,
        "sky_mode": "gradient",
    },
    "performance": {
        "slope_shading": False,
        "ao": False,
        "rim": False,
        "multi_light": False,
        "volumetric_fog": False,
        "height_fog": False,
        "weather_lighting": False,
        "lightning": False,
        "particle_cap": 150,
        "fog_cull_distance": 1000,
        "ambient_overlay_alpha": 0,
        "sky_mode": "solid",
    },
}
DEFAULT_SHADING_PRESET = "stylized"
```

**B. `seasons/season_system.py`** — add time-of-day + lighting profile:
```python
# In __init__ (after line 62):
self.time_of_day: float = 0.5   # Start at noon
self.day_duration: float = DAY_DURATION_SECONDS
self._lighting_profile: dict = SEASON_LIGHTING[self.current_season]

# In tick(dt) (after line 87):
self.time_of_day = (self.time_of_day + dt / self.day_duration) % 1.0

# New method (after get_survival_modifiers):
def get_lighting_params(self) -> dict:
    """Returns {ambient_color, sun_color, fog_tint, sun_direction, sun_altitude, ambient_level} for current season+time."""
    profile = self._lighting_profile
    t = self.time_of_day
    # Sun altitude: -30° at midnight (t=0), 0° at sunrise (0.25), +30° at noon (0.5), 0° at sunset (0.75), -30° at midnight (1.0)
    if t < 0.25:  # Night before dawn
        sun_alt = -30.0 + 60.0 * (t / 0.25)
    elif t < 0.5:  # Morning
        sun_alt = 60.0 * ((t - 0.25) / 0.25)
    elif t < 0.75:  # Afternoon
        sun_alt = 60.0 * (1.0 - (t - 0.5) / 0.25)
    else:  # Evening
        sun_alt = -30.0 * ((t - 0.75) / 0.25)
    sun_alt = math.radians(sun_alt)
    # Ambient lerp between night/day
    day_frac = 1.0 if 0.25 <= t <= 0.75 else 0.0
    # Smooth transitions near sunrise/sunset
    if 0.125 <= t <= 0.375:
        day_frac = (t - 0.125) / 0.25
    elif 0.625 <= t <= 0.875:
        day_frac = 1.0 - (t - 0.625) / 0.25
    ambient_level = NIGHT_AMBIENT_LEVEL + day_frac * (DAY_AMBIENT_LEVEL - NIGHT_AMBIENT_LEVEL)
    # Sun direction vector (3D)
    azimuth = math.radians(SUN_AZIMUTH)
    sun_dir = (
        math.cos(sun_alt) * math.sin(azimuth),
        math.cos(sun_alt) * math.cos(azimuth),
        math.sin(sun_alt),
    )
    return {
        "ambient_color": profile["ambient"],
        "sun_color": profile["sun_color"],
        "fog_tint": profile["fog_tint"],
        "sun_direction": sun_dir,
        "sun_altitude": sun_alt,
        "ambient_level": ambient_level,
    }
```

**C. `world/tile_map.py`** — update `compute_slope_shading` to accept sun direction:
```python
# Add import at top:
from config import LIGHT_DIRECTION, SHADING_STRENGTH  # LIGHT_DIRECTION now deprecated

# Replace compute_slope_shading signature (line 269):
def compute_slope_shading(self, x: int, y: int, light_dir: tuple[float, float, float] | None = None) -> Tuple[float, float]:
    """light_dir: (x, y, z) world-space unit vector. If None, uses fixed NW for backward compat."""
    ...
    # Line 302-303: replace hardcoded (-1, -1) with light_dir
    if light_dir is None:
        # Legacy: screen-space NW (-1, -1) -> world (after yaw=0) is (0, -1)
        light_x, light_y, light_z = 0.0, -1.0, 0.0
    else:
        light_x, light_y, light_z = light_dir
    # Project light into 2D gradient space (elevation gradient is in world X/Y)
    light_dot = (light_x * grad_x) + (light_y * grad_y)
    brightness = 1.0 + max(-SHADING_STRENGTH, min(SHADING_STRENGTH, light_dot * SHADING_STRENGTH * 2.0))
    return (brightness, min(slope_mag / 2.0, 1.0))
```

**D. `render/tile_renderer.py`** — pass sun direction to shading, use ambient level:
```python
# In render() method, after getting tiles_to_render (line 117):
lighting = {}
if hasattr(self, 'lighting_system') and self.lighting_system is not None:
    lighting = self.lighting_system.get_params()  # returns dict from SeasonSystem.get_lighting_params()
    sun_dir = lighting.get("sun_direction")
    ambient_level = lighting.get("ambient_level", 1.0)
else:
    sun_dir = None
    ambient_level = 1.0

# In per-tile loop (replace line 150):
brightness, slope_mag = tile_map.compute_slope_shading(x, y, light_dir=sun_dir)
# Multiply by ambient level (so night is darker even on lit slopes)
brightness = brightness * ambient_level

# Sky fill (line 273 in game.py) — move to tile_renderer or keep in game.py but use lighting["ambient_color"]
```

**E. `render/seasonal_renderer.py`** — use dynamic ambient from lighting:
```python
# In draw_ambient_overlay, replace hardcoded alpha/color:
def draw_ambient_overlay(self, screen, alpha=20, color=(0,0,0)):
    # If lighting_system provides ambient_color, use it
    if self._lighting_ambient_color is not None:
        color = self._lighting_ambient_color
    if self._lighting_ambient_alpha is not None:
        alpha = self._lighting_ambient_alpha
    ...
# Add setters:
def set_lighting_ambient(self, color: tuple[int, int, int], alpha: int):
    self._lighting_ambient_color = color
    self._lighting_ambient_alpha = alpha
```

**F. `core/bootstrap.py`** — wire `SeasonSystem` + `tile_renderer` with lighting params (in `_wire_phase4` or new `_wire_phase6`).

---

### 6.2 Ambient Occlusion (SSAO-style, Pre-baked)

**Goal:** Pre-bake per-corner AO at world-gen; apply as multiplicative overlay at render.

#### Files & Changes

**A. `world/tile_map.py`** — add AO bake method:
```python
# Add to TileMap.__init__ (line 88):
self.corner_ao: list[list[float]] = []  # (width+1) x (height+1)

# New method after compute_slope_shading (after line 309):
def bake_ambient_occlusion(self) -> None:
    """Pre-compute per-corner AO factor [0.0, 1.0]. 1.0 = no occlusion (convex), <1.0 = occluded (concave)."""
    w, h = self.width, self.height
    self.corner_ao = [[1.0] * (h + 1) for _ in range(w + 1)]
    
    # Reuse the 12-tile kernel from get_corner_height
    kernel = [
        (-1, -1, 4.0), (0, -1, 4.0), (-1, 0, 4.0), (0, 0, 4.0),
        (-2, -1, 1.0), (1, -2, 1.0), (2, 1, 1.0), (-1, 2, 1.0),
        (-2, -2, 0.25), (2, -2, 0.25), (2, 2, 0.25), (-2, 2, 0.25),
    ]
    
    for cx in range(w + 1):
        for cy in range(h + 1):
            # Reference elevation = average of 4 corner tiles
            ref_elev = self.get_raw_corner_elevation(cx, cy)
            concave_weight = 0.0
            total_weight = 0.0
            for dx, dy, weight in kernel:
                tx, ty = cx + dx, cy + dy
                tile = self.get_tile(tx, ty)
                if tile is not None:
                    total_weight += weight
                    if tile.elevation > ref_elev:
                        concave_weight += weight * min(1.0, (tile.elevation - ref_elev) / 2.0)
            if total_weight > 0:
                occlusion = concave_weight / total_weight
                self.corner_ao[cx][cy] = max(0.0, 1.0 - occlusion * AO_STRENGTH)
            else:
                self.corner_ao[cx][cy] = 1.0
    
    # Optional blur pass
    if AO_BLUR_RADIUS > 0:
        blurred = [[1.0] * (h + 1) for _ in range(w + 1)]
        for cx in range(w + 1):
            for cy in range(h + 1):
                s = 0.0
                c = 0
                for dx in range(-AO_BLUR_RADIUS, AO_BLUR_RADIUS + 1):
                    for dy in range(-AO_BLUR_RADIUS, AO_BLUR_RADIUS + 1):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx <= w and 0 <= ny <= h:
                            s += self.corner_ao[nx][ny]
                            c += 1
                blurred[cx][cy] = s / c if c > 0 else 1.0
        self.corner_ao = blurred

def get_tile_ao(self, x: int, y: int) -> float:
    """Bilinear interpolation of 4 corner AO values for a tile."""
    return (
        self.corner_ao[x][y] + self.corner_ao[x+1][y] +
        self.corner_ao[x][y+1] + self.corner_ao[x+1][y+1]
    ) / 4.0
```

**B. `world/world_gen.py`** — call bake after tile grid is built (in `generate`):
```python
# In generate(), after _build_tile_grid (around line 224):
tile_map.bake_ambient_occlusion()
```

**C. `render/tile_renderer.py`** — apply AO overlay:
```python
# In per-tile loop, after slope shading (after line 186):
if self.preset.get("ao", False):
    ao = tile_map.get_tile_ao(x, y)
    if ao < 0.99:
        # AO darkening: blend black with (1-ao) opacity
        ao_alpha = int((1.0 - ao) * 255)
        ao_surf = pygame.Surface(terrain_sprite.get_size(), pygame.SRCALPHA)
        ao_surf.fill((0, 0, 0, ao_alpha))
        self.screen.blit(ao_surf, rect, special_flags=pygame.BLEND_RGBA_MULT)
```

---

### 6.3 Rim Lighting / Fresnel

**Goal:** Brighten slopes facing the camera at grazing angles.

#### Files & Changes

**A. `world/tile_map.py`** — add surface normal helper:
```python
# New method after compute_slope_shading:
def get_surface_normal(self, x: int, y: int) -> tuple[float, float, float]:
    """Returns unnormalized normal (grad_x, grad_y, 1.0) for tile center."""
    nw = self.get_raw_corner_elevation(x, y)
    ne = self.get_raw_corner_elevation(x + 1, y)
    sw = self.get_raw_corner_elevation(x, y + 1)
    se = self.get_raw_corner_elevation(x + 1, y + 1)
    grad_x = (ne + se - nw - sw) / 2.0
    grad_y = (sw + se - nw - ne) / 2.0
    return (grad_x, grad_y, 1.0)  # Z is 1 (elevation is in Z)
```

**B. `render/tile_renderer.py`** — compute and apply rim:
```python
# In render(), get camera pitch once:
pitch = camera.pitch if hasattr(camera, "pitch") else 0.0
view_z = -math.sin(pitch)  # Camera forward in world Z (downward)

# In per-tile loop, after AO (if enabled):
if self.preset.get("rim", False):
    nx, ny, nz = tile_map.get_surface_normal(x, y)
    n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
    if n_len > 0:
        nx, ny, nz = nx/n_len, ny/n_len, nz/n_len
        # View vector is (0, 0, view_z) in yaw-rotated space; rim is 1 - dot(n, -view)
        # Since view is downward, -view = (0, 0, -view_z). Dot = -nz * view_z
        dot = -nz * view_z  # view_z is negative, so -nz * view_z = nz * |view_z|
        rim = max(0.0, 1.0 - dot) ** RIM_EXPONENT
        rim_alpha = int(rim * RIM_STRENGTH * 255)
        if rim_alpha > 0:
            rim_surf = pygame.Surface(terrain_sprite.get_size(), pygame.SRCALPHA)
            # White rim (or sun_color for colored rim)
            rim_surf.fill((255, 255, 255, rim_alpha))
            self.screen.blit(rim_surf, rect, special_flags=pygame.BLEND_RGBA_ADD)
```

---

### 6.4 Seasonal Lighting Variation

**Goal:** Winter = cooler/low sun, Summer = warm/high sun, Autumn = golden hour, Spring = neutral.

#### Files & Changes

**A. `config/constants.py`** — add `SEASON_LIGHTING` dict (already shown in 6.1 section).

**B. `seasons/season_system.py`** — extend with `get_lighting_params()` (shown in 6.1).

**C. `render/seasonal_renderer.py`** — add `set_lighting_ambient()` and update `sync()`:
```python
# In sync() (line 65), also store lighting params:
def sync(self, season_progress, current_season, previous_season):
    self.season_progress = season_progress
    self.current_season = current_season
    self.previous_season = previous_season
    # Fetch lighting from season system (passed or global)
    if hasattr(self, 'season_system') and self.season_system:
        lp = self.season_system.get_lighting_params()
        self.set_lighting_ambient(lp["ambient_color"], int(lp["ambient_level"] * 80))
```

**D. `core/bootstrap.py`** — pass `season_system` to `seasonal_renderer`:
```python
# In _wire_phase4 or new _wire_phase6:
self.game.seasonal_renderer.season_system = self.game.season_system
```

---

### 6.5 Volumetric Fog (Elevation-Based)

**Goal:** Fog density increases in valleys (low elevation), decreases on peaks.

#### Files & Changes

**A. `config/constants.py`** — add `FOG_SCALE_HEIGHT`, `FOG_HEIGHT_PLANES` (see 6.1 section).

**B. `render/tile_renderer.py`** — compute per-corner fog alpha, render gradient:
```python
# In per-tile loop, replace uniform fog_alpha (lines 142-148):
if self.preset.get("height_fog", False) and self.preset.get("volumetric_fog", False):
    # Get 4 corner elevations (already have h_nw, h_ne, h_se, h_sw from lines 99-102)
    # Fog density = base * exp(-elev / scale_height)
    def corner_fog(elev):
        base_t = (dist - FOG_NEAR_DISTANCE) / (FOG_FAR_DISTANCE - FOG_NEAR_DISTANCE)
        base_t = max(0.0, min(1.0, base_t))
        return base_t * math.exp(-elev / FOG_SCALE_HEIGHT)
    
    # Compute per-corner alpha
    fog_nw = int(corner_fog(h_nw) * 255)
    fog_ne = int(corner_fog(h_ne) * 255)
    fog_sw = int(corner_fog(h_sw) * 255)
    fog_se = int(corner_fog(h_se) * 255)
    
    # Render 4 triangles with interpolated alpha (tessellate the quad)
    # Simple approach: draw 4 corner circles with varying alpha, or split into 2 triangles
    # For pygame, easiest: draw a gradient rect using 4 blits with BLEND_RGBA_MULT
    fog_color = lighting.get("fog_tint", FOG_COLOR)
    # Draw 4 smaller rects overlapping at center — good enough approximation
    half_w = rect.width // 2
    half_h = rect.height // 2
    corners = [
        (rect.left, rect.top, fog_nw),
        (rect.left + half_w, rect.top, fog_ne),
        (rect.left + half_w, rect.top + half_h, fog_se),
        (rect.left, rect.top + half_h, fog_sw),
    ]
    for cx, cy, alpha in corners:
        if alpha > 0:
            surf = pygame.Surface((half_w + 1, half_h + 1), pygame.SRCALPHA)
            surf.fill((*fog_color, alpha))
            self.screen.blit(surf, (cx, cy))
else:
    # Existing uniform fog logic
```

**C. `render/sprite_renderer.py`** — extend `_fog_alpha` to accept elevation:
```python
@staticmethod
def _fog_alpha(world_x, world_y, player_x, player_y, elevation=0.0) -> float:
    dist = math.sqrt(dx*dx + dy*dy)
    base_alpha = ...  # existing logic
    if FOG_SCALE_HEIGHT > 0:
        base_alpha *= math.exp(-elevation / FOG_SCALE_HEIGHT)
    return int(base_alpha)
```

---

### 6.6 Dynamic Weather Lighting

**Goal:** Cloud shadows, rain darkening, snow brightening, lightning flashes.

#### Files & Changes

**A. `seasons/weather_system.py`** — extend `get_effects()`:
```python
def get_effects(self) -> dict:
    ...
    effects["light_level"] = 1.0
    effects["cloud_coverage"] = 0.0
    effects["rain_intensity"] = 0.0
    effects["lightning_chance"] = 0.0
    
    if self.current_weather == "rain":
        effects["light_level"] = 0.7
        effects["cloud_coverage"] = 0.8
        effects["rain_intensity"] = 0.6
    elif self.current_weather == "snow":
        effects["light_level"] = 1.1  # Snow brightens
        effects["cloud_coverage"] = 0.9
    elif self.current_weather == "storm":
        effects["light_level"] = 0.4
        effects["cloud_coverage"] = 1.0
        effects["rain_intensity"] = 1.0
        effects["lightning_chance"] = 0.02  # Per frame at 60fps ≈ 1.2/sec
    elif self.current_weather == "fog":
        effects["light_level"] = 0.85
        effects["cloud_coverage"] = 0.3
    return effects
```

**B. `render/tile_renderer.py`** — apply weather light level + cloud shadows:
```python
# In render(), get weather effects:
weather = {}
if hasattr(self, 'weather_system') and self.weather_system:
    weather = self.weather_system.get_effects()

# In per-tile loop, after brightness:
brightness *= weather.get("light_level", 1.0)

# Cloud shadows (cheap: low-freq noise mask)
if weather.get("cloud_coverage", 0.0) > 0.1 and self.preset.get("weather_lighting", False):
    # Use a simple per-tile hash for cloud shadow (deterministic, no extra state)
    import hashlib
    seed = hash((x * 10000 + y) ^ int(time.time() // 5.0))  # changes every 5 sec
    rnd = (seed % 1000) / 1000.0
    if rnd < weather["cloud_coverage"] * CLOUD_SHADOW_STRENGTH:
        shadow_alpha = int(rnd * CLOUD_SHADOW_STRENGTH * 255)
        shadow_surf = pygame.Surface(terrain_sprite.get_size(), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, shadow_alpha))
        self.screen.blit(shadow_surf, rect, special_flags=pygame.BLEND_RGBA_MULT)
```

**C. `core/game.py`** — lightning flash in `render_game`:
```python
# After particles (line 368), before HUD:
weather = self.weather_system.get_effects() if self.weather_system else {}
if weather.get("lightning_chance", 0.0) > 0 and self.preset.get("lightning", False):
    import random
    if random.random() < weather["lightning_chance"]:
        # Flash overlay
        flash = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        flash.fill((255, 255, 255, LIGHTNING_FLASH_ALPHA))
        self.screen.blit(flash, (0, 0))
```

---

### 6.7 Configurable Shading Presets

**Goal:** Single config switch changes all lighting quality knobs.

#### Files & Changes

**A. `config/constants.py`** — `SHADING_PRESETS` dict (see 6.1 section).

**B. `core/game.py`** — add `shading_preset` field, read preset in `render_game`:
```python
# In Game.__init__ (line 80):
from config import SHADING_PRESETS, DEFAULT_SHADING_PRESET
self.shading_preset: str = DEFAULT_SHADING_PRESET
self.preset_config: dict = SHADING_PRESETS[self.shading_preset]

# In render_game(), pass to renderers:
self._tile_renderer.preset = self.preset_config
self._sprite_renderer.preset = self.preset_config
if self.particle_system:
    self.particle_system.preset = self.preset_config
```

**C. `render/tile_renderer.py`** — use `self.preset.get(key, False)` for all features (see 6.1, 6.2, 6.3, 6.5).

**D. `render/sprite_renderer.py`** — use preset for particle culling, fog cull:
```python
# In __init__, add:
self.preset = SHADING_PRESETS[DEFAULT_SHADING_PRESET]

# In _should_cull (line 387):
def _should_cull(self, world_x, world_y, player_x, player_y) -> bool:
    cull_dist = self.preset.get("fog_cull_distance", FOG_CULL_DISTANCE)
    return dist >= cull_dist

# In sync() (line 44), cap particles:
if hasattr(self, 'preset'):
    MAX_PARTICLES = self.preset.get("particle_cap", MAX_PARTICLES)
```

**E. `render/particle_system.py`** — use preset cap:
```python
# In __init__:
self.preset = None

# In _spawn_particle (line 63):
cap = self.preset.get("particle_cap", MAX_PARTICLES) if self.preset else MAX_PARTICLES
if len(self.particles) >= cap:
    return
```

---

## Test Strategy

| Test File | Scope |
|-----------|-------|
| `tests/test_lighting_presets.py` | Verify each preset enables/disables correct features |
| `tests/test_time_of_day.py` | Sun direction changes over day cycle; ambient lerps at dawn/dusk |
| `tests/test_ambient_occlusion.py` | AO factor <1.0 in concave corners, 1.0 on peaks; blur works |
| `tests/test_rim_lighting.py` | Rim factor >0 on slopes facing camera at high pitch |
| `tests/test_seasonal_lighting.py` | Season profiles produce distinct ambient/sun/fog colors |
| `tests/test_volumetric_fog.py` | Fog density higher at low elevation vs high elevation |
| `tests/test_weather_lighting.py` | Rain darkens, snow brightens, storm triggers lightning chance |
| `tests/test_phase6_integration.py` | Full render pass with realistic preset produces valid surface |

---

## Migration / Rollout Checklist

1. [ ] Add all new constants to `config/constants.py`
2. [ ] Extend `SeasonSystem` with time-of-day + `get_lighting_params()`
3. [ ] Add `bake_ambient_occlusion()` to `TileMap`; call in `generate()`
4. [ ] Update `compute_slope_shading` to accept `light_dir`
5. [ ] Add `get_surface_normal` to `TileMap`
6. [ ] Wire `SeasonSystem` → `SeasonalRenderer` → `TileRenderer` in bootstrap
7. [ ] Implement AO overlay in `TileRenderer`
8. [ ] Implement rim lighting in `TileRenderer`
9. [ ] Implement volumetric fog (per-corner) in `TileRenderer`
10. [ ] Extend `WeatherSystem.get_effects()` with lighting fields
11. [ ] Add cloud shadow + lightning in `TileRenderer` / `Game.render_game`
12. [ ] Add `shading_preset` to `Game`; thread into renderers
13. [ ] Add preset configs to `constants.py`
14. [ ] Write all unit tests
15. [ ] Run full test suite + manual playtest 3 worlds per preset

---

## Performance Notes

- **AO bake**: `O(tiles * 12)` at world-gen. For 512×512 = 262k tiles × 12 = 3.1M ops — ~0.1s in Python. Acceptable at gen time.
- **Per-frame**: 
  - AO lookup: 1 bilinear sample per visible tile (cheap)
  - Rim: 1 normal normalize + dot per visible tile
  - Volumetric fog: 4 exp() per visible tile (cache `exp(-elev/scale)` per tile at gen if needed)
  - Weather: 1 hash + float compare per tile (cheap)
- **Sprite cache fix** (8d in survey): Add zoom-keyed terrain cache in `TileRenderer._load_terrain_sprite` to avoid per-frame scaling.
- **Rolling FPS**: Add `game.fps_avg` updated via exponential moving average in `Game.update()` for future auto-preset switching.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| AO bake adds world-gen time | Only ~0.1s for 512²; runs once. Can skip in "performance" preset. |
| Volumetric fog 4× per-tile math | Precompute `exp(-elev/FOG_SCALE_HEIGHT)` per tile at gen; store in `Tile.fog_density`. |
| Weather hash per-tile = non-deterministic across runs | Use `(x * width + y) ^ weather_frame_index` as hash; deterministic per frame. |
| Preset config fragmentation | Keep all knobs in `SHADING_PRESETS` dict; no scattered `if preset == "X"` outside dispatch. |
| Season/weather/lighting coupling | `LightingSystem` class encapsulates all cross-cutting state; single source of truth. |

---

## Next Steps

1. **Approve plan** — confirm scope and priorities
2. **Create `LightingSystem` class** as the central coordinator (new file `render/lighting_system.py`)
3. **Implement 6.1 + 6.4** (time-of-day + seasonal lighting) first — they're the foundation
4. **Implement 6.2** (AO) — most expensive at gen time, test early
5. **Implement 6.3, 6.5, 6.6** in any order
6. **Implement 6.7** (presets) — wires everything together
7. **Full test pass + playtest**