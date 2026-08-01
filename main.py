import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import random
import numpy as np
import ctypes
import vnoise
import sys
import os
import heapq
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="vnoise")

# ---------- 字体配置 ----------
FONT_PATH = "./File/minecraftfont.woff"

# ---------- 初始化 ----------
pygame.init()
display = (1024, 768)
screen = pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
pygame.display.set_caption('3D Minecraft')
pygame.mouse.set_visible(False)
pygame.event.set_grab(True)

glEnable(GL_DEPTH_TEST)
glDisable(GL_CULL_FACE)
glDisable(GL_LIGHTING)
glLineWidth(1)
glMatrixMode(GL_PROJECTION)
gluPerspective(70, display[0] / display[1], 0.1, 100.0)
glMatrixMode(GL_MODELVIEW)
glClearColor(0.53, 0.81, 0.92, 1.0)

# ---------- 调试用字体 ----------
try:
    if os.path.exists(FONT_PATH):
        debug_font = pygame.font.Font(FONT_PATH, 18)
    else:
        debug_font = pygame.font.SysFont('monospace', 18)
except Exception as e:
    debug_font = pygame.font.SysFont('monospace', 18)

show_debug = False
fps_counter = 0
fps_time = pygame.time.get_ticks()
fps_display = 0

# ---------- 常量 ----------
CHUNK_SIZE = 16
CHUNK_HEIGHT = 384
WORLD_RADIUS = 50

LOAD_LEVEL_ENTITY = 31
LOAD_LEVEL_BLOCK = 32
LOAD_LEVEL_FULL = 33
LOAD_LEVEL_INACCESSIBLE = 34
LOAD_LEVEL_UNLOADED = 45

RENDER_DIST = 12
LOAD_DIST = RENDER_DIST + 4
CHUNKS_PER_FRAME = 5

# ---------- 方块颜色 ----------
BLOCK_COLORS = {
    'grass': (0.2, 0.7, 0.2),
    'dirt': (0.55, 0.27, 0.07),
    'stone': (0.6, 0.6, 0.6),
    'wood': (0.63, 0.32, 0.18),
    'leaves': (0.0, 0.6, 0.0),
    'sand': (0.93, 0.84, 0.69),
    'snow': (0.95, 0.95, 0.98),
}
block_types = ['grass', 'dirt', 'stone', 'wood', 'leaves', 'sand', 'snow']
selected_block = 'grass'

# ---------- 几何定义 ----------
CUBE_VERTICES = [
    (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
    (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)
]
CUBE_EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7)
]

FACES = [
    {"dir": (0, 1, 0), "verts": [
        (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5)
    ]},
    {"dir": (0, -1, 0), "verts": [
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5)
    ]},
    {"dir": (1, 0, 0), "verts": [
        (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5), (0.5, -0.5, 0.5), (0.5, -0.5, -0.5)
    ]},
    {"dir": (-1, 0, 0), "verts": [
        (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5)
    ]},
    {"dir": (0, 0, 1), "verts": [
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, -0.5, 0.5)
    ]},
    {"dir": (0, 0, -1), "verts": [
        (0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5)
    ]},
]


def get_face_color(btype, face_dir):
    if btype == 'grass':
        if face_dir == (0, 1, 0):
            return BLOCK_COLORS['grass']
        else:
            return BLOCK_COLORS['dirt']
    return BLOCK_COLORS[btype]


# ---------- 加载动画 ----------
def draw_loading(progress):
    glPushAttrib(GL_ALL_ATTRIB_BITS)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, display[0], display[1], 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)

    glClearColor(0.15, 0.15, 0.25, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    bar_width = 400
    bar_height = 20
    cx = display[0] // 2
    cy = display[1] // 2
    bar_x = cx - bar_width // 2
    bar_y = cy - bar_height // 2

    glColor3f(0.3, 0.3, 0.4)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + bar_width, bar_y)
    glVertex2f(bar_x + bar_width, bar_y + bar_height)
    glVertex2f(bar_x, bar_y + bar_height)
    glEnd()

    fill_width = int(bar_width * progress)
    glColor3f(0.2, 0.9, 0.3)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + fill_width, bar_y)
    glVertex2f(bar_x + fill_width, bar_y + bar_height)
    glVertex2f(bar_x, bar_y + bar_height)
    glEnd()

    glColor3f(0.8, 0.8, 0.9)
    glLineWidth(2)
    glBegin(GL_LINE_LOOP)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + bar_width, bar_y)
    glVertex2f(bar_x + bar_width, bar_y + bar_height)
    glVertex2f(bar_x, bar_y + bar_height)
    glEnd()

    pygame.display.flip()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopAttrib()
    glEnable(GL_DEPTH_TEST)


