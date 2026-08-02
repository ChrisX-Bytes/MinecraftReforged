#pragma once
#include <array>
#include <vector>
#include <cstdint>
#include "block_ids.h"

constexpr int SUBCHUNK_SIZE = 16;
constexpr int SUBCHUNK_VOLUME = SUBCHUNK_SIZE * SUBCHUNK_SIZE * SUBCHUNK_SIZE;

class SubChunk {
public:
    SubChunk() : yBase(0), dirty(true), chunkX(0), chunkZ(0) {
        blocks.fill(BLOCK_AIR);
    }

    void init(int yBase_);
    void setChunkPos(int cx, int cz) { chunkX = cx; chunkZ = cz; }

    BlockID getBlock(int lx, int ly, int lz) const;
    void setBlock(int lx, int ly, int lz, BlockID id);

    bool isDirty() const { return dirty; }
    void markDirty() { dirty = true; }
    void clearDirty() { dirty = false; }

    std::vector<float> buildMesh();

    int getYBase() const { return yBase; }

    uint32_t faceVBO = 0;
    uint32_t lineVBO = 0;
    int faceCount = 0;
    int lineCount = 0;

private:
    std::array<BlockID, SUBCHUNK_VOLUME> blocks;
    int yBase;
    bool dirty;
    int chunkX, chunkZ;   // 新增：所属区块的世界坐标（以区块为单位）
};
