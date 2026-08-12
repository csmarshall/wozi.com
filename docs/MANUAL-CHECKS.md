# Manual checks — the things only a real phone answers

Everything in `tools/` runs headless Chrome over CDP, plus one windowless
WKWebView (`webkit_band.js`). None of them has browser chrome, a window manager,
a battery, or a finger. The checks below are the ones that follow from that, each
with the reason no harness here can take it over — because a check nobody can
justify as manual gets automated badly, and a check nobody wrote down gets
skipped.

**The page's only mobile oracle is one human.** That is why this file exists. It
is not a gate and nothing runs it; it is the list to work through on a real
device after a change to the fit, the safe-area offsets, the frame budget or the
fixed controls, and when a phone reports something odd.

**The test for whether something belongs here is "can no harness in this repo
answer it".** If a harness can, it belongs as a gate instead. Two pages are
covered: the landing page (checks 1–8) and `/fidget/` (checks 9–13), which is a
separate published page with its own physics loop and is *more* device-dependent
than the landing page, because a finger is its only real input.

`CLAUDE.md` summarises this file as "six things no harness here can answer" and
names the original six (checks 1–6). The list has grown past that count; the
count in `CLAUDE.md` is the stale half, not this list.

---

## Reproducing what a phone saw

**`?seed=<n>` ships, and recording it is the single most useful thing a phone
report can carry.** It has been live since CL#109 (`index.html`, `DEAL_SEED`,
directly under the `?seed=8231` comment block at the top of the page script). A
seed replaces `Math.random` before the first draw, so the tooth counts, centre
families and variants, bearing angles, planetary clocking, colours and which
wheel wears which service all come out the same — a machine that can be drawn
again on a desk. Verified on this tree with `tools/deal_dump.py`: under
`?seed=8231` two settled loads came out with identical per-wheel tooth counts,
radii and centres, while three unseeded loads produced a different machine each
time.

Four things to know about it, all confirmed in headless Chrome against this tree:

- **It fixes the DEAL, not the FIT.** Placement is measured off the viewport, so
  reproducing a machine takes the same seed *and* the same window size. Say what
  the window was.
- **Check it took.** The page logs `wozi: dealt from ?seed=… — the same seed at
  the same window size draws the same machine`, and `window.__WOZI_SEED` reads
  back the number (`null` when the deal came from the browser).
- **A malformed or out-of-range seed deals at random and says so** —
  `wozi: ignoring ?seed=abc — expected a whole number 0…2147483647; dealing at
  random`. Silent degradation is the failure this parameter was most likely to
  have, so it was made loud instead.
- **The page does not report the seed of an UNSEEDED load**, which is the half of
  this idea that was deliberately not built (CL#109: self-seeding every load
  would replace the unseeded deal's source of randomness, and no pixel gate can
  tell that apart from a regression). So a machine that went wrong once, unseeded,
  is gone. Record device, iOS version, orientation, light or dark, window size and
  a photograph, *then* hunt for a seed that reproduces it.

**No gate may use `?seed`**, and that is not incidental to this file: the
harnesses inject their own LCG through `Page.addScriptToEvaluateOnNewDocument`
precisely so a fault in the page's own deal cannot be invisible to both. This
parameter's consumer is a person writing a bug report.

**`/fidget/` needs no seed and has none.** It contains no `Math.random` at all
and reads no URL parameters, so a report from it is reproducible from the state
instead: which grounding (rings or suns — the `ground` button's caption says
which one it will switch *to*), which set is on screen, orientation, and theme.

## `?hud` — the page reporting on itself

The one test hook that ships, and the only way to read tick rate, dropped ticks,
rAF/s, the wheel census, the gear's size in CSS *and* device px, and **which of
the fit terms is binding** (`tick/s`, `drop`, `wheels`, `gear px`, `binds`,
`view`), on a device no harness can drive. Off by default and
unreachable by accident: the gate is `/[?&]hud(=|&|$)/`, so `?hudson=1` does not
trip it (both verified on this tree — `?hud` drew the panel, `?hudson=1` did
not). There is no button and no key binding. It reports the loop without joining
it: integer arithmetic inside `step()`, all drawing on a 500ms timer outside it,
and it displays its own cost so that claim can be checked rather than believed.

Use it for checks 1 and 4 especially — it is the only instrument that can say
whether a phone is actually running at the tick rate the page thinks it is.

