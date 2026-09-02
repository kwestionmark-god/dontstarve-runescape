"""
config.py — Global constants and tuning parameters.

All magic numbers are defined here. No subsystem should hardcode
values that appear in this table; instead, import from config.
"""

# ─── Window & Rendering ───────────────────────────────────────────────

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
WINDOW_TITLE = "Don't Starve RuneScape"
TARGET_FPS = 60

# ─── Tile & Terrain ───────────────────────────────────────────────────

TILE_SIZE = 64                # Pixel size of one tile
TILE_SUBDIVISIONS = 2         # Half-tile rendering (2×2 sub-tiles)
MAP_WIDTH = 512               # Tiles wide
MAP_HEIGHT = 512              # Tiles tall
ELEVATION_LEVELS = 32         # 0–31 elevation levels (was 15, now 32 for finer detail)
Z_SCALE = 8                   # Pixels of vertical displacement per elevation unit

# ─── Proc-Gen Noise Configuration (Phase 5) ───────────────────────────

# Base noise parameters
NOISE_SCALE = 0.015           # Controls "zoom" of noise features (larger = more variation)
ELEVATION_OCTAVES = 5         # Number of noise layers for detail
MOISTURE_OCTAVES = 3
MOISTURE_SCALE = 0.008        # Independent scale for moisture (larger = more variation)
MOISTURE_RANGE_MULTIPLIER = 2.5  # Scale factor to expand moisture noise range

# Ridgeline noise parameters (for sharp ridges/valleys)
RIDGE_NOISE_SCALE = 0.023     # Higher frequency for ridges (non-integer ratio to base)
RIDGE_OCTAVES = 4             # More octaves for sharp detail
RIDGE_LACUNARITY = 2.1        # Non-integer lacunarity to break periodicity
RIDGE_PERSISTENCE = 0.5

# Domain warping parameters (for geological distortion)
DOMAIN_WARP_SCALE = 0.008
DOMAIN_WARP_OCTAVES = 3
DOMAIN_WARP_AMPLITUDE = 12.0  # Max warp distance in tiles

# Biome-specific noise overrides (can be overridden per biome)
BIOME_NOISE_PARAMS: dict[str, dict] = {
    "mountains": {
        "scale": 0.018,
        "octaves": 5,
        "lacunarity": 2.1,
        "persistence": 0.5,
        "ridge_weight": 0.4,    # Reduced ridge weight
        "domain_warp": 15.0,
    },
    "plains": {
        "scale": 0.01,
        "octaves": 3,
        "lacunarity": 2.1,
        "persistence": 0.6,
        "ridge_weight": 0.05,   # Very subtle ridges
        "domain_warp": 5.0,
    },
    "forest": {
        "scale": 0.012,
        "octaves": 4,
        "lacunarity": 2.1,
        "persistence": 0.5,
        "ridge_weight": 0.15,
        "domain_warp": 10.0,
    },
    "swamp": {
        "scale": 0.006,
        "octaves": 2,
        "lacunarity": 2.1,
        "persistence": 0.7,
        "ridge_weight": 0.0,    # Flat, no ridges
        "domain_warp": 3.0,
    },
    "desert": {
        "scale": 0.014,
        "octaves": 4,
        "lacunarity": 2.1,
        "persistence": 0.4,
        "ridge_weight": 0.2,
        "domain_warp": 8.0,
    },
    "coastal": {
        "scale": 0.01,
        "octaves": 3,
        "lacunarity": 2.1,
        "persistence": 0.6,
        "ridge_weight": 0.05,
        "domain_warp": 5.0,
    },
}

# Erosion simulation parameters (Phase 5.2)
EROSION_ITERATIONS = 5
EROSION_RAIN_AMOUNT = 0.01
EROSION_SOLUBILITY = 0.05
EROSION_EVAPORATION = 0.01
EROSION_GRAVITY = 4.0
EROSION_SEDIMENT_CAPACITY_FACTOR = 0.1

# Cliff detection threshold (Phase 5.5)
CLIFF_THRESHOLD = 2.0         # Elevation delta > this = cliff

# Water body generation (Phase 5.6)
RIVER_THRESHOLD = 10.0        # Flow accumulation threshold for rivers (upstream tile count)
LAKE_MIN_SIZE = 5             # Minimum tiles for a lake

# ─── Survival ─────────────────────────────────────────────────────────

HUNGER_DRAIN_INTERVAL = 30.0  # Seconds per hunger point drain
HUNGER_DRAIN_RATE = 1.0       # Hunger points per interval
STARVATION_HP_DRAIN_RATE = 0.5  # HP drain per interval when hunger = 0
HP_BASE_MAX = 20.0            # Starting max HP
MAX_STAMINA_BASE = 30.0       # Max stamina for Woodcutting/Mining actions

# ─── Player ───────────────────────────────────────────────────────────

PLAYER_MOVEMENT_SPEED = 150.0  # Pixels per second

