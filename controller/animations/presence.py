"""
animations/presence.py — Family member presence display

Pings configured IP addresses periodically and displays presence
on the LED grid. Each family member has a fixed grid position,
colour and IP address.

Present      — bright centre pixel + steady disc around it, pulsating in brightness
Transitioning — one missed ping in a row; visualized identically to present
Absent       — two or more missed pings in a row; dim centre pixel only, static

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

PING_INTERVAL  = 40.0    # seconds between ping rounds
PING_TIMEOUT   = 2.0     # seconds to wait for ping reply
MISS_THRESHOLD = 2       # consecutive missed pings before considered fully absent

# Brightness levels
PRESENT_CENTRE = 1.0     # centre pixel when present
ABSENT_DIM     = 0.2     # centre pixel brightness when absent

# Disc pulse animation
DISC_RADIUS    = 2.8     # radius of the steady disc around each present member
PULSE_MAX      = 0.3     # peak disc brightness
PULSE_MIN      = 0.04    # trough disc brightness
PULSE_PERIOD   = 3.0     # seconds per pulse cycle
PULSE_SHAPE    = "fast_rise_slow_fade"  # "sine" or "fast_rise_slow_fade"
PULSE_ATTACK   = 0.2     # fraction of cycle spent rising (fast_rise_slow_fade only)

# Fade transition speed (brightness units per second)
FADE_SPEED     = 0.2

# Family members — edit this list
# Each entry: (col, row, color, ip_address, label)
FAMILY_MEMBERS = [
    # (col, row, (R, G, B),        "ip",          "label")
    (  6,  4,  ( 60,  60, 255),  "192.168.1.11", "Seb"),
    (  2,  5,  (180,  70,  70),  "192.168.1.12", "San"),
    (  7,  8,  ( 45, 200,  45),  "192.168.1.16", "Lar"),
    (  2,  1,  ( 80,  10, 255),  "192.168.1.19", "Fem"),
]

def _pulse_value(phase):
    """Return 0..1 pulse level for a phase (0..1 fraction of cycle)."""
    frac = phase % 1.0
    if PULSE_SHAPE == "fast_rise_slow_fade":
        if frac < PULSE_ATTACK:
            # fast rise: ease-out
            x = frac / PULSE_ATTACK
            return math.sin(x * math.pi / 2)
        else:
            # slow fade: ease-in decay back to 0
            x = (frac - PULSE_ATTACK) / (1.0 - PULSE_ATTACK)
            return (1.0 - x) ** 2
    # default: sine, 0..1
    return (math.sin(frac * 2 * math.pi) + 1) / 2

# ── Member state ──────────────────────────────────────────────────────────────

class _Member:
    def __init__(self, col, row, color, ip, label):
        self.col       = col
        self.row       = row
        self.color     = color
        self.ip        = ip
        self.label     = label
        self.state     = "absent"      # "present" | "transitioning" | "absent"
        self.miss_count = 0            # consecutive missed pings
        self.brightness = ABSENT_DIM   # current brightness (fades smoothly)
        self.pulse_t    = 0.0          # elapsed time within the pulse cycle
        self.pulse_phase = random.uniform(0.0, 1.0)  # stagger pulse offsets (fraction of cycle)

    @property
    def visually_present(self):
        # Transitioning looks identical to present — only true "absent" dims
        return self.state in ("present", "transitioning")

    def target_brightness(self):
        return PRESENT_CENTRE if self.visually_present else ABSENT_DIM

    def update(self, dt):
        # Fade brightness toward target
        target = self.target_brightness()
        diff   = target - self.brightness
        step   = FADE_SPEED * dt
        if abs(diff) <= step:
            self.brightness = target
        else:
            self.brightness += step * (1 if diff > 0 else -1)

        # Advance pulse whenever visually present (present or transitioning)
        if self.visually_present:
            self.pulse_t += dt

    def draw(self, buf):
        # Centre pixel
        buf[self.row][self.col] = scale(self.color, self.brightness)

        # Pulsating disc — only when visually present
        if self.visually_present and self.brightness > ABSENT_DIM:
            phase   = (self.pulse_t / PULSE_PERIOD) + self.pulse_phase
            level   = _pulse_value(phase)                        # 0..1
            disc_bri = (PULSE_MIN + (PULSE_MAX - PULSE_MIN) * level) * (self.brightness / PRESENT_CENTRE)
            for r in range(ROWS):
                for c in range(COLS):
                    if r == self.row and c == self.col:
                        continue
                    dist = math.sqrt((c - self.col) ** 2 + (r - self.row) ** 2)
                    if dist <= DISC_RADIUS:
                        existing = buf[r][c]
                        buf[r][c] = (
                            min(255, existing[0] + int(self.color[0] * disc_bri)),
                            min(255, existing[1] + int(self.color[1] * disc_bri)),
                            min(255, existing[2] + int(self.color[2] * disc_bri)),
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
                got_reply = isinstance(result, float)
            except Exception as e:
                print(f"  Presence [{member.label}] ping error: {e}")
                got_reply = False

            if got_reply:
                # A reply can never be a false positive — go straight to present
                member.state = "present"
                member.miss_count = 0
            else:
                member.miss_count += 1
                if member.miss_count >= MISS_THRESHOLD:
                    member.state = "absent"
                else:
                    member.state = "transitioning"

            print(f"  Presence [{member.label}] {member.ip}: {member.state}")
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
