# Backlog sprint

The named process for working the open backlog down in one pass, so it does not
have to be re-explained. Charles asks for "a backlog sprint" (or `/backlog-sprint`)
and this is what he means.

It exists because the default failure mode is worse than slow: a long serial
grind through tickets, each one interrupted to ask a question, so Charles is
pulled back in a dozen times and the expensive resource — **his attention** — is
spent on scheduling rather than on decisions.

## The shape

**Phase 1 — read everything, then ask once.**

Read every open ticket in full, including comments. Read `CLAUDE.md`, and
`session-state.md` if it exists. The point is to know what is actually blocked
versus what only looks blocked, *before* asking anything.

Then form **one batched set of questions** through the structured question UI
(`AskUserQuestion`), not scattered through prose. Rules that matter:

- Only ask what genuinely **changes what happens next**. Anything a sensible
  default covers, take the default and say so.
- Lead each with a recommendation marked `(Recommended)`.
- Four questions per call is the hard limit; more than that means splitting
  across calls, so prioritise ruthlessly rather than padding.
- A question Charles cannot act on is worse than no question.

**Phase 2 — classify every ticket before dispatching any of it.**

| class | meaning | action |
| --- | --- | --- |
| **Ready** | scope is clear enough to execute | dispatch |
| **Evaluate** | needs measurement, research or a design pass before anyone can decide | dispatch the *evaluation*, not an implementation |
| **Blocked** | needs a Charles decision that Phase 1 did not settle | **stack it, do not dispatch** |

The distinction between Ready and Evaluate is the one that earns its keep: a
ticket whose right answer is unknown should produce **numbers or a design**, and
a decision request — never a guessed implementation.

**Phase 3 — dispatch in parallel, along the file boundaries that actually exist.**

Parallelism is bounded by *file contention*, not by ticket count. In this repo:

- `index.html` is the bottleneck — roughly a dozen tickets touch it (that IS
  GitHub #113's remaining cost). **`docs/INDEX-REGIONS.md` is the map**: it scores
  46 regions for textual *and* semantic independence and gives a mechanical
  dispatch rule. Its honest ceiling is **two implementation agents, sometimes
  three** — the five exclusive scopes overlap, and they cover exactly the regions
  real tickets are about. A brief should name the region and its anchor symbol,
  never a line range, because the line numbers drift.
- **Read-only work needs no lane at all, and this is the most under-used win.**
  Measurement, audits, research, `docs/`, `?hud` readings — none of it takes the
  lock or needs isolation, so it can *always* run alongside the implementation
  lane. Since much of a backlog is *Evaluate* rather than *Ready*, dispatch those
  freely and concurrently rather than queueing them behind a file they never
  touch.
- `fidget/index.html`, `tools/*`, `.github/workflows/*`, `config.js` and docs are
  independent of it and of each other, so those genuinely run concurrently.
- Anything that mutates files in parallel gets `isolation: "worktree"`. Two
  agents editing one file with no isolation is a collision waiting to happen —
  it has already been survived once by luck, which is not a plan.
- Read-only evaluation (measurement, research, audits) never needs isolation and
  can always run alongside.

**The injected `CLAUDE.md` is a snapshot taken at session start, and it goes stale
inside a long session.** A senior review this way asserted the repo was still
private, quoting the rulebook, hours after the paragraph had been rewritten to say
PUBLIC — because it trusted the copy in its context rather than reading the file.
The orchestrator carries the same stale snapshot and is no less exposed. So: **a
claim about the repo's CURRENT state — visibility, what a gate runs, what a
constant is set to — needs a read of the working tree, exactly like any other
prose-versus-reality check.** Quoting the injected rulebook as evidence about now
is quoting an instrument that stopped.

Related trap: `.claude/worktrees/*/` are other agents' checkouts pinned to
arbitrary older commits, each with its own stale `CLAUDE.md` and `CHANGELOG.md`.
Read docs from the repo root only.

Every subagent brief must carry, without exception:

- **Read `CLAUDE.md` first**; it overrides their defaults. Tell them to read it
  **from disk at the repo root**, not from whatever snapshot arrived in context.
- **The invariants their work could break**, named specifically — the one-clock
  rule, no CSS animation on anything that turns, no hardcoded geometry, inline
  styling only, the deploy whitelist, `tools/test.js` reading constants out of
  `index.html`.
- **Which files they may touch, and which they must not.**
- **Forbid `open`.** They report absolute paths; the orchestrator decides what
  reaches Charles's screen and always attaches a question to it. Ten agents each
  opening a sheet is ten unexplained windows.
- **Forbid committing, pushing, and touching GitHub issues.** The orchestrator
  merges, commits and comments, so the history stays coherent and one voice
  writes the tickets.
- **Require a `DECISIONS NEEDED` section** — questions only Charles can answer,
  each with options and a recommendation — or an explicit statement that there
  are none.
- **Require real verification with numbers**, and require it be *run*, not
  asserted. `npm test`, the relevant gates, and for anything visual a forced
  `?kind=` / `?who=` shot, because the default deal draws seven wheels from
  eleven families and a change to one family has about an even chance of not
  appearing at all.

**Phase 4 — land the work, one voice.**

As each agent reports: review the diff, verify independently rather than
trusting the report, merge, run `npm test` plus the gates the change actually
touches, write the `CHANGELOG.md` entry, commit, comment on and close the ticket,
and clean up the worktree. Charles pushes, or approves the push.

**Phase 5 — then, and only then, the stacked blockers.**

Everything deferred in Phase 1 and everything surfaced as `DECISIONS NEEDED` in
Phase 4 is now batched, deduped, and put to Charles in one more structured round.
Drop anything the intervening work already answered — that happens often, and
asking anyway wastes the round.

Repeat from Phase 2 with the answers. Stop when the backlog is empty or
everything left is genuinely blocked on something outside the repo.

## Rules that hold across every phase

- **Nothing appears on Charles's screen without a question attached.** A picture
  with no question is noise; he cannot tell whether to decide, check, or admire.
  Every `open` states what he is looking at, what differs between panels, and
  what it decides — or says explicitly "no action needed, evidence for X".
- **Show, don't describe.** Tuned numbers, layout, colour and spacing get built
  and photographed, ideally as a sweep of several values rather than one sample.
  Expect them to be revised once he can see them, so a tuned value is one named
  constant and its location is stated.
- **Prefixed tickets go straight to the tracker.** A `feature:` / `bug:` /
  `chore:` / `perf:` line mid-sprint gets filed as a GitHub issue immediately,
  with the constraints and invariants already discovered written into it, and the
  number confirmed back in one line. Never folded silently into current work.
- **A `0px` pixel-gate result can mean "not tested", not "unchanged."** Force the
  family or the person before believing it.
- **Report faithfully.** If a gate failed, say so with the output. If a claim is
  projected rather than verified, mark it projected. A single passing run is not
  "proven".
- **Update `session-state.md` continuously**, not at the end, so a crash loses
  nothing.

## Worth knowing before the first dispatch

Real findings from the sprint on 2026-08-11, kept because each cost time:

- **Closing a ticket is not implied by shipping the code.** Every ticket needs an
  explicit comment and close; #95 shipped and sat open for hours.
- **Agents die on API errors mid-run.** The worktree survives. Resume with
  `SendMessage` rather than starting over — a resumed agent kept 456 insertions
  of intact work.
- **A subagent's baseline can go stale** while it works, so its diff may not
  apply. Reconcile hunk by hunk; do not force it.
- **`a11y_audit.py` and `devices.py` catch real defects**, not just theoretical
  ones — a 15px hit box and a 12px safe-area overflow in one sprint. Run them on
  anything touching controls or layout.
- **They are slow enough to hit the foreground timeout.** Background them.
- **CDP harnesses flake occasionally** (`ConnectionClosedError`). Retry once
  before investigating.
