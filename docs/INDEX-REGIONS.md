# index.html regions — what can be held at once, and what cannot

`index.html` is 9,844 lines and one file, and that is the whole of GitHub #113's
remaining cost. Costs (1) and (2) are closed with numbers — brotli is live at
198,588 bytes, HTML parse is 7ms unthrottled — and neither of them made the file
any easier to work on concurrently. Roughly a dozen open tickets edit it, so they
are dispatched in waves.

This is the cheap answer the ticket asked for: **a map, so concurrent work can be
dispatched along boundaries that already exist, without splitting anything.** It
is not a fix and it does not make the file smaller. Read the last section before
treating it as one.

**Two claims are kept apart throughout, because they are different claims.**

- **Textually independent** — two agents edit both regions and `git merge`
  produces no conflict markers.
- **Semantically independent** — neither edit can silently change what the other
  one draws or measures.

A clean textual merge that breaks a derived constant is the dangerous case: it
lands, it looks fine, and the only thing that objects is a screenshot nobody
took. Every region below is scored on both.

---

## 1. The region map

Line numbers are HEAD as of 2026-08-11 and **will drift**. They are anchors for
reading, not identifiers — a dispatch brief should name the region and its
anchor symbol (`gearSvg`, `SPINDOWN_*`, the `<style>` block), never a bare line
range, or the brief goes stale the first time anything above it grows.

### The document, before any script

