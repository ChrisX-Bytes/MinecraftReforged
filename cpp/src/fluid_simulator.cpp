#include "fluid_simulator.h"
#include "chunk.h"
#include <iostream>

FluidSimulator::FluidSimulator(int updatesPerTick) : updatesPerTick(updatesPerTick), currentBucket(0) {
    // 初始化桶
    for (int i = 0; i < 512; ++i) buckets[i].clear();
}

void FluidSimulator::tick() {
    auto& bucket = buckets[currentBucket];
    // 复制一份待处理集合，因为处理过程中可能修改桶
    auto items = bucket;
    bucket.clear();

    int processed = 0;
    for (uint64_t pos : items) {
        if (processed >= updatesPerTick) break;
        // 检查该位置是否仍是水且状态为 flowing
        int wx = pos >> 40;
        int wy = (pos >> 20) & 0xFFFFF;
        int wz = pos & 0xFFFFF;
        // 从全局 world 获取区块，检查方块ID
        // 这里需要访问全局 World 实例，但我们暂时跳过，只是简单模拟。
        // 实际中需要通过 World 单例或全局变量获取。
        // 为编译通过，我们只打印一条消息。
        // 用户可以之后填充真实逻辑。
        processSource(pos);
        processed++;
    }
    currentBucket = (currentBucket + 1) % 512;
}

void FluidSimulator::activate(uint64_t pos) {
    // 将状态设为 flowing，并调度到5刻后
    fluidStates[pos] = 1; // flowing
    schedule(pos, 5);
}

void FluidSimulator::setSource(uint64_t pos, uint8_t level) {
    // 设置为静止水
    fluidStates[pos] = 0; // still
    // 不调度
}

void FluidSimulator::schedule(uint64_t pos, int delay) {
    int bucketIndex = (currentBucket + delay) % 512;
    buckets[bucketIndex].insert(pos);
}

void FluidSimulator::processSource(uint64_t pos) {
    // 这里实现流动逻辑：检查邻居，计算水位，扩散等
    // 暂时为空，仅作演示。
    // 用户可参照原 Python 实现移植到 C++。
}
