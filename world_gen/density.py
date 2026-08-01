# world_gen/density.py
from config import WORLD_BOTTOM, WORLD_TOP

def final_density(x, y, z, noise_gen, seed):
    # 1. 基础地形 (大陆性噪声)
    continentalness = noise_gen.noise2d(x * 0.005, z * 0.005)
    base_height = 64.0 + continentalness * 40.0

    # 2. 计算基础密度
    density = base_height - y

    # 3. 细节噪声 (微地形起伏)
    detail = noise_gen.noise3d(x * 0.08, y * 0.08, z * 0.08) * 1.2
    density += detail

    # 4. 山脊噪声 (增强连续性)
    ridge_input = noise_gen.noise2d(x * 0.025, z * 0.025)
    ridge = 1.0 - abs(ridge_input)
    surface_proximity = max(0.0, 1.0 - abs(density) / 25.0)
    density += ridge * 8.0 * surface_proximity

    # 5. 世界边界强制
    if y <= WORLD_BOTTOM:
        density = 1.0
    elif y >= WORLD_TOP:
        density = -1.0

    return density