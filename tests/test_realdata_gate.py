"""On the real matches: the door serves the ten calibration matches and refuses the ten held-out.

Deselected by default (``pytest -m realdata``): it needs the twenty matches built under
``$FTBASE_DATA_ROOT`` or ``data/``. A held-out match is refused before any of its files is
opened, so this test reads nothing of them: no rows, no counts, no sizes.
"""

from __future__ import annotations

import pytest
from test_split import CALIBRATION, HELDOUT

from ac2fb.protocol import data

pytestmark = pytest.mark.realdata


def test_the_door_serves_the_ten_calibration_matches() -> None:
    for match_id in CALIBRATION:
        frames = data.read_frames([match_id], columns=["native_match_id"])
        events = data.read_events([match_id], columns=["native_match_id"])
        for table in (frames, events):
            assert table.num_rows > 0
            assert set(table["native_match_id"].to_pylist()) == {match_id}
    matches = data.read_dim("dim_match", CALIBRATION)
    assert sorted(matches["native_match_id"].to_pylist()) == sorted(CALIBRATION)


def test_the_door_refuses_the_ten_heldout_matches() -> None:
    status = data.guard_status()
    assert not status.open, "this test holds until the protocol is frozen"
    assert data.load_split().heldout == HELDOUT
    for match_id in HELDOUT:
        with pytest.raises(data.HeldOutLocked):
            data.read_frames([match_id], columns=["native_match_id"])
        with pytest.raises(data.HeldOutLocked):
            data.read_events([match_id], columns=["native_match_id"])
        with pytest.raises(data.HeldOutLocked):
            data.read_dim("dim_match", [match_id])
