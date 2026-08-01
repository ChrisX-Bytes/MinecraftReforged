# chunk_manager.py
import numpy as np
import ctypes
from OpenGL.GL import *
from config import *

# ---------- 立方体几何数据 ----------
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
    {"dir": (0,1,0), "verts": [(-0.5,0.5,-0.5),(0.5,0.5,-0.5),(0.5,0.5,0.5),
                               (0.5,0.5,0.5),(-0.5,0.5,0.5),(-0.5,0.5,-0.5)]},
    {"dir": (0,-1,0), "verts": [(-0.5,-0.5,0.5),(0.5,-0.5,0.5),(0.5,-0.5,-0.5),
                                (0.5,-0.5,-0.5),(-0.5,-0.5,-0.5),(-0.5,-0.5,0.5)]},
    {"dir": (1,0,0), "verts": [(0.5,-0.5,-0.5),(0.5,0.5,-0.5),(0.5,0.5,0.5),
                               (0.5,0.5,0.5),(0.5,-0.5,0.5),(0.5,-0.5,-0.5)]},
    {"dir": (-1,0,0), "verts": [(-0.5,-0.5,0.5),(-0.5,0.5,0.5),(-0.5,0.5,-0.5),
                                (-0.5,0.5,-0.5),(-0.5,-0.5,-0.5),(-0.5,-0.5,0.5)]},
    {"dir": (0,0,1), "verts": [(-0.5,-0.5,0.5),(0.5,-0.5,0.5),(0.5,0.5,0.5),
                               (0.5,0.5,0.5),(-0.5,0.5,0.5),(-0.5,-0.5,0.5)]},
    {"dir": (0,0,-1), "verts": [(0.5,-0.5,-0.5),(-0.5,-0.5,-0.5),(-0.5,0.5,-0.5),
                                (-0.5,0.5,-0.5),(0.5,0.5,-0.5),(0.5,-0.5,-0.5)]},
]

def get_face_color(btype, face_dir):
    if btype == 'grass_block':
        return BLOCK_COLORS['grass_block'] if face_dir == (0,1,0) else BLOCK_COLORS['dirt']
    return BLOCK_COLORS.get(btype, (0.5,0.5,0.5))

# ---------- 全局区块字典 ----------
chunks = {}

def calculate_load_level(dist):
    if dist <= 4:
        return LOAD_LEVEL_ENTITY
    elif dist <= 8:
        return LOAD_LEVEL_BLOCK
    elif dist <= RENDER_DIST:
        return LOAD_LEVEL_FULL
    elif dist <= LOAD_DIST:
        return LOAD_LEVEL_INACCESSIBLE
    else:
        return LOAD_LEVEL_UNLOADED

