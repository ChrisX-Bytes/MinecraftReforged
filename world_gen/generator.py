# world_gen/generator.py
import random
from OpenGL.GL import glDeleteBuffers
from config import *
from chunk_manager import (
    get_chunk, set_block, get_block, is_solid,
    chunks, get_chunk_pos, calculate_load_level
)
from .density import final_density
from .surface import apply_surface_rule
from .noise import PerlinNoise3D
from .multi_noise_biome_source import MultiNoiseBiomeSource

def apply_biomes(cx, cz, noise_gen, seed):
    chunk = get_chunk(cx, cz)
    if chunk.generation_stage >= 1:
        return
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    biome_source = MultiNoiseBiomeSource(seed, noise_gen)

    for lx in range(CHUNK_SIZE):
        for lz in range(CHUNK_SIZE):
            wx = base_x + lx
            wz = base_z + lz
            if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
                continue
            biome_id = biome_source.get_biome(wx, 64, wz)
            chunk.biome_map[(lx, lz)] = biome_id
    chunk.generation_stage = 1
    chunk.is_dirty = True


def generate_chunk_terrain(cx, cz, noise_gen, seed):
    chunk = get_chunk(cx, cz)
    if chunk.generation_stage < 1:
        apply_biomes(cx, cz, noise_gen, seed)
    if chunk.generation_stage >= 2:
        return
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE

    column_top = {}
    # 计算每列地表高度
    for lx in range(CHUNK_SIZE):
        for lz in range(CHUNK_SIZE):
            wx = base_x + lx
            wz = base_z + lz
            if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
                continue
            top_y = WORLD_BOTTOM - 1
            for wy in range(WORLD_TOP - 1, WORLD_BOTTOM - 1, -1):
                density = final_density(wx, wy, wz, noise_gen, seed)
                if density > 0:
                    top_y = wy
                    break
            if top_y > WORLD_BOTTOM - 1:
                column_top[(lx, lz)] = top_y

    # 填充方块（从底部到地表）
    for lx in range(CHUNK_SIZE):
        for lz in range(CHUNK_SIZE):
            wx = base_x + lx
            wz = base_z + lz
            if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
                continue
            top_y = column_top.get((lx, lz), WORLD_BOTTOM - 1)
            if top_y > WORLD_BOTTOM - 1:
                for wy in range(WORLD_BOTTOM, top_y + 1):
                    set_block(wx, wy, wz, 'stone')

    # 水源
    for lx in range(CHUNK_SIZE):
        for lz in range(CHUNK_SIZE):
            wx = base_x + lx
            wz = base_z + lz
            if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
                continue
            top_y = column_top.get((lx, lz), WORLD_BOTTOM - 1)
            if top_y < 63:
                # 海面水源：level 0，生成阶段不激活流动（静态海面本就稳定，激活会塞爆调度桶）
                set_block(wx, 63, wz, 'water', 0, activate_fluid=False)

    chunk.generation_stage = 2
    chunk.is_dirty = True

def apply_surface(cx, cz, noise_gen):
    chunk = get_chunk(cx, cz)
    if chunk.generation_stage < 2:
        return
    if chunk.generation_stage >= 3:
        return
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE

    for lx in range(CHUNK_SIZE):
        for lz in range(CHUNK_SIZE):
            wx = base_x + lx
            wz = base_z + lz
            if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
                continue
            biome_id = chunk.biome_map.get((lx, lz), 0)
            for wy in range(WORLD_BOTTOM, WORLD_TOP):
                apply_surface_rule(wx, wy, wz, biome_id, noise_gen)
    chunk.generation_stage = 3
    chunk.is_dirty = True

