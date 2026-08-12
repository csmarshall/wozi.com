#!/usr/bin/env python3
"""Does an ESCAPE-RUN GHOST actually mesh with what it grew from? (GitHub #117)

    tools/escape_mesh.py                       # serves the repo itself
    tools/escape_mesh.py --census              # every residual, not just verdicts
    tools/escape_mesh.py --query '?who=charles'
    tools/escape_mesh.py --seeds 20260804 --viewports 1440x900

WHY A HARNESS OF ITS OWN. tools/dom_invariants.py's mesh check deliberately sees
only the wheels solve() placed: its element test requires the anchor's parent to
be the artwork container itself, and an escape-run ghost lives one level deeper,
inside the ghost layer. That exemption is correct for the assertion it makes --
"no wheel is an orphan" -- because an escape run ENDS, and two unrelated runs are
not required to mesh. But it left the majority of the wheels on the page, 14 on a
solo stage and 200+ on a wide one, with nothing checked about them at all. #117
is Charles pointing at a screenshot: "this configuration doesn't look possible."

CL#80's derivation is the claim under test. A run is grown wheel to wheel, each
step at `prev.r + r` from the last, and the wheel count is bounded by "the
shortest possible step = two minimum wheels in mesh, foreshortened by
ESCAPE_WOBBLE". So every consecutive pair in a run is MEANT to mesh, and so is
the first ghost against the wheel it hangs off. Nothing has ever measured
whether the rendered page agrees.

WHAT IS ASSERTED, and it is stated per RUN because a wheel list cannot express
it: within one run, ghost k meshes with ghost k-1; ghost 0 meshes with its host.
Nothing is asserted ACROSS runs, or about where a run ends -- runs deliberately
stop, and two runs passing near each other are unrelated.

MEASURED OFF THE RENDERED DOM, NEVER MODELLED (GitHub #102). Positions are
`getBoundingClientRect()` on the zero-size ANCHOR div -- which is exactly the
wheel's centre, carries no rotation of its own, and has every ancestor transform
already applied, including the ghost layer's parallax scale and the stage's
portrait rotation. (dom_invariants avoids getBoundingClientRect because a
ROTATING element returns the box of a spinning square; the anchor is not the
rotating element, its child is.) Radii come off the <svg> width ATTRIBUTE and are
converted to a pitch radius with dom_invariants' own pads, imported rather than
restated -- CLAUDE.md is explicit that the page and its gates must not disagree
about what "meshes" means, and a second definition of it here is the failure this
file would otherwise introduce. TOL_MESH_PX comes from there too.

THE ONE THING READ OUT OF THE PAGE RATHER THAN OFF IT is the RUN STRUCTURE --
which ghost belongs to which run, at what index, hanging off which host. That is
not geometry and cannot be recovered from a picture: it is bookkeeping
fitEscapes() already records on each ghost (`person`, `lead`, `k`, `hostCx`,
`hostCy`) precisely because "a run's heading only means anything measured from
its host". Re-deriving membership from positions would mean modelling the rule
under test and then checking the model against itself. So membership is taken
from the page and every NUMBER is measured from the DOM.

SEEDED AND IN BOTH ORIENTATIONS. The deal is pinned exactly as dom_invariants,
devices.py and pixel_regress do, by injecting an LCG over Math.random through
Page.addScriptToEvaluateOnNewDocument with the seed BAKED INTO THE CLOSURE and
never named in the URL (CL#109 forbids gates using the page's own `?seed`, and
GitHub #155 is the entry about this file having used it anyway: the injected
script read `location.search`, so it only ran when the page's own handler ran
too, and index.html's DEAL_SEED -- module scope, later than any injected script
-- then dealt the machine itself. The injection was dead code and the sentence
above was false for as long as it stood. `dom.seed_js()` is the one home for the
generator now, and the residuals this file prints all changed at CL#180 because
every machine it measures did).

Portrait is not optional: the stage rotates the whole train by
`_axisRot`, and CLAUDE.md records two separate bugs from geometry that honoured
the screen instead of the axis -- both of which only a measurement in screen
space could see.

Exit 0 if every run meshes, 1 if any ghost does not, 2 if it could not measure.

THIS HARNESS DOES NOT PIN THE WEBFONT, AND THAT IS THE MEASURED ANSWER RATHER
THAN AN OMISSION (GitHub #145). `tools/fontpin.py` exists because the page's
drawing depends on WHEN Manrope arrives relative to its own first render (#98),
and four gates import it. This one was held to the same test CL#168 applied to
the others -- a full `--census` run with both font hosts blackholed at Chrome's
resolver, against a normal run -- and the two outputs are IDENTICAL: 4 seeds x 2
viewports, every run, every ghost, every residual to the last printed digit, the
only differing line being the ephemeral port the server bound. Zero exposure, so
pinning would add a mechanism and prove nothing. RE-RUN AT CL#180 and still
identical, which was not optional: GitHub #155 changed every deal this file
measures, so the CL#168 result was a measurement about machines that no longer
exist.

Two reasons it comes out that way, and both would have to change before this
paragraph does. Every number here is a radius or a centre, taken off the anchor
divs and the svg width attribute -- no text is measured, laid out, or even
looked at. And the console errors it collects come from `Runtime` only; `Log` is
never enabled, so the `ERR_CONNECTION_REFUSED` a blocked stylesheet produces is
invisible here, where it is what made `verify_motion` go red for a font outage.
"""

