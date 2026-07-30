/* Measures the PLANETARY set's mesh the way mesh_inv.js measures the train:
   build the real outlines, roll the set through a full turn of the host wheel,
   and report how far metal goes into metal and how much air is left at the
   tightest point.

   Two meshes per set, and they are not the same problem:
     sun <-> planet   external, both true involutes straight out of teethPath
     planet <-> ring  internal, and the ring is NOT an involute — index.html
                      builds it as a trapezoid (tip 0.95m inward of pitch, root
                      1.15m outward, half-width 0.24 of pitch at the tip, 1.7x
                      that at the root). Whether that trapezoid clears a real
                      involute is the question this harness exists to answer.

   Every profile here is star-shaped about its own centre — a radius for each
   angle, no re-entrant flanks — so each one is indexed once as a radial profile
   R(theta) and every containment test is a table lookup. Overlap is reported
   RADIALLY: the distance a point sits past the other body's surface along the
   line from that body's centre. On a 20-degree flank that overestimates the
   true perpendicular depth by about 6%, which is the safe direction to err.

   All lengths are in MODULES (m2 = 1), so the numbers hold at any wheel size:
   multiply by the wheel's own m2 (= 2*Rr/Zr px) for pixels.

   Run: node tools/mesh_epi.js            shipped profile, every dealt set
        node tools/mesh_epi.js --solve    is the derived phase the clearing one?
        node tools/mesh_epi.js --sweep    search ring tooth proportions
*/
'use strict';

const { enumeratePlanetaries } = require('./enumerate-planetaries.js');

const PA = 20, ADD = 1.00, DED = 1.25, THICK = 0.495;
const inv = (x) => Math.tan(x) - x;
const D2R = Math.PI / 180, TAU = Math.PI * 2;

/* ---- radial profiles ------------------------------------------------------
   profile(fn, pitchAngle) samples one tooth pitch and answers R(theta) for any
   angle by folding into that pitch. Bodies are periodic, so one pitch is all
   the information there is. */
const SAMPLES = 720;
function profileFromPoints(pts, period, mode) {
  /* pts: [angle, radius] within one period. Bucketed to a table.
     mode 'max' for a solid body seen from its own centre (outermost surface
     wins); 'min' for a VOID seen from the centre it encloses (the first metal
     going outward wins). */
  const outer = mode !== 'min';
  const tab = new Float64Array(SAMPLES);
  const idx = (a) => Math.floor((((a % period) + period) % period) / period * SAMPLES) % SAMPLES;
  tab.fill(outer ? -1 : Infinity);
  const better = (r, cur) => (outer ? r > cur : r < cur);
  for (let i = 0; i < pts.length; i++) {
    const [a1, r1] = pts[i], [a2, r2] = pts[(i + 1) % pts.length];
    let da = a2 - a1;
    while (da > period / 2) da -= period;
    while (da < -period / 2) da += period;
    const n = Math.max(1, Math.ceil(Math.abs(da) / (period / SAMPLES) * 2));
    for (let s = 0; s <= n; s++) {
      const a = a1 + da * (s / n), r = r1 + (r2 - r1) * (s / n);
      const k = idx(a);
      if (better(r, tab[k])) tab[k] = r;
    }
  }
  /* fill any unsampled cell from its neighbours */
  const unset = (v) => (outer ? v < 0 : !isFinite(v));
  for (let k = 0; k < SAMPLES; k++) {
    if (!unset(tab[k])) continue;
    let a = k, b = k;
    while (unset(tab[(a + SAMPLES * 4) % SAMPLES])) a--;
    while (unset(tab[b % SAMPLES])) b++;
    tab[k] = (tab[(a + SAMPLES * 4) % SAMPLES] + tab[b % SAMPLES]) / 2;
  }
  return { tab, period, at: (a) => tab[idx(a)] };
}

