"""The video script gate, run on synthetic scripts in temporary directories.

``scripts/video_script_check.py`` reads one script table and the artifacts its citations name,
so each test builds a small repository (the script, a reports file) that passes, then changes ONE
thing: that change must flip the verdict and name what broke. The three mutations of task 34 (a
changed number, a missing source, 151 words) and one per extra rule; the committed script is
checked as it is at the end.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "video_script_check.py"

_spec = importlib.util.spec_from_file_location("video_script_check", SCRIPT)
assert _spec is not None and _spec.loader is not None
vsc: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["video_script_check"] = vsc
_spec.loader.exec_module(vsc)

DATA = {
    "key": {"seen": 4, "filled": 7},
    "n": 11,
    "line": {"of": [7.19, 13.88, 9.0]},
    "effect": -0.19268,
}
SEEN = "`reports/data.json:key.seen`"
N = "`reports/data.json:n`"
LINE_MIN = "`reports/data.json:line.of.*(min)`"
LINE_MAX = "`reports/data.json:line.of.*(max)`"
EFFECT = "`reports/data.json:effect`"
RUN = "`Full build run 39782141426, step quick`"
# (shot, sentence, sources): 35 spoken words, 5 cited numbers, one CI number, one allow-listed.
ROWS: list[tuple[str, str, str]] = [
    ("Clip, second 3", "The camera saw 4 of these 11 defenders.", f"{SEEN}, {N}"),
    (
        "Figure 1, panel c",
        "In Layer 2 the line sits 7 to 14 metres higher.",
        f"{LINE_MIN}, {LINE_MAX}",
    ),
    ("Figure 2", "The effect was -0.19 sd.", EFFECT),
    ("README on screen", "One match builds in about 9 seconds.", RUN),
    ("Javier on camera", "That is the result.", ""),
]


def words_of(rows: list[tuple[str, str, str]]) -> int:
    return len(" ".join(sentence for _, sentence, _ in rows).split())


def script(rows: list[tuple[str, str, str]], stated: str | None = None) -> str:
    """The Markdown of a script whose stated count is right unless ``stated`` says otherwise."""
    words = words_of(rows)
    seconds = (words * 60 + 75) // 150
    head = stated if stated is not None else f"{words} spoken words, {seconds} s"
    lines = [
        "# Script\n",
        f"**{head} at 150 words per minute.**\n",
        "| # | Time | Shot | Sentence | Sources |",
        "|---|---|---|---|---|",
    ]
    for i, (shot, sentence, sources) in enumerate(rows, 1):
        lines.append(
            f"| {i} | 0:{4 * i:02d} to 0:{4 * i + 4:02d} | {shot} | {sentence} | {sources} |"
        )
    return "\n".join(lines) + "\n"


def build(
    tmp: Path,
    rows: list[tuple[str, str, str]] = ROWS,
    stated: str | None = None,
    text: str | None = None,
    data: dict[str, object] = DATA,
) -> Path:
    """A repository in ``tmp`` whose script is ``rows`` (or the literal ``text``); LF files."""
    files = {
        "docs/video_script.md": script(rows, stated) if text is None else text,
        "reports/data.json": json.dumps(data),
    }
    for name, content in files.items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return tmp


def failures(tmp: Path) -> list[str]:
    return vsc.check(tmp).failures


def with_row(
    tmp: Path, i: int, sentence: str | None = None, sources: str | None = None
) -> list[str]:
    """The baseline with row ``i`` (from 1) changed in its sentence, its sources or both."""
    rows = list(ROWS)
    shot, old_sentence, old_sources = rows[i - 1]
    rows[i - 1] = (
        shot,
        old_sentence if sentence is None else sentence,
        old_sources if sources is None else sources,
    )
    build(tmp, rows)
    return failures(tmp)


def test_baseline_passes(tmp_path: Path) -> None:
    """Anchor of every mutation below: the unmutated repository is clean, and nothing is skipped."""
    report = vsc.check(build(tmp_path))
    assert report.failures == []
    assert (report.rows, report.words, report.seconds) == (5, 35, 14)
    assert (report.matched, report.ci_only, report.allowed, report.number_failures) == (5, 1, 1, 0)


# --- the three mutations of task 34 -------------------------------------------------------------


def test_a_changed_number_fails_and_names_it(tmp_path: Path) -> None:
    found = with_row(tmp_path, 1, sentence="The camera saw 5 of these 11 defenders.")
    assert len(found) == 1 and found[0].startswith("row 1: number '5'")
    assert "does not match" in found[0] and "key.seen" in found[0]
    # Off by one rounding step in a cited range.
    found = with_row(tmp_path, 2, sentence="In Layer 2 the line sits 8 to 14 metres higher.")
    assert len(found) == 1 and "'8'" in found[0] and "(min)" in found[0]


def test_a_number_with_no_source_fails(tmp_path: Path) -> None:
    found = with_row(tmp_path, 1, sources=SEEN)
    assert found == [
        "row 1: 2 number(s) (4, 11) but 1 citation(s) in 'The camera saw 4 of these 11 defenders.'"
    ]
    # No sources at all, and a citation outside backticks is no citation.
    assert len(with_row(tmp_path, 3, sources="")) == 1
    assert len(with_row(tmp_path, 3, sources=EFFECT.strip("`"))) == 1
    # An extra number in a sentence with one citation.
    found = with_row(tmp_path, 3, sentence="The effect was -0.19 sd in 8 matches.")
    assert len(found) == 1 and "2 number(s) (-0.19, 8) but 1 citation(s)" in found[0]


def with_words(tmp: Path, target: int) -> list[str]:
    """The baseline plus filler words in the last sentence, so that ``target`` words are spoken."""
    missing = target - words_of(ROWS)
    assert missing > 0
    rows = [*ROWS[:-1], ("Javier on camera", "That is the result. " + "word " * missing, "")]
    build(tmp, rows)
    report = vsc.check(tmp)
    assert report.words == target
    return report.failures


def test_150_words_pass_and_151_fail(tmp_path: Path) -> None:
    assert with_words(tmp_path / "a", 150) == []
    assert with_words(tmp_path / "b", 151) == ["words: 151 > 150"]


# --- one mutation per extra rule ----------------------------------------------------------------


def test_only_the_sentence_column_is_spoken_or_checked(tmp_path: Path) -> None:
    """Numbers and words in the shot or the time column count for nothing."""
    rows = [("Clip at second 3, 7 of 11, extra words here", *ROWS[0][1:]), *ROWS[1:]]
    build(tmp_path, rows)
    report = vsc.check(tmp_path)
    assert report.failures == [] and report.words == 35 and report.numbers == 7


def test_a_citation_with_no_number_fails(tmp_path: Path) -> None:
    found = with_row(tmp_path, 5, sources=N)
    assert found == ["row 5: 0 number(s) (none) but 1 citation(s) in 'That is the result.'"]


def test_a_written_sign_must_match(tmp_path: Path) -> None:
    assert with_row(tmp_path, 3, sentence="The effect was 0.19 sd.") == []
    found = with_row(tmp_path, 3, sentence="The effect was +0.19 sd.")
    assert len(found) == 1 and "'+0.19'" in found[0] and "does not match" in found[0]


def test_a_src_that_does_not_resolve_fails(tmp_path: Path) -> None:
    found = with_row(tmp_path, 3, sources="`reports/data.json:effekt`")
    assert len(found) == 1 and found[0].startswith("row 3: src 'reports/data.json:effekt'")
    found = with_row(tmp_path, 3, sources="`reports/gone.json:effect`")
    assert len(found) == 1 and "gone.json" in found[0]
    # A CI citation with no run id is not a citation; 'same run' needs a run before it.
    found = with_row(tmp_path, 4, sources="`Full build run 12`")
    assert len(found) == 1 and found[0].startswith("row 4: src")
    rows = [ROWS[3], *ROWS[:3], ROWS[4]]
    rows[0] = (rows[0][0], rows[0][1], "`same run`")
    build(tmp_path, rows)
    assert any("'same run' with no earlier CI run" in f for f in failures(tmp_path))


def test_the_stated_count_and_duration_must_be_true(tmp_path: Path) -> None:
    build(tmp_path, stated="34 spoken words, 14 s")
    found = failures(tmp_path)
    assert found == [
        "stated: '34 spoken words, 14 s at 150 words per minute', "
        "but the table has 35 spoken words, 14 s"
    ]
    build(tmp_path, stated="35 spoken words, 13 s")
    assert len(failures(tmp_path)) == 1
    text = script(ROWS).replace("35 spoken words, 14 s at 150 words per minute", "a minute")
    build(tmp_path, text=text)
    assert failures(tmp_path) == [
        "stated: no line 'N spoken words, S s at 150 words per minute' in the file"
    ]


def test_a_table_without_the_columns_or_a_short_row_fails(tmp_path: Path) -> None:
    text = script(ROWS).replace("| Sentence |", "| Text |")
    build(tmp_path, text=text)
    assert failures(tmp_path) == [
        "docs/video_script.md: no table with the columns Sentence and Sources"
    ]
    text = script(ROWS)
    assert "| Javier on camera | That is the result. |  |" in text
    build(tmp_path, text=text.replace("| Javier on camera | That is the result. |  |", "| |"))
    found = failures(tmp_path)
    assert found[0] == "row 5: 3 cells, the header has 5"


def test_allow_listed_numbers_need_no_citation_and_their_neighbours_do(tmp_path: Path) -> None:
    line = "Layer 1 and Figure 2 of the Analytics Cup 2.0 (2024/25 data), with 7 metrics."
    assert len(with_row(tmp_path, 5, sentence=line)) == 1  # the 7
    assert with_row(tmp_path, 5, sentence=line.replace(", with 7 metrics", "")) == []
    assert len(with_row(tmp_path, 5, sentence="Layer 4.")) == 1
    # A date that starts like a season: the whole number must sit inside the allowed match.
    assert len(with_row(tmp_path, 5, sentence="Read on 2026/10/24.")) == 1
    # The match id form of the README's allow-list is a plain number here.
    assert len(with_row(tmp_path, 5, sentence="Run it with --match 1874553.")) == 1


def test_crlf_script_gives_the_same_verdict(tmp_path: Path) -> None:
    build(tmp_path)
    path = tmp_path / "docs" / "video_script.md"
    path.write_bytes(path.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
    assert failures(tmp_path) == []


# --- the command and the committed script -----------------------------------------------------


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
    assert "rows: 5" in good.stdout and "words: 35 (max 150), 14 s at 150" in good.stdout
    assert "numbers: 7 checked, 5 equal to their src, 1 covered by a CI citation" in good.stdout
    assert good.stdout.rstrip().endswith("video_script_check: OK")
    with_row(tmp_path, 1, sentence="The camera saw 5 of these 11 defenders.")
    bad = run(tmp_path)
    assert bad.returncode == 1
    assert "FAIL row 1: number '5'" in bad.stdout
    assert "video_script_check: FAILED (1 failures)" in bad.stdout


def test_the_committed_script_passes(tmp_path: Path) -> None:
    """The real script, against the real artefacts: at most 150 words and every number true."""
    report = vsc.check(ROOT)
    assert report.failures == []
    assert report.words <= vsc.MAX_WORDS and report.seconds <= 60
    assert report.number_failures == 0 and report.matched > 0
