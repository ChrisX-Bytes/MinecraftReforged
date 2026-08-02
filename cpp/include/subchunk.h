#pragma once
#include <array>
#include <vector>
#include <cstdint>
#include "block_ids.h"

constexpr int SUBCHUNK_SIZE = 16;
constexpr int SUBCHUNK_VOLUME = SUBCHUNK_SIZE * SUBCHUNK_SIZE * SUBCHUNK_SIZE;

class SubChunk {
public:
    SubChunk(int yBase);

    BlockID getBlock(int lx, int ly, int lz) const;
    void setBlock(int lx, int ly, int lz, BlockID id);

    bool isDirty() const { return dirty; }
    void markDirty() { dirty = true; }
    void clearDirty() { dirty = false; }

    // 生成网格数据：返回顶点数组（每个顶点6个float: x,y,z,r,g,b）
    std::vector<float> buildMesh(bool includeLines = false) const;

    // 获取位置
    int getYBase() const { return yBase; }

    // VBO句柄（由Python管理，C++只存储数值）
    uint32_t faceVBO = 0;
    uint32_t lineVBO = 0;
    int faceCount = 0;
    int lineCount = 0;

private:
    std::array<BlockID, SUBCHUNK_VOLUME> blocks;
    int yBase;
    bool dirty;
};
