#!/usr/bin/env python3
"""Resolve a CHANGELOG.md merge conflict by ENTRY, never by line range.

WHY THIS EXISTS. Every branch appends an entry at the top of `## Unreleased` /
`### Changed`, so every landing conflicts in this one file. Resolving that with
a line-range splice -- keep the HEAD side, then the incoming side -- is correct
only while the conflict markers happen to fall BETWEEN entries. As soon as two
branches touch adjacent entries the markers cut through one, and a naive splice
joins two halves and silently drops whatever fell outside. That is not
hypothetical: it deleted CL#120's entire body, which then sat on main as a bare
header through several landings before anyone noticed.

The resolution is always the same and does not need judgement: entries are
append-at-top, independent, and identified by their own number. Parse them,
take the union, order by number descending. A duplicate number is the one case
a human must look at, so it is refused rather than guessed.

    tools/changelog_merge.py CHANGELOG.md      # resolve in place
    tools/changelog_merge.py --check FILE      # no conflict; just audit it

--check is what belongs in a gate: it asserts every entry has a body, which is
the specific damage this file is prone to and the specific thing that went
unnoticed.
"""
import re
import sys

HEADER = re.compile(r"^- \*\*(?:CL)?#(\d+)\b")
CONFLICT = re.compile(r"^(<<<<<<<|=======|>>>>>>>)")


def split_entries(lines):
    """[(number, [lines])] for every entry, plus the preamble before the first."""
    starts = [i for i, l in enumerate(lines) if HEADER.match(l)]
    if not starts:
        return lines, []
    entries = []
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        entries.append((int(HEADER.match(lines[i]).group(1)), lines[i:end]))
    return lines[:starts[0]], entries


def resolve(text):
    """Rewrite only the conflicted span. Everything outside it passes through.

    The first version policed the whole file and refused on a duplicate number
    anywhere in it -- which immediately tripped on `#51`, used by two different
    entries since long before any of this. That is a real defect in the file,
    but it is not this tool's business and it must not block a merge happening
    a thousand lines away. A conflict is local; the resolution should be too.
    """
    lines = text.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.startswith("<<<<<<<"))
    end = max(i for i, l in enumerate(lines) if l.startswith(">>>>>>>"))
    span = [l for l in lines[start:end + 1] if not CONFLICT.match(l)]

    preamble, entries = split_entries(span)

    seen, merged = {}, []
    for num, body in entries:
        if num in seen:
            if "".join(seen[num]).strip() != "".join(body).strip():
                sys.exit(
                    f"FAIL: CL#{num} appears twice, with different text, INSIDE "
                    f"the conflict. Two branches claimed the same number -- a "
                    f"real collision that needs a human, not a merge rule."
                )
            continue
        seen[num] = body
        merged.append((num, body))

    merged.sort(key=lambda e: -e[0])
    # Each entry's body is a LIST of lines, so it has to be flattened before it
    # is joined -- `"".join(b for _, b in merged)` joins a generator of lists and
    # raises. That was true of the very first version too, which means this tool
    # had never once resolved a real conflict: every exercise of it hit --check
    # or the no-conflict path, and both of those return before reaching here.
    out = ("".join(lines[:start]) + "".join(preamble)
           + "".join("".join(b) for _, b in merged) + "".join(lines[end + 1:]))
    return out, [n for n, _ in merged]


def audit(text):
    """Catch the specific damage a line-range splice does: a truncated entry.

    Not "is the body long enough" -- old entries are legitimately one line, and
    a length threshold flags them forever. The precise signature is that the
    entry's bold TITLE never closes. CL#120's corpse read

        - **CL#120 — the datum showed through the bridge idlers, because a translucent

    with no closing `**`, because the line carrying it was the one dropped. An
    entry whose title is still open is an entry that was cut in half, and that
    is true whatever its length.
    """
    _, entries = split_entries(text.splitlines(keepends=True))
    truncated = []
    for num, body in entries:
        text_ = "".join(body)
        after_open = text_.split("**", 1)[1] if "**" in text_ else ""
        if "**" not in after_open:
            truncated.append(num)
    return [n for n, _ in entries], truncated


