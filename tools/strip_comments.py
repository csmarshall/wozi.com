#!/usr/bin/env python3
"""Produce a comment-stripped copy of index.html FOR DEPLOYMENT ONLY.

WHY THIS EXISTS (GitHub #113). `index.html` is ~550KB of source, and roughly two
thirds of it is comment: the argument for every derived constant, the two rules
that were tried and rejected before the shipped one, the issue number that
caused it. That prose IS the project's documentation and it stays in the repo,
unabridged, forever. What it does not have to do is travel down the wire to
somebody who wanted to look at some gears. So the repo keeps the source and the
bucket gets the machine.

WHAT IT TOUCHES, AND WHERE THE GATE WENT. It does not touch the repo's own
`index.html` — a plain run writes to `scratchpad/`. It IS now wired into
`.github/workflows/deploy.yml`, which was previously refused here on the grounds
that publishing something other than the file in the repo changes what "the repo
is the source of truth for s3://wozi.com" means, and that is a decision with a
gate on it. The decision was taken; this is the gate.

The shape of it matters more than the fact of it. Every gate in `tools/` used to
run against the source, so the moment a transform sits between the repo and the
bucket, the reviewed file and the served file are two different files and only
one of them is measured. The deploy therefore runs this tool over its OWN
CHECKOUT (`--in-place`), before any gate and before any credential, so that
every gate below — the geometry suite, the device profiles, the motion and DOM
and escape-mesh checks — measures the artifact rather than the source, unchanged
and without knowing anything about stripping. `tools/pixel_regress.py --ref HEAD`
is then the bridge between the two: the working tree is the artifact, HEAD is the
source, and 0 pixels differ is the whole claim this transform is allowed to make.

`--in-place` REFUSES on a file that differs from HEAD, because the one
unrecoverable version of this mistake is running it over a working tree carrying
uncommitted documentation. In CI the checkout is clean by construction.

BACKLINKS, AND WHY THEY ARE FOUR CHARACTERS AND A NUMBER (Charles, 2026-08-11:
"do we want to have the script inject references back to github to individual
methods in the code so that someone could easily go from one to the other?").
The stripped file must stay navigable back to the documented source, and the
naive form of that is a full URL at every site: ~80 bytes × 709 comments is
~57KB, which against a 189KB delivered file is a third of it spent saying the
same thing 709 times. So the URL is carried ONCE, in the banner, and each site
keeps only the line number it came from:

    /*L1234*/         in JS and CSS
    <!--L1234-->      in markup

and the banner explains the convention in one line. `#L1234` on the banner's URL
is then the comment that used to be there. Measured on index.html the 709 markers
cost 7,146 B raw and 2,502 B brotli — 3.8% of a file that is 68.7% smaller than
the source, or 1.7% of the 414KB the strip saves. So per-COMMENT resolution is
affordable and the coarser fallback (one marker per method) buys nothing worth
having; the report prints the figure on every run so the trade can be re-checked
rather than remembered.

THE LINK IS PINNED TO A COMMIT, not to a branch. `blob/main/index.html#L1234`
names a line that moves the next time anything above it is edited, so the number
in the marker would quietly start pointing at the wrong prose — a drifting
constant published 709 times over. The SHA comes from `--sha` (the deploy passes
`github.sha`) or from `git rev-parse HEAD`, and if the input differs from that
commit the banner SAYS SO rather than implying a precision it does not have.

The base URL still comes from `git remote get-url origin` rather than being
written down here. This tool shipped carrying a caveat that the repo was private,
so the link asked a reader for a GitHub sign-in rather than giving them the
comments it promised; the history rewrite landed and the repo is public, so the
caveat is gone and the banner simply points at the source. `--repo-url` stays, so
pointing the banner somewhere else — a mirror, a rename — is one flag in the
deploy rather than an edit here.

THE TRAP THIS AVOIDS. This is ONE file carrying three comment syntaxes plus the
x-dc template markup, and every naive approach eats live code:

  - `'https://wozi.com'` is not a line comment, and neither is any of the
    `https://fonts.googleapis.com` in <helmet>.
  - `` `a /* b` `` inside a template literal is not a block comment, and template
    literals nest through `${ ... }` back into real expression context.
  - `/[?&]seed=([^&]*)/` is a regex literal whose body contains `/*`. Treat it as
    division and the stripper eats forward to the next `*/` — hundreds of lines
    of code, silently.
  - `<style>` appears five times in this file and only once as a tag; the other
    four are the word "<style>" inside JS comments discussing it. Anything that
    finds regions with `str.find('<style')` gets the wrong one.

So the scanner is a real state machine, not a regex sweep, and where it cannot
decide confidently it KEEPS the text.

WHAT VERIFICATION IS WORTH, AND WHAT IT WAS WORTH BEFORE (GitHub #161). Every
removal is verified from the outside, but "outside" used to mean "the same
tokenizer, run again". `comment_spans()` made the cut, and the idempotence check,
the marker tally and the leftover exemption all asked `comment_spans()` whether
anything was left — so a MISPARSE PASSED ITS OWN VERIFICATION. That is not a
theoretical hole; it was measured. `a++ / 2; // note` read the `/` as the start of
a regex, because the scanner's idea of the preceding token was one character (`+`)
and `+` is a position where an expression may begin. The scan then ran forward to
the `/` of the `//`, the comment was never located, it SURVIVED into the published
file, and `verify()` returned clean.

And the fault was not confined to keeping text, which is what made it worth
fixing rather than noting. A `/` mistaken for a regex opener leaves the cursor
wherever that phantom literal happened to end, which can be the middle of a
string — and the scanner then reads the REST OF THAT STRING as code. Measured:
`let s = 'x /y/ /* z */ w';` after a `i++ /` misparse had `/* z */` cut out of the
string's own contents, and the result still parsed, so `node --check` was content
and only a pixel could have told. Postfix `++`/`--` are now values, so that
particular door is shut, but the general shape stands: a misparse can eat.

So there are now three checks that do NOT ask the tokenizer anything, and they
are the ones the guarantee rests on:

  - THE DELIVERED STYLESHEET MUST CONTAIN NO COMMENT. CSS is the half with no
    parser behind it — `node --check` reads JavaScript, and `brace_balance` is a
    whole-document NET count, so a declaration eaten out of `:focus-visible` or
    `@media (prefers-reduced-motion)` used to pass everything (those are states no
    screenshot photographs). After a correct strip a `<style>` body holds no `/*`
    at all outside a quoted string, which is absolute rather than differential and
    needs no opinion about what a comment is. Measured on both published files:
    zero.
  - THE DELIVERED STYLESHEET'S STRUCTURE MUST BE UNCHANGED. Its ordered census of
    at-rules, selectors and declaration PROPERTY NAMES must match the source's,
    per `<style>` block — which is what notices an eaten declaration inside a rule
    that only applies in a state nothing renders.
  - A SURVIVING JS COMMENT IS DETECTED BY NODE, NOT BY US. Every `//` or `/*` left
    in a script body that is not one of this tool's markers is perturbed in a way
    that is inert inside a comment and fatal anywhere else — deleted to end of
    line, or given a `${'` that only a comment can swallow — and `node --check`
    passes judgement. A candidate whose perturbation still parses BEHAVES like a
    comment, whatever this file's tokenizer believes. Ten hand-built cases pin it,
    including `//` inside a multi-line template literal, which is the one a naive
    delete-to-end-of-line probe gets wrong.

Alongside those, and still worth having: the output's script bodies must pass
`node --check`; the load-bearing markers other gates match on must still be
present, PER FILE (they used to be `index.html`'s strings applied to both pages,
which made them vacuous for `fidget/index.html` — a file with no declared anchors
is now a verification failure, not a silent pass); the CSS braces must balance;
the artifact must differ from the source ONLY at the located comment sites, with
whitespace discounted; and a second pass must find nothing left to strip but this
tool's own banner and its backlink markers.

That last one is still the same tokenizer asking itself, which is why it is listed
last and no longer stands alone. The markers are themselves comments, so it is
widened by exactly their own shape and no further: a leftover is forgiven only if
it matches `/*L<digits>*/` or the markup form of the same, every marker's line
number must land inside the source's own line count, and the number of markers
must equal the number of source LINES that carried a comment.

WHAT IS STILL ONLY COVERED BY A PICTURE. A span that is well-formed but in the
WRONG PLACE — a `/*` inside a string, taken for a comment — removes text that
looks exactly like a comment, so no lexical check here can object. The JS half of
that is caught by `node --check` when it breaks the parse and by
`tools/pixel_regress.py --ref HEAD` when it does not; `tools/mutation_gate.py
--only stripper-ate-a-line` is the standing proof that the pixel gate does catch
it. Do not read the checks above as making the pixel gate optional.

    tools/strip_comments.py                 # strip, verify, write to scratchpad/
    tools/strip_comments.py --check         # strip and verify, write NOTHING (CI)
    tools/strip_comments.py --selftest      # fixtures for every trap above
    tools/strip_comments.py --out PATH IN   # explicit paths
    tools/strip_comments.py --no-markers    # no backlinks, to price them
    tools/strip_comments.py --in-place F    # OVERWRITE F -- the deploy's own use

Exit codes: 0 ok, 1 verification failed, 2 usage or I/O, 3 selftest failed.
"""
from __future__ import annotations

import functools
import gzip
import os
import re
import subprocess
import sys
import tempfile
from typing import Iterator, List, Optional, Tuple

