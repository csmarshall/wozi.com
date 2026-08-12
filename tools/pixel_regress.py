#!/usr/bin/env python3
"""Photograph the page deterministically, and diff this working tree against a
git ref pixel for pixel.

    tools/pixel_regress.py                  # working tree vs HEAD
    tools/pixel_regress.py --ref origin/main
    tools/pixel_regress.py --shot /tmp/x.png # just capture, no comparison
    tools/pixel_regress.py --query '?who=charles'   # one chain, not the stage
    tools/pixel_regress.py --path fidget/   # a different page in the same tree

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
pair. So the guard is not a model of the mechanism at all. IT IS A CONTROL: the
working tree is photographed TWICE, once before the ref pass and once after, and
while those two disagree no pixel count from the run is reported as a verdict
about the ref. That is what the gate was missing. Every other guard here refuses
one named mechanism, and the fault that got through was a mechanism nobody had
named yet; a control refuses all of them, including the next one. Verified
against a coin-flip reproduction of the original fault -- half the navigations
paying a slow fetch, half not -- where it reports HARNESS NOT REPEATABLE and 383
or 999 px, instead of the artifact verdict CI printed.

And with the font off the network there is nothing left to sleep for, so the
fixed four seconds is gone. Readiness is a CONDITION: document load complete,
document.fonts.ready settled, and then two screenshots STABLE_SAMPLE_MS apart
that come back byte-identical. The settle is deliberately in pixels rather than
in DOM mutations -- see STABLE_SAMPLE_MS for the page that makes a quiet-DOM
test impossible -- and it catches the #98 re-render whenever it lands rather
than waiting it out. It is also about four times faster.

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
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import websockets

CHROME = (os.environ.get("CHROME")
          or shutil.which("google-chrome") or shutil.which("chromium-browser")
          or shutil.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if sys.platform == "darwin" else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The two hosts index.html reaches for Manrope. Named once; the interception
# patterns, the prefetch scan and the operator-facing messages all read them
# from here, so adding a third provider is one line and not four.
FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")

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
# Chrome asks Google Fonts for woff2 and unicode-range subsets; urllib's own
# User-Agent gets served legacy TTF with no subsetting, which is a different
# face with different metrics. Prefetching under Chrome's UA is what makes the
# bytes this harness serves the bytes the browser would have fetched itself.
PREFETCH_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# The stress knob, and the only reason it exists: this file now CLAIMS that the
# font cannot vary between the two trees, and a claim about a race is worth
# nothing unless the race can be re-run on demand. Set
# WOZI_PX_FONT_DELAY_S=2.5 and every intercepted font request is held for a
# random interval up to that long, independently -- the exact asymmetry that
# turned CI red. The gate must still report 0 px and the same font state on both
# trees under it. It is off unless the variable is set, it is announced when it
# is on, and no gate ever sets it.
FONT_DELAY_S = float(os.environ.get("WOZI_PX_FONT_DELAY_S", "0") or 0)


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


# Installed alongside determinism_js. This hooks document.fonts.ready at
# document-start, BEFORE the page's own #98 handler registers on the same promise
# -- so `__fontsReady` going true means the font settled, and deliberately NOT
# that the page has finished reacting to it. Callbacks on one promise run in
# registration order, so ours is always first; what proves the page has finished
# reacting is the pixel settle, not this flag.
OBSERVE_JS = (
    "(()=>{window.__fontsReady=false;window.__t0=Date.now();window.__tf=-1;"
    "window.__fp=-1;"
    "try{new PerformanceObserver((l)=>{for(const e of l.getEntries()){"
    "if(window.__fp<0)window.__fp=Date.now()-window.__t0;}})"
    ".observe({type:'paint',buffered:true})}catch(e){}"
    "try{document.fonts.ready.then(()=>{window.__tf=Date.now()-window.__t0;"
    "window.__fontsReady=true})}"
    "catch(e){window.__fontsReady=true}})()")

# Milliseconds from document-start to document.fonts.ready, and to first paint.
# REPORTED, AND DELIBERATELY NOT GATED ON, because they were tried as the gate and
# they do not discriminate. Measured, holding the font by hand:
#
#     font settled 310ms, first paint 53ms  -> the CORRECT picture
#     font settled 131ms, first paint 202ms -> 999 px away from it
#
# Anti-correlated, so neither an absolute budget on the arrival nor the obvious
# derived condition (arrived before first paint) separates the good regime from
# the bad one. Whatever the page's memoised engraving metrics are really racing,
# it is not an event either of these two names. So they stay in the output as
# diagnostics -- worth seeing when something goes wrong -- and the thing actually
# asserted is repeatability, in pixels, which needs no model of the page at all.
ARRIVAL_JS = "window.__tf+'/'+window.__fp"

# Returns 'ready', or a short string naming which term is still binding -- which
# is what gets printed if READY_TIMEOUT_S is reached, so a hang says whether it
# was the load event, the font promise or the picture.
READY_JS = (
    "(()=>{"
    "if(document.readyState!=='complete')return 'load:'+document.readyState;"
    "if(!window.__fontsReady)return 'fonts.ready pending';"
    "if(!document.body)return 'no body';"
    "return 'ready';})()")


def applied_js(families):
    """Is the webfont ACTUALLY PAINTING? Not 'has it loaded' -- see the module
    docstring: document.fonts.status and document.fonts.check both answer 'yes'
    with the stylesheet blocked, because a family nobody ever registered cannot
    be reported missing. So measure instead. The same string is laid out twice,
    once in "<family>,monospace" and once in "monospace" alone, and monospace is
    chosen as the sentinel precisely because no proportional webfont can
    accidentally match its metrics. Equal widths mean the family did not resolve.

    Returns 'applied', 'fallback', or 'none' when the page declares no webfont at
    all -- which /fidget/ does not, and that is not a fault to report.
    """
    if not families:
        return "'none'"
    probe = json.dumps("'%s',monospace" % sorted(families)[0].replace("'", ""))
    return (
        "(()=>{if(!document.body)return 'no body';"
        "const mk=(f)=>{const s=document.createElement('span');"
        "s.style.cssText='position:absolute;left:-9999px;top:0;white-space:pre;"
        "font:600 40px '+f;"
        "s.textContent='Handgloves 0123456789';document.body.appendChild(s);"
        "const w=s.getBoundingClientRect().width;s.remove();return w;};"
        f"const a=mk({probe});const b=mk('monospace');"
        "return Math.abs(a-b)>0.5?'applied':'fallback';})()")


def page_source(root, path):
    """The HTML file a given --path actually serves, so the font scan reads the
    page under test rather than assuming index.html. A directory means its
    index.html, exactly as http.server resolves it."""
    p = os.path.join(root, path) if path else root
    if os.path.isdir(p):
        p = os.path.join(p, "index.html")
    return p if os.path.isfile(p) else None


def scan_font_urls(html_path):
    """Every stylesheet URL on a font host that the page links. Read off the
    FILE and not over HTTP, because this has to happen before any browser
    starts -- a URL discovered by watching the first navigation would mean the
    first navigation was the one that paid for it, which is the race."""
    if not html_path:
        return []
    src = open(html_path, encoding="utf-8", errors="replace").read()
    hosts = "|".join(re.escape(h) for h in FONT_HOSTS)
    return sorted(set(re.findall(r'https://(?:' + hosts + r')/[^"\'\s>)]+', src)))


def families_from_urls(urls):
    """The font-family names, read out of the stylesheet URL's own `family=`
    parameter rather than out of the stylesheet.

    It has to come from here and not from the CSS, because the probe is needed
    most in exactly the case where the CSS was never fetched: with the font
    blocked, a probe that does not know what family to look for returns 'no
    webfont declared' and the run then cannot tell 'correctly absent' from 'never
    asked'. That was a real hole -- --fonts blocked reported a font-state
    mismatch on every render until the name came from the URL.

    Google's form is `css2?family=Manrope:wght@400;500;600;800`, so the name ends
    at the first colon and '+' is a space.
    """
    out = set()
    for u in urls:
        for m in re.findall(r"[?&]family=([^&]+)", u):
            out.add(urllib.parse.unquote_plus(m.split(":")[0]).strip())
    return {f for f in out if f}


def prefetch_fonts(html_path):
    """Pull the font CSS and every face it references into this process, BEFORE a
    browser exists. Returns (cache, families, error).

    `cache` maps absolute URL -> (content-type, bytes) and is served back to
    Chrome by Fetch.fulfillRequest, so no measured navigation ever touches the
    network. `families` is the font-family names the CSS declares, which is where
    the applied-probe gets its name from rather than hardcoding 'Manrope' -- one
    home for that fact, and it stays right if the page changes provider.

    The CSS declares many @font-face blocks (latin, latin-ext, cyrillic, ...) and
    Chrome fetches only the subsets it needs. All of them are cached anyway:
    which subset a given render asks for is exactly the sort of thing that must
    not vary between the two trees.
    """
    cache, families = {}, set()
    for url in scan_font_urls(html_path):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": PREFETCH_UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                css = r.read()
                cache[url] = (r.headers.get("Content-Type", "text/css"), css)
        except Exception as e:
            return {}, set(), f"{url}: {e}"
        text = css.decode("utf-8", "replace")
        families.update(m.strip().strip('"\'')
                        for m in re.findall(r"font-family:\s*([^;]+);", text))
        for face in sorted(set(re.findall(r"url\((https://[^)]+)\)", text))):
            try:
                req = urllib.request.Request(face, headers={"User-Agent": PREFETCH_UA})
                with urllib.request.urlopen(req, timeout=15) as r:
                    cache[face] = (r.headers.get("Content-Type", "font/woff2"), r.read())
            except Exception as e:
                return {}, set(), f"{face}: {e}"
    return cache, families, None


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
    raise SystemExit(f"FATAL: could not serve {directory}")


async def shoot(url, viewports, seed, frames, theme, fonts, cache, families):
    """One browser, every viewport. Returns ({label: png}, {label: font state}).

    `fonts` is 'pinned' or 'blocked' and is decided once by main() for the whole
    run, so both trees are photographed under the same typography by
    construction rather than by both happening to win the same race.
    """
    port = free_port()
    profile = tempfile.mkdtemp(prefix="wozi-px-")
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
        raise SystemExit("FATAL: no DevTools endpoint")

    out, states, arrivals = {}, {}, {}
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

        async def raw(m, p=None):
            nonlocal mid
            mid += 1
            await c.send(json.dumps({"id": mid, "method": m, "params": p or {}}))

        async def pump_once(timeout):
            try:
                msg = json.loads(await asyncio.wait_for(c.recv(), timeout=timeout))
            except asyncio.TimeoutError:
                return
            if msg.get("id") in waiting:
                waiting.pop(msg["id"]).set_result(msg.get("result", {}))
            elif msg.get("method") == "Fetch.requestPaused":
                paused.append(msg["params"])
                await answer(msg["params"])

        async def answer(ev):
            """One of two states, chosen for the whole run, applied identically to
            every request on a font host. `blocked` fails it immediately, so
            'no webfont' is true from the first byte with no timing in it at all;
            `pinned` fulfils it from the prefetched bytes, which is a memory copy
            and not a fetch. Anything not in the cache is a URL the prefetch scan
            never saw, and it is refused rather than let through to the network --
            a single un-pinned request is the whole race back again."""
            rid = ev["requestId"]
            # A COIN FLIP, not a uniform delay, because that is what the fault was.
            # A uniform hold is the weaker model and it is misleading: every render
            # in the run lands on the same side of the step, all three passes agree,
            # and the gate reports a confident PASS on a picture 999 px from the
            # right one. What turned CI red was some navigations paying a slow fetch
            # and others not, so that is what this reproduces.
            if FONT_DELAY_S and random.random() < 0.5:
                await asyncio.sleep(FONT_DELAY_S)
            hit = cache.get(ev["request"]["url"]) if fonts == "pinned" else None
            if hit:
                await raw("Fetch.fulfillRequest",
                          {"requestId": rid, "responseCode": 200,
                           "responseHeaders": [
                               {"name": "content-type", "value": hit[0]},
                               {"name": "access-control-allow-origin", "value": "*"},
                               {"name": "cache-control", "value": "no-store"}],
                           "body": base64.b64encode(hit[1]).decode()})
            else:
                await raw("Fetch.failRequest",
                          {"requestId": rid, "errorReason": "BlockedByClient"})

        async def send(m, p=None):
            nonlocal mid
            mid += 1
            fut = asyncio.get_event_loop().create_future()
            waiting[mid] = fut
            await c.send(json.dumps({"id": mid, "method": m, "params": p or {}}))
            while not fut.done():
                await pump_once(30.0)
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
            raise SystemExit(f"FATAL: {what} timed out after {timeout}s "
                             f"(last: {last!r}) -- nothing has been photographed, "
                             f"so nothing has been proved")

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Fetch.enable",
                   {"patterns": [{"urlPattern": f"https://{h}/*"} for h in FONT_HOSTS]})
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
            raise SystemExit(
                f"FATAL: {label} never stopped changing — two screenshots "
                f"{STABLE_SAMPLE_MS}ms apart still differ after {timeout}s. Nothing "
                f"has been photographed, so nothing has been proved.")

        probe = applied_js(families)
        for w, hgt in viewports:
            label = f"{w}x{hgt}"
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": w, "height": hgt, "deviceScaleFactor": 1,
                        "mobile": False})
            await send("Page.navigate", {"url": url})
            await wait_until(READY_JS, "ready", READY_TIMEOUT_S,
                            f"{label} never finished loading")
            await settle(label, READY_TIMEOUT_S)
            # Read the font state BEFORE pumping frames: the probe appends a span
            # and removes it, which is a DOM mutation, and taking it while the
            # quiescence condition still matters would invalidate the thing that
            # was just waited for.
            r = await send("Runtime.evaluate", {"expression": probe, "returnByValue": True})
            states[label] = r.get("result", {}).get("value", "unreadable")
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
    return out, states, arrivals


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
    # Both trees are the same page modulo comments, so the working tree's own copy
    # is the right place to read the font URLs from; the ref worktree does not
    # exist yet and must not be what decides how the FIRST tree is photographed.
    src = page_source(ROOT, a.path)
    urls = scan_font_urls(src)
    # The family name is derived from the URL, never from the prefetch, so the
    # probe knows what to look for in every mode -- including the one where
    # nothing was fetched. See families_from_urls().
    families = families_from_urls(urls)
    cache, err = {}, None
    if urls and a.fonts != "blocked":
        cache, _css_families, err = prefetch_fonts(src)
    mode = "pinned" if cache else "blocked"
    if not urls:
        print(f"fonts: /{a.path or ''} links no webfont — nothing to pin, "
              f"and nothing that can race")
        expect = "none"
    elif mode == "pinned":
        print(f"fonts: PINNED — {len(cache)} object(s) prefetched, served from memory, "
              f"family {sorted(families)[0] if families else '?'}")
        expect = "applied"
    else:
        if a.fonts == "pinned":
            print(f"FATAL: --fonts pinned could not prefetch the webfont ({err}). "
                  f"Refusing to photograph: the alternative is a comparison whose "
                  f"typography came off a third party's network. Re-run with "
                  f"--fonts blocked to compare without it, knowing that real "
                  f"typography is then not exercised.")
            return 2
        why = f"could not prefetch ({err})" if err else "requested"
        print(f"fonts: BLOCKED — {why}. Both trees draw in the FALLBACK stack, so "
              f"this run does not exercise real typography; it is still a valid "
              f"comparison, because both sides are held to the same state.")
        expect = "fallback"

    srv, base = serve(ROOT)
    try:
        now, now_fonts, now_ms = asyncio.run(shoot(base + a.path + a.query, vps, a.seed,
                                                   a.frames, a.theme, mode, cache, families))
    finally:
        srv.kill()

    if a.shot:
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

    work = tempfile.mkdtemp(prefix="wozi-ref-")
    tree = os.path.join(work, "t")
    r = subprocess.run(["git", "-C", ROOT, "worktree", "add", "--detach", tree, a.ref],
                       capture_output=True, text=True)
    if r.returncode:
        print("FATAL: could not check out " + a.ref + "\n" + r.stderr.strip())
        return 2
    try:
        srv2, base2 = serve(tree)
        try:
            ref, ref_fonts, ref_ms = asyncio.run(shoot(base2 + a.path + a.query, vps, a.seed,
                                                       a.frames, a.theme, mode, cache, families))
        finally:
            srv2.kill()
    finally:
        subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", tree],
                       capture_output=True)
        shutil.rmtree(work, ignore_errors=True)

    # ---- THE CONTROL: the same tree, photographed a second time ---------------
    # Deliberately AFTER the ref pass rather than back-to-back with the first, so
    # the two samples of one tree straddle the ref's in time and catch drift
    # across the run rather than only within a burst.
    #
    # This is the check the gate did not have, and its absence is why the original
    # failure was reported as an artifact fault. Every guard above is specific to a
    # mechanism -- the seed, the clock, the font state -- and a guard can only
    # refuse the fault it was written for. This one asks the question none of them
    # do and that subsumes all of them: given the SAME bytes twice, does this
    # machine draw the same picture? While the answer is no, no pixel count from
    # this run means anything at all, whatever caused it -- a font, a GPU, a
    # thermal throttle, a mechanism nobody has thought of yet. It costs one extra
    # pass, which the condition-based settle has already more than paid for.
    srv3, base3 = serve(ROOT)
    try:
        again, again_fonts, again_ms = asyncio.run(shoot(base3 + a.path + a.query, vps,
                                                        a.seed, a.frames, a.theme,
                                                        mode, cache, families))
    finally:
        srv3.kill()

    print(f"\nworking tree vs {a.ref}   seed {a.seed}, {a.frames} frames, "
          f"{a.theme} theme, /{a.path}{a.query}, "
          f"fonts {'n/a — none linked' if expect == 'none' else mode}")

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
