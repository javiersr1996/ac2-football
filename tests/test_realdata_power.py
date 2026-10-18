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
