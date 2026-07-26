"""
animations/weather.py — Animated weather display using Open-Meteo

Layout:
  Rows 0–10  — animated weather icon (full grid, anchored top-left)
  Rows 6–10  — temperature overlay (bottom-right, rendered on top)

Temperature display (12px wide, right-aligned):
  [minus 2px][gap 1px][digit 3px][gap 1px][digit 3px][gap 1px][degree 1px]
  Single digit: right-aligned against degree pixel, minus area blank.
  Colour gradient: 0°→blue, 20°→yellow, 40°→red (clamped outside range).

Dependencies: requests, Pillow (only if using GIF — not used here)
"""

import time
import math
import random
import threading
import requests
from .shared import COLS, ROWS, xy, lerp_color, scale, hsv_to_rgb

FRAME_DELAY      = 0.05
NAME             = "Weather"

LATITUDE         = 51.4416
LONGITUDE        = 5.4697
REFRESH_SECONDS  = 30 * 60

# ── Temperature display layout ────────────────────────────────────────────────

TEMP_ROW_START   = 6    # top row of temperature display (rows 6–10)
TEMP_ROW_END     = 10   # bottom row (inclusive)
# Column layout (right-aligned, 12px wide):
# col 0–1  : minus sign (2px wide, 1px tall, vertically centred)
# col 2    : gap
# col 3–5  : tens digit  (or units if single digit)
# col 6    : gap
# col 7–9  : units digit (blank if single digit and tens shown)
# col 10   : gap
# col 11   : degree pixel (top-right of temp area)

DEGREE_COL       = 11
DEGREE_ROW       = TEMP_ROW_START + 1 # degree pixel near top-right of temp area
MINUS_ROW        = TEMP_ROW_START + 2 # vertically centred in 5-row font
DIGIT_POSITIONS  = [3, 7]             # left col of each digit slot

# ── 3×5 mini font ─────────────────────────────────────────────────────────────
# Each digit: list of 5 rows, each row is a 3-bit bitmask (MSB = left col)

MINI_FONT = {
    "0": [0b111, 0b101, 0b101, 0b101, 0b111],
    "1": [0b010, 0b110, 0b010, 0b010, 0b111],
    "2": [0b111, 0b001, 0b111, 0b100, 0b111],
    "3": [0b111, 0b001, 0b111, 0b001, 0b111],
    "4": [0b101, 0b101, 0b111, 0b001, 0b001],
    "5": [0b111, 0b100, 0b111, 0b001, 0b111],
    "6": [0b111, 0b100, 0b111, 0b101, 0b111],
    "7": [0b111, 0b001, 0b001, 0b001, 0b001],
    "8": [0b111, 0b101, 0b111, 0b101, 0b111],
    "9": [0b111, 0b101, 0b111, 0b001, 0b111],
}

# ── Temperature colour gradient ───────────────────────────────────────────────

COLD_COLOR = (  0,  20, 255)   # deep blue
MID_COLOR  = (255, 200,   0)   # amber at 20°C
HOT_COLOR  = (255,  10,   0)   # deep red

def _temp_color(temp):
    t = max(0.0, min(1.0, (temp + 10) / 50.0))
    if t < 0.5:
        a, b = (0, 20, 255), (255, 200, 0)   # blue → amber
        t2 = t * 2
    else:
        a, b = (255, 200, 0), (255, 10, 0)   # amber → red
        t2 = (t - 0.5) * 2
    return tuple(int(a[i] + (b[i] - a[i]) * t2) for i in range(3))

# ── Weather state ─────────────────────────────────────────────────────────────

_weather = {
    "icon": "sun", "temp": 15.0, "temp_min": 10.0,
    "temp_max": 20.0, "is_day": True, "error": False,
}

def _wmo_to_icon(code, is_day):
    if code == 0:                           return "sun" if is_day else "night"
    elif code in (1, 2):                    return "partly_cloudy" if is_day else "night"
    elif code == 3:                         return "cloudy"
    elif code in (45, 48):                  return "fog"
    elif code in (51,53,55,61,63,65,80,81,82): return "rain"
    elif code in (71,73,75,77,85,86):       return "snow"
    elif code in (95,96,99):                return "thunder"
    return "sun"