# ---------- 分块系统 ----------
class Chunk:
    def __init__(self, cx, cz):
        self.cx = cx
        self.cz = cz
        self.blocks = {}
        self.is_dirty = True
        self.face_vbo = glGenBuffers(1)
        self.line_vbo = glGenBuffers(1)
        self.face_count = 0
        self.line_count = 0
        self.generation_stage = 0
        self.is_generated = False
        self.load_level = LOAD_LEVEL_UNLOADED

    def get_block(self, wx, wy, wz):
        return self.blocks.get((wx, wy, wz), None)

    def set_block(self, wx, wy, wz, block_type):
        if block_type is None:
            self.blocks.pop((wx, wy, wz), None)
        else:
            self.blocks[(wx, wy, wz)] = block_type
        self.is_dirty = True

    def rebuild_mesh(self):
        face_vertices = []
        line_vertices = []

        for (wx, wy, wz), btype in list(self.blocks.items()):
            has_exposed_face = False
            for face in FACES:
                dx, dy, dz = face["dir"]
                if not is_solid(wx + dx, wy + dy, wz + dz):
                    has_exposed_face = True
                    r, g, b = get_face_color(btype, face["dir"])
                    for vx, vy, vz in face["verts"]:
                        face_vertices.extend([wx + vx, wy + vy, wz + vz, r, g, b])

            if has_exposed_face:
                for edge in CUBE_EDGES:
                    for idx in edge:
                        vx, vy, vz = CUBE_VERTICES[idx]
                        line_vertices.extend([wx + vx, wy + vy, wz + vz, 0.0, 0.0, 0.0])

        if face_vertices:
            face_data = np.array(face_vertices, dtype=np.float32)
            self.face_count = len(face_data) // 6
            glBindBuffer(GL_ARRAY_BUFFER, self.face_vbo)
            glBufferData(GL_ARRAY_BUFFER, face_data.nbytes, face_data, GL_DYNAMIC_DRAW)
        else:
            self.face_count = 0

        if line_vertices:
            line_data = np.array(line_vertices, dtype=np.float32)
            self.line_count = len(line_data) // 6
            glBindBuffer(GL_ARRAY_BUFFER, self.line_vbo)
            glBufferData(GL_ARRAY_BUFFER, line_data.nbytes, line_data, GL_DYNAMIC_DRAW)
        else:
            self.line_count = 0

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.is_dirty = False
        self.generation_stage = 3
        self.is_generated = True


# ---------- 世界管理 ----------
chunks = {}


def get_chunk(cx, cz):
    key = (cx, cz)
    if key not in chunks:
        chunks[key] = Chunk(cx, cz)
    return chunks[key]


def get_chunk_pos(wx, wz):
    cx = wx // CHUNK_SIZE if wx >= 0 else (wx + 1) // CHUNK_SIZE - 1
    cz = wz // CHUNK_SIZE if wz >= 0 else (wz + 1) // CHUNK_SIZE - 1
    return cx, cz


def set_block(wx, wy, wz, block_type):
    cx, cz = get_chunk_pos(wx, wz)
    chunk = get_chunk(cx, cz)
    chunk.set_block(wx, wy, wz, block_type)


def is_solid(wx, wy, wz):
    cx, cz = get_chunk_pos(wx, wz)
    chunk = chunks.get((cx, cz))
    if chunk is None:
        return False
    return chunk.get_block(wx, wy, wz) is not None


def world_get_block(wx, wy, wz):
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
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            if (cx + dx, cz + dz) in chunks:
                rebuild_chunk(cx + dx, cz + dz)


# ---------- 地形生成 ----------
def get_height(x, z, noise_gen):
    scale_continent = 0.005
    scale_main = 0.03
    scale_detail = 0.08
    scale_micro = 0.18
    scale_ridge = 0.04
    continent = noise_gen.noise2(x * scale_continent, z * scale_continent)
    main = noise_gen.noise2(x * scale_main, z * scale_main, octaves=4, persistence=0.5, lacunarity=2.0)
    detail = noise_gen.noise2(x * scale_detail, z * scale_detail, octaves=3, persistence=0.5, lacunarity=2.0)
    micro = noise_gen.noise2(x * scale_micro, z * scale_micro)
    ridge = abs(noise_gen.noise2(x * scale_ridge, z * scale_ridge))
    ridge = 1.0 - ridge * 2.0
    ridge = abs(ridge) * 0.4
    height = (main * 0.6 + detail * 0.3 + micro * 0.1) + ridge * 0.3
    return height