| # | lines | region | what it is | depends on |
| --- | --- | --- | --- | --- |
| **R1** | 1–13 | real `<head>` | charset, viewport, the two `<script src>` tags | load ORDER is load-bearing: `config.js` must precede `support.js` |
| **R2** | 14–35 | `<helmet>` | font preconnects, the two theme-aware SVG-data-URI favicons, `/favicon.ico` fallback, `<title>` | nothing in the file. The favicon glyph is a baked path — it does **not** re-read `font-family` |
| **R3** | 36–276 | the `<style>` block | see breakdown below | — |
| **R3a** | 37–149 | light palette tokens | `:root` — `--ref-bg`, `--ink`, `--muted`, sizing tokens, `--safe-*` env() reads | read by `syncVars`, `datumOpacity`, `datumInk` via `getComputedStyle` |
| **R3b** | 150–157 | dark overrides | `:root[data-theme="dark"]` | aliases R3a's `--ref-bg-dark`; must not re-declare colours |
| **R3c** | 158–164 | base element rules | `html,body`, `a`, the `:focus-visible` ring (#23) | R3a tokens |
| **R3d** | 165–237 | range-input pseudo-elements | the ONLY non-inline styling in the file, and the only pseudo-element rules. Reads `--thumb-color` set inline by `renderVals` | R5's `speedTrackStyle` / `wearTrackStyle` |
| **R3e** | 238–270 | "WHAT YOU CAN EDIT WITHOUT DOING GEOMETRY" | prose only — the existing partial ancestor of this document, in a CSS comment | — |
| **R3f** | 271–275 | media queries | reduced-motion, three viewport token steps | R3a |
| **R4** | 279–424 | the template markup | the corner row (four buttons, right-anchored by index), the pop-out `<nav>`, the stage, the wordmark. `{{ }}` holes only — every value comes from `renderVals` | **every** `{{ name }}` must exist in R46, `renderVals`'s return object |
| **R5** | 426–464 | the shipped-layer-defaults comment | prose describing what `data-props` means | — |
| **R6** | 465 | `<script type="text/x-dc" data-props="…">` | **the prop schema, as one HTML attribute.** `speed.min`/`max` here are the two ends of the stop ladder | nothing — but a great deal depends on IT (see §3) |

### The script, top level (466–3616)

| # | lines | region | what it is | depends on |
| --- | --- | --- | --- | --- |
| **R7** | 466–573 | `?seed` prologue | `SEED_MAX`, `DEAL_SEED`, the LCG install over `Math.random` | reads `location.search` only |
| **R8** | 574–717 | geometry constants | `MODULE`, `TOOTH_PA/ADD/DED/THICK/FILLET`, `BOSS_MUL`, `BAND_DEPTH/RISE`, `RIM_UNDER_BAND`, `BASELINE_MID`, `ENGRAVE_*`, `TOOTH_ROOT_MIN`, `RING_STUB`, `LIST_ROW_FONT`, `WEAR_SCUFF_RATIO` | nothing. **Everything else depends on these** |
| **R9** | 718–962 | time, speed and coast | `BASE_MS`, `PROP_SCHEMA`, `SPEED_FLOOR/CEIL`, `strobeSpeed()`, `SPEED_STOPS`, `SPINDOWN_*`, `approachSpeed()` | R6's attribute (via `PROP_SCHEMA`), `BASE_MS` |
| **R10** | 963–1088 | ghost palette + APCA | `GHOST_COLORS`, `GHOST_GROUNDS`, `GHOST_OFFSET_L`, `GHOST_LIGHT_PAINT`, `lstarOf`, `apcaLc` | R3a/R3b hexes by value, not by reference |
| **R11** | 1089–1141 | plane-geometry primitives | `polarR`, `polarD`, `segCross`, `segDist`, `ENDS_APART`, `CLEARANCE` | `MODULE` |
| **R12** | 1142–1206 | config binding + hostname resolve | `CFG`, `CONF`, `STAGE`, `SELECTED` | `config.js` (`STAGE_HOSTS`, `PEOPLE`) |
| **R13** | 1209–1443 | the chain tree | `CHAIN_PARENT`, `CHAIN_TREE`, `CHAIN_ORDER`, `DRIVE_FROM`, `SPINE`, `CHAIN_RANK`, the three refused mistakes, `order`/name tie-breaks | R12 |
| **R14** | 1446–1592 | datum + idler budget constants | `DATUM_PLATE`, `PLATE_TOP_CLEAR`, `PLATE_START_ALONG`, `MIN_IDLERS`, `MAX_IDLERS`, `IDLERS_FOR`, `ORIGIN_MOUNT` | `MODULE` |
| **R15** | 1594–1744 | `TRAIN` and its indexes | the dealt wheel list, `BRIDGE_FROM`, `BRIDGE_HEAD`, `ORIGIN_OF`, `HEAD_OF` | R13, R14 |
| **R16** | 1745–2256 | tooth deal + family menus | `TEETH_MIN/MAX/MEAN`, `dealTeeth`, `dealAngles`, `enumeratePlanetaries`, `planetaryBore`, `RAVIGNEAUX_MENU`, `planetaryMenuFor`, `MIN_MODULE`, `CENTRE_FAMILIES`, `CANDIDATE_FAMILIES`, `FORCE_KIND` | R8 (all of it) |
| **R17** | 2257–2272 | the `?hud` gate | `HUD`, `HUD_MS`, `HUD_WINDOW` | `location.search` |
| **R18** | 2273–2660 | the fit maths | `dealCentres`, `smallestBlankHolding`, `ANG_MIN/MAX`, `STEP_DRIFT_MAX`, `endsCapFor`, `NOMINAL_SPAN`, `LINK_SHARE`, `WHEEL_SPAN`, `TARGET_GEAR_PX`, `STAGE_CROSS` | R8, R15, R16 |
| **R19** | 2661–2771 | the epicyclic re-seat | `CENTRE_DEAL`, then the pass that moves an epicyclic onto a blank that can hold it | R16, R18 |
| **R20** | 2772–2781 | analytics beacon | `AN`, `track()` | `CONF.ANALYTICS`, `SELECTED` (**not** `SPINE`) |
| **R21** | 2782–3205 | the colour layer | `hueOf`, `WHEEL_POOL`, `dealColours`, the whole OKLab stack, `POOL_ENVELOPE`, `TONE_AIM`, `faceStep`, `familyFor`, `capacityOf`, `PALETTE_SEED` | `CONF.WHEEL_POOL`, R10 |
| **R22** | 3207–3280 | the colour deal | `DEALT`, `WHEEL_DEAL`, `POOL_DEAL`, per-chain seeded families, the console warning | R21, R15 |
| **R23** | 3281–3385 | config-derived content | `PAIR_SLOTS`, `PAIRS`, `SINGLES`, `PILL_STACK`, `BRAND`, `ACCENTS` | `config.js` |
| **R24** | 3386–3536 | ink, cut floors, contrast | `MIN_CUT_PX`, `MIN_CUT_LO/HI`, `EPI_LINE_OP`, `BADGE_DISC`, `flatTones`, `ENGRAVE_STROKE`, `shades`, `relLum`, `rgbOf`, `contrastAt` | R21 |
| **R25** | 3537–3616 | link table + escape constants | `SITES`, `badgeKey`, `BOOST_REF_PX`, `TIGHT_REF_PX`, `ESCAPE_*` | R23 |

### `class Component` (3618–9841)

| # | lines | region | what it is | depends on |
| --- | --- | --- | --- | --- |
| **R26** | 3618–3665 | state + instance fields | `state`, `_M`, `_v`, `_badgeOff`, the HUD counters, the two refs | R17 (`HUD` sizes `_tickDt`) |
| **R27** | 3666–3948 | input handlers | `onGrab`, `badgeGrab`, `motionActive`, `rnd`, and the speed accessors `tickRate`/`driveCap`/`speedStrobes`/`speedFactor`/`layerOn`/`speedIndex`/`rateAt`/`idleRate` | R9 |
| **R28** | 3949–4153 | chain axes + datum runs | `chainAxes`, `datumRuns` | R13, R11 |
| **R29** | 4154–4484 | `fitEscapes` | the escape-run solver, seeded with `solved.bridgeRuns` | R25, R11, `solve()` |
| **R30** | 4485–4552 | `applyRotation` | one clock → every transform, and every strand's `stroke-dashoffset` | R26 |
| **R31** | 4553–4697 | `startPhysics` — the rAF loop | `step()`, the integrator, the sleep gate, the frame budget | R9, R27, R30 |
| **R32** | 4698–4970 | the `?hud` panel | `hudTick`, `hudMount`, `hudSample` | R17, R26 — **but its call sites are inside R30/R31** |
| **R33** | 4971–5073 | small utilities | `textWidth`, `loadIcons`, `axisRot`, `idlerCount`, `gsRender` | R18 |
| **R34** | 5075–5370 | `fitStage` | the four fit terms, `visualViewport`, `--gsfit` | R18, R33 |
| **R35** | 5371–5483 | lifecycle | `componentDidMount`, `componentDidUpdate`, `componentWillUnmount`, `syncVars`, `apply` | R3a (via `getComputedStyle`), R32, R34 |
| **R36** | 5484–6332 | `solve()` | wheel placement, bridges, origin runs, `BRIDGE_BEARING`, the attachment search, the overlap report | R13, R14, R15, R18 |
| **R37** | 6333–6348 | `wearWheels` | picks the two marked wheels, once per solve | R36 |
| **R38** | 6349–6457 | `engraving` | the band, the handle and stamp type sizes | R8 |
| **R39** | 6458–6534 | `teethPath` | the tooth profile and the ONE fracture shape (`chipIdx`/`chipSev`) | R8 |
| **R40** | 6535–6740 | wheel-level helpers | `arcD`, `ringPath`, `ghostOpacity`, `wheelOpacity`, `datumOpacity`, `datumInk` | R3a, R10, R24 |
| **R41** | 6741–6867 | `ghostSvg` | the background-palette wheel — reads neither `kind` nor `arms` | R40, R39 |
| **R42** | 6868–8360 | **`gearSvg`** | the artwork. 1,493 lines. Breakdown below | R8, R24, R38, R39 |
| **R43** | 8361–8460 | `chainEl` | the dormant chain/belt strand builder | R11 |
| **R44** | 8461–8919 | the datum stack | `plateMetrics`, `plateMargin`, `datumClear`, `slabClip`, `plateAir`, `plateExcluded`, `plateNearestClean`, `plateSeat`, `datumLayer` | R14, R28, R40 |
| **R45** | 8920–9443 | `renderVals` body | the layer assembly: `gearArt`, `wheels`, `ghosts`, `links`, `togPeople`, the row-metric derivations | almost everything above |
| **R46** | 9444–9841 | **`renderVals`'s return object** | every `{{ name }}` R4 can reference. 398 lines of one object literal | R45 |

### Inside `gearSvg` (R42)

The family branches are one `if / else if` chain, which is why they merge
cleanly — and they all read the same locals declared above them, which is why
that is only half the story.

| lines | what |
| --- | --- |
| 6868–7091 | **the shared preamble** — `px()` (6887), `MIN_CUT` (6892), `LATTICE_WALL` (6901), `POLARBRICK_ASPECT_MAX`, `shades`/`flatTones` calls, `faceR`/`wellR`/`hubR`, `timingMark`, `nearestEdge`, `amShells`, `slots`, the wear/character chip selection |
| 7092–7096 | `spokes` |
| 7097–7101 | `pockets` |
| 7102–7173 | `holes` |
| 7174–7187 | `ring` |
| 7188–7378 | `planetary` / `ravigneaux` — the two families that DRAW rather than cut |
| 7379–7400 | `iris` |
| 7401–7417 | `star` |
| 7418–7470 | `honeycomb` |
| 7471–7773 | `hexcore` |
| 7774–7884 | `isogrid` |
| 7885–7965 | `polarbrick` / `polariso` |
| 7966–8041 | `labyrinth` — retired and unphotographable |
| 8042–8064 | `geneva` |
| 8065–8142 | `sunburst` |
| 8143–8360 | **the shared epilogue** — `lineWork`, `knurl`, the tooth stroke width, the clipped group, the evenodd body path, the cut contours drawn OUTSIDE the clip |

---

## 2. Which regions are genuinely independent

### Textually AND semantically independent — hold these concurrently

Verified against history where history had something to say (§5).

- **R2, the `<helmet>`.** CL#151 (`1f5159f`) changed the favicon and touched
  **line 20 and nothing else** in the entire file. The one caveat is documented
  in CLAUDE.md and is not a coupling: the favicon's "w", both SVGs' "w" and
  `engraving()`'s lettering are three independent facts, so a font change in one
  does not reach the others — which is exactly what makes R2 safe to hold.
- **R7, the `?seed` prologue.** Reads `location.search`, installs an LCG, and
  nothing downstream names it.
- **R17 + R32, the `?hud` panel.** `HUD_MS`, `HUD_WINDOW`, `hudTick`,
  `hudMount`, `hudSample` — but see the caveat below; the panel is independent,
  its *instrumentation* is not.
- **R20, the analytics beacon.** Ten lines, one config read, one `sendBeacon`.
- **R43, `chainEl`.** Dormant. Nothing invokes it while no `TRAIN` entry carries
  a `link`.
- **R3f, the media queries.** Three token steps, no JS reader.
- **Any single family branch inside R42** against **any other single family
  branch** — `hexcore` (7471–7773) against `sunburst` (8065–8142) is a genuine
  concurrent pair, provided neither touches the shared preamble. That proviso
  disqualifies most real family work; see §3.

### Textually independent, semantically NOT — the dangerous set

These merge clean and can still change each other's output:

- **R3a/R3b (palette tokens) against R10 (ghost palette) against R40
  (`datumOpacity`, `datumInk`).** The tokens are read at runtime by
  `getComputedStyle`, and the ghost alphas are *solved* by matching one theme's
  prominence against the other's. CL#140 (`aa54185`) is the proof: one ticket,
  hunks at 57, 139, 887, 6239 and 6438 — token, dark block, ghost constants and
  two render sites, because they are one fact spread across four regions.
- **R24 (`MIN_CUT_PX = 10.3`) against R42's `sunburst` branch.** The constant's
  own comment states where the number came from: *"`sunburst` never cuts below
  7.41 solve units, measured where `--gsfit` is 1.396."* Edit `sunburst`'s cut
  sizing and `MIN_CUT_PX` becomes a figure with no surviving derivation, with
  nothing anywhere reporting it.
- **R9 against R6.** `SPEED_STOPS`, `strobeSpeed()`, `driveCap()` and the whole
  coast model derive from `PROP_SCHEMA`, which is parsed out of an HTML
  attribute on line 465. Widening `speed.max` in the markup silently relays the
  ladder, the strobe boundary and how long a throw coasts.
- **R16 (`MIN_MODULE`, `planetaryBore`) against R8.** A bigger bore makes gear
  sets reachable that nothing has measured — CLAUDE.md's own warning, and the
  reason `npm test` must be re-run after any R8 edit.
- **R4 (markup) against R46 (return object).** A `{{ name }}` with no key
  renders empty. Neither half fails; the page just draws a control with no
  label.

---

## 3. The coupling that defeats naive parallelism

### 3.1 R8 is a fan-out, not a region

`MODULE` is referenced at 55 sites spanning almost every region in the file —
242, 265, 574, 695, 1103–1125, 1454, 1771–1875, 2040–2060, 2417–2598, 4372–4535,
5061, 5671–6030, 6367, 6459, 6856–6951, 8365–8807, 8997, 9165. `TOOTH_ADD` at 14
sites, `TOOTH_DED` at 7, `BAND_DEPTH` at 10, `RIM_UNDER_BAND` at 5 (including a
CSS comment), `MIN_MODULE` at 6, `TEETH_MAX` at 21.

`BOSS_MUL` is the clearest single case. It is one line (609) and CL#149
(`d66773b`) — the commit that gave `hubR * 1.5` its one home — landed **fifteen
hunks**: 556, then 6859, 6872, 7147, 7164, 7217, 7291, 7520, 7631, 7705, 7781,
7804, 7815, 7848, 7881. That is the constants block plus most of `gearSvg`'s
family branches at once. **A constants-block ticket is not a small ticket; it is
a whole-file ticket wearing one line.**

Two constants are pleasantly bounded and worth naming as the exceptions:
`LATTICE_WALL` (6 sites, all inside `gearSvg`) and `MIN_CUT_PX` (2 sites).

### 3.2 `tools/test.js` reads this file by text, from everywhere

`tools/test.js` extracts **66 distinct `grabBlock` anchors** and **13
`grabNumber` names** out of `index.html`, plus the `data-props` attribute
directly (`test.js:1550`). The anchors reach into R8, R9, R11, R12, R13, R15,
R16, R18, R21, R24, R25, R28, R29, R33, R34, R36, R38, R42, R44 and R46 — which
is to say, nearly the whole map. This is deliberate and CLAUDE.md defends it:
the suite measures what actually ships. It is also the single largest hidden
coupling, and #101 is the standing warning about how fragile it is.

Three failure modes, in increasing order of nastiness:

- **`grabNumber` throws on ambiguity, which is the good case.** Since CL#112 it
  counts assignments in the comment-stripped source and refuses when there is
  more than one. So introducing a second `MAX_IDLERS = …` anywhere in the file
  fails `npm test` loudly. That is a merge hazard, not a silent one.
- **`grabBlockFrom` takes the FIRST `indexOf(decl)` with no ambiguity check and
  no comment stripping** (`test.js:101–109`). An anchor string that comes to
  appear earlier in a comment is silently matched instead. Anchors like
  `'gearSvg(g, S) {'`, `'  solve() {'` and `'const NOMINAL_SPAN ='` are prose-shaped
  enough that this is reachable by accident.
- **It balances braces by counting characters**, so a brace inside a comment or a
  string within the extracted block silently truncates or over-extends it.
  `grabBlock('gearSvg(g, S) {', '{', '}')` spans 1,493 comment-dense lines on
  that basis.
- **Two-space indentation is part of several anchors** (`'  solve() {'`,
  `'  applyRotation() {'`, `'  renderVals() {'`, `'  datumRuns(solved, ghosts, S) {'`).
  Re-indenting a method breaks its extractor.

And the markup tests match exact inline-style strings — for instance
`right:calc(var(--offright) + (var(--btn) + var(--btngap)) * 2)` for the menu
toggle's index-2 slot (`test.js:1425`), and `display: speedNow === SPEED_FLOOR ? 'none' : 'flex'`
(`test.js:1413`). Reformatting R4 or R46 for readability fails tests in a file a
different agent may be holding.

**The practical consequence:** `tools/test.js` is *co-contended*, not
independent. **16 of the last 30 commits to `index.html` also edited it.** Two
agents holding two disjoint `index.html` regions frequently both want
`tools/test.js` as well, which re-serialises them through the back door.

`CHANGELOG.md` is worse — **29 of 30** — which is why `tools/changelog_merge.py`
exists and why the orchestrator should write the entry rather than the agent.

### 3.3 `renderVals` is a shared surface, by design

R46 is one 398-line object literal, and every control feature adds keys to it.
Recent evidence, from the hunk starts of each commit:

| change | hunks in `renderVals` |
| --- | --- |
| CL#155, Speed/Wear labels (`b617d0f`) | 9342, 9450, 9486, 9608, 9676, 9696, 9717 |
| CL#154, three style layers (`f25de06`) | 9645 |
| CL#153, Wear slider (`93bd1a1`) | 9183, 9202, 9355, 9469 |
| CL#144, menu control surface (`dc3958f`) | 8813 |
| CL#142, per-mesh flywheel (`6391ec5`) | 8868 |

There is no partition of it to hand out. Two control tickets both add a row's
`style`, `label`, `readout` and handler keys to the same literal, and the row
metrics they derive (`rowLabelMinWidth`, `rowAntiOverlapGap`, `ROW_PAD_Y`,
`PANEL_GAP`, at 9406–9440) are shared arithmetic, not per-row values. **This
region is a lock, not a lane.**

R4 travels with it: the markup carries the `{{ }}` holes and the four corner
buttons are right-anchored *by index*, so adding or removing a permanent control
renumbers its neighbours. CL#155 and CL#154 both edited R4 (lines 369/378 and
380/463) *and* R46. Run concurrently they would have conflicted twice.

