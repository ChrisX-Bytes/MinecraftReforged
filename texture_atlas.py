# texture_atlas.py
# Minecraft-style texture atlas system.
# Loads individual 16x16 block textures, packs them into a single GL texture atlas,
# and provides UV coordinate lookup by texture ID.
#
# MC block textures may be P (palette), L (grayscale), or RGBA.
# Grass block side = base + overlay composited (MC tinter behavior).
# Water textures are animated sprite sheets; we take the first frame.

import os
import numpy as np
from PIL import Image
from OpenGL.GL import *

TEXTURE_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'textures', 'block')
TEX_SIZE = 16  # Each texture slot is 16x16 pixels

# ── Texture ID constants ──
# C++ will use these same values in buildMesh() to emit UV coords.
# Convention: texId = atlas_row * ATLAS_COLS + atlas_col
# Each block maps to (top, side, bottom) texture IDs.
TEX_GRASS_TOP       = 0
TEX_GRASS_SIDE      = 1
TEX_DIRT            = 2
TEX_STONE           = 3
TEX_OAK_LOG_SIDE    = 4
TEX_OAK_LOG_TOP     = 5
TEX_OAK_LEAVES      = 6
TEX_SAND            = 7
TEX_SNOW            = 8
TEX_BEDROCK         = 9
TEX_WATER_STILL     = 10
TEX_WATER_FLOW      = 11
TEX_COUNT           = 12

# Block face → texture mapping (face_dir: 0=top, 1=bottom, 2-5=sides)
# Used in C++ via get_tex_id(BlockID, face_dir)
BLOCK_TEX_MAP = {
    # (block_id, face_dir) -> tex_id
    # face_dir: 0=top, 1=bottom, 2=right(+x), 3=left(-x), 4=front(+z), 5=back(-z)
}


def _load_and_convert(path):
    """Load a PNG texture file, convert to RGBA 16x16."""
    img = Image.open(path)
    img = img.convert('RGBA')
    img = img.resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)
    return img


def _composite_grass_side():
    """MC grass_block_side = dirt base + grayscale overlay × biome tint.
    In vanilla MC, grass_block_side.png is the dirt-only base; the overlay
    (grass_block_side_overlay.png, L-mode) is multiplied by the grass biome
    colormap then alpha-blended onto the dirt. We use dirt.png as the base to
    avoid double-compositing, and apply Plains grass tint #7CBD6B."""
    base_path = os.path.join(TEXTURE_DIR, 'dirt.png')
    overlay_path = os.path.join(TEXTURE_DIR, 'grass_block_side_overlay.png')

    # Dirt base
    base = Image.open(base_path).convert('RGBA').resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)

    # Overlay: L-mode grayscale mask; high values = grass, low values = dirt
    overlay_l = Image.open(overlay_path).convert('L').resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)

    # Plains biome grass tint color (from MC grass.png colormap, index 127)
    grass_r, grass_g, grass_b = 124, 189, 107  # #7CBD6B

    result = base.copy()
    pixels = result.load()
    ov_pixels = overlay_l.load()
    for y in range(TEX_SIZE):
        for x in range(TEX_SIZE):
            alpha = ov_pixels[x, y] / 255.0  # 1.0 = fully grass, 0.0 = fully dirt
            base_r, base_g, base_b, base_a = pixels[x, y]
            r = int(base_r * (1 - alpha) + grass_r * alpha)
            g = int(base_g * (1 - alpha) + grass_g * alpha)
            b = int(base_b * (1 - alpha) + grass_b * alpha)
            pixels[x, y] = (r, g, b, 255)
    return result


