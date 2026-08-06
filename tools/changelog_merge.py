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
    conflicted = [l for l in text.splitlines(keepends=True) if not CONFLICT.match(l)]
    preamble, entries = split_entries(conflicted)

    seen, merged = {}, []
    for num, body in entries:
        if num in seen:
            prev = "".join(seen[num]).strip()
            cur = "".join(body).strip()
            if prev != cur:
                sys.exit(
                    f"FAIL: CL#{num} appears twice with different text. Two "
                    f"branches claimed the same number -- that is a real "
                    f"collision and needs a human, not a merge rule."
                )
            continue
        seen[num] = body
        merged.append((num, body))

    merged.sort(key=lambda e: -e[0])
    return "".join(preamble) + "".join(b for _, b in merged), [n for n, _ in merged]


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


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
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
