# Multiple chains on one stage, joined by ghost idler bridges

Date: 2026-08-02
Status: design approved in conversation; not implemented, no issue filed yet
Supersedes: the "power take-off" draft of the same date, which attached chains
directly wheel-to-wheel. Ghost idlers do the same job better — see *Why idlers*.
Related: #65 (the blank-gear bug that surfaced this), #19/#44 (the ratio-cap
history that dictates the sizing fix), #61/#62/#63 (the rendered-pixel legibility
floors that bound the whole design), #10 (escape runs continue the train's axis),
#55 (seat once, not on every solve)

## The picture

```
~~~(o)-(o)-(o)-(o)-(o)-(o)-(o)~~~>     the spine — the longest chain
              |
             (g)                        ghost idlers: bridge and spacing
             (g)
              |
             (o)~~~~~~~~~~~~~~~~~>      a shorter chain, visibly driven
```

Chains run **parallel**. Bridges run **perpendicular**, made of ghost gears that
both transmit the drive and create the separation. One machine, several shafts.

## The problem this solves

`config.js` now carries two people: `charles` (7 links) and `harper` (1 link).
Only one chain is ever on stage. Charles wants all of them visible, driven by one
gear set.

There is also a live defect. A one-wheel chain scales to fill the viewport:

```
fit = max(0.28, min(LINK_SHARE * longAvail / longSolved,
                    crossAvail * CROSS_BLEED / crossSolved))
```

With one wheel both `longSolved` and `crossSolved` are a single wheel diameter,
so both terms explode. `?who=harper` renders one gear cropped off the top and
bottom of the page. Confirmed by screenshot. **No existing gate catches it** —
`verify_motion` asks whether things turn, `pixel_regress` asks whether they
changed, and a page-filling wheel passes both.

## Why idlers

Idler gears exist to bridge distance between two shafts and correct direction
without changing the ratio between the gears they connect. That is exactly this
job.

The first draft attached chains wheel-to-wheel, and an earlier draft before that
used a shared drive wheel belonging to nobody. The drive wheel was rejected
because it would carry no badge and no engraving — a deliberately blank gear,
visually identical to the #65 bug, where a wheel with no slug drew as a blank
gear and looked broken.

**A ghost has no such problem.** Grey, no badge, no engraving, no epicyclic
centre — and the page is already full of them. Anonymity is a ghost's established
visual language rather than a defect. The objection that killed the drive wheel
does not apply, and the bridge additionally provides the spacing, which a
wheel-to-wheel take-off did not.

## Why not a second module

Considered and rejected: "smaller gears with more teeth, with a transmission gear
converting between tooth counts."

- Tooth counts are already free and already vary. Ghost runs deal
  `min(26, 11 + k*2 + rnd()*8)` teeth against linked wheels of 13–19, and the
  conjugate-phase computation at `index.html:1965-1968` lands every tooth in the
  right space across the mismatch.
- What must match at a mesh is the **module**, not the tooth count. At fixed
  module `r = MODULE * teeth / 2`, so more teeth makes a gear *bigger*. "Smaller
  gears with more teeth" therefore means a finer module, and a fine-module gear
  cannot mesh with a coarse one. No gear converts module at a mesh; only a
  **compound gear** does — two gears of different modules on one shaft — and the
  conversion happens on the shaft.
- A finer module narrows the engraving band, which is module-derived
  (`bandIn = r - MODULE * (BAND_RISE + BAND_DEPTH)`), walking straight back into
  the #61–#63 floors. `harper@wozi.com` is a long string for a small wheel.

Single module throughout. A compound drive stays available later as its own
change if a visible transmission is ever wanted.

## Topology

### The spine is the longest chain

Not necessarily `PEOPLE[0]`. Ties break by `PEOPLE` order, so Charles wins at
equal length. On a solo host the single chain is trivially the spine.

### Attachment: prefer the spine, cascade on failure

Shorter chains attach **directly to the spine**. When a placement on the spine
fails, that chain **cascades off a child** instead.

