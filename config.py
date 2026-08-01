# config.py
# Consolidated configuration with sensible defaults for development and MC-style behavior

# Chunk geometry
CHUNK_SIZE = 16
CHUNK_HEIGHT = 384
SECTION_HEIGHT = 16
NUM_SECTIONS = CHUNK_HEIGHT // SECTION_HEIGHT  # 24
WORLD_BOTTOM = -64
WORLD_TOP = WORLD_BOTTOM + CHUNK_HEIGHT - 1

# World radius for generation limits
WORLD_RADIUS = 30000000

# Distances (in chunks)
RENDER_DIST = 6
LOAD_DIST = RENDER_DIST + 4

# Load levels
LOAD_LEVEL_ENTITY = 31
LOAD_LEVEL_BLOCK = 32
LOAD_LEVEL_FULL = 33
LOAD_LEVEL_INACCESSIBLE = 34
LOAD_LEVEL_UNLOADED = 45

# Fluid / simulation defaults (Minecraft-like)
MAX_FLUID_LEVEL = 7
WATER_TICK_DELAY = 5
DEFAULT_UPDATES_PER_TICK = 80

# Rebuild defaults
REBUILDS_PER_FRAME_DEFAULT = 2

# Block colors
BLOCK_COLORS = {
    'grass_block': (0.2, 0.7, 0.2),
    'dirt': (0.55, 0.27, 0.07),
    'stone': (0.6, 0.6, 0.6),
    'deepslate': (0.4, 0.4, 0.4),
    'wood': (0.63, 0.32, 0.18),
    'leaves': (0.0, 0.6, 0.0),
    'sand': (0.93, 0.84, 0.69),
    'snow': (0.95, 0.95, 0.98),
    'bedrock': (0.3, 0.3, 0.3),
    'water': (0.1, 0.3, 0.7),
}

block_types = ['grass_block', 'dirt', 'stone', 'wood', 'leaves', 'sand', 'snow', 'water']

# Random tick speed (per chunk section)
RANDOM_TICK_SPEED = 3

# Debug
DEBUG = False
VERBOSE = False