/* Does a two-row (Ravigneaux) set actually mesh, or does metal pass through
   metal? Same method as mesh_epi.js -- every profile is star-shaped about its
   own centre, so each is indexed once as a radial profile R(theta) and every
   containment test is a table lookup -- but there are now FIVE relationships to
   check per station, not two:

     P2 <-> ring   must mesh
     P1 <-> P2     must mesh          (moving-to-moving, the new one)
     sun <-> P1    must mesh
     P1 <-> ring   must NOT touch     (the inner row has no business out there)
     sun <-> P2    must NOT touch     (nor the outer row in here)

   Reads the assemblable sets emitted by ravigneaux.js.
   Run: EMIT_TO=/tmp/rav.json node tools/ravigneaux.js 35 --emit
        node tools/mesh_rav.js /tmp/rav.json
*/
'use strict';

const PA = 20, ADD = 1.00, DED = 1.25, THICK = 0.495, RING_STUB = 0.70;
const inv = (x) => Math.tan(x) - x;
const D2R = Math.PI / 180, TAU = Math.PI * 2;
const SAMPLES = 720;

function profileFromPoints(pts, period, mode) {
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
  const unset = (v) => (outer ? v < 0 : !isFinite(v));
  for (let k = 0; k < SAMPLES; k++) {
    if (!unset(tab[k])) continue;
    let a = k, b = k;
    while (unset(tab[(a + SAMPLES * 4) % SAMPLES])) a--;
    while (unset(tab[b % SAMPLES])) b++;
    tab[k] = (tab[(a + SAMPLES * 4) % SAMPLES] + tab[b % SAMPLES]) / 2;
  }
  return { at: (a) => tab[idx(a)] };
}

function involuteProfile(n, r) {
  const phi = PA * D2R;
  const ro = r + ADD, rr = Math.max(0.5, r - DED), rb = r * Math.cos(phi);
  const a = TAU / n, psiP = THICK * Math.PI / n;
  const half = (R) => psiP + inv(phi) - inv(Math.acos(Math.min(1, rb / R)));
  const rStart = Math.max(rb, rr + 0.01), hRoot = half(rStart);
  const pts = [], STEPS = 16;
  for (let s = 0; s <= 4; s++) pts.push([-a / 2 + (a / 2 - hRoot) * (s / 4), rr]);
  pts.push([-hRoot, rStart]);
  for (let s = 1; s <= STEPS; s++) { const R = rStart + (ro - rStart) * (s / STEPS); pts.push([-half(R), R]); }
  for (let s = 0; s <= 3; s++) pts.push([-half(ro) + 2 * half(ro) * (s / 3), ro]);
  for (let s = STEPS; s >= 1; s--) { const R = rStart + (ro - rStart) * (s / STEPS); pts.push([half(R), R]); }
  pts.push([hRoot, rStart]);
  for (let s = 0; s <= 4; s++) pts.push([hRoot + (a / 2 - hRoot) * (s / 4), rr]);
  return profileFromPoints(pts, a, 'max');
}

