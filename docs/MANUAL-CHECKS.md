# Manual checks — the things only a real phone answers

Everything in `tools/` runs headless Chrome over CDP, plus one windowless
WKWebView (`webkit_band.js`). None of them has browser chrome, a window manager,
a battery, or a finger. The seven checks below are the ones that follow from
that, each with the reason no harness here can take it over — because a check
nobody can justify as manual gets automated badly, and a check nobody wrote
down gets skipped.

**The page's only mobile oracle is one human.** That is why this file exists. It
is not a gate and nothing runs it; it is the list to work through on a real
device after a change to the fit, the safe-area offsets, the frame budget or the
fixed controls, and when a phone reports something odd.

**A repro from a phone is only useful if it can be reproduced.** Every wheel is
dealt at random — 11 bare `Math.random()` sites in `index.html` pick tooth
counts, families, bearings and the background machinery — so "it looked wrong on
my phone" currently describes a machine that will never be drawn again. The
in-page `?seed=` hook that would fix this is **GitHub #48 part 1 and does not
exist yet**: `index.html` parses no `seed` parameter at all, and both harnesses
that need determinism inject their own `Math.random` over CDP before page script
runs (`devices.py:375-382`, `pixel_regress.py:81-85`), which is deliberate — no
test hook reaches the shipped page — and is unavailable to a phone. Until it
lands, record what you can: device, iOS version, orientation, light or dark, and
a photograph. A photograph of the wrong machine is still evidence that the wrong
machine can be drawn.

**And anything pointer-shaped needs a hand on it regardless.** `tools/README.md`
records it: synthesized CDP pointer events never trigger native link
drag-and-drop, so a harness can pass an interaction that is broken under a real
mouse — or a real thumb.

---

## 1. Toolbar collapse mid-scroll

**Do.** Load the page in iOS Safari. Drag or flick the page so Safari collapses
its toolbar to the mini bar, then let it come back. Watch the train through the
whole transition, not just at the two ends.

**Correct.** The train re-fits as the viewport grows and shrinks: still edge to
edge along the long axis, still centred, no dead band at either end and nothing
clipped. `fitStage()` measures `window.visualViewport` rather than
`innerHeight` (`index.html:2714-2716`) and is wired to the `visualViewport`
resize event, which is what iOS fires here instead of `resize`
(`index.html:2953-2955`).

**Failure.** The train stays sized for the viewport it had before — dead space at
one end and clipping at the other, which is exactly the shape of the bug that put
`min-height:100svh` on `main` in the first place (`index.html:2702-2713`). A
train that snaps rather than re-fitting smoothly is a lesser failure worth
noting, not a blocker.

**Why no harness.** `tools/devices.py` models browser chrome as a **constant
subtracted from the device height before navigating** — the two per-row numbers
in `DEVICES` (`devices.py:94-104`), read off real Safari screenshots
(`devices.py:86-93`). A constant cannot collapse. Metrics are set once per row
and never touched again during the load, so every row is one static viewport, and
even re-overriding them mid-load would model the two endpoints as a step change
rather than the transition, which is where the fit either keeps up or does not.

---

## 2. Rotation with the keyboard up

**Do.** The page has **no text input of its own** — zero `<input>`, `<textarea>`
or `contenteditable` in `index.html` — so the keyboard only ever arrives from
Safari's own chrome. Raise it that way: the URL bar, or the page menu's Find on
Page. With the keyboard up and the visual viewport short, rotate the device.
Dismiss the keyboard and rotate back.

**Correct.** The train ends up along the long side of the screen in whichever
orientation you land in, correctly sized for the viewport that is actually
visible, and the fixed controls — the corner row and the wordmark — stay in
their corners. On a combined stage the bridge should be across the long axis in
portrait — that is the axis-relative bearing doing its job.

**Failure.** The train sized for the keyboard-shortened viewport and left that
way after the keyboard goes; the axis rotation not landing, so the train runs
across the short side; controls stranded away from their corners.

**Why no harness.** This is two viewport changes racing — a visual-viewport
resize and an orientation change — and `devices.py` issues each of its emulation
overrides on its own, sequentially, against a page that is then reloaded
(`devices.py:389-397`). Nothing in `tools/` ever changes orientation on a live
page, and nothing there has a keyboard at all. The two endpoints are covered by
the portrait and landscape rows; the race between them is not.