def get_biome(x, z, noise_gen):
    biome_noise = noise_gen.noise2(x * 0.012, z * 0.012)
    if biome_noise < -0.4:
        return 'plains'
    elif biome_noise < 0.1:
        return 'forest'
    elif biome_noise < 0.5:
        return 'hills'
    else:
        return 'mountains'


def get_biome_height_scale(biome):
    scales = {'plains': 0.5, 'forest': 0.7, 'hills': 1.2, 'mountains': 1.8}
    return scales.get(biome, 1.0)


# ---------- 区块生成 ----------
def generate_chunk_terrain(cx, cz, noise_gen, amplitude):
    WORLD_BOTTOM = -64
    chunk = get_chunk(cx, cz)
    if chunk.generation_stage >= 1:
        return

    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE

    for lx in range(CHUNK_SIZE):
        for lz in range(CHUNK_SIZE):
            wx = base_x + lx
            wz = base_z + lz
            if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
                continue

            n = get_height(wx, wz, noise_gen)
            base_height = 64
            h = int((n + 1) * amplitude / 2) + base_height
            if h < 0:
                h = 0

            biome = get_biome(wx, wz, noise_gen)
            scale = get_biome_height_scale(biome)
            h = int((h - base_height) * scale) + base_height

            if biome == 'plains' or biome == 'forest':
                surface_block = 'grass'
            elif biome == 'hills':
                surface_block = 'grass'
            elif biome == 'mountains':
                if h > 120:
                    surface_block = 'snow'
                elif h > 100:
                    surface_block = 'stone'
                else:
                    surface_block = 'grass'
            if h < 64:
                surface_block = 'sand'

            for y in range(h, WORLD_BOTTOM - 1, -1):
                if y == h:
                    set_block(wx, y, wz, surface_block)
                elif y > h - 5:
                    set_block(wx, y, wz, 'dirt')
                elif y > h - 17:
                    set_block(wx, y, wz, 'stone')
                elif y > WORLD_BOTTOM + 3:
                    set_block(wx, y, wz, 'stone')
                else:
                    set_block(wx, y, wz, 'stone')

    chunk.generation_stage = 1


def generate_chunk_decorations(cx, cz, noise_gen):
    chunk = get_chunk(cx, cz)
    if chunk.generation_stage >= 2:
        return

    base_x = cx * CHUNK_SIZE
    base_z = cz * CHUNK_SIZE

    for _ in range(3):
        wx = base_x + random.randint(0, CHUNK_SIZE - 1)
        wz = base_z + random.randint(0, CHUNK_SIZE - 1)
        if abs(wx) > WORLD_RADIUS or abs(wz) > WORLD_RADIUS:
            continue
        biome = get_biome(wx, wz, noise_gen)
        if biome != 'forest':
            continue
        ground_y = None
        for y in range(100, -1, -1):
            if is_solid(wx, y, wz):
                ground_y = y
                break
        if ground_y is None:
            continue
        if world_get_block(wx, ground_y, wz) in ['grass', 'sand']:
            tree_height = random.randint(4, 7)
            for h in range(1, tree_height + 1):
                set_block(wx, ground_y + h, wz, 'wood')
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    for dy in range(tree_height - 2, tree_height + 2):
                        distance = abs(dx) + abs(dz) + abs(dy - tree_height + 1)
                        if distance <= 3 and random.random() < 0.85:
                            bx, by, bz = wx + dx, ground_y + dy, wz + dz
                            if not is_solid(bx, by, bz):
                                set_block(bx, by, bz, 'leaves')

    for _ in range(2):
        wx = base_x + random.randint(0, CHUNK_SIZE - 1)
        wz = base_z + random.randint(0, CHUNK_SIZE - 1)
        if abs(wx) < 5 and abs(wz) < 5:
            continue
        depth = random.randint(5, 20)
        ground_y = None
        for y in range(80, -64, -1):
            if is_solid(wx, y, wz):
                ground_y = y
                break
        if ground_y is None or ground_y < -60:
            continue
        cave_y = max(ground_y - depth, -60)
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in range(-2, 3):
                    if random.random() < 0.3:
                        bx, by, bz = wx + dx, cave_y + dy, wz + dz
                        if is_solid(bx, by, bz):
                            set_block(bx, by, bz, None)

    chunk.generation_stage = 2
    chunk.is_dirty = True


