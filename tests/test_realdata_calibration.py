"""Task 21 on the ten real calibration matches: ``pytest -m realdata``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_split import CALIBRATION

from ac2fb import cli
from ac2fb.defence import bar, calibration, design, effect, power, probe_s1
from ac2fb.reliability.report import render_report

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def report(name: str) -> Any:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def test_the_committed_calibration_report_is_what_the_code_writes() -> None:
    fresh = render_report(calibration.calibration_report(CALIBRATION))
    committed = (REPORTS / calibration.REPORT_NAME).read_bytes()
    assert b"\r" not in committed
    assert committed.decode("utf-8") == fresh


def test_the_design_is_the_design_report() -> None:
    got, des = report(calibration.REPORT_NAME), report(design.REPORT_NAME)
    for m in map(str, CALIBRATION):
        for key in ("design", "excluded_gap", "kept", "kept_pressed", "kept_v1"):
            assert got["design"]["units"][m][key] == des["units"][m][key]
    simulated = des["index_cause"]["power"]
    assert got["design"]["mde80_sd"] == {
        v: simulated["variants"][v]["mde80_sd"] for v in effect.VARIANTS
    }
    assert got["design"]["null"] == {
        "rho_v0_pooled": simulated["rho_v0_pooled"],
        "blocked": simulated["blocked"],
    }
    protocol = cli._read_protocol(cli._PROTOCOL)
    assert got["design"]["null"]["blocked"] is protocol["null"]["blocked"]
    assert all(
        v["null"]["blocked"] is protocol["null"]["blocked"] for v in got["variants"].values()
    )


def test_d1_is_probe_s1s_verdict() -> None:
    got, s1 = report(calibration.REPORT_NAME), report(probe_s1.REPORT_NAME)
    for m in map(str, CALIBRATION):
        assert got["design"]["d1_contrast"][m] == s1["matches"][m]["contrast"]
    assert got["criteria"]["D1"]["kills"] is not s1["verdict"]["c1_survives_probe"]
    assert (
        got["criteria"]["D1"]["values"]["matches_increasing"]
        == (s1["verdict"]["matches_increasing"])
    )


def test_every_kept_unit_is_counted() -> None:
    got = report(calibration.REPORT_NAME)
    v0 = got["variants"]["V0"]
    for m in map(str, CALIBRATION):
        outcomes, match = got["outcomes"][m], v0["matches"][m]
        assert (
            outcomes["pressed"]["kept"] + outcomes["free"]["kept"]
            == (got["design"]["units"][m]["kept"])
            == match["units"]
        )
        for group in ("pressed", "free"):
            assert match["left_out"]["no_outcome"][group] == outcomes[group]["undefined"]
        left = sum(sum(g.values()) for g in match["left_out"].values())
        assert match["used"] + left == match["units"]


def weighted(values: list[float], weights: list[float]) -> float:
    return sum(v * w for v, w in zip(values, weights, strict=True)) / sum(weights)


@pytest.mark.parametrize("variant", effect.VARIANTS)
def test_the_pooled_figures_are_the_cells(variant: str) -> None:
    got = report(calibration.REPORT_NAME)["variants"][variant]
    cells = got["cells"]
    assert got["t"] == pytest.approx(
        weighted([c["z"] for c in cells], [c["w"] for c in cells]), abs=2e-6
    )
    with_pre = [c for c in cells if c["pretrend"] is not None]
    assert got["pretrend_sd"] == pytest.approx(
        weighted([c["pretrend"] for c in with_pre], [c["w"] for c in with_pre]), abs=2e-6
    )
    for m in map(str, CALIBRATION):
        mine = [c for c in cells if str(c["match"]) == m]
        assert got["matches"][m]["cells"] == len(mine)
        if mine:
            assert got["matches"][m]["effect"] == pytest.approx(
                weighted([c["z"] for c in mine], [c["w"] for c in mine]), abs=2e-6
            )
    factor = got["variance_factor"]
    assert factor["cells"] == len(cells)
    assert 1.0 <= factor["median"] <= factor["max"] and factor["weighted_mean"] >= 1.0


def test_the_verdict_follows_from_the_figures() -> None:
    got = report(calibration.REPORT_NAME)
    v0, v1, crit = got["variants"]["V0"], got["variants"]["V1"], got["criteria"]
    for v in (v0, v1):
        agreeing = sum(
            m["effect"] is not None and (m["effect"] > 0) == (v["t"] > 0)
            for m in v["matches"].values()
        )
        assert v["agreeing"] == v["bar"]["agreeing"] == agreeing
        assert v["bar"]["passed"] is (agreeing >= bar.BAR_SAME_SIGN and v["null"]["p"] <= bar.BAR_P)
        assert v["null"]["p"] == pytest.approx((1 + v["null"]["extreme"]) / 2001, abs=1e-6)
    assert crit["D2"]["kills"] is (got["design"]["mde80_sd"]["V0"] > power.MDE_LIMIT)
    assert crit["D3"]["kills"] is (abs(v0["pretrend_sd"]) >= power.D3_RATIO * abs(v0["t"]))
    assert crit["D4"]["kills"] is (
        (v1["t"] > 0) != (v0["t"] > 0) or abs(v1["t"]) < effect.D4_RATIO * abs(v0["t"])
    )
    killing = [c for c in ("D1", "D2", "D3", "D4") if crit[c]["kills"]]
    assert crit["D5"]["killing"] == killing
    assert crit["D5"]["kills"] is (not v0["bar"]["passed"] or bool(killing))
    assert got["verdict"]["calibration_passes"] is not crit["D5"]["kills"]
