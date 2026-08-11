#!/usr/bin/env python3
"""How long does this page spend PARSING and COMPILING itself, and on what?

    tools/parse_cost.py                         # 1x, 4x, 6x CPU at 1440x900
    tools/parse_cost.py --runs 7 --throttle 1 --throttle 20
    tools/parse_cost.py --encoding identity     # uncompressed, for comparison
    tools/parse_cost.py --query '?who=charles'  --viewport 390x844
    tools/parse_cost.py --json /tmp/parse.json  # every run, unrounded
    tools/parse_cost.py --root /tmp/stripped    # the comment-stripped counterfactual

WHY THIS EXISTS. GitHub #113 asked how to optimise a 600 KB index.html, and the
first honest answer was that nobody had measured what the size actually costs.
The wire cost is already known and small -- CloudFront serves the file gzipped,
so 588 KB on disk is 209 KB on the wire -- and the frame budget is known to be
fine, because `?hud` reports 30 ticks/s with no dropped ticks. The one cost in
that ticket with no number against it is the one this measures: the time between
the first byte arriving and the page being on screen, and how much of it is the
browser reading and compiling the document rather than drawing it.

WHAT IT REPORTS, and why each number is here rather than another:

  * DOMContentLoaded / load, from the navigation timing entry, which is the same
    clock a browser's own devtools reports and is measured from navigation start.
  * First Contentful Paint, from the paint timeline -- the first moment the
    visitor sees anything at all that is not the background.
  * Largest Contentful Paint, from a PerformanceObserver planted before any page
    script runs. `getEntriesByType` cannot be trusted for LCP: entries are
    delivered to observers and only *buffered* for one, so a poll after load can
    legitimately come back empty on a page whose largest element settled early.
  * Long tasks -- count and total. A parse problem shows up here first: main
    thread blocked in one 400ms lump is a stall a visitor feels, where the same
    400ms spread over twenty tasks is not.
  * The trace's own breakdown of where that time went, by SELF time. This is the
    part that answers #113 directly, and self time is the only aggregate that
    can: `ParseHTML` events nest `EvaluateScript` events which nest `v8.compile`
    events, so summing inclusive durations counts the same milliseconds three
    times and makes every phase look like the culprit.

WHAT THE FILE'S SHAPE MEANS FOR THE ANSWER. 568 KB of index.html's 588 KB sits
inside `<script type="text/x-dc" data-dc-script>`. That is not a JavaScript MIME
type, so the HTML parser treats the block as raw text and V8 never sees it during
document parse. It is compiled later, by `new Function` inside support.js
(`evalDcLogic`), which is a *runtime* cost on the main thread and appears in the
trace as compilation with no script URL. Whether that lands as parse cost or as
execution cost is exactly the question, so both are reported separately and the
anonymous compiles are called out by name.

METHOD, and the two ways this harness deliberately differs from its siblings:

  * It serves the tree through a gzip-encoding server rather than
    `python3 -m http.server`, because the live distribution compresses and a
    measurement of the uncompressed file is a measurement of a page nobody is
    served. `--encoding identity` asks the other question on purpose.
  * It seeds an LCG over Math.random through
    `Page.addScriptToEvaluateOnNewDocument`, as every harness here does and for
    the reason CLAUDE.md gives -- a gate that deals through the page's own
    `?seed` cannot see a fault in the dealing. But it does NOT freeze
    requestAnimationFrame or pin performance.now the way pixel_regress.py does.
    Those exist to stop the clock so a screenshot is reproducible, and stopping
    the clock is precisely what destroys this measurement.

WHAT LCP IS AND IS NOT, HERE. The largest contentful paint on this page is a TEXT
element, every time, because SVG is not an LCP candidate -- so LCP lands within a
few milliseconds of FCP and NEITHER of them is the moment the gear train appears.
The train's arrival is the `FunctionCall react.production.min.js` line in the
per-script table, which is React rendering the whole composition in one task, and
it is the largest single number this harness reports. Read LCP as "the page has
text on it", not as "the machine is on screen".

Cache is disabled for every run, so every run is a cold one: no HTTP cache and,
more to the point, no V8 code cache, which is the state a first-time visitor and
a hard reload are both in. Runs are repeated and the MEDIAN reported, because the
first navigation into a fresh renderer pays for warming the process and is not
representative of anything.

Exit 0 if it measured, 2 if it could not get a browser or a trace.
"""

