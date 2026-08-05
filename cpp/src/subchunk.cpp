#include "subchunk.h"
#include "world.h"
#include "block_ids.h"
#include <cmath>
#include <vector>
#include <cstdint>
#include <algorithm>

// 几何常量
static const float CUBE_VERTICES[8][3] = {
    {-0.5f, -0.5f, -0.5f}, { 0.5f, -0.5f, -0.5f},
    { 0.5f,  0.5f, -0.5f}, {-0.5f,  0.5f, -0.5f},
    {-0.5f, -0.5f,  0.5f}, { 0.5f, -0.5f,  0.5f},
    { 0.5f,  0.5f,  0.5f}, {-0.5f,  0.5f,  0.5f}
};
static const int CUBE_EDGES[12][2] = {
    {0,1},{1,2},{2,3},{3,0},
    {4,5},{5,6},{6,7},{7,4},
    {0,4},{1,5},{2,6},{3,7}
};
// 面顺序与方向映射对应：0=y+, 1=y-, 2=x+, 3=x-, 4=z+, 5=z-
// 每个面取该平面上的 4 个顶点，并用逆时针绕序（从面外部看，法线朝外）
static const int FACE_INDICES[6][6] = {
    {2,3,7, 7,6,2}, // 上 (y+)  顶点 2,3,6,7 全部 y=+0.5
    {0,1,5, 5,4,0}, // 下 (y-)  顶点 0,1,4,5 全部 y=-0.5
    {1,2,6, 6,5,1}, // 右 (x+)  顶点 1,2,5,6 全部 x=+0.5
    {0,4,7, 7,3,0}, // 左 (x-)  顶点 0,3,4,7 全部 x=-0.5
    {4,5,6, 6,7,4}, // 前 (z+)  顶点 4,5,6,7 全部 z=+0.5
    {0,3,2, 2,1,0}  // 后 (z-)  顶点 0,1,2,3 全部 z=-0.5
};

// 颜色映射（GL_MODULATE: vertex_color × texture_color）
// 方块纹理已在 atlas 构建时包含最终颜色（含生物群系着色），
// 因此使用白色 (1,1,1) 顶点色以保持纹理原色。
// 水面等半透明方块保留自定义顶点色以调节亮度/透明度。
static void get_color(BlockID id, int face_dir, float &r, float &g, float &b) {
    switch (id) {
        case BLOCK_GRASS_BLOCK:
            // 顶面和侧面纹理已含生物群系着色，用白色
            r = 1.0f; g = 1.0f; b = 1.0f;
            break;
        case BLOCK_DIRT:      r=0.8f;  g=0.6f;  b=0.4f;  break;
        case BLOCK_STONE:     r=0.6f;  g=0.6f;  b=0.6f;  break;
        case BLOCK_WOOD:      r=0.63f; g=0.32f; b=0.18f; break;
        case BLOCK_LEAVES:
            // 纹理已含生物群系着色，用白色
            r = 1.0f; g = 1.0f; b = 1.0f;
            break;
        case BLOCK_SAND:      r=0.93f; g=0.84f; b=0.69f; break;
        case BLOCK_SNOW:      r=0.95f; g=0.95f; b=0.98f; break;
        case BLOCK_BEDROCK:   r=0.5f;  g=0.5f;  b=0.5f;  break;
        case BLOCK_WATER:     r=0.3f;  g=0.5f;  b=0.8f;  break;
        default:              r=1.0f;  g=1.0f;  b=1.0f;  break;
    }
}

// ── 纹理 Atlas 系统 ──
// texId 常量与 texture_atlas.py 完全一致
constexpr int ATLAS_COLS = 4;
constexpr int TEX_SIZE = 16;

enum TexID : int {
    TEX_GRASS_TOP    = 0,
    TEX_GRASS_SIDE   = 1,
    TEX_DIRT         = 2,
    TEX_STONE        = 3,
    TEX_OAK_LOG_SIDE = 4,
    TEX_OAK_LOG_TOP  = 5,
    TEX_OAK_LEAVES   = 6,
    TEX_SAND         = 7,
    TEX_SNOW         = 8,
    TEX_BEDROCK      = 9,
    TEX_WATER_STILL  = 10,
    TEX_WATER_FLOW   = 11,
};

