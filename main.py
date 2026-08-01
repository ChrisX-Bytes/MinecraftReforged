# main.py
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import random
import sys
import os
import warnings
import ctypes
import time

warnings.filterwarnings("ignore")

from config import *
from chunk_manager import (
    chunks, get_chunk, set_block, get_block, is_solid,
    rebuild_chunk, rebuild_neighbors, Chunk, get_chunk_pos,
    calculate_load_level, FACES, get_face_color
)
from world_gen import generate_chunk, generate_chunk_to_level, update_chunk_load_levels
from world_gen.noise import PerlinNoise3D
from world_gen.fluid_simulator import FluidSimulator

# ---------- 调试开关 ----------
DEBUG_PROFILE = True  # 打开后会打印流体 tick/ms 和每帧重建耗时，调试时开启，稳定后建议关闭

# ---------- 初始化 ----------
pygame.init()
display = (1024, 768)
screen = pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
pygame.display.set_caption('3D Minecraft - Reforged')
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

# ---------- 流体与性能参数（可调整） ----------
FLUID_TPS = 20.0                     # 逻辑 tick 频率（ticks per second）
FLUID_DT = 1.0 / FLUID_TPS
fluid_time_acc = 0.0

# 每个逻辑 tick 最多允许的写操作（set_block），防止单次 tick 写太多触发大量重建
fluid_simulator = FluidSimulator(updates_per_tick=80)
# fluid_simulator = FluidSimulator(updates_per_tick=150)  # 如果机器性能允许可调高
# fluid_simulator = FluidSimulator(updates_per_tick=40)   # 更保守的值

# 每帧最多重建的区块数量（避免 glBufferData 峰值）
REBUILDS_PER_FRAME = 2

# ---------- 字体 ----------
FONT_PATH = "./File/minecraftfont.woff"
try:
    if os.path.exists(FONT_PATH):
        debug_font = pygame.font.Font(FONT_PATH, 18)
    else:
        debug_font = pygame.font.SysFont('monospace', 18)
except:
    debug_font = pygame.font.SysFont('monospace', 18)

show_debug = False
fps_counter = 0
fps_time = pygame.time.get_ticks()
fps_display = 0
selected_block = 'grass_block'

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
    glClearColor(0.15, 0.15, 0.25, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    bar_width, bar_height = 400, 20
    cx, cy = display[0] // 2, display[1] // 2
    bar_x, bar_y = cx - bar_width // 2, cy - bar_height // 2
    glColor3f(0.3, 0.3, 0.4)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y); glVertex2f(bar_x + bar_width, bar_y)
    glVertex2f(bar_x + bar_width, bar_y + bar_height); glVertex2f(bar_x, bar_y + bar_height)
    glEnd()
    fill = int(bar_width * progress)
    glColor3f(0.2, 0.9, 0.3)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y); glVertex2f(bar_x + fill, bar_y)
    glVertex2f(bar_x + fill, bar_y + bar_height); glVertex2f(bar_x, bar_y + bar_height)
    glEnd()
    glColor3f(0.8, 0.8, 0.9)
    glLineWidth(2)
    glBegin(GL_LINE_LOOP)
    glVertex2f(bar_x, bar_y); glVertex2f(bar_x + bar_width, bar_y)
    glVertex2f(bar_x + bar_width, bar_y + bar_height); glVertex2f(bar_x, bar_y + bar_height)
    glEnd()
    pygame.display.flip()
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopAttrib()
    glEnable(GL_DEPTH_TEST)

