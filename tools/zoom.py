#!/usr/bin/env python3
"""Zoom into a mesh point between two adjacent wheels to inspect tooth overlap."""

import asyncio, base64, json, subprocess, sys, time, urllib.request
import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL = "http://127.0.0.1:8765/"
OUT = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad"
PORT = 9352

FIND = r"""
(() => {
  const b = [...document.querySelectorAll('a[href]')].map(a => {
    const r = a.getBoundingClientRect();
    return { cx: r.left + r.width/2, cy: r.top + r.height/2 };
  }).filter(p => p.cx > 0).sort((x,y) => x.cx - y.cx);
  if (b.length < 2) return JSON.stringify(null);
  // midpoint between the first two wheel hubs = their mesh region
  return JSON.stringify({
    mx: (b[0].cx + b[1].cx) / 2, my: (b[0].cy + b[1].cy) / 2,
    gap: Math.hypot(b[1].cx - b[0].cx, b[1].cy - b[0].cy)
  });
})()
"""

async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={OUT}/cp-zoom", "--hide-scrollbars", "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws_url = None
    for _ in range(60):
        try:
            ws_url = json.load(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/new?{URL}", timeout=1))["webSocketDebuggerUrl"]; break
        except Exception:
            try:
                rq = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
                ws_url = json.load(urllib.request.urlopen(rq, timeout=1))["webSocketDebuggerUrl"]; break
            except Exception: time.sleep(0.2)
    mid = 0
    async with websockets.connect(ws_url, max_size=60*1024*1024) as ws:
        async def send(m, p=None):
            nonlocal mid; mid += 1; my = mid
            await ws.send(json.dumps({"id": my, "method": m, "params": p or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == my: return msg.get("result", {})
        await send("Page.enable"); await send("Runtime.enable")
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        await send("Page.navigate", {"url": URL})
        await asyncio.sleep(3.2)
        r = await send("Runtime.evaluate", {"expression": FIND, "returnByValue": True})
        d = json.loads(r["result"]["value"])
        print("mesh midpoint:", d)
        half = max(90, d["gap"] * 0.75)
        clip = {"x": d["mx"] - half, "y": d["my"] - half,
                "width": half * 2, "height": half * 2, "scale": 5}
        shot = await send("Page.captureScreenshot", {"format": "png", "clip": clip})
        p = f"{OUT}/mesh-zoom.png"
        open(p, "wb").write(base64.b64decode(shot["data"]))
        print("->", p, "clip:", {k: round(v, 1) for k, v in clip.items()})
    proc.kill()

asyncio.run(main())
