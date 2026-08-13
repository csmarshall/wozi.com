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

/* config.js is a plain script that assigns one global, so RUNNING it is the most
   direct read there is of what ships -- no parsing, no comment stripping, and
   nothing here that has to know the shape of a key. Seven tests wanted it, each
   with its own copy of this line; it has one home now (#99). Fresh each call, so
   a test that mutates what it gets back cannot reach any other. */
function loadConfig() {
  const win = {};
  new Function('window', CFG_SRC)(win);
  return win.WOZI_CONFIG;
}

/* ---- extraction: pull the real thing out of the real page ---------------- */

/* COMMENTS ARE MASKED, NOT DELETED, AND THE MASK IS LENGTH-PRESERVING (GitHub
   #101, #137). Every extractor below matches against the mask and then slices
   the ORIGINAL, so an anchor can never be satisfied by prose while the text
   handed back to the suite is still the real page, comments and all -- which
   matters, because two tests regex the extracted block for things a comment is
   allowed to mention (`applyRotation()` and its clocks, `approachSpeed()` and
   the formula it retired).

   Length-preserving is what makes that possible: a deleted comment moves every
   offset after it, so a match position in the stripped text says nothing about
   where the block starts in the file. Spaces keep the two in lockstep, and they
   are strictly safer than deletion for grabNumber() too -- deleting the comment
   in `A =<block comment> 3` joins two tokens that were never adjacent.

   THE SCANNER IS DELIBERATELY NAIVE, AND THE DIRECTION OF ITS ERROR IS THE
   ARGUMENT. `tools/strip_comments.py` needs a real state machine because it
   REMOVES text from a file that then has to run: it must not mistake
   `'https://…'`, a template literal or the `/*` inside a regex literal for a
   comment. This mask is only ever used to LOCATE an anchor, so its two failure
   modes are not symmetric:

     - mask something that was live code -> the anchor vanishes or moves, and
       every caller throws. LOUD.
     - leave a comment unmasked -> prose satisfies an anchor again. SILENT, and
       exactly the bug being closed.

   So it errs toward masking: block comments and markup comments, first match
   wins, no string or regex awareness. Checked against the file it reads rather
   than assumed -- index.html carries 722 `/*` and 9 `<!--`, they pair up (so
   nothing nests), it has no `//` line comments at all, and masking all 731
   leaves every `<script>` body still passing `node --check`, which is the proof
   that no `/*` in this file lives inside a string, a template or a regex today.
   If one ever does, the anchors in that region go missing and the suite says so.
   Line comments are not handled for the same reason they need care: `//` in
   `'https://fonts.googleapis.com'` is not a comment, and neither file has a real
   one to gain by guessing. */
function maskComments(src) {
  const out = src.split('');
  let i = 0;
  while (i < src.length) {
    let end = -1;
    if (src.startsWith('<!--', i)) {
      const j = src.indexOf('-->', i + 4);
      end = j < 0 ? src.length : j + 3;
    } else if (src.startsWith('/*', i)) {
      const j = src.indexOf('*/', i + 2);
      end = j < 0 ? src.length : j + 2;
    }
    if (end < 0) { i++; continue; }
    for (let k = i; k < end; k++) if (out[k] !== '\n') out[k] = ' ';
    i = end;
  }
  return out.join('');
}

/* Memoised per source string. grabBlockFrom() is called ~37,000 times in a run
   over a 632KB file, and the mask is O(n) -- one per distinct src (index.html,
   config.js, and one small fragment per person) rather than one per call. */
const MASKED = new Map();
function maskedOf(src) {
  let m = MASKED.get(src);
  if (m === undefined) { m = maskComments(src); MASKED.set(src, m); }
  return m;
}

const STRIPPED_SRC = maskedOf(SRC);

/* CONTRACT (GitHub #101, CL#112): returns the value of the ONE live
   `NAME = <number>` assignment in index.html. Throws if NAME is assigned more
   than once in the comment-stripped source -- even if only one of those
   assignments' right-hand side is a plain number literal.

   That last clause is not paranoia: it is exactly the shape of the bug this
   closes. index.html declares CELL_MIN twice -- a retired honeycomb family's
   `CELL_MIN = 2.8` and hexcore's live `CELL_MIN = px(3.9, 2.2, 6.0)`. The old
   "first numeric match wins" grabNumber matched only the first, because
   `px(...)` is not a number literal and never matched the pattern at all --
   so the retired figure was not merely preferred, it was the ONLY thing this
   function could see, and it returned 2.8 with no error whatsoever. Counting
   plain-number matches alone would still miss that: there was exactly one.
   What actually disambiguates it is counting ASSIGNMENTS to the name,
   literal or not -- CELL_MIN has two, so this now refuses to guess between
   them.

   A name assigned exactly once, whose value is not a number literal, still
   throws below via the "not found" path -- correct, since there is nothing
   here this function could honestly call a number.

   Ambiguity is the caller's problem to resolve, not this function's to guess
   at: rename one of the colliding declarations, or extend this function with
   a scope/anchor parameter (index.html itself is out of scope for this fix --
   see CHANGELOG CL#112). */
function grabNumber(name) {
  const assignments = [...STRIPPED_SRC.matchAll(new RegExp('\\b' + name + '\\s*=(?!=)', 'g'))];
  if (assignments.length > 1) {
    throw new Error('constant ' + name + ' is assigned ' + assignments.length +
      ' times in index.html -- grabNumber() cannot tell which one ships ' +
      '(the CELL_MIN trap, GitHub #101). Give it a unique name, or teach ' +
      'grabNumber() to scope the search.');
  }
  const m = STRIPPED_SRC.match(new RegExp('\\b' + name + '\\s*=\\s*(-?[0-9]+(?:\\.[0-9]+)?)'));
  if (!m) throw new Error('constant not found in index.html: ' + name);
  return parseFloat(m[1]);
}

/* WOZI_ANCHOR_DUMP=<path>: append every extraction -- where it came from, the
   anchor that found it, its length and its text. Nothing reads this in CI. It
   exists because the only honest way to change an extractor is to prove all 66
   anchors still resolve to the same bytes: dump, change, dump, diff. Hardening
   this file (GitHub #137) was verified that way, and the next edit to it can be
   too, which is why the hook stays rather than being deleted with the diff it
   was written for. Read once, not per call: the suite resolves ~37,000 anchors
   and an instrument is not allowed to cost anything when it is switched off. */
const ANCHOR_DUMP = process.env.WOZI_ANCHOR_DUMP || '';
function noteAnchor(where, decl, text) {
  if (ANCHOR_DUMP) {
    fs.appendFileSync(ANCHOR_DUMP,
      '=== ' + where + ' :: ' + JSON.stringify(decl) + ' :: ' + text.length + '\n' + text + '\n');
  }
  return text;
}

/* AN ANCHOR NEVER CARRIES INDENTATION, IN EITHER DIRECTION (GitHub #137).
   Turning `  solve() {` into a pattern: leading whitespace is dropped, and every
   newline inside the anchor matches a newline plus whatever indentation the file
   happens to use. So an anchor says WHICH LINES, never HOW FAR IN, and
   re-indenting a method -- moving it into or out of a block, changing the file's
   indent width -- cannot break the suite without changing a line of logic. The
   old anchors baked two spaces into 21 of the 66 strings, which made
   `git diff -w`-clean edits load-bearing.

   The lead is not thrown away, though: PRESENT means "first thing on its line",
   at any indentation. That is what keeps `  solve() {` off `this.solve() {`-shaped
   text elsewhere, and it is a property of the source's structure rather than of
   its whitespace. Absent means "anywhere", which is what the method-in-a-class
   anchors (`gearSvg(g, S) {`) have always relied on. */
function anchorPattern(decl) {
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return decl.split(/\r?\n[ \t]*/).map(esc).join('\\n[ \\t]*');
}

/* CONTRACT (GitHub #137, the #101 fault in the sibling function): returns the
   offset in `src` of the ONE place the anchor matches with comments masked, and
   REFUSES rather than guessing when there is more than one.

   `grabBlockFrom` had none of CL#112's hardening and 66 anchors against
   grabNumber's 13. It took the first `indexOf` of its anchor, in the raw file,
   so a second occurrence -- a copy of the same `forEach` further down, or the
   anchor's own text quoted in the prose above it -- silently yielded a different
   block. That does not fail: it makes a PASSING TEST MEASURE THE WRONG CODE,
   which is the one outcome a suite must never produce, and it became load-bearing
   twice over when CL#159 started running this suite against the stripped artifact
   as the only gate that reads the page as text.

   Ambiguity is the caller's to resolve, exactly as in grabNumber: extend the
   anchor over the next line until it is unique (`\n` costs nothing now that it
   ignores indentation), or scope the search by passing a narrower `src` -- the
   parameter grabNumber's docstring wishes it had. Two anchors needed the first of
   those, `BRIDGES.forEach(b => {` and `ORIGINS.forEach(o => {`, both of which
   solve() carries a second copy of; they had been reading the right block by
   luck of file order alone.

   The not-found path distinguishes the two ways of missing. An anchor that is
   nowhere is a stale anchor; an anchor that is in the file but only inside a
   comment is the #101 trap itself, and saying which one it is turns a five-minute
   grep into a sentence.

   Memoised for the same reason maskedOf() is: the suite resolves ~37,000 anchors,
   all of them one of ~114 distinct strings against one of a handful of sources,
   and a global regex over 632KB per call turns an 8-second gate into a 35-second
   one. Both `src` and the answer are immutable, so the cache cannot go stale
   within a run -- and a throw is cached as a throw, so a refusal stays a refusal
   however many callers ask, rather than being loudest for the first caller and
   silent for the rest. */
const ANCHOR_AT = new Map();
function locateAnchor(src, where, what, decl) {
  let byDecl = ANCHOR_AT.get(src);
  if (byDecl === undefined) ANCHOR_AT.set(src, byDecl = new Map());
  const hit = byDecl.get(decl);
  if (hit !== undefined) {
    if (typeof hit === 'number') return hit;
    throw hit;
  }
  try {
    const at = locateAnchorOnce(src, where, what, decl);
    byDecl.set(decl, at);
    return at;
  } catch (e) {
    byDecl.set(decl, e);
    throw e;
  }
}
function locateAnchorOnce(src, where, what, decl) {
  const lead = /^[ \t]*/.exec(decl)[0];
  const body = decl.slice(lead.length);
  const masked = maskedOf(src);
  const re = new RegExp(anchorPattern(body), 'g');
  const hits = [];
  let m;
  while ((m = re.exec(masked)) !== null) {
    re.lastIndex = m.index + 1;   /* overlapping occurrences are occurrences too */
    let at = m.index;
    if (lead) {
      let p = at;
      while (p > 0 && (masked[p - 1] === ' ' || masked[p - 1] === '\t')) p--;
      if (p !== 0 && masked[p - 1] !== '\n') continue;
      /* Back over the real indentation so the block reads as it does in the
         file. Over the MASK for the line test and over the SOURCE here, and the
         difference is load-bearing on the stripped artifact: its line is a
         backlink marker followed by `  solve() {`, and the marker is whitespace
         to the line test while having to stay out of the extracted text. */
      while (at > 0 && (src[at - 1] === ' ' || src[at - 1] === '\t')) at--;
    }
    hits.push(at);
  }
  if (hits.length > 1) {
    throw new Error(what + ' anchor ' + JSON.stringify(decl) + ' matches ' +
      hits.length + ' places in ' + where + ' with comments masked -- ' +
      'the extractor cannot tell which one ships (the CELL_MIN trap, GitHub ' +
      '#101, in grabBlockFrom this time: GitHub #137). Extend the anchor over ' +
      'the next line until it is unique -- indentation inside it is ignored -- ' +
      'or scope the search by passing a narrower src.');
  }
  if (!hits.length) {
    const inProse = new RegExp(anchorPattern(body)).test(src);
    throw new Error(what + ' not found in ' + where + ': ' + decl +
      (inProse ? ' -- it IS in the file, but only inside a comment, so nothing '
        + 'live matches it (GitHub #101/#137). The declaration it names has '
        + 'probably been renamed or commented out.' : ''));
  }
  return hits[0];
}

/* Brace-matched from the anchor, counted over the MASK: a `{` in prose used to
   count toward the depth, so a comment inside the block carrying an unbalanced
   brace -- or a `}` in a sentence before the real one -- ended the block early.
   The slice comes off `src`, so what the suite executes is still the page's own
   text with its own comments in it. */
function grabBlockFrom(src, where, decl, open, close) {
  const i = locateAnchor(src, where, 'block', decl);
  const masked = maskedOf(src);
  const j = masked.indexOf(open, i);
  if (j < 0) throw new Error('block never opens with ' + open + ' in ' + where + ': ' + decl);
  let depth = 0;
  for (let k = j; k < masked.length; k++) {
    if (masked[k] === open) depth++;
    else if (masked[k] === close) { depth--; if (depth === 0) return noteAnchor(where, decl, src.slice(i, k + 1)); }
  }
  throw new Error('unterminated block: ' + decl);
}
function grabBlock(decl, open, close) {
  return grabBlockFrom(SRC, 'index.html', decl, open, close);
}

/* WHICH ANSWER index.html SHIPS to "where does an independent chain's own drive
   come from" (GitHub #116, CL#123) -- executed, not pattern-matched, because
   grabNumber() reads numbers and this one is a word. Every fixture below builds
   at the shipped value unless it deliberately asks for the other, so the suite
   moves with the constant rather than pinning it: the two readings are an A/B
   awaiting Charles's call, and a harness that hardcoded one would start failing
   the day the default flipped, which is a test measuring the wrong thing. */
const PAGE_ORIGIN_MOUNT = new Function(
  grabDecl('const ORIGIN_MOUNT =') + ' return ORIGIN_MOUNT;')();

/* engraving()'s handle/stamp type sizes, as fractions of MODULE -- read out of
   the page's own line rather than retyped as two separate literals (GitHub
   #102). `const T0 = fit(handle, mid, m * 0.80), B0 = fit(stamp, mid, m *
   0.60);` is the one place both numbers are declared; a copy of either would
   keep passing if engraving()'s own line changed. */
const ENGRAVE_SIZES = (function () {
  const m = SRC.match(/const T0 = fit\(handle, mid, m \* ([0-9.]+)\), B0 = fit\(stamp, mid, m \* ([0-9.]+)\);/);
  if (!m) throw new Error('could not find engraving()\'s handle/stamp type-size line in index.html');
  return { handle: parseFloat(m[1]), stamp: parseFloat(m[2]) };
})();

