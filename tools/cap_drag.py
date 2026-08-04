#!/usr/bin/env python3
"""Does a magnetic hub cap actually pull off the axle, and spring back?

The point of this harness is the WAIT. Every previous pointer test dispatched
the press and the first move in the same task, so no animation frame ran in
between -- and that is the one thing a real hand can never do. Pressing and
then moving, with frames in between, is what exposed the cap drag being dead:
the spring loop deleted the brand-new (settled, undragged) entry on the first
frame, and every later move mutated an orphan.

So: press, let frames pass, move in steps, measure, release, let it settle,
measure again.

The second phase is the OTHER cap (#78). Everything about badge interaction --
the spring entry, the element reference, the drag claim, the hover -- used to be
keyed by service slug alone, which was unique only for as long as one chain was
ever on stage. Two people who both own a `mail` wheel share the key, so dragging
one cap dragged the other and hovering one lit the other. This phase is the case
that shape can fail: find a service TWO chains carry, work one of them, and
assert the far one never twitched. Phase one alone cannot see it -- it only ever
touched a single chain, which is exactly why the bug shipped.

The third phase is the CLICK AFTER THE FLICK (#92). Letting go of a cap while
the pointer is still moving lands the release on empty stage -- the cap tracks
the pointer a frame behind, so it is no longer under it -- and the browser then
fires `click` on the common ancestor of press and release rather than on the
anchor. The drag-suppression flag was cleared only by the anchor's own click
handler, so after that gesture it survived, and the next real click on that cap
was spent clearing it instead of following the link. This phase flicks, then
clicks for real, and asserts the second click was not swallowed. It also keeps
the original guarantee honest in the same breath: a drag that DOES end on the
anchor must still have its click suppressed, or a drag would count as an
outbound visit.

Usage: tools/cap_drag.py [url] [port]
Exit 0 only if the cap moves under drag, returns after release, the same-named
cap on the other chain is untouched by either, and a flick does not eat the
click that follows it.
"""

import asyncio
import json
import subprocess
import sys
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
# THE PORT IS NOT FIXED (#42). Every harness here used a hardcoded DevTools
# port, so two running at once fought over it and the loser reported a
# ConnectionClosedError -- which reads as a page fault, not a harness fault, and
# wasted real time this session more than once. Bind to whatever the OS gives
# us, and honour CDP_PORT if a caller wants a specific one.
import os  # for CDP_PORT, below
def _free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]; s.close()
    return p
PORT = (int(sys.argv[2]) if len(sys.argv) > 2
        else int(os.environ.get("CDP_PORT") or 0) or _free_port())
PROFILE = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad/chrome-cap"

FIND = r"""
(() => {
  const as = [...document.querySelectorAll('a[href]')].filter(a => a.getAttribute('aria-label')
             && a.getBoundingClientRect().width > 20);
  if (!as.length) return JSON.stringify({ error: 'no badges' });
  const a = as[Math.min(2, as.length - 1)];
  const r = a.getBoundingClientRect();
  window.__cap = a;
  return JSON.stringify({ label: a.getAttribute('aria-label'),
                          x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width });
})()
"""

READ = "(() => window.__cap ? (window.__cap.style.transform || '(none)') : 'no cap')()"

# TWO CHAINS, ONE SERVICE NAME. On a combined stage the accessible name is
# "<service>, <person>", so the text before the first comma is the service and
# what follows is who owns that wheel. Group by the service, and any group with
# two members is a pair the old slug-only keying could not tell apart. Nothing
# here reads a slug -- the page never exposes one -- so the harness matches on
# what a screen reader would hear, which is the same thing a person sees.
FIND_PAIR = r"""
(() => {
  const as = [...document.querySelectorAll('a[href]')].filter(a => a.getAttribute('aria-label')
             && a.getBoundingClientRect().width > 20);
  const by = {};
  as.forEach(a => {
    const name = a.getAttribute('aria-label');
    const svc = name.split(',')[0].trim();
    (by[svc] = by[svc] || []).push(a);
  });
  const svc = Object.keys(by).filter(k => by[k].length > 1)[0];
  if (!svc) return JSON.stringify({ error: 'no service is on two chains' });
  const [a, b] = by[svc];
  window.__capA = a; window.__capB = b;
  const box = (el) => { const r = el.getBoundingClientRect();
    return { label: el.getAttribute('aria-label'),
             x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width }; };
  return JSON.stringify({ svc: svc, a: box(a), b: box(b) });
})()
"""

