#!/usr/bin/env python3
"""Photograph the page deterministically, and diff this working tree against a
git ref pixel for pixel.

    tools/pixel_regress.py                  # working tree vs HEAD
    tools/pixel_regress.py --ref origin/main
    tools/pixel_regress.py --shot /tmp/x.png # just capture, no comparison
    tools/pixel_regress.py --query '?who=charles'   # one chain, not the stage
    tools/pixel_regress.py --path fidget/   # a different page in the same tree
    tools/pixel_regress.py --panel          # with the pop-out menu OPEN

WHY THIS EXISTS. A screenshot of this page proves very little on its own, for
two separate reasons, and both had to be dealt with before a pixel diff could
mean anything:

  1. The train is DEALT at random. Math.random picks the tooth counts, the web
     families, the bearing angles and the background machinery, so two loads
     draw two different machines. Seeding an LCG over Math.random before any
     page script runs fixes which machine you get.

  2. The train is TURNING. The seed does not say how far it has turned by the
     time the shutter opens, and that depends on how long the page took to load.
     So requestAnimationFrame is queued rather than run, performance.now is
     pinned to the same virtual clock, and __pump(n) advances exactly n frames
     of exactly 1/60s. Pinning performance.now matters as much as the rAF
     timestamp: the loop stamps `last` from the real clock when it mounts and
     compares it against the frame timestamp, so a page that loaded 30ms slower
     skipped a different number of frames and landed on a different angle. With
     rAF frozen and the clock real, two runs of identical code still differed by
     ~40k pixels; with both frozen, they differ by none.

With those two nailed down, "0 pixels differ" is a real statement about the
code. This is what proved #58 -- collapsing forty dead ternaries out of gearSvg
changed the markup by construction, so only the pixels could say whether it
changed the drawing.

The comparison side checks out the ref into a throwaway git worktree and serves
it on its own port, so nothing touches your working tree -- no stash, no
checkout, no chance of losing an edit to a harness run.

THIS IS ALSO THE GATE ON THE DELIVERED ARTIFACT. `tools/strip_comments.py
--in-place` makes the deploy's checkout the stripped file, so "working tree vs
HEAD" becomes "what ships vs what is reviewed" with nothing added here: the
transform is allowed to change the bytes and forbidden to change the drawing, and
that is exactly the one claim this tool can settle. `--path` is what extends it to
/fidget/, which is stripped by the same step and is a different page in the same
tree rather than a query on this one.

THE FOURTH THING A SHOT CANNOT SEE IS A CONTROL THAT IS NOT DISPLAYED, AND THE
GATE REACHES INTO THE PAGE RATHER THAN THE PAGE GROWING A FLAG FOR THE GATE
(GitHub #144). The pop-out menu is `display:none` until its corner button is
clicked, so every control inside it -- the speed slider, the wear slider, the
three style-layer checkboxes, both section headings -- was invisible to this
tool for the whole of its life. Five of them were rewritten in CL#169 and the
verdict came back `0 px differ / PASS` at both viewports, with the font pinned
and the control clean. The gate was working correctly and photographing a page
that does not contain the thing that changed.

That is strictly worse than the `?kind=` coverage gap documented below. There the
discipline is to remember a flag; here there was no flag to remember, and no
amount of care by the author could have produced a shot of the panel.

`--panel` is that shot. It is deliberately NOT a `?panel` query parameter, which
is the cheaper option and the wrong one: `?seed` is the only determinism
affordance shipped code carries (CL#109), and `ORIGIN_MOUNT` was kept out of the
address bar for exactly this reason -- "a second switch reachable from the
address bar is a second way for the page to draw something no gate
photographs." Adding one to close a gate's blind spot is that same mistake
pointing the other way. `?hud` earns its exception by being the only way to read
tick rate on a real phone; a harness can click, so a panel flag has no argument
of that kind. The shipped page is byte-identical with this mode and without it.

WHAT IT COSTS IS ONE MORE STATE TRANSITION, AND THAT IS WAITED FOR AS A
CONDITION. The click is delivered to the element the page itself marks as the
disclosure (`[aria-expanded]`, the same target tools/devices.py and
tools/a11y_audit.py locate) and never to a screen position, because a coordinate
is a guess that goes stale the moment the corner row is renumbered -- and a
click into empty space produces a photograph of a closed panel, which is exactly
the 0px this mode exists to stop. Then the page's own report is polled until it
says the panel is open AND the controls inside it have non-zero boxes; a page
that never gets there stops the run rather than being photographed shut. The
settle happens AFTER the panel is open, so the pixels being waited on are the
ones the shutter is going to catch.

THE THIRD NONDETERMINISM, AND THE ONE THAT COMES OFF THE NETWORK. index.html
pulls Manrope from fonts.googleapis.com, and the page's own #98 handler clears
its text-measurement memo when document.fonts.ready settles. That makes the
drawing depend on WHEN the font arrives relative to the first render, and the
answer is measured in a third party's latency:

  * font applied before the first render (local, ~65-146ms) -- 0 px.
  * font applied AFTER it but before the shutter -- a few thousand px, in nine
    narrow bands, one per wheel: the engraved lettering, measured once against
    fallback metrics and never fully re-measured. Reproduced here by holding the
    font requests 1.4s or longer: a clean STEP FUNCTION, 0 px below the boundary
    and 2,941 px (390x844) / 7,292 px (1440x900) above it, identical at every
    delay past it.
  * font never applied -- the whole page differs (1,296,000 px at 1440x900).

CI ran two trees x two viewports = four independent races per check and got two
of them on the far side of that step, which is the 195 px / 2016 px it reported.
/fidget/ passed both viewports in the same run because it is the one published
page with no Google Fonts link at all -- it has always drawn in the fallback, and
so has always been deterministic.

document.fonts is no help in telling which regime you are in. With the requests
blocked, document.fonts.status is 'loaded' and document.fonts.check('600 13px
Manrope') is TRUE -- because the stylesheet never arrived, no @font-face was ever
registered, and `check` on a family it has never heard of trivially agrees. The
only honest detector is to MEASURE: one string in "'Manrope',monospace" against
the same string in "monospace", which differ by 58px at 40px type when the
webfont is really painting and by nothing at all when it is not.

So the font is pinned the same way Math.random and performance.now are: taken off
the network entirely. Both font hosts are intercepted, and one of two states is
chosen ONCE per run, before any browser starts, and enforced identically on both
trees -- fulfilled from bytes prefetched into this process, or failed outright.
Either way every navigation sees the same font state with no network in it, and
that state is VERIFIED by the width probe after every single render. A run that
cannot make both trees agree on it stops with exit 2 rather than diffing two
pictures taken under different typography, which is the shape of failure CL#159
removed from the Pillow path and which must not come back through the font.

Note what that does and does not buy, because the difference matters and the
weaker claim is the tempting one to make. Pinning removes the network, and the
state check proves both trees drew under the same typography; neither makes a
render insensitive to WHEN the font arrives. Held artificially at a uniform 2.5s,
all three passes agreed at 0 px and the picture they agreed on was 999 px away
from the one a prompt font produces. Two equally wrong pictures agreeing
perfectly is the one failure this gate may not have.

An absolute budget on the arrival was tried as the guard against that and is
refuted -- see ARRIVAL_JS for the two measurements that killed it, and note that
the obvious derived condition (arrived before first paint) is refuted by the same
pair. So the guard is not a model of the mechanism at all. IT IS A CONTROL, and
every guard above it refuses one NAMED mechanism while the faults that keep
getting through are mechanisms nobody had named yet. A control refuses all of
them, including the next one.

NEITHER SIDE OF A SUBTRACTION MAY BE A SINGLE SAMPLE. CL#162 shot the working
tree twice and the ref once, and that asymmetry was itself a bug: an odd pass on
the ref side leaves the control reading a contented 0 px while the artifact
comparison reads over a thousand, so the gate blames the stripper for a wobble in
its own measurement. Measured under CPU contention with the runner's flags, the
odd pass landed on the ref side in two runs out of three. So each tree is now
photographed until it agrees with ITSELF (stable_render, up to STABLE_ATTEMPTS),
and only then are the two agreed renders subtracted. The working tree is done
twice, before and after the ref, so its agreement spans the whole run instead of
one burst. A tree that needs a third pass is reported as a flake rather than
smoothed over, and a tree that never agrees stops the run at exit 2.

Verified against a coin-flip reproduction of the font fault -- half the
navigations paying a slow fetch, half not -- where it refuses instead of
returning the artifact verdict CI printed.

And with the font off the network there is nothing left to sleep for, so the
fixed four seconds is gone. Readiness is a CONDITION: document load complete,
document.fonts.ready settled, and then two screenshots STABLE_SAMPLE_MS apart
that come back byte-identical. The settle is deliberately in pixels rather than
in DOM mutations -- see STABLE_SAMPLE_MS for the page that makes a quiet-DOM
test impossible -- and it catches the #98 re-render whenever it lands rather
than waiting it out. A navigation that took a flat 4s now takes a few hundred
milliseconds, which is what pays for tripling the number of passes: six passes
of two viewports come in under the old four's.

Exit 0 if every viewport matches, 1 if any pixel differs, 2 if it could not
photograph -- OR COULD NOT COMPARE, OR COULD NOT PIN THE FONT. Those used to be
different: a missing Pillow printed "cannot diff" and exited 0, so the strongest
gate in the tree passed by not running, on a machine that had simply never
installed numpy. A comparison that did not happen is not a comparison that
passed.
"""

