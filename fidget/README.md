# `/fidget` — a double planetary you can spin

GitHub #123. One standalone page, `fidget/index.html`, loading nothing from
`support.js` or `config.js`. It draws its own gears and integrates its own
physics.

**Charles's decision, recorded on the issue: ring fixed, coasts to REST.** Both
ring gears are grounded, the sun and the final carrier are the two free ports,
and a spin ends at a genuine stop rather than settling back to an idle rate.

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
and the **ring speed must come out at exactly zero**. If it does not, the
algebra is wrong and everything drawn from it is decoration.

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

**Disc inertia is `∝ r⁴`**, derived, not tabulated: `J = ½mr²` with `m ∝ r²` at
constant thickness and density. The absolute constant is arbitrary because only
*ratios* of inertia matter, which is precisely why the page can be honest about
reflected inertia without inventing kilograms.

A planet contributes **twice** — its own spin, and its mass carried round at the
carrier's speed (parallel axis). Both terms are real and at these proportions
they come out nearly equal.

**Grounded rings contribute nothing**, because their speed is zero. That is not
a simplification; it is what "grounded" means.

| contribution (sun-referred, arbitrary units) | set 1 | set 2 |
| --- | --- | --- |
| sun | 20 736 | 536 |
| planet spin (×3) | 8 748 | 547 |
| planet orbital (×3) | 8 748 | 547 |
| carrier | 5 557 | 220 |
| **share of J_eff** | **95.9 %** | **4.1 %** |

`J_eff = 45 638`. Set 1 dominates because it turns fastest and the reduction
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
| sun | 1 | 45 638 | 1.0× |
| carrier | 15.1667 | 10 497 000 | **230.0×** |

Neither 230 nor the square is written anywhere in the source. The square arrives
because a torque at a port maps onto the sun coordinate by dividing by `gear`,
*and* the port's angle is the sun's divided by the same `gear`.

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
| `REF_SPEED` | **12 rev/s at the sun** (75.40 rad/s) | The speed the coast figure is quoted at. Named once so the solver, the flick strength and the speed clamp mean the same thing. |

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
| `HAND_FREQ` | **60 rad/s** | The undamped natural frequency of grip-on-*sun*. Stiffness is derived from `J_eff` rather than picked against it, so a tooth-count change leaves the sun tracking the finger the same way. |
| `HAND_DAMPING` | **0.28** | Damping ratio, the same at either port. Low enough that a flick still throws; high enough that neither port oscillates about the finger. |

`HAND_STIFFNESS = HAND_FREQ² × J_eff = 1.643e8`. At the carrier the same
stiffness gives `60 / 15.1667 = 3.96 rad/s` — a **1.59 s** response period
against the sun's **0.105 s**, a 15× difference your hand notices immediately.

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
| bodies advancing 700 ms apart after a flick | **16 of 20** groups — the 4 static ones are the two set translates and the two ring assembly-phase rotations, which is correct |
| coast from a sun flick | **AT REST after 8.0 s** (a 0.75× `REF_SPEED` flick against a 9.0 s figure quoted at `REF_SPEED`) |
| console | clean but for the expected `/favicon.ico` 404 |

---

## Project rules this page is held to

From `CLAUDE.md`, and none of them optional:

- **No CSS animation or transition on anything that turns.** One
  `requestAnimationFrame` loop integrates one state — the sun's angle and rate —
  and every body's transform is derived from it each tick. Independent animation
  drifts out of mesh within seconds (#3).
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

## Not decided here

- **Whether it ships, and at what path.** Nothing has been added to
  `.github/workflows/deploy.yml`, so this folder does **not** publish. The
  deploy is a whitelist and adding a file does not publish it.
- **`COAST_RANGE_S = 9.0`** is a placeholder for Charles's call, in the same
  sense `SPINDOWN_RANGE_MS` was in CL#127 and CL#141.