# ─── XP & Progression ────────────────────────────────────────────────

XP_SCALE_FACTOR = 4.0          # Denominator in OSRS XP formula
STAT_POINTS_PER_LEVEL = 3     # Stat points granted per skill level
WILDCARD_INTERVAL = 5          # Every N total skill levels for wildcard point

# ─── Camera ───────────────────────────────────────────────────────────

CAMERA_ZOOM_MIN = 0.5
CAMERA_ZOOM_MAX = 3.0
CAMERA_ZOOM_DEFAULT = 1.8      # Closer, more intimate aerial view
CAMERA_ORBIT_SPEED = 90.0      # Degrees per second for yaw (horizontal orbit)
CAMERA_TILT_SPEED = 60.0       # Degrees per second for pitch (vertical tilt)
CAMERA_PITCH_MIN = 18.0       # Minimum pitch (18° keeps the view from flattening into a wall)
CAMERA_PITCH_MAX = 35.0        # Maximum pitch in degrees (35° = steep isometric)

# ─── Terrain Shading ──────────────────────────────────────────────────

SHADING_STRENGTH = 0.20        # ±brightness on slopes (0.0 = none, 0.25 = dramatic)
LIGHT_DIRECTION = (-1, -1)     # North-west light (screen-space gradient)

# ─── Fog & LOD ─────────────────────────────────────────────────────────

FOG_NEAR_DISTANCE = 500.0      # Pixels from player where fog begins to fade
FOG_FAR_DISTANCE = 1400.0      # Pixels from player where fog fully obscures (alpha = 255)
FOG_CULL_DISTANCE = 1700.0     # Pixels beyond which sprites are not rendered at all
FOG_COLOR = (135, 206, 235)    # Matches sky colour for seamless blend

# ─── Phase 6: Advanced Shading & Lighting ────────────────────────────

# Time-of-day
DAY_DURATION_SECONDS = 1200.0        # Full day/night cycle (20 min)
SUNRISE_HOUR = 6.0                   # Time-of-day 0.25
SUNSET_HOUR = 18.0                   # Time-of-day 0.75
SUN_ALTITUDE_MIN = -30.0             # Degrees at midnight
SUN_ALTITUDE_MAX = 30.0              # Degrees at noon
SUN_AZIMUTH = 45.0                   # Degrees from north (0=N, 90=E). Matches NW light.
NIGHT_AMBIENT_LEVEL = 0.15           # Minimum ambient at night (0–1)
DAY_AMBIENT_LEVEL = 0.45             # Maximum ambient at noon (0–1)

# Ambient occlusion
AO_STRENGTH = 0.35                   # Max AO darkening (0–1)
AO_BLUR_RADIUS = 1                   # Tiles to blur AO across (0=sharp)

# Rim lighting / fresnel
RIM_STRENGTH = 0.25                  # Max rim brightening (0–1)
RIM_EXPONENT = 3.0                   # Fresnel sharpness

# Height fog / volumetric
FOG_SCALE_HEIGHT = 8.0               # Elevation scale for density falloff
FOG_HEIGHT_PLANES = []               # Optional: [(height, color, density_mult), ...]

# Weather lighting
CLOUD_SHADOW_STRENGTH = 0.20         # Max cloud shadow darkening
LIGHTNING_FLASH_DURATION_MS = 50     # Screen flash duration
LIGHTNING_FLASH_ALPHA = 180          # 0–255

# Seasonal lighting profiles (per-biome ambient/sun/fog tint)
SEASON_LIGHTING: dict[str, dict[str, tuple[int, int, int]]] = {
    "spring":  {"ambient": (230, 240, 220), "sun_color": (255, 240, 200), "fog_tint": (180, 210, 190)},
    "summer":  {"ambient": (245, 235, 210), "sun_color": (255, 245, 220), "fog_tint": (200, 190, 160)},
    "autumn":  {"ambient": (235, 220, 190), "sun_color": (255, 200, 140), "fog_tint": (180, 160, 130)},
    "winter":  {"ambient": (200, 220, 240), "sun_color": (220, 235, 255), "fog_tint": (160, 180, 200)},
}

# Shading presets
SHADING_PRESETS: dict[str, dict] = {
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
        "terrain_style": "textured",
        "terrain_subdiv": 2,
        "terrain_lod": True,
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
        "terrain_style": "flat",
        "terrain_subdiv": 4,
        "terrain_lod": True,
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
        "terrain_style": "textured",
        "terrain_subdiv": 2,
        "terrain_lod": True,
    },
}
DEFAULT_SHADING_PRESET = "stylized"

# ─── State Machine ────────────────────────────────────────────────────

LOADING_SCREEN_DURATION = 3.0  # Minimum seconds for loading screen
FLAVOR_TEXT_COUNT = 10         # Number of loading screen messages

