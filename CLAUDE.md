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

**One clock.** Every wheel transform and every strand's `stroke-dashoffset` is
derived from the same master angle each tick — one tooth of travel per tooth of
the driving sprocket, in whichever direction the train is turning. Reversing the
drag must reverse the chain and belt.

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

## Verifying a change

Never trust the screenshot alone — a static train looks fine in a still. Serve
the page and check, ~700ms apart:

- gear `transform` values advance
- `stroke-dashoffset` on the chain/belt paths is non-empty and changing
- no console errors
- hub badges sit at 0px offset from their wheel centres

## Change tracking

`CHANGELOG.md` is the log. Entries are numbered and stable; add upward, newest
first, and cite the number in the commit subject and the closing issue.
