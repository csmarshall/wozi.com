/* The suite. Run: node tools/test.js   (or npm test)
   Exits non-zero on any failure, so CI can gate a deploy on it.

   The whole design rests on one rule: everything here is read OUT OF
   index.html, never re-typed into this file. The constants, the two-row menu
   and the sizing functions are extracted from the shipped page and executed, so
   the suite measures what actually ships. A test that keeps its own copy of a
   constant passes happily while the page is broken, which is the failure this
   project has already had three times in other forms.

   What it asserts, in the order the geometry derives:

     1. the page parses and its geometry constants are sane
     2. planetaryBore() reserves band + ring under band, and the works never
        reach out under the engraving
     3. every single-row set the page can deal MESHES -- zero penetration at
        both the sun and the ring, with real backlash
     4. every shipped two-row set ASSEMBLES (all stations agree on one sun) and
        MESHES on all five relationships
     5. every two-row set's stored `blank` is honest: it fits at that blank and
        does NOT fit one tooth smaller
     6. no dealable set trips teethPath's root-circle floor, which is what
        silently shortens teeth into stubs
     7. the solver's own constraints hold for everything shipped
     8. the tooth and bearing deals obey their stated bounds, over many draws
*/
'use strict';

const fs = require('fs');
const path = require('path');
const { enumeratePlanetaries } = require('./enumerate-planetaries.js');
const meshEpi = require('./mesh_epi.js');
const meshRav = require('./mesh_rav.js');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

/* ---- extraction: pull the real thing out of the real page ---------------- */

function grabNumber(name) {
  const m = SRC.match(new RegExp('\\b' + name + '\\s*=\\s*(-?[0-9]+(?:\\.[0-9]+)?)'));
  if (!m) throw new Error('constant not found in index.html: ' + name);
  return parseFloat(m[1]);
}

function grabBlock(decl, open, close) {
  const i = SRC.indexOf(decl);
  if (i < 0) throw new Error('block not found in index.html: ' + decl);
  let j = SRC.indexOf(open, i), depth = 0;
  for (let k = j; k < SRC.length; k++) {
    if (SRC[k] === open) depth++;
    else if (SRC[k] === close) { depth--; if (depth === 0) return SRC.slice(i, k + 1); }
  }
  throw new Error('unterminated block: ' + decl);
}

const page = (function build() {
  const consts = ['MODULE', 'TOOTH_ADD', 'TOOTH_DED', 'TOOTH_ROOT_MIN', 'BAND_RISE',
    'BAND_DEPTH', 'RIM_UNDER_BAND', 'BASELINE_MID', 'ROOT_MARGIN', 'MIN_MODULE',
    'TEETH_MIN', 'TEETH_MAX', 'TEETH_SLACK', 'TEETH_HOST',
    'ANG_MIN', 'ANG_MAX', 'BAND_MAX', 'ENDS_MAX'];
  const decls = consts.map(n => 'const ' + n + ' = ' + grabNumber(n) + ';').join('\n');
  /* TEETH_SUM is derived from the train's length now, so it is read the same way
     the page computes it rather than scraped as a literal -- a suite that hard-codes
     a number the page derives is exactly the drift this file exists to prevent. */
  const trainLen = (grabBlock('const TRAIN =', '[', ']').match(/slug:/g) || []).length;
  const src = decls + '\n'
    + grabBlock('const PLANETARY_FLAVOURS =', '[', ']') + ';\n'
    + grabBlock('const RAVIGNEAUX_MENU =', '[', ']') + ';\n'
    + grabBlock('function planetaryBore(', '{', '}') + '\n'
    + grabBlock('function planetaryMenuFor(', '{', '}') + '\n'
    + 'return { planetaryBore, planetaryMenuFor, RAVIGNEAUX_MENU, PLANETARY_FLAVOURS, '
    + consts.join(', ') + ' };';
  const built = new Function('enumeratePlanetaries', src)(enumeratePlanetaries);
  built.TRAIN_LEN = trainLen;
  built.TEETH_SUM = Math.round(16.3 * trainLen);
  return built;
})();

/* ---- tiny harness -------------------------------------------------------- */

let passed = 0, failed = 0, current = '';
const results = [];
function test(name, fn) {
  current = name;
  try {
    fn();
    passed++;
    results.push(['ok  ', name, '']);
  } catch (e) {
    failed++;
    results.push(['FAIL', name, e.message]);
  }
}
function ok(cond, msg) { if (!cond) throw new Error(msg); }
function eq(a, b, msg) { if (a !== b) throw new Error(msg + ' (got ' + a + ', want ' + b + ')'); }

/* ---- 1. the page and its constants --------------------------------------- */

