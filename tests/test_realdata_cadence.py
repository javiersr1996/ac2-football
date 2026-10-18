"""The cadence probe on the ten real calibration matches: ``pytest -m realdata``."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_split import CALIBRATION

from ac2fb.reliability import cadence
from ac2fb.reliability.match import load_match
from ac2fb.reliability.report import render_report

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def test_the_committed_cadence_report_is_what_the_code_writes_for_the_calibration_matches() -> None:
    fresh = render_report(cadence.cadence_report([load_match(m) for m in CALIBRATION]))
    committed = (REPORTS / cadence.REPORT_NAME).read_bytes()
    assert b"\r" not in committed
    assert committed.decode("utf-8") == fresh