### 3.4 The `?hud` panel reports on the loop, so it reaches into it

R32 is self-contained; its counters are not. `_tickN`, `_tickDrop`, `_tickDt`,
`_rafN`, `_paintN`, `_hudAsleep` are written from inside `applyRotation` (4514)
and `step()` (4618–4634), and wired up in `componentDidMount` (5415) and
`componentWillUnmount` (5456–5457). So a HUD ticket and a physics ticket collide
in R30/R31 even though the panel itself is elsewhere — and `_hudAsleep`
deliberately *mirrors* the sleep gate's expression rather than re-deriving it,
which means a change to that gate has to be made in two places on purpose.

### 3.5 `gearSvg`'s shared preamble is where family work actually lands

The branch structure suggests eleven independent lanes. History says otherwise.
CL#138 (`566a2d7`) was scoped to `hexcore` and `labyrinth` and still landed
hunks in the preamble at 6979–7055 — because holding a family to `MIN_CUT`
*means* editing `MIN_CUT` and `LATTICE_WALL` where they are declared. CL#157
(`678f0a4`) reached 6966, 7334 and 7372 in `gearSvg` **and** 8231, 8246 in the
datum stack, from one ticket about timing marks.

**One agent at a time in `gearSvg`.** The branch boundaries are real, and they
are not where the work falls.