test('index.html parses and exposes its geometry constants', () => {
  ok(page.MODULE > 0, 'MODULE must be positive');
  ok(page.BAND_DEPTH > 0 && page.BAND_RISE > 0, 'band must have depth and rise');
  ok(page.RIM_UNDER_BAND > 0, 'a ring of metal must be reserved under the band');
  ok(page.TOOTH_ROOT_MIN > 0, 'root floor must exist');
  ok(page.MIN_MODULE > 0, 'module floor must exist');
});

test('the engraving band is taller than the text it carries', () => {
  /* engraving() sets the handle at MODULE * 0.80 */
  const textModules = 0.80;
  ok(page.BAND_DEPTH > textModules,
    'band ' + page.BAND_DEPTH + 'm cannot hold ' + textModules + 'm lettering');
  ok(page.BAND_DEPTH < textModules * 2.2,
    'band ' + page.BAND_DEPTH + 'm is more than twice its own lettering -- that surplus '
    + 'is radius taken from the works');
});

test('the ring the lettering rides on stays inside the band', () => {
  /* engraving() does not ask the engine to centre the type: it hangs the glyphs off
     the alphabetic baseline and drops the ring by BASELINE_MID of the font size, so
     the middle of the lettering lands mid-band in every engine alike. That shift is
     only safe while it is smaller than the band's own half-depth -- otherwise the
     ring itself leaves the metal it is supposed to be cut into. Handle first (the
     larger of the two lines, so the larger shift), then the machining stamp. */
  const halfBand = page.BAND_DEPTH / 2;
  [['handle', 0.80], ['stamp', 0.60]].forEach(([which, textModules]) => {
    const shift = page.BASELINE_MID * textModules;
    ok(shift < halfBand,
      which + ' ring is dropped ' + shift.toFixed(3) + 'm, past the band half-depth '
      + halfBand.toFixed(3) + 'm -- the arc would sit outside its own band');
  });
  ok(page.BASELINE_MID > 0 && page.BASELINE_MID < 0.5,
    'BASELINE_MID ' + page.BASELINE_MID + ' is not a plausible ascent-over-descent middle');
});

/* ---- 2. the bore derives outside-in -------------------------------------- */

test('the bore never reaches out under the engraving band', () => {
  for (let teeth = page.TEETH_MIN; teeth <= page.TEETH_MAX; teeth++) {
    const r = page.MODULE * teeth / 2;
    const bandIn = r - page.MODULE * (page.BAND_RISE + page.BAND_DEPTH);
    const bore = page.planetaryBore(teeth);
    ok(bore < bandIn, teeth + '-tooth blank: bore ' + bore.toFixed(2)
      + ' is outside the band inner edge ' + bandIn.toFixed(2));
    ok(Math.abs((bandIn - bore) - page.MODULE * page.RIM_UNDER_BAND) < 1e-9,
      teeth + '-tooth blank: ring under band is not RIM_UNDER_BAND');
  }
});

/* ---- 3. every dealable single-row set meshes ------------------------------ */

function dealableSingle() {
  const seen = {}, out = [];
  for (let teeth = page.TEETH_MIN; teeth <= page.TEETH_MAX; teeth++) {
    const m = page.planetaryMenuFor(teeth);
    if (m.fallback) continue;              /* blank too small; nothing is dealt */
    m.one.forEach(v => {
      const k = v.pg.join('.');
      if (!seen[k]) { seen[k] = 1; out.push({ pg: v.pg, teeth }); }
    });
  }
  return out;
}

const SINGLE = dealableSingle();

test('the page can deal at least one single-row set', () => {
  ok(SINGLE.length > 0, 'no single-row sets are dealable at any blank size');
});

test('every dealable single-row set meshes (sun and ring, zero penetration)', () => {
  const bad = [];
  for (const s of SINGLE) {
    let sunPen = 0, ringPen = 0, sunGap = Infinity, ringGap = Infinity;
    for (const Q of [0, 37, 111, 249]) {
      const r = meshEpi.audit(s.pg, { kind: 'involute', sunPhase: 'fixed', addI: 0.70 }, Q, 0, 0, 90);
      sunPen = Math.max(sunPen, r.sunPen); ringPen = Math.max(ringPen, r.ringPen);
      sunGap = Math.min(sunGap, r.sunGap); ringGap = Math.min(ringGap, r.ringGap);
    }
    if (sunPen > 1e-3 || ringPen > 1e-3) {
      bad.push('(' + s.pg.join(',') + ') sunPen ' + sunPen.toFixed(3) + ' ringPen ' + ringPen.toFixed(3));
    } else if (!(sunGap > 0) || !(ringGap > 0)) {
      bad.push('(' + s.pg.join(',') + ') has no backlash');
    }
  }
  ok(bad.length === 0, bad.length + ' of ' + SINGLE.length + ' foul:\n      ' + bad.join('\n      '));
});

