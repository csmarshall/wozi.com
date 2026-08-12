#!/usr/bin/env python3
"""Full accessibility audit: axe-core injected over CDP, plus the structural and
behavioural checks axe cannot make on a page that is entirely motion.

Run against both themes, because contrast findings differ per theme — and since
GitHub #157 that means BOTH batteries, not just axe: the 24x24 target floor, the
duplicate-name check, lang/main and the unlabelled-focusable count used to be
gated on `theme == "dark"`, which made half this tool's assertions statements
about one theme inside a tool whose whole reason for looping is that they differ.
The verbose printout is still dark-only; the assertions are not.

Axe's `incomplete` bucket is PRINTED and never failed. A check axe could not
decide is an open question, and this page is painted almost entirely in inline
gradients, which is exactly the background `color-contrast` cannot flatten — so
"no violations" was a weaker sentence than it read as. Measured on the shipped
page: one undecided node per theme, an aria-hidden rim engraving overlapped by
another element.

Usage: python3 tools/a11y_audit.py [url] [--fonts auto|pinned|blocked]

THE WEBFONT IS PINNED, AND THE HONEST ANSWER IS THAT THE EXPOSURE MEASURED ZERO
(GitHub #145). This was the harness to worry about, for a good reason: it asserts
the WCAG 2.5.8 floor of 24x24 CSS px on every focusable, and a hit box derived
from a label changes size when the face swaps -- which is `pill_clip`'s fault
exactly, where the same page measured -0.58px of clip clearance with Manrope and
-1.45px without, against a +0.05px tolerance.

So it was measured rather than assumed, with both font hosts blackholed against a
normal run, the deal held fixed so the font was the only variable:

    every focusable's box, 30 of them   IDENTICAL to 0.01px in both regimes
    smallest target, over 12 deals      IDENTICAL in both regimes, 39.44-44.00px
    axe-core, both themes               no violations in either regime

The one number that DOES move is the Table of Gears row: 268.63px wide with
Manrope, 270.52px without -- 1.89px, and the row's HEIGHT, which is what the
floor would bite on, does not move at all. Nothing here asserts a width, and the
nearest thing to the floor is a checkbox at exactly 24.00x24.00 whose size is
fixed in CSS. **So this is pinned as insurance, not as a fix** -- the same
verdict CL#168 reached for `devices.py`, and worth saying plainly rather than
dressing up. What it buys: the type-derived boxes stop moving between runs, so a
human diffing two runs is not shown a number changing with nothing changed, and
the day a control's box starts coming from its label the gate is already
deterministic.

**The three fixed sleeps are the part that was actually wrong.** A plain
`asyncio.sleep` in a render path HOLDS the stylesheet for its duration and lets
it land afterwards, which is the late-font regime itself (see tools/fontpin.py).
They are replaced by conditions, and the `location.reload()` they were covering
is gone with them -- the theme and speed are injected at document-start now, the
way tools/dom_invariants.py does it, so there is no outgoing document to poll as
ready.
"""
import argparse, asyncio, json, subprocess, sys, time, urllib.request
import websockets

