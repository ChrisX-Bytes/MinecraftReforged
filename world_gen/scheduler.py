# world_gen/scheduler.py
# Bucket-based scheduled tick manager (circular buckets).
# schedule(pos, delay) -> pos is tuple (wx,wy,wz). delay is integer >=0.
# tick() advances to next bucket and returns the set of positions scheduled for this tick.

from collections import defaultdict

class ScheduledTickManager:
    def __init__(self, num_buckets=512):
        # num_buckets should be larger than max expected delay (e.g., 512)
        self.num_buckets = int(num_buckets)
        self.buckets = [set() for _ in range(self.num_buckets)]
        self.current = 0

    def schedule(self, pos, delay):
        """Schedule pos to be processed after `delay` ticks."""
        if delay < 0:
            delay = 0
        idx = (self.current + (delay % self.num_buckets)) % self.num_buckets
        self.buckets[idx].add(tuple(pos))

    def tick(self):
        """Advance one tick and return positions scheduled for this tick (as a set)."""
        items = self.buckets[self.current]
        self.buckets[self.current] = set()
        self.current = (self.current + 1) % self.num_buckets
        return items

# Provide a module-level scheduler instance for easy import/use.
scheduler = ScheduledTickManager()