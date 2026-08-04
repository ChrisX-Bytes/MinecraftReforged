#include "fluid_simulator.h"
#include "chunk.h"
#include "block_ids.h"

FluidSimulator::FluidSimulator(World* world, int updatesPerTick)
    : world(world), updatesPerTick(updatesPerTick), currentBucket(0) {
    for (int i = 0; i < 512; ++i) buckets[i].clear();
}

void FluidSimulator::setWorld(World* w) {
    world = w;
    // 旧 World 已销毁，其上的待处理方块位置对新 World 无意义，清空调度桶与脏区块
    for (int i = 0; i < 512; ++i) buckets[i].clear();
    dirtyChunks.clear();
}

void FluidSimulator::markChunkDirty(int wx, int wz) {
    int cx = wx >> 4;
    int cz = wz >> 4;
    dirtyChunks.insert((uint64_t(uint32_t(cx)) << 32) | uint32_t(cz));
}

std::vector<std::pair<int,int>> FluidSimulator::popDirtyChunks() {
    std::vector<std::pair<int,int>> result;
    result.reserve(dirtyChunks.size());
    for (uint64_t key : dirtyChunks) {
        int cx = int(uint32_t(key >> 32));
        int cz = int(uint32_t(key & 0xFFFFFFFFu));
        result.push_back({cx, cz});
    }
    dirtyChunks.clear();
    return result;
}

uint64_t FluidSimulator::encode(int wx, int wy, int wz) {
    // 位布局：wx(24位) | wy(16位) | wz(24位)，总 64 位，绝不超 uint64。
    // 各段用无符号截断后左移，避免高位污染。
    const uint64_t WX_MASK = (uint64_t(1) << 24) - 1; // 0xFFFFFF
    const uint64_t WY_MASK = (uint64_t(1) << 16) - 1; // 0xFFFF
    uint64_t ux = uint32_t(wx) & WX_MASK;
    uint64_t uy = uint32_t(wy) & WY_MASK;
    uint64_t uz = uint32_t(wz) & WX_MASK;
    return (ux << 40) | (uy << 24) | uz;
}

void FluidSimulator::decode(uint64_t pos, int& wx, int& wy, int& wz) {
    // 与 encode 对应的逆向，用符号扩展还原负数坐标
    auto sext24 = [](uint32_t v) -> int {
        return int(v) << 8 >> 8; // 取低24位后符号扩展
    };
    auto sext16 = [](uint32_t v) -> int {
        return int(v) << 16 >> 16;
    };
    wx = sext24(uint32_t((pos >> 40) & 0xFFFFFF));
    wy = sext16(uint32_t((pos >> 24) & 0xFFFF));
    wz = sext24(uint32_t(pos & 0xFFFFFF));
}

void FluidSimulator::schedule(uint64_t pos, int delay) {
    if (delay < 1) delay = 1;
    int bucketIndex = (currentBucket + delay) % 512;
    buckets[bucketIndex].insert(pos);
}

void FluidSimulator::activate(uint64_t pos) {
    schedule(pos, 5); // MC：水每 5 刻更新一次
}

void FluidSimulator::setSource(uint64_t pos, uint8_t level) {
    // 仅记录，不调度（生成阶段水源本就稳定）
    (void)pos; (void)level;
}

bool FluidSimulator::isSolidOrWater(BlockID id) const {
    // 阻挡水流（视为支撑/容器壁）
    return id != BLOCK_AIR;
}

bool FluidSimulator::canFlowInto(BlockID id) const {
    // 水能流入空气；已是水则按水位判断更新
    return id == BLOCK_AIR || id == BLOCK_WATER;
}

void FluidSimulator::tick() {
    auto& bucket = buckets[currentBucket];
    auto items = bucket; // 拷贝，处理中可能改桶
    bucket.clear();

    int processed = 0;
    for (uint64_t pos : items) {
        if (processed >= updatesPerTick) {
            // 本刻未处理完，重新调度到下一刻
            schedule(pos, 1);
            continue;
        }
        processSource(pos);
        processed++;
    }
    currentBucket = (currentBucket + 1) % 512;
}

