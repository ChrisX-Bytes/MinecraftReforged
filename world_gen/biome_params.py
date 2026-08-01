# world_gen/biome_params.py
import math

BIOME_PLAINS = 0
BIOME_FOREST = 1
BIOME_HILLS = 2
BIOME_MOUNTAINS = 3
BIOME_OCEAN = 4
BIOME_DESERT = 5
BIOME_SNOWY_TUNDRA = 6

# 理想参数：每个参数是一个 (最小值, 最大值) 的区间
BIOME_PARAMETERS = {
    BIOME_PLAINS: {
        "temperature": (0.5, 0.7),
        "humidity": (0.3, 0.5),
        "continentalness": (0.1, 0.4),   # 稍微扩大陆地范围
        "erosion": (0.2, 0.8),
        "weirdness": (-1.0, 1.0),
        "depth": (-0.1, 0.1),
    },
    BIOME_FOREST: {
        "temperature": (0.5, 0.7),
        "humidity": (0.6, 0.9),
        "continentalness": (0.3, 0.7),
        "erosion": (0.3, 0.7),
        "weirdness": (-1.0, 1.0),
        "depth": (-0.1, 0.1),
    },
    BIOME_HILLS: {
        "temperature": (0.4, 0.7),
        "humidity": (0.3, 0.6),
        "continentalness": (0.6, 0.9),
        "erosion": (0.0, 0.3),
        "weirdness": (-1.0, 1.0),
        "depth": (-0.1, 0.1),
    },
    BIOME_MOUNTAINS: {
        "temperature": (0.2, 0.6),
        "humidity": (0.3, 0.7),
        "continentalness": (0.8, 1.0),
        "erosion": (0.0, 0.2),
        "weirdness": (-1.0, 1.0),
        "depth": (-0.1, 0.1),
    },
    BIOME_OCEAN: {
        "temperature": (0.3, 0.7),
        "humidity": (0.3, 0.7),
        "continentalness": (-1.0, -0.2),   # 缩小海洋范围
        "erosion": (0.2, 0.8),
        "weirdness": (-1.0, 1.0),
        "depth": (-0.1, 0.1),
    },
    BIOME_DESERT: {
        "temperature": (0.8, 1.0),
        "humidity": (-0.5, 0.0),
        "continentalness": (0.4, 0.8),
        "erosion": (0.4, 0.8),
        "weirdness": (-1.0, 1.0),
        "depth": (-0.1, 0.1),
    },
    BIOME_SNOWY_TUNDRA: {
        "temperature": (-0.8, -0.3),
        "humidity": (0.2, 0.5),
        "continentalness": (0.4, 0.8),
        "erosion": (0.4, 0.8),
        "weirdness": (-1.0, 1.0),
        "depth": (-0.1, 0.1),
    },
}

def calculate_distance(point_a: dict, point_b: dict) -> float:
    keys = ["temperature", "humidity", "continentalness", "erosion", "weirdness", "depth"]
    sum_sq = 0.0
    for key in keys:
        val_a = point_a.get(key, 0.0)
        val_b = point_b.get(key, 0.0)
        if isinstance(val_b, tuple):
            min_val, max_val = val_b
            if val_a < min_val:
                diff = min_val - val_a
            elif val_a > max_val:
                diff = val_a - max_val
            else:
                diff = 0.0
        else:
            diff = val_a - val_b
        sum_sq += diff * diff
    return math.sqrt(sum_sq)