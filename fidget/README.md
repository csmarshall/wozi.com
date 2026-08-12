# `/fidget` — a double planetary you can spin

GitHub #123. One standalone page, `fidget/index.html`, loading nothing from
`support.js` or `config.js`. It draws its own gears and integrates its own
physics.

**Charles's decision, recorded on the issue: ring fixed, coasts to REST.** Both
ring gears are grounded, the sun and the final carrier are the two free ports,
and a spin ends at a genuine stop rather than settling back to an idle rate.

**A second grounding is implemented as of GitHub #129 and is now reachable four
ways** — a vertical swipe off the gear, the `ground` button, `g`, and
Shift+Up/Down. `GROUNDED` is still one word in the source (`'ring'`) and it is
now only the *starting* grounding rather than the only one. See *The other
grounding* below for the algebra and for what it costs the page's own claim, and
*One set at a time* for the layout the swipe arrived with. Everything in the
sections before those is stated for ring-grounding, which is what boots.

This file records every number the page chose and why, so none of them is a
mystery later. Nothing below is measured-and-forgotten: each is either derived
in the source from something else, or named here as a chosen shape figure with
the reason it sits where it does.

---

## The gearing

| | sun | planet | ring | planets | stage ratio |
| --- | --- | --- | --- | --- | --- |
| set 1 | 24 | 18 | 60 | 3 | **3.5000 : 1** |
| set 2 | 18 | 21 | 60 | 3 | **4.3333 : 1** |

Set 1's carrier is set 2's sun — one shaft. That is what makes it a *compound*
(double) planetary rather than two sets standing next to each other.

**Overall, sun → final carrier: 15.1667 : 1.**

Two constraints hold per set and both are **asserted at load**, not trusted;
either one violated describes a machine that cannot be built, and the page
throws rather than drawing it:

- coaxial: `N_ring = N_sun + 2·N_planet` — 24+36=60, 18+42=60
- equal planet spacing: `(N_sun + N_ring) % planets == 0` — 84/3, 78/3

A third check runs on the kinematics themselves: Willis is solved for each set
and **the grounded member's speed must come out at exactly zero**. If it does
not, the algebra is wrong and everything drawn from it is decoration. There is
one such check per grounding and each takes the long way round to the member it
is checking — `ringCheck` reaches the ring through the planet-ring internal mesh,
`sunCheck` reaches the sun through the sun-planet external mesh — so neither is a
restatement of the line that set the speed in the first place. Both were
mutation-tested: perturbing either stage ratio by one part in a million throws.

### Why these counts and not others

- **Both rings are 60.** Same module, so both sets draw at the same diameter and
  the page is symmetric without any layout number saying so.
- **The ratio spread is the point.** 3.5 × 4.333 gives 15.17:1, so reflected
  inertia between the ports is **230×**. Anything much lower and the two ports
  stop feeling different; much higher and the carrier stops responding to a
  finger at all within one gesture.
- **Set 2's planet count is odd (21) and set 1's is even (18).** Not deliberate,
  but it exercised both branches of the assembly-phasing rule below, which is
  how that rule got written correctly.

### Assembly phasing (why the drawn teeth actually mesh)

`gearPath` puts a tooth centre at each wheel's own angle zero, so left alone,
two wheels present a tooth to each other at the line of centres and
interpenetrate. Working in tooth-index coordinates `t(a) = (a − β)·N/2π`
(material at integers, space at half-integers), with the sun pinned at `β = 0`:

- **planet:** `β_p = −π/N_p` when `N_p` is even, `0` when odd.
- **ring:** takes whichever of tooth/space the planet is *not* presenting at
  their own contact — `0` for an even planet, `−π/N_r` for an odd one.
- **planet k at orbit angle θ:** local spin phase `θ·N_s/N_p`. A planet moved
  round to θ is the same machine with the sun held and the carrier wound on by
  θ, so its own spin has advanced `θ(1 + N_s/N_p)`; inside a group already
  carrying θ, that leaves `θ·N_s/N_p`. The equal-spacing check is *exactly* the
  condition that the same motion returns the ring to its own zero.

Nothing here is a fudge factor — remove the derivation and the teeth clash.

---

## Inertia — the thing that has to land

