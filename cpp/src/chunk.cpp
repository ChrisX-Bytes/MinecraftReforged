#include "chunk.h"
#include <cmath>

Chunk::Chunk(int cx, int cz) : cx(cx), cz(cz), loadLevel(LOAD_LEVEL_UNLOADED), isGenerated(false) {
    // 初始化所有子区块，每个子区块的 yBase 为 section_index * 16 + WORLD_BOTTOM
    for (int i = 0; i < NUM_SECTIONS; ++i) {
        int yBase = i * 16 + -64; // WORLD_BOTTOM = -64
        // 实际应使用配置，但为简单起见直接计算
        // 注意：subchunks 是 std::array<SubChunk, NUM_SECTIONS>，默认构造
        // 我们只能用 placement new 或重新赋值，但 SubChunk 有默认构造函数
        // 所以这里调用默认构造即可（已自动构造）
        // 如果需要设置 yBase，可以在 SubChunk 构造函数中传入
        // 但 SubChunk 没有默认无参构造，需修改。先假设有默认构造。
        // 更简单：在 SubChunk 中提供一个 setYBase 方法，或直接在构造函数传参
        // 这里我们重新设计：SubChunk 构造函数接受 yBase。
        // 但由于是数组，我们只能使用默认构造，然后调用 init 方法。
        subchunks[i].init(i * 16 + WORLD_BOTTOM);
    }
}

SubChunk* Chunk::getSubChunk(int sectionIdx) {
    if (sectionIdx < 0 || sectionIdx >= NUM_SECTIONS) return nullptr;
    return &subchunks[sectionIdx];
}

BlockID Chunk::getBlock(int wx, int wy, int wz) const {
    int secIdx = getSectionIndex(wy);
    if (secIdx < 0) return BLOCK_AIR;
    int lx = wx - cx * 16;
    int ly = wy - (secIdx * 16 + WORLD_BOTTOM);
    int lz = wz - cz * 16;
    // 确保坐标在子区块范围内
    if (lx < 0 || lx >= 16 || ly < 0 || ly >= 16 || lz < 0 || lz >= 16) return BLOCK_AIR;
    return subchunks[secIdx].getBlock(lx, ly, lz);
}

void Chunk::setBlock(int wx, int wy, int wz, BlockID id) {
    int secIdx = getSectionIndex(wy);
    if (secIdx < 0) return;
    int lx = wx - cx * 16;
    int ly = wy - (secIdx * 16 + WORLD_BOTTOM);
    int lz = wz - cz * 16;
    if (lx < 0 || lx >= 16 || ly < 0 || ly >= 16 || lz < 0 || lz >= 16) return;
    subchunks[secIdx].setBlock(lx, ly, lz, id);
}

void Chunk::rebuildDirtySubChunks() {
    for (auto& sub : subchunks) {
        if (sub.isDirty()) {
            sub.buildMesh(); // 假设 buildMesh 内部更新 VBO 并清除脏标志
        }
    }
}

int Chunk::getSectionIndex(int wy) const {
    int yAbs = wy - WORLD_BOTTOM;
    if (yAbs < 0 || yAbs >= 384) return -1;
    return yAbs / 16;
}
