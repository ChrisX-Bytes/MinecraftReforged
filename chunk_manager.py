# chunk_manager.py
# Chunk management using C++ core (minecraft_core).
# All data is stored in C++ objects; Python acts as wrapper.

import math
import ctypes
import numpy as np
from OpenGL.GL import *
from config import *
import minecraft_core as mc

# Global storage for chunks: keys are (cx, cz) -> Chunk wrapper
chunks = {}

# Global rebuild queue (for compatibility, but C++ handles dirty sections)
rebuild_queue = set()

# Global C++ World instance (initialized in main.py)
world = None

# Block type to ID mapping (must match C++ block_ids.h)
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
    # Add more as needed
}

def init_world():
    """Initialize C++ World instance. Call once at startup."""
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
        # C++ Chunk object (created or retrieved from World)
        self.cpp_chunk = world.getChunk(cx, cz)
        # Keep compatibility attributes
        self.is_dirty = False  # Not used; dirty tracked per subchunk in C++
        self.face_vbo = 0
        self.line_vbo = 0
        self.face_count = 0
        self.line_count = 0
        # load level is stored in C++ but we mirror it here for compatibility
        self.load_level = self.cpp_chunk.loadLevel

    def get_block(self, wx, wy, wz):
        bid = self.cpp_chunk.getBlock(wx, wy, wz)
        return get_block_name(bid)

    def set_block(self, wx, wy, wz, block_type, fluid_level=None):
        bid = get_block_id(block_type)
        self.cpp_chunk.setBlock(wx, wy, wz, bid)
        if block_type == 'water':
            # Compress coordinates into 64-bit key (simple shift)
            pos = (wx << 40) | (wy << 20) | wz
            # Ask fluid simulator to activate this source (fluid_sim is global)
            # We'll call fluid_sim.setSource in main.py via a global reference
            # For now, we just mark pending fluid in C++ chunk
            self.cpp_chunk.pendingFluids.add(pos)
        # C++ will handle dirty marking; we just need to add to rebuild_queue for compatibility
        rebuild_queue.add(self)

    def rebuild_mesh(self):
        """Rebuild all dirty subchunks by calling C++ rebuildDirtySubChunks."""
        self.cpp_chunk.rebuildDirtySubChunks()
        # After rebuild, we need to upload VBO data? Actually C++ updates VBOs inside.
        # But Python still needs to know face counts for each subchunk.
        # We'll read them from C++ subchunks when rendering.
        # No need to do anything here.
        pass

    def get_subchunk(self, idx):
        return self.cpp_chunk.getSubChunk(idx)

    # Compatibility properties
    @property
    def is_generated(self):
        return self.cpp_chunk.isGenerated

    @is_generated.setter
    def is_generated(self, value):
        self.cpp_chunk.isGenerated = value

    @property
    def generation_stage(self):
        return 7 if self.is_generated else 0

    @generation_stage.setter
    def generation_stage(self, value):
        pass  # ignore

    @property
    def load_level(self):
        return self.cpp_chunk.loadLevel

    @load_level.setter
    def load_level(self, value):
        self.cpp_chunk.loadLevel = value

    def get_fluid_level(self, wx, wy, wz):
        # For now, we don't store fluid levels in Python; they are in C++ Chunk.
        # We'll need to add a method to Chunk to retrieve fluid level.
        # Simulate by returning -1 if not found.
        return -1

# ---------- Utility functions (mostly unchanged but using C++ world) ----------

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
                # Mark all subchunks dirty in C++
                for i in range(NUM_SECTIONS):
                    sub = ch.get_subchunk(i)
                    if sub:
                        sub.markDirty()
                rebuild_queue.add(ch)

def calculate_load_level(dist_or_cx, cz=None, player_x=None, player_z=None):
    # same as original, unchanged
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