---

## 3. Home-indicator and Dynamic Island overlap

**Do.** On a notch or Dynamic Island phone, in both orientations: look at the
wordmark in the bottom-left corner and the corner row in the top-right — three
buttons at 1x, a fourth departure indicator alongside them at any other speed
(GitHub #108, CL#114) — and **tap each with a thumb**. Then swipe up from the
bottom edge.

**Correct.** The wordmark sits clear above the home-indicator pill; every
button in the corner row, three or four of them, sits clear below the Island
and inside the rounded corners; each takes a thumb tap first time — including
the departure indicator, off 1x, which should reset the machine to 1x on
contact. The gears themselves are supposed to run under all of it —
`viewport-fit=cover` is deliberate (`index.html:87-92`) and a machine that
stops short of the physical edge is the failure, not the one that bleeds past
it.

**Failure.** The wordmark under or clipped by the indicator pill; a button under
the Island; a button that is visibly clear but does not take the tap, because the
system's own edge gestures claim the strip before the page sees it.

**Why no harness.** The layout half is covered — `devices.py`'s second pass sets
`--safe-t/r/b/l` itself and measures every fixed control against the resulting
safe rectangle (`devices.py:141-167`, `SAFE_MEASURE` at `172-205`). But it
supplies the numbers; see check 6. And the tap is a different question from the
geometry: whether the system swallows a touch near an edge gesture is not a
property of any bounding box, and per `tools/README.md` a synthesized pointer
event proves nothing about a real one.

---

## 4. Low Power Mode and rAF throttling

**Do.** Turn on Low Power Mode, load the page cold, and watch the train for about
thirty seconds — through the spin-up, at rest pace, and then drag it hard and let
the flywheel settle. Compare against the same phone with Low Power Mode off.

**Correct.** The train turns at a steady pace and reads as smooth; the spin-up
reaches rest pace rather than crawling toward it; a drag throws it and friction
brings it back.

**Failure.** Visible judder, or a rest pace obviously slower than the same phone
off Low Power, or a spin-up that never arrives.

**Why no harness, and the specific thing to look for.** The loop caps itself with
`budget = 1000 / (frameRate ?? 30) - 1.5` and skips any callback arriving sooner
(`index.html:2517`) — 31.83ms at the shipped 30fps. iOS is understood to throttle
`requestAnimationFrame` to roughly 30Hz under Low Power Mode; that is external
knowledge, not something measured here. On paper a 33.3ms stream clears the
31.83ms budget on every callback and the train still runs at 30fps, but the
margin is 1.5ms, so **any jitter that brings an interval under the budget drops
that tick** and the projected worst case is the rate falling toward 15fps.
Hopefully the margin holds on a real phone; nobody has looked.

Nothing in `tools/` can look either. `verify_motion.py` samples the DOM twice
~700ms apart and reports how many transforms *advanced* — a binary
(`verify_motion.py:5, 188`), which a train at 15fps passes exactly as well as one
at 30. And `pixel_regress.py` cannot ask the question at all: it queues rAF
instead of running it and pins `performance.now` to a virtual clock so `__pump(n)`
advances exactly n frames of exactly 1/60s (`pixel_regress.py:19-27`). The one
harness that controls the clock is the one that replaced it.

---

## 5. Reader mode and Safari's own controls

**Do.** Load the page in iOS Safari and look at what Safari puts on screen around
it: the page-menu control, and whether a Reader glyph appears at all. Open the
page menu. If Reader is offered, enter it and come back.

**Correct.** Safari's controls stay in Safari's chrome, clear of the wordmark and
the corner row. Whether Safari offers Reader on a page with one `<h1>` and no
body copy is Safari's heuristic and not something this repo decides — if it is
offered, entering it gives a blank or near-blank screen, which is expected rather
than a bug, and backing out must return the running train.

**Failure.** A Safari control landing on a tappable page control. The bottom-left
corner is the one to watch: the wordmark is pinned there
(`index.html:199`, `left:var(--offleft); bottom:var(--offbot)`) and iOS Safari's
bottom bar puts a control in the same corner.

**Why no harness.** No harness in `tools/` renders any browser chrome. `devices.py`
removes the pixels the chrome occupies and paints nothing in them
(`devices.py:86-104`, `h -= pchrome`/`lchrome` at `devices.py:388`), so a control
that could overlap does not exist to overlap. Reader availability is a heuristic
inside Safari, and there is no CDP call that asks about it.

---

## 6. Real `env(safe-area-inset-*)` values

Distinct from check 3, and the reason check 3 is only half-covered. Check 3 asks
whether the layout keeps the controls clear *given* insets. This asks whether iOS
hands the page the insets the harness assumed.

**Do.** Attach Safari Web Inspector to the phone over USB (Settings → Safari →
Advanced → Web Inspector) and read the four resolved values in each orientation:

    const cs = getComputedStyle(document.documentElement);
    ['--safe-t','--safe-r','--safe-b','--safe-l'].map(p => [p, cs.getPropertyValue(p)]);

**Correct.** They are non-zero where they should be, and they match what
`SAFE_DEVICES` injects (`devices.py:162-167`): iPhone 13/14 `47/0/34/0` portrait
and `0/47/21/47` landscape; iPhone 15 Pro Max `59/0/34/0` and `0/59/21/59`. Those
are Apple's published figures, which is not the same as observed ones.

**Failure.** Any divergence — including all four reading `0px`, which would mean
the `@supports (top:env(safe-area-inset-top))` guard (`index.html:107-109`) is not
matching and the tokens are sitting on their `0px` defaults. On a divergence the
thing to correct is `SAFE_DEVICES`, because it is the assumption everything else
in that pass is measured against.

**Why no harness.** `devices.py` states it outright: Chrome device emulation
"implements `env()` and resolves every inset to 0 on every emulated device,
because the insets come from the real window manager, not from the device metrics
override. So there is nothing to observe and no way to make Chrome produce one"
(`devices.py:149-152`) — and, of the half that is WebKit's, "no harness on this
machine can check it" (`devices.py:158`). The one non-Chrome harness here,
`webkit_band.js`, builds a WKWebView that **opens no window** (`tools/README.md:32-36`);
a windowless web view has no window manager to take insets from either.

---

## 7. The speed slider and the departure indicator, under a real finger

**Do.** Open the pop-out menu and drag the slider at the top of it, slowly,
past the boundary where the thumb turns `--accent` and the readout starts
saying "strobing" (GitHub #69's A/B sheets found this exact boundary is where
a track-based warning had failed — see below). Then close the menu, note the
corner shows nothing, drag the slider off 1x, close the menu again, and tap
the departure indicator that has appeared in the corner. Repeat on a phone
narrow enough that the menu panel and the slider inside it are genuinely
cramped, and once on a solo host (`?who=<slug>`), where the person picker is
absent and the slider is the first and only thing above the gear-family list.

**Correct.** The thumb is easy to pick up and drop on a stop with a thumb, not
just a mouse; every stop the drag passes over updates the readout and (past
the boundary) the "strobing" note live, matching what the train visibly does;
releasing on a stop is where the choice sticks (reload and confirm it
persisted). The corner control appears the instant the slider leaves 1x and
disappears the instant it returns; tapping the corner control resets the
machine to 1x and the slider (reopen the menu to check) reflects that. None of
this requires the keyboard fallback that headless Chrome exercises instead of
a touch.

**Failure.** A thumb that is hard to acquire with a fingertip (the rendered
disc is 24px; `tools/a11y_audit.py` reports the input's own hit box
separately — see check 6's sibling number in that tool's output — and the two
are not the same rectangle, so a phone is the only way to know whether the
gap between them matters in practice). A drag that skips stops or lands
off-ladder. A corner control that lags a frame behind the slider, or that
does not reset cleanly. The strobing colour reading differently under real
sunlight or an OLED panel than it does in a screenshot.

**Why no harness.** Every harness in `tools/` drives this page over CDP, which
can set a range input's `value` and fire synthetic `input`/`change` events,
but per `tools/README.md` a synthesized pointer event proves nothing about a
real one — dragging a 24px thumb between two of eight stops is exactly the
class of small, continuous, pressure-sensitive gesture no injected event
reproduces. `tools/a11y_audit.py` and `tools/devices.py` both confirm the
control is *reachable* (focusable, correctly sized, clear of the safe area)
and *labelled* (the accessible name carries the strobing note); neither can
confirm it is *usable* with a thumb, which is the whole reason this entry
exists rather than being folded into check 3.
