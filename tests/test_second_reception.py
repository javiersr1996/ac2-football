"""The rule of the page's second reception (``scripts/second_reception.py``) on a planted world.

A hand-built match, no data and no base: two teams of five and seven, two periods, one receiver
(player 11) receiving at frames 20, 40, 60 and 80 of the first period, each reception held by a
phase of play of his team that starts two frames before it. The rivals stand so that each unit the
page draws reads its own players: the line is 21 to 24, the pressure 26 alone, the nearest rival
25 (behind the receiver, so it weighs nothing in the pressure), the block's length 20 (the
goalkeeper) and 25, at the start of the phase. Every row is detected; each test plants what the
camera did not see, or a hole, in a copy and asks which reception the rule picks. Each test names
the mutation of the rule that makes it fail.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pyarrow as pa
import pytest

from ac2fb import clip
from ac2fb.reliability import metrics
from ac2fb.reliability.match import Event, MatchData, locate_rows
from ac2fb.reliability.sensitivity import Window, sensitivity, window_frames

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "second_reception", ROOT / "scripts" / "second_reception.py"
)
assert _spec is not None and _spec.loader is not None
sr: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules["second_reception"] = sr
_spec.loader.exec_module(sr)

MATCH_ID = 1
A, B = 1, 2  # the receiver's team attacks +x in period 1, -x in period 2
TINY = clip.Rule(before=5, frames=20, min_seen=4)
PERIODS = {1: range(0, 100), 2: range(200, 300)}
KEYS = (20, 40, 60, 80)
# where each player stands, in the frame where the receiver's team attacks +x
SPOTS = {
    10: (A, -50.0, 0.0),  # A's goalkeeper (the proxy: deepest in his own half)
    11: (A, 20.0, 0.0),  # the receiver
    12: (A, 0.0, -20.0),
    13: (A, 0.0, 20.0),
    14: (A, -20.0, 0.0),
    20: (B, 50.0, 0.0),  # B's goalkeeper: one end of the block's length
    21: (B, 32.0, -15.0),  # 21 to 24: the line, the four deepest outfield rivals
    22: (B, 32.0, -5.0),
    23: (B, 32.0, 5.0),
    24: (B, 32.0, 15.0),
    25: (B, 17.0, 0.0),  # the nearest rival, right behind the receiver: no weight in pressure
    26: (B, 25.0, 6.0),  # the one rival within the pressure's radius and ahead
}
LINE, PRESSURE, NEAREST, BLOCK = (21, 22, 23, 24), (26,), (25,), (20, 25)


def _events(keys: tuple[int, ...] = KEYS, phase_back: int = 2) -> list[Event]:
    out = []
    for k in keys:
        period = 1 if k < 200 else 2
        out.append(Event("phases_of_play", "build_up", k - phase_back, k + 10, period, A, None))
        out.append(Event("player_possession", "pass", k, k + 10, period, A, 11))
    return out


def world(
    spots: dict[int, tuple[int, float, float]] = SPOTS, events: list[Event] | None = None
) -> MatchData:
    """The planted match: every player listed and detected in every frame, the ball at the
    receiver's feet."""
    frames = np.array([f for r in PERIODS.values() for f in r], dtype=np.int64)
    period = np.array([p for p, r in PERIODS.items() for _ in r], dtype=np.int64)
    sign = np.where(period == 1, 1.0, -1.0)
    ids = sorted(spots)
    n = len(frames)
    player = np.repeat(np.array(ids, dtype=np.int64), n)
    team = np.repeat(np.array([spots[p][0] for p in ids], dtype=np.int64), n)
    x = np.concatenate([spots[p][1] * sign for p in ids])
    y = np.concatenate([spots[p][2] * sign for p in ids])
    frame = np.tile(frames, len(ids))
    order = np.argsort(frame, kind="stable")
    return MatchData(
        match_id=MATCH_ID,
        player=player,
        team=team,
        period=np.tile(period, len(ids)),
        frame=frame,
        x=x,
        y=y,
        detected=np.ones(len(player), dtype=np.bool_),
        gap=np.zeros(len(player), dtype=np.int64),
        key=player * (1 << 32) + frame,
        frame_order=order,
        frame_sorted=frame[order],
        ball_frame=frames,
        ball_period=period,
        ball_x=spots[11][1] * sign,
        ball_y=spots[11][2] * sign,
        ball_detected=np.ones(n, dtype=np.bool_),
        ball_gap=np.zeros(n, dtype=np.int64),
        events=tuple(_events() if events is None else events),
        attack_sign={(1, A): 1, (1, B): -1, (2, A): -1, (2, B): 1},
    )


def plant(
    match: MatchData, out: dict[tuple[int, int], int] | None = None, ball_out: int | None = None
) -> MatchData:
    """A copy with ``out[(player, frame)] = gap_len`` filled in (gap -1: none), ``ball_out`` the
    frame of a ball the camera did not see."""
    detected, gap, ball = match.detected.copy(), match.gap.copy(), match.ball_detected.copy()
    for (player, frame), g in (out or {}).items():
        row = locate_rows(match, np.array([player]), np.array([frame]))[0]
        detected[row], gap[row] = False, g
    if ball_out is not None:
        ball[int(np.searchsorted(match.ball_frame, ball_out))] = False
    return dataclasses.replace(match, detected=detected, gap=gap, ball_detected=ball)