const page = (function build() {
  const consts = ['MODULE', 'TOOTH_ADD', 'TOOTH_DED', 'TOOTH_ROOT_MIN', 'BAND_RISE',
    'BAND_DEPTH', 'RIM_UNDER_BAND', 'BASELINE_MID', 'ROOT_MARGIN', 'MIN_MODULE',
    'TEETH_MIN', 'TEETH_MAX', 'TEETH_SLACK', 'TEETH_HOST',
    'ANG_MIN', 'ANG_MAX',
    /* The clear-metal gap engraving()'s fit() solves its sweep cap FROM (GitHub #98).
       Read out of the page so the gap-constancy test below measures the ratio
       the page actually ships, not a copy of it. */
    'ENGRAVE_GAP',
    /* The one figure on this page stated in RENDERED pixels rather than in
       modules (#76). Read from the page like everything else, so the suite
       measures the bound that ships rather than a copy of it. */
    'PLATE_TOP_CLEAR',
    /* And the second one (#95), which acts ALONG the line where PLATE_TOP_CLEAR
       acts across it. Read from the page for the same reason, and named apart
       from it for the reason the constants themselves give. */
    'PLATE_START_ALONG',
    /* How far an escape run may wander off its own axis. fitEscapes both deals the
       wobble with it and derives its wheel-count backstop from it (#80), so the
       suite has to hand it in or the extracted function throws. */
    'ESCAPE_WOBBLE',
    /* fitEscapes' named search policy (GitHub #103) -- extracted and run for
       real by fitEscapesOn(), which throws ReferenceError on any of these
       without them handed in the same way ESCAPE_WOBBLE already is. */
    'ESCAPE_CROSS_EXT_PX', 'ESCAPE_MIN_REACH_PX', 'ESCAPE_RUN_MARGIN',
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
  /* TRAIN is no longer a literal -- it is built from the active person's links
     in config.js, so the length is counted there.

     COUNTED BY RUNNING config.js, NOT BY READING IT. It used to strip comments
     out of the PEOPLE block, brace-walk it into one text per person and count
     `href:` in each -- an arrangement that knew the NAME OF A KEY a link happens
     to carry, and #99 took that key away: a link is a slug plus a handle now,
     and only the odd one out still writes an href. Counting a key is the same
     shape of coupling as counting a slug was, and it was one refactor from
     reporting a train of length 0 and dealing the geometry against it.
     Executing the file is the strictly more direct read of the same source, and
     it drops the comment stripping with it -- a retired wheel is commented out
     rather than deleted, and a comment simply is not in the array.

     COUNTED PER PERSON, NOT OVER THE WHOLE LIST. It used to be one count across
     every chain, guarded by an assertion that there was exactly one -- which was
     honest only while that held. A second chain means only ONE person is ever on
     stage at a time, so summing them would measure a train the page never builds.
     Every chain is now measured on its own, and the deal tests below run against
     each of them: the geometry has to be legal for whoever is on stage, and the
     shortest chain is the one that strains the bounds. */
  const people = loadConfig().PEOPLE || [];
  if (!people.length) throw new Error('no people found in config.js PEOPLE');
  const trainLens = people.map(p => (p.links || []).length);
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
    /* BAND_MAX and ENDS_MAX stopped being literals at GitHub #97 (CL#130): they
       are now derived from STEP_DRIFT_MAX, itself an expression over MODULE and
       the tooth/bearing range, so grabNumber() -- which only ever matched a bare
       numeric literal -- cannot read them any more. Grabbed as the real
       declarations instead of re-derived here, for the same reason endsCapFor is
       grabbed as a block below: a copy of the arithmetic is exactly the drift
       this suite exists to catch. */
    + grabDecl('const STEP_DRIFT_MAX =') + '\n'
    + grabDecl('const BAND_MAX =') + '\n'
    + grabBlock('function endsCapFor(', '{', '}') + '\n'
    /* ESCAPE_SEARCH_ARC is an array, so grabNumber() cannot read it -- grabbed
       as the real declaration like STEP_DRIFT_MAX/BAND_MAX above. */
    + grabDecl('const ESCAPE_SEARCH_ARC =') + '\n'
    + 'return { planetaryBore, planetaryMenuFor, RAVIGNEAUX_MENU, PLANETARY_FLAVOURS, '
    + 'endsCapFor, TEETH_MEAN, STEP_DRIFT_MAX, BAND_MAX, ENDS_MAX, ESCAPE_SEARCH_ARC, '
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

/* ---- 0a. the extractor itself --------------------------------------------- */

test('grabNumber() refuses an ambiguous CELL_MIN rather than guessing (GitHub #101, CL#112)', () => {
  /* index.html declares CELL_MIN twice: a retired honeycomb family's literal
     `CELL_MIN = 2.8`, and hexcore's live `CELL_MIN = px(3.9, 2.2, 6.0)`. Before
     CL#112, grabNumber() took the FIRST regex match with no ambiguity check at
     all, and since px(...) is not a number literal the retired 2.8 was not
     merely preferred -- it was the only thing the old extractor could see, and
     it returned that with no error whatsoever.

     Tolerant of either fixed shape on purpose: if a later change removes the
     retired duplicate from index.html (out of scope for this ticket -- see
     CHANGELOG CL#112), CELL_MIN stops being ambiguous and grabNumber() should
     simply resolve it, so this only insists that the retired figure is never
     silently returned again. */
  let result, threw = null;
  try { result = grabNumber('CELL_MIN'); } catch (e) { threw = e; }
  if (threw) {
    ok(/CELL_MIN/.test(threw.message),
      'grabNumber(\'CELL_MIN\') threw, but its message does not name the constant: ' + threw.message);
  } else {
    ok(result !== 2.8,
      'grabNumber(\'CELL_MIN\') silently returned the retired honeycomb literal (2.8) ' +
      'instead of throwing or reading the live hexcore value -- CL#112 regressed');
  }
});

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

test('?seed= is installed before the first draw it is meant to fix', () => {
  /* ?seed= works by replacing Math.random, so its ONE requirement is position:
     every draw in the file has to happen after the replacement. The deal is not
     a function anybody calls -- dealTeeth() and dealAngles() are IIFEs that run
     at module load -- so a draw moved above the installer, or the installer
     moved below one, silently un-seeds the page while every other gate stays
     green. Both harnesses inject their own generator ahead of all page script,
     so NEITHER of them can see this break: it is the one thing about this
     feature that only a static read of the file can assert.

     Checked as source positions rather than by running the page, for the same
     reason the rest of this suite is static -- it gates before Chrome exists. */
  /* Comments stripped first, and that is not fastidiousness: the installer's own
     block comment counts the draw sites by name, so a prose mention sits above
     the installer forever and would fail this on the day it was written. */
  const code = SRC.replace(/\/\*[\s\S]*?\*\//g, '');
  const install = code.indexOf('Math.random = function');
  ok(install >= 0, 'index.html no longer installs a seeded Math.random');
  const draws = [];
  const re = /Math\.random\(\)/g;
  let m;
  while ((m = re.exec(code))) draws.push(m.index);
  ok(draws.length > 0, 'index.html draws nothing at random — has the deal gone?');
  const early = draws.filter(i => i < install);
  ok(early.length === 0,
    `${early.length} Math.random() call(s) run before the ?seed= installer at ${install}`
    + ` (first at ${early[0]}) — those draws cannot be seeded`);
});


/* ---- 0b. the deploy whitelist -------------------------------------------- */

/* WHAT A PUBLISH STEP IS, STRUCTURALLY. It is not "a step whose prose mentions a
   file" and it is not "a step whose name contains the word publish" -- both of
   those are the bug this section replaces (GitHub #89). It is a step that runs
   `aws s3 cp` or `aws s3 sync` with a DESTINATION under $BUCKET. That is the only
   thing in the workflow that puts bytes on the web, so it is the only thing worth
   asserting about, and a comment cannot accidentally be one.

   The old assertion was /\bconfig\.js\b/ over the whole of deploy.yml. config.js
   is named there seven times -- once in the loop that publishes it, twice in
   comments explaining why it matters, four times in the live-site checks -- so
   deleting it from the publish loop left the suite at 77 passed, 0 failed. The
   guard written to stop #59 recurring was satisfied by its own explanatory
   comments. Narrowing the pattern would have been the same bug with a smaller
   window; the fix is to stop reading prose and start reading the commands. */

const WORKFLOW = fs.readFileSync(
  path.join(__dirname, '..', '.github', 'workflows', 'deploy.yml'), 'utf8');

/* Split the workflow into steps, and reduce each to the SHELL it actually runs:
   the body of its `run: |` block, with shell comments removed and line
   continuations folded so a command spanning five lines is one string. YAML-level
   comments never enter, because only run bodies are collected. */
function workflowSteps(wf) {
  const all = wf.split('\n');
  /* Start AT the steps: key, not at the top of the file -- `on: push: paths-ignore:`
     carries list items at the very same indent, and a scan of the whole document
     picks them up as steps. They have no run block so they change no verdict, but
     a parser that reports four phantom steps is one nobody can check by eye. */
  /* EVERY job's steps block, not the first one (GitHub #184, CL#199). This took
     the FIRST `steps:` and stopped at the first dedent, which collected the whole
     workflow while it was a single job -- and silently collected only `build` the
     moment CL#198 split it into five. The assertion above is about the WHOLE
     workflow: it asks whether some publish step copies each published file, and a
     parser that can only see one job answers a narrower question than the test
     asks. It failed LOUDLY rather than passing on a partial read, which is the only
     reason this was a five-minute fix -- see the `no publish step was found`
     message it carries. */
  const blocks = [];
  for (let i = 0; i < all.length; i++) {
    const m = all[i].match(/^(\s*)steps:\s*$/);
    if (!m) continue;
    const stepsIndent = m[1].length;
    const body = [];
    for (let j = i + 1; j < all.length; j++) {
      const raw = all[j];
      if (raw.trim() && raw.length - raw.trimStart().length <= stepsIndent) break;
      body.push(raw);
    }
    blocks.push({ stepsIndent, body });
  }
  if (!blocks.length) throw new Error('deploy.yml has no steps: block');
  const lines = [];
  for (const b of blocks) lines.push(...b.body);
  const stepsIndent = blocks[0].stepsIndent;
  const itemIndent = stepsIndent + 2;
  const marker = ' '.repeat(itemIndent) + '- ';

  const steps = [];
  let cur = null, runIndent = null;
  for (const raw of lines) {
    if (raw.startsWith(marker)) { cur = { name: null, run: [] }; steps.push(cur); runIndent = null; }
    if (!cur) continue;
    if (runIndent !== null) {
      /* A blank line does not end a block scalar; a dedent does. */
      if (!raw.trim() || raw.length - raw.trimStart().length > runIndent) { cur.run.push(raw); continue; }
      runIndent = null;
    }
    const nm = raw.match(/^\s*(?:-\s+)?name:\s*(.+?)\s*$/);
    if (nm && !cur.name) cur.name = nm[1];
    const rm = raw.match(/^(\s*)run:\s*\|\s*$/);
    if (rm) runIndent = rm[1].length;
  }
  return steps.map(s => ({
    name: s.name || '(unnamed step)',
    shell: s.run.map(l => l.replace(/(^|\s)#.*$/, '$1')).join('\n').replace(/\\\n\s*/g, ' ')
  }));
}

function unquote(s) { return s.replace(/^(['"])([\s\S]*)\1$/, '$2'); }

/* Every path one step copies to the bucket. TWO SHAPES, and the assertion has to
   understand both or a file moves between them and the guard evaporates:

     for f in support.js config.js; do aws s3 cp "$f" "$BUCKET/$f" ... done
     aws s3 cp robots.txt "$BUCKET/robots.txt" ...

   so a source that is a bare variable is resolved through the `for` loop that
   binds it, in the same step. A sync contributes a DIRECTORY rather than a file:
   assets/ publishes whatever is under it, and nothing here should have to know
   which icons exist. */
function publishedBy(step) {
  const loops = {};
  let m;
  const FOR = /\bfor\s+(\w+)\s+in\s+([^;\n]+?)\s*;\s*do\b/g;
  while ((m = FOR.exec(step.shell))) loops[m[1]] = m[2].trim().split(/\s+/);

  const files = [], dirs = [];
  const S3 = /\baws\s+s3\s+(cp|sync)\s+("[^"]*"|'[^']*'|\S+)\s+("[^"]*"|'[^']*'|\S+)/g;
  while ((m = S3.exec(step.shell))) {
    const dst = unquote(m[3]);
    if (!/\$\{?BUCKET\b/.test(dst)) continue;   /* not a write to the live site */
    const src = unquote(m[2]);
    const v = src.match(/^\$\{?(\w+)\}?$/);
    const paths = v ? (loops[v[1]] || []) : [src];
    if (m[1] === 'sync') dirs.push(...paths); else files.push(...paths);
  }
  return { files, dirs };
}

const PUBLISH = (function () {
  const steps = workflowSteps(WORKFLOW);
  const files = new Set(), dirs = new Set(), blind = [];
  steps.forEach(s => {
    if (!/\baws\s+s3\s+(?:cp|sync)\b/.test(s.shell)) return;
    const got = publishedBy(s);
    /* A step that copies to the bucket and yields no path means the PARSER has
       gone blind, not that the step publishes nothing -- exactly the failure this
       whole section exists to make impossible, so it is asserted rather than
       assumed. */
    if (!got.files.length && !got.dirs.length) blind.push(s.name);
    got.files.forEach(f => files.add(f));
    got.dirs.forEach(d => dirs.add(d.replace(/\/+$/, '') + '/'));
  });
  return { steps, files, dirs, blind };
})();

function isPublished(p) {
  if (PUBLISH.files.has(p)) return true;
  for (const d of PUBLISH.dirs) if (p.startsWith(d)) return true;
  return false;
}

/* What the site NEEDS published, derived from two sources already in the tree
   rather than typed here as a list that would drift the moment a file is added:

     1. the scripts index.html loads, plus index.html itself
     2. every URL the deploy's OWN live-site checks assert is reachable

   The second is the interesting one. `check https://wozi.com/robots.txt` is the
   deploy stating that the file has to be there; if no publish step copies it, the
   workflow is asserting something about a file it never uploads -- #59's shape
   ("the rules requiring a file the rules do not name") inside a single file. */
function requiredPaths() {
  let m;
  const fromPage = [];
  const SCRIPT = /<script\s+src="\.\/([^"]+)"/g;
  while ((m = SCRIPT.exec(SRC))) fromPage.push(m[1]);

  const fromLive = [];
  const shell = PUBLISH.steps.map(s => s.shell).join('\n');
  const CHECK = /\b(?:check|check_content_type|exact)\s+https:\/\/wozi\.com(\/\S*)/g;
  while ((m = CHECK.exec(shell))) {
    let p = m[1].replace(/^\//, '');
    if (!p || p.endsWith('/')) p += 'index.html';   /* a directory serves its index */
    fromLive.push(p);
  }

  /* Kept apart so each source can be shown to have found something. A path both
     of them name -- config.js is one -- must not make either look empty, which is
     what one shared map keyed by path did. */
  const need = new Map([['index.html', ['it is the page']]]);
  const add = (p, why) => {
    const seen = need.get(p) || [];
    if (!seen.includes(why)) seen.push(why);
    need.set(p, seen);
  };
  fromPage.forEach(p => add(p, 'index.html loads it'));
  fromLive.forEach(p => add(p, 'the deploy asserts it is live'));
  return { need, fromPage, fromLive };
}

test('every file the site needs is copied to the bucket by a publish step', () => {
  ok(PUBLISH.blind.length === 0,
    'a step copies to $BUCKET but no path could be read out of it, so this whole '
    + 'assertion is blind: ' + PUBLISH.blind.join(', '));
  ok(PUBLISH.files.size > 0 && PUBLISH.dirs.size > 0,
    'no publish step was found in .github/workflows/deploy.yml — the parser is '
    + 'reading nothing, so nothing below can fail');
  const { need, fromPage, fromLive } = requiredPaths();
  ok(fromPage.length > 0, 'no <script src="./…"> was found in index.html — the page '
    + 'half of this derivation found nothing');
  ok(fromLive.length > 0, 'no live-site check was found in deploy.yml — the deploy '
    + 'half of this derivation found nothing');
  const missing = [];
  need.forEach((why, p) => {
    if (!isPublished(p)) missing.push(p + ' (' + why.join('; ') + ')');
  });
  ok(missing.length === 0,
    'required but never copied to the bucket by any publish step in '
    + '.github/workflows/deploy.yml: ' + missing.join(', '));
});

test('every path the deploy publishes exists in the repo', () => {
  /* The other half of the same guarantee. A path in the publish list that is not
     in the tree fails the deploy at run time, on a live bucket, after the geometry
     and the browsers have all gone green -- and the suite can answer it in a
     millisecond. This is also what catches a rename that updated the repo and not
     the workflow. */
  const at = p => path.join(__dirname, '..', p);
  const missing = [];
  PUBLISH.files.forEach(f => {
    if (!fs.existsSync(at(f)) || !fs.statSync(at(f)).isFile()) missing.push(f);
  });
  PUBLISH.dirs.forEach(d => {
    if (!fs.existsSync(at(d)) || !fs.statSync(at(d)).isDirectory()) missing.push(d);
  });
  ok(missing.length === 0,
    'named in a publish step in .github/workflows/deploy.yml but not in the repo, '
    + 'so the deploy would fail against the live bucket: ' + missing.join(', '));
});

test('the deploy publishes nothing it is documented never to publish', () => {
  /* CLAUDE.md: legacy/ is the archive of everything retired from the bucket, and
     every document in the repo root stays off a public site. The whitelist exists
     so that a new file cannot reach the web by being forgotten; this is the same
     rule read from the other end, and it can only be checked once the publish
     steps are parsed rather than grepped. */
  const bad = [...PUBLISH.files, ...PUBLISH.dirs]
    .filter(p => /^legacy\//.test(p) || /^[^/]+\.md$/i.test(p));
  ok(bad.length === 0,
    'a publish step would copy an archived or repo-only document to the live '
    + 'bucket: ' + bad.join(', '));
});

/* The real SITES builder, sliced out of index.html and run against whatever
   config it is handed. A service owns its URL stem and a person owns only their
   handle (#99), so a link is no longer a value in the file -- it is the RESULT
   of joining two of them, and nothing else in this suite would notice if that
   join produced rubbish. `node --check` in CI cannot: a template with a typo in
   it is perfectly valid JavaScript. The block walker stops on the IIFE's closing
   brace, so the call that runs it is put back here; the body is the page's. */
function buildSites(conf, log) {
  const body = grabBlock('const SITES = (function () {', '{', '}') + ')();';
  return new Function('CONF', 'STAGE', 'console',
    body + '\n return SITES;')(conf, { people: conf.PEOPLE || [] }, log || console);
}

test('every configured link resolves to a real destination', () => {
  /* WHAT A TEMPLATE BUYS AND WHAT IT COSTS. It buys one home for `github.com`.
     It costs the property that a link was previously self-evident on the line
     it was written on: `{handle}` misspelt in SERVICES, or a `handle` left off a
     link, is now a badge pointing somewhere that does not exist, on a page that
     looks entirely correct. Both failures are shapes, so both can be asserted.

     Run over EVERY person, not the one on stage -- a combined stage draws them
     all and a solo host draws any one of them. */
  const conf = loadConfig();
  const sites = buildSites(conf);
  const bad = [];
  (conf.PEOPLE || []).forEach(p => {
    (p.links || []).forEach(l => {
      const s = (sites[p.slug] || {})[l.slug];
      /* Dropped, which the builder does loudly and on purpose -- but only ever
         for a config that is wrong, and this is the shipped one. */
      if (!s) return bad.push(`${p.slug}/${l.slug} resolves to no link at all`);
      if (!s.href) bad.push(`${p.slug}/${l.slug} has an empty href`);
      /* The band. An empty one is a wheel engraved with nothing. */
      if (!s.path) bad.push(`${p.slug}/${l.slug} engraves an empty band`);
      /* An unfilled placeholder is the typo, arriving intact in the output. */
      [['href', s.href], ['path', s.path]].forEach(([k, v]) => {
        if (/[{}]/.test(String(v))) {
          bad.push(`${p.slug}/${l.slug} ${k} still carries a placeholder: ${v} `
            + '— the template names something the link does not supply');
        }
      });
    });
  });
  ok(bad.length === 0, bad.join('\n      '));

  /* AND THE GUARD IS NOT VACUOUS. A link naming a service with no `url` and
     carrying no `href` of its own has no destination that could be derived, and
     must be left out of the table rather than handed an empty href -- an
     `<a href="">` reloads the page and reads as a working badge. It must also
     say so: the console is the only place this failure is ever reported. */
  const said = [];
  const broken = buildSites({
    SERVICES: { orphan: { label: 'Orphan' } },
    PEOPLE: [{ slug: 'nobody', links: [{ slug: 'orphan', handle: 'x' }] }]
  }, { error: (m) => said.push(m) });
  eq(Object.keys(broken.nobody).length, 0,
    'a link with no derivable destination was seated anyway');
  ok(said.length === 1 && /nobody\/orphan/.test(said[0]),
    'a link with no derivable destination was dropped silently');
});

test('no address reaches the published config but the one deliberately published', () => {
  /* config.js IS SERVED TO THE WEB. Whatever a wheel's band is engraved with,
     an address in this file is public in plain text -- a harvester reads the
     file, not the artwork. Harper's is deliberately withheld (GitHub #65): her
     wheel carries Charles's address as its handle and overrides the band to read
     `harper`, so the two halves disagree on purpose, and the obvious tidy-up is
     the one that would publish her.

     This is an ALLOWLIST of what may appear, not a search for one address. It
     names nothing that is being protected -- naming it here would be a second
     copy of the fact, in the repo, for the sake of guarding the first -- and it
     catches any NEW address arriving by any route, which is the real risk now
     that an address is a `handle` rather than a whole `mailto:`. */
  const PUBLISHED = ['charles@wozi.com'];
  const found = [...new Set(CFG_SRC.match(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g) || [])];
  const leaked = found.filter(a => PUBLISHED.indexOf(a) < 0);
  ok(leaked.length === 0,
    'config.js is published: ' + leaked.join(', ') + ' would be served in plain '
    + 'text. If that is intended, add it to PUBLISHED here deliberately.');
  ok(found.length > 0,
    'no address in config.js at all — the allowlist above is guarding nothing, so '
    + 'either the mail wheels are gone or this test has stopped seeing the file');
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
  const conf = loadConfig();
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
  const conf = loadConfig();
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

test('the person picker is retired, and nothing re-introduces it (GitHub #118, CL#144)', () => {
  /* THIS TEST ASSERTED THE OPPOSITE UNTIL CL#144. The old rule -- draw the
     picker only on the combined stage -- existed because a personal link must
     not advertise everyone else on the domain (#68). Charles retired the picker
     outright instead: the menu became a CONTROL surface, and a list of the
     household sat oddly beside a speed slider.

     The disclosure the old rule guarded is now impossible rather than
     conditional, which is a stronger guarantee: there is no list to leak. What
     is asserted instead is that it STAYS impossible, because the block is still
     there as an empty list and the easy regression is somebody repopulating it.

     THE COST IS REAL AND IS NOT THIS TEST'S TO JUDGE: per-person pages are now
     reachable only by subdomain or by ?who=<slug>, neither of which is
     discoverable. That was Charles's call, made with the cost in front of him. */
  /* STRIPPED_SRC, not SRC: the comment above the declaration explains what the
     picker WAS and quotes its old shape, so a check against raw source would
     match its own prose (the #101 trap). */
  const decl = /const togPeople\s*=\s*([^;]*);/.exec(STRIPPED_SRC);
  ok(decl, 'the togPeople declaration is gone entirely — this suite can no longer '
    + 'tell whether the picker came back');
  ok(/^\[\s*\]$/.test(decl[1].trim()),
    `togPeople is no longer an empty list — it is "${decl[1].trim().slice(0, 40)}". The `
    + 'person picker has been re-introduced, and with it the disclosure #68 was filed '
    + 'about: a personal page listing everyone else on the domain');

  /* The panel must still carry the speed control, which is the whole reason it
     survives the picker's removal -- it is the only route to that control once
     the corner stops showing it at 1x. */
  ok(/aria-label="Gear speed"/.test(SRC),
    'the speed slider is gone from the panel — retiring the picker has taken the '
    + 'menu\'s only remaining control with it');
  ok(/Machine Settings/.test(SRC),
    'the panel no longer names its settings group, so the slider sits under nothing');
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

     The counts the suite deals against come from RUNNING config.js. The check is
     that a SECOND, INDEPENDENT count -- walking the braces of the source text --
     agrees with them. Independent is the whole value: it shares no step with the
     first, so a stray brace, a mis-nested links array or an object that parses to
     something other than what it reads as shows up here rather than silently
     re-sizing every train the deal tests below measure.

     It counts STRUCTURE, never a key name. Counting `href:` per person is what
     this used to do, and #99 took that key off every ordinary link -- one line of
     config away from reporting a train of length 0. Objects nested one deep
     inside a person's own `links` array are links whatever they are made of. */
  const block = grabBlockFrom(CFG_SRC, 'config.js', 'PEOPLE:', '[', ']')
    .replace(/\/\*[\s\S]*?\*\//g, '');   /* a retired wheel is commented out, not deleted */
  /* Depth is walked rather than regexed because each person's `links` array holds
     objects of its own, and a non-greedy brace match would end at the first. */
  const objectsAtDepth = (s, want) => {
    const out = [];
    let depth = 0, start = -1;
    for (let k = 0; k < s.length; k++) {
      if (s[k] === '{') { if (depth === want) start = k; depth++; }
      else if (s[k] === '}') { depth--; if (depth === want) out.push(s.slice(start, k + 1)); }
    }
    return out;
  };
  const walked = objectsAtDepth(block, 0).map(person => {
    const links = grabBlockFrom(person, 'a person in config.js PEOPLE', 'links:', '[', ']');
    return objectsAtDepth(links, 0).length;
  });
  eq(page.TRAIN_LENS.length, walked.length,
    'the headcount from running config.js disagrees with the one from reading it');
  eq(page.TRAIN_LENS.join(','), walked.join(','),
    'a chain is a different length run than read — the per-person link counts disagree');
  eq(page.TRAIN_LENS.reduce((a, b) => a + b, 0), walked.reduce((a, b) => a + b, 0),
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
  const conf = loadConfig();
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
  const conf = loadConfig();
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
   the difference between measuring what ships and measuring a copy of it.

   Same locator as grabBlockFrom, for the same reason -- 47 of these anchors sit
   in the same file, and `const px = (want, lo, hi) =>` appearing a second time
   in a comment discussing it is the whole of GitHub #101. The `;` is found on
   the mask too: a semicolon in the prose between the anchor and the end of the
   line would otherwise truncate the declaration into something that still
   parses. */
function grabDecl(decl) {
  const i = locateAnchor(SRC, 'index.html', 'declaration', decl);
  const j = maskedOf(SRC).indexOf(';', i);
  if (j < 0) throw new Error('unterminated declaration: ' + decl);
  return noteAnchor('index.html decl', decl, SRC.slice(i, j + 1));
}

/* Executes the real TRAIN builder out of index.html rather than modelling it.
   Returns the bridges and the origin runs it filled in as well as the wheels:
   the three are built together, and a test that only saw the array could not
   tell an idler apart from the chain it feeds, nor a bridge idler from an origin
   idler. Every value the builder closes over is handed in from the page rather
   than re-typed -- MAX_IDLERS and ORIGIN_MOUNT are read out of index.html, and
   HAS_WHEELS, SIBLING_SORT, CHAIN_PARENT, CHAIN_TREE, CHAIN_ORDER, DRIVE_FROM,
   SPINE and SPINE_LEN are the page's OWN LINES, executed against the fixture, in
   the page's own declaration order. SPINE_LEN used to be re-derived here, which
   is the one thing this file forbids: a suite holding its own copy of a
   derivation passes happily while the page computes something else.

   THE FIXTURE GOES IN THROUGH THE PAGE'S OWN DECLARATIONS -- `child` and `order`
   per person (GitHub #116, CL#123) -- exactly as config.js does, and there is no
   way past them. There used to be: a `stack` argument substituted CHAIN_STACK
   outright, so a test could reach a layout order no config could ask for. The
   drive tree is what finally retired the need for one. Any head, any sequence
   behind it and any shape of tree are expressible as declarations, so the only
   orders an override still bought were the ILLEGAL ones -- a spine that is not at
   the head, or a headless chain with no wheels -- and a harness that can build a
   train the page cannot is a harness that can pass a test the page would fail.

   `conf` IS THE WHOLE OF config.js, NOT THE STAGE, and the two are different on
   purpose: CHAIN_PARENT tells a `child` naming somebody who is simply not on THIS
   stage (silent, legitimate on a solo page) from one naming a slug that is not a
   person anywhere (a typo, warned). A fixture that does not care passes neither
   and gets the stage back as the config, which is what a combined stage is. */
function buildTrain(people, conf, mount) {
  const expr = grabBlock('const TRAIN = (function', '(', ')');
  const bridges = [], origins = [], headOf = {};
  const built = new Function('STAGE', 'CONF', 'MAX_IDLERS', 'ORIGIN_MOUNT',
    'BRIDGES', 'ORIGINS', 'HEAD_OF', 'console',
    grabDecl('const HAS_WHEELS =') + '\n'
    + grabDecl('const STACK_AT =') + '\n'
    + grabDecl('const NAME_KEY =') + '\n'
    + grabDecl('const SIBLING_SORT =') + '\n'
    + grabBlock('const CHAIN_PARENT = (function', '(', ')') + '();\n'
    + grabBlock('const CHAIN_TREE = (function', '(', ')') + '();\n'
    + grabDecl('const CHAIN_ORDER =') + '\n'
    + grabDecl('const DRIVE_FROM =') + '\n'
    + grabDecl('const SPINE =') + '\n'
    + grabDecl('const SPINE_LEN =') + '\n'
    + 'return { train: ' + expr.replace(/^const TRAIN = /, '') + '(), '
    + 'order: CHAIN_ORDER, spine: SPINE, driveFrom: DRIVE_FROM, '
    + 'parent: CHAIN_PARENT };')(
    { people: people }, { PEOPLE: conf || people }, grabNumber('MAX_IDLERS'),
    mount || PAGE_ORIGIN_MOUNT, bridges, origins, headOf, spineConsole);
  return { train: built.train, bridges, origins, headOf, order: built.order,
    spine: built.spine, driveFrom: built.driveFrom, parent: built.parent,
    spineWarns: spineConsole.taken() };
}
/* CHAIN_PARENT announces a `child` it cannot honour rather than obeying it in
   silence, so the suite has to be able to READ that -- and must not print it over
   the test output on the fixtures that provoke it deliberately. */
const spineConsole = (function () {
  const said = [];
  return { warn: (m) => said.push(m), error: (m) => said.push(m),
    taken: () => said.splice(0, said.length) };
})();

/* FOUR CHAINS AND A REAL CASCADE (Charles, GitHub #116, CL#123), which is the
   shape two chains cannot show and three can only just: a spine with TWO
   dependents and an unrelated root standing behind the whole subtree.

   EVERY KEY IS SET AGAINST WHAT A SORT WOULD DO, so nothing here can pass by
   agreeing with the old rule:

     `far` is the LONGEST chain on stage and is still LAST, because it is a root
     and the walk finishes the spine's subtree first -- link count no longer
     orders the page, only siblings;
     `kid` and `cub` are declared in PEOPLE in the order cub-then-kid, and must
     come out kid-then-cub, because siblings sort by link count descending;
     so `cub` -- the SECOND sibling -- takes its drive off `kid`'s lead gear and
     not off `hub`, which is the cascade itself;
     and `hub` is a three-wheel axis with a seven-wheel chain elsewhere on stage,
     the #98 arrangement, so the default anchor index is exercised too. */
const CASCADE = [
  { slug: 'cub', child: 'hub', links: [{ slug: 'c1' }] },
  { slug: 'far', links: [1, 2, 3, 4, 5, 6, 7].map(n => ({ slug: 'f' + n })) },
  { slug: 'hub', order: 10, links: [{ slug: 'h1' }, { slug: 'h2' }, { slug: 'h3' }] },
  { slug: 'kid', child: 'hub', links: [{ slug: 'k1' }, { slug: 'k2' }] }
];

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
  ok(/SPINE_SLUG/.test(SRC.slice(i, i + 200)),
    'the extremities are not restricted to the spine, so every pair of leaves on '
    + 'a branched stage is pushed ENDS_APART');
});

test('every chain but the spine stands off through at least one idler', () => {
  /* Chains never mesh directly -- the idlers are what make the drive legible,
     and it is the same floor for both kinds of run (CL#123): a BRIDGE when
     another chain drives this one, an ORIGIN RUN when nothing does. */
  ok(/role:\s*'idler'/.test(SRC), 'no idler role is ever assigned');
  ok(/MIN_IDLERS/.test(SRC), 'there is no floor on the number of idlers in a bridge');
  const MIN = grabNumber('MIN_IDLERS');

  /* A DEPENDENT. `child: 'a'` is the declaration; the bridge is what it buys. */
  const driven = buildTrain([
    { slug: 'a', links: [{ slug: 'p' }, { slug: 'q' }, { slug: 'r' }] },
    { slug: 'b', child: 'a', links: [{ slug: 's' }] }
  ]);
  eq(driven.bridges.length, 1, 'the dependent chain got no bridge');
  eq(driven.origins.length, 0, 'a chain something else drives was given an origin '
    + 'run as well, so it is being driven twice');
  ok(driven.bridges[0].idlers.length >= MIN,
    `bridge carries ${driven.bridges[0].idlers.length} idlers, floor is ${MIN}`);
  /* Walk from the driven chain's first wheel back toward the spine: it must pass
     through idlers and never mesh a link of another chain directly. */
  let at = driven.train[driven.bridges[0].head].parent, hops = 0, seen = 0;
  while (at !== null && hops++ <= driven.train.length) {
    if (driven.train[at].role === 'idler') seen++;
    else break;
    at = driven.train[at].parent;
  }
  ok(seen >= MIN, `the driven chain meshes a linked wheel after ${seen} idlers`);
  ok(at !== null && driven.train[at].role === 'link' && driven.train[at].person === 'a',
    'the bridge does not land on the spine');

  /* AN INDEPENDENT CHAIN, which is the same claim about the other kind of run.
     It takes no bridge idlers -- nothing on stage drives it -- and gets a run of
     its own instead, so it is never a set of gears standing there undriven
     (Charles, GitHub #116). */
  const own = buildTrain([
    { slug: 'a', links: [{ slug: 'p' }, { slug: 'q' }, { slug: 'r' }] },
    { slug: 'b', links: [{ slug: 's' }] }
  ]);
  eq(own.origins.length, 1, 'an independent chain got no origin run, so nothing '
    + 'turns it -- which is the state GitHub #116 exists to remove');
  eq(own.origins[0].person, 'b', 'the origin run does not feed the chain it belongs to');
  ok(own.origins[0].idlers.length >= MIN,
    `an origin run carries ${own.origins[0].idlers.length} idlers, floor is ${MIN}`);
  eq(own.bridges.filter(b => b.idlers.length).length, 0,
    'an independent chain kept bridge idlers, so it is being driven by the chain '
    + 'it takes no drive from');
});

test('a parent always appears earlier in TRAIN than its children', () => {
  /* solve() derives a wheel from g[t.parent] out of the wheels it has ALREADY
     placed. A forward reference reads undefined and the branch lands wherever
     the last iteration happened to leave it -- silently, with no error. The
     spine is emitted first for exactly this reason, so the check has to run on
     a stage where the spine is NOT the first person in config order.

     ONE ROOT PER INDEPENDENT CHAIN, and no more (CL#123). It used to be exactly
     one on any stage, because every chain but the spine hung off the spine. A
     self-driven chain is a second tree by definition -- that is what
     independence IS -- so the count is a statement about the DECLARATIONS
     rather than a constant: every chain with no `child` is a root, every chain
     with one is not, and anything else means the tree was built from something
     other than the config. */
  [[[{ slug: 'short', links: [{ slug: 's' }] },
     { slug: 'long', links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] }], 'long'],
   [CASCADE, 'hub']
  ].forEach(([people, head]) => {
    const { train } = buildTrain(people);
    const bad = [];
    train.forEach((t, i) => {
      if (t.parent === null) return;
      if (t.parent >= i) bad.push(`wheel ${i} (${t.role}) names parent ${t.parent}, which is not placed yet`);
    });
    eq(train.filter(t => t.parent === null).length,
      people.filter(p => p.child == null && (p.links || []).length).length,
      'the number of roots in TRAIN is not the number of independent chains');
    eq(train[0].person, head, 'the spine is not emitted first');
    ok(bad.length === 0, bad.join('\n      '));
  });
});

test("the static tree's default bridge anchor is a spine wheel, whatever the layout order", () => {
  /* #98, found latent under #85. SPINE_LEN was
     `Math.max(1, ...people.map(p => p.links.length))` -- the longest chain
     ANYWHERE on stage -- and the TRAIN builder used it as a WHEEL INDEX INTO
     THE SPINE. Those two quantities agree only while the spine IS the longest
     chain, which the old CHAIN_ORDER sort guaranteed and neither a declared
     spine nor the drive tree that replaced it (CL#123) does. The guarantee lived
     in a different declaration from the index it was propping up, which is the
     whole defect.

     So the fixture MAKES the short chain the axis, by making the long one its
     dependent: a two-wheel spine with a seven-wheel chain hanging off it, the
     arrangement #85 made askable and one no sort by link count could ever
     produce. `child` is what asks for it now. Under the old derivation the
     default anchor is floor((7-1)/2) = 3 -- past the spine's last wheel at index
     1, landing on one of the bridged chain's OWN idlers, and a forward reference
     into the bargain. solve() overwrites this parent before anything is drawn,
     so no pixel ever moved; #65 was a malformed static tree all the same, and
     being unable to build one is worth having. */
  const people = [
    { slug: 'spine', links: [{ slug: 'a' }, { slug: 'b' }] },
    { slug: 'long', child: 'spine', links: [1, 2, 3, 4, 5, 6, 7].map(n => ({ slug: 'l' + n })) }
  ];
  const { train, bridges } = buildTrain(people);
  eq(train[0].person, 'spine', 'the chain nothing drives was not laid out first');
  const spineWheels = train.filter(t => t.role === 'link' && t.person === 'spine').length;

  /* The fixture is only evidence if it would have caught the old shape. This is
     the discarded derivation, written out ONCE, here, precisely because it is no
     longer in index.html to be read out of. */
  const wasIndex = Math.floor((Math.max(1, ...people.map(p => (p.links || []).length)) - 1) / 2);
  ok(wasIndex > spineWheels - 1,
    `fixture does not exercise the bug: the old max-over-stage index ${wasIndex} `
    + `still lands inside a spine of ${spineWheels} wheels`);

  const bad = [];
  bridges.forEach(b => {
    if (!b.idlers.length) return;
    const first = b.idlers[0], anchor = train[first].parent, t = train[anchor];
    if (!t || t.role !== 'link' || t.person !== 'spine') {
      bad.push(`${b.person}'s bridge defaults to wheel ${anchor}, which is `
        + (t ? (t.person ? `a link of ${t.person}` : 'a ghost idler') : 'past the end of TRAIN')
        + ` -- the spine is wheels 0..${spineWheels - 1}`);
    }
    if (!(anchor < first)) {
      bad.push(`${b.person}'s bridge defaults to wheel ${anchor}, which is not `
        + `placed when idler ${first} asks for it`);
    }
  });
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
     failure as #67.

     IT READS THE DECLARATION, NOT A WINDOW OF BYTES EITHER SIDE OF IT. This used
     to slice 600 characters after the first mention of BRIDGE_BEARING and look
     for _axisRot anywhere inside, which passes on any file where the two happen
     to be written near each other -- including, as it turned out, on a comment
     that grew long enough to push the code out of the window. The statement that
     has to be relative is `const bridgeBase =`, so that is what is read.

     THIS IS THE ANGLE HALF ONLY. Which way round the perpendicular runs is the
     other half, and it is asserted where it can actually be seen -- in screen
     coordinates, by "the spine is topmost in landscape and LEFTMOST in
     portrait". A source-shape test cannot tell a bearing from its mirror. */
  const i = SRC.indexOf('const bridgeBase =');
  ok(i > 0, 'solve() no longer names a bridgeBase');
  const decl = SRC.slice(i, SRC.indexOf(';', i) + 1);
  ok(/_axisRot/.test(decl),
    'the bridge bearing is not measured from _axisRot: ' + decl);
  ok(/BRIDGE_BEARING/.test(decl),
    'the bridge bearing is not expressed as BRIDGE_BEARING from the axis: ' + decl);
});

test('an independent chain keeps its position and takes its drive from itself', () => {
  /* No `child` says "nothing here drives me", not "put me nowhere": the chain
     stays a root, and solve() still has to place it clear of the others -- every
     root but the first resolved to (0,0) before that was fixed, which drew the
     second chain on top of the first.

     WHAT IT DOES NOT MEAN IS UNDRIVEN (Charles, GitHub #116, CL#123). `bridge:
     false` shipped that for one release as CL#122 and it is what this replaces:
     the chain is a root, keeps no BRIDGE idlers -- there is nothing on stage to
     hang them off -- and gets an ORIGIN RUN of its own instead, so it reads as
     its own machine running rather than as a set of gears nothing turns. */
  const { train, bridges, origins } = buildTrain([
    { slug: 'a', links: [{ slug: 'p' }, { slug: 'q' }, { slug: 'r' }] },
    { slug: 'b', links: [{ slug: 's' }] }
  ]);
  /* Every message in this file names the FAULT, not the invariant, and these two
     were the only pair with no word in them saying so -- "an independent chain
     claims idlers" and "an independent chain is not a root" read as flat
     statements about a healthy tree, and quoted out of a failing run they say the
     opposite of what is being claimed. Their neighbours carry "still" and "so
     nothing places it"; these carry it now too. */
  eq(bridges.length, 1, 'an independent chain is not registered, so nothing places it');
  eq(bridges[0].idlers.length, 0, 'an independent chain kept bridge idlers on its '
    + 'record, and there is no drive on stage to hang them off');
  eq(train.filter(t => t.role === 'idler' && t.drive === 'bridge').length, 0,
    'an independent chain still built bridge idlers');
  eq(origins.length, 1, 'an independent chain got no origin run, so it stands '
    + 'undriven -- the CL#122 shape this replaced');
  eq(train.filter(t => t.role === 'idler' && t.drive === 'origin').length,
    grabNumber('MAX_IDLERS'), 'the origin run was not dealt the same idlers a '
    + 'bridge is, so the two runs no longer take the same room across the stage');
  /* UNDER 'edge' the run hangs off the lead gear outward and the head stays a
     root; under 'fixed' the run runs inward from a mount and the head parents
     onto its last idler, which makes the MOUNT the root. Either way the chain
     is exactly one tree with exactly one root, and it is not the spine's. */
  const head = train[bridges[0].head];
  if (PAGE_ORIGIN_MOUNT === 'edge') {
    eq(head.parent, null, 'an independent chain was given a parent, so it is '
      + 'being driven by a chain it declares no relationship to');
    ok(origins[0].idlers.every(ix => train[ix].parent != null),
      'an edge-mounted origin idler is a root, so it has nothing to be placed off');
  } else {
    eq(train[origins[0].idlers[0]].parent, null,
      'a mounted origin run does not start at a station, so it has nothing to '
      + 'be placed off');
  }
  ok(/const free = /.test(SRC),
    'solve() has no branch for a root that is not the first wheel, so it would '
    + 'resolve to (0,0) on top of the spine');
});

/* ---- 0c. the speed control: a menu slider, and a corner departure indicator
   (GitHub #108, CL#114) --------------------------------------------------- */

/* This suite has no DOM and no React, so nothing here executes renderVals() or
   mounts the component -- everything below reads the SHIPPED markup and logic
   as text, exactly the way the deploy-whitelist and host-disjointness checks
   above do. A regex cannot mistake intent for behaviour, but it can catch
   exactly the failure this feature is prone to: the corner button's old
   `right` index left stale, the slider wired to a continuous value instead of
   SPEED_STOPS, or the strobe warning quietly dropped from one of the two
   controls that carry it now instead of one. */

test('the corner speed control cycles nothing any more — it resets to 1x', () => {
  ok(!/cycleSpeed/.test(SRC),
    'cycleSpeed still exists — the corner control is supposed to be a reset, '
    + 'not a ladder cycler, once the slider took over choosing a stop');
  ok(/resetSpeed\s*:\s*\(\)\s*=>/.test(SRC),
    'no resetSpeed render value found — the corner control has nothing left to do');
  ok(/onClick="\{\{ resetSpeed \}\}"/.test(SRC),
    'the corner button does not call resetSpeed — tapping it while off 1x has no way back');
});

test('the corner control shows nothing at 1x, and only at 1x', () => {
  /* The whole of "shows nothing at 1x" is one ternary on the button's own
     `display`; SPEED_FLOOR is the schema's own floor, not a hardcoded 1, so a
     schema change moves the hidden state with it rather than leaving a stale
     literal behind. */
  ok(/display:\s*speedNow === SPEED_FLOOR \? 'none' : 'flex'/.test(SRC),
    "the corner button's display is not gated on speedNow === SPEED_FLOOR — "
    + 'it would either always show or never show, instead of only away from 1x');
});

test('removing the permanent speed button closed the gap, not stranded it', () => {
  /* Speed used to sit at index 2 (between pause and the menu toggle). Once it
     stopped being permanent, the menu toggle has to close the gap down to
     index 2 itself — leaving it at index 3 would strand a hole in the middle
     of the row at 1x, which is the exact trap this test exists to catch. The
     departure indicator takes the outer slot the toggle gave up (index 3), so
     showing or hiding it only ever grows or shrinks the row from its open
     end, never reflows a permanent button. */
  ok(/onClick="\{\{ toggleTog \}\}"[^>]*right:calc\(var\(--offright\) \+ \(var\(--btn\) \+ var\(--btngap\)\) \* 2\)/.test(SRC),
    'the menu toggle is not at index 2 — removing the permanent speed button '
    + 'left a gap between pause and the menu toggle instead of closing it');
  ok(/right:\s*'calc\(var\(--offright\) \+ \(var\(--btn\) \+ var\(--btngap\)\) \* 3\)',/.test(SRC),
    "speedStyle's right is not index 3 — the departure indicator no longer sits "
    + 'in the outer slot the menu toggle vacated');
});

test('the slider steps over SPEED_STOPS by index, never continuously', () => {
  ok(/<input type="range" min="0" max="\{\{ speedMax \}\}" step="1" value="\{\{ speedPos \}\}"/.test(SRC),
    'the slider markup does not step min=0/step=1 over an index — a continuous '
    + 'range would spend most of its travel between the top two stops (CL#96)');
  ok(/speedMax:\s*speedSpan,/.test(SRC),
    'speedMax is not derived from speedSpan (SPEED_STOPS.length - 1) — a '
    + 'hardcoded bound would drift the day the ladder is widened or narrowed');
  ok(/const speedSpan = SPEED_STOPS\.length - 1;/.test(SRC),
    'speedSpan is not derived from SPEED_STOPS.length — never hand-write a stop list');
});

test('the slider sits at the top of the menu, above the picker and the links', () => {
  const navAt = SRC.indexOf('aria-label="Table of gears"');
  ok(navAt >= 0, 'the pop-out menu <nav> is missing entirely');
  const sliderAt = SRC.indexOf('<input type="range"', navAt);
  const peopleAt = SRC.indexOf('{{ togPeople }}', navAt);
  const gearsAt = SRC.indexOf('{{ togList }}', navAt);
  ok(sliderAt > navAt, 'no <input type="range"> found inside the pop-out menu at all');
  ok(sliderAt < peopleAt, 'the slider is not above the person picker in source order '
    + '(source order is render order for a plain list of siblings here)');
  ok(sliderAt < gearsAt, 'the slider is not above the gear-family links in source order');
});

test('the slider is reachable on a solo host, where the picker is deliberately absent', () => {
  /* togPeople is emptied by `people.length > 1 && STAGE.mode === 'all'` — true
     only on a combined stage. The slider row must not share that gate, or a
     solo host (?who=<slug>) would lose its only route to the speed control
     the moment the corner stops showing it. Checked as: nothing between the
     <nav> tag itself and the <input type="range"> mentions sc-if, sc-for or
     togPeople — the only ways a chunk of this template can become
     conditional or repeated. */
  const navAt = SRC.indexOf('aria-label="Table of gears"');
  const sliderAt = SRC.indexOf('<input type="range"', navAt);
  ok(navAt >= 0 && sliderAt > navAt, 'the pop-out menu <nav> or its slider is missing');
  /* Strip HTML comments before checking — the markup between the tags is
     documented in prose that names togPeople on purpose, and that prose is
     not a template directive. */
  const between = SRC.slice(navAt, sliderAt).replace(/<!--[\s\S]*?-->/g, '');
  ok(!/sc-if|sc-for|togPeople/.test(between),
    'something between the <nav> tag and the slider gates or repeats it — the '
    + 'slider must render unconditionally, the same way it does on the combined stage');
});

test('the strobe warning is carried by both controls that can show a value', () => {
  /* CL#96's invariant — every stop at or above strobeSpeed() says so in its
     accessible name — used to bind one control. There are two now, and both
     have to keep it: the slider's aria-valuetext (every value change) and the
     corner's aria-label (the one value it ever shows). */
  ok(/speedValueText:\s*speedNow \+ '×' \+ \(speedStrobes \? ', strobing — benchmark only' : ''\)/.test(SRC),
    "speedValueText does not carry the strobing note — the slider's "
    + 'aria-valuetext would go silent about the illusion breaking');
  ok(/speedLabel:\s*'Gear speed ' \+ speedNow \+ '×'\s*\n\s*\+ \(speedStrobes \? ', strobing — benchmark only' : ''\)/.test(SRC),
    "speedLabel does not carry the strobing note — the corner control's "
    + 'accessible name would go silent about the illusion breaking');
  ok(/tap to reset to 1×/.test(SRC),
    'the corner control\'s accessible name does not say what tapping it does');
});

test('the thumb colour is state-driven through a CSS custom property, not a static rule', () => {
  /* The redline-on-the-track approach (GitHub #69's A/B sheets) failed
     exactly at the boundary stop, because a static track marker sits under a
     thumb that is centred on the very index it would mark. Colouring the
     thumb itself has to be driven by JS-computed state, not a fixed CSS rule
     — this asserts the mechanism, not just its absence. */
  const thumbRules = SRC.match(/::-webkit-slider-thumb\{[^}]*\}/g) || [];
  ok(thumbRules.length > 0, 'no ::-webkit-slider-thumb rule found at all');
  ok(thumbRules.every(r => /var\(--thumb-color,\s*var\(--muted\)\)/.test(r)),
    'the thumb pseudo-element does not read --thumb-color — its colour would '
    + 'be fixed regardless of whether the current stop strobes');
  ok(/'--thumb-color':\s*fill,/.test(SRC),
    '--thumb-color is never set inline from render state — the pseudo-element '
    + 'rule above has nothing state-driven to read');
});

test('every range input on the page carries its own --thumb-color', () => {
  /* Was "there is exactly one range input" -- true until GitHub #112 added a
     second (Wear, beside Speed in the same settings group). The bare
     input[type="range"] selector is still safe with two, but for a different
     reason than "there's only one": --thumb-color is a custom property set
     INLINE on each element, so the shared ::-webkit-slider-thumb/
     ::-moz-range-thumb rule reads a different value per control rather than
     styling both identically by accident. This asserts THAT is still true --
     a third range input with no --thumb-color of its own would silently fall
     back to var(--muted) and read as broken rather than as a decision. */
  const count = (SRC.match(/<input type="range"/g) || []).length;
  eq(count, 2, 'expected exactly two range inputs (Speed, Wear) — a new one '
    + 'changes what this test and the CSS comment above input[type="range"] '
    + 'both need to say');
  const inputs = SRC.match(/<input type="range"[^>]*>/g) || [];
  inputs.forEach(tag => {
    const m = tag.match(/style="\{\{\s*(\w+)\s*\}\}"/);
    ok(m, 'a range input has no style binding to check for --thumb-color: ' + tag);
    const styleName = m[1];
    const re = new RegExp(styleName + ':\\s*\\([\\s\\S]*?\\}\\)\\(\\)');
    const block = SRC.match(re);
    ok(block && /--thumb-color/.test(block[0]),
      styleName + ' does not set --thumb-color — it will silently share var(--muted) '
      + 'with every other range input on the page');
  });
});

/* ---- 0d. the flywheel's approach to a new target speed (GitHub #106, CL#127)
   ---------------------------------------------------------------------------

   approachSpeed() is extracted and RUN, not read as text, because the property
   this ticket exists to guarantee — a bigger drop settles more slowly than a
   smaller one — is a claim about behaviour over many ticks, not about the
   shape of the source. A regex can confirm the old `Math.exp(-dt / 900)` is
   gone; only running the replacement against synthetic v/target/dt can confirm
   it actually fixes #106 rather than merely renaming the bug. */

/* The schema's own min/max, read out of the SAME data-props JSON PROP_SCHEMA
   parses at runtime — not retyped, so a ladder change (the top stop moving off
   200, say) moves these with it. This suite has no DOM to run PROP_SCHEMA's own
   parse through, so the one JSON.parse happens here instead, against the exact
   attribute string the page carries. */
function speedSchema() {
  const m = SRC.match(/data-props="([^"]*)"/);
  ok(m, 'no data-props attribute found — the prop schema this suite reads is gone');
  const json = m[1].replace(/&quot;/g, '"').replace(/&amp;/g, '&');
  const schema = JSON.parse(json);
  ok(schema.speed && typeof schema.speed.min === 'number' && typeof schema.speed.max === 'number',
    'the prop schema has no speed.min/speed.max — SPEED_FLOOR/SPEED_CEIL would '
    + 'fall back to defaults the page is not actually shipping');
  return { floor: schema.speed.min, ceil: schema.speed.max };
}

/* Grabs the two constants and the function as one contiguous chunk — they are
   written next to each other for exactly this reason (see the block comment
   above them in index.html) — and executes it with the page's own BASE_MS and
   speed schema, never a copy of either. */
function loadApproachSpeed() {
  const { floor, ceil } = speedSchema();
  const baseMs = grabNumber('BASE_MS');
  const start = SRC.indexOf('const SPINDOWN_RANGE_MS');
  ok(start > 0, 'no SPINDOWN_RANGE_MS found — the flywheel\'s settle-time '
    + 'constant (CL#127) has been renamed or removed without updating this suite');
  const fnBlock = grabBlock('function approachSpeed(', '{', '}');
  const end = SRC.indexOf(fnBlock, start) + fnBlock.length;
  ok(end > start, 'function approachSpeed(...) not found after SPINDOWN_RANGE_MS');
  const chunk = SRC.slice(start, end);
  return new Function('BASE_MS', 'SPEED_CEIL', 'SPEED_FLOOR',
    chunk + '\nreturn approachSpeed;')(baseMs, ceil, floor);
}

/* Ticks approachSpeed() from v0 toward target at a fixed dt, exactly the way
   step() does (dt is clamped to 60 there too), and returns how many ticks it
   took to REACH target — not merely get close to it. approachSpeed() is
   expected to arrive exactly, in finite time (CL#127's whole point, versus an
   exponential that only ever approaches); a runaway loop here means that
   stopped being true. */
function ticksToSettle(approachSpeed, v0, target, dt) {
  let v = v0;
  for (let i = 1; i <= 100000; i++) {
    v = approachSpeed(v, target, dt);
    if (v === target) return i;
  }
  throw new Error('approachSpeed() did not reach target ' + target + ' from ' + v0
    + ' within 100000 ticks — it no longer arrives in finite time');
}

test('approachSpeed() replaces the fixed 900ms lag — GitHub #106', () => {
  /* STRIPPED_SRC, not SRC -- the old formula is quoted verbatim in the block
     comment documenting why it changed, and a check against the raw source
     would fail on its own prose (the exact trap STRIPPED_SRC exists for,
     GitHub #101). */
  ok(!/Math\.exp\(-dt \/ 900\)/.test(STRIPPED_SRC),
    'the old fixed-tau easing (Math.exp(-dt / 900)) is still LIVE CODE — #106 is unfixed');
  /* One flywheel PER MESH since CL#142 (GitHub #122), so the call site is
     indexed by component. Still asserted as an exact shape rather than loosely,
     because the point of the check is that step() is where the flywheel moves --
     but the shape it is asserted against had to follow the code. */
  ok(/this\._v\[c\] = approachSpeed\(this\._v\[c\] \|\| 0, target, dt\)/.test(SRC),
    'step() does not call approachSpeed() — the flywheel update has moved '
    + 'somewhere this suite is not looking, or was reverted');
  ok(/function approachSpeed\(v, target, dt\)/.test(SRC),
    'approachSpeed(v, target, dt) not found with that exact signature');
});

test('a bigger drop settles more slowly than a smaller one (GitHub #106\'s core complaint)', () => {
  /* This is the property the shipped exponential got backwards: settling time
     was independent of the size of the jump, so 200x -> 1x and 2x -> 1x took
     the same ~4.5s. Big vs small, from the ladder's own floor and ceiling
     rather than hand-picked numbers, so a ladder change keeps this test
     honest about what "bigger" and "smaller" mean. */
  const approachSpeed = loadApproachSpeed();
  const { floor, ceil } = speedSchema();
  const idleRate = (x) => (7200 / grabNumber('BASE_MS')) * x;
  const dt = 1000 / 30;
  const bigDrop = ticksToSettle(approachSpeed, idleRate(ceil), idleRate(floor), dt);
  const smallDrop = ticksToSettle(approachSpeed, idleRate(2 * floor), idleRate(floor), dt);
  ok(bigDrop > smallDrop,
    `the ${ceil}x -> ${floor}x drop settled in ${bigDrop} ticks, no slower than the `
    + `${2 * floor}x -> ${floor}x drop's ${smallDrop} — a bigger drop must take longer, `
    + 'not the same or less');
});

test('the flywheel COASTS — drag falls as it slows, and it still arrives (GitHub #121, CL#139)', () => {
  /* THIS TEST ASSERTED THE OPPOSITE UNTIL CL#139, and the reversal is the
     point of the ticket rather than a relaxation of it.

     CL#127 replaced a fixed-tau exponential with a CONSTANT deceleration and
     this test pinned that shape. Charles, on the result once CL#136 let a throw
     show the whole of it: "the spindown speed is just weird now - almost as if
     there is a break on the wheel". He was right, and it is a statement about
     the model: a constant retarding torque IS a brake. Nothing coasts at one
     flat rate and then stops decelerating at a corner.

     What replaces it is the standard three-term coast-down model an engineer
     fits to a real rotor — Coulomb + viscous + windage — so the rate RISES with
     how far the wheel is from the speed it is driven at.

     The two failure modes sit at either end of SPINDOWN_DRAG_RANGE and this
     test guards both, because they are opposite mistakes:
       - range -> 1 collapses the terms to a constant. That is the brake again.
       - range -> infinity kills the Coulomb residue and leaves a pure
         exponential, which is #106: it never arrives, and settling time stops
         depending on the size of the drop.
     So: the rate must genuinely shrink toward the target (not a brake), AND
     arrival must stay finite (not an exponential). Neither alone is enough. */
  const approachSpeed = loadApproachSpeed();
  const { floor, ceil } = speedSchema();
  const idleRate = (x) => (7200 / grabNumber('BASE_MS')) * x;
  const dt = 1000 / 30;
  let v = idleRate(ceil);
  const target = idleRate(floor);
  const deltas = [];
  /* The tick budget is DERIVED from the coast the page actually ships, not a
     round number: CL#141 took SPINDOWN_RANGE_MS to 15000, and a fixed 400 ticks
     at 30Hz is only 13.3s -- the loop ran out before the flywheel arrived and
     the test reported a lost Coulomb term, which was a statement about the
     budget rather than about the model. Doubled for headroom. */
  const budget = Math.ceil(grabNumber('SPINDOWN_RANGE_MS') / dt) * 2;
  for (let i = 0; i < budget && v !== target; i++) {
    const before = v;
    v = approachSpeed(v, target, dt);
    deltas.push(before - v);
  }
  ok(deltas.length > 10, 'fewer than 10 ticks before settling — not enough of a '
    + 'descent window to say anything about the shape of the approach');

  /* Clear of the first tick and of the final snap-to-target, either of which
     can legitimately be a partial step. */
  const mid = deltas.slice(2, -2);
  const early = mid[0], late = mid[mid.length - 1];

  ok(late < early,
    `the per-tick step is ${late} late against ${early} early — the retarding rate `
    + 'does not fall as the wheel slows, which is a constant-rate BRAKE, the exact '
    + 'thing GitHub #121 was raised about');

  /* Not merely smaller — smaller by enough to read as coasting. The shipped
     dynamic range is 15, and sampling misses both ends, so this asks for a
     modest fraction of it rather than the figure itself: a token taper would
     satisfy `late < early` while still looking like a brake. */
  ok(early / late > 3,
    `the rate only falls ${(early / late).toFixed(2)}x across the descent — too flat `
    + 'to read as a coast; SPINDOWN_DRAG_RANGE has collapsed toward 1');

  /* And the other end: it must still ARRIVE. A pure exponential would run the
     loop above to its cap without ever hitting target. */
  ok(v === target,
    'the flywheel never reached its target — the Coulomb term has been lost and '
    + 'this is a pure exponential again, which is GitHub #106');
});

test('the flywheel actually ARRIVES at its target, in finite time (GitHub #106, CL#127)', () => {
  /* An exponential asymptote never truly arrives — the shipped control (CL#127's
     candidate A) leaves a residual forever. Requiring exact arrival is what
     rules a reversion to that shape out, rather than merely a slower one. */
  const approachSpeed = loadApproachSpeed();
  const { floor, ceil } = speedSchema();
  const idleRate = (x) => (7200 / grabNumber('BASE_MS')) * x;
  const dt = 1000 / 30;
  const ticks = ticksToSettle(approachSpeed, idleRate(ceil), idleRate(floor), dt);
  ok(ticks < 100000, 'did not settle within the tick budget');
  // ticksToSettle() itself only returns on v === target; reaching here at all
  // is the assertion. A second call confirms it STAYS there rather than
  // overshooting and oscillating back out.
  const held = approachSpeed(idleRate(floor), idleRate(floor), dt);
  eq(held, idleRate(floor), 'approachSpeed() moved v away from a target it had already reached');
});

/* driveCap() is a class method, not a constant, so it is extracted with rateAt()
   -- the one home for the 1x rate that both it and idleRate() are built on --
   and both are run against the page's own BASE_MS and speed schema. Read as
   text this would only confirm a shape; the properties below are arithmetic. */
function loadDriveCap() {
  const { floor, ceil } = speedSchema();
  const baseMs = grabNumber('BASE_MS');
  const rateAt = grabBlock('rateAt(mult) {', '{', '}');
  const driveCap = grabBlock('driveCap() {', '{', '}');
  const host = new Function('BASE_MS', 'SPEED_CEIL', 'SPEED_FLOOR', 'speedFactor',
    'const o = { ' + rateAt + ', ' + driveCap
    + ', idleRate() { return this.rateAt(speedFactor); } }; return o;');
  return (factor) => host(baseMs, ceil, floor, factor);
}

test('how long a throw can coast is the ladder\'s own crossing time (GitHub #121, CL#136)', () => {
  /* THE REGRESSION, stated as the arithmetic that caused it. Once CL#127 made
     the flywheel decelerate at a CONSTANT rate, the time a thrown wheel coasts
     stopped being a property of the easing and became purely
     (driveCap() - idleRate()) / SPINDOWN_DECEL. driveCap() was `max(8,
     idleRate())`, so at 1x it was 8 -- and 8 -> 0.343 at the shipped
     deceleration is 269ms. No throw, however hard, could outlast a quarter
     second, which is #121: the train read as refusing to coast.

     Deriving the cap from the ladder's top instead makes this exact rather than
     merely bigger: a saturating throw sheds idleRate(ceil) - idleRate(floor) at
     a rate defined as that same span over SPINDOWN_RANGE_MS, so it takes
     SPINDOWN_RANGE_MS precisely. Asserted as an identity, not a threshold,
     because a threshold would need a number nobody derived -- and the identity
     is what makes the hardest possible throw and the full slider sweep the same
     journey, one by hand and one by control. */
  const approachSpeed = loadApproachSpeed();
  const capFor = loadDriveCap();
  const { floor, ceil } = speedSchema();
  const rangeMs = grabNumber('SPINDOWN_RANGE_MS');
  const at1x = capFor(floor);

  /* A tick fine enough that quantisation is a rounding error rather than the
     measurement -- the identity is about the continuous rate, and step()'s real
     dt is not this suite's to choose. */
  const dt = 0.5;
  const ticks = ticksToSettle(approachSpeed, at1x.driveCap(), at1x.idleRate(), dt);
  const coastMs = ticks * dt;
  /* Tolerance scales with the quantity being measured. `dt * 2` is 1ms, which is
     0.04% of a 2400ms coast and a reasonable bound there, but the same absolute
     figure against CL#141's 15000ms asks the tick-quantised sum to land within
     0.007% -- tighter than the integration itself, and it failed by 1.5ms on a
     model that had not changed. 0.1% or two ticks, whichever is larger. */
  ok(Math.abs(coastMs - rangeMs) <= Math.max(dt * 2, rangeMs * 0.001),
    `a saturating throw at ${floor}x coasts ${coastMs.toFixed(1)}ms, but the ladder's own `
    + `crossing time is ${rangeMs}ms — driveCap() and SPINDOWN_DECEL are no longer `
    + 'derived from the same span, so the hardest throw and a full slider sweep have '
    + 'drifted apart');

  /* And it must still be a CEILING at every stop, which is what `max(8, ...)`
     was protecting when the cap was a fixed number: a cap below the idle rate
     would clamp the train DOWN and act as a brake (the failure the old comment
     called out at 200x). Being the largest idleRate() the schema permits, it
     clears every stop by construction -- this checks the construction. */
  SPEED_STOPS_FOR_TEST().forEach(stop => {
    const o = capFor(stop);
    ok(o.driveCap() >= o.idleRate() - 1e-9,
      `at ${stop}x the drive cap (${o.driveCap()}) is below the idle rate `
      + `(${o.idleRate()}) — the cap has become a brake, not a ceiling`);
  });

  /* The historic 8 is gone from live code. Quoted in the comment that explains
     why, so STRIPPED_SRC and not SRC -- the #101 trap. */
  ok(!/Math\.max\(8,\s*Math\.abs\(this\.idleRate\(\)\)\)/.test(STRIPPED_SRC),
    'driveCap() still returns max(8, idleRate()) as live code — #121 is unfixed');
});

/* The ladder the shipped page builds, rebuilt here from the schema's own bounds
   by the same 1-2-5 rule index.html uses, so the stops this suite checks the cap
   against are the stops the control actually offers. */
function SPEED_STOPS_FOR_TEST() {
  const { floor, ceil } = speedSchema();
  const out = [];
  for (let decade = 1; decade <= ceil; decade *= 10) {
    for (const rung of [1, 2, 5]) {
      const v = decade * rung;
      if (v >= floor && v <= ceil) out.push(v);
    }
  }
  return out.length ? out : [floor];
}

test('spin-up and spin-down share the same approach — GitHub #106 asks explicitly', () => {
  /* Charles: a real train winds up slowly and coasts down slowly. approachSpeed()
     takes no direction argument at all — target > v (spin-up) and target < v
     (spin-down) go through the identical formula — so this checks the actual
     behavioural symmetry that no-special-case implies: converging from A to B
     takes exactly as many ticks as converging from B to A. */
  const approachSpeed = loadApproachSpeed();
  const { floor, ceil } = speedSchema();
  const idleRate = (x) => (7200 / grabNumber('BASE_MS')) * x;
  const dt = 1000 / 30;
  const spinDown = ticksToSettle(approachSpeed, idleRate(ceil), idleRate(floor), dt);
  const spinUp = ticksToSettle(approachSpeed, idleRate(floor), idleRate(ceil), dt);
  eq(spinDown, spinUp,
    'spin-up and spin-down settle in different tick counts — approachSpeed() is '
    + 'branching on direction somewhere, which #106 says it should not');
});

test('the settle-rate constant is DERIVED from the speed ladder and BASE_MS, not a bare deg/ms² literal', () => {
  /* CLAUDE.md: no drifting constants. The one tunable figure this candidate
     exposes is a wall-clock DURATION (named and commented in index.html as a
     placeholder for Charles's call); the actual master-degrees-per-ms-squared
     rate has to come from that duration divided by the ladder's own span, or a
     ladder change (moving the top stop off 200x) would silently desync the feel
     from the number that is supposed to define it. */
  const chunk = SRC.slice(SRC.indexOf('const SPINDOWN_RANGE_MS'),
    SRC.indexOf('function approachSpeed('));
  ok(/SPEED_CEIL/.test(chunk) && /SPEED_FLOOR/.test(chunk) && /BASE_MS/.test(chunk),
    'the settle-rate constant does not reference SPEED_CEIL, SPEED_FLOOR and '
    + 'BASE_MS — it may have been hand-tuned as a bare number instead of derived');
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
  const { train, bridges, origins, headOf, order, spine, driveFrom, parent } =
    buildTrain(people, opts.conf, opts.mount);
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

  /* The three index lookups solve() asks per wheel per pass -- two into BRIDGES
     and one into ORIGINS -- executed out of index.html rather than rebuilt, for
     the same reason everything else here is: a harness that keeps its own copy of
     "which run does this wheel belong to" can agree with itself while the page
     disagrees with both. */
  /* BOTH ANCHORS RUN ONTO THEIR SECOND LINE, and have to (GitHub #137): solve()
     walks BRIDGES and ORIGINS itself, so `BRIDGES.forEach(b => {` occurs twice
     in the page and `ORIGINS.forEach(o => {` three times. The old extractor took
     the first `indexOf` and happened to be right only because these load-time
     lookups are written above solve(); it would have started measuring the
     solver's parking loop the day anything moved. Indentation inside an anchor
     is ignored, so the continuation costs nothing but the disambiguation. */
  const lookups = grabDecl('const BRIDGE_FROM =') + '\n'
    + grabBlockFrom(SRC, 'index.html', 'BRIDGES.forEach(b => {\nBRIDGE_FROM[', '{', '}') + ');\n'
    + grabDecl('const ORIGIN_OF =') + '\n'
    + grabBlockFrom(SRC, 'index.html', 'ORIGINS.forEach(o => {\no.idlers.forEach(ix => {', '{', '}') + ');';
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
  const solve = new Function('TRAIN', 'BRIDGES', 'ORIGINS', 'ORIGIN_MOUNT',
    'HEAD_OF', 'DRIVE_FROM', 'CHAIN_ORDER', 'MODULE', 'TOOTH_ADD',
    'TEETH_MEAN', 'MIN_IDLERS', 'MAX_IDLERS', 'CLEARANCE', 'ENDS_APART',
    'ANG_MIN', 'ANG_MAX', 'CHAIN_RANK', 'SPINE_SLUG', 'PAIR_SLOTS', 'PAIRS', 'SINGLES',
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
  const solved = solve(train, bridges, origins, opts.mount || PAGE_ORIGIN_MOUNT,
    headOf, driveFrom, order, MODULE, page.TOOTH_ADD, TEETH_MEAN,
    grabNumber('MIN_IDLERS'), grabNumber('MAX_IDLERS'), grabNumber('CLEARANCE'),
    grabNumber('ENDS_APART'), page.ANG_MIN, page.ANG_MAX, CHAIN_RANK,
    spine ? spine.slug : '', [], [], [], sites,
    { warn: (m) => warns.push(m), error: (m) => warns.push(m) }).call(ctx);
  return { solved, train, bridges, origins, headOf, warns, ctx, order, spine,
    driveFrom, parent };
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

/* Three INDEPENDENT chains -- no `child` anywhere, so all three are roots -- whose
   PEOPLE order is deliberately NOT their length order, so a layout that follows
   config order sorts differently from one that follows chain length. Two of them
   are therefore self-driven, each with an origin run of its own (CL#123), which
   is what makes this the fixture for everything about ROOTS: the sibling
   fallback, the stacking, and the shape a chain nothing on stage drives arrives
   in. Anything about a bridge wants CASCADE, declared up with the TRAIN builder
   because the builder's own tests need it too. */
const THREE = [
  { slug: 'mid', links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] },
  { slug: 'tiny', links: [{ slug: 'd' }] },
  { slug: 'spine', links: [1, 2, 3, 4, 5, 6, 7].map(n => ({ slug: 's' + n })) }
];

/* THE SAME THREE CHAINS, STACKED BY DECLARATION rather than by length: the axis
   is the MIDDLE chain, and the stack behind it runs shortest to longest. PEOPLE
   order is a third sequence again, so nothing here can pass by accident of the
   file.

   THIS ARRANGEMENT WAS UNREACHABLE under the single sort. Longest-first answered
   both questions at once -- which chain is the axis, and what order the rest sit
   in -- so no config could ask for a short spine or for a stack that is not
   length order. That is what #85's split bought, and CL#123 keeps every bit of it
   with ONE key instead of two: these are all roots, `order` ranks the roots, and
   THE SPINE IS THE FIRST ROOT. `spine: true` is gone because it could only ever
   have agreed with that.

   MID IS A THREE-WHEEL SPINE ON PURPOSE (Charles, 2026-08-05 / GitHub #104): it
   used to be four, specifically so this fixture would not exercise the ENDS_APART
   defect a three-wheel spine cannot pay -- #85's own composition test would have
   inherited a console.warn nobody wrote it to expect, and a well-formedness
   assertion that treats a coin-flip warning as sometimes-fine is not an
   assertion. Now that a three-wheel spine is fixed (CL#111), this is the more
   honest fixture: the general "a declared stack composes cleanly" test and the
   specific "three-wheel spine pays ENDS_APART" regression are the same shape of
   claim, so one fixture proves both rather than the second needing a twin of the
   first. */
const DECLARED = [
  { slug: 'mid', order: 10, links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] },
  { slug: 'tiny', order: 20, links: [{ slug: 'd' }] },
  { slug: 'big', order: 30, links: [1, 2, 3, 4, 5, 6, 7].map(n => ({ slug: 's' + n })) }
];


/* Each chain's mean position along the CROSS AXIS, in the increasing screen
   direction: down at _axisRot 0, right at 90. Idlers are excluded -- they span
   two rows and belong to neither.

   IT IS DELIBERATELY NOT THE BRIDGE DIRECTION. This measured `rot + 90`, which
   is the bearing solve() used to take, so it agreed with the code by
   construction and would have gone on agreeing with it whichever way round the
   bridges ran. A test that reads the implementation's own heading can see the
   chains arrive in order and still not see them arrive on the WRONG SIDE, which
   is exactly what happened: at rot 90 the stack ran leftward off a rightmost
   spine, the assertion passed, and the only thing that could tell was a
   photograph. (sin rot, cos rot) is the rule in screen terms instead -- the
   cross axis pointing away from the origin corner -- so it stays true if the
   bearing is ever taken the other way round again, and fails if it is. */
function alongCross(solved, rot) {
  const dir = (90 - rot) * Math.PI / 180;
  const at = {};
  solved.gears.forEach(w => {
    if (w.person == null) return;
    (at[w.person] = at[w.person] || []).push(w.x * Math.cos(dir) + w.y * Math.sin(dir));
  });
  const mean = {};
  Object.keys(at).forEach(p => {
    mean[p] = at[p].reduce((a, b) => a + b, 0) / at[p].length;
  });
  return mean;
}

test('chains stack in the order CHAIN_ORDER declares, across the cross axis', () => {
  /* Charles, 2026-08-02: "lay them out in order ... top to bottom in landscape,
     and the equivalent along the cross axis in portrait". PEOPLE order is
     arbitrary the moment there are three chains, and until this rule the second
     and third both hung off the spine and arrived in the SAME row, ordered by
     nothing.

     WHAT THE ORDER IS was link count until #85 and is now DECLARED -- so the
     assertion is no longer "longest first", which would forbid the very thing
     the keys exist to express. It is the stronger statement underneath it: the
     chains arrive along the cross axis in CHAIN_ORDER, whatever CHAIN_ORDER
     says, and the same run proves the two ways of arriving at one. THREE
     declares nothing and must still come out by link count, because that is what
     the fallback still leads with; DECLARED asks for an order no fallback could
     produce and must get it. Delete either half and the test stops having teeth:
     the first alone cannot see a declaration being ignored, the second alone
     cannot see the default having drifted. */
  const bad = [];
  [[THREE, 'spine,mid,tiny', 'the default stack no longer leads with link count'],
   [DECLARED, 'mid,tiny,big', 'the declared spine and order were not honoured']
  ].forEach(([people, want, why]) => {
    [0, 90].forEach(rot => {
      const { solved, order } = runSolve(people, { axisRot: rot });
      eq(order.map(p => p.slug).join(','), want, why);
      const mean = alongCross(solved, rot);
      let last = -Infinity, lastSlug = 'the top edge';
      order.forEach(p => {
        const v = mean[p.slug];
        if (!(v > last)) {
          bad.push(`at axisRot ${rot}: ${p.slug} (${(p.links || []).length} wheels) `
            + `sits at ${v.toFixed(0)} along the cross axis, not past ${lastSlug} `
            + `at ${last.toFixed(0)}`);
        }
        last = v; lastSlug = p.slug;
      });
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the spine is topmost in landscape and LEFTMOST in portrait', () => {
  /* Charles, 2026-08-05: "why is the longest chain not the leftmost chain in
     portrait, when in landscape it is at the top?" It was not: the spine came out
     RIGHTMOST and the stack ran leftward from it, which a screenshot showed and
     nothing in tools/ could.

     THE BEARING WAS THE #67 FAILURE HALF-FIXED. BRIDGE_BEARING is relative to
     _axisRot, so the bridge stayed perpendicular to the spine when the stage
     turned -- that much was already right. But WHICH WAY ROUND it went was still
     a fixed +90: "down" at rot 0, and the identical +90 is "left" at rot 90. The
     rotation was honoured and the handedness was not, and the mirror image is
     equally legal geometry, so nothing local could object.

     SO THE ASSERTION IS IN SCREEN COORDINATES, deliberately -- x and y as the
     viewer sees them, not a heading the code also computes. Every other test
     here measures along the bridge direction, which is what let this stand: any
     test that asks "are they in order along the way the bridges point" gets yes
     from both mirror images. Only naming the edge can tell them apart. */
  const bad = [];
  [['THREE', THREE], ['DECLARED', DECLARED]].forEach(([label, people]) => {
    [[0, 'y', 'topmost', 'landscape'], [90, 'x', 'leftmost', 'portrait']]
      .forEach(([rot, axis, end, view]) => {
        const { solved, order } = runSolve(people, { axisRot: rot });
        const at = {};
        solved.gears.forEach(w => {
          if (w.person == null) return;
          (at[w.person] = at[w.person] || []).push(w[axis]);
        });
        const mean = (s) => at[s].reduce((a, b) => a + b, 0) / at[s].length;
        const spine = order[0].slug;
        order.slice(1).forEach(p => {
          if (!(mean(spine) < mean(p.slug))) {
            bad.push(`${label} in ${view}: the spine "${spine}" is at ${axis}=`
              + `${mean(spine).toFixed(0)} and "${p.slug}" at ${mean(p.slug).toFixed(0)}, `
              + `so the spine is not ${end}`);
          }
        });
      });
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('the spine is the first root, and a dependent can never be one', () => {
  /* WHAT REPLACED `spine: true` (Charles, GitHub #116, CL#123). The axis used to
     be its own declaration, kept separate from `order` because #85 found the two
     entangled in one sort. Under a drive tree there is nothing left for it to
     say: a root is exactly what "no `child`" means, the walk lays the roots out
     in `order`, and the first chain laid out IS the axis -- so the two keys could
     only ever have agreed, and a config could express a disagreement that the
     page would then have had to arbitrate.

     WHAT SURVIVES IS `order`, and it still moves the axis -- among the ROOTS.
     Changing which root is first changes the spine, which is the whole of what
     `spine: true` used to buy, in the key that was already there. */
  const declared = buildTrain(DECLARED);
  eq(declared.spine.slug, 'mid', 'the lowest-ordered root is not the axis');
  eq(declared.order.map(p => p.slug).join(','), 'mid,tiny,big',
    'the declared stack was not honoured');

  const reordered = DECLARED.map(p => p.slug === 'big'
    ? Object.assign({}, p, { order: 1 }) : p);
  const moved = buildTrain(reordered);
  eq(moved.spine.slug, 'big', 'moving a root to the head of the stack did not '
    + 'move the axis with it, so `order` no longer names the spine and nothing does');
  eq(moved.order.map(p => p.slug).join(','), 'big,mid,tiny',
    'the reordered stack was not honoured');

  /* A DEPENDENT IS NEVER THE AXIS, however low its `order`. `order` ranks
     siblings, and a chain with a parent is laid out inside its parent's subtree
     by construction -- there is no number it can carry that puts it first. */
  const low = CASCADE.map(p => p.child ? Object.assign({}, p, { order: -99 }) : p);
  eq(buildTrain(low).spine.slug, 'hub',
    'a dependent chain became the axis, so the walk is being overridden by a sort');

  /* AND THE SPINE IS ALWAYS THE HEAD OF THE LAYOUT. That is structural, not
     cosmetic: a bridge may only hang off a wheel already placed, so a spine
     emitted second would be driven by the chain it is supposed to drive. */
  [DECLARED, reordered, CASCADE, low, THREE].forEach(people => {
    const { order, spine } = buildTrain(people);
    eq(order[0].slug, spine.slug,
      'CHAIN_ORDER[0] is ' + order[0].slug + ', not the spine ' + spine.slug);
  });
});

test('the stack is a depth-first walk of the drive tree, not a sort', () => {
  /* Charles, GitHub #116: "if chloe ends up being marked as my child and harper
     has 3 clickable links, it goes me -> chloe child since it's a dependent,
     then harper". A DEPENDENT FOLLOWS ITS PARENT IMMEDIATELY even when an
     unrelated root is longer -- so link count stops ordering the page and
     survives only as the sibling tie-break.

     CASCADE is built to fail under a flat sort: `far` is the longest chain on
     stage and comes LAST, because it is a root and the walk finishes the spine's
     subtree before starting another one. Sort the four by anything at all and
     `far` moves. */
  const { order, driveFrom } = buildTrain(CASCADE);
  eq(order.map(p => p.slug).join(','), 'hub,kid,cub,far',
    'the chains did not come out as a depth-first walk of the drive tree');

  /* AND IT IS RECURSIVE, not one level deep: a grandchild follows ITS parent,
     inside its parent's own subtree, before the walk returns to the roots. */
  const deep = buildTrain(CASCADE.concat([
    { slug: 'pup', child: 'cub', links: [{ slug: 'p1' }] },
    { slug: 'gcub', child: 'kid', links: [{ slug: 'g1' }] }
  ]));
  eq(deep.order.map(p => p.slug).join(','), 'hub,kid,gcub,cub,pup,far',
    'a grandchild did not follow its own parent, so the walk is not depth-first');

  /* A PARENT IS ALWAYS PLACED BEFORE ANYTHING IT DRIVES, which is the invariant
     the entire solve rests on -- a bridge may only hang off a wheel already
     placed -- and under a tree it has to be checked rather than assumed. */
  const rank = {};
  order.forEach((p, k) => { rank[p.slug] = k; });
  Object.keys(driveFrom).forEach(slug => {
    ok(rank[driveFrom[slug]] < rank[slug],
      `${slug} takes its drive from ${driveFrom[slug]}, which is laid out after it`);
  });
});

test('siblings cascade off each other, they do not all hang off the parent', () => {
  /* Charles, GitHub #116: "obviously dependents sort by # of links -- with the
     lead gear of the first child being the place where the PTO for the next
     child feeds off". `child: 'hub'` declares MEMBERSHIP of hub's dependent
     group; the attachment point is COMPUTED. You do not take four power
     take-offs off one gear, you cascade them.

     SO THE SIBLING SORT AND THE DRIVE TOPOLOGY ARE ONE FACT. `kid` has two links
     and `cub` one, so kid leads and cub takes its drive from KID -- and `cub` is
     written FIRST in the fixture's PEOPLE, so a config-order walk fails this. */
  const { bridges, headOf, driveFrom, parent } = buildTrain(CASCADE);
  eq(driveFrom.kid, 'hub', 'the first sibling does not take its drive from the parent');
  eq(driveFrom.cub, 'kid', 'the second sibling hangs off the parent instead of off '
    + 'the lead gear of the sibling before it');
  eq(parent.cub, 'hub', 'the declared parent was rewritten by the cascade -- '
    + '`child` names the group, and the group is still hub');

  /* AND THE COMPUTED ATTACHMENT NAMES A WHEEL, not just a chain. A first child
     may take its drive anywhere along its parent's chain, so the search is left
     free (`at` is null); a later sibling names the exact lead gear. */
  const by = {};
  bridges.forEach(b => { by[b.person] = b; });
  eq(by.kid.at, null, "the first sibling's attachment was pinned to one wheel, so "
    + 'the search has nothing left to choose between');
  eq(by.cub.at, headOf.kid, 'the second sibling does not name its predecessor\'s '
    + 'lead gear as the wheel its drive comes off');
  ok(by.cub.at < by.cub.head, 'the wheel the drive comes off is emitted after the '
    + 'chain it drives, so it is not placed when it is asked for');

  /* THREE DEEP, because two siblings cannot tell a cascade from a rule that says
     "the previous chain". A third sibling must chain off the SECOND, not the first
     and not the parent. */
  const three = buildTrain(CASCADE.concat([
    { slug: 'runt', child: 'hub', links: [{ slug: 'r1' }] }
  ]));
  /* cub and runt both have one link, so the name breaks it, descending: runt, cub. */
  eq(three.order.map(p => p.slug).join(','), 'hub,kid,runt,cub,far',
    'siblings did not sort by link count then name, descending');
  eq(three.driveFrom.runt, 'kid', 'the second of three siblings did not take its '
    + 'drive from the first');
  eq(three.driveFrom.cub, 'runt', 'the third sibling did not take its drive from '
    + 'the second -- the drive is a star off the parent, not a cascade');
});

test('a child naming itself, a stranger, or a cycle is refused by name', () => {
  /* THREE MISTAKES BECOME NEWLY EXPRESSIBLE the moment a declaration names
     another chain, and all three are refused ALOUD and placed as roots. A walk
     that can recurse must never be one edit away from doing it, and a config
     that is quietly ignored is a composition nobody asked for. */
  const links = [{ slug: 'x' }];
  const self = buildTrain([
    { slug: 'a', links: links },
    { slug: 'b', child: 'b', links: links }
  ]);
  eq(self.parent.b, null, 'a chain declaring itself its own child was honoured');
  ok(self.spineWarns.some(w => /"b"/.test(w) && /its own child/.test(w)),
    'a chain drove itself in silence: ' + (self.spineWarns.join(' | ') || '(silence)'));

  const stranger = buildTrain([
    { slug: 'a', links: links },
    { slug: 'b', child: 'nobody', links: links }
  ]);
  eq(stranger.parent.b, null, 'a child naming a slug that is not a person was honoured');
  ok(stranger.spineWarns.some(w => /"nobody"/.test(w) && /not a person/.test(w)),
    'a dangling child name passed in silence: '
    + (stranger.spineWarns.join(' | ') || '(silence)'));

  /* A CYCLE, which is the one that does not merely draw the wrong thing -- an
     unguarded walk never terminates. Two-chain and three-chain, because a
     two-chain cycle can be caught by a self-reference test that a longer one
     walks straight past. */
  [[{ slug: 'a', child: 'b', links: links }, { slug: 'b', child: 'a', links: links }],
   [{ slug: 'a', child: 'c', links: links }, { slug: 'b', child: 'a', links: links },
    { slug: 'c', child: 'b', links: links }]
  ].forEach(people => {
    const cyc = buildTrain(people);
    const broke = people.filter(p => cyc.parent[p.slug] == null);
    ok(broke.length > 0, 'a drive cycle of ' + people.length + ' chains was left intact');
    ok(cyc.order.length === people.length,
      'a drive cycle lost a chain out of the layout instead of breaking the cycle');
    ok(cyc.spineWarns.some(w => /drive cycle/.test(w)),
      'a drive cycle was broken in silence: '
      + (cyc.spineWarns.join(' | ') || '(silence)'));
    /* And every chain still reaches a root in at most one pass per chain, which
       is the property the guard exists to give. */
    people.forEach(p => {
      let at = cyc.parent[p.slug], hops = 0;
      while (at != null && hops++ <= people.length) at = cyc.parent[at];
      ok(hops <= people.length, `${p.slug} still walks a cycle after the refusal`);
    });
  });
});

test('a parent off this stage is silent; a parent with no wheels is stepped over', () => {
  /* A SOLO PAGE CARRIES ONE PERSON, so every dependent's parent is legitimately
     absent there. That is not a mistake and must not warn -- it is the same
     silence `bridge` kept on a single-chain page, where there was nothing to
     bridge to. The test is the difference between a slug that is not on stage and
     one that is not in config.js at all, which is why buildTrain takes both. */
  const conf = [{ slug: 'a', links: [{ slug: 'x' }] },
    { slug: 'b', child: 'a', links: [{ slug: 'y' }] }];
  const solo = buildTrain([conf[1]], conf);
  eq(solo.parent.b, null, 'a dependent whose parent is not on stage was given one');
  eq(solo.spine.slug, 'b', 'a solo dependent is not the axis of its own page');
  eq(solo.spineWarns.join(' | '), '',
    'a solo page warned about a parent that is simply not on it');
  eq(solo.bridges.length, 0, 'the one chain on a solo page was given a bridge');
  eq(solo.origins.length, 0, 'the one chain on a solo page was given an origin '
    + 'run -- the spine takes no idlers, and a solo page is all spine');

  /* A PARENT WITH NO LINKS IS NOT LAID OUT AT ALL, so it cannot drive anything.
     The drive is taken from the nearest ancestor that IS on the page rather than
     from a chain that is not there, and the walk therefore never sees it. */
  const gap = buildTrain([
    { slug: 'top', links: [{ slug: 'a' }, { slug: 'b' }] },
    { slug: 'hollow', child: 'top', links: [] },
    { slug: 'under', child: 'hollow', links: [{ slug: 'c' }] }
  ]);
  eq(gap.parent.under, 'top', 'a chain with no wheels was left driving another one');
  eq(gap.order.map(p => p.slug).join(','), 'top,under,hollow',
    'a chain with no wheels is inside the walk instead of appended after it');
  eq(gap.driveFrom.under, 'top', 'the drive was taken from a chain that is not drawn');
});

test('the keys CL#123 retired are announced, not ignored', () => {
  /* `bridge` and `spine` did real work until CL#123, so a file still carrying one
     is not a typo -- it is a config that has not been migrated, and reading it in
     silence would draw a composition nobody asked for while config.js reads as
     though a choice had been made. Both are ignored, and both say so. */
  const stale = buildTrain([
    { slug: 'a', spine: true, links: [{ slug: 'x' }, { slug: 'y' }] },
    { slug: 'b', bridge: false, links: [{ slug: 'z' }] }
  ]);
  ok(stale.spineWarns.some(w => /"a"/.test(w) && /spine/.test(w) && /retired/.test(w)),
    'a leftover `spine` was ignored in silence: '
    + (stale.spineWarns.join(' | ') || '(silence)'));
  ok(stale.spineWarns.some(w => /"b"/.test(w) && /bridge/.test(w) && /retired/.test(w)),
    'a leftover `bridge` was ignored in silence: '
    + (stale.spineWarns.join(' | ') || '(silence)'));
  /* AND THE MESSAGE SAYS WHAT TO WRITE INSTEAD, which is the whole value of
     warning rather than dropping the key: `bridge: false` becomes no `child` at
     all, and `bridge: true` becomes a `child` naming somebody. */
  const kept = buildTrain([
    { slug: 'a', links: [{ slug: 'x' }] },
    { slug: 'b', bridge: true, links: [{ slug: 'z' }] }
  ]);
  ok(kept.spineWarns.some(w => /child: '<slug>'/.test(w)),
    'the migration note for `bridge: true` does not name the key that replaces it: '
    + (kept.spineWarns.join(' | ') || '(silence)'));
  ok(stale.spineWarns.some(w => /child: null/.test(w)),
    'the migration note for `bridge: false` does not name what replaces it: '
    + (stale.spineWarns.join(' | ') || '(silence)'));
  /* AND NEITHER KEY DOES ANYTHING. `a` declares the axis and does not get it --
     `b` is the shorter chain but neither declares an `order`, so the fallback
     ranks the roots by link count and `a` leads on its own merits; the proof that
     `spine: true` was ignored is that the identical stage without it lays out
     exactly the same. */
  eq(stale.order.map(p => p.slug).join(','),
    buildTrain([{ slug: 'a', links: [{ slug: 'x' }, { slug: 'y' }] },
      { slug: 'b', links: [{ slug: 'z' }] }]).order.map(p => p.slug).join(','),
    'a retired key changed the layout, so it is still being read');
});

test('the stack nobody declares is link count, then name, descending', () => {
  /* THE FALLBACK, WHICH IS NOT NOTHING. `order` is the rule; this is what a chain
     that has not been given one falls back to, and Charles set it on 2026-08-05:
     by number of links, then by name, DESCENDING on both. It replaced "ties keep
     PEOPLE order", which was not a rule so much as an artefact -- Array
     .prototype.sort is stable, so the tie fell to the line a person happened to
     be written on, and nothing in config.js said so.

     THE EXPECTED ORDER IS WORKED OUT HERE, from the fixture, rather than read
     back out of the page: this is the one assertion that must NOT share a
     derivation with the thing it is checking. Fixtures cover what the sort is
     actually asked to survive -- a tie on length, an all-equal set where the name
     is the ONLY signal (and where PEOPLE order is deliberately the reverse of the
     answer, so the old rule cannot pass), and an empty chain, which sorts last
     and cannot be the spine. */
  const bad = [];
  const chain = (slug, n) => ({ slug, name: slug.toUpperCase(),
    links: Array.from({ length: n }, (_, k) => ({ slug: slug + k })) });
  [[chain('a', 3), chain('b', 5), chain('c', 3)],
   [chain('a', 2), chain('b', 2), chain('c', 2)],
   [chain('a', 1), chain('b', 0), chain('c', 4)],
   [chain('only', 3)]
  ].forEach(people => {
    const want = people.slice()
      .sort((x, y) => ((y.links || []).length - (x.links || []).length)
        || (x.name < y.name ? 1 : x.name > y.name ? -1 : 0))
      .map(p => p.slug);
    const { order, spine } = buildTrain(people);
    const got = order.map(p => p.slug);
    if (got.join(',') !== want.join(',')) {
      bad.push(`[${people.map(p => p.slug + ':' + p.links.length).join(' ')}] stacks `
        + `${got.join(',')}, not links-then-name-descending ${want.join(',')}`);
    }
    /* And the undeclared spine is still the longest chain WITH WHEELS, which is
       what the old single sort chose and the only reason it was ever right. */
    const wantSpine = want.find(s => people.find(p => p.slug === s).links.length > 0);
    if (spine.slug !== wantSpine) {
      bad.push(`[${people.map(p => p.slug).join(' ')}] made ${spine.slug} the axis, `
        + `not ${wantSpine}`);
    }
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('a half-declared stack puts the declarations first, and the rest behind them', () => {
  /* THE STATE EVERY CONFIG PASSES THROUGH -- one person given an `order` and the
     others not yet -- and the one the fallback is easiest to get wrong in, since
     it is the only case where the declared rule and the default rule are both
     live at once. Infinity is what makes it need no branch of its own: an
     undeclared chain is at the far end of the stack by arithmetic, so it falls in
     behind every declaration however large the numbers are. */
  const link = (n) => Array.from({ length: n }, (_, k) => ({ slug: 's' + k }));
  const mixed = buildTrain([
    { slug: 'late-number', order: 900, links: link(1) },
    { slug: 'plain-long', links: link(4) },
    { slug: 'plain-short', links: link(2) },
    { slug: 'early-number', order: 3, links: link(1) }
  ]);
  eq(mixed.order.map(p => p.slug).join(','),
    'early-number,late-number,plain-long,plain-short',
    'a declared order did not outrank an undeclared chain, or the undeclared '
    + 'chains stopped falling in longest-first behind them');
  eq(mixed.spine.slug, 'early-number',
    'the head of the stack is not the axis when the stack is only half declared');

  /* TWO CHAINS ASKING FOR THE SAME PLACE ARE NOT A COIN TOSS. `a - b` is 0 for
     equal numbers, so the comparator falls through to the documented default --
     links descending, then name descending -- rather than to whichever pair the
     sort happened to compare. Both keys are asserted, because only the second can
     tell a decided fall-through from a lucky one: the name pair is written in the
     REVERSE of the answer, so the old PEOPLE-order rule would fail it. */
  eq(buildTrain([
    { slug: 'short', name: 'Short', order: 1, links: link(2) },
    { slug: 'long', name: 'Long', order: 1, links: link(5) }
  ]).order.map(p => p.slug).join(','), 'long,short',
    'two chains claiming one place did not fall through to longest-first');
  eq(buildTrain([
    { slug: 'anna', name: 'Anna', order: 1, links: link(2) },
    { slug: 'zoe', name: 'Zoe', order: 1, links: link(2) }
  ]).order.map(p => p.slug).join(','), 'zoe,anna',
    'two chains claiming one place at the same length did not break to name, '
    + 'descending');

  /* THE NAME KEY IS THE NAME, AND FALLS BACK TO THE SLUG. Case must not decide
     it either -- "alice" and "Alice" are one name spelt two ways, and a
     code-unit compare puts every capital before every lowercase, which would
     sort by shift key rather than by name. */
  eq(buildTrain([
    { slug: 'zeta', name: 'alpha', links: link(1) },
    { slug: 'alpha', name: 'Zeta', links: link(1) }
  ]).order.map(p => p.slug).join(','), 'alpha,zeta',
    'the tie broke on the slug or on letter case, not on the name');

  /* AND A NUMBER THAT IS NOT A POSITION IS NOT A DECLARATION. NaN compares false
     with everything including itself, so without the isFinite guard the
     comparator disagrees with itself and the order a sort returns from one is
     defined by nothing. It has to land on the documented default instead.

     THE NONSENSE CHAIN IS THE LONGER ONE ON PURPOSE. Without the guard the
     comparison yields NaN, the sort falls through to link count and the longest
     chain leads -- which is the answer the fixture would have got anyway if it
     were the shorter one, so a fixture that way round proves nothing. */
  eq(buildTrain([
    { slug: 'nonsense', order: NaN, links: link(5) },
    { slug: 'real', order: 2, links: link(1) }
  ]).order.map(p => p.slug).join(','), 'real,nonsense',
    'an unusable `order` was treated as a position rather than as no declaration');
});

test('the shipped config declares its stack and its drive, and gets what it declares', () => {
  /* #85 is only finished if the FILE says where each chain goes. Everything above
     proves the keys work on fixtures; this is the one that reads config.js, and
     it is what stops the next person added to the household from arriving with
     their position decided by how many links they happen to have -- which is the
     inference the whole issue exists to remove, and which would come back
     silently, because the default is deliberately the old rule.

     IT GATES `child` TOO NOW (GitHub #116, CL#123). A `child` is the one key in
     this file that names ANOTHER entry, so it is the one key that can be wrong
     about something other than itself: a typo, a self-reference or a cycle. The
     page refuses all three aloud at load, which is the right behaviour on a
     browser and the wrong place to find out. This is that same check, before the
     deploy.

     It is a gate on the config rather than on the code, so it says what to do. */
  const people = loadConfig().PEOPLE || [];
  const bad = [];
  const seen = {}, known = {};
  people.forEach(p => { known[p.slug] = p; });
  people.forEach(p => {
    if (!('order' in p)) {
      bad.push(`"${p.slug}" declares no order -- give it one (they need not be `
        + 'contiguous; 10, 20, 30 leaves room to insert people between them)');
      return;
    }
    if (!(typeof p.order === 'number' && isFinite(p.order))) {
      bad.push(`"${p.slug}" declares order: ${JSON.stringify(p.order)}, which is `
        + 'not a position -- it is ignored, and the chain silently falls back');
      return;
    }
    if (seen[p.order]) bad.push(`"${p.slug}" and "${seen[p.order]}" both claim `
      + `order ${p.order}, so the file does not decide which comes first`);
    seen[p.order] = p.slug;
  });

  /* THE RETIRED KEYS ARE A CONFIG FAULT, not a code one: the page ignores them
     and warns, and a file that still carries one is a migration nobody finished. */
  people.forEach(p => {
    ['spine', 'bridge'].forEach(k => {
      if (p[k] !== undefined) {
        bad.push(`"${p.slug}" still declares ${k}: ${JSON.stringify(p[k])}, which `
          + 'CL#123 retired -- `child` names who drives a chain, and its absence '
          + 'means nothing does');
      }
    });
  });

  people.forEach(p => {
    if (p.child == null) return;
    if (p.child === p.slug) {
      bad.push(`"${p.slug}" declares itself its own child -- nothing drives itself`);
      return;
    }
    if (!known[p.child]) {
      bad.push(`"${p.slug}" declares child: ${JSON.stringify(p.child)}, which is `
        + 'not a person in this file');
      return;
    }
    const walk = [p.slug];
    let at = known[p.child];
    while (at && at.child != null) {
      if (walk.indexOf(at.slug) >= 0) break;
      walk.push(at.slug);
      at = known[at.child];
      if (at && walk.indexOf(at.slug) >= 0) {
        bad.push(`"${p.slug}" is in a drive cycle (${walk.concat(at.slug).join(' -> ')})`);
        break;
      }
    }
  });

  /* AT LEAST ONE ROOT, or there is no axis and nothing on the page is driven by
     anything: a file where every chain names a parent is a file that is all
     cycle, however it is walked. */
  const roots = people.filter(p => p.child == null && (p.links || []).length);
  if (!roots.length) {
    bad.push('no chain in config.js is a root -- every one names a `child`, so '
      + 'there is no axis for the composition to be built around');
  }
  ok(bad.length === 0, bad.join('\n      '));

  /* AND THE PAGE USES WHAT THE FILE SAYS. Read back through index.html's own
     declarations against the real PEOPLE, so the assertion is about the shipped
     config going through the shipped derivation, not about either alone. The
     expected order is worked out HERE, from the file, rather than read back out
     of the page: the roots in ascending `order`, each followed by its own
     dependents. */
  const { order, spine, spineWarns } = buildTrain(people);
  const byOrder = (a, b) => a.order - b.order;
  const want = [];
  const push = (p) => {
    want.push(p.slug);
    people.filter(k => k.child === p.slug && (k.links || []).length)
      .sort(byOrder).forEach(push);
  };
  roots.slice().sort(byOrder).forEach(push);
  eq(spine.slug, want[0], 'the first root in config.js is not the chain the page '
    + 'laid out first, and the spine is the first root');
  eq(spineWarns.join(' | '), '', 'the shipped config provoked a drive-tree warning');
  eq(order.filter(p => (p.links || []).length).map(p => p.slug).join(','),
    want.join(','),
    'the shipped chains do not lay out as a walk of the drive tree in `order`');
});

test('a declared stack and a real cascade still compose into a well-formed machine', () => {
  /* The keys are not worth having if the arrangements they unlock do not solve.
     Both hard cases go through the same battery, at both stage rotations and at
     both idler counts:

       DECLARED -- three INDEPENDENT chains, a THREE-wheel axis with a SEVEN-wheel
       chain behind it, which no sort by link count could ever present to the
       solver, and which under CL#123 also means two self-driven chains each
       carrying an origin run of its own;
       CASCADE -- a spine with TWO dependents that chain off each other, plus an
       unrelated root, which is the only shape that exercises a computed
       attachment onto a named lead gear AND an origin run in the same solve.

     What is asked of each:

       every drive run hangs off a chain EARLIER in the layout order, which is
       what "a wheel already placed" means once solve() has chosen the anchor;
       no chain head fell back to the origin, the failure the bridge exists to
       remove;
       every wheel of every chain is placed at a finite point -- coverage;
       no wheel of one chain overlaps a wheel of another; and the spine itself
       -- three wheels, the shortest length that ever needs to pay ENDS_APART at
       all (GitHub #104) -- never falls back to planting a wheel with a warning. */
  const bad = [];
  [['DECLARED', DECLARED, 'mid'], ['CASCADE', CASCADE, 'hub']].forEach(([label, people, axis]) => {
    for (let trial = 0; trial < 40 && bad.length === 0; trial++) {
      const rot = trial % 2 ? 90 : 0, n = trial % 4 < 2 ? 1 : 2;
      const ctx = {};
      const { solved, train, bridges, origins, warns, spine, order } =
        runSolve(people, { axisRot: rot, idlerN: n, ctx });
      const where = `${label} at axisRot ${rot}, ${n} idler(s): `;
      eq(spine.slug, axis, label + ': the first root is not the axis the solver used');
      warns.forEach(w => bad.push(where + `warned "${w}"`));
      const rank = {};
      order.forEach((p, k) => { rank[p.slug] = k; });
      const at = {};
      solved.gears.forEach(w => { at[w.i] = w; });
      bridges.forEach(b => {
        const anchor = (ctx._bridgeAt || {})[b.person];
        if (!anchor || anchor.at == null) return;   /* a refused bridge is warned above */
        const host = chainOfWheel(train, { i: anchor.at, person: train[anchor.at].person });
        if (!(rank[host] < rank[b.person])) {
          bad.push(where + `chain ${b.person} hangs off ${host}, which is not `
            + 'earlier in the layout order');
        }
        const head = at[b.head];
        if (!head) bad.push(where + `chain ${b.person}'s head is not placed at all`);
        else if (Math.hypot(head.x, head.y) < 1e-9) {
          bad.push(where + `chain ${b.person}'s head fell back to the origin`);
        }
      });
      /* AN ORIGIN RUN IS STRUCTURE, SO ITS IDLERS ARE PLACED WHEELS -- every one
         of them that is still in mesh at this idler count, at a finite point.
         A run that is registered and not drawn is a chain that says it drives
         itself and shows nothing doing it.

         AND EXACTLY THAT MANY. `nIdle` is a property of the VIEWPORT -- how much
         cross axis there is to spend -- and an origin run is the same run of
         plain idlers a bridge is, so a stage with room for one bridge idler has
         room for one of these. Parked in the same pass and by the same count, so
         the surplus must be absent as firmly as the rest must be present:
         asserting only the presence half leaves a run free to draw its full
         MAX_IDLERS on a viewport that has room for one. */
      origins.forEach(o => {
        o.idlers.forEach((ix, k) => {
          const w = at[ix];
          if (k < n) {
            if (!w) bad.push(where + `${o.person}'s origin idler ${ix} was not placed`);
            else if (!isFinite(w.x) || !isFinite(w.y)) {
              bad.push(where + `${o.person}'s origin idler ${ix} is at (${w.x}, ${w.y})`);
            }
          } else if (w) {
            bad.push(where + `${o.person}'s origin run drew idler ${ix}, slot ${k}, `
              + `on a stage with room for ${n} — the surplus is not parked`);
          }
        });
      });
      train.forEach((t, i) => {
        if (t.role !== 'link') return;
        const w = at[i];
        if (!w) bad.push(where + `${t.person} wheel ${i} was not placed at all`);
        else if (!isFinite(w.x) || !isFinite(w.y)) {
          bad.push(where + `${t.person} wheel ${i} is at (${w.x}, ${w.y})`);
        }
      });
      crossChainFouls(train, solved).forEach(f => bad.push(where + f));
    }
  });
  ok(bad.length === 0, [...new Set(bad)].slice(0, 5).join('\n      '));
});

test('a three-wheel spine pays ENDS_APART instead of planting a wheel (GitHub #104)', () => {
  /* The narrowest case ENDS_APART ever has to settle: a spine of exactly three
     wheels, alone on stage, no bridges to complicate it. Wheel 2 is the leaf,
     wheel 0 is the root, and wheel 1 -- the only host between them -- is one
     mesh step from each, so the CLEARANCE and ENDS_APART the leaf owes the root
     have to fit inside ONE wheel's own +/-60 degree nudge. Before CL#111 the
     flat push (90) asked for more separation than a lot of dealt hosts could
     ever produce, in EITHER direction, and 'wozi: wheel 2 ... found no clear
     bearing' planted the leaf anyway on a measured 483 of 1,000 deals against
     the pre-fix file (48.3%, GitHub #104's own count was ~41%). Run against
     many real deals here too, because it is the teeth and bearings drawn that
     decide whether the push is payable, not any single lucky one.

     THIS TEST CAN FAIL: comment out the `Math.min(ENDS_APART * tight,
     endsApartCapFor(o))` cap in solve() (restore a flat `ENDS_APART * tight`)
     and this assertion trips within the first few of these 200 trials --
     verified by hand while writing it, then restored. A trial count small
     enough to pass by luck on the broken code would not be evidence of
     anything. */
  const bad = [];
  const THREE_WHEEL_SPINE = [{ slug: 'solo', links: [{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }] }];
  let trials = 0;
  for (let trial = 0; trial < 200; trial++) {
    [0, 90].forEach(rot => {
      trials++;
      const { warns } = runSolve(THREE_WHEEL_SPINE, { axisRot: rot });
      warns.filter(w => /found no clear bearing/.test(w)).forEach(w => bad.push(`axisRot ${rot}: ${w}`));
    });
  }
  ok(bad.length === 0, bad.length + ' of ' + trials + ' deals planted the leaf without a '
    + 'clear bearing: ' + bad.slice(0, 3).join('; '));
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

test('a self-driven chain takes its sense from its own idler count, not a second clock', () => {
  /* "Its own idler train, its own ratio, its own resulting direction" (GitHub
     #107, folded into #116). WHERE THE DIRECTION COMES FROM is the whole of the
     claim: the far end of the origin run is the driver, so the count of idlers
     between it and the lead gear decides which way that chain turns -- the same
     rule a bridged chain has always obeyed, applied to a run that starts off the
     stage instead of on another chain.

     SO IT IS DERIVED, AND IT MOVES WHEN THE COUNT MOVES. Solve the same stage at
     one idler and at two: an independent chain's lead gear must come out the
     other way round, and the spine's must not move at all, because nothing
     stands between the spine and the drive it is the datum of.

     AND THERE IS NO SECOND INTEGRATOR IN ANY OF IT (CL#3, the invariant this
     page has broken twice). Independence is an independent drive PATH; every
     wheel's angle is still `phase + dir * _M / teeth` off the one master angle,
     and `dir` is a solve-time constant. The rule is checked at its one home --
     applyRotation() -- because a second clock would have to appear there. */
  const dirOf = (solved, slug, heads) => {
    const w = solved.gears.find(g => g.i === heads[slug]);
    return w ? w.dir : null;
  };
  const bad = [];
  for (let trial = 0; trial < 20; trial++) {
    [0, 90].forEach(rot => {
      const one = runSolve(THREE, { axisRot: rot, idlerN: 1 });
      const two = runSolve(THREE, { axisRot: rot, idlerN: 2 });
      const spine = one.order[0].slug;
      const where = `axisRot ${rot}: `;
      if (dirOf(one.solved, spine, one.headOf) !== dirOf(two.solved, spine, two.headOf)) {
        bad.push(where + 'the spine changed sense with the idler count, and nothing '
          + 'stands between it and the drive');
      }
      one.origins.forEach(o => {
        if (o.mounted) return;   /* a mounted run re-parents instead; see below */
        const a = dirOf(one.solved, o.person, one.headOf);
        const b = dirOf(two.solved, o.person, two.headOf);
        if (a === null || b === null) return bad.push(where + o.person + "'s lead gear was not placed");
        if (a === b) {
          bad.push(where + `${o.person} turns ${a} through both one idler and two, `
            + 'so its sense is not derived from its own origin run at all');
        }
      });
    });
  }
  ok(bad.length === 0, [...new Set(bad)].slice(0, 4).join('\n      '));

  /* ONE CLOCK, read at the only place a second one could be introduced. */
  const rot = grabBlock('  applyRotation() {', '{', '}');
  ok(!/requestAnimationFrame|performance\.now|Date\.now|setInterval|setTimeout/.test(rot),
    'applyRotation() reaches for a clock of its own — every wheel must derive '
    + 'from the one master angle (CL#3)');
  const angles = rot.match(/rotate\('[^)]*\+[^)]*\)/g) || [];
  ok(angles.length > 0 && angles.every(a => /_M/.test(a)),
    'a transform is written from something other than the master angle: '
    + angles.filter(a => !/_M/.test(a)).join(' | '));
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

     IT NEEDS A STAGE WITH BRIDGES ON IT, which is CASCADE and no longer THREE:
     under CL#123 a stage of roots has no bridges to refuse, because nothing on it
     is driven by anything else. Forced by asking for a clearance nothing can
     satisfy, so EVERY candidate is rejected for every dependent chain. */
  const { solved, train, bridges, origins, warns } = runSolve(CASCADE, { tight: 400 });

  const anchor = warns.filter(w => /no clear bridge anchor/.test(w));
  ok(anchor.length > 0,
    'every candidate was rejected and nothing was said: ' + (warns[0] || '(silence)'));
  ok(/candidates rejected/.test(anchor[0]) && /fouled a wheel/.test(anchor[0]),
    'the warning does not say why the candidates were rejected: ' + anchor[0]);
  ok(/chain "/.test(anchor[0]), 'the warning does not name the chain: ' + anchor[0]);
  ok(/refusing to bridge/.test(anchor[0]),
    'the warning does not say the bridge was refused: ' + anchor[0]);

  /* NO BRIDGE GEOMETRY IS EMITTED. Not a parked surplus idler -- none at all.
     The origin runs on the same stage are untouched by any of this: a refusal is
     a statement about an anchor on ANOTHER chain, and a self-driven chain has no
     anchor to lose. Counted apart for exactly that reason -- summing them would
     let a refused bridge hide behind an origin run that is still there. */
  const bridgeIdlers = solved.gears.filter(w => w.role === 'idler'
    && train[w.i].drive === 'bridge');
  eq(bridgeIdlers.length, 0,
    'a refused bridge still drew ' + bridgeIdlers.length + ' idler(s): '
    + bridgeIdlers.map(w => 'wheel ' + w.i).join(', '));
  eq(solved.gears.filter(w => w.role === 'idler' && train[w.i].drive === 'origin').length,
    origins.length * grabNumber('MAX_IDLERS'),
    'a refused bridge cost an unrelated chain its own origin run');

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

test('a refused hop keeps its cascade in place, and names what it left undriven', () => {
  /* THE ONE THING A CASCADE ADDED TO A REFUSAL (Charles, GitHub #116, CL#123). A
     bridge that cannot be placed cleanly refuses and the chain is placed
     undriven; under a star off the spine that cost exactly one chain its drive.
     Under a cascade every chain whose drive path runs THROUGH the refused one
     loses its drive as well -- and loses NOTHING ELSE, which is what makes it
     dangerous: a later sibling still cascades off the refused chain's lead gear,
     is still placed exactly where it was going, and looks completely correct.

     SO THE DEFINED FALLBACK IS: POSITION SURVIVES, DRIVE DOES NOT, AND THE
     CONSOLE SAYS WHOSE. Asserted as all three -- the downstream sibling is still
     bridged and still hangs off the chain it was told to, no wheel is lost, and
     the refusal warning names the chains it stranded.

     PROVOKED RATHER THAN FORCED. A clearance nothing can satisfy refuses every
     bridge on the stage, which is not the interesting case; the interesting one
     is a refusal partway down a cascade, and that arrives on its own at a
     clearance in between. Trials are run until it does, and the test says so
     rather than passing vacuously if it never happens. */
  let saw = 0;
  const bad = [];
  [2.5, 3, 4].forEach(t => {
    for (let k = 0; k < 30; k++) {
      [0, 90].forEach(rot => {
        [1, 2].forEach(n => {
          const ctx = {};
          const { train, solved, warns } = runSolve(CASCADE, { axisRot: rot, idlerN: n, tight: t, ctx });
          const refused = warns.filter(w => /no clear bridge anchor/.test(w));
          const named = refused.map(w => (w.match(/chain "([^"]+)"/) || [])[1]);
          if (named.indexOf('kid') < 0 || named.indexOf('cub') >= 0) return;
          saw++;
          const where = `tight ${t}, axisRot ${rot}, ${n} idler(s): `;
          /* THE REFUSAL NAMES WHAT IT STRANDED. `cub` takes its drive through
             `kid`, so a refusal of kid's bridge is the cause of cub being
             undriven, and it is the only place that can be said. */
          const w = refused[named.indexOf('kid')];
          if (!/undriven too/.test(w) || !/cub/.test(w)) {
            bad.push(where + 'the refusal did not name the cascade it stranded: ' + w);
          }
          /* AND THE CASCADE IS STILL THERE. cub keeps its bridge, still hangs off
             kid, and every one of its wheels is still placed -- the failure is a
             loss of drive and of nothing else. */
          const a = ctx._bridgeAt.cub;
          if (!a || a.at == null) return bad.push(where + 'cub lost its anchor with kid\'s');
          if (!a.bridged) bad.push(where + 'cub lost its own bridge to a refusal upstream of it');
          const took = train[a.at].person != null ? train[a.at].person : train[a.at].bridge;
          if (took !== 'kid') bad.push(where + 'cub cascades off ' + took + ', not off kid');
          const placed = {};
          solved.gears.forEach(g => { placed[g.i] = g; });
          train.forEach((e, i) => {
            if (e.role === 'link' && !placed[i]) bad.push(where + `${e.person} wheel ${i} was dropped`);
          });
        });
      });
    }
  });
  ok(saw > 0, 'no trial refused a hop partway down the cascade, so nothing here '
    + 'was actually exercised — widen the clearance sweep');
  ok(bad.length === 0, [...new Set(bad)].slice(0, 5).join('\n      '));
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
  const fn = new Function('SPINE_SLUG',
    'return function ' + grabBlock('  chainAxes(solved) {', '{', '}') + ';')(
    spineSlug);
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
  /* TEETH_MIN/TEETH_MAX and ESCAPE_WOBBLE are the run's own sizing rule since #80:
     the wheels are dealt over the chain's range instead of a ramp of their own, and
     the wheel-count backstop is derived from the smallest step the loop can take.
     Handed in from the page's values, never restated here. */
  const fn = new Function('window', 'MODULE', 'TOOTH_ADD', 'GHOST_COLORS', 'segCross',
    'TEETH_MIN', 'TEETH_MAX', 'ESCAPE_WOBBLE',
    'ESCAPE_SEARCH_ARC', 'ESCAPE_CROSS_EXT_PX', 'ESCAPE_MIN_REACH_PX', 'ESCAPE_RUN_MARGIN',
    'return function ' + grabBlock('  fitEscapes() {', '{', '}') + ';')(
    { innerWidth: solved.w + margin * 2, innerHeight: solved.h + margin * 2 },
    page.MODULE, page.TOOTH_ADD, ['#000'],
    new Function('return ' + grabBlock('function segCross(', '{', '}'))(),
    page.TEETH_MIN, page.TEETH_MAX, page.ESCAPE_WOBBLE,
    page.ESCAPE_SEARCH_ARC, page.ESCAPE_CROSS_EXT_PX, page.ESCAPE_MIN_REACH_PX, page.ESCAPE_RUN_MARGIN);
  const ctx = {
    _axisRot: axisRot,
    _stageRef: { current: { getBoundingClientRect: () => (
      { width: solved.w, height: solved.h, left: margin, top: margin }) } },
    /* fitEscapes also measures the wordmark now, so the datum plate can be
       stamped at the end of its mark furthest from it (GitHub #131). There is no
       DOM here, so the ref is present and unattached -- which is the state the
       page itself is in for the frame before its first fit, and plateSeat's own
       fallback covers it. Supplied for the same reason _stageRef is: a lifted
       function reaching for a ref the harness never gave it throws, and these
       tests are about escape runs rather than about the plate. */
    _colRef: { current: null },
    solve: () => solved,
    chainAxes: new Function('SPINE_SLUG',
      'return function ' + grabBlock('  chainAxes(solved) {', '{', '}') + ';')(
      spineSlug),
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
    /* ro, r, i and teeth come along too (CL#119, GitHub #100): the addendum
       agreement test needs the outer and pitch radii a ghost was actually
       placed with, not merely where its centre landed. */
    (runs[ei] = runs[ei] || []).push({ cx: g.cx, cy: g.cy,
      person: g.person, lead: g.lead, k: g.k,
      hostCx: g.hostCx, hostCy: g.hostCy,
      ro: g.ro, r: g.r, i: g.i, teeth: g.teeth });
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
    /* WHO GETS A LEADING RUN, and the rule is about DRIVE, not about the spine.
       The spine keeps both. A chain something on stage drives keeps only the
       trailing one, because the leading end is where its bridge arrives and a
       second tail there would run into the machinery driving it. A SELF-DRIVEN
       ROOT keeps both as well: nothing arrives at its leading end except its own
       origin run, so withholding the run left it stopping dead in open space
       while the spine ran off the frame.

       THIS FIXTURE IS ALL ROOTS, which is the whole reason the old form of this
       assertion was never true of what it claimed. It asserted "every non-spine
       chain gets one" and reported failures as "driven chain mid", against a
       THREE whose own comment says its chains "are therefore self-driven, each
       with an origin run of its own". The driven case is asserted separately,
       below, against CASCADE -- which actually has bridges. */
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
      /* Asked of the solve rather than of the config: a chain owns an origin run
         exactly when it is self-driven, and the wheels say so themselves. */
      const selfDriven = solved.gears.some(g => g.drive === 'origin' && g.serves === c.person);
      const want = selfDriven ? 2 : 1;
      if (mine.length !== want) {
        bad.push(`rot ${rot}: ${selfDriven ? 'self-driven root' : 'driven chain'} ${c.person} `
          + `got ${mine.length} escape runs, not ${want}`);
      } else if (!selfDriven && mine[0][0].lead) {
        bad.push(`rot ${rot}: driven chain ${c.person}'s run leaves by the LEADING end, `
          + 'which is the end its bridge arrives at');
      } else if (selfDriven && mine.filter(r => r[0].lead).length !== 1) {
        bad.push(`rot ${rot}: self-driven root ${c.person}'s two runs do not leave by `
          + 'opposite ends');
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
        /* THE WHEEL THE RUN ACTUALLY GREW FROM, as recorded by fitEscapes. This
           was `r[0].lead ? c.head : c.tail`, which stopped being true when a
           self-driven root's leading run moved onto the far end of its origin
           run -- and a heading measured from the wrong origin is off by the
           whole length of that run. */
        const host = { cx: r[0].hostCx, cy: r[0].hostCy };
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

test('a DRIVEN chain keeps only its trailing escape run, and a root keeps both', () => {
  /* THE RULE THIS ASSERTS HAD NEVER BEEN TESTED AGAINST A DRIVEN CHAIN. The
     assertion above ran on THREE, whose chains are all self-driven roots -- its
     own comment says so -- yet it reported failures as "driven chain mid got N
     escape runs". It was checking `!spine`, calling that "driven", and no
     fixture on the page ever put a real bridge under it.

     CASCADE has all four cases at once: `hub` is the spine, `kid` and `cub` are
     driven off it (and off each other, as the cascade), and `far` is a root with
     an origin run of its own. So this is the first time the withheld leading run
     is measured on a chain that actually has a bridge arriving there -- which is
     the entire justification the rule was written with. */
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, order } = runSolve(CASCADE, { axisRot: rot });
    const spineSlug = order[0].slug;
    const axes = chainAxesOf(solved, rot, spineSlug);
    const runs = fitEscapesOn(solved, rot, spineSlug);
    const byPerson = {};
    Object.keys(runs).forEach(ei => {
      const r = runs[ei];
      (byPerson[r[0].person] = byPerson[r[0].person] || []).push(r);
    });
    let sawDriven = 0;
    axes.forEach(c => {
      const mine = byPerson[c.person] || [];
      const selfDriven = solved.gears.some(g => g.drive === 'origin' && g.serves === c.person);
      const want = (c.spine || selfDriven) ? 2 : 1;
      if (!c.spine && !selfDriven) sawDriven++;
      if (mine.length !== want) {
        bad.push(`rot ${rot}: ${c.person} (${c.spine ? 'spine' : selfDriven ? 'root' : 'driven'}) `
          + `got ${mine.length} escape runs, wanted ${want}`);
      } else if (want === 1 && mine[0][0].lead) {
        bad.push(`rot ${rot}: driven chain ${c.person} kept its LEADING run, which is the `
          + 'end its bridge arrives at');
      }
    });
    /* Without this the whole test passes vacuously if CASCADE ever stops
       producing a bridged chain. */
    ok(sawDriven >= 1, `rot ${rot}: CASCADE solved with no driven chain at all, so the `
      + 'rule this test exists for was not exercised');
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('a ghost addendum is derived from TOOTH_ADD, and every reader of it agrees (CL#119, GitHub #100)', () => {
  /* A ghost's outer radius used to be computed three ways -- 0.95 in fitEscapes'
     ghost creation, 1.25 in the ghost-layer bounding box, and TOOTH_ADD (1.00)
     everywhere a linked wheel is measured -- and none of the first two was
     TOOTH_ADD. The failure mode is DISAGREEMENT, so this asserts agreement
     rather than pinning any one number: reintroduce either of the old values
     and one of the two checks below should fail, naming which call site regressed
     and by how much, rather than a bare "expected X got Y". */

  /* Call site 1: fitEscapes() itself, run for real via fitEscapesOn (same harness
     the two tests above use) rather than regexed as text -- a ghost's ro is a
     runtime VALUE, and only running the function reads it back. */
  const { solved, order } = runSolve(THREE, { axisRot: 0 });
  const runs = fitEscapesOn(solved, 0, order[0].slug);
  const bad = [];
  Object.keys(runs).forEach(ei => runs[ei].forEach(g => {
    const addendModules = (g.ro - g.r) / page.MODULE;
    if (Math.abs(addendModules - page.TOOTH_ADD) > 1e-9) {
      bad.push(`ghost ${g.i}: fitEscapes' addendum is ${addendModules.toFixed(3)} modules, `
        + `TOOTH_ADD is ${page.TOOTH_ADD} -- ghost creation has drifted off TOOTH_ADD again`);
    }
  }));
  ok(bad.length === 0, bad.join('\n      '));

  /* Call site 2: the ghost-layer bounding-box computation inside renderVals().
     It is not standalone-callable -- it reaches into this.state, S and solved --
     so read its `ro` formula as TEXT and check it is built from TOOTH_ADD rather
     than restating the addendum as a private number. Checking the identifier is
     what catches a reintroduced magic number that happens to still total 1.25:
     the old bug was never really about the NUMBER 1.25, it was about it not
     being spelled TOOTH_ADD + something. */
  const renderSrc = grabBlock('  renderVals() {', '{', '}');
  const m = renderSrc.match(/const ro = MODULE \* \(g\.teeth \/ 2 \+ ([^)]+)\) \* S/);
  if (!m) throw new Error('the ghost-layer bounding-box ro formula was not found in renderVals() '
    + '-- it moved or was rewritten; update the regex in this test to match');
  const addendExpr = m[1].trim();
  ok(/\bTOOTH_ADD\b/.test(addendExpr),
    `the ghost-layer bounding box's addendum term is "${addendExpr}" and does not mention `
    + 'TOOTH_ADD -- it is a competing addendum again, the exact shape of GitHub #100');
  /* And numerically: evaluate the captured expression with the page's real
     constants, so a rewrite that keeps the word TOOTH_ADD but drops the box back
     to under-reserving still gets caught. Over-reserving costs a slightly larger
     compositing surface; under-reserving clips a tooth, which is the actual bug
     (see the comment immediately above this line in index.html). */
  const padModules = new Function('TOOTH_ADD', 'GHOST_BOX_PAD',
    'return (' + addendExpr + ') - TOOTH_ADD;')(page.TOOTH_ADD, grabNumber('GHOST_BOX_PAD'));
  ok(padModules >= 0, `the ghost-layer box reserves ${padModules.toFixed(3)} modules LESS than `
    + `TOOTH_ADD (${page.TOOTH_ADD}) -- under-reserving clips a tooth`);
});

test('a chain axis is measured from its own linked wheels, never its idlers', () => {
  /* Including an idler drags the axis toward the BRIDGE, which is perpendicular
     to the chain -- for a one-wheel chain it becomes the bridge exactly. That is
     the whole defect: escape runs leaving along the spine-to-branch diagonal.

     SO THE FIXTURE HAS TO BE ONE WITH BRIDGES ON IT, which is CASCADE and not
     THREE (CL#123). An origin run's idlers travel ALONG their chain's own axis
     rather than across to another chain, so counting them barely moves the answer
     and the naive measurement below has nothing to be measurably worse than --
     the test would pass on a page where the defect was fully present. */
  const bad = [];
  [0, 90].forEach(rot => {
    const { solved, train, order } = runSolve(CASCADE, { axisRot: rot });
    const axes = chainAxesOf(solved, rot, order[0].slug);
    eq(axes.length, CASCADE.length, 'rot ' + rot + ': not every chain has an axis');
    const spine = axes.find(c => c.spine);
    ok(spine && spine.person === order[0].slug,
      'rot ' + rot + ': the chain chainAxes() calls the spine is not the one laid out first');
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
      /* THE COMPARISON BELOW IS ABOUT BRIDGE IDLERS, so a chain that has none is
         not evidence either way (CL#123). An ORIGIN run's idlers travel along
         their own chain's axis rather than across to another chain, so counting
         them barely moves the naive answer -- and a fixture that let a
         self-driven chain into this comparison would be asserting that a
         difference of nearly nothing is a difference, which passes on a page
         where the defect is fully present. */
      if (!solved.gears.some(w => w.role === 'idler'
        && train[w.i].bridge === c.person && train[w.i].drive === 'bridge')) return;
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
     really does lie across the run that was placed without it.

     AND THE SET IT IS SEEDED WITH INCLUDES ORIGIN RUNS (CL#123). THREE is three
     roots, so two of its four published runs are origin runs -- a self-driven
     chain's own drive is metal across the composition exactly as a bridge is, and
     every one of them is planted in turn below rather than only the first. */
  const bad = [];
  const seg = (p) => ({ x: p.cx, y: p.cy });
  [0, 90].forEach(rot => {
    const { solved, order, origins } = runSolve(THREE, { axisRot: rot });
    ok(origins.length > 0 && solved.bridgeRuns.length > origins.length,
      'rot ' + rot + ': the fixture publishes no origin run, so this test cannot '
      + 'tell whether fitEscapes sees one');
    const spineSlug = order[0].slug;
    const branches = chainAxesOf(solved, rot, spineSlug).filter(c => !c.spine);
    const clear = fitEscapesOn(Object.assign({}, solved, { bridgeRuns: [] }), rot, spineSlug);
    /* SELECTED BY WHAT THE RUN IS, not by where it landed in the hosts array.
       This used to compute `String(2 + bi)` from "the spine's two, then one per
       branch" -- an arithmetic model of the emission order, which silently
       aimed at the wrong run the moment a self-driven root started pushing a
       leading host as well as a trailing one. It then reported that a bridge
       laid across `tiny`'s run had not moved it, while actually examining
       `mid`'s. The trailing run is the one this test anchors at `c.tail`, so
       ask for that. */
    const runOf = (set, person) => {
      const k = Object.keys(set).find(key =>
        set[key][0].person === person && !set[key][0].lead);
      return k ? set[k] : null;
    };
    branches.forEach((c) => {
      const run = runOf(clear, c.person);
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
        const moved = runOf(blocked, c.person);
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
  /* ONE PUBLISHED RUN PER STRUCTURAL RUN, and there are two kinds now (CL#123):
     a BRIDGES entry -- the run that carries another chain's drive in, or, for an
     independent chain, the step that carries its position -- and an ORIGINS
     entry, the run a self-driven chain turns on. Both are metal laid across the
     composition, so both have to come out where a later bridge and fitEscapes can
     refuse to cross them; an origin run that stayed inside solve() would be the
     exact hole this test was written to close, reopened for the new run. Counted
     off the TRAIN builder's own two arrays rather than off a number, because
     which chains get which run is the config's business and not this test's. */
  const { solved, bridges, origins } = runSolve(CASCADE, { axisRot: 0 });
  eq(solved.bridgeRuns.length, bridges.length + origins.length,
    'solve() does not publish one run per bridge and one per origin run');
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
    chainAxes: new Function('SPINE_SLUG',
      'return function ' + grabBlock('  chainAxes(solved) {', '{', '}') + ';')(
      spineSlug)
  };
  return fn.call(ctx, solved, ghosts || [], S === undefined ? 1 : S);
}
/* plateSeat() lifted out of the page. It reads exactly two things off the
   component -- the measured viewport box and its own margin rule -- so both are
   handed in and the seat it returns is the seat the page would compute, and one
   constant, which is read out of index.html rather than copied (#95): a suite
   holding its own 25 would agree with itself forever while the page moved.
   `past` is the run-out datumLayer draws beyond the assembly, and is handed in
   the same way the page hands it in. Warnings are captured rather than printed:
   "neither side fits" is a reported state, and a test that could not see it
   could not tell it from a silent give-up.

   `brand` IS THE MEASURED WORDMARK (GitHub #131, CL#160), handed in unattached
   exactly as `_vpBox` is: plateSeat() reads `this._brandBox` to decide which END
   of the mark it stamps at, and a component the harness never builds has no
   wordmark to measure. Left off it is UNDEFINED, which is the page's own state
   for the frame before the ref is attached -- so every caller written before
   this parameter existed goes on testing the near-end anchor it always did, and
   none of them had to be touched to say so. */
function plateSeatOn(vpBox, r, S, pw, ph, past, box, metal, brand) {
  const metrics = new Function('MODULE',
    'return function ' + grabBlock('  plateMetrics(s) {', '{', '}') + ';')(page.MODULE);
  const margin = new Function('return function ' + grabBlock('  plateMargin(s) {', '{', '}') + ';')();
  /* plateSeat() now calls this.plateAir() and this.datumClear() (GitHub #88,
     CL#108 re-landed), so both are extracted onto the ctx the same way
     plateMetrics/plateMargin already were -- a lifted function calling a
     method the harness never gave it throws, which is exactly the shape of
     extraction failure this file's own docstring warns about. */
  const air = new Function('MODULE',
    'return function ' + grabBlock('  plateAir(O, at, r, pw, ph, metal) {', '{', '}') + ';')(page.MODULE);
  const clear = new Function('MODULE', 'PLATE_TOP_CLEAR',
    'return function ' + grabBlock('  datumClear(S) {', '{', '}') + ';')(
    page.MODULE, page.PLATE_TOP_CLEAR);
  /* plateSeat() now searches for an exact clean window before falling back
     to the single unsearched point (GitHub #88/#109/#110 follow-up) -- both
     helpers it calls on `this` are extracted the same way plateAir/datumClear
     already are. */
  const excl = new Function('return function ' + grabBlock('  plateExcluded(O, r, pw, ph, metal, air) {', '{', '}') + ';')();
  const nearest = new Function('return function ' + grabBlock('  plateNearestClean(want, lo, hi, excluded) {', '{', '}') + ';')();
  const seat = new Function('PLATE_START_ALONG',
    'return function ' + grabBlock('  plateSeat(r, S, pw, ph, past, box, metal) {', '{', '}') + ';')(
    page.PLATE_START_ALONG);
  const clip = new Function('return function ' + grabBlock('  slabClip(px, py, dx, dy, box) {', '{', '}') + ';')();
  const warns = [];
  const ctx = { _vpBox: vpBox, _brandBox: brand, plateMetrics: metrics,
    plateMargin: margin, slabClip: clip,
    plateAir: air, datumClear: clear, plateExcluded: excl, plateNearestClean: nearest };
  const real = console.warn;
  console.warn = (m) => warns.push(m);
  try {
    const out = seat.call(ctx, r, S, pw, ph, past === undefined ? 0 : past, box || vpBox, metal || []);
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
const DATUM_DRAW = SRC.slice(SRC.indexOf('  datumLayer(solved, S, box, metal) {'),
  SRC.indexOf('  renderVals() {'));
/* Bounded at datumInk() rather than at ghostSvg(), because the two methods sit
   next to each other and the rule below is about ONE of them. datumOpacity() may
   never end at the current theme's ghost alpha; datumInk() divides by that same
   alpha on every path, by design (#81). Slicing to the far side of both would
   read the second one's arithmetic as the first one's fallback. */
const DATUM_OP = SRC.slice(SRC.indexOf('  datumOpacity() {'),
  SRC.indexOf('  datumInk() {'));
const DATUM_INK = SRC.slice(SRC.indexOf('  datumInk() {'),
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
  if (!m) return null;
  const raw = m[1].trim();
  /* RESOLVE ONE var() INDIRECTION, because the stylesheet uses them and a browser
     would. CL#140 gave the dark page colour a home in :root as --ref-bg-dark so
     BOTH grounds are readable from either theme -- the light ghost fade is solved
     by matching one against the other -- and pointed the dark block's --bg at it,
     the same shape light has always had with --ref-bg. This harness reads the CSS
     as TEXT, so without this it handed 'var(--ref-bg-dark)' to rgbOf(), got null,
     and reported "datumInk did not return a colour for --muted from a palette
     that declares it": a true statement about the test and a false one about the
     page. */
  const ref = /^var\(\s*(--[\w-]+)\s*\)$/.exec(raw);
  return ref ? cssVar(CSS_ROOT, ref[1]) : raw;
}
const TOKENS = {
  light: { '--ref-bg': cssVar(CSS_ROOT, '--ref-bg'), '--ref-muted': cssVar(CSS_ROOT, '--ref-muted'),
    /* `--muted` IS READ AS ITSELF, NOT AS --ref-muted (GitHub #152). The two were
       one declaration and this modelled the alias; they are separate facts now,
       and while their hexes agree that is invisible -- the moment the ink moves,
       reading it through the reference would assert the light alpha of a palette
       the page does not have, and pass. */
    '--bg': cssVar(CSS_ROOT, '--ref-bg'), '--muted': cssVar(CSS_ROOT, '--muted'),
    '--hair': cssVar(CSS_ROOT, '--hair') },
  dark: { '--ref-bg': cssVar(CSS_ROOT, '--ref-bg'), '--ref-muted': cssVar(CSS_ROOT, '--ref-muted'),
    '--bg': cssVar(CSS_DARK, '--bg'), '--muted': cssVar(CSS_DARK, '--muted'),
    '--hair': cssVar(CSS_DARK, '--hair') }
};

/* Runs the page's own datumInk() over a palette of the test's choosing, the same
   way datumOpacityOn does -- and for the same reason. The mark is drawn inside
   the ghost layer's opacity now (#81), so what it is drawn IN is a colour rather
   than an alpha, and whether that colour lands on the tone the solve asked for
   is arithmetic no still and no solve can answer. */
function datumInkOn(tokens, theme) {
  const obj = new Function('rgbOf', 'contrastAt', 'getComputedStyle', 'document', 'console',
    'return {\n' + grabBlock('  datumInk() {', '{', '}') + ',\n'
    + grabBlock('  datumOpacity() {', '{', '}') + ',\n'
    + grabBlock('  ghostOpacity(theme) {', '{', '}') + '\n};')(
    colour.rgbOf, colour.contrastAt,
    () => ({ getPropertyValue: (k) => (tokens[k] === undefined ? '' : tokens[k]) }),
    { documentElement: {} }, { warn: () => {} });
  obj.state = { theme: theme };
  return { ink: obj.datumInk(), alpha: obj.datumOpacity(), ghost: obj.ghostOpacity(theme) };
}

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
    o: { x: 0, y: 0 }, alt: { x: 0, y: -20 }, stations: [], d0: 0, d1: 0 };
  const pw = 40, ph = 10, S = 1;
  const wide = { x0: -100, y0: -100, x1: 100, y1: 100 };
  const A = plateSeatOn(wide, r, S, pw, ph);
  eq(A.seat.side, 1, 'a plate with room on its own side is moved anyway');
  eq(A.seat.oy, 0, 'a plate with room on its own side does not stay on it');
  /* THE FIGURE IS MEASURED TO THE PLATE'S NEAR EDGE, from the start of the mark
     (#95). With the drawn area defaulted to the page, the mark starts where the
     page does, so the near edge lands exactly the stated figure inside it. */
  eq(A.seat.at, wide.x0 + page.PLATE_START_ALONG + pw / 2,
    'the plate is not seated ' + page.PLATE_START_ALONG + 'px in from the start of '
    + 'its line, measured to the edge of the plate');
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
  /* THE TWO STARTS, AND WHICH ONE WINS (#95). The mark starts where the drawing
     starts, and the page only takes over once the drawing starts outside it --
     which on the shipped composition is nearly always, because every escape run
     is grown until it is past the edge. Both directions are checked here, since
     an implementation that only ever took one of them would pass a test written
     against the case it takes. */
  const short_ = { x0: -50, y0: -100, x1: 50, y1: 100 };
  const E = plateSeatOn(wide, r, S, pw, ph, 0, short_);
  eq(E.seat.at, short_.x0 + page.PLATE_START_ALONG + pw / 2,
    'a mark that stops INSIDE the page is not what the plate is seated from — the '
    + 'plate stands off the edge of a page the line does not reach');
  const long_ = { x0: -500, y0: -500, x1: 500, y1: 500 };
  const F = plateSeatOn(wide, Object.assign({}, r, { d0: -300 }), S, pw, ph, 0, long_);
  eq(F.seat.at, wide.x0 + page.PLATE_START_ALONG + pw / 2,
    'a mark that starts off the page is seated from where it starts rather than '
    + 'from where the page can show it — which is a plate nobody can see');
  /* AND THAT IS WHAT ANSWERS GitHub #82. A chain with no leading escape run
     starts its
     mark at its own first gear, so every referent measured on the machine seats
     that plate within a wheel of the one wheel the chain owns. Against a mark
     that runs off the page, the plate clears it outright. */
  const ro = 30;
  ok(F.seat.at + pw / 2 < -ro,
    'the plate is seated over the head wheel of a chain whose mark starts there, '
    + 'which is GitHub #82 restated at ' + page.PLATE_START_ALONG + 'px');
  /* WHAT WINS ON A PAGE TOO NARROW TO HONOUR THE FIGURE: the seat. The figure is
     a preference and the interval in which the whole plate is on the page is
     not, so a page shorter along the run than the figure plus a plate pushes the
     plate BACK toward the start -- closer in than the stated distance rather
     than hung over the far edge. */
  const narrow = { x0: -100, y0: -100, x1: -40, y1: 100 };
  const C = plateSeatOn(narrow, r, S, pw, ph, 0, long_);
  eq(C.seat.side, 1, 'a plate that only needed sliding was mirrored instead');
  eq(C.seat.at, narrow.x1 - pw / 2 - C.pad.pad,
    'a page with no room for the stated distance does not give it up — the seat '
    + 'has to win, or the plate hangs off the far edge');
  ok(C.seat.at - pw / 2 - narrow.x0 < page.PLATE_START_ALONG,
    'the plate was slid the wrong way when the page could not honour the figure');
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
  /* ONE STRIKE, SINCE #115: the major at a station is all that is left to
     follow the side. Minor ticks -- the chain's own subdivision and the
     borrowed grid a one-station chain used to be scribed with -- were removed
     on the evidence (CL#121, GitHub #115); this count used to be three and is
     asserted at its new value so a tick strike cannot quietly reappear. */
  const ticks = DATUM_DRAW.match(/at\(d, [^)]*MAJOR\)/g) || [];
  eq(ticks.length, 1, 'expected exactly one tick strike in datumLayer, found ' + ticks.length);
  ticks.forEach(t => ok(/out \* MAJOR/.test(t),
    'a tick is struck at a fixed sign (' + t + '), so a mirrored datum draws its '
    + 'ticks into the wheels it is meant to clear'));
});

test('a plate gives way to the metal, even when that costs more slide', () => {
  /* GitHub #88, CL#108 (re-landed against the current mesh/ghost/flywheel
     code, after CL#108 itself was reverted for an unrelated render loop --
     see CHANGELOG). A plate that only ever chose the side with less slide
     could still choose a side a wheel sits on top of; this is the rule that
     stops it. */
  const r = { person: 'p', plate: 'P', ux: 1, uy: 0, nx: 0, ny: 1,
    o: { x: 0, y: 0 }, alt: { x: 0, y: -20 }, stations: [], d0: 0, d1: 0 };
  const pw = 40, ph = 10, S = 1;
  const wide = { x0: -100, y0: -100, x1: 100, y1: 100 };
  /* A wheel sitting exactly on the natural side's seat point (oy=0, at the
     figure's own distance in from the start), with the alternate side clear.
     Only the metal-clearance rule can move this seat -- the viewport alone
     has room on both sides, so a seat measured by slide/window fit picks the
     natural side every time. */
  const naturalAt = wide.x0 + page.PLATE_START_ALONG + pw / 2;
  const onNaturalSide = [{ x: naturalAt, y: 0, r: 5 }];
  const A = plateSeatOn(wide, r, S, pw, ph, 0, wide, onNaturalSide);
  eq(A.seat.side, -1, 'a plate stayed on a crowded side that costs it nothing '
    + 'in slide, over an alternate side that is clear');
  eq(A.seat.clean, true, 'the seat that was chosen still reports itself as crowded');
  /* WHEN NEITHER SIDE CLEARS ANYWHERE IN ITS WINDOW, THE ROOMIER ONE WINS AND
     IT WARNS -- the same shape of rule as a crossing bridge or overlapping
     chains: absent is worse than crowded, but crowded is reported, never
     hidden. A wheel this large excludes the whole finite window on its own
     side regardless of where the search would otherwise land -- the point is
     to prove the "genuinely nowhere clean" fallback still fires, which one
     small wheel no longer does now that plateSeat searches around it. */
  const onBothSides = [{ x: naturalAt, y: 0, r: 1000 }, { x: naturalAt, y: -20, r: 1000 }];
  const B = plateSeatOn(wide, r, S, pw, ph, 0, wide, onBothSides);
  eq(B.seat.clean, false, 'a plate crowded on both sides reports itself as clean');
  eq(B.warns.length, 1, 'a plate crowded on both sides warns about it');
  ok(/no uncrowded seat/.test(B.warns[0]), 'the warning does not say the seat is crowded');
  /* A CLEAN SEAT IS SILENT, exactly as it was before this rule existed --
     nothing about a plate that already had room to spare should start
     warning just because the metal it is compared against is now published. */
  const C = plateSeatOn(wide, r, S, pw, ph, 0, wide, []);
  eq(C.seat.clean, true, 'a plate with no metal to clear reports itself as crowded');
  eq(C.warns.length, 0, 'a plate with no metal nearby warns about crowding anyway');
});

test('the plate is stamped at the end of its mark furthest from the wordmark', () => {
  /* GitHub #131, CL#160, and the gap GitHub #138 was filed for: every OTHER plate
     test above runs with no measured wordmark, so all of them take plateSeat()'s
     fallback anchor -- the near end, which is what shipped before CL#160. Nothing
     in the suite could tell a derived far-end anchor from a hardcoded `+1`.

     THE ASSERTIONS ARE IN SCREEN x AND y, NOT ALONG THE RUN, and that is the whole
     shape of this test. "Right in landscape, top in portrait" over a direction
     that comes from _axisRot is a handedness, so its mirror image passes every
     measurement taken along the axis -- which is #67, and the bridge's own sign
     made the same mistake later (see CLAUDE.md). A seat reported as a distance
     along the run says nothing about which end of the page it landed on until the
     run's own direction is resolved back onto the screen, so that is what is
     compared here: the seat's screen point against the wordmark's.

     `seatXY` is that resolution and nothing more -- the origin the seat chose plus
     its distance along the run, which is where datumLayer draws it. */
  const seatXY = (s, run) => ({ x: s.ox + s.at * run.ux, y: s.oy + s.at * run.uy });
  const pw = 40, ph = 10, S = 1;
  const step = page.PLATE_START_ALONG + pw / 2;
  const vp = { x0: -100, y0: -100, x1: 100, y1: 100 };
  /* THE WORDMARK IS PINNED TO THE BOTTOM-LEFT CORNER in both orientations -- it is
     the same fixed furniture whichever way the stage has turned -- so one box
     serves both halves below, and the two answers have to differ because the RUN
     differs and for no other reason. */
  const brand = { x0: -95, y0: 78, x1: -55, y1: 95 };
  const brandC = { x: (brand.x0 + brand.x1) / 2, y: (brand.y0 + brand.y1) / 2 };
  /* LANDSCAPE: the mark runs +x, the wordmark is off its start, so the plate is
     stamped at the FINISH -- the stated figure in from the far end rather than the
     near one, measured to the plate's near edge exactly as it is at either end. */
  const land = { person: 'p', plate: 'P', ux: 1, uy: 0, nx: 0, ny: 1,
    o: { x: 0, y: 0 }, alt: { x: 0, y: -20 }, stations: [], d0: 0, d1: 0 };
  const A = plateSeatOn(vp, land, S, pw, ph, 0, vp, [], brand);
  eq(A.warns.length, 0, 'a plate seated at the far end of a page with room on both '
    + 'sides warns about it');
  eq(A.seat.at, vp.x1 - step, 'the plate is not seated ' + page.PLATE_START_ALONG
    + 'px in from the FINISH of its mark — a measured wordmark off the start of the '
    + 'run is the whole of what CL#160 added, and this is the near-end seat again');
  const a = seatXY(A.seat, land);
  ok(Math.abs(a.x - brandC.x) > Math.abs((vp.x0 + step) - brandC.x),
    'the plate landed nearer the wordmark in screen x than the other end of the '
    + 'same mark would have — the end furthest from it is the end it is stamped at');
  /* AND THE SAME MARK WITH NO WORDMARK MEASURED KEEPS THE OLD SEAT, so the two
     branches are asserted against each other rather than one being described. */
  eq(plateSeatOn(vp, land, S, pw, ph, 0, vp, []).seat.at, vp.x0 + step,
    'an unmeasured wordmark no longer stands in for the near end, which is the one '
    + 'frame of the page\'s life that has a viewport and no brand box');
  /* PORTRAIT DOES NOT FLIP, and this is the half worth pinning. The run is +y, so
     the mark's START already IS the top of the page and the wordmark at the bottom
     is furthest from it: `away` is negative and the anchor stays where it was. A
     rule written as "top in portrait" and a rule written as "furthest from the
     brand" agree here, which is exactly why the mirror image of this is invisible
     to anything measured along the run. */
  const port = { person: 'p', plate: 'P', ux: 0, uy: 1, nx: 1, ny: 0,
    o: { x: 0, y: 0 }, alt: { x: 20, y: 0 }, stations: [], d0: 0, d1: 0 };
  const B = plateSeatOn(vp, port, S, pw, ph, 0, vp, [], brand);
  eq(B.warns.length, 0, 'a portrait plate with room on both sides warns about it');
  const b = seatXY(B.seat, port);
  eq(b.y, vp.y0 + step, 'the portrait plate is not stamped ' + page.PLATE_START_ALONG
    + 'px down from the TOP of the page, in screen y');
  ok(b.y < (vp.y0 + vp.y1) / 2, 'the portrait plate is stamped in the bottom half of '
    + 'the page, which is the corner the wordmark is pinned to — the anchor flipped '
    + 'on an axis that never asked it to (#67)');
  ok(Math.abs(b.y - brandC.y) > Math.abs((vp.y1 - step) - brandC.y),
    'the portrait plate is nearer the wordmark than the other end of its own mark');
  /* AND IT IS THE MEASURED BRAND THAT DECIDES, NOT THE ORIENTATION: move the same
     wordmark to the TOP-left and the same portrait run must stamp at the bottom.
     Nothing else in the call changes, so an implementation that read _axisRot, or
     the sign of `uy`, or anything but the box, cannot pass both this and the one
     above. */
  const high = { x0: -95, y0: -95, x1: -55, y1: -78 };
  const C = plateSeatOn(vp, port, S, pw, ph, 0, vp, [], high);
  eq(seatXY(C.seat, port).y, vp.y1 - step,
    'a wordmark measured at the top of the page does not move the plate to the '
    + 'bottom of the same mark — the end is being chosen by the orientation rather '
    + 'than by where the brand actually is');
  /* THE INTERACTION (CL#152 at the far anchor): a far-end seat that is also
     crowded must still SLIDE. The clearance search and the anchor choice are
     independent, and a search that only ever ran from the near end would leave the
     far-end plate sitting on the metal -- which is the failure #88 was, arriving
     at the other end of the mark.

     A wheel on the far-end seat point of EACH side, so neither side is clean where
     it wants to sit and both must slide the same distance: the natural side then
     keeps the seat on the strict tie, exactly as it does at the near anchor, and
     what is being measured is the slide rather than the choice of side. */
  const want = vp.x1 - step;
  const both = [{ x: want, y: 0, r: 5 }, { x: want, y: -20, r: 5 }];
  const D = plateSeatOn(vp, land, S, pw, ph, 0, vp, both, brand);
  eq(D.seat.clean, true, 'a far-end plate with clear page either side of the metal '
    + 'reports itself crowded — the interval search does not run at this anchor');
  eq(D.warns.length, 0, 'a far-end plate that found a clean seat warns about it');
  ok(D.seat.at !== want, 'the far-end plate stayed on top of the wheel sitting at '
    + 'its seat point, so CL#152\'s search runs at one anchor only');
  const d = seatXY(D.seat, land);
  ok(Math.abs(d.x - (vp.x1 - step)) < Math.abs(d.x - (vp.x0 + step)),
    'a crowded far-end plate slid all the way back to the near end of its mark '
    + 'instead of stepping clear of the metal — the slide is a nudge, not a '
    + 'change of anchor');
  /* AND THE SAME CROWDING AT THE NEAR ANCHOR STILL SLIDES, which is what makes the
     claim "at either anchor" rather than "at the far one too". */
  const near = vp.x0 + step;
  const E = plateSeatOn(vp, land, S, pw, ph, 0, vp,
    [{ x: near, y: 0, r: 5 }, { x: near, y: -20, r: 5 }]);
  eq(E.seat.clean, true, 'a near-end plate with clear page either side of the metal '
    + 'reports itself crowded');
  ok(E.seat.at !== near, 'the near-end plate no longer slides off the metal at all');
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

test('a datum spans its chain\'s ghosts, and no chain seats its plate on a wheel', () => {
  /* RULE 1 stands: the run off the trailing edge is part of the machine the line
     references, so the line goes where it goes.

     RULE 3 IS GONE (#95, GitHub #87). The plate used to sit alongside the last
     LEADING
     ghost, and a chain with no leading run -- which is every driven chain, since
     that is the end its bridge arrives at -- fell back to its own head wheel.
     That fallback is GitHub #82, and on a one-wheel chain the wheel it landed
     on was
     the whole chain. The seat is measured from the start of the MARK now, so
     there is no wheel in it to fall back to and no branch to take, and this
     asserts the two halves of that: nothing about a wheel survives in the run,
     and the seat a chain with no leading run gets is the same seat, arrived at
     by the same arithmetic, as the spine's.

     A HORIZONTAL RUN FOR THE SEAT, so the start of the page along the line is
     just its left edge measured from the origin, and the assertion does not need
     a second copy of the clip to state what it expects. */
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
    /* NO WHEEL ANCHOR IS PUBLISHED AT ALL. A run that still carried one would let
       the old rule creep back into the seat without a single assertion moving. */
    runs.forEach(x => {
      if ('plateAt' in x)
        bad.push(`rot ${rot}: ${x.person}'s run still publishes a wheel anchor for `
          + 'the plate to ride');
    });
    if (/\.lead\b/.test(DATUM_SRC))
      bad.push('the datum still picks a leading ghost to seat its plate on');
  });
  ok(!/plateAt/.test(SRC), 'index.html still names a plate anchor taken off a wheel');
  /* AND THE SEAT ITSELF, for a chain with a leading run and a chain without: same
     distance in from the start of the page along their own lines, and both clear
     of the wheel the old rule would have put them on. Only rot 0 -- the seat is
     asserted against a horizontal run on purpose (see above). */
  const { solved, order } = runSolve(THREE, { axisRot: 0 });
  const sites = seatSlugs(solved);
  const spineSlug = order[0].slug;
  const axes = chainAxesOf(solved, 0, spineSlug);
  const spine = axes.find(c => c.spine);
  const step = spine.head.ro * 3;
  /* A leading run for the spine and nothing for anybody else, which is the
     asymmetry fitEscapes actually deals. */
  const ghosts = [0, 1].map(k => ({ person: spineSlug, lead: true, k: k,
    cx: spine.head.cx - step * (k + 1), cy: spine.head.cy }));
  const runs = datumRunsOn(solved, 0, spineSlug, ghosts, sites);
  /* A PAGE INSIDE THE DRAWN AREA, so the mark starts off it -- which is the
     shipped case, and the only one under which GitHub #82 is answered: a plate
     can only
     stand clear of the wheels on a page that shows some line before the machine
     starts. It does. The stage box is the LINKED wheels alone and the fit centres
     it, so the escape runs and the empty line either side of them are what the
     rest of the page carries: measured at 2560x1440, the spine's datum origin --
     its first linked wheel -- sat 832 rendered px in from the near edge of the
     page. Half the train's width is the same relationship in solve units. */
  const vp = { x0: -solved.w * 0.5, y0: -4000, x1: solved.w + 40, y1: solved.h + 4000 };
  const drawn = { x0: -9000, y0: -9000, x1: 9000, y1: 9000 };
  const pw = 60, ph = 20;
  runs.forEach(x => {
    const c = axes.find(a => a.person === x.person);
    const seat = plateSeatOn(vp, x, 1, pw, ph, 0, drawn).seat;
    const want = (vp.x0 - seat.ox) + page.PLATE_START_ALONG + pw / 2;
    if (Math.abs(seat.at - want) > 1e-9)
      bad.push(`${x.person}${c.spine ? ' (spine)' : ''} seats its plate at `
        + `${seat.at.toFixed(1)}, not ${want.toFixed(1)} — ${page.PLATE_START_ALONG}px `
        + 'in from the start of its own mark');
    const head = (c.head.cx - x.o.x) * x.ux + (c.head.cy - x.o.y) * x.uy;
    if (seat.at + pw / 2 > head - c.head.ro)
      bad.push(`${x.person}'s plate reaches back over its own head wheel, which is `
        + 'the seat GitHub #82 reported');
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
  /* RULE 6: one mark, beneath EVERY wheel — and BENEATH now has to mean covered,
     not merely earlier. Painted per chain, the following chain's ghost run
     buries the previous chain's plate, which is what the mock did first; painted
     as a SIBLING of the ghost layer, it is below all 24 of them in paint order
     and still shows straight through every one, because an occluder composited
     at 0.17 occludes nothing (#81). The arrangement that holds is: the mark
     inside the layer that carries the ghost opacity, first child, so the wheels
     paint over it at full alpha and the assembly is dimmed once. */
  const art = SRC.slice(SRC.indexOf('const gearArt = h(\'div\''));
  ok(!/this\.datumLayer\(/.test(art),
    'the datum is emitted beside the ghost layer rather than inside it, where a '
    + 'wheel drawn at the ghost alpha cannot cover it');
  ok(art.indexOf('ghosts,') > 0 && art.indexOf('ghosts,') < art.indexOf("key: 'shadows'"),
    'the ghost layer is not the first thing the stage paints, so the mark it '
    + 'carries is no longer beneath the machine');
  const layer = SRC.slice(SRC.indexOf('const ghosts = h(\'div\', { key: \'ghosts\''),
    SRC.indexOf('const gearArt = h(\'div\''));
  ok(/opacity: this\.ghostOpacity\(\)/.test(layer),
    'the ghost layer no longer carries the ghost opacity, so nothing says what '
    + 'alpha the datum inside it is being drawn at');
  ok(layer.indexOf('datum.el') > 0 && layer.indexOf('datum.el') < layer.indexOf('wheels)'),
    'the datum is not the first child of the ghost layer, so a background wheel '
    + 'is painted under the mark that is supposed to be a reference for it');
  /* The double-dim trap: inside the layer, an opacity of its own would charge
     the dimming twice and the scribe would be gone. */
  ok(!/opacity:/.test(DATUM_DRAW),
    'the datum svg still carries an opacity of its own on top of the ghost '
    + 'layer\'s, which dims the scribe twice');
  /* RULE 5: tokens, never invented greys. Still true, one step removed — the
     colours are LIFTED from the tokens by datumInk() so that drawing them at the
     ghost alpha lands on the tone datumOpacity() solved for. */
  /* A HASH IS ONLY A COLOUR WHEN IT IS A STRING. The bare pattern was
     `#[0-9A-Fa-f]{3,6}`, and every three-digit decimal number is three hex
     digits -- so from CHANGELOG entry 100 onward this test forbade the one
     method it guards from CITING the entry that changed it, which is a rule that
     would have been broken by writing a comment. A literal colour reaches the
     drawing as a quoted string or through rgb(); a citation never does. */
  ok(!/['"`]\s*#[0-9A-Fa-f]{3,8}\b|rgb\(/.test(DATUM_DRAW),
    'the datum draws itself in a literal colour instead of one derived from '
    + '--muted and --hair');
  ok(/this\.datumInk\(\)/.test(DATUM_DRAW),
    'the datum does not take its scribe and plate colours from datumInk()');
  ok(/--muted/.test(DATUM_INK) && /--hair/.test(DATUM_INK) && /--bg/.test(DATUM_INK),
    'the datum ink is not derived from the theme tokens it is supposed to match');
  ok(/this\.datumOpacity\(\) \/ this\.ghostOpacity\(\)/.test(DATUM_INK),
    'the lift is a number of its own rather than the ratio of the two alphas it '
    + 'exists to convert between — which is a constant nobody will re-measure');
  /* THE CONVERSION IS EXACT, in both palettes, and this is the whole claim of
     the fix: the ink drawn at the ghost alpha must composite to the same tone
     the token reaches at the alpha datumOpacity() solved for. Off by more than
     sRGB rounding and the mark has quietly changed weight. */
  ['light', 'dark'].forEach(theme => {
    const r = datumInkOn(TOKENS[theme], theme);
    const bg = colour.rgbOf(TOKENS[theme]['--bg']);
    [['line', '--muted'], ['plate', '--hair']].forEach(pair => {
      const got = colour.rgbOf(r.ink[pair[0]]);
      ok(got, theme + ': datumInk did not return a colour for ' + pair[1]
        + ' from a palette that declares it');
      const token = colour.rgbOf(TOKENS[theme][pair[1]]);
      got.forEach((v, i) => {
        const drawn = bg[i] + (v - bg[i]) * r.ghost;
        const want = bg[i] + (token[i] - bg[i]) * r.alpha;
        ok(Math.abs(drawn - want) <= 1,
          theme + ': ' + pair[1] + ' channel ' + i + ' composites to '
          + drawn.toFixed(1) + ' at the ghost alpha, not the ' + want.toFixed(1)
          + ' the solved alpha asks for — the mark changed weight when it moved '
          + 'inside the layer');
      });
    });
  });
  /* AND THE WAY OUT IS STILL VISIBLE. With no palette to read there is nothing
     to lift, so the line must fall back to a token that contrasts with the page
     by construction rather than to one that vanishes at the ghost alpha. */
  const blind = datumInkOn({}, 'dark').ink;
  ok(blind.line === 'var(--ink)',
    'a datum that cannot read its palette falls back to ' + blind.line
    + ' — at the ghost alpha the scribe has to be drawn in the page\'s own '
    + 'foreground or it is indistinguishable from not being there');
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
  ok(/--bg:\s*var\(--ref-bg\)/.test(CSS_ROOT) && !/--muted:\s*var\(--ref-muted\)/.test(CSS_ROOT),
    'the light --bg no longer aliases --ref-bg, or --muted aliases --ref-muted '
    + 'again (GitHub #152) — the light GROUND is one fact and may alias, the light '
    + 'INK is two and may not: one hex cannot be both the ink a WCAG ratio binds '
    + "and the weight the datum was judged at, and re-aliasing restores the cap "
    + 'that made #120\'s candidates unshippable');
/* THE INK-ON-ACCENT RULE IS HELD TO ITS OWN FLOORS, FOR EVERY ACCENT (GitHub #153).
   The ticket's own constraint was that "a fix that cannot be shown to hold for the
   other four accents just moves the latency" -- and a11y_audit cannot meet it: it
   renders ONE accent, the one the schema ships, so four of the five are unreachable
   to it. This test is the other four, and it needs no browser: inkOnAccent() is pure
   arithmetic over colours, so it is extracted out of index.html and run directly,
   the same way this suite already treats the geometry.

   HYPOTHETICALS TOO, and that is the point of a derived rule rather than a table of
   five. A table passes today and says nothing about a sixth accent; a rule can be
   asserted over colours nobody has chosen yet. The claim it rests on is arithmetic:
   pure black and pure white contrast equally at ground luminance 0.1791, both at
   4.58:1, so the better of the two poles is never worse than 4.58 against ANY colour
   -- which clears both 4.5 and 3 unconditionally. If that ever fails here, the rule
   is broken rather than the accent unlucky. */
test('the ink on an accent clears its WCAG floor for every accent, in both themes', () => {
  const src = grabBlock('function rgbOf(', '{', '}') + '\n'
    + grabBlock('function relLum(', '{', '}') + '\n'
    + grabBlock('function contrastAt(', '{', '}') + '\n'
    + grabBlock('function inkOnAccent(', '{', '}') + '\n'
    + 'return { inkOnAccent, contrastAt, rgbOf };';
  const F = new Function(src)();
  const TEXT = grabNumber('WCAG_TEXT_CONTRAST');
  const NONTEXT = grabNumber('WCAG_NONTEXT_CONTRAST');
  ok(TEXT === 4.5 && NONTEXT === 3,
    'the WCAG floors moved: 1.4.3 wants 4.5 for normal-size text and 1.4.11 wants '
    + '3 for a non-text component, and this test asserts against the page\'s own '
    + 'constants so it cannot drift from them');

  /* The five reachable accents are config.js's ACCENTS map: light value -> its dark
     counterpart. BOTH sides are real accents that get painted, so both are swept --
     the dark column is not decoration, it is what --accent becomes in dark mode. */
  const accents = [];
  for (const [lightVal, darkVal] of Object.entries(loadConfig().ACCENTS || {})) {
    accents.push(['light', lightVal], ['dark', darkVal]);
  }
  ok(accents.length >= 10,
    'config.js ACCENTS no longer carries the five accents this sweep was written '
    + 'against — the sweep is now narrower than the page');

  /* Hypothetical accents on a coarse RGB lattice: a rule has to answer for colours
     nobody has picked, which is the whole reason it is a rule. */
  for (let r = 0; r <= 255; r += 51)
    for (let g = 0; g <= 255; g += 51)
      for (let b = 0; b <= 255; b += 51)
        accents.push(['hypothetical', 'rgb(' + r + ',' + g + ',' + b + ')']);

  for (const floor of [TEXT, NONTEXT]) {
    for (const [theme, accent] of accents) {
      const toks = theme === 'dark'
        ? [{ name: '--chip', value: cssVar(CSS_DARK, '--chip') },
           { name: '--ink', value: cssVar(CSS_DARK, '--ink') }]
        : [{ name: '--chip', value: cssVar(CSS_ROOT, '--chip') },
           { name: '--ink', value: cssVar(CSS_ROOT, '--ink') }];
      const ink = F.inkOnAccent(accent, toks, floor);
      ok(ink !== null,
        'inkOnAccent returned nothing for ' + accent + ' at floor ' + floor
        + ' — the caller then keeps the token it shipped with, which is the bet '
        + 'this rule exists to remove');
      /* Resolve the answer the way the page would: a var() reference is one of the
         tokens handed in, anything else is a literal colour. */
      const m = /^var\((--[\w-]+)\)$/.exec(ink);
      const resolved = m ? (toks.find(t => t.name === m[1]) || {}).value : ink;
      const got = F.contrastAt(F.rgbOf(resolved), F.rgbOf(accent), 1);
      ok(got >= floor,
        'ink ' + ink + ' on ' + theme + ' accent ' + accent + ' measures '
        + got.toFixed(3) + ':1 against a floor of ' + floor
        + ' — the derived rule does not actually reach its own floor, so the '
        + 'bisection or the pole choice is wrong');
    }
  }
});

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
  const conf = loadConfig();
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
  /* THE WHOLE EXPRESSION, NOT ONE LINE OF IT (CL#110). This used to anchor on the
     literal `const fit = Math.max(0.28`, which was the entire computation while
     the four terms were arguments to a min() written inline. They are named
     locals now, so the min's operands live on the four lines above the `fit`
     line and a one-line slice would read as though the cross-axis guard had
     been deleted -- a false FAIL, and worse, a test that could stop seeing a
     ceiling re-added to a term instead of to the result. The same two ends the
     fit builder at the top of this file uses: WHEEL_CROSS_MAX opens the block,
     the --gsfit write closes it. */
  const i = SRC.indexOf('const WHEEL_CROSS_MAX =');
  const j = SRC.indexOf('const root = document.documentElement.style;', i);
  ok(i > 0 && j > i, 'could not find the fit computation');
  const line = SRC.slice(i, j);
  ok(/const fit = Math\.max\(/.test(line), 'the fit is no longer a floored minimum');
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

test('the epicyclic hub badge scales across the whole tooth range, and never plateaus', () => {
  /* CL#116 / GitHub #94. `discF` used to fork on `epicyclic` too (0.38 vs 0.72),
     on top of the shrink `capF` already does -- and 0.38 * g.r landed under
     `disc`'s own solve-unit floor of 30 for every wheel this page has ever
     dealt (g.r runs MODULE * TEETH_MIN/2 .. MODULE * TEETH_MAX/2, i.e.
     45.5..66.5, so g.r * 0.38 was 17.3..25.3 -- always short, at every scale,
     because the floor bound BEFORE `S` scaled the value in). `disc` therefore
     came out exactly 30 regardless of teeth, and the rendered badge tracked
     `cap` alone -- until `cap` itself passed 30 at 16 teeth, at which point
     the pinned `disc * S` became the smaller, size-deciding term and the
     badge stopped moving for the rest of the range (16-19 teeth all drew at
     the same size). A single tooth count cannot see a threshold in the
     middle of a range; this sweeps every tooth count the page can deal. */
  const badgeSize = new Function('g', 'S',
    SRC.slice(SRC.indexOf('const epicyclic = g.kind ==='),
      SRC.indexOf(';', SRC.indexOf('const size = Math.min(cap * S')) + 1)
    + ' return size;');

  /* S = 1.3 is the scale #64's own measured table (reproduced in the issue)
     used to catch the plateau -- reused here rather than re-derived, since
     the point is to see what a real render scale exposes, not to invent one. */
  const S = 1.3;
  const sizes = [];
  for (let t = page.TEETH_MIN; t <= page.TEETH_MAX; t++) {
    sizes.push(badgeSize({ kind: 'planetary', r: page.MODULE * t / 2 }, S));
  }

  const flat = [];
  for (let i = 1; i < sizes.length; i++) {
    if (sizes[i] <= sizes[i - 1]) {
      flat.push((page.TEETH_MIN + i - 1) + '->' + (page.TEETH_MIN + i) + ' teeth: '
        + sizes[i - 1].toFixed(1) + 'px -> ' + sizes[i].toFixed(1) + 'px');
    }
  }
  ok(flat.length === 0, 'the epicyclic badge stops scaling at ' + flat.join(', ')
    + ' -- full sweep ' + page.TEETH_MIN + '..' + page.TEETH_MAX + ' teeth: '
    + sizes.map(s => s.toFixed(1)).join(', '));
});

test('no sunburst window falls below its own legibility floor, on the smallest blank', () => {
  /* GitHub #96 / CL#117. The sunburst branch of gearSvg used to deal its window
     count straight from the variant (10/14/18 arms) with no regard for how much
     room the wheel actually has. On the smallest blank the deal can produce (13
     teeth) an 18-arm deal cut a window measured at 0.78 rendered px on a real
     phone (#64's finding A8) -- an aliasing artefact, not an opening.

     THE FIX'S OWN ARITHMETIC RUNS HERE, pulled out of gearSvg verbatim rather
     than modelled: the px() floor, the asin() inversion that turns it into a
     window-count ceiling, and the min() against the dealt variant. A copy of
     the formula would keep passing if the shipped code diverged from it; this
     fails exactly when the shipped code does. */
  const famDecl = "{ type: 'sunburst', web: 3.1, hub: 0.2,";
  const famBlock = grabBlockFrom(SRC, 'index.html', famDecl, '{', '}');
  const hub = +((famBlock.match(/hub:\s*([0-9.]+)/) || [])[1]);
  const web = +((famBlock.match(/web:\s*([0-9.]+)/) || [])[1]);
  const dealtArms = [...famBlock.matchAll(/arms:\s*([0-9]+)/g)].map(m => +m[1]);
  ok(hub > 0 && web > 0 && dealtArms.length >= 3,
    'could not read the sunburst family entry out of CENTRE_FAMILIES -- the extraction is broken, not the page');

  const fn = new Function('hubR', 'wellR', 'g', 'S',
    'const BOSS_MUL = ' + grabNumber('BOSS_MUL') + ';\n'
    + grabDecl('const px = (want, lo, hi) =>') + '\n'
    + grabDecl('const rInR = Math.max(hubR * BOSS_MUL, 9)') + '\n'
    + grabDecl('const winMin =') + '\n'
    + grabDecl('const maxLegible =') + '\n'
    + grabDecl('const nR =') + '\n'
    + grabDecl('const wi = (360 / nR) * 0.16') + '\n'
    + 'return { nR: nR, rInR: rInR, winMin: winMin, wi: wi };');

  /* The same worst-case scale the legibility-floors test above derives -- the S
     below which gearSvg's own rendered-pixel intents stop being satisfiable --
     reused rather than re-picked, so the two tests cannot disagree about which
     viewport is the hard one. */
  const intents = [...grabBlock('gearSvg(g, S) {', '{', '}')
    .matchAll(/\bpx\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)/g)]
    .map(m => ({ want: +m[1], hi: +m[3] }));
  const S_WORST = Math.max(...intents.map(p => p.want / p.hi));

  const bad = [];
  for (let teeth = page.TEETH_MIN; teeth <= page.TEETH_MAX; teeth++) {
    const r = page.MODULE * teeth / 2;
    const hubR = Math.max(8, r * hub);
    const wellR = Math.max(4, r - page.MODULE * web);
    dealtArms.forEach(dealt => {
      const out = fn(hubR, wellR, { arms: dealt }, S_WORST);
      const widthSolve = 2 * out.rInR * Math.sin(out.wi * Math.PI / 180);
      if (widthSolve < out.winMin - 1e-9) {
        bad.push(`${teeth}-tooth blank, ${dealt}-arm deal at S=${S_WORST.toFixed(2)}: `
          + `nR=${out.nR} cuts a window ${(widthSolve * S_WORST).toFixed(2)}px wide `
          + `(${widthSolve.toFixed(2)} solve units), under the ${out.winMin.toFixed(2)}-unit `
          + `floor the same code just derived -- the count is not honouring its own ceiling`);
      }
    });
  }
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
  /* engraving() sets the handle at MODULE * ENGRAVE_SIZES.handle -- read out
     of the page (GitHub #102), not retyped. */
  const textModules = ENGRAVE_SIZES.handle;
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
  [['handle', ENGRAVE_SIZES.handle], ['stamp', ENGRAVE_SIZES.stamp]].forEach(([which, textModules]) => {
    const shift = page.BASELINE_MID * textModules;
    ok(shift < halfBand,
      which + ' ring is dropped ' + shift.toFixed(3) + 'm, past the band half-depth '
      + halfBand.toFixed(3) + 'm -- the arc would sit outside its own band');
  });
  ok(page.BASELINE_MID > 0 && page.BASELINE_MID < 0.5,
    'BASELINE_MID ' + page.BASELINE_MID + ' is not a plausible ascent-over-descent middle');
});

test('the engraving cap is a clear-metal length, not a fixed angle (GitHub #98)', () => {
  /* STRUCTURAL, and cheap: catches an outright revert -- someone typing a fixed
     degree cap back into fit() -- with a message that names the actual
     regression, before the slower geometric test below ever runs. */
  const fitSrc = grabBlockFrom(SRC, 'index.html', 'const fit = (txt, rr, base) => {', '{', '}');
  ok(/const MAX = .*\brr\b/.test(fitSrc),
    'MAX no longer depends on rr -- the sweep cap is a fixed angle again (#64, GitHub #98)');
  ok(!/\b168\b/.test(fitSrc), 'a literal 168-degree cap is back in fit() (GitHub #98)');
  const engSrc = grabBlockFrom(SRC, 'index.html', 'engraving(g, r, m, bandOut) {', '{', '}');
  ok(/this\.textWidth\(/.test(engSrc),
    'engraving() no longer calls textWidth() -- the per-character guess may be back (GitHub #98)');
  ok(!/\bper\s*\*\s*fs\b|\bfs\s*\*\s*\(per\b/.test(engSrc),
    'a per-character width guess (per + track) is back in engraving() (GitHub #98)');
});

test('the engraving cap holds the same clear metal on every wheel size and label length (GitHub #98, #64)', () => {
  /* engraving() ITSELF is executed here, out of index.html, rather than a model
     of its algebra -- the earlier test above only proves the source text still
     mentions rr and textWidth(); this proves the method actually behaves, which
     a hand-modelled copy of the formula could not: it would agree with a broken
     page as readily as a working one.

     textWidth() is stubbed because Node has no canvas, but the stub only needs
     to be monotonic in font size and string length for this test to mean
     anything -- what is under test is the CAP fit() enforces algebraically once
     emWidth() returns any positive, well-behaved number; GitHub #98's actual fix (a
     canvas measurement replacing a per-character guess) is what FEEDS the cap,
     and is covered by the structural test above and by dom_invariants.py's
     rendered-DOM check, neither of which this one repeats. */
  const textWidthStub = (text, font) => {
    const sizePx = parseFloat((/(\d+(?:\.\d+)?)px/.exec(font) || [0, 16])[1]);
    return Math.ceil(text.length * sizePx * 0.55);
  };
  const SITES_STUB = { p: { x: { path: '' } } };
  const buildEngraving = new Function('SITES', 'MODULE', 'BAND_DEPTH', 'BASELINE_MID', '__tw',
    grabDecl('const ENGRAVE_GAP =') + '\n'
    + grabDecl('const ENGRAVE_FONT_FAMILY =') + '\n'
    + grabDecl('const ENGRAVE_FONT_WEIGHT =') + '\n'
    + grabDecl('const ENGRAVE_TRACK =') + '\n'
    + grabDecl('const ENGRAVE_TW_REF =') + '\n'
    + 'const obj = { textWidth: __tw, '
    + grabBlockFrom(SRC, 'index.html', 'engraving(g, r, m, bandOut) {', '{', '}') + ' };\n'
    + 'return function (g, r, m, bandOut) { return obj.engraving(g, r, m, bandOut); };');
  const engraving = buildEngraving(SITES_STUB, page.MODULE, page.BAND_DEPTH, page.BASELINE_MID, textWidthStub);

  const m = page.MODULE;
  const geom = (teeth) => {
    const r = m * teeth / 2, bandOut = r - m * page.BAND_RISE;
    return { r, bandOut, g: { slug: 'x', person: 'p', teeth, kind: 'spur' } };
  };
  const teethRange = [];
  for (let t = page.TEETH_MIN; t <= page.TEETH_MAX; t++) teethRange.push(t);

  /* Find a label long enough to force the shrink at the LARGEST wheel (the
     hardest to force -- most circumference to fill) while staying above
     MIN_ENGRAVE at the SMALLEST wheel (the easiest to floor out -- least
     circumference to spend). If no such length exists in a generous search
     range the test fails honestly rather than silently passing on a label that
     never actually engaged the cap anywhere. */
  let L = -1;
  for (let len = 4; len <= 200; len++) {
    SITES_STUB.p.x.path = 'w'.repeat(len);
    const atMax = engraving(geom(page.TEETH_MAX).g, geom(page.TEETH_MAX).r, m, geom(page.TEETH_MAX).bandOut);
    const atMin = engraving(geom(page.TEETH_MIN).g, geom(page.TEETH_MIN).r, m, geom(page.TEETH_MIN).bandOut);
    if (atMax.fT < m * 0.80 - 1e-9 && atMin.fT > m * 0.30 + 1e-6) { L = len; break; }
  }
  ok(L > 0, 'could not find a label length that engages the cap at every wheel size '
    + 'without flooring out at the smallest -- the search range may need widening');

  SITES_STUB.p.x.path = 'w'.repeat(L);
  const gaps = teethRange.map(teeth => {
    const { r, bandOut, g } = geom(teeth);
    const eng = engraving(g, r, m, bandOut);
    ok(eng.fT < m * 0.80 - 1e-9,
      teeth + '-tooth wheel: the cap did not engage at label length ' + L
      + ' (fT ' + eng.fT.toFixed(3) + ') -- the search above picked a bad length');
    /* The clear metal is what the cap actually leaves behind on ONE side,
       measured back out of the wheel's own returned radius and sweep rather
       than re-derived from the formula under test. */
    return { teeth, gap: eng.rT * (Math.PI - eng.sT * Math.PI / 180) };
  });
  const expected = page.ENGRAVE_GAP * m;
  const bad = gaps.filter(x => Math.abs(x.gap - expected) > 1e-6 * Math.max(1, expected));
  ok(bad.length === 0, 'clear metal is not constant across the tooth range at label length ' + L
    + ' (expected ' + expected.toFixed(4) + ' every time): '
    + bad.map(x => x.teeth + '-tooth ' + x.gap.toFixed(4)).join(', '));

  /* SAME INVARIANT, EVERY LABEL LENGTH THE CONFIG CAN ACTUALLY PRODUCE, at both
     ends of the tooth range -- a fixed-angle bug hides at a single size, so it
     is not enough to check one wheel. This does not require the cap to engage
     (most shipped handles are short enough that it never does); it only
     requires that the sweep NEVER exceeds the budget the derived cap allows. */
  const realHandles = ['csmarshall', 'cs_marshall', 'charles.wozi.com', 'charles@wozi.com',
    'harper', 'a', ''];
  [page.TEETH_MIN, page.TEETH_MAX].forEach(teeth => {
    const { r, bandOut, g } = geom(teeth);
    realHandles.concat(['w'.repeat(1), 'w'.repeat(60), 'w'.repeat(200)]).forEach(h => {
      SITES_STUB.p.x.path = h;
      const eng = engraving(g, r, m, bandOut);
      const rr = eng.rT, maxDeg = (Math.PI - (page.ENGRAVE_GAP * m) / rr) * 180 / Math.PI;
      ok(eng.sT <= maxDeg + 1e-6,
        teeth + '-tooth wheel, handle ' + JSON.stringify(h) + ': sweep ' + eng.sT.toFixed(2)
        + 'deg exceeds the derived cap ' + maxDeg.toFixed(2) + 'deg');
    });
  });

  /* THE #59 FLOOR BEHAVIOUR SURVIVES: a label long enough to hit MIN_ENGRAVE
     truncates with an ellipsis rather than smearing past the sweep budget,
     the same shape the guess-based version produced. */
  const longest = geom(page.TEETH_MIN);
  SITES_STUB.p.x.path = 'w'.repeat(200);
  const flooredEng = engraving(longest.g, longest.r, m, longest.bandOut);
  ok(Math.abs(flooredEng.fT - m * 0.30) < 1e-9,
    'a 200-character handle on the smallest wheel does not floor at MIN_ENGRAVE -- '
    + 'got fT ' + flooredEng.fT.toFixed(3));
  ok(flooredEng.handle.endsWith('…') && flooredEng.handle.length < 200,
    'a 200-character handle at the floor size was not truncated with an ellipsis: '
    + JSON.stringify(flooredEng.handle));
  const rrFloor = flooredEng.rT, maxDegFloor = (Math.PI - (page.ENGRAVE_GAP * m) / rrFloor) * 180 / Math.PI;
  ok(flooredEng.sT <= maxDegFloor + 1e-6,
    'the truncated handle still overruns the sweep budget: ' + flooredEng.sT.toFixed(2)
    + 'deg against ' + maxDegFloor.toFixed(2) + 'deg');
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
  const conf = loadConfig();
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

test('the bearing deal keeps the train a horizontal line, at a real rate', () => {
  /* Swept over every chain length a page could carry, not just the ones shipped:
     the caps are applied PER CHAIN now, so a length that cannot satisfy them
     leaves that chain's wheels on the deal's fallback draw rather than on a
     legal one -- and until endsCapFor existed, a two-wheel chain was exactly
     such a length and the deal assigned no bearings at all.

     THE GATE USED TO BE "at least one legal draw in 2000" (GitHub #97). That
     passes just as happily at a 0.05% legal rate as at 99% -- every load but
     one in two thousand landing on the closest-draw fallback reads as green --
     so it could not have told anyone the flat BAND_MAX/ENDS_MAX literals this
     test used to check were starving some chain lengths (CL#130 found 9.7% on
     an 8-wheel chain at the old 62/26, purely from step-count parity: see the
     comment at BAND_MAX in index.html). Given the RATE_FLOOR treatment
     'the tooth deal always produces a legal train' already has, for the same
     reason: a presence check cannot fail for a weak deal, only an absent one. */
  const { ANG_MIN, ANG_MAX, BAND_MAX, TEETH_MIN, TEETH_MAX } = page;
  ok(ANG_MIN > 0 && ANG_MAX > ANG_MIN, 'bearing range is degenerate');
  ok(ANG_MAX <= 45, 'bearings past 45 degrees stack the wheels diagonally');

  /* rOf() is EXECUTED straight out of dealAngles() rather than modelled (GitHub
     #102). A fixed `MODULE * 16` stand-in for rOf(parent) + rOf(child) measured
     6 points optimistic against the page (#64, A13): TEETH_MEAN is 16.3, not
     16, and -- more to the point -- the wheels feeding this drift are DEALT
     per wheel from [TEETH_MIN, TEETH_MAX], not nominal, so a real step's radius
     sum can be as wide as two TEETH_MAX blanks or as narrow as two TEETH_MIN
     ones. Modelling it as one fixed pair understates the spread the actual
     deal can produce. */
  const rOf = new Function('MODULE', grabDecl('const rOf =') + ' return rOf;')(page.MODULE);

  /* Not a re-tuned number: the derived BAND_MAX/ENDS_MAX (CL#130) measure at
     84-100% legal across every swept length (worst case an 8-wheel chain,
     step-count parity again -- the caps did not remove that effect, only how
     punishing it is). RATE_FLOOR sits well under that floor and well over what
     the old flat 62/26 produced (9.7% worst case), so it passes the bounds
     this ticket derives with room to spare and would have failed the ones it
     replaced -- see CL#130 for the measured before/after. CL#130 measured that
     against a modelled rOf; this test now executes the page's own, so treat the
     stated percentages as the ticket's figures rather than as this file's. */
  const RATE_FLOOR = 0.5;
  const TRIALS = 4000;
  const bad = [];
  const lens = [...new Set([...page.TRAIN_LENS, 1, 2, 3, 4, 5, 6, 7, 8, 9])];
  lens.forEach((len) => {
    let legal = 0;
    for (let trial = 0; trial < TRIALS; trial++) {
      const first = Math.random() < 0.5 ? 1 : -1;
      const ang = [0];
      for (let i = 1; i < len; i++) ang.push(first * (i % 2 ? 1 : -1) * (ANG_MIN + Math.random() * (ANG_MAX - ANG_MIN)));
      /* One tooth count DEALT per wheel, uniform over the same [TEETH_MIN,
         TEETH_MAX] range dealTeeth() draws each wheel from -- not a nominal
         average -- so a step's radius sum is exactly what a real chain of this
         length could actually produce. */
      const teeth = [];
      for (let i = 0; i < len; i++) {
        teeth.push(TEETH_MIN + Math.floor(Math.random() * (TEETH_MAX - TEETH_MIN + 1)));
      }
      let y = 0, lo = 0, hi = 0;
      for (let i = 1; i < len; i++) {
        y += (rOf({ teeth: teeth[i - 1] }) + rOf({ teeth: teeth[i] })) * Math.sin(ang[i] * Math.PI / 180);
        lo = Math.min(lo, y); hi = Math.max(hi, y);
      }
      if (hi - lo <= BAND_MAX && Math.abs(y) <= page.endsCapFor(len)) legal++;
    }
    const rate = legal / TRIALS;
    if (rate === 0) bad.push('a chain of ' + len + ' wheels: no bearing draw '
      + 'satisfies the drift caps at all; every load would fall back');
    else if (rate < RATE_FLOOR) bad.push('a chain of ' + len + ' wheels: only '
      + (rate * 100).toFixed(1) + '% of draws are legal (floor is '
      + (RATE_FLOOR * 100).toFixed(0) + '%); the deal will often exhaust its '
      + 'tries and fall back to the closest draw instead of a legal one');
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

/* ---- 9. the colour deal, and the families derived from one seed ---------- */

/* Builds the REAL palette machinery out of index.html against a fixture set of
   people, WHEEL_POOL and all. Everything a derived family is measured against is
   read from the page -- flatTones, relLum, contrastAt, the ink, the ghost
   palette -- so what this suite checks is what the browser computes. */
function palette(people, warn) {
  const conf = (function () { const w = {}; new Function('window', CFG_SRC)(w); return w.WOZI_CONFIG; })();
  const parts = [
    grabBlock('const hueOf =', '{', '}') + ';',
    grabDecl('const WHEEL_POOL ='),
    grabDecl('const hueGap ='),
    grabDecl('const MIN_HUE_SEP ='),
    grabBlock('function dealColours(', '{', '}'),
    grabDecl('const OK_M ='),
    grabDecl('const srgbLin ='),
    grabDecl('const srgbGam ='),
    grabBlock('function oklabOf(', '{', '}'),
    grabBlock('function oklabRgb(', '{', '}'),
    grabDecl('const hexOf ='),
    grabBlock('const deltaE =', '{', '}') + ';',
    grabBlock('function maxChroma(', '{', '}'),
    grabDecl('const oklchHex ='),
    grabDecl('const FLAT_INK ='),
    grabDecl('const ENGRAVE_ALPHA ='),
    grabBlock('function flatTones(', '{', '}'),
    grabBlock('function relLum(', '{', '}'),
    grabBlock('function rgbOf(', '{', '}'),
    grabBlock('function contrastAt(', '{', '}'),
    grabBlock('const POOL_ENVELOPE =', '{', '}') + ')();',
    grabDecl('const GHOST_COLORS ='),
    grabBlock('const POOL_CHROMA_MIN =', '{', '}') + '));',
    grabBlock('const GHOST_CHROMA_MAX =', '{', '}') + '));',
    grabBlock('const bodyLegible =', '{', '}') + ');',
    grabBlock('const TONE_AIM =', '{', '}') + ')();',
    grabDecl('const faceStep ='),
    grabBlock('function familyFor(', '{', '}'),
    grabBlock('function capacityOf(', '{', '}'),
    grabBlock('const PALETTE_SEED =', '{', '}') + ')();',
    'return { WHEEL_POOL, MIN_HUE_SEP, hueGap, deltaE, dealColours, oklabOf, rgbOf,'
    + ' POOL_ENVELOPE, POOL_CHROMA_MIN, GHOST_CHROMA_MAX, bodyLegible, TONE_AIM,'
    + ' faceStep, familyFor, capacityOf, PALETTE_SEED, flatTones, relLum, contrastAt,'
    + ' FLAT_INK, ENGRAVE_ALPHA };'
  ];
  return new Function('CONF', 'console', parts.join('\n'))(
    { WHEEL_POOL: conf.WHEEL_POOL, PEOPLE: people }, { warn: warn || (() => {}) });
}

/* Seeds chosen to exercise different corners rather than to flatter the maths:
   the light purple of the worked example, a pool colour, the darkest and the
   most chromatic things the pool has, a purple that sits BELOW the envelope and
   has to be slid, and a near-white that has to be lifted in chroma. */
const SEEDS = ['#B79CE8', '#9B8CE0', '#F2C14E', '#17A05C', '#E8615A', '#54BFB6',
  '#7E57C2', '#FFF8E0'];

test('hue distance and perceptual distance cannot be the same rule on this pool', () => {
  /* This is the whole justification for #97 keeping TWO separation rules rather
     than re-expressing #12 as one perceptual floor, and it is a measurement
     rather than an opinion -- so it is asserted, and it fails the day the pool
     changes enough for the argument to stop holding. Which would be good news,
     and would want the code simplified rather than left claiming something that
     is no longer true. */
  const mod = palette([]);
  const pool = mod.WHEEL_POOL;
  let allowed = Infinity, rejected = 0;
  for (let i = 0; i < pool.length; i++) {
    for (let j = i + 1; j < pool.length; j++) {
      const d = mod.deltaE(pool[i].c, pool[j].c);
      if (mod.hueGap(pool[i].h, pool[j].h) >= mod.MIN_HUE_SEP) allowed = Math.min(allowed, d);
      else rejected = Math.max(rejected, d);
    }
  }
  ok(rejected > allowed, 'a single OKLab floor between ' + allowed.toFixed(4)
    + ' and ' + rejected.toFixed(4) + ' would now reproduce the 40-degree rule '
    + 'on this pool — #97 keeps two rules on the grounds that no such number '
    + 'exists, and that is no longer true. Collapse them into one.');
  /* And the specific pair #12 was written for is on the wrong side of it. */
  const blues = mod.deltaE('#4A90E2', '#8CB8F2');
  ok(blues > allowed, 'the two blues (' + blues.toFixed(4) + ') are no longer '
    + 'closer in hue but further in OKLab than a pair the rule allows ('
    + allowed.toFixed(4) + ')');
});

test('a seeded chain is one colour, and no two of its wheels are a step nobody could see', () => {
  /* The floor is the distance between a wheel's body and its own raised face --
     the smallest tonal step this drawing already asks every viewer to see. Above
     it two neighbours are at least as distinguishable as something the artwork
     already depends on. Checked over EVERY pair, not just neighbours on the
     ramp, because the wheels are handed out shuffled. */
  const mod = palette([]);
  const bad = [];
  SEEDS.forEach(seed => {
    const cap = mod.capacityOf(seed);
    ok(cap >= 4, seed + ' can only hold ' + cap + ' wheels, which is fewer than '
      + 'any chain this page is likely to draw');
    for (let n = 1; n <= cap; n++) {
      const f = mod.familyFor(seed, n);
      if (!f.colours) { bad.push(seed + ' produced no family at all at n=' + n); continue; }
      if (f.colours.length !== n) bad.push(seed + ' n=' + n + ' returned ' + f.colours.length);
      if (n > 1 && f.worst < f.floor) {
        bad.push(seed + ' n=' + n + ': closest pair ' + f.worst.toFixed(4)
          + ' is under its own floor ' + f.floor.toFixed(4) + ', inside the '
          + 'capacity it claims (' + cap + ')');
      }
      /* One wheel gets the colour that was asked for, exactly. */
      if (n === 1 && !f.moved && f.colours[0].toLowerCase() !== seed.toLowerCase()) {
        bad.push(seed + ' n=1 was dealt ' + f.colours[0] + ' rather than the seed');
      }
    }
    /* And past capacity it must NOT quietly claim to have separated them. */
    const over = mod.familyFor(seed, cap + 2);
    if (over.colours && over.worst >= over.floor) {
      bad.push(seed + ' claims ' + (cap + 2) + ' wheels are still ' + over.worst.toFixed(4)
        + ' apart, past a capacity of ' + cap + ' — the capacity is not honest');
    }
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('every derived colour stays inside the tonal envelope the pool already occupies, in both themes', () => {
  /* A pale family is exactly where the engraving and the page both get thin, and
     a palette that reads on dark and muddies on light is half a feature. The
     bound is not a number somebody chose: it is what the shipped pool already
     reaches, measured through the same flatTones() the page draws with. */
  const mod = palette([]);
  const bad = [];
  SEEDS.forEach(seed => {
    [1, 2, 3, 5, 7, mod.capacityOf(seed)].forEach(n => {
      const f = mod.familyFor(seed, n);
      if (!f.colours) return;
      f.colours.forEach(c => {
        ['light', 'dark'].forEach(theme => {
          const env = mod.POOL_ENVELOPE[theme];
          const body = mod.rgbOf(mod.flatTones(c, theme === 'light').body);
          const y = mod.relLum(body);
          if (y < env.lo - 1e-9 || y > env.hi + 1e-9) {
            bad.push(seed + ' n=' + n + ' -> ' + c + ' sits at ' + y.toFixed(3)
              + ' luminance in ' + theme + ', outside the pool\'s ' + env.lo.toFixed(3)
              + '..' + env.hi.toFixed(3));
          }
          const ink = mod.contrastAt(mod.rgbOf(mod.FLAT_INK), body, mod.ENGRAVE_ALPHA);
          if (ink < env.ink - 1e-9) {
            bad.push(seed + ' n=' + n + ' -> ' + c + ': the engraving reaches only '
              + ink.toFixed(2) + ':1 over it in ' + theme + ', against ' + env.ink.toFixed(2)
              + ':1 over the worst wheel that ships');
          }
        });
      });
    });
  });
  ok(bad.length === 0, [...new Set(bad)].slice(0, 6).join('\n      '));
});

test('a seed the machine cannot use is moved or refused, and never quietly accepted', () => {
  const said = [];
  const mod = palette([
    { slug: 'named', palette: 'rebeccapurple', links: [1] },
    { slug: 'ghost', palette: '#9AA6AD', links: [1] },
    { slug: 'ok', palette: '#B79CE8', links: [1] }
  ], m => said.push(m));
  ok(!mod.PALETTE_SEED['named'], 'a named CSS colour was accepted as a seed');
  ok(said.some(m => /not a colour this page can read/.test(m)),
    'a seed this page cannot parse said nothing');
  ok(!mod.PALETTE_SEED['ghost'], 'a seed as grey as the background machinery was accepted');
  ok(said.some(m => /background machinery is drawn at/.test(m)),
    'a seed at ghost chroma said nothing');
  eq(mod.PALETTE_SEED['ok'], '#b79ce8', 'a usable seed was not kept');

  /* Outside the envelope is SLID, not refused: "pick another colour" is a poor
     answer to a child who picked this one. But the family must then really be
     inside, and must say it moved. */
  const bad = [];
  ['#7E57C2', '#301860', '#FFF8E0'].forEach(seed => {
    const f = mod.familyFor(seed, 5);
    if (!f.colours) { bad.push(seed + ' produced no family'); return; }
    if (!f.moved) bad.push(seed + ' is outside the envelope but does not report moving');
    f.colours.forEach(c => { if (!mod.bodyLegible(c)) bad.push(seed + ' -> ' + c + ' is still outside'); });
    /* Hue is what the person actually chose, and moving lightness must not
       throw it away. */
    const a = mod.oklabOf(mod.rgbOf(seed)), b = mod.oklabOf(mod.rgbOf(f.anchor));
    const ah = (Math.atan2(a[2], a[1]) * 180 / Math.PI + 360) % 360;
    const bh = (Math.atan2(b[2], b[1]) * 180 / Math.PI + 360) % 360;
    const drift = Math.min(Math.abs(ah - bh), 360 - Math.abs(ah - bh));
    if (drift > 1) bad.push(seed + ' slid to ' + f.anchor + ', ' + drift.toFixed(1)
      + ' degrees off the hue that was asked for');
  });
  ok(bad.length === 0, bad.join('\n      '));
});

test('a seeded chain leaves the pool deal exactly as it was', () => {
  /* The two rules are never both applied because they are never both
     applicable: a chain with a seed is taken out of dealColours() altogether, so
     its wheels can neither be scored by a hue rule that means nothing to them
     nor consume pool colours the other chains are being dealt from. */
  const src = SRC.slice(SRC.indexOf('const POOL_SLOTS = ['), SRC.indexOf('TRAIN.forEach((t, i) => {', SRC.indexOf('const POOL_SLOTS = [')));
  ok(/PALETTE_SEED\[TRAIN\[i\]\.person\]/.test(src),
    'the pool deal no longer excludes chains that carry a seed');
  const mod = palette([]);
  /* And dealColours itself is untouched: still the hue rule, still 80 tries. */
  const bad = [];
  for (let trial = 0; trial < 400; trial++) {
    const deal = mod.dealColours(7, (k) => k === 0 ? null : k - 1);
    for (let k = 1; k < 7; k++) {
      const a = mod.WHEEL_POOL.find(p => p.c === deal[k]);
      const b = mod.WHEEL_POOL.find(p => p.c === deal[k - 1]);
      const g = mod.hueGap(a.h, b.h);
      if (g < mod.MIN_HUE_SEP) bad.push('meshing pair at ' + g.toFixed(1) + ' degrees');
    }
  }
  ok(bad.length === 0, bad.length + ' pool-dealt meshing pairs broke the '
    + mod.MIN_HUE_SEP + '-degree rule over 400 deals: ' + bad.slice(0, 3).join(', '));
});

/* ---- 10. a kidney slot holds its shape as the wheel grows ----------------- */

test('a kidney slot keeps its width-to-length proportion across the whole dealt tooth range (GitHub #93)', () => {
  /* CL#115, GitHub #93: slots() set the arm -- the metal LEFT BETWEEN two openings -- by a
     FIXED NUMBER OF DEGREES, while the slot's own WIDTH is a fraction of the
     annulus SPAN (rOut - rIn). A fixed angle converts to a physical length
     through the wheel's MID radius, which tracks the CIRCUMFERENCE; the width
     tracks the much smaller SPAN instead -- two quantities that grow at
     different rates across TEETH_MIN..TEETH_MAX, so the straight run went flat
     while the width nearly tripled and the kidney read as a round hole at the
     big end. The fix replaces the fixed angle with `aspect`, a straight-run /
     width ratio derived the same mid-radius way capDeg already is, so this
     measures the ACHIEVED ratio at every dealt wheel size -- not one sampled
     size, which is exactly what the bug was about.

     Read out of index.html rather than retyped: the slots() closure itself
     (executed, not modelled), its px() floor, the two call sites' own hub
     multiple / target aspect / width scale, and CENTRE_FAMILIES' own web/hub
     for the two kinds that call it. */
  const pxLine = grabDecl('const px = (want, lo, hi) =>');
  const pxFn = new Function('S', pxLine + '\nreturn px;')(1);
  const slotsSrc = grabBlock('const slots = (arms, rIn, rOut, aspect, widthScale) => {', '{', '}');
  const gearSvgSrc = grabBlock('gearSvg(g, S) {', '{', '}');
  const radiiSrc = grabDecl('const faceR =') + grabDecl('const wellR =') + grabDecl('const hubR =');

  function famNums(type) {
    const re = new RegExp('\\{ type: \'' + type + '\',\\s*web:\\s*([0-9.]+),\\s*hub:\\s*([0-9.]+),');
    const m = SRC.match(re);
    ok(m, 'CENTRE_FAMILIES has no ' + type + ' entry with web/hub -- extraction is broken, not the page');
    return { web: +m[1], hub: +m[2] };
  }
  function callSiteFor(kind) {
    /* The hub multiplier is a bare number OR the named constant BOSS_MUL
       (GitHub #95) -- either is read here rather than assumed, so renaming
       what the call site passes cannot silently stop being checked. */
    const re = kind === 'spokes'
      ? /slots\(arms,\s*hubR\s*\*\s*([0-9.]+|BOSS_MUL),\s*wellR,\s*([0-9.]+),\s*([0-9.]+)\)/
      : /slots\(g\.arms,\s*hubR\s*\*\s*([0-9.]+|BOSS_MUL),\s*wellR,\s*([0-9.]+),\s*([0-9.]+)\)/;
    const m = gearSvgSrc.match(re);
    ok(m, 'could not find the ' + kind + ' call site to slots() -- extraction is broken, not the page');
    const hubMult = m[1] === 'BOSS_MUL' ? grabNumber('BOSS_MUL') : +m[1];
    return { hubMult: hubMult, aspect: +m[2], widthScale: +m[3] };
  }
  function wheelRadii(teeth, fam) {
    const r = page.MODULE * teeth / 2;
    const prof = { web: fam.web, hub: fam.hub };
    const fn = new Function('r', 'm', 'prof', 'marked', 'bandIn', radiiSrc + 'return { wellR, hubR };');
    return fn(r, page.MODULE, prof, false, 0);
  }
  /* Runs the REAL slots() closure. PT is stubbed to record every (radius,
     angle) it is asked to plot instead of turning them into an SVG path --
     four calls per opening (rO,a0)(rO,a1)(rI,a1)(rI,a0) -- which is enough to
     recover a0, a1, rO and rI without needing to decode path syntax. h(),
     p and this.arcD only affect what gets DRAWN, never what gets computed,
     so they are stubbed harmlessly. */
  function runSlots(arms, rIn, rOut, aspect, widthScale) {
    const calls = [];
    const holes = [], inner = [];
    const PT = (r, a) => { calls.push({ r: r, a: a }); return ''; };
    const h = () => null;
    const p = ['0', '1', '2', '3'];
    const fakeThis = { arcD: () => '' };
    const wrapper = new Function('px', 'PT', 'holes', 'inner', 'h', 'p',
      slotsSrc + '\nreturn slots;');
    wrapper.call(fakeThis, pxFn, PT, holes, inner, h, p)(arms, rIn, rOut, aspect, widthScale);
    return calls;
  }

  const bad = [];
  ['spokes', 'pockets'].forEach(kind => {
    const fam = famNums(kind);
    const site = callSiteFor(kind);
    [4, 5, 6].forEach(arms => {
      const measured = [];
      for (let teeth = page.TEETH_MIN; teeth <= page.TEETH_MAX; teeth++) {
        const { wellR, hubR } = wheelRadii(teeth, fam);
        const rIn = hubR * site.hubMult, rOut = wellR;
        const calls = runSlots(arms, rIn, rOut, site.aspect, site.widthScale);
        if (calls.length < 4) continue;   // this size cuts no opening at all -- not this test's concern
        const mid = (rIn + rOut) / 2;
        const wSlot = calls[0].r - calls[2].r;
        const straightLen = (calls[1].a - calls[0].a) * Math.PI / 180 * mid;
        measured.push({ teeth: teeth, aspect: straightLen / wSlot });
      }
      ok(measured.length >= 2, kind + ' arms=' + arms + ' produced fewer than two measurable '
        + 'sizes across teeth ' + page.TEETH_MIN + '-' + page.TEETH_MAX
        + ' -- the extraction or the deal bounds are broken, not necessarily the fix');
      const values = measured.map(m => m.aspect);
      const min = Math.min(...values), max = Math.max(...values);
      const ratio = max / min;
      /* 1.5 sits between the two: this fix's own worst case (arms=6, where the
         gap is tightest and the arm floors at zero for the smaller sizes)
         measures 1.29-1.46x over this exact sweep; the ORIGINAL fixed-degree
         code measured 1.54-3.13x over the same sweep -- comfortably on the
         other side, for every kind/arms combination. */
      if (ratio > 1.5) bad.push(kind + ' arms=' + arms + ': aspect ratio ranges '
        + min.toFixed(3) + '-' + max.toFixed(3) + ' (' + ratio.toFixed(2) + 'x) across teeth '
        + measured[0].teeth + '-' + measured[measured.length - 1].teeth
        + ' -- the slot is not holding its shape as the wheel grows');
      /* arms=4 never floors the arm at zero for either family (checked above,
         over the whole tooth range), so its achieved aspect must equal the
         designed target EXACTLY, at every size -- proving the arm is derived
         from the same mid-radius conversion capDeg uses, not merely bounded
         into a plausible-looking range. */
      if (arms === 4) measured.forEach(m => {
        if (Math.abs(m.aspect - site.aspect) > 1e-6) bad.push(kind + ' arms=4 teeth=' + m.teeth
          + ': achieved aspect ' + m.aspect.toFixed(6) + ' does not equal the designed target '
          + site.aspect + ' -- the arm is not being derived the way capDeg is');
      });
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
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
