"""
web_api.py — HTTP API + Web UI for the NeoPixel Grid Controller

Runs as a background thread alongside the main animation loop.
Receives controller state and actions via a dict passed from controller.py,
avoiding circular imports and double GPIO initialisation.

Usage in controller.py:
    import web_api
    web_api.start_web_api(pixels, {
        "get_status":         _get_api_status,
        "get_modes":          _get_api_modes,
        "resolve_mode":       _resolve_mode,
        "set_mode_direct":    _set_mode_direct,
        "do_single_click":    _do_single_click,
        "advance_group":      _advance_group,
        "slideshow_on":       _slideshow_on,
        "slideshow_off":      _slideshow_off,
    })

Endpoints:
    GET  /                   — web UI
    GET  /status             — current state
    GET  /modes              — all groups and modes
    POST /mode/next          — next mode in current group
    POST /mode/{name}        — switch to named mode directly
    POST /group/next         — next group
    POST /slideshow/on       — enable slideshow
    POST /slideshow/off      — disable slideshow
    POST /brightness/{value} — set brightness (0.0–1.0)

Dependencies:
    sudo pip3 install fastapi uvicorn
"""

import threading
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

API_PORT = 8000

_ctrl   = None
_pixels = None

app = FastAPI(title="NeoPixel Controller", version="1.0")

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/status")
def get_status():
    return _ctrl["get_status"](_pixels)

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

@app.post("/brightness/{value}")
def post_brightness(value: float):
    if not 0.0 <= value <= 1.0:
        raise HTTPException(status_code=400, detail="Brightness must be between 0.0 and 1.0")
    _pixels.brightness = value
    print(f"  -> [API] Brightness: {value:.2f}")
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
    padding: 20px;
    max-width: 480px;
    margin: 0 auto;
  }

  h1 { font-size: 1.1rem; color: #aaa; margin-bottom: 16px; letter-spacing: 0.1em; }
  h2 { font-size: 0.75rem; color: #555; letter-spacing: 0.12em; text-transform: uppercase;
       margin: 20px 0 8px; }

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

  .btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }

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

  button.group-btn { border-color: #444; color: #aaa; }
  button.group-btn.active { border-color: #fc0; color: #fc0; background: #1a1500; }

  .mode-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 6px;
  }

  .mode-btn { text-align: left; }
  .mode-btn.active { border-color: #0cf; color: #0cf; background: #0a1f22; }

  input[type=range] {
    width: 100%;
    accent-color: #0cf;
    height: 6px;
    margin: 8px 0;
  }

  #brightness-val { font-size: 0.8rem; color: #888; }

  .slideshow-row { display: flex; gap: 8px; align-items: center; }
  #slideshow-status { font-size: 0.8rem; color: #555; }
  button.ss-on.active  { border-color: #0f0; color: #0f0; background: #0a1a0a; }
  button.ss-off.active { border-color: #f44; color: #f44; background: #1a0a0a; }
</style>
</head>
<body>

<h1>⚡ NEOPIXEL CONTROLLER</h1>

<div id="status-bar">
  Group: <span id="s-group">—</span> &nbsp;|&nbsp;
  Mode: <span id="s-mode">—</span>
</div>

<h2>Groups</h2>
<div class="btn-row" id="group-btns"></div>

<h2>Modes</h2>
<div class="mode-grid" id="mode-btns"></div>

<h2>Slideshow</h2>
<div class="slideshow-row">
  <button class="ss-on"  onclick="api('/slideshow/on')">Enable</button>
  <button class="ss-off" onclick="api('/slideshow/off')">Disable</button>
  <span id="slideshow-status">—</span>
</div>

<h2>Brightness</h2>
<input type="range" id="brightness" min="0" max="100" value="80"
       oninput="onBrightness(this.value)">
<div id="brightness-val">80%</div>

<script>
  let _brightnessTimer = null;

  async function api(path, method="POST") {
    try {
      const res = await fetch(path, { method });
      if (res.ok) updateUI(await res.json());
    } catch(e) { console.error(e); }
  }

  async function fetchModes() {
    const res  = await fetch("/modes");
    const data = await res.json();

    const groupBtns = document.getElementById("group-btns");
    groupBtns.innerHTML = "";
    data.groups.forEach(g => {
      const btn = document.createElement("button");
      btn.className     = "group-btn";
      btn.textContent   = g.name;
      btn.dataset.group = g.name;
      btn.onclick       = () => api("/group/next");
      groupBtns.appendChild(btn);
    });

    const modeBtns = document.getElementById("mode-btns");
    modeBtns.innerHTML = "";
    data.groups.forEach(g => {
      g.modes.forEach(name => {
        const btn = document.createElement("button");
        btn.className    = "mode-btn";
        btn.textContent  = name;
        btn.dataset.mode = name;
        btn.onclick      = () => api("/mode/" + encodeURIComponent(name));
        modeBtns.appendChild(btn);
      });
    });
  }

  function updateUI(s) {
    document.getElementById("s-group").textContent = s.group;
    document.getElementById("s-mode").textContent  = s.mode;

    document.querySelectorAll(".group-btn").forEach(b =>
      b.classList.toggle("active", b.dataset.group === s.group));
    document.querySelectorAll(".mode-btn").forEach(b =>
      b.classList.toggle("active", b.dataset.mode === s.mode));

    document.querySelector(".ss-on").classList.toggle("active",   s.slideshow);
    document.querySelector(".ss-off").classList.toggle("active", !s.slideshow);
    document.getElementById("slideshow-status").textContent = s.slideshow ? "ON" : "OFF";

    const bVal = Math.round(s.brightness * 100);
    document.getElementById("brightness").value           = bVal;
    document.getElementById("brightness-val").textContent = bVal + "%";
  }

  function onBrightness(val) {
    document.getElementById("brightness-val").textContent = val + "%";
    clearTimeout(_brightnessTimer);
    _brightnessTimer = setTimeout(
      () => api("/brightness/" + (val / 100).toFixed(2)), 150
    );
  }

  async function poll() {
    try {
      const res = await fetch("/status");
      if (res.ok) updateUI(await res.json());
    } catch(e) {}
    setTimeout(poll, 3000);
  }

  fetchModes().then(() => poll());
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
