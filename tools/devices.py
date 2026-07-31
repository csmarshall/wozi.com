#!/usr/bin/env python3
"""Does the gear train run along the LONG side of the screen, in both orientations?

The page rotates its own axis (`axisRot()` returns 90 when the viewport is taller
than it is wide), so this checks that the rotation actually lands: for each
device, in portrait and in landscape, it measures the bounding box of the linked
wheels and asserts the train's long axis matches the screen's long axis, and that
it spans a decent share of it rather than huddling in the middle.

HONEST ABOUT WHAT THIS IS: Chrome device emulation over CDP — real device metrics,
device pixel ratio, touch and mobile flags and user-agent, which is what the
DevTools device toolbar does. It is NOT an iOS simulator, so it does not catch
WebKit-specific behaviour. There are no iOS runtimes or Android SDK installed on
this machine; if you want true Safari coverage that needs Xcode simulators.

Usage: tools/devices.py [url]
Exit 0 only if every device passes in both orientations.
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
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
PORT = 9600
import tempfile as _tf
# The scratchpad path only exists on Charles's machine; CI gets a temp dir.
PROFILE = _os.environ.get("CHROME_PROFILE") or _tf.mkdtemp(prefix="wozi-chrome-")

IOS_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
IPAD_UA = ("Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
           "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
AND_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/124.0.0.0 Mobile Safari/537.36")

# (label, portrait width, portrait height, dpr, ua, portrait chrome, landscape chrome)
#
# THE CHROME NUMBERS ARE THE POINT. A phone's nominal height is not the height a
# page gets: Safari and Chrome keep a URL bar, and in landscape Safari adds a tab
# strip on top of it.測 measuring against the full device height is what made
# this harness pass a layout that visibly failed on Charles's own iPhone -- the
# viewport it was handed was 100px taller than any real browser would give.
# Values are CSS px of chrome subtracted from the height, read off real Safari
# screenshots (landscape iPhone loses ~117px to the tab strip plus toolbar).
DEVICES = [
    ("iPhone SE (2022)",      375,  667, 2, IOS_UA,      88, 100),
    ("iPhone 13 / 14",        390,  844, 3, IOS_UA,      96, 117),
    ("iPhone 15 Pro Max",     430,  932, 3, IOS_UA,      96, 117),
    ("iPad mini",             744, 1133, 2, IPAD_UA,   64,  64),
    ("iPad Pro 12.9",        1024, 1366, 2, IPAD_UA,     0, 0),
    ("Pixel 8",               412,  915, 2.625, AND_UA,  72,  56),
    ("Galaxy S23 Ultra",      412,  915, 3.5, AND_UA,    72,  56),
    # desktop Safari maximised: the case where the old 1.75 ceiling bit
    ("MacBook Safari full",  1440,  900, 2, IOS_UA,      90,  90),
    ("Ultrawide",            2560, 1080, 1, IOS_UA,      90,  90),
]

# (label, portrait w, portrait h, dpr, ua, orientation, chrome, (top, right, bottom, left))
#
# THE SECOND PASS, and why it has to fake its own numbers. `viewport-fit=cover`
# hands the page the whole display, notch and home indicator included, and the
# page is supposed to WANT that -- the gears run under the chrome. The four fixed
# controls are the exception: they add env(safe-area-inset-*) so they stay
# reachable. Chrome device emulation cannot help here. It implements env() and
# resolves every inset to 0 on every emulated device, because the insets come
# from the real window manager, not from the device metrics override. So there is
# nothing to observe and no way to make Chrome produce one.
#
# What this pass tests instead is the LAYOUT CONSEQUENCE, which is the half that
# lives in this repo: given non-zero insets, do the controls move inward by
# exactly that much and stay clear, and do the gears ignore them and still bleed
# to the physical edge? The insets reach the page through the --safe-* custom
# properties rather than through env() written inline, precisely so they can be
# set from here. Whether iOS then hands those properties the right numbers is
# WebKit's half, and no harness on this machine can check it.
#
# Inset values are Apple's published safe areas for the notch/Dynamic Island
# phones, in CSS px.
SAFE_DEVICES = [
    ("iPhone 13 / 14",     390, 844, 3, IOS_UA, "portrait",   96, (47, 0, 34, 0)),
    ("iPhone 13 / 14",     390, 844, 3, IOS_UA, "landscape", 117, (0, 47, 21, 47)),
    ("iPhone 15 Pro Max",  430, 932, 3, IOS_UA, "portrait",   96, (59, 0, 34, 0)),
    ("iPhone 15 Pro Max",  430, 932, 3, IOS_UA, "landscape", 117, (0, 59, 21, 59)),
]

# Set the four insets, then measure every fixed control against the safe rect and
# the whole assembly against the physical one. Written as a template so the
# Python side owns the numbers.
SAFE_MEASURE = r"""
(() => {
  const s = document.documentElement.style;
  s.setProperty('--safe-t', '%(t)dpx'); s.setProperty('--safe-r', '%(r)dpx');
  s.setProperty('--safe-b', '%(b)dpx'); s.setProperty('--safe-l', '%(l)dpx');
  /* The controls that must NOT bleed: the three corner buttons and the wordmark
     (its <h1>'s fixed parent). Everything else on the page is allowed under the
     chrome and is supposed to be. */
  const ctrls = [...document.querySelectorAll('button')].map(
    b => [b.getAttribute('aria-label') || 'button', b]);
  const h1 = document.querySelector('h1');
  if (h1 && h1.parentElement) ctrls.push(['wordmark', h1.parentElement]);
  const box = ([name, el]) => {
    const r = el.getBoundingClientRect();
    return { name: name, x0: +r.left.toFixed(1), y0: +r.top.toFixed(1),
             x1: +r.right.toFixed(1), y1: +r.bottom.toFixed(1),
             w: +r.width.toFixed(1), h: +r.height.toFixed(1) };
  };
  /* and the machine, which must still reach the physical edges */
  let ax0 = 1e9, ax1 = -1e9, ay0 = 1e9, ay1 = -1e9;
  document.querySelectorAll('svg').forEach(sv => {
    const r = sv.getBoundingClientRect();
    if (r.width < 30) return;
    ax0 = Math.min(ax0, r.left); ax1 = Math.max(ax1, r.right);
    ay0 = Math.min(ay0, r.top);  ay1 = Math.max(ay1, r.bottom);
  });
  return JSON.stringify({
    vw: window.innerWidth, vh: window.innerHeight,
    ctrls: ctrls.map(box),
    allX0: +ax0.toFixed(1), allX1: +ax1.toFixed(1),
    allY0: +ay0.toFixed(1), allY1: +ay1.toFixed(1)
  });
})()
"""

MEASURE = r"""
(() => {
  /* Two different things get measured, because they have different jobs:
     the LINKED wheels are the content and belong centred; the whole assembly,
     ghosts included, is the machine and is supposed to run off both edges so it
     reads as continuing past the frame. */
  const badges = [...document.querySelectorAll('a[href]')].filter(a => {
    const r = a.getBoundingClientRect();
    return a.getAttribute('aria-label') && r.width > 10;
  });
  if (badges.length < 3) return JSON.stringify({ error: 'only ' + badges.length + ' wheels found' });
  let lx0 = 1e9, lx1 = -1e9, ly0 = 1e9, ly1 = -1e9;
  badges.forEach(a => {
    const r = a.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    lx0 = Math.min(lx0, cx); lx1 = Math.max(lx1, cx);
    ly0 = Math.min(ly0, cy); ly1 = Math.max(ly1, cy);
  });
  /* every wheel that is actually drawn, ghosts included */
  let ax0 = 1e9, ax1 = -1e9, ay0 = 1e9, ay1 = -1e9, n = 0;
  document.querySelectorAll('svg').forEach(s => {
    const r = s.getBoundingClientRect();
    if (r.width < 30) return;
    n++;
    ax0 = Math.min(ax0, r.left); ax1 = Math.max(ax1, r.right);
    ay0 = Math.min(ay0, r.top);  ay1 = Math.max(ay1, r.bottom);
  });
  return JSON.stringify({
    links: badges.length, wheels: n,
    vw: window.innerWidth, vh: window.innerHeight,
    linkX0: +lx0.toFixed(1), linkX1: +lx1.toFixed(1),
    linkY0: +ly0.toFixed(1), linkY1: +ly1.toFixed(1),
    allX0: +ax0.toFixed(1), allX1: +ax1.toFixed(1),
    allY0: +ay0.toFixed(1), allY1: +ay1.toFixed(1),
    overflowX: document.documentElement.scrollWidth > window.innerWidth + 1
  });
})()
"""


async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--no-first-run", *CI_FLAGS,
         "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(60):
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

    print(f"Chrome device emulation (not an iOS simulator — none installed)\n")
    print(f"{'device':22} {'orient':10} {'viewport':11} {'covered':7} {'off-ctr':8} verdict")
    bad = 0
    sbad = 0
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

        for label, pw, ph, dpr, ua, pchrome, lchrome in DEVICES:
            for orient in ("portrait", "landscape"):
                w, h = (pw, ph) if orient == "portrait" else (ph, pw)
                h -= pchrome if orient == "portrait" else lchrome   # browser chrome is real
                await send("Emulation.setUserAgentOverride", {"userAgent": ua})
                await send("Emulation.setDeviceMetricsOverride", {
                    "width": w, "height": h, "deviceScaleFactor": dpr, "mobile": True,
                    "screenOrientation": {"type": "portraitPrimary" if orient == "portrait"
                                          else "landscapePrimary",
                                          "angle": 0 if orient == "portrait" else 90}})
                await send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
                await send("Page.navigate", {"url": URL + ("&" if "?" in URL else "?") + f"d={w}x{h}"})
                await asyncio.sleep(2.3)
                r = await send("Runtime.evaluate", {"expression": MEASURE, "returnByValue": True})
                m = json.loads(r["result"]["value"])
                if "error" in m:
                    print(f"{label:22} {orient:10} {w}x{h:<7} {m['error']}")
                    bad += 1
                    continue
                horiz = m["vw"] >= m["vh"]
                if horiz:
                    long_px, a0, a1 = m["vw"], m["allX0"], m["allX1"]
                    l0, l1 = m["linkX0"], m["linkX1"]
                    train_long = "x" if (m["linkX1"] - m["linkX0"]) >= (m["linkY1"] - m["linkY0"]) else "y"
                    want = "x"
                else:
                    long_px, a0, a1 = m["vh"], m["allY0"], m["allY1"]
                    l0, l1 = m["linkY0"], m["linkY1"]
                    train_long = "x" if (m["linkX1"] - m["linkX0"]) >= (m["linkY1"] - m["linkY0"]) else "y"
                    want = "y"
                covered = max(0.0, min(a1, long_px) - max(a0, 0)) / long_px
                reaches = (a0 <= 1) and (a1 >= long_px - 1)
                centre_off = abs(((l0 + l1) / 2) - long_px / 2) / long_px
                ok = (train_long == want) and reaches and centre_off <= 0.06 and not m["overflowX"]
                if not ok:
                    bad += 1
                why = []
                if train_long != want:
                    why.append("runs across the SHORT side")
                if not reaches:
                    why.append(f"stops {max(0, a0):.0f}px short / {max(0, long_px - a1):.0f}px short")
                if centre_off > 0.06:
                    why.append(f"links off-centre by {centre_off:.0%}")
                if m["overflowX"]:
                    why.append("scrolls sideways")
                print(f"{label:22} {orient:10} {str(w) + 'x' + str(h):11} "
                      f"{covered * 100:5.0f}%   {centre_off * 100:4.0f}%    "
                      f"{'ok' if ok else 'FAIL: ' + ', '.join(why)}")

        print(f"\nsafe areas (insets injected — Chrome resolves every env() to 0)\n")
        print(f"{'device':22} {'orient':10} {'insets':16} {'clearance':11} verdict")
        for label, pw, ph, dpr, ua, orient, chrome, insets in SAFE_DEVICES:
            t, r_, b, l = insets
            w, h = (pw, ph) if orient == "portrait" else (ph, pw)
            h -= chrome
            await send("Emulation.setUserAgentOverride", {"userAgent": ua})
            await send("Emulation.setDeviceMetricsOverride", {
                "width": w, "height": h, "deviceScaleFactor": dpr, "mobile": True,
                "screenOrientation": {"type": "portraitPrimary" if orient == "portrait"
                                      else "landscapePrimary",
                                      "angle": 0 if orient == "portrait" else 90}})
            await send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
            await send("Page.navigate", {"url": URL + ("&" if "?" in URL else "?") + f"s={w}x{h}"})
            await asyncio.sleep(2.3)
            res = await send("Runtime.evaluate", {
                "expression": SAFE_MEASURE % {"t": t, "r": r_, "b": b, "l": l},
                "returnByValue": True})
            m = json.loads(res["result"]["value"])
            why = []
            # Every fixed control inside the safe rectangle, and still tappable.
            # Half a pixel of slack: fractional layout, not a real overlap.
            worst = 1e9
            for c in m["ctrls"]:
                clear = min(c["x0"] - l, m["vw"] - r_ - c["x1"],
                            c["y0"] - t, m["vh"] - b - c["y1"])
                worst = min(worst, clear)
                if clear < -0.5:
                    why.append(f"{c['name']} out by {-clear:.0f}px")
                if c["w"] < 24 or c["h"] < 24:
                    why.append(f"{c['name']} is {c['w']:.0f}x{c['h']:.0f}")
            # ...and the machine ignoring all of it, as it is meant to.
            horiz = m["vw"] >= m["vh"]
            long_px = m["vw"] if horiz else m["vh"]
            e0, e1 = (m["allX0"], m["allX1"]) if horiz else (m["allY0"], m["allY1"])
            if e0 > 1 or e1 < long_px - 1:
                why.append("assembly no longer reaches the physical edges")
            if why:
                sbad += 1
            print(f"{label:22} {orient:10} {f'{t}/{r_}/{b}/{l}':16} "
                  f"{worst:7.0f}px   {'ok' if not why else 'FAIL: ' + ', '.join(why)}")

    proc.kill()
    print(f"\n{len(DEVICES) * 2 - bad}/{len(DEVICES) * 2} passed"
          " — assembly must reach BOTH edges of the long side, links centred.")
    print(f"{len(SAFE_DEVICES) - sbad}/{len(SAFE_DEVICES)} passed"
          " — fixed controls clear injected safe-area insets, gears ignore them.")
    return 0 if bad == 0 and sbad == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
