#!/usr/bin/env python3
"""Pin a wheel at eight rotations and measure which half is lit, in both themes.

Samples the TOOTH RING only (0.75r-0.93r). Nothing but the body linear gradient
paints there -- no badge, no radial face/well gradients -- so it isolates the one
thing #19 is about.

The test for #19: with a single light above, top-minus-bottom must be clearly
positive at EVERY angle. It was a consistent -0.008 before.
Also reports wheel-vs-page contrast, which is the measurement #20 turns on.
"""
import asyncio, base64, json, subprocess, sys, time, urllib.request
import numpy as np
from PIL import Image
import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
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
URL = "http://127.0.0.1:8765/"


def lum(a):
    x = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]


def measure(path, cx, cy, rin, rout):
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64) / 255.0
    L = lum(im); h, w = L.shape
    y0, y1 = max(0, int(cy - rout)), min(h, int(cy + rout))
    x0, x1 = max(0, int(cx - rout)), min(w, int(cx + rout))
    P = L[y0:y1, x0:x1]; yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.hypot(xx - cx, yy - cy); ring = (d > rin) & (d < rout)
    top = P[ring & (yy < cy)]; bot = P[ring & (yy >= cy)]
    body = P[ring]
    bg = float(np.median(L[8:40, :]))
    return float(top.mean()), float(bot.mean()), float(body.mean()), bg


PROBE = r"""
(() => {
  /* A REAL wheel, not a ghost: ghosts render first in document order and carry no
     badge. Match an svg centre to a badge centre to be sure which is which. */
  const hubs=[...document.querySelectorAll('a[href]')].map(a=>{const b=a.getBoundingClientRect();
    return {x:b.left+b.width/2,y:b.top+b.height/2};}).filter(p=>p.x>0);
  const svgs=[...document.querySelectorAll('svg')].filter(v=>v.getBoundingClientRect().width>60);
  let s=null,best=1e9;
  for(const v of svgs){const b=v.getBoundingClientRect();
    const c={x:b.left+b.width/2,y:b.top+b.height/2};
    for(const hb of hubs){const d=Math.hypot(c.x-hb.x,c.y-hb.y);
      if(d<3 && b.width<best){best=b.width; s=v;}}}
  if(!s) return JSON.stringify({err:'no real wheel matched'});
  let el=s.parentElement, host=null;
  while(el&&!host){const t=el.style&&el.style.transform; if(t&&/rotate/.test(t))host=el; el=el.parentElement;}
  window.__host=host; const b=s.getBoundingClientRect();
  return JSON.stringify({cx:b.left+b.width/2,cy:b.top+b.height/2,d:b.width});
})()
"""


async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={OUT}/cp-pin", "--hide-scrollbars", "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(60):
        try:
            ws = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{URL}", timeout=1))["webSocketDebuggerUrl"]; break
        except Exception:
            try:
                rq = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
                ws = json.load(urllib.request.urlopen(rq, timeout=1))["webSocketDebuggerUrl"]; break
            except Exception:
                time.sleep(0.2)
    mid = 0
    async with websockets.connect(ws, max_size=6 * 10 ** 7) as c:
        async def send(m, p=None):
            nonlocal mid
            mid += 1; my = mid
            await c.send(json.dumps({"id": my, "method": m, "params": p or {}}))
            while True:
                msg = json.loads(await c.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})
        await send("Runtime.enable"); await send("Page.enable")
        await send("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 700, "deviceScaleFactor": 2, "mobile": False})
        for theme in ("dark", "light"):
            await send("Page.navigate", {"url": URL}); await asyncio.sleep(2.0)
            await send("Runtime.evaluate", {"expression":
                f"(()=>{{localStorage.setItem('wozi-theme','{theme}');location.reload();}})()"})
            await asyncio.sleep(3.4)
            await send("Runtime.evaluate", {"expression":
                "(()=>{let id=requestAnimationFrame(()=>{});for(let i=1;i<=id;i++)cancelAnimationFrame(i);return id;})()"})
            await asyncio.sleep(0.25)
            info = json.loads((await send("Runtime.evaluate", {"expression": PROBE, "returnByValue": True}))["result"]["value"])
            print(f"\n=== {theme} ===")
            print("   rotation    top      bottom    top-bottom")
            diffs = []
            body = bg = None
            for deg in (0, 45, 90, 135, 180, 225, 270, 315):
                await send("Runtime.evaluate", {"expression": f"window.__host.style.transform='rotate({deg}deg)'"})
                await asyncio.sleep(0.22)
                s = await send("Page.captureScreenshot", {"format": "png"})
                fp = f"{OUT}/pt-{theme}-{deg}.png"; open(fp, "wb").write(base64.b64decode(s["data"]))
                t, b, bd, pg = measure(fp, info["cx"] * 2, info["cy"] * 2, info["d"] * 2 * 0.375, info["d"] * 2 * 0.465)
                diffs.append(t - b); body, bg = bd, pg
                flag = "OK " if (t - b) > 0 else "BAD"
                print(f"   {deg:4d} deg   {t:.4f}   {b:.4f}    {t-b:+.4f}  {flag}")
            print(f"   -> all positive: {all(d > 0 for d in diffs)}   mean {np.mean(diffs):+.4f}")
            contrast = (max(body, bg) + 0.05) / (min(body, bg) + 0.05)
            print(f"   wheel body {body:.3f} vs page {bg:.3f}  ->  contrast {contrast:.2f}:1")
    proc.kill()
    return 0

# An exit code, so this can be used in a chain or a hook rather than only read
# by a human (#47). It ended at asyncio.run(main()) with main() returning None,
# so it exited 0 whatever it measured.
if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
