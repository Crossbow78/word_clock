"""
animations/shared.py

Shared utilities available to all animation modules.
Imported once by the controller and passed into each module via init().
"""

import math

# ── Grid dimensions ───────────────────────────────────────────────────────────

COLS = 12
ROWS = 11
LED_COUNT = COLS * ROWS   # 132

# ── Coordinate mapping ────────────────────────────────────────────────────────

def xy(col, row):
    """
    Map (col, row) in code-space to a physical pixel index.
      col: 0 = left,  11 = right
      row: 0 = top,   10 = bottom  (y increases downward)
    Physical wiring: horizontal zig-zag, row 0 (physical bottom) goes right→left.
    """
    physical_row = ROWS - 1 - row
    if physical_row % 2 == 0:
        return physical_row * COLS + (COLS - 1 - col)
    else:
        return physical_row * COLS + col

# ── Colour helpers ────────────────────────────────────────────────────────────

def hsv_to_rgb(h, s=1.0, v=1.0):
    h = h % 1.0
    i = int(h * 6)
    f = h * 6 - i
    p, q, t = v*(1-s), v*(1-f*s), v*(1-(1-f)*s)
    r, g, b = [(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)][i % 6]
    return int(r*255), int(g*255), int(b*255)

def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def scale(color, factor):
    return tuple(int(c * max(0.0, min(1.0, factor))) for c in color)

# ── Runtime-adjustable module parameters ────────────────────────────────────
# Modules that want a "module settings" panel in the web UI declare:
#
#   PARAMS = [
#       ("text",  TEXT(),          "Hello World"),
#       ("speed", FLOAT(0.1, 5.0), 1.0),
#       ("mirror", BOOL(),         False),
#   ]
#   _params, get_params, set_param = make_param_store(PARAMS)
#
# then read live values via _params["key"] inside frame(). Modules without
# a PARAMS list simply have no settings panel — no cost either way.

class TEXT:
    kind = "TEXT"

class INT:
    kind = "INT"
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

class FLOAT:
    kind = "FLOAT"
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

class BOOL:
    kind = "BOOL"

class CHOICE:
    kind = "CHOICE"
    def __init__(self, options):
        self.options = list(options)   # fixed set of valid string values

def _coerce_param(ptype, value):
    if ptype.kind == "TEXT":
        return str(value)
    if ptype.kind == "INT":
        return max(ptype.lo, min(ptype.hi, int(value)))
    if ptype.kind == "FLOAT":
        return max(ptype.lo, min(ptype.hi, float(value)))
    if ptype.kind == "BOOL":
        return bool(value)
    if ptype.kind == "CHOICE":
        value = str(value)
        if value not in ptype.options:
            raise ValueError(f"'{value}' not in allowed options {ptype.options}")
        return value
    raise ValueError(f"unknown param kind {ptype.kind}")

def make_param_store(specs):
    """specs = [(key, type_instance, default), ...]
    Returns (values, get_params, set_param):
      values     — live mutable dict, read directly in frame()
      get_params — () -> [{"key","type","value",["min","max"]}, ...]
      set_param  — (key, value) -> None, validates/clamps by type
    """
    values = {key: default for key, _, default in specs}
    by_key = {key: ptype for key, ptype, _ in specs}

    def get_params():
        out = []
        for key, ptype, _ in specs:
            entry = {"key": key, "type": ptype.kind, "value": values[key]}
            if ptype.kind in ("INT", "FLOAT"):
                entry["min"], entry["max"] = ptype.lo, ptype.hi
            if ptype.kind == "CHOICE":
                entry["options"] = ptype.options
            out.append(entry)
        return out

    def set_param(key, value):
        if key not in by_key:
            raise KeyError(key)
        values[key] = _coerce_param(by_key[key], value)

    return values, get_params, set_param
