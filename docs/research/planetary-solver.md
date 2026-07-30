# Planetary tooth-count solver — research report

Research task for wozi.com's epicyclic gear set. Goal: given planet count N (3–6)
and a sun-size bias, enumerate valid (Zs, Zp, Zr, N) tuples instead of hand-picking.
Nothing here was written into the repo; this document and the companion
`enumerate-planetaries.js` live only in the scratchpad.

## Sources actually read (constraint code, not READMEs)

1. **chrisspen/gears** (`gears.scad`, the Getriebe.scad/janssen86 lineage) —
   <https://github.com/chrisspen/gears>
   - Ring teeth: `ring_teeth = sun_teeth + 2*planet_teeth;`
   - Auto-picks planet count by filtering candidates:
     `list = [for (n=[2:1:n_max]) if ((((ring_teeth+sun_teeth)/n)==floor((ring_teeth+sun_teeth)/n))) n];`
   - Adjacency cap (pitch-circle only, weaker than KHK):
     `n_max = floor(180/asin(modul*(planet_teeth)/(modul*(sun_teeth + planet_teeth))));`
     i.e. planets fit while `sin(180/N) > Zp/(Zs+Zp)` — no tip-diameter allowance.

2. **hyperair/planetary-gears** (`planetary-gears.scad`) —
   <https://github.com/hyperair/planetary-gears>
   - Hard-errors the equal-spacing assembly condition:
     `if ((sun_teeth + ring_teeth) % number_of_planets != 0) echo("ERROR: ...")`
   - Hard-errors non-integer planet teeth: `planet_teeth = (ring_teeth - sun_teeth) / 2;`
     with `floor(planet_teeth) != planet_teeth` check → **Zs and Zr must share parity**.
   - Places planets at `360/number_of_planets` intervals (equal spacing only).

3. **Emmett Lalish's Gear Bearing** (Thingiverse thing:53451; mirror gist read:
   <https://gist.github.com/mccv/646f4d65c8b6eebbd4ff3ac5f39683dd>)
   - Does not *check* the assembly condition — it *constructs* tooth counts so it
     holds. With `m` = number of planets, `np` = planet teeth:
     ```
     k1 = round(2/m*(ns1+np));
     k  = k1*m%2 != 0 ? k1+1 : k1;
     ns = k*m/2 - np;
     nr = ns + 2*np;
     ```
     so `ns + nr = k*m` — sun+ring is a multiple of the planet count by construction.
   - Per-planet mesh phase: `rotate([0,0, i*ns/m*360/np - phi*(ns+np)/np - phi])` —
     the same per-station phase stagger wozi.com already implements.
   - The general (unequal-spacing) rule this construction is a special case of:
     a planet can be placed at any angle that is an integer multiple of
     `360°/(Zs+Zr)` — widely-copied gear-bearing remixes quantise placement as
     `round(i*(ns+nr)/np)*360/(ns+nr)` when the sum is not a multiple of N.

4. **BOSL2** (`gears.scad` wiki) — <https://github.com/BelfrySCAD/BOSL2/wiki/gears.scad>
   - Undercut floor: "The minimum number of teeth to avoid undercutting is 17 for a
     pressure angle of 20, but it is 32 for a pressure angle of 14.5 degrees. It can
     be computed as `2/(sin(alpha))^2`." Rule of thumb: 14 teeth OK at 20° because
     the undercut is negligible.
   - Profile shifting "can eliminate undercutting, while still allowing the gear to
     mesh with unmodified gears" and "changes the mesh distance" — this is the
     escape hatch real generators use for small pinions, and it is also how the
     strict concentricity equation is relaxed (shifted meshes move the operating
     centre distance, so `Zr = Zs + 2Zp` need not hold exactly if the sun–planet
     and planet–ring shifts are balanced).
   - Its planetary example (24/16/56, four planets) satisfies all conditions:
     24 + 2·16 = 56, (24+56)/4 = 20.

