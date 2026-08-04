#include "world.h"

Chunk* World::getChunk(int cx, int cz) {
    uint64_t key = (uint64_t(cx) << 32) | uint32_t(cz);
    auto it = chunks.find(key);
    if (it != chunks.end()) {
        return &it->second;
    }
    // 创建新区块
    auto result = chunks.emplace(key, Chunk(cx, cz));
    return &result.first->second;
}

BlockID World::getBlock(int wx, int wy, int wz) {
    int cx = wx >> 4;
    int cz = wz >> 4;
    Chunk* chunk = getChunk(cx, cz);
    return chunk->getBlock(wx, wy, wz);
}

void World::setBlock(int wx, int wy, int wz, BlockID id) {
    int cx = wx >> 4;
    int cz = wz >> 4;
    Chunk* chunk = getChunk(cx, cz);
    chunk->setBlock(wx, wy, wz, id);
}

uint8_t World::getWaterLevel(int wx, int wy, int wz) {
    int cx = wx >> 4;
    int cz = wz >> 4;
    Chunk* chunk = getChunk(cx, cz);
    return chunk->getWaterLevel(wx, wy, wz);
}

void World::setWaterLevel(int wx, int wy, int wz, uint8_t level) {
    int cx = wx >> 4;
    int cz = wz >> 4;
    Chunk* chunk = getChunk(cx, cz);
    chunk->setWaterLevel(wx, wy, wz, level);
}
