"""
animations/balls.py — Bouncing coloured balls with trails
"""

import math
import random
from .shared import COLS, ROWS, xy, INT, FLOAT, make_param_store

FRAME_DELAY   = 0.05
NAME          = "Bouncing Balls"

PARAMS = [
    ("num_balls", INT(2, 15),     6),    # ball count (takes effect on next init/reactivate)
    ("speed_min", FLOAT(0.1, 2.0), 0.4), # slowest possible ball speed (new balls only)
    ("speed_max", FLOAT(0.1, 3.0), 0.9), # fastest possible ball speed (new balls only)
]
_params, get_params, set_param = make_param_store(PARAMS)

TRAIL_FALLOFF = [1.0, 0.45, 0.18, 0.06]

BALL_COLORS = [
    (255,40,40),(255,160,0),(220,220,0),(0,220,0),
    (0,180,255),(60,60,255),(200,0,255),(255,0,160),
    (0,220,180),(255,220,0),
]

class _Ball:
    def __init__(self):
        self.x     = random.uniform(0, COLS-1)
        self.y     = random.uniform(0, ROWS-1)
        angle      = random.uniform(0, math.pi*2)
        lo, hi     = sorted((_params["speed_min"], _params["speed_max"]))
        speed      = random.uniform(lo, hi)
        self.vx    = math.cos(angle) * speed
        self.vy    = math.sin(angle) * speed
        self.color = random.choice(BALL_COLORS)
        self.trail = []

    def step(self):
        self.trail.insert(0, (self.x, self.y))
        if len(self.trail) > len(TRAIL_FALLOFF):
            self.trail.pop()
        self.x += self.vx
        self.y += self.vy
        if self.x < 0:
            self.x = -self.x; self.vx = abs(self.vx)
        elif self.x > COLS-1:
            self.x = 2*(COLS-1)-self.x; self.vx = -abs(self.vx)
        if self.y < 0:
            self.y = -self.y; self.vy = abs(self.vy)
        elif self.y > ROWS-1:
            self.y = 2*(ROWS-1)-self.y; self.vy = -abs(self.vy)

    def _paint(self, buf, fx, fy, factor):
        x0, y0 = int(fx), int(fy)
        dx, dy  = fx-x0, fy-y0
        for dc in range(2):
            for dr in range(2):
                c, r = x0+dc, y0+dr
                if 0 <= c < COLS and 0 <= r < ROWS:
                    wx = (1-dx if dc==0 else dx)
                    wy = (1-dy if dr==0 else dy)
                    w  = wx * wy * factor
                    buf[r][c] = (
                        min(255, buf[r][c][0] + int(self.color[0]*w)),
                        min(255, buf[r][c][1] + int(self.color[1]*w)),
                        min(255, buf[r][c][2] + int(self.color[2]*w)),
                    )

    def draw(self, buf):
        self._paint(buf, self.x, self.y, 1.0)
        for i, (tx, ty) in enumerate(self.trail):
            f = TRAIL_FALLOFF[i] if i < len(TRAIL_FALLOFF) else 0
            if f > 0:
                self._paint(buf, tx, ty, f)

_balls = []

def init():
    global _balls
    _balls = [_Ball() for _ in range(_params["num_balls"])]

def _reconcile_ball_count():
    """Grow/shrink _balls to match the live param without disturbing balls
    already in flight — so changing num_balls doesn't reset their
    positions/trails, and no mode switch is needed for it to take effect."""
    target = _params["num_balls"]
    while len(_balls) < target:
        _balls.append(_Ball())
    while len(_balls) > target:
        _balls.pop()

def frame(pixels, dt):
    _reconcile_ball_count()
    buf = [[(0,0,0)]*COLS for _ in range(ROWS)]
    for ball in _balls:
        ball.step()
        ball.draw(buf)
    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = buf[r][c]
    pixels.show()