The HUD reads correctly on a solo page as well as the combined stage. It did not
until CL#183: `hudSample()`'s `scope` row still said `WHO`, which had been split
into `SPINE`/`SELECTED`, so `?hud` threw a `ReferenceError` every `HUD_MS` on any
`?who=<slug>` page — and the combined stage short-circuits the same expression,
which is why it survived. Worth knowing only because a phone report is usually a
solo page, so the instrument was broken in the situation it exists for.

## And anything pointer-shaped needs a hand on it regardless

`tools/README.md` records it: synthesized CDP pointer events never trigger native
link drag-and-drop, so a harness can pass an interaction that is broken under a
real mouse — or a real thumb.

---

# The landing page

## 1. Toolbar collapse mid-scroll

**Do.** Load the page in iOS Safari. Drag or flick the page so Safari collapses
its toolbar to the mini bar, then let it come back. Watch the train through the
whole transition, not just at the two ends. `?hud`'s `view` row is the readout
that says what the page thinks the viewport is.

**Correct.** The train re-fits as the viewport grows and shrinks: still edge to
edge along the long axis, still centred, no dead band at either end and nothing
clipped. `viewBox()` is the one home for that measurement and reads
`window.visualViewport` in preference to `innerHeight` (`index.html`), and
`componentDidMount` subscribes to the `visualViewport` resize event, which is
what iOS fires here instead of `resize`.

**Failure.** The train stays sized for the viewport it had before — dead space at
one end and clipping at the other, which is exactly the shape of the bug that put
`min-height:100svh` on `main` in the first place. A train that snaps rather than
re-fitting smoothly is a lesser failure worth noting, not a blocker.

**Why no harness.** `tools/devices.py` models browser chrome as a **constant
subtracted from the device height before navigating** — the two per-row numbers
in `DEVICES`, read off real Safari screenshots (88/100 on an SE, 96/117 on a 13,
14 and 15 Pro Max). A constant cannot collapse. Metrics are set once per row and
never touched again during the load, so every row is one static viewport, and even
re-overriding them mid-load would model the two endpoints as a step change rather
than the transition, which is where the fit either keeps up or does not.

---

## 2. Rotation with the keyboard up

**Do.** The page has **no text input of its own** — no `<input type="text">`, no
`<textarea>`, no `contenteditable`; the only form controls anywhere are the
pop-out panel's two range sliders and its style-layer checkboxes, and none of
those raises a keyboard — so the keyboard only ever arrives from Safari's own
chrome. Raise it that way: the URL bar, or the page menu's Find on Page. With the keyboard up and the visual viewport
short, rotate the device. Dismiss the keyboard and rotate back.

**Correct.** The train ends up along the long side of the screen in whichever
orientation you land in, correctly sized for the viewport that is actually
visible, and the fixed controls — the corner row and the wordmark — stay in
their corners. On a combined stage the bridge should be across the long axis in
portrait — that is the axis-relative bearing doing its job, and rank 0 should be
leftmost there.

**Failure.** The train sized for the keyboard-shortened viewport and left that
way after the keyboard goes; the axis rotation not landing, so the train runs
across the short side; the stack mirrored, with the spine rightmost in portrait;
controls stranded away from their corners.

**Why no harness.** This is two viewport changes racing — a visual-viewport
resize and an orientation change — and `devices.py` issues each of its emulation
overrides on its own, sequentially, against a page that is then reloaded. Nothing
in `tools/` ever changes orientation on a live page, and nothing there has a
keyboard at all. The two endpoints are covered by the portrait and landscape
rows; the race between them is not.

---

## 3. Home-indicator and Dynamic Island overlap

