/* Is a two-row (Ravigneaux) planetary geometrically possible in one of our
   wheels, and if so which tooth counts?

   Layout, in one plane -- this is the point of Ravigneaux, both rows are visible
   from the front rather than stacked behind each other:

       sun  ->  inner planet (P1)  ->  outer planet (P2)  ->  ring

   P1 never touches the ring and P2 never touches the sun; the two rows mesh with
   each other, which is what makes them counter-rotate (issue #27).

   Everything is in MODULES. Station k puts P1 at angle k*360/N and P2 at that
   angle plus dTheta, where dTheta closes the triangle
   (Rc1, Rc2, Rp1+Rp2) -- the two rows sit at different radii AND different
   angles, so the pair fits in an annulus neither row could span alone.

   Run: node tools/ravigneaux.js [maxZr]
*/
'use strict';

const ADD = 1.00, DED = 1.25;
const RING_STUB = 0.70;          /* the ring's stub addendum, as shipped */
const CLEAR = 0.25;              /* tip clearance we insist on between free parts */
const MIN_TEETH = 8;             /* measured floor: seven-tooth pinions foul the ring */
const MAX_ZR = +(process.argv[2] || 35);

const tip = (z) => z / 2 + ADD;
const root = (z) => z / 2 - DED;

function feasible(Zs, Zp1, Zp2, Zr, N) {
  const Rs = Zs / 2, Rp1 = Zp1 / 2, Rp2 = Zp2 / 2, Rr = Zr / 2;
  const Rc1 = Rs + Rp1;                       /* sun-P1 mesh sets the inner radius */
  const Rc2 = Rr - Rp2;                       /* P2-ring mesh sets the outer radius */
  const d12 = Rp1 + Rp2;                      /* P1-P2 mesh distance */

  /* the triangle has to close, with a little slack so dTheta is not degenerate */
  if (d12 <= Math.abs(Rc2 - Rc1) + 0.15) return null;
  if (d12 >= Rc1 + Rc2 - 0.15) return null;
  const cosD = (Rc1 * Rc1 + Rc2 * Rc2 - d12 * d12) / (2 * Rc1 * Rc2);
  if (cosD <= -1 || cosD >= 1) return null;
  const dTheta = Math.acos(cosD);
  if (dTheta < 12 * Math.PI / 180) return null;   /* rows would visually merge */

  /* P1 must not reach the ring; P2 must not reach the sun */
  if (Rc1 + tip(Zp1) > Rr - RING_STUB - CLEAR) return null;
  if (Rc2 - tip(Zp2) < tip(Zs) + CLEAR) return null;

  /* every station's two planets, then every non-meshing pair checked for collision */
  const pts = [];
  for (let k = 0; k < N; k++) {
    const a = k * 2 * Math.PI / N;
    pts.push({ st: k, row: 1, x: Rc1 * Math.cos(a), y: Rc1 * Math.sin(a), t: tip(Zp1) });
    pts.push({ st: k, row: 2, x: Rc2 * Math.cos(a + dTheta), y: Rc2 * Math.sin(a + dTheta), t: tip(Zp2) });
  }
  let tightest = Infinity;
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const A = pts[i], B = pts[j];
      const meshing = A.st === B.st && A.row !== B.row;   /* the one pair allowed to touch */
      const d = Math.hypot(A.x - B.x, A.y - B.y);
      if (meshing) continue;
      const slack = d - (A.t + B.t) - CLEAR;
      if (slack < 0) return null;
      if (slack < tightest) tightest = slack;
    }
  }
  return { Zs, Zp1, Zp2, Zr, N, dTheta: dTheta * 180 / Math.PI, tightest, Rc1, Rc2 };
}

/* Room, exactly as index.html derives it: blank, less band, less the ring under
   the band. m2 = 2*bore/(Zr+4). A set is only useful if its smallest member
   still has a real root circle and its teeth are big enough to read. */
const MODULE = 7, BAND_RISE = 1.3, BAND_DEPTH = 1.2, RIM_UNDER_BAND = 0.6;
const TOOTH_ROOT_MIN = 4, ROOT_MARGIN = 1.05, MIN_MODULE = 1.8;
const boreOf = (teeth) => MODULE * teeth / 2 - MODULE * (BAND_RISE + BAND_DEPTH) - MODULE * RIM_UNDER_BAND;

