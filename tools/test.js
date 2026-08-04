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
    /* The one figure on this page stated in RENDERED pixels rather than in
       modules (#76). Read from the page like everything else, so the suite
       measures the bound that ships rather than a copy of it. */
    'PLATE_TOP_CLEAR',
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

test('stage hosts and solo hosts are disjoint, and every person has a solo host', () => {
  /* A HOSTNAME SELECTS A SCOPE, NOT A PERSON. The apex, www and the loopback
     names carry the combined stage; a person's own subdomain carries that person
     alone. The two lists must not overlap, because the resolver checks
     STAGE_HOSTS first -- a name in both would silently mean "everyone" while
     config.js reads as though it meant one person, and only a screenshot would
     ever say so.
     Every person also needs at least one solo host, or their chain is reachable
     only by ?who= and the subdomain they were given does nothing. */
  const conf = (function () { const w = {}; new Function('window', CFG_SRC)(w); return w.WOZI_CONFIG; })();
  ok(Array.isArray(conf.STAGE_HOSTS) && conf.STAGE_HOSTS.length,
    'config.js defines no STAGE_HOSTS, so nothing selects the combined stage');
  const bad = [];
  /* And no two people may claim the same solo host. The resolver takes the FIRST
     match in PEOPLE order, so the second claimant's subdomain silently serves
     somebody else's chain -- a typo in one character of a copied line, and the
     only symptom is a page that looks entirely correct for the wrong person. */
  const claimed = {};
  (conf.PEOPLE || []).forEach(p => {
    if (!(p.hosts || []).length) bad.push(`${p.slug} has no solo host`);
    (p.hosts || []).forEach(h => {
      if (conf.STAGE_HOSTS.indexOf(h) >= 0) bad.push(`${h} is both a stage host and ${p.slug}'s solo host`);
      if (claimed[h]) bad.push(`${h} is a solo host for both ${claimed[h]} and ${p.slug}`);
      else claimed[h] = p.slug;
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('a hostname matching nothing falls back to the combined stage', () => {
  /* THE FALLBACK IS THE SCOPE, NOT PEOPLE[0]. An alternate domain name can be
     added to the distribution long before anyone edits config.js, and until they
     do it matches no list at all. Falling back to the first person would serve
     that new domain one chain and give no sign it was a default; falling back to
     the combined stage serves everyone, which is what an apex is for.
     Executes the real resolver out of index.html against a hostname in neither
     list, rather than restating its order of precedence here. */
  /* The block walker stops on the IIFE's closing brace, so the call that runs it
     is put back here -- the body itself is the page's, unedited. */
  const src = grabBlock('const STAGE = (function () {', '{', '}') + ')();';
  const conf = (function () { const w = {}; new Function('window', CFG_SRC)(w); return w.WOZI_CONFIG; })();
  const run = (host, search) => new Function('CONF', 'location', 'URLSearchParams',
    src + '\n return STAGE;')(conf, { hostname: host, search: search || '' }, URLSearchParams);
  eq(run('nothing-here.example').mode, 'all',
    'an unrecognised hostname does not fall back to the combined stage');
  eq(run(conf.STAGE_HOSTS[0]).mode, 'all', conf.STAGE_HOSTS[0] + ' does not select the combined stage');
  const solo = run((conf.PEOPLE[0].hosts || [])[0]);
  eq(solo.mode, 'solo', "a person's own host does not select them alone");
  eq(solo.people.length, 1, "a person's own host puts more than one chain on stage");
  eq(solo.people[0].slug, conf.PEOPLE[0].slug, "a person's own host selects the wrong person");
  eq(run(conf.STAGE_HOSTS[0], '?who=' + conf.PEOPLE[1].slug).people[0].slug, conf.PEOPLE[1].slug,
    '?who= does not override a stage host');
  /* A ?who= NAMING NOBODY DEFERS TO THE HOSTNAME. It is the one precedence path
     with two defensible answers, so it is the one worth pinning: a stale link,
     a renamed slug or a typed guess should land on whatever that hostname would
     have drawn anyway, not on a fallback that ignores it. A solo host still
     draws its own person; a stage host still draws everyone. */
  const staleSolo = run((conf.PEOPLE[0].hosts || [])[0], '?who=nobody-by-that-name');
  eq(staleSolo.mode, 'solo', 'an unknown ?who= stops a solo host drawing its person');
  eq(staleSolo.people[0].slug, conf.PEOPLE[0].slug,
    'an unknown ?who= makes a solo host draw the wrong person');
  eq(run(conf.STAGE_HOSTS[0], '?who=nobody-by-that-name').mode, 'all',
    'an unknown ?who= stops a stage host drawing the combined stage');
});

test('the person picker is drawn only on the combined stage', () => {
  /* A PERSONAL LINK MUST NOT ADVERTISE EVERYONE ELSE. charles.wozi.com is
     Charles's page, and a menu listing every other person on the domain is a
     disclosure the visitor did not ask for. The existing rule -- hidden while
     there is one person -- extends to "or while the view is deliberately one
     person", and both halves have to be in the same condition.

     THE LIST IS BUILT, NOT READ. This used to be two regexes over the source of
     the block, which is a check on the spelling of a condition rather than on
     what it decides: moving the live test into the comment beside it leaves the
     suite green while the disclosure ships. The block is a plain IIFE over CONF
     and STAGE, so it runs here with both handed in. */
  const src = grabBlock('const togPeople = (function () {', '{', '}') + ')();';
  const run = (n, mode) => new Function('CONF', 'STAGE', src + '\n return togPeople;')(
    { PEOPLE: Array.from({ length: n }, (_, k) => ({ slug: 'p' + k, name: 'Person ' + k })) },
    { mode: mode });
  eq(run(3, 'all').length, 3, 'the combined stage does not offer every person');
  eq(run(3, 'all').map(p => p.href).join(','), '?who=p0,?who=p1,?who=p2',
    'the picker does not link each person by ?who=');
  eq(run(3, 'solo').length, 0,
    'a solo page lists every person on the domain — the disclosure #68 exists to stop');
  eq(run(1, 'all').length, 0, 'the picker draws with nobody to pick');
  eq(run(1, 'solo').length, 0, 'the picker draws on a one-person solo page');
  /* NOBODY IS CURRENT on the combined stage: every entry is a link away from
     what is being looked at, so marking one would tell a screen reader it is
     viewing a person while the page shows the household. */
  ok(run(3, 'all').every(p => p.current === 'false'),
    'the picker marks an entry current on a stage that is showing everyone');
});

test('the rule between the people and the gears is not a link', () => {
  /* IT WAS ONE, AND IT WAS FAILING ON THE SHIPPED PAGE. The separator used to be
     a menu entry -- an <a> with an empty href and no text -- and the menu
     template renders one <a> per entry, so there was no way for it to be
     anything else. `a11y_audit` reads `a[href]` out of the DOM, which the
     panel's display:none does not remove, so it counted as a focusable element
     with no accessible name from the day a second person made the picker draw
     at all.
     Two things have to hold and neither is visible in a screenshot of the closed
     panel: the separator must not be produced by either list, and the template
     must render it as something that cannot take focus. */
  const nav = SRC.slice(SRC.indexOf('<nav aria-label="Table of gears"'),
    SRC.indexOf('</nav>'));
  ok(/<sc-if value="\{\{ togSep \}\}">/.test(nav),
    'the table of gears no longer guards its separator with sc-if');
  const sep = nav.slice(nav.indexOf('<sc-if'), nav.indexOf('</sc-if>'));
  ok(/<div\b/.test(sep) && !/<a\b/.test(sep),
    'the separator between the people and the gears is a link again — it has no '
    + 'accessible name, so it is a focusable element with nothing to announce');
  ok(/aria-hidden="true"/.test(sep), 'the separator is not hidden from the accessibility tree');
  /* And it floats in the gap rather than riding an entry's edge: the gear list
     entries are 9px-rounded pills that are FILLED whenever their kind is the
     active one, and the first of them is active on any page without ?kind=. A
     border on that pill is a line across the top of a block of accent colour,
     not a rule between two groups. */
  ok(!/borderTop/.test(SRC.slice(SRC.indexOf('togList: (function'), SRC.indexOf('toggleMotion:'))),
    'a gear entry carries a borderTop again — the rule belongs in the gap between '
    + 'the lists, not on the edge of a filled pill');
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

test('no two badges on a combined stage answer to the same identity', () => {
  /* #78. Every map behind the magnetic hub caps -- the spring entries, the
     element references, the drag claim, the hover -- was keyed by service slug,
     which is unique only while one chain is on stage. Charles and Harper both
     own a `mail` wheel, so both caps read one spring entry and one hover flag:
     dragging his sent hers out to arm's length on release, and hovering either
     lit both.

     WHAT THIS CAN AND CANNOT SEE, said plainly. It runs the real badgeKey out of
     index.html against the real config and proves the identity is injective over
     every (person, service) the page can seat. It CANNOT prove the render path
     asks it that question rather than passing a bare slug -- that is behaviour in
     a browser, and tools/cap_drag.py is what checks it, by dragging one chain's
     mail cap and measuring the other's. A test here that grepped index.html for
     the call sites would assert on the shape of the source rather than on what it
     does, which is worth less than the harness that already exists.

     The second assertion is what keeps the first from going quietly vacuous: if
     no service is ever on two chains, injectivity is free and this test stops
     meaning anything without failing. */
  const conf = (function () {
    const win = {};
    new Function('window', CFG_SRC)(win);
    return win.WOZI_CONFIG;
  })();
  const line = SRC.slice(SRC.indexOf('const badgeKey ='));
  const badgeKey = new Function(line.slice(0, line.indexOf('\n')) + '\n return badgeKey;')();

  const seen = {}, bySlug = {}, bad = [];
  (conf.PEOPLE || []).forEach(p => {
    (p.links || []).forEach(l => {
      const k = badgeKey(p.slug, l.slug);
      if (seen[k]) bad.push('two badges share the identity "' + k + '": '
        + seen[k] + ' and ' + p.slug + '/' + l.slug);
      seen[k] = p.slug + '/' + l.slug;
      (bySlug[l.slug] = bySlug[l.slug] || []).push(p.slug);
    });
  });
  ok(bad.length === 0, bad.join('\n      '));

  const shared = Object.keys(bySlug).filter(s => bySlug[s].length > 1);
  ok(shared.length > 0,
    'no service is configured on more than one chain, so keying badges by slug '
    + 'alone would collide with nothing and the check above proves nothing — '
    + 'either restore a shared service or retire this test deliberately');
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
    'TARGET_GEAR_PX', 'WHEEL_SPAN',
    'longAvail', 'crossAvail', 'longSolved', 'crossSolved', `
    const LINK_SHARE = ${LINK_SHARE}, CROSS_BLEED = ${CROSS_BLEED};
    ${frag}
    return { fit, wheelSpan: WHEEL_SPAN, NOMINAL_SPAN, WHEEL_CROSS_MAX, TARGET_GEAR_PX };`);
  return (n, longAvail, crossAvail, longSolved, crossSolved) => {
    const train = Array.from({ length: n }, () => ({ teeth: page.TEETH_MAX }));
    return fn(page.MODULE, page.TOOTH_ADD, train, NOMINAL_SPAN,
      grabNumber('TARGET_GEAR_PX'), wheelSpanOf(train),
      longAvail, crossAvail, longSolved, crossSolved);
  };
}

/* The largest wheel a train puts on stage, as index.html's own WHEEL_SPAN line
   computes it, executed against a fixture rather than re-typed here (#47). It
   moved to module scope when the fit stopped sizing a gear as a share of the
   long axis and started drawing it at TARGET_GEAR_PX: two callers divide by it
   now, fitStage() and idlerCount(), and both must be handed the same number this
   file measures. */
function wheelSpanOf(train) {
  return new Function('TRAIN', 'MODULE', 'TOOTH_ADD',
    grabDecl('const WHEEL_SPAN =') + ' return WHEEL_SPAN;')(
    train, page.MODULE, page.TOOTH_ADD);
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
     opinion about it.

     RUN, NOT READ. This used to be four regexes over the render, which is a
     check on how an expression is spelled: rewrite `this.ghostOpacity()` as the
     literal beside it and every one of them still passes while the two numbers
     start drifting apart. The rule has a name now -- wheelOpacity() -- and both
     the ghost layer and the cast shadows derive from it, so it can be lifted and
     ASKED, in both themes, for every kind of wheel the solve produces.

     The theme parameter is optional and names one: the datum's own opacity is
     solved against the LIGHT treatment's contrast whichever theme is on, and it
     asks ghostOpacity() for that reference alpha rather than repeating 0.46. */
  const fns = (theme) => {
    const ctx = {
      state: { theme: theme },
      ghostOpacity: new Function('return function ' + grabBlock('  ghostOpacity(theme) {', '{', '}') + ';')(),
      wheelOpacity: new Function('return function ' + grabBlock('  wheelOpacity(g) {', '{', '}') + ';')()
    };
    return ctx;
  };
  const bad = [];
  ['dark', 'light'].forEach(theme => {
    const c = fns(theme);
    const ghost = c.ghostOpacity.call(c);
    ok(typeof ghost === 'number' && ghost > 0 && ghost < 1,
      theme + ': ghostOpacity() is not an alpha');
    /* An idler is drawn at the ghost layer's own number, not near it. */
    const idler = c.wheelOpacity.call(c, { role: 'idler' });
    if (idler !== ghost) {
      bad.push(`${theme}: an idler is drawn at ${idler} while the ghost layer is at `
        + `${ghost} — a second opinion about how dim a ghost is`);
    }
    /* A linked wheel carries no opacity of its own: the machine is full weight. */
    ['link', undefined].forEach(role => {
      if (c.wheelOpacity.call(c, { role: role }) != null) {
        bad.push(`${theme}: a wheel with role ${role} is dimmed like background machinery`);
      }
    });
    /* AND THE SHADOW LAYER'S OWN PREDICATE, EXECUTED. Re-asking wheelOpacity()
       here would only restate the two answers above and would leave the
       derivation claim -- "the shadows come from this rule rather than testing
       the role a second time" -- untested. The render's filter callback is
       sliced out of index.html and RUN, the way fitRule() runs the real fit
       expression. It is an arrow, so it takes its `this` from the scope it is
       built in: calling the builder on the stub is what binds it. */
    const shad = SRC.slice(SRC.indexOf("h('div', { key: 'shadows'"));
    const m = shad.match(/solved\.gears\.filter\((.*?)\)\.map\(/);
    ok(m, 'could not find the cast-shadow layer\'s gear filter in index.html');
    const filterFn = new Function('return ' + m[1] + ';').call(c);
    const wheels = [{ i: 'idler', role: 'idler' }, { i: 'link', role: 'link' }, { i: 'plain' }];
    const kept = wheels.filter(filterFn).map(g => g.i).join(',');
    if (kept !== 'link,plain') {
      bad.push(`${theme}: the cast-shadow layer keeps [${kept}] — it must draw under `
        + 'every full-weight wheel and under no background machinery');
    }
    if (!/wheelOpacity/.test(m[1])) {
      bad.push('the cast-shadow filter tests something other than wheelOpacity(), so '
        + 'the two rules can drift apart again');
    }
  });
  /* The two themes must not resolve to the same alpha, or the whole per-theme
     derivation above is measuring one number twice. */
  const d = fns('dark'), l = fns('light');
  ok(d.ghostOpacity.call(d) !== l.ghostOpacity.call(l),
    'the ghost opacity is the same in both themes, so this test cannot tell them apart');
  ok(bad.length === 0, bad.join('\n      '));
});

/* chainAxes() lifted out of the page and run against a solve of the test's
   choosing. `this` is the only thing it reads from the component -- _axisRot,
   which is what fitStage() hands solve() too -- so no DOM is needed. */
function chainAxesOf(solved, axisRot, spineSlug) {
  const fn = new Function('WHO',
    'return function ' + grabBlock('  chainAxes(solved) {', '{', '}') + ';')(
    { slug: spineSlug });
  return fn.call({ _axisRot: axisRot }, solved);
}
/* Unsigned angle between two headings, folded to 0..90: an axis and its reverse
   are the same axis. */
const axisOff = (a, b) => {
  const d = Math.abs(((a - b) % 360 + 540) % 360 - 180);
  return d > 90 ? 180 - d : d;
};

/* The page's own crossing predicate, so a test that asks "does this cross that"
   asks it the same way the solver does. */
const segCrossJs = new Function(
  'return ' + grabBlock('function segCross(', '{', '}'))();

/* THE REAL fitEscapes, lifted out of the page and run against a solve of the
   test's choosing. It reads the DOM through exactly two holes -- the stage's
   bounding rect and the viewport size -- so both are handed in and the runs it
   places are the runs the page would place. Scale is deliberately 1: solve units
   and screen pixels then coincide, and a segment can be compared against
   solved.bridgeRuns without a second conversion rule to get wrong.

   GHOST_COLORS is a stand-in of length one. The draw that picks a colour consumes
   one rnd() whatever the array holds, so the geometry downstream of it is
   identical; nothing here looks at a colour. */
function fitEscapesOn(solved, axisRot, spineSlug, margin) {
  margin = margin || 300;
  const fn = new Function('window', 'MODULE', 'GHOST_COLORS', 'segCross',
    'return function ' + grabBlock('  fitEscapes() {', '{', '}') + ';')(
    { innerWidth: solved.w + margin * 2, innerHeight: solved.h + margin * 2 },
    page.MODULE, ['#000'],
    new Function('return ' + grabBlock('function segCross(', '{', '}'))());
  const ctx = {
    _axisRot: axisRot,
    _stageRef: { current: { getBoundingClientRect: () => (
      { width: solved.w, height: solved.h, left: margin, top: margin }) } },
    solve: () => solved,
    chainAxes: new Function('WHO',
      'return function ' + grabBlock('  chainAxes(solved) {', '{', '}') + ';')(
      { slug: spineSlug }),
    rnd: new Function('return function ' + grabBlock('  rnd() {', '{', '}') + ';')(),
    setState: function (s) { this.ghosts = s.ghosts; }
  };
  ctx.ghosts = [];
  fn.call(ctx);
  /* The ghosts are already in solve units -- each run is meshed onto its host
     wheel and grows from its centre. Grouped by the host that spawned it:
     fitEscapes names its wheels 'gh<host><k>'. */
  const runs = {};
  ctx.ghosts.forEach(g => {
    const ei = g.i.slice(2, 3);
    /* `person`, `lead` and `k` come along because fitEscapes records them for the
       datum mark, and a test asking WHICH chain a run belongs to and which end
       it left by would otherwise have to infer it from geometry it is trying to
       measure. */
    (runs[ei] = runs[ei] || []).push({ cx: g.cx, cy: g.cy,
      person: g.person, lead: g.lead, k: g.k });
  });
  return runs;
}

test('escape runs follow each chain axis, never its bridge axis', () => {
  /* A branch has TWO directions: the bridge runs perpendicular to set spacing,
     then the chain runs parallel to the spine. A run that followed the bridge
     would leave by the short axis -- the #10 and #67 failure.

     RUN, NOT READ. This used to be four regexes over the body of fitEscapes,
     including one that matched the ORDER of two `hosts.push(` calls -- which
     asserts how the function is written, not what it places, and passes intact
     through any rewrite that keeps the words. fitEscapesOn() has run the real
     thing since the crossing test was written; this asks it the same questions.

     THE HOST WHEEL IS THE ORIGIN, not the first ghost: the run is a random walk
     of up to seven wheels dealt within 20 degrees of each other, so the heading
     that matters is the one from the wheel it meshes with to where it ended up. */
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, order } = runSolve(THREE, { axisRot: rot });
    const spineSlug = order[0].slug;
    const axes = chainAxesOf(solved, rot, spineSlug);
    const spine = axes.find(c => c.spine);
    const branches = axes.filter(c => !c.spine);
    const runs = fitEscapesOn(solved, rot, spineSlug);
    /* The spine keeps both runs; every other chain gets ONE, on the same side.
       The missing leading run is where the bridge attaches, so a driven chain
       visibly receives its power there. */
    const byPerson = {};
    Object.keys(runs).forEach(ei => {
      const r = runs[ei];
      (byPerson[r[0].person] = byPerson[r[0].person] || []).push(r);
    });
    const spineRuns = byPerson[spine.person] || [];
    if (spineRuns.length !== 2) {
      bad.push(`rot ${rot}: the spine got ${spineRuns.length} escape runs, not a leading `
        + 'and a trailing one');
    } else if (spineRuns.filter(r => r[0].lead).length !== 1) {
      bad.push(`rot ${rot}: the spine's two runs do not leave by opposite ends`);
    }
    branches.forEach(c => {
      const mine = byPerson[c.person] || [];
      if (mine.length !== 1) {
        bad.push(`rot ${rot}: driven chain ${c.person} got ${mine.length} escape runs, not one`);
      } else if (mine[0][0].lead) {
        bad.push(`rot ${rot}: driven chain ${c.person}'s run leaves by the LEADING end, `
          + 'which is the end its bridge arrives at');
      }
    });
    /* And the heading of every run, against its OWN chain's axis rather than
       against one axis for the whole array. The bridge runs at 90 degrees to it,
       which is what a run measured first-to-last across the whole train used to
       follow. */
    axes.forEach(c => {
      const home = {};
      solved.gears.forEach(g => { home[g.i] = g; });
      (byPerson[c.person] || []).forEach(r => {
        const host = r[0].lead ? c.head : c.tail;
        const last = r[r.length - 1];
        const deg = Math.atan2(last.cy - host.cy, last.cx - host.cx) * 180 / Math.PI;
        if (axisOff(deg, c.deg) >= axisOff(deg, c.deg + 90)) {
          bad.push(`rot ${rot}: ${c.person}'s ${r[0].lead ? 'leading' : 'trailing'} run `
            + `leaves at ${deg.toFixed(1)}°, closer to its bridge axis `
            + `(${axisOff(deg, c.deg + 90).toFixed(1)}°) than to its own chain axis `
            + `(${axisOff(deg, c.deg).toFixed(1)}°)`);
        }
        /* Which WAY along that axis, not merely along it: the leading run has to
           run backwards off the head and the trailing one onwards off the tail,
           or the spine grows both tails out of the same end. */
        const want = r[0].lead ? c.deg + 180 : c.deg;
        if (Math.cos((deg - want) * Math.PI / 180) <= 0) {
          bad.push(`rot ${rot}: ${c.person}'s ${r[0].lead ? 'leading' : 'trailing'} run `
            + `leaves at ${deg.toFixed(1)}° when its end points ${want.toFixed(1)}°`);
        }
      });
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('a chain axis is measured from its own linked wheels, never its idlers', () => {
  /* Including an idler drags the axis toward the BRIDGE, which is perpendicular
     to the chain -- for a one-wheel chain it becomes the bridge exactly. That is
     the whole defect: escape runs leaving along the spine-to-branch diagonal. */
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, train, order } = runSolve(THREE, { axisRot: rot });
    const axes = chainAxesOf(solved, rot, order[0].slug);
    eq(axes.length, THREE.length, 'rot ' + rot + ': not every chain has an axis');
    const spine = axes.find(c => c.spine);
    ok(spine && spine.person === order[0].slug, 'rot ' + rot + ': the spine is not the longest chain');
    axes.forEach(c => {
      if (c.wheels.some(w => w.role !== 'link'))
        bad.push(`rot ${rot}: ${c.person}'s axis counts a wheel that is not a link`);
      /* Parallel to the spine, not to the bridge, which runs at rot + 90. */
      if (axisOff(c.deg, rot) >= axisOff(c.deg, rot + 90))
        bad.push(`rot ${rot}: ${c.person} runs closer to the bridge axis `
          + `(${axisOff(c.deg, rot + 90).toFixed(1)}°) than to the stage axis `
          + `(${axisOff(c.deg, rot).toFixed(1)}°)`);
      /* Every chain points the way the spine points, so one run per driven chain
         leaves the same side as the spine's trailing run. */
      if (Math.cos((c.deg - spine.deg) * Math.PI / 180) < 0)
        bad.push(`rot ${rot}: ${c.person} points back against the spine`);
      if (c.wheels.length === 1 && axisOff(c.deg, rot) > 1e-9)
        bad.push(`rot ${rot}: a one-wheel chain measured an axis of its own (${c.deg}) `
          + `instead of falling back to the stage axis (#67)`);
      if (c.spine) return;
      /* What the old code did: first-to-last across everything the chain is
         reached through. It must be measurably more bridge-ward than the answer. */
      const with_ = solved.gears.filter(w => (w.person != null ? w.person : train[w.i].bridge) === c.person);
      const a = with_[0], b = with_[with_.length - 1];
      const naive = Math.atan2(b.cy - a.cy, b.cx - a.cx) * 180 / Math.PI;
      if (axisOff(naive, rot + 90) >= axisOff(c.deg, rot + 90))
        bad.push(`rot ${rot}: ${c.person}'s axis is no further from the bridge with `
          + `its idlers dropped — the idlers are still being counted`);
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('an escape run refuses to cross a bridge, not only another escape run', () => {
  /* `taken` held escape runs only, so a bridge was the ONE run on the page that
     an escape run could be laid straight across without anything noticing --
     bridgeRuns existed, but inside solve(), and never came out. It does not fire
     on any shipped viewport, because a branch's one run leaves the end its bridge
     does NOT arrive at. That is an argument from the current composition, and the
     non-crossing rule is the thing the solver exists to enforce, so this forces
     the geometry instead of trusting the argument: run the real fitEscapes twice
     on the same solve, once with no bridges and once with a bridge laid
     deliberately across the branch's own run, and the run must move.

     Step 3 is what stops this passing vacuously -- it asserts the planted bridge
     really does lie across the run that was placed without it. */
  const bad = [];
  const seg = (p) => ({ x: p.cx, y: p.cy });
  [0, 90].forEach(rot => {
    const { solved, order } = runSolve(THREE, { axisRot: rot });
    const spineSlug = order[0].slug;
    const branches = chainAxesOf(solved, rot, spineSlug).filter(c => !c.spine);
    const clear = fitEscapesOn(Object.assign({}, solved, { bridgeRuns: [] }), rot, spineSlug);
    branches.forEach((c, bi) => {
      /* Which host index this branch's run got: the hosts are the spine's two,
         then one per branch in chainAxes order. */
      const ei = String(2 + bi);
      const run = clear[ei];
      if (!run || !run.length) { bad.push(`rot ${rot}: ${c.person} got no escape run at all`); return; }
      const a = { x: c.tail.cx, y: c.tail.cy };
      const b = { x: run[run.length - 1].cx, y: run[run.length - 1].cy };
      const L = Math.hypot(b.x - a.x, b.y - a.y);
      /* THE BLOCKER IS A REAL BRIDGE, moved -- its length is one this stage
         actually solved, not a number chosen to make the test pass. A bridge is a
         couple of wheel diameters and a run is five to seven wheels, so it spans
         roughly the middle third of the run: wide enough that the chain's own
         axis is refused, narrow enough that the search has somewhere to go. Every
         bridge on the stage is tried, so this is not one lucky length. */
      solved.bridgeRuns.forEach((real, k) => {
        const half = Math.hypot(real[1].cx - real[0].cx, real[1].cy - real[0].cy) / 2;
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        const px = -(b.y - a.y) * half / L, py = (b.x - a.x) * half / L;
        const blocker = [{ cx: mx - px, cy: my - py }, { cx: mx + px, cy: my + py }];
        const where = `rot ${rot}: ${c.person} against bridge ${k}`;
        if (!segCrossJs(a, b, seg(blocker[0]), seg(blocker[1]))) {
          bad.push(`${where}: the planted bridge does not lie across the run that was `
            + `placed without it — this case cannot fail as written`);
          return;
        }
        const blocked = fitEscapesOn(Object.assign({}, solved, { bridgeRuns: [blocker] }),
          rot, spineSlug);
        const moved = blocked[ei];
        if (!moved || !moved.length) {
          bad.push(`${where}: the run was dropped rather than re-aimed`);
        } else if (JSON.stringify(moved) === JSON.stringify(run)) {
          bad.push(`${where}: the run is unchanged by a bridge laid straight across it `
            + `— fitEscapes never sees solved.bridgeRuns`);
        }
        /* NOT ASSERTED: that the DRAWN run clears the bridge. The search tests a
           straight ray at the candidate heading, but each wheel of the run is then
           wobbled up to 20 degrees off it, and seven wheels of that wander well
           away from the ray -- so a run whose ray cleared can still bend back
           across the segment. That is how the crossing rule has worked since #10,
           for escape runs against each other as much as against a bridge, and it
           is not this change's to alter: tightening it moves runs on the shipped
           page. Measured, not assumed -- rot 0's one-wheel chain does exactly this.
           What IS asserted is the property the seeding adds: the bridge is
           consulted, and the heading it blocks is refused. */
        /* The spine's runs, which the planted bridge is nowhere near, must not
           have moved: the seeding refuses a crossing, it does not perturb the lot. */
        ['0', '1'].forEach(s => {
          if (JSON.stringify(blocked[s]) !== JSON.stringify(clear[s]))
            bad.push(`${where}: the spine's run ${s} moved for a bridge it never crosses`);
        });
      });
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the bridges come out of solve(), and stay distinct from the drawn strands', () => {
  /* Two different classes of run, and Task 6 kept them apart deliberately:
     `chains` is the dormant chain-and-belt capability's list and IS drawn, a
     bridge is meshed metal that draws nothing. Merging them would put a strand
     on screen wherever a chain is bridged. */
  const ret = SRC.slice(SRC.indexOf('this._solved = { gears: g'));
  ok(/bridgeRuns: bridges/.test(ret.slice(0, 200)),
    'solve() still keeps its bridge runs to itself, so nothing placed after the '
    + 'fit can refuse to cross one');
  ok(/chains: chains/.test(ret.slice(0, 200)),
    'the drawn strand list is gone or renamed — bridges and strands must stay '
    + 'separately addressable');
  const { solved } = runSolve(THREE, { axisRot: 0 });
  eq(solved.bridgeRuns.length, THREE.length - 1,
    'a solve of three chains does not publish one bridge run per driven chain');
  ok(solved.bridgeRuns.every(s => s.length === 2
      && s.every(p => Number.isFinite(p.cx) && Number.isFinite(p.cy))),
    'a published bridge run is not a finite two-point segment in stage units');
  /* Stage units, not raw solve coordinates: every wheel sits at cx >= 0 after
     the centring shift, and so must every bridge endpoint. */
  ok(solved.bridgeRuns.every(s => s.every(p => p.cx >= 0 && p.cy >= 0)),
    'the bridge runs were published in the pre-centring frame, so they do not '
    + 'line up with the gears\' cx/cy');
});

/* THE REAL datumRuns, lifted out of the page and run against a solve of the
   test's choosing. It reads nothing from the DOM at all -- the drawing is a
   separate method -- so only the chain axis it consumes has to be handed in, and
   that is the page's own chainAxes() built the same way the escape-run harness
   builds it. `ghosts` is the escape-run list the page would have in state. */
function datumRunsOn(solved, axisRot, spineSlug, ghosts, sites, plates, S) {
  const fn = new Function('MODULE', 'SITES', 'DATUM_PLATE',
    'return function ' + grabBlock('  datumRuns(solved, ghosts, S) {', '{', '}') + ';')(
    page.MODULE, sites || {}, plates || {});
  /* The stand-off is bounded in RENDERED pixels (#76), so the page's own
     datumClear() comes along with the rest -- lifted, never restated, because a
     second copy of the owner's figure is exactly the drift the comment on
     PLATE_TOP_CLEAR warns about. It needs the plate's own height, so
     plateMetrics comes with it. A render scale of 1 is the harness default:
     there the module of air fits inside the figure, which is the case every
     assertion written before #76 was written against. */
  const ctx = {
    _axisRot: axisRot,
    plateMetrics: new Function('MODULE',
      'return function ' + grabBlock('  plateMetrics(s) {', '{', '}') + ';')(page.MODULE),
    datumClear: new Function('MODULE', 'PLATE_TOP_CLEAR',
      'return function ' + grabBlock('  datumClear(S) {', '{', '}') + ';')(
      page.MODULE, page.PLATE_TOP_CLEAR),
    chainAxes: new Function('WHO',
      'return function ' + grabBlock('  chainAxes(solved) {', '{', '}') + ';')(
      { slug: spineSlug })
  };
  return fn.call(ctx, solved, ghosts || [], S === undefined ? 1 : S);
}
/* plateSeat() lifted out of the page. It reads exactly two things off the
   component -- the measured viewport box and its own margin rule -- so both are
   handed in and the seat it returns is the seat the page would compute. Warnings
   are captured rather than printed: "neither side fits" is a reported state, and
   a test that could not see it could not tell it from a silent give-up. */
function plateSeatOn(vpBox, r, S, pw, ph) {
  const metrics = new Function('MODULE',
    'return function ' + grabBlock('  plateMetrics(s) {', '{', '}') + ';')(page.MODULE);
  const margin = new Function('return function ' + grabBlock('  plateMargin(s) {', '{', '}') + ';')();
  const seat = new Function('return function ' + grabBlock('  plateSeat(r, S, pw, ph) {', '{', '}') + ';')();
  const warns = [];
  const ctx = { _vpBox: vpBox, plateMetrics: metrics, plateMargin: margin };
  const real = console.warn;
  console.warn = (m) => warns.push(m);
  try {
    const out = seat.call(ctx, r, S, pw, ph);
    return { seat: out, warns: warns, pad: margin.call(ctx, S) };
  } finally { console.warn = real; }
}

/* runSolve seats no service slugs -- PAIR_SLOTS, PAIRS and SINGLES are handed in
   empty, so slugFor is empty and every wheel comes back with slug null. The
   harness supplies what the page's own seating supplies: one slug per linked
   wheel, and the SITES table that resolves it. Returns that table. */
function seatSlugs(solved) {
  const sites = {};
  solved.gears.forEach(g => {
    if (g.role !== 'link' || g.person == null) return;
    g.slug = 'w' + g.i;
    (sites[g.person] = sites[g.person] || {})[g.slug] = {};
  });
  return sites;
}
/* Where the datum source lives, so an assertion about it cannot drift onto some
   other mention of the word. `datum` appears in chainAxes' rationale first. */
const DATUM_SRC = SRC.slice(SRC.indexOf('  datumRuns(solved, ghosts, S) {'),
  SRC.indexOf('  fitEscapes() {'));
const DATUM_DRAW = SRC.slice(SRC.indexOf('  datumLayer(solved, S, box) {'),
  SRC.indexOf('  renderVals() {'));
const DATUM_OP = SRC.slice(SRC.indexOf('  datumOpacity() {'),
  SRC.indexOf('  ghostSvg(g, S) {'));

/* THE REAL COLOUR MATHS, lifted out of the page. datumOpacity() is the one part
   of the datum that cannot be judged from a still or from a solve: it reads the
   theme tokens through getComputedStyle and turns them into the alpha the mark
   is drawn at. Stubbing that one read is the only way a static suite gets to
   watch what the page does when the palette comes back EMPTY, or comes back
   holding something that is not a colour -- and both of those used to end at an
   invisible mark, which is indistinguishable from the feature not existing. */
const colour = new Function(
  grabBlock('function relLum(', '{', '}') + '\n'
  + grabBlock('function rgbOf(', '{', '}') + '\n'
  + grabBlock('function contrastAt(', '{', '}') + '\n'
  + 'return { relLum: relLum, rgbOf: rgbOf, contrastAt: contrastAt };')();

const GHOST_ALPHA = (function () {
  const o = new Function('return {' + grabBlock('  ghostOpacity(theme) {', '{', '}') + '};')();
  return { light: o.ghostOpacity('light'), dark: o.ghostOpacity('dark') };
})();

/* Runs the page's own datumOpacity() over a palette of the test's choosing. A
   token the object does not carry reads back as '', which is what a browser
   hands over for a custom property that is not declared. */
function datumOpacityOn(tokens, theme) {
  const warned = [];
  const obj = new Function('rgbOf', 'contrastAt', 'getComputedStyle', 'document', 'console',
    'return {\n' + grabBlock('  datumOpacity() {', '{', '}') + ',\n'
    + grabBlock('  ghostOpacity(theme) {', '{', '}') + '\n};')(
    colour.rgbOf, colour.contrastAt,
    () => ({ getPropertyValue: (k) => (tokens[k] === undefined ? '' : tokens[k]) }),
    { documentElement: {} }, { warn: (m) => warned.push(m) });
  obj.state = { theme: theme };
  return { alpha: obj.datumOpacity(), warned: warned };
}

/* The palettes come OUT OF THE STYLESHEET, so a token that moves moves the test
   with it rather than leaving it asserting a colour the page stopped using. */
const CSS_ROOT = SRC.slice(SRC.indexOf(':root{'), SRC.indexOf('@supports (top:env('));
const CSS_DARK = SRC.slice(SRC.indexOf(':root[data-theme="dark"]{'), SRC.indexOf('html,body{'));
function cssVar(block, name) {
  const m = new RegExp('(?:^|[;{\\s])' + name + '\\s*:\\s*([^;]+);').exec(block);
  return m ? m[1].trim() : null;
}
const TOKENS = {
  light: { '--ref-bg': cssVar(CSS_ROOT, '--ref-bg'), '--ref-muted': cssVar(CSS_ROOT, '--ref-muted'),
    '--bg': cssVar(CSS_ROOT, '--ref-bg'), '--muted': cssVar(CSS_ROOT, '--ref-muted') },
  dark: { '--ref-bg': cssVar(CSS_ROOT, '--ref-bg'), '--ref-muted': cssVar(CSS_ROOT, '--ref-muted'),
    '--bg': cssVar(CSS_DARK, '--bg'), '--muted': cssVar(CSS_DARK, '--muted') }
};

test('the datum takes its axis from the chain, never its own copy', () => {
  /* #67, twice over. A one-wheel chain has no first-to-last vector: head and
     tail are the same wheel, atan2(0, 0) returns 0, and 0 degrees is horizontal
     in every orientation -- so a mark that derives its own direction lies across
     the SHORT axis in portrait. chainAxes() already answers this for the escape
     runs, and a second copy of the answer is how the escape runs and the bridge
     came to disagree in the first place.

     WHICH of the two axes chainAxes() publishes is the mark's is asserted
     separately, below (#76): this one is about where the answer comes from. */
  ok(DATUM_SRC.length > 0, 'no datum is drawn at all');
  ok(/this\.chainAxes\(/.test(DATUM_SRC),
    'the datum derives its own axis instead of sharing the chain axis');
  ok(!/Math\.atan2/.test(DATUM_SRC),
    'the datum measures an angle of its own — the axis must come from chainAxes()');
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, order } = runSolve(THREE, { axisRot: rot });
    const spineSlug = order[0].slug;
    const axes = chainAxesOf(solved, rot, spineSlug);
    const runs = datumRunsOn(solved, rot, spineSlug, [], seatSlugs(solved));
    eq(runs.length, axes.length, 'rot ' + rot + ': not every chain gets a datum');
    runs.forEach((r, k) => {
      if (Math.abs(r.deg - axes[k].travel) > 1e-9)
        bad.push(`rot ${rot}: ${r.person}'s datum runs at ${r.deg.toFixed(2)}, `
          + `its chain's path of travel at ${axes[k].travel.toFixed(2)}`);
      /* The one-wheel chain is the case that collapses. Its mark must still have
         length, and must lie on the stage axis rather than on the horizontal. */
      if (axes[k].wheels.length === 1) {
        if (axisOff(r.deg, rot) > 1e-9)
          bad.push(`rot ${rot}: a one-wheel chain's datum lies at ${r.deg} instead `
            + `of on the stage axis (${rot}) — #67 again`);
        if (!(r.d1 - r.d0 >= 0) || !isFinite(r.d0) || !isFinite(r.d1))
          bad.push(`rot ${rot}: a one-wheel chain's datum has no extent`);
      }
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the datum is scribed straight along the travel, and stands off by the stated figure', () => {
  /* #76, both halves, over many dealt trains rather than one.

     THE ANGLE. `chainAxes()` measures each chain head-to-tail, and a dealt
     serpentine's ends rarely land level: the bearings come out of
     [ANG_MIN, ANG_MAX] with alternating signs and only the band and the
     end-to-end drift are capped, never the end-to-end angle. So the MEASURED
     axis carries whatever tilt this load dealt -- up to a couple of degrees --
     and a datum laid at it runs visibly askew to a chain the eye reads as
     travelling straight. The mark is laid along the PATH OF TRAVEL, which is the
     stage's own axis, and is therefore exactly parallel on every deal. This is
     the test that would have caught it: a single deal can look level by luck,
     so it takes many, and it asserts the tilt is not merely small but ZERO.

     THE OFFSET. "the top of the label box is no more than 20px outside the
     extreme border of the side" -- so the plate's outer edge, in RENDERED
     pixels, against the deepest tip radius of the chain's own link gears
     projected on the travel normal. Checked at three render scales, chosen for
     which side of the figure they fall on: at S=1 a module of air still fits
     inside it and nothing is taken away; at the ~1.47 a 1440-wide window deals
     the bound is what holds the mark in; at the ~3.4 an ultrawide deals the
     plate's own half-height has already spent the whole figure, so the air goes
     to zero and the mark stands as close as it geometrically can. The last is
     the case a bound stated in rendered pixels cannot satisfy, and the assertion
     says so in the same terms the page does rather than exempting it. Both sides
     of the line are checked, because plateSeat() may mirror the mark onto the
     other one. */
  const bad = [];
  const PLATE_HALF = (S) => page.MODULE * 2 * S / 2;   /* plateMetrics().h / 2 */
  [0, 90].forEach(rot => {
    [1, 1.47, 3.4].forEach(S => {
      /* Every runSolve is a fresh deal -- dealAngles() draws from Math.random --
         so the loop IS the sweep of trains, and a tilt that only shows up on
         some loads cannot hide behind one lucky arrangement. */
      for (let deal = 0; deal < 24; deal++) {
        const { solved, order } = runSolve(THREE, { axisRot: rot });
        const spineSlug = order[0].slug;
        const runs = datumRunsOn(solved, rot, spineSlug, [], seatSlugs(solved), null, S);
        runs.forEach(r => {
          /* PARALLEL TO THE TRAVEL, to the last bit of floating point. */
          if (axisOff(r.deg, rot) > 1e-9)
            bad.push(`rot ${rot} S ${S} deal ${deal}: ${r.person}'s datum is laid at `
              + `${r.deg.toFixed(3)}, ${axisOff(r.deg, rot).toFixed(3)}° off the path of travel`);
          /* And the direction vector it hands the drawing agrees with that
             angle -- a `deg` used only for the plate's rotation, with ux/uy
             still off the measured axis, would draw a tilted line under a
             square plate and pass an angle-only check. */
          const ux = Math.cos(r.deg * Math.PI / 180), uy = Math.sin(r.deg * Math.PI / 180);
          if (Math.hypot(r.ux - ux, r.uy - uy) > 1e-9)
            bad.push(`rot ${rot} S ${S} deal ${deal}: ${r.person}'s datum reports `
              + `${r.deg}° but runs along (${r.ux.toFixed(4)}, ${r.uy.toFixed(4)})`);
          /* THE STAND-OFF, on each side, in rendered pixels. */
          const own = solved.gears.filter(g => g.person === r.person && g.role === 'link');
          const hi = Math.max.apply(null, own.map(g => g.cx * r.nx + g.cy * r.ny + g.ro));
          const lo = Math.min.apply(null, own.map(g => g.cx * r.nx + g.cy * r.ny - g.ro));
          /* What the figure leaves for air once the plate's own half-height is
             paid out of it. Zero once the plate alone is 20px from the line,
             which is where the bound stops being satisfiable at all. */
          const allowed = Math.max(0, page.PLATE_TOP_CLEAR - PLATE_HALF(S));
          [[r.o, hi, 1], [r.alt, lo, -1]].forEach(pair => {
            const line = pair[0].x * r.nx + pair[0].y * r.ny;
            /* how far outside that side's extreme border the line sits */
            const air = (line - pair[1]) * pair[2];
            const top = (air * S) + PLATE_HALF(S);
            if (air < -1e-9)
              bad.push(`rot ${rot} S ${S} deal ${deal}: ${r.person}'s datum is scribed `
                + `${(-air).toFixed(2)} inside the teeth it references`);
            if (air * S > allowed + 1e-6)
              bad.push(`rot ${rot} S ${S} deal ${deal}: ${r.person}'s datum stands `
                + `${(air * S).toFixed(2)} rendered px off the extreme border, where the `
                + `stated ${page.PLATE_TOP_CLEAR} leaves room for ${allowed.toFixed(2)} `
                + `once its ${PLATE_HALF(S).toFixed(2)} of plate is paid for`);
            if (allowed > 0 && top > page.PLATE_TOP_CLEAR + 1e-6)
              bad.push(`rot ${rot} S ${S} deal ${deal}: the top of ${r.person}'s label box `
                + `stands ${top.toFixed(2)} rendered px outside the extreme border, past the `
                + `stated ${page.PLATE_TOP_CLEAR}`);
            /* And where the air still fits inside the figure, it is the module
               of air the rest of this page states its clearances in -- the bound
               is a ceiling, not a target, so it may not quietly become one. */
            if (allowed >= page.MODULE * S - 1e-9 && Math.abs(air - page.MODULE) > 1e-9)
              bad.push(`rot ${rot} S ${S} deal ${deal}: ${r.person}'s datum gave up its `
                + `module of air (${air.toFixed(3)}) where the figure had room for it`);
          });
        });
      }
    });
  });
  ok(bad.length === 0, bad.slice(0, 6).join('\n      ')
    + (bad.length > 6 ? `\n      … and ${bad.length - 6} more` : ''));
});

test('a datum station is a clickable gear, never a ghost or an idler', () => {
  /* Ghosts and idlers are spanned but never indexed: they are machinery, not
     parts you can reach. chainAxes() has already dropped the idlers; the station
     filter is what drops a link the active config seats no service on. */
  ok(/\.slug/.test(DATUM_SRC),
    'the datum indexes every wheel rather than only the clickable ones');
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, order } = runSolve(THREE, { axisRot: rot });
    const sites = seatSlugs(solved);
    const runs = datumRunsOn(solved, rot, order[0].slug, [], sites);
    runs.forEach(r => {
      const want = THREE.find(p => p.slug === r.person).links.length;
      if (r.stations.length !== want)
        bad.push(`rot ${rot}: ${r.person} has ${r.stations.length} stations for `
          + `${want} clickable wheels`);
      /* Every station must land on one of that chain's own linked wheels, and on
         nothing else the stage carries. An idler projected onto the line would
         sit between two of them and pass a count-only check. */
      const own = solved.gears.filter(g => g.person === r.person && g.role === 'link');
      const at = (g) => (g.cx - r.o.x) * r.ux + (g.cy - r.o.y) * r.uy;
      const mine = own.map(at).sort((a, b) => a - b);
      r.stations.forEach((d, k) => {
        if (Math.abs(d - mine[k]) > 1e-9)
          bad.push(`rot ${rot}: ${r.person}'s station ${k} is not one of its own links`);
      });
      /* And the mark must clear the teeth of every wheel it indexes, not only
         the first: a serpentine wanders perpendicular by most of a wheel. */
      own.forEach(g => {
        const perp = (g.cx - r.o.x) * r.nx + (g.cy - r.o.y) * r.ny;
        if (perp > -g.ro)
          bad.push(`rot ${rot}: ${r.person}'s datum passes through a wheel `
            + `(clearance ${(-perp - g.ro).toFixed(1)})`);
      });
    });
    /* NOT ASSERTED: that no idler projects onto a station. A bridge runs
       perpendicular to the chain it feeds, so the idler that feeds a one-wheel
       chain lands on exactly that wheel's position along the axis -- a
       coincidence of projection, not an index. What binds the rule is above:
       the station list IS that chain's own linked wheels, in order. */
    /* And the predicate is the badges' own, not merely `role === 'link'`: take
       one service out of SITES and its station must go with it, because a wheel
       whose service the active config does not seat is not a part you can
       reach. */
    const one = runs.find(r => r.stations.length > 1);
    const drop = Object.keys(sites[one.person])[0];
    const thin = JSON.parse(JSON.stringify(sites));
    delete thin[one.person][drop];
    const after = datumRunsOn(solved, rot, order[0].slug, [], thin)
      .find(r => r.person === one.person);
    if (after.stations.length !== one.stations.length - 1)
      bad.push(`rot ${rot}: a wheel with no service seated on it is still indexed`);
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the plate seats on the side the page has room for, and the ticks follow it', () => {
  /* THE MARK MAY NOT LEAVE THE PAGE, which datumRuns() has always said and
     nothing enforced: the plate is placed after fitStage, outside all three limbs
     of the fit, and the fit deliberately lets the machine bleed past the cross
     axis. Measured unseeded, that put Harper's plate wholly below the fold on
     2 of 20 loads at 1440x900.

     A horizontal run, so the two axes separate cleanly: sliding along it moves x
     only, and the choice of side moves y only. That is the shape of the real
     failure -- both observed cases were cross-axis, which sliding cannot fix. */
  const r = { person: 'p', plate: 'P', ux: 1, uy: 0, nx: 0, ny: 1,
    o: { x: 0, y: 0 }, alt: { x: 0, y: -20 }, plateAt: 0, stations: [], d0: 0, d1: 0 };
  const pw = 40, ph = 10, S = 1;
  const wide = { x0: -100, y0: -100, x1: 100, y1: 100 };
  const A = plateSeatOn(wide, r, S, pw, ph);
  eq(A.seat.side, 1, 'a plate with room on its own side is moved anyway');
  eq(A.seat.oy, 0, 'a plate with room on its own side does not stay on it');
  eq(A.seat.at, 0, 'a plate with room at its own station is slid off it');
  eq(A.warns.length, 0, 'a plate that seats cleanly warns about it');
  /* THE MARGIN IS REAL, not nominal. The seat must hold the plate `pad` inside
     every edge, so a box exactly the plate's own size does NOT fit. */
  const half = ph / 2;
  const snug = { x0: -100, y0: -half, x1: 100, y1: half };
  ok(plateSeatOn(snug, r, S, pw, ph).warns.length === 1,
    'a box exactly the size of the plate is treated as room for it — the seat is '
    + 'flush, so the stroke that straddles its edge hangs off the page');
  /* ONLY THE MIRROR FITS: the natural side is below the fold, the mirrored one is
     not, and no station along a horizontal run can change a y. */
  const low = { x0: -100, y0: -100, x1: 100, y1: half + 1 };
  const B = plateSeatOn(low, r, S, pw, ph);
  eq(B.seat.side, -1, 'the plate stays on a side the page cannot show, with the '
    + 'mirrored origin standing unused');
  eq(B.seat.oy, -20, 'the seat reports the mirrored side but not the mirrored origin');
  eq(B.warns.length, 0, 'a plate that seats on the mirror is reported as unplaceable');
  /* SLIDING IS THE OTHER FREEDOM, and is preferred over mirroring: a station out
     of reach along the run is pulled back to the nearest one that fits, on the
     side the plate was already on. */
  const narrow = { x0: -100, y0: -100, x1: 100, y1: 100 };
  const far = Object.assign({}, r, { plateAt: 500 });
  const C = plateSeatOn(narrow, far, S, pw, ph);
  eq(C.seat.side, 1, 'a plate that only needed sliding was mirrored instead');
  ok(C.seat.at < 500 && C.seat.at + pw / 2 + C.pad.pad <= 100 + 1e-9,
    'a plate past the end of the page is not pulled back to a station that fits');
  /* NEITHER SIDE FITTING IS REPORTED, NOT HIDDEN. */
  const none = { x0: -100, y0: -1, x1: 100, y1: 1 };
  const D = plateSeatOn(none, r, S, pw, ph);
  eq(D.seat.side, 1, 'an unplaceable plate does not fall back to its natural side');
  eq(D.warns.length, 1, 'a plate that fits nowhere is drawn silently');
  ok(/neither side/.test(D.warns[0]), 'the warning does not say what went wrong');
  /* THE TICKS FOLLOW THE SIDE. They are struck along the normal, and on the
     mirrored origin the normal points AT the wheels: a major tick is 1.2 modules
     against one module of clearance, so unflipped ticks vanish under the chain's
     own teeth and the mark reads inverted and short. The seeded gate cannot see
     it — the mirror only fires on deals that seed does not produce. */
  ok(/const out = seat\.side/.test(DATUM_DRAW),
    'datumLayer no longer takes its outboard direction from the seat');
  const ticks = DATUM_DRAW.match(/at\(d[m]?, [^)]*(MAJOR|MINOR)\)/g) || [];
  eq(ticks.length, 2, 'expected exactly two tick strikes in datumLayer, found ' + ticks.length);
  ticks.forEach(t => ok(/out \* (MAJOR|MINOR)/.test(t),
    'a tick is struck at a fixed sign (' + t + '), so a mirrored datum draws its '
    + 'ticks into the wheels it is meant to clear'));
});

test('the datum plate defaults to the person name, untransformed', () => {
  /* The casing config.js carries is the casing on the plate. Never uppercased,
     abbreviated or given a serial: a plate that says something other than what
     the picker says is a second name for the same person. */
  ok(!/toUpperCase\(\)/.test(DATUM_SRC + DATUM_DRAW),
    'the datum plate transforms the configured name');
  ok(/p\.datum \|\| p\.name/.test(SRC),
    'the plate string is not the configured name with an optional `datum` override');
  ok(/datum\s+optional/.test(CFG_SRC),
    'config.js does not document the optional per-person `datum` key');
  const { solved, order } = runSolve(THREE, { axisRot: 0 });
  const runs = datumRunsOn(solved, 0, order[0].slug, [], seatSlugs(solved),
    { spine: 'A. Name', mid: 'b' });
  eq(runs.find(r => r.person === 'spine').plate, 'A. Name',
    'the plate does not come from the configured string');
  eq(runs.find(r => r.person === 'tiny').plate, 'tiny',
    'a person with no plate string configured loses the fallback to their slug '
    + 'and gets no plate at all');
});

test('a datum spans its chain\'s ghosts and rides its plate on the last leading one', () => {
  /* Rule 1 and rule 3. The run off the trailing edge is part of the machine the
     line references, so the line goes where it goes; the plate sits alongside
     the background wheel immediately before the first real gear, which is the
     placard at the head of the run. A driven chain has no leading run at all --
     that is the end its bridge arrives at -- and falls back to the head wheel
     rather than vanishing. */
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, order } = runSolve(THREE, { axisRot: rot });
    const sites = seatSlugs(solved);
    const spineSlug = order[0].slug;
    const axes = chainAxesOf(solved, rot, spineSlug);
    const spine = axes.find(c => c.spine);
    const bare = datumRunsOn(solved, rot, spineSlug, [], sites);
    /* Two ghosts off the leading end and two off the trailing end of the spine,
       placed on its own axis at real escape-run distances so the projection has
       to do the work rather than agreeing by construction. */
    const step = spine.head.ro * 3;
    const ghosts = [0, 1].map(k => ({ person: spineSlug, lead: true, k: k,
      cx: spine.head.cx - Math.cos(spine.deg * Math.PI / 180) * step * (k + 1),
      cy: spine.head.cy - Math.sin(spine.deg * Math.PI / 180) * step * (k + 1) }))
      .concat([0, 1].map(k => ({ person: spineSlug, lead: false, k: k,
        cx: spine.tail.cx + Math.cos(spine.deg * Math.PI / 180) * step * (k + 1),
        cy: spine.tail.cy + Math.sin(spine.deg * Math.PI / 180) * step * (k + 1) })));
    const runs = datumRunsOn(solved, rot, spineSlug, ghosts, sites);
    const r = runs.find(x => x.person === spineSlug);
    const b = bare.find(x => x.person === spineSlug);
    if (!(r.d0 < b.d0 - 1) || !(r.d1 > b.d1 + 1))
      bad.push(`rot ${rot}: the datum stops at the linked wheels — the background `
        + `machinery is not spanned (${b.d0.toFixed(0)}..${b.d1.toFixed(0)} vs `
        + `${r.d0.toFixed(0)}..${r.d1.toFixed(0)})`);
    const lead0 = ghosts[0];
    const want = (lead0.cx - r.o.x) * r.ux + (lead0.cy - r.o.y) * r.uy;
    if (Math.abs(r.plateAt - want) > 1e-9)
      bad.push(`rot ${rot}: the plate is not at the LAST leading ghost`);
    /* Every other chain has no leading run, so its plate falls back to the head. */
    runs.filter(x => x.person !== spineSlug).forEach(x => {
      const c = axes.find(a => a.person === x.person);
      const head = (c.head.cx - x.o.x) * x.ux + (c.head.cy - x.o.y) * x.uy;
      if (Math.abs(x.plateAt - head) > 1e-9)
        bad.push(`rot ${rot}: ${x.person} has no leading ghost and lost its plate `
          + `rather than falling back to the head of the run`);
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('no datum is drawn while one chain is on stage, and none is painted per chain', () => {
  /* The datum exists to tell chains apart. On a solo page there is nothing to
     tell apart, so the mark would be furniture identifying the only thing
     present -- and the shipped default page is exactly that case, which is why
     it is pixel-identical across this change. */
  const solo = [{ slug: 'only', links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] }];
  const { solved, order } = runSolve(solo, { axisRot: 0 });
  eq(datumRunsOn(solved, 0, order[0].slug, [], seatSlugs(solved)).length, 0,
    'a solo page draws a datum, which identifies nothing and moves shipped pixels');
  /* RULE 6: one layer, beneath EVERY wheel. Painted per chain, the following
     chain's ghost run buries the previous chain's plate — which is what the mock
     did first. */
  const art = SRC.slice(SRC.indexOf('const gearArt = h(\'div\''));
  const iDatum = art.indexOf('this.datumLayer(');
  ok(iDatum > 0 && iDatum < art.indexOf('ghosts,') && iDatum < art.indexOf("key: 'shadows'"),
    'the datum layer is not the first thing the stage paints, so a chain\'s '
    + 'machinery can cover another chain\'s plate');
  /* RULE 5: tokens, never invented greys. */
  ok(!/#[0-9A-Fa-f]{3,6}/.test(DATUM_DRAW),
    'the datum draws itself in a literal colour instead of --muted and --hair');
  ok(/var\(--muted\)/.test(DATUM_DRAW) && /var\(--hair\)/.test(DATUM_DRAW),
    'the datum does not take its scribe and plate colours from the theme tokens');
  /* The dark alpha is SOLVED against the light treatment's contrast, not carried
     as a second number beside the ghost layer's pair. */
  ok(/contrastAt\(/.test(DATUM_OP) && !/0\.3[0-9]/.test(DATUM_OP),
    'the datum\'s dark opacity is a number someone measured once rather than one '
    + 'the page solves from its own tokens');
});

test('a datum that cannot read its palette fails visible, never invisible', () => {
  /* THE ONE OUTCOME THIS MARK MAY NOT HAVE IS "ABSENT". It is the identity
     signal, so a scribe drawn at an alpha nobody can see looks exactly like the
     feature never having been built, and leaves nothing on the page to diagnose
     it from. Two ways of losing the palette both used to end there.

     The reference colours were read by scanning document.styleSheets for a rule
     whose selectorText was ':root' EXACTLY -- so wrapping that block in a @media
     or an @supports, writing it ':root, :host', or shipping a second sheet that
     declares --muted finds nothing. The fallback was then ghostOpacity() for the
     CURRENT theme, which in dark is the ghost alpha: precisely the weight the
     mock proved makes the scribe disappear. Nothing surfaced it, and no static
     suite could see it, because the mechanism only exists in a browser. */
  /* Comments stripped, because the mechanism being ruled out is NAMED in the
     rationale that replaced it -- an assertion that could not tell the two apart
     would fail on its own explanation. */
  ok(!/styleSheets|cssRules|selectorText/.test(SRC.replace(/\/\*[\s\S]*?\*\//g, '')),
    'the page reads its own stylesheet back through CSSOM, which finds nothing '
    + 'the moment the :root block is wrapped or its selector is joined');
  ok(!/ghostOpacity\(\)/.test(DATUM_OP),
    'the datum falls back to the CURRENT theme\'s ghost alpha — in dark that is '
    + GHOST_ALPHA.dark + ', the alpha that makes the scribe vanish');
  /* The reference palette is two tokens the dark block does not override, and
     the light declarations are aliases of them, so each colour is still written
     in exactly one place. */
  ok(TOKENS.light['--ref-bg'] && TOKENS.light['--ref-muted'],
    'the light reference palette is not declared in :root, so nothing under dark '
    + 'can reach the treatment the datum is solved against');
  ok(!cssVar(CSS_DARK, '--ref-bg') && !cssVar(CSS_DARK, '--ref-muted'),
    'the dark block overrides the reference palette, so the datum solves for the '
    + 'contrast it already has and every theme returns the same alpha');
  ok(/--bg:\s*var\(--ref-bg\)/.test(CSS_ROOT) && /--muted:\s*var\(--ref-muted\)/.test(CSS_ROOT),
    'the light --bg/--muted are written out again beside the reference tokens '
    + 'instead of aliasing them, so the two can drift apart');
  /* Solved, both palettes. Light is the reference and returns its alpha by
     construction; dark must reach the SAME contrast, which is what makes its
     answer a derivation rather than a number with a story attached. */
  const light = datumOpacityOn(TOKENS.light, 'light').alpha;
  const dark = datumOpacityOn(TOKENS.dark, 'dark').alpha;
  eq(light, GHOST_ALPHA.light,
    'the light palette no longer returns the reference alpha by construction');
  const at = (t, a) => colour.contrastAt(colour.rgbOf(t['--muted']), colour.rgbOf(t['--bg']), a);
  const want = at(TOKENS.light, GHOST_ALPHA.light);
  ok(Math.abs(at(TOKENS.dark, dark) - want) < 0.02,
    `the dark alpha ${dark} reaches ${at(TOKENS.dark, dark).toFixed(3)}:1, not the `
    + `light treatment's ${want.toFixed(3)}:1`);
  ok(dark > GHOST_ALPHA.dark,
    'the dark scribe is drawn no harder than a ghost wheel, which is the weight '
    + 'the mock proved it disappears at');
  /* NOW TAKE THE PALETTE AWAY, one token at a time, in the theme where being
     wrong is invisible. Every refusal has to land at or above the reference
     alpha: too strong for a dark page, obviously so to anyone looking, present. */
  ['--bg', '--muted', '--ref-bg', '--ref-muted'].forEach(k => {
    const t = Object.assign({}, TOKENS.dark);
    delete t[k];
    const got = datumOpacityOn(t, 'dark').alpha;
    ok(got >= GHOST_ALPHA.light,
      `with ${k} unreadable the dark datum is drawn at ${got} — a mark nobody can `
      + 'see is indistinguishable from the feature not being there');
  });
  /* A palette that is present but has no answer in it. --muted and --bg at the
     same luminance means no alpha reaches `want`, and an unguarded bisection
     drives hi to 1 and hands back a FULL-OPACITY scribe -- the loudest mark on a
     page whose whole requirement is a quiet one. */
  const flat = Object.assign({}, TOKENS.dark, { '--muted': TOKENS.dark['--bg'] });
  const got = datumOpacityOn(flat, 'dark').alpha;
  ok(got < 1, `a palette with no solution in it draws the scribe at ${got}`);
  eq(got, GHOST_ALPHA.light,
    'a palette with no solution in it does not fall back to the reference weight');
});

test('the datum reads every colour form a token can carry, and refuses the rest', () => {
  /* `parseInt(hex.slice(1), 16)` had one exit and it was the bad one. #abc
     parses to 2748 and yields channels nothing asked for; a named colour or an
     rgb() string yields NaN -- and NaN is worse than wrong, because it is
     SILENT: contrastAt returns NaN, `NaN < want` is false, so the bisection
     drives hi to zero and settles at ~0. That is an invisible datum, cached for
     the life of the theme. "The solve follows the token" only held while every
     token stayed a six-digit hex, which nothing in the stylesheet promises. */
  const R = colour.rgbOf;
  const j = (v) => JSON.stringify(v);
  eq(j(R('#abc')), '[170,187,204]', 'a three-digit hex is not expanded');
  eq(j(R('#AABBCC')), '[170,187,204]', 'a six-digit hex is not read case-insensitively');
  eq(j(R('  #6b7e7c  ')), '[107,126,124]', 'a padded token is not trimmed');
  eq(j(R('rgb(107, 126, 124)')), '[107,126,124]', 'a comma-separated rgb() is not read');
  eq(j(R('rgb(107 126 124 / 0.5)')), '[107,126,124]', 'a space-separated rgb() is not read');
  eq(j(R('rgba(107,126,124,1)')), '[107,126,124]', 'an rgba() is not read');
  const pc = R('rgb(50% 20% 30%)');
  ok(pc && pc.length === 3 && [127.5, 51, 76.5].every((v, i) => Math.abs(pc[i] - v) < 1e-6),
    'rgb() percentages are not read as 0-255 (got ' + j(pc) + ')');
  /* Everything else must be null, NOT a number: null stops the derivation and
     the caller draws at the reference alpha. An eight-digit hex is refused on
     purpose -- dropping its alpha would compute the wrong contrast quietly. */
  ['teal', '', '   ', '#12345', '#11223344', 'var(--nope)', 'currentColor', null, undefined]
    .forEach(v => eq(R(v), null, `rgbOf(${j(v)}) returned a colour instead of refusing`));
  /* And the solve genuinely follows the token, whichever form it is written in:
     the same colour as #rgb, as #rrggbb and as rgb() must give one alpha. */
  const long = Object.assign({}, TOKENS.dark, { '--muted': '#99AABB' });
  const short = Object.assign({}, TOKENS.dark, { '--muted': '#9AB' });
  const rgbForm = Object.assign({}, TOKENS.dark, { '--muted': 'rgb(153, 170, 187)' });
  eq(datumOpacityOn(short, 'dark').alpha, datumOpacityOn(long, 'dark').alpha,
    'the same colour written three-digit and six-digit solves to two alphas');
  eq(datumOpacityOn(rgbForm, 'dark').alpha, datumOpacityOn(long, 'dark').alpha,
    'the same colour written rgb() and hex solves to two alphas');
  /* The NaN trap itself: a token the page cannot read must not resolve to zero,
     and must say so rather than going quiet. */
  ['teal', 'rgb(a, b, c)', '#11223344'].forEach(v => {
    const t = Object.assign({}, TOKENS.dark, { '--muted': v });
    const r = datumOpacityOn(t, 'dark');
    ok(r.alpha >= GHOST_ALPHA.light,
      `--muted: ${v} draws the scribe at ${r.alpha} — the NaN collapse is back`);
    eq(r.warned.length, 1,
      `--muted: ${v} is unreadable and the page says nothing about it`);
  });
  /* A token that is simply not there YET is not a fault: the page's own <style>
     is compiled and re-inserted, so the first render can read '' before it
     lands. That path stays quiet, and stays uncached so the next render asks
     again rather than holding the fallback for the life of the page. */
  const empty = Object.assign({}, TOKENS.dark, { '--muted': '' });
  eq(datumOpacityOn(empty, 'dark').warned.length, 0,
    'a palette that has not been applied yet is reported as a broken one');
  ok(!/this\._datumOp\[theme\]\s*=/.test(DATUM_OP.slice(0, DATUM_OP.indexOf('const want'))),
    'the datum caches a fallback alpha, so one early render freezes the mark at '
    + 'the wrong weight for the life of the page');
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
     not run along. Asking the rotation itself makes them agree by construction.

     RUN, NOT READ. Asserting that the source says `this.axisRot()` is a check on
     a spelling, and it passes just as happily while the two are handed DIFFERENT
     VIEWPORTS -- which is the second half of the same bug: this read the visual
     viewport while the rotation it defers to reads innerWidth/innerHeight, so an
     iOS toolbar collapse put them back into disagreement by another route.

     No formula is repeated here. The real idlerCount() is run with the rotation
     FORCED, which is the only way to ask a function whether it is listening: a
     count that derives its own axis gives the same answer whatever it is told,
     and that is exactly the defect. So the first thing asserted is that some
     viewport exists where forcing 0 and forcing 90 give DIFFERENT counts.

     WHAT IS NOT ASSERTED, AND WHY. There is no case in the 1.00-1.05 band where
     the two readings differ NUMERICALLY: swept at 10px over 200-3000px, the
     count comes out the same whichever axis is called long, because the cross
     term the bridge asks for is ~0.95 of the long term at three chains and the
     band only reaches 0.952. So the band cannot discriminate today -- which is
     luck, not a property, and it moves the moment a person is added or the
     module changes. The band is pinned to the landscape reading instead, which
     is what "agree with axisRot" means there. */
  const STAGE_CROSS = new Function('MODULE', 'TEETH_MEAN', 'STAGE',
    grabDecl('const STAGE_CROSS =') + '\n return STAGE_CROSS;')(
    page.MODULE, page.TEETH_MEAN, { people: THREE });
  const IDLERS_FOR = new Function('MIN_IDLERS', 'MAX_IDLERS',
    grabDecl('const IDLERS_FOR =') + '\n return IDLERS_FOR;')(
    grabNumber('MIN_IDLERS'), grabNumber('MAX_IDLERS'));
  /* NOMINAL_SPAN is the page's own derivation, executed, exactly as fitRule()
     does it -- a copy of that formula here is the drift this file exists to
     stop. */
  const NOMINAL_SPAN = new Function('MODULE', 'TEETH_MEAN', 'ANG_MIN', 'ANG_MAX', 'NOMINAL_CHAIN',
    'return ' + grabBlock('const NOMINAL_SPAN =', '(', ')')
      .replace(/^const NOMINAL_SPAN =\s*/, '') + '()')(
    page.MODULE, page.TEETH_MEAN, page.ANG_MIN, page.ANG_MAX, Math.max(...page.TRAIN_LENS));
  const fixture = Array.from({ length: Math.max(...page.TRAIN_LENS) },
    () => ({ teeth: page.TEETH_MAX }));
  const countOn = (win) => new Function('window', 'LINK_SHARE', 'NOMINAL_SPAN',
    'STAGE_CROSS', 'MODULE', 'TEETH_MEAN', 'IDLERS_FOR', 'MAX_IDLERS',
    'TARGET_GEAR_PX', 'WHEEL_SPAN',
    'return function ' + grabBlock('  idlerCount() {', '{', '}') + ';')(
    win, grabNumber('LINK_SHARE'), NOMINAL_SPAN, STAGE_CROSS,
    page.MODULE, page.TEETH_MEAN, IDLERS_FOR, grabNumber('MAX_IDLERS'),
    grabNumber('TARGET_GEAR_PX'), wheelSpanOf(fixture));
  const rotOn = (win) => new Function('window',
    'return function ' + grabBlock('  axisRot() {', '{', '}') + ';')(win);
  const bad = [];
  /* THE COUNT MUST LISTEN. Somewhere, telling it 0 and telling it 90 has to give
     two different answers -- otherwise it is deriving its own axis and this whole
     test is measuring nothing. */
  let listens = 0;
  for (let w = 200; w <= 3000 && !listens; w += 10) {
    for (let h = 200; h <= 3000 && !listens; h += 10) {
      const c = countOn({ innerWidth: w, innerHeight: h });
      if (c.call({ _idlerN: 2, axisRot: () => 0 }) !== c.call({ _idlerN: 2, axisRot: () => 90 })) {
        listens++;
      }
    }
  }
  ok(listens > 0, 'forcing axisRot() to 0 and to 90 gives the same idler count at every '
    + 'viewport, so the count is deriving its own long axis and ignoring the rotation');
  /* Straddling the 1.05 hinge from both sides in 5px steps -- the band the two
     used to disagree in -- plus a genuine phone, tablet and desktop. */
  const shapes = [[390, 844], [844, 390], [1440, 900], [2560, 1080], [744, 1133]];
  for (let w = 700; w <= 1500; w += 25) {
    for (let h = w; h <= Math.round(w * 1.10); h += 5) shapes.push([w, h]);
  }
  shapes.forEach(([w, h]) => {
    const win = { innerWidth: w, innerHeight: h };
    const count = countOn(win), rot = rotOn(win)();
    [1, 2].forEach(held => {
      const live = count.call({ _idlerN: held, axisRot: rotOn(win) });
      const asRot = count.call({ _idlerN: held, axisRot: () => rot });
      if (live !== asRot) {
        bad.push(`${w}x${h} holding ${held}: the count does not follow axisRot() — `
          + `it says ${rot}deg and forcing that gives ${asRot}, but the live call gave ${live}`);
      }
      /* Inside the band the stage has NOT turned, so the count may not read the
         taller side as the long one however close the two are. */
      if (h > w && h <= w * 1.05) {
        const asLandscape = count.call({ _idlerN: held, axisRot: () => 0 });
        if (live !== asLandscape) {
          bad.push(`${w}x${h} holding ${held}: taller than wide but under the 1.05 hinge, `
            + `so the stage is still landscape — the count says ${live}, landscape says ${asLandscape}`);
        }
      }
    });
  });
  /* AND BOTH HALVES MEASURE THE SAME WINDOW. A visual viewport shorter than the
     layout one is the iOS toolbar collapsing; axisRot() cannot see it, so
     neither may this. Calibrated rather than asserted blind: a pair of sizes
     that genuinely give different counts is searched for first, and the visual
     viewport is then set to the OTHER one. */
  let pair = null;
  for (let h = 400; h <= 1400 && !pair; h += 10) {
    for (let h2 = 400; h2 <= 1400 && !pair; h2 += 10) {
      const a = countOn({ innerWidth: 900, innerHeight: h });
      const b = countOn({ innerWidth: 900, innerHeight: h2 });
      if (a.call({ _idlerN: 2, axisRot: rotOn({ innerWidth: 900, innerHeight: h }) })
        !== b.call({ _idlerN: 2, axisRot: rotOn({ innerWidth: 900, innerHeight: h2 }) })) {
        pair = [h, h2];
      }
    }
  }
  ok(pair, 'no two viewport heights give different idler counts, so the visual-viewport '
    + 'check below would be vacuous');
  const layout = { innerWidth: 900, innerHeight: pair[0] };
  const spoofed = { innerWidth: 900, innerHeight: pair[0],
    visualViewport: { width: 900, height: pair[1] } };
  eq(countOn(spoofed).call({ _idlerN: 2, axisRot: rotOn(spoofed) }),
    countOn(layout).call({ _idlerN: 2, axisRot: rotOn(layout) }),
    'a visual viewport of a different size moves the idler count, which axisRot() '
    + 'cannot see — the two are measuring different windows again');
  ok(bad.length === 0, bad.join('\n      '));
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

test('a wheel only ever stops growing at the standard size', () => {
  /* WHAT REPLACED #44's PROPERTY, and why it had to be replaced rather than
     re-stated. #44 said the linked run takes a CONSTANT share of the long axis
     at every width, and this test asserted exactly that. It is no longer true:
     past TARGET_GEAR_PX a gear is a fixed number of pixels, so its share of a
     growing axis falls as 1/W. Charles asked for that (GitHub #75) -- the share
     rule read the long axis and nothing else, so the same screen area reshaped
     from 3.3:1 to 1:1 moved the wheels 1.8x.

     What is still forbidden is the failure #19, #44 and #66 actually were: a
     share that falls while the wheels are still BELOW the standard size, which
     is what a ratio ceiling produces and what nobody chose. So the property is
     now a disjunction, asserted at every width: either the share is the share
     the narrowest viewport got, or the wheels have reached their standard size
     and the escape runs are covering the difference. A ratio ceiling fails it
     immediately -- it caps the share somewhere the wheels are still small.

     AND THE SIZE IS MONOTONE. A wider viewport may never give a SMALLER wheel,
     and no viewport may give one larger than the standard. Between them those
     two bound the whole rule from both sides, which is what the old single-sided
     share assertion never did. */
  const fit = fitRule();
  const TARGET = grabNumber('TARGET_GEAR_PX');
  const bad = [];
  for (const n of [1, 2, 4, 7, 9]) {
    const span = n === 1 ? 150 : page.MODULE * 16.3 * n;
    const widths = [1440, 2560, 3440, 5120];
    const rows = widths.map(w => {
      const r = fit(n, w, w * 0.5625, span, n === 1 ? 150 : 210);
      return { w, share: (r.fit * span) / w, px: r.fit * r.wheelSpan };
    });
    const base = rows[0].share;
    rows.forEach(r => {
      if (Math.abs(r.share - base) > 0.001 && r.px < TARGET - 0.5) {
        bad.push(`${n} wheels at ${r.w}px: share moved to ${(r.share * 100).toFixed(1)}% `
          + `from ${(base * 100).toFixed(1)}% while the wheel is only ${r.px.toFixed(1)}px, `
          + `under the ${TARGET}px standard — that is a ratio ceiling, not a size`);
      }
      if (r.px > TARGET + 0.5) {
        bad.push(`${n} wheels at ${r.w}px: wheel renders ${r.px.toFixed(1)}px, `
          + `past the ${TARGET}px standard size`);
      }
    });
    for (let i = 1; i < rows.length; i++) {
      if (rows[i].px < rows[i - 1].px - 0.5) {
        bad.push(`${n} wheels: ${rows[i].w}px gives a ${rows[i].px.toFixed(1)}px wheel, `
          + `SMALLER than the ${rows[i - 1].px.toFixed(1)}px at ${rows[i - 1].w}px`);
      }
    }
  }
  ok(bad.length === 0, bad.join('\n      '));
});

test('gear size does not track the shape of the viewport at constant area', () => {
  /* GitHub #75, as measured: swept wide to square at a constant screen AREA, the
     wheels moved 1.8x -- 325.9px at 3.3:1 against 178.1px at 1:1 -- because both
     binding limbs of the fit read the long axis and the two cross-axis limbs are
     ceilings, which shrink a gear and never grow one. Rotating a window changed
     nothing, which is what says it was shape and not orientation.

     The bound is not zero spread. LINK_SHARE still binds where the chain
     genuinely cannot fit the axis, which is correct and is most of what is left.
     Both endpoints are measured through this same harness, at the issue's own
     shapes and its own constant area: the outgoing rule gives 1.82x
     (321/262/224/198/177px, which is the issue's measured table), and the
     standard size gives 1.26x (222/222/222/198/177px). The bound is the
     geometric midpoint of the two, 1.51 -- far enough from the survivor to
     tolerate a change in LINK_SHARE or the module, and nowhere near far enough
     to let the long-axis rule back in.

     ORIENTATION IS NOT SWEPT HERE, and that is not an omission: the fit is handed
     longAvail and crossAvail, so a rotated window is the same call with the same
     arguments. The issue measured it -- 1.6:1 landscape and 1:1.6 portrait give
     the same wheel -- which is what says the fault was shape, not rotation.
     tools/devices.py is where both orientations are actually drawn. */
  const fit = fitRule();
  const AREA = 2074 * 625;
  const px = (long, short) => {
    /* Solved extents scale with the chain, not the viewport: hold them fixed so
       the only thing moving between shapes is the viewport itself. */
    const r = fit(7, long, short, page.MODULE * 16.3 * 7, 210);
    return r.fit * r.wheelSpan;
  };
  const bad = [];
  const sizes = [3.3, 2.2, 1.6, 1.25, 1.0].map(ratio => {
    const long = Math.round(Math.sqrt(AREA * ratio));
    return { ratio, px: px(long, Math.round(AREA / long)) };
  });
  const spread = Math.max(...sizes.map(s => s.px)) / Math.min(...sizes.map(s => s.px));
  if (spread > 1.51) {
    bad.push(`at one constant area the wheel moves ${spread.toFixed(2)}x across shapes `
      + `(${sizes.map(s => s.ratio + ':1 ' + s.px.toFixed(0) + 'px').join(', ')}) — `
      + `gear size is tracking the long axis again (GitHub #75)`);
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

test('the configured chains still clear the legibility floors', () => {
  /* WHEELS SHRINK AS CHAINS ARE ADDED. That is accepted -- it is what putting
     more than one person on stage costs. What is not accepted is that the layout
     goes on WORKING long after the page has stopped being READABLE, with nothing
     failing anywhere in between. Three things go before the geometry does: the
     engraving band is module-derived, so it shrinks with the wheel and takes the
     lettering down with it; the epicyclic inside a wheel is dealt against
     MIN_MODULE, so its teeth are the first marks to stop reading as teeth; and
     the hub badge has an ABSOLUTE 30px floor in a page where everything else
     scales, so it is the one mark that grows relative to the bore it sits in.

     WHERE THE FLOORS COME FROM, because a legibility gate that invents its own
     thresholds computes its own answer and agrees with itself forever:

       THE SCALE FLOOR is read out of gearSvg's own px(want, lo, hi) calls. Those
       are #61's rendered-pixel intents: `want` is a number of RENDERED pixels and
       the clamp turns it into solve units by dividing by S. Below S = want/hi the
       ceiling binds instead, and the feature is drawn THINNER than the pixels it
       says it needs. The largest want/hi in gearSvg is therefore the scale at
       which the page can no longer honour a floor it states in rendered pixels.
       Derived from the page, not chosen here.

       THE CROSS-AXIS FLOOR is the page's own rule, stated at LINK_SHARE and
       enforced by idlerCount(): the bleed "exists so a serpentine may run off the
       top and bottom of a wide screen, not so a bridge may hang off the side" --
       CROSS_BLEED costs a serpentine nothing, because its top and bottom are
       ghost runs, and costs a stacked composition a person's badge. So the
       stacked composition's own cross demand, STAGE_CROSS, has to fit crossAvail
       WITHOUT spending the bleed.

     NO RENDERED-PIXEL FLOOR EXISTS IN THE PAGE FOR THE BAND OR FOR THE EPICYCLIC
     MODULE, and this test does not invent one. MIN_ENGRAVE (0.30 modules) and
     MIN_MODULE (1.8 solve units) are both scale-free, which is exactly what #61
     established a legibility floor cannot be -- at the shipped two-chain portrait
     scale both are already under their own number when read as pixels, so
     asserting them as pixels would fail the configuration Charles has approved.
     What IS sourced is the scale below which the page's stated rendered-pixel
     intents stop being satisfiable; and since the band, its lettering and the
     epicyclic module are all solve-unit constants multiplied by that same scale,
     it bounds all three. Their measured pixel sizes are reported in the failure
     so it names the thing you would actually see, not only the scale.

     EVERY INPUT IS EXECUTED OUT OF index.html: the fit expression through
     fitRule(), NOMINAL_SPAN read back out of it, STAGE_CROSS and IDLERS_FOR as
     the page's own declarations, axisRot() and idlerCount() as the page's own
     methods against a stub window, the 1% quantisation as the page's own line,
     and the badge size as the page's own three lines. Nothing here is a model of
     the page; a copy would pass while the page was broken.

     BOTH ESTIMATES ERR TOWARD PASSING, deliberately. NOMINAL_SPAN "lands UNDER a
     real solve rather than over it", and STAGE_CROSS is an estimate the page uses
     to choose an idler count rather than a measurement of the finished solve --
     it understates what is really on stage, which carries badges and datum plates
     as well as wheels. So the scale computed here is an UPPER bound on the real
     one and the cross extent a LOWER bound: anything this gate fires on, the real
     page cannot beat.

     PORTRAIT IS IN THE SWEEP because it has roughly half the cross axis of a
     laptop and a bridge is paid for in cross axis. It is the orientation that
     goes first, and 1440x900 on its own would not see it. */
  const fit = fitRule();
  const people = page.TRAIN_LENS.length;
  const spine = Math.max(...page.TRAIN_LENS);

  /* The scale floor, out of gearSvg's own rendered-pixel intents. */
  const intents = [...grabBlock('gearSvg(g, S) {', '{', '}')
    .matchAll(/\bpx\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)/g)]
    .map(m => ({ want: +m[1], hi: +m[3] }));
  /* A gate that extracts nothing passes vacuously, which is worse than no gate. */
  ok(intents.length >= 4, 'found only ' + intents.length + ' px() rendered-pixel '
    + 'intents in gearSvg — the extraction is broken, not the page');
  const S_MIN = Math.max(...intents.map(p => p.want / p.hi));

  /* The page's own cross-axis demand, idler rule, rotation test and quantisation. */
  const STAGE_CROSS = new Function('MODULE', 'TEETH_MEAN', 'STAGE',
    grabDecl('const STAGE_CROSS =') + ' return STAGE_CROSS;')(
    page.MODULE, page.TEETH_MEAN, { people: new Array(people).fill(0) });
  const IDLERS_FOR = new Function('MIN_IDLERS', 'MAX_IDLERS',
    grabDecl('const IDLERS_FOR =') + ' return IDLERS_FOR;')(
    grabNumber('MIN_IDLERS'), grabNumber('MAX_IDLERS'));
  const rotAt = new Function('window',
    'const o = { ' + grabBlock('axisRot() {', '{', '}') + ' }; return o.axisRot();');
  /* `this._idlerN` is undefined on a stub, which is the fresh-load branch of the
     hysteresis: one nominal wheel of cross axis must be SPARE to take the second
     idler. That is the branch that takes fewer idlers, so it asks for less cross
     axis — the generous direction, consistent with the rest of this test. */
  const idlersAt = new Function('window', 'MODULE', 'TEETH_MEAN', 'LINK_SHARE',
    'NOMINAL_SPAN', 'STAGE_CROSS', 'MAX_IDLERS', 'MIN_IDLERS', 'IDLERS_FOR',
    'TARGET_GEAR_PX', 'WHEEL_SPAN',
    'const o = { ' + grabBlock('axisRot() {', '{', '}') + ', '
    + grabBlock('idlerCount() {', '{', '}') + ' }; return o.idlerCount();');
  /* Quantised DOWN to 1% before anything is drawn at it, so the scale the marks
     are actually rasterised at is this one, not the raw fit. */
  const quantise = new Function('fit', grabDecl('const gsr =') + ' return gsr;');

  /* The handle's type size and the epicyclic's module, both as the page writes
     them: `fit(handle, mid, m * 0.80)` in engraving(), and m2 = 2*bore/(Zr+4)
     inside planetaryMenuFor(), executed rather than re-typed. */
  const handleEm = (SRC.match(/fit\(handle,\s*mid,\s*m\s*\*\s*([0-9.]+)\)/) || [])[1];
  ok(handleEm, 'could not find the handle type size in engraving()');
  const m2Of = new Function('bore', 's', grabDecl('const m2 = 2 * bore') + ' return m2;');
  /* The tightest epicyclic set the page can deal, over every blank it will
     actually seat one on. `fallback` blanks hold no set at all — an honest
     answer, and the deal never seats an epicyclic there. */
  let worstM2 = Infinity, worstAt = 0;
  const holds = [];
  for (let t = page.TEETH_MIN; t <= page.TEETH_MAX; t++) {
    const menu = page.planetaryMenuFor(t);
    if (menu.fallback) continue;
    holds.push(t);
    const bore = page.planetaryBore(t);
    menu.one.forEach(v => {
      const m = m2Of(bore, { Zr: v.pg[2] });
      if (m < worstM2) { worstM2 = m; worstAt = t; }
    });
    menu.two.forEach(v => {
      const m = m2Of(bore, { Zr: v.pg2[3] });
      if (m < worstM2) { worstM2 = m; worstAt = t; }
    });
  }
  ok(holds.length > 0, 'no blank in the deal can hold an epicyclic at all');

  /* The badge, as the render builds it: an absolute 30px floor inside a min()
     against the axle cap. The floor is the reason this is checked at all — it is
     the one size on the wheel that does not shrink with the machine. */
  const badgeSize = new Function('g', 'S',
    SRC.slice(SRC.indexOf('const epicyclic = g.kind ==='),
      SRC.indexOf(';', SRC.indexOf('const size = Math.min(cap * S')) + 1)
    + ' return size;');

  const bad = [];
  [[390, 844], [1440, 900]].forEach(([w, h]) => {
    const win = { innerWidth: w, innerHeight: h };
    const turned = rotAt(win) !== 0;
    const longAvail = turned ? h : w, crossAvail = turned ? w : h;
    /* NOMINAL_SPAN is computed inside the rule from the page's own line; read it
       back out rather than deriving a second copy here. It is also what
       longSolved is set to: on a stacked stage the linked run along the long axis
       IS the spine, and the page's own estimate of its span is that line. */
    const NOMINAL_SPAN = fit(spine, longAvail, crossAvail, 1, 1).NOMINAL_SPAN;
    const idlers = idlersAt(win, page.MODULE, page.TEETH_MEAN, grabNumber('LINK_SHARE'),
      NOMINAL_SPAN, STAGE_CROSS, grabNumber('MAX_IDLERS'), grabNumber('MIN_IDLERS'),
      IDLERS_FOR, grabNumber('TARGET_GEAR_PX'),
      wheelSpanOf(Array.from({ length: spine }, () => ({ teeth: page.TEETH_MAX }))));
    const crossSolved = STAGE_CROSS(idlers);
    const S = quantise.call({ props: {} },
      fit(spine, longAvail, crossAvail, NOMINAL_SPAN, crossSolved).fit);

    const bandPx = S * page.MODULE * page.BAND_DEPTH;
    const typePx = S * page.MODULE * parseFloat(handleEm);
    const at = `${w}x${h}, ${people} chain${people === 1 ? '' : 's'}`;
    if (S < S_MIN) {
      bad.push(`${at}: the stage renders at ${S.toFixed(2)}x, under the ${S_MIN.toFixed(2)}x `
        + `at which gearSvg's own rendered-pixel floors (#61) stop being satisfiable — `
        + `the engraving band lands at ${bandPx.toFixed(1)}px carrying ${typePx.toFixed(1)}px `
        + `lettering, and the tightest epicyclic set the deal can reach (${worstAt} teeth) `
        + `renders its module at ${(worstM2 * S).toFixed(2)}px against MIN_MODULE ${page.MIN_MODULE}`);
    }
    if (crossSolved * S > crossAvail) {
      bad.push(`${at}: the composition wants ${(crossSolved * S).toFixed(0)}px of cross axis `
        + `at ${S.toFixed(2)}x and the viewport has ${crossAvail}px — a stacked stage may not `
        + `spend CROSS_BLEED (see LINK_SHARE and idlerCount): the bleed is for a serpentine's `
        + `ghost runs, and here it hangs a person's badge off the edge`);
    }
    holds.forEach(t => {
      const badge = badgeSize({ kind: 'planetary', r: page.MODULE * t / 2 }, S);
      const bore = 2 * page.planetaryBore(t) * S;
      if (badge >= bore) {
        bad.push(`${at}: on a ${t}-tooth blank the hub badge is ${badge.toFixed(1)}px across `
          + `and the bore it sits in is ${bore.toFixed(1)}px — the works vanish behind the cap`);
      }
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
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
