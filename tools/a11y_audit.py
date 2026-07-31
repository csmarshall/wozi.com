#!/usr/bin/env python3
"""Full accessibility audit: axe-core injected over CDP, plus the structural and
behavioural checks axe cannot make on a page that is entirely motion.

Run against both themes, because contrast findings differ per theme.
"""
import asyncio, json, subprocess, sys, time, urllib.request
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
OUT = "/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad"
AXE = OUT + "/node_modules/axe-core/axe.min.js"
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if _sys_platform_is_darwin() else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
PORT = 9420

# Things axe structurally cannot judge on this page.
MANUAL = r"""
(() => {
  const out = {};
  out.lang = document.documentElement.getAttribute('lang');
  out.main = !!document.querySelector('main, [role="main"]');
  out.h1 = document.querySelectorAll('h1').length;
  out.headings = document.querySelectorAll('h1,h2,h3,h4,h5,h6').length;
  out.title = document.title;
  out.skipLink = !!document.querySelector('a[href^="#"]');

  /* SVG text that a screen reader will walk through: the rim engravings. */
  const svgText = [...document.querySelectorAll('svg text')];
  out.svgTextNodes = svgText.length;
  out.svgTextHidden = svgText.filter(t => t.closest('[aria-hidden="true"]')).length;
  out.svgTextSample = svgText.slice(0, 4).map(t => t.textContent.trim()).filter(Boolean);

  /* Decorative SVGs should be hidden from the tree entirely. */
  const svgs = [...document.querySelectorAll('svg')];
  out.svgTotal = svgs.length;
  out.svgHidden = svgs.filter(s => s.getAttribute('aria-hidden') === 'true'
                              || s.closest('[aria-hidden="true"]')).length;

  /* Focusable things and whether they show a focus ring. */
  const foc = [...document.querySelectorAll('a[href],button,[tabindex]:not([tabindex="-1"])')];
  out.focusable = foc.length;
  out.focusableNoLabel = foc.filter(e =>
      !e.getAttribute('aria-label') && !e.getAttribute('title') && !e.textContent.trim()).length;

  /* Does anything define a visible focus indicator? */
  let outlineRules = 0;
  for (const sh of document.styleSheets) {
    try { for (const r of sh.cssRules) {
      if (r.selectorText && /:focus/.test(r.selectorText)) outlineRules++;
    } } catch (e) {}
  }
  out.focusRules = outlineRules;

  /* Motion: is anything gated on the reduced-motion preference? */
  out.reducedMotionInCSS = (() => {
    let n = 0;
    for (const sh of document.styleSheets) {
      try { for (const r of sh.cssRules) {
        if (r.conditionText && /prefers-reduced-motion/.test(r.conditionText)) n++;
      } } catch (e) {}
    }
    return n;
  })();

  /* Touch targets: 24x24 CSS px is the WCAG 2.2 minimum. */
  out.smallTargets = foc.filter(e => {
    const b = e.getBoundingClientRect();
    return b.width > 0 && (b.width < 24 || b.height < 24);
  }).length;

  return JSON.stringify(out);
})()
"""


async def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={OUT}/cp-a11y", "--hide-scrollbars", "--no-first-run", *CI_FLAGS, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(60):
        try:
            ws = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/new?{URL}", timeout=1))["webSocketDebuggerUrl"]; break
        except Exception:
            try:
                rq = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{URL}", method="PUT")
                ws = json.load(urllib.request.urlopen(rq, timeout=1))["webSocketDebuggerUrl"]; break
            except Exception:
                time.sleep(0.2)
    axe_src = open(AXE).read()
    mid = 0
    async with websockets.connect(ws, max_size=8 * 10 ** 7) as c:
        async def send(m, p=None):
            nonlocal mid
            mid += 1; my = mid
            await c.send(json.dumps({"id": my, "method": m, "params": p or {}}))
            while True:
                msg = json.loads(await c.recv())
                if msg.get("id") == my:
                    return msg.get("result", {})
        async def ev(expr, awaited=False):
            r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                                "awaitPromise": awaited})
            return r.get("result", {}).get("value")

        await send("Runtime.enable"); await send("Page.enable")
        await send("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False})

        for theme in ("dark", "light"):
            await send("Page.navigate", {"url": URL}); await asyncio.sleep(2.0)
            await ev(f"(()=>{{localStorage.setItem('wozi-theme','{theme}');location.reload();}})()")
            await asyncio.sleep(3.4)
            await ev(axe_src)
            res = await ev("axe.run(document,{resultTypes:['violations']}).then(r=>JSON.stringify("
                           "r.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,n:v.nodes.length}))))", True)
            v = json.loads(res)
            print(f"\n=== axe-core, {theme} theme ===")
            if not v:
                print("   no violations")
            for x in sorted(v, key=lambda z: ["critical","serious","moderate","minor"].index(z["impact"] or "minor")):
                print(f"   [{(x['impact'] or '?').upper():<8}] {x['id']:<28} x{x['n']}  {x['help']}")
            if theme == "dark":
                m = json.loads(await ev(MANUAL))
                print("\n=== structural / behavioural (axe cannot judge these) ===")
                print(f"   lang attribute          : {m['lang'] or 'MISSING'}")
                print(f"   <main> landmark         : {'yes' if m['main'] else 'MISSING'}")
                print(f"   headings on page        : {m['headings']}  (h1: {m['h1']})")
                print(f"   skip link               : {'yes' if m['skipLink'] else 'none'}")
                print(f"   focusable elements      : {m['focusable']}  (unlabelled: {m['focusableNoLabel']})")
                print(f"   :focus style rules       : {m['focusRules']}")
                print(f"   prefers-reduced-motion   : {m['reducedMotionInCSS']} rules")
                print(f"   SVG elements             : {m['svgTotal']}  (hidden from a11y tree: {m['svgHidden']})")
                print(f"   SVG <text> nodes         : {m['svgTextNodes']}  (hidden: {m['svgTextHidden']})")
                print(f"     sample announced       : {m['svgTextSample']}")
                print(f"   targets under 24x24px    : {m['smallTargets']}")
    proc.kill()

asyncio.run(main())
