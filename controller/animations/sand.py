"""
animations/sand.py — Falling sand simulation (non-blocking state machine)
"""

import random
from .shared import COLS, ROWS, xy

FRAME_DELAY    = 0.04
NAME           = "Sand"

ROWS_EXTRA     = 4
ROWS_LOGICAL   = ROWS + ROWS_EXTRA
SPAWN_CHANCE   = 0.6
FADE_STEPS     = 20
FADE_DELAY     = 0.04
FULL_PAUSE     = 0.8
RAIN_START_ROW = ROWS_EXTRA

GRAIN_COLORS = [
    (220,180, 80),(200,160, 60),(240,200,100),(180,120, 40),
    (255,200, 80),( 80,160, 80),(160, 80, 40),(200,100, 60),
]

# ── State machine states ──────────────────────────────────────────────────────
# "filling"    → spawning and stepping grains each frame
# "full_pause" → grid is full, pause before fading
# "fading"     → fade out the grid
# "restarting" → brief gap before new cycle

_state       = "filling"
_accumulator = 0.0
_grid        = []
_falling     = []
_fade_step   = 0
_snapshot    = []

# ── Grid helpers ──────────────────────────────────────────────────────────────

def _reset():
    global _grid, _falling
    _grid    = [[None]*COLS for _ in range(ROWS_LOGICAL)]
    _falling = []

def _is_empty(col, row):
    if col < 0 or col >= COLS or row < 0 or row >= ROWS_LOGICAL:
        return False
    return _grid[row][col] is None

def _grid_full():
    return all(_grid[ROWS_EXTRA][c] is not None for c in range(COLS))

class _Grain:
    def __init__(self, col, color):
        self.col    = col
        self.row    = 0
        self.color  = color
        self.active = True

    def step(self):
        r = self.row
        if _is_empty(self.col, r+1):
            self.row += 1
            return
        sides = [-1, 1]
        random.shuffle(sides)
        for dc in sides:
            if _is_empty(self.col+dc, r+1):
                self.col += dc
                self.row += 1
                return
        _grid[r][self.col] = self.color
        self.active = False

# ── Drawing ───────────────────────────────────────────────────────────────────

def _draw(pixels):
    for r in range(ROWS):
        lr = ROWS_EXTRA + r
        for c in range(COLS):
            pixels[xy(c, r)] = _grid[lr][c] or (0,0,0)
    for grain in _falling:
        vis_r = grain.row - ROWS_EXTRA
        if 0 <= grain.col < COLS and 0 <= vis_r < ROWS:
            pixels[xy(grain.col, vis_r)] = grain.color
    pixels.show()

# ── Init ──────────────────────────────────────────────────────────────────────

def init():
    global _state, _accumulator
    _reset()
    _state       = "filling"
    _accumulator = 0.0

# ── Frame ─────────────────────────────────────────────────────────────────────

def frame(pixels, dt):
    global _state, _accumulator, _falling, _fade_step, _snapshot

    _accumulator += dt

    if _state == "filling":
        # Spawn a new grain
        if random.random() < SPAWN_CHANCE:
            col = random.randint(4, 7)
            if _grid[0][col] is None:
                _falling.append(_Grain(col, random.choice(GRAIN_COLORS)))

        # Step all active grains
        for grain in _falling:
            if grain.active:
                grain.step()
        _falling = [g for g in _falling if g.active]

        _draw(pixels)

        if _grid_full():
            _snapshot    = [[(_grid[ROWS_EXTRA+r][c] or (0,0,0)) for c in range(COLS)] for r in range(ROWS)]
            _state       = "full_pause"
            _accumulator = 0.0

    elif _state == "full_pause":
        if _accumulator >= FULL_PAUSE:
            _fade_step   = 0
            _state       = "fading"
            _accumulator = 0.0

    elif _state == "fading":
        if _accumulator < FADE_DELAY:
            return
        _accumulator = 0.0
        f = max(0.0, 1.0 - _fade_step / FADE_STEPS)
        for r in range(ROWS):
            for c in range(COLS):
                pixels[xy(c, r)] = tuple(int(v*f) for v in _snapshot[r][c])
        pixels.show()
        _fade_step += 1
        if _fade_step > FADE_STEPS:
            _state       = "restarting"
            _accumulator = 0.0

    elif _state == "restarting":
        if _accumulator >= 0.4:
            _reset()
            _state       = "filling"
            _accumulator = 0.0
