"""game.py — Top-level game state container. Aggregates all subsystems."""

import math
import pygame
from typing import TYPE_CHECKING

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE,
    TARGET_FPS,
    FLAVOR_TEXTS,
    FIRE_INTERACTION_RADIUS_TILES,
    CAMPFIRE_SEARCH_RADIUS_TILES,
    INITIAL_MONSTER_SPAWN_RADIUS_TILES,
    AUTOSAVE_INTERVAL,
    TILE_SIZE,
    FOG_COLOR,
    Z_SCALE, TERRAIN_HEIGHT_SCALE,
)

from core.state import GameState
from render import TileRenderer, SpriteRenderer
from actions import ActionState, ActionType
from input.panel_dispatcher import PanelDispatcher
from interactions.npc_flows import NPCFlows
from ui.title_screen import render_title_screen, handle_title_event
from ui.loading_screen import render_loading_screen, handle_loading_event
from ui.character_select import CharacterSelectPanel, render_character_select, handle_character_select_event

from world.biome import BiomeRegistry
from world.world_gen import generate as generate_world
from data import load_json, load_json_list

if TYPE_CHECKING:
    from world.tile_map import TileMap
    from survival.survival_system import SurvivalSystem
    from survival.food import FoodRegistry
    from skills.skill_manager import SkillManager
    from crafting.crafting_system import CraftingSystem
    from inventory.inventory import Inventory
    from camera import Camera
    from ui.hud import HUD
    from core.save_system import SaveSystem
    from input.input_manager import InputManager
    from input.router import InputRouter
    from interactions.fire import FireInteraction
    from interactions.interact import InteractSystem


