"""
Game constants and configuration.
"""

from enum import Enum, auto

# =============================================================================
# DISPLAY SETTINGS
# =============================================================================

# Base resolution (all UI measurements are relative to this)
BASE_WIDTH = 1280
BASE_HEIGHT = 720

# Available resolutions
RESOLUTIONS = [
    (1280, 720),    # 720p
    (1600, 900),    # 900p
    (1920, 1080),   # 1080p
    (2560, 1440),   # 1440p
    (3840, 2160),   # 4K
]

# Current resolution (can be changed at runtime)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# Scale factor (computed at runtime based on resolution)
SCALE = 1.0

def get_scale():
    """Get current scale factor."""
    return SCREEN_WIDTH / BASE_WIDTH

def scale(value):
    """Scale a value from base resolution to current resolution."""
    return int(value * get_scale())

def scale_pos(x, y):
    """Scale a position tuple."""
    s = get_scale()
    return (int(x * s), int(y * s))

def scale_rect(x, y, w, h):
    """Scale a rectangle."""
    s = get_scale()
    return (int(x * s), int(y * s), int(w * s), int(h * s))

# Map dimensions (in game units, not affected by UI scale)
MAP_WIDTH = 2000
MAP_HEIGHT = 2000
TILE_SIZE = 64
FPS = 60

# =============================================================================
# COLORS
# =============================================================================

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 50, 50)
BLUE = (50, 50, 200)
GREEN = (50, 200, 50)
YELLOW = (200, 200, 50)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)
BROWN = (139, 90, 43)
GOLD = (255, 215, 0)
DARK_GREEN = (34, 139, 34)

# =============================================================================
# NETWORK SETTINGS
# =============================================================================

DEFAULT_PORT = 5555
BUFFER_SIZE = 4096

# =============================================================================
# STARTING RESOURCES
# =============================================================================

STARTING_GOLD = 500
STARTING_FOOD = 200
STARTING_WOOD = 300

# =============================================================================
# UNIT DEFINITIONS
# =============================================================================

UNIT_COSTS = {
    'peasant': {'gold': 50, 'food': 25},
    'knight': {'gold': 150, 'food': 50},
    'cavalry': {'gold': 200, 'food': 75},
    'cannon': {'gold': 300, 'food': 0, 'wood': 100}
}

# Build time in seconds (for buildings and cannons)
BUILD_TIMES = {
    'house': 10.0,
    'farm': 8.0,
    'castle': 30.0,
    'cannon': 5.0,
    'tower': 15.0
}

# Refund percentage when deconstructing
DECONSTRUCT_REFUND = 0.7

UNIT_STATS = {
    'peasant': {
        'health': 50,
        'attack': 5,
        'defense': 2,
        'speed': 2.5,
        'range': 20,
        'cooldown': 1.0
    },
    'knight': {
        'health': 150,
        'attack': 20,
        'defense': 15,
        'speed': 1.8,
        'range': 35,
        'cooldown': 1.2
    },
    'cavalry': {
        'health': 120,
        'attack': 25,
        'defense': 10,
        'speed': 4.0,
        'range': 40,
        'cooldown': 0.8
    },
    'cannon': {
        'health': 80,
        'attack': 50,
        'defense': 5,
        'speed': 1.0,
        'range': 200,
        'cooldown': 3.0
    }
}

# =============================================================================
# BUILDING DEFINITIONS
# =============================================================================

BUILDING_COSTS = {
    'house': {'gold': 100, 'wood': 50},
    'castle': {'gold': 500, 'wood': 200},
    'farm': {'gold': 75, 'wood': 25},
    'tower': {'gold': 200, 'wood': 100}
}

BUILDING_STATS = {
    'house': {'health': 300},
    'castle': {'health': 2000},
    'farm': {'health': 200},
    'tower': {'health': 500}
}

# =============================================================================
# RESOURCE GENERATION
# =============================================================================

RESOURCE_TICK_INTERVAL = 5.0  # seconds

# Base generation when a peasant is working at the building
BUILDING_RESOURCE_GENERATION = {
    'house': {'gold': 20, 'food': 0, 'wood': 0, 'max_workers': 2},
    'farm': {'gold': 0, 'food': 25, 'wood': 5, 'max_workers': 3},
    'castle': {'gold': 10, 'food': 5, 'wood': 5, 'max_workers': 1},
    'tower': {'gold': 0, 'food': 0, 'wood': 0, 'max_workers': 2}
}

# =============================================================================
# TOWER COMBAT STATS
# =============================================================================

TOWER_STATS = {
    'attack': 60,           # High damage
    'range': 250,           # Long range
    'cooldown': 2.0,        # Attack interval in seconds
    'hit_chance': 0.7       # 70% chance to hit
}

# Worker assignment range - how close peasant must be to work
WORKER_RANGE = 80

# =============================================================================
# FOOD CONSUMPTION
# =============================================================================

FOOD_CONSUMPTION_INTERVAL = 10.0  # seconds between food consumption ticks
FOOD_PER_UNIT = 2  # food consumed per unit per tick
STARVATION_DAMAGE = 5  # damage taken when no food available

# =============================================================================
# AI DIFFICULTY SETTINGS
# =============================================================================

class Difficulty(Enum):
    EASY = auto()
    NORMAL = auto()
    HARD = auto()
    BRUTAL = auto()

# Difficulty multipliers: affects AI think speed, resource bonus, and aggression
DIFFICULTY_SETTINGS = {
    Difficulty.EASY: {
        'think_speed': 0.5,      # AI thinks slower
        'resource_bonus': 0.8,   # AI gets less resources
        'aggression': 0.3,       # Less aggressive
        'military_cap': 5,       # Max military units
        'name': 'Easy'
    },
    Difficulty.NORMAL: {
        'think_speed': 1.0,
        'resource_bonus': 1.0,
        'aggression': 0.5,
        'military_cap': 8,
        'name': 'Normal'
    },
    Difficulty.HARD: {
        'think_speed': 1.5,      # AI thinks faster
        'resource_bonus': 1.2,   # AI gets bonus resources
        'aggression': 0.7,
        'military_cap': 12,
        'name': 'Hard'
    },
    Difficulty.BRUTAL: {
        'think_speed': 2.0,
        'resource_bonus': 1.5,
        'aggression': 0.9,
        'military_cap': 20,
        'name': 'Brutal'
    }
}

# =============================================================================
# ENUMS
# =============================================================================

class GameState(Enum):
    MAIN_MENU = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()
    MULTIPLAYER_LOBBY = auto()
    CONNECTING = auto()
    WAITING_FOR_ACCEPT = auto()
    SETTINGS = auto()
    DIFFICULTY_SELECT = auto()
    HOW_TO_PLAY = auto()
    KEYBINDS = auto()
    MODS = auto()


class UnitType(Enum):
    PEASANT = auto()
    KNIGHT = auto()
    CAVALRY = auto()
    CANNON = auto()


class BuildingType(Enum):
    HOUSE = auto()
    CASTLE = auto()
    FARM = auto()
    TOWER = auto()


class Team(Enum):
    PLAYER = auto()
    ENEMY = auto()