State is angular momentum, not angle. Every moving body has a moment of inertia
and the train is reduced to one degree of freedom (it is fixed-ratio, so it has
exactly one) by `J_eff = Σ J_i (ω_i/ω_sun)²`.

**Disc inertia is `∝ r⁴/2`**, derived, not tabulated: `J = ½mr²` with `m ∝ r²` at
constant thickness and density. The absolute constant is arbitrary because only
*ratios* of inertia matter, which is precisely why the page can be honest about
reflected inertia without inventing kilograms.

A planet contributes **twice** — its own spin, and its mass carried round at the
carrier's speed (parallel axis). Both terms are real, and **the orbital term is
exactly twice the spin term, which is a theorem rather than a proportion that
happens to land**: a planet rolls on whichever of the sun and the ring is
stationary, so its instantaneous centre is at that contact and the distance from
there to its own axis is its pitch radius, giving `r_p·ω_p = orbitR·ω_c`. The spin
term is `½m·r_p²·ω_p²` and the orbital term is `m·orbitR²·ω_c²`, so that identity
collapses them to exactly 1:2. It holds in both groundings, and would stop holding
if the carrier were the grounded member.

**The half in `disc` was missing until #129, and is now corrected.** `disc(r)` was
`r⁴`, which stands for `J = m·r²` rather than `½m·r²` — harmless while every disc
body shared the one arbitrary constant, and *not* harmless the moment a body's
inertia is weighed against a **parallel-axis** term, because `m·d²` is the whole
of `m d²` and carries no factor to match. The two planet terms therefore came out
equal instead of 1:2. The fix is in `disc`, not on the orbital term: `m d²` is
exactly right as it stands, so the error was never there.

**Nothing the page *does* changes, and that is worth being precise about.**
`J_eff` enters the loop only as a scale — `HAND_STIFFNESS ∝ J_eff`,
`FLICK_IMPULSE ∝ J_eff`, and `accel = torque/J_eff` divides by it again — so it
cancels out of every rate and every angle the page produces, and the port ratios
below are `RATIO²` and do not involve `J_eff` at all. The cancellation is exact
rather than approximate — a flick adds
`flickImpulse / (J_eff × gear) = REF_SPEED × 0.75 / gear`, in which `J_eff` does
not appear — and it was checked as well as derived: alternating runs before and
after the correction sample **6.29 / 6.34 / 6.39 rev/s** against
**6.28 / 6.29 / 6.29 / 6.33 / 6.34**, one overlapping spread caused by where in
the coast the 150 ms sample lands, and the port figures are unmoved at 230.0× and
3.3×. What changed is the honesty of the numbers in these tables. **Found by
re-deriving for the second grounding**, not by anything going wrong.

**The grounded member contributes nothing**, because its speed is zero. That is
not a simplification; it is what "grounded" means. The sum is written over every
body and the zero does the work, so it is the same expression in both
groundings — which is why the ring's own rotational inertia is now modelled: it
was omitted before because a body at zero speed cannot be got wrong.

| contribution (sun-referred, arbitrary units) | set 1 | set 2 |
| --- | --- | --- |
| sun | 10 368 | 268 |
| planet spin (×3) | 4 374 | 273 |
| planet orbital (×3) | 8 748 | 547 |
| carrier | 2 778 | 110 |
| ring | 0 | 0 |
| **share of J_eff** | **95.6 %** | **4.4 %** |

`J_eff = 27 466`. Set 1 dominates because it turns fastest and the reduction
weights by the square of speed — which is the same square the whole page is
about, showing up first inside the train rather than at the ports.

**`CARRIER_THICKNESS = 0.35`** is the one inertia figure that is chosen rather
than derived: a carrier is a plate or a spider, not a solid gear blank, and
there is no other quantity on the page it could be computed from. It is one
number applied to both carriers by the same disc formula, rather than a
hand-written inertia each.

### The two ports

Inertia seen at a port is `J_eff × gear²` where `gear` is how many sun turns one
port turn is worth.

| port | gear | inertia | vs the sun |
| --- | --- | --- | --- |
| sun | 1 | 27 466 | 1.0× |
| carrier | 15.1667 | 6 317 983 | **230.0×** |