# WHAT A SWALLOWED CLICK LOOKS LIKE FROM OUTSIDE. There is no way to read the
# component's private flag, and asking for one would be testing the fix rather
# than the behaviour. What a person experiences is "the link did nothing", and
# the browser's word for that is defaultPrevented -- so listen on `document` in
# the bubble phase, which runs AFTER React's delegated handler at the root, and
# record whether the anchor's guard had cancelled the click by then. The
# listener cancels the click itself afterwards, because a link that really does
# navigate would take the page out from under the rest of the run.
CLICK_PROBE = r"""
(() => {
  window.__clicks = [];
  document.addEventListener('click', (e) => {
    window.__clicks.push({
      onCap: !!(window.__cap && (window.__cap === e.target || window.__cap.contains(e.target))),
      prevented: e.defaultPrevented });
    e.preventDefault();
  }, false);
  return 'ok';
})()
"""

# Where the cap is NOW -- after a release it springs home, and the genuine click
# has to land on the axle it came back to, not the coordinate it was let go at.
CAP_POS = r"""
(() => { const r = window.__cap.getBoundingClientRect();
         return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); })()
"""

# Both caps in one read, so the two are always sampled on the same frame.
READ_PAIR = r"""
(() => {
  const of = (el) => el ? { t: el.style.transform || '(none)',
                            w: el.getBoundingClientRect().width } : null;
  return JSON.stringify({ a: of(window.__capA), b: of(window.__capB) });
})()
"""


def scale_of(transform):
    """Pull the badge scale out of '... scale(1.06)'. 1.0 when it says nothing."""
    if "scale(" not in transform:
        return 1.0
    try:
        return float(transform.split("scale(")[-1].split(")")[0])
    except ValueError:
        return 1.0


def offset_of(transform):
    """Pull the drag translate out of 'translate(-50%,-50%) translate(12.3px,4.5px) scale(1)'."""
    parts = [p for p in transform.split("translate(") if "px" in p]
    if not parts:
        return 0.0
    inner = parts[-1].split(")")[0]
    try:
        xs, ys = inner.split(",")
        return (float(xs.replace("px", "")) ** 2 + float(ys.replace("px", "")) ** 2) ** 0.5
    except ValueError:
        return 0.0


