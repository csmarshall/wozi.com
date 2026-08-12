#!/usr/bin/env python3
"""Four structural assertions about the RENDERED page, made with no image at all.

    tools/dom_invariants.py http://127.0.0.1:PORT/
    tools/dom_invariants.py http://127.0.0.1:PORT/ --query '?who=charles'
    tools/dom_invariants.py http://127.0.0.1:PORT/ --census   # print the numbers

WHY A FIFTH HARNESS. `npm test` proves the gear MATHS meshes -- it reads the
constants out of index.html and assembles every set the deal can produce, in
Node, with no browser. The pixel gate proves the page draws the same PICTURE as
a git ref. Between the two there is a gap the width of the renderer: nothing
asserted that what `solve()` computed is what the DOM actually contains. A
wheel could render with the wrong tooth count, an empty <svg>, a missing
engraving or a fill that had gone black, and the maths suite would pass because
the maths never changed, while the pixel gate would either pass (single-chain
scope untouched) or fail with a number that says only "801,797 pixels moved".

So this harness asserts STRUCTURE, and it does it with one CDP evaluate against
the served page:

  1. MESH AT RENDER TIME -- every wheel on the stage has at least one partner
     whose centre distance equals the sum of the two pitch radii. Measured off
     the rendered DOM, not off solve()'s output.
  2. NO WHEEL RENDERS EMPTY -- every wheel draws a toothed blank whose tooth
     count is exactly the one its own rendered radius implies, plus the discs
     its renderer emits unconditionally; every hub badge holds a drawn icon.
  3. ENGRAVING PRESENT -- every linked wheel carries a non-empty handle on a
     textPath that resolves, with a non-zero computed text length.
  4. INK CENSUS -- every literal colour on a wheel is a TONE OF THAT WHEEL'S OWN
     COLOUR: same hue, saturation not thrown away, value inside the band the
     tone functions can produce. A fill that went black is not a tone of
     anything.

There are no images, no baselines and no platform-dependent rasterisation
anywhere in here, so it runs identically on this laptop and on CI's Linux.

SEEDED, BECAUSE AN UNSEEDED VERDICT IS A PROPERTY OF THE MACHINE YOU GOT. The
whole train is dealt at random per load; #88 is the entry about a gate that
navigated once and judged what it happened to get, then failed in CI on rows
that had passed ten times locally. The deal is pinned by injecting an LCG over
Math.random through Page.addScriptToEvaluateOnNewDocument, which beats every
page script -- the same mechanism tools/devices.py and tools/pixel_regress.py
use, and for the same reason. `Page.enable` must be called BEFORE the
injection: without it the injection is accepted and silently never runs.
Determinism lives in the harness and never in index.html -- the shipped page
carries no test hooks.

THE WEBFONT IS PINNED TOO, AND THIS HARNESS IS THE LEAST EXPOSED OF THE FOUR --
WHICH IS WHY IT IS WORTH SAYING WHAT PINNING BUYS HERE (GitHub #140). The page's
drawing depends on WHEN Manrope arrives relative to its own first render
(index.html clears its textWidth memo on document.fonts.ready, #98), and that
time comes off a third party's network. Measured on this machine, same seed, with
the font reachable and then with both font hosts blackholed:

    mesh residual        0.0008px of 0.35px  -- IDENTICAL
    tooth census         exact to 0.0000     -- IDENTICAL
    ink census           56 inks, same bounds -- IDENTICAL
    shortest engraving   21.7px  ->  23.5px  -- MOVED, by 8%

So none of the four ASSERTIONS is font-sensitive: check 3 asserts a computed text
length greater than zero, and every face clears that. What moved is a REPORTED
number, and that is still worth pinning rather than shrugging at -- a human
diffing two runs of this tool on the same seed would see the engraving line
change with nothing in the tree changed, and would have no way to tell that from
a real regression. The state is asserted after the measurement (a width probe;
document.fonts cannot answer it -- see tools/fontpin.py), so the number printed
below is now a number about the page.

Exit 0 if every check passes, 1 if any fails, 2 if it could not measure at all --
including a run whose typography was not the one it chose.
"""

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fontpin

