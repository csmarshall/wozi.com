# Credits

The gear geometry on this page is hand-built, but the planetary work was not
done in a vacuum. This records what was learned where.

## What was actually taken

To be precise about it, because the distinction matters: **no code was copied
from any of these projects.** What was taken is a set of *design conditions* —
the relationships that decide whether a planetary gearset can be assembled at
all. Those are standard gear-engineering facts. They appear in textbooks
(Shigley, Norton), in manufacturer references (KHK), and in every open-source
gear generator, because they are properties of the mechanism rather than
anybody's invention:

| | condition | |
|---|---|---|
| C1 | `Zr = Zs + 2·Zp` | concentricity — the ring, planets and sun must share an axis |
| C2 | `(Zs + Zr) % N == 0` | assembly — N planets can only be equally spaced if this holds |
| C3 | `(Zs + Zp)·sin(π/N) > Zp + 2` | adjacency — neighbouring planets must not collide |
| C4 | `gcd == 1` | hunting tooth, for even wear — cosmetic here, reported and never enforced |
| C5 | ≥17 teeth at 20° PA | undercut limit — a soft floor here, since these teeth are stylised |

The value of the open-source generators was **cross-checking**: confirming that
the formulations used here match what working implementations actually enforce,
and learning which conditions the careless ones get wrong. C3 is the clearest
example — several generators ship only a weaker pitch-circle form that
under-rejects, and the tip-circle version used here came from comparing them.

The derivations that are specific to this page — the mesh-phase constants, the
star-arrangement rate factors, and the whole two-row (Ravigneaux) phase chain —
were worked out here and verified by measurement in `tools/`. Where an earlier
version of those was wrong, it was wrong in this repository's own way.

## Sources

- **chrisspen/gears** — <https://github.com/chrisspen/gears>
  (the Getriebe.scad / janssen86 lineage). Planetary constraint set; its
  adjacency check is the weaker pitch-circle form, which is what prompted
  checking C3 against KHK. *Licence: not clearly declared — GitHub reports
  `NOASSERTION`. Nothing was copied from it.*

- **hyperair/planetary-gears** — <https://github.com/hyperair/planetary-gears>
  Errors out on fractional planet teeth and on failed equal spacing, which is
  the cleanest statement of C1 and C2 found. *Licence: none declared. Nothing
  was copied from it.*

- **Emmett Lalish's Gear Bearing** — Thingiverse thing:53451
  (mirror read at <https://gist.github.com/mccv/646f4d65c8b6eebbd4ff3ac5f39683dd>).
  Satisfies C2 by construction rather than by filtering, which is a neater way
  to think about the assembly condition. *Licence: Thingiverse terms apply to
  the original; not verified here. Nothing was copied from it.*

- **BOSL2** — <https://github.com/BelfrySCAD/BOSL2/wiki/gears.scad>
  Undercut limits and profile shift, the source for treating C5 as a soft floor
  for stylised teeth. *Licence: BSD-2-Clause.*

- **madl3x/plgcalc** — <https://github.com/madl3x/plgcalc>
  A second opinion on the constraint set. *Licence: MIT.*

- **KHK Gears technical reference** — the neighbour condition in its tip-circle
  form (C3), which is the one this page enforces. Manufacturer documentation,
  not code.

- **Ravigneaux gearset** — named for **Pol Ravigneaux**, who patented the
  two-row arrangement in the 1930s; it is the layout behind most automatic
  transmissions. The kinematics here were derived from first principles, but
  the arrangement is his.

- The **star** arrangement used by the single-row set (carrier grounded, so the
  planets spin in place and the sun counter-rotates) is standard practice, with
  precedent in the ALF 502 turbofan reduction box and in automatics that brake
  the carrier for reverse.

## Notes for whoever reads this next

`docs/research/planetary-solver.md` has the long form: which source states which
condition, where they disagree, and why this page resolves the disagreement the
way it does. `docs/research/planetary-physics.md` covers the Willis-equation
derivations behind the rate factors.

The page itself carries no third-party code. Its only runtime dependency is the
React/Babel pair already loaded by `index.html`.
