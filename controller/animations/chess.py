"""
animations/chess.py — Chess with time-bounded minimax AI (iterative deepening + alpha-beta)

Two AI players play a full game of chess on an 8×8 board.
Pieces are colour-coded by type, brightness indicates player.
Captured pieces shown on the right, turn indicator on the left.

Layout (all parametric — adjust constants below):
  Board:      cols BOARD_COL .. BOARD_COL+7, rows BOARD_ROW .. BOARD_ROW+7
  Turn white: col  TURN_COL,  row TURN_WHITE_ROW
  Turn black: col  TURN_COL,  row TURN_BLACK_ROW
  Cap white:  cols CAP_COLS,  rows CAP_WHITE_ROWS  (left→right, top→bottom)
  Cap black:  cols CAP_COLS,  rows CAP_BLACK_ROWS
  Overflow:   col  CAP_OVERFLOW_COL (used when cap slots are full)
"""

import time
import math
import random
import copy
from .shared import COLS, ROWS, xy

FRAME_DELAY  = 0.05
NAME         = "Chess"

# ── Layout parameters ─────────────────────────────────────────────────────────

BOARD_COL        = 1      # leftmost column of the board
BOARD_ROW        = 1      # topmost row of the board

TURN_COL         = 0      # column for turn indicators
TURN_WHITE_ROW   = 9      # row for white turn indicator
TURN_BLACK_ROW   = 0      # row for black turn indicator

CAP_COLS         = [11, 10]          # captured piece columns, filled left→right
CAP_OVERFLOW_COL = 9                 # third column if > 10 captures per side
CAP_WHITE_ROWS   = list(range(9, 4, -1)) # rows 5-9 for white captures
CAP_BLACK_ROWS   = list(range(0, 5))     # rows 0–4 for black captures

# ── Timing ────────────────────────────────────────────────────────────────────

MOVE_DELAY       = 1.0    # seconds between moves (gives CPU breathing room)
ANIM_FLASH_TIME  = 0.15   # duration of each flash step
GAME_END_PAUSE   = 3.0    # pause at checkmate/stalemate before restart

THINK_TIME_MS        = 1500  # base thinking budget per move (milliseconds)
THINK_TIME_JITTER_MS = 500   # +/- random variation per move, for a bit of personality
MAX_DEPTH            = 6     # hard cap on search depth regardless of time left

# ── Piece colours ─────────────────────────────────────────────────────────────
# Bright = white player, dim = black player (factor applied to color)

PIECE_COLORS = {
    "K": (255, 220,   0),   # King    — gold
    "Q": (220,   0, 220),   # Queen   — magenta
    "R": (220,  30,  30),   # Rook    — red
    "B": (30,   80, 220),   # Bishop  — blue
    "N": (30,  200,  60),   # Knight  — green
    "P": (180,  80,  10),   # Pawn    — amber
}

WHITE_BRIGHTNESS = 1.0
BLACK_BRIGHTNESS = 0.18

SQUARE_LIGHT     = ( 45,  45,  45)   # light squares
SQUARE_DARK      = ( 10,  10,  10)   # dark squares
TURN_COLOR       = (255, 255, 255)   # turn indicator pixel
TURN_DIM         = (  0,   0,   0)   # inactive turn indicator

# ── Chess engine ──────────────────────────────────────────────────────────────

# Piece values for evaluation
PIECE_VALUES = {"K": 0, "Q": 900, "R": 500, "B": 330, "N": 320, "P": 100}

# Board representation: list of 64 squares
# Each square: None or (piece_type, color) where color = "W" or "B"
# Index: row * 8 + col, row 0 = rank 8 (black's back rank), row 7 = rank 1 (white's back rank)

def _start_board():
    b = [None] * 64
    back = ["R","N","B","Q","K","B","N","R"]
    for c, p in enumerate(back):
        b[0*8+c] = (p, "B")
        b[7*8+c] = (p, "W")
    for c in range(8):
        b[1*8+c] = ("P", "B")
        b[6*8+c] = ("P", "W")
    return b

