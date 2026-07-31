# Changelog

Every entry is one tracked change. Newest first. Numbers are stable — reference
them in issues and commits (`fix: #14 stamp hidden under specular arc`).

## Unreleased

### Added

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