5. **KHK Gears technical reference** (via patent/reference citations of the KHK
   design conditions) — <https://www.slideshare.net/slideshow/khk-gears-technical-referencepdf/257293334>
   - Names the canonical trio:
     - coaxial condition `Zr = Zs + 2Zp`
     - assembly condition `Integer = (Zr+Zs)/N`
     - **neighbor condition** `Zp + 2 < (Zr − Zp)·sin(180°/N)`
       Since `Zr − Zp = Zs + Zp`, this is `(Zs+Zp)·sin(π/N) > Zp + 2`: the planet
       tip *diameter* in tooth units is `Zp + 2` (one addendum module per side),
       and the chord between adjacent planet centres is `(Zs+Zp)·2·sin(π/N)`
       pitch-radius units... expressed per-radius as above. This is the correct,
       tip-circle form; chrisspen/gears' pitch-circle version under-rejects.

6. **madl3x/plgcalc** — <https://github.com/madl3x/plgcalc>
   - Enforces `R = 2P + S` and the *stricter* "R divisible by N AND S divisible
     by N". That over-constrains: it guarantees every sun–planet mesh is in the
     same phase (no stagger needed) but rejects perfectly assemblable sets like
     (12,9,30,3). Since wozi.com already handles per-station phase stagger, the
     weaker `(Zs+Zr)%N == 0` is the right condition; `Zs % N == 0` is only a
     convenience flag (`inPhase` in the implementation below).

