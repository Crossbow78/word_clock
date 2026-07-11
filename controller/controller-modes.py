"""
NeoPixel Grid Controller
Raspberry Pi + adafruit-circuitpython-neopixel + gpiozero

12×11 LED grid controller. Button on GPIO17 cycles through all
animation modes. Long-press toggles power on/off.

Button wiring:
  Leg 1 → GPIO17 (pin 11)
  Leg 2 → GND    (pin 9 or any GND)

Modes (in order):
  0  Word Clock
  1  Matrix Rain
  2  Ripple
  3  Plasma
  4  Game of Life
  5  Tetris AI
  6  Lava Lamp
  7  Sand
  8  Bouncing Balls
  9  Flow Field
  10  Spiral
  11 Snake
  12 Fire
  13 Weather
  14 Flags
  15 Chess

Dependencies:
    sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel noise gpiozero requests

Run with sudo:
    sudo python3 controller.py
"""

import time
import board
import neopixel
import argparse
from gpiozero import Button

from animations import (
    wordclock, matrix, ripple, plasma, life, tetris_ai,
    lavalamp, sand, balls, flowfield, spiral,
    snake, fire, weather, flags, chess
)

# ── Hardware ──────────────────────────────────────────────────────────────────

LED_PIN        = board.D12
LED_COUNT      = 132
LED_BRIGHTNESS = 0.6
LED_ORDER      = neopixel.GRB
BUTTON_PIN     = 17
FRAME_DELAY    = 0.04   # default; modes with internal timing ignore this

# ── Mode list ─────────────────────────────────────────────────────────────────

MODES = [
    wordclock,
    matrix,
    ripple,
    fire,
    plasma,
    life,
    tetris_ai,
    lavalamp,
    sand,
    balls,
    flowfield,
    spiral,
    snake,
    weather,
    flags,
    chess
]

# ── State ─────────────────────────────────────────────────────────────────────

current_mode   = 0
strip_on       = False   # start powered off
hold_triggered = False

# ── Button handling ───────────────────────────────────────────────────────────

def on_press():
    global hold_triggered
    hold_triggered = False

def on_hold():
    global hold_triggered, strip_on
    hold_triggered = True
    strip_on = not strip_on
    print(f"  → Power: {'ON' if strip_on else 'OFF'}")

def on_release():
    global current_mode
    if not hold_triggered:
        if not strip_on:
            return
        current_mode = (current_mode + 1) % len(MODES)
        mode = MODES[current_mode]
        print(f"  → Mode {current_mode}: {mode.NAME}")
        mode.init()

button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.05, hold_time=0.8)
button.when_pressed  = on_press
button.when_held     = on_hold
button.when_released = on_release

# ── Startup flash ─────────────────────────────────────────────────────────────

def startup_flash(pixels):
    """Double-blink pixel 0 to indicate ready."""
    for _ in range(2):
        pixels[0] = (255, 255, 255)
        pixels.show()
        time.sleep(0.1)
        pixels[0] = (0, 0, 0)
        pixels.show()
        time.sleep(0.05)

def parse_args():
    parser = argparse.ArgumentParser(description="NeoPixel Grid Controller")
    parser.add_argument(
        "--mode", "-m",
        type=str,
        default=None,
        help=f"Start in a specific mode by name. Available: {', '.join(m.NAME for m in MODES)}"
    )
    return parser.parse_args()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    pixels = neopixel.NeoPixel(
        LED_PIN,
        LED_COUNT,
        brightness=LED_BRIGHTNESS,
        pixel_order=LED_ORDER,
        auto_write=False,
    )

    # Initialise all modes at startup
    print("Initialising animations...")
    for mode in MODES:
        mode.init()
        print(f"  ✓ {mode.NAME}")

    # Resolve startup mode
    global current_mode, strip_on
    if args.mode is not None:
        names = [m.NAME.lower() for m in MODES]
        key   = args.mode.lower()
        if key in names:
            current_mode = names.index(key)
            strip_on     = True
            print(f"\nStarting in mode: {MODES[current_mode].NAME}")
        else:
            print(f"\nUnknown mode '{args.mode}'. Available: {', '.join(m.NAME for m in MODES)}")

    startup_flash(pixels)
    print("\nReady. Hold button to power on.")
    print("Tap  → next mode")
    print("Hold → on / off\n")

    last_time = time.monotonic()

    try:
        while True:
            now = time.monotonic()
            dt  = now - last_time
            last_time = now

            if not strip_on:
                pixels.fill((0, 0, 0))
                pixels.show()
                time.sleep(0.1)
                continue

            mode  = MODES[current_mode]
            delay = getattr(mode, "FRAME_DELAY", FRAME_DELAY)
            mode.frame(pixels, dt)
            time.sleep(max(0.02, delay))

    except KeyboardInterrupt:
        print("\nStopping — clearing LEDs.")
        pixels.fill((0, 0, 0))
        pixels.show()

if __name__ == "__main__":
    main()
