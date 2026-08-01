# world_gen/noise.py
import math
import random

class PerlinNoise3D:
    def __init__(self, seed=0):
        random.seed(seed)
        self.perm = list(range(256))
        random.shuffle(self.perm)
        self.perm += self.perm

    def fade(self, t):
        return t*t*t*(t*(t*6-15)+10)

    def lerp(self, t, a, b):
        return a + t*(b-a)

    def grad(self, h, x, y, z):
        h &= 15
        u = x if h<8 else y
        v = y if h<4 else (x if h in (12,14) else z)
        return (u if (h&1)==0 else -u) + (v if (h&2)==0 else -v)

    def noise3d(self, x, y, z):
        X = int(math.floor(x)) & 255
        Y = int(math.floor(y)) & 255
        Z = int(math.floor(z)) & 255
        x -= math.floor(x)
        y -= math.floor(y)
        z -= math.floor(z)
        u = self.fade(x)
        v = self.fade(y)
        w = self.fade(z)
        A = self.perm[X] + Y
        AA = self.perm[A] + Z
        AB = self.perm[A+1] + Z
        B = self.perm[X+1] + Y
        BA = self.perm[B] + Z
        BB = self.perm[B+1] + Z
        return self.lerp(w,
            self.lerp(v,
                self.lerp(u, self.grad(self.perm[AA], x,y,z), self.grad(self.perm[BA], x-1,y,z)),
                self.lerp(u, self.grad(self.perm[AB], x,y-1,z), self.grad(self.perm[BB], x-1,y-1,z))
            ),
            self.lerp(v,
                self.lerp(u, self.grad(self.perm[AA+1], x,y,z-1), self.grad(self.perm[BA+1], x-1,y,z-1)),
                self.lerp(u, self.grad(self.perm[AB+1], x,y-1,z-1), self.grad(self.perm[BB+1], x-1,y-1,z-1))
            )
        )

    def noise2d(self, x, z):
        return self.noise3d(x, 0.0, z)