# world_gen/fluid_simulator.py
from chunk_manager import get_block, set_block, get_chunk, chunks, is_solid, get_chunk_pos
from config import MAX_FLUID_LEVEL

class FluidSimulator:
    def __init__(self):
        self.updates_per_tick = 20  # 每帧最多更新20个流体，保证帧率

    def tick(self):
        """主更新循环 - 每帧调用"""
        pending = self.collect_pending_fluids()
        count = 0
        for pos in pending:
            if count >= self.updates_per_tick:
                break
            if self.update_fluid(pos):
                count += 1

    def collect_pending_fluids(self):
        """从所有区块收集待更新流体"""
        pending = []
        for (cx, cz), chunk in chunks.items():
            # 只处理加载等级足够的区块
            if chunk.load_level > 33:  # 只更新完全加载的区块
                continue
            for pos in chunk.pending_fluids:
                pending.append(pos)
            chunk.pending_fluids.clear()
        return pending

    def update_fluid(self, pos):
        """更新单个流体方块"""
        x, y, z = pos
        block = get_block(x, y, z)
        if block != 'water':
            return False

        # 获取当前深度
        chunk = self.get_chunk_at(x, z)
        if not chunk:
            return False
        current_level = chunk.get_fluid_level(x, y, z)
        if current_level < 0:
            return False

        # 如果已经是深度7，不再流动
        if current_level >= MAX_FLUID_LEVEL:
            # 检查是否应该成为源（无限水）
            if self.should_become_source(x, y, z):
                chunk.set_block(x, y, z, 'water', 0)
                return True
            return False

        # 1. 检查下方是否可流
        if not is_solid(x, y-1, z) and get_block(x, y-1, z) != 'water':
            # 向下流：深度不变
            self.flow_to(x, y-1, z, current_level)
            return True

        # 2. 检查水平方向 - 寻找最低洼处
        best_direction = self.find_lowest_neighbor(x, y, z)
        if best_direction:
            dx, dz = best_direction
            new_level = current_level + 1
            if new_level <= MAX_FLUID_LEVEL:
                self.flow_to(x+dx, y, z+dz, new_level)
                return True

        # 3. 检查是否应该成为源（无限水逻辑）
        if self.should_become_source(x, y, z):
            chunk.set_block(x, y, z, 'water', 0)
            return True

        return False

    def flow_to(self, x, y, z, level):
        """水流动到新位置"""
        block = get_block(x, y, z)
        # 如果是空气或水（允许重叠更新）
        if block is None or block == 'water':
            set_block(x, y, z, 'water', level)
            # 加入待更新队列
            chunk = self.get_chunk_at(x, z)
            if chunk:
                chunk.pending_fluids.add((x, y, z))

    def find_lowest_neighbor(self, x, y, z):
        """找到最低的邻居方向（优先向下倾斜）"""
        directions = [(1,0), (-1,0), (0,1), (0,-1)]
        best_dir = None
        best_y = y  # 初始为当前位置

        for dx, dz in directions:
            nx, nz = x+dx, z+dz
            # 检查该位置是否可流
            if not self.can_flow_to(nx, y, nz):
                continue
            # 检查该位置下方是否更低（优先考虑下坡）
            if not is_solid(nx, y-1, nz) and get_block(nx, y-1, nz) != 'water':
                # 如果下方是空气，优先选择这个方向（形成瀑布）
                return (dx, dz)
            # 检查同高度是否有更低的洼地？我们需要比较邻居的高度
            # 实际上MC中水平流动是向周围的低处流，但这里简化：只要邻居是空气就可以流
            # 更准确：如果邻居是空气，则流动；但如果有多个，我们可以选择最低的Y
            # 由于Y相同，我们默认第一个可流的方向
            if get_block(nx, y, nz) is None:
                if best_dir is None:
                    best_dir = (dx, dz)
                    best_y = y  # 同高度
                # 如果已经有同高度的，不做改变

        # 如果没有任何方向可流，但best_dir已设置，说明可以水平流
        return best_dir

    def can_flow_to(self, x, y, z):
        """检查位置是否可流（空气或水）"""
        block = get_block(x, y, z)
        # 允许流向空气或水（更新水深度）
        return block is None or block == 'water'

    def should_become_source(self, x, y, z):
        """检查是否应成为新水源（无限水逻辑）"""
        water_sources = 0
        for dx, dz in [(1,0), (-1,0), (0,1), (0,-1)]:
            nx, nz = x+dx, z+dz
            chunk = self.get_chunk_at(nx, nz)
            if chunk and chunk.get_fluid_level(nx, y, nz) == 0:
                water_sources += 1
            if water_sources >= 2:
                return True
        return False

    def get_chunk_at(self, x, z):
        """获取坐标所在区块"""
        from chunk_manager import get_chunk_pos, chunks
        cx, cz = get_chunk_pos(x, z)
        return chunks.get((cx, cz))