"""
animations/tetris_ai.py — Tetris with greedy heuristic AI (non-blocking state machine)
"""

import time
import random
import copy
from .shared import COLS, ROWS, xy

FRAME_DELAY      = 0.03
NAME             = "Tetris AI"

FALL_DELAY       = 0.10
SLIDE_DELAY      = 0.10
ROTATE_DELAY     = 0.12
LOCK_PAUSE       = 0.15
CLEAR_FLASH_TIME = 0.08
FLASH_COUNT      = 2
FADE_STEPS       = 24
FADE_DELAY       = 0.04

AI_IMPERFECTION  = 0.0

W_LINES_CLEARED  =  8.0
W_AGG_HEIGHT     = -0.5
W_HOLES          = -7.0
W_BUMPINESS      = -0.4

RAW_PIECES = [
    [[(0,0),(1,0),(2,0),(3,0)], [(0,0),(0,1),(0,2),(0,3)]],
    [[(0,0),(1,0),(0,1),(1,1)]],
    [[(0,0),(1,0),(2,0),(1,1)], [(0,0),(0,1),(1,1),(0,2)],
     [(1,0),(0,1),(1,1),(2,1)], [(1,0),(0,1),(1,1),(1,2)]],
    [[(1,0),(2,0),(0,1),(1,1)], [(0,0),(0,1),(1,1),(1,2)]],
    [[(0,0),(1,0),(1,1),(2,1)], [(1,0),(0,1),(1,1),(0,2)]],
    [[(0,0),(0,1),(0,2),(1,2)], [(0,0),(1,0),(2,0),(0,1)],
     [(0,0),(1,0),(1,1),(1,2)], [(2,0),(0,1),(1,1),(2,1)]],
    [[(1,0),(1,1),(0,2),(1,2)], [(0,0),(0,1),(1,1),(2,1)],
     [(0,0),(1,0),(0,1),(0,2)], [(0,0),(1,0),(2,0),(2,1)]],
]

# ── State machine states ──────────────────────────────────────────────────────
# "spawning"  → pick new piece, compute AI target
# "rotating"  → rotate piece toward target rotation
# "sliding"   → slide piece toward target column
# "falling"   → drop piece one row at a time
# "locking"   → brief pause after landing
# "flashing"  → row-clear flash animation
# "clearing"  → apply row clear, redraw
# "fading"    → end-of-game fade out
# "restarting"→ brief pause before new game

_state       = "spawning"
_accumulator = 0.0

_board       = []
_cur_shape   = []
_cur_col     = 0
_cur_row     = 0
_cur_color   = (0,0,0)
_cur_rot     = 0
_rotations   = []
_target_rot  = 0
_target_col  = 0
_full_rows   = []
_flash_step  = 0
_fade_step   = 0
_snapshot    = []

# ── Board helpers ─────────────────────────────────────────────────────────────

def _pw(shape): return max(c for c,r in shape) + 1
def _ph(shape): return max(r for c,r in shape) + 1

def _random_color():
    return random.choice([
        (255,40,40),(255,140,0),(220,220,0),(0,210,0),
        (0,180,255),(0,80,255),(180,0,255),(255,0,160),
        (0,220,180),(255,200,0),
    ])

def _reset_board():
    global _board
    _board = [[None]*COLS for _ in range(ROWS)]

def _collides(shape, col, row, brd=None):
    if brd is None: brd = _board
    for dc, dr in shape:
        c, r = col+dc, row+dr
        if c < 0 or c >= COLS or r >= ROWS: return True
        if r >= 0 and brd[r][c] is not None: return True
    return False

def _lock(shape, col, row, color, brd=None):
    if brd is None: brd = _board
    for dc, dr in shape:
        c, r = col+dc, row+dr
        if 0 <= c < COLS and 0 <= r < ROWS:
            brd[r][c] = color

def _drop_row(shape, col, brd):
    row = 0
    while not _collides(shape, col, row+1, brd):
        row += 1
    return row

def _find_full_rows(brd=None):
    if brd is None: brd = _board
    return [r for r in range(ROWS) if all(brd[r][c] is not None for c in range(COLS))]

def _apply_clear_rows(brd):
    cleared = 0
    full = _find_full_rows(brd)
    while full:
        for r in sorted(full, reverse=True):
            del brd[r]
            brd.insert(0, [None]*COLS)
            cleared += 1
        full = _find_full_rows(brd)
    return cleared

def _col_heights(brd):
    heights = []
    for c in range(COLS):
        h = 0
        for r in range(ROWS):
            if brd[r][c] is not None:
                h = ROWS - r
                break
        heights.append(h)
    return heights

def _holes(brd):
    holes = 0
    for c in range(COLS):
        found = False
        for r in range(ROWS):
            if brd[r][c] is not None: found = True
            elif found: holes += 1
    return holes

def _score(brd):
    sim     = copy.deepcopy(brd)
    lines   = _apply_clear_rows(sim)
    heights = _col_heights(sim)
    return (W_LINES_CLEARED * lines +
            W_AGG_HEIGHT    * sum(heights) +
            W_HOLES         * _holes(sim) +
            W_BUMPINESS     * sum(abs(heights[i]-heights[i+1]) for i in range(len(heights)-1)))

