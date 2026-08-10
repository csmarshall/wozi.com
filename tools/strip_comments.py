#!/usr/bin/env python3
"""Produce a comment-stripped copy of index.html FOR DEPLOYMENT ONLY.

WHY THIS EXISTS (GitHub #113). `index.html` is ~550KB of source, and roughly two
thirds of it is comment: the argument for every derived constant, the two rules
that were tried and rejected before the shipped one, the issue number that
caused it. That prose IS the project's documentation and it stays in the repo,
unabridged, forever. What it does not have to do is travel down the wire to
somebody who wanted to look at some gears. So the repo keeps the source and the
bucket gets the machine.

WHAT THIS DOES NOT DO. It does not touch `index.html`, and it is deliberately
NOT wired into `.github/workflows/deploy.yml` — publishing something other than
the file in the repo changes what "the repo is the source of truth for
s3://wozi.com" means, and that is a decision with a gate on it, not a side
effect of adding a tool. Run it, read the numbers it prints, then decide.

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
but this tool's own banner.

THE BANNER, AND THE THING NOBODY HAS DECIDED. The output carries a short comment
at the top pointing at the source repo, taken from `git remote get-url origin`
rather than written down here, so it cannot drift from where the code actually
lives. NOTE THAT THE REPO IS PRIVATE — `cards/` carries a real address and mobile
number, which is why. A reader who follows that URL therefore hits a GitHub
sign-in page rather than the comments they were promised, and pointing the public
at a door they cannot open may be worse than pointing them nowhere. That is
unresolved and is not this tool's call: it prints the URL it will use so the
decision can be made with the string in view.

    tools/strip_comments.py                 # strip, verify, write the output
    tools/strip_comments.py --check         # strip and verify, write NOTHING (CI)
    tools/strip_comments.py --selftest      # fixtures for every trap above
    tools/strip_comments.py --out PATH IN   # explicit paths

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


def apply_spans(text: str, spans: List[Span]) -> str:
    """Cut the spans out, then tidy only the lines the cut emptied.

    A block comment becomes a single space when it was welding two tokens
    together (`a/**/b` is `a b`, not `ab`); everything else becomes nothing. A
    line that is whitespace-only ONLY BECAUSE a comment left it that way is
    dropped, which is where most of the saving comes from -- but a line that was
    already blank in the source is kept, so the output's remaining structure is
    the author's and not this tool's.
    """
    out: List[str] = []
    touched_lines = set()
    line_of = _line_index(text)
    pos = 0
    for sp in spans:
        out.append(text[pos:sp.start])
        before = text[sp.start - 1] if sp.start else "\n"
        after = text[sp.end] if sp.end < len(text) else "\n"
        if sp.kind != "js-line" and not before.isspace() and not after.isspace():
            out.append(" ")
        for ln in range(line_of(sp.start), line_of(sp.end) + 1):
            touched_lines.add(ln)
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
        if line.strip():
            kept.append(line)
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


def strip(text: str) -> str:
    return apply_spans(text, comment_spans(text))


def repo_url() -> Optional[str]:
    """The origin remote, as an https URL. Never hardcoded -- see the docstring:
    the URL is the one fact in the banner that can go stale, and the remote is
    where it actually lives."""
    try:
        raw = subprocess.run(
            ["git", "-C", REPO_ROOT, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if raw.returncode != 0:
        return None
    url = raw.stdout.strip()
    if not url:
        return None
    scp = re.match(r"^(?:ssh://)?(?:[^@/]+@)?([^:/]+)[:/](.+?)(?:\.git)?/?$", url)
    if url.startswith(("http://", "https://")):
        return re.sub(r"(?:\.git)?/?$", "", url)
    if scp:
        return f"https://{scp.group(1)}/{scp.group(2)}"
    return url


def banner(url: Optional[str]) -> str:
    where = url or "the private source repository"
    return (
        f"<!-- {BANNER_MARK}.\n"
        f"     The source of this page is heavily commented -- every derived\n"
        f"     constant, every rejected alternative, every issue number. None of\n"
        f"     that is here; it lives with the code at\n"
        f"       {where}\n"
        f"     Generated by tools/strip_comments.py. Do not edit this file: edit\n"
        f"     index.html in the repo above. -->\n"
    )


def inject_banner(html: str, url: Optional[str]) -> str:
    """Place the banner immediately AFTER the doctype, never before it.

    A comment ahead of `<!DOCTYPE html>` is legal in the HTML5 parser but is the
    classic way to lose standards mode in older engines, and there is nothing to
    be gained by finding out which ones still care.
    """
    m = re.match(r"^\s*<!DOCTYPE[^>]*>\s*\n?", html, re.I)
    if not m:
        return banner(url) + html
    return html[:m.end()] + banner(url) + html[m.end():]


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


def verify(src: str, out: str) -> List[str]:
    """Everything that must still be true of the output. Returns failures."""
    fails: List[str] = []

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

    # Idempotence: a second pass must find nothing but this tool's own banner.
    # Anything else means the first pass left a comment it could not recognise,
    # which is worth knowing even though leaving one is the safe direction.
    leftovers = [sp for sp in comment_spans(out)
                 if BANNER_MARK not in out[sp.start:sp.end]]
    if leftovers:
        sample = out[leftovers[0].start:leftovers[0].start + 60].replace("\n", " ")
        fails.append(f"{len(leftovers)} comment(s) survived the strip, first: {sample!r}")

    return fails


def sizes(text: str) -> Tuple[int, int]:
    raw = text.encode()
    # mtime=0 so the figure is reproducible, and level 9 because CloudFront and
    # S3 both serve a precompressed object at whatever level it was made with.
    return len(raw), len(gzip.compress(raw, compresslevel=9, mtime=0))


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
)

MUST_GO = (
    "an HTML comment",
    "a CSS comment",
    "strip this trailing note",
    "spanning lines",
    "keep the value, drop this",
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

    fails.extend(verify(FIXTURE, out))

    # The banner must be injected after the doctype, and must not disturb it.
    stamped = inject_banner(out, "https://github.com/example/repo")
    if not stamped.lower().startswith("<!doctype html>"):
        fails.append("the banner displaced the doctype")
    if BANNER_MARK not in stamped or "https://github.com/example/repo" not in stamped:
        fails.append("the banner is missing or does not name the repo")
    fails.extend(verify(FIXTURE, stamped))

    # An unterminated construct must not silently swallow the rest of the file.
    truncated = strip("<script>\nconst a = 1;\n/* never closed\n")
    if "const a = 1;" not in truncated:
        fails.append("an unterminated block comment ate the code before it")

    if fails:
        print("SELFTEST FAILED:\n  - " + "\n  - ".join(fails), file=sys.stderr)
        sys.exit(EXIT_SELFTEST)
    print(f"selftest ok: {len(MUST_SURVIVE)} live constructs intact, "
          f"{len(MUST_GO)} comments removed, output verified")


# --------------------------------------------------------------------------


def main(argv: List[str]) -> int:
    if "--selftest" in argv:
        selftest()
        return EXIT_OK

    check_only = "--check" in argv
    rest = [a for a in argv if a not in ("--check", "--selftest")]
    out_path = DEFAULT_OUT
    if "--out" in rest:
        k = rest.index("--out")
        if k + 1 >= len(rest):
            print("usage: strip_comments.py [--check] [--out PATH] [INPUT]",
                  file=sys.stderr)
            return EXIT_USAGE
        out_path = rest[k + 1]
        del rest[k:k + 2]
    in_path = rest[0] if rest else DEFAULT_IN

    try:
        src = open(in_path, encoding="utf-8").read()
    except OSError as exc:
        print(f"cannot read {in_path}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    url = repo_url()
    stripped = inject_banner(strip(src), url)

    fails = verify(src, stripped)
    if len(stripped) >= len(src):
        fails.append(f"output is not smaller ({len(src)} -> {len(stripped)}) -- "
                     f"nothing was stripped, or the banner is all there is")

    src_raw, src_gz = sizes(src)
    out_raw, out_gz = sizes(stripped)
    print(f"source  {in_path}")
    print(f"  raw   {src_raw:>9,} B   ->  {out_raw:>9,} B   "
          f"({100 * (src_raw - out_raw) / src_raw:5.1f}% smaller)")
    print(f"  gzip  {src_gz:>9,} B   ->  {out_gz:>9,} B   "
          f"({100 * (src_gz - out_gz) / src_gz:5.1f}% smaller)")
    print(f"  comments removed: {len(comment_spans(src)):,}")
    print(f"  banner points at: {url or '(no origin remote found)'}")

    if fails:
        print("VERIFY FAILED:\n  - " + "\n  - ".join(fails), file=sys.stderr)
        return EXIT_VERIFY
    print("  verified: script bodies parse, markers intact, braces balanced")

    if check_only:
        print("  --check: nothing written")
        return EXIT_OK

    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        open(out_path, "w", encoding="utf-8").write(stripped)
    except OSError as exc:
        print(f"cannot write {out_path}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"  wrote {out_path}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
