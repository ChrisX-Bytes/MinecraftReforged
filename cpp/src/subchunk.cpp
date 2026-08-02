#include "subchunk.h"
#include "block_ids.h"
#include <cmath>
#include <vector>
#include <cstdint>

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
static const int FACE_INDICES[6][6] = {
    {0,1,2, 2,3,0}, // 上 (y+)
    {4,5,6, 6,7,4}, // 下 (y-)
    {1,5,6, 6,2,1}, // 右 (x+)
    {0,4,7, 7,3,0}, // 左 (x-)
    {0,1,5, 5,4,0}, // 前 (z+)
    {2,6,7, 7,3,2}  // 后 (z-)
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

void SubChunk::init(int yBase_) {
    yBase = yBase_;
    dirty = true;
    blocks.fill(BLOCK_AIR);
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

std::vector<float> SubChunk::buildMesh() {
    if (!dirty) {
        return std::vector<float>();
    }

    std::vector<float> face_vertices;

    for (int ly = 0; ly < SUBCHUNK_SIZE; ++ly) {
        for (int lz = 0; lz < SUBCHUNK_SIZE; ++lz) {
            for (int lx = 0; lx < SUBCHUNK_SIZE; ++lx) {
                BlockID id = blocks[(ly * SUBCHUNK_SIZE + lz) * SUBCHUNK_SIZE + lx];
                if (id == BLOCK_AIR) continue;

                // 关键修复：使用 chunkX, chunkZ 计算世界坐标
                int wx = chunkX * 16 + lx;
                int wz = chunkZ * 16 + lz;
                int wy = ly + yBase;
                bool exposed = false;

                for (int face = 0; face < 6; ++face) {
                    int dx = (face == 2) ? 1 : (face == 3) ? -1 : 0;
                    int dy = (face == 0) ? 1 : (face == 1) ? -1 : 0;
                    int dz = (face == 4) ? 1 : (face == 5) ? -1 : 0;
                    int nx = lx + dx;
                    int ny = ly + dy;
                    int nz = lz + dz;
                    bool neighbor_solid = false;
                    if (nx >= 0 && nx < SUBCHUNK_SIZE && ny >= 0 && ny < SUBCHUNK_SIZE && nz >= 0 && nz < SUBCHUNK_SIZE) {
                        BlockID neighbor = blocks[(ny * SUBCHUNK_SIZE + nz) * SUBCHUNK_SIZE + nx];
                        if (neighbor != BLOCK_AIR && neighbor != BLOCK_WATER) {
                            neighbor_solid = true;
                        }
                    }
                    if (!neighbor_solid) {
                        exposed = true;
                        float r, g, b;
                        get_color(id, face, r, g, b);
                        for (int vi = 0; vi < 6; ++vi) {
                            int vert_idx = FACE_INDICES[face][vi];
                            float vx = CUBE_VERTICES[vert_idx][0] + wx;
                            float vy = CUBE_VERTICES[vert_idx][1] + wy;
                            float vz = CUBE_VERTICES[vert_idx][2] + wz;
                            face_vertices.push_back(vx);
                            face_vertices.push_back(vy);
                            face_vertices.push_back(vz);
                            face_vertices.push_back(r);
                            face_vertices.push_back(g);
                            face_vertices.push_back(b);
                        }
                    }
                }
                // 线框暂不生成
            }
        }
    }

    faceCount = (int)face_vertices.size() / 6;
    lineCount = 0;

    dirty = false;
    return face_vertices;
}