import argparse
import asyncio
import base64
import json
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

CHROME = (os.environ.get("CHROME")
          or shutil.which("google-chrome") or shutil.which("chromium-browser")
          or shutil.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if sys.platform == "darwin" and not os.environ.get("WOZI_PX_CI_FLAGS") else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])

# PINNING THE RENDERER, for the same reason the clock and the deal are pinned.
# CL#162's control caught a residual: ~1,200 px at a max channel delta of 10 --
# antialiasing scale, not structural -- on the combined stage at 1440x900 only,
# appearing in roughly one render pass in several. Reproduced on a desk only under
# heavy CPU contention with the runner's own flags, which is why it was invisible
# here and red there.
#
# None of these change what the page looks like; every one removes a decision
# Chrome is otherwise free to make differently on two runs of identical bytes:
#
#   run-all-compositor-stages-before-draw  finish compositing before the frame is
#       drawn, so a capture cannot land mid-stage. The most direct answer to a
#       difference that is pure antialiasing.
#   disable-new-content-rendering-timeout  never draw a partial frame because a
#       deadline passed -- a deadline is wall-clock, and wall-clock is the input
#       this harness exists to remove.
#   disable-partial-raster  raster the tile, never reuse part of the previous
#       one. Incremental reuse is a known source of AA differences between frames
#       that ought to be identical.
#   disable-background-timer-throttling, disable-renderer-backgrounding,
#   disable-backgrounding-occluded-windows  the window is deliberately parked at
#       -4000,-4000 (off every screen), so it is exactly the window Chrome is
#       entitled to treat as occluded and deprioritise. Under contention that is
#       a coin toss about how much work a pass gets to finish.
#   disable-threaded-animation, disable-threaded-scrolling  keep the work on one
#       thread, so ordering does not depend on how many cores were free.
#   force-color-profile=srgb  pin colour management, which otherwise follows the
#       host display and is a real local-vs-CI difference.
#
# force-device-scale-factor=1 restates the deviceScaleFactor the emulation
# override already sets, so a browser launched on a HiDPI desk cannot start out
# rastering at 2x before the override lands.
# WOZI_PX_NO_DET_FLAGS=1 launches without them, which is the third stress knob and
# the only way to check that this list still earns its place. A flag list is
# exactly the kind of thing that accretes and is never re-measured; with this, the
# claim "removing these brings the flake back" stays testable instead of becoming
# folklore. Measured under 16-way CPU contention with the runner's flags: without
# the list, 2 runs in 6 needed a discarded pass; with it, 0 in 14.
DETERMINISTIC_FLAGS = [] if os.environ.get("WOZI_PX_NO_DET_FLAGS") else [
    "--run-all-compositor-stages-before-draw",
    "--disable-new-content-rendering-timeout",
    "--disable-partial-raster",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-threaded-animation",
    "--disable-threaded-scrolling",
    "--force-color-profile=srgb",
    "--force-device-scale-factor=1",
]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# THE FONT MECHANISM LIVES IN tools/fontpin.py NOW (GitHub #140), because three
# other harnesses needed it and three copies of it would have been three chances
# to fix two of them. What was here -- the host list, the Chrome-UA prefetch, the
# Fetch interception, the width probe, the coin-flip delay knob -- is that module,
# lifted unchanged in behaviour. What stays here is what is particular to a PIXEL
# comparison: the settle in PNG bytes, the per-tree agreement control, and the
# fact that both trees are held to one state decided before either is served.
FONT_HOSTS = fontpin.FONT_HOSTS

