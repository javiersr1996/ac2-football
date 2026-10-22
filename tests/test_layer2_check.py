"""Task 26 (b): ``ac2fb layer2 --check`` on a random world put in place of the guarded reader.

Mutations, each with the test that kills it (script and log in the task's record): a check that
compares only the numbers (``test_the_check_names_the_value_that_differs``), that ignores a
missing or an extra value or a carriage return (``test_the_check_sees_a_missing_or_extra_value``,
``test_the_check_refuses_a_file_it_cannot_trust``), that accepts a file rendered otherwise, or a
command that writes the long Parquet or does not say how much it verified
(``test_the_command_checks_says_how_much_and_writes_nothing``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_amputate import with_ball
from test_reliability_metrics import random_world

from ac2fb import cli
from ac2fb.reliability import report
from ac2fb.reliability.match import MatchData

MATCH = 7


def world(match_id: int) -> MatchData:
    return with_ball(random_world(1)[0], 1)


@pytest.fixture(autouse=True)
def planted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report, "load_match", world)


def written(tmp_path: Path) -> Path:
    return report.write_report(report.layer2_report([MATCH]), tmp_path)


def checked(path: Path) -> report.Check:
    return report.check([MATCH], path.read_bytes())


def rewrite(path: Path, change: object) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc)  # type: ignore[operator]
    path.write_bytes(report.render_report(doc).encode("utf-8"))


def test_the_check_passes_and_counts_every_value(tmp_path: Path) -> None:
    path = written(tmp_path)
    got = checked(path)
    assert got.ok and got.matches == 1
    leaves = report._flat(json.loads(path.read_text(encoding="utf-8")))
    assert got.values == len(leaves) > 100
    assert any(isinstance(v, str) for v in leaves.values())
    assert any(v is None for v in leaves.values())


def test_the_check_names_the_value_that_differs(tmp_path: Path) -> None:
    path = written(tmp_path)
    rewrite(path, lambda d: d["matches"][str(MATCH)]["detection"].__setitem__("ball_rows", 1))
    assert any(
        p.startswith(f"matches.{MATCH}.detection.ball_rows: file 1, code ")
        for p in checked(path).problems
    )
    path = written(tmp_path)
    rewrite(path, lambda d: d.__setitem__("about", "another text"))
    assert any(p.startswith("about: file 'another text'") for p in checked(path).problems)


def test_the_check_sees_a_missing_or_extra_value(tmp_path: Path) -> None:
    path = written(tmp_path)
    rewrite(path, lambda d: d["matches"][str(MATCH)]["detection"].pop("ball_rows"))
    assert f"missing from the file: matches.{MATCH}.detection.ball_rows" in checked(path).problems
    path = written(tmp_path)
    rewrite(path, lambda d: d.__setitem__("extra", 1))
    assert "not produced by the code: extra" in checked(path).problems


def test_the_check_refuses_a_file_it_cannot_trust(tmp_path: Path) -> None:
    assert "does not exist" in report.check([MATCH], None).problems[0]
    path = written(tmp_path)
    good = path.read_bytes()
    path.write_bytes(good.replace(b"\n", b"\r\n"))
    assert checked(path).problems == ("the file has a carriage return",)
    path.write_bytes(good.replace(b"  ", b"   "))  # the same values, another indent
    assert checked(path).problems == ("the file is not rendered as the code renders it",)


def test_the_command_checks_says_how_much_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = written(tmp_path)

    def no_parquet(match_ids: list[int]) -> None:
        raise AssertionError("the check wrote the long Parquet")

    monkeypatch.setattr(cli, "write_long", no_parquet)
    args = ["layer2", "--check", "--match", str(MATCH), "--reports-dir", str(tmp_path)]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert f"verified: {checked(path).values} values, 1 matches" in out and "layer2: OK" in out
    rewrite(path, lambda d: d["matches"][str(MATCH)]["detection"].__setitem__("ball_rows", 1))
    before = path.read_bytes()
    assert cli.main(args) == 1
    out = capsys.readouterr().out
    assert "layer2: FAILED" in out and ".detection.ball_rows: file 1" in out
    assert path.read_bytes() == before
