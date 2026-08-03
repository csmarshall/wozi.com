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
/* The settings moved to config.js (#40), so the suite reads BOTH files. It has
   to: TRAIN is derived from the active person's links now, and its length feeds
   the tooth total each chain is dealt against, and therefore the geometry -- a
   suite that only read index.html would be measuring a train whose size it could
   no longer see. */
const CFG_SRC = fs.readFileSync(path.join(__dirname, '..', 'config.js'), 'utf8');

/* ---- extraction: pull the real thing out of the real page ---------------- */

function grabNumber(name) {
  const m = SRC.match(new RegExp('\\b' + name + '\\s*=\\s*(-?[0-9]+(?:\\.[0-9]+)?)'));
  if (!m) throw new Error('constant not found in index.html: ' + name);
  return parseFloat(m[1]);
}

function grabBlockFrom(src, where, decl, open, close) {
  const i = src.indexOf(decl);
  if (i < 0) throw new Error('block not found in ' + where + ': ' + decl);
  let j = src.indexOf(open, i), depth = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === open) depth++;
    else if (src[k] === close) { depth--; if (depth === 0) return src.slice(i, k + 1); }
  }
  throw new Error('unterminated block: ' + decl);
}
function grabBlock(decl, open, close) {
  return grabBlockFrom(SRC, 'index.html', decl, open, close);
}