**Do.** On a notch or Dynamic Island phone, in both orientations: look at the
wordmark in the bottom-left corner and the corner row in the top-right — three
permanent buttons at 1×, a fourth departure indicator alongside them at any other
speed (GitHub #108, CL#114) — and **tap each with a thumb**. Then swipe up from
the bottom edge.

**Correct.** The wordmark sits clear above the home-indicator pill; every
button in the corner row, three or four of them, sits clear below the Island
and inside the rounded corners; each takes a thumb tap first time — including
the departure indicator, off 1×, which should reset the machine to 1× on
contact. The gears themselves are supposed to run under all of it —
`viewport-fit=cover` is deliberate (`index.html`'s viewport meta) and a machine
that stops short of the physical edge is the failure, not the one that bleeds
past it.

**Failure.** The wordmark under or clipped by the indicator pill; a button under
the Island; a button that is visibly clear but does not take the tap, because the
system's own edge gestures claim the strip before the page sees it.

**Why no harness.** The layout half is covered — `devices.py`'s second pass sets
`--safe-t/r/b/l` itself and measures every fixed control against the resulting
safe rectangle (`SAFE_DEVICES`, `SAFE_MEASURE`). But it supplies the numbers; see
check 6. And the tap is a different question from the geometry: whether the system
swallows a touch near an edge gesture is not a property of any bounding box, and
per `tools/README.md` a synthesized pointer event proves nothing about a real one.

---

## 4. Low Power Mode and rAF throttling

**Do.** Turn on Low Power Mode, load the page cold with `?hud`, and watch the
train for about thirty seconds — through the spin-up, at rest pace, and then drag
it hard and let the flywheel settle. Read the HUD's `tick/s`, `raf/s` and `drop`
rows rather than judging by eye alone. Compare against the same phone with Low
Power Mode off. (On a solo page the HUD currently throws — see the caveat above —
so do this on the combined stage.)

**Correct.** The tick rate sits at the shipped rate with dropped ticks at or near
zero; the train reads as smooth; the spin-up reaches rest pace rather than
crawling toward it; a drag throws it and the coast brings it back to rest pace in
finite time.

**Failure.** Visible judder, a dropped-tick count that climbs, a rest pace
obviously slower than the same phone off Low Power, or a spin-up that never
arrives.

**Why no harness, and the specific thing to look for.** The loop caps itself with
`budget = 1000 / this.tickRate() - 1.5` and skips any callback arriving sooner —
31.83ms at the shipped 30fps. iOS is understood to throttle
`requestAnimationFrame` to roughly 30Hz under Low Power Mode; that is external
knowledge, not something measured here. On paper a 33.3ms stream clears the
31.83ms budget on every callback and the train still runs at 30fps, but the
margin is 1.5ms, so **any jitter that brings an interval under the budget drops
that tick** and the projected worst case is the rate falling toward 15fps.
Hopefully the margin holds on a real phone; nobody has looked.

Nothing in `tools/` can look either. `verify_motion.py` samples the DOM twice
~700ms apart and reports how many transforms *advanced* — a binary, which a train
at 15fps passes exactly as well as one at 30. And `pixel_regress.py` cannot ask
the question at all: it queues rAF instead of running it and pins
`performance.now` to a virtual clock so `__pump(n)` advances exactly n frames of
exactly 1/60s. The one harness that controls the clock is the one that replaced
it. **Partly automatable and worth knowing:** CDP can throttle rAF, which GitHub
#164 notes while arguing the same point for `/fidget/` (check 11). If that ever
lands, this check shrinks to the part an eye judges.

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
corner is the one to watch: the wordmark is pinned there (`left:var(--offleft);
bottom:var(--offbot)`) and iOS Safari's bottom bar puts a control in the same
corner.

**Why no harness.** No harness in `tools/` renders any browser chrome. `devices.py`
removes the pixels the chrome occupies and paints nothing in them (`h -= pchrome`
/ `lchrome` before navigating), so a control that could overlap does not exist to
overlap. Reader availability is a heuristic inside Safari, and there is no CDP
call that asks about it.

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
`SAFE_DEVICES` injects: iPhone 13/14 `47/0/34/0` portrait and `0/47/21/47`
landscape; iPhone 15 Pro Max `59/0/34/0` and `0/59/21/59`. Those are Apple's
published figures, which is not the same as observed ones.

**Failure.** Any divergence — including all four reading `0px`, which would mean
the `@supports (top:env(safe-area-inset-top))` guard is not matching and the
tokens are sitting on their `0px` defaults. On a divergence the thing to correct
is `SAFE_DEVICES`, because it is the assumption everything else in that pass is
measured against.

**Why no harness.** `devices.py` states it outright: Chrome device emulation
"implements `env()` and resolves every inset to 0 on every emulated device,
because the insets come from the real window manager, not from the device metrics
override. So there is nothing to observe and no way to make Chrome produce one"
— and, of the half that is WebKit's, "no harness on this machine can check it".
The one non-Chrome harness here, `webkit_band.js`, builds a WKWebView that
**opens no window** (`tools/README.md`); a windowless web view has no window
manager to take insets from either. `/fidget/` uses the same `env()` values
directly on its chrome overlay, so check 13 is this one's other half.

---

## 7. The speed slider and the departure indicator, under a real finger

**Do.** Open the pop-out menu and drag the Speed slider — the panel's first
child — slowly, past the boundary where the thumb turns `--accent` and the
readout starts saying "strobing". Then close the menu, note the corner shows
nothing, drag the slider off 1×, close the menu again, and tap the departure
indicator that has appeared in the corner. Do the same with the Wear slider
beside it (GitHub #112), whose marks are deliberately subtle enough to need
close inspection. Repeat on a phone narrow enough that the panel is genuinely
cramped, and once on a solo host (`?who=<slug>`), where the slider is the first
thing in the panel regardless.

**Correct.** The thumb is easy to pick up and drop on a stop with a thumb, not
just a mouse; every stop the drag passes over updates the readout and (past the
boundary) the "strobing" note live, matching what the train visibly does;
releasing on a stop is where the choice sticks (reload and confirm it persisted).
The corner control appears the instant the slider leaves 1× and disappears the
instant it returns; tapping it resets the machine to 1× and the slider (reopen
the menu to check) reflects that. None of this requires the keyboard fallback
that headless Chrome exercises instead of a touch.

**Failure.** A drag that skips stops or lands off-ladder. A corner control that
lags a frame behind the slider, or that does not reset cleanly. The strobing
colour reading differently under real sunlight or an OLED panel than it does in
a screenshot.

**Two boxes, and say which one you mean** (GitHub #134). The visible disc is
`--thumb`, **16px**, chosen from a 24/20/16/12 sweep for legibility; what a
finger actually acquires is the `<input>` itself, a **129×44** box with the same
44px target every corner button uses, and a press anywhere in it jumps the thumb
to that stop. `a11y_audit.py` reports the input's box, never the disc's. So the
manual question is not "is the target big enough" — it is whether a 16px visual
cue on a 44px target is precise enough under a fingertip, which is a judgement no
bounding box contains.

**Why no harness.** Every harness in `tools/` drives this page over CDP, which
can set a range input's `value` and fire synthetic `input`/`change` events, but
per `tools/README.md` a synthesized pointer event proves nothing about a real
one — dragging a 16px disc between two neighbouring stops on the derived 1-2-5
ladder is exactly the class of small, continuous, pressure-sensitive gesture no
injected event reproduces. `a11y_audit.py` and `devices.py` both confirm the
control is *reachable* (focusable, correctly sized, clear of the safe area) and
*labelled* (the accessible name carries the strobing note); `pixel_regress
--panel` (CL#172) confirms it *draws*; none of them can confirm it is *usable*
with a thumb.

---

## 8. The cold load, seen by an eye (CL#174)

**Do.** On a real phone, on a real network, load the page cold — cache cleared,
not a reload — in both themes, and watch the first second. Do it on the combined
stage and on a solo page.

**Correct.** The train appears at its final size. CL#174 removed the render that
drew the whole composition at the boot `--gsfit` of 0.86 against a real ~1.4, so
the scale sequence is now `[1.39, 1.39, 1.39, 1.39]` where it was
`[0.86, 1.39, 1.39, 1.39, 1.39]` — there should be no visible jump from small to
full size. (Those figures are the desk measurement; a phone solves its own scale,
and 0.86 was the one boot value that was wrong at every viewport.)

**Failure.** Any visible resize, reflow or jump after the first paint. Note that
the webfont is a separate arrival: the page clears its `textWidth` memo on
`document.fonts.ready` (#98), so rim lettering settling a moment after the wheels
is a different event from the fit, and worth reporting as such.

**Why no harness.** The scale *sequence* is instrumented and verified —
`render_cost.py` counts renders and CL#174 logged every `--gsfit` — but no gate
here photographs the moment. `pixel_regress.py` pumps 90 virtual frames before
shooting, so it measures the settled state by construction, and every other
harness either measures cost or measures the DOM. What a visitor perceives during
a cold load, on a phone, with the font coming off a third party's network, is only
observable by eye.

**One thing not to chase.** CL#174's `?who=charles` shot at 390×844 moved **1px,
max channel delta 1**, reproducibly and in both themes, with a byte-identical
DOM. It was attributed: the promoted layer is now rasterised once at the final
scale instead of at 0.86 and again at 1.39, so it is the better raster and the
visible trace of the deleted render. It is a desktop-Chrome rasterisation
artefact and there is nothing for an eye on a phone to find in it — recorded here
so nobody goes looking.

---

# `/fidget/`

A separate published page (CL#156 onward) with its own physics loop, its own
palette tokens and no dependency on `support.js` or `config.js`. Only
`pixel_regress.py` is ever pointed at it — `devices.py` and `a11y_audit.py` read
the root page's constants or default to its URL — and its resting pose has no
finger down, so a still says nothing about how it responds. It is driven by a
finger, which makes almost everything interesting about it manual.

## 9. The grounding swipe against iOS's own edge gestures

**Do.** In portrait, swap the grounding by swiping vertically **off the gear** —
the disc is the grab target and everything outside it is the swipe's. The
threshold is `SWIPE_FRACTION` (0.12) of the shorter window edge with a
`SWIPE_BIAS` of 1.5 (it must be 1.5× more vertical than horizontal), and it
commits on move, not release. Try it from the band above the gear and the band
below it, near each edge, and both directions. Then confirm the same swap through
the `ground` button, `g`, and Shift+Up/Down.

**Correct.** A deliberate short vertical drag off the gear swaps rings↔suns, once
per gesture however far the drag goes on, and the readout and `aria-label` follow.
A swipe that begins **on** the gear spins the train instead and must not swap. A
swipe on the shaft stub must do neither.

**Failure.** A swipe near the top edge opening Notification/Control Centre, or one
near the bottom edge triggering the home swipe or app switcher, instead of
reaching the page — the bands off the gear in portrait are exactly those zones.
Also: the bottom band is partly occupied by the chrome overlay, whose button row
and readout carry `pointer-events:auto`, so a drag starting on the readout text
never reaches the `<svg>` at all. If the gesture is unreachable in practice on a
phone, that is the finding, and the button and keys are what keep the feature
reachable meanwhile.

**Why no harness.** Whether iOS's own edge gestures win is arbitration between
the system and the page, which no CDP-synthesized pointer sequence participates
in. The threshold arithmetic itself is already measured over CDP pointer events —
`fidget/README.md`'s *Measured* table records 108px at 1440×900, no swap at 88px
vertical, at 400px horizontal, on a diagonal or on a tap, and one swap per 700px
drag — so what is left here is only the part the OS decides.

---

## 10. Rubber-band, pinch and the browser's own pan

**Do.** With a finger: drag the gear fast and let go near the edges of the screen;
try a two-finger pinch on the drawing; try a hard flick upward as if scrolling;
double-tap it.

**Correct.** Nothing scrolls, rubber-bands, zooms or double-tap-zooms — the
gesture always belongs to the gear. `body` carries `overscroll-behavior:none` and
`touch-action:none`, the `<svg>` repeats `touch-action:none` plus
`user-select:none`, and the pointer path takes capture on pointerdown.

**Failure.** The page bouncing at an edge, a pinch zooming the drawing, or a
gesture that starts as a spin and is stolen mid-drag by the browser's pan.

**Why no harness.** Rubber-band scrolling, pinch-zoom and double-tap-zoom are
UIKit/WebKit behaviours: headless Chrome has none of them, and the one WebKit
harness here opens no window. `fidget/README.md` records "verified in portrait at
390×760", which is CDP pointer events against Chrome — it establishes that the
page's own gesture logic holds, not that iOS declines to interrupt it.

---

## 11. The grip spring in Low Power Mode (GitHub #164)

**Do.** With Low Power Mode **on**, grip the **light** port — the sun, the input
port, on set 1 — and twist it, hold it still, and let go. Then do the same with
Low Power Mode off and compare. Repeat at the heavy port (walk the shaft stub to
set 2's carrier) as a control, where the same fault is not expected.

**Correct.** The gear follows the finger and settles on it: one small overshoot
and done, no growing oscillation, no runaway. The heavy port should feel
distinctly heavier — that difference *is* the 230× reflected inertia and is the
whole point of the page.

**Failure.** The light port oscillating with **growing** amplitude, or running
away to the speed clamp, while a finger holds it still. That is the divergence,
not a feel complaint.

**Why no harness, and why this is a known hazard rather than a suspicion.** The
grip spring is integrated explicitly, so its stability depends on `ω_n·dt`. At
the shipped `HAND_FREQ` and 60fps the input port's `ω_n·dt` is **1.0** — inside
stability, but far enough in that the tick and not the model sets the shape
(measured first overshoot 90% against the continuous ζ=0.28's 40%, converging on
40.3% as `dt` shrinks). Past about **1.3** — below roughly **50fps** — it
diverges into a limit cycle bounded only by `MAX_SPEED` and the losses; at the
0.05s `dt` clamp a 1-radian step excursions to 8 radians. **Low Power Mode is
30fps.** The heavy port is nowhere near it (`ω_n·dt` = 0.066). Pre-existing and
unchanged by #158; every candidate fix changes how the light port feels, which is
why it is a decision (#164) and not a patch. `pixel_regress --path fidget/` reads
0px regardless, because the resting pose has no finger down and the spring term is
only reached while a grip exists. Note #164's own point: **CDP can throttle rAF**,
so part of this may become a gate — until it does, a phone in Low Power Mode is
the only place the question is asked.

---

## 12. Toolbar collapse on `/fidget/`

**Do.** The same gesture as check 1, on `/fidget/`: flick so Safari collapses its
toolbar, then let it back. Both orientations. Watch the gear and the chrome strip.

**Correct.** The gear stays centred and filling 0.700 of the shorter edge, the
shaft stub still runs out into the letterbox band along the long axis, and the
chrome strip stays pinned to the bottom safe area.

**Failure.** The gear sized or centred for the previous viewport — off-centre, or
the caption or stub label clipped — and left that way.

**Why no harness, and the reason to expect something.** `layout()` is wired to
`window`'s `resize` event **only**; there is no `visualViewport` listener
anywhere in `fidget/index.html`. That is precisely the gap check 1 documents for
the landing page, where `viewBox()` reading `visualViewport` is the fix. Whether
iOS Safari fires a plain `resize` for a toolbar collapse — it fires
`visualViewport` resize on the landing page, which is why that listener exists —
is the open question, and it can only be answered on a device with a collapsing
toolbar. **Projected, not verified: this may be a real fault.** If the gear does
lag, the fix is a `visualViewport` listener beside the `resize` one, and that is
an `index.html`-shaped change in `fidget/`, not a docs one.

---

## 13. `/fidget/`'s hit targets and its bottom safe area

**Do.** On a notch or Dynamic Island phone, both orientations: tap the shaft stub
with a thumb (it is the dashed tie running off the edge of the window, a real
`role="button"`), then each of the four chrome buttons — `flick sun`,
`flick carrier`, `ground`, `theme` — and check the readout row is fully legible.
Swipe up from the bottom edge.

**Correct.** Every one takes a thumb tap first time. The readout's last line sits
clear above the home-indicator pill, and the button row clear of the rounded
corners in landscape. `theme` cycles and the whole page follows.

**Failure.** A tap on the stub that misses or that spins the gear instead; a
chrome button that needs a second attempt; the readout clipped by, or sitting
under, the home indicator; a button under the Island in landscape.

**Why no harness.** Two halves, and both are absent here rather than impossible
in principle — worth saying plainly. The insets are the same problem as check 6:
`/fidget/` reads `env(safe-area-inset-left)` and `env(safe-area-inset-bottom)`
directly on the chrome strip, Chrome resolves both to 0 on every emulated device,
and `devices.py`'s inset-injecting pass is pointed at the root page and reads the
root page's constants — so nothing measures this page's safe-area behaviour at
all. The hit boxes are measurable in principle (`a11y_audit.py` takes a URL and
could be pointed here), and the numbers are already known to be small: the stub's
hit width is `SHAFT_TARGET` × R = 0.2R, which is 63px on a 1440×900 desk and
about **27px on a 390-wide phone** — deliberately a share of the drawing rather
than a pixel figure, and **below the 44px the landing page holds its own controls
to**. The chrome buttons are roughly 31px tall (11px text, 9px padding, 1px
border), over the WCAG 24px floor and under 44px too. So the box sizes are a gate
somebody could write; whether 27px is acquirable with a thumb, at the far edge of
a phone, is the part only a thumb answers.