import argparse
import functools
import gzip
import http.server
import json
import os
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import asyncio

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

# The trace categories that carry the phase breakdown. "-*" first, so nothing
# arrives except what is asked for -- a full trace of a page this size is tens of
# megabytes over the websocket and most of it is thread metadata.
TRACE_CATEGORIES = [
    "-*",
    "devtools.timeline",
    "disabled-by-default-devtools.timeline",
    "v8",
    "v8.execute",
    "disabled-by-default-v8.compile",
    "blink.user_timing",
    "blink",
    "cc",
    "loading",
    "toplevel",
]

# Everything the browser does to a document, grouped the way a reader of #113
# would want it grouped rather than the way the trace names it. Order is the
# order it is printed in.
PHASES: "list[tuple[str, tuple[str, ...]]]" = [
    # TextResourceDecoder is the gunzip-and-UTF-8 step, which is genuinely a cost
    # of the document's SIZE and belongs with parsing rather than with networking.
    ("HTML parse", ("ParseHTML", "ParseAuthorStyleSheet", "HTMLDocumentParser*",
                    "TextResourceDecoder*", "CSSParser*")),
    # V8.Compile*, V8.PreParse and the Maglev/TurboFan tiers are all "turning
    # source into code", which is the cost #113 is really asking about, so they
    # are one bucket. A trailing * is a prefix match -- the JIT tiers carry a
    # dozen sub-phase names that would otherwise need enumerating and would
    # silently fall into "other" the next time V8 renames one.
    ("script compile", ("v8.compile", "v8.compileModule", "v8.parseOnBackground",
                        "V8.Compile*", "V8.PreParse*", "V8.ScriptCompiler*",
                        "V8.Maglev*", "V8.TurboFan*", "V8.Optimize*",
                        "V8.Parse*", "V8.RunMicrotasks.Compile*")),
    ("script execute", ("EvaluateScript", "v8.run", "FunctionCall",
                        "V8.Execute", "RunMicrotasks", "TimerFire",
                        "EventDispatch", "XHRReadyStateChange")),
    ("style + layout", ("UpdateLayoutTree", "Layout*", "ScheduleStyleRecalculation",
                        "InvalidateLayout", "Document::recalcStyle",
                        "Document::updateStyle*", "StyleEngine*",
                        "LocalFrameView*")),
    ("paint + composite", ("Paint", "PrePaint", "PaintImage", "Commit",
                          "CompositeLayers", "UpdateLayer", "UpdateLayerTree",
                          "RasterTask", "Layerize", "GpuRasterBuffer*",
                          "RasterBufferProvider*", "Picture*", "cc::*",
                          "DisplayItemList*")),
    ("garbage collection", ("MinorGC", "MajorGC", "BlinkGC*", "V8.GC*")),
    # Not the page's cost at all: the scheduler's own task wrappers, IPC to the
    # browser process, and GPU-process work. Broken out rather than left in
    # "other", because "other" has to stay small enough that anything appearing
    # in it is worth chasing.
    ("scheduler / IPC / GPU", ("ThreadControllerImpl::RunTask", "RunTask",
                               "ThreadPool_RunTask", "SequenceManager*",
                               "Receive mojo message", "Receive mojo reply",
                               "GPUTask", "DawnPlatformImpl::RunWorkerTask",
                               "MessagePump*", "TaskGraphRunner::RunTask",
                               "SimpleWatcher*", "Channel::*")),
]

# Compiles with no script URL are the `new Function` calls in support.js, which
# is where index.html's 568 KB x-dc block is actually turned into code. Named
# separately because "compile time with no URL" is the whole finding, and a
# reader who sees it folded into a total will assume it was the document.
ANON = "<anonymous / new Function>"


