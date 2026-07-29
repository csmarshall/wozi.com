# Session log

An accounting of the work behind this page, written at the end of the session
that produced it. `CHANGELOG.md` lists *what* changed as numbered entries; this
file records *why*, what was tried and rejected, and what state things were left
in. Assembled from the working session, so it is a faithful record of the
decisions rather than a commit-by-commit history — there was no repository during
the work.

## What was built

A landing page for wozi.com in the form of a working machine: seven meshed gear
wheels driven by a physics loop, with a roller chain and a toothed belt coupling
outlying wheels back into the train. Each wheel carries one social link at its
hub. Background "outrigger" wheels run off the first and last wheel to imply the
machine continues past the frame.

Content: LinkedIn, GitHub, Threads, Bluesky, Mastodon, Instagram, and email.
Targets live in the `SITES` map. Flickr was dropped; GitHub and Bluesky added;
Threads pointed at threads.com. The wordmark reads the host it is served from.
Light and dark themes follow the OS with a persistent toggle.

## The arc of the work

**From animation to simulation.** The first build turned the wheels with CSS
animations. That could not hold — the chain and belt had their own independent
animations and drifted out of mesh, and nothing responded to input. Everything
was moved onto a single `requestAnimationFrame` loop integrating one master
angle, with flywheel inertia and drag-to-spin. That is the change the rest of the
project rests on: mesh correctness became structural rather than something to
keep re-tuning.

**Geometry earned its correctness.** Wheel sizes, tooth counts and centre
distances are all derived from one module constant, so the train meshes by
construction rather than by hand-fitted numbers. The same principle later fixed
the engraving band: define the band from the module first, then force the raised
face to start where the band ends.

**The drive runs took the most iteration.** In order: they wrapped the near face
of the sprocket instead of the far side; they crossed each other; they were too
short and read as folded; and finally the real cause of the folding turned out to
be *direction*, not length — a wheel could be seated on a bearing pointing back
into the group. The solver now rejects any run that crosses another, passes over
a third wheel, shares an edge with an outrigger, or heads back toward the
centroid of the wheels already placed, and searches a ±150° arc to find a bearing
that satisfies all of it.

That is where the strands *ended*, but not where the page did. The train that
shipped is fully direct-mesh: no entry in `TRAIN` carries a `link`, so no chain
and no belt are drawn. Having every wheel drive its neighbour fixes spacing at
the pitch radii and leaves only the bearing free — a serpentine with no slack,
which cannot fold no matter what the solver does. The strand code stays in the
file, intact and correct, against wanting it later; `CLAUDE.md` records how to
re-enable it and which of the four hard-won rules a new run has to satisfy.

**Performance was a real constraint, then stopped being one.** Per-wheel
`drop-shadow` filters were the dominant cost — nine filtered SVGs re-rasterising
every frame. Removing them (baking shadows into the artwork), dropping the
background blur, cutting the outriggers from up to sixteen down to two, and
idling the loop when nothing moves brought it to a sustained 60fps with about
0.02ms of JS per tick and zero forced layout. That optimisation also caused the
worst regression of the session: the sleep gate latched true while the stage was
still zero-sized and the entire machine sat still. Worth remembering that a
static train photographs perfectly.

**Lighting was fixed at the model, not per-wheel.** Wheels looked subtly
off-centre; the cause was that every gradient was lit from the upper-left. On
concentric geometry, diagonal light reads as eccentricity. Relit from directly
above and made symmetric about the vertical axis.

**Detail layers, added last.** Five were proposed and all five built, each an
independent flag: spin-up, engraved rims, parallax, character marks, hover drag.
Engraving then took three passes of its own — floating above the artwork, then
struck into the metal but crossing the cutouts, then correctly bedded in the band
but sitting on the arc as a baseline rather than centred on it.

## Decisions worth keeping

- **One imperfection, not seven.** A single fractured tooth reads as a machine
  that has been used. Marks on every wheel read as broken.
- **Blind pockets were a mistake.** A milled pocket at this scale looks like a
  hole that failed to punch. Every opening is now cut clean through.
- **The stamps are real notation.** `M7 Z17` is module and tooth count, the two
  numbers a machinist reads off a blank to know whether two gears will run
  together. They are generated from the values the solver actually used, so they
  stay true if a wheel changes.
- **Rim engravings carry the link.** Each wheel's band is struck with the handle
  it points to, so the rim tells you where the wheel goes — content without a
  link list.

## Rejected or not pursued

- Rendering each wheel once to a bitmap and rotating that. Offered as the next
  performance lever; not needed, since JS cost is ~0.1% of a core and the
  remaining cost is compositor rasterisation. Measure before revisiting.
- Sound.
- More elaborate imperfection variety (scuff, burr, worn face) — offered, left in
  the backlog.

## Left open

- No `prefers-reduced-motion` handling. The most substantive gap.
- Wear variety and optional bitmap caching, both in the backlog.

## Tweak state at handoff

Defaults: **spin-up on**, **hover drag on**, engraved rims / parallax / character
off, so each can be switched on one at a time. All five were verified rendering
together without errors before the defaults were set back.

Note: in the final session the accent was being previewed at `#E8483A` with
parallax off. Those were unsaved local preview values, not defaults — the
committed accent is `#3B7DE8`.

## Tooling constraint

There was no repository during any of this work, and no issue tracking. GitHub
access in that environment was read-only — browse, read, and diff, but no commit
and no issue creation. `CHANGELOG.md` was written at the end to back-fill the
fixes as numbered, citable entries, and this folder is the intended first commit.
