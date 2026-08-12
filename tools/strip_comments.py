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
decide confidently it KEEPS the text. Every removal is then verified from the
outside: the output's script bodies must still pass `node --check`, the load-
bearing markers other gates match on must still be present, the CSS braces must
still balance, and a second pass over the output must find nothing left to strip
but this tool's own banner and its backlink markers.

The markers are themselves comments, so they widen that last check by exactly
their own shape and no further: a leftover is forgiven only if it matches
`/*L<digits>*/` or the markup form of the same, every marker's line number must
land inside the source's own line count, and the number of markers must equal the
number of source LINES that carried a comment. That last one is the useful half —
a strip that quietly ate a run of code would take the comments in it too, and the
count is computed from the source, so it cannot agree with a mistake.

    tools/strip_comments.py                 # strip, verify, write to scratchpad/
    tools/strip_comments.py --check         # strip and verify, write NOTHING (CI)
    tools/strip_comments.py --selftest      # fixtures for every trap above
    tools/strip_comments.py --out PATH IN   # explicit paths
    tools/strip_comments.py --no-markers    # no backlinks, to price them
    tools/strip_comments.py --in-place F    # OVERWRITE F -- the deploy's own use

Exit codes: 0 ok, 1 verification failed, 2 usage or I/O, 3 selftest failed.
"""
from __future__ import annotations

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

# Markers other gates match on by literal text. Stripping is only allowed to
# remove commentary, so every one of these must survive verbatim. `data-props`
# carries the shipped layer defaults AND the editor schema; the aria-label is
# what tools/devices.py finds the speed slider by; the three identifiers are
# named in CLAUDE.md's invariants, so a strip that ate one has eaten code.
REQUIRED_MARKERS = (
    'data-props=',
    'aria-label="Gear speed"',
    'MIN_CUT_PX',
    'SPINDOWN_RANGE_MS',
    'GHOST_COLORS',
)

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
# `]`, `}`, string) is a value, so the `/` is division.
REGEX_OK_PUNCT = set("(,=:[!&|?{};+-*%~^<>")
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
    `f(x) / 2`) and both are answered "division": that decision removes nothing,
    so it can only ever leave a comment in place, never delete code.
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


def _git(*args: str) -> Optional[str]:
    """`git -C REPO_ROOT ...`, or None if git could not answer at all. Every
    caller treats None as "say less in the banner", never as a value."""
    try:
        r = subprocess.run(["git", "-C", REPO_ROOT, *args],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _git_rc(*args: str) -> Optional[int]:
    """The exit status of a git command, for the ones whose ANSWER is the status
    (`diff --quiet` is 0 for same, 1 for different, 128 for no repo at all)."""
    try:
        return subprocess.run(["git", "-C", REPO_ROOT, *args],
                              capture_output=True, text=True, timeout=10).returncode
    except (OSError, subprocess.SubprocessError):
        return None


def commit_sha(explicit: Optional[str] = None) -> Optional[str]:
    """The commit the backlinks will be pinned to.

    `--sha` (the deploy passes `github.sha`) wins, then `$GITHUB_SHA` so a CI run
    is right even if the flag is forgotten, then the local HEAD. Whichever it is,
    `matches_commit()` is asked separately whether the file being stripped is
    actually AT that commit -- the two questions are independent, and conflating
    them is how a stripped file ends up claiming a precision it has not got.
    """
    return explicit or os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD")


def matches_commit(rel: str) -> Optional[bool]:
    """Is the working copy of `rel` identical to HEAD's? None when git cannot say.

    Untracked is asked about separately, because `git diff` ignores a file it has
    never heard of and would report a brand-new file as unchanged.
    """
    if _git_rc("ls-files", "--error-unmatch", "--", rel) != 0:
        return False
    rc = _git_rc("diff", "--quiet", "HEAD", "--", rel)
    return None if rc is None or rc > 1 else rc == 0


def repo_url() -> Optional[str]:
    """The origin remote, as an https URL. Never hardcoded -- see the docstring:
    the URL is the one fact in the banner that can go stale, and the remote is
    where it actually lives."""
    raw_url = _git("remote", "get-url", "origin")
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
    over the whole file is always one too many."""
    for sp in comment_spans(out):
        if BANNER_MARK in out[sp.start:sp.end]:
            return out[:sp.start] + out[sp.end:]
    return out


def script_bodies(html: str) -> List[str]:
    """Inline script bodies only -- `<script src=...>` has no body to check."""
    bodies = []
    for m in re.finditer(r"<script\b", html, re.I):
        body = _skip_tag(html, m.start())
        close = re.compile(r"</script\s*>", re.I).search(html, body)
        if close is None:
            continue
        text = html[body:close.start()]
        if text.strip():
            bodies.append(text)
    return bodies