def free_port() -> int:
    """Never a fixed port (#42): two of these running at once used to fight over
    one and the loser reported a page fault that was really a harness fault."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class GzipHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the tree the way CloudFront serves the bucket: gzipped.

    The live distribution has `content-encoding: gzip` on `/`, so a measurement
    taken against `python3 -m http.server` measures a 588 KB transfer nobody
    receives. Compression changes the *shape* of the measurement, not only its
    size: bytes arrive sooner, and the HTML parser is handed decompressed chunks
    by a different path than it is handed socket reads.

    Only text is compressed, and only when the client asked, so an `Accept-
    Encoding: identity` run through the same server is the uncompressed control.
    """

    encode_ok = True     # flipped off by --encoding identity
    quiet = True
    # Compressing 588 KB at level 9 per request costs ~30ms of Python, and that
    # lands in the browser's TTFB where it looks like the site being slow.
    # CloudFront compresses once and caches the result, so caching here is the
    # accurate behaviour as well as the fast one.
    cache: "dict[tuple, bytes]" = {}

    def log_message(self, fmt: str, *args: object) -> None:
        if not self.quiet:
            super().log_message(fmt, *args)

    def handle_one_request(self) -> None:
        # Chrome drops keep-alive sockets the moment a navigation is replaced,
        # and the default handler prints a full traceback for each one. That is
        # noise in the middle of a table of numbers, not a fault.
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _compressible(self, path: str) -> bool:
        return path.endswith((".html", ".js", ".css", ".svg", ".json", ".txt"))

    def do_GET(self) -> None:
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if not os.path.isfile(path):
            super().do_GET()
            return
        accepts = "gzip" in self.headers.get("Accept-Encoding", "")
        gz = self.encode_ok and accepts and self._compressible(path)
        key = (path, gz, os.path.getmtime(path))
        body = self.cache.get(key)
        if body is None:
            body = open(path, "rb").read()
            if gz:
                body = gzip.compress(body, 9)
            self.cache[key] = body
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(len(body)))
        if gz:
            self.send_header("Content-Encoding", "gzip")
        # No-store on every response, so the browser cannot bring a code cache
        # to the second run. Belt and braces with Network.setCacheDisabled.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def serve(directory: str, encode: bool) -> "tuple[http.server.ThreadingHTTPServer, str]":
    """A threaded server in-process, because the gzip behaviour is the point.

    Its siblings shell out to `python3 -m http.server`; that module cannot
    compress, and the encoding is what makes this measurement match the live
    site. Returns (server, base_url); call `.shutdown()` when finished.
    """
    handler = type("H", (GzipHandler,), {"encode_ok": encode})
    port = free_port()
    # The document root is a constructor kwarg on SimpleHTTPRequestHandler, and
    # ThreadingHTTPServer only ever calls the class it is given -- so bind it
    # here rather than chdir'ing the whole process.
    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", port), functools.partial(handler, directory=directory))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/"
    for _ in range(60):
        try:
            urllib.request.urlopen(base, timeout=1).read(1)
            return srv, base
        except Exception:
            time.sleep(0.1)
    srv.shutdown()
    raise SystemExit(f"FATAL: could not serve {directory}")


def determinism_js(seed: int) -> str:
    """Seed the deal and NOTHING else.

    CLAUDE.md requires harnesses to inject their own generator rather than using
    the page's `?seed`, so a fault in the page's own dealing cannot be agreed
    with. What is deliberately absent is pixel_regress.py's frozen rAF and
    pinned performance.now: this harness measures the clock, so it may not stop
    it, and the wheel census that Math.random decides is the only thing here that
    needs to be the same machine run to run.
    """
    return ("(()=>{"
            f"let s={seed};"
            "Math.random=()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};"
            "})()")


# Planted before any page script. LCP and long tasks are delivered to observers
# rather than being readable after the fact -- `buffered:true` covers entries
# dispatched before this line only if the observer exists at all, which is why
# it cannot be evaluated after load and read back.
OBSERVE_JS = r"""
(() => {
  const P = (window.__perf = { lcp: null, longtasks: [], shifts: 0 });
  const obs = (type, fn) => {
    try { new PerformanceObserver(l => l.getEntries().forEach(fn))
            .observe({ type: type, buffered: true }); } catch (e) {}
  };
  obs('largest-contentful-paint', e => {
    P.lcp = { t: e.startTime, size: e.size,
              tag: e.element ? e.element.tagName.toLowerCase() : null };
  });
  obs('longtask', e => P.longtasks.push({ t: +e.startTime.toFixed(1),
                                          d: +e.duration.toFixed(1) }));
  obs('layout-shift', e => { if (!e.hadRecentInput) P.shifts += e.value; });
})()
"""

