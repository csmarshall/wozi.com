#!/usr/bin/env python3
"""Full accessibility audit: axe-core injected over CDP, plus the structural and
behavioural checks axe cannot make on a page that is entirely motion.

Run against both themes, because contrast findings differ per theme.
"""
import asyncio, json, subprocess, sys, time, urllib.request
import websockets

import os as _os, shutil as _sh, sys as _sys, tempfile as _tf
def _sys_platform_is_darwin():
    return _sys.platform == "darwin"
# CI runs on Linux, where Chrome is not in /Applications. Honour $CHROME,
# then fall back to whatever is on PATH, then to the macOS bundle.
CHROME = (_os.environ.get("CHROME")
          or _sh.which("google-chrome") or _sh.which("chromium-browser")
          or _sh.which("chromium")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
# WHERE AXE LIVES. This used to be hardcoded to one session's scratchpad
# directory, which stops existing when that session ends -- so the tool raised
# FileNotFoundError on every run afterwards and nobody noticed, because it also
# had no exit code (#47). Resolve it relative to the repo, honour an override,
# and fall back to a temp dir that a fetch can populate.
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_REPO = _os.path.dirname(_HERE)
OUT = _os.environ.get("WOZI_SCRATCH") or _tf.mkdtemp(prefix="wozi-a11y-")
AXE = (_os.environ.get("AXE_PATH")
       or _os.path.join(_REPO, "node_modules", "axe-core", "axe.min.js"))
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if _sys_platform_is_darwin() else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
_FAILURES = []
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
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

  /* Focusable things and whether they show a focus ring.

     FORM CONTROLS ARE IN THE LIST, and were not until GitHub #108 (CL#114).
     The selector was `a[href],button,[tabindex]` -- every focusable thing
     this page happened to contain at the time, and therefore a gate with a
     hole in it shaped like whatever got added next. What got added next was
     the speed slider: an `input[type=range]`, natively focusable and a real
     touch target, invisible to every check below. Named explicitly rather
     than left to `[tabindex]`, because a native control needs no tabindex to
     be focusable. */
  const foc = [...document.querySelectorAll(
    'a[href],button,input:not([type="hidden"]),select,textarea,[tabindex]:not([tabindex="-1"])')];
  out.focusable = foc.length;
  /* How many of those are range inputs, and what their box measures versus
     their visible thumb -- the WCAG 2.5.8 floor can be satisfied by an
     invisible hit area while the rendered control looks smaller (GitHub
     #108). --thumb is the CSS token the visible disc is drawn at; the input's
     own bounding box is whatever height CL#114 gave it for the touch target. */
  out.rangeInputs = foc.filter(e => e.tagName === 'INPUT' && e.type === 'range').map(e => {
    const r = e.getBoundingClientRect();
    const thumbPx = parseFloat(getComputedStyle(e).getPropertyValue('--thumb')) || null;
    return { box: [Math.round(r.width), Math.round(r.height)], thumbPx };
  });
  const accName = e => (e.getAttribute('aria-label')
                     || e.getAttribute('title')
                     || e.textContent.trim() || '').replace(/\s+/g, ' ').trim();
  out.focusableNoLabel = foc.filter(e => !accName(e)).length;

  /* TWO FOCUSABLES THAT SOUND IDENTICAL AND GO SOMEWHERE DIFFERENT. Counting
     UNLABELLED elements, which is the check above, passes a page where every
     control has a name and two of them are the same name -- and that is exactly
     what a combined stage produces, because two people can carry the same
     service and "Mail" then names two different mailboxes. A screen reader gets
     a tab order with no way to tell them apart; the datum plate that
     distinguishes them on screen is inside the aria-hidden gear art.
     Same name AND same href is not a finding: that is one destination reachable
     twice, which is a navigation choice, not an ambiguity. Anything WITHOUT a
     destination gets a key unique to the element instead of its tag name -- two
     same-named buttons are two different actions announced identically, and
     keying them both on "BUTTON" made them compare equal and slip through. */
  const byName = {};
  foc.forEach((e, i) => {
    const n = accName(e);
    if (!n) return;
    const dest = e.tagName === 'A' && e.getAttribute('href') !== null ? 'href:' + e.href : 'el:' + i;
    (byName[n] = byName[n] || []).push(dest);
  });
  out.dupNames = Object.keys(byName).filter(n =>
      new Set(byName[n]).size > 1).map(n => [n, byName[n].length]);

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
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
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
    # FETCH AXE IF IT IS NOT THERE, rather than requiring a node_modules that
    # this repo deliberately does not have. The path used to point into one
    # session's scratchpad, which stops existing when that session ends -- so
    # this raised FileNotFoundError on every run afterwards, and nobody noticed
    # because the tool also had no exit code (#47). Cached in a temp dir.
    if not _os.path.exists(AXE):
        _cache = _os.path.join(_tf.gettempdir(), "wozi-axe.min.js")
        if not _os.path.exists(_cache):
            import urllib.request as _u
            print(f"   fetching axe-core -> {_cache}")
            try:
                _u.urlretrieve("https://unpkg.com/axe-core@4/axe.min.js", _cache)
            except Exception as _e:
                print(f"FATAL: axe-core unavailable and could not be fetched: {_e}")
                print("       set AXE_PATH=/path/to/axe.min.js to use a local copy")
                proc.kill()
                return 2
        _use = _cache
    else:
        _use = AXE
    axe_src = open(_use).read()
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
            # speed pinned off 1x (GitHub #108, CL#114): the corner departure
            # indicator is display:none at 1x, so auditing at the shipped
            # default would never see it. 5x is a real, non-strobing stop.
            await ev(f"(()=>{{localStorage.setItem('wozi-theme','{theme}');"
                     "localStorage.setItem('wozi-speed','5');location.reload();}})()")
            await asyncio.sleep(3.4)
            # Open the pop-out menu so the slider is actually visible to axe
            # and to the MANUAL checks below -- display:none is neither, and
            # the slider is the ONLY route to the speed control off 1x now.
            await ev("(()=>{const b=document.querySelector('[aria-expanded]'); "
                     "if (b) b.click();})()")
            await asyncio.sleep(0.3)
            await ev(axe_src)
            res = await ev("axe.run(document,{resultTypes:['violations']}).then(r=>JSON.stringify("
                           "r.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,n:v.nodes.length}))))", True)
            v = json.loads(res)
            print(f"\n=== axe-core, {theme} theme ===")
            if not v:
                print("   no violations")
            for x in sorted(v, key=lambda z: ["critical","serious","moderate","minor"].index(z["impact"] or "minor")):
                print(f"   [{(x['impact'] or '?').upper():<8}] {x['id']:<28} x{x['n']}  {x['help']}")
                # WHAT ACTUALLY FAILS THIS GATE. Only critical and serious, so
                # the check has teeth without turning red over a moderate hint
                # nobody has agreed to act on -- a gate that fails on an open
                # question trains everyone to ignore it (#41, #46).
                if (x["impact"] or "") in ("critical", "serious"):
                    _FAILURES.append(f"axe {theme}: [{x['impact']}] {x['id']} x{x['n']} — {x['help']}")
            if theme == "dark":
                m = json.loads(await ev(MANUAL))
                print("\n=== structural / behavioural (axe cannot judge these) ===")
                print(f"   lang attribute          : {m['lang'] or 'MISSING'}")
                print(f"   <main> landmark         : {'yes' if m['main'] else 'MISSING'}")
                print(f"   headings on page        : {m['headings']}  (h1: {m['h1']})")
                print(f"   skip link               : {'yes' if m['skipLink'] else 'none'}")
                print(f"   focusable elements      : {m['focusable']}  (unlabelled: {m['focusableNoLabel']})")
                print(f"   duplicate accessible names: {m['dupNames'] or 'none'}")
                print(f"   :focus style rules       : {m['focusRules']}")
                print(f"   prefers-reduced-motion   : {m['reducedMotionInCSS']} rules")
                print(f"   SVG elements             : {m['svgTotal']}  (hidden from a11y tree: {m['svgHidden']})")
                print(f"   SVG <text> nodes         : {m['svgTextNodes']}  (hidden: {m['svgTextHidden']})")
                print(f"     sample announced       : {m['svgTextSample']}")
                print(f"   targets under 24x24px    : {m['smallTargets']}")
                # THE BOX MEASURED IS NOT THE THUMB DRAWN (GitHub #108). A
                # range input's own bounding box -- what the 24x24 check above
                # actually measures -- is not the same rectangle as its
                # visible thumb, which is a pseudo-element getBoundingClientRect
                # cannot see at all. Reported separately so "passes 24x24" and
                # "the thing you'd tap looks that big" are never conflated.
                for ri in m.get("rangeInputs", []):
                    w, h = ri["box"]
                    print(f"   range input hit box      : {w}x{h}px "
                          f"(visible thumb: {ri['thumbPx']}px disc)")
                # WCAG 2.5.8 target size. Two-sided by nature -- there is no
                # upper bound worth asserting on a hit target, so this one floor
                # is the whole check.
                if m["smallTargets"]:
                    _FAILURES.append(f"{m['smallTargets']} interactive target(s) under 24x24px (WCAG 2.5.8)")
                if not m["lang"]:
                    _FAILURES.append("no lang attribute on <html>")
                if not m["main"]:
                    _FAILURES.append("no <main> landmark")
                if m["focusableNoLabel"]:
                    _FAILURES.append(f"{m['focusableNoLabel']} focusable element(s) with no accessible name")
                for name, n in m["dupNames"]:
                    _FAILURES.append(
                        f'{n} focusables share the accessible name "{name}" and do not '
                        f"share a destination (WCAG 2.4.4/4.1.2)")
    proc.kill()
    # AN EXIT CODE, so this is a gate rather than a printout (#47). It ended at
    # asyncio.run(main()) with main() returning None, so it exited 0 whatever it
    # found -- and every "axe clean, gate green" in the merge log was a report
    # somebody read, not a check that could go red.
    return 1 if _FAILURES else 0

if __name__ == "__main__":
    _code = asyncio.run(main())
    if _FAILURES:
        print("\nRESULT: FAIL")
        for f in _FAILURES:
            print("  " + f)
    else:
        print("\nRESULT: PASS")
    sys.exit(_code or (1 if _FAILURES else 0))
