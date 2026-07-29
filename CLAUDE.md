# CLAUDE.md — wozi.com

Static site, no build step. `index.html` is the entire page; `support.js` is the
runtime it loads. Serve the folder; that is the deploy.

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
