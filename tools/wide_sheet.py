#!/usr/bin/env python3
"""Photograph the train across desktop widths, in one image, and measure it.

The question this exists to answer (#44 / #21): at a wide window the sides look
empty -- is that because the machine is too SMALL, or because the ghost wheels
that already span the full width are too FAINT to see?

Those are different bugs with different fixes and the same numbers, so the only
way to settle it is to look. This tiles one screenshot per width, prints the
measurements beside them, and writes a PNG you can open.

Measured per width:
  assembly   how far the whole chain reaches, ghosts included, as % of window
  linked     how far the wheels carrying badges reach, as % of window
  ghost      contrast ratio of a ghost wheel against the page background

If `assembly` is ~100% or more while the sides still look bare, the ghosts are
there and invisible -> a CONTRAST problem (#21).
If `linked` falls as the window widens, the train is not growing -> a SIZING
problem (#44).

Usage:
  tools/wide_sheet.py [url] [out.png] [--light]
  tools/wide_sheet.py                       # local, dark, default widths
  tools/wide_sheet.py https://wozi.com/     # what is actually live
"""

import asyncio, json, os, random, shutil, subprocess, sys, tempfile, time, urllib.request
import websockets

WIDTHS = [1280, 1600, 2000, 2560]
HEIGHT = 1000

CHROME = (os.environ.get("CHROME")
          or shutil.which("google-chrome") or shutil.which("chromium-browser")
          or shutil.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CI_FLAGS = ([] if sys.platform == "darwin" else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])

PROBE = r"""
(() => {
  const lum = (c) => {                       /* WCAG relative luminance */
    const m = c.match(/[\d.]+/g) || [0, 0, 0];
    const f = m.slice(0, 3).map(v => { v = +v / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2];
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };

  let lo = Infinity, hi = -Infinity, llo = Infinity, lhi = -Infinity, n = 0;
  let ghostFill = null;
  document.querySelectorAll('svg').forEach(s => {
    const w = parseFloat(s.getAttribute('width') || '0');
    if (w < 40) return;
    n++;
    const r = s.getBoundingClientRect();
    lo = Math.min(lo, r.left); hi = Math.max(hi, r.right);
    /* a ghost is a wheel with no badge anywhere near its centre */
    if (!ghostFill && (r.right < 0 || r.left > innerWidth)) {
      const p = s.querySelector('path[fill]');
      if (p) ghostFill = getComputedStyle(p).fill;
    }
  });
  document.querySelectorAll('a[aria-label]').forEach(a => {
    const r = a.getBoundingClientRect();
    if (r.width < 10) return;
    llo = Math.min(llo, r.left); lhi = Math.max(lhi, r.right);
  });
  const bg = getComputedStyle(document.body).backgroundColor;
  return JSON.stringify({
    vw: innerWidth, wheels: n,
    assembly: +(100 * (hi - lo) / innerWidth).toFixed(1),
    linked: +(100 * (lhi - llo) / innerWidth).toFixed(1),
    ghost: ghostFill ? +ratio(ghostFill, bg).toFixed(2) : null,
    bg: bg, ghostFill: ghostFill
  });
})()
"""


async def shoot(url, width, dark, outdir, port):
    profile = tempfile.mkdtemp(prefix="wozi-wide-")
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={port}",
         f"--user-data-dir={profile}", f"--window-size={width},{HEIGHT}",
         "--no-first-run", "--window-position=-4000,-4000",
         "--hide-scrollbars", *CI_FLAGS, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    sep = "&" if "?" in url else "?"
    target = f"{url}{sep}v={random.randint(1, 99999)}"
    for _ in range(80):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/json/new?{target}", method="PUT")
            ws = json.load(urllib.request.urlopen(req, timeout=1))["webSocketDebuggerUrl"]
            break
        except Exception:
            time.sleep(0.25)
    if not ws:
        proc.kill(); shutil.rmtree(profile, ignore_errors=True)
        return None
    try:
        async with websockets.connect(ws, max_size=40 * 1024 * 1024) as c:
            mid = 0
            async def send(m, p=None):
                nonlocal mid
                mid += 1; my = mid
                await c.send(json.dumps({"id": my, "method": m, "params": p or {}}))
                while True:
                    msg = json.loads(await c.recv())
                    if msg.get("id") == my:
                        return msg.get("result", {})
            await send("Emulation.setEmulatedMedia", {"features": [
                {"name": "prefers-color-scheme", "value": "dark" if dark else "light"}]})
            await send("Runtime.enable")
            await asyncio.sleep(4.0)
            r = await send("Runtime.evaluate", {"expression": PROBE, "returnByValue": True})
            d = json.loads(r["result"]["value"])
            shot = await send("Page.captureScreenshot", {"format": "png"})
            path = os.path.join(outdir, f"w{width}.png")
            import base64
            with open(path, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            d["png"] = path
            return d
    finally:
        proc.kill(); shutil.rmtree(profile, ignore_errors=True)


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dark = "--light" not in sys.argv
    url = args[0] if args else "http://127.0.0.1:8765/"
    out = args[1] if len(args) > 1 else os.path.join(
        tempfile.gettempdir(), f"wozi-wide-{int(time.time())}.png")
    outdir = tempfile.mkdtemp(prefix="wozi-shots-")

    print(f"{url}   {'dark' if dark else 'light'} mode\n")
    print(f"{'width':>6} {'wheels':>7} {'assembly':>9} {'linked':>7} {'ghost vs page':>14}")
    rows = []
    for i, w in enumerate(WIDTHS):
        d = await shoot(url, w, dark, outdir, 9700 + i)
        if not d:
            print(f"{w:>6}   (no data)"); continue
        rows.append(d)
        g = f"{d['ghost']:.2f}:1" if d["ghost"] else "   n/a"
        print(f"{w:>6} {d['wheels']:>7} {d['assembly']:>8.1f}% {d['linked']:>6.1f}% {g:>14}")

    if not rows:
        print("\nnothing captured"); return 2

    # stack the screenshots into one tall image, scaled to a common width
    try:
        from PIL import Image
        imgs = [Image.open(r["png"]) for r in rows]
        W = max(i.width for i in imgs)
        scaled = [i.resize((W, int(i.height * W / i.width))) if i.width != W else i
                  for i in imgs]
        sheet = Image.new("RGB", (W, sum(i.height for i in scaled)), (10, 12, 14))
        y = 0
        for i in scaled:
            sheet.paste(i, (0, y)); y += i.height
        sheet.save(out)
        print(f"\nwrote {out}")
    except ImportError:
        print("\nPillow not installed — individual shots are in:")
        for r in rows:
            print("  " + r["png"])
        out = outdir

    print("\nRead it like this:")
    print("  assembly stays ~100%+ while the sides LOOK bare  -> the ghosts are")
    print("     there and too faint. A CONTRAST problem (#21).")
    print("  linked falls as the window widens                -> the train is not")
    print("     growing with the window. A SIZING problem (#44).")
    print("  ghost vs page under about 1.5:1 in dark mode is close to invisible.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
