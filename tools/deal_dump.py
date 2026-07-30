#!/usr/bin/env python3
"""What actually varies between page loads?

Loads the page N times and dumps, per wheel: tooth count, radius, centre
position, which centre family and variant it was dealt, and its colour. Then
reports which of those columns ever changed. Answers "is this the same machine
every time, or does it only look that way" without guessing.

Also measures the planetary wheel's hub cap against its sun, since the cap
covering the sun is what stops the set reading as an epicyclic.

Usage: tools/deal_dump.py [url] [loads]
"""

import asyncio
import json
import subprocess
import sys
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
LOADS = int(sys.argv[2]) if len(sys.argv) > 2 else 6
PORT = 9371
PROFILE = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad/chrome-deal"

SAMPLE = r"""
(() => {
  const svgs = [...document.querySelectorAll('svg')].filter(s => s.getBoundingClientRect().width > 40);
  const wheels = svgs.map((s) => {
    const r = s.getBoundingClientRect();
    const teethPath = s.querySelector('path[d]');
    /* tooth count: the stamp text on the rim reads "M7 Z17" */
    let stamp = '';
    s.querySelectorAll('text').forEach(t => { const v = (t.textContent || '').trim();
      if (/Z\d+/.test(v)) stamp = v; });
    /* colour: the body fill of the largest path */
    let fill = '';
    let best = 0;
    s.querySelectorAll('path').forEach(p => {
      const bb = p.getBBox ? p.getBBox() : null;
      if (bb && bb.width > best) { best = bb.width; fill = p.getAttribute('fill') || ''; }
    });
    /* centre family: fingerprint by what the centre contains */
    const inner = s.innerHTML;
    let kind = 'unknown';
    const marks = [['epiring','planetary'],['labyrinth','labyrinth']];
    for (const [needle, name] of marks) if (inner.indexOf(needle) >= 0) kind = name;
    return {
      cx: +(r.left + r.width / 2).toFixed(0), cy: +(r.top + r.height / 2).toFixed(0),
      outerR: +(r.width / 2).toFixed(1), stamp, fill, kind,
      paths: s.querySelectorAll('path').length,
      circles: s.querySelectorAll('circle').length,
    };
  });
  return JSON.stringify({ wheels });
})()
"""

MEASURE = r"""
(() => {
  const svgs = [...document.querySelectorAll('svg')];
  let host = null, bestN = 0;
  for (const s of svgs) {
    const n = [...s.querySelectorAll('g')].filter(g => (g.style.transform || '').indexOf('rotate') === 0).length;
    if (n > bestN) { bestN = n; host = s; }
  }
  if (!host || bestN < 2) return JSON.stringify({ planetary: false });
  const hr = host.getBoundingClientRect();
  const hc = [hr.left + hr.width / 2, hr.top + hr.height / 2];
  const rot = [...host.querySelectorAll('g')].filter(g => (g.style.transform || '').indexOf('rotate') === 0);
  const out = { planetary: true, wheelOuterR: +(hr.width / 2).toFixed(1) };
  const sun = rot[rot.length - 1];
  if (sun) { const b = sun.getBoundingClientRect(); out.sunR = +(Math.max(b.width, b.height) / 2).toFixed(1); }
  document.querySelectorAll('a[href]').forEach((a) => {
    const r = a.getBoundingClientRect();
    const d = Math.hypot(r.left + r.width / 2 - hc[0], r.top + r.height / 2 - hc[1]);
    if (d < 25) out.capR = +(r.width / 2).toFixed(1);
  });
  return JSON.stringify(out);
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
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{URL}", timeout=1) as r:
                ws_url = json.load(r)["webSocketDebuggerUrl"]
                break
        except Exception:
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
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
    loads = []
    meas = []
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

        for i in range(LOADS):
            if i:
                await send("Page.navigate", {"url": URL + ("&" if "?" in URL else "?") + "n=" + str(i)})
            await asyncio.sleep(2.2)
            r = await send("Runtime.evaluate", {"expression": SAMPLE, "returnByValue": True})
            loads.append(json.loads(r["result"]["value"])["wheels"])
            r2 = await send("Runtime.evaluate", {"expression": MEASURE, "returnByValue": True})
            meas.append(json.loads(r2["result"]["value"]))
    proc.kill()

    n = min(len(l) for l in loads)
    print(f"{len(loads)} loads, {n} wheels each\n")
    cols = ["stamp", "outerR", "cx", "cy", "fill", "paths", "circles"]
    print(f"{'column':10} {'varies?':9} example values across loads")
    for c in cols:
        seen = []
        for w in range(n):
            vals = [str(l[w][c]) for l in loads]
            seen.append(len(set(vals)) > 1)
        varies = any(seen)
        sample = " | ".join(str(l[0][c]) for l in loads[:4])
        which = f"wheels {sum(seen)}/{n}" if varies else "NEVER"
        print(f"{c:10} {which:9} {sample}")

    print("\nper-wheel geometry, load 1 vs load 2:")
    for w in range(n):
        a, b = loads[0][w], loads[1][w]
        same = "same" if (a["stamp"] == b["stamp"] and abs(a["cx"] - b["cx"]) < 2
                          and abs(a["cy"] - b["cy"]) < 2) else "DIFFERS"
        print(f"  wheel {w}: {a['stamp']:8} at ({a['cx']},{a['cy']}) r={a['outerR']:6}  ->  "
              f"{b['stamp']:8} at ({b['cx']},{b['cy']})  {same}")

    print("\nplanetary hub cap vs sun (screen px radius):")
    for i, m in enumerate(meas):
        if not m.get("planetary"):
            print(f"  load {i + 1}: no planetary wheel found")
            continue
        cap, sun = m.get("capR"), m.get("sunR")
        verdict = "sun HIDDEN" if (cap and sun and cap >= sun) else "sun visible"
        print(f"  load {i + 1}: cap r={cap}  sun r={sun}  -> {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