# Read after load has settled. Everything here comes off the same navigation
# entry a browser's own devtools panel reads, plus the transfer sizes -- which
# are what makes "as served (gzip)" a claim about bytes rather than an assertion.
COLLECT_JS = r"""
(() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const paint = {};
  performance.getEntriesByType('paint').forEach(p => { paint[p.name] = p.startTime; });
  const res = performance.getEntriesByType('resource').map(r => ({
    name: r.name.replace(/^https?:\/\/[^/]+/, ''),
    dur: +r.duration.toFixed(1),
    enc: r.encodedBodySize, dec: r.decodedBodySize,
  }));
  const P = window.__perf || {};
  const wheels = document.querySelectorAll('svg').length;
  // THE 568 KB BLOCK, TIMED DIRECTLY. The trace does not attribute it: the
  // `new Function` call in support.js shows up as ~2ms of FunctionCall with no
  // compile event under it, because V8 compiles a Function constructor's body
  // lazily -- only the top level eagerly, and the inner functions on first call.
  // So the only way to put a number on "what does compiling this cost" is to do
  // it again and time it. The unique trailing comment is not decoration: V8
  // keeps a compilation cache keyed on the source string, so recompiling the
  // identical text measures a cache hit and reports near zero.
  const el = document.querySelector('script[data-dc-script]');
  const src = el ? el.textContent : '';
  let compileMs = null;
  if (src) {
    const t0 = performance.now();
    try {
      new Function('DCLogic', 'StreamableLogic', 'React',
                   src + '\n//' + Math.random() + '\n;return 0;');
    } catch (e) { compileMs = -1; }
    if (compileMs === null) compileMs = performance.now() - t0;
  }
  return JSON.stringify({
    ttfb: nav.responseStart, respEnd: nav.responseEnd,
    domInteractive: nav.domInteractive,
    dcl: nav.domContentLoadedEventEnd, load: nav.loadEventEnd,
    docEnc: nav.encodedBodySize, docDec: nav.decodedBodySize,
    docTransfer: nav.transferSize,
    fp: paint['first-paint'] || null, fcp: paint['first-contentful-paint'] || null,
    lcp: P.lcp, longtasks: P.longtasks || [], cls: P.shifts || 0,
    resources: res, wheels: wheels,
    dcBytes: src.length, dcCompileMs: compileMs,
    errors: window.__errs || [],
  });
})()
"""

# Console and page errors, so a run that measured a broken page says so rather
# than reporting a very fast first paint of an error state.
ERRORS_JS = ("window.__errs=[];addEventListener('error',e=>"
             "window.__errs.push(String(e.message||e.error)));")