# CI runs on Linux, where Chrome is not in /Applications. Honour $CHROME, then
# fall back to whatever is on PATH, then to the macOS bundle.
CHROME = (os.environ.get("CHROME")
          or shutil.which("google-chrome") or shutil.which("chromium-browser")
          or shutil.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if sys.platform == "darwin" else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    """THE PORT IS NOT FIXED (#42). Fourteen harnesses once shared one hardcoded
    DevTools port; two running at once dropped the socket in a way that reads as
    a page fault rather than a harness fault. Honour CDP_PORT if a caller wants
    a specific one, otherwise take whatever the OS gives us."""
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ---- constants, read OUT OF index.html, never re-typed ---------------------
#
# A harness holding its own copy of a page constant agrees with itself forever
# while the page moves underneath it -- the failure tools/test.js's header warns
# about, and the reason nothing below is a literal 7, 1.00 or '#243033'.
with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as _f:
    _HTML = _f.read()

# Block comments stripped once, up front -- same idiom tools/test.js's
# grabNumber() and tools/mesh_dirs.py's _grab_number() already use (GitHub
# #101, CL#112). Without it a name merely DISCUSSED in prose, or sitting in a
# retired branch commented out rather than deleted, reads exactly like a live
# declaration -- MODULE and BAND_DEPTH each have a second textual match
# inside a comment quoting their own declaration in prose.
_STRIPPED_HTML = re.sub(r"/\*[\s\S]*?\*/", "", _HTML)


def _grab_number(name):
    """CONTRACT (GitHub #101 / #114, CL#112): returns the value of the ONE
    live `NAME = <number>` assignment in index.html. Fatal if NAME is
    assigned more than once in the comment-stripped source -- even if only
    one of those assignments' right-hand side is a plain number literal.

    That clause is the load-bearing half, not the comment-stripping: it is
    exactly the shape of the CELL_MIN trap this closes. Counting only plain
    numeric matches would still miss a case where one declaration is a
    literal and the other is not -- there both used to look like exactly one
    match. Counting ASSIGNMENTS to the name, literal or not, is what actually
    disambiguates it; see tools/test.js's grabNumber() docstring for the full
    account and tools/mesh_dirs.py's _grab_number() for the identical Python
    copy this one is a third of."""
    assignments = re.findall(r"\b" + re.escape(name) + r"\s*=(?!=)", _STRIPPED_HTML)
    if len(assignments) > 1:
        sys.exit(f"FATAL: constant {name} is assigned {len(assignments)} times in "
                 "index.html -- _grab_number() cannot tell which one ships (the "
                 "CELL_MIN trap, GitHub #101)")
    m = re.search(r"\b" + re.escape(name) + r"\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)", _STRIPPED_HTML)
    if not m:
        sys.exit(f"FATAL: constant not found in index.html: {name}")
    return float(m.group(1))


def _grab_string(name):
    """Same contract as _grab_number() above, for a quoted string constant --
    arguably the more important half, since a string has no shape to fail
    on: any first match looks like a valid answer, so an ambiguity check is
    the only thing standing between this and a plausible wrong colour."""
    assignments = re.findall(r"\b" + re.escape(name) + r"\s*=(?!=)", _STRIPPED_HTML)
    if len(assignments) > 1:
        sys.exit(f"FATAL: constant {name} is assigned {len(assignments)} times in "
                 "index.html -- _grab_string() cannot tell which one ships (the "
                 "CELL_MIN trap, GitHub #101)")
    m = re.search(r"\b" + re.escape(name) + r"\s*=\s*'([^']*)'", _STRIPPED_HTML)
    if not m:
        sys.exit(f"FATAL: constant not found in index.html: {name}")
    return m.group(1)


MODULE = _grab_number("MODULE")
TOOTH_ADD = _grab_number("TOOTH_ADD")
# The engraving's ink. It is the one colour on a wheel that is NOT derived from
# that wheel's own colour -- a fixed ink, struck into every band alike -- so the
# tone test below has to know it in order to exempt it, and it is read here
# rather than retyped for the same reason as the two numbers above.
FLAT_INK = _grab_string("FLAT_INK").lower()

# TWO RENDERERS DRAW A SOLVED WHEEL and they pad their <svg> differently:
# gearSvg(g, S) sizes its box `(g.ro + 6) * 2`, ghostSvg(g, S) `(g.ro + 4) * 2`,
# and in both g.ro is already the OUTER radius (pitch + addendum). So the svg's
# own width overstates the pitch radius -- the radius mesh is measured against --
# by addendum plus that renderer's padding.
#
# Both have to be corrected, not just gearSvg's: a bridge idler is drawn by
# ghostSvg and is a real, structural, meshing wheel -- it is what carries the
# drive from one chain into the next -- so a harness that could not measure one
# would report PASS on a stage whose second chain was not driven at all.
#
# The 6 and the 4 are literals in index.html rather than named constants, so
# they are pulled out of the exact source line that defines each. Same idiom,
# same reasoning and the same regexes as tools/mesh_dirs.py: if either line
# moves or changes shape this fails loudly instead of drifting back to the bug.
def _pad_literal(rx, who):
    m = re.search(rx, _HTML)
    if not m:
        sys.exit(f"FATAL: {who}'s svg-sizing line not found in index.html -- the "
                 "padding this harness corrects for may have moved or been renamed")
    return float(m.group(1))


PAD_LINKED = MODULE * TOOTH_ADD + _pad_literal(
    r"size\s*=\s*\(g\.ro\s*\+\s*(-?[0-9]+(?:\.[0-9]+)?)\)\s*\*\s*2,\s*r\s*=\s*g\.r\s*,\s*m\s*=\s*MODULE",
    "gearSvg()")
PAD_GHOST = MODULE * TOOTH_ADD + _pad_literal(
    r"size\s*=\s*\(g\.ro\s*\+\s*(-?[0-9]+(?:\.[0-9]+)?)\)\s*\*\s*2,\s*r\s*=\s*g\.r\s*;",
    "ghostSvg()")

# ---- tolerances, and where each came from ---------------------------------
#
# MESH. solve() places a direct-mesh child at EXACTLY `(prev.r + r) * S` from
# its parent -- clearance nudging moves the bearing angle, never this distance --
# so once the svg width is corrected back to a pitch radius the residual on a
# genuinely meshing pair is float noise. Measured over 30 runs (5 seeds x 2
# themes x 2 scopes, then 5 viewports from 375x667 to 5120x1440) the worst
# residual on a meshing pair was 0.0045px.
#
# The tolerance is not set by that, though: S is recovered LOSSILY. index.html
# writes `--gsfit` as `fit.toFixed(3)` and this harness re-floors that string to
# gsRender()'s own 2-decimal quantisation, exactly as the page's boot fallback
# does. toFixed can move the parsed value by up to 0.0005, and because floor()
# is a step function that is enough to land on the neighbouring 0.01 step when
# the true value sits near a boundary. One step of S multiplies the radius pad
# (13 solve units) on BOTH wheels of a pair: 2 * 13 * 0.01 = 0.26px worst case.
# 0.35px clears that analytically, and the closest NON-meshing pair over those
# same 30 runs was 47.5px away, on the smallest viewport in the list -- so the
# bound has ~135x margin on the side that would make it lie. It is the same
# number, reached the same way, as tools/mesh_dirs.py's; the brief for this work
# said "~0.5px", and the tighter figure is used because the repo has already
# paid for the analysis and the measured margin supports it.
TOL_MESH_PX = 0.35

# EMPTY. Both renderers' return statements emit, with no branch taken, one
# toothed blank path plus three concentric discs -- gearSvg the band ring, the
# hub and the centre dot; ghostSvg the face, the well and the boss. Anything
# else (webs, lattices, spokes, planet gears, engravings) is conditional on the
# wheel's kind, so four is the largest floor that holds for every wheel the deal
# can produce.
#
# THIS ONE IS NOT DERIVED and cannot honestly be made so: the renderers are
# nested `h()` calls a thousand lines long, not a table, and a regex that tried
# to count their unconditional emissions would be far more fragile than the
# number it replaced. What keeps it from drifting is that the check it backs up
# -- the tooth census below -- IS exact and derived, and that is where this
# check's teeth actually are. Measured: exactly 4 on an idler, 6 to 31 on a
# linked wheel depending on which web family the deal gave it.
MIN_DRAWN_SHAPES = 4

# INK. Every colour a wheel is painted with comes from flatTones(c) or
# shades(c), and both are pure functions of one base colour c that mix it toward
# black or toward white. Mixing toward black leaves HSV hue and saturation
# untouched and scales value; mixing toward white leaves hue untouched and
# reduces both saturation and value a little. So a tone of c has c's hue, most
# of c's saturation, and a value near c's -- and grey, black and white have
# none of those properties, which is exactly the failure this check exists for.
#
# Every bound below is stated against what the page's own tone factors produce,
# and the harness prints the observed extremes next to them so the next person
# can judge the margin rather than trust it:
#
#   toward black  mix(t, 0)   t in {0.13, 0.16, 0.30, 0.40}   sat x1.00  val x0.60-0.87
#   toward white  mix(0.07, 255)                              sat x0.89  val x1.05
#   ghost dim     x0.78 dark / x0.55 light, applied to c before the tones above
#
# so saturation never falls far below the base's and value stays near it. The
# bounds are set well wide of the extremes measured over the same 30 runs the
# mesh tolerance was checked against, and a fill that went black lands at sat
# 0.00 / val 0.00 -- nowhere near any of them.
HUE_TOL_DEG = 4.0         # observed worst, on a saturated base: 0.55 degrees
SAT_RATIO_MIN = 0.60      # observed minimum: 0.807
VAL_RATIO = (0.45, 1.40)  # observed range: 0.598 - 1.116
# HUE IS MEANINGLESS ON A NEAR-GREY, and the background wheels are deliberately
# near-grey -- an idler's base measures about 0.07 saturation. At that chroma one
# 8-bit rounding step moves the hue by whole degrees: the ghost tones measured up
# to 3.9 degrees off their own base while being exact mixes of it, against 0.55
# degrees on the saturated linked wheels. So the hue test only runs where the
# base has a hue to match; below this the saturation and value tests still do,
# and those are what the black-fill failure trips anyway.
HUE_BASE_SAT_MIN = 0.15
# A wheel painted in one flat colour has lost its tonal structure entirely, which
# no renderer here can produce: the blank, the face and the darker contour are
# three different mixes of the base in every path through both functions. Stated,
# not derived, for the same reason as MIN_DRAWN_SHAPES; measured 4 on a ghost and
# 5 on a linked wheel, FLAT_INK excluded from both.
MIN_DISTINCT_INKS = 3

# ---- the one evaluate ------------------------------------------------------
#
# WHICH ELEMENTS ARE WHEELS, structurally rather than by appearance. Every wheel
# solve() places -- linked or bridge idler -- is rendered as an anchor <div>
# directly inside the one `aria-hidden="true"` container renderVals() builds for
# the artwork. The escape runs are NOT: they live one level deeper, inside the
# ghost layer that container holds, so their anchor's parent is that layer. The
# parent test therefore separates "solved with the train" from "dealt afterwards
# by fitEscapes" -- which is the distinction that matters, since an escape run is
# decoration and is not required to mesh with anything.
#
# The `willChange: transform` test on the inner wrapper is what separates a wheel
# from a CONTAINER. The full-stage `chains` <svg> is `solved.w * S` across,
# paints nothing while no drive strand is enabled, and at 5120x1440 measures
# ~40px WIDER than the outermost wheel -- a measure an empty box can satisfy is
# not a measure.
#
# POSITION and ROTATION live on two different ancestors: the outer anchor's
# inline left/top IS the wheel's true centre (the div is width:0; height:0, so
# there is no +w/2 to add), and the inner div carries only the rotation. Centre
# is read off that inline style and radius off the <svg>'s width ATTRIBUTE --
# never getBoundingClientRect(), which on a rotating element returns the
# axis-aligned box of a spinning square, up to sqrt(2) too large and varying
# with phase. That mistake was made twice in one week in this repo and inflated
# measurements by up to 41%.
#
# `S`, the render scale, is a lexical const the page does not attach to window,
# so it is recovered off the `--gsfit` custom property exactly as gsRender()'s
# own boot fallback reads it.
SAMPLE_JS = r"""
(() => {
  /* An svg fill or stroke may be an indirection: url(#id) points at a gradient
     whose stops carry the real tones. Resolve it, because those stops ARE the
     face and well tones and the census would otherwise miss the wheel's
     brightest and darkest paint. */
  const literal = (v) => v && !/^(none|transparent|currentColor)$/i.test(v)
                      && !/^var\(/.test(v) && !/^url\(/.test(v);
  const stopsOf = (svg, v) => {
    const m = /^url\(["']?#([^)"']+)["']?\)/.exec(v || '');
    if (!m) return [];
    const g = svg.querySelector('[id="' + m[1] + '"]');
    if (!g) return [];
    return [...g.querySelectorAll('stop')]
      .map(s => s.getAttribute('stop-color')).filter(literal);
  };

  const wheels = [];
  document.querySelectorAll('svg').forEach((svg) => {
    const spin = svg.parentElement;                 /* transform: rotate(...) */
    if (!spin || getComputedStyle(spin).willChange !== 'transform') return;
    const anchor = spin.parentElement;              /* left/top == wheel centre */
    const stage = anchor && anchor.parentElement;
    if (!stage || stage.getAttribute('aria-hidden') !== 'true') return;
    const st = anchor.getAttribute('style') || '';
    const pos = st.match(/left:\s*([-0-9.]+)px;\s*top:\s*([-0-9.]+)px/);
    const w = parseFloat(svg.getAttribute('width'));
    if (!pos || !(w > 0)) return;

    /* gearSvg opens with a <defs>; ghostSvg does not. That says which renderer
       drew this wheel, which picks the padding to subtract and says whether an
       engraving is owed. */
    const linked = !!(svg.firstElementChild &&
                      svg.firstElementChild.tagName.toLowerCase() === 'defs');

    /* THE BLANK. The first <path> outside <defs> is the toothed body -- the
       identical path inside defs is the clip, and every other path is a web
       detail. teethPath() emits exactly two quadratic fillet blends per tooth,
       chipped or not, and no other 'Q' anywhere, so counting them counts teeth.
       Only the FIRST subpath is the blank: cut-outs are appended to the same
       `d` as further M-subpaths and must not be counted. */
    const drawnSel = 'path,circle,rect,ellipse,polygon,polyline,line';
    const drawn = [...svg.querySelectorAll(drawnSel)].filter(e => !e.closest('defs'));
    const body = drawn.filter(e => e.tagName.toLowerCase() === 'path')[0];
    const d = body ? (body.getAttribute('d') || '') : '';
    const cut = d.indexOf('M', 1);
    const blank = cut < 0 ? d : d.slice(0, cut);

    /* THE INK. Every literal colour this wheel is painted with, gradient stops
       resolved, indirections and keywords dropped. */
    const inks = {};
    const add = (v) => { if (literal(v)) inks[v.toLowerCase()] = (inks[v.toLowerCase()] || 0) + 1; };
    [...svg.querySelectorAll('*')].forEach((e) => {
      ['fill', 'stroke', 'stop-color'].forEach(a => add(e.getAttribute(a)));
    });
    /* The base every other tone is a mix of: the blank's own fill, through the
       gradient if that is what it points at. */
    const bodyFill = body ? body.getAttribute('fill') : null;
    const base = literal(bodyFill) ? bodyFill.toLowerCase()
               : (stopsOf(svg, bodyFill)[0] || '').toLowerCase();

    /* THE ENGRAVING. textContent says something was asked for; a resolvable
       textPath target and a non-zero computed length say it was DRAWN -- a
       dangling href renders nothing at all while leaving the text in the DOM. */
    const texts = [...svg.querySelectorAll('text')].map((t) => {
      const tp = t.querySelector('textPath');
      const href = tp && (tp.getAttribute('href') || tp.getAttribute('xlink:href'));
      const id = href && href.charAt(0) === '#' ? href.slice(1) : null;
      let len = -1;
      try { len = t.getComputedTextLength(); } catch (e) {}
      return { text: (t.textContent || '').trim(), len: len,
               target: !!(id && svg.querySelector('[id="' + id + '"]')) };
    });

    wheels.push({
      cx: parseFloat(pos[1]), cy: parseFloat(pos[2]), rOuter: w / 2, linked: linked,
      hasBlank: !!body, quads: (blank.match(/Q/g) || []).length,
      drawn: drawn.length, inks: inks, base: base, texts: texts
    });
  });

  /* THE HUB BADGES. Each is an <a> with an accessible name; loadIcons() fetches
     the icon and its .catch swallows a failure silently, so an empty badge is
     the page's quietest breakage -- it is what a file:// load produces, and what
     a wrong Content-Type on the .svg objects would produce on the live site. */
  const badges = [...document.querySelectorAll('a[href][aria-label]')]
    .filter(a => a.getBoundingClientRect().width > 10)
    .map(a => ({ label: a.getAttribute('aria-label'),
                 svgs: a.querySelectorAll('svg').length,
                 shapes: a.querySelectorAll('svg path,svg circle,svg rect,svg ellipse,svg polygon,svg polyline,svg line').length }));

  const raw = parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue('--gsfit'));
  return JSON.stringify({ wheels: wheels, badges: badges,
                          S: Math.floor((raw || 0) * 100) / 100 });
})()
"""

# The same LCG, seeded off the URL, that tools/devices.py and
# tools/pixel_regress.py inject. Reading the seed from the query rather than
# baking it in means the injection happens once and each navigation names its
# own.
SEED_JS = """
  (() => {
    const m = /[?&]seed=(\\d+)/.exec(location.search);
    if (!m) return;
    let s = +m[1] >>> 0;
    Math.random = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  })();
"""


def hsv(hex_str):
    """HSV, with hue in degrees and s/v in 0..1. Hue is undefined at zero
    chroma and reported as None there rather than as an arbitrary 0."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    mx, mn = max(r, g, b), min(r, g, b)
    c = mx - mn
    if c == 0:
        hue = None
    elif mx == r:
        hue = (60 * ((g - b) / c)) % 360
    elif mx == g:
        hue = 60 * ((b - r) / c) + 120
    else:
        hue = 60 * ((r - g) / c) + 240
    return hue, (0.0 if mx == 0 else c / mx), mx


def hue_gap(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


# The digest the settle below compares: how many wheels are on the stage, the fit
# scale every measurement is divided by, and where each hub badge sits. Badge
# centres are wheel centres, so they move when the solve moves and hold still
# while the train turns -- which is exactly the difference this needs to see. Kept
# to one string so the comparison is an equality and not a set of tolerances.
GEOMETRY_JS = (
    "(()=>{const n=document.querySelectorAll('svg').length;"
    "const f=getComputedStyle(document.documentElement).getPropertyValue('--gsfit');"
    "const b=[...document.querySelectorAll('a[href][aria-label]')].map(a=>{"
    "const r=a.getBoundingClientRect();"
    "return Math.round(r.left)+','+Math.round(r.top);}).join(' ');"
    "return n+'|'+f.trim()+'|'+b;})()")
# How long the stage may go on moving after the page reports itself loaded.
# Reaching it is a hard failure and not a fallback: this file asserts exact tooth
# counts and sub-pixel mesh residuals, and a half-solved stage fails them for a
# reason that has nothing to do with the code.
GEOMETRY_TIMEOUT_S = 15.0


async def settle_geometry(send, pump, timeout=GEOMETRY_TIMEOUT_S):
    """Wait until two consecutive reads of GEOMETRY_JS agree. Returns how long it
    took, in seconds, so the caller can report a page that was slow rather than
    only one that never arrived."""
    t0 = time.monotonic()
    prev = None
    while time.monotonic() - t0 < timeout:
        r = await send("Runtime.evaluate", {"expression": GEOMETRY_JS,
                                           "returnByValue": True})
        now = r.get("result", {}).get("value")
        if now and now == prev:
            return time.monotonic() - t0
        prev = now
        await pump(0.1)
    raise SystemExit(
        f"FATAL: the stage never stopped moving — two reads of its geometry still "
        f"disagree after {timeout}s. Nothing has been measured, so nothing has "
        f"been proved.")


async def sample(url, seed, viewport, theme, pin):
    """One navigation, one evaluate. Returns (payload, console errors).

    `pin` is the font state chosen once, before this function is called and before
    any browser exists -- see tools/fontpin.py. It is enforced on every request to
    a font host and verified by a width probe once the page has been measured.
    """
    port = int(os.environ.get("CDP_PORT") or 0) or free_port()
    profile = os.environ.get("CHROME_PROFILE") or tempfile.mkdtemp(prefix="wozi-dom-")
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
         *CI_FLAGS, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(60):
        for method in (None, "PUT"):
            try:
                target = f"http://127.0.0.1:{port}/json/new?about:blank"
                req = urllib.request.Request(target, method=method) if method else target
                ws_url = json.load(urllib.request.urlopen(req, timeout=1))["webSocketDebuggerUrl"]
                break
            except Exception:
                pass
        if ws_url:
            break
        time.sleep(0.2)
    if not ws_url:
        proc.kill()
        return None, ["could not reach Chrome DevTools endpoint"]

    errors = []
    try:
        async with websockets.connect(ws_url, max_size=10 ** 8) as ws:
            def watch(msg):
                """Console errors and exceptions, collected off every message
                rather than only the ones that happen to arrive while a reply is
                pending. This used to live inside `send`'s own recv loop; it is a
                callback now because fontpin.attach owns the socket, and it has to
                go on seeing everything -- the overlap and refused-bridge warnings
                this file reports are console output and nothing else can see
                them."""
                if msg.get("method") == "Runtime.exceptionThrown":
                    det = msg["params"]["exceptionDetails"]
                    errors.append("exception: " + str(det.get("text", ""))[:160])
                elif msg.get("method") == "Runtime.consoleAPICalled":
                    if msg["params"]["type"] in ("error", "assert"):
                        args = [str(a.get("value", a.get("description", "")))
                                for a in msg["params"]["args"]]
                        errors.append("console.error: " + " ".join(args)[:160])

            # send/pump/wait_until come from fontpin: a paused font request arrives
            # unsolicited and MUST be answered or the page hangs on its stylesheet,
            # and `pump` is what makes a wait answer them instead of sleeping
            # through them.
            send, pump, wait_until = fontpin.attach(ws, pin, on_message=watch)

            # Page.enable FIRST. Without it the injection below is accepted and
            # silently never runs, which reads exactly like a seed that does not
            # work -- two different deals and the same green verdict.
            await send("Page.enable")
            await send("Runtime.enable")
            await send("Page.addScriptToEvaluateOnNewDocument", {"source": SEED_JS})
            await send("Page.addScriptToEvaluateOnNewDocument",
                       {"source": "try{localStorage.setItem('wozi-theme','%s')}catch(e){}" % theme})
            await pin.install(send)
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": viewport[0], "height": viewport[1],
                        "deviceScaleFactor": 1, "mobile": False})
            sep = "&" if "?" in url else "?"
            await send("Page.navigate", {"url": f"{url}{sep}seed={seed}"})
            # A CONDITION, NOT THE OLD FIXED 4.0s. That sleep was three things at
            # once -- load, the font coming off the network, and the fit settling --
            # and only one of them is still a duration at all now the font is
            # served from memory. So: wait for load and fonts.ready, then wait for
            # the geometry to stop moving, and measure only then. On a settled page
            # this is far quicker than 4s; on a slow one it waits longer than 4s
            # instead of measuring a half-solved stage and asserting exact tooth
            # counts against it.
            await fontpin.wait_ready(send, pump, wait_until, what="the page")
            await settle_geometry(send, pump)
            res = await send("Runtime.evaluate",
                             {"expression": SAMPLE_JS, "returnByValue": True})
            raw = res.get("result", {}).get("value")
            # AFTER the measurement, never before: the probe appends and removes a
            # span, and a DOM this file has not yet read is not one to mutate.
            await pin.state(send, label="the sample")
    finally:
        proc.kill()
        if not os.environ.get("CHROME_PROFILE"):
            shutil.rmtree(profile, ignore_errors=True)
    if not raw:
        return None, errors + ["the page returned nothing to measure"]
    return json.loads(raw), errors


def check_mesh(wheels, S, census):
    """1. MESH AT RENDER TIME.

    Two wheels mesh when their centres sit at the sum of their PITCH radii --
    not the padded outer radii the svg width reports, so the pad comes off
    first. The assertion is deliberately NOT "these particular pairs mesh",
    which would be circular (find the pairs that mesh, then assert they mesh).
    It is that NO WHEEL IS AN ORPHAN: solve() places every wheel after the first
    against one already placed, so a wheel with no meshing partner anywhere on
    the stage is a wheel the renderer has put somewhere solve() did not.

    The component count is reported rather than asserted. A chain whose bridge
    was refused is placed unbridged, which is a documented and warned-about
    state (CLAUDE.md, "A bridge that cannot be placed cleanly refuses"), and
    turning it into a hard failure would make this gate fail on a page that is
    behaving exactly as specified.
    """
    fails = []
    n = len(wheels)
    for w in wheels:
        w["rPitch"] = w["rOuter"] - (PAD_LINKED if w["linked"] else PAD_GHOST) * S
    pairs, worst_mesh, closest_gap = [], 0.0, None
    for i in range(n):
        for j in range(i + 1, n):
            a, b = wheels[i], wheels[j]
            dist = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
            diff = dist - (a["rPitch"] + b["rPitch"])
            if abs(diff) < TOL_MESH_PX:
                pairs.append((i, j, diff))
                worst_mesh = max(worst_mesh, abs(diff))
            elif closest_gap is None or abs(diff) < abs(closest_gap[2]):
                closest_gap = (i, j, diff)

    partners = {i: 0 for i in range(n)}
    for i, j, _ in pairs:
        partners[i] += 1
        partners[j] += 1

    # Connected components, reported.
    seen, comps = set(), 0
    adj = {i: [] for i in range(n)}
    for i, j, _ in pairs:
        adj[i].append(j)
        adj[j].append(i)
    for i in range(n):
        if i in seen:
            continue
        comps += 1
        stack = [i]
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            stack.extend(adj[k])

    if n < 2:
        print(f"1 MESH        n/a  -- {n} wheel on this stage, nothing to mesh with")
        return []
    for i in range(n):
        if partners[i]:
            continue
        a = wheels[i]
        # How far off the nearest candidate is, so the failure says how badly
        # rather than only that it happened.
        near = min(abs(math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
                       - (a["rPitch"] + b["rPitch"]))
                   for k, b in enumerate(wheels) if k != i)
        fails.append(f"wheel {i} ({'linked' if a['linked'] else 'idler'}) at "
                     f"({a['cx']:.1f},{a['cy']:.1f}) meshes with nothing -- the nearest "
                     f"centre distance is off by {near:.2f}px")
    gap = f"{closest_gap[2]:+.1f}px (wheels {closest_gap[0]},{closest_gap[1]})" if closest_gap else "n/a"
    print(f"1 MESH        {'ok  ' if not fails else 'FAIL'} {len(pairs)} meshing pairs over {n} wheels, "
          f"{comps} component{'s' if comps != 1 else ''}; worst residual {worst_mesh:.4f}px "
          f"of {TOL_MESH_PX}px, closest non-mesh {gap}")
    if census:
        for i, j, diff in pairs:
            print(f"                 wheels {i:>2},{j:<2} residual {diff:+.4f}px")
    return fails


def check_blank(wheels, badges, S, census):
    """2. NO WHEEL RENDERS EMPTY.

    The tooth census is the exact half and carries this check: teethPath() emits
    two quadratic fillet blends per tooth and no other 'Q', so the blank states
    its own tooth count -- and the wheel's rendered radius states what that count
    must be, since a pitch radius IS module * teeth / 2. The two are compared as
    integers, with no tolerance at all. An empty <svg> has no blank; a blank
    drawn at the wrong size, count or scale disagrees.

    The shape floor and the badge test are the blunt half: an <svg> that drew
    nothing, and a hub badge that fetched no icon -- which is what a file:// load
    or a wrong Content-Type on the .svg objects produces, silently, because
    loadIcons()'s .catch swallows the failure.
    """
    fails = []
    worst = 0.0
    for i, w in enumerate(wheels):
        if not w["hasBlank"]:
            fails.append(f"wheel {i} draws no blank -- its <svg> holds no path outside <defs>")
            continue
        implied = 2 * (w["rPitch"] / S) / MODULE
        drawn_teeth = w["quads"] / 2
        worst = max(worst, abs(implied - drawn_teeth))
        if abs(implied - drawn_teeth) > 0.5 or drawn_teeth < 1:
            fails.append(f"wheel {i} draws {drawn_teeth:g} teeth but its rendered pitch radius "
                         f"{w['rPitch'] / S:.3f} implies {implied:.3f}")
        if w["drawn"] < MIN_DRAWN_SHAPES:
            fails.append(f"wheel {i} draws only {w['drawn']} shapes, under the "
                         f"{MIN_DRAWN_SHAPES} both renderers emit unconditionally")
    empty = [b["label"] for b in badges if b["svgs"] < 1 or b["shapes"] < 1]
    for label in empty:
        fails.append(f"hub badge {label!r} holds no drawn icon -- loadIcons() failed silently "
                     f"(a file:// load, or the icons served as the wrong type)")
    print(f"2 BLANK       {'ok  ' if not fails else 'FAIL'} {len(wheels)} wheels, "
          f"tooth census exact to {worst:.4f} of a tooth; "
          f"min shapes {min([w['drawn'] for w in wheels], default=0)} of {MIN_DRAWN_SHAPES}; "
          f"{len(badges)} badges, {len(badges) - len(empty)} carrying an icon")
    if census:
        for i, w in enumerate(wheels):
            print(f"                 wheel {i:>2} {'linked' if w['linked'] else 'idler '} "
                  f"{w['quads'] // 2:>3} teeth drawn, {2 * (w['rPitch'] / S) / MODULE:7.4f} implied, "
                  f"{w['drawn']:>3} shapes")
    return fails


def check_engraving(wheels, badges, census):
    """3. ENGRAVING PRESENT ON MARKED WHEELS.

    A linked wheel is a service, and every service's handle is struck into its
    band -- `engravedRims` defaults true and index.html's own note says Charles
    wants it. Bridge idlers carry no engraving by design (#65: an idler is the
    drive between two machines, not a wheel someone forgot to label), so they
    are exempt.

    Three things are asserted, because only the third of them can tell a drawn
    engraving from a present one: the text is non-empty, its textPath target
    resolves inside the same <svg>, and its computed length is greater than
    zero. A dangling href leaves the string in the DOM and paints nothing.

    The badge count is checked against the linked-wheel count for the same
    reason: a linked wheel and a hub badge are two renderings of one fact, and
    if they ever disagree the page is drawing a service it cannot name.
    """
    fails = []
    linked = [(i, w) for i, w in enumerate(wheels) if w["linked"]]
    shortest = None
    for i, w in linked:
        marks = [t for t in w["texts"] if t["text"]]
        if not marks:
            fails.append(f"wheel {i} is a linked wheel with no engraving at all")
            continue
        for t in marks:
            if not t["target"]:
                fails.append(f"wheel {i} engraving {t['text']!r} rides a textPath whose "
                             f"target does not resolve -- nothing is painted")
            if not t["len"] > 0:
                fails.append(f"wheel {i} engraving {t['text']!r} has computed length "
                             f"{t['len']} -- present in the DOM, absent from the page")
            if shortest is None or t["len"] < shortest[1]:
                shortest = (t["text"], t["len"])
    if not linked:
        fails.append("no linked wheels on the stage at all -- nothing to engrave, and "
                     "nothing this check could ever fail on")
    if len(badges) != len(linked):
        fails.append(f"{len(linked)} linked wheels but {len(badges)} hub badges -- a linked "
                     f"wheel and a badge are two renderings of one service")
    s = f"shortest {shortest[0]!r} at {shortest[1]:.1f}px" if shortest else "none measured"
    print(f"3 ENGRAVING   {'ok  ' if not fails else 'FAIL'} "
          f"{sum(len([t for t in w['texts'] if t['text']]) for _, w in linked)} marks on "
          f"{len(linked)} linked wheels ({len(wheels) - len(linked)} idlers exempt); {s}")
    if census:
        for i, w in linked:
            for t in w["texts"]:
                print(f"                 wheel {i:>2} {t['text']!r} len {t['len']:.2f} "
                      f"target {'resolves' if t['target'] else 'DANGLING'}")
    return fails


def check_ink(wheels, census):
    """4. INK CENSUS.

    Every colour on a wheel is produced by flatTones(c) or shades(c), and both
    are pure functions of ONE base colour that mix it toward black or toward
    white. So the census is not a count of colours, it is a statement about the
    set: each literal ink must be a tone of that wheel's own base -- same hue,
    saturation not thrown away, value inside the band those mixes can reach.
    The base is read off the blank's own fill, through its gradient when that is
    what the fill points at, so nothing here needs to know the palette.

    That is what catches "a fill went black" with no image: black shares no
    hue, keeps no saturation and sits far under the value floor. It equally
    catches a stray hardcoded colour, a tone taken from the wrong wheel, and a
    theme's palette leaking into the other theme's render.

    FLAT_INK is exempt and is the only exemption: the engraving is struck in one
    fixed ink on every wheel alike, so it is deliberately NOT a tone of the
    wheel's colour. It is read out of index.html rather than retyped.
    """
    fails = []
    ext = {"sat": 9.9, "val_lo": 9.9, "val_hi": 0.0, "hue": 0.0}
    for i, w in enumerate(wheels):
        inks = [k for k in w["inks"] if k != FLAT_INK]
        if len(inks) < MIN_DISTINCT_INKS:
            fails.append(f"wheel {i} is painted in {len(inks)} distinct ink(s), under the "
                         f"{MIN_DISTINCT_INKS} every renderer emits -- its tonal structure is gone")
        base = hsv(w["base"]) if w["base"] else None
        if not base:
            fails.append(f"wheel {i} has no resolvable base colour on its blank "
                         f"({w['base']!r}) -- the ink census cannot be made")
            continue
        bh, bs, bv = base
        for ink in sorted(inks):
            t = hsv(ink)
            if not t:
                fails.append(f"wheel {i} carries an unparseable ink {ink!r}")
                continue
            th, ts, tv = t
            sr = ts / bs if bs > 0 else 1.0
            vr = tv / bv if bv > 0 else 1.0
            ext["sat"] = min(ext["sat"], sr)
            ext["val_lo"] = min(ext["val_lo"], vr)
            ext["val_hi"] = max(ext["val_hi"], vr)
            if bs >= HUE_BASE_SAT_MIN and th is not None and bh is not None:
                ext["hue"] = max(ext["hue"], hue_gap(th, bh))
                if hue_gap(th, bh) > HUE_TOL_DEG:
                    fails.append(f"wheel {i} ink {ink} is hue {th:.1f}deg against the wheel's "
                                 f"{bh:.1f}deg base {w['base']} -- not a tone of it")
            if sr < SAT_RATIO_MIN:
                fails.append(f"wheel {i} ink {ink} keeps {sr:.2f} of the base {w['base']}'s "
                             f"saturation, under {SAT_RATIO_MIN} -- the colour has been "
                             f"drained out of it")
            if not (VAL_RATIO[0] <= vr <= VAL_RATIO[1]):
                fails.append(f"wheel {i} ink {ink} sits at {vr:.2f} of the base {w['base']}'s "
                             f"value, outside {VAL_RATIO} -- no mix of that base reaches it")
            if census:
                print(f"                 wheel {i:>2} {ink} vs base {w['base']}  "
                      f"hue {'n/a' if th is None or bh is None else f'{hue_gap(th, bh):5.2f}deg'}  "
                      f"sat x{sr:.3f}  val x{vr:.3f}")
    print(f"4 INK         {'ok  ' if not fails else 'FAIL'} "
          f"{sum(len(w['inks']) for w in wheels)} inks over {len(wheels)} wheels; "
          f"worst hue {ext['hue']:.2f}deg of {HUE_TOL_DEG}, "
          f"min sat x{ext['sat']:.3f} of {SAT_RATIO_MIN}, "
          f"val x{ext['val_lo']:.3f}-{ext['val_hi']:.3f} of {VAL_RATIO}")
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    # POSITIONAL, like every other harness here -- and with a default that is a
    # real server's address rather than a guess, because a harness pointed at
    # nothing returns confident nonsense.
    ap.add_argument("url", nargs="?", default="http://127.0.0.1:8765/",
                    help="served page (NOTHING IS STARTED FOR YOU -- serve the repo first)")
    ap.add_argument("--query", default="",
                    help="scope query, e.g. '?who=charles'. 127.0.0.1 is a STAGE_HOSTS "
                         "name, so with no query this measures the combined stage")
    ap.add_argument("--seed", type=int, default=20260804,
                    help="LCG seed for the deal; the verdict is a property of this")
    ap.add_argument("--viewport", default="1440x900")
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--census", action="store_true",
                    help="print every measurement, not just the verdict")
    ap.add_argument("--fonts", default="auto", choices=["auto", "pinned", "blocked"],
                    help="auto: serve the webfont from prefetched bytes, degrading "
                         "loudly to blocked if it cannot be fetched. pinned: require "
                         "it, exit 2 if unobtainable. blocked: never fetch it — the "
                         "engraving lengths reported are then fallback metrics.")
    a = ap.parse_args()

    # Appended to a bare directory URL, a query with no '?' becomes a PATH:
    # 'who=charles' asks for a file of that name, gets a 404, and a 404 has no
    # wheels to fail on -- so every check would pass vacuously. Same trap
    # tools/pixel_regress.py guards.
    if a.query and not a.query.startswith("?"):
        print(f"FATAL: --query must start with '?' (got {a.query!r})")
        return 2
    try:
        vw, vh = (int(n) for n in a.viewport.lower().split("x"))
    except ValueError:
        print(f"FATAL: --viewport must be WxH (got {a.viewport!r})")
        return 2

    # The font state is decided ONCE, here, before any browser exists -- a pin
    # armed after the first navigation is decoration. The stylesheet URL is read
    # off the SERVED page rather than this repo's index.html, because this harness
    # is pointed at a server somebody else started and it may be serving a
    # different worktree entirely.
    pin = fontpin.FontPin.decide(want=a.fonts, url=a.url)
    fatal = pin.announce()
    if fatal:
        print(fatal)
        return 2

    t0 = time.time()
    payload, errors = asyncio.run(sample(a.url + a.query, a.seed, (vw, vh), a.theme, pin))
    if payload is None:
        print("FATAL: " + "; ".join(errors))
        return 2
    # Verified, not assumed, and BEFORE any verdict is printed: a render that did
    # not draw in the state this run chose means the pin leaked, and the numbers
    # below are then about a typography nobody chose.
    if not pin.report():
        return 2

    wheels, badges, S = payload["wheels"], payload["badges"], payload["S"]
    print(f"{a.url + a.query}   seed {a.seed}, {vw}x{vh}, {a.theme} theme")
    print(f"scale S {S:.2f} (from --gsfit), radius pad {PAD_LINKED:.2f} linked / "
          f"{PAD_GHOST:.2f} idler solve units\n")

    if not wheels:
        print("RESULT: FAIL (no wheels on the stage -- four checks that measure "
              "nothing would otherwise all pass)")
        return 1
    if S <= 0:
        print("RESULT: FAIL (--gsfit unreadable -- no pitch radius, no mesh test)")
        return 1

    fails = []
    fails += check_mesh(wheels, S, a.census)
    fails += check_blank(wheels, badges, S, a.census)
    fails += check_engraving(wheels, badges, a.census)
    fails += check_ink(wheels, a.census)

    # A /favicon.ico 404 is expected and benign: the real icon is a data: URI
    # injected through helmet, so the browser asks for the default path first.
    real = [e for e in errors if "favicon.ico" not in e]
    if real:
        print(f"\nconsole errors: {len(real)}")
        for e in real[:10]:
            print("  " + e)

    if fails:
        print(f"\n{len(fails)} failure{'s' if len(fails) != 1 else ''}:")
        for f in fails:
            print("  " + f)
        print(f"\nRESULT: FAIL   ({time.time() - t0:.1f}s)")
        return 1
    print(f"\nRESULT: PASS   ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
