#include "fluid_simulator.h"
#include "chunk.h"
#include "block_ids.h"

FluidSimulator::FluidSimulator(World* world, int updatesPerTick)
    : world(world), updatesPerTick(updatesPerTick), currentBucket(0) {
    for (int i = 0; i < 512; ++i) buckets[i].clear();
}

uint64_t FluidSimulator::encode(int wx, int wy, int wz) {
    // wy 用 20 位带符号偏移（-524288..+524287 足够覆盖 -64..319）
    return (uint64_t(uint32_t(wx)) << 40)
         | (uint64_t(uint32_t(wy) & 0xFFFFF) << 20)
         | (uint64_t(uint32_t(wz)) & 0xFFFFF);
}

void FluidSimulator::decode(uint64_t pos, int& wx, int& wy, int& wz) {
    wx = int(uint32_t(pos >> 40));
    wy = int((pos >> 20) & 0xFFFFF);
    wz = int(pos & 0xFFFFF);
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
    // 条件：下方为固体/水源，且水平 >=2 个水源邻居
    bool belowSupports = (below != BLOCK_AIR); // 固体或水源都算支撑
    if (belowSupports) {
        int sourceNeighbors = 0;
        if (world->getBlock(wx+1, wy, wz) == BLOCK_WATER && world->getWaterLevel(wx+1, wy, wz) == 0) sourceNeighbors++;
        if (world->getBlock(wx-1, wy, wz) == BLOCK_WATER && world->getWaterLevel(wx-1, wy, wz) == 0) sourceNeighbors++;
        if (world->getBlock(wx, wy, wz+1) == BLOCK_WATER && world->getWaterLevel(wx, wy, wz+1) == 0) sourceNeighbors++;
        if (world->getBlock(wx, wy, wz-1) == BLOCK_WATER && world->getWaterLevel(wx, wy, wz-1) == 0) sourceNeighbors++;
        if (sourceNeighbors >= 2) {
            if (myLevel != 0) {
                world->setBlock(wx, wy, wz, BLOCK_WATER);
                world->setWaterLevel(wx, wy, wz, 0);
                // 通知邻居重新评估（它们的扩散目标可能改变）
                schedule(encode(wx+1,wy,wz), 5);
                schedule(encode(wx-1,wy,wz), 5);
                schedule(encode(wx,wy,wz+1), 5);
                schedule(encode(wx,wy,wz-1), 5);
            }
            return; // 水源稳定，无需流动
        }
    }

    // ---- 2. 向下流（最优先） ----
    if (below == BLOCK_AIR) {
        // 下方为空气：生成下落水（level 8）
        world->setBlock(wx, wy - 1, wz, BLOCK_WATER);
        world->setWaterLevel(wx, wy - 1, wz, 8);
        schedule(encode(wx, wy - 1, wz), 5);
        // 自身若不是下落（即上方有水柱源头），保持；否则不变
        return;
    }

    // ---- 3. 计算自身应扩散的水平水位 ----
    // 水源(level 0)向水平扩散 level 1；流水(level k)扩散 level k+1；下落(level 8)落地后按 0 扩散。
    int spreadLevel;
    if (myLevel == 8) {
        // 下落水落地：本格相当于源头级别向四周扩散 level 1
        spreadLevel = 1;
    } else if (above == BLOCK_WATER) {
        // 上方有水：自身视为满（扩散 level 1）
        spreadLevel = 1;
    } else {
        spreadLevel = myLevel + 1;
    }

    // 超过 7 则不再继续扩散（MC 平地最远 7 格）
    if (spreadLevel > 7) {
        // 已到极限；但若自身是从更高水位降下来的，保留现状即可
        return;
    }

    // ---- 4. 水平扩散到 4 个邻居 ----
    const int dx[4] = {1, -1, 0, 0};
    const int dz[4] = {0, 0, 1, -1};
    for (int i = 0; i < 4; ++i) {
        int nx = wx + dx[i];
        int nz = wz + dz[i];
        int ny = wy;
        BlockID nid = world->getBlock(nx, ny, nz);
        if (nid == BLOCK_AIR) {
            // 流入空气
            world->setBlock(nx, ny, nz, BLOCK_WATER);
            world->setWaterLevel(nx, ny, nz, uint8_t(spreadLevel));
            schedule(encode(nx, ny, nz), 5);
        } else if (nid == BLOCK_WATER) {
            // 已是水：若邻居水位比 spreadLevel 高（更接近源），则把它降为 spreadLevel
            // 防止无限循环：只在严格降低时更新
            uint8_t nLevel = world->getWaterLevel(nx, ny, nz);
            if (nLevel != 0 && nLevel != 8 && nLevel > uint8_t(spreadLevel)) {
                world->setWaterLevel(nx, ny, nz, uint8_t(spreadLevel));
                schedule(encode(nx, ny, nz), 5);
            }
        }
    }
}
