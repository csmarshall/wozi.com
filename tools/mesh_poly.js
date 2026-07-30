/* Builds the real tooth outlines for adjacent wheels and measures the mesh:
   does either gear's outline penetrate the other, and how much empty arc sits
   between a tooth and the space it enters. Sweeps candidate tooth thicknesses so
   the fix is chosen from measurement rather than taste. */

const MODULE = 7;

const TRAIN = [
  { teeth: 17, angle: 0,   prof: { add: 1.0,  tip: 0.36 } },
  { teeth: 15, angle: 20,  prof: { add: 0.92, tip: 0.38 } },
  { teeth: 18, angle: -24, prof: { add: 0.96, tip: 0.34 } },
  { teeth: 14, angle: 22,  prof: { add: 1.05, tip: 0.31 } },
  { teeth: 17, angle: -20, prof: { add: 0.88, tip: 0.34 } },
  { teeth: 15, angle: 24,  prof: { add: 1.0,  tip: 0.35 } },
  { teeth: 18, angle: -18, prof: { add: 0.9,  tip: 0.4  } },
];

/* Outline of one gear as a closed polygon, exactly as teethPath draws it:
   root arc, up the flank, across the tip, down the far flank. Root fillet points
   sit at 0.17 and 0.83 of the pitch REGARDLESS of tip, so the tooth is a trapezoid
   with a fixed 66%-of-pitch base and a `tip`-wide top. */
function outline(n, r, add, tipFrac, phaseDeg, cx, cy, arcSteps = 6, baseR0 = 0.17) {
  const m = MODULE;
  const ro = r + m * add, rr = Math.max(4, r - m * 1.15);
  const a = 2 * Math.PI / n;
  const t0 = 0.5 - tipFrac / 2, t1 = 0.5 + tipFrac / 2;
  const r0 = baseR0, r1 = 1 - baseR0;
  const ph = phaseDeg * Math.PI / 180;
  const pts = [];
  const push = (rad, ang) => pts.push([cx + rad * Math.cos(ang + ph), cy + rad * Math.sin(ang + ph)]);
  for (let i = 0; i < n; i++) {
    const b = i * a - 0.5 * a;
    for (let s = 0; s <= arcSteps; s++) push(rr, b + (r1 - 1 + (r0 - (r1 - 1)) * (s / arcSteps)) * a);
    push(ro, b + t0 * a);
    push(ro, b + t1 * a);
  }
  return pts;
}

function inside(pt, poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (((yi > pt[1]) !== (yj > pt[1])) &&
        (pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi)) c = !c;
  }
  return c;
}

function minDist(pa, pb, near) {
  let best = Infinity;
  for (const p of pa) {
    if (Math.hypot(p[0] - near[0], p[1] - near[1]) > 60) continue;
    for (const q of pb) {
      if (Math.hypot(q[0] - near[0], q[1] - near[1]) > 60) continue;
      const d = Math.hypot(p[0] - q[0], p[1] - q[1]);
      if (d < best) best = d;
    }
  }
  return best;
}

function build(tipOverride, addOverride) {
  const g = [];
  TRAIN.forEach((t, i) => {
    const r = MODULE * t.teeth / 2;
    const tipFrac = tipOverride === null ? t.prof.tip : tipOverride;
    const addV = addOverride === undefined || addOverride === null ? t.prof.add : addOverride;
    let x = 0, y = 0, dir = 1, phase = 0, ang = 0;
    if (i > 0) {
      const prev = g[i - 1];
      const d = prev.r + r;
      ang = t.angle;
      const aa = ang * Math.PI / 180;
      x = prev.x + d * Math.cos(aa); y = prev.y + d * Math.sin(aa);
      dir = -prev.dir;
      const pPrev = 360 / prev.teeth, pThis = 360 / t.teeth;
      let u = ((ang - prev.phase) / pPrev) % 1;
      if (u < 0) u += 1;
      phase = ang + 180 - (0.5 - u) * pThis;
    }
    g.push({ i, teeth: t.teeth, r, add: addV, tip: tipFrac, x, y, dir, phase });
  });
  return g;
}

function depthInside(pt, poly) {
  /* Distance from an interior point to the nearest polygon edge = how deep it sits. */
  let best = Infinity;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [x1,y1] = poly[j], [x2,y2] = poly[i];
    const vx = x2-x1, vy = y2-y1, L = vx*vx+vy*vy;
    let t = L ? ((pt[0]-x1)*vx + (pt[1]-y1)*vy)/L : 0;
    t = Math.max(0, Math.min(1, t));
    const d = Math.hypot(pt[0]-(x1+t*vx), pt[1]-(y1+t*vy));
    if (d < best) best = d;
  }
  return best;
}

let BASE_R0 = 0.17;
function audit(tipOverride, label, addOverride) {
  const g = build(tipOverride, addOverride);
  let worstPen = 0, minGap = Infinity, pairsTouching = 0, maxDeep = 0;
  for (let i = 1; i < g.length; i++) {
    const A = g[i - 1], B = g[i];
    const pa = outline(A.teeth, A.r, A.add, A.tip, A.phase, A.x, A.y, 6, BASE_R0);
    const pb = outline(B.teeth, B.r, B.add, B.tip, B.phase, B.x, B.y, 6, BASE_R0);
    const mid = [(A.x + B.x) / 2, (A.y + B.y) / 2];
    let pen = 0, deep = 0;
    for (const p of pa) if (inside(p, pb)) { pen++; deep = Math.max(deep, depthInside(p, pb)); }
    for (const p of pb) if (inside(p, pa)) { pen++; deep = Math.max(deep, depthInside(p, pa)); }
    maxDeep = Math.max(maxDeep, deep);
    const gap = minDist(pa, pb, mid);
    worstPen = Math.max(worstPen, pen);
    minGap = Math.min(minGap, gap);
    if (gap < 1.5) pairsTouching++;
  }
  console.log(`${label.padEnd(24)} pts:${String(worstPen).padStart(3)}  ` +
              `max depth:${maxDeep.toFixed(2).padStart(6)}px  min gap:${minGap.toFixed(2).padStart(6)}px`);
  return { worstPen, minGap, maxDeep };
}

console.log('shipped, for reference');
audit(null, '  shipped');
console.log('\ncandidate: base 48% (r0=0.26), around the chosen point');
for (const [b, tip, add] of [[0.26,0.36,0.90],[0.26,0.36,0.95],[0.26,0.36,1.00],
                             [0.26,0.38,0.90],[0.26,0.34,0.90],[0.24,0.36,0.90],[0.28,0.36,0.90]]) {
  BASE_R0 = b;
  audit(tip, `  base=${((1-2*b)*100).toFixed(0)}% tip=${tip} add=${add}`, add);
}
console.log('\npenetrating pts > 0 means the outlines actually overlap (teeth colliding).');
console.log('min gap is the closest approach between the two outlines at the mesh;');
console.log('near 0 reads as engaged, several px reads as a gap.');