Neither 230 nor the square is written anywhere in the source. The square arrives
because a torque at a port maps onto the sun coordinate by dividing by `gear`,
*and* the port's angle is the sun's divided by the same `gear`.

---

## The other grounding — sun fixed

GitHub #129, and **Charles's call: it ships.** "The other format of planetary
gear" is **the same metal with a different member bolted to the world**: same
tooth counts, same wheels, same assembly, one substitution in one equation. It is
implemented and currently inert — `GROUNDED = 'ring'` in the source is the only
thing that selects between the two, and no gesture, key or URL parameter reaches
it yet.

Willis, with `ω_sun = 0` instead of `ω_ring = 0`:

```
(0 - ω_c) / (ω_r - ω_c) = -N_r / N_s
    ω_c · N_s = N_r · (ω_r - ω_c)
    ω_c = ω_r · N_r / (N_s + N_r)
    ω_r / ω_c = 1 + N_s / N_r
```

So the free ports are the **ring** and the **carrier**, and the reduction per set
is `1 + N_s/N_r` where ring-grounding gave `1 + N_r/N_s`. **That reciprocal is a
hard boundary, not a range.** Every buildable set has `N_r = N_s + 2·N_p`, so
`N_r > N_s` always, so sun-grounding can never reduce by as much as **2:1** and
ring-grounding can never reduce by less than **3:1**. A grounding chooses which
side of that line the machine is on; it is not a knob along one scale.

| | sun | planet | ring | ring-grounded | **sun-grounded** |
| --- | --- | --- | --- | --- | --- |
| set 1 | 24 | 18 | 60 | 3.5000 : 1 | **1.4000 : 1** |
| set 2 | 18 | 21 | 60 | 4.3333 : 1 | **1.3000 : 1** |
| overall | | | | 15.1667 : 1 | **1.8200 : 1** |

Per-body speeds, per unit speed of the input port:

| | ring | carrier | planet | sun |
| --- | --- | --- | --- | --- |
| set 1 | 1 | 0.714286 | 1.666667 | **0** |
| set 2 | 0.714286 | 0.549451 | 1.020408 | **0** |

`sunCheck` closes back on those zeroes to 2.2e−16 and 0.0 exactly.

### The compound shaft has to move, and that is the one non-algebraic consequence

Under ring-grounding the shaft is **carrier 1 → sun 2**. Ground both suns and
that shaft would tie a grounded member to a moving one: set 1 would have its sun
*and* its carrier pinned, which is two constraints on a two-degree-of-freedom
set, and **the whole train would be a solid object**. So under sun-grounding the
shaft is **carrier 1 → ring 2**. A carrier tied to a ring is as much one coaxial
rotating member as a carrier tied to a sun, so the drawing's ONE SHAFT note stays
true without being restated — but it is a different shaft, and it is the reason
"just ground the other member" is not purely a substitution.

### What J_eff is made of now

The sum is unchanged as an expression — every body, weighted by the square of its
own speed — and the zero moved. The sun drops out, and **the rings now move, so a
ring's own rotational inertia matters and it was not modelled at all before**: a
body at zero speed cannot be got wrong. A ring is an annulus and inertia is
additive, so it is `disc(outer) − disc(inner)` under the same arbitrary constant
as everything else, with the inner bound at the pitch circle (the convention the
external wheels already take) and the outer at `RING_RIM`, which is now named once
and read by the outline, the page extent and the inertia — the inertia of the ring
that is actually drawn, not of a differently-sized one.

| contribution (ring-referred, arbitrary units) | set 1 | set 2 |
| --- | --- | --- |
| sun | 0 | 0 |
| planet spin (×3) | 27 338 | 18 984 |
| planet orbital (×3) | 54 675 | 37 969 |
| carrier | 17 364 | 7 639 |
| **ring** | **202 467** | **103 299** |
| **share of J_eff** | **64.3 %** | **35.7 %** |

`J_eff = 469 735`, against ring-grounding's 27 466. Two things flip. The rings are
**nearly two thirds of the whole train's inertia** — they are the biggest wheels on
the page and they were previously free — and the stage shares even up (64.3 / 35.7
against 95.6 / 4.4), because the reduction is now shallow enough that stage 2 is
not squared into irrelevance.

### The page's own claim, weakened — plainly

