# Changelog

Every entry is one tracked change. Newest first. Numbers are stable — reference
them in issues and commits (`fix: #14 stamp hidden under specular arc`).

## Unreleased

### Fixed

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

### Added

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

### Fixed

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

- **#1 — Layers.** Five independent detail passes, each a tweakable flag:
  spin-up (train winds up from rest on the flywheel), engraved rims (each
  wheel's handle struck into its band), parallax (background wheels ~22% slower,
  set back, drifting against pointer movement), character (chipped tooth plus
  stamped `M<module> Z<teeth>` marks), hover drag (hovering loads the machine to
  ~40% speed).
