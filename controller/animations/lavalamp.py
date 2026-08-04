"""
animations/lavalamp.py — Gaussian blob lava lamp
"""

import math
import random
from .shared import COLS, ROWS, xy, INT, FLOAT, make_param_store

FRAME_DELAY = 0.05
NAME        = "Lava Lamp"

PARAMS = [
    ("num_blobs",   INT(1, 10),      5),      # blob count (takes effect on next init/reactivate)
    ("blob_radius", FLOAT(0.8, 5.0), 2.2),    # blob size
    ("time_scale",  FLOAT(0.002, 0.08), 0.015),  # drift speed
]
_params, get_params, set_param = make_param_store(PARAMS)

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
        radius = _params["blob_radius"]
        d  = ((col-cx)/radius)**2 + ((row-cy)/radius)**2
        return math.exp(-d)

_blobs = []
_t     = 0.0

def init():
    global _blobs, _t
    _blobs = [_Blob() for _ in range(_params["num_blobs"])]
    _t     = 0.0

def _reconcile_blob_count():
    """Grow/shrink _blobs to match the live param without disturbing
    existing blobs — so changing num_blobs doesn't reset ones already
    mid-drift, and no mode switch is needed for it to take effect."""
    target = _params["num_blobs"]
    while len(_blobs) < target:
        _blobs.append(_Blob())
    while len(_blobs) > target:
        _blobs.pop()

def frame(pixels, dt):
    global _t
    _reconcile_blob_count()
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
    _t += _params["time_scale"]
