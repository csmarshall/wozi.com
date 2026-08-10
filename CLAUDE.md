# CLAUDE.md — wozi.com

Static site, no build step. `index.html` is the landing page; `support.js` is the
runtime it loads. Serve the folder and you are looking at the site.

This repo is the **source of truth** for `s3://wozi.com`, including the parts
that predate the gear train. It is private, because `cards/` carries a real
address and mobile number.

## What deploys, and what does not

The deploy **names the paths it publishes** rather than excluding the ones it
does not — a whitelist, so a new file cannot reach the web by being forgotten.

Published: `index.html`, `support.js`, `config.js`, `assets/`, `cards/`,
`keybase.html`, `ssh_public_key`, `robots.txt`.

`config.js` carries the link table, the people and the palette. It is published,
and CI asserts it is reachable, serves as `text/javascript` and parses — this
rulebook simply failed to list it for a while (#59), which is the worst kind of
drift: the rules requiring a file the rules do not name.

`keybase.html` is a signed ownership proof and is kept live deliberately — the
claim only verifies while the file is reachable, so dropping it from the include
list silently breaks it. Its content is signature-covered: serve it byte-exact or
not at all.

## The crawl policy, and where it is not stated

`robots.txt` allows everything and disallows nothing (#74). Before it existed the
path returned the raw S3 `AccessDenied` XML at 403, and a 403 is not a policy —
a crawler that cannot read a robots.txt treats the site as unrestricted, so the
site was indexed on a default nobody had chosen. It is published, and CI asserts
it is reachable, serves as `text/plain; charset=utf-8`, and is **byte-identical
to the repo copy** — the last of those is the only one that can tell a crawl
policy from the *right* crawl policy, since a stale object carrying the wrong
directive returns 200 as happily as the right one.

**Per-page indexing is decided on the page, never here.** Both card pages carry
`<meta name="robots" content="noindex">`, and `robots.txt` says nothing about
`cards/`. Two independent reasons, and either alone would settle it:

- **A `Disallow` would break the thing it looks like it is doing.** Disallow
  stops the fetch, so the crawler never reads the `noindex` — and a URL it is
  forbidden to fetch can still be listed, bare, from an inbound link. Blocking
  the crawl is strictly *worse* for keeping a page out of an index than letting
  it be crawled and told not to index.
- **`robots.txt` is world-readable, so naming a path advertises it.** `cards/`
  carries a real address and mobile number. A line pointing at it in the one
  file every scraper fetches first is a signpost, not a fence.

Which leads to the rule that matters more than either: **`robots.txt` is not a
privacy control and must never be used as one.** It steers well-behaved
indexers. Address harvesters ignore it entirely, and the live `mailto:` links on
the combined stage are exactly as harvestable with this file as without it —
that was considered and declined on its own merits, and nothing here changes it.
Anything that genuinely must not be public does not get published.

The `noindex` tags themselves are gated only in passing: `exact
https://wozi.com/cards/ cards/index.html` in the deploy compares whole-file
hashes, so removing one changes the hash and fails the deploy. That is a
by-product of #54's byte-identity check rather than an assertion anybody wrote
about indexing, and it hopefully holds, but it is worth knowing it is what is
holding.

Never published: `legacy/` (the archive of everything retired from the bucket),
and every document in the repo root — `CLAUDE.md`, `README.md`, `CHANGELOG.md`,
`PROMPT.md`, `SESSION-LOG.md`, `session-state.md`.

If you add something that should be live, add it to the include list in
`.github/workflows/deploy.yml`. Adding a file alone does not publish it.

## What a hostname selects

One object is served to every domain, and the browser decides what to draw from
it. **A hostname selects a scope, not a person.**

| what arrives | what draws |
| --- | --- |
| `wozi.com`, `www.wozi.com`, `localhost`, `127.0.0.1` | the combined stage — every chain |
| `charles.wozi.com` | Charles alone |
| `harper.wozi.com` | Harper alone |
| `?who=<slug>` | that person, solo, whatever the hostname said |
| `?who=all` | the combined stage |
| anything else | the combined stage |

The combined-stage names live in `STAGE_HOSTS` in `config.js`; a person's own
names live in their `hosts`, which are **solo hosts only**. The two lists must
stay disjoint and `npm test` asserts it — `STAGE_HOSTS` is checked first, so a
name in both would quietly mean "everyone" while `config.js` read as though it
named one person.

**The fallback is the combined stage, not `PEOPLE[0]`.** An alternate domain
name reaches the distribution before anyone edits `config.js`, so an
unrecognised hostname has to work on its own; it used to serve whoever was
written first, with nothing to say that was a default. Adding a domain is an ACM
SAN in us-east-1, an alternate domain name on the distribution and a Route53
alias — no deploy change, and no edit to `config.js` unless the new name is
meant to be somebody's personal address.

**A scope is not a person, and the code now says so in two names.** `SELECTED` is
the person the page is about and is `null` on the combined stage, where the
honest answer is "everybody"; `SPINE` is which chain the composition is built
around, which is a geometry question the hostname does not ask. They were one
constant (`WHO`), so every reader had to know which of the two it meant — the
analytics beacon wanted the selection and got the spine. See *Invariants* for the
rest; what belongs here is that **nothing about a hostname chooses a spine.**

**The picker is drawn only on the combined stage.** A personal link must not
advertise everyone else living on the domain, so the old rule — hidden while
there is one person — now also hides it while the view is deliberately one
person. It is stated here because this rulebook has got the host and file model
wrong once already (#59, `config.js` published but unnamed), and a rule nobody
writes down is the one that drifts.

## Do not

- **Do not hand-edit `support.js`.** It is generated runtime, not project code.
- **Do not add CSS animations or transitions to anything that turns.** All motion
  comes from one `requestAnimationFrame` loop that integrates a master angle.
  Anything animated independently drifts out of mesh within seconds — this has
  broken twice (#3).
- **Do not introduce stylesheets or CSS classes for layout.** Styling is inline
  by design.
- **Do not add `filter: drop-shadow` to the wheels.** Nine filtered SVGs
  re-rasterising per frame was the dominant frame cost (#6). Shadows are baked
  into the artwork and into one shared layer behind all wheels.
- **Do not hardcode wheel sizes, tooth counts, or centre distances.** They are
  derived from `MODULE` so the train meshes by construction.

## Invariants

**One clock.** Every wheel transform is derived from the same master angle each
tick — one tooth of travel per tooth of the driving sprocket, in whichever
direction the train is turning. The same rule binds any drive strand: its
`stroke-dashoffset` comes off that master angle too, so reversing the drag
reverses the strand with it. No chain or belt is enabled in the shipped train
(see *Dormant capability* below), but this invariant is what makes re-enabling
one safe.

**The speed control is a multiplier on that integrator and nothing else** (#96).
`speedFactor()` is the only thing it reaches, wherever it is drawn — the menu
slider (#108, CL#114) or the corner's reset-to-1× tap — and `idleRate()` scales
by it, the flywheel eases to the new target, and every wheel follows because not
one of them is animated on its own. Moving *where* the control is drawn must
never give it a second job.

**The flywheel COASTS: drag falls as it slows, and it still arrives** (GitHub
#106 → #121, CL#127 → CL#139). `approachSpeed(v, target, dt)` is the one
function `step()` calls to move `_v` toward whatever `target` `idleRate()` and
`motionActive()` computed that tick — spin-up and spin-down both, no direction
special-case.

The retarding rate is the standard three-term coast-down model an engineer fits
to a real rotor, acting on the gap between the wheel and the speed it is driven
at: **Coulomb + viscous + windage**. Windage (the square term) is air drag on a
disc and dominates at speed — it is what gives a hard throw its initial dive.
Coulomb is the constant residue that makes the wheel ARRIVE in finite time.

**Both previous models were wrong at opposite ends, and `SPINDOWN_DRAG_RANGE`
is the axis between them.** It is how much harder the wheel brakes at the top of
the ladder than at rest:

- **At 1** the terms collapse to a constant. That is CL#127's model, and it is a
  *brake* — a constant retarding torque is literally what a friction brake
  applies. Charles: *"almost as if there is a break on the wheel."* Nothing
  coasts at one flat rate and then stops decelerating at a corner.
- **Very large** the Coulomb residue vanishes and it becomes the pure
  exponential #106 rejected: it never truly arrives, and settling time stops
  depending on how hard you threw it. Measured — a windage-only fit makes a 2×
  throw take 1200ms against a full-ladder throw's 2400ms, so the throw stops
  telling you how hard you threw it.

15 is a **compromise, not a physical constant**. A real flywheel's range is far
higher (windage at 200× against bearing Coulomb at rest is easily 100×), but
past about 30 small throws read as sluggish. Realism and #106 pull against each
other and this is where they were balanced.

**Only the scale is solved; the shape is chosen.** `SPINDOWN_DRAG_RANGE` and
`SPINDOWN_WINDAGE` set the split, and the overall scale is bisected at load so a
full-ladder transition still takes exactly `SPINDOWN_RANGE_MS`. That is what
keeps CL#136's identity true — a saturating throw *is* the ladder travelled by
hand, so it must take the ladder's own time. `SPINDOWN_RANGE_MS` remains the
duration figure and is still a placeholder for Charles's call.

**The pixel gate cannot be 0px for a change to this function, ever.** `_M` is
the integral of `_v`, so a different spin-up curve permanently offsets
accumulated phase. CL#139 measured 48,551 / 48,590 / 48,788 px at 90 / 900 /
3000 frames — stable, not growing, which is the check that distinguishes a phase
offset from something structural. Use `dom_invariants` and `verify_motion` for
structure here.

**The speed that strobes is derived; the speed the control stops at is chosen.**
Keep those apart. A wheel's angle is `_M / teeth` and its pitch is `360 / teeth`,
so **one tooth of travel is 360 master-degrees on every wheel** — the tooth count
cancels, and there is one strobe speed for the whole train:
`strobeSpeed(frameRate) = 180 / ((7200 / BASE_MS) * (1000 / frameRate))`, which
is **15.75× at 30fps**. At or above it the teeth are sampled below Nyquist and
the train reads as stopped or reversing.

`SPEED_STOPS` lays a 1-2-5 preferred-number ladder between the `speed` schema's
`min` and `max` — **1, 2, 5, 10, 20, 50, 100, 200** — and the strobe limit does
**not** truncate it. The top stops are deliberately absurd: they exist to
benchmark the renderer, and a benchmark stop is allowed to look wrong. What is
not allowed is offering one silently, so every stop at or above `strobeSpeed()`
says "strobing — benchmark only" in its accessible name, and the control's
colour moves to `--accent` instead of `--muted`.

**The slider steps over `SPEED_STOPS` by index, never continuously** (#108,
CL#114). `min=0`, `max=SPEED_STOPS.length-1`, `step=1`, so every stop sits the
same distance under the thumb regardless of how far apart its neighbours are on
the multiplier's own scale — the ladder stays a ladder, and the absurd top
stops stay exactly as reachable as 2× is.

**The strobe warning is carried by colouring the thumb itself, not a mark on the
track.** A 2px tick at the boundary stop was tried first (GitHub #69's A/B
sheets) and was invisible at exactly that stop, because the 24px thumb sits
centred on the index it would mark — visible five stops either side, gone at
the one that means something. `--thumb-color` is a custom property set inline
on the input and read by the `::-webkit-slider-thumb` / `::-moz-range-thumb`
rules, so the thumb's own paint is state-driven even though a pseudo-element
takes no `style` attribute of its own; the readout text and the track's filled
portion carry the same colour, so all three flip together at the stop where the
illusion actually breaks.

So `min` and `max` in the schema are the levers; the strobe limit is never
written down anywhere, because it is a property of `BASE_MS` and the frame rate.
Never hand-write a stop list.

`tickRate()` is the one home for the update rate — `step()`'s frame budget and
`strobeSpeed()` are both computed from it. `driveCap()` is the one home for how
hard a flick or an arrow key may drive the flywheel.

**`driveCap()` is a property of the machine, not of the current setting, and it
decides how long a throw coasts** (GitHub #121, CL#136). It is
`rateAt(SPEED_CEIL)` — the fastest the train can be *asked* to run, so a hand may
wind it up that far and no further. It was `max(8, idleRate())`, and the reason
that had to go is the part worth remembering: **once CL#127 made the flywheel
decelerate at a constant rate, the coast became exactly `(driveCap() -
idleRate()) / SPINDOWN_DECEL`**, so a cap written as a bound on *speed* silently
became the only thing bounding *duration*. At 1× it was 8, and 8 → 0.343 is
269ms — for the hardest throw expressible, not just a gentle one. Deriving it
from the ladder's top makes the hardest throw take exactly `SPINDOWN_RANGE_MS`,
because it **is** the ladder travelled by hand instead of by the slider, and
makes the coast proportional to effort. `rateAt(mult)` is the one home for the
1× rate that both it and `idleRate()` are built on. Do not reintroduce a
constant here: a number chosen for the cap is a number chosen for the coast, and
nothing in the file will say so.

**The speed control lives in the pop-out menu now, not the corner row** (GitHub
#108, CL#114). The corner row is back to three permanent buttons — theme,
motion, the menu toggle — right-anchored by index exactly as before, just
renumbered to close the gap the speed button left. A fourth, conditional
corner control appears in the freed-up outer slot only when `speedFactor() !==
SPEED_FLOOR`: a **departure indicator**, not a chooser — its whole job is to
say "this page is not running at its normal pace" and to reset to 1× on a tap.
It reaches nowhere the slider does not; there is still exactly one thing the
speed control does, from either control that can touch it.

**The corner control's `style` is a render value, and it is the only fixed
control whose style is.** The other three are inline because nothing about
them depends on state; this one's colour depends on whether the current stop
strobes, and its `display` depends on whether it should be showing at all.
That is the whole of the exception — do not generalise it into hoisting the
row's styling.

**Hiding at 1× must not strand anyone.** The menu is the only route to
the speed control once the corner stops showing it, so the panel must open and
the slider must be reachable in every state the corner row can be in —
including a solo host (`?who=<slug>`), where the person picker is deliberately
absent and the slider is the first thing in the panel regardless.

**The pop-out panel is capped and scrollable, because centred-and-overflowing
loses content off both edges equally.** `togPanelStyle` sits at `top:50%`
with `transform:translateY(-50%)` and, until CL#114, no limit on its own
height — fine while nothing inside it mattered more than the rest, false the
moment the panel's first child became the only route to a control the corner
no longer shows. The Table of Gears list alone is tall enough to exceed a
landscape phone's viewport (595px of content against a 273px-tall iPhone
13/14 landscape window), and a panel centred on a viewport it overflows loses
the same amount off its top as its bottom — pushing the slider entirely above
the visible area, with no scrollbar to bring it back, on exactly the device
class where the corner is smallest and the menu matters most. `max-height:
calc(100vh - var(--offtop) - var(--offbot))` plus `overflow-y:auto` leaves the
panel the same clearance every other fixed element gets and makes the rest
scrollable, so the slider — flex-column's first child — is always the first
thing in view when the panel opens, whatever else it contains. Caught by
widening `tools/devices.py`'s safe-area selector to see the slider at all
(GitHub #108) — the panel's own overflow was invisible to that harness before
there was a form control inside it worth measuring.

**A cut opening is only as legible as what shows through it** (CL#133). Every
family but `planetary` and `ravigneaux` appends its openings to the wheel's own
path under `fillRule: 'evenodd'`, so the material is REMOVED and a cut shows
whatever is behind — the page. Its contrast is therefore `body vs page`: 1.33:1
on the palest wheel in light against 4.74–9.54 in dark. The epicyclics cut
nothing and DRAW their ring and teeth in `ft.line`, which is why they read at
every colour and the cut families did not. Every cut now gets that same contour:
`ft.line` for the ink, a fraction of the opening for the width, and opacity
raised only where the width has bottomed out on the aliasing floor. **Draw it
OUTSIDE the clipped group** — inside, the clip is `path + holes` with evenodd and
a stroke on a hole boundary loses its inner half.

**`MIN_CUT` floors the CUT, never the pitch** (CL#133). A lattice floors its
pitch and then shrinks each cell by `1.732 * WALL` to leave the wall, so a 5.2
pitch cut a 3.34-unit opening and `polariso` reached 2.18 — at that size the
walls and the contour are most of the cell. The pitch floor is derived from
`MIN_CUT`, so a blank that cannot host cells at that size cuts FEWER, LARGER
ones. That is what `sunburst`'s `maxLegible` has always done, and `sunburst` was
never the complaint. Note the search counts DOWN from the dealt cell size, so a
floor above its start silently skips the loop and the fallback takes over — the
fallback needs the floor too.

**`MIN_CUT` is stated in PIXELS and converted by `px()`** (CL#137). It was 5.6
solve units, which is one number meaning 7.8px on a desk and 4.7px on a phone —
the "correct at exactly one screen size" trap `px()` exists for. It is
`MIN_CUT_PX = 10.3`, taken from the family that works: `sunburst` never cuts
below 7.41 solve units, measured where `--gsfit` is 1.396. The retired 5.6 came
from `hexcore`, a family Charles had already complained about. A phone therefore
asks for MORE solve units to make the same 10.3px and cuts fewer, larger
openings — that is the intent, not a side effect.

**Every family is held to it now, and the conversion is per-family** (CL#138).
`MIN_CUT` floors the opening's NARROWEST dimension, so each family needs its own
map from its size parameter to that width, and they are not interchangeable:

- `isogrid`/`polariso` — the cut is inset by a wall each side, so the pitch must
  clear `MIN_CUT + 1.732 * WALL`. Subtractive.
- `hexcore` — `cellX` is the hexagon's CIRCUMRADIUS and the wall is additive in
  `step`, so `cellX` is pure cut. The narrow dimension is across the FLATS, not
  the vertices: `sqrt(3) * cellX >= MIN_CUT`, so the floor is `MIN_CUT / sqrt(3)`.
- `labyrinth` — an arc slot is long tangentially and narrow RADIALLY, so its
  `wL` already IS the narrow dimension and the floor applies directly. Its old
  cap of 6 units sat below `MIN_CUT` at every viewport, so every slot it ever cut
  was under the floor by construction. **Retired and unphotographable** — no
  `CENTRE_FAMILIES` entry, and `?kind=labyrinth` silently deals an ordinary mix —
  so it is bounded by its own row pitch rather than by any figure chosen by eye.

**The floor is an AIM for `hexcore`, not a gate, and a blank web is the reason.**
Its rings are anchored at the wheel centre, so radii land on fixed multiples of
the pitch and a ring is wholly in or wholly out — cells do not degrade
gracefully, they stop fitting. Applied as a hard floor it emptied 1 of 7 wheels
on a desk and 3 of 7 on a phone. So the sweep retries at `hexcore`'s own
legibility floor (`px(3.9, 2.2, 6.0)`, where a cell stops reading as a hexagon),
which bounds the fallback at what already shipped: never a smaller cell than
before, never a web that used to be full and is now empty. Same trade the shell
clearance makes — *having any pattern is not a nicety*.

**The sweep grid is anchored at the FLOOR, never the ceiling** (CL#138). Written
as `for (c = ceiling; c >= floor; c -= 0.05)` the set of sizes actually tested
depends on where it STARTS, so moving the ceiling silently tests a different set
and the floor is sampled only when the span is a whole number of steps. A
13-tooth wheel went blank at one viewport and not at a neighbouring one with
identical `rIn`/`rOut` because the only feasible size sat just under the last
grid point the ceiling happened to produce. Count down from the floor.

**`LATTICE_WALL` is the one home for the wall between openings.** The expression
`max(px(1.06, 0.55, 2.4), 1.2 * teeth / TEETH_MAX)` was written out four times —
`WALLX`, `wallI0`, `WALLP` and labyrinth's — which is four chances to update
three of them.

**Light mode casts no wheel shadow** (CL#133). The shared layer shows through the
openings as well as the tooth gaps, so a cut measured 22 units darker than the
page beside the gear and never showed the page at all. Off in light, kept in
dark, where the wheel is lighter than the page and the halo does what it was
written for. The badge disc keeps its own `0 3px 10px`, so the page still reads
as layered.

**Lighting from directly above.** All shading is symmetric about the vertical
axis: vertical body gradients, radial highlights at 50% horizontally, specular
arc centred on the bottom, cast shadows straight down. Any diagonal or corner
light makes concentric geometry read as eccentric (#10).

**Geometry derives in one direction.** The engraving band is defined first, as a
module-based annulus inside the tooth roots; the raised face then starts exactly
where the band ends. Never the reverse — per-wheel `rim` values are what made the
band inconsistent (#15).

**Drive runs are solved, not placed.** A candidate run is rejected if it crosses
another run, passes over a third wheel, shares an edge with a background
outrigger, or heads back toward the centroid of already-placed wheels (dot ≤
0.15). Re-solved on resize, quantised so resizing does not thrash.

**Paint order matters.** The specular arc must go *under* the rim engravings or
it washes the far-side stamp out (#17). Cast shadows live in one layer behind all
wheels, never inside a wheel's own SVG, or a wheel shadows the gear it meshes
with (#18).

**The sleep gate starts awake.** Offscreen/hidden gating may only sleep the loop
on an explicit `isIntersecting === false` *after* the stage has non-zero size,
and the flag must be one expression evaluated in `step()`. Latching it true
froze the entire page (#7).

**A drive run is structure; an escape run is decoration.** On a combined stage
every chain but the spine arrives through a run of ghost idlers, and those
idlers are **solved with the train** — they are `TRAIN` entries, they mesh, and
the gap between two chains is exactly what they take up, so the spacing is a
consequence of the drive rather than a number beside it. Escape runs are the
other ghosts: computed *after* the fit, off wheels that are already placed,
purely to carry the eye off the edge. **Never merge the two.** They look alike
on the page and are opposites in the solve — one may move a chain, the other may
not move anything. What they do share is the crossing rule: `fitEscapes` is
seeded with `solved.bridgeRuns` so an escape run refuses to cross one, and
**every structural run must be published into that list** or it becomes the one
run on the page that anything may be laid straight across.

**Who gets a *leading* escape run is decided by drive, not by the spine** (CL#132).
The spine gets both runs. A chain something on stage drives gets only the
trailing one — its leading end is where its bridge arrives, and a second tail
there would run into the machinery driving it. **A self-driven root gets both**,
because nothing arrives at its leading end except its own origin run. That last
case was the bug: the gate read `!spine` while the argument only ever covered
`driven`, so a root's leading side stopped dead in open space (x=406 at 1440×900)
while the spine's ran off the frame (x=−222). A root's leading run is hosted on
the **outermost origin idler**, not on the lead gear — the origin run already
occupies that side — and that idler is already placed, so this adds nothing to
`TRAIN`.

**A solved wheel says what it is *for*, not only where it is** (CL#132). `drive`
is `'bridge'`, `'origin'` or null and `serves` names the chain a ghost carries,
so "is this chain self-driven" is answerable from the solve instead of by
indexing back into `TRAIN` or inferring it from position. `fitEscapes` records
each ghost's host centre for the same reason: a run's heading means nothing
measured from the wrong origin, and the host stopped being `head`-or-`tail` the
moment a root's leading run moved onto its origin tip.

**`MAX_IDLERS` is budgeted against the cross axis, and an origin run does not
travel along it.** `IDLERS_FOR(roomy)` is binary — `roomy ? MAX_IDLERS :
MIN_IDLERS` — and `idlerCount()` asks whether `STAGE_CROSS(MAX_IDLERS)` fits the
**cross** axis, because the count was written for bridges, which travel across to
separate chains. An origin run travels along its **own chain's** long axis. So
raising `MAX_IDLERS` to lengthen an origin run makes it *shorter*: the larger
demand fails the cross-axis test and falls back to `MIN_IDLERS`. Measured, not
reasoned — a 6-idler pool dropped a root to one leading ghost. **This is still
true and is not fixed**; the shared count is documented below as a feature, but
the budget behind it only ever measured one direction.

**There are two kinds of structural run and one count** (GitHub #116, CL#123). A
**bridge** carries a dependent chain's drive in from the chain that drives it; an
**origin run** carries a self-driven chain's drive in from off the stage. They
are the same run of plain idlers, they take the same `MAX_IDLERS`, they park by
the same `nIdle`, and both go into `bridgeRuns` — so how many wheels stand
between a chain and whatever turns it is one number and not two. The one line
that has to know the difference is the bearing: an origin run travels **along its
own chain's axis** (`originBase`), a bridge **across to another chain**
(`bridgeBase`). Fold them together and an independent chain's drive leaves by the
cross axis, which is the #67 confusion exactly.

**`ORIGIN_MOUNT` decides where a self-driven chain's run originates, and it is
awaiting Charles's call.** `'edge'` (shipped) trails the run off the stage and
leaves the chain's position **solved**; `'fixed'` starts it at an anchored mount
and makes the position **pinned**, with the gap between chains becoming
`CHAIN_RANK × ORIGIN_PITCH` instead of what the idlers take up. It is one word in
`index.html` and deliberately **not** a URL parameter — `?seed` is the only
determinism affordance shipped code carries (CL#109), and a second switch
reachable from the address bar would be a second way for the page to draw
something no gate photographs.

**A bridge bearing is relative to the axis, never to the screen.** The stage
rotates the whole train by `_axisRot` in portrait. `BRIDGE_BEARING` is 90°
*from the spine*, and is only ever used added to `_axisRot` — write it in
absolute screen degrees and the bridge stays horizontal while the train turns
upright, sending it across the **short** axis. That is the #67 class of failure,
and it has now been made twice by two different pieces of geometry.

**And so is which way round it runs.** That is the same lesson's second half, and
it was missing until 2026-08-05: the bearing was relative to the axis but its
*sign* was fixed at `+90`, which means "down" at `_axisRot` 0 and "left" at 90.
The rotation was honoured and the handedness was not, so in portrait the spine
came out **rightmost** with the stack running toward the left edge — geometry
that is a legal mirror image, which is exactly why nothing local objected and
only a screenshot could tell. The rule now, stated once: **the bridge runs along
the cross axis away from the stage origin**, so rank 0 is topmost in landscape and
leftmost in portrait, and both candidate bearings are compared rather than one
being written down. Note what caught it and what did not — every harness here
measured *along the bridge direction*, and both mirror images pass that. The
regression test is in screen `x`/`y` for that reason.

**One key says who drives a chain, and the stack falls out of it** (GitHub #116,
CL#123). `child: '<slug>'` names the chain this one takes its drive from;
`child: null`, or no key at all, means the chain is a **root** — nothing on stage
drives it, and it is **self-driven** by an origin run of its own. It replaced
`bridge: true|false`, which was a boolean about the spine: it could express a
star and never a tree, and its `false` produced a set of gears nothing turns.

**`child` declares membership, not the attachment point.** The wheel a chain
actually hangs off is computed: the **first child takes its drive from the
parent, and every later sibling takes it from the lead gear of the sibling before
it** — you do not take four power take-offs off one gear, you cascade them.

**The stack is a depth-first walk of that tree, not a sort.** A dependent follows
its parent immediately even when an unrelated root is longer. Link count and name
survive only as the **sibling** tie-break, and `order: <n>` ranks siblings
ascending — **topmost in landscape and leftmost in portrait**. Undeclared falls in
behind every sibling that declares one, then by link count, then by name, both
descending. The name is where `PEOPLE` order used to be: the tie broke on the
line a person was written on, which held only because `Array.prototype.sort` is
stable and which nothing in `config.js` said out loud. `PEOPLE` order now decides
only the person picker. The compare is case-folded and deliberately **not**
locale-aware — a tie-break that changes with the runtime's ICU data is a drifting
constant wearing a method call.

**`spine: true` is retired, because the spine is the first root.** A root is
exactly what `child: null` means and the first of them is exactly what the walk
lays out first, so the two declarations could only ever have agreed — and a
config could express a disagreement the page would then have had to arbitrate.
The roots are siblings, so `order` still names the axis; it is the same lever it
always was, one scope narrower. **Both retired keys are warned about, not
ignored**: a file still carrying one is an unfinished migration, and reading it in
silence would draw a composition nobody asked for.

**Three mistakes are newly expressible and all three are refused by name**, each
warned and the chain placed as a root: a chain naming **itself**, a chain naming a
slug that is **not a person in `config.js`**, and a **cycle**. The cycle check
walks the parent links already resolved and stops the first time it revisits a
name — one pass, and it cannot recurse. A parent that is simply **not on this
stage** is silent and not a mistake: a solo page carries one person, so every
dependent is legitimately a root there. A parent with **no wheels** is stepped
over to the nearest ancestor that has some, so the tree the walk sees contains
only chains that are actually drawn.

`CHAIN_ORDER` is that walk, with wheel-less chains appended after it, and is not
a second thing to keep in step. **The spine is always at its head**, which is
structural rather than a preference — `solve()` places wheels in `TRAIN` order and
a drive run may only hang off a wheel already placed, and a cascade is inherently
ordered because each sibling's anchor is the previous sibling's lead gear.
`CHAIN_ORDER[0] === SPINE` is therefore true by construction rather than by a
sort happening to make it true.

**`SPINE` and `SELECTED` are different questions and no longer share a name.**
`SPINE` is which chain is the axis; `SELECTED` is which person the page is about,
and it is `null` on the combined stage, where the answer is "everybody". They
were one constant (`WHO`) and every consumer had to know which of the two it was
really asking for — the beacon wanted the selection and got the spine.

**Overlap is a reported failure — not an impossible one.** The attachment search
ranks every anchor and takes the first that clears three
tests: the bridge and the whole chain behind it must foul no wheel, the bridge
run must pass over none, and it must cross no other bridge. There is no
cross-axis band test — the cross axis is bounded elsewhere, by `idlerCount()`.
What the search does **not** do is refuse: when nothing
clears, the last-ditch path takes the best-ranked anchor and plants the chain
anyway — `console.warn`, "which may clash" — because a chain that is simply
absent is worse than one standing too close. A separate pass then measures every
cross-chain pair and warns `wozi: chains overlap — …` with the wheels and the
overlap in pixels. So overlap is *detected and announced*, never silently
prevented: if that warning is in the console, the composition has failed and the
console is the only place it says so. **A crossing bridge is the thing that is
actually impossible** — see below — and that is a stronger guarantee than this
one on purpose.

**A bridge that cannot be placed cleanly refuses.** When no anchor clears the
non-crossing rule, the bridge is abandoned and the chain is placed *unbridged* —
at the same distance, warning to the console. An undriven chain now and then is a
cost; a bridge drawn across another run is the rule itself failing. **A crossing
bridge is never drawn.** This is the one place the page still draws an undriven
chain: a refusal is discovered at *solve* time, and the idlers that would carry an
origin run are `TRAIN` entries dealt at *load* time, so it cannot fall back to
one. Adding wheels at solve time is #55 exactly.

**And a refusal is not local, which is what the cascade added** (CL#123). Every
chain whose drive path runs *through* the refused one loses its drive too — while
keeping its position and its own bridge, so nothing moves and nothing is missing,
and the only symptom is a run of chains that turn because everything turns. The
refusal warning therefore **names the chains it stranded**, from the one refusal
that caused it rather than as *n* symptoms. It is invisible in a still and
invisible in the geometry; the console is the only place it can be said.

**A self-driven chain is a second connected component, and always will be.**
`tools/dom_invariants.py` reports the component count and asserts only that no
wheel is an *orphan* — and that distinction is now load-bearing. CL#122's
`bridge: false` left Harper's single wheel meshing with nothing at all, which
failed the gate; her origin run is what fixes it. The count is still **2**,
because a chain nothing on stage drives is a separate mesh by definition. One
component and a self-driven chain cannot both be true.

## Dormant capability: chain and belt

The shipped train is fully direct-mesh — every wheel drives its neighbour, so
spacing is fixed by the pitch radii and only the bearing varies. That was a
deliberate late decision: a serpentine with no slack cannot fold, which is how
#9 was finally settled.

The roller chain and toothed belt are **not deleted, only uninvoked**, and the
implementation is intact:

- `chainEl()` builds both variants — external tangents plus far-side wrap arcs,
  with dash arrays at the gears' own circular pitch (π × module), so every roller
  drops into a tooth space.
- `applyRotation()` drives every tracked strand's `stroke-dashoffset` off the
  master angle.
- `solve()` reads `belt: t.link` and creates a run wherever a `TRAIN` entry
  carries one.

To bring one back, put `link: 'chain'` or `link: 'belt'` on the `TRAIN` entry
that should drive its successor by strand instead of tooth mesh. Nothing else
needs wiring — the solver picks it up.

Re-enabling means re-earning the four rules the strands cost the most to learn. A
run must wrap the **far** side of the sprocket (#4), must not cross another run
(#5), must be long enough to read as span rather than wrap (#8), and must head
*away* from the centroid of the wheels already placed (#9). The solver still
enforces all four; they are simply not exercised while no entry has a `link`.

## Verifying a change

**Run `npm test` first.** It is the geometry suite (`tools/test.js`), and it
reads its constants, the two-row menu and the sizing functions *out of
`index.html`* rather than keeping copies — so it measures what actually ships.
It asserts that every gear set the page can deal actually meshes, that every
two-row set assembles and clears all five of its relationships, and that each
one's stated minimum blank is honest. CI runs it before assuming any AWS
credential, so a broken set cannot reach the bucket.

This matters most for one class of edit: `MODULE`, any `TOOTH_*`, `BAND_*`,
`RIM_UNDER_BAND`, `MIN_MODULE` or the deal bounds all feed the bore, and a
bigger bore makes gear sets reachable that nothing has ever measured. Change one
and re-run the suite before pushing.


**A 0px pixel gate can mean "not tested", not "unchanged".** The default deal is
seven wheels drawn from eleven families, so a change confined to one family has
about an even chance of not appearing in the shot at all. CL#138 rebuilt
`hexcore` and `pixel_regress` reported **0px differ** at both viewports; the same
run with `--query '?who=charles&kind=hexcore'` reported **27,069**. When a change
targets a family, force it with `kind=` or the gate is agreeing with you about a
picture it never took.

**The pixel gate photographs the combined stage.** `tools/pixel_regress.py`
serves on `127.0.0.1`, which is a `STAGE_HOSTS` name, so its default shot is
every chain at once. Use `--query '?who=charles'` to ask the narrower and often
more useful question — whether **one** chain still draws exactly as it did —
because a change to the bridge, the datum or the chain ordering moves the
combined shot enormously while leaving the single-chain path untouched, and only
the second run can tell you so.

**`?seed=8231` fixes the deal, and no gate may use it.** The shipped page accepts
a seed in the URL, and when it gets one it deals every wheel from a generator of
its own — tooth counts, families, bearings, colours, which wheel wears which
service. It exists so that a bug report from a real phone describes a machine
that can be drawn again on a desk, and it is the only determinism affordance in
shipped code (CL#109). **The harnesses keep injecting their own LCG through
`Page.addScriptToEvaluateOnNewDocument` and must go on doing so**: a gate that
deals through the same mechanism the page deals through cannot see a fault in
that mechanism, because it would agree with the page about a machine they had
both got wrong. Absent the parameter the page does not touch `Math.random` at
all, which is what keeps `pixel_regress` at 0px; a malformed or out-of-range seed
deals at random and says so in the console. And it fixes the **deal**, not the
fit — the placement is measured off the viewport, so reproducing a machine takes
the same seed *and* the same window size.

**`?hud` is the page reporting on itself, and it is the one test hook that
ships.** Everything else in `tools/` observes the page from outside; this draws a
panel *in* it, which is a deliberate exception to the rule that test scaffolding
lives in the harness and never in the shipped file. It earns the exception by
being the only way to read tick rate, dropped ticks, the wheel census and
**which of the four fit terms is binding** on a device no harness can drive — a
real phone, on battery, in Low Power Mode, with a collapsing URL bar.

It is off by default and cannot be reached by accident: the gate is
`/[?&]hud(=|&|$)/`, so `?hudson=1` does not trip it, and there is no button and
no key binding. Absent the parameter the page is byte-identical.

**It reports the loop; it must never join it.** Inside `step()` it does integer
arithmetic and one array write — no DOM, no allocation, no layout read — and all
drawing happens on a 500ms timer outside the loop. It reads the raw inline
`--gsfit` string rather than calling `getComputedStyle`, and the `_solved` cache
rather than `solve()`, because either would make the instrument change the
reading. `_hudAsleep` mirrors the sleep gate's own expression rather than
re-deriving it, since a second opinion about that flag is exactly what #7 was.
It displays its own cost so those claims can be checked rather than believed.

**Six things no harness here can answer, and `docs/MANUAL-CHECKS.md` names
them.** Everything in `tools/` is headless Chrome over CDP plus one windowless
WKWebView, so none of it has browser chrome, a window manager, a battery or a
finger: a collapsing URL bar, rotation with the keyboard up, home-indicator
overlap, Low Power Mode's rAF throttling, Safari's own controls, and the real
`env(safe-area-inset-*)` values `tools/devices.py` currently has to inject
because Chrome resolves every one of them to 0. That file lists each with what
correct looks like and why it cannot be automated. It is not a gate and nothing
runs it — the page's only mobile oracle is one human, which is the whole reason
it is written down. Work through it after a change to the fit, the safe-area
offsets, the frame budget or the fixed controls. `docs/` is not published.

Never trust the screenshot alone — a static train looks fine in a still. Serve
the page and check, ~700ms apart:

- gear `transform` values advance — all of them, not just the first
- no console errors. A `/favicon.ico` 404 is expected and benign: the real icon
  is a `data:` URI injected through `helmet`, so the browser asks for the default
  path first.
- hub badges sit at ~0px offset from their wheel centres
- each badge contains an `<svg>`. Empty badges mean the page was opened from
  `file://` instead of served — `loadIcons()` fetches them, and its `.catch`
  swallows the failure silently.

Only if a drive strand has been enabled: its `stroke-dashoffset` is non-empty and
changing. **The shipped direct-mesh train has no strands, so there is no
`stroke-dashoffset` anywhere on the page** — an absent value is correct here, not
a regression.

## Change tracking

`CHANGELOG.md` is the log. Entries are numbered and stable; add upward, newest
first, and cite the number in the commit subject and the closing issue.
