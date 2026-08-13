#!/usr/bin/env python3
"""Take Manrope off the network, so a harness measures the page and not a race.

WHAT THIS IS FOR (GitHub #140, and CL#162 before it). `index.html` links Manrope
from fonts.googleapis.com, and its own #98 handler clears the `textWidth` memo
when `document.fonts.ready` settles. Engraving metrics are therefore measured
early, against whatever face happened to be resolved at that instant, and only
partly re-measured afterwards -- so the drawing depends on WHEN the font arrives
relative to the page's own first render. That instant comes off a third party's
network. **Any harness that loads the page without pinning the font is
nondeterministic by construction**, whatever it measures.

It is not theoretical: CL#159's pixel gate reported 195px and 2,016px in CI on a
build that measured 0px at every viewport locally -- four independent races per
check (two trees x two viewports), two of them landing on the far side of a clean
step function. `tools/pixel_regress.py` solved it; this module is that mechanism
lifted out of it verbatim in behaviour, so the other harnesses get the same fix
once rather than three subtly different ones.

THE MECHANISM, and the four traps inside it:

  1. PREFETCH BEFORE ANY BROWSER EXISTS. The stylesheet URL is read out of the
     HTML FILE (or, for a harness pointed at a server that is already up, over
     one plain HTTP GET of the page) and every face it references is pulled into
     this process. A URL discovered by watching the first navigation would mean
     the first navigation was the one that paid for it -- which is the race.

  2. A CHROME USER-AGENT ON THE PREFETCH. urllib's own UA gets served legacy TTF
     with no unicode-range subsetting: a different face with different metrics.
     Prefetching under Chrome's UA is what makes the bytes served back the bytes
     the browser would have fetched for itself.

  3. ONE STATE, CHOSEN ONCE PER RUN, ENFORCED EVERYWHERE. Every request to a font
     host is intercepted with CDP `Fetch` and either fulfilled from those
     prefetched bytes (a memory copy, not a fetch) or failed outright. Nothing
     reaches the network, so there is no latency left to vary. A URL the prefetch
     never saw is REFUSED rather than let through -- one un-pinned request is the
     whole race back again. A Google Fonts outage degrades to blocked-and-loud
     rather than failing the deploy for something that is not the deploy's fault.

  4. THE STATE IS VERIFIED AFTER EVERY RENDER, BY MEASURING. `document.fonts`
     cannot answer this and it is worth being blunt about why: with the
     stylesheet blocked, `document.fonts.status` is 'loaded' AND
     `document.fonts.check('600 13px Manrope')` is TRUE, because no `@font-face`
     was ever registered and `check` on a family it has never heard of trivially
     agrees. The only honest detector is a width probe -- one string laid out in
     "'Manrope',monospace" against the same string in "monospace" alone, which
     differ by 58px at 40px type when the webfont is really painting and by
     nothing at all when it is not (640.4 vs 698.4px at the size this module
     uses). See applied_js().

WHAT PINNING BUYS AND WHAT IT DOES NOT. It removes the network, and the state
check proves every render drew under the same typography. Neither makes a render
insensitive to WHEN the font arrives: held artificially at a uniform delay, every
render in a run agrees and the picture they agree on is the wrong one. A harness
that compares two renders needs a CONTROL on top of this (pixel_regress shoots
each tree until it agrees with itself); a harness that measures ABSOLUTES needs
either a repeat measurement or an honest note that its assertions do not depend
on type. Pinning is the floor, not the ceiling.

NOTHING TO PIN IS NOT A FAILURE. `/fidget/index.html` links no webfont at all,
which is exactly why it was the only CI check to pass both viewports. `decide()`
reports that as `expect == 'none'` and the probe agrees with it, so a harness
pointed at fidget is held to "no webfont, deliberately" rather than being failed
for the absence of a race it never had.

A NOTE ON SLEEPS. A paused request arrives UNSOLICITED, and the loop-until-my-id
`send` every harness here was written with silently discards anything that is not
its own reply -- so a font request paused in the middle of an `asyncio.sleep` is
never answered and the page hangs on its stylesheet forever. That is why
`attach()` exists: it returns a `send` that dispatches every message, and a
`pump` to use INSTEAD OF `asyncio.sleep` anywhere a navigation might still be in
flight. A plain sleep in the render path re-introduces the very latency this
module removes -- deterministically late is still late, and #98 fires on arrival.

Prefer a CONDITION to a sleep where the harness can take one (wait_ready()).
Note that CL#162 rejected MutationObserver quiescence for a good reason and it
still holds: `fidget/index.html` ends with `setInterval(draw, 250)`, an
unconditional repaint four times a second forever, so a quiet DOM is not merely
slow to reach there, it is UNREACHABLE.
"""

