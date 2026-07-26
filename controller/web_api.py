"""
web_api.py — HTTP API + Web UI for the NeoPixel Grid Controller

Endpoints:
    GET  /                        — web UI
    GET  /status                  — current state
    GET  /system                  — CPU, temperature, uptime, wifi signal
    GET  /modes                   — all groups and modes
    POST /mode/next               — next mode in current group
    POST /mode/{name}             — switch to named mode directly
    POST /group/next              — next group
    POST /slideshow/on            — enable slideshow
    POST /slideshow/off           — disable slideshow
    POST /slideshow/interval/{s}  — set slideshow interval (1–60s)
    POST /brightness/{value}      — set brightness (0.0–1.0), switches to manual
    POST /brightness/auto         — switch to auto (hour-based) brightness

Dependencies:
    sudo pip3 install fastapi uvicorn psutil
"""

import time
import threading
import psutil
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

API_PORT = 8000

_ctrl   = None
_pixels = None

app = FastAPI(title="NeoPixel Controller", version="1.0")

# ── System stats ──────────────────────────────────────────────────────────────

def _wifi_signal():
    try:
        with open("/proc/net/wireless") as f:
            for line in f:
                if "wlan0" in line:
                    return int(float(line.split()[3]))
    except Exception:
        return None

def _system_stats():
    # CPU
    cpu = psutil.cpu_percent(interval=None)

    # Temperature
    temp = None
    try:
        temps = psutil.sensors_temperatures()
        if "cpu_thermal" in temps:
            temp = round(temps["cpu_thermal"][0].current, 1)
        elif "coretemp" in temps:
            temp = round(temps["coretemp"][0].current, 1)
    except Exception:
        pass

    # Uptime
    uptime_seconds = int(time.time() - psutil.boot_time())
    hours, rem     = divmod(uptime_seconds, 3600)
    minutes        = rem // 60
    uptime_str     = f"{hours}h {minutes}m"

    # WiFi signal
    wifi = _wifi_signal()

    return {
        "cpu":    round(cpu, 1),
        "temp":   temp,
        "uptime": uptime_str,
        "wifi":   wifi,
    }

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/status")
def get_status():
    return _ctrl["get_status"](_pixels)

@app.get("/system")
def get_system():
    return _system_stats()

@app.get("/modes")
def get_modes():
    return {"groups": _ctrl["get_modes"]()}

@app.post("/mode/next")
def post_mode_next():
    _ctrl["do_single_click"]()
    return _ctrl["get_status"](_pixels)

@app.post("/mode/{name}")
def post_mode(name: str):
    gi, mi = _ctrl["resolve_mode"](name)
    if gi is None:
        raise HTTPException(status_code=404, detail=f"Unknown mode '{name}'")
    _ctrl["set_mode_direct"](gi, mi)
    return _ctrl["get_status"](_pixels)

@app.post("/group/next")
def post_group_next():
    _ctrl["advance_group"]()
    return _ctrl["get_status"](_pixels)

@app.post("/slideshow/on")
def post_slideshow_on():
    _ctrl["slideshow_on"]()
    print("  -> [API] Slideshow: ON")
    return _ctrl["get_status"](_pixels)

@app.post("/slideshow/off")
def post_slideshow_off():
    _ctrl["slideshow_off"]()
    print("  -> [API] Slideshow: OFF")
    return _ctrl["get_status"](_pixels)

@app.post("/slideshow/interval/{seconds}")
def post_slideshow_interval(seconds: float):
    if not 1 <= seconds <= 60:
        raise HTTPException(status_code=400, detail="Interval must be between 1 and 60")
    _ctrl["set_slideshow_interval"](seconds)
    return _ctrl["get_status"](_pixels)

@app.post("/brightness/auto")
def post_brightness_auto():
    _ctrl["set_brightness_auto"]()
    print("  -> [API] Brightness: Auto")
    return _ctrl["get_status"](_pixels)

@app.post("/brightness/{value}")
def post_brightness(value: float):
    if not 0.0 <= value <= 1.0:
        raise HTTPException(status_code=400, detail="Brightness must be between 0.0 and 1.0")
    _ctrl["set_brightness"](value)
    print(f"  -> [API] Brightness: {value:.2f} (manual)")
    return _ctrl["get_status"](_pixels)

# ── Web UI ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def get_ui():
    return HTML_UI