import argparse
import asyncio
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# THE DEFINITION OF "MESHES", IMPORTED. Not re-derived, not re-typed: the pads
# that turn a padded svg width back into a pitch radius, and the tolerance that
# analysis of --gsfit's lossy recovery justified, both live in dom_invariants.py
# and this harness must agree with them by construction. If that file's pad
# regexes stop matching index.html it exits fatally on import here too, which is
# the correct outcome -- a harness that cannot find the padding cannot measure a
# radius.
import dom_invariants as dom  # noqa: E402

CHROME, CI_FLAGS, ROOT = dom.CHROME, dom.CI_FLAGS, dom.ROOT
PAD_LINKED, PAD_GHOST, TOL_MESH_PX = dom.PAD_LINKED, dom.PAD_GHOST, dom.TOL_MESH_PX

# WHAT THAT TOLERANCE ACTUALLY BUYS *HERE*, re-measured at CL#180 over 24 deals
# (12 seeds x 2 viewports) because GitHub #155 changed every one of them. Worst
# residual on a ghost the gate calls meshing: 0.0233px against the 0.35px bound,
# a 15x margin. It is worth stating separately from dom_invariants' own number
# because a ghost's residual comes out an order of magnitude LARGER than a
# structural pair's (0.0036px there) and consistently so -- an observation, with
# no mechanism established for it here, and therefore not a number either file
# may borrow from the other. THE MARGIN TIGHTENED at CL#180 -- the old deals' worst was
# 0.0197px, an 18x margin -- which is a property of which machines get dealt and
# not of the geometry. 15x is still an order of magnitude clear of the bound, so
# the bound is unchanged; a future re-characterisation that lands under about 5x
# is the one that should move it.

# How close an escape ghost's recorded host coordinate has to land to a rendered
# structural wheel's own inline centre before we believe they are the same wheel.
# This is an IDENTITY match, not a geometry test: both numbers are the same
# quantity in the same solve units, written by the same render pass, so they
# agree to float noise. It is loose only because S is recovered from --gsfit's
# 3-decimal string (see dom_invariants' tolerance note) and both sides of the
# comparison are multiplied through it.
HOST_MATCH_PX = 1.5


def serve(directory):
    """A server per run, on its own port (#42 -- never a fixed one). Returns
    (proc, base_url). The gate serves the repo itself rather than trusting a
    server the caller may or may not have started somewhere else: a harness
    pointed at nothing measures no wheels, and no wheels is a green verdict on
    every check that iterates over them."""
    port = dom.free_port()
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
    # print-then-2, never `SystemExit("...")`: the string form exits 1, which the
    # docstring above promises means "a ghost does not mesh" (GitHub #156).
    print(f"FATAL: could not serve {directory}")
    raise SystemExit(2)


