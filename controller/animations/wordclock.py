"""
animations/wordclock.py — Word Clock

Displays the current time as words on the 12×11 LED grid.
Updates only when the displayed text changes (typically every 5 minutes).
Each word gets a random colour; brightness dims in the evening and at night.
On the hour, plays a GIF animation before showing the new time.

Adapted from github.com/johniak/word-clock — pixel writes go through
the controller's shared pixels object and xy().

Word layout (pixel 131 = top-left, 0 = bottom-right):
  131 ITLISASTHPMA 120
  108 ACFIFTEENDCO 119
  107 TWENTYFIVEXW 096
  084 THIRTYXTENXW 095
  083 MINUTESETOUR 072
  060 PASTORUFOURT 071
  059 SEVENXTWELVE 048
  036 NINEFIVECTWO 047
  035 EIGHTFELEVEN 024
  012 SIXTHREEONEG 023
  011 TENSEZOCLOCK 000
"""

import random
import time
from datetime import datetime
from PIL import Image
from .shared import COLS, ROWS, xy

FRAME_DELAY = 1.0    # check every second; only redraws when words change
NAME        = "Word Clock"

# ── GIF ───────────────────────────────────────────────────────────────────────

GIF_PATH     = "./assets/heart.gif"
GIF_DURATION = 4.0   # seconds to play the gif on hour change

# ── Word → LED index ranges (inclusive) ──────────────────────────────────────

WORDS_TO_LEDS = {
    "HOUR_1":     (20, 22),
    "HOUR_2":     (45, 47),
    "HOUR_3":     (15, 19),
    "HOUR_4":     (67, 70),
    "HOUR_5":     (40, 43),
    "HOUR_6":     (12, 14),
    "HOUR_7":     (55, 59),
    "HOUR_8":     (31, 35),
    "HOUR_9":     (36, 39),
    "HOUR_10":    ( 9, 11),
    "HOUR_11":    (24, 29),
    "HOUR_12":    (48, 53),
    "OCLOCK":     ( 0,  5),
    "PAST":       (60, 63),
    "TO":         (63, 64),
    "MINUTES":    (77, 83),
    "THIRTY":     (84, 89),
    "TWENTY":     (102,107),
    "TWENTYFIVE": (98, 107),
    "FIVE":       (98, 101),
    "TEN":        (91,  93),
    "FIFTEEN":    (110,116),
    "IS":         (127,128),
    "IT":         (130,131),
}

# ── Colour palette ────────────────────────────────────────────────────────────

COLORS = [
    (255,  20,  20),
    ( 20, 255,  20),
    ( 20,  20, 255),
    (255, 255,  20),
    (255,  20, 255),
    ( 20, 255, 255),
    (255, 255, 255),
    (255, 120,  40),
]

DIM_FACTOR_DARK   = 0.12
DIM_FACTOR_DIMMED = 0.50
DIM_FACTOR_NORMAL = 1.00

# ── Coordinate mapping ────────────────────────────────────────────────────────

def _strip_index_to_xy(idx):
    """
    Convert raw word-clock strip index (0-131) to pixel index via xy().
    The HAL uses y=0 at the bottom; xy() handles the physical wiring flip
    internally so we pass y directly without inverting.
    """
    NUM_LEDS = COLS * ROWS

    for y in range(ROWS):
        if y % 2 == 0:
            row_start = NUM_LEDS - y * COLS
            row_end   = NUM_LEDS - y * COLS - COLS
            if row_end <= idx <= row_start:
                x = row_start - idx - 1
                return xy(x, y)
        else:
            row_start = NUM_LEDS - (y + 1) * COLS
            row_end   = row_start + COLS - 1
            if row_start <= idx <= row_end:
                x = idx - row_start
                return xy(x, y)
    return None

# Pre-compute strip index -> pixel index lookup table at import time
_STRIP_TO_PIXEL = {}
for _i in range(COLS * ROWS):
    _p = _strip_index_to_xy(_i)
    if _p is not None:
        _STRIP_TO_PIXEL[_i] = _p

