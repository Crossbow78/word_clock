"""
animations/othello.py — Reversi/Othello with time-bounded minimax AI (iterative deepening + alpha-beta)

Two AI players play a full game of Othello on an 8×8 board.
Discs are colour-coded per player; captured discs flip colour in a
cascading animation each move. Score bars on the side columns show
disc counts, turn indicators show whose move it is.

Layout (all parametric — adjust constants below):
  Board:      cols BOARD_COL .. BOARD_COL+7, rows BOARD_ROW .. BOARD_ROW+7
  Score bars: col SCORE_COL_B (black), col SCORE_COL_W (white), rows BOARD_ROW..BOARD_ROW+7
  Turn dots:  row TURN_ROW, col TURN_COL_B (black), col TURN_COL_W (white)
"""

import time
import random
from .shared import COLS, ROWS, xy

FRAME_DELAY = 0.05
NAME        = "Othello"

# ── Layout parameters ─────────────────────────────────────────────────────────

BOARD_COL   = 2      # leftmost column of the 8x8 board
BOARD_ROW   = 1      # topmost row of the 8x8 board

SCORE_COL_B = 0       # black disc-count bar
SCORE_COL_W = 11      # white disc-count bar

TURN_ROW    = 0
TURN_COL_B  = 0
TURN_COL_W  = 11

# ── Timing ────────────────────────────────────────────────────────────────────

MOVE_DELAY      = 2.0     # seconds between moves
PASS_PAUSE      = 1.2     # seconds to show a "pass" flash
PLACE_FLASH     = 0.15    # duration of the placed-disc flash
FLIP_STEP_TIME  = 0.08    # time between each cascading flip step
GAME_END_PAUSE  = 4.0     # pause at game over before restart

THINK_TIME_MS        = 1250  # base thinking budget per move (milliseconds)
THINK_TIME_JITTER_MS = 250   # +/- random variation per move, for a bit of personality
MAX_DEPTH            = 8     # hard cap on search depth regardless of time left

# ── Colours ───────────────────────────────────────────────────────────────────

COLOR_B      = ( 30,  70, 230)   # black player — blue
COLOR_W      = (230, 150,  20)   # white player — amber
EMPTY_COLOR  = (  0,  25,   8)   # felt green
FLASH_COLOR  = (255, 255, 255)   # placed-disc flash
TURN_ON      = (255, 255, 255)
TURN_OFF     = (  0,   0,   0)

# ── Positional weights (standard Othello heuristic, corners/edges favoured) ────