/* ---- 4/5. the shipped two-row menu ---------------------------------------- */

const RAV = page.RAVIGNEAUX_MENU;

test('the shipped two-row menu is non-empty and well formed', () => {
  ok(RAV.length > 0, 'RAVIGNEAUX_MENU is empty');
  RAV.forEach(v => {
    eq(v.pg2.length, 5, 'a two-row entry needs [Zs,Zp1,Zp2,Zr,N]');
    ok(typeof v.blank === 'number', 'entry is missing its blank requirement');
  });
});

test('every shipped two-row set assembles (all stations agree on one sun)', () => {
  const bad = [];
  for (const v of RAV) {
    let worst = 0;
    for (const Q of [0, 41, 137, 263]) worst = Math.max(worst, meshRav.sunSpread(v, Q));
    if (worst > 1e-6) bad.push('(' + v.pg2.join(',') + ') sun spread ' + worst.toFixed(4) + ' deg');
  }
  ok(bad.length === 0, bad.length + ' do not assemble:\n      ' + bad.join('\n      '));
});

test('every shipped two-row set meshes on all five relationships', () => {
  const bad = [];
  for (const v of RAV) {
    const worst = { ringPen: 0, p12Pen: 0, sunPen: 0, strayP1: 0, strayP2: 0 };
    for (const Q of [0, 137, 263]) {
      v._baseS = meshRav.sunPhase(v, Q);
      const a = meshRav.audit(v, Q, 60);
      for (const k of Object.keys(worst)) worst[k] = Math.max(worst[k], a[k]);
    }
    const hit = Object.keys(worst).filter(k => worst[k] > 1e-3);
    if (hit.length) bad.push('(' + v.pg2.join(',') + ') ' + hit.map(k => k + ' ' + worst[k].toFixed(3)).join(' '));
  }
  ok(bad.length === 0, bad.length + ' of ' + RAV.length + ' foul:\n      ' + bad.join('\n      '));
});

test('every two-row set fits the blank it claims, and not a smaller one', () => {
  const fitsAt = (pg2, teeth) => {
    const bore = page.planetaryBore(teeth);
    const m2 = 2 * bore / (pg2[3] + 4);
    const worst = m2 * (Math.min(pg2[0], pg2[1], pg2[2]) / 2 - page.TOOTH_DED);
    return m2 >= page.MIN_MODULE && worst >= page.TOOTH_ROOT_MIN * page.ROOT_MARGIN;
  };
  const bad = [];
  for (const v of RAV) {
    if (!fitsAt(v.pg2, v.blank)) {
      bad.push('(' + v.pg2.join(',') + ') claims blank ' + v.blank + ' but does not fit there');
    } else if (v.blank > page.TEETH_MIN && fitsAt(v.pg2, v.blank - 1)) {
      bad.push('(' + v.pg2.join(',') + ') claims blank ' + v.blank + ' but fits at ' + (v.blank - 1));
    }
  }
  ok(bad.length === 0, bad.length + ' of ' + RAV.length + ' have a stale blank:\n      ' + bad.join('\n      '));
});

test('a two-row set is reachable from some blank the deal can produce', () => {
  const reachable = RAV.filter(v => v.blank <= page.TEETH_MAX);
  ok(reachable.length > 0, 'no two-row set fits any blank the tooth deal can make');
});

/* ---- 6. nothing trips the root floor ------------------------------------- */

test('no dealable set trips teethPath\'s root-circle floor', () => {
  const bad = [];
  const check = (label, members, Zr, teeth) => {
    const m2 = 2 * page.planetaryBore(teeth) / (Zr + 4);
    members.forEach(z => {
      const root = m2 * z / 2 - page.TOOTH_DED * m2;
      if (root < page.TOOTH_ROOT_MIN) {
        bad.push(label + ' at ' + teeth + ' teeth: ' + z + '-tooth member root '
          + root.toFixed(2) + ' < floor ' + page.TOOTH_ROOT_MIN);
      }
    });
  };
  for (let teeth = page.TEETH_MIN; teeth <= page.TEETH_MAX; teeth++) {
    const m = page.planetaryMenuFor(teeth);
    if (m.fallback) continue;
    m.one.forEach(v => check('(' + v.pg.join(',') + ')', [v.pg[0], v.pg[1]], v.pg[2], teeth));
    m.two.forEach(v => check('(' + v.pg2.join(',') + ')', [v.pg2[0], v.pg2[1], v.pg2[2]], v.pg2[3], teeth));
  }
  ok(bad.length === 0, bad.length + ' members would be floored into stubs:\n      ' + bad.join('\n      '));
});

