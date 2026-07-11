"""
NeoPixel Grid Controller
Raspberry Pi + adafruit-circuitpython-neopixel + gpiozero

12×11 LED grid controller. Button on GPIO17 navigates a two-level
group / mode hierarchy.

  Short press → next mode within current group
  Long press  → next group (remembers last mode per group)

Groups:
  Current:    Word Clock, Weather
  Games:      Tetris AI, Snake, Chess
  Animations: Matrix Rain, Ripple, Fire, Plasma, Lava Lamp, Sand,
              Bouncing Balls, Game of Life, Flow Field, Spiral, Flags

Button wiring:
  Leg 1 → GPIO17 (pin 11)
  Leg 2 → GND    (pin 9 or any GND)

Dependencies:
    sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel noise gpiozero requests

Run with sudo:
    sudo python3 controller.py
"""

import time
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
        "name": "Current",
        "modes": [wordclock, weather],
    },
    {
        "name": "Animations",
        "modes": [matrix, ripple, fire, plasma, sand, lavalamp, balls, life, flowfield, spiral, flags],
    },
    {
        "name": "Games",
        "modes": [tetris_ai, snake, chess],
    },
]

# ── State ─────────────────────────────────────────────────────────────────────

current_group  = 0
# Remember last mode index per group
group_mode_idx = [0] * len(GROUPS)
hold_triggered = False

def _current_mode():
    return GROUPS[current_group]["modes"][group_mode_idx[current_group]]

def _activate_mode():
    mode = _current_mode()
    if hasattr(mode, "activate"):
        mode.activate()

# ── Button handling ───────────────────────────────────────────────────────────

def on_press():
    global hold_triggered
    hold_triggered = False

def on_hold():
    global hold_triggered, current_group
    hold_triggered = True

    # Cycle to next group
    current_group = (current_group + 1) % len(GROUPS)
    group = GROUPS[current_group]
    print(f"  → Group: {group['name']} / {_current_mode().NAME}")

    # Brief black flash to signal group switch
    # (handled in main loop via _flash_pending flag)
    global _flash_pending
    _flash_pending = True

def on_release():
    global group_mode_idx
    if not hold_triggered:
        group  = GROUPS[current_group]
        modes  = group["modes"]
        group_mode_idx[current_group] = (group_mode_idx[current_group] + 1) % len(modes)
        _activate_mode()
        print(f"  → Mode: {mode.NAME}")

button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05, hold_time=0.8)
button.when_pressed  = on_press
button.when_held     = on_hold
button.when_released = on_release

# ── Group switch flash ────────────────────────────────────────────────────────

_flash_pending = False

def _do_group_flash(pixels):
    pixels.fill((0, 0, 0))
    pixels.show()
    time.sleep(0.2)

# ── Argument parsing ──────────────────────────────────────────────────────────

def _all_modes():
    return [m for g in GROUPS for m in g["modes"]]

def parse_args():
    all_names = ", ".join(m.NAME for m in _all_modes())
    parser = argparse.ArgumentParser(description="NeoPixel Grid Controller")
    parser.add_argument(
        "--mode", "-m",
        type=str,
        default=None,
        help=f"Start in a specific mode by name. Available: {all_names}"
    )
    return parser.parse_args()

def _resolve_mode(name):
    """Find group and mode index for a given mode name (case-insensitive)."""
    key = name.lower()
    for gi, group in enumerate(GROUPS):
        for mi, mode in enumerate(group["modes"]):
            if mode.NAME.lower() == key:
                return gi, mi
    return None, None

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global current_group, _flash_pending

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

    # Initialise all modes at startup
    print("Initialising animations...")
    for mode in _all_modes():
        mode.init()
        print(f"  ✓ {mode.NAME}")

    # Resolve optional startup mode argument
    if args.mode is not None:
        gi, mi = _resolve_mode(args.mode)
        if gi is not None:
            current_group = gi
            group_mode_idx[gi] = mi
            print(f"\nStarting in mode: {_current_mode().NAME} ({GROUPS[gi]['name']})")
        else:
            all_names = ", ".join(m.NAME for m in _all_modes())
            print(f"\nUnknown mode '{args.mode}'. Available: {all_names}")

    print(f"\nStarting in group: {GROUPS[current_group]['name']}")
    print(f"Starting in mode:  {_current_mode().NAME}")
    print("Short press → next mode | Long press → next group\n")

    last_time     = time.monotonic()
    _flash_pending = False

    _activate_mode()

    while True:
        now = time.monotonic()
        dt  = now - last_time
        last_time = now

        # Handle group switch flash
        if _flash_pending:
            _flash_pending = False
            _do_group_flash(pixels)

        mode  = _current_mode()
        delay = getattr(mode, "FRAME_DELAY", FRAME_DELAY)
        mode.frame(pixels, dt)
        time.sleep(max(0.02, delay))

if __name__ == "__main__":
    main()
