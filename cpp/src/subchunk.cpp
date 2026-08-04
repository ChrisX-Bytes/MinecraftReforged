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

// 颜色映射
static void get_color(BlockID id, int face_dir, float &r, float &g, float &b) {
    switch (id) {
        case BLOCK_GRASS_BLOCK:
            if (face_dir == 0) { r=0.2f; g=0.7f; b=0.2f; }
            else { r=0.55f; g=0.27f; b=0.07f; }
            break;
        case BLOCK_DIRT:      r=0.55f; g=0.27f; b=0.07f; break;
        case BLOCK_STONE:     r=0.6f;  g=0.6f;  b=0.6f;  break;
        case BLOCK_WOOD:      r=0.63f; g=0.32f; b=0.18f; break;
        case BLOCK_LEAVES:    r=0.0f;  g=0.6f;  b=0.0f;  break;
        case BLOCK_SAND:      r=0.93f; g=0.84f; b=0.69f; break;
        case BLOCK_SNOW:      r=0.95f; g=0.95f; b=0.98f; break;
        case BLOCK_BEDROCK:   r=0.3f;  g=0.3f;  b=0.3f;  break;
        case BLOCK_WATER:     r=0.1f;  g=0.3f;  b=0.7f;  break;
        default:              r=0.5f;  g=0.5f;  b=0.5f;  break;
    }
}

// 流体顶面高度比例(0..8/9)：MC 实际值——源/下落=8/9, 流水 level k=(8-k)/9, 非水=0。
// 非水返回 0 表示"无水"，使流水顶点向无水邻居倾斜（形成瀑布唇/边缘下降）。
static float fluidHeight(BlockID id, uint8_t level) {
    if (id != BLOCK_WATER) return 0.0f;
    if (level == 0 || level == 8) return 8.0f / 9.0f;
    return (8.0f - float(level)) / 9.0f;
}

// 计算流水方块某顶角的顶面高度比例（MC FluidRenderer 算法）。
// ax, az 为 ±1 表示该角在 +x/+z 侧。取 自身+两方向邻居 的最小高度，**不做 clamp**：
// 这样空气邻居(高度0)会让角降到 0，水面向空气倾斜（瀑布唇），符合 MC 行为。
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
    return std::min({hSelf, hX, hZ});  // 纯 min，不 clamp
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

                    bool neighbor_solid = false;
                    // 仅检查子区块内部邻居（跨区块边界一律视为可见，避免接缝处露空）
                    if (nx >= 0 && nx < SUBCHUNK_SIZE && ny >= 0 && ny < SUBCHUNK_SIZE && nz >= 0 && nz < SUBCHUNK_SIZE) {
                        int nIdx = (ny * SUBCHUNK_SIZE + nz) * SUBCHUNK_SIZE + nx;
                        BlockID neighbor = blocks[nIdx];
                        if (neighbor != BLOCK_AIR && neighbor != BLOCK_WATER) {
                            // 固体遮挡
                            neighbor_solid = true;
                        } else if (neighbor == BLOCK_WATER && id == BLOCK_WATER) {
                            // 水-水相邻：仅当水位完全相同时剔除；水位不同则保留面
                            // （高水位朝低水位那面会露出台阶/瀑布侧面，避免透视缺口）
                            uint8_t myWl = waterLevels[(ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx];
                            uint8_t nWl = waterLevels[nIdx];
                            if (myWl == nWl) neighbor_solid = true;
                        }
                    }

                    if (!neighbor_solid) {
                        float r, g, b;
                        get_color(id, face, r, g, b);

                        for (int vi = 0; vi < 6; ++vi) {
                            int vert_idx = FACE_INDICES[face][vi];
                            float vx = CUBE_VERTICES[vert_idx][0] + wx;
                            float vy = CUBE_VERTICES[vert_idx][1];
                            float vz = CUBE_VERTICES[vert_idx][2] + wz;
                            // 流水：上方顶点(y==+0.5)按该角邻居水位取最小，形成平滑斜面。
                            // 顶面+侧面上边顶点同步，消除硬台阶（MC 正确几何）。
                            if (isFlowing && vy > 0.499f) {
                                // 由顶点的 x/z 符号确定查哪两个邻居
                                int ax = (CUBE_VERTICES[vert_idx][0] > 0.0f) ? 1 : -1;
                                int az = (CUBE_VERTICES[vert_idx][2] > 0.0f) ? 1 : -1;
                                float h = fluidCornerHeight(wx, wy, wz, ax, az, id, wl);
                                vy = h - 0.5f;
                            }
                            vy += wy;
                            face_vertices.push_back(vx);
                            face_vertices.push_back(vy);
                            face_vertices.push_back(vz);
                            face_vertices.push_back(r);
                            face_vertices.push_back(g);
                            face_vertices.push_back(b);
                        }
                    }
                }
            }
        }
    }

    faceCount = (int)face_vertices.size() / 6;
    lineCount = (int)lineVertices.size() / 6; // 每条线段 = 2 个顶点
    dirty = false;
    return face_vertices;
}
