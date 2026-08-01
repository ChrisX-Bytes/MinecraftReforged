# world_gen/fluid_simulator.py
"""
MC-style fluid simulator integrated with ScheduledTickManager:
- scheduler.tick() provides positions scheduled for this tick (water ticks).
- FluidSimulator.tick(scheduled_positions) processes those positions (and any pending positions),
  performs down-first then BFS horizontal spread (max level = MAX_FLUID_LEVEL),
  and applies up to updates_per_tick writes.
"""
from collections import deque
from config import MAX_FLUID_LEVEL, DEFAULT_UPDATES_PER_TICK, LOAD_LEVEL_FULL
from chunk_manager import get_block, set_block, get_chunk, chunks, is_solid, get_chunk_pos

HDIRS = [(1,0), (-1,0), (0,1), (0,-1)]

class FluidSimulator:
    def __init__(self, updates_per_tick=DEFAULT_UPDATES_PER_TICK):
        self.updates_per_tick = updates_per_tick

    def tick(self, scheduled_positions):
        """
        scheduled_positions: set of (wx,wy,wz) positions that scheduler says should be processed now.
        We also consider chunk.pending_fluids to capture writes that were added but not scheduled.
        """
        # Consolidate candidate sources from scheduled positions and pending sets
        sources = set()

        # 1) From scheduled_positions (explicitly scheduled)
        if scheduled_positions:
            for pos in scheduled_positions:
                wx, wy, wz = pos
                b = get_block(wx, wy, wz)
                if b == 'water':
                    # Only treat level==0 as source for horizontal BFS (we will rely on fluid_levels info in chunk)
                    chx, chz = get_chunk_pos(wx, wz)
                    ch = chunks.get((chx, chz))
                    if ch:
                        lvl = ch.get_fluid_level(wx, wy, wz)
                        if lvl == 0:
                            sources.add((wx, wy, wz))

        # 2) Also include pending_fluids from loaded chunks (small set per chunk)
        for (cx, cz), chunk in list(chunks.items()):
            if getattr(chunk, 'load_level', LOAD_LEVEL_UNLOADED) > LOAD_LEVEL_FULL:
                continue
            if chunk.pending_fluids:
                # inspect pending positions in this chunk
                for (wx, wy, wz) in list(chunk.pending_fluids):
                    b = get_block(wx, wy, wz)
                    if b == 'water':
                        lvl = chunk.get_fluid_level(wx, wy, wz)
                        if lvl == 0:
                            sources.add((wx, wy, wz))

        if not sources:
            return

        # Aggregate targets
        target_levels = {}
        falling = {}
        touched = set()

        # BFS/propagate from each source (horizontal BFS limited by MAX_FLUID_LEVEL), down-first handled earlier
        for sx, sy, sz in sources:
            for dx, dz in HDIRS:
                nx, ny, nz = sx + dx, sy, sz + dz
                nb = get_block(nx, ny, nz)
                if nb is not None and nb != 'water':
                    continue
                below = get_block(nx, ny - 1, nz)
                if below is None:
                    key = (nx, ny - 1, nz)
                    if target_levels.get(key, 99) > 0:
                        falling[key] = 0
                        touched.add(key)
                    continue
                if (below == 'water' or is_solid(nx, ny - 1, nz)):
                    # BFS horizontally
                    q = deque()
                    visited = set()
                    q.append((nx, nz, 1))
                    visited.add((nx, nz))
                    while q:
                        x0, z0, dist = q.popleft()
                        if dist > MAX_FLUID_LEVEL:
                            continue
                        y0 = ny
                        b = get_block(x0, y0, z0)
                        if b is None or b == 'water':
                            key = (x0, y0, z0)
                            new_level = dist
                            prev = target_levels.get(key)
                            if prev is None or new_level < prev:
                                target_levels[key] = new_level
                                touched.add(key)
                        below0 = get_block(x0, y0 - 1, z0)
                        if below0 is None:
                            continue
                        if not (below0 == 'water' or is_solid(x0, y0 - 1, z0)):
                            continue
                        for ddx, ddz in HDIRS:
                            nx2, nz2 = x0 + ddx, z0 + ddz
                            if (nx2, nz2) in visited:
                                continue
                            nb2 = get_block(nx2, y0, nz2)
                            if nb2 is not None and nb2 != 'water':
                                continue
                            visited.add((nx2, nz2))
                            q.append((nx2, nz2, dist + 1))

        # Also consider existing water that should fall (below is empty)
        for (cx, cz), chunk in list(chunks.items()):
            if getattr(chunk, 'load_level', LOAD_LEVEL_UNLOADED) > LOAD_LEVEL_FULL:
                continue
            for (wx, wy, wz), lvl in chunk.fluid_levels.items():
                below = get_block(wx, wy - 1, wz)
                if below is None:
                    key = (wx, wy - 1, wz)
                    if target_levels.get(key, 99) > 0:
                        falling[key] = 0
                        touched.add(key)

        # Apply writes with budget
        writes = 0
        # falling first
        for (x,y,z), lvl in falling.items():
            if writes >= self.updates_per_tick:
                break
            cur = get_block(x, y, z)
            if cur == 'water':
                chx, chz = get_chunk_pos(x, z)
                ch = chunks.get((chx, chz))
                if ch and ch.get_fluid_level(x, y, z) == lvl:
                    continue
            set_block(x, y, z, 'water', lvl)
            writes += 1

        # then horizontal (favor smaller levels for nicer visuals)
        items = sorted(target_levels.items(), key=lambda it: it[1])
        for (x,y,z), lvl in items:
            if writes >= self.updates_per_tick:
                break
            cur = get_block(x, y, z)
            if cur == 'water':
                chx, chz = get_chunk_pos(x, z)
                ch = chunks.get((chx, chz))
                if ch and ch.get_fluid_level(x, y, z) == lvl:
                    continue
            set_block(x, y, z, 'water', lvl)
            writes += 1

        # Ensure touched positions' chunks have pending marks (set_block normally does this too)
        for (x,y,z) in touched:
            chx, chz = get_chunk_pos(x, z)
            ch = chunks.get((chx, chz))
            if ch:
                ch.pending_fluids.add((x,y,z))