# THE SETTLE IS MEASURED IN PIXELS, WHICH IS THIS GATE'S OWN CURRENCY, and that
# is not the obvious choice -- a MutationObserver watching for a quiet DOM was
# written first and is unusable. /fidget/ ends with `setInterval(draw, 250)`
# (fidget/index.html:1472), an unconditional repaint four times a second forever,
# so DOM quiescence is not merely slow to reach there, it is UNREACHABLE: the
# observer never saw a gap longer than 220ms and the gate timed out on a page
# that had in fact been finished for twenty seconds. Lowering the threshold under
# 250ms would have been a constant tuned to one page's timer.
#
# Two screenshots this far apart, identical, says the thing actually being
# asserted -- the picture has stopped changing -- and it is true of a page that
# rebuilds identical content on a timer as well as of one that has gone still. It
# is also strictly stronger than any DOM proxy: a mutation that changes no pixel
# cannot hold the shutter, and a change that alters pixels without touching the
# DOM (a late font swapping in, which is the whole of the fault above) cannot
# sneak past it.
STABLE_SAMPLE_MS = 150
# The ceiling on waiting for that condition. Reaching it is a HARSH failure and
# not a fallback -- a page that never goes quiet has not been photographed, and
# saying so is the whole point of CL#159's exit 2.
READY_TIMEOUT_S = 25.0
# How many passes a single tree may take to agree with itself before the run is
# abandoned. Three, so a lone odd pass is survivable and reported, and two odd
# passes out of three is not quietly averaged into a verdict.
STABLE_ATTEMPTS = 3

# EVERY OTHER CEILING IN THIS FILE IS ENFORCED BY A LOOP THAT CALLS `send`, AND
# `send` ITSELF HAD NO CEILING AT ALL (GitHub #174). That is not a theoretical
# hole: run 31639824875 sat in_progress for 93 MINUTES on this gate and never
# advanced, and `concurrency: cancel-in-progress: false` — which is correct and
# must stay — queued every later deploy behind it, so the site silently stayed on
# an older commit for the whole of it.
#
# The shape of the fault is worth stating, because a reader looking at
# READY_TIMEOUT_S, PANEL_TIMEOUT_S and STABLE_ATTEMPTS would reasonably conclude
# this file cannot hang. Each of those is `while time.monotonic() < end: await
# send(...)`, so the deadline is only ever CHECKED BETWEEN round trips. A single
# round trip that never comes back never returns to the loop that would notice,
# and `send` waited on `pump_once(30.0)` in a `while not fut.done()` — a 30s read
# timeout retried forever, which is an infinite wait wearing a timeout's clothes.
#
# A DEAD SOCKET IS NOT THE CASE TO WORRY ABOUT, and that is measured rather than
# assumed: SIGSTOP the harness's own headless Chrome and `websockets` (15.0.1)
# keepalive ends the read in 48-50s with ConnectionClosedError. Which also settles
# what the 93-minute hang was NOT — a dropped connection would have died in a
# minute. So the case that has no exception to catch is a Chrome that is ALIVE and
# wedged: answering keepalive pings, never answering `Page.captureScreenshot` or
# `Runtime.evaluate`. Only a deadline ends that one, and the same SIGSTOP
# experiment against this version stops in CDP_TIMEOUT_S naming the method.
#
# Worth knowing and NOT fixed here: that ConnectionClosedError is unhandled, so it
# leaves as a traceback and exits 1 — this tool's word for THE ARTIFACT MOVED, on a
# run that photographed nothing. Measured, exit=1. It is the #156 confusion by a
# different route and wants its own ticket rather than being folded in here.
#
# 90s is a per-CALL ceiling, not a budget for the run, and the margin is measured
# rather than guessed: a full healthy `--ref HEAD` passes with the deadline
# squeezed to WOZI_CDP_TIMEOUT_S=2, and passes at 2 again under
# WOZI_PX_CPU_THROTTLE=6, which is the knob that reproduces a shared CI runner. So
# no legitimate round trip here — navigation or screenshot included — takes two
# seconds even throttled, and 90 is 45x the worst observed. It is deliberately far
# above the honest worst case because deploy.yml's step and job bounds are the
# backstop and this is the thing that should fire FIRST, naming the CDP method
# that stopped answering. Overridable so the deadline itself stays testable —
# WOZI_CDP_TIMEOUT_S=0.001 is how it was demonstrated to fire, and to fire as
# exit 2 rather than as a pixel verdict.
CDP_TIMEOUT_S = float(os.environ.get("WOZI_CDP_TIMEOUT_S", "90") or 90)

# ---- opening the pop-out, for --panel (GitHub #144) -------------------------
# THE TARGET IS THE PAGE'S OWN DISCLOSURE MARKER, NOT A COORDINATE. Every corner
# button is a fixed-position circle whose `right` is its index in the row times a
# button pitch, and that index has already been renumbered once (CL#114 moved the
# menu toggle from 2 to 3 and back). A harness that clicked x/y would have gone on
# clicking the button that used to be there, and a click into empty space
# photographs a SHUT panel and reports 0 px -- the fault this mode exists to
# remove, reintroduced by the mode itself. `[aria-expanded]` is the one attribute
# the panel's toggle carries and nothing else on the page does; tools/devices.py
# and tools/a11y_audit.py locate it the same way, so there is one answer to "which
# button opens the menu" rather than three.
#
# The click returns a WORD rather than nothing, so a missing toggle is a fast,
# named failure instead of ten seconds of polling a condition that can never come
# true. /fidget/ is the case that matters: it is a different page with no menu at
# all, so `--panel --path fidget/` must say so immediately rather than time out
# and leave the operator guessing whether the wait was too short.
PANEL_CLICK_JS = ("(()=>{const b=document.querySelector('[aria-expanded]');"
                  "if(!b)return 'no toggle';"
                  "if(b.getAttribute('aria-expanded')==='true')return 'already open';"
                  "b.click();return 'clicked';})()")
# AND THE OPEN STATE IS A CONDITION, NEVER A SLEEP. Two things are asserted and
# they fail for different reasons. `aria-expanded === 'true'` is the page saying
# it changed state -- if that is false the click was delivered somewhere useless.
# A non-zero box on the controls themselves is the stronger half: the panel is
# switched between `display:flex` and `display:none`, and a display:none subtree
# reports every rect as 0x0, so a control with width is proof that what is about
# to be photographed is actually being laid out. #46's shape is the thing being
# refused here -- a check that passes loudest when the feature is broken.
PANEL_OPEN_JS = ("(()=>{const b=document.querySelector('[aria-expanded]');"
                 "if(!b)return 'no toggle';"
                 "if(b.getAttribute('aria-expanded')!=='true')return 'shut';"
                 "const c=[...document.querySelectorAll("
                 "'nav input[type=range],nav input[type=checkbox]')]"
                 ".filter(e=>e.getBoundingClientRect().width>0);"
                 "return c.length?'open':'no controls';})()")
