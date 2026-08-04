"""
animations/matrix.py — Matrix rain
"""

import random
from .shared import COLS, ROWS, xy, INT, make_param_store

FRAME_DELAY  = 0.06
NAME         = "Matrix Rain"

PARAMS = [
    ("trail_length", INT(1, 6),  6),    # visible trail length (capped by TRAIL_FALLOFF size)
    ("respawn_min",  INT(0, 60), 2),    # shortest blank gap before a column respawns
    ("respawn_max",  INT(1, 80), 20),   # longest blank gap before a column respawns
]
_params, get_params, set_param = make_param_store(PARAMS)

TRAIL_FALLOFF = [0.7, 0.45, 0.28, 0.15, 0.07, 0.03]
TRAIL_COLOR   = (0, 255, 0)
HEAD_COLOR    = (180, 255, 180)

class _Drop:
    def __init__(self, col, start_delay=0):
        self.col    = col
        self.row    = -start_delay
        self.active = True

    def step(self):
        self.row += 1
        if self.row - _params["trail_length"] >= ROWS:
            self.active = False

    def draw(self, buf):
        if 0 <= self.row < ROWS:
            buf[self.col][self.row] = HEAD_COLOR
        visible = min(_params["trail_length"], len(TRAIL_FALLOFF))
        for t in range(visible):
            factor = TRAIL_FALLOFF[t]
            trail_row = self.row - 1 - t
            if 0 <= trail_row < ROWS:
                ex = buf[self.col][trail_row]
                buf[self.col][trail_row] = (
                    min(255, ex[0] + int(TRAIL_COLOR[0] * factor)),
                    min(255, ex[1] + int(TRAIL_COLOR[1] * factor)),
                    min(255, ex[2] + int(TRAIL_COLOR[2] * factor)),
                )

_drops = []

def init():
    global _drops
    _drops = [_Drop(col, start_delay=random.randint(0, ROWS + _params["trail_length"]))
              for col in range(COLS)]

def frame(pixels, dt):
    buf = [[(0, 0, 0)] * ROWS for _ in range(COLS)]
    for drop in _drops:
        drop.draw(buf)
        drop.step()
    lo = min(_params["respawn_min"], _params["respawn_max"])
    hi = max(_params["respawn_min"], _params["respawn_max"])
    for i, drop in enumerate(_drops):
        if not drop.active:
            _drops[i] = _Drop(drop.col, start_delay=random.randint(lo, hi))
    for col in range(COLS):
        for row in range(ROWS):
            pixels[xy(col, row)] = buf[col][row]
    pixels.show()
