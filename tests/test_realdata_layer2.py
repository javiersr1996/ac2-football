"""Layer 2 on the ten real calibration matches: deselected by default (``pytest -m realdata``).

Reads only through the guarded door, so only calibration matches are touched.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from test_split import CALIBRATION

from ac2fb.protocol import data
from ac2fb.reliability import runs
from ac2fb.reliability.long import long_table
from ac2fb.reliability.match import load_match
from ac2fb.reliability.report import REPORT_NAME, layer2_report, render_report

pytestmark = pytest.mark.realdata

REPORTS = Path(__file__).resolve().parent.parent / "reports"
FIRST = CALIBRATION[0]


def test_gap_len_is_zero_exactly_where_detected_on_a_real_match() -> None:
    frames = data.read_frames(
        [FIRST],
        columns=[
            "match_id", "native_match_id", "period", "frame_native", "entity_id",
            "entity_kind", "team_id", "x_m", "y_m", "is_detected",
        ],
    )  # fmt: skip
    table = long_table(frames)
    gap = np.asarray(table["gap_len"].fill_null(-1).to_numpy())
    seen = np.asarray(table["is_detected"].to_numpy(zero_copy_only=False))
    assert table.num_rows == frames.num_rows > 900_000
    assert (gap[seen] == 0).all() and (gap[~seen] != 0).all()
    assert (gap[~seen] > 0).mean() > 0.99  # a few entities have no detection in a period


def test_the_first_match_reproduces_the_plan_probe_m11_to_the_third_decimal() -> None:
    summary = runs.run_summary(runs.extrapolated_runs(load_match(FIRST), bridge_holes=True))
    bands = summary["by_band"]
    assert bands["gt_20s"]["n_with_jump"] == 400  # type: ignore[index]
    assert round(bands["gt_20s"]["jump_median"], 3) == 0.212  # type: ignore[index]
    assert round(bands["gt_20s"]["jump_p90"], 3) == 0.459  # type: ignore[index]
    assert round(bands["le_1s"]["jump_median"], 3) == 0.216  # type: ignore[index]


def test_the_committed_report_is_what_the_code_writes_for_the_calibration_matches() -> None:
    fresh = render_report(layer2_report(list(CALIBRATION)))
    assert (REPORTS / REPORT_NAME).read_bytes().decode("utf-8") == fresh


def test_the_goalkeeper_proxy_is_the_rostered_goalkeeper_in_every_period_and_team() -> None:
    from ac2fb.reliability.visibility import goalkeepers

    for match_id in CALIBRATION:  # the rosters of calibration matches only, through the door
        roster = data.read_bronze_players([match_id], columns=["id", "player_role_name"])
        rostered = {r["id"] for r in roster.to_pylist() if "goal" in r["player_role_name"].lower()}
        assert rostered, match_id
        proxy = goalkeepers(load_match(match_id))
        assert len(proxy) == 4 and set(proxy.values()) <= rostered, (match_id, proxy)