EXIT_OK = 0
EXIT_VERIFY = 1
EXIT_USAGE = 2
EXIT_SELFTEST = 3

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_IN = os.path.join(REPO_ROOT, "index.html")
# scratchpad/ is gitignored, so a build artifact cannot be committed by accident
# and cannot reach the bucket -- the deploy is a whitelist of named paths.
DEFAULT_OUT = os.path.join(REPO_ROOT, "scratchpad", "index.stripped.html")

# Markers other gates match on by literal text, KEYED BY THE FILE THEY BELONG TO
# (GitHub #161). Stripping is only allowed to remove commentary, so every one of
# these must survive verbatim. They were one flat tuple of `index.html` strings
# checked against whatever file was being stripped, and `if marker in src and
# marker not in out` is vacuously true when the marker is in neither — so the
# second published page, `fidget/index.html`, had no anchor protection at all
# while appearing to have five.
#
# index.html: `data-props` carries the shipped layer defaults AND the editor
# schema; the aria-label is what tools/devices.py finds the speed slider by; the
# three identifiers are named in CLAUDE.md's invariants.
# fidget/index.html: `setInterval(draw, 250)` is matched by name in both
# tools/fontpin.py and tools/pixel_regress.py, `planetary` is what the deploy's
# post-publish smoke check greps the live page for, and the rest are the ids and
# constants the page cannot draw without.
REQUIRED_MARKERS = {
    "index.html": (
        'data-props=',
        'aria-label="Gear speed"',
        'MIN_CUT_PX',
        'SPINDOWN_RANGE_MS',
        'GHOST_COLORS',
    ),
    "fidget/index.html": (
        'setInterval(draw, 250)',
        'planetary',
        'id="train"',
        'aria-label="Switch theme"',
        'GROUNDINGS',
        'REF_SPEED',
    ),
}

BANNER_MARK = "wozi.com -- comments stripped for delivery"

# A backlink marker: the SOURCE line the removed comment stood on, and nothing
# else. The URL it hangs off is in the banner, once. Two syntaxes because the
# marker has to be a comment in whatever language the site was in -- `/*L1*/` in
# the body of an HTML document is not a comment, it is text on the page.
BACKLINK = r"(?:<!--L\d+-->|/\*L\d+\*/)"
BACKLINK_ONE = re.compile(BACKLINK)
BACKLINK_NUM = re.compile(r"L(\d+)")
# A line whose entire content is markers has no code on it, so its indentation is
# paying for nothing and gets dropped with the prose it used to align to.
BACKLINK_ONLY_LINE = re.compile(BACKLINK + r"(?:\s*" + BACKLINK + r")*\Z")

RAW_TEXT_TAG = re.compile(r"<(script|style)\b", re.I)

# A `/` opens a regex literal only in expression position. These are the tokens
# after which an expression may begin; anything else (identifier, number, `)`,
# `]`, `}`, `++`, `--`, string) is a value, so the `/` is division.
#
# `}` USED TO BE IN HERE and the docstring below already claimed it was not
# (GitHub #161). It is genuinely ambiguous -- it ends a block, after which a regex
# may begin, and it ends an object literal, after which it may not -- so it is
# answered "division" with the rest of the values, which is the direction that
# cannot delete anything. Neither published file has a `/` after a `}` at all, so
# the change moves no byte of either artifact; it removes a guess that could have.
REGEX_OK_PUNCT = set("(,=:[!&|?{;+-*%~^<>")
REGEX_OK_WORDS = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "do", "else", "case", "yield", "await", "throw",
}


class Span:
    """One comment found in the source: [start, end) and which language."""

    __slots__ = ("start", "end", "kind")

    def __init__(self, start: int, end: int, kind: str) -> None:
        self.start, self.end, self.kind = start, end, kind

    def __repr__(self) -> str:  # pragma: no cover - debugging only
        return f"Span({self.start}, {self.end}, {self.kind!r})"


def _skip_tag(text: str, i: int) -> int:
    """Step over a `<...>` tag, honouring quoted attribute values.

    `data-props` is a single attribute holding ~1.5KB of entity-escaped JSON, and
    the whole point of coming through here rather than `text.find('>')` is that
    an attribute value may contain `>`, `<!--`, or the word `<style>` without any
    of those meaning what they would mean outside the quotes.
    """
    i += 1
    while i < len(text):
        c = text[i]
        if c in "\"'":
            close = text.find(c, i + 1)
            i = len(text) if close < 0 else close + 1
        elif c == ">":
            return i + 1
        else:
            i += 1
    return len(text)


def _css_spans(text: str, lo: int, hi: int) -> Iterator[Span]:
    """CSS has only `/* */`, but it also has strings and `url()` -- and the
    palette comments in this file are full of `#F1F2F0` and prose apostrophes."""
    i = lo
    while i < hi:
        c = text[i]
        if c in "\"'":
            i += 1
            while i < hi and text[i] != c:
                i += 2 if text[i] == "\\" else 1
            i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = hi if end < 0 or end + 2 > hi else end + 2
            yield Span(i, end, "css")
            i = end
        else:
            i += 1


def _js_spans(text: str, lo: int, hi: int) -> Iterator[Span]:
    """Tokenise JS well enough to know a comment from everything that looks like
    one: strings, template literals (which nest back into expression context
    through `${}`), and regex literals.

    `prev` is the last significant token -- the only thing that distinguishes
    `a / b / c` from `/[?&]seed=([^&]*)/`. When a `/` is ambiguous the fallback
    is DIVISION, which removes nothing; guessing "regex" wrongly would consume
    forward to the next `/` and delete live code.
    """
    i = lo
    prev = ""              # last significant token, for the regex decision
    stack: List[str] = []  # template-literal nesting: '`' or '{'

    while i < hi:
        c = text[i]

        if c in " \t\r\n":
            i += 1
            continue

        if text.startswith("//", i):
            end = text.find("\n", i)
            end = hi if end < 0 or end > hi else end
            yield Span(i, end, "js-line")
            i = end
            continue

        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = hi if end < 0 or end + 2 > hi else end + 2
            yield Span(i, end, "js-block")
            i = end
            continue

        if c in "\"'":
            j = i + 1
            while j < hi and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            prev = "str"
            continue

        if c == "`":
            stack.append("`")
            i += 1
            prev = "str"
            # Scan the literal here rather than via a mode flag: `${` re-enters
            # expression context, where a nested template or a comment is legal.
            while i < hi and stack and stack[-1] == "`":
                ch = text[i]
                if ch == "\\":
                    i += 2
                elif ch == "`":
                    stack.pop()
                    i += 1
                elif text.startswith("${", i):
                    depth, j = 1, i + 2
                    # Recurse over the substitution so a `//` or `/*` inside it
                    # is still found, and a nested template still shields its own
                    # text. Brace counting alone would miscount `{` in a string.
                    sub_end = _match_brace(text, j, hi)
                    for sp in _js_spans(text, j, sub_end):
                        yield sp
                    i = sub_end + 1
                    del depth
                else:
                    i += 1
            continue

        if c == "/":
            if _regex_position(prev):
                j = _scan_regex(text, i, hi)
                if j > 0:
                    i = j
                    prev = "str"
                    continue
            i += 1
            prev = "/"
            continue

        if c.isalnum() or c in "_$":
            j = i
            while j < hi and (text[j].isalnum() or text[j] in "_$."):
                j += 1
            prev = text[i:j]
            i = j
            continue

        # `++` and `--` have to be ONE token, not two of whatever their last
        # character is (GitHub #161). A postfix increment leaves a VALUE, so the
        # `/` after it is division -- but with `prev` holding a bare `+`, which is
        # a position where an expression may begin, `a++ / 2; // note` had its `/`
        # read as a regex opener and the comment after it was never found. This is
        # not one of the ambiguous cases: `++` can only ever be followed by an
        # operator, so answering "division" is correct rather than merely safe.
        if c in "+-" and i + 1 < hi and text[i + 1] == c:
            prev = c + c
            i += 2
            continue

        prev = c
        i += 1


def _match_brace(text: str, i: int, hi: int) -> int:
    """Index of the `}` closing a `${` substitution that starts at `i`.

    Counts braces while skipping strings, templates and comments, because a `}`
    inside any of those closes nothing.
    """
    depth = 1
    while i < hi:
        c = text[i]
        if c in "\"'`":
            q = c
            i += 1
            while i < hi:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == q:
                    break
                if q == "`" and text.startswith("${", i):
                    i = _match_brace(text, i + 2, hi) + 1
                    continue
                i += 1
            i += 1
        elif text.startswith("//", i):
            nl = text.find("\n", i)
            i = hi if nl < 0 else nl
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = hi if end < 0 else end + 2
        elif c == "{":
            depth += 1
            i += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
            i += 1
        else:
            i += 1
    return hi


def _regex_position(prev: str) -> bool:
    """True when a `/` here can only be the start of a regex literal.

    `)` and `}` are the genuinely ambiguous ones (`if (a) /re/.test(b)` against
    `f(x) / 2`) and both are answered "division", because that is the direction
    that cannot delete: a `/` treated as division advances the cursor one
    character, so the worst it can do is leave a comment standing.

    "Removes nothing" is what this used to claim and it was too strong (GitHub
    #161). Division only removes nothing HERE; the cursor carries on, and whatever
    the wrong answer resynchronises onto is read as code. `if (a) /x/*y/.test(s)`
    is the demonstration -- with `)` answered division, the `/*` two characters
    later is a block comment and the strip eats forward to the next `*/`, which in
    a real file is hundreds of lines. `node --check` caught that one. The honest
    statement is that division is the SAFER guess, not a safe one, and that the
    checks in `verify()` which do not consult this function are what the guarantee
    actually rests on.

    Both published files were measured under both answers for the ambiguous
    tokens: `index.html` strips to the identical byte either way, and
    `fidget/index.html` has two sites (`(now - last) / 1000` and `(S.rate + v) / 2`,
    each followed by a block comment) where answering "regex" would swallow the
    comment opener and keep the comment. So the shipped answer is also the correct
    one there, and it is load-bearing rather than incidental.
    """
    if prev == "":
        return True
    if prev in REGEX_OK_WORDS:
        return True
    return len(prev) == 1 and prev in REGEX_OK_PUNCT


