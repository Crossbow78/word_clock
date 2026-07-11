"""
animations/snake.py — Snake with BFS AI (non-blocking state machine)
"""

import math
import random
import collections
from .shared import COLS, ROWS, xy, lerp_color, scale

FRAME_DELAY   = 0.03
NAME          = "Snake"

STEP_DELAY    = 0.18
FLASH_ON      = 0.08
FLASH_OFF     = 0.08
FLASH_COUNT   = 3
FADE_STEPS    = 20
FADE_DELAY    = 0.04
PULSE_SPEED   = 0.15
START_LENGTH  = 3

HEAD_COLOR    = (255, 255, 255)
BODY_COLOR_A  = (  0, 200,  80)
BODY_COLOR_B  = (  0,  60,  20)
FRUIT_COLOR   = (255,  20,   0)

DIRECTIONS = [(0,1),(0,-1),(1,0),(-1,0)]

# ── State machine states ──────────────────────────────────────────────────────
# "playing"  → snake is alive, stepping on a timer
# "flashing" → death flash animation
# "fading"   → red fade-out after flashing
# "restarting" → brief pause before new game

_state       = "playing"
_accumulator = 0.0
_snake       = collections.deque()
_fruit       = None
_pulse       = 0.0
_flash_step  = 0      # which flash we're on (0..FLASH_COUNT*2)
_fade_step   = 0      # which fade step we're on
_snapshot    = []     # snake positions captured at death for fade

# ── AI helpers ────────────────────────────────────────────────────────────────

def _in_bounds(col, row):
    return 0 <= col < COLS and 0 <= row < ROWS

def _bfs(start, goal, blocked):
    if start == goal: return None
    queue   = collections.deque([(start, [])])
    visited = {start}
    while queue:
        pos, path = queue.popleft()
        for dc, dr in DIRECTIONS:
            nxt = (pos[0]+dc, pos[1]+dr)
            if nxt == goal:
                return path[0] if path else nxt
            if _in_bounds(*nxt) and nxt not in visited and nxt not in blocked:
                visited.add(nxt)
                queue.append((nxt, path+[nxt]))
    return None

def _flood(start, blocked):
    visited = {start}
    queue   = collections.deque([start])
    while queue:
        pos = queue.popleft()
        for dc, dr in DIRECTIONS:
            nxt = (pos[0]+dc, pos[1]+dr)
            if _in_bounds(*nxt) and nxt not in visited and nxt not in blocked:
                visited.add(nxt)
                queue.append(nxt)
    return len(visited)

def _ai_move(snake, fruit):
    head    = snake[0]
    blocked = set(snake[1:])
    nxt     = _bfs(head, fruit, blocked)
    if nxt is not None:
        sim_blocked = set(snake[:-1])
        sim_blocked.discard(nxt)
        if nxt == fruit or _flood(nxt, sim_blocked) > len(snake)//2:
            return nxt
    best_count, best_next = -1, None
    for dc, dr in DIRECTIONS:
        n = (head[0]+dc, head[1]+dr)
        if _in_bounds(*n) and n not in blocked:
            count = _flood(n, blocked|{n})
            if count > best_count:
                best_count, best_next = count, n
    return best_next

def _spawn_fruit(snake):
    occupied = set(snake)
    free     = [(c,r) for c in range(COLS) for r in range(ROWS) if (c,r) not in occupied]
    return random.choice(free) if free else None

# ── Drawing ───────────────────────────────────────────────────────────────────

def _draw_playing(pixels, fruit_brightness):
    for i in range(COLS*ROWS):
        pixels[i] = (0,0,0)
    n = len(_snake)
    for i, (c, r) in enumerate(_snake):
        color = HEAD_COLOR if i == 0 else lerp_color(BODY_COLOR_A, BODY_COLOR_B, i/max(n-1,1))
        pixels[xy(c, r)] = color
    fc, fr = _fruit
    pixels[xy(fc, fr)] = tuple(int(v*fruit_brightness) for v in FRUIT_COLOR)
    pixels.show()

def _draw_flash(pixels, on):
    for i in range(COLS*ROWS):
        pixels[i] = (0,0,0)
    color = (255, 0, 0) if on else (0, 0, 0)
    for c, r in _snapshot:
        pixels[xy(c, r)] = color
    pixels.show()

def _draw_fade(pixels, step):
    f = max(0.0, 1.0 - step / FADE_STEPS)
    for i in range(COLS*ROWS):
        pixels[i] = (0,0,0)
    for c, r in _snapshot:
        pixels[xy(c, r)] = (int(255*f), 0, 0)
    pixels.show()

# ── Init / reset ──────────────────────────────────────────────────────────────

def _start_game():
    global _snake, _fruit, _state, _accumulator, _pulse
    cx    = COLS // 2
    cy    = ROWS // 2
    _snake = collections.deque([(cx-i, cy) for i in range(START_LENGTH)])
    _fruit = _spawn_fruit(list(_snake))
    _state = "playing"
    _accumulator = 0.0
    _pulse = 0.0

def _start_death():
    global _state, _snapshot, _flash_step, _accumulator
    _snapshot  = list(_snake)
    _state     = "flashing"
    _flash_step = 0
    _accumulator = 0.0

def init():
    _start_game()

# ── Frame ─────────────────────────────────────────────────────────────────────

def frame(pixels, dt):
    global _state, _accumulator, _pulse, _flash_step, _fade_step, _fruit

    _accumulator += dt

    if _state == "playing":
        _pulse += PULSE_SPEED * dt / FRAME_DELAY
        fruit_brightness = 0.6 + 0.4 * math.sin(_pulse)
        _draw_playing(pixels, fruit_brightness)

        if _accumulator < STEP_DELAY:
            return
        _accumulator = 0.0

        nxt = _ai_move(list(_snake), _fruit)
        if nxt is None:
            _start_death()
            return

        _snake.appendleft(nxt)
        if nxt == _fruit:
            _fruit = _spawn_fruit(list(_snake))
            if _fruit is None:
                _start_death()
                return
        else:
            _snake.pop()

        if list(_snake).count(_snake[0]) > 1:
            _start_death()

    elif _state == "flashing":
        # Alternate on/off FLASH_COUNT times
        flash_duration = FLASH_ON if _flash_step % 2 == 0 else FLASH_OFF
        _draw_flash(pixels, on=(_flash_step % 2 == 0))

        if _accumulator < flash_duration:
            return
        _accumulator = 0.0
        _flash_step += 1

        if _flash_step >= FLASH_COUNT * 2:
            global _fade_step
            _fade_step   = 0
            _state       = "fading"

    elif _state == "fading":
        _draw_fade(pixels, _fade_step)

        if _accumulator < FADE_DELAY:
            return
        _accumulator = 0.0
        _fade_step  += 1

        if _fade_step > FADE_STEPS:
            _state       = "restarting"
            _accumulator = 0.0

    elif _state == "restarting":
        if _accumulator >= 0.5:
            _start_game()