def _best_move(rotations, color):
    candidates = []
    for rot_idx, shape in enumerate(rotations):
        for col in range(COLS - _pw(shape) + 1):
            if _collides(shape, col, 0): continue
            row = _drop_row(shape, col, _board)
            sim = copy.deepcopy(_board)
            _lock(shape, col, row, color, sim)
            candidates.append((_score(sim), rot_idx, col))
    if not candidates: return 0, 0
    candidates.sort(key=lambda x: x[0], reverse=True)
    if random.random() < AI_IMPERFECTION and len(candidates) > 1:
        _, rot_idx, col = random.choice(candidates[len(candidates)//2:])
    else:
        _, rot_idx, col = candidates[0]
    return rot_idx, col

# ── Drawing ───────────────────────────────────────────────────────────────────

def _draw(pixels, shape=None, col=0, row=0, color=None):
    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = _board[r][c] or (0,0,0)
    if shape is not None:
        for dc, dr in shape:
            c, r = col+dc, row+dr
            if 0 <= c < COLS and 0 <= r < ROWS:
                pixels[xy(c, r)] = color
    pixels.show()

# ── Init ──────────────────────────────────────────────────────────────────────

def init():
    global _state, _accumulator
    _reset_board()
    _state       = "spawning"
    _accumulator = 0.0

# ── Frame ─────────────────────────────────────────────────────────────────────

def frame(pixels, dt):
    global _state, _accumulator
    global _cur_shape, _cur_col, _cur_row, _cur_color, _cur_rot
    global _rotations, _target_rot, _target_col
    global _full_rows, _flash_step, _fade_step, _snapshot

    _accumulator += dt

    if _state == "spawning":
        time.sleep(0.02)   # breathe before heavy computation
        _rotations  = random.choice(RAW_PIECES)
        _cur_color  = _random_color()
        _cur_rot    = 0
        _cur_shape  = _rotations[0]
        _cur_col    = (COLS - _pw(_cur_shape)) // 2
        _cur_row    = 0
        if _collides(_cur_shape, _cur_col, _cur_row):
            # Board full — start fade
            _snapshot    = [[_board[r][c] or (0,0,0) for c in range(COLS)] for r in range(ROWS)]
            _fade_step   = 0
            _state       = "fading"
            _accumulator = 0.0
            return
        _target_rot, _target_col = _best_move(_rotations, _cur_color)
        _draw(pixels, _cur_shape, _cur_col, _cur_row, _cur_color)
        _state       = "rotating"
        _accumulator = 0.0

    elif _state == "rotating":
        if _accumulator < ROTATE_DELAY:
            return
        _accumulator = 0.0
        if _cur_rot == _target_rot:
            _state = "sliding"
            return
        _cur_rot   = (_cur_rot + 1) % len(_rotations)
        _cur_shape = _rotations[_cur_rot]
        _cur_col   = max(0, min(_cur_col, COLS - _pw(_cur_shape)))
        _draw(pixels, _cur_shape, _cur_col, _cur_row, _cur_color)

    elif _state == "sliding":
        if _accumulator < SLIDE_DELAY:
            return
        _accumulator = 0.0
        if _cur_col == _target_col:
            _state = "falling"
            return
        step = 1 if _target_col > _cur_col else -1
        nxt  = _cur_col + step
        if not _collides(_cur_shape, nxt, _cur_row):
            _cur_col = nxt
        else:
            _state = "falling"
            return
        _draw(pixels, _cur_shape, _cur_col, _cur_row, _cur_color)

    elif _state == "falling":
        if _accumulator < FALL_DELAY:
            return
        _accumulator = 0.0
        if _collides(_cur_shape, _cur_col, _cur_row + 1):
            # Land
            _lock(_cur_shape, _cur_col, _cur_row, _cur_color)
            _draw(pixels)
            _full_rows = _find_full_rows()
            _state     = "locking"
        else:
            _cur_row += 1
            _draw(pixels, _cur_shape, _cur_col, _cur_row, _cur_color)

    elif _state == "locking":
        if _accumulator < LOCK_PAUSE:
            return
        _accumulator = 0.0
        if _full_rows:
            _flash_step  = 0
            _state       = "flashing"
        else:
            _state = "spawning"

    elif _state == "flashing":
        flash_duration = CLEAR_FLASH_TIME
        on = (_flash_step % 2 == 0)
        if _accumulator < flash_duration:
            return
        _accumulator = 0.0
        # Draw flash frame
        for r in _full_rows:
            for c in range(COLS):
                pixels[xy(c, r)] = (255,255,255) if on else (0,0,0)
        pixels.show()
        _flash_step += 1
        if _flash_step >= FLASH_COUNT * 2:
            _state = "clearing"

    elif _state == "clearing":
        _apply_clear_rows(_board)
        _draw(pixels)
        _state       = "spawning"
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
        if _accumulator >= 0.6:
            _reset_board()
            _state       = "spawning"
            _accumulator = 0.0
