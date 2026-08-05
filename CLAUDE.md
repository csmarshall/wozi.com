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
`speedFactor()` is the only thing the corner button reaches; `idleRate()` scales
by it, the flywheel eases to the new target, and every wheel follows because not
one of them is animated on its own.

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
says "strobing — benchmark only" in its accessible name and draws its numeral in
`--accent` instead of `--muted`.

So `min` and `max` in the schema are the levers; the strobe limit is never
written down anywhere, because it is a property of `BASE_MS` and the frame rate.
Never hand-write a stop list.

`tickRate()` is the one home for the update rate — `step()`'s frame budget and
`strobeSpeed()` are both computed from it. `driveCap()` is the one home for how
hard a flick or an arrow key may drive the flywheel: it is `max(8, idleRate())`,
because a fixed 8 stopped being a ceiling and became a *brake* once the idle rate
could reach 68.6 at 200×.

**The speed button's `style` is a render value, and it is the only fixed control
whose style is.** The other three are inline because nothing about them depends
on state; this one's colour does. That is the whole of the exception — do not
generalise it into hoisting the row's styling.

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

**A bridge is structure; an escape run is decoration.** On a combined stage
every chain but the spine is driven off it through ghost idlers, and those
idlers are **solved with the train** — they are `TRAIN` entries, they mesh, and
the gap between two chains is exactly what they take up, so the spacing is a
consequence of the drive rather than a number beside it. Escape runs are the
other ghosts: computed *after* the fit, off wheels that are already placed,
purely to carry the eye off the edge. **Never merge the two.** They look alike
on the page and are opposites in the solve — one may move a chain, the other may
not move anything. What they do share is the crossing rule: `fitEscapes` is
seeded with the bridges so an escape run refuses to cross one.

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

**Which chain is the spine and what order the rest stack in are two declarations,
not one sort** (#85). `spine: true` names the axis — a geometry choice, since it
sets the scale and every other chain is laid parallel to it. `order: <n>` names
the stack — a presentation choice, ascending, **topmost in landscape and leftmost
in portrait**. Both are per-person keys in `config.js` and both are documented
there.

**What an undeclared chain falls back to is link count, then name, both
descending**, and it falls in behind every chain that does declare an `order`.
The name is where `PEOPLE` order used to be: the tie broke on the line a person
was written on, which held only because `Array.prototype.sort` is stable and
which nothing in `config.js` said out loud. Naming the key makes the sort total,
so nothing leans on sort stability any more, and `PEOPLE` order now decides only
the person picker. The compare is case-folded and deliberately **not**
locale-aware — a tie-break that changes with the runtime's ICU data is a drifting
constant wearing a method call.

The spine's fallback does not restate any of that: it is *whichever chain the
stack puts first*, skipping any with no wheels. One home for "which chain leads".

`CHAIN_ORDER` is derived from the two and is not a third thing to keep in step:
it is the spine followed by the stack. **The spine is always at its head**, which
is structural rather than a preference — `solve()` places wheels in `TRAIN` order
and a bridge may only hang off a wheel already placed, so growth goes one way and
it starts at the axis. `CHAIN_ORDER[0] === SPINE` is therefore true by
construction rather than by the sort happening to make it true.

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
the same shape `bridge: false` produces, at the same distance, warning to the
console. An undriven chain now and then is a cost; a bridge drawn across another
run is the rule itself failing. **A crossing bridge is never drawn.**

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