class Conn:
    """A CDP connection with a reader task, because tracing needs one.

    Its siblings can get away with "send, then read until the id matches",
    discarding everything in between. Tracing cannot: the trace itself arrives as
    a stream of `Tracing.dataCollected` events between the `Tracing.end` call and
    its `Tracing.tracingComplete`, so a helper that throws away non-matching
    messages throws away the measurement.
    """

    def __init__(self, ws: object) -> None:
        self.ws = ws
        self.mid = 0
        self.pending: "dict[int, asyncio.Future]" = {}
        self.events: "list[dict]" = []
        self.trace: "list[dict]" = []
        self.reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        try:
            while True:
                msg = json.loads(await self.ws.recv())
                if "id" in msg:
                    fut = self.pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        fut.set_result(msg.get("result", {}))
                elif msg.get("method") == "Tracing.dataCollected":
                    self.trace.extend(msg["params"].get("value", []))
                else:
                    self.events.append(msg)
        except Exception:
            pass

    async def send(self, method: str, params: "dict | None" = None) -> dict:
        self.mid += 1
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[self.mid] = fut
        await self.ws.send(json.dumps({"id": self.mid, "method": method,
                                       "params": params or {}}))
        return await asyncio.wait_for(fut, timeout=120)

    async def wait_event(self, method: str, timeout: float) -> "dict | None":
        """Poll the collected events; the reader owns the socket, so this cannot
        block on it and must not try to."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for e in self.events:
                if e.get("method") == method:
                    return e
            await asyncio.sleep(0.05)
        return None


def paint_window(trace: "list[dict]", page: dict) -> "tuple[float, float]":
    """navigationStart to the moment the page is finished appearing.

    The trace covers the settle period too, and that has to be cut off: the two
    seconds this harness waits for LCP to finalise are full of ordinary animation
    frames, and folding them in buries a 3ms parse under 900ms of rAF.

    The end of the window is `load` OR the largest contentful paint, whichever is
    LATER, and on this page it is reliably the paint. The document's own load
    event fires while support.js is still fetching React from unpkg, so a window
    that stopped at `load` would stop before the train is compiled or drawn --
    and would report, very confidently, that building this page costs nothing.
    """
    starts = [e["ts"] for e in trace if e.get("name") == "navigationStart"]
    t0 = min(starts) if starts else 0.0
    ms = max(page.get("load") or 0.0,
             (page.get("lcp") or {}).get("t", 0.0) if page.get("lcp") else 0.0,
             page.get("fcp") or 0.0)
    return t0, (t0 + ms * 1000.0) if ms else float("inf")


def thread_names(trace: "list[dict]") -> "dict[tuple, str]":
    """(pid, tid) -> thread name, from the trace's own metadata events."""
    out: "dict[tuple, str]" = {}
    for e in trace:
        if e.get("ph") == "M" and e.get("name") == "thread_name":
            out[(e.get("pid"), e.get("tid"))] = (e.get("args") or {}).get("name", "")
    return out


# The renderer's main thread. Everything a visitor waits on happens here;
# compilation and rasterisation also happen elsewhere, and time spent there is
# real work but not a stall.
MAIN_THREAD = "CrRendererMain"


def self_times(trace: "list[dict]", window: "tuple[float, float] | None" = None,
               threads: "dict[tuple, str] | None" = None,
               main_only: bool = False
               ) -> "tuple[dict[str, float], dict[str, float], dict[str, list]]":
    """Turn the raw trace into self time per event name.

    THIS IS THE ONLY AGGREGATE THAT CAN ANSWER #113. Complete ('X') events nest:
    a `ParseHTML` contains the `EvaluateScript` for each inline script, which
    contains the `v8.compile` for it. Their inclusive durations therefore overlap
    completely, and adding them up attributes the same millisecond to parsing,
    executing and compiling at once -- which is how a reader concludes that
    everything is slow. Self time is inclusive duration minus the duration of the
    direct children, computed per thread with a stack over start order.

    Returns (self time by name, self time by compile URL, biggest events by name).
    """
    lo, hi = window or (0.0, float("inf"))
    per_thread: "dict[tuple, list[dict]]" = {}
    for e in trace:
        if e.get("ph") != "X" or e.get("dur") is None:
            continue
        if not (lo <= e["ts"] <= hi):
            continue
        key = (e.get("pid"), e.get("tid"))
        # V8 streams and compiles scripts on background threads, and CDP's CPU
        # throttling does not reach them -- which is exactly how a compile total
        # that refuses to move at 6x throttling gives itself away. Splitting the
        # threads is what turns that from a puzzle into the finding.
        if main_only and (threads or {}).get(key) != MAIN_THREAD:
            continue
        per_thread.setdefault(key, []).append(e)

    by_name: "dict[str, float]" = {}
    by_url: "dict[str, float]" = {}
    biggest: "dict[str, list]" = {}
    for evs in per_thread.values():
        # Outer events first at equal start, so a parent is pushed before its
        # child even when the trace timestamps them identically.
        evs.sort(key=lambda e: (e["ts"], -e["dur"]))
        stack: "list[list]" = []          # [event, child_dur_total]
        for e in evs:
            while stack and stack[-1][0]["ts"] + stack[-1][0]["dur"] <= e["ts"]:
                done = stack.pop()
                _record(done, by_name, by_url, biggest)
            if stack:
                stack[-1][1] += e["dur"]
            stack.append([e, 0.0])
        while stack:
            _record(stack.pop(), by_name, by_url, biggest)
    return by_name, by_url, biggest