---

## 4. The dispatch rule

Mechanical enough to apply without re-reading this document.

### Step 1 — classify the ticket by the widest region it must touch

| the ticket touches | verdict |
| --- | --- |
| R8 (`MODULE`, `TOOTH_*`, `BAND_*`, `RIM_UNDER_BAND`, `BOSS_MUL`), or R16's `MIN_MODULE` | **exclusive.** Takes `index.html` alone, and `tools/test.js` with it |
| R46 / R45 (`renderVals`) or R4 (markup) | **exclusive over the control surface.** No other control ticket concurrently |
| R42 (`gearSvg`), any part | **exclusive over the artwork.** No other family or cut ticket concurrently |
| R6 (`data-props`) or R9 (`BASE_MS`, `SPEED_*`, `SPINDOWN_*`) | **exclusive over speed.** Nothing touching R27, R30, R31 or the speed keys in R46 |
| R36 (`solve`), R13, R14, R15, R18 | **exclusive over layout.** Nothing touching R28, R29, R34 or R44 |
| R3a/R3b, R10, R24, R40, R21 | **exclusive over colour.** These four are one fact in five places (CL#140) |
| only R2, R7, R17+R32, R20, R43, R3f, or exactly one non-shared method | **concurrent-safe** |

### Step 2 — check the second file

If two candidates both need `tools/test.js`, they are **not** concurrent unless
their tests are pure appends at different points in that file. Assume they are
not. `CHANGELOG.md` is written by the orchestrator, never the agent.

### Step 3 — the honest count

**Two agents on `index.html`. Sometimes three.**

Not more, and the reason is not the map — the map has 46 regions. It is that the
five exclusive scopes in Step 1 cover the regions real tickets are about, and
they overlap each other: the speed scope reaches `renderVals`, the artwork scope
reaches the datum stack, the colour scope reaches the style block and the render
sites, and any constants ticket reaches all of them.

The realistic concurrent shapes, worth stating as recipes:

1. **One implementation lane + one read-only lane.** Always available, always
   safe. Audits, measurement, `docs/`, screenshots, `?hud` readings — no
   isolation needed, unlimited count. This is the parallelism that is actually
   free, and it is under-used.
2. **Two implementation lanes when their scopes are disjoint in Step 1** and only
   one needs `tools/test.js`. Verified by history: CL#136 (coast, hunks 3314 and
   3376) and CL#138 (lattices, hunks 1804–8394 but none between 3097 and 6272)
   ran as two branches and merged at `fe1cbba` with **zero conflicts in
   `index.html`**.