```
preferred                          overflow
~~(o)-(o)-(o)-(o)-(o)~~>           ~~(o)-(o)-(o)-(o)-(o)~~>
     |        |                         |
    (g)      (g)                       (g)
     |        |                         |
    (o)~>    (o)~>                     (o)~~~~~~~~>
    2nd      3rd                        |
                                       (g)
                                        |
                                       (o)~~~~~~~>
```

This is *solved, not placed* — the rule the repo already uses for drive runs.

### What counts as a failed placement

"Space doesn't exist, or it looks odd", made testable. A candidate attachment is
rejected if any of these hold:

1. **No clear bearing.** The attachment wheel already carries two meshes; a third
   that cannot clear both fails. Uses the existing nudge loop.
2. **Crossing.** The bridge crosses another bridge, another chain, or an escape
   run. Uses the existing `segCross` / `segDist` rules.
3. **Bearing too far off perpendicular.** A bridge that must angle sharply to
   find room is what "looks odd" usually means. Bounded like the bearing deal is.
4. **Legibility floor.** Another sibling would push rendered wheels under the
   #61–#63 floors.

Fail any, and try the cascade.

### All bridges on the same side

Every chain hangs from the same side of its parent. Chosen deliberately over
alternating sides, for the clear ordering.

**Recorded cost:** alternating would split cross-axis growth two ways and roughly
double how many chains fit before wheels shrink. Same-side spends it all one
direction, and the spine sits at the top of the composition rather than its
middle. Accepted.

## Geometry

### A branch has two directions, not one

This is the structural correction that came out of "her chain needs a ghost chain
running off the same side as mine":

- the **bridge** runs perpendicular to the spine axis, and sets the spacing
- the **chain** then runs parallel to the spine
- **escape runs continue the chain axis, never the bridge axis**

Without this, a one-wheel branch's escape run heads *down the bridge* and off the
bottom of the screen — a horizontal machine with a vertical tail, which reads as
an S rather than as a machine continuing past the frame. That is precisely the
mistake #10 fixed.

It also disposes of a degenerate case properly. A one-wheel train has
`first === last`, so `axisDeg = atan2(0, 0) = 0` — an axis by accident. Under
this design a chain's axis is "parallel to the spine" by construction.

### Escape runs per chain

- The **spine** gets leading and trailing runs, as today.
- Every **other chain** gets **one** run, leaving the same side as the spine's
  trailing run.

Asymmetric on purpose: the missing leading run is where the bridge attaches, so
a driven chain visibly receives its power rather than trailing off in both
directions.

### Bridge bearing is relative, never absolute

The bridge bearing must be expressed **relative to the spine axis**
(`this._axisRot`), never in absolute screen terms. The page already rotates the
whole train by `_axisRot` and swaps axes via `alongX = w >= hgt`. Express the
bridge relatively and it rotates with the train for free — perpendicular to the
spine in both orientations.

### Bridge length: solved for a target gap

Centre distance between meshing gears is the sum of their pitch radii, so **the
gap is quantised by idler count and tooth counts**. It is not a number that can
be set directly; it is reached by choosing idlers.

- **Target: ~2 wheel diameters of clear space** where there is room. Typically
  two idlers. The chains read as two shafts of one machine.
- **Minimum: one idler.** Chains never mesh directly — the bridge is what makes
  the drive legible.

### Adaptive in portrait

Portrait has roughly half the cross-axis budget of a desktop, and the bridge
consumes cross axis by definition. **The gap gives; the wheels do not.** In
portrait, fall back to fewer idlers and a tighter gap to preserve wheel size.

Rationale: the #61–#63 legibility floors are stated in *rendered pixels*, and a
phone has the fewest pixels to spend. Wheel size is the scarcer resource there,
so it is the worst place to spend margin on whitespace.

**Threshold behaviour must be hysteretic.** Idler count changing with viewport
means a re-solve at the threshold; without hysteresis, dragging a window edge
across it will thrash between one and two idlers.

## When wheels start shrinking