def _record(frame: list, by_name: dict, by_url: dict, biggest: dict) -> None:
    e, kids = frame
    name = e["name"]
    self_us = max(0.0, e["dur"] - kids)
    by_name[name] = by_name.get(name, 0.0) + self_us / 1000.0
    lst = biggest.setdefault(name, [])
    lst.append(e["dur"] / 1000.0)
    data = (e.get("args") or {}).get("data") or {}
    if name in ("v8.compile", "V8.CompileScript", "EvaluateScript", "FunctionCall"):
        url = data.get("url") or ""
        key = (url.rsplit("/", 1)[-1] or ANON) if url else ANON
        if data.get("lineNumber") not in (None, 0) and key != ANON:
            key += f":{data['lineNumber']}"
        by_url[f"{name} {key}"] = by_url.get(f"{name} {key}", 0.0) + e["dur"] / 1000.0


def _matches(name: str, pattern: str) -> bool:
    return name.startswith(pattern[:-1]) if pattern.endswith("*") else name == pattern


def classify(name: str) -> "str | None":
    """Which phase an event name belongs to, or None if this harness has not
    learned it. First match wins, so PHASES order is also precedence."""
    for label, patterns in PHASES:
        if any(_matches(name, p) for p in patterns):
            return label
    return None


def phase_table(by_name: "dict[str, float]") -> "dict[str, float]":
    out = {label: 0.0 for label, _ in PHASES}
    out["other"] = 0.0
    for name, ms in by_name.items():
        out[classify(name) or "other"] += ms
    return out


async def measure(url: str, viewport: "tuple[int, int]", rate: int, runs: int,
                  seed: int, settle: float, block: "list[str]",
                  encode: bool) -> "list[dict]":
    """One browser, `runs` cold navigations at one CPU throttling rate."""
    port = free_port()
    profile = tempfile.mkdtemp(prefix="wozi-parse-")
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

    out: "list[dict]" = []
    async with websockets.connect(ws_url, max_size=2 ** 30) as ws:
        c = Conn(ws)
        await c.send("Page.enable")
        await c.send("Runtime.enable")
        await c.send("Network.enable")
        await c.send("Performance.enable")
        await c.send("Network.setCacheDisabled", {"cacheDisabled": True})
        if block:
            await c.send("Network.setBlockedURLs", {"urls": block})
        await c.send("Emulation.setDeviceMetricsOverride",
                     {"width": viewport[0], "height": viewport[1],
                      "deviceScaleFactor": 1, "mobile": False})
        for src in (determinism_js(seed), ERRORS_JS, OBSERVE_JS):
            await c.send("Page.addScriptToEvaluateOnNewDocument", {"source": src})

        for i in range(runs):
            # Throttling is set per run rather than once, because navigating
            # away and back can reset the override in some Chrome builds and a
            # silently-unthrottled run reads as a suspiciously fast device.
            await c.send("Emulation.setCPUThrottlingRate", {"rate": rate})
            c.events.clear()
            c.trace.clear()
            await c.send("Tracing.start", {
                "transferMode": "ReportEvents",
                "traceConfig": {"includedCategories": TRACE_CATEGORIES,
                                "recordMode": "recordAsMuchAsPossible"},
            })
            await c.send("Page.navigate", {"url": url})
            got = await c.wait_event("Page.loadEventFired", 60.0 * max(1, rate / 4))
            # The train keeps drawing after `load`, and LCP is not final until
            # nothing larger arrives, so settle scaled by the throttling rate --
            # a 6x-slower CPU needs 6x longer to finish the same work.
            await asyncio.sleep(settle * max(1.0, rate / 2))
            r = await c.send("Runtime.evaluate", {"expression": COLLECT_JS,
                                                 "returnByValue": True})
            page = json.loads(r["result"]["value"])
            await c.send("Tracing.end")
            await c.wait_event("Tracing.tracingComplete", 60.0)
            # Un-throttle before the next Tracing.start so the harness's own
            # bookkeeping is not run at 1/6 speed.
            await c.send("Emulation.setCPUThrottlingRate", {"rate": 1})
            win = paint_window(c.trace, page)
            threads = thread_names(c.trace)
            by_name, by_url, biggest = self_times(c.trace, win, threads, True)
            all_name, _, _ = self_times(c.trace, None, threads, True)
            off_name, _, _ = self_times(c.trace, win, threads, False)
            off = {k: v - by_name.get(k, 0.0) for k, v in off_name.items()}
            page.update({
                "run": i, "rate": rate, "loaded": bool(got),
                "encoding": "gzip" if encode else "identity",
                "phases": phase_table(by_name), "by_name": by_name,
                "phases_full": phase_table(all_name),
                "phases_off": phase_table(off),
                "by_url": by_url,
                "trace_events": len(c.trace),
                "longest_task": max((t["d"] for t in page["longtasks"]), default=0.0),
                "biggest": {k: round(max(v), 2) for k, v in biggest.items()
                            if max(v) >= 1.0},
            })
            out.append(page)
        c.reader.cancel()
    proc.kill()
    shutil.rmtree(profile, ignore_errors=True)
    return out