async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={PROFILE}", "--window-size=1440,900",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ws_url = None
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{URL}", timeout=1) as r:
                ws_url = json.load(r)["webSocketDebuggerUrl"]
                break
        except Exception:
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
                with urllib.request.urlopen(req, timeout=1) as r:
                    ws_url = json.load(r)["webSocketDebuggerUrl"]
                    break
            except Exception:
                time.sleep(0.2)
    if not ws_url:
        proc.kill()
        print("FATAL: no DevTools endpoint")
        return 2

    mid = 0
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        async def send(method, params=None):
            nonlocal mid
            mid += 1
            my = mid
            await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})

        async def ev(expr):
            r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
            return r.get("result", {}).get("value")

        async def mouse(kind, x, y, buttons=0, button="none"):
            await send("Input.dispatchMouseEvent", {
                "type": kind, "x": x, "y": y, "button": button,
                "buttons": buttons, "clickCount": 1 if button != "none" else 0,
                "pointerType": "mouse"})

        await asyncio.sleep(2.2)
        cap = json.loads(await ev(FIND))
        if "error" in cap:
            proc.kill()
            print("FATAL:", cap["error"])
            return 2
        x, y = cap["x"], cap["y"]
        print(f"cap: {cap['label']}  at ({x:.0f},{y:.0f})  {cap['w']:.0f}px across\n")

        await mouse("mouseMoved", x, y)
        await asyncio.sleep(0.25)
        await mouse("mousePressed", x, y, buttons=1, button="left")

        # THE WAIT. This is the whole point: let animation frames run between
        # the press and the first move, the way a hand does.
        await asyncio.sleep(0.20)
        held = offset_of(await ev(READ))

        for i in range(1, 13):
            await mouse("mouseMoved", x + i * 7, y + i * 3, buttons=1, button="left")
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.05)
        dragged = offset_of(await ev(READ))
        transform = await ev(READ)

        await mouse("mouseReleased", x + 84, y + 36, buttons=0, button="left")
        await asyncio.sleep(0.9)
        settled = offset_of(await ev(READ))

        # ---- PHASE TWO: the far chain's cap of the same name (#78) -----------
        # A fresh load before each half, because the point of the measurement is
        # that the far cap was NEVER touched -- leftover drag or hover state from
        # the phase above would be a second explanation for anything seen here.
        pair = {}
        async def reload():
            await ev("location.reload()")
            await asyncio.sleep(2.2)

        await reload()
        found = json.loads(await ev(FIND_PAIR))
        if "error" in found:
            pair["skip"] = found["error"]
        else:
            ax, ay = found["a"]["x"], found["a"]["y"]
            pair["svc"] = found["svc"]
            pair["a_label"] = found["a"]["label"]
            pair["b_label"] = found["b"]["label"]

            # DRAG the near cap, watch the far one.
            await mouse("mouseMoved", ax, ay)
            await asyncio.sleep(0.25)
            await mouse("mousePressed", ax, ay, buttons=1, button="left")
            await asyncio.sleep(0.20)          # frames between press and move
            for i in range(1, 13):
                await mouse("mouseMoved", ax + i * 7, ay + i * 3, buttons=1, button="left")
                await asyncio.sleep(0.02)
            await asyncio.sleep(0.05)
            during = json.loads(await ev(READ_PAIR))
            pair["a_drag"] = offset_of(during["a"]["t"])
            pair["b_drag"] = offset_of(during["b"]["t"])
            pair["b_drag_t"] = during["b"]["t"]
            await mouse("mouseReleased", ax + 84, ay + 36, buttons=0, button="left")
            # AND IMMEDIATELY AFTER RELEASE, which is where the far cap was
            # actually seen to jump. Only the pressed element is written by the
            # spring loop, so while the drag is live the far cap simply holds
            # whatever transform it last rendered with -- it is the forceUpdate
            # on release that hands it the shared offset, and it then sits out
            # at arm's length while the near one springs home. Sampled before
            # the spring has travelled, so the number is the offset, not a
            # fraction of it.
            await asyncio.sleep(0.08)
            after = json.loads(await ev(READ_PAIR))
            pair["b_release"] = offset_of(after["b"]["t"])
            pair["b_release_t"] = after["b"]["t"]
            await asyncio.sleep(0.9)

            # HOVER the near cap, watch the far one. The plate grows into a pill
            # when it is on, so its rendered WIDTH is the honest probe -- scale
            # alone would miss a pill that opened without the badge growing.
            await reload()
            found = json.loads(await ev(FIND_PAIR))
            ax, ay = found["a"]["x"], found["a"]["y"]
            rest = json.loads(await ev(READ_PAIR))
            await mouse("mouseMoved", ax, ay)
            await asyncio.sleep(0.45)          # past the .26s pill transition
            hot = json.loads(await ev(READ_PAIR))
            pair["a_grew"] = hot["a"]["w"] - rest["a"]["w"]
            pair["b_grew"] = hot["b"]["w"] - rest["b"]["w"]
            pair["a_scale"] = scale_of(hot["a"]["t"])
            pair["b_scale"] = scale_of(hot["b"]["t"])

        # ---- PHASE THREE: the click after the gesture (#92) ------------------
        # Two gestures, each followed by a genuine click on the same cap. The
        # only difference between them is whether a frame runs before the
        # release, which is the whole of the bug: with one, the cap has caught
        # up and the release lands on it; without, it has not and the release
        # lands on the stage behind.
        async def drag_then_click(fast):
            await reload()
            here = json.loads(await ev(FIND))
            await ev(CLICK_PROBE)
            x0, y0 = here["x"], here["y"]
            await mouse("mouseMoved", x0, y0)
            await asyncio.sleep(0.25)
            await mouse("mousePressed", x0, y0, buttons=1, button="left")
            await asyncio.sleep(0.20)          # frames between press and move
            if fast:
                for i in range(1, 7):
                    await mouse("mouseMoved", x0 + i * 7, y0 + i * 3, buttons=1, button="left")
                    await asyncio.sleep(0.02)
                # THE FLICK: one long throw and the release in the SAME task, so
                # no frame runs between them and the cap is still where it was.
                # This is a hand letting go mid-movement, which is how a magnet
                # you can pull all the way off is normally put down.
                await mouse("mouseMoved", x0 + 420, y0 + 180, buttons=1, button="left")
                await mouse("mouseReleased", x0 + 420, y0 + 180, buttons=0, button="left")
            else:
                for i in range(1, 13):
                    await mouse("mouseMoved", x0 + i * 7, y0 + i * 3, buttons=1, button="left")
                    await asyncio.sleep(0.02)
                await asyncio.sleep(0.05)      # a frame, so the cap catches up
                await mouse("mouseReleased", x0 + 84, y0 + 36, buttons=0, button="left")
            await asyncio.sleep(0.3)
            during = json.loads(await ev("JSON.stringify(window.__clicks)"))
            await asyncio.sleep(1.2)           # let the spring carry it home
            home = json.loads(await ev(CAP_POS))
            await ev("window.__clicks = []")
            await mouse("mouseMoved", home["x"], home["y"])
            await asyncio.sleep(0.2)
            await mouse("mousePressed", home["x"], home["y"], buttons=1, button="left")
            await asyncio.sleep(0.12)
            await mouse("mouseReleased", home["x"], home["y"], buttons=0, button="left")
            await asyncio.sleep(0.3)
            after = json.loads(await ev("JSON.stringify(window.__clicks)"))
            return (during[0] if during else None), (after[0] if after else None)

        away_release, after_away = await drag_then_click(True)
        on_release, after_on = await drag_then_click(False)

    proc.kill()

    print(f"after press, before moving : {held:.1f}px   (should be ~0)")
    print(f"after an 84x36 drag        : {dragged:.1f}px")
    print(f"  transform: {transform}")
    print(f"0.9s after release         : {settled:.1f}px   (should be back near 0)\n")

    ok = dragged > 20 and settled < 6
    if dragged <= 20:
        print("FAIL: the cap did not move under drag.")
    elif settled >= 6:
        print("FAIL: the cap did not spring home.")
    else:
        print("PASS: cap pulls off the axle and springs back.")

    print()
    if "skip" in pair:
        # Not a failure: a solo page has one chain and no pair to confuse.
        print(f"two chains  : SKIP -- {pair['skip']}")
    else:
        print(f"two chains  : \"{pair['svc']}\" is on both")
        print(f"  near cap  : {pair['a_label']}")
        print(f"  far cap   : {pair['b_label']}")
        print(f"dragging the near cap  : near {pair['a_drag']:.1f}px, "
              f"far {pair['b_drag']:.1f}px   (far should be ~0)")
        print(f"  far transform: {pair['b_drag_t']}")
        print(f"just after release     : far {pair['b_release']:.1f}px   (far should be ~0)")
        print(f"  far transform: {pair['b_release_t']}")
        print(f"hovering the near cap  : near +{pair['a_grew']:.1f}px wide "
              f"(scale {pair['a_scale']:.2f}), far +{pair['b_grew']:.1f}px wide "
              f"(scale {pair['b_scale']:.2f})   (far should be +0)")
        print()
        if pair["a_drag"] <= 20:
            print("FAIL: the near cap did not move, so the far one proves nothing.")
            ok = False
        elif pair["b_drag"] >= 2 or pair["b_release"] >= 2:
            print("FAIL: dragging one chain's cap moved the same-named cap on the other.")
            ok = False
        else:
            print("PASS: the far cap did not move under the near cap's drag.")
        if pair["a_grew"] <= 2:
            print("FAIL: hovering the near cap did not open it, so the far one proves nothing.")
            ok = False
        elif pair["b_grew"] >= 2 or pair["b_scale"] > 1.02:
            print("FAIL: hovering one chain's cap lit the same-named cap on the other.")
            ok = False
        else:
            print("PASS: the far cap stayed dark and shut while the near one was hovered.")

    print()
    say = lambda c: "no click at all" if c is None else (
        ("on the cap" if c["onCap"] else "somewhere else") +
        (", swallowed" if c["prevented"] else ", allowed through"))
    print(f"flick, release mid-move    : {say(away_release)}")
    print(f"  then a genuine click     : {say(after_away)}   (must be allowed through)")
    print(f"drag, release on the cap   : {say(on_release)}   (must be swallowed)")
    print(f"  then a genuine click     : {say(after_on)}   (must be allowed through)")
    print()

    # The flick only proves anything if it actually released off the anchor. If
    # the cap caught up, this run reproduced the ordinary drag twice and has
    # nothing to say about #92 -- which is a broken harness, not a pass.
    if away_release is None or away_release["onCap"]:
        print("FAIL: the flick still released on the cap, so this phase tested nothing.")
        ok = False
    elif after_away is None or not after_away["onCap"]:
        print("FAIL: the genuine click missed the cap, so this phase tested nothing.")
        ok = False
    elif after_away["prevented"]:
        print("FAIL: a flick swallowed the next genuine click on that cap.")
        ok = False
    else:
        print("PASS: a click after a flick still reaches the link.")

    if on_release is None or not on_release["onCap"]:
        print("FAIL: the slow drag did not release on the cap, so suppression is untested.")
        ok = False
    elif not on_release["prevented"]:
        print("FAIL: a drag that ended on the cap navigated -- it would count as an outbound visit.")
        ok = False
    elif after_on is None or after_on["prevented"]:
        print("FAIL: a drag swallowed the next genuine click on that cap.")
        ok = False
    else:
        print("PASS: a drag is still suppressed, and only its own click.")

    print()
    print("RESULT: PASS" if ok else "RESULT: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
