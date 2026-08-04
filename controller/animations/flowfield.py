"""
animations/flowfield.py — Perlin noise flow field
"""

import math
import random
from noise import pnoise3
from .shared import COLS, ROWS, xy, hsv_to_rgb, INT, FLOAT, CHOICE, make_param_store

FRAME_DELAY    = 0.05
NAME           = "Flow Field"

PARAMS = [
    ("num_particles",  INT(5, 60),        20),    # particle count (applies live, existing particles untouched)
    ("particle_speed", FLOAT(0.05, 1.0),  0.35),  # how fast particles travel
    ("trail_decay",    FLOAT(0.05, 0.5),  0.18),  # how quickly trails fade — higher = shorter trails
    ("spatial_scale",  FLOAT(0.05, 1.0),  0.35),  # noise turbulence — higher = choppier flow
    ("time_scale",     FLOAT(0.001, 0.05), 0.008), # how fast the flow field itself evolves
    ("max_lifetime",   INT(20, 400),      120),   # longest a particle can live before respawning
    ("color_mode",     CHOICE(["fixed", "direction", "age"]), "fixed"),
]
_params, get_params, set_param = make_param_store(PARAMS)

_buf = [[[0.0, 0.0, 0.0] for _ in range(COLS)] for _ in range(ROWS)]
_t   = 0.0

def _buf_decay():
    decay = _params["trail_decay"]
    for r in range(ROWS):
        for c in range(COLS):
            _buf[r][c][0] *= (1.0 - decay)
            _buf[r][c][1] *= (1.0 - decay)
            _buf[r][c][2] *= (1.0 - decay)

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
        max_lifetime  = _params["max_lifetime"]
        self.lifetime = random.randint(max_lifetime//2, max_lifetime)

    def step(self, t):
        n     = pnoise3(self.x*_params["spatial_scale"], self.y*_params["spatial_scale"], t,
                        octaves=2, persistence=0.5, lacunarity=2.0)
        angle = n * math.pi * 4
        if _params["color_mode"] == "direction":
            hue = (angle / (math.pi*2)) % 1.0
        elif _params["color_mode"] == "age":
            hue = (self.age / self.lifetime) % 1.0
        else:
            hue = self.hue
        age_factor = min(self.age/10, 1.0) * min((self.lifetime-self.age)/10, 1.0)
        r, g, b    = hsv_to_rgb(hue, s=0.9, v=1.0)
        color      = (r/255*age_factor, g/255*age_factor, b/255*age_factor)
        _buf_add(self.x, self.y, color, strength=0.6)
        self.x   += math.cos(angle) * _params["particle_speed"]
        self.y   += math.sin(angle) * _params["particle_speed"]
        self.age += 1
        if (self.x < 0 or self.x >= COLS or
            self.y < 0 or self.y >= ROWS or
            self.age >= self.lifetime):
            self.respawn()

_particles = []

def init():
    global _particles, _t
    _particles = [_Particle() for _ in range(_params["num_particles"])]
    for p in _particles:
        p.age = random.randint(0, p.lifetime)
    _t = 0.0

def _reconcile_particle_count():
    """Grow/shrink _particles to match the live param without disturbing
    particles already mid-flight — so changing num_particles doesn't reset
    the flow field, and no mode switch is needed for it to take effect."""
    target = _params["num_particles"]
    while len(_particles) < target:
        p = _Particle()
        p.age = random.randint(0, p.lifetime)   # blend in rather than pop in at age 0
        _particles.append(p)
    while len(_particles) > target:
        _particles.pop()

def frame(pixels, dt):
    global _t
    _reconcile_particle_count()
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
    _t += _params["time_scale"]
