"""
animations/ripple.py — Expanding colour ripples
"""

import math
import random
from .shared import COLS, ROWS, xy, INT, FLOAT, make_param_store

FRAME_DELAY  = 0.05
NAME         = "Ripple"

PARAMS = [
    ("max_ripples",  INT(1, 10),        5),      # how many ripples can be alive at once
    ("spawn_chance", FLOAT(0.0, 1.0),   0.1),    # chance per frame to spawn a new one
    ("ripple_speed", FLOAT(0.1, 2.0),   0.4),    # radius growth per frame
    ("ring_width",   FLOAT(0.3, 3.0),   1.5),    # thickness of each ring
]
_params, get_params, set_param = make_param_store(PARAMS)

MAX_RADIUS   = math.sqrt(COLS**2 + ROWS**2)

RIPPLE_COLORS = [
    (  0, 180, 255),
    (  0, 255, 120),
    (180,   0, 255),
    (255, 100,   0),
    (255,   0, 100),
    (  0, 120, 255),
]

class _Ripple:
    def __init__(self):
        self.cx     = random.uniform(0, COLS - 1)
        self.cy     = random.uniform(0, ROWS - 1)
        self.radius = 0.0
        self.color  = random.choice(RIPPLE_COLORS)
        self.active = True

    def step(self):
        self.radius += _params["ripple_speed"]
        if self.radius - _params["ring_width"] > MAX_RADIUS:
            self.active = False

    def contribution(self, col, row):
        ring_width = _params["ring_width"]
        dist  = math.sqrt((col - self.cx)**2 + (row - self.cy)**2)
        delta = abs(dist - self.radius)
        if delta > ring_width:
            return 0.0
        brightness = (1 + math.cos(math.pi * delta / ring_width)) / 2
        age_fade   = max(0.0, 1.0 - self.radius / MAX_RADIUS)
        return brightness * age_fade

_ripples = []

def init():
    global _ripples
    _ripples = [_Ripple()]

def frame(pixels, dt):
    global _ripples
    if len(_ripples) < _params["max_ripples"] and random.random() < _params["spawn_chance"]:
        _ripples.append(_Ripple())
    for col in range(COLS):
        for row in range(ROWS):
            r = g = b = 0.0
            for ripple in _ripples:
                br = ripple.contribution(col, row)
                if br > 0:
                    r += ripple.color[0] * br
                    g += ripple.color[1] * br
                    b += ripple.color[2] * br
            pixels[xy(col, row)] = (min(255, int(r)), min(255, int(g)), min(255, int(b)))
    pixels.show()
    for ripple in _ripples:
        ripple.step()
    _ripples = [r for r in _ripples if r.active]
