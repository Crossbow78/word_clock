"""
animations/life.py — Conway's Game of Life
"""

import random
from .shared import COLS, ROWS, xy

FRAME_DELAY      = 0.15
NAME             = "Game of Life"

SEED_DENSITY     = 0.4
MAX_AGE          = 8
STAGNATION_LIMIT = 8

AGE_COLORS = [
    (180, 255, 180),
    ( 80, 255,  80),
    (  0, 220,   0),
    (  0, 180,   0),
    (  0, 140,   0),
    (  0, 100,   0),
    (  0,  60,   0),
    (  0,  30,   0),
]

def _make_grid():
    return [[1 if random.random() < SEED_DENSITY else 0
             for _ in range(COLS)] for _ in range(ROWS)]

def _count_neighbours(grid, row, col):
    count = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            count += grid[(row+dr) % ROWS][(col+dc) % COLS] > 0
    return count

def _next_generation(grid):
    new = [[0]*COLS for _ in range(ROWS)]
    for r in range(ROWS):
        for c in range(COLS):
            n     = _count_neighbours(grid, r, c)
            alive = grid[r][c] > 0
            if alive and n in (2, 3):
                new[r][c] = min(grid[r][c] + 1, MAX_AGE)
            elif not alive and n == 3:
                new[r][c] = 1
    return new

def _population(grid):
    return sum(grid[r][c] > 0 for r in range(ROWS) for c in range(COLS))

def _grids_equal(a, b):
    return all(a[r][c] == b[r][c] for r in range(ROWS) for c in range(COLS))

_grid       = []
_prev_grid  = None
_stagnation = 0

def init():
    global _grid, _prev_grid, _stagnation
    _grid       = _make_grid()
    _prev_grid  = None
    _stagnation = 0

def frame(pixels, dt):
    global _grid, _prev_grid, _stagnation
    for r in range(ROWS):
        for c in range(COLS):
            age = _grid[r][c]
            color = AGE_COLORS[min(age-1, len(AGE_COLORS)-1)] if age > 0 else (0, 0, 0)
            pixels[xy(c, r)] = color
    pixels.show()

    next_grid = _next_generation(_grid)

    if _prev_grid and _grids_equal(next_grid, _grid):
        _stagnation += 1
    else:
        _stagnation = 0
    _prev_grid = _grid

    if _population(next_grid) == 0 or _stagnation >= STAGNATION_LIMIT:
        next_grid   = _make_grid()
        _stagnation = 0

    _grid = next_grid
