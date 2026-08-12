#!/usr/bin/env python3
"""Break the page on purpose and prove the gate that should catch it goes red.

    tools/mutation_gate.py                 # every mutant, every gate  (~9 min)
    tools/mutation_gate.py --gate suite    # one gate's mutants        (~19 s)
    tools/mutation_gate.py --only sleep-latched
    tools/mutation_gate.py --list          # the registry, no browsers
    tools/mutation_gate.py --blind         # prove THIS gate can fail

WHY THIS EXISTS. A gate observed green is not a gate proven able to fail. This
repo has shipped a harness that printed FAIL and exited 0, one that had been
dead with a NameError for weeks, and one with no exit code at all — and every
"gate green" reported out of any of them was a printout somebody read. Nothing
in CI could tell those apart from a gate that was working, because a working
gate and a blind gate produce the same thing on a tree with no bug in it.

The only way to tell them apart is to put a bug in the tree. Each mutant below
is one surgical, reversible substitution that a NAMED gate must catch, chosen to
reproduce a failure this project has actually had rather than an arbitrary
scramble. The runner applies it, runs that gate, requires a non-zero exit,
restores, and — once per gate, after its mutants — runs the gate on the restored
tree and requires zero. Red for a stated reason, then green again.

NOTHING IS MUTATED IN YOUR WORKING TREE. Everything happens in a throwaway
`git worktree` checked out at --ref (HEAD by default) under a temp dir, thrown
away at the end. That is not caution for its own sake: `git stash` on a clean
tree stashes nothing and reports success, so a stash-based runner silently tests
the UNMUTATED tree and passes every time. The consequence is worth stating out
loud — this gate measures the COMMITTED tree, so uncommitted work is invisible
to it, and it says so at startup when the tree is dirty.

THREE KINDS OF EXPECTATION. Most mutants are `caught`: the gate must go red. A
few are `survives`, a gap that is known, filed and deliberately not papered
over. Those are asserted to survive, so the day somebody strengthens the gate
this runner fails with "the documented gap has closed" and the registry gets
updated instead of quietly keeping a stale excuse.

The third is `tolerated`, and it is the opposite claim: the substitution is a
LEGITIMATE edit and the gate must stay GREEN. A gate can fail in two directions
and only one of them is a false negative — `tolerated` is how the other is kept
proved. It exists because a gate that reads the page as TEXT can be broken by an
edit that changes no behaviour at all: `tools/test.js` extracts 66 blocks out of
`index.html` by literal anchor, and until GitHub #137 twenty-one of those anchors
baked in two spaces of indentation, so re-indenting a method — a `git diff -w`
no-op — turned the suite red for nothing. A `tolerated` mutant is not a gap and
not a bug; it is the negative control that says the refusal is aimed at real
faults and not at whitespace.

Exit 0 only if every mutant met its expectation (red for `caught`, green for
`survives` and `tolerated`) and every control run was green.
Exit 1 on any survivor, any closed gap, or any control that could not go green.
Exit 2 if a mutation could no longer be applied — the string it edits is gone,
which means the page moved out from under the registry and these mutants have
been testing nothing.
"""

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# The gates. Each is exactly the command CI runs (or, for `pixels`, the command
# CHANGELOG #48 ran by hand), not a reimplementation of it — a mutation gate
# testing its own copy of a gate would prove nothing about the one that ships.
#
# `server` says whether the gate needs the tree served and the URL appended.
# It is never a fixed port: several of these run concurrently on this machine
# and #42 is what happens when two harnesses share one.
# ---------------------------------------------------------------------------
GATES = {
    "suite":  {"argv": ["node", "tools/test.js"], "server": False,
               "what": "tools/test.js — the geometry suite (CI, every push)"},
    "motion": {"argv": [sys.executable, "tools/verify_motion.py"], "server": True,
               "what": "tools/verify_motion.py — the train turns (CI, every push)"},
    "type":   {"argv": [sys.executable, "tools/pill_clip.py"], "server": True,
               "what": "tools/pill_clip.py — the pill label fits its clip (CI, every push)"},
    "pixels": {"argv": [sys.executable, "tools/pixel_regress.py", "--ref", "HEAD",
                        "--viewport", "1440x900"], "server": False,
               "what": "tools/pixel_regress.py — the drawing is unchanged (manual)"},
    "layout": {"argv": [sys.executable, "tools/devices.py"], "server": True,
               "what": "tools/devices.py — the train fills the long axis (CI, every push)"},
}