# ---------- 初始世界生成 ----------
def generate_initial_world():
    seed = 114514
    noise_gen = PerlinNoise3D(seed=seed)
    start_cx, start_cz = 0, 0
    total_chunks = (2 * RENDER_DIST + 1) ** 2
    generated = 0
    draw_loading(0.0)

    for dx in range(-RENDER_DIST, RENDER_DIST + 1):
        for dz in range(-RENDER_DIST, RENDER_DIST + 1):
            cx, cz = start_cx + dx, start_cz + dz
            generate_chunk(cx, cz, noise_gen, seed)
            generated += 1
            draw_loading(generated / total_chunks)
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit(); sys.exit()

    for dx in range(-LOAD_DIST, LOAD_DIST + 1):
        for dz in range(-LOAD_DIST, LOAD_DIST + 1):
            cx, cz = start_cx + dx, start_cz + dz
            if (cx, cz) not in chunks:
                chunk = get_chunk(cx, cz)
                generate_chunk_to_level(cx, cz, noise_gen, seed, LOAD_LEVEL_INACCESSIBLE)

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
    return noise_gen, seed

noise_gen, seed = generate_initial_world()

# ---------- 玩家 ----------
class Player:
    def __init__(self):
        self.x, self.y, self.z = 0, 65, 0
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
        self.spawn_x, self.spawn_y, self.spawn_z = 0, 65, 0

    def collide(self, x, y, z):
        shrink = self.EPSILON
        half = self.width - shrink
        h = self.height - shrink * 2
        if half <= 0 or h <= 0: return False
        foot_y = shrink
        head_y = shrink + h
        for dx in (-half, half):
            for dz in (-half, half):
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
        if l > 0:
            mx /= l; mz /= l
        self.vx = mx * speed
        self.vz = mz * speed
        if keys[K_SPACE] and self.on_ground:
            self.vy = 9.0
        self.vy -= 32 * dt
        if self.vy < -78.4:
            self.vy = -78.4

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
        orig_y = self.y
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
                self.y = orig_y
                if not self.collide(new_x, self.y, self.z):
                    self.x = new_x
                if not self.collide(self.x, self.y, new_z):
                    self.z = new_z

        if self.y < -64:
            self.x, self.y, self.z = self.spawn_x, self.spawn_y, self.spawn_z
            self.vx = self.vy = self.vz = 0

    def eye(self):
        return (self.x, self.y + self.eye_height, self.z)

    def look(self):
        pitch = math.radians(self.rot_x)
        yaw = math.radians(self.rot_y)
        return (math.cos(pitch) * math.sin(yaw), math.sin(pitch), -math.cos(pitch) * math.cos(yaw))

    def intersects_block(self, bx, by, bz):
        shrink = self.EPSILON
        half = self.width - shrink
        h = self.height - shrink * 2
        if half <= 0 or h <= 0: return False
        pminx = self.x - half; pmaxx = self.x + half
        pminy = self.y + shrink; pmaxy = self.y + shrink + h
        pminz = self.z - half; pmaxz = self.z + half
        bminx = bx - 0.5; bmaxx = bx + 0.5
        bminy = by - 0.5; bmaxy = by + 0.5
        bminz = bz - 0.5; bmaxz = bz + 0.5
        return not (pmaxx <= bminx or pminx >= bmaxx or pmaxy <= bminy or pminy >= bmaxy or pmaxz <= bminz or pminz >= bmaxz)

player = Player()

# 放置玩家到正确位置
spawn_x, spawn_z = 0, 0
for y in range(100, -64, -1):
    if is_solid(spawn_x, y, spawn_z):
        player.y = y + 1
        break
player.x, player.z = spawn_x, spawn_z
player.spawn_x, player.spawn_y, player.spawn_z = player.x, player.y, player.z
player.prev_x, player.prev_y, player.prev_z = player.x, player.y, player.z

