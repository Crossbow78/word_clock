"""
animations/lavalamp.py — Gaussian blob lava lamp
"""

import math
import random
from .shared import COLS, ROWS, xy

FRAME_DELAY = 0.05
NAME        = "Lava Lamp"

NUM_BLOBS   = 5
BLOB_RADIUS = 2.2
TIME_SCALE  = 0.015
BG_COLOR    = (4, 0, 8)

BLOB_COLORS = [
    (255, 20,   0),
    (255, 80,   0),
    (220,  0, 100),
    (160,  0, 255),
    (255,140,   0),
    (200,  0,  60),
    (255, 40, 120),
]

class _Blob:
    def __init__(self):
        self.color   = random.choice(BLOB_COLORS)
        self.cx_base = random.uniform(1, COLS-2)
        self.cy_base = random.uniform(1, ROWS-2)
        self.ax      = random.uniform(1.5, COLS/2-1)
        self.ay      = random.uniform(1.0, ROWS/2-1)
        self.fx      = random.uniform(0.3, 1.0)
        self.fy      = random.uniform(0.3, 1.0)
        self.px      = random.uniform(0, math.pi*2)
        self.py      = random.uniform(0, math.pi*2)

    def brightness(self, col, row, t):
        cx = self.cx_base + self.ax * math.sin(t * self.fx + self.px)
        cy = self.cy_base + self.ay * math.sin(t * self.fy + self.py)
        d  = ((col-cx)/BLOB_RADIUS)**2 + ((row-cy)/BLOB_RADIUS)**2
        return math.exp(-d)

_blobs = []
_t     = 0.0

def init():
    global _blobs, _t
    _blobs = [_Blob() for _ in range(NUM_BLOBS)]
    _t     = 0.0

def frame(pixels, dt):
    global _t
    for col in range(COLS):
        for row in range(ROWS):
            r, g, b = BG_COLOR
            for blob in _blobs:
                bri = blob.brightness(col, row, _t)
                r  += blob.color[0] * bri
                g  += blob.color[1] * bri
                b  += blob.color[2] * bri
            pixels[xy(col, row)] = (min(255,int(r)), min(255,int(g)), min(255,int(b)))
    pixels.show()
    _t += TIME_SCALE
