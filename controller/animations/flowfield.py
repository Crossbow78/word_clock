"""
animations/flowfield.py — Perlin noise flow field
"""

import math
import random
from noise import pnoise3
from .shared import COLS, ROWS, xy, hsv_to_rgb

FRAME_DELAY    = 0.05
NAME           = "Flow Field"

NUM_PARTICLES  = 20
PARTICLE_SPEED = 0.35
TRAIL_DECAY    = 0.18
SPATIAL_SCALE  = 0.35
TIME_SCALE     = 0.008
MAX_LIFETIME   = 120
COLOR_MODE     = "fixed"   # "direction", "age", or "fixed"

_buf = [[[0.0, 0.0, 0.0] for _ in range(COLS)] for _ in range(ROWS)]
_t   = 0.0

def _buf_decay():
    for r in range(ROWS):
        for c in range(COLS):
            _buf[r][c][0] *= (1.0 - TRAIL_DECAY)
            _buf[r][c][1] *= (1.0 - TRAIL_DECAY)
            _buf[r][c][2] *= (1.0 - TRAIL_DECAY)

def _buf_add(col, row, color, strength=1.0):
    x0, y0 = int(col), int(row)
    dx, dy  = col-x0, row-y0
    for dc in range(2):
        for dr in range(2):
            c, r = x0+dc, y0+dr
            if 0 <= c < COLS and 0 <= r < ROWS:
                wx = (1-dx if dc==0 else dx)
                wy = (1-dy if dr==0 else dy)
                w  = wx * wy * strength
                _buf[r][c][0] = min(1.0, _buf[r][c][0] + color[0]*w)
                _buf[r][c][1] = min(1.0, _buf[r][c][1] + color[1]*w)
                _buf[r][c][2] = min(1.0, _buf[r][c][2] + color[2]*w)

class _Particle:
    def __init__(self):
        self.respawn()

    def respawn(self):
        self.x        = random.uniform(0, COLS-1)
        self.y        = random.uniform(0, ROWS-1)
        self.age      = 0
        self.hue      = random.random()
        self.lifetime = random.randint(MAX_LIFETIME//2, MAX_LIFETIME)

    def step(self, t):
        n     = pnoise3(self.x*SPATIAL_SCALE, self.y*SPATIAL_SCALE, t,
                        octaves=2, persistence=0.5, lacunarity=2.0)
        angle = n * math.pi * 4
        if COLOR_MODE == "direction":
            hue = (angle / (math.pi*2)) % 1.0
        elif COLOR_MODE == "age":
            hue = (self.age / self.lifetime) % 1.0
        else:
            hue = self.hue
        age_factor = min(self.age/10, 1.0) * min((self.lifetime-self.age)/10, 1.0)
        r, g, b    = hsv_to_rgb(hue, s=0.9, v=1.0)
        color      = (r/255*age_factor, g/255*age_factor, b/255*age_factor)
        _buf_add(self.x, self.y, color, strength=0.6)
        self.x   += math.cos(angle) * PARTICLE_SPEED
        self.y   += math.sin(angle) * PARTICLE_SPEED
        self.age += 1
        if (self.x < 0 or self.x >= COLS or
            self.y < 0 or self.y >= ROWS or
            self.age >= self.lifetime):
            self.respawn()

_particles = []

def init():
    global _particles, _t
    _particles = [_Particle() for _ in range(NUM_PARTICLES)]
    for p in _particles:
        p.age = random.randint(0, p.lifetime)
    _t = 0.0

def frame(pixels, dt):
    global _t
    _buf_decay()
    for p in _particles:
        p.step(_t)
    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = (
                int(min(1.0, _buf[r][c][0]) * 255),
                int(min(1.0, _buf[r][c][1]) * 255),
                int(min(1.0, _buf[r][c][2]) * 255),
            )
    pixels.show()
    _t += TIME_SCALE