# ---------- 射线投射 ----------
def raycast(origin, direction, max_dist=10):
    dx, dy, dz = direction
    length = math.hypot(dx, dy, dz)
    if length < 1e-12: return None, None
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
    t_max_x = ((bx + 0.5) - x) / dx if dx > 0 else ((bx - 0.5) - x) / dx if dx < 0 else float('inf')
    t_max_y = ((by + 0.5) - y) / dy if dy > 0 else ((by - 0.5) - y) / dy if dy < 0 else float('inf')
    t_max_z = ((bz + 0.5) - z) / dz if dz > 0 else ((bz - 0.5) - z) / dz if dz < 0 else float('inf')
    travel = 0.0
    normal = (0, 0, 0)
    while travel <= max_dist:
        if (bx, by, bz) != start_block and is_solid(bx, by, bz):
            return (bx, by, bz), normal
        if t_max_x < t_max_y and t_max_x < t_max_z:
            travel = t_max_x
            bx += step_x
            t_max_x += t_delta_x
            normal = (-step_x, 0, 0)
        elif t_max_y < t_max_z:
            travel = t_max_y
            by += step_y
            t_max_y += t_delta_y
            normal = (0, -step_y, 0)
        else:
            travel = t_max_z
            bz += step_z
            t_max_z += t_delta_z
            normal = (0, 0, -step_z)
    return None, None

# ---------- 渲染（含受限重建） ----------
def render_chunks():
    start_rebuild_time = time.time() if DEBUG_PROFILE else None
    pcx, pcz = get_chunk_pos(player.x, player.z)
    items = list(chunks.items())
    # 优先靠近玩家的区块先重建
    items.sort(key=lambda it: max(abs(it[0][0] - pcx), abs(it[0][1] - pcz)))
    rebuilds = 0
    rebuild_ms_total = 0.0
    for (cx, cz), chunk in items:
        if chunk.load_level > LOAD_LEVEL_FULL:
            continue
        if chunk.is_dirty:
            if rebuilds < REBUILDS_PER_FRAME:
                if DEBUG_PROFILE:
                    t0 = time.time()
                    chunk.rebuild_mesh()
                    t1 = time.time()
                    rebuild_ms_total += (t1 - t0) * 1000.0
                else:
                    chunk.rebuild_mesh()
                rebuilds += 1
            else:
                # defer rebuild to later frames
                continue
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
    if DEBUG_PROFILE:
        rebuild_time = (time.time() - start_rebuild_time) * 1000.0 if start_rebuild_time else rebuild_ms_total
        # Show rebuild total time for this frame (approx)
        print(f"[PROFILE] rebuilds={rebuilds}, rebuild_ms={rebuild_time:.1f}")

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
    glVertex2f(cx - size, cy); glVertex2f(cx + size, cy)
    glVertex2f(cx, cy - size); glVertex2f(cx, cy + size)
    glEnd()
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

