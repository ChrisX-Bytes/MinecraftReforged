# chunk_manager.py
# Chunk management utilities used by main.py and world_gen.
# Lazy VBO creation, protections to avoid GL access violations, and chunk data storage.

import math
import ctypes
import numpy as np
from OpenGL.GL import *
from config import *

# Global storage for chunks: keys are (cx, cz) -> Chunk instance
chunks = {}

# Global rebuild queue (chunks needing mesh rebuild). Modules should add chunks here
rebuild_queue = set()

# Simple utility: chunk size (X,Z)
CHUNK_SIZE_X = CHUNK_SIZE if 'CHUNK_SIZE' in globals() else 16
CHUNK_SIZE_Z = CHUNK_SIZE if 'CHUNK_SIZE' in globals() else 16

# Cube geometry helpers (used for line debug/outline generation)
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

class Chunk:
    def __init__(self, cx, cz):
        self.cx = int(cx)
        self.cz = int(cz)

        # sections: list of dicts mapping (lx, ly, lz) -> block_type
        self.sections = [{} for _ in range(NUM_SECTIONS)]
        self.biome_map = {}
        self.is_dirty = True

        # Mesh / GL handles - lazy (created only when needed in GL context)
        self.face_vbo = 0
        self.line_vbo = 0
        self.face_count = 0
        self.line_count = 0

        # Generation / load status
        self.generation_stage = 0
        self.is_generated = False
        self.load_level = LOAD_LEVEL_UNLOADED

        # Fluid data
        self.fluid_levels = {}  # {(wx,wy,wz): level}
        self.pending_fluids = set()

    def ensure_vbos(self):
        """Create VBOs if not yet created. Must be called in a valid GL context."""
        try:
            if not self.face_vbo:
                self.face_vbo = glGenBuffers(1)
            if not self.line_vbo:
                self.line_vbo = glGenBuffers(1)
        except Exception as e:
            # GL context may not be ready; keep handles 0 and let caller handle missing VBOs
            print("[Chunk.ensure_vbos] GL exception (maybe context not ready):", e)
            self.face_vbo = self.face_vbo or 0
            self.line_vbo = self.line_vbo or 0

    def get_section_index(self, y):
        y_abs = y - WORLD_BOTTOM
        if y_abs < 0 or y_abs >= CHUNK_HEIGHT:
            return None
        return y_abs // SECTION_HEIGHT

    def get_local_y(self, y):
        y_abs = y - WORLD_BOTTOM
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
        rebuild_queue.add(self)

    def get_fluid_level(self, wx, wy, wz):
        return self.fluid_levels.get((wx, wy, wz), -1)

    def rebuild_mesh(self):
        """
        Rebuild mesh for this chunk.
        - Ensure VBOs exist in GL context.
        - Build face and line vertex arrays only if there is geometry.
        - Upload to GL and set counts. If upload fails, leave counts at 0 to avoid draw.
        """
        # Attempt to ensure buffers exist
        self.ensure_vbos()

        face_vertices = []
        line_vertices = []
        for sec_idx, section in enumerate(self.sections):
            if not section:
                continue
            base_y = sec_idx * SECTION_HEIGHT + WORLD_BOTTOM
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

        # Upload faces
        if face_vertices:
            face_data = np.array(face_vertices, dtype=np.float32)
            try:
                glBindBuffer(GL_ARRAY_BUFFER, self.face_vbo)
                glBufferData(GL_ARRAY_BUFFER, face_data.nbytes, face_data, GL_DYNAMIC_DRAW)
                glBindBuffer(GL_ARRAY_BUFFER, 0)
                self.face_count = len(face_data)//6
            except Exception as e:
                print("[Chunk.rebuild_mesh] GL upload failed for faces:", e)
                self.face_count = 0
        else:
            self.face_count = 0

        # Upload lines
        if line_vertices:
            line_data = np.array(line_vertices, dtype=np.float32)
            try:
                glBindBuffer(GL_ARRAY_BUFFER, self.line_vbo)
                glBufferData(GL_ARRAY_BUFFER, line_data.nbytes, line_data, GL_DYNAMIC_DRAW)
                glBindBuffer(GL_ARRAY_BUFFER, 0)
                self.line_count = len(line_data)//6
            except Exception as e:
                print("[Chunk.rebuild_mesh] GL upload failed for lines:", e)
                self.line_count = 0
        else:
            self.line_count = 0

        self.is_dirty = False
        self.generation_stage = 7
        self.is_generated = True

# Utilities
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
                ch.is_dirty = True
                rebuild_queue.add(ch)

def calculate_load_level(dist_or_cx, cz=None, player_x=None, player_z=None):
    """Backwards compatible: either pass a distance or (cx,cz,player_x,player_z)."""
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