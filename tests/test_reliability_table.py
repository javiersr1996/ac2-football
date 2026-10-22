"""Task 25: ``reports/reliability.csv`` and its ``--check``, on the planted world.

The match is the hand-made one of ``test_reliability_metrics`` (a carrier, a goalkeeper and six
rivals, two possessions and one phase), put in place of the guarded reader, so every cell has an
expected value written in the test and the check has something to compare. Mutations, each with
the test that kills it: a check that compares fewer columns than the file has
(``test_the_check_sees_a_mutated_cell_in_every_column``), that stops at the first row, ignores
a missing or an extra row or a carriage return
(``test_the_check_sees_a_missing_extra_or_repeated_row``,
``test_the_check_refuses_a_file_it_cannot_trust``), or that does not say how much it verified
(``test_the_command_writes_and_checks_and_says_how_much_it_verified``); a writer that leaves a
CR or a NaN in the file (``test_the_file_has_lf_and_no_nan``).
"""

from __future__ import annotations

import csv
import dataclasses
import io
from pathlib import Path

import pytest
from test_reliability_metrics import INDEX, long_of, planted_match

from ac2fb import cli
from ac2fb.reliability import metrics, table
from ac2fb.reliability.match import Event, MatchData

MATCH = 7


def world() -> MatchData:
    """The planted match with rival 15 undetected in one frame, and a phase at frame 100."""
    match = planted_match(not_detected=[(15, 195)])
    phase = Event("phases_of_play", None, 100, 100, 1, 1, None)
    return dataclasses.replace(match, events=(*match.events, phase))


@pytest.fixture(autouse=True)
def planted(monkeypatch: pytest.MonkeyPatch) -> None:
    match = world()
    monkeypatch.setattr(table, "load_with_long", lambda match_id: (match, long_of(match)))


def written(tmp_path: Path) -> list[list[str]]:
    path = table.write_table([MATCH], tmp_path)
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))


def checked(directory: Path) -> table.Check:
    """The check of the file in ``directory``, as the command line hands it over."""
    return table.check([MATCH], (directory / table.REPORT_NAME).read_bytes())


def test_the_table_has_the_planted_rows_in_order(tmp_path: Path) -> None:
    rows = written(tmp_path)
    assert tuple(rows[0]) == table.COLUMNS
    by = {(r[1], r[2]): dict(zip(table.COLUMNS, r, strict=True)) for r in rows[1:]}
    assert list(dict.fromkeys(r[1] for r in rows[1:])) == list(metrics.METRICS)
    index = by["pressure_index", "V0"]
    assert (index["match_id"], index["n"], index["n_units"]) == (str(MATCH), "2", "2")
    assert index["mean"] == repr(round(INDEX, 6))
    assert by["nearest_rival_m", "V0"]["mean"] == "3.0"
    assert by["line_height_m", "V0"]["mean"] == "20.25"
    assert by["line_reaction_m", "V0"]["mean"] == "1.5"
    reaction = by["line_reaction_m", "V1"]
    assert reaction["n"] == "1" and reaction["extrapolated_fraction"] == repr(round(1 / 112, 6))
    assert (reaction["gap_len_n"], reaction["gap_len_median"], reaction["gap_len_max"]) == (
        "1",
        "1.0",
        "1",
    )
    assert [
        (r[2], r[3]) for r in rows[1:] if r[1] == "line_reaction_m" and r[2].startswith("V2")
    ] == [
        ("V2_3", "1"),
        ("V2_4", "1"),
    ]
    # the block has one phase: one unit per block metric, nothing extrapolated
    assert by["block_area_m2", "V0"]["n"] == "1" and by["block_area_m2", "V0"]["gap_len_n"] == "0"
    assert by["block_area_m2", "V0"]["gap_len_median"] == ""  # no value is an empty cell


def test_a_value_that_is_not_a_number_is_an_empty_cell() -> None:
    assert [table._cell(v) for v in (float("nan"), float("inf"), None, 0.0, 3, 0.1234567)] == [
        "",
        "",
        "",
        "0.0",
        "3",
        "0.123457",
    ]