def generate_chunk(cx, cz, noise_gen, amplitude):
    chunk = get_chunk(cx, cz)
    if chunk.is_generated:
        return
    generate_chunk_terrain(cx, cz, noise_gen, amplitude)
    generate_chunk_decorations(cx, cz, noise_gen)
    chunk.rebuild_mesh()
    # ===== 关键修复：设置加载等级 =====
    chunk.load_level = LOAD_LEVEL_FULL


# ===== Minecraft 风格加载等级系统 =====

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


def generate_chunk_to_level(cx, cz, noise_gen, amplitude, target_level):
    chunk = get_chunk(cx, cz)
    if chunk.load_level <= target_level:
        return

    if target_level >= LOAD_LEVEL_INACCESSIBLE and chunk.generation_stage < 1:
        generate_chunk_terrain(cx, cz, noise_gen, amplitude)
        chunk.generation_stage = 1

    if target_level <= LOAD_LEVEL_FULL and chunk.generation_stage < 3:
        if chunk.generation_stage < 2:
            generate_chunk_decorations(cx, cz, noise_gen)
            chunk.generation_stage = 2
        chunk.rebuild_mesh()
        chunk.generation_stage = 3

    chunk.load_level = target_level


def update_chunk_load_levels(player_x, player_z, noise_gen, amplitude):
    pcx, pcz = get_chunk_pos(player_x, player_z)
    to_unload = []

    load_range = LOAD_DIST
    for dx in range(-load_range, load_range + 1):
        for dz in range(-load_range, load_range + 1):
            cx, cz = pcx + dx, pcz + dz
            if abs(cx * CHUNK_SIZE) > WORLD_RADIUS or abs(cz * CHUNK_SIZE) > WORLD_RADIUS:
                continue
            dist = max(abs(dx), abs(dz))
            target_level = calculate_load_level(dist)
            if target_level <= LOAD_DIST:
                generate_chunk_to_level(cx, cz, noise_gen, amplitude, target_level)

    for (cx, cz), chunk in chunks.items():
        dist = max(abs(cx - pcx), abs(cz - pcz))
        if dist > LOAD_DIST:
            to_unload.append((cx, cz))

    for cx, cz in to_unload:
        chunk = chunks.get((cx, cz))
        if chunk:
            glDeleteBuffers(2, [chunk.face_vbo, chunk.line_vbo])
            del chunks[(cx, cz)]


# ---------- 初始生成 ----------
def generate_initial_world():
    noise_gen = vnoise.Noise(seed=114514)
    amplitude = 50

    start_cx, start_cz = 0, 0
    total_chunks = (2 * RENDER_DIST + 1) ** 2
    generated = 0

    draw_loading(0.0)

    for dx in range(-RENDER_DIST, RENDER_DIST + 1):
        for dz in range(-RENDER_DIST, RENDER_DIST + 1):
            cx, cz = start_cx + dx, start_cz + dz
            generate_chunk(cx, cz, noise_gen, amplitude)
            generated += 1
            progress = generated / total_chunks
            draw_loading(progress)
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit()
                    sys.exit()

    for dx in range(-LOAD_DIST, LOAD_DIST + 1):
        for dz in range(-LOAD_DIST, LOAD_DIST + 1):
            cx, cz = start_cx + dx, start_cz + dz
            if (cx, cz) not in chunks:
                chunk = get_chunk(cx, cz)
                generate_chunk_terrain(cx, cz, noise_gen, amplitude)
                # ===== 设置加载等级为不可访问 =====
                chunk.load_level = LOAD_LEVEL_INACCESSIBLE

    glBindBuffer(GL_ARRAY_BUFFER, 0)
    glDisableClientState(GL_VERTEX_ARRAY)
    glDisableClientState(GL_COLOR_ARRAY)
    glDisable(GL_BLEND)
    glClearColor(0.53, 0.81, 0.92, 1.0)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(70, display[0] / display[1], 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glEnable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)

    return noise_gen, amplitude