function smallestBlankFor(s) {
  for (let teeth = 13; teeth <= 22; teeth++) {
    const m2 = 2 * boreOf(teeth) / (s.Zr + 4);
    const worst = m2 * root(Math.min(s.Zs, s.Zp1, s.Zp2));
    if (m2 >= MIN_MODULE && worst >= TOOTH_ROOT_MIN * ROOT_MARGIN) return teeth;
  }
  return null;
}

const hits = [];
for (let Zr = 24; Zr <= MAX_ZR; Zr++) {
  for (let Zs = MIN_TEETH; Zs <= Zr - 2 * MIN_TEETH; Zs++) {
    for (let Zp1 = MIN_TEETH; Zp1 <= Zr; Zp1++) {
      for (let Zp2 = MIN_TEETH; Zp2 <= Zr; Zp2++) {
        for (const N of [3, 4, 5]) {
          const f = feasible(Zs, Zp1, Zp2, Zr, N);
          if (!f) continue;
          const blank = smallestBlankFor(f);
          if (blank === null) continue;
          hits.push(Object.assign(f, { blank }));
        }
      }
    }
  }
}

hits.sort((a, b) => (a.blank - b.blank) || (b.N - a.N) || (b.tightest - a.tightest));
console.log(`${hits.length} two-row sets are geometrically possible and fit a real blank\n`);
console.log('blank  N  sun  P1  P2  ring   row offset  tightest gap');
const shown = {};
for (const h of hits) {
  const key = h.blank + '.' + h.N;
  shown[key] = (shown[key] || 0) + 1;
  if (shown[key] > 3) continue;            /* a few per (blank, N), not thousands */
  console.log(`  ${String(h.blank).padStart(2)}  ${h.N}  ${String(h.Zs).padStart(3)} ${String(h.Zp1).padStart(3)} ${String(h.Zp2).padStart(3)} ${String(h.Zr).padStart(5)}   ${h.dTheta.toFixed(1).padStart(6)} deg  ${h.tightest.toFixed(2).padStart(6)}m`);
}
const byBlank = {};
hits.forEach(h => { byBlank[h.blank] = (byBlank[h.blank] || 0) + 1; });
console.log('\ncandidates by smallest blank that holds them:');
Object.keys(byBlank).sort((a, b) => a - b).forEach(b => console.log(`  ${b} teeth: ${byBlank[b]}`));
console.log('\nNOT yet checked: the three mesh-phase conditions (sun-P1, P1-P2, P2-ring).');
console.log('P1-P2 is moving-to-moving, which is the one the single-row build never needed.');

/* ---- mesh phases, and which sets actually assemble --------------------------

   Same technique the single row was finally derived with: write each gear's
   position at the line of centres as a fraction of ITS OWN pitch. An external
   pair turns opposite ways, so that pair of fractions sums to a constant; an
   internal pair turns the same way, so theirs differs by a constant. Tooth into
   space is the half-pitch value of that constant.

   Chain, outermost first, because each link pins the next:
     P2 <-> ring   internal  -> fixes baseP2 from the station angle
     P1 <-> P2     external  -> fixes baseP1 from baseP2   (moving-to-moving: new)
     sun <-> P1    external  -> fixes baseS from baseP1

   Every station pins the sun independently, and there is only one sun. So the
   assembly condition is simply that all N stations demand the SAME sun phase.
   Rather than derive that condition in closed form and risk being clever, it is
   computed per station and compared -- if the stations disagree, the set does
   not assemble with equal spacing and is dropped.

   In the page's wheel-relative k factors (page rate = 1 + k, carrier kC = -1):
     P1  k = -Zr/Zp1     P2  k = +Zr/Zp2     sun  k = Zr/Zs - 1
   so the rows counter-rotate and the sun co-rotates with the wheel. */

const D2R = Math.PI / 180;
const wrap = (x, p) => ((x % p) + p) % p;