def _idx(r, c): return r * 8 + c
def _pos(i):    return i // 8, i % 8

def _on_board(r, c): return 0 <= r < 8 and 0 <= c < 8

def _moves_for(board, idx, check_castle=True):
    """Generate pseudo-legal moves for piece at idx. Returns list of (from, to) tuples."""
    piece = board[idx]
    if piece is None: return []
    pt, color = piece
    opp = "B" if color == "W" else "W"
    r, c = _pos(idx)
    moves = []

    def slide(dirs):
        for dr, dc in dirs:
            nr, nc = r+dr, c+dc
            while _on_board(nr, nc):
                t = board[_idx(nr,nc)]
                if t is None:
                    moves.append((idx, _idx(nr,nc)))
                elif t[1] == opp:
                    moves.append((idx, _idx(nr,nc)))
                    break
                else:
                    break
                nr += dr; nc += dc

    def step(dirs):
        for dr, dc in dirs:
            nr, nc = r+dr, c+dc
            if _on_board(nr, nc):
                t = board[_idx(nr,nc)]
                if t is None or t[1] == opp:
                    moves.append((idx, _idx(nr,nc)))

    if pt == "R": slide([(0,1),(0,-1),(1,0),(-1,0)])
    elif pt == "B": slide([(1,1),(1,-1),(-1,1),(-1,-1)])
    elif pt == "Q": slide([(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)])
    elif pt == "N": step([(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)])
    elif pt == "K": step([(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)])
    elif pt == "P":
        dr = -1 if color == "W" else 1
        start_row = 6 if color == "W" else 1
        # Forward
        nr = r + dr
        if _on_board(nr, c) and board[_idx(nr,c)] is None:
            moves.append((idx, _idx(nr,c)))
            # Double push from start
            if r == start_row and board[_idx(nr+dr,c)] is None:
                moves.append((idx, _idx(nr+dr,c)))
        # Captures
        for dc in (-1, 1):
            nc = c + dc
            if _on_board(nr, nc):
                t = board[_idx(nr,nc)]
                if t is not None and t[1] == opp:
                    moves.append((idx, _idx(nr,nc)))
    return moves

def _all_moves(board, color):
    moves = []
    for i in range(64):
        if board[i] and board[i][1] == color:
            moves.extend(_moves_for(board, i))
    return moves

def _apply_move(board, move):
    """Return new board with move applied. Handles pawn promotion."""
    b = board[:]
    frm, to = move
    piece = b[frm]
    b[to]  = piece
    b[frm] = None
    # Pawn promotion to queen
    if piece[0] == "P":
        tr, tc = _pos(to)
        if (piece[1] == "W" and tr == 0) or (piece[1] == "B" and tr == 7):
            b[to] = ("Q", piece[1])
    return b

def _king_pos(board, color):
    for i in range(64):
        if board[i] == ("K", color):
            return i
    return None

def _in_check(board, color):
    opp  = "B" if color == "W" else "W"
    king = _king_pos(board, color)
    if king is None: return True
    for move in _all_moves(board, opp):
        if move[1] == king:
            return True
    return False

def _legal_moves(board, color):
    """Filter pseudo-legal moves to only those that don't leave king in check."""
    legal = []
    for move in _all_moves(board, color):
        nb = _apply_move(board, move)
        if not _in_check(nb, color):
            legal.append(move)
    return legal

def _evaluate(board):
    """Simple material + centre control evaluation, from white's perspective."""
    score = 0
    centre = {_idx(3,3), _idx(3,4), _idx(4,3), _idx(4,4)}
    for i in range(64):
        p = board[i]
        if p is None: continue
        val = PIECE_VALUES[p[0]]
        if i in centre: val += 10
        score += val if p[1] == "W" else -val
    return score

class _TimeUp(Exception):
    """Raised to unwind the search once the thinking-time budget is spent."""
    pass