# The ceiling on that condition. A click is a discrete event and the re-render is
# synchronous, so this is orders of magnitude more than it needs and is here only
# so a genuinely stuck page stops the run instead of hanging it.
PANEL_TIMEOUT_S = 10.0
# WHAT THE OPEN PANEL ACTUALLY MEASURES, reported alongside the shot and not
# gated on. The panel's `max-height` is `calc(100vh - --offtop - --offbot)`
# (CL#114) and it sits on a content-box element with 10px of padding, so its
# border box can exceed the cap it was given -- GitHub #149, which no gate has
# ever seen because tools/devices.py measures with the panel SHUT. This mode is
# the first thing in the tree that photographs it open, so it is the first thing
# that can print the two numbers side by side. Diagnostics, deliberately: #149 is
# an index.html fault and turning a number into a verdict here would be a gate
# nobody asked this change for.
PANEL_BOX_JS = ("(()=>{const n=document.querySelector('nav[aria-label]');"
                "if(!n)return 'no panel';const r=n.getBoundingClientRect();"
                "const cs=getComputedStyle(n);"
                "return JSON.stringify({h:+r.height.toFixed(1),"
                "cap:cs.maxHeight,vh:innerHeight,"
                "over:+(r.bottom-innerHeight).toFixed(1)});})()")
PREFETCH_UA = fontpin.PREFETCH_UA
# The stress knob that makes this file's claim about the race testable: hold every
# intercepted font request on a coin flip, and the gate must STILL report 0 px and
# the same font state on both trees. It is read once, in fontpin, along with the
# reasoning for why a coin flip and not a uniform delay -- WOZI_PX_FONT_DELAY_S is
# still the name that turns it on, and WOZI_FONT_DELAY_S now works too, since the
# other three harnesses share the mechanism and should share the knob.
FONT_DELAY_S = fontpin.FONT_DELAY_S
# The second stress knob, and the one that reproduces a CI runner rather than a
# network. WOZI_PX_CPU_THROTTLE=6 slows every render 6x through
# Emulation.setCPUThrottlingRate, which is what a shared 2-core runner does to a
# 600KB page. It exists because the first residual this gate caught was invisible
# on a fast desk and reproducible on CI, and a fault that can only be seen on the
# machine that is blocked by it cannot be worked on. Off unless set, announced
# when on, and no gate sets it.
CPU_THROTTLE = float(os.environ.get("WOZI_PX_CPU_THROTTLE", "0") or 0)


def free_port():
    """Never a fixed port (#42): two of these running at once used to fight over
    one and the loser reported a page fault that was really a harness fault."""
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# Installed before any page script runs. Everything nondeterministic about the
# page is pinned here and nowhere else -- index.html carries no test hooks.
def determinism_js(seed):
    return (
        "(()=>{"
        f"let s={seed};"
        "Math.random=()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};"
        "let q=[],t=0;"
        "window.requestAnimationFrame=(cb)=>{q.push(cb);return q.length};"
        "window.cancelAnimationFrame=()=>{};"
        "performance.now=()=>t;"
        "window.__pump=(n)=>{for(let i=0;i<n;i++){const c=q;q=[];t+=16.6667;"
        "c.forEach(f=>{try{f(t)}catch(e){}})}};"
        "})()")


# The arrival observer, the load condition and the width probe all come from
# fontpin, so the answer to "was the webfont really painting" is one answer for
# every harness here rather than four that can drift apart.
OBSERVE_JS = fontpin.OBSERVE_JS
ARRIVAL_JS = fontpin.ARRIVAL_JS
READY_JS = fontpin.READY_JS
applied_js = fontpin.applied_js
page_source = fontpin.page_source

# The dead-socket exception, taken from fontpin rather than imported again here
# (GitHub #180). It is guarded there — `websockets` without that module leaves an
# empty tuple, which `except` accepts and never matches — and one home for it means
# this file and `attach()` cannot come to disagree about what a closed socket is.
WS_CLOSED = fontpin.WS_CLOSED


def fatal(msg):
    """Stop with the exit code the docstring promises for a run that could not
    photograph, which is 2 and not 1.

    THE CODE IS PART OF THE MESSAGE. Every failure below is "nothing has been
    photographed, so nothing has been proved" -- an unservable tree, a browser
    with no DevTools endpoint, a page that never loaded, a picture that never
    went still, a menu that is not there to open. `raise SystemExit("FATAL: ...")`
    prints the string and exits 1, which is this tool's word for THE ARTIFACT
    MOVED, so a caller reading only the code was told a pixel verdict by a run
    that never took a picture. That is CL#159's fault exactly -- "a comparison
    that did not happen is not a comparison that passed" -- one rung further
    down, in the codes rather than in the prose, and it survived because every
    one of these paths prints a sentence that makes it obvious to a human
    reading the log and invisible to anything reading the exit status.

    AND IT PRINTS A `RESULT:` LINE, because that is the channel anybody actually
    reads (GitHub #181). main() already ends every exit-2 it reaches itself with
    `RESULT: COULD NOT COMPARE`; these paths ended with a FATAL and no verdict line
    at all, so a sweep filtering `grep -E "^RESULT"` saw NOTHING from them -- not a
    pass, not a failure, no line. That is precisely how #181's own investigation
    threw away the diagnostic it needed, and it is a11y_audit's `RESULT: NOT
    AUDITED` lesson one rung down: the exit code and the verdict line are two
    channels, and only one of them gets read.
    """
    print(msg)
    print("\nRESULT: COULD NOT COMPARE — nothing was photographed, so this is a "
          "harness fault and not a pixel verdict (see the FATAL line above)")
    raise SystemExit(2)


def serve(directory):
    """A server per tree, on its own port. Returns (proc, base_url)."""
    port = free_port()
    p = subprocess.Popen([sys.executable, "-m", "http.server", str(port),
                          "--bind", "127.0.0.1", "--directory", directory],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}/"
    for _ in range(60):
        try:
            urllib.request.urlopen(base, timeout=1).read(1)
            return p, base
        except Exception:
            time.sleep(0.1)
    p.kill()
    fatal(f"FATAL: could not serve {directory}")


