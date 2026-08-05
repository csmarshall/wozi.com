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
import re
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
PORT = int(_os.environ.get("CDP_PORT") or 0) or _free_port()
import tempfile as _tf
# The scratchpad path only exists on Charles's machine; CI gets a temp dir.
PROFILE = _os.environ.get("CHROME_PROFILE") or _tf.mkdtemp(prefix="wozi-chrome-")

# THE STANDARD GEAR SIZE COMES OUT OF index.html, never a copy of it. A harness
# holding its own number agrees with itself forever while the page moves, which
# is the failure tools/test.js exists to avoid and states in its own header.
def _page_const(name):
    src = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "index.html")
    with open(src, encoding="utf-8") as fh:
        m = re.search(r"\b" + re.escape(name) + r"\s*=\s*([0-9.]+)\s*[,;]", fh.read())
    if not m:
        raise SystemExit(f"FATAL: {name} not found in index.html")
    return float(m.group(1))


TARGET_GEAR_PX = _page_const("TARGET_GEAR_PX")
# The top of the deal's range. Read here for the same reason as the line above:
# the gear bound's tolerance is one tooth wide and a tooth is 1/(TEETH_MAX + 2)
# of a wheel, so a harness holding its own copy would keep agreeing with itself
# after the deal's range moved.
TEETH_MAX = _page_const("TEETH_MAX")

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
# strip on top of it. Measuring against the full device height is what made
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
    # #2: "train may sit right of centre at very large widths" -- pushing the
    # long axis up past where anyone reported the bug, to check whether the
    # LINK_SHARE rework (fitStage, index.html) actually killed it or just
    # moved the threshold out of reach of the old device list.
    #
    # 3440 AND 5120 ARE BACK (#80), and the reason they were out is the reason
    # this list now goes this wide. Both were dropped during the #2 work because
    # they reproducibly failed a DIFFERENT check -- "stops short" of the physical
    # edges, a coverage gap rather than a centring one -- and closing that meant
    # deciding how many more outrigger wheels 5120px of empty edge was worth
    # against the per-SVG frame cost #6 fought to remove. That was Charles's call
    # to make, not a silent fix, and since this tool gates CI a row with no agreed
    # fix would have blocked every deploy over an open question.
    #
    # The call was made in #80: the run's wheel count is derived from the distance
    # it has to cover, so it is no longer a number anyone chooses. Measured at
    # 8 loads per width, ghost extent against the physical edges:
    #
    #                 before #80          after #80
    #   3440x1440     8/8 reach           8/8 reach
    #   5120x1440     0/8, 457-639px      8/8 reach
    #
    # and the frame cost that made it a question came in at nothing measurable:
    # 31 -> 59 wheels at 5120, median frame time flat at the 16.7ms vsync interval
    # and p95 17.3 -> 17.5ms. Hopefully that holds on hardware weaker than this
    # machine; it is headroom being spent, and headless Chrome here has plenty.
    #
    # THESE TWO ROWS ARE WHY THE GATE READ 20/20 WHILE COVERAGE VISIBLY FAILED.
    # Not a wrong measure and not a settling race -- the two widths where the page
    # failed were the two widths the list did not contain. A gate is only ever
    # green about what it was pointed at.
    ("Ultrawide 3440",       3440, 1440, 1, IOS_UA,      90,  90),
    ("Super ultrawide",      5120, 1440, 1, IOS_UA,      90,  90),
    ("QHD wide",             2560, 1440, 1, IOS_UA,      90,  90),
]

