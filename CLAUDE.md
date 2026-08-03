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
`keybase.html`, `ssh_public_key`.

`config.js` carries the link table, the people and the palette. It is published,
and CI asserts it is reachable, serves as `text/javascript` and parses — this
rulebook simply failed to list it for a while (#59), which is the worst kind of
drift: the rules requiring a file the rules do not name.

`keybase.html` is a signed ownership proof and is kept live deliberately — the
claim only verifies while the file is reachable, so dropping it from the include
list silently breaks it. Its content is signature-covered: serve it byte-exact or
not at all.

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

**Chains are laid out longest first, and overlap is a reported failure — not an
impossible one.** `CHAIN_ORDER` sorts by link count, ties breaking to `PEOPLE`
order, and that is the *layout* order, not merely the emission order: `solve()`
places wheels in `TRAIN` order and a bridge may only hang off a wheel already
placed, so a chain can only ever be driven from one earlier in the list. The
spine is `CHAIN_ORDER[0]` and growth goes one way.

The attachment search *prefers* a clear band of the cross axis and rejects every
anchor that does not give one. What it does **not** do is refuse: when nothing
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
