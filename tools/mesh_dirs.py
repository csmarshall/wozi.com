#!/usr/bin/env python3
"""Verify that every meshing pair of wheels on the wozi.com gear train turns
opposite ways.

The "One clock" invariant (CLAUDE.md) says every wheel transform derives from
the same master angle -- and for a direct-mesh train that means adjacent
teeth must turn opposite directions, or the mesh would grind. A wrong
direction still animates smoothly (nothing visibly "jams"), so nothing else
in this repo catches it. This drives headless Chrome over CDP, samples the
live DOM twice ~700ms apart, finds meshing pairs by centre distance, and
checks that each pair's rotation deltas have opposite sign.

Plumbing (Chrome launch, free-port CDP_PORT handling, websocket RPC) is
copied verbatim from tools/verify_motion.py -- see #42: fourteen harnesses
once hardcoded one DevTools port, and two running at once dropped the socket
in a way that read as a page fault, not a harness fault.
"""

import asyncio
import json
import math
import os as _os
import re
import subprocess
import sys
import time
import urllib.request

import websockets

import shutil as _sh, sys as _sys
def _sys_platform_is_darwin():
    return _sys.platform == "darwin"
# CI runs on Linux, where Chrome is not in /Applications. Honour $CHROME,
# then fall back to whatever is on PATH, then to the macOS bundle.
CHROME = (_os.environ.get("CHROME")
          or _sh.which("google-chrome") or _sh.which("chromium-browser")
          or _sh.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
import sys as _s
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if _sys_platform_is_darwin() else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
URL = _s.argv[1] if len(_s.argv) > 1 else "http://127.0.0.1:8765/"
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

# ---- geometry constants, read OUT OF index.html, never re-typed -----------
#
# A harness that keeps its own copy of a page constant passes happily while
# the page drifts underneath it -- the exact failure tools/test.js's docstring
# warns about, and the reason this file does not carry a literal 7, 1 or 6 of
# its own.
_HTML_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "index.html")
with open(_HTML_PATH, "r", encoding="utf-8") as _f:
    _HTML_SRC = _f.read()

# Block comments stripped once, up front -- same idiom tools/test.js's
# grabNumber() uses (GitHub #101, CL#112). Without it a name merely discussed
# in prose, or sitting in a retired branch commented out rather than deleted,
# reads exactly like a live declaration.
_STRIPPED_HTML_SRC = re.sub(r"/\*[\s\S]*?\*/", "", _HTML_SRC)


def _grab_number(name):
    """Same idiom as tools/test.js's grabNumber(): find the ONE live
    `NAME = <number>` in index.html and read the number back out, rather than
    retyping it here.

    CONTRACT (GitHub #101, CL#112): fatal if NAME is assigned more than once
    in the comment-stripped source -- even if only one of those assignments'
    right-hand side is a plain number literal. That clause matters:
    index.html declares CELL_MIN twice, a retired literal and a live
    `px(...)` expression, and the old "first numeric match wins" idiom saw
    only the retired literal (px(...) never matched the number pattern at
    all) and returned it with no error. Counting plain-number matches alone
    would still miss that -- there was exactly one. Counting ASSIGNMENTS,
    literal or not, is what catches it."""
    assignments = re.findall(r"\b" + re.escape(name) + r"\s*=(?!=)", _STRIPPED_HTML_SRC)
    if len(assignments) > 1:
        print(f"FATAL: constant {name} is assigned {len(assignments)} times in index.html -- "
              f"_grab_number() cannot tell which one ships (the CELL_MIN trap, GitHub #101)")
        sys.exit(2)
    m = re.search(r"\b" + re.escape(name) + r"\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)", _STRIPPED_HTML_SRC)
    if not m:
        print(f"FATAL: constant not found in index.html: {name}")
        sys.exit(2)
    return float(m.group(1))


MODULE = _grab_number("MODULE")
TOOTH_ADD = _grab_number("TOOTH_ADD")

