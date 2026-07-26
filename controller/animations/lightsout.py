"""
animations/lightsout.py — Lights Out puzzle with a genuine GF(2) solver

A single-player toggle puzzle, played on the full COLS×ROWS grid:
pressing a cell toggles it and its 4 orthogonal neighbours between lit
and unlit. The goal is to turn every cell off.

Each round: scramble the board from all-off using a random subset of
presses (which guarantees a solvable board), pause, solve it with
Gaussian elimination over GF(2), then animate stepping through the
solution — each press flashes the affected cross of cells before
settling — until the board goes fully dark. Then repeat.
"""

import random
from .shared import COLS, ROWS, xy

FRAME_DELAY = 0.05
NAME        = "Lights Out"

N = COLS * ROWS   # one variable per cell

# ── Timing ────────────────────────────────────────────────────────────────────

SCRAMBLE_PAUSE = 1.5    # seconds to show the freshly-scrambled board before solving
STEP_FLASH_TIME = 0.2   # how long each press's affected cells flash before settling
STEP_SETTLE_TIME = 0.1  # brief pause after settling, before the next press
SOLVED_PAUSE    = 2.0   # seconds to show the fully-dark board before re-scrambling

# ── Colours ───────────────────────────────────────────────────────────────────

ON_COLOR    = (255, 190,  30)   # lit cell
OFF_COLOR   = (  0,   0,   0)   # unlit cell
FLASH_COLOR = (255, 255, 255)   # cells affected by the press currently animating

# ── Grid helpers (logical row-major index, independent of LED wiring) ─────────

def _li(r, c): return r * COLS + c
def _rc(i):    return divmod(i, COLS)

# NEIGHBOR_MASKS[i] = bitmask of the cells toggled by pressing cell i
# (itself plus up/down/left/right neighbours that exist on the board).
NEIGHBOR_MASKS = []
for _i in range(N):
    _r, _c = _rc(_i)
    _mask = 1 << _i
    for _dr, _dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        _nr, _nc = _r + _dr, _c + _dc
        if 0 <= _nr < ROWS and 0 <= _nc < COLS:
            _mask |= 1 << _li(_nr, _nc)
    NEIGHBOR_MASKS.append(_mask)

# ── GF(2) solver ──────────────────────────────────────────────────────────────

def _solve(board_bits):
    """Return a bitmask of which cells to press to clear `board_bits`
    (a bitmask of currently-lit cells), via Gaussian elimination mod 2.
    Falls back to None if the system turns out inconsistent (shouldn't
    happen for boards produced by _scramble, which are solvable by
    construction).
    """
    # Augmented rows: bit i = NEIGHBOR_MASKS row for cell i (which button
    # presses affect cell i — the matrix is symmetric, so this doubles as
    # both the per-cell equation and the per-button effect), bit N = rhs.
    rows = [NEIGHBOR_MASKS[i] | (((board_bits >> i) & 1) << N) for i in range(N)]

    pivot_row = 0
    pivot_col_of_row = {}
    for col in range(N):
        found = None
        for r in range(pivot_row, N):
            if (rows[r] >> col) & 1:
                found = r
                break
        if found is None:
            continue
        rows[pivot_row], rows[found] = rows[found], rows[pivot_row]
        for r in range(N):
            if r != pivot_row and (rows[r] >> col) & 1:
                rows[r] ^= rows[pivot_row]
        pivot_col_of_row[pivot_row] = col
        pivot_row += 1

    # Consistency check: any fully-zero-mask row with rhs bit set means no solution
    for r in range(pivot_row, N):
        if (rows[r] >> N) & 1 == 0 and (rows[r] & ((1 << N) - 1)) == 0:
            continue
        if (rows[r] & ((1 << N) - 1)) == 0 and (rows[r] >> N) & 1:
            return None

    solution = 0
    for r, col in pivot_col_of_row.items():
        if (rows[r] >> N) & 1:
            solution |= (1 << col)
    return solution

def _scramble():
    """Random solvable board: XOR together a random subset of presses,
    starting from all-off."""
    board = 0
    for i in range(N):
        if random.random() < 0.5:
            board ^= NEIGHBOR_MASKS[i]
    return board

# ── Sweep styles ──────────────────────────────────────────────────────────────
# Each is a sort key over a cell index; combined with a random reverse flag
# per round, this gives a variety of "directions" the solve animates in.

def _sweep_diag_tlbr(i):
    r, c = _rc(i)
    return (r + c, r)

def _sweep_diag_trbl(i):
    r, c = _rc(i)
    return (r - c, r)

def _sweep_row_major(i):
    r, c = _rc(i)
    return (r, c)

def _sweep_col_major(i):
    r, c = _rc(i)
    return (c, r)

SWEEP_STYLES = [_sweep_diag_tlbr, _sweep_diag_trbl, _sweep_row_major, _sweep_col_major]

# ── Rendering ─────────────────────────────────────────────────────────────────

def _render(pixels, board, flash_mask=0):
    for i in range(N):
        r, c = _rc(i)
        if (flash_mask >> i) & 1:
            color = FLASH_COLOR
        elif (board >> i) & 1:
            color = ON_COLOR
        else:
            color = OFF_COLOR
        pixels[xy(c, r)] = color
    pixels.show()

# ── State machine ─────────────────────────────────────────────────────────────
# States:
#   "scrambled" — freshly scrambled board, brief pause before solving starts
#   "stepping"  — animating through the solution, one press at a time
#   "solved"    — board fully dark, pause before the next round

_board        = 0
_solution     = []   # ordered list of cell indices to press
_step         = 0
_toggled_this_step = False
_accumulator  = 0.0
_state        = "scrambled"

def _new_round():
    global _board, _solution, _step, _toggled_this_step, _accumulator, _state
    _board = _scramble()
    sol_mask = _solve(_board)
    if sol_mask is None:
        # Shouldn't happen for a board built by _scramble, but guard anyway —
        # pressing the exact same presses that built it always clears it.
        sol_mask = _board
    presses = [i for i in range(N) if (sol_mask >> i) & 1]
    # Sweep order varies each round — a different style and direction, so
    # consecutive games don't all wipe the same way
    style   = random.choice(SWEEP_STYLES)
    reverse = random.choice([False, True])
    presses.sort(key=style, reverse=reverse)
    _solution           = presses
    _step               = 0
    _toggled_this_step  = False
    _accumulator        = 0.0
    _state              = "scrambled"

def init():
    _new_round()

def frame(pixels, dt):
    global _board, _step, _toggled_this_step, _accumulator, _state

    _accumulator += dt

    if _state == "scrambled":
        _render(pixels, _board)
        if _accumulator >= SCRAMBLE_PAUSE:
            _state       = "stepping"
            _accumulator = 0.0

    elif _state == "stepping":
        if _step >= len(_solution):
            _state       = "solved"
            _accumulator = 0.0
            _render(pixels, _board)
            return

        idx = _solution[_step]
        affected = NEIGHBOR_MASKS[idx]

        if _accumulator < STEP_FLASH_TIME:
            _render(pixels, _board, flash_mask=affected)
        else:
            if not _toggled_this_step:
                _board ^= affected
                _toggled_this_step = True
            _render(pixels, _board)
            if _accumulator >= STEP_FLASH_TIME + STEP_SETTLE_TIME:
                _step += 1
                _toggled_this_step = False
                _accumulator = 0.0

    elif _state == "solved":
        _render(pixels, _board)
        if _accumulator >= SOLVED_PAUSE:
            _new_round()