# ---- the one evaluate ------------------------------------------------------
#
# STRUCTURAL WHEELS are found with dom_invariants' own element test, character
# for character: an <svg> whose parent has `willChange: transform` and whose
# grandparent is the `aria-hidden="true"` artwork container. That is what
# separates "solved with the train" from "dealt afterwards by fitEscapes", and
# copying the test rather than inventing a looser one is what keeps the two
# harnesses talking about the same set of wheels.
#
# ESCAPE GHOSTS are taken from `_ghostEls`, the array the render pass already
# builds to drive applyRotation -- {el, g} pairs of the rotating div and the
# ghost it was rendered from. It is reached by walking the React fiber up from
# the artwork container to the component that owns it. Only the BOOKKEEPING on
# `g` is used (person / lead / k / host centre); every position and radius below
# is measured off `el` and its <svg>.
#
# THE SCALE FACTOR IS ACCUMULATED FROM THE ANCESTORS rather than assumed to be
# 1. `parallax` ships false, so the ghost layer's `scale(0.94)` is not applied
# today -- but #117's leading hypothesis is exactly a scale mismatch between the
# ghost layer and the train, and a harness that hardcoded 1 would be unable to
# see the bug it was written for. sqrt(|det|) is the uniform scale of whatever
# 2D matrix is on each ancestor, so a pure rotation contributes exactly 1 and
# the portrait axis rotation drops out on its own.
SAMPLE_JS = r"""
(() => {
  const fiberOf = (el) => {
    for (const k in el) {
      if (k.indexOf('__reactFiber$') === 0 || k.indexOf('__reactInternalInstance$') === 0)
        return el[k];
    }
    return null;
  };
  const scaleOf = (el) => {
    let s = 1;
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const t = getComputedStyle(n).transform;
      if (!t || t === 'none') continue;
      const m = new DOMMatrix(t);
      const det = Math.abs(m.a * m.d - m.b * m.c);
      if (det > 0) s *= Math.sqrt(det);
    }
    return s;
  };

  let stageEl = null;
  const structural = [];
  document.querySelectorAll('svg').forEach((svg) => {
    const spin = svg.parentElement;
    if (!spin || getComputedStyle(spin).willChange !== 'transform') return;
    const anchor = spin.parentElement;
    const stage = anchor && anchor.parentElement;
    if (!stage || stage.getAttribute('aria-hidden') !== 'true') return;
    const st = anchor.getAttribute('style') || '';
    const pos = st.match(/left:\s*([-0-9.]+)px;\s*top:\s*([-0-9.]+)px/);
    const w = parseFloat(svg.getAttribute('width'));
    if (!pos || !(w > 0)) return;
    stageEl = stage;
    const r = anchor.getBoundingClientRect();
    structural.push({
      /* screen centre: the anchor is width:0;height:0, so its rect origin IS
         the centre, with every ancestor transform already applied */
      x: r.left, y: r.top, w: w, scale: scaleOf(anchor),
      /* solve-space centre, used only to identify a ghost's recorded host */
      lx: parseFloat(pos[1]), ly: parseFloat(pos[2]),
      linked: !!(svg.firstElementChild &&
                 svg.firstElementChild.tagName.toLowerCase() === 'defs')
    });
  });

  /* The page's own class is not the fiber's stateNode: support.js wraps it in a
     StreamableComponent and keeps the instance on `.logic`. Both are tried, and
     the test is "does it own _ghostEls" rather than a class name, so a change to
     the wrapper cannot silently strand this. */
  let app = null;
  for (let f = stageEl ? fiberOf(stageEl) : null; f && !app; f = f.return) {
    const sn = f.stateNode;
    if (!sn || sn.nodeName) continue;
    if (sn._ghostEls) app = sn;
    else if (sn.logic && sn.logic._ghostEls) app = sn.logic;
  }

  const ghosts = [];
  if (app) (app._ghostEls || []).forEach((x) => {
    if (!x || !x.el || !x.g) return;
    const anchor = x.el.parentElement;
    const svg = x.el.querySelector('svg');
    if (!anchor || !svg) return;
    const r = anchor.getBoundingClientRect();
    const w = parseFloat(svg.getAttribute('width'));
    if (!(w > 0)) return;
    ghosts.push({
      x: r.left, y: r.top, w: w, scale: scaleOf(anchor),
      /* bookkeeping, not geometry: which run, where in it, off which wheel */
      person: x.g.person === undefined ? null : x.g.person,
      lead: !!x.g.lead, k: x.g.k,
      hostCx: x.g.hostCx, hostCy: x.g.hostCy, teeth: x.g.teeth
    });
  });

  const raw = parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue('--gsfit'));
  return JSON.stringify({
    structural: structural, ghosts: ghosts, reachedApp: !!app,
    S: Math.floor((raw || 0) * 100) / 100,
    portrait: window.innerHeight > window.innerWidth * 1.05
  });
})()
"""