WEIGHTS = [
    [100, -20, 10,  5,  5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [ 10,  -2, -1, -1, -1, -1,  -2,  10],
    [  5,  -2, -1, -1, -1, -1,  -2,   5],
    [  5,  -2, -1, -1, -1, -1,  -2,   5],
    [ 10,  -2, -1, -1, -1, -1,  -2,  10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10,  5,  5, 10, -20, 100],
]

DIRS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

# ── Othello engine ───────────────────────────────────────────────────────────

def _idx(r, c): return r * 8 + c
def _pos(i):    return i // 8, i % 8
def _on_board(r, c): return 0 <= r < 8 and 0 <= c < 8

def _start_board():
    b = [None] * 64
    b[_idx(3, 3)] = "W"
    b[_idx(3, 4)] = "B"
    b[_idx(4, 3)] = "B"
    b[_idx(4, 4)] = "W"
    return b

def _flips_for(board, idx, color):
    if board[idx] is not None:
        return []
    opp = "W" if color == "B" else "B"
    r, c = _pos(idx)
    flips = []
    for dr, dc in DIRS:
        line = []
        nr, nc = r + dr, c + dc
        while _on_board(nr, nc) and board[_idx(nr, nc)] == opp:
            line.append(_idx(nr, nc))
            nr += dr; nc += dc
        if line and _on_board(nr, nc) and board[_idx(nr, nc)] == color:
            flips.extend(line)
    return flips

def _legal_moves(board, color):
    moves = []
    for i in range(64):
        flips = _flips_for(board, i, color)
        if flips:
            moves.append((i, flips))
    return moves

def _apply_move(board, move, color):
    idx, flips = move
    b = board[:]
    b[idx] = color
    for f in flips:
        b[f] = color
    return b

def _evaluate(board):
    score = 0
    for i in range(64):
        p = board[i]
        if p is None:
            continue
        r, c = _pos(i)
        w = WEIGHTS[r][c]
        score += w if p == "B" else -w
    return score

def _final_evaluate(board):
    b = sum(1 for p in board if p == "B")
    w = sum(1 for p in board if p == "W")
    return (b - w) * 1000

class _TimeUp(Exception):
    """Raised to unwind the search once the thinking-time budget is spent."""
    pass

def _minimax(board, depth, alpha, beta, maximising, deadline=float("inf"), pass_count=0):
    if time.monotonic() >= deadline:
        raise _TimeUp()

    color = "B" if maximising else "W"
    moves = _legal_moves(board, color)

    if not moves:
        if pass_count >= 1:
            return _final_evaluate(board), None
        return _minimax(board, depth, alpha, beta, not maximising, deadline, pass_count + 1)

    if depth == 0:
        return _evaluate(board), None

    # Shuffle first so ties break differently game to game — an easy hook
    # for variation — then keep the bigger-flips-first ordering on top.
    random.shuffle(moves)
    moves.sort(key=lambda m: len(m[1]), reverse=True)

    best_move = moves[0]
    if maximising:
        best = -999999
        for move in moves:
            nb = _apply_move(board, move, color)
            val, _ = _minimax(nb, depth - 1, alpha, beta, False, deadline, 0)
            if val > best:
                best, best_move = val, move
            alpha = max(alpha, best)
            if beta <= alpha: break
        return best, best_move
    else:
        best = 999999
        for move in moves:
            nb = _apply_move(board, move, color)
            val, _ = _minimax(nb, depth - 1, alpha, beta, True, deadline, 0)
            if val < best:
                best, best_move = val, move
            beta = min(beta, best)
            if beta <= alpha: break
        return best, best_move

def _search(board, maximising, time_budget_ms):
    """Iterative-deepening search bounded by a thinking-time budget (ms).

    Depth 1 always completes fully so a legal move is guaranteed even with
    a tiny or already-expired budget; deeper iterations are cut off by
    _TimeUp once the budget runs out, falling back to the last completed
    depth's best move.
    """
    _, best_move = _minimax(board, 1, -999999, 999999, maximising)

    deadline = time.monotonic() + time_budget_ms / 1000.0
    depth = 2
    while depth <= MAX_DEPTH:
        try:
            _, move = _minimax(board, depth, -999999, 999999, maximising, deadline)
        except _TimeUp:
            break
        if move is not None:
            best_move = move
        depth += 1
    return best_move

# ── Rendering ─────────────────────────────────────────────────────────────────

def _board_xy(br, bc):
    return BOARD_COL + bc, BOARD_ROW + br

def _disc_color(color, flash=False):
    if flash:
        return FLASH_COLOR
    return COLOR_B if color == "B" else COLOR_W

def _render(pixels, board, turn, highlight=None, hide=None, flipped_shown=None):
    for i in range(COLS * ROWS):
        pixels[i] = (0, 0, 0)

    # Board squares and discs
    for br in range(8):
        for bc in range(8):
            gc, gr = _board_xy(br, bc)
            idx    = _idx(br, bc)
            piece  = board[idx]

            if hide and idx in hide:
                pixels[xy(gc, gr)] = EMPTY_COLOR
            elif piece:
                flash = bool(highlight and idx in highlight)
                pixels[xy(gc, gr)] = _disc_color(piece, flash=flash)
            else:
                pixels[xy(gc, gr)] = EMPTY_COLOR

    # Score bars — filled bottom-up, proportional to disc count out of 64
    b_count = sum(1 for p in board if p == "B")
    w_count = sum(1 for p in board if p == "W")
    b_lit   = round(b_count / 64 * 8)
    w_lit   = round(w_count / 64 * 8)
    for r in range(8):
        row = BOARD_ROW + (7 - r)   # fill from bottom row upward
        pixels[xy(SCORE_COL_B, row)] = COLOR_B if r < b_lit else (0, 0, 0)
        pixels[xy(SCORE_COL_W, row)] = COLOR_W if r < w_lit else (0, 0, 0)

    # Turn indicators
    pixels[xy(TURN_COL_B, TURN_ROW)] = TURN_ON if turn == "B" else TURN_OFF
    pixels[xy(TURN_COL_W, TURN_ROW)] = TURN_ON if turn == "W" else TURN_OFF

    pixels.show()

# ── State machine ─────────────────────────────────────────────────────────────
# States:
#   "thinking"  — check for legal moves / pass / compute AI move
#   "pass"      — brief flash indicating a forced pass
#   "placing"   — flash the newly-placed disc
#   "flipping"  — cascade flipped discs outward from the placed disc
#   "waiting"   — pause before next move
#   "game_over" — no legal moves for either side, pause then restart

_board        = []
_turn         = "B"
_pending_move = None
_flip_order   = []
_flip_step    = 0
_accumulator  = 0.0
_state        = "thinking"
_consec_pass  = 0

def _start_game():
    global _board, _turn, _pending_move, _flip_order, _flip_step
    global _accumulator, _state, _consec_pass
    _board        = _start_board()
    _turn         = "B"
    _pending_move = None
    _flip_order   = []
    _flip_step    = 0
    _accumulator  = 0.0
    _state        = "thinking"
    _consec_pass  = 0

def init():
    _start_game()

def _sort_flips_by_distance(idx, flips):
    r, c = _pos(idx)
    def dist(f):
        fr, fc = _pos(f)
        return abs(fr - r) + abs(fc - c)
    return sorted(flips, key=dist)

def frame(pixels, dt):
    global _state, _accumulator, _turn, _board, _pending_move
    global _flip_order, _flip_step, _consec_pass

    _accumulator += dt

    if _state == "thinking":
        _render(pixels, _board, _turn)

        legal = _legal_moves(_board, _turn)
        if not legal:
            _consec_pass += 1
            if _consec_pass >= 2:
                _state       = "game_over"
                _accumulator = 0.0
                return
            _turn        = "W" if _turn == "B" else "B"
            _state       = "pass"
            _accumulator = 0.0
            return

        _consec_pass = 0
        budget = THINK_TIME_MS + random.randint(-THINK_TIME_JITTER_MS, THINK_TIME_JITTER_MS)
        budget = max(50, budget)
        move = _search(_board, _turn == "B", budget)
        if move is None:
            _state       = "game_over"
            _accumulator = 0.0
            return

        idx, flips     = move
        _pending_move  = (idx, flips)
        _flip_order    = _sort_flips_by_distance(idx, flips)
        _flip_step     = 0
        _state         = "placing"
        _accumulator   = 0.0

    elif _state == "pass":
        _render(pixels, _board, _turn)
        if _accumulator >= PASS_PAUSE:
            _state       = "thinking"
            _accumulator = 0.0

    elif _state == "placing":
        idx, _ = _pending_move
        sim = _board[:]
        sim[idx] = _turn
        flash_on = int(_accumulator / (PLACE_FLASH / 2)) % 2 == 0
        _render(pixels, sim, _turn, highlight={idx} if flash_on else None)
        if _accumulator >= PLACE_FLASH:
            # Commit the disc itself (flips happen incrementally next state)
            _board[idx]  = _turn
            _state       = "flipping"
            _accumulator = 0.0

    elif _state == "flipping":
        if _accumulator >= FLIP_STEP_TIME and _flip_step < len(_flip_order):
            flip_idx = _flip_order[_flip_step]
            _board[flip_idx] = _turn
            _flip_step  += 1
            _accumulator = 0.0

        idx, _ = _pending_move
        highlight = {_flip_order[_flip_step - 1]} if _flip_step > 0 else None
        _render(pixels, _board, _turn, highlight=highlight)

        if _flip_step >= len(_flip_order):
            _turn        = "W" if _turn == "B" else "B"
            _state       = "waiting"
            _accumulator = 0.0

    elif _state == "waiting":
        _render(pixels, _board, _turn)
        if _accumulator >= MOVE_DELAY:
            _state       = "thinking"
            _accumulator = 0.0

    elif _state == "game_over":
        b_count = sum(1 for p in _board if p == "B")
        w_count = sum(1 for p in _board if p == "W")
        winner  = "B" if b_count > w_count else ("W" if w_count > b_count else None)

        blink_on = (int(_accumulator / 0.5) % 2 == 0)
        if winner and blink_on:
            _render(pixels, _board, _turn, highlight=set(
                i for i, p in enumerate(_board) if p == winner))
        else:
            _render(pixels, _board, _turn)

        if _accumulator >= GAME_END_PAUSE:
            _start_game()
