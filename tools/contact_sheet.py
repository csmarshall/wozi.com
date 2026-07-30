#!/usr/bin/env python3
"""A review sheet of every gear centre, captured from the real page.

The point is fidelity. It would be quicker to draw the candidates fresh in a
standalone file, but then the sheet shows a drawing of a design rather than the
design — and the two drift the moment either is edited. So this loads the actual
page once per family with ?kind=<type>, photographs a wheel, and tiles the
results. What you pick is what you get.

Families are read out of index.html, so a new one appears here as soon as it
exists, whether it is in the deal or only a candidate.

Usage: tools/contact_sheet.py [base-url] [out.png]
"""

import asyncio
import base64
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/gear_sheet.png"
PORT = 9500
PROFILE = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad/chrome-sheet"
ROOT = Path(__file__).resolve().parent.parent


def families():
    """Read the live and candidate family lists out of index.html."""
    src = (ROOT / "index.html").read_text()

    def block(decl):
        i = src.index(decl)
        j = src.index("[", i)
        depth = 0
        for k in range(j, len(src)):
            if src[k] == "[":
                depth += 1
            elif src[k] == "]":
                depth -= 1
                if depth == 0:
                    return src[j:k + 1]
        raise SystemExit("unterminated " + decl)

    def types(text):
        # only uncommented entries: strip /* ... */ first
        clean = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        return re.findall(r"type:\s*'([a-z]+)'", clean)

    live = types(block("const CENTRE_FAMILIES ="))
    cand = types(block("const CANDIDATE_FAMILIES ="))
    out = [(t, False) for t in live] + [(t, True) for t in cand]
    # the double row is a view of the planetary, not a family of its own
    if "planetary" in live:
        out.insert(live.index("planetary") + 1, ("ravigneaux", False))
    return out


SHOT = r"""
(() => {
  /* the widest wheel that carries a badge -- the one worth photographing */
  /* Real wheels only. The background outriggers are enormous and one of them
     can sit under a badge by chance, which is how the sheet once photographed a
     ghost instead of the gear. */
  const vw = window.innerWidth;
  const svgs = [...document.querySelectorAll('svg')].filter(s => {
    const w = s.getBoundingClientRect().width;
    return w > 60 && w < vw * 0.42;
  });
  let best = null, bw = 0;
  const badges = [...document.querySelectorAll('a[href]')].filter(a => a.getAttribute('aria-label'));
  for (const s of svgs) {
    const r = s.getBoundingClientRect();
    const c = [r.left + r.width / 2, r.top + r.height / 2];
    const has = badges.some(a => {
      const b = a.getBoundingClientRect();
      return Math.hypot(b.left + b.width / 2 - c[0], b.top + b.height / 2 - c[1]) < 20;
    });
    if (has && r.width > bw) { bw = r.width; best = r; }
  }
  if (!best) return JSON.stringify({ error: 'no wheel' });
  /* hide the caps: the centre design is the subject */
  badges.forEach(a => { a.style.visibility = 'hidden'; });
  return JSON.stringify({ x: best.left, y: best.top, w: best.width, h: best.height });
})()
"""


async def main():
    fams = families()
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--window-size=1200,760",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{BASE}", timeout=1) as r:
                ws_url = json.load(r)["webSocketDebuggerUrl"]
                break
        except Exception:
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{BASE}", method="PUT")
                with urllib.request.urlopen(req, timeout=1) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.2)
    if not ws_url:
        proc.kill()
        print("FATAL: no DevTools endpoint")
        return 2

    tiles = []
    mid = 0
    async with websockets.connect(ws_url, max_size=60 * 1024 * 1024) as ws:
        async def send(method, params=None):
            nonlocal mid
            mid += 1
            my = mid
            await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})

        for kind, is_cand in fams:
            url = BASE + ("&" if "?" in BASE else "?") + "kind=" + kind
            await send("Page.navigate", {"url": url})
            await asyncio.sleep(2.4)
            r = await send("Runtime.evaluate", {"expression": SHOT, "returnByValue": True})
            box = json.loads(r["result"]["value"])
            if "error" in box:
                print(f"  {kind}: SKIPPED ({box['error']})")
                continue
            # tighten onto the centre: the design is the subject, not the teeth
            f = 0.80
            cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
            clip = {"x": cx - box["w"] * f / 2, "y": cy - box["h"] * f / 2,
                    "width": box["w"] * f, "height": box["h"] * f, "scale": 3}
            shot = await send("Page.captureScreenshot", {"format": "png", "clip": clip})
            tiles.append((kind, is_cand, base64.b64decode(shot["data"])))
            print(f"  {kind}{'  (candidate)' if is_cand else ''}")

    proc.kill()

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        d = Path(OUT).parent
        for kind, _, data in tiles:
            (d / f"gear_{kind}.png").write_bytes(data)
        print(f"\nPillow not installed — wrote {len(tiles)} separate files to {d}")
        return 0

    import io
    cell = 260
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    label_h = 26
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (24, 27, 31))
    draw = ImageDraw.Draw(sheet)
    for i, (kind, is_cand, data) in enumerate(tiles):
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((cell - 16, cell - 16))
        cx = (i % cols) * cell + (cell - im.width) // 2
        cy = (i // cols) * (cell + label_h) + (cell - im.height) // 2
        sheet.paste(im, (cx, cy))
        text = kind + ("  · candidate" if is_cand else "")
        tw = draw.textlength(text)
        draw.text(((i % cols) * cell + (cell - tw) / 2,
                   (i // cols) * (cell + label_h) + cell + 4),
                  text, fill=(210, 214, 210) if not is_cand else (240, 176, 96))
    sheet.save(OUT)
    print(f"\nwrote {OUT}  ({len(tiles)} designs, {cols}x{rows})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