import asyncio
import base64
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request

# The hosts index.html reaches for Manrope. Named once: the interception
# patterns, the prefetch scan and the operator-facing messages all read them from
# here, so adding a third provider is one line and not four.
FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")

# Chrome asks Google Fonts for woff2 and unicode-range subsets; urllib's own
# User-Agent gets served legacy TTF with no subsetting, which is a different face
# with different metrics. See trap 2 in the module docstring.
PREFETCH_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# The stress knob, and the only reason it exists: this module CLAIMS the font
# cannot vary between renders, and a claim about a race is worth nothing unless
# the race can be re-run on demand. Set WOZI_FONT_DELAY_S=2.5 and every
# intercepted request is held for a random interval up to that long,
# INDEPENDENTLY -- a coin flip, not a uniform hold, because a uniform hold is the
# weaker model: every render lands on the same side of the step, they all agree,
# and a gate reports a confident PASS on the wrong picture. What turned CI red
# was some navigations paying a slow fetch and others not.
#
# WOZI_PX_FONT_DELAY_S is honoured too, because that is the name CL#162 shipped
# and a knob that silently stops working is worse than one with two names.
FONT_DELAY_S = float(os.environ.get("WOZI_FONT_DELAY_S")
                     or os.environ.get("WOZI_PX_FONT_DELAY_S") or 0)

# THE CEILING ON ONE CDP ROUND TRIP, shared by every harness that attaches through
# this module (GitHub #174). `attach`'s `send` waited on a 30s socket read inside
# `while not fut.done()`, which retries forever: a timeout that cannot expire. It
# is the same code `tools/pixel_regress.py` carries its own copy of, and that copy
# is what held a deploy runner for 93 minutes with no line in the log.
#
# What it does NOT cover is a socket that dies: `websockets` (15.0.1) keepalive
# turns that into ConnectionClosedError in 48-50s, measured by SIGSTOPping a
# headless Chrome. It terminates on its own — though as an unhandled traceback,
# which exits 1 rather than 2, and that is a separate defect of the same #156
# family. This deadline is for the case with nothing to catch: a Chrome that
# answers keepalive pings and never answers the method.
#
# It is deliberately far above any honest round trip, because `wait_until` above it
# owns the question "did the page get there in time" and this owns only "is the
# browser still talking at all". A deadline tight enough to argue with the first one
# would turn a slow-but-healthy run red, which is worse than no deadline. Measured:
# a healthy pixel_regress run passes with this squeezed to 2s, and passes at 2s
# again under a 6x CPU throttle, so 90 is 45x the worst round trip observed.
#
# THE EXIT CODE IS PART OF THE FIX. This is a library, so what it raises is what
# a11y_audit, dom_invariants, devices, escape_mesh, pill_clip and verify_motion
# return: `print(...)` then `raise SystemExit(2)`, never `SystemExit("string")`,
# which prints and exits 1 — "it measured and the answer is bad", the opposite of
# what a wedged browser means (GitHub #156).
CDP_TIMEOUT_S = float(os.environ.get("WOZI_CDP_TIMEOUT_S", "90") or 90)