function phasesFor(s, Q) {
  const { Zs, Zp1, Zp2, Zr, N } = s;
  const Rs = Zs / 2, Rp1 = Zp1 / 2, Rp2 = Zp2 / 2, Rr = Zr / 2;
  const Rc1 = Rs + Rp1, Rc2 = Rr - Rp2, d12 = Rp1 + Rp2;
  const dTheta = Math.acos((Rc1 * Rc1 + Rc2 * Rc2 - d12 * d12) / (2 * Rc1 * Rc2)) / D2R;
  /* angle of the P1->P2 line, measured from the station's own radius */
  const psi = Math.atan2(Rc2 * Math.sin(dTheta * D2R),
                         Rc2 * Math.cos(dTheta * D2R) - Rc1) / D2R;
  const a1 = 360 / Zp1, a2 = 360 / Zp2, as = 360 / Zs;
  const baseC = -Q;
  const out = { dTheta, psi, baseC, stations: [], as, a1, a2 };
  let suns = [];
  for (let k = 0; k < N; k++) {
    const A = k * 360 / N;
    const baseP2 = wrap(a2 * (-0.5 + Zr * (Q - A - dTheta) / 360), a2);
    const baseP1 = wrap(psi + a1 * ((psi + 180 - dTheta - baseP2) * Zp2 / 360 - 0.5), a1);
    const baseS = wrap((baseC + A) + as * ((180 - baseP1) * Zp1 / 360 - 0.5), as);
    out.stations.push({ A, baseP1, baseP2, baseS });
    suns.push(baseS);
  }
  /* do all stations demand the same sun clocking? compare on the circle of as */
  let spread = 0;
  for (const v of suns) {
    let d = Math.abs(wrap(v - suns[0] + as / 2, as) - as / 2);
    if (d > spread) spread = d;
  }
  out.sunSpread = spread;
  out.baseS = suns[0];
  return out;
}

if (process.argv.includes('--phases')) {
  const ok = [];
  for (const h of hits) {
    /* must hold at any carrier clocking, not one convenient one */
    let worst = 0;
    for (const Q of [0, 41, 137, 263]) worst = Math.max(worst, phasesFor(h, Q).sunSpread);
    if (worst < 1e-6) ok.push(Object.assign({}, h, { spread: worst }));
  }
  console.log(`\n${ok.length} of ${hits.length} also ASSEMBLE (all stations agree on one sun phase)\n`);
  const seen = {};
  const menu = [];
  for (const h of ok) {
    const key = [h.Zs, h.Zp1, h.Zp2, h.Zr, h.N].join('.');
    if (seen[key]) continue;
    seen[key] = 1;
    menu.push(h);
  }
  console.log('blank  N  sun  P1  P2  ring   offset   gap');
  menu.slice(0, 24).forEach(h => console.log(
    `  ${String(h.blank).padStart(2)}  ${h.N}  ${String(h.Zs).padStart(3)} ${String(h.Zp1).padStart(3)} ${String(h.Zp2).padStart(3)} ${String(h.Zr).padStart(5)}  ${h.dTheta.toFixed(1).padStart(6)}  ${h.tightest.toFixed(2)}m`));
  const byN = {};
  menu.forEach(h => { byN[h.N] = (byN[h.N] || 0) + 1; });
  console.log('\nassemblable sets by station count:', JSON.stringify(byN));
  const byBlank2 = {};
  menu.forEach(h => { byBlank2[h.blank] = (byBlank2[h.blank] || 0) + 1; });
  console.log('by smallest blank:', JSON.stringify(byBlank2));
}

if (process.argv.includes('--emit')) {
  const seen = {}, menu = [];
  for (const h of hits) {
    let worst = 0;
    for (const Q of [0, 41, 137, 263]) worst = Math.max(worst, phasesFor(h, Q).sunSpread);
    if (worst >= 1e-6) continue;
    const key = [h.Zs, h.Zp1, h.Zp2, h.Zr, h.N].join('.');
    if (seen[key]) continue;
    seen[key] = 1;
    menu.push({ pg2: [h.Zs, h.Zp1, h.Zp2, h.Zr, h.N], blank: h.blank,
                dTheta: +h.dTheta.toFixed(4), gap: +h.tightest.toFixed(3) });
  }
  require('fs').writeFileSync(process.env.EMIT_TO || '/tmp/rav.json', JSON.stringify(menu, null, 1));
  console.error('emitted ' + menu.length + ' assemblable sets');
}
