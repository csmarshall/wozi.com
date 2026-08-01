#!/usr/bin/env python3
"""Does the hover pill's label fit inside its own clip box?

The label span sets `overflow: hidden` and that is NOT optional -- it is what
lets the pill open by animating `max-width` from 0. But overflow cannot be
hidden on one axis alone, so asking for it horizontally takes the vertical with
it: if the line box is shorter than the ink, the descenders are not merely
overflowing, they are SLICED OFF. That is exactly what happened with
`font: 13px/1` -- a line box the same height as the font size, with the font's
own box 18px tall -- and "Instagram" lost 1.8px of the tail of its g.

Nothing measured that. `tools/test.js` is geometry, `devices.py` is layout and
`verify_motion.py` is animation; no gate has ever looked at type. So the bug was
reported by eye, fixed by measurement, and could have come back the same way.

This hovers each badge with a REAL mouse -- `Input.dispatchMouseEvent`, because
the badge's hover handler is bound to the element and a synthetic `mouseenter`
built in JS does not open the pill -- then, for each label:

  - takes the font's own box (ascent + descent) and this string's own deepest
    ink from canvas TextMetrics, using the same stack the element renders in
  - places the baseline by the half-leading rule: (lineHeight - fontBox) / 2
  - compares baseline + inkDescent against the clip edge

and fails if any label's ink runs past its clip edge.

TWO-SIDED ON PURPOSE (#46). It also asserts each pill actually OPENED. A pill
stuck shut has zero width and nothing to clip, so a clipping check alone would
pass most loudly on a page where the feature is broken outright.

Usage: python3 tools/pill_clip.py [url]
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

# CI runs on Linux, where Chrome is not in /Applications. Honour $CHROME, then
# whatever is on PATH, then the macOS bundle. Same order as the other harnesses.
CHROME = (os.environ.get("CHROME")
          or shutil.which("google-chrome") or shutil.which("chromium-browser")
          or shutil.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if sys.platform == "darwin" else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
PORT = int(os.environ.get("CDP_PORT", "9412"))
PROFILE = os.environ.get("CHROME_PROFILE") or tempfile.mkdtemp(prefix="wozi-pill-")

# Ink may not reach the clip edge, but it may not pass it either. A tolerance
# of zero would make the gate a coin toss on sub-pixel line-box rounding --
# WebKit reports the 18.2px box back as 18 -- so allow a twentieth of a pixel,
# which is far below anything that can be seen and far below the 0.8px of room
# the shipped line-height actually leaves.
TOLERANCE = 0.05

# Every badge, so the harness does not have to be told what links exist.
LIST_JS = r"""
(() => {
  const out = [];
  document.querySelectorAll('a[href][aria-label]').forEach((a) => {
    const r = a.getBoundingClientRect();
    if (r.width < 10 || r.height < 10) return;
    /* the badge carries a label span; the Table of Gears rows do not */
    const span = [...a.querySelectorAll('span')].find(
      (s) => (s.textContent || '').trim().length > 0);
    if (!span) return;
    out.push({ label: a.getAttribute('aria-label'),
               x: r.left + r.width / 2, y: r.top + r.height / 2 });
  });
  return JSON.stringify(out);
})()
"""

# Measures the badge whose aria-label is %LABEL%, in whatever state it is in.
MEASURE_JS = r"""
(() => {
  const a = [...document.querySelectorAll('a[href][aria-label]')].find(
    (x) => x.getAttribute('aria-label') === %LABEL%);
  if (!a) return JSON.stringify({ err: 'badge vanished' });
  const span = [...a.querySelectorAll('span')].find(
    (s) => (s.textContent || '').trim().length > 0);
  if (!span) return JSON.stringify({ err: 'no label span' });

  const c = getComputedStyle(span);
  /* The badge scales 1.06 on hover, so getBoundingClientRect is in SCALED
     pixels while the font metrics below are in CSS pixels. Read the box from
     offsetWidth/offsetHeight, which are not scaled, and the two agree. */
  const cv = document.createElement('canvas').getContext('2d');
  cv.font = c.fontWeight + ' ' + c.fontSize + ' ' + c.fontFamily;
  const m = cv.measureText(span.textContent);
  const fa = m.fontBoundingBoxAscent, fd = m.fontBoundingBoxDescent;
  const lh = c.lineHeight === 'normal' ? (fa + fd) : parseFloat(c.lineHeight);
  /* the font box is centred in the line box; negative leading pulls the
     baseline UP the box and pushes the descender out of the bottom */
  const baseline = (lh - (fa + fd)) / 2 + fa;
  const inkBottom = baseline + m.actualBoundingBoxDescent;
  /* overflow:hidden clips at the PADDING box -- measure the padding rather
     than assuming there is none */
  const clipBottom = span.offsetHeight - parseFloat(c.paddingBottom);

  /* Which family actually rendered. document.fonts.check() is no use here: it
     answers true for any family that is not a pending FontFace, installed or
     not. A width against a deliberately bogus family is decisive, because a
     name that does not resolve falls through to the same last resort. */
  const widthIn = (fam) => {
    cv.font = '650 13px "' + fam + '", monospace';
    return cv.measureText('Handgloves 0123456789').width;
  };
  const bogus = widthIn('ZzNoSuchFaceZz');
  const used = (c.fontFamily.split(',')
    .map((f) => f.trim().replace(/^["']|["']$/g, ''))
    .find((f) => Math.abs(widthIn(f) - bogus) > 0.01)) || '(last resort)';

  return JSON.stringify({
    text: span.textContent, used: used,
    openW: span.offsetWidth,
    fontSize: parseFloat(c.fontSize), lineHeight: +lh.toFixed(2),
    fontAscent: +fa.toFixed(2), fontDescent: +fd.toFixed(2),
    inkDescent: +m.actualBoundingBoxDescent.toFixed(2),
    baseline: +baseline.toFixed(2), inkBottom: +inkBottom.toFixed(2),
    clipBottom: +clipBottom.toFixed(2),
    overrun: +(inkBottom - clipBottom).toFixed(2)
  });
})()
"""


async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--window-size=1600,1000",
         "--no-first-run", *CI_FLAGS, "--no-default-browser-check",
         "--disable-features=Translate", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(60):
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/json/new?about:blank", timeout=2) as r:
                ws_url = json.load(r)["webSocketDebuggerUrl"]
                break
        except Exception:
            try:  # older Chrome requires PUT on /json/new
                req = urllib.request.Request(
                    f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")
                with urllib.request.urlopen(req, timeout=2) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.25)
    if not ws_url:
        proc.kill()
        print("FATAL: could not reach Chrome DevTools endpoint")
        return 2

    mid = 0
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        async def send(method, params=None):
            nonlocal mid
            mid += 1
            my = mid
            await ws.send(json.dumps({"id": my, "method": method,
                                      "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})

        async def ev(expr):
            r = await send("Runtime.evaluate", {"expression": expr,
                                                "returnByValue": True,
                                                "awaitPromise": True})
            return r.get("result", {}).get("value")

        await send("Runtime.enable")
        await send("Page.enable")
        # The CDP profile persists across runs, so a cached document is a real
        # hazard -- one of these harnesses served a 300s-old page once.
        bust = ("&" if "?" in URL else "?") + "v=" + str(int(time.time() * 1000))
        await send("Page.navigate", {"url": URL + bust})
        await asyncio.sleep(4.0)

        badges = json.loads(await ev(LIST_JS))
        if not badges:
            proc.kill()
            print("FATAL: no badges found — is anything serving " + URL + "?")
            return 2

        rows = []
        for b in badges:
            lab = json.dumps(b["label"])
            # Park the pointer well away first, so leaving the previous badge is
            # a real mouseleave and each measurement starts from rest.
            await send("Input.dispatchMouseEvent",
                       {"type": "mouseMoved", "x": 4, "y": 4, "buttons": 0})
            await asyncio.sleep(0.15)
            shut = json.loads(await ev(MEASURE_JS.replace("%LABEL%", lab)))
            # A REAL mouse move. A MouseEvent built in JS and dispatched at the
            # element does not open the pill; the width stays 0 and the gate
            # would then be measuring a collapsed span.
            await send("Input.dispatchMouseEvent",
                       {"type": "mouseMoved", "x": b["x"], "y": b["y"],
                        "buttons": 0})
            await asyncio.sleep(0.9)   # the max-width transition is 260ms
            d = json.loads(await ev(MEASURE_JS.replace("%LABEL%", lab)))
            d["shutW"] = shut.get("openW")
            d["aria"] = b["label"]
            rows.append(d)

    proc.kill()

    print(f"url                : {URL}")
    print(f"badges measured    : {len(rows)}")
    print()
    print("label        face              lh    asc/desc  baseline    ink"
          "   clip  overrun  width")
    worst = -99.0
    stuck = []
    broken = [r for r in rows if r.get("err")]
    for r in rows:
        if r.get("err"):
            print(f"  {r.get('aria','?'):<12} ERROR {r['err']}")
            continue
        worst = max(worst, r["overrun"])
        if r["openW"] <= max(1, (r["shutW"] or 0)):
            stuck.append(r["text"])
        print(f"  {r['text']:<12} {r['used']:<16}"
              f"{r['lineHeight']:>5}"
              f"{(str(r['fontAscent']) + '/' + str(r['fontDescent'])):>10}"
              f"{r['baseline']:>10}{r['inkBottom']:>7}{r['clipBottom']:>7}"
              f"{r['overrun']:>+9.2f}"
              f"{r['shutW']:>4}->{r['openW']:<4}"
              f"{'  CLIPPED' if r['overrun'] > TOLERANCE else ''}")

    print()
    print(f"worst overrun      : {worst:+.2f}px   "
          f"(tolerance {TOLERANCE:+.2f})")
    print(f"pills that opened  : {len(rows) - len(stuck) - len(broken)}"
          f" of {len(rows)}")
    if stuck:
        print("  never opened     : " + ", ".join(stuck))

    ok = (not broken) and (not stuck) and worst <= TOLERANCE
    print()
    print("PASS — every label sits inside its own clip box" if ok else
          "FAIL — see above")
    return 0 if ok else 1


sys.exit(asyncio.run(main()))