async def shoot(url, viewports, seed, frames, theme, pin, panel=False,
                theme_honoured=True):
    """One browser, every viewport. Returns ({label: png}, {label: font state}).

    `pin` is the font state, decided once by main() before either tree is served,
    so both trees are photographed under the same typography by construction
    rather than by both happening to win the same race. It carries the
    interception itself (tools/fontpin.py): every request to a font host is
    answered from prefetched bytes or failed outright, identically on both sides.

    `panel` opens the pop-out menu before the shutter (GitHub #144). It belongs
    HERE rather than in main() for the same reason the seed and the clock do:
    every render the run makes goes through this function -- three passes of the
    working tree and two of the ref -- so putting the click anywhere else would
    give a subtraction one side with the panel open and one without, which is a
    picture of the panel rather than of the change.
    """
    port = free_port()
    profile = tempfile.mkdtemp(prefix="wozi-px-")
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
         *DETERMINISTIC_FLAGS, *CI_FLAGS, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(60):
        for method in (None, "PUT"):
            try:
                target = f"http://127.0.0.1:{port}/json/new?about:blank"
                req = (urllib.request.Request(target, method=method)
                       if method else target)
                ws_url = json.load(urllib.request.urlopen(req, timeout=1))["webSocketDebuggerUrl"]
                break
            except Exception:
                pass
        if ws_url:
            break
        time.sleep(0.2)
    if not ws_url:
        proc.kill()
        fatal("FATAL: no DevTools endpoint")

    out, states, arrivals, boxes = {}, {}, {}, {}
    mid = 0
    async with websockets.connect(ws_url, max_size=10 ** 8) as c:
        # A request paused by the Fetch domain arrives UNSOLICITED and can land
        # while we are blocked reading the reply to something else -- and it must
        # be answered, or the page it belongs to hangs on a stylesheet forever.
        # So every message is dispatched: replies resolve their own future,
        # Fetch.requestPaused is answered on the spot. The old loop-until-my-id
        # helper silently discarded everything else, which was fine while nothing
        # else needed a response and is a deadlock now.
        waiting, paused = {}, []

        async def wire(payload, what):
            """One outbound frame, with the DEAD-SOCKET case named (GitHub #180).

            Distinct from the deadline below and deliberately so: that one is a
            Chrome which answers keepalive and never the method, this one is a
            Chrome that is gone. `websockets` raises here on its own after 48-50s
            of keepalive — a duration this does not try to shorten, since the
            defect was never the wait but the traceback at the end of it, which
            exits 1 and means "the artifact moved" on a run that photographed
            nothing.
            """
            try:
                await c.send(payload)
            except WS_CLOSED as e:
                proc.kill()
                fontpin.socket_died(f"{what} (no picture was taken)", e)

        async def raw(m, p=None):
            nonlocal mid
            mid += 1
            await wire(json.dumps({"id": mid, "method": m, "params": p or {}}),
                       f"{m} (unsolicited)")

        async def pump_once(timeout, what="a background message"):
            try:
                msg = json.loads(await asyncio.wait_for(c.recv(), timeout=timeout))
            except asyncio.TimeoutError:
                return
            except WS_CLOSED as e:
                proc.kill()
                fontpin.socket_died(f"{what} (no picture was taken)", e)
            if msg.get("id") in waiting:
                waiting.pop(msg["id"]).set_result(msg.get("result", {}))
            elif msg.get("method") == "Fetch.requestPaused":
                paused.append(msg["params"])
                await answer(msg["params"])

        async def answer(ev):
            """One of two states, chosen for the whole run and applied identically
            to every request on a font host -- fulfilled from prefetched bytes or
            failed outright, never let through to the network, because a single
            un-pinned request is the whole race back again. The mechanism is
            fontpin's; what stays here is the socket it is answered on."""
            await pin.answer(ev, raw)

        async def send(m, p=None):
            """One CDP round trip, with a DEADLINE (GitHub #174).

            The id is captured into a local: `pump_once` answers paused font
            requests through `raw`, which increments `mid` too, so the reply this
            call is waiting for cannot be identified by re-reading `mid`.

            Reaching the deadline is exit 2 and nothing else. A call that never
            came back means no picture was taken, and the whole of CL#159's
            argument is that "I could not look" must never read the same as
            "nothing moved" — least of all by way of hanging until a CI job's
            360-minute default kills the runner with no sentence in the log at
            all.
            """
            nonlocal mid
            mid += 1
            my = mid
            fut = asyncio.get_event_loop().create_future()
            waiting[my] = fut
            await wire(json.dumps({"id": my, "method": m, "params": p or {}}), m)
            end = time.monotonic() + CDP_TIMEOUT_S
            while not fut.done():
                left = end - time.monotonic()
                if left <= 0:
                    waiting.pop(my, None)
                    proc.kill()
                    fatal(f"FATAL: Chrome never answered {m} — no reply in "
                          f"{CDP_TIMEOUT_S:g}s, with {len(waiting)} other call(s) "
                          f"outstanding. The browser is wedged rather than gone (a "
                          f"closed socket raises instead), so nothing has been "
                          f"photographed and nothing has been proved.")
                await pump_once(min(1.0, left), m)
            return fut.result()

        async def wait_until(expr, want, timeout, what):
            """Poll an in-page expression until it returns `want`, pumping the
            socket in between so paused font requests are still answered while we
            wait. Returns the last value seen, so the caller can say which term
            was binding when it gave up."""
            end = time.monotonic() + timeout
            last = "never evaluated"
            while time.monotonic() < end:
                r = await send("Runtime.evaluate",
                               {"expression": expr, "returnByValue": True})
                last = r.get("result", {}).get("value", last)
                if last == want:
                    return last
                await pump_once(0.05)
            fatal(f"FATAL: {what} timed out after {timeout}s "
                             f"(last: {last!r}) -- nothing has been photographed, "
                             f"so nothing has been proved")

        await send("Page.enable")
        await send("Runtime.enable")
        if CPU_THROTTLE:
            await send("Emulation.setCPUThrottlingRate", {"rate": CPU_THROTTLE})
        await send("Fetch.enable", {"patterns": pin.patterns})
        await send("Page.addScriptToEvaluateOnNewDocument",
                   {"source": determinism_js(seed)})
        await send("Page.addScriptToEvaluateOnNewDocument", {"source": OBSERVE_JS})
        # The theme is remembered in localStorage, so it has to be planted and
        # the page reloaded -- and the reload has to happen through the same
        # injected script, or the second load deals a different train.
        await send("Page.addScriptToEvaluateOnNewDocument",
                   {"source": "try{localStorage.setItem('wozi-theme','%s')}catch(e){}" % theme})

        async def settle(label, timeout):
            """Wait until two screenshots STABLE_SAMPLE_MS apart come back
            identical. PNG bytes are compared and not decoded pixels: one encoder
            with one set of settings renders identical pixels to identical bytes,
            and going through Pillow here would make the settle depend on the very
            optional import whose absence CL#159 had to stop treating as a pass."""
            end = time.monotonic() + timeout
            prev = None
            while time.monotonic() < end:
                shot = (await send("Page.captureScreenshot", {"format": "png"}))["data"]
                if shot == prev:
                    return
                prev = shot
                # Pumped, not slept, so a font request paused in the middle of the
                # settle is still answered and the page can actually finish.
                deadline = time.monotonic() + STABLE_SAMPLE_MS / 1000
                while time.monotonic() < deadline:
                    await pump_once(0.02)
            fatal(
                f"FATAL: {label} never stopped changing — two screenshots "
                f"{STABLE_SAMPLE_MS}ms apart still differ after {timeout}s. Nothing "
                f"has been photographed, so nothing has been proved.")

        probe = applied_js(pin.families)
        for w, hgt in viewports:
            label = f"{w}x{hgt}"
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": w, "height": hgt, "deviceScaleFactor": 1,
                        "mobile": False})
            await send("Page.navigate", {"url": url})
            await wait_until(READY_JS, "ready", READY_TIMEOUT_S,
                            f"{label} never finished loading")
            if panel:
                # BEFORE the settle, not after: opening the panel is the last
                # thing that changes the picture, so waiting for the picture to
                # stop changing has to come after it. Reversed, the settle
                # certifies a page that is about to be redrawn, which is the one
                # thing this gate's readiness condition exists to refuse.
                r = await send("Runtime.evaluate", {"expression": PANEL_CLICK_JS,
                                                    "returnByValue": True})
                clicked = r.get("result", {}).get("value")
                if clicked not in ("clicked", "already open"):
                    proc.kill()
                    fatal(
                        f"FATAL: {label} has no pop-out toggle to click "
                        f"({clicked!r}) — --panel is asking for a menu this page "
                        f"does not have (/fidget/ is the likely case). Nothing has "
                        f"been photographed, so nothing has been proved.")
                await wait_until(PANEL_OPEN_JS, "open", PANEL_TIMEOUT_S,
                                 f"{label}: the pop-out panel never opened")
            await settle(label, READY_TIMEOUT_S)
            if panel:
                r = await send("Runtime.evaluate", {"expression": PANEL_BOX_JS,
                                                    "returnByValue": True})
                boxes[label] = r.get("result", {}).get("value", "unreadable")
            # Read the font state BEFORE pumping frames: the probe appends a span
            # and removes it, which is a DOM mutation, and taking it while the
            # quiescence condition still matters would invalidate the thing that
            # was just waited for.
            r = await send("Runtime.evaluate", {"expression": probe, "returnByValue": True})
            states[label] = r.get("result", {}).get("value", "unreadable")
            # THE THEME IS ASSERTED, NOT ASSUMED (GitHub #157). It is planted in
            # localStorage by an injected script and nothing here ever read it
            # back, so a `--theme light` run that silently rendered dark would
            # report a contented 0 px about a picture of the other theme -- which
            # is CL#171's fault verbatim, where an f-string brace bug made
            # a11y_audit's "PASS in both themes" one theme twice for months. It
            # matters more now that the deploy has a light run: the run whose whole
            # job is to look at the other palette is exactly the one that must
            # prove it did. Exit 2, because a shot of the wrong theme has
            # photographed nothing this run asked for.
            #
            # ONLY WHERE THE PLANT IS READ. `--path fidget/` is a page that keeps
            # its own `data-theme="auto"` and never looks at `wozi-theme`, so
            # asserting there would fail a run that is behaving correctly -- and
            # the honest consequence, said out loud rather than hidden behind a
            # passing assertion, is that `--theme` MEANS NOTHING on such a page and
            # a light run of it tests the same picture twice. `theme_honoured` is
            # decided once, off the served page's own source, before any browser
            # exists, exactly as the font decision is.
            if theme_honoured:
                r = await send("Runtime.evaluate",
                               {"expression": "document.documentElement.getAttribute('data-theme')",
                                "returnByValue": True})
                drawn = r.get("result", {}).get("value")
                if drawn != theme:
                    proc.kill()
                    fatal(f"FATAL: {label} asked for the {theme} theme and the page reports "
                          f"data-theme={drawn!r}. This shot is of the wrong palette, so "
                          f"nothing this run asked for has been photographed.")
            r = await send("Runtime.evaluate", {"expression": ARRIVAL_JS,
                                                "returnByValue": True})
            arrivals[label] = r.get("result", {}).get("value", -1)
            await send("Runtime.evaluate",
                       {"expression": f"window.__pump && window.__pump({frames})",
                        "returnByValue": True})
            shot = await send("Page.captureScreenshot", {"format": "png"})
            out[label] = base64.b64decode(shot["data"])
    proc.kill()
    shutil.rmtree(profile, ignore_errors=True)
    return out, states, arrivals, boxes


