# tools/ — verification harnesses

Session harnesses rescued from the working scratchpad before a reboot
(2026-07-30). None of this is published: the deploy whitelists paths, and
tools/ and docs/ are not on the list.

**Path caveat:** each script hardcodes an OUT/PROFILE base under a
Claude-session scratchpad in /tmp that no longer exists after reboot. Before
running one, either `mkdir -p` that path or edit the constant near the top to
any writable directory. Everything else is self-contained (headless Chrome over
CDP; `pip` needs websockets, and Pillow/numpy for the image-analysis ones).

- verify_motion.py <url>   THE gate: 18/18 transforms advance, badges centred,
                           no console errors. Counts only deg-suffixed
                           rotations (static rotate(120) planet seats are
                           placement, not animation).
- a11y_audit.py <url>      axe-core injected over CDP + the structural checks
                           axe cannot make (focus rules, reduced-motion, SVG
                           exposure, target sizes).
- shots.py <url>           five-viewport geometry + screenshots (layout work).
- pin_test.py              pins a wheel at 8 rotations, samples the tooth ring
                           (the only band where the body paint is alone).
- zoom.py                  close-up of a mesh point between two wheels.
- mesh_audit.js /          numeric tooth-mesh measurement: penetration depth
  mesh_poly.js /             and minimum gap at all six adjacent pairs, for
  mesh_inv.js                straight and involute profiles.
- palettes.py              renders palette candidates side by side.

Testing lesson recorded in git history worth repeating here: synthesized CDP
pointer events never trigger native link drag-and-drop, so a harness can pass
an interaction that is broken under a real mouse. Anything pointer-related
needs a human hand on it once.
