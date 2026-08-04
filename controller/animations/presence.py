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
from .shared import COLS, ROWS, xy, scale, INT, FLOAT, CHOICE, make_param_store

FRAME_DELAY    = 0.05
NAME           = "Presence"

# ── Configuration ─────────────────────────────────────────────────────────────

PARAMS = [
    ("ping_interval",  FLOAT(5.0, 120.0), 40.0),   # seconds between ping rounds
    ("ping_timeout",   FLOAT(0.2, 5.0),   2.0),    # seconds to wait for a reply
    ("miss_threshold", INT(1, 6),         2),      # consecutive misses before "absent"
    ("absent_dim",     FLOAT(0.0, 0.6),   0.15),    # centre pixel brightness when absent
    ("disc_radius",    FLOAT(0.5, 5.0),   2.5),    # radius of the pulsating disc
    ("pulse_max",      FLOAT(0.05, 1.0),  0.5),    # peak disc brightness
    ("pulse_min",      FLOAT(0.0, 0.5),   0.08),   # trough disc brightness
    ("pulse_period",   FLOAT(0.5, 10.0),  3.5),    # seconds per pulse cycle
    ("pulse_shape",    CHOICE(["sine", "fast_rise_slow_fade"]), "fast_rise_slow_fade"),
    ("pulse_attack",   FLOAT(0.05, 0.6),  0.15),    # fraction of cycle spent rising (fast_rise_slow_fade only)
    ("fade_speed",     FLOAT(0.05, 2.0),  0.3),    # brightness units/sec when transitioning present<->absent
]
_params, get_params, set_param = make_param_store(PARAMS)

PRESENT_CENTRE = 1.0     # centre pixel when present

# Family members — edit this list
# Each entry: (col, row, color, ip_address, label)
FAMILY_MEMBERS = [
    # (col, row, (R, G, B),        "ip",          "label")
    (  6,  4,  ( 60,  60, 255),  "192.168.1.11", "Sebastian"),
    (  2,  5,  (180,  70,  70),  "192.168.1.12", "Sandra"),
    (  7,  8,  ( 45, 200,  45),  "192.168.1.16", "Lars"),
    (  2,  1,  ( 80,  10, 255),  "192.168.1.19", "Femke"),
]

def _pulse_value(phase):
    """Return 0..1 pulse level for a phase (0..1 fraction of cycle)."""
    frac = phase % 1.0
    if _params["pulse_shape"] == "fast_rise_slow_fade":
        attack = _params["pulse_attack"]
        if frac < attack:
            # fast rise: ease-out
            x = frac / attack
            return math.sin(x * math.pi / 2)
        else:
            # slow fade: ease-in decay back to 0
            x = (frac - attack) / (1.0 - attack)
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
        self.brightness = _params["absent_dim"]   # current brightness (fades smoothly)
        self.pulse_t    = 0.0          # elapsed time within the pulse cycle
        self.pulse_phase = random.uniform(0.0, 1.0)  # stagger pulse offsets (fraction of cycle)

    @property
    def visually_present(self):
        # Transitioning looks identical to present — only true "absent" dims
        return self.state in ("present", "transitioning")

    def target_brightness(self):
        return PRESENT_CENTRE if self.visually_present else _params["absent_dim"]

    def update(self, dt):
        # Fade brightness toward target
        target = self.target_brightness()
        diff   = target - self.brightness
        step   = _params["fade_speed"] * dt
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
        if self.visually_present and self.brightness > _params["absent_dim"]:
            phase   = (self.pulse_t / _params["pulse_period"]) + self.pulse_phase
            level   = _pulse_value(phase)                        # 0..1
            pulse_min, pulse_max = _params["pulse_min"], _params["pulse_max"]
            disc_bri = (pulse_min + (pulse_max - pulse_min) * level) * (self.brightness / PRESENT_CENTRE)
            radius = _params["disc_radius"]
            for r in range(ROWS):
                for c in range(COLS):
                    if r == self.row and c == self.col:
                        continue
                    dist = math.sqrt((c - self.col) ** 2 + (r - self.row) ** 2)
                    if dist <= radius:
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
                result = ping3.ping(member.ip, timeout=_params["ping_timeout"])
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
                if member.miss_count >= _params["miss_threshold"]:
                    member.state = "absent"
                elif member.state == "present":
                    # Grace period only applies when downgrading from a
                    # confirmed present — a member who was already absent
                    # (e.g. right at startup) has nothing to "transition"
                    # from and should just stay absent, not flash into a
                    # visually-present state on its very first missed ping.
                    member.state = "transitioning"
                # else: already "transitioning" or "absent" and still under
                # threshold — stay as-is, no-op.

            print(f"  Presence [{member.label}] {member.ip}: {member.state}")
        _time.sleep(_params["ping_interval"])

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
