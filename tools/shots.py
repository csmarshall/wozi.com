#!/usr/bin/env python3
"""Screenshot the gear train at several viewports, and report the solved layout.

Used to reproduce the ultrawide "S shape" complaint: the train is a serpentine
by construction (alternating bearings in TRAIN), and the question is how that
reads as the fit scale grows on a wide display.
"""

import asyncio
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
OUT = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad"
import os  # for CDP_PORT, below
# THE PORT IS NOT FIXED (#42). Every harness here used a hardcoded DevTools
# port, so two running at once fought over it and the loser reported a
# ConnectionClosedError -- which reads as a page fault, not a harness fault, and
# wasted real time this session more than once. Bind to whatever the OS gives
# us, and honour CDP_PORT if a caller wants a specific one.
def _free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close()
    return p
PORT = int(os.environ.get("CDP_PORT") or 0) or _free_port()
VIEWPORTS = [
    (390, 844, "390x844-phone"),
    (900, 1200, "900x1200-portrait"),
    (1440, 900, "1440x900"),
    (2560, 1080, "2560x1080"),
    (3440, 1440, "3440x1440"),
]

# Report the solved geometry: stage box, and every wheel centre/radius in
# viewport pixels, so the shape of the run is measurable rather than eyeballed.
GEOM = r"""
(() => {
  const svgs = [...document.querySelectorAll('svg')].map(s => {
    const b = s.getBoundingClientRect();
    return { cx: +(b.left + b.width/2).toFixed(1),
             cy: +(b.top + b.height/2).toFixed(1),
             d:  +b.width.toFixed(1) };
  }).filter(w => w.d > 40).sort((a,b) => a.cx - b.cx);
  const badges = [...document.querySelectorAll('a[href]')].map(a => {
    const b = a.getBoundingClientRect();
    return { cx: +(b.left + b.width/2).toFixed(1), cy: +(b.top + b.height/2).toFixed(1) };
  }).filter(b => b.cx > 0).sort((a,b) => a.cx - b.cx);
  const dir = getComputedStyle(document.documentElement).getPropertyValue('--dir').trim();
  const gsfit = getComputedStyle(document.documentElement).getPropertyValue('--gsfit').trim();
  return JSON.stringify({ wheels: svgs, badges: badges, dir: dir, gsfit: gsfit,
                          vp: [innerWidth, innerHeight] });
})()
"""


async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={OUT}/cp-shots", "--hide-scrollbars",
         "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(60):
        try:
            ws_url = json.load(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/new?{URL}", timeout=1))["webSocketDebuggerUrl"]
            break
        except Exception:
            try:
                rq = urllib.request.Request(
                    f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
                ws_url = json.load(urllib.request.urlopen(rq, timeout=1))["webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.2)
    if not ws_url:
        proc.kill(); print("no devtools"); return 2

    mid = 0
    async with websockets.connect(ws_url, max_size=60 * 1024 * 1024) as ws:
        async def send(m, p=None):
            nonlocal mid
            mid += 1; my = mid
            await ws.send(json.dumps({"id": my, "method": m, "params": p or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})

        await send("Page.enable")
        await send("Runtime.enable")

        for w, h, tag in VIEWPORTS:
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False})
            await send("Page.navigate", {"url": URL})
            await asyncio.sleep(3.2)
            r = await send("Runtime.evaluate", {"expression": GEOM, "returnByValue": True})
            g = json.loads(r["result"]["value"])

            ys = [p["cy"] for p in g["wheels"]]
            xs = [p["cx"] for p in g["wheels"]]
            span_x = (max(xs) - min(xs)) if xs else 0
            span_y = (max(ys) - min(ys)) if ys else 0
            print(f"\n=== {tag}  (--dir={g['dir']}, --gsfit={g['gsfit']}) ===")
            print(f"  wheels: {len(g['wheels'])}   badges: {len(g['badges'])}")
            print(f"  wheel-centre span: x={span_x:.0f}px  y={span_y:.0f}px"
                  f"   ratio y/x={ (span_y/span_x if span_x else 0):.2f}")
            print(f"  viewport fill: x={span_x/w*100:.0f}%  y={span_y/h*100:.0f}%")
            if g["badges"]:
                by = [b["cy"] for b in g["badges"]]
                print(f"  badge y range: {min(by):.0f} .. {max(by):.0f}"
                      f"  (swing {max(by)-min(by):.0f}px)")
                print("  badge path:", " ".join(f"({b['cx']:.0f},{b['cy']:.0f})" for b in g["badges"]))

            shot = await send("Page.captureScreenshot", {"format": "png"})
            path = f"{OUT}/train-{tag}.png"
            open(path, "wb").write(base64.b64decode(shot["data"]))
            print(f"  -> {path}")

    proc.kill()
    return 0


sys.exit(asyncio.run(main()))
