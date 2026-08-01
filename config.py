# config.py
CHUNK_SIZE = 16
CHUNK_HEIGHT = 384
SECTION_HEIGHT = 16
NUM_SECTIONS = CHUNK_HEIGHT // SECTION_HEIGHT   # 24
WORLD_RADIUS = 50

RENDER_DIST = 12
LOAD_DIST = RENDER_DIST + 4

WORLD_BOTTOM = -64
WORLD_TOP = 320

# 加载等级（与MC原版一致）
LOAD_LEVEL_ENTITY = 31
LOAD_LEVEL_BLOCK = 32
LOAD_LEVEL_FULL = 33
LOAD_LEVEL_INACCESSIBLE = 34
LOAD_LEVEL_UNLOADED = 45

# 方块颜色（渲染用）
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
    'water': (0.1, 0.3, 0.7),   # 不透明蓝色
}
block_types = ['grass_block', 'dirt', 'stone', 'wood', 'leaves', 'sand', 'snow']

# config.py 新增
MAX_FLUID_LEVEL = 7
FLUID_UPDATE_INTERVAL = 5  # 每5个tick更新一次流体

# 生物群系ID（与multi_noise_biome_source.py一致）
BIOME_PLAINS = 0
BIOME_FOREST = 1
BIOME_HILLS = 2
BIOME_MOUNTAINS = 3
BIOME_OCEAN = 4
BIOME_DESERT = 5
BIOME_SNOWY_TUNDRA = 6