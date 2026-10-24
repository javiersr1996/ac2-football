"""Gate on the video script: spoken words and every number against the key it cites (task 34).

    uv run python scripts/video_script_check.py [--root DIR]

Exit 0 when every rule holds, 1 otherwise; it prints the rows, the spoken words and their
duration, the numbers checked and each failure. The rules, on ``docs/video_script.md``:

* One Markdown table with a ``Sentence`` and a ``Sources`` column; the other columns (time, shot)
  are free text. The Sentence cells are the spoken text; nothing else is counted or checked.
* Spoken words <= 150: whitespace-separated tokens of the Sentence cells. At 150 words per minute
  that is the minute the rules allow. The duration is printed, and the file must carry the line
  ``N spoken words, S s at 150 words per minute`` with those two values (S rounded half up), so
  the stated duration cannot drift from the text.
* Every number of a Sentence cell is either allow-listed (the patterns of ``readme_check.ALLOWED``
  that need no artefact: "Layer 3", "Figure 1", a season) or paired with the next backticked
  citation of its row's Sources cell, in order, in the ``src`` syntax of ``README.src.json``;
  ``scripts/readme_check.py`` resolves the citation and compares the value at the written
  rounding, a written sign must match, a CI run is checked for presence only. A row with more
  numbers than citations, or more citations than numbers, fails and names them.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
rc: Any = importlib.import_module("readme_check")

SCRIPT = Path("docs") / "video_script.md"
MAX_WORDS = 150
WORDS_PER_MINUTE = 150
COLUMNS = ("Sentence", "Sources")
CITATION = re.compile(r"`([^`]+)`")
STATED = re.compile(r"(\d+) spoken words, (\d+) s at 150 words per minute")
# The allow-list patterns that need no artefact; the match id one reads reports/ and is not spoken.
ALLOWED = [pattern for _, pattern, id_group in rc.ALLOWED if not id_group]


@dataclass
class Report:
    rows: int = 0
    words: int = 0
    matched: int = 0
    ci_only: int = 0
    allowed: int = 0
    number_failures: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def numbers(self) -> int:
        return self.matched + self.ci_only + self.allowed + self.number_failures

    @property
    def seconds(self) -> int:
        """The spoken words at ``WORDS_PER_MINUTE``, in whole seconds, half up."""
        return (self.words * 60 + WORDS_PER_MINUTE // 2) // WORDS_PER_MINUTE


def table(text: str) -> tuple[list[str], list[list[str]]]:
    """The header and the rows (as cells) of the first Markdown table; empty without one."""
    header: list[str] = []
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if header:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not header:
            header = cells
        elif not rc.SEPARATOR.match(line):
            rows.append(cells)
    return header, rows


def numbers_of(sentence: str, report: Report) -> list[Any]:
    """The tokens of ``sentence`` that need a citation; the allow-listed ones are counted."""
    exempt = [m.span() for pattern in ALLOWED for m in re.finditer(pattern, sentence)]
    tokens = []
    for m in rc.TOKEN.finditer(sentence):
        if any(a <= m.start(3) < b for a, b in exempt):
            report.allowed += 1
            continue
        tokens.append(
            rc.Token(
                m.group(0),
                m.group(1),
                m.group(3).replace(",", ""),
                sentence.startswith("%", m.end()),
                m.start(),
            )
        )
    return tokens


def check(root: Path, script: Path = SCRIPT) -> Report:
    report = Report()
    text = (root / script).read_text(encoding="utf-8").replace("\r\n", "\n")
    header, rows = table(text)
    if any(column not in header for column in COLUMNS):
        report.failures.append(
            f"{script.as_posix()}: no table with the columns {' and '.join(COLUMNS)}"
        )
        return report
    report.rows = len(rows)
    at = {column: header.index(column) for column in COLUMNS}
    shaped = [row for row in rows if len(row) == len(header)]
    for i, row in enumerate(rows, 1):
        if len(row) != len(header):
            report.failures.append(f"row {i}: {len(row)} cells, the header has {len(header)}")

    report.words = len(" ".join(row[at["Sentence"]] for row in shaped).split())
    if report.words > MAX_WORDS:
        report.failures.append(f"words: {report.words} > {MAX_WORDS}")
    stated = STATED.search(text)
    if stated is None:
        report.failures.append(
            "stated: no line 'N spoken words, S s at 150 words per minute' in the file"
        )
    elif (int(stated.group(1)), int(stated.group(2))) != (report.words, report.seconds):
        report.failures.append(
            f"stated: {stated.group(0)!r}, but the table has {report.words} spoken words, "
            f"{report.seconds} s"
        )

    seen_ci = False
    for i, row in enumerate(rows, 1):
        if len(row) != len(header):
            continue
        sentence, sources = row[at["Sentence"]], row[at["Sources"]]
        tokens = numbers_of(sentence, report)
        citations = CITATION.findall(sources)
        if len(tokens) != len(citations):
            report.number_failures += len(tokens)
            names = ", ".join(t.raw for t in tokens) or "none"
            report.failures.append(
                f"row {i}: {len(tokens)} number(s) ({names}) but {len(citations)} citation(s) "
                f"in {sentence!r}"
            )
            continue
        for tok, src in zip(tokens, citations, strict=True):
            try:
                cand = rc.resolve(src, root, seen_ci)
            except rc.SrcError as exc:
                report.number_failures += 1
                report.failures.append(f"row {i}: src {src!r}: {exc}")
                continue
            seen_ci = seen_ci or cand.ci
            if cand.ci:
                report.ci_only += 1
            elif rc.agrees(tok, cand):
                report.matched += 1
            else:
                report.number_failures += 1
                report.failures.append(
                    f"row {i}: number {rc.context(sentence, tok)} does not match {src!r}"
                )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    report = check(args.root)
    print(f"rows: {report.rows}")
    print(
        f"words: {report.words} (max {MAX_WORDS}), {report.seconds} s at {WORDS_PER_MINUTE} "
        "words per minute"
    )
    print(
        f"numbers: {report.numbers} checked, {report.matched} equal to their src, "
        f"{report.ci_only} covered by a CI citation only (presence, not value), "
        f"{report.allowed} allow-listed, {report.number_failures} failed"
    )
    for failure in report.failures:
        print(f"FAIL {failure}")
    if report.failures:
        print(f"video_script_check: FAILED ({len(report.failures)} failures)")
        return 1
    print("video_script_check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
