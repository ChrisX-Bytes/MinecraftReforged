#pragma once
#include <unordered_map>
#include <unordered_set>
#include <array>
#include <cstdint>

class FluidSimulator {
public:
    FluidSimulator(int updatesPerTick = 40);

    void tick(); // 每帧调用，推进计划刻

    // 激活一个位置（方块变化时调用）
    void activate(uint64_t pos);

    // 设置水源（初始生成）
    void setSource(uint64_t pos, uint8_t level = 0);

private:
    // 计划刻桶（每5刻一个桶，共512个桶循环）
    std::array<std::unordered_set<uint64_t>, 512> buckets;
    int currentBucket = 0;

    int updatesPerTick;

    // 流体状态：'still' 或 'flowing'，用uint8_t表示0=still, 1=flowing
    std::unordered_map<uint64_t, uint8_t> fluidStates;

    // 内部方法
    void schedule(uint64_t pos, int delay);
    void processSource(uint64_t pos);
    void spread(uint64_t pos, int level);
    void applyUpdate(uint64_t pos, uint8_t newLevel, uint8_t state);
};