# ── Helpers ───────────────────────────────────────────────────────────────────

_next_color = None

def _shuffle_colors():
    global _next_color
    random.shuffle(COLORS)
    _next_color = 0

def _random_color():
    global _next_color
    color = COLORS[_next_color]
    _next_color += 1
    _next_color %= len(COLORS)
    return color

def _scale(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)

def _dim_factor(hour):
    if hour >= 23 or hour <= 5:
        return DIM_FACTOR_DARK
    elif hour >= 19 or hour <= 7:
        return DIM_FACTOR_DIMMED
    return DIM_FACTOR_NORMAL

def _minutes_word(minute):
    if   minute <  5: return "OCLOCK"
    elif minute < 10: return "FIVE"
    elif minute < 15: return "TEN"
    elif minute < 20: return "FIFTEEN"
    elif minute < 25: return "TWENTY"
    elif minute < 30: return "TWENTYFIVE"
    elif minute < 35: return "THIRTY"
    elif minute < 40: return "TWENTYFIVE"
    elif minute < 45: return "TWENTY"
    elif minute < 50: return "FIFTEEN"
    elif minute < 55: return "TEN"
    else:             return "FIVE"

def _words_for_time(hour, minute):
    words = ["IT", "IS"]
    hour  = hour % 12 or 12
    if minute < 5:
        words.append("OCLOCK")
    elif minute < 35:
        words += ["MINUTES", "PAST"]
    else:
        words += ["MINUTES", "TO"]
        hour = (hour % 12) + 1
    words.append(_minutes_word(minute))
    words.append(f"HOUR_{hour}")
    return words

def _display_word(pixels, word, color):
    start, end = WORDS_TO_LEDS[word]
    for i in range(start, end + 1):
        pixel_idx = _STRIP_TO_PIXEL.get(i)
        if pixel_idx is not None:
            pixels[pixel_idx] = color

def _display_gif(pixels):
    try:
        img        = Image.open(GIF_PATH)
        start_time = time.time()
        while time.time() < start_time + GIF_DURATION:
            try:
                frame      = img.convert("RGBA").resize((COLS, ROWS))
                gif_pixels = frame.load()
                for r in range(ROWS):
                    for c in range(COLS):
                        pr, pg, pb, a = gif_pixels[c, r]
                        pixels[xy(c, r)] = (pr, pg, pb) if a > 0 else (0, 0, 0)
                pixels.show()
                time.sleep(0.1)
                img.seek(img.tell() + 1)
            except EOFError:
                img.seek(0)
    except Exception as e:
        print(f"  GIF error: {e}")

# ── State ─────────────────────────────────────────────────────────────────────

_last_words  = ""
_last_hour   = -1
_accumulator = 0.0

def init():
    global _last_words, _last_hour, _accumulator
    _last_words  = ""
    _last_hour   = -1
    _accumulator = 0.0

def activate():
    global _last_words
    _last_words = ""   # force redraw on next frame

def frame(pixels, dt):
    global _last_words, _last_hour, _accumulator

    _accumulator += dt
    if _accumulator < 1.0:
        return
    _accumulator = 0.0

    now    = datetime.now()
    hour   = now.hour
    minute = now.minute
    dim    = _dim_factor(hour)
    words  = _words_for_time(hour, minute)
    key    = ",".join(words)

    # Only redraw when the displayed words change
    if key == _last_words:
        return
    _last_words = key

    # Play GIF on the hour
    hour_12 = hour % 12 or 12
    if hour_12 != _last_hour:
        _display_gif(pixels)
    _last_hour = hour_12

    # Draw words
    for i in range(COLS * ROWS):
        pixels[i] = (0, 0, 0)

    _shuffle_colors()
    for word in words:
        _display_word(pixels, word, _scale(_random_color(), dim))

    pixels.show()