HTML_UI = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>NeoPixel Controller</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #111;
    color: #eee;
    font-family: system-ui, sans-serif;
    padding: 20px 20px 60px;
    max-width: 480px;
    margin: 0 auto;
  }

  h1 {
    font-size: 1.1rem;
    color: #aaa;
    margin-bottom: 16px;
    letter-spacing: 0.1em;
  }

  h2 {
    font-size: 0.75rem;
    color: #555;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 20px 0 8px;
  }

  #status-bar {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #888;
    margin-bottom: 4px;
  }
  #status-bar span { color: #fff; }

  /* Groups + modes */
  .group-section { margin-bottom: 12px; }

  .group-header {
    font-size: 0.72rem;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 4px 0 6px;
    border-bottom: 1px solid #222;
    margin-bottom: 6px;
  }
  .group-header.active-group { color: #fc0; border-color: #fc0; }

  .mode-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 6px;
  }

  button {
    padding: 10px 16px;
    border: 1px solid #333;
    border-radius: 8px;
    background: #1a1a1a;
    color: #ccc;
    font-size: 0.85rem;
    cursor: pointer;
    transition: background 0.1s, border-color 0.1s;
    -webkit-tap-highlight-color: transparent;
  }
  button:active { background: #2a2a2a; }

  .mode-btn { text-align: left; width: 100%; }
  .mode-btn.active { border-color: #0cf; color: #0cf; background: #0a1f22; }

  #btn-next-group {
    margin-top: 12px;
    border-color: #444;
    color: #aaa;
  }
  #btn-next-group:active { border-color: #fc0; color: #fc0; }

  /* Slideshow */
  .toggle-row { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; }
  .toggle-status { font-size: 0.8rem; color: #555; }
  .slider-row { display: flex; align-items: center; gap: 10px; }
  .slider-val  { font-size: 0.8rem; color: #888; min-width: 36px; text-align: right; }

  input[type=range] {
    flex: 1;
    accent-color: #0cf;
    height: 6px;
  }

  button.active-green { border-color: #0f0; color: #0f0; background: #0a1a0a; }
  button.active-red   { border-color: #f44; color: #f44; background: #1a0a0a; }
  button.active-cyan  { border-color: #0cf; color: #0cf; background: #0a1f22; }

  /* System stats bar */
  #sys-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #0d0d0d;
    border-top: 1px solid #222;
    padding: 6px 16px;
    display: flex;
    gap: 16px;
    justify-content: center;
    font-size: 0.72rem;
    color: #555;
  }
  #sys-bar span { color: #888; }
  .sys-item { white-space: nowrap; }
</style>
</head>
<body>

<h1>⚡ NEOPIXEL CONTROLLER</h1>

<div id="status-bar">
  Group: <span id="s-group">—</span> &nbsp;|&nbsp;
  Mode: <span id="s-mode">—</span>
</div>

<h2>Modes</h2>
<div id="mode-sections"></div>
<button id="btn-next-group" onclick="api('/group/next')">Next Group →</button>

<h2>Slideshow</h2>
<div class="toggle-row">
  <button id="ss-on"  onclick="api('/slideshow/on')">Enable</button>
  <button id="ss-off" onclick="api('/slideshow/off')">Disable</button>
  <span class="toggle-status" id="ss-status">—</span>
</div>
<div class="slider-row">
  <span style="font-size:0.8rem;color:#666">Interval</span>
  <input type="range" id="ss-interval" min="1" max="60" value="30"
         oninput="onInterval(this.value)">
  <span class="slider-val" id="ss-interval-val">30s</span>
</div>

<h2>Brightness</h2>
<div class="toggle-row">
  <button id="btn-auto" onclick="api('/brightness/auto')">Auto</button>
  <span class="toggle-status" id="brightness-mode-status">—</span>
</div>
<div class="slider-row">
  <input type="range" id="brightness" min="0" max="100" value="80"
         oninput="onBrightness(this.value)">
  <span class="slider-val" id="brightness-val">80%</span>
</div>

<!-- System stats fixed bottom bar -->
<div id="sys-bar">
  <span class="sys-item">CPU <span id="sys-cpu">—</span></span>
  <span class="sys-item">Temp <span id="sys-temp">—</span></span>
  <span class="sys-item">Up <span id="sys-uptime">—</span></span>
  <span class="sys-item">WiFi <span id="sys-wifi">—</span></span>
</div>

<script>
  let _brightnessTimer = null;
  let _intervalTimer   = null;

  async function api(path, method="POST") {
    try {
      const res = await fetch(path, { method });
      if (res.ok) updateUI(await res.json());
    } catch(e) { console.error(e); }
  }

  async function fetchModes() {
    const res  = await fetch("/modes");
    const data = await res.json();
    const container = document.getElementById("mode-sections");
    container.innerHTML = "";
    data.groups.forEach(g => {
      const section = document.createElement("div");
      section.className = "group-section";

      const header = document.createElement("div");
      header.className    = "group-header";
      header.textContent  = g.name;
      header.dataset.group = g.name;
      section.appendChild(header);

      const grid = document.createElement("div");
      grid.className = "mode-grid";
      g.modes.forEach(name => {
        const btn = document.createElement("button");
        btn.className    = "mode-btn";
        btn.textContent  = name;
        btn.dataset.mode = name;
        btn.onclick      = () => api("/mode/" + encodeURIComponent(name));
        grid.appendChild(btn);
      });
      section.appendChild(grid);
      container.appendChild(section);
    });
  }

  function updateUI(s) {
    document.getElementById("s-group").textContent = s.group;
    document.getElementById("s-mode").textContent  = s.mode;

    // Highlight active group header
    document.querySelectorAll(".group-header").forEach(h =>
      h.classList.toggle("active-group", h.dataset.group === s.group));

    // Highlight active mode button
    document.querySelectorAll(".mode-btn").forEach(b =>
      b.classList.toggle("active", b.dataset.mode === s.mode));

    // Slideshow
    document.getElementById("ss-on").className  = s.slideshow ? "active-green" : "";
    document.getElementById("ss-off").className = s.slideshow ? "" : "active-red";
    document.getElementById("ss-status").textContent = s.slideshow ? "ON" : "OFF";

    const iVal = Math.round(s.slideshow_interval);
    document.getElementById("ss-interval").value           = iVal;
    document.getElementById("ss-interval-val").textContent = iVal + "s";

    // Brightness
    const isAuto = s.brightness_mode === "auto";
    document.getElementById("btn-auto").className =
      isAuto ? "active-cyan" : "";
    document.getElementById("brightness-mode-status").textContent =
      isAuto ? "Auto (hour-based)" : "Manual";
    document.getElementById("brightness").style.accentColor =
      isAuto ? "#888" : "#0cf";

    const bVal = Math.round(s.brightness * 100);
    document.getElementById("brightness").value           = bVal;
    document.getElementById("brightness-val").textContent = bVal + "%";
  }

  function onBrightness(val) {
    document.getElementById("brightness-val").textContent = val + "%";
    clearTimeout(_brightnessTimer);
    _brightnessTimer = setTimeout(
      () => api("/brightness/" + (val / 100).toFixed(2)), 350
    );
  }

  function onInterval(val) {
    document.getElementById("ss-interval-val").textContent = val + "s";
    clearTimeout(_intervalTimer);
    _intervalTimer = setTimeout(
      () => api("/slideshow/interval/" + val), 350
    );
  }

  async function pollStatus() {
    try {
      const res = await fetch("/status");
      if (res.ok) updateUI(await res.json());
    } catch(e) {}
    setTimeout(pollStatus, 3000);
  }

  async function pollSystem() {
    try {
      const res  = await fetch("/system");
      const data = await res.json();
      document.getElementById("sys-cpu").textContent    = data.cpu    != null ? data.cpu + "%" : "—";
      document.getElementById("sys-temp").textContent   = data.temp   != null ? data.temp + "°C" : "—";
      document.getElementById("sys-uptime").textContent = data.uptime != null ? data.uptime : "—";
      document.getElementById("sys-wifi").textContent   = data.wifi   != null ? data.wifi + " dBm" : "—";
    } catch(e) {}
    setTimeout(pollSystem, 5000);
  }

  fetchModes().then(() => {
    pollStatus();
    pollSystem();
  });
</script>
</body>
</html>"""

# ── Server startup ────────────────────────────────────────────────────────────

def start_web_api(pixels, ctrl):
    global _ctrl, _pixels
    _ctrl   = ctrl
    _pixels = pixels

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    print(f"  Web API -> http://raspberrypi.local:{API_PORT}")