# THE OTHER FAULT, AND IT IS NOT THE ONE ABOVE (GitHub #180). Two failures look
# alike from an operator's chair and are opposites on the wire, so they are kept
# apart deliberately and named separately in what they print:
#
#   * CDP_TIMEOUT_S is a Chrome that IS THERE and will not answer — it replies to
#     keepalive pings and never to the method. Nothing raises, so only a deadline
#     ends it.
#   * this is a socket that DIED. `websockets` (15.0.1) keepalive notices a dead
#     peer on its own and raises `ConnectionClosedError` — measured at 48-50s by
#     SIGSTOPping a headless Chrome, which is keepalive's own detection interval
#     and NOT something this catch tries to shorten. There is nothing to speed up
#     here: the fault is the exit code, not the duration.
#
# Because nothing caught it, that exception reached the top as a traceback and the
# process exited **1** — which across these harnesses means "it measured, and the
# artifact is wrong". A socket that died measured nothing, so 1 is a page verdict
# delivered by a run that never saw the page: the #156 confusion arriving by a
# route that sweep did not cover. CLAUDE.md records that CDP harnesses flake this
# way occasionally, so the normal intermittent infrastructure fault was reporting
# itself as a regression and sending the operator to look for a change that is not
# there.
#
# THE IMPORT IS GUARDED because this is a library and its callers should not be
# made to carry a dependency to be told about one. `except ()` is legal and never
# matches, so a `websockets` without the module simply keeps HEAD's behaviour
# rather than failing at import time.
try:
    from websockets.exceptions import ConnectionClosed as WS_CLOSED
except Exception:  # pragma: no cover - depends on the installed websockets
    WS_CLOSED = ()


def socket_died(what, err):
    """The socket closed mid-round-trip: exit 2, and say whose fault it is not.

    A library, so this code is what a11y_audit, devices, dom_invariants,
    escape_mesh, pill_clip and verify_motion return — `print(...)` then
    `raise SystemExit(2)`, never `SystemExit("string")`, which prints and exits 1
    (GitHub #156).
    """
    print(f"FATAL: the CDP socket closed during {what} — "
          f"{type(err).__name__}: {err}. The browser is GONE rather than wedged "
          f"(a wedged one is caught by CDP_TIMEOUT_S instead), so this is a "
          f"harness fault and not a verdict: nothing has been measured and "
          f"nothing about the page has been shown.")
    raise SystemExit(2)


# Installed at document-start, BEFORE the page's own #98 handler registers on the
# same promise -- callbacks on one promise run in registration order, so ours is
# always first. `__fontsReady` therefore means the font SETTLED and deliberately
# not that the page has finished reacting to it; what proves the latter is
# whatever settle the harness applies afterwards.
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
# REPORTED, AND DELIBERATELY NOT GATED ON, because they were tried as the gate
# and they do not discriminate. Measured, holding the font by hand:
#
#     font settled 310ms, first paint 53ms  -> the CORRECT picture
#     font settled 131ms, first paint 202ms -> 999 px away from it
#
# Anti-correlated, so neither an absolute budget on the arrival nor the obvious
# derived condition (arrived before first paint) separates the good regime from
# the bad one. They stay as diagnostics; what gets asserted is the STATE.
ARRIVAL_JS = "window.__tf+'/'+window.__fp"

# Returns 'ready', or a short string naming which term is still binding -- so a
# hang says whether it was the load event or the font promise, rather than
# timing out anonymously.
READY_JS = (
    "(()=>{"
    "if(document.readyState!=='complete')return 'load:'+document.readyState;"
    "if(!window.__fontsReady)return 'fonts.ready pending';"
    "if(!document.body)return 'no body';"
    "return 'ready';})()")