| | ring-grounded | sun-grounded |
| --- | --- | --- |
| overall ratio | 15.1667 : 1 | 1.8200 : 1 |
| `J_eff` (arbitrary units) | 27 466 | 469 735 |
| inertia at the input port | 1.0× | 1.0× |
| inertia at the carrier | **230.0×** (`RATIO²` = 230.0278) | **3.3×** (`RATIO²` = 3.3124) |
| grip response period, input | 0.105 s | 0.105 s |
| grip response period, carrier | 1.588 s (**15.2×**) | 0.191 s (**1.8×**) |

**The claim does not invert, but it goes quiet.** The square law is intact and is
still the only thing producing either number — 230.0 and 3.31 are both `RATIO²`,
and neither is written down. But 3.3× is a difference a hand can *just* notice and
230× is one it cannot miss, and the two ports at 0.191 s against 0.105 s are close
to feeling like the same port.

**This is inherent and was accepted knowingly** — Charles's call, "let the drop be
the point", recorded here because it is exactly the kind of thing that gets
re-litigated as a bug later. **Sun-grounding cannot be made louder by choosing
different teeth.** `N_r = N_s + 2·N_p` in every buildable set, so `N_r > N_s`
always, so `1 + N_s/N_r < 2` always: a sun-grounded stage can never reduce as much
as 2:1 and can therefore never reflect more than 4×, however many stages are
compounded at whatever counts. A swipe between these two is a swipe from two very
different ports to two similar ones, with the ratio visibly the only thing that
changed — which is the demonstration rather than a shortfall in it.

---

## One set at a time, and what the shaft became

GitHub #129 parts 3 and 4, and Charles's call: **the page shows one gear set at a
time, filling the window.** The physics did not move an inch for this — `MODE.ratio`,
`MODE.jEff`, every body speed and every number in the readout are the compound
machine's, summed over both stages, and none of them asks what is on screen.
`VIEW` is a camera position.

**The `ONE SHAFT` tie survives as a stub, and it is the control that travels along
it.** That was the decision worth arguing, because the tie is not decoration: stage
1's carrier *is* stage 2's input member, and that is the whole difference between a
compound set and two sets standing next to each other. Three alternatives were
rejected:

- **Delete it.** The page would draw a single epicyclic while the readout went on
  quoting 15.167:1 for a train it no longer shows.
- **A stub with a caption and nothing else.** The tie then points at a stage that
  cannot be reached, and the heavy port — which *is* the demonstration — becomes
  button-only. Following a shaft to the other end of it is what a shaft is for.
- **Draw the two sets concentrically.** Rejected when the page was first built:
  the two orbit radii are 21 and 19.5 units, so the teeth interleave into an
  unreadable mess. Nothing about #129 changes that.

So the stub runs from the visible set's rim off the edge of the window, and a tap,
Enter or Space on it walks to the other stage. It keeps `S.angle` and `S.rate` —
that is the difference between `useView()` and `useGrounding()`. A grounding swap
picks up a *different machine* and its coordinate has to start again; walking down
one shaft is the same machine seen from somewhere else, so a train spinning down
keeps spinning down and every re-drawn body lands on exactly the phase it would
have been at had it been on screen all along.

Every number in the stub's layout is measured or derived, none chosen by eye:

| figure | value | why |
| --- | --- | --- |
| the stub's bearing | **along the window's long axis** | The viewBox is square and `meet` letterboxes it, so the unused space is a band either side in landscape and above and below in portrait. A root `<svg>` clips at its element box, not its viewBox, so the stub runs out into that band and is cut by the window edge. Send it the other way and it is clipped instantly. |
| `SHAFT_INK` / `SHAFT_TARGET` | **0.4 units / 0.2 × R** | Two numbers on purpose: 0.4 is a legible dashed note and an impossible target. The hit width is a share of the ring's radius, so it lands at **63px** on a 1440×900 desk and **27px** on a 390-wide phone where the whole drawing is 4.6× smaller — the drawing's own proportion, not a pixel figure. |
| the label | **longest of three phrasings that fits** | Measured with `getComputedTextLength`. The band is 405px beside a 1440×900 window and 133px beside a square one, so one phrasing is either cut in half at the first or needlessly terse at the second. Its budget is the band less the chrome strip's own measured height, because the chrome floats *over* the stage (CL#156). |
| the caption | **on the side the shaft does not leave by** | In portrait they share an axis and a stub leaving upward would be drawn through the caption's letters. Landscape never collides, so the caption stays above. |

