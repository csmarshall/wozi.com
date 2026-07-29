# wozi.com

The landing page for wozi.com: a single-file, self-contained animated gear train.
Each wheel carries one social link at its hub; the whole train is driven by a
physics loop (flywheel inertia, drag-to-spin, meshed ratios) rather than CSS
animation, so every wheel, the roller chain and the toothed belt stay in exact
mechanical sync.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | The page. Opens directly in a browser — no build step, no bundler. |
| `support.js` | Runtime the page loads (template + logic host). Do not hand-edit. |
| `CHANGELOG.md` | Change log, one entry per tracked fix. |
| `CLAUDE.md` | Invariants and workflow for anyone (or anything) editing this. |
| `SESSION-LOG.md` | Why the design is the way it is; what was tried and rejected. |
| `PROMPT.md` | Paste-in brief for a first Claude Code session. |
| `assets/icons/*.svg` | One single-colour hub mark per link, fetched at runtime. |

Deploy by serving the folder statically. There is nothing to compile — but it does
have to be *served*: the hub icons are fetched at runtime, so opening the file
directly from `file://` leaves the badges empty.

## How it works

- **Solver.** Wheel sizes, tooth counts and centre distances are derived at
  runtime from one module constant (`MODULE`), so every wheel meshes by
  construction. Drive runs (chain, belt) are placed by a search that rejects any
  route that crosses another run, passes over a third wheel, or doubles back
  through the middle of the group.
- **One frame loop.** No CSS animations. A single `requestAnimationFrame` step
  integrates a master angle; every wheel transform and every strand's
  `stroke-dashoffset` is derived from it. One tooth of travel per tooth of the
  driving sprocket, in whichever direction the train is turning.
- **Layers.** Optional detail passes (spin-up, engraved rims, parallax,
  character marks, hover drag) are independent flags and compose freely.
- **Lighting.** All shading is symmetric about the vertical axis — lit from
  directly above, never from a corner, so concentric webs and hubs read centred.

## Content

Link targets live in the `SITES` map in `index.html`. That map is the source of
truth for the page's content; the wordmark reads the host it is served from.
