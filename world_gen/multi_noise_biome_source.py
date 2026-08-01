# world_gen/multi_noise_biome_source.py
from .multi_noise_sampler import MultiNoiseSampler
from .biome_params import BIOME_PARAMETERS, calculate_distance

class MultiNoiseBiomeSource:
    def __init__(self, seed: int, noise_gen):
        self.seed = seed
        self.noise_sampler = MultiNoiseSampler(noise_gen)

    def get_biome(self, x: int, y: int, z: int) -> int:
        point_params = self.noise_sampler.sample(x, y, z)
        best_biome = None
        best_distance = float('inf')
        for biome_id, ideal_params in BIOME_PARAMETERS.items():
            dist = calculate_distance(point_params, ideal_params)
            if dist < best_distance:
                best_distance = dist
                best_biome = biome_id
        return best_biome if best_biome is not None else 0