CONFLICTED_FIXTURE = """# Changelog

Entries are numbered and stable.

## Unreleased

### Changed

<<<<<<< HEAD
- **CL#131 — the entry main added.**
  main body line one
  main body line two

- **CL#130 — an entry both sides already had.**
  shared body
=======
- **CL#125 — the entry the branch added.**
  branch body line one

- **CL#130 — an entry both sides already had.**
  shared body
>>>>>>> 5c47213 (a branch)

- **CL#100 — an older entry outside the conflict.**
  tail body
"""


def selftest():
    """Exercise resolve() against a REAL conflicted document.

    This exists because the tool shipped broken. `"".join(b for _, b in merged)`
    joined a generator of LISTS and raised TypeError on any conflict at all --
    and nothing caught it, because every exercise of this file until then hit
    --check or the no-conflict path, both of which return before resolve() is
    ever called. A tool written to stop CHANGELOG.md being silently damaged
    would have failed the first time it was asked to do the job.

    So the fixture is not a smoke test. It reproduces the CL#120 shape exactly:
    the markers cut BETWEEN two entries while both sides also carry a third,
    identical entry -- which is what a line-range splice duplicates and what a
    careless dedupe drops the body of.
    """
    out, nums = resolve(CONFLICTED_FIXTURE)
    fails = []

    if "<<<<<<<" in out or "=======" in out or ">>>>>>>" in out:
        fails.append("conflict markers survived the resolution")
    if nums != [131, 130, 125]:
        fails.append(f"span entries should be [131, 130, 125] newest-first, got {nums}")

    found, truncated = audit(out)
    if found != [131, 130, 125, 100]:
        fails.append(f"whole-file order should be [131, 130, 125, 100], got {found}")
    if truncated:
        fails.append(f"resolution truncated {truncated} -- this is the CL#120 damage itself")

    # The bodies, not just the headers. A splice that keeps every header and
    # drops a body passes an entry count and is exactly the bug.
    for needle in ("main body line one", "main body line two",
                   "branch body line one", "shared body", "tail body"):
        if needle not in out:
            fails.append(f"lost a body line: {needle!r}")
    if out.count("shared body") != 1:
        fails.append(f"CL#130 was carried by both sides and should appear once, "
                     f"got {out.count('shared body')}")
    if "an older entry outside the conflict" not in out:
        fails.append("content outside the conflict span was not passed through")

    # A genuine collision must still refuse rather than guess.
    collision = CONFLICTED_FIXTURE.replace("branch body line one", "different text entirely") \
                                  .replace("- **CL#125 —", "- **CL#131 —")
    try:
        resolve(collision)
        fails.append("two branches claiming CL#131 with different text was not refused")
    except SystemExit:
        pass

    if fails:
        sys.exit("SELFTEST FAILED:\n  - " + "\n  - ".join(fails))
    print(f"selftest ok: {len(found)} entries, markers gone, bodies intact, "
          f"duplicate number refused")


def main():
    args = [a for a in sys.argv[1:] if a not in ("--check", "--selftest")]
    if "--selftest" in sys.argv:
        selftest()
        return
    check_only = "--check" in sys.argv
    path = args[0] if args else "CHANGELOG.md"
    text = open(path).read()

    if check_only:
        nums, bare = audit(text)
        if bare:
            sys.exit(f"FAIL: {len(bare)} entry/entries is truncated -- its bold title never closes: "
                     + ", ".join(f"CL#{n}" for n in bare))
        print(f"ok: {len(nums)} entries, every title closes")
        return

    if "<<<<<<<" not in text:
        nums, bare = audit(text)
        print(f"no conflict; {len(nums)} entries"
              + (f", BARE: {bare}" if bare else ", all have bodies"))
        return

    out, nums = resolve(text)
    _, bare = audit(out)
    if bare:
        sys.exit(f"FAIL: resolution left {bare} without a body -- refusing to write")
    open(path, "w").write(out)
    print(f"resolved: {len(nums)} entries, newest first ({nums[0]} .. {nums[-1]})")


if __name__ == "__main__":
    main()