3. **A third lane only if it is confined to R2, R7, R20, R43 or R3f** and needs
   neither `tools/test.js` nor `renderVals`. In practice that is a favicon
   ticket or a beacon ticket, not a feature.

Everything else stays in waves, and the map's contribution is that the wave
boundaries can now be drawn before dispatch rather than discovered at merge.

---

## 5. What history said

Checked against `git log` and the actual hunk positions of the last 30 commits
to `index.html`, plus the four merge commits in that range.

**The map's central claim is confirmed by a real parallel merge.** `fe1cbba`
merged CL#136 (the coast model) with CL#138 (every lattice held to `MIN_CUT`).
Their hunks against the merge base `e9de32b`:

- CL#136 — 3314, 3376. Region R9.
- CL#138 — 1804–1874, 3041–3096, 6273–8394. Regions R16, R24, R42.

Replaying the merge with `git merge-tree` gives **one conflict, and it is in
`CHANGELOG.md`.** `index.html` merged clean, 218 lines of separation at the
closest approach. The other three merges in range (`c3c9d77`, `46759a5`,
`e9de32b`) produce zero conflicts in any file. **Two agents did hold this file at
once and it worked — and the thing that fought was the changelog, which is
exactly what `tools/changelog_merge.py` was later written for.**

**Single-region commits exist and match the map.**

