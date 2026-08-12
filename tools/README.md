# tools/ — verification harnesses

Session harnesses rescued from the working scratchpad before a reboot
(2026-07-30). None of this is published: the deploy whitelists paths, and
tools/ and docs/ are not on the list.

**Path caveat:** each script hardcodes an OUT/PROFILE base under a
Claude-session scratchpad in /tmp that no longer exists after reboot. Before
running one, either `mkdir -p` that path or edit the constant near the top to
any writable directory. Everything else is self-contained (headless Chrome over
CDP; `pip` needs websockets, and Pillow/numpy for the image-analysis ones).

- verify_motion.py <url>   THE gate: 18/18 transforms advance, badges centred,
                           no console errors. Counts only deg-suffixed
                           rotations (static rotate(120) planet seats are
                           placement, not animation). Pins the webfont, and
                           NOT for a type measurement — "no console errors" is
                           an assertion about the network while the font is on
                           it, and an unreachable fonts.googleapis.com turned
                           this gate red on an unchanged page (GitHub #145).
- dom_invariants.py <url>  four structural assertions about the RENDERED DOM,
                           with no image at all: every wheel meshes with
                           something, every blank draws the tooth count its own
                           radius implies, every linked wheel's engraving is
                           actually painted, and every ink is a tone of its own
                           wheel's colour. Seeds the deal. Takes --query
                           '?who=charles' for the single-chain path; --census
                           prints every measurement rather than the verdict.
- fontpin.py               NOT a harness — the shared mechanism the six gates
                           import (pixel_regress, pill_clip, devices,
                           dom_invariants, verify_motion, a11y_audit). Takes
                           Manrope off the network:
                           prefetches the CSS and every face into the process
                           BEFORE Chrome starts, fulfils every font-host request
                           from memory over CDP `Fetch`, and VERIFIES with a width
                           probe after each render that the face really painted --
                           `document.fonts.status` and `.check()` both answer
                           "yes" with the stylesheet blocked, so neither can be
                           the detector. One state per run (`--fonts
                           auto|pinned|blocked`), degrading loudly rather than
                           failing on a Google Fonts outage; a page with no
                           webfont at all, like /fidget/, is reported as such and
                           not failed for it. Also carries the dispatching CDP
                           session every caller now uses -- a paused font request
                           arrives unsolicited and MUST be answered, and `pump()`
                           is what replaces `asyncio.sleep` so a wait answers
                           them instead of sleeping through them. GitHub #140;
                           the fault it removes cost a red deploy (CL#159).
                           **escape_mesh.py is deliberately NOT on that list**:
                           its exposure was measured at exactly zero (a full
                           --census run byte-identical with both font hosts
                           blackholed), so it is documented as immune rather
                           than pinned for symmetry.
- a11y_audit.py <url>      axe-core injected over CDP + the structural checks
                           axe cannot make (focus rules, reduced-motion, SVG
                           exposure, target sizes). Reports the tightest hit
                           boxes, not only "0 under 24x24", and now states which
                           theme and speed were actually IN FORCE per pass —
                           they never were: a `}}` that never collapsed made
                           every preference-setting snippet throw SyntaxError,
                           so both passes audited the same default theme at 1x
                           and every "PASS in both themes" in CHANGELOG.md is
                           one theme audited twice (GitHub #145).
- strip_comments.py        NOT a harness — the one thing in here that BUILDS
                           what ships. Cuts the commentary out of an HTML page
                           for delivery (603KB -> 189KB on index.html) and
                           leaves a /*L1234*/ backlink where each comment was,
                           pinned by the banner to the commit it came from. The
                           deploy runs it `--in-place` over its own checkout
                           before any gate, which is how everything else in this
                           directory ends up measuring the artifact instead of
                           the source. `--in-place` refuses on a file that
                           differs from HEAD; `--selftest` covers every trap.
- shots.py <url>           five-viewport geometry + screenshots (layout work).
- pin_test.py              pins a wheel at 8 rotations, samples the tooth ring
                           (the only band where the body paint is alone).
- zoom.py                  close-up of a mesh point between two wheels.
- mesh_audit.js /          numeric tooth-mesh measurement: penetration depth
  mesh_poly.js /             and minimum gap at all six adjacent pairs, for
  mesh_inv.js                straight and involute profiles.
- palettes.py              renders palette candidates side by side.
- webkit_band.js <url>     the only harness here that is NOT Chrome. Builds a
                           WKWebView — Safari's engine, and every iOS
                           browser's — and measures the rim engraving against
                           its band. Run with
                           `osascript -l JavaScript tools/webkit_band.js <url>`;
                           needs no Safari setting enabled and opens no window.
                           Exists because #19 was invisible to everything else
                           in this directory: Blink and Gecko centred the
                           handle, WebKit put it 19% of a band depth out.

**Check you are measuring your own tree.** Everything here that takes a `<url>`
measures whatever answers on that port, and the deploy's layout step serves on a
FIXED 8765 — fine on a clean runner, a trap on this machine. With another agent's
worktree already on 8765, `python3 -m http.server 8765` fails with EADDRINUSE and
every gate then passes against somebody else's `index.html` without a word. Serve
on a port of your own, and confirm the body is the tree you meant before believing
a PASS. `pixel_regress.py` picks a free port for this reason (#42).

Testing lesson recorded in git history worth repeating here: synthesized CDP
pointer events never trigger native link drag-and-drop, so a harness can pass
an interaction that is broken under a real mouse. Anything pointer-related
needs a human hand on it once.
