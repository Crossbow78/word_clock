"""
animations/plasma.py — Overlapping sine wave plasma
"""

import math
from .shared import COLS, ROWS, xy, hsv_to_rgb

FRAME_DELAY = 0.04
NAME        = "Plasma"

TIME_SCALE  = 0.05
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
    for col in range(COLS):
        for row in range(ROWS):
            nx   = col / COLS * math.pi * 2
            ny   = row / ROWS * math.pi * 2
            dist = math.sqrt((col - _cx)**2 + (row - _cy)**2)
            nd   = dist / math.sqrt(_cx**2 + _cy**2) * math.pi
            v1   = math.sin(nx * FREQ_1 + _t)
            v2   = math.sin(ny * FREQ_3 + _t * 0.7)
            v3   = math.sin((nx * FREQ_4 + ny * FREQ_4) + _t * 0.5)
            v4   = math.sin(nd * FREQ_2 - _t * 0.8)
            hue  = ((v1 + v2 + v3 + v4) / 4 + 1) / 2
            pixels[xy(col, row)] = hsv_to_rgb(hue)
    pixels.show()
    _t += TIME_SCALE
