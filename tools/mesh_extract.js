'use strict';
/* Shared "read not model" extractor for the one-shot mesh/ravigneaux analysis
   tools (GitHub #102, tier 3). Each of ravigneaux.js, mesh_inv.js, mesh_epi.js,
   mesh_rav.js, mesh_audit.js and mesh_poly.js used to carry its own hand-typed
   copy of MODULE, TOOTH_ADD, TOOTH_DED, RING_STUB and friends -- the exact
   failure CLAUDE.md warns tools/test.js exists to avoid, just not gated by CI.
   One of those copies had actually drifted: mesh_audit.js and mesh_poly.js
   still used a root dedendum of 1.15, which is what TOOTH_DED was BEFORE
   bf16c0c ("true involute tooth flanks -- the teeth now touch") moved it to
   1.25 -- proof this is not a hypothetical risk.

   These six files are all plain Node, live in the same directory, and share no
   language boundary -- unlike tools/test.js (the CI gate, kept deliberately
   independent per CL#126) and the JS/Python split between tools/mesh_dirs.py
   and tools/dom_invariants.py. A single shared module here costs nothing and
   removes six copies of the same ~15-line idiom instead of leaving a sixth.

   Ports CL#112's contract unchanged: comments are stripped first, then every
   ASSIGNMENT to a name is counted, and more than one throws rather than
   silently returning the first match (the CELL_MIN trap, GitHub #101).

   AND NOW GitHub #137's, for the same reason: `grabBlock`/`grabDecl` here were
   the same first-`indexOf`-wins pattern as tools/test.js's, so an anchor
   occurring twice -- or occurring only in prose -- silently returned a different
   block. The comment mask is length-preserving so the offset found on the mask
   still points into the real file, the anchor refuses to guess between two
   matches, and indentation in an anchor means "first thing on its line" rather
   than a literal number of spaces. tools/test.js carries the long-form argument
   for each of those; it is duplicated rather than shared because CL#126 keeps
   the CI gate independent of everything in tools/ that is not a gate. */
const fs = require('fs');
const path = require('path');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

/* Comments replaced by spaces, newlines kept -- see tools/test.js for why the
   scanner is deliberately naive and why its error direction is loud. */
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
const MASKED = maskComments(SRC);

/* The one live match for an anchor, or a refusal. Leading whitespace in the
   anchor means "first thing on its line" at any indentation; a newline inside it
   matches a newline plus whatever indentation the file uses, so an anchor can be
   extended over the next line to disambiguate without baking in a layout. */
function locateAnchor(what, decl) {
  const lead = /^[ \t]*/.exec(decl)[0];
  const body = decl.slice(lead.length);
  const pattern = body.split(/\r?\n[ \t]*/)
    .map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\n[ \\t]*');
  const re = new RegExp(pattern, 'g');
  const hits = [];
  let m;
  while ((m = re.exec(MASKED)) !== null) {
    re.lastIndex = m.index + 1;
    let at = m.index;
    if (lead) {
      let p = at;
      while (p > 0 && (MASKED[p - 1] === ' ' || MASKED[p - 1] === '\t')) p--;
      if (p !== 0 && MASKED[p - 1] !== '\n') continue;
      while (at > 0 && (SRC[at - 1] === ' ' || SRC[at - 1] === '\t')) at--;
    }
    hits.push(at);
  }
  if (hits.length > 1) {
    throw new Error(what + ' anchor ' + JSON.stringify(decl) + ' matches ' +
      hits.length + ' places in index.html with comments masked -- cannot tell ' +
      'which one ships (GitHub #101, #137). Extend the anchor over the next line ' +
      'until it is unique; indentation inside it is ignored.');
  }
  if (!hits.length) {
    const inProse = new RegExp(pattern).test(SRC);
    throw new Error(what + ' not found in index.html: ' + decl +
      (inProse ? ' -- it IS in the file, but only inside a comment (GitHub #101).' : ''));
  }
  return hits[0];
}

function grabNumber(name) {
  const assignments = [...MASKED.matchAll(new RegExp('\\b' + name + '\\s*=(?!=)', 'g'))];
  if (assignments.length > 1) {
    throw new Error('constant ' + name + ' is assigned ' + assignments.length +
      ' times in index.html -- grabNumber() cannot tell which one ships ' +
      '(the CELL_MIN trap, GitHub #101). Give it a unique name, or teach ' +
      'grabNumber() to scope the search.');
  }
  const m = MASKED.match(new RegExp('\\b' + name + '\\s*=\\s*(-?[0-9]+(?:\\.[0-9]+)?)'));
  if (!m) throw new Error('constant not found in index.html: ' + name);
  return parseFloat(m[1]);
}

/* One `function NAME(...) { ... }` or `{ ... }` block, brace-matched from a
   literal decl string -- the same technique tools/test.js uses to execute the
   page's own functions instead of modelling their algebra. */
function grabBlock(decl, open, close) {
  const i = locateAnchor('block', decl);
  const j = MASKED.indexOf(open, i);
  if (j < 0) throw new Error('block never opens with ' + open + ': ' + decl);
  let depth = 0;
  for (let k = j; k < MASKED.length; k++) {
    if (MASKED[k] === open) depth++;
    else if (MASKED[k] === close) { depth--; if (depth === 0) return SRC.slice(i, k + 1); }
  }
  throw new Error('unterminated block: ' + decl);
}

function grabDecl(decl) {
  const i = locateAnchor('declaration', decl);
  const j = MASKED.indexOf(';', i);
  if (j < 0) throw new Error('unterminated declaration: ' + decl);
  return SRC.slice(i, j + 1);
}

module.exports = { grabNumber, grabBlock, grabDecl, SRC };