def table(match: MatchData) -> pa.Table:
    """The match's player rows as the long table's columns that ``window_frames`` reads."""
    return pa.table(
        {
            "match_id": pa.array([f"fb:{match.match_id}"] * len(match.player)),
            "player_id": match.player,
            "frame": match.frame,
            "team_id": match.team,
            "x": match.x,
            "y": match.y,
            "is_detected": match.detected,
            "gap_len": match.gap.astype(np.int32),
        }
    )


def every(frames: np.ndarray) -> bool:
    return True


def pick(match: MatchData, rule: clip.Rule = TINY, corners=every) -> object:
    return sr.choose(match, window_frames(table(match)), corners, rule)


def key_of(found: object) -> int:
    scene = found.scene  # type: ignore[attr-defined]
    return int(scene.frame[scene.key])


def rejected(found: object) -> dict[str, int]:
    return {k: v for k, v in found.rejected.items() if v}  # type: ignore[attr-defined]


# --- the planted world reads as designed --------------------------------------------------------


def test_the_world_reads_as_designed() -> None:
    # Not a test of the rule: the units of the reception at 20 read the players this file plants.
    m = world()
    units_of = metrics.metric_units(m)
    windows = window_frames(table(m))
    players = {
        name: sr.reading(units_of, windows, MATCH_ID, metric, 20 if at == "reception" else 18)[
            1
        ].player_ids
        for name, metric, at in sr.UNITS
    }
    assert players == {
        "line": LINE,
        "block": BLOCK,
        "pressure": PRESSURE,
        "nearest": NEAREST,
    }


# --- the rule ------------------------------------------------------------------------------------


def test_the_earliest_reception_whose_units_all_count_wins() -> None:
    found = pick(world())
    assert key_of(found) == 20 and rejected(found) == {}
    scene = found.scene
    assert scene.frame.tolist() == list(range(15, 35)) and scene.key == TINY.before
    assert scene.receiver == 11 and scene.team == A and scene.period == 1
    assert scene.rivals.tolist() == [20, 21, 22, 23, 24, 25, 26]
    assert found.phase.frame_start == 18
    assert {n: (f, r.player_ids) for n, (f, _, r) in found.units.items()} == {
        "line": (20, LINE),
        "block": (18, BLOCK),
        "pressure": (20, PRESSURE),
        "nearest": (20, NEAREST),
    }


def test_a_line_defender_filled_in_at_the_reception_skips_it() -> None:
    # Mutation (the line left out of the units, or V1 not tested): 20 wins.
    found = pick(plant(world(), {(21, 20): 7}))
    assert key_of(found) == 40 and rejected(found) == {"v1": 1}


def test_the_pressure_and_the_nearest_rival_are_tested_on_their_own() -> None:
    # 26 is in the pressure alone, 25 at the reception in the nearest alone (the block reads 25 at
    # the phase's start). Mutation (either unit left out): 20 wins.
    assert key_of(pick(plant(world(), {(26, 20): 3}))) == 40
    assert key_of(pick(plant(world(), {(25, 20): 3}))) == 40


def test_the_block_is_read_at_the_start_of_its_phase_not_at_the_reception() -> None:
    # The goalkeeper fixes the block's length: filled in at the phase's start (18) the reception is
    # skipped; filled in at the reception only, it is not. Mutation (the block read at the
    # reception): both assertions turn.
    assert key_of(pick(plant(world(), {(20, 18): 40}))) == 40
    assert key_of(pick(plant(world(), {(20, 20): 40}))) == 20


def test_a_unit_that_reads_no_player_counts_as_sensitivity_counts_it() -> None:
    # 26 moved out of every radius: the pressure at 20 reads nobody, and sensitivity keeps it in V1.
    # Mutation (an empty unit refused): 20 is skipped and, with no reception left, none is found.
    spots = {**SPOTS, 26: (B, -30.0, 30.0)}
    m = world(spots)
    found = pick(m)
    assert key_of(found) == 20 and found.units["pressure"][2].player_ids == ()
    metric, _ = metrics.metric_units(m)["pressure_index"]
    assert sensitivity(metric, table(m), [Window(MATCH_ID, 20, 20)])[MATCH_ID].v1.n == 1


def test_the_receiver_and_the_ball_must_be_seen_at_the_reception() -> None:
    # The clip's candidates. Mutation (receiver or ball not tested): 20 wins.
    receiver = pick(plant(world(), {(11, 20): 1}))
    ball = pick(plant(world(), ball_out=20))
    assert key_of(receiver) == key_of(ball) == 40
    assert rejected(receiver) == rejected(ball) == {"seen": 1}


