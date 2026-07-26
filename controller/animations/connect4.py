"""
animations/connect4.py — Connect Four with time-bounded minimax AI (iterative deepening + alpha-beta)

Two AI players play Connect Four on a 7×6 board (standard size).
Discs are colour-coded per player and animate falling into place.
Turn indicator dots sit above the board.

Layout (all parametric — adjust constants below):
  Board:     cols BOARD_COL .. BOARD_COL+6, rows BOARD_ROW .. BOARD_ROW+5
  Turn dots: row TURN_ROW, col BOARD_COL (red), col BOARD_COL+6 (yellow)
"""

import time
import random
from .shared import COLS, ROWS, xy

FRAME_DELAY = 0.05
NAME        = "Connect Four"

# ── Layout parameters ─────────────────────────────────────────────────────────

BOARD_COL = 2     # leftmost column of the 7-wide board
BOARD_ROW = 2     # topmost row of the 6-tall board
TURN_ROW  = 0

N_COLS = 7
N_ROWS = 6

# ── Timing ────────────────────────────────────────────────────────────────────

MOVE_DELAY       = 0.5    # seconds between moves
FALL_STEP_TIME   = 0.04   # seconds per row of fall animation
LANDING_FLASH    = 0.15   # duration of the landed-disc flash
GAME_END_PAUSE   = 4.0    # pause at win/draw before restart

THINK_TIME_MS        = 1800   # base thinking budget per move (milliseconds)
THINK_TIME_JITTER_MS = 400   # +/- random variation per move, for a bit of personality
MAX_DEPTH            = 8     # hard cap on search depth regardless of time left

# ── Colours ───────────────────────────────────────────────────────────────────

COLOR_R      = (255,  30,  10)   # red player
COLOR_Y      = (255, 190,  10)   # yellow player
EMPTY_COLOR  = (  0,  10,  30)   # board felt (dark blue)
FLASH_COLOR  = (255, 255, 255)
TURN_ON      = (255, 255, 255)
TURN_OFF     = (  0,   0,   0)
WIN_FLASH_A  = (255, 255, 255)

# ── Connect Four engine ───────────────────────────────────────────────────────
# board is a flat list of length N_COLS*N_ROWS, indexed board[r * N_COLS + c],
# r=0 is the top row, r=N_ROWS-1 is the bottom row.

def _idx(r, c): return r * N_COLS + c

def _empty_board():
    return [None] * (N_COLS * N_ROWS)

def _drop_row(board, col):
    """Lowest empty row in this column, or None if the column is full."""
    for r in range(N_ROWS - 1, -1, -1):
        if board[_idx(r, col)] is None:
            return r
    return None

def _legal_moves(board):
    return [c for c in range(N_COLS) if _drop_row(board, c) is not None]

def _apply_move(board, col, color):
    row = _drop_row(board, col)
    b = board[:]
    b[_idx(row, col)] = color
    return b, row

def _check_win(board, color):
    # Horizontal
    for r in range(N_ROWS):
        for c in range(N_COLS - 3):
            if all(board[_idx(r, c + k)] == color for k in range(4)):
                return True
    # Vertical
    for c in range(N_COLS):
        for r in range(N_ROWS - 3):
            if all(board[_idx(r + k, c)] == color for k in range(4)):
                return True
    # Diagonal down-right
    for r in range(N_ROWS - 3):
        for c in range(N_COLS - 3):
            if all(board[_idx(r + k, c + k)] == color for k in range(4)):
                return True
    # Diagonal down-left
    for r in range(N_ROWS - 3):
        for c in range(3, N_COLS):
            if all(board[_idx(r + k, c - k)] == color for k in range(4)):
                return True
    return False

def _is_full(board):
    return all(cell is not None for cell in board[:N_COLS])   # top row full = board full

def _window_score(window, piece):
    opp = "Y" if piece == "R" else "R"
    score = 0
    p_count = window.count(piece)
    e_count = window.count(None)
    o_count = window.count(opp)
    if p_count == 4:
        score += 100
    elif p_count == 3 and e_count == 1:
        score += 5
    elif p_count == 2 and e_count == 2:
        score += 2
    if o_count == 3 and e_count == 1:
        score -= 4
    return score