// Atlas 像素尺寸（计算得到，与 Python 一致）
static constexpr int ATLAS_SIZE_PX = TEX_SIZE * ATLAS_COLS; // 64
static constexpr int ATLAS_ROWS = 3; // ceil(12 / 4) = 3
static constexpr int ATLAS_SIZE_PY = TEX_SIZE * ATLAS_ROWS; // 48

// 返回方块+面方向对应的纹理 ID
// face_dir: 0=top(y+), 1=bottom(y-), 2=right(x+), 3=left(x-), 4=front(z+), 5=back(z-)
static int get_tex_id(BlockID id, int face_dir) {
    switch (id) {
        case BLOCK_GRASS_BLOCK:
            return (face_dir == 0) ? TEX_GRASS_TOP : (face_dir == 1) ? TEX_DIRT : TEX_GRASS_SIDE;
        case BLOCK_DIRT:      return TEX_DIRT;
        case BLOCK_STONE:     return TEX_STONE;
        case BLOCK_WOOD:
            return (face_dir <= 1) ? TEX_OAK_LOG_TOP : TEX_OAK_LOG_SIDE;
        case BLOCK_LEAVES:    return TEX_OAK_LEAVES;
        case BLOCK_SAND:      return TEX_SAND;
        case BLOCK_SNOW:      return TEX_SNOW;
        case BLOCK_BEDROCK:   return TEX_BEDROCK;
        case BLOCK_WATER:     return TEX_WATER_STILL;
        default:               return TEX_STONE;
    }
}

// 返回纹理在 atlas 中的 (u0, v0, u1, v1)
static void get_uv_for_tex(int tex_id, float &u0, float &v0, float &u1, float &v1) {
    int col = tex_id % ATLAS_COLS;
    int row = tex_id / ATLAS_COLS;
    u0 = (float)(col * TEX_SIZE) / ATLAS_SIZE_PX;
    v0 = (float)(row * TEX_SIZE) / ATLAS_SIZE_PY;
    u1 = (float)((col + 1) * TEX_SIZE) / ATLAS_SIZE_PX;
    v1 = (float)((row + 1) * TEX_SIZE) / ATLAS_SIZE_PY;
}

// ── 面顶点 UV 映射 ──
// 每个面有 4 个角（由 FACE_INDICES 引用的顶点索引定义）。
// 对于每个面的 6 个三角形顶点，我们需要根据顶点属于 4 个角中的哪一个来分配 UV。
// 下面定义每个面（face 0-5）中，6 个顶点各自对应矩形的哪个角：
//   0=左下(u0,v0)  1=右下(u1,v0)  2=右上(u1,v1)  3=左上(u0,v1)
// 根据 FACE_INDICES 的顶点布局（已在 CUBE_VERTICES 中按空间坐标确定），
// 每个面需要从外部观察时按 CCW 绕序正确分配 UV。
// UV corner: 0=BL, 1=BR, 2=TR, 3=TL
// 关键：UV 角必须逐顶点跟随 FACE_INDICES，且 4 个角顶点映射到 4 个不同 UV，
// 否则两个对角顶点共 UV 会导致三角形纹理扭曲（侧面"重叠"伪影）。
static const int FACE_UV_CORNER[6][6] = {
    {1,0,3, 3,2,1}, // 上 (y+): looking down from above
    {0,1,2, 2,3,0}, // 下 (y-): looking up from below
    {0,3,2, 2,1,0}, // 右 (x+): looking from +x
    {1,0,3, 3,2,1}, // 左 (x-): looking from -x
    {1,0,3, 3,2,1}, // 前 (z+): looking from +z
    {0,3,2, 2,1,0}, // 后 (z-): looking from -z  (修正：第二三角形 2,3,0 -> 2,1,0)
};

// 流体顶面高度比例(0..8/9)：MC 实际值——源/下落=8/9, 流水 level k=(8-k)/9, 非水=0。
// 非水返回 0 表示"无水"，使流水顶点向无水邻居倾斜（形成瀑布唇/边缘下降）。
static float fluidHeight(BlockID id, uint8_t level) {
    if (id != BLOCK_WATER) return 0.0f;
    if (level == 0 || level == 8) return 8.0f / 9.0f;
    return (8.0f - float(level)) / 9.0f;
}

