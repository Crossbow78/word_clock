"""
NeoPixel Grid Controller
Raspberry Pi + adafruit-circuitpython-neopixel + gpiozero

12×11 LED grid controller with group-based navigation and slideshow mode.

Button behaviour:
  Single press  → next mode within current group (cancels slideshow)
  Double press  → toggle slideshow (auto-advance every 30s)
  Long press    → next group (remembers last mode, cancels slideshow)

Groups:
  Current:    Word Clock, Weather
  Games:      Tetris AI, Snake, Chess
  Animations: Matrix Rain, Ripple, Fire, Plasma, Game of Life, Lava Lamp,
              Sand, Bouncing Balls, Flow Field, Spiral, Flags

Button wiring:
  Leg 1 → GPIO17 (pin 11)
  Leg 2 → GND    (pin 9 or any GND)

Dependencies:
    sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel noise gpiozero requests

Run with sudo:
    sudo python3 controller.py
"""

import time
import threading
import board
import neopixel
import argparse
import signal
import sys

from gpiozero import Button

from animations import (
    wordclock, matrix, ripple, plasma, life, tetris_ai,
    lavalamp, sand, balls, flowfield, spiral,
    snake, fire, weather, flags, chess
)

# ── Hardware ──────────────────────────────────────────────────────────────────

LED_PIN        = board.D12
LED_COUNT      = 132
LED_BRIGHTNESS = 0.8
LED_ORDER      = neopixel.GRB
BUTTON_PIN     = 17
FRAME_DELAY    = 0.04

# ── Groups ────────────────────────────────────────────────────────────────────

GROUPS = [
    {
        "name":  "Current",
        "modes": [wordclock, weather],
    },
    {
        "name": "Animations",
        "modes": [matrix, ripple, fire, plasma, sand, lavalamp, balls, life, flowfield, spiral, flags],
    },
    {
        "name":  "Games",
        "modes": [tetris_ai, snake, chess],
    },
]

# ── State ─────────────────────────────────────────────────────────────────────

current_group      = 0
group_mode_idx     = [0] * len(GROUPS)
hold_triggered     = False
_pending_advance   = None    # "mode" or "group" — set before transition runs
_slideshow_active  = False
_slideshow_timer   = 0.0
SLIDESHOW_INTERVAL = 30.0

def _current_mode():
    return GROUPS[current_group]["modes"][group_mode_idx[current_group]]

def _all_modes():
    return [m for g in GROUPS for m in g["modes"]]

# ── Navigation actions ────────────────────────────────────────────────────────

def _advance_mode():
    global _pending_advance
    _pending_advance = "mode"

def _advance_group():
    global _pending_advance
    _pending_advance = "group"

def _apply_advance(pending):
    """Apply a pending mode or group switch after the transition fade."""
    global current_group
    if pending == "mode":
        idx = group_mode_idx[current_group]
        group_mode_idx[current_group] = (idx + 1) % len(GROUPS[current_group]["modes"])
    elif pending == "group":
        current_group = (current_group + 1) % len(GROUPS)
    mode = _current_mode()
    if hasattr(mode, "activate"):
        mode.activate()
    label = GROUPS[current_group]["name"] if pending == "group" else ""
    print(f"  -> {('Group: ' + label + ' / ') if label else 'Mode: '}{mode.NAME}")

# ── Button handling ───────────────────────────────────────────────────────────

DOUBLE_CLICK_WINDOW = 0.35

_click_count = 0
_click_timer = None

def on_press():
    global hold_triggered
    hold_triggered = False

def on_hold():
    global hold_triggered, _slideshow_active, _slideshow_timer
    hold_triggered    = True
    #_slideshow_active = False
    _slideshow_timer  = 0.0
    _advance_group()

def on_release():
    global _click_count, _click_timer
    if hold_triggered:
        return
    _click_count += 1
    if _click_timer is not None:
        _click_timer.cancel()
    _click_timer = threading.Timer(DOUBLE_CLICK_WINDOW, _dispatch_clicks)
    _click_timer.start()