# (label, portrait w, portrait h, dpr, ua, orientation, chrome, (top, right, bottom, left))
#
# THE SECOND PASS, and why it has to fake its own numbers. `viewport-fit=cover`
# hands the page the whole display, notch and home indicator included, and the
# page is supposed to WANT that -- the gears run under the chrome. The fixed
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
  /* The controls that must NOT bleed: every corner button, the speed slider,
     and the wordmark (its <h1>'s fixed parent). Everything else on the page
     is allowed under the chrome and is supposed to be.

     FORM CONTROLS ARE IN THE LIST, and were not until GitHub #108 (CL#114).
     This selected `button` alone -- every control the page had at the time,
     and therefore a check that would silently stop covering the corner the
     day one of them stopped being a button. That day is now: the speed
     control is an `input[type=range]` inside the pop-out panel, a fixed
     control (its ancestor <nav> is position:fixed) the safe-area pass could
     not otherwise see. Enumerated by tag rather than counted, so the next one
     is measured the day it exists. */
  const ctrls = [...document.querySelectorAll(
    'button,input:not([type="hidden"]),select,textarea')].map(
    b => [b.getAttribute('aria-label') || b.getAttribute('title') || b.tagName.toLowerCase(), b]);
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
  /* HOW BIG A GEAR ACTUALLY CAME OUT, which is the thing index.html now promises
     (TARGET_GEAR_PX) and the thing GitHub #75 was about. Read off the wheel's
     own `width` attribute rather than its bounding box: the wrappers rotate, and
     a rotated box over-reports by up to sqrt(2). The filter is the promoted
     wrapper, which is what distinguishes a wheel from the full-stage chains
     <svg> -- that one is solved.w * S across and would swamp the maximum. */
  let gear = 0;
  document.querySelectorAll('svg').forEach(s => {
    const w = s.getAttribute('width');
    if (!w || /%$/.test(w) || !(parseFloat(w) > 30)) return;
    if (!s.parentElement || getComputedStyle(s.parentElement).willChange !== 'transform') return;
    gear = Math.max(gear, parseFloat(w));
  });
  /* Every wheel that is actually DRAWN, ghosts included -- and only those.
     This used to take any <svg> wider than 30px, which quietly let the page's
     container elements answer the question. The largest of them is the full-stage
     `key: 'chains'` svg: it is `solved.w * S` across, paints nothing while no drive
     strand is enabled, and at 5120x1440 measured ~40px WIDER than the outermost
     wheel. So "the assembly reaches both edges" could be satisfied by a declared
     box rather than by any visible machinery. It never was the reason this gate
     passed while coverage failed (#80 was the missing widths, above) -- but a
     coverage measure that can be answered by an empty container is one screenful
     of drift away from being exactly that, so it measures paint now.

     A wheel's own wrapper is `transform: rotate(Ndeg)` inside the zero-size offset
     div its layer positions it with. That signature belongs to the linked wheels
     and the ghosts alike, and to nothing else on the page. */
  let ax0 = 1e9, ax1 = -1e9, ay0 = 1e9, ay1 = -1e9, n = 0;
  document.querySelectorAll('svg').forEach(s => {
    const r = s.getBoundingClientRect();
    if (r.width < 30) return;
    const p = s.parentElement, gp = p && p.parentElement;
    if (!p || !gp) return;
    if (!/^transform:\s*rotate\(/.test(p.getAttribute('style') || '')) return;
    if (!/width:\s*0px/.test(gp.getAttribute('style') || '')) return;
    n++;
    ax0 = Math.min(ax0, r.left); ax1 = Math.max(ax1, r.right);
    ay0 = Math.min(ay0, r.top);  ay1 = Math.max(ay1, r.bottom);
  });
  if (!n) return JSON.stringify({ error: 'no wheels found — the wrapper signature the assembly measure keys on has changed' });
  return JSON.stringify({
    links: badges.length, wheels: n, gear: +gear.toFixed(1),
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
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
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
    print(f"{'device':22} {'orient':10} {'viewport':11} {'covered':7} {'links':6} "
          f"{'gear':>7}  verdict")
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

        # SETTLE-POLL, NOT A FIXED SLEEP. Chasing #2, some FAILs at large widths
        # looked at first like an artifact of running ~30 navigations back to back
        # in one Chrome tab without ever restarting the renderer -- a fixed 2.3s
        # wait reading badges before fitStage's resize settle had finished. That
        # turned out not to be the actual mechanism (the FAILs were real, and
        # #2's fix in index.html's solve() is what cleared them), so this is not
        # load-bearing for #2 the way it first looked. It is still a genuine
        # improvement over a fixed sleep on its own merits: poll until two
        # consecutive reads of the measured geometry agree, so the verdict
        # reflects the settled layout rather than a guessed wait, whatever is
        # loading the renderer at the time.
        async def measure_settled(expr, max_wait=6.0, poll=0.3, tol=0.5):
            keys = ("linkX0", "linkX1", "linkY0", "linkY1", "allX0", "allX1", "allY0", "allY1")
            prev = None
            waited = 0.0
            last = None
            while waited < max_wait:
                r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
                m = json.loads(r["result"]["value"])
                last = m
                if "error" in m:
                    return m
                if prev is not None and all(abs(m[k] - prev[k]) <= tol for k in keys):
                    return m
                prev = m
                await asyncio.sleep(poll)
                waited += poll
            return last  # never settled inside the budget -- report the last read anyway

        # THE DEAL IS SEEDED, ONE FIXED SEED PER ROW.
        #
        # Every wheel on this page is dealt at random, so two loads of one profile
        # are two different machines -- and this tool's verdict was a property of
        # whichever machine it happened to get. It bit for real: CI failed two rows
        # on a gear measuring 215.4px against the 222px standard, while the same
        # rows passed ten times running here. Measured over 10 loads at 1080x2470,
        # the gear comes out 215.4 or 221.0 depending only on the deal, and the
        # bound below asks for 217.6 -- so those rows have been a coin toss since
        # #85, and every green run of them was luck rather than evidence.
        #
        # A flaky gate is worse than a narrow one: it teaches everyone to re-run
        # until it passes, which is how a real failure gets waved through. So the
        # deal is pinned. Breadth is not lost, because the seed varies BY ROW --
        # 24 profiles still exercise 24 different machines, the same 24 every time.
        #
        # Same LCG and the same reasoning as tools/pixel_regress.py, and the seed
        # is read from the URL rather than baked in, so the injection happens once
        # and each navigation names its own. Determinism lives in the harness and
        # never in index.html -- there is no test hook in the shipped page.
        # Page.enable FIRST. Without it the injection is accepted and silently
        # never runs, which reads exactly like a seed that does not work: two runs
        # of this tool came back with different deals and the same 24/24.
        await send("Page.enable")
        await send("Runtime.enable")
        await send("Page.addScriptToEvaluateOnNewDocument", {"source": """
          (() => {
            const m = /[?&]seed=(\\d+)/.exec(location.search);
            if (!m) return;
            let s = +m[1] >>> 0;
            Math.random = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
          })();
        """})
        seed = 20260804
        for label, pw, ph, dpr, ua, pchrome, lchrome in DEVICES:
            for orient in ("portrait", "landscape"):
                seed += 1
                w, h = (pw, ph) if orient == "portrait" else (ph, pw)
                h -= pchrome if orient == "portrait" else lchrome   # browser chrome is real
                await send("Emulation.setUserAgentOverride", {"userAgent": ua})
                await send("Emulation.setDeviceMetricsOverride", {
                    "width": w, "height": h, "deviceScaleFactor": dpr, "mobile": True,
                    "screenOrientation": {"type": "portraitPrimary" if orient == "portrait"
                                          else "landscapePrimary",
                                          "angle": 0 if orient == "portrait" else 90}})
                await send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
                await send("Page.navigate", {"url": URL + ("&" if "?" in URL else "?")
                                             + f"d={w}x{h}&seed={seed}"})
                await asyncio.sleep(2.3)
                m = await measure_settled(MEASURE)
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
                # The LINKED wheels must sit wholly on screen with room at both
                # ends for a ghost -- coverage comes from the chain being longer,
                # never from an icon running off the edge.
                link_share = (l1 - l0) / long_px
                # TWO-SIDED, AND ON A NAMED DATUM (#46).
                #
                # This is the BADGE-CENTRE span -- l0/l1 are hub centres -- which
                # is about 81% of the tooth envelope that index.html's fitStage
                # actually divides LINK_SHARE by. Three different measures of
                # "linked span" were in play, 15 points apart: the envelope
                # (0.780 when LINK_SHARE binds), badge edges (0.673), and badge
                # centres (0.632). A threshold is meaningless without saying
                # which, so: these bounds are on CENTRES, and any harness copying
                # them must use centres too.
                #
                # The old ceiling of 0.88 could never fail. On this datum 0.88
                # corresponds to LINK_SHARE ~ 1.086, which the page cannot
                # produce while LINK_SHARE is 0.78. That is the other half of why
                # #44 passed 20 profiles: no floor, and a ceiling outside the
                # reachable range. A bound that cannot be crossed is not a bound.
                #
                # Now bracketed around the reachable 0.632: a floor at 0.45
                # catches the train collapsing (it read 0.30-0.33 on the
                # ultrawides while #44 was live), a ceiling at 0.80 catches it
                # running off the edges, and both sit inside what the page can
                # actually reach.
                #
                # THE FLOOR IS NOW A DISJUNCTION, because the page stopped making
                # the promise the bare floor was measuring (GitHub #75, CHANGELOG
                # #85). A gear is drawn at TARGET_GEAR_PX and shrinks below that
                # only when an axis cannot afford it, so past that size the linked
                # run IS a fixed number of pixels and its share of a growing long
                # axis falls as 1/W by design -- 62% here on every profile up to a
                # laptop, and about 35% on the 2560px ones. A bare 0.45 fails four
                # rows of this list against a page doing exactly what Charles
                # asked for.
                #
                # This is NOT the floor being loosened to go green, which is what
                # the note in webkit_fit.js warns against. The bound is moved onto
                # the property that replaced it: EITHER the linked run still takes
                # its share, OR the wheels have reached their standard size and
                # the escape runs are covering the rest. A train that collapses
                # for any other reason -- a fit that goes wrong, a solve that
                # shrinks, the 0.28 floor engaging -- still gives small wheels AND
                # a small share, and still fails here.
                #
                # And it gained the half it never had: a CEILING on gear size.
                # That is the bound GitHub #75 needed and no harness carried --
                # run against the outgoing rule it fails these same four rows at
                # 390-418px against a 222px standard. TARGET_GEAR_PX is read out
                # of index.html rather than copied, for the same reason
                # tools/test.js reads its constants there.
                LINK_FLOOR, LINK_CEIL = 0.45, 0.80
                gear = m.get("gear", 0)
                # THE TOLERANCE IS ONE TOOTH, AND IT IS DERIVED, because the two
                # sides of this comparison are not the same quantity.
                #
                # `gear` is the LARGEST wheel the deal produced. TARGET_GEAR_PX is
                # the size the fit aims that wheel at. The deal does not always
                # reach TEETH_MAX: with the counts drawn per wheel and constrained
                # only by each chain's total, the biggest wheel on stage is usually
                # the full TEETH_MAX and sometimes one tooth under it. A wheel's
                # outside diameter is m(z + 2), so one tooth short of the maximum
                # is a wheel 1/(TEETH_MAX + 2) smaller -- about 4.8% here -- and
                # the old flat 0.98 sat inside that. It failed rows where the page
                # had done nothing wrong, and which of them failed depended on the
                # deal. CI caught this the honest way: two rows at 215.4px against
                # a 222px standard that pass ten times running locally.
                #
                # Deriving the slack from the tooth pitch says exactly what is
                # being allowed -- one tooth of deal variance and not a pixel more
                # -- instead of naming a percentage that has to be re-measured
                # whenever the deal's range moves. It is still nowhere near a
                # collapse: #44 read 0.30-0.33 of the long axis with wheels far
                # smaller than one tooth off standard.
                one_tooth = 1.0 / (TEETH_MAX + 2)
                at_standard = gear >= TARGET_GEAR_PX * (1 - one_tooth)
                links_in = ((l0 >= -1) and (l1 <= long_px + 1)
                            and (LINK_FLOOR <= link_share or at_standard)
                            and link_share <= LINK_CEIL)
                gear_ok = 0 < gear <= TARGET_GEAR_PX * 1.02
                ok = ((train_long == want) and reaches and centre_off <= 0.06
                      and links_in and gear_ok and not m["overflowX"])
                if not ok:
                    bad += 1
                why = []
                if train_long != want:
                    why.append("runs across the SHORT side")
                if not reaches:
                    why.append(f"stops {max(0, a0):.0f}px short / {max(0, long_px - a1):.0f}px short")
                if centre_off > 0.06:
                    why.append(f"links off-centre by {centre_off:.0%}")
                if not gear_ok:
                    why.append(f"gear renders {gear:.0f}px against the "
                               f"{TARGET_GEAR_PX}px standard size — sizing is tracking "
                               f"the viewport again (GitHub #75)")
                if not links_in:
                    if link_share < LINK_FLOOR and not at_standard:
                        why.append(f"links span only {link_share:.0%}, under the "
                                   f"{LINK_FLOOR:.0%} floor, with the gear at only "
                                   f"{gear:.0f}px of its {TARGET_GEAR_PX}px standard — "
                                   f"the train has collapsed (#44)")
                    elif link_share > LINK_CEIL:
                        why.append(f"links span {link_share:.0%}, over the "
                                   f"{LINK_CEIL:.0%} ceiling — they will run off the edge")
                    else:
                        why.append("links run off the edge")
                if m["overflowX"]:
                    why.append("scrolls sideways")
                print(f"{label:22} {orient:10} {str(w) + 'x' + str(h):11} "
                      f"{covered * 100:5.0f}%   {link_share * 100:4.0f}%  "
                      f"{gear:5.0f}px  {'ok' if ok else 'FAIL: ' + ', '.join(why)}")

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
            # PIN SPEED OFF 1x AND OPEN THE MENU (GitHub #108, CL#114) before
            # measuring. The corner departure indicator is display:none at 1x
            # -- the shipped default -- so measuring at that default would
            # never see it; and the slider is inside the pop-out panel, also
            # display:none until opened. Both are new fixed controls this
            # pass exists to check, so both have to actually be on screen.
            await send("Runtime.evaluate", {"expression":
                "(()=>{try{localStorage.setItem('wozi-speed','5')}catch(e){}"
                "location.reload();})()"})
            await asyncio.sleep(2.3)
            await send("Runtime.evaluate", {"expression":
                "(()=>{const b=document.querySelector('[aria-expanded]'); if(b) b.click();})()"})
            await asyncio.sleep(0.3)
            res = await send("Runtime.evaluate", {
                "expression": SAFE_MEASURE % {"t": t, "r": r_, "b": b, "l": l},
                "returnByValue": True})
            m = json.loads(res["result"]["value"])
            why = []
            # Every fixed control inside the safe rectangle, and still tappable.
            # Half a pixel of slack: fractional layout, not a real overlap.
            # Zero-size entries are skipped rather than measured: a control
            # display:none has no box at all (getBoundingClientRect reports
            # 0,0,0,0 regardless of its CSS position), which would otherwise
            # read as "out of bounds by exactly the inset" -- a false failure
            # from measuring nothing, not a real one from measuring a control.
            worst = 1e9
            for c in m["ctrls"]:
                if c["w"] <= 0 or c["h"] <= 0:
                    continue
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