# ---------------------------------------------------------------------------
# The registry. Ordered cheapest gate first so a broken tree is reported in
# seconds rather than after the three-and-a-half-minute device sweep.
#
# `find` must occur EXACTLY ONCE in `file`. That is the anti-rot property: when
# somebody renames a constant, this runner stops with exit 2 and says which
# mutant went stale, instead of applying nothing and reporting a clean sweep.
# ---------------------------------------------------------------------------
MUTANTS = [
    {
        "id": "band-depth-halved",
        "gate": "suite",
        "file": "index.html",
        "find": "const BAND_DEPTH = 1.59;",
        "repl": "const BAND_DEPTH = 0.50;",
        "expect": "caught",
        "why": "CLAUDE.md names this exact edit as the dangerous class: BAND_DEPTH "
               "feeds the bore, a bigger bore makes gear sets reachable that nothing "
               "has ever measured, and the band is what #15 was. The suite reads the "
               "constant out of index.html, so a mutant here is also the test of that "
               "reading — a suite holding its own copy would agree with itself and "
               "stay green.",
    },
    {
        "id": "stage-host-on-a-person",
        "gate": "suite",
        "file": "config.js",
        "find": "hosts: ['charles.wozi.com'],",
        "repl": "hosts: ['charles.wozi.com', 'wozi.com'],",
        "expect": "caught",
        "why": "The host model's one hard rule: STAGE_HOSTS and a person's solo hosts "
               "must stay disjoint, because STAGE_HOSTS is matched first — a name in "
               "both quietly means 'everyone' while config.js reads as though it named "
               "one person, and only a screenshot would show it. A second suite mutant "
               "on purpose: the geometry half and the configuration half of test.js are "
               "different machinery and one can rot without the other.",
    },
    {
        "id": "config-js-off-the-whitelist",
        "gate": "suite",
        "file": ".github/workflows/deploy.yml",
        "find": "for f in support.js config.js; do",
        "repl": "for f in support.js; do",
        "expect": "caught",
        "why": "#59 exactly: config.js published but unnamed, and the page then renders "
               "a turning machine with NO LINKS and says so only in the console. This "
               "was the registry's one `survives` entry (GitHub #89) — test.js asserted "
               "config.js was named in the deploy whitelist with `/\\bconfig\\.js\\b/` "
               "over the WHOLE workflow, and config.js is named there seven times, so "
               "the guard stayed green while the file stopped being published. The "
               "assertion now reads the aws s3 commands rather than the prose, the gap "
               "is closed, and the mutant is kept as the proof of it (CHANGELOG #104).",
    },
    {
        "id": "anchor-declared-twice",
        "gate": "suite",
        "file": "index.html",
        "find": "  driveCap() { return Math.abs(this.rateAt(SPEED_CEIL)); }",
        "repl": "  driveCap() { return Math.abs(this.rateAt(SPEED_CEIL)); }\n"
                "  driveCap() { return 8; }",
        "expect": "caught",
        "why": "THE SUITE'S OWN READING MECHANISM, mutated (GitHub #137). test.js "
               "extracts 66 blocks out of index.html by literal anchor, and until this "
               "was hardened it took the first indexOf with no ambiguity check — the "
               "#101 fault in the sibling of the function CL#112 fixed. A second "
               "`driveCap() {` LATER in the class body is the shape that matters: "
               "JavaScript lets the later definition win, so the page runs `return 8` "
               "while the suite measures the real line above it and reports 119 passed. "
               "Verified: with the pre-#137 extractor this mutant scores 119/0 and exits "
               "0. It now refuses by name instead, which is the only outcome that is not "
               "a passing test measuring the wrong code.",
    },
    {
        "id": "anchor-only-in-a-comment",
        "gate": "suite",
        "file": "index.html",
        "find": "const ORIGIN_MOUNT = 'edge';",
        "repl": "/* retired: const ORIGIN_MOUNT = 'edge'; */",
        "expect": "caught",
        "why": "GitHub #101 restaged verbatim, in the extractor it was never fixed in: a "
               "declaration commented out rather than deleted. index.html is roughly two "
               "thirds comment, and the anchors used to match raw text, so prose "
               "satisfied them — CLAUDE.md records the same trap for `<style>`, five "
               "occurrences of which only one is a tag. Here the page loses ORIGIN_MOUNT "
               "entirely and every fixture in the suite is built at whatever the COMMENT "
               "says, which is the same word, so nothing looks wrong. Verified: with the "
               "pre-#137 extractor this mutant scores 119/0 and exits 0. It now says "
               "the anchor is in the file but only inside a comment.",
    },
    {
        "id": "anchor-reindented",
        "gate": "suite",
        "file": "index.html",
        "find": "\n  applyRotation() {\n",
        "repl": "\napplyRotation() {\n",
        "expect": "tolerated",
        "why": "THE NEGATIVE CONTROL for the two above, and the reason `tolerated` "
               "exists (GitHub #137). Twenty-one of the 66 anchors used to carry two "
               "spaces of indentation, so this — a whitespace-only edit that changes no "
               "logic and no pixel — made the old suite fail with 'block not found', "
               "which is a gate objecting to `git diff -w` noise. Verified in both "
               "directions: with the pre-#137 extractor this mutant is RED, and it must "
               "now stay GREEN. An anchor states which lines it wants, never how far in "
               "they are indented; if this one ever goes red again, indentation has been "
               "baked back into an anchor.",
    },
    {
        "id": "plate-anchor-by-orientation",
        "gate": "suite",
        "file": "index.html",
        "find": "      if (away > 0) anchor = -1;",
        "repl": "      if (Math.abs(r.ux) > Math.abs(r.uy)) anchor = -1;",
        "expect": "caught",
        "why": "THE #67 MIRROR IMAGE, at the datum plate (GitHub #131 / #138). CL#160 "
               "chooses which END of the mark the plate is stamped at by a screen-space "
               "dot product against the measured wordmark; this replaces that with the "
               "handedness it is often mistaken for — 'the far end in landscape, the near "
               "end in portrait' — which produces exactly the same seat on the shipped "
               "composition and is a legal mirror image everywhere else. It passes every "
               "measurement taken along the run, which is why the suite's assertion is in "
               "screen x/y and why moving the wordmark to the other corner is the case "
               "that catches it. Before GitHub #138 no plate test supplied a brand box at "
               "all, so this mutant scored 119/0 and exited 0.",
    },
    {
        "id": "ssh-key-off-the-whitelist",
        "gate": "suite",
        "file": ".github/workflows/deploy.yml",
        "find": 'aws s3 cp ssh_public_key "$BUCKET/ssh_public_key" \\',
        "repl": 'aws s3 cp keybase.html "$BUCKET/ssh_public_key" \\',
        "expect": "caught",
        "why": "The whitelist has TWO shapes — a `for f in …` loop and individual "
               "`aws s3 cp` lines — and an assertion that understood only the loop "
               "would be the same hole with a smaller window. This is the second shape, "
               "and the wrong-source copy is how it plausibly breaks: the key still gets "
               "an object, so the deploy succeeds. ssh_public_key is still SPELT three "
               "times in the file afterwards — the destination key, the echo and the "
               "live-site check — so a text search still finds it and only reading the "
               "commands notices it has stopped being published.",
    },
    {
        "id": "sleep-latched",
        "gate": "motion",
        "file": "index.html",
        "find": "const asleep = document.hidden || this._offscreen === true;",
        "repl": "const asleep = true;",
        "expect": "caught",
        "why": "#7, restaged. The sleep gate latching true froze the entire page, and a "
               "frozen train PHOTOGRAPHS PERFECTLY — that is the whole reason a motion "
               "gate exists. The loop still runs here, so nothing throws and nothing "
               "looks wrong in a still; only two samples 700ms apart can tell.",
    },
    {
        "id": "hub-icon-misnamed",
        "gate": "motion",
        "file": "config.js",
        "find": "{ slug: 'reddit',",
        "repl": "{ slug: 'redit',",
        "expect": "caught",
        "why": "loadIcons() fetches assets/icons/<slug>.svg and its .catch swallows the "
               "failure, so a badge that cannot find its icon renders EMPTY and silent. "
               "This is the file:// failure and the wrong-content-type failure from the "
               "same direction. It exercises the other half of verify_motion — the badge "
               "and console channel rather than the transforms — which is why it is a "
               "second mutant on a gate that already has one.",
    },
    {
        "id": "pill-line-height",
        "gate": "type",
        "file": "index.html",
        "find": "pillType.replace('13px', '13px/1.4')",
        "repl": "pillType.replace('13px', '13px/1')",
        "expect": "caught",
        "why": "#51 put back, byte for byte: a line box the same height as the font size, "
               "inside a span whose overflow:hidden is not optional. The descenders are "
               "not overflowing, they are sliced off. It was found by eye and could have "
               "come back the same way, and the bucket still carried 13px/1 the day the "
               "gate was written.",
    },
    {
        "id": "ghost-stroke-opacity",
        "gate": "pixels",
        "file": "index.html",
        "find": "strokeOpacity: 0.65, strokeLinejoin: 'round'",
        "repl": "strokeOpacity: 0.45, strokeLinejoin: 'round'",
        "expect": "caught",
        "why": "The change no numeric gate can see: the geometry is identical, the train "
               "turns, every badge is centred, the type fits. #48's own proof that the "
               "pixel gate can fail was this substitution run by hand once — a max "
               "channel delta of 4, invisible to the eye. Automated here so it stays "
               "proved rather than remembered.",
    },
    {
        "id": "stripper-ate-a-line",
        "gate": "pixels",
        "file": "index.html",
        "find": "        stroke: L.col, strokeWidth: (eng.fT * ENGRAVE_STROKE).toFixed(3), strokeOpacity: L.op,\n",
        "repl": "",
        "expect": "caught",
        "why": "THE FAILURE MODE THE DELIVERY STRIPPER CAN HAVE, stood up as a mutant. "
               "tools/strip_comments.py now runs over the deploy's own checkout, so the "
               "published page is not the reviewed one, and the thing it could do wrong "
               "is eat live code on its way past a comment — a regex read as division, a "
               "template literal cut short, a `//` inside a URL. The stripper's own "
               "verification catches every version of that which stops PARSING, and this "
               "is the version that does not: one line of props deleted out of the middle "
               "of an object literal is valid JavaScript, meshes identically, turns, fits "
               "every viewport and passes the whole of tools/test.js. It is also #36's "
               "hairline, so what it costs is legibility of the engraving on every wheel "
               "at once. The pixel gate is the only thing in the tree that can see it, "
               "which is exactly why the deploy runs it against HEAD after stripping.",
    },
    {
        "id": "link-share-collapsed",
        "gate": "layout",
        "file": "index.html",
        "find": "const LINK_SHARE = 0.78;",
        "repl": "const LINK_SHARE = 0.20;",
        "expect": "caught",
        "why": "The train huddles in the middle of the screen instead of reaching both "
               "ends of the long axis. That is #46's floor and #87's short escape runs, "
               "and it is the failure the device sweep exists for: every wheel still "
               "meshes, still turns, still draws — the composition is simply wrong, at "
               "every viewport at once.",
    },
]


