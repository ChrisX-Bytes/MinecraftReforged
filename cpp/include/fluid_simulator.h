#pragma once
#include <unordered_map>
#include <unordered_set>
#include <array>
#include <vector>
#include <utility>
#include <cstdint>
#include "world.h"

// MC Java 水流规则：
//   level 0   = 水源（满方块，下方需固体/水源支撑）
//   level 1-7 = 流水（每远一格 +1，平地最远 7 格）
//   level 8   = 下落（垂直下落的满柱）
// 水源形成：水方块若水平方向有 >=2 个水源邻居 且 下方为固体/水源 -> 变水源。
// 刻速：水每 5 游戏刻扩散一格。

class FluidSimulator {
public:
    // 注入 World 指针，使流体模拟可跨区块读写方块/水位
    FluidSimulator(World* world = nullptr, int updatesPerTick = 40);

    // 重建 World 后更新指针，避免悬空（reset_world 会销毁旧 World 实例）
    void setWorld(World* w);

    void tick(); // 每游戏刻调用，推进计划刻并处理至多 updatesPerTick 个方块

    // 返回本次 tick 期间被流体改动过的区块坐标列表 [(cx,cz),...]，并清空内部集合。
    // Python 端据此把对应区块加入 rebuild_queue，确保流体改动可见。
    std::vector<std::pair<int,int>> popDirtyChunks();

    // 方块变化时激活该位置（5 刻后处理），触发流动
    void activate(uint64_t pos);

    // 设置水源（初始生成用，不调度）
    void setSource(uint64_t pos, uint8_t level = 0);

private:
    World* world;

    // 计划刻桶（512 个桶循环，每桶代表一个游戏刻）
    std::array<std::unordered_set<uint64_t>, 512> buckets;
    int currentBucket = 0;

    int updatesPerTick;

    // 本次 tick 期间被流体改动过的区块集合，key = (uint32(cx)<<32)|uint32(cz)
    std::unordered_set<uint64_t> dirtyChunks;
    void markChunkDirty(int wx, int wz);

    // pos 编码：wx(24) | wy(16) | wz(24)，共 64 位
    static void decode(uint64_t pos, int& wx, int& wy, int& wz);
    static uint64_t encode(int wx, int wy, int wz);

    void schedule(uint64_t pos, int delay);         // delay 单位：游戏刻
    void processSource(uint64_t pos);               // 核心流动逻辑

    // 辅助
    bool isSolidOrWater(BlockID id) const;          // 是否阻挡水流（固体）
    bool canFlowInto(BlockID id) const;             // 水能否流入（空气或水）
};