class Chunk:
    def __init__(self, cx, cz):
        self.cx = cx
        self.cz = cz
        self.sections = [{} for _ in range(NUM_SECTIONS)]
        self.biome_map = {}
        self.is_dirty = True
        self.face_vbo = glGenBuffers(1)
        self.line_vbo = glGenBuffers(1)
        self.face_count = 0
        self.line_count = 0
        self.generation_stage = 0
        self.is_generated = False
        self.load_level = LOAD_LEVEL_UNLOADED
        self.fluid_levels = {}  # {(x,y,z): level} 存储水的深度 (0=源, 1-7=流动)
        self.pending_fluids = set()  # 待更新的流体位置

    def get_section_index(self, y):
        y_abs = y + 64
        if y_abs < 0 or y_abs >= CHUNK_HEIGHT:
            return None
        return y_abs // SECTION_HEIGHT

    def get_local_y(self, y):
        y_abs = y + 64
        return y_abs % SECTION_HEIGHT

    def get_block(self, wx, wy, wz):
        sec_idx = self.get_section_index(wy)
        if sec_idx is None:
            return None
        local_y = self.get_local_y(wy)
        lx = wx - self.cx * CHUNK_SIZE
        lz = wz - self.cz * CHUNK_SIZE
        if not (0 <= lx < CHUNK_SIZE and 0 <= lz < CHUNK_SIZE):
            return None
        return self.sections[sec_idx].get((lx, local_y, lz), None)

    def set_block(self, wx, wy, wz, block_type, fluid_level=None):
        """设置方块，可选指定流体深度"""
        sec_idx = self.get_section_index(wy)
        if sec_idx is None:
            return
        local_y = self.get_local_y(wy)
        lx = wx - self.cx * CHUNK_SIZE
        lz = wz - self.cz * CHUNK_SIZE
        if not (0 <= lx < CHUNK_SIZE and 0 <= lz < CHUNK_SIZE):
            return
        if block_type is None:
            self.sections[sec_idx].pop((lx, local_y, lz), None)
            # 移除流体数据
            self.fluid_levels.pop((wx, wy, wz), None)
            self.pending_fluids.discard((wx, wy, wz))
        else:
            self.sections[sec_idx][(lx, local_y, lz)] = block_type
            if block_type == 'water':
                if fluid_level is None:
                    fluid_level = 0
                self.fluid_levels[(wx, wy, wz)] = fluid_level
                self.pending_fluids.add((wx, wy, wz))
            else:
                self.fluid_levels.pop((wx, wy, wz), None)
                self.pending_fluids.discard((wx, wy, wz))
        self.is_dirty = True

    def get_fluid_level(self, wx, wy, wz):
        return self.fluid_levels.get((wx, wy, wz), -1)

    def rebuild_mesh(self):
        face_vertices = []
        line_vertices = []
        for sec_idx, section in enumerate(self.sections):
            if not section:
                continue
            base_y = sec_idx * SECTION_HEIGHT - 64
            for (lx, ly, lz), btype in section.items():
                wx = self.cx * CHUNK_SIZE + lx
                wy = base_y + ly
                wz = self.cz * CHUNK_SIZE + lz
                exposed = False
                for face in FACES:
                    dx,dy,dz = face["dir"]
                    if not is_solid(wx+dx, wy+dy, wz+dz):
                        exposed = True
                        r,g,b = get_face_color(btype, face["dir"])
                        for vx,vy,vz in face["verts"]:
                            face_vertices.extend([wx+vx, wy+vy, wz+vz, r,g,b])
                if exposed:
                    for edge in CUBE_EDGES:
                        for idx in edge:
                            vx,vy,vz = CUBE_VERTICES[idx]
                            line_vertices.extend([wx+vx, wy+vy, wz+vz, 0.0,0.0,0.0])
        if face_vertices:
            face_data = np.array(face_vertices, dtype=np.float32)
            self.face_count = len(face_data)//6
            glBindBuffer(GL_ARRAY_BUFFER, self.face_vbo)
            glBufferData(GL_ARRAY_BUFFER, face_data.nbytes, face_data, GL_DYNAMIC_DRAW)
        else:
            self.face_count = 0
        if line_vertices:
            line_data = np.array(line_vertices, dtype=np.float32)
            self.line_count = len(line_data)//6
            glBindBuffer(GL_ARRAY_BUFFER, self.line_vbo)
            glBufferData(GL_ARRAY_BUFFER, line_data.nbytes, line_data, GL_DYNAMIC_DRAW)
        else:
            self.line_count = 0
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.is_dirty = False
        self.generation_stage = 7
        self.is_generated = True

# ---------- 全局操作函数 ----------
def get_chunk(cx, cz):
    key = (cx, cz)
    if key not in chunks:
        chunks[key] = Chunk(cx, cz)
    return chunks[key]

def get_chunk_pos(wx, wz):
    return wx // CHUNK_SIZE, wz // CHUNK_SIZE

def set_block(wx, wy, wz, block_type, fluid_level=None):
    """全局设置方块，支持流体深度"""
    cx, cz = get_chunk_pos(wx, wz)
    chunk = get_chunk(cx, cz)
    chunk.set_block(wx, wy, wz, block_type, fluid_level)

def is_solid(wx, wy, wz):
    cx, cz = get_chunk_pos(wx, wz)
    chunk = chunks.get((cx, cz))
    if chunk is None:
        return False
    return chunk.get_block(wx, wy, wz) is not None

def get_block(wx, wy, wz):
    cx, cz = get_chunk_pos(wx, wz)
    chunk = chunks.get((cx, cz))
    if chunk is None:
        return None
    return chunk.get_block(wx, wy, wz)

def rebuild_chunk(cx, cz):
    chunk = chunks.get((cx, cz))
    if chunk:
        chunk.rebuild_mesh()

def rebuild_neighbors(cx, cz):
    for dx in (-1,0,1):
        for dz in (-1,0,1):
            if (cx+dx, cz+dz) in chunks:
                rebuild_chunk(cx+dx, cz+dz)