# TWO RENDERERS DRAW A SOLVED WHEEL, and they pad their <svg> by different
# amounts. gearSvg(g, S) draws the linked wheels and sizes its svg
# `(g.ro + 6) * 2`; ghostSvg(g, S) draws the bridge idlers -- and the escape
# runs -- and sizes its own `(g.ro + 4) * 2`. In both, g.ro is already the OUTER
# radius (pitch radius + addendum) in solve units, so the svg's width overstates
# the pitch radius that meshing distance is measured against by addendum plus
# that renderer's padding.
#
# Correcting both matters, not just gearSvg's: a bridge idler is a real,
# structural, MESHING wheel -- it is what carries the drive from one chain into
# the next -- so a harness that could not measure one would report PASS on a
# stage whose second chain was not driven at all, which is precisely the failure
# this file exists to catch.
#
# The "6" and the "4" are literals in index.html, not named constants, so they
# cannot be grabbed with _grab_number(). Each is pulled out of the exact source
# line that defines it instead of retyped -- the same rule #59 exists for a whole
# file, applied to two padding literals. If either line moves or changes shape,
# this harness fails loudly rather than silently drifting back to the bug it was
# written to catch.
def _pad_literal(rx, who):
    m = re.search(rx, _HTML_SRC)
    if not m:
        print(f"FATAL: {who}'s svg-sizing line not found in index.html -- "
              "the padding this harness corrects for may have moved or been renamed")
        sys.exit(2)
    return float(m.group(1))


PAD_LITERAL = _pad_literal(
    r"size\s*=\s*\(g\.ro\s*\+\s*(-?[0-9]+(?:\.[0-9]+)?)\)\s*\*\s*2,\s*r\s*=\s*g\.r\s*,\s*m\s*=\s*MODULE",
    "gearSvg()")
GHOST_PAD_LITERAL = _pad_literal(
    r"size\s*=\s*\(g\.ro\s*\+\s*(-?[0-9]+(?:\.[0-9]+)?)\)\s*\*\s*2,\s*r\s*=\s*g\.r\s*;",
    "ghostSvg()")

# The full outer-radius overstatement, in SOLVE units (unscaled by the page's
# fit factor): addendum beyond the pitch circle, plus the drawn padding. One per
# renderer; the sample below says which drew each wheel.
RADIUS_PAD_SOLVE = MODULE * TOOTH_ADD + PAD_LITERAL
GHOST_RADIUS_PAD_SOLVE = MODULE * TOOTH_ADD + GHOST_PAD_LITERAL


# WHICH WHEELS ARE ON THE STAGE, structurally rather than by appearance. Every
# wheel solve() places -- linked or idler -- is rendered as an anchor <div>
# directly inside the one `aria-hidden="true"` container renderVals() builds for
# the artwork. The escape runs are NOT: they live one level deeper, inside the
# ghost layer that container holds, so their anchor's parent is that layer and
# not the container. Testing the anchor's parent therefore separates "solved with
# the train" from "dealt afterwards by fitEscapes", which is the distinction that
# matters here -- and it does not confuse a bridge idler with an escape wheel
# merely because both are drawn in the background palette.
#
# `defs` then says which RENDERER drew it: gearSvg opens with a <defs>, ghostSvg
# does not. That picks the padding to subtract, nothing more.
#
# POSITION and ROTATION live on two different ancestors, not one combined
# wrapper: solve()'s render (index.html ~3600) emits an outer anchor <div>
# whose inline left/top IS the wheel's true centre (width:0; height:0 --
# there is no +w/2 to add), wrapping an inner <div> that carries only
# `transform: rotate(...)`, wrapping the <svg>. Centre comes from that outer
# anchor's inline style -- POSITION, never getBoundingClientRect(), which on
# a rotating element returns the axis-aligned box of a spinning square and is
# up to sqrt(2) too large, varying with phase. This exact mistake was made
# twice in this project this week and inflated measurements by up to 41%.
#
# `rOuter` is the drawn (padded) radius -- svg width/2, exactly what gearSvg
# put there. It is NOT the meshing radius; RADIUS_PAD_SOLVE * S is subtracted
# from it below, in Python, once per wheel, to recover the pitch radius two
# meshing wheels' centres actually sit at the sum of.
#
# `S` is the one number every rendered coordinate in the stage is multiplied
# by (index.html's gsRender()). It is not attached to `window` -- it lives in
# a lexical const inside the page's own script and Runtime.evaluate cannot see
# it -- so it is recovered the same way gsRender()'s own boot fallback reads
# it: off the `--gsfit` custom property, floored to the same two decimals
# fitStage() quantises the real render scale to (index.html ~1957).
SAMPLE_JS = r"""
(() => {
  const out = [];
  document.querySelectorAll('svg').forEach((s) => {
    const spin = s.parentElement;       // carries transform: rotate(...)
    const anchor = spin && spin.parentElement;  // carries left/top == wheel centre
    const stage = anchor && anchor.parentElement;
    if (!stage || stage.getAttribute('aria-hidden') !== 'true') return;
    const k = s.firstElementChild;
    const st = anchor.getAttribute('style') || '';
    const m = st.match(/left:\s*([-0-9.]+)px;\s*top:\s*([-0-9.]+)px/);
    const w = parseFloat(s.getAttribute('width'));
    const tr = getComputedStyle(spin).transform;
    const mm = tr.match(/matrix\(([-0-9.e]+),\s*([-0-9.e]+)/);
    if (!m || !mm) return;
    out.push({
      cx: parseFloat(m[1]), cy: parseFloat(m[2]), rOuter: w / 2,
      ghost: !(k && k.tagName.toLowerCase() === 'defs'),
      rot: Math.atan2(+mm[2], +mm[1]) * 180 / Math.PI
    });
  });
  const raw = parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue('--gsfit'));
  const S = Math.floor((raw || 0) * 100) / 100;
  return JSON.stringify({ wheels: out, S: S });
})()
"""


