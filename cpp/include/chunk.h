#pragma once
#include <array>
#include <unordered_map>
#include <unordered_set>
#include "subchunk.h"
#include "block_ids.h"


class Chunk {
public:
    Chunk(int cx, int cz);

    BlockID getBlock(int wx, int wy, int wz) const;
    void setBlock(int wx, int wy, int wz, BlockID id);

    uint8_t getWaterLevel(int wx, int wy, int wz) const;
    void setWaterLevel(int wx, int wy, int wz, uint8_t level);

    SubChunk* getSubChunk(int sectionIdx);
    void rebuildDirtySubChunks();

    // 流体数据
    std::unordered_map<uint64_t, uint8_t> fluidLevels;   // key: (wx,wy,wz) 压缩
    std::unordered_set<uint64_t> pendingFluids;

    bool isGenerated = false;
    int loadLevel = 45; // LOAD_LEVEL_UNLOADED

private:
    int cx, cz;
    std::array<SubChunk, NUM_SECTIONS> subchunks;

    // 辅助函数：将世界坐标转为子区块索引和本地坐标
    int getSectionIndex(int wy) const;
    void getLocalCoords(int wx, int wy, int wz, int &lx, int &ly, int &lz, int &secIdx) const;
};
