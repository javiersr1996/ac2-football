"""The README gate, run on synthetic README texts in temporary directories.

``scripts/readme_check.py`` reads one README, its sidecar ``README.src.json`` and the artifacts
the sidecar cites, so each test builds a small repository (README, sidecar, a reports file, a
pyproject, a note, a CI citation) that passes, then changes ONE thing: that change must flip the
verdict and name what broke. A test that only shows the good case passes by construction; every
rule has its mutation here (the four of task 31: 1001 words, a third table, an invented number,
the sentence deleted; the three of task 33: a number with no entry, an entry with no number, the
two out of order; and one per extra rule).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "readme_check.py"

_spec = importlib.util.spec_from_file_location("readme_check", SCRIPT)
assert _spec is not None and _spec.loader is not None
rc: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["readme_check"] = rc
_spec.loader.exec_module(rc)

SENTENCE = "Synthetic fixtures are used only for tests and produce no figure in this README."
DATA = {
    "stats": {"det": {"median": 0.562}, "n": 214, "p": 0.0005, "half": {"v": 0.5625}},
    "summary": {"line.detected": {"median": 0.5}},  # an object key that holds a dot
    "runs": {"gt_20s": {"jump": 0.217}},
    "matches": {"a": {"effect": -0.36}, "b": {"effect": 0.09}, "c": {"effect": -0.1}},
    "effect": -0.19268,
    "pre": 0.182152,
    "ids": [1, 2, 3, 4, 5],
    "more": [6, 7],
}
PYPROJECT = '[project]\nrequires-python = ">=3.13"\n[tool.uv.sources.base]\ntag = "v0.1.0"\n'
NOTE = "# Note\n\n**tool version:** 3.19.1 (checked on the day)\nother line 7.7\n"

DET = "reports/data.json:stats.det.median"
N = "reports/data.json:stats.n"
LINE = "reports/data.json:summary.line.detected.median"
TAG = "pyproject.toml:tool.uv.sources.base.tag"
PY = "pyproject.toml:project.requires-python"
TOOL = "docs/note.md:tool version"
BODY = (
    "# Demo\n\n"
    "![Figure 1](figures/f1.png)\n\n"
    "Rows detected: 56.2%, over 214 items. Line 50.0% of the line.\n\n"
    "Pinned at tag `v0.1.0` on Python 3.13 and tool 3.19.1.\n\n"
    f"{SENTENCE}\n"
)
ENTRIES: list[tuple[str, str]] = [
    ("56.2", DET),
    ("214", N),
    ("50.0", LINE),
    ("v0.1.0", TAG),
    ("3.13", PY),
    ("3.19.1", TOOL),
]


def sidecar(entries: list[tuple[str, str]]) -> str:
    return json.dumps({"numbers": [{"number": n, "src": s} for n, s in entries]})


def build(
    tmp: Path,
    readme: str = BODY,
    entries: list[tuple[str, str]] | None = None,
    data: dict[str, object] | None = None,
) -> Path:
    """A repository in ``tmp`` whose README is ``readme``; the files are written with LF."""
    files = {
        "README.md": readme,
        "README.src.json": sidecar(ENTRIES if entries is None else entries),
        "reports/data.json": json.dumps(DATA if data is None else data),
        "pyproject.toml": PYPROJECT,
        "docs/note.md": NOTE,
    }
    for name, content in files.items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return tmp


def failures(tmp: Path) -> list[str]:
    return rc.check(tmp).failures


def mutate(tmp: Path, old: str, new: str, both: bool = True) -> list[str]:
    """``old`` becomes ``new`` in the README and, with ``both``, in the sidecar entry too."""
    assert old in BODY, f"the mutation targets {old!r}, absent from the baseline"
    entries = ENTRIES
    before = [m.group(0) for m in rc.TOKEN.finditer(old)]
    after = [m.group(0) for m in rc.TOKEN.finditer(new)]
    if both and len(before) == 1 and len(after) == 1:
        entries = [(after[0] if n == before[0] else n, s) for n, s in ENTRIES]
    build(tmp, BODY.replace(old, new, 1), entries)
    return failures(tmp)


def added(tmp: Path, line: str, *pairs: tuple[str, str]) -> list[str]:
    """The baseline plus ``line`` before the required sentence and ``pairs`` at the end."""
    build(tmp, BODY.replace("\n\n" + SENTENCE, f"\n{line}\n\n{SENTENCE}"), ENTRIES + list(pairs))
    return failures(tmp)


def test_baseline_passes(tmp_path: Path) -> None:
    """Anchor of every mutation below: the unmutated repository is clean, and nothing is skipped."""
    report = rc.check(build(tmp_path))
    assert report.failures == []
    # Six cited numbers (3.13, 3.19.1 and 0.1.0 among them) and Figure 1, which is allow-listed.
    assert (report.matched, report.ci_only, report.allowed) == (6, 0, 1)
    assert (report.figures, report.tables) == (1, 0)


# --- the four mutations of task 31 ------------------------------------------------------------


def with_words(tmp: Path, target: int) -> list[str]:
    """The baseline plus filler words, so that the README has exactly ``target`` words."""
    build(tmp)
    missing = target - rc.check(tmp).words
    assert missing > 0
    build(tmp, BODY + "word " * missing + "\n")
    report = rc.check(tmp)
    assert report.words == target
    return report.failures


def test_1000_words_pass_and_1001_fail(tmp_path: Path) -> None:
    assert with_words(tmp_path / "a", 1000) == []
    found = with_words(tmp_path / "b", 1001)
    assert found == ["words: 1001 > 1000"]


def test_the_raw_file_is_the_counted_text_comments_included(tmp_path: Path) -> None:
    """A comment of five words on top of 1000 visible ones is 1005: what ``wc -w`` would say."""
    with_words(tmp_path, 1000)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    build(tmp_path, text + "<!-- one two three -->\n")  # the markers are tokens too
    report = rc.check(tmp_path)
    assert report.words == 1005 == len((tmp_path / "README.md").read_text("utf-8").split())
    assert report.failures == ["words: 1005 > 1000"]


def test_code_blocks_count_as_words(tmp_path: Path) -> None:
    """The text of a fenced block is text: 1000 words of which some are code is the limit."""
    with_words(tmp_path, 1000)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    build(tmp_path, text + "```bash\nuv run extra\n```\n")
    assert rc.check(tmp_path).words == 1005
    assert failures(tmp_path) == ["words: 1005 > 1000"]


TABLE = "\n| a | b |\n|---|---|\n| x | y |\n"  # a table of one row, with no number in it


def test_two_figures_and_tables_pass_a_third_fails(tmp_path: Path) -> None:
    ok = BODY + TABLE  # one figure + one table
    build(tmp_path, ok)
    report = rc.check(tmp_path)
    assert (report.figures, report.tables, report.failures) == (1, 1, [])
    # The third element, a second table, breaks the limit.
    build(tmp_path, ok + TABLE)
    assert failures(tmp_path) == ["figures + tables: 1 + 2 > 2"]
    # Or a second image on top of the table, or an <img>.
    build(tmp_path, ok + "\n![Figure 2](figures/f2.png)\n")
    assert failures(tmp_path) == ["figures + tables: 2 + 1 > 2"]
    build(tmp_path, ok + '\n<img src="x.png">\n')
    assert failures(tmp_path) == ["figures + tables: 2 + 1 > 2"]


def test_a_table_inside_a_code_fence_or_a_comment_is_not_a_table(tmp_path: Path) -> None:
    build(tmp_path, BODY + "\n```\n" + TABLE + "```\n\n<!--" + TABLE + "-->\n")
    assert rc.check(tmp_path).tables == 0
    assert failures(tmp_path) == []


def test_invented_number_fails_and_names_it(tmp_path: Path) -> None:
    found = mutate(tmp_path, "over 214", "over 215")
    assert len(found) == 1 and "'215'" in found[0] and "does not match" in found[0]
    # A number with no entry at all fails too: in prose (it lands between two entries, so the
    # pairing breaks there) and in a code block at the end (the entries run out).
    found = mutate(tmp_path, "of the line.", "of the line, in 42 cases.")
    assert len(found) == 1 and "'42'" in found[0] and "missing or out of order" in found[0]
    build(tmp_path, BODY + "\n```bash\nuv run tool --top 42\n```\n")
    found = failures(tmp_path)
    assert len(found) == 1 and "'42'" in found[0] and "has no entry" in found[0]


def test_sentence_deleted_fails(tmp_path: Path) -> None:
    assert mutate(tmp_path, SENTENCE, "") == [f"missing sentence: {SENTENCE!r}"]
    # Changed by one word is a deletion of the literal sentence.
    assert len(mutate(tmp_path, "produce no figure", "produce a figure")) == 1


def test_sentence_may_wrap_across_lines(tmp_path: Path) -> None:
    assert mutate(tmp_path, "only for tests and", "only for tests\nand") == []


# --- the three mutations of task 33: README and sidecar out of step ---------------------------


def test_a_readme_number_the_sidecar_does_not_list_fails(tmp_path: Path) -> None:
    """Changed in the README only: the sidecar still says 214, so the pairing breaks there."""
    found = mutate(tmp_path, "over 214", "over 215", both=False)
    assert len(found) == 1 and "'215'" in found[0] and "'214'" in found[0]
    assert "missing or out of order" in found[0]
    # One number more at the end: the entries run out.
    build(tmp_path, BODY + "\n3 more.\n")
    found = failures(tmp_path)
    assert len(found) == 1 and "'3'" in found[0] and "has no entry in README.src.json" in found[0]


def test_a_sidecar_entry_with_no_readme_number_fails(tmp_path: Path) -> None:
    build(tmp_path, BODY, ENTRIES + [("7", N)])
    found = failures(tmp_path)
    assert len(found) == 1 and found[0].startswith("src: entry 7 of README.src.json, '7'")
    assert "has no number in the README" in found[0]


def test_entries_out_of_order_fail_and_name_both_sides(tmp_path: Path) -> None:
    swapped = [ENTRIES[1], ENTRIES[0], *ENTRIES[2:]]
    build(tmp_path, BODY, swapped)
    found = failures(tmp_path)
    assert len(found) == 1 and "'56.2'" in found[0] and "'214'" in found[0]
    assert "is number 1 of the README but entry 1" in found[0]
    report = rc.check(tmp_path)
    assert report.number_failures == 6  # nothing after the break is counted as verified
    assert report.matched == 0


def test_a_missing_or_malformed_sidecar_fails(tmp_path: Path) -> None:
    build(tmp_path)
    (tmp_path / "README.src.json").unlink()
    found = failures(tmp_path)
    assert found[0] == "README.src.json: missing" and any("has no entry" in f for f in found)
    (tmp_path / "README.src.json").write_text("[]", encoding="utf-8")
    assert failures(tmp_path)[0].startswith("README.src.json: not an object with a 'numbers' list")
    (tmp_path / "README.src.json").write_text('{"numbers": [{"number": 56.2}]}', encoding="utf-8")
    assert failures(tmp_path)[0] == "README.src.json: entry 1 needs string 'number' and 'src'"


# --- one mutation per extra rule --------------------------------------------------------------


def test_number_off_by_one_rounding_step_fails(tmp_path: Path) -> None:
    assert mutate(tmp_path, "56.2", "56.1")[0].startswith("number: '56.1'")
    assert mutate(tmp_path, "56.2", "56.3")[0].startswith("number: '56.3'")
    # More decimals than the value is a different claim: 56.20 is the same as 56.2.
    assert mutate(tmp_path, "56.2", "56.20") == []


def test_rounding_is_half_up_and_percent_is_times_100(tmp_path: Path) -> None:
    half = "reports/data.json:stats.half.v"
    # 0.5625 shown as a percent with one decimal is 56.3 (half up); 56.2 would be banker's rounding.
    assert added(tmp_path, "Also 56.3%.", ("56.3", half)) == []
    assert len(added(tmp_path, "Also 56.2%.", ("56.2", half))) == 1
    # Without the %, 0.5625 is not 56.3.
    assert len(added(tmp_path, "Also 56.3.", ("56.3", half))) == 1


def test_a_src_key_that_does_not_exist_fails(tmp_path: Path) -> None:
    def with_src(root: Path, old: str, new: str) -> list[str]:
        build(root, BODY, [(n, s.replace(old, new)) for n, s in ENTRIES])
        return failures(root)

    found = with_src(tmp_path, "stats.det.median", "stats.det.medyan")
    assert any(f.startswith("src:") and "medyan" in f for f in found)
    found = with_src(tmp_path, "reports/data.json:stats.n", "reports/gone.json:stats.n")
    assert any(f.startswith("src:") and "gone.json" in f for f in found)
    found = with_src(tmp_path, "docs/note.md:tool version", "docs/note.md:no such phrase")
    assert any(f.startswith("src:") and "no such phrase" in f for f in found)
    # A file that exists but outside the repository is not a source either.
    outside = tmp_path / "outside.json"
    outside.write_text('{"stats": {"n": 214}}', encoding="utf-8", newline="\n")
    found = with_src(tmp_path / "repo", "reports/data.json:stats.n", "../outside.json:stats.n")
    assert any(f.startswith("src:") and "not a file of the repository" in f for f in found)


def test_a_horizontal_rule_is_not_a_table(tmp_path: Path) -> None:
    build(tmp_path, BODY + "\nA line | with a bar\n---\n\nText\n\n---\n")
    assert rc.check(tmp_path).tables == 0
    assert failures(tmp_path) == []


def test_pending_left_fails_even_in_a_comment(tmp_path: Path) -> None:
    found = mutate(tmp_path, "of the line.", "of the line, held-out PENDING(task 9).")
    assert found == ["pending: 'PENDING(task 9)' is still in the README"]
    found = mutate(tmp_path, "of the line.", "of the line. <!-- PENDING(task 9) -->")
    assert found == ["pending: 'PENDING(task 9)' is still in the README"]


def test_numbers_inside_pending_are_not_double_reported(tmp_path: Path) -> None:
    found = mutate(tmp_path, "of the line.", "of the line, PENDING(task 27).")
    assert len(found) == 1


def test_an_unsigned_number_is_a_magnitude_a_written_sign_must_match(tmp_path: Path) -> None:
    effect = "reports/data.json:effect"
    assert added(tmp_path, "Effect 0.19.", ("0.19", effect)) == []
    assert added(tmp_path, "Effect -0.19.", ("-0.19", effect)) == []
    assert added(tmp_path, "Effect +0.19.", ("+0.19", effect)) != []


def test_wildcards_need_a_modifier_and_give_min_max_count(tmp_path: Path) -> None:
    path = "reports/data.json:matches.*.effect"
    cases = [
        ("From -0.36.", "-0.36", f"{path} (min)", True),
        ("To +0.09.", "+0.09", f"{path} (max)", True),
        ("To 0.10.", "0.10", f"{path} (max)", False),
        ("Negative in 2 of 3.", "2", f"{path} (count below zero)", True),
        ("Negative in 1 of 3.", "1", f"{path} (count below zero)", False),
        ("From -0.36.", "-0.36", f"{path}", False),
    ]
    for text, number, src, passes in cases:
        pairs = [(number, src)]
        if " of 3" in text:
            pairs.append(("3", f"{path} (count below zero)"))  # 3 is the count of items
        found = added(tmp_path, text, *pairs)
        assert (found == []) is passes, (text, src, found)


def test_ratio_list_length_sum_and_duration_in_the_key(tmp_path: Path) -> None:
    ratio = "reports/data.json:pre / effect"
    assert added(tmp_path, "About 95.", ("95", ratio)) != []  # no % sign: 0.945 is not 95
    assert added(tmp_path, "About 95%.", ("95", ratio)) == []
    assert added(tmp_path, "About 96%.", ("96", ratio)) != []
    assert added(tmp_path, "5 items.", ("5", "reports/data.json:ids")) == []
    assert added(tmp_path, "6 items.", ("6", "reports/data.json:ids")) != []
    assert added(tmp_path, "7 items.", ("7", "reports/data.json:ids,more")) == []  # 5 + 2
    jump = "reports/data.json:runs.gt_20s.jump"
    assert added(tmp_path, "Gaps over 20 s jump 0.217.", ("20", jump), ("0.217", jump)) == []
    assert added(tmp_path, "Gaps over 30 s jump 0.217.", ("30", jump), ("0.217", jump)) != []


def test_a_text_file_citation_needs_the_number_on_the_phrase_line(tmp_path: Path) -> None:
    # 7.7 is in the note, on another line than "tool version"
    assert mutate(tmp_path, "tool 3.19.1", "tool 7.7")[0].startswith("number: '7.7'")
    assert mutate(tmp_path, "tool 3.19.1", "tool 3.19.2")[0].startswith("number: '3.19.2'")


def test_a_toml_version_must_equal_the_pin(tmp_path: Path) -> None:
    assert mutate(tmp_path, "`v0.1.0`", "`v0.1.1`")[0].startswith("number: 'v0.1.1'")
    assert mutate(tmp_path, "Python 3.13", "Python 3.12")[0].startswith("number: '3.12'")


RUN = "Full build run 39782141426, step quick"


def test_a_ci_citation_only_has_its_presence_checked(tmp_path: Path) -> None:
    """The number under a CI citation is accepted whatever it is: said so in the output."""
    line = "About 9 s and then 1,919 MB."
    assert added(tmp_path, line, ("9", RUN), ("1,919", "same run")) == []
    assert rc.check(tmp_path).ci_only == 2
    # 'same run' with no run before it fails: it cites nothing.
    found = added(tmp_path, line, ("9", "same run"), ("1,919", "same run"))
    assert any("'same run' with no earlier CI run" in f for f in found)
    # A malformed run id is not a citation.
    found = added(tmp_path, line, ("9", RUN.replace("39782141426", "12")), ("1,919", "same run"))
    assert any(f.startswith("src:") for f in found)
    # A run URL is one too.
    url = "https://github.com/o/r/actions/runs/39782141426"
    assert added(tmp_path, line, ("9", url), ("1,919", "same run")) == []


def test_allow_list_is_explicit(tmp_path: Path) -> None:
    line = "Analytics Cup 2.0 (2024/25 data, October 2026), Layer 1, layer 2, Figure 1."
    assert added(tmp_path, line) == []
    # Neighbours of the allowed forms are not allowed: a bare year is any integer 2000 to 2099.
    bads = ("Analytics Cup 3.0", "2.0 in total", "Layer 4", "Figure 1 and 7", "in 1850", "in 2026")
    # "2026/10/24" starts like a season: the whole number must sit inside the allowed match.
    for bad in (*bads, "2026 runs", "2024/2025", "2026/10/24"):
        assert added(tmp_path, line.replace("layer 2", bad)) != [], bad


def test_match_id_in_a_command_must_be_in_reports(tmp_path: Path) -> None:
    code = "\n```bash\nuv run tool --match 1874553\n```\n"
    build(tmp_path, BODY + code, data={**DATA, "ids_seen": [1874553]})
    assert failures(tmp_path) == []
    build(tmp_path, BODY + code)  # reports/ has no such id: an invented match
    found = failures(tmp_path)
    assert len(found) == 1 and "'1874553'" in found[0]


def test_crlf_readme_gives_the_same_verdict(tmp_path: Path) -> None:
    build(tmp_path)
    (tmp_path / "README.md").write_bytes(BODY.replace("\n", "\r\n").encode("utf-8"))
    assert failures(tmp_path) == []


# --- the command --------------------------------------------------------------------------------


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_command_exit_codes_and_output(tmp_path: Path) -> None:
    build(tmp_path)
    good = run(tmp_path)
    assert good.returncode == 0, good.stdout + good.stderr
    assert "words: " in good.stdout and "figures + tables: 1 + 0 = 1" in good.stdout
    assert "numbers: 7 checked" in good.stdout and good.stdout.rstrip().endswith("readme_check: OK")
    entries = [("215" if n == "214" else n, s) for n, s in ENTRIES]
    build(tmp_path, BODY.replace(SENTENCE, "").replace("over 214", "over 215"), entries)
    bad = run(tmp_path)
    assert bad.returncode == 1
    assert "FAIL missing sentence" in bad.stdout and "FAIL number: '215'" in bad.stdout
    assert "readme_check: FAILED (2 failures)" in bad.stdout


@pytest.mark.parametrize("name", ["README.md"])
def test_the_script_reads_the_file_it_is_given(tmp_path: Path, name: str) -> None:
    """No README in the root is an error, not a pass."""
    with pytest.raises(FileNotFoundError):
        rc.check(tmp_path, name)
