#!/usr/bin/env python3
"""Verify the wozi.com gear train is actually turning.

A static train photographs perfectly (CHANGELOG #7), so a screenshot proves
nothing. This drives headless Chrome over CDP, samples the live DOM twice ~700ms
apart, and reports whether the values that must advance actually advanced.

Checks, per CLAUDE.md "Verifying a change":
  1. gear transform values advance
  2. stroke-dashoffset on the chain/belt paths is non-empty and changing
  3. no console errors
  4. hub badges sit at ~0px offset from their wheel centres
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

SAMPLE_JS = r"""
(() => {
  const norm = (s) => (s || '').trim();
  const rot = [];
  document.querySelectorAll('[transform]').forEach((el) => {
    const t = norm(el.getAttribute('transform'));
    /* animated rotations use deg; unitless rotate() attributes are static
       placement wrappers (the planetary's 120-degree planet seats) */
    if (/rotate\([-0-9.]+deg/i.test(t)) rot.push(t);
  });
  document.querySelectorAll('*').forEach((el) => {
    const t = el.style && norm(el.style.transform);
    if (t && /rotate/i.test(t)) rot.push(t);
  });
  const dash = [];
  document.querySelectorAll('[stroke-dashoffset], path, polyline').forEach((el) => {
    const a = norm(el.getAttribute && el.getAttribute('stroke-dashoffset'));
    const s = el.style && norm(el.style.strokeDashoffset);
    const v = s || a;
    if (v) dash.push(v);
  });
  return JSON.stringify({ rot: rot.slice(0, 40), dash: dash.slice(0, 40) });
})()
"""

BADGE_JS = r"""
(() => {
  // Each hub badge is an <a> inside the stage. Its centre should coincide with
  // the centre of the wheel it is seated on. Compare against the nearest wheel
  // <svg>'s centre and report the worst offset.
  const wheels = [...document.querySelectorAll('svg')].map((s) => {
    const r = s.getBoundingClientRect();
    return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width };
  }).filter((w) => w.w > 40);
  const out = [];
  document.querySelectorAll('a[href]').forEach((a) => {
    const r = a.getBoundingClientRect();
    if (!r.width) return;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    let best = null, bd = Infinity;
    wheels.forEach((w) => {
      const d = Math.hypot(cx - w.cx, cy - w.cy);
      if (d < bd) { bd = d; best = w; }
    });
    if (best) out.push({ href: a.getAttribute('href'), off: +bd.toFixed(2) });
  });
  return JSON.stringify({ wheels: wheels.length, badges: out });
})()
"""


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

        s1 = json.loads(await evaluate(SAMPLE_JS))
        await asyncio.sleep(0.7)
        s2 = json.loads(await evaluate(SAMPLE_JS))
        badges = json.loads(await evaluate(BADGE_JS))
        title = await evaluate("document.title")
        icons = await evaluate(
            "document.querySelectorAll('a[href] svg').length")

    proc.kill()

    rot_changed = sum(1 for a, b in zip(s1["rot"], s2["rot"]) if a != b)
    dash_changed = sum(1 for a, b in zip(s1["dash"], s2["dash"]) if a != b)

    print(f"title              : {title}")
    print(f"rotating elements  : {len(s1['rot'])} sampled, {rot_changed} advanced in 700ms")
    print(f"dashoffset values  : {len(s1['dash'])} sampled, {dash_changed} changed in 700ms")
    print(f"hub icons injected : {icons} <svg> inside badge links")
    print(f"wheels measured    : {badges['wheels']}")
    worst = 0.0
    for b in badges["badges"]:
        worst = max(worst, b["off"])
        print(f"  badge {b['href'][:44]:<46} offset {b['off']}px")
    print(f"console errors     : {len(errors)}")
    for e in errors[:10]:
        print("  " + e)

    if s1["rot"][:3]:
        print("\nsample rot [0] t1 :", s1["rot"][0][:90])
        print("sample rot [0] t2 :", s2["rot"][0][:90])
    if s1["dash"][:1]:
        print("sample dash[0] t1 :", s1["dash"][0][:90])
        print("sample dash[0] t2 :", s2["dash"][0][:90])

    # The shipped train is direct-mesh, so there are no strands and no
    # stroke-dashoffset anywhere. Absent is correct; only a strand that exists
    # and is NOT moving is a failure.
    dash_ok = len(s1["dash"]) == 0 or dash_changed > 0
    real_errors = [e for e in errors if "favicon.ico" not in e]
    # THE EXPECTATION IS MEASURED, NOT PARSED. This used to re-derive the wheel
    # count by walking config.js and counting `href:` across the whole PEOPLE
    # block -- a copy of page geometry living in a harness, which is the hazard
    # this repo has been bitten by repeatedly. It was also wrong the moment a
    # SECOND person existed: only one chain is ever on stage, so summing every
    # person's links expected 8 icons on a 7-wheel page and reported CHECK ABOVE
    # against a page that was fine.
    #
    # What CLAUDE.md actually asks is "each badge contains an <svg>", and both
    # sides of that are on the page: count the badge links, count the ones with
    # an icon inside, compare. No config parsing, correct for any chain, and it
    # still catches the failure it was written for -- loadIcons() fetches the
    # icons and swallows its own error, so a file:// open leaves empty badges.
    _want = len(badges["badges"])
    ok = (rot_changed == len(s1["rot"]) and len(s1["rot"]) > 0
          and dash_ok and not real_errors and worst < 2.0
          and _want > 0 and icons == _want)
    if not _want:
        print("hub icons          : no badge links on the page at all")
    elif icons != _want:
        print(f"hub icons          : {icons} injected, expected {_want} (one per badge link)")
    print("\nstrands            :",
          "none (correct for the direct-mesh train)" if not s1["dash"]
          else f"{len(s1['dash'])} present, {dash_changed} advancing")
    print("RESULT:", "PASS" if ok else "CHECK ABOVE")
    return 0 if ok else 1


sys.exit(asyncio.run(cdp()))
