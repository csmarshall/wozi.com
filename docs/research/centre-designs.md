# Centre Design Pool — Research & Proposals

Research report for new decorative gear-centre kinds for the wozi.com gear train.
No repository files were changed. All geometry is expressed in the codebase's own
terms: the annulus between `hubR` (inner) and `wellR` (outer), the shared `MODULE`
constant (`m = 7` px in the shipped train), the `PT(rad, deg)` polar-point helper,
and openings pushed as **closed subpaths** onto `holes[]` for the even-odd fill
(index.html ~lines 932–1027). Existing kinds: `spokes` (circumferential kidney
slots between arms), `holes` (drilled circle ring), `pockets` (wider kidney
slots), `ring` (plain ring + 5 relief holes), `spiral` (scroll-chuck slots, 1.15
turns).

Scale context: shipped wheels are 14–18 teeth → pitch radius `r = m·teeth/2` =
49–63 px, so the centre annulus runs roughly **hubR ≈ 8–16 px to wellR ≈ 29–43
px** — a radial depth of only ~15–30 px. That thinness is the dominant design
constraint: shapes need to read at a band about 2–4 modules deep, viewed at
roughly 120–260 px wheel diameter.

---

## Part 1 — What the real world offers, and what survives at 120–260 px

**Machinist flywheels.** Cast flywheels used curved or S-shaped spokes because
straight spokes cracked as the casting cooled — the curve flexes instead of
tearing ([Model Engineer forum](https://www.model-engineer.co.uk/forums/topic/curved-flywheel-spokes/),
[HMEM forum](https://www.homemodelenginemachinist.com/threads/curved-flywheel-spokes.3279/)).
Visually, 5–6 curved spokes read beautifully at small sizes: the eye gets both the
opening shape and a sense of implied rotation direction. Straight-spoke
handwheels (3 spokes + rim) also read instantly. **Reads well small.**

**Lathe chucks / faceplates.** Scroll chucks are already taken (the `spiral`
kind). Faceplates contribute a different motif: radial T-slots and drilled bolt
circles — sparse, chunky, unambiguous
([Wikipedia: lathe faceplate](https://en.wikipedia.org/wiki/Lathe_faceplate)).
Chunky slots survive small scale; fine bolt patterns do not.

**Horology.** Skeleton watches cut plates and bridges into flowing openwork where
the bridge shapes guide the eye ([Wikipedia: skeleton watch](https://en.wikipedia.org/wiki/Skeleton_watch),
[TrueFacet guide](https://www.truefacet.com/guide/skeletonized-watches-the-ultimate-guide/)).
Balance wheels — a heavy rim on two or three thin crossing spokes — are the
strongest small-scale motif horology offers: almost all rim, almost no web.
Geneva/Maltese-cross wheels (radial slots + concave locking arcs between them)
are instantly recognisable machine iconography
([Wikipedia: Geneva drive](https://en.wikipedia.org/wiki/Geneva_drive),
[Firgelli mechanism note](https://www.firgelliauto.com/blogs/mechanisms/maltese-cross-mechanism)).
**Both read well small; fine skeleton filigree does not.**

**Bicycle disc rotors and chainrings.** Rotors combine two vocabularies: rings of
small drilled holes, and short *angled* slots (tilted off-radial), often with
curved struts joining the braking band to the hub spider — some are explicitly
designed as graphics ([BikeRadar rotor guide](https://www.bikeradar.com/advice/buyers-guides/disc-brake-rotors),
[US patent 2013/0032439 "Disk rotor with graphical structural elements"](https://patents.justia.com/patent/20130032439)).
The angled-slot ring is distinctive and survives small scale if slots stay ≥
0.5 m wide. Chainring spiders (4–5 broad arched windows) also scale down well.

**Iris / aperture mechanisms.** 5–11 overlapping curved blades around a central
opening; the aperture polygon's shape comes from the blade count, and blades are
curved to keep the opening round ([camera-wiki: Diaphragm](https://camera-wiki.org/wiki/Diaphragm),
[rp-photonics: diaphragms](https://www.rp-photonics.com/diaphragms.html)). The
*look* — tangentially-tilted crescent leaves converging on the hub — is unlike
anything in the current pool. **Reads well at 6–8 leaves; 11 gets mushy small.**

**Turbines / impellers.** Backswept centrifugal impeller vanes follow logarithmic
spirals, r = e^(θ·cot β) ([Brennen, *Hydrodynamics of Pumps* ch. 2](http://brennen.caltech.edu/HTMPUM/chap2.htm),
[log-spiral blade profile](https://www.researchgate.net/figure/Blade-profile-of-logarithmic-spiral-method_fig3_347892543)).
A short sweep (60–100°) reads as "fan/turbine" where the existing 1.15-turn
scroll reads as "spiral" — related but distinct silhouettes. **Reads well at
5–9 vanes.**

**Gothic tracery / rose windows.** Wheel windows are literally this problem:
radial mullions, foiled circles, trefoil and quatrefoil openings, cusped arches
([Wikipedia: quatrefoil](https://en.wikipedia.org/wiki/Quatrefoil),
[Wikipedia: trefoil](https://en.wikipedia.org/wiki/Trefoil),
[Chiffriller, *Tips & Tricks to Gothic Geometry*](http://westongeometry.pbworks.com/w/file/fetch/62270876/TIPSTRICKS.pdf)).
Pointed-arch (lancet) windows arranged radially survive small scale very well —
the cusp/point is legible even tiny. Full multi-order tracery does not.

**Art Deco / Jugendstil.** The sunburst: radiating rays alternating long/short,
diverging from a central disc ([awedeco: sunburst motif](https://awedeco.com/sunburst-motif-in-art-deco/),
[Wikipedia: sunburst](https://en.wikipedia.org/wiki/Sunburst)). Perfectly
rotational, perfectly parametric. **Reads well if ray count stays ≤ 16.**

**Hypocycloids / spirograph.** Hypotrochoids x = (R−r)cos t + d·cos(((R−r)/r)t)
produce n-petal rosettes when R/r is coprime ([mathcurve: rose](https://mathcurve.com/courbes2d.gb/rosace/rosace.shtml),
[Chalkdust: spirographs](https://chalkdustmagazine.com/regulars/on-the-cover/on-the-cover-spirographs/)).
Full multi-loop spirographs alias badly small; a *single-lobe-order* rose
boundary (r(θ) = a + b·cos nθ) is the usable extraction — smooth, closed,
non-self-intersecting when b < a. **Rose boundary reads well; true multi-pass
spirograph curves do not.**

General small-scale rules that fell out of this survey:

- Feature width below ~0.5·m (3–4 px) stops reading as a cut and starts reading
  as noise; the codebase already guards for this (`if (wSlot < 6) return`).
- 3–9 repeats of a bold element beat 12+ repeats of a fine one.
- Concave corners (cusps, notches) are cheap legibility — they say "machined"
  even at 20 px.
- Shapes owning a full annular band read stronger than shapes floating in one.

---

## Part 2 — Proposed designs

Conventions used below:

- `m` = `MODULE`. `mid = (hubR + wellR) / 2`. `depth = wellR - hubR`.
- All angles in degrees, using the existing `PT(rad, deg)` helper; π-free arc
  commands as in the current `slots()` builder.
- Every opening is one **closed subpath appended to `holes[]`**; the page shows
  through via the existing even-odd fill. Decorative strokes (struck edges) go on
  `inner[]` exactly as the spiral kind does.
- Every design should carry the existing guard style: if `depth` is too small for
  the motif, degrade (fewer repeats, or fall back to plain ring). Suggested
  guard noted per design.
- All are n-fold rotationally symmetric, so they are balanced in motion by
  construction.
- Strobe note baseline: the train turns slowly (a fraction of a degree per
  frame), so classic wagon-wheel aliasing is mild; the real risk is *shimmer* —
  many fine elements crossing the anti-aliased threshold at once. Keep repeat
  counts ≤ 12 and feature widths ≥ 0.5·m and none of these will strobe.

---

### 1. `flywheel` — S-curved spokes
**One-liner:** Classic cast-iron flywheel: 5–6 gently curved spokes, the
openings between them broad curved-sided windows, whole web implying a direction
of turn.

**Recipe.** Openings are the gaps between n curved spokes. Model each spoke
centreline as a radial line sheared by a constant angular *sweep*: a point at
radius fraction f sits at angle `base + sweep·f`. Each opening is the region
between two adjacent spoke edges plus inner/outer arcs:

```
n      = arms (5 or 6)
sweep  = 28..40 (deg of shear hub→well; sign sets handedness)
halfW  = spoke half-width in deg at mid radius ≈ (0.5·m / mid)·180/π  · wScale
rIn    = hubR·1.35 ; rOut = wellR - 0.6·m
edge(k, side, f) = PT(rIn + (rOut-rIn)·f,  k·(360/n) + sweep·f + side·halfW·(1/ (0.6 + 0.4·f)))
   // spokes taper slightly: wider at hub than at rim, like a casting
subpath k: M edge(k,+1,0)
           L… edge(k,+1,f) for f = 0..1 in 10 steps      (leading spoke's edge)
           A rOut arc CCW to edge(k+1,-1,1)              (outer window sill)
           L… edge(k+1,-1,f) for f = 1..0 in 10 steps    (trailing spoke's edge)
           A rIn arc CW back to start ; Z
```
Polyline edges (10 steps) are plenty at this size; the codebase's spiral already
does exactly this. Struck edge: restroke the leading polyline at strokeWidth 1.4,
opacity 0.5, like `spe` in the spiral kind.

**Tunables:** `arms` 4–6; `sweep` 20°–45°; taper ratio 1.0 (none) – 1.8;
`wScale` 0.8–1.4. Guard: `depth < 2.2·m` → drop taper and reduce to arms 4.

**In motion:** the curve makes rotation direction legible at a glance — the
wheel looks like it is "pulling". No strobe risk (n ≤ 6, broad openings). If
`sweep` sign is randomised, half the pool will appear to lean against its true
rotation, which is charming rather than wrong (real engines ran flywheels both
ways — [Smokstak thread](https://www.smokstak.com/forum/threads/flywheel-rotation.187845/)).

**Difficulty:** Easy-medium. Two polyline edges + two arcs per opening; no
self-intersection possible while `sweep·(1) + 2·halfW < 360/n`.

---

### 2. `iris` — aperture leaves
**One-liner:** Six to eight crescent-shaped openings tilted tangentially around
the hub, like the gaps between camera aperture blades converging on a lens.

**Recipe.** Each opening is a *lune*: the area between two circular arcs sharing
endpoints. Place n lunes with n-fold symmetry:

```
n     = leaves (6..8)
p0    = PT(hubR·1.45, k·360/n)                  // inner tip
p1    = PT(wellR - 0.5·m, k·360/n + skew)       // outer tip, skewed tangentially
skew  = 34..55 deg — this is what makes it an iris and not a spoke wheel
chord = |p1 - p0|
Rb    = chord / (2·sin(bulge))   // arc radius for each side, from bulge half-angle
subpath k: M p0
           A Rb,Rb 0 0 1 p1     // shallow side (bulge small)
           A Rc,Rc 0 0 1 p0  Z  // return arc, Rc < Rb so the two arcs enclose a crescent
```
Concretely: side 1 uses `bulge₁ ≈ 18°`, side 2 (returning) uses `bulge₂ ≈ 34°`
on the same chord — the enclosed lens is their difference, a curved blade-gap.
Both arcs bow the *same* direction (sweep flag 1 both ways, different radii),
producing the crescent. Non-intersection between neighbours is guaranteed while
`skew + widthAngle < 360/n` where `widthAngle ≈ 2·(bulge₂ - bulge₁)`.

**Tunables:** `n` 5–9; `skew` 30°–60°; `bulge₂ − bulge₁` 10°–22° (crescent
fatness); tip radii ±0.3·m. Guard: `depth < 2·m` → reduce bulges (thinner
crescents) rather than dropping leaves.

**In motion:** exceptional — the tangential tilt gives a strong pinwheel read,
and because every leaf is identical the figure is perfectly balanced. Mild
shimmer only if n ≥ 10 with thin crescents; keep n ≤ 8.

**Difficulty:** Medium. Two arcs per opening, but getting the two `bulge` values
tuned so crescents neither collapse nor overlap needs one session of eyeballing.

---

### 3. `geneva` — Maltese-cross web
**One-liner:** The metal left behind forms a Maltese cross: n radial slot
openings with parallel flanks and rounded outer ends, plus concave arc bites in
the cross's shoulders between them.

**Recipe.** Two families of openings, both n-fold (n = 4 or 6):

```
Family A — radial slots (the pin slots of a Geneva wheel):
  w   = slot half-width = max(0.35·m, depth·0.10)
  rI  = hubR·1.5 ; rO = wellR - 0.4·m
  at angle a = k·360/n:
    stadium: two lines parallel to the radial at ±w (offset perpendicular),
    from radius rI to rO, capped with semicircle radius w at rO
    and a flat or semicircular cap at rI.
    (Same construction as slots() but radial instead of circumferential:
     corners at PT-with-perpendicular-offset; 4 commands + 2 caps.)

Family B — shoulder bites (the locking-disc concaves):
  at angle b = (k + 0.5)·360/n:
    circle of radius cR = depth·0.30, centred at PT(wellR + cR·0.15, b) —
    i.e. deliberately overlapping wellR so only a concave bite intrudes…
```
…but a plain circle poking past `wellR` would escape the annulus. Keep it legal:
centre the bite circle at `PT(wellR - cR·1.05, b)` with `cR = depth·0.28`, fully
inside — it reads the same. Emit each circle with the two-arc closed-circle
idiom already used by the `holes` kind.

**Tunables:** `n` 4 (canonical) or 6; slot width factor 0.08–0.14 of depth;
bite radius 0.22–0.32 of depth. Guard: `depth < 2.5·m` → drop family B.

**In motion:** the cross silhouette is the star; strong 4-fold symmetry gives a
crisp, slightly mechanical "indexing" feel as it turns. Zero strobe risk.

**Difficulty:** Easy. Both families are shapes the codebase already knows how to
emit (stadium slots, two-arc circles).

---

### 4. `honeycomb` — hex port ring
**One-liner:** A single orbit of 6–9 regular hexagonal openings, flats aligned
tangentially — a drilled-hole ring gone angular.

**Recipe.**
```
n      = ports (6..9)
orbit  = mid
hexR   = min(depth·0.36, (π·orbit/n)·0.42)   // circumradius; caps by both depth and pitch
for k in 0..n-1:
  c = PT(orbit, k·360/n)
  vertices v_j = c + hexR·(cos(k·360/n + 30 + j·60), sin(…))   // point-out orientation,
  subpath: M v_0 L v_1 … L v_5 Z                               // rotated with the orbit slot
```
Rotating each hexagon by its own orbital angle (the `+ k·360/n` inside the
vertex angle) keeps the pattern n-fold symmetric — every port presents the same
face to the centre. Counter-bore ring accent: stroke a hexagon 1.3·hexR at
opacity 0.4 on `inner[]`, mirroring the `cb` circles of the `holes` kind.

**Tunables:** `n` 6–9; `hexR` scale 0.30–0.40 of depth; orientation point-out vs
flat-out; optional second inner orbit of tiny hexes (only when `depth > 3.5·m`).
Guard: `hexR < 0.6·m` → fall back to `holes`.

**In motion:** polygonal corners catch the eye more than circles do, giving a
subtle sparkle as vertices rotate through the vertical-light highlight. n ≤ 9
keeps it below shimmer threshold.

**Difficulty:** Easy. Pure polygon emission; hardest part is the sizing cap.

---

### 5. `rosette` — petal web (rose-curve cut)
**One-liner:** Solid metal petals radiate from the hub inside a circular
opening — the cut is the space between a wavy rose-curve boundary and the well
circle, leaving a flower silhouette attached to the hub.

**Recipe.** One opening, two subpaths, even-odd does the rest:

```
n      = petals (5..8)
a      = hubR·1.35 + 0.5·(wellR - 0.5·m - hubR·1.35)   // rose mean radius
b      = (wellR - 0.5·m - hubR·1.35)·0.5·0.85          // rose amplitude, b < a - hubR·1.35
subpath 1 (outer boundary of the cut):  full circle radius wellR - 0.4·m
                                        (two-arc closed circle idiom)
subpath 2 (inner boundary = the petals): polyline over t = 0..360 step 5:
    r(t) = a + b·cos(n·t)
    M PT(r(0),0) L PT(r(5),5) … Z
```
The region between the circle and the rose curve is cut through; the petal metal
stays joined to the hub (rose min radius `a − b` > hubR·1.35), the rim metal
stays joined at `wellR` — nothing floats, and the two subpaths cannot intersect
because `a + b < wellR − 0.4·m`. This is the single-lobe-order extraction of the
hypotrochoid family ([mathcurve rose curves](https://mathcurve.com/courbes2d.gb/rosace/rosace.shtml)).
Struck edge: restroke the rose polyline on `inner[]`.

**Tunables:** `n` 5–8; amplitude ratio b/(a−hubR) 0.6–0.95 (spiky ↔ gentle);
optional phase-offset second harmonic `+ 0.15·b·cos(2n·t)` for a Jugendstil
lean. Guard: `depth < 2.2·m` → reduce b; below 1.6·m → fall back to `ring`.

**In motion:** the smooth wave gives an organic, almost liquid rotation — the
only fully-curvilinear organic form in the pool. No strobe risk; the boundary is
one continuous curve.

**Difficulty:** Easy. One polyline + one circle; the constraint arithmetic is
three lines.

---

### 6. `magstar` — star truss
**One-liner:** A straight-edged n-point star of metal spanning hub to well, the
openings the concave triangular bays between star points — BMX mag wheel /
sheriff-badge geometry.

**Recipe.** n bays, each bounded by two straight star edges and an outer arc:

```
n     = points (5..7)
rTip  = wellR - 0.4·m          // star tip radius (tips touch the well ring)
rVal  = hubR + depth·0.22      // valley radius (star waist)
tip_k    = PT(rTip, k·360/n)
valley_k = PT(rVal, (k+0.5)·360/n)
bay k: M tip_k
       L valley_k
       L tip_{k+1}
       A (wellR-0.4·m) arc back (sweep 0, i.e. CCW along the well circle) to tip_k ; Z
```
Each bay is a closed "bow-tie-free" triangle-with-arc; neighbours share only the
tip *points*, never edges, so even-odd stays clean. Widen the star arms by
pulling `tip` and `valley` each into two points ±halfW degrees apart if the
knife-edge tips look too sharp at small sizes (recommended: halfW ≈ 2–4°).

**Tunables:** `n` 5–7; valley ratio 0.15–0.35 of depth (fat ↔ skeletal star);
tip/valley half-width 0°–5°. Guard: none needed beyond global `depth` floor —
the shape degrades gracefully.

**In motion:** the boldest silhouette in the pool; straight edges sweeping past
the vertical light give a clean heliograph flash once per point. n ≤ 7 → no
strobe.

**Difficulty:** Easy. Two line segments and one arc per bay.

---

### 7. `labyrinth` — staggered arc gallery
**One-liner:** Two concentric rings of curved slots, the outer ring offset half
a pitch from the inner — a labyrinth-seal / phonograph-groove rhythm of dashes
circling the hub.

**Recipe.** Reuses the existing `slots()` circumferential-stadium construction
twice at different radii:

```
n        = slots per ring (4..6)
bandW    = depth·0.26                       // radial width of each slot band
g        = depth·0.16                       // radial gap between rings
ring 1 (inner): slots(n, hubR·1.4,          hubR·1.4 + bandW·2, armDeg≈10, wScale≈0.9)
ring 2 (outer): same but rIn = hubR·1.4 + bandW·2 + g, rOut = that + bandW·2,
                and every angle offset by 180/n   // the half-pitch stagger
```
(`slots(arms, rIn, rOut, …)` already produces rounded-end circumferential
stadium cuts centred at `(rIn+rOut)/2`; call it with the phase offset added to
`a0/a1` — a one-argument extension.)

**Tunables:** `n` 4–6; bandW/g ratio; stagger 180/n (canonical) or randomised
±20%; 3 rings instead of 2 when `depth > 4·m`. Guard: `depth < 3·m` → single
ring (which is close to `spokes` — so at small depth prefer another kind).

**In motion:** the two counter-phased rings create a beautiful moiré-free
"breathing" rhythm — bridges of one ring align and un-align with slots of the
other as it turns. This is the most motion-dependent design in the set: it looks
plain in a still and comes alive spinning. Shimmer risk only if 3 thin rings are
used on a small wheel.

**Difficulty:** Easy. It is two calls to a helper that already exists.

---

### 8. `rotor` — angled brake-rotor slots
**One-liner:** A ring of short stadium slots tilted ~35° off-radial, optionally
alternating with small drilled holes — slotted-and-drilled disc rotor.

**Recipe.**
```
n     = slots (6..9)
tilt  = 30..45 deg off the radial
len   = depth·0.62 ; hw = max(0.35·m, depth·0.09)   // slot half-length, half-width
for k: c   = PT(mid, k·360/n)
       dir = unit vector at angle (k·360/n + 90 - tilt)    // tilted from tangent
       e0 = c - len·dir ; e1 = c + len·dir
       stadium subpath: line e0→e1 offset ±hw, semicircle caps radius hw
         (M e0+p·hw  L e1+p·hw  A hw cap  L e0-p·hw  A hw cap Z, p = perpendicular)
optional drilled holes: circle radius 0.55·hw at PT(mid, (k+0.5)·360/n)
```
Clamp: `len` such that both endpoints satisfy `hubR + hw < |e| < wellR − hw`
(shrink `len` until true) — that keeps every cap inside the annulus.

**Tunables:** `n` 6–9; `tilt` (sign randomised = handedness); holes on/off;
slot slight curvature (bow each long edge with a large-radius arc) for the
premium-rotor look. Guard: `depth < 2·m` → holes-only (falls back toward
`holes` kind, so prefer other kinds when thin).

**In motion:** tilted slots give the same pinwheel energy as `iris` but
sharper-edged and sparser; the direction of tilt reads as intake/exhaust. With
n ≤ 9 and hw ≥ 0.35·m, no strobe; the alternating small holes are the first
thing to shimmer, so drop them below ~140 px wheel diameter.

**Difficulty:** Easy-medium. Stadium-at-arbitrary-angle needs a perpendicular
offset helper (~4 lines), then it is the existing cap idiom.

---

### 9. `sunburst` — Deco ray wedges
**One-liner:** Radiating tapered wedge openings alternating long and short, an
Art-Deco sunburst cut clean through the web.

**Recipe.**
```
n      = ray pairs (5..7) → 2n wedge openings
rI     = hubR·1.4
rLong  = wellR - 0.5·m ; rShort = rI + (rLong - rI)·0.62
wedge half-angle: wIn = 5..7 deg at rI, tapering to wOut = 2..3 deg at tip
for j in 0..2n-1:
  a    = j·(360/(2n))
  rOut = (j even) ? rLong : rShort
  subpath: M PT(rI,   a - wIn) 
           A rI arc to PT(rI, a + wIn)          // inner sill (tiny arc)
           L PT(rOut, a + wOut)
           A rOut arc to PT(rOut, a - wOut)     // tip sill (or L for a sharp point)
           Z
```
The taper (wide at hub, narrow at tip) is what makes it Deco rather than merely
slotted — rays *converge* outward, inverting the sun figure into negative space
([awedeco sunburst survey](https://awedeco.com/sunburst-motif-in-art-deco/)).

**Tunables:** n pairs 5–7; long/short ratio 0.55–0.75; taper wIn/wOut 1.5–3.5;
all-equal-length variant (plain radial burst). Guard: wedge width at rI
< 0.5·m → reduce n.

**In motion:** the alternating lengths create a two-frequency twinkle as tips
pass the highlight — elegant, slightly hypnotic. 2n ≤ 14 openings is the
comfort ceiling; at 2n = 16+ the short rays start to shimmer at small sizes.

**Difficulty:** Easy. Four commands per wedge, all from `PT`.

---

### 10. `arcade` — Gothic arch windows
**One-liner:** A ring of 5–7 pointed-arch (lancet) openings standing on the hub
boss, columns of metal between them — a rose-window wheel arcade.

**Recipe.** Each window: two straight jambs, a two-arc pointed head, a flat sill:

```
n      = windows (5..7)
pitch  = 360/n ; halfWin = pitch·0.30          // window half-angle; 0.20 column half-angle
rSill  = hubR·1.5 ; rSpring = rSill + depth·0.45 ; rApex = wellR - 0.5·m
for k: a = k·pitch
  jambL = PT(rSpring, a - halfWin) ; jambR = PT(rSpring, a + halfWin)
  apex  = PT(rApex, a)
  head arcs: radius Rh = |jambL→apex chord| (equilateral arch — the classic
             two-centre Gothic construction, centres at each opposite jamb)
  subpath: M PT(rSill, a - halfWin)
           L jambL
           A Rh,Rh 0 0 1 apex           // left head arc
           A Rh,Rh 0 0 1 (mirror) jambR // right head arc
           L PT(rSill, a + halfWin)
           A rSill arc back to start ; Z
```
Two-centre arch per [Chiffriller's Gothic geometry notes](http://westongeometry.pbworks.com/w/file/fetch/62270876/TIPSTRICKS.pdf).
Optional cusp: replace 8% of each head arc near the apex with a small inward
notch arc — legibility is surprisingly good even at 30 px window height.

**Tunables:** `n` 5–7; halfWin 0.24–0.34 of pitch; spring-line height 0.35–0.55
of depth; cusped/plain. Guard: `depth < 2.5·m` → drop to round-headed
(Romanesque) arches: single arc head, simpler and shorter.

**In motion:** windows parade past like a carousel colonnade; the pointed heads
give a directional flick at the top of each pass. No strobe at n ≤ 7.

**Difficulty:** Medium. The mirrored two-arc head with correct sweep flags is
the only fiddly part.

---

### 11. `trefoil` — foiled ports
**One-liner:** Three or four large openings, each a trefoil (three overlapping
round lobes with cusps) — Gothic tracery's foil punched through a steel web.

**Recipe.** Each port is the *outer boundary* of f overlapping circles, emitted
as f arcs meeting at cusp points:

```
f      = foils per port (3 or 4) ; nPorts = 3 or 4
portR  = depth·0.42                       // overall port radius, capped by pitch
lobeC  = portR·0.55                       // lobe-centre distance from port centre
lobeR  = portR - lobeC                    // lobe radius (lobes just fill portR)
cusp angle: cusps sit on bisectors between lobes at radius
    rc = sqrt(lobeC² - lobeR²·…)  — or simply: cusp_j = intersection of
    neighbouring lobe circles nearer the port centre:
    cusp_j = PT_local(lobeC·cos(180/f)/cos(0),  (j+0.5)·360/f)  approximated as
             lobeC·cos(180/f) + small ε; in practice compute the two-circle
             intersection once (both centres at distance lobeC, separation
             2·lobeC·sin(180/f), radius lobeR each) — closed form, 3 lines.
subpath: for j in 0..f-1: arc (radius lobeR, sweep 1, large-arc 1) from
         cusp_{j-1} to cusp_j ; Z
port placement: nPorts-fold at PT(mid, k·360/nPorts), each port rotated with
its orbit angle (as honeycomb) to preserve symmetry.
```
Requires `2·(portR) < 2π·mid/nPorts` so ports don't touch. Overlapping-circle
foil construction per [Wikipedia: quatrefoil](https://en.wikipedia.org/wiki/Quatrefoil).

**Tunables:** f 3/4; nPorts 3/4; lobeC/portR 0.45–0.62 (deep ↔ shallow cusps);
one giant single port variant is NOT possible (would swallow the hub). Guard:
`portR < 1.2·m` → fall back to plain round ports (= `holes`).

**In motion:** the cusps are the payoff — three tiny points per port catching
the light in turn. At nPorts·f = 9–16 arc lobes total, still below shimmer
threshold because each port reads as one object.

**Difficulty:** Hard(est of the set). The two-circle intersection and large-arc
sweep flags must be exactly right or even-odd fill inverts a lobe. Worth it —
nothing else in the pool has cusps.

---

### 12. `turbine` — backswept vanes
**One-liner:** Seven short log-spiral vane slots sweeping hub to well in under a
quarter turn — a centrifugal impeller in silhouette, cousin-but-not-sibling to
the scroll spiral.

**Recipe.** Same slot construction as the existing `spiral` kind (offset
polylines, `spt`-style), with two parameter changes that completely change the
read:

```
n       = vanes (6..9)          (spiral uses 3..7 arms)
sweepT  = 0.18..0.28 turns      (spiral uses 1.15 — this is the key difference)
profile : angle(f) = base + f²·sweepT·360    // quadratic — vanes leave the hub
                                             // radially and bend late, the
                                             // log-spiral look without logs
width   : w(f) = m·(0.75 - 0.35·f)          // tapering slot, wide at hub
rIn = hubR·1.5 ; rOut = wellR - 0.5·m ; STEPS = 14
subpath k: offset polyline ±w(f)/2 around
           (rIn + (rOut-rIn)·f) at angle (k·360/n + f²·sweepT·360), f = 0..1
```
Log-spiral blade rationale per [Brennen ch. 2](http://brennen.caltech.edu/HTMPUM/chap2.htm);
the f² profile is a two-character approximation that reads identically at this
scale.

**Tunables:** n 6–9; sweepT 0.15–0.30; taper 0–0.5; handedness. Guard: shares
the spiral's guards.

**In motion:** strong directional read like `flywheel` but denser and more
mechanical; feels like it should be moving air. With n = 9 and thin tapered
tips, mild tip-shimmer on the smallest wheels — cap n at 7 when
`depth < 3·m`.

**Difficulty:** Easy — it is a re-parameterisation of code that already ships.
*Pool-design caution:* ensure random assignment never puts `turbine` and
`spiral` on adjacent wheels, or they read as duplicates.

---

## Part 3 — Ranking for variety

The existing five kinds occupy: **circumferential rounded slots** (spokes,
pockets), **round drilled holes** (holes, ring), and **long-wound curved slots**
(spiral). Missing vocabularies: straight lines/corners, tangential tilt, wavy
organic boundaries, concentric rhythm, polygons, cusps.

Add first, in order:

1. **`iris`** — tangentially-tilted crescents; a geometry class (lunes) and an
   energy (pinwheel) the pool has zero of. Biggest single win.
2. **`magstar`** — the first straight edges and sharp corners anywhere in the
   train; boldest silhouette; trivially cheap to build.
3. **`rosette`** — the first organic/wavy boundary; also the first design whose
   opening is one large annular cut rather than n discrete punches ("doesn't
   have to be sturdy" fully exploited, though nothing actually floats).
4. **`labyrinth`** — the first concentric, multi-ring rhythm, and the design
   that rewards the constant rotation most (counter-phased bridges breathing).
5. **`honeycomb`** — polygonal ports; nearest to an existing kind (holes) of
   this five, but the hex corners read distinctly and it is nearly free to
   implement, giving the randomiser a safe workhorse.

Second wave: `geneva` and `sunburst` (both easy, both iconic), then `flywheel`
and `arcade`. `rotor` and `turbine` last — good designs, but each sits nearest
an existing kind (holes/spokes and spiral respectively), so they add the least
marginal variety per unit of pool size. `trefoil` whenever the appetite for the
hard one arrives — it is the only cusped design and worth the fiddling.

Implementation notes that apply pool-wide:

- All twelve use only `PT`, polylines, `A` arcs, and closed subpaths on
  `holes[]` — no masks, no gradients required; every one works in the `flat`
  path with just `ft.line` strokes.
- The `GHOST_KINDS` array (index.html:134) and the per-kind branch (~line 959)
  are the only two integration points; ghost wheels randomise `arms` 3–7
  already, so each new kind should tolerate that range or clamp it.
- Every design keeps subpaths strictly inside `(hubR, wellR)` by construction —
  the clamps are stated inline above. None of the subpaths within a design can
  intersect while the stated angular/radial inequalities hold; each recipe's
  inequality is one `Math.min`/guard line in code.

---

## Sources

- [Model Engineer forum — Curved flywheel spokes](https://www.model-engineer.co.uk/forums/topic/curved-flywheel-spokes/)
- [Home Model Engine Machinist — Curved flywheel spokes](https://www.homemodelenginemachinist.com/threads/curved-flywheel-spokes.3279/)
- [Home Shop Machinist BBS — S-shaped spokes](https://bbs.homeshopmachinist.net/forum/general/15536-s-shaped-spokes)
- [Smokstak — Flywheel rotation](https://www.smokstak.com/forum/threads/flywheel-rotation.187845/)
- [Wikipedia — Skeleton watch](https://en.wikipedia.org/wiki/Skeleton_watch)
- [TrueFacet — Skeletonized watches guide](https://www.truefacet.com/guide/skeletonized-watches-the-ultimate-guide/)
- [Wikipedia — Geneva drive](https://en.wikipedia.org/wiki/Geneva_drive)
- [Firgelli — Maltese cross mechanism](https://www.firgelliauto.com/blogs/mechanisms/maltese-cross-mechanism)
- [Engineers Edge — Geneva mechanism design equations](https://www.engineersedge.com/mechanics_machines/geneva_internal_mechanism_14920.htm)
- [BikeRadar — Disc brake rotors explained](https://www.bikeradar.com/advice/buyers-guides/disc-brake-rotors)
- [US patent app. 2013/0032439 — Disk rotor with graphical structural elements](https://patents.justia.com/patent/20130032439)
- [camera-wiki — Diaphragm](https://camera-wiki.org/wiki/Diaphragm)
- [RP Photonics — Diaphragms](https://www.rp-photonics.com/diaphragms.html)
- [Wikipedia — Quatrefoil](https://en.wikipedia.org/wiki/Quatrefoil)
- [Wikipedia — Trefoil](https://en.wikipedia.org/wiki/Trefoil)
- [Chiffriller — Tips & Tricks to Gothic Geometry (PDF)](http://westongeometry.pbworks.com/w/file/fetch/62270876/TIPSTRICKS.pdf)
- [Wikipedia — Sunburst motif](https://en.wikipedia.org/wiki/Sunburst)
- [awedeco — The sunburst motif in Art Deco](https://awedeco.com/sunburst-motif-in-art-deco/)
- [mathcurve — Rose curves](https://mathcurve.com/courbes2d.gb/rosace/rosace.shtml)
- [Chalkdust — Spirographs](https://chalkdustmagazine.com/regulars/on-the-cover/on-the-cover-spirographs/)
- [Brennen — Hydrodynamics of Pumps, ch. 2 (log-spiral blades)](http://brennen.caltech.edu/HTMPUM/chap2.htm)
- [ResearchGate — Log-spiral blade profile figure](https://www.researchgate.net/figure/Blade-profile-of-logarithmic-spiral-method_fig3_347892543)
- [Wikipedia — Lathe faceplate](https://en.wikipedia.org/wiki/Lathe_faceplate)
