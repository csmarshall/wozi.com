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
PORT = 9430
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
    return re.sub(r"const WHEEL_PALETTE = \[[^\]]*\];",
                  "const WHEEL_PALETTE = ['" + "', '".join(colours) + "'];",
                  src, count=1)


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
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
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