**Decision: wheels shrinking is accepted** — the necessary cost of supporting more
chains, and the design generalises to N rather than being a two-person case.

Each branch grows the cross dimension, and `fit` takes the **min** of the long
and cross terms, so branches charge only against the cross term. Estimated from
the figures recorded at `index.html:1725` (`solved.w` ≈ 779.6 module units,
`solved.h` ≈ 209.1, over 4000 replayed deals), with a 16T wheel at 112 units:

| Viewport | Today | +1 chain (2-idler bridge) | +2 chains |
|---|---|---|---|
| 1440×900 landscape | long binds (1.44 vs 5.38) | long binds (1.44 vs 2.30) | **cross binds** (~1.24) |
| 390×844 portrait | long binds (0.84 vs 2.33) | **dead even** (0.84 vs 0.84) | cross binds |

So: two chains cost nothing on a desktop; shrinking arrives at the third person.
**On a phone a comfortable bridge is already at the crossover with the second
chain**, which is what the adaptive portrait gap exists to avoid.

Same-side stacking halves the headroom that alternating would have given.

**These are estimates off recorded averages, not measurements.** They must be
confirmed with the `tools/devices.py` sweep before the gap bounds are fixed.

### The real ceiling is legibility, not layout

The layout keeps working long after the page stops being readable. Three things
fail first, all of them recent work:

- **The engraving band is module-derived**, so it shrinks with the wheels, and
  `harper@wozi.com` is a long string. #61 restated every floor in rendered pixels
  precisely because solve-unit floors lie about this.
- **The epicyclic centres go first.** `MIN_MODULE = 1.8` floors the module of the
  gear set *inside* a wheel and is scored when the centre family is chosen.
  Shrink the host blank and the roomy sets stop being reachable — what
  `config.js` means by "the centres stop being legible well before the layout
  breaks".
- **The hub badge covers the bore**, already noted at `index.html:950` for the
  14- and 15-tooth wheels.

So the design scales to a handful of chains, and past that the honest mechanism
is the one `config.js` already names: *"beyond that the picker is doing the real
work, since only one chain is ever on stage at a time."* The stage is not the
answer for a large number of people; the picker is.

## Architecture: path becomes tree

Today `TRAIN` is a **path**, and the path is *implicit*: wheel *i* meshes wheel
*i−1*, and nothing says so. That assumption is baked in three ways — `g[i - 1]`
in the solver, the running `x, y, dir, phase` variables carried down the array,
and the deals comparing `cut[i]` to `cut[i-1]` to mean "the wheel next to me".

The change is to make the parent **explicit**.

### Data

Each `TRAIN` entry gains:

- `parent` — index of the wheel driving it; `null` for the root
- `person` — owning chain, for seating and labelling; `null` for a ghost idler
- `role` — `link` or `idler`

Bridge idlers are entries in `TRAIN` like any other wheel. They carry no slug, no
badge and no engraving, and they are drawn in the ghost palette.

### Two classes of ghost, kept distinct

- **Structural idlers** — solved *with* the train, because they decide where a
  chain sits.
- **Escape runs** — computed *after* the fit in `fitEscapes`, in screen space,
  re-solved on resize, exactly as today.

These must not be merged. Name the distinction in the code so nobody later tidies
them back together.

### `solve()` changes

Around `index.html:1906-1972`:

| Today | Becomes |
|---|---|
| `let x = 0, y = 0, dir = 1, phase = 0` carried across the loop | derived from `g[t.parent]` per wheel; no running state |
| `if (i > 0)` | `if (t.parent != null)` |
| `const prev = g[i - 1]` | `const prev = g[t.parent]` |
| `if (oi === i - 1) return false` | `if (oi === t.parent) return false` |
| `chainFrom = i - 1` | `chainFrom = t.parent` |
| `dir = -prev.dir` | unchanged once `prev` is the parent — rotation propagates down the tree |

The conjugate-phase computation already reads `prev`, so it needs no change
beyond `prev` meaning the parent.

