"""
animations/shared.py

Shared utilities available to all animation modules.
Imported once by the controller and passed into each module via init().
"""

import math

# ── Grid dimensions ───────────────────────────────────────────────────────────

COLS = 12
ROWS = 11
LED_COUNT = COLS * ROWS   # 132

# ── Coordinate mapping ────────────────────────────────────────────────────────

def xy(col, row):
    """
    Map (col, row) in code-space to a physical pixel index.
      col: 0 = left,  11 = right
      row: 0 = top,   10 = bottom  (y increases downward)
    Physical wiring: horizontal zig-zag, row 0 (physical bottom) goes right→left.
    """
    physical_row = ROWS - 1 - row
    if physical_row % 2 == 0:
        return physical_row * COLS + (COLS - 1 - col)
    else:
        return physical_row * COLS + col

# ── Colour helpers ────────────────────────────────────────────────────────────

def hsv_to_rgb(h, s=1.0, v=1.0):
    h = h % 1.0
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v*(1-s), v*(1-f*s), v*(1-(1-f)*s)
    r, g, b = [(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)][i % 6]
    return int(r*255), int(g*255), int(b*255)

def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def scale(color, factor):
    return tuple(int(c * max(0.0, min(1.0, factor))) for c in color)
