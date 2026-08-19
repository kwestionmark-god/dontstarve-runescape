"""
particle_system.py — Weather particle effects.

Screen-space particles for rain/snow/storm; capped count for performance.
"""

from __future__ import annotations
import random
from typing import Any

MAX_PARTICLES = 500
DEFAULT_PARTICLE_SPAWN_RATE = 10  # particles per second


class Particle:
    """A single weather particle."""

    __slots__ = ("x", "y", "vx", "vy", "size", "alpha", "life")

    def __init__(self, x: float, y: float, vx: float, vy: float, size: int, alpha: int) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.alpha = alpha
        self.life: float = 0.0


class ParticleSystem:
    """Manages weather particles (rain, snow, storm, fog)."""

    def __init__(self, max_particles: int = MAX_PARTICLES) -> None:
        self.max_particles = max_particles
        self.particles: list[Particle] = []
        self.current_weather: str = "clear"
        self._spawn_rate = 0  # Initialized to match "clear" weather
        self._rng = random.Random(42)

    def sync(self, weather: str) -> None:
        """Update particle settings based on current weather."""
        if weather == self.current_weather:
            return
        self.current_weather = weather
        # Set spawn rate and properties per weather type
        rates: dict[str, int] = {
            "clear": 0,
            "rain": 20,
            "snow": 10,
            "storm": 40,
            "fog": 5,
        }
        self._spawn_rate = rates.get(weather, 0)

    def update(self, dt: float) -> None:
        """Update particle positions and spawn new ones."""
        # Spawn
        if self._spawn_rate > 0:
            to_spawn = int(self._spawn_rate * dt)
            for _ in range(to_spawn):
                if len(self.particles) >= self.max_particles:
                    break
                self._spawn_particle()

        # Update
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life += dt
            # Remove if off-screen or expired
            if p.y > 1000 or p.life > 10.0:
                p.life = 10.0  # Mark for removal

        # Compact — remove expired (life >= 10.0)
        self.particles = [p for p in self.particles if p.life < 10.0]

    def _spawn_particle(self) -> None:
        """Spawn a new particle based on current weather type."""
        if self.current_weather in ("rain", "storm"):
            x = self._rng.uniform(0, 1280)
            y = -10
            vy = self._rng.uniform(300, 600)
            vx = -50 if self.current_weather == "storm" else -20
            size = 2
        elif self.current_weather == "snow":
            x = self._rng.uniform(0, 1280)
            y = -10
            vy = self._rng.uniform(40, 100)
            vx = self._rng.uniform(-30, 30)
            size = 3
        elif self.current_weather == "fog":
            x = self._rng.uniform(0, 1280)
            y = self._rng.uniform(0, 720)
            vx = self._rng.uniform(-5, 5)
            vy = self._rng.uniform(-5, 5)
            size = 40
        else:
            return

        alpha = 180 if self.current_weather != "fog" else 60
        self.particles.append(Particle(x, y, vx, vy, size, alpha))

    def draw(self, screen: Any) -> None:
        """Draw all particles on the screen surface."""
        import pygame

        if not self.particles:
            return

        if self.current_weather == "fog":
            # Fog: draw circles
            for p in self.particles:
                color = (200, 200, 210, p.alpha)
                try:
                    pygame.draw.circle(screen, (200, 200, 210), (int(p.x), int(p.y)), p.size)
                except (ValueError, TypeError):
                    pass
        else:
            # Rain/snow: draw lines or small rects
            for p in self.particles:
                if self.current_weather in ("rain", "storm"):
                    # Draw as short line
                    end_x = int(p.x - p.vx * 0.03)
                    end_y = int(p.y + 10)
                    pygame.draw.line(screen, (150, 180, 220), (int(p.x), int(p.y)), (end_x, end_y), 1)
                elif self.current_weather == "snow":
                    pygame.draw.circle(screen, (240, 240, 250), (int(p.x), int(p.y)), p.size)
