"""
animations/lightning.py — Lightning strikes

A shimmering dark orange background (subtle random flicker) interrupted by
jagged lightning bolts that grow from top to bottom, optionally branch,
then decay through a return-stroke flicker.

States:
  "idle"     — background noise, waiting for next strike
  "growing"  — bolt grows downward one row per frame
  "flash"    — full bolt at peak brightness
  "decay"    — bolt fades through dimming steps + return stroke
  "recharge" — brief dark pause before idle resumes
"""

import random
import time as _time
from .shared import COLS, ROWS, xy, scale

FRAME_DELAY = 0.03
NAME        = "Lightning"

# ── Configuration ─────────────────────────────────────────────────────────────

# Background flicker
BG_COLOR     = (50, 20, 0)     # dark orange base
BG_FLICKER   = 0.15            # random brightness range around base
BG_SMOOTH    = 0.10            # drift speed toward new target (0=frozen, 1=instant)

# Idle period between strikes (seconds)
CALM_MIN     = 2.0
CALM_MAX     = 8.0

# Bolt growth
GROW_DELAY   = 0.03            # seconds per row while growing

# Bolt colours
BOLT_HEAD    = (220, 240, 255) # bright cold white-blue head
BOLT_CORE    = (180, 210, 255) # slightly dimmer core
BOLT_BRANCH  = (120, 160, 220) # branches slightly dimmer

# Flash envelope — (brightness, duration_seconds) steps after full bolt visible
FLASH_STEPS = [
    (1.00, 0.05),
    (0.80, 0.03),
    (1.00, 0.02),   # return stroke re-brighten
    (0.60, 0.04),
    (0.30, 0.05),
    (0.10, 0.06),
    (0.00, 0.00),
]

# Branch probability and max length
BRANCH_CHANCE  = 0.6
BRANCH_MAX_LEN = 3

# ── Bolt generation ───────────────────────────────────────────────────────────

def _gen_bolt():
    col  = random.randint(3, COLS - 4)
    path = []
    for row in range(ROWS):
        path.append((col, row))
        col += random.choice([-1, -1, 0, 0, 0, 1, 1])
        col  = max(0, min(COLS - 1, col))
    return path

def _gen_branch(bolt_path):
    if random.random() > BRANCH_CHANCE or len(bolt_path) < 4:
        return []
    start_idx = random.randint(2, len(bolt_path) - 3)
    col, row  = bolt_path[start_idx]
    branch    = []
    direction = random.choice([-1, 1])
    length    = random.randint(2, BRANCH_MAX_LEN)
    for i in range(length):
        col += direction
        row += 1
        if not (0 <= col < COLS and 0 <= row < ROWS):
            break
        branch.append((col, row))
    return branch

# ── Background ────────────────────────────────────────────────────────────────

_bg_brightness = [
    [random.uniform(0.15, 0.35) for _ in range(COLS)]
    for _ in range(ROWS)
]

def _draw_bg(pixels):
    for r in range(ROWS):
        for c in range(COLS):
            target = random.uniform(0.15 - BG_FLICKER * 0.5, 0.15 + BG_FLICKER)
            _bg_brightness[r][c] += (target - _bg_brightness[r][c]) * BG_SMOOTH
            pixels[xy(c, r)] = scale(BG_COLOR, max(0.0, _bg_brightness[r][c]))

def _draw_bolt(pixels, bolt, branch, brightness):
    for col, row in bolt:
        pixels[xy(col, row)] = scale(BOLT_CORE, brightness)
    if bolt:
        c, r = bolt[-1]
        pixels[xy(c, r)] = scale(BOLT_HEAD, brightness)
    for col, row in branch:
        pixels[xy(col, row)] = scale(BOLT_BRANCH, brightness * 0.7)

# ── State ─────────────────────────────────────────────────────────────────────

_state       = "idle"
_accumulator = 0.0
_calm_until  = 0.0

_bolt        = []
_branch      = []
_grow_row    = 0
_flash_step  = 0
_flash_acc   = 0.0

def init():
    global _state, _accumulator, _calm_until
    _state       = "idle"
    _accumulator = 0.0
    _calm_until  = _time.monotonic() + random.uniform(CALM_MIN, CALM_MAX)

def frame(pixels, dt):
    global _state, _accumulator, _calm_until
    global _bolt, _branch, _grow_row, _flash_step, _flash_acc

    _accumulator += dt

    if _state == "idle":
        _draw_bg(pixels)
        pixels.show()
        if _time.monotonic() >= _calm_until:
            _bolt        = _gen_bolt()
            _branch      = _gen_branch(_bolt)
            _grow_row    = 0
            _flash_step  = 0
            _flash_acc   = 0.0
            _state       = "growing"
            _accumulator = 0.0

    elif _state == "growing":
        if _accumulator < GROW_DELAY:
            return
        _accumulator = 0.0
        _grow_row   += 1

        _draw_bg(pixels)
        visible_bolt   = _bolt[:_grow_row]
        visible_branch = [p for p in _branch if p[1] < _grow_row]
        _draw_bolt(pixels, visible_bolt, visible_branch, brightness=1.0)
        pixels.show()

        if _grow_row >= len(_bolt):
            _state      = "flash"
            _flash_step = 0
            _flash_acc  = 0.0

    elif _state == "flash":
        if _flash_step >= len(FLASH_STEPS):
            _state       = "recharge"
            _accumulator = 0.0
            return

        brightness, duration = FLASH_STEPS[_flash_step]
        _draw_bg(pixels)
        _draw_bolt(pixels, _bolt, _branch, brightness)
        pixels.show()

        _flash_acc += dt
        if _flash_acc >= duration:
            _flash_acc  = 0.0
            _flash_step += 1

    elif _state == "recharge":
        _draw_bg(pixels)
        pixels.show()
        if _accumulator >= 0.3:
            _calm_until  = _time.monotonic() + random.uniform(CALM_MIN, CALM_MAX)
            _state       = "idle"
            _accumulator = 0.0