def _scan_regex(text: str, i: int, hi: int) -> int:
    """End index of the regex literal opening at `i`, or -1 if it is not one.

    Refusing (-1) is the conservative answer -- the caller falls back to
    division and strips nothing. A literal cannot span a newline and cannot be
    empty (`//` is a comment), so either of those means we guessed wrong.
    """
    j = i + 1
    in_class = False
    while j < hi:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "\n":
            return -1
        if in_class:
            if c == "]":
                in_class = False
        elif c == "[":
            in_class = True
        elif c == "/":
            if j == i + 1:
                return -1
            j += 1
            while j < hi and text[j].isalpha():  # flags
                j += 1
            return j
        j += 1
    return -1


def comment_spans(text: str) -> List[Span]:
    """Every comment in the document, in source order.

    Walks the HTML as a document rather than as a string: raw-text elements are
    entered by their real open tag and left at their real close tag, so the four
    mentions of the word "<style>" inside JS commentary are never mistaken for
    the one that is markup.
    """
    spans: List[Span] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c != "<":
            i += 1
            continue
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            end = n if end < 0 else end + 3
            spans.append(Span(i, end, "html"))
            i = end
            continue
        m = RAW_TEXT_TAG.match(text, i)
        if m:
            tag = m.group(1).lower()
            body = _skip_tag(text, i)
            close = re.compile(r"</" + tag + r"\s*>", re.I).search(text, body)
            end = n if close is None else close.start()
            scan = _js_spans if tag == "script" else _css_spans
            spans.extend(scan(text, body, end))
            i = end if close is None else close.end()
            continue
        i = _skip_tag(text, i)
    return spans


def marker_for(kind: str, line: int) -> str:
    """The backlink marker for a comment of `kind` that stood on source `line`.

    The syntax has to match the site, not the file: markup takes `<!--L1-->` and
    everything inside a <script> or <style> takes `/*L1*/`. Get that the wrong way
    round and the marker either prints on the page or ends the script early.
    """
    return f"<!--L{line}-->" if kind == "html" else f"/*L{line}*/"


def apply_spans(text: str, spans: List[Span], markers: bool = True) -> str:
    """Cut the spans out, leave a backlink where each one was, then tidy only the
    lines the cut emptied.

    With `markers` off a block comment becomes a single space when it was welding
    two tokens together (`a/**/b` is `a b`, not `ab`) and everything else becomes
    nothing. With markers on the marker IS that separator -- a block comment is
    whitespace to the tokeniser whatever is written inside it -- so no space is
    added, which also makes the output one byte closer to the source than the
    space-inserting path was.

    One marker per source LINE, not per comment: two comments on one line have one
    line number between them, and printing it twice would say nothing twice.

    A line that is whitespace-only ONLY BECAUSE a comment left it that way is
    dropped, which is where most of the saving comes from -- but a line that was
    already blank in the source is kept, so the output's remaining structure is
    the author's and not this tool's.
    """
    out: List[str] = []
    line_of = _line_index(text)
    pos = 0
    marked_line = -1
    for sp in spans:
        out.append(text[pos:sp.start])
        line = line_of(sp.start) + 1          # 1-based, to match #L1234 on GitHub
        if markers and line != marked_line:
            out.append(marker_for(sp.kind, line))
            marked_line = line
        else:
            before = text[sp.start - 1] if sp.start else "\n"
            after = text[sp.end] if sp.end < len(text) else "\n"
            if sp.kind != "js-line" and not before.isspace() and not after.isspace():
                out.append(" ")
        pos = sp.end
    out.append(text[pos:])
    cut = "".join(out)

    # Re-derive which output lines were touched: the spans' line numbers are in
    # SOURCE coordinates, so walk the result and drop a whitespace-only line only
    # when the source line it came from carried a removal.
    kept: List[str] = []
    src_lines = text.split("\n")
    out_lines = cut.split("\n")
    # A removal can merge source lines, so map by consuming source lines that
    # were fully removed. Simpler and sufficient: a whitespace-only output line
    # is dropped iff the identically-indexed source line was not whitespace-only.
    for idx, line in enumerate(out_lines):
        body = line.strip()
        if body:
            # A marker-only line is the remains of a standalone comment: there is
            # no code left for its indentation to line up with, so the indent goes
            # too. Nothing in the source can look like this -- `/*L1*/` as code is
            # a comment by definition -- so the test cannot match real content.
            kept.append(body if BACKLINK_ONLY_LINE.fullmatch(body) else line)
            continue
        was_blank = idx < len(src_lines) and not src_lines[idx].strip()
        if was_blank:
            kept.append(line)
    return "\n".join(kept)


def _line_index(text: str):
    """Closure returning the 0-based line number of a character offset."""
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())

    def at(off: int) -> int:
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo

    return at


def strip(text: str, markers: bool = True) -> str:
    return apply_spans(text, comment_spans(text), markers)