def node_check(bodies: List[str]) -> List[str]:
    """`node --check` each script body. Returns a list of failures.

    `node --check` cannot read HTML, which is the whole reason the bodies are
    extracted first. A missing node is itself a failure: an unverified strip is
    not a strip anybody should publish.
    """
    fails: List[str] = []
    for n, body in enumerate(bodies):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(body)
            path = fh.name
        try:
            r = subprocess.run(["node", "--check", path],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                fails.append(f"script body #{n + 1} does not parse:\n"
                             + (r.stderr.strip() or r.stdout.strip()))
        except FileNotFoundError:
            fails.append("node is not on PATH -- the output cannot be verified, "
                         "and an unverified strip must not be published")
            break
        except (OSError, subprocess.SubprocessError) as exc:
            fails.append(f"node --check failed to run: {exc}")
            break
        finally:
            os.unlink(path)
    return fails


def brace_balance(text: str) -> int:
    """Net `{` minus `}` across the whole document. A crude figure, but it is
    the same crude figure before and after, and a stripper that ate into a CSS
    rule or a JS block moves it."""
    return text.count("{") - text.count("}")


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


def verify(src: str, out: str, markers: bool = True) -> List[str]:
    """Everything that must still be true of the output. Returns failures."""
    fails: List[str] = []
    fails.extend(verify_backlinks(src, out, markers))

    # PRESENCE, not count. Every one of these names is also DISCUSSED in the
    # commentary -- `SPINDOWN_RANGE_MS` appears seven times in the source and
    # twice in the code -- so a count that drops is the tool working. What must
    # never happen is one going to zero: that is a gate's anchor deleted.
    for marker in REQUIRED_MARKERS:
        if marker in src and marker not in out:
            fails.append(f"marker {marker!r} is in the source and gone from the output")

    if brace_balance(src) != brace_balance(out):
        fails.append(f"brace balance moved: {brace_balance(src)} -> "
                     f"{brace_balance(out)}; a comment cut into real syntax")

    src_bodies, out_bodies = script_bodies(src), script_bodies(out)
    if len(src_bodies) != len(out_bodies):
        fails.append(f"{len(src_bodies)} inline script(s) in source, "
                     f"{len(out_bodies)} in output")
    fails.extend(node_check(out_bodies))

    # Idempotence: a second pass must find nothing but this tool's own banner and
    # its backlink markers. Anything else means the first pass left a comment it
    # could not recognise, which is worth knowing even though leaving one is the
    # safe direction. The marker exemption is by exact shape, so a real comment
    # cannot slip through it.
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
<!-- an HTML comment, with Charles's apostrophe in it, that must go -->
<style>
/* a CSS comment -- it's got an apostrophe too */
a{background:url(https://wozi.com//double/slash.png);color:#fff}
b:after{content:"/* not a comment */"}
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
)

MUST_GO = (
    "an HTML comment",
    "a CSS comment",
    "strip this trailing note",
    "spanning lines",
    "keep the value, drop this",
    "indented standalone note",
    "second on the same line",
)

# Every marker the fixture must produce, in source order and by exact text. Not a
# count: a count passes while the numbers are all one too high, which is the whole
# failure this is here to catch. L4 is markup and takes the markup syntax; L29
# carries TWO comments and gets ONE marker, because a line number said twice says
# nothing twice.
FIXTURE_BACKLINKS = ("<!--L4-->", "/*L6*/", "/*L14*/", "/*L22*/", "/*L24*/",
                     "/*L28*/", "/*L29*/")


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
    if "\n/*L28*/\n" not in out:
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

    # An unterminated construct must not silently swallow the rest of the file.
    truncated = strip("<script>\nconst a = 1;\n/* never closed\n")
    if "const a = 1;" not in truncated:
        fails.append("an unterminated block comment ate the code before it")

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

    # THE ONE UNRECOVERABLE MISTAKE. Overwriting the source is fine when the source
    # is safely in a commit -- the deploy's checkout is -- and destroys work that
    # exists nowhere else when it is not. So the guard is on the FILE's state, not
    # on which flag was typed: `--out index.html index.html` gets it too.
    if same and not a.in_place:
        print(f"refusing to overwrite {in_path} without --in-place", file=sys.stderr)
        return EXIT_USAGE
    if same:
        rel_in = os.path.relpath(os.path.abspath(in_path), REPO_ROOT)
        clean = matches_commit(rel_in)
        if clean is not True and not a.force:
            why = ("git cannot say whether it is committed"
                   if clean is None else "it differs from HEAD")
            print(f"refusing --in-place on {rel_in}: {why}, and the comments it "
                  f"carries exist nowhere else. Commit first, or pass --force.",
                  file=sys.stderr)
            return EXIT_USAGE

    try:
        src = open(in_path, encoding="utf-8").read()
    except OSError as exc:
        print(f"cannot read {in_path}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    rel = os.path.relpath(os.path.abspath(in_path), REPO_ROOT).replace(os.sep, "/")
    url = a.repo_url or repo_url()
    sha = commit_sha(a.sha)
    at_commit = matches_commit(rel)
    stripped = inject_banner(strip(src, a.markers), url, rel=rel, sha=sha,
                             markers=a.markers, at_commit=at_commit)
    # The unmarked strip exists only to price the markers. It is the same cut, so
    # the difference between the two IS the backlinks and nothing else.
    bare = inject_banner(strip(src, False), url, rel=rel, sha=sha, markers=False,
                         at_commit=at_commit) if a.markers else None

    fails = verify(src, stripped, a.markers)
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
    print(f"  source:           {blob_url(url, rel, sha) or '(no origin remote found)'}")
    if at_commit is False:
        print("  NOTE: the input differs from that commit, so the line numbers "
              "describe something unpushed -- the banner says so too")

    if fails:
        print("VERIFY FAILED:\n  - " + "\n  - ".join(fails), file=sys.stderr)
        return EXIT_VERIFY
    print("  verified: script bodies parse, anchors intact, braces balanced, "
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