# ---------- 执行生成 ----------
noise_gen, amplitude = generate_initial_world()
glBindBuffer(GL_ARRAY_BUFFER, 0)
glDisableClientState(GL_VERTEX_ARRAY)
glDisableClientState(GL_COLOR_ARRAY)
glClearColor(0.53, 0.81, 0.92, 1.0)
glMatrixMode(GL_PROJECTION)
glLoadIdentity()
gluPerspective(70, display[0] / display[1], 0.1, 100.0)
glMatrixMode(GL_MODELVIEW)
glLoadIdentity()
glEnable(GL_DEPTH_TEST)
glDisable(GL_LIGHTING)


# ---------- 玩家 ----------
class Player:
    def __init__(self):
        self.x, self.y, self.z = 0, 5, 0
        self.rot_x = 0
        self.rot_y = 0
        self.vx = self.vy = self.vz = 0
        self.on_ground = False
        self.width = 0.3
        self.height = 1.8

        self.prev_x = self.x
        self.prev_y = self.y
        self.prev_z = self.z
        self.prev_rot_x = self.rot_x
        self.prev_rot_y = self.rot_y

        self.EPSILON = 0.0625
        self.STEP_HEIGHT = 0.6
        self.eye_height = 1.62

        self.spawn_x = 0
        self.spawn_y = 65
        self.spawn_z = 0

    def collide(self, x, y, z):
        shrink = self.EPSILON
        half_width = self.width - shrink
        height = self.height - shrink * 2

        if half_width <= 0 or height <= 0:
            return False

        foot_y = shrink
        head_y = shrink + height

        for dx in (-half_width, half_width):
            for dz in (-half_width, half_width):
                for dy in (foot_y, head_y):
                    bx = int(math.floor(x + dx + 0.5))
                    by = int(math.floor(y + dy + 0.5))
                    bz = int(math.floor(z + dz + 0.5))
                    if is_solid(bx, by, bz):
                        return True
        return False

    def update(self, dt, keys):
        speed = 4.317
        yaw = math.radians(self.rot_y)
        fwd = (math.sin(yaw), 0, -math.cos(yaw))
        right = (math.cos(yaw), 0, math.sin(yaw))

        mx = mz = 0
        if keys[K_w]: mx += fwd[0]; mz += fwd[2]
        if keys[K_s]: mx -= fwd[0]; mz -= fwd[2]
        if keys[K_a]: mx -= right[0]; mz -= right[2]
        if keys[K_d]: mx += right[0]; mz += right[2]

        l = math.hypot(mx, mz)
        if l > 0: mx /= l; mz /= l
        self.vx = mx * speed
        self.vz = mz * speed

        if keys[K_SPACE] and self.on_ground:
            self.vy = 9.0
        self.vy -= 32 * dt
        if self.vy < -78.4: self.vy = -78.4

        start_x, start_y, start_z = self.x, self.y, self.z

        new_y = self.y + self.vy * dt
        self.on_ground = False
        if not self.collide(self.x, new_y, self.z):
            self.y = new_y
        else:
            low, high = self.y, new_y
            for _ in range(8):
                mid = (low + high) * 0.5
                if self.collide(self.x, mid, self.z):
                    high = mid
                else:
                    low = mid
            self.y = low
            if self.vy < 0:
                self.on_ground = True
            self.vy = 0

        new_x = self.x + self.vx * dt
        new_z = self.z + self.vz * dt
        original_y = self.y

        if not self.collide(new_x, self.y, new_z):
            self.x = new_x
            self.z = new_z
        else:
            stepped = False
            if self.on_ground:
                step_y = self.y + self.STEP_HEIGHT
                if not self.collide(new_x, step_y, new_z):
                    self.y = step_y
                    self.x = new_x
                    self.z = new_z
                    stepped = True

            if not stepped:
                self.y = original_y
                if not self.collide(new_x, self.y, self.z):
                    self.x = new_x
                if not self.collide(self.x, self.y, new_z):
                    self.z = new_z

        speed_x = (self.x - start_x) / dt
        speed_z = (self.z - start_z) / dt
        horizontal_speed = math.hypot(speed_x, speed_z)
        if horizontal_speed > 5.0:
            self.x, self.y, self.z = start_x, start_y, start_z
            self.vx, self.vy, self.vz = 0, 0, 0

        if self.y < -64:
            self.x = self.spawn_x
            self.y = self.spawn_y
            self.z = self.spawn_z
            self.vx = 0
            self.vy = 0
            self.vz = 0
            self.prev_x = self.x
            self.prev_y = self.y
            self.prev_z = self.z

    def intersects_block(self, bx, by, bz):
        shrink = self.EPSILON
        half_width = self.width - shrink
        height = self.height - shrink * 2

        if half_width <= 0 or height <= 0:
            return False

        p_min_x = self.x - half_width
        p_max_x = self.x + half_width
        p_min_y = self.y + shrink
        p_max_y = self.y + shrink + height
        p_min_z = self.z - half_width
        p_max_z = self.z + half_width

        b_min_x = bx - 0.5
        b_max_x = bx + 0.5
        b_min_y = by - 0.5
        b_max_y = by + 0.5
        b_min_z = bz - 0.5
        b_max_z = bz + 0.5

        if p_max_x <= b_min_x or p_min_x >= b_max_x:
            return False
        if p_max_y <= b_min_y or p_min_y >= b_max_y:
            return False
        if p_max_z <= b_min_z or p_min_z >= b_max_z:
            return False
        return True

    def eye(self):
        return (self.x, self.y + self.eye_height, self.z)

    def look(self):
        pitch = math.radians(self.rot_x)
        yaw = math.radians(self.rot_y)
        dir_x = math.cos(pitch) * math.sin(yaw)
        dir_y = math.sin(pitch)
        dir_z = -math.cos(pitch) * math.cos(yaw)
        return (dir_x, dir_y, dir_z)