def free_port():
    """Never a fixed port (#42): two harnesses on one port make the loser report
    a page fault that is really a harness fault."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def serve(directory):
    """Serve the mutated tree. One server for the whole run — http.server reads
    from disk per request, so the tree changing underneath it is picked up."""
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
         "--directory", directory],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}/"
    for _ in range(80):
        try:
            urllib.request.urlopen(base + "index.html", timeout=1).read(1)
            return proc, base
        except Exception:
            time.sleep(0.1)
    proc.kill()
    raise SystemExit("FATAL: could not serve " + directory)


def apply_mutation(tree, m):
    """Exactly one occurrence, or stop the whole run. A mutation that no longer
    applies is not a small problem: it means the registry has been testing
    nothing, and a silent no-op here would report a clean sweep."""
    path = os.path.join(tree, m["file"])
    src = open(path, encoding="utf-8").read()
    n = src.count(m["find"])
    if n != 1:
        return n
    open(path, "w", encoding="utf-8").write(src.replace(m["find"], m["repl"]))
    return 1


def restore(tree, m):
    subprocess.run(["git", "-C", tree, "checkout", "--", m["file"]], check=True)
    dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    return dirty


# The gates' own vocabulary for a red verdict. The last few lines of output are
# not always where the evidence is -- verify_motion's "0 advanced in 700ms" sits
# above eight badge lines -- and a mutation gate whose log says only that the
# exit code was 1 is asking to be taken on trust, which is the habit this whole
# file exists to break.
SIGNAL = re.compile(r"advanced in|overrun|px differ|passed,|console errors|"
                    r"\bFAIL\b|\b0/\d+ passed", re.I)


def run_gate(tree, gate, base, blind, tail=6):
    """Returns (exit code, the lines worth printing, seconds)."""
    g = GATES[gate]
    if blind:
        # A gate that has gone blind: it runs, it prints, it exits 0 whatever
        # the tree looks like. Every harness this repo has caught being broken
        # behaved exactly like this.
        argv = [sys.executable, "-c", "print('gate: OK')"]
    else:
        argv = list(g["argv"]) + ([base] if g["server"] else [])
    t0 = time.time()
    r = subprocess.run(argv, cwd=tree, capture_output=True, text=True)
    secs = time.time() - t0
    out = (r.stdout + r.stderr).strip().splitlines()
    last = out[-tail:]
    signal = [l for l in out[:-tail] if SIGNAL.search(l)][-4:]
    return r.returncode, signal + last, secs


def main():
    ap = argparse.ArgumentParser(
        description="mutate the page, prove the named gate goes red, restore, prove it goes green")
    ap.add_argument("--ref", default="HEAD",
                    help="git ref to mutate a throwaway worktree of (default HEAD). "
                         "Uncommitted work is NOT tested — see the module docstring.")
    ap.add_argument("--gate", action="append", default=[], choices=sorted(GATES),
                    help="only mutants targeting this gate, repeatable")
    ap.add_argument("--only", action="append", default=[],
                    help="only this mutant id, repeatable")
    ap.add_argument("--list", action="store_true", help="print the registry and stop")
    ap.add_argument("--blind", action="store_true",
                    help="replace every gate with one that always exits 0 — a gate that "
                         "has gone blind. This runner MUST then exit non-zero; it is how "
                         "the mutation gate proves itself able to fail.")
    ap.add_argument("--keep", action="store_true", help="leave the worktree in place")
    a = ap.parse_args()

    chosen = [m for m in MUTANTS
              if (not a.gate or m["gate"] in a.gate)
              and (not a.only or m["id"] in a.only)]
    if a.only:
        unknown = set(a.only) - {m["id"] for m in MUTANTS}
        if unknown:
            print("FATAL: no such mutant: " + ", ".join(sorted(unknown)))
            return 2
    if not chosen:
        print("FATAL: no mutants selected")
        return 2

    if a.list:
        for gate in [g for g in GATES if any(m["gate"] == g for m in chosen)]:
            print(f"\n{gate:<8} {GATES[gate]['what']}")
            for m in chosen:
                if m["gate"] == gate:
                    mark = {"caught": "must be caught",
                            "survives": "KNOWN GAP — must survive",
                            "tolerated": "LEGITIMATE EDIT — must stay green"}[m["expect"]]
                    print(f"  {m['id']:<28} {m['file']:<28} {mark}")
                    print(f"    {m['why']}")
        return 0

    dirty = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    sha = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", a.ref],
                         capture_output=True, text=True).stdout.strip()
    print(f"mutating a throwaway worktree of {a.ref} ({sha})")
    if dirty:
        print(f"NOTE: {len(dirty.splitlines())} uncommitted change(s) in this tree are "
              f"NOT under test — this gate measures {a.ref}, not your working copy.")
    if a.blind:
        print("BLIND MODE: every gate replaced with one that always exits 0.")
        print("            A working runner reports every mutant SURVIVED and exits 1.")

    work = tempfile.mkdtemp(prefix="wozi-mutate-")
    tree = os.path.join(work, "t")
    r = subprocess.run(["git", "-C", ROOT, "worktree", "add", "--detach", tree, a.ref],
                       capture_output=True, text=True)
    if r.returncode:
        print("FATAL: could not check out " + a.ref + "\n" + r.stderr.strip())
        shutil.rmtree(work, ignore_errors=True)
        return 2

    srv = base = None
    results, controls = [], {}
    stale = None
    t_all = time.time()
    try:
        if not a.blind and any(GATES[m["gate"]]["server"] for m in chosen):
            srv, base = serve(tree)

        for gate in [g for g in GATES if any(m["gate"] == g for m in chosen)]:
            mine = [m for m in chosen if m["gate"] == gate]
            print(f"\n=== {gate} — {GATES[gate]['what']}")
            for m in mine:
                n = apply_mutation(tree, m)
                if n != 1:
                    stale = (m, n)
                    break
                rc, tail, secs = run_gate(tree, gate, base, a.blind)
                left = restore(tree, m)
                want_red = m["expect"] == "caught"
                good = (rc != 0) if want_red else (rc == 0)
                if want_red:
                    verdict = "CAUGHT" if rc else "SURVIVED"
                elif m["expect"] == "tolerated":
                    verdict = "tolerated — still green" if rc == 0 else \
                              "REJECTED A LEGITIMATE EDIT"
                else:
                    verdict = "survived — known gap" if rc == 0 else "GAP CLOSED"
                print(f"  {'ok  ' if good else 'FAIL'} {m['id']:<28} "
                      f"exit {rc}  {verdict}  ({secs:.0f}s)")
                for line in tail:
                    print("         | " + line[:110])
                if left:
                    print(f"  FAIL {m['id']:<28} tree not clean after restore: {left}")
                    good = False
                results.append((m, rc, good))
            if stale:
                break

            # The control runs AFTER the mutants, on the restored tree: red for
            # a stated reason, then green again. Two attempts, because the page
            # is dealt at random and a gate that reads the composition can go
            # red on a machine it happened to get (#88) — a flake here would
            # void a whole gate's verdict, so it gets one retry and says so.
            for attempt in (1, 2):
                rc, tail, secs = run_gate(tree, gate, base, a.blind)
                if rc == 0:
                    break
                print(f"  control run {attempt} came back red (exit {rc}) — retrying"
                      if attempt == 1 else "")
            controls[gate] = rc
            print(f"  {'ok  ' if rc == 0 else 'FAIL'} {'(control, restored tree)':<28} "
                  f"exit {rc}  {'green' if rc == 0 else 'RED ON A CLEAN TREE — verdict void'}"
                  f"  ({secs:.0f}s)")
            if rc:
                for line in tail:
                    print("         | " + line[:110])
    finally:
        if srv:
            srv.kill()
        if not a.keep:
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", tree],
                           capture_output=True)
            shutil.rmtree(work, ignore_errors=True)
            subprocess.run(["git", "-C", ROOT, "worktree", "prune"], capture_output=True)
        else:
            print("\nworktree kept at " + tree)

    if stale:
        m, n = stale
        print(f"\nFATAL: mutant {m['id']} no longer applies — found {n} occurrences of")
        print(f"       {m['find']!r}")
        print(f"       in {m['file']}, wanted exactly 1. The page moved and this mutant")
        print("       has been testing nothing. Fix the registry before trusting a sweep.")
        return 2

    caught = [r for r in results if r[0]["expect"] == "caught"]
    gaps = [r for r in results if r[0]["expect"] == "survives"]
    tol = [r for r in results if r[0]["expect"] == "tolerated"]
    bad = [r for r in results if not r[2]] + \
          [(None, c, False) for c in controls.values() if c]
    print(f"\n{sum(1 for r in caught if r[2])}/{len(caught)} mutants caught, "
          + (f"{sum(1 for r in tol if r[2])}/{len(tol)} legitimate edit(s) tolerated, " if tol else "")
          + f"{len(gaps)} known gap(s) still open, "
          f"{sum(1 for c in controls.values() if c == 0)}/{len(controls)} controls green "
          f"— {time.time() - t_all:.0f}s")
    for m, rc, good in gaps:
        if good:
            print(f"  KNOWN GAP  {m['id']}: {m.get('issue', 'not caught by ' + m['gate'])}")
    if bad:
        print("\nRESULT: FAIL — a gate that cannot fail is not a gate.")
        return 1
    print("\nRESULT: PASS — every gate went red for its own mutant and green again after.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
