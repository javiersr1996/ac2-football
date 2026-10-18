"""The split committed at HEAD is plan decision 1, word for word."""

from __future__ import annotations

from ac2fb.protocol import data

CALIBRATION = (
    1874553, 1886347, 1925299, 1959846, 1996435, 1996436, 2007448, 2010085, 2011166, 2015213
)  # fmt: skip
HELDOUT = (
    1899585, 1927964, 1953632, 1986691, 2006229, 2006363, 2007721, 2013725, 2016236, 2017461
)  # fmt: skip


def test_the_committed_split_is_decision_1() -> None:
    split = data.load_split()
    assert split.calibration == CALIBRATION
    assert split.heldout == HELDOUT
    assert len(set(CALIBRATION) | set(HELDOUT)) == 20