player = Player()

# ---- 出生点 ----
spawn_x, spawn_z = 0, 0
ground_y = None
for y in range(100, -64, -1):
    if is_solid(spawn_x, y, spawn_z):
        ground_y = y
        break

if ground_y is not None:
    player.x = spawn_x
    player.y = ground_y + 1.0
    player.z = spawn_z
else:
    player.x = 0
    player.y = 65
    player.z = 0

player.spawn_x = player.x
player.spawn_y = player.y
player.spawn_z = player.z
player.prev_x = player.x
player.prev_y = player.y
player.prev_z = player.z


# ---------- 射线投射 ----------
def raycast(origin, direction, max_dist=10):
    dx, dy, dz = direction
    length = math.hypot(dx, dy, dz)
    if length < 1e-12:
        return None, None
    dx, dy, dz = dx / length, dy / length, dz / length
    x, y, z = origin

    bx = int(math.floor(x + 0.5))
    by = int(math.floor(y + 0.5))
    bz = int(math.floor(z + 0.5))
    start_block = (bx, by, bz)

    step_x = 1 if dx > 0 else -1
    step_y = 1 if dy > 0 else -1
    step_z = 1 if dz > 0 else -1

    t_delta_x = abs(1.0 / dx) if abs(dx) > 1e-12 else float('inf')
    t_delta_y = abs(1.0 / dy) if abs(dy) > 1e-12 else float('inf')
    t_delta_z = abs(1.0 / dz) if abs(dz) > 1e-12 else float('inf')

    if dx > 0:
        t_max_x = ((bx + 0.5) - x) / dx
    elif dx < 0:
        t_max_x = ((bx - 0.5) - x) / dx
    else:
        t_max_x = float('inf')

    if dy > 0:
        t_max_y = ((by + 0.5) - y) / dy
    elif dy < 0:
        t_max_y = ((by - 0.5) - y) / dy
    else:
        t_max_y = float('inf')

    if dz > 0:
        t_max_z = ((bz + 0.5) - z) / dz
    elif dz < 0:
        t_max_z = ((bz - 0.5) - z) / dz
    else:
        t_max_z = float('inf')

    travel_dist = 0.0
    normal = (0, 0, 0)
    while travel_dist <= max_dist:
        if (bx, by, bz) != start_block and is_solid(bx, by, bz):
            return (bx, by, bz), normal
        if t_max_x < t_max_y and t_max_x < t_max_z:
            travel_dist = t_max_x
            bx += step_x
            t_max_x += t_delta_x
            normal = (-step_x, 0, 0)
        elif t_max_y < t_max_z:
            travel_dist = t_max_y
            by += step_y
            t_max_y += t_delta_y
            normal = (0, -step_y, 0)
        else:
            travel_dist = t_max_z
            bz += step_z
            t_max_z += t_delta_z
            normal = (0, 0, -step_z)
    return None, None


# ---------- 准星 ----------
def draw_crosshair():
    glPushMatrix()
    glLoadIdentity()
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, display[0], display[1], 0, -1, 1)
    glDisable(GL_DEPTH_TEST)
    cx, cy = display[0] // 2, display[1] // 2
    glColor3f(1, 1, 1)
    glLineWidth(2)
    size = 12
    glBegin(GL_LINES)
    glVertex2f(cx - size, cy)
    glVertex2f(cx + size, cy)
    glVertex2f(cx, cy - size)
    glVertex2f(cx, cy + size)
    glEnd()
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


