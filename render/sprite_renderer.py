"""
sprite_renderer.py — Billboard sprite rendering.

Renders the player and resource-node sprites on top of the terrain.
Sprites are "billboard" style — they always face the camera and do not
rotate with the orbit angle. They are positioned with elevation-aware
Y-offsets so they sit naturally on the terrain.

Asset loading falls back to colored placeholder rectangles when no
sprite sheet is available.

Usage:
    sprite_renderer = SpriteRenderer()
    sprite_renderer.render_player(player, camera)
    sprite_renderer.render_resource(node, camera)
"""

from __future__ import annotations

import math
import time

import pygame
from typing import TYPE_CHECKING

from config import Z_SCALE, FOG_NEAR_DISTANCE, FOG_FAR_DISTANCE, FOG_CULL_DISTANCE, FOG_COLOR

if TYPE_CHECKING:
    from camera import Camera
    from world.tile_map import TileMap

# Placeholder sprite cache keyed by (width, height, color_hex).
_placeholder_cache: dict[tuple[int, int, str], pygame.Surface] = {}


class SpriteRenderer:
    """
    Handles all sprite-based rendering (player + resource nodes).

    Parameters
    ----------
    sprite_dir : str, optional
        Root directory for sprite assets (default ``"assets/sprites"``).
    """

    __slots__ = ("sprite_dir", "_sprite_cache", "_font", "tile_map", "seasonal_renderer")

    def __init__(
        self,
        sprite_dir: str = "assets/sprites",
        tile_map: "TileMap | None" = None,
        seasonal_renderer: object | None = None,
    ) -> None:
        self.sprite_dir = sprite_dir
        self.tile_map = tile_map
        self.seasonal_renderer = seasonal_renderer
        self._sprite_cache: dict[str, pygame.Surface | None] = {}
        self._font: pygame.font.Font | None = None

    # ── Player rendering ──────────────────────────────────────────────

    def render_player(
        self, screen: object, player: object, camera: object, elevation: int = 0,
    ) -> None:
        """
        Draw the player sprite centred on their world position.

        Parameters
        ----------
        screen : pygame.Surface
            The display surface to draw on.
        player : Player
            The player entity (must have ``world_x``, ``world_y``).
        camera : Camera
            The orbital camera for coordinate transforms.
        elevation : int, optional
            Current tile elevation (default 0). Deprecated — tile_map is now used.
        """
        world_x = player.world_x
        world_y = player.world_y

        # Get tile center height for Z-aware positioning.
        if self.tile_map is not None:
            tx = int(world_x // self.TILE_SIZE)
            ty = int(world_y // self.TILE_SIZE)
            corner_h = self.tile_map.get_tile_center_height(tx, ty)
            screen_x, screen_y = camera.world_to_screen(world_x, world_y, elevation=corner_h * Z_SCALE)
            # Camera elevation parameter now handles vertical displacement
        else:
            # Fallback to original behavior.
            screen_x, screen_y = camera.world_to_screen(world_x, world_y)
            elevation_offset = elevation * 3
            screen_y -= elevation_offset

        # Zoom: scale sprite so it matches zoomed world
        zoom = camera.zoom if hasattr(camera, "zoom") else 1.0

        # Select sprite based on movement state
        if getattr(player, "is_moving", False):
            sprite = self._load_player_sprite("walk_0")
        else:
            sprite = self._load_player_sprite("idle_0")

        if sprite is not None and zoom != 1.0:
            scaled_w = max(4, int(sprite.get_width() * zoom))
            scaled_h = max(4, int(sprite.get_height() * zoom))
            sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))

        if sprite is not None:
            # Apply seasonal tint if available
            if self.seasonal_renderer is not None:
                tint_color = self._get_season_tint(tier=1)
                sprite = self._apply_seasonal_tint(sprite, tint_color, alpha=40)

            rect = sprite.get_rect(center=(int(screen_x), int(screen_y)))
            screen.blit(sprite, rect)
        else:
            # Placeholder scaled by zoom
            base_size = 32
            rect = pygame.Rect(0, 0, int(base_size * zoom), int(base_size * zoom))
            rect.center = (int(screen_x), int(screen_y))
            pygame.draw.rect(screen, (100, 200, 255), rect)
            pygame.draw.rect(screen, (80, 160, 200), rect, 2)

    # ── Resource sprite rendering ──────────────────────────────────────

    # Tile size (pixels) — mirrors config TILE_SIZE
    TILE_SIZE: int = 64

    # Placeholder sizes per resource family.
    _RESOURCE_SIZES: dict[str, int] = {
        "tree": 18,
        "rock": 16,
        "bush": 14,
        "ore": 14,
        "plant": 12,
        "water": 12,
        "default": 14,
    }

    def render_resource(
        self,
        screen: object,
        node: object,
        camera: object,
        elevation: int = 0,
        tile_x: int = 0,
        tile_y: int = 0,
    ) -> None:
        """
        Draw a resource-node sprite centred on its tile.

        Parameters
        ----------
        screen : pygame.Surface
            The display surface to draw on.
        node : ResourceNode
            The resource node (must have ``sprite_key`` and
            ``is_depleted``).
        camera : Camera
            The orbital camera for coordinate transforms.
        elevation : int, optional
            Current tile elevation (default 0). Deprecated — tile_map is now used.
        tile_x : int
            Grid-column of the tile this node occupies.
        tile_y : int
            Grid-row of the tile this node occupies.
        """
        world_x = tile_x * self.TILE_SIZE + self.TILE_SIZE // 2
        world_y = tile_y * self.TILE_SIZE + self.TILE_SIZE // 2

        # Get player position from camera for distance calculations.
        player_x = 0.0
        player_y = 0.0
        if hasattr(camera, "player") and camera.player is not None:
            player_x = camera.player.world_x
            player_y = camera.player.world_y

        # Zoom: scale sprite so it matches zoomed world
        zoom = camera.zoom if hasattr(camera, "zoom") else 1.0

        # LOD culling: skip if beyond fog cull distance.
        if self._should_cull(world_x, world_y, player_x, player_y):
            return

        # Get tile center height for Z-aware positioning.
        if self.tile_map is not None:
            corner_h = self.tile_map.get_tile_center_height(tile_x, tile_y)
            screen_x, screen_y = camera.world_to_screen(world_x, world_y, elevation=corner_h * Z_SCALE)
            # Camera elevation parameter now handles vertical displacement
        else:
            # Fallback to original behavior.
            screen_x, screen_y = camera.world_to_screen(world_x, world_y)
            elevation_offset = elevation * 3
            screen_y -= elevation_offset

        cy = int(screen_y - 8)
        cx = int(screen_x)

        # Resolve the correct sprite key based on depletion / regrowth state.
        sprite_key, sprite = self._resolve_resource_sprite(
            node, tile_x, tile_y,
        )

        if sprite is not None:
            # Apply seasonal tint if available (same path as mature sprites).
            if self.seasonal_renderer is not None:
                tier = getattr(node, "tier", 1)
                tint_color = self._get_season_tint(tier=tier)
                sprite = self._apply_seasonal_tint(sprite, tint_color, alpha=40)
            # Scale sprite by zoom
            if zoom != 1.0:
                scaled_w = max(4, int(sprite.get_width() * zoom))
                scaled_h = max(4, int(sprite.get_height() * zoom))
                sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
            rect = sprite.get_rect(center=(cx, cy))
            screen.blit(sprite, rect)
            # Apply fog overlay
            fog_a = self._fog_alpha(world_x, world_y, player_x, player_y)
            if fog_a > 0:
                self._apply_fog_overlay(screen, rect, fog_a)
        else:
            # ── Placeholder ───────────────────────────────────
            # Scale placeholder sizes by zoom
            base_size = self._resource_radius(node)
            size = int(base_size * zoom)
            depleted = getattr(node, "is_depleted", False)

            if depleted:
                # Draw a subtle "stump / rubble" marker.
                colour = (100, 90, 80)
                pygame.draw.circle(screen, colour, (cx, cy), max(1, size // 2))
                pygame.draw.circle(
                    screen, (80, 70, 60), (cx, cy), max(1, size // 2 - 2), 2,
                )
                return

            family = self._resource_family(node)
            colour = self._resource_colour(node)

            if family == "tree":
                # Circle (canopy).
                pygame.draw.circle(screen, colour, (cx, cy), max(1, size))
                pygame.draw.circle(screen, self._darken(colour, 30), (cx, cy), max(1, size), 2)
                # Trunk hint (scale thickness too).
                line_thick = max(1, int(3 * zoom))
                pygame.draw.line(screen, (80, 50, 30), (cx, cy + size), (cx, cy + size + int(6 * zoom)), line_thick)
            elif family == "rock":
                # Rounded rectangle (boulder).
                r = pygame.Rect(cx - size, cy - size // 2, size * 2, size)
                pygame.draw.rect(screen, colour, r, border_radius=max(1, int(4 * zoom)))
                pygame.draw.rect(screen, self._darken(colour, 30), r, 2, border_radius=max(1, int(4 * zoom)))
            elif family == "bush":
                # Diamond (leafy bush).
                points = [
                    (cx, cy - size),
                    (cx + size, cy),
                    (cx, cy + size),
                    (cx - size, cy),
                ]
                pygame.draw.polygon(screen, colour, points)
                pygame.draw.polygon(
                    screen, self._darken(colour, 30), points, max(1, int(2 * zoom)),
                )
            elif family == "ore":
                # Small bright diamond (glowing ore).
                points = [
                    (cx, cy - size),
                    (cx + size, cy),
                    (cx, cy + size),
                    (cx - size, cy),
                ]
                pygame.draw.polygon(screen, colour, points)
                pygame.draw.polygon(
                    screen, self._darken(colour, 40), points, max(1, int(2 * zoom)),
                )
            elif family == "water":
                # Blue ellipse (pool).
                ellipse_rect = pygame.Rect(cx - size, cy - size // 2, size * 2, size)
                pygame.draw.ellipse(screen, colour, ellipse_rect)
                pygame.draw.ellipse(
                    screen, self._darken(colour, 30), ellipse_rect, max(1, int(2 * zoom)),
                )
            else:
                # Generic circle.
                pygame.draw.circle(screen, colour, (cx, cy), max(1, size))
                pygame.draw.circle(screen, self._darken(colour, 30), (cx, cy), max(1, size), 2)

    # ── Seasonal tinting helpers ────────────────────────────────────────

    @staticmethod
    def _get_season_tint(tier: int = 1) -> tuple[int, int, int]:
        """Return a seasonal tint color based on sprite tier.

        Tints are subtle overlays applied to sprites to reflect seasonal
        atmosphere. Lower tiers get greener tints (nature), higher tiers
        get more muted/earthy tones.

        Args:
            tier: Sprite tier (1 = common/nature, 4 = rare/precious).

        Returns:
            RGB tuple for seasonal tint overlay.
        """
        tints = {
            1: (80, 100, 60),    # Green — nature, player
            2: (100, 100, 100),  # Grey  — neutral NPCs
            3: (120, 100, 60),   # Gold  — rare items
            4: (100, 80, 100),   # Purple — rare entities
        }
        return tints.get(tier, tints[1])

    def _apply_seasonal_tint(
        self,
        sprite: pygame.Surface,
        tint_color: tuple[int, int, int],
        alpha: int = 40,
    ) -> pygame.Surface:
        """Create a tinted copy of a sprite.

        Blends a semi-transparent tint overlay onto the sprite using
        BLEND_RGBA_MULT for additive color mixing.

        Args:
            sprite: The original pygame Surface to tint.
            tint_color: RGB tuple for the tint overlay.
            alpha: Overlay opacity (0–255).

        Returns:
            A new Surface with the tint applied.
        """
        if alpha <= 0:
            return sprite.copy()

        tinted = sprite.copy()
        tint_surf = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        r, g, b = tint_color
        tint_surf.fill((r, g, b, alpha))
        tinted.blit(tint_surf, (0, 0))
        return tinted

    # ── Fog & LOD helpers ─────────────────────────────────────────────

    @staticmethod
    def _fog_alpha(world_x: float, world_y: float, player_x: float, player_y: float) -> float:
        """Return fog alpha (0–255) based on distance from player.
        
        - 0 alpha when distance <= FOG_NEAR_DISTANCE (fully visible)
        - 255 alpha when distance >= FOG_FAR_DISTANCE (fully obscured)
        - Linear fade in between
        """
        dx = world_x - player_x
        dy = world_y - player_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist >= FOG_FAR_DISTANCE:
            return 255
        if dist <= FOG_NEAR_DISTANCE:
            return 0
        # Linear fade from 0 → 255 across [FOG_NEAR, FOG_FAR]
        fade_range = FOG_FAR_DISTANCE - FOG_NEAR_DISTANCE
        t = (dist - FOG_NEAR_DISTANCE) / fade_range
        return int(t * 255)

    @staticmethod
    def _should_cull(world_x: float, world_y: float, player_x: float, player_y: float) -> bool:
        """Return True if the entity should be skipped due to LOD culling."""
        dx = world_x - player_x
        dy = world_y - player_y
        dist = math.sqrt(dx * dx + dy * dy)
        return dist >= FOG_CULL_DISTANCE

    @staticmethod
    def _apply_fog_overlay(
        screen: pygame.Surface, rect: pygame.Rect, alpha: float,
    ) -> None:
        """Blit a fog-coloured overlay onto the given screen region.
        
        The overlay matches the region size and uses SRCALPHA with
        ``alpha`` as its opacity.
        """
        w = rect.width
        h = rect.height
        fog_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        fog_surf.fill((*FOG_COLOR, int(alpha)))
        screen.blit(fog_surf, rect)

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_sprite(self, sprite_key: str) -> pygame.Surface | None:
        """
        Load a sprite from cache or disk.

        Parameters
        ----------
        sprite_key : str
            Relative path inside ``sprite_dir`` (e.g. ``"trees/oak"``).

        Returns
        -------
        pygame.Surface | None
            The loaded sprite, or ``None`` if not found.
        """
        if sprite_key in self._sprite_cache:
            return self._sprite_cache[sprite_key]

        path = f"{self.sprite_dir}/{sprite_key}.png"
        try:
            surf = pygame.image.load(path)
            surf = surf.convert_alpha()
        except (pygame.error, FileNotFoundError):
            surf = None

        self._sprite_cache[sprite_key] = surf
        return surf

    def _load_player_sprite(self, frame: str = "idle_0") -> pygame.Surface | None:
        """Load a player sprite frame.
        
        Args:
            frame: Frame identifier, e.g. 'idle_0', 'walk_0'.
        """
        return self._get_sprite(f"player/{frame}")

    @staticmethod
    def _resource_radius(node: object) -> int:
        """Return placeholder radius based on resource family."""
        family = SpriteRenderer._resource_family(node)
        return SpriteRenderer._RESOURCE_SIZES.get(family, SpriteRenderer._RESOURCE_SIZES["default"])

    @staticmethod
    def _resource_family(node: object) -> str:
        """
        Infer a resource family from sprite_key / resource_id.

        Families: tree, rock, bush, ore, plant, water, default.

        Trees are reliably classified by their sprite_key prefix (``trees/``)
        or known tree resource_ids, so the renderer can resolve regrowth
        stage sprites for any tree-type resource.
        """
        key = getattr(node, "sprite_key", "")
        rid = getattr(node, "resource_id", "")
        # Strip directory prefix (e.g. "trees/berry_bush" -> "berry_bush")
        basename = key.rsplit("/", 1)[-1]
        combined = f"{basename} {rid}".lower()

        # Trees: sprite_key prefix "trees/" or known tree-ish resource_ids
        if key.startswith("trees/") or "tree" in combined or rid.endswith("_tree") or rid == "elder_wood":
            return "tree"
        if any(t in combined for t in ("gemstone", "rare_ore")):
            return "ore"
        if any(t in combined for t in ("rock", "iron_rock", "copper", "stone_quarry", "stone", "gold")):
            return "rock"
        if any(t in combined for t in ("bush", "berry", "cactus")):
            return "bush"
        if any(t in combined for t in ("water", "fish", "salt", "sand", "shell")):
            return "water"
        # Default: treat as plant-like
        return "plant"

    @staticmethod
    def _darken(colour: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
        """Return a colour darker by *amount* (0-255 per channel)."""
        return tuple(max(0, c - amount) for c in colour)

    @staticmethod
    def _resource_colour(node: object) -> tuple[int, int, int]:
        """Return a placeholder colour based on resource tier."""
        tier = getattr(node, "tier", 1)
        colours = {
            1: (139, 90, 43),    # Brown — wood/fibre
            2: (150, 150, 160),  # Grey   — stone
            3: (200, 170, 50),   # Gold   — precious
            4: (220, 100, 220),  # Purple — rare
        }
        return colours.get(tier, (139, 90, 43))

    # ── Sprite key resolution (depleted / regrowth / mature) ──────────

    def _family_fallback(self, family: str) -> pygame.Surface | None:
        """Return the shared fallback sprite for a depleted family."""
        if family == "tree":
            return self._get_sprite("trees/stump")
        if family in ("rock", "ore"):
            return self._get_sprite("rocks/rubble")
        # plant / bush / water
        return self._get_sprite("world/depleted_patch")

    def _resolve_resource_sprite(
        self,
        node: object,
        tile_x: int,
        tile_y: int,
    ) -> tuple[str, pygame.Surface | None]:
        """Resolve the correct sprite key and surface for a resource node.

        Implements the naming convention from
        ``docs/superpowers/plans/phase-depleted-regrowth-sprites.md``:

        - mature:        ``{base}.png``
        - depleted:      ``{base}_depleted.png`` (or family fallback)
        - tree regrowth: ``{base}_sapling.png`` / ``{base}_young.png`` (or
          ``trees/{stage}_generic.png`` or ``trees/stump.png``)

        Prefers ``tile.regrow_timer`` / ``tile.depleted`` over
        ``node.is_depleted`` when ``tile_map`` is set, so timer-driven
        stages are accurate.
        """
        base = getattr(node, "sprite_key", "")
        family = self._resource_family(node)
        depletion_count = getattr(node, "depletion_count", 0)

        # Infinite resources (depletion_count <= 0) never deplete.
        if depletion_count <= 0:
            return base, self._get_sprite(base)

        # Determine depletion state, preferring tile state when available.
        tile = None
        if self.tile_map is not None:
            tile = self.tile_map.get_tile(tile_x, tile_y)

        node_depleted = getattr(node, "is_depleted", False)
        tile_depleted = tile.depleted if tile is not None else node_depleted
        regrow_timer = tile.regrow_timer if tile is not None else 0.0
        regrow_time = getattr(node, "regrow_time", 0.0)

        depleted = node_depleted or tile_depleted

        if depleted:
            if family == "tree" and regrow_timer > 0:
                # Tree regrowth: pick sapling / young stage.
                stage = self._tree_growth_stage(
                    regrow_timer, regrow_time, family,
                )
                key = f"{base}_{stage}"
                sprite = self._get_sprite(key)
                if sprite is None:
                    # Shared generic fallback for this stage.
                    generic = f"trees/{stage}_generic"
                    sprite = self._get_sprite(generic)
                if sprite is None:
                    # Per-type depleted fallback.
                    sprite = self._get_sprite(f"{base}_depleted")
                if sprite is None:
                    # Ultimate fallback.
                    sprite = self._get_sprite("trees/stump")
                return key, sprite
            else:
                # Depleted: try per-type depleted, then family fallback.
                key = f"{base}_depleted"
                sprite = self._get_sprite(key)
                if sprite is None:
                    sprite = self._family_fallback(family)
                return key, sprite
        else:
            # Mature (or regrowth finished).
            return base, self._get_sprite(base)

    @staticmethod
    def _tree_growth_stage(
        regrow_timer: float,
        regrow_time: float,
        family: str,
    ) -> str:
        """Return the regrowth stage name for a tree.

        Standard trees use a 3-stage map: sapling (<40%), young (<80%),
        mature (>=80%). Berry bushes use a simpler 2-stage map: young
        covers the whole regrowth period (no sapling stage).
        """
        if regrow_time <= 0:
            return "mature"
        progress = 1.0 - (regrow_timer / regrow_time)
        # Berry bushes skip the sapling stage (2-stage map).
        if family == "bush":
            if progress < 0.01:
                return "depleted"
            return "young"
        if progress < 0.40:
            return "sapling"
        elif progress < 0.80:
            return "young"
        return "mature"

    # ── Monster rendering ───────────────────────────────────────────

    _MONSTER_COLOURS: dict[str, tuple[int, int, int]] = {
        "wolf": (160, 160, 160),
        "bear": (100, 60, 30),
        "goblin": (60, 140, 60),
        "poison_frog": (180, 220, 50),
        "crocodile": (50, 100, 50),
        "swamp_drake": (80, 120, 80),
        "scorpion": (180, 140, 50),
        "sand_worm": (200, 180, 120),
        "djinn": (200, 150, 50),
        "stone_golem": (140, 140, 150),
        "eagle": (120, 80, 40),
        "cave_troll": (100, 110, 80),
        "boar": (120, 80, 50),
        "snake": (80, 160, 60),
        "hawk": (140, 120, 80),
        "crab": (200, 100, 80),
        "sea_serpent": (50, 100, 160),
    }

    _NPC_COLOURS: dict[str, tuple[int, int, int]] = {
        "merchant": (100, 180, 100),
        "quest_giver": (100, 140, 200),
        "faction_leader": (200, 100, 100),
        "recruit": (200, 180, 80),
    }

    def render_monster(
        self,
        screen: pygame.Surface,
        monster: object,
        camera: object,
    ) -> None:
        """
        Draw a monster sprite as a billboard with health bar.

        Monsters do not have a fixed tile position; elevation 0 is used.

        Parameters
        ----------
        screen : pygame.Surface
            The display surface.
        monster : Monster
            The monster entity (must have ``world_x``, ``world_y``,
            ``sprite_key``, ``hp``, ``max_hp``, ``monster_id``).
        camera : Camera
            The orbital camera.
        """
        world_x = monster.world_x
        world_y = monster.world_y

        # Get player position from camera for distance calculations.
        player_x = 0.0
        player_y = 0.0
        if hasattr(camera, "player") and camera.player is not None:
            player_x = camera.player.world_x
            player_y = camera.player.world_y

        # Zoom: scale sprite so it matches zoomed world
        zoom = camera.zoom if hasattr(camera, "zoom") else 1.0

        # LOD culling: skip if beyond fog cull distance.
        if self._should_cull(world_x, world_y, player_x, player_y):
            return

        # Monsters have no fixed tile — use elevation 0
        screen_x, screen_y = camera.world_to_screen(world_x, world_y, elevation=0)

        cy = int(screen_y - 12)
        cx = int(screen_x)

        # Determine sprite size for health bar positioning
        sprite = self._get_sprite(f"monster/{monster.monster_id}")
        # Scale sprite by zoom
        if sprite is not None and zoom != 1.0:
            scaled_w = max(4, int(sprite.get_width() * zoom))
            scaled_h = max(4, int(sprite.get_height() * zoom))
            sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
        size = sprite.get_width() if sprite is not None else int(14 * zoom)

        if sprite is not None:
            # Apply seasonal tint if available
            if self.seasonal_renderer is not None:
                tint_color = self._get_season_tint(tier=2)
                sprite = self._apply_seasonal_tint(sprite, tint_color, alpha=30)

            rect = sprite.get_rect(center=(cx, cy))
            screen.blit(sprite, rect)
            # Apply fog overlay
            fog_a = self._fog_alpha(world_x, world_y, player_x, player_y)
            if fog_a > 0:
                self._apply_fog_overlay(screen, rect, fog_a)
        else:
            # Fallback: colored circle based on monster_id
            colour = self._MONSTER_COLOURS.get(monster.monster_id, (200, 50, 50))
            # Apply seasonal tint to fallback colors
            if self.seasonal_renderer is not None:
                tint_color = self._get_season_tint(tier=2)
                r = int(colour[0] * (1 - 0.1))
                g = int(colour[1] * (1 - 0.05))
                b = int(colour[2] * (1 - 0.1))
                colour = (
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                )
            pygame.draw.circle(screen, colour, (cx, cy), max(1, size))
            darkened = self._darken(colour, 40)
            pygame.draw.circle(screen, darkened, (cx, cy), max(1, size), 2)

        # Health bar above monster (scaled by zoom)
        hp_pct = monster.hp / monster.max_hp if monster.max_hp > 0 else 0
        bar_width = int(30 * zoom)
        bar_height = max(1, int(3 * zoom))
        bar_x = cx - bar_width // 2
        bar_y = cy - size - int(8 * zoom)
        # Background
        pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        # Fill
        hp_color = (60, 180, 60) if hp_pct > 0.5 else (200, 60, 60)
        pygame.draw.rect(
            screen, hp_color,
            (bar_x, bar_y, int(bar_width * hp_pct), bar_height),
        )

    # ── NPC rendering ───────────────────────────────────────────

    def render_npc(
        self,
        screen: pygame.Surface,
        npc,
        camera: Camera,
        elevation: int = 0,
    ) -> None:
        """Render an NPC billboard sprite with fallback colored placeholder."""
        npc_x = int(npc.world_x // self.TILE_SIZE)
        npc_y = int(npc.world_y // self.TILE_SIZE)

        # Get player position from camera for distance calculations.
        player_x = 0.0
        player_y = 0.0
        if hasattr(camera, "player") and camera.player is not None:
            player_x = camera.player.world_x
            player_y = camera.player.world_y

        # Zoom: scale sprite so it matches zoomed world
        zoom = camera.zoom if hasattr(camera, "zoom") else 1.0

        # LOD culling: skip if beyond fog cull distance.
        if self._should_cull(npc.world_x, npc.world_y, player_x, player_y):
            return

        if self.tile_map is not None:
            corner_h = self.tile_map.get_tile_center_height(npc_x, npc_y)
            screen_x, screen_y = camera.world_to_screen(
                npc.world_x, npc.world_y, elevation=corner_h * Z_SCALE,
            )
            elevation_offset = 0.0  # Already baked in via camera
        else:
            # Fallback to original behavior.
            screen_x, screen_y = camera.world_to_screen(npc.world_x, npc.world_y)
            elevation_offset = elevation * 3

        # Try recruit_sprite_key first if recruited, then fall back to npc_type
        if getattr(npc, "is_recruited", False) and getattr(npc, "recruit_sprite_key", ""):
            sprite_key = f"npcs/{npc.recruit_sprite_key}"
        else:
            sprite_key = f"npcs/{npc.npc_type}"
        sprite = self._get_sprite(sprite_key)

        if sprite is not None:
            # Scale sprite by zoom
            if zoom != 1.0:
                scaled_w = max(4, int(sprite.get_width() * zoom))
                scaled_h = max(4, int(sprite.get_height() * zoom))
                sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))

            # Apply seasonal tint if available
            if self.seasonal_renderer is not None:
                npc_type = getattr(npc, "npc_type", "unknown")
                tier = 2 if npc_type in ("merchant", "quest_giver") else 3
                tint_color = self._get_season_tint(tier=tier)
                sprite = self._apply_seasonal_tint(sprite, tint_color, alpha=35)

            rect = sprite.get_rect(center=(screen_x, screen_y - elevation_offset))
            screen.blit(sprite, rect)
            # Apply fog overlay
            fog_a = self._fog_alpha(npc.world_x, npc.world_y, player_x, player_y)
            if fog_a > 0:
                self._apply_fog_overlay(screen, rect, fog_a)
        else:
            # Fallback: colored ellipse (scaled by zoom)
            color = self._NPC_COLOURS.get(npc.npc_type, (200, 200, 200))
            radius = int(14 * zoom)
            ellipse_rect = pygame.Rect(screen_x - radius, screen_y - elevation_offset - radius, radius * 2, radius * 2)
            pygame.draw.ellipse(screen, color, ellipse_rect)

        # Visual indicator: green outline for recruited NPCs
        if getattr(npc, "is_recruited", False):
            outline_color = (50, 200, 50)  # Green outline
            outline_rect = pygame.Rect(
                screen_x - radius - 2,
                screen_y - elevation_offset - radius - 2,
                radius * 2 + 4,
                radius * 2 + 4,
            )
            pygame.draw.rect(screen, outline_color, outline_rect, 2)

    def render_proximity_prompt(
        self,
        screen: pygame.Surface,
        npc,
        camera: Camera,
    ) -> None:
        """Render interaction prompt above an NPC when player is nearby.
        Prompt text varies by NPC type:
        - merchant: "[E] Trade with {name}"
        - quest_giver: "[E] Talk to {name}"
        - faction_leader: "[E] Speak with {name}"
        - recruit: "[E] Recruit {name}"
        - default: "[E] Talk to {name}"
        """
        npc_x = int(npc.world_x // self.TILE_SIZE)
        npc_y = int(npc.world_y // self.TILE_SIZE)
        elevation = 0.0
        if self.tile_map is not None:
            elevation = self.tile_map.get_tile_center_height(npc_x, npc_y) * Z_SCALE
        screen_x, screen_y = camera.world_to_screen(npc.world_x, npc.world_y, elevation=elevation)

        npc_type = getattr(npc, "npc_type", "unknown")
        prompt_text = "[E] Talk to " + npc.name  # default

        if npc_type == "merchant":
            prompt_text = "[E] Trade with " + npc.name
        elif npc_type == "quest_giver":
            prompt_text = "[E] Talk to " + npc.name
        elif npc_type == "faction_leader":
            prompt_text = "[E] Speak with " + npc.name
        elif npc_type == "recruit":
            prompt_text = "[E] Recruit " + npc.name

        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 14)

        text_surface = self._font.render(prompt_text, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(screen_x, screen_y - 40))

        # Semi-transparent background
        bg_rect = text_rect.inflate(10, 6)
        bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 128))
        screen.blit(bg_surface, bg_rect)
        screen.blit(text_surface, text_rect)

    # ── Fire rendering ────────────────────────────────────────────

    def render_fire(
        self,
        screen: pygame.Surface,
        fire: object,
        camera: object,
    ) -> None:
        """
        Draw a fire entity with a glowing flame effect.

        Parameters
        ----------
        screen : pygame.Surface
            The display surface.
        fire : FireEntity
            The fire entity (must have ``world_x``, ``world_y``,
            ``heat_output``, ``burn_duration_remaining``, ``burn_duration_total``).
        camera : Camera
            The orbital camera.
        """
        world_x = fire.world_x
        world_y = fire.world_y

        # Get player position from camera for distance calculations.
        player_x = 0.0
        player_y = 0.0
        if hasattr(camera, "player") and camera.player is not None:
            player_x = camera.player.world_x
            player_y = camera.player.world_y

        # Zoom: scale fire by camera zoom
        zoom = camera.zoom if hasattr(camera, "zoom") else 1.0

        # LOD culling: skip if beyond fog cull distance.
        if self._should_cull(world_x, world_y, player_x, player_y):
            return

        # Get tile center height for Z-aware positioning.
        if self.tile_map is not None:
            fx = int(world_x // self.TILE_SIZE)
            fy = int(world_y // self.TILE_SIZE)
            corner_h = self.tile_map.get_tile_center_height(fx, fy)
            screen_x, screen_y = camera.world_to_screen(world_x, world_y, elevation=corner_h * Z_SCALE)
        else:
            # Fallback to original behavior.
            screen_x, screen_y = camera.world_to_screen(world_x, world_y)

        cx = int(screen_x)
        cy = int(screen_y - 8)

        # Fire radius in screen pixels (based on heat_output, scaled by zoom)
        base_radius = int(20 * zoom)
        radius = int(base_radius * fire.heat_output)

        # Flicker effect: oscillate radius and color based on time
        t = time.time()
        flicker = math.sin(t * 8) * 0.15 + math.sin(t * 13) * 0.1
        radius = int(radius * (1 + flicker))

        # Outer glow (large, transparent)
        glow_radius = int(radius * 2.5)
        if glow_radius > 0:
            glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            alpha = int(40 + 20 * math.sin(t * 6))
            # Fog reduces glow visibility at distance
            fog_a = self._fog_alpha(world_x, world_y, player_x, player_y)
            if fog_a > 0:
                # Scale down glow alpha with fog density
                effective_glow_alpha = int(alpha * (1 - fog_a / 255))
            else:
                effective_glow_alpha = alpha
            
            pygame.draw.circle(
                glow_surf, (255, 150, 30, effective_glow_alpha),
                (glow_radius, glow_radius), glow_radius,
            )
            screen.blit(glow_surf, (cx - glow_radius, cy - glow_radius))
            
            # Apply fog overlay to the entire fire area
            fire_rect = pygame.Rect(cx - glow_radius, cy - glow_radius, glow_radius * 2, glow_radius * 2)
            if fog_a > 0:
                self._apply_fog_overlay(screen, fire_rect, fog_a)

        # Middle flame (orange-red) — scaled by zoom
        mid_radius = max(1, int(radius * 0.7))
        if mid_radius > 0:
            color_mid = (255, int(120 + 40 * math.sin(t * 10)), 20)
            pygame.draw.circle(screen, color_mid, (cx, cy), mid_radius)

        # Inner flame (yellow-white) — scaled by zoom
        inner_radius = max(1, int(radius * 0.35))
        if inner_radius > 0:
            color_inner = (255, int(220 + 35 * math.sin(t * 15)), int(50 + 50 * math.sin(t * 8)))
            pygame.draw.circle(screen, color_inner, (cx, cy - int(4 * zoom)), inner_radius)

        # Smoke wisps when fire is dying (last 20% burn time) — scaled by zoom
        if fire.burn_duration_total > 0:
            burn_pct = fire.burn_duration_remaining / fire.burn_duration_total
            if burn_pct < 0.2:
                smoke_alpha = int(80 * (1 - burn_pct) * 5)
                smoke_radius = int((5 + (0.2 - burn_pct) * 20) * zoom)
                for offset in range(3):
                    sx = cx + int(math.sin(t * 2 + offset * 2) * smoke_radius)
                    sy = cy - int((offset + 1) * 12 * zoom + t * 10)
                    if smoke_radius > 0 and sy > 0:
                        smoke_surf = pygame.Surface((smoke_radius * 2, smoke_radius * 2), pygame.SRCALPHA)
                        pygame.draw.circle(smoke_surf, (150, 150, 150, smoke_alpha),
                                         (smoke_radius, smoke_radius), smoke_radius)
                        screen.blit(smoke_surf, (sx - smoke_radius, sy - smoke_radius))

    # ── Structure rendering ─────────────────────────────────────────

    _STRUCTURE_COLOURS: dict[str, tuple[int, int, int]] = {
        "campfire": (200, 120, 30),
        "chest": (160, 120, 60),
        "furnace": (100, 100, 110),
        "cooking_station": (120, 100, 80),
        "drying_rack": (140, 120, 80),
        "smelter": (90, 90, 100),
        "stone_wall": (130, 130, 140),
        "wooden_gate": (140, 100, 50),
        "iron_gate": (100, 100, 110),
        "stone_wall_tower": (140, 140, 150),
        "wooden_trap": (120, 90, 40),
        "iron_trap": (80, 80, 90),
        "ballista": (120, 100, 60),
        "trebuchet": (100, 90, 60),
        "tapestry": (160, 100, 160),
        "lantern": (200, 180, 100),
        "garden_plot": (80, 140, 60),
        "stone_bench": (130, 130, 140),
    }

    def render_structure(
        self,
        screen: pygame.Surface,
        structure: object,
        camera: object,
    ) -> None:
        """
        Draw a structure sprite as a billboard.

        Parameters
        ----------
        screen : pygame.Surface
            The display surface.
        structure : Structure
            The structure entity (must have ``world_x``, ``world_y``,
            ``structure_def``, ``hp``, ``max_hp``).
        camera : Camera
            The orbital camera.
        """
        world_x = structure.world_x
        world_y = structure.world_y

        # Get player position from camera for distance calculations.
        player_x = 0.0
        player_y = 0.0
        if hasattr(camera, "player") and camera.player is not None:
            player_x = camera.player.world_x
            player_y = camera.player.world_y

        # Zoom: scale sprite so it matches zoomed world
        zoom = camera.zoom if hasattr(camera, "zoom") else 1.0

        # LOD culling: skip if beyond fog cull distance.
        if self._should_cull(world_x, world_y, player_x, player_y):
            return

        # Get tile center height for Z-aware positioning.
        if self.tile_map is not None:
            sx = int(world_x // self.TILE_SIZE)
            sy = int(world_y // self.TILE_SIZE)
            corner_h = self.tile_map.get_tile_center_height(sx, sy)
            screen_x, screen_y = camera.world_to_screen(world_x, world_y, elevation=corner_h * Z_SCALE)
        else:
            # Fallback to original behavior.
            screen_x, screen_y = camera.world_to_screen(world_x, world_y)

        cy = int(screen_y - 8)
        cx = int(screen_x)

        # Try to load structure sprite
        sprite = self._get_sprite(f"structure/{structure.structure_def.structure_id}")
        base_size = 16 if structure.structure_def.occupies_tile else 12
        size = int(base_size * zoom)

        if sprite is not None:
            # Scale sprite by zoom
            if zoom != 1.0:
                scaled_w = max(4, int(sprite.get_width() * zoom))
                scaled_h = max(4, int(sprite.get_height() * zoom))
                sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
            rect = sprite.get_rect(center=(cx, cy))
            screen.blit(sprite, rect)
            # Apply fog overlay
            fog_a = self._fog_alpha(world_x, world_y, player_x, player_y)
            if fog_a > 0:
                self._apply_fog_overlay(screen, rect, fog_a)
        else:
            # Fallback: draw generic shape based on structure type (scaled by zoom)
            colour = self._STRUCTURE_COLOURS.get(
                structure.structure_def.structure_id, (120, 120, 120),
            )

            if structure.structure_def.structure_type == "fixed":
                # Rectangle for fixed structures
                rect = pygame.Rect(cx - size, cy - size // 2, size * 2, size)
                pygame.draw.rect(screen, colour, rect, border_radius=max(1, int(3 * zoom)))
                pygame.draw.rect(screen, self._darken(colour, 30), rect, 2, border_radius=max(1, int(3 * zoom)))
            else:
                # Circle for portable structures
                pygame.draw.circle(screen, colour, (cx, cy), max(1, size))
                pygame.draw.circle(screen, self._darken(colour, 30), (cx, cy), max(1, size), 2)

        # HP bar if damaged (scaled by zoom)
        if structure.hp < structure.max_hp:
            hp_pct = structure.hp / structure.max_hp if structure.max_hp > 0 else 0
            bar_width = int(24 * zoom)
            bar_height = max(1, int(2 * zoom))
            bar_x = cx - bar_width // 2
            bar_y = cy - size - int(6 * zoom)
            hp_color = (60, 180, 60) if hp_pct > 0.5 else (200, 60, 60)
            pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
            pygame.draw.rect(
                screen, hp_color,
                (bar_x, bar_y, int(bar_width * hp_pct), bar_height),
            )