def draw_debug_info():
    if not show_debug:
        return
    global fps_counter, fps_time, fps_display
    fps_counter += 1
    cur = pygame.time.get_ticks()
    if cur - fps_time >= 1000:
        fps_display = fps_counter
        fps_counter = 0
        fps_time = cur
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
    glColor4f(0, 0, 0, 0.5)
    w, h = text_surf.get_size()
    glBegin(GL_QUADS)
    glVertex2f(10, 10); glVertex2f(w + 20, 10); glVertex2f(w + 20, h + 20); glVertex2f(10, h + 20)
    glEnd()
    data = pygame.image.tobytes(text_surf, 'RGBA', False)
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glEnable(GL_TEXTURE_2D)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(10, 10)
    glTexCoord2f(1, 0); glVertex2f(w + 10, 10)
    glTexCoord2f(1, 1); glVertex2f(w + 10, h + 10)
    glTexCoord2f(0, 1); glVertex2f(10, h + 10)
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

    # 处理输入事件
    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        elif event.type == MOUSEMOTION and lock_mouse:
            dx, dy = event.rel
            player.rot_y += dx * 0.2
            player.rot_x -= dy * 0.2
            player.rot_x = max(-89, min(89, player.rot_x))
        elif event.type == MOUSEBUTTONDOWN:
            eye = player.eye()
            direction = player.look()
            if event.button == 1:
                pos, _ = raycast(eye, direction)
                if pos and is_solid(*pos):
                    set_block(pos[0], pos[1], pos[2], None)
                    cx, cz = get_chunk_pos(pos[0], pos[2])
                    rebuild_neighbors(cx, cz)
            elif event.button == 3:
                pos, normal = raycast(eye, direction)
                if pos and normal:
                    nx, ny, nz = normal
                    new_pos = (pos[0] + nx, pos[1] + ny, pos[2] + nz)
                    if not is_solid(*new_pos) and not player.intersects_block(*new_pos):
                        if selected_block == 'water':
                            set_block(new_pos[0], new_pos[1], new_pos[2], 'water', 0)
                        else:
                            set_block(new_pos[0], new_pos[1], new_pos[2], selected_block)
                        cx, cz = get_chunk_pos(new_pos[0], new_pos[2])
                        rebuild_neighbors(cx, cz)
        elif event.type == KEYDOWN:
            if event.key == K_F1:
                lock_mouse = not lock_mouse
                pygame.mouse.set_visible(not lock_mouse)
                pygame.event.set_grab(lock_mouse)
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
            elif event.key == K_8:
                selected_block = block_types[7] if len(block_types) > 7 else selected_block
            elif event.key == K_ESCAPE:
                running = False

    # 物理固定步长（包括流体）：每 FLUID_DT 秒跑一次
    fluid_time_acc += dt
    while fluid_time_acc >= FLUID_DT:
        if DEBUG_PROFILE:
            t0 = time.time()
            fluid_simulator.tick()
            t1 = time.time()
        else:
            fluid_simulator.tick()
        fluid_time_acc -= FLUID_DT

    # 物理/玩家运动（基于 PHYSICS_DT 的子步）
    physics_accumulator += dt
    while physics_accumulator >= PHYSICS_DT:
        player.prev_x, player.prev_y, player.prev_z = player.x, player.y, player.z
        player.prev_rot_x, player.prev_rot_y = player.rot_x, player.rot_y
        player.update(PHYSICS_DT, keys)
        physics_accumulator -= PHYSICS_DT

    # 区块加载/生成逻辑（保留）
    update_chunk_load_levels(player.x, player.z, noise_gen, seed)

    # 渲染插值
    alpha = min(1.0, max(0.0, physics_accumulator / PHYSICS_DT))
    render_x = player.prev_x + (player.x - player.prev_x) * alpha
    render_y = player.prev_y + (player.y - player.prev_y) * alpha
    render_z = player.prev_z + (player.z - player.prev_z) * alpha
    render_rot_x = player.prev_rot_x + (player.rot_x - player.prev_rot_x) * alpha
    render_rot_y = player.prev_rot_y + (player.rot_y - player.prev_rot_y) * alpha

    # 渲染
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    eye = (render_x, render_y + player.eye_height, render_z)
    pitch = math.radians(render_rot_x)
    yaw = math.radians(render_rot_y)
    look_dir = (math.cos(pitch) * math.sin(yaw), math.sin(pitch), -math.cos(pitch) * math.cos(yaw))
    look_at = (eye[0] + look_dir[0], eye[1] + look_dir[1], eye[2] + look_dir[2])
    gluLookAt(eye[0], eye[1], eye[2], look_at[0], look_at[1], look_at[2], 0, 1, 0)

    render_chunks()

    physical_eye = player.eye()
    physical_dir = player.look()
    hit_pos, _ = raycast(physical_eye, physical_dir)
    if hit_pos and is_solid(*hit_pos):
        x, y, z = hit_pos
        btype = get_block(x, y, z)
        if btype:
            r, g, b = get_face_color(btype, (0, 1, 0))
            dark = (r * 0.5, g * 0.5, b * 0.5)
            glPushMatrix()
            glTranslatef(x, y, z)
            glScalef(1.001, 1.001, 1.001)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glDisable(GL_DEPTH_TEST)
            glColor4f(dark[0], dark[1], dark[2], 0.6)
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

# 清理
for chunk in chunks.values():
    glDeleteBuffers(2, [chunk.face_vbo, chunk.line_vbo])
pygame.quit()