def applied_js(families):
    """Is the webfont ACTUALLY PAINTING? Not 'has it loaded' -- see trap 4 in the
    module docstring: `document.fonts.status` and `document.fonts.check` both
    answer yes with the stylesheet blocked, because a family nobody ever
    registered cannot be reported missing. So measure instead. The same string is
    laid out twice, once in "<family>,monospace" and once in "monospace" alone,
    and monospace is the sentinel precisely because no proportional webfont can
    accidentally match its metrics. Equal widths mean the family did not resolve.

    Returns a JS expression evaluating to 'applied', 'fallback', or 'none' when
    the page declares no webfont at all -- which /fidget/ does not, and which is
    not a fault to report.
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
    """The HTML file a given path under `root` actually serves, so the font scan
    reads the page under test rather than assuming index.html. A directory means
    its index.html, exactly as http.server resolves it."""
    p = os.path.join(root, path) if path else root
    if os.path.isdir(p):
        p = os.path.join(p, "index.html")
    return p if os.path.isfile(p) else None


def scan_font_urls(html_path):
    """Every stylesheet URL on a font host that the page links. Read off the FILE
    and not over HTTP, because this has to happen before any browser starts --
    see trap 1."""
    if not html_path:
        return []
    src = open(html_path, encoding="utf-8", errors="replace").read()
    return _scan(src)


def _scan(src):
    hosts = "|".join(re.escape(h) for h in FONT_HOSTS)
    return sorted(set(re.findall(r'https://(?:' + hosts + r')/[^"\'\s>)]+', src)))


def families_from_urls(urls):
    """The font-family names, read out of the stylesheet URL's own `family=`
    parameter rather than out of the stylesheet.

    It has to come from here and not from the CSS, because the probe is needed
    most in exactly the case where the CSS was never fetched: with the font
    blocked, a probe that does not know what family to look for cannot tell
    'correctly absent' from 'never asked'. That was a real hole in CL#162 --
    blocked mode reported a font-state mismatch on every render until the name
    came from the URL.

    Google's form is `css2?family=Manrope:wght@400;500;600;800`, so the name ends
    at the first colon and '+' is a space.
    """
    out = set()
    for u in urls:
        for m in re.findall(r"[?&]family=([^&]+)", u):
            out.add(urllib.parse.unquote_plus(m.split(":")[0]).strip())
    return {f for f in out if f}


def prefetch(urls):
    """Pull each font stylesheet and every face it references into this process,
    BEFORE a browser exists. Returns (cache, css_families, error).

    `cache` maps absolute URL -> (content-type, bytes) and is served back to
    Chrome by Fetch.fulfillRequest, so no measured navigation ever touches the
    network.

    The CSS declares many @font-face blocks (latin, latin-ext, cyrillic, ...) and
    Chrome fetches only the subsets it needs. All of them are cached anyway:
    which subset a given render asks for is exactly the sort of thing that must
    not vary between renders -- and it genuinely does vary, because a harness may
    override the User-Agent per profile (tools/devices.py drives 24 of them) and
    Google serves different subsets to different engines. Serving one prefetched
    stylesheet to every profile makes that one fact instead of 24.
    """
    cache, families = {}, set()
    for url in urls:
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


def urls_from_url(url, timeout=5):
    """The font stylesheet URLs a SERVED page links, over one plain HTTP GET.

    The file-on-disk scan is the better source and is what pixel_regress uses,
    because it starts its own servers and its ref tree does not exist yet when
    the decision has to be taken. The other three harnesses are the opposite
    case: they are POINTED AT a server somebody else already started, which may
    be serving a different worktree than the one this file lives in, so reading
    this repo's index.html would be reading the wrong page. One GET of the page
    itself is still before any browser exists, and it is not a font host -- the
    thing that must not be on the critical path of a measured navigation.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": PREFETCH_UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return _scan(r.read().decode("utf-8", "replace"))
    except Exception:
        return []


