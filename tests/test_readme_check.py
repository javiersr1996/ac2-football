"""The README gate, run on synthetic README texts in temporary directories.

``scripts/readme_check.py`` reads one README and the artifacts it cites, so each test builds a
small repository (README, a reports file, a pyproject, a note, a CI citation) that passes, then
changes ONE thing: that change must flip the verdict and name what broke. A test that only shows
the good case passes by construction; every rule has its mutation here (the four of the task:
1001 words, a third table, an invented number, the sentence deleted; and one per extra rule).
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


def src(cite: str) -> str:
    return f"<!-- src: {cite} -->"


DET = src("reports/data.json:stats.det.median")
N = src("reports/data.json:stats.n")
LINE = src("reports/data.json:summary.line.detected.median")
TAG = src("pyproject.toml:tool.uv.sources.base.tag")
PY = src("pyproject.toml:project.requires-python")
TOOL = src("docs/note.md:tool version")
BODY = (
    "# Demo\n\n"
    "![Figure 1](figures/f1.png)\n\n"
    f"Rows detected: 56.2{DET}%, over 214{N} items. Line 50.0{LINE}% of the line.\n\n"
    f"Pinned at tag `v0.1.0`{TAG} on Python 3.13{PY} and tool 3.19.1{TOOL}.\n\n"
    f"{SENTENCE}\n"
)


def build(tmp: Path, readme: str = BODY, data: dict[str, object] | None = None) -> Path:
    """A repository in ``tmp`` whose README is ``readme``; the files are written with LF."""
    files = {
        "README.md": readme,
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


def mutate(tmp: Path, old: str, new: str, readme: str = BODY) -> list[str]:
    assert old in readme, f"the mutation targets {old!r}, absent from the baseline"
    build(tmp, readme.replace(old, new, 1))
    return failures(tmp)


def test_baseline_passes(tmp_path: Path) -> None:
    """Anchor of every mutation below: the unmutated repository is clean, and nothing is skipped."""
    report = rc.check(build(tmp_path))
    assert report.failures == []
    # Six cited numbers (3.13, 3.19.1 and 0.1.0 among them) and Figure 1, which is allow-listed.
    assert (report.matched, report.ci_only, report.allowed) == (6, 0, 1)
    assert (report.figures, report.tables) == (1, 0)


# --- the four mutations of the task ---------------------------------------------------------


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


def test_html_comment_words_are_not_counted(tmp_path: Path) -> None:
    """500 words in a comment on top of 1000 visible ones: still 1000 (counted, they would fail)."""
    with_words(tmp_path, 1000)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    build(tmp_path, text + "<!-- " + "hidden " * 500 + "-->\n")
    assert rc.check(tmp_path).words == 1000
    assert failures(tmp_path) == []


def test_code_blocks_count_as_words(tmp_path: Path) -> None:
    """The text of a fenced block is text: 1000 words of which some are code is the limit."""
    with_words(tmp_path, 1000)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    build(tmp_path, text + "```bash\nuv run extra\n```\n")
    assert rc.check(tmp_path).words == 1005
    assert failures(tmp_path) == ["words: 1005 > 1000"]


TABLE = "\n| a | b |\n|---|---|\n| 1 | 2 |\n"  # a table of one row; "1" and "2" are uncited numbers


def test_two_figures_and_tables_pass_a_third_fails(tmp_path: Path) -> None:
    table = TABLE.replace("1", "x").replace("2", "y")
    ok = BODY + table  # one figure + one table
    build(tmp_path, ok)
    report = rc.check(tmp_path)
    assert (report.figures, report.tables, report.failures) == (1, 1, [])
    # The third element, a second table, breaks the limit.
    build(tmp_path, ok + table)
    assert failures(tmp_path) == ["figures + tables: 1 + 2 > 2"]
    # Or a second image on top of the table, or an <img>.
    build(tmp_path, ok + "\n![Figure 2](figures/f2.png)\n")
    assert failures(tmp_path) == ["figures + tables: 2 + 1 > 2"]
    build(tmp_path, ok + '\n<img src="x.png">\n')
    assert failures(tmp_path) == ["figures + tables: 2 + 1 > 2"]


def test_a_table_inside_a_code_fence_or_a_comment_is_not_a_table(tmp_path: Path) -> None:
    table = TABLE.replace("1", "x").replace("2", "y")
    build(tmp_path, BODY + "\n```\n" + table + "```\n\n<!--" + table + "-->\n")
    assert rc.check(tmp_path).tables == 0
    assert failures(tmp_path) == []


def test_invented_number_fails_and_names_it(tmp_path: Path) -> None:
    found = mutate(tmp_path, "over 214<!--", "over 215<!--")
    assert len(found) == 1 and "'215'" in found[0] and "does not match" in found[0]
    # A number with no src at all fails too, in prose and in a code block.
    found = mutate(tmp_path, "of the line.", "of the line, in 42 cases.")
    assert len(found) == 1 and "'42'" in found[0] and "no src" in found[0]
    build(tmp_path, BODY + "\n```bash\nuv run tool --top 42\n```\n")
    assert len(failures(tmp_path)) == 1 and "'42'" in failures(tmp_path)[0]


def test_sentence_deleted_fails(tmp_path: Path) -> None:
    assert mutate(tmp_path, SENTENCE, "") == [f"missing sentence: {SENTENCE!r}"]
    # Changed by one word is a deletion of the literal sentence.
    assert len(mutate(tmp_path, "produce no figure", "produce a figure")) == 1


def test_sentence_may_wrap_across_lines(tmp_path: Path) -> None:
    assert mutate(tmp_path, "only for tests and", "only for tests\nand") == []


# --- one mutation per extra rule --------------------------------------------------------------


def test_number_off_by_one_rounding_step_fails(tmp_path: Path) -> None:
    assert mutate(tmp_path, "56.2<!--", "56.1<!--")[0].startswith("number: '56.1'")
    assert mutate(tmp_path, "56.2<!--", "56.3<!--")[0].startswith("number: '56.3'")
    # More decimals than the value is a different claim: 56.20 is the same as 56.2.
    assert mutate(tmp_path, "56.2<!--", "56.20<!--") == []


def test_rounding_is_half_up_and_percent_is_times_100(tmp_path: Path) -> None:
    src = "<!-- src: reports/data.json:stats.half.v -->"
    # 0.5625 shown as a percent with one decimal is 56.3 (half up); 56.2 would be banker's rounding.
    ok = BODY.replace("\n\n" + SENTENCE, f"\nAlso 56.3{src}%.\n\n{SENTENCE}")
    build(tmp_path, ok)
    assert failures(tmp_path) == []
    build(tmp_path, ok.replace("56.3", "56.2"))
    assert len(failures(tmp_path)) == 1
    # Without the %, 0.5625 is not 56.3.
    build(tmp_path, ok.replace("56.3<!--", "56.3 <!--").replace("%.", "."))
    assert len(failures(tmp_path)) == 1


def test_a_src_key_that_does_not_exist_fails(tmp_path: Path) -> None:
    found = mutate(tmp_path, "stats.det.median", "stats.det.medyan")
    assert any(f.startswith("src:") and "medyan" in f for f in found)
    found = mutate(tmp_path, "reports/data.json:stats.n", "reports/gone.json:stats.n")
    assert any(f.startswith("src:") and "gone.json" in f for f in found)
    found = mutate(tmp_path, "docs/note.md:tool version", "docs/note.md:no such phrase")
    assert any(f.startswith("src:") and "no such phrase" in f for f in found)
    # A file that exists but outside the repository is not a source either.
    outside = tmp_path / "outside.json"
    outside.write_text('{"stats": {"n": 214}}', encoding="utf-8", newline="\n")
    repo = tmp_path / "repo"
    found = mutate(repo, "reports/data.json:stats.n", "../outside.json:stats.n")
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


def test_a_src_after_no_number_fails(tmp_path: Path) -> None:
    found = mutate(tmp_path, "of the line.", "of the line<!-- src: reports/data.json:stats.n -->.")
    assert len(found) == 1 and "sits after no number" in found[0]


def test_an_unsigned_number_is_a_magnitude_a_written_sign_must_match(tmp_path: Path) -> None:
    def line(text: str, src: str) -> list[str]:
        build(
            tmp_path, BODY.replace("\n\n" + SENTENCE, f"\n{text}<!-- src: {src} -->\n\n{SENTENCE}")
        )
        return failures(tmp_path)

    assert line("Effect 0.19", "reports/data.json:effect") == []
    assert line("Effect -0.19", "reports/data.json:effect") == []
    assert line("Effect +0.19", "reports/data.json:effect") != []


def test_wildcards_need_a_modifier_and_give_min_max_count(tmp_path: Path) -> None:
    path = "reports/data.json:matches.*.effect"
    cases = [
        ("From -0.36", f"{path} (min)", True),
        ("To +0.09", f"{path} (max)", True),
        ("To 0.10", f"{path} (max)", False),
        ("Negative in 2 of 3", f"{path} (count below zero)", True),
        ("Negative in 1 of 3", f"{path} (count below zero)", False),
        ("From -0.36", f"{path}", False),
    ]
    for text, src, passes in cases:
        build(
            tmp_path, BODY.replace("\n\n" + SENTENCE, f"\n{text}<!-- src: {src} -->\n\n{SENTENCE}")
        )
        assert (failures(tmp_path) == []) is passes, (text, src, failures(tmp_path))


def test_ratio_list_length_sum_and_duration_in_the_key(tmp_path: Path) -> None:
    def line(text: str, src: str) -> bool:
        build(
            tmp_path, BODY.replace("\n\n" + SENTENCE, f"\n{text}<!-- src: {src} -->\n\n{SENTENCE}")
        )
        return failures(tmp_path) == []

    assert line("About 95", "reports/data.json:pre / effect") is False  # no % sign: 0.945 is not 95
    assert line("About 95%", "reports/data.json:pre / effect") is True
    assert line("About 96%", "reports/data.json:pre / effect") is False
    assert line("5 items", "reports/data.json:ids") is True
    assert line("6 items", "reports/data.json:ids") is False
    assert line("7 items", "reports/data.json:ids,more") is True  # 5 + 2
    assert line("Gaps over 20 s jump 0.217", "reports/data.json:runs.gt_20s.jump") is True
    assert line("Gaps over 30 s jump 0.217", "reports/data.json:runs.gt_20s.jump") is False


def test_a_text_file_citation_needs_the_number_on_the_phrase_line(tmp_path: Path) -> None:
    assert mutate(tmp_path, "and tool 3.19.1<!--", "and tool 7.7<!--")[0].startswith(
        "number: '7.7'"
    )  # 7.7 is in the note, on another line than "tool version"
    assert mutate(tmp_path, "and tool 3.19.1<!--", "and tool 3.19.2<!--")[0].startswith(
        "number: '3.19.2'"
    )


def test_a_toml_version_must_equal_the_pin(tmp_path: Path) -> None:
    assert mutate(tmp_path, "`v0.1.0`<!--", "`v0.1.1`<!--")[0].startswith("number: 'v0.1.1'")
    assert mutate(tmp_path, "Python 3.13<!--", "Python 3.12<!--")[0].startswith("number: '3.12'")


CI = "<!-- src: Full build run 39782141426, step quick -->"


def test_a_ci_citation_only_has_its_presence_checked(tmp_path: Path) -> None:
    """The number under a CI citation is accepted whatever it is: said so in the output."""
    text = BODY.replace(
        "\n\n" + SENTENCE,
        f"\nAbout 9 s{CI} and then 1,919 MB{src('same run')}.\n\n{SENTENCE}",
    )
    build(tmp_path, text)
    report = rc.check(tmp_path)
    assert report.failures == [] and report.ci_only == 2
    # 'same run' with no run before it fails: it cites nothing.
    build(tmp_path, text.replace("Full build run 39782141426, step quick", "same run"))
    assert any("'same run' with no earlier CI run" in f for f in failures(tmp_path))
    # A malformed run id is not a citation.
    build(tmp_path, text.replace("39782141426", "12"))
    assert any(f.startswith("src:") for f in failures(tmp_path))
    # A run URL is one too.
    url = "https://github.com/o/r/actions/runs/39782141426"
    build(tmp_path, text.replace("Full build run 39782141426, step quick", url))
    assert failures(tmp_path) == []


def test_allow_list_is_explicit(tmp_path: Path) -> None:
    ok = BODY.replace(
        "\n\n" + SENTENCE,
        f"\nEntry to the Analytics Cup 2.0 (2024/25 data), Layer 2 and Figure 1.\n\n{SENTENCE}",
    )
    build(tmp_path, ok)
    assert failures(tmp_path) == []
    # Neighbours of the allowed forms are not allowed.
    for bad in ("Analytics Cup 3.0", "2.0 in total", "Layer 4", "Figure 1 and 7", "in 1850"):
        build(tmp_path, ok.replace("Layer 2", bad))
        assert failures(tmp_path) != [], bad


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
    build(tmp_path, BODY.replace(SENTENCE, "").replace("over 214<!--", "over 215<!--"))
    bad = run(tmp_path)
    assert bad.returncode == 1
    assert "FAIL missing sentence" in bad.stdout and "FAIL number: '215'" in bad.stdout
    assert "readme_check: FAILED (2 failures)" in bad.stdout


@pytest.mark.parametrize("name", ["README.md"])
def test_the_script_reads_the_file_it_is_given(tmp_path: Path, name: str) -> None:
    """No README in the root is an error, not a pass."""
    with pytest.raises(FileNotFoundError):
        rc.check(tmp_path, name)
