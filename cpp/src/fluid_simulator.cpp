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

// ---- 辅助：4 水平方向偏移 ----
static const int DX4[4] = {1, -1, 0, 0};
static const int DZ4[4] = {0, 0, 1, -1};

void FluidSimulator::processSource(uint64_t pos) {
    if (!world) return;

    int wx, wy, wz;
    decode(pos, wx, wy, wz);

    BlockID id = world->getBlock(wx, wy, wz);
    if (id != BLOCK_WATER) return; // 已不是水（被挖掉/替换）

    uint8_t myLevel = world->getWaterLevel(wx, wy, wz);
    BlockID below = world->getBlock(wx, wy - 1, wz);
    BlockID above = world->getBlock(wx, wy + 1, wz);

    // below 是否"支撑"（液体流不进的方块）：固体，或水源（源柱不下降）。
    // 注意：流水(level 1-7)不算支撑——水会从流水上方继续往下渗透。
    bool belowSupports = (below != BLOCK_AIR && below != BLOCK_WATER) ||
                         (below == BLOCK_WATER && world->getWaterLevel(wx, wy - 1, wz) == 0);

    // ===== 阶段 1：无限水源形成（仅对流水块 level 1-7）=====
    // MC Java：非源水流块，下方有支撑，且水平 4 邻居中水源(level 0) ≥ 2 → 变源。
    if (myLevel != 0 && myLevel != 8 && belowSupports) {
        int sourceNeighbors = 0;
        for (int i = 0; i < 4; ++i) {
            if (world->getBlock(wx + DX4[i], wy, wz + DZ4[i]) == BLOCK_WATER &&
                world->getWaterLevel(wx + DX4[i], wy, wz + DZ4[i]) == 0) {
                sourceNeighbors++;
            }
        }
        if (sourceNeighbors >= 2) {
            world->setBlock(wx, wy, wz, BLOCK_WATER);
            world->setWaterLevel(wx, wy, wz, 0);
            markChunkDirty(wx, wz);
            // 通知 6 邻居重算（成源可能改变它们的供给/扩散）
            for (int i = 0; i < 4; ++i) schedule(encode(wx + DX4[i], wy, wz + DZ4[i]), 5);
            schedule(encode(wx, wy - 1, wz), 5);
            schedule(encode(wx, wy + 1, wz), 5);
            myLevel = 0;
        }
    }

    // ===== 阶段 2：重算流水块应有水位（receiver 模型）=====
    // MC Java：流水块水位 = min(有效供给) + 1。供给来自水平邻居或上方下落。
    // 适用：level 1-7 总是重算；level 8 仅当上方不再是水时才重算
    //   （下落柱被切断：上方变空气 → 不再是下落柱一部分 → 退回平地流水重算）。
    if (myLevel != 0 && (myLevel != 8 || above != BLOCK_WATER)) {
        int targetLevel;
        if (above == BLOCK_WATER) {
            // 上方有水（源或下落柱）→ 本格是下落柱的一部分 → level 8
            // （此分支仅在 myLevel 为 1-7 时进入，因为 myLevel==8 且 above==water 已被外层 if 排除）
            targetLevel = 8;
        } else if (myLevel == 8) {
            // 刚脱离下落柱的 level 8 块（上方已变空气）：
            // 只接受"真实水源"——水平邻居中的源(level 0)或下落柱(level 8)——作为新供给，
            // 不接受它自己之前扩散出去的流水(level 1-7)反喂（否则切断后永不变干）。
            // 有真实水源 → 降为 level 1（落地点重新扩散）；无 → 干涸。
            bool hasRealSource = false;
            for (int i = 0; i < 4; ++i) {
                if (world->getBlock(wx + DX4[i], wy, wz + DZ4[i]) == BLOCK_WATER) {
                    uint8_t nl = world->getWaterLevel(wx + DX4[i], wy, wz + DZ4[i]);
                    if (nl == 0 || nl == 8) { hasRealSource = true; break; }
                }
            }
            if (!hasRealSource) {
                world->setBlock(wx, wy, wz, BLOCK_AIR);
                world->setWaterLevel(wx, wy, wz, 0);
                markChunkDirty(wx, wz);
                for (int i = 0; i < 4; ++i) schedule(encode(wx + DX4[i], wy, wz + DZ4[i]), 5);
                schedule(encode(wx, wy - 1, wz), 5);
                schedule(encode(wx, wy + 1, wz), 5);
                return;
            }
            targetLevel = 1; // 落地点：重新按 level 1 扩散
        } else {
            // level 1-7 平地流水：扫 4 水平邻居，取最小有效供给水位。
            // 有效供给条件：邻居等效水位 eff < myLevel（供给方水位须严格低于本块，
            // 否则 eff+1 > myLevel 无法维持本块水位，且避免同级方块互相"供给"导致永不变干）。
            //   邻居 level 8（下落柱）按源 0 供给（eff=0 < 任何 level 1-7）。
            //   邻居 level 0（源）eff=0。
            int minInput = 999;
            for (int i = 0; i < 4; ++i) {
                if (world->getBlock(wx + DX4[i], wy, wz + DZ4[i]) == BLOCK_WATER) {
                    uint8_t nl = world->getWaterLevel(wx + DX4[i], wy, wz + DZ4[i]);
                    int eff = (nl == 8) ? 0 : nl;
                    if (eff < myLevel && eff < minInput) minInput = eff;
                }
            }
            if (minInput == 999) {
                // 无有效供给 → 干涸（水源被切断）
                world->setBlock(wx, wy, wz, BLOCK_AIR);
                world->setWaterLevel(wx, wy, wz, 0);
                markChunkDirty(wx, wz);
                // 级联：通知邻居重算（它们可能也失去供给）
                for (int i = 0; i < 4; ++i) schedule(encode(wx + DX4[i], wy, wz + DZ4[i]), 5);
                schedule(encode(wx, wy - 1, wz), 5);
                schedule(encode(wx, wy + 1, wz), 5);
                return;
            }
            targetLevel = minInput + 1; // 1..7
        }
        if (targetLevel != myLevel) {
            world->setWaterLevel(wx, wy, wz, uint8_t(targetLevel));
            markChunkDirty(wx, wz);
            myLevel = uint8_t(targetLevel);
            // 水位变化，通知水平邻居重算
            for (int i = 0; i < 4; ++i) schedule(encode(wx + DX4[i], wy, wz + DZ4[i]), 5);
        }
    }

    // ===== 阶段 3：向下流（below 是空气）=====
    // MC：下方是空气时只直落成下落柱(level 8)，不水平扩散。
    // 含水源也遵循——源块 below 是固体才扩散，below 是空气就落下。
    if (below == BLOCK_AIR) {
        world->setBlock(wx, wy - 1, wz, BLOCK_WATER);
        world->setWaterLevel(wx, wy - 1, wz, 8);
        markChunkDirty(wx, wz);
        schedule(encode(wx, wy - 1, wz), 5);
        return; // 只下落，不水平扩散
    }

    // ===== 阶段 4：水平扩散（仅当 below 是固体）=====
    // MC 规则：液体只在"有支撑"（below 是固体）时才向四周水平扩散。
    //   below 是空气 → 已在阶段 3 下落并 return。
    //   below 是水（下落柱/水源）→ 本块是下落流的一部分，不水平扩散——
    //     否则悬空的流水块会在半腰形成水平水架（图三 bug：2-3 层悬浮水）。
    //   关键防回归：流水块下落后，below 被填成水，若被重新调度会再次扩散 → 悬浮水架。
    //     所以 below 非（固体）时一律不扩散。
    if (below == BLOCK_AIR || below == BLOCK_WATER) {
        // below 非固体：不水平扩散。源(0)/下落柱(8)自我重调度以监听 below 变化；
        //   流水(1-7)不自我重调度（稳定态，由邻居变化驱动）。
        if (myLevel == 0 || myLevel == 8) {
            schedule(encode(wx, wy, wz), 5);
        }
        return;
    }

    // pushLevel：源(0)和下落柱落地点(8)按 1 扩散；流水(k)按 k+1 扩散。
    int pushLevel;
    if (myLevel == 0 || myLevel == 8) {
        pushLevel = 1; // 源 / 下落柱落地点（below 必固体）
    } else {
        pushLevel = myLevel + 1;
    }
    if (pushLevel > 7) {
        // 超出 MC 最远距离（流水 level 7 不再扩散），不自我重调度（稳定态）。
        // 水源被切断时 set_block 激活邻居，邻居阶段2干涸并级联 schedule 下游，无需自我轮询。
        return;
    }

    // 水平扩散：流入空气或降低高水位邻居。
    // 记录本次是否有改动；若无改动说明本块已处稳定平衡——不再自我重调度，
    // 避免稳定后海量方块轮询挤占 updatesPerTick 配额导致调度饥饿（新水流"停了"）。
    // 邻居变化时该块会被邻居 schedule 重新激活（扩散链/干涸链都会 schedule 受影响邻居）。
    bool changed = false;
    for (int i = 0; i < 4; ++i) {
        int nx = wx + DX4[i];
        int nz = wz + DZ4[i];
        BlockID nid = world->getBlock(nx, wy, nz);
        if (nid == BLOCK_AIR) {
            // 流入空气：创建 pushLevel 流水
            world->setBlock(nx, wy, nz, BLOCK_WATER);
            world->setWaterLevel(nx, wy, nz, uint8_t(pushLevel));
            markChunkDirty(nx, nz);
            schedule(encode(nx, wy, nz), 5);
            changed = true;
        } else if (nid == BLOCK_WATER) {
            uint8_t nLevel = world->getWaterLevel(nx, wy, nz);
            // 邻居是源(0)/下落(8)不动；否则若水位 > pushLevel，降至 pushLevel（收敛）
            if (nLevel != 0 && nLevel != 8 && nLevel > uint8_t(pushLevel)) {
                world->setWaterLevel(nx, wy, nz, uint8_t(pushLevel));
                markChunkDirty(nx, nz);
                schedule(encode(nx, wy, nz), 5);
                changed = true;
            }
        }
    }

    // 自我重调度策略：
    // - 源(0)/下落柱(8)：每 5 刻重调度，持续驱动扩散并监听 below 变化。
    // - 流水(1-7)有改动时：5 刻后重调度，继续驱动扩散/收敛链条。
    // - 流水(1-7)无改动（稳定）时：不自我重调度。邻居变化时由邻居 schedule 重新激活。
    //   干涸链：水源被挖时 set_block 激活邻居，邻居阶段2干涸并 schedule 其邻居，级联传播。
    //   少数边缘块可能因调度时序短暂滞后干涸，会在邻居干涸后被 schedule 而最终收敛。
    if (changed || myLevel == 0 || myLevel == 8) {
        schedule(encode(wx, wy, wz), 5);
    }
}