def _dispatch_clicks():
    global _click_count
    count        = _click_count
    _click_count = 0
    if count == 1:
        _do_single_click()
    elif count >= 2:
        _do_double_click()

def _do_single_click():
    global _slideshow_active, _slideshow_timer
    _slideshow_active = False
    _slideshow_timer  = 0.0
    _advance_mode()

def _do_double_click():
    global _slideshow_active, _slideshow_timer
    _slideshow_active = not _slideshow_active
    _slideshow_timer  = 0.0
    print(f"  -> Slideshow: {'ON' if _slideshow_active else 'OFF'}")

button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05, hold_time=0.8)
button.when_pressed  = on_press
button.when_held     = on_hold
button.when_released = on_release

# ── Transition fade ───────────────────────────────────────────────────────────

def _do_transition(pixels, steps=16, delay=0.02):
    """Fade current frame to black, then apply the pending mode/group switch."""
    snapshot = [pixels[i] for i in range(LED_COUNT)]
    for step in range(steps, -1, -1):
        factor = step / steps
        for i in range(LED_COUNT):
            pixels[i] = tuple(int(c * factor) for c in snapshot[i])
        pixels.show()
        time.sleep(delay)

# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    all_names = ", ".join(m.NAME for m in _all_modes())
    parser    = argparse.ArgumentParser(description="NeoPixel Grid Controller")
    parser.add_argument(
        "--mode", "-m",
        type=str,
        default=None,
        help=f"Start in a specific mode by name. Available: {all_names}"
    )
    parser.add_argument(
        "--slideshow",
        action="store_true",
        help="Start with slideshow mode enabled"
    )
    return parser.parse_args()

def _resolve_mode(name):
    key = name.lower()
    for gi, group in enumerate(GROUPS):
        for mi, mode in enumerate(group["modes"]):
            if mode.NAME.lower() == key:
                return gi, mi
    return None, None

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global current_group, _pending_advance, _slideshow_active, _slideshow_timer

    args = parse_args()

    pixels = neopixel.NeoPixel(
        LED_PIN,
        LED_COUNT,
        brightness=LED_BRIGHTNESS,
        pixel_order=LED_ORDER,
        auto_write=False,
    )

    def cleanup_and_exit(*args):
        print("Killed...")
        pixels.fill((0, 0, 0))
        pixels.show()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    # Initialise all modes
    print("Initialising animations...")
    for mode in _all_modes():
        mode.init()
        print(f"  ✓ {mode.NAME}")

    # Resolve optional startup mode
    if args.mode is not None:
        gi, mi = _resolve_mode(args.mode)
        if gi is not None:
            current_group = gi
            group_mode_idx[gi] = mi
            print(f"\nStarting in mode: {_current_mode().NAME} ({GROUPS[gi]['name']})")
        else:
            all_names = ", ".join(m.NAME for m in _all_modes())
            print(f"\nUnknown mode '{args.mode}'. Available: {all_names}")

    # Activate initial mode
    mode = _current_mode()
    if hasattr(mode, "activate"):
        mode.activate()

    if args.slideshow:
        _slideshow_active = True
        print("  Slideshow enabled from command line")

    print(f"\nStarting in group : {GROUPS[current_group]['name']}")
    print(f"Starting in mode  : {_current_mode().NAME}")
    print("Single press -> next mode")
    print("Double press -> toggle slideshow")
    print("Long press   -> next group\n")

    last_time        = time.monotonic()
    _pending_advance = None

    while True:
        now = time.monotonic()
        dt  = now - last_time
        last_time = now

        # Fade out current mode, then switch
        if _pending_advance is not None:
            _do_transition(pixels)
            _apply_advance(_pending_advance)
            _pending_advance = None

        # Slideshow auto-advance
        if _slideshow_active:
            _slideshow_timer += dt
            if _slideshow_timer >= SLIDESHOW_INTERVAL:
                _slideshow_timer = 0.0
                _advance_mode()

        mode  = _current_mode()
        delay = getattr(mode, "FRAME_DELAY", FRAME_DELAY)
        mode.frame(pixels, dt)
        time.sleep(max(0.02, delay))

if __name__ == "__main__":
    main()
