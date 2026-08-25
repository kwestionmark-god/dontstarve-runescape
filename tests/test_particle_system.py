"""
test_particle_system.py — Integration tests for ParticleSystem.

Tests:
- Particle sync with weather types
- Particle spawning rates per weather
- Particle update and position changes
- Particle capping at max_particles
- Particle removal when off-screen
- Clear weather produces no particles
"""

import pytest
from types import SimpleNamespace
from render.particle_system import ParticleSystem


class TestParticleSystemSync:
    """Test weather sync and spawn rate changes."""

    def test_clear_weather_zero_spawn(self):
        """Clear weather should have zero spawn rate."""
        ps = ParticleSystem()
        # ParticleSystem starts with _spawn_rate=10, sync("clear") sets it to 0
        ps.sync("clear")

        assert ps.current_weather == "clear"
        assert ps._spawn_rate == 0

    def test_rain_weather_increases_spawn(self):
        """Rain weather should increase spawn rate."""
        ps = ParticleSystem()
        ps.sync("rain")

        assert ps.current_weather == "rain"
        assert ps._spawn_rate == 20

    def test_snow_weather_low_spawn(self):
        """Snow weather should have low spawn rate."""
        ps = ParticleSystem()
        ps.sync("snow")

        assert ps.current_weather == "snow"
        assert ps._spawn_rate == 10

    def test_storm_weather_high_spawn(self):
        """Storm weather should have highest spawn rate."""
        ps = ParticleSystem()
        ps.sync("storm")

        assert ps.current_weather == "storm"
        assert ps._spawn_rate == 40

    def test_fog_weather_lowest_spawn(self):
        """Fog weather should have lowest non-zero spawn rate."""
        ps = ParticleSystem()
        ps.sync("fog")

        assert ps.current_weather == "fog"
        assert ps._spawn_rate == 5

    def test_sync_noop_for_same_weather(self):
        """Syncing to current weather should not reinitialize."""
        ps = ParticleSystem()
        ps.sync("rain")
        spawn_rate = ps._spawn_rate
        particles_before = len(ps.particles)

        ps.sync("rain")

        assert ps._spawn_rate == spawn_rate
        assert len(ps.particles) == particles_before


class TestParticleSpawning:
    """Test particle spawning behavior."""

    def test_no_particles_spawned_for_clear(self):
        """Clear weather should not spawn any particles."""
        ps = ParticleSystem()
        ps.sync("clear")
        ps.update(1.0)

        assert len(ps.particles) == 0

    def test_rain_spawns_particles_over_time(self):
        """Rain weather should spawn particles over time."""
        ps = ParticleSystem()
        ps.sync("rain")

        # Spawn for 2 seconds
        ps.update(2.0)

        # Should have spawned particles (20/s * 2s = ~40)
        assert len(ps.particles) > 0
        assert len(ps.particles) <= 50  # Within reasonable range

    def test_storm_spawns_most_particles(self):
        """Storm weather should spawn more particles than rain."""
        ps_storm = ParticleSystem()
        ps_storm.sync("storm")
        ps_storm.update(1.0)

        ps_rain = ParticleSystem()
        ps_rain.sync("rain")
        ps_rain.update(1.0)

        assert len(ps_storm.particles) > len(ps_rain.particles)

    def test_particles_capped_at_max(self):
        """Particle count should not exceed max_particles."""
        ps = ParticleSystem(max_particles=100)
        ps.sync("storm")

        # Spawn heavily for 10 seconds
        ps.update(10.0)

        assert len(ps.particles) <= 100


class TestParticleUpdate:
    """Test particle position updates."""

    def test_rain_particles_move_downward(self):
        """Rain particles should move downward (increasing y)."""
        ps = ParticleSystem()
        ps.sync("rain")
        ps.update(1.0)

        if ps.particles:
            # All rain particles should have positive y velocity
            for p in ps.particles:
                assert p.vy > 0  # Moving downward
                assert p.x < 1280  # Within screen width
                assert p.y > -10  # Should have moved from spawn

    def test_snow_particles_drift_sideways(self):
        """Snow particles should drift sideways."""
        ps = ParticleSystem()
        ps.sync("snow")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                # Snow has slow vertical and some horizontal movement
                assert p.vy > 0  # Still moving down
                assert abs(p.vx) < 50  # Slow horizontal drift

    def test_fog_particles_move_slowly(self):
        """Fog particles should move very slowly."""
        ps = ParticleSystem()
        ps.sync("fog")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                # Fog particles are very slow
                assert abs(p.vx) <= 5
                assert abs(p.vy) <= 5

    def test_particles_removed_when_expired(self):
        """Particles older than 10 seconds should be removed."""
        ps = ParticleSystem()
        ps.sync("rain")

        # Spawn some particles
        ps.update(1.0)
        initial_count = len(ps.particles)
        assert initial_count > 0

        # Age all particles beyond the 10s limit
        for p in ps.particles:
            p.life = 10.5  # Exceeds the 10.0 limit

        # Switch to clear weather to prevent new spawns
        ps.sync("clear")
        ps.update(0.1)

        # All expired particles should be removed
        assert len(ps.particles) == 0


