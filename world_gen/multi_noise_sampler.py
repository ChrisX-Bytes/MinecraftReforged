# world_gen/multi_noise_sampler.py
from .noise import PerlinNoise3D

class MultiNoiseSampler:
    def __init__(self, noise_gen: PerlinNoise3D):
        self.noise = noise_gen

    def sample(self, x: int, y: int, z: int) -> dict:
        return {
            "temperature": self.noise.noise2d(x * 0.005, z * 0.005),
            "humidity": self.noise.noise2d(x * 0.005 + 1000, z * 0.005 + 1000),
            "continentalness": self.noise.noise2d(x * 0.005, z * 0.005),
            "erosion": self.noise.noise2d(x * 0.005 + 2000, z * 0.005 + 2000),
            "weirdness": self.noise.noise2d(x * 0.005 + 3000, z * 0.005 + 3000),
            "depth": 0.0,
        }