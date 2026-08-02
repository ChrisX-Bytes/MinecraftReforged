#include "subchunk.h"
#include <cmath>

void SubChunk::init(int yBase_) {
    yBase = yBase_;
    dirty = true;
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

std::vector<float> SubChunk::buildMesh() {
    // 暂时只清除脏标记，返回空向量
    // 实际应遍历 blocks，生成顶点数据并上传到 VBO
    dirty = false;
    // 这里可以设置 faceCount 和 lineCount 为 0，防止绘制
    faceCount = 0;
    lineCount = 0;
    return std::vector<float>();
}
