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

Exit 0 if every viewport matches, 1 if any pixel differs, 2 if it could not
photograph -- OR COULD NOT COMPARE. Those two used to be different: a missing
Pillow printed "cannot diff" and exited 0, so the strongest gate in the tree
passed by not running, on a machine that had simply never installed numpy. A
comparison that did not happen is not a comparison that passed.
"""

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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


async def shoot(url, viewports, seed, frames, theme):
    """One browser, every viewport. Returns {label: png bytes}."""
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

    out = {}
    mid = 0
    async with websockets.connect(ws_url, max_size=10 ** 8) as c:
        async def send(m, p=None):
            nonlocal mid
            mid += 1
            my = mid
            await c.send(json.dumps({"id": my, "method": m, "params": p or {}}))
            while True:
                msg = json.loads(await c.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Page.addScriptToEvaluateOnNewDocument",
                   {"source": determinism_js(seed)})
        # The theme is remembered in localStorage, so it has to be planted and
        # the page reloaded -- and the reload has to happen through the same
        # injected script, or the second load deals a different train.
        await send("Page.addScriptToEvaluateOnNewDocument",
                   {"source": "try{localStorage.setItem('wozi-theme','%s')}catch(e){}" % theme})

        for w, hgt in viewports:
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": w, "height": hgt, "deviceScaleFactor": 1,
                        "mobile": False})
            await send("Page.navigate", {"url": url})
            await asyncio.sleep(4.0)
            await send("Runtime.evaluate",
                       {"expression": f"window.__pump && window.__pump({frames})",
                        "returnByValue": True})
            shot = await send("Page.captureScreenshot", {"format": "png"})
            out[f"{w}x{hgt}"] = base64.b64decode(shot["data"])
    proc.kill()
    shutil.rmtree(profile, ignore_errors=True)
    return out


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

    srv, base = serve(ROOT)
    try:
        now = asyncio.run(shoot(base + a.path + a.query, vps, a.seed, a.frames, a.theme))
    finally:
        srv.kill()

    if a.shot:
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
            ref = asyncio.run(shoot(base2 + a.path + a.query, vps, a.seed, a.frames, a.theme))
        finally:
            srv2.kill()
    finally:
        subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", tree],
                       capture_output=True)
        shutil.rmtree(work, ignore_errors=True)

    print(f"\nworking tree vs {a.ref}   seed {a.seed}, {a.frames} frames, "
          f"{a.theme} theme, /{a.path}{a.query}")
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