FLAVOR_TEXTS: list[str] = [
    "Assembling campfire from existential dread...",
    "Teaching wolves to share resources...",
    "Polishing pickaxe with hope and determination...",
    "Convincing trees to donate logs...",
    "Balancing hunger against hope...",
    "Crafting planks from pure optimism...",
    "Mining stones for future prosperity...",
    "Cooking fish over a dream of warmth...",
    "Gathering herbs to heal existential wounds...",
    "Exploring biomes of endless possibility...",
]

# ─── Combat (stub — Phase 2) ─────────────────────────────────────────

PLAYER_HP_PER_COMBAT_LEVEL = 1  # HP gain per Combat level (stub)
COMBAT_BASE_ATTACK_COOLDOWN = 1.5  # Base attack cooldown in seconds (unarmed)
COMBAT_SPEED_STAT_COOLDOWN_REDUCTION = 0.3  # Cooldown reduction per speed stat point
COMBAT_DAMAGE_NUMBER_RISE_RATE = 30.0  # Damage number rise rate (px/s)
DEATH_CLEAR_MONSTERS_RADIUS = 0.0  # Radius in tiles to clear monsters on death (0 = all)

# ─── Firemaking ──────────────────────────────────────────────────────

FIRE_INTERACTION_RADIUS_TILES = 2  # Tiles radius for fire interaction check
CAMPFIRE_SEARCH_RADIUS_TILES = 3  # Tiles radius for campfire search

# ─── Monster Spawning ────────────────────────────────────────────────

INITIAL_MONSTER_SPAWN_RADIUS_TILES = 20  # Spawn radius in tiles

# ─── Save System ──────────────────────────────────────────────────────

SAVE_SLOT_COUNT = 10           # Number of save slots
AUTOSAVE_INTERVAL = 300.0      # Seconds between autosaves (5 min)
DEATH_RESTORE_HP_FRACTION = 0.5  # HP fraction restored on soft death
DEATH_RESTORE_HUNGER_FRACTION = 0.5  # Hunger fraction restored on soft death
DEATH_XP_PENALTY_FRACTION = 0.01  # XP lost on soft death (1%)

# ─── Data File Paths ──────────────────────────────────────────────────

DATA_DIR = "data"
BIOMES_FILE = "data/biomes.json"
RESOURCES_FILE = "data/resources.json"
ITEMS_FILE = "data/items.json"

# ─── Seasons & Weather (Phase 4) ──────────────────────────────────────

SEASON_DURATION_SECONDS = 600       # 10 minutes per season
SEASON_TRANSITION_SECONDS = 30      # Visual/logical transition window
SEASON_ORDER = ("spring", "summer", "autumn", "winter")
SEASON_TRANSITIONS = {
    "spring": "summer",
    "summer": "autumn",
    "autumn": "winter",
    "winter": "spring",
}

# Weather weights by season → (clear, rain, snow, storm, fog)
WEATHER_WEIGHTS: dict[str, tuple[float, float, float, float, float]] = {
    "spring":  (40.0, 35.0,  0.0, 10.0, 15.0),
    "summer":  (50.0, 30.0,  0.0, 15.0,  5.0),
    "autumn":  (45.0, 30.0,  0.0, 15.0, 10.0),
    "winter":  (40.0, 15.0, 30.0, 10.0,  5.0),
}
WEATHER_CHANGE_INTERVAL = 120.0     # Seconds between weather rolls

# ─── Proc-Gen Rarity System (Phase 1) ──────────────────────────────────

# Rarity → (min_density, max_density) for base_density clamping
# Global density scale factor: 0.35 reduces overall spawn density while preserving
# relative rarity ratios. Adjust this single value to tune global abundance.
_GLOBAL_DENSITY_SCALE = 0.35

RARITY_DENSITY_RANGE: dict[str, tuple[float, float]] = {
    "ubiquitous": (0.15 * _GLOBAL_DENSITY_SCALE, 0.30 * _GLOBAL_DENSITY_SCALE),   # water, grass
    "common":     (0.08 * _GLOBAL_DENSITY_SCALE, 0.15 * _GLOBAL_DENSITY_SCALE),   # oak, iron, fiber, berry, birch, maple, pine, reed
    "uncommon":   (0.03 * _GLOBAL_DENSITY_SCALE, 0.08 * _GLOBAL_DENSITY_SCALE),   # copper, gold, gem, tin, spruce, willow, dead_tree
    "rare":       (0.01 * _GLOBAL_DENSITY_SCALE, 0.03 * _GLOBAL_DENSITY_SCALE),   # void_crystal, obsidian, silk, elder_wood, moonstone
    "epic":       (0.003 * _GLOBAL_DENSITY_SCALE, 0.01 * _GLOBAL_DENSITY_SCALE),  # mithril, ghost_iron, dragonbone, void_essence, phoenix
    "legendary":  (0.001 * _GLOBAL_DENSITY_SCALE, 0.003 * _GLOBAL_DENSITY_SCALE), # star_metal, ancient_rune, celestial_crystal
}


