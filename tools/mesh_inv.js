/* Measures the mesh with true involute flanks, matching teethPath exactly. */
const { grabNumber } = require('./mesh_extract.js');
const MODULE = grabNumber('MODULE'), PA = grabNumber('TOOTH_PA'),
  ADD = grabNumber('TOOTH_ADD'), DED = grabNumber('TOOTH_DED');
const TRAIN = [
  { teeth: 17, angle: 0 }, { teeth: 15, angle: 20 }, { teeth: 18, angle: -24 },
  { teeth: 14, angle: 22 }, { teeth: 17, angle: -20 }, { teeth: 15, angle: 24 },
  { teeth: 18, angle: -18 },
];
const inv = x => Math.tan(x) - x;

function outline(n, r, thick, phaseDeg, cx, cy) {
  const m = MODULE, phi = PA * Math.PI / 180;
  const ro = r + m * ADD, rr = Math.max(4, r - m * DED), rb = r * Math.cos(phi);
  const a = 2 * Math.PI / n, ph = phaseDeg * Math.PI / 180;
  const psiP = thick * Math.PI / n;
  const half = R => psiP + inv(phi) - inv(Math.acos(Math.min(1, rb / R)));
  const rStart = Math.max(rb, rr + 0.01), hRoot = half(rStart);
  const pts = [], STEPS = 14;
  const push = (rad, ang) => pts.push([cx + rad * Math.cos(ang + ph), cy + rad * Math.sin(ang + ph)]);
  for (let i = 0; i < n; i++) {
    const c = i * a;
    for (let s = 0; s <= 4; s++) push(rr, c - a / 2 + (a / 2 - hRoot) * (s / 4));
    if (rStart > rr) push(rStart, c - hRoot);
    for (let s = 1; s <= STEPS; s++) { const R = rStart + (ro - rStart) * (s / STEPS); push(R, c - half(R)); }
    for (let s = 0; s <= 3; s++) push(ro, c - half(ro) + 2 * half(ro) * (s / 3));
    for (let s = STEPS; s >= 1; s--) { const R = rStart + (ro - rStart) * (s / STEPS); push(R, c + half(R)); }
    if (rStart > rr) push(rStart, c + hRoot);
    for (let s = 0; s <= 4; s++) push(rr, c + hRoot + (a / 2 - hRoot) * (s / 4));
  }
  return pts;
}
function insideP(pt, poly) {
  let cnt = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (((yi > pt[1]) !== (yj > pt[1])) && (pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi)) cnt = !cnt;
  }
  return cnt;
}
function depth(pt, poly) {
  let best = Infinity;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [x1, y1] = poly[j], [x2, y2] = poly[i];
    const vx = x2 - x1, vy = y2 - y1, L = vx * vx + vy * vy;
    let t = L ? ((pt[0] - x1) * vx + (pt[1] - y1) * vy) / L : 0;
    t = Math.max(0, Math.min(1, t));
    const dd = Math.hypot(pt[0] - (x1 + t * vx), pt[1] - (y1 + t * vy));
    if (dd < best) best = dd;
  }
  return best;
}
function run(thick, label) {
  const g = [];
  TRAIN.forEach((t, i) => {
    const r = MODULE * t.teeth / 2;
    let x = 0, y = 0, dir = 1, phase = 0, ang = 0;
    if (i) {
      const p = g[i - 1], d = p.r + r; ang = t.angle;
      const aa = ang * Math.PI / 180;
      x = p.x + d * Math.cos(aa); y = p.y + d * Math.sin(aa); dir = -p.dir;
      const pPrev = 360 / p.teeth, pThis = 360 / t.teeth;
      let u = ((ang - p.phase) / pPrev) % 1; if (u < 0) u += 1;
      phase = ang + 180 - (0.5 - u) * pThis;
    }
    g.push({ teeth: t.teeth, r, x, y, dir, phase });
  });
  let pen = 0, maxD = 0, minGap = Infinity;
  for (let i = 1; i < g.length; i++) {
    const A = g[i - 1], B = g[i];
    const pa = outline(A.teeth, A.r, thick, A.phase, A.x, A.y);
    const pb = outline(B.teeth, B.r, thick, B.phase, B.x, B.y);
    const mid = [(A.x + B.x) / 2, (A.y + B.y) / 2];
    for (const p of pa) if (insideP(p, pb)) { pen++; maxD = Math.max(maxD, depth(p, pb)); }
    for (const p of pb) if (insideP(p, pa)) { pen++; maxD = Math.max(maxD, depth(p, pa)); }
    let best = Infinity;
    for (const p of pa) { if (Math.hypot(p[0]-mid[0],p[1]-mid[1]) > 55) continue;
      for (const q of pb) { if (Math.hypot(q[0]-mid[0],q[1]-mid[1]) > 55) continue;
        const dd = Math.hypot(p[0]-q[0],p[1]-q[1]); if (dd < best) best = dd; } }
    minGap = Math.min(minGap, best);
  }
  console.log(`${label.padEnd(26)} penetrating:${String(pen).padStart(4)}  max depth:${maxD.toFixed(2).padStart(6)}px  min gap:${minGap.toFixed(2).padStart(6)}px`);
}
console.log(`involute flanks, ${PA} deg PA, add ${ADD.toFixed(2)}m, ded ${DED.toFixed(2)}m\n`);
for (const t of [0.500, 0.495, 0.485, 0.475, 0.460, 0.440]) run(t, `  thickness ${t.toFixed(3)} of pitch`);
console.log('\n(a real gear is 0.500; less is backlash. min gap ~0 = flanks touching.)');
