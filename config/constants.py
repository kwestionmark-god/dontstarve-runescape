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
ELEVATION_LEVELS = 15          # 0–14 elevation levels
Z_SCALE = 8                   # Pixels of vertical displacement per elevation unit

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
CAMERA_PITCH_MIN = 5.0        # Minimum pitch in degrees (5° = elevated isometric)
CAMERA_PITCH_MAX = 35.0        # Maximum pitch in degrees (35° = steep isometric)

# ─── Terrain Shading ──────────────────────────────────────────────────

SHADING_STRENGTH = 0.20        # ±brightness on slopes (0.0 = none, 0.25 = dramatic)
LIGHT_DIRECTION = (-1, -1)     # North-west light (screen-space gradient)

# ─── Fog & LOD ─────────────────────────────────────────────────────────

FOG_NEAR_DISTANCE = 500.0      # Pixels from player where fog begins to fade
FOG_FAR_DISTANCE = 1400.0      # Pixels from player where fog fully obscures (alpha = 255)
FOG_CULL_DISTANCE = 1700.0     # Pixels beyond which sprites are not rendered at all
FOG_COLOR = (135, 206, 235)    # Matches sky colour for seamless blend

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