def _git(root: str, *args: str) -> Optional[str]:
    """`git -C root ...`, or None if git could not answer at all. Every caller
    treats None as "say less in the banner", never as a value."""
    try:
        r = subprocess.run(["git", "-C", root, *args],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _git_rc(root: str, *args: str) -> Optional[int]:
    """The exit status of a git command, for the ones whose ANSWER is the status
    (`diff --quiet` is 0 for same, 1 for different, 128 for no repo at all)."""
    try:
        return subprocess.run(["git", "-C", root, *args],
                              capture_output=True, text=True, timeout=10).returncode
    except (OSError, subprocess.SubprocessError):
        return None


def locate(path: str) -> Tuple[str, str]:
    """The working tree that contains `path`, and `path` within it (GitHub #171).

    EVERY git question this tool asks is about the FILE it was handed, not about
    the copy of the tool that happens to be running -- and those are two different
    trees whenever a linked worktree is involved. `REPO_ROOT` is derived from
    `__file__`, so asking it about a worktree's `index.html` produced
    `.claude/worktrees/<name>/index.html`: a path that exists in no commit, which
    `git diff HEAD --` then reports as "differs" for free. The refusal was right
    and the question was wrong.

    `rev-parse --show-toplevel` is the one thing that answers this correctly for a
    linked worktree, whose `.git` is a FILE holding a `gitdir:` pointer -- walking
    up for a `.git` DIRECTORY finds the main checkout's, and `--git-common-dir`
    names the main repo by design. Both land back on the bug.

    Falls back to `REPO_ROOT` when git cannot answer at all (no git, no repo), so
    a path outside any working tree still gets a printable name and
    `matches_commit()` still says "not committed" -- which is what makes the guard
    refuse rather than proceed.
    """
    real = os.path.realpath(path)
    top = _git(os.path.dirname(real) or ".", "rev-parse", "--show-toplevel")
    root = os.path.realpath(top) if top else REPO_ROOT
    rel = os.path.relpath(real, root).replace(os.sep, "/")
    # A file in no working tree at all has no repo-relative name, and a ladder of
    # `../` is not one -- it is a path the refusal message then asks the reader to
    # decode. Say where the file actually is; git will decline it either way, which
    # is what keeps the guard refusing.
    return (root, real) if rel.startswith("../") else (root, rel)


def commit_sha(root: str, explicit: Optional[str] = None) -> Optional[str]:
    """The commit the backlinks will be pinned to.

    `--sha` (the deploy passes `github.sha`) wins, then `$GITHUB_SHA` so a CI run
    is right even if the flag is forgotten, then the local HEAD. Whichever it is,
    `matches_commit()` is asked separately whether the file being stripped is
    actually AT that commit -- the two questions are independent, and conflating
    them is how a stripped file ends up claiming a precision it has not got.

    `root` is the file's own working tree, so a worktree's file is pinned to the
    WORKTREE's HEAD -- which is the commit its lines are true of.
    """
    return explicit or os.environ.get("GITHUB_SHA") or _git(root, "rev-parse", "HEAD")


def matches_commit(root: str, rel: str) -> Optional[bool]:
    """Is the working copy of `rel` identical to HEAD's? None when git cannot say.

    `root`/`rel` come from `locate()` together and must not be mixed from two
    sources: a path relative to one tree, asked of another, is the GitHub #171
    fault exactly.

    Untracked is asked about separately, because `git diff` ignores a file it has
    never heard of and would report a brand-new file as unchanged.
    """
    if _git_rc(root, "ls-files", "--error-unmatch", "--", rel) != 0:
        return False
    rc = _git_rc(root, "diff", "--quiet", "HEAD", "--", rel)
    return None if rc is None or rc > 1 else rc == 0


def repo_url(root: str) -> Optional[str]:
    """The origin remote, as an https URL. Never hardcoded -- see the docstring:
    the URL is the one fact in the banner that can go stale, and the remote is
    where it actually lives."""
    raw_url = _git(root, "remote", "get-url", "origin")
    if not raw_url:
        return None
    url = raw_url
    scp = re.match(r"^(?:ssh://)?(?:[^@/]+@)?([^:/]+)[:/](.+?)(?:\.git)?/?$", url)
    if url.startswith(("http://", "https://")):
        return re.sub(r"(?:\.git)?/?$", "", url)
    if scp:
        return f"https://{scp.group(1)}/{scp.group(2)}"
    return url


def blob_url(url: Optional[str], rel: str, sha: Optional[str]) -> Optional[str]:
    """The permanent address of the file this was stripped from.

    Pinned to a COMMIT, never to `main`: a line number is only true of one
    revision, and 709 markers pointing at a moving branch are 709 wrong
    references the first time anything above them is edited.
    """
    if not url:
        return None
    return f"{url}/blob/{sha or 'main'}/{rel}"


def banner(url: Optional[str], rel: str = "index.html", sha: Optional[str] = None,
           markers: bool = True, at_commit: Optional[bool] = None) -> str:
    """The one place the source URL, the commit and the marker convention are
    stated -- so that every site below can cost four characters and a number.

    Nothing in here may contain `-->`, which is why the marker convention is
    described by its JS form alone: writing the markup form out would close this
    comment at the first one and publish the rest of the banner as page text.
    """
    blob = blob_url(url, rel, sha)
    where = blob or "the source repository"
    lines = [
        f"<!-- {BANNER_MARK}.",
        "     The source of this page is heavily commented -- every derived",
        "     constant, every rejected alternative, every issue number. None of",
        "     that is here; it lives with the code at",
        f"       {where}",
    ]
    if markers:
        lines += [
            "     Each /*L1234*/ below (and the equivalent markup comment) is where",
            "     a comment was removed, naming the line it stood on: add #L1234 to",
            "     the URL above to read it.",
        ]
        if sha:
            lines.append("     That URL is pinned to the exact commit this file was built"
                         " from,")
            lines.append("     so the line numbers stay true however the source moves on.")
        else:
            lines.append("     No commit could be determined when this was built, so that"
                         " URL")
            lines.append("     is UNPINNED and the line numbers drift as the source changes.")
        if at_commit is False:
            lines.append("     Built from a working copy that DIFFERED from that commit:"
                         " the line")
            lines.append("     numbers describe something unpushed, so treat them as"
                         " approximate.")
    lines += [
        "     Generated by tools/strip_comments.py. Do not edit this file: edit",
        f"     {rel} in the repo above. -->",
    ]
    return "\n".join(lines) + "\n"


def inject_banner(html: str, url: Optional[str], **kw) -> str:
    """Place the banner immediately AFTER the doctype, never before it.

    A comment ahead of `<!DOCTYPE html>` is legal in the HTML5 parser but is the
    classic way to lose standards mode in older engines, and there is nothing to
    be gained by finding out which ones still care.
    """
    text = banner(url, **kw)
    m = re.match(r"^\s*<!DOCTYPE[^>]*>\s*\n?", html, re.I)
    if not m:
        return text + html
    return html[:m.end()] + text + html[m.end():]


def without_banner(out: str) -> str:
    """The output with this tool's own banner cut out, for the checks that count
    markers: the banner explains the convention BY SHOWING ONE, so a naive count
    over the whole file is always one too many.

    Found by PLAIN SEARCH rather than by `comment_spans()` (GitHub #161). This
    feeds the checks whose whole purpose is to not depend on the tokenizer, and a
    tokenizer confused enough to have mislaid the banner would then have handed
    them the banner's own example marker to reason about. The banner is this
    tool's own output, it is the first comment in the file, and `--selftest`
    asserts it contains exactly one `-->`, so `<!--` before the mark and the first
    `-->` after it is the whole of it.
    """
    at = out.find(BANNER_MARK)
    if at < 0:
        return out
    start = out.rfind("<!--", 0, at)
    end = out.find("-->", at)
    if start < 0 or end < 0:
        return out
    return out[:start] + out[end + 3:]


def raw_text_bodies(html: str, tag: str) -> List[str]:
    """The bodies of every real `<script>` or `<style>` element, in document order.

    WALKED AS A DOCUMENT, not swept for with a regex (GitHub #161). This is the
    same trap the module docstring names for `comment_spans()` and it was live
    here: `re.finditer(r'<script\\b')` counts the word wherever it appears,
    including inside a comment discussing it, and `fidget/index.html` line 75 says
    "The <style> block below carries..." in exactly such a comment. So the source
    measured two stylesheets and the stripped artifact one, and the pair of them
    disagreeing is a genuine finding about the extractor rather than about the
    strip. index.html was passing by luck: its three `<script` are three real tags.

    HTML comments are skipped, tags are stepped over with quoted attribute values
    honoured, and a raw-text element is left at its real close tag -- so a `<style`
    inside a script's own string is never seen, because the walk is already past it.
    An element with no body (`<script src=...>`) contributes nothing.
    """
    want = tag.lower()
    bodies: List[str] = []
    i, n = 0, len(html)
    while i < n:
        if html[i] != "<":
            i += 1
            continue
        if html.startswith("<!--", i):
            end = html.find("-->", i + 4)
            i = n if end < 0 else end + 3
            continue
        m = RAW_TEXT_TAG.match(html, i)
        if not m:
            i = _skip_tag(html, i)
            continue
        # A raw-text element of EITHER kind is left at its own close tag, whichever
        # one it is: the walk has to step over a <script> whole even when it is
        # looking for stylesheets, or a `<style` in the script's own text is next.
        found = m.group(1).lower()
        body = _skip_tag(html, i)
        close = re.compile(r"</" + found + r"\s*>", re.I).search(html, body)
        if close is None:
            i = n
            continue
        if found == want and html[body:close.start()].strip():
            bodies.append(html[body:close.start()])
        i = close.end()
    return bodies


def script_bodies(html: str) -> List[str]:
    """Inline script bodies only -- `<script src=...>` has no body to check."""
    return raw_text_bodies(html, "script")


NO_NODE = ("node is not on PATH -- the output cannot be verified, "
           "and an unverified strip must not be published")


@functools.lru_cache(maxsize=None)
def _node_parses(body: str) -> Tuple[Optional[bool], str]:
    """Does `node --check` accept this text? `(None, why)` if node could not say.

    Split out of `node_check()` because the surviving-comment probe below asks the
    same question dozens of times about perturbed copies of the same body, and the
    two must agree about what "parses" means or the probe's verdict is measured
    against a different oracle from the one that gates the file.

    Memoised because it is a pure function of the text and the selftest verifies
    several artifacts that share a script body byte for byte -- the banner goes in
    the head, so `strip()`'s output and `inject_banner()`'s are the same JavaScript
    and were being parsed twice over.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(body)
        path = fh.name
    try:
        r = subprocess.run(["node", "--check", path],
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0, (r.stderr.strip() or r.stdout.strip())
    except FileNotFoundError:
        return None, NO_NODE
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"node --check failed to run: {exc}"
    finally:
        os.unlink(path)


def node_check(bodies: List[str]) -> List[str]:
    """`node --check` each script body. Returns a list of failures.

    `node --check` cannot read HTML, which is the whole reason the bodies are
    extracted first. A missing node is itself a failure: an unverified strip is
    not a strip anybody should publish.
    """
    fails: List[str] = []
    for n, body in enumerate(bodies):
        ok, why = _node_parses(body)
        if ok is None:
            fails.append(why)
            break
        if not ok:
            fails.append(f"script body #{n + 1} does not parse:\n{why}")
    return fails


# A perturbation that a comment can swallow and nothing else can. `${'` is an
# unterminated string inside a template substitution and a stray quote inside an
# ordinary string; the newline is illegal inside every JS literal except a
# template. Inside a comment both are just characters.
PROBE_TAIL = "${'"


def _comment_candidates(body: str) -> Iterator[Tuple[int, str]]:
    """Every `//` or `/*` in a stripped script body that is not one of ours.

    The markers are blanked to spaces rather than deleted so the offsets still
    address `body` itself -- the probe has to perturb the real text, not a copy
    with different coordinates.
    """
    blanked = BACKLINK_ONE.sub(lambda m: " " * len(m.group(0)), body)
    for m in re.finditer(r"//|/\*", blanked):
        yield m.start(), m.group(0)


def js_leftovers(bodies: List[str]) -> List[str]:
    """Surviving JS comments, decided by NODE rather than by our own tokenizer.

    This is the check the idempotence pass could not be (GitHub #161). Asking
    `comment_spans()` whether anything is left is asking the tokenizer to review
    its own work, and the misparse that keeps a comment keeps it from both passes
    identically. So each candidate is perturbed instead, in a way that is inert
    inside a comment and fatal inside a string, a template literal or a regex:

      - `//` is deleted to end of line, AND given a `PROBE_TAIL`. Both must still
        parse. Two perturbations rather than one because either alone has a class
        it gets wrong -- deletion is survivable inside a multi-line template, and
        the tail is survivable inside a single-quoted string on the odd occasion.
      - `/*` is given a newline and a `PROBE_TAIL`. The newline alone would be
        enough for quoted strings and regexes; the tail is what refuses a template
        literal, which may legally contain the newline.

    A candidate that still parses under all of its perturbations BEHAVES like a
    comment, and the delivered file is not allowed to contain one. Ten cases pin
    the classifier in `--selftest`, five that are comments and five that are not.

    Cost is one `node --check` per candidate in the ordinary case, because the
    first perturbation fails immediately for anything inside a literal. Both
    published files measure 1 candidate between them -- `'http://www.w3.org/2000/svg'`
    in /fidget/ -- so this is a couple of node invocations, not a sweep.
    """
    fails: List[str] = []
    for n, body in enumerate(bodies):
        for at, tok in _comment_candidates(body):
            if tok == "//":
                eol = body.find("\n", at)
                eol = len(body) if eol < 0 else eol
                probes = [body[:at] + body[eol:],
                          body[:at + 2] + PROBE_TAIL + body[at + 2:]]
            else:
                probes = [body[:at + 2] + "\n" + PROBE_TAIL + body[at + 2:]]

            for probe in probes:
                ok, why = _node_parses(probe)
                if ok is None:
                    return fails + [why]
                if not ok:
                    break
            else:
                ctx = body[max(0, at - 50):at + 40].replace("\n", " ")
                fails.append(f"script body #{n + 1}: {tok!r} at offset {at} behaves "
                             f"like a JavaScript comment and survived the strip -- "
                             f"...{ctx}...")
    return fails


def brace_balance(text: str) -> int:
    """Net `{` minus `}` across the whole document. A crude figure, but it is
    the same crude figure before and after, and a stripper that ate into a CSS
    rule or a JS block moves it.

    Crude in one specific way that matters, which is why the CSS census below
    exists: it is a NET count over the WHOLE document, so an eaten `{` and an
    eaten `}` cancel, and a declaration eaten from inside a rule moves it not at
    all.
    """
    return text.count("{") - text.count("}")


def style_bodies(html: str) -> List[str]:
    """Inline stylesheet bodies, the same way `script_bodies()` does scripts."""
    return raw_text_bodies(html, "style")


def _css_strings_blanked(body: str) -> str:
    """`body` with the CONTENTS of every quoted string replaced by spaces.

    Offsets are preserved so a finding can still be reported against the real
    text. CSS strings cannot span a newline and have no sibling construct that
    quotes -- no regex literals, no template literals -- so this is the whole of
    what has to be excluded before a `/*` in a stylesheet means what it says.
    """
    out = list(body)
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c in "\"'":
            j = i + 1
            while j < n and body[j] != c and body[j] != "\n":
                if body[j] == "\\":
                    out[j] = " "
                    j += 1
                    if j < n:
                        out[j] = " "
                        j += 1
                    continue
                out[j] = " "
                j += 1
            i = j + 1
            continue
        i += 1
    return "".join(out)


def css_leftovers(out: str) -> List[str]:
    """Any comment surviving in a delivered stylesheet. Asks nothing of anybody.

    THIS IS THE ONE ABSOLUTE CHECK IN THE FILE (GitHub #161), and CSS is the only
    language here that admits one. After a correct strip a `<style>` body contains
    no `/*` and no `*/` at all, outside a quoted string and outside this tool's own
    markers -- measured as exactly zero in both published files. So there is
    nothing to compare against the source and nothing to ask the tokenizer: a
    delimiter is either there or it is not.

    That is worth more here than anywhere else, because CSS has no `node --check`
    behind it and the pixel gate only photographs states that render. A rule that
    applies on `:focus-visible`, or inside `@media (prefers-reduced-motion)`, is
    invisible to every other gate on the deploy path.
    """
    fails: List[str] = []
    for n, body in enumerate(style_bodies(out)):
        blanked = _css_strings_blanked(BACKLINK_ONE.sub(
            lambda m: " " * len(m.group(0)), body))
        for m in re.finditer(r"/\*|\*/", blanked):
            ctx = body[max(0, m.start() - 50):m.start() + 40].replace("\n", " ")
            fails.append(f"a comment survived into the delivered stylesheet: "
                         f"{m.group(0)!r} in style block #{n + 1} at offset "
                         f"{m.start()} -- ...{ctx}...")
    return fails


def css_structure(body: str, collapse: bool = False) -> List[str]:
    """An ordered census of one stylesheet: at-rules, selectors, property names.

    WHAT IT IS FOR. `brace_balance` is a net count and `node --check` does not read
    CSS, so until this existed a strip that ate a declaration out of a rule passed
    every check on the deploy path (GitHub #161). The census is per-block and
    ordered, so an eaten declaration, an eaten selector, a lost brace or a
    reordering all move it, whether or not the rule is one anything ever renders.

    WHAT IT DOES NOT TRUST. It lexes CSS itself rather than reusing
    `_css_spans()`, and it reaches the stylesheet through `style_bodies()` rather
    than through `comment_spans()`' document walk -- so a runaway span from the JS
    side, a misidentified `<style>` tag, or damage from `apply_spans()`' line
    tidying all show up as a census that stopped matching. What it cannot be
    independent of is the belief that `/*` opens a comment in CSS, and it does not
    need to be: CSS has no regex literal and no template literal, so that is a fact
    rather than a decision. All the tool's real fragility is on the JS side.

    `collapse` removes whitespace inside selectors as well, for the `--no-markers`
    path, where a block comment welded between two tokens becomes a space instead
    of a marker. Property names always have their whitespace removed -- a property
    name cannot contain any.
    """
    toks: List[str] = []
    buf: List[str] = []
    i, n = 0, len(body)

    def prelude() -> str:
        text = "".join(buf)
        return re.sub(r"\s+", "" if collapse else " ", text).strip()

    def flush() -> None:
        text = prelude()
        if not text:
            return
        # A `:` makes it a declaration and everything before the FIRST one is the
        # property. `background:url(https://x)` has three colons and one property.
        if ":" in text:
            toks.append("decl " + re.sub(r"\s+", "", text.split(":", 1)[0]))
        else:
            toks.append("at " + text)

    while i < n:
        c = body[i]
        if body.startswith("/*", i):
            end = body.find("*/", i + 2)
            i = n if end < 0 else end + 2
            buf.append(" ")
            continue
        if c in "\"'":
            j = i + 1
            while j < n and body[j] != c:
                j += 2 if body[j] == "\\" else 1
            buf.append(body[i:min(j + 1, n)])
            i = j + 1
            continue
        if c == "{":
            toks.append("{ " + prelude())
            buf = []
            i += 1
            continue
        if c == "}":
            flush()
            buf = []
            toks.append("}")
            i += 1
            continue
        if c == ";":
            flush()
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    flush()
    return toks


def verify_css(src: str, out: str, markers: bool) -> List[str]:
    """The stylesheet half of verification: no survivors, and no lost structure."""
    fails: List[str] = list(css_leftovers(out))
    src_blocks, out_blocks = style_bodies(src), style_bodies(out)
    if len(src_blocks) != len(out_blocks):
        fails.append(f"{len(src_blocks)} inline stylesheet(s) in source, "
                     f"{len(out_blocks)} in output")
        return fails
    for n, (s, o) in enumerate(zip(src_blocks, out_blocks)):
        want = css_structure(s, collapse=not markers)
        got = css_structure(o, collapse=not markers)
        if want == got:
            continue
        diff = next((k for k in range(min(len(want), len(got)))
                     if want[k] != got[k]), min(len(want), len(got)))
        was = want[diff] if diff < len(want) else "(end of stylesheet)"
        now = got[diff] if diff < len(got) else "(end of stylesheet)"
        fails.append(
            f"the delivered stylesheet's structure differs from the source's in "
            f"style block #{n + 1}: {len(want)} census entries became {len(got)}, "
            f"first divergence at #{diff + 1}, {was!r} became {now!r}")
    return fails


def verify_delta(src: str, out: str) -> List[str]:
    """The artifact must differ from the source ONLY where a comment was located.

    Source with every located span excised, whitespace discounted, must be byte
    equal to the artifact with the banner and the markers excised, whitespace
    discounted. Whitespace has to be discounted because the cut deliberately drops
    the lines it emptied and the indentation of the lines it left holding only a
    marker.

    BE PRECISE ABOUT WHAT THIS PROVES, because it is the check GitHub #161 asked
    for and the ticket credited it with more than it can do. It does not audit what
    was CALLED a comment -- a span in the wrong place removes bytes this check then
    agrees were removable, so the measured `a++ / 2; // note` case passes it, as
    does any other misparse. What it proves is that nothing ELSE moved: an
    `apply_spans()` fault, a line-tidying fault that dropped a line with code on
    it, a marker written over the byte next to it, or any future step that started
    changing bytes away from a comment site.
    """
    keep: List[str] = []
    pos = 0
    for sp in comment_spans(src):
        keep.append(src[pos:sp.start])
        pos = sp.end
    keep.append(src[pos:])
    want = re.sub(r"\s+", "", "".join(keep))
    got = re.sub(r"\s+", "", BACKLINK_ONE.sub("", without_banner(out)))
    if want == got:
        return []
    at = next((k for k in range(min(len(want), len(got))) if want[k] != got[k]),
              min(len(want), len(got)))
    return [f"the output differs from the source outside every comment it removed: "
            f"{len(want)} non-space bytes of code became {len(got)}, first "
            f"divergence at {at} -- source has {want[at:at + 60]!r}, output has "
            f"{got[at:at + 60]!r}"]


def verify_backlinks(src: str, out: str, markers: bool) -> List[str]:
    """The backlinks must be a true statement about the source, not decoration.

    Two things are asserted and the second is the one that earns its keep:

      - every marker names a line that EXISTS in the source. A marker built from
        the wrong file, or from an offset measured after removal rather than
        before, lands outside the line count and is caught here rather than by
        somebody following a link into the middle of a different function.
      - the number of markers equals the number of source LINES that carried a
        comment. That count comes off the SOURCE, so it cannot be satisfied by
        agreeing with whatever the output happens to contain: a strip that ate a
        run of live code took the comments in it too, and the tally moves.

    With markers off, the assertion inverts -- there must be none, or a stale
    marker is being published with no banner to explain it.
    """
    fails: List[str] = []
    body = without_banner(out)
    found = BACKLINK_ONE.findall(body)

    if not markers:
        if found:
            fails.append(f"{len(found)} backlink marker(s) in an output built with "
                         f"--no-markers, first {found[0]!r}")
        return fails

    line_count = src.count("\n") + 1
    numbers = [int(BACKLINK_NUM.search(f).group(1)) for f in found]
    outside = [n for n in numbers if n < 1 or n > line_count]
    if outside:
        fails.append(f"{len(outside)} backlink marker(s) name a line the source does "
                     f"not have ({line_count} lines), first L{outside[0]}")

    want = len({_line_index(src)(sp.start) for sp in comment_spans(src)})
    if len(found) != want:
        fails.append(f"{want} source line(s) carry a comment but the output has "
                     f"{len(found)} backlink marker(s) -- a removal went unrecorded")
    return fails


def verify(src: str, out: str, markers: bool = True,
           rel: str = "index.html") -> List[str]:
    """Everything that must still be true of the output. Returns failures.

    `rel` is which published page this is, because the load-bearing anchors are
    per-file (GitHub #161) and a page nobody has declared any for cannot be
    verified at all. The default is `index.html` so that the selftest's fixture --
    which carries that page's anchors on purpose -- and any ad-hoc call read
    naturally; the deploy passes the real path for both of its files.
    """
    fails: List[str] = []
    fails.extend(verify_backlinks(src, out, markers))

    # PRESENCE, not count. Every one of these names is also DISCUSSED in the
    # commentary -- `SPINDOWN_RANGE_MS` appears seven times in the source and
    # twice in the code -- so a count that drops is the tool working. What must
    # never happen is one going to zero: that is a gate's anchor deleted.
    #
    # An undeclared file FAILS rather than passing with nothing checked. The old
    # flat tuple was `index.html`'s strings, and `marker in src and marker not in
    # out` is vacuously true for a file that never had them -- so /fidget/ was
    # anchored by five conditions none of which could fire.
    anchors = REQUIRED_MARKERS.get(rel)
    if anchors is None:
        fails.append(f"no required markers are declared for {rel!r}, so nothing "
                     f"anchors its code -- add them to REQUIRED_MARKERS")
    else:
        for marker in anchors:
            if marker in src and marker not in out:
                fails.append(f"marker {marker!r} is in the source and gone from "
                             f"the output")
            elif marker not in src:
                fails.append(f"required marker {marker!r} is not in {rel!r} at all, "
                             f"so it anchors nothing -- REQUIRED_MARKERS is stale")

    if brace_balance(src) != brace_balance(out):
        fails.append(f"brace balance moved: {brace_balance(src)} -> "
                     f"{brace_balance(out)}; a comment cut into real syntax")

    # The artifact may differ from the source only where a comment was located.
    fails.extend(verify_delta(src, out))

    src_bodies, out_bodies = script_bodies(src), script_bodies(out)
    if len(src_bodies) != len(out_bodies):
        fails.append(f"{len(src_bodies)} inline script(s) in source, "
                     f"{len(out_bodies)} in output")
    fails.extend(node_check(out_bodies))
    # ...and node, not this file's tokenizer, says whether a comment survived one.
    fails.extend(js_leftovers(out_bodies))

    # The stylesheet, which has no parser of its own on the deploy path.
    fails.extend(verify_css(src, out, markers))

    # Idempotence: a second pass must find nothing but this tool's own banner and
    # its backlink markers. Anything else means the first pass left a comment it
    # could not recognise. THIS IS THE CIRCULAR ONE -- the tokenizer reviewing its
    # own work, which a misparse passes by construction because both passes make
    # the same mistake (GitHub #161). It is kept because it costs nothing and it
    # still catches a comment SHAPE the scanner does not know, and it is listed
    # last because it is no longer what the guarantee rests on. The marker
    # exemption is by exact shape, so a real comment cannot slip through it.
    leftovers = [sp for sp in comment_spans(out)
                 if BANNER_MARK not in out[sp.start:sp.end]
                 and not BACKLINK_ONE.fullmatch(out[sp.start:sp.end])]
    if leftovers:
        sample = out[leftovers[0].start:leftovers[0].start + 60].replace("\n", " ")
        fails.append(f"{len(leftovers)} comment(s) survived the strip, first: {sample!r}")

    return fails


def sizes(text: str) -> Tuple[int, int, Optional[int]]:
    """Raw, gzip and -- when the module is installed -- brotli.

    brotli is what CloudFront actually negotiates with a modern browser, so it is
    the only one of the three that is a wire figure. It is OPTIONAL rather than a
    dependency: a stripper that will not run without a compression library it does
    not need in order to strip would be a worse tool, so the report says "not
    measured" and everything else still works.
    """
    raw = text.encode()
    # mtime=0 so the figure is reproducible, and level 9 because CloudFront and
    # S3 both serve a precompressed object at whatever level it was made with.
    gz = len(gzip.compress(raw, compresslevel=9, mtime=0))
    try:
        import brotli  # type: ignore
        return len(raw), gz, len(brotli.compress(raw, quality=11))
    except Exception:
        return len(raw), gz, None


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

# Every line here is a trap that a regex sweep gets wrong. The point is not
# coverage of the stripper's branches; it is that each of these constructs
# survives BYTE FOR BYTE, because the failure mode being guarded against is
# silent deletion of live code that still parses afterwards.
FIXTURE = r'''<!DOCTYPE html>
<html>
<head>
<!-- an HTML comment, with Charles's apostrophe in it, that must go, and which mentions the <style> and <script> blocks below without either being a tag -->
<style>
/* a CSS comment -- it's got an apostrophe too */
a{background:url(https://wozi.com//double/slash.png);color:#fff}
b:after{content:"/* not a comment */"}
button:focus-visible{outline:2px solid #f00;outline-offset:2px}  /* a state no screenshot photographs */
@media (prefers-reduced-motion:reduce){
  .spin{animation:none;transition:none}   /* nor this one */
}
</style>
</head>
<body>
<div data-props="{&quot;speed&quot;:1}" title="a -- b">keep</div>
<script>
const site = 'https://wozi.com//path';   // strip this trailing note
const alsoSite = "http://example.com//x";
const notComment = 'a // b and a /* c */ d';
const tpl = `template with /* not a comment */ and // not one either`;
const nested = `outer ${ inner('a // b') } tail`;
const seedRe = /[?&]seed=([^&]*)/;
const slashy = /a\/\*b/;
const div = (10) / 2 / 1;
let n = 7;
const inc = n++ / 2;   // a postfix increment is division, so this must go
const dec = n-- / 2;   /* and so is this one */
/* a block comment
   spanning lines, with an apostrophe: it's gone */
const MIN_CUT_PX = 3;          // keep the value, drop this
const SPINDOWN_RANGE_MS = 4500;
const GHOST_COLORS = ['#aaa'];
function f(){ return /\/\*/.test(site); }
    /* an indented standalone note, whose indent must not be paid for */
const two = 1; /* first */ /* second on the same line */
</script>
<label aria-label="Gear speed">x</label>
</body>
</html>
'''

MUST_SURVIVE = (
    "'https://wozi.com//path'",
    '"http://example.com//x"',
    "'a // b and a /* c */ d'",
    "`template with /* not a comment */ and // not one either`",
    "`outer ${ inner('a // b') } tail`",
    "/[?&]seed=([^&]*)/",
    r"/a\/\*b/",
    "(10) / 2 / 1",
    r"/\/\*/.test(site)",
    "url(https://wozi.com//double/slash.png)",
    'content:"/* not a comment */"',
    'data-props="{&quot;speed&quot;:1}"',
    'title="a -- b"',
    'aria-label="Gear speed"',
    "const MIN_CUT_PX = 3;",
    "SPINDOWN_RANGE_MS = 4500",
    "GHOST_COLORS = ['#aaa']",
    "const two = 1;",
    # The two GitHub #161 cases. A postfix increment leaves a value, so both of
    # these are division and both trailing comments must be found -- with `prev`
    # holding a bare `+` the `/` read as a regex opener, the scan ran forward to
    # the comment's own `/`, and the comment was published.
    "const inc = n++ / 2;",
    "const dec = n-- / 2;",
    # A rule that only applies while an element has focus, and one that only
    # applies under a media query: states no screenshot on the deploy path
    # photographs, which is why the CSS census counts them rather than trusting a
    # picture to.
    "button:focus-visible{outline:2px solid #f00;outline-offset:2px}",
    "@media (prefers-reduced-motion:reduce)",
    ".spin{animation:none;transition:none}",
)

MUST_GO = (
    "an HTML comment",
    "a CSS comment",
    "strip this trailing note",
    "spanning lines",
    "keep the value, drop this",
    "indented standalone note",
    "second on the same line",
    "postfix increment is division",
    "and so is this one",
    "a state no screenshot photographs",
    "nor this one",
    "without either being a tag",
)

# Every marker the fixture must produce, in source order and by exact text. Not a
# count: a count passes while the numbers are all one too high, which is the whole
# failure this is here to catch. L4 is markup and takes the markup syntax; L36
# carries TWO comments and gets ONE marker, because a line number said twice says
# nothing twice.
FIXTURE_BACKLINKS = ("<!--L4-->", "/*L6*/", "/*L9*/", "/*L11*/", "/*L18*/",
                     "/*L27*/", "/*L28*/", "/*L29*/", "/*L31*/", "/*L35*/",
                     "/*L36*/")

# Ten hand-built cases pinning the node probe that decides whether a `//` or `/*`
# left in a delivered script body is a comment. Five are, five are not, and the
# ones that earn their keep are the template literals: a `//` inside a MULTI-LINE
# template survives being deleted to end of line, so the naive probe calls it a
# comment. `PROBE_TAIL` is what refuses it.
PROBE_CASES = (
    ("a real line comment",       "const a = 1; // a real comment\nconst b = 2;\n", True),
    ("a real block comment",      "const a = 1; /* real\nblock */\nconst b = 2;\n", True),
    ("a standalone line comment", "// nothing but a comment\nconst a = 1;\n", True),
    ("a trailing block comment",  "const a = 1; /* short */\n", True),
    ("a commented-out line",      "const a = 1;\n// const b = 2;\n", True),
    ("`//` in a single-quoted string", "const s = 'a // b';\nconst c = 1;\n", False),
    ("`//` in a URL",             'const s = "http://x//y";\nconst c = 1;\n', False),
    ("`//` in a multi-line template",
     "const s = `a // b\nmore`;\nconst c = 1;\n", False),
    ("`//` in a regex class",     "const r = /[//]/;\nconst c = 1;\n", False),
    ("`/*` in a multi-line template",
     "const s = `a /* c */ d\ntail`;\nconst c = 1;\n", False),
)


def selftest() -> None:
    fails: List[str] = []
    out = strip(FIXTURE)

    for needle in MUST_SURVIVE:
        if needle not in out:
            fails.append(f"EATEN LIVE CODE: {needle!r} is not in the output")
    for needle in MUST_GO:
        if needle in out:
            fails.append(f"comment survived: {needle!r}")

    # The apostrophes are called out separately because they are the specific
    # thing that turns a comment into an unterminated string for a tokeniser
    # that tracks quotes without knowing it is inside a comment.
    if "apostrophe" in out:
        fails.append("a comment containing an apostrophe was not removed")

    # A raw-text element is found by WALKING the document, not by finding its name.
    # The fixture's first comment discusses both blocks by name, which is what
    # `re.finditer(r'<style\b')` counted as a second stylesheet in the source and
    # not in the artifact -- a difference caused entirely by the extractor.
    for kind, found in (("style", style_bodies), ("script", script_bodies)):
        if len(found(FIXTURE)) != 1 or len(found(out)) != 1:
            fails.append(f"<{kind}> is being found by name rather than by walking "
                         f"the document: {len(found(FIXTURE))} in the source and "
                         f"{len(found(out))} in the output, and there is one")

    fails.extend(verify(FIXTURE, out))

    # THE BACKLINKS, BY EXACT TEXT AND IN ORDER. The numbers are the whole value
    # of the feature: a marker that names the wrong line is worse than no marker,
    # because it sends a reader to prose about something else and looks right doing
    # it. Order matters too -- markers found out of source order would mean the
    # line index and the cut are disagreeing about where they are.
    got = BACKLINK_ONE.findall(out)
    if tuple(got) != FIXTURE_BACKLINKS:
        fails.append(f"backlinks are {got} and should be {list(FIXTURE_BACKLINKS)}")
    # An indent kept for a line with no code left on it is bytes paid for nothing.
    if "\n/*L35*/\n" not in out:
        fails.append("a marker-only line kept the indentation of the comment it replaced")
    # The markup form is not interchangeable with the JS form: `/*L4*/` in the
    # document body is text on the page, and `<!--L6-->` inside <style> is not a
    # CSS comment. Assert the one that would be visible rather than merely wrong.
    if "/*L4*/" in out:
        fails.append("a markup comment was replaced with a JS marker, which would "
                     "print on the page")

    # With markers off there must be none at all, and the file must still verify:
    # this is the path that prices them, so it has to be a real strip.
    bare = strip(FIXTURE, markers=False)
    if BACKLINK_ONE.search(bare):
        fails.append("--no-markers still emitted a backlink marker")
    fails.extend(verify(FIXTURE, bare, markers=False))
    if len(bare) >= len(out):
        fails.append("the marked output is not larger than the unmarked one, so the "
                     "cost being reported is not the markers' cost")

    # The banner must be injected after the doctype, and must not disturb it. It
    # also has to survive being a COMMENT that contains an example marker: written
    # carelessly it would close itself at the first `-->` and publish its own
    # remaining prose as page text.
    stamped = inject_banner(out, "https://github.com/example/repo",
                            rel="index.html", sha="deadbeef" * 5, markers=True,
                            at_commit=True)
    if not stamped.lower().startswith("<!doctype html>"):
        fails.append("the banner displaced the doctype")
    if BANNER_MARK not in stamped or "https://github.com/example/repo" not in stamped:
        fails.append("the banner is missing or does not name the repo")
    if "/blob/" + "deadbeef" * 5 + "/index.html" not in stamped:
        fails.append("the banner does not carry a commit-pinned URL for the source")
    first = comment_spans(stamped)[0]
    if BANNER_MARK not in stamped[first.start:first.end]:
        fails.append("the banner is not the first comment in the output")
    if stamped.count("-->", first.start, first.end) != 1:
        fails.append("the banner closes itself early -- its own text contains `-->`")
    # The repo is public, so the banner must not apologise for a sign-in wall that
    # is not there. Asserted rather than merely deleted: the caveat was true for the
    # whole life of this tool, which makes it exactly the sentence somebody
    # reinstates from memory.
    for stale in ("private", "sign-in"):
        if stale in stamped[first.start:first.end]:
            fails.append(f"the banner still calls the source repository {stale!r}")
    fails.extend(verify(FIXTURE, stamped))

    # A dirty tree must be admitted in the banner rather than implied away.
    dirty = inject_banner(out, "https://github.com/example/repo", sha="c0ffee",
                          at_commit=False)
    if "DIFFERED" not in dirty:
        fails.append("a build from a modified working copy does not say so")

    # THE NODE PROBE'S OWN CLASSIFIER, both ways round. A probe that answers "yes"
    # to everything would make the leftover check unusable and a probe that answers
    # "no" to everything would make it vacuous, which is the shape of the fault
    # GitHub #161 was about in the first place.
    for name, body, is_comment in PROBE_CASES:
        found = bool(js_leftovers([body]))
        if found != is_comment:
            fails.append(f"the surviving-comment probe says {name} is "
                         f"{'a comment' if found else 'not a comment'}")

    # EVERY CHECK ADDED FOR GitHub #161, SHOWN GOING RED. A check nobody has
    # watched fail is not a check -- that is what `tools/mutation_gate.py` exists
    # to say about the pixel gate, and it applies here. Each case mangles the
    # VERIFIED artifact in one specific way and demands the failure that names it,
    # by substring, so a mutation caught by some other check for some other reason
    # does not count as proof.
    def mangled(text: str, old: str, new: str) -> str:
        if old not in text:
            fails.append(f"the negative case for {old!r} no longer applies to the "
                         f"fixture, so it is proving nothing")
        return text.replace(old, new, 1)

    negatives = (
        # A comment left standing in the delivered stylesheet. Absolute: there is
        # nothing to compare it against.
        ("a surviving CSS comment",
         mangled(stamped, ".spin{", "/* left behind */.spin{"),
         "comment survived into the delivered stylesheet"),
        # A comment left standing in the delivered script. Only node can say so.
        ("a surviving JS comment",
         mangled(stamped, "const two = 1;", "// left behind\nconst two = 1;"),
         "behaves like a JavaScript comment"),
        # One declaration eaten out of a rule that applies only while an element
        # has focus. Braces still balance, the page still parses, and no screenshot
        # on the deploy path renders the state.
        ("a declaration eaten from :focus-visible",
         mangled(stamped, ";outline-offset:2px", ""),
         "the delivered stylesheet's structure differs"),
        # ...and out of a media query nothing on the deploy path matches either.
        ("a declaration eaten from prefers-reduced-motion",
         mangled(stamped, ";transition:none", ""),
         "the delivered stylesheet's structure differs"),
        # A line of live code gone from the artifact with no comment near it. This
        # is the case `verify_delta` is for, and the one shape of it the census and
        # the probes cannot see.
        ("a line of live code eaten",
         mangled(stamped, "const GHOST_COLORS = ['#aaa'];", ""),
         "differs from the source outside every comment"),
    )
    for name, bad, want in negatives:
        got = verify(FIXTURE, bad)
        if not any(want in f for f in got):
            fails.append(f"a mangled artifact ({name}) was NOT rejected for the "
                         f"reason it should have been: wanted {want!r}, got {got}")

    # A page nobody has declared anchors for must not verify at all: the old flat
    # tuple made five conditions that could never fire read as five that had passed.
    if not any("no required markers are declared" in f
               for f in verify(FIXTURE, stamped, rel="nobody/declared-this.html")):
        fails.append("a file with no declared anchors verified anyway, so its code "
                     "is unanchored and nothing says so")
    # ...and a declared anchor that is not in the file anchors nothing.
    for rel, anchors in REQUIRED_MARKERS.items():
        path = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        for anchor in anchors:
            if anchor not in text:
                fails.append(f"REQUIRED_MARKERS names {anchor!r} for {rel}, which "
                             f"does not contain it -- it anchors nothing")

    # THE MEASURED MISPARSE FROM GitHub #161, END TO END. Both halves: the comment
    # must be found, and the string next to a postfix increment must come through
    # untouched -- that second one is how the fault deleted rather than merely kept,
    # and it parsed afterwards, so nothing but a pixel would have objected.
    ticket = ("<script>\nconst x = a++ / 2; // this comment was published\n"
              "let s = 'x /y/ /* z */ w';\nlet k = 9;\n</script>\n")
    ticket_out = strip(ticket)
    if "this comment was published" in ticket_out:
        fails.append("the GitHub #161 misparse is back: a `/` after a postfix "
                     "increment reads as a regex opener and the comment survives")
    if "'x /y/ /* z */ w'" not in ticket_out:
        fails.append("the GitHub #161 misparse is back: a string after a postfix "
                     "increment had its contents cut out")

    # An unterminated construct must not silently swallow the rest of the file.
    truncated = strip("<script>\nconst a = 1;\n/* never closed\n")
    if "const a = 1;" not in truncated:
        fails.append("an unterminated block comment ate the code before it")

    # GitHub #171: the git questions are about the FILE, not about the tool. A tree
    # of its own, nowhere near `REPO_ROOT`, is the cheap stand-in for the linked
    # worktree that produced the bug -- the fault is identical (`REPO_ROOT` is not
    # the file's tree) and a `git init` costs milliseconds where a `worktree add`
    # costs a checkout. `--show-toplevel` is what has to answer, so the assertion is
    # that the root MOVED and the path within it is the bare filename.
    with tempfile.TemporaryDirectory() as tmp:
        elsewhere = os.path.realpath(tmp)
        env_git = subprocess.run(["git", "-C", elsewhere, "init", "-q"],
                                 capture_output=True, text=True)
        if env_git.returncode == 0:
            open(os.path.join(elsewhere, "index.html"), "w").write("<p>x</p>\n")
            root, rel = locate(os.path.join(elsewhere, "index.html"))
            if root != elsewhere:
                fails.append(f"locate() resolved a file in its own tree to "
                             f"{root!r}, not {elsewhere!r} -- GitHub #171 is back "
                             f"and --in-place will refuse a clean file")
            if rel != "index.html":
                fails.append(f"locate() called that file {rel!r} rather than "
                             f"'index.html', so HEAD is being asked about a path "
                             f"no commit contains -- GitHub #171 is back")
            # An untracked file must still be refused: the guard's whole job.
            if matches_commit(root, rel) is not False:
                fails.append("an uncommitted file read as safe to overwrite in "
                             "place, which is the one unrecoverable mistake")
        else:
            fails.append("selftest could not `git init` a temporary tree, so the "
                         "GitHub #171 path resolution was not tested at all")

    if fails:
        print("SELFTEST FAILED:\n  - " + "\n  - ".join(fails), file=sys.stderr)
        sys.exit(EXIT_SELFTEST)
    print(f"selftest ok: {len(MUST_SURVIVE)} live constructs intact, "
          f"{len(MUST_GO)} comments removed, "
          f"{len(FIXTURE_BACKLINKS)} backlinks correct, output verified")


# --------------------------------------------------------------------------


def _row(label: str, src_n: int, out_n: Optional[int], bare_n: Optional[int]) -> str:
    """One line of the size table: source, delivered, and what the markers cost.

    The marker column is the delivered file measured against the SAME strip with
    the backlinks turned off, so it is the price of the navigability and not of the
    strip -- the two are separate decisions and the report must not blur them.
    """
    if out_n is None:
        return f"  {label:<6}{src_n:>9,} B   ->  {'not measured':>21}"
    pct = 100 * (src_n - out_n) / src_n if src_n else 0
    cost = "" if bare_n is None else \
        f"   markers +{out_n - bare_n:,} B ({100 * (out_n - bare_n) / out_n:.1f}%)"
    return (f"  {label:<6}{src_n:>9,} B   ->  {out_n:>9,} B   "
            f"({pct:5.1f}% smaller){cost}")


def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="strip_comments.py",
        description="Comment-stripped copy of an HTML page, FOR DELIVERY ONLY.")
    ap.add_argument("input", nargs="?", default=DEFAULT_IN)
    ap.add_argument("--out", default=None, help=f"default {DEFAULT_OUT}")
    ap.add_argument("--check", action="store_true",
                    help="strip and verify, write nothing")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--in-place", action="store_true",
                    help="OVERWRITE the input. Refuses unless it matches HEAD.")
    ap.add_argument("--force", action="store_true",
                    help="allow --in-place over a modified file (it is not recoverable)")
    ap.add_argument("--no-markers", dest="markers", action="store_false",
                    help="omit the backlink markers, to price them")
    ap.add_argument("--sha", default=None,
                    help="commit to pin the backlinks to; CI passes github.sha")
    ap.add_argument("--repo-url", default=None,
                    help="base URL for the source, overriding the origin remote")
    a = ap.parse_args(argv)

    if a.selftest:
        selftest()
        return EXIT_OK

    in_path = a.input
    out_path = a.out or (in_path if a.in_place else DEFAULT_OUT)
    same = (os.path.abspath(out_path) == os.path.abspath(in_path))
    # ONE answer to "which tree, and what is it called in there", asked once and
    # used by the guard, the banner and the anchor lookup alike. It was computed
    # twice from `REPO_ROOT` with two different slash conventions, which is two
    # chances to fix one of them (GitHub #171).
    root, rel = locate(in_path)

    # THE ONE UNRECOVERABLE MISTAKE. Overwriting the source is fine when the source
    # is safely in a commit -- the deploy's checkout is -- and destroys work that
    # exists nowhere else when it is not. So the guard is on the FILE's state, not
    # on which flag was typed: `--out index.html index.html` gets it too.
    if same and not a.in_place:
        print(f"refusing to overwrite {in_path} without --in-place", file=sys.stderr)
        return EXIT_USAGE
    if same:
        clean = matches_commit(root, rel)
        if clean is not True and not a.force:
            why = ("git cannot say whether it is committed"
                   if clean is None else "it differs from HEAD")
            print(f"refusing --in-place on {rel}: {why}, and the comments it "
                  f"carries exist nowhere else. Commit first, or pass --force.",
                  file=sys.stderr)
            return EXIT_USAGE

    try:
        src = open(in_path, encoding="utf-8").read()
    except OSError as exc:
        print(f"cannot read {in_path}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    url = a.repo_url or repo_url(root)
    sha = commit_sha(root, a.sha)
    at_commit = matches_commit(root, rel)
    stripped = inject_banner(strip(src, a.markers), url, rel=rel, sha=sha,
                             markers=a.markers, at_commit=at_commit)
    # The unmarked strip exists only to price the markers. It is the same cut, so
    # the difference between the two IS the backlinks and nothing else.
    bare = inject_banner(strip(src, False), url, rel=rel, sha=sha, markers=False,
                         at_commit=at_commit) if a.markers else None

    fails = verify(src, stripped, a.markers, rel=rel)
    if len(stripped) >= len(src):
        fails.append(f"output is not smaller ({len(src)} -> {len(stripped)}) -- "
                     f"nothing was stripped, or the banner is all there is")

    src_raw, src_gz, src_br = sizes(src)
    out_raw, out_gz, out_br = sizes(stripped)
    bare_raw, bare_gz, bare_br = sizes(bare) if bare is not None else (None, None, None)
    print(f"source  {in_path}")
    print(_row("raw", src_raw, out_raw, bare_raw))
    print(_row("gzip", src_gz, out_gz, bare_gz))
    print(_row("br", src_br or 0, out_br, bare_br) if src_br else
          "  br    not measured -- `pip install Brotli` for the figure "
          "CloudFront actually serves")
    print(f"  comments removed: {len(comment_spans(src)):,}")
    print(f"  backlinks:        "
          + (f"{len(BACKLINK_ONE.findall(without_banner(stripped))):,}"
             if a.markers else "none (--no-markers)"))
    # The checks that do not consult the tokenizer, with their subjects counted, so
    # the claim below is a reading rather than a reassurance. A file whose census is
    # empty, or whose probe had nothing to look at, has been verified by nothing --
    # which is what /fidget/'s five inapplicable anchors amounted to (GitHub #161).
    censused = sum(len(css_structure(b, collapse=not a.markers))
                   for b in style_bodies(stripped))
    probed = sum(1 for b in script_bodies(stripped) for _ in _comment_candidates(b))
    print(f"  anchors:          {len(REQUIRED_MARKERS.get(rel, ())):,} declared "
          f"for {rel}")
    print(f"  css census:       {censused:,} entries over "
          f"{len(style_bodies(stripped)):,} stylesheet(s)")
    print(f"  node-probed:      {probed:,} comment opener(s) left in the script "
          f"bodies, none of them a comment")
    print(f"  source:           {blob_url(url, rel, sha) or '(no origin remote found)'}")
    if at_commit is False:
        print("  NOTE: the input differs from that commit, so the line numbers "
              "describe something unpushed -- the banner says so too")

    if fails:
        print("VERIFY FAILED:\n  - " + "\n  - ".join(fails), file=sys.stderr)
        return EXIT_VERIFY
    print("  verified: stylesheet holds no comment and no lost declaration, node "
          "finds no surviving comment,\n            nothing moved outside a comment "
          "site, script bodies parse, anchors intact,\n            braces balanced, "
          "every backlink names a real line")

    if a.check:
        print("  --check: nothing written")
        return EXIT_OK

    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, "w", encoding="utf-8").write(stripped)
    except OSError as exc:
        print(f"cannot write {out_path}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"  wrote {out_path}" + ("  (IN PLACE -- this checkout is now the "
                                   "artifact, not the source)" if same else ""))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
