"""
animations/plasma.py — Overlapping sine wave plasma
"""

import math
from .shared import COLS, ROWS, xy, hsv_to_rgb, FLOAT, make_param_store

FRAME_DELAY = 0.04
NAME        = "Plasma"

PARAMS = [
    ("time_scale", FLOAT(0.005, 0.3), 0.05),   # how fast the pattern evolves
    ("freq_scale", FLOAT(0.3, 3.0),   1.0),    # multiplies all wave frequencies — higher = busier
]
_params, get_params, set_param = make_param_store(PARAMS)

FREQ_1      = 1.0
FREQ_2      = 0.8
FREQ_3      = 1.2
FREQ_4      = 0.6

_t  = 0.0
_cx = (COLS - 1) / 2
_cy = (ROWS - 1) / 2

def init():
    global _t
    _t = 0.0

def frame(pixels, dt):
    global _t
    fs = _params["freq_scale"]
    for col in range(COLS):
        for row in range(ROWS):
            nx   = col / COLS * math.pi * 2
            ny   = row / ROWS * math.pi * 2
            dist = math.sqrt((col - _cx)**2 + (row - _cy)**2)
            nd   = dist / math.sqrt(_cx**2 + _cy**2) * math.pi
            v1   = math.sin(nx * FREQ_1 * fs + _t)
            v2   = math.sin(ny * FREQ_3 * fs + _t * 0.7)
            v3   = math.sin((nx * FREQ_4 * fs + ny * FREQ_4 * fs) + _t * 0.5)
            v4   = math.sin(nd * FREQ_2 * fs - _t * 0.8)
            hue  = ((v1 + v2 + v3 + v4) / 4 + 1) / 2
            pixels[xy(col, row)] = hsv_to_rgb(hue)
    pixels.show()
    _t += _params["time_scale"]