def _minimax(board, depth, alpha, beta, maximising, deadline=float("inf")):
    if time.monotonic() >= deadline:
        raise _TimeUp()

    color = "W" if maximising else "B"
    moves = _legal_moves(board, color)

    if depth == 0 or not moves:
        return _evaluate(board), None

    # Shuffle first so ties in move_priority (and in alpha-beta best-so-far
    # comparisons) break differently game to game — an easy hook for variation.
    random.shuffle(moves)

    # Move ordering: captures first
    def move_priority(m):
        return 0 if board[m[1]] is not None else 1

    moves.sort(key=move_priority)

    best_move = moves[0]
    if maximising:
        best = -999999
        for move in moves:
            nb  = _apply_move(board, move)
            val, _ = _minimax(nb, depth-1, alpha, beta, False, deadline)
            if val > best:
                best, best_move = val, move
            alpha = max(alpha, best)
            if beta <= alpha: break
        return best, best_move
    else:
        best = 999999
        for move in moves:
            nb  = _apply_move(board, move)
            val, _ = _minimax(nb, depth-1, alpha, beta, True, deadline)
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
    """Convert board (row, col) to pixel (col, row) in grid space."""
    return BOARD_COL + bc, BOARD_ROW + br

def _piece_color(piece, highlight=False):
    pt, color = piece
    base  = PIECE_COLORS[pt]
    bri   = WHITE_BRIGHTNESS if color == "W" else BLACK_BRIGHTNESS
    if highlight: bri = min(1.0, bri + 0.5)
    return tuple(int(c * bri) for c in base)

def _square_color(br, bc):
    return SQUARE_LIGHT if (br + bc) % 2 == 0 else SQUARE_DARK

def _render(pixels, board, captured_w, captured_b,
            current_turn, highlight=None, hide=None):
    # Clear all pixels
    for i in range(COLS * ROWS):
        pixels[i] = (0, 0, 0)

    # Draw board squares and pieces
    for br in range(8):
        for bc in range(8):
            gc, gr = _board_xy(br, bc)
            idx    = _idx(br, bc)
            piece  = board[idx]
            sq     = _square_color(br, bc)

            if hide and idx in hide:
                pixels[xy(gc, gr)] = sq
            elif piece:
                lit = highlight and idx in highlight
                pixels[xy(gc, gr)] = _piece_color(piece, highlight=lit)
            else:
                pixels[xy(gc, gr)] = sq

    # Turn indicator
    pixels[xy(TURN_COL, TURN_WHITE_ROW)] = TURN_COLOR if current_turn == "W" else TURN_DIM
    pixels[xy(TURN_COL, TURN_BLACK_ROW)] = TURN_COLOR if current_turn == "B" else TURN_DIM

    # Captured pieces — white captures (pieces black lost)
    all_cap_slots = (
        [(col, r) for r in CAP_WHITE_ROWS for col in CAP_COLS] +   # cols 11,10 first
        [(CAP_OVERFLOW_COL, r) for r in CAP_WHITE_ROWS]             # col 9 overflow
    )
    for i, piece in enumerate(captured_b[:len(all_cap_slots)]):
        gc, gr = all_cap_slots[i]
        pixels[xy(gc, gr)] = _piece_color(piece)

    # Captured pieces — black captures (pieces white lost)
    all_cap_slots_b = (
        [(col, r) for r in CAP_BLACK_ROWS for col in CAP_COLS] +
        [(CAP_OVERFLOW_COL, r) for r in CAP_BLACK_ROWS]
    )
    for i, piece in enumerate(captured_w[:len(all_cap_slots_b)]):
        gc, gr = all_cap_slots_b[i]
        pixels[xy(gc, gr)] = _piece_color(piece)

    pixels.show()

# ── State machine ─────────────────────────────────────────────────────────────
# States:
#   "thinking"   — AI computing next move (runs synchronously, brief freeze)
#   "flashing"   — flash source piece once
#   "toggling"   — toggle piece between src and dst twice
#   "landing"    — place piece at destination
#   "waiting"    — pause before next move
#   "game_over"  — checkmate or stalemate, pause then restart

_board_state  = []
_turn         = "W"
_captured_w   = []   # pieces white lost (captured by black)
_captured_b   = []   # pieces black lost (captured by white)
_pending_move = None
_anim_step    = 0
_accumulator  = 0.0
_state        = "thinking"
_move_src     = None
_move_dst     = None
_moved_piece  = None
_toggle_count = 0