def test_the_file_has_lf_and_no_nan(tmp_path: Path) -> None:
    raw = table.write_table([MATCH], tmp_path).read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n") and b"nan" not in raw.lower()


def test_the_check_passes_and_counts_what_it_compared(tmp_path: Path) -> None:
    rows = written(tmp_path)
    report = checked(tmp_path)
    assert report.ok and report.matches == 1
    assert report.rows == len(rows) - 1 and report.cells == (len(rows) - 1) * len(table.COLUMNS)


def edit(path: Path, change: object) -> None:
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))
    change(rows)  # type: ignore[operator]
    path.write_bytes(table.render(rows[1:]).encode("utf-8"))


@pytest.mark.parametrize("column", table.COLUMNS)
@pytest.mark.parametrize("row", [0, -1])
def test_the_check_sees_a_mutated_cell_in_every_column(
    tmp_path: Path, column: str, row: int
) -> None:
    written(tmp_path)
    j = table.COLUMNS.index(column)

    def mutate(rows: list[list[str]]) -> None:
        rows[1:][row][j] = rows[1:][row][j] + "9"

    edit(tmp_path / table.REPORT_NAME, mutate)
    report = checked(tmp_path)
    assert not report.ok
    words = " {column}: file " if j >= 3 else "the code: " if j == 2 else ""
    assert any(words.format(column=column) in p for p in report.problems), report.problems


def test_the_check_sees_a_missing_extra_or_repeated_row(tmp_path: Path) -> None:
    written(tmp_path)
    path = tmp_path / table.REPORT_NAME
    edit(path, lambda rows: rows.pop(3))
    assert any("missing from the file" in p for p in checked(tmp_path).problems)
    written(tmp_path)
    edit(path, lambda rows: rows.append([*rows[1][:2], "V9", *rows[1][3:]]))
    assert any("not produced by the code" in p for p in checked(tmp_path).problems)
    written(tmp_path)
    edit(path, lambda rows: rows.append(list(rows[1])))
    assert any("repeats" in p for p in checked(tmp_path).problems)


def test_the_check_refuses_a_file_it_cannot_trust(tmp_path: Path) -> None:
    assert "does not exist" in table.check([MATCH], None).problems[0]
    written(tmp_path)
    path = tmp_path / table.REPORT_NAME
    good = path.read_bytes()
    path.write_bytes(good.replace(b"\n", b"\r\n"))
    assert any("carriage return" in p for p in checked(tmp_path).problems)
    path.write_bytes(good.replace(b"match_id", b"match", 1))
    assert not checked(tmp_path).ok


def test_rows_of_other_matches_are_not_checked_nor_counted(tmp_path: Path) -> None:
    written(tmp_path)
    path = tmp_path / table.REPORT_NAME
    edit(path, lambda rows: rows.append(["99", "pressure_index", "V0", *["x"] * 11]))
    report = checked(tmp_path)
    assert report.ok and report.matches == 1


def test_the_command_writes_and_checks_and_says_how_much_it_verified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["reliability", "--match", str(MATCH), "--reports-dir", str(tmp_path)]) == 0
    assert "wrote" in capsys.readouterr().out
    rows = len((tmp_path / table.REPORT_NAME).read_text(encoding="utf-8").splitlines()) - 1
    args = ["reliability", "--check", "--match", str(MATCH), "--reports-dir", str(tmp_path)]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert f"verified: {rows} rows, {rows * len(table.COLUMNS)} cells, 1 matches" in out
    assert "reliability: OK" in out

    edit(tmp_path / table.REPORT_NAME, lambda rows: rows[1].__setitem__(4, "123.0"))
    assert cli.main(args) == 1
    out = capsys.readouterr().out
    assert "reliability: FAILED" in out and " mean: file " in out
    assert (tmp_path / table.REPORT_NAME).read_bytes().count(b"123.0") == 1  # --check wrote nothing


def test_the_reading_runs_the_table() -> None:
    assert cli.LAYER2_READS["reliability"] is table.write_table