function ringVoidProfile(Zr, Rr) {
  const a = TAU / Zr, phi = PA * D2R, rb = Rr * Math.cos(phi);
  const tip = Rr - RING_STUB, root = Rr + DED;
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

const wrap = (x, p) => ((x % p) + p) % p;

function audit(set, Q, steps) {
  const [Zs, Zp1, Zp2, Zr, N] = set.pg2;
  const Rs = Zs / 2, Rp1 = Zp1 / 2, Rp2 = Zp2 / 2, Rr = Zr / 2;
  const Rc1 = Rs + Rp1, Rc2 = Rr - Rp2, d12 = Rp1 + Rp2;
  const dTheta = Math.acos((Rc1 * Rc1 + Rc2 * Rc2 - d12 * d12) / (2 * Rc1 * Rc2)) / D2R;
  const psi = Math.atan2(Rc2 * Math.sin(dTheta * D2R), Rc2 * Math.cos(dTheta * D2R) - Rc1) / D2R;
  const a1 = 360 / Zp1, a2 = 360 / Zp2, as = 360 / Zs;
  const kP1 = -Zr / Zp1, kP2 = Zr / Zp2, kS = Zr / Zs - 1;
  const baseC = -Q;

  const ring = ringVoidProfile(Zr, Rr);
  const sun = involuteProfile(Zs, Rs);
  const pr1 = involuteProfile(Zp1, Rp1);
  const pr2 = involuteProfile(Zp2, Rp2);

  const PN = 600;
  const sample = (prof) => {
    const out = [];
    for (let i = 0; i < PN; i++) { const th = (i / PN) * TAU; out.push([th, prof.at(th)]); }
    return out;
  };
  const s1 = sample(pr1), s2 = sample(pr2), ss = sample(sun);

  const res = { ringPen: 0, ringGap: Infinity, p12Pen: 0, p12Gap: Infinity,
                sunPen: 0, sunGap: Infinity, strayP1: 0, strayP2: 0 };

  for (let step = 0; step < steps; step++) {
    const tw = (step / steps) * 360;
    const C = baseC - tw;
    const sunRot = (0 + kS * tw) * D2R;   /* baseS added below per set */
    const baseS = set._baseS;
    const sunAng = (baseS + kS * tw) * D2R;

    for (let k = 0; k < N; k++) {
      const A = k * 360 / N;
      const sg1 = C + A, sg2 = sg1 + dTheta;
      const baseP2 = wrap(a2 * (-0.5 + Zr * (Q - A - dTheta) / 360), a2);
      const baseP1 = wrap(psi + a1 * ((psi + 180 - dTheta - baseP2) * Zp2 / 360 - 0.5), a1);
      const b1 = (sg1 + baseP1 + kP1 * tw) * D2R;
      const b2 = (sg2 + baseP2 + kP2 * tw) * D2R;
      const c1x = Rc1 * Math.cos(sg1 * D2R), c1y = Rc1 * Math.sin(sg1 * D2R);
      const c2x = Rc2 * Math.cos(sg2 * D2R), c2y = Rc2 * Math.sin(sg2 * D2R);

      /* P2 against the ring, and against the sun (which it must clear) */
      for (let i = 0; i < PN; i++) {
        const th = s2[i][0] + b2, R = s2[i][1];
        const x = c2x + R * Math.cos(th), y = c2y + R * Math.sin(th);
        const rad = Math.hypot(x, y), ang = Math.atan2(y, x);
        const d = rad - ring.at(ang);
        if (d > 0) res.ringPen = Math.max(res.ringPen, d);
        else res.ringGap = Math.min(res.ringGap, -d);
        const ds = sun.at(ang - sunAng) - rad;
        if (ds > 0) res.strayP2 = Math.max(res.strayP2, ds);
      }
      /* P1 against the sun, and against the ring (which it must clear) */
      for (let i = 0; i < PN; i++) {
        const th = s1[i][0] + b1, R = s1[i][1];
        const x = c1x + R * Math.cos(th), y = c1y + R * Math.sin(th);
        const rad = Math.hypot(x, y), ang = Math.atan2(y, x);
        const ds = sun.at(ang - sunAng) - rad;
        if (ds > 0) res.sunPen = Math.max(res.sunPen, ds);
        else res.sunGap = Math.min(res.sunGap, -ds);
        const dr = rad - ring.at(ang);
        if (dr > 0) res.strayP1 = Math.max(res.strayP1, dr);
        /* and against P2, in P2's own frame */
        const ux = x - c2x, uy = y - c2y;
        const rr2 = Math.hypot(ux, uy);
        if (rr2 < Rp2 + ADD + 0.5) {
          const aa = Math.atan2(uy, ux) - b2;
          const dd = pr2.at(aa) - rr2;
          if (dd > 0) res.p12Pen = Math.max(res.p12Pen, dd);
          else res.p12Gap = Math.min(res.p12Gap, -dd);
        }
      }
    }
  }
  return res;
}

const file = process.argv[2] || '/tmp/rav.json';
const sets = JSON.parse(require('fs').readFileSync(file, 'utf8'));
const QS = [0, 41, 137, 263, 311];

/* the sun clocking each set demands, from station 0 */
function sunPhase(set, Q) {
  const [Zs, Zp1, Zp2, Zr] = set.pg2;
  const Rs = Zs / 2, Rp1 = Zp1 / 2, Rp2 = Zp2 / 2, Rr = Zr / 2;
  const Rc1 = Rs + Rp1, Rc2 = Rr - Rp2, d12 = Rp1 + Rp2;
  const dTheta = Math.acos((Rc1 * Rc1 + Rc2 * Rc2 - d12 * d12) / (2 * Rc1 * Rc2)) / D2R;
  const psi = Math.atan2(Rc2 * Math.sin(dTheta * D2R), Rc2 * Math.cos(dTheta * D2R) - Rc1) / D2R;
  const a1 = 360 / Zp1, a2 = 360 / Zp2, as = 360 / Zs;
  const baseP2 = wrap(a2 * (-0.5 + Zr * (Q - 0 - dTheta) / 360), a2);
  const baseP1 = wrap(psi + a1 * ((psi + 180 - dTheta - baseP2) * Zp2 / 360 - 0.5), a1);
  return wrap(-Q + as * ((180 - baseP1) * Zp1 / 360 - 0.5), as);
}

console.log(`${sets.length} assemblable two-row sets, five relationships each, ${QS.length} clockings, full turn\n`);
console.log('set (sun,P1,P2,ring)xN   P2<->ring        P1<->P2          sun<->P1        strays');
let bad = 0;
for (const set of sets) {
  const r = { ringPen: 0, ringGap: Infinity, p12Pen: 0, p12Gap: Infinity,
              sunPen: 0, sunGap: Infinity, strayP1: 0, strayP2: 0 };
  for (const Q of QS) {
    set._baseS = sunPhase(set, Q);
    const a = audit(set, Q, 90);
    r.ringPen = Math.max(r.ringPen, a.ringPen); r.ringGap = Math.min(r.ringGap, a.ringGap);
    r.p12Pen = Math.max(r.p12Pen, a.p12Pen); r.p12Gap = Math.min(r.p12Gap, a.p12Gap);
    r.sunPen = Math.max(r.sunPen, a.sunPen); r.sunGap = Math.min(r.sunGap, a.sunGap);
    r.strayP1 = Math.max(r.strayP1, a.strayP1); r.strayP2 = Math.max(r.strayP2, a.strayP2);
  }
  const p = set.pg2;
  const fail = r.ringPen > 0.001 || r.p12Pen > 0.001 || r.sunPen > 0.001
            || r.strayP1 > 0.001 || r.strayP2 > 0.001;
  if (fail) bad++;
  console.log(`(${p[0]},${p[1]},${p[2]},${p[3]})x${p[4]}`.padEnd(22)
    + ` ${r.ringPen.toFixed(3)}/${r.ringGap.toFixed(3)}`.padEnd(16)
    + ` ${r.p12Pen.toFixed(3)}/${r.p12Gap.toFixed(3)}`.padEnd(16)
    + ` ${r.sunPen.toFixed(3)}/${r.sunGap.toFixed(3)}`.padEnd(15)
    + ` ${r.strayP1.toFixed(3)}/${r.strayP2.toFixed(3)}` + (fail ? '   <-- FAIL' : ''));
}
console.log(`\n${sets.length - bad} of ${sets.length} clear every relationship. pen/gap in modules; pen 0.000 is the only pass.`);

/* --pass writes the sets that cleared every relationship, as the literal the
   page carries. The solver proposes, the measurement disposes: the failures are
   involute interference (a larger gear's tooth reaching past an 8-tooth pinion's
   base circle, where teethPath has only a straight wall), which no closed-form
   assembly rule predicts -- so the approved list is measured, not derived. */
if (process.argv.includes('--pass')) {
  const clean = [];
  for (const set of sets) {
    const r = { ringPen: 0, p12Pen: 0, sunPen: 0, strayP1: 0, strayP2: 0 };
    for (const Q of QS) {
      set._baseS = sunPhase(set, Q);
      const a = audit(set, Q, 90);
      r.ringPen = Math.max(r.ringPen, a.ringPen); r.p12Pen = Math.max(r.p12Pen, a.p12Pen);
      r.sunPen = Math.max(r.sunPen, a.sunPen);
      r.strayP1 = Math.max(r.strayP1, a.strayP1); r.strayP2 = Math.max(r.strayP2, a.strayP2);
    }
    if (r.ringPen > 0.001 || r.p12Pen > 0.001 || r.sunPen > 0.001
     || r.strayP1 > 0.001 || r.strayP2 > 0.001) continue;
    clean.push({ pg2: set.pg2, blank: set.blank });
  }
  clean.sort((a, b) => a.blank - b.blank || a.pg2[3] - b.pg2[3]);
  const lines = clean.map(c => `  { pg2: [${c.pg2.join(', ')}], blank: ${c.blank} }`);
  require('fs').writeFileSync('/tmp/rav_pass.js', lines.join(',\n'));
  console.error(`\n${clean.length} clean sets written to /tmp/rav_pass.js`);
}