// 计算流水方块某顶角的顶面高度比例（MC FluidRenderer 算法）。
// ax, az 为 ±1 表示该角在 +x/+z 侧。该角由最多 4 个方块共享：
//   自身、+x 邻居、+z 邻居、对角(+x,+z) 邻居。
// 取这 4 个方块水面高度的最小值，使水面对齐到最低邻居，形成平滑过渡。
// 空气/非水邻居高度为 0，会让角降到 0（瀑布唇/边缘下降）。
float SubChunk::fluidCornerHeight(int wx, int wy, int wz, int ax, int az,
                                  BlockID selfId, uint8_t selfLevel) const {
    float hSelf = fluidHeight(selfId, selfLevel);
    if (!world) return hSelf;
    int nx = wx + ax;
    int nz = wz + az;
    BlockID idX = world->getBlock(nx, wy, wz);
    float hX = fluidHeight(idX, world->getWaterLevel(nx, wy, wz));
    BlockID idZ = world->getBlock(wx, wy, nz);
    float hZ = fluidHeight(idZ, world->getWaterLevel(wx, wy, nz));
    BlockID idD = world->getBlock(nx, wy, nz);  // 对角邻居
    float hD = fluidHeight(idD, world->getWaterLevel(nx, wy, nz));
    return std::min({hSelf, hX, hZ, hD});  // 4 方块最小值
}

void SubChunk::init(int yBase_) {
    yBase = yBase_;
    dirty = true;
    blocks.fill(BLOCK_AIR);
    waterLevels.fill(0); // 默认水源水位，兼容现有海面
    faceCount = 0;
    lineCount = 0;
}