**`ENDS_APART` needs redefining.** Today: "the two ends of the train repel each
other, so the run reads as a line of machinery rather than a closed ring", as
`oi === 0 && i === TRAIN.length - 1`. A tree has more than two ends. Becomes: the
leaves repel each other and the root.

**The centroid rule is unaffected** — the dot ≤ 0.15 test applies only to `linked`
strand runs, and no shipped entry carries a `link`.

**Attachment and bridge choices must be quantised**, like slug seating in #55 and
the escape runs today. Otherwise a chain jumps between attachment wheels while a
window edge is dragged.

### Deals that assume adjacency by index

Three deals treat "index *i−1*" as "the neighbouring wheel":

- **`dealTeeth`** rejects twins with `cut[i] === cut[i-1]` — must compare parent
  to child.
- **`dealAngles`** alternates bearing signs by index parity and walks *i−1 → i*
  for the drift band — must follow parents, and each chain needs a starting
  bearing off its bridge.
- **`dealColours`** scores hue separation over `pick[i-1]` vs `pick[i]` — wheels
  are only confused with the ones *beside* them, so the 40° rule applies across
  parent/child pairs, not adjacent slots. Idlers are excluded; they are ghosts.

**`TEETH_SUM` semantics shift.** It is `round(16.3 * TRAIN.length)` and holds the
train's overall *length* near the original. With branches, wheel count overstates
the span — a branch adds cross-axis height, not length. It should derive from the
**longest root-to-leaf path along chain wheels**, excluding idlers.

## Hosts select a scope, not just a person

```
wozi.com / www / localhost / 127.0.0.1  ->  combined stage, all chains
charles.wozi.com                        ->  Charles alone
harper.wozi.com                         ->  Harper alone
?who=<slug>                             ->  that person, solo
?who=all                                ->  combined stage
hostname matching nothing               ->  combined stage
```

One rule: **a person's subdomain is that person; the apex is everyone.**

- `PEOPLE[].hosts` becomes that person's **solo** hosts only. Charles's entry
  loses `wozi.com`, `www.wozi.com`, `localhost` and `127.0.0.1`, keeping
  `charles.wozi.com`.
- A new top-level `STAGE_HOSTS` carries the combined-stage hostnames.
- The fallback changes from `PEOPLE[0]` to the combined stage, so a new alternate
  domain name works before anyone edits config.