def med(rows: "list[dict]", key: str, default: float = 0.0) -> float:
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return statistics.median(vals) if vals else default


def med_path(rows: "list[dict]", outer: str, key: str) -> float:
    vals = [r[outer].get(key, 0.0) for r in rows if isinstance(r.get(outer), dict)]
    return statistics.median(vals) if vals else 0.0


def report(label: str, rows: "list[dict]", runs_shown: bool = True) -> None:
    n = len(rows)
    print(f"\n=== {label}   median of {n} cold runs ===")
    lcps = [r["lcp"]["t"] for r in rows if r.get("lcp")]
    print(f"  {'TTFB':<26}{med(rows, 'ttfb'):>9.1f} ms")
    print(f"  {'First Paint':<26}{med(rows, 'fp'):>9.1f} ms")
    print(f"  {'First Contentful Paint':<26}{med(rows, 'fcp'):>9.1f} ms")
    print(f"  {'Largest Contentful Paint':<26}"
          f"{(statistics.median(lcps) if lcps else float('nan')):>9.1f} ms"
          + ("" if lcps else "   (no LCP candidate reported)"))
    print(f"  {'DOMContentLoaded':<26}{med(rows, 'dcl'):>9.1f} ms")
    print(f"  {'load':<26}{med(rows, 'load'):>9.1f} ms")
    lt = [len(r["longtasks"]) for r in rows]
    print(f"  {'long tasks (>50ms)':<26}{statistics.median(lt):>9.0f}"
          f"   longest {med(rows, 'longest_task'):.0f} ms"
          f"   total {statistics.median([sum(t['d'] for t in r['longtasks']) for r in rows]):.0f} ms")
    print(f"  {'wheels drawn':<26}{statistics.median([r['wheels'] for r in rows]):>9.0f}")
    dcb = med(rows, "dcBytes")
    print(f"  {'x-dc block':<26}{dcb/1024:>9.1f} KiB"
          f"   new Function() top-level compile {med(rows, 'dcCompileMs'):.1f} ms")

    print("\n  main-thread SELF time by phase, navigationStart -> LCP")
    print("  (nested durations not double counted; the settle period is excluded)")
    for label_, _ in PHASES + [("other", ())]:
        v = med_path(rows, "phases", label_)
        if v >= 0.05:
            print(f"    {label_:<24}{v:>9.1f} ms"
                  f"      full trace {med_path(rows, 'phases_full', label_):>9.1f} ms")
    tot = sum(med_path(rows, "phases", l) for l, _ in PHASES + [("other", ())])
    print(f"    {'TOTAL traced':<24}{tot:>9.1f} ms")
    offs = [(med_path(rows, "phases_off", l), l) for l, _ in PHASES + [("other", ())]]
    hot = ", ".join(f"{l} {v:.1f}ms" for v, l in sorted(offs, reverse=True) if v >= 1.0)
    if hot:
        print(f"    off the main thread, same window: {hot}")

    # "other" is where a misclassification hides, so it is never left as one
    # number: an event this harness has not learned to name would otherwise sit
    # in it looking like idle time.
    unk = {k for r in rows for k in r["by_name"] if classify(k) is None}
    ranked_unk = sorted(((statistics.median([r["by_name"].get(k, 0.0) for r in rows]), k)
                         for k in unk), reverse=True)[:6]
    if ranked_unk and ranked_unk[0][0] >= 0.5:
        print("    of which, unclassified: "
              + ", ".join(f"{k} {v:.1f}ms" for v, k in ranked_unk if v >= 0.5))

    print("\n  compile / execute, attributed to the script it belongs to (inclusive)")
    keys = {k for r in rows for k in r["by_url"]}
    ranked = sorted(((statistics.median([r["by_url"].get(k, 0.0) for r in rows]), k)
                     for k in keys), reverse=True)
    for v, k in ranked[:12]:
        if v >= 0.5:
            print(f"    {k[:56]:<56}{v:>9.1f} ms")
    if runs_shown:
        doc = med(rows, 'docEnc')
        dec = med(rows, 'docDec')
        print(f"\n  document transfer  {doc/1024:.1f} KiB encoded"
              f"  ->  {dec/1024:.1f} KiB decoded"
              f"   ({rows[0]['encoding']})")
    errs = [e for r in rows for e in r.get("errors") or []]
    if errs:
        print(f"  PAGE ERRORS: {sorted(set(errs))}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--viewport", action="append", default=[],
                    help="WxH, repeatable (default 1440x900)")
    ap.add_argument("--throttle", action="append", type=int, default=[],
                    help="CDP CPU throttling rate, repeatable (default 1, 4, 6)")
    ap.add_argument("--runs", type=int, default=5,
                    help="cold navigations per cell; the median is reported")
    ap.add_argument("--seed", type=int, default=20260731,
                    help="LCG seed for the deal, so every cell draws one machine")
    ap.add_argument("--settle", type=float, default=2.0,
                    help="seconds after load to let LCP finalise, scaled by throttle")
    ap.add_argument("--encoding", default="gzip", choices=["gzip", "identity"],
                    help="serve compressed (as CloudFront does) or raw")
    ap.add_argument("--query", default="",
                    help="query string appended to the page, e.g. '?who=charles'")
    ap.add_argument("--no-fonts", action="store_true",
                    help="block fonts.googleapis.com/gstatic, to isolate first-party cost")
    # The counterfactual is the only way to price the file's SIZE rather than
    # its content: build a tree whose index.html is the same page with the
    # comments taken out (tools/strip_comments.py --out), serve it here, and
    # compare. Anything the size costs has to show up as a difference between
    # those two runs, and anything that does not is not a size problem.
    ap.add_argument("--root", default=ROOT,
                    help="serve this directory instead of the repo, e.g. a "
                         "comment-stripped copy built by tools/strip_comments.py")
    ap.add_argument("--json", help="write every run, unrounded, to this path")
    a = ap.parse_args()

    # Same trap pixel_regress.py names: appended to a bare directory URL without
    # the '?', the query becomes a PATH and the whole measurement is of a 404 --
    # which parses very fast indeed.
    if a.query and not a.query.startswith("?"):
        print(f"FATAL: --query must start with '?' (got {a.query!r}); "
              f"without it the page is a 404, and a 404 parses instantly")
        return 2

    vps = [tuple(int(n) for n in v.lower().split("x")) for v in a.viewport] \
        or [(1440, 900)]
    rates = a.throttle or [1, 4, 6]
    block = (["*fonts.googleapis.com*", "*fonts.gstatic.com*"]
             if a.no_fonts else [])
    encode = a.encoding == "gzip"

    raw = os.path.getsize(os.path.join(a.root, "index.html"))
    print(f"{os.path.join(a.root, 'index.html')}: {raw/1024:.1f} KiB on disk"
          f"   served as: {a.encoding}"
          f"   fonts: {'blocked' if a.no_fonts else 'allowed'}")

    srv, base = serve(a.root, encode)
    everything: "list[dict]" = []
    try:
        for vp in vps:
            for rate in rates:
                rows = asyncio.run(measure(base + a.query, vp, rate, a.runs,
                                           a.seed, a.settle, block, encode))
                everything.extend({**r, "viewport": f"{vp[0]}x{vp[1]}"} for r in rows)
                report(f"{vp[0]}x{vp[1]}  CPU {rate}x", rows)
    finally:
        srv.shutdown()

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(everything, fh, indent=1)
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