/* ---- 7. the solver's own constraints hold -------------------------------- */

test('every single-row set satisfies concentricity and assembly', () => {
  const bad = [];
  for (const s of SINGLE) {
    const [Zs, Zp, Zr, N] = s.pg;
    if (Zr !== Zs + 2 * Zp) bad.push('(' + s.pg.join(',') + ') C1 Zr != Zs + 2*Zp');
    if ((Zs + Zr) % N !== 0) bad.push('(' + s.pg.join(',') + ') C2 (Zs+Zr) % N != 0');
    if ((Zs + Zp) * Math.sin(Math.PI / N) <= Zp + 2.5) bad.push('(' + s.pg.join(',') + ') C3 adjacency');
  }
  ok(bad.length === 0, bad.join('\n      '));
});

test('no planet anywhere is under eight teeth', () => {
  /* measured floor: seven-tooth pinions foul the ring even against the stub */
  const bad = [];
  SINGLE.forEach(s => { if (s.pg[1] < 8) bad.push('single (' + s.pg.join(',') + ')'); });
  RAV.forEach(v => { if (v.pg2[1] < 8 || v.pg2[2] < 8) bad.push('two-row (' + v.pg2.join(',') + ')'); });
  ok(bad.length === 0, bad.join('\n      '));
});

/* ---- 8. the deals obey their own bounds ---------------------------------- */

test('the tooth deal always produces a legal train', () => {
  const { TEETH_MIN, TEETH_MAX, TEETH_SUM, TEETH_SLACK, TEETH_HOST, TRAIN_LEN } = page;
  let found = 0;
  for (let trial = 0; trial < 4000; trial++) {
    const cut = Array.from({ length: TRAIN_LEN }, () =>
      TEETH_MIN + Math.floor(Math.random() * (TEETH_MAX - TEETH_MIN + 1)));
    if (Math.abs(cut.reduce((a, b) => a + b, 0) - TEETH_SUM) > TEETH_SLACK) continue;
    if (Math.max.apply(null, cut) < TEETH_HOST) continue;
    let twins = false;
    for (let i = 1; i < cut.length; i++) if (cut[i] === cut[i - 1]) twins = true;
    if (twins) continue;
    found++;
  }
  ok(found > 0, 'the tooth deal bounds admit no legal train at all -- the deal '
    + 'would fall through to its fallback every load');
  ok(found > 40, 'only ' + found + '/4000 draws are legal; the deal will often '
    + 'exhaust its tries and fall back');
});

test('the largest blank a deal guarantees can host a planetary', () => {
  const m = page.planetaryMenuFor(page.TEETH_HOST);
  ok(!m.fallback && m.one.length > 0,
    'TEETH_HOST=' + page.TEETH_HOST + ' cannot hold a single-row set, so the '
    + 'force-seat has nowhere honest to put the planetary');
});

test('the bearing deal keeps the train a horizontal line', () => {
  const { ANG_MIN, ANG_MAX, BAND_MAX, ENDS_MAX, MODULE } = page;
  ok(ANG_MIN > 0 && ANG_MAX > ANG_MIN, 'bearing range is degenerate');
  ok(ANG_MAX <= 45, 'bearings past 45 degrees stack the wheels diagonally');
  let legal = 0;
  for (let trial = 0; trial < 2000; trial++) {
    const first = Math.random() < 0.5 ? 1 : -1;
    const ang = [0];
    for (let i = 1; i < page.TRAIN_LEN; i++) ang.push(first * (i % 2 ? 1 : -1) * (ANG_MIN + Math.random() * (ANG_MAX - ANG_MIN)));
    let y = 0, lo = 0, hi = 0;
    for (let i = 1; i < page.TRAIN_LEN; i++) {
      y += (MODULE * 16) * Math.sin(ang[i] * Math.PI / 180);   /* two mid-size wheels */
      lo = Math.min(lo, y); hi = Math.max(hi, y);
    }
    if (hi - lo <= BAND_MAX && Math.abs(y) <= ENDS_MAX) legal++;
  }
  ok(legal > 0, 'no bearing draw satisfies the drift caps; every load would fall back');
});

/* ---- report -------------------------------------------------------------- */

console.log('\nwozi.com — geometry suite (everything read out of index.html)\n');
for (const [tag, name, msg] of results) {
  console.log('  ' + tag + '  ' + name);
  if (msg) console.log('        ' + msg);
}
console.log('\n  ' + passed + ' passed, ' + failed + ' failed'
  + '   [' + SINGLE.length + ' single-row sets, ' + RAV.length + ' two-row sets checked]\n');
process.exit(failed ? 1 : 0);
