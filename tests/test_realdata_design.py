"""Task 19 on the ten real calibration matches: ``pytest -m realdata``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_split import CALIBRATION

from ac2fb import cli
from ac2fb.defence import design, power
from ac2fb.reliability.report import render_report

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def report(name: str) -> Any:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def test_the_committed_design_report_is_what_the_code_writes() -> None:
    fresh = render_report(design.design_report(CALIBRATION))
    committed = (REPORTS / design.REPORT_NAME).read_bytes()
    assert b"\r" not in committed
    assert committed.decode("utf-8") == fresh


def test_the_design_starts_from_task_17s_units_and_drops_the_overlap() -> None:
    got, pw = report(design.REPORT_NAME), report(power.REPORT_NAME)
    c1 = pw["candidates"]["C1"]
    v0 = c1["outcomes"]["ball_advance"]["incoming_ball"]["variants"]["V0"]["matches"]
    for m in map(str, CALIBRATION):
        units = got["units"][m]
        assert units["design"] == v0[m]["n"] == c1["window_overlap"][m]["units"]
        assert units["overlap_design"] == c1["window_overlap"][m]
        assert units["excluded_gap"] == c1["window_overlap"][m]["within_w"]
        assert units["kept"] == units["design"] - units["excluded_gap"]
        assert units["overlap_kept"]["within_w"] == 0
        assert units["kept_pressed"] + units["kept_free"] == units["kept"]
        assert units["kept_v1"] == units["v2_classes"]["0"] <= units["kept"]
        assert sum(units["v2_classes"].values()) == units["kept"]
        assert sum(x["kept"] for x in units["by_level"].values()) == units["kept"]
        assert sum(x["kept"] for x in units["by_stratum"].values()) == units["kept"]
        assert units["proxy"]["pressed"] + units["proxy"]["free"] == units["kept"]
        kept = got["index_cause"]["power"]["variants"]["V0"]["matches"][m]
        assert kept["n"] == units["kept"] and kept["pressed"] == units["kept_pressed"]
        assert got["index_cause"]["power"]["variants"]["V1"]["matches"][m]["n"] == units["kept_v1"]


def test_the_blocking_decision_follows_the_protocol() -> None:
    got = report(design.REPORT_NAME)
    protocol = cli._read_protocol(cli._PROTOCOL)
    simulated = got["index_cause"]["power"]
    rho, limit = simulated["rho_v0_pooled"], protocol["null"]["block_by_possession_if_rho_above"]
    assert simulated["blocked"] is (rho is not None and rho > limit)
    assert simulated["blocked"] is protocol["null"]["blocked"]
    assert (
        got["constants"]["pressed_index"]
        == protocol["cause"]["treatment"]["pressed_if_index_at_least"]
    )
    assert (
        got["constants"]["exclusion_gap_frames"]
        == protocol["units"]["exclusion"]["gap_frames_at_most"]
    )


def test_the_pooled_pretrend_is_the_weighted_mean_of_the_matches() -> None:
    got = report(design.REPORT_NAME)
    for cause in ("index_cause", "proxy_cause"):
        for variant, pre in got[cause]["pretrend"].items():
            weights = got["index_cause"]["power"]["variants"][variant]["matches"]
            if cause == "index_cause":
                # The sd figure is task 17's pooling on the kept units, by its own weights.
                mean = sum(weights[m]["weight"] * pre["matches"][m]["sd"] for m in weights) / sum(
                    x["weight"] for x in weights.values()
                )
                assert pre["sd"] == pytest.approx(mean, abs=2e-6)
                simulated = got["index_cause"]["power"]["variants"][variant]["pretrend"]
                assert pre["sd"] == pytest.approx(simulated["pooled_sd"], abs=2e-6)
                assert pre["d3_abs_effect_must_exceed_sd"] == pytest.approx(
                    simulated["d3_abs_effect_must_exceed_sd"], abs=4e-6
                )
            assert pre["d3_abs_effect_must_exceed_sd"] == pytest.approx(
                2 * abs(pre["sd"]), abs=4e-6
            )
            assert pre["d3_abs_effect_must_exceed_m"] == pytest.approx(
                2 * abs(pre["metres"]), abs=4e-6
            )