- CL#151 (`1f5159f`), the favicon — **line 20 only**. R2 alone.
- CL#131 (`19a10e1`), the light background stepping to 88% L — **line 42 only**.
  R3a alone.
- CL#147 (`5706b3d`), escape ghosts driven by their own flywheel — **one hunk**
  at 4316. Inside R29/R31.
- CL#152 (`975c737`), the datum plate — 8224–8695. R44 alone, nine hunks, no
  reach outside it.

**Where the map would have been wrong, and it is worth naming.**

- **A colour ticket is not a palette-region ticket.** CL#140 (`aa54185`) touched
  57, 139, 887, 6239 and 6438. A naive reading of the map — "R3a is small and
  isolated, hand it out" — would have permitted a concurrent ghost-palette or
  `datumOpacity` edit, and the merge would have been clean while the two themes
  stopped being reflections of each other. This is why §2 lists R3a in the
  dangerous set rather than the safe one, and why Step 1 has a single colour
  scope covering five regions.
- **A "one constant" ticket fans out.** CL#149 (`d66773b`) is fifteen hunks from
  a single-line change. CL#150 (`51cebde`), the unnamed-constants sweep, is
  twelve hunks across 1638–7722. Anything phrased as *"give X one home"* is a
  whole-file ticket.
- **Sequential commits that would have collided.** CL#155 and CL#154 both edited
  R4 (369/378 vs 380/463) and R46 (9342–9717 vs 9645). They shipped one after the
  other. Dispatched concurrently they would have conflicted in two places — and
  that is the pair most like the tickets still open, since both are control-surface
  work.
