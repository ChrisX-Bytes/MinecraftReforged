# world_gen/density.py
from config import WORLD_BOTTOM, WORLD_TOP


def final_density(x, y, z, noise_gen, seed):
    # 1. 使用噪声计算一个基础地表高度 (ground level)
    # 范围大约在 40 到 90 之间，形成起伏的地形
    continentalness = noise_gen.noise2d(x * 0.005, z * 0.005)
    ground_level = 64.0 + continentalness * 25.0

    # 2. 添加微地形起伏 (让地形更自然)
    detail = noise_gen.noise3d(x * 0.08, y * 0.08, z * 0.08) * 1.5
    ground_level += detail

    # 3. 核心密度计算：基于当前高度与地表高度的差值
    # 如果 y > ground_level，density 为负 (空气)
    # 如果 y < ground_level，density 为正 (石头)
    density = ground_level - y

    # 4. 添加一些山脊/山谷的微调 (可选，增加趣味)
    ridge_input = noise_gen.noise2d(x * 0.025, z * 0.025)
    ridge = 1.0 - abs(ridge_input)
    # 只在接近地表的位置施加影响，避免影响地下深处
    surface_proximity = max(0.0, 1.0 - abs(density) / 15.0)
    density += ridge * 5.0 * surface_proximity

    # 5. 世界边界强制 (保持不变)
    if y <= WORLD_BOTTOM:
        density = 1.0
    elif y >= WORLD_TOP:
        density = -1.0

    return density