class FontPin:
    """One font state, decided once, enforced on every navigation and verified
    after every render.

    Construct it with `decide()` before any browser starts -- that ordering is
    the whole point, and a pin built after the first navigation is decoration.
    """

    def __init__(self, urls, families, cache, want, err):
        self.urls = urls
        self.families = families
        self.cache = cache
        self.err = err
        self.want = want
        self.mode = "pinned" if cache else "blocked"
        # What every render must report. Kept separate from `mode` because
        # 'none' is not a mode -- it is a page that declares no webfont, and
        # holding it to 'fallback' would fail /fidget/ for being itself.
        self.expect = "none" if not urls else (
            "applied" if self.mode == "pinned" else "fallback")
        self.states = {}

    # ---- construction ------------------------------------------------------

    @classmethod
    def decide(cls, want="auto", html_path=None, url=None):
        """Choose the state for the whole run. `want` is 'auto', 'pinned' or
        'blocked'; `html_path` is preferred and `url` is the fallback source for
        the stylesheet URLs (see urls_from_url).

        'auto' is the default everywhere because it is the only one of the three
        that is deterministic AND never fails a run for something that is not the
        run's fault: the decision is taken once, before a browser exists, and
        every render is then held to it and checked against it. A run that
        degrades to blocked says so on its own first line.
        """
        urls = scan_font_urls(html_path) if html_path else []
        if not urls and url:
            urls = urls_from_url(url)
        families = families_from_urls(urls)
        cache, err = {}, None
        if urls and want != "blocked":
            cache, _css_families, err = prefetch(urls)
        return cls(urls, families, cache, want, err)

    def announce(self):
        """The one line that says which state this run is in. Returns None, or a
        fatal message when the caller asked for 'pinned' and it could not be had
        -- refusing is the right answer there, because the alternative is a
        measurement whose typography came off a third party's network."""
        if not self.urls:
            print("fonts: the page links no webfont — nothing to pin, and nothing "
                  "that can race")
            return None
        if self.mode == "pinned":
            print(f"fonts: PINNED — {len(self.cache)} object(s) prefetched, served "
                  f"from memory, family "
                  f"{sorted(self.families)[0] if self.families else '?'}"
                  + (f"   [FONT_DELAY_S={FONT_DELAY_S} — requests held on a coin "
                     f"flip, on purpose]" if FONT_DELAY_S else ""))
            return None
        if self.want == "pinned":
            return (f"FATAL: --fonts pinned could not prefetch the webfont "
                    f"({self.err}). Refusing to measure: the alternative is a "
                    f"measurement whose typography came off a third party's "
                    f"network. Re-run with --fonts blocked to measure without it, "
                    f"knowing that real typography is then not exercised.")
        why = f"could not prefetch ({self.err})" if self.err else "requested"
        print(f"fonts: BLOCKED — {why}. Every render draws in the FALLBACK stack, "
              f"so this run does not exercise the shipped typography; it is still "
              f"a valid run, because every render is held to the same state.")
        return None

    # ---- enforcement -------------------------------------------------------

    @property
    def patterns(self):
        return [{"urlPattern": f"https://{h}/*"} for h in FONT_HOSTS]

    async def install(self, send):
        """Arm the interception and the arrival observer. Must be called before
        the first navigation, and after Page.enable -- without Page.enable the
        injected script is accepted and silently never runs, which reads exactly
        like an injection that does not work."""
        await send("Fetch.enable", {"patterns": self.patterns})
        await send("Page.addScriptToEvaluateOnNewDocument", {"source": OBSERVE_JS})

    async def answer(self, ev, raw):
        """Answer one paused request, identically for every request on a font
        host. `blocked` fails it immediately, so 'no webfont' is true from the
        first byte with no timing in it at all; `pinned` fulfils it from the
        prefetched bytes, which is a memory copy and not a fetch.

        `cache-control: no-store` on the fulfilment is deliberate: a harness that
        navigates repeatedly in one tab (devices.py does 24 times) would
        otherwise have its first profile pay the interception and the rest read a
        memory cache, so only one of the 24 would actually be verified against
        the state this run chose.
        """
        rid = ev["requestId"]
        if FONT_DELAY_S and random.random() < 0.5:
            await asyncio.sleep(FONT_DELAY_S)
        hit = self.cache.get(ev["request"]["url"]) if self.mode == "pinned" else None
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

    # ---- verification ------------------------------------------------------

    async def state(self, send, label=None):
        """Measure which face is really painting, right now, in this page. Record
        it under `label` so a run can report every render's state at the end.

        Take this AFTER whatever settle the harness applies, never before: the
        probe appends a span and removes it, which is a DOM mutation, and a
        harness whose settle watches the DOM would be invalidated by its own
        instrument.
        """
        r = await send("Runtime.evaluate", {"expression": applied_js(self.families),
                                            "returnByValue": True})
        got = r.get("result", {}).get("value", "unreadable")
        if label is not None:
            self.states[label] = got
        return got

    async def arrival(self, send):
        """`fonts.ready`/first-paint in ms, as a diagnostic string. See ARRIVAL_JS
        for why neither number is ever asserted on."""
        r = await send("Runtime.evaluate", {"expression": ARRIVAL_JS,
                                            "returnByValue": True})
        return r.get("result", {}).get("value", -1)

    def mismatches(self):
        """Every render whose measured state was not the one this run chose. A
        non-empty list means the pin LEAKED -- a request reached the network, or
        the page changed provider and the scan missed it -- and whatever was
        measured under it has not been shown to be about the code."""
        return {k: v for k, v in self.states.items() if v != self.expect}

    def report(self):
        """One line per run summarising the state every render was held to, and
        the complaint if they were not all the same. Returns True when the run's
        typography is trustworthy."""
        bad = self.mismatches()
        if not self.states:
            print("fonts: NOT VERIFIED — no render reported a font state; the pin "
                  "was armed and never checked, which proves nothing")
            return False
        if bad:
            print(f"fonts: MISMATCH — {len(bad)} of {len(self.states)} render(s) did "
                  f"not draw in the state this run chose ({self.expect!r}):")
            for k, v in sorted(bad.items())[:10]:
                print(f"   {str(k):<28} measured {v!r}")
            print("   The pin leaked. Nothing measured above is a statement about "
                  "the code.")
            return False
        print(f"fonts: every render verified {self.expect!r} "
              f"({len(self.states)} render(s), {self.mode})")
        return True


