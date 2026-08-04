#include "chunk.h"
#include <cmath>

Chunk::Chunk(int cx, int cz) : cx(cx), cz(cz), loadLevel(45), isGenerated(false) {
    for (int i = 0; i < NUM_SECTIONS; ++i) {
        subchunks[i].init(i * 16 + WORLD_BOTTOM);
        subchunks[i].setChunkPos(cx, cz);   // 关键：告诉子区块它属于哪个区块
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

uint8_t Chunk::getWaterLevel(int wx, int wy, int wz) const {
    int secIdx = getSectionIndex(wy);
    if (secIdx < 0) return 0;
    int lx = wx - cx * 16;
    int ly = wy - (secIdx * 16 + WORLD_BOTTOM);
    int lz = wz - cz * 16;
    if (lx < 0 || lx >= 16 || ly < 0 || ly >= 16 || lz < 0 || lz >= 16) return 0;
    return subchunks[secIdx].getWaterLevel(lx, ly, lz);
}

void Chunk::setWaterLevel(int wx, int wy, int wz, uint8_t level) {
    int secIdx = getSectionIndex(wy);
    if (secIdx < 0) return;
    int lx = wx - cx * 16;
    int ly = wy - (secIdx * 16 + WORLD_BOTTOM);
    int lz = wz - cz * 16;
    if (lx < 0 || lx >= 16 || ly < 0 || ly >= 16 || lz < 0 || lz >= 16) return;
    subchunks[secIdx].setWaterLevel(lx, ly, lz, level);
}

void Chunk::rebuildDirtySubChunks() {
    // Python 端会自己调用 buildMesh，这里留空
}

int Chunk::getSectionIndex(int wy) const {
    int yAbs = wy - WORLD_BOTTOM;
    if (yAbs < 0 || yAbs >= 384) return -1;
    return yAbs / 16;
}
