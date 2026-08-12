#!/usr/bin/env python3
"""WHERE does the first render's one long task actually spend its time?

    tools/render_cost.py                              # 1x, 4x, 6x, combined + solo
    tools/render_cost.py --throttle 6 --runs 3
    tools/render_cost.py --families                   # one forced family per run
    tools/render_cost.py --coverage                   # call counts, not times
    tools/render_cost.py --json /tmp/render.json

WHY THIS EXISTS, AND WHY IT IS NOT `parse_cost.py`. GitHub #135 was split out of
#113 with the headline already measured: the whole document parse is 7ms, the
555KB `x-dc` block costs 0.1-2.0ms to compile, and the ONE long task on the page
is `FunctionCall react.production.min.js` -- 34ms at 1x, 176ms at 6x. That is
`parse_cost.py`'s finding and this harness does not re-take it. What #135 asks
next is the question a trace cannot answer: a trace's finest grain on that task
is the task itself, because every millisecond inside it is one uninterrupted
`FunctionCall` with no sub-events. Only a SAMPLING PROFILER can see inside it.

So this is a sibling rather than an extension. It imports `parse_cost`'s server,
its LCG injection, its trace helpers and its phase table -- there is no second
copy of any of that here -- and adds the two CDP domains `parse_cost.py` does
not use:

  * `Profiler` at a 100us sampling interval, aggregated by SELF time per
    JavaScript function, restricted to the react task's own trace window. The
    window is the whole point: the profile also covers `solve()`, the fit, the
    settle period and 2+ seconds of animation frames, and folding those in
    reports the steady state rather than the first render.
  * `Profiler.startPreciseCoverage(callCount, detailed)`, which answers the
    third question -- what is RE-DONE -- with call counts rather than time. A
    `renderVals` that runs three times before first paint is a fact no timing
    measurement states out loud.

HOW THE BUCKETS ARE ASSIGNED, and why leaf-first. Every sample is a stack. Each
sample is credited to the FIRST frame that matches a bucket, scanning from the
leaf DOWNWARD toward the root, so the buckets are disjoint and each one holds
only the time spent in its own frames. `teethPath` therefore does not appear
inside `gearSvg`'s number, and `React.createElement` -- which the page calls as
`h`, tens of thousands of times -- does not appear inside the number for
whichever of our functions called it. Read the table as a partition of the task,
not as a call tree.

WHAT THE FAMILY SWEEP IS FOR. `gearSvg`'s eleven family branches are one
`if / else if` chain inside a single function, so no profiler can separate
`hexcore` from `sunburst` by function name -- they share a frame. `?kind=<name>`
already forces every wheel to one family (it is how the contact sheets are
made), so the separation is done by running the page eleven times instead of by
sub-attributing one function. `--families` does that, at a fixed wheel count.

CPU THROTTLING IS SYNTHETIC and this harness cannot make it otherwise. 6x is a
number, not a device; `docs/MANUAL-CHECKS.md` exists because nothing in `tools/`
has a battery or Low Power Mode. Rates are reported side by side so the SHAPE of
the breakdown can be compared across them -- if a bucket's share is flat across
1x/4x/6x it is CPU-bound work and the throttle is behaving as a multiplier; if a
share moves, something in that bucket is not on the throttled clock.

Cache is disabled for every run and the median of `--runs` is reported, for
`parse_cost.py`'s reasons: a cold V8 code cache is the state a first-time visitor
is in, and the first navigation into a fresh renderer pays to warm the process.

Exit 0 if it measured, 2 if it could not get a browser, a trace or a profile.
"""

import argparse
import asyncio
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_cost as pc                                    # noqa: E402

ROOT = pc.ROOT

# The families that are actually DEALT (CENTRE_FAMILIES). `iris`, `honeycomb`,
# `spiral` and `labyrinth` are retired and `?kind=` for one of them silently
# falls back to the ordinary mix -- dealCentres does not error on an unknown
# name -- so asking for one would report the mixed deal under a family's name.
FAMILIES = ["spokes", "holes", "pockets", "star", "hexcore", "isogrid",
            "polarbrick", "polariso", "sunburst", "planetary", "ravigneaux"]

