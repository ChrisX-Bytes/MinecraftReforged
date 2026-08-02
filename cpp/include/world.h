#pragma once
#include <unordered_map>
#include "chunk.h"

class World {
public:
    Chunk* getChunk(int cx, int cz);
    BlockID getBlock(int wx, int wy, int wz);
    void setBlock(int wx, int wy, int wz, BlockID id);

private:
    std::unordered_map<uint64_t, Chunk> chunks; // key: (cx,cz) Ñ¹Ëõ
};