/* Involute tooth flank, point-for-point the construction teethPath draws. */
function involuteProfile(n, r) {
  const phi = PA * D2R;
  const ro = r + ADD, rr = Math.max(0.5, r - DED), rb = r * Math.cos(phi);
  const a = TAU / n;
  const psiP = THICK * Math.PI / n;
  const half = (R) => psiP + inv(phi) - inv(Math.acos(Math.min(1, rb / R)));
  const rStart = Math.max(rb, rr + 0.01), hRoot = half(rStart);
  const pts = [];
  const STEPS = 16;
  for (let s = 0; s <= 4; s++) pts.push([-a / 2 + (a / 2 - hRoot) * (s / 4), rr]);
  pts.push([-hRoot, rStart]);
  for (let s = 1; s <= STEPS; s++) { const R = rStart + (ro - rStart) * (s / STEPS); pts.push([-half(R), R]); }
  for (let s = 0; s <= 3; s++) pts.push([-half(ro) + 2 * half(ro) * (s / 3), ro]);
  for (let s = STEPS; s >= 1; s--) { const R = rStart + (ro - rStart) * (s / STEPS); pts.push([half(R), R]); }
  pts.push([hRoot, rStart]);
  for (let s = 0; s <= 4; s++) pts.push([hRoot + (a / 2 - hRoot) * (s / 4), rr]);
  return profileFromPoints(pts, a, 'max');
}

/* The ring's VOID: the surface enclosing the air the planets run in. Inside it
   is air; outside it, out to the bore, is metal.

   'trapezoid' is what index.html ships. 'involute' is the proper internal gear:
   the same involute curve, but the TOOTH occupies what would be an external
   gear's space, so its thickness grows with radius instead of shrinking, and
   the addendum points inward. Cut that way, a planet tooth and a ring space are
   congruent by construction rather than by fitted constants. */
function ringVoidProfile(Zr, Rr, opt) {
  const a = TAU / Zr;
  if (opt.kind === 'involute') {
    const phi = PA * D2R, rb = Rr * Math.cos(phi);
    const tip = Rr - (opt.addI !== undefined ? opt.addI : ADD), root = Rr + DED;
    /* half-thickness of the RING tooth at radius R -- complement of the
       external law, so the space it leaves is congruent to a planet tooth */
    const psiI = THICK * Math.PI / Zr;
    const halfI = (R) => psiI - inv(phi) + inv(Math.acos(Math.min(1, rb / R)));
    const pts = [], STEPS = 16;
    pts.push([-a / 2, root]);
    pts.push([-halfI(root), root]);
    for (let s = STEPS - 1; s >= 0; s--) { const R = tip + (root - tip) * (s / STEPS); pts.push([-halfI(R), R]); }
    for (let s = 0; s <= STEPS; s++) { const R = tip + (root - tip) * (s / STEPS); pts.push([halfI(R), R]); }
    pts.push([a / 2 - 1e-9, root]);
    return profileFromPoints(pts, a, 'min');
  }
  const tip = Rr - opt.addIn, root = Rr + opt.dedOut;
  const wt = a * opt.widthFrac, rf = opt.rootFactor;
  const pts = [
    [-a / 2, root], [-wt * rf, root], [-wt, tip], [wt, tip], [wt * rf, root], [a / 2 - 1e-9, root],
  ];
  return profileFromPoints(pts, a, 'min');
}

/* One gear set, rolled through a full turn of the host wheel.
   dS / dP are diagnostic offsets added to the derived sun / planet phases: if
   the mesh only clears at a non-zero offset, the derivation is what is wrong. */