import os as _os, shutil as _sh, sys as _sys, tempfile as _tf

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import fontpin  # noqa: E402
# ONE HOME FOR THE INJECTED LCG (GitHub #155, #165). Four harnesses each carried a
# copy and all four copies read the seed out of the URL, which is the fault #155 is
# about — a fifth copy would be a fifth chance to reintroduce it.
import dom_invariants as _dom  # noqa: E402


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
# THE RULESET IS PINNED TO AN EXACT VERSION (GitHub #165). This fetched
# `axe-core@4` -- a major-version RANGE off somebody else's server -- so any 4.x
# release that added or tightened a rule changed what this gate asserts with
# nothing in this repo having changed. By this repo's own no-drifting-constants
# rule that is worse than a magic number: it is a magic number nobody here can
# even read.
#
# 4.13.0 IS WHAT `axe-core@4` RESOLVED TO on the day this was pinned, chosen for
# exactly that reason -- pinning to anything older would have re-rolled the verdict
# against a different ruleset instead of freezing the one the current green was
# measured under. What this costs, stated rather than discovered later: new
# upstream rules stop arriving for free, so an upgrade is now a task somebody has
# to do. That is the trade — a verdict that is attributable, against a gate that
# improves silently and can also break silently.
#
# THE VERSION IS IN THE CACHE FILENAME, which is not cosmetic: a cache keyed on
# the name alone would serve the OLD bytes forever after a bump, so the pin would
# read as changed while the gate went on asserting the previous ruleset.
AXE_VERSION = "4.13.0"
AXE_URL = f"https://unpkg.com/axe-core@{AXE_VERSION}/axe.min.js"
# Containers have no sandbox and a tiny /dev/shm, so Chrome refuses to start
# without these. Only added off macOS, where they are unnecessary.
CI_FLAGS = ([] if _sys_platform_is_darwin() else
            ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
_FAILURES = []
# POSITIONAL and optional, because CI appends the served URL to this argv.
_ap = argparse.ArgumentParser(description="accessibility audit: axe-core + the "
                                          "checks axe cannot make")
_ap.add_argument("url", nargs="?", default="http://127.0.0.1:8765/")
_ap.add_argument("--fonts", default="auto", choices=["auto", "pinned", "blocked"],
                 help="auto: serve the webfont from prefetched bytes, degrading "
                      "loudly to blocked if it cannot be fetched. pinned: require "
                      "it, exit 2 if unobtainable. blocked: never fetch it — the "
                      "shipped typography is then NOT what gets measured.")
# THE DEAL IS PINNED, BECAUSE AXE'S CONTRAST RULE READS DEALT COLOURS (GitHub
# #165). Unlike every gate in deploy.yml this one injected no generator, so each
# pass audited a randomly dealt machine -- and twelve consecutive green runs is
# green-on-average over an unbounded population of deals, which is not the same
# claim as deterministic green. A contrast failure reachable by one deal in fifty
# would have sat here indefinitely, passing.
#
# AND IT IS THE INJECTED LCG, NOT ?seed. CLAUDE.md is explicit: a gate that deals
# through the same mechanism the page deals through cannot see a fault in that
# mechanism, because it would agree with the page about a machine they had both got
# wrong. #155 is what happens when a harness does both -- DEAL_SEED runs at module
# scope, after any injected script, so the page wins and the injection is dead code.
#
# WHAT THIS DOES NOT FIX, said here so nobody reads more into it: one pinned deal
# makes the verdict REPRODUCIBLE, not COMPLETE. It audits one of the machines the
# page can draw. Sweeping several seeds is the way to widen that, and the weekly
# job is the right home for a sweep -- see mutation.yml.
_ap.add_argument("--seed", type=int, default=20260804,
                 help="the deal to audit. Injected over Math.random before any page "
                      "script runs; the verdict is a property of this number")
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

  /* Touch targets: 24x24 CSS px is the WCAG 2.2 minimum.

     THE DIMENSIONS ARE REPORTED, NOT ONLY THE COUNT (GitHub #145). A bare
     "0 targets under 24x24" cannot distinguish a page with room to spare from
     one sitting a tenth of a pixel over the floor -- and some of these boxes
     are derived from their own label, so they move when the face resolves
     differently. Printing the tightest few is what makes that visible in a
     diff of two runs instead of only in the run that finally goes red. */
  const boxed = foc.map(e => {
    const b = e.getBoundingClientRect();
    return { name: accName(e) || '(unlabelled)', tag: e.tagName,
             w: +b.width.toFixed(2), h: +b.height.toFixed(2),
             min: +Math.min(b.width, b.height).toFixed(2) };
  }).filter(t => t.w > 0);
  boxed.sort((a, b) => a.min - b.min);
  out.tightest = boxed.slice(0, 6);
  out.smallTargets = boxed.filter(t => t.min < 24);

  return JSON.stringify(out);
})()
"""


# The panel's own state, as the page reports it, and the slider's box. Not a
# duration: the pop-out is opened by a real click and the audit below is
# meaningless until it is actually open -- axe cannot see a display:none control
# and neither can the target-size check, so a click that silently misses would
# quietly drop the slider out of the gate. #46's shape: the check that passes
# loudest when the feature is broken.
PANEL_JS = ("(()=>{const b=document.querySelector('[aria-expanded]');"
            "if(!b)return 'no toggle';"
            "if(b.getAttribute('aria-expanded')!=='true')return 'shut';"
            "const r=[...document.querySelectorAll('input[type=range]')]"
            ".filter(e=>e.getBoundingClientRect().width>0);"
            "return r.length?'open':'no slider';})()")
PANEL_TIMEOUT_S = 10.0
# WHICH THEME IS ACTUALLY IN FORCE, and this is asserted rather than assumed for
# the best possible reason (GitHub #145): it was NOT in force, for the whole life
# of this file. The preferences were written by a JS snippet built from an
# f-string concatenated with a plain string -- `f"...{{..."  "...}})()"` -- so the
# `}}` in the second half never collapsed to one brace and every run threw
# `SyntaxError: Unexpected token '}'` into a value nothing looked at. The theme
# was never set, the speed was never set, and both passes audited the SAME
# default theme at 1x. Every "a11y_audit PASS in both themes" in CHANGELOG.md is
# one theme audited twice.
#
# A gate must therefore say what it measured. `data-theme` is the page's own
# answer, and the speed is read back for the same reason -- CL#114 audits at 5x
# so the corner departure indicator exists to be audited at all.
INFORCE_JS = ("(()=>{const h=document.documentElement;return JSON.stringify({"
              "theme:h.getAttribute('data-theme'),"
              "speed:(()=>{try{return localStorage.getItem('wozi-speed')}"
              "catch(e){return 'unreadable'}})(),"
              "corner:document.querySelectorAll('[aria-expanded]').length});})()")


async def main(pin):
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--window-position=-4000,-4000", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={OUT}/cp-a11y", "--hide-scrollbars", "--no-first-run", *CI_FLAGS, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(60):
        # about:blank, NOT the page under test. Asking /json/new for the URL makes
        # the tab navigate before the font interception is armed, so that first
        # navigation pulls the stylesheet off the network and warms the cache for
        # every measured one after it -- a pin installed afterwards is decoration.
        for method in (None, "PUT"):
            try:
                target = f"http://127.0.0.1:{PORT}/json/new?about:blank"
                rq = urllib.request.Request(target, method=method) if method else target
                ws = json.load(urllib.request.urlopen(rq, timeout=1))["webSocketDebuggerUrl"]
                break
            except Exception:
                pass
        if ws:
            break
        time.sleep(0.2)
    # FETCH AXE IF IT IS NOT THERE, rather than requiring a node_modules that
    # this repo deliberately does not have. The path used to point into one
    # session's scratchpad, which stops existing when that session ends -- so
    # this raised FileNotFoundError on every run afterwards, and nobody noticed
    # because the tool also had no exit code (#47). Cached in a temp dir.
    if not _os.path.exists(AXE):
        # Version in the filename: see AXE_VERSION. A cache keyed on the name alone
        # would serve the previous ruleset forever after a bump.
        _cache = _os.path.join(_tf.gettempdir(), f"wozi-axe-{AXE_VERSION}.min.js")
        if not _os.path.exists(_cache):
            import urllib.request as _u
            print(f"   fetching axe-core {AXE_VERSION} -> {_cache}")
            try:
                _u.urlretrieve(AXE_URL, _cache)
            except Exception as _e:
                print(f"FATAL: axe-core unavailable and could not be fetched: {_e}")
                print("       set AXE_PATH=/path/to/axe.min.js to use a local copy")
                proc.kill()
                return 2
        _use = _cache
    else:
        _use = AXE
    axe_src = open(_use).read()
    async with websockets.connect(ws, max_size=8 * 10 ** 7) as c:
        # send/pump/wait_until come from fontpin, and not for tidiness: a paused
        # font request arrives UNSOLICITED and must be answered, and the
        # loop-until-my-id send this file used to carry discarded exactly that
        # message, so the page would hang on its own stylesheet forever.
        send, pump, wait_until = fontpin.attach(c, pin)

        async def ev(expr, awaited=False):
            r = await send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                                "awaitPromise": awaited})
            return r.get("result", {}).get("value")

        await send("Runtime.enable")
        # Page.enable FIRST, or the injections below are accepted and silently
        # never run -- which reads exactly like an injection that does not work.
        await send("Page.enable")
        await pin.install(send)
        # THE DEAL, INSTALLED ONCE AND LEFT IN PLACE. It is the same for both themes,
        # so unlike `prefs` below it does not need removing and re-adding between
        # navigations -- which is the safer shape, because a remove/re-add pair that
        # ever failed would leave two generators installed and the last one added
        # would silently decide both deals (the hazard devices.py guards explicitly).
        await send("Page.addScriptToEvaluateOnNewDocument",
                   {"source": _dom.seed_js(_ARGS.seed)})
        await send("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False})

        for theme in ("dark", "light"):
            # THE PREFERENCES ARE INJECTED AT DOCUMENT-START, so one navigation
            # does what a navigate-then-reload used to. The reload was the hazard,
            # not the wait it needed: after `location.reload()` there are two
            # documents in flight and a readiness poll can answer for the OUTGOING
            # one, which is CL#168's bug in devices.py exactly. Nothing to poll
            # wrongly if nothing reloads.
            #
            # Speed is pinned off 1x (GitHub #108, CL#114): the corner departure
            # indicator is display:none at 1x, so auditing at the shipped default
            # would never see it. 5x is a real, non-strobing stop.
            prefs = await send("Page.addScriptToEvaluateOnNewDocument", {
                "source": "try{localStorage.setItem('wozi-theme','%s');"
                          "localStorage.setItem('wozi-speed','5')}catch(e){}" % theme})
            await send("Page.navigate", {"url": URL})
            # CONDITIONS, not the retired 2.0s + 3.4s. Those were tuned to a
            # network the font is no longer on, and a sleep in the render path
            # holds the stylesheet for its whole duration and lets it land
            # afterwards -- the late-font regime itself.
            await fontpin.wait_ready(send, pump, wait_until, what=f"{theme}: the page")
            # Open the pop-out menu so the slider is actually visible to axe and
            # to the MANUAL checks below -- display:none is neither, and the
            # slider is the ONLY route to the speed control off 1x now.
            await ev("(()=>{const b=document.querySelector('[aria-expanded]'); "
                     "if (b) b.click();})()")
            await wait_until(PANEL_JS, "open", PANEL_TIMEOUT_S,
                             f"{theme}: the pop-out panel never opened")
            # Each theme is a fresh document, so the injection must not stack:
            # left in place, the light pass would still be told 'dark' by the
            # script the dark pass added.
            await send("Page.removeScriptToEvaluateOnNewDocument",
                       {"identifier": prefs["identifier"]})
            inforce = json.loads(await ev(INFORCE_JS))
            print(f"\n=== axe-core, {theme} theme ===")
            print(f"   in force: data-theme={inforce['theme']!r}, "
                  f"wozi-speed={inforce['speed']!r}, panel open")
            if inforce["theme"] != theme:
                _FAILURES.append(
                    f"asked for the {theme} theme and the page reports "
                    f"{inforce['theme']!r} — this pass audited the wrong theme, so "
                    f"its findings are about the other one")
            if inforce["speed"] != "5":
                _FAILURES.append(
                    f"asked for 5x and the page reports wozi-speed="
                    f"{inforce['speed']!r} — the corner departure indicator is "
                    f"display:none at 1x, so it was not audited (GitHub #108)")
            await ev(axe_src)
            # THE PIN IS READ BACK, NOT ASSUMED (GitHub #165). A version nobody
            # verifies is the same class of fault as a theme planted in localStorage
            # and never read: AXE_PATH and a stale cache are both routes to auditing
            # under a ruleset other than the one named above, and the report would
            # say the pinned version either way. Exit 2 rather than 1 -- a run under
            # an unknown ruleset has not measured what it claims to have measured.
            loaded = await ev("(typeof axe!=='undefined'&&axe.version)||''")
            if loaded != AXE_VERSION:
                print(f"FATAL: pinned axe-core {AXE_VERSION} and the page loaded "
                      f"{loaded or 'nothing'!r} (from {_use}). This audit ran under a "
                      f"ruleset nobody named, so its verdict is not attributable.")
                proc.kill()
                return 2
            # THE NODES COME BACK WITH THE COUNT. A finding stated as
            # "color-contrast x3" is a fact nobody can act on: which three, and
            # by how much? axe already knows -- it is the `any` check's own
            # message, carrying the two colours and the ratio it wanted.
            # `incomplete` COMES BACK WITH THE VIOLATIONS, and it is reported
            # rather than asserted (GitHub #157). axe puts a check it could not
            # decide into `incomplete`, not `violations` -- and on a page painted
            # almost entirely in inline gradients, `color-contrast` is exactly the
            # rule that lands there, because axe cannot resolve a background it
            # cannot flatten to one colour. So "no violations" was a weaker
            # sentence than it read as: it did not mean axe had cleared the page,
            # only that nothing it could decide came out failing.
            #
            # NOT A FAILURE, deliberately. An undecided check is an open question,
            # and a gate that goes red on an open question trains everyone to
            # ignore it -- the same #41/#46 reasoning that keeps `moderate` out of
            # the verdict. It is printed so the operator sees the size of what axe
            # declined to judge, and so a change that moves a rule FROM decided TO
            # undecided is visible instead of reading as a clean run.
            #
            # `resultTypes` is left naming only `violations`: it controls which
            # buckets get every node populated, and one node per incomplete rule
            # is all this printout wants. The invisibility was `r.violations.map`,
            # not that flag.
            res = await ev("axe.run(document,{resultTypes:['violations']}).then(r=>JSON.stringify({"
                           "v:r.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,"
                           "n:v.nodes.length,nodes:v.nodes.slice(0,6).map(nd=>({"
                           "t:(nd.target||[]).join(' '),"
                           "why:((nd.any||[])[0]||{}).message||nd.failureSummary||''}))})),"
                           "i:r.incomplete.map(x=>({id:x.id,impact:x.impact,n:x.nodes.length,"
                           "t:((x.nodes[0]||{}).target||[]).join(' '),"
                           "why:(((x.nodes[0]||{}).any||[])[0]||{}).message||''}))}))", True)
            parsed = json.loads(res)
            v, inc = parsed["v"], parsed["i"]
            if not v:
                print("   no violations")
            for x in sorted(v, key=lambda z: ["critical","serious","moderate","minor"].index(z["impact"] or "minor")):
                print(f"   [{(x['impact'] or '?').upper():<8}] {x['id']:<28} x{x['n']}  {x['help']}")
                for nd in x.get("nodes", []):
                    print(f"       {nd['t']}")
                    print(f"         {' '.join(nd['why'].split())[:150]}")
                # WHAT ACTUALLY FAILS THIS GATE. Only critical and serious, so
                # the check has teeth without turning red over a moderate hint
                # nobody has agreed to act on -- a gate that fails on an open
                # question trains everyone to ignore it (#41, #46).
                if (x["impact"] or "") in ("critical", "serious"):
                    _FAILURES.append(f"axe {theme}: [{x['impact']}] {x['id']} x{x['n']} — {x['help']}")
            if inc:
                print(f"   axe could not DECIDE {len(inc)} rule(s) here — reported, not failed:")
                for x in inc:
                    print(f"   [undecided] {x['id']:<28} x{x['n']}  {x['t'][:60]}")
                    if x["why"]:
                        print(f"         {' '.join(x['why'].split())[:150]}")
            else:
                print("   nothing undecided")
            # THE BATTERY RUNS IN BOTH THEMES NOW (GitHub #157). It used to be
            # gated on `theme == "dark"`, which made the 24x24 floor, the
            # duplicate-name check, lang/main and the unlabelled-focusable count
            # assertions about ONE theme in a tool whose whole reason for iterating
            # two is that findings differ between them. Nothing here is
            # theme-independent by construction: a target's box comes from the
            # style that painted it, and the accessible names come from a DOM built
            # per render.
            #
            # The VERBOSE printout stays dark-only, because that half is a
            # description of the page rather than a check, and printing it twice
            # buries the assertions in a log nobody reads twice. The ASSERTIONS run
            # in both and name their theme.
            m = json.loads(await ev(MANUAL))
            if theme == "dark":
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
                print(f"   targets under 24x24px    : {len(m['smallTargets'])}")
                # THE MARGIN, NOT ONLY THE VERDICT (GitHub #145). The floor is
                # 24x24 and "0 under it" says nothing about whether the tightest
                # target clears it by 20px or by 0.2 -- and these boxes are the
                # ones that could in principle be set by their own label, which
                # is what made this harness worth measuring for the font race.
                for t in m.get("tightest", []):
                    print(f"     {t['min']:>7.2f}px min  {t['w']}x{t['h']}  "
                          f"{t['tag'].lower()}  {t['name'][:38]}")
                for t in m["smallTargets"]:
                    print(f"   UNDER THE FLOOR          : {t['w']}x{t['h']}px  "
                          f"{t['tag'].lower()}  {t['name'][:38]}")
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
            else:
                # One line for the theme that does not get the full printout, so a
                # reader can tell the battery RAN here rather than assuming it did.
                print(f"   structural battery, {theme} theme: "
                      f"{len(m['smallTargets'])} target(s) under 24x24px, "
                      f"{m['focusable']} focusable ({m['focusableNoLabel']} unlabelled), "
                      f"{len(m['dupNames'])} duplicate name(s), "
                      f"tightest {min((t['min'] for t in m.get('tightest', [])), default=float('nan')):.2f}px")
            # WCAG 2.5.8 target size. Two-sided by nature -- there is no
            # upper bound worth asserting on a hit target, so this one floor
            # is the whole check.
            if m["smallTargets"]:
                _FAILURES.append(
                    f"{theme}: {len(m['smallTargets'])} interactive target(s) under "
                    f"24x24px (WCAG 2.5.8): "
                    + ", ".join(f"{t['name']} {t['w']}x{t['h']}"
                                for t in m["smallTargets"][:6]))
            if not m["lang"]:
                _FAILURES.append(f"{theme}: no lang attribute on <html>")
            if not m["main"]:
                _FAILURES.append(f"{theme}: no <main> landmark")
            if m["focusableNoLabel"]:
                _FAILURES.append(f"{theme}: {m['focusableNoLabel']} focusable element(s) "
                                 f"with no accessible name")
            for name, n in m["dupNames"]:
                _FAILURES.append(
                    f'{theme}: {n} focusables share the accessible name "{name}" and do not '
                    f"share a destination (WCAG 2.4.4/4.1.2)")
            # AFTER everything measured in this theme, never before: the probe
            # appends and removes a span, and a state read before the page was
            # measured says nothing about the render that was.
            await pin.state(send, label=f"{theme} theme")
    proc.kill()
    # The typography every render drew in, verified rather than assumed. A leak
    # means nothing above is a statement about the page.
    if not pin.report():
        _FAILURES.append("the font pin leaked — see the MISMATCH line above")
    # AN EXIT CODE, so this is a gate rather than a printout (#47). It ended at
    # asyncio.run(main()) with main() returning None, so it exited 0 whatever it
    # found -- and every "axe clean, gate green" in the merge log was a report
    # somebody read, not a check that could go red.
    return 1 if _FAILURES else 0

if __name__ == "__main__":
    # THE FONT DECISION IS TAKEN BEFORE CHROME EXISTS, and that ordering is the
    # whole mechanism -- a pin built after the first navigation is decoration. The
    # stylesheet URL comes off the SERVED page rather than this repo's
    # index.html, because this harness is pointed at a server somebody else
    # started and it may be serving another worktree entirely.
    _pin = fontpin.FontPin.decide(want=_ARGS.fonts, url=URL)
    _fatal = _pin.announce()
    if _fatal:
        print(_fatal)
        sys.exit(2)
    _code = asyncio.run(main(_pin))
    # EXIT 2 GETS ITS OWN SENTENCE, and until GitHub #165 it did not: this branched
    # on _FAILURES alone, so every path that returned 2 -- axe-core unreachable, the
    # panel never opening, a ruleset that is not the pinned one -- printed
    # "RESULT: PASS" on its way out. The exit code was right and the line a human
    # reads was its opposite, which is #156's lie relocated into the reporting layer:
    # nobody greps an exit code out of a CI log, they read the last line.
    if _code == 2:
        print("\nRESULT: NOT AUDITED — see the FATAL above. Nothing has been proved "
              "either way; this is not a pass.")
    elif _FAILURES:
        print("\nRESULT: FAIL")
        for f in _FAILURES:
            print("  " + f)
    else:
        print("\nRESULT: PASS")
    sys.exit(_code or (1 if _FAILURES else 0))
