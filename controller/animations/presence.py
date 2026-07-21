"""
animations/presence.py — Family member presence display

Pings configured IP addresses periodically and displays presence
on the LED grid. Each family member has a fixed grid position,
colour and IP address.

Present  — bright centre pixel + pulsing ring expanding outward
Absent   — dim centre pixel only, static

Configuration: edit FAMILY_MEMBERS below.

Dependencies:
    sudo pip3 install ping3
"""

import math
import random
import threading
import time as _time
import ping3
from .shared import COLS, ROWS, xy, scale

FRAME_DELAY    = 0.05
NAME           = "Presence"

# ── Configuration ─────────────────────────────────────────────────────────────

PING_INTERVAL  = 60.0    # seconds between ping rounds
PING_TIMEOUT   = 2.0     # seconds to wait for ping reply

# Brightness levels
PRESENT_CENTRE = 1.0     # centre pixel when present
PRESENT_RING   = 0.3     # peak ring brightness when present
ABSENT_DIM     = 0.15    # centre pixel brightness when absent

# Ring animation
RING_SPEED     = 1.3     # radius units per second
RING_MAX       = 3.0     # maximum ring radius before reset
RING_WIDTH     = 0.8     # thickness of the ring

# Fade transition speed (brightness units per second)
FADE_SPEED     = 0.2

# Family members — edit this list
# Each entry: (col, row, color, ip_address, label)
FAMILY_MEMBERS = [
    # (col, row, (R, G, B),        "ip",          "label")
    (  6,  4,  ( 60,  60, 255),  "192.168.1.11", "Sebastian"),
    (  2,  5,  (180,  70,  70),  "192.168.1.12", "Sandra"),
    (  7,  8,  ( 45, 200,  45),  "192.168.1.16", "Lars"),
    (  2,  1,  ( 80,  10, 255),  "192.168.1.19", "Femke"),
]

# ── Member state ──────────────────────────────────────────────────────────────

class _Member:
    def __init__(self, col, row, color, ip, label):
        self.col       = col
        self.row       = row
        self.color     = color
        self.ip        = ip
        self.label     = label
        self.present   = False
        self.brightness = ABSENT_DIM   # current brightness (fades smoothly)
        self.ring_t    = 0.0           # current ring radius
        self.ring_phase = random.uniform(0, math.pi * 2)  # stagger ring offsets

    def target_brightness(self):
        return PRESENT_CENTRE if self.present else ABSENT_DIM

    def update(self, dt):
        # Fade brightness toward target
        target = self.target_brightness()
        diff   = target - self.brightness
        step   = FADE_SPEED * dt
        if abs(diff) <= step:
            self.brightness = target
        else:
            self.brightness += step * (1 if diff > 0 else -1)

        # Advance ring only when present
        if self.present:
            self.ring_t += dt
            #self.ring_r += RING_SPEED * dt
            #if self.ring_r > RING_MAX:
            #    self.ring_r = 0.0

    def draw(self, buf):
        # Centre pixel
        buf[self.row][self.col] = scale(self.color, self.brightness)

        # Pulsing ring — only when present
        if self.present and self.brightness > ABSENT_DIM:
            effective_r = ((self.ring_t * RING_SPEED + self.ring_phase) % RING_MAX)
            for r in range(ROWS):
                for c in range(COLS):
                    if r == self.row and c == self.col:
                        continue
                    dist  = math.sqrt((c - self.col)**2 + (r - self.row)**2)
                    delta = abs(dist - effective_r)
                    if delta < RING_WIDTH:
                        falloff  = (1 + math.cos(math.pi * delta / RING_WIDTH)) / 2
                        fade     = 1.0 - (effective_r / RING_MAX)
                        ring_bri = PRESENT_RING * falloff * fade * (self.brightness / PRESENT_CENTRE)
                        existing = buf[r][c]
                        buf[r][c] = (
                            min(255, existing[0] + int(self.color[0] * ring_bri)),
                            min(255, existing[1] + int(self.color[1] * ring_bri)),
                            min(255, existing[2] + int(self.color[2] * ring_bri)),
                        )

# ── Ping thread ───────────────────────────────────────────────────────────────

_members     = []
_ping_thread = None
_started     = False

def _ping_all():
    while True:
        for member in _members:
            try:
                result = ping3.ping(member.ip, timeout=PING_TIMEOUT)
                member.present = isinstance(result, float)
                status = "present" if member.present else "absent"
                print(f"  Presence [{member.label}] {member.ip}: {status}")
            except Exception as e:
                print(f"  Presence [{member.label}] ping error: {e}")
                member.present = False
        _time.sleep(PING_INTERVAL)

# ── Module interface ──────────────────────────────────────────────────────────

def init():
    global _members, _started
    _members = [
        _Member(col, row, color, ip, label)
        for col, row, color, ip, label in FAMILY_MEMBERS
    ]
    if not _started:
        t = threading.Thread(target=_ping_all, daemon=True)
        t.start()
        _started = True
        print(f"  Presence: monitoring {len(_members)} members")

def activate():
    pass   # ping thread runs continuously, no reset needed

def frame(pixels, dt):
    # Clear buffer
    buf = [[(0, 0, 0)] * COLS for _ in range(ROWS)]

    # Update and draw each member
    for member in _members:
        member.update(dt)
        member.draw(buf)

    # Push to strip
    for r in range(ROWS):
        for c in range(COLS):
            pixels[xy(c, r)] = buf[r][c]
    pixels.show()