- **The picker appears only in the combined view.** A personal link should not
  advertise everyone else on the domain. This extends the existing rule ("hidden
  while there is one person") to "…or while the view is deliberately one person".

Solo is not a separate rendering path — one chain is a tree with no branches,
which is a path. `solve()` needs no special case, and no bridge is built.

**This makes the px cap a prerequisite.** `harper.wozi.com` *is* the one-wheel
case. The feature cannot ship without the sizing fix.

Upside: `dealCentres` guarantees exactly one planetary per load, so on a one-wheel
chain that wheel *is* the planetary. Capped to a sane size with escape runs
filling the rest, a solo page becomes one showpiece gear in a field of background
machinery — better than a scaled-up seven-wheel layout.

### Deploy and infrastructure

No deploy change. Selection is client-side from `location.hostname`, the HTML is
byte-identical for every domain, and one cached CloudFront object serves them all
— the property `config.js` already documents. Adding a domain remains an ACM SAN
in us-east-1, an alternate domain name on the distribution, and a Route53 alias.

**Before `harper.wozi.com` goes live:** it publishes `harper@wozi.com` as a
`mailto:` where address harvesters will find it. That is already true of
`charles@wozi.com`, so it continues the existing posture rather than creating a
new exposure — but it is a decision about someone else's address and should be a
deliberate one.

## The sizing fix

Per `index.html:1739`, in Charles's own words after #19 and #44:

> If a size cap is ever wanted again it must be an ABSOLUTE wheel size in px, not
> a multiplier on a ratio, or this recurs a fourth time.

An absolute ceiling on rendered wheel diameter in pixels, applied after the
existing `fit`. Not a ratio, not a multiplier — those were capped at 1.15, then
1.55, then 1.25, each fixing the bug and reintroducing it further out, because a
ratio grows with the viewport so any constant is crossed at *some* width.

The 0.28 floor stays a floor. `LINK_SHARE` still binds at every width, preserving
the width-invariance established in #44: the cap engages only when the solve is
small enough that a wheel would otherwise exceed a sane physical size — precisely
the short-chain case.

**The value is measured, not chosen** — swept across viewports and chain lengths,
and recorded with its measurement, the way the 2.6 sweep was.

## Testing

Added to `tools/test.js`, which reads its constants out of `index.html` so it
measures what ships:

1. **The tree is well formed** — exactly one root, every non-root's parent
   exists, no cycles, every wheel reachable.
2. **Rotation alternates across every mesh** — `dir === -parent.dir` for every
   parent/child pair. The "One clock" invariant on a tree, and the change most
   likely to break silently: a wrong direction still animates smoothly.
3. **Every wheel of every chain gets a service seated on it** — the #65 test,
   over per-person slot ranges. Idlers are exempt and must be *asserted* exempt,
   so an idler never acquires a slug.
4. **No two meshing wheels share a tooth count** — the twins rule, parent-based.
5. **Hue separation across parent/child pairs**, idlers excluded.
6. **Every chain's escape run leaves along its chain axis**, never its bridge
   axis — the #10 rule, generalised.
7. **The absolute wheel-size cap holds** across a viewport and chain-length
   sweep, including a one-wheel chain.
8. **Legibility floors survive the chain count** — with N chains, the rendered
   band and the reachable centre sets still clear the #61–#63 floors. This is the
   gate that makes "wheels may shrink" safe: the page fails a test rather than
   silently becoming unreadable.
9. **Both orientations** — every geometric assertion runs at a landscape and a
   portrait viewport, since the bridge is the first feature whose cost differs
   materially between them.

Beyond the suite, required by CLAUDE.md:

- `verify_motion` on the combined stage and each `?who=` view.
- `pixel_regress` — expected to differ substantially, since the layout changes by
  construction. The useful comparison is before/after by eye, then 0 px against
  the new baseline once settled.
- **Screenshots, looked at, in both orientations.** The #65 report was incomplete
  because every gate passed while Harper's page rendered one gear the size of a
  wall. No automated check in this repo asks whether the picture is the right
  size.

## Order of work

1. **The px cap** — standalone, fixes a live defect, unblocks everything else.
2. **Path → tree** — explicit parent, solver, direction, the three deals.
3. **Ghost idler bridges** — structural idlers, attachment solving, the adaptive
   portrait gap.
4. **Host scoping** — the config split and selection logic.
5. **The legibility gate** — what makes shrinking safe.

## Fallback

If bridged branching fights the non-crossing solver badly enough, fall back to
stacked labelled rows: independent solves, one shared scale, no tree. Cheaper,
less faithful to "one set powers both chains", and it still satisfies every
decision recorded below.

## Decisions settled

| Question | Answer |
|---|---|
| How chains connect | Ghost idler bridges — transmit drive *and* create spacing |
| Why not a drive wheel | It would be a deliberately blank gear, like the #65 bug |
| Why not a second module | Gears mesh only at equal module; finer module breaks the band |
| Spine | The longest chain; ties break by `PEOPLE` order |
| Attachment | Prefer the spine; cascade off a child when placement fails |
| Bridge side | All the same side — ordering chosen over balance |
| Chain orientation | Parallel to the spine; bridges perpendicular |
| Escape runs | Spine gets both ends; every other chain gets one, same side |
| Target gap | ~2 wheel diameters, minimum one idler |
| Portrait | Adaptive — the gap gives, the wheels do not |
| Wheels shrinking | Accepted, as the cost of more chains |
| Scope | Generalise to N chains |
| Host scoping | A person's subdomain is that person; the apex is everyone |
| Picker on a solo page | Hidden |
| Sizing fix | Absolute px cap, measured not chosen |
