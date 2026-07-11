"""
animations/weather.py — Animated weather display using Open-Meteo
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

ICON_ROWS        = ROWS - 1   # rows 0–9 for icon
TEMP_ROW         = ROWS - 1   # row 10 = bottom

# ── Weather state ─────────────────────────────────────────────────────────────

_weather = {
    "icon": "sun", "temp": 15.0, "temp_min": 10.0,
    "temp_max": 20.0, "is_day": True, "error": False,
}

def _wmo_to_icon(code, is_day):
    if code == 0:               return "sun" if is_day else "night"
    elif code in (1, 2):        return "partly_cloudy" if is_day else "night"
    elif code == 3:             return "cloudy"
    elif code in (45, 48):      return "fog"
    elif code in (51,53,55,61,63,65,80,81,82): return "rain"
    elif code in (71,73,75,77,85,86):          return "snow"
    elif code in (95,96,99):    return "thunder"
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
        data  = requests.get(url, timeout=15).json()
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
    except Exception as e:
        print(f"  Weather fetch failed: {e}")
        _weather["error"] = True
    return _weather["error"]

def _refresh_loop():
    while True:
        has_error = _fetch()
        if has_error:
            time.sleep(60)
        else:
            time.sleep(REFRESH_SECONDS)

# ── Frame buffer ──────────────────────────────────────────────────────────────

_buf = [[(0,0,0)]*COLS for _ in range(ROWS)]

def _clear_icon():
    for r in range(ICON_ROWS):
        for c in range(COLS):
            _buf[r][c] = (0,0,0)

def _push(pixels):
    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = _buf[r][c]
    pixels.show()

# ── Temperature bar ───────────────────────────────────────────────────────────

def _draw_temp_bar():
    cold, hot = (0,80,255), (255,40,0)
    for c in range(COLS):
        _buf[TEMP_ROW][c] = scale(lerp_color(cold, hot, c/(COLS-1)), 0.5)
    t_range = _weather["temp_max"] - _weather["temp_min"]
    if t_range > 0:
        mc = int((_weather["temp"] - _weather["temp_min"]) / t_range * (COLS-1))
        _buf[TEMP_ROW][max(0, min(COLS-1, mc))] = (255,255,255)

# ── Cloud helpers ─────────────────────────────────────────────────────────────

CLOUD_BLOBS = [
    ( 0.0,  0.0, 2.8),
    ( 2.5,  0.2, 2.2),
    (-2.5,  0.2, 2.0),
    ( 1.0, -1.5, 1.8),
    (-1.0, -1.5, 1.5),
]
CLOUD_CX       = 5.5
CLOUD_ROW      = 2.5
RAIN_START_ROW = 5

def _cloud_col_range():
    left  = int(min(CLOUD_CX + bc - r for bc, _, r in CLOUD_BLOBS))
    right = int(max(CLOUD_CX + bc + r for bc, _, r in CLOUD_BLOBS))
    return max(0, left), min(COLS-1, right)

def _draw_cloud(offset_c, offset_r, brightness=1.0):
    for bc, br, radius in CLOUD_BLOBS:
        for r in range(ICON_ROWS):
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

# ── Icon draw functions ───────────────────────────────────────────────────────

def _draw_sun(t):
    _clear_icon()
    cx, cy = 5.5, 4.5
    for r in range(ICON_ROWS):
        for c in range(COLS):
            dist = math.sqrt((c-cx)**2 + (r-cy)**2)
            if dist < 3.5:
                _buf[r][c] = scale((255,200,0), max(0.0, 1.0-dist/3.5))
    for ray in range(8):
        angle = t + ray * math.pi/4
        for d in range(3, 6):
            ri = int(round(cy + math.sin(angle)*d))
            ci = int(round(cx + math.cos(angle)*d))
            if 0 <= ri < ICON_ROWS and 0 <= ci < COLS:
                _buf[ri][ci] = scale((255,180,0), max(0.0, 1.0-(d-3)/3.0)*0.8)


# ── Night: evenly spread stars ────────────────────────────────────────────────
# Divide the icon area into a grid of zones, place one star per zone
# with a small random offset to avoid a mechanical look.
# Moon occupies top-right, so exclude that region from star placement.

_MOON_CX   = 9.5   # moon centre col
_MOON_CY   = 3.5   # moon centre row
_MOON_R    = 3.2   # moon disc radius (for exclusion zone)

def _gen_star_positions(n=11):
    """Generate n evenly spread star positions avoiding the moon area."""
    positions = []
    attempts  = 0
    # Tile the icon area into a grid and jitter within each cell
    cols_div = 4
    rows_div = 3
    cells    = [(c, r) for r in range(rows_div) for c in range(cols_div)]
    random.shuffle(cells)
    for gc, gr in cells:
        if len(positions) >= n:
            break
        col = int((gc / cols_div) * COLS + random.uniform(0.5, COLS / cols_div - 0.5))
        row = int((gr / rows_div) * ICON_ROWS + random.uniform(0.5, ICON_ROWS / rows_div - 0.5))
        col = max(0, min(COLS - 1, col))
        row = max(0, min(ICON_ROWS - 1, row))
        # Skip if too close to moon
        if math.sqrt((col - _MOON_CX)**2 + (row - _MOON_CY)**2) < _MOON_R + 1:
            continue
        positions.append((col, row))
    return positions

_star_pos   = _gen_star_positions(11)
# Each star gets a unique phase and speed for independent twinkling
_star_phase = [random.uniform(0, math.pi * 2) for _ in _star_pos]
_star_speed = [random.uniform(1.5, 3.5)       for _ in _star_pos]

def _draw_night(t):
    _clear_icon()

    # ── Moon crescent ─────────────────────────────────────────────────────────
    # Draw a bright disc then subtract a slightly offset disc to form crescent.
    # Offset disc centre is shifted right and slightly down.
    cx, cy   = _MOON_CX, _MOON_CY
    r_disc   = _MOON_R
    # Offset of the "bite" disc
    ox, oy   = 2.5, 0
    r_bite   = r_disc * 1.05   # slightly larger so the edge is clean

    for r in range(ICON_ROWS):
        for c in range(COLS):
            d_moon = math.sqrt((c - cx)**2 + (r - cy)**2)
            d_bite = math.sqrt((c - (cx + ox))**2 + (r - (cy + oy))**2)
            if d_moon < r_disc and d_bite >= r_bite:
                # Inside moon disc but outside bite → visible crescent
                brightness = max(0.0, 1.0 - d_moon / r_disc) * 0.9 + 0.1
                # Warm yellow-white moon colour
                _buf[r][c] = scale((255, 240, 100), brightness)

    # ── Stars with punchy sparkle ─────────────────────────────────────────────
    for i, (c, r) in enumerate(_star_pos):
        # Raw sine value
        raw = math.sin(_star_phase[i] + t * _star_speed[i])
        # Raise to power to sharpen the peak — bright flash, long dim period
        sparkle = max(0.0, raw) ** 3
        # Minimum ambient glow so stars are always faintly visible
        brightness = 0.08 + 0.92 * sparkle
        _buf[r][c] = scale((210, 220, 255), brightness)

_cloud_drift = 0.0

def _draw_cloudy(t):
    global _cloud_drift
    _clear_icon()
    _cloud_drift = math.sin(t*0.5)*1.5
    _draw_cloud(CLOUD_CX + _cloud_drift, 4.0)

def _draw_partly_cloudy(t):
    _clear_icon()
    cx, cy = 8.5, 2.5
    for r in range(ICON_ROWS):
        for c in range(COLS):
            dist = math.sqrt((c-cx)**2 + (r-cy)**2)
            if dist < 2.2:
                _buf[r][c] = scale((255,200,0), max(0.0, 1.0-dist/2.2))
    for ray in range(8):
        angle = t + ray*math.pi/4
        for d in range(2, 4):
            ri = int(round(cy + math.sin(angle)*d))
            ci = int(round(cx + math.cos(angle)*d))
            if 0 <= ri < ICON_ROWS and 0 <= ci < COLS:
                _buf[ri][ci] = scale((255,180,0), max(0.0, 1.0-(d-2)/2.0)*0.7)
    _draw_cloud(4.5 + math.sin(t*0.5)*1.0, 5.5, brightness=0.95)

_rain_drops = [{"c": random.uniform(2,9), "r": random.uniform(RAIN_START_ROW, ICON_ROWS)}
               for _ in range(14)]

def _draw_rain(t):
    _clear_icon()
    _draw_cloud(CLOUD_CX, CLOUD_ROW, brightness=0.85)
    col_min, col_max = _cloud_col_range()
    for drop in _rain_drops:
        drop["r"] += 0.3
        if drop["r"] >= ICON_ROWS:
            drop["r"] = float(RAIN_START_ROW)
            drop["c"] = random.uniform(col_min, col_max)
        ri, ci = int(drop["r"]), int(drop["c"])
        if 0 <= ri < ICON_ROWS and 0 <= ci < COLS:
            _buf[ri][ci] = (80,120,255)
        if 0 <= ri-1 < ICON_ROWS:
            _buf[ri-1][ci] = (30,60,140)

_thunder_timer = 0
_thunder_flash = False

def _draw_thunder(t):
    global _thunder_timer, _thunder_flash
    _clear_icon()
    _draw_cloud(CLOUD_CX, CLOUD_ROW, brightness=0.85)
    col_min, col_max = _cloud_col_range()
    for drop in _rain_drops:
        drop["r"] += 0.3
        if drop["r"] >= ICON_ROWS:
            drop["r"] = float(RAIN_START_ROW)
            drop["c"] = random.uniform(col_min, col_max)
        ri, ci = int(drop["r"]), int(drop["c"])
        if 0 <= ri < ICON_ROWS and 0 <= ci < COLS:
            _buf[ri][ci] = (80,120,255)
    _thunder_timer -= 1
    if _thunder_timer <= 0:
        _thunder_flash = not _thunder_flash
        _thunder_timer = random.randint(3,25) if not _thunder_flash else random.randint(1,3)
    if _thunder_flash:
        for bc, br in [(5,5),(5,6),(6,6),(6,7),(5,7),(5,8)]:
            if 0 <= br < ICON_ROWS:
                _buf[br][bc] = (255,255,100)

_snow_flakes = [{"c": random.uniform(2,9), "r": random.uniform(RAIN_START_ROW, ICON_ROWS),
                 "drift": random.uniform(-0.05,0.05)} for _ in range(12)]

def _draw_snow(t):
    _clear_icon()
    _draw_cloud(CLOUD_CX, CLOUD_ROW, brightness=0.7)
    col_min, col_max = _cloud_col_range()
    for flake in _snow_flakes:
        flake["r"] += 0.15
        flake["c"] += flake["drift"] + math.sin(t + flake["r"])*0.05
        flake["c"]  = max(0, min(COLS-1, flake["c"]))
        if flake["r"] >= ICON_ROWS:
            flake["r"] = float(RAIN_START_ROW)
            flake["c"] = random.uniform(col_min, col_max)
        ri, ci = int(flake["r"]), int(flake["c"])
        if 0 <= ri < ICON_ROWS and 0 <= ci < COLS:
            _buf[ri][ci] = (200,220,255)

def _draw_fog(t):
    _clear_icon()
    for r in range(ICON_ROWS):
        for c in range(COLS):
            n = (math.sin(c*0.6 + t*0.4 + r*0.3) * math.sin(r*0.5 + t*0.3) * 0.5 + 0.5)
            _buf[r][c] = scale((180,190,200), n*0.45)

_ICON_FUNCS = {
    "sun": _draw_sun, "night": _draw_night, "cloudy": _draw_cloudy,
    "partly_cloudy": _draw_partly_cloudy, "rain": _draw_rain,
    "thunder": _draw_thunder, "snow": _draw_snow, "fog": _draw_fog,
}

# ── Module interface ──────────────────────────────────────────────────────────

_t          = 0.0
_started    = False

def init():
    global _t, _started
    _t = 0.0
    if not _started:
        _fetch()   # blocking initial fetch
        thread = threading.Thread(target=_refresh_loop, daemon=True)
        thread.start()
        _started = True

def frame(pixels, dt):
    global _t
    _ICON_FUNCS.get(_weather["icon"], _draw_sun)(_t)
    _draw_temp_bar()
    _push(pixels)
    _t += 0.025
    _t %= math.pi * 40