def test_at_least_min_seen_rivals_must_be_seen_and_exactly_min_seen_is_enough() -> None:
    # The goalkeeper filled in at the reception (no unit reads him there): 6 of 7 rivals seen.
    # Mutation (``<`` to ``<=``, or the threshold off by one): one of the three assertions fails.
    m = plant(world(), {(20, 20): 40})
    assert key_of(pick(m, clip.Rule(before=5, frames=20, min_seen=6))) == 20
    assert key_of(pick(m, clip.Rule(before=5, frames=20, min_seen=7))) == 40
    assert key_of(pick(world(), clip.Rule(before=5, frames=20, min_seen=7))) == 20


def test_a_window_with_a_hole_is_skipped() -> None:
    # The goalkeeper without a gap_len at frame 30 (in the window, read by no unit). Mutation (the
    # clip's completeness not tested): 20 wins.
    found = pick(plant(world(), {(20, 30): -1}))
    assert key_of(found) == 40 and rejected(found) == {"window": 1}


def test_a_window_before_the_period_is_skipped() -> None:
    # A reception at frame 3 has no 5 frames before it. Mutation (window clipped to the data): 3
    # wins.
    found = pick(world(events=_events((3, *KEYS))))
    assert key_of(found) == 20 and rejected(found) == {"window": 1}


def test_a_window_without_the_cameras_corners_is_skipped() -> None:
    # Frame 25 has no corners: the window of 20 (15 to 34) holds it, that of 40 does not.
    # Mutation (corners not asked): 20 wins.
    found = pick(world(), corners=lambda frames: 25 not in frames)
    assert key_of(found) == 40 and rejected(found) == {"corners": 1}


@pytest.mark.parametrize(
    ("events", "wins"),
    [
        ([e for e in _events() if e.frame_start != 18], 40),  # no phase holds 20
        (
            [*_events(), Event("phases_of_play", "create", 19, 25, 1, A, None)],
            40,
        ),  # two hold it
        (_events(phase_back=6), None),  # every phase starts before its window
        (_events(phase_back=5), 20),  # at the window's first frame: inside
        (
            [e for e in _events() if e.frame_start != 18]
            + [Event("phases_of_play", "build_up", 18, 30, 1, B, None)],
            40,
        ),  # a phase of the other team
    ],
)
def test_exactly_one_phase_of_the_team_holds_the_reception_and_starts_in_the_window(
    events: list[Event], wins: int | None
) -> None:
    # Mutation (any team's phase, the count or the start unasked, ``<`` for ``<=``): a case turns.
    if wins is None:
        with pytest.raises(sr.NoReception, match="phase 4"):
            pick(world(events=events))
    else:
        assert key_of(pick(world(events=events))) == wins


def test_receptions_are_taken_by_period_and_frame_whatever_the_events_order() -> None:
    # Mutation (the events' own order): 80, listed first, wins.
    events = _events()[::-1]
    assert (events[0].family, events[0].frame_start) == ("player_possession", 80)
    assert key_of(pick(world(events=events))) == 20


def test_the_reasons_count_every_reception_turned_down() -> None:
    m = plant(world(), {(21, 20): 7, (20, 50): -1, (11, 60): 1})
    found = pick(m)
    assert key_of(found) == 80
    assert found.rejected == {
        "seen": 1,
        "window": 1,
        "corners": 0,
        "phase": 0,
        "unit": 0,
        "v1": 1,
    }


def test_no_reception_that_passes_is_an_error_naming_the_match() -> None:
    every_line = {(21, k): 7 for k in KEYS}
    with pytest.raises(sr.NoReception, match=f"match {MATCH_ID} .*4 looked at.*v1 4"):
        pick(plant(world(), every_line))


@pytest.mark.parametrize(
    ("name", "metric", "player", "frame"),
    [
        ("line", "line_height_m", 22, 20),
        ("block", "block_length_m", 20, 18),
        ("pressure", "pressure_index", 26, 20),
        ("nearest", "nearest_rival_m", 25, 20),
    ],
)
def test_counts_in_v1_is_sensitivitys_v1_unit_by_unit(
    name: str, metric: str, player: int, frame: int
) -> None:
    # Seen and filled in, each unit: counts_in_v1 says what sensitivity's V1 count says. Mutation
    # (``detected`` read at one player only, or ``present`` dropped): a case differs.
    for m in (world(), plant(world(), {(player, frame): 5})):
        fn, _ = metrics.metric_units(m)[metric]
        got = sr.reading(metrics.metric_units(m), window_frames(table(m)), MATCH_ID, metric, frame)
        assert got is not None
        want = sensitivity(fn, table(m), [Window(MATCH_ID, frame, frame)])[MATCH_ID].v1.n
        assert sr.counts_in_v1(*got) == bool(want)


def test_the_rule_in_words_carries_its_numbers_and_its_units() -> None:
    words = sr.describe(clip.DEFAULT_RULE)
    assert "at least 4 rivals" in words and "100 frames at 10 Hz from 30 frames before" in words
    assert "line_height_m, pressure_index and nearest_rival_m at the reception" in words
    assert "block_length_m at the start of that phase" in words
    other = sr.describe(clip.Rule(before=7, frames=50, min_seen=2))
    assert "at least 2 rivals" in other and "50 frames at 10 Hz from 7 frames before" in other
