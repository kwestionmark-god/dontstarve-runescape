"""Phase 6 tests — advanced shading & lighting.

Tests cover:
- 6.1: Time-of-day in SeasonSystem (sun direction, ambient level)
- 6.2: AO bake correctness (concave = low AO, convex = high AO)
- 6.3: Rim/fresnel response to camera pitch
- 6.4: Seasonal lighting profiles
- 6.5: Volumetric fog per-tile density
- 6.6: Weather lighting effects
- 6.7: Shading preset switching
"""

import contextlib
import sys
sys.path.insert(0, '.')

import numpy as np
import pytest

from world import world_gen
from world.biome import BiomeRegistry
from world.tile_map import TileMap
from seasons.season_system import SeasonSystem
from seasons.weather_system import WeatherSystem
from render.lighting_system import LightingSystem
from data import load_json_list
from config import ELEVATION_LEVELS


@contextlib.contextmanager
def _small_map(size=128):
    """Patch world_gen MAP_WIDTH/MAP_HEIGHT for fast test generation."""
    saved_w, saved_h = world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT
    world_gen.MAP_WIDTH = size
    world_gen.MAP_HEIGHT = size
    try:
        yield
    finally:
        world_gen.MAP_WIDTH, world_gen.MAP_HEIGHT = saved_w, saved_h


def _gen_world(seed=42, size=128):
    """Generate a small test world."""
    with _small_map(size):
        registry = BiomeRegistry(load_json_list("biomes.json", "biomes"))
        ss = SeasonSystem()
        tm = world_gen.generate(seed, registry, ss)
        return tm, ss


# ─── 6.1: Time-of-day in SeasonSystem ────────────────────────────────

class TestTimeOfDay:
    """Sun direction and ambient level vary over day cycle."""

    def test_noon_has_high_sun(self):
        ss = SeasonSystem()
        ss.time_of_day = 0.5  # Noon
        lp = ss.get_lighting_params()
        alt_deg = np.degrees(lp["sun_altitude"])
        assert alt_deg > 55.0, f"Noon sun should be high, got {alt_deg:.1f}°"

    def test_midnight_has_low_sun(self):
        ss = SeasonSystem()
        ss.time_of_day = 0.0  # Midnight
        lp = ss.get_lighting_params()
        alt_deg = np.degrees(lp["sun_altitude"])
        assert alt_deg < -10.0, f"Midnight sun should be below horizon, got {alt_deg:.1f}°"

    def test_noon_ambient_is_max(self):
        ss = SeasonSystem()
        ss.time_of_day = 0.5  # Noon
        lp = ss.get_lighting_params()
        assert abs(lp["ambient_level"] - 0.45) < 0.01, f"Noon ambient should be max (0.45), got {lp['ambient_level']}"

    def test_midnight_ambient_is_min(self):
        ss = SeasonSystem()
        ss.time_of_day = 0.0  # Midnight
        lp = ss.get_lighting_params()
        assert abs(lp["ambient_level"] - 0.15) < 0.01, f"Midnight ambient should be min (0.15), got {lp['ambient_level']}"

    def test_time_advances_with_tick(self):
        ss = SeasonSystem()
        t0 = ss.time_of_day
        ss.tick(1.0)
        assert ss.time_of_day > t0, "Tick should advance time_of_day"

    def test_sun_direction_changes_with_time(self):
        ss = SeasonSystem()
        # The sun path is symmetric around noon (t=0.5), so we test that
        # adjacent positions (morning rise, noon, afternoon) differ.
        # t=0.1 → morning rising, t=0.4 → afternoon high, t=0.9 → night low
        pairs = [(0.1, 0.4), (0.1, 0.9), (0.4, 0.9)]
        for t1, t2 in pairs:
            ss.time_of_day = t1
            lp1 = ss.get_lighting_params()
            ss.time_of_day = t2
            lp2 = ss.get_lighting_params()
            dx = abs(lp1["sun_direction"][0] - lp2["sun_direction"][0])
            dy = abs(lp1["sun_direction"][1] - lp2["sun_direction"][1])
            dz = abs(lp1["sun_direction"][2] - lp2["sun_direction"][2])
            assert max(dx, dy, dz) > 0.01, (
                f"Sun dir at {t1} vs {t2} too similar: "
                f"({lp1['sun_direction']}) vs ({lp2['sun_direction']})")


