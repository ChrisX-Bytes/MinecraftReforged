#pragma once
#include <array>
#include <vector>
#include <cstdint>
#include "block_ids.h"

constexpr int SUBCHUNK_SIZE = 16;
constexpr int SUBCHUNK_VOLUME = SUBCHUNK_SIZE * SUBCHUNK_SIZE * SUBCHUNK_SIZE;

class World;  // 前向声明，避免循环依赖（world.h 已 include chunk.h -> subchunk.h）

class SubChunk {
public:
    SubChunk() : yBase(0), dirty(true), chunkX(0), chunkZ(0) {
        blocks.fill(BLOCK_AIR);
    }

    void init(int yBase_);
    void setChunkPos(int cx, int cz) { chunkX = cx; chunkZ = cz; }
    void setWorld(World* w) { world = w; }

    BlockID getBlock(int lx, int ly, int lz) const;
    void setBlock(int lx, int ly, int lz, BlockID id);

    // 水位（仅对 BLOCK_WATER 方块有意义）：0=水源, 1-7=流水, 8=下落满柱
    uint8_t getWaterLevel(int lx, int ly, int lz) const;
    void setWaterLevel(int lx, int ly, int lz, uint8_t level);

    // 计算流水方块某顶角的顶面高度比例（按邻居水位最小值平滑，MC FluidRenderer 算法）
    float fluidCornerHeight(int wx, int wy, int wz, int ax, int az,
                            BlockID selfId, uint8_t selfLevel) const;

    bool isDirty() const { return dirty; }
    void markDirty() { dirty = true; }
    void clearDirty() { dirty = false; }

    std::vector<float> buildMesh();

    int getYBase() const { return yBase; }

    // 线框顶点数据（每6个float一组：x,y,z,r,g,b）
    // buildMesh() 会同时填充它，供 Python 端上传到 lineVBO
    std::vector<float> lineVertices;

    uint32_t faceVBO = 0;
    uint32_t lineVBO = 0;
    int faceCount = 0;
    int lineCount = 0;

private:
    std::array<BlockID, SUBCHUNK_VOLUME> blocks;
    std::array<uint8_t, SUBCHUNK_VOLUME> waterLevels; // 并行副数据，仅水方块有意义；默认 0（水源）
    int yBase;
    bool dirty;
    int chunkX, chunkZ;   // 所属区块的世界坐标（以区块为单位）
    World* world = nullptr; // 流体渲染需查相邻区块水位，由 World::getChunk 设置
};
