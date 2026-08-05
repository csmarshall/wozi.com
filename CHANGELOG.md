# Changelog

Every entry is one tracked change. Newest first. Numbers are stable — reference
them in issues and commits (`fix: #14 stamp hidden under specular arc`).

## Unreleased

### Changed

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