def _fetch():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&current=temperature_2m,weathercode,is_day"
        "&daily=temperature_2m_max,temperature_2m_min"
        "&timezone=auto&forecast_days=1"
    )
    try:
        data  = requests.get(url, timeout=20).json()
        curr  = data["current"]
        daily = data["daily"]
        _weather["temp"]      = curr["temperature_2m"]
        _weather["temp_min"]  = daily["temperature_2m_min"][0]
        _weather["temp_max"]  = daily["temperature_2m_max"][0]
        _weather["is_day"]    = bool(curr["is_day"])
        _weather["icon"]      = _wmo_to_icon(curr["weathercode"], curr["is_day"])
        _weather["error"]     = False
        print(f"  Weather: {_weather['icon']}, {_weather['temp']:.1f}°C "
              f"(min {_weather['temp_min']:.1f} / max {_weather['temp_max']:.1f})")
        return True
    except Exception as e:
        print(f"  Weather fetch failed: {e}")
        _weather["error"] = True
        return False

def _refresh_loop():
    while True:
        success = _fetch()
        time.sleep(REFRESH_SECONDS if success else 60)

# ── Frame buffer ──────────────────────────────────────────────────────────────

_buf = [[(0,0,0)]*COLS for _ in range(ROWS)]

def _clear():
    for r in range(ROWS):
        for c in range(COLS):
            _buf[r][c] = (0,0,0)

def _push(pixels):
    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = _buf[r][c]
    pixels.show()

# ── Temperature overlay ───────────────────────────────────────────────────────

def _draw_digit(digit_char, left_col, color):
    """Draw a 3×5 digit at left_col, rows TEMP_ROW_START..TEMP_ROW_END."""
    if digit_char not in MINI_FONT:
        return
    rows = MINI_FONT[digit_char]
    for dr, bits in enumerate(rows):
        r = TEMP_ROW_START + dr
        for dc in range(3):
            if bits & (0b100 >> dc):
                c = left_col + dc
                if 0 <= c < COLS and 0 <= r < ROWS:
                    _buf[r][c] = color

def _draw_temperature():
    temp    = _weather["temp"]
    color   = _temp_color(temp)
    neg     = temp < 0
    abs_t   = int(abs(temp))
    tens    = abs_t // 10
    units   = abs_t % 10

    # Degree pixel — top-right of temp area
    _buf[DEGREE_ROW][DEGREE_COL] = color

    if tens > 0:
        # Two digit number: tens at slot 0, units at slot 1
        _draw_digit(str(tens),  DIGIT_POSITIONS[0], color)
        _draw_digit(str(units), DIGIT_POSITIONS[1], color)
        minus_cols = (0, 1)
    else:
        # Single digit: right-aligned at slot 1
        _draw_digit(str(units), DIGIT_POSITIONS[1], color)
        minus_cols = (5, 6)

    # Minus sign: 2 pixels wide, vertically centred
    if neg:
        _buf[MINUS_ROW][minus_cols[0]] = color
        _buf[MINUS_ROW][minus_cols[1]] = color

# ── Cloud helpers ─────────────────────────────────────────────────────────────

CLOUD_BLOBS = [
    ( 0.0,  0.0, 2.8),
    ( 2.5,  0.2, 2.2),
    (-2.5,  0.2, 2.0),
    ( 1.0, -1.5, 1.8),
    (-1.0, -1.5, 1.5),
]
CLOUD_CX       = 4.5    # shifted left to anchor icon top-left
CLOUD_ROW      = 2.5
RAIN_START_ROW = 5

def _cloud_col_range():
    left  = int(min(CLOUD_CX + bc - r for bc, _, r in CLOUD_BLOBS))
    right = int(max(CLOUD_CX + bc + r for bc, _, r in CLOUD_BLOBS))
    return max(0, left), min(COLS-1, right)