function audit(PG, opt, Q, dS, dP, steps) {
  dS = dS || 0; dP = dP || 0; steps = steps || 180;
  const [Zs, Zp, Zr, NP] = PG;
  const Rr = Zr / 2, Rs = Zs / 2, Rp = Zp / 2, Rc = Rs + Rp;
  const kC = -1, kP = Zr / Zp, kS = -(1 + Zr / Zs);
  const pp = 360 / Zp, ps = 360 / Zs;
  const baseC = -Q;
  const basePAt = (A) => dP + ((((kP * (Q - A) - pp / 2) % pp) + pp) % pp);
  /* SHIPPED sun phase vs the one the interleave condition actually gives.
     Derivation: the planet's phase is already pinned by the ring mesh, so the
     sun's only job is to present a space where the planet presents a tooth.
     Writing both as a fraction of their own pitch at the line of centres, the
     sum is conserved (external mesh turns them opposite ways), which leaves
     baseS = ps*(Zp/2 - Q*(Zs+Zr)/360). The Zs term in the shipped constant is
     spurious: whether the planet points a tooth or a gap at the sun depends on
     Zp's parity alone. A_k drops out because (Zs+Zr)%N == 0 -- the assembly
     condition doing exactly the job it is there for. */
  const sunShipped = 180 * (1 - Zp / Zs) + Q * (Zr / Zs - 1);
  const sunFixed = 180 * Zp / Zs - Q * (Zs + Zr) / Zs;
  const raw = opt.sunPhase === 'fixed' ? sunFixed : sunShipped;
  const baseS = dS + (((raw % ps) + ps) % ps);

  const ring = ringVoidProfile(Zr, Rr, opt);
  const sun = involuteProfile(Zs, Rs);
  const planet = involuteProfile(Zp, Rp);

  /* Sample points on the planet's own surface, in its local frame. */
  const PN = 900, plPts = [];
  for (let i = 0; i < PN; i++) {
    const th = (i / PN) * TAU;
    const R = planet.at(th);
    plPts.push([th, R]);
  }

  const res = { ringPen: 0, ringGap: Infinity, sunPen: 0, sunGap: Infinity, ringAt: 0, Rp, rb: Rp * Math.cos(PA * D2R), rr: Rp - DED };

  for (let step = 0; step < steps; step++) {
    const tw = (step / steps) * 360;
    const carrier = baseC + kC * tw;
    const sunRot = (baseS + kS * tw) * D2R;

    for (let k = 0; k < NP; k++) {
      const A = k * (360 / NP);
      const stationDeg = carrier + A;
      const bodyRot = (carrier + A + basePAt(A) + kP * tw) * D2R;
      const st = stationDeg * D2R;
      const cx = Rc * Math.cos(st), cy = Rc * Math.sin(st);

      for (let i = 0; i < PN; i++) {
        const th = plPts[i][0] + bodyRot, R = plPts[i][1];
        const x = cx + R * Math.cos(th), y = cy + R * Math.sin(th);
        const rad = Math.hypot(x, y), ang = Math.atan2(y, x);
        if (rad > Rc) {                       /* outboard half: talks to the ring */
          const surf = ring.at(ang);
          const d = rad - surf;
          if (d > 0) {
            if (d > res.ringPen) { res.ringPen = d; res.ringAt = R; }
            } else res.ringGap = Math.min(res.ringGap, -d);
        } else {                              /* inboard half: talks to the sun */
          const surf = sun.at(ang - sunRot);
          const d = surf - rad;
          if (d > 0) res.sunPen = Math.max(res.sunPen, d);
          else res.sunGap = Math.min(res.sunGap, -d);
        }
      }
    }
  }
  return res;
}

const SHIPPED = { widthFrac: 0.24, rootFactor: 1.7, addIn: 0.95, dedOut: 1.15 };

function menu() {
  const flavours = [[3, 'medium'], [3, 'large'], [4, 'medium'], [4, 'large'], [5, 'small'], [5, 'medium']];
  const seen = {}, out = [];
  flavours.forEach((c) => {
    const r = enumeratePlanetaries({ N: c[0], sunBias: c[1], ZrMin: 24, ZrMax: 33,
      minTeeth: +(process.env.MIN_TEETH || 5) })[0];
    if (!r) return;
    const key = [r.Zs, r.Zp, r.Zr, r.N].join('.');
    if (seen[key]) return;
    seen[key] = 1;
    out.push([r.Zs, r.Zp, r.Zr, r.N]);
  });
  return out;
}

const SETS = menu();
/* The carrier is clocked at random per load, so the phase constants have to
   hold at every clocking, not one convenient one. */
const QS = [0, 17, 37, 68, 111, 154, 203, 249, 298, 331];

function report(label, opt) {
  console.log('\n' + label);
  console.log('  set (Zs,Zp,Zr)xN   sun <-> planet        planet <-> ring');
  for (const PG of SETS) {
    let rp = 0, rg = Infinity, sp = 0, sg = Infinity;
    for (const Q of QS) {
      const r = audit(PG, opt, Q);
      rp = Math.max(rp, r.ringPen); rg = Math.min(rg, r.ringGap);
      sp = Math.max(sp, r.sunPen); sg = Math.min(sg, r.sunGap);
    }
    const tag = `(${PG[0]},${PG[1]},${PG[2]})x${PG[3]}`.padEnd(14);
    console.log(`  ${tag} pen ${sp.toFixed(3)}m gap ${sg.toFixed(3)}m   pen ${rp.toFixed(3)}m gap ${rg.toFixed(3)}m`);
  }
}

