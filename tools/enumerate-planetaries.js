'use strict';

// Reference planetary tooth-count enumerator. Plain JS, browser-safe, no deps.
//
// Constraint sources (see planetary-solver.md for links):
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

if (typeof module !== 'undefined') module.exports = { enumeratePlanetaries: enumeratePlanetaries };

// ---- sanity checks (node only) ----
if (typeof require !== 'undefined' && require.main === module) {
  const has = (list, t) => list.some(r => r.Zs === t[0] && r.Zp === t[1] && r.Zr === t[2]);
  const fmt = r => `(${r.Zs},${r.Zp},${r.Zr})x${r.N} ratio=${r.ratio.toFixed(2)} hunt=${r.hunting} phase=${r.inPhase ? 'in' : 'stag'}`;

  const a = enumeratePlanetaries({ N: 3, sunBias: 'medium', ZrMin: 24, ZrMax: 36 });
  console.log('N=3 medium, Zr 24..36 — top 6 of ' + a.length);
  a.slice(0, 6).forEach(r => console.log('  ' + fmt(r)));
  console.log('contains (12,9,30,3):', has(a, [12, 9, 30]));

  const b = enumeratePlanetaries({ N: 4, sunBias: 'large', ZrMin: 24, ZrMax: 36 });
  console.log('N=4 large, Zr 24..36 — top 6 of ' + b.length);
  b.slice(0, 6).forEach(r => console.log('  ' + fmt(r)));
  console.log('contains (18,6,30,4):', has(b, [18, 6, 30]));

  // adjacency must actually bite: N=6 with a tiny sun should reject big planets
  const c = enumeratePlanetaries({ N: 6, sunBias: 'small', ZrMin: 24, ZrMax: 48 });
  const bad = c.filter(r => (r.Zs + r.Zp) * Math.sin(Math.PI / 6) <= r.Zp + 2.5);
  console.log('N=6 results:', c.length, 'adjacency violations leaked:', bad.length);
  c.slice(0, 4).forEach(r => console.log('  ' + fmt(r)));
}
