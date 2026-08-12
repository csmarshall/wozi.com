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

THE WEBFONT IS PINNED, AND OF EVERY HARNESS HERE THIS IS THE ONE THAT HAD TO BE
(GitHub #140). Every number below is a type measurement: the font's own
ascent/descent box, this string's deepest ink, the line box it sits in. All of
them are properties of the FACE THAT RESOLVED, and which face that was used to
come off fonts.googleapis.com at load time -- so the gate's own currency was set
by a third party's network. Measured here, on this machine, one run apart:

    Manrope resolved        worst overrun -0.58px, faces reported "Manrope"
    Manrope unreachable     worst overrun -1.45px, faces reported "system-ui"

0.87px of swing, against a +0.05px tolerance and 0.58px of real clearance. Today
neither regime trips the gate, which is exactly what makes it dangerous: a
regression that eats 0.6px of clearance is caught in one regime and passed in the
other, and nothing in the output said which one you got except a `face` column
nobody was diffing. So the font now comes out of `tools/fontpin.py` -- prefetched
into this process, served from memory, and VERIFIED by a width probe after every
render rather than assumed. See that module for why `document.fonts` cannot
answer the question.

AND IT IS MEASURED TWICE. Pinning removes the network; it does not prove that
what was measured is repeatable. Two full passes, over two separate navigations,
must agree on every label's ink to REPEAT_TOL or no verdict is reported at all --
because this harness measures ABSOLUTES and so cannot borrow pixel_regress's
control of subtracting two renders. Cheap here in a way it is not everywhere:
one pass is about ten seconds, and a second one buys the only evidence that a
0.58px clearance is a fact about the page rather than about this run. --once
gives it up, and says so by printing no `repeat` line.

AND THE DEAL IS DEALT BY THE HARNESS, NOT BY THE PAGE (GitHub #167, and #155
before it). Until this change the injected LCG below read its seed out of
`location.search` and this file navigated with `?seed=` appended -- which handed
the dealing to `index.html`'s own `DEAL_SEED` block, because that runs at module
scope, strictly after anything injected, and reassigns `Math.random` to its own
generator. The injection was dead code and the page dealt every machine this gate
has ever measured, which CLAUDE.md forbids in as many words. The seed is baked
into the closure now, `dom_invariants.seed_js()` is the one home for it, and the
URL carries no `seed=` at all. The consequence when reading output from before
this change: every deal, and therefore every badge coordinate, differs. The type
numbers themselves do not -- font-size and line-height are fixed by the page --
which is why the verdict did not move.

Usage: python3 tools/pill_clip.py [url] [--fonts auto|pinned|blocked] [--once]
                                  [--seed N]
"""

import argparse
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fontpin
# ONE HOME FOR THE SEEDED GENERATOR, imported rather than copied (GitHub #167).
# Four copies of it is what let one fault be four. Note what the import costs:
# dom_invariants reads its constants out of index.html at module scope, so a
# checkout whose index.html has stopped matching those regexes fails here on
# import too. Every caller of this harness runs from a checkout, and the
# alternative -- a fifth copy of five lines of LCG -- is what #167 was about.
import dom_invariants as dom

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

_ap = argparse.ArgumentParser(description="does the hover pill's label fit its clip box")
# POSITIONAL, because CI and tools/mutation_gate.py both append the served URL
# to this argv and neither should have to learn a flag for it.
_ap.add_argument("url", nargs="?", default="http://127.0.0.1:8765/")
_ap.add_argument("--fonts", default="auto", choices=["auto", "pinned", "blocked"],
                 help="auto: serve the webfont from prefetched bytes, degrading "
                      "loudly to blocked if it cannot be fetched. pinned: require "
                      "it, exit 2 if unobtainable. blocked: never fetch it — the "
                      "shipped typography is then NOT what gets measured.")
_ap.add_argument("--once", action="store_true",
                 help="one measurement pass instead of two. Faster, and it gives up "
                      "the only evidence that the numbers are repeatable.")
# A FLAG, NOT A BURIED CONSTANT, because the two halves of a determinism claim
# need different seeds: repeat runs at one seed must be bit-identical, AND a
# different seed must draw a different machine. With the seed hardcoded only the
# first half was checkable, and on its own that is also what a silently dead
# injection looks like -- which is exactly the fault #167 fixed. It also makes the
# bounds below re-characterisable over many deals without editing the harness.
_ap.add_argument("--seed", type=int, default=20260812,
                 help="the deal to pin, injected into this harness's own LCG and "
                      "never named in the URL (default: 20260812)")
_ARGS = _ap.parse_args()
URL = _ARGS.url
# How far two passes over the same page may disagree about one label's ink before
# this refuses to report a verdict. Not a tolerance on the MEASUREMENT -- the gate
# below still has its own +0.05px and that is untouched -- but on the harness's
# agreement with itself. With the font pinned and the geometry static, two passes
# come back identical to the last printed digit, so anything above rounding is a
# real wobble and worth stopping for.
REPEAT_TOL = 0.01
# How long the badges may go on moving after the page reports itself loaded, and
# how far two reads may disagree and still count as still. Half a pixel, because
# the badge centre is a rect midpoint and sub-pixel jitter in a settled layout is
# not motion; the budget is generous because reaching it is a hard failure, not a
# fallback.
SETTLE_TOL = 0.5
SETTLE_TIMEOUT_S = 15.0
# THE DEAL IS SEEDED, and it became necessary the moment this file measured twice.
# Every wheel is dealt at random, so two navigations draw two different machines:
# the badges come back in a different order, at different coordinates, and a
# comparison by position is then comparing "Instagram" against "LinkedIn" and
# calling the 3.1px between their descenders a wobble. The type numbers themselves
# do not depend on the deal -- font-size and line-height are fixed -- but the
# harness's ability to line two passes up does.
#
# THE SEED IS BAKED INTO THE INJECTED CLOSURE AND `?seed=` NEVER REACHES THE URL
# (GitHub #167). The retired version of this comment claimed it seeded "the same
# way tools/devices.py and tools/dom_invariants.py" do, which was true when it was
# written and became false in the other direction at CL#180: those two stopped
# reading the seed out of `location.search` precisely because doing so let
# index.html's own DEAL_SEED -- module scope, so after any injected script -- take
# Math.random over and deal the machine itself. A comment asserting compliance is
# what stops the next reader checking, so it is worth saying plainly what this
# does: `dom.seed_js(SEED)` closes over the number, is the only thing on the page
# that touches Math.random, and the URL below carries a cache-buster and nothing
# else. A repeat run being bit-identical is therefore evidence about this closure.
SEED = _ARGS.seed
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
    # THE FONT DECISION IS TAKEN BEFORE CHROME EXISTS, and that ordering is the
    # whole mechanism -- a pin armed after the first navigation is decoration.
    # The stylesheet URL comes off the SERVED page rather than this repo's
    # index.html, because this harness is pointed at a server somebody else
    # started and it may be serving another worktree entirely.
    pin = fontpin.FontPin.decide(want=_ARGS.fonts, url=URL)
    fatal = pin.announce()
    if fatal:
        print(fatal)
        return 2

    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
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

    passes = []
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        # send/pump/wait_until come from fontpin, and the reason is a deadlock
        # rather than tidiness: `Fetch.requestPaused` arrives UNSOLICITED, the
        # loop-until-my-id send this file used to carry threw it away, and a
        # paused stylesheet nobody answers hangs the page forever. `pump` is the
        # replacement for asyncio.sleep wherever a navigation may still be in
        # flight -- a plain sleep there holds the font for its whole duration and
        # then lets it land, which is the late-font regime the pin exists to
        # remove.
        send, pump, wait_until = fontpin.attach(ws, pin)

        async def ev(expr):
            r = await send("Runtime.evaluate", {"expression": expr,
                                                "returnByValue": True,
                                                "awaitPromise": True})
            return r.get("result", {}).get("value")

        await send("Runtime.enable")
        # Page.enable FIRST, or the injection fontpin.install() makes is accepted
        # and silently never runs.
        await send("Page.enable")
        await send("Page.addScriptToEvaluateOnNewDocument",
                   {"source": dom.seed_js(SEED)})
        await pin.install(send)

        async def one_pass(tag):
            """Navigate, hover every badge, measure every label. Returns the rows.

            A whole pass per measurement, not two reads of one render, because
            the thing being checked for repeatability is what the NAVIGATION
            resolved -- which face was in place when the page measured its own
            type. Two reads of one render would agree by construction and prove
            nothing.
            """
            # The CDP profile persists across runs, so a cached document is a real
            # hazard -- one of these harnesses served a 300s-old page once.
            bust = ("&" if "?" in URL else "?") + "v=" + str(int(time.time() * 1000))
            # NO `seed=` IN THE URL, EVER (GitHub #167). The deal comes off the
            # injected closure; naming a seed here would hand it to index.html's
            # own DEAL_SEED, which runs later and wins.
            await send("Page.navigate", {"url": f"{URL}{bust}"})
            # A CONDITION, not the fixed 4s this used to sleep. That 4s was tuned
            # to a network which is no longer in the path: the font now arrives
            # from memory, so the honest wait is "loaded and fonts.ready settled"
            # and it comes in well under a second.
            await fontpin.wait_ready(send, pump, wait_until, what=f"{tag}: the page")
            # AND THEN WAIT FOR THE BADGES TO STOP MOVING, which load-complete and
            # fonts.ready do not imply and the retired 4.0s sleep was silently
            # covering. Every hover below is dispatched at a COORDINATE, so a badge
            # that shifts after this list is read is a pointer that lands on the
            # page instead of on the badge -- and a pill that never opened reads as
            # the feature being broken (#46) rather than as the harness aiming at
            # where it used to be. Caught for real: with only the load condition,
            # one of eight badges came back 0px wide on the second pass.
            #
            # Two consecutive reads agreeing is the same shape of condition
            # devices.py uses on its own geometry, and it is a condition rather
            # than a duration -- it comes in well under the old sleep on a settled
            # page and waits longer than it on a slow one.
            badges = None
            began = time.monotonic()
            end = began + SETTLE_TIMEOUT_S
            while time.monotonic() < end:
                now = json.loads(await ev(LIST_JS))
                if badges is not None and len(now) == len(badges) and all(
                        a["label"] == b["label"]
                        and abs(a["x"] - b["x"]) <= SETTLE_TOL
                        and abs(a["y"] - b["y"]) <= SETTLE_TOL
                        for a, b in zip(now, badges)):
                    badges = now
                    break
                badges = now
                await pump(0.1)
            else:
                # print-then-exit-2, NOT `raise SystemExit("...")` (GitHub #156).
                # The string form prints and exits 1, which is the code for "it
                # measured and the answer is bad" -- the exact opposite of the
                # sentence it was printing. CL#179 fixed seven of these and this
                # one survived, in the file that was not in its list.
                print(f"FATAL: {tag}: the badges never stopped moving — two reads "
                      f"{SETTLE_TOL}px apart still disagree after "
                      f"{SETTLE_TIMEOUT_S}s. Nothing has been measured, so nothing "
                      f"has been proved.")
                raise SystemExit(2)
            if not badges:
                return None
            # HOW MUCH OF THE TIMEOUT WAS USED. SETTLE_TIMEOUT_S is the other
            # re-measurable bound in this file and nothing printed the figure it is
            # a bound on, so the only way to learn the margin was to watch a run
            # fail. Reported per pass; the verdict does not read it.
            settled_s = time.monotonic() - began
            rows = []
            for b in badges:
                lab = json.dumps(b["label"])
                # Park the pointer well away first, so leaving the previous badge
                # is a real mouseleave and each measurement starts from rest.
                await send("Input.dispatchMouseEvent",
                           {"type": "mouseMoved", "x": 4, "y": 4, "buttons": 0})
                await pump(0.15)
                shut = json.loads(await ev(MEASURE_JS.replace("%LABEL%", lab)))
                # A REAL mouse move. A MouseEvent built in JS and dispatched at
                # the element does not open the pill; the width stays 0 and the
                # gate would then be measuring a collapsed span.
                await send("Input.dispatchMouseEvent",
                           {"type": "mouseMoved", "x": b["x"], "y": b["y"],
                            "buttons": 0})
                await pump(0.9)   # the max-width transition is 260ms
                d = json.loads(await ev(MEASURE_JS.replace("%LABEL%", lab)))
                d["shutW"] = shut.get("openW")
                d["aria"] = b["label"]
                # THE DEAL, CARRIED THROUGH TO THE OUTPUT (GitHub #167). The type
                # numbers are the same on every machine the page can deal, so they
                # cannot tell a working seed injection from a dead one -- the badge
                # coordinates are the only thing printed here that the deal moves.
                # Without them "two runs agree" and "the seed does nothing" look
                # identical, which is how a dead injection survived this long.
                d["bx"], d["by"] = round(b["x"], 1), round(b["y"], 1)
                rows.append(d)
            # AFTER the measurements, never before: the probe appends and removes
            # a span, and a font state read before the page has been measured says
            # nothing about the render that was.
            await pin.state(send, label=tag)
            print(f"{tag:<19}: badges settled in {settled_s:.2f}s "
                  f"(timeout {SETTLE_TIMEOUT_S}s)")
            return rows

        for i in range(1 if _ARGS.once else 2):
            got = await one_pass(f"pass {i + 1}")
            if got is None:
                proc.kill()
                print("FATAL: no badges found — is anything serving " + URL + "?")
                return 2
            passes.append(got)

    proc.kill()

    rows = passes[0]

    # ---- the typography this run measured, verified rather than assumed -------
    if not pin.report():
        return 2

    # ---- the harness agreeing with itself, before it says anything about the
    # page. A disagreement here is not a FAIL: it is a refusal, because a label
    # whose ink moved between two identical navigations has not been measured.
    if len(passes) > 1:
        drift = []
        # MATCHED BY ARIA LABEL, NOT BY POSITION. The seed makes the two passes
        # deal the same machine, so the orders do in fact agree -- and lining them
        # up by index anyway would mean that the day the seed injection silently
        # stops working, this check reports 3.1px of "drift" that is really
        # Instagram's descender being compared with LinkedIn's baseline. The label
        # is the identity; the index is an accident of the deal.
        second = {r.get("aria"): r for r in passes[1]}
        # THE MARGIN, NOT ONLY THE VERDICT. REPEAT_TOL and SETTLE_TOL are both
        # bounds somebody has to be able to re-measure, and a line that says only
        # "agrees" gives the next person no way to tell 0.00px of agreement from
        # 0.009px of it. Reported, never asserted on: the assertions below are
        # against the bounds themselves.
        worst_drift, worst_drift_what = -1.0, "-"
        worst_move = 0.0
        for a in passes[0]:
            b = second.get(a.get("aria"))
            if b is None:
                drift.append(f"{a.get('aria', '?')} measured in pass 1 and absent "
                             f"from pass 2")
                continue
            if a.get("err") or b.get("err"):
                continue
            for key in ("inkBottom", "clipBottom", "overrun", "openW"):
                # `gap`, not `d`: `d` is the reported-drift loop variable a few
                # lines below and the measured row dict above, and a name reused
                # across three meanings in one function is the shape of trap #156
                # recorded for `fatal`.
                gap = abs((a.get(key) or 0) - (b.get(key) or 0))
                if gap > worst_drift:
                    worst_drift, worst_drift_what = gap, f"{a.get('text', '?')} {key}"
                if gap > REPEAT_TOL:
                    drift.append(f"{a.get('text', '?')} {key} "
                                 f"{a.get(key)} vs {b.get(key)}")
            # The badge's own position, which the deal moves and the type does not.
            # A seed injection that stopped working shows up here first and by a
            # wide margin -- two random deals put a badge tens of pixels away --
            # so it is measured even though the verdict does not depend on it.
            worst_move = max(worst_move,
                             abs((a.get("bx") or 0) - (b.get("bx") or 0)),
                             abs((a.get("by") or 0) - (b.get("by") or 0)))
            if a.get("used") != b.get("used"):
                drift.append(f"{a.get('text', '?')} face {a.get('used')!r} vs "
                             f"{b.get('used')!r}")
        if len(passes[0]) != len(passes[1]):
            drift.append(f"badge count {len(passes[0])} vs {len(passes[1])}")
        if drift:
            print(f"FATAL: two passes over the same page disagree "
                  f"(tolerance {REPEAT_TOL}px) — nothing has been proved about the "
                  f"page, only about the harness:")
            for d in drift[:12]:
                print("   " + d)
            return 2
        print(f"repeat             : 2 passes agree to within {REPEAT_TOL}px "
              f"(worst {worst_drift:.2f}px on {worst_drift_what}; badge centres "
              f"moved {worst_move:.2f}px, budget {SETTLE_TOL})")

    print(f"url                : {URL}")
    print(f"seed               : {SEED} (injected; the URL carries no seed=)")
    print(f"badges measured    : {len(rows)}")
    # THE DEAL, PRINTED (GitHub #167). Two runs at one seed must produce this line
    # identically and two different seeds must not, which is the only pair of
    # observations that can tell a live seed injection from a dead one. It is a
    # census, not a gate: nothing here is asserted against a bound, because where
    # the machine lands is a property of the deal and the viewport rather than of
    # the typography this harness is for.
    print("deal               : " + " ".join(
        f"{r.get('text', '?')}@{r.get('bx')},{r.get('by')}" for r in rows))
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