async def sample(url, seed, viewport, theme):
    """One navigation, one evaluate. Bootstrapping copied from
    tools/dom_invariants.py, including the rule that `Page.enable` must precede
    the injection -- without it the seed script is accepted and silently never
    runs, which reads as two different deals and the same green verdict. The seed
    is baked into the injected closure and the URL carries no `seed=` at all
    (GitHub #155)."""
    port = int(os.environ.get("CDP_PORT") or 0) or dom.free_port()
    profile = os.environ.get("CHROME_PROFILE") or tempfile.mkdtemp(prefix="wozi-esc-")
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
                req = urllib.request.Request(target, method=method) if method else target
                ws_url = json.load(urllib.request.urlopen(req, timeout=1))["webSocketDebuggerUrl"]
                break
            except Exception:
                pass
        if ws_url:
            break
        time.sleep(0.2)
    if not ws_url:
        proc.kill()
        return None, ["could not reach Chrome DevTools endpoint"]

    errors = []
    mid = 0
    raw = None
    try:
        async with websockets.connect(ws_url, max_size=10 ** 8) as ws:
            async def send(method, params=None):
                nonlocal mid
                mid += 1
                my = mid
                await ws.send(json.dumps({"id": my, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("method") == "Runtime.exceptionThrown":
                        det = msg["params"]["exceptionDetails"]
                        errors.append("exception: " + str(det.get("text", ""))[:160])
                    elif msg.get("method") == "Runtime.consoleAPICalled":
                        if msg["params"]["type"] in ("error", "assert"):
                            args = [str(a.get("value", a.get("description", "")))
                                    for a in msg["params"]["args"]]
                            errors.append("console.error: " + " ".join(args)[:160])
                    if msg.get("id") == my:
                        return msg.get("result", {})

            await send("Page.enable")
            await send("Runtime.enable")
            await send("Page.addScriptToEvaluateOnNewDocument", {"source": dom.seed_js(seed)})
            await send("Page.addScriptToEvaluateOnNewDocument",
                       {"source": "try{localStorage.setItem('wozi-theme','%s')}catch(e){}" % theme})
            await send("Emulation.setDeviceMetricsOverride",
                       {"width": viewport[0], "height": viewport[1],
                        "deviceScaleFactor": 1, "mobile": False})
            # NO `seed=` IN THE URL (GitHub #155) -- the deal comes off the baked
            # closure above, and naming a seed here would hand it to index.html's
            # own DEAL_SEED, which runs later and wins.
            await send("Page.navigate", {"url": url})
            # fitEscapes runs out of the fit pass, which settles a beat after the
            # first paint -- the runs do not exist at load.
            await asyncio.sleep(4.0)
            res = await send("Runtime.evaluate",
                             {"expression": SAMPLE_JS, "returnByValue": True})
            raw = res.get("result", {}).get("value")
    finally:
        proc.kill()
        if not os.environ.get("CHROME_PROFILE"):
            shutil.rmtree(profile, ignore_errors=True)
    if not raw:
        return None, errors + ["the page returned nothing to measure"]
    return json.loads(raw), errors


def pitch(w, scale, S, linked):
    """A rendered pitch radius, in SCREEN pixels. The svg's own width overstates
    it by the addendum plus that renderer's padding (see dom_invariants), and
    the whole element is then drawn through whatever its ancestors scale it by."""
    return (w / 2 - (PAD_LINKED if linked else PAD_GHOST) * S) * scale


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def check_runs(payload, S, census, label):
    """The assertion, stated per run.

    Within a run, consecutive wheels mesh, and the first one meshes with the
    wheel it grew from. Nothing across runs, and nothing about where a run
    ends -- a run stopping is what a run is for.
    """
    fails, notes = [], []
    ghosts, structural = payload["ghosts"], payload["structural"]
    if not payload["reachedApp"]:
        return ([f"{label}: could not reach the component that owns the escape runs -- "
                 f"the run structure is not recoverable, so nothing can be asserted"], [])
    if not structural:
        return ([f"{label}: no structural wheels on the stage -- a check that iterates "
                 f"over nothing passes vacuously"], [])
    if not ghosts:
        return ([f"{label}: no escape ghosts at all. Every run refused, or the layer did "
                 f"not render -- either way this gate has measured nothing"], [])

    for g in ghosts:
        g["rp"] = pitch(g["w"], g["scale"], S, False)
    for w in structural:
        w["rp"] = pitch(w["w"], w["scale"], S, w["linked"])

    # RUN IDENTITY. Each host contributes at most one run, and a host is
    # (chain, which end) -- fitEscapes pushes exactly one leading and one
    # trailing host per chain, never two of either.
    runs = {}
    for g in ghosts:
        runs.setdefault((g["person"], g["lead"]), []).append(g)
    for key in runs:
        runs[key].sort(key=lambda g: g["k"])

    worst = 0.0
    worst_who = None
    measured = 0
    for (person, lead) in sorted(runs, key=lambda t: (str(t[0]), t[1])):
        run = runs[(person, lead)]
        end = "leading" if lead else "trailing"
        ks = [g["k"] for g in run]
        if ks != list(range(len(run))):
            fails.append(f"{label}: run {person}/{end} has indices {ks} -- not a run "
                         f"but a set of wheels, so 'the next wheel in the run' is undefined")
            continue
        for g in run:
            if g["k"] == 0:
                # The host is a wheel solve() already placed. Identity comes off
                # the centre fitEscapes recorded; the GEOMETRY comes off whatever
                # the DOM says that wheel actually rendered at.
                hx, hy = g["hostCx"] * S, g["hostCy"] * S
                host = min(structural, key=lambda w: math.hypot(w["lx"] - hx, w["ly"] - hy))
                off = math.hypot(host["lx"] - hx, host["ly"] - hy)
                if off > HOST_MATCH_PX:
                    fails.append(f"{label}: run {person}/{end} names a host at "
                                 f"({g['hostCx']:.1f},{g['hostCy']:.1f}) solve units and the "
                                 f"nearest rendered wheel is {off:.2f}px away -- the run hangs "
                                 f"off a wheel that is not on the stage")
                    continue
                partner, what = host, f"its host ({'linked' if host['linked'] else 'idler'})"
            else:
                partner, what = run[g["k"] - 1], f"ghost {g['k'] - 1} of its run"
            resid = dist(g, partner) - (g["rp"] + partner["rp"])
            measured += 1
            if abs(resid) > worst:
                worst, worst_who = abs(resid), f"{person}/{end} ghost {g['k']} vs {what}"
            if census:
                print(f"                 {str(person):>8}/{end:<8} ghost {g['k']:>2} vs "
                      f"{what:<24} residual {resid:+.4f}px")
            if abs(resid) > TOL_MESH_PX:
                fails.append(f"{label}: {person}/{end} ghost {g['k']} does not mesh with "
                             f"{what} -- centres {dist(g, partner):.2f}px apart against a "
                             f"pitch sum of {g['rp'] + partner['rp']:.2f}px, off by "
                             f"{resid:+.2f}px (tolerance {TOL_MESH_PX}px)")

    # GHOST AGAINST THE TRAIN, reported and never asserted. #117 asks for it --
    # "a ghost fouling a linked wheel is a different and worse failure" -- but an
    # escape run is explicitly allowed to pass over wheels it has no relationship
    # with, so a hard failure here would be this gate inventing a rule the page
    # does not have. It is printed so the number is on the record either way.
    fouls = []
    for g in ghosts:
        for w in structural:
            gap = dist(g, w) - (g["rp"] + w["rp"])
            if gap < -TOL_MESH_PX:
                fouls.append((g, w, gap))
    if fouls:
        deep = min(f[2] for f in fouls)
        notes.append(f"{label}: {len(fouls)} ghost/structural pair(s) overlap, deepest "
                     f"{-deep:.1f}px (reported, not asserted -- an escape run may pass "
                     f"over a wheel it has no relationship with)")

    print(f"  {label:<28} {'ok  ' if not fails else 'FAIL'} {len(runs)} run(s), "
          f"{len(ghosts)} ghosts, {measured} mesh(es) measured; worst residual "
          f"{worst:.4f}px of {TOL_MESH_PX}px"
          + (f" ({worst_who})" if worst_who and worst > TOL_MESH_PX else ""))
    return fails, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", default=None,
                    help="a served page; omit and this serves the repo itself")
    ap.add_argument("--query", default="",
                    help="scope query, e.g. '?who=charles'. 127.0.0.1 is a STAGE_HOSTS "
                         "name, so with no query this measures the combined stage")
    ap.add_argument("--seeds", default="20260804,8231,17,999983",
                    help="comma-separated LCG seeds; the verdict is a property of these")
    ap.add_argument("--viewports", default="1440x900,900x1440",
                    help="comma-separated WxH. Both orientations by default -- portrait "
                         "rotates the whole train and is where this file's bugs hide")
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--census", action="store_true",
                    help="print every residual, not just the verdicts")
    a = ap.parse_args()

    # A query with no '?' becomes a PATH on a bare directory URL: 'who=charles'
    # asks for a file of that name and gets a 404, which has no wheels to fail
    # on. Same trap dom_invariants.py and pixel_regress.py guard.
    if a.query and not a.query.startswith("?"):
        print(f"FATAL: --query must start with '?' (got {a.query!r})")
        return 2
    try:
        viewports = [tuple(int(n) for n in v.strip().lower().split("x"))
                     for v in a.viewports.split(",") if v.strip()]
        assert viewports and all(len(v) == 2 for v in viewports)
    except (ValueError, AssertionError):
        print(f"FATAL: --viewports must be a comma-separated list of WxH (got {a.viewports!r})")
        return 2
    try:
        seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
        assert seeds
    except (ValueError, AssertionError):
        print(f"FATAL: --seeds must be a comma-separated list of integers (got {a.seeds!r})")
        return 2

    t0 = time.time()
    server = None
    url = a.url
    if not url:
        server, url = serve(ROOT)
    try:
        print(f"{url + a.query}   {a.theme} theme, radius pad {PAD_LINKED:.2f} linked / "
              f"{PAD_GHOST:.2f} ghost solve units, tolerance {TOL_MESH_PX}px\n")
        fails, notes, errors = [], [], []
        for seed in seeds:
            for vw, vh in viewports:
                payload, errs = asyncio.run(
                    sample(url + a.query, seed, (vw, vh), a.theme))
                orient = "portrait" if vh > vw * 1.05 else "landscape"
                label = f"seed {seed} {vw}x{vh} {orient}"
                if payload is None:
                    print(f"  {label:<28} FAIL could not measure: {'; '.join(errs)}")
                    fails.append(f"{label}: the page returned nothing to measure")
                    continue
                if payload["S"] <= 0:
                    print(f"  {label:<28} FAIL --gsfit unreadable")
                    fails.append(f"{label}: --gsfit unreadable, so there is no pitch radius")
                    continue
                f, n = check_runs(payload, payload["S"], a.census, label)
                fails += f
                notes += n
                errors += [e for e in errs if "favicon.ico" not in e]
    finally:
        if server:
            server.kill()

    if notes:
        print("\nnotes:")
        for n in notes:
            print("  " + n)
    if errors:
        print(f"\nconsole errors: {len(errors)}")
        for e in errors[:10]:
            print("  " + e)
    if fails:
        print(f"\n{len(fails)} failure{'s' if len(fails) != 1 else ''}:")
        for f in fails[:40]:
            print("  " + f)
        if len(fails) > 40:
            print(f"  ... and {len(fails) - 40} more")
        print(f"\nRESULT: FAIL   ({time.time() - t0:.1f}s)")
        return 1
    print(f"\nRESULT: PASS   ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
