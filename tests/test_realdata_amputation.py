"""Task 26 on the ten real calibration matches: ``pytest -m realdata``.

The committed ``reports/amputation.csv`` is what the code writes; its units are the V1 units of
``reports/reliability.csv``; its bands split them and nobody hidden is no error; and the hiding of
each match is the detection by distance to the ball of ``reports/layer2.json``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from test_split import CALIBRATION

from ac2fb.reliability import amputate, metrics, table
from ac2fb.reliability.match import load_match

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def rows_of(name: str) -> list[dict[str, str]]:
    return list(csv.DictReader((REPORTS / name).read_text(encoding="utf-8").splitlines()))


def by_key() -> dict[tuple[str, str, str], dict[str, str]]:
    return {(r["match_id"], r["metric"], r["band"]): r for r in rows_of(amputate.REPORT_NAME)}


def test_the_committed_table_is_what_the_code_writes_for_the_calibration_matches() -> None:
    raw = (REPORTS / amputate.REPORT_NAME).read_bytes()
    result = amputate.check(CALIBRATION, raw)
    assert result.ok, result.problems
    expected = len(CALIBRATION) * len(metrics.METRICS) * len(amputate.BAND_NAMES)
    assert result.matches == 10 and result.rows == len(by_key()) == expected
    assert result.cells == result.rows * len(amputate.COLUMNS)
    assert b"\r" not in raw


def test_the_check_sees_a_mutated_value_of_the_real_table(tmp_path: Path) -> None:
    first = str(CALIBRATION[0])
    lines = (REPORTS / amputate.REPORT_NAME).read_text(encoding="utf-8").splitlines()
    i = next(k for k, line in enumerate(lines) if line.startswith(f"{first},line_height_m,all,"))
    cells = lines[i].split(",")
    cells[5] = repr(float(cells[5]) + 0.000001)  # mean_abs_error, one unit in the last place
    lines[i] = ",".join(cells)
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    result = amputate.check([CALIBRATION[0]], raw)
    assert not result.ok and len(result.problems) == 1
    assert f"{first}/line_height_m/all mean_abs_error: file " in result.problems[0]


def test_the_units_are_the_v1_units_of_the_reliability_map() -> None:
    v1 = {
        (r["match_id"], r["metric"]): int(r["n"])
        for r in rows_of(table.REPORT_NAME)
        if r["ball_stratum"] == "all" and r["variant"] == "V1"
    }
    rows = by_key()
    for m in CALIBRATION:
        for name in metrics.METRICS:
            assert int(rows[str(m), name, "all"]["n_units"]) == v1[str(m), name] > 0, (m, name)


def test_the_bands_split_the_units_and_nobody_hidden_is_no_error() -> None:
    rows = by_key()
    for m in CALIBRATION:
        for name in metrics.METRICS:
            whole = rows[str(m), name, "all"]
            parts = sum(int(rows[str(m), name, b]["n"]) for b in amputate.BAND_NAMES[:-1])
            assert parts == int(whole["n"]) == int(whole["n_units"]) - int(whole["n_skipped"])
            none = rows[str(m), name, "none"]
            assert none["max_abs_error"] in ("0.0", "") and int(none["n"]) < int(whole["n"])


@pytest.mark.parametrize("match_id", CALIBRATION)
def test_the_hiding_is_the_detection_by_ball_distance_of_layer2(match_id: int) -> None:
    layer2 = json.loads((REPORTS / "layer2.json").read_text(encoding="utf-8"))
    bins = layer2["matches"][str(match_id)]["ball_distance"]
    hide = amputate.hiding(load_match(match_id))
    assert len(bins) == len(hide.probability)
    for k, figures in enumerate(bins.values()):
        assert abs(hide.probability[k] - (1 - figures["detected"])) < 1e-6, (match_id, k)
    assert min(len(b) for b in hide.back) > 0
