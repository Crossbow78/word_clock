"""
animations/flags.py — Waving national flags

Cycles through: Netherlands, Belgium, France, Japan, Switzerland, Spain.
Each flag waves for one full cycle (~8 seconds) then cross-fades to the next.

Flag stripes are defined as horizontal or vertical bands.
Wave motion is a sine displacement per column with subpixel blending
within stripes. Stripe boundaries are kept sharp to avoid colour mixing.

Dependencies: none beyond shared
"""

import math
from .shared import COLS, ROWS, xy

FRAME_DELAY   = 0.04
NAME          = "Flags"

# ── Wave parameters ───────────────────────────────────────────────────────────

WAVE_SPEED     = 0.8     # radians per second
WAVE_AMPLITUDE = 0.0     # pixels of vertical displacement
WAVE_FREQUENCY = 0.8     # spatial frequency (cycles across the strip)
CYCLE_DURATION = 8.0     # seconds per flag (one full wave cycle)
FADE_DURATION  = 2.0     # seconds for cross-fade between flags

# ── Flag definitions ──────────────────────────────────────────────────────────
# Each flag is a list of stripes.
# Horizontal flags: axis="h", bands divide the ROWS vertically
# Vertical flags:   axis="v", bands divide the COLS horizontally
# Each band: (fraction_end, (R, G, B))
# fraction_end is the upper boundary of this band as a 0–1 fraction of the axis

FLAGS = [
    {
        "name": "Netherlands",
        "axis": "h",   # horizontal stripes
        "stripes": [
            (1/3, (193,   0,  42)),   # red
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
            (1.0, (193,   0,  42)),   # red
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
            (1.0, (227,  15,  30)),   # red
        ],
    },
    {
        "name": "Switzerland",
        "axis": "h",
        "stripes": [
            (1.0, (255,   0,  40)),   # red background
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
            (1.0, (206,   0,  28)),   # red
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
            "color": (188,   0,  45),
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
            (2/3, (221,   0,   0)),   # red
            (1.0, (255, 206,   0)),   # gold
        ],
    },
    {
        "name": "Italy",
        "axis": "h",
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
    """
    Return the base colour for a pixel at normalised position (norm_h, norm_v).
    norm_h = row / ROWS, norm_v = col / COLS, both 0–1.
    """
    axis = flag.get("axis", "h")
    pos  = norm_h if axis == "h" else norm_v

    # Find which stripe this position falls in
    color = flag["stripes"][-1][1]
    for frac, c in flag["stripes"]:
        if pos <= frac:
            color = c
            break

    # Japan disc overlay
    if "disc" in flag:
        d   = flag["disc"]
        cx  = d["cx"]
        cy  = d["cy"]
        r   = d["r"] * min(COLS, ROWS)
        dx  = (norm_v - cx) * COLS
        dy  = (norm_h - cy) * ROWS
        if math.sqrt(dx**2 + dy**2) <= r:
            color = d["color"]

    # Switzerland cross overlay
    if "cross" in flag:
        col_n, row_n = norm_v, norm_h
        for cs, ce, rs, re in flag["cross"]["rects"]:
            if cs <= col_n <= ce and rs <= row_n <= re:
                color = flag["cross"]["color"]
                break

    return color

def _render_flag(flag, t):
    """
    Render a flag into a 2D buffer with wave displacement.
    Returns buf[row][col] = (r, g, b).
    """
    buf = [[(0,0,0)] * COLS for _ in range(ROWS)]

    for col in range(COLS):
        # Wave: vertical sine displacement for this column
        wave = WAVE_AMPLITUDE * math.sin(
            WAVE_FREQUENCY * (col / COLS) * math.pi * 2 - t * WAVE_SPEED
        )

        for row in range(ROWS):
            # Displaced row in float space
            src_row = row + wave

            # Clamp to grid bounds
            src_row = max(0.0, min(ROWS - 1.0, src_row))

            row0  = int(src_row)
            row1  = min(row0 + 1, ROWS - 1)
            blend = src_row - row0

            # Sample pixel centres for even stripe distribution
            norm_h0 = (row0 + 0.5) / ROWS
            norm_h1 = (row1 + 0.5) / ROWS
            norm_v  = (col  + 0.5) / COLS

            c0 = _stripe_color(flag, norm_h0, norm_v)
            c1 = _stripe_color(flag, norm_h1, norm_v)

            # Only blend if both pixels are the same colour (within stripe)
            # At stripe boundaries keep sharp by snapping to nearest
            if c0 == c1:
                color = c0
            elif blend < 0.5:
                color = c0
            else:
                color = c1

            buf[row][col] = color

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

_t            = 0.0          # animation time
_flag_index   = 0
_flag_time    = 0.0          # time spent on current flag
_state        = "showing"    # "showing" or "fading"
_fade_time    = 0.0

def init():
    global _t, _flag_index, _flag_time, _state, _fade_time
    _t          = 0.0
    _flag_index = 0
    _flag_time  = 0.0
    _fade_time  = 0.0
    _state      = "showing"

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
