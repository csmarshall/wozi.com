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

THE WEBFONT IS PINNED, AND NOT FOR THE REASON THE OTHER HARNESSES PIN IT (GitHub
#145). Nothing measured here is a type measurement: the rotations, the
dashoffsets and the badge offsets were all measured with both font hosts
blackholed and every one of them came back the same -- 40 of 40 advancing, 0
strands, badge offsets 0.00-0.01px either way. The exposure is in check 3.

**"No console errors" is an assertion about the network as long as the font is on
it.** With fonts.googleapis.com unreachable this file went from `console errors:
0  RESULT: PASS` to `console errors: 3  RESULT: CHECK ABOVE`, on an unchanged
page -- three `ERR_CONNECTION_REFUSED` Log entries for one stylesheet. So a
Google Fonts outage, or a runner with no egress, turned THE gate CI runs on every
push red for something that is not the code. Pinning removes the request
entirely; a run that degrades to `blocked` announces itself and then tolerates
font-host errors, because failing a run for the state it chose out loud is not a
finding. In `pinned` mode a font-host error is still fatal: nothing should reach
the network at all, so one that does means the pin leaked.

The fixed 3.5s sleep is gone with it. A plain sleep in the render path HOLDS the
stylesheet for its duration and lets it land afterwards, which is the late-font
regime itself -- see tools/fontpin.py. What replaces it is a condition: loaded
and fonts.ready settled, then the element census stable.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
import urllib.request

import websockets

import os as _os, shutil as _sh, sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import fontpin  # noqa: E402


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
# The URL stays POSITIONAL and optional: CI and tools/mutation_gate.py both
# append the served URL to this argv and neither should have to learn a flag.
_ap = argparse.ArgumentParser(description="is the gear train actually turning")
_ap.add_argument("url", nargs="?", default="http://127.0.0.1:8765/")
_ap.add_argument("--fonts", default="auto", choices=["auto", "pinned", "blocked"],
                 help="auto: serve the webfont from prefetched bytes, degrading "
                      "loudly to blocked if it cannot be fetched. pinned: require "
                      "it, exit 2 if unobtainable. blocked: never fetch it — "
                      "font-host request failures are then expected and tolerated.")
_ARGS = _ap.parse_args()
URL = _ARGS.url
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

# How many wheels, badges and rotating elements the page is showing. Not a
# measurement -- a settle condition: the escape-run ghosts arrive out of the fit
# pass a beat after first paint, so a census taken at load-complete counts a
# partly built stage.
CENSUS_JS = ("(()=>{const n=(s)=>document.querySelectorAll(s).length;"
             "return n('svg')+'/'+n('a[href]')+'/'+n('[transform]');})()")
# How long the stage may go on gaining elements after the page reports itself
# loaded. Reaching it is a hard failure, not a fallback.
CENSUS_TIMEOUT_S = 15.0
# And then how long the flywheel is given to leave rest. This one IS a duration
# and cannot honestly be a condition: "every sampled rotation advanced" is the
# assertion this file makes, so waiting for it before asserting it would be the
# gate agreeing with itself. It is safe where the retired 3.5s was not, because
# it happens AFTER fonts.ready has settled -- it holds no stylesheet and lets
# nothing land late. The train leaves rest in one frame; this is slack, not a
# tuned figure.
SPINUP_S = 0.6


async def settle_census(send, pump, timeout=CENSUS_TIMEOUT_S):
    """Wait until two consecutive reads of CENSUS_JS agree. Returns the seconds it
    took, so a slow page is reported rather than only an impossible one."""
    t0 = time.monotonic()
    prev = None
    while time.monotonic() - t0 < timeout:
        r = await send("Runtime.evaluate", {"expression": CENSUS_JS,
                                           "returnByValue": True})
        now = r.get("result", {}).get("value")
        if now and now == prev:
            return time.monotonic() - t0
        prev = now
        await pump(0.1)
    raise SystemExit(
        f"FATAL: the stage never stopped gaining elements — two reads of its "
        f"census still disagree after {timeout}s. Nothing has been measured, so "
        f"nothing has been proved.")


async def cdp(pin):
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--window-size=1440,900",
         "--no-first-run", *CI_FLAGS, "--no-default-browser-check",
         "--disable-features=Translate", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(50):
        # about:blank, NOT the page. Asking /json/new for the URL directly makes
        # the tab navigate before Fetch interception is armed, so that first
        # navigation fetches the stylesheet off the network and warms the cache
        # for the measured one -- a pin installed after it is decoration.
        for method in (None, "PUT"):  # older Chrome requires PUT on /json/new
            try:
                target = f"http://127.0.0.1:{PORT}/json/new?about:blank"
                req = urllib.request.Request(target, method=method) if method else target
                with urllib.request.urlopen(req, timeout=1) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass
        if ws_url:
            break
        time.sleep(0.2)
    if not ws_url:
        proc.kill()
        print("FATAL: could not reach Chrome DevTools endpoint")
        return 2

    errors = []

    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        def watch(msg):
            """Errors off EVERY message, not only the ones that happen to arrive
            while a reply is pending. This lived inside the old send()'s own recv
            loop; it is a callback now because fontpin.attach owns the socket."""
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

        # send/pump/wait_until come from fontpin: a paused font request arrives
        # UNSOLICITED and must be answered, and the loop-until-my-id send this
        # file used to carry threw exactly that message away.
        send, pump, wait_until = fontpin.attach(ws, pin, on_message=watch)

        async def evaluate(expr):
            r = await send("Runtime.evaluate",
                           {"expression": expr, "returnByValue": True,
                            "awaitPromise": True})
            return r.get("result", {}).get("value")

        await send("Runtime.enable")
        await send("Log.enable")
        # Page.enable BEFORE the injection fontpin.install() makes, or it is
        # accepted and silently never runs.
        await send("Page.enable")
        await pin.install(send)
        await send("Page.navigate", {"url": URL})
        # CONDITIONS, not the retired 3.5s: loaded and fonts.ready settled, then
        # the element census stable. Only the spin-up slack is still a duration,
        # and it now sits entirely after the font has arrived.
        await fontpin.wait_ready(send, pump, wait_until, what="the page")
        settled = await settle_census(send, pump)
        await pump(SPINUP_S)

        s1 = json.loads(await evaluate(SAMPLE_JS))
        # pump, not asyncio.sleep: a sleep here answers no paused request and can
        # hang the page on its own stylesheet.
        await pump(0.7)
        s2 = json.loads(await evaluate(SAMPLE_JS))
        badges = json.loads(await evaluate(BADGE_JS))
        title = await evaluate("document.title")
        icons = await evaluate(
            "document.querySelectorAll('a[href] svg').length")
        # AFTER the measurement, never before: the probe appends and removes a
        # span, and a font state read before the page was measured says nothing
        # about the render that was.
        await pin.state(send, label="the sample")

    proc.kill()

    rot_changed = sum(1 for a, b in zip(s1["rot"], s2["rot"]) if a != b)
    dash_changed = sum(1 for a, b in zip(s1["dash"], s2["dash"]) if a != b)

    print(f"title              : {title}")
    print(f"census settled in  : {settled:.2f}s after load + fonts.ready")
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
    print(f"font state         : {pin.states.get('the sample', '?')} "
          f"(expected {pin.expect!r}, {pin.mode})")

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
    # WHAT COUNTS AS A REAL ERROR, and the font is why this list has a second
    # entry (GitHub #145). A run that has ANNOUNCED itself as blocked cannot then
    # be failed for the font host refusing to answer -- that is the state it
    # chose, out loud, and Chrome logs it as an error either way. In `pinned`
    # mode the same line is still fatal: every font request is fulfilled from
    # memory, so one that reached the network at all means the pin leaked.
    font_noise = (lambda e: any(h in e for h in fontpin.FONT_HOSTS)
                  ) if pin.mode == "blocked" else (lambda e: False)
    real_errors = [e for e in errors
                   if "favicon.ico" not in e and not font_noise(e)]
    tolerated = len(errors) - len(real_errors)
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
    # pin.report() is part of the verdict, not a footnote: a render that did not
    # draw in the state this run chose has not been shown to be about the code.
    font_ok = pin.report()
    if tolerated:
        print(f"                     ({tolerated} font-host error(s) tolerated — "
              f"this run is deliberately {pin.mode})")
    ok = (rot_changed == len(s1["rot"]) and len(s1["rot"]) > 0
          and dash_ok and not real_errors and worst < 2.0
          and _want > 0 and icons == _want and font_ok)
    if not _want:
        print("hub icons          : no badge links on the page at all")
    elif icons != _want:
        print(f"hub icons          : {icons} injected, expected {_want} (one per badge link)")
    print("\nstrands            :",
          "none (correct for the direct-mesh train)" if not s1["dash"]
          else f"{len(s1['dash'])} present, {dash_changed} advancing")
    print("RESULT:", "PASS" if ok else "CHECK ABOVE")
    return 0 if ok else 1


def main():
    # THE FONT DECISION IS TAKEN BEFORE CHROME EXISTS, and that ordering is the
    # whole mechanism. The stylesheet URL comes off the SERVED page, because this
    # harness is pointed at a server somebody else started and it may be serving
    # another worktree entirely.
    pin = fontpin.FontPin.decide(want=_ARGS.fonts, url=URL)
    fatal = pin.announce()
    if fatal:
        print(fatal)
        return 2
    return asyncio.run(cdp(pin))


sys.exit(main())
