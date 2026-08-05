# Changelog

Every entry is one tracked change. Newest first. Numbers are stable — reference
them in issues and commits (`fix: #14 stamp hidden under specular arc`).

## Unreleased

### Changed

- **CL#120 — the datum showed through the bridge idlers, because a translucent
  group of one cannot occlude anything.** (GitHub #86.)

  A bridge idler was dimmed by putting `opacity` on the wrapping `<div>` that
  also carries its rotation. That makes the whole wheel translucent — so the
  datum line, painted behind it, read straight through the teeth and the hub.
  Dimming and occluding are different jobs and one property cannot do both.

  The fix separates them. Opacity moves off the div and onto a `<g>` **inside**
  the wheel's own SVG, and an opaque backing plate is painted before that group:
  a `<use>` of the wheel's **own tooth path**, filled and stroked in `var(--bg)`,
  so the plate is exactly the tooth silhouette and no second geometry exists to
  drift from it. Because compositing is linear, `bg + alpha*(colour - bg)` is
  what a pre-blended fill would have produced — the same pixels, without
  recolouring anything, so the ink census still reads the original hues.

  **Verified by arithmetic rather than by eye**, which is worth recording because
  a screenshot cannot tell a fixed leak from a lucky crop. Reading the idler's
  own rendered fill and computing the composite predicts **(175.4, 178.6,
  177.6)** in light theme; the after-shot at the datum crossing reads a flat
  **(175, 179, 177)** — under 1/255 per channel, with no datum ink in it. The
  same pixels before read (145-152, 152-158, 152-158), deviating 20-30/255,
  which is the additive blend that was the bug.

  **`?who=charles` is 0 px** across both themes and against two separate base
  commits: the solo path has no datum and no bridge, and is untouched.

  **The escape-run ghosts are deliberately not covered, and that is correct** —
  a point worth writing down because it looks like an omission. `wheelOpacity()`
  returns a value only for `role === 'idler'`, so escape-run outriggers take the
  null branch and get no plate. They do not need one: unlike idlers, they and the
  datum already live inside the **same** `ghosts` container under one group-level
  opacity, so the translucent-group-of-one problem never applied to them. An
  isolated escape ghost on the datum baseline diffs **0 px** before and after.
  The two classes are in different coordinate spaces and only one of them was
  ever broken.

  `EDGE` names the stroke width the plate and the real path share, so they cannot
  drift apart. It is not a new tuned number — it is the literal `1` that was
  already on the outline, given one home.

- **CL#113 — two assertion messages that named the pass instead of the fail, and
  a sweep for a third.** (GitHub #105.)

  `eq(bridges[0].idlers.length, 0, 'an unbridged chain claims idlers')` and
  `eq(train[bridges[0].head].parent, null, 'an unbridged chain is not a root')`
  each read, cold, as a flat statement about a healthy tree rather than as a
  report of what broke — a message an assertion function only ever prints on
  failure has to say what *is* true then, and "claims idlers" / "is not a root"
  are exactly as true of the passing case as of the failing one, so a reader
  meeting either for the first time on a red run has nothing in the sentence to
  tell them which. Both were rewritten to say the deviation: *"kept idlers on
  its bridge record, and it has no drive to hang them off"* and *"was given a
  parent, so it is being driven by the chain it opted out of"*.

  Both corrections had already landed, uncredited, inside CL#104's commit —
  found there while chasing the same family of fault (an assertion that cannot
  say what went wrong is one more step from an assertion that cannot fail at
  all, GitHub #89). This entry is the credit that commit didn't leave, plus the
  sweep the ticket actually asked for: every `ok(...)` and `eq(...)` message in
  `tools/test.js` — 282 call sites across 89 `test()` cases — read against the
  same question, which state does this sentence describe. None of the rest
  share the fault; the file's prevailing convention already names the
  deviation directly ("a plate that seats cleanly warns about it", "the bridge
  bearing is not measured from `_axisRot`") or states the requirement as a
  requirement ("a train must have exactly one root", "a two-row entry needs
  `[Zs,Zp1,Zp2,Zr,N]`"), and either reads the same on a red run as off one.

  Verified by forcing `bridges[0].idlers.length` to want `99` instead of `0`:
  the suite failed with *"an unbridged chain kept idlers on its bridge record,
  and it has no drive to hang them off (got 0, want 99)"*, then restored.
  `npm test`: **89 passed, 0 failed.**
- **CL#112 — `grabNumber()` no longer guesses between two declarations of the
  same constant.** (GitHub #101.)

  `tools/test.js` reads its geometry constants OUT OF `index.html` rather than
  keeping copies, which is the whole reason a broken page cannot pass the
  suite (see CLAUDE.md, "Verifying a change"). `grabNumber()` is the function
  that makes that true, and it had one live trap: `String.match` with a
  non-global regex returns the FIRST match in the file, with no check that a
  name is unique.

  `index.html` declares `CELL_MIN` twice — a retired honeycomb family's
  literal `CELL_MIN = 2.8`, and hexcore's live `CELL_MIN = px(3.9, 2.2, 6.0)`.
  Verified directly: the old `grabNumber('CELL_MIN')` returned **2.8**, the
  retired figure, and could not have returned the live one under any
  circumstances — `px(...)` is not a number literal, so it never matched the
  pattern at all. Nothing in `test.js`'s `consts` list currently asks for
  `CELL_MIN`, so this had not yet produced a false pass, but it was the exact
  shape of bug CLAUDE.md warns the whole suite's honesty rests on: silent and
  green.

  **Ambiguity is now fatal, and it is caught even where counting numeric
  matches alone would miss it.** Comments are stripped first (block comments,
  the idiom four other call sites in `test.js` already use), so a name merely
  discussed in prose can no longer stand in for a declaration. Then
  `grabNumber()` counts every ASSIGNMENT to the name — literal or not — and
  throws if there is more than one. Counting plain-number matches alone would
  not have caught `CELL_MIN`: only one of its two declarations is a literal,
  so that count was already 1. `tools/mesh_dirs.py`'s `_grab_number()`, the
  identical idiom in Python, got the same treatment.

  Swept every name either file currently extracts — the full `consts` list
  plus `TEETH_MEAN`, `LINK_SHARE`, `CROSS_BLEED`, `MAX_IDLERS`, `MIN_IDLERS`,
  `CLEARANCE`, `ENDS_APART`, `TARGET_GEAR_PX`, `MODULE`, `TOOTH_ADD` — and
  every one of them resolves to exactly one declaration; `CELL_MIN` is the
  only ambiguous name in the file, and nothing currently reads it, so no
  extracted value changed. Mutation-tested by reverting `grabNumber()` to the
  original first-match behaviour: the suite's new test fails, naming the
  regression (`grabNumber('CELL_MIN') silently returned the retired honeycomb
  literal (2.8)...`) rather than failing on an unrelated assertion.

  `index.html` itself is untouched — the retired `CELL_MIN` stays retired, on
  purpose, the same as `honeycomb`'s whole family. `grabNumber()` is what had
  to cope, not the page.
- **CL#111 — a three-wheel spine can now pay `ENDS_APART`.** (GitHub #104.)

  `ENDS_APART` (90, in solve units) is the extra push kept between the
  machine's two spine extremities so a run reads as a line rather than a
  closed ring. A spine of exactly three wheels asks for the whole of it in
  two mesh steps — the leaf's only host is one hop from the root — and on
  measured ~40-50% of deals no bearing within the leaf's own ±60° nudge could
  pay it, in either direction: not a search failure, but the root and the
  ENDS_APART owed to it not fitting inside that swing at all. `wozi: wheel 2
  ... found no clear bearing ...; planted anyway, and may clash` was the
  visible result. Four wheels and longer never hit this: the host the check
  compares against is by then several hops from the root, so the achievable
  separation dwarfs the flat push and it was never the binding constraint.

  **`ENDS_APART` itself is unchanged** — still the one flat figure, still 90,
  still in solve units, still named and used exactly where it was. What
  changed is `solve()`'s own arithmetic: the push it actually asks a wheel to
  clear is now `Math.min(ENDS_APART, endsApartCapFor(o))`, where the cap is
  the greatest distance from `o` any candidate the swing loop is *already
  about to try* can reach — computed by walking that same discrete candidate
  set once, not a second formula that could disagree with the search using
  it. A longer spine's cap sits far above `ENDS_APART` and never binds, so
  nothing here is a second measured constant standing in for the first: it is
  a ceiling derived from the wheels already dealt and the swing already
  budgeted, that happens to equal the old flat push whenever the chain is
  long enough to afford it outright.

  **Measured, not merely run once:** 1,000 real deals of a solo three-wheel
  spine dropped from 483 warnings (48.3%, matching the issue's own ~40% within
  sampling noise) before this change to 0 after, at both stage rotations. A
  1–8 wheel sweep after the fix warns 0/80 at every length, matching the
  issue's own report that only length three ever warned. `?who=charles` and
  the combined stage are both 0px against `HEAD` (`tools/pixel_regress.py`) —
  Charles's own chain is seven wheels, far past where the cap ever binds (a
  500-trial sample of the same cap put its floor at 444.7 against a flat
  push of 90), so nothing about its geometry moved.

  `tools/test.js`'s `DECLARED` fixture (#85) shrinks its spine from four
  wheels to three, which is what it should have been all along: it exists to
  prove a declared spine and stack still compose, and a four-wheel spine
  never exercised the one length this defect actually lived at. A dedicated
  test drives 400 solo three-wheel deals on its own and asserts zero
  no-clear-bearing warnings.
- **CL#115 — a kidney slot's arm is set by width, not by angle, so it keeps
  its shape as the wheel grows.** (GitHub #93.)

  `slots()` — the shared kidney-slot cutter behind the `spokes` and `pockets`
  centre families — sized the slot's width as a fraction of the annulus span
  (`rOut - rIn`), the way every other module-derived measurement on the page
  is, but sized the arm left between two slots as a fixed number of *degrees*.
  A fixed angle converts to a physical length through the wheel's mid radius,
  which tracks the wheel's circumference; the width tracks the much smaller
  span instead — two quantities that grow at different rates across the dealt
  tooth range, so the straight run went flat while the width nearly tripled
  and the kidney read as a round hole at the big end of the deal.

  The fix replaces the fixed angle with `aspect`, a designed straight-run/width
  ratio — a proportion, exactly like the existing `widthScale` — and derives
  the one arm length that delivers exactly that ratio out of the gap this arm
  count leaves at this wheel's own mid radius, converted to degrees by the
  same mid-radius division `capDeg` already used. Where a gap is too tight to
  afford it, the arm floors at zero rather than going negative, so the slot
  widens toward the whole gap instead of demanding an impossible shape.

  `npm test` gained an assertion that reads `slots()` and its two call sites
  back out of `index.html`, executes the real closure, and measures the
  achieved aspect ratio across the whole `TEETH_MIN..TEETH_MAX` range — not
  one sampled size, which is what the bug was about.
- **CL#116 — the epicyclic hub badge's dead knob, and the plateau it was
  hiding.** (GitHub #94.)

  Two faults, both in six lines of `renderVals()`'s badge sizing, and
  measurement rather than reading is what told them apart. `discF` forked on
  `epicyclic` (0.38 vs 0.72) on top of `capF`'s own shrink (0.55 vs 1.15) — a
  second attempt at the same job. `g.r` runs 45.5–66.5 solve units over every
  tooth count this page can deal (`TEETH_MIN`..`TEETH_MAX`, module-derived, not
  hand-picked), so `g.r * 0.38` was always 17.3–25.3: short of `disc`'s own
  30-floor **for every wheel the page has ever dealt, at every scale**, because
  that floor was applied in solve units, before `S` scaled the value in — no
  viewport could ever lift it clear. `disc` came out exactly 30 regardless of
  teeth, which is what "dead" means here: not merely untested, but
  unconditionally unreachable, confirmed by sweeping the full tooth range
  rather than by inspecting the arithmetic. The badge that actually rendered
  tracked `cap` alone, and plateaued the instant `cap` itself passed 30 — at 16
  teeth — because the pinned `disc * S` became the smaller, size-deciding term
  for every tooth count above it.

  **The fix is one constant, not two.** `capF` already shrinks the epicyclic
  badge — that is the comment sitting right above it — so `discF` no longer
  forks on `epicyclic`; it is `0.72` for every kind, matching the ordinary
  wheel's factor it was always meant to sit above. `cap`, smaller by `capF`
  alone, is now what actually governs the epicyclic badge across the whole
  tooth range, and the badge grows continuously from 32.5px to 48.1px over
  13–19 teeth (measured at the render scale #64's own table used) instead of
  flattening at 39.0px past 16. The ordinary-wheel path is untouched — its
  `discF` was already live, so before and after render pixel-identical there.

  **The floor is now stated once, in the unit it is legible in.** The same `30`
  literal appeared twice, four lines apart, in two different units — a
  solve-unit clamp on `disc` and a rendered-pixel clamp on `disc * S` — which is
  what let the first one go dead without anyone noticing the second was doing
  all the work. The solve-unit clamp (and its unreachable 60-ceiling twin) is
  gone; the one clamp that remains is the pixel-space floor, applied after `S`
  scales the badge down, which is the only place a legibility floor means
  anything.

  `npm test`'s existing legibility-floor test now exercises the fixed formula
  unchanged (it reads the three lines out of the page, not a copy), and a new
  test sweeps every dealable tooth count and fails if the epicyclic badge ever
  stops growing — mutation-tested against the original dead-floor code, where
  it fails naming the exact plateau (`16->17 teeth: 39.0px -> 39.0px`, etc.).
- **CL#118 — `engraving()`'s sweep cap is a clear-metal length, and its width
  is measured, not guessed.** (GitHub #98.)

  Two faults in one six-line closure. The cap on how far the handle or the
  stamp may sweep round the band was a fixed 168 degrees, so the clear metal
  it left between them — the thing that actually has to stay constant — held
  at exactly one radius and drifted everywhere else: #64 measured 6.46 to
  10.86 units, a 1.68x spread, across the shipped 13-19 tooth range. It is now
  solved the other way round: `ENGRAVE_GAP` (1.24 modules, chosen to land
  close to where 168 degrees did at the middle of the tooth range) states the
  clear metal, and the permitted angle is derived from it per wheel —
  "geometry derives in one direction" applied to the band's circumference
  instead of its depth. And the text width feeding that computation was a
  per-character guess (`per`/`track`) sitting a thousand lines under
  `textWidth()`, the memoised canvas measurement built for exactly this
  problem — one home for the fact, not two answers that could disagree.
  `emWidth()` now asks `textWidth()` at a large fixed reference size and scales
  the ratio down, so every candidate font size `fit()` tries for the same
  string is one memoised canvas call rather than several.

  **Replacing the guess uncovered a second, sharper bug on the way in.**
  `emWidth()`'s first measurement runs during the very first render, which is
  before the Google Fonts stylesheet has registered Manrope in
  `document.fonts` — measured then, `bold Manrope` silently falls back to the
  fallback stack and *underestimates* the real glyph run, and because
  `textWidth()` memoises forever, that wrong number stuck: the guide arc built
  from it was shorter than the text painted on it once the real face arrived,
  which is a worse failure than the guess it replaced. `componentDidMount` now
  clears the memo and forces one more render once `document.fonts.ready`
  settles. A second, smaller gap came from the tracking convention: Blink adds
  the 0.1em letter-spacing after every glyph, including the last, not once per
  gap between glyphs, so `emWidth()` now counts `str.length` tracking units,
  not `str.length - 1`. Both were found by comparing every engraved wheel's
  guide-path length against its own `getComputedTextLength()` on the live DOM,
  not by eyeballing a render.

  Verified with two mutation tests (a reintroduced fixed angle, a
  reintroduced per-character guess) that fail with a message naming the real
  regression, a new `npm test` assertion that the clear metal stays within
  1e-6 of `ENGRAVE_GAP * MODULE` across the full 13-19 tooth range at a label
  length long enough to engage the cap, and a contact sheet of the longest and
  shortest configured labels on the smallest and largest dealt wheels, both
  themes, before and after.
- **CL#119 — a ghost's addendum now has one home, `TOOTH_ADD`, instead of
  three.** (GitHub #100.)

  A ghost wheel's outer radius — pitch radius plus addendum — was computed
  three different ways: `MODULE * 0.95` where `fitEscapes()` places and
  collision-tests an escape-run ghost, `MODULE * (teeth/2 + 1.25)` where the
  ghost layer reserves its compositing box, and `MODULE * TOOTH_ADD` (1.00)
  everywhere a linked wheel is measured, including `WHEEL_SPAN`. None of the
  first two read `TOOTH_ADD`, so the constant that exists to be the addendum's
  one stated home was quietly disagreed with twice.

  The `0.95` had no defending comment and was 5% under the true addendum on a
  background wheel's own placement radius — measured, in module units, against
  `TOOTH_ADD`: 0.05 modules short, 0.35 solve units, well under a pixel at the
  page's usual scale. Small, but it meant a ghost's own creation site and every
  linked wheel disagreed about what an addendum is. Now reads `TOOTH_ADD`
  directly.

  The `1.25` was different: its comment already named it as addendum plus a
  real flat pad for the drawn wheel's stroke and baked-in shadow, measured at a
  10–17px shortfall if omitted. It was written as one number, `1.25`, rather
  than as `TOOTH_ADD` plus that pad — so it read as a competing addendum
  instead of an addendum with a margin, and would not have followed `TOOTH_ADD`
  if that constant ever moved. Decomposed into `TOOTH_ADD + GHOST_BOX_PAD`
  (`GHOST_BOX_PAD = 0.25`), with the pad now named and the total numerically
  unchanged — the reserved box is exactly as large as before, so nothing that
  read it can have started clipping.

  **Measured, not assumed.** A representative wheel's tip radius under the
  three old addenda, in solve units (`MODULE = 7`): 76.65 (`0.95`, ghost
  creation) vs 77.00 (`TOOTH_ADD`, every linked wheel) vs 78.75 (`1.25`, the
  ghost box) — a 2.1-unit spread top to bottom, teeth-count-independent since
  the addendum term doesn't carry `teeth`. At the page's documented "usual
  scale" of `S ~ 1.25` that is under 3px, which is why nothing has visibly
  clipped; the bug was never the size of the gap, it was that three call sites
  had no reason to agree on it.

  **Confirmed by seeded pixel diff** (`tools/pixel_regress.py --seed 8231`):
  the linked (coloured) wheels are pixel-identical before and after, on the
  combined stage and on `?who=charles` alone. Only the decorative escape-run
  ghosts move, because the corrected placement radius feeds a collision test
  inside a seeded random walk — shifting the radius by 0.05 modules can flip
  which candidate step a rejection-sampling loop accepts, forking the `rnd()`
  draw sequence for every ghost placed after it in that run. That is a real,
  visible ripple under a fixed seed and an invisible one in production: ghosts
  are re-dealt on every real page load regardless, seed or no seed.

  Added a test asserting *agreement* rather than any one value — the failure
  mode here was always disagreement between call sites, not a wrong constant —
  by running the real `fitEscapes()` and reading a ghost's placed radius back,
  and by checking the ghost-box formula is textually built from `TOOTH_ADD`
  rather than restating the addendum as its own number. Mutation-tested by
  reintroducing each of `0.95` and the bare `1.25`: both are caught, each with
  a message naming the call site and the value, not a bare number mismatch.

- **CL#110 — `?hud`, an animation HUD for how the browser is really rendering
  the gears.** (GitHub #92.)

  Every gate in this repo runs one engine, headless, at fixed pixel sizes, with
  no battery and no finger. So the page's behaviour on a real phone — the one
  place several of its bugs have actually lived — has never been readable by
  anything except a human describing what they saw. `?hud` makes the page report
  on itself.

  **Off by default and unreachable by accident.** The gate is
  `/[?&]hud(=|&|$)/`, so `?hudson=1` does not trip it, and there is no button and
  no key binding — the parameter is the whole interface. A visitor who does not
  type it sees a byte-identical page.

  What it reports, grouped by the question it answers: the scope being drawn;
  tick/s against nominal, rAF/s, writes/s, dropped ticks, tick ms at p50 and p95,
  and the sleep gate's own verdict; the speed multiplier with measured master
  rate, teeth per tick and percent of Nyquist, marked when strobing; the wheel
  census split linked/idler/ghost, `--gsfit` raw and quantised, **which of the
  four fit terms is binding**, gear size in CSS and device px, viewport; and the
  panel's own cost in ms and as a share of a frame.

  **It measures without perturbing what it measures**, which is the whole risk of
  a HUD like this. Inside the rAF loop it does integer arithmetic and one array
  write — no DOM, no allocation, no layout read. All rendering happens on a 500ms
  timer outside the loop. It reads the raw inline `--gsfit` string rather than
  calling `getComputedStyle`, which would force a style recalc, and it reads the
  `_solved` cache rather than calling `solve()`, which could pay for a whole
  re-solve on a timer. It reports its own cost so that claim is checkable rather
  than asserted.

  **It reports the sleep gate, it does not participate in it.** `_hudAsleep`
  mirrors the loop's own expression rather than re-deriving it — the one-expression
  rule from #7 is exactly the kind of thing a second opinion breaks.

  **One unsourced claim removed.** A comment stated ticks/s had been "measured at
  28.5–29.7 against a nominal 30". Nothing in the tree supported it, and measuring
  it properly contradicted it: **30.03 ticks/s**, median 33.3ms, p95 34.3ms, and
  **zero** ticks needing a third raw frame across ~1,700 samples — combined stage,
  one chain and a 223-wheel viewport, at 1× and 200×, including a run with every
  core deliberately oversubscribed. The comment now carries that figure and its
  limits, since a number in a comment is read as fact by whoever finds it next.

  Landing note: the branch cited changelog `#103` in six places, which is now a
  GitHub issue number and not this entry. Renumbered to CL#110. **CL#108 is
  deliberately skipped** — it is in history on the reverted plate-clearance commit
  and is reserved for that work re-landing.

- **CL#109 — `?seed=8231`, so that a machine drawn once can be drawn again.**
  (GitHub #48, part 1 of three; parts 2 and 3 shipped as #100 and #93.) Every
  wheel on this page is dealt. Twelve bare `Math.random()` calls pick the tooth
  counts, the centre families and their variants, the bearing angles, the
  planetary's clocking, the colours, and which wheel wears which service — so a
  machine exists for exactly as long as its tab does, and **"it looked wrong on
  my phone" describes something that will never be drawn again.** Both harnesses
  that need a fixed machine inject their own LCG over `Math.random` through
  `Page.addScriptToEvaluateOnNewDocument`, which is right for them and is
  unavailable to a human holding a phone. Naming the seed in the URL is the
  whole feature.

  **This is a deliberate exception to a rule this repo states in several places
  — determinism belongs to the harness, and no test hook ships — so it is argued
  in the file rather than left to be discovered.** A seed is not that hook. It
  changes no behaviour, bypasses no logic, exposes no internal and reaches
  nothing a visitor could not otherwise reach; it fixes ONE input that is
  otherwise unobservable, and its consumer is a person writing a bug report
  rather than a gate. The distinction that makes it safe is not the size of the
  code, it is who is allowed to use it.

  **No gate may ever use it, and the harnesses were deliberately left alone.**
  `tools/pixel_regress.py` and `tools/dom_invariants.py` both still inject their
  own generator even though this parameter would now do the job in one query
  string, because the moment a gate deals through the same mechanism the page
  deals through, a fault in that mechanism is invisible to both — the gate would
  agree with the page about a machine they had both got wrong. Two generators is
  the point. It is written at the install site and in `CLAUDE.md`, which are the
  two places somebody would be tempted.

  **It is installed above every other statement in `index.html`**, and that is
  required rather than tidy: the deal is not something anybody calls.
  `dealTeeth()` and `dealAngles()` are IIFEs that run at module load and the
  first of them draws long before anything renders, so a parameter read beside
  its consumer would be read too late. `?kind=` can afford to sit next to the
  family list it filters — only a function reads it. It follows that parser's
  shape (a regex over `location.search` inside a `try`) and not its position.

  **The seed reaches all twelve draw sites by replacing `Math.random`, not by
  threading a generator through twelve call sites.** Twelve edits is twelve
  chances to miss one, and the thirteenth `Math.random()` somebody adds next
  year would silently escape the seed. Replacing the global covers the deal by
  construction, and the count is now free to move without this feature rotting —
  the issue itself corrected "ten" to "eleven" once already, and it is twelve.

  **The proof is the repeat.** `?seed=8231` in three fresh documents, and again
  in a separate browser process with a separate profile and a separate server
  port: one fingerprint, `576ec7f6b36a6278`, over 26 wheels — rim stamp (which
  carries the tooth count), body fill, centre in screen pixels, and the element
  census of each centre design, identical field by field. `?seed=8232`, one
  apart, draws a different machine (24 wheels): the seed is passed through the
  murmur3 finalizer before it becomes LCG state, because an LCG's state is
  affine in its seed and `?seed=1` and `?seed=2` would otherwise part by
  1664525/2³¹ on their first draw — under a thousandth, which is the same tooth
  count, the same family and the same bearing. Three loads with **no** seed gave
  three different fingerprints, which is the other half of the same proof.

  **And the same statement in pixels**, which is the version that needs no
  fingerprint to be trusted: two independent `pixel_regress --shot` captures of
  `?seed=8231` at 1440×900 differ by **0 px**, and `?seed=8232` differs from
  them by **510,350 px**. (The page's own generator is installed at page-script
  time, so on a seeded URL it displaces the harness's injected one — which is
  fine for a photograph and is exactly why a gate must not pass this parameter.)

  **One static assertion, because no harness can see this break.** `npm test`
  now checks that the installer precedes every `Math.random()` call in the file
  — comments stripped first, since the installer's own comment counts the draw
  sites by name. Position is the feature's whole requirement, and a draw moved
  above the installer (or the installer moved below one) un-seeds the page while
  every other gate stays green: both harnesses inject their own generator ahead
  of all page script, so neither is capable of noticing. Proved able to fail in
  both directions — a draw planted at the top of the script reports the offset
  of the offender, and renaming the installer reports its absence. The suite is
  **89 passed, 0 failed** (was 88).

  **What it fixes and what it does not.** It fixes the *deal*; where the
  finished train is then placed is measured off the viewport, so a seed
  reproduces a machine at a given window size and says nothing across two —
  same seed **and** same window. The escape runs are outside it in the other
  direction: `fitEscapes()` resets its own `_seed` on entry, so that stream was
  never part of the random deal and was already the same on every load. The
  rotation phase is outside it too, and always was — the only thing that moved
  between two same-seed loads was each wheel's axis-aligned box, by up to 0.4px,
  which is the turning the pixel gate freezes with `__pump()` and not the deal.

  **A malformed seed deals at random, and says so.** This is module scope:
  anything thrown here takes the whole script with it and renders nothing at
  all, which is #53 exactly. `?seed=abc`, `?seed=-1`, `?seed=3.5`,
  `?seed=2147483648`, `?seed=` and `?seed=%zz` all draw a normal random machine
  and log one `console.warn` naming what was refused. The capture is everything
  up to the next `&` rather than a run of digits *because* of that message —
  matching digits only would make `?seed=abc` indistinguishable from no seed at
  all. The undecodable case is the one that nearly slipped through: `%zz` makes
  `decodeURIComponent` throw, and catching that with the outer `try` would have
  sent the single most obviously malformed input down the silent path. It is
  caught next to the decode instead and rejected by name. The accepted range is
  `0…0x7fffffff`, which is the generator's own state space rather than a bound
  anybody picked, and `?seed=0` is a seed like any other.

  **Absent the parameter the page does not touch `Math.random` at all**, and
  that is the load-bearing half. `tools/pixel_regress.py` against `main` is
  **0px at 1440×900 and 390×844, on `?who=charles` and on the combined stage** —
  the proof that this costs nothing when unused.

  **The more valuable half did not ship, and the reason is the rule itself.**
  Accepting a seed asks the reporter to reproduce a fault on a machine that is
  not the one that failed; what a bug report actually wants is the seed of the
  machine that *went wrong*. That needs the page to seed itself on **every**
  load, and self-seeding necessarily replaces the unseeded deal's source of
  randomness — after which the pixel gate, whose own LCG the page would now be
  consuming one value from and then ignoring, reports a different machine at
  every viewport and cannot tell that apart from a regression. The only way to
  have both is for the page to recognise when it is being tested, which is
  precisely the test hook none of this is allowed to be. Recording the drawn
  values into a `?deal=` blob would close it honestly — the unseeded stream
  stays native, so the pixel gate stays at 0px — at the cost of a URL nobody can
  read out over the phone. Filed as a follow-up rather than smuggled in here.

  **Discoverability, and what it is honestly worth.** The seed in effect is
  readable at `window.__WOZI_SEED` (`null` when the deal came from the browser),
  read-only data in the same shape as `__WOZI_GEOM`, and a seeded load says so
  once with `console.info`. Both exist for the failure mode this parameter is
  most likely to have — degrading silently with no way to tell whether the seed
  took — and neither is reachable from a phone, which is exactly why no UI
  affordance was added for it: on a seeded load the URL bar already shows the
  seed, and on an unseeded load nothing the page could offer would be the
  machine on screen. A control that hands over a *different* fixed machine is
  not the feature, and it would have cost an `a11y_audit` focusable and a DOM
  invariant to say so.

  Gates: **89 passed, 0 failed** (was 88), `verify_motion` PASS (37/37
  rotating, 8 badges at ≤0.01px, no strands, no console errors), `dom_invariants`
  PASS 4/4 — run with its own injected seed, which is the point,
  `pixel_regress` 0px against `main` at both viewports on both views, `devices`
  24/24 and 4/4.
- **CL#107 — a one-link chain's datum carried no scale, because one station is one
  tick and nothing to subdivide.** (GitHub #83.) Minor ticks subdivided the gap
  between a chain's own stations, and Harper's chain has exactly one station: the
  loop struck a single stroke at her only wheel and returned on its first pass.
  A line, a name and one mark is not a scale — it is a hairline that looks like
  one.

  **The scale is the spine's, which is a design call and not a derivation**
  (Charles, GitHub #90 item 5). Every self-referential candidate could give a
  chain marks; only a shared one gives two chains marks that mean the same
  distance, which is what a datum scale is *for*. A machine bed carries one
  scale, not one per part. **It costs something and the code says so**: a
  one-station chain's minor marks reference *another* chain's wheels, which is
  the one thing the rule above them — "the marks cannot drift out of step with
  the wheels they reference, because they ARE the wheels" — does not otherwise
  bend on. That exception is stated in `datumRuns()` rather than glossed.

  **What was derived is the figure itself, and its degenerate case falls out of
  the same arithmetic.** "The spine's station spacing" needed pinning to one
  number, and the obvious one — the mean gap, `span / (stations - 1)` — is
  undefined at exactly the configuration the ticket is about, so a chain that is
  its own spine would have needed a second rule beside the first. Instead the
  spine lends its **station pitch**: the axial length its station pattern
  occupies, over the number of stations occupying it. The extent is measured on
  the pitch circles, leading edge of the first station to trailing edge of the
  last, because that is the circle a mesh's centre distance is set on — so it is
  the projected span plus the two end radii.

  That reading is the spacing, not merely something like it. For stations that
  mesh in a row the span telescopes to `Sum(r_k + r_k+1)` and the extent to
  exactly `2 * Sum(r)`, so the pitch is twice their mean radius — the centre
  distance between neighbours, for wheels of one size. A real serpentine wanders
  off its own axis and the projection shortens it, which is correct: the marks
  are struck along the line, so the scale should measure what the line measures.

  **And at one station the span is zero, the two end radii are the same wheel's,
  and what is left is that wheel's pitch diameter, `MODULE * teeth`** — the first
  candidate on the ticket, arrived at as the *limit* of the third rather than
  chosen beside it. So the objection that a borrowed scale breaks when a chain
  has no spine but itself is answered by the derivation: no branch, no fallback
  constant, nothing to keep in step. The other two halves of that objection were
  never load-bearing — a datum is drawn **only** on a shared stage, so a solo
  host and a lone chain draw no mark at all to need a scale, and `bridge: false`
  changes what *drives* a chain, not what bed it stands on. Both are now run
  rather than argued.

  The one case with nothing in it stays empty: a chain the active config seats no
  service on has no length to measure and no major tick to measure against, so it
  lends `0` — meaning **absent**, and also what keeps the borrowed grid's loop
  finite. Only a chain with exactly *one* station borrows; two or more have a gap
  of their own, and zero has no anchor to phase a grid against.

  Drawn as **minor** marks only — a major tick means a wheel you can reach, and
  this chain has one — phased on that station and run out to the ends of the
  borrower's own assembly, `d0..d1`. The spine lends the spacing and nothing
  else; how far the scale reaches is the borrower's own dimension. The divisor is
  one named `SUBDIV`, read by both the self-subdividing path and the borrowed
  one, so a division here is the same distance as a division there.

  Measured on the shipped stage at 1440×900: Charles's own minor ticks fall
  32–42 px apart as his station gaps vary, and Harper's borrowed grid is a
  uniform **38 px** — inside his range, which is the comparability the whole
  choice was made for. **284 px move in total** (179 at 1440×900, 105 at
  390×844), all of them the new marks; `?who=charles` is untouched, since no
  datum is drawn on a solo stage at all.

  Two suite tests, on real solves: that a one-station chain — bridged *and*
  unbridged — is scribed at the spine's pitch while nothing else is, bounded
  against a ceiling the suite derives for itself rather than against a copy of
  the method's own arithmetic; and that a spine which is its own borrower lands
  on `MODULE * teeth`, with a one-link chain alone on stage drawing no datum at
  all.

  **And one guard had to be repaired to let this be written down at all.** The
  "no literal colours in the datum" assertion was `/#[0-9A-Fa-f]{3,6}|rgb\(/`
  over the whole of `datumLayer()` — and every three-digit decimal is three hex
  digits, so from entry #100 onward the rule forbade the one method it guards
  from *citing the entry that changed it*. A rule that a comment can break is not
  the rule anyone wrote. A literal colour reaches the drawing as a quoted string
  or through `rgb(`; a citation never does, so the pattern now requires the
  quote.

- **CL#106 — which chain is the spine and what order the rest stack in are two
  questions, and the bridges were running the wrong way in portrait.** (GitHub
  #85, GitHub #90 item 4, and a bug Charles found by looking at the page.)

  **The split.** One key did both jobs, and the two agreed only because the sort
  made them agree: sorting by link count named the longest chain the spine as a
  *side effect* of deciding where the others sat. Give Harper eight links and the
  whole composition rebuilds around her, with nothing in `config.js` to say that
  had ever been a choice — the same defect as the old `PEOPLE[0]` hostname
  fallback, a default that works by accident and says nothing about itself.

  Now two independent per-person keys: `spine: true` is **geometry** (it sets the
  scale, and it is the axis every other chain runs parallel to), `order: <n>` is
  **presentation**. `CHAIN_STACK` sorts, `SPINE` is declared, and
  `CHAIN_ORDER = [SPINE, ...stack minus spine]` — so `CHAIN_ORDER[0] === SPINE`
  holds **by construction**, which is what keeps `solve()`'s one-way growth
  invariant true rather than merely likely.

  `WHO` split with it, into `SPINE` (the axis) and `SELECTED` (which person the
  page is *about*, `null` on the combined stage). The analytics beacon had been
  reading the spine and calling it the selection.

  **The fallback sort, Charles's spec:** `order`, then link count descending,
  then **name descending**. Undeclared chains sort to `Infinity`, which is why the
  fallback needs no branch of its own. The name key is where PEOPLE order used to
  be — a tie that held only because `Array.prototype.sort` is stable, which reads
  as no rule at all in the file it governs. The sort is now **total**; nothing
  leans on stability any more, and `PEOPLE` order decides only the picker.

  Deliberately **not** locale-aware: `localeCompare` folds case and accents
  better and would also make the layout depend on the runtime's ICU data. A
  tie-break that comes out differently in two browsers is a drifting constant.

  On the shipped config this is a **zero-pixel change** — Charles has seven links
  to Harper's one, so link count decides before the name key is ever consulted,
  and both declare `order` explicitly anyway.

  **The bug underneath it, which is the part that moved the page.**
  `BRIDGE_BEARING` was made relative to `_axisRot` by CL#67, but its **sign was
  still hardcoded at `+90`** — "down" at rot 0 and **"left"** at rot 90. So in
  portrait the chains stacked leftward off the spine and the spine came out
  **rightmost**. Measured at 390×844 before: Charles x≈290, Harper x≈173.

  The handedness is now derived rather than picked: both candidate bearings are
  evaluated and the one pointing **away from the stage origin** wins, so rank 0 is
  topmost in landscape and leftmost in portrait at any `_axisRot`. After: Charles
  x≈69, Harper x≈321.

  **This is the third failure of the same kind and the second in this one
  constant**, which is why CLAUDE.md now carries a bridge-handedness invariant
  beside the bearing one. Making a value axis-relative is only half the job —
  a *sign* is as screen-absolute as a number of degrees is.

  **Why nothing caught it:** every existing test measured *along* the bridge
  direction, and both mirror images satisfy that. `alongBridge` is now
  `alongCross` and asserts in screen x/y, plus a test named for the requirement.
  Reverting the fix fails two.

  **Two real defects fixed in the inherited implementation**, both found by
  review rather than by the suite:

  - `STACK_AT` accepted `NaN` as a position. `NaN` compares false against
    everything including itself, so the comparator became **non-transitive** and
    the sort's output was undefined — not wrong, *undefined*. Now `isFinite`.
  - The `SPINE` warnings each re-derived their own replacement, so two bad
    declarations at once could print a chain that was not the one used. The
    answer is settled first and both messages read it.

  **Harness narrowed on purpose:** `buildTrain`'s `stack` override is gone. After
  the split every legal layout is expressible as declarations, so the override
  bought only *illegal* trains — a harness able to build what the page cannot is
  a harness that can go green on a page that would not run.

  Suite 79 → 86, every new assertion mutation-verified.

- **CL#105 — the street address is off the site, in all three places it was
  published.** (GitHub #84, and GitHub #90 item 3.)

  **First entry under the new citation style.** Changelog entry numbers and
  GitHub issue numbers had grown into almost exactly the same range — splitting
  GitHub #64 filed tickets at #93-#103 while this file already had entries 93-101
  — so a bare `#97` meant the derived palette *or* the sunburst window count
  depending on which file you were reading. From here new entries are cited
  `CL#NNN` in commit subjects and code comments; the ~100 existing bare `#N`
  references stay as they are, and the break in style is itself a signal about
  which era a reference comes from. GitHub refs keep the `(GitHub #NN)` form.

  The decision that drove the change: **old QR codes must keep working**, so the
  path cannot move. That strikes the unguessable-path and CloudFront-token
  options for as long as printed cards are in circulation, and leaves exactly one
  mitigation that *reduces* exposure rather than relocating it — don't publish the
  address.

  **It was in three places, not one.** The question was posed about the vCard;
  the vCard was the smallest of the three:

  | where | what it was |
  | --- | --- |
  | `cards/charles/contact.vcf` | the `ADR:` line |
  | `cards/index.html` | a visible block printing street, apt, city, state, country |
  | `cards/charles/index.html` | byte-identical copy of the same |

  Removing it from the vCard alone would have left it fully readable on the page
  and exactly as harvestable — the relocate-rather-than-reduce failure the
  decision existed to avoid.

  **The click-to-map handler went with it, and had to.** Both pages carried a
  `<script>` whose only job was `getElementById('address')` plus a listener
  opening Google Maps. Left behind with the block gone it returns `null` and
  throws on `addEventListener` on every card page load — a change that removes
  markup has to remove the script that reaches for it.

  The card still carries name, mobile, email and `wozi.com`.

  Verified after: no occurrence of the street, apt, city or postcode anywhere
  under `cards/`; both card pages still **byte-identical to each other**; both
  still carry `<meta name="robots" content="noindex">`, which matters because the
  deploy's `exact https://wozi.com/cards/ cards/index.html` whole-file hash check
  is the only thing gating those tags. `npm test` green.

  **Unchanged, and stated because it will be asked again:** `robots.txt` is not a
  privacy control and is not being used as one. `cards/` is still not named there
  — naming a path in the one file every scraper fetches first is a signpost, not
  a fence. The live `mailto:` links on the combined stage remain exactly as
  harvestable as before; that was considered and declined on its own merits.

- **#104 — the deploy-whitelist guard read the workflow's prose, so it could not
  fail for the reason it was written.** (GitHub #89, closing the one `survives`
  entry left by #100.) `tools/test.js` asserted `/\bconfig\.js\b/` over the
  **whole** of `.github/workflows/deploy.yml`. `config.js` is named there seven
  times — once in the loop that publishes it, twice in comments about why it
  matters, four times in the live-site checks — so the single edit that restages
  #59,

      -          for f in support.js config.js; do
      +          for f in support.js; do

  left the suite green. The guard against *"the rules requiring a file the rules
  do not name"* was being satisfied by its own explanatory comments. The same
  hole covered `support.js`, `robots.txt`, `ssh_public_key` and `keybase.html`,
  all of which are likewise named in comments and in live checks.

  **A narrower regex would have been the same bug with a smaller window**, so the
  assertion stops reading prose and reads the commands. A publish step is now
  identified by what it *does*: a step whose `run:` block issues `aws s3 cp` or
  `aws s3 sync` with a **destination under `$BUCKET`**. That is the only thing in
  the workflow that puts bytes on the web, and a comment cannot accidentally be
  one. The workflow is split into steps at the `steps:` key, each reduced to the
  shell it actually runs — shell comments stripped, line continuations folded —
  and both whitelist shapes are understood, because a file moving between them
  must not evaporate the guard:

  | shape | how the path is recovered |
  | --- | --- |
  | `for f in support.js config.js; do … cp "$f" "$BUCKET/$f"` | the `for` binding in the same step resolves the variable |
  | `aws s3 cp robots.txt "$BUCKET/robots.txt"` | the literal source |
  | `aws s3 sync assets/ "$BUCKET/assets/"` | a published **directory**, so nothing has to know which icons exist |

  **What must be published is derived, never listed here.** Two sources already
  in the tree: the `<script src="./…">` tags `index.html` carries, and every URL
  the deploy's *own* live-site checks assert is reachable. The second is the one
  that earns its keep — `check https://wozi.com/robots.txt` is the workflow
  stating the file has to be there, so a workflow that checks a file it never
  uploads is #59's shape inside a single file. Between them they require
  `index.html`, `config.js`, `support.js`, `keybase.html`, `ssh_public_key`,
  `robots.txt`, both card pages and a hub icon, with no list typed into the
  suite to go stale.

  Two more assertions, because a whitelist has two ends and a parser has a third:

  - **Every path the deploy publishes exists in the repo.** A publish list naming
    a file the tree does not have fails at run time, against a live bucket, after
    the geometry and both browsers have gone green — and the suite answers it in
    a millisecond.
  - **Nothing it is documented never to publish is in the list** — `legacy/` and
    the repo-root documents. Only checkable once the steps are parsed rather than
    grepped.
  - **A step that copies to `$BUCKET` and yields no path is a failure**, not an
    empty result. That is the parser going blind, which is precisely the fault
    this whole section replaces, so it is asserted rather than assumed.

  **Proved able to fail, in a throwaway `git worktree` at `HEAD`** — never `git
  stash`, which on a clean tree stashes nothing and silently tests the unmutated
  file. Baseline exit **0**; `config.js` dropped from the publish loop, exit
  **1**, naming `config.js (index.html loads it; the deploy asserts it is live)`
  — with the file still spelt seven times in the workflow and the old
  `/\bconfig\.js\b/` still returning `true`; restored, exit **0**. Then the other
  shape: `aws s3 cp ssh_public_key` pointed at the wrong source, exit **1**,
  naming `ssh_public_key`, which is still spelt three times afterwards; restored,
  exit **0**. The two supporting assertions were proved the same way — a
  nonexistent `runtime.js` added to the loop, exit **1**; `CHANGELOG.md` added to
  it, exit **1** — as was the blindness guard, by renaming the loop variable so
  the parser could no longer resolve it: *"a step copies to $BUCKET but no path
  could be read out of it"*, exit **1**.

  **The ratchet was updated rather than deleted.** `tools/mutation_gate.py`
  registered `config-js-off-the-whitelist` as `expect: survives` so that closing
  the gap would report `GAP CLOSED` and force this edit. It is now `expect:
  caught` — the mutant is kept as the standing proof that the gap stays closed,
  which is worth more than removing it — and a second mutant,
  `ssh-key-off-the-whitelist`, covers the individually-copied shape. The suite
  gate: **4/4 caught, 0 known gaps, 1/1 controls green**.

  While in the file: two assertion messages in *a chain that opts out of bridging
  is a root* were the only pair with no word in them marking the sentence as a
  fault — `an unbridged chain claims idlers` and `an unbridged chain is not a
  root` read as flat statements about a healthy tree, unlike their neighbours,
  which carry *"still"* and *"so nothing places it"*. They now say what broke. A
  sweep of every other `ok()`/`eq()` message in the file for the same shape found
  none; the rest already name the fault.

  `npm test` **79 passed, 0 failed** (77 before: one prose-matching test removed,
  three command-reading tests added). Nothing on the deploy path was touched —
  `deploy.yml` is asserted, not edited.
- **#99 — a service owned its URL stem in as many places as there were people
  with an account on it.** (GitHub #70.) Every link carried a whole `href`, so
  `https://github.com/` was written once per person who had GitHub, and the only
  thing keeping two spellings in step was that somebody would notice. Two people
  are on stage today; the duplication was already live, and a third would have
  made three copies of every shared stem.

  `SERVICES` now carries `url` and `path` templates with `{handle}` in them, and
  a link is a slug plus a handle. **The stem belongs to the service and the
  handle belongs to the person**, which is the split `SERVICES` was created for —
  it was always the shared half, and `SITES` was always the personal one
  (`/in/csmarshall` is Charles's, not LinkedIn's). Charles's seven links lost
  fourteen strings and gained seven.

  **Nothing moved.** Every resolved `href` and every engraved band is
  byte-identical for both people — checked by running the real `SITES` builder
  against the config at `HEAD` and against this branch and diffing the two
  tables, which is the only evidence that means anything about a refactor of a
  link table. The pixel gate agrees from the other side: **0 px** at 1440×900 and
  390×844, on `?who=charles` *and* on the combined stage. The commented-out
  Mastodon wheel resolves byte-identically too, uncommented and dumped rather
  than assumed.

  **Three things had to be decided rather than assumed:**

  - **A link that is not a stem plus a handle supplies its own `href`, and that
    href is filled by the same substitution.** So the escape hatch is not a
    second mechanism — it moves where the stem is written, not whether the handle
    has one home. Mastodon is the worked example and is honest about it: the
    instance is part of the account, so there is no stem to share, and
    `mastodon` deliberately has no `url` at all. Its band still comes from the
    service's `/@{handle}`.
  - **`mailto:` is a template like any other**, `mailto:{handle}`, with the
    address as the handle — and the substitution is **literal, never
    percent-encoded**, which is the whole reason it works. Encoding would escape
    the `@` of an address that is legal exactly as it stands, and would have been
    the one change in this branch that moved a byte.
  - **A link that resolves to nothing is left out of the table and named in the
    console.** An `<a href="">` navigates to the current page: it reads as a
    working badge and is not. Left out, the wheel is still dealt and still turns
    with no badge on it — the same unlinked wheel a missing `config.js` produces,
    which every read of that table has been guarded for since #53 and #76.

  **Harper's mail wheel is the reason `path` overrides exist**, and it survived
  this untouched: her handle is *Charles's* address and her band overrides to
  read `harper`. The two halves disagree on purpose (GitHub #65), because
  `config.js` is served to the web and a harvester reads the file rather than the
  artwork. The hazard the templates introduce is a tidy-up — deleting an override
  that looks redundant, then making the handle agree with the band — so the entry
  now says that in as many words, and the suite guards it from the other end: an
  **allowlist of the addresses that may appear in the published config**, which
  names nothing it is protecting and catches any new one arriving by any route.

  Two suite changes were forced rather than chosen, and both were latent faults:

  - **The train length was counted by grepping for `href:`.** It stripped
    comments out of `PEOPLE`, brace-walked it per person and counted a key —
    coupling to the *name of a field* a link happens to carry, and this branch
    took that field off every ordinary link. That count feeds the tooth total, so
    a suite that kept it would have dealt every chain's geometry against a train
    of length **0** and reported nothing. It runs `config.js` now, which is the
    more direct read of the same file and drops the comment stripping with it: a
    retired wheel is commented out rather than deleted, and a comment is simply
    not in the array. The cross-check that used to compare two key-counts now
    walks braces and counts **structure** — objects one deep inside a person's
    own `links` — so it shares no step with the count it is checking and knows no
    key name at all.
  - **A template typo is valid JavaScript**, so `node --check` in CI would pass a
    `config.js` whose GitHub wheel pointed at `github.com/{hadnle}/`. The new
    test runs the page's own `SITES` builder over every person and fails on an
    empty href, an empty band, or a `{` surviving into the output — verified by
    introducing that exact typo and watching it fail, then reverting. It also
    proves its own drop path is not vacuous, with a service that has no `url` and
    a link that has no `href`.

  Seven copies of `new Function('window', CFG_SRC)` in the suite became one
  `loadConfig()` while passing through, for the same reason as the rest of this
  entry.

  Not touched, deliberately: `http://` on the LinkedIn and Instagram stems, and
  the trailing slashes some services carry and others do not. Normalising those
  changes where the links **point**; this changed where they are **written**.
  They are at least in one place to tidy now. The logo half of GitHub #70 needed
  nothing — the icon is fetched at `assets/icons/<slug>.svg` and `BRAND` and
  `PILL_STACK` are keyed by slug, so a mark was never per-person.

  Gates: 71/71 suite (69 before, plus the two above), motion PASS — 37 rotating
  elements all advancing, 8 badges at ≤0.01 px, no console errors past the
  expected favicon 404 — `a11y_audit` PASS in both themes, pixel gate 0 px on
  both the solo and the combined shot.
- **#95 — the datum plate is seated from the start of the mark, not from a wheel
  on it.** (GitHub #87, closing #82 and #77.) Charles: *"seat the datum plate
  25px from the start of the datum line"*. That replaces a rule rather than
  tuning one. The plate rode the **last leading ghost** — the background wheel
  immediately before the first real gear — and a chain with no leading run fell
  back to its own head wheel. Every driven chain has no leading run, because that
  is the end its bridge arrives at, so the fallback was not an edge case: it was
  the rule for everybody but the spine, and on a one-wheel chain the wheel it
  landed on was the whole chain. That is GitHub #82, and it is gone with the
  fallback — the seat has no wheel in it to fall back to and no branch to take.

  **Which "start" it is measured from was the whole of the work.** The ticket
  lists three readings and recommends `d0`, the outermost wheel of the run
  including its background machinery, over the line's first drawn pixel, on the
  grounds that the second makes the plate a function of the window rather than of
  the machine — the property #84 was fixed to remove. Measured, that
  recommendation does not survive its own reasoning, in two separate ways:

  - **`d0` is never on the page.** An escape run is grown until it is 120 px past
    the edge of the viewport — #87 above, the entry, not the ticket — so the
    start of a chain that *has* a leading run is off the page by construction.
    Instrumented at five viewports from 390×844 to 5120×1440, `d0` sat **134 to
    281 rendered px outboard of the near edge on every one**, and the drawn line
    then runs a further two modules beyond it. `plateSeat()` clamps a station
    into the interval where the whole plate is on the page, so a preference
    stated from `d0` would have been overruled on every load ever drawn: a
    constant that never once takes effect, which is worse than no constant.
  - **No referent measured on the machine answers GitHub #82.** A chain with no leading
    run starts its mark *at its own first gear*. Both `d0` and "the first linked
    wheel" put that plate within a wheel's radius of the one wheel the chain
    owns — which is the complaint restated at 25 px, not a fix for it.

  So the mark starts where the **drawing** starts: `Math.min(d0, the drawn area)`
  less the run-out, and the page takes over once that is outboard of the frame.
  One `Math.max`, and the machine still decides wherever the drawing stops inside
  the frame — before the first fit there are no ghosts to widen the drawn area,
  and a chain may be dealt a run that leaves by the far end only. The reasoning
  is the one datumRuns() already states for the cross axis: *off the page is
  invisible, and invisible is the one thing this mark may not be.*

  **`PLATE_START_ALONG = 25`, named for the axis it acts on.** `PLATE_TOP_CLEAR`
  is measured **across** the line, from the chain's extreme border to the top of
  the placard; this is measured **along** it, from the start of the mark to the
  plate's near edge — the plate's own half-width is carried inside `plateSeat()`
  so what the figure names is the gap a viewer can actually see. The two were
  filed as one ambiguous "20px" (GitHub #77) before either was written down, and
  a second bare 20 beside the first would have read as related.

  The line's slab clip moved out of `datumLayer()` into `slabClip()`, because the
  seat and the drawing now have to agree about where the mark starts: a second
  copy of that arithmetic is a plate standing a little way off the end of its own
  line. `plateAt` is gone from the run, and with it the leading-ghost search that
  produced it. The ghosts still record `lead` — the escape-run suite reads it to
  assert that only the spine gets a leading run — but nothing in the page reads a
  ghost's `k` any more, and that field is now dead. It is left alone rather than
  deleted because it is set in `fitEscapes()`, which is not this change's to
  touch; it wants a line of its own.

  **What wins on a narrow screen: the seat.** The figure is a preference; the
  interval in which the whole plate is on the page is not. A page shorter along
  the run than the figure plus a plate pushes the plate *back* toward the start —
  closer in than 25 px rather than hung over the far edge — and the suite asserts
  that direction, because guessing it wrong is invisible until somebody resizes.

  Measured from the DOM after the change: every plate's near edge sits **25.0 px**
  from the near edge of the page along its own line, at 2560×1440, 5120×1440,
  1440×900, 900×1400 and 390×844, portrait and landscape, and none of them
  overlaps a live gear. The combined stage differs from HEAD by **7,248 px**
  (5,593 at 1440×900, 1,655 at 390×844) and the diff is two plate rectangles at
  each viewport — the one they left and the one they arrived at. Nothing else
  moved. `?who=charles` is **0 px**: a solo page draws no datum at all.

  **GitHub #83 is not fixed here, deliberately.** A one-link chain has one
  station, so it gets one major tick and no minor ones, and the design is
  explicit that minor ticks subdivide the gap between stations *"without
  inventing a spacing to give it one"*. Every candidate needs a second choice
  that nothing derives — which gap of the spine's, or how far the marks run on a
  chain that has no gap of its own — and inventing that is the thing an earlier
  mock was rejected for. Nothing was implemented. What this change does do for it
  is remove the aggravation that ticket names: that chain's plate no longer sits
  on the same lone gear as its one tick.

  Gates: 69/69 suite, devices 24/24 and 4/4, motion PASS (37 of 37 rotating, no
  strands, badges at 0 px), pixel gate as above. Looked at in light and dark at
  2560×1440 and 5120×1440, and in portrait at 900×1400 and 390×844.

- **A hostname selects a scope, not a person — and `wozi.com` is now everybody.**
  This is the change a visitor sees. `wozi.com`, `www.wozi.com` and the loopback
  names moved off Charles's entry into a new top-level `STAGE_HOSTS`, and they
  draw the combined stage: Charles's seven wheels along the spine, Harper's one
  bridged off it through ghost idlers, each chain against its own scribed datum.
  `charles.wozi.com` is Charles alone, `harper.wozi.com` is Harper alone,
  `?who=<slug>` is that person solo and `?who=all` is the stage.

  **The fallback changed with it**, from `PEOPLE[0]` to the combined stage. An
  alternate domain name reaches the distribution long before anyone edits
  `config.js`, and until they do it matches no list at all — it used to be served
  one person, with nothing on the page to say that was a default. A hostname
  nobody has claimed is far likelier to be another way of saying "this site".

  **The picker is now hidden on a personal page.** It appeared whenever there was
  more than one person; it now also requires `STAGE.mode === 'all'`. A link to
  `charles.wozi.com` should not hand the visitor a menu of everyone else living
  on the domain — the old rule was this rule with the scope left out. Nobody is
  marked `aria-current` on the combined stage either: every entry there is a link
  *away* from what is being looked at, and `WHO` is the spine, not the selection.

  Two things had to be proved rather than assumed, because the default view
  changing means the pixel gate's own baseline changes:

  - `?who=charles` is **0 px** against `439c9ba` at 1440×900 and 390×844, in
    **both themes**. Nothing in the whole idler-bridge branch touched the
    single-chain path, which is the only way to say that with a number. The gate
    grew a `--query` flag to ask it at all: it serves on `127.0.0.1`, which is
    now a stage host, so its default shot is the combined stage.
  - The default shot differs by **801,797 px** (608,767 at 1440×900, 193,030 at
    390×844) against `439c9ba`. That is the feature, photographed.

  `?who=harper` renders her chain alone: one wheel at a sane size, no datum — a
  datum needs two chains to discriminate — and no bridge, since solo is not a
  separate path but a tree with no branches.

  One real defect fell out of making the picker visible. The rule between the
  people and the gear families was drawn as its own menu entry: an `<a>` with an
  empty `href` and no text, which the menu template cannot hide from the
  accessibility tree — a **focusable element with no accessible name**.

  **It was shipping, not latent.** The claim that it cost nothing until the apex
  drew the picker was wrong: at `439c9ba` the picker's gate was already
  `people.length > 1` alone, and `PEOPLE` had had two entries since Harper was
  added. The panel's `display:none` hides nothing from the audit, which counts
  `a[href]` straight out of the DOM. It was on the live page.

  The rule is now its own `<div>` between two lists, guarded by `sc-if` — the
  1px hairline it always was, inset 10px, floating in 6px of gap, and unable to
  take focus. It is **not** a `border-top` on the first gear entry: that entry is
  a 9px-rounded pill filled with `--accent` on any page without a `?kind=`, so a
  border there draws on the top edge of a block of colour, at the entry's full
  width rather than the rule's inset one. `a11y_audit` went from FAIL to PASS.

  **The pageview beacon reports the scope now, not the spine.** It sent
  `view/` + `WHO.slug`, and `WHO` is `CHAIN_ORDER[0]` — so every visit to the
  combined stage reported `view/charles` and was indistinguishable in the
  analytics from a visit to `charles.wozi.com`. The same spine-versus-selection
  confusion as the `aria-current` above, in the one place where being wrong
  produces a plausible-looking number instead of a visible fault. It sends
  `view/all` on the combined stage.

  `CLAUDE.md` gained the host model and four invariants this branch had been
  relying on without naming: the bridge as structure versus escape runs as
  decoration, the axis-relative bridge bearing (#67's class), longest-first
  non-overlapping chain order, and the bridge's refusal to draw a crossing. That
  omission is the #59 failure — the rulebook requiring what the rulebook does not
  name.

  Gates: 63/63 suite, motion PASS on the apex and on both solo views,
  `mesh_dirs` PASS (8 meshing pairs, 1 idler on that viewport), devices 20/20 and
  4/4, `a11y_audit` PASS in both themes. Apex looked at in light and dark at
  1440×900, 390×844 and 2560×1440; portrait puts the bridge across the *long*
  axis, as the axis-relative bearing requires.

### Added

- **#100 — `tools/mutation_gate.py`, which breaks the page on purpose so that
  every other gate has to prove it can fail.** A gate observed green is not a
  gate proven able to fail. This repo has shipped a harness that printed FAIL
  and exited 0, one that had been dead with a `NameError` for weeks, and one
  with no exit code at all — and on a healthy tree all three were
  indistinguishable from a gate that was working, because a working gate and a
  blind gate produce the same output when there is nothing to find. The only
  way to tell them apart is to put a bug in the tree.

  Eight mutations, each a single surgical substitution in one named file, each
  chosen to restage a failure this project has actually had rather than to
  scramble something arbitrary:

  | mutant | file | gate | what it restages |
  | --- | --- | --- | --- |
  | `BAND_DEPTH` 1.59 → 0.50 | `index.html` | `test.js` | #15, and the class `CLAUDE.md` names by hand: the band feeds the bore, and a bigger bore makes gear sets reachable that nothing has measured |
  | a stage host added to a person's `hosts` | `config.js` | `test.js` | the host model's one hard rule — `STAGE_HOSTS` is matched first, so a name in both quietly means *everyone* |
  | `config.js` dropped from the publish loop | `deploy.yml` | `test.js` | #59 — published but unnamed. **This one survives**; see below |
  | `asleep = document.hidden \|\| …` → `asleep = true` | `index.html` | `verify_motion.py` | #7 — the sleep gate latching, and a frozen train photographs perfectly |
  | a hub icon's slug misspelt | `config.js` | `verify_motion.py` | the empty badge: `loadIcons()`'s `.catch` swallows the failure and nothing on the page says so |
  | pill label `13px/1.4` → `13px/1` | `index.html` | `pill_clip.py` | #51, byte for byte — the line box shorter than the ink, so `overflow:hidden` slices the descenders |
  | ghost stroke opacity 0.65 → 0.45 | `index.html` | `pixel_regress.py` | #48's own hand-run proof: geometry identical, train turning, badges centred, type fitting, and the drawing changed |
  | `LINK_SHARE` 0.78 → 0.20 | `index.html` | `devices.py` | #44's collapse and #46's floor — every wheel still meshes and turns, the composition is simply wrong |

  The order is red, then green: each gate's mutants run first and must exit
  non-zero, then the gate runs once more on the restored tree and must exit
  zero. A control that cannot go green voids that gate's whole verdict rather
  than being reported alongside it, and it gets one retry first, because the
  page is dealt at random and a gate that reads the composition can go red on
  whichever machine it was handed (#88).

  **Nothing is mutated in the working tree.** Every run happens in a throwaway
  `git worktree` at `--ref` (`HEAD` by default), thrown away at the end — the
  same shape `pixel_regress` already used, and for a sharper reason than
  tidiness: `git stash` on a clean tree stashes *nothing* and reports success,
  so a stash-based runner silently tests the unmutated tree and passes forever.
  The consequence is stated at startup rather than buried: this gate measures
  the committed tree, and it prints how many uncommitted changes it is
  therefore not testing.

  **It runs in its own workflow, not on the deploy path**, and that is the one
  judgement call here worth arguing with. `deploy.yml` gates a live bucket on
  every push and every pull request; the full sweep is **500s**, of which 414s
  is the device gate alone, run twice — once mutated, once as the control.
  Tripling the latency of a deploy to re-answer a question whose answer changes
  only when a *harness* changes is the wrong trade, and a flake in a second
  browser-heavy job racing the first would block a deploy over something that
  is not about the deploy. So `.github/workflows/mutation.yml` splits it by how
  often the answer can move:

  - **`registry`** — one second, no browser, on every push and pull request. It
    runs the sweep with every gate replaced by one that always exits 0 and
    requires the runner to come back FAIL. That proves the runner can fail, and
    it proves all eight mutations still apply to the files they name, which is
    the one thing ordinary page edits rot silently: rename a constant and the
    mutant stops testing anything while reporting a clean sweep.
  - **`mutate`** — the real 500s sweep. Weekly, on demand, and on a pull request
    labelled `harness`.

  **Proved able to fail in every direction it can fail**, which for this file is
  not optional — a mutation gate that can only pass is precisely the thing it
  exists to prevent. Exit **0** on a working sweep (7/7 caught, 5/5 controls
  green). Exit **1** with `--blind`, every gate stubbed green: 0/7 caught, every
  mutant reported SURVIVED. Exit **1** again on the opposite fault, a documented
  gap that has silently closed. Exit **2** when a mutant's `find` string no
  longer occurs exactly once, naming the mutant and the string — simulated by
  pointing `band-depth-halved` at a constant that does not exist.

  **One mutant survived, and it is kept rather than dropped.** `test.js` asserts
  `config.js` is named in the deploy whitelist — the guard against #59 — but the
  assertion is `/\bconfig\.js\b/` over the *whole* of `deploy.yml`, and
  `config.js` is named there seven times: once in the loop that publishes it,
  twice in comments about why it matters, four times in the live-site checks.
  Delete it from the publish loop and `npm test` stays at **69 passed, 0
  failed**. The guard cannot fail for the reason it was written. It is filed on
  the tracker as issue #89 (the log's numbers and the tracker's are separate
  spaces, and this is one of the places they collide), and it is registered here
  as a mutant expected to **survive** — so the day the assertion is strengthened
  this runner fails with `GAP CLOSED` and the entry has to be removed, instead
  of a stale excuse quietly outliving the defect.

  Two things did not make the set. The issue proposed `TEETH_MAX` 19 → 26 as the
  suite's mutant; it **survives** — the suite simply measures the twentieth
  single-row set that the wider bound reaches, and passes it — which is the
  suite being right rather than blind, so `BAND_DEPTH` took its place. And there
  is no mutant for `a11y_audit.py` or `webkit_band.js`: neither runs in CI, and
  a mutation gate for a gate nobody runs is a longer list, not a better one.

  Nothing on the deploy path was touched. `npm test` is unchanged at 69 passed,
  0 failed.
- **#96 — a gearbox on the corner widget, with a benchmark stop at the top of
  it.** (GitHub #69.) A fourth corner button, between the table of gears and
  pause, wearing its own value instead of an icon: `1×`, and a press moves it to
  the next stop. Eight of them, **1, 2, 5, 10, 20, 50, 100, 200**.

  **Most of it was already built, and the first job was to prove that rather
  than assume it.** `idleRate()` has multiplied by `this.props.speed` for a long
  time, but nothing on the page could set that prop and no measurement had ever
  been taken through it, so "the integrator already honours speed" was a reading
  of the source and not a fact. It is a fact now. The `speed` default was moved
  to `2` in a copy of the document served beside the original, `Math.random` was
  seeded before either page's first script so both dealt the *same* train — tooth
  counts are dealt per load, and rotation rates from two different deals are not
  comparable — and the same 39 rotating elements were sampled over a fixed window
  after the flywheel had settled: **24.4779 → 48.9501 deg/s** on the median, and
  2.0000 on the min and the max as well. The whole train scales by one factor
  because there is one integrator. So the work here was a control, not a
  mechanism.

  ### The stop where it stops being animation

  A gear turning fast enough strobes. Past half a tooth pitch of travel per tick
  the sampling is under Nyquist and the train visibly stands still or runs
  backwards — the wagon-wheel effect — and that is the one high-speed artefact
  that reads as *broken* rather than as fast. The limit is exactly computable,
  and it does not depend on the tooth count at all:

  A wheel's angle is `phase + dir * _M / teeth` and its pitch is `360 / teeth`
  degrees, so **one tooth of travel is 360 master-degrees on every wheel in the
  train**. A 13-tooth blank and a 19-tooth one cover the same fraction of a tooth
  per tick, and there is one strobe speed for the whole machine:

  ```
  master-deg per tick at 1x = (7200 / BASE_MS) * (1000 / frameRate)
                            = 0.342857 * 33.33 = 11.43     (BASE_MS 21000, 30fps)
  tooth fraction per tick   = 11.43 / 360      = 0.0317
  strobe at half a pitch    = 180 / 11.43      = 15.75x
  ```

  Measured, the crossing lands exactly there: 10× covers 0.334 of a tooth per
  tick (67% of the limit) and 20× covers 0.663 (133%).

  **The ladder is allowed past it anyway.** Charles asked for a top stop that is
  "ludicrous", usable "almost … to do benchmarking", so `strobeSpeed()` no longer
  truncates the ladder — it *classifies* it. Every stop at or above 15.75× says
  "strobing — benchmark only" in its accessible name and draws its numeral in
  `--accent` rather than `--muted`. A control that silently hands over a setting
  which breaks the illusion is worse than one that says where the illusion ends.

  ### Why these eight numbers

  A 1-2-5 preferred-number ladder between the schema's `min` and `max`. Equal
  ratios rather than equal increments, because the effect is perceptually
  multiplicative — 1× to 2× and 50× to 100× are the same size of change to look
  at — and 1-2-5 is the standard logarithmic ladder for exactly that: scope
  timebases, chart axes, preferred component values. 1 to 200 gives eight
  positions, which is as many as a cycling button can carry, and **200 is a rung
  of that ladder exactly**, so the ceiling is Charles's number landing on the
  ladder rather than the ladder being bent to reach it. The floor is 1×: the
  control only ever speeds the machine up, because slowing it down was not wanted
  and stopping it is already the pause button's job.

  Nothing about the spacing was picked. `min` and `max` are the only levers, and
  the strobe limit is not written down anywhere — it is a property of `BASE_MS`
  and the frame rate, derived by `strobeSpeed()`, exactly as `gsRender()` reads
  `--gsfit` out of its own CSS declaration rather than keeping a copy.

  ### The benchmark, measured

  Every stop, same seeded deal, 10s windows at 1440×900 in headless Chrome. Ticks
  are counted as `applyRotation()` bursts — `step()` early-returns under its frame
  budget, so rAF callbacks are *not* ticks and counting them would report 60 on a
  page updating at 30:

  | stop | deg/s | ratio | ticks/s | rAF/s | tooth/tick | % of Nyquist | rim px/tick | rim/cap |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | 1× | 24.47 | 1.000 | 28.86 | 59.96 | 0.033 | 6.6% | 0.76 | 0.07 |
  | 2× | 48.96 | 2.001 | 29.37 | 59.98 | 0.065 | 13.0% | 1.49 | 0.14 |
  | 5× | 122.88 | 5.021 | 29.23 | 59.96 | 0.163 | 32.6% | 3.75 | 0.41 |
  | 10× | 244.30 | 9.983 | 28.49 | 59.98 | 0.334 | 66.9% | 7.65 | 0.70 |
  | **20×** | 490.62 | 20.048 | 28.74 | 59.98 | 0.663 | **133%** | 15.23 | **1.57** |
  | 50× | 1226.22 | 50.108 | 28.98 | 60.08 | 1.643 | 329% | 37.74 | 3.43 |
  | 100× | 2452.56 | 100.220 | 28.99 | 59.97 | 3.286 | 657% | 75.46 | 7.15 |
  | 200× | 4895.75 | 200.057 | 29.74 | 59.97 | 6.405 | 1281% | 146.83 | 14.29 |

  **The headline is the column that does not move.** Ticks per second sits at
  28.5–29.7 at *every* stop, 200× included, against a nominal 30. The renderer
  does not care how fast the train is going, and the reason is structural rather
  than lucky: the work per tick is 39 transform writes whatever the multiplier
  is, and speed changes the number written into each one, not the number of
  writes. **Speed is free; only the illusion is not.** The 1.5ms margin in
  `budget = 1000/tickRate - 1.5` was flagged as thin, and it may well be — but no
  stop on this ladder is what makes it thin, and nothing here moved it.

  Two independent limits land in the same gap, which is worth noting because
  neither was fitted to the other. The teeth cross Nyquist between 10× and 20×;
  the rim engraving crosses `rim/cap = 1.0` — where consecutive frames share no
  ink at all and the handle reads as a train of ghosts rather than one moving
  object — between 10× (0.70) and 20× (1.57). Rim travel was measured on the
  wheel the lettering actually sits on, off that wheel's own rotating ancestor
  and its own radius, with the cap converted out of SVG user units by the
  wheel's own viewBox scale. **10× is the last honest stop, by both measures.**

  ### Accessibility, and the one real defect this found

  The numeral is *text*, and axe checks text contrast where it does not check an
  icon's stroke. WCAG asks 4.5:1 of small text and 3:1 of graphics, and `--muted`
  on `--bg` is **3.54:1** — so at 13px the new button **failed** the light-theme
  audit while its three neighbours passed at exactly the same colour. Bold text
  at 18.66px or more is "large scale" and back to a 3:1 threshold, and `--icon`
  is already 20px, so the label is set at `--icon`: the same size as the glyphs
  beside it, clearing the bar by construction rather than by a number somebody
  has to remember. Measured after the change, every stop passes in both themes —
  3.54:1 for the plain stops and 4.69:1 for the strobing ones in light, 6.21:1
  and 7.93:1 in dark. The warning state is the *more* legible of the two, not the
  less.

  The accessible name reports where the machine is, whether that stop strobes,
  and where the next press puts it — "Gear speed 20×, strobing — benchmark only,
  next 50×". A cycling control that reports only its current value tells a screen
  reader user nothing about what activating it does, and the full name is also
  what keeps it unique, which is the check #74 added.

  ### Everything else it touched

  - **`driveCap()`, because a fixed clamp became a brake.** A flick or an arrow
    key was bounded at ±8 master-deg/ms, which stood comfortably while idle was
    0.343 — twenty-three times slower, so the bound only ever caught a violent
    flick. Idle reaches **68.6** at 200×, where a single arrow press would have
    slammed the train from 68.6 to 8 and then climbed back over ~900ms. The bound
    is `max(8, idleRate())` now: a ceiling again at every stop, and identical to
    the old one at 1×.
  - **The choice persists** in `localStorage` under `wozi-speed`, restored before
    the flywheel is seeded so a `spinUp:false` page starts at the chosen rate
    instead of easing up from the default. Bounded by the ladder's own ends
    rather than by numbers written at the read site: `9999` is discarded and the
    button returns to `1×`; `1.25`, which is *between* stops, is kept, because
    `speedIndex()` can always say which stop a value is nearest and offers `2×`
    as the next press. A setting the control cannot leave is the failure worth
    guarding against, not an unfamiliar number.
  - **A dead `speed` read came out of `syncVars()`.** It resolved the multiplier
    on every render and dropped it on the floor — it belonged to the `--s`
    variable deleted in #57 and outlived it. Speed reaches the page through
    `idleRate()` and never through CSS.
  - **`tickRate()` is one home for the update rate.** `step()`'s frame budget and
    `strobeSpeed()` are both computed from it; two copies of `?? 30` would have
    been a control offering stops the renderer had stopped being able to show.
  - **`tools/devices.py`'s comment said "the three corner buttons".** The code
    was always right — it enumerates `button` elements, which is why the fourth
    was measured the moment it existed — but the prose had gone stale.

  The row's arithmetic did not change shape, only length. Each button's `right`
  is its index in whole button pitches — `(--btn + --btngap)` — off `--offright`,
  which already carries the safe-area inset, so a fourth button costs one term
  and no new constant. The table of gears moved from index 2 to 3; pause and
  theme did not move. Three of the four styles are still repeated inline
  verbatim, which remains deliberate. **The speed button's is a render value**,
  and that exception has exactly one reason: its colour depends on state, which
  is the thing the other three do not have.

  Gates: 69/69 suite (unchanged), `verify_motion` PASS, `a11y_audit` PASS in both
  themes — 27 focusables, 0 unlabelled, no duplicate names, 0 targets under
  24×24 — and `devices` 24/24 with 4/4 safe-area, which is the pass that measures
  every fixed control against injected insets and therefore the one a fourth
  control is for. Photographed at all eight stops in both themes. The button box
  is 44×44 at every stop; the widest label, `200×`, renders 45.9px and so sits
  1.9px proud of its own transparent disc, which collides with nothing — its
  neighbours are 20px glyphs centred in 44px discs, leaving 19px of clear space.

  **Not verified:** the pixel gate's stored baseline was not reshot — the control
  is a visible addition to every view, so both the combined-stage and
  `?who=charles` shots necessarily differ from `main`. And the frame-rate figures
  are headless Chrome on an idle workstation, which is the easy case: they say
  the multiplier costs nothing, not that the page holds 30fps on a loaded phone.
- **#94 — the checks only a phone can make, written down instead of remembered.**
  (GitHub #49.) `docs/MANUAL-CHECKS.md`, and it is documentation of a gap rather
  than a new gate: nothing runs it and nothing can.

  Everything in `tools/` is headless Chrome over CDP plus `webkit_band.js`, which
  builds a WKWebView that opens no window. So the directory has no browser chrome,
  no window manager, no battery and no finger, and six questions fall straight
  through it — a URL bar collapsing mid-scroll, rotation with the keyboard up,
  home-indicator and Island overlap, Low Power Mode's rAF throttling, Safari's own
  controls landing on the page's, and whether iOS hands the page the safe-area
  insets `devices.py` has to inject for it. Each entry says what to do, what
  correct looks like, what failure looks like, and — the part worth the file —
  which line of which harness proves the question cannot be automated.

  Two of those are worth naming here because the code already half-answers them
  and the half is easy to mistake for the whole:

  - **The safe-area pass tests the layout consequence, not the insets.**
    `devices.py` sets `--safe-t/r/b/l` itself, from Apple's published figures, and
    measures the fixed controls against the rectangle that produces — because
    Chrome resolves every `env()` to 0 on every emulated device, the insets coming
    from the real window manager rather than the metrics override. The file has
    said so honestly all along; what it could not do is say who checks the other
    half. Now something does, and it says which numbers are the assumption.
  - **Nothing measures the frame *rate*.** `verify_motion.py` samples the DOM
    twice ~700ms apart and reports how many transforms advanced, which is a
    binary a train at 15fps passes exactly as well as one at 30; and
    `pixel_regress.py` cannot ask at all, since it queues rAF rather than running
    it and pins `performance.now` to a virtual clock. That matters under Low Power
    Mode, where iOS is understood to throttle rAF to about 30Hz: the loop's budget
    is `1000/30 - 1.5` = 31.83ms, so a 33.3ms stream clears it on every callback
    and the train should still run at pace — with 1.5ms of margin, and any jitter
    under the budget dropping the tick. Projected worst case is the rate falling
    toward 15fps. Hopefully the margin holds on a real phone; this is arithmetic
    off `index.html:2517`, not a measurement, and check 4 is how it gets one.

  **A repro from a phone is only useful if it can be reproduced, and it cannot
  be yet.** Eleven bare `Math.random()` sites deal the machine, so "it looked
  wrong on my phone" describes a train that will never be drawn again. The
  in-page `?seed=` hook is GitHub #48 part 1 and does not exist — `index.html`
  parses no `seed` parameter, and the determinism both harnesses rely on is
  injected over CDP before page script runs, deliberately out of reach of a
  phone. The file says so rather than implying a hook is there.

  Referenced from `CLAUDE.md` under *Verifying a change*, after the pixel gate.
  Not published: `docs/` is absent from the deploy whitelist and stays absent.

  This is the unblocked half of GitHub #49. **Whether to adopt Playwright is
  Charles's call and nothing here takes it** — no dependency was added,
  `package.json` still has none, and the issue stays open on that question.
- **#93 — four assertions about the rendered DOM, in the gap between the maths
  suite and the pixel gate.** (GitHub #48.) `node tools/test.js` proves the gear
  *maths* meshes — in Node, with no browser, off the constants it reads out of
  `index.html`. `tools/pixel_regress.py` proves the page draws the same
  *picture* as a git ref. Between the two sat the renderer, and nothing asserted
  that what `solve()` computed is what the DOM actually contains. A wheel could
  render with the wrong tooth count, an empty `<svg>`, an engraving that paints
  nothing or a fill that had gone black, and the maths suite would pass because
  the maths never moved, while the pixel gate would either pass — the
  single-chain path untouched — or fail with a number that says only "801,797
  pixels differ".

  `tools/dom_invariants.py` makes four structural assertions from one CDP
  evaluate. **No images, no baselines, no rasterisation anywhere in it**, which
  is what lets it run on CI's Linux today rather than being a thing that only
  agrees with itself on one laptop.

  - **Mesh at render time.** Every wheel's centre distance to at least one other
    equals the sum of the two pitch radii. Deliberately *not* "these pairs
    mesh", which would be circular — find the pairs that mesh, then assert they
    mesh. It is that **no wheel is an orphan**: `solve()` places every wheel
    after the first against one already placed, so a wheel meshing with nothing
    is a wheel the renderer put somewhere the solver did not.
  - **No wheel renders empty.** `teethPath()` emits exactly two quadratic fillet
    blends per tooth and no other `Q`, so the blank *states its own tooth
    count* — and the wheel's rendered radius states what that count must be,
    since a pitch radius is `MODULE × teeth / 2`. The two are compared as
    integers with **no tolerance at all**, and came out exact on every wheel of
    every run. Plus the blunt half: a shape floor, and every hub badge holding a
    drawn icon.
  - **Engraving present.** Three things, because only the third can tell a drawn
    engraving from a present one: non-empty text, a `textPath` target that
    resolves inside the same `<svg>`, and `getComputedTextLength() > 0`. A
    dangling `href` leaves the string in the DOM and paints nothing.
  - **Ink census.** Every colour on a wheel comes from `flatTones(c)` or
    `shades(c)`, both pure functions of one base that mix it toward black or
    toward white. So the census is not a count of colours, it is a statement
    about the set: **each ink must be a tone of that wheel's own base** — same
    hue, saturation not thrown away, value inside the band those mixes reach.
    The base is read off the blank's own fill, through its gradient when that is
    what the fill points at, so nothing here needs to know the palette. `FLAT_INK`
    is the one exemption and is read out of `index.html` rather than retyped.

  **The verdict is seeded, because an unseeded one is a property of whichever
  machine you were dealt.** Same LCG over `Math.random`, injected through
  `Page.addScriptToEvaluateOnNewDocument` before any page script, as #88 put
  into `devices.py` — and `Page.enable` must come first or the injection is
  accepted and silently never runs. Determinism lives in the harness; the
  shipped page still carries no test hooks.

  **Every check was proved able to fail** (#47), one mutant tree per check, each
  turning exactly one line of a throwaway copy of `index.html` red:

  | mutation | exit | what went red |
  | --- | --- | --- |
  | one anchor moved 3 solve units off its solved centre | 1 | mesh only — orphan wheel, 2 components, nearest distance off by 3.97px |
  | one blank drawn with one tooth fewer than its radius implies | 1 | blank only — "draws 14 teeth but its rendered pitch radius implies 15.000" |
  | the handle's `textPath` pointed at a ring that does not exist | 1 | engraving only — 8 wheels, "target does not resolve" |
  | the hub ring's stroke replaced with `#000000` | 1 | ink only — "keeps 0.00 of the base #e8615a's saturation" |
  | `loadIcons()` pointed at a path that 404s | 1 | blank only — 8 badges, 0 carrying an icon |

  The last row is the one worth keeping: that failure is what a `file://` load
  produces, and what a wrong `Content-Type` on the `assets/` objects would
  produce on the live site, and `loadIcons()`'s `.catch` swallows it in silence.

  **The mesh tolerance is 0.35px and it is the same number, reached the same
  way, as `mesh_dirs.py`'s.** `S` is recovered lossily — `--gsfit` is written as
  `toFixed(3)` and re-floored to the render's own 2-decimal quantisation, which
  can land a step out — and one step of `S` multiplies the 13-unit radius pad on
  *both* wheels of a pair: 0.26px worst case. Measured over 30 runs (5 seeds ×
  2 themes × 2 scopes, then five viewports from 375×667 to 5120×1440) the worst
  residual on a real meshing pair was **0.0045px** and the closest non-meshing
  pair was **47.5px** away. The brief asked for ~0.5px; the tighter figure is
  used because the analysis was already paid for and the margin supports it.

  Two constants in there are **stated rather than derived, and say so**: the
  four-shape floor and the three-ink floor. Both renderers are nested `h()`
  calls a thousand lines long rather than a table, and a regex counting their
  unconditional emissions would be more fragile than the number it replaced.
  What keeps them from mattering is that the check they back — the tooth census
  — is exact.

  **What it does not cover, stated so nobody reads more into a green run than is
  there.** It is a still: nothing here looks at motion, which is
  `verify_motion.py`'s job, or at direction, which is `mesh_dirs.py`'s. It
  cannot see a whole chain drifting out of position as a rigid body — every
  wheel in it still meshes with its neighbours. It reports the mesh graph's
  component count but does not assert it, because a bridge that refuses is a
  documented state and a gate that failed on it would be failing a page doing
  exactly what it was told. The ink census covers the wheels, not the hub icons'
  brand colours. And it is Blink only, so it says nothing about WebKit — which
  is the gap `webkit_band.js` exists to cover, and #19 is the reminder that the
  gap is real.

  Gates: 69/69 suite unchanged. `dom_invariants` PASS on the combined stage and
  on `?who=charles`, in both themes, at 375×667, 390×844, 744×1133, 1440×900,
  2560×1440 and 5120×1440, ~4.6s per run. Wired into the deploy workflow beside
  `devices.py`, `verify_motion.py` and `pill_clip.py`, before any AWS credential
  is assumed, and run against **both scopes** because they are different code
  paths: `127.0.0.1` is a `STAGE_HOSTS` name, so the bare URL is the combined
  stage — bridges, idlers, a datum — and `?who=charles` is one chain with none
  of them.
- **#97 — one colour, and a whole chain made of it.** (GitHub #68.)
  `palette: '#B79CE8'` on a `PEOPLE` entry says "make this person's machine light
  purple", and every wheel on that chain comes out that colour or a near
  variation of it. Harper's chain is purple as of this entry, at Charles's
  request, seeded `#9B8CE0` — the pool's own purple, an authored colour that has
  already been judged good on these wheels. Her chain is one wheel today, and a
  chain of one gets the seed **exactly**.

  **The default palette is untouched.** `WHEEL_POOL` is still authored, still
  ground truth, and `dealColours()` is the function that shipped, line for line —
  a chain with a seed is taken out of that deal altogether rather than changing
  how it works. Saying so plainly because the history invites the opposite
  reading: five attempts at deriving the *pool* from a formula were all worse and
  that is settled (#40). This derives **one person's opt-in family from a colour
  they chose**, which is a different question with a different answer.

  **The hard problem was #12, and it did not survive contact with the
  requirement.** The 40-degree minimum hue separation between meshing wheels is a
  proxy for "a viewer would call these the same colour", and it is a good proxy
  exactly while hue is the axis carrying the difference. A single-colour family
  has no hue difference by construction, so that rule would reject every possible
  arrangement. The obvious repair is to re-express #12 perceptually — OKLab, one
  rule everywhere, separation carried by whichever axis is available.

  **Measured on the shipped pool, that repair is not available, and the numbers
  say so plainly.** In OKLab the closest pair the 40-degree rule *allows* into
  mesh is `#9B8CE0`/`#DB79B8` at ΔE **0.117**; the two blues the rule exists to
  keep apart, `#4A90E2`/`#8CB8F2`, are **0.135** apart and the two greens
  **0.168**. A single ΔE floor would have to be at or below 0.117 to leave the
  pool dealable and above 0.135 to go on rejecting the blues. No such number
  exists — on this pool the two metrics disagree about which pair is closer, and
  swapping one for the other would seat the exact pair #12 was written for.

  So the rule is stated once and **measured twice**, by whichever axis the
  palette actually varies on: *no two meshing wheels may be ones a viewer would
  fail to tell apart*. A pool-dealt chain varies by hue and is judged in degrees.
  A single-colour chain varies by lightness and chroma and is judged in OKLab.
  Neither is ever relaxed, and they are never both applicable — every meshing
  pair in the deal belongs to one chain and therefore to one palette, because a
  chain head past a bridge meshes an idler rather than another chain. The suite
  asserts the contradiction that justifies keeping two rules, so the day the pool
  changes enough for one to do it is the day a test says so.

  **What varies, and how far.** Lightness does most of the work; chroma follows
  it, held at the seed's own fraction of what the sRGB gamut allows at each
  lightness, which is how a tint behaves and which cannot leave the gamut by
  construction. Hue moves a little and deliberately — `MIN_HUE_SEP / 2` across
  the whole ramp, half the angle at which this page already calls two hues
  different colours — because a family with no hue movement reads as
  machine-generated tints of one swatch. The ramp only opens as far as the wheel
  count needs: a short chain stays near the colour that was asked for.

  **Every bound is something the pool already reaches**, so the rule is always
  "no worse than a wheel that ships" rather than a number somebody picked:

  - the **tonal envelope**, measured through the same `flatTones()` the page
    draws with, in *both* themes — body luminance 0.240–0.566 light, 0.261–0.576
    dark. No derived wheel may be lighter than the lightest that ships or darker
    than the darkest.
  - the **engraving margin** — `FLAT_INK` at its own opacity must reach at least
    2.61:1 light and 2.75:1 dark over the body, which is what it reaches over the
    worst pool wheel. A pale family is exactly where that gets thin.
  - the **spacing it aims for** — ΔE 0.117, the closest this page has ever put
    two meshing wheels, so a chain short enough to afford it is spaced exactly as
    widely as a pool deal.
  - the **floor it must clear** — the ΔE between a wheel's body and its own
    raised face, the smallest tonal step this artwork already asks every viewer
    to see, measured per seed on the colour actually drawn.

  **The arithmetic, and what happens past it.** The legible band around
  `#B79CE8` is ΔE 0.191 deep, so the wheels are `span/(n-1)` apart and the seed
  holds **9** wheels before the closest pair drops under its own floor. Seven
  wheels leave 0.0281 against a floor of 0.0198; ten leave 0.0190 and the console
  says so, naming the seed, both numbers and the real capacity. The chain is
  still drawn — one that is absent is worse than one that is subtle — but it is
  never drawn while claiming the spacing held. Capacity across the seeds
  photographed runs 7–14, and it is **asked rather than predicted**:
  `floor(path / faceStep) + 1` is the right way to think about it and is off by
  one on real seeds, because the ramp is a curve through a gamut boundary rather
  than a straight line.

  **Three failures were built and then measured out**, each caught by a test
  written before the fix:

  - The band is walked at the seed's hue and the ramp does not stay there.
    `#F2C14E` put its top rung at 0.573 luminance against a ceiling of 0.566,
    because the hue it drifted to carries more chroma and therefore more light.
    Every legibility question is now asked at both edges of the widest wander the
    ramp can ask for, and the colours actually handed out are the thing checked.
  - A seed can be outside the envelope itself. `#7E57C2` is an ordinary purple
    that lands darker than any wheel that ships, and every wheel of the chain
    came out the identical colour. It is not refused — "pick another one" is a
    poor answer to a child who picked this one — the anchor is slid to the
    nearest lightness that works and the console names both hexes.
  - Taking the chroma fraction at the colour as written rather than at the slid
    anchor turned a pale cream into a saturated amber: near white the gamut is
    narrow, so a faint chroma is a *large* fraction of it.

  A seed at or below the chroma the background machinery is drawn at (0.0181) is
  refused outright: the bridge idlers are grey, and a chain that grey reads as
  structure rather than as somebody's — the #65 blank-gear defect arrived at from
  the other side. A seed paler than the palest wheel that ships is lifted to it.
  A named CSS colour is refused with a message: `rgbOf()` is the one parser here,
  and a format it cannot read is one that cannot be taken into OKLab at all.

  `FLAT_INK` moved up beside the palette because the legibility envelope is now
  its earliest reader, and the engraving's opacity became `ENGRAVE_ALPHA` rather
  than a literal in two places that could drift apart. `MIN_HUE_SEP` is named
  rather than a bare 40 for the same reason.

  Gates: 74/74 suite (five new), `a11y_audit` PASS in both themes,
  `verify_motion` PASS. Photographed as a sweep — seven seeds and the pool deal,
  the same machine under each, both themes, plus one seed at 4, 7, 10 and 14
  wheels so the floor can be seen running out.

- **#89 — a crawl policy, because a 403 was standing in for one.**
  `https://wozi.com/robots.txt` returned the raw S3 `AccessDenied` XML: the file
  did not exist, was not in the deploy whitelist, and no `<meta name="robots">`
  said anything on the site's behalf either. That is not "no policy" in any
  useful sense — a crawler that cannot read a robots.txt takes the site as
  unrestricted and proceeds, so the site had a policy all along and it was
  whichever one each crawler defaults to.

  The file allows everything, in four lines of directive and a comment block
  explaining why. Each decision was available to go the other way:

  - **Indexed, not `Disallow: /`.** It is a personal landing page whose whole
    job is to be the thing found when somebody looks up the name, and it carries
    a signed ownership proof that is worth nothing unreachable. De-indexing a
    site is also asymmetric to undo — dropping out of an index is quick and
    climbing back in is not — so the reversible answer is the one to ship while
    nobody has argued for the other.
  - **No `Sitemap:` line.** There is no sitemap. Pointing at a URL that 404s
    teaches a crawler the file is unreliable, and a sitemap for a single page is
    a second copy of a fact the page already states.
  - **No named AI-crawler blocklist.** Declined deliberately, and it is one line
    to add if the view changes. A list of agent tokens is a maintenance-bearing
    artifact that is stale the day after it is written, it is exactly as
    advisory as the rest of the file, and there is nothing on this page it would
    be protecting: nine SVG gears and a link table pointing at profiles that are
    already public. Blocking a crawler that honours the request while the ones
    that do not carry on is a gesture, and gestures in a policy file get
    mistaken for guarantees later.
  - **Nothing said about `cards/`, on purpose.** Both card pages already carry
    `<meta name="robots" content="noindex">`, which is the stronger instrument
    here rather than the weaker one: `Disallow` stops the *fetch*, so the
    crawler never reads the `noindex`, and a URL it is forbidden to fetch can
    still be listed bare from an inbound link. Blocking the crawl would be worse
    at keeping the page out of an index than allowing it. And `robots.txt` is
    world-readable, so naming a path advertises it — a line pointing at the one
    directory carrying a real address and mobile number, in the first file every
    scraper fetches, is a signpost rather than a fence.

  **This changes nothing about harvesting, and the file says so.** `robots.txt`
  steers well-behaved indexers; address harvesters ignore it. The live
  `mailto:` links on the combined stage are exactly as exposed as they were
  yesterday. Keeping that distinction visible is why the file's own comment ends
  by disclaiming it — a crawl policy that reads as an anti-scraping measure is
  worse than none, because it invites the belief that something is protected.

  Published under its own deploy step with an explicit `text/plain;
  charset=utf-8` — a robots.txt served as `text/html` is ignored outright by
  Google — and `max-age=300` to match the other mutable objects rather than the
  86400 the assets get, so that changing a crawl decision is never stuck behind
  a day of edge cache.

  Three live assertions, and **all three were proved able to fail** rather than
  merely observed green, by lifting `check`, `check_content_type` and `exact`
  verbatim out of the workflow and running them against a local origin under
  four states. Missing object: all three fail (the #74 state exactly). Correct
  object: all three pass. Published without `--content-type`: the content-type
  check fails **alone**, the other two passing. A stale object serving
  `Disallow: /`: `exact` fails **alone** — still 200, still `text/plain`, still
  containing `User-agent: *`, which is the whole reason the byte-identity check
  is there and not just a status check. That last state is the expensive one, so
  it is the one worth having a gate for.

  `CLAUDE.md` gained `robots.txt` in the published list — omitting it would have
  been #59 exactly, the rulebook requiring a file the rulebook does not name —
  and a section stating the per-page-`noindex` rule, since the reasoning for a
  file whose most important content is what it deliberately does not say cannot
  live in the file itself.

- **Harper's chain.** A second person in `config.js`: `harper`, one link,
  `mail` → `harper@wozi.com`. `harper.wozi.com` is listed as a host before it
  resolves, which costs nothing — a hostname matching nothing simply never
  selects the chain, and `?who=harper` reaches her either way. Making it live is
  an ACM SAN in us-east-1, an alternate domain name on the distribution and a
  Route53 alias; no deploy change.

  The person picker appears by itself at two people, as designed — both entries
  render in the corner menu with `aria-current` set. Charles remains `PEOPLE[0]`,
  so the default page is unchanged, and the pixel gate agrees: **0 px differ**
  against HEAD at 1440×900 and 390×844.

### Fixed

- **#101 — the gear menu named the mechanism instead of the thing being chosen.**
  (GitHub #91.) The first entry read `Mixed deal (default)` while every other entry in
  the list is a plain family name — `Isogrid`, `Radial brickwork`, `Radial isogrid` — so
  "deal" was the one word describing how the wheels are picked rather than what you get.
  Now `Mixed (default)`.

  The `(default)` marker stays. It is the only thing in the menu that says which entry
  you get without asking, and it is what `aria-current` is paired with, so dropping it
  would take information out of the accessibility tree as well as off the page.

- **#98 — one name was doing two jobs: a maximum was being used as an index.**
  `SPINE_LEN` was `Math.max(1, ...STAGE.people.map(p => p.links.length))` — the
  longest chain *anywhere on stage* — and the `TRAIN` builder then used it as a
  **wheel index into the spine**, `Math.floor((SPINE_LEN - 1) / 2)`, to seat the
  default bridge anchor. Those two quantities agree only while the spine *is* the
  longest chain, which today's `CHAIN_ORDER` sort happens to guarantee. The
  guarantee lived in a different declaration from the index it was propping up,
  which is the whole of the defect: nothing at the point of use said what it
  depended on, and the thing it depended on was free to change.

  Found while reading #85, which proposes **declaring** the chain order instead
  of inferring it from link count. **That design fork is not decided and nothing
  here decides it** — the sort is untouched, no config key was added, and the
  suite's deliberate `CHAIN_ORDER is not longest-first` assertion still runs
  against its three-chain fixture at both stage rotations. Only the latent bug
  is fixed, because a declared order is exactly what makes a short spine
  reachable and the fix is a prerequisite either way.

  The two quantities are now named apart and each derived from what it actually
  means:

  - **`SPINE_LEN` — how many wheels the spine has.** `SPINE.links.length`, where
    `SPINE` is the first chain in `CHAIN_ORDER` that `HAS_WHEELS`. It is a count
    of one chain, never a maximum, and it is only ever used to index that
    chain's own wheels.
  - **`NOMINAL_CHAIN` — the longest chain configured anywhere.** Unchanged, and
    already sitting further down the file: it is the maximum-shaped quantity,
    and the one that genuinely sets the SCALE (`NOMINAL_SPAN` derives from it,
    `TARGET_GEAR_PX` from that). It ranges over every configured person rather
    than the stage precisely *because* it indexes nothing — a solo page has to
    draw its wheels at the size they have on a chain that is not on stage to be
    measured.

  The index is now in range **by construction rather than by a promise made
  elsewhere**, and the argument is local to the line: the emitter skips chains
  with no wheels and emits `SPINE` first, `SPINE` is the first chain in that very
  order with wheels, and the spine is unbridged so it takes no idlers — its
  wheels therefore *are* `out[0 .. SPINE_LEN-1]`. Half of `SPINE_LEN-1` lands on
  one of them whatever the order is sorted by. The "a chain with no links is not
  laid out" rule got one home, `HAS_WHEELS`, since the spine is defined by it and
  two copies of that test is how the emitter and the spine would come to disagree.

  **Proved by construction rather than asserted.** The new test hands the real
  `TRAIN` builder a layout order the page's own sort would never produce — a
  two-wheel spine with a seven-wheel chain behind it — which is the shape #85
  would make legal. The suite's `buildTrain` grew an optional order for this, and
  substitutes *only* `CHAIN_ORDER`; `SPINE` and `SPINE_LEN` are still the page's
  own lines deriving their own answer from it. Against the old derivation the
  test fails, with the anchor landing on the bridged chain's own idler and
  forward-referencing a wheel that is not placed yet:

  ```
  FAIL  the static tree's default bridge anchor is a spine wheel, whatever the layout order
        long's bridge defaults to wheel 3, which is a ghost idler -- the spine is wheels 0..1
        long's bridge defaults to wheel 3, which is not placed when idler 2 asks for it
  ```

  Against the new one it passes, with the anchor at wheel 0. The fixture also
  checks *itself*: it asserts the discarded `max`-over-stage index would have
  been out of range, so the test cannot quietly stop exercising the bug.

  **Nothing on screen moved, and nothing was ever going to.** `solve()`
  overwrites this parent with whatever it finds room for before a wheel is drawn,
  so this is the *static* tree only — but a malformed static tree is exactly what
  #65 was, and the failure mode is silent: `solve()` reads `g[t.parent]` out of
  the wheels it has already placed, so a forward reference reads `undefined` and
  the branch lands wherever the last iteration left it.

  Gates: **70/70** suite (69 baseline plus the new test), devices **24/24** and
  **4/4**, motion PASS (39 of 39 elements advanced, no strands, which is correct
  for the direct-mesh train). The pixel gate is the one that matters for a
  renaming: **0 px** against HEAD at 1440×900 and 390×844, on `?who=charles`
  *and* on the combined stage. On today's config the new derivation and the old
  one compute the same number, so identical output is the expected result and not
  a lucky one.

- **#92 — flicking a hub cap off its axle ate the next click on that cap.**
  (GitHub #56.) Pull a cap off, let go while the hand is still moving, then come
  back and click the link underneath: nothing happened. Once, silently, and only
  for the cap that was thrown.

  **The suppression flag outlived the gesture that set it.** A drag ends in a
  `click`, and that click must not navigate or be counted as an outbound visit,
  so `up()` records `_badgeMoved` and the anchor's `clickGuard` cancels the click
  it finds waiting — clearing the flag as it goes. `clickGuard` was the only
  thing that ever cleared it, and it only runs when the browser fires `click`
  **on the anchor**. The cap follows the pointer a frame behind, so a release
  taken mid-movement lands on empty stage rather than on the cap; Chrome then
  sends the click to the common ancestor of press and release, the guard never
  runs, and the flag survives. The next real click on that badge was spent
  clearing it instead of following the link.

  That is not an edge case — the cap is deliberately a magnet you can pull all
  the way off, ever since the asymptote that used to stop it at about three of
  its own widths was taken out, so letting go out in space is the ordinary way
  to put one down. The
  slow, careful release is the one that happens to work, because the cap has
  caught up and is still under the pointer.

  **The flag is now cleared where it is armed**, on the press, first thing in
  `badgeGrab`. The issue offered a second option — stamp the flag with a
  timestamp and ignore it after about 300ms — and that is a tuned constant nobody
  could re-derive later, wrong for any hand that pauses before clicking and
  wrong again on a slow frame. Clearing on the press needs no window at all,
  because every genuine click begins with a primary pointerdown on the same
  anchor: by the time a click could be swallowed, the line has already run. It
  clears unconditionally rather than only for its own key, since only the gesture
  in progress may suppress anything. `preventDefault` in `badgeGrab` is untouched
  — it is what stops the browser's native link-drag from hijacking the pointer
  stream — and the flag is still the composite `badgeKey` of #86, not a bare slug.

  **The gate can fail, and was made to.** `tools/cap_drag.py` grew a third phase
  that performs both gestures and then clicks for real, reading
  `event.defaultPrevented` from a `document`-level listener that runs after
  React's delegated handler — what a person calls "the link did nothing", asked
  of the browser rather than of the component's private state. Against a
  throwaway worktree at `ff3cb07` it exits **1**: *flick, release mid-move →
  somewhere else, allowed through; then a genuine click → on the cap,
  swallowed.* With the fix it exits **0**, and the same run still asserts the
  original guarantee — a drag that does end on the cap is suppressed, so a drag
  is not counted as an outbound visit. A flick that fails to release off the
  anchor is itself reported as a failure, because a phase that cannot reproduce
  its own gesture has proved nothing.

  Also gated: 69/69 suite, `verify_motion` PASS (35/35 advancing, badge offsets
  ≤0.01px), `a11y_audit` PASS in both themes, pixel gate **0px** at 1440×900 and
  390×844 on `?who=charles` — this change draws nothing.

  **What none of that proves.** Synthetic CDP input has now hidden three pointer
  bugs in this file, and the reason is in `cap_drag.py`'s own header: press and
  move arrive in the same task with no frame between them, which a hand can never
  do. The new phase leans on exactly that asymmetry in reverse — it needs the cap
  to be *behind* the pointer at release, and it gets there by dispatching the
  last move and the release with no frame in between. A real hand achieves the
  same thing by moving fast, which is a different mechanism producing the same
  geometry. Final confirmation is a person, a real mouse, and a cap thrown across
  the stage.
- **#91 — an escape run wandered off its own line, and the wander grew with the
  run.** Charles, looking at a 5120px-wide screen: the ghost runs should follow
  the chain's centre line more closely.

  The wobble was already dealt around the run's own bearing rather than the
  previous wheel's, so the ANGLE never accumulated. The POSITION did. Every step
  displaces the run sideways by `d * sin(wobble)`, and those sum as a random walk,
  so lateral drift grew with the square root of the run's length. Invisible while
  a run was seven wheels; #87 made the length a function of the viewport, so on an
  ultrawide a run is seventeen wheels and left its line by **207px** — on a stage
  1440px tall. The fix made the symptom worse before anyone saw it.

  **Each step now aims back at the axis before it wobbles.** Solving for the
  bearing that lands the next centre back on the line and dealing the wobble
  around THAT turns the walk into a contraction: the offset after a step is
  `off * (1 - cos w) + d * cos(correct) * sin w`, and a coefficient under 1 on the
  carried term is the whole difference between drift that accumulates and drift
  that is bounded.

  Four rules were photographed side by side, two seeded loads each, at two widths.
  Peak excursion from the run's own axis:

  | | 2560x1440 | 5120x1440 |
  | --- | --- | --- |
  | shipped — free wobble | 148px | **207px** |
  | alternating signs | 62px | 119px |
  | **steer home** | 55px | **59px** |
  | steer home + alternating | 54px | 60px |

  The column that decides it is the second against the first, not either alone.
  The first two GROW with the run (8 wheels per run at 2560, 17 at 5120); the last
  two are flat. Since the length now follows the viewport, an unbounded rule keeps
  getting worse on wider screens.

  Alternating the wobble's sign — the chain's own rule — halves the drift at 2560
  and looks like the answer, then gives most of it back at 5120: decorrelating the
  angle leaves the magnitudes free, so the position still walks. Steering plus
  alternation is statistically identical to steering alone (60 vs 59), so the
  simpler mechanism wins, and it keeps the uncorrelated wander that gives the runs
  their character while removing only the accumulation.

  Two corrections came with it, both of the same family as #87:

  - **The progress sum was projecting the wrong angle.** It read `cos(wobble)`
    while the step was taken at `wobble`, which agreed only while those were the
    same angle. Steering added a term to the bearing without touching that line,
    so the projection would have silently stopped matching the step — and it
    over-credits, which is the direction that stops a run short. It projects
    `ang - e.ang` now, the whole deflection by construction.
  - **The iteration backstop assumed the widest off-axis step was the wobble
    alone.** With steering it is the wobble plus the largest correction, and that
    is derivable rather than measurable: the offset contracts to `d * tan(w)`, so
    the largest correction is that over the shortest centre distance. The bound
    stays an upper bound instead of quietly becoming an estimate.

  Coverage is unchanged — reaches both edges on every load at every width tested,
  0px shortfall, no new console warnings.

  **Found while measuring, and it changes what the drift means:** `fitEscapes`
  resets `this._seed` on entry (`index.html`), so the ghost wobble stream is
  identical on every load. The drift figures came out bit-identical across two
  genuinely different deals. The wandering was not an unlucky deal anyone could
  reload away — it was the shape, every time, at a given viewport.
- **#90 — the scribed datum showed through every background wheel, and paint
  order was never the reason.** (GitHub #81.) The line and its ticks ran
  unbroken across the ghost runs at any wide viewport, which reads as an overlay
  laid on the drawing rather than as the reference a fitter follows along a bed.

  **The obvious diagnosis was wrong, and it was written down before it was
  checked.** The issue said the ghosts were a separate layer painted after
  `gearArt`, so the datum — first child of `gearArt` — necessarily sat in front
  of them. Hit-testing the shipped page at six points where a datum line crosses
  a ghost body says otherwise: `elementsFromPoint` returns the ghost first and
  the datum line fourth or fifth, at every one. The mark was already **below all
  24 of them**. Both are children of `gearArt`, both carry `z-index: 0`, and the
  datum is written first.

  **What it actually is: an occluder at 0.17 does not occlude.** The ghost layer
  carries one `opacity` for the whole background assembly. Anything inside that
  group paints at full alpha onto the group's surface and the alpha is charged
  once, at the end — which is exactly why ghost wheels have always hidden *each
  other* cleanly. The datum was the only part of the assembly standing outside
  the group, so it was the only part nothing could cover: measured off the
  shipped page, a hairline crossing a wheel body kept **83%** of its weight,
  i.e. was attenuated only by the wheel's own transparency. Below in paint order
  and visible through the thing above it are not a contradiction.

  **The fix is to move the mark inside the group, first child**, where the
  wheels' real silhouettes cover it — teeth, gaps and all, with no mask, no
  circle approximation and no geometry duplicated out of `ghostSvg`. Three
  things had to be paid for:

  - **The alpha it lost is spent on ink instead.** Inside the group the mark can
    only be drawn at `ghostOpacity()`, and `datumOpacity()` had solved for a
    different number — 0.28 against the ghosts' 0.17 on dark, because a hairline
    does not survive dimming the way a filled body does. Compositing is linear
    in sRGB values, so `ink = bg + (datumOpacity / ghostOpacity) × (token − bg)`
    drawn at the group's alpha lands on the tone the solve asked for; on dark
    that lifts `--muted` to `rgb(223,250,244)`. Photographed, the two agree to
    within **2/255** on every channel off a wheel, which is rounding rather than
    a change in weight. In light the two alphas are the same number by
    construction, the ratio is exactly 1, and `datumInk()` hands the token back
    unchanged. **Nothing was re-dimmed to fake depth** — that would have traded a
    paint bug for the legibility one #61 and the mock already settled.
  - **The layer's box has to hold the mark too (#21).** It is the element
    carrying the opacity, so WebKit rasterises the group at *its* box while Blink
    takes the union of its children — and a datum runs past the wheels on
    purpose. `datumLayer()` now returns its bounds and the layer is widened to
    contain them. The *wheels'* union is settled first and never widened
    afterwards: the line is run to the edge of that box and a little past, so a
    box that had already grown to hold the line would push the line out again.
  - **The parallax transform moved down to the wheels alone.** The datum's
    stations mark the centres of linked wheels, which are drawn at the train's
    scale; scaling the mark 0.94 with the far plane would slide every station off
    the wheel it points at. An inner div now carries the `scale(0.94)` and the
    pointer drift, and holds `_ghostLayer` — a transform does not force a
    subtree to composite separately, so the wheels still paint over the datum at
    full alpha. `parallax` is off by deliberate default, so this is latent either
    way; it is fixed rather than introduced, since the mark and the wheels it
    references had never travelled together.

  **What this does not cover, and cannot.** A bridge idler is a ghost drawn in
  the chain layer with the same alpha applied *per wheel* — it cannot live in the
  ghost layer because it has to mesh, and that layer is parallax-scaled. Each one
  is therefore its own translucent group, and no stacking arrangement makes a
  translucent element occlude anything. The datum still shows through the bridge
  idlers, and only through them: a handful of wheels in the column between two
  chains, against 24 in the background runs. Fixing that means masking or
  pre-blended fills, which is a different change.

  Measured on the combined stage at 2560×1440, one seed, one load:
  **2,881 px** differ on dark and **2,266 px** on light, max channel delta 29 and
  30 — all of it the mark disappearing under wheels. The shipped fix is **0 px**
  against a live mock of the same idea injected into the unmodified page, which
  is what says the implementation does what the experiment did. Gates: suite
  **69/69**, devices **24/24** plus safe-area **4/4**, motion **PASS**, and
  `pixel_regress --query '?who=charles'` **0 px** against `main` at both
  viewports — a solo page draws no datum, so the single-chain path had to be
  untouched, and it is. The three fixed controls and all eight badges still
  hit-test **on top** with the layer's box widened.

  Two assertions in the suite moved with it, and both now assert the real rule:
  the datum must be the **first child of the layer that carries the ghost
  opacity** rather than merely the first thing `gearArt` paints, and the ink
  conversion is checked numerically in both palettes — every channel must
  composite at the ghost alpha to what the token reaches at the solved one. The
  suite's slice of `datumOpacity()` was also bounded at `datumInk()`, since the
  new method divides by `ghostOpacity()` on every path and the old bound would
  have read that arithmetic as the previous method's fallback.

- **#88 — the device gate's verdict was a property of whichever machine it
  happened to deal.** Found by CI failing #87 on two rows that pass ten times
  running locally, at a gear of 215.4px against a 222px standard.

  Every wheel on this page is dealt at random, and `tools/devices.py` navigated
  once per profile and judged what it got. Two things followed from that, and the
  second is the one that matters:

  - **The deal is now seeded, one fixed seed per row.** Same LCG and the same
    reasoning as `tools/pixel_regress.py`, injected over CDP so no test hook
    reaches the shipped page, and read from the URL so each navigation names its
    own. Breadth is not lost — 24 rows still exercise 24 different machines, but
    the same 24 every time. A flaky gate is worse than a narrow one: it teaches
    everyone to re-run until it passes, which is how a real failure gets waved
    through.
  - **The gear bound was comparing two different quantities.** It measures the
    *largest wheel the deal produced* and bounded it against `TARGET_GEAR_PX`,
    the size the fit aims that wheel at — but the deal does not always reach
    `TEETH_MAX`, and one tooth short is a wheel `1/(TEETH_MAX + 2)` smaller,
    about 4.8%. The flat 2% tolerance sat inside that, so the bound failed pages
    that had done nothing wrong, and which rows failed depended on the deal. The
    slack is now derived from the tooth pitch, which says exactly what is being
    allowed — one tooth of deal variance and not a pixel more — rather than
    naming a percentage somebody has to re-measure when the deal's range moves.
    `TEETH_MAX` is read out of `index.html` beside `TARGET_GEAR_PX`, for the same
    reason.

  This is the third time in this file that a bound has been wrong because nobody
  said *which* measure it was on: the linked span had three datums 15 points
  apart, the ceiling of 0.88 could never be crossed, and now a bound on the mean
  wheel was being applied to the largest one.

- **#87 — the escape runs stopped short of the edges, and the gate that was
  supposed to say so had been pointed away from the widths where it happened.**
  (GitHub #80.)

  `fitEscapes` grew each run until it was off the edge *or* it had placed seven
  wheels, whichever came first. The seven was a backstop, and while a wheel's size
  tracked the long axis it never bound: a wider window dealt bigger ghosts, so
  seven of them always got there. #85 gave a gear a standard size instead, and
  from that moment the same seven wheels covered the same ground whatever the
  window was. At 5120×1440 the runs ended 532px and 637px inside the two edges,
  leaving a band of bare page at each end of a machine that is meant to read as
  continuing past the frame (#10).

  Three things changed, and only the first is the bug:

  - **The wheel count is derived from the distance.** The shortest step the loop
    can take is two minimum wheels in mesh, foreshortened by the widest wobble it
    may deal; the run needs `span + 120`. The ratio bounds the iterations, so the
    backstop cannot be reached before the edge is. It is an upper bound on what
    the arithmetic can need rather than a number anyone picked, which is the whole
    difference between this and what it replaced.
  - **The run's wheels are dealt like the chain's**, uniform over
    `[TEETH_MIN, TEETH_MAX]`. They used to ramp — `11 + k * 2`, capped at 26 —
    growing as the run went out and past the chain's own maximum at that. It was a
    second sizing philosophy inside a machine whose premise is that sizes are
    random, and it existed only to keep runs short enough for the cap. With the
    count derived, a run can be as long as it needs and these can be wheels like
    any other.
  - **Progress is measured along the run's axis, not as the length of the step.**
    `span` is measured straight down the escape bearing, so a step taken `wobble`
    degrees off it advances the run by only its cosine. Summing raw centre
    distances credited the run with ground it had not covered — and always in the
    same direction, since cos is at most 1, so the error could only ever stop a
    run short.

  **The gate read 20/20 throughout, and the reason is worth more than the fix.**
  Not a wrong measure and not a settling race: 3440 and 5120 had been commented
  out of `tools/devices.py`'s device list during the #2 work, because they failed
  a coverage check whose answer — how many more wheels an empty edge is worth
  against the per-SVG frame cost of #6 — was Charles's to make and would have
  blocked every deploy while it stayed open. The two widths where the page failed
  were the two widths the list did not contain. A gate is only ever green about
  what it was pointed at.

  Both rows are back, and proven able to fail: against the pre-fix tree the suite
  reports **22/24** with 5120 short by 532px and 637px in portrait and 516px and
  623px in landscape; against this one, **24/24**. Measured over 8 loads a width,
  5120 went from 0/8 reaching to 8/8, and every width from 1440 to 3440 reached
  both before and after.

  The frame cost that made this a question in the first place came in at nothing
  measurable: 31 → 59 wheels at 5120, median frame time flat at the 16.7ms vsync
  interval and p95 17.3 → 17.5ms. That is headroom being spent, on a fast machine
  in headless Chrome — hopefully it holds up on weaker hardware, which this cannot
  prove.

  One thing found on the way and fixed with it: the assembly extent was the union
  of every `<svg>` on the page wider than 30px, which let the page's *container*
  elements answer a question about paint. The largest is the full-stage `chains`
  svg — `solved.w * S` across, drawing nothing at all while no drive strand is
  enabled, and at 5120 it measured about 40px wider than the outermost wheel. It
  was not why this gate passed, but a coverage measure that an empty box can
  satisfy is one edit away from being exactly that. It measures wheels now.

- **#86 — a hub cap knew which service it was, but not which of two it was.**
  (GitHub #78.) Dragging Charles's `mail` cap threw Harper's out to arm's length,
  and hovering either one lit both and opened both pills.

  Every map behind the magnetic caps — the spring entries `_badgeOff`, the
  element references `_badgeEl`, the drag claim `_badgeDragging`, the click guard
  `_badgeMoved` and `state.hover` — was keyed by service slug. A slug names a
  *service*, and that was unique only for as long as one chain was ever on stage;
  the combined stage put two `mail` wheels up and the key stopped telling them
  apart. `_badgeEl` was the sharp end: one element per slug, so the second badge
  to register overwrote the first, and the spring then animated the pressed cap
  while both read one shared offset. Nothing visibly moved on the far cap during
  the drag — it simply held its last render — and then the `forceUpdate` on
  release handed it that shared offset and it jumped, measured at **91.4 px** out
  and sitting there while the near cap sprang home.

  Identity is now `badgeKey(person, slug)` everywhere the question is *which of
  these caps is this*. It is deliberately **not** used where the question is
  *which service is this* — `SITES[person][slug]`, the icon, `BRAND`,
  `PILL_STACK`, the pill's own label, the outbound counter — because those are
  per service by design and were already right; keying them by person would trade
  a drag bug for missing icons and flat brand colours.

  `tools/cap_drag.py` had exercised dragging since the caps were built and could
  never have caught this: it worked one chain, where the slug *is* unique. It now
  runs a second phase that finds a service two chains carry, drags one and
  measures the other — far cap **0.0 px** through the drag, through the release
  and after the spring settles, and **+0.0 px** wide while the near one opens by
  44. The suite gained the static half: the real `badgeKey` sliced out of
  `index.html` must be injective over every configured (person, service), *and*
  some service must actually be on two chains — without that second assertion the
  first goes quietly vacuous the day the config stops sharing one. That the
  render sites ask `badgeKey` the question rather than passing a bare slug is
  behaviour, and is checked in a browser rather than by grepping the source.

- **#84 — the datum was laid at the tilt the deal happened to hand it, and stood
  off its chain by a distance nothing bounded.** (GitHub #76.) Two faults
  stacking into one complaint: the line reads as askew to a chain the eye reads
  as travelling straight.

  `chainAxes()` measures each chain head-to-tail, and a dealt serpentine's ends
  rarely land level — the bearings come out of `[ANG_MIN, ANG_MAX]` with
  alternating signs, and only the *band* and the *end-to-end drift* are capped,
  never the end-to-end *angle*. Measured unseeded, the datum came out up to
  **1.84° off horizontal at 1440×900** and **2.3° off vertical at 390×844**,
  differently on every load. It now publishes **two** named directions instead of
  one: `deg`, the chain's own measured axis, which is what an escape run
  *continues*; and `travel`, the stage's axis, which is what a scribed reference
  is *laid along*. Both come from the one function — the #67 rule against a
  second copy is kept, and what was forked was the question, not the derivation.
  Across 80 unseeded loads the mark now reads **exactly 0.000° / 90.000°**.

  The stand-off was a flat module of *solve* units, so it grew with the render
  scale: at the fit a 1440-wide window deals, the plate's outer edge stood
  **20.6 rendered px** off the chain's extreme border, and at 3440×1440 nearer
  49. Charles's rule — *"put the datum straight along the side such that the top
  of the label box is no more than 20px outside the extreme border of the side"* —
  is now `PLATE_TOP_CLEAR`, the one figure on this page stated in **rendered
  pixels** rather than in modules, and `datumClear()` pays the plate's own
  half-height out of it before handing back the air that is left. It is a
  ceiling, not a target: wherever a module of air fits inside the figure, a module
  of air is what the mark gets.

  Past a render scale of about 2.86 the plate's half-height alone has spent the
  whole figure and no non-negative air satisfies it. The mark then stands as
  close as the geometry allows — outer edge ~24 px rather than ~48 — and the
  scribe grazes the deepest tooth tip. A real change of look on an ultrawide,
  taken deliberately and stated in `datumClear()`, not discovered later.

  Re-measured on the **stroked** extent, because the offset moved: 0 clipped
  across 80 unseeded loads, worst margin **3.49 px** at 1440×900 and **2.20 px**
  at 390×844. `?who=charles` is **0 px** against `439c9ba`. The new suite case
  asserts parallelism and the bound over 144 dealt trains at three render scales,
  and fails on both halves of the old behaviour.

- **#83 — the cast-shadow derivation was claimed but never executed, and two
  same-named buttons slipped past the duplicate-name check.** The opacity test
  re-asked `wheelOpacity()` instead of running the render's own
  `filter(g => this.wheelOpacity(g) == null)`, so the claim that the shadows
  *derive* from the opacity rule was untested; the filter callback is now sliced
  out of `index.html` and run, and fails both on `g => true` and on
  `g => g.role !== 'idler'` — right answer, wrong derivation. `a11y_audit` keyed
  each focusable on `href || tagName`, so two `<button>`s with one name compared
  equal; anything without a destination now keys on the element.

- **#82 — a mirrored datum struck its ticks into its own wheels.** Ticks run
  along the normal at `+MAJOR`, and the mirrored origin reverses which way that
  points. A major tick is 1.2 modules against one module of clearance, so a
  mirrored chain's ticks crossed the clearance and vanished under its own gears —
  the mark reading inverted and short beside an unmirrored one. `plateSeat()`
  returns the side with the origin, and every tick is struck at `out * MAJOR`.
  Invisible to the seeded gate, because the mirror only fires on deals that seed
  does not produce.

- **#81 — the plate was seated flush, against a box that could move underneath
  it.** Two faults, and only measurement separated them. The clamp bounded the
  *geometric* rectangle while the body is stroked `HAIR` wide down its centre
  line, so half that stroke hung outside — and the sweep measured the same
  rectangle, so it could not see the overhang either. The seat now carries
  `max(PLATE_H * 0.1, HAIR / 2)`: the plate's **own corner radius**, floored at
  exactly the stroke's overhang. Both are read off marks already drawn.

  The margin alone was not enough, and a probe that walks the viewport a pixel at
  a time without navigating proved it: `_vpBox` is published from `fitEscapes`,
  but a render only happens when something *quantised* moves, so the stage
  re-centres underneath a seat that was computed against an older box. Measured,
  that put the mark **1.32 px off the left edge at 390×844**. `fitEscapes` now
  re-renders once the stage has drifted past the margin's real clearance —
  a threshold asked of `plateMargin()`, not restated.

  The first attempt compared consecutive `fitEscapes` calls, which compares one
  step of a drag: forever under the threshold while the total runs away, and it
  made 1440×900 strictly worse at **22.91 px past the fold**. `_vpSeated` is
  stamped in `componentDidUpdate`, the one moment a render is known to have
  finished, so the whole distance since the seat is what gets measured. Guarded to
  the combined stage, so a solo page keeps the render schedule it had.

  Re-measured on the **stroked** extent: 0 clipped of 2,720 measurements across a
  40-load unseeded sweep and a 2,560-step one-pixel resize walk, worst margin
  0.30 px inside the edge.

- **#80 — `CLAUDE.md` described an attachment search that does not exist, in the
  section added to close the #59 class.** It said the search "*prefers a clear
  band of the cross axis and rejects every anchor that does not give one*".
  `search()` has no cross-axis band test: it rejects on foul, pass-over and
  bridge-crossing, and the cross axis is bounded elsewhere, by `idlerCount()`. The
  neighbouring paragraph about the search's refusal-to-refuse was accurate
  throughout, which is what made the wrong sentence read as checked. Rewritten to
  what the code does.

- **#79 — the datum plate's font stack named no face a Windows machine has.**
  `ui-monospace, Menlo, 'DejaVu Sans Mono', monospace` covers Apple and Linux and
  falls through to Courier New everywhere else — a lighter, narrower face at the
  same size, on the one mark that carries the identity and already the smallest
  lettering on the page. `Consolas` is now in the stack, ahead of the generic.
  The plate's *size* is untouched and is Charles's call: it measures 4.8 px at
  320×568, 7.5 at 390×844 and 12.5 at 1440×900, against tick numerals that were
  dropped at 4.4/6.7/11.4 for being illegible.

- **#78 — `idlerCount()` measured a different window from the `axisRot()` it
  defers to.** It read `visualViewport`; the rotation reads
  `innerWidth`/`innerHeight`. The two differ exactly when the iOS toolbar
  collapses, which is the moment the fit re-runs — the same disagreement #67's
  fix removed, arriving by a second route. Near-miss rather than a live fault at
  390×844, and free to make consistent: one measurement now feeds both halves of
  one decision.

- **#77 — four "invariant" tests asserted source text, so the guard the ledger
  cited as proof was not a guard.** The person-picker test was two regexes over a
  slice of `index.html`: move the live condition into the comment beside it and
  the suite stays 65/65 while the disclosure defect ships. The idler-count,
  ghost-opacity and escape-run tests were the same shape. All four now **execute**
  the page's own functions — `togPeople` against a synthetic `CONF` and `STAGE`,
  `idlerCount()` with the rotation forced so the test can tell whether it is
  listening at all, `wheelOpacity()` in both themes, and the real `fitEscapes` via
  the `fitEscapesOn` harness that already existed. Each was checked by mutating
  `index.html` and confirming it goes red; each carries its own non-vacuity
  assertion.

  The opacity rule got a name to be asked by: `wheelOpacity(g)`, which the cast
  shadow layer now derives from instead of testing `role` a second time — "a
  wheel drawn at reduced weight casts nothing" in one place.

- **#76 — the last unguarded `SITES[g.person][g.slug]`.** Four other derefs
  guard; `engraving()` did not, and it runs inside the render, so a person with no
  table at all is a blank page rather than a missing engraving. That is #53's
  exact failure mode. Unreachable with today's config; guarded anyway.

- **#75 — the colour deal was sized before the idlers existed.** It was dealt over
  `TRAIN.length`, which counts the bridge idlers — whose colours are then thrown
  away and overpainted from `GHOST_COLORS`. So the deal spent pool entries on
  wheels that never wear them (the *links* run out first when the train grows),
  and a chain head arriving over a bridge was hue-scored against a colour nobody
  draws. It is now sized and scored over the linked wheels only, and a head past a
  bridge is scored against nothing at all — honest, because a whole idler of
  background palette stands between it and the nearest coloured wheel.

  `dealColours` also repeats its shuffled pool when there are more wheels than
  colours, so those slots are inside the scored array. The call site used to close
  that gap itself with `WHEEL_DEAL[i % len]`, which handed out colours the 40°
  rule of #12 had never looked at. `WHEEL_POOL` is 10 and the train is exactly 10
  today: one more link and it would have wrapped.

- **#74 — two focusable links shared the accessible name "Mail".** New with the
  combined stage: two people, two mailboxes, one string. The only differentiator
  was the datum plate, which lives inside the `aria-hidden` gear art. `a11y_audit`
  passing was not evidence — it counted *unlabelled* focusables, not ambiguous
  ones. On the combined stage a badge is now named `"<service>, <person>"`, using
  the same name the plate is stamped with so the audible differentiator and the
  visible one are one string. The solo page is unchanged, and the visible pill
  still reads the service alone — a prefix of the name, which is what WCAG 2.5.3
  asks. `a11y_audit` grew a duplicate-accessible-name check (same name, different
  destination) and was confirmed to go red on the unqualified label.

- **#73 — the datum plate fell off the viewport on a random fraction of loads.**
  `datumLayer` runs *after* `fitStage`, so the plate sat outside all three limbs
  of the fit: `WHEEL_CROSS_MAX` bounds a wheel, `CROSS_BLEED` bounds the band, and
  both deliberately let the machine bleed past the cross axis — which is the edge
  the mark then went over. Measured unseeded over 20 loads per viewport: **2/20**
  put Harper's plate at y 913–930 against a 900 px viewport at 1440×900, and
  **1/20** put it at x −18…−9 at 390×844. The seeded pixel gate structurally
  cannot see it; it photographs one deal.

  `datumRuns()` already said "off the page is invisible, and invisible is the one
  thing this mark may not be", and nothing enforced it. It now hands over **both**
  origins — a scribed datum may be laid either side of the parts it references,
  and both clear every tooth by the same module of air — and `plateSeat()` spends
  the two freedoms a datum actually has, in order: which side, then which station
  along it. The natural side and the natural station win every tie, so a load that
  was already right is untouched, and the smaller slide wins otherwise. Neither
  side fitting is a `console.warn`, not a silent give-up.

  The fit is deliberately *not* changed. Shrinking the machine so a placard fits
  inverts the composition: the train is the subject and the mark references it, so
  the mark is what moves.

  Re-measured unseeded at 40 loads per viewport, 160 plate placements: **0
  clipped**, worst margins −3.5 px at 1440×900 and −0.1 px at 390×844.

- **#72 — `SERPENTINE_PACKING` was a measured constant standing in for a
  derivation.** #67 shipped it at 0.85, measured over 15 loads at 5 viewports,
  with a comment that had to say *"re-measure if the deal bounds, `MODULE`,
  `TOOTH_ADD` or the bearing range ever move"*. That is a description of drift,
  not a defence against it — the same failure as the hand-written hue fields in
  #12, the per-wheel `rim` values in #15 and the copied constant in #51.

  What it stood in for was one missing term. The first attempt floored the span at
  `MODULE × TEETH_MEAN × N`, which models the train as a **straight rack** and
  ignores the bearings, putting seven wheels at 798.7 units against a real mean of
  779.6. Centres actually advance by `(r1 + r2) × cos(bearing)`, and every bearing
  is drawn from `[ANG_MIN, ANG_MAX]`, so the mean of that range is the honest
  foreshortening. `NOMINAL_SPAN` is now one full wheel plus a foreshortened centre
  distance per step after it, computed from values the page already defines —
  change `MODULE`, the tooth target or the bearing range and it recomputes.

  It lands *under* a real solve rather than over it, which is the property that
  matters: the standard size sits in a `min()` beside the chain's own span, so
  underestimating means a real chain is bound by itself and never by this.
  Overestimating is what clamped the page in the first attempt.

  `16.3` appeared as a literal in two derivations and is now `TEETH_MEAN`, named
  once. `WHEEL_CROSS_MAX` went from a tuned 0.70 to **1.0** — a definition rather
  than a number chosen to look right: a gear may not be wider than the screen's
  short side.

  The suite now **executes** the `NOMINAL_SPAN` derivation out of `index.html`
  rather than repeating it, so the two cannot drift apart. 28/28, and 0 px against
  the previous commit at both viewports.

- **#67 — one-wheel escape runs crossed the short axis in portrait, and the
  sizing constant was arbitrary.** Two problems, both found by looking at the page
  rather than by any gate.

  `axisDeg` is measured from the first gear to the last. With one wheel those are
  the same object, so it is `atan2(0, 0)` — which returns **0** rather than
  failing, and 0° is horizontal in every orientation. On a 390×844 phone both runs
  left by the 390px sides after one wheel each and the whole 844px of height sat
  empty: exactly the failure #10 fixed for multi-wheel trains. The seven-wheel
  chain was verified correct in portrait, so this was only ever the degenerate
  case. A one-wheel train has no axis of its own, so it now falls back to the
  stage's — `axisRot()`, which is 90 in portrait and 0 in landscape and *is* the
  "chain follows the longest dimension" rule, reused rather than re-derived.

  The wheel also looked jittery, and that turned out to be the same problem as
  "too big". Sampling rotation in-page off rAF: the seven-wheel chain moves its
  rim **1.21px** per moving frame, the one-wheel chain moved **2.01px** — 66%
  further, because the wheel was 86% larger. `frameRate: 30` duplicates half of
  every 59 frames by design, so a bigger wheel simply steps further per update.

  And #66's `NOMINAL_WHEELS = 4` was wrong twice over. It was picked from
  screenshots as a taste call when the requirement is a rule — a gear is the same
  size wherever you meet it, so a solo page draws its wheel at the size a wheel
  has on the main page and carries more outriggers. And it floored the solved span
  against an *estimator* of something the solver already computes exactly:
  `MODULE × 16.3 × N` models seven wheels as 798.7 units while a real solve
  averages 779.6 and ranges either side, so the floor clamped some deals and not
  others. The main page's own scale moved between visits, and a fixed-seed pixel
  diff showed 107,664 changed pixels.

  Restated in **gears across the long axis**, derived from a scan of every chain:
  `GEARS_ACROSS = longest chain × SERPENTINE_PACKING`, and a gear is
  `longAvail / GEARS_ACROSS` px. Adding people never needs a retune and every
  chain matches the longest. `SERPENTINE_PACKING` exists because a chain of N
  wheels does **not** span N gear widths — the bearings run 14–30° off axis and
  the drawn span carries addendum and padding beyond the pitch circle. Measured
  over 15 loads at 5 viewports, seven wheels occupy **6.134–6.855** gear widths,
  so counting wheels overestimates by ~1.4× and would have shrunk every gear by
  ~30%. The factor must stay at or below 6.134/7 = 0.876 for the standard size
  never to clamp a real chain; 0.85 takes a margin under the lowest observed.

  Worth knowing: stated this way, rendered size is `longAvail / GEARS_ACROSS`, so
  `fit` and the wheel's own span **cancel** — a wheel is the same number of pixels
  whatever tooth count it was dealt. Wheels *within* a chain still vary relative
  to each other, because there the chain's own span binds instead.

  **0 px against `047b5f0`** at 1440×900 and 390×844: the main page is genuinely
  untouched, which #66's approach was not.

- **#66 — a one-wheel chain scaled to fill the viewport, and no absolute px cap
  could fix it.** Both `fit` terms are ratios against the *solve*, so neither
  says anything about how big one wheel ends up. Fine while the solve is a chain;
  not fine when the solve **is** one wheel, because `crossSolved` becomes a single
  diameter and the band term reduces to "a wheel may be `CROSS_BLEED` of the short
  axis" — exactly 125%, at every viewport. `?who=harper` drew one gear cropped off
  the top and bottom of the page.

  The note at #44 said any future cap must be an absolute wheel size in px.
  Measured over seven viewports, that cannot work: the seven-wheel chain peaks at
  **812px** (5120×1440) while the one-wheel chain bottoms at **486px** (390×844),
  so a full chain on an ultrawide renders *larger* wheels than a lone wheel does
  on a phone and no single pixel value spares one while catching the other. The
  note is kept rather than deleted — its reasoning about ratios driven by the
  **long** axis is still right — with the measurement recorded beside it.

  What shipped is one rule with four bounds and **no branch on chain length**: a
  gear has a standard size for this viewport, and shrinks only when the chain is
  too long to fit, when the serpentine's band would overflow the short axis, or
  when a single wheel would. "Standard size" and the first bound are the same
  expression with different denominators, so they collapse to
  `LINK_SHARE * long / max(NOMINAL_SPAN, longSolved)` — a long chain is bound by
  its own span, a short one by the nominal span, and neither knows which it is.

  #44's width-invariance is intact in every state: a one-wheel chain takes a
  constant 25.9–27.2% of the long axis from 390px to 5120px, with the escape runs
  covering the difference. A different constant, not a broken invariant. The
  fourth bound exists because that is still not enough — 27% of 5120px is 1391px,
  which on a 1440px display is 96.6% of the short axis, so `WHEEL_CROSS_MAX = 0.70`
  guards the aspect ratio the floor cannot. The seven-wheel chain peaks at 57.6%,
  so it never engages on a real chain.

  `NOMINAL_WHEELS = 4` was picked from screenshots at 3/4/5/7, not from theory —
  at 7 a lone wheel is exactly one of the chain's and its engraving is too small;
  at 3 it dominates the page.

  Three tests added, each executing the **real** fit expression sliced out of
  `index.html` rather than a copy of it: that the rule does not branch on gear
  count (lengths 1–12, identical scale out), that no chain renders past the guard
  (8 viewports × 12 lengths × both solve shapes), and that the linked share stays
  width-invariant. Mutation-proved both ways — dropping the guard reports
  `5120×1440, 1 wheels: rendered 1391.3px exceeds 1008.0px`, and adding a
  `TRAIN.length > 3` branch trips the first.

  **0 px** against the previous commit at 1440×900 and 390×844: a complete no-op
  for the seven-wheel chain.

  Method note worth keeping: the first measurement pass used
  `getBoundingClientRect()` on **rotating** elements, which returns the
  axis-aligned box of a spinning square — up to √2 too large, varying with phase.
  It inflated every figure by up to 41% and briefly suggested the seven-wheel
  chain rendered bigger wheels than the one-wheel chain. Measure the `width`
  attribute, never the rect, on anything that turns.

- **#65 — a chain shorter than `PAIR_SLOTS` assumes leaves wheels blank.**
  `PAIR_SLOTS` is `[[0,1],[3,4]]`, and those are wheel *indices*: `[0,1]` needs
  two wheels, `[3,4]` needs five. `singleSlots` was built as "every index no pair
  slot claims", so an unreachable slot went on claiming its in-range index
  anyway. On a one-wheel train, wheel 0 was withheld from the singles while no
  pair could ever be seated in it, and `slugFor` came out empty.

  A wheel with no slug does not throw — it draws as a **blank gear**: no badge,
  no engraved handle, no link. Harper's page was her one wheel, anonymous. This
  is the other end of #53: that was a slug the person did not have, this is no
  slug at all. A pair slot the train cannot reach is not a pair slot, so it is
  filtered out and its index falls through to the singles — which is what an
  unpairable wheel is.

  Two harnesses had the matching fault, both counting `href:` across the *whole*
  `PEOPLE` block — the train's length only while one chain exists. `tools/test.js`
  had a deliberate tripwire for exactly this and it fired on the second chain;
  `TRAIN_LEN`/`TEETH_SUM` are now per-chain, and both deal tests run against every
  chain, since the shortest is the one that strains the bounds.
  `tools/verify_motion.py` had no guard and simply went wrong, expecting 8 icons
  on a 7-wheel page and reporting `CHECK ABOVE` against a page that was fine. It
  now compares the icons to the badge links **on the page**, which is what this
  rulebook actually asks for and needs no config parsing at all — one less
  harness modelling page geometry (#64).

  The suite's seating test only ever modelled a five-wheel train, which is how
  this got through. It now replays the real seating block against the real
  config — every person, the actual `PAIR_SLOTS`/`PAIRS`/`SINGLES` — and asserts
  every wheel of every chain gets a service seated on it. Mutation-proved:
  reverting the one-line fix fails it with `harper: wheel 0 of 1 has no service
  seated on it`.

- **#58 — `const flat = true` made about half of `gearSvg` unreachable.** The
  flag sat at the top of both `gearSvg` and `ghostSvg` guarding a modelled-metal
  rendering behind roughly forty ternaries. It read as a live choice and was not
  one: both themes went flat on 2026-07-30 and every branch behind it has been
  dead since, so anyone editing a wheel had to reason about a second drawing
  that never runs.

  Gone rather than dormant — unlike the chain and belt this is not a capability
  anyone means to invoke again, so the comment at the head of `gearSvg` records
  what the modelled treatment did (five-stop body gradient, radial wells and
  bosses, turned-metal rings, specular arc across the lower face, drop shadow
  behind the blank, two-layer cut/lit engraving) and the code goes.

  What came out: **21** gradient stops repeating their own neighbours' colour,
  **17** paths drawn with *both* `fill="none"` and `stroke="none"`, `turned()`
  which returned `null` unconditionally plus its four call sites, and the
  ghosts' unused `shades()` palette. `shades()` stays live in `gearSvg` — `p[3]`
  is the line colour throughout.

  Verified in pixels, not by eye: collapsing dead branches changes the markup by
  construction, so a markup diff cannot answer the question. **0 px differ**
  against HEAD at 1440×900 and 390×844.

  Worth recording: the first diff said 57,709 px changed and it was the
  animation phase, not the code. Same class of mistake as measuring a rotated
  element with `getBoundingClientRect` — the measurement was fine, the thing
  being measured was moving. That is what forced #48 into existence.

- **#57 — a gradient nothing fills, a parameter nothing reads, three fields
  nothing draws.** The `<id>d` radial gradient was defined on every wheel and
  `url(#…d)` appears zero times in the file. `teethPath` took `prof` and never
  read it — a tooth is a function of the module and the `TOOTH_*` constants
  alone, never of the web style bolted to the same wheel, so the parameter
  invited exactly the wrong idea; removed from the signature and all five call
  sites with a comment saying why it must not come back. The background wheels
  carried `kind`, `arms` and a five-field `prof` that `ghostSvg` never reads.

  The isolation matters: deleting the seven `rnd()` draws shifts the seeded
  sequence, so the ghosts deal differently — 43,009 px, max channel delta 21,
  all faint grey machinery. Putting the seven draws back with their values still
  unused reads **0 px**, which is the proof that the gradient and the parameter
  are inert and the whole diff is the reshuffled deal. These wheels are re-dealt
  on every load anyway.

- **#42 — fourteen harnesses fought over one DevTools port each.** Every CDP
  tool hardcoded its port (9333, 9341, 9350, 9351, 9352, 9371, 9390, 9391, 9412,
  9420, 9430, 9500, 9600, 9700+i). Two running at once meant the loser raised
  `ConnectionClosedError`, which reads as a **page** fault rather than a harness
  fault — it produced a false `devices.py` failure on a layout that was entirely
  fine, and re-run alone the same page reported 20/20 and 4/4.

  Each now asks the OS for a free port and honours `CDP_PORT` when a caller
  wants a specific one. `cap_drag` and `epi_shot` keep their positional
  argument; it falls back to a free port instead of a fixed one. `wide_sheet`
  derived per-shot ports from a fixed base, so two sheets collided
  shot-for-shot — each shot now takes its own. Proved by running
  `verify_motion`, `pin_test` and `deal_dump` concurrently, all exiting 0.

  Every launch also carries `--window-position=-4000,-4000`, so a headless run
  stops stealing focus mid-session on macOS.

- **#51 — The hover pill clipped its own descenders, and nothing measured
  type.** Charles: *"Instagram's label is cut off along the bottom."* The label
  span sets `overflow: hidden`, which is **not** optional — it is the mechanism
  that lets the pill open by animating `max-width` from `0` — and overflow
  cannot be hidden on one axis alone, so asking for it horizontally takes the
  vertical with it. Paired with `font: 13px/1`, the line box was exactly as tall
  as the font size while the face's own box is 18px, so the tails were not
  overflowing, they were **sliced**.

  Measured at 13px Manrope: ascent 14, descent 4, and "Instagram" inks 12.68px
  with a 3.32px descender. At line-height 13px the half-leading is
  `(13 − 18) / 2 = −2.5px`, putting the baseline 11.5px down a 13px box, so the
  ink reached 14.82px and **1.82px was cut** — more than half the tail of the g.
  Solving `(LH − 18)/2 + 14 + 3.32 ≤ LH` gives `LH ≥ 16.64px`; `1.4` (18.2px)
  clears it and matches the face's own natural box rather than inventing a
  number. Two labels were affected, not one — Bluesky lost 1.62px of its y.

  | label | before | after |
  |---|---|---|
  | Instagram | ink 14.82 vs clip 13 → **+1.82 clipped** | 17.42 vs 18.2 → −0.78 |
  | Bluesky | ink 14.62 vs clip 13 → **+1.62 clipped** | 17.22 vs 18.2 → −0.98 |
  | the other five | −1.30 (no descender) | −3.70 |

  Confirmed in **both** engines. That mattered: a WebKit-only paint clip is a
  live defect on this page (#21), so "fixed in Blink" would not have been
  evidence about Safari. A WKWebView reports the same numbers, and the fallback
  path — the Google-hosted Manrope never arriving, so the stack falls through to
  `system-ui` — clears too, at −1.46. Neither *Instagram Sans* nor *Segoe UI*
  resolves on a stock Mac, so every pill renders in the same face and the one
  calculation covers all of them.

- **#37 — Blurry wheels in Safari: a promoted layer rasterised small, then
  stretched.** Every wheel wrapper carries `will-change: transform`, which
  promotes it to its own compositing layer, and a compositing layer is rasterised
  at its **layout** size. The whole gear container then multiplied that raster by
  `transform: scale(var(--gs))`. The badge plates, alone on the page, laid out at
  final size via `calc(px * var(--gs))` — which is why they stayed razor sharp
  while the teeth went soft, and why the contrast between them was the diagnosis.
  Blink re-rasterises a promoted layer when the composited scale changes; WebKit
  frequently does not, so Chrome looked fine throughout. #30 made it worse
  without causing it: uncapping the fit so the train could fill the long axis
  meant a bigger blow-up of the same small bitmap.

  Measured on Charles's own Safari screenshot, which is the only real composited
  WebKit frame available here — 10–90 edge-spread width, in pixels, and
  normalised high-frequency energy, over the gear teeth and over the badge plates
  in the *same* image: teeth **8.1–8.9px / hf 0.30–0.37**, plates **5.2–6.4px /
  hf 0.82–0.94**. The two halves of one screenshot differ by half again in edge
  width and by a factor of ~2.7 in high-frequency content.

  Fixed by rendering the wheels at final size instead of scaling a raster.
  `solve()` still works in module units — the geometry suite and the mesh tools
  read it, and it must not move — but `renderVals()` now multiplies every
  coordinate it emits by one quantised scale, `gsRender()`, and the container's
  `transform` is gone. Each wheel's SVG keeps its viewBox and takes a scaled
  `width`/`height`, so every path, gradient and engraving below it is still
  authored in module units while the element handed to the compositor is already
  the size it will be seen at. The badges follow the same arithmetic in plain
  pixels, so there is now exactly one place a scale is applied. `will-change`
  stays: promotion was never the fault — promoting a layer whose layout size was
  not its display size was.

  The check that replaces the eyeball is a ratio the DOM can answer: displayed
  wheel width ÷ the wheel SVG's own `width` attribute, which is the factor the
  engine has to blow the raster up by. In WKWebView — Safari's engine, same
  harness family as `tools/webkit_band.js` — that was **1.2500 on all eight
  wheels before and 1.0000 after**, at the same displayed size. In Blink across
  four viewports it was 1.250 / 1.180 / 1.067 / 0.727 before and 1.000
  everywhere after, and it stays 1.000 through a live resize sweep from 1600px
  to 700px.

  Dropping `will-change` was tried first, as the cheaper fix, and rejected on
  two counts. It relies on the engine choosing *not* to promote an element whose
  transform is rewritten every frame, which is a heuristic and not a contract —
  if WebKit promotes it anyway the blur comes straight back. And the thing it
  trades away is real: promotion is what keeps a rotating SVG off the paint path
  (#6). Blink's main-thread cost came out at 17.5 ms/s without `will-change`
  against 17.0 with, and 17.5 for the fix as shipped — all inside the run-to-run
  spread, so the measurement neither justified nor condemned it, and the
  structural change costs nothing measurable either way.

  **Unverified:** WebKit's *composited output* could not be photographed on this
  machine. `takeSnapshotWithConfiguration` re-renders from the display list
  rather than reading the compositor — a control page with an identical vector
  mounted promoted and unpromoted inside a scaled ancestor came back
  bit-identical, so the harness is blind to exactly this class of fault — and an
  offscreen WKWebView has no display link, so rAF never fires and nothing paints
  on a clock. What is verified is the geometry the fault is made of, before and
  after, in WebKit itself; what is not is a Safari photograph of the fixed page.
  That wants Charles's eye on a real browser.

- **#26 — Rim engraving off centre in WebKit only, and only there.** (Numbered
  past #24 and #25: `index.html` already cites both, from a11y work that was
  never logged here, and reusing them would have pointed those comments at this
  entry.) The handle sat centred in Blink and Gecko and rode outward in WebKit —
  Safari on the desktop and *every* browser on iOS, since they all run WebKit.
  Measured rather than guessed, in all three engines on the same geometry, as
  the offset of the line box's middle from the band's middle in fractions of
  band depth: WebKit **+0.192**, Gecko −0.000, Blink −0.000. On the shipped
  train that is 2.13px outward on an 11.13px band — far enough that the line box
  cleared the band's outer edge by 0.4px while leaving 3.9px of bare metal
  against the inner one.

  The cause is `dominant-baseline: central`, which #16 introduced to fix this
  exact symptom. WebKit does not apply it to text on a `textPath`: it lays the
  glyphs on the plain alphabetic baseline, which is precisely the pre-#16
  behaviour #16 described — *"the arc was being used as the baseline, so glyphs
  rode above it."* #16 was never wrong about the fault. It was wrong to hand the
  correction to a property that only two engines out of three implement here,
  and Chrome-only harnesses could not see the difference.

  Fixed by removing the engine's judgement from the loop rather than asking it
  for a different answer. The type now hangs off `dominant-baseline: alphabetic`
  — the initial value, the one every engine agrees on, and the one WebKit was
  already using when it ignored the property — and `engraving()` offsets the
  ring it rides on by `BASELINE_MID` (0.385em, half of Manrope's own ascent over
  descent) so the middle of the lettering lands mid-band. The shift is opposite
  in sign on the two lines, because the handle's ascenders point outward and the
  machining stamp's point inward. Nothing reads a font metric at runtime: the
  number is a constant in the page, so the radius is identical everywhere.
  Re-measured after: WebKit **−0.003**, Gecko −0.005, Blink +0.003 — a spread of
  0.193 of band depth between engines closed to 0.013, about a tenth of a pixel.

  `tools/webkit_band.js` is the harness this needed and the repo did not have:
  a WKWebView — Safari's engine, driven from JXA, no Safari setting enabled and
  no window opened — that measures the engraving against its band and prints a
  verdict. It reports PASS on the fixed page and FAIL on the old one. Every
  other harness here is Chrome, which is how a WebKit-only fault shipped.

- **#31 — Five hub marks were redraws, and four brand hexes were wrong.** The
  Reddit fix was treated as a one-off; auditing the other seven against
  **Simple Icons** — which is CC0 and cites each vendor's own brand page — showed
  the same problem everywhere. `bluesky` was a Font Awesome butterfly on a
  512-unit grid; `github`, `instagram`, `mastodon` and `threads` were Bootstrap
  Icons redraws on a 16-unit grid. All five are now the official Simple Icons
  path, re-cut to this repo's wrapper so `loadIcons()`'s `fill="#000"` swap still
  bites. The colours were off by more than rounding: GitHub `#24292F` → `#181717`
  (that was GitHub's old *text* grey, not its logo black), Bluesky `#0285FF` →
  `#1185FE`, Instagram `#E1306C` → `#FF0069` (`#E1306C` is a sample from the old
  2016 gradient, superseded), Threads `#101010` → `#000000`. `reddit`, `linkedin`
  and `mastodon` were already correct. `mail` is a generic envelope, not a brand,
  and is exempt.

  Three guideline problems are **known and not fixed**, because each one is a
  design decision rather than an error. Hover recolours the mark to
  `var(--accent)`, which most brand guidelines forbid outright. Instagram's
  current guidelines want the gradient glyph and permit flat colour only in
  monochrome contexts, which this page is not. And at the 30px floor the badge
  can reach, the marks are below several published minimum sizes — Mastodon and
  the snoo are the first to go muddy.

- **#20 — Docs described a chain and a belt that render nowhere.** Every document
  in the repo said the page had a roller chain and a toothed belt; the shipped
  train is fully direct-mesh and draws neither. Verified against the served page:
  zero of 100 paths carry a `stroke-dasharray` or `stroke-dashoffset`. The cause
  is simply that no `TRAIN` entry carries a `link`, so `solve()` yields no runs
  and `chainEl()` is never called. Worst of it was in `CLAUDE.md`: the documented
  verification recipe told the next reader to check that `stroke-dashoffset` was
  changing, a check that **cannot pass on healthy code** — the mirror of #7, where
  a static train photographed perfectly. Recipe rewritten around values that
  exist, and the strand code documented as a dormant capability (how to re-enable
  it, and the four rules from #4/#5/#8/#9 a new run must still satisfy) rather
  than deleted or left unexplained.
- **#19 — Train rendered smaller the larger the window got.** The fit scale was
  capped at 1.15, while the viewport spread boost widens the solve on big screens
  — so a large display produced a wide solve squeezed back down to small wheels
  sitting in an empty frame, with the background outriggers dominating. Ceiling
  raised (the artwork is vector, so growing is free) and the row-mode width allowance
  nudged to 0.86. Settled at **1.55** — 2.6 was tried first and read as far too
  large. Worth re-checking on a very large display; the `gearScale` tweak is the
  quickest way to test a different number before baking it in. **Still open:** at very large widths the train also
  looked offset right of centre; unverified at that size, since centring measures
  exact at 924×540 (stage centre 462 === viewport centre 462). If it persists,
  centre on the train bbox explicitly rather than relying on flex centring.
- **#18 — Cast shadows painted over adjacent wheels.** Each wheel drew its own
  cast shadow inside its own SVG, so a wheel later in the stack laid its shadow
  across the gear it meshes with, reading as if it floated above. All cast
  shadows moved to one layer behind every wheel; body extrusion pulled to 1px.
- **#17 — Machining stamp invisible on the far side of the band.** Drawn before
  the 205°–335° specular arc, which washed it out, and it had only a single flat
  fill. Arc now goes underneath; stamp gets the same two-layer struck treatment
  as the handle.
- **#16 — Engraved text not vertically centred in the band.** The arc was being
  used as the baseline, so glyphs rode above it. Both lines now centre their
  x-height on the ring (`dominant-baseline: central`).
- **#15 — Engraving band inconsistent between wheels.** Each wheel set its own
  `rim` value, so text sometimes sat on a flat ledge and sometimes straddled the
  step onto the raised face. Band is now defined first from the module, and the
  raised face is forced to start where the band ends — identical ledge on every
  wheel.
- **#14 — Blind pockets read as failed punch-throughs.** Cut clean through, so
  every opening on every wheel is genuinely transparent.
- **#13 — Chipped tooth was a pasted circle.** Even-odd filled as a separate
  blob. The tooth is now omitted from the profile and the blank runs straight
  across at root height, like a sheared tooth.
- **#12 — Engravings floated above the artwork.** Sat at a radius crossing the
  cutouts and outside the clip. Now struck into the solid band inside the tooth
  roots, inside the clipped metal, as a cut shadow plus lower highlight.
- **#11 — Hover drag never triggered.** Listened for hover only on the small
  icon badges, so most of each wheel was dead. The whole stage registers now.
- **#10 — Lighting read as eccentric.** Every radial gradient was centred at
  ~34%/28% with a diagonal body gradient and a lower-left specular arc; on a
  concentric object that reads as off-centre. Whole model relit from directly
  above and made symmetric about the vertical axis.
- **#9 — Drive runs doubled back through the group.** A belted wheel could be
  placed on a bearing pointing back into the train, folding the strand through
  the middle. Runs must now head away from the centroid of already-placed wheels
  (dot > 0.15), searching a ±150° arc to satisfy that plus the no-crossing rules.
- **#8 — Runs too short, reading as folded.** Base centre distance raised to
  ~2.4–2.5× the sprocket radii with a quantised viewport boost up to 1.55×, so
  strands are mostly straight span rather than wrap.
- **#7 — Train completely static (regression from #6).** Sleep gating could
  latch: the IntersectionObserver's first delivery reported `isIntersecting:
  false` while the stage was still 0×0, and nothing re-fired. Loop now starts
  awake, sleeps only on an explicit false after the stage has size, and derives
  the flag from one expression evaluated in `step()`.
- **#6 — CPU cost too high.** Nine `drop-shadow`-filtered SVGs re-rasterised
  every frame. Shadows baked into the artwork, background blur dropped, frame
  loop skips frames where the train has not visibly moved. Outriggers cut from
  up to 16 across four edges to two, one off each end wheel.
- **#5 — Drive runs crossed each other.** Edge selection now tests each
  candidate against runs already placed and skips intersections, on top of the
  no-shared-edge rule. Re-evaluated on resize.
- **#4 — Strands wrapped the near face of the sprocket.** Escape runs arced
  across the front; they now wrap the far side, entering on one tangent and
  leaving on the other.
- **#3 — Chain and belt drifted out of sync with the wheels.** Their independent
  CSS animations were replaced by the same master angle that drives the wheels,
  so they cannot drift or keep running on their own, and they reverse with the
  train.
- **#2 — Logic class dead from a name collision.** `P` was used for both the
  pitch constant and the point helper, killing the whole class. Renamed to
  `PITCH`.

### Added

- **#48 — `tools/pixel_regress.py`, a pixel gate that can actually fail.** The
  page is dealt at random *and* it turns, so two screenshots of identical code
  never matched and no visual check could be automated. Both sources of
  variation are pinned in the harness — `index.html` carries no test hooks:

  1. an LCG over `Math.random`, installed through
     `Page.addScriptToEvaluateOnNewDocument` so it beats every page script, so
     the same seed deals the same train;
  2. `requestAnimationFrame` queued rather than run, `performance.now` pinned to
     the same virtual clock, and `__pump(n)` advancing exactly *n* frames of
     exactly 1/60s.

  The second half is the one that would have been skipped. The loop stamps
  `last` from the real clock when it mounts and compares it against the frame
  timestamp, so a page that loaded 30ms slower skipped a different number of
  frames and stopped at a different angle. **With rAF frozen and the clock real,
  two runs of unchanged code still differed by ~40,000 px. With both frozen,
  zero.**

  Comparison checks the ref out into a throwaway `git worktree` on its own port,
  so nothing touches the working tree — no stash, no checkout, no uncommitted
  edit lost to a harness run.

  Mutation-proved per #47: ghost stroke opacity 0.65 → 0.45, a max channel delta
  of **2** and invisible to the eye, is caught at both viewports and exits 1; an
  unmodified tree exits 0.

- **#51 — `tools/pill_clip.py`, a gate for type.** The clipping above was
  reported by eye and could have come back the same way: `test.js` is geometry,
  `devices.py` is layout, `verify_motion.py` is animation, and **nothing had
  ever looked at a glyph**. This hovers every badge with a real
  `Input.dispatchMouseEvent` — a `MouseEvent` built in JS does not open the
  pill, the span stays 0 wide, and the gate would then be measuring a collapsed
  box — then places each baseline by the half-leading rule from the font's own
  metrics and compares the deepest ink against the clip edge.

  Two-sided, per #46: it also asserts every pill actually **opened**. A pill
  stuck shut has no width and nothing to clip, so a clipping check alone would
  pass most loudly on a page where the feature is broken outright.

  And it can fail, per #47 — demonstrated rather than assumed. Pointed at the
  deployed bucket, which still carries `13px/1`, it returns 1 and names
  Instagram at `+1.82` and Bluesky at `+1.62`; pointed at this tree it returns 0
  with a worst overrun of `−0.58`. It runs in CI beside the layout and motion
  gates, before any AWS credential is assumed.

- **#38 — The hex core takes the cells it was refusing.** Charles, looking at a
  GitHub wheel: *"isn't there space for even a few more hexagons on each side
  between the side of the shape and the curve of the inner circle"*. There was,
  and the reason it was being refused is a conservative test: the fit check
  asked `distance + c > rOut`, which treats every hexagon as a **circle** of
  radius `c`. A hexagon only reaches `c` toward its six vertices; in every other
  direction it falls short by up to `1 − cos 30°`. So cells that genuinely fit
  were rejected — and specifically the ones at the flats, which is exactly where
  the gap is visible. The keep now tests the six vertices and takes every whole
  cell that clears, rather than only cells belonging to a complete ring.

  | wheel | coarse | medium | fine |
  |---|---|---|---|
  | 14T | 18 | 18 | 18 → **24** |
  | 15T | 18 → **24** | 42 | 42 |
  | 16T | 18 → **42** | 42 | 42 → **66** |
  | 18T | 42 → **48** | 72 | 72 → **102** |
  | 19T | 72 | 108 | 108 → **120** |

  This cannot cost symmetry, which is the property that actually matters here:
  the lattice is six-fold symmetric about the centre and the test depends only
  on distance from it, so the kept set is closed under a 60° rotation — a cell
  that fits guarantees its five partners fit. Verified numerically rather than
  by eye: **21 of 21 wheel-and-variant combinations, worst mismatch 0.0000**.
  The patch gains symmetric bumps at the flats, never an uneven edge, and no
  cell is ever cut.

  What is left cannot be taken without cutting a cell — on most wheels the
  residue at the flats is narrower than one whole hexagon. That is the residue
  `polarbrick` and `polariso` exist to remove, being defined *by* the annulus
  rather than clipped to it.

- **#38 / #43 — Three ways to fill the web, and the hex core becomes a printed
  part.** #38 had been argued four times without closing, and the reason turns
  out to be that every option was a variation inside the losing family. The
  region to fill is an **annulus** — between the boss and the engraving — and a
  Cartesian lattice can never fill a ring. It either crops cells or leaves the
  six crescents the issue kept relitigating. A **polar** pattern is defined *by*
  the annulus, so it fills it by construction. Measured at real dealt sizes
  (`docs/core-fill.html`, never published), as a fraction of the annulus:

  | | 13T | 16T | 19T |
  |---|---|---|---|
  | hex core | 43% | 50% | 54% |
  | `isogrid` | 41% | 56% | 57% |
  | `polarbrick` | 61% | 62% | 60% |
  | `polariso` | 67% | 67% | 67% |

  The ceiling near 67% is the walls, which are material, not loss. What matters
  is that the two polar families reach the well circle exactly and the Cartesian
  ones do not. All three ship: `isogrid` for its equilateral cells, the polar
  pair for coverage. Eleven families now, so nothing repeats.

  **Symmetry is the requirement, not the boundary shape.** The retired
  ring-course honeycomb failed because its walls between courses never lined up
  with the walls within one. Every family here holds exact six-fold symmetry:
  the triangular lattice is centred on a lattice *vertex*, and the polar cell
  count starts at a multiple of six and only ever doubles outward.

  And the hex core's own question is answered by reframing rather than
  geometry. Read as a **milled** web it is wrong three ways — honeycomb is poor
  in in-plane shear, the pockets have sharp internal corners no endmill can cut,
  and the ring at the flats reads as the pattern running out. Read as an
  **additively manufactured** one, all three invert: a lattice is what you
  design for AM, no cutter means no tool radius to honour, and that ring is the
  **perimeter shell** every printed part carries around its lattice. The
  crescent is a required feature, not a defect. So the four lattice families now
  draw two shell walls inside the well and stamp `17-4PH · DMLS` beside their
  module and tooth count — metal rather than nylon, because what is drawn is a
  designed lightweighting lattice on the visible face and not slicer infill,
  which is an FDM concept and is always buried under solid top layers. Metal
  also keeps these wheels inside `WHEEL_POOL`, which is ground truth.

  A printed wheel renders that stamp regardless of the `character` layer, which
  is off as shipped (`2e5a721`) and would otherwise have hidden the mark on
  precisely the wheels that need it. Machined wheels still obey the flag and
  still say nothing.

  Two sizing traps are recorded in the code because both were hit: `cell` means
  triangle *side* for `isogrid` and course *height* for the polar pair, and
  neither is comparable to the hex core's number — equal visual weight needs
  `s = 2.45a`, so the first attempt rendered a mesh screen with cells 3.4× too
  small, and the correction then overshot into legible triangles with a third of
  the web bare. The shipped values sit deliberately between the two.

- **#41 — The device gate covers 2560×1440, and says out loud what it does not
  cover.** The layout guard had never been run above 2560×1080, which meant the
  widths people actually reported problems at were the widths nothing measured.
  QHD-wide is now in the list and passes. Two wider profiles are present as
  commented-out rows rather than being quietly absent: 3440 fails on four
  consecutive runs, 20–35px short of one edge at 99% coverage, and 5120 falls
  700–800px short. Both are **coverage**, not centring — the assembly is placed
  correctly and simply does not reach — and closing either means deciding how
  many more outrigger wheels that empty edge is worth against the per-SVG frame
  cost #6 fought to remove. That is a judgement, not a bug fix, and a gate that
  fails on an open question trains everyone to ignore red. The rows carry their
  own reasoning inline so neither width can be lost, and they go back in
  together once the outrigger count is settled.

- **#36 — The engraved underscores have ink, not just space.** `cs_marshall`
  was hard to read on the band because the underscore is pure edge: it has no
  body to spare, so at 5.6px it lost far more coverage to anti-aliasing than a
  letter did. Measured on the same rasteriser the SVG text goes through, its
  effective opacity came out at 0.45 against 0.57–0.60 for ordinary letters —
  the glyph was being drawn at roughly three-quarters the weight of its
  neighbours. Raising `fillOpacity` was rejected because it darkens every glyph
  equally and the struck-metal look is the point. Instead a hairline stroke
  matched to the fill (`ENGRAVE_STROKE` 0.035, about 0.2px here) is applied to
  the handle ring only, taking the underscore to 0.57 and 2.74:1 while moving
  letters by a tenth of that. The stamp ring is deliberately untouched — it
  carries no underscores.

- **#35 — The badge disc separates from the page in light mode.** The disc sat
  at **1.05:1** against the page, which is no edge at all; the comment claiming
  1.21:1 had been measured against the original white disc and never updated
  when it was toned down to answer a glare complaint. Rather than move back
  toward white and re-open that complaint, the disc is toned *darker* —
  `#CCCEC9`, the same hue scaled down — reaching 1.31:1 while still clearing
  11.3:1 against GitHub's near-black mark and 13.2:1 against Threads' pure
  black, so it remains a pale field for dark logos. Dark mode was already at
  12.2:1 and is unchanged.

- **#8 — The shipped defaults are stated, not inferred.** `SESSION-LOG.md`
  warned that the initial commit had baked in unsaved preview values, and it was
  right at the time — but two later commits (`e6936a7`, `2e5a721`) had already
  corrected parallax, character chips and the accent before the issue was even
  filed. Nothing currently shipping is accidental; every value traces to a
  deliberate commit. Establishing that took git archaeology against a stale log,
  so the `data-props` block now carries a comment naming all six live values and
  citing the commits that set them. `engravedRims` and the steel accent are
  deliberate overrides and were left exactly as they are. No default was flipped.

- **#7 — The dead CSS keyframes are gone.** `rotate`, `rotate-back`, `signsway`,
  `chainrun` and `chainrun-back` were left over from the build that animated the
  train in CSS, before everything moved onto the one `requestAnimationFrame`
  clock. Each was confirmed unreferenced across the whole repo before removal —
  the only surviving `animation:` rules anywhere are `support.js`'s own loading
  shimmer, which is unrelated. Nothing that turns has used CSS animation for a
  long time; now nothing can accidentally start.

- **#32 — The machine runs under Safari's chrome on iOS.** `viewport-fit=cover`
  hands the page the whole display instead of the safe rectangle, so the ghost
  wheels continue behind the translucent toolbars, under the notch and past the
  home indicator — a window onto a running train rather than a picture in a box.
  It only reads that way because #30 already made the assembly fill the long axis
  and let the cross axis bleed; before that there was nothing out there to see.
  The four fixed controls are the one thing that must not follow it under the
  chrome, so each corner offset is now `--btnoff` plus that edge's
  `env(safe-area-inset-*)`. The insets sit in their own `--safe-*` custom
  properties rather than being written into the offsets inline, for two reasons:
  a bare `env()` inside a `calc()` is invalid on a browser that has never heard
  of it, and an invalid `top` does not fall back to `--btnoff`, it falls back to
  `auto`; and a plain custom property can be given a value from a test, which is
  how `tools/devices.py` now exercises this. Chrome device emulation resolves
  every inset to 0 no matter which phone it is pretending to be, so the harness
  injects Apple's published insets itself and asserts the controls move inward by
  exactly that much while the gears ignore them entirely — a check that fails on
  all four profiles against the previous page. **Unverified:** no iOS runtime
  exists on this machine, so what iOS actually reports for
  `safe-area-inset-bottom` while Safari's tab bar is showing has not been
  observed. Adding the inset can only move a control further from an obscured
  edge, never into one, so the change is safe either way — but whether it fully
  clears the tab bar wants a look on a real phone.

- **#23 — Deploys from GitHub Actions, keyless.** Push to `main` publishes to
  `s3://wozi.com` and invalidates CloudFront. Auth is GitHub OIDC into
  `wozi-com-deploy`, whose trust policy pins the subject to
  `repo:csmarshall/wozi.com:ref:refs/heads/main` — repo *and* branch, so a fork or
  a side branch cannot assume it — and whose permissions reach exactly one bucket
  and one distribution. No long-lived keys exist anywhere. The job publishes an
  explicit whitelist and deliberately does **not** pass `--delete`: a bad sync
  with it empties the live site, while a stale object is merely untidy.
  Invalidation is not optional, since the distribution's default TTL is 86400 and
  a deploy would otherwise be invisible for a day. The run then verifies the live
  site over HTTPS and fails if anything is wrong, including asserting the icons
  are served as `image/svg+xml` — served as anything else, `loadIcons()` still
  fetches them, its `.catch` swallows the failure, and every badge renders empty
  with no console error.

- **#22 — www, TLS and directory URLs fixed at the edge.** `https://www.wozi.com`
  had never worked: www was a plain CNAME to the HTTP-only S3 website endpoint and
  was not an alias on the distribution, so it failed TLS outright rather than
  redirecting. A new ACM cert covers both names, www is now an alias on the
  distribution, and one CloudFront viewer-request function does two jobs —
  redirects www to the apex preserving path and query, and rewrites any
  trailing-slash URI to `index.html`. That second rule fixes `/cards/`, which had
  been returning **200 with a zero-byte body**: the origin is the S3 REST endpoint
  behind an OAI, so S3's own `IndexDocument` never runs and CloudFront's
  `DefaultRootObject` only covers `/`. Bucket versioning was enabled before any
  cleanup, so everything retired that day is still recoverable as a `null` version
  behind a delete marker.

- **#21 — The repo is now the source of truth for the whole bucket.** Everything
  in `s3://wozi.com` and `s3://www.wozi.com` was pulled in, and the repo made
  private to hold it. Still served: the gear train, `cards/`, `keybase.html` and
  `ssh_public_key`. Retired into `legacy/`: the 2023 landing page and its assets,
  the 2014 resume, `Spacer.gif`, and the entire `www` bucket (unreachable for
  years behind a redirect-all rule). Deploys publish an explicit
  **whitelist** of paths, so nothing reaches the web by being forgotten.
  **Melissa's contact card was removed from the site and deliberately kept out of
  this repo entirely** — `cards/index.html` had been a byte-identical duplicate of
  her card rather than an index, so trimming the URL to `/cards/` served her
  address and mobile to anyone who tried it. It now serves Charles's card. Her
  card lives only in `~/work/claude/qr_code_vcf`.

- **#1 — Layers.** Five independent detail passes, each a tweakable flag:
  spin-up (train winds up from rest on the flywheel), engraved rims (each
  wheel's handle struck into its band), parallax (background wheels ~22% slower,
  set back, drifting against pointer movement), character (chipped tooth plus
  stamped `M<module> Z<teeth>` marks), hover drag (hovering loads the machine to
  ~40% speed).