def compare(a, b, label, outdir):
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print("   Pillow/numpy missing — cannot diff; wrote both shots instead")
        return None
    import io
    x = np.asarray(Image.open(io.BytesIO(a)).convert("RGB")).astype(int)
    y = np.asarray(Image.open(io.BytesIO(b)).convert("RGB")).astype(int)
    if x.shape != y.shape:
        print(f"   {label:<12} SHAPE {x.shape} vs {y.shape}")
        return 10 ** 9
    d = np.abs(x - y)
    n = int((d.max(2) > 0).sum())
    print(f"   {label:<12} {n:>8} px differ   max channel delta {int(d.max())}")
    if n and outdir:
        # Red where it moved, so the difference is findable rather than counted.
        m = (d.max(2) > 0)
        vis = y.copy()
        vis[m] = [255, 0, 0]
        Image.fromarray(vis.astype("uint8")).save(os.path.join(outdir, f"diff-{label}.png"))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="HEAD", help="git ref to compare against")
    ap.add_argument("--seed", type=int, default=20260731)
    ap.add_argument("--frames", type=int, default=90, help="virtual frames to pump before the shot")
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--shot", help="capture the working tree to this path and stop")
    ap.add_argument("--viewport", action="append", default=[],
                    help="WxH, repeatable (default 1440x900 and 390x844)")
    ap.add_argument("--outdir", default=tempfile.gettempdir())
    # The page is scoped by hostname AND by ?who=, and the harness only ever
    # serves 127.0.0.1 -- which is a combined-stage host. Without this there is
    # no way to ask whether ONE chain still draws exactly as it did, which is
    # the only question left once the default view has deliberately changed.
    ap.add_argument("--query", default="",
                    help="query string appended to the page, e.g. '?who=charles'")
    # /fidget/ is a second published page in the same tree, with its own physics
    # loop, and it goes through the same stripper. Without this there is no way to
    # ask the artifact question about it at all -- --query cannot reach a path, and
    # a second harness for one page would be a second thing to keep in step.
    ap.add_argument("--path", default="",
                    help="path under the served root, e.g. 'fidget/'")
    # The pop-out is display:none until it is clicked, so the default shot cannot
    # contain any control that lives in it (GitHub #144). This is the only way to
    # ask whether the speed slider, the wear slider or the three style-layer
    # checkboxes still draw as they did -- and it is a HARNESS action rather than a
    # query parameter on purpose, so the shipped page stays byte-identical whether
    # this mode is used or not. See the module docstring for why a `?panel` flag
    # was refused.
    ap.add_argument("--panel", action="store_true",
                    help="click the pop-out menu open before shooting, so the "
                         "controls inside it are actually in the picture")
    # Which typography both trees are photographed under. See the module
    # docstring for why this cannot be left to the network. `auto` is the default
    # because it is the only one of the three that is deterministic AND never
    # fails the deploy for something that is not the deploy's fault: the decision
    # is taken ONCE, before a browser exists, and both trees are then held to it
    # and verified against it. A run that degrades says so on its own first line.
    ap.add_argument("--fonts", default="auto", choices=["auto", "pinned", "blocked"],
                    help="auto: serve the webfont from prefetched bytes, falling back "
                         "to blocking it (loudly) if it cannot be fetched. "
                         "pinned: require it, exit 2 if unobtainable. "
                         "blocked: never fetch it — real typography is not exercised.")
    a = ap.parse_args()

    # It is appended to a bare directory URL, so without the '?' it becomes a
    # PATH: 'who=charles' asks for a file of that name and gets a 404 on both
    # sides, which compare cleanly and print '0 px differ'. A gate that passes by
    # photographing two error pages is worse than one that fails.
    if a.query and not a.query.startswith("?"):
        print(f"FATAL: --query must start with '?' (got {a.query!r}); "
              f"without it the shot is a 404, and two 404s agree perfectly")
        return 2

    # Same trap, one level up: a leading slash makes the join absolute and drops
    # the port, and a directory without its trailing slash is a 404 from
    # http.server -- which, again, two of would compare perfectly.
    if a.path.startswith("/"):
        print(f"FATAL: --path must be relative to the served root (got {a.path!r})")
        return 2
    if a.path and not a.path.endswith("/") and "." not in os.path.basename(a.path):
        print(f"FATAL: --path {a.path!r} names neither a file nor a directory "
              f"(a directory needs its trailing slash, or http.server 404s)")
        return 2

    vps = [tuple(int(n) for n in v.lower().split("x")) for v in a.viewport] \
        or [(1440, 900), (390, 844)]

    # ---- the font decision, taken once, before any browser exists -------------
    # Read off the WORKING tree's own copy of the page: both trees are the same page
    # modulo comments, and the ref worktree does not exist yet -- it must not be
    # what decides how the FIRST tree is photographed. fontpin.decide() does the
    # scan, the Chrome-UA prefetch and the degradation-to-blocked; `announce` prints
    # the one line saying which state this run is in, and returns a fatal message
    # only when --fonts pinned asked for a state it could not have.
    src = page_source(ROOT, a.path)
    pin = fontpin.FontPin.decide(want=a.fonts, html_path=src)
    # NOT named `fatal`: that is the module-level helper (:398) which exits 2, and
    # `stable_render()` below closes over it. A local of that name shadows it for
    # the whole of main(), so the never-agrees path called None and died with a
    # TypeError -- exit 1, this tool's word for THE ARTIFACT MOVED (GitHub #156).
    announce_err = pin.announce()
    if announce_err:
        print(announce_err)
        return 2
    mode, expect = pin.mode, pin.expect

    # ---- the theme decision, taken the same way and for the same reason --------
    # Whether `--theme` reaches this page at all. The harness plants `wozi-theme`
    # in localStorage; a page that never reads that key cannot be put into either
    # theme by this tool, and /fidget/ is exactly such a page — it keeps its own
    # `data-theme="auto"`. Decided off the WORKING tree's source before any browser
    # exists, so the assertion in `shoot()` is only made where it can be true, and
    # the run SAYS which of the two situations it is in rather than leaving a
    # reader to assume the flag did something.
    theme_honoured = bool(src) and "wozi-theme" in open(
        src, encoding="utf-8", errors="replace").read()
    if not theme_honoured:
        print(f"theme: /{a.path} does not read 'wozi-theme' — --theme {a.theme} "
              f"reaches nothing here, and both themes photograph the same page")

    def stable_render(directory, who):
        """Photograph one tree until it agrees with itself, and say so if it did not
        the first time.

        WHY BOTH SIDES NEED THIS, and why CL#162's single control was not enough.
        That control sampled the WORKING tree twice and the ref once, so it could
        only ever catch an odd pass on one side of the comparison. Reproduced under
        contention, the odd pass landed on the REF side twice in three runs -- and
        then the control reads a contented 0 px while the artifact comparison reads
        1,214 px. The gate blamed the stripper for a fault in its own measurement,
        which is the exact failure it was written to stop. A side that has not been
        shown to agree with itself is not a side you can subtract.

        Two consecutive identical passes, up to STABLE_ATTEMPTS of them. A run that
        needs a third pass is a FLAKE THAT GETS REPORTED -- named, on its own NOTE
        line, so it is greppable in a CI log and countable over time rather than
        smoothed away. Majority is not silently taken: if no two passes agree, the
        run stops with exit 2 and nothing is claimed.
        """
        srv_, base_ = serve(directory)
        try:
            passes = []
            for _ in range(STABLE_ATTEMPTS):
                passes.append(asyncio.run(shoot(base_ + a.path + a.query, vps, a.seed,
                                                a.frames, a.theme, pin, a.panel,
                                                theme_honoured)))
                if len(passes) < 2:
                    continue
                # Compared as PNG bytes, per viewport: same encoder, same settings,
                # so identical pixels are identical bytes. No Pillow needed to
                # decide whether to keep shooting.
                for older in range(len(passes) - 1):
                    if all(passes[older][0][k] == passes[-1][0][k] for k in passes[-1][0]):
                        if len(passes) > 2:
                            print(f"   NOTE: {who} needed {len(passes)} passes to agree "
                                  f"with itself; discarded {len(passes) - 2} odd pass(es). "
                                  f"The machine is not rendering repeatably — this run is "
                                  f"still valid, but the flake is real and worth chasing.")
                        return passes[-1]
            fatal(f"FATAL: {who} never agreed with itself in {STABLE_ATTEMPTS} passes of "
                  f"identical bytes. This is a fault in the harness or the machine, not "
                  f"in the artifact, and nothing has been proved either way.")
        finally:
            srv_.kill()

    if a.shot:
        srv, base = serve(ROOT)
        try:
            now, now_fonts, now_ms, now_box = asyncio.run(
                shoot(base + a.path + a.query, vps, a.seed, a.frames, a.theme,
                      pin, a.panel, theme_honoured))
        finally:
            srv.kill()
        for label, box in sorted(now_box.items()):
            print(f"   {label:<12} panel {box}")
        # Same diagnostics as the comparison path, because --shot is what a human
        # uses to look at one render, and "which typography is this, and did it get
        # there in time" is exactly as load-bearing for a shot as for a diff.
        for label in now:
            print(f"   {label:<12} webfont {now_fonts[label]}, settled {now_ms[label]}ms")
        # One viewport per file, named, so --shot on several does not overwrite.
        for label, png in now.items():
            p = a.shot if len(now) == 1 else a.shot.replace(".png", f"-{label}.png")
            open(p, "wb").write(png)
            print(f"wrote {p}")
        return 0

    # ---- EACH SIDE IS ESTABLISHED BEFORE EITHER IS SUBTRACTED -----------------
    # The working tree first, so its two passes straddle the ref's in time and
    # catch drift across the run rather than only within a burst.
    now, now_fonts, now_ms, now_box = stable_render(ROOT, "the working tree")

    work = tempfile.mkdtemp(prefix="wozi-ref-")
    tree = os.path.join(work, "t")
    r = subprocess.run(["git", "-C", ROOT, "worktree", "add", "--detach", tree, a.ref],
                       capture_output=True, text=True)
    if r.returncode:
        print("FATAL: could not check out " + a.ref + "\n" + r.stderr.strip())
        return 2
    try:
        ref, ref_fonts, ref_ms, ref_box = stable_render(tree, a.ref)
    finally:
        subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", tree],
                       capture_output=True)
        shutil.rmtree(work, ignore_errors=True)

    # And one more pass of the working tree AFTER the ref, which is what makes the
    # working side's agreement span the whole run. stable_render's own two passes
    # are back-to-back; this is the straddle.
    again, again_fonts, again_ms, again_box = stable_render(ROOT, "the working tree (again)")

    print(f"\nworking tree vs {a.ref}   seed {a.seed}, {a.frames} frames, "
          f"{a.theme} theme, /{a.path}{a.query}, "
          f"fonts {'n/a — none linked' if expect == 'none' else mode}"
          f"{', POP-OUT PANEL OPEN' if a.panel else ''}")

    # The panel's own box, printed per viewport and per tree, because a mode whose
    # whole claim is "the panel is in this picture" should say what it measured
    # rather than be believed (GitHub #144). `over` is how far the panel's border
    # box falls past the bottom of the viewport, which is GitHub #149's number:
    # the max-height cap sits on a content-box element with 10px of padding, so
    # the border box is 20px taller than the cap allows and the panel's own
    # clearance is gone. Not asserted here — see PANEL_BOX_JS.
    for label in sorted(now_box):
        print(f"   panel {label:<12} working {now_box[label]}")
        # Only printed when it differs, and every difference is worth a line: the
        # ref's box differing is the change under test, and the working tree's own
        # second pass differing is the harness wobbling, which the pixel control
        # below would also catch but not explain.
        if ref_box.get(label) != now_box[label]:
            print(f"   panel {label:<12} {a.ref} {ref_box.get(label)}")
        if again_box.get(label) != now_box[label]:
            print(f"   panel {label:<12} working again {again_box.get(label)}")

    # ---- the font state is checked, never assumed ------------------------------
    # Deciding the mode up front makes the two renders SUPPOSED to match; this is
    # what proves they did. Both halves matter and they fail for different
    # reasons: a state that is not what the mode asked for means the pin leaked
    # (an unscanned URL, a provider redirect), and a state that differs BETWEEN the
    # trees is the original fault itself, back again. Either way the pixel counts
    # below would be a comparison of two pictures taken under different
    # typography, and reporting those as a pixel verdict is precisely the failure
    # shape CL#159 removed from the Pillow path.
    wrong = {f"{t}/{lb}": v
             for t, d in (("working", now_fonts), (a.ref, ref_fonts),
                          ("working (again)", again_fonts))
             for lb, v in d.items() if v != expect}
    disagree = [lb for lb in now_fonts
                if len({now_fonts[lb], ref_fonts.get(lb), again_fonts.get(lb)}) > 1]
    if wrong or disagree:
        for lb, v in sorted(wrong.items()):
            print(f"   {lb:<24} font state {v!r}, expected {expect!r}")
        for lb in disagree:
            print(f"   {lb:<24} RENDERS DISAGREE: working {now_fonts[lb]!r}, "
                  f"{a.ref} {ref_fonts.get(lb)!r}, working again {again_fonts.get(lb)!r}")
        print(f"\nRESULT: COULD NOT COMPARE — the two renders were not drawn under the "
              f"same typography, so any pixel count from them would be measuring the "
              f"font and not the change. Nothing has been proved either way.")
        return 2

    print(f"   every render: webfont {expect}   "
          f"(fonts.ready/first-paint ms: " +
          ", ".join(f"{lb} {now_ms[lb]}|{ref_ms.get(lb)}|{again_ms.get(lb)}"
                    for lb in now_ms) + ")")

    # ---- and the control is read BEFORE the verdict ---------------------------
    # Order matters here. The repeatability failure must be reported instead of a
    # pixel verdict and never alongside one, because a number the operator can read
    # as "the artifact moved 195 pixels" is exactly what sent somebody looking at
    # the stripper for a fault that was in this file.
    unstable = {}
    for label in now:
        n = compare(now[label], again[label], f"control {label}", None)
        if n:
            unstable[label] = n
    if unstable:
        print(f"\nRESULT: HARNESS NOT REPEATABLE — the SAME bytes photographed twice "
              f"disagree at " + ", ".join(f"{k} ({v} px)" for k, v in unstable.items()) +
              f". Nothing has been proved about {a.ref} either way: until this is 0, a "
              f"difference against the ref cannot be told apart from this one. Suspect "
              f"the machine or the harness, not the artifact.")
        return 2

    total = 0
    skipped = []
    for label in now:
        n = compare(ref[label], now[label], label, a.outdir)
        if n is None:
            skipped.append(label)
        total += (n or 0)
    if skipped:
        # Reported as a harness failure (2), never as agreement (0). See the
        # docstring: this is the gate the artifact rests on, and "I could not
        # look" must not read the same as "nothing moved".
        print(f"\nRESULT: COULD NOT COMPARE {len(skipped)} viewport(s) "
              f"({', '.join(skipped)}) -- install Pillow and numpy. Nothing has "
              f"been proved either way.")
        return 2
    if total:
        print(f"\nRESULT: {total} pixels differ — see diff-*.png in {a.outdir}")
        print("        Intended? Then this is your record of exactly what moved.")
    else:
        print("\nRESULT: PASS — identical to " + a.ref + " at every viewport")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