def _evaluate(board):
    score = 0
    # Centre column preference
    for r in range(N_ROWS):
        if board[_idx(r, N_COLS // 2)] == "R":
            score += 3
        elif board[_idx(r, N_COLS // 2)] == "Y":
            score -= 3

    # Horizontal windows
    for r in range(N_ROWS):
        row = [board[_idx(r, c)] for c in range(N_COLS)]
        for c in range(N_COLS - 3):
            window = row[c:c + 4]
            score += _window_score(window, "R")
            score -= _window_score(window, "Y")

    # Vertical windows
    for c in range(N_COLS):
        col = [board[_idx(r, c)] for r in range(N_ROWS)]
        for r in range(N_ROWS - 3):
            window = col[r:r + 4]
            score += _window_score(window, "R")
            score -= _window_score(window, "Y")

    # Diagonal down-right windows
    for r in range(N_ROWS - 3):
        for c in range(N_COLS - 3):
            window = [board[_idx(r + k, c + k)] for k in range(4)]
            score += _window_score(window, "R")
            score -= _window_score(window, "Y")

    # Diagonal down-left windows
    for r in range(N_ROWS - 3):
        for c in range(3, N_COLS):
            window = [board[_idx(r + k, c - k)] for k in range(4)]
            score += _window_score(window, "R")
            score -= _window_score(window, "Y")

    return score

class _TimeUp(Exception):
    """Raised to unwind the search once the thinking-time budget is spent."""
    pass

def _minimax(board, depth, alpha, beta, maximising, deadline=float("inf")):
    if time.monotonic() >= deadline:
        raise _TimeUp()

    if _check_win(board, "R"):
        return 1000000 + depth, None      # prefer faster wins
    if _check_win(board, "Y"):
        return -1000000 - depth, None     # prefer slower losses
    moves = _legal_moves(board)
    if not moves or depth == 0:
        return _evaluate(board), None

    # Shuffle first so ties break differently game to game — an easy hook
    # for variation — then keep the centre-out ordering on top (better
    # alpha-beta pruning, since central columns are usually stronger).
    random.shuffle(moves)
    centre = N_COLS // 2
    moves.sort(key=lambda c: abs(c - centre))

    color = "R" if maximising else "Y"
    best_move = moves[0]
    if maximising:
        best = -9999999
        for col in moves:
            nb, _ = _apply_move(board, col, color)
            val, _ = _minimax(nb, depth - 1, alpha, beta, False, deadline)
            if val > best:
                best, best_move = val, col
            alpha = max(alpha, best)
            if beta <= alpha: break
        return best, best_move
    else:
        best = 9999999
        for col in moves:
            nb, _ = _apply_move(board, col, color)
            val, _ = _minimax(nb, depth - 1, alpha, beta, True, deadline)
            if val < best:
                best, best_move = val, col
            beta = min(beta, best)
            if beta <= alpha: break
        return best, best_move

def _immediate_win_count(board, color):
    """How many legal moves would let `color` win right now."""
    count = 0
    for col in _legal_moves(board):
        nb, _ = _apply_move(board, col, color)
        if _check_win(nb, color):
            count += 1
    return count

def _root_search(board, maximising, depth, deadline):
    """Like _minimax, but evaluates every root move fully (no pruning at
    the root) so ties at the optimal value can be broken sensibly rather
    than by whichever sibling alpha-beta happened to visit first.
    """
    if time.monotonic() >= deadline:
        raise _TimeUp()

    moves = _legal_moves(board)
    if not moves:
        return None

    random.shuffle(moves)
    centre = N_COLS // 2
    moves.sort(key=lambda c: abs(c - centre))

    color = "R" if maximising else "Y"
    opp   = "Y" if color == "R" else "R"

    results = []
    for col in moves:
        nb, _ = _apply_move(board, col, color)
        val, _ = _minimax(nb, depth - 1, -9999999, 9999999, not maximising, deadline)
        results.append((col, val))

    best_val = max(v for _, v in results) if maximising else min(v for _, v in results)
    tied = [c for c, v in results if v == best_val]
    if len(tied) == 1:
        return tied[0]

    # Secondary tie-break: among equally-optimal moves (this matters most
    # in a lost position, where every move is "you lose next turn" and the
    # raw score can't distinguish them) prefer leaving the opponent with
    # the fewest immediate winning replies — makes the AI visibly block
    # one threat instead of ignoring all of them, even when the loss
    # itself is unavoidable.
    def opp_threats(col):
        nb, _ = _apply_move(board, col, color)
        return _immediate_win_count(nb, opp)

    min_threats = min(opp_threats(c) for c in tied)
    best_tied   = [c for c in tied if opp_threats(c) == min_threats]
    return random.choice(best_tied)

def _search(board, maximising, time_budget_ms):
    """Iterative-deepening search bounded by a thinking-time budget (ms).

    Depth 1 always completes fully so a legal move is guaranteed even with
    a tiny or already-expired budget; deeper iterations are cut off by
    _TimeUp once the budget runs out, falling back to the last completed
    depth's best move.
    """
    best_move = _root_search(board, maximising, 1, float("inf"))

    deadline = time.monotonic() + time_budget_ms / 1000.0
    depth = 2
    while depth <= MAX_DEPTH:
        try:
            move = _root_search(board, maximising, depth, deadline)
        except _TimeUp:
            break
        if move is not None:
            best_move = move
        depth += 1
    return best_move

# ── Rendering ─────────────────────────────────────────────────────────────────

def _color_for(piece, flash=False):
    if flash:
        return FLASH_COLOR
    return COLOR_R if piece == "R" else COLOR_Y

def _render(pixels, board, turn, falling=None, win_cells=None, win_blink_on=True):
    for i in range(COLS * ROWS):
        pixels[i] = (0, 0, 0)

    for r in range(N_ROWS):
        for c in range(N_COLS):
            gc, gr = BOARD_COL + c, BOARD_ROW + r
            piece  = board[_idx(r, c)]
            if piece:
                if win_cells and (r, c) in win_cells:
                    pixels[xy(gc, gr)] = WIN_FLASH_A if win_blink_on else _color_for(piece)
                else:
                    pixels[xy(gc, gr)] = _color_for(piece)
            else:
                pixels[xy(gc, gr)] = EMPTY_COLOR

    if falling is not None:
        col, row, color, flash = falling
        gc, gr = BOARD_COL + col, BOARD_ROW + row
        pixels[xy(gc, gr)] = _color_for(color, flash=flash)

    pixels[xy(BOARD_COL, TURN_ROW)]             = TURN_ON if turn == "R" else TURN_OFF
    pixels[xy(BOARD_COL + N_COLS - 1, TURN_ROW)] = TURN_ON if turn == "Y" else TURN_OFF

    pixels.show()

def _find_win_cells(board, color):
    cells = set()
    for r in range(N_ROWS):
        for c in range(N_COLS - 3):
            if all(board[_idx(r, c + k)] == color for k in range(4)):
                cells.update((r, c + k) for k in range(4))
    for c in range(N_COLS):
        for r in range(N_ROWS - 3):
            if all(board[_idx(r + k, c)] == color for k in range(4)):
                cells.update((r + k, c) for k in range(4))
    for r in range(N_ROWS - 3):
        for c in range(N_COLS - 3):
            if all(board[_idx(r + k, c + k)] == color for k in range(4)):
                cells.update((r + k, c + k) for k in range(4))
    for r in range(N_ROWS - 3):
        for c in range(3, N_COLS):
            if all(board[_idx(r + k, c - k)] == color for k in range(4)):
                cells.update((r + k, c - k) for k in range(4))
    return cells

# ── State machine ─────────────────────────────────────────────────────────────
# States:
#   "thinking"  — compute the AI's move (or detect a draw)
#   "falling"   — animate the disc dropping down its column
#   "landed"    — brief flash once the disc settles
#   "waiting"   — pause before the next move
#   "game_over" — a win or a draw; pause then restart

_board       = []
_turn        = "R"
_fall_col    = None
_fall_row    = 0
_target_row  = 0
_accumulator = 0.0
_state       = "thinking"
_winner      = None

def _start_game():
    global _board, _turn, _fall_col, _fall_row, _target_row
    global _accumulator, _state, _winner
    _board       = _empty_board()
    _turn        = "R"
    _fall_col    = None
    _fall_row    = 0
    _target_row  = 0
    _accumulator = 0.0
    _state       = "thinking"
    _winner      = None

def init():
    _start_game()

def frame(pixels, dt):
    global _state, _accumulator, _turn, _board
    global _fall_col, _fall_row, _target_row, _winner

    _accumulator += dt

    if _state == "thinking":
        _render(pixels, _board, _turn)

        if _is_full(_board):
            _winner      = None
            _state       = "game_over"
            _accumulator = 0.0
            return

        budget = THINK_TIME_MS + random.randint(-THINK_TIME_JITTER_MS, THINK_TIME_JITTER_MS)
        budget = max(50, budget)
        col = _search(_board, _turn == "R", budget)
        if col is None:
            _winner      = None
            _state       = "game_over"
            _accumulator = 0.0
            return

        _fall_col    = col
        _fall_row    = 0
        _target_row  = _drop_row(_board, col)
        _state       = "falling"
        _accumulator = 0.0

    elif _state == "falling":
        if _accumulator >= FALL_STEP_TIME and _fall_row < _target_row:
            _fall_row   += 1
            _accumulator = 0.0
        _render(pixels, _board, _turn,
                falling=(_fall_col, _fall_row, _turn, False))
        if _fall_row >= _target_row and _accumulator >= FALL_STEP_TIME:
            _board[_idx(_target_row, _fall_col)] = _turn
            _state       = "landed"
            _accumulator = 0.0

    elif _state == "landed":
        flash_on = int(_accumulator / (LANDING_FLASH / 2)) % 2 == 0
        _render(pixels, _board, _turn,
                falling=(_fall_col, _target_row, _turn, flash_on))
        if _accumulator >= LANDING_FLASH:
            if _check_win(_board, _turn):
                _winner      = _turn
                _state       = "game_over"
                _accumulator = 0.0
            else:
                _turn        = "Y" if _turn == "R" else "R"
                _state       = "waiting"
                _accumulator = 0.0

    elif _state == "waiting":
        _render(pixels, _board, _turn)
        if _accumulator >= MOVE_DELAY:
            _state       = "thinking"
            _accumulator = 0.0

    elif _state == "game_over":
        blink_on = (int(_accumulator / 0.5) % 2 == 0)
        if _winner:
            win_cells = _find_win_cells(_board, _winner)
            _render(pixels, _board, _turn, win_cells=win_cells, win_blink_on=blink_on)
        else:
            _render(pixels, _board, _turn)
        if _accumulator >= GAME_END_PAUSE:
            _start_game()
