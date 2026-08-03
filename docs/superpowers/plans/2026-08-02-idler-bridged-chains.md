# Idler-Bridged Multi-Chain Stage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render every configured chain on one stage, each driven off the longest chain through a bridge of ghost idler gears that also provides the spacing.

**Architecture:** `TRAIN` stops being an implicit path (wheel *i* meshes *i−1*) and becomes an explicit tree — each entry names its `parent`. `solve()` derives position, direction and phase from `g[t.parent]` instead of carrying running state down the array. Ghost idlers become real `TRAIN` entries with `role: 'idler'`, solved with the train rather than added after the fit. Hosts then select a scope (all chains, or one person alone) instead of just a default person.

**Tech Stack:** Static HTML/JS, no build step. React (UMD) via `h()` calls. Geometry suite is plain Node (`tools/test.js`). Browser harnesses are Python over CDP (`tools/*.py`) and JXA over WKWebView (`tools/webkit_*.js`).

## Global Constraints

Copied from `CLAUDE.md` and the spec. Every task's requirements implicitly include this section.

- **Do not hand-edit `support.js`.** It is generated runtime, not project code.
- **No CSS animations or transitions on anything that turns.** All motion comes from one `requestAnimationFrame` loop integrating a master angle (#3).
- **No stylesheets or CSS classes for layout.** Styling is inline by design.
- **No `filter: drop-shadow` on wheels** (#6). Shadows are baked into the artwork and one shared layer.
- **Do not hardcode wheel sizes, tooth counts, or centre distances.** They derive from `MODULE`.
- **No tuned constants that need re-measuring later.** Derive, or state explicitly why you cannot.
- **One clock.** Every wheel transform derives from the same master angle each tick.
- **Lighting from directly above.** All shading symmetric about the vertical axis.
- **Paint order:** specular arc under rim engravings; cast shadows in one layer behind all wheels.
- **The sleep gate starts awake.** Only sleep on explicit `isIntersecting === false` after non-zero stage size (#7).
- **No test hooks in shipped code.** Determinism is injected over CDP by the harness.
- **Single `MODULE`.** No compound gears, no second module.
- **Commit messages via `git commit -F <file>`** — backticks in `-m` are eaten by zsh.
- **`npm test` must pass before any push.** CI gates the deploy on it.
- **Push deploys.** `.github/workflows/deploy.yml` fires on any push to `main` that is not a `.md`-only change.

**Baseline commit:** `439c9ba`. Tasks 1–3 must be **0 px** against it via `python3 tools/pixel_regress.py --ref 439c9ba`.

**Serving locally:** `python3 -m http.server 8765` from the repo root.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `index.html` | The page and all geometry | Modified throughout — see per-task line refs |
| `config.js` | Settings: people, services, palette | Add `STAGE_HOSTS`; narrow `PEOPLE[].hosts` to solo hosts |
| `tools/test.js` | Geometry suite, reads constants out of `index.html` | Add tree/seating/legibility tests |
| `tools/mesh_dirs.py` | **New.** Browser harness asserting meshing neighbours turn opposite ways | Create |
| `tools/pixel_regress.py` | Deterministic screenshot diff | Unchanged, used as gate |
| `tools/verify_motion.py` | Motion/badge/icon gate | Unchanged, used as gate |
| `CHANGELOG.md` | Numbered log, newest first | One entry per shipped task group |

---

### Task 1: Make the parent explicit

Turns the implicit path into an explicit tree with **no behaviour change**. Every wheel's parent is still `i − 1`, so the render must be pixel-identical.

**Files:**
- Modify: `index.html:380` (TRAIN construction)
- Modify: `index.html:2061-2075` (solve loop head and placement)
- Modify: `tools/test.js` (add tree tests)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: every `TRAIN` entry carries `parent: number|null`, `person: string`, `role: 'link'|'idler'`. `solve()` reads `g[t.parent]`. Later tasks rely on all four.

- [ ] **Step 1: Write the failing test**

Add to `tools/test.js`, immediately before `test('the fit rule does not branch...')`:

```js
/* Executes the real TRAIN builder out of index.html rather than modelling it. */
function buildTrain(links, personSlug) {
  const i = SRC.indexOf('const TRAIN = ');
  const j = SRC.indexOf(';', i);
  ok(i > 0 && j > i, 'could not find the TRAIN builder in index.html');
  const expr = SRC.slice(i + 'const TRAIN = '.length, j);
  return new Function('WHO', 'return ' + expr)({ links: links, slug: personSlug });
}

test('every TRAIN entry names its parent, and the parents form one tree', () => {
  const train = buildTrain([{ slug: 'a' }, { slug: 'b' }, { slug: 'c' }], 'p');
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
  const train = buildTrain([{ slug: 'a' }, { slug: 'b' }], 'harper');
  const bad = [];
  train.forEach((t, i) => {
    if (t.person !== 'harper') bad.push(`wheel ${i} person is ${t.person}, want harper`);
    if (t.role !== 'link') bad.push(`wheel ${i} role is ${t.role}, want link`);
  });
  ok(bad.length === 0, bad.join('\n      '));
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test 2>&1 | grep -E "FAIL|passed,"`
Expected: both new tests FAIL — the entries have no `parent`, `person` or `role` yet.

- [ ] **Step 3: Add the fields to the TRAIN builder**

Replace `index.html:380`:

```js
const TRAIN = (WHO.links || []).map((l, i) => ({ slug: l.slug, prof: { rim: 1.7 },
  /* THE PARENT IS EXPLICIT. It used to be implicit -- wheel i meshed wheel i-1,
     and nothing said so -- which is why solve() carried x/y/dir/phase as running
     state down the array. A chain is still a path, so every parent here is i-1
     and nothing renders differently; what changes is that a branch becomes
     expressible at all. */
  parent: i === 0 ? null : i - 1,
  person: WHO.slug,
  role: 'link' }));
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test 2>&1 | grep -E "FAIL|passed,"`
Expected: 30 passed, 0 failed.

- [ ] **Step 5: Make solve() read the parent**

In `index.html`, replace the loop head at `2061-2066`:

```js
    const g = [], strands = [];
    TRAIN.forEach((t, i) => {
      const prof = t.prof || {};
      const r = MODULE * t.teeth / 2;
      const ro = r + MODULE * TOOTH_ADD;
      let chainFrom = null;
      /* PER WHEEL, NOT CARRIED. These used to be declared outside the loop and
         mutated, so wheel i's position was whatever the previous iteration left
         behind -- the implicit path, written as shared state. Deriving each wheel
         from its own parent is what makes a branch possible. The initial values
         are the ones the old declaration held, so the root is unchanged. */
      let x = 0, y = 0, dir = 1, phase = 0;
      if (t.parent != null) {
        const prev = g[t.parent];
```

Then, inside the clash test, replace `if (oi === i - 1) return false;` with:

```js
                if (oi === t.parent) return false;
```

and in the `linked` strand test replace `oi !== i - 1` with `oi !== t.parent`, and `chainFrom = i - 1;` with `chainFrom = t.parent;`.

- [ ] **Step 6: Verify the render did not move**

Run: `python3 tools/pixel_regress.py --ref 439c9ba`
Expected: `0 px differ` at both viewports. **If this is not zero, the refactor changed behaviour — stop and find out why before continuing.**

Run: `npm test`
Expected: 30 passed.

- [ ] **Step 7: Commit**

```bash
git add index.html tools/test.js
cat > /tmp/m.txt <<'EOF'
refactor: make each wheel's parent explicit, so a branch is expressible

TRAIN was an implicit path -- wheel i meshed wheel i-1 and nothing said so,
which is why solve() carried x/y/dir/phase as running state down the array.
Every parent is still i-1, so nothing renders differently.

0 px vs 439c9ba at 1440x900 and 390x844.
EOF
git commit -F /tmp/m.txt
```

---

### Task 2: Move the three deals from index-adjacency to parent-adjacency

Three deals treat "index *i−1*" as "the neighbouring wheel". On a tree the neighbour is the parent. Still a no-op for a path.

**Files:**
- Modify: `index.html:922-960` (`dealTeeth` twins rule)
- Modify: `index.html:978-1000` (`dealAngles` drift walk)
- Modify: `index.html:1125-1145` (`dealColours` hue separation)
- Modify: `tools/test.js`

**Interfaces:**
- Consumes: `t.parent` from Task 1.
- Produces: no new symbols. Behaviour: adjacency everywhere means parent/child.

- [ ] **Step 1: Write the failing test**

Add to `tools/test.js` after the tree tests:

```js
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test 2>&1 | grep -A3 "adjacency by array index"`
Expected: FAIL listing all three.

- [ ] **Step 3: Fix `dealTeeth`**

In `index.html`, inside `dealTeeth`, replace the twins loop:

```js
    /* Two identical wheels side by side read as a mistake rather than a choice --
       and "side by side" means MESHING, which on a tree is the parent, not the
       previous array slot. */
    let twins = false;
    for (let i = 0; i < cut.length; i++) {
      const p = TRAIN[i].parent;
      if (p != null && cut[i] === cut[p]) twins = true;
    }
```

- [ ] **Step 4: Fix `dealAngles`**

Replace the drift walk so it follows parents. The band and end-drift caps are measured along the chain from the root:

```js
    /* Walk parents, not indices: on a tree the offset of a wheel is its parent's
       offset plus this step, and the array order is not the chain order. */
    const yOf = new Array(TRAIN.length).fill(0);
    let lo = 0, hi = 0, last = 0;
    for (let i = 1; i < TRAIN.length; i++) {
      const p = TRAIN[i].parent;
      yOf[i] = yOf[p] + (rOf(TRAIN[p]) + rOf(TRAIN[i])) * Math.sin(ang[i] * Math.PI / 180);
      if (yOf[i] < lo) lo = yOf[i];
      if (yOf[i] > hi) hi = yOf[i];
      last = yOf[i];
    }
    if (hi - lo > BAND_MAX) continue;
    if (Math.abs(last) > ENDS_MAX) continue;
```

- [ ] **Step 5: Fix `dealColours`**

`dealColours` scores a candidate set. It must score meshing pairs, so it needs the parent map. Change its signature and the call site:

```js
function dealColours(n, parentOf) {
  const dist = (a, b) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b));
  let best = null, bestScore = -1;
  for (let tries = 0; tries < 80; tries++) {
    const idx = WHEEL_POOL.map((c, i) => i);
    for (let i = idx.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const t = idx[i]; idx[i] = idx[j]; idx[j] = t;
    }
    const pick = idx.slice(0, Math.min(n, idx.length));
    /* Score MESHING pairs. Wheels are only confused with the ones beside them,
       and beside means meshed -- on a tree that is the parent, not the previous
       slot in this array. */
    let score = 360;
    for (let i = 0; i < pick.length; i++) {
      const p = parentOf(i);
      if (p == null || p >= pick.length) continue;
      score = Math.min(score, dist(WHEEL_POOL[pick[i]].h, WHEEL_POOL[pick[p]].h));
    }
    if (score > bestScore) { bestScore = score; best = pick; }
    if (score >= 40) break;
  }
  return best.map(i => WHEEL_POOL[i].c);
}
const WHEEL_DEAL = dealColours(TRAIN.length, (i) => TRAIN[i].parent);
```

- [ ] **Step 6: Run tests and the pixel gate**

Run: `npm test`
Expected: 31 passed, 0 failed.

Run: `python3 tools/pixel_regress.py --ref 439c9ba`
Expected: `0 px differ`. The deals consume `Math.random()` in the same order and quantity, so a seeded run must be identical. **If pixels differ, you changed the draw order — find it.**

- [ ] **Step 7: Commit**

```bash
git add index.html tools/test.js
cat > /tmp/m.txt <<'EOF'
refactor: adjacency means the parent, not the previous array slot

Three deals used i-1 to mean "the wheel next to me": the twins rule in
dealTeeth, the drift walk in dealAngles, and the 40-degree hue separation in
dealColours. On a tree the neighbour is the parent.

0 px vs 439c9ba -- the deals consume Math.random() in the same order.
EOF
git commit -F /tmp/m.txt
```

---

### Task 3: Redefine ENDS_APART for a tree

"The two ends of the train repel each other" does not survive a tree with more than two ends.

**Files:**
- Modify: `index.html` (the `need` computation inside solve's clash test)
- Modify: `tools/test.js`

**Interfaces:**
- Consumes: `t.parent`.
- Produces: `isLeaf(i)` available inside `solve()`.

- [ ] **Step 1: Write the failing test**

```js
test('the ends-apart rule is expressed in leaves, not array positions', () => {
  /* "The two ends of the train repel each other, so the run reads as a line of
     machinery rather than a closed ring." A tree has more than two ends. */
  ok(!/oi === 0 && i === TRAIN\.length - 1/.test(SRC),
    'ENDS_APART still tests the first and last array positions');
  ok(/isLeaf/.test(SRC), 'solve() does not compute leaves for the ends-apart rule');
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test 2>&1 | grep -A2 "ends-apart"`
Expected: FAIL.

- [ ] **Step 3: Implement**

Before the `TRAIN.forEach` in `solve()`:

```js
    /* A TREE HAS MORE THAN TWO ENDS. The rule is that the machine's extremities
       push apart so the run reads as a line rather than a closed ring; with one
       chain that is the first and last wheel, but a branch adds an end. Leaves
       and the root are the extremities. */
    const hasChild = new Array(TRAIN.length).fill(false);
    TRAIN.forEach(t => { if (t.parent != null) hasChild[t.parent] = true; });
    const isLeaf = (i) => !hasChild[i];
```

Then replace the `need` line:

```js
                const need = o.ro + ro + CLEARANCE * tight
                  + ((isLeaf(oi) || o.i === 0) && isLeaf(i) && oi !== t.parent ? ENDS_APART * tight : 0);
```

- [ ] **Step 4: Run tests and the pixel gate**

Run: `npm test` — expected 32 passed.
Run: `python3 tools/pixel_regress.py --ref 439c9ba` — expected `0 px differ`. On a path the only leaf is the last wheel and the root is index 0, so the rule reduces to exactly what it was.

- [ ] **Step 5: Commit**

```bash
git add index.html tools/test.js
cat > /tmp/m.txt <<'EOF'
refactor: the ends-apart rule is about leaves, not array positions

A tree has more than two ends. On a path this reduces to the old rule exactly,
so 0 px vs 439c9ba.
EOF
git commit -F /tmp/m.txt
```

---

### Task 4: A harness that proves rotation alternates across every mesh

The "One clock" invariant on a tree. A wrong direction still animates smoothly, so nothing else catches it. Build this **before** branching exists, so it is proven against known-good output.

**Files:**
- Create: `tools/mesh_dirs.py`

**Interfaces:**
- Produces: `tools/mesh_dirs.py <url>` exits 0 when every meshing pair turns opposite ways, 1 otherwise.

- [ ] **Step 1: Write the harness**

Create `tools/mesh_dirs.py`. Model it on `tools/verify_motion.py` — copy its Chrome launch, free-port (`CDP_PORT` honoured) and websocket plumbing verbatim; do not invent new plumbing.

Core measurement, injected in-page:

```python
SAMPLE_JS = r"""
(() => {
  // A linked wheel is an <svg> whose first child is <defs>. Its centre comes from
  // the wrapper's inline left/top -- POSITION, never getBoundingClientRect, which
  // on a rotating element returns the axis-aligned box of a spinning square and
  // is up to sqrt(2) wrong depending on phase.
  const out = [];
  document.querySelectorAll('svg').forEach((s) => {
    const k = s.firstElementChild;
    if (!k || k.tagName.toLowerCase() !== 'defs') return;
    const wrap = s.parentElement;
    const st = wrap.getAttribute('style') || '';
    const m = st.match(/left:\s*([-0-9.]+)px;\s*top:\s*([-0-9.]+)px/);
    const w = parseFloat(s.getAttribute('width'));
    const tr = getComputedStyle(wrap).transform;
    const mm = tr.match(/matrix\(([-0-9.e]+),\s*([-0-9.e]+)/);
    if (!m || !mm) return;
    out.push({
      cx: parseFloat(m[1]) + w / 2, cy: parseFloat(m[2]) + w / 2,
      r: w / 2, rot: Math.atan2(+mm[2], +mm[1]) * 180 / Math.PI
    });
  });
  return JSON.stringify(out);
})()
"""
```

Then, after sampling twice ~700ms apart:

```python
def delta(a, b):
    d = b - a
    while d > 180: d -= 360
    while d < -180: d += 360
    return d

# Two wheels MESH when their centres sit at the sum of their radii. The drawn
# radius carries addendum and padding beyond the pitch circle, so allow a
# tolerance proportional to size rather than an absolute pixel figure.
pairs = []
for i in range(len(s1)):
    for j in range(i + 1, len(s1)):
        a, b = s1[i], s1[j]
        d = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
        if abs(d - (a["r"] + b["r"])) < 0.18 * (a["r"] + b["r"]):
            pairs.append((i, j))

bad = []
for i, j in pairs:
    di, dj = delta(s1[i]["rot"], s2[i]["rot"]), delta(s1[j]["rot"], s2[j]["rot"])
    if abs(di) < 1e-6 or abs(dj) < 1e-6:
        bad.append(f"wheels {i},{j} mesh but one is not turning")
    elif (di > 0) == (dj > 0):
        bad.append(f"wheels {i},{j} mesh but both turn the same way ({di:+.2f}, {dj:+.2f})")
```

Fail if `bad` is non-empty **or** `len(pairs) == 0` (finding no meshes at all means the detector is broken, and a silent pass is worse than a failure).

- [ ] **Step 2: Run it against the current page**

```bash
python3 -m http.server 8765 &
python3 tools/mesh_dirs.py "http://127.0.0.1:8765/"
```
Expected: PASS, with at least 6 meshing pairs found on the seven-wheel chain.

- [ ] **Step 3: Mutation-prove it**

Temporarily change `dir = -prev.dir;` to `dir = prev.dir;` in `index.html`, re-run.
Expected: FAIL listing every meshing pair.
Then revert the mutation and re-run: PASS.

- [ ] **Step 4: Commit**

```bash
git add tools/mesh_dirs.py
cat > /tmp/m.txt <<'EOF'
test: a harness that proves meshing wheels turn opposite ways

The One Clock invariant expressed on a tree, and the change most likely to
break silently -- a wrong direction still animates smoothly. Meshing pairs are
found by centre distance, so it needs no knowledge of the tree.

Mutation-proved: dir = prev.dir fails every pair.
EOF
git commit -F /tmp/m.txt
```

---

### Task 5: Assemble every chain into one TRAIN, behind `?who=all`

The default page must not change yet. `?who=all` becomes the only way to see the combined stage.

**Files:**
- Modify: `index.html:350-364` (`WHO`), `:380` (TRAIN), `:404` (TEETH_SUM), `:441` (NOMINAL_CHAIN), `:2029-2058` (seating)
- Modify: `tools/test.js`

**Interfaces:**
- Consumes: `parent`/`person`/`role` from Task 1.
- Produces: `STAGE` — `{ mode: 'all'|'solo', people: [...] }`. `TRAIN` spans every person in `STAGE.people`. `SPINE_LEN` is the longest chain's link count.

- [ ] **Step 1: Write the failing test**

```js
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test 2>&1 | grep -A4 "combined stage seats"`
Expected: FAIL — seating is global and `SITES` is currently flat, so wheels get another person's service or none.

- [ ] **Step 3: Add the stage resolver**

Replace the `WHO` IIFE at `index.html:350`:

```js
/* WHICH CHAINS ARE ON STAGE, and whether they share it. `?who=all` shows every
   chain; `?who=<slug>` or a person's own hostname shows one. Selection stays in
   the browser so one cached object serves every alternate domain name. */
const STAGE = (function () {
  const people = CONF.PEOPLE || [];
  if (!people.length) return { mode: 'solo', people: [] };
  let q = '';
  try { q = new URLSearchParams(location.search).get('who') || ''; } catch (e) {}
  if (q === 'all') return { mode: 'all', people: people.slice() };
  const host = (typeof location !== 'undefined' && location.hostname) || '';
  const one = people.find(p => p.slug === q)
           || people.find(p => (p.hosts || []).indexOf(host) >= 0)
           || people[0];
  return { mode: 'solo', people: [one] };
})();
/* Kept so everything reading a single active person still works: on a combined
   stage it is the spine, which is the chain the composition is built around. */
const WHO = STAGE.people.slice().sort((a, b) =>
  (b.links || []).length - (a.links || []).length)[0] || { slug: '', name: '', links: [] };
```

- [ ] **Step 4: Build TRAIN across every staged person**

**Before writing it:** the Task 1 test helper `buildTrain()` slices from
`const TRAIN = ` to the **first `;`**, which works only while the builder is a
single expression. The builder below is an IIFE containing semicolons, so that
helper breaks. Update it in the same step to slice a balanced block instead:

```js
function buildTrain(people) {
  const expr = grabBlock('const TRAIN = (function', '(', ')');
  return new Function('STAGE', 'return ' + expr.replace(/^const TRAIN = /, '') + '()')(
    { people: people });
}
```

and update the two Task 1 tests to pass `[{ slug: 'p', links: [...] }]`.

Replace the TRAIN builder:

```js
/* One entry per wheel across every chain on stage. Each person's first wheel is
   a root for now; Task 6 gives it a bridge to hang from. */
const TRAIN = (function () {
  const out = [];
  STAGE.people.forEach(p => {
    const base = out.length;
    (p.links || []).forEach((l, i) => {
      out.push({ slug: l.slug, prof: { rim: 1.7 },
        parent: i === 0 ? null : base + i - 1,
        person: p.slug, role: 'link' });
    });
  });
  return out;
})();
/* The SPINE is the longest chain -- it sets the scale and, from Task 6, the axis
   every other chain runs parallel to. Ties break by PEOPLE order. */
const SPINE_LEN = Math.max(1, ...STAGE.people.map(p => (p.links || []).length));
```

- [ ] **Step 5: Base TEETH_SUM on the spine, not the total**

Replace `index.html:404`'s `TEETH_SUM`:

```js
/* The train's overall LENGTH, which is the spine -- a branch adds cross-axis
   height, not length, so counting every wheel on stage would overstate it and
   the layout would lose its proportions. */
const TEETH_SUM = Math.round(TEETH_MEAN * SPINE_LEN);
```

**`NOMINAL_CHAIN` and `SPINE_LEN` are two different quantities. Keep both.**

- `SPINE_LEN` = the longest chain among the people **on stage**. It sets
  `TEETH_SUM`, because that is the train actually being drawn.
- `NOMINAL_CHAIN` at `index.html:441` = the longest chain among **all configured**
  people, staged or not. It sets `NOMINAL_SPAN`, which is what makes a gear the
  same size on every page — a solo page must render at the fullest chain's scale
  even though that chain is not on stage.

They coincide on the combined stage and differ on a solo one, which is the whole
point. Leave `NOMINAL_CHAIN` scanning `CONF.PEOPLE` and add a comment saying
exactly why, so nobody "simplifies" it to `SPINE_LEN`:

```js
/* ALL CONFIGURED PEOPLE, not just the ones on stage -- deliberately different
   from SPINE_LEN. A solo page has to draw its wheels at the size they have on
   the fullest chain, and that chain is not on stage to be measured. */
const NOMINAL_CHAIN = Math.max(1, ...((CONF.PEOPLE || []).map(p => (p.links || []).length)));
```

- [ ] **Step 6: Make SITES and seating per person**

Replace `const SITES` at `index.html:1276`:

```js
/* Per person now: a combined stage carries several chains and a service belongs
   to whoever's chain it sits on. Keyed person -> slug -> { label, path, href }. */
const SITES = (function () {
  const out = {};
  STAGE.people.forEach(p => {
    const m = out[p.slug] = {};
    (p.links || []).forEach(l => {
      const svc = (CONF.SERVICES || {})[l.slug] || {};
      m[l.slug] = { label: svc.label || l.slug, path: l.path, href: l.href };
    });
  });
  return out;
})();
```

Replace the seating block (`index.html:2029-2058`) so each person is seated over their own wheel range:

```js
    if (!this._slugFor) {
      const slugFor = {};
      /* SEATED PER PERSON. PAIR_SLOTS names wheel indices WITHIN a chain, so on a
         combined stage they have to be read relative to where that person's
         wheels start -- otherwise a pair straddles a boundary and one of someone
         else's services lands on this person's wheel (#65 is the same family:
         a wheel that ends up with the wrong slug, or none). */
      const byPerson = {};
      TRAIN.forEach((t, i) => {
        if (t.role !== 'link') return;
        (byPerson[t.person] = byPerson[t.person] || []).push(i);
      });
      Object.keys(byPerson).forEach(person => {
        const idx = byPerson[person];
        /* A pair slot the chain cannot reach is not a pair slot -- it would claim
           its in-range index while never being fillable, and that wheel would draw
           blank (#65). */
        const pairSlots = PAIR_SLOTS.filter(pr => pr.every(k => k < idx.length));
        const singleSlots = [];
        idx.forEach((_, k) => { if (!pairSlots.some(pr => pr.indexOf(k) >= 0)) singleSlots.push(k); });
        const has = (slug) => Object.prototype.hasOwnProperty.call(SITES[person] || {}, slug);
        const pairs = shuffle(PAIRS.filter(pr => pr.every(has)).map(pr => shuffle(pr.slice())));
        const singles = shuffle(SINGLES.filter(has));
        if (pairs.length) pairSlots.forEach((pr, k) => {
          const pair = pairs[k % pairs.length];
          slugFor[idx[pr[0]]] = pair[0]; slugFor[idx[pr[1]]] = pair[1];
        });
        if (singles.length) singleSlots.forEach((s, k) => { slugFor[idx[s]] = singles[k % singles.length]; });
      });
      this._slugFor = slugFor;
    }
```

- [ ] **Step 7: Fix every `SITES[slug]` read**

Run: `grep -n "SITES\[" index.html`

Every hit must become `SITES[g.person][g.slug]`. The gear object already carries `person` — add it to the `g.push({...})` in `solve()` alongside `slug`:

```js
        slug: slugFor[i] || null, person: t.person, role: t.role,
```

- [ ] **Step 8: Run the tests and both gates**

Run: `npm test` — expected 33 passed.
Run: `python3 tools/pixel_regress.py --ref 439c9ba` — expected `0 px differ`. The default page is still solo, and a solo stage of one person produces the same TRAIN it always did.
Run: `python3 tools/verify_motion.py "http://127.0.0.1:8765/?who=all"` — expected PASS, with 8 badges (7 + 1).
Run: `python3 tools/mesh_dirs.py "http://127.0.0.1:8765/?who=all"` — expected PASS.

**Note:** at this point `?who=all` renders both chains as two *unconnected* roots. They will overlap or scatter, because nothing yet places one relative to the other. That is expected — Task 6 connects them. Screenshot it anyway and look, so you know the starting point.

- [ ] **Step 9: Commit**

```bash
git add index.html tools/test.js
cat > /tmp/m.txt <<'EOF'
feat: assemble every chain into one TRAIN, behind ?who=all

TRAIN spans every person on stage; SITES and the seating go per person, since
PAIR_SLOTS names wheel indices WITHIN a chain and reading them globally straddles
a boundary. TEETH_SUM comes from the spine, not the wheel count -- a branch adds
cross-axis height, not length.

The default page is untouched: 0 px vs 439c9ba. ?who=all shows both chains as
unconnected roots; bridges land next.
EOF
git commit -F /tmp/m.txt
```

---

### Task 6: Ghost idler bridges

**Files:**
- Modify: `index.html` (TRAIN assembly, `solve()`, `ghostSvg` selection by `role`)
- Modify: `tools/test.js`

**Interfaces:**
- Consumes: `STAGE`, `SPINE_LEN`, `parent`, `role`.
- Produces: `TRAIN` entries with `role: 'idler'`, drawn in the ghost palette, carrying no slug or engraving.

**Design constraints from the spec, restated so you do not have to re-read it:**
- Bridge idlers are **structural** — solved with the train, not added after the fit. Escape runs stay in `fitEscapes()`. Do not merge the two.
- Target gap **~2 wheel diameters**; **minimum one idler**, so chains never mesh directly.
- **Adaptive in portrait**: fewer idlers and a tighter gap. The gap gives; the wheels do not.
- The bridge bearing is **relative to `this._axisRot`**, never absolute screen degrees, or portrait breaks.
- **All bridges on the same side.**
- Attachment: prefer the spine; **cascade off a child when placement fails.** Rejected when there is no clear bearing, when it crosses another bridge/chain/escape run, when the bearing is too far off perpendicular, or when the legibility floor would be breached.
- **Quantise** the attachment and idler count, or a chain hops between wheels while a window edge is dragged (#55).
- **Hysteresis on the idler count.** `IDLERS_FOR` changes with orientation, so a
  viewport dragged across the threshold re-solves — and without hysteresis it will
  thrash between one and two idlers, adding and removing a whole wheel on every
  pixel of drag. Use separate thresholds for adding and removing (add the second
  idler at a wider cross axis than the one at which you drop it), and verify with
  the resize probe pattern from #67: drag 1440→1340 in 4px steps and assert the
  idler count changes at most once.

**Honesty about this task:** it is the least specified in the plan, deliberately.
The placement code cannot be written blind — it depends on how the existing nudge
loop behaves once a third mesh is asked of a wheel, which is only observable by
running it. What is fixed and non-negotiable is the constraint list above; the
implementer derives the code to satisfy it. If the nudge loop cannot place a
bridge without violating the non-crossing rule, **stop and report** rather than
loosening the rule — the fallback in the spec is stacked labelled rows, and that
is a decision for Charles, not for the implementer.

- [ ] **Step 1: Write the failing tests**

```js
test('every non-spine chain is reached through at least one idler', () => {
  /* Chains never mesh directly -- the bridge is what makes the drive legible. */
  ok(/role:\s*'idler'/.test(SRC), 'no idler role is ever assigned');
  ok(/MIN_IDLERS/.test(SRC), 'there is no floor on the number of idlers in a bridge');
});

test('an idler never carries a service, a badge or an engraving', () => {
  /* A ghost is anonymous by design language; that is the whole reason the bridge
     is made of them rather than of an unowned coloured wheel, which would look
     exactly like the blank-gear defect in #65. */
  const i = SRC.indexOf('if (!this._slugFor) {');
  const j = SRC.indexOf('const g = [], strands = []', i);
  ok(/t\.role !== 'link'/.test(SRC.slice(i, j)),
    'the seating block does not exclude idlers, so one could acquire a slug');
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npm test 2>&1 | grep -E "idler|bridge bearing"`
Expected: three FAILs.

- [ ] **Step 3: Insert idlers into TRAIN**

Extend the TRAIN builder from Task 5. For every person after the spine, emit idlers before their first link, parented into the chain, and parent their first link to the last idler:

```js
/* HOW MANY IDLERS BRIDGE A CHAIN TO THE SPINE. Never zero -- two chains meshing
   directly would read as one machine, and the bridge is what makes the drive
   visible. The target gap is about two wheel diameters, which is two idlers at
   the nominal tooth count; portrait takes fewer, because there the cross axis is
   the scarce one and the gap is what gives (the wheels do not). */
const MIN_IDLERS = 1;
const IDLERS_FOR = (portrait) => portrait ? MIN_IDLERS : 2;
```

Idler entries carry `role: 'idler'`, `person: null`, `slug: null`, and take their tooth count from the same deal bounds so they mesh by construction.

- [ ] **Step 4: Place bridges in `solve()`**

Give each idler a bearing of `this._axisRot + BRIDGE_BEARING`, where:

```js
    /* PERPENDICULAR TO THE SPINE, RELATIVE TO IT. The stage rotates by _axisRot in
       portrait, so an absolute bearing would keep the bridge horizontal and send
       it across the short axis -- exactly the #67 failure. All bridges take the
       same side, which is the ordering Charles chose over balancing the cross
       axis: growth goes one way and the spine sits at the top. */
    const BRIDGE_BEARING = 90;
```

The existing nudge loop already searches ±`step` for a clear bearing, so a bridge that cannot leave perpendicular will find the nearest clear angle. Add the "too far off perpendicular" rejection by bounding `step` for idler placement:

```js
        const isBridge = t.role === 'idler';
        const maxStep = isBridge ? BRIDGE_SWING : 60;
```

with `BRIDGE_SWING` derived from the bearing deal's own range (`ANG_MAX - ANG_MIN`), not a new tuned number.

- [ ] **Step 5: Draw idlers as ghosts**

Where `solve()`'s output is rendered, select `ghostSvg` for `role === 'idler'` and `gearSvg` otherwise. Idlers must get no badge — the badge loop already filters on `slug`, and idlers have none, so verify rather than assume:

Run: `python3 tools/verify_motion.py "http://127.0.0.1:8765/?who=all"`
Expected: badge count equals the number of **linked** wheels only.

- [ ] **Step 6: Cascade when the spine has no room**

Attachment is solved, not placed. Try each spine wheel in turn; on failure, try the wheels of already-placed chains. Quantise the result on the instance the way `_slugFor` is, so it survives a resize:

```js
      if (!this._bridgeAt) this._bridgeAt = solveBridgeAttachments();
```

- [ ] **Step 7: Run everything**

Run: `npm test` — expected 36 passed.
Run: `python3 tools/mesh_dirs.py "http://127.0.0.1:8765/?who=all"` — expected PASS. **This is the important one:** it proves the drive propagates through the idlers into the second chain with correct alternation.
Run: `python3 tools/pixel_regress.py --ref 439c9ba` — expected `0 px differ` (default page still solo).
Screenshot `?who=all` at 1440×900 **and** 390×844 and look at both.

- [ ] **Step 8: Commit**

```bash
git add index.html tools/test.js
cat > /tmp/m.txt <<'EOF'
feat: bridge chains with ghost idlers that also set the spacing

Idlers are structural -- solved with the train, because they decide where a chain
sits -- and distinct from the escape runs, which stay in fitEscapes. A ghost is
anonymous by design language, which is why the bridge is made of them rather than
an unowned coloured wheel: that would look exactly like the #65 blank gear.

Bearing is relative to _axisRot, never absolute, or portrait breaks (#67).
EOF
git commit -F /tmp/m.txt
```

---

### Task 7: Branch axis and escape runs per chain

**Files:**
- Modify: `index.html:1462-1470` (`fitEscapes` hosts and axis)
- Modify: `tools/test.js`

**Interfaces:**
- Consumes: `role`, `person`, `parent`.
- Produces: `fitEscapes()` emits one run per driven chain and two for the spine.

- [ ] **Step 1: Write the failing test**

```js
test('escape runs follow each chain axis, never its bridge axis', () => {
  /* A branch has TWO directions: the bridge runs perpendicular to set spacing,
     then the chain runs parallel to the spine. A run that followed the bridge
     would leave by the short axis -- the #10 and #67 failure. */
  const i = SRC.indexOf('fitEscapes()');
  const j = SRC.indexOf('applyRotation()', i);
  const frag = SRC.slice(i, j);
  ok(!/solved\.gears\[solved\.gears\.length - 1\]/.test(frag)
     || /chainAxis|perChain/.test(frag),
    'fitEscapes still takes the first and last gear of the whole train as its ends');
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `npm test 2>&1 | grep -A2 "escape runs follow"`

- [ ] **Step 3: Implement**

`hosts` becomes: for the spine, its two end wheels; for every other chain, its last wheel only. Each host's heading is **its own chain's** axis — first-to-last of that chain's linked wheels — falling back to `this._axisRot` when a chain has one wheel, which is the fix already shipped in #67 generalised.

The spine keeps both runs; a driven chain gets one, on the same side as the spine's trailing run. Asymmetric on purpose: the missing leading run is where the bridge attaches, so a driven chain visibly receives its power.

- [ ] **Step 4: Verify**

Run: `npm test` — expected 37 passed.
Screenshot `?who=all` at 390×844. **Both chains' runs must travel down the long axis, not across.** Compare against `/` in portrait, which is known correct.
Run: `python3 tools/pixel_regress.py --ref 439c9ba` — expected `0 px differ`.

- [ ] **Step 5: Commit**

```bash
git add index.html tools/test.js
cat > /tmp/m.txt <<'EOF'
feat: a branch has two axes -- bridge perpendicular, chain parallel

Escape runs follow the CHAIN axis, never the bridge axis. A one-wheel chain takes
the stage axis, generalising the #67 fix. The spine keeps both runs; a driven
chain gets one, on the same side, because the missing leading run is where its
bridge attaches.
EOF
git commit -F /tmp/m.txt
```

---

### Task 8: Host scoping, and make the combined stage the default

**This is the task that changes what `wozi.com` shows.** Everything before it is invisible to a visitor.

**Files:**
- Modify: `config.js` (add `STAGE_HOSTS`, narrow `PEOPLE[].hosts`)
- Modify: `index.html` (`STAGE` resolver, picker visibility)
- Modify: `tools/test.js`, `CLAUDE.md`

**Interfaces:**
- Consumes: `STAGE` from Task 5.
- Produces: final host behaviour.

- [ ] **Step 1: Write the failing test**

```js
test('stage hosts and solo hosts are disjoint, and every person has a solo host', () => {
  const conf = (function () { const w = {}; new Function('window', CFG_SRC)(w); return w.WOZI_CONFIG; })();
  ok(Array.isArray(conf.STAGE_HOSTS) && conf.STAGE_HOSTS.length,
    'config.js defines no STAGE_HOSTS, so nothing selects the combined stage');
  const bad = [];
  (conf.PEOPLE || []).forEach(p => {
    if (!(p.hosts || []).length) bad.push(`${p.slug} has no solo host`);
    (p.hosts || []).forEach(h => {
      if (conf.STAGE_HOSTS.indexOf(h) >= 0) bad.push(`${h} is both a stage host and ${p.slug}'s solo host`);
    });
  });
  ok(bad.length === 0, bad.join('\n      '));
});
```

- [ ] **Step 2: Run it to verify it fails**

- [ ] **Step 3: Update `config.js`**

Move `wozi.com`, `www.wozi.com`, `localhost`, `127.0.0.1` off Charles's entry into a new top-level `STAGE_HOSTS`. Charles keeps `charles.wozi.com`; Harper keeps `harper.wozi.com`. Document that adding a domain is still an ACM SAN, an alternate domain name and a Route53 alias — no deploy change.

- [ ] **Step 4: Update the `STAGE` resolver**

Order: explicit `?who=` first, then `STAGE_HOSTS`, then a person's solo hosts, then **fall back to the combined stage** rather than `PEOPLE[0]` — so a newly added alternate domain works before anyone edits config.

- [ ] **Step 5: Show the picker only on the combined stage**

At the picker block, add `STAGE.mode === 'all'` to the `people.length > 1` condition. A personal link should not advertise everyone else on the domain.

- [ ] **Step 6: Update `CLAUDE.md`**

Add the host model to the rulebook. `CLAUDE.md` already had `config.js` missing from its published list once (#59) — the same drift, so state the scoping explicitly.

- [ ] **Step 7: Full verification**

```bash
npm test
python3 tools/verify_motion.py "http://127.0.0.1:8765/"
python3 tools/verify_motion.py "http://127.0.0.1:8765/?who=charles"
python3 tools/verify_motion.py "http://127.0.0.1:8765/?who=harper"
python3 tools/mesh_dirs.py "http://127.0.0.1:8765/"
python3 tools/devices.py
python3 tools/a11y_audit.py
```

`pixel_regress` **will** differ against `439c9ba` now, by design — the default page changed. Re-baseline after review, and record the before/after screenshots in the changelog entry.

Screenshot at 1440×900, 390×844, 2560×1440 and 5120×1440, in both themes, and **look at every one**. The #65 report was incomplete because every gate passed while Harper's page rendered a gear the size of a wall.

- [ ] **Step 8: Commit and open a PR rather than pushing to main**

This one changes the live site's front page. Branch it:

```bash
git checkout -b feat/combined-stage
git add config.js index.html tools/test.js CLAUDE.md CHANGELOG.md
git commit -F /tmp/m.txt
git push -u origin feat/combined-stage
gh pr create --fill
```

---

### Task 9: The legibility gate

The gate that makes "wheels are allowed to shrink" safe rather than open-ended.

**Files:**
- Modify: `tools/test.js`

- [ ] **Step 1: Write the test**

```js
test('the configured chains still clear the legibility floors', () => {
  /* Wheels shrink as chains are added, which is accepted -- but the layout keeps
     working long after the page stops being readable. Three things fail first:
     the module-derived engraving band, MIN_MODULE on the epicyclic sets inside a
     wheel, and the hub badge covering the bore. This fails the build rather than
     letting the page quietly become unreadable. */
  const fit = fitRule();
  const totalWheels = page.TRAIN_LENS.reduce((a, b) => a + b, 0);
  const bad = [];
  [[390, 844], [1440, 900]].forEach(([w, h]) => {
    const longAvail = Math.max(w, h), crossAvail = Math.min(w, h);
    const r = fit(totalWheels, longAvail, crossAvail,
      page.MODULE * 16.3 * totalWheels, 210 * page.TRAIN_LENS.length);
    const bandPx = r.fit * page.MODULE * page.BAND_DEPTH;
    if (bandPx < 6) {
      bad.push(`${w}x${h}: engraving band renders at ${bandPx.toFixed(1)}px with `
        + `${totalWheels} wheels configured — under the 6px floor from #61`);
    }
  });
  ok(bad.length === 0, bad.join('\n      '));
});
```

- [ ] **Step 2: Verify it fails when it should**

Temporarily add four dummy people to `config.js` with 7 links each, run `npm test`, confirm the gate trips. Remove them and confirm it passes.

- [ ] **Step 3: Commit**

```bash
git add tools/test.js
cat > /tmp/m.txt <<'EOF'
test: fail the build before the page becomes unreadable

Wheels shrinking as chains are added is accepted; shrinking past the #61-#63
legibility floors is not. Proved by adding four dummy chains and watching it trip.
EOF
git commit -F /tmp/m.txt
```

---

## Verification Summary

Run before any push, in this order:

| Command | Gate |
|---|---|
| `npm test` | geometry, tree shape, seating, fit rule, legibility |
| `python3 tools/mesh_dirs.py <url>` | One Clock across every mesh |
| `python3 tools/verify_motion.py <url>` | motion, badges at ~0px, an `<svg>` per badge |
| `python3 tools/pixel_regress.py --ref <sha>` | 0 px for Tasks 1–7 |
| `python3 tools/devices.py` | layout across device profiles |
| `python3 tools/a11y_audit.py` | contrast, hit targets |
| **Screenshots, looked at** | both orientations, both themes, every chain |

The last row is not optional. Every automated gate in this repo passed while `?who=harper` rendered one gear the size of a wall.

## Known open questions

- **#71** — WebKit renders the linked train at 39% of the window against a 48% floor, pre-existing. If the research finds the WKWebView harness untrustworthy, the combined stage may need re-verifying there. It should not change the design.
- **Portrait crossover** — a two-idler bridge is estimated to sit at the shrink threshold with the *second* chain at 390×844. Estimated, not measured. Measure with `tools/devices.py` during Task 6 and adjust `IDLERS_FOR` before Task 8.
