"""
animations/fire.py — 2D Perlin noise fire

Hot bright yellow at the bottom, cooling through orange and red
toward dark embers at the top. Each column simmers independently
via 2D Perlin noise (position × time).

Dependencies: noise
"""

import math
from noise import pnoise2
from .shared import COLS, ROWS, xy

FRAME_DELAY    = 0.05
NAME           = "Fire"

# How fast the fire evolves
TIME_SCALE     = 0.08

# Spatial turbulence — lower = smoother, higher = choppier
SPATIAL_SCALE  = 0.1

OCTAVES        = 2
PERSISTENCE    = 1.5
LACUNARITY     = 2.0

# Gamma > 1 deepens the dark gaps between flames
GAMMA          = 2.8

# Colour palette: (threshold 0–1, (R, G, B))
# 0.0 = coldest (top), 1.0 = hottest (bottom)
FIRE_PALETTE = [
    (0.00, (  0,   0,   0)),   # black
    (0.21, ( 60,   0,   0)),   # deep red ember
    (0.40, (160,  10,   0)),   # red
    (0.58, (220,  60,   0)),   # orange-red
    (0.72, (255, 130,   0)),   # orange
    (0.84, (255, 200,  20)),   # amber
    (0.95, (255, 200, 160)),   # hot yellow-white core
    (1.00, (255, 255, 235)),   # bright white core
]

_t = 0.0

def _palette(intensity):
    intensity = max(0.0, min(1.0, intensity))
    for i in range(len(FIRE_PALETTE) - 1):
        t0, c0 = FIRE_PALETTE[i]
        t1, c1 = FIRE_PALETTE[i + 1]
        if t0 <= intensity <= t1:
            t = (intensity - t0) / (t1 - t0)
            return tuple(int(c0[j] + (c1[j] - c0[j]) * t) for j in range(3))
    return FIRE_PALETTE[-1][1]

def init():
    global _t
    _t = 0.0

def frame(pixels, dt):
    global _t
    for col in range(COLS):
        for row in range(ROWS):
            # Sample Perlin noise: x = column, y = time
            raw = pnoise2(
                col * SPATIAL_SCALE,
                _t + row * SPATIAL_SCALE * 0.5,
                octaves=OCTAVES,
                persistence=PERSISTENCE,
                lacunarity=LACUNARITY,
            )
            # Remap noise (-0.7..0.7) to 0–1
            intensity = (raw + 0.7) / 1.4

            # Apply gamma for punchier contrast
            intensity = intensity ** GAMMA

            # Cooling gradient: row 0 = top (cold), row ROWS-1 = bottom (hot)
            # Invert so heat rises from the bottom
            heat = row / (ROWS - 1)   # 0 at top, 1 at bottom
            # Scale noise by heat so the bottom is always bright
            # and the top can only reach a dim ember at best
            intensity = intensity * 0.5 + heat * 0.6

            pixels[xy(col, row)] = _palette(intensity)

    pixels.show()
    _t += TIME_SCALE
