"""Task 25 on the ten real calibration matches: ``pytest -m realdata``.

The committed ``reports/reliability.csv`` is what the code writes; its figures equal those of
task 12 and of the probes where they overlap (the line's V2 strata with ``layer2.json``, the
block's width and length with ``probe_s3.json``, the units of the line with ``probe_s2.json``,
the extrapolated near rivals with ``layer2.json``); the metrics written for the reading equal
the definitions of ``defence/`` match by match; and the strata of the line's reaction split its
units by the direction of the incoming ball of probe S2.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest
from test_split import CALIBRATION

from ac2fb.defence import block, line, power, pressure, probe_s3
from ac2fb.defence.line import LineReception
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.defence.pressure import Reception
from ac2fb.reliability import metrics, table
from ac2fb.reliability.match import Event, MatchData, load_with_long
from ac2fb.reliability.sensitivity import Metric, Reading, WindowFrames, sensitivity

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def every_row() -> list[dict[str, str]]:
    return list(csv.DictReader((REPORTS / table.REPORT_NAME).read_text("utf-8").splitlines()))


def committed() -> dict[tuple[str, str, str], dict[str, str]]:
    """The rows over all the units of each metric (``ball_stratum`` ``all``)."""
    rows = every_row()
    return {
        (r["match_id"], r["metric"], r["variant"]): r for r in rows if r["ball_stratum"] == "all"
    }


def report(name: str) -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = json.loads((REPORTS / name).read_text(encoding="utf-8"))[
        "matches"
    ]
    return found


def test_the_committed_table_is_what_the_code_writes_for_the_calibration_matches() -> None:
    result = table.check(CALIBRATION, (REPORTS / table.REPORT_NAME).read_bytes())
    assert result.ok, result.problems
    assert result.matches == 10 and result.rows == len(every_row())
    assert result.cells == result.rows * len(table.COLUMNS)
    assert {m for m, _, _ in committed()} == {str(m) for m in CALIBRATION}
    assert b"\r" not in (REPORTS / table.REPORT_NAME).read_bytes()


def test_the_check_sees_a_mutated_value_of_the_real_table(tmp_path: Path) -> None:
    text = (REPORTS / table.REPORT_NAME).read_text(encoding="utf-8")
    first = str(CALIBRATION[0])
    lines = text.splitlines()
    start = f"{first},line_reaction_m,all,V1,"
    i = next(k for k, line in enumerate(lines) if line.startswith(start))
    cells = lines[i].split(",")
    cells[5] = repr(float(cells[5]) + 0.000001)  # the mean of V1, one unit in the last place
    lines[i] = ",".join(cells)
    (tmp_path / table.REPORT_NAME).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    result = table.check([CALIBRATION[0]], (tmp_path / table.REPORT_NAME).read_bytes())
    assert not result.ok and len(result.problems) == 1
    assert f"{first}/line_reaction_m/all/V1 mean: file " in result.problems[0]


def test_every_match_has_every_metric_in_v0_and_v1() -> None:
    rows = committed()
    for m in CALIBRATION:
        for name in metrics.METRICS:
            v0, v1 = rows[str(m), name, "V0"], rows[str(m), name, "V1"]
            assert int(v1["n"]) <= int(v0["n"]) == int(v0["n_units"]) > 0
            assert rows[str(m), name, "V0"]["extrapolated_fraction"] != ""


def test_the_figures_equal_those_of_task_12_and_the_probes_where_they_overlap() -> None:
    rows, layer2 = committed(), report("layer2.json")
    s2, s3 = report("probe_s2.json"), report("probe_s3.json")
    for m in CALIBRATION:
        key = str(m)
        line_counts = layer2[key]["line"]["detected_count"]  # type: ignore[index]
        strata = {
            int(v.split("_")[1]): int(r["n"])
            for (mm, name, v), r in rows.items()
            if mm == key and name == "line_height_m" and v.startswith("V2")
        }
        assert strata == {int(k): n for k, n in line_counts.items() if n}
        assert int(rows[key, "line_height_m", "V0"]["n_units"]) == s2[key]["counts"]["line_at_t"]  # type: ignore[index]
        assert int(rows[key, "block_width_m", "V0"]["n_units"]) == layer2[key]["block"]["phases"]  # type: ignore[index]
        # reception: V1 leaves out the units with an extrapolated rival within 10 m
        rec = layer2[key]["reception"]
        out = round(rec["events_with_rival_within_10"] * rec["with_extrapolated_rival_within_10"])  # type: ignore[index]
        index = rows[key, "pressure_index", "V0"], rows[key, "pressure_index", "V1"]
        assert int(index[0]["n"]) - int(index[1]["n"]) == out
        # block: the S3 fixers of the chosen definition, to the six decimals of both files
        for metric, name in (("width", "block_width_m"), ("length", "block_length_m")):
            fix = s3[key]["chosen"]["fixers"][metric]  # type: ignore[index]
            v0, v1 = rows[key, name, "V0"], rows[key, name, "V1"]
            assert (int(v0["n"]), float(v0["mean"])) == (fix["v0"]["n"], fix["v0"]["mean"])
            assert (int(v1["n"]), float(v1["mean"])) == (fix["v1"]["n"], fix["v1"]["mean"])
            assert float(v0["extrapolated_fraction"]) == fix["extrapolated_fraction"]
            assert int(v0["gap_len_max"]) == fix["gap_len"]["max"]
            assert int(v0["n_skipped"]) == fix["n_skipped"]


def test_the_strata_of_the_reaction_split_its_units() -> None:
    rows = every_row()
    for m in CALIBRATION:
        mine = [r for r in rows if r["match_id"] == str(m) and r["metric"] == "line_reaction_m"]
        v0 = {r["ball_stratum"]: r for r in mine if r["variant"] == "V0"}
        assert list(v0) == ["all", *metrics.DIRECTIONS]
        for column in ("n", "n_units", "n_skipped", "player_frames"):
            parts = sum(int(v0[d][column]) for d in metrics.DIRECTIONS)
            assert parts == int(v0["all"][column]), (m, column)
        assert min(int(v0[d]["n"]) for d in ("backward", "forward", "lateral")) > 0


@pytest.mark.parametrize("match_id", CALIBRATION)
def test_the_direction_is_the_one_of_probe_s2_on_the_real_matches(match_id: int) -> None:
    match, _ = load_with_long(match_id)
    seen: set[str] = set()
    for e in metrics.possessions(match.events):
        sign = match.attack_sign[(e.period, e.team or 0)]
        mine = metrics.incoming_direction(match, e.frame_start, sign)
        assert mine == pressure.incoming_ball(match, e.frame_start, sign, 0.0).split("/")[0]
        seen.add(mine)
    assert seen == set(metrics.DIRECTIONS)


def test_the_probe_s3_definition_is_the_one_the_metrics_use() -> None:
    assert (
        json.loads((REPORTS / "probe_s3.json").read_text(encoding="utf-8"))["chosen_definition"]
        == power.C3_DEFINITION
    )


def line_original(match: MatchData, held: list[Event], kind: str) -> Metric:
    """The line of ``defence/line.py`` as a metric: its height at t, or its reaction since t - W."""
    built, _ = line.build_units(
        match,
        [LineReception(str(i), e.period, e.frame_start, e.team or 0, e.player or 0, None, None)
         for i, e in enumerate(held)],
        [0, W],
    )  # fmt: skip
    by_frame = {u.reception.frame: u for u in built}

    def metric(window: WindowFrames) -> Reading | None:
        u = by_frame.get(window.window.frame_end)
        if u is None or (kind == "reaction" and not math.isfinite(u.depth[W])):
            return None
        return Reading(u.depth[0] - (u.depth[W] if kind == "reaction" else 0.0), u.line)

    return metric


def equal_to_the_original(m: int) -> None:
    definition = next(d for d in block.DEFINITIONS if block.name_of(d) == power.C3_DEFINITION)
    match, long = load_with_long(m)
    units = metrics.metric_units(match)
    held = metrics.possessions(match.events)
    receptions = [
        Reception(str(i), e.period, e.frame_start, e.team or 0, e.player or 0, 1)
        for i, e in enumerate(held)
    ]
    phases = probe_s3.load_inputs(m).phases
    originals = {
        "pressure_index": pressure.make_metric(match, receptions),
        "line_height_m": line_original(match, held, "height"),
        "line_reaction_m": line_original(match, held, "reaction"),
        "block_width_m": probe_s3.make_metric(match, phases, definition, "width"),
        "block_length_m": probe_s3.make_metric(match, phases, definition, "length"),
    }
    for name, original in originals.items():
        metric, windows = units[name]
        assert sensitivity(original, long, windows)[m] == sensitivity(metric, long, windows)[m], (
            name
        )


@pytest.mark.parametrize("match_id", CALIBRATION)
def test_the_metrics_equal_the_definitions_of_defence_on_the_real_matches(match_id: int) -> None:
    equal_to_the_original(match_id)
