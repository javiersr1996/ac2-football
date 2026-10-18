"""Probe S2 on the ten real calibration matches: ``pytest -m realdata``."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_split import CALIBRATION

from ac2fb.defence import probe_s2
from ac2fb.reliability.report import render_report

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def test_the_committed_s2_report_is_what_the_code_writes_for_the_calibration_matches() -> None:
    fresh = render_report(probe_s2.s2_report([probe_s2.load_inputs(m) for m in CALIBRATION]))
    committed = (REPORTS / probe_s2.REPORT_NAME).read_bytes()
    assert b"\r" not in committed
    assert committed.decode("utf-8") == fresh