7. **Hunting-tooth guidance** — Dorman Shop Press
   (<https://shoppress.dormanproducts.com/hunting-tooth-gearsets/>) and NAWCC forum
   (<https://mb.nawcc.org/threads/even-uniform-gear-wear-using-relatively-prime-coprime-tooth-counts.114963/>):
   meshing pairs with `gcd > 1` re-mate the same tooth pairs forever, concentrating
   wear; coprime counts distribute it. **Purely cosmetic for an SVG** — noted as a
   report flag only, never a rejection. (12,9,30,3) fails hunting on both meshes
   (gcd(12,9)=3, gcd(9,30)=3) and looks fine, which proves the point.

## The complete constraint set

Beyond wozi.com's existing two:

| # | Constraint | Formula | Enforced by |
|---|-----------|---------|-------------|
| C1 | Concentricity (coaxial) | `Zr = Zs + 2·Zp`; ⇒ Zs, Zr same parity so Zp is an integer | chrisspen, hyperair, Emmett, KHK |
| C1' | Profile-shift generalisation | shifted meshes may deviate from C1 if sun–planet and planet–ring operating centre distances are re-balanced via shifts; BOSL2 "changes the mesh distance". Not needed for a stylised SVG — keep C1 exact. | BOSL2 |
| C2 | Assembly, equal spacing | `(Zs + Zr) % N == 0` | hyperair (hard error), chrisspen (filter), KHK, Emmett (by construction: `ns+nr = k·m`) |
| C2' | Assembly, unequal-but-valid | planet angles must be integer multiples of `360°/(Zs+Zr)`; N planets fit iff N such slots exist with pairwise gaps ≥ the adjacency angle `2·asin((Zp+2)/(Zs+Zp))` | Emmett-lineage placement quantisation |
| C3 | Adjacency / tip clearance | `(Zs + Zp)·sin(π/N) > Zp + 2` (+2 = two addenda at ha*=1; add a margin for backlash) | KHK neighbor condition; chrisspen has only the weaker pitch-circle form |
| C4 | Hunting tooth (cosmetic) | prefer `gcd(Zs,Zp) = gcd(Zp,Zr) = 1` for even wear; irrelevant to rendering, report-only | Dorman/NAWCC; no generator read enforces it |
| C5 | Undercut minimum | real involutes: ≥ 17 teeth at 20° PA (`2/sin²α`), ~14 by rule of thumb; generators either warn or auto-profile-shift (BOSL2). wozi.com's teeth are stylised, so this is a soft floor (default 6) with an `undercutSafe` info flag | BOSL2 |

Also worth carrying as an output flag: `inPhase = (Zs % N == 0)` — when true, all
sun–planet meshes engage identically and no per-station stagger is needed (this is
what plgcalc's over-strict rule buys); when false, the existing stagger code is
load-bearing.

## Reference implementation (plain JS, no deps, browser-safe)

Tested under node; both known-good wozi.com tuples appear and rank **first** for
their natural bias.

```js
'use strict';

// Reference planetary tooth-count enumerator. Plain JS, browser-safe, no deps.
//
// Constraint sources:
//   [C1] Concentricity     Zr = Zs + 2*Zp          — chrisspen/gears, hyperair/planetary-gears, KHK "coaxial condition"
//   [C2] Assembly/spacing  (Zs + Zr) % N == 0      — hyperair/planetary-gears, chrisspen/gears, Emmett Lalish's
//                          for EQUAL spacing.        Gear Bearing derives ns,nr so ns+nr = k*N by construction.
//                          General (unequal) rule: planets may sit at any integer multiple of 360/(Zs+Zr).
//   [C3] Adjacency         (Zr - Zp)*sin(pi/N) > Zp + 2   — KHK technical reference "neighbor condition"
//                          (equivalently (Zs + Zp)*sin(pi/N) > Zp + 2, since Zr - Zp = Zs + Zp).
//                          The +2 is the two addenda (1 module each) on the planet tip diameter.
//                          chrisspen/gears uses the weaker pitch-circle form floor(180/asin(Zp/(Zs+Zp))).
//   [C4] Hunting tooth     gcd of meshing counts == 1 preferred — even wear; cosmetic-only for wozi.com,
//                          reported as a flag, never used to reject.
//   [C5] Undercut          real involutes want >= 17 teeth at 20 deg PA (2/sin^2(alpha)), ~14 by rule of
//                          thumb, or profile shift — BOSL2 gears.scad. We render stylised teeth, so the
//                          floor is a soft parameter (default 6) and small pinions are merely flagged.

function gcd(a, b) { while (b) { const t = a % b; a = b; b = t; } return a; }

/**
 * Enumerate valid planetary (star) gear tooth tuples.
 * @param {object} opts
 * @param {number} opts.N        planet count, 3..6
 * @param {string} [opts.sunBias]  'small' | 'medium' | 'large' — sun size relative to ring
 * @param {number} [opts.ZrMin]  smallest ring tooth count to consider (default 24)
 * @param {number} [opts.ZrMax]  largest ring tooth count to consider (default 60)
 * @param {number} [opts.minTeeth]  floor for Zs and Zp (default 6 — visual fudge; real involutes want 14+)
 * @param {number} [opts.clearanceTeeth]  extra tip clearance margin, in tooth-count units (default 0.5)
 * @returns {Array<{Zs:number,Zp:number,Zr:number,N:number,ratio:number,hunting:boolean,inPhase:boolean,undercutSafe:boolean}>}
 *          sorted best-fit-to-bias first.
 */
function enumeratePlanetaries(opts) {
  const N = opts.N;
  const sunBias = opts.sunBias || 'medium';
  const ZrMin = opts.ZrMin !== undefined ? opts.ZrMin : 24;
  const ZrMax = opts.ZrMax !== undefined ? opts.ZrMax : 60;
  const minTeeth = opts.minTeeth !== undefined ? opts.minTeeth : 6;
  const clearanceTeeth = opts.clearanceTeeth !== undefined ? opts.clearanceTeeth : 0.5;

  if (!(N >= 3 && N <= 6)) throw new Error('N must be 3..6');
  const target = { small: 0.25, medium: 0.40, large: 0.60 }[sunBias];
  if (target === undefined) throw new Error("sunBias must be 'small'|'medium'|'large'");

  const sinHalf = Math.sin(Math.PI / N);
  const out = [];

  for (let Zr = ZrMin; Zr <= ZrMax; Zr++) {
    // [C1] Zs and Zr must share parity so Zp = (Zr - Zs)/2 is an integer
    // (hyperair/planetary-gears errors out on fractional planet teeth).
    for (let Zs = minTeeth; Zs <= Zr - 2 * minTeeth; Zs++) {
      if ((Zr - Zs) % 2 !== 0) continue;
      const Zp = (Zr - Zs) / 2;                       // [C1] concentricity, by construction
      if (Zp < minTeeth) continue;
      if ((Zs + Zr) % N !== 0) continue;              // [C2] equal-spacing assembly condition
      if ((Zs + Zp) * sinHalf <= Zp + 2 + clearanceTeeth) continue; // [C3] tip-circle adjacency

      out.push({
        Zs: Zs, Zp: Zp, Zr: Zr, N: N,
        ratio: Zs / Zr,                                // sun size relative to ring
        hunting: gcd(Zs, Zp) === 1 && gcd(Zp, Zr) === 1, // [C4] even-wear flag (cosmetic here)
        inPhase: Zs % N === 0,   // all sun-planet meshes in phase; false => per-station stagger needed
        undercutSafe: Zs >= 17 && Zp >= 17             // [C5] strict 20-deg involute floor (informational)
      });
    }
  }

  out.sort(function (a, b) {
    const d = Math.abs(a.ratio - target) - Math.abs(b.ratio - target);
    if (d !== 0) return d;
    if (a.Zr !== b.Zr) return a.Zr - b.Zr;             // prefer smaller wheels on a tie
    return (b.hunting ? 1 : 0) - (a.hunting ? 1 : 0);  // then even-wear sets
  });
  return out;
}
```

Design notes:

- **Why `ratio = Zs/Zr`** as the bias metric: pitch diameters scale with tooth
  count at fixed module, so Zs/Zr *is* the sun-to-ring visual size ratio. Targets:
  small 0.25, medium 0.40, large 0.60 — chosen so each known-good tuple is the
  natural top hit for its bias.
- **`clearanceTeeth`** (default 0.5) pads KHK's strict `> Zp + 2` so planet tips
  don't visually kiss; set 0 for the textbook boundary.
- **`minTeeth` default 6** deliberately admits the stylised 6T/9T pinions the site
  already ships; a real gearbox generator would default 14–17 or profile-shift
  (C5). The `undercutSafe` flag preserves the honest engineering answer.
- Unequal-but-valid spacing (C2') is intentionally *not* enumerated — the wozi.com
  train places stations symmetrically, so equal spacing is the requirement. If ever
  wanted: drop the C2 filter and instead accept tuples where N angles from the set
  `{k·360/(Zs+Zr)}` can be chosen with pairwise gaps ≥ `2·asin((Zp+2)/(Zs+Zp))`.

## Sanity-check results (node, verified)

`N=3, sunBias='medium', ZrMin=24, ZrMax=36` → 30 tuples, top 6:

```
(12,9,30)x3 ratio=0.40 hunt=false phase=in     <- shipped tuple, rank 1
(14,10,34)x3 ratio=0.41 hunt=false phase=stag
(10,8,26)x3 ratio=0.38 hunt=false phase=stag
(13,11,35)x3 ratio=0.37 hunt=true  phase=stag
(11,7,25)x3 ratio=0.44 hunt=true  phase=stag
(11,10,31)x3 ratio=0.35 hunt=true  phase=stag
```

`N=4, sunBias='large', ZrMin=24, ZrMax=36` → 36 tuples, top 6:

```
(18,6,30)x4 ratio=0.60 hunt=false phase=stag   <- shipped tuple, rank 1
(21,7,35)x4 ratio=0.60 hunt=false phase=stag
(19,7,33)x4 ratio=0.58 hunt=true  phase=stag
(20,6,32)x4 ratio=0.63 hunt=false phase=in
(16,6,28)x4 ratio=0.57 hunt=false phase=in
(20,8,36)x4 ratio=0.56 hunt=false phase=in
```

`N=6, sunBias='small', Zr 24..48` → 39 tuples, zero adjacency leaks; best available
ratio is ~0.43 because a genuinely small sun with six planets violates the neighbor
condition — the constraint biting exactly as KHK says it should.

Manual spot checks of the shipped tuples against C3:
- (12,9,30,3): (12+9)·sin 60° = 18.19 > 9+2 = 11 ✓
- (18,6,30,4): (18+6)·sin 45° = 16.97 > 6+2 = 8 ✓

Runnable copy of the code with the test harness:
`/private/tmp/claude-501/-Users-charles-work-claude-wozi-com/fd0b7254-2923-429f-bfc6-8be63ee34a46/scratchpad/enumerate-planetaries.js`
