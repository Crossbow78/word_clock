"""
animations/matrix.py — Matrix rain
"""

import random
from .shared import COLS, ROWS, xy

FRAME_DELAY  = 0.06
NAME         = "Matrix Rain"

TRAIL_LENGTH  = 6
TRAIL_FALLOFF = [0.7, 0.45, 0.28, 0.15, 0.07, 0.03]
TRAIL_COLOR   = (0, 255, 0)
HEAD_COLOR    = (180, 255, 180)
RESPAWN_MIN   = 2
RESPAWN_MAX   = 20

class _Drop:
    def __init__(self, col, start_delay=0):
        self.col    = col
        self.row    = -start_delay
        self.active = True

    def step(self):
        self.row += 1
        if self.row - TRAIL_LENGTH >= ROWS:
            self.active = False

    def draw(self, buf):
        if 0 <= self.row < ROWS:
            buf[self.col][self.row] = HEAD_COLOR
        for t, factor in enumerate(TRAIL_FALLOFF):
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
    _drops = [_Drop(col, start_delay=random.randint(0, ROWS + TRAIL_LENGTH))
              for col in range(COLS)]

def frame(pixels, dt):
    buf = [[(0, 0, 0)] * ROWS for _ in range(COLS)]
    for drop in _drops:
        drop.draw(buf)
        drop.step()
    for i, drop in enumerate(_drops):
        if not drop.active:
            _drops[i] = _Drop(drop.col, start_delay=random.randint(RESPAWN_MIN, RESPAWN_MAX))
    for col in range(COLS):
        for row in range(ROWS):
            pixels[xy(col, row)] = buf[col][row]
    pixels.show()
