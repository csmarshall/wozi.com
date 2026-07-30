# Epicyclic Train Physics — Zs=6, Zp=9, Zr=24, ring driven at wheel speed

Convention: all angular velocities are **absolute** (fixed/ground frame).
Positive = the direction the wheel (ring) turns. Subscripts: s = sun, p = planet
(spin about its own axis), c = carrier (arm), r = ring/annulus.

Geometry checks first:

- Concentricity: Zs + 2·Zp = 6 + 18 = 24 = Zr  ✓ (standard-depth gears, common module)
- Pitch radii (module m): rs = 3m, rp = 4.5m, rr = 12m; carrier radius rc = rs + rp = 7.5m ✓ (= rr − rp)

## 1. The Willis equation

For any simple epicyclic, viewed from the carrier frame the train is an ordinary
fixed-axis train, so the ratio of *relative* speeds is the ordinary train value
(Willis, 1841; Shigley §13-13 "Planetary Gear Trains"; Norton, *Design of
Machinery*, ch. 9; Machinery's Handbook, "Planetary Gearing"):

    e = (ω_last − ω_c) / (ω_first − ω_c)

Sun → planet is an **external** mesh (sense reverses): factor −Zs/Zp.
Planet → ring is an **internal** mesh (sense preserved): factor +Zp/Zr.

    e(sun→ring) = (ω_r − ω_c)/(ω_s − ω_c) = (−Zs/Zp)(+Zp/Zr) = −Zs/Zr = −6/24 = −1/4

Planet spin relative to the carrier, from either mesh:

    ω_p − ω_c = −(Zs/Zp)(ω_s − ω_c)          [sun mesh, external]
    ω_p − ω_c = +(Zr/Zp)(ω_r − ω_c)          [ring mesh, internal]

These two must agree for any consistent state — used below as a cross-check.

## 2. Case: SUN GROUNDED (ω_s = 0), ring driven at ω_r

Willis with ω_s = 0:

    (ω_r − ω_c)/(−ω_c) = −Zs/Zr
    ω_r − ω_c = (Zs/Zr)·ω_c
    ω_r = ω_c (Zr + Zs)/Zr
    → **ω_c = ω_r · Zr/(Zr+Zs) = ω_r · 24/30 = 0.8 ω_r**   (same sign as ring)

Planet spin (fixed frame), from the sun mesh with ω_s = 0:

    ω_p − ω_c = −(Zs/Zp)(0 − ω_c) = (Zs/Zp) ω_c
    → **ω_p = ω_c (Zs + Zp)/Zp = 0.8 ω_r · 15/9 = 4/3 ω_r ≈ 1.333 ω_r**  (same sign)

Cross-check via the ring mesh: ω_p − ω_c = (Zr/Zp)(ω_r − ω_c) = (24/9)(0.2 ω_r)
= 0.5333 ω_r → ω_p = 0.8 + 0.5333 = 1.3333 ω_r. ✓ Identical.

Tabulation (superposition) check — rotate everything +x locked, then add a
carrier-fixed rotation y of the sun:

| member  | all locked | carrier fixed, sun +y | total        |
|---------|-----------:|----------------------:|--------------|
| carrier | x          | 0                     | x            |
| sun     | x          | y                     | x + y = 0    |
| planet  | x          | −(6/9) y              | x − (2/3)y   |
| ring    | x          | −(6/24) y             | x − (1/4)y   |

Sun grounded → y = −x. Ring = x + x/4 = (5/4)x = ω_r → x = 0.8 ω_r = ω_c ✓;
planet = x + (2/3)x = (5/3)x = 4/3 ω_r ✓.

**Fixed-frame speeds: sun 0, carrier +0.8 ω_r, ring +1.0 ω_r, planets +1.333 ω_r.**
Everything that moves turns the same direction. **Nothing counter-rotates in the
fixed frame.** (Even relative to the carrier the planets turn +0.533 ω_r, still
the ring's sense.) The claim as stated is confirmed in full.

## 3. Case: CARRIER GROUNDED (star arrangement, ω_c = 0), ring driven at ω_r

With ω_c = 0 the train is an ordinary fixed-axis train (this is precisely what
distinguishes a "star" from a "planetary" arrangement — Machinery's Handbook;
Dudley's Gear Handbook).

Planets (internal mesh with ring, sense preserved):

    ω_p = (Zr/Zp) ω_r = (24/9) ω_r = **+2.667 ω_r, SAME direction as the ring** ✓

Sun (external mesh with planet, sense reversed):

    ω_s = −(Zp/Zs) ω_p = −(Zp/Zs)(Zr/Zp) ω_r = −(Zr/Zs) ω_r
    ω_s = **−(24/6) ω_r = −4 ω_r — COUNTER-rotating at 4× ring speed** ✓

(Equivalently, straight from Willis with ω_c = 0: ω_s = ω_r/e = ω_r/(−1/4) = −4 ω_r.)

Both claims confirmed, including signs. Note the planet axes are stationary:
planets spin in place at their fixed 120° stations.

## 4. Case: RING GROUNDED (ω_r = 0), carrier driven at ω_c — physics only

Willis with ω_r = 0:

    (0 − ω_c)/(ω_s − ω_c) = −1/4 → ω_s = ω_c (Zs + Zr)/Zs = +5 ω_c  (sun same sense, 5×)

Planet spin relative to the carrier (ring mesh):

    ω_p − ω_c = (Zr/Zp)(0 − ω_c) = −2.667 ω_c → **planets counter-spin relative
    to the carrier** ✓ (fixed frame: ω_p = −1.667 ω_c, counter-rotating there too)

This is the classic "planetary" reduction (wind-turbine main gearboxes,
P&W GTF PW1000-series fan drive: ring fixed, carrier to the fan). Correctly
rejected for this build: the ring *is* the wheel and cannot be stationary —
a grounded ring would visibly float with no path to ground.

## 5. Assembly / mesh-phase condition

General condition for N equally spaced planets in a simple epicyclic
(KHK Gear Technical Reference, "Planetary gear mechanism — conditions of
assembly"; Shigley; Dudley):

    (Zs + Zr) / N = integer

Here (6 + 24)/3 = 10 ✓ — the train assembles with planets at exactly 120°.

Nuance worth stating precisely (the claim said "identical tooth-phase
constants"): (Zs+Zr)/N ∈ ℤ guarantees *assembly*, but in general the three
meshes may sit at staggered phases within a tooth pitch. All stations carry an
**identical** phase constant iff N divides Zs and Zr separately. Here
Zs/N = 6/3 = 2 and Zr/N = 24/3 = 8, both integers, so for this particular train
the stronger claim is also true: all three planets mesh in identical tooth
phase, and a rendering may reuse one planet's mesh alignment rotated by 120°.

Adjacency (planets must not touch each other): tip diameter m(Zp+2) = 11m must
be less than the planet-centre spacing 2·rc·sin(π/N) = 15m·sin 60° ≈ 12.99m ✓.

## 6. Verdict for the display: sun-grounded vs carrier-grounded

Ring = the wheel = input at ω_r, ground available only at the central axle
(hidden by the hub badge). The two honest options:

| member  | sun grounded | carrier grounded (star) |
|---------|-------------:|------------------------:|
| ring    | +1.0 ω_r     | +1.0 ω_r                |
| carrier | +0.8 ω_r     | 0 (ground)              |
| planets | +1.333 ω_r   | +2.667 ω_r (in place)   |
| sun     | 0 (ground)   | **−4 ω_r**              |

**Sun grounded** is the gentle option: planets orbit (carrier turns), which is
charming, but every moving member turns the same way within a 1.7× speed band.
At a glance it reads as "everything drifts together"; the epicyclic character
is easy to miss.

**Carrier grounded (star)** is the dramatic option and still completely honest:
the sun counter-rotates at 4× wheel speed and the planets spin briskly in place
at 2.667×. Mechanically it is exactly a star gearbox with annulus input and sun
output, ratio −Zr/Zs = −4:1 — nothing a career gearing engineer would blink at.
The grounding is also the most natural of the two to *depict*: the carrier
spider bolts to the stationary axle behind the hub badge, and stationary planet
pins radiating from a stationary hub read as obviously grounded structure.

Real-world precedent for each:

- **Sun fixed to a stationary axle:** internal bicycle hub gears
  (Sturmey-Archer, Shimano Nexus) — topologically the closest match to this
  display: stationary central axle, rotating outer shell.
- **Carrier fixed (star):** standard where output reversal is acceptable or
  wanted — the Lycoming/Honeywell ALF 502/LF 507 turbofan reduction gearbox is
  a star arrangement; automotive automatic transmissions obtain reverse
  precisely by braking the carrier (the sign flip in §3 is *why* reverse works).
- (Ring fixed, for contrast, is the P&W geared-turbofan / wind-turbine
  arrangement — unavailable here, per §4.)

**Recommendation: ground the carrier.** It is the only arrangement of the two
that produces any counter-rotation at all, the −4:1 sun is unmistakable motion,
and the grounded member is the one most naturally anchored to the visible axle.
One aesthetic cost, stated honestly: planets no longer orbit — their centres are
fixed and only spin. If orbiting planets are the priority over counter-rotation,
sun-grounded is the fallback, with the caveat that it demonstrably contains no
counter-rotating member.

## Sources

- R. Willis, *Principles of Mechanism* (1841) — origin of the relative-velocity
  (train-value) method for epicyclic trains.
- Budynas & Nisbett, *Shigley's Mechanical Engineering Design*, ch. 13
  ("Gears — General", §Planetary Gear Trains): e = (ω_L − ω_A)/(ω_F − ω_A),
  sign rule per mesh (external −, internal +).
- R. Norton, *Design of Machinery*, ch. 9 — tabular/superposition method used
  in §2 above.
- *Machinery's Handbook* (Industrial Press), "Planetary Gearing" section —
  ratio formulas for fixed sun / fixed carrier / fixed annulus cases.
- KHK Stock Gears, *Gear Technical Reference*, "Planetary Gear Mechanisms" —
  assembly condition (Zs+Zr)/N = integer, concentricity Zr = Zs + 2Zp,
  adjacency condition; star vs planetary vs solar nomenclature.
- Dudley's *Gear Handbook* — star vs planetary arrangement terminology and
  applications (aero reduction gearboxes).
