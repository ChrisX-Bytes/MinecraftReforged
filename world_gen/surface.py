# world_gen/surface.py
from chunk_manager import get_block, set_block
from .biome_params import BIOME_PLAINS, BIOME_FOREST, BIOME_HILLS, BIOME_MOUNTAINS, BIOME_OCEAN, BIOME_DESERT, BIOME_SNOWY_TUNDRA

def apply_surface_rule(x, y, z, biome_id, noise_gen):
    block = get_block(x, y, z)
    if block is None:
        return

    is_surface = (get_block(x, y+1, z) is None)
    if is_surface and block in ('stone', 'deepslate'):
        if biome_id == BIOME_PLAINS:
            if y > 100:
                set_block(x, y, z, 'snow')
            else:
                set_block(x, y, z, 'grass_block')
                for dy in range(1, 4):
                    if get_block(x, y-dy, z) in ('stone', 'deepslate'):
                        set_block(x, y-dy, z, 'dirt')
        elif biome_id == BIOME_FOREST:
            set_block(x, y, z, 'grass_block')
            for dy in range(1, 4):
                if get_block(x, y-dy, z) in ('stone', 'deepslate'):
                    set_block(x, y-dy, z, 'dirt')
        elif biome_id == BIOME_HILLS:
            set_block(x, y, z, 'grass_block')
            for dy in range(1, 3):
                if get_block(x, y-dy, z) in ('stone', 'deepslate'):
                    set_block(x, y-dy, z, 'dirt')
        elif biome_id == BIOME_MOUNTAINS:
            if y > 120:
                set_block(x, y, z, 'snow')
            elif y > 100:
                set_block(x, y, z, 'stone')
            else:
                set_block(x, y, z, 'grass_block')
                for dy in range(1, 3):
                    if get_block(x, y-dy, z) in ('stone', 'deepslate'):
                        set_block(x, y-dy, z, 'dirt')
        elif biome_id == BIOME_DESERT:
            set_block(x, y, z, 'sand')
            for dy in range(1, 5):
                if get_block(x, y-dy, z) in ('stone', 'deepslate'):
                    set_block(x, y-dy, z, 'sandstone')
        elif biome_id == BIOME_SNOWY_TUNDRA:
            set_block(x, y, z, 'snow')
            for dy in range(1, 3):
                if get_block(x, y-dy, z) in ('stone', 'deepslate'):
                    set_block(x, y-dy, z, 'dirt')
        elif biome_id == BIOME_OCEAN:
            # 海洋地表已经由水覆盖，表面规则仅在非水方块上生效
            # 这里保留原逻辑以防水面上的方块（如沙滩）
            if y < 63:
                set_block(x, y, z, 'stone')
            else:
                set_block(x, y, z, 'sand')
        return

    if block == 'stone' and y < 0:
        set_block(x, y, z, 'deepslate')
        return
    if y == -64:
        set_block(x, y, z, 'bedrock')
        return
    if block == 'stone' and get_block(x, y+1, z) == 'sand':
        set_block(x, y, z, 'sandstone')
        return