# Leaf-first precedence. First match from the top of the stack downward wins, so
# these are a PARTITION of the task rather than a call tree: a bucket's number is
# time in its own frames only. Each entry is (label, kind, needle).
#   'url'  -- substring of the frame's script URL
#   'fn'   -- exact function name
#   'fnset'-- function name in a set
#
# WHAT IS DELIBERATELY *NOT* A BUCKET, and why that is the load-bearing half.
# `polarR`, `polarD`, `px`, `arcD`, `ringPath`, `shades` and `flatTones` are
# leaf primitives called from everywhere. Giving them a bucket makes them the
# top of the table -- the first version of this file did, and reported 30.6ms in
# "wheel helpers" while `teethPath`, which is what spends it, showed 5.5ms. A
# leaf-first scan attributes to the innermost bucket, so a primitive that HAS a
# bucket takes the time away from the caller whose cost it actually is. They are
# left out on purpose, so they roll up into `teethPath` / `gearSvg` / whichever
# frame asked for the arithmetic.
#
# `textWidth` keeps its own bucket for the opposite reason: it is not
# arithmetic, it is `canvas.measureText`, and its cost belongs to text
# measurement rather than to the row it was measured for.
BUCKETS = [
    ("(gc)", "fnset", {"(garbage collector)"}),
    ("(program/native)", "fnset", {"(program)", "(root)"}),
    ("ReactDOM reconcile+commit", "url", "react-dom"),
    ("React.createElement (h)", "url", "react.production"),
    ("support.js runtime", "url", "support.js"),
    ("config.js", "url", "config.js"),
    ("teethPath (involute)", "fn", "teethPath"),
    ("engraving (band+type)", "fn", "engraving"),
    ("ghostSvg", "fn", "ghostSvg"),
    ("gearSvg (body/cuts/lattice)", "fn", "gearSvg"),
    ("datum stack", "fnset", {"datumLayer", "plateMetrics", "plateMargin",
                              "datumClear", "slabClip", "plateAir",
                              "plateExcluded", "plateNearestClean", "plateSeat"}),
    ("textWidth (measureText)", "fn", "textWidth"),
    ("fitStage (the four fit terms)", "fn", "fitStage"),
    ("solve() + escapes + datum runs", "fnset",
     {"solve", "chainAxes", "datumRuns", "fitEscapes", "dealCentres",
      "idlerCount", "smallestBlankHolding", "wearWheels", "axisRot", "gsRender"}),
    ("loadIcons (fetch)", "fn", "loadIcons"),
    ("renderVals (assembly)", "fn", "renderVals"),
    ("syncVars (getComputedStyle)", "fn", "syncVars"),
    ("componentDidMount", "fn", "componentDidMount"),
]

IDLE = {"(idle)"}

# WHICH PHASE OF REACT'S OWN CYCLE a sample is in, found by scanning the stack
# from the ROOT outward -- the opposite direction to BUCKETS. A bucket asks "what
# was this millisecond spent computing", which is a question about the innermost
# frame; a phase asks "which pass of the render cycle are we in", which is a
# question about the outermost one. `renderVals` inside `componentDidUpdate`'s
# forced update is a render, not a lifecycle callback, and only a root-first scan
# says so.
#
# This is what turns "one 183ms task" into a timeline. React 18's `createRoot`
# flushes a `setState` made during `componentDidMount` before it yields, so a
# second full render can be -- and here is -- INSIDE the first task, where no
# trace event marks the boundary.
PHASE_MARKERS = [
    ("render (renderVals -> 41 svgs)", {"renderVals"}),
    ("componentDidUpdate", {"componentDidUpdate"}),
    ("componentDidMount", {"componentDidMount"}),
    ("fitStage / fitEscapes", {"fitStage", "fitEscapes"}),
    ("solve()", {"solve"}),
    ("startPhysics / step", {"startPhysics", "step", "applyRotation"}),
]