def generate_chunk_decorations(cx, cz, noise_gen, seed):
    chunk = get_chunk(cx, cz)
    if chunk.generation_stage < 3:
        return
    if chunk.generation_stage >= 4:
        return
    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE
    biome_source = MultiNoiseBiomeSource(seed, noise_gen)

    # 树木（仅森林）
    for _ in range(3):
        wx = base_x + random.randint(0, CHUNK_SIZE-1)
        wz = base_z + random.randint(0, CHUNK_SIZE-1)
        if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
            continue
        biome_id = biome_source.get_biome(wx, 64, wz)
        if biome_id != 1:   # forest
            continue
        ground_y = None
        for y in range(WORLD_TOP-1, WORLD_BOTTOM-1, -1):
            if is_solid(wx, y, wz):
                ground_y = y
                break
        if ground_y is None:
            continue
        if get_block(wx, ground_y, wz) in ('grass_block','sand'):
            tree_height = random.randint(4,7)
            for h in range(1, tree_height+1):
                set_block(wx, ground_y+h, wz, 'wood')
            for dx in range(-2,3):
                for dz in range(-2,3):
                    for dy in range(tree_height-2, tree_height+2):
                        dist = abs(dx)+abs(dz)+abs(dy-tree_height+1)
                        if dist <= 3 and random.random() < 0.85:
                            bx, by, bz = wx+dx, ground_y+dy, wz+dz
                            if not is_solid(bx, by, bz):
                                set_block(bx, by, bz, 'leaves')
    chunk.generation_stage = 4
    chunk.is_dirty = True

def generate_chunk(cx, cz, noise_gen, seed):
    chunk = get_chunk(cx, cz)
    if chunk.is_generated:
        return

    apply_biomes(cx, cz, noise_gen, seed)
    generate_chunk_terrain(cx, cz, noise_gen, seed)
    apply_surface(cx, cz, noise_gen)
    generate_chunk_decorations(cx, cz, noise_gen, seed)

    chunk.rebuild_mesh()
    chunk.load_level = LOAD_LEVEL_FULL
    chunk.is_generated = True

def generate_chunk_to_level(cx, cz, noise_gen, seed, target_level):
    chunk = get_chunk(cx, cz)
    if chunk.load_level <= target_level:
        return

    if target_level >= LOAD_LEVEL_INACCESSIBLE:
        if chunk.generation_stage < 1:
            apply_biomes(cx, cz, noise_gen, seed)
        if chunk.generation_stage < 2:
            generate_chunk_terrain(cx, cz, noise_gen, seed)
        if chunk.generation_stage < 3:
            apply_surface(cx, cz, noise_gen)

    if target_level <= LOAD_LEVEL_FULL:
        if chunk.generation_stage < 4:
            generate_chunk_decorations(cx, cz, noise_gen, seed)
        chunk.rebuild_mesh()
        chunk.is_generated = True

    chunk.load_level = target_level

def update_chunk_load_levels(player_x, player_z, noise_gen, seed):
    pcx, pcz = get_chunk_pos(player_x, player_z)
    to_unload = []
    load_range = LOAD_DIST
    for dx in range(-load_range, load_range+1):
        for dz in range(-load_range, load_range+1):
            cx, cz = pcx+dx, pcz+dz
            if abs(cx*CHUNK_SIZE) > WORLD_RADIUS or abs(cz*CHUNK_SIZE) > WORLD_RADIUS:
                continue
            dist = max(abs(dx), abs(dz))
            target_level = calculate_load_level(dist)
            if target_level <= LOAD_DIST:
                generate_chunk_to_level(cx, cz, noise_gen, seed, target_level)

    for (cx,cz), chunk in chunks.items():
        dist = max(abs(cx-pcx), abs(cz-pcz))
        if dist > LOAD_DIST:
            to_unload.append((cx,cz))

    for cx,cz in to_unload:
        chunk = chunks.get((cx,cz))
        if chunk:
            # 释放该区块所有子区块实际申请的 VBO（faceVBO/lineVBO）。
            # 旧代码删的是 Chunk 包装层上恒为 0 的 face_vbo/line_vbo，子区块 VBO 从未释放 → 显存泄漏。
            vbos_to_delete = []
            for i in range(NUM_SECTIONS):
                sub = chunk.get_subchunk(i)
                if sub is None:
                    continue
                if sub.faceVBO != 0:
                    vbos_to_delete.append(sub.faceVBO)
                    sub.faceVBO = 0
                if sub.lineVBO != 0:
                    vbos_to_delete.append(sub.lineVBO)
                    sub.lineVBO = 0
            if vbos_to_delete:
                glDeleteBuffers(len(vbos_to_delete), vbos_to_delete)
            del chunks[(cx,cz)]