def _apply_biome_tint_grass(img):
    """Apply Plains grass biome tint to a grayscale grass texture.
    MC grass_block_top.png is L-mode grayscale; it is tinted at runtime by
    the grass.png biome colormap. Plains tint = #7CBD6B (124, 189, 107)."""
    gray = img.convert('L')
    result = Image.new('RGBA', (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    pixels = result.load()
    gray_px = gray.load()
    tint_r, tint_g, tint_b = 124, 189, 107  # Plains #7CBD6B
    for y in range(TEX_SIZE):
        for x in range(TEX_SIZE):
            v = gray_px[x, y] / 255.0
            pixels[x, y] = (int(tint_r * v), int(tint_g * v), int(tint_b * v), 255)
    return result


def _apply_biome_tint_leaves(img):
    """Apply Plains foliage biome tint to oak_leaves texture.
    MC oak_leaves.png is palette-mode; it is tinted at runtime by
    the foliage.png biome colormap. Plains tint = #77AB2F (119, 171, 47).
    Alpha channel (transparent pixels) is preserved."""
    base = img.convert('RGBA')
    result = Image.new('RGBA', (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    pixels = result.load()
    base_px = base.load()
    tint_r, tint_g, tint_b = 119, 171, 47  # Plains #77AB2F
    for y in range(TEX_SIZE):
        for x in range(TEX_SIZE):
            r, g, b, a = base_px[x, y]
            if a == 0:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                # Multiply texture RGB by normalized tint
                pixels[x, y] = (
                    min(255, int(r * tint_r / 255)),
                    min(255, int(g * tint_g / 255)),
                    min(255, int(b * tint_b / 255)),
                    a
                )
    return result


def _crop_water_frame(path):
    """Water textures are sprite sheets (e.g., 16x512 or 32x1024).
    Take the first frame (top 16x16)."""
    img = Image.open(path).convert('RGBA')
    w, h = img.size
    # The first frame is the top 16 rows
    return img.crop((0, 0, min(w, TEX_SIZE), TEX_SIZE)).resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)


def _load_all_textures():
    """Load all needed textures into a list of PIL RGBA images (16x16)."""
    textures = [None] * TEX_COUNT

    # 0: grass_block_top (grayscale + biome tint)
    grass_top_raw = Image.open(os.path.join(TEXTURE_DIR, 'grass_block_top.png')).resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)
    textures[TEX_GRASS_TOP] = _apply_biome_tint_grass(grass_top_raw)

    # 1: grass_block_side (composited with overlay)
    textures[TEX_GRASS_SIDE] = _composite_grass_side()

    # 2: dirt
    textures[TEX_DIRT] = _load_and_convert(os.path.join(TEXTURE_DIR, 'dirt.png'))

    # 3: stone
    textures[TEX_STONE] = _load_and_convert(os.path.join(TEXTURE_DIR, 'stone.png'))

    # 4: oak_log side
    textures[TEX_OAK_LOG_SIDE] = _load_and_convert(os.path.join(TEXTURE_DIR, 'oak_log.png'))

    # 5: oak_log top
    textures[TEX_OAK_LOG_TOP] = _load_and_convert(os.path.join(TEXTURE_DIR, 'oak_log_top.png'))

    # 6: oak_leaves (biome tint applied)
    leaves_raw = Image.open(os.path.join(TEXTURE_DIR, 'oak_leaves.png')).resize((TEX_SIZE, TEX_SIZE), Image.NEAREST)
    textures[TEX_OAK_LEAVES] = _apply_biome_tint_leaves(leaves_raw)

    # 7: sand
    textures[TEX_SAND] = _load_and_convert(os.path.join(TEXTURE_DIR, 'sand.png'))

    # 8: snow
    textures[TEX_SNOW] = _load_and_convert(os.path.join(TEXTURE_DIR, 'snow.png'))

    # 9: bedrock
    textures[TEX_BEDROCK] = _load_and_convert(os.path.join(TEXTURE_DIR, 'bedrock.png'))

    # 10: water_still (first frame)
    textures[TEX_WATER_STILL] = _crop_water_frame(os.path.join(TEXTURE_DIR, 'water_still.png'))

    # 11: water_flow (first frame)
    textures[TEX_WATER_FLOW] = _crop_water_frame(os.path.join(TEXTURE_DIR, 'water_flow.png'))

    return textures


# ── Atlas layout ──
# Arrange textures in a grid. ATLAS_COLS x ATLAS_ROWS grid of TEX_SIZE slots.
ATLAS_COLS = 4
ATLAS_ROWS = (TEX_COUNT + ATLAS_COLS - 1) // ATLAS_COLS
ATLAS_SIZE_PX = TEX_SIZE * ATLAS_COLS  # atlas width in pixels
ATLAS_SIZE_PY = TEX_SIZE * ATLAS_ROWS  # atlas height in pixels


def _get_uv(tex_id):
    """Return (u0, v0, u1, v1) for a given texture ID within the atlas (OpenGL UV space).
    UV origin is bottom-left in OpenGL, but we lay out top-to-bottom in PIL
    and flip during upload, so row 0 is at the bottom of the GL texture."""
    col = tex_id % ATLAS_COLS
    row = tex_id // ATLAS_COLS
    u0 = col * TEX_SIZE / ATLAS_SIZE_PX
    v0 = row * TEX_SIZE / ATLAS_SIZE_PY
    u1 = u0 + TEX_SIZE / ATLAS_SIZE_PX
    v1 = v0 + TEX_SIZE / ATLAS_SIZE_PY
    return (u0, v0, u1, v1)


# UV lookup table: tex_id -> (u0, v0, u1, v1)
UV_TABLE = None  # populated after atlas is built


def build_atlas():
    """Build the texture atlas and upload to OpenGL. Returns the GL texture ID."""
    global UV_TABLE

    textures = _load_all_textures()

    # Create atlas image (PIL, row 0 at top)
    atlas = Image.new('RGBA', (ATLAS_SIZE_PX, ATLAS_SIZE_PY), (0, 0, 0, 0))
    for tex_id, tex_img in enumerate(textures):
        if tex_img is None:
            continue
        col = tex_id % ATLAS_COLS
        row = tex_id // ATLAS_COLS
        atlas.paste(tex_img, (col * TEX_SIZE, row * TEX_SIZE))

    # Build UV table
    UV_TABLE = [_get_uv(i) for i in range(TEX_COUNT)]

    # Flip vertically for OpenGL (origin at bottom-left)
    atlas = atlas.transpose(Image.FLIP_TOP_BOTTOM)

    # Convert to bytes
    data = atlas.tobytes('raw', 'RGBA', 0, -1)

    # Upload to GL
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, ATLAS_SIZE_PX, ATLAS_SIZE_PY,
                 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
    glBindTexture(GL_TEXTURE_2D, 0)

    return tex_id


def get_uv(tex_id):
    """Get UV coordinates for a texture ID. Returns (u0, v0, u1, v1)."""
    if UV_TABLE is None:
        raise RuntimeError("Atlas not built yet. Call build_atlas() first.")
    return UV_TABLE[tex_id]


# Export UV constants as a dict for C++ to use (via get_tex_id in subchunk.cpp)
# C++ texId values must match TEX_* constants above.
TEX_ID_CONSTANTS = {
    'TEX_GRASS_TOP':    TEX_GRASS_TOP,
    'TEX_GRASS_SIDE':   TEX_GRASS_SIDE,
    'TEX_DIRT':         TEX_DIRT,
    'TEX_STONE':        TEX_STONE,
    'TEX_OAK_LOG_SIDE': TEX_OAK_LOG_SIDE,
    'TEX_OAK_LOG_TOP':  TEX_OAK_LOG_TOP,
    'TEX_OAK_LEAVES':   TEX_OAK_LEAVES,
    'TEX_SAND':         TEX_SAND,
    'TEX_SNOW':         TEX_SNOW,
    'TEX_BEDROCK':      TEX_BEDROCK,
    'TEX_WATER_STILL':  TEX_WATER_STILL,
    'TEX_WATER_FLOW':   TEX_WATER_FLOW,
}
