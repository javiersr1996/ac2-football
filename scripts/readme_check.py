"""Gate on the README: length, structure, honest numbers, no placeholders (tasks 31 and 33).

    uv run python scripts/readme_check.py [--root DIR]

Exit 0 when every rule holds, 1 otherwise; it prints the words, figures + tables, numbers checked
and each failure. The rules, on ``README.md`` and its sidecar ``README.src.json``:

* Words <= 1000: whitespace-separated tokens of the raw file, fenced code and HTML comments
  included. The raw file is the counted text, so ``wc -w README.md`` gives the same number.
* Figures (images) plus Markdown tables <= 2, fences and comments excluded.
* The literal sentence that the synthetic fixtures produce no figure is present.
* No ``PENDING(`` left anywhere.
* Every number of the README is either allow-listed (``ALLOWED`` below) or the next entry of
  ``README.src.json``: ``{"numbers": [{"number": "<as written>", "src": "<citation>"}, ...]}``
  in order of appearance (a ``note`` per entry is free text). A README number with no entry,
  an entry with no README number, or the two out of order fails; so does a cited value that
  is not the written number at the README's rounding.

The ``src`` syntax:

* ``path/to/file.json:dotted.key`` or ``pyproject.toml:dotted.key``. A JSON object key may itself
  contain dots (``summary`` in ``reports/layer2.json`` does), so the longest matching key wins.
  ``*`` fans out over a dict or list; it then needs a trailing ``(min)``, ``(max)`` or
  ``(count below zero)``, and the count of items is also accepted ("8 of 10").
* ``a,b``: several keys of the same file; their sum is also accepted (10 + 10 = 20 matches).
* ``a / b``: the ratio of two keys of the same file.
* A list value stands for its length. Durations in a key (``gt_20s``, ``1_5s``) stand for
  their numbers ("more than 20 s").
* Any other file (``docs/*.md``, ``uv.lock``, ``.github/workflows/*.yml``): ``path:phrase``; the
  phrase must be on a line of the file and the cited number must be written on that same line.
* A CI run, ``Full build run <id>``, ``same run`` (after one) or an ``actions/runs/<id>`` URL:
  only the presence of the citation is checked. The numbers it covers (sizes, durations) are NOT
  verified; there is no network here.

Rounding: the value is rounded half up to the decimals written. A number followed by ``%`` is
compared with the value times 100. An unsigned number matches the magnitude; a written ``+`` or
``-`` must match the sign. Units other than ``%`` (m, s, MB) are not checked. Only numerals count,
not number words.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_WORDS = 1000
MAX_FIGURES_AND_TABLES = 2
SIDECAR = "README.src.json"
# The sentence of the README's last section. A decision: the task names it, not its words.
REQUIRED_SENTENCE = (
    "Synthetic fixtures are used only for tests and produce no figure in this README."
)

# Numbers that need no citation. (label, pattern, id group whose text must occur in reports/ or 0)
ALLOWED: list[tuple[str, str, int]] = [
    ("edition name", r"Analytics Cup 2\.0", 0),
    ("year or season", r"\b20\d\d(?:/\d\d)?\b", 0),
    ("figure number", r"\bFigure \d+", 0),
    ("layer number", r"\b[Ll]ayer [123]\b", 0),
    ("match id of the quick run", r"--match (\d+)", 1),
]

COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)
TOKEN = re.compile(r"(?<![\w.])([+-]?)(v?)((?:\d{1,3}(?:,\d{3})+|\d+)(?:[./]\d+)*)(?!\w)")
PENDING = re.compile(r"PENDING\([^)\n]*\)?")
CI = re.compile(
    r"(?:Full build run (?P<run>\d{6,})|(?P<same>same run)\b"
    r"|https://github\.com/\S+/actions/runs/(?P<url>\d+))"
)
MODIFIER = re.compile(r"\s*\((min|max|count below zero)\)\s*$")
DURATION = re.compile(r"^(?:[a-z]+_)?(\d+)(?:_(\d+))?s$")
FENCE = re.compile(r"^\s*(```|~~~)")
SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<img\b")


class SrcError(Exception):
    """A src citation that does not resolve."""


@dataclass
class Candidates:
    numbers: list[Decimal] = field(default_factory=list)
    strings: set[str] = field(default_factory=set)
    ci: bool = False


@dataclass
class Report:
    words: int = 0
    figures: int = 0
    tables: int = 0
    matched: int = 0
    ci_only: int = 0
    allowed: int = 0
    number_failures: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def numbers(self) -> int:
        return self.matched + self.ci_only + self.allowed + self.number_failures


def text_tokens(text: str) -> set[str]:
    return {m.group(3) for m in TOKEN.finditer(text)}


def walk(node: Any, segs: list[str]) -> list[Any]:
    """The values at ``segs``; a ``*`` fans out. Dotted object keys: the longest one wins."""
    if not segs:
        return [node]
    head = segs[0]
    if head == "*":
        children = list(node.values()) if isinstance(node, dict) else node
        if not isinstance(children, list):
            raise SrcError("'*' needs a dict or a list")
        return [leaf for child in children for leaf in walk(child, segs[1:])]
    if isinstance(node, dict):
        for j in range(len(segs), 0, -1):
            key = ".".join(segs[:j])
            if key in node:
                try:
                    return walk(node[key], segs[j:])
                except SrcError:
                    continue
        raise SrcError(f"no key {'.'.join(segs)!r}")
    if isinstance(node, list) and head.isdigit() and int(head) < len(node):
        return walk(node[int(head)], segs[1:])
    raise SrcError(f"no key {'.'.join(segs)!r}")


def number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return Decimal(repr(value))


def key_values(data: Any, expr: str, cand: Candidates) -> Decimal | None:
    """Add the candidates of one key expression (with its modifier); return its main value."""
    modifier = MODIFIER.search(expr)
    key = MODIFIER.sub("", expr).strip()
    segs = key.split(".")
    leaves = walk(data, segs)
    for seg in segs:
        dur = DURATION.match(seg)
        if dur:
            cand.numbers += [Decimal(g) for g in dur.groups() if g]
    if "*" in segs:
        if modifier is None:
            raise SrcError(
                f"{key!r} fans out with '*' and needs (min), (max) or (count below zero)"
            )
        nums = [n for n in map(number, leaves) if n is not None]
        if len(nums) != len(leaves):
            raise SrcError(f"{key!r} has a non-numeric leaf")
        cand.numbers.append(Decimal(len(nums)))
        what = modifier.group(1)
        if what == "count below zero":
            main = Decimal(sum(1 for n in nums if n < 0))
        else:
            main = min(nums) if what == "min" else max(nums)
        cand.numbers.append(main)
        return main
    if modifier is not None:
        raise SrcError(f"{key!r} has a modifier but no '*'")
    value = leaves[0]
    if isinstance(value, str):
        cand.strings |= text_tokens(value)
        return None
    if isinstance(value, list):
        main = Decimal(len(value))
    else:
        found = number(value)
        if found is None:
            raise SrcError(f"{key!r} is not a number, a string or a list")
        main = found
    cand.numbers.append(main)
    return main


def resolve(src: str, root: Path, seen_ci: bool) -> Candidates:
    ci = CI.match(src)
    if ci:
        if ci.group("same") and not seen_ci:
            raise SrcError("'same run' with no earlier CI run cited")
        return Candidates(ci=True)
    path_text, sep, rest = src.partition(":")
    if not sep or not rest.strip():
        raise SrcError(f"cannot read {src!r} as file:key or as a CI run")
    path = (root / path_text.strip()).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise SrcError(f"{path_text.strip()!r} is not a file of the repository")
    rest = rest.strip()
    cand = Candidates()
    suffix = path.suffix.lower()
    if suffix not in (".json", ".toml"):
        lines = [
            ln for ln in path.read_text(encoding="utf-8").splitlines() if rest.lower() in ln.lower()
        ]
        if not lines:
            raise SrcError(f"{path_text.strip()!r} has no line with {rest!r}")
        for ln in lines:
            cand.strings |= text_tokens(ln)
        return cand
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw) if suffix == ".json" else tomllib.loads(raw)
    except ValueError as exc:
        raise SrcError(f"{path_text.strip()!r} does not parse: {exc}") from exc
    if " / " in rest:
        left, _, right = rest.partition(" / ")
        a = key_values(data, left.strip(), cand)
        b = key_values(data, right.strip(), cand)
        if a is None or b is None or b == 0:
            raise SrcError(f"{rest!r}: a ratio needs two numbers, the second not zero")
        cand.numbers.append(a / b)
        return cand
    mains = [key_values(data, part.strip(), cand) for part in rest.split(",")]
    numeric = [m for m in mains if m is not None]
    if len(numeric) > 1:
        cand.numbers.append(sum(numeric, Decimal(0)))
    return cand


@dataclass
class Token:
    raw: str  # as written: sign, optional v, digits
    sign: str
    text: str  # digits as written, without separators, sign or v
    percent: bool
    start: int

    @property
    def decimals(self) -> int:
        return len(self.text.partition(".")[2])

    @property
    def plain(self) -> bool:
        return self.text.count(".") <= 1 and "/" not in self.text


def agrees(tok: Token, cand: Candidates) -> bool:
    if tok.text in cand.strings:
        return True
    if not tok.plain:
        return False
    written = Decimal(tok.text)
    if tok.sign == "-":
        written = -written
    quantum = Decimal(1).scaleb(-tok.decimals)
    for value in cand.numbers:
        shown = value * 100 if tok.percent else value
        if not tok.sign:
            shown = abs(shown)
        try:
            if shown.quantize(quantum, rounding=ROUND_HALF_UP) == written:
                return True
        except InvalidOperation:
            continue
    return False


def reports_text(root: Path) -> str:
    parts = []
    for path in sorted((root / "reports").rglob("*")):
        if path.is_file() and path.suffix in (".json", ".csv", ".txt", ".md"):
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def count_structure(clean: str) -> tuple[int, int]:
    """Images and Markdown tables outside fenced code."""
    figures = tables = 0
    fenced = False
    previous = ""
    for line in clean.splitlines():
        if FENCE.match(line):
            fenced = not fenced
            previous = ""
            continue
        if fenced:
            continue
        figures += len(IMAGE.findall(line))
        if SEPARATOR.match(line) and "|" in line and "|" in previous:
            tables += 1
        previous = line
    return figures, tables


def sidecar_entries(root: Path, report: Report) -> list[tuple[str, str]]:
    """The ``(number, src)`` pairs of README.src.json, in order; a bad file is a failure."""
    path = root / SIDECAR
    if not path.is_file():
        report.failures.append(f"{SIDECAR}: missing")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["numbers"]
    except (ValueError, KeyError, TypeError) as exc:
        report.failures.append(f"{SIDECAR}: not an object with a 'numbers' list ({exc})")
        return []
    pairs: list[tuple[str, str]] = []
    for i, entry in enumerate(entries, 1):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("number"), str)
            or not isinstance(entry.get("src"), str)
        ):
            report.failures.append(f"{SIDECAR}: entry {i} needs string 'number' and 'src'")
            return []
        pairs.append((entry["number"], entry["src"]))
    return pairs


def check(root: Path, readme: str = "README.md") -> Report:
    report = Report()
    text = (root / readme).read_text(encoding="utf-8").replace("\r\n", "\n")

    report.words = len(text.split())
    if report.words > MAX_WORDS:
        report.failures.append(f"words: {report.words} > {MAX_WORDS}")

    report.figures, report.tables = count_structure(COMMENT.sub("", text))
    if report.figures + report.tables > MAX_FIGURES_AND_TABLES:
        report.failures.append(
            f"figures + tables: {report.figures} + {report.tables} > {MAX_FIGURES_AND_TABLES}"
        )

    if REQUIRED_SENTENCE not in " ".join(text.split()):
        report.failures.append(f"missing sentence: {REQUIRED_SENTENCE!r}")

    for m in PENDING.finditer(text):
        report.failures.append(f"pending: {m.group(0)!r} is still in the README")
    marked = PENDING.sub(lambda m: " " * len(m.group(0)), text)

    exempt: list[tuple[int, int]] = []
    corpus: list[str] = []  # reports text, read once and only if a match id is met
    for label, pattern, id_group in ALLOWED:
        for m in re.finditer(pattern, marked):
            exempt.append(m.span())
            if id_group:
                if not corpus:
                    corpus.append(reports_text(root))
                if m.group(id_group) not in corpus[0]:
                    report.failures.append(
                        f"number: {m.group(id_group)!r} ({label}) is in no artifact of reports/"
                    )

    tokens: list[Token] = []
    for m in TOKEN.finditer(marked):
        if any(a <= m.start(3) < b for a, b in exempt):
            report.allowed += 1
            continue
        tokens.append(
            Token(
                m.group(0),
                m.group(1),
                m.group(3).replace(",", ""),
                marked.startswith("%", m.end()),
                m.start(),
            )
        )

    entries = sidecar_entries(root, report)
    pairs: list[tuple[Token, str]] = []
    for i, (tok, (written, src)) in enumerate(zip(tokens, entries, strict=False), 1):
        if tok.raw != written:
            report.failures.append(
                f"number: {context(marked, tok)} is number {i} of the README but entry {i} of "
                f"{SIDECAR} is {written!r} ({src}): missing or out of order"
            )
            report.number_failures += len(tokens) - len(pairs)
            break
        pairs.append((tok, src))
    else:
        if len(tokens) > len(entries):
            for tok in tokens[len(entries) :]:
                report.number_failures += 1
                report.failures.append(f"number: {context(marked, tok)} has no entry in {SIDECAR}")
        for i, (written, src) in enumerate(entries[len(tokens) :], len(tokens) + 1):
            report.failures.append(
                f"src: entry {i} of {SIDECAR}, {written!r} ({src}), has no number in the README"
            )

    seen_ci = False
    for tok, src in pairs:
        try:
            cand = resolve(src, root, seen_ci)
        except SrcError as exc:
            report.failures.append(f"src: {src!r}: {exc}")
            report.number_failures += 1
            continue
        seen_ci = seen_ci or cand.ci
        if cand.ci:
            report.ci_only += 1
        elif agrees(tok, cand):
            report.matched += 1
        else:
            report.number_failures += 1
            report.failures.append(f"number: {context(marked, tok)} does not match {src!r}")
    return report


def context(marked: str, tok: Token) -> str:
    around = marked[max(0, tok.start - 30) : tok.start + len(tok.raw) + 15].replace("\n", " ")
    return f"{tok.raw!r} in '...{around}...'"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    report = check(args.root)
    print(f"words: {report.words} (max {MAX_WORDS})")
    print(
        f"figures + tables: {report.figures} + {report.tables} = "
        f"{report.figures + report.tables} (max {MAX_FIGURES_AND_TABLES})"
    )
    print(
        f"numbers: {report.numbers} checked, {report.matched} equal to their src, "
        f"{report.ci_only} covered by a CI citation only (presence, not value), "
        f"{report.allowed} allow-listed, {report.number_failures} failed"
    )
    for failure in report.failures:
        print(f"FAIL {failure}")
    if report.failures:
        print(f"readme_check: FAILED ({len(report.failures)} failures)")
        return 1
    print("readme_check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