def _start_game():
    global _board_state, _turn, _captured_w, _captured_b
    global _pending_move, _state, _accumulator
    _board_state  = _start_board()
    _turn         = "W"
    _captured_w   = []
    _captured_b   = []
    _pending_move = None
    _state        = "thinking"
    _accumulator  = 0.0

def init():
    _start_game()

def frame(pixels, dt):
    global _state, _accumulator, _turn, _board_state
    global _pending_move, _move_src, _move_dst, _moved_piece
    global _anim_step, _toggle_count, _captured_w, _captured_b

    _accumulator += dt

    if _state == "thinking":
        # Render current position while thinking
        _render(pixels, _board_state, _captured_w, _captured_b, _turn)

        # Compute best move (blocking but brief at depth 2)
        legal = _legal_moves(_board_state, _turn)
        if not legal:
            _state = "game_over"
            _accumulator = 0.0
            return

        budget = THINK_TIME_MS + random.randint(-THINK_TIME_JITTER_MS, THINK_TIME_JITTER_MS)
        budget = max(50, budget)
        move = _search(_board_state, _turn == "W", budget)
        if move is None:
            _state = "game_over"
            _accumulator = 0.0
            return

        _move_src    = move[0]
        _move_dst    = move[1]
        _moved_piece = _board_state[_move_src]
        _anim_step   = 0
        _toggle_count = 0
        _state       = "flashing"
        _accumulator = 0.0

    elif _state == "flashing":
        # Flash source piece on/off once
        show_piece = (_anim_step % 2 == 0)
        _render(pixels, _board_state, _captured_w, _captured_b, _turn,
                highlight={_move_src} if show_piece else None,
                hide=None if show_piece else {_move_src})
        if _accumulator >= ANIM_FLASH_TIME:
            _accumulator = 0.0
            _anim_step  += 1
            if _anim_step >= 2:   # one full flash
                _state     = "toggling"
                _anim_step = 0

    elif _state == "toggling":
        # Toggle piece between src and dst twice
        at_dst = (_anim_step % 2 == 1)
        hide   = {_move_src if not at_dst else _move_dst}
        # Temporarily show piece at dst for toggling
        sim_board = _board_state[:]
        if at_dst:
            sim_board[_move_dst] = _moved_piece
            sim_board[_move_src] = None
        _render(pixels, sim_board, _captured_w, _captured_b, _turn,
                highlight={_move_dst if at_dst else _move_src})
        if _accumulator >= ANIM_FLASH_TIME:
            _accumulator  = 0.0
            _anim_step   += 1
            if _anim_step >= 4:   # two full toggles
                _state = "landing"

    elif _state == "landing":
        # Apply move to board
        captured = _board_state[_move_dst]
        if captured:
            if _turn == "W":
                _captured_b.append(captured)
            else:
                _captured_w.append(captured)
        _board_state = _apply_move(_board_state, (_move_src, _move_dst))
        _render(pixels, _board_state, _captured_w, _captured_b, _turn,
                highlight={_move_dst})
        # Switch turn
        _turn  = "B" if _turn == "W" else "W"
        _state = "waiting"
        _accumulator = 0.0

    elif _state == "waiting":
        _render(pixels, _board_state, _captured_w, _captured_b, _turn)
        if _accumulator >= MOVE_DELAY:
            _state       = "thinking"
            _accumulator = 0.0

    elif _state == "game_over":
        # Slowly blink the defeated king (the side that just moved lost)
        defeated = _turn   # _turn already switched to the side that can't move
        king_idx = _king_pos(_board_state, defeated)

        blink_on = (int(_accumulator / 0.6) % 2 == 0)   # 0.6s per blink step

        _render(pixels, _board_state, _captured_w, _captured_b, _turn,
            highlight={king_idx} if blink_on and king_idx is not None else None,
            hide={king_idx}      if not blink_on and king_idx is not None else None)

        if _accumulator >= 10.0:
            _start_game()