BlockID SubChunk::getBlock(int lx, int ly, int lz) const {
    if (lx < 0 || lx >= SUBCHUNK_SIZE || ly < 0 || ly >= SUBCHUNK_SIZE || lz < 0 || lz >= SUBCHUNK_SIZE)
        return BLOCK_AIR;
    int index = (ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx;
    return blocks[index];
}

void SubChunk::setBlock(int lx, int ly, int lz, BlockID id) {
    if (lx < 0 || lx >= SUBCHUNK_SIZE || ly < 0 || ly >= SUBCHUNK_SIZE || lz < 0 || lz >= SUBCHUNK_SIZE)
        return;
    int index = (ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx;
    blocks[index] = id;
    dirty = true;
}

uint8_t SubChunk::getWaterLevel(int lx, int ly, int lz) const {
    if (lx < 0 || lx >= SUBCHUNK_SIZE || ly < 0 || ly >= SUBCHUNK_SIZE || lz < 0 || lz >= SUBCHUNK_SIZE)
        return 0;
    int index = (ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx;
    return waterLevels[index];
}

void SubChunk::setWaterLevel(int lx, int ly, int lz, uint8_t level) {
    if (lx < 0 || lx >= SUBCHUNK_SIZE || ly < 0 || ly >= SUBCHUNK_SIZE || lz < 0 || lz >= SUBCHUNK_SIZE)
        return;
    int index = (ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx;
    waterLevels[index] = level;
    dirty = true;
}

std::vector<float> SubChunk::buildMesh() {
    if (!dirty) {
        return std::vector<float>();
    }

    std::vector<float> face_vertices;
    lineVertices.clear(); // 逐方块线框已移除：MC 原版只在准星瞄准的方块上画线框（见 main.py）

    for (int ly = 0; ly < SUBCHUNK_SIZE; ++ly) {
        for (int lz = 0; lz < SUBCHUNK_SIZE; ++lz) {
            for (int lx = 0; lx < SUBCHUNK_SIZE; ++lx) {
                BlockID id = blocks[(ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx];
                if (id == BLOCK_AIR) continue;

                // 计算世界坐标（使用 chunkX, chunkZ）
                int wx = chunkX * 16 + lx;
                int wz = chunkZ * 16 + lz;
                int wy = ly + yBase;

                // 水位：水方块的流水(level 1-7)顶面需降低；水源(0)/下落(8)满方块。
                // 关键：流水顶面每个顶点按该角相邻方块水位取最小（MC FluidRenderer 算法），
                // 形成平滑斜面，而非逐方块硬台阶。
                bool isWater = (id == BLOCK_WATER);
                uint8_t wl = isWater ? waterLevels[(ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx] : 0;
                bool isFlowing = isWater && (wl >= 1 && wl <= 7);
                float selfTopY = 0.5f;
                if (isFlowing) selfTopY = (fluidHeight(id, wl) - 0.5f); // 中心坐标 y

                // 遍历 6 个面，判断邻居是否为透明（air/water），决定面是否可见
                for (int face = 0; face < 6; ++face) {
                    int dx = (face == 2) ? 1 : (face == 3) ? -1 : 0;
                    int dy = (face == 0) ? 1 : (face == 1) ? -1 : 0;
                    int dz = (face == 4) ? 1 : (face == 5) ? -1 : 0;
                    int nx = lx + dx;
                    int ny = ly + dy;
                    int nz = lz + dz;

                    // 取邻居方块与水位：子区块内部用本地数组（快），
                    // 跨边界用 world->getBlock() 查询（避免共面渲染 → z-fighting）。
                    BlockID neighbor = BLOCK_AIR;
                    uint8_t nWl = 0;
                    bool inBounds = (nx >= 0 && nx < SUBCHUNK_SIZE &&
                                     ny >= 0 && ny < SUBCHUNK_SIZE &&
                                     nz >= 0 && nz < SUBCHUNK_SIZE);
                    if (inBounds) {
                        int nIdx = (ny * SUBCHUNK_SIZE + nz) * SUBCHUNK_SIZE + nx;
                        neighbor = blocks[nIdx];
                        nWl = waterLevels[nIdx];
                    } else if (world) {
                        // 跨子区块/区块边界：查世界
                        neighbor = world->getBlock(wx + dx, wy + dy, wz + dz);
                        if (neighbor == BLOCK_WATER) {
                            nWl = world->getWaterLevel(wx + dx, wy + dy, wz + dz);
                        }
                    }

                    bool neighbor_solid = false;
                    if (neighbor != BLOCK_AIR && neighbor != BLOCK_WATER) {
                        // 固体遮挡
                        neighbor_solid = true;
                    } else if (neighbor == BLOCK_WATER && id == BLOCK_WATER) {
                        // 水-水相邻：仅当水位完全相同时剔除；水位不同则保留面
                        // （高水位朝低水位那面会露出台阶/瀑布侧面，避免透视缺口）
                        uint8_t myWl = wl;
                        if (myWl == nWl) neighbor_solid = true;
                    }

                    if (!neighbor_solid) {
                        float r, g, b;
                        get_color(id, face, r, g, b);
                        int texId = get_tex_id(id, face);
                        float tu0, tv0, tu1, tv1;
                        get_uv_for_tex(texId, tu0, tv0, tu1, tv1);

                        for (int vi = 0; vi < 6; ++vi) {
                            int vert_idx = FACE_INDICES[face][vi];
                            float vx = CUBE_VERTICES[vert_idx][0] + wx;
                            float vy = CUBE_VERTICES[vert_idx][1];
                            float vz = CUBE_VERTICES[vert_idx][2] + wz;
                            // 流水(level 1-7)的顶面/侧面上边顶点降至该方块水位高度。
                            // 顶面保持**水平**（4 角同高 = 自身水位），从上方看呈方块状菱形（MC 俯视图）。
                            // 不向邻居倾斜——倾斜会让菱形边缘呈锯齿状三角形。
                            if (isFlowing && vy > 0.499f) {
                                vy = selfTopY;  // 自身水位高度（水平顶面）
                            }
                            vy += wy;
                            face_vertices.push_back(vx);
                            face_vertices.push_back(vy);
                            face_vertices.push_back(vz);
                            // UV 坐标
                            int corner = FACE_UV_CORNER[face][vi];
                            switch (corner) {
                                case 0: face_vertices.push_back(tu0); face_vertices.push_back(tv1); break; // BL
                                case 1: face_vertices.push_back(tu1); face_vertices.push_back(tv1); break; // BR
                                case 2: face_vertices.push_back(tu1); face_vertices.push_back(tv0); break; // TR
                                case 3: face_vertices.push_back(tu0); face_vertices.push_back(tv0); break; // TL
                            }
                            face_vertices.push_back(r);
                            face_vertices.push_back(g);
                            face_vertices.push_back(b);
                        }
                    }
                }
            }
        }
    }

    faceCount = (int)face_vertices.size() / 8; // 每顶点 8 float: x,y,z,u,v,r,g,b
    lineCount = (int)lineVertices.size() / 6; // 每条线段 = 2 个顶点（线框保持旧格式）
    dirty = false;
    return face_vertices;
}
