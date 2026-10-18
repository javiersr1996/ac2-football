"""Task 17 on the ten real calibration matches: ``pytest -m realdata``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_split import CALIBRATION

from ac2fb.defence import power
from ac2fb.reliability.report import render_report

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def report(name: str) -> Any:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def test_the_committed_power_report_is_what_the_code_writes() -> None:
    fresh = render_report(power.power_report(CALIBRATION, REPORTS))
    committed = (REPORTS / power.REPORT_NAME).read_bytes()
    assert b"\r" not in committed
    assert committed.decode("utf-8") == fresh


def test_the_units_are_the_probes_units() -> None:
    # C1 is probe S1's population and V1; C3 probe S3's measured phases and fixers' V1.
    got, s1, s3 = report(power.REPORT_NAME), report("probe_s1.json"), report("probe_s3.json")
    assert got["probes"] == {
        "C1": s1["verdict"]["c1_survives_probe"],
        "C2": report("probe_s2.json")["verdict"]["c2_survives_probe"],
        "C3": s3["verdict"]["c3_survives_probe"],
    }
    assert s3["chosen_definition"] == power.C3_DEFINITION
    for m in map(str, CALIBRATION):
        c1 = got["candidates"]["C1"]["probe_counts"][m]
        assert c1["scored"] == s1["matches"][m]["receptions"]["scored"]
        assert c1["stratum_undefined"] == s1["matches"][m]["incoming_ball"]["undefined"]
        assert c1["v1_scored"] == s1["matches"][m]["sensitivity"]["v1"]["n"]
        v0 = got["candidates"]["C1"]["outcomes"]["ball_advance"]["incoming_ball"]["variants"]
        assert v0["V0"]["matches"][m]["n"] == c1["scored"] - c1["stratum_undefined"]
        c3 = got["candidates"]["C3"]["probe_counts"][m]
        fixers = s3["matches"][m]["chosen"]["fixers"]
        assert c3["measured"] == fixers["width"]["v0"]["n"] == fixers["length"]["v0"]["n"]
        assert c3["v1_width"] == fixers["width"]["v1"]["n"]
        assert c3["v1_length"] == fixers["length"]["v1"]["n"]
        # Every phase of probe S3 is counted once by type and third.
        types = got["candidates"]["C3"]["phase_types_by_third"]["matches"][m]
        assert sum(sum(t.values()) for t in types.values()) == s3["matches"][m]["counts"]["phases"]
        # The window overlap is over C1's V0 units.
        overlap = got["candidates"]["C1"]["window_overlap"][m]
        assert overlap["units"] == v0["V0"]["matches"][m]["n"]


def test_the_pooled_pretrend_is_the_weighted_mean_of_the_matches() -> None:
    # Review 18: the figure D3 judges, recomputed from the per-match figures and the bar's
    # weights, and probe S2's count of matches over its bar.
    c1 = report(power.REPORT_NAME)["candidates"]["C1"]["outcomes"]["ball_advance"]
    for variant in c1["incoming_ball"]["variants"].values():
        matches, pre = variant["matches"].values(), variant["pretrend"]
        mean = sum(x["weight"] * x["pretrend_sd"] for x in matches) / sum(
            x["weight"] for x in matches
        )
        assert pre["pooled_sd"] == pytest.approx(mean, abs=2e-6)
        assert pre["d3_abs_effect_must_exceed_sd"] == pytest.approx(2 * abs(mean), abs=4e-6)
        over = sum(abs(x["pretrend_sd"]) > 0.15 for x in matches)
        assert pre["s2_bar"]["matches_over"] == over


def test_the_contiguous_contrasts_keep_to_their_third_and_block_the_null() -> None:
    c3 = report(power.REPORT_NAME)["candidates"]["C3"]
    types = c3["phase_types_by_third"]["matches"]
    # Low and high never share enough of a third: that contrast has no cell within strata.
    for outcome in ("width", "length"):
        for variant in c3["outcomes"][outcome]["incoming_ball"]["variants"].values():
            assert all(x["cells_used"] == 0 for x in variant["matches"].values())
    for name, (deeper, higher, third) in power.C3_CONTIGUOUS.items():
        design = c3["contiguous"][name]
        assert (design["contrast"], design["third"]) == ([deeper, higher], third)
        for outcome in ("width", "length"):
            result = design["outcomes"][outcome]
            assert result["blocked"] is True
            for m, x in result["variants"]["V0"]["matches"].items():
                assert x["pressed"] <= types[m][deeper][third]
                assert x["free"] <= types[m][higher][third]
