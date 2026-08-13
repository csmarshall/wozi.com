# Changelog

Every entry is one tracked change. Newest first. Numbers are stable — reference
them in issues and commits (`fix: #14 stamp hidden under specular arc`).

## Unreleased

### Added

- **CL#194 — Wear's fracture gets its own drawn contour, because a silhouette was all it
  ever had.** (GitHub #146.)

  Charles: *"wear adjustments don't seem to be reflected in gears"*. **The mechanism was
  working and the marked wheels were inspectable — the mark was simply below the bar this
  codebase already sets.** Measured: full Wear moved **205 of 1,296,000 pixels (0.016%)**
  and removed **8.61px** of tooth flank on the deeper mark, **4.28px** on the shallower,
  against **`MIN_CUT_PX` = 10.3** — the floor a *cut* must clear here to read at all. On
  a phone it is 5.35px and 2.66px, the latter at the aliasing floor.

  Two escapes were closed by measurement before this was chosen. **Depth cannot fix it**:
  `fBot` bottoms out at 0.44 of the flank and below that you are authoring a different
  crack, which `CLAUDE.md` forbids. **Position is not the constraint either**: marks were
  measured landing both in mesh gaps and on open rim, and in the best case — open rim
  against the page — the 1:1 sweep was *still* indistinguishable across all five slider
  positions.

  **The fix is the one CL#133 already made for cut openings, whose fault was identical —
  a shape whose only contrast is its silhouette.** `ft.line` at `m * CHIP_INK_MUL`, drawn
  **outside** the clipped group (inside, the clip is `path + holes` under `evenodd` and a
  stroke on a hole boundary loses its inner half). `teethPath` stays the one home: a
  `chipOut` out-parameter is filled **from the same point strings `d` is concatenated
  from**, so the ink cannot drift from the cut.

  **The pixel count is the wrong headline, and the agent said so rather than quoting the
  flattering number.** It is a diff against the *unworn* render, and the old mark's
  biggest pixels were already saturated by silhouette — so the metric is nearly blind to
  what was broken. The measurement that matters is the mark's **absolute contrast against
  the ground it sits on**, from a single worn shot:

  | | wear 0 | any wear > 0 |
  | --- | --- | --- |
  | light, deeper mark | **2.00:1** | **4.07:1** |
  | light, shallower mark | **3.51:1** | **5.96:1** |
  | dark, both | 8.09:1 / 5.05:1 | **unchanged** |

  **Dark gains area; light gains contrast.** That inversion is the honest result and it
  is not a compromise — in dark the wheel-against-page edge is already the strongest
  thing in the box, and light is where the 35% contrast deficit lived. At **1:1 in light
  on a desk the mark is visible from 25% up**, where before there was nothing.

  **`CHIP_INK_MUL = 0.30` is bounded from above by a dark-theme fact, not by taste.** A
  heavier line begins to *fill* the notch rather than outline it: over the ladder
  0 / 0.30 / 0.45 / 0.60 / 0.90 the largest channel delta the mark moves goes
  **205 / 205 / 172 / 139 / 109**. So 0.30 is the heaviest weight that leaves the
  silhouette **exactly as strong as it was** while adding the ink, and past 0.60 the
  authored jag stops reading as a crack and becomes a blob.

  **Both stated guarantees proved rather than assumed.** Wear 0 is byte-identical to
  HEAD — `pixel_regress` **0px** on the stage, `?who=charles` and `--theme light`,
  controls 0px — and the wear-0 render is byte-identical across *every* rung of the ink
  ladder, so the contour is **absent** at severity 0 rather than faint. `WEAR_SCUFF_RATIO`
  and `teethPath`'s fractions are untouched, and with Wear at 100% the difference from
  HEAD is 208px desk / 90px phone in dark and 216 / 101 in light — the ink and nothing
  else, since both sides draw the same fracture.

  **The ink census is unchanged at Wear 100%**: 56 inks on the stage, 42 solo, 64 light,
  identical to Wear 0. `ft.line` is already on every wheel and is the darkest tone
  `flatTones` produces.

  **A phone at 1:1 still cannot show it**, stated rather than glossed: the weight is in
  modules so it scales with the wheel, and the wheel is 62% the size (`--gsfit` 0.867
  against 1.396), which puts the line near 1.8px. Accepted, because #5 asked for a detail
  that rewards inspection and it now does at desk scale. Flooring the weight in *pixels*
  the way `MIN_CUT_PX` is would make a phone's mark relatively heavier than a desk's, and
  that reopens the "correct at exactly one screen size" argument from the other side — a
  new decision, not this ticket's.

  **My own figures in the ticket were wrong**: *"205 px / delta 137 light"* paired a dark
  pixel count with a light delta. Per theme at HEAD it is dark 210px / Δ205, light 198px
  / Δ153.

  `npm test` 121/0. `a11y_audit` PASS both themes. `strip_comments --selftest` ok.

  **Two harness findings worth keeping.** `DETERMINISTIC_FLAGS` remove Chrome's licence
  to abandon an uncommitted frame, so `captureScreenshot` can hang under another agent's
  headless Chrome — and one killed run leaves its Chrome holding the `--user-data-dir`,
  which Chrome treats as a **singleton**, so every later launch hands its command line to
  the survivor and never listens on the new debug port. The symptom is a silent stall,
  not an error. And `--shot` mode has **no `stable_render` control**, so a single shot has
  no self-control: one run came back at 1,209px and was a raster flake, agreeing at
  210/210 on two re-shoots. The workaround — planting `wozi-wear` in localStorage the way
  `wozi-theme` is planted, and driving `pixel_regress`/`dom_invariants` themselves — is
  probably the cheap answer to **#177**: three ~20-line wrappers rather than a new
  harness.

- **CL#193 — the 93-minute deploy hang had a proven cause: a CDP round trip with no
  ceiling. And it was not the dropped socket I guessed.** (GitHub #174.)

  Both CDP session helpers — `pixel_regress.py`'s own copy and `fontpin.py`'s
  `attach()`, shared by six harnesses — were:

  ```python
  while not fut.done():
      await pump_once(30.0)      # 30s read timeout, retried forever
  ```

  **A timeout that cannot expire.** `READY_TIMEOUT_S`, `PANEL_TIMEOUT_S` and `settle()`
  all check their deadlines *between* round trips, so a single call that never returns
  never reaches the loop that would notice it. Both now carry `CDP_TIMEOUT_S` (90s,
  `WOZI_CDP_TIMEOUT_S` overridable), kill the browser, and exit **2** naming the CDP
  method.

  **My hypothesis in the ticket was wrong, and it was ruled out by measurement rather
  than argued down.** I guessed a socket that dropped without closing. `websockets`
  15.0.1 keepalive turns that into `ConnectionClosedError` in **48–50s**, measured by
  `SIGSTOP`ping a headless Chrome against HEAD's code. So a dead socket terminates on
  its own and cannot explain 93 minutes. What can is a Chrome that **answers keepalive
  pings and never answers the method** — wedged but alive. The new FATAL message says
  exactly that, so the next operator does not repeat my guess: *"The browser is wedged
  rather than gone (a closed socket raises instead)."*

  Proved, not reasoned: the deadline fires and names the method at exit **2** in both
  copies (`Page.enable`, verified independently in `pixel_regress` and via `fontpin`
  from `dom_invariants`); against a **real wedge** — `SIGSTOP` on the harness's own
  Chrome — `pixel_regress` exits 2 in 10s naming `Runtime.evaluate`; and HEAD's code in
  the same experiment ran 48–50s and died with an unhandled traceback at exit **1**,
  which is this tool's word for "the artifact moved".

  **The 90s margin is measured, not chosen:** a full healthy run still passes with the
  deadline squeezed to **2s**, and passes at 2s again under 6× CPU throttling. So 90 is
  45× the worst observed round trip.

  **Timing the gate sequence, serially**, which is what makes the workflow bounds
  measured rather than guessed: `node tools/test.js` 7.6s, `devices.py` 158–162s,
  `verify_motion` 4.8s, `pill_clip` 18.8s, three `dom_invariants` 1.3s each,
  `escape_mesh` 37.0s → **3m43 for the browser-gate step**; the five-run pixel battery
  14.6/14.1/8.6/14.8/11.0 → **1m03**. Worth recording: **the CI factor is ~1.4×, not an
  order of magnitude** — `devices.py` is 3m38 in CI against 2m40 here.

  Bounds added everywhere they were absent. `deploy.yml`: job **45**, with per-step
  bounds including **20** on the browser-gate step and **25** on the pixel battery — the
  per-step ones are what actually catch a hang *and name it*, so the job bound only
  needs to be safely clear of healthy. 45 rather than the ticket's suggested 30 because
  the measured healthy total is ~15 min in CI **of which the CloudFront invalidation
  waiter alone can be 10** — a path whose slowest part is somebody else's
  infrastructure. `mutation.yml`: `registry` **10** (it had none, so the 360-minute
  default applied), and the sweep gets a **step** bound of 40 *under* its job's 45 so
  the `if: always()` Summary still runs.

  `cancel-in-progress: false` is unchanged, with a comment saying why flipping it trades
  a stale bucket for a **mixed** one.

  Verified: `npm test` 121/0; `pixel_regress --ref HEAD` 0px, controls 0px;
  `mutation_gate --blind` 17/17 mutations still apply; both workflows parse and all **19**
  `run:` blocks pass `bash -n`.

  **Projected, not proved, and worth keeping separate:** workflow-level behaviour — that
  a step timeout cancels the job and names the step, and that a job timeout skips
  `if: always()` steps — is from GitHub's documentation, since an agent cannot push and
  so cannot trigger CI. And that run `31639824875` sat in *this specific* unbounded loop
  is inference: the loop is proved unbounded, the dead-socket alternative is ruled out by
  the keepalive measurement, and the step before it passed.

- **CL#192 — `/fidget/`'s grip spring diverged at 30fps, which is Low Power Mode; and
  the page now hears a collapsing URL bar.** (GitHub #164, GitHub #170.)

  **#164 — the grip was integrated explicitly, so `ζ = 0.28` was a claim about the
  continuous model and not about the page.** `ω_n·dt` is 1.0 at 60fps and 2.0 at 30fps,
  and forward Euler on a spring is unstable once the step is that large relative to the
  period. Measured on the real page at 30fps, a 60° twist then held still: the old code
  peaked at **4.98×** the finger's angle and **settled there** — 300° away from a finger
  holding perfectly still. At the 0.05s `dt` clamp it reached **7.45×**. Simulating the
  spring alone, with the page's other bounding terms removed, it diverges **without
  bound** (5.5×10¹⁹⁹ at 30fps, NaN at 20fps) — so 4.98× was not the fault's size, it was
  what the rest of the machine happened to contain.

  **Fixed in closed form** — the exact solution of the linear damped oscillator over
  `dt`, which is available because the finger's target is constant between pointer
  events. Two alternatives were considered and rejected with reasons:

  - **Clamping `dt`** runs the machine *slow* on the slow device, which is a different
    bug wearing this one's clothes.
  - **Semi-implicit Euler** was checked rather than assumed: its bound is
    `ω_n·dt < 2.64` at ζ = 0.28, which **still fails** at the 0.05s clamp (3.0). Closed
    form is unconditionally stable *and* `dt`-independent, so there is no threshold to
    sit near and no sub-step count to jitter between frames.

  | | 60fps | 30fps (Low Power Mode) | 20fps (the clamp) |
  | --- | --- | --- | --- |
  | before, peak | 1.90× | **4.98×, settling there** | **7.45×** |
  | after, peak | 1.38× | 1.31× | 1.38× |
  | after, settles | 1.000× | 1.000× | 1.000× |

  **`ζ` measured at 60fps is now 0.280 — exactly `HAND_DAMPING` — and `ω_n` 59.31
  against a model 60.** Those were assertions in the file; they are measurements now.
  Every quantity is flat across 60/30/20fps: **30fps behaves like 60fps.**

  `ω_n` and `ζ` are **derived, not restated** — `MODE.stiffness / p.inertia` and
  `MODE.damper(p) / p.inertia / 2`, read off the same two quantities the old torque
  expression used, so nothing new is written down and `HAND_FREQ / gear` is not
  re-asserted. All three damping regimes are handled including the **ζ = 1 limit**,
  where `sin(ω_d·dt)/ω_d → dt` and neither branch computes it — getting that wrong is a
  NaN into `S.angle`, and `HAND_DAMPING` is a constant a future hand may move.

  **The no-grip branch is arithmetically untouched**, so flick and coast are
  bit-identical: a 0.75× `REF_SPEED` flick coasts to rest after **8.400s** with total
  angle **113.199758027 rad** on both sides. `ringCheck`/`sunCheck` still pass, including
  on the sun-grounded path, where the same gesture gives 1.31× against HEAD's 4.98×.

  **#170 — one feature-guarded line**, beside the existing `resize` handler, using the
  landing page's solved pattern. `visualViewport` references in the file go 0 → 2.
  **Honest about what is and is not established:** the *asymmetry* is measured
  (`index.html` 6 references, this file 0), and the fix moves **0px**, which is the
  specific failure mode to watch for — a listener that fires on load rather than only on
  change. The *symptom* is unverified and cannot be verified here: headless Chrome has no
  browser chrome, so there is no toolbar to collapse. It is in because the cost is
  asymmetric, not because anyone reproduced it. `docs/MANUAL-CHECKS.md` check 12 remains
  the only thing that can close it, and it still needs a phone.

  `layout()` deliberately still measures `svg.clientWidth/clientHeight` rather than
  `visualViewport.width/height` — copying that half would risk integer-versus-fractional
  differences and a non-zero pixel gate for no verified gain.

  **`pixel_regress --path fidget/` is 0px at 90, 900 and 3000 frames, and that is the
  structural expectation rather than a miss.** The resting pose has no finger down, so
  `gripAdvance` is never reached and the free branch is the identical expression with
  `S.rate = 0`. Worth contrasting with the landing page's flywheel, where `_M`
  accumulates phase from a *drawn* integrator so a change can never be 0px: here the
  changed branch is not on the resting page at all. The two probes are the actual gate,
  and they agree digit-for-digit by two independent routes — the page's own `step()`
  executed in Node, and the real page in real Chrome with real pointer events on a
  virtual clock.

  `npm test` 121/0. `verify_motion` 0 console errors. `strip_comments --check` passes on
  this file, which is one of the two built artifacts. All four before/after screenshots
  are byte-identical.

  **`fidget/README.md` records several numbers this invalidates and was deliberately not
  edited** — the whole "one thing the fix does not reach" paragraph now documents a
  hazard that is gone, the carrier step-response row shifts about 2%, and the port-ratio
  row's 14.2× becomes **15.6×**, which is *closer* to `RATIO` = 15.17× than the old
  figure. `docs/MANUAL-CHECKS.md` checks 11 and 12 both need rewriting; check 12's claim
  that there is no `visualViewport` listener is now false.

- **CL#191 — `--in-place` asked git about the wrong tree, and the accessibility
  ruleset is vendored so no gate depends on anyone else's uptime.** (GitHub #171,
  GitHub #168.)

  **#171's root cause is not what the ticket guessed**, and the real one is more
  general. I suspected `--git-common-dir` indirection or a `.git`-directory walk;
  `REPO_ROOT` was already `dirname(dirname(__file__))`. The actual fault: **every git
  question was asked of the tree the TOOL lives in, while the answer had to be about
  the tree the FILE lives in.** `matches_commit()` ran
  `git -C REPO_ROOT diff --quiet HEAD -- <path relative to REPO_ROOT>`, so the moment
  those two trees differ the path handed to git exists in no commit and `git diff`
  reports "differs" for free.

  **The corollary is the useful part:** a worktree running its *own*
  `tools/strip_comments.py` always worked, because `__file__` was then inside it. So
  the trigger is **tool-tree ≠ file-tree**, and a linked worktree is merely the
  common way to produce that — which is why the symptom looked like a worktree bug
  and was not one.

  `locate(path) -> (root, rel)` asks `git -C dirname(path) rev-parse --show-toplevel`,
  with `realpath` on both sides so a symlink cannot skew the relative name, and the
  root and rel now travel together rather than being mixed from two sources. It also
  killed a duplicate: `rel` was computed twice from `REPO_ROOT` with two different
  slash conventions.

  **The guard it must not lose is proved intact**, which matters more than the fix —
  overwriting a source carrying uncommitted prose is the one version of this mistake
  nothing can undo. Verified with the main checkout's tool against a worktree: a
  clean file now **succeeds** where it used to refuse; a dirty file **still refuses**,
  and the message names the real path (`index.html`) instead of a
  `../../../../../Users/…` ladder; `--force` still overrides. A file in no git tree
  refuses with its absolute path.

  **CI cannot regress**, and the reason is worth stating: for a relative path in a
  clean checkout `--show-toplevel` returns exactly what `REPO_ROOT` returned, and if
  git refuses to answer at all (a container's "dubious ownership") the fallback lands
  on `REPO_ROOT` — today's behaviour precisely.

  **The idiom is shared but the bug is not.** `ROOT = dirname(dirname(__file__))`
  appears in six other tools; none computes a repo-relative path for a file handed in
  from elsewhere, so all six use `ROOT` as the tree they operate *on*.
  `strip_comments` was unique in taking an arbitrary file argument and then measuring
  it against its own tree. One genuinely worktree-hostile thing was found and left
  alone: `tools/palettes.py` hardcodes an absolute repo path plus a dead scratchpad
  path, so it would silently render the *main* checkout from inside any worktree. It
  gates nothing.

  **#168 — `tools/vendor/axe-core-4.13.0.min.js`, 580,491 B, committed.** Pinning the
  version (CL#182) fixed *what* was asserted; it did not stop an unpkg outage, a DNS
  failure or a runner with no egress from reddening a run with nothing here having
  changed — and this is the only automated check on contrast or target size anywhere
  in the tree.

  The blob is **byte-identical** to the temp-cached copy every green run so far was
  measured under (sha256 `c24f097b…`), so vendoring changed the ruleset's *delivery*
  and not the ruleset. Checked rather than assumed. **The filename is derived from
  `AXE_VERSION`**, so bumping the pin points at a path that does not exist yet and the
  run says so loudly — the cache-filename reasoning applied to a copy that cannot
  expire. Resolution order is `AXE_PATH` → vendored → `node_modules` → temp cache →
  network, with `node_modules` demoted below the vendored copy because its path
  carries no version.

  **One more exit-2 site**, the ninth of this family: an `AXE_PATH` that does not
  exist used to fall through to a silent network fetch — auditing under a ruleset the
  operator did not name while appearing to honour the one they did.

  **Verified with a control, because "needs no network" is unfalsifiable without
  one** — and my first attempt at that control was inconclusive, since removing the
  vendored blob alone still let the temp cache satisfy the run:

  | condition | result |
  | --- | --- |
  | normal | `RESULT: PASS`, exit 0, ruleset read off disk |
  | unpkg blackholed, blob present | `RESULT: PASS`, exit 0 |
  | blob **and** temp cache gone, blackholed | `RESULT: NOT AUDITED`, **exit 2** |
  | blob restored, cache still gone, still blackholed | `RESULT: PASS`, exit 0 |
  | `AXE_PATH` → a real 4.12.1 build | `NOT AUDITED`, exit 2, read-back refused it |
  | `AXE_PATH` → nonexistent | `NOT AUDITED`, exit 2, no fetch attempted |

  That fourth row is the decisive one: it audits with **no network and no cache**.

  **The blob cannot reach the web, verified against the publish commands rather than
  an exclude list.** Every publish in `deploy.yml` is an explicitly named file, plus
  exactly one `aws s3 sync` rooted at `assets/`. `tools/` is named in no publish
  command, and `git check-ignore` reports no rule matching `tools/vendor/`.

  `mutation.yml` gets a **comment-only** change: reason 1 rewritten as *spent*, with
  the measured evidence, and reason 2 left intact — **one pinned deal makes the
  verdict reproducible, not complete.** Moving the audit onto the deploy path is a
  separate decision and has deliberately not been taken.

  `npm test` **121/0**. `strip_comments --selftest` green, 2.86s.

- **CL#190 — every drive strand rode `_M[0]`, so the one-clock rule was broken for the
  dormant chain code.** (GitHub #175.)

  `applyRotation()` was already written for per-component clocks — it reads
  `this._M[c.comp != null ? c.comp : 0]` — but `chainEl()`'s ref tracker pushed only
  `{el, sign}`. So `c.comp` was always `undefined` and every strand fell back to
  component 0. The consumer was taught about the split; the producer never was.

  **And enabling strands is exactly what creates the extra components**, so the more of
  the dormant capability was switched on, the more of it was driven by the wrong clock.

  Measured, strands temporarily enabled, 18 tracked paths over 8 components:

  | | before | after |
  | --- | --- | --- |
  | `comp` on the 18 strands | `undefined` on all 18 | `[0,1,2,3,4,5]` |
  | advance `_M[5]` by 720°, strands changed | **0 of 18** | **3 of 18** |
  | which components | — | **only 5**; 0–4 untouched |
  | `_chainEls` after 2 renders | 36 entries, **18 null** | 18 entries, **0 null** |

  Reversal is symmetric at **±21.99px per 360 master-degrees**, which is π × `MODULE` —
  one circular pitch per tooth of travel, in whichever direction the drag runs. That is
  the invariant's own stated consequence and it now holds.

  **The 8-component seed is gone, and the projection about it was wrong in an
  instructive way.** `for (let c = 0; c < 8; c++)` had zero margin: today's config with
  every link stranded reaches exactly **8 of 8**. Pushed to 10 components it was
  reproduced — but the symptom is **`rotate(0deg)`, not `rotate(NaN deg)`**, because
  `NaN || 0` is falsy and `applyRotation()`'s own fallback writes zero. So the mesh
  snaps to angle 0 and restarts from 0 next tick with its accumulated phase discarded.
  **A NaN that drew would at least have been obvious.** The bound is derived from the
  solve now; nothing knows the count except the solve.

  **Why this rotted unnoticed, which is the general lesson:** dormant code is covered by
  no gate. `verify_motion` cannot check a strand that does not exist and the pixel gate
  photographs a page without one, so per-component `_M` (CL#142) moved an invariant out
  from under code nothing exercises, with no signal at all.

  **`verify_motion` is also insufficient here and would not have caught it**, which is
  worth stating rather than assuming the harness has it covered: its
  `dashoffset values: N sampled, N changed` is an **aggregate**, and every strand riding
  `_M[0]` still moves — so it reports N of N while most strands are on the wrong clock. A
  per-component variant would have to group sampled dashoffsets by the driver's
  component; the awkward part is that it has no handle on the logic instance and reaching
  it needed a React fiber walk, which wants a test-only accessor rather than fiber
  archaeology.

  Also corrected in `index.html`: two comments the #147 prototype disproved — the
  "seven site wheels" count (`TRAIN` is generated from `CHAIN_ORDER`/`PEOPLE`, so a
  `link` must be computed in the generator, and `tools/test.js` executes that builder in
  Node with an injected declaration list) and the claim that re-enabling *"stays a
  one-line TRAIN edit"*. The `link` also goes on the **receiving** wheel, which is now
  said where somebody re-enabling it will read it.

  Verified with strands **off**, which is the shipped state: `npm test` **121/0**;
  `pixel_regress --ref HEAD` **0px** on the stage, `?who=charles` and `--theme light`,
  controls 0px — that 0 is what proves the change is inert on the live page.
  `dom_invariants` PASS dark and light, **2 components**. `verify_motion` PASS,
  `strands: none (correct for the direct-mesh train)`.

  **One mechanical problem deliberately left to #147**, because it is that ticket's
  design question rather than this one's bug: `solve()` places a linked wheel at
  `(prev.r + r) × spread`, and the union-find only unions pairs at `r1 + r2` — so a
  strand's driver and driven sprocket land in **different components by construction**.
  Recording the driver's component is correct and is what makes the test above pass, but
  the consequence is that dragging the driver travels the strand while the driven
  sprocket does not turn. A real roller chain cannot do that. Unioning the pair would
  collapse the very multi-component condition this fix is verified against, so it is a
  question about whether a strand makes two wheels one machine — and it decides what
  `dom_invariants` check 1 should assert.

- **CL#189 — a short scored index mark on every ghost wheel's raised face, on by
  default.** (GitHub #148.)

  Charles: *"add default timing mark - but not full line - on ghost gears outer ring"*.
  Three things in that sentence were load-bearing and all three are honoured: **ghost**
  wheels (not the linked train), the **raised-face ring** (not the well), and **not a
  full line** — a scored mark with a punch dot, `GHOST_TIMING_SPAN = 0.60` of the ring's
  depth, chosen by Charles from a 12× seven-panel sweep against 0.50 (the dot alone),
  0.70, 0.85, 1.00 and a line-only variant.

  **The first of #125's three layers to ship ON**, via a new `ghostTiming` prop with
  `default:true` read through `layerOn()`. The existing `timing` prop stays `false` —
  flipping *that* would have marked every linked wheel too, which is not what was asked
  for.

  **No fourth checkbox**, deliberately: CL#154's third row left only 2px of safe-area
  clearance on the shortest landscape phone, so a fourth would very likely re-fail
  `devices.py`. Charles asked for a default, not a control, so `ghostTiming` follows
  `character`'s half of the pattern — schema default, no `storedFlag`, no row.

  **`timingMark()` had to move before it could be shared.** It was a local `const`
  inside `gearSvg`, so the shape itself was unreachable from the ghost renderer; it is
  at module scope now with its proportions named (`TIMING_STROKE_MUL`,
  `TIMING_DOT_MUL`, `TIMING_ALPHA`). It reads no `this`, so it stayed a free function —
  which keeps all three existing call sites unchanged, including one inside a plain
  `function(){}` IIFE where `this` is not the page. The three inline `Math.max` radius
  literals in `ghostSvg` are named too (`gFaceR`/`gWellR`/`gBossR`).

  **Both ghost classes get the mark, with no `role` test.** Bridge and origin idlers
  versus escape-run outriggers are opposites in the **solve** — one may move a chain,
  the other may not move anything — and `CLAUDE.md` is emphatic that they must never be
  merged there. But in the **paint** they are already one renderer, one palette, one
  dimming, and a mark is a property of a drawn wheel. Nothing here moves a wheel.

  **A bug in the tuning itself, found by the sweep and worth recording**: the constant
  was first defined as the *line's* length, and at 0.62 the resulting shape covered
  **94%** of the ring — the dot adds its own diameter past the line's end and the round
  cap adds half a stroke past the other, so the number in the file and the number on the
  page were different quantities. Redefined as the **whole mark's extent, dot
  included**; a per-ghost probe confirms **60% of the ring on all 19 ghosts at both
  viewports**, +3.36 units of inner clearance, contained. Usable range is 0.47 (the dot
  alone) to 1.00.

  Drawn **inside** the alpha'd group — outside it would paint at full strength over a
  bridge idler's opaque backing plate — and in `ft.line`, an ink already censused.
  **`dom_invariants` reports 56 inks dark / 64 light / 42 solo, all unchanged**, which
  is the check that would have caught a new literal colour.

  Verified: `npm test` **121/0**. `dom_invariants` PASS ×3. `escape_mesh` PASS, worst
  residual 0.0162px of 0.35. `a11y_audit` PASS both themes. `verify_motion` PASS, 0
  console errors, strands correctly absent. `pill_clip` PASS, worst overrun −0.58px.
  `pixel_regress` **674px stage / 142px solo / 697px light**, controls **0px** on every
  run — non-zero forever after by design, since a default-on layer is now part of the
  picture. The solo figure is smaller *for a reason worth stating*: that page has **0
  structural idlers**, so only escape-run outriggers are marked there, against the
  stage's 2 idlers plus 17 outriggers.

  **Frame budget, which the ticket asked about:** `?hud` with the layer on versus off
  gives tick ms **33.4 p50 / 49.9 p95** against **33.3 / 50.0**, 7 drops both. Under
  `render_cost --throttle 6` `ghostSvg` is 1.5ms of a 139ms task, and tree-vs-HEAD
  totals sit **inside** a 21% run-to-run variance measured on identical code — so the
  honest verdict is **"not resolvable above noise"**, not "free".

  The mark is ~3× stronger in light than dark (max channel delta 36 vs 12), straight off
  `ghostOpacity`'s 0.46 against 0.17 — a consequence of the existing ghost paint, not a
  new decision.

- **CL#164 — the datum label is etched clear of an unbroken rule, on one side for
  every chain.** (GitHub #139.)

  Charles: *"change the datum label to a label that looks etched into the
  background ... so the datum line looks like a piece of the system we're looking
  at."* Then, on seeing five candidates: *"the name could be slightly larger and
  etched either below or above the line - almost as a marker added after the
  fact."* The plate is gone; the scribe runs unbroken; the name stands off it in
  relief at 1.3x, cut copy raised and lit copy dropped, which is `engraving()`'s
  own vocabulary and obeys the overhead-lighting rule (#10).

  **The plate was costing contrast, not buying it.** Its `--hair`-derived fill sat
  between the ink and the page, so removing it RAISES the ratio in both themes —
  1.56/1.50 to **1.64:1 in both** — and closes the light/dark gap. The "faint
  versus legible" tension this was expected to trade against does not exist here.
  Contrast is also size-invariant by construction, not by luck: the hairline is
  `fs × ENGRAVE_STROKE`, so the stroke-to-glyph ratio cannot move with the size.

  **The side is DERIVED, and the switch that used to choose it is gone.** No `+1`
  appears anywhere: both candidate sides are compared against a direction taken
  from the spine's own outboard normal, which itself comes from a seat that already
  compared both origins. That is the compare-never-assert construction the bridge
  handedness fix arrived at, and this is the third piece of geometry to need it
  (#67, the bridge's sign, and nearly this) — a legal mirror image passes every
  measurement taken along the axis, so the handedness has to be derived or it is
  guessed. It is axis-relative rather than screen-absolute, so rotating the stage
  in portrait turns the answer with it.

  **One side for N chains, because Charles caught that outboard-of-its-own-chain
  does not generalise.** The first implementation put each name outboard of the
  chain it named, which measured *better* (+14 to +28px of clearance) and looked
  correct with two chains — and would scatter labels across both sides with no
  inferable rule once `CHAIN_ORDER` carries more. Verified consistent at **2, 3 and
  4 chains**, at both viewports, using staged config copies; the checkout's
  `config.js` was never touched.

  **The referent is the assembly, not the origin corner, and that was measured
  rather than assumed.** Away-from-origin is `BRIDGE_BEARING`'s own referent and
  was the obvious guess, so it was implemented and measured first: on this
  composition the datum is scribed on the side of its chain *nearest* that corner,
  so away-from-origin puts the name toward the machine and **every** chain loses —
  the spine by 17.3px, with lettering over metal where the chip had cleared. Away
  from the assembly instead: Charles +24.1, Harper +27.9 at 1440x900, Charles
  +15.4 on a phone, and **Harper on the phone down 10.0px** — one chain out of four
  chain-and-viewport pairs, stated because it is the trade being bought.

  Known and accepted: the assembly referent is consistent *within* a composition
  but its screen side can **flip as chains are added** (above at 2-3 chains, below
  at 4). Adding a chain re-solves the whole composition anyway, so a label side
  moving with it is consistent with everything else moving; the origin referent
  would be stable across chain count too, and is left as a one-line swap with the
  measurement written at the site.

  `PLATE_TOP_CLEAR` is untouched and now documented as bounding **the scribe's
  standoff rather than the label's** — with the mark offset, the real outer edge is
  33-39px against a figure stated as 20. Filed as **#141** rather than fixed here,
  because making `datumClear()` pay the mark's true reach pulls the scribe toward
  the teeth and moves every datum line at every viewport.

  `npm test` 119/0. `pixel_regress` **14,588px** across the two viewports, control
  0px, fonts pinned, no harness warning — intended, and the record of what moved.
  `?who=charles` **0px**, correct by construction: a solo page draws no datum at
  all, which is also the trap that made the first sweep photograph nothing.
  `a11y_audit` PASS both themes, with 16/16 SVG `<text>` already hidden from the
  a11y tree — chain identity reaches a screen reader through the link names, never
  the plate — and the relief copies carry `aria-hidden` so they could not treble an
  announcement. `verify_motion` 40/40 with 0 console errors; `dom_invariants` 2
  components, no orphans. Frame cost unchanged at 33.3ms p50, 0 dropped ticks.

- **CL#161 — `/fidget/` shows one set at a time, and the shaft is how you travel
  between them.** (GitHub #129, parts 3 and 4 — the ticket is now complete.)

  Charles decided one gear at a time and a swipe to change grounding. The question
  the ticket could not answer in advance was what happens to the `ONE SHAFT` tie,
  because that tie carries the whole compound-train story: stage 2's sun IS stage
  1's carrier.

  **The tie became the control.** It stays as a stub leaving the frame, and a tap,
  Enter or Space on it walks to the other stage — labelled with what is at the far
  end (`ONE SHAFT → SET 2 · CARRIER`), read off the live mode so it can never
  describe a grounding the page has left. Following a shaft to its other end is
  what a shaft is for. Rejected: deleting it (the readout would keep quoting
  15.167:1 for a train no longer drawn); stub-plus-caption (points at a stage
  nobody can reach, and makes the *heavy* port — the whole demonstration —
  button-only); and concentric superposition, already rejected at #123 because
  orbit radii of 21 and 19.5 units interleave into an unreadable mess.

  **`useView()` deliberately does not zero `S`, and `useGrounding()` does.** Same
  machine seen from elsewhere versus a different machine: a coasting train keeps
  coasting across a view change and every redrawn body lands on the phase it would
  have reached anyway, whereas a grounding swap must reset, since 40 rad of sun is
  not 40 rad of ring.

  **The swipe hit-tests through `portAt(p) === null`** — the existing test, now
  answering both questions. There is one grabbable disc and `layout()` decides
  where it is, so a region-based swipe zone would be a second opinion about that.
  Threshold is `0.12 × min(innerWidth, innerHeight)` with a 1.5× vertical bias,
  committing on move and disarming so one drag is one swap. Keyboard route is a
  `ground` button plus `g` and Shift+Up/Down — Shift tested first, so unmodified
  arrows still flick the port.

  **Two faults only a picture could catch**, both now commented: the rotated
  portrait label had its anchor copied from the landscape branch, so it read back
  down over its own gear (the rotation already carries the direction); and `↑`
  inside a −90° rotated label renders pointing **left**, so the rotated branch
  writes `→` and lets the rotation aim it. Also fixed: the label's fit was measured
  before the browser's first full layout, so `layout()` now runs once more on
  `load`.

  Verified: zero console messages through every gesture in both groundings; 8 of 10
  transform groups advancing (the two static are the set translate and the grounded
  member's phase); the static phases **swap from rings to suns** at DOM level;
  `S.angle` confirmed zeroed on a grounding swap, with set 2's ring landing on
  `rotate(-3.000)` = −π/60, its own `ringPhase` exactly. A 300px drag **starting on
  the gear** does not swap and spins the train instead (+7.03 → −7.62 rev/s), and
  four off-gear negatives (88px, horizontal, diagonal, tap) also do not.
  `npm test` 119/0; root-page pixel gate **0px**, so this folder stayed inside
  itself. The fidget gate moves ~502k px by design — one set instead of two, drawn
  larger (527px → 630px across at desk) — attributed by ink dropping 274,242 →
  202,563 px rather than a band shifting.


- **CL#159 — the bucket gets the machine, the repo keeps the prose, and the
  gates moved onto the artifact.** (GitHub #113.)

  `tools/strip_comments.py` has existed and worked for a while and was
  deliberately not wired into the deploy: publishing something other than the
  file in the repo changes what "the repo is the source of truth for
  s3://wozi.com" means, and its own docstring called that "a decision with a
  gate on it, not a side effect of adding a tool." Charles took the decision.
  This is the gate.

  | | source | delivered | saving |
  |---|---|---|---|
  | `index.html` raw | 602,972 B | 188,901 B | 68.7% |
  | `index.html` brotli | 172,917 B | 45,435 B | 73.7% |
  | `fidget/index.html` raw | 38,329 B | 20,646 B | 46.1% |
  | `fidget/index.html` brotli | 12,091 B | 6,123 B | 49.4% |

  **The stripped page stays navigable back to the source.** Charles: *"do we
  want to have the script inject references back to github to individual
  methods in the code so that someone could easily go from one to the other?"*
  A full URL at each of the 709 sites would be ~57KB — a third of the delivered
  file spent saying the same thing 709 times — so the URL is carried ONCE in the
  banner and each site keeps only `/*L1234*/`, the line it stood on. `#L1234`
  on the banner's URL is the comment that used to be there. Measured cost:
  7,146 B raw / 2,517 B brotli, 3.8% of the delivered file against a 68.7%
  saving, so per-comment resolution was affordable and the coarser per-method
  fallback was not needed. The marker syntax follows the SITE, not the file —
  `<!--L1234-->` in markup, because `/*L1234*/` in a document body is text on
  the page.

  **The banner links to a repo that is now public**, which landed the same day
  (the PII history rewrite completed, verified from an anonymous clone). The
  tool shipped with a caveat that the reader would meet a GitHub sign-in wall —
  pointing the public at a door they cannot open being arguably worse than
  pointing them nowhere, which is why the caveat was written in the first place.
  It is gone, and `--selftest` now asserts it STAYS gone: it was true for the
  whole life of the tool, so it is exactly the sentence somebody restores from
  memory. `--repo-url` remains for a rename or a mirror.

  **The URL is pinned to the deployed commit.** `blob/main/index.html#L1234`
  names a line that moves the next time anything above it is edited, which would
  make the marker a drifting constant published 709 times over. The SHA is
  `github.sha` in CI, `git rev-parse HEAD` locally, and a build from a working
  copy that differs from that commit SAYS SO in the banner instead of implying a
  precision it has not got.

  **The gating is the order of the steps, not a second set of checks.** The real
  risk here is the one CLAUDE.md names: a transform between the repo and the
  bucket means the reviewed file and the served file are two different files, and
  every gate in `tools/` ran against the first one. So the strip runs over the
  deploy's OWN CHECKOUT (`--in-place`) before Chrome and before any credential,
  and `npm test`, `devices.py`, `verify_motion.py`, `dom_invariants.py` (both
  scopes), `pill_clip.py` and `escape_mesh.py` all measure the artifact with not
  one line changed in any of them — a harness that had to be told about
  stripping would be one that could be told the wrong thing. `npm test` runs
  twice, source and artifact, because it is the only gate that reads the page as
  TEXT and so the only one that could notice a strip that left the drawing
  correct and the file unparseable.

  **`pixel_regress.py --ref HEAD` is the bridge, and 0 is the only passing
  answer**: working tree is the artifact, HEAD is the source, so the transform
  may change every byte and must change no pixel. Measured 0 px at 1440x900 and
  390x844 on the combined stage, 0 px on `?who=charles`, and 0 px on `/fidget/`
  through the new `--path`. Two smaller fixes fell out of using it this way. It
  now exits 2 rather than 0 when it cannot diff — a missing Pillow printed
  "cannot diff" and passed, so the strongest gate in the tree could go green by
  not running — and `--path` exists because `--query` cannot reach a second page
  and a separate harness for `/fidget/` would have been a second thing to keep in
  step.

  **What that catches is the failure a stripper actually has.** The versions that
  stop parsing are caught by the tool's own `node --check`; the version that does
  not is caught by nothing else in the tree.
  `tools/mutation_gate.py --only stripper-ate-a-line` is the standing proof —
  one line of props deleted out of an object literal (#36's engraving hairline)
  is valid JavaScript, meshes identically, turns, fits every viewport, passes all
  119 of `npm test`, and moves **2,933 pixels**.

  **`--in-place` refuses on a file that differs from HEAD.** Overwriting a source
  carrying uncommitted prose is the one version of this that nothing undoes. A CI
  checkout is clean by construction, so the guard only ever bites on a laptop —
  which is exactly where it matters.

  `keybase.html` never goes near the stripper: its body is signature-covered, so
  it is served byte-exact or the ownership proof stops verifying. `robots.txt` is
  still asserted byte-identical to the repo copy. The publish whitelist is
  untouched and still a whitelist — nothing new is reachable over HTTP, and the
  intermediate is the checkout itself rather than a new file that would have to be
  kept off the list. One assertion was added to the live-site checks:
  `blob/<github.sha>/index.html` must appear in the served body, which in one
  substring says the object is the artifact rather than the source, is THIS
  commit's artifact rather than a stale one, and still carries the markers that
  are a visitor's only route to the documentation.

- **CL#158 — `/fidget/` can be grounded at the sun instead of the ring, and the
  inertia model is now honest about the parallel-axis term.** (GitHub #129,
  part 2 of 4.)

  Charles decided "the other format" means **swapping which member is
  grounded**, so Willis is now solved twice: ring-pinned (shipped, unchanged)
  and sun-pinned, `ω_r/ω_c = 1 + N_s/N_r`. `sunCheck` mirrors the existing
  `ringCheck` and, like it, reaches its member down the *other* mesh, so it
  cannot merely restate the line that set the speed. Both were mutation-tested —
  perturbing a stage ratio by one part in 10⁶ makes each throw — because an
  assertion that cannot fail is not an assertion.

  **The compound shaft has to move, and that is not a substitution.** Ring-pinned
  it is carrier 1 → sun 2; sun-pinned it must be carrier 1 → ring 2, because
  grounding both suns would pin sun *and* carrier on set 1 — two constraints on a
  2-DOF set — and the train becomes a solid object.

  **The reflected-inertia claim survives but goes quiet, and Charles accepted
  that knowingly:** 230.0× becomes 3.3×, 15.1667:1 becomes 1.8200:1. It is a
  hard bound rather than a tuning failure — every buildable set has
  `N_r = N_s + 2N_p`, so sun-grounding can never reduce as much as 2:1 and can
  therefore never reflect more than ~4× however teeth are chosen. That argument
  is written into both the page header and the README so it is not re-litigated
  later as a bug. Neither figure is written down; both are still `RATIO²`.

  **Assembly phasing is unaffected, explicitly.** `planetPhase`/`ringPhase`
  describe where teeth sit at angle zero — the assembly standing still — and the
  assembly is the same parts however it is later bolted down. Both groundings
  share those expressions unchanged and draw the identical picture at rest.

  Two things re-deriving exposed. A ring's rotational inertia **was never
  modelled**, legitimately — a body at zero speed cannot be got wrong — and now
  is (`ringInertia`, an annulus as disc-minus-hole); rings turn out to be two
  thirds of the sun-grounded train. And `disc(r)` was `r⁴`, standing for
  `J = m·r²`, which is harmless while every disc shares one arbitrary constant
  and **not** harmless the moment a body's inertia is weighed against a
  parallel-axis term that carries no such factor. `disc` is now `r⁴/2`
  (`J = ½m·r²`); `m·d²` was correct all along and was never the error. The
  theorem restated correctly: **a planet's orbital term is exactly twice its spin
  term**, in both groundings, because it rolls on whichever member is stationary.
  It came out 1:1 before, and the missing half was the whole of it.

  `J_eff` therefore moves 45,638 → **27,466** ring-grounded and 846,826 →
  **469,735** sun-grounded, and `HAND_STIFFNESS` with it. **Nothing the page does
  changes:** `J_eff` enters only as a scale and cancels exactly out of every rate
  (a flick adds `REF_SPEED × 0.75 / gear`, in which it does not appear), verified
  empirically by alternating pre/post runs — post-flick sun speed 6.29/6.34/6.39
  against 6.28/6.29/6.29/6.33/6.34 rev/s, one overlapping spread set by where in
  the coast the sample lands.

  `GROUNDED` stays a source constant, exactly as `ORIGIN_MOUNT` does, and
  deliberately **not** a URL parameter — a second switch reachable from the
  address bar is a second way for the page to draw something no gate
  photographs. Nothing reaches it yet: the swipe is part 3.

  Verified: both modes boot over HTTP with zero console errors, 16 of 21
  transform groups advance over ~700ms in each (the 5 static ones are the
  coupling label, two set translates and two phase rotations), and those two
  static rotations visibly **move from the rings to the suns** in the DOM when
  grounding swaps. Rendered SVG with transforms stripped is **byte-identical**
  to before at 32,863 bytes with zero diff lines, which is the check that
  distinguishes "the model changed" from "the picture changed". `npm test`
  119/0. Every ring-grounded number in `fidget/README.md` reproduces.

### Fixed

- **CL#188 — the datum seat searched a box the label no longer occupied, and
  `GHOST_ALPHA_LAYER` was a second home for two numbers.** (GitHub #162, GitHub #163.)

  **#162 — the seat now searches what it draws.** CL#166 reversed which side the label
  sits on and CL#164 replaced the plate with an unbroken scribe plus relief lettering,
  so the clearance search was reserving space around geometry that had moved. This is
  the INBOARD half of #141, whose outboard half was `datumClear()` paying 20% short of
  the tick length. `markOffset(side)` is derived **before** `plateSeat` and handed over
  on the run; `plateSeat` builds a plate origin per candidate and `window_`,
  `plateExcluded` and `plateAir` all read it. `edgeOf()` and the viewport clip still
  read the *line*'s origin, because the scribe is still drawn on the line. One
  derivation, not a searched copy and a drawn copy.

  **It moves the drawing, which is the proof it was wrong before.** Across 5 seeds × 2
  viewports on the combined stage: on the desk Harper's stamp slides a uniform
  **−13.98px** along its run — the offset, finally paid — and Charles is unchanged on 4
  of 5 seeds, sliding 119px on seed 17 to find a clean window. On the phone Harper's
  mark **changes side**, onto the mirrored origin and down the run. In the before shot
  the drawn label sits over a ghost wheel's teeth at the top of the frame; after, it
  sits in clear air. That is the guarantee the search had been claiming.

  **Zero `wozi:` warnings on either tree**, all 10 combinations — no "neither side", no
  "no uncrowded seat", no overlap. So the stricter search still finds a clean seat
  everywhere; the difference is that HEAD was clean about a box it was not drawing.

  **#163 — the direction of the derivation was decided by the harness, not by taste.**
  `tools/test.js` lifts `ghostOpacity(theme)` out of `index.html` as *text* and runs it
  through `new Function` with nothing else in scope, at three sites — so a constant
  referenced from that method body would throw a `ReferenceError` there. The method had
  to stay self-contained, which meant the **constant** had to go, not the other way
  round.

  That forced the real structural fix. `GHOST_OFFSET_L` and `GHOST_LIGHT_PAINT` were
  module-scope `const`s evaluated before the class exists, which is *why* the two
  numbers were written twice in the first place — TDZ, not carelessness. They are one
  memoised module function now, `ghostLightPaint(aDark, aLight)`, called from
  `ghostSvg`'s `mirrored()` at the first moment in the page's life when the one home is
  readable. Memo keyed on the alpha pair, so the 40-step bisection runs once per page
  and **re-runs by itself if either alpha is ever retuned** — which is the property a
  duplicated constant cannot have.

  Isolated and proved pixel-neutral: `--theme light --query '?who=charles'` is the only
  path that reads the mirror table, and a solo page draws no datum, so #162 cannot
  contaminate it — **0px at both viewports, controls 0px.**

  Also removed: `let markDir = null;` in `datumLayer` was **dead** — declared, never
  assigned, never read, referenced only by its own comment claiming it was "filled in
  from the spine on the first pass through the loop". No tool references it.

  Verified: `npm test` **121/0**. `dom_invariants` exit 0 on stage, solo and light.
  `escape_mesh` PASS. `a11y_audit` PASS both themes. `pixel_regress` **5,372px on the
  combined stage** — the datum move, intended — and **0px on `?who=charles` in both
  themes**, which is what confines the change to the datum and isolates #163.

  Two findings filed rather than folded in: **#172**, the `DATUM_MARK_SIDE` note
  describes a spine comparison no code performs — and #162's phone result makes that
  prose wrong about its *outcome* too, not just its mechanism — and **#173**, the
  station ticks stand `MODULE * 1.2 * S` outboard of the box `window_` guards and
  nothing bounds them, landing at 376px of 390 on the phone.

- **CL#187 — the stripper's self-check could not see a comment it had failed to find,
  and it silently deleted from inside a string literal.** (GitHub #161.)

  **The circularity was real and the ticket described it correctly**, but two of its
  other claims were wrong and the corrections are the more useful half.

  `comment_spans("<script>const x = a++ / 2; // note</script>")` returned **no spans**:
  `++` was tokenized as two divisions, the `/` after it opened a phantom regex, and the
  `//` was consumed inside it. The comment survived into the artifact and `verify()`
  returned clean — because `verify()` derives its expectation from the same scan that
  produced the output. A check that asks the scanner to grade its own homework.

  **"It is deletion-safe" was false, and this is the fault that mattered.** A `/`
  misread as a regex opener leaves the cursor wherever the phantom literal ended, and
  the scanner reads on from there. Measured, old tokenizer:

  ```
  <script>let n = i++ / 2; let s = 'x /y/ /* z */ w';</script>
    ->    <script>let n = i++ / 2; let s = 'x /y/  w';</script>
  ```

  It deleted `/* z */` **out of the middle of a string literal**, and the result still
  parses — so `node --check` cannot see it and only the pixel gate can. That is the
  stripper doing exactly what `mutation_gate --only stripper-ate-a-line` exists to
  prove is catchable, except for real and in the shipped tool. A second case
  (`if (a) /x/*y/`) ate to end of file, which `node --check` does catch. The
  docstring's claim was wrong in both directions and is rewritten.

  **The ticket's own proposed fix does not catch the ticket's own example**, which is
  worth recording: "blank the spans on both sides and require byte equality" returns
  *equal* for the `a++` case, because the span was never located, so the surviving
  comment is present and identical on both sides. It went in anyway as `verify_delta`,
  for a different fault class, and its docstring says which.

  **Six checks, each demonstrated going red** by disabling it and re-running
  `--selftest` — the standard this repo holds a gate to, applied to the gate's own
  checks: `css_leftovers`, `css_structure`, `js_leftovers`, `verify_delta`, per-file
  `REQUIRED_MARKERS`, and the `++`/`--` tokenizer fix.

  **CSS was the uncovered half and now has two checks.** `node --check` is a JavaScript
  parser and says nothing about a stylesheet. After a correct strip both published
  stylesheets contain **zero** `/*`, `*/` or `//` outside strings and markers —
  measured — so "no comment survives here" is absolute and needs no tokenizer opinion.
  The ordered census (138 entries on `index.html`, 50 on `/fidget/`) is what notices a
  declaration eaten out of `:focus-visible` or `@media (prefers-reduced-motion)`, which
  a net brace count structurally cannot.

  **The JS leftover check is genuinely independent, because node is the oracle rather
  than the scanner.** Each non-marker `//` or `/*` is perturbed in a way that is inert
  inside a comment and fatal inside a string, template or regex; 10 hand-built probe
  cases pin it, including a `//` inside a multi-line template literal, which a naive
  delete-to-EOL probe misclassifies. Real candidates: **0** in `index.html`, **1** in
  `/fidget/` (`'http://www.w3.org/2000/svg'`), correctly judged not a comment.

  **And the new check immediately found a latent bug of the same species.**
  `script_bodies()` used `re.finditer(r'<script\b')` — the exact trap the module
  docstring warns about for `comment_spans` — and `fidget/index.html` says *"The
  `<style>` block below carries…"* inside a comment, so the count came out 2 in source
  and 1 in output. `index.html` was passing by luck: three `<script` occurrences, all
  real tags. Both extractors walk the document now, and the case is in the fixture.

  Cost, stated: `--selftest` goes **0.19s → 3.13s**, about 60 memoised `node --check`
  calls, on the deploy path. That is what a standing proof costs.

  Verified: `--selftest` ok. `npm test` **121/0** on the source and on the stripped
  artifact — the only gate that can see a strip which leaves the page drawing correctly
  while making it unparseable to the tools that read it. `pixel_regress --ref HEAD`
  **0px** on the stage and **0px** on `/fidget/` against a stripped tree.
  `mutation_gate --only stripper-ate-a-line` still **CAUGHT** at 2,933px.

  **Deliberately not closed:** a well-formed span in the *wrong place* still cannot be
  caught lexically. That remains `node --check` plus the pixel gate, and the docstring
  says so rather than implying these checks make the pixel gate optional.

  Two things found on the way and filed rather than folded in: **#171**, `--in-place`
  refuses inside a linked git worktree because it resolves the repo-relative path
  wrongly — which is where subagents work, though CI's ordinary checkout is
  unaffected — and the size figures in `CLAUDE.md`, now corrected: `index.html` is
  **687,760 → 196,704 B raw** and **196,733 → 47,445 brotli**, with markers costing
  7,783 B (4.0%) over 770 comments.

- **CL#186 — `pill_clip` was the fourth harness dealing through the page's own
  `?seed`, and it carried the eighth exit-code lie.** (GitHub #167.)

  The last of the four. `SEED_JS` read `/[?&]seed=(\d+)/` off `location.search` and
  the navigation appended `&seed={SEED}` — so `DEAL_SEED`, which runs at module scope
  *after* any injected script, dealt every machine this gate has ever measured, and the
  injection was dead code. Now `dom.seed_js(SEED)` with no `seed=` on the URL, the local
  copy deleted, and the comment rewritten: it used to assert it seeded *"THE SAME WAY
  `tools/devices.py` AND `tools/dom_invariants.py`"* do, which was true when written and
  went false in the other direction at CL#180.

  **Two of the ticket's own premises were wrong, and the more useful correction is the
  second.** It asked for the webfont to be pinned here — **already done in CL#168**,
  verified rather than assumed (`fonts: PINNED — 7 object(s) prefetched … every render
  verified 'applied'`). And it called this "a one-line change plus a comment", which
  understates it — not because of the font, but because of what determinism needs to be
  *checkable*.

  **A `--seed` flag and three census lines, because without them the two halves of a
  determinism claim are indistinguishable.** The seed was a buried constant, so "the
  seed does nothing" and "two runs agree" looked identical from outside — which is
  precisely how a dead injection survived in four files at once. The census prints the
  seed, the per-badge deal, and the settle time, and asserts nothing.

  Re-characterised over **15 deals, 30 renders**, and **no bound moved**: `TOLERANCE`
  +0.05px against a worst overrun of **−0.58px** (0.63px clear), `REPEAT_TOL` 0.01px
  against **0.00px** drift, `SETTLE_TOL` 0.5px against **0.00px**, and
  `SETTLE_TIMEOUT_S` 15.0s against a **0.10s** settle — 150× clear. 15/15 deal lines
  distinct, 15/15 PASS.

  **Nothing tightened, and unlike CL#180 the reason is structural rather than lucky:**
  the type figures are invariant across the deal by construction, since font-size and
  line-height are fixed by the page, so the verdict does not move even though every
  badge coordinate does. Stated honestly: there is no prior distribution to compare
  against here, because the file had no per-deal census at all before — these 15 are
  the first on record, not a re-measurement of a known set.

  **The pin is load-bearing, demonstrated rather than argued:** `--fonts blocked` moves
  the worst overrun from −0.58px to **−1.45px** and the face from Manrope to
  system-ui — the 0.87px swing the docstring claims, reproduced. Under a true blackhole
  `--fonts auto` degrades loudly and `--fonts pinned` **refuses with exit 2**. And the
  `deal` line is byte-identical across all three font regimes, which is the property
  that matters: the seed pins the deal independently of typography.

  **The eighth instance of CL#179's exit-code lie**, which that sweep missed because
  `pill_clip` was not in #156's list: the settle-timeout path said *"Nothing has been
  measured, so nothing has been proved"* and exited **1**. Print-then-2 now. Eight
  sites over three commits is the honest count, and the reflex is clearly still live.

  Verified independently: three consecutive runs identical in every measured quantity —
  only the wall-clock settle line moves, 0.10s against 0.11s, which is a small cost of
  putting a duration in a census meant for bit-comparison — and `--seed 4242` changes
  the deal. `npm test` 121/0. `mutation_gate --gate type` 1/1 caught, controls green;
  `--gate type --blind` 0/1 and `RESULT: FAIL`.

  **This closes the set: all four harnesses now deal from the injected generator**, and
  `CLAUDE.md`'s claim that `pill_clip` was "the last harness still carrying the unpinned
  exposure" is corrected — every *gate* pins, and has for longer than that sentence
  admitted. A stale exemption list is worse than none: it sends someone to fix what is
  already fixed, which is what this ticket did.

- **CL#185 — one alias was hiding two facts, and the ink on an accent is now derived
  rather than guessed.** (GitHub #152, GitHub #153.)

  **#152 — `--muted:var(--ref-muted)` is split, and the split is deliberately a
  no-op.** `--ref-muted` is now only the weight the datum was judged at; `--muted` is
  only the light UI ink. Same hex on purpose — moving the value is #120's decision,
  not this change's — so the split moves no pixel and changes no behaviour, and its
  entire effect is that the next move becomes *possible*. One hex cannot be both the
  ink a WCAG ratio binds and the reference weight a datum alpha was solved against;
  while they were one declaration, the cap on one was a cap on the other, which is
  what made #120's candidates unshippable.

  **`tools/test.js` asserted the alias, so #152 could not land alone.** The suite read
  `--muted` *through* `--ref-muted` in `TOKENS.light` and asserted the aliasing text
  in `:root` — so the harness modelled the very thing being removed, and would have
  gone on asserting the light alpha of a palette the page no longer has the moment the
  ink moved. The assertion is **inverted rather than deleted**: the light *ground* may
  alias `--ref-bg` and is still asserted to, the light *ink* may not, and re-aliasing
  now fails. That distinction is the finding.

  **#153 — `inkOnAccent(accent, tokens, floor)`, a rule and not a table.** It picks
  the pole (pure white or black, whichever contrasts more with the accent), takes
  whichever supplied token sits nearest that pole, returns it as written if it already
  clears the floor, and only otherwise bisects the smallest mix toward the pole that
  reaches it. Two named spec floors, because they are two different clauses:
  `WCAG_TEXT_CONTRAST = 4.5` for the selected row's 13px/600 label (1.4.3) and
  `WCAG_NONTEXT_CONTRAST = 3` for the toggle knob (1.4.11) — and CL#169 is the reason
  that boundary is treated as real rather than academic.

  A table of five hand-picked inks would pass today and say nothing about a sixth
  accent. **The floor is reachable by arithmetic, not by measurement:** black and white
  contrast equally at ground luminance 0.1791, both at 4.58:1, so the better pole is
  never worse than 4.58 against *any* colour and clears both floors unconditionally.

  Measured in light, where the old bet lost four times in five — red 3.88 → **row 4.53
  / knob 3.56**, blue 3.97 → **4.50 / 3.47**, amber **1.85 → 7.44**, green 3.21 →
  **4.52 / 4.30**. Steel, the accent that ships, is unchanged and pixel-identical; dark
  is unchanged at all five.

  **One real bug the sweep caught before it shipped:** bisecting the *ideal* mix and
  rounding afterwards landed red and blue at **4.49:1**, because rounding moves the
  colour back toward the token — the losing direction. The bisection measures the
  rounded colour it actually returns.

  **And #153's own constraint is now met in a gate rather than a scratchpad.** The
  ticket asked that the fix be *shown* to hold for the other four accents, and
  `a11y_audit` structurally cannot: it renders the one accent the schema ships. So the
  sweep is a `tools/test.js` test — `inkOnAccent` is pure arithmetic over colours, so
  it is extracted from `index.html` and run with no browser — over all five accents ×
  both themes × both floors, plus a lattice of **216 hypothetical accents**, since a
  rule can be asserted over colours nobody has chosen yet and a table cannot. **Proved
  able to fail**, twice: forcing the pole to white always (which is amber's 1.85:1
  case) and returning the unrounded mix (the 4.49 bug above) both turn it red, and the
  restored tree is green. Suite 120 → **121**.

  **Two premises corrected, both of which had been written down as fact.** #153 said
  `--accent` is per person and that adding someone would surface this — no `PEOPLE`
  entry in `config.js` carries an accent; there is one global `accent` prop and
  `ACCENTS` is a light→dark *map* of the five reachable values, so the ticket's trigger
  does not exist and the four non-steel accents are unreachable without editing that
  prop. The fix is still right; the urgency story was not. And `CLAUDE.md` claimed the
  pixel gate's raster residual needs contention *plus* the CI runner's flags —
  contention alone was enough to print the `NOTE` on this laptop, on both a dark and a
  light run, with neither flag set.

  `npm test` 121/0. `a11y_audit` PASS both themes, exit 0, 0 targets under 24×24.
  `pixel_regress` **0px** on the stage, `--panel` and `--theme light`, controls 0px.
  `dom_invariants` exit 0 dark and light, 56 inks dark / 64 light.

- **CL#184 — `docs/MANUAL-CHECKS.md` denied that `?seed` exists, had no `/fidget/`
  entries, and every line reference in it had drifted.** (GitHub #160.)

  This file is the list of things **no harness here can answer** — everything in
  `tools/` is headless Chrome over CDP plus one windowless WKWebView, so none of it
  has browser chrome, a window manager, a battery or a finger. The page's only mobile
  oracle is one human, which is the whole reason it is written down. It had drifted
  into being wrong about the thing that makes it usable. 254 → 526 lines.

  **The `?seed` denial was the worst of it**, because that hook exists *for this
  file's use case*: it said the hook "does not exist yet" and that "`index.html`
  parses no `seed` parameter at all". It does, and the section now states what a seed
  fixes (the **deal**), what it does not (the **fit** — placement is measured off the
  viewport, so reproducing a machine takes the same seed *and* the same window size),
  how to confirm it took, and the asymmetry that matters most holding a phone: **the
  page does not report the seed of an unseeded load**, so a machine that went wrong
  once is gone. Record device, orientation, theme, window and a photo first; hunt a
  seed second.

  **Five `/fidget/` checks added, where there had been none** — the grounding swipe
  against iOS edge gestures and the chrome overlay's own `pointer-events:auto` rows;
  rubber-band and pinch under `touch-action:none`; the grip spring in Low Power Mode
  (#164); toolbar collapse; and the shaft stub under a thumb against `/fidget/`'s own
  `env()` insets, which **no harness measures at all** — `devices.py` and
  `a11y_audit.py` both default to the root page, and `devices.py` reads root
  constants. CL#174's own requested check is in as check 8, with its 1px raster
  recorded as **do not chase**: desk-Chrome rasterisation over a byte-identical DOM,
  with nothing on a phone for an eye to find.

  **Every line reference had rotted**, which is the more general lesson:
  `index.html:87-92` was cited for `viewport-fit=cover` and is now palette prose. All
  of them are symbol anchors now (`viewBox()`, `DEAL_SEED`, `SAFE_DEVICES`,
  `DEVICES`), the same rule a subagent brief follows. Also corrected: the frame budget
  reads through `tickRate()`; the retired person picker is gone from check 7, replaced
  by Wear beside Speed; and a `?hud` section exists, where the file had none at all
  despite `?hud` being the instrument two of its checks lean on.

  **One correction changes the question rather than the answer.** The file claimed a
  24px slider disc. It is **16px** (`--thumb`), on a **129×44** input box (#134) — so
  the manual question is not "is the target big enough", which it comfortably is, but
  whether a 16px visual cue on a 44px target is *precise* enough under a thumb.

  The report distinguishes what was **verified by reading the tree** from what is
  **carried forward on trust** because only a real device can settle it — iOS
  throttling rAF in Low Power Mode, Safari's Reader heuristic, whether iOS fires a
  plain `resize` on a toolbar collapse. That distinction is this file's entire subject
  matter, so it is now modelled in the text rather than left implicit.

  **Two live faults fell out of the audit**, filed rather than folded in: #169, fixed
  in CL#183 above, and **#170** — `fidget/index.html` has **zero** `visualViewport`
  references against the landing page's six, and its only relayout wiring is
  `window.addEventListener('resize', layout)`. Projected, not observed, and
  unobservable by anything in `tools/`; check 12 is that question.

- **CL#183 — `?hud` threw a `ReferenceError` on every solo page, twice a second.**
  (GitHub #169.)

  `hudSample()`'s `scope` row still read `WHO.slug`. `WHO` was split into `SPINE`
  (which chain is the axis) and `SELECTED` (which person the page is about) precisely
  because every reader had to know which of the two it meant — and this one reference
  was not carried over. There is no live `WHO` declaration anywhere in the file.

  **It survived because the combined stage short-circuits it.**
  `STAGE.mode === 'all' ? 'all' : (WHO.slug || '?')` never evaluates the right-hand
  side at `127.0.0.1` or `wozi.com`, which is exactly where anyone testing the HUD
  would look. On a solo page — `?who=<slug>` or a personal subdomain — it threw, and
  `hudSample()` runs on a 500ms `setInterval`, so it threw for as long as the page was
  open.

  **The instrument was broken in the one situation it exists for.** `?hud` is the only
  test hook that ships, a deliberate exception to the rule that scaffolding lives in
  the harness, and it earns that exception by being the only way to read tick rate,
  dropped ticks and which of the four fit terms is binding on a device no harness can
  drive. A phone bug report is usually a solo page.

  **The verification is worth more than the fix, because the first attempt at it was
  blind.** A bespoke CDP probe reported "no exceptions" on the fixed tree — and
  reported the same on a worktree at HEAD that still contained the bug, because every
  `Runtime.evaluate` in it was silently returning nothing. Only shooting the control
  revealed that. `tools/verify_motion.py`, which already solves attachment and console
  capture properly, gives the real answer: HEAD reports **3 console errors** naming
  `ReferenceError: WHO is not defined` and `RESULT: CHECK ABOVE`; the fix reports **0**
  and `RESULT: PASS`. Reuse the harness rather than writing a probe.

  Also verified: `?hud` on the combined stage still clean and still reads `all`;
  `?hudson=1` still draws no panel, so the `/[?&]hud(=|&|$)/` gate is intact; plain
  `?who=charles` clean. `npm test` 120/0, and `pixel_regress` **0px** on both the stage
  and `?who=charles` — which is the correct answer here, since absent `?hud` the page
  must be byte-identical, and a non-zero result would have meant the change leaked into
  the shipped render.

- **CL#182 — `a11y_audit`'s green was green-on-average against a floating ruleset,
  and every run that measured nothing signed off as a pass.** (GitHub #165.)

  Three faults, found by making the gate prove its own verdict rather than reading it.

  **The ruleset was a major-version range off somebody else's server.** It fetched
  `axe-core@4`, so any 4.x release that added or tightened a rule changed what this
  gate asserts with nothing here having changed — by this repo's own
  no-drifting-constants rule, worse than a magic number, because it is a magic number
  nobody here can read. Pinned to **4.13.0**, which is deliberately *what `axe-core@4`
  resolved to on the day it was pinned*: anything older would have re-rolled the
  verdict against a different ruleset rather than freezing the one today's green was
  measured under. The cost, stated rather than discovered later — new upstream rules
  stop arriving for free, so an upgrade becomes a task somebody has to do.

  **And the pin is read back off `axe.version`, not assumed.** A version nobody
  verifies is the same fault as a theme planted in localStorage and never read
  (CL#171, and `pixel_regress` until CL#179): both `AXE_PATH` and a stale cache are
  routes to auditing under a ruleset nobody named, and the report would print the
  pinned number either way. Exit 2 on mismatch, proved by pointing `AXE_PATH` at
  4.12.1 while the pin said 4.13.0. **The version is in the cache filename** for the
  same reason — a cache keyed on the name alone serves the previous ruleset forever
  after a bump, so the pin would read as changed while the gate went on asserting the
  old rules.

  **It injected no LCG at all**, alone among the gates, while axe's `color-contrast`
  rule reads dealt colours. So each pass audited a randomly dealt machine, and twelve
  consecutive green runs was green-on-average over an unbounded population of deals —
  not deterministic green. A contrast failure reachable by one deal in fifty would
  have sat here indefinitely, passing. It now injects `dom_invariants.seed_js`, the
  same one home the other four harnesses use since CL#180, and takes a `--seed`.

  Proved in both halves, because either alone proves nothing: repeat runs at one seed
  are identical, and a different **injected** seed changes the deal — `SVG <text>
  nodes: 17` against `15`, which is engraving count and therefore a property of which
  wheels were dealt. It is the injected LCG and **not** `?seed`, for the reason
  `CLAUDE.md` gives and #155 demonstrated: a gate dealing through the page's own
  mechanism cannot see a fault in that mechanism.

  **The third fault was worse than either, and pre-existed both.** The final verdict
  line branched on the failure list alone, so **every path that returned 2 printed
  `RESULT: PASS`** — axe-core unreachable, the panel never opening, and now an
  unpinned ruleset. The exit code was correct and the sentence a human reads was its
  opposite: #156's lie relocated from the exit code into the reporting layer, which is
  arguably the more dangerous half, because nobody greps an exit code out of a CI log.
  It prints `RESULT: NOT AUDITED — … this is not a pass.` A sweep of the other
  harnesses found no second instance; `dom_invariants` conflates "no wheels on the
  stage" with a real failure but at least says `FAIL`.

  Verified: `RESULT: PASS`, exit 0, both themes, on the pinned deal. Mismatched
  ruleset → `RESULT: NOT AUDITED`, exit 2. Workflows parse.

  **What this does not buy, and what remains.** One pinned deal makes the verdict
  *reproducible*, not *complete* — it audits one of the machines the page can draw,
  and a sweep over several seeds is how to widen that, which is weekly work rather
  than deploy work. And the bytes still arrive from unpkg at run time, so an outage
  could still redden a deploy; **vendoring axe-core is what would close that** and let
  the job move onto the deploy path. Filed separately rather than folded in.

- **CL#181 — the one manual step in the deploy path could not be run as
  documented.** (GitHub #166.)

  `infra/cloudfront-viewer-request.js` exists because **it is not what is running** —
  the CloudFront Function is applied by hand, nothing deploys it, and if the two ever
  disagree then AWS is live and the repo copy is stale documentation until someone
  runs the commands in the header. Those commands were the only thing standing
  between the two, and the `update-function` one **died before it reached AWS**:

  ```
  Invalid type for parameter FunctionConfig.Comment,
  value: ['www->apex redirect', 'directory index rewrite', '/fidget slash'],
  type: <class 'list'>, valid types: <class 'str'>
  ```

  `--function-config` shorthand separates key=value pairs on **commas**, and the
  shell strips the quotes before the CLI sees them — so a `Comment` containing commas
  is split into a list. Now passed as JSON, which is unambiguous and also survives
  being pasted into a shell that quotes differently.

  **Verified without mutating anything**, which is the part worth recording: both
  forms were run against a deliberately nonexistent function name, because the CLI
  validates parameter types *before* it makes a request. The shorthand form fails at
  `ParamValidation`; the JSON form gets past it and fails on credentials — parameters
  parsed, request attempted. No AWS state was touched and no approval was needed.

  The change is **comment-only**, so the live function needs no update — the fix is to
  the instructions, not to the code they publish.

  Also recorded in the header: `test-function` was returning **503** during CL#146's
  work, confirmed with `--debug` rather than assumed, so it was AWS-side. The fallback
  used then was simulating `handler()` in Node over the same sample events, which
  exercises this file's logic but **not** CloudFront's own runtime — and the header now
  says to report which of the two was done rather than calling either "tested".

  All six sample events re-simulated and correct: `/fidget` 301s to `/fidget/`; the
  query survives; `www.wozi.com/fidget` takes **one** hop straight to
  `https://wozi.com/fidget/`; `charles.wozi.com/fidget` stays on
  `charles.wozi.com`; `/ssh_public_key` passes through untouched — which is why `DIRS`
  is a named list and not an extensionless rule; and `/fidget/` still rewrites to
  `/fidget/index.html`. `node --check` passes and the JSON literal in the comment
  parses.

- **CL#180 — three gates dealt their machines through the shipped `?seed`
  mechanism, so their own injected generator was dead code.** (GitHub #155.)

  `CLAUDE.md` is explicit that a harness must inject its own LCG and never use the
  page's `?seed`, because *"a gate that deals through the same mechanism the page
  deals through cannot see a fault in that mechanism — it would agree with the page
  about a machine they had both got wrong."* `dom_invariants`, `escape_mesh` and
  `devices` each did **both**, and doing both means the injection loses:

  Their copy of the injected source read the seed out of `location.search`, so it
  only produced anything when `?seed=` was also on the URL — and `DEAL_SEED` runs at
  `index.html`'s **module scope**, which is *after* any injected script, reassigning
  `Math.random` to its own generator. The shipped mechanism dealt every machine those
  three gates have ever measured. The rule was in the rulebook, the mechanism was in
  the file, and the two had never been checked against each other.

  **Fixed by baking the seed into the closure** — `seed_js(seed)` replaces the
  `SEED_JS` constant, and the URL carries no `seed=` at all. `dom_invariants.seed_js`
  is the **one home**, imported by the other two rather than copied, because three
  copies is what let one fault be three.

  **Proved in both halves, because either alone is worthless.** Repeats must be
  bit-identical *and* the injected seed must be what governs — absent `?seed=` the
  page does not touch `Math.random`, so identical repeats can only come from the
  injection:

  | measurement | result |
  | --- | --- |
  | `dom_invariants --census` ×2, same seed | identical but for the wall-clock line |
  | same nominal seed, before vs after | 76 of 85 lines differ — the deal changed |
  | injected seed 20260804 vs 4242 | 127 census lines differ |
  | `escape_mesh --census` ×2 | identical, 149/149 |
  | `devices --census`, three seed bases | **28/28 rows differ** on each |

  **`devices` had a second, larger hole: its `SAFE_DEVICES` pass was not seeded at
  all.** Four of its 28 rows dealt at random every run. All 28 are now pinned on one
  counter. The re-injection is per-navigation via
  `Page.removeScriptToEvaluateOnNewDocument`, and it **fails hard** if Chrome returns
  no identifier — leaving stale scripts installed would be *worse* than the original
  bug, because the last one added would silently decide all 28 deals. Its first
  navigation also went to `?{URL}`, racing the network before `pin.install()`; it is
  `/json/new?about:blank` now, like its siblings.

  **Every bound was re-characterised and none was moved.** Every number these three
  gates print changed, because every machine they measure changed — nothing about the
  page did. `dom_invariants` over 30 runs: worst meshing residual **0.0036px** of
  0.35 (97×), closest non-meshing pair **47.5px** (136×). `escape_mesh` over 24
  deals: worst ghost residual **0.0233px** of 0.35 (15×). `devices` over 72 dealt
  machines: centre offset 600× clear, gear ceiling 4.5px, link-share floor **0.104**.

  Two of those **tightened** — `escape_mesh` from 18× to 15×, `devices`' link-share
  floor from ~0.12 — and both are properties of which machines got dealt rather than
  of the geometry. Left alone deliberately: a bound moved to keep a run green
  measures nothing. One honest confound stated rather than smoothed over: the
  `devices` floor moved while **two** things changed at once, different deals *and*
  three times as many of them, so part of that is more sampling finding a worse row
  and not evidence about the page.

  **Two gates that run on every deploy had no mutant at all**, so "every gate went
  red for its own mutant" was silent about them — exactly the claim
  `mutation_gate.py` exists to stop anyone taking on trust. `dom` and `escape` are
  registered now, with three mutants, all **caught**:

  - `train-loses-mesh` — `prev.r + r` → `+ 2`. Every direct-mesh pair opens ~2.78px;
    the gate reports all 10 wheels orphaned across 10 components.
  - `escape-host-misrecorded` — `hostCx: host.g.cx + 40`. **Moves no pixel and
    changes no geometry**; it corrupts only the page's account of which wheel a run
    grew from, which is precisely what no pixel gate can see.
  - `escape-run-steps-wide` — escape step `+ 1.5`, red at 2.20px against 0.35, and
    invisible to `dom_invariants` by construction.

  `--blind` on the two new gates reports 0/3 and exits 1, so the registrations are
  not self-certifying.

  **One caveat found while proving determinism, documented rather than hidden:**
  `devices --census`'s `reach` figures wobble a few tenths of a pixel between
  identical runs while every other quantity is bit-identical. `a0`/`a1` come off
  `getBoundingClientRect()` on the *rotating* wheel wrappers — the box of a spinning
  square — so it is phase-dependent and always was. 144px of margin, so it cannot
  reach the assertion.

  **Two more instances of CL#179's exit-code lie, and one of them was brand new.**
  `escape_mesh`'s serve failure was a pre-existing eighth site. The other was
  introduced *by this change* — the stale-injection guard above was written as
  `SystemExit("...")`, which exits **1**, this tool's word for *"a device failed its
  layout check"*, on a condition that means nothing was measured at all. Worth
  recording rather than quietly fixing: the contract is one commit old and the reflex
  that breaks it is still the default. Both are print-then-2 now, and a sweep of
  `tools/` finds no string-form `SystemExit` left in any gate. The two remaining
  (`contact_sheet.py`, `palettes.py`) document no exit-code contract and are not
  gates, so there is nothing for them to contradict.

  `npm test` 120/0. `dom_invariants` exit 0 on stage, solo and light; `escape_mesh`
  PASS; `devices` 24/24 and 4/4. `mutation_gate` **17/17 caught**, 1/1 tolerated, 1
  known gap still open, 8/8 controls green.

  **Follow-up, not fixed:** `tools/pill_clip.py` carries a **fourth** copy of the
  URL-reading seed source and has the identical fault — and its own comment asserts
  it seeds the same way as the two files just fixed, which is now false in the other
  direction. It needs its own tolerance re-characterisation, since its deals will
  change too.

- **CL#179 — seven harness paths said "nothing has been proved" and exited with the
  code that means "the artifact is wrong"; and the light theme is now rendered by
  three gates instead of none.** (GitHub #156, GitHub #157.)

  **The shadow.** `tools/pixel_regress.py` had `fatal = pin.announce()` in `main()`,
  which shadows the module-level `fatal()` — the helper that prints and exits **2** —
  for the whole of `main()`, and `stable_render()` closes over it. So the one path
  that reports a harness fault called `None`, died with a `TypeError`, and exited
  **1**: this tool's word for THE ARTIFACT MOVED. A flaky machine would have been
  reported as a broken page. The local is now `announce_err`, and the reason it may
  never be called `fatal` again is written at the site.

  Demonstrated in both directions rather than reasoned about, by forcing the
  never-agrees branch with `STABLE_ATTEMPTS = 1` from a wrapper so no flaky machine
  was needed: with the shadow restored, `TypeError: 'NoneType' object is not
  callable`, exit **1**; with the fix, the intended sentence and exit **2**.

  **It was not one site but seven, and they are one contract.** `SystemExit("some
  string")` prints the string and exits **1**. Every tool here documents **2** as
  "could not measure", so every use of the string form was a sentence contradicting
  its own exit code:

  | site | what it says | exited |
  | --- | --- | --- |
  | `pixel_regress` never-agrees | a fault in the harness, not the artifact | 1 (`TypeError`) |
  | `render_cost` / `parse_cost` no DevTools endpoint | could not get a browser | 1 |
  | `render_cost` / `parse_cost` **absent** `$CHROME` | — | 1 (`FileNotFoundError` traceback) |
  | `fontpin` `wait_until` timeout | nothing has been measured, so nothing has been proved | 1 |
  | `dom_invariants` `settle_geometry` | nothing has been measured, so nothing has been proved | 1 |
  | `mutation_gate` `serve` | could not serve | 1 |
  | `devices` `_page_const` | constant not found in `index.html` | 1 |

  The absent-`$CHROME` pair is the one nobody would have predicted: a **missing**
  binary and a binary that **never answers** are the same sentence to an operator,
  and they were different exit codes because `Popen` raises `FileNotFoundError`
  before any of the tool's own error handling runs. All seven are now
  print-then-`SystemExit(2)`, each proved by forcing its branch — `CHROME` pointed
  at a nonexistent path, `CHROME=/usr/bin/true` (launches, publishes no endpoint), a
  `settle_geometry` whose reads never agree, a served directory that does not exist,
  and a constant name that is not in the page.

  **`fontpin`'s is the one that had already fired**, and it fired again while this
  was being landed: an `a11y_audit` run pointed at a port nothing was serving printed
  *"nothing has been measured, so nothing has been proved"* and exited **1**. It is a
  library, so its code is the code `a11y_audit` and `dom_invariants` return — and it
  now sits under the CI job added below, whose `exit 2` branch could never have seen
  it.

  **The light theme was rendered by no gate in any workflow.** Every themed harness
  in `deploy.yml` runs at its own `--theme dark` default, and `a11y_audit` — the only
  tool that iterates both, and the only automated check on contrast or target size
  anywhere — was in **no workflow at all**. Twelve gate invocations, none of which
  had ever drawn the palette half the page is painted in, in a project whose real
  faults have been light-only twice: CL#133 removed the wheel shadow in light because
  the shared layer showed through the cuts, and CL#173 fixed five serious contrast
  failures in light, two of them a regression introduced one commit earlier.

  Three additions, and each answers a different question:

  - **A fifth `pixel_regress` run, `--theme light`**, combined stage. 0px at both
    viewports, controls 0px, 12s locally against the other four's 16/15/9/15.
  - **A third `dom_invariants` run, `--theme light`.** The ink census is the one
    check here whose *subject* changes with the theme, and it claims to catch a
    palette leaking into the other theme's render — a claim it could not
    substantiate while it only ever rendered one. Measured at the same seed: **64
    inks in light against 56 in dark**, with different saturation and value extremes,
    so eight of the page's inks had never been censused. **The light pixel run does
    not subsume it**: `pixel_regress` is *differential*, so a light-only fault
    present in both sides is 0px there forever, while the census is *absolute*.
  - **An `a11y` job in `mutation.yml`**, on the same weekly/dispatch/`harness`-label
    trigger, port 8797. It is on a Monday rather than the deploy path, and **not
    because it is slow** — 1.6–2.3s warm against `devices.py`'s 3m38 in CI. The
    reasons are that it fetches `axe-core@4` from unpkg, so somebody else's publish
    can turn a deploy red, and that unlike every gate in `deploy.yml` it injects no
    LCG, so it audits a randomly dealt machine each pass and axe's contrast rule
    reads dealt colours. Twelve consecutive green runs is green-on-average over an
    unbounded population of deals, which is not the same claim as deterministic
    green. This workflow is now "the weekly slow-or-drifting checks": both jobs
    answer questions whose answers change on somebody else's schedule.

  **Half of `a11y_audit`'s own assertions were about one theme.** The 24×24 floor,
  the duplicate-name check, `lang`/`main` and the unlabelled-focusable count were
  gated on `theme == "dark"` inside a tool whose entire reason for looping is that
  findings differ between themes — and nothing there is theme-independent by
  construction, since a target's box comes from the style that painted it. They run
  in both now and name their theme in each failure; the verbose printout stays
  dark-only, because that half describes the page rather than checking it, and light
  prints a one-line summary so a reader can tell the battery ran. Light comes back
  identical to dark today — 0 under the floor, 30 focusable, 0 unlabelled, tightest
  24.00px — so it costs nothing and is now asserted rather than assumed.

  **"No violations" was a weaker sentence than it read as.** axe puts a check it
  could not decide into `incomplete`, and the report only ever mapped
  `r.violations` — so the undecided bucket was invisible. On a page painted almost
  entirely in inline gradients, `color-contrast` is exactly the rule that lands
  there. Measured: **exactly one undecided rule per theme**, `color-contrast` on an
  SVG rim engraving axe could not flatten a background for. That engraving is inside
  an `aria-hidden="true"` SVG, as all 40 are, so it is decorative and never
  announced — the gap was real and what it hid is not alarming. It is **printed,
  never failed**, on the same #41/#46 reasoning that keeps `moderate` out of the
  verdict; a rule moving from decided to undecided is now visible instead of reading
  as a clean run.

  **And the new light run is now able to prove it looked at light.**
  `pixel_regress` plants `wozi-theme` in localStorage and **never read it back**, so
  a `--theme light` run that silently rendered dark would have reported a contented
  0px — CL#171's fault verbatim, on the very run whose whole job is the other
  palette. It asserts `data-theme` after every render and exits 2 on a mismatch,
  proved by inverting the comparison. `/fidget/` keeps its own `data-theme="auto"`
  and never reads the key, so the assertion is **exempted there by a decision taken
  off the page source before any browser starts**, exactly as the font decision is —
  and the run now *says* so, where `--theme` was previously an unstated no-op on that
  page.

  `npm test` 120/0. All five `pixel_regress` runs 0px, controls 0px. `a11y_audit`
  PASS in both themes, exit 0. `dom_invariants` exit 0 for stage, solo and light.
  `mutation_gate` full sweep 14/14 caught, 1/1 tolerated, 6/6 controls green, one
  known gap still open; `--blind` still returns `0/14 caught … RESULT: FAIL`, so the
  runner can still fail. Both workflows parse as YAML and every `run:` block passes
  `bash -n`.

- **CL#178 — `/fidget/`'s grip spring was divided by gear twice, so the drag and the
  flick buttons demonstrated different laws.** (GitHub #158.)

  `portAngle` and `portRate` are already in the port's coordinate, so each term of the
  torque owes exactly **one** further division to map back onto the generalised
  coordinate: `Q = [k(target − θ_p) − c·θ̇_p] / gear`. The damper did that; the spring
  did it twice. One token.

  **The damper is an independent proof rather than a second opinion.** `MODE.damper` is
  `2ζ√(stiffness × port.inertia)` — critical damping *in the port's coordinate* — which
  only yields ζ at the port if the spring is mapped by one gear too.

  **Measured by simulating the shipped `step()` verbatim, and by a step response driven
  in the page over CDP:**

  | ring-grounded carrier | before | after |
  | --- | --- | --- |
  | ω_n | 1.02 (`HAND_FREQ/RATIO^1.5`) | **3.956** (`HAND_FREQ/RATIO`) |
  | ζ | **1.090**, overdamped | **0.280** |
  | t90 | 6.35s sim / **6.26s in-page** | 0.467s sim / **0.411s in-page** |
  | rings? | never | yes — measured period **1.645s**, ω_d 3.82 against a model 3.798 |

  The input port is confirmed **exactly** unchanged, and structurally so: `gear` is 1
  there, so the two laws are the same expression.

  **The bug was overstating the page's own demonstration.** The ω_n ratio between the
  ports was `RATIO^1.5` = **59.0×** where the physics gives `RATIO` = **15.17×** — so
  the heavy port felt nearly four times heavier than the machine justifies, on a page
  that exists to make that exact ratio felt. t90 ratio at the shipped tick is now 14.2×.

  **Two things the before-simulation turned up.** Pre-fix the heavy port did not merely
  lag, it **stalled**: a 60° twist settled at 56.1° after 8s, the spring torque near
  the target having fallen under the Coulomb residue. And the README's unexplained
  **34.6%** carrier-tracking figure is now attributed — it is that sweep sampled ~1s
  *after* release, which re-measures at 36.5% pre-fix; the at-end-of-gesture figure is
  **17.0% → 92.0%**, against an ODE prediction of 16.1 → 91.0.

  **`HAND_DAMPING` needed no re-tune, and that is structural.** With the spring mapped
  by one gear the port-referred equation is `J_eff·gear²·θ̈ = k(target−θ) − c·θ̇`, giving
  `ω_n = HAND_FREQ/gear` and `ζ = HAND_DAMPING` **exactly** at both ports in both
  groundings — verified numerically to 1e−12. The 1.09 was an artefact of the mapping,
  not a damping choice. The mapping is no longer a free parameter.

  **Dimensional sweep of the whole file, all sound** — because CL#158 had already
  corrected a different factor of two here (the parallel-axis term in `disc()`), so one
  more was worth looking for: `disc` (½r⁴) and `mass` (r²); `ringInertia` checked
  against a direct ∫2r³dr, exact; all five `effectiveInertia` terms; the parallel-axis
  ratio coming out **2.0000** in all four stage×grounding cases with the rolling
  identity exact in the ground frame; Willis in both groundings by a **third**
  independent route; `port.inertia = J·gear²`; `stiffness = ω²J`; `flick()`'s
  `L/(J·gear)`; and the loss model (`retard(REF)/retard(0)` = 60.000 = `DRAG_RANGE`,
  bisected coast 8.998s against a stated 9.0). Every J_eff figure in both README tables
  reproduced digit-for-digit, so this fix moves no inertia number.

  **One pre-existing hazard found and NOT fixed, filed separately:** the grip spring is
  integrated explicitly, so the *input* port's `ω_n·dt` is **1.0 at 60fps** — the tick,
  not the model, sets the shape there (measured first overshoot 90% against the
  continuous 40%). Past about 1.3, below ~50fps, it **diverges into a limit cycle**
  bounded only by `MAX_SPEED` and the losses. Low Power Mode is 30fps. Identical before
  and after this fix, since gear is 1 at that port, and the heavy port is nowhere near
  it (`ω_n·dt` 0.066).

  `pixel_regress --path fidget/` **0px** — and this is the "0px can mean *not tested*"
  case rather than a pass: the resting pose is `S.angle = 0` with no finger down, and
  the spring term is only reached while a grip exists. The drag probes are the
  measurement that can see this. `npm test` 120/0. Boots in both groundings with **0
  console messages**, transforms advancing. Both Willis guards re-mutation-tested at the
  fixed tree and still throwing. `planetary` survives the strip, 3× in the stripped body.

  The README also claimed this folder does not publish, which has been false since
  `fidget/index.html` joined the deploy whitelist. Corrected.

- **CL#177 — the datum's ink caches are discarded when the palette in force changes,
  and the latent failure was reproduced before it was fixed.** (GitHub #159.)

  `datumOpacity()` and `datumInk()` cached per `state.theme` for the page's life, while
  the palette actually in force is the **`data-theme` attribute** — and CL#174 moved
  the state seed to construction while `paintTheme()` still applies the attribute at
  the end of mount. So the first render could solve and cache against a theme whose
  palette was not yet applied.

  **Reproduced rather than reasoned about, and it is worse than the ticket said.** With
  a scratch FOUC fix (the `<helmet>` style block duplicated into the real `<head>`,
  never shipped), a dark first render reads `--muted: #677977` — the **light** value —
  with the attribute still `null`, caches it, and never reads again. The datum then
  ships **`rgb(0, 0, 0)`**: pure black, not merely dark, because `k` is the dark ratio
  applied to a light token that sits *below* the light page, so every channel clamps at
  zero. With the fix, all six cold-load combinations give the correct
  `rgb(223,250,244)`.

  **Two corrections to #159's own text.** The trigger is *dark at first render from ANY
  source*, not the system path specifically — `state.theme` is seeded from
  `storedChoice()` at construction too. Which means that once someone lands the FOUC
  fix, `pixel_regress --theme dark` **would** catch this, since that plants
  localStorage; today's empty token reads are what hide it from both paths equally.

  **Cleared rather than re-keyed, for a reason worth keeping.** `datumInk()` computes
  `k = datumOpacity() / ghostOpacity()`, and `ghostOpacity()` reads `state.theme`.
  Keying the caches on the attribute would leave the two solvers reading one theme
  while the ratio they divide by reads the other — **a second opinion about "which
  theme am I in", inside exactly the window the bug lives in.** Clearing on "the
  palette in force just changed" needs no second notion of theme, keeps CL#174's
  paint/setState split intact, and costs one bisection per theme change, off the rAF
  loop. **The solve is untouched — only when it may be remembered.**

  Swept for the same shape: there are exactly **three** `getComputedStyle` sites. The
  third, `GHOST_GROUNDS` at module scope, is **theme-invariant by construction** — it
  reads only `--ref-bg` and `--ref-bg-dark`, both declared in bare `:root` and
  deliberately not overridden in the dark block, and carries literal fallbacks equal to
  those hexes — so its timing cannot matter. Every instance memo was checked for what
  it keys on and when it is seeded (`_tw`/`_ti`, `_gsr`, `_hexMemo`, `_bridgeAt`,
  `_slugFor`, `_solved`, the warn-once flags): none is theme-dependent. Every other
  `state.theme` consumer is a render-time read with no memo, and `syncVars()` runs
  after `paintTheme()` so the `--accent` write never precedes the attribute.

  `npm test` 120/0. `pixel_regress` **0px** on the combined stage, on `?who=charles`,
  and on `--theme light` — all three expected zeros, since this is a caching fix — with
  controls 0px. `dom_invariants`, `verify_motion` and `a11y_audit` (both themes) PASS,
  0 console errors. Solved inks byte-identical to HEAD at every cold-load combination,
  so the green-channel clamp and CL#173's 0.15-wide token window are untouched.

- **CL#176 — `datumClear()` was paying 20% short of what the datum actually puts
  outboard, in every treatment the page has ever shipped.** (GitHub #141.)

  **#141's own premise was obsolete when I filed it.** It assumed the label sat
  outboard at 33.2/39.0px — CL#164-era geometry that **CL#166 had already reversed**.
  `markSign` resolves to `-out` on every chain, so the label is always **inboard**;
  measured, **0px of label ink outboard of the scribe**, both chains, both viewports.

  **The thing that is outboard is the station ticks** — `MODULE * 1.2 * S`, declared
  inline in `datumLayer` where `datumClear()` could not see them. So `datumClear()`
  paid `plateMetrics().h / 2` = `MODULE * S`: **20% short, in every treatment
  including the original chip.** Neither #139 nor #166 caused it; it is older than
  both, and it is the fault #141 was reaching for from the wrong direction.

  So option (2) — rename the constant to bound the scribe's standoff — would have
  documented a mismatch CL#166 had removed while leaving a real one in place. Took
  option (1): `PLATE_TOP_CLEAR` keeps meaning "clearance from the extreme border" and
  `datumClear()` now pays the true reach.

  **Derived, not a second constant.** `plateMetrics()` gains `tick` — the one home for
  the tick length, now read by `MAJOR` in `datumLayer` where the literal used to be —
  and `reach = max(tick, h/2, hair/2)`: a max over the three things the shape puts
  outboard of its own line, so it stays true if any one is retuned rather than being
  true because one happens to be biggest today.

  Bound satisfaction at 1440x900: **21.40px → 20.00px** against a stated 20. The
  crossover where the bound takes over from the module of air moves from
  `20/(MODULE*2)` = 1.429 to `20/(MODULE*2.2)` ≈ **1.299**, so the change is confined
  to `--gsfit` 1.299–1.461.

  **Swept 10 seeds at desk and 5 on a phone**, two servers, harness LCG pinned. Every
  scribe moved exactly **±1.41px toward its own chain**, uniform across deals as it
  must be — the standoff is a property of the render scale, not the deal. Charles's
  seat **unchanged to the last digit on all 10**; Harper's — the crowded chain — moved
  **+0.32 to +0.63px**, second-order, because `datumClear()` also feeds `plateSeat`'s
  metal-clearance air. **No seat lost a clean window.** The phone is **byte-identical**,
  confirming it sits below the new crossover. Zero `plateSeat` warnings, zero overlap
  warnings, zero console errors across ~30 seeded runs.

  `pixel_regress` **11,636px at 1440x900 and 0px at 390x844** — and that split *is* the
  accounting rather than a curiosity: the desk is inside the affected band and the
  phone is not. `?who=charles` 0px both, since a solo page draws no datum at all.
  `npm test` 120/0 with **both mutation-tested plate tests passing unchanged and
  unedited**, plus the standoff test whose three assertions were checked against the
  new air. `dom_invariants` and `verify_motion` PASS, 0 console errors.

  **The inboard half of the same mismatch is still open and is filed as #162**:
  `plateSeat()` searches a box centred on the line while `markT` moves the drawn box
  ~14.27px inboard, onto the side that has the metal. It costs a guarantee rather than
  a picture — CL#166 measured 0.0% of mark pixels on metal — and fixing it means
  re-ordering `datumLayer` so the per-chain offset is known before the search, not
  widening a box.

- **CL#175 — the pop-out panel can be dismissed by tapping off it, and it stops
  overshooting its own cap.** (GitHub #154, #149 — both close.)

  Charles: *"click or tap off of the settings pannel should collapse it if open"*.
  It could not be: `toggleTog` was the only thing that changed `state.tog`, there was
  no document listener, and **no Escape handler either** — so a disclosure that can
  cover most of a phone was dismissible only from the smallest target on screen.

  Four routes now, all through one `closeTog(refocus)`, so `state.tog` and
  `aria-expanded` cannot disagree — and that attribute's contract is untouched, since
  `pixel_regress --panel` (CL#172) and `a11y_audit` (CL#171) both locate the toggle by
  it. Escape returns focus to the toggle rather than dropping the visitor somewhere
  arbitrary.

  **The dismissing tap is CONSUMED, and the mechanism is layout rather than event
  bookkeeping.** A full-viewport transparent scrim sits at `z-index 19`, the panel at
  30, all four corner controls at 20. One ladder is the whole policy: inside clicks and
  slider drags never reach the scrim because the panel is above it; **the scrim cannot
  see the toggle's own press, so the close-then-reopen double-fire is impossible rather
  than guarded**; and the stage's `onPointerDown` never fires because the scrim is the
  hit target — so there is no `stopPropagation()` for a later edit to delete. A tap
  whose intent is to dismiss does not also fling the machine.

  **`position: fixed`, not `absolute`, and that is not interchangeable — measured.**
  `main` has `overflow:hidden` but `html`/`body` do not, so at short landscape
  viewports the composition is taller than the window and the page really scrolls
  (`scrollHeight` 423 vs 390, 440 vs 273). With an absolute scrim, after scrolling,
  `elementFromPoint` at the bottom edge returns `MAIN` — an uncovered band where a tap
  would spin the train.

  **Theme and motion deliberately do NOT dismiss**, against the ticket's own
  presumption: they are peers of the panel's settings (flipping theme to compare is
  something you do *with* it open), and the departure indicator's job is to reset the
  very speed the panel's slider sets. Reversible by dropping the scrim to `z-index 21`.

  #149: `boxSizing: 'border-box'` on `togPanelStyle`. The `maxHeight` cap sat on a
  `content-box` element with `padding: 10px 6px` and a 1px border, so padding and
  border were added **on top of** the cap — the fault CL#114 was written to prevent,
  by 22px. Proven by the gate CL#172 built: at 844x390 the box goes **396 → 374 against
  a 374px cap**, `over: +3 → −8`, so the panel gets the same 8px clearance every other
  fixed element gets. Rejected the alternative of subtracting `20px + 2px` inside the
  `calc()` — that restates the padding and border three lines above their own
  declaration, which is the `LATTICE_WALL`/`BOSS_MUL` failure mode. The 22px comes out
  of the scrolled remainder, not the opening view: the slider is still first child with
  `scrollTop` 0 at both tight profiles, on the combined stage and on `?who=charles`.

  Six behaviours measured with real `Input.dispatchMouseEvent` taps rather than
  `element.click()`, with capture counters on both the stage and the scrim: outside tap
  closes (scrim 1, **stage 0**); toggle tap closes without reopening (**scrim 0**); a
  Table of Gears entry does not close; a slider drag from inside to x=824 outside does
  not close and moves the value 0→7; Escape closes from inside-panel focus and returns
  it to the toggle; Escape while shut is inert. Bonus: a dismissing tap landing on a
  gear badge dismisses **without** navigating, while the same tap with the panel shut
  still navigates.

  **`--panel` reports 2,852px at the two uncapped viewports and it is not the panel** —
  the panel box is byte-identical there (568.6px), and the differing pixels are
  scattered over the whole frame at antialiasing magnitude. Isolated by experiment:
  forcing the scrim's `display` off and changing nothing else gives **0px**. A
  transparent fixed layer changes how Chrome rasterises what is beneath it, it exists
  only while the menu is open, and the default gate is 0px. Accepted as the price of
  structural consumption; the `absolute` variant was 0px and genuinely incorrect under
  scroll. At the capped viewports `--panel` reports 27,384 / 22,849, which is #149's
  intended 22px and its re-centring.

  `npm test` 120/0, `a11y_audit` PASS both themes with the panel confirmed open in
  each, `devices.py` 24/24 + 4/4 with the tightest clearance unchanged at 8px,
  `verify_motion` and `dom_invariants` PASS with 0 console errors, `strip_comments
  --check` still parses with all 769 backlinks naming real lines.

- **CL#174 — the page no longer draws itself once at a scale it is about to throw
  away.** (GitHub #135, plan A. The ticket's remaining work.)

  The profile behind #135 found the page renders its own composition **five times per
  cold load**, three inside the one long task, with **render 1 drawn at the boot
  `--gsfit` of 0.86** against a real ~1.4 — a value the file's own comment called
  provisional — and render 3 existing only to re-solve the ghosts once the scale was
  right. Every input the first render got wrong was **synchronously available before
  mount**: `localStorage`, `matchMedia`, and the fit itself, which reads only
  `innerWidth`/`innerHeight`/`visualViewport` with no `getComputedStyle` and no
  layout.

  Theme, motion, speed, wear and the three style layers now seed the **initial
  state**, through `storedChoice()` / `storedNumber()` / `storedFlag()` — one
  `try/catch` and one home for the `wozi-` prefix, where six restores had been
  written out separately in `startPhysics()`. **`fitScale()` is the fit's one home**,
  called by both `gsRender()` and `fitStage()`, so the boot CSS value is no longer a
  second source of truth for it.

  **Renders 5 → 4, scales `[0.86, 1.39, 1.39, 1.39, 1.39]` → `[1.39, 1.39, 1.39,
  1.39]`.** Measured on top of CL#170, so the before figure is 176ms rather than the
  ticket's 183ms:

  | | 6x before | 6x after | 1x before | 1x after |
  | --- | --- | --- | --- | --- |
  | combined | 176.0 | **126.1** (−28.4%) | 25.0 | **17.6** |
  | `?who=charles` | 150.5 | **101.6** (−32.5%) | 18.9 | **14.4** |

  Call counts agree: `renderVals` 5→4, `gearSvg` 40→28, `polarR` 41,485→30,950 on a
  solo page.

  **The risk was the deal, not the clock, and it is provably unchanged.** `solve()`
  consumes `Math.random` for the service shuffle, so a reordered initialisation could
  silently change which wheel wears which service. A harness-side LCG logged every
  call's value *and calling frames* over a full cold load: **229 calls, sha1
  identical, `diff` empty**, on the combined stage and on `?who=charles` alike. The
  shuffle is calls 225–229 in both, same values, same frames.

  **A second first-render error nobody had named**, found on the way: `solve()`'s
  partial self-seed set `_axisRot` and `_idlerN` but left `_tight` reading as 1, so
  the first solve was laid out at the wrong tightness. `seatLayout()` is now the one
  home for those four quantised inputs and `solve()` calls it.

  **#142 turns out to be a latent hazard, not a live fault, and its filed diagnosis
  was wrong.** That ticket — mine — claimed `setState({speed})` runs *after* the
  flywheel seed is read. Probed directly: `support.js`'s `__setLogicState` assigns
  `logic.state` **synchronously** before scheduling the re-render, so HEAD already
  seeded at `rateAt(20)` = 6.857143 with `spinUp:false` and a saved 20x, exactly as
  the existing comment claimed. Plan A removes the ordering dependency structurally
  rather than fixing a break. Worth recording because *"React state is not readable
  until the next render"* is false in this runtime and will be reached for again.

  **The gate reading, stated precisely.** Combined stage **0px** at both viewports
  with controls 0px — and here 0px IS the pass, because the settled state is
  identical by construction and 90 pumped frames would have exposed a phase offset.
  `?who=charles` is 0px at 1440x900 and **1px at 390x844, max channel delta 1**. That
  one pixel was chased, not waved past: the rendered DOM is byte-identical (`main`'s
  `outerHTML`, the whole body with script sources masked, and the root inline style
  including `--gsfit` all diff to zero), each build reproduces its own shot across
  fresh browser launches, and it appears in light theme too. It is **rasterisation**,
  by #37's own mechanism — the promoted layer is now rasterised **once** at the final
  composited scale instead of at 0.86 and again at 1.39. Strictly the better raster,
  and the visible trace of the render this change deleted. Not a tolerance and not a
  flake; reproduced independently before merging.

  **One clock is not at risk and nothing is deferred** — this makes the first render
  *more* complete, adds no gate and latches no flag, so #7 is untouched, and `_M`/`_v`
  initialisation is unmoved.

  Also corrects the `--gsfit` declaration's comment, which still claimed
  `gsRender()` read it "so the two cannot drift apart". It no longer does; the
  declaration is now only what `?hud` displays before the first `setProperty`, and the
  comment says so rather than describing a coupling that has gone.

  `npm test` 120/0, `dom_invariants` PASS, `verify_motion` 40/40 with 0 console
  errors, `escape_mesh` PASS across 8 seed/orientation combinations, `devices.py`
  24/24 + 4/4, `pill_clip` PASS, `a11y_audit` PASS in both themes.

  **For `docs/MANUAL-CHECKS.md`**: the first paint now shows the train at the right
  scale rather than at 0.86 jumping to ~1.4. No harness photographs that moment —
  every gate here measures the settled state — so it wants a human eye on a real
  device, as does the 1px raster difference on a phone.

- **CL#172 — the pixel gate can photograph the pop-out panel, and a paired mutant
  proves it.** (GitHub #144, closes it.)

  Five controls were rewritten in CL#169 and `pixel_regress` reported **0px differ /
  PASS** with a clean control and pinned fonts. The panel is `display:none` until
  clicked and there was **no forcing parameter**, so unlike the `?kind=` trap
  CLAUDE.md warns about there was nothing to remember to pass — every control in the
  menu, including the speed slider that is the only route to speed once the corner
  button hides at 1x, was permanently invisible to the strongest gate in the repo.

  **`--panel` clicks it open; the page grew nothing.** That was the deliberate
  choice: `?seed` is the only determinism affordance in shipped code (CL#109) and
  `ORIGIN_MOUNT` was kept out of the URL for exactly this reason — a second switch
  reachable from the address bar is a second way for the page to draw something no
  gate photographs. `?hud` earns its exception by being the only way to read some
  things on a real device; a harness can click, so a panel flag has no such
  argument. **The gate reaches into the page rather than the page growing an
  affordance for the gate.**

  It locates the toggle by `[aria-expanded]` — the one attribute nothing else on the
  page carries, and the locator `devices.py` and `a11y_audit.py` already use — never
  by coordinates, because the corner row has been renumbered once already (CL#114)
  and a click into empty space photographs a **shut** panel and reports 0px, which
  is #144 reintroduced inside its own fix. Open-ness is a condition, not a sleep:
  `aria-expanded === 'true'` **and** a non-zero input box inside the nav, the second
  half being load-bearing because a `display:none` subtree reports every rect as 0x0.

  **The deliverable is the PAIR of mutants, not the flag.** The same one-pixel edit
  — `--thumb` 16px → 15px, whose centring margin is derived so the disc also shifts
  half a pixel — registered twice with opposite expectations:

  | mutant | gate | result |
  | --- | --- | --- |
  | `panel-thumb-one-px` | new `panel` | **caught, 132px differ**, max delta 117 |
  | `panel-thumb-invisible-shut` | existing `pixels` | **survives, 0px, PASS** |

  Identical edit, 0px shut against 132px open: that **measures** the coverage gap
  rather than asserting it, and `--gate panel --blind` reports 0/1 caught, so the new
  gate is inside the mutation gate's own self-proof. Wired into the deploy alongside
  the three existing invocations.

  **It also became the first thing in the tree that can see #149.** `PANEL_BOX_JS`
  prints the open panel's box, cap and overhang per viewport: at 844x390 the panel is
  **396px against a 374px cap — exactly #149's 22px**, from padding on a
  `content-box` element. Diagnostic rather than verdict, deliberately, since #149 is
  an `index.html` fault. At the two shipped gate viewports the panel is 568.6px
  against an 828–884px cap, which is precisely why the fault has hidden.

  One correctness fix outside the brief and worth keeping: every "could not
  photograph" path (`serve`, no DevTools endpoint, `wait_until`, `settle`,
  `stable_render`) raised `SystemExit("FATAL: …")`, which **exits 1 — this tool's own
  word for "the artifact moved"**. They now route through `fatal()` and exit **2**,
  matching what the module docstring has always promised. CL#159's lesson one rung
  lower, in the codes rather than the prose.

  4 consecutive runs, zero flake notes, zero variance; also 0px under
  `WOZI_PX_CPU_THROTTLE=6`. Every existing invocation still 0px with controls 0px.
  `mutation_gate` 14/14 caught, 1/1 tolerated, 1 known gap (the deliberate one), 6/6
  controls green. `npm test` 120/0.

- **CL#173 — light's `--muted` clears 4.5:1, and it turns out to live in a 0.15-wide
  window with two automated walls.** (GitHub #151, closes it.)

  `--ref-muted` `#6B7E7C` → **`#677977`**, a hue-preserving step, plus `togList`'s
  active pill taking `var(--chip)` instead of `var(--bg)`. All five failures clear:
  the two headings and both readouts 4.285 → **4.587**, the selected row 4.427 →
  **5.688**.

  **The finding #151 did not have: the failing ground is `--chip` (white), not
  `--bg`.** Every measurement in #120 and CL#131 was taken against the page —
  3.33:1, correctly reported as a 3:1 problem, because everything `--muted` paints
  there is a glyph or large text. The **panel is a different, lighter ground**, so it
  carries the *higher* ratio and is the only place `--muted` sets ordinary text. That
  is why 4.28 → 4.59 suffices where the page's number made it look like a much
  bigger move was needed.

  **Neither of #120's candidates can ship, and that is measured rather than
  aesthetic.** `#5A6E6C` (5.41) and `#4F6462` (6.30) both clear 4.5:1 easily and
  **both fail `npm test`** — because light's `--muted` IS `--ref-muted`, darkening it
  strengthens the datum's judged reference, `datumOpacity()` raises **dark's** solved
  alpha 0.27 → 0.31, and `datumInk()`'s green channel clamps at 255 once that alpha
  rounds past **0.28**, so the mark composites to 71.6 where the solve asked 74.6 and
  the datum test fails in exactly the terms that function's own comment predicts.

  So the token sits between two computed walls, **both held by automation**: a floor
  at `#687A79` (4.5:1 on `--chip`, held by `a11y_audit`) and a cap at `#657876`
  (dark alpha ≤ 0.28, held by `npm test`). `#677977` is mid-band at 4.587:1 and alpha
  0.2812 against a 0.285 cutoff. That is thin, and both walls plus which gate holds
  each are now written at the token.

  The fifth finding is a different pair and got its own look: the active pill is
  punched out of the **panel**, so it should take the panel's ground; `--bg` is a
  surface that row never touches. `--chip` beats `--bg` for **all five** accent enum
  options, so it is a strict improvement rather than a fix for the shipped one, and
  it needs no theme branch (dark holds at 6.63 by the same argument).

  Blast radius checked across every `--muted` consumer in light — corner glyphs, the
  departure indicator, the wordmark's `.com`, the slider track and `--thumb-color`,
  the toggle's OFF knob, `?hud`'s labels (unaudited, and also failing before this) —
  **nothing gets worse**; the page-ground consumers go 3.335 → 3.570 against a 3:1
  floor. **#120's light/dark drift is narrowed, not closed**: that remains a palette
  question rather than a threshold one.

  `a11y_audit` PASS in **both** themes with `in force:` asserting light was genuinely
  exercised at a non-1x speed with the panel open — the first time that has actually
  happened, per CL#171. `npm test` 120/0. Pixel deltas region-decomposed rather than
  quoted: combined light 9,270/4,135, dark 5,847/3,483, solo light 1,905/850, **solo
  dark 0** — and every changed pixel accounted for, **none on a gear**. Solo dark
  being 0 independently confirms the dark-side change is entirely the datum's alpha
  stepping one rounding place.

- **CL#171 — `a11y_audit` had never audited the light theme, and fixing it turned up
  five real contrast failures.** (GitHub #145, closes it.)

  #145 asked whether `a11y_audit`, `verify_motion` and `escape_mesh` carried the
  unpinned-webfont exposure CL#162/#168 fixed elsewhere. The answer per harness was
  measured before anything changed, and the honest split is three different answers —
  but the font question turned out to be the least of it.

  **`a11y_audit.py` has never audited the light theme.** Its preference-injection
  snippet was an f-string concatenated with a plain string, so the `}}` escape did
  not apply in the non-f half, the injected JS carried a stray brace, and it threw
  `SyntaxError` into a return value nothing inspected. Measured: the old flow reports
  `data-theme='dark'` and `wozi-speed=null` in **both** passes. So **every
  "a11y_audit PASS in both themes" in this changelog is one theme audited twice**,
  and CL#114's stated reason for pinning speed off 1x — auditing the corner departure
  indicator — never happened. The gate now asserts what it actually audited, per
  pass, so it cannot recur silently.

  **With that fixed it is RED, on five pre-existing `serious` contrast failures**,
  light theme only, all in the pop-out control surface: both section headings and
  both slider readouts at **4.28:1** on `--muted` `#6b7e7c`, and the selected row's
  label at **4.42:1**, against a 4.5:1 threshold. Filed as **#151**.

  **Two of those five are a regression from CL#169, one commit earlier**, and the
  mechanism is worth recording because no colour changed: CL#169 dropped the Speed
  and Wear readouts from `var(--icon)` 20px to `LIST_ROW_FONT_BOLD` 13px. At 20px
  bold they were WCAG **large text** with a 3:1 threshold, which 4.28 cleared; at
  13px bold they are normal text at 4.5:1, which it does not. The size change moved
  the threshold, not the ink. CL#169's compaction was measured carefully for height
  and for hit-box overlap and nobody thought to ask whether shrinking type crossed a
  contrast boundary — and the gate that would have said so had never run in light.

  **`verify_motion.py` was exposed, and it is the one assertion flip found
  anywhere** — not through type (rotations 40/40, badge offsets 0.00-0.01px,
  identical in both regimes) but through check 3, *"no console errors"*: unreachable
  fonts produce three `ERR_CONNECTION_REFUSED` lines, so **a Google Fonts outage or
  a runner without egress turned a gate CI runs on every push red for something that
  is not the code**. Now demonstrated fixed: with both the prefetch and Chrome's
  resolver blackholed it announces `fonts: BLOCKED`, tolerates exactly the font-host
  lines, and passes — while in `pinned` mode those same lines still mean the pin
  leaked.

  **`a11y_audit`'s own font exposure is zero in its assertions**, measured across 12
  deals: every hit box identical to 0.01px, the tightest box 24.00x24.00 in both
  regimes. The one number that moves is a Table of Gears row's **width** (268.63 vs
  270.52px) and nothing asserts a width — the row's *height*, which the 24x24 floor
  would bite on, does not move. Pinned anyway as insurance, the `devices.py` verdict.

  **`escape_mesh.py` is immune and was NOT changed except to say so.** A full
  `--census` across 4 seeds x 2 viewports is byte-identical between regimes — 148
  lines, every ghost and residual to the last digit — because it measures only radii
  and centres and never enables the `Log` domain, so the stylesheet's failure is
  invisible to it. Documented rather than pinned for symmetry.

  Two further harness bugs, both of the CL#168 class: **both harnesses asked
  `/json/new?<URL>`**, so the tab navigated *before* interception was armed and that
  first fetch warmed the font cache for every measured render — they now open
  `about:blank`; and `verify_motion` held an `asyncio.sleep` in the render path,
  which holds the stylesheet for its duration and lets it land afterwards, i.e.
  manufactures the regime it was hiding. Its 3.5s settle is now a condition at
  ~0.10s.

  `npm test` 120/0. `verify_motion` PASS x10 plus PASS under a simulated total font
  outage (exit 1 before). `escape_mesh` PASS x3. `pill_clip`, `dom_invariants`,
  `devices`, `pixel_regress` all verified undisturbed. `mutation_gate` 13/13 caught,
  1/1 tolerated, 5/5 controls green. `a11y_audit` FAIL x4 **identically** — a side
  benefit of the pin.

- **CL#170 — `hexcore`'s cell-size search is memoised, and the estimate it was
  approved on was wrong.** (GitHub #135, plan B.)

  `hexcore` was **50.4ms of `gearSvg` at 6x against `sunburst`'s 2.1ms**, because its
  cell-size search is a triple-nested sweep — `CELL_FLOORS` x `rOutTry` x ~n sizes at
  0.05 steps — enumerating the whole lattice per candidate size and discarding all
  but the winner, **recomputed on every one of the five renders per cold load**.

  **Memoised, deliberately NOT bisected.** Feasibility is genuinely non-monotonic in
  cell size: the rings are anchored at the wheel centre so a ring is wholly in or
  wholly out, and CL#138's own comment records the case that proves it — a 13-tooth
  wheel whose only feasible size sat just under one grid point. A bisection over a
  predicate that switches on and off along the axis is entitled to land on a
  different winner, which would move the drawing; the floor-anchored grid exists
  precisely so the tested SET is fixed. Memoisation cannot change which size wins
  because it does not change the search.

  **The key is seven numbers and every one of them earns its place**, verified by
  reading the sweep rather than trusting the profile: `rInX`; **both** entries of
  `rOutTry`, because the fallback attempt reaches the second so the pair is an input
  rather than just the winner; `WALLX`; **both** `CELL_FLOORS` entries, because the
  shared floor is an aim rather than a gate (CL#138) so *which* floor produced the
  answer is part of the answer; and `ceiling`. `CELL_FLOORS[0]` is what makes the key
  scale-dependent — it carries `MIN_CUT`, which is stated in **pixels** and converted
  by `px()` (CL#137), so omitting it would serve a phone the lattice solved for a
  desk. `ceiling` is keyed on the **derived** value rather than its three inputs, so
  a change to how it is computed cannot leave the key behind. `S` and `g.teeth` are
  deliberately absent: they reach the sweep only through `px()` and the radii and are
  already carried.

  The keep is inside the memo too, so the cached value is the finished list of cut
  paths, which also retires `vertsX` from repeat renders. `bestWaste` was written and
  never read; it went with it.

  **The ticket's ~50ms was not achievable, and that is worth recording rather than
  quietly under-delivering.** Real saving on a hexcore-heavy deal is **≈12.6ms of
  `gearSvg` and ≈19ms of the task at 6x** (183.3 → 164.5ms; 26.0 → 23.0ms at 1x).
  Two structural reasons: the 50.4ms is spread across all five renders, and only
  **three** can hit — render 1 draws at the boot `--gsfit` of 0.86 and renders 2+ at
  the real ~1.4, so there are two distinct scales and therefore two unavoidable
  misses per wheel. Call counts confirm it: `at` 46,006 → **20,496**, `vertsX`
  9,587 → **2,440**, i.e. the sweep now runs about 2.2 renders' worth instead of 5.
  **Plan A compounds with this** — killing the boot-scale render leaves one miss
  instead of two.

  The default deal barely moves (184.0 → 178.8ms combined at 6x, inside noise)
  because it draws few or no `hexcore` wheels. That is the point: this removes the
  **tail** the deal creates (#143), not the median.

  **What bounds the map:** one entry per wheel geometry per `--gsfit`, and `fitStage`
  quantises `--gsfit` down to 1% over ~0.28–5.12, so a resize drag walks a bounded
  ladder rather than a continuum. `HEX_MEMO_MAX = 48`, cleared **wholesale** at the
  cap rather than evicted one at a time — a miss costs one sweep, an LRU costs a
  second structure to keep honest.

  **`pixel_regress --query '?who=charles&kind=hexcore'` is 0px at both viewports
  with controls 0px** — the mandatory check, since a mixed deal's 0px would be
  agreeing about a picture it never took (CLAUDE.md). Byte-identical lattice means
  the key is right. Combined stage and `?who=charles` also 0px. `npm test` 120/0,
  `dom_invariants` PASS on both the combined stage and forced to hexcore,
  `verify_motion` 40/40 with 0 console errors.

- **CL#169 — Machine Settings gets toggle switches and a 16px thumb, and the rows
  tighten.** (GitHub #134, closes it.)

  Charles: *"Make machine settings checkboxes and sliders more compact and reflect
  more machine-like vibe."* Then, from a six-candidate sweep, a combination that was
  not one of the rows: *"toggle switches + compact circle slider (what we have now is
  ok, but it's too big)."*

  **The toggle won on a measurement, not a look.** The sweep found that **no**
  candidate — the shipped one included — reaches WCAG 1.4.11's 3:1 for on-versus-off
  in **light** mode (knurled-lamp 1.86, toggle 2.22, instrument-plate 2.33, shipped
  2.85). The toggle is the only one whose state cue is **positional**: the knob
  moves. That property is recorded in capitals at the site with the four figures, and
  with an explicit instruction not to convert it back to a colour-only cue.

  **It also had to be fixed to have that property at all.** The swept version drew
  the knob `--chip` in both states — measured **1.28:1 light / 1.20:1 dark** against
  the off pill, because `--chip` is the panel's own colour and they are deliberate
  neighbours. The knob was invisible, defeating exactly the thing it was chosen for.
  It now takes whichever token contrasts with its slot: 3.33:1 light / 6.21:1 dark
  off, 5.69 / 6.63 on.

  **And a caveat left standing rather than papered over:** the ON figure rides
  `--accent`, which `syncVars` writes per person. Four of `config.js`'s five accents
  give 3.21–5.69:1; **amber `#F4B32B` gives 1.86:1 in light**. Accepted because by
  then the pill has changed colour and the knob has moved, and recorded as wanting a
  design decision rather than a token swap.

  **The thumb is 16px, and the WCAG floor is not what bounds it.** The slider's
  target is the input's full 129x44 box — CL#155's hit-vs-visible split — so
  `a11y_audit` passes at 24/20/16/12 alike and never becomes the disc's floor.
  What bounds it is **readback**: the slider steps over `SPEED_STOPS` by index, so
  someone wanting a particular stop reads position off the disc, and 12px stops
  reading as a separate part. 16 is 4x the 4px track.

  **The compaction is 650 → 569px, NOT the 542px Charles was shown** — that figure
  was a candidate which also took checkbox padding to 0, tightened both headings and
  halved the separator. He approved two levers, two shipped, and the remaining ~27px
  is left on the table deliberately.

  **`rowAntiOverlapGap` had a rounding trap that a model rounded the wrong way turns
  into real overlap.** `centreDistance = --btn + (realLine - modelledLine)`, so
  modelling the content line *up* steals margin: `Math.ceil(13 x 1.3) = 17` measured
  **-0.1px of genuine hit-box overlap**. The model is now floored to Chrome's own
  1/64px `LayoutUnit` grid, which is at or under both Chrome's and Gecko's line box.
  Measured after: the two inputs' edges meet at **exactly 236.15px**, centres exactly
  44.00px apart.

  Readouts are `LIST_ROW_FONT_BOLD`, derived from `LIST_ROW_FONT` by one replace
  rather than a second hand-written 13px.

  `npm test` 120/0. `a11y_audit` PASS x2 with **0 targets under 24x24**, switch box
  40x24, range box 129x44. `devices.py` 24/24 and 4/4 with the tightest profile's
  clearance unchanged at 8px. Slider reachable at 844x273 on the combined stage and
  on `?who=charles`. All eight stops step with the readout tracking and
  `--thumb-color` flipping at index 4; all three switches flip, restore, and move the
  knob; Wear 100% still touches exactly 2 of 40 tooth-path sets.

  **`pixel_regress` 0px is NOT evidence about this change** — the panel is
  `display:none` with no forcing parameter (**#144**), so the gate cannot photograph
  a single control here. What the 0px does usefully prove is the negative: the
  machine itself is byte-identical, so none of this leaked into the artwork.

- **CL#167 — the plate's far-end anchor is now covered by the suite, and the mirror
  image is a registry mutant.** (GitHub #138, closes it.)

  CL#160 made `plateSeat()` choose which END of the datum mark to stamp the label
  at, by measuring the wordmark and taking the end furthest from it. **Every
  existing plate test ran without a `_brandBox`**, so they all took the fallback
  branch — the behaviour that shipped *before* CL#160 — including CL#152's
  mutation-tested *"a plate gives way to the metal"*. The far-end path was covered
  by measurement and by `pixel_regress`, and by nothing that would fail.

  One test, six claims, and **no new extraction anchors** — `plateSeatOn` gained a
  ninth parameter set as `_brandBox` on the fabricated ctx, the same
  dependency-injection move `_vpBox` already uses, so the six pre-existing callers
  keep testing the near end and not one existing assertion was edited. #113's
  region map and CL#165 both argue against adding anchors and neither was
  contradicted.

  **The claim that earns its place is the fourth: the brand decides, not the
  orientation.** The same portrait run with the wordmark moved to the *top*-left
  must stamp at the bottom. A "far end in landscape, near end in portrait" hardcode
  passes every other claim — it is the #67 mirror image, legal geometry that no
  measurement taken along the axis can distinguish — and only that assertion kills
  it. It is now the registry mutant **`plate-anchor-by-orientation`**, recorded with
  the fact that it scored 119/0 and exit 0 before this test existed.

  Three mutants, each verified to fail and then restored: forcing the near end
  always, the axis-terms handedness above, and **searching only at the near
  anchor** — the last being invisible to CL#152's own test, which is precisely the
  gap this ticket named.

  `npm test` **120/0**. Full sweep 13/13 caught, 1/1 tolerated, 5/5 controls green.
  Verified independently by breaking the anchor gate here and watching the new test
  go red, then restoring to byte-identity. Also cross-checked against CL#166, which
  landed mid-flight: that changes the label's CROSS-axis side, not `plateSeat`'s
  along-axis anchor, and the suite is 120/0 against it.

- **CL#168 — three more harnesses pin the webfont, and `pill_clip` was carrying the
  fault live.** (GitHub #140, closes it.)

  CL#162/#163 fixed `pixel_regress`. `tools/fontpin.py` now lifts that mechanism
  out — behaviour verbatim, not re-derived — and `pill_clip`, `devices`,
  `dom_invariants` and `pixel_regress` all share it.

  **`pill_clip` was the worst exposed, and it is the fault class exactly**: same
  page, same run, only the font's reachability changed — worst overrun **−0.58px
  with Manrope against −1.45px without**, i.e. 0.87px of swing against a **+0.05px
  tolerance** and 0.58px of real clearance. Neither regime trips the gate today,
  which is what made it dangerous: **a regression eating 0.6px is caught in one
  regime and passed in the other**, and the only hint in the output was a `face`
  column nobody diffed.

  **`devices` measured exposure of exactly zero** — all 28 rows byte-identical with
  both font hosts blackholed — and is pinned as insurance on 28 races and because it
  overrides the UA per profile, where Google legitimately serves different CSS to
  different engines. Said plainly rather than dressed up as a fix.
  **`dom_invariants` is exposed only in a diagnostic**: `shortest 'harper'` moves
  21.7 → 23.5px, no assertion depends on it, and it is pinned so a human diffing
  two same-seed runs is not shown a line moving with nothing changed.

  **Two real harness bugs surfaced, both hidden by the sleeps it removed.**
  `pill_clip` read hover coordinates before layout settled, so one of eight pills
  came back 0px wide — which reads as #46's "feature broken" rather than as a
  harness fault. And `devices`' safe-area pass could poll the **outgoing** document
  as ready, measuring at 1x with the panel shut; it now discriminates by a marker
  on the doomed document instead of a guessed 0.4s.

  `attach()` replaced the loop-until-my-id CDP helper all three carried, which
  discarded unsolicited `Fetch.requestPaused` and deadlocks once a paused request
  must be answered. And a plain `asyncio.sleep` in a render path *holds* the
  stylesheet for its duration and lets it land afterwards — which is the late-font
  regime itself, so the sleeps were not merely slow, they manufactured the bug.
  `dom_invariants` went 4.7s → **1.2s** as a side effect.

  Repeatability added in **one** place with a reason: `pill_clip` measures absolutes
  so it cannot subtract two renders — it now navigates twice, matches by
  aria-label, and exits **2** without a verdict if the two disagree by more than
  0.01px. `devices` (28 profiles are already a spread) and `dom_invariants` (exact
  integers, zero-tolerance residuals, both wobble sources now conditions) were
  deliberately left alone.

  `npm test` 119/0 at the time; `pill_clip` PASS x4, `devices` 24/24 + 4/4 x4,
  `dom_invariants` PASS x6, `pixel_regress` 0px with control 0px and 0px on
  `/fidget/`. Mutation sweep 10/10 caught with `pill-line-height` still caught at
  +1.82px.

- **CL#166 — the datum label sits opposite the ticks, referenced to its own ink, so
  the gap is the same for every chain.** (GitHub #139 follow-up.)

  Charles, looking at CL#164 on the live site: *"why on the light mode does the
  spacing between the name and the datum seem to be inconsistent."* He was right,
  and it was a bug I shipped. Measured: **17px for Charles against 6px for Harper**
  at 1440x900 — exactly `MAJOR - HAIR/2`.

  **The cause was two rules I asked for interacting.** CL#164 made the side ONE
  consistent side for every chain (his own N-chains requirement), but the standoff
  still cleared *whatever that side happened to carry on this chain*: the full tick
  length where the consistent side coincided with that chain's own tick direction,
  a hairline where it did not. Each rule was defensible alone. Together they made
  the gap depend on which way an individual chain's ticks point. Portrait looked
  fine only because both chains happened to land the same way — luck.

  **Charles's own fix was the better rule: put the name opposite the ticks.** Then
  no label ever has a tick to clear and consistency is structural rather than
  maintained. Which forced the honest finding underneath it: **consistent gap and
  one consistent screen side are mutually exclusive.** A chain's tick direction
  mirrors with its own origin, so "opposite the ticks" is per-chain by definition —
  it gives one gap for N chains and cannot give one side. At four chains, two land
  on the other side. He chose the gap, having seen both.

  **The standoff is now referenced to the INK, and that closes a second
  inconsistency before it shipped.** `PLATE_H/2` was doing real work — a centre
  being placed, an edge having to clear — but it referenced the *reserved box*,
  which is 0.769x the type and ignores what is drawn. Harper has a descender and
  Charles does not, so a box- or baseline-referenced standoff hands them different
  gaps: measured at **3.19 / 4.30 / 5.40px** at the three sizes, up to half the bug
  just fixed. The eye measures to the nearest *drawn* pixel — which is what Charles
  did when he caught the 11px — so `textInk()` measures the real extent and the
  standoff clears that. `MAJOR` disappears entirely; only the air remains judged.

  **`DATUM_MARK_AIR` is a multiple of `pad`, deliberately not of the type**, so
  growing the name does not push it off the rule. That orthogonality is what makes
  "bigger AND closer" expressible at all.

  Size 1.75 and air 1.5 are Charles's picks from a 3x4 grid plus references, 64
  renders. **Verified independently in PIXELS**, because a DOM reading cannot
  answer this: `getBoundingClientRect` on an SVG `<text>` returns the em box (26px
  against a 17.1px ink height), so it reports overlap where the ink clears — my own
  first check said 29px spread and was measuring the wrong thing. Pixel truth:
  **desk 4.00 / 5.50px, phone 2.50 / 2.50px**, against today's 19 / 8. Bigger,
  closer, and consistent.

  **The occlusion Charles pre-approved turns out not to occur.** He agreed to the
  name going behind the machine; measured, **0.0% of the mark's pixels land on
  metal** in every positive-air cell, both themes, both viewports, to size 2.20 —
  because the rule is already stood off the chain by `PLATE_TOP_CLEAR`, so a name
  placed inboard lands in that existing gap. No type-over-type collision with the
  wheels' own engraved rims arises either; the nearest engraved wheel stays 42-48px
  away, and the first thing a larger name approaches is a *ghost*, which carries no
  rim lettering at all.

  **One residual that cannot be removed, and it is why 1.75 rather than 2.20.** The
  mark is three copies — cut raised, lit dropped, ink between — and *which copy
  faces the rule flips with the side*, while one of the two is nearly invisible in
  a given theme. So the visible gap varies by up to one relief depth (`fs x 0.12`),
  which is the whole of the measured 1.5px desk residual. Making the relief
  symmetric would contradict the overhead-lighting rule (#10). It grows with size,
  so it caps how consistent this can ever look.

  Zero `plateSeat` warnings and zero console output in all 64 renders. `npm test`
  119/0. Contrast flat across the grid and size-invariant, confirming CL#164.
  `datumRelief()` and `textInk()` are new single homes — `datumStamp()` no longer
  restates `fs*0.35` or `max(1, fs*DATUM_ETCH_DEPTH)`.

- **CL#165 — the block extractors refuse an ambiguous anchor instead of taking the
  first one.** (GitHub #137, closes it.)

  `tools/test.js` reads its constants, the two-row menu and the sizing functions
  **out of `index.html`** so the suite measures what actually ships. CL#112
  hardened `grabNumber` under #101 to throw on ambiguity. The block extractors got
  none of that, and the scope turned out wider than the ticket: **`grabBlockFrom`
  has 66 anchors, `grabDecl` had the identical fault with 47 more**, and
  `tools/mesh_extract.js` was a third copy of it.

  **Two anchors were already ambiguous in live code** — `BRIDGES.forEach(b => {`
  occurs twice and `ORIGINS.forEach(o => {` three times, because `solve()` walks
  the same lists — and were resolving correctly *by file order alone*. Both now
  carry their second line. That is a latent fault found, not a hypothetical one
  guarded against.

  **The fix masks comments to SPACES rather than deleting them**, so offsets found
  on the mask still point into the real file: every extractor now *matches on the
  mask and slices the original*, which is what keeps the text handed to the suite
  the page as written (two tests regex an extracted block for things a comment is
  allowed to mention) and keeps a stripped artifact's `/*L1234*/` backlink out of
  it. `STRIPPED_SRC` became the same one home rather than a second idiom.

  **The scanner is deliberately naive and the asymmetry is the argument**: this
  mask only *locates*, so mis-masking live code makes an anchor **vanish loudly**
  while leaving a comment unmasked lets prose satisfy an anchor **silently** —
  which is the bug. Rather than duplicate `strip_comments.py`'s state machine, the
  naive mask was verified empirically against this file: 722 `/*` and 9 `<!--` pair
  up exactly with no nesting, there are **zero `//` line comments** in either
  `index.html` or `config.js`, and masking all 731 leaves every `<script>` body
  passing `node --check` — so no `/*` currently lives inside a string, template or
  regex, and if one ever does the anchors in that region go missing rather than
  going wrong.

  Indentation is out of the anchors both ways: leading whitespace now means "first
  thing on its line, at any indentation", and 21 anchors had two spaces baked in.
  Brace and `;` matching moved onto the mask too — a `{` in prose used to count.

  **Proven by mutation, and the old extractor fails silently in two of three:**
  a second `driveCap() {` declared after the real one (JS lets the later win, so
  the page runs `return 8`) passed **exit 0, 119 tests green** before and refuses
  now; an anchor commented out passed **exit 0, 119 green** before and now names
  the difference between a stale anchor and one that "IS in the file, but only
  inside a comment"; and a whitespace-only re-indent was **red before** on a
  `git diff -w` no-op and is green now. That third case needed a new expectation
  kind — `tolerated`, a legitimate edit the gate must stay green on — because an
  extractor that *refuses* a re-indent is the weakness, not the guard, so the
  honest assertion is the negative control rather than a fake "known gap".

  Full sweep: **12/12 mutants caught, 1/1 legitimate edit tolerated, 0 known gaps,
  5/5 controls green.** Every pre-existing mutant still caught, `stripper-ate-a-line`
  included.

  **Extraction is byte-identical**: 117 instrumented records over a full run, 116
  distinct anchors, **all hashes unchanged** — the only lines that move in the
  keyed diff are the two anchor strings that were extended, and both extract the
  same bytes. The stripped artifact resolves the same 116-key set, and `npm test`
  passes against it (632,729 → 192,834 B), which matters because CL#159 made that
  run the only gate reading the page as text.

  Memoising anchor resolution left it **faster than before** despite far more work
  per lookup — 7.4s against an 8.6s baseline, where an unmemoised mask would have
  been 35s.

- **CL#163 — the pixel gate stops blaming the artifact for its own wobble.**
  (GitHub #113, superseding part of CL#162's design.)

  CL#162 pinned the webfont, which was right and fixed the first fault. Its
  **control** — photograph the working tree twice — then caught a *second*,
  narrower non-determinism on its very first CI run: 1,235px at 1440x900 on the
  combined stage, max channel delta 10, while `?who=charles` and `/fidget/` were
  0px. It correctly refused to claim anything about the artifact.

  **The cause is rasterisation, not the integrator** — the leading hypothesis
  (accumulated phase drifting between renders) is **refuted by measurement**: every
  `transform` attribute and inline transform was dumped after the 90-frame pump
  across 10 passes under the contention that produces the flake, and there is **one
  distinct transform set out of ten**. The master angle does not drift; `step()`
  reads only the already-pinned `performance.now()`, and `Date.now` appears nowhere
  in `index.html`.

  It reproduced only under 16-way CPU contention **plus the runner's own flags**
  (`--no-sandbox --disable-dev-shm-usage --disable-gpu`, which macOS never
  exercises): 1,214px at delta 10 against CI's 1,235px at delta 10. CPU throttling
  alone never reproduced it, which is the tell — throttling slows everything
  proportionally and preserves ordering, whereas contention perturbs it. The
  mechanism is Chrome's freedom to render a pass differently: partial raster reuse,
  a capture landing mid-compositing, and the harness window parked at
  `-4000,-4000`, which is exactly the window Chrome may treat as occluded and
  deprioritise. Antialiasing-scale, and combined-stage-only because that stage has
  the most content to raster.

  **`DETERMINISTIC_FLAGS`** removes that freedom without changing what is drawn —
  ten launch flags (`--run-all-compositor-stages-before-draw`,
  `--disable-partial-raster`, the occlusion/backgrounding three, the threading two,
  `--force-color-profile=srgb`, …), **verified appearance-neutral at 0px / max
  delta 0** against the original pre-CL#162 real-network baseline.

  **And the second bug, which is the one that actually blocked deploys.** CL#162
  shot the working tree twice and the ref **once**, so an odd pass on the *ref*
  side left the control reading a contented 0px while the artifact comparison read
  1,214px — the gate blaming the stripper for a wobble in its own measurement. That
  happened in **2 of 3** reproduction runs; CI got lucky in the other direction, its
  odd pass landing on a working pass so the control caught it. `stable_render()`
  now photographs **each tree until it agrees with itself** (up to 3 attempts) and
  only then subtracts, with the working tree checked before *and* after the ref so
  its agreement spans the run. A third pass prints a greppable `NOTE:` naming the
  flake rather than failing; no two agreeing is a loud exit 2.

  **No tolerance was introduced anywhere** — not on the diff, not on the control. It
  turned out not to be needed, which is the outcome to prefer over a threshold
  chosen to make a red run green.

  Independently validated, 14 runs of the combined stage at 1440x900: **0 flakes in
  14 with the flags** (8 unloaded, 6 under contention), against **2 of 6 without
  them** — and all six still produced the correct verdict, because `stable_render`
  absorbed the odd pass instead of misattributing it. So the flags remove the cause
  and `stable_render` makes any residual survivable and correctly blamed.

  Sensitivity unchanged: `stripper-ate-a-line` still caught at **exactly 2,933px,
  max Δ52**, control 0px. `npm test` 119/0. Runtime ~15s for two viewports across
  six passes — still faster than the pre-CL#162 four-pass version, because the
  condition-based settle replaced 4s of sleep per navigation with a few hundred ms.

  **`--frames 90` was left alone deliberately.** Seven runs at `--frames 0` showed
  no odd pass, hinting the rotated train's sub-pixel transforms are what give
  raster something to wobble on — but seven runs against a ~33% rate is not
  significant (p≈0.05), and dropping the pump would stop exercising
  `applyRotation()` entirely.

- **CL#162 — the pixel gate pins the webfont, proves it did, and shoots a control.**
  (GitHub #113, found by CL#159's first real deploy.)

  CL#159's artifact gate went red in CI — 195px and 2,016px on two different
  viewports of two different checks — while the identical build measured **0px at
  every viewport locally**. The stripper was innocent; the harness was not.

  **The cause is not cache warmth** (the first hypothesis, refuted: `fromDiskCache`
  is `False` on every navigation, so all four navigations per check re-race
  independently — which is why the failing viewport differed between checks). It is
  that **the drawing depends on WHEN Manrope arrives relative to the page's own
  first render**, and that time comes off a third party's network. `index.html`
  clears its `textWidth` memo on `document.fonts.ready` (GitHub #98), so engraving
  metrics are measured early and only partly re-measured.

  Measured by holding only the font requests — a clean **step function**, identical
  at every delay past the boundary: held 0–1.2s gives 0px, held 1.4–3.6s gives
  2,941px at 390x844 (nine narrow row bands, one per wheel: the engraved
  lettering), held forever gives 329,160px. **The corroboration that settles it:
  `/fidget/` is the only published page with no Google Fonts link, and it was the
  only check that passed both viewports in CI.**

  **The font is now pinned off the network** the same way `Math.random` and
  `performance.now` already are: the CSS and every face are prefetched into the
  process before any browser starts — under a Chrome UA, because Google serves
  legacy TTF with different metrics otherwise — and fulfilled from memory. The
  pinned render is **byte-identical to the old harness's real-network render**, so
  real typography is preserved rather than traded away. One state is chosen once per
  run and enforced on both trees, and **verified after every render by a width
  probe** (640.4 vs 698.4px discriminates, where `document.fonts` does not).

  Note why the Font Loading API cannot answer this: with the requests blocked,
  `document.fonts.status` is `loaded` and `check('600 13px Manrope')` is `true`,
  because the stylesheet never arrived, so no `@font-face` was ever registered and
  `check` on an unknown family trivially agrees.

  **`sleep(4.0)` is gone.** Readiness is a condition — load complete, `fonts.ready`
  settled, then two screenshots 150ms apart that come back byte-identical — with a
  loud timeout naming the binding term. ~20s to ~7.5s per check.

  **And the gate now shoots a control**: the working tree twice, once before the ref
  pass and once after. While those disagree, no pixel count is reported as a
  verdict. Under a coin-flip reproduction of the CI fault it prints *"HARNESS NOT
  REPEATABLE — the SAME bytes photographed twice disagree"*, which is what run
  31558915146 should have said. Honest limitation, documented in the file: a
  **uniform** shift lands all passes in the same regime and still reports PASS — the
  control catches asymmetric instability, which is what the real fault was.

  **SUPERSEDED IN PART BY CL#163, and the way it was wrong is worth keeping.** This
  control shot the working tree twice and the ref only **once**, so an odd pass on
  the *ref* side left the control reading a contented 0px while the artifact
  comparison read a real-looking difference — the gate blaming the artifact for a
  wobble in its own measurement, in 2 of 3 later reproduction runs. The control
  earned its keep anyway (it caught the residual on its first CI run and refused to
  claim anything), but "photograph one side twice" is half a control. CL#163 makes
  **each** side agree with itself before they are subtracted.

  Rejected and worth recording: **DOM quiescence via MutationObserver** — written
  first and unusable, since `fidget/index.html` runs `setInterval(draw, 250)` so a
  quiet DOM is unreachable there; **warming the cache** (nothing to warm); and **an
  absolute budget on font arrival**, implemented then removed after measurement
  showed it anti-correlated — 310ms settled with 53ms first paint gave the *correct*
  picture while 131ms settled with 202ms first paint gave a 999px wrong one. A
  constant that does not measure what it claims is worse than none; both numbers are
  still reported as diagnostics.

  Sensitivity preserved and proven rather than assumed: `mutation_gate.py --only
  stripper-ate-a-line` is still **caught at exactly 2,933px, max Δ52** — the
  identical count the old harness produced — with the control at 0px, so it is
  correctly attributed to the artifact. Five consecutive repeat runs PASS. `npm
  test` 119/0.

  **The artifact is exonerated:** on the real stripped build, `/`, `?who=charles`
  and `/fidget/` are all **0px at both viewports**, controls 0px throughout.

- **CL#160 — the datum plate is stamped at the end of its mark furthest from the
  wordmark.** (GitHub #131.)

  Charles: *"shift datum name badges to be on the right (landscape) and top
  (portrait) - this should help with spacing when near 'wozi.com' badge."* The
  crowding turned out to be worse than crowding: at 1440x900 Harper's plate
  **intersected the wordmark's box on both axes** (x −84.3, y −21.4), and
  Charles's overlapped it in x by 93.4px while clearing it vertically.

  **The rule is deliberately not written down as "right in landscape, top in
  portrait."** That phrasing is a handedness stated in screen terms over a
  direction that comes from `_axisRot` — the #67 trap exactly, and its mirror
  image passes every measurement taken along the axis. Instead the wordmark is
  measured into `_brandBox` and the plate takes whichever end of its mark stands
  furthest from it, by a screen-space dot product. A signed distance cannot be got
  the wrong way round without the sign being wrong, which is checkable. Charles's
  two cases then **fall out** rather than being encoded: the mark runs along the
  travel axis and the brand is bottom-left in both orientations.

  The wordmark is **measured, not restated** — its box is a `clamp()`ed font size
  plus a safe-area inset, so only CSS knows it, and a restated corner would drift
  the first time `--offleft`, `--offbot` or the type size moved.
  `PLATE_START_ALONG` stayed one number and became one signed step, so the
  mark's-own-end-vs-frame rule is one rule rather than a start reading with a
  far-end special case.

  **CL#152's clearance search still bites at the new anchor**, which landscape
  proves rather than merely permits: Charles lands flush at exactly
  `PLATE_START_ALONG` from the far edge, while Harper **slid 131.4px inboard** of
  that flush point with a clean console — `plateExcluded`/`plateNearestClean`
  moving her off the ghost wheels at the right of her row and finding an
  uncrowded seat, rather than falling back or emitting the crowd warning.

  **Portrait was already top-anchored** and comes out byte-identical: the travel
  axis is +y there, so the mark's start IS the top, and the new rule agrees with
  the ask instead of flipping it. So this is a landscape-only change, which is why
  `pixel_regress` reports 12,374px at 1440x900 and **0px at 390x844** — expected,
  not "not tested", and confirmed independently by measured plate rects.
  `?who=charles` is 0px at both because a solo page carries one chain,
  `datumRuns()` returns `[]`, and no plate is drawn — this change cannot reach
  that path.

  `npm test` 119/0 including *"a plate gives way to the metal, even when that
  costs more slide"*; `dom_invariants` 8 meshing pairs / 2 components / worst
  residual 0.0008px; `verify_motion` 40/40 advancing with 0 console errors;
  `devices.py` 24/24 and 4/4. Corner buttons re-measured since the plate moved
  toward them — 315px clear in landscape, and portrait's 5.3px is unchanged from
  before this ticket.

  One line in `tools/test.js`: the lifted `fitEscapes` ctx needed `_colRef`
  supplied unattached, the same dependency injection `_stageRef` already gets,
  since the harness has no DOM. No test was changed or weakened.

- **CL#157 — a timing mark only exists where there is metal, and an epicyclic
  is marked where a real one would be.** (GitHub #132, #133.)

  Charles, with a screenshot: *"timing mark lines added to plantary and grid
  centers adding lines that are drawn on top of empty space"* and *"timming
  marks missing from planets in single and dual planetary gearsets."* Two
  reports, one root cause: CL#154's mark spans `hubR * BOSS_MUL → wellR`, which
  is **exactly the web** — solid on a plain blank, and the one annulus every
  other family either cuts a pattern into or draws an assembly onto. The mark
  never consulted what the wheel's web actually contained.

  **Cut families now clip the mark to the body's own solid material**, reusing
  the `path + holes` evenodd clip the fill already builds, so it breaks at each
  opening and resumes on the next wall by itself. Note this is the *opposite*
  case to the cut contour's rule (CLAUDE.md: draw that one OUTSIDE the clipped
  group, since a stroke tracing a hole boundary loses its inner half) — that
  warning is about a stroke ON the boundary; this is one crossing the interior,
  where being cut off at the boundary is the whole intent.

  **Epicyclics get no mark on the blank at all, and marks on the sun and every
  planet instead.** Relocating rather than clipping, because on
  `planetary`/`ravigneaux` that span is where the ring, sun and planets are
  DRAWN, and because the blank is the one body in an epicyclic whose phase
  carries no information. Each planet's mark lives *inside* the group carrying
  its own `base` rotation, not the carrier's — what a fitter actually checks is
  each planet's phase against the carrier arm, and a mark riding the carrier
  would hold still relative to it and say nothing. So #133 was not a missing
  feature so much as the same mistake as #132 seen from the other side.

  Relocating the shape to three sites made it worth having one home:
  `timingMark(rIn, rOut, mod, col)` carries the proportions once (0.22 of a
  module of stroke, a 0.28 dot), the same argument `teethPath()`'s `chipSev`
  makes for a fracture. Planet and sun marks stop inside their own root circles
  via `TOOTH_DED`, derived rather than chosen.

  Verified by counting elements rather than trusting a screenshot of a
  deliberately subtle mark: with `?kind=` forcing each family, `planetary` gives
  35 marks = 7 × (1 sun + 4 planets) and **0** on the blanks, `ravigneaux` 49 =
  7 × (1 sun + 6 planets), and `isogrid`/`hexcore`/`spokes` one per wheel with
  **all 7 clipped**; `timing=false` gives 0 everywhere, so the layer gate still
  holds. Zero console errors in every case. `npm test` 119/0.

  Still default OFF, so none of this is live on the shipped page.

### Added

- **CL#156 — `/fidget/` fills the whole window instead of sharing it with a
  button bar and a readout row.** (GitHub #129, part 1 of 4.)

  Charles asked for "one gear on a page — like a fidget spinner." This is the
  layout half only: the stage used to be a flex row sized by whatever the
  chrome above and below it left over; now the stage is the full viewport and
  the buttons + readout are a floating overlay pinned to the bottom safe area,
  faded in on a gradient so text stays legible over whichever wheel sits
  underneath. Nothing below the `<body>` tag touches `SET_NODES`, `CENTRES`,
  the integrator, or any Willis-equation math — the drawing already scales to
  fill whatever box it's given (the SVG's own `viewBox` + default
  `xMidYMid-meet`), so shrinking the box was never the hard part.

  What #129 actually asked for beyond this — swiping to switch between two
  planetary *formats* (Charles: swap which member is grounded, ring vs sun) —
  is a new Willis derivation, not a layout change, and ships separately once
  that math is designed and its own `sunCheck` invariant is verified the way
  `ringCheck` is today.

- **CL#154 — three fidget-style layers ported to the landing page, each its
  own live checkbox.** (GitHub #125.)

  Charles picked items 1 (timing marks), 2 (line-drawn tooth profiles) and 3
  (rim ticks) from #125's own analysis — never item 4 (carriers, correctly
  excluded, the direct-mesh train has none) or item 5 (monochrome + accent,
  which the ticket itself flagged as replacing CL#140's per-chain palette
  system rather than extending it).

  **Timing marks** are one bold radial spoke per wheel with a punch-mark dot
  at its tip, rotating for free under the wheel's own existing transform (the
  one-clock rule costs nothing here, since it adds no clock of its own). A
  first pass reached out to the tooth root to escape the cluttered inner
  disc, and Charles caught the real problem with it on review: reaching that
  far crossed the engraving band's own radial span, and a scored index line
  on a real part would not run uninterrupted through a separately-machined
  rim feature, whether or not it visually crossed the lettering itself.
  Confined back to the well and made legible within it instead — a heavier
  stroke plus the punch-mark dot — which is what actually reads as a real
  machining mark rather than a longer one crossing something it should not
  have.

  **Line-drawn tooth profiles** turned out to be mostly already true — this
  page's teeth were never a plain filled silhouette, they already carry a
  stroke. What fidget's version actually has that this page's didn't is a
  *crisper* stroke: `toothStrokeW` scales the existing per-theme stroke
  width (already `1.6`/`1.1`) by a new `LINEWORK_STROKE_MUL`, gated behind
  `lineWork`, rather than adding a second overlapping stroke — tried once and
  discarded, since two strokes on the same edge read as smeared rather than
  crisper.

  **Knurled rim ticks** are a ring of `g.teeth` hatch marks — one per tooth
  rather than fidget's fixed 24, so density scales with the wheel rather than
  reading coarse on a big wheel and dense on a small one — sitting inside
  `faceR`, the one radius every wheel kind already guarantees is solid metal.
  Because that radius sits inside the engraving band by construction (`faceR`
  collapses to `bandIn` exactly when the band is reserved), the ticks have a
  *structural* guarantee of clearing the lettering, not merely an angular
  one like the timing mark's.

  **All three are independently gated** behind new `timing`/`lineWork`/
  `knurl` props (`data-props` schema, "Layers" section, `default:false` —
  the same pattern `character`/`engravedRims` already use) and **live
  checkboxes in Machine Settings**, added on Charles's own request so each
  could be judged by eye and toggled without a screenshot round-trip per
  change. `layerOn(key)` is the one home for "state overrides the schema
  default" — the same fallback `speedFactor()` already models for speed —
  read by both `gearSvg()` and the checkbox list's own `checked` binding.
  `a11y_audit.py` caught two real defects in the first checkbox pass before
  they shipped: a 15px hit box under the WCAG 2.5.8 floor every other control
  on this page holds to, and no accessible name reaching the input despite
  the visible label text beside it — both fixed (24px boxes, explicit
  `aria-label`), confirmed by a clean re-run.

  Built in parallel by two independent agents (line-drawn teeth; rim ticks)
  working the same file concurrently, reconciled by hand afterward — no
  collisions, confirmed by diff inspection and a full re-run of every gate
  against the combined result.

  `npm test` 119/0, `pixel_regress` 0px both scopes at every prop's default,
  `dom_invariants`/`verify_motion`/`pill_clip`/`a11y_audit.py` all green,
  live-click-tested (a real DOM `.click()` on the checkbox, not just a state
  assertion) to confirm the toggle actually re-renders.

  `devices.py` caught a real one too: three checkbox rows stacked in the
  Machine Settings panel pushed the last past the safe-area rectangle by
  12px on the shortest landscape phone profile (iPhone 13/14) — the panel's
  own `max-height`/`overflow-y:auto` (CL#114) keeps it visually clipped, but
  `getBoundingClientRect()` still reports a control's flow position
  regardless of scroll, and devices.py measures every real `<input>` on the
  page for exactly that reason. Fixed by tightening the rows' own padding
  (5px → 2px — the 24px checkbox itself is a WCAG floor and cannot shrink,
  so padding was the only slack); re-run confirmed 2px of clearance instead
  of −12px, with every other device profile unaffected.

- **CL#153 — Wear, a second slider beside Speed in Machine Settings.** (GitHub
  #112, closing GitHub #5.)

  Turns the fixed `SCUFF_SEV = 0.50` constant a design sweep chose before any
  control existed into a live 0-100% range, following through on Charles's
  own reasoning on #112: a control does not weaken CLAUDE.md's rule against
  drifting constants, it dissolves the problem the rule is about — the value
  stops being a hidden number with a story attached and becomes a declared
  default plus a live range anyone can move and see.

  **Marks exactly two wheels — the spine's own largest- and smallest-tooth
  linked wheels** — chosen once per solve by the new `wearWheels()`, memoized
  alongside `_solved` so which wheel is marked cannot change mid-drag. The
  largest tracks the slider directly; the smallest tracks it scaled by the
  new `WEAR_SCUFF_RATIO` (0.5) — the slider's top position reproduces the
  exact fixed pair that shipped before, every position below it scales that
  same pair down together, and **0 is today's shipped default exactly**:
  `character:false` has kept every fracture invisible since CL#16, and this
  changes nothing about that. `npm test`/`pixel_regress` confirm 0px/0-diff
  at Wear's default.

  **`teethPath()`'s existing `chipIdx` fracture geometry gained a `chipSev`
  parameter (0-1) rather than a second shape.** The authored fracture (fixed
  fractions 0.44 through 0.93 of the addendum, unchanged) is scaled by how
  far up the tooth it reaches, not redrawn — a light scuff is a shallow
  version of the same crack, never a different one. `chipSev` defaults to 1,
  so the pre-existing `character` debug flag (which chips every wheel
  uniformly, and still overrides Wear's selective two when both are on)
  renders byte-identically to before this change.

  **It is genuinely subtle, on purpose** — confirmed by an 8× crop, not by
  eye at normal scale, after an initial full-page screenshot looked
  unchanged and needed real debugging (not a rendering bug: `wearWheels()`
  had a real one, `g.person !== SPINE` compared a string against the whole
  person object CHAIN_TREE actually stores, always false — fixed to compare
  against `SPINE_SLUG`) to distinguish "not rendering" from "rendering, but a
  single fractured tooth among a dozen-plus identical ones is meant to
  reward a closer look," which is the literal ask on #5.

  Also documents the wear layer in CLAUDE.md, per #112's own "meanwhile" ask
  — nothing had ever said the fracture existed, that `character` gated it, or
  that it had been invisible since CL#16.

  `a11y_audit.py`/`devices.py` already select `input:not([type="hidden"])`
  rather than `button` alone (CL#114's speed-slider widening), so the new
  range input is covered with no gate changes. `tools/test.js`'s "exactly one
  range input" invariant is now "every range input carries its own
  `--thumb-color`" — still safe for the shared `::-webkit-slider-thumb`/
  `::-moz-range-thumb` rule with two controls, for a different reason than
  "there's only one." `npm test` 119/0.

### Fixed

- **CL#155 — Speed and Wear get visible labels, and their rows shrink to the
  Table of Gears' own rhythm without losing any touch-target area.** (GitHub
  #127.)

  Charles: *"the slider for speed is unlabeled and bigger than necessary -
  is there a reason it can't be sized more in coordination with the table of
  gears line items."* Both true: "Machine Settings" names the group, not
  either control, and a bare numeric readout with no word next to it reads
  as unlabelled to anyone not using a screen reader (the accessible name was
  always there via `aria-label` — this is purely the sighted half); and the
  row's rendered height was dictated by the `<input>`'s own 44px WCAG
  touch-target box, well above a Table of Gears row's ~27px.

  **The touch target does not shrink** — that would trade away real
  accessibility for density. What shrinks is how much of that 44px the ROW
  allocates in flow, via the exact hit-vs-visible split the corner buttons
  already use between their 44px box and their `var(--icon)` glyph: a
  `margin: calc((var(--trk) - var(--btn)) / 2) 0` on the input pulls it in
  to sit centred without changing its rendered size, so the row's own height
  now falls out of the label/readout line instead. Measured: 58px → 34px per
  row.

  **Two 44px hit boxes stacked in a shrunk row can mathematically overlap**
  once their row centres are closer together than `var(--btn)` — caught
  before it shipped, not after: `rowAntiOverlapGap` derives the exact margin
  needed between Speed and Wear specifically (the only two rows here with an
  oversized hit box to protect) from the same padding/gap figures the rows
  actually use, rather than a second guessed number that could drift out of
  step with them. Verified directly, not just measured on paper: Speed's
  input bottom edge and Wear's input top edge land at the identical
  coordinate — zero gap, zero overlap, confirmed with the three `#125`
  checkbox rows present too.

  `LIST_ROW_FONT`/`ROW_PAD_Y` are now the one home for the Table of Gears'
  own type/padding, read by both list styles instead of a second copy of
  `"600 13px/1.3 'Manrope',system-ui,sans-serif"`.

  Built in a worktree-isolated agent, reviewed and manually reconciled onto
  a `main` that had since gained the `#125` checkbox rows the agent's own
  baseline predated — no collisions. `npm test` 119/0, `a11y_audit.py`
  clean (0 targets under 24×24px, 0 unlabelled focusable elements, hit boxes
  still 129×44px), `devices.py` 24/24 and 4/4 (the safe-area clearance this
  session's `#125` checkboxes had narrowed to 2px on the tightest phone
  profile is back up to 8px, since three fewer pixels of row height per
  control adds up).

- **CL#152 — the datum plate clears the metal it is drawn near, and searches
  for a clean spot before giving up.** (GitHub #88, #109, #110 — CL#108
  re-landed against the current mesh/ghost/flywheel code, then taken further
  than CL#108 ever went.)

  CL#108 gave the plate two candidate seats — its natural side and the mirror
  — and picked whichever cleared the surrounding metal, or the less-bad of
  the two when neither did. It was reverted the same day: it deployed red,
  `verify_motion` reporting 20× React error #185 ("maximum update depth
  exceeded"), traced at the time to a suspected circular dependency between
  the plate's seat and the escape-ghost solve. **That cycle does not exist on
  current `main`** — the stage's own size is `solved.w * S` /
  `solved.h * S`, fixed before any ghost or datum geometry runs, so nothing
  the plate does can feed back into what `fitEscapes()` measures. Confirmed
  empirically, not just by inspection: `verify_motion` against the combined
  stage reports 0 console errors with the re-landed code in place.

  **Re-landing CL#108's own design surfaced a second, more specific problem.**
  It only ever evaluates two FIXED points along the run, one per side; when a
  wheel happens to sit on both of them — common for a short chain like
  Harper's, surrounded by much larger background ghosts — there is no third
  option, and the "less-bad of two bad choices" fallback drew a background
  tooth straight across the "Harper" label, into the last letter. Confirmed
  live: at one seed/viewport this shipped with a −21.7px overlap and no
  warning strong enough to say so.

  **The fix searches for a genuinely clean point along the run before ever
  falling back**, and it solves for that point exactly rather than sampling
  for it: because the plate's run direction and its normal are perpendicular
  unit vectors, a wheel's distance to the run's *own axis* never changes as
  the seat slides along it — only the distance along the run does. That
  collapses "which positions does this wheel block" from a 2D question to
  exact 1D interval algebra (`plateExcluded()`), and the nearest clean point
  outside every wheel's excluded interval is then a direct lookup
  (`plateNearestClean()`), not a stepped search. Verified across 8 seeds at
  1440×900: before this, 7 of 8 warned about a crowded seat, several with
  real overlap; after, 0 of 8 warn, and "Harper" now sits with visible air on
  both sides of the box.

  `metal` — every wheel the stage draws, linked and idler and ghost alike —
  is built once per render and threaded through `datumLayer()` into
  `plateSeat()`, the same shape CL#108 used. A still-crowded seat (nothing
  clears anywhere in the window) still warns once per chain to the console
  rather than being hidden, the same rule a crossing bridge or overlapping
  chains already answer to.

  `tools/test.js` extracts `plateSeat`/`plateAir`/`plateExcluded`/
  `plateNearestClean`/`datumLayer` the same way it already extracted
  `plateMetrics`/`plateMargin` — a lifted function calling a method the
  harness never gave it throws, which is what caught every signature change
  here before a screenshot did. A new test asserts the metal-clearance rule
  directly (a plate gives way to a crowded side even at zero slide cost, a
  plate crowded on *both* sides still warns and reports itself uncrowded,
  and a clean plate stays silent) — mutation-tested by reverting the
  side-selection comparator to slide-only and confirming the new test catches
  it by name. `npm test` 119/0. `pixel_regress` 0px at the suite's default
  seed (expected — CLAUDE.md's own warning about 0px meaning "not tested"
  applies here: the default seed does not happen to crowd anyone's plate),
  confirmed instead at the seed that does (14,978px, matching exactly what
  moved). `dom_invariants`, `verify_motion`, `pill_clip`, `escape_mesh.py` all
  green and unaffected.

- **CL#151 — the favicon is a "w" in the page's own font, not a generic blue
  dot, and `/favicon.ico` is a real file instead of a 403.** (GitHub #119.)

  Three findings, all fixed together: the placeholder two-circle blue dot
  (`#3B7DE8`, a colour belonging to no palette on the page) is replaced by a
  single "w" in Manrope ExtraBold; `/favicon.ico` — requested unconditionally
  by every browser before any `<link rel="icon">` is honoured — now returns
  200 instead of 403 (the exact #74 failure shape, one file later); and
  CLAUDE.md's own claim that the 403 was actually a benign 404 is corrected.

  **Theme-aware, via two `<link rel="icon" media="(prefers-color-scheme: ...)">`
  tags** rather than one static icon — each an inline SVG in the matching
  theme's real `--bg`/`--ink`. This can only ever track the system/browser
  colour scheme, never the page's own manual toggle (a media query has no way
  to read `data-theme`) — stated plainly in both the markup comment and
  CLAUDE.md, not chased as a bug.

  **The glyph is the real Manrope, not a substitute.** A `data:` favicon
  cannot load a webfont, so the "w" outline was extracted once from the
  actual Manrope ExtraBold TTF with `fontTools` and baked into a static SVG
  path; `favicon.ico` (three embedded sizes, 16/32/48) is a `Pillow`-rendered
  raster of the same glyph. Three independent artifacts — the two SVGs and
  the ICO — none of which re-read `index.html`'s own `font-family`
  declaration, worth remembering if the page's font ever changes.

  `favicon.ico` joins the publish whitelist and CLAUDE.md's published-files
  list; the deploy's liveness check asserts it's reachable and served as
  `image/x-icon`. `npm test` 118/0, `pixel_regress` 0px (a `<link>` tag is
  invisible to the render), 0 console errors.

- **CL#150 — unnamed constants sweep (GitHub #103).** Five entries, all
  `index.html` unless noted:

  - **`colH` deleted.** Assigned from a DOM `offsetHeight` read (forcing
    layout) inside `fitStage()`, and never read by anything.
  - **`boost`'s cache invalidation is now guarded on `TRAIN_HAS_LINKED`.** It
    is the spread multiplier for the dormant chain-and-belt capability, read
    only in the `linked` branch no shipped `TRAIN` entry takes — so comparing
    it unconditionally threw the whole solve away and rebuilt it on every
    resize that crossed one of its ~6 quantised thresholds, for a variable
    with no effect on this train. `TRAIN_HAS_LINKED` is computed once, off
    the same `TRAIN` a revived `link: 'chain'`/`link: 'belt'` entry would
    already be part of — the moment one exists, this line starts
    invalidating on `boost` again, with nothing else to remember.
  - **Named:** `BOOST_REF_PX`/`TIGHT_REF_PX` (fitStage's two reference
    viewport widths — chosen, not derived, no record of why they're 8%
    apart); `ESCAPE_SEARCH_ARC` (the arc `fitEscapes` searches either side of
    a run's axis); `ESCAPE_CROSS_EXT_PX`/`ESCAPE_MIN_REACH_PX` (both screen
    px); `ESCAPE_RUN_MARGIN` (solve units — the unit split matters: this one
    is added to `span` *after* `span = e.reach / gs` has already converted
    screen px into solve units, so an unlabelled `120` on either side of that
    line would look identical and mean different things); `POLARBRICK_ASPECT_MAX`
    (the one unexplained figure in an otherwise fully-derived family — chosen,
    not derived, no record of why 1.9).
  - **`tools/test.js`** updated to hand all four new `fitEscapes` constants
    into `fitEscapesOn()` the same way `ESCAPE_WOBBLE` already was —
    `ESCAPE_SEARCH_ARC` is an array, so it's grabbed as the real declaration
    (`grabDecl`) rather than through `grabNumber()`, same as `STEP_DRIFT_MAX`/
    `BAND_MAX`.

  Deliberately not touched: `spiral`'s `spW` — the ticket's own read is that
  it's retired code (the `else` fallback, `CENTRE_FAMILIES` entry commented
  out), same as `honeycomb`/`iris`/`labyrinth`, worth leaving alone rather
  than tuning a renderer nothing deals.

  `npm test` 118/0, `pixel_regress` 0px on both scopes (plus forced on
  `?kind=polarbrick`, the one family whose rendering math changed a variable
  name), `tools/escape_mesh.py` unchanged (17/17 meshes, same residuals).

- **CL#149 — `hubR * 1.5` gets one home: `BOSS_MUL`.** (GitHub #95.)

  Ten boss circles and three pattern-start clearances (`spokes`, `sunburst`'s
  `rInR`, and one more) all wrote the same fact — "where the boss disc's edge
  sits" — as the same bare literal. The `hexcore` comment already stated why
  that matters: a lattice that cleared less than the boss ran its innermost
  ring underneath the boss's own fill. Ten call sites move with a single edit
  now; three clearance sites no longer can silently stop agreeing with them.

  `tools/test.js` read two of those thirteen sites by exact string/regex
  match on the literal `1.5`, so the rename would have broken its own
  extraction rather than the page — fixed to resolve `BOSS_MUL` from
  `index.html` the same way it already reads every other page constant,
  rather than either hardcoding the new name or leaving the old literal in
  place to keep the harness quiet.

  Deliberately untouched: `1.55`/`1.6`/`1.32`/`1.3`/`1.35`, which are each
  family's own choice to clear the boss by a further margin, not instances of
  this fact. `npm test` 118/0, `pixel_regress` 0px on both scopes — a pure
  rename has no visible effect by construction.

- **CL#148 — `tools/escape_mesh.py` (GitHub #117) is now wired into CI, not
  just written.** The harness itself already existed and already passed — 4
  runs, 17 ghosts, 17 meshes measured, worst residual 0.0144px of a 0.35px
  tolerance across 4 seeds and both orientations — but nothing in
  `deploy.yml` ever ran it, so a real regression in escape-run meshing could
  ship with every other gate green. Added alongside `dom_invariants` in the
  same gated step. Closed #117 on this plus CL#147: the specific "this
  configuration doesn't look possible" screenshot is very likely CL#147's bug
  — a ghost rotating off the wrong flywheel reads as an impossible mesh on a
  still frame even though its static geometry (what this gate measures) was
  correct the whole time.

- **CL#147 — a self-driven chain's escape ghosts were driven by the SPINE's
  flywheel, not their own.** (GitHub #122 follow-up. Charles: *"if one pulls
  on my chain it moves all the gears on my chain and all the ghost gears on
  harper's chain excluding the 2 before and after the link gear."*)

  CL#142 gave every mesh its own flywheel (`_M[comp]`) and tagged every wheel
  with the component it belongs to — but only wheels that pass through
  `solve()`'s union-find get tagged. Escape-run ghosts are decoration
  computed afterward, in `fitEscapes()`, entirely outside `g`: they never
  reach line ~6137, so `.comp` was always `undefined` on every escape ghost
  on the page, and `applyRotation()`'s `x.g.comp != null ? x.g.comp : 0`
  fallback silently drove all of them off **component 0** — the spine's.

  That is exactly why the two idlers nearest the mesh point were unaffected
  and everything past them was not: those two are harper's own **origin-run**
  idlers, structural `TRAIN` entries solved into `g` like any real gear and
  correctly comp-tagged there. Her escape run, trailing off the far end, is
  pure decoration with no such tag, so it rode Charles's angle instead of
  hers — not just moving when a self-driven chain's ghosts should have sat
  still, but rotating at the wrong rate entirely, which is what broke the
  tooth-sync illusion between a ghost and the real wheel it is drawn meshing
  against.

  **The fix is one field.** `host.g` — the solved gear (`c.head`/`c.tail`/the
  origin-run tip) an escape run grows from — is already comp-tagged by
  `solve()` before `fitEscapes()` ever runs. Every ghost grown from it now
  carries `comp: host.g.comp`, the same pattern already used for `hostCx`/
  `hostCy` a few lines above, for the same reason: a run's identity is only
  ever recoverable from its host.

  **Verified by reaching into the live React instance rather than by eye.**
  A one-off harness (not shipped — see `scratchpad/`) walks the stage's fiber
  tree to the component instance, reads `_solved.gears` and `_ghostEls`
  directly, holds `wozi-motion` at `rest` so idle animation cannot confound
  the reading, and drags a real wheel on Charles's chain with a real pointer
  sequence (press, wait for frames, tangential move, release — the #78/#92
  class of gesture this repo's other drag harnesses already insist on).
  Before the fix: all 12 of harper's escape ghosts carried `comp: null` and
  all 12 moved. After: all 12 carry `comp: 1`, matching her own linked wheel,
  and none moved. `npm test` 118/0, `dom_invariants` both scopes,
  `verify_motion`, `pill_clip` all green; `pixel_regress` 0px both scopes —
  expected, since nothing about a resting frame changes when only the
  *ownership* of a flywheel is corrected.

- **CL#146 — `/fidget` redirects to `/fidget/` instead of 403ing.**

  The origin is the S3 REST endpoint behind an OAI, not the S3 website
  endpoint, so S3's own `IndexDocument` rule never runs and CloudFront's
  `DefaultRootObject` only covers `/` — a request for the bare directory path
  reached S3 directly and got its raw `AccessDenied` XML back at 403. Same
  failure shape as #74, one directory later, and CL#145 shipped the page
  without anyone having typed the URL without its slash.

  The fix is not in this repo in the usual sense. `wozi-viewer-request`, the
  CloudFront Function already doing the www→apex redirect and the directory-
  index rewrite that makes `/fidget/` itself work, now also slashes any path
  in a new `DIRS` list (currently `['fidget']`) before either of those run —
  so `www.wozi.com/fidget` takes one hop, not two, and `charles.wozi.com/fidget`
  redirects to `charles.wozi.com/fidget/`, never to the apex.

  **`DIRS` is a named list, not "any extensionless path gets a slash."**
  `ssh_public_key` is a root object published deliberately without an
  extension; an extensionless rule would 301 it into `/ssh_public_key/` and
  break it. Same whitelist reasoning as the deploy step in
  `.github/workflows/deploy.yml` — a directory not added here fails as a 403,
  not as a broken published object.

  The function's source is now versioned at
  `infra/cloudfront-viewer-request.js` — see CLAUDE.md, "What the distribution
  does before S3 sees the request," for why that file is documentation and not
  what CI deploys, and why nothing before this entry ever said CloudFront ran
  code at all. `deploy.yml`'s liveness check gained `check_redirect`, asserting
  both the status and the `Location`, and used it for both `/fidget` and the
  pre-existing bare www check, which previously asserted only the status code.

  Verified against AWS's own `test-function` API returning a genuine
  `ServiceUnavailable` 503 (confirmed via `--debug`, not a malformed event) —
  pre-publish verification fell back to running the function body directly
  under Node against eight scenarios (host × path combinations covering the
  slash, the redirect, the exclusion, and the per-host preservation) before
  publishing DEVELOPMENT to LIVE. Confirmed live afterward with `curl`.

- **CL#144 — the pop-out menu is a control surface, and the person picker is
  gone.** (GitHub #118.)

  Charles's call, put to him with the cost attached and taken with it in view.

  The panel now carries two labelled groups — **MACHINE SETTINGS** over the speed
  slider, **TABLE OF GEARS** over the family list — where before the slider sat
  under nothing and the household sat between the two. It is 55px shorter.

  **What is lost, stated plainly:** per-person pages are reachable only by
  subdomain or `?who=<slug>` now, and neither is discoverable by anyone who has
  not been told. The picker was the only signpost.

  `togPeople` survives as an empty list rather than being deleted. `togSep` reads
  its length to decide whether the gear entries need a rule above them, and the
  template renders one tag per entry — an empty list is the honest way to say
  "nothing here" without unpicking separator logic the new heading now relies on.

  **The test that guarded the old rule now guards the new one.** It asserted the
  picker drew only on the combined stage — the disclosure guard from #68. That
  disclosure is now impossible rather than conditional, which is the stronger
  guarantee, so the assertion became "it stays impossible": `togPeople` must
  remain an empty list, the slider must still be in the panel, and the heading
  must still name the group. Confirmed to fail on both regressions — repopulating
  the list, and removing the heading.

  Read against `STRIPPED_SRC` rather than `SRC`, because the comment above the
  declaration explains what the picker was and quotes its old shape; checking raw
  source would match the suite's own prose, which is the #101 trap.

  **Not done here, and still open on #118:** the wear control. `fix/118-machine-
  settings` carries a wip implementation (CL#128/CL#129, "service hours") from
  two killed agents, based before CL#132 — 677 lines of `index.html` against a
  base that predates the flywheel, ghost-palette and `MIN_CUT` rewrites. It is
  worth salvaging deliberately rather than rebasing blind, and #112 is where that
  belongs.

### Added

- **CL#145 — `/fidget` ships.** (GitHub #123. Charles: *"ship fidget"*.)

  One line in the deploy's publish whitelist is the whole of it — CLAUDE.md's
  own rule that adding a file does not publish it had been holding the page
  back since it was built, which is exactly its job.

  `fidget/index.html` joins the HTML publish loop. `fidget/README.md` does
  not: it records the tooth counts, inertias and loss coefficients and why
  they were chosen, which is repo documentation and not something the web
  needs.

  The liveness check is a substring rather than the `exact()` byte-identity
  used for `keybase.html`. Deliberate: `/fidget` carries no sensitive data and
  no signature, so byte-identity buys nothing, and what actually matters is
  that the page arrives and is the fidget rather than a redirect or an error
  body.

  Not published, and staying that way: `legacy/`, every root `.md`, and the
  tools.

### Fixed

- **CL#143 — `cards/` is removed entirely.**

  Charles: *"nah - blow away /cards"*, after noting *"I actually think that I had
  /cards before I realized I could create a vcf inside a QR Code itself"* — a
  vCard fits inside the QR payload, so a hosted page was never needed for new
  cards.

  **Stated once, because it is the cost:** #84 recorded that printed cards are in
  circulation and concluded the path had to stay for them. Removing it means
  those QR codes stop resolving. Charles made the call with that in front of him.

  Gone from the repo: `cards/index.html`, `cards/charles/index.html`,
  `cards/charles/contact.vcf`, `cards/images/icon.png`, `cards/styles/qrserve.css`.

  Gone from `deploy.yml`: the two card pages from the HTML publish loop, the
  whole "Publish card assets" step, the `check https://wozi.com/cards/` liveness
  assertion, and both `exact` byte-identity assertions.

  **The `exact()` helper is kept**, and the comment above it rewritten. It was
  introduced for `cards/` under #54, but `keybase.html` needs it for an unrelated
  reason — its body is signature-covered, so a truncated response still returns
  200 while the ownership proof silently stops verifying, and a substring check
  cannot tell those apart.

  **The reason this repo is private has changed, and CLAUDE.md now says so.** It
  went private because `cards/` published a real address and mobile number; that
  no longer applies to the working tree. What still argues against publishing is
  **history** — the vCard blob and the street address remain reachable in the
  object graph of every past commit, gone from HEAD but not from the repository —
  plus `legacy/resume-2014.pdf`, which is uncleared because `pdftotext` was
  unavailable and `strings` under-reports on a compressed PDF.

  The `robots.txt` section kept its reasoning and lost its example: the argument
  that a `Disallow` is worse than a `noindex`, and that naming a path in a
  world-readable file advertises it, applies to whatever is added next.

  **The live objects are not touched by this.** The deploy does not pass
  `--delete`, so `s3://wozi.com/cards/*` continues to serve until removed by
  hand. That is deliberate — it separates a reversible repo change from an
  irreversible outward-facing one.

- **CL#142 — one clock, several angles: chains that share no gearing no longer
  share a flywheel.** (GitHub #122.)

  Charles: *"when I have two chains if I grab one chain/stop/etc the other chain
  also responds — even though as far as anyone can see they should be two
  entirely independent chains."*

  The shared root was `_M`. Every wheel's transform came off one master angle, so
  every input that could reach it — drag, arrow keys, the speed control — moved
  the whole stage. The config already disagreed: a self-driven root is a separate
  mesh, CLAUDE.md says it always will be, and `dom_invariants` has been reporting
  **2 components** all along. The geometry knew; the animation did not.

  **Components are derived exactly as the gate derives them** — union-find over
  pairs whose centre distance equals the sum of their pitch radii. Deriving it any
  other way would let the page and its own gate disagree about what "connected"
  means, which is the #67 class of fault. Ghost idlers are included deliberately,
  because a bridge run is precisely what makes two chains ONE machine: a chain
  reached by a bridge shares its parent's flywheel, and only a chain nothing on
  stage drives gets its own. A refused bridge therefore separates a component by
  itself, with no extra bookkeeping.

  **"One clock" is preserved, and this is what it actually meant.** There is still
  one `requestAnimationFrame` loop and one `dt`. The invariant is about wheels
  that MESH — they must share a clock or their teeth diverge (#3). Two chains that
  share no gearing do not mesh, so they never had to share an angle, and giving
  them one is what produced the bug.

  **Per-chain momentum, not per-chain state** (Charles's call). Each mesh gets its
  own angle and velocity, so a throw or a held hand reaches only the chain under
  it. The motion toggle and the speed control stay global — the speed control
  still reaches exactly one thing, which the alternative would have broken.

  Two things went wrong in the making, both worth recording:

  - `_dragging` gated the ENTIRE integrator, so a hand on any wheel froze the
    page. That is the substance of the fix: the dragged component is skipped, not
    the loop.
  - `_M[undefined]` is `undefined`, and `|| 0` turns that into **angle zero**
    rather than "no change". Ghost outriggers and epicyclic internals are built
    from objects that predate the tagging, so 38 of the 41 rotating bodies pinned
    to zero and the page looked frozen when only the trim was. Every read now
    falls back to component 0 — the spine's — rather than to an angle.

  Verified by holding one chain for 1.2s under a real pointer press: **38 rotating
  bodies held still, 3 kept turning**. `pixel_regress` is 0px on a solo chain,
  which is the right answer — one chain is one component and nothing changes.

- **CL#141 — the coast is a declutched flywheel, not a braked one.** (GitHub
  #121, third pass.)

  Charles, after CL#139: *"it still feels like grabbing and spinning the gears
  there is an artificial break on the gears — I want it so you have SOME gradual
  slowdown — but more like if you walked up to the gears on the table with a
  clutch so you could spin them freely, that if you grabbed a gear chain and spun
  it you could get a gratifying spin that ended up slowly and naturally returning
  back to the same speed, but in whatever direction you spin the chain."*

  **CL#139 fixed the shape and still had the balance wrong.** It leaned on
  windage at 0.60, and the square term bites hardest exactly where a thrown wheel
  is FASTEST — so a hard spin dumped most of its speed inside the first second
  and the gratifying part of the throw was gone before it started. Low windage
  and a wide dynamic range is the opposite trade: little drag at speed, falling
  steeply as the wheel slows.

  Four candidates were staged as servable pages and spun by hand on the real
  page rather than judged from a plot. Charles picked C.

  | | range | drag range | windage | real throw | ladder |
  | --- | --- | --- | --- | --- | --- |
  | A (CL#139) | 2400 | 15 | 0.60 | 2.1s | 2.4s |
  | B | 8000 | 30 | 0.20 | 7.1s | 8.0s |
  | D | 11000 | 40 | 0.15 | 9.9s | 11.0s |
  | **C — shipped** | **15000** | **60** | **0.10** | **13.6s** | **15.0s** |

  A real hand throw was measured at `_v` 40–52 this session, so the "real throw"
  column is taken at 45 rather than at the saturating value.

  **How physical is it, honestly?** The character is: drag that falls steeply
  with speed, a long tail, a definite stop. The magnitude is a design choice — a
  cast-iron flywheel on good bearings coasts for minutes, not seconds. What makes
  13.6s defensible is that this is a geared TRAIN, not a bare flywheel, and every
  mesh adds friction; a multi-gear train damps out far faster than a single
  wheel.

  Direction already behaved as asked and is unchanged: `up()` flips `_dirSign`
  when the drag moved more than 30 master-degrees, so the train settles back to
  its normal pace in whichever direction it was spun.

  **Two test bounds were derived rather than widened.** The shape test's tick
  budget was a fixed 400, which is 13.3s at 30Hz — it ran out before a 15s coast
  arrived and reported a lost Coulomb term, a statement about the budget and not
  about the model; it now comes off `SPINDOWN_RANGE_MS`. CL#136's identity
  tolerance was `dt * 2`, i.e. 1ms: fine as 0.04% of 2400ms, far tighter than the
  integration itself at 15000ms. Now 0.1% or two ticks, whichever is larger. Both
  guards were re-confirmed to fire at each end — a drag range of 1.0001 trips the
  brake assertion, 200000 trips the arrival one.

- **CL#140 — the two themes' ghost palettes are reflections of each other.**

  Charles: *"in light mode the gears stick out as they are dark on a light
  background"*, and then the question that produced the actual design: *"why is
  it that the colour palette for light mode ghost gears isn't the reverse of what
  dark mode is?"*

  **There was no reason.** `GHOST_COLORS` is ONE list of greys, and each theme
  applied its own ad-hoc factor — 0.78 toward black in dark, 0.55 in light —
  tuned independently, neither derived from the other. In CIE L\*, dark ghosts sit
  **+7.99 above** their page while light ghosts sat **−22.21 below** theirs: 2.8×
  further out. That is the complaint, measured.

  The rule is now one line: **a ghost sits the same distance from its page in
  both themes, on the side that page allows** — above a dark ground, below a pale
  one. `GHOST_OFFSET_L` is read off the shipped dark treatment, so dark stays the
  reference and light is its reflection; nothing is hand-picked, and a change to
  `GHOST_COLORS`, to either ground, or to the dark factor re-derives.

  | | offset from page | spread |
  | --- | --- | --- |
  | dark, unchanged | **+7.99** | 2.03 |
  | light, before | −22.21 | 3.17 |
  | light, first attempt (APCA match) | −2.57 | 1.53 |
  | light, shipped (L\* mirror) | **−7.98** | 1.99 |

  **The first attempt matched APCA and was wrong, which is worth recording.**
  Matching perceptual contrast sounds stricter, but APCA is polarity-weighted, so
  equal Lc does *not* put the two themes at equal distance — light landed at a
  third of dark's offset, over-correcting. Worse, it compressed the four greys
  toward the page and took their spread with them (2.03 → 1.53), so they stopped
  being four tones and became a wash. Charles: *"that looks odd to me."* The
  mirror preserves the spread because it moves each grey by the same rule rather
  than collapsing them onto a point.

  **Why the colour and not the layer alpha, also tried first.** Lowering
  `ghostOpacity()` is identical arithmetic for a wheel and *not* identical for the
  datum, which is drawn INSIDE that group (#81) so the layer is a ceiling on it.
  At the matching alpha `datumInk()`'s lift ran past black, clamped 12 units
  short, and the dark scribe solved to no harder than a ghost wheel — the weight
  the mock proves it disappears at. **Colour touches the wheels; alpha touches
  everything in the layer.**

  `--ref-bg-dark` joins `--ref-bg` in `:root`, deliberately not overridden, so
  both grounds are readable from either theme — the mirror reads one against the
  other, and a value that only exists while its own theme is active cannot be
  reflected. The dark block points `--bg` at it, the shape light has always had.
  `tools/test.js`'s `cssVar()` learned to resolve one `var()` indirection as a
  result: it reads the CSS as text, and without that it reported *"datumInk did
  not return a colour for --muted from a palette that declares it"* — true about
  the test, false about the page.

- **CL#139 — the flywheel coasts instead of braking: drag falls as it slows.**
  (GitHub #121 follow-up.)

  Charles, on the shipped constant-deceleration model once CL#136 let a throw
  show the whole of it: *"the spindown speed is just weird now — almost as if
  there is a break on the wheel"*.

  **That reading is exactly right, and it is about the MODEL, not the tuning.** A
  constant retarding torque is literally what a friction brake applies. Pure
  Coulomb friction sheds speed at the same rate at 200× as at 1.1×, so the wheel
  ramps down a straight line and then stops decelerating at a corner. Nothing
  coasts like that — a flywheel free on its bearings loses most of its drag AS IT
  SLOWS, so it drops away quickly and then trails off.

  CL#136 did not cause this, it revealed it: while `driveCap()` was 8 a throw only
  ever showed the first 269ms of that straight line.

  **The model is the standard three-term coast-down an engineer fits to a real
  rotor** — `decel = Coulomb + viscous·e + windage·e²`, on the gap between the
  wheel and the speed it is driven at. Windage is air drag on a disc, dominates
  at speed, and is what gives a hard throw its initial dive. Coulomb is the
  residue that makes it ARRIVE in finite time, which is CL#127's win over the old
  fixed-tau exponential and is kept deliberately.

  **Both previous models were wrong at opposite ends of one axis.**
  `SPINDOWN_DRAG_RANGE` is how much harder it brakes at the ladder's top than at
  rest, and the two failures sit at its ends: at **1** the terms collapse to a
  constant and it is CL#127's brake; **very large** kills the Coulomb residue and
  it is #106's pure exponential, which never arrives and stops depending on how
  hard you threw it. Measured — a windage-only fit makes a 2× throw take 1200ms
  against a full-ladder 2400ms, so the throw stops reporting its own strength.

  **15 is a compromise, not a physical constant.** A real flywheel's range is far
  higher (windage at 200× against bearing Coulomb at rest is easily 100×), but
  past about 30 the small throws read as sluggish. Realism and #106 pull against
  each other; this is where they were balanced, and it is the knob to turn.

  Measured on the real page through a real pointer gesture — note the new model
  coasts LONGER from a WEAKER throw, which is the shape changing rather than the
  duration being turned up:

  | | hard throw | gentle throw |
  | --- | --- | --- |
  | CL#136 (brake) | 1715ms at `_v` −49.4 | 182ms |
  | this change | **2015ms** at `_v` −40.8 | **465ms** |

  **Only the scale is solved; the shape is chosen.** The two shape figures set
  the split and the overall scale is bisected at load (Simpson over 1/decel —
  the closed form loses precision as the windage share goes to zero and threw a
  domain error when tried) so that a full-ladder transition still takes exactly
  `SPINDOWN_RANGE_MS`. That keeps CL#136's identity true: a saturating throw is
  the ladder travelled by hand, so it must take the ladder's own time.

  **The test that asserted the opposite is reversed, not deleted**, and now
  guards both ends: the rate must fall by more than 3× across the descent (not a
  brake) AND arrival must stay exact (not an exponential). Confirmed to fail at
  each end — a drag range of 1.0001 trips the flatness assertion, and 100000
  trips three tests including #106's own core complaint.

  **`pixel_regress` cannot be 0px for a change to this function, ever**, because
  `_M` is the integral of `_v` and a different spin-up curve permanently offsets
  phase. 48,551 / 48,590 / 48,788 px at 90 / 900 / 3000 frames — stable rather
  than growing, which is what separates a phase offset from a structural break.
  Structure is held by `dom_invariants` and `verify_motion`, both green.

- **CL#138 — `hexcore` and `labyrinth` are held to `MIN_CUT` too, each by its
  own geometry.** (Follows CL#137.)

  Charles: *"let's hold hexcore and labyrinth to the floor too — how do we
  calculate that"*.

  **The conversion is the whole calculation, and it is different per family.**
  `MIN_CUT` floors the opening's NARROWEST dimension, so each family needs its
  own map from its size parameter to that width:

  | family | parameter | narrow dimension | floor |
  | --- | --- | --- | --- |
  | isogrid, polariso | lattice pitch | pitch less a wall each side | `MIN_CUT + 1.732 * WALL` |
  | hexcore | `cellX`, the CIRCUMRADIUS | across the FLATS = `sqrt(3) * cellX` | `MIN_CUT / sqrt(3)` |
  | labyrinth | `wL`, radial slot width | already the narrow one | `MIN_CUT` |

  hexcore is not isogrid's case: its wall is ADDITIVE in `step`
  (`cellX + WALLX / sqrt(3)`), so it sits between cells and takes nothing off the
  opening — `cellX` is pure cut, and the only correction needed is flats rather
  than vertices. The gap this closes, measured: the old floor allowed **6.8px
  across the flats at every viewport against a 10.3px requirement, 34% under**,
  which is the "reads as dots" complaint as a number.

  labyrinth's cap of 6 solve units was below `MIN_CUT` at every viewport, so
  every slot it ever cut was under the floor by construction.

  **The floor had to become an AIM for hexcore, not a gate.** Its rings are
  anchored at the wheel centre, so ring radii land on fixed multiples of the
  pitch and a ring is wholly in or wholly out — cells do not degrade gracefully,
  they stop fitting. Applied as a hard floor it emptied **1 of 7 wheels on a desk
  and 3 of 7 on a phone**, measured by `scratchpad/hexcore_census.py`, which
  counts cut paths off the rendered DOM across four seeds and four viewports. The
  sweep now retries at hexcore's own legibility floor, which bounds the fallback
  at what already shipped: never a smaller cell than before, never a web that used
  to be full and is now empty. Final census: **no blank web introduced anywhere**.

  **A separate bug the census exposed, and the more interesting one.** The sweep
  was `for (c = ceiling; c >= floor; c -= 0.05)`, which anchors the tested sizes
  to where it STARTS — so moving the ceiling silently tests a different set, and
  the floor itself is sampled only when the span happens to be a whole number of
  steps. A 13-tooth wheel went blank at one viewport and not at a neighbouring
  one with IDENTICAL `rIn`/`rOut`, because the only feasible size sat just under
  the last grid point that ceiling produced. Counting down from the floor makes
  the tested set independent of the ceiling and always samples the floor exactly.
  This was latent before this change and would have surfaced on any ceiling edit.

  **`CELL_MAX` had to move with the floor or invert it.** A flat 4.8 solve units
  sat above the old floor on a desk (2.79) and BELOW the new one on a phone in
  landscape (7.06), and a ceiling under the floor collapses the sweep to one
  iteration. It is now `CELL_MIN * 1.7` — and 1.7 is the one judged figure here,
  taken from the ratio the shipped pair expressed at desktop (4.8 / 2.79), since
  how much range the search gets is not a property of the geometry.

  **`LATTICE_WALL`** is added as the one home for the wall between openings: the
  same expression was written out four times.

  **labyrinth is corrected but unphotographed, and that is not an oversight.** It
  is retired — no `CENTRE_FAMILIES` entry, and `?kind=labyrinth` silently returns
  an ordinary mix rather than erroring — so there is no picture to check a chosen
  figure against. It is therefore bounded by its own row pitch (widen past that
  and neighbouring rows merge) and drops a row when the floor will not fit, rather
  than by any number picked by eye.

- **CL#137 — `MIN_CUT` is stated in pixels, and set from the family that works
  rather than the one that was complained about.** (Follows CL#133.)

  Two faults in one constant, found while checking CL#133's claim that a lattice
  floors its pitch from `MIN_CUT`.

  **The units were wrong.** `MIN_CUT = 5.6` was in solve units, and whether a cut
  reads is a question about what reaches the eye. `--gsfit` measures 1.396 at
  1440x900, 0.842 on a phone in landscape and 1.461 at 5K, so one solve-unit
  floor is a 1.7x spread in what it actually asks for: 7.8px on the desk, 4.7px
  on a phone. That is exactly the trap the hexcore wall floor fell into and that
  `px()` was written for — this constant was simply never converted. It is now
  `MIN_CUT_PX = 10.3`, converted per render.

  **The figure was wrong too, and taken from the wrong witness.** 5.6 came from
  hexcore, a family Charles had already complained about. The family that reads
  at every colour is sunburst, and across four seeds and every wheel it never
  cuts below 7.41 solve units — measured on the desk, where S is 1.396, so
  10.3px is the requirement the working family actually meets.

  A phone therefore asks for MORE solve units to make the same 10.3px, and cuts
  fewer, larger openings. That is the intent, not a side effect: fine detail is
  precisely what a small screen cannot show.

  `MIN_CUT_LO`/`MIN_CUT_HI` (7.0 and 12.5 units) are rails, not the mechanism —
  over the real range of `--gsfit` the conversion lands between 7.05 and 12.23,
  so neither binds today.

  **What this does NOT fix.** `hexcore` and `labyrinth` have their own sizing and
  are still not held to the floor, so hexcore reading as round cells rather than
  hexagons is untouched and open. The hexcore row on the comparison sheet does
  move, and that is the deal shifting rather than the floor acting: changing the
  cell count changes RNG consumption, so a before/after pair is not guaranteed to
  be the same tooth count or colour. Sheet: `scratchpad/mincut_sheet.py`.

- **CL#136 — a thrown wheel coasts for as long as the throw deserves, because
  the ceiling on a throw is now the machine's, not a remembered 8.**
  (GitHub #121.)

  Charles: *"when one manually grabs and throws the wheel recent updates have
  prevented the free flowing return to normal — one used to be able to throw the
  gear chain and have it coast back to normal now it artificially holds."*

  **The recent update was CL#127, and it did not have a bug in it.** It replaced
  a fixed-tau exponential with constant deceleration, which is what GitHub #106
  asked for and is the right model for a heavy wheel under Coulomb friction.
  What changed underneath it is what `driveCap()` MEANS. Under an exponential,
  settling time is independent of the size of the drop, so the cap bounded how
  FAST a throw could go and nothing else. Under constant deceleration the coast
  is exactly `(driveCap() - idleRate()) / SPINDOWN_DECEL` — so the cap silently
  became the only thing deciding how LONG a throw could run.

  `driveCap()` was `max(8, idleRate())`. At 1× that is 8, and 8 → 0.343 at the
  shipped deceleration is **269ms**. Not 269ms for a gentle throw — 269ms for
  the hardest throw physically expressible, because every throw was clamped to
  the same ceiling. That is the whole complaint.

  **Measured, on the real page, through a real gesture.** A CDP pointer drag
  through the actual `pointerdown`/`pointermove`/`pointerup` path, with `_v`
  logged per tick from a staged copy under `scratchpad/` (the hook never reaches
  the repo, let alone the bucket):

  | | saturating throw | gentle throw |
  | --- | --- | --- |
  | before CL#127 (fixed 900ms τ) | 2115ms to 90% | 2115ms to 90% |
  | shipped | **283ms** | 164ms |
  | this change | **1848ms** | 199ms |

  Note the first row: under the old lag a gentle throw and a violent one took
  the *same* time to settle, which is the #106 defect seen from the other side.
  Effort buying nothing is why it needed replacing; effort buying nothing but
  capped at a quarter second is why #121 was raised.

  **The fix is a subtraction.** The 8 was historic and its own comment admitted
  it — it "stood while the idle rate was 0.343". The ladder's top is the natural
  ceiling and is not a new number: a hand may wind the train up to the fastest
  the machine can be *asked* to run, and no further. Two things then fall out
  that a fixed 8 could not express. A saturating throw takes exactly
  `SPINDOWN_RANGE_MS` to come back, because it **is** the ladder, travelled by
  hand instead of by the slider. And the coast becomes proportional to effort,
  which is what constant deceleration means.

  `rateAt(mult)` is added as the one home for the 1× rate, since `idleRate()`
  and `driveCap()` now want it at two different multipliers and writing
  `7200 / BASE_MS` a third time would be a third place to update.

  **The regression test is the identity, not a threshold.** A saturating throw's
  coast and `SPINDOWN_RANGE_MS` are algebraically the same quantity once both
  derive from the ladder's span, so `tools/test.js` asserts they are equal
  rather than picking a duration nobody derived. Confirmed to fail on the
  original defect: restoring `max(8, idleRate())` reports *"a saturating throw
  at 1x coasts 269.5ms, but the ladder's own crossing time is 2400ms"*. It also
  checks the cap clears the idle rate at every declared stop — the brake case
  the old `max(...)` was there to prevent — and that the 8 is gone from live
  code.

  **`SPINDOWN_RANGE_MS` is untouched at 2400**, and is still the placeholder
  awaiting Charles's call that CL#127 left. This change gives that one number a
  second job it can now be judged on: it is both how long the slider takes to
  cross the ladder and how long the hardest throw runs.

  Nothing about the page at rest changes — `pixel_regress` is 0px at both
  viewports.

### Changed

- **CL#135 — one badge disc for both themes, and an edge so it has a boundary.**

  Charles, on a light stage: *"why do the plates for the icon/links look sort of
  dirty as compared to the background?"*, then *"I like the disc in light mode
  matching dark mode... but could we give a slight border/edge to the disc in
  light mode - both when in a circle and when expanded"*.

  **It was tuned against the wrong thing.** The disc was a per-theme pair and the
  light value had drifted twice already (#35): `#FFFFFF` glared, `#EDEFEA` landed
  at 1.05:1 against the page and vanished, and `#CCCEC9` went the other way. Each
  move was judged against the PAGE — but the disc sits on a WHEEL and never
  touches the page. Measured against one: `#CCCEC9` is **1.07:1** on a yellow
  wheel, which is why it read as grime on warm colours. `#DFE2DE` clears
  **1.30:1** there, and improves the marks the plate exists to carry — GitHub's
  near-black 11.28 → **13.69**, Threads' 13.24 → **16.07**, both far above the
  4.5:1 floor #22 set. `BADGE_DISC` states it once, so there is no second copy to
  drift, and the file keeps one fewer theme conditional.

  **Which leaves it at 1.02:1 against a light page**, so wherever a badge or its
  expanded pill overlaps the background it has no boundary at all. The existing
  `1px solid rgba(20,30,35,.14)` was the same in both themes and far too faint to
  serve: `#c3c7c4`, 1.33:1 against the page. Light now takes `.40` — `#8e9493`,
  **2.40:1** — and dark keeps `.14`, since its disc is 12.25:1 against its page
  and needs nothing.

  **One element carries both states.** The circle and the expanded pill are the
  same node — the pill is that node with a width/left transition — so edging it
  covers both, and they cannot drift apart later.

- **CL#134 — the epicyclic is one part, so it reads at one weight and one tone.**

  Charles, on a light-mode planetary: *"why do the planets have a thicker/more
  defined border than the ring of teeth that they run in?"*, then *"the sun gear
  is noticeably darker than the planets"*, then *"why don't the ring, planets and
  body all end up the same color?!"*

  **The weight was an omission, not a choice.** The annulus carried
  `strokeOpacity: 0.6`; the planet and sun `teethPath` calls simply left the
  attribute out and inherited SVG's default of 1, so the parts came out heavier
  than the ring they run inside. The stud was worse again -- `fill: ft.line` at
  full opacity, the one place the contour ink is used as a FILL rather than a
  line, which made it the darkest thing in the assembly. `EPI_LINE_OP` states the
  figure once and the ring, planets, sun and stud all read it, in both themes.

  **The tone was inheritance.** Planets were `ft.face` (7% toward white) and the
  sun `ft.well` (13% toward black) -- 1.42x apart on a yellow wheel, 1.51x on a
  blue one -- so the sun read as sunk in a pocket. Nothing defended it: the one
  comment about differing fills is about the TWO-ROW case, where the rows
  counter-rotate and identical fills "would hide the one thing worth seeing".
  A single-row planetary has no second row, so the justification never applied.
  Ring, planets and sun now all take `ft.body`, and are told apart by their
  contours -- which is what `ft.face`'s own comment argues for: "in a flat
  drawing the raised face is told by its outline, not by a tonal jump."

  **The two-row rows keep their difference.** On `ravigneaux` the inner and outer
  rows stay `ft.face` and `ft.well`, because there the tonal split carries
  information rather than inheritance.

  The carrier arm is deliberately left heavier (`strokeWidth: 3`,
  `strokeOpacity: 0.85`): its own comment says the load path "is drawn, not
  implied", which is a stated decision rather than an omission.

- **CL#133 — a cut opening is only as legible as what shows through it, and in
  light mode that was the page plus a shadow.** (GitHub #120.)

  Charles, on the shipped light stage: *"the gear centers for a number of them
  become washed out as the outer gear color goes lighter"*, then, marking 51 of
  150 cells on a family x colour matrix, *"look at any light colored gear in
  light mode - their internals are hardly discernable"*.

  **Openings are CUT, not drawn.** Every family but the two epicyclics appends
  its openings to the wheel's own path under `fillRule: 'evenodd'`, so the
  material is removed and what shows inside is whatever is behind. A cut's
  contrast is therefore `body vs page` — 1.33:1 on the palest wheel in light
  against 4.74–9.54 in dark. `planetary` and `ravigneaux` cut nothing; they draw
  their ring and teeth in `ft.line`, 40% toward black from the wheel's own
  colour, and were the only two families marked 0/10 at every colour. That is
  the whole asymmetry, and the fix is to give the cut families the contour the
  drawn ones always had.

  **Proportional on both axes, no per-family table.** Colour is `ft.line`, so a
  pale wheel gets a line 40% darker than itself and Harper's chain gets a purple
  one. Width is a fraction of the opening — measured, opening size spans 5.6x
  across the families (34.6 units on `spokes`, 6.2 on `isogrid`), and a flat 1px
  read as a contour on `sunburst` while flooding `isogrid` into speckle. Opacity
  ramps only where the width has bottomed out on the aliasing floor, which is
  the one axis that cannot thicken a lattice.

  **`MIN_CUT` — the floor was on the wrong quantity.** `isogrid` floors its
  lattice PITCH at 5.2, then shrinks each cell by `1.732 * WALL` to leave the
  wall, so what was actually cut measured **3.34** units; `polariso` reached
  **2.18**. At that size the walls and the contour are most of the cell. The
  floor now sits on the CUT and the pitch is derived from it, which makes the
  sweep stop coarser: `isogrid` 108 openings -> 60, `polariso` 120 -> 72,
  `polarbrick` 90 -> 36. Fewer and larger, which is exactly what `sunburst`'s
  `maxLegible` already does — and `sunburst`, which never cuts below 7.41, was
  never the complaint.

  Two corrections on the way: flooring the sweep did nothing at first because it
  counts DOWN from the dealt cell size, so a floor above that start meant the
  loop never ran and the fallback took over — the min moved 3.34 -> 4.12 and the
  opening COUNT went UP. The fallback needed the floor too.

  **And light mode no longer casts a wheel shadow.** The shared layer paints a
  halo under each wheel and shows through the openings as well as the tooth
  gaps: measured, a cut read **22 units darker** than the page beside the gear,
  so a hole never showed the page. Charles: *"there should be no adjustment to
  what is visible as the background behind the gear"*. With it off the interiors
  measure bit-identical to `--ref-bg`. Dark keeps its halo, where the wheel is
  lighter than the page and the shadow does what it was written for; the badge
  disc keeps its own lift, so the page still reads as layered.

  **Things measured and discarded**, each of which looked right until it was
  photographed: darkening the wheel BODY (aimed at `shades()`, which does not
  paint the body — rendered luminance moved +0.009); a `LIGHT_BODY_FLOOR` solved
  against wheel-vs-page (a +0.224 predictor, where family was +0.275); a uniform
  tint inside each opening (the contrast curve is V-shaped and 0.16 sits at its
  bottom, taking the yellow from 1.33:1 to 1.03:1); and a clipped, offset "inner
  shadow" that turned out to be that same tint, since a 2.2px drop on a 30px ray
  overlaps 93% of itself.

  Placement mattered more than any of the tuning: the contour must be drawn
  OUTSIDE the clipped group. Inside it the clip is `path + holes` with evenodd,
  so a stroke on a hole boundary loses its inner half — deepening the ink from
  0.78 to 0.96 measured 0.43% dark pixels against shipped's 0.42%.

- **CL#132 — a self-driven root gets its leading escape run, because the rule
  withholding it was written about bridges.** (GitHub #116 follow-up.)

  Charles, looking at the live combined stage: *"why in the fuck doesn't harper's
  chain look the same as my chain — the logic for both chains should be identical
  now since they are independent"*, and then the precise version: *"you only have
  two leading gears — and the chain doesn't extend in front of the only gear in
  the chain."*

  He was right, and the page was doing it deliberately in two places.

  **Measured before it was touched.** At 1440×900 Charles's row ran ghosts off
  the left edge to x=−222; Harper's stopped dead at x=406, a third of the way
  into the frame. Both ran off the right edge normally. So the fault was one
  end of one chain, not the composition.

  **The cause is that the two sides were made of different things.** Harper's
  leading side is an **origin run** — structural, a `TRAIN` entry, capped at
  `MAX_IDLERS`. Every side of the spine is an **escape run** — decoration,
  computed after the fit, which keeps adding ghosts until it leaves the
  viewport. A capped run cannot reach the frame; an uncapped one always does.
  That is also why her *trailing* run had six ghosts and the spine's had three:
  it starts further from the edge, so it has more distance to fill.

  **`fitEscapes` withheld the leading run from every chain that is not the
  spine, and the argument it was written with only covers driven chains:** "the
  end a driven chain is missing its leading run at is the end its bridge arrives
  at, so the chain visibly receives its power there instead of trailing a second
  tail into the machinery that drives it." A root has no bridge arriving
  anywhere. The gate is now `owns an origin run`, asked of the solve, rather than
  `is the spine`. A driven chain keeps exactly what it had.

  **Hosted on the outermost origin idler, not on the lead gear**, because the
  origin run already occupies that side and starting at the lead gear would lay
  the escape ghosts straight over it. That idler is a wheel `solve()` has already
  placed, so this stays what an escape run is and adds nothing to `TRAIN` — #55
  is untouched.

  **`drive` and `serves` are now published on the solved wheel.** The geometry
  was published and the *purpose* was not, so "which chain does this idler carry"
  could only be recovered by indexing back into `TRAIN` or inferring it from
  position. Recording it is what this file already argues for elsewhere, and it
  is what lets the escape pass stay ignorant of the chain tree. `fitEscapes` also
  records each ghost's host centre, because a run's heading is meaningless
  measured from the wrong origin and the host is no longer `head`-or-`tail`.

  **The other exception was left alone, and it earns it.** The spine still takes
  no idlers — not because it is the datum, but because *"that is also what keeps
  a solo page byte-identical in behaviour"*: one chain is one root, the root is
  the spine, and a solo page has never drawn ghosts.

  **The bigger-pool alternative was built and photographed, and it made things
  worse.** Raising `MAX_IDLERS` to 6 dropped Harper to *one* leading ghost.
  `IDLERS_FOR(roomy)` is binary — `roomy ? MAX_IDLERS : MIN_IDLERS` — and
  `idlerCount()` asks whether `STAGE_CROSS(MAX_IDLERS)` fits the **cross** axis,
  so a larger cap fails that test and falls back to the minimum. Worth stating
  plainly: **`MAX_IDLERS` is budgeted against the cross axis because it was
  written for bridges, which travel across; an origin run travels along its own
  chain's long axis.** The shared count is documented as a feature, but the
  budget behind it only ever measured one direction. That is still true and is
  not fixed here.

  **And the assertion that guarded the withheld run had never tested a driven
  chain.** It ran on `THREE`, whose own comment says its chains "are therefore
  self-driven, each with an origin run of its own" — yet it checked `!spine`,
  called that "driven", and reported `driven chain mid got 2 escape runs`. A new
  test puts the rule on `CASCADE`, which has `hub` as spine, `kid` and `cub`
  genuinely bridged, and `far` a root — all four cases on one stage, with a
  vacuity guard so it cannot pass by solving without a bridge. Both tests fail if
  the one new `hosts.push` is removed; that was checked rather than assumed.

  Two harness models of emission order were removed as fallout, both of which
  aimed at the wrong run the moment a root pushed a second host: `String(2 + bi)`
  for "the spine's two, then one per branch", and `lead ? head : tail` for a
  run's origin. Selected by what the run *is* now.

- **CL#131 — the light background steps down from 90.8% to 88% lightness.**
  (Charles: *"is the light mode background too light? Almost blinding."*)

  `--ref-bg` moves `#E8EAE5` → `#E1E4DD`. A chosen tone, not a derived one — it
  is where a human said the glare stops — but the **constraint** on it is
  derivable and is now written beside it.

  **Two corrections came out of measuring this, and both were mine.**

  First, I blamed the wrong thing. I said `--chip: #FFFFFF` paints the eight
  badge discs and that they, not the background, were the glare. **That has been
  false since CHANGELOG #35**, which fixed this exact complaint: the badge fill
  is a per-theme literal (`#CCCEC9` light, `#DFE2DE` dark), deliberately
  detached from `--chip`. Today `--chip` paints only the closed-by-default gear
  panel and the `?hud` instrument, neither visible in a normal load. So the
  background really was the only remaining glare source, which is what Charles
  said in the first place.

  Second, **darkening the background lowers ink contrast rather than raising
  it.** Ink is near-black, so moving the background down moves it *toward* the
  ink and shrinks the gap — 11.38:1 shipped, 10.73:1 here. Still far clear of
  the 4.5:1 floor, but the mechanism is the opposite of the intuition.

  **`--muted` is the binding ratio, and that is the number to remember.** It
  goes 3.54:1 → 3.33:1 against a **3:1** floor for UI text. A further step to
  85% L lands at **3.12:1** — 0.12 of margin. So 88% leaves room and 85% very
  nearly does not: anything darker needs `--muted` lifted with it, which makes
  it a light-theme pass rather than a one-token change.

  Decided from photographs, not from the numbers: seven variants at a fixed seed
  with the contrast table printed on each panel, including a dark-theme
  reference showing the chip-to-background relationship dark keeps and light
  had been accused of breaking.

- **CL#130 — `BAND_MAX`/`ENDS_MAX` were absolute against a proportional
  drift, and the suite's gate on them was one legal draw in 2000.** (GitHub
  #97, split from #64's finding A9.)

  Both caps bound `dealAngles`' accumulated `y` drift, computed from
  `(rOf(parent) + rOf(child)) * sin(angle)` — `MODULE * teeth`, in effect —
  while the caps themselves were flat literals, 62 and 26, right only by
  coincidence at today's `MODULE = 7` and never re-earned when it or the
  tooth range moved.

  **Derived instead of retuned.** `STEP_DRIFT_MAX` computes, once, the widest
  drift any single step of the walk could ever contribute — the same "widest
  pair, steepest angle" arithmetic `endsCapFor()`'s two-wheel floor already
  used, now shared rather than duplicated. `ENDS_MAX` is that ceiling
  itself; `BAND_MAX` is twice it, since the walk's highest and lowest points
  can each reach roughly that far from the baseline before the alternating
  sign pulls it back. At `MODULE = 7` this lands at `BAND_MAX = 129.5`,
  `ENDS_MAX = 64.75` — both well past the old 62/26, which is the point: the
  old numbers were not merely un-derived, they were too tight.

  **The suite's own gate could not have told anyone that.** `'the bearing
  deal keeps the train a horizontal line'` asserted only `legal >= 1` across
  2000 trials — indistinguishable, to that assertion, from a dealer that is
  legal 0.05% of the time. Renamed `'…, at a real rate'` and given the
  `dealTeeth` treatment: a measured rate per swept chain length (1 through 9
  wheels, plus every length a configured chain actually carries), a hard
  fail at zero, and a floor (`RATE_FLOOR = 0.5`) below it. Same family of gap
  as CL#104 (an assertion that could not fail for the reason it was written)
  and CL#113 (a message describing the wrong state).

  **Measured, not merely argued.** At the old flat 62/26 the legal rate
  swept from 100% (short chains) down to 9.7% on an 8-wheel chain — an even
  number of steps cannot fully cancel its own drift back to baseline, so a
  cap sized loosely enough for the lengths that cancel starved the lengths
  that cannot, and a flat number could not represent both. The derived bounds
  measure 84–100% across the same sweep, worst case still the 8-wheel
  parity chain. Confirmed by mutation: reverting `BAND_MAX`/`ENDS_MAX` to
  the old literals fails the strengthened gate outright — *"a chain of 8
  wheels: only 9.5% of draws are legal (floor is 50%)"* — restored
  afterward.

  **`?seed=8231` and the pixel gate move, as expected.** A change to the
  bearing deal changes the shapes it can draw; `tools/pixel_regress.py`
  showed the combined stage and `?who=charles` both moving by exactly that
  and nothing else — see the PR for the measured deltas.
- **CL#126 — `tools/dom_invariants.py` had a third unguarded copy of the
  first-match extractor.** (GitHub #114.)

  CL#112 fixed the `CELL_MIN` trap in `tools/test.js`'s `grabNumber()` and its
  Python mirror in `tools/mesh_dirs.py`: both took the FIRST regex match with
  no ambiguity check, so a name assigned twice — once retired, once live —
  silently returned whichever happened to appear earlier. `#114` was filed
  because that fix left a third copy untouched: `tools/dom_invariants.py`'s
  own `_grab_number()`, and a `_grab_string()` with the identical weakness.

  Not a live bug — the three names this file extracts (`MODULE`, `TOOTH_ADD`,
  `FLAT_INK`) each resolve to exactly one assignment in `index.html` today —
  but that was true of `CELL_MIN` too, right up until it wasn't. The failure
  mode is a plausible wrong value with everything downstream still passing,
  and `_grab_string()` is arguably worse: a string has no shape to fail on,
  so any first match looks like a valid answer.

  **The same contract, ported rather than re-derived.** Comments are stripped
  first (`MODULE` and `BAND_DEPTH` each have a second textual match inside a
  comment quoting their own declaration in prose), then both functions count
  every *assignment* to the name — literal or not — and refuse if there is
  more than one. Counting only numeric literals is the naive fix and would
  not have caught `CELL_MIN`, since the live declaration is `px(3.9, 2.2,
  6.0)`, not a number; CL#112's mutation testing already established that
  the assignment count, not the comment-stripping, is the load-bearing half.

  **Verified by mutation, on scratch copies of `index.html` only** — this
  ticket is tools-only and `index.html` itself was never touched. A second
  `MODULE = ` assignment made `_grab_number('MODULE')` throw "constant
  MODULE is assigned 2 times… cannot tell which one ships"; a second
  `FLAT_INK = ` assignment made `_grab_string('FLAT_INK')` throw the same
  shape of message. Both restored. Swept every name the file actually
  extracts (`MODULE`, `TOOTH_ADD`, `FLAT_INK`) against real `index.html`:
  each resolves to exactly one assignment, and `tools/dom_invariants.py`
  still passes all four checks against a served copy of `main`.

  **Three files, three copies, one fix applied twice now.** Worth naming
  since it is the pattern this ticket exists to close: a shared helper is
  not obviously worth it — it would span one `.js` and two `.py` files with
  no natural import path between them, for ~15 lines of logic each copy
  already carries a from-scratch, well-commented account of — but three
  independent copies have now needed the identical patch twice, which is
  exactly the "one home for a fact" rule this repo holds everywhere else.
  Left as a recommendation rather than acted on here: extract a single
  `extract_constant.py` (or equivalent) that `mesh_dirs.py` and
  `dom_invariants.py` both import, and accept that `test.js` stays a fourth,
  deliberately independent implementation since there is no clean shared
  module across a language boundary without adding a build step this repo
  does not otherwise have.
- **CL#125 — the bearing-deal harness modelled the train instead of reading
  it, and two engraving copies did too.** (GitHub #102.)

  Split from #64 (finding A13, second half): several harnesses carried their
  own literal, formula or model of page geometry instead of reading it out of
  `index.html`, which is the one rule `tools/test.js`'s own header states —
  and CLAUDE.md, in *"Verifying a change"* — is what makes the suite honest.
  Safe to act on now that both extractor traps CL#112 and CL#126 closed are
  fixed: converting more harnesses onto `grabNumber()`/`grabDecl()` no longer
  multiplies a bug, it just reads the page.

  **Confirmed independently before touching anything.** `tools/test.js`'s
  `'the bearing deal keeps the train a horizontal line'` stood in for
  `rOf(parent) + rOf(child)` with a fixed `MODULE * 16` — not even
  `TEETH_MEAN` (16.3), and never the DEALT radii `dealAngles()` actually
  produces (`dealTeeth()` draws each wheel uniformly from `[TEETH_MIN,
  TEETH_MAX]`, so a real step can be as wide as two `TEETH_MAX` blanks). A
  throwaway probe — the model's fixed radius against per-wheel teeth dealt
  uniformly over `[TEETH_MIN, TEETH_MAX]` and the real `rOf()`, 500,000
  trials per length — measured the shipped 7-wheel chain at **model 57.7% /
  real 54.1%, a 3.7-point gap**, and confirms the bias is systematic and in
  the direction #64 reported: every ODD chain length (1, 3, 5, 7, 9 — the ones
  bound by `endsCapFor`'s single uncancelled step) showed a 3-4 point gap,
  while every EVEN length (bound by `BAND_MAX`, where alternating steps
  cancel regardless of radius) showed under 1 point. The exact **6.1**-point
  figure #64 reported did not reproduce — the page has moved since (CL#111's
  `ENDS_APART`-for-three-wheel-spines fix among them) and #64 does not state
  its trial count or exact methodology — but the qualitative finding does:
  the model is optimistic, by several points, specifically on the odd-length
  chains the design's own comments say are the tight case.

  **The fix executes the page's own `rOf()`** (`const rOf = (t) => MODULE *
  t.teeth / 2;`, `grabDecl`'d out of `dealAngles()`) against per-wheel teeth
  dealt uniformly over `page.TEETH_MIN..TEETH_MAX` each trial, instead of a
  hand-typed stand-in. Two engraving copies went the same way:
  `textModules = 0.80` (twice) is now `ENGRAVE_SIZES.{handle,stamp}`, read
  off `engraving()`'s own `const T0 = fit(handle, mid, m * 0.80), B0 =
  fit(stamp, mid, m * 0.60);` line by regex rather than retyped — the second
  number, `0.60` for the machining stamp, had never been extracted at all
  before this, only the handle's.

  **No assertion's verdict changed against the shipped page** — real
  acceptance never hit 0% for any length 1–20 the sweep covers, so nothing
  currently reachable flips `bad.length === 0`. What changed is what the test
  can now catch: mutation-tested by reverting to the old fixed-model logic
  against a scratch `index.html` with `TEETH_MAX` raised from 19 to 40 (a
  real regression the deal could actually ship) — the OLD test kept passing,
  blind to it by construction, since it never reads `TEETH_MIN`/`TEETH_MAX`
  at all; the NEW test fails, naming `a chain of 8 wheels: no bearing draw
  satisfies the drift caps`. The two engraving assertions were mutation-tested
  the same way, each failing on the real page value it now reads (handle
  pushed to `m * 1.90`: *"band 1.59m cannot hold 1.9m lettering"*; stamp
  pushed to `m * 3.00`: *"stamp ring is dropped 1.155m, past the band
  half-depth 0.795m"*) and restored clean afterward.

  **Swept the issue's tier-3 files** — `tools/ravigneaux.js`, `mesh_inv.js`,
  `mesh_epi.js`, `mesh_rav.js`, `mesh_audit.js`, `mesh_poly.js` — one-shot
  analysis scripts run by hand, not gates, but cited as evidence in design
  decisions. All six carried their own copies of `MODULE`, `TOOTH_ADD`,
  `TOOTH_DED`, `TOOTH_PA`, `TOOTH_THICK`, `RING_STUB`, `CLEARANCE`,
  `ENDS_APART`, `ROOT_MARGIN`, `MIN_MODULE` and (`ravigneaux.js`) a second
  copy of `planetaryBore()`'s formula; all six now read those out of
  `index.html` through one new shared `tools/mesh_extract.js` (`grabNumber`/
  `grabBlock`/`grabDecl`, porting CL#112's contract unchanged). Unlike the
  JS/Python split CL#126 declined to bridge, these six files share no
  language boundary with each other, so one module removes six copies of the
  same ~15-line idiom instead of leaving a sixth — `ravigneaux.js`'s `boreOf`
  now executes the page's real `planetaryBore()` rather than re-deriving it.

  **One of the six copies had actually drifted, not just risked it.**
  `mesh_audit.js` and `mesh_poly.js` both drew their tooth root at `r -
  MODULE * 1.15` — `TOOTH_DED`'s value *before* `bf16c0c` ("true involute
  tooth flanks — the teeth now touch") moved it to `1.25`, which neither file
  ever picked up. Reading `TOOTH_DED` instead changes their printed numbers
  for real: `mesh_audit.js`'s root-clearance column moves from about `-1.6`
  to about `-2.3` (the root sits shallower than these tools had been
  reporting), and `mesh_poly.js`'s shipped-profile min gap moves from
  `0.78px` to `1.48px`. Neither script asserts pass/fail, so nothing was
  silently green — but anyone reading either tool's output by hand for the
  last nine commits was reading tooth geometry that was not what
  `teethPath()` actually draws. `tools/mesh_inv.js`'s (already-correct)
  `MODULE`/`TOOTH_PA`/`TOOTH_ADD`/`TOOTH_DED` and `tools/ravigneaux.js`,
  `mesh_epi.js`, `mesh_rav.js` were re-run before and after conversion and
  diffed byte-identical — those five copies had not drifted, only risked it.
  The hand-authored `TRAIN` fixtures in `mesh_inv.js`, `mesh_audit.js` and
  `mesh_poly.js` are deliberately left alone: they pin one worst-case scenario
  for repeatable-by-hand debugging, which is a different job from measuring
  what the deal produces, and dealing them for real would trade that
  repeatability for nothing this ticket asked for.

  `index.html` itself is untouched throughout — every number above moved
  because a tool started reading it correctly, not because the page changed.
  `npm test`: 104/104, unchanged from before this ticket.
- **CL#124 — three constants said "px" and none of them was px.** (GitHub #99.)

  `CLEARANCE` was commented *"px kept between the tip circles of wheels that are
  not meshed"* and `ENDS_APART` *"extra push between the two extremities of the
  spine"* — both in **solve units**, which are scaled by `tight` and then by `S`
  on the way to the screen. So a value reading as "13 px" is not 13 px on any
  display, and the realised gap is `CLEARANCE * tight * S`.

  **A comment stating the wrong unit is worse than no comment**: it is a false
  statement a reader will act on, and it sits in the same family as CL#112 (an
  extractor silently returning a retired value) and CL#113 (assertion messages
  describing the state that held rather than the one that broke). Three
  varieties of the file saying something that is not true.

  **The sweep found a third**, which is the point of sweeping rather than fixing
  the two that were reported: `TOOTH_ROOT_MIN = 4` carried the same "px floor"
  label and is also solve units — compared straight against `r = MODULE *
  teeth/2`, the same unscaled space. It predates `px()` (CHANGELOG #61), so it is
  not run through that conversion either.

  **Deliberately NOT re-expressed as `MODULE` multiples.** CLAUDE.md's rule is
  that a derivable value should be derived, and a clearance stated in modules
  would survive a change to `MODULE` where a bare 90 would not — but these were
  *tuned as flat pushes in solve units*, not conceived as module counts, and
  rewriting them as multiples would assert a relationship nobody established.
  That is a different change, and it would have to prove itself at 0px rather
  than be smuggled in beside a comment fix.

  This waited for CL#111, which fixed the three-wheel spine and deliberately left
  `ENDS_APART` itself untouched — a flat 90, same declaration — precisely so
  there would be something stable to document.
- **CL#123 — `bridge` was a boolean about the spine; `child` names a parent.**
  (Charles, 2026-08-05/06. GitHub #116, which supersedes GitHub #107 and
  replaces CL#122 outright.)

  Charles: *"why in the heck would we want an undriven set of gears if it's not
  'bridged' — change `bridge` to be `child`: if set to another name then bridge
  off that at the appropriate spot, with re-ordering etc; if set to null, or
  removed, then the chain is independent."*

  `bridge: true | false` answered "does the spine reach me?", which is not the
  question that matters. It could only ever express a **star off the spine** —
  there was nowhere to say that chain C is driven by chain B — and `bridge:
  false` produced a set of gears nothing turns.

      child: 'charles'      a dependent, driven off Charles's group
      child: null / absent  independent, and independent means SELF-DRIVEN

  **Independence is a drive path, not a disconnection.** An independent chain
  gets an **origin run** of its own: a run of plain idlers, the same count a
  bridge takes, carrying drive in from off the stage. It has its own resulting
  direction — derived from that idler count, exactly as a bridged chain's is —
  and reads as its own machine running rather than as one that happens to spin.
  Both chains still turn on **the one master angle**, and that must never change:
  a second integrator drifts out of mesh within seconds and has broken this page
  twice (CL#3).

  **Siblings cascade; they do not all hang off the parent.** `child: 'charles'`
  declares *membership* of Charles's dependent group — the attachment point is
  computed. The first child takes its drive from the parent, and every later
  sibling takes it from the **lead gear of the sibling before it**, because you
  do not take four power take-offs off one gear. Siblings order by `order`, then
  link count, then name.

  **The stack is a depth-first walk of that tree, not a sort.** A dependent
  follows its parent immediately even when an unrelated root is longer — Charles,
  then Charles's child, then Harper. Link count and name survive only as the
  sibling tie-break. This preserves the invariant the whole solve rests on *by
  construction*: `solve()` places wheels in `TRAIN` order and a drive run may only
  hang off a wheel already placed, and a cascade is inherently ordered, so
  `CHAIN_ORDER[0] === SPINE` still holds without a sort having to agree.

  **`spine: true` is retired; `order` survives, narrowed.** The spine is *the
  first root* — a root is exactly what `child: null` means, and the first of them
  is exactly what the walk lays out first — so the two declarations could only
  ever have agreed, and a config could express a disagreement the page would then
  have had to arbitrate. `order` still ranks **siblings**, and the roots are
  siblings, which is where it names the axis. Both retired keys are **warned
  about rather than ignored**: a file still carrying one is an unfinished
  migration, and reading it in silence would draw a composition nobody asked for.

  **Three mistakes become newly expressible and all three are refused by name**,
  each with a console warning and the chain placed as a root: a chain naming
  itself, a chain naming a slug that is not a person in `config.js`, and a
  **cycle**. The cycle check walks the parent links it has already resolved and
  stops the first time it revisits a name — one pass, and it cannot recurse. A
  parent that is simply not on *this* stage is silent and not a mistake: a solo
  page carries one person, so every dependent is legitimately a root there.

  **A failed hop is announced with everything it stranded.** A bridge that cannot
  be placed cleanly still refuses and the chain is still placed undriven — but
  under a cascade every chain whose drive path runs *through* it loses its drive
  as well, while keeping its position and its bridge, so nothing moves and nothing
  is missing. That is invisible in a still and invisible in the geometry, so the
  refusal warning now names the chains it left undriven, from the one refusal that
  caused it rather than as n symptoms.

  **`ORIGIN_MOUNT` is a placeholder for Charles's call, not a preference of the
  code's.** Where a self-driven chain's run *originates* is the question #107
  never settled and #116 left to be answered from a photograph: `'edge'` (the run
  trails off the stage; the chain's position stays solved) or `'fixed'` (the run
  starts at an anchored mount; the chain's position is pinned and the gap between
  chains becomes `CHAIN_RANK × ORIGIN_PITCH` instead of what the idlers take up).
  `'edge'` is defaulted because it is the reading that changes nothing else, and
  the A/B is a one-word edit. It is deliberately **not** a URL parameter: `?seed`
  is the only determinism affordance shipped code carries (CL#109).

  **An origin run is structure, not decoration.** Its idlers are `TRAIN` entries
  solved *with* the train, they park by the same count a bridge's do, and the run
  is published into `bridgeRuns` — so a later bridge and `fitEscapes` both refuse
  to cross one, exactly as they refuse to cross a bridge.

  **What the gates say.** `npm test` **110 passed, 0 failed** (104 on `main`).
  `tools/verify_motion.py`: 36 of 36 rotating elements advanced, one console
  error, the benign `/favicon.ico` 404. `tools/dom_invariants.py`: **MESH ok, 8
  meshing pairs over 10 wheels, 2 components** — and the component count is the
  thing to read carefully. Under CL#122 Harper's single wheel meshed with nothing
  at all and the gate **failed** on an orphan; her origin run is what fixes that.
  It is still **two components**, and always will be: a chain nothing on stage
  drives is a second mesh *by definition* — that is what independence is. One
  component and a self-driven chain cannot both be true.


- **CL#120 — the datum showed through the bridge idlers, because a translucent
  group of one cannot occlude anything.** (GitHub #86.)

  A bridge idler was dimmed by putting `opacity` on the wrapping `<div>` that
  also carries its rotation. That makes the whole wheel translucent — so the
  datum line, painted behind it, read straight through the teeth and the hub.
  Dimming and occluding are different jobs and one property cannot do both.

  The fix separates them. Opacity moves off the div and onto a `<g>` **inside**
  the wheel's own SVG, and an opaque backing plate is painted before that group:
  a `<use>` of the wheel's **own tooth path**, filled and stroked in `var(--bg)`,
  so the plate is exactly the tooth silhouette and no second geometry exists to
  drift from it. Because compositing is linear, `bg + alpha*(colour - bg)` is
  what a pre-blended fill would have produced — the same pixels, without
  recolouring anything, so the ink census still reads the original hues.

  **Verified by arithmetic rather than by eye**, which is worth recording because
  a screenshot cannot tell a fixed leak from a lucky crop. Reading the idler's
  own rendered fill and computing the composite predicts **(175.4, 178.6,
  177.6)** in light theme; the after-shot at the datum crossing reads a flat
  **(175, 179, 177)** — under 1/255 per channel, with no datum ink in it. The
  same pixels before read (145-152, 152-158, 152-158), deviating 20-30/255,
  which is the additive blend that was the bug.

  **`?who=charles` is 0 px** across both themes and against two separate base
  commits: the solo path has no datum and no bridge, and is untouched.

  **The escape-run ghosts are deliberately not covered, and that is correct** —
  a point worth writing down because it looks like an omission. `wheelOpacity()`
  returns a value only for `role === 'idler'`, so escape-run outriggers take the
  null branch and get no plate. They do not need one: unlike idlers, they and the
  datum already live inside the **same** `ghosts` container under one group-level
  opacity, so the translucent-group-of-one problem never applied to them. An
  isolated escape ghost on the datum baseline diffs **0 px** before and after.
  The two classes are in different coordinate spaces and only one of them was
  ever broken.

  `EDGE` names the stroke width the plate and the real path share, so they cannot
  drift apart. It is not a new tuned number — it is the literal `1` that was
  already on the outline, given one home.

- **CL#127 — spin-down from 200x was over almost at once, because a fixed
  900ms lag is viscous drag on a massless flywheel.** (GitHub #106.)

  Charles: *"cooking down from 200x speed to 1x speed seems to happen really
  fast — is that obeying some artificial physics?"* Yes. `step()` eased the
  flywheel with a first-order lag at a FIXED time constant:

      this._v += (target - this._v) * (1 - Math.exp(-dt / 900));

  Settling time for an exponential decay toward a target does not depend on
  the SIZE of the jump — so 200x -> 1x and 2x -> 1x both took the same
  ~4.5 seconds to settle. For the big drop that meant ~145x of the 199x gap
  was gone in the first 900ms, leaving four more seconds of an imperceptible
  crawl through the last 1x — measured on the real page (below) at 72.3x,
  27.1x, 10.6x and 2.3x at 0.9s/1.8s/2.7s/4.5s, matching the issue's own
  hand-derived table almost exactly. That is a physically coherent model — it
  is exactly what viscous drag (friction proportional to speed) does — just
  the wrong one: viscous drag on a flywheel with no mass. A heavy flywheel
  under mostly Coulomb friction (~constant retarding torque) decelerates at a
  CONSTANT rate instead, so stopping from 200x genuinely takes about 200x as
  long as stopping from 1x — the behaviour the eye expects from something
  that looks like cast iron.

  **`BASE_MS` reconstructed, not merely asserted.** CLAUDE.md's `strobeSpeed()`
  comment already showed `7200 = 360 * 20`, and Charles's own reconstruction —
  a 20-tooth wheel takes `BASE_MS` (21000ms, 21s) to turn once, so an N-tooth
  wheel takes `1050 * N` ms — is confirmed by code that predates every comment
  discussing it: the original per-wheel animation duration, still in the
  file's early history, was `dur: (BASE_MS * t.teeth / 20).toFixed(2)`. That is
  the reconstruction stated as fact, not a guess dressed as one.

  **Three candidates were built and measured against the real page, not
  simulated** (`_v` has no hook to the outside — reading it would mean adding
  one for a one-off capture, which is the kind of debug surface `?hud`'s own
  CLAUDE.md section says to think hard before adding). `tools/spindown_capture.py`
  boots the page pre-seeded to 200x via `localStorage` (the same
  `Page.addScriptToEvaluateOnNewDocument` technique the other harnesses use),
  taps the REAL corner "reset to 1x" button (`resetSpeed()`, GitHub #108 —
  the actual production code path, not a simulated `setState`), and samples
  the driving wheel's own `rotate(...)deg` transform at full frame rate,
  in-page, for the whole run. Speed units are self-calibrated from one
  candidate's own settle (see the script for why the naive per-candidate
  self-calibration was wrong for the slowest candidate, and what fixed it) —
  nothing in the harness needs to know `BASE_MS`, teeth counts, or which
  candidate is running, the same "measure what ships" discipline `tools/test.js`
  already holds to. `tools/spindown_report.py` turns the three JSON traces into
  an overlaid speed-vs-time plot (linear and log) and a filmstrip contact
  sheet. Candidates, all sharing one function name (`approachSpeed(v, target,
  dt)`) so the call site in `step()` never changed shape:

  - **A — as shipped, the control.** `900` named as `SPINDOWN_TAU_MS` and
    nothing else changed. Reproduces the issue's own table.
  - **B — proportional/logarithmic tau.** Keeps the exponential (still smooth)
    but scales tau by the number of OCTAVES the transition spans —
    `SPINDOWN_MS_PER_OCTAVE * log2(bigger/smaller)` — recomputed only when the
    target actually changes (or `_v` was set directly by a flick, which
    invalidates the cached tau so the next tick re-tunes against the new gap
    instead of reusing one tuned for a different jump). The cheaper fix in
    spirit, but it needs latched per-transition state (`_spinTarget`,
    `_spinTau`) and a one-line touch to the drag handler's `up()` to keep that
    state honest across a flick — more moving parts than candidate C for a
    model that (at `SPINDOWN_MS_PER_OCTAVE=300`, the value captured) still
    hadn't fully settled 9 seconds after the tap.
  - **C — Coulomb-ish constant deceleration. Shipped.** `_v` moves toward
    `target` at a fixed rate and ARRIVES, in finite time, rather than easing
    toward it forever. The rate (`SPINDOWN_DECEL`, master-deg/ms²) is derived,
    not hand-picked: `SPINDOWN_RANGE_MS` (2400ms) names the one tunable feel
    figure — how long the flywheel takes to cross the WHOLE ladder, idleRate()
    at `SPEED_CEIL` down to `SPEED_FLOOR` — and `SPINDOWN_DECEL` is that range
    divided by that time, guarded against the schema's own degenerate fallback
    (`SPEED_CEIL === SPEED_FLOOR`) so a broken prop schema can't also zero the
    decel and freeze the flywheel. Memoryless: no latched state, no touch
    needed anywhere outside `step()` and the constants it uses, correct
    through a flick, an arrow key, hover-drag's `load` factor, or a motion
    toggle exactly because it never looks at how `_v` got to where it is.

  **2400ms is a placeholder for Charles's call**, same as CL#127 candidate B's
  300ms/octave — captured against two other candidates, not asserted as the
  only one that was built. Both a linear filmstrip and a log-scale plot are in
  the capture (log shows the multiplicative SHAPE; linear shows what the eye
  actually watches, which is the whole reason the fixed-tau model reads as
  "over at once" despite being smooth in log-space the entire time).

  **Spin-up shares this, deliberately** — the issue asked for the decision to
  be explicit. `approachSpeed()` takes no direction argument: spin-up
  (0 -> idleRate()) and spin-down are the identical formula, called with
  `target` on whichever side of `v` it lands. Coulomb friction opposes motion
  in either direction at the same magnitude, and a real train winds up slowly
  for the same reason it coasts down slowly — no special case, and the suite
  asserts the resulting symmetry directly (equal tick counts to converge A -> B
  and B -> A).

  **A felt side effect worth flagging, not fixed here.** Making the TOP of the
  ladder take longer necessarily makes the BOTTOM snappier than the old
  constant did, because `900` was tuned back when the ladder topped out at 2x
  (the original prop schema), not 200x — it was never really "the" spin-down
  feel, it was the feel for a jump that no longer exists at the top of the
  range. Concretely: an arrow-key tap at 1x used to bleed off over ~900ms
  under the old model; under the shipped constant it settles in ~270ms
  (`driveCap()`'s own comment updated to stop citing the stale figure). That
  is a consequence of fixing #106, not a second bug, but it is a real change
  in feel for the single most common interaction on the page and Charles
  should look at it deliberately rather than inherit it as a side effect.

  **`npm test` grew six assertions**, extracted and RUN rather than read as
  text (`tools/test.js`'s own stated reason: the guarantee here is about
  behaviour over many ticks, not the shape of the source) — a bigger drop
  settles more slowly than a smaller one; the per-tick step stays constant
  mid-descent instead of shrinking toward the target (the exact shape an
  exponential has and this candidate does not); the flywheel reaches its
  target exactly, in finite time, and stays there; spin-up and spin-down
  converge in equal tick counts; the old formula is confirmed gone from LIVE
  code (checked against `STRIPPED_SRC`, not `SRC` — the old formula is quoted
  verbatim in the block comment explaining why it changed, and a check against
  raw source failed on its own prose before it was fixed to strip comments
  first, GitHub #101's trap in a new guise); and `SPINDOWN_DECEL` is checked to
  reference `SPEED_CEIL`/`SPEED_FLOOR`/`BASE_MS` in its own declaration rather
  than being a bare tuned literal. **Mutation-tested by hand**, three mutants:
  reverting `approachSpeed()`'s body to the old exponential (caught by five of
  the six new tests), reverting the call site in `step()` back to the inline
  old formula with `approachSpeed()` left intact but unused (caught by the
  "old formula is gone" test), and hardcoding `SPINDOWN_DECEL` as a bare
  literal instead of deriving it (caught by exactly the one test built for it,
  nothing else). 104 -> 110, all green, restored clean after each mutant.

  **`driveCap()`'s comment updated**, not its logic — it still reads `Math.max(8,
  Math.abs(this.idleRate()))`, untouched, but the comment explaining WHY cited
  a `~900ms` recovery figure that stopped being true the moment `900` stopped
  existing anywhere in the file; it now describes the mechanism (`approachSpeed()`)
  rather than a number that would have gone stale silently a second time.

  **Verify:** `tools/verify_motion.py` against the shipped page — gears
  advancing (39/39 in 700ms), badges at ≤0.01px, one console error (the
  benign favicon 404) — run both without and with `?hud`.
  group of one cannot occlude anything.** (GitHub #86.)

  A bridge idler was dimmed by putting `opacity` on the wrapping `<div>` that
  also carries its rotation. That makes the whole wheel translucent — so the
  datum line, painted behind it, read straight through the teeth and the hub.
  Dimming and occluding are different jobs and one property cannot do both.

  The fix separates them. Opacity moves off the div and onto a `<g>` **inside**
  the wheel's own SVG, and an opaque backing plate is painted before that group:
  a `<use>` of the wheel's **own tooth path**, filled and stroked in `var(--bg)`,
  so the plate is exactly the tooth silhouette and no second geometry exists to
  drift from it. Because compositing is linear, `bg + alpha*(colour - bg)` is
  what a pre-blended fill would have produced — the same pixels, without
  recolouring anything, so the ink census still reads the original hues.

  **Verified by arithmetic rather than by eye**, which is worth recording because
  a screenshot cannot tell a fixed leak from a lucky crop. Reading the idler's
  own rendered fill and computing the composite predicts **(175.4, 178.6,
  177.6)** in light theme; the after-shot at the datum crossing reads a flat
  **(175, 179, 177)** — under 1/255 per channel, with no datum ink in it. The
  same pixels before read (145-152, 152-158, 152-158), deviating 20-30/255,
  which is the additive blend that was the bug.

  **`?who=charles` is 0 px** across both themes and against two separate base
  commits: the solo path has no datum and no bridge, and is untouched.

  **The escape-run ghosts are deliberately not covered, and that is correct** —
  a point worth writing down because it looks like an omission. `wheelOpacity()`
  returns a value only for `role === 'idler'`, so escape-run outriggers take the
  null branch and get no plate. They do not need one: unlike idlers, they and the
  datum already live inside the **same** `ghosts` container under one group-level
  opacity, so the translucent-group-of-one problem never applied to them. An
  isolated escape ghost on the datum baseline diffs **0 px** before and after.
  The two classes are in different coordinate spaces and only one of them was
  ever broken.

  `EDGE` names the stroke width the plate and the real path share, so they cannot
  drift apart. It is not a new tuned number — it is the literal `1` that was
  already on the outline, given one home.
- **CL#121 — the datum's minor ticks are gone, and CL#107's borrowing mechanism
  went with them.** (GitHub #115.)

  This entry records a mechanism that was built and then removed on the
  evidence. Charles: *"I don't know that the minor ticks on the datum line add
  any value — prove me wrong."* A sweep was run — four variants, both themes,
  1440×810 and 390×844, identical crop windows — and could not. At real
  viewing size, with or without them was indistinguishable in full context; at
  1:1 the marks were findable only once you already knew where to look, and
  read as texture rather than as a countable scale. Measured: at 390×844 the
  minor tick is **1.00px** wide — `Math.max(1, MODULE * 0.13 * S)` hitting its
  clamp floor, so the *derived* width was already sub-pixel — and about 3px
  long. At 1440×810 it was 1.26px by 4.86px, spaced ~37px apart.

  **The decisive finding concerns Harper.** CL#107's borrowing worked — it
  matched her one-link chain's minor spacing to Charles's, within rounding.
  But that means her marks were exactly as imperceptible as his. The mechanism
  achieved parity, not visibility. **CL#107's derivation was correct and
  elegant, and it served something nobody could see.** Sunk cost is not value,
  so it comes out rather than staying dormant.

  **Removed:**
  - The minor ticks themselves, from the datum line, for every chain — both
    the loop that subdivided a chain's own station gaps and the borrowed-grid
    loop a one-station chain used instead.
  - CL#107's whole borrowing mechanism: the station-pitch derivation (the
    axial length the station pattern occupies, over the station count), its
    degenerate-case collapse to a wheel's own pitch diameter, the
    zero-station lends-nothing rule, `SUBDIV`, and the two suite tests it
    added (`a one-station chain is scribed at the spine's station pitch, and
    nothing else is`, `the spine lends the scale to itself when it is the
    one-station chain`).

  **Checked, not assumed: the derivation fed nothing but the minors.** `pitch`
  (on each run) and `scale` (feeding it) had exactly one consumer each —
  `datumLayer()`'s borrowed-tick loop and the `lent`/`pitch` assignment in
  `datumRuns()` — so nothing else in the file, and nothing else in the suite,
  read either name.

  **What stays.** The major ticks — one per station, at the wheel centres —
  and the datum line, the plate and its stamp are untouched. `MAJOR` and
  `PAST` are unaffected; only `MINOR` and `SUBDIV` are gone.

  Two suite tests removed with the mechanism they existed to prove (`npm
  test`: 90 → 88 `test()` blocks). The remaining tick-strike count in `the
  plate seats on the side the page has room for, and the ticks follow it` —
  which used to assert three strikes (major, self-subdividing minor, borrowed
  minor) — now asserts one; reverting the removal so a strike reappears was
  used to confirm the assertion still catches a regression. `npm test`: **88
  passed, 0 failed.**

  Photographed before and after, both themes, 1440×810 and 390×844, deal held
  fixed with a seeded LCG: the combined stage moved (258–490px differ per
  viewport/theme, all of it the missing marks), `?who=harper` did not (0px —
  no datum is drawn on a solo stage at all, so the removal has nothing to
  touch there).

- **CL#113 — two assertion messages that named the pass instead of the fail, and
  a sweep for a third.** (GitHub #105.)

  `eq(bridges[0].idlers.length, 0, 'an unbridged chain claims idlers')` and
  `eq(train[bridges[0].head].parent, null, 'an unbridged chain is not a root')`
  each read, cold, as a flat statement about a healthy tree rather than as a
  report of what broke — a message an assertion function only ever prints on
  failure has to say what *is* true then, and "claims idlers" / "is not a root"
  are exactly as true of the passing case as of the failing one, so a reader
  meeting either for the first time on a red run has nothing in the sentence to
  tell them which. Both were rewritten to say the deviation: *"kept idlers on
  its bridge record, and it has no drive to hang them off"* and *"was given a
  parent, so it is being driven by the chain it opted out of"*.

  Both corrections had already landed, uncredited, inside CL#104's commit —
  found there while chasing the same family of fault (an assertion that cannot
  say what went wrong is one more step from an assertion that cannot fail at
  all, GitHub #89). This entry is the credit that commit didn't leave, plus the
  sweep the ticket actually asked for: every `ok(...)` and `eq(...)` message in
  `tools/test.js` — 282 call sites across 89 `test()` cases — read against the
  same question, which state does this sentence describe. None of the rest
  share the fault; the file's prevailing convention already names the
  deviation directly ("a plate that seats cleanly warns about it", "the bridge
  bearing is not measured from `_axisRot`") or states the requirement as a
  requirement ("a train must have exactly one root", "a two-row entry needs
  `[Zs,Zp1,Zp2,Zr,N]`"), and either reads the same on a red run as off one.

  Verified by forcing `bridges[0].idlers.length` to want `99` instead of `0`:
  the suite failed with *"an unbridged chain kept idlers on its bridge record,
  and it has no drive to hang them off (got 0, want 99)"*, then restored.
  `npm test`: **89 passed, 0 failed.**
- **CL#112 — `grabNumber()` no longer guesses between two declarations of the
  same constant.** (GitHub #101.)

  `tools/test.js` reads its geometry constants OUT OF `index.html` rather than
  keeping copies, which is the whole reason a broken page cannot pass the
  suite (see CLAUDE.md, "Verifying a change"). `grabNumber()` is the function
  that makes that true, and it had one live trap: `String.match` with a
  non-global regex returns the FIRST match in the file, with no check that a
  name is unique.

  `index.html` declares `CELL_MIN` twice — a retired honeycomb family's
  literal `CELL_MIN = 2.8`, and hexcore's live `CELL_MIN = px(3.9, 2.2, 6.0)`.
  Verified directly: the old `grabNumber('CELL_MIN')` returned **2.8**, the
  retired figure, and could not have returned the live one under any
  circumstances — `px(...)` is not a number literal, so it never matched the
  pattern at all. Nothing in `test.js`'s `consts` list currently asks for
  `CELL_MIN`, so this had not yet produced a false pass, but it was the exact
  shape of bug CLAUDE.md warns the whole suite's honesty rests on: silent and
  green.

  **Ambiguity is now fatal, and it is caught even where counting numeric
  matches alone would miss it.** Comments are stripped first (block comments,
  the idiom four other call sites in `test.js` already use), so a name merely
  discussed in prose can no longer stand in for a declaration. Then
  `grabNumber()` counts every ASSIGNMENT to the name — literal or not — and
  throws if there is more than one. Counting plain-number matches alone would
  not have caught `CELL_MIN`: only one of its two declarations is a literal,
  so that count was already 1. `tools/mesh_dirs.py`'s `_grab_number()`, the
  identical idiom in Python, got the same treatment.

  Swept every name either file currently extracts — the full `consts` list
  plus `TEETH_MEAN`, `LINK_SHARE`, `CROSS_BLEED`, `MAX_IDLERS`, `MIN_IDLERS`,
  `CLEARANCE`, `ENDS_APART`, `TARGET_GEAR_PX`, `MODULE`, `TOOTH_ADD` — and
  every one of them resolves to exactly one declaration; `CELL_MIN` is the
  only ambiguous name in the file, and nothing currently reads it, so no
  extracted value changed. Mutation-tested by reverting `grabNumber()` to the
  original first-match behaviour: the suite's new test fails, naming the
  regression (`grabNumber('CELL_MIN') silently returned the retired honeycomb
  literal (2.8)...`) rather than failing on an unrelated assertion.

  `index.html` itself is untouched — the retired `CELL_MIN` stays retired, on
  purpose, the same as `honeycomb`'s whole family. `grabNumber()` is what had
  to cope, not the page.
- **CL#111 — a three-wheel spine can now pay `ENDS_APART`.** (GitHub #104.)

  `ENDS_APART` (90, in solve units) is the extra push kept between the
  machine's two spine extremities so a run reads as a line rather than a
  closed ring. A spine of exactly three wheels asks for the whole of it in
  two mesh steps — the leaf's only host is one hop from the root — and on
  measured ~40-50% of deals no bearing within the leaf's own ±60° nudge could
  pay it, in either direction: not a search failure, but the root and the
  ENDS_APART owed to it not fitting inside that swing at all. `wozi: wheel 2
  ... found no clear bearing ...; planted anyway, and may clash` was the
  visible result. Four wheels and longer never hit this: the host the check
  compares against is by then several hops from the root, so the achievable
  separation dwarfs the flat push and it was never the binding constraint.

  **`ENDS_APART` itself is unchanged** — still the one flat figure, still 90,
  still in solve units, still named and used exactly where it was. What
  changed is `solve()`'s own arithmetic: the push it actually asks a wheel to
  clear is now `Math.min(ENDS_APART, endsApartCapFor(o))`, where the cap is
  the greatest distance from `o` any candidate the swing loop is *already
  about to try* can reach — computed by walking that same discrete candidate
  set once, not a second formula that could disagree with the search using
  it. A longer spine's cap sits far above `ENDS_APART` and never binds, so
  nothing here is a second measured constant standing in for the first: it is
  a ceiling derived from the wheels already dealt and the swing already
  budgeted, that happens to equal the old flat push whenever the chain is
  long enough to afford it outright.

  **Measured, not merely run once:** 1,000 real deals of a solo three-wheel
  spine dropped from 483 warnings (48.3%, matching the issue's own ~40% within
  sampling noise) before this change to 0 after, at both stage rotations. A
  1–8 wheel sweep after the fix warns 0/80 at every length, matching the
  issue's own report that only length three ever warned. `?who=charles` and
  the combined stage are both 0px against `HEAD` (`tools/pixel_regress.py`) —
  Charles's own chain is seven wheels, far past where the cap ever binds (a
  500-trial sample of the same cap put its floor at 444.7 against a flat
  push of 90), so nothing about its geometry moved.

  `tools/test.js`'s `DECLARED` fixture (#85) shrinks its spine from four
  wheels to three, which is what it should have been all along: it exists to
  prove a declared spine and stack still compose, and a four-wheel spine
  never exercised the one length this defect actually lived at. A dedicated
  test drives 400 solo three-wheel deals on its own and asserts zero
  no-clear-bearing warnings.
- **CL#115 — a kidney slot's arm is set by width, not by angle, so it keeps
  its shape as the wheel grows.** (GitHub #93.)

  `slots()` — the shared kidney-slot cutter behind the `spokes` and `pockets`
  centre families — sized the slot's width as a fraction of the annulus span
  (`rOut - rIn`), the way every other module-derived measurement on the page
  is, but sized the arm left between two slots as a fixed number of *degrees*.
  A fixed angle converts to a physical length through the wheel's mid radius,
  which tracks the wheel's circumference; the width tracks the much smaller
  span instead — two quantities that grow at different rates across the dealt
  tooth range, so the straight run went flat while the width nearly tripled
  and the kidney read as a round hole at the big end of the deal.

  The fix replaces the fixed angle with `aspect`, a designed straight-run/width
  ratio — a proportion, exactly like the existing `widthScale` — and derives
  the one arm length that delivers exactly that ratio out of the gap this arm
  count leaves at this wheel's own mid radius, converted to degrees by the
  same mid-radius division `capDeg` already used. Where a gap is too tight to
  afford it, the arm floors at zero rather than going negative, so the slot
  widens toward the whole gap instead of demanding an impossible shape.

  `npm test` gained an assertion that reads `slots()` and its two call sites
  back out of `index.html`, executes the real closure, and measures the
  achieved aspect ratio across the whole `TEETH_MIN..TEETH_MAX` range — not
  one sampled size, which is what the bug was about.
- **CL#116 — the epicyclic hub badge's dead knob, and the plateau it was
  hiding.** (GitHub #94.)

  Two faults, both in six lines of `renderVals()`'s badge sizing, and
  measurement rather than reading is what told them apart. `discF` forked on
  `epicyclic` (0.38 vs 0.72) on top of `capF`'s own shrink (0.55 vs 1.15) — a
  second attempt at the same job. `g.r` runs 45.5–66.5 solve units over every
  tooth count this page can deal (`TEETH_MIN`..`TEETH_MAX`, module-derived, not
  hand-picked), so `g.r * 0.38` was always 17.3–25.3: short of `disc`'s own
  30-floor **for every wheel the page has ever dealt, at every scale**, because
  that floor was applied in solve units, before `S` scaled the value in — no
  viewport could ever lift it clear. `disc` came out exactly 30 regardless of
  teeth, which is what "dead" means here: not merely untested, but
  unconditionally unreachable, confirmed by sweeping the full tooth range
  rather than by inspecting the arithmetic. The badge that actually rendered
  tracked `cap` alone, and plateaued the instant `cap` itself passed 30 — at 16
  teeth — because the pinned `disc * S` became the smaller, size-deciding term
  for every tooth count above it.

  **The fix is one constant, not two.** `capF` already shrinks the epicyclic
  badge — that is the comment sitting right above it — so `discF` no longer
  forks on `epicyclic`; it is `0.72` for every kind, matching the ordinary
  wheel's factor it was always meant to sit above. `cap`, smaller by `capF`
  alone, is now what actually governs the epicyclic badge across the whole
  tooth range, and the badge grows continuously from 32.5px to 48.1px over
  13–19 teeth (measured at the render scale #64's own table used) instead of
  flattening at 39.0px past 16. The ordinary-wheel path is untouched — its
  `discF` was already live, so before and after render pixel-identical there.

  **The floor is now stated once, in the unit it is legible in.** The same `30`
  literal appeared twice, four lines apart, in two different units — a
  solve-unit clamp on `disc` and a rendered-pixel clamp on `disc * S` — which is
  what let the first one go dead without anyone noticing the second was doing
  all the work. The solve-unit clamp (and its unreachable 60-ceiling twin) is
  gone; the one clamp that remains is the pixel-space floor, applied after `S`
  scales the badge down, which is the only place a legibility floor means
  anything.

  `npm test`'s existing legibility-floor test now exercises the fixed formula
  unchanged (it reads the three lines out of the page, not a copy), and a new
  test sweeps every dealable tooth count and fails if the epicyclic badge ever
  stops growing — mutation-tested against the original dead-floor code, where
  it fails naming the exact plateau (`16->17 teeth: 39.0px -> 39.0px`, etc.).
- **CL#118 — `engraving()`'s sweep cap is a clear-metal length, and its width
  is measured, not guessed.** (GitHub #98.)

  Two faults in one six-line closure. The cap on how far the handle or the
  stamp may sweep round the band was a fixed 168 degrees, so the clear metal
  it left between them — the thing that actually has to stay constant — held
  at exactly one radius and drifted everywhere else: #64 measured 6.46 to
  10.86 units, a 1.68x spread, across the shipped 13-19 tooth range. It is now
  solved the other way round: `ENGRAVE_GAP` (1.24 modules, chosen to land
  close to where 168 degrees did at the middle of the tooth range) states the
  clear metal, and the permitted angle is derived from it per wheel —
  "geometry derives in one direction" applied to the band's circumference
  instead of its depth. And the text width feeding that computation was a
  per-character guess (`per`/`track`) sitting a thousand lines under
  `textWidth()`, the memoised canvas measurement built for exactly this
  problem — one home for the fact, not two answers that could disagree.
  `emWidth()` now asks `textWidth()` at a large fixed reference size and scales
  the ratio down, so every candidate font size `fit()` tries for the same
  string is one memoised canvas call rather than several.

  **Replacing the guess uncovered a second, sharper bug on the way in.**
  `emWidth()`'s first measurement runs during the very first render, which is
  before the Google Fonts stylesheet has registered Manrope in
  `document.fonts` — measured then, `bold Manrope` silently falls back to the
  fallback stack and *underestimates* the real glyph run, and because
  `textWidth()` memoises forever, that wrong number stuck: the guide arc built
  from it was shorter than the text painted on it once the real face arrived,
  which is a worse failure than the guess it replaced. `componentDidMount` now
  clears the memo and forces one more render once `document.fonts.ready`
  settles. A second, smaller gap came from the tracking convention: Blink adds
  the 0.1em letter-spacing after every glyph, including the last, not once per
  gap between glyphs, so `emWidth()` now counts `str.length` tracking units,
  not `str.length - 1`. Both were found by comparing every engraved wheel's
  guide-path length against its own `getComputedTextLength()` on the live DOM,
  not by eyeballing a render.

  Verified with two mutation tests (a reintroduced fixed angle, a
  reintroduced per-character guess) that fail with a message naming the real
  regression, a new `npm test` assertion that the clear metal stays within
  1e-6 of `ENGRAVE_GAP * MODULE` across the full 13-19 tooth range at a label
  length long enough to engage the cap, and a contact sheet of the longest and
  shortest configured labels on the smallest and largest dealt wheels, both
  themes, before and after.
- **CL#119 — a ghost's addendum now has one home, `TOOTH_ADD`, instead of
  three.** (GitHub #100.)

  A ghost wheel's outer radius — pitch radius plus addendum — was computed
  three different ways: `MODULE * 0.95` where `fitEscapes()` places and
  collision-tests an escape-run ghost, `MODULE * (teeth/2 + 1.25)` where the
  ghost layer reserves its compositing box, and `MODULE * TOOTH_ADD` (1.00)
  everywhere a linked wheel is measured, including `WHEEL_SPAN`. None of the
  first two read `TOOTH_ADD`, so the constant that exists to be the addendum's
  one stated home was quietly disagreed with twice.

  The `0.95` had no defending comment and was 5% under the true addendum on a
  background wheel's own placement radius — measured, in module units, against
  `TOOTH_ADD`: 0.05 modules short, 0.35 solve units, well under a pixel at the
  page's usual scale. Small, but it meant a ghost's own creation site and every
  linked wheel disagreed about what an addendum is. Now reads `TOOTH_ADD`
  directly.

  The `1.25` was different: its comment already named it as addendum plus a
  real flat pad for the drawn wheel's stroke and baked-in shadow, measured at a
  10–17px shortfall if omitted. It was written as one number, `1.25`, rather
  than as `TOOTH_ADD` plus that pad — so it read as a competing addendum
  instead of an addendum with a margin, and would not have followed `TOOTH_ADD`
  if that constant ever moved. Decomposed into `TOOTH_ADD + GHOST_BOX_PAD`
  (`GHOST_BOX_PAD = 0.25`), with the pad now named and the total numerically
  unchanged — the reserved box is exactly as large as before, so nothing that
  read it can have started clipping.

  **Measured, not assumed.** A representative wheel's tip radius under the
  three old addenda, in solve units (`MODULE = 7`): 76.65 (`0.95`, ghost
  creation) vs 77.00 (`TOOTH_ADD`, every linked wheel) vs 78.75 (`1.25`, the
  ghost box) — a 2.1-unit spread top to bottom, teeth-count-independent since
  the addendum term doesn't carry `teeth`. At the page's documented "usual
  scale" of `S ~ 1.25` that is under 3px, which is why nothing has visibly
  clipped; the bug was never the size of the gap, it was that three call sites
  had no reason to agree on it.

  **Confirmed by seeded pixel diff** (`tools/pixel_regress.py --seed 8231`):
  the linked (coloured) wheels are pixel-identical before and after, on the
  combined stage and on `?who=charles` alone. Only the decorative escape-run
  ghosts move, because the corrected placement radius feeds a collision test
  inside a seeded random walk — shifting the radius by 0.05 modules can flip
  which candidate step a rejection-sampling loop accepts, forking the `rnd()`
  draw sequence for every ghost placed after it in that run. That is a real,
  visible ripple under a fixed seed and an invisible one in production: ghosts
  are re-dealt on every real page load regardless, seed or no seed.

  Added a test asserting *agreement* rather than any one value — the failure
  mode here was always disagreement between call sites, not a wrong constant —
  by running the real `fitEscapes()` and reading a ghost's placed radius back,
  and by checking the ghost-box formula is textually built from `TOOTH_ADD`
  rather than restating the addendum as its own number. Mutation-tested by
  reintroducing each of `0.95` and the bare `1.25`: both are caught, each with
  a message naming the call site and the value, not a bare number mismatch.
- **CL#117 — the sunburst window count is derived from the blank, not dealt.**
  (GitHub #96.)

  `sunburst`'s `arms` variant (10/14/18) was cut straight into the wheel as its
  window count, with no regard for how much room the blank actually has. On the
  smallest wheel the deal can produce (13 teeth) the 18-arm variant cut a window
  measured at 0.78 rendered px on a real phone (#64's finding A8) — an aliasing
  artefact, below a hairline, not an opening.

  The renderer now inverts the same width equation the bug report named: a
  window's chord width at the inner radius is `2*rInR*sin(0.32*PI/n)`, so the
  largest `n` that still clears a legible floor is a closed form, solved the way
  `holes` already solves for its drill count. The floor is a rendered-pixel
  intent, `px(1.6, 0.7, 2.3)`, sitting between the wall floor above it (1.06px,
  a line that must not vanish) and the drill floor's second tier (2.5px, a
  filled hole that must read as intentional) — a cut window needs to read as an
  opening, more than a wall, but is a slot rather than a filled hole so does not
  need the drill's full area.

  **The dealt variant survives as a ceiling on the count, not the count
  itself.** Ten/fourteen/eighteen still read as coarse/medium/fine wherever a
  blank has room for them — the derivation only bites on the wheel too small to
  seat the dealt number legibly, so the 19-tooth wheel is unaffected at every
  real scale and only the small end is capped, to what it can actually show
  rather than to a fixed floor.

  `npm test` gained an assertion that no sunburst window on any blank the deal
  can produce falls below the floor the renderer itself computed, executing the
  shipped `px()`/`asin()` arithmetic out of `index.html` rather than modelling
  it — mutation-tested by reverting the count to the raw dealt value, which
  failed the new assertion by name (`nR=18 cuts a window ... under the 2.29-unit
  floor`) before the fix was restored.

- **CL#110 — `?hud`, an animation HUD for how the browser is really rendering
  the gears.** (GitHub #92.)

  Every gate in this repo runs one engine, headless, at fixed pixel sizes, with
  no battery and no finger. So the page's behaviour on a real phone — the one
  place several of its bugs have actually lived — has never been readable by
  anything except a human describing what they saw. `?hud` makes the page report
  on itself.

  **Off by default and unreachable by accident.** The gate is
  `/[?&]hud(=|&|$)/`, so `?hudson=1` does not trip it, and there is no button and
  no key binding — the parameter is the whole interface. A visitor who does not
  type it sees a byte-identical page.

  What it reports, grouped by the question it answers: the scope being drawn;
  tick/s against nominal, rAF/s, writes/s, dropped ticks, tick ms at p50 and p95,
  and the sleep gate's own verdict; the speed multiplier with measured master
  rate, teeth per tick and percent of Nyquist, marked when strobing; the wheel
  census split linked/idler/ghost, `--gsfit` raw and quantised, **which of the
  four fit terms is binding**, gear size in CSS and device px, viewport; and the
  panel's own cost in ms and as a share of a frame.

  **It measures without perturbing what it measures**, which is the whole risk of
  a HUD like this. Inside the rAF loop it does integer arithmetic and one array
  write — no DOM, no allocation, no layout read. All rendering happens on a 500ms
  timer outside the loop. It reads the raw inline `--gsfit` string rather than
  calling `getComputedStyle`, which would force a style recalc, and it reads the
  `_solved` cache rather than calling `solve()`, which could pay for a whole
  re-solve on a timer. It reports its own cost so that claim is checkable rather
  than asserted.

  **It reports the sleep gate, it does not participate in it.** `_hudAsleep`
  mirrors the loop's own expression rather than re-deriving it — the one-expression
  rule from #7 is exactly the kind of thing a second opinion breaks.

  **One unsourced claim removed.** A comment stated ticks/s had been "measured at
  28.5–29.7 against a nominal 30". Nothing in the tree supported it, and measuring
  it properly contradicted it: **30.03 ticks/s**, median 33.3ms, p95 34.3ms, and
  **zero** ticks needing a third raw frame across ~1,700 samples — combined stage,
  one chain and a 223-wheel viewport, at 1× and 200×, including a run with every
  core deliberately oversubscribed. The comment now carries that figure and its
  limits, since a number in a comment is read as fact by whoever finds it next.

  Landing note: the branch cited changelog `#103` in six places, which is now a
  GitHub issue number and not this entry. Renumbered to CL#110. **CL#108 is
  deliberately skipped** — it is in history on the reverted plate-clearance commit
  and is reserved for that work re-landing.

- **CL#109 — `?seed=8231`, so that a machine drawn once can be drawn again.**
  (GitHub #48, part 1 of three; parts 2 and 3 shipped as #100 and #93.) Every
  wheel on this page is dealt. Twelve bare `Math.random()` calls pick the tooth
  counts, the centre families and their variants, the bearing angles, the
  planetary's clocking, the colours, and which wheel wears which service — so a
  machine exists for exactly as long as its tab does, and **"it looked wrong on
  my phone" describes something that will never be drawn again.** Both harnesses
  that need a fixed machine inject their own LCG over `Math.random` through
  `Page.addScriptToEvaluateOnNewDocument`, which is right for them and is
  unavailable to a human holding a phone. Naming the seed in the URL is the
  whole feature.

  **This is a deliberate exception to a rule this repo states in several places
  — determinism belongs to the harness, and no test hook ships — so it is argued
  in the file rather than left to be discovered.** A seed is not that hook. It
  changes no behaviour, bypasses no logic, exposes no internal and reaches
  nothing a visitor could not otherwise reach; it fixes ONE input that is
  otherwise unobservable, and its consumer is a person writing a bug report
  rather than a gate. The distinction that makes it safe is not the size of the
  code, it is who is allowed to use it.

  **No gate may ever use it, and the harnesses were deliberately left alone.**
  `tools/pixel_regress.py` and `tools/dom_invariants.py` both still inject their
  own generator even though this parameter would now do the job in one query
  string, because the moment a gate deals through the same mechanism the page
  deals through, a fault in that mechanism is invisible to both — the gate would
  agree with the page about a machine they had both got wrong. Two generators is
  the point. It is written at the install site and in `CLAUDE.md`, which are the
  two places somebody would be tempted.

  **It is installed above every other statement in `index.html`**, and that is
  required rather than tidy: the deal is not something anybody calls.
  `dealTeeth()` and `dealAngles()` are IIFEs that run at module load and the
  first of them draws long before anything renders, so a parameter read beside
  its consumer would be read too late. `?kind=` can afford to sit next to the
  family list it filters — only a function reads it. It follows that parser's
  shape (a regex over `location.search` inside a `try`) and not its position.

  **The seed reaches all twelve draw sites by replacing `Math.random`, not by
  threading a generator through twelve call sites.** Twelve edits is twelve
  chances to miss one, and the thirteenth `Math.random()` somebody adds next
  year would silently escape the seed. Replacing the global covers the deal by
  construction, and the count is now free to move without this feature rotting —
  the issue itself corrected "ten" to "eleven" once already, and it is twelve.

  **The proof is the repeat.** `?seed=8231` in three fresh documents, and again
  in a separate browser process with a separate profile and a separate server
  port: one fingerprint, `576ec7f6b36a6278`, over 26 wheels — rim stamp (which
  carries the tooth count), body fill, centre in screen pixels, and the element
  census of each centre design, identical field by field. `?seed=8232`, one
  apart, draws a different machine (24 wheels): the seed is passed through the
  murmur3 finalizer before it becomes LCG state, because an LCG's state is
  affine in its seed and `?seed=1` and `?seed=2` would otherwise part by
  1664525/2³¹ on their first draw — under a thousandth, which is the same tooth
  count, the same family and the same bearing. Three loads with **no** seed gave
  three different fingerprints, which is the other half of the same proof.

  **And the same statement in pixels**, which is the version that needs no
  fingerprint to be trusted: two independent `pixel_regress --shot` captures of
  `?seed=8231` at 1440×900 differ by **0 px**, and `?seed=8232` differs from
  them by **510,350 px**. (The page's own generator is installed at page-script
  time, so on a seeded URL it displaces the harness's injected one — which is
  fine for a photograph and is exactly why a gate must not pass this parameter.)

  **One static assertion, because no harness can see this break.** `npm test`
  now checks that the installer precedes every `Math.random()` call in the file
  — comments stripped first, since the installer's own comment counts the draw
  sites by name. Position is the feature's whole requirement, and a draw moved
  above the installer (or the installer moved below one) un-seeds the page while
  every other gate stays green: both harnesses inject their own generator ahead
  of all page script, so neither is capable of noticing. Proved able to fail in
  both directions — a draw planted at the top of the script reports the offset
  of the offender, and renaming the installer reports its absence. The suite is
  **89 passed, 0 failed** (was 88).

  **What it fixes and what it does not.** It fixes the *deal*; where the
  finished train is then placed is measured off the viewport, so a seed
  reproduces a machine at a given window size and says nothing across two —
  same seed **and** same window. The escape runs are outside it in the other
  direction: `fitEscapes()` resets its own `_seed` on entry, so that stream was
  never part of the random deal and was already the same on every load. The
  rotation phase is outside it too, and always was — the only thing that moved
  between two same-seed loads was each wheel's axis-aligned box, by up to 0.4px,
  which is the turning the pixel gate freezes with `__pump()` and not the deal.

  **A malformed seed deals at random, and says so.** This is module scope:
  anything thrown here takes the whole script with it and renders nothing at
  all, which is #53 exactly. `?seed=abc`, `?seed=-1`, `?seed=3.5`,
  `?seed=2147483648`, `?seed=` and `?seed=%zz` all draw a normal random machine
  and log one `console.warn` naming what was refused. The capture is everything
  up to the next `&` rather than a run of digits *because* of that message —
  matching digits only would make `?seed=abc` indistinguishable from no seed at
  all. The undecodable case is the one that nearly slipped through: `%zz` makes
  `decodeURIComponent` throw, and catching that with the outer `try` would have
  sent the single most obviously malformed input down the silent path. It is
  caught next to the decode instead and rejected by name. The accepted range is
  `0…0x7fffffff`, which is the generator's own state space rather than a bound
  anybody picked, and `?seed=0` is a seed like any other.

  **Absent the parameter the page does not touch `Math.random` at all**, and
  that is the load-bearing half. `tools/pixel_regress.py` against `main` is
  **0px at 1440×900 and 390×844, on `?who=charles` and on the combined stage** —
  the proof that this costs nothing when unused.

  **The more valuable half did not ship, and the reason is the rule itself.**
  Accepting a seed asks the reporter to reproduce a fault on a machine that is
  not the one that failed; what a bug report actually wants is the seed of the
  machine that *went wrong*. That needs the page to seed itself on **every**
  load, and self-seeding necessarily replaces the unseeded deal's source of
  randomness — after which the pixel gate, whose own LCG the page would now be
  consuming one value from and then ignoring, reports a different machine at
  every viewport and cannot tell that apart from a regression. The only way to
  have both is for the page to recognise when it is being tested, which is
  precisely the test hook none of this is allowed to be. Recording the drawn
  values into a `?deal=` blob would close it honestly — the unseeded stream
  stays native, so the pixel gate stays at 0px — at the cost of a URL nobody can
  read out over the phone. Filed as a follow-up rather than smuggled in here.

  **Discoverability, and what it is honestly worth.** The seed in effect is
  readable at `window.__WOZI_SEED` (`null` when the deal came from the browser),
  read-only data in the same shape as `__WOZI_GEOM`, and a seeded load says so
  once with `console.info`. Both exist for the failure mode this parameter is
  most likely to have — degrading silently with no way to tell whether the seed
  took — and neither is reachable from a phone, which is exactly why no UI
  affordance was added for it: on a seeded load the URL bar already shows the
  seed, and on an unseeded load nothing the page could offer would be the
  machine on screen. A control that hands over a *different* fixed machine is
  not the feature, and it would have cost an `a11y_audit` focusable and a DOM
  invariant to say so.

  Gates: **89 passed, 0 failed** (was 88), `verify_motion` PASS (37/37
  rotating, 8 badges at ≤0.01px, no strands, no console errors), `dom_invariants`
  PASS 4/4 — run with its own injected seed, which is the point,
  `pixel_regress` 0px against `main` at both viewports on both views, `devices`
  24/24 and 4/4.
- **CL#114 — the speed control moved into the pop-out menu, and the corner now
  shows nothing at 1x.** (GitHub #108.) Charles: *"if the speed is 1x nothing
  shows in the upper right, but if someone pops up the menu the slider is at
  the top."* Three decisions, all his: the control is a range input, in the
  menu, above the person picker and the link entries; the corner control shows
  only away from 1x and tapping it resets to 1x rather than cycling; and the
  strobe warning is carried by colouring the thumb itself, not a mark on the
  track.

  **The corner control is a departure indicator now, not a chooser.** All
  actual choosing happens on the slider — `speedFactor()` stays the only thing
  either control reaches (CL#96's invariant, unmoved by *where* the control is
  drawn). The corner's whole job became saying "this page is not running at
  its normal pace" and giving a one-tap way back to 1x, which is a stronger
  idea than a button that is always there saying "1x": its presence is itself
  the information.

  **Removing a permanent button from the middle of a row right-anchored by
  index leaves a gap unless the remaining indices are rechecked.** Speed used
  to sit at index 2 of the corner row (between pause and the menu toggle,
  right-anchored at `(--btn + --btngap) * index` off `--offright`). Simply
  deleting it would have stranded the menu toggle at index 3 with a hole at
  index 2 whenever speed was off 1x and nothing showed there — a gap in the
  middle of the row, not at its end. The menu toggle is renumbered down to
  index 2 instead, closing the gap, and the departure indicator takes the
  outer slot the toggle gave up (index 3) — so showing or hiding it only ever
  grows or shrinks the row from its open end, never reflows a permanent
  button.

  **The strobe warning had already failed once, on the track.** GitHub #69's
  A/B photography tried a 2px accent tick at the first strobing stop and found
  it invisible AT EXACTLY THAT STOP, because the 24px thumb sits centred on
  the very index the tick would mark — visible five stops either side, gone at
  the one that means something. Fixed where it broke: `--thumb-color` is a
  custom property set inline on the `<input>` from render state and read by
  the `::-webkit-slider-thumb` / `::-moz-range-thumb` rules — the mechanism a
  pseudo-element leaves for being reached from a value a pseudo-element cannot
  itself hold a `style` attribute for. The readout text and the track's filled
  portion carry the same colour, so the thumb, the number and the fill all
  flip to `--accent` together at the boundary stop, rather than a mark trying
  to sit on top of the very thing that covers it.

  **The slider steps over `SPEED_STOPS` by index, never continuously**
  (`min=0`, `max=SPEED_STOPS.length-1`, `step=1`) — CL#96's ladder stays a
  1-2-5 ladder under the thumb regardless of how far apart two multipliers sit
  on their own scale, so the absurd top stops stay exactly as reachable as 2x
  is. `input` drives the flywheel live during a drag (the same ~900ms bleed
  that settles a flick carries it to the new pace); `change` is the only thing
  that persists to `localStorage`, so a value merely passed through mid-drag
  never survives a reload.

  **The touch target and the visible control are two different boxes, on
  purpose.** The `<input>` is given an explicit 44px height — the same touch
  target the corner buttons use — while the track it paints stays 4px and the
  thumb stays a 24px disc; `tools/a11y_audit.py` measures the input's box
  (129x44px, comfortably clear of the WCAG 2.5.8 floor), which is not the same
  rectangle as the disc a person sees, and both numbers are worth knowing
  separately rather than assuming they agree.

  **Both harnesses that check fixed controls had to be widened to see a form
  control at all.** `tools/a11y_audit.py`'s focusable selector and
  `tools/devices.py`'s safe-area `ctrls` selector were both `button`-shaped —
  every focusable, fixed control the page happened to contain at the time —
  and neither would have noticed a slider going unmeasured. Both now select
  `input`/`select`/`textarea` alongside `button` explicitly, and
  `devices.py`'s safe-area pass pins speed off 1x and opens the pop-out menu
  before measuring, since both new controls are `display:none` at the shipped
  default and a check run only at that default would never see either one.

  **Widening that selector found a real, pre-existing stranding bug.** The
  pop-out panel (`togPanelStyle`) is vertically centred with no cap on its own
  height, and the Table of Gears list alone — unrelated to this change — is
  595px of content against a 273px-tall iPhone 13/14 landscape window.
  Centred-and-overflowing loses the excess off both edges equally, so the
  panel's first child was pushed to `y = -144px`, entirely above the visible
  area, with no scrollbar to reach it. That child is now the slider, and the
  corner shows nothing at 1x — so on that exact device and orientation there
  was no way at all to reach the speed control. `max-height:calc(100vh -
  var(--offtop) - var(--offbot))` plus `overflow-y:auto` on the panel fixes
  it: `tools/devices.py`'s safe-area pass went from 2/4 to 4/4. The bug
  predates this change; only the harness widening that CL#114 needed to see
  the slider is what surfaced it.

- **CL#107 — a one-link chain's datum carried no scale, because one station is one
  tick and nothing to subdivide.** (GitHub #83.) Minor ticks subdivided the gap
  between a chain's own stations, and Harper's chain has exactly one station: the
  loop struck a single stroke at her only wheel and returned on its first pass.
  A line, a name and one mark is not a scale — it is a hairline that looks like
  one.

  **The scale is the spine's, which is a design call and not a derivation**
  (Charles, GitHub #90 item 5). Every self-referential candidate could give a
  chain marks; only a shared one gives two chains marks that mean the same
  distance, which is what a datum scale is *for*. A machine bed carries one
  scale, not one per part. **It costs something and the code says so**: a
  one-station chain's minor marks reference *another* chain's wheels, which is
  the one thing the rule above them — "the marks cannot drift out of step with
  the wheels they reference, because they ARE the wheels" — does not otherwise
  bend on. That exception is stated in `datumRuns()` rather than glossed.

  **What was derived is the figure itself, and its degenerate case falls out of
  the same arithmetic.** "The spine's station spacing" needed pinning to one
  number, and the obvious one — the mean gap, `span / (stations - 1)` — is
  undefined at exactly the configuration the ticket is about, so a chain that is
  its own spine would have needed a second rule beside the first. Instead the
  spine lends its **station pitch**: the axial length its station pattern
  occupies, over the number of stations occupying it. The extent is measured on
  the pitch circles, leading edge of the first station to trailing edge of the
  last, because that is the circle a mesh's centre distance is set on — so it is
  the projected span plus the two end radii.

  That reading is the spacing, not merely something like it. For stations that
  mesh in a row the span telescopes to `Sum(r_k + r_k+1)` and the extent to
  exactly `2 * Sum(r)`, so the pitch is twice their mean radius — the centre
  distance between neighbours, for wheels of one size. A real serpentine wanders
  off its own axis and the projection shortens it, which is correct: the marks
  are struck along the line, so the scale should measure what the line measures.

  **And at one station the span is zero, the two end radii are the same wheel's,
  and what is left is that wheel's pitch diameter, `MODULE * teeth`** — the first
  candidate on the ticket, arrived at as the *limit* of the third rather than
  chosen beside it. So the objection that a borrowed scale breaks when a chain
  has no spine but itself is answered by the derivation: no branch, no fallback
  constant, nothing to keep in step. The other two halves of that objection were
  never load-bearing — a datum is drawn **only** on a shared stage, so a solo
  host and a lone chain draw no mark at all to need a scale, and `bridge: false`
  changes what *drives* a chain, not what bed it stands on. Both are now run
  rather than argued.

  The one case with nothing in it stays empty: a chain the active config seats no
  service on has no length to measure and no major tick to measure against, so it
  lends `0` — meaning **absent**, and also what keeps the borrowed grid's loop
  finite. Only a chain with exactly *one* station borrows; two or more have a gap
  of their own, and zero has no anchor to phase a grid against.

  Drawn as **minor** marks only — a major tick means a wheel you can reach, and
  this chain has one — phased on that station and run out to the ends of the
  borrower's own assembly, `d0..d1`. The spine lends the spacing and nothing
  else; how far the scale reaches is the borrower's own dimension. The divisor is
  one named `SUBDIV`, read by both the self-subdividing path and the borrowed
  one, so a division here is the same distance as a division there.

  Measured on the shipped stage at 1440×900: Charles's own minor ticks fall
  32–42 px apart as his station gaps vary, and Harper's borrowed grid is a
  uniform **38 px** — inside his range, which is the comparability the whole
  choice was made for. **284 px move in total** (179 at 1440×900, 105 at
  390×844), all of them the new marks; `?who=charles` is untouched, since no
  datum is drawn on a solo stage at all.

  Two suite tests, on real solves: that a one-station chain — bridged *and*
  unbridged — is scribed at the spine's pitch while nothing else is, bounded
  against a ceiling the suite derives for itself rather than against a copy of
  the method's own arithmetic; and that a spine which is its own borrower lands
  on `MODULE * teeth`, with a one-link chain alone on stage drawing no datum at
  all.

  **And one guard had to be repaired to let this be written down at all.** The
  "no literal colours in the datum" assertion was `/#[0-9A-Fa-f]{3,6}|rgb\(/`
  over the whole of `datumLayer()` — and every three-digit decimal is three hex
  digits, so from entry #100 onward the rule forbade the one method it guards
  from *citing the entry that changed it*. A rule that a comment can break is not
  the rule anyone wrote. A literal colour reaches the drawing as a quoted string
  or through `rgb(`; a citation never does, so the pattern now requires the
  quote.

- **CL#106 — which chain is the spine and what order the rest stack in are two
  questions, and the bridges were running the wrong way in portrait.** (GitHub
  #85, GitHub #90 item 4, and a bug Charles found by looking at the page.)

  **The split.** One key did both jobs, and the two agreed only because the sort
  made them agree: sorting by link count named the longest chain the spine as a
  *side effect* of deciding where the others sat. Give Harper eight links and the
  whole composition rebuilds around her, with nothing in `config.js` to say that
  had ever been a choice — the same defect as the old `PEOPLE[0]` hostname
  fallback, a default that works by accident and says nothing about itself.

  Now two independent per-person keys: `spine: true` is **geometry** (it sets the
  scale, and it is the axis every other chain runs parallel to), `order: <n>` is
  **presentation**. `CHAIN_STACK` sorts, `SPINE` is declared, and
  `CHAIN_ORDER = [SPINE, ...stack minus spine]` — so `CHAIN_ORDER[0] === SPINE`
  holds **by construction**, which is what keeps `solve()`'s one-way growth
  invariant true rather than merely likely.

  `WHO` split with it, into `SPINE` (the axis) and `SELECTED` (which person the
  page is *about*, `null` on the combined stage). The analytics beacon had been
  reading the spine and calling it the selection.

  **The fallback sort, Charles's spec:** `order`, then link count descending,
  then **name descending**. Undeclared chains sort to `Infinity`, which is why the
  fallback needs no branch of its own. The name key is where PEOPLE order used to
  be — a tie that held only because `Array.prototype.sort` is stable, which reads
  as no rule at all in the file it governs. The sort is now **total**; nothing
  leans on stability any more, and `PEOPLE` order decides only the picker.

  Deliberately **not** locale-aware: `localeCompare` folds case and accents
  better and would also make the layout depend on the runtime's ICU data. A
  tie-break that comes out differently in two browsers is a drifting constant.

  On the shipped config this is a **zero-pixel change** — Charles has seven links
  to Harper's one, so link count decides before the name key is ever consulted,
  and both declare `order` explicitly anyway.

  **The bug underneath it, which is the part that moved the page.**
  `BRIDGE_BEARING` was made relative to `_axisRot` by CL#67, but its **sign was
  still hardcoded at `+90`** — "down" at rot 0 and **"left"** at rot 90. So in
  portrait the chains stacked leftward off the spine and the spine came out
  **rightmost**. Measured at 390×844 before: Charles x≈290, Harper x≈173.

  The handedness is now derived rather than picked: both candidate bearings are
  evaluated and the one pointing **away from the stage origin** wins, so rank 0 is
  topmost in landscape and leftmost in portrait at any `_axisRot`. After: Charles
  x≈69, Harper x≈321.

  **This is the third failure of the same kind and the second in this one
  constant**, which is why CLAUDE.md now carries a bridge-handedness invariant
  beside the bearing one. Making a value axis-relative is only half the job —
  a *sign* is as screen-absolute as a number of degrees is.

  **Why nothing caught it:** every existing test measured *along* the bridge
  direction, and both mirror images satisfy that. `alongBridge` is now
  `alongCross` and asserts in screen x/y, plus a test named for the requirement.
  Reverting the fix fails two.

  **Two real defects fixed in the inherited implementation**, both found by
  review rather than by the suite:

  - `STACK_AT` accepted `NaN` as a position. `NaN` compares false against
    everything including itself, so the comparator became **non-transitive** and
    the sort's output was undefined — not wrong, *undefined*. Now `isFinite`.
  - The `SPINE` warnings each re-derived their own replacement, so two bad
    declarations at once could print a chain that was not the one used. The
    answer is settled first and both messages read it.

  **Harness narrowed on purpose:** `buildTrain`'s `stack` override is gone. After
  the split every legal layout is expressible as declarations, so the override
  bought only *illegal* trains — a harness able to build what the page cannot is
  a harness that can go green on a page that would not run.

  Suite 79 → 86, every new assertion mutation-verified.

- **CL#105 — the street address is off the site, in all three places it was
  published.** (GitHub #84, and GitHub #90 item 3.)

  **First entry under the new citation style.** Changelog entry numbers and
  GitHub issue numbers had grown into almost exactly the same range — splitting
  GitHub #64 filed tickets at #93-#103 while this file already had entries 93-101
  — so a bare `#97` meant the derived palette *or* the sunburst window count
  depending on which file you were reading. From here new entries are cited
  `CL#NNN` in commit subjects and code comments; the ~100 existing bare `#N`
  references stay as they are, and the break in style is itself a signal about
  which era a reference comes from. GitHub refs keep the `(GitHub #NN)` form.

  The decision that drove the change: **old QR codes must keep working**, so the
  path cannot move. That strikes the unguessable-path and CloudFront-token
  options for as long as printed cards are in circulation, and leaves exactly one
  mitigation that *reduces* exposure rather than relocating it — don't publish the
  address.

  **It was in three places, not one.** The question was posed about the vCard;
  the vCard was the smallest of the three:

  | where | what it was |
  | --- | --- |
  | `cards/charles/contact.vcf` | the `ADR:` line |
  | `cards/index.html` | a visible block printing street, apt, city, state, country |
  | `cards/charles/index.html` | byte-identical copy of the same |

  Removing it from the vCard alone would have left it fully readable on the page
  and exactly as harvestable — the relocate-rather-than-reduce failure the
  decision existed to avoid.

  **The click-to-map handler went with it, and had to.** Both pages carried a
  `<script>` whose only job was `getElementById('address')` plus a listener
  opening Google Maps. Left behind with the block gone it returns `null` and
  throws on `addEventListener` on every card page load — a change that removes
  markup has to remove the script that reaches for it.

  The card still carries name, mobile, email and `wozi.com`.

  Verified after: no occurrence of the street, apt, city or postcode anywhere
  under `cards/`; both card pages still **byte-identical to each other**; both
  still carry `<meta name="robots" content="noindex">`, which matters because the
  deploy's `exact https://wozi.com/cards/ cards/index.html` whole-file hash check
  is the only thing gating those tags. `npm test` green.

  **Unchanged, and stated because it will be asked again:** `robots.txt` is not a
  privacy control and is not being used as one. `cards/` is still not named there
  — naming a path in the one file every scraper fetches first is a signpost, not
  a fence. The live `mailto:` links on the combined stage remain exactly as
  harvestable as before; that was considered and declined on its own merits.

- **#104 — the deploy-whitelist guard read the workflow's prose, so it could not
  fail for the reason it was written.** (GitHub #89, closing the one `survives`
  entry left by #100.) `tools/test.js` asserted `/\bconfig\.js\b/` over the
  **whole** of `.github/workflows/deploy.yml`. `config.js` is named there seven
  times — once in the loop that publishes it, twice in comments about why it
  matters, four times in the live-site checks — so the single edit that restages
  #59,

      -          for f in support.js config.js; do
      +          for f in support.js; do

  left the suite green. The guard against *"the rules requiring a file the rules
  do not name"* was being satisfied by its own explanatory comments. The same
  hole covered `support.js`, `robots.txt`, `ssh_public_key` and `keybase.html`,
  all of which are likewise named in comments and in live checks.

  **A narrower regex would have been the same bug with a smaller window**, so the
  assertion stops reading prose and reads the commands. A publish step is now
  identified by what it *does*: a step whose `run:` block issues `aws s3 cp` or
  `aws s3 sync` with a **destination under `$BUCKET`**. That is the only thing in
  the workflow that puts bytes on the web, and a comment cannot accidentally be
  one. The workflow is split into steps at the `steps:` key, each reduced to the
  shell it actually runs — shell comments stripped, line continuations folded —
  and both whitelist shapes are understood, because a file moving between them
  must not evaporate the guard:

  | shape | how the path is recovered |
  | --- | --- |
  | `for f in support.js config.js; do … cp "$f" "$BUCKET/$f"` | the `for` binding in the same step resolves the variable |
  | `aws s3 cp robots.txt "$BUCKET/robots.txt"` | the literal source |
  | `aws s3 sync assets/ "$BUCKET/assets/"` | a published **directory**, so nothing has to know which icons exist |

  **What must be published is derived, never listed here.** Two sources already
  in the tree: the `<script src="./…">` tags `index.html` carries, and every URL
  the deploy's *own* live-site checks assert is reachable. The second is the one
  that earns its keep — `check https://wozi.com/robots.txt` is the workflow
  stating the file has to be there, so a workflow that checks a file it never
  uploads is #59's shape inside a single file. Between them they require
  `index.html`, `config.js`, `support.js`, `keybase.html`, `ssh_public_key`,
  `robots.txt`, both card pages and a hub icon, with no list typed into the
  suite to go stale.

  Two more assertions, because a whitelist has two ends and a parser has a third:

  - **Every path the deploy publishes exists in the repo.** A publish list naming
    a file the tree does not have fails at run time, against a live bucket, after
    the geometry and both browsers have gone green — and the suite answers it in
    a millisecond.
  - **Nothing it is documented never to publish is in the list** — `legacy/` and
    the repo-root documents. Only checkable once the steps are parsed rather than
    grepped.
  - **A step that copies to `$BUCKET` and yields no path is a failure**, not an
    empty result. That is the parser going blind, which is precisely the fault
    this whole section replaces, so it is asserted rather than assumed.

  **Proved able to fail, in a throwaway `git worktree` at `HEAD`** — never `git
  stash`, which on a clean tree stashes nothing and silently tests the unmutated
  file. Baseline exit **0**; `config.js` dropped from the publish loop, exit
  **1**, naming `config.js (index.html loads it; the deploy asserts it is live)`
  — with the file still spelt seven times in the workflow and the old
  `/\bconfig\.js\b/` still returning `true`; restored, exit **0**. Then the other
  shape: `aws s3 cp ssh_public_key` pointed at the wrong source, exit **1**,
  naming `ssh_public_key`, which is still spelt three times afterwards; restored,
  exit **0**. The two supporting assertions were proved the same way — a
  nonexistent `runtime.js` added to the loop, exit **1**; `CHANGELOG.md` added to
  it, exit **1** — as was the blindness guard, by renaming the loop variable so
  the parser could no longer resolve it: *"a step copies to $BUCKET but no path
  could be read out of it"*, exit **1**.

  **The ratchet was updated rather than deleted.** `tools/mutation_gate.py`
  registered `config-js-off-the-whitelist` as `expect: survives` so that closing
  the gap would report `GAP CLOSED` and force this edit. It is now `expect:
  caught` — the mutant is kept as the standing proof that the gap stays closed,
  which is worth more than removing it — and a second mutant,
  `ssh-key-off-the-whitelist`, covers the individually-copied shape. The suite
  gate: **4/4 caught, 0 known gaps, 1/1 controls green**.

  While in the file: two assertion messages in *a chain that opts out of bridging
  is a root* were the only pair with no word in them marking the sentence as a
  fault — `an unbridged chain claims idlers` and `an unbridged chain is not a
  root` read as flat statements about a healthy tree, unlike their neighbours,
  which carry *"still"* and *"so nothing places it"*. They now say what broke. A
  sweep of every other `ok()`/`eq()` message in the file for the same shape found
  none; the rest already name the fault.

  `npm test` **79 passed, 0 failed** (77 before: one prose-matching test removed,
  three command-reading tests added). Nothing on the deploy path was touched —
  `deploy.yml` is asserted, not edited.
- **#99 — a service owned its URL stem in as many places as there were people
  with an account on it.** (GitHub #70.) Every link carried a whole `href`, so
  `https://github.com/` was written once per person who had GitHub, and the only
  thing keeping two spellings in step was that somebody would notice. Two people
  are on stage today; the duplication was already live, and a third would have
  made three copies of every shared stem.

  `SERVICES` now carries `url` and `path` templates with `{handle}` in them, and
  a link is a slug plus a handle. **The stem belongs to the service and the
  handle belongs to the person**, which is the split `SERVICES` was created for —
  it was always the shared half, and `SITES` was always the personal one
  (`/in/csmarshall` is Charles's, not LinkedIn's). Charles's seven links lost
  fourteen strings and gained seven.

  **Nothing moved.** Every resolved `href` and every engraved band is
  byte-identical for both people — checked by running the real `SITES` builder
  against the config at `HEAD` and against this branch and diffing the two
  tables, which is the only evidence that means anything about a refactor of a
  link table. The pixel gate agrees from the other side: **0 px** at 1440×900 and
  390×844, on `?who=charles` *and* on the combined stage. The commented-out
  Mastodon wheel resolves byte-identically too, uncommented and dumped rather
  than assumed.

  **Three things had to be decided rather than assumed:**

  - **A link that is not a stem plus a handle supplies its own `href`, and that
    href is filled by the same substitution.** So the escape hatch is not a
    second mechanism — it moves where the stem is written, not whether the handle
    has one home. Mastodon is the worked example and is honest about it: the
    instance is part of the account, so there is no stem to share, and
    `mastodon` deliberately has no `url` at all. Its band still comes from the
    service's `/@{handle}`.
  - **`mailto:` is a template like any other**, `mailto:{handle}`, with the
    address as the handle — and the substitution is **literal, never
    percent-encoded**, which is the whole reason it works. Encoding would escape
    the `@` of an address that is legal exactly as it stands, and would have been
    the one change in this branch that moved a byte.
  - **A link that resolves to nothing is left out of the table and named in the
    console.** An `<a href="">` navigates to the current page: it reads as a
    working badge and is not. Left out, the wheel is still dealt and still turns
    with no badge on it — the same unlinked wheel a missing `config.js` produces,
    which every read of that table has been guarded for since #53 and #76.

  **Harper's mail wheel is the reason `path` overrides exist**, and it survived
  this untouched: her handle is *Charles's* address and her band overrides to
  read `harper`. The two halves disagree on purpose (GitHub #65), because
  `config.js` is served to the web and a harvester reads the file rather than the
  artwork. The hazard the templates introduce is a tidy-up — deleting an override
  that looks redundant, then making the handle agree with the band — so the entry
  now says that in as many words, and the suite guards it from the other end: an
  **allowlist of the addresses that may appear in the published config**, which
  names nothing it is protecting and catches any new one arriving by any route.

  Two suite changes were forced rather than chosen, and both were latent faults:

  - **The train length was counted by grepping for `href:`.** It stripped
    comments out of `PEOPLE`, brace-walked it per person and counted a key —
    coupling to the *name of a field* a link happens to carry, and this branch
    took that field off every ordinary link. That count feeds the tooth total, so
    a suite that kept it would have dealt every chain's geometry against a train
    of length **0** and reported nothing. It runs `config.js` now, which is the
    more direct read of the same file and drops the comment stripping with it: a
    retired wheel is commented out rather than deleted, and a comment is simply
    not in the array. The cross-check that used to compare two key-counts now
    walks braces and counts **structure** — objects one deep inside a person's
    own `links` — so it shares no step with the count it is checking and knows no
    key name at all.
  - **A template typo is valid JavaScript**, so `node --check` in CI would pass a
    `config.js` whose GitHub wheel pointed at `github.com/{hadnle}/`. The new
    test runs the page's own `SITES` builder over every person and fails on an
    empty href, an empty band, or a `{` surviving into the output — verified by
    introducing that exact typo and watching it fail, then reverting. It also
    proves its own drop path is not vacuous, with a service that has no `url` and
    a link that has no `href`.

  Seven copies of `new Function('window', CFG_SRC)` in the suite became one
  `loadConfig()` while passing through, for the same reason as the rest of this
  entry.

  Not touched, deliberately: `http://` on the LinkedIn and Instagram stems, and
  the trailing slashes some services carry and others do not. Normalising those
  changes where the links **point**; this changed where they are **written**.
  They are at least in one place to tidy now. The logo half of GitHub #70 needed
  nothing — the icon is fetched at `assets/icons/<slug>.svg` and `BRAND` and
  `PILL_STACK` are keyed by slug, so a mark was never per-person.

  Gates: 71/71 suite (69 before, plus the two above), motion PASS — 37 rotating
  elements all advancing, 8 badges at ≤0.01 px, no console errors past the
  expected favicon 404 — `a11y_audit` PASS in both themes, pixel gate 0 px on
  both the solo and the combined shot.
- **#95 — the datum plate is seated from the start of the mark, not from a wheel
  on it.** (GitHub #87, closing #82 and #77.) Charles: *"seat the datum plate
  25px from the start of the datum line"*. That replaces a rule rather than
  tuning one. The plate rode the **last leading ghost** — the background wheel
  immediately before the first real gear — and a chain with no leading run fell
  back to its own head wheel. Every driven chain has no leading run, because that
  is the end its bridge arrives at, so the fallback was not an edge case: it was
  the rule for everybody but the spine, and on a one-wheel chain the wheel it
  landed on was the whole chain. That is GitHub #82, and it is gone with the
  fallback — the seat has no wheel in it to fall back to and no branch to take.

  **Which "start" it is measured from was the whole of the work.** The ticket
  lists three readings and recommends `d0`, the outermost wheel of the run
  including its background machinery, over the line's first drawn pixel, on the
  grounds that the second makes the plate a function of the window rather than of
  the machine — the property #84 was fixed to remove. Measured, that
  recommendation does not survive its own reasoning, in two separate ways:

  - **`d0` is never on the page.** An escape run is grown until it is 120 px past
    the edge of the viewport — #87 above, the entry, not the ticket — so the
    start of a chain that *has* a leading run is off the page by construction.
    Instrumented at five viewports from 390×844 to 5120×1440, `d0` sat **134 to
    281 rendered px outboard of the near edge on every one**, and the drawn line
    then runs a further two modules beyond it. `plateSeat()` clamps a station
    into the interval where the whole plate is on the page, so a preference
    stated from `d0` would have been overruled on every load ever drawn: a
    constant that never once takes effect, which is worse than no constant.
  - **No referent measured on the machine answers GitHub #82.** A chain with no leading
    run starts its mark *at its own first gear*. Both `d0` and "the first linked
    wheel" put that plate within a wheel's radius of the one wheel the chain
    owns — which is the complaint restated at 25 px, not a fix for it.

  So the mark starts where the **drawing** starts: `Math.min(d0, the drawn area)`
  less the run-out, and the page takes over once that is outboard of the frame.
  One `Math.max`, and the machine still decides wherever the drawing stops inside
  the frame — before the first fit there are no ghosts to widen the drawn area,
  and a chain may be dealt a run that leaves by the far end only. The reasoning
  is the one datumRuns() already states for the cross axis: *off the page is
  invisible, and invisible is the one thing this mark may not be.*

  **`PLATE_START_ALONG = 25`, named for the axis it acts on.** `PLATE_TOP_CLEAR`
  is measured **across** the line, from the chain's extreme border to the top of
  the placard; this is measured **along** it, from the start of the mark to the
  plate's near edge — the plate's own half-width is carried inside `plateSeat()`
  so what the figure names is the gap a viewer can actually see. The two were
  filed as one ambiguous "20px" (GitHub #77) before either was written down, and
  a second bare 20 beside the first would have read as related.

  The line's slab clip moved out of `datumLayer()` into `slabClip()`, because the
  seat and the drawing now have to agree about where the mark starts: a second
  copy of that arithmetic is a plate standing a little way off the end of its own
  line. `plateAt` is gone from the run, and with it the leading-ghost search that
  produced it. The ghosts still record `lead` — the escape-run suite reads it to
  assert that only the spine gets a leading run — but nothing in the page reads a
  ghost's `k` any more, and that field is now dead. It is left alone rather than
  deleted because it is set in `fitEscapes()`, which is not this change's to
  touch; it wants a line of its own.

  **What wins on a narrow screen: the seat.** The figure is a preference; the
  interval in which the whole plate is on the page is not. A page shorter along
  the run than the figure plus a plate pushes the plate *back* toward the start —
  closer in than 25 px rather than hung over the far edge — and the suite asserts
  that direction, because guessing it wrong is invisible until somebody resizes.

  Measured from the DOM after the change: every plate's near edge sits **25.0 px**
  from the near edge of the page along its own line, at 2560×1440, 5120×1440,
  1440×900, 900×1400 and 390×844, portrait and landscape, and none of them
  overlaps a live gear. The combined stage differs from HEAD by **7,248 px**
  (5,593 at 1440×900, 1,655 at 390×844) and the diff is two plate rectangles at
  each viewport — the one they left and the one they arrived at. Nothing else
  moved. `?who=charles` is **0 px**: a solo page draws no datum at all.

  **GitHub #83 is not fixed here, deliberately.** A one-link chain has one
  station, so it gets one major tick and no minor ones, and the design is
  explicit that minor ticks subdivide the gap between stations *"without
  inventing a spacing to give it one"*. Every candidate needs a second choice
  that nothing derives — which gap of the spine's, or how far the marks run on a
  chain that has no gap of its own — and inventing that is the thing an earlier
  mock was rejected for. Nothing was implemented. What this change does do for it
  is remove the aggravation that ticket names: that chain's plate no longer sits
  on the same lone gear as its one tick.

  Gates: 69/69 suite, devices 24/24 and 4/4, motion PASS (37 of 37 rotating, no
  strands, badges at 0 px), pixel gate as above. Looked at in light and dark at
  2560×1440 and 5120×1440, and in portrait at 900×1400 and 390×844.

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

- **#100 — `tools/mutation_gate.py`, which breaks the page on purpose so that
  every other gate has to prove it can fail.** A gate observed green is not a
  gate proven able to fail. This repo has shipped a harness that printed FAIL
  and exited 0, one that had been dead with a `NameError` for weeks, and one
  with no exit code at all — and on a healthy tree all three were
  indistinguishable from a gate that was working, because a working gate and a
  blind gate produce the same output when there is nothing to find. The only
  way to tell them apart is to put a bug in the tree.

  Eight mutations, each a single surgical substitution in one named file, each
  chosen to restage a failure this project has actually had rather than to
  scramble something arbitrary:

  | mutant | file | gate | what it restages |
  | --- | --- | --- | --- |
  | `BAND_DEPTH` 1.59 → 0.50 | `index.html` | `test.js` | #15, and the class `CLAUDE.md` names by hand: the band feeds the bore, and a bigger bore makes gear sets reachable that nothing has measured |
  | a stage host added to a person's `hosts` | `config.js` | `test.js` | the host model's one hard rule — `STAGE_HOSTS` is matched first, so a name in both quietly means *everyone* |
  | `config.js` dropped from the publish loop | `deploy.yml` | `test.js` | #59 — published but unnamed. **This one survives**; see below |
  | `asleep = document.hidden \|\| …` → `asleep = true` | `index.html` | `verify_motion.py` | #7 — the sleep gate latching, and a frozen train photographs perfectly |
  | a hub icon's slug misspelt | `config.js` | `verify_motion.py` | the empty badge: `loadIcons()`'s `.catch` swallows the failure and nothing on the page says so |
  | pill label `13px/1.4` → `13px/1` | `index.html` | `pill_clip.py` | #51, byte for byte — the line box shorter than the ink, so `overflow:hidden` slices the descenders |
  | ghost stroke opacity 0.65 → 0.45 | `index.html` | `pixel_regress.py` | #48's own hand-run proof: geometry identical, train turning, badges centred, type fitting, and the drawing changed |
  | `LINK_SHARE` 0.78 → 0.20 | `index.html` | `devices.py` | #44's collapse and #46's floor — every wheel still meshes and turns, the composition is simply wrong |

  The order is red, then green: each gate's mutants run first and must exit
  non-zero, then the gate runs once more on the restored tree and must exit
  zero. A control that cannot go green voids that gate's whole verdict rather
  than being reported alongside it, and it gets one retry first, because the
  page is dealt at random and a gate that reads the composition can go red on
  whichever machine it was handed (#88).

  **Nothing is mutated in the working tree.** Every run happens in a throwaway
  `git worktree` at `--ref` (`HEAD` by default), thrown away at the end — the
  same shape `pixel_regress` already used, and for a sharper reason than
  tidiness: `git stash` on a clean tree stashes *nothing* and reports success,
  so a stash-based runner silently tests the unmutated tree and passes forever.
  The consequence is stated at startup rather than buried: this gate measures
  the committed tree, and it prints how many uncommitted changes it is
  therefore not testing.

  **It runs in its own workflow, not on the deploy path**, and that is the one
  judgement call here worth arguing with. `deploy.yml` gates a live bucket on
  every push and every pull request; the full sweep is **500s**, of which 414s
  is the device gate alone, run twice — once mutated, once as the control.
  Tripling the latency of a deploy to re-answer a question whose answer changes
  only when a *harness* changes is the wrong trade, and a flake in a second
  browser-heavy job racing the first would block a deploy over something that
  is not about the deploy. So `.github/workflows/mutation.yml` splits it by how
  often the answer can move:

  - **`registry`** — one second, no browser, on every push and pull request. It
    runs the sweep with every gate replaced by one that always exits 0 and
    requires the runner to come back FAIL. That proves the runner can fail, and
    it proves all eight mutations still apply to the files they name, which is
    the one thing ordinary page edits rot silently: rename a constant and the
    mutant stops testing anything while reporting a clean sweep.
  - **`mutate`** — the real 500s sweep. Weekly, on demand, and on a pull request
    labelled `harness`.

  **Proved able to fail in every direction it can fail**, which for this file is
  not optional — a mutation gate that can only pass is precisely the thing it
  exists to prevent. Exit **0** on a working sweep (7/7 caught, 5/5 controls
  green). Exit **1** with `--blind`, every gate stubbed green: 0/7 caught, every
  mutant reported SURVIVED. Exit **1** again on the opposite fault, a documented
  gap that has silently closed. Exit **2** when a mutant's `find` string no
  longer occurs exactly once, naming the mutant and the string — simulated by
  pointing `band-depth-halved` at a constant that does not exist.

  **One mutant survived, and it is kept rather than dropped.** `test.js` asserts
  `config.js` is named in the deploy whitelist — the guard against #59 — but the
  assertion is `/\bconfig\.js\b/` over the *whole* of `deploy.yml`, and
  `config.js` is named there seven times: once in the loop that publishes it,
  twice in comments about why it matters, four times in the live-site checks.
  Delete it from the publish loop and `npm test` stays at **69 passed, 0
  failed**. The guard cannot fail for the reason it was written. It is filed on
  the tracker as issue #89 (the log's numbers and the tracker's are separate
  spaces, and this is one of the places they collide), and it is registered here
  as a mutant expected to **survive** — so the day the assertion is strengthened
  this runner fails with `GAP CLOSED` and the entry has to be removed, instead
  of a stale excuse quietly outliving the defect.

  Two things did not make the set. The issue proposed `TEETH_MAX` 19 → 26 as the
  suite's mutant; it **survives** — the suite simply measures the twentieth
  single-row set that the wider bound reaches, and passes it — which is the
  suite being right rather than blind, so `BAND_DEPTH` took its place. And there
  is no mutant for `a11y_audit.py` or `webkit_band.js`: neither runs in CI, and
  a mutation gate for a gate nobody runs is a longer list, not a better one.

  Nothing on the deploy path was touched. `npm test` is unchanged at 69 passed,
  0 failed.
- **#96 — a gearbox on the corner widget, with a benchmark stop at the top of
  it.** (GitHub #69.) A fourth corner button, between the table of gears and
  pause, wearing its own value instead of an icon: `1×`, and a press moves it to
  the next stop. Eight of them, **1, 2, 5, 10, 20, 50, 100, 200**.

  **Most of it was already built, and the first job was to prove that rather
  than assume it.** `idleRate()` has multiplied by `this.props.speed` for a long
  time, but nothing on the page could set that prop and no measurement had ever
  been taken through it, so "the integrator already honours speed" was a reading
  of the source and not a fact. It is a fact now. The `speed` default was moved
  to `2` in a copy of the document served beside the original, `Math.random` was
  seeded before either page's first script so both dealt the *same* train — tooth
  counts are dealt per load, and rotation rates from two different deals are not
  comparable — and the same 39 rotating elements were sampled over a fixed window
  after the flywheel had settled: **24.4779 → 48.9501 deg/s** on the median, and
  2.0000 on the min and the max as well. The whole train scales by one factor
  because there is one integrator. So the work here was a control, not a
  mechanism.

  ### The stop where it stops being animation

  A gear turning fast enough strobes. Past half a tooth pitch of travel per tick
  the sampling is under Nyquist and the train visibly stands still or runs
  backwards — the wagon-wheel effect — and that is the one high-speed artefact
  that reads as *broken* rather than as fast. The limit is exactly computable,
  and it does not depend on the tooth count at all:

  A wheel's angle is `phase + dir * _M / teeth` and its pitch is `360 / teeth`
  degrees, so **one tooth of travel is 360 master-degrees on every wheel in the
  train**. A 13-tooth blank and a 19-tooth one cover the same fraction of a tooth
  per tick, and there is one strobe speed for the whole machine:

  ```
  master-deg per tick at 1x = (7200 / BASE_MS) * (1000 / frameRate)
                            = 0.342857 * 33.33 = 11.43     (BASE_MS 21000, 30fps)
  tooth fraction per tick   = 11.43 / 360      = 0.0317
  strobe at half a pitch    = 180 / 11.43      = 15.75x
  ```

  Measured, the crossing lands exactly there: 10× covers 0.334 of a tooth per
  tick (67% of the limit) and 20× covers 0.663 (133%).

  **The ladder is allowed past it anyway.** Charles asked for a top stop that is
  "ludicrous", usable "almost … to do benchmarking", so `strobeSpeed()` no longer
  truncates the ladder — it *classifies* it. Every stop at or above 15.75× says
  "strobing — benchmark only" in its accessible name and draws its numeral in
  `--accent` rather than `--muted`. A control that silently hands over a setting
  which breaks the illusion is worse than one that says where the illusion ends.

  ### Why these eight numbers

  A 1-2-5 preferred-number ladder between the schema's `min` and `max`. Equal
  ratios rather than equal increments, because the effect is perceptually
  multiplicative — 1× to 2× and 50× to 100× are the same size of change to look
  at — and 1-2-5 is the standard logarithmic ladder for exactly that: scope
  timebases, chart axes, preferred component values. 1 to 200 gives eight
  positions, which is as many as a cycling button can carry, and **200 is a rung
  of that ladder exactly**, so the ceiling is Charles's number landing on the
  ladder rather than the ladder being bent to reach it. The floor is 1×: the
  control only ever speeds the machine up, because slowing it down was not wanted
  and stopping it is already the pause button's job.

  Nothing about the spacing was picked. `min` and `max` are the only levers, and
  the strobe limit is not written down anywhere — it is a property of `BASE_MS`
  and the frame rate, derived by `strobeSpeed()`, exactly as `gsRender()` reads
  `--gsfit` out of its own CSS declaration rather than keeping a copy.

  ### The benchmark, measured

  Every stop, same seeded deal, 10s windows at 1440×900 in headless Chrome. Ticks
  are counted as `applyRotation()` bursts — `step()` early-returns under its frame
  budget, so rAF callbacks are *not* ticks and counting them would report 60 on a
  page updating at 30:

  | stop | deg/s | ratio | ticks/s | rAF/s | tooth/tick | % of Nyquist | rim px/tick | rim/cap |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | 1× | 24.47 | 1.000 | 28.86 | 59.96 | 0.033 | 6.6% | 0.76 | 0.07 |
  | 2× | 48.96 | 2.001 | 29.37 | 59.98 | 0.065 | 13.0% | 1.49 | 0.14 |
  | 5× | 122.88 | 5.021 | 29.23 | 59.96 | 0.163 | 32.6% | 3.75 | 0.41 |
  | 10× | 244.30 | 9.983 | 28.49 | 59.98 | 0.334 | 66.9% | 7.65 | 0.70 |
  | **20×** | 490.62 | 20.048 | 28.74 | 59.98 | 0.663 | **133%** | 15.23 | **1.57** |
  | 50× | 1226.22 | 50.108 | 28.98 | 60.08 | 1.643 | 329% | 37.74 | 3.43 |
  | 100× | 2452.56 | 100.220 | 28.99 | 59.97 | 3.286 | 657% | 75.46 | 7.15 |
  | 200× | 4895.75 | 200.057 | 29.74 | 59.97 | 6.405 | 1281% | 146.83 | 14.29 |

  **The headline is the column that does not move.** Ticks per second sits at
  28.5–29.7 at *every* stop, 200× included, against a nominal 30. The renderer
  does not care how fast the train is going, and the reason is structural rather
  than lucky: the work per tick is 39 transform writes whatever the multiplier
  is, and speed changes the number written into each one, not the number of
  writes. **Speed is free; only the illusion is not.** The 1.5ms margin in
  `budget = 1000/tickRate - 1.5` was flagged as thin, and it may well be — but no
  stop on this ladder is what makes it thin, and nothing here moved it.

  Two independent limits land in the same gap, which is worth noting because
  neither was fitted to the other. The teeth cross Nyquist between 10× and 20×;
  the rim engraving crosses `rim/cap = 1.0` — where consecutive frames share no
  ink at all and the handle reads as a train of ghosts rather than one moving
  object — between 10× (0.70) and 20× (1.57). Rim travel was measured on the
  wheel the lettering actually sits on, off that wheel's own rotating ancestor
  and its own radius, with the cap converted out of SVG user units by the
  wheel's own viewBox scale. **10× is the last honest stop, by both measures.**

  ### Accessibility, and the one real defect this found

  The numeral is *text*, and axe checks text contrast where it does not check an
  icon's stroke. WCAG asks 4.5:1 of small text and 3:1 of graphics, and `--muted`
  on `--bg` is **3.54:1** — so at 13px the new button **failed** the light-theme
  audit while its three neighbours passed at exactly the same colour. Bold text
  at 18.66px or more is "large scale" and back to a 3:1 threshold, and `--icon`
  is already 20px, so the label is set at `--icon`: the same size as the glyphs
  beside it, clearing the bar by construction rather than by a number somebody
  has to remember. Measured after the change, every stop passes in both themes —
  3.54:1 for the plain stops and 4.69:1 for the strobing ones in light, 6.21:1
  and 7.93:1 in dark. The warning state is the *more* legible of the two, not the
  less.

  The accessible name reports where the machine is, whether that stop strobes,
  and where the next press puts it — "Gear speed 20×, strobing — benchmark only,
  next 50×". A cycling control that reports only its current value tells a screen
  reader user nothing about what activating it does, and the full name is also
  what keeps it unique, which is the check #74 added.

  ### Everything else it touched

  - **`driveCap()`, because a fixed clamp became a brake.** A flick or an arrow
    key was bounded at ±8 master-deg/ms, which stood comfortably while idle was
    0.343 — twenty-three times slower, so the bound only ever caught a violent
    flick. Idle reaches **68.6** at 200×, where a single arrow press would have
    slammed the train from 68.6 to 8 and then climbed back over ~900ms. The bound
    is `max(8, idleRate())` now: a ceiling again at every stop, and identical to
    the old one at 1×.
  - **The choice persists** in `localStorage` under `wozi-speed`, restored before
    the flywheel is seeded so a `spinUp:false` page starts at the chosen rate
    instead of easing up from the default. Bounded by the ladder's own ends
    rather than by numbers written at the read site: `9999` is discarded and the
    button returns to `1×`; `1.25`, which is *between* stops, is kept, because
    `speedIndex()` can always say which stop a value is nearest and offers `2×`
    as the next press. A setting the control cannot leave is the failure worth
    guarding against, not an unfamiliar number.
  - **A dead `speed` read came out of `syncVars()`.** It resolved the multiplier
    on every render and dropped it on the floor — it belonged to the `--s`
    variable deleted in #57 and outlived it. Speed reaches the page through
    `idleRate()` and never through CSS.
  - **`tickRate()` is one home for the update rate.** `step()`'s frame budget and
    `strobeSpeed()` are both computed from it; two copies of `?? 30` would have
    been a control offering stops the renderer had stopped being able to show.
  - **`tools/devices.py`'s comment said "the three corner buttons".** The code
    was always right — it enumerates `button` elements, which is why the fourth
    was measured the moment it existed — but the prose had gone stale.

  The row's arithmetic did not change shape, only length. Each button's `right`
  is its index in whole button pitches — `(--btn + --btngap)` — off `--offright`,
  which already carries the safe-area inset, so a fourth button costs one term
  and no new constant. The table of gears moved from index 2 to 3; pause and
  theme did not move. Three of the four styles are still repeated inline
  verbatim, which remains deliberate. **The speed button's is a render value**,
  and that exception has exactly one reason: its colour depends on state, which
  is the thing the other three do not have.

  Gates: 69/69 suite (unchanged), `verify_motion` PASS, `a11y_audit` PASS in both
  themes — 27 focusables, 0 unlabelled, no duplicate names, 0 targets under
  24×24 — and `devices` 24/24 with 4/4 safe-area, which is the pass that measures
  every fixed control against injected insets and therefore the one a fourth
  control is for. Photographed at all eight stops in both themes. The button box
  is 44×44 at every stop; the widest label, `200×`, renders 45.9px and so sits
  1.9px proud of its own transparent disc, which collides with nothing — its
  neighbours are 20px glyphs centred in 44px discs, leaving 19px of clear space.

  **Not verified:** the pixel gate's stored baseline was not reshot — the control
  is a visible addition to every view, so both the combined-stage and
  `?who=charles` shots necessarily differ from `main`. And the frame-rate figures
  are headless Chrome on an idle workstation, which is the easy case: they say
  the multiplier costs nothing, not that the page holds 30fps on a loaded phone.
- **#94 — the checks only a phone can make, written down instead of remembered.**
  (GitHub #49.) `docs/MANUAL-CHECKS.md`, and it is documentation of a gap rather
  than a new gate: nothing runs it and nothing can.

  Everything in `tools/` is headless Chrome over CDP plus `webkit_band.js`, which
  builds a WKWebView that opens no window. So the directory has no browser chrome,
  no window manager, no battery and no finger, and six questions fall straight
  through it — a URL bar collapsing mid-scroll, rotation with the keyboard up,
  home-indicator and Island overlap, Low Power Mode's rAF throttling, Safari's own
  controls landing on the page's, and whether iOS hands the page the safe-area
  insets `devices.py` has to inject for it. Each entry says what to do, what
  correct looks like, what failure looks like, and — the part worth the file —
  which line of which harness proves the question cannot be automated.

  Two of those are worth naming here because the code already half-answers them
  and the half is easy to mistake for the whole:

  - **The safe-area pass tests the layout consequence, not the insets.**
    `devices.py` sets `--safe-t/r/b/l` itself, from Apple's published figures, and
    measures the fixed controls against the rectangle that produces — because
    Chrome resolves every `env()` to 0 on every emulated device, the insets coming
    from the real window manager rather than the metrics override. The file has
    said so honestly all along; what it could not do is say who checks the other
    half. Now something does, and it says which numbers are the assumption.
  - **Nothing measures the frame *rate*.** `verify_motion.py` samples the DOM
    twice ~700ms apart and reports how many transforms advanced, which is a
    binary a train at 15fps passes exactly as well as one at 30; and
    `pixel_regress.py` cannot ask at all, since it queues rAF rather than running
    it and pins `performance.now` to a virtual clock. That matters under Low Power
    Mode, where iOS is understood to throttle rAF to about 30Hz: the loop's budget
    is `1000/30 - 1.5` = 31.83ms, so a 33.3ms stream clears it on every callback
    and the train should still run at pace — with 1.5ms of margin, and any jitter
    under the budget dropping the tick. Projected worst case is the rate falling
    toward 15fps. Hopefully the margin holds on a real phone; this is arithmetic
    off `index.html:2517`, not a measurement, and check 4 is how it gets one.

  **A repro from a phone is only useful if it can be reproduced, and it cannot
  be yet.** Eleven bare `Math.random()` sites deal the machine, so "it looked
  wrong on my phone" describes a train that will never be drawn again. The
  in-page `?seed=` hook is GitHub #48 part 1 and does not exist — `index.html`
  parses no `seed` parameter, and the determinism both harnesses rely on is
  injected over CDP before page script runs, deliberately out of reach of a
  phone. The file says so rather than implying a hook is there.

  Referenced from `CLAUDE.md` under *Verifying a change*, after the pixel gate.
  Not published: `docs/` is absent from the deploy whitelist and stays absent.

  This is the unblocked half of GitHub #49. **Whether to adopt Playwright is
  Charles's call and nothing here takes it** — no dependency was added,
  `package.json` still has none, and the issue stays open on that question.
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
- **#97 — one colour, and a whole chain made of it.** (GitHub #68.)
  `palette: '#B79CE8'` on a `PEOPLE` entry says "make this person's machine light
  purple", and every wheel on that chain comes out that colour or a near
  variation of it. Harper's chain is purple as of this entry, at Charles's
  request, seeded `#9B8CE0` — the pool's own purple, an authored colour that has
  already been judged good on these wheels. Her chain is one wheel today, and a
  chain of one gets the seed **exactly**.

  **The default palette is untouched.** `WHEEL_POOL` is still authored, still
  ground truth, and `dealColours()` is the function that shipped, line for line —
  a chain with a seed is taken out of that deal altogether rather than changing
  how it works. Saying so plainly because the history invites the opposite
  reading: five attempts at deriving the *pool* from a formula were all worse and
  that is settled (#40). This derives **one person's opt-in family from a colour
  they chose**, which is a different question with a different answer.

  **The hard problem was #12, and it did not survive contact with the
  requirement.** The 40-degree minimum hue separation between meshing wheels is a
  proxy for "a viewer would call these the same colour", and it is a good proxy
  exactly while hue is the axis carrying the difference. A single-colour family
  has no hue difference by construction, so that rule would reject every possible
  arrangement. The obvious repair is to re-express #12 perceptually — OKLab, one
  rule everywhere, separation carried by whichever axis is available.

  **Measured on the shipped pool, that repair is not available, and the numbers
  say so plainly.** In OKLab the closest pair the 40-degree rule *allows* into
  mesh is `#9B8CE0`/`#DB79B8` at ΔE **0.117**; the two blues the rule exists to
  keep apart, `#4A90E2`/`#8CB8F2`, are **0.135** apart and the two greens
  **0.168**. A single ΔE floor would have to be at or below 0.117 to leave the
  pool dealable and above 0.135 to go on rejecting the blues. No such number
  exists — on this pool the two metrics disagree about which pair is closer, and
  swapping one for the other would seat the exact pair #12 was written for.

  So the rule is stated once and **measured twice**, by whichever axis the
  palette actually varies on: *no two meshing wheels may be ones a viewer would
  fail to tell apart*. A pool-dealt chain varies by hue and is judged in degrees.
  A single-colour chain varies by lightness and chroma and is judged in OKLab.
  Neither is ever relaxed, and they are never both applicable — every meshing
  pair in the deal belongs to one chain and therefore to one palette, because a
  chain head past a bridge meshes an idler rather than another chain. The suite
  asserts the contradiction that justifies keeping two rules, so the day the pool
  changes enough for one to do it is the day a test says so.

  **What varies, and how far.** Lightness does most of the work; chroma follows
  it, held at the seed's own fraction of what the sRGB gamut allows at each
  lightness, which is how a tint behaves and which cannot leave the gamut by
  construction. Hue moves a little and deliberately — `MIN_HUE_SEP / 2` across
  the whole ramp, half the angle at which this page already calls two hues
  different colours — because a family with no hue movement reads as
  machine-generated tints of one swatch. The ramp only opens as far as the wheel
  count needs: a short chain stays near the colour that was asked for.

  **Every bound is something the pool already reaches**, so the rule is always
  "no worse than a wheel that ships" rather than a number somebody picked:

  - the **tonal envelope**, measured through the same `flatTones()` the page
    draws with, in *both* themes — body luminance 0.240–0.566 light, 0.261–0.576
    dark. No derived wheel may be lighter than the lightest that ships or darker
    than the darkest.
  - the **engraving margin** — `FLAT_INK` at its own opacity must reach at least
    2.61:1 light and 2.75:1 dark over the body, which is what it reaches over the
    worst pool wheel. A pale family is exactly where that gets thin.
  - the **spacing it aims for** — ΔE 0.117, the closest this page has ever put
    two meshing wheels, so a chain short enough to afford it is spaced exactly as
    widely as a pool deal.
  - the **floor it must clear** — the ΔE between a wheel's body and its own
    raised face, the smallest tonal step this artwork already asks every viewer
    to see, measured per seed on the colour actually drawn.

  **The arithmetic, and what happens past it.** The legible band around
  `#B79CE8` is ΔE 0.191 deep, so the wheels are `span/(n-1)` apart and the seed
  holds **9** wheels before the closest pair drops under its own floor. Seven
  wheels leave 0.0281 against a floor of 0.0198; ten leave 0.0190 and the console
  says so, naming the seed, both numbers and the real capacity. The chain is
  still drawn — one that is absent is worse than one that is subtle — but it is
  never drawn while claiming the spacing held. Capacity across the seeds
  photographed runs 7–14, and it is **asked rather than predicted**:
  `floor(path / faceStep) + 1` is the right way to think about it and is off by
  one on real seeds, because the ramp is a curve through a gamut boundary rather
  than a straight line.

  **Three failures were built and then measured out**, each caught by a test
  written before the fix:

  - The band is walked at the seed's hue and the ramp does not stay there.
    `#F2C14E` put its top rung at 0.573 luminance against a ceiling of 0.566,
    because the hue it drifted to carries more chroma and therefore more light.
    Every legibility question is now asked at both edges of the widest wander the
    ramp can ask for, and the colours actually handed out are the thing checked.
  - A seed can be outside the envelope itself. `#7E57C2` is an ordinary purple
    that lands darker than any wheel that ships, and every wheel of the chain
    came out the identical colour. It is not refused — "pick another one" is a
    poor answer to a child who picked this one — the anchor is slid to the
    nearest lightness that works and the console names both hexes.
  - Taking the chroma fraction at the colour as written rather than at the slid
    anchor turned a pale cream into a saturated amber: near white the gamut is
    narrow, so a faint chroma is a *large* fraction of it.

  A seed at or below the chroma the background machinery is drawn at (0.0181) is
  refused outright: the bridge idlers are grey, and a chain that grey reads as
  structure rather than as somebody's — the #65 blank-gear defect arrived at from
  the other side. A seed paler than the palest wheel that ships is lifted to it.
  A named CSS colour is refused with a message: `rgbOf()` is the one parser here,
  and a format it cannot read is one that cannot be taken into OKLab at all.

  `FLAT_INK` moved up beside the palette because the legibility envelope is now
  its earliest reader, and the engraving's opacity became `ENGRAVE_ALPHA` rather
  than a literal in two places that could drift apart. `MIN_HUE_SEP` is named
  rather than a bare 40 for the same reason.

  Gates: 74/74 suite (five new), `a11y_audit` PASS in both themes,
  `verify_motion` PASS. Photographed as a sweep — seven seeds and the pool deal,
  the same machine under each, both themes, plus one seed at 4, 7, 10 and 14
  wheels so the floor can be seen running out.

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

- **#101 — the gear menu named the mechanism instead of the thing being chosen.**
  (GitHub #91.) The first entry read `Mixed deal (default)` while every other entry in
  the list is a plain family name — `Isogrid`, `Radial brickwork`, `Radial isogrid` — so
  "deal" was the one word describing how the wheels are picked rather than what you get.
  Now `Mixed (default)`.

  The `(default)` marker stays. It is the only thing in the menu that says which entry
  you get without asking, and it is what `aria-current` is paired with, so dropping it
  would take information out of the accessibility tree as well as off the page.

- **#98 — one name was doing two jobs: a maximum was being used as an index.**
  `SPINE_LEN` was `Math.max(1, ...STAGE.people.map(p => p.links.length))` — the
  longest chain *anywhere on stage* — and the `TRAIN` builder then used it as a
  **wheel index into the spine**, `Math.floor((SPINE_LEN - 1) / 2)`, to seat the
  default bridge anchor. Those two quantities agree only while the spine *is* the
  longest chain, which today's `CHAIN_ORDER` sort happens to guarantee. The
  guarantee lived in a different declaration from the index it was propping up,
  which is the whole of the defect: nothing at the point of use said what it
  depended on, and the thing it depended on was free to change.

  Found while reading #85, which proposes **declaring** the chain order instead
  of inferring it from link count. **That design fork is not decided and nothing
  here decides it** — the sort is untouched, no config key was added, and the
  suite's deliberate `CHAIN_ORDER is not longest-first` assertion still runs
  against its three-chain fixture at both stage rotations. Only the latent bug
  is fixed, because a declared order is exactly what makes a short spine
  reachable and the fix is a prerequisite either way.

  The two quantities are now named apart and each derived from what it actually
  means:

  - **`SPINE_LEN` — how many wheels the spine has.** `SPINE.links.length`, where
    `SPINE` is the first chain in `CHAIN_ORDER` that `HAS_WHEELS`. It is a count
    of one chain, never a maximum, and it is only ever used to index that
    chain's own wheels.
  - **`NOMINAL_CHAIN` — the longest chain configured anywhere.** Unchanged, and
    already sitting further down the file: it is the maximum-shaped quantity,
    and the one that genuinely sets the SCALE (`NOMINAL_SPAN` derives from it,
    `TARGET_GEAR_PX` from that). It ranges over every configured person rather
    than the stage precisely *because* it indexes nothing — a solo page has to
    draw its wheels at the size they have on a chain that is not on stage to be
    measured.

  The index is now in range **by construction rather than by a promise made
  elsewhere**, and the argument is local to the line: the emitter skips chains
  with no wheels and emits `SPINE` first, `SPINE` is the first chain in that very
  order with wheels, and the spine is unbridged so it takes no idlers — its
  wheels therefore *are* `out[0 .. SPINE_LEN-1]`. Half of `SPINE_LEN-1` lands on
  one of them whatever the order is sorted by. The "a chain with no links is not
  laid out" rule got one home, `HAS_WHEELS`, since the spine is defined by it and
  two copies of that test is how the emitter and the spine would come to disagree.

  **Proved by construction rather than asserted.** The new test hands the real
  `TRAIN` builder a layout order the page's own sort would never produce — a
  two-wheel spine with a seven-wheel chain behind it — which is the shape #85
  would make legal. The suite's `buildTrain` grew an optional order for this, and
  substitutes *only* `CHAIN_ORDER`; `SPINE` and `SPINE_LEN` are still the page's
  own lines deriving their own answer from it. Against the old derivation the
  test fails, with the anchor landing on the bridged chain's own idler and
  forward-referencing a wheel that is not placed yet:

  ```
  FAIL  the static tree's default bridge anchor is a spine wheel, whatever the layout order
        long's bridge defaults to wheel 3, which is a ghost idler -- the spine is wheels 0..1
        long's bridge defaults to wheel 3, which is not placed when idler 2 asks for it
  ```

  Against the new one it passes, with the anchor at wheel 0. The fixture also
  checks *itself*: it asserts the discarded `max`-over-stage index would have
  been out of range, so the test cannot quietly stop exercising the bug.

  **Nothing on screen moved, and nothing was ever going to.** `solve()`
  overwrites this parent with whatever it finds room for before a wheel is drawn,
  so this is the *static* tree only — but a malformed static tree is exactly what
  #65 was, and the failure mode is silent: `solve()` reads `g[t.parent]` out of
  the wheels it has already placed, so a forward reference reads `undefined` and
  the branch lands wherever the last iteration left it.

  Gates: **70/70** suite (69 baseline plus the new test), devices **24/24** and
  **4/4**, motion PASS (39 of 39 elements advanced, no strands, which is correct
  for the direct-mesh train). The pixel gate is the one that matters for a
  renaming: **0 px** against HEAD at 1440×900 and 390×844, on `?who=charles`
  *and* on the combined stage. On today's config the new derivation and the old
  one compute the same number, so identical output is the expected result and not
  a lucky one.

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
