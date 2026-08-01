# world_gen/noise_router.py
from .noise import PerlinNoise3D

class NoiseRouter:
    def __init__(self, noise_gen: PerlinNoise3D, seed: int):
        self.noise_gen = noise_gen
        self.seed = seed

    def fluid_level_floodedness(self, x: float, y: float, z: float) -> float:
        aquifer_noise = self.noise_gen.noise3d(x * 0.03, y * 0.03, z * 0.03)
        flooded = (aquifer_noise + 1) / 2
        return flooded

    def is_water_filled(self, x: float, y: float, z: float) -> bool:
        # 禁止在 y > 80 的天空生成水
        if y > 80:
            return False

        continentalness = self.noise_gen.noise2d(x * 0.005, z * 0.005)

        # 海洋逻辑：大陆性低且 y < 63 的区域为水
        if continentalness < -0.1 and y < 63:
            return True

        # 地下含水层（y < 63）正常判断，y >= 63 时阈值提高
        flooded = self.fluid_level_floodedness(x, y, z)
        if y < 63:
            return flooded > 0.55
        else:
            # y 在 63~80 之间，仅当淹没度极高时才生成水（防止山顶异常水）
            return flooded > 0.75