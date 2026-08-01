#!/usr/bin/env python3
"""Render the train under several palette directions and stitch a comparison.

Four blind tuning passes have not converged, so this stops guessing and puts
concrete options side by side to be chosen between.
"""
import asyncio, base64, json, os, re, shutil, subprocess, time, urllib.request
from PIL import Image, ImageDraw
import websockets

REPO = "/Users/charles/work/claude/wozi.com"
OUT = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad"
STAGE = OUT + "/pal-stage"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
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
HTTP = 8790

PALETTES = [
    ("A  bright curated (current)",
     ['#D63C6A', '#DF5F24', '#E0A52C', '#35A853', '#0E9E92', '#2F6FDB', '#7C5CD9']),
    ("B  muted industrial",
     ['#9A5F66', '#A0714F', '#9C8B52', '#5F8465', '#4F7E80', '#556E96', '#6F6389']),
    ("C  bold poster",
     ['#E03B2F', '#F0932B', '#EFC629', '#3EA55A', '#159AAF', '#2E5FD0', '#8A45B5']),
    ("D  steel with one accent",
     ['#79858C', '#8C979E', '#68737A', '#9AA5AC', '#5B666D', '#A8B3BA', '#C2502E']),
    ("E  brass and copper",
     ['#A85C38', '#C08A3E', '#8C7A3E', '#6B7F55', '#4E6E66', '#5B6B85', '#7C5C6E']),
    ("F  the original template palette (note: two blues, two greens)",
     ['#4A90E2', '#17A05C', '#8CB8F2', '#E8615A', '#6ECFA6', '#F2C14E', '#9B8CE0']),
]


def variant(src, colours):
    """Swap the wheel palette in a copy of config.js.

    THIS TARGETED A NAME THAT NO LONGER EXISTS. It substituted WHEEL_PALETTE,
    which #40 renamed to WHEEL_POOL when the pool moved out of index.html into
    config.js -- and re.sub with no match returns the source unchanged and
    raises nothing, so this rendered six IDENTICAL palettes and reported
    success. Same family as the CI_FLAGS bug: a tool failing into something
    that looks like a result (#47).

    Asserts the substitution happened, so the next rename is loud.
    """
    out, n = re.subn(r"WHEEL_POOL:\s*\[[^\]]*\]",
                     "WHEEL_POOL: ['" + "', '".join(colours) + "']",
                     src, count=1)
    if n != 1:
        raise SystemExit("palettes.py: WHEEL_POOL not found in config.js — "
                         "the palette was renamed again; fix this substitution")
    return out


async def shoot(send, theme, tag):
    await send("Page.navigate", {"url": f"http://127.0.0.1:{HTTP}/"})
    await asyncio.sleep(1.8)
    await send("Runtime.evaluate", {"expression":
        f"(()=>{{localStorage.setItem('wozi-theme','{theme}');location.reload();}})()"})
    await asyncio.sleep(3.2)
    s = await send("Page.captureScreenshot", {"format": "png"})
    p = f"{OUT}/pal-{tag}.png"
    open(p, "wb").write(base64.b64decode(s["data"]))
    return p


async def main():
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE)
    for f in ("support.js",):
        shutil.copy(f"{REPO}/{f}", STAGE)
    shutil.copytree(f"{REPO}/assets", f"{STAGE}/assets")
    src = open(f"{REPO}/index.html").read()

    srv = subprocess.Popen(["python3", "-m", "http.server", str(HTTP), "--bind", "127.0.0.1"],
                           cwd=STAGE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={OUT}/cp-pal", "--hide-scrollbars", "--no-first-run", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(60):
        try:
            ws = json.load(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/new?http://127.0.0.1:{HTTP}/", timeout=1))["webSocketDebuggerUrl"]; break
        except Exception:
            try:
                rq = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?http://127.0.0.1:{HTTP}/", method="PUT")
                ws = json.load(urllib.request.urlopen(rq, timeout=1))["webSocketDebuggerUrl"]; break
            except Exception:
                time.sleep(0.2)

    mid = 0
    shots = []
    async with websockets.connect(ws, max_size=8 * 10 ** 7) as c:
        async def send(m, p=None):
            nonlocal mid
            mid += 1; my = mid
            await c.send(json.dumps({"id": my, "method": m, "params": p or {}}))
            while True:
                msg = json.loads(await c.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})
        await send("Runtime.enable"); await send("Page.enable")
        await send("Emulation.setDeviceMetricsOverride",
                   {"width": 1250, "height": 330, "deviceScaleFactor": 2, "mobile": False})
        for i, (label, cols) in enumerate(PALETTES):
            open(f"{STAGE}/index.html", "w").write(variant(src, cols))
            await asyncio.sleep(0.4)
            for theme in ("light", "dark"):
                shots.append((label, theme, await shoot(send, theme, f"{i}-{theme}")))
    proc.kill(); srv.kill()

    # stitch: each palette a row, light left / dark right
    ims = [Image.open(p) for _, _, p in shots]
    w, h = ims[0].size
    sw, sh = w // 2, h // 2
    board = Image.new("RGB", (sw * 2, sh * len(PALETTES) + 26 * len(PALETTES)), "#FFFFFF")
    d = ImageDraw.Draw(board)
    y = 0
    for i, (label, _) in enumerate(PALETTES):
        d.text((8, y + 7), label, fill="#111111")
        y += 26
        board.paste(ims[i * 2].resize((sw, sh)), (0, y))
        board.paste(ims[i * 2 + 1].resize((sw, sh)), (sw, y))
        y += sh
    board.save(f"{OUT}/palette-options.png")
    print(f"-> palette-options.png  ({len(PALETTES)} options, light left / dark right)")

asyncio.run(main())