def _draw_cloud(offset_c, offset_r, brightness=1.0):
    for bc, br, radius in CLOUD_BLOBS:
        for r in range(ROWS):
            for c in range(COLS):
                dist = math.sqrt((c-(offset_c+bc))**2 + (r-(offset_r+br))**2)
                if dist < radius:
                    b  = max(0.0, (1.0 - dist/radius) * brightness)
                    ex = _buf[r][c]
                    _buf[r][c] = (
                        min(255, ex[0] + int(180*b)),
                        min(255, ex[1] + int(180*b)),
                        min(255, ex[2] + int(190*b)),
                    )

# ── Icon draw functions (anchored top-left) ───────────────────────────────────

def _draw_sun(t):
    cx, cy = 4.0, 3.0
    for r in range(ROWS):
        for c in range(COLS):
            dist = math.sqrt((c-cx)**2 + (r-cy)**2)
            if dist < 2.5:
                _buf[r][c] = scale((255,180,45), max(0.0, 1.0-dist/2.5) * 0.75)
    for ray in range(8):
        angle = t + ray * math.pi/4
        for d in range(3, 5):
            ri = int(round(cy + math.sin(angle)*d))
            ci = int(round(cx + math.cos(angle)*d))
            if 0 <= ri < ROWS and 0 <= ci < COLS:
                _buf[ri][ci] = scale((255,180,45), max(0.0, 1.0-(d-3)/2.0) * 0.45)

# Fixed star positions — evenly distributed across the full 12×11 grid
_STARS = [
    (1, 0), (7, 0), (10, 0),
    (3, 2), (9, 2),
    (0, 4), (6, 4), (11, 4),
    (2, 6), (8, 6),
    (4, 8), (10, 8),
    (1, 10),(7, 10),
]
_star_state = [
    {
        "sparkling": False,
        "sparkle_t": 0.0,
        "next_sparkle": 0, # Dummy value
    }
    for _ in _STARS
]

# Each star has an independent sparkle timer
def _init_stars():
    now = time.monotonic()
    for i, (c, r) in enumerate(_STARS):
        _star_state[i]["sparkling"] = False
        _star_state[i]["next_sparkle"] = now + random.uniform(0.5, 12.0)

STAR_DIM        = 0.06    # base brightness when idle
STAR_SPARKLE    = 1.0     # peak brightness during sparkle
SPARKLE_DURATION = 1.5    # seconds for a full sparkle fade-in/out

def _draw_night(t):
    now = time.monotonic()
    for i, (c, r) in enumerate(_STARS):
        s = _star_state[i]

        if s["sparkling"]:
            # Smooth sine fade-in/out over SPARKLE_DURATION
            progress   = (now - s["sparkle_t"]) / SPARKLE_DURATION
            if progress >= 1.0:
                s["sparkling"]    = False
                s["next_sparkle"] = now + random.uniform(3.0, 12.0)
                brightness = STAR_DIM
            else:
                brightness = STAR_DIM + (STAR_SPARKLE - STAR_DIM) * math.sin(progress * math.pi)
        else:
            brightness = STAR_DIM
            if now >= s["next_sparkle"]:
                s["sparkling"] = True
                s["sparkle_t"] = now

        _buf[r][c] = scale((210, 220, 255), brightness)

_cloud_drift = 0.0

def _draw_cloudy(t):
    global _cloud_drift
    _cloud_drift = math.sin(t*0.5)*1.5
    _draw_cloud(CLOUD_CX + _cloud_drift, CLOUD_ROW)

def _draw_partly_cloudy(t):
    cx, cy = 3.0, 2.0
    for r in range(ROWS):
        for c in range(COLS):
            dist = math.sqrt((c-cx)**2 + (r-cy)**2)
            if dist < 2.0:
                _buf[r][c] = scale((255,180,45), max(0.0, 1.0-dist/2.0)*0.75)
    for ray in range(8):
        angle = t + ray*math.pi/4
        for d in range(2, 4):
            ri = int(round(cy + math.sin(angle)*d))
            ci = int(round(cx + math.cos(angle)*d))
            if 0 <= ri < ROWS and 0 <= ci < COLS:
                _buf[ri][ci] = scale((255,180,45), max(0.0, 1.0-(d-2)/2.0)*0.45)
    _draw_cloud(CLOUD_CX + math.sin(t*0.4)*1.0, CLOUD_ROW + 2.0, brightness=0.95)

