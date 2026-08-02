#pragma once
#include <array>
#include <vector>
#include <cstdint>
#include "block_ids.h"

constexpr int SUBCHUNK_SIZE = 16;
constexpr int SUBCHUNK_VOLUME = SUBCHUNK_SIZE * SUBCHUNK_SIZE * SUBCHUNK_SIZE;

class SubChunk {
public:
    SubChunk() : yBase(0), dirty(true) {
        blocks.fill(BLOCK_AIR);
    }

    // 新增：初始化方法，用于设置 yBase
    void init(int yBase_);

    BlockID getBlock(int lx, int ly, int lz) const;
    void setBlock(int lx, int ly, int lz, BlockID id);

    bool isDirty() const { return dirty; }
    void markDirty() { dirty = true; }
    void clearDirty() { dirty = false; }

    // 生成网格数据：返回顶点数组，同时上传到 VBO（这里返回空，实际应实现）
    std::vector<float> buildMesh();

    int getYBase() const { return yBase; }

    // VBO 句柄（由 Python 管理，C++ 只存储数值）
    uint32_t faceVBO = 0;
    uint32_t lineVBO = 0;
    int faceCount = 0;
    int lineCount = 0;

private:
    std::array<BlockID, SUBCHUNK_VOLUME> blocks;
    int yBase;
    bool dirty;
};
