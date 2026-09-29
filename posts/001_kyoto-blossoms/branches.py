"""Procedural cherry branches: geometry only (drawing lives in canopy.py).

A branch is grown recursively: each limb bends a little as it goes, tapers,
and splits into a leader and an occasional side shoot. Seeded, so the tree
is identical on every render.

Coordinates are pixels (origin top-left, y down).
"""
import numpy as np
from matplotlib.path import Path as MPath
from matplotlib.transforms import Affine2D


def flower_marker(petal):
    """Five petals around a centre: a whole blossom, unlike the data petals."""
    parts = [Affine2D().scale(0.55).translate(0, 0.62).rotate_deg(a).transform_path(petal)
             for a in range(0, 360, 72)]
    return MPath.make_compound_path(*parts)


class Branch:
    def __init__(self, seed, allowed, bend=9, split=0.8):
        self.rng = np.random.default_rng(seed)
        self.allowed = allowed          # f(x, y) -> bool, keeps the tree in its zone
        self.bend = bend                # degrees of wander per step
        self.split = split              # chance of a side shoot
        self.segments, self.widths = [], []
        self.tips = []

    def grow(self, x, y, angle, length, width, depth):
        steps = 8
        for _ in range(steps):
            angle += self.rng.normal(0, self.bend)
            nx = x + np.cos(np.radians(angle)) * length / steps
            ny = y + np.sin(np.radians(angle)) * length / steps
            if not self.allowed(nx, ny):
                self.tips.append((x, y))
                return
            self.segments.append([(x, y), (nx, ny)])
            self.widths.append(width)
            x, y = nx, ny
            width *= 0.965
        if depth == 0 or width < 0.9:
            self.tips.append((x, y))
            return
        self.grow(x, y, angle + self.rng.normal(0, 12), length * 0.78, width * 0.8, depth - 1)
        if self.rng.random() < self.split:
            side = self.rng.choice([-1, 1]) * self.rng.uniform(25, 50)
            self.grow(x, y, angle + side, length * 0.6, width * 0.55, depth - 1)
