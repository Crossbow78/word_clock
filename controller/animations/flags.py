"""
animations/flags.py — Waving national flags

Cycles through a collection of national flags.
Each flag displays for CYCLE_DURATION seconds then cross-fades to the next.
A horizontal brightness wave rolls across the flag to simulate fabric movement.

Dependencies: none beyond shared
"""

import math
import random
from .shared import COLS, ROWS, xy

FRAME_DELAY   = 0.04
NAME          = "Flags"

# ── Wave parameters ───────────────────────────────────────────────────────────

BRIGHTNESS_WAVE_SPEED = 1.8    # how fast the wave travels left→right
BRIGHTNESS_WAVE_FREQ  = 1.6    # spatial frequency (cycles across the flag)
BRIGHTNESS_MIN        = 0.4    # darkest point of the wave
BRIGHTNESS_MAX        = 1.0    # brightest point

CYCLE_DURATION = 5.0           # seconds per flag
FADE_DURATION  = 1.5           # seconds for cross-fade between flags

# ── Flag definitions ──────────────────────────────────────────────────────────

FLAGS = [
    {
        "name": "Netherlands",
        "axis": "h",   # horizontal stripes
        "stripes": [
            (1/3, (193,   0,  20)),   # red
            (2/3, (255, 255, 255)),   # white
            (1.0, ( 15,  20, 159)),   # blue
        ],
    },
    {
        "name": "Belgium",
        "axis": "v",   # vertical stripes
        "stripes": [
            (1/3, ( 10,  10,  10)),   # black
            (2/3, (253, 218,  36)),   # yellow
            (1.0, (193,   0,  20)),   # red
        ],
    },
    {
        "name": "Ukraine",
        "axis": "h",
        "stripes": [
            (1/2, (  0,  87, 183)),   # blue
            (1.0, (255, 215,   0)),   # yellow
        ],
    },
    {
        "name": "France",
        "axis": "v",
        "stripes": [
            (1/3, (  0,  35, 149)),   # blue
            (2/3, (255, 255, 255)),   # white
            (1.0, (227,  0,  20)),   # red
        ],
    },
    {
        "name": "Switzerland",
        "axis": "h",
        "stripes": [
            (1.0, (255,   0,  20)),   # red background
        ],
        "cross": {
            "color": (255, 255, 255),
            # Cross defined as two rectangles in fraction coords
            # (col_start, col_end, row_start, row_end)
            "rects": [
                (0.35, 0.65, 0.20, 0.80),   # vertical bar
                (0.20, 0.80, 0.35, 0.65),   # horizontal bar
            ],
        },
    },
    {
        "name": "Romania",
        "axis": "v",
        "stripes": [
            (1/3, (  0,  43, 127)),   # blue
            (2/3, (252, 209,  22)),   # yellow
            (1.0, (206,   0,  20)),   # red
        ],
    },
    {
        "name": "Japan",
        "axis": "h",
        "stripes": [
            # White background with red disc in the centre
            # Represented as a single white field; disc drawn separately
            (1.0, (255, 255, 255)),
        ],
        "disc": {
            "cx": 0.5,    # fraction of COLS
            "cy": 0.5,    # fraction of ROWS
            "r":  0.25,   # fraction of min(COLS, ROWS)
            "color": (196,   0,  20),
        },
    },
    {
        "name": "Spain",
        "axis": "h",
        "stripes": [
            (0.25, (193,   0,  22)),   # red
            (0.75, (241, 189,   0)),   # yellow
            (1.00, (193,   0,  22)),   # red
        ],
    },
    {
        "name": "Indonesia",
        "axis": "h",
        "stripes": [
            (1/2, (206,   0,  22)),   # red
            (1.0, (255, 255, 255)),   # white
        ],
    },
    {
        "name": "Germany",
        "axis": "h",
        "stripes": [
            (1/3, ( 10,  10,  10)),   # black
            (2/3, (221,   0,  10)),   # red
            (1.0, (255, 206,   0)),   # gold
        ],
    },
    {
        "name": "Italy",
        "axis": "v",
        "stripes": [
            (1/3, (  0, 170,  30)),   # green
            (2/3, (255, 255, 255)),   # white
            (1.0, (206,   0,  15)),   # red
        ],
    },
    {
        "name": "Russia",
        "axis": "h",
        "stripes": [
            (1/3, (255, 255, 255)),   # white
            (2/3, (  0,  57, 166)),   # blue
            (1.0, (195,   0,  20)),   # red
        ],
    },
    {
        "name": "Austria",
        "axis": "h",
        "stripes": [
            (1/3, (237,  11,  27)),   # red
            (2/3, (255, 255, 255)),   # white
            (1.0, (237,  11,  27)),   # red
        ],
    },
    {
        "name": "Thailand",
        "axis": "h",
        "stripes": [
            ( 2/11, (195,   0,  18)),   # red
            ( 4/11, (255, 255, 255)),   # white
            ( 7/11, ( 25,  26, 160)),   # blue  (3 rows)
            ( 9/11, (255, 255, 255)),   # white
            (11/11, (195,   0,  18)),   # red
        ],
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _stripe_color(flag, norm_h, norm_v):
    axis  = flag.get("axis", "h")
    pos   = norm_h if axis == "h" else norm_v
    color = flag["stripes"][-1][1]
    for frac, c in flag["stripes"]:
        if pos <= frac:
            color = c
            break
    if "disc" in flag:
        d  = flag["disc"]
        r  = d["r"] * min(COLS, ROWS)
        dx = (norm_v - d["cx"]) * COLS
        dy = (norm_h - d["cy"]) * ROWS
        if math.sqrt(dx**2 + dy**2) <= r:
            color = d["color"]
    if "cross" in flag:
        for cs, ce, rs, re in flag["cross"]["rects"]:
            if cs <= norm_v <= ce and rs <= norm_h <= re:
                color = flag["cross"]["color"]
                break
    return color

def _render_flag(flag, t):
    """Render flag with horizontal brightness wave. Returns buf[row][col]."""
    buf = [[(0,0,0)] * COLS for _ in range(ROWS)]
    for col in range(COLS):
        wave_brightness = BRIGHTNESS_MIN + (BRIGHTNESS_MAX - BRIGHTNESS_MIN) * (
            math.sin(
                col / COLS * math.pi * 2 * BRIGHTNESS_WAVE_FREQ
                - t * BRIGHTNESS_WAVE_SPEED
            ) * 0.5 + 0.5
        )
        norm_v = (col + 0.5) / COLS
        for row in range(ROWS):
            norm_h = (row + 0.5) / ROWS
            color  = _stripe_color(flag, norm_h, norm_v)
            buf[row][col] = tuple(int(c * wave_brightness) for c in color)
    return buf

def _lerp_buf(buf_a, buf_b, t):
    """Cross-fade between two frame buffers."""
    out = [[(0,0,0)] * COLS for _ in range(ROWS)]
    for r in range(ROWS):
        for c in range(COLS):
            a, b = buf_a[r][c], buf_b[r][c]
            out[r][c] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return out

# ── State ─────────────────────────────────────────────────────────────────────

_t          = 0.0
_flag_index = 0
_flag_time  = 0.0
_state      = "showing"
_fade_time  = 0.0

def init():
    global _t, _flag_index, _flag_time, _state, _fade_time
    _t          = 0.0
    _flag_index = 0
    _flag_time  = 0.0
    _fade_time  = 0.0
    _state      = "showing"

def activate():
    random.shuffle(FLAGS)
    init()

def frame(pixels, dt):
    global _t, _flag_index, _flag_time, _state, _fade_time

    _t         += dt
    _flag_time += dt

    current_flag = FLAGS[_flag_index]
    next_flag    = FLAGS[(_flag_index + 1) % len(FLAGS)]

    if _state == "showing":
        if _flag_time >= CYCLE_DURATION:
            _state     = "fading"
            _fade_time = 0.0
        buf = _render_flag(current_flag, _t)

    elif _state == "fading":
        _fade_time += dt
        progress    = min(1.0, _fade_time / FADE_DURATION)
        buf_a = _render_flag(current_flag, _t)
        buf_b = _render_flag(next_flag,    _t)
        buf   = _lerp_buf(buf_a, buf_b, progress)
        if progress >= 1.0:
            _flag_index = (_flag_index + 1) % len(FLAGS)
            _flag_time  = 0.0
            _state      = "showing"
            print(f"  → Flag: {FLAGS[_flag_index]['name']}")

    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = buf[r][c]
    pixels.show()
