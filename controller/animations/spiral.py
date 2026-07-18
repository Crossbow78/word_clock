"""
animations/spiral.py — Radar sweep spiral
"""

import math
from .shared import COLS, ROWS, xy, hsv_to_rgb

FRAME_DELAY    = 0.05
NAME           = "Spiral"

ROTATION_SPEED = 0.05
NUM_ARMS       = 3
ARM_WIDTH      = 0.4
TRAIL_DECAY    = 0.2
CYCLE_COLOR    = True
COLOR_SPEED    = 0.003
ARM_COLOR      = (0, 200, 255)
TIP_BOOST      = 1.5

_buf          = [[[0.0,0.0,0.0] for _ in range(COLS)] for _ in range(ROWS)]
_sweep_angle  = 0.0
_hue          = 0.0

_cx = (COLS-1) / 2.0
_cy = (ROWS-1) / 2.0
_max_dist = math.sqrt(_cx**2 + _cy**2)

_cell_angle = [[math.atan2(r - _cy, c - _cx) for c in range(COLS)] for r in range(ROWS)]
_cell_dist  = [[math.sqrt((c-_cx)**2 + (r-_cy)**2) for c in range(COLS)] for r in range(ROWS)]

def _angle_diff(a, b):
    d = (a - b) % (math.pi*2)
    if d > math.pi: d -= math.pi*2
    return d

def init():
    global _sweep_angle, _hue
    _sweep_angle = 0.0
    _hue         = 0.0
    for r in range(ROWS):
        for c in range(COLS):
            _buf[r][c] = [0.0, 0.0, 0.0]

def frame(pixels, dt):
    global _sweep_angle, _hue
    for r in range(ROWS):
        for c in range(COLS):
            _buf[r][c][0] *= (1.0 - TRAIL_DECAY)
            _buf[r][c][1] *= (1.0 - TRAIL_DECAY)
            _buf[r][c][2] *= (1.0 - TRAIL_DECAY)

    if CYCLE_COLOR:
        cr, cg, cb = hsv_to_rgb(_hue)
        color = (cr/255, cg/255, cb/255)
    else:
        color = tuple(v/255 for v in ARM_COLOR)

    for arm in range(NUM_ARMS):
        arm_angle = (_sweep_angle + arm * math.pi*2/NUM_ARMS) % (math.pi*2)
        for r in range(ROWS):
            for c in range(COLS):
                diff = abs(_angle_diff(_cell_angle[r][c], arm_angle))
                if diff < ARM_WIDTH:
                    af       = (1 + math.cos(math.pi*diff/ARM_WIDTH)) / 2
                    df       = _cell_dist[r][c] / _max_dist
                    boost    = 1.0 + (TIP_BOOST-1.0) * df
                    strength = af * df * boost
                    _buf[r][c][0] = min(1.0, _buf[r][c][0] + color[0]*strength)
                    _buf[r][c][1] = min(1.0, _buf[r][c][1] + color[1]*strength)
                    _buf[r][c][2] = min(1.0, _buf[r][c][2] + color[2]*strength)

    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = (
                int(min(1.0,_buf[r][c][0])*255),
                int(min(1.0,_buf[r][c][1])*255),
                int(min(1.0,_buf[r][c][2])*255),
            )
    pixels.show()
    _sweep_angle = (_sweep_angle + ROTATION_SPEED) % (math.pi*2)
    _hue         = (_hue + COLOR_SPEED) % 1.0
