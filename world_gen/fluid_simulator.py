# world_gen/fluid_simulator.py
"""
更接近 Minecraft Java 的水流实现（受限且兼顾性能）。
策略摘要：
- 只用现有的 source（level==0）作为 BFS 源来水平扩散，流动块不当作新源来触发无限扩散。
- 水平扩散只在 "supported" 的格子上进行（下方是实体或水）；否则会下落（下落产生 level=0 的瀑布）。
- tick 开始时快照 existing_sources 防止本 tick 新写入的 source 参与同 tick 的转换。
- 写入被限制（updates_per_tick），且仅在值真正改变时写入，以减少不必要重建。
"""
from collections import deque, defaultdict
from config import MAX_FLUID_LEVEL, LOAD_LEVEL_FULL
from chunk_manager import get_block, set_block, get_chunk, chunks, is_solid, get_chunk_pos

HDIRS = [(1,0), (-1,0), (0,1), (0,-1)]

class FluidSimulator:
    def __init__(self, updates_per_tick=150):
        self.updates_per_tick = updates_per_tick
        # pending queue is kept in chunk.pending_fluids; we will scan those into a work list each tick
        # no persistent global queue here; we compute targets per tick from sources snapshot
        # to avoid repeated heavy work, we only BFS from sources touching pending areas
        pass

    def tick(self):
        """Single simulation step.
        Steps:
          1) Snapshot existing sources (level==0) across loaded chunks.
          2) Collect candidate sources to process: those sources that are in/near pending_fluids (optimization).
          3) For each such source, BFS horizontally up to MAX_FLUID_LEVEL, but only traverse "supported" cells
             (cells whose below is solid or water). If neighbor's below is empty, produce a falling target (level 0).
          4) Aggregate target_levels and falling targets, then write them (bounded by updates_per_tick).
          5) Clear processed chunk.pending_fluids entries appropriately.
        """
        # 1) 快照所有已存在的 source（仅在加载区块内）
        existing_sources = set()
        for (cx, cz), chunk in list(chunks.items()):
            if getattr(chunk, "load_level", LOAD_LEVEL_FULL+1) > LOAD_LEVEL_FULL:
                continue
            # chunk.fluid_levels: dict {(wx,wy,wz): level}
            for (wx, wy, wz), lvl in chunk.fluid_levels.items():
                if lvl == 0:
                    existing_sources.add((wx, wy, wz))

        if not existing_sources:
            return

        # 2) 收集要处理的 source：优化为只处理邻近 pending 的 source 或所有 source（保守起见：处理所有 source）
        # For simplicity, we process all existing_sources. If performance becomes an issue, we can limit to sources near pending.
        sources_to_process = existing_sources

        # 3) BFS from each source, aggregate target_levels
        # target_levels[(x,y,z)] = level to set (0..MAX)
        target_levels = dict()
        falling_targets = dict()  # (x,y,z)->level (level will be 0)
        # We'll also record which positions we touched so we can re-add their chunk's pending later
        touched_positions = set()

        for sx, sy, sz in sources_to_process:
            # For each horizontal neighbor of the source, start BFS with distance=1
            for dx, dz in HDIRS:
                nx, ny, nz = sx + dx, sy, sz + dz
                # skip solids (can't replace)
                nb = get_block(nx, ny, nz)
                if nb is not None and nb != 'water':
                    continue
                # if below is empty -> falling
                below = get_block(nx, ny - 1, nz)
                if below is None:
                    # falling target is the block below (ny-1)
                    key = (nx, ny-1, nz)
                    # always level 0 for falling
                    if target_levels.get(key, 99) > 0:
                        falling_targets[key] = 0
                        touched_positions.add(key)
                    continue
                # else if below is supported (solid or water), BFS horizontally starting at (nx,ny,nz) with dist=1
                if (below is not None) and (below == 'water' or is_solid(nx, ny-1, nz)):
                    # BFS queue entries: (x,z,dist)
                    q = deque()
                    visited = set()
                    q.append((nx, nz, 1))
                    visited.add((nx, nz))
                    while q:
                        x0, z0, dist = q.popleft()
                        if dist > MAX_FLUID_LEVEL:
                            continue
                        y0 = ny  # same y plane
                        # check replaceable
                        b = get_block(x0, y0, z0)
                        if b is None or b == 'water':
                            key = (x0, y0, z0)
                            # new level = dist (because source neighbor had dist=1 -> level=1)
                            new_level = dist
                            prev = target_levels.get(key)
                            if prev is None or new_level < prev:
                                target_levels[key] = new_level
                                touched_positions.add(key)
                        # expand further only if this cell is supported (below solid or water) and not exceeded depth
                        below0 = get_block(x0, y0-1, z0)
                        if below0 is None:
                            # position's below empty -> we don't expand horizontally from here; it would fall
                            # but we already handled falling for adjacent to source; we can also mark falling if needed
                            continue
                        if not (below0 == 'water' or is_solid(x0, y0-1, z0)):
                            continue
                        # expand
                        for ddx, ddz in HDIRS:
                            nx2, nz2 = x0 + ddx, z0 + ddz
                            if (nx2, nz2) in visited:
                                continue
                            nb2 = get_block(nx2, y0, nz2)
                            if nb2 is not None and nb2 != 'water':
                                continue
                            visited.add((nx2, nz2))
                            q.append((nx2, nz2, dist + 1))

        # 4) Also consider existing flowing blocks that are over empty: they should fall
        # Find all chunks' pending_fluids or existing water blocks; to avoid heavy scan, we scan touched_positions neighborhood
        # But to keep correctness, do a light scan: any water block whose below is empty becomes falling target
        # (We scan loaded chunks; this is O(n_loaded) but acceptable if not too many chunks)
        for (cx, cz), chunk in list(chunks.items()):
            if getattr(chunk, "load_level", LOAD_LEVEL_FULL+1) > LOAD_LEVEL_FULL:
                continue
            # iterate over fluid_levels
            for (wx, wy, wz), lvl in chunk.fluid_levels.items():
                if lvl >= 0:
                    below = get_block(wx, wy - 1, wz)
                    if below is None:
                        key = (wx, wy - 1, wz)
                        if target_levels.get(key, 99) > 0:
                            falling_targets[key] = 0
                            touched_positions.add(key)

        # 5) Now write targets, but bound by updates_per_tick and avoid writing unchanged states
        writes = 0
        # write falling targets first (they are visually important)
        for (x,y,z), lvl in falling_targets.items():
            if writes >= self.updates_per_tick:
                break
            cur_block = get_block(x,y,z)
            if cur_block == 'water':
                ch = self.get_chunk_at(x, z)
                if ch and ch.get_fluid_level(x,y,z) == lvl:
                    continue
            # set only if different
            set_block(x, y, z, 'water', lvl)
            writes += 1

        # then write horizontal target_levels (sort to favor small levels first for nicer visuals)
        items = sorted(target_levels.items(), key=lambda it: it[1])
        for (x,y,z), lvl in items:
            if writes >= self.updates_per_tick:
                break
            cur_block = get_block(x,y,z)
            if cur_block == 'water':
                ch = self.get_chunk_at(x, z)
                if ch and ch.get_fluid_level(x,y,z) == lvl:
                    continue
            set_block(x, y, z, 'water', lvl)
            writes += 1

        # 6) Mark pending for touched positions' chunks so next tick they will be considered (set_block usually does this,
        # but ensure neighbor updates)
        for (x,y,z) in touched_positions:
            ch = self.get_chunk_at(x, z)
            if ch:
                ch.pending_fluids.add((x,y,z))

    def get_chunk_at(self, x, z):
        cx, cz = get_chunk_pos(x, z)
        return chunks.get((cx, cz))