# ---------- 渲染 ----------
def render_chunks():
    for (cx, cz), chunk in chunks.items():
        if chunk.load_level > LOAD_LEVEL_FULL:
            continue
        if chunk.is_dirty:
            chunk.rebuild_mesh()

        if chunk.face_count > 0:
            glBindBuffer(GL_ARRAY_BUFFER, chunk.face_vbo)
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)
            glVertexPointer(3, GL_FLOAT, 24, ctypes.c_void_p(0))
            glColorPointer(3, GL_FLOAT, 24, ctypes.c_void_p(12))
            glDrawArrays(GL_TRIANGLES, 0, chunk.face_count)
            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_COLOR_ARRAY)

        if chunk.line_count > 0:
            glBindBuffer(GL_ARRAY_BUFFER, chunk.line_vbo)
            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)
            glVertexPointer(3, GL_FLOAT, 24, ctypes.c_void_p(0))
            glColorPointer(3, GL_FLOAT, 24, ctypes.c_void_p(12))
            glDrawArrays(GL_LINES, 0, chunk.line_count)
            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_COLOR_ARRAY)

    glBindBuffer(GL_ARRAY_BUFFER, 0)


# ---------- 调试 ----------
def draw_debug_info():
    if not show_debug:
        return

    global fps_counter, fps_time, fps_display
    fps_counter += 1
    current_time = pygame.time.get_ticks()
    if current_time - fps_time >= 1000:
        fps_display = fps_counter
        fps_counter = 0
        fps_time = current_time

    cx, cz = get_chunk_pos(player.x, player.z)
    block_x = int(math.floor(player.x + 0.5))
    block_y = int(math.floor(player.y + 0.5))
    block_z = int(math.floor(player.z + 0.5))

    loaded = len([c for c in chunks.values() if c.load_level <= LOAD_LEVEL_FULL])
    total = len(chunks)
    lines = [
        f"XYZ: {player.x:.1f} {player.y:.1f} {player.z:.1f}",
        f"Block: {block_x} {block_y} {block_z}",
        f"Chunk: {cx} {cz}",
        f"FPS: {fps_display}",
        f"Loaded: {loaded}/{total} chunks",
        f"Block: {selected_block}",
    ]

    line_height = 22
    padding = 10
    surf_width = 340
    surf_height = len(lines) * line_height + 30
    text_surf = pygame.Surface((surf_width, surf_height), pygame.SRCALPHA)
    text_surf.fill((0, 0, 0, 0))

    y_pos = 15
    for line in lines:
        line_surf = debug_font.render(line, True, (255, 255, 255))
        text_surf.blit(line_surf, (padding, y_pos))
        y_pos += line_height

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, display[0], display[1], 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glColor4f(0.0, 0.0, 0.0, 0.5)
    glBegin(GL_QUADS)
    glVertex2f(10, 10)
    glVertex2f(text_surf.get_width() + 20, 10)
    glVertex2f(text_surf.get_width() + 20, text_surf.get_height() + 20)
    glVertex2f(10, text_surf.get_height() + 20)
    glEnd()

    width, height = text_surf.get_size()
    data = pygame.image.tobytes(text_surf, 'RGBA', False)

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    glEnable(GL_TEXTURE_2D)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(10, 10)
    glTexCoord2f(1, 0); glVertex2f(width + 10, 10)
    glTexCoord2f(1, 1); glVertex2f(width + 10, height + 10)
    glTexCoord2f(0, 1); glVertex2f(10, height + 10)
    glEnd()

    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)
    glDeleteTextures([tex_id])
    glBindTexture(GL_TEXTURE_2D, 0)

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    glEnable(GL_DEPTH_TEST)


# ---------- 主循环 ----------
clock = pygame.time.Clock()
running = True
lock_mouse = True

PHYSICS_DT = 0.05
physics_accumulator = 0.0