const page = (function build() {
  const consts = ['MODULE', 'TOOTH_ADD', 'TOOTH_DED', 'TOOTH_ROOT_MIN', 'BAND_RISE',
    'BAND_DEPTH', 'RIM_UNDER_BAND', 'BASELINE_MID', 'ROOT_MARGIN', 'MIN_MODULE',
    'TEETH_MIN', 'TEETH_MAX', 'TEETH_SLACK', 'TEETH_HOST',
    'ANG_MIN', 'ANG_MAX', 'BAND_MAX', 'ENDS_MAX',
    /* RING_STUB governs the mesh this suite's headline test is named after, and
       was the one constant kept as a copy here instead of read from the page.
       Mutating index.html alone used to leave every test green while 10 of 19
       sets fouled (#51). */
    'RING_STUB'];
  const decls = consts.map(n => 'const ' + n + ' = ' + grabNumber(n) + ';').join('\n');
  /* The tooth total is derived from a chain's length now, so it is read the same
     way the page computes it rather than scraped as a literal -- a suite that
     hard-codes a number the page derives is exactly the drift this file exists to
     prevent. */
  /* Comments are stripped first: a retired wheel is commented out rather than
     deleted, and counting its slug would inflate the train's length -- which
     feeds the tooth total, so the error would land in the geometry. */
  /* TRAIN is no longer a literal -- it is built from the active person's links
     in config.js. Count them there, still stripping comments first, because a
     retired wheel is commented out rather than deleted and counting its slug
     would inflate the train's length. That length feeds the tooth total, so the
     error would land in the geometry rather than anywhere obvious.

     COUNTED PER PERSON, NOT OVER THE WHOLE BLOCK. It used to be one count across
     every chain, guarded by an assertion that there was exactly one -- which was
     honest only while that held. A second chain means only ONE person is ever on
     stage at a time, so summing them would measure a train the page never builds.
     Every chain is now measured on its own, and the deal tests below run against
     each of them: the geometry has to be legal for whoever is on stage, and the
     shortest chain is the one that strains the bounds. */
  const peopleBlock = grabBlockFrom(CFG_SRC, 'config.js', 'PEOPLE:', '[', ']')
    .replace(/\/\*[\s\S]*?\*\//g, '');
  /* Split on the top-level objects inside PEOPLE -- one per person. Depth is
     walked rather than regexed because each person's `links` array holds objects
     of its own, and a non-greedy brace match would end at the first inner one. */
  const personBlocks = [];
  {
    let depth = 0, start = -1;
    for (let k = 0; k < peopleBlock.length; k++) {
      const c = peopleBlock[k];
      if (c === '{') { if (depth === 0) start = k; depth++; }
      else if (c === '}') { depth--; if (depth === 0) personBlocks.push(peopleBlock.slice(start, k + 1)); }
    }
  }
  if (!personBlocks.length) throw new Error('no people found in config.js PEOPLE');
  /* Count `href:`, NOT `slug:` -- a person carries a slug of their own as well
     as one per link, so counting slugs would report one wheel too many per
     person and inflate its tooth total. Only links have an href. */
  const trainLens = personBlocks.map(b => (b.match(/href:/g) || []).length);
  trainLens.forEach((n, i) => {
    if (!n) throw new Error('person ' + i + ' in config.js PEOPLE has no links');
  });
  const src = decls + '\n'
    + grabBlock('const PLANETARY_FLAVOURS =', '[', ']') + ';\n'
    + grabBlock('const RAVIGNEAUX_MENU =', '[', ']') + ';\n'
    + grabBlock('function planetaryBore(', '{', '}') + '\n'
    + grabBlock('function planetaryMenuFor(', '{', '}') + '\n'
    /* The end-drift cap is a FUNCTION of chain length now, not a constant, and
       it is the page's own -- executed here rather than re-derived, so the
       bearing test below measures the rule that ships. */
    + 'const TEETH_MEAN = ' + grabNumber('TEETH_MEAN') + ';\n'
    + grabBlock('function endsCapFor(', '{', '}') + '\n'
    + 'return { planetaryBore, planetaryMenuFor, RAVIGNEAUX_MENU, PLANETARY_FLAVOURS, '
    + 'endsCapFor, TEETH_MEAN, '
    + consts.join(', ') + ' };';
  const built = new Function('enumeratePlanetaries', src)(enumeratePlanetaries);
  /* One entry per chain, in PEOPLE order. The page has no TEETH_SUM constant any
     more -- the total is a CHAIN's overall length and a combined stage has several,
     so dealTeeth() computes round(TEETH_MEAN * n) per chain. Same derivation here,
     with TEETH_MEAN read out of the page rather than retyped. */
  built.TRAIN_LENS = trainLens;
  built.TEETH_SUMS = trainLens.map(n => Math.round(grabNumber('TEETH_MEAN') * n));
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

/* ---- 0. the split between page and config -------------------------------- */

test('no setting is defined in both index.html and config.js', () => {
  /* The whole point of #40's split is that each value has exactly ONE home.
     A copy is the failure mode that matters: edit one, forget the other, and
     the page ships something nobody chose -- and because index.html reads the
     config at load, the copy that wins is not the one you edited. Assert it
     directly rather than trusting review. */
  const names = ['SERVICES', 'PEOPLE', 'PAIR_SLOTS', 'PAIRS', 'SINGLES',
    'BRAND', 'PILL_STACK', 'WHEEL_POOL', 'ACCENTS'];
  const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '');
  const page = strip(SRC), cfg = strip(CFG_SRC);
  names.forEach(n => {
    /* In index.html these must appear only as `const NAME = CONF.NAME` reads,
       never as an authored literal. */
    const authored = new RegExp('const\\s+' + n + '\\s*=\\s*[\\[{]');
    ok(!authored.test(page),
      n + ' is authored as a literal in index.html — it belongs in config.js only');
    ok(cfg.indexOf(n + ':') >= 0, n + ' is missing from config.js');
  });
});

test('config.js is a plain script that assigns WOZI_CONFIG', () => {
  /* It must not be a module and must not defer: index.html reads WOZI_CONFIG
     while building the train, so anything that delays it breaks the page. */
  ok(/window\.WOZI_CONFIG\s*=/.test(CFG_SRC), 'config.js does not assign window.WOZI_CONFIG');
  ok(!/\bexport\b/.test(CFG_SRC.replace(/\/\*[\s\S]*?\*\//g, '')),
    'config.js uses export — it is loaded as a plain script, so it must not be a module');
  ok(/<script src="\.\/config\.js"><\/script>/.test(SRC),
    'index.html does not load config.js');
  ok(SRC.indexOf('config.js') < SRC.indexOf('support.js'),
    'config.js must be loaded BEFORE support.js');
});

test('config.js is named in the deploy whitelist', () => {
  /* The deploy publishes an explicit list of paths, so a file in the repo does
     NOT reach the web by existing. If config.js is missing from it the page
     still renders a turning machine with no links, and only says so in the
     console -- a failure a screenshot would happily pass. */
  const wf = fs.readFileSync(
    path.join(__dirname, '..', '.github', 'workflows', 'deploy.yml'), 'utf8');
  ok(/\bconfig\.js\b/.test(wf), 'config.js is not published by .github/workflows/deploy.yml');
});

test('every chain is counted on its own, never summed across people', () => {
  /* This replaces the old "exactly one person" tripwire, which fired the day
     Harper was added and demanded exactly this: only one chain is ever on stage,
     so a single count across the whole list would measure a train the page never
     builds, and the tooth total is derived from that length -- the error lands in
     the geometry rather than anywhere visible.
     The check is that the per-person split agrees with the independent
     slug-minus-href headcount. If the brace walker ever mis-splits, these two
     disagree and the deal tests below are silently measuring the wrong trains. */
  const block = grabBlockFrom(CFG_SRC, 'config.js', 'PEOPLE:', '[', ']')
    .replace(/\/\*[\s\S]*?\*\//g, '');
  const people = (block.match(/\bslug:/g) || []).length - (block.match(/\bhref:/g) || []).length;
  eq(page.TRAIN_LENS.length, people,
    'the per-person split disagrees with the headcount in config.js');
  eq(page.TRAIN_LENS.reduce((a, b) => a + b, 0), (block.match(/href:/g) || []).length,
    'the per-person link counts do not add up to every link in PEOPLE');
});

test('an empty train does not throw — a missing config degrades, it does not blank', () => {
  /* #53. Four documents promise "the machine still turns, on unlinked wheels".
     It did not: with no config, TRAIN is empty, every draw in dealTeeth is
     rejected (Math.max.apply(null, []) is -Infinity, always below host), and
     execution reached TRAIN[0].teeth and threw. It is a module-load IIFE, so
     the whole script aborted and NOTHING rendered. CI cannot see this case --
     it asserts config.js is 200 and parses -- so the suite has to. */
  const fn = grabBlock('(function dealTeeth()', '{', '}');
  const run = new Function(`
    const TRAIN = [];
    const TEETH_MIN = ${page.TEETH_MIN}, TEETH_MAX = ${page.TEETH_MAX};
    const TEETH_SLACK = ${page.TEETH_SLACK}, TEETH_HOST = ${page.TEETH_HOST};
    const TEETH_MEAN = ${grabNumber('TEETH_MEAN')}, FORCE_FAMILY = null;
    const smallestBlankHolding = () => ${page.TEETH_MIN};
    ${fn})();
    return 'ok';`);
  let out;
  try { out = run(); } catch (e) { throw new Error('dealTeeth threw on an empty train: ' + e.message); }
  eq(out, 'ok', 'dealTeeth did not complete on an empty train');
});

test('a service the active person does not have is never seated on a wheel', () => {
  /* #53. config.js states "a service named here but absent from the active
     person's links is simply skipped". It was not -- solve() seated PAIRS and
     SINGLES without checking them against the person, and renderVals() then read
     SITES[g.slug].label unguarded, crashing the page 2000 times out of 2000.
     This matters now: #39 is shipped and adding a person is a config edit.
     Replays the real seating block against a person missing three services. */
  /* Anchor on the cache wrapper, not on the first declaration inside it — the
     seating is wrapped in `if (!this._slugFor) {` since #55, so slicing from
     the inner line yields an unmatched brace. */
  const i = SRC.indexOf('if (!this._slugFor) {');
  const j = SRC.indexOf('const g = [], strands = []', i);
  ok(i > 0 && j > i, 'could not find the slug-seating block in index.html');
  const frag = SRC.slice(i, j);
  const seated = new Function(`
    const PAIR_SLOTS = [[0,1],[3,4]];
    const PAIRS = [['linkedin','github'], ['instagram','threads']];
    const SINGLES = ['bluesky','mail','reddit'];
    const SITES = { p: { linkedin:{}, github:{}, bluesky:{}, mail:{} } };   /* 5-link person */
    const TRAIN = [1,2,3,4,5].map(() => ({ person: 'p', role: 'link' }));
    const shuffle = (arr) => arr;
    /* the block caches onto \`this\`, so it is called with one (#55) */
    ${frag}
    return Object.values(slugFor).filter(s => s && !SITES.p[s]);`).call({});
  eq(seated.length, 0,
    'seated services the active person does not have: ' + [...new Set(seated)].join(', '));
});

test('every wheel of every chain gets a service seated on it', () => {
  /* The other half of #53, found when Harper's one-link chain was added. A wheel
     with no slug does not crash -- it draws as a blank gear: no badge, no
     engraved handle, no link. Silent, and a screenshot passes it.

     The cause was PAIR_SLOTS naming wheel indices a short chain does not have.
     [0,1] needs two wheels and [3,4] needs five, but an unreachable slot still
     claimed its in-range index, so wheel 0 was withheld from singleSlots while no
     pair could ever be seated there. A one-wheel train lost its only wheel.

     Replays the real seating block against the REAL config -- every person, and
     the actual PAIR_SLOTS/PAIRS/SINGLES -- rather than a fixture, because the
     fixture is what let this through: it only ever modelled a five-wheel train. */
  const conf = (function () {
    const win = {};
    new Function('window', CFG_SRC)(win);
    return win.WOZI_CONFIG;
  })();
  const i = SRC.indexOf('if (!this._slugFor) {');
  const j = SRC.indexOf('const g = [], strands = []', i);
  ok(i > 0 && j > i, 'could not find the slug-seating block in index.html');
  const frag = SRC.slice(i, j);
  const bad = [];
  (conf.PEOPLE || []).forEach((p) => {
    const links = p.links || [];
    const sites = {};
    links.forEach(l => { sites[l.slug] = {}; });
    const seat = new Function('PAIR_SLOTS', 'PAIRS', 'SINGLES', 'SITES', 'TRAIN', 'shuffle', `
      ${frag}
      return slugFor;`);
    const slugFor = seat.call({}, conf.PAIR_SLOTS, conf.PAIRS, conf.SINGLES,
      { [p.slug]: sites }, links.map(l => ({ slug: l.slug, person: p.slug, role: 'link' })), (arr) => arr);
    for (let k = 0; k < links.length; k++) {
      if (!slugFor[k]) bad.push(p.slug + ': wheel ' + k + ' of ' + links.length
        + ' has no service seated on it — it draws as a blank gear');
    }
    Object.keys(slugFor).forEach(k => {
      if (slugFor[k] && !sites[slugFor[k]]) {
        bad.push(p.slug + ': seated "' + slugFor[k] + '", which this person does not have');
      }
      if (+k >= links.length) {
        bad.push(p.slug + ': seated a service on wheel ' + k + ', past the end of a '
          + links.length + '-wheel train');
      }
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

/* The three tests below all execute the REAL fit expression, sliced out of
   index.html and run with inputs of our choosing. They are not a model of it --
   a copy of that formula here is exactly the drift this file exists to stop. */
function fitRule() {
  /* Anchored on WHEEL_CROSS_MAX, which exists once and only inside fitStage.
     Anything anchored on the deal constants beside TEETH_MEAN would match their
     module-level declarations instead, and slice in a thousand lines of unrelated
     code. */
  const i = SRC.indexOf('const WHEEL_CROSS_MAX =');
  const j = SRC.indexOf('const root = document.documentElement.style;', i);
  ok(i > 0 && j > i, 'could not find the fit computation in index.html');
  const frag = SRC.slice(i, j);
  const LINK_SHARE = grabNumber('LINK_SHARE'), CROSS_BLEED = grabNumber('CROSS_BLEED');
  /* NOMINAL_SPAN is computed at module scope from the module, the tooth count the
     deal aims at and the bearing range, so it is an input to the sliced
     expression rather than part of it. EXECUTED out of index.html, not
     re-typed -- if the derivation there changes, this follows it. */
  const spanFn = new Function('MODULE', 'TEETH_MEAN', 'ANG_MIN', 'ANG_MAX',
    'NOMINAL_CHAIN',
    'return ' + grabBlock('const NOMINAL_SPAN =', '(', ')').replace(/^const NOMINAL_SPAN =\s*/, '') + '()');
  const NOMINAL_SPAN = spanFn(page.MODULE, grabNumber('TEETH_MEAN'),
    page.ANG_MIN, page.ANG_MAX, Math.max(...page.TRAIN_LENS));
  const fn = new Function('MODULE', 'TOOTH_ADD', 'TRAIN', 'NOMINAL_SPAN',
    'longAvail', 'crossAvail', 'longSolved', 'crossSolved', `
    const LINK_SHARE = ${LINK_SHARE}, CROSS_BLEED = ${CROSS_BLEED};
    ${frag}
    return { fit, wheelSpan, NOMINAL_SPAN, WHEEL_CROSS_MAX };`);
  return (n, longAvail, crossAvail, longSolved, crossSolved) => {
    const train = Array.from({ length: n }, () => ({ teeth: page.TEETH_MAX }));
    return fn(page.MODULE, page.TOOTH_ADD, train, NOMINAL_SPAN,
      longAvail, crossAvail, longSolved, crossSolved);
  };
}

/* One `const NAME = ...;` declaration, verbatim from index.html. For the
   one-line derivations the builder closes over: executing the page's line is
   the difference between measuring what ships and measuring a copy of it. */
function grabDecl(decl) {
  const i = SRC.indexOf(decl);
  if (i < 0) throw new Error('declaration not found in index.html: ' + decl);
  const j = SRC.indexOf(';', i);
  if (j < 0) throw new Error('unterminated declaration: ' + decl);
  return SRC.slice(i, j + 1);
}

/* Executes the real TRAIN builder out of index.html rather than modelling it.
   Returns the bridges it filled in as well as the wheels: the two are built
   together, and a test that only saw the array could not tell an idler apart
   from the chain it feeds. Every value the builder closes over is handed in
   from the page rather than re-typed -- MAX_IDLERS is read out of index.html,
   and CHAIN_ORDER and SPINE_LEN are the page's OWN LINES, executed against the
   fixture. SPINE_LEN used to be re-derived here, which is the one thing this
   file forbids: a suite holding its own copy of a derivation passes happily
   while the page computes something else. */
function buildTrain(people) {
  const expr = grabBlock('const TRAIN = (function', '(', ')');
  const bridges = [];
  const built = new Function('STAGE', 'MAX_IDLERS', 'BRIDGES',
    grabDecl('const CHAIN_ORDER =') + '\n'
    + grabDecl('const SPINE_LEN =') + '\n'
    + 'return { train: ' + expr.replace(/^const TRAIN = /, '') + '(), order: CHAIN_ORDER };')(
    { people: people }, grabNumber('MAX_IDLERS'), bridges);
  return { train: built.train, bridges, order: built.order };
}

test('every TRAIN entry names its parent, and the parents form one tree', () => {
  const { train } = buildTrain([{ slug: 'p', links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] }]);
  const roots = train.filter(t => t.parent === null || t.parent === undefined);
  eq(roots.length, 1, 'a train must have exactly one root');
  const bad = [];
  train.forEach((t, i) => {
    if (t.parent === null) return;
    if (!(t.parent >= 0 && t.parent < train.length)) bad.push(`wheel ${i} parent ${t.parent} is out of range`);
    if (t.parent === i) bad.push(`wheel ${i} is its own parent`);
  });
  /* Walk to the root from every wheel; a cycle never terminates. */
  train.forEach((t, i) => {
    let hops = 0, at = i;
    while (train[at].parent !== null && hops <= train.length) { at = train[at].parent; hops++; }
    if (hops > train.length) bad.push(`wheel ${i} does not reach the root — cycle`);
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('every TRAIN entry names its person and its role', () => {
  const { train } = buildTrain([{ slug: 'harper', links: [{ slug: 'a' }, { slug: 'b' }] }]);
  const bad = [];
  train.forEach((t, i) => {
    if (t.person !== 'harper') bad.push(`wheel ${i} person is ${t.person}, want harper`);
    if (t.role !== 'link') bad.push(`wheel ${i} role is ${t.role}, want link`);
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('no deal decides adjacency by array index', () => {
  /* Wheels are only ever confused with the ones they MESH, and on a tree that is
     the parent, not the previous array slot. Each of these three lines is a place
     where i-1 used to stand in for "next to me". */
  const bad = [];
  const checks = [
    ['dealTeeth twins rule', /cut\[i\]\s*===\s*cut\[i\s*-\s*1\]/],
    ['dealAngles drift walk', /rOf\(TRAIN\[i\s*-\s*1\]\)/],
    ['dealColours hue separation', /pick\[i\s*-\s*1\]/]
  ];
  checks.forEach(([what, re]) => {
    if (re.test(SRC)) bad.push(what + ' still compares against index i-1');
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the ends-apart rule is expressed in leaves, not array positions', () => {
  /* "The two ends of the train repel each other, so the run reads as a line of
     machinery rather than a closed ring." A tree has more than two ends. */
  ok(!/oi === 0 && i === TRAIN\.length - 1/.test(SRC),
    'ENDS_APART still tests the first and last array positions');
  ok(/isLeaf/.test(SRC), 'solve() does not compute leaves for the ends-apart rule');
});

test('the ends-apart rule means the spine\'s extremities, not any two leaves', () => {
  /* Read as "any two leaves" the rule over-applies the moment the tree is bushy:
     two chains hanging off one spine are both leaves, and they are MEANT to sit
     one bridge apart rather than be shoved a further ENDS_APART from each other.
     What that looks like from outside is the nudge loop growing the centre
     distance by 12% over and over until something lands. */
  const i = SRC.indexOf('const isEnd =');
  ok(i > 0, 'solve() no longer names the machine\'s extremities');
  ok(/WHO\.slug/.test(SRC.slice(i, i + 200)),
    'the extremities are not restricted to the spine, so every pair of leaves on '
    + 'a branched stage is pushed ENDS_APART');
});

test('every non-spine chain is reached through at least one idler', () => {
  /* Chains never mesh directly -- the bridge is what makes the drive legible. */
  ok(/role:\s*'idler'/.test(SRC), 'no idler role is ever assigned');
  ok(/MIN_IDLERS/.test(SRC), 'there is no floor on the number of idlers in a bridge');
  const { train, bridges } = buildTrain([
    { slug: 'a', links: [{ slug: 'p' }, { slug: 'q' }, { slug: 'r' }] },
    { slug: 'b', links: [{ slug: 's' }] }
  ]);
  eq(bridges.length, 1, 'the second chain got no bridge');
  const MIN = grabNumber('MIN_IDLERS');
  ok(bridges[0].idlers.length >= MIN,
    `bridge carries ${bridges[0].idlers.length} idlers, floor is ${MIN}`);
  /* Walk from the driven chain's first wheel back to the root: it must pass
     through idlers and never mesh a link of another chain directly. */
  let at = train[bridges[0].head].parent, hops = 0, seen = 0;
  while (at !== null && hops++ <= train.length) {
    if (train[at].role === 'idler') seen++;
    else break;
    at = train[at].parent;
  }
  ok(seen >= MIN, `the driven chain meshes a linked wheel after ${seen} idlers`);
  ok(at !== null && train[at].role === 'link' && train[at].person === 'a',
    'the bridge does not land on the spine');
});

test('a parent always appears earlier in TRAIN than its children', () => {
  /* solve() derives a wheel from g[t.parent] out of the wheels it has ALREADY
     placed. A forward reference reads undefined and the branch lands wherever
     the last iteration happened to leave it -- silently, with no error. The
     spine is emitted first for exactly this reason, so the check has to run on
     a stage where the spine is NOT the first person in config order. */
  const { train } = buildTrain([
    { slug: 'short', links: [{ slug: 's' }] },
    { slug: 'long', links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] }
  ]);
  const bad = [];
  train.forEach((t, i) => {
    if (t.parent === null) return;
    if (t.parent >= i) bad.push(`wheel ${i} (${t.role}) names parent ${t.parent}, which is not placed yet`);
  });
  eq(train.filter(t => t.parent === null).length, 1, 'a bridged stage must have exactly one root');
  eq(train[0].person, 'long', 'the spine is not emitted first');
  ok(bad.length === 0, bad.join('\n      '));
});

test('an idler never carries a service, a badge or an engraving', () => {
  /* A ghost is anonymous by design language; that is the whole reason the bridge
     is made of them rather than of an unowned coloured wheel, which would look
     exactly like the blank-gear defect in #65. */
  const i = SRC.indexOf('if (!this._slugFor) {');
  const j = SRC.indexOf('const g = [], strands = []', i);
  ok(/t\.role !== 'link'/.test(SRC.slice(i, j)),
    'the seating block does not exclude idlers, so one could acquire a slug');
  const { train } = buildTrain([
    { slug: 'a', links: [{ slug: 'p' }, { slug: 'q' }] },
    { slug: 'b', links: [{ slug: 's' }] }
  ]);
  const bad = [];
  train.filter(t => t.role === 'idler').forEach((t, k) => {
    if (t.slug) bad.push(`idler ${k} carries slug ${t.slug}`);
    if (t.person) bad.push(`idler ${k} claims to belong to ${t.person}`);
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the bridge bearing is relative to the stage axis, never absolute', () => {
  /* The page rotates the whole train by _axisRot in portrait. A bridge expressed
     in screen degrees would stay horizontal and cross the SHORT axis -- the same
     failure as #67. */
  const i = SRC.indexOf('BRIDGE_BEARING');
  ok(i > 0, 'no BRIDGE_BEARING is defined');
  const near = SRC.slice(i, i + 600);
  ok(/_axisRot/.test(near), 'BRIDGE_BEARING is not expressed relative to _axisRot');
});

test('a chain that opts out of bridging is a root, and keeps no idlers', () => {
  /* `bridge: false` is a per-person setting in config.js and says "no drive",
     not "no position": the chain stays a root, and solve() still has to place it
     clear of the others -- every root but the first resolved to (0,0) before
     this task, which drew the second chain on top of the first. */
  const { train, bridges } = buildTrain([
    { slug: 'a', links: [{ slug: 'p' }, { slug: 'q' }, { slug: 'r' }] },
    { slug: 'b', bridge: false, links: [{ slug: 's' }] }
  ]);
  eq(train.filter(t => t.role === 'idler').length, 0,
    'an unbridged chain still built idlers');
  eq(bridges.length, 1, 'an unbridged chain is not registered, so nothing places it');
  eq(bridges[0].idlers.length, 0, 'an unbridged chain claims idlers');
  eq(train[bridges[0].head].parent, null, 'an unbridged chain is not a root');
  ok(/const free = /.test(SRC),
    'solve() has no branch for a root that is not the first wheel, so it would '
    + 'resolve to (0,0) on top of the spine');
});

/* ---- the real solver, executed against a stage of our choosing ------------ */

/* EXECUTES solve() ITSELF, sliced out of index.html. Everything above tests the
   TRAIN builder, which is a tree; where two chains END UP is a question only the
   solver can answer, and "chains do not overlap" is a statement about exactly
   that. It closes over nothing the page does not hand it: the deals, the two
   bridge lookups and the segment helpers are all executed out of index.html too.
   No DOM is touched -- solve() reads the viewport only through _axisRot and
   _idlerN, and both are supplied, which is the same thing fitStage() does. */
function runSolve(people, opts) {
  opts = opts || {};
  const { train, bridges, order } = buildTrain(people);
  const MODULE = page.MODULE, TEETH_MEAN = grabNumber('TEETH_MEAN');
  /* Real deals, so the geometry under test is geometry the page can produce. */
  new Function('TRAIN', 'TEETH_MIN', 'TEETH_MAX', 'TEETH_SLACK', 'TEETH_HOST',
    'TEETH_MEAN', 'FORCE_FAMILY', 'smallestBlankHolding',
    grabBlock('(function dealTeeth()', '{', '}') + ')();')(
    train, page.TEETH_MIN, page.TEETH_MAX, page.TEETH_SLACK, page.TEETH_HOST,
    TEETH_MEAN, null, () => page.TEETH_MIN);
  new Function('TRAIN', 'MODULE', 'ANG_MIN', 'ANG_MAX', 'BAND_MAX', 'endsCapFor',
    grabBlock('(function dealAngles()', '{', '}') + ')();')(
    train, MODULE, page.ANG_MIN, page.ANG_MAX, page.BAND_MAX, page.endsCapFor);

  const lookups = grabDecl('const BRIDGE_FROM =') + '\n'
    + grabBlockFrom(SRC, 'index.html', 'BRIDGES.forEach(b => {', '{', '}') + ');';
  const body = grabBlock('  solve() {', '{', '}').replace(/^\s*solve\(\)\s*/, '');
  /* CHAIN_RANK is the page's own line too, run against the order buildTrain got
     from executing the page's CHAIN_ORDER -- not a second sort of the fixture. */
  const CHAIN_RANK = new Function('CHAIN_ORDER',
    grabDecl('const CHAIN_RANK =') + '\n'
    + grabBlockFrom(SRC, 'index.html', 'CHAIN_ORDER.forEach((p, k) =>', '{', '}')
    + ');\n return CHAIN_RANK;')(order);
  const sites = {};
  people.forEach(p => (p.links || []).forEach(l => {
    (sites[p.slug] = sites[p.slug] || {})[l.slug] = {};
  }));
  const solve = new Function('TRAIN', 'BRIDGES', 'MODULE', 'TOOTH_ADD',
    'TEETH_MEAN', 'MIN_IDLERS', 'MAX_IDLERS', 'CLEARANCE', 'ENDS_APART',
    'ANG_MIN', 'ANG_MAX', 'CHAIN_RANK', 'WHO', 'PAIR_SLOTS', 'PAIRS', 'SINGLES',
    'SITES', 'console', `
    ${grabBlock('function segCross(', '{', '}')}
    ${grabBlock('function segDist(', '{', '}')}
    ${lookups}
    return function () ${body};`);
  const warns = [];
  const ctx = opts.ctx || {};
  ctx.props = { shuffle: false };
  ctx.state = { theme: 'light' };
  ctx._axisRot = opts.axisRot || 0;
  ctx._idlerN = opts.idlerN === undefined ? grabNumber('MAX_IDLERS') : opts.idlerN;
  ctx._tight = opts.tight === undefined ? 1 : opts.tight;
  ctx._spreadBoost = 1;
  ctx._solved = null;
  const solved = solve(train, bridges, MODULE, page.TOOTH_ADD, TEETH_MEAN,
    grabNumber('MIN_IDLERS'), grabNumber('MAX_IDLERS'), grabNumber('CLEARANCE'),
    grabNumber('ENDS_APART'), page.ANG_MIN, page.ANG_MAX, CHAIN_RANK,
    order[0] || { slug: '' }, [], [], [], sites,
    { warn: (m) => warns.push(m), error: (m) => warns.push(m) }).call(ctx);
  return { solved, train, bridges, warns, ctx, order };
}

/* Which chain a placed wheel belongs to: an idler belongs to the chain it
   feeds, which is where it sits in the layout. */
const chainOfWheel = (train, w) => w.person != null ? w.person : train[w.i].bridge;

/* Every pair of wheels from DIFFERENT chains that are not meshed, and by how
   much their tip circles interpenetrate. Meshed pairs are excluded by their
   parentage, not by chain: a bridge idler meshes the wheel it hangs off, and
   that wheel is on another chain by definition. */
function crossChainFouls(train, solved) {
  const g = solved.gears, out = [];
  const parent = {};
  g.forEach(w => { parent[w.i] = train[w.i].parent; });
  for (let p = 0; p < g.length; p++) {
    for (let q = p + 1; q < g.length; q++) {
      if (chainOfWheel(train, g[p]) === chainOfWheel(train, g[q])) continue;
      const d = Math.hypot(g[p].x - g[q].x, g[p].y - g[q].y);
      if (d >= g[p].ro + g[q].ro) continue;
      /* meshed, by whichever direction the parentage runs -- including the
         re-parenting solve() does when an idler is parked */
      if (Math.abs(d - (g[p].r + g[q].r)) < 0.5) continue;
      out.push(`${chainOfWheel(train, g[p])} wheel ${g[p].i} × `
        + `${chainOfWheel(train, g[q])} wheel ${g[q].i} overlap by `
        + (g[p].ro + g[q].ro - d).toFixed(1));
    }
  }
  return out;
}

/* Three chains whose PEOPLE order is deliberately NOT their length order, so a
   layout that follows config order sorts differently from one that follows
   chain length. Four when the cascade itself is under test. */
const THREE = [
  { slug: 'mid', links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] },
  { slug: 'tiny', links: [{ slug: 'd' }] },
  { slug: 'spine', links: [1, 2, 3, 4, 5, 6, 7].map(n => ({ slug: 's' + n })) }
];

test('chains are laid out longest first, in order, across the cross axis', () => {
  /* Charles, 2026-08-02: "lay them out in order of how many entries they have,
     longest first, then descending, top to bottom in landscape, and the
     equivalent along the cross axis in portrait". PEOPLE order is arbitrary the
     moment there are three chains, and until this rule the second and third
     both hung off the spine and arrived in the SAME row, ordered by nothing.
     Measured along the bridge direction, which is what "top to bottom" means
     once the stage rotates: the bridges all run one way, perpendicular to the
     spine and relative to it. */
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, train, order } = runSolve(THREE, { axisRot: rot });
    eq(order.map(p => p.slug).join(','), 'spine,mid,tiny',
      'CHAIN_ORDER is not longest-first');
    const dir = (rot + 90) * Math.PI / 180;
    const along = {};
    solved.gears.forEach(w => {
      if (w.person == null) return;                 /* idlers span two rows */
      (along[w.person] = along[w.person] || []).push(w.x * Math.cos(dir) + w.y * Math.sin(dir));
    });
    let last = -Infinity, lastSlug = 'the top edge';
    order.forEach(p => {
      const v = along[p.slug].reduce((a, b) => a + b, 0) / along[p.slug].length;
      if (!(v > last)) {
        bad.push(`at axisRot ${rot}: ${p.slug} (${(p.links || []).length} wheels) `
          + `sits at ${v.toFixed(0)} along the bridge axis, not past ${lastSlug} `
          + `at ${last.toFixed(0)}`);
      }
      last = v; lastSlug = p.slug;
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('no wheel of one chain ever overlaps a wheel of another', () => {
  /* Charles, 2026-08-02: "they shouldn't overlap right". Nothing guaranteed it
     across chains -- the attachment search checked as far as the chain head and
     no further, and the per-wheel nudge plants a wheel wherever it ran out of
     swing. Run against real deals, many times, because the teeth and the
     bearings are what decide whether a chain fits where the anchor put it. */
  const bad = [];
  for (let trial = 0; trial < 60 && bad.length === 0; trial++) {
    [0, 90].forEach(rot => {
      [1, 2].forEach(n => {
        const { solved, train, warns } = runSolve(THREE, { axisRot: rot, idlerN: n });
        crossChainFouls(train, solved).forEach(f =>
          bad.push(`axisRot ${rot}, ${n} idler(s): ` + f));
        warns.forEach(w => bad.push(`axisRot ${rot}, ${n} idler(s): warned "${w}"`));
      });
    });
  }
  ok(bad.length === 0, bad.slice(0, 5).join('\n      '));
});

test('no chain head is ever dropped at the origin', () => {
  /* The cascade path the bridge exists to remove: a head whose host is not on
     stage keeps x = y = 0 and draws on top of the spine's first wheel. Only
     TRAIN[0] belongs at the origin. */
  const bad = [];
  for (let trial = 0; trial < 40; trial++) {
    const { solved, bridges } = runSolve(THREE, { axisRot: trial % 2 ? 90 : 0 });
    const at = {};
    solved.gears.forEach(w => { at[w.i] = w; });
    bridges.forEach(b => {
      const w = at[b.head];
      if (!w) return bad.push(`chain ${b.person}'s head is not placed at all`);
      if (!isFinite(w.x) || !isFinite(w.y)) bad.push(`chain ${b.person}'s head is at (${w.x}, ${w.y})`);
      if (Math.hypot(w.x, w.y) < 1e-9) bad.push(`chain ${b.person}'s head fell back to the origin`);
    });
  }
  ok(bad.length === 0, [...new Set(bad)].join('\n      '));
});

test('an exhausted anchor search refuses to bridge, and says so', () => {
  /* Charles, 2026-08-02: a bridge that cannot be placed without crossing another
     run REFUSES -- the chain is placed undriven instead, exactly as `bridge:
     false` places it. The old code kept `cands[0]` whatever happened: an anchor
     known to foul, handed to a nudge bounded at BRIDGE_SWING, which then planted
     the wheel wherever it ran out. That is the one rule this solver exists to
     enforce, loosened in silence. A chain turning up undriven is the acceptable
     cost; a bridge drawn across another run is not.
     Forced by asking for a clearance nothing can satisfy, so EVERY candidate is
     rejected for every chain. */
  const { solved, train, bridges, warns } = runSolve(THREE, { tight: 400 });

  const anchor = warns.filter(w => /no clear bridge anchor/.test(w));
  ok(anchor.length > 0,
    'every candidate was rejected and nothing was said: ' + (warns[0] || '(silence)'));
  ok(/candidates rejected/.test(anchor[0]) && /fouled a wheel/.test(anchor[0]),
    'the warning does not say why the candidates were rejected: ' + anchor[0]);
  ok(/chain "/.test(anchor[0]), 'the warning does not name the chain: ' + anchor[0]);
  ok(/refusing to bridge/.test(anchor[0]),
    'the warning does not say the bridge was refused: ' + anchor[0]);

  /* NO BRIDGE GEOMETRY IS EMITTED. Not a parked surplus idler -- none at all. */
  const idlers = solved.gears.filter(w => w.role === 'idler');
  eq(idlers.length, 0,
    'a refused bridge still drew ' + idlers.length + ' idler(s): '
    + idlers.map(w => 'wheel ' + w.i).join(', '));

  /* AND THE CHAIN IS STILL PLACED. Refusing the bridge must not cost the chain
     its position: every wheel of every chain is on stage, and no head fell back
     to the origin the way an unplaced root does. */
  const placed = {};
  solved.gears.forEach(w => { placed[w.i] = w; });
  const bad = [];
  train.forEach((t, i) => {
    if (t.role !== 'link') return;
    const w = placed[i];
    if (!w) return bad.push(`${t.person} wheel ${i} was not placed at all`);
    if (!isFinite(w.x) || !isFinite(w.y)) bad.push(`${t.person} wheel ${i} is at (${w.x}, ${w.y})`);
  });
  bridges.forEach(b => {
    const w = placed[b.head];
    if (w && Math.hypot(w.x, w.y) < 1e-9) {
      bad.push(`chain ${b.person}'s head fell back to the origin`);
    }
  });
  ok(bad.length === 0, bad.join('\n      '));

  /* AND IT IS PLACED CLEAR. Measured against the REAL tip circles, not the
     absurd clearance that forced the refusal -- the point of refusing is that
     what arrives is a composition, not a pile. */
  const fouls = crossChainFouls(train, solved);
  ok(fouls.length === 0, 'refused chains overlap: ' + fouls.join('; '));
});

test('a bridge anchor survives the idler count dropping under it', () => {
  /* _bridgeAt is decided once and cached across resizes (#55), while nIdle falls
     to one on a narrow cross axis. An anchor on a SECOND idler therefore named a
     wheel that is no longer placed after the flip: gi[host] === -1, and the chain
     hanging off it resolved to (0,0) -- the overlap this bridge removes, arriving
     by the back door. Anchors are chosen with two idlers in mesh, then the same
     instance is re-solved with one, exactly as fitStage does it. */
  const bad = [];
  for (let trial = 0; trial < 20; trial++) {
    const ctx = {};
    runSolve(THREE, { axisRot: 0, idlerN: 2, ctx });
    const { solved, train, bridges, warns } = runSolve(THREE, { axisRot: 0, idlerN: 1, ctx });
    warns.forEach(w => bad.push('after the drop to one idler: ' + w));
    crossChainFouls(train, solved).forEach(f => bad.push('after the drop: ' + f));
    Object.keys(ctx._bridgeAt || {}).forEach(person => {
      const k = ctx._bridgeAt[person] && ctx._bridgeAt[person].at;
      if (k == null) return;
      if (train[k].role !== 'idler') return;
      /* which position it holds within its own bridge -- only the ones below
         MIN_IDLERS stay in mesh at every viewport */
      const b = bridges.filter(br => br.idlers.indexOf(k) >= 0)[0];
      const slot = b ? b.idlers.indexOf(k) : -1;
      if (slot >= grabNumber('MIN_IDLERS')) {
        bad.push(`chain ${person} is anchored on idler slot ${slot}, which parks`);
      }
    });
  }
  ok(bad.length === 0, [...new Set(bad)].slice(0, 5).join('\n      '));
});

test('a bridge idler is drawn at the same opacity as every other ghost', () => {
  /* An idler is emitted from solved.gears, NOT from the ghosts layer -- it has
     to mesh, and that layer is parallax-scaled 0.94. So it missed the layer's
     own opacity and was drawn at 1.0 over ghostSvg's palette, which is dimmed by
     a factor measured UNDERNEATH that opacity: about 5.5:1 against the pale
     page, darker and higher in contrast than any of the linked wheels the
     machine is actually about. The number must be the SAME number, not a second
     opinion about it. */
  ok(/ghostOpacity\(\)\s*\{/.test(SRC), 'there is no single source for the ghost opacity');
  const ghosts = SRC.slice(SRC.indexOf("h('div', { key: 'ghosts'"), SRC.indexOf("key: 'shadows'"));
  ok(/opacity: this\.ghostOpacity\(\)/.test(ghosts),
    'the ghost layer no longer takes its opacity from ghostOpacity()');
  const art = SRC.slice(SRC.indexOf("key: 'shadows'"));
  ok(/role === 'idler' \? this\.ghostOpacity\(\)/.test(art),
    'a bridge idler is drawn without the ghost layer\'s opacity, so it reads as '
    + 'the most prominent wheel on the page');
  ok(/filter\(g => g\.role !== 'idler'\)/.test(art),
    'the cast-shadow layer still draws under the idlers — background machinery '
    + 'that casts a full-strength shadow reads heavier than the wheel casting it');
});

test('the end-drift floor clears the widest step the deal can actually produce', () => {
  /* endsCapFor's floor was the NOMINAL wheel: 27.6 units. The wheels are dealt,
     not nominal, and two 19-tooth blanks stand 133 apart -- their shallowest
     step is 32.2, so an odd-step chain dealt at the top of the range still
     missed the cap and fell through to the closest-draw fallback. Runs the real
     dealAngles on the widest two-wheel chain the deal can produce and asserts
     the result is LEGAL, not merely assigned. */
  const fn = grabBlock('(function dealAngles()', '{', '}');
  const bad = [];
  for (let trial = 0; trial < 200 && bad.length === 0; trial++) {
    const train = [
      { teeth: page.TEETH_MAX, parent: null, person: 'a', role: 'link' },
      { teeth: page.TEETH_MAX - 1, parent: 0, person: 'a', role: 'link' }
    ];
    new Function('TRAIN', 'MODULE', 'ANG_MIN', 'ANG_MAX', 'BAND_MAX', 'endsCapFor',
      `${fn})();`)(train, page.MODULE, page.ANG_MIN, page.ANG_MAX, page.BAND_MAX,
      page.endsCapFor);
    const d = page.MODULE * (train[0].teeth + train[1].teeth) / 2;
    const drift = Math.abs(d * Math.sin(train[1].angle * Math.PI / 180));
    if (drift > page.endsCapFor(2) + 1e-9) {
      bad.push(`a ${train[0].teeth}+${train[1].teeth} chain drifts ${drift.toFixed(1)}, `
        + `past its own cap of ${page.endsCapFor(2).toFixed(1)} — the deal fell `
        + `through to its fallback draw`);
    }
  }
  ok(bad.length === 0, bad.join('\n      '));
});

test('the idler count and the stage rotation agree on which axis is long', () => {
  /* idlerCount() took max/min of the two viewport dimensions while axisRot()
     only turns the stage past h > w * 1.05. Between 1.00 and 1.05 they
     disagreed, and the bridge was then measured across the axis the stage does
     not run along. Asking the rotation itself makes them agree by construction. */
  const i = SRC.indexOf('  idlerCount() {');
  const frag = SRC.slice(i, SRC.indexOf('\n  }', i));
  ok(/this\.axisRot\(\)/.test(frag),
    'idlerCount() does not derive its long axis from axisRot()');
  ok(!/Math\.max\(w, h\)/.test(frag),
    'idlerCount() still calls the larger dimension the long axis, which axisRot() '
    + 'does not between 1.00 and 1.05');
});

test('a combined stage seats every person, each within its own slot range', () => {
  /* PAIR_SLOTS indexes wheels. On a combined stage those indices must be read
     per person -- siblings sit on neighbouring wheels WITHIN a chain, not across
     a boundary into someone else's. */
  const conf = (function () { const w = {}; new Function('window', CFG_SRC)(w); return w.WOZI_CONFIG; })();
  const i = SRC.indexOf('if (!this._slugFor) {');
  const j = SRC.indexOf('const g = [], strands = []', i);
  const frag = SRC.slice(i, j);
  const people = conf.PEOPLE || [];
  const train = [], sites = {};
  people.forEach(p => (p.links || []).forEach(l => {
    train.push({ slug: l.slug, person: p.slug, role: 'link' });
    (sites[p.slug] = sites[p.slug] || {})[l.slug] = {};
  }));
  const seat = new Function('PAIR_SLOTS', 'PAIRS', 'SINGLES', 'SITES', 'TRAIN', 'shuffle',
    `${frag}\n return slugFor;`);
  const slugFor = seat.call({}, conf.PAIR_SLOTS, conf.PAIRS, conf.SINGLES, sites, train, (a) => a);
  const bad = [];
  train.forEach((t, k) => {
    if (!slugFor[k]) bad.push(`${t.person}: wheel ${k} has no service seated on it`);
    else if (!sites[t.person][slugFor[k]]) {
      bad.push(`${t.person}: wheel ${k} seated "${slugFor[k]}", which belongs to someone else`);
    }
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the fit rule does not branch on how many gears are in the chain', () => {
  /* The rule is "a gear has a standard size for this viewport, and shrinks only
     when something physical says it must". Nothing in it may depend on the
     wheel COUNT -- a one-wheel chain and a nine-wheel chain must run identical
     arithmetic. Same solved extents and same largest wheel in, same scale out,
     whatever the length of the array. */
  const fit = fitRule();
  const base = fit(1, 1440, 900, 900, 300).fit;
  const bad = [];
  for (let n = 1; n <= 12; n++) {
    const got = fit(n, 1440, 900, 900, 300).fit;
    if (got !== base) bad.push('chain of ' + n + ' gave fit ' + got + ', chain of 1 gave ' + base);
  }
  ok(bad.length === 0, bad.join('\n      '));
});

test('no chain renders a wheel past the cross-axis guard', () => {
  /* #65. A one-wheel solve makes crossSolved a single diameter, so the band term
     reduces to "a wheel may be CROSS_BLEED of the short axis" and never binds.
     WHEEL_CROSS_MAX is the bound that does. Swept over real viewports and every
     chain length, with the solved extents modelled BOTH as a long chain and as a
     lone wheel, since the guard has to hold either way. */
  const fit = fitRule();
  const VIEWPORTS = [[390, 844], [844, 390], [768, 1024], [1440, 900],
    [2560, 1440], [3440, 1440], [5120, 1440], [7680, 2160]];
  const bad = [];
  for (const [w, h] of VIEWPORTS) {
    const longAvail = Math.max(w, h), crossAvail = Math.min(w, h);
    for (let n = 1; n <= 12; n++) {
      const lone = fit(n, longAvail, crossAvail, 150, 150);
      const chain = fit(n, longAvail, crossAvail, page.MODULE * 16.3 * n, 210);
      for (const r of [lone, chain]) {
        const rendered = r.fit * r.wheelSpan;
        /* The 0.28 floor is a FLOOR and outranks every bound, so it can lift a
           wheel past the guard on an absurdly small cross axis. Assert the
           guard everywhere the floor is not the binding term. */
        if (r.fit <= 0.28) continue;
        if (rendered > r.WHEEL_CROSS_MAX * crossAvail + 1e-6) {
          bad.push(`${w}x${h}, ${n} wheels: rendered ${rendered.toFixed(1)}px `
            + `exceeds ${(r.WHEEL_CROSS_MAX * crossAvail).toFixed(1)}px`);
        }
      }
    }
  }
  ok(bad.length === 0, bad.slice(0, 6).join('\n      '));
});

test('the linked share of the long axis stays width-invariant', () => {
  /* #44's property, which the NOMINAL_SPAN floor must not break. A full chain
     takes LINK_SHARE of the long axis; a short one takes a smaller CONSTANT
     share, with the escape runs covering the difference. What must never happen
     is a share that FALLS as the viewport widens -- that is the 1/W failure that
     shipped three times behind three different ratio ceilings. */
  const fit = fitRule();
  const bad = [];
  for (const n of [1, 2, 4, 7, 9]) {
    const span = n === 1 ? 150 : page.MODULE * 16.3 * n;
    const shares = [1440, 2560, 3440].map(w => {
      const r = fit(n, w, w * 0.5625, span, n === 1 ? 150 : 210);
      return (r.fit * span) / w;
    });
    const spread = Math.max(...shares) - Math.min(...shares);
    if (spread > 0.001) {
      bad.push(`${n} wheels: share of the long axis varies with width `
        + `(${shares.map(s => (s * 100).toFixed(1) + '%').join(', ')})`);
    }
  }
  ok(bad.length === 0, bad.join('\n      '));
});

test('the fit scale has no constant ceiling on the ratio', () => {
  /* #44/#19. A cap on LINK_SHARE * longAvail / longSolved is crossed at SOME
     width, and past it the train is a fixed size whose share falls as 1/W. That
     bug shipped at 1.15, then 1.55, then 1.25 -- three values of the same
     constant, each fixing it and reintroducing it further out. The ceiling is
     gone; this asserts it stays gone, because re-adding one is the natural
     "fix" the next time the wheels look too big. */
  const i = SRC.indexOf('const fit = Math.max(0.28');
  ok(i > 0, 'could not find the fit computation');
  const line = SRC.slice(i, SRC.indexOf(';', i));
  ok(!/GS_MAX/.test(line),
    'a constant ceiling is back in the fit — see #44: cap an absolute size, never a ratio');
  ok(/crossAvail/.test(line), 'the cross-axis guard is missing from the fit');
});

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
      const r = meshEpi.audit(s.pg, { kind: 'involute', sunPhase: 'fixed', addI: page.RING_STUB }, Q, 0, 0, 90);
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

test('the tooth deal always produces a legal train, for every chain', () => {
  /* Run per chain, not once: each person's train has its own length and
     therefore its own tooth total, and a chain short enough to strain the bounds
     would be invisible in a single averaged run. */
  const { TEETH_MIN, TEETH_MAX, TEETH_SLACK, TEETH_HOST } = page;
  const bad = [];
  page.TRAIN_LENS.forEach((len, pi) => {
    const TEETH_SUM = page.TEETH_SUMS[pi];
    let found = 0;
    for (let trial = 0; trial < 4000; trial++) {
      const cut = Array.from({ length: len }, () =>
        TEETH_MIN + Math.floor(Math.random() * (TEETH_MAX - TEETH_MIN + 1)));
      if (Math.abs(cut.reduce((a, b) => a + b, 0) - TEETH_SUM) > TEETH_SLACK) continue;
      if (Math.max.apply(null, cut) < TEETH_HOST) continue;
      let twins = false;
      for (let i = 1; i < cut.length; i++) if (cut[i] === cut[i - 1]) twins = true;
      if (twins) continue;
      found++;
    }
    if (found === 0) bad.push('chain ' + pi + ' (' + len + ' wheels): no legal draw at '
      + 'all -- the deal would fall through to its fallback every load');
    else if (found <= 40) bad.push('chain ' + pi + ' (' + len + ' wheels): only ' + found
      + '/4000 draws are legal; the deal will often exhaust its tries and fall back');
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the tooth deal succeeds on a combined stage, not only on one chain', () => {
  /* The target total is a CHAIN's overall length, and a combined stage has
     several. Summed across the whole array it was a constraint no combined stage
     could ever satisfy -- ten wheels cannot total a seven-wheel target, their
     minimum already exceeds it -- so every draw was rejected, every load fell
     through to the fallback, and ?who=all dealt a flat train of floor-sized
     wheels with one giant at the head. Silent, and a screenshot passes it.

     Runs the REAL dealTeeth against the REAL people, plus the idlers a bridge
     adds, and asserts the result is a legal draw rather than the fallback. */
  const conf = (function () { const w = {}; new Function('window', CFG_SRC)(w); return w.WOZI_CONFIG; })();
  const { train } = buildTrain(conf.PEOPLE || []);
  const fn = grabBlock('(function dealTeeth()', '{', '}');
  const TEETH_MEAN = grabNumber('TEETH_MEAN');
  const deal = new Function('TRAIN', 'TEETH_MIN', 'TEETH_MAX', 'TEETH_SLACK',
    'TEETH_HOST', 'TEETH_MEAN', 'FORCE_FAMILY', 'smallestBlankHolding',
    `${fn})();`);
  const chains = {};
  train.forEach((t, i) => { if (t.role === 'link') (chains[t.person] = chains[t.person] || []).push(i); });
  const bad = [];
  let fell = 0;
  for (let trial = 0; trial < 300; trial++) {
    deal(train, page.TEETH_MIN, page.TEETH_MAX, page.TEETH_SLACK, page.TEETH_HOST,
      TEETH_MEAN, null, () => page.TEETH_MIN);
    const legal = Object.keys(chains).every(k => Math.abs(
      chains[k].reduce((a, i) => a + train[i].teeth, 0)
      - Math.round(TEETH_MEAN * chains[k].length)) <= page.TEETH_SLACK);
    if (!legal) fell++;
    train.forEach((t, i) => {
      if (t.teeth < page.TEETH_MIN || t.teeth > page.TEETH_MAX) {
        bad.push(`wheel ${i} was dealt ${t.teeth}, outside [${page.TEETH_MIN},${page.TEETH_MAX}]`);
      }
    });
    /* The big blank has to be one you can see into: an idler is drawn in the
       background palette with no centre design at all. */
    const big = Math.max(...train.filter(t => t.role === 'link').map(t => t.teeth));
    if (big < page.TEETH_HOST) bad.push(`no LINKED wheel reached TEETH_HOST (largest was ${big})`);
  }
  ok(fell === 0, `${fell}/300 deals fell through to the fallback on the combined `
    + `stage (${train.length} wheels across ${Object.keys(chains).length} chains)`);
  ok(bad.length === 0, [...new Set(bad)].slice(0, 4).join('\n      '));
});

test('the largest blank a deal guarantees can host a planetary', () => {
  const m = page.planetaryMenuFor(page.TEETH_HOST);
  ok(!m.fallback && m.one.length > 0,
    'TEETH_HOST=' + page.TEETH_HOST + ' cannot hold a single-row set, so the '
    + 'force-seat has nowhere honest to put the planetary');
});

test('the bearing deal keeps the train a horizontal line', () => {
  /* Swept over every chain length a page could carry, not just the ones shipped:
     the caps are applied PER CHAIN now, so a length that cannot satisfy them
     leaves that chain's wheels on the deal's fallback draw rather than on a
     legal one -- and until endsCapFor existed, a two-wheel chain was exactly
     such a length and the deal assigned no bearings at all. */
  const { ANG_MIN, ANG_MAX, BAND_MAX, MODULE } = page;
  ok(ANG_MIN > 0 && ANG_MAX > ANG_MIN, 'bearing range is degenerate');
  ok(ANG_MAX <= 45, 'bearings past 45 degrees stack the wheels diagonally');
  const bad = [];
  const lens = [...new Set([...page.TRAIN_LENS, 1, 2, 3, 4, 5, 6, 7, 8, 9])];
  lens.forEach((len) => {
    let legal = 0;
    for (let trial = 0; trial < 2000; trial++) {
      const first = Math.random() < 0.5 ? 1 : -1;
      const ang = [0];
      for (let i = 1; i < len; i++) ang.push(first * (i % 2 ? 1 : -1) * (ANG_MIN + Math.random() * (ANG_MAX - ANG_MIN)));
      let y = 0, lo = 0, hi = 0;
      for (let i = 1; i < len; i++) {
        y += (MODULE * 16) * Math.sin(ang[i] * Math.PI / 180);   /* two mid-size wheels */
        lo = Math.min(lo, y); hi = Math.max(hi, y);
      }
      if (hi - lo <= BAND_MAX && Math.abs(y) <= page.endsCapFor(len)) legal++;
    }
    if (!legal) bad.push('a chain of ' + len + ' wheels: no bearing draw '
      + 'satisfies the drift caps; every load would fall back');
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the bearing deal always assigns a bearing, even with no legal draw', () => {
  /* A filter with no floor. Every draw was either legal or discarded, and 500
     discards in a row left `angle` undefined on every wheel -- which becomes NaN
     coordinates, a NaN fit scale, and `gsr !== this._gsr` true forever because
     NaN never equals itself. The page rendered nothing and spun until React gave
     up on the update depth. Runs the REAL dealAngles against caps it cannot
     possibly satisfy, and asserts it still assigns. */
  const fn = grabBlock('(function dealAngles()', '{', '}');
  const train = [
    { teeth: 16, parent: null, person: 'a', role: 'link' },
    { teeth: 17, parent: 0, person: 'a', role: 'link' },
    { teeth: 15, parent: 1, person: 'a', role: 'link' }
  ];
  new Function('TRAIN', 'MODULE', 'ANG_MIN', 'ANG_MAX', 'BAND_MAX', 'endsCapFor',
    `${fn})();`)(train, page.MODULE, page.ANG_MIN, page.ANG_MAX, 0, () => 0);
  const bad = train.filter((t, i) => typeof t.angle !== 'number' || !isFinite(t.angle));
  ok(bad.length === 0, bad.length + ' of ' + train.length
    + ' wheels were left with no bearing when no draw could satisfy the caps');
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