def launch(port: int) -> "tuple[subprocess.Popen, str]":
    """Start headless Chrome and return (process, websocket url).

    The only thing here that is not imported from `parse_cost` -- its own launch
    is inline in `measure()` and not reachable as a function, and reaching into
    that file to extract one would put an edit into a harness another agent may
    be holding. Twenty lines duplicated is the smaller cost.
    """
    profile = tempfile.mkdtemp(prefix="wozi-render-")
    # A CHROME THAT IS NOT THERE IS THE SAME SENTENCE AS ONE THAT NEVER ANSWERS,
    # and it used to be a different exit code (#156): Popen raises
    # FileNotFoundError, which reaches the top as a traceback and exits 1 — the
    # code that means "it measured, and the answer is bad". Said here, once,
    # rather than caught around the whole run.
    if not os.path.exists(pc.CHROME):
        print(f"FATAL: no Chrome at {pc.CHROME!r} — set $CHROME to the binary")
        raise SystemExit(2)
    proc = subprocess.Popen(
        [pc.CHROME, "--headless=new", "--window-position=-4000,-4000",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
         *pc.CI_FLAGS, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws_url = None
    for _ in range(60):
        for method in (None, "PUT"):
            try:
                target = f"http://127.0.0.1:{port}/json/new?about:blank"
                req = (urllib.request.Request(target, method=method)
                       if method else target)
                ws_url = json.load(urllib.request.urlopen(
                    req, timeout=1))["webSocketDebuggerUrl"]
                break
            except Exception:
                pass
        if ws_url:
            break
        time.sleep(0.2)
    if not ws_url:
        proc.kill()
        shutil.rmtree(profile, ignore_errors=True)
        # print-then-2, never `SystemExit("...")`: the string form exits 1, and
        # the docstring above promises 2 for "could not get a browser" (#156).
        print("FATAL: no DevTools endpoint")
        raise SystemExit(2)
    proc._wozi_profile_dir = profile                      # type: ignore[attr-defined]
    return proc, ws_url


def kill(proc: subprocess.Popen) -> None:
    proc.kill()
    shutil.rmtree(getattr(proc, "_wozi_profile_dir", ""), ignore_errors=True)


def render_task(trace: "list[dict]", threads: "dict[tuple, str]") -> "dict | None":
    """The longest main-thread `FunctionCall` attributed to React.

    This is the task #135 names. It is found by URL rather than by taking the
    longest task on the thread, because "the longest task" would silently become
    a different task if anything else ever got slower -- and then the breakdown
    below would be of something other than the first render, with nothing saying
    so. Returns the raw trace event, whose `ts`/`dur` are microseconds.
    """
    best = None
    for e in trace:
        if e.get("name") != "FunctionCall" or e.get("ph") != "X":
            continue
        if threads.get((e.get("pid"), e.get("tid"))) != pc.MAIN_THREAD:
            continue
        url = ((e.get("args") or {}).get("data") or {}).get("url") or ""
        if "react" not in url:
            continue
        if best is None or (e.get("dur") or 0) > (best.get("dur") or 0):
            best = e
    return best


def react_calls(trace: "list[dict]", threads: "dict[tuple, str]") -> "list[dict]":
    """Every main-thread React `FunctionCall`, longest first, with its URL.

    `react.production.min.js` and `react-dom.production.min.js` are two different
    entry points and #135 names only the first. Printing both, with durations,
    is what distinguishes "React rendering the composition" from "the whole mount
    including `componentDidMount`" -- they nest, and only the trace says which
    one a number came from.
    """
    out = []
    for e in trace:
        if e.get("name") != "FunctionCall" or e.get("ph") != "X":
            continue
        if threads.get((e.get("pid"), e.get("tid"))) != pc.MAIN_THREAD:
            continue
        data = (e.get("args") or {}).get("data") or {}
        url = data.get("url") or ""
        if "react" not in url:
            continue
        out.append({"url": url.rsplit("/", 1)[-1],
                    "fn": data.get("functionName") or "",
                    "line": data.get("lineNumber"),
                    "d": e["dur"] / 1000.0, "t": e["ts"]})
    out.sort(key=lambda r: -r["d"])
    return out[:6]


def main_tasks(trace: "list[dict]", threads: "dict[tuple, str]") -> "list[dict]":
    """Every main-thread top-level task, longest first, as {t, d, name, url}.

    Context for the claim that there is only ONE long task. A breakdown of a
    176ms task is only interesting if the next-largest is far smaller, and that
    has to be shown rather than asserted.
    """
    out = []
    for e in trace:
        if e.get("ph") != "X" or e.get("dur") is None:
            continue
        if threads.get((e.get("pid"), e.get("tid"))) != pc.MAIN_THREAD:
            continue
        if e.get("name") not in ("RunTask", "ThreadControllerImpl::RunTask"):
            continue
        out.append({"t": e["ts"], "d": e["dur"] / 1000.0})
    out.sort(key=lambda r: -r["d"])
    return out[:8]


def bucket_of(frame: dict) -> str:
    fn = frame.get("functionName") or "(anonymous)"
    url = frame.get("url") or ""
    for label, kind, needle in BUCKETS:
        if kind == "url" and needle in url:
            return label
        if kind == "fn" and fn == needle:
            return label
        if kind == "fnset" and fn in needle:
            return label
    return None


def profile_slice(prof: dict, window: "tuple[float, float] | None"
                  ) -> "tuple[dict, dict, float, int]":
    """Aggregate a CPU profile into disjoint buckets and per-function self time.

    Samples carry a node id and `timeDeltas[i]` is the wall time BEFORE sample i,
    so sample i's own cost is `timeDeltas[i+1]` -- attributing `timeDeltas[i]`
    instead shifts the whole profile one sample earlier, which at 100us and a
    34ms task is a real 3% error at the boundaries of a window this narrow.

    `window` is in trace microseconds. `profile.startTime` is the same
    `base::TimeTicks` clock the trace's `ts` uses, which is what makes the
    intersection legitimate; `main()` checks the two overlap at all and says so
    rather than reporting a confident breakdown of an empty intersection.

    Returns (buckets, per-function self ms, total ms, samples used, react-cycle
    phases, and a segmented timeline of contiguous same-phase runs).
    """
    nodes = {n["id"]: n for n in prof.get("nodes", [])}
    parent: "dict[int, int]" = {}
    for n in prof.get("nodes", []):
        for kid in n.get("children") or []:
            parent[kid] = n["id"]

    # Bucket and self-name are properties of the NODE, not of the sample, so they
    # are resolved once per node rather than once per sample -- there are tens of
    # thousands of samples and a few hundred nodes.
    node_bucket: "dict[int, str]" = {}
    node_self: "dict[int, str]" = {}
    node_phase: "dict[int, str]" = {}
    for nid in nodes:
        # Root-first: build the ancestor chain, then take the FIRST marker met
        # walking down from the root. See PHASE_MARKERS.
        chain, cur, seen = [], nid, set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            chain.append((nodes[cur].get("callFrame") or {}).get("functionName") or "")
            cur = parent.get(cur)
        chain.reverse()
        phase = "before/after the cycle"
        for fn in chain:
            hit = next((lbl for lbl, names in PHASE_MARKERS if fn in names), None)
            if hit:
                phase = hit
                break
        node_phase[nid] = phase
    for nid in nodes:
        frame = nodes[nid].get("callFrame") or {}
        fn = frame.get("functionName") or "(anonymous)"
        url = (frame.get("url") or "").rsplit("/", 1)[-1]
        line = frame.get("lineNumber")
        node_self[nid] = (f"{fn} [{url or 'x-dc'}"
                          + (f":{line + 1}]" if isinstance(line, int) and line >= 0 else "]"))
        cur, label = nid, None
        seen = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            label = bucket_of(nodes[cur].get("callFrame") or {})
            if label:
                break
            cur = parent.get(cur)
        node_bucket[nid] = label or "other page code (x-dc)"

    samples = prof.get("samples") or []
    deltas = prof.get("timeDeltas") or []
    t = float(prof.get("startTime", 0.0))
    lo, hi = window or (0.0, float("inf"))
    buckets: "dict[str, float]" = {}
    selfms: "dict[str, float]" = {}
    phases: "dict[str, float]" = {}
    timeline: "list[list]" = []          # [label, start ms into window, ms]
    total = 0.0
    used = 0
    for i, nid in enumerate(samples):
        t += deltas[i] if i < len(deltas) else 0.0
        cost = float(deltas[i + 1]) if i + 1 < len(deltas) else 0.0
        if not (lo <= t <= hi):
            continue
        frame = (nodes.get(nid) or {}).get("callFrame") or {}
        if (frame.get("functionName") or "") in IDLE:
            continue
        used += 1
        ms = cost / 1000.0
        total += ms
        b = node_bucket.get(nid, "other page code (x-dc)")
        buckets[b] = buckets.get(b, 0.0) + ms
        s = node_self.get(nid, "?")
        selfms[s] = selfms.get(s, 0.0) + ms
        p = node_phase.get(nid, "before/after the cycle")
        phases[p] = phases.get(p, 0.0) + ms
        rel = (t - lo) / 1000.0 if lo else 0.0
        if timeline and timeline[-1][0] == p:
            timeline[-1][2] += ms
        else:
            timeline.append([p, rel, ms])
    return buckets, selfms, total, used, phases, timeline


COUNT_JS = r"""
(() => {
  // The census the breakdown has to be divided by. Every number in the table
  // above is meaningless per-wheel without it, and the wheel count is a
  // consequence of the deal and the fit, not something the URL states.
  const svgs = document.querySelectorAll('svg').length;
  const stage = document.querySelectorAll('svg[data-wheel], g[data-wheel]').length;
  const paths = document.querySelectorAll('path').length;
  const nodes = document.getElementsByTagName('*').length;
  const defs = document.querySelectorAll('defs').length;
  const grads = document.querySelectorAll('linearGradient,radialGradient').length;
  const clips = document.querySelectorAll('clipPath').length;
  let dlen = 0, dmax = 0;
  document.querySelectorAll('path').forEach(p => {
    const d = (p.getAttribute('d') || '').length;
    dlen += d; if (d > dmax) dmax = d;
  });
  return JSON.stringify({ svgs, stage, paths, nodes, defs, grads, clips,
                          pathDataBytes: dlen, biggestPathBytes: dmax });
})()
"""


async def measure(url: str, viewport: "tuple[int, int]", rate: int, runs: int,
                  seed: int, settle: float) -> "list[dict]":
    """One browser, `runs` cold navigations, trace + CPU profile on each."""
    port = pc.free_port()
    proc, ws_url = launch(port)
    out: "list[dict]" = []
    try:
        async with websockets.connect(ws_url, max_size=2 ** 31) as ws:
            c = pc.Conn(ws)
            await c.send("Page.enable")
            await c.send("Runtime.enable")
            await c.send("Network.enable")
            await c.send("Profiler.enable")
            await c.send("Network.setCacheDisabled", {"cacheDisabled": True})
            await c.send("Emulation.setDeviceMetricsOverride",
                         {"width": viewport[0], "height": viewport[1],
                          "deviceScaleFactor": 1, "mobile": False})
            # 100us. The default 1000us puts about 34 samples inside a 34ms task
            # at 1x, which cannot distinguish a 20% bucket from a 30% one.
            await c.send("Profiler.setSamplingInterval", {"interval": 100})
            for src in (pc.determinism_js(seed), pc.ERRORS_JS, pc.OBSERVE_JS):
                await c.send("Page.addScriptToEvaluateOnNewDocument", {"source": src})

            for i in range(runs):
                await c.send("Emulation.setCPUThrottlingRate", {"rate": rate})
                c.events.clear()
                c.trace.clear()
                await c.send("Tracing.start", {
                    "transferMode": "ReportEvents",
                    "traceConfig": {"includedCategories": pc.TRACE_CATEGORIES,
                                    "recordMode": "recordAsMuchAsPossible"},
                })
                await c.send("Profiler.start")
                await c.send("Page.navigate", {"url": url})
                got = await c.wait_event("Page.loadEventFired",
                                         60.0 * max(1, rate / 4))
                await asyncio.sleep(settle * max(1.0, rate / 2))
                page = json.loads((await c.send("Runtime.evaluate", {
                    "expression": pc.COLLECT_JS, "returnByValue": True,
                }))["result"]["value"])
                census = json.loads((await c.send("Runtime.evaluate", {
                    "expression": COUNT_JS, "returnByValue": True,
                }))["result"]["value"])
                prof = (await c.send("Profiler.stop")).get("profile") or {}
                await c.send("Tracing.end")
                await c.wait_event("Tracing.tracingComplete", 120.0)
                await c.send("Emulation.setCPUThrottlingRate", {"rate": 1})

                threads = pc.thread_names(c.trace)
                task = render_task(c.trace, threads)
                win = (task["ts"], task["ts"] + task["dur"]) if task else None
                buckets, selfms, tot, used, cyc, tline = profile_slice(prof, win)
                # Everything after the react task, up to the last paint in the
                # navigation window: style, layout and paint of the 41 SVGs it
                # just built. Question 1 asks whether that is where the time is,
                # and it is a trace question rather than a profiler one -- none
                # of it is JavaScript.
                nav = pc.paint_window(c.trace, page)
                # EXCLUSIVE OF THE TASK AT BOTH ENDS. `pc.self_times` compares
                # `lo <= ts <= hi`, so a window ending exactly at `task["ts"]`
                # admits the task itself -- which reported the 174ms render as
                # 174ms of "script execute BEFORE the render" and invented a
                # second long task that does not exist. One microsecond of
                # clearance is the whole fix.
                after = ((task["ts"] + task["dur"] + 1, nav[1]) if task else None)
                post_name, _, _ = pc.self_times(c.trace, after, threads, True)
                before = (nav[0], task["ts"] - 1) if task else None
                pre_name, pre_url, _ = pc.self_times(c.trace, before, threads, True)
                out.append({
                    "run": i, "rate": rate, "loaded": bool(got), "url": url,
                    "task_ms": (task["dur"] / 1000.0) if task else 0.0,
                    "prof_ms": tot, "prof_samples": used,
                    "prof_startTime": prof.get("startTime"),
                    "prof_total_samples": len(prof.get("samples") or []),
                    "window": win,
                    "buckets": buckets, "self": selfms,
                    "cycle": cyc, "timeline": tline,
                    "post_phases": pc.phase_table(post_name),
                    "pre_phases": pc.phase_table(pre_name),
                    # WHAT RUNS BEFORE THE RENDER, by script. #135 says the render
                    # is the only long task; at 6x there is a second one in front
                    # of it, and naming the script is the difference between a
                    # finding and a mystery.
                    "pre_by_url": {k: v for k, v in pre_url.items() if v >= 1.0},
                    "tasks": main_tasks(c.trace, threads),
                    "react_calls": react_calls(c.trace, threads),
                    "census": census,
                    "fcp": page.get("fcp"), "load": page.get("load"),
                    "lcp": (page.get("lcp") or {}).get("t"),
                    "longtasks": page.get("longtasks") or [],
                    "errors": page.get("errors") or [],
                })
            c.reader.cancel()
    finally:
        kill(proc)
    return out


async def coverage(url: str, viewport: "tuple[int, int]", seed: int,
                   settle: float) -> dict:
    """Per-function CALL COUNTS for one cold load, unthrottled.

    Times cannot answer "what is re-done"; counts can. Coverage is collected in
    its own run because `startPreciseCoverage` adds counting overhead to every
    function entry, which would inflate exactly the numbers the timed runs
    report -- so this run's durations are deliberately not reported at all.
    """
    port = pc.free_port()
    proc, ws_url = launch(port)
    try:
        async with websockets.connect(ws_url, max_size=2 ** 31) as ws:
            c = pc.Conn(ws)
            await c.send("Page.enable")
            await c.send("Runtime.enable")
            await c.send("Profiler.enable")
            await c.send("Network.setCacheDisabled", {"cacheDisabled": True})
            await c.send("Emulation.setDeviceMetricsOverride",
                         {"width": viewport[0], "height": viewport[1],
                          "deviceScaleFactor": 1, "mobile": False})
            for src in (pc.determinism_js(seed), pc.ERRORS_JS):
                await c.send("Page.addScriptToEvaluateOnNewDocument", {"source": src})
            await c.send("Profiler.startPreciseCoverage",
                         {"callCount": True, "detailed": True})
            await c.send("Page.navigate", {"url": url})
            await c.wait_event("Page.loadEventFired", 60.0)
            await asyncio.sleep(settle)
            res = await c.send("Profiler.takePreciseCoverage")
            census = json.loads((await c.send("Runtime.evaluate", {
                "expression": COUNT_JS, "returnByValue": True,
            }))["result"]["value"])
            c.reader.cancel()
    finally:
        kill(proc)

    # One count per named function, taking the OUTERMOST range's count, which is
    # the function's own entry count. Inner ranges are branches within it and
    # counting those would report how often an `if` was taken as how often the
    # function ran.
    counts: "dict[str, int]" = {}
    for script in res.get("result") or []:
        tag = (script.get("url") or "").rsplit("/", 1)[-1] or "x-dc"
        for fn in script.get("functions") or []:
            name = fn.get("functionName") or ""
            if not name:
                continue
            ranges = fn.get("ranges") or []
            if not ranges:
                continue
            outer = max(ranges, key=lambda r: r["endOffset"] - r["startOffset"])
            key = f"{name} [{tag}]"
            counts[key] = max(counts.get(key, 0), int(outer.get("count") or 0))
    return {"counts": counts, "census": census}


def medof(rows: "list[dict]", key: str) -> float:
    vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return statistics.median(vals) if vals else 0.0


def med_map(rows: "list[dict]", key: str) -> "dict[str, float]":
    names = set()
    for r in rows:
        names |= set((r.get(key) or {}).keys())
    return {n: statistics.median([(r.get(key) or {}).get(n, 0.0) for r in rows])
            for n in names}


def report(label: str, rows: "list[dict]", top: int) -> None:
    if not rows:
        print(f"\n=== {label}: NO RUNS ===")
        return
    task = medof(rows, "task_ms")
    prof = medof(rows, "prof_ms")
    cen = rows[0]["census"]
    print(f"\n=== {label}   median of {len(rows)} cold runs ===")
    print(f"  react FunctionCall task      {task:>9.1f} ms")
    print(f"  profiler samples in window   {int(medof(rows, 'prof_samples')):>9d}"
          f"   ({prof:.1f} ms accounted)")
    if task and abs(prof - task) / task > 0.25:
        print("  !! profile and trace disagree by >25% -- clocks may not share a"
              " base; treat shares, not absolutes")
    print(f"  DOM at settle                {cen['svgs']:>9d} svg, "
          f"{cen['paths']} path, {cen['nodes']} nodes, "
          f"{cen['grads']} gradients, {cen['clips']} clipPaths")
    print(f"  path data                    {cen['pathDataBytes']:>9d} bytes total,"
          f" {cen['biggestPathBytes']} biggest")
    errs = [e for r in rows for e in r.get("errors") or []]
    if errs:
        print(f"  !! page errors: {errs[:3]}")

    print("\n  --- inside the task, by REACT CYCLE PHASE ---")
    cy = med_map(rows, "cycle")
    cyt = sum(cy.values()) or 1.0
    for name, ms in sorted(cy.items(), key=lambda kv: -kv[1]):
        if ms < 0.05:
            continue
        print(f"    {name:<34}{ms:>8.1f} ms  {100 * ms / cyt:>5.1f}%")

    # The one thing no trace event can show: how many full renders are inside
    # this single task. React flushes a didMount setState before yielding, so the
    # boundaries are invisible from outside and only the sample order finds them.
    mid0 = sorted(rows, key=lambda r: r["task_ms"])[len(rows) // 2]
    segs = [s for s in (mid0.get("timeline") or []) if s[2] >= 1.5]
    print("  --- the same task as a timeline (segments >= 1.5ms, median run) ---")
    for label, at, ms in segs:
        print(f"    +{at:>7.1f} ms   {ms:>7.1f} ms   {label}")
    nrender = sum(1 for i, s in enumerate(segs)
                  if s[0].startswith("render") and
                  (i == 0 or not segs[i - 1][0].startswith("render")))
    print(f"    => {nrender} separate render pass(es) inside this ONE task")

    print("\n  --- inside the task, by SELF time (disjoint buckets) ---")
    b = med_map(rows, "buckets")
    tot = sum(b.values()) or 1.0
    for name, ms in sorted(b.items(), key=lambda kv: -kv[1]):
        if ms < 0.05:
            continue
        print(f"    {name:<34}{ms:>8.1f} ms  {100 * ms / tot:>5.1f}%")
    print(f"    {'TOTAL':<34}{tot:>8.1f} ms")

    print(f"\n  --- hottest functions by self time (top {top}) ---")
    s = med_map(rows, "self")
    for name, ms in sorted(s.items(), key=lambda kv: -kv[1])[:top]:
        if ms < 0.05:
            continue
        print(f"    {name:<58}{ms:>8.1f} ms")

    # READ THESE TWO LINES FOR THEIR NAMED PHASES, NOT THEIR TOTALS. The window
    # excludes the render task, but the scheduler RunTask that ENCLOSES it starts
    # before the window ends, so it is admitted while its excluded child is not
    # subtracted -- and its whole duration lands in one bucket. "script execute"
    # and "style + layout" are trustworthy; "other" carries that artefact. What
    # the line is here to answer is whether a SECOND long task exists before the
    # render, and "longest main-thread tasks" below answers that directly.
    print("\n  --- main-thread trace phases OUTSIDE the task ---")
    for tag, key in (("before it (parse, compile, fetch)", "pre_phases"),
                     ("after it (style, layout, paint)", "post_phases")):
        ph = med_map(rows, key)
        line = "  ".join(f"{k}={v:.1f}" for k, v in
                         sorted(ph.items(), key=lambda kv: -kv[1]) if v >= 0.5)
        print(f"    {tag}: {line or '(nothing >= 0.5ms)'}")

    mid = rows[len(rows) // 2]
    lt = mid.get("tasks") or []
    pu = med_map(rows, "pre_by_url")
    print("    before it, by script (inclusive): "
          + ", ".join(f"{k}={v:.1f}" for k, v in
                      sorted(pu.items(), key=lambda kv: -kv[1])[:5]))
    print("    longest main-thread tasks: "
          + ", ".join(f"{t['d']:.0f}ms" for t in lt[:5]))
    print("    React FunctionCalls: "
          + ", ".join(f"{r['d']:.0f}ms {r['url']}:{r['line']}"
                      for r in (mid.get("react_calls") or [])[:4]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--viewport", default="1440x900")
    ap.add_argument("--throttle", action="append", type=int, default=[],
                    help="CPU throttling rates; default 1, 4, 6")
    ap.add_argument("--query", action="append", default=[],
                    help="query strings to compare; default '' and '?who=charles'")
    ap.add_argument("--families", action="store_true",
                    help="one run per dealt family at ?who=charles&kind=<name>")
    ap.add_argument("--coverage", action="store_true",
                    help="also take a call-count pass (unthrottled, untimed)")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260731)
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("--top", type=int, default=18)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json", help="every run, unrounded")
    a = ap.parse_args()

    w, h = (int(x) for x in a.viewport.lower().split("x"))
    rates = a.throttle or [1, 4, 6]
    queries = a.query or ["", "?who=charles"]
    if a.families:
        queries = [f"?who=charles&kind={f}" for f in FAMILIES]

    srv, base = pc.serve(a.root, True)
    everything: "list[dict]" = []
    try:
        print(f"serving {a.root} at {base}  viewport {w}x{h}  "
              f"runs {a.runs}  seed {a.seed}")
        for q in queries:
            for rate in rates:
                rows = asyncio.run(measure(base + q, (w, h), rate, a.runs,
                                           a.seed, a.settle))
                everything += rows
                report(f"{q or '(combined stage)'}   CPU {rate}x", rows, a.top)
        if a.coverage:
            for q in queries:
                cov = asyncio.run(coverage(base + q, (w, h), a.seed, a.settle))
                print(f"\n=== call counts, {q or '(combined stage)'}  "
                      f"(1 cold load, unthrottled, TIMES NOT VALID) ===")
                print(f"  {cov['census']['svgs']} svg, "
                      f"{cov['census']['paths']} path")
                for name, n in sorted(cov["counts"].items(),
                                      key=lambda kv: -kv[1])[:a.top]:
                    print(f"    {name:<58}{n:>10d}")
                interesting = ("renderVals", "gearSvg", "solve", "teethPath",
                               "engraving", "ghostSvg", "fitStage", "render",
                               "datumLayer", "wearWheels", "dealCentres")
                print("  -- the ones this ticket is about --")
                for want in interesting:
                    for name, n in sorted(cov["counts"].items()):
                        if name.split(" [")[0] == want:
                            print(f"    {name:<58}{n:>10d}")
                everything.append({"coverage": cov, "url": q})
    finally:
        srv.shutdown()

    if a.json:
        with open(a.json, "w") as fh:
            json.dump(everything, fh, indent=1)
        print(f"\nwrote {a.json}")
    return 0 if everything else 2


if __name__ == "__main__":
    sys.exit(main())