**Two things here were caught only by a picture**, and both are recorded in the
source because the numbers were right while the drawing was wrong. The rotated
portrait label had its anchor copied from the landscape branch, and the rotation
already carries the direction there — so it read back down over its own gear. And
the arrow is a glyph *inside* the rotated label, so a `↑` turned with it renders
pointing **left**; the rotated branch writes `→` and lets the rotation point it.

**The gear fills 0.700 of the window's shorter edge**, at every viewport, and that
is `R / (R + margin)` with the margin unchanged from the two-set layout. It is up
from 527px to **630px** across on a 1440×900 desk, and the composition's ink is
down from 274,242 to 202,563 pixels — one set instead of two, drawn larger. The
margin is symmetric because the viewBox is, which is what centres the gear; it
holds one line of caption and is generous, so **how much of the window the gear
should fill is a live question and not a settled number.**

---

## Losses

The three-term coast-down the landing page arrived at over four iterations
(CL#127 → CL#139 → CL#141), reused as a **shape**:

```
retarding rate = COULOMB + VISCOUS·|ω| + WINDAGE·ω²
```

Each term earns its place, and the two failure modes sit at opposite ends of one
axis:

- **Coulomb alone** is a constant retarding torque — literally a friction brake.
  It sheds speed at the same rate at 12 rev/s as at 0.1, ramps down a straight
  line and stops at a corner. CL#127's shipped model, and CL#139's complaint.
- **Viscous/windage alone** is an exponential. It never arrives, and how long it
  takes stops depending on how hard you threw it. #106's complaint.

**Coulomb is kept here precisely BECAUSE this page coasts to rest** — it is the
residue that makes a stop happen in finite time instead of asymptotically. On
the landing page the flywheel returns to an idle rate and the term is doing
subtler work; here it is what a stop *is*.

| figure | value | why |
| --- | --- | --- |
| `DRAG_RANGE` | **60** | CL#141's shipped value. How much harder it retards at the top of the range than at rest. At 1 the terms collapse to a constant (the brake); very large kills the Coulomb residue (the exponential). 60 is where "free-feeling" lands: low drag at speed, falling steeply as it slows. |
| `WINDAGE_SHARE` | **0.10** | CL#141's correction. Air drag on a disc only dominates at genuinely high rpm; at these speeds bearing losses do. A high windage share also fights the brief: the square term bites hardest where a thrown wheel is *fastest*, so it takes the gratifying part of the spin away first. |
| `COAST_RANGE_S` | **9.0 s** | The one feel figure, and the only one to turn if the coast feels wrong. How long a firm flick of the sun takes to reach a dead stop. Shorter than the landing page's 15 s because there is one machine here rather than a chain of them, and because a fidget is spun repeatedly. **A placeholder for Charles's call.** |
| `REF_SPEED` | **12 rev/s at the input port** (75.40 rad/s) | The speed the coast figure is quoted at. Named once so the solver, the flick strength and the speed clamp mean the same thing. Quoted at the *port* rather than at the sun so it means the same thing in both groundings: the losses are a deceleration of the generalised coordinate, and the coordinate is the input port by construction, so a coast takes `COAST_RANGE_S` whichever member the finger is turning. The bearings do not know what is bolted down. |

**The scale is solved, not chosen.** The two shape figures fix the split between
the three terms; the overall scale is bisected against a Simpson integral of
`1/decel` so a coast from `REF_SPEED` takes exactly `COAST_RANGE_S`. The closed
form loses precision as the windage share goes to zero, which is why it is not
used. A few hundred multiplications, once, at load.

Solved values: `COULOMB 0.6153`, `VISCOUS 0.4333`, `WINDAGE 6.385e−4` rad/s².
Deceleration is **0.615 rad/s² at rest against 36.9 at `REF_SPEED` — a factor
of 60.0**, which is `DRAG_RANGE` recovered from the solve. At full speed the
terms split 1.7 % Coulomb / 88.5 % viscous / 9.8 % windage.

**Losses are expressed as a deceleration rather than a torque, and that is not a
shortcut.** The train is fixed-ratio, so `J_eff` is a constant, and a retarding
torque and a retarding acceleration differ only by that constant. Writing it as
a rate means the coast time does not silently change when a tooth count does.

---

## The hand

A finger is not a velocity source. Modelling it as one — the body tracks the
pointer exactly — would make both ports feel identical, which is the one thing
this page must not do. So a drag imposes an angle and the grip pulls the body
toward it through a **spring and a damper**. The light port snaps to the finger;
the heavy port has to be wound up. That lag *is* the reflected inertia.

| figure | value | why |
| --- | --- | --- |
| `HAND_FREQ` | **60 rad/s** | The undamped natural frequency of grip-on-*input-port*. Stiffness is derived from `J_eff` rather than picked against it, so a tooth-count change — or a grounding change, which moves `J_eff` by 18× — leaves the input port tracking the finger the same way. |
| `HAND_DAMPING` | **0.28** | Damping ratio, the same at either port. Low enough that a flick still throws; high enough that neither port oscillates about the finger. |

`HAND_STIFFNESS = HAND_FREQ² × J_eff = 9.888e7` (ring-grounded; `1.691e9`
sun-grounded, because `J_eff` is 17× larger there — and it makes no difference to
how anything feels, which is the point of deriving the stiffness from the inertia
rather than picking it). At the carrier the same stiffness gives
`60 / 15.1667 = 3.96 rad/s` — a **1.59 s** response period against the sun's
**0.105 s**, a 15× difference your hand notices immediately.

`FLICK_IMPULSE = J_eff × REF_SPEED × 0.75` — a firm flick of the sun, so the
buttons and the arrow keys reach the same integrator a finger does and nothing
else.

---

## Measured

Headless Chrome over CDP, driving real pointer events.

| | result |
| --- | --- |
| identical 180° sweep over 1.5 s at the **sun** | port followed **181.9°** — tracking **101 %** (slight overshoot; ζ=0.28 is deliberately lively) |
| the same sweep at the **carrier** | port followed **62.2°** — tracking **34.6 %** |
| same impulse at each port, peak sun speed | 8.17 vs 0.58 rev/s (**14.1×**; the theoretical 15.17 less what losses took in the 50 ms sampling window) |
| bodies advancing 700 ms apart after a flick | **8 of 10** transform groups, in *both* groundings — the 2 static ones are the set's own translate and the **grounded** member's assembly-phase rotation, which is correct. (It was 16 of 21 while both sets were drawn.) The static rotation moves from the ring to the sun when the grounding does: ring `rotate(0.000)` → `rotate(0.000)` and sun `rotate(0.000)` → `rotate(1926.339)` under ring-grounding, exactly swapped under sun-grounding. That is the swap visible in the DOM |
| coast from a sun flick | **AT REST after 8.0 s** (a 0.75× `REF_SPEED` flick against a 9.0 s figure quoted at `REF_SPEED`) |
| `S.angle` zeroed on a grounding swap | **verified in the DOM, not assumed.** After a swipe every body reads `rotate(0.000)` or its own assembly phase and nothing else — set 2's ring lands on `rotate(-3.000)`, which is `-π/60` exactly, its `ringPhase` for a 21-tooth planet. `useGrounding()` already did this; it needed checking rather than trusting |
| the swipe, driven as real pointer events | threshold **108px** at 1440×900 (0.12 × the shorter edge). 88px vertical: **no swap**. 400px horizontal: **no swap**. Diagonal dy −150 / dx 300: **no swap**. A tap: **no swap**. A 300px vertical drag **starting on the gear**: no swap, and the sun goes from +7.03 to −7.62 rev/s, so it span the train instead. 200px vertical off the gear: **RINGS → SUNS**, and again back. One 700px drag: **one swap**, not several |
| `g` and Shift+Up/Down on the focused drawing | swap; unmodified Up/Down still flick the input port |
| console, both groundings, through every gesture above | **0 messages** — no errors, no warnings, no exceptions. (Served over HTTP; the `/favicon.ico` 404 the earlier note mentions is the harness's own static server, and this run logged none) |
| `npm test` | **119 passed, 0 failed** — it reads the root `index.html` and is untouched by anything here |
| root page pixel gate | **0 px differ** at 1440×900 and 390×844, which is the check that this folder stayed inside itself |
| `/fidget/` pixel gate vs HEAD | **402,810 px** at 1440×900 and **99,083 px** at 390×844 (31.1% and 30.1% of the frame). Deliberate: it is the whole composition moving. Attributed rather than accepted — ink 274,242 → 202,563 px at desk and 82,577 → 51,527 on the phone, the change split evenly top/bottom, which is one set instead of two rather than one band shifting |

---

## Project rules this page is held to

From `CLAUDE.md`, and none of them optional:

- **No CSS animation or transition on anything that turns.** One
  `requestAnimationFrame` loop integrates one state — the input port's angle and
  rate — and every body's transform is derived from it each tick. Independent
  animation drifts out of mesh within seconds (#3). The second grounding adds no
  second clock and no branch inside the loop: a ring is a mover unconditionally,
  at whatever rate the grounding gave it, and that rate is zero when it is the
  member being held.
- **Inline styling, no classes for layout.** The `<style>` block carries palette
  tokens and nothing else, exactly as `index.html`'s does.
- **No hardcoded geometry.** Radii, orbit distances, tooth pitch, page spacing
  and every inertia come off the tooth counts and `MODULE`.
- **Both themes**, using `index.html`'s token names. The tokens are *copied*
  rather than imported, because sharing a stylesheet is the coupling this page
  is deliberately avoiding — if `index.html`'s `:root` moves, these should move
  with it.
- **Touch first.** Pointer events cover mouse, touch and pen on one path, and
  `touch-action: none` plus `overscroll-behavior: none` stop the browser's own
  pan from stealing the gesture. Verified in portrait at 390×760.
- **The accessibility story survives a mode swap.** The `aria-label` is rewritten
  from `MODE` and from `VIEW` on every rebuild — the grounding, the overall ratio,
  which set of how many is on screen, what dragging it turns, and how to reach the
  other grounding — because a label asserting fixed rings on a page whose suns are
  grounded is the page describing a machine it is not integrating. The shaft stub
  is a real `role="button"` with `tabindex`, its own label naming what is at the
  far end, and Enter and Space.
- **A gesture is not a keyboard route, so the grounding has three others.** The
  `ground` button (the discoverable one, labelled with what it will *do*), `g`, and
  Shift+Up/Down. The shift modifier is what keeps them off the flick keys: an
  unmodified Up or Down still throws the input port, and the modifier is tested
  first so one press can never fire both.

## Not decided here

- **Whether it ships, and at what path.** Nothing has been added to
  `.github/workflows/deploy.yml`, so this folder does **not** publish. The
  deploy is a whitelist and adding a file does not publish it.
- **`COAST_RANGE_S = 9.0`** is a placeholder for Charles's call, in the same
  sense `SPINDOWN_RANGE_MS` was in CL#127 and CL#141.
- **How much of the window the gear should fill.** It is 0.700 of the shorter
  edge, which is `R / (R + margin)` with `margin = R * 0.42` inherited unchanged
  from the two-set layout, where it also had to be reconciled against the gap
  between the sets. It now holds one line of caption and nothing else, and the
  viewBox is symmetric so the same clearance is left on all four sides to keep the
  gear centred. Tightening it makes the gear bigger everywhere; it is one
  expression in `layout()`, and it wants a picture rather than an argument.
- **Whether the swap should read as animated.** It is instant: the machine is
  re-solved and re-drawn in one tick. The obvious way to soften it is forbidden
  outright — no CSS transition may touch anything that turns (#3) — so any easing
  would have to be integrated in the one rAF loop, which is real work and a design
  question rather than a polish pass.
- **Whether the swipe needs an on-screen hint.** The `ground` button says what the
  gesture does but not that a gesture exists.

**Decided, so no longer open:** sun-grounding **ships** as the second format, with
the drop from 230× to 3.3× accepted knowingly — see *The other grounding* for why
it cannot be made louder. The parallel-axis ½ is **corrected**, not deferred. The
swipe reaches `useGrounding()`, and so do a button and two key bindings; the page
shows **one set at a time** and the `ONE SHAFT` tie is the control that walks
between them.
