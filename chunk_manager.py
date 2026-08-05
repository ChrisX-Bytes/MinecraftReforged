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
fluid_sim = None  # 由 main.py 在初始化后通过 register_fluid_sim 注入

def register_fluid_sim(sim):
    global fluid_sim
    fluid_sim = sim

def _encode_pos(wx, wy, wz):
    # 与 C++ FluidSimulator::encode 完全一致：wx(24) | wy(16) | wz(24)，总 64 位。
    # 各段按位截断后左移，绝不超 uint64。
    MASK24 = 0xFFFFFF
    MASK16 = 0xFFFF
    return (((wx & MASK24) << 40) | ((wy & MASK16) << 24) | (wz & MASK24))

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
BLOCK_WATER_ID = BLOCK_ID_MAP['water']

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

    def set_block(self, wx, wy, wz, block_type, fluid_level=None, activate_fluid=True):
        bid = get_block_id(block_type)
        # 先读旧方块：判断本次改动是否涉及水（新放的是水，或旧方块是水被替换/挖掉）。
        # 只有涉及水时才需要触发流体调度，避免生成阶段海量非水方块淹没调度桶。
        old_bid = self.cpp_chunk.getBlock(wx, wy, wz)
        involves_water = (bid == BLOCK_WATER_ID) or (old_bid == BLOCK_WATER_ID)

        self.cpp_chunk.setBlock(wx, wy, wz, bid)
        # 水位：玩家放置的水默认为水源(level 0)；非水方块水位清零
        if bid == BLOCK_WATER_ID:
            self.cpp_chunk.setWaterLevel(wx, wy, wz, fluid_level if fluid_level is not None else 0)
        else:
            self.cpp_chunk.setWaterLevel(wx, wy, wz, 0)
        # 仅当涉及水、且允许激活时才调度（生成阶段传 activate_fluid=False 整条路径都不激活）
        if activate_fluid and involves_water and fluid_sim is not None:
            pos = _encode_pos(wx, wy, wz)
            fluid_sim.activate(pos)
            for dx, dy, dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                fluid_sim.activate(_encode_pos(wx+dx, wy+dy, wz+dz))
        rebuild_queue.add(self)

    def rebuild_mesh(self):
        # 只重建真正变脏的子区块（C++ setBlock 已自动只标脏改动的那一个子区块）。
        # 不要无条件 markDirty 全部——那会让 C++ buildMesh 的 if(!dirty) 快路径失效，
        # 导致每帧全量重建+全量上传 VBO，这是加入水后卡顿的核心原因。
        for idx in range(NUM_SECTIONS):
            sub = self.cpp_chunk.getSubChunk(idx)
            if sub is None:
                continue
            if not sub.isDirty():
                continue
            verts = sub.buildMesh()
            # 面数据
            if verts:
                if sub.faceVBO == 0:
                    sub.faceVBO = glGenBuffers(1)
                data = np.array(verts, dtype=np.float32)
                glBindBuffer(GL_ARRAY_BUFFER, sub.faceVBO)
                glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
                glBindBuffer(GL_ARRAY_BUFFER, 0)
                sub.faceCount = len(verts) // 8  # 每顶点 8 float: x,y,z,u,v,r,g,b
            else:
                sub.faceCount = 0
            # 线框数据（C++ buildMesh 不再填充 lineVertices；保留分支以兼容旧接口）
            line_verts = sub.lineVertices
            if line_verts:
                if sub.lineVBO == 0:
                    sub.lineVBO = glGenBuffers(1)
                ldata = np.array(line_verts, dtype=np.float32)
                glBindBuffer(GL_ARRAY_BUFFER, sub.lineVBO)
                glBufferData(GL_ARRAY_BUFFER, ldata.nbytes, ldata, GL_DYNAMIC_DRAW)
                glBindBuffer(GL_ARRAY_BUFFER, 0)
                sub.lineCount = len(line_verts) // 6
            else:
                sub.lineCount = 0

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
    # 注意：get_block 对空气返回字符串 'air'（非 None），不能再用 `if not b`
    if b is None or b == 'air':
        return False
    if b == 'water':
        return False
    return True

def is_targetable(wx, wy, wz):
    """射线能否命中此方块（含水）。用于挖掘：MC 用桶舀水，本作没桶，让水可被挖掉。"""
    b = get_block(wx, wy, wz)
    if b is None or b == 'air':
        return False
    return True  # 含水，可被射线命中并挖掘

def set_block(wx, wy, wz, block_type, fluid_level=None, activate_fluid=True):
    cx, cz = get_chunk_pos(wx, wz)
    chunk = get_chunk(cx, cz)
    chunk.set_block(wx, wy, wz, block_type, fluid_level, activate_fluid)

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


def reset_world():
    global world, chunks
    # 清除 Python 侧的缓存引用（让旧对象被垃圾回收）
    chunks.clear()
    # 重新创建 C++ World
    world = None
    init_world()  # 这会创建新的 mc.World 实例
    # 关键：reset_world 会销毁旧 World 实例，FluidSimulator 内部持有的旧指针会悬空，
    # 必须更新为新 World 指针，否则 tick() 访问已释放内存会段错误。
    if fluid_sim is not None:
        fluid_sim.setWorld(world)