class Game:
    """Central game state. Single instance, aggregates all subsystems."""

    SUCCESS_COLOR = (100, 255, 100)
    ERROR_COLOR = (180, 100, 100)

    __slots__ = (
        "seed", "screen", "clock", "state", "dt",
        "loading_progress", "death_count",
        "world", "player", "survival", "food_registry",
        "skill_manager", "crafting", "inventory",
        "camera", "hud", "save_system", "input_manager",
        "_inventory_panel", "_skill_panel", "_crafting_panel",
        "_gear_panel", "_building_panel", "_dashboard",
        "build_mode", "_building_pending_id",
        "_trade_panel", "_quest_panel", "_recruit_panel", "_diplomacy_panel",
        "quest_system", "faction_system",
        "combat_system", "firemaking", "metallurgy",
        "intelligence", "cooking", "building_system", "construction",
        "npc_system", "trade_system", "recruitment_system",
        "_autosave_timer", "_panel_dispatcher",
        "_fire_interaction", "_interact_system",
        "season_system", "weather_system",
        "particle_system", "seasonal_renderer",
        "_tile_renderer", "_sprite_renderer",
        "_title_selection_index", "_save_slots", "_flavor_text",
        "_build_cursor", "_input_router", "_npc_flows", "_bootstrap",
        "_character_select_panel", "_pending_character_def",
        "lighting_system",
        "woodcutting", "mining", "foraging",
        "_world_gen_thread", "_world_gen_result", "_world_gen_error",
    )

    def __init__(self, seed: int = 42) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.seed = seed
        self.state = GameState.TITLE
        self.dt = 0.0
        self.loading_progress = 0.0
        self._autosave_timer = 0.0
        self.death_count = 0
        self.world: "TileMap | None" = None
        self.player: object | None = None
        self.survival: "SurvivalSystem | None" = None
        self.food_registry: "FoodRegistry | None" = None
        self.skill_manager: "SkillManager | None" = None
        self.crafting: "CraftingSystem | None" = None
        self.inventory: "Inventory | None" = None
        self.camera: "Camera | None" = None
        self.hud: "HUD | None" = None
        self.save_system: "SaveSystem | None" = None
        self.input_manager: "InputManager | None" = None
        self._inventory_panel = None
        self._skill_panel = None
        self._crafting_panel = None
        # B4 (Phase 5): build_mode is a PLAYING sub-state — selecting a
        # structure closes the panel and enters placement mode; left-click
        # places, right-click / ESC cancels.
        self.build_mode = False
        self._building_pending_id: "str | None" = None
        self.combat_system = None
        self.firemaking = None
        self.metallurgy = None
        self.intelligence = None
        self.building_system = None
        self.construction = None
        self.npc_system = None
        self.trade_system = None
        self.recruitment_system = None
        self._building_panel = None
        self._dashboard = None
        self._gear_panel = None
        self._trade_panel = None
        self._character_select_panel = None
        self._pending_character_def = None
        self.quest_system = None
        self.faction_system = None
        self._quest_panel = None
        self._fire_interaction = None
        self._interact_system = None
        self._tile_renderer = TileRenderer(None, None)
        self._sprite_renderer = SpriteRenderer()
        self._title_selection_index = 0
        self._save_slots: list[dict] = []
        self._input_router = None
        self.season_system = None
        self.weather_system = None
        self.particle_system = None
        self.seasonal_renderer = None
        self._flavor_text = ""
        self._build_cursor = None
        self._world_gen_thread = None
        self._world_gen_result = None
        self._world_gen_error = None
        from core.save_system import SaveSystem
        self.save_system = SaveSystem()
        self._npc_flows = NPCFlows(self)
        self._panel_dispatcher = PanelDispatcher(self)
        from interactions.fire import FireInteraction
        from interactions.interact import InteractSystem
        self._fire_interaction = FireInteraction(self)
        self._interact_system = InteractSystem(self)

        # Phase 6: Lighting coordinator
        from render.lighting_system import LightingSystem
        self.lighting_system = None  # Set by Bootstrap._wire_phase4

        from core.bootstrap import Bootstrap
        self._bootstrap = Bootstrap(self, None)

    def set_state(self, new_state: GameState) -> None:
        if self.state == new_state:
            return
        old_state = self.state
        self.state = new_state
        if self._input_router is not None:
            if new_state == GameState.PLAYING:
                self._input_router._close_all_panels()
            elif self._input_router._is_panel_state(old_state) and self._input_router._is_panel_state(new_state):
                self._input_router._close_all_panels()
        if (
            old_state == GameState.DASHBOARD_OPEN
            and new_state != GameState.DASHBOARD_OPEN
            and self._dashboard is not None
        ):
            self._dashboard.visible = False
        if new_state == GameState.INVENTORY_OPEN:
            self._inventory_panel.visible = True
        elif new_state == GameState.SKILL_PANEL:
            self._skill_panel.visible = True
        elif new_state == GameState.CRAFTING_PANEL:
            self._crafting_panel.visible = True
        elif new_state == GameState.BUILDING_PANEL:
            self._building_panel.visible = True
        elif new_state == GameState.GEAR_PANEL:
            self._gear_panel.visible = True
        elif new_state == GameState.TRADE_PANEL:
            self._trade_panel.visible = True
        elif new_state == GameState.QUEST_PANEL:
            self._quest_panel.visible = True
        elif new_state == GameState.RECRUIT_PANEL:
            self._recruit_panel.visible = True
            # NOTE: no close_session() here — the session is opened by
            # NPCFlows.open_recruit_panel BEFORE set_state(RECRUIT_PANEL), so
            # wiping it here would leave the panel open with no recruit data.
        elif new_state == GameState.DIPLOMACY_PANEL:
            self._diplomacy_panel.visible = True
        elif new_state == GameState.DASHBOARD_OPEN and self._dashboard is not None:
            self._dashboard.visible = True
        elif new_state == GameState.CHARACTER_SELECT:
            if self._character_select_panel is None:
                self._character_select_panel = CharacterSelectPanel()
                self._character_select_panel.set_confirm_callback(lambda cd: None)  # handled via event
            self._character_select_panel.visible = True
        if (old_state == GameState.TITLE or old_state == GameState.CHARACTER_SELECT) and new_state == GameState.LOADING:
            self._bootstrap.begin_world_gen()
        elif old_state == GameState.TITLE and new_state == GameState.LOADING_SAVE:
            self._bootstrap.load_save()
        elif new_state == GameState.PLAYING and old_state in (GameState.LOADING, GameState.LOADING_SAVE):
            self._bootstrap.on_world_gen_complete()

    def open_dashboard(self, tab: str) -> None:
        """Open the unified dashboard on the given tab (or switch tabs when open)."""
        if self._dashboard is None:
            return
        self._dashboard.set_active(tab)
        if self.state != GameState.DASHBOARD_OPEN:
            self.set_state(GameState.DASHBOARD_OPEN)

    def check_world_gen_complete(self) -> None:
        """Check if background world generation has completed and transition state."""
        if self.state not in (GameState.LOADING, GameState.LOADING_SAVE):
            return
        if self._world_gen_thread is not None and self._world_gen_thread.is_alive():
            return  # Still running
        
        # Thread has finished (or never started)
        if self._world_gen_error is not None:
            self.state = GameState.ERROR
        elif self._world_gen_result == "success":
            self.set_state(GameState.PLAYING)
        else:
            # Thread finished but no result (shouldn't happen)
            self.state = GameState.ERROR
            self._world_gen_error = "World generation failed silently"

    def update(self, dt: float) -> None:
        self.dt = dt
        if self.survival is not None:
            self.survival.tick(dt)
        if self.inventory is not None and self.player is not None:
            spoilage_messages = self.inventory.tick(dt)
            for msg in spoilage_messages:
                self.player.action_system.add_notification(msg, (255, 200, 50))
        if self.state == GameState.PLAYING and self.save_system is not None:
            self._autosave_timer += dt
            if self._autosave_timer >= AUTOSAVE_INTERVAL:
                self._autosave_timer = 0.0
                self.save_system.save(self, slot=0)
        if self.state == GameState.PLAYING:
            if self.world is not None:
                self.world.update(dt)
            if self.player is not None and self.input_manager is not None:
                camera_yaw = self.camera.yaw if self.camera is not None else 0.0
                self.player.apply_key_input(self.input_manager.input_state, self.dt, camera_yaw)
                self.player.update(dt)
            if self.world is not None and self.player is not None and self.survival is not None:
                current_tile = self.world.get_tile(*self.player.get_tile_position())
                self.survival.update_from_tile(current_tile)
            if self.player is not None and self.inventory is not None and self.skill_manager is not None:
                action_sys = self.player.action_system
                if action_sys is not None:
                    result = action_sys.update(dt)
                    action_sys.process_completion(result, self.inventory, self.skill_manager, self.food_registry)
                    action_sys.update_notifications(dt)
            if self.hud is not None:
                action_sys = self.player.action_system if self.player else None
                if action_sys is not None:
                    self.hud.set_notifications(action_sys.notifications)
                    if action_sys.active.state == ActionState.RUNNING:
                        skill_name = "Woodcutting" if action_sys.active.action_type == ActionType.WOODCUTTING else "Mining"
                        self.hud.set_action_progress(action_sys.active.progress, skill_name)
                    else:
                        self.hud.set_action_progress(0.0, "")
                self.hud.tick_notifications(dt)
            if self.camera is not None and self.input_manager is not None:
                self.camera.update(dt, self.input_manager.input_state)
            if self.combat_system is not None:
                self.combat_system.tick(dt)
            if self.firemaking is not None:
                self.firemaking.tick(dt)
            if self.building_system is not None:
                self.building_system.tick(dt, combat_system=self.combat_system)
            if self.npc_system is not None:
                self.npc_system.tick(dt)
            if self.recruitment_system is not None:
                self.recruitment_system.tick(dt)
            if self.npc_system is not None:
                self.npc_system.tick_faction_npcs(dt)
            if self.trade_system is not None:
                self.trade_system.tick(dt)
            if self.quest_system is not None:
                self.quest_system.tick(dt, self.player, self.world)
            if self.weather_system is not None:
                self.weather_system.tick(dt)
            if self.season_system is not None:
                self.season_system.tick(dt)
            if self.seasonal_renderer is not None and self.season_system is not None:
                self.seasonal_renderer.sync(self.season_system.season_progress,
                    self.season_system.current_season, self.season_system.previous_season)
            if self.particle_system is not None and self.weather_system is not None:
                self.particle_system.sync(self.weather_system.current_weather)
                self.particle_system.update(dt)
            # Phase 6: Update lighting from season + weather
            if self.lighting_system is not None:
                if self.season_system is not None:
                    self.lighting_system.update_from_season(self.season_system)
                if self.weather_system is not None:
                    self.lighting_system.update_from_weather(self.weather_system)

        # One-shot input flags (wheel zoom, click-to-move, panel toggles)
        # are consumed during this update; clear them at the END of the
        # frame so consumers actually see them before the reset.
        if self.input_manager is not None:
            self.input_manager.clear_frame()

    def render(self, screen: pygame.Surface) -> None:
        if self.state == GameState.TITLE:
            render_title_screen(self, screen)
        elif self.state == GameState.CHARACTER_SELECT:
            render_character_select(self, screen)
        elif self.state in (GameState.LOADING, GameState.LOADING_SAVE, GameState.ERROR):
            render_loading_screen(self, screen)
        else:
            self.render_game(screen)

    def render_game(self, screen: pygame.Surface) -> None:
        screen.fill(FOG_COLOR)
        if self._tile_renderer is not None and self.camera is not None:
            self._tile_renderer.render(self.camera)

        # Collect all sprite drawables with their depth sort key (distance
        # along the camera's view axis, so the painter's order stays correct
        # when yaw rotates) so entities behind others are drawn first.
        drawables: list[tuple[float, callable]] = []
        if self.camera is not None:
            _cy = math.cos(self.camera.yaw)
            _sy = math.sin(self.camera.yaw)

            def depth_of(world_x: float, world_y: float, elevation: float = 0.0) -> float:
                # Matches TileRenderer's per-tile depth: rotate by yaw, plus a
                # small elevation nudge so higher ground sorts slightly nearer.
                return world_y * _cy + world_x * _sy + elevation * 0.5
        else:
            def depth_of(world_x: float, world_y: float, elevation: float = 0.0) -> float:
                return world_y

        if self._sprite_renderer is not None and self.world is not None and self.camera is not None:
            left, top, right, bottom = self.camera.get_view_rect()
            x_min, x_max = max(0, int(left // TILE_SIZE)), min(self.world.width, int(right // TILE_SIZE) + 1)
            y_min, y_max = max(0, int(top // TILE_SIZE)), min(self.world.height, int(bottom // TILE_SIZE) + 1)
            for x in range(x_min, x_max):
                for y in range(y_min, y_max):
                    tile = self.world.tiles[x][y]
                    if tile is not None and tile.resource_node is not None:
                        # Sort by yaw-rotated depth of the tile center
                        sort_y = depth_of((x + 0.5) * TILE_SIZE,
                                          (y + 0.5) * TILE_SIZE,
                                          tile.elevation * Z_SCALE)
                        drawables.append((
                            sort_y,
                            lambda s=screen, n=tile.resource_node, c=self.camera, e=tile.elevation, tx=x, ty=y:
                                self._sprite_renderer.render_resource(s, n, c, e, tile_x=tx, tile_y=ty),
                        ))

        if self._sprite_renderer is not None and self.player is not None and self.camera is not None and self.world is not None:
            tx, ty = self.player.get_tile_position()
            tile = self.world.get_tile(tx, ty)
            sort_y = depth_of(self.player.world_x, self.player.world_y,
                              (tile.elevation if tile else 0) * Z_SCALE)
            drawables.append((
                sort_y,
                lambda s=screen, p=self.player, c=self.camera, e=(tile.elevation if tile else 0), dt=self.dt:
                    self._sprite_renderer.render_player(s, p, c, e, dt),
            ))

        if self._sprite_renderer is not None and self.combat_system is not None and self.camera is not None:
            for monster in self.combat_system.monsters:
                if monster.is_alive():
                    sort_y = depth_of(monster.world_x, monster.world_y)
                    drawables.append((
                        sort_y,
                        lambda s=screen, m=monster, c=self.camera:
                            self._sprite_renderer.render_monster(s, m, c),
                    ))

        if self._sprite_renderer is not None and self.npc_system is not None and self.player is not None:
            nearby_npc = self.npc_system.check_proximity(self.player)
            for npc in self.npc_system.npcs:
                if not npc.is_active:
                    continue
                sort_y = depth_of(npc.world_x, npc.world_y)
                drawables.append((
                    sort_y,
                    lambda s=screen, n=npc, c=self.camera:
                        self._sprite_renderer.render_npc(s, n, c, elevation=0),
                ))
                if npc is nearby_npc:
                    drawables.append((
                        sort_y,
                        lambda s=screen, n=npc, c=self.camera:
                            self._sprite_renderer.render_proximity_prompt(s, n, c),
                    ))

        if self._sprite_renderer is not None and self.building_system is not None and self.camera is not None:
            for structure in self.building_system.structures:
                if structure.is_active:
                    sort_y = depth_of(structure.world_x, structure.world_y)
                    drawables.append((
                        sort_y,
                        lambda s=screen, st=structure, c=self.camera:
                            self._sprite_renderer.render_structure(s, st, c),
                    ))

        # Build-mode ghost preview (a PLAYING sub-state): translucent marker
        # under the cursor showing where the next structure will land.
        if self.build_mode and self.camera is not None and self.world is not None and self._build_cursor is not None:
            drawables.append((
                float('inf'),  # Always drawn last (on top)
                lambda s=screen: self._render_build_ghost(s),
            ))

        if self._sprite_renderer is not None and self.firemaking is not None and self.camera is not None:
            for fire in self.firemaking.get_active_fires():
                sort_y = depth_of(fire.world_x, fire.world_y)
                drawables.append((
                    sort_y,
                    lambda s=screen, f=fire, c=self.camera:
                        self._sprite_renderer.render_fire(s, f, c),
                ))

        # Sort by depth (Y coordinate) so entities "behind" are drawn first
        drawables.sort(key=lambda d: d[0])
        for _, draw_fn in drawables:
            draw_fn()

        if self.particle_system is not None:
            self.particle_system.draw(screen)
        if self.seasonal_renderer is not None:
            self.seasonal_renderer.draw_ambient_overlay(screen, alpha=20)
        if self.combat_system is not None and self.camera is not None:
            from combat.combat_ui import render_damage_numbers
            from render.font_cache import get_monospace_bold
            font = get_monospace_bold(16)
            render_damage_numbers(screen, self.combat_system.damage_numbers, self.camera, font)
            if self.combat_system.damage_numbers:
                latest = self.combat_system.damage_numbers[-1]
                if latest.value < 0 and self.hud is not None:
                    self.hud.trigger_damage_flash()
        if self.state == GameState.INVENTORY_OPEN and self._inventory_panel is not None:
            self._inventory_panel.render(screen)
        elif self.state == GameState.DASHBOARD_OPEN and self._dashboard is not None:
            self._dashboard.render(screen)
        elif self.state == GameState.SKILL_PANEL and self._skill_panel is not None:
            self._skill_panel.render(screen)
        elif self.state == GameState.CRAFTING_PANEL and self._crafting_panel is not None:
            self._crafting_panel.render(screen)
        elif self.state == GameState.BUILDING_PANEL and self._building_panel is not None:
            self._building_panel.render(screen, self.building_system, self.skill_manager)
        elif self.state == GameState.GEAR_PANEL and self._gear_panel is not None:
            from combat.gear import GearItem
            self._gear_panel.render(screen, self.player.gear, self.inventory, GearItem.load_all())
        elif self.state == GameState.TRADE_PANEL and self._trade_panel is not None:
            self._trade_panel.render(screen)
        elif self.state == GameState.QUEST_PANEL and self._quest_panel is not None:
            self._quest_panel.render(screen)
        elif self.state == GameState.RECRUIT_PANEL and self._recruit_panel is not None:
            self._recruit_panel.render(screen)
        elif self.state == GameState.DIPLOMACY_PANEL and self._diplomacy_panel is not None:
            self._diplomacy_panel.render(screen)
        # HUD is drawn last so its bars/overlays are never occluded by the
        # entity sprites, the seasonal overlay, or an open panel above.
        if self.hud is not None:
            self.hud.render(screen)

    def _render_build_ghost(self, screen: pygame.Surface) -> None:
        """Draw a translucent marker at the tile under the build cursor."""
        if self._build_cursor is None or self.camera is None or self.world is None:
            return
        mx, my = self._build_cursor
        tx = int(mx // TILE_SIZE)
        ty = int(my // TILE_SIZE)
        if self.world.get_tile(tx, ty) is None:
            return
        # Project the tile's footprint so the ghost follows yaw/pitch/zoom
        # and elevation exactly like the terrain beneath it.
        tile = self.world.get_tile(tx, ty)
        elev = getattr(tile, "elevation", 0) * Z_SCALE * TERRAIN_HEIGHT_SCALE
        corners = [
            self.camera.world_to_screen(tx * TILE_SIZE, ty * TILE_SIZE, elevation=elev),
            self.camera.world_to_screen((tx + 1) * TILE_SIZE, ty * TILE_SIZE, elevation=elev),
            self.camera.world_to_screen((tx + 1) * TILE_SIZE, (ty + 1) * TILE_SIZE, elevation=elev),
            self.camera.world_to_screen(tx * TILE_SIZE, (ty + 1) * TILE_SIZE, elevation=elev),
        ]
        min_x = min(c[0] for c in corners)
        min_y = min(c[1] for c in corners)
        max_x = max(c[0] for c in corners)
        max_y = max(c[1] for c in corners)
        if max_x < 0 or max_y < 0 or min_x > WINDOW_WIDTH or min_y > WINDOW_HEIGHT:
            return
        w = max(1, int(max_x - min_x) + 2)
        h = max(1, int(max_y - min_y) + 2)
        ghost = pygame.Surface((w, h), pygame.SRCALPHA)
        local = [(int(cx - min_x) + 1, int(cy - min_y) + 1) for cx, cy in corners]
        pygame.draw.polygon(ghost, (120, 220, 120, 90), local)
        pygame.draw.polygon(ghost, (180, 255, 180, 200), local, 2)
        screen.blit(ghost, (int(min_x), int(min_y)))

    def handle_event(self, event) -> None:
        if self.state == GameState.TITLE:
            handle_title_event(self, event)
        elif self.state == GameState.CHARACTER_SELECT:
            handle_character_select_event(self, event)
        elif self.state in (GameState.LOADING, GameState.LOADING_SAVE, GameState.ERROR):
            handle_loading_event(self, event)
        else:
            if self._input_router is not None:
                self._input_router.handle(event)

 