_rain_drops = [{"c": random.uniform(1,7), "r": random.uniform(RAIN_START_ROW, ROWS)}
               for _ in range(14)]

def _draw_rain(t):
    _draw_cloud(CLOUD_CX, CLOUD_ROW, brightness=0.85)
    col_min, col_max = _cloud_col_range()
    for drop in _rain_drops:
        drop["r"] += 0.3
        if drop["r"] >= ROWS:
            drop["r"] = float(RAIN_START_ROW)
            drop["c"] = random.uniform(col_min, col_max)
        ri, ci = int(drop["r"]), int(drop["c"])
        if 0 <= ri < ROWS and 0 <= ci < COLS:
            _buf[ri][ci] = (80,120,255)
        if 0 <= ri-1 < ROWS:
            _buf[ri-1][ci] = (30,60,140)

_thunder_timer = 0
_thunder_flash = False

def _draw_thunder(t):
    global _thunder_timer, _thunder_flash
    _draw_cloud(CLOUD_CX, CLOUD_ROW, brightness=0.85)
    col_min, col_max = _cloud_col_range()
    for drop in _rain_drops:
        drop["r"] += 0.3
        if drop["r"] >= ROWS:
            drop["r"] = float(RAIN_START_ROW)
            drop["c"] = random.uniform(col_min, col_max)
        ri, ci = int(drop["r"]), int(drop["c"])
        if 0 <= ri < ROWS and 0 <= ci < COLS:
            _buf[ri][ci] = (80,120,255)
    _thunder_timer -= 1
    if _thunder_timer <= 0:
        _thunder_flash = not _thunder_flash
        _thunder_timer = random.randint(3,25) if not _thunder_flash else random.randint(1,3)
    if _thunder_flash:
        for bc, br in [(4,5),(4,6),(5,6),(5,7),(4,7),(4,8)]:
            if 0 <= br < ROWS:
                _buf[br][bc] = (255,255,100)

_snow_flakes = [{"c": random.uniform(1,7), "r": random.uniform(RAIN_START_ROW, ROWS),
                 "drift": random.uniform(-0.05,0.05)} for _ in range(12)]

def _draw_snow(t):
    _draw_cloud(CLOUD_CX, CLOUD_ROW, brightness=0.7)
    col_min, col_max = _cloud_col_range()
    for flake in _snow_flakes:
        flake["r"] += 0.15
        flake["c"] += flake["drift"] + math.sin(t + flake["r"])*0.05
        flake["c"]  = max(0, min(COLS-1, flake["c"]))
        if flake["r"] >= ROWS:
            flake["r"] = float(RAIN_START_ROW)
            flake["c"] = random.uniform(col_min, col_max)
        ri, ci = int(flake["r"]), int(flake["c"])
        if 0 <= ri < ROWS and 0 <= ci < COLS:
            _buf[ri][ci] = (200,220,255)

def _draw_fog(t):
    for r in range(ROWS):
        for c in range(COLS):
            n = (math.sin(c*0.6 + t*0.4 + r*0.3) * math.sin(r*0.5 + t*0.3) * 0.5 + 0.5)
            _buf[r][c] = scale((180,190,200), n*0.45)

_ICON_FUNCS = {
    "sun":           _draw_sun,
    "night":         _draw_night,
    "cloudy":        _draw_cloudy,
    "partly_cloudy": _draw_partly_cloudy,
    "rain":          _draw_rain,
    "thunder":       _draw_thunder,
    "snow":          _draw_snow,
    "fog":           _draw_fog,
}

# ── Module interface ──────────────────────────────────────────────────────────

_t       = 0.0
_started = False

def init():
    global _t, _started
    _t = 0.0
    if not _started:
        _fetch()
        thread = threading.Thread(target=_refresh_loop, daemon=True)
        thread.start()
        _started = True

def activate():
    global _t
    _t = 0.0 # Restart animation on activation
    _init_stars()

def frame(pixels, dt):
    global _t
    _clear()
    _ICON_FUNCS.get(_weather["icon"], _draw_sun)(_t)
    _draw_temperature()   # rendered on top of icon
    _push(pixels)
    _t = (_t + 0.05) % (math.pi * 40)
