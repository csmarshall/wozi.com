/* Replicates solve()'s placement and phase for the real TRAIN, then measures the
   mesh at every adjacent pair. Numbers, not impressions. */

const { grabNumber } = require('./mesh_extract.js');

const MODULE = grabNumber('MODULE');
/* CLEARANCE and ENDS_APART are in solve units, not pixels (GitHub #99, CL#124).
   Reading them rather than retyping them is what keeps that true here: the
   literals this file used to carry were a second home for the same fact, and a
   second home is where the units drifted apart in the first place. */
const CLEARANCE = grabNumber('CLEARANCE');
const ENDS_APART = grabNumber('ENDS_APART');
/* The root dedendum teethPath actually uses (GitHub #102): this file's `1.15`
   was TOOTH_DED's value before bf16c0c moved it to 1.25 for true involute
   flanks, and nothing here followed. Read, not retyped, so it cannot happen
   again. */
const TOOTH_DED = grabNumber('TOOTH_DED');

const TRAIN = [
  { teeth: 17, angle: 0,   prof: { add: 1.0,  tip: 0.36 } },
  { teeth: 15, angle: 20,  prof: { add: 0.92, tip: 0.38 } },
  { teeth: 18, angle: -24, prof: { add: 0.96, tip: 0.34 } },
  { teeth: 14, angle: 22,  prof: { add: 1.05, tip: 0.31 } },
  { teeth: 17, angle: -20, prof: { add: 0.88, tip: 0.34 } },
  { teeth: 15, angle: 24,  prof: { add: 1.0,  tip: 0.35 } },
  { teeth: 18, angle: -18, prof: { add: 0.9,  tip: 0.4  } },
];

const tight = 1, axisRot = 0;
const g = [];
TRAIN.forEach((t, i) => {
  const prof = t.prof;
  const r = MODULE * t.teeth / 2;
  const ro = r + MODULE * prof.add;
  let x = 0, y = 0, dir = 1, phase = 0, ang = 0;
  if (i > 0) {
    const prev = g[i - 1];
    const d = prev.r + r;
    const base = t.angle + axisRot;
    let placed = false;
    ang = base;
    for (let step = 0; step <= 60 && !placed; step += 4) {
      for (let sgn = 1; sgn >= -1 && !placed; sgn -= 2) {
        const cand = base + sgn * step;
        const a = cand * Math.PI / 180;
        const px = prev.x + d * Math.cos(a), py = prev.y + d * Math.sin(a);
        const clash = g.some((o, oi) => {
          if (oi === i - 1) return false;
          const need = o.ro + ro + CLEARANCE * tight +
                       (oi === 0 && i === TRAIN.length - 1 ? ENDS_APART * tight : 0);
          return Math.hypot(px - o.x, py - o.y) < need;
        });
        if (!clash) { ang = cand; x = px; y = py; placed = true; }
        if (step === 0) break;
      }
    }
    if (!placed) { const a = base * Math.PI / 180; x = prev.x + d * Math.cos(a); y = prev.y + d * Math.sin(a); }
    dir = -prev.dir;
    const pPrev = 360 / prev.teeth, pThis = 360 / t.teeth;
    let u = ((ang - prev.phase) / pPrev) % 1;
    if (u < 0) u += 1;
    phase = ang + 180 - (0.5 - u) * pThis;
  }
  g.push({ i, teeth: t.teeth, prof, r, ro, x, y, dir, phase, ang,
           rr: Math.max(4, r - MODULE * TOOTH_DED) });
});

console.log('per-wheel geometry (MODULE = ' + MODULE + ')');
console.log('  #  teeth   r      tip-radius   root-radius   add    tip(thickness frac)');
g.forEach(k => {
  console.log(`  ${k.i}  ${String(k.teeth).padStart(3)}   ${k.r.toFixed(1).padStart(5)}   ` +
    `${k.ro.toFixed(1).padStart(7)}      ${k.rr.toFixed(1).padStart(6)}      ` +
    `${k.prof.add.toFixed(2)}   ${k.prof.tip.toFixed(2)}`);
});

console.log('\nmesh at each adjacent pair');
console.log('  pair   centre-d   r1+r2    tip-overlap   root-clearance   tooth-arc  space-arc  slack');
let worstSlack = -1e9, bestSlack = 1e9;
for (let i = 1; i < g.length; i++) {
  const A = g[i - 1], B = g[i];
  const d = Math.hypot(B.x - A.x, B.y - A.y);
  const sum = A.r + B.r;
  /* How far A's tip reaches past B's root circle along the line of centres. */
  const overlapAB = (A.ro + B.ro) - d;         // tip circles interpenetration
  const bottomA = (A.ro + B.rr) - d;           // >0 means A's tip is inside B's root circle
  const bottomB = (B.ro + A.rr) - d;
  /* Arc thickness at the pitch circle: tooth = tip * circular pitch. */
  const cp = Math.PI * MODULE;                  // circular pitch, same for all (m*pi)
  const toothA = A.prof.tip * cp, spaceB = (1 - B.prof.tip) * cp;
  const slack = spaceB - toothA;
  worstSlack = Math.max(worstSlack, slack);
  bestSlack = Math.min(bestSlack, slack);
  console.log(`  ${i-1}-${i}    ${d.toFixed(2).padStart(7)}   ${sum.toFixed(2).padStart(6)}   ` +
    `${overlapAB.toFixed(2).padStart(8)}      ${Math.min(bottomA,bottomB).toFixed(2).padStart(8)}      ` +
    `${toothA.toFixed(2).padStart(7)}   ${spaceB.toFixed(2).padStart(7)}   ${slack.toFixed(2).padStart(6)}`);
}
console.log(`\ncircular pitch = pi * MODULE = ${(Math.PI*MODULE).toFixed(2)}px`);
console.log(`tooth thickness as a fraction of pitch ranges ${Math.min(...TRAIN.map(t=>t.prof.tip))} .. ${Math.max(...TRAIN.map(t=>t.prof.tip))}`);
console.log(`a standard gear uses 0.5 (tooth == space). Slack at the mesh ranges ` +
            `${bestSlack.toFixed(2)}px .. ${worstSlack.toFixed(2)}px of empty arc.`);

console.log('\nbearing deflection (how far the solver moved each wheel off its TRAIN angle)');
g.forEach((k, i) => { if (i) console.log(`  wheel ${i}: TRAIN angle ${TRAIN[i].angle}, placed at ${k.ang} (deflected ${k.ang - TRAIN[i].angle})`); });