if (process.argv.includes('--solve')) {
  /* Is the DERIVATION wrong, or only the clearance? Walk the sun phase across a
     whole tooth pitch and the planet phase across one of its own, and find where
     the metal actually clears. A minimum at offset 0 exonerates the formula. */
  for (const PG of SETS) {
    const [Zs, Zp] = PG;
    const ps = 360 / Zs, pp = 360 / Zp;
    console.log(`\n(${PG[0]},${PG[1]},${PG[2]})x${PG[3]}  sun pitch ${ps.toFixed(1)} deg, planet pitch ${pp.toFixed(1)} deg`);
    let bestS = null, bestP = null;
    for (let i = 0; i < 36; i++) {
      const dS = (i / 36) * ps;
      const r = audit(PG, SHIPPED, 0, dS, 0, 12);
      if (!bestS || r.sunPen < bestS.pen) bestS = { d: dS, pen: r.sunPen, gap: r.sunGap };
      const dP = (i / 36) * pp;
      const r2 = audit(PG, SHIPPED, 0, 0, dP, 12);
      if (!bestP || r2.ringPen < bestP.pen) bestP = { d: dP, pen: r2.ringPen, gap: r2.ringGap };
    }
    const at0 = audit(PG, SHIPPED, 0, 0, 0, 12);
    console.log(`  sun : derived -> pen ${at0.sunPen.toFixed(3)}m | best at ${bestS.d.toFixed(2)} deg = ${(bestS.d / ps).toFixed(3)} pitch -> pen ${bestS.pen.toFixed(3)}m`);
    console.log(`  ring: derived -> pen ${at0.ringPen.toFixed(3)}m | best at ${bestP.d.toFixed(2)} deg = ${(bestP.d / pp).toFixed(3)} pitch -> pen ${bestP.pen.toFixed(3)}m`);
  }
} else if (process.argv.includes('--sweep')) {
  for (const wf of [0.24, 0.21, 0.19, 0.17, 0.15]) {
    for (const rf of [1.7, 1.5, 1.3]) {
      report(`widthFrac ${wf}  rootFactor ${rf}`, { widthFrac: wf, rootFactor: rf, addIn: 0.95, dedOut: 1.15 });
    }
  }
} else {
  report('SHIPPED: trapezoid ring teeth, shipped sun phase', SHIPPED);
  report('FIX 1 only: shipped ring teeth, corrected sun phase',
    { ...SHIPPED, sunPhase: 'fixed' });
  report('FIX 1 + 2: true internal involute ring, corrected sun phase',
    { kind: 'involute', sunPhase: 'fixed' });
  report('PROPOSED: internal involute, 0.70m stub addendum, corrected sun phase',
    { kind: 'involute', sunPhase: 'fixed', addI: 0.70 });
}

console.log('\npen = deepest metal into metal, radially, in modules. 0.000 is the only pass.');
console.log('gap = tightest air at the mesh; near 0 means flanks kissing, which is the target.');

/* Where does the ring bite, and does a shorter ring tooth clear it? Reports the
   radius on the PLANET at which the deepest interference happens, against that
   planet's base circle -- below the base circle teethPath has no involute left
   to give, so a ring tooth reaching past it is interfering with a wall. */
if (process.argv.includes('--ring')) {
  for (const addI of [1.00, 0.90, 0.85, 0.80, 0.75, 0.70]) {
    console.log(`\nring addendum ${addI.toFixed(2)}m inward, true internal involute`);
    for (const PG of SETS) {
      let worst = null;
      for (const Q of QS) {
        const r = audit(PG, { kind: 'involute', sunPhase: 'fixed', addI }, Q);
        if (!worst || r.ringPen > worst.ringPen) worst = r;
      }
      const tag = `(${PG[0]},${PG[1]},${PG[2]})x${PG[3]}`.padEnd(14);
      const where = worst.ringPen > 0
        ? `bites at R=${worst.ringAt.toFixed(2)} (base circle ${worst.rb.toFixed(2)}, root ${worst.rr.toFixed(2)})`
        : 'clear';
      console.log(`  ${tag} pen ${worst.ringPen.toFixed(3)}m gap ${worst.ringGap.toFixed(3)}m  ${where}`);
    }
  }
}
