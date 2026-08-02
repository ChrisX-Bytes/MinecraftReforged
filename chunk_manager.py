# chunk_manager.py
# Chunk management using C++ core (minecraft_core).
# C++ generates vertex data, Python uploads to VBO.

import math
import ctypes
import numpy as np
from OpenGL.GL import *
from config import *
import minecraft_core as mc

# ---------- 几何辅助（供渲染使用，与 C++ 核心无关） ----------
CUBE_VERTICES = [
    (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
    (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)
]
CUBE_EDGES = [
    (0,1),(1,2),(2,3),(3,0),
    (4,5),(5,6),(6,7),(7,4),
    (0,4),(1,5),(2,6),(3,7)
]

FACES = [
    {"dir": (0,1,0), "verts": [(-0.5,0.5,-0.5),(0.5,0.5,-0.5),(0.5,0.5,0.5),(0.5,0.5,0.5),(-0.5,0.5,0.5),(-0.5,0.5,-0.5)]},
    {"dir": (0,-1,0), "verts": [(-0.5,-0.5,0.5),(0.5,-0.5,0.5),(0.5,-0.5,-0.5),(0.5,-0.5,-0.5),(-0.5,-0.5,-0.5),(-0.5,-0.5,0.5)]},
    {"dir": (1,0,0), "verts": [(0.5,-0.5,-0.5),(0.5,0.5,-0.5),(0.5,0.5,0.5),(0.5,0.5,0.5),(0.5,-0.5,0.5),(0.5,-0.5,-0.5)]},
    {"dir": (-1,0,0), "verts": [(-0.5,-0.5,0.5),(-0.5,0.5,0.5),(-0.5,0.5,-0.5),(-0.5,0.5,-0.5),(-0.5,-0.5,-0.5),(-0.5,-0.5,0.5)]},
    {"dir": (0,0,1), "verts": [(-0.5,-0.5,0.5),(0.5,-0.5,0.5),(0.5,0.5,0.5),(0.5,0.5,0.5),(-0.5,0.5,0.5),(-0.5,-0.5,0.5)]},
    {"dir": (0,0,-1), "verts": [(0.5,-0.5,-0.5),(-0.5,-0.5,-0.5),(-0.5,0.5,-0.5),(-0.5,0.5,-0.5),(0.5,0.5,-0.5),(0.5,-0.5,-0.5)]},
]

def get_face_color(btype, face_dir):
    if btype == 'grass_block':
        return BLOCK_COLORS['grass_block'] if face_dir == (0,1,0) else BLOCK_COLORS['dirt']
    return BLOCK_COLORS.get(btype, (0.5,0.5,0.5))

# ---------- C++ 核心封装 ----------
chunks = {}
rebuild_queue = set()
world = None

BLOCK_ID_MAP = {
    'air': 0,
    'stone': 1,
    'grass_block': 2,
    'dirt': 3,
    'wood': 4,
    'leaves': 5,
    'sand': 6,
    'snow': 7,
    'bedrock': 8,
    'water': 9,
}

def init_world():
    global world
    if world is None:
        world = mc.World()
    return world

def get_block_id(block_type):
    return BLOCK_ID_MAP.get(block_type, 0)

def get_block_name(block_id):
    for name, bid in BLOCK_ID_MAP.items():
        if bid == block_id:
            return name
    return None

class Chunk:
    """Python wrapper for C++ Chunk object."""
    def __init__(self, cx, cz):
        self.cx = int(cx)
        self.cz = int(cz)
        self.cpp_chunk = world.getChunk(cx, cz)
        self.is_dirty = False
        self.face_vbo = 0
        self.line_vbo = 0
        self.face_count = 0
        self.line_count = 0
        self.load_level = self.cpp_chunk.loadLevel
        self._is_generated = False
        self._generation_stage = 0
        self.biome_map = {}

    def get_block(self, wx, wy, wz):
        bid = self.cpp_chunk.getBlock(wx, wy, wz)
        return get_block_name(bid)

    def set_block(self, wx, wy, wz, block_type, fluid_level=None):
        bid = get_block_id(block_type)
        self.cpp_chunk.setBlock(wx, wy, wz, bid)
        if block_type == 'water':
            pos = (wx << 40) | (wy << 20) | wz
            self.cpp_chunk.pendingFluids.add(pos)
        rebuild_queue.add(self)

    def rebuild_mesh(self):
        # 1. 强制所有子区块标记为脏
        for idx in range(NUM_SECTIONS):
            sub = self.cpp_chunk.getSubChunk(idx)
            if sub:
                sub.markDirty()

        # 2. 重建所有脏子区块
        for idx in range(NUM_SECTIONS):
            sub = self.cpp_chunk.getSubChunk(idx)
            if sub is None:
                continue
            if sub.isDirty():
                verts = sub.buildMesh()
                if verts:
                    if sub.faceVBO == 0:
                        sub.faceVBO = glGenBuffers(1)
                    data = np.array(verts, dtype=np.float32)
                    glBindBuffer(GL_ARRAY_BUFFER, sub.faceVBO)
                    glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
                    glBindBuffer(GL_ARRAY_BUFFER, 0)
                    sub.faceCount = len(verts) // 6
                    # 打印调试（可选）
                    # print(f"SubChunk {idx} faceCount = {sub.faceCount}")
                else:
                    sub.faceCount = 0

    def get_subchunk(self, idx):
        return self.cpp_chunk.getSubChunk(idx)

    @property
    def is_generated(self):
        return self._is_generated

    @is_generated.setter
    def is_generated(self, value):
        self._is_generated = value

    @property
    def generation_stage(self):
        return self._generation_stage

    @generation_stage.setter
    def generation_stage(self, value):
        self._generation_stage = value

    @property
    def load_level(self):
        return self.cpp_chunk.loadLevel

    @load_level.setter
    def load_level(self, value):
        self.cpp_chunk.loadLevel = value

    def get_fluid_level(self, wx, wy, wz):
        return -1

# ---------- Utility functions ----------
def get_chunk(cx, cz):
    key = (int(cx), int(cz))
    c = chunks.get(key)
    if c is None:
        c = Chunk(cx, cz)
        chunks[key] = c
    return c

def get_chunk_pos(wx, wz):
    cx = math.floor(wx / CHUNK_SIZE)
    cz = math.floor(wz / CHUNK_SIZE)
    return int(cx), int(cz)

def get_block(wx, wy, wz):
    cx, cz = get_chunk_pos(wx, wz)
    chunk = chunks.get((cx, cz))
    if not chunk:
        return None
    return chunk.get_block(wx, wy, wz)

def is_solid(wx, wy, wz):
    b = get_block(wx, wy, wz)
    if not b:
        return False
    if b == 'water':
        return False
    return True

def set_block(wx, wy, wz, block_type, fluid_level=None):
    cx, cz = get_chunk_pos(wx, wz)
    chunk = get_chunk(cx, cz)
    chunk.set_block(wx, wy, wz, block_type, fluid_level)

def rebuild_chunk(cx, cz):
    chunk = chunks.get((cx, cz))
    if chunk:
        chunk.rebuild_mesh()

def rebuild_neighbors(cx, cz):
    for dx in (-1,0,1):
        for dz in (-1,0,1):
            key = (cx+dx, cz+dz)
            ch = chunks.get(key)
            if ch:
                for i in range(NUM_SECTIONS):
                    sub = ch.get_subchunk(i)
                    if sub:
                        sub.markDirty()
                rebuild_queue.add(ch)

def calculate_load_level(dist_or_cx, cz=None, player_x=None, player_z=None):
    if cz is None and player_x is None and player_z is None:
        d = int(dist_or_cx)
        if d <= 4:
            return LOAD_LEVEL_ENTITY
        elif d <= 8:
            return LOAD_LEVEL_BLOCK
        elif d <= RENDER_DIST:
            return LOAD_LEVEL_FULL
        elif d <= LOAD_DIST:
            return LOAD_LEVEL_INACCESSIBLE
        else:
            return LOAD_LEVEL_UNLOADED
    cx = int(dist_or_cx)
    cz = int(cz)
    if player_x is None:
        return LOAD_LEVEL_FULL
    pcx = math.floor(player_x / CHUNK_SIZE)
    pcz = math.floor(player_z / CHUNK_SIZE)
    d = max(abs(cx - pcx), abs(cz - pcz))
    if d <= 4:
        return LOAD_LEVEL_ENTITY
    elif d <= 8:
        return LOAD_LEVEL_BLOCK
    elif d <= RENDER_DIST:
        return LOAD_LEVEL_FULL
    elif d <= LOAD_DIST:
        return LOAD_LEVEL_INACCESSIBLE
    else:
        return LOAD_LEVEL_UNLOADED