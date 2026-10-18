"""Probe S1 on the ten real calibration matches: ``pytest -m realdata``."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_split import CALIBRATION

from ac2fb.defence import probe_s1
from ac2fb.reliability.report import render_report

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def test_the_committed_s1_report_is_what_the_code_writes_for_the_calibration_matches() -> None:
    fresh = render_report(probe_s1.s1_report([probe_s1.load_inputs(m) for m in CALIBRATION]))
    committed = (REPORTS / probe_s1.REPORT_NAME).read_bytes()
    assert b"\r" not in committed
    assert committed.decode("utf-8") == fresh


def test_every_real_match_loads_with_unique_frames_and_labels_that_match_their_ids() -> None:
    # receptions_from raises on a label that disagrees with its id and on a repeated frame.
    for match_id in CALIBRATION:
        inputs = probe_s1.load_inputs(match_id)
        assert 0 < len(inputs.receptions) <= inputs.possessions