- **A family-scoped ticket reaches the shared preamble.** CL#138's hunks at
  6979–7055 are in `gearSvg`'s preamble, not in `hexcore`'s branch. The
  eleven-lane reading of R42 is wrong in practice.

No case was found where the map forbids a pair that history shows merging
cleanly. The errors all run one way — the map is optimistic about small regions
whose *meaning* is spread wider than their lines — which is why §2 splits
textual from semantic independence rather than reporting one verdict.

---

## What this does not solve

Say this out loud, because a map reads like a fix and this is not one.

- **It does not make the file smaller, faster or easier to read.** 9,844 lines
  before, 9,844 after. Cost (2) already established that the size is not a
  performance problem; this does not revisit that.
- **It does not raise the concurrent ceiling much.** Two, sometimes three. The
  dozen tickets still go in waves; the map only means the waves can be composed
  in advance instead of discovered when a merge fails.
- **It does not remove the `tools/test.js` coupling** — it only names it. That
  coupling is deliberate and defended in CLAUDE.md, and until #101's extractor
  is scoped or anchored, it stays a hidden edge between every region and one
  other file.
- **It does not detect a violation.** Nothing enforces this document. No gate
  reads it, no test asserts a region boundary, and the line numbers drift the
  first time anything above them grows. It is a briefing aid whose only reader
  is whoever is dispatching, and a stale region table is worse than none because
  it reads as authoritative.
- **It does not settle whether the file should eventually be split.** Option 4 in
  #113 remains open on its own terms. If anything, the map is an argument for
  *where* a split would fall naturally — the artwork, the solver, the control
  surface — but the constraints that make a split expensive (no build step, the
  extractor, inline styling, byte-identical deploys) are all still standing.
- **It cannot promise the semantic verdicts are complete.** §2's dangerous set is
  what was found by reading references and checking 30 commits. A coupling that
  no recent ticket happened to exercise would not have shown up, and the honest
  expectation is that at least one more exists.
