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
   silently returning the first match (the CELL_MIN trap, GitHub #101). */
const fs = require('fs');
const path = require('path');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const STRIPPED = SRC.replace(/\/\*[\s\S]*?\*\//g, '');

function grabNumber(name) {
  const assignments = [...STRIPPED.matchAll(new RegExp('\\b' + name + '\\s*=(?!=)', 'g'))];
  if (assignments.length > 1) {
    throw new Error('constant ' + name + ' is assigned ' + assignments.length +
      ' times in index.html -- grabNumber() cannot tell which one ships ' +
      '(the CELL_MIN trap, GitHub #101). Give it a unique name, or teach ' +
      'grabNumber() to scope the search.');
  }
  const m = STRIPPED.match(new RegExp('\\b' + name + '\\s*=\\s*(-?[0-9]+(?:\\.[0-9]+)?)'));
  if (!m) throw new Error('constant not found in index.html: ' + name);
  return parseFloat(m[1]);
}

/* One `function NAME(...) { ... }` or `{ ... }` block, brace-matched from a
   literal decl string -- the same technique tools/test.js uses to execute the
   page's own functions instead of modelling their algebra. */
function grabBlock(decl, open, close) {
  const i = SRC.indexOf(decl);
  if (i < 0) throw new Error('block not found in index.html: ' + decl);
  const j = SRC.indexOf(open, i);
  let depth = 0;
  for (let k = j; k < SRC.length; k++) {
    if (SRC[k] === open) depth++;
    else if (SRC[k] === close) { depth--; if (depth === 0) return SRC.slice(i, k + 1); }
  }
  throw new Error('unterminated block: ' + decl);
}

function grabDecl(decl) {
  const i = SRC.indexOf(decl);
  if (i < 0) throw new Error('declaration not found in index.html: ' + decl);
  const j = SRC.indexOf(';', i);
  if (j < 0) throw new Error('unterminated declaration: ' + decl);
  return SRC.slice(i, j + 1);
}

module.exports = { grabNumber, grabBlock, grabDecl, SRC };
