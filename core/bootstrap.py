"""
core/bootstrap.py — Game subsystem initialization.

Extracted from Game._initialize_subsystems in Phase 3.5.7.
Builds all subsystems in dependency order and wires them together.

Usage:
    from core.bootstrap import Bootstrap
    bootstrap = Bootstrap(game, biome_registry)
    bootstrap.initialize()
"""

from __future__ import annotations

import json
from config import WINDOW_WIDTH, WINDOW_HEIGHT, TILE_SIZE
from data import load_json, load_json_list
from world.biome import BiomeRegistry
from world.world_gen import generate as generate_world
from core.state import GameState


class Bootstrap:
    """Wires and initializes all game subsystems in dependency order."""

    def __init__(self, game, biome_registry) -> None:
        """
        Args:
            game: The Game instance (accepts subsystem references).
            biome_registry: BiomeRegistry for environmental pressure lookup.
        """
        self.game = game
        self.biome_registry = biome_registry

    def initialize(self) -> None:
        """Run the full subsystem initialization pipeline."""
        self._build_inventory()
        self._build_survival()
        self._build_player_actions()
        self._build_food_registry()
        self._build_skill_manager()
        self._build_player_gear()
        self._build_crafting()
        self._build_camera()
        self._build_input_manager()
        self._build_input_router()
        self._build_phase2_skills()
        self._build_construction_and_building()
        self._build_npc_system()
        self._build_trade_system()
        self._build_trade_panel()
        self._build_recruitment_system()
        self._build_quest_system()
        self._build_faction_system()
        self._build_quest_panel()
        self._build_recruit_panel()
        self._build_diplomacy_panel()
        self._build_combat_system()
        # Route starvation death through the shared soft-death handler once
        # combat exists. Combat-triggered death still goes via take_damage's
        # return value; only starvation needed a bridge.
        if self.game.survival is not None and self.game.combat_system is not None:
            self.game.combat_system.set_player_death_handler(self.game.survival.on_death)
        self._spawn_initial_monsters()
        self._build_renderers()
        self._build_hud()
        self._build_ui_panels()
        self._wire_phase4()

    # ── Subsystem builders ──────────────────────────────────────────

    def _build_inventory(self) -> None:
        """Create inventory FIRST — needed by starter pack and subsystems."""
        from inventory.inventory import Inventory

        self.game.inventory = Inventory()

        # Wire the shared inventory into the player so player-facing
        # subsystems (combat loot, trade, quest rewards, recruitment) that
        # read `player.inventory` resolve to the same object the game owns.
        if self.game.player is not None:
            self.game.player.inventory = self.game.inventory

        # Register stack sizes from items data
        items_data = load_json_list("items.json", "items")
        for item in items_data:
            if "stack_size" in item:
                self.game.inventory.set_stack_size(item["id"], item["stack_size"])

    def _build_survival(self) -> None:
        """Initialize the survival system."""
        from survival.survival_system import SurvivalSystem

        start_tile = self.game.world.get_tile(
            self.game.world.spawn_x, self.game.world.spawn_y,
        )
        env_pressure = (
            start_tile.biome.environmental_pressure
            if start_tile and start_tile.biome
            else 1.0
        )
        self.game.survival = SurvivalSystem(
            environmental_pressure=env_pressure,
        )

    def _build_player_actions(self) -> None:
        """Wire the player's action system to the survival system."""
        from actions import ActionSystem

        self.game.player.action_system = ActionSystem()
        self.game.player.action_system.survival = self.game.survival

    def _build_food_registry(self) -> None:
        """Create the food registry from items data."""
        from survival.food import FoodRegistry

        items_data = load_json_list("items.json", "items")
        self.game.food_registry = FoodRegistry(items_data)

    def _build_skill_manager(self) -> None:
        """Initialize the skill manager."""
        from skills.skill_manager import SkillManager

        self.game.skill_manager = SkillManager()

    def _build_player_gear(self) -> None:
        """Create player gear and wire skill_manager to player."""
        from combat.gear import PlayerGear

        self.game.player.gear = PlayerGear()
        self.game.player.skill_manager = self.game.skill_manager
        self.game.player.survival = self.game.survival

    def _build_crafting(self) -> None:
        """Initialize the crafting system with a unified RecipeRegistry."""
        from crafting.crafting_system import CraftingSystem
        from crafting.recipe_registry import RecipeRegistry

        self._recipe_registry = RecipeRegistry()
        self._recipe_registry.load_all()
        self.game.crafting = CraftingSystem(recipe_registry=self._recipe_registry)

    def _build_camera(self) -> None:
        """Create the camera and attach it to the player."""
        from camera import Camera

        self.game.camera = Camera(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.game.camera.set_player(self.game.player)

    def _build_input_manager(self) -> None:
        """Initialize the input manager."""
        from input.input_manager import InputManager

        self.game.input_manager = InputManager()

    def _build_input_router(self) -> None:
        """Create the input router that delegates to panel dispatcher."""
        from input.router import InputRouter

        self.game._input_router = InputRouter(
            self.game, self.game.input_manager, self.game._panel_dispatcher,
        )

    def _build_hud(self) -> None:
        """Create the HUD overlay."""
        from ui.hud import HUD
        from ui.seasonal_hud import SeasonalHUD

        self.game.hud = HUD(
            self.game.screen,
            self.game.survival,
            self.game.inventory,
            self.game.faction_system,
            self.game.npc_system,
            self.game._sprite_renderer,
        )
        self.game.hud.set_player(self.game.player)
        # Create and wire SeasonalHUD for season/weather display
        seasonal_hud = SeasonalHUD()
        self.game.hud.set_seasonal_hud(seasonal_hud)
        # Wire season system for dynamic season/weather display
        if self.game.season_system is not None:
            self.game.hud.set_season_system(self.game.season_system)

    def _build_ui_panels(self) -> None:
        """Create base UI panels (inventory, skill, crafting, building)."""
        from ui.inventory_panel import InventoryPanel
        from ui.skill_panel import SkillPanel
        from ui.crafting_panel import CraftingPanel
        from ui.building_panel import BuildingPanel

        self.game._inventory_panel = InventoryPanel(self.game._sprite_renderer)
        self.game._inventory_panel.set_inventory(self.game.inventory)

        self.game._skill_panel = SkillPanel()
        self.game._skill_panel.set_skill_manager(self.game.skill_manager)

        self.game._crafting_panel = CraftingPanel()
        self.game._crafting_panel.set_crafting(self.game.crafting)
        self.game._crafting_panel.set_inventory(self.game.inventory)

        self.game._building_panel = BuildingPanel()
        self.game._building_panel.visible = False

    def _build_phase2_skills(self) -> None:
        """Initialize skills and wire them to the game."""
        from skills.metallurgy.metallurgy import MetallurgySkill
        from skills.firemaking.firemaking import FiremakingSkill
        from skills.intelligence.intelligence import IntelligenceSkill
        from skills.cooking.cooking import CookingSkill
        from ui.gear_panel import GearPanel

        self.game.metallurgy = MetallurgySkill(
            self.game.skill_manager, recipe_registry=self._recipe_registry,
        )
        self.game.firemaking = FiremakingSkill(self.game.skill_manager)
        self.game.intelligence = IntelligenceSkill(self.game.skill_manager)
        self.game.cooking = CookingSkill(self.game.skill_manager)

        self.game._gear_panel = GearPanel()
        self.game._gear_panel.visible = False

        # Wire metallurgy to crafting panel
        self.game._crafting_panel.set_metallurgy(self.game.metallurgy)

    def _build_construction_and_building(self) -> None:
        """Initialize construction and building system."""
        from skills.construction.construction import Construction
        from building.structure import StructureDef
        from building.building_system import BuildingSystem

        self.game.construction = Construction(self.game.skill_manager)
        structure_defs = StructureDef.load_all()
        self.game.building_system = BuildingSystem(
            self.game.skill_manager,
            self.game.inventory,
            self.game.construction,
            structure_defs,
            game_ref=self.game,
        )

    def _build_npc_system(self) -> None:
        """Initialize the NPC system and spawn NPCs."""
        from npc.npc_system import NPCSystem

        self.game.npc_system = NPCSystem(self.game.world)
        self.game.npc_system.game = self.game
        self.game.npc_system.spawn_npcs()

    def _build_trade_system(self) -> None:
        """Initialize the trade system."""
        from npc.trade_system import TradeSystem

        self.game.trade_system = TradeSystem(self.game.intelligence)
        self.game.trade_system.set_npc_system(self.game.npc_system)
        self.game.trade_system.load_trade_data()

    def _build_trade_panel(self) -> None:
        """Create the trade panel."""
        from ui.trade_panel import TradePanel

        self.game._trade_panel = TradePanel()
        self.game._trade_panel.set_trade_system(self.game.trade_system)
        self.game._trade_panel.set_inventory(self.game.inventory)
        self.game._trade_panel.visible = False

    def _build_recruitment_system(self) -> None:
        """Initialize the recruitment system."""
        from npc.recruitment import RecruitmentSystem

        self.game.recruitment_system = RecruitmentSystem(self.game)
        self.game.recruitment_system._building_system = self.game.building_system

    def _build_quest_system(self) -> None:
        """Initialize the quest system."""
        from npc.quest_system import QuestSystem

        self.game.quest_system = QuestSystem(self.game.intelligence)
        self.game.quest_system.load_quest_data()
        self.game.quest_system.game = self.game

    def _build_faction_system(self) -> None:
        """Initialize the faction standing system and wire cross-references."""
        from npc.faction_system import FactionSystem

        factions_data = load_json("factions.json")
        self.game.faction_system = FactionSystem(factions_data)
        self.game.faction_system.game = self.game

        # Wire FactionSystem to TradeSystem for faction-based pricing
        self.game.trade_system.set_faction_system(self.game.faction_system)

        # Wire FactionSystem to QuestSystem for prerequisite checks
        self.game.quest_system.faction_system = self.game.faction_system

    def _build_quest_panel(self) -> None:
        """Create the quest panel."""
        from ui.quest_panel import QuestPanel

        self.game._quest_panel = QuestPanel()
        self.game._quest_panel.set_quest_system(self.game.quest_system)
        self.game._quest_panel.set_player(self.game.player)
        self.game._quest_panel.visible = False

    def _build_recruit_panel(self) -> None:
        """Create the recruit panel."""
        from ui.recruit_panel import RecruitPanel

        self.game._recruit_panel = RecruitPanel()
        self.game._recruit_panel.set_player(self.game.player)
        self.game._recruit_panel.visible = False

    def _build_diplomacy_panel(self) -> None:
        """Create the diplomacy panel."""
        from ui.diplomacy_panel import DiplomacyPanel

        self.game._diplomacy_panel = DiplomacyPanel()
        self.game._diplomacy_panel.set_player(self.game.player)
        self.game._diplomacy_panel.visible = False

    def _build_combat_system(self) -> None:
        """Initialize the combat system."""
        from combat.combat_system import CombatSystem

        self.game.combat_system = CombatSystem(
            self.game.player,
            self.game.survival,
            building_system=self.game.building_system,
            firemaking=self.game.firemaking,
            game=self.game,
            faction_system=self.game.faction_system,
        )

    def _spawn_initial_monsters(self) -> None:
        """Spawn initial monsters on the map based on biome."""
        import random

        if self.game.world is None or self.game.combat_system is None:
            return

        start_tile = self.game.world.get_tile(
            self.game.world.spawn_x, self.game.world.spawn_y,
        )
        if start_tile is None or start_tile.biome is None:
            return

        biome_id = start_tile.biome.id

        monster_data = load_json("monsters.json")
        biome_monsters = monster_data.get("monsters", {}).get(biome_id, {})

        if not biome_monsters:
            return

        spawn_world_x = self.game.world.spawn_x * TILE_SIZE + TILE_SIZE // 2
        spawn_world_y = self.game.world.spawn_y * TILE_SIZE + TILE_SIZE // 2
        from config import INITIAL_MONSTER_SPAWN_RADIUS_TILES
        spawn_radius = INITIAL_MONSTER_SPAWN_RADIUS_TILES * TILE_SIZE

        self.game.combat_system.spawn_initial_monsters(
            biome_monster_data=biome_monsters,
            spawn_world_x=spawn_world_x,
            spawn_world_y=spawn_world_y,
            spawn_radius_px=spawn_radius,
            rng_seed=self.game.seed + 1,
            biome_id=biome_id,
        )

    def _build_renderers(self) -> None:
        """Create the tile and sprite renderers."""
        from render import TileRenderer, SpriteRenderer

        self.game._tile_renderer = TileRenderer(self.game.world, self.game.screen)
        self.game._sprite_renderer = SpriteRenderer(tile_map=self.game.world)

    def begin_world_gen(self) -> None:
        """
        Start procedural world generation.
        Called when transitioning from TITLE → LOADING.
        """
        self.game.loading_progress = 0.0

        try:
            # Load biome data
            biome_data = load_json_list("biomes.json", "biomes")
            biome_registry = BiomeRegistry(biome_data)
            # Update our stored biome_registry (caller may have passed None)
            self.biome_registry = biome_registry

            # Create SeasonSystem before world generation so seasonal
            # tier 3/4 resources can be gated correctly during placement.
            from seasons import SeasonSystem
            self.game.season_system = SeasonSystem()

            # Generate world (with progress updates)
            self.game.loading_progress = 0.2
            self.game.world = generate_world(
                self.game.seed, biome_registry, self.game.season_system
            )
            self.game.loading_progress = 0.6

            # Create player at spawn point
            from core.player import Player
            spawn_px_x = self.game.world.spawn_x * TILE_SIZE + TILE_SIZE // 2  # Center of tile
            spawn_px_y = self.game.world.spawn_y * TILE_SIZE + TILE_SIZE // 2
            self.game.player = Player(spawn_px_x, spawn_px_y)

            # Initialize starter pack definition (pack applied after subsystem init)
            from survival.starter_pack import CharacterDefinition
            character_def = CharacterDefinition()

            # Initialize all subsystems via bootstrap
            self.initialize()
            self.game.loading_progress = 0.8

            # Apply starter pack AFTER inventory is created
            from survival.starter_pack import apply_starter_pack
            apply_starter_pack(self.game.inventory, character_def.starter_pack_id)
            self.game.loading_progress = 1.0

            # Transition to playing state
            self.game.set_state(GameState.PLAYING)

        except Exception as e:
            # On error, transition to ERROR state
            print(f"World generation error: {e}")
            self.game.world = None
            self.game.player = None
            self.game.state = GameState.ERROR
            self.game.loading_progress = 1.0

    def load_save(self) -> None:
        """
        Load save file when TITLE -> LOADING_SAVE.
        """
        self.game.loading_progress = 0.0

        # Find first non-empty slot (or slot 0)
        slot = 0
        for i in range(self.game.save_system.slot_count):
            if self.game.save_system.has_save(i):
                slot = i
                break

        save_data = self.game.save_system.load(slot)
        if save_data is None:
            self.game.world = None
            self.game.player = None
            self.game.state = GameState.ERROR
            self.game.loading_progress = 1.0
            return

        self.game.seed = save_data["seed"]
        self.game.death_count = save_data.get("death_count", 0)

        try:
            # Regenerate world from saved seed
            biome_data = load_json_list("biomes.json", "biomes")
            biome_registry = BiomeRegistry(biome_data)
            self.biome_registry = biome_registry

            self.game.loading_progress = 0.2

            # Create SeasonSystem before world generation so seasonal
            # tier 3/4 resources are gated consistently with a fresh game.
            from seasons import SeasonSystem
            self.game.season_system = SeasonSystem()

            self.game.world = generate_world(
                self.game.seed, biome_registry, self.game.season_system
            )
            self.game.loading_progress = 0.6

            # Create player at spawn point
            from core.player import Player
            spawn_px_x = self.game.world.spawn_x * TILE_SIZE + TILE_SIZE // 2
            spawn_px_y = self.game.world.spawn_y * TILE_SIZE + TILE_SIZE // 2
            self.game.player = Player(spawn_px_x, spawn_px_y)

            # Initialize subsystems via bootstrap
            self.initialize()

            # Restore state from save (order: skills -> survival -> inventory -> gear -> position -> structures -> fires)
            self.game.save_system.load_into_game(save_data, self.game)

            self.game.loading_progress = 1.0

            # Transition to playing state
            self.game.set_state(GameState.PLAYING)
        except Exception as e:
            print(f"Save load error: {e}")
            self.game.world = None
            self.game.player = None
            self.game.state = GameState.ERROR
            self.game.loading_progress = 1.0

    def on_world_gen_complete(self) -> None:
        """
        Called when transitioning from LOADING → PLAYING after world gen.

        Finalizes the game state: ensures camera is centered on the player,
        resets renderers, and notifies the player that the world is ready.
        """
        game = self.game
        if game.camera is not None and game.player is not None:
            game.camera.set_player(game.player)

        if game._tile_renderer is not None:
            game._tile_renderer.tile_map = game.world
            game._tile_renderer.screen = game.screen

        if game.hud is not None and game.player is not None:
            game.hud.set_survival(game.survival)
            action_sys = game.player.action_system
            if action_sys is not None:
                action_sys.add_notification(
                    "World generated. Good luck!", (100, 255, 100),
                )

    # ── Phase 4 wiring ─────────────────────────────────────────────

    def _wire_phase4(self) -> None:
        """Create and wire Phase 4 systems (seasons, weather)."""
        from seasons import SeasonSystem, WeatherSystem

        # Reuse existing SeasonSystem if already created (e.g., during world gen)
        if self.game.season_system is None:
            self.game.season_system = SeasonSystem()

        # Wire SeasonSystem → SurvivalSystem (hunger modifiers)
        if hasattr(self.game, "survival") and self.game.survival is not None:
            self.game.survival.season_system = self.game.season_system

        # Wire SeasonSystem → ActionSystem (yield multipliers)
        if (
            hasattr(self.game, "player")
            and self.game.player is not None
            and hasattr(self.game.player, "action_system")
        ):
            self.game.player.action_system.season_system = self.game.season_system

        # Wire SeasonSystem → TileMap (regrowth speed)
        if (
            hasattr(self.game, "world")
            and self.game.world is not None
        ):
            self.game.world.season_system = self.game.season_system

        # Create WeatherSystem and wire to SeasonSystem
        self.game.weather_system = WeatherSystem(season_system=self.game.season_system, seed=self.game.seed)
        # Wire weather system to HUD for weather icon/forecast display
        if self.game.hud is not None:
            self.game.hud.set_weather_system(self.game.weather_system)

        # Wire WeatherSystem → Player (movement speed modifier)
        if hasattr(self.game, "player") and self.game.player is not None:
            self.game.player.weather_system = self.game.weather_system

        # Wire WeatherSystem → SurvivalSystem (visibility, movement, crafting, spawn modifiers)
        if hasattr(self.game, "survival") and self.game.survival is not None:
            self.game.survival.weather_system = self.game.weather_system

        # Wire WeatherSystem → ActionSystem (outdoor crafting modifier)
        if (
            hasattr(self.game, "player")
            and self.game.player is not None
            and hasattr(self.game.player, "action_system")
        ):
            self.game.player.action_system.weather_system = self.game.weather_system

        # Wire WeatherSystem → CombatSystem (spawn modifier)
        if hasattr(self.game, "combat_system") and self.game.combat_system is not None:
            self.game.combat_system.weather_system = self.game.weather_system

        # Wire SeasonSystem → WeatherSystem (if not already set)
        if (
            hasattr(self.game, "weather_system")
            and self.game.weather_system is not None
            and self.game.weather_system.season_system is None
        ):
            self.game.weather_system.set_season_system(self.game.season_system)

        # Create ParticleSystem for weather visual effects
        from render import ParticleSystem
        self.game.particle_system = ParticleSystem()

        # Wire ParticleSystem → WeatherSystem
        if (
            hasattr(self.game, "weather_system")
            and self.game.weather_system is not None
        ):
            self.game.particle_system.sync(self.game.weather_system.current_weather)

        # Create SeasonalRenderer for terrain color blending
        from render import SeasonalRenderer
        self.game.seasonal_renderer = SeasonalRenderer()

        # Wire TileRenderer → SeasonalRenderer (for fallback colored tiles)
        if self.game._tile_renderer is not None:
            self.game._tile_renderer.seasonal_renderer = self.game.seasonal_renderer

        # Wire SpriteRenderer → SeasonalRenderer (for sprite tinting)
        if self.game._sprite_renderer is not None:
            self.game._sprite_renderer.seasonal_renderer = self.game.seasonal_renderer
