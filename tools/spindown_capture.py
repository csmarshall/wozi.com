#!/usr/bin/env python3
"""Sample REAL spin-up/spin-down motion from the live page (GitHub #106, CL#127).

Boots the page pre-seeded to run at 200x (localStorage set before the page's
own scripts run — the same `Page.addScriptToEvaluateOnNewDocument` technique
CLAUDE.md documents for the other harnesses), lets it spin up, taps the real
corner "reset to 1x" button — the same control a person would use, not a
simulated event — and records the driving wheel's actual on-screen rotation at
full frame rate for the whole run, spin-up and spin-down both.

There is no hook into `_v` from outside the page, and this suite intentionally
does not add one (a debug hook that leaks internal state for a one-off capture
is exactly the kind of thing CLAUDE.md's `?hud` section says to think hard
about before adding). What is measured instead is the thing `_v` is FOR: the
first gear's `rotate(...)deg` transform, which applyRotation() writes from
`_M` every tick applyRotation() runs — sampled in-page via requestAnimationFrame
(so the sample rate tracks the page's own tick rate, not this script's
websocket round-trip time), then finite-differenced in Python.

Self-calibrating: the settled window BEFORE the tap is defined as 200x and the
settled window at the END of the capture is defined as 1x (whatever the model
being measured actually settles to — every candidate's target is idleRate() at
SPEED_FLOOR once the corner control has been tapped, so this holds for all
three). Converting the raw deg/s trace to "x" units is then one affine map, and
it does not require this script to know BASE_MS, teeth counts or which
candidate is running — nothing here can drift out of step with the page for
the same reason grabNumber()/grabBlock() read index.html instead of copying it.

Usage:
    tools/spindown_capture.py <url> <candidate-name> <outdir>

Writes <outdir>/<candidate-name>.json (calibrated time series) and
<outdir>/<candidate-name>_frames/*.png (filmstrip frames at fixed offsets from
the tap, before and after).
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = (os.environ.get("CHROME")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CI_FLAGS = [] if sys.platform == "darwin" else \
    ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]

# Wall-clock offsets (seconds) from the tap at which a filmstrip frame is
# captured. Negative offsets are BEFORE the tap, showing the steady 200x state.
FRAME_OFFSETS = [-0.3, 0.0, 0.15, 0.3, 0.5, 0.8, 1.2, 1.8, 2.5, 3.5, 5.0, 7.0]

# How long the in-page rAF collector runs, and when (relative to ITS OWN start,
# not the tap) the tap fires. Long enough on both sides for every candidate's
# settle to be visible in the tail even at the slowest one under review.
PRETAP_S = 6.0      # time given to spin up to 200x and settle before tapping
POSTTAP_S = 9.0      # time sampled after the tap
TOTAL_MS = int((PRETAP_S + POSTTAP_S) * 1000)
TAP_AT_MS = int(PRETAP_S * 1000)


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


SEED_JS = ("localStorage.setItem('wozi-speed','200');"
           "localStorage.setItem('wozi-motion','run');")

# Runs entirely in-page. Finds the first element carrying an inline
# `rotate(...)deg` transform (applyRotation() writes those on the driving
# wheels every tick) and samples its angle once per animation frame for
# TOTAL_MS, resolving with the full trace. dir/teeth are irrelevant to this
# script — the affine calibration in Python only needs the RATIO of angular
# velocities, and dividing by a constant teeth count cancels out of a ratio.
SAMPLE_JS = r"""
(() => new Promise((resolve) => {
  const re = /rotate\(([-0-9.eE+]+)deg\)/i;
  let el = null;
  for (const e of document.querySelectorAll('*')) {
    const t = e.style && e.style.transform;
    if (t && re.test(t)) { el = e; break; }
  }
  if (!el) { resolve(JSON.stringify({ error: 'no rotating element found' })); return; }
  const out = [];
  const t0 = performance.now();
  function tick() {
    const t = performance.now() - t0;
    const m = re.exec(el.style.transform);
    out.push([+t.toFixed(2), m ? parseFloat(m[1]) : null]);
    if (t < %TOTAL_MS%) requestAnimationFrame(tick);
    else resolve(JSON.stringify({ samples: out }));
  }
  requestAnimationFrame(tick);
}))()
""".replace("%TOTAL_MS%", str(TOTAL_MS))

# Finds and clicks the real corner "reset to 1x" departure indicator — the
# production code path (resetSpeed(), GitHub #108) rather than a simulated
# setState. Only present/visible once speedFactor() !== SPEED_FLOOR.
TAP_JS = r"""
(() => {
  const btn = [...document.querySelectorAll('button[aria-label^="Gear speed"]')][0];
  if (!btn) return 'NO BUTTON FOUND';
  if (getComputedStyle(btn).display === 'none') return 'BUTTON HIDDEN';
  btn.click();
  return 'CLICKED';
})()
"""


async def run(url, name, outdir):
    frames_dir = os.path.join(outdir, name + "_frames")
    os.makedirs(frames_dir, exist_ok=True)
    port = free_port()
    profile = tempfile.mkdtemp(prefix="wozi-spindown-")
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--window-size=1440,900", "--no-first-run", *CI_FLAGS,
         "--no-default-browser-check", "--disable-features=Translate",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = None
        for _ in range(50):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/json/new?about:blank", timeout=1) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                try:  # newer Chrome requires PUT on /json/new
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
                    with urllib.request.urlopen(req, timeout=1) as r:
                        ws_url = json.load(r)["webSocketDebuggerUrl"]
                        break
                except Exception:
                    time.sleep(0.2)
        if not ws_url:
            print("FATAL: could not reach Chrome DevTools endpoint")
            return None

        pending = {}
        mid = 0

        async with websockets.connect(ws_url, max_size=40 * 1024 * 1024) as ws:
            async def recv_loop():
                async for raw in ws:
                    msg = json.loads(raw)
                    if "id" in msg and msg["id"] in pending:
                        pending.pop(msg["id"]).set_result(msg)

            recv_task = asyncio.create_task(recv_loop())

            async def send(method, params=None):
                nonlocal mid
                mid += 1
                my = mid
                fut = asyncio.get_event_loop().create_future()
                pending[my] = fut
                await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
                return await fut

            def send_nowait(method, params=None):
                nonlocal mid
                mid += 1
                my = mid
                fut = asyncio.get_event_loop().create_future()
                pending[my] = fut
                asyncio.create_task(ws.send(json.dumps(
                    {"id": my, "method": method, "params": params or {}})))
                return fut

            async def evaluate(expr, await_promise=False):
                r = await send("Runtime.evaluate", {
                    "expression": expr, "returnByValue": True,
                    "awaitPromise": await_promise})
                return r.get("result", {}).get("result", {}).get("value")

            await send("Page.enable")
            await send("Runtime.enable")
            # Seed localStorage BEFORE the page's own scripts run, exactly the
            # pattern the LCG-seeding harnesses already use.
            await send("Page.addScriptToEvaluateOnNewDocument", {"source": SEED_JS})
            await send("Page.navigate", {"url": url})
            await asyncio.sleep(1.2)  # initial load/layout settle

            # Kick off the long in-page sampler WITHOUT waiting for it (it
            # resolves only after TOTAL_MS) — this is the one call we let run
            # in the background while the tap and the screenshots interleave.
            sample_fut = send_nowait("Runtime.evaluate", {
                "expression": SAMPLE_JS, "returnByValue": True, "awaitPromise": True})
            t_sample_start = time.monotonic()

            shots = []

            async def shoot(offset_s):
                r = await send("Page.captureScreenshot", {"format": "png"})
                data = r.get("result", {}).get("data")
                if data:
                    shots.append((offset_s, data))

            # Negative-offset frames, before the tap.
            for off in [o for o in FRAME_OFFSETS if o < 0]:
                target = TAP_AT_MS / 1000 + off
                delay = target - (time.monotonic() - t_sample_start)
                if delay > 0:
                    await asyncio.sleep(delay)
                await shoot(off)

            # The tap itself, at the scheduled moment.
            delay = TAP_AT_MS / 1000 - (time.monotonic() - t_sample_start)
            if delay > 0:
                await asyncio.sleep(delay)
            tap_result = await evaluate(TAP_JS)
            t_tap = time.monotonic()

            # Positive-offset frames, after the tap.
            for off in [o for o in FRAME_OFFSETS if o >= 0]:
                delay = off - (time.monotonic() - t_tap)
                if delay > 0:
                    await asyncio.sleep(delay)
                await shoot(off)

            result = await sample_fut
            recv_task.cancel()

        payload = json.loads(result.get("result", {}).get("result", {}).get("value") or "{}")
        samples = payload.get("samples")
        if not samples:
            print("FATAL: no samples collected —", payload.get("error"))
            return None

        for i, (off, data) in enumerate(shots):
            fn = os.path.join(frames_dir, f"{i:02d}_{off:+.2f}s.png")
            with open(fn, "wb") as f:
                import base64
                f.write(base64.b64decode(data))

        out = {
            "candidate": name, "tap_result": tap_result,
            "tap_at_ms": TAP_AT_MS, "samples": samples,
            "frames": [{"offset_s": off, "file": os.path.join(name + "_frames",
                        f"{i:02d}_{off:+.2f}s.png")} for i, (off, _) in enumerate(shots)],
        }
        with open(os.path.join(outdir, name + ".json"), "w") as f:
            json.dump(out, f)
        print(f"{name}: {len(samples)} samples, tap={tap_result}, {len(shots)} frames -> {outdir}/{name}.json")
        return out
    finally:
        proc.kill()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    url, name, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    r = asyncio.run(run(url, name, outdir))
    sys.exit(0 if r else 1)