def _pad_of(wheel):
    """The outer-radius overstatement for whichever renderer drew this wheel."""
    return GHOST_RADIUS_PAD_SOLVE if wheel["ghost"] else RADIUS_PAD_SOLVE


def delta(a, b):
    d = b - a
    while d > 180:
        d -= 360
    while d < -180:
        d += 360
    return d


async def cdp():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--window-size=1440,900",
         "--no-first-run", *CI_FLAGS, "--no-default-browser-check",
         "--disable-features=Translate", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{URL}",
                                        timeout=1) as r:
                ws_url = json.load(r)["webSocketDebuggerUrl"]
                break
        except Exception:
            try:  # older Chrome requires PUT on /json/new
                req = urllib.request.Request(
                    f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
                with urllib.request.urlopen(req, timeout=1) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.2)
    if not ws_url:
        proc.kill()
        print("FATAL: could not reach Chrome DevTools endpoint")
        return 2

    errors = []
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
                if msg.get("method") == "Runtime.exceptionThrown":
                    d = msg["params"]["exceptionDetails"]
                    errors.append("exception: " + (d.get("text") or "") + " " +
                                  str(d.get("exception", {}).get("description", ""))[:200])
                elif msg.get("method") == "Runtime.consoleAPICalled":
                    if msg["params"]["type"] in ("error", "assert"):
                        args = [str(a.get("value", a.get("description", "")))
                                for a in msg["params"]["args"]]
                        errors.append("console.error: " + " ".join(args)[:200])
                elif msg.get("method") == "Log.entryAdded":
                    e = msg["params"]["entry"]
                    if e.get("level") == "error":
                        errors.append(f"log: {e.get('text','')[:200]} {e.get('url','')}")
                if msg.get("id") == my:
                    return msg.get("result", {})

        async def evaluate(expr):
            r = await send("Runtime.evaluate",
                           {"expression": expr, "returnByValue": True,
                            "awaitPromise": True})
            return r.get("result", {}).get("value")

        await send("Runtime.enable")
        await send("Log.enable")
        await send("Page.enable")
        await send("Page.navigate", {"url": URL})
        await asyncio.sleep(3.5)  # load + spin-up layer settling

        r1 = json.loads(await evaluate(SAMPLE_JS))
        await asyncio.sleep(0.7)
        r2 = json.loads(await evaluate(SAMPLE_JS))

    proc.kill()

    s1, s2 = r1["wheels"], r2["wheels"]
    S = r1["S"]

    print(f"wheels sampled     : {len(s1)}  "
          f"({sum(1 for w in s1 if not w['ghost'])} linked, "
          f"{sum(1 for w in s1 if w['ghost'])} idler)")
    print(f"fit scale (S)      : {S:.2f}  (from --gsfit, floored to gsRender()'s own quantisation)")
    print(f"radius pad (solve) : {RADIUS_PAD_SOLVE:.4f} linked / "
          f"{GHOST_RADIUS_PAD_SOLVE:.4f} idler  "
          f"(MODULE*TOOTH_ADD={MODULE * TOOTH_ADD:.4f} + literal {PAD_LITERAL:.4f} / "
          f"{GHOST_PAD_LITERAL:.4f}, from each renderer's own sizing line)")

    if S <= 0:
        print("\nRESULT: FAIL (--gsfit unreadable -- cannot recover pitch radius)")
        return 1

    # Two wheels MESH when their centres sit at the sum of their PITCH radii,
    # not the sum of the padded/addendum radii the svg width actually reports.
    # Recover the pitch radius once per wheel by subtracting the known,
    # page-derived overstatement, then compare against the sum directly.
    #
    # TOLERANCE: for a direct-mesh pair, solve() (index.html ~2098) places the
    # child at EXACTLY `(prev.r + r) * S` from its parent -- clearance nudging
    # only moves the bearing angle, never this distance -- so once rOuter is
    # corrected back to pitch radius, a genuinely meshing pair's residual
    # should be float noise, not geometry: repeated loads measured it within
    # +-0.003px of 0.
    #
    # But S itself is recovered lossily. index.html writes `--gsfit` as
    # `fit.toFixed(3)` -- a STRING rounded to 3 decimals -- and this harness
    # re-floors that string to gsRender()'s own 2-decimal quantisation. toFixed
    # can move the parsed value by up to 0.0005 either side of the true `fit`,
    # and because floor() is a step function, an offset that size can flip
    # which 0.01 step it lands on whenever the true value sits near a
    # boundary -- an error of exactly one quantisation step (0.01) in S,
    # worst case, no more (0.0005 * 100 = 0.05 < 1 step). That step multiplies
    # RADIUS_PAD_SOLVE (13 solve units) on BOTH wheels of a pair, so the worst
    # case is 2 * 13 * 0.01 = 0.26px -- which is exactly what run 3 of 5 during
    # development hit (S misread as 1.50 vs the true 1.49, diff +0.2584px on a
    # genuinely meshing pair, zero pairs found, correctly reported FAIL rather
    # than silently passing on the other 5 pairs).
    #
    # 0.35px clears that analytic worst case with margin, is nowhere near
    # separated real geometry (the closest non-meshing pair sampled was
    # 106-124px away across a dozen loads -- see task-4-report.md), and is
    # still ~130-1000x tighter than the 18-24% fractional tolerance it
    # replaces, which on this train's radii was worth 30-50px.
    TOL_PX = 0.35
    pairs = []
    for i in range(len(s1)):
        for j in range(i + 1, len(s1)):
            a, b = s1[i], s1[j]
            ra = a["rOuter"] - _pad_of(a) * S
            rb = b["rOuter"] - _pad_of(b) * S
            d = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
            rs = ra + rb
            diff = d - rs
            if abs(diff) < TOL_PX:
                pairs.append((i, j, d, rs, diff))

    print(f"meshing pairs found: {len(pairs)}  (tolerance {TOL_PX}px)")
    for i, j, d, rs, diff in pairs:
        print(f"  wheels {i},{j}: centre-dist={d:.4f}px  pitch-radius-sum={rs:.4f}px  "
              f"diff={diff:+.4f}px")

    # Print the residuals for every OTHER pair too, so the next person can
    # judge TOL_PX against real numbers rather than trust it. The closest
    # non-meshing pair is the tolerance's actual margin of safety.
    non_pairs = []
    for i in range(len(s1)):
        for j in range(i + 1, len(s1)):
            if any(i == pi and j == pj for pi, pj, *_ in pairs):
                continue
            a, b = s1[i], s1[j]
            ra = a["rOuter"] - _pad_of(a) * S
            rb = b["rOuter"] - _pad_of(b) * S
            d = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
            rs = ra + rb
            non_pairs.append((i, j, d - rs))
    if non_pairs:
        closest = min(non_pairs, key=lambda t: abs(t[2]))
        print(f"closest non-mesh   : wheels {closest[0]},{closest[1]}  "
              f"diff={closest[2]:+.4f}px  (tolerance's actual margin: "
              f"{abs(closest[2]) - TOL_PX:.4f}px clear)")

    bad = []
    for i, j, d, rs, diff in pairs:
        di, dj = delta(s1[i]["rot"], s2[i]["rot"]), delta(s1[j]["rot"], s2[j]["rot"])
        if abs(di) < 1e-6 or abs(dj) < 1e-6:
            bad.append(f"wheels {i},{j} mesh but one is not turning ({di:+.4f}, {dj:+.4f})")
        elif (di > 0) == (dj > 0):
            bad.append(f"wheels {i},{j} mesh but both turn the same way ({di:+.2f}, {dj:+.2f})")

    print(f"console errors     : {len(errors)}")
    for e in errors[:10]:
        print("  " + e)

    # A detector that finds zero meshes and reports success is worse than no
    # detector -- it would silently stop testing anything the moment the page
    # geometry changed underneath it.
    if not pairs:
        print("\nRESULT: FAIL (no meshing pairs found -- detector cannot be trusted)")
        return 1

    if bad:
        print("\nbad pairs:")
        for b in bad:
            print("  " + b)
        print("\nRESULT: FAIL")
        return 1

    print("\nRESULT: PASS")
    return 0


sys.exit(asyncio.run(cdp()))