void FluidSimulator::processSource(uint64_t pos) {
    if (!world) return;

    int wx, wy, wz;
    decode(pos, wx, wy, wz);

    BlockID id = world->getBlock(wx, wy, wz);
    if (id != BLOCK_WATER) return; // 已不是水（被挖掉/替换）

    uint8_t myLevel = world->getWaterLevel(wx, wy, wz);
    BlockID below = world->getBlock(wx, wy - 1, wz);
    BlockID above = world->getBlock(wx, wy + 1, wz);

    // ---- 1. 水源形成（无限水规则） ----
    bool belowSupports = (below != BLOCK_AIR); // 固体或水源都算支撑
    if (belowSupports) {
        int sourceNeighbors = 0;
        if (world->getBlock(wx+1, wy, wz) == BLOCK_WATER && world->getWaterLevel(wx+1, wy, wz) == 0) sourceNeighbors++;
        if (world->getBlock(wx-1, wy, wz) == BLOCK_WATER && world->getWaterLevel(wx-1, wy, wz) == 0) sourceNeighbors++;
        if (world->getBlock(wx, wy, wz+1) == BLOCK_WATER && world->getWaterLevel(wx, wy, wz+1) == 0) sourceNeighbors++;
        if (world->getBlock(wx, wy, wz-1) == BLOCK_WATER && world->getWaterLevel(wx, wy, wz-1) == 0) sourceNeighbors++;
        if (sourceNeighbors >= 2 && myLevel != 0) {
            world->setBlock(wx, wy, wz, BLOCK_WATER);
            world->setWaterLevel(wx, wy, wz, 0);
            markChunkDirty(wx, wz);
            for (int d : {-1, 1}) {
                schedule(encode(wx+d, wy, wz), 5);
                schedule(encode(wx, wy, wz+d), 5);
            }
            myLevel = 0; // 已变水源
        }
    }

    // ---- 2. 传播式重算：流水方块的应有水位 ----
    // MC 规则：流水水位 = min(相邻水源/流水水位) + 1，clamp[1,7]；被切断则移除。
    if (myLevel != 0) { // 非水源才需重算
        // 若上方有水（源或下落），本格是下落柱的一部分 → level 8
        if (above == BLOCK_WATER) {
            if (myLevel != 8) {
                world->setWaterLevel(wx, wy, wz, 8);
                markChunkDirty(wx, wz);
                myLevel = 8;
            }
        } else if (below != BLOCK_AIR) {
            // 平地流水：重算应有水位。供给源 = 水位严格低于自身的相邻水方块。
            // 这样同级流水互相不能维持（防止孤立流水群永不消失）。
            int bestFeeder = 999; // 最优供给水位（最小，需严格 < myLevel 才算有效供给）
            const int dx4[4] = {1,-1,0,0};
            const int dz4[4] = {0,0,1,-1};
            for (int i = 0; i < 4; ++i) {
                BlockID nb = world->getBlock(wx+dx4[i], wy, wz+dz4[i]);
                if (nb == BLOCK_WATER) {
                    uint8_t nl = world->getWaterLevel(wx+dx4[i], wy, wz+dz4[i]);
                    if (nl < bestFeeder) bestFeeder = nl;
                }
            }
            // 有效供给要求 bestFeeder+1 <= myLevel（即存在水位更低的邻居能喂它）
            // 若 bestFeeder+1 > myLevel（无更低邻居）→ 失去供给 → 移除
            if (bestFeeder == 999 || bestFeeder + 1 > myLevel) {
                // 无有效供给（被切断）→ 移除本格水
                world->setBlock(wx, wy, wz, BLOCK_AIR);
                world->setWaterLevel(wx, wy, wz, 0);
                markChunkDirty(wx, wz);
                // 通知邻居重新评估（它们可能也需退回）
                for (int d : {-1, 1}) {
                    schedule(encode(wx+d, wy, wz), 5);
                    schedule(encode(wx, wy, wz+d), 5);
                    schedule(encode(wx, wy-1, wz), 5);
                    schedule(encode(wx, wy+1, wz), 5);
                }
                return;
            }
            int shouldLevel = bestFeeder + 1;
            if (shouldLevel > 7) shouldLevel = 7;
            if (shouldLevel != myLevel) {
                world->setWaterLevel(wx, wy, wz, uint8_t(shouldLevel));
                markChunkDirty(wx, wz);
                myLevel = uint8_t(shouldLevel);
                // 水位变化，通知邻居重算
                for (int d : {-1, 1}) {
                    schedule(encode(wx+d, wy, wz), 5);
                    schedule(encode(wx, wy, wz+d), 5);
                }
            }
        }
    }

    // ---- 3. 向下流（最优先）：下方空气则生成下落水 ----
    if (below == BLOCK_AIR) {
        world->setBlock(wx, wy - 1, wz, BLOCK_WATER);
        world->setWaterLevel(wx, wy - 1, wz, 8);
        markChunkDirty(wx, wz);
        schedule(encode(wx, wy - 1, wz), 5);
    }

    // ---- 4. 水平扩散：把 level+1 推给水平邻居 ----
    // 水源(0)→扩散1；流水(k)→扩散k+1。最远 level 7。
    // 下落水柱(level 8)：仅在落地点(below是固体)才水平扩散(level 1)；
    // 下落中(below空气/水)只继续向下，不水平扩散——否则整根柱子每层都扩散会流得很远。
    int spreadLevel;
    if (myLevel == 8) {
        if (below == BLOCK_AIR || below == BLOCK_WATER) {
            return; // 下落中，不水平扩散
        }
        spreadLevel = 1; // 落地，按源级别扩散
    } else {
        spreadLevel = myLevel + 1;
    }
    if (spreadLevel > 7) return; // 超出 MC 最远距离

    // 自身周期性重调度以维持扩散（水源/下落柱持续驱动）
    schedule(encode(wx, wy, wz), 5);

    const int dx[4] = {1, -1, 0, 0};
    const int dz[4] = {0, 0, 1, -1};
    for (int i = 0; i < 4; ++i) {
        int nx = wx + dx[i];
        int nz = wz + dz[i];
        BlockID nid = world->getBlock(nx, wy, nz);
        if (nid == BLOCK_AIR) {
            world->setBlock(nx, wy, nz, BLOCK_WATER);
            world->setWaterLevel(nx, wy, nz, uint8_t(spreadLevel));
            markChunkDirty(nx, nz);
            schedule(encode(nx, wy, nz), 5);
        } else if (nid == BLOCK_WATER) {
            uint8_t nLevel = world->getWaterLevel(nx, wy, nz);
            // 邻居是水源/下落则不动；否则若其水位高于 spreadLevel，降至 spreadLevel（收敛）
            if (nLevel != 0 && nLevel != 8 && nLevel > uint8_t(spreadLevel)) {
                world->setWaterLevel(nx, wy, nz, uint8_t(spreadLevel));
                markChunkDirty(nx, nz);
                schedule(encode(nx, wy, nz), 5);
            }
        }
    }
}
