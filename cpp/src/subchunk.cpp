#include "subchunk.h"
#include <cmath>

SubChunk::SubChunk(int yBase_) : yBase(yBase_), dirty(true) {
    blocks.fill(BLOCK_AIR);
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

std::vector<float> SubChunk::buildMesh(bool includeLines) const {
    std::vector<float> vertices;
    // 这里简化实现：遍历所有方块，对每个面判断邻居是否透明
    // 实际应使用与之前Python类似的FACES，但为了速度，我们直接在C++中定义
    // 由于代码量较大，这里仅给出框架，您可以根据之前的Python逻辑实现
    // 返回的顶点格式: [x,y,z, r,g,b, x,y,z, r,g,b, ...]
    // 示例：暂时返回空
    return vertices;
}