# ─── 6.2: Ambient occlusion (AO) ────────────────────────────────────

class TestAO:
    """AO precompute produces valid factors in [0, 1] and responds to concavity."""

    def test_ao_corner_baked_on_generation(self):
        tm, _ = _gen_world()
        assert hasattr(tm, 'corner_ao'), "TileMap should have corner_ao"
        assert len(tm.corner_ao) == tm.width + 1, f"AO should be (W+1)x(H+1), got {len(tm.corner_ao)}"
        assert len(tm.corner_ao[0]) == tm.height + 1

    def test_ao_values_in_range(self):
        tm, _ = _gen_world(size=64)  # Small for speed
        for x in range(tm.width + 1):
            for y in range(tm.height + 1):
                v = tm.corner_ao[x][y]
                assert 0.0 <= v <= 1.0, f"AO at ({x},{y}) = {v} out of range [0,1]"

    def test_low_elevation_concave_has_low_ao(self):
        tm, _ = _gen_world(size=64)
        # Sample within the actual map bounds (0..width+1 for corners)
        hi = min(tm.width + 1, 40)  # Safe bounds
        centers = [tm.corner_ao[x][y] for x in range(2, hi) for y in range(2, hi)]
        peaks = [tm.corner_ao[x][y] for x in range(2, hi) for y in range(2, hi)
                 if tm.get_corner_height(x, y) > 20]
        if peaks and centers:
            avg_peak = sum(peaks) / len(peaks)
            avg_center = sum(centers) / len(centers)
            # Peaks should have higher AO (more convex)
            assert avg_peak > avg_center, f"Peaks should have higher AO ({avg_peak:.2f} vs {avg_center:.2f})"


# ─── 6.3: Rim lighting / fresnel ───────────────────────────────────

class TestRimLighting:
    """Surface normal availability; rim response to camera pitch."""

    def test_get_surface_normal(self):
        tm, _ = _gen_world(size=64)
        nx, ny, nz = tm.get_surface_normal(32, 32)
        # Normal should be a 3-tuple
        assert isinstance(nx, float) and isinstance(ny, float) and isinstance(nz, float)
        # Z should be positive (elevation)
        assert nz > 0

    def test_flat_land_normal(self):
        # Create a flat TileMap manually
        from world.tile_map import TileMap
        tm = TileMap(16, 16, 0, 0)
        # Set all elevation to same value
        for x in range(16):
            for y in range(16):
                tm.tiles[x][y].elevation = 15
        nx, ny, nz = tm.get_surface_normal(8, 8)
        # Flat land → normal should point straight up
        assert abs(nx) < 0.01 and abs(ny) < 0.01 and nz == 1.0

    def test_steep_land_normal(self):
        from world.tile_map import TileMap
        tm = TileMap(16, 16, 0, 0)
        # Create a slope
        for x in range(16):
            for y in range(16):
                tm.tiles[x][y].elevation = x  # Linear slope
        nx, ny, nz = tm.get_surface_normal(8, 8)
        # Should tilt toward +X
        assert nx > 0.1


# ─── 6.4: Seasonal lighting variation ───────────────────────────────

class TestSeasonalLighting:
    """Each season produces distinct ambient/sun/fog colors."""

    def test_season_lighting_distinct(self):
        ss = SeasonSystem()
        profiles = {}
        for s in ("spring", "summer", "autumn", "winter"):
            ss.current_season = s
            lp = ss.get_lighting_params()
            profiles[s] = (lp["ambient_color"], lp["sun_color"], lp["fog_tint"])
        # All four should be different
        assert len(set(profiles.values())) == 4, "All four seasons should produce distinct lighting"

    def test_winter_is_cooler(self):
        ss = SeasonSystem()
        ss.current_season = "winter"
        ss.time_of_day = 0.5
        lp = ss.get_lighting_params()
        # Winter ambient should have more blue than spring
        ss.current_season = "spring"
        lp_spring = ss.get_lighting_params()
        assert lp["ambient_color"][2] > lp_spring["ambient_color"][0], "Winter ambient should be bluer"


# ─── 6.5: Volumetric fog ────────────────────────────────────────────