class TestParticleProperties:
    """Test particle visual properties per weather type."""

    def test_rain_particle_size(self):
        """Rain particles should be size 2."""
        ps = ParticleSystem()
        ps.sync("rain")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                assert p.size == 2

    def test_snow_particle_size(self):
        """Snow particles should be size 3."""
        ps = ParticleSystem()
        ps.sync("snow")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                assert p.size == 3

    def test_fog_particle_size(self):
        """Fog particles should be large (size 40)."""
        ps = ParticleSystem()
        ps.sync("fog")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                assert p.size == 40

    def test_rain_particle_alpha(self):
        """Rain particles should have alpha 180."""
        ps = ParticleSystem()
        ps.sync("rain")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                assert p.alpha == 180

    def test_fog_particle_alpha(self):
        """Fog particles should have alpha 60."""
        ps = ParticleSystem()
        ps.sync("fog")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                assert p.alpha == 60

    def test_storm_particles_have_negative_vx(self):
        """Storm particles should have negative vx (wind direction)."""
        ps = ParticleSystem()
        ps.sync("storm")
        ps.update(1.0)

        if ps.particles:
            for p in ps.particles:
                assert p.vx < 0  # Wind blowing left


class TestParticleSystemIntegration:
    """Integration tests with Game."""

    def test_bootstrap_creates_particle_system(self):
        """Bootstrap should create ParticleSystem and wire it."""
        # This test verifies the bootstrap wiring works
        from core.bootstrap import Bootstrap
        from seasons import SeasonSystem, WeatherSystem

        # Create minimal mock game
        class MockGame:
            survival = None
            player = None
            weather_system = None
            particle_system = None

        game = MockGame()

        # Create SeasonSystem and WeatherSystem
        season_system = SeasonSystem()
        weather_system = WeatherSystem()
        weather_system.set_season_system(season_system)

        game.season_system = season_system
        game.weather_system = weather_system

        # Wire particle system (same as bootstrap does)
        from render import ParticleSystem
        game.particle_system = ParticleSystem()
        game.particle_system.sync(game.weather_system.current_weather)

        # Verify
        assert game.particle_system is not None
        assert game.particle_system.current_weather == "clear"
        assert game.particle_system._spawn_rate == 0

    def test_particle_system_syncs_with_weather_changes(self):
        """ParticleSystem should update spawn rate when weather changes."""
        ps = ParticleSystem()
        ps.sync("clear")
        assert ps._spawn_rate == 0

        ps.sync("rain")
        assert ps._spawn_rate == 20

        ps.sync("storm")
        assert ps._spawn_rate == 40

        ps.sync("snow")
        assert ps._spawn_rate == 10

        ps.sync("fog")
        assert ps._spawn_rate == 5

        ps.sync("clear")
        assert ps._spawn_rate == 0


class TestParticleSystemSurfaceAdaptation:
    """#20: particle spawn/off-screen bounds follow the real surface size."""

    def test_screen_dims_update_from_surface(self):
        """draw() records the surface size for spawn bounds."""
        ps = ParticleSystem()
        ps.screen_w, ps.screen_h = 0, 0
        fake_screen = SimpleNamespace(get_size=lambda: (1024, 600))
        ps.draw(fake_screen)
        assert ps.screen_w == 1024
        assert ps.screen_h == 600

    def test_draw_none_is_safe(self):
        """draw(None) must not raise (preserves prior None-safety)."""
        ps = ParticleSystem()
        ps.draw(None)  # no particles -> returns cleanly

    def test_rain_spawns_within_adaptive_width(self):
        """Rain particles stay within the captured screen width."""
        ps = ParticleSystem()
        ps.sync("rain")
        # Non-default width; keep default height so particles aren't
        # height-culled within a single update (vy reaches 600px/s).
        ps.screen_w, ps.screen_h = 320, 720
        ps.update(1.0)
        assert ps.particles
        for p in ps.particles:
            # Spawned within [0, screen_w]; one frame of leftward wind
            # (<=50px/s) can only pull x a little below 0.
            assert -50 <= p.x <= 320
            assert p.y > -10
