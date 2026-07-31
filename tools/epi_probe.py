#!/usr/bin/env python3
"""Ground truth for the planetary set, taken from the rendered page.

The arithmetic in index.html says the carrier stands still, the planets spin in
place, and the sun counter-rotates. That is only true if the browser resolves
each element's transform about the origin we think it does -- and the planet
groups use a CSS `transform` while their placement uses SVG attribute
transforms, which do NOT share an origin convention.

So don't reason about it: read getScreenCTM off the real elements, twice, and
decompose. Reports for every moving member:
  centre drift  -- how far its own origin moved (a spinning planet drifts 0;
                   an orbiting one sweeps an arc)
  rotation      -- degrees turned, and the ratio against the host wheel

Usage: tools/epi_probe.py [url]   (default http://127.0.0.1:8765/?kind=planetary)
"""

import asyncio
import json
import subprocess
import sys
import time
import urllib.request

import websockets

import os as _os, shutil as _sh, sys as _sys
def _sys_platform_is_darwin():
    return _sys.platform == "darwin"
# CI runs on Linux, where Chrome is not in /Applications. Honour $CHROME,
# then fall back to whatever is on PATH, then to the macOS bundle.
CHROME = (_os.environ.get("CHROME")
          or _sh.which("google-chrome") or _sh.which("chromium-browser")
          or _sh.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if _sys_platform_is_darwin() else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/?kind=planetary"
PORT = 9341
PROFILE = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad/chrome-epi"

SAMPLE = r"""
(() => {
  /* The planetary wheel is the one whose svg contains a group keyed epicarrier;
     find it structurally rather than by index -- the deal moves it. */
  const svgs = [...document.querySelectorAll('svg')];
  let host = null;
  for (const s of svgs) {
    if (s.querySelector('g[data-epi="carrier"]') || s.innerHTML.indexOf('epicarrier') >= 0) { host = s; break; }
  }
  /* Fall back: the wheel that owns the most nested <g> with a rotate() style. */
  if (!host) {
    let best = 0;
    for (const s of svgs) {
      const n = [...s.querySelectorAll('g')].filter(g => (g.style.transform || '').indexOf('rotate') === 0).length;
      if (n > best) { best = n; host = s; }
    }
  }
  if (!host) return JSON.stringify({ error: 'no planetary wheel found' });

  const dec = (el) => {
    const m = el.getScreenCTM();
    if (!m) return null;
    return { x: m.e, y: m.f, rot: Math.atan2(m.b, m.a) * 180 / Math.PI };
  };

  const out = { members: [] };
  const hostG = host.querySelector('g');           /* the wheel's own rotating group */
  const rot = [...host.querySelectorAll('g')].filter(g => (g.style.transform || '').indexOf('rotate') === 0);
  out.members.push({ name: 'wheel', ...dec(host.querySelector('g') || host) });
  rot.forEach((g, i) => {
    const d = dec(g);
    if (!d) return;
    /* Depth tells carrier (child of svg root chain) from planet (inside a
       translate) -- report it so the caller can label without guessing. */
    let depth = 0, p = g;
    while (p && p !== host) { depth++; p = p.parentNode; }
    const bb = g.getBBox();
    out.members.push({ name: 'g' + i, depth: depth, ...d, bbw: +bb.width.toFixed(1),
                       style: g.style.transform });
  });
  return JSON.stringify(out);
})()
"""


async def cdp():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--window-size=1440,900",
         "--no-first-run", *CI_FLAGS, "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{URL}",
                                        timeout=1) as r:
                ws_url = json.load(r)["webSocketDebuggerUrl"]
                break
        except Exception:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
                with urllib.request.urlopen(req, timeout=1) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.2)
    if not ws_url:
        proc.kill()
        print("FATAL: no DevTools endpoint")
        return 2

    mid = 0
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        async def send(method, params=None):
            nonlocal mid
            mid += 1
            my = mid
            await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})

        async def ev(expr):
            r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
            return r.get("result", {}).get("value")

        await send("Runtime.enable")
        await asyncio.sleep(2.0)
        # give the flywheel a shove so there is motion to measure
        await ev("window.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight'}))")
        await asyncio.sleep(0.4)

        a = json.loads(await ev(SAMPLE))
        await asyncio.sleep(0.7)
        b = json.loads(await ev(SAMPLE))

    proc.kill()

    if "error" in a:
        print("FATAL:", a["error"])
        return 2

    wa = a["members"][0]
    wb = b["members"][0]

    def dr(p, q):
        d = q["rot"] - p["rot"]
        while d > 180:
            d -= 360
        while d < -180:
            d += 360
        return d

    wheel = dr(wa, wb)
    print(f"host wheel turned {wheel:+.3f} deg in the sample window\n")
    print(f"{'member':8} {'depth':>5} {'bbox w':>7} {'centre drift':>13} {'turned':>9} {'ratio':>8}  style")
    for p, q in zip(a["members"][1:], b["members"][1:]):
        drift = ((q["x"] - p["x"]) ** 2 + (q["y"] - p["y"]) ** 2) ** 0.5
        turned = dr(p, q)
        ratio = turned / wheel if abs(wheel) > 1e-6 else float("nan")
        print(f"{p['name']:8} {p['depth']:>5} {p['bbw']:>7} {drift:>12.2f}px {turned:>+8.2f} {ratio:>+8.3f}  {p['style']}")
    print("\nA planet on a fixed stud drifts 0px. Anything that sweeps an arc is orbiting.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(cdp()))