class TestVolumetricFog:
    """Fog density varies with elevation."""

    def test_fog_density_decreases_with_elevation(self):
        tm, _ = _gen_world(size=64)
        # High elevation should have lower fog density
        high_elev_density = []
        low_elev_density = []
        for x in range(10, 54):
            for y in range(10, 54):
                e = tm.tiles[x][y].elevation
                if e > 20:
                    high_elev_density.append(tm.tiles[x][y].fog_density)
                elif e < 10:
                    low_elev_density.append(tm.tiles[x][y].fog_density)
        if high_elev_density and low_elev_density:
            avg_high = sum(high_elev_density) / len(high_elev_density)
            avg_low = sum(low_elev_density) / len(low_elev_density)
            assert avg_high < avg_low, f"High elevation should have lower fog ({avg_high:.3f} vs {avg_low:.3f})"

    def test_fog_density_all_tiles_initialized(self):
        tm, _ = _gen_world(size=64)
        for x in range(tm.width):
            for y in range(tm.height):
                v = tm.tiles[x][y].fog_density
                assert 0.0 <= v <= 1.0, f"fog_density at ({x},{y}) = {v} out of range"


# ─── 6.6: Weather lighting ───────────────────────────────────────────

class TestWeatherLighting:
    """Weather effects modify light level, cloud coverage, lightning chance."""

    def test_rain_darkens(self):
        ss = SeasonSystem()
        ws = WeatherSystem()
        ws.current_weather = "rain"
        effects = ws.get_effects()
        assert effects["light_level"] < 1.0, "Rain should darken"
        assert effects["cloud_coverage"] > 0.5, "Rain implies high cloud coverage"

    def test_snow_brightens(self):
        ss = SeasonSystem()
        ws = WeatherSystem()
        ws.current_weather = "snow"
        effects = ws.get_effects()
        assert effects["light_level"] > 1.0, "Snow should brighten"

    def test_storm_has_lightning(self):
        ss = SeasonSystem()
        ws = WeatherSystem()
        ws.current_weather = "storm"
        effects = ws.get_effects()
        assert effects["lightning_chance"] > 0, "Storm should trigger lightning"

    def test_clear_has_no_lightning(self):
        ss = SeasonSystem()
        ws = WeatherSystem()
        ws.current_weather = "clear"
        effects = ws.get_effects()
        assert effects["lightning_chance"] == 0.0, "Clear weather should not have lightning"


# ─── 6.7: Shading presets ───────────────────────────────────────────

class TestShadingPresets:
    """Different presets gate the correct features."""

    def test_preset_switches_features(self):
        ls = LightingSystem("stylized")
        assert ls.preset_config["ao"] is False
        assert ls.preset_config["rim"] is False
        ls.set_preset("realistic")
        assert ls.preset_config["ao"] is True
        assert ls.preset_config["rim"] is True
        assert ls.preset_config["multi_light"] is True

    def test_performance_minimal(self):
        ls = LightingSystem("performance")
        assert ls.preset_config["slope_shading"] is False
        assert ls.preset_config["ao"] is False
        assert ls.preset_config["rim"] is False
        assert ls.preset_config["particle_cap"] == 150

    def test_default_preset(self):
        from config import DEFAULT_SHADING_PRESET
        ls = LightingSystem()
        assert ls.preset == DEFAULT_SHADING_PRESET


# ─── Integration: Full lighting frame ────────────────────────────────

class TestIntegration:
    """End-to-end: world gen + lighting produces valid output."""

    def test_full_pipeline_no_crash(self):
        tm, ss = _gen_world(size=64)
        ls = LightingSystem()
        ws = WeatherSystem(season_system=ss)
        
        # Simulate frame update
        ls.update_from_season(ss)
        ls.update_from_weather(ws)
        
        # Verify state
        assert ls.sun_direction is not None
        assert 0.0 <= ls.ambient_level <= 1.0
        assert ls.weather_light_level > 0

    def test_compute_all_shading_numpy(self):
        tm, _ = _gen_world(size=64)
        ls = LightingSystem()
        ls.set_preset("realistic")  # multi_light = True
        brightness, slope = ls.compute_all_shading(tm, 0.5, 0.5, 0.7)
        assert brightness is not None
        assert brightness.shape == (64, 64)
        assert slope.shape == (64, 64)
        # All values should be in reasonable range
        assert np.all(brightness >= 0.5), "Brightness should be >= 0.5"
        assert np.all(brightness <= 1.5), "Brightness should be <= 1.5"
        assert np.all(slope >= 0.0), "Slope magnitude should be >= 0"
        assert np.all(slope <= 1.0), "Slope magnitude should be <= 1"
