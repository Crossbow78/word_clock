"""
animations/ripple.py — Expanding colour ripples
"""

import math
import random
from .shared import COLS, ROWS, xy

FRAME_DELAY  = 0.05
NAME         = "Ripple"

MAX_RIPPLES  = 4
SPAWN_CHANCE = 0.08
RIPPLE_SPEED = 0.4
RING_WIDTH   = 1.2
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
        self.radius += RIPPLE_SPEED
        if self.radius - RING_WIDTH > MAX_RADIUS:
            self.active = False

    def contribution(self, col, row):
        dist  = math.sqrt((col - self.cx)**2 + (row - self.cy)**2)
        delta = abs(dist - self.radius)
        if delta > RING_WIDTH:
            return 0.0
        brightness = (1 + math.cos(math.pi * delta / RING_WIDTH)) / 2
        age_fade   = max(0.0, 1.0 - self.radius / MAX_RADIUS)
        return brightness * age_fade

_ripples = []

def init():
    global _ripples
    _ripples = [_Ripple()]

def frame(pixels, dt):
    global _ripples
    if len(_ripples) < MAX_RIPPLES and random.random() < SPAWN_CHANCE:
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
