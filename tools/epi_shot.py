#!/usr/bin/env python3
"""Close-up of the planetary wheel, big enough to see individual flanks.

Finds the wheel that carries the epicyclic set, freezes nothing (the page runs),
and captures just that wheel at high device scale so tooth contact is legible.

Usage: tools/epi_shot.py <url> <out.png>
"""

import asyncio
import json
import base64
import subprocess
import sys
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/?kind=planetary"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/epi.png"
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 9351
PROFILE = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad/chrome-epishot"

FIND = r"""
(() => {
  const svgs = [...document.querySelectorAll('svg')];
  let host = null;
  for (const s of svgs) if (s.innerHTML.indexOf('epiring') >= 0 || s.querySelector('[key="epiring"]')) { host = s; break; }
  if (!host) {
    let best = 0;
    for (const s of svgs) {
      const n = [...s.querySelectorAll('g')].filter(g => (g.style.transform || '').indexOf('rotate') === 0).length;
      if (n > best) { best = n; host = s; }
    }
  }
  if (!host) return JSON.stringify({ error: 'no planetary wheel' });
  const r = host.getBoundingClientRect();
  return JSON.stringify({ x: r.left, y: r.top, w: r.width, h: r.height });
})()
"""


async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--window-size=1440,900",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(50):
        for method in (None, "PUT"):
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{URL}",
                                             method=method) if method else \
                      f"http://127.0.0.1:{PORT}/json/new?{URL}"
                with urllib.request.urlopen(req, timeout=1) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
        if ws_url:
            break
        time.sleep(0.2)
    if not ws_url:
        proc.kill()
        print("FATAL: no DevTools endpoint")
        return 2

    mid = 0
    async with websockets.connect(ws_url, max_size=40 * 1024 * 1024) as ws:
        async def send(method, params=None):
            nonlocal mid
            mid += 1
            my = mid
            await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})

        await asyncio.sleep(2.2)
        box = json.loads((await send("Runtime.evaluate",
                                     {"expression": FIND, "returnByValue": True}))
                         ["result"]["value"])
        if "error" in box:
            proc.kill()
            print("FATAL:", box["error"])
            return 2
        if "--nobadge" in sys.argv:
            # The hub cap covers the sun completely, so the sun<->planet mesh
            # cannot be inspected with it in place.
            await send("Runtime.evaluate", {"expression":
                "document.querySelectorAll('a[href]').forEach(a=>a.style.visibility='hidden')"})
            await asyncio.sleep(0.2)
        if "--pull" in sys.argv:
            # Drag the hub cap off its axle and hold it there, so the shot shows
            # what is underneath: the sun.
            grab = json.loads((await send("Runtime.evaluate", {"expression": r"""
              (() => {
                const svgs=[...document.querySelectorAll('svg')];
                let host=null,bn=0;
                for(const s of svgs){const n=[...s.querySelectorAll('g')].filter(g=>(g.style.transform||'').indexOf('rotate')===0).length; if(n>bn){bn=n;host=s;}}
                const hr=host.getBoundingClientRect();
                const hc=[hr.left+hr.width/2, hr.top+hr.height/2];
                let best=null,bd=1e9;
                document.querySelectorAll('a[href]').forEach(a=>{
                  const r=a.getBoundingClientRect();
                  const d=Math.hypot(r.left+r.width/2-hc[0], r.top+r.height/2-hc[1]);
                  if(d<bd){bd=d;best={x:r.left+r.width/2,y:r.top+r.height/2};}
                });
                return JSON.stringify(best);
              })()""", "returnByValue": True}))["result"]["value"])
            gx, gy = grab["x"], grab["y"]
            for kind, btn, bmask, px, py in [("mouseMoved", "none", 0, gx, gy),
                                             ("mousePressed", "left", 1, gx, gy)]:
                await send("Input.dispatchMouseEvent", {"type": kind, "x": px, "y": py,
                           "button": btn, "buttons": bmask, "clickCount": 1,
                           "pointerType": "mouse"})
            await asyncio.sleep(0.2)          # let frames pass, as a hand does
            for i in range(1, 15):
                await send("Input.dispatchMouseEvent", {"type": "mouseMoved",
                           "x": gx + i * 6, "y": gy - i * 5, "button": "left",
                           "buttons": 1, "pointerType": "mouse"})
                await asyncio.sleep(0.02)
            await asyncio.sleep(0.1)
        if "--hub" in sys.argv:
            # Just the bore, where the epicyclic set lives.
            f = 0.42
            cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
            clip = {"x": cx - box["w"] * f / 2, "y": cy - box["h"] * f / 2,
                    "width": box["w"] * f, "height": box["h"] * f, "scale": 8}
            shot = await send("Page.captureScreenshot", {"format": "png", "clip": clip})
            with open(OUT, "wb") as f2:
                f2.write(base64.b64decode(shot["data"]))
            proc.kill()
            print(f"wrote {OUT}  (hub close-up at 8x)")
            return 0
        pad = 6
        clip = {"x": max(0, box["x"] - pad), "y": max(0, box["y"] - pad),
                "width": box["w"] + pad * 2, "height": box["h"] + pad * 2, "scale": 4}
        shot = await send("Page.captureScreenshot", {"format": "png", "clip": clip})
        with open(OUT, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
    proc.kill()
    print(f"wrote {OUT}  ({box['w']:.0f}x{box['h']:.0f} css px at 4x)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