while running:
    dt = clock.tick(144) / 1000.0
    keys = pygame.key.get_pressed()

    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        elif event.type == MOUSEMOTION:
            if lock_mouse:
                dx, dy = event.rel
                player.rot_y += dx * 0.2
                player.rot_x -= dy * 0.2
                player.rot_x = max(-89, min(89, player.rot_x))
        elif event.type == MOUSEBUTTONDOWN:
            eye = player.eye()
            direction = player.look()
            if event.button == 1:
                pos, _ = raycast(eye, direction)
                if pos:
                    if is_solid(*pos):
                        set_block(pos[0], pos[1], pos[2], None)
                        cx, cz = get_chunk_pos(pos[0], pos[2])
                        rebuild_neighbors(cx, cz)
            elif event.button == 3:
                pos, normal = raycast(eye, direction)
                if pos and normal:
                    nx, ny, nz = normal
                    new_pos = (pos[0] + nx, pos[1] + ny, pos[2] + nz)
                    if not is_solid(*new_pos) and not player.intersects_block(*new_pos):
                        set_block(new_pos[0], new_pos[1], new_pos[2], selected_block)
                        cx, cz = get_chunk_pos(new_pos[0], new_pos[2])
                        rebuild_neighbors(cx, cz)
        elif event.type == KEYDOWN:
            if event.key == K_F1:
                lock_mouse = not lock_mouse
                if lock_mouse:
                    pygame.mouse.set_visible(False)
                    pygame.event.set_grab(True)
                else:
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
            elif event.key == K_F3:
                show_debug = not show_debug
            elif event.key == K_1:
                selected_block = block_types[0]
            elif event.key == K_2:
                selected_block = block_types[1]
            elif event.key == K_3:
                selected_block = block_types[2]
            elif event.key == K_4:
                selected_block = block_types[3]
            elif event.key == K_5:
                selected_block = block_types[4]
            elif event.key == K_6:
                selected_block = block_types[5]
            elif event.key == K_7:
                selected_block = block_types[6]
            elif event.key == K_ESCAPE:
                running = False

    physics_accumulator += dt
    while physics_accumulator >= PHYSICS_DT:
        player.prev_x = player.x
        player.prev_y = player.y
        player.prev_z = player.z
        player.prev_rot_x = player.rot_x
        player.prev_rot_y = player.rot_y

        player.update(PHYSICS_DT, keys)
        physics_accumulator -= PHYSICS_DT

    update_chunk_load_levels(player.x, player.z, noise_gen, amplitude)

    alpha = physics_accumulator / PHYSICS_DT
    if alpha > 1.0:
        alpha = 1.0
    elif alpha < 0.0:
        alpha = 0.0

    render_x = player.prev_x + (player.x - player.prev_x) * alpha
    render_y = player.prev_y + (player.y - player.prev_y) * alpha
    render_z = player.prev_z + (player.z - player.prev_z) * alpha
    render_rot_x = player.prev_rot_x + (player.rot_x - player.prev_rot_x) * alpha
    render_rot_y = player.prev_rot_y + (player.rot_y - player.prev_rot_y) * alpha

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    render_eye = (render_x, render_y + player.eye_height, render_z)
    pitch = math.radians(render_rot_x)
    yaw = math.radians(render_rot_y)
    render_direction = (math.cos(pitch) * math.sin(yaw),
                        math.sin(pitch),
                        -math.cos(pitch) * math.cos(yaw))
    look_at = (render_eye[0] + render_direction[0],
               render_eye[1] + render_direction[1],
               render_eye[2] + render_direction[2])
    gluLookAt(render_eye[0], render_eye[1], render_eye[2],
              look_at[0], look_at[1], look_at[2],
              0, 1, 0)

    render_chunks()

    physical_eye = player.eye()
    physical_direction = player.look()
    hit_pos, _ = raycast(physical_eye, physical_direction)
    if hit_pos and is_solid(*hit_pos):
        x, y, z = hit_pos
        btype = world_get_block(x, y, z)
        if btype:
            r, g, b = get_face_color(btype, (0, 1, 0))
            dark_r, dark_g, dark_b = r * 0.5, g * 0.5, b * 0.5
            glPushMatrix()
            glTranslatef(x, y, z)
            glScalef(1.001, 1.001, 1.001)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glDisable(GL_DEPTH_TEST)
            glColor4f(dark_r, dark_g, dark_b, 0.6)
            glBegin(GL_TRIANGLES)
            for face in FACES:
                for vx, vy, vz in face["verts"]:
                    glVertex3f(vx, vy, vz)
            glEnd()
            glEnable(GL_DEPTH_TEST)
            glDisable(GL_BLEND)
            glPopMatrix()

    draw_crosshair()
    draw_debug_info()
    pygame.display.flip()

for chunk in chunks.values():
    glDeleteBuffers(2, [chunk.face_vbo, chunk.line_vbo])
pygame.quit()