def attach(ws, pin, on_message=None):
    """Wrap a websocket in a CDP session that DISPATCHES every message.

    Returns (send, pump, wait_until).

    This exists because of one deadlock, and it is worth stating plainly. Every
    harness here was written with a `send` that loops on `ws.recv()` until it sees
    its own id and throws everything else away. That is fine while nothing else
    needs a response -- and `Fetch.requestPaused` arrives UNSOLICITED and MUST be
    answered, or the page it belongs to hangs on its stylesheet until the
    harness's own timeout. So:

      * `send(method, params)` resolves its own reply and answers anything else.
      * `pump(seconds)` is the replacement for `asyncio.sleep` anywhere a
        navigation may still be in flight. A plain sleep there does not merely
        risk a hang: it holds the stylesheet for the whole sleep and lets it
        arrive afterwards, which is the LATE-FONT regime the pin exists to
        remove. Deterministically late is still late.
      * `wait_until(expr, want, timeout, what)` polls an in-page expression while
        pumping, so a condition can be waited for instead of a duration guessed.

    `on_message` is called with every raw message, for harnesses that watch the
    protocol for their own reasons (dom_invariants collects console errors and
    exceptions this way, and must go on doing so).
    """
    mid = 0
    waiting = {}

    async def wire(payload, what):
        """One outbound frame. See socket_died: a closed socket must not leave as
        a traceback, because a traceback is exit 1 (GitHub #180)."""
        try:
            await ws.send(payload)
        except WS_CLOSED as e:
            socket_died(what, e)

    async def raw(method, params=None):
        nonlocal mid
        mid += 1
        await wire(json.dumps({"id": mid, "method": method, "params": params or {}}),
                   f"{method} (unsolicited)")

    async def dispatch(msg):
        if on_message:
            on_message(msg)
        if msg.get("id") in waiting:
            waiting.pop(msg["id"]).set_result(msg.get("result", {}))
        elif msg.get("method") == "Fetch.requestPaused" and pin is not None:
            await pin.answer(msg["params"], raw)

    async def pump_once(timeout, what="a background message"):
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
        except asyncio.TimeoutError:
            return
        except WS_CLOSED as e:
            socket_died(what, e)
        await dispatch(msg)

    async def send(method, params=None):
        """One CDP round trip, with a DEADLINE — see CDP_TIMEOUT_S (GitHub #174).

        The id is captured into a local because `pump_once` answers paused font
        requests through `raw`, which increments `mid` as well, so the reply this
        call is waiting for cannot be identified by re-reading it.

        A socket that dies under this call is the OTHER fault and exits 2 by a
        different sentence — see socket_died (GitHub #180).
        """
        nonlocal mid
        mid += 1
        my = mid
        fut = asyncio.get_event_loop().create_future()
        waiting[my] = fut
        await wire(json.dumps({"id": my, "method": method, "params": params or {}}),
                   method)
        end = time.monotonic() + CDP_TIMEOUT_S
        while not fut.done():
            left = end - time.monotonic()
            if left <= 0:
                waiting.pop(my, None)
                print(f"FATAL: Chrome never answered {method} — no reply in "
                      f"{CDP_TIMEOUT_S:g}s, with {len(waiting)} other call(s) "
                      f"outstanding. The browser is wedged rather than gone (a "
                      f"closed socket raises instead), so nothing has been "
                      f"measured and nothing has been proved.")
                raise SystemExit(2)
            await pump_once(min(1.0, left), method)
        return fut.result()

    async def pump(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            await pump_once(min(0.05, max(0.005, end - time.monotonic())))

    async def wait_until(expr, want, timeout, what):
        """Poll until `expr` returns `want`, pumping in between. Returns the last
        value seen; raises SystemExit naming the binding term if it never does,
        because a page that never became ready has not been measured and saying
        so is the whole point.

        AND IT MUST SAY SO IN THE EXIT CODE TOO, not only in the sentence
        (GitHub #156). `SystemExit("some string")` prints the string and exits
        **1** — which in both callers means "it measured, and the artifact is
        wrong", the opposite of what the message says. This is a library, so the
        code it raises is the code `a11y_audit` and `dom_invariants` return, and
        both document 2 as "unobtainable"."""
        end = time.monotonic() + timeout
        last = "never evaluated"
        while time.monotonic() < end:
            r = await send("Runtime.evaluate", {"expression": expr,
                                                "returnByValue": True})
            last = r.get("result", {}).get("value", last)
            if last == want:
                return last
            await pump(0.05)
        print(f"FATAL: {what} timed out after {timeout}s (last: {last!r}) "
              f"-- nothing has been measured, so nothing has been proved")
        raise SystemExit(2)

    return send, pump, wait_until


async def wait_ready(send, pump, wait_until, timeout=25.0, what="the page"):
    """The load condition every harness here can share: document complete, and
    `document.fonts.ready` settled. That is a CONDITION, not a duration, and it
    replaces the fixed multi-second sleeps these harnesses were written with --
    which were tuned to a network that is no longer in the path at all.

    It is deliberately NOT the whole readiness question. What it cannot know is
    when a given harness's own measurement has settled: pixel_regress waits for
    two byte-identical screenshots, devices.py polls until two reads of the
    geometry agree, and both of those are stronger than anything stated here.
    This is the floor they sit on.
    """
    return await wait_until(READY_JS, "ready", timeout, f"{what} never finished loading")
