# Start here — prompt for Claude Code

Unzip this folder, `cd` into it, and paste the block below into Claude Code as
your first message. Everything it needs is in this folder.

---

You are taking over an existing, finished design: the wozi.com landing page. It
is a single-file animated gear train — seven meshed wheels, a roller chain and a
toothed belt, each wheel carrying one social link at its hub. `index.html` opens
directly in a browser and is the whole site; `support.js` is its runtime.

This is **shipping code, not a mock to reimplement.** Do not rewrite it in a
framework, do not extract a build step, do not restyle it. Read `CLAUDE.md`
before touching anything — it lists the invariants that keep the machine
mechanically correct, and they are load-bearing. Read `CHANGELOG.md` too: its 18
numbered entries are the bugs already found and fixed, and most of them are
mistakes that are easy to make twice. `SESSION-LOG.md` has the reasoning behind
the current shape of the thing, including what was tried and rejected.

Your first job is repository setup:

1. `git init`, commit everything here as the initial commit, and push to
   `github.com/csmarshall/wozi.com` on `main`. The remote exists and is empty.
2. Adopt `CHANGELOG.md` as the change log going forward. Entries are numbered and
   stable; keep numbering upward from #18 and reference the number in commit
   subjects (`fix: #19 respect prefers-reduced-motion`).
3. Using `gh`, create one issue per item in the Backlog section below, labelled
   `enhancement` or `a11y` as marked. Do not open issues for anything already in
   the changelog — those are done.
4. Confirm the page still renders and animates after the push: serve the folder,
   load it, and check that wheel transforms advance and `stroke-dashoffset` on
   the chain paths changes between two samples ~700ms apart. A static train has
   been the single worst regression in this project's history (#7).

Then stop and report. Do not start on the backlog until I say so.

## Icons and other assets

The seven hub icons are **not inlined** — they are separate files in
`assets/icons/<slug>.svg`, one per entry in `SITES` (`linkedin`, `github`,
`mastodon`, `instagram`, `threads`, `bluesky`, `mail`), fetched at runtime by
`loadIcons()` and injected into the badge. Two consequences to know before you
touch them:

- **They must be served over HTTP.** Opening `index.html` from `file://` makes
  the fetches fail silently and the badges come up empty; the page otherwise
  looks fine. Serve the folder.
- **They inherit colour.** Each mark is authored as a minimal single-colour SVG
  that paints with `currentColor`, so the badge tints it — brand colour at rest
  (the `BRAND` map), accent on hover. Do not bake fills into the files, and do not
  swap in multi-colour brand artwork without reworking that.
- `loadIcons()` rewrites each file's root `<svg>` to `width="100%" height="100%"`
  so it fills the badge regardless of the source viewBox. A missing or unfetchable
  file degrades to an empty badge rather than an error.

To add a link: add an entry to `SITES`, give a wheel that `slug` in `TRAIN`, drop
a matching single-colour SVG at `assets/icons/<slug>.svg`, and add a `BRAND`
colour. Nothing else needs to change — the solver picks the rest up. If you need
canonical brand marks rather than the simplified ones here, take them from each
brand's own press/brand-assets page; the current files are simplified glyphs
drawn to read at ~20px, not official artwork.

`assets/icons/flickr.svg` is deliberately not shipped — Flickr was dropped from
the link set. `assets/gears.png` was a reference image used while designing and is
not loaded by the page.

Also note: the wheel *rim* engravings are not icons. They are live text derived
from `SITES[slug].path`, struck into the band, so a changed handle changes the
engraving automatically.

## Backlog

- **layout — confirm the fit scale on a real large display.** The ceiling is
  `1.55` in `fitStage()`. 2.6 was tried and read as far too large; 1.15 was the
  original and made big screens render *smaller* wheels (see #19). Verify at
  ≥2000px wide and adjust the one constant — the `gearScale` prop is the quickest
  way to test a number before baking it in. `enhancement`
- **layout — train may sit right of centre at large widths.** Reported from a wide
  window; not reproducible at 924×540, where centring measures exact (stage centre
  462 === viewport centre 462). If it reproduces, stop relying on flex centring
  and centre the train's own bbox: the stage box is the tight gear bounds, so an
  asymmetric serpentine solve can shift the perceived centre even when the box is
  centred. `bug`

- **a11y — honour `prefers-reduced-motion`.** There is currently no check. The
  machine should come to rest and stay legible (engravings and hubs still
  readable) rather than freeze mid-tooth. `a11y`
- **perf — optional bitmap caching for wheels.** JS cost is already negligible
  (~0.02ms/tick); the remaining cost is the compositor rasterising rotated SVG.
  If a low-power device struggles, render each wheel once to a bitmap and rotate
  that. Measure before doing it. `enhancement`
- **detail — vary the wear marks.** Exactly one wheel has a fractured tooth. A
  scuff, a burr, or a worn tooth face on one or two others would reward a closer
  look. Deliberately not on every wheel: a machine with seven damaged gears
  reads as broken rather than used. `enhancement`
- **content — `SITES` is the content source of truth.** If link targets change,
  they change there and nowhere else. No issue needed; noted so you don't go
  looking for a CMS. 
