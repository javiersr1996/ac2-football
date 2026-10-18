"""Layer 2 on the base's synthetic match, five seeds, against the runs planted in it.

Every expected number comes from the ``PlantedRun`` list that the generator wrote (a player, a
period, a start frame, a length), by brute force on that list, never from the code under test.
The seed only moves coordinates, so the runs and the answers are the same in all five.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pytest
from ftbase import silver
from ftbase.fixtures import PERIODS, PLANTED_RUNS, PlantedRun
from gate_helpers import build_one

from ac2fb.reliability import runs as R
from ac2fb.reliability.long import LONG_SCHEMA, NO_DETECTION, long_table
from ac2fb.reliability.match import MatchData, build_match
from ac2fb.reliability.sensitivity import (
    Reading,
    Sensitivity,
    Window,
    WindowFrames,
    sensitivity,
)
from ac2fb.reliability.visibility import (
    block_detection,
    detection_by_ball_distance,
    detection_shares,
    reception_detection,
)

# The base's runs plus runs of lengths 1, 3, 8, 12 and 15, one at the first frame of a period.
EXTRA = (
    PlantedRun(73, 1, 20, 15),
    PlantedRun(73, 2, 100, 1),
    PlantedRun(72, 1, 0, 3),
    PlantedRun(82, 1, 35, 12),
    PlantedRun(83, 1, 10, 8),
)
RUNS = PLANTED_RUNS + EXTRA
SEEDS = (1, 2, 3, 4, 5)
PLAYERS = (71, 72, 73, 81, 82, 83)
TEAM = {71: 7, 72: 7, 73: 7, 81: 8, 82: 8, 83: 8}


class Synthetic:
    """One built synthetic match: the tables of the base and the arrays of ac2fb."""

    def __init__(self, data: Path, match_id: int) -> None:
        self.match_id = match_id
        self.frames = silver.read_frames([match_id], data_dir=data)
        self.events = silver.read_events([match_id], data_dir=data)
        self.long = long_table(self.frames)
        self.match: MatchData = build_match(
            match_id, self.frames, self.events, silver.read_dim("dim_team_period", data_dir=data)
        )


@pytest.fixture(scope="module", params=SEEDS, ids=[f"seed{s}" for s in SEEDS])
def synth(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Synthetic:
    seed = int(request.param)
    root = tmp_path_factory.mktemp(f"synth{seed}")
    data = build_one(root, match_id=900000 + seed, seed=seed, runs=RUNS)
    return Synthetic(data, 900000 + seed)


# --- the truth, from the planted runs only ---------------------------------------------------


def planted_frames(player: int) -> set[int]:
    return {f for r in RUNS if r.player_id == player for f in r.frames}


def true_gap(player: int, period: int, frame: int) -> int:
    """Frames to the nearest frame of the period where the player is not in a planted run."""
    first, last = PERIODS[period]
    own = planted_frames(player)
    return min(abs(frame - g) for g in range(first, last + 1) if g not in own)


def period_of(frame: int) -> int:
    return next(p for p, (a, b) in PERIODS.items() if a <= frame <= b)


def in_run(player: int, frame: int) -> bool:
    return frame in planted_frames(player)


# --- gap_len ---------------------------------------------------------------------------------


def test_gap_len_is_the_planted_distance_to_the_nearest_detection(synth: Synthetic) -> None:
    rows = synth.long.to_pylist()
    players = [r for r in rows if r["player_id"] is not None]
    assert len(players) == 120 * len(PLAYERS)
    planted = [r for r in players if in_run(r["player_id"], r["frame"])]
    assert len(planted) == sum(r.length for r in RUNS)
    for r in players:
        want = (
            true_gap(r["player_id"], r["period"], r["frame"])
            if in_run(r["player_id"], r["frame"])
            else 0
        )
        assert r["gap_len"] == want, r
        assert r["is_detected"] == (not in_run(r["player_id"], r["frame"]))
    # The runs the gap test is about are not all the same shape.
    assert {r.length for r in RUNS} >= {1, 3, 8, 12, 15}
    # The largest gap is the 10-frame run that ends a period: only one side has a detection.
    assert max(r["gap_len"] for r in players) == 10
    assert all(r["gap_len"] == 0 for r in rows if r["player_id"] is None)  # the ball


def test_the_longest_planted_gap_is_the_middle_of_the_longest_run(synth: Synthetic) -> None:
    longest = max(RUNS, key=lambda r: r.length)
    gaps = {
        r["frame"]: r["gap_len"]
        for r in synth.long.to_pylist()
        if r["player_id"] == longest.player_id and in_run(longest.player_id, r["frame"])
    }
    assert [gaps[f] for f in longest.frames] == [1, 2, 3, 4, 5, 6, 7, 8, 7, 6, 5, 4, 3, 2, 1]
    # A run that starts a period has only a detection after it, so the gap is the distance to it.
    touching = next(r for r in RUNS if r.start_frame == 0)
    assert [true_gap(touching.player_id, 1, f) for f in touching.frames] == [3, 2, 1]
    after = {
        r["frame"]: r["gap_len"]
        for r in synth.long.to_pylist()
        if r["player_id"] == touching.player_id and r["frame"] < 3
    }
    assert after == {0: 3, 1: 2, 2: 1}


def test_a_series_with_no_detection_has_no_gap_len() -> None:
    series = np.array([1, 1, 1, 2, 2], dtype=np.int64)
    frame = np.array([0, 1, 2, 0, 1], dtype=np.int64)
    detected = np.array([False, False, False, True, False])
    from ac2fb.reliability.long import gap_len

    assert gap_len(series, frame, detected).tolist() == [NO_DETECTION] * 3 + [0, 1]


def test_gap_len_matches_brute_force_on_random_series() -> None:
    from ac2fb.reliability.long import gap_len

    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        sizes = rng.integers(1, 40, 6)
        series = np.repeat(np.arange(len(sizes)), sizes).astype(np.int64)
        # Frames rise with gaps (unlisted frames) inside each series.
        frame = np.concatenate([np.cumsum(rng.integers(1, 4, s)) for s in sizes]).astype(np.int64)
        detected = rng.random(len(series)) < 0.4
        got = gap_len(series, frame, detected)
        for i in range(len(series)):
            same = series == series[i]
            near = np.abs(frame[same & detected] - frame[i])
            want = int(near.min()) if len(near) else NO_DETECTION
            assert got[i] == want, (seed, i)


def test_the_long_table_has_the_documented_columns_and_order(synth: Synthetic) -> None:
    assert synth.long.schema == LONG_SCHEMA
    keys = [
        (r["player_id"] is not None, r["player_id"] or 0, r["frame"])
        for r in synth.long.to_pylist()
    ]
    assert keys == sorted(keys)
    assert synth.long.num_rows == synth.frames.num_rows
    assert set(synth.long["match_id"].to_pylist()) == {f"fb:{synth.match_id}"}


# --- runs --------------------------------------------------------------------------------------


def test_extrapolated_runs_are_the_planted_runs(synth: Synthetic) -> None:
    found = R.extrapolated_runs(synth.match)
    got = sorted(
        zip(
            found.player[~found.detected].tolist(),
            found.start_frame[~found.detected].tolist(),
            found.length[~found.detected].tolist(),
            strict=True,
        )
    )
    want = sorted((r.player_id, r.start_frame, r.length) for r in RUNS)
    assert got == want


def test_the_jump_is_the_step_to_the_first_detected_frame(synth: Synthetic) -> None:
    where = {
        (r["entity_id"], r["frame_native"]): (r["x_m"], r["y_m"]) for r in synth.frames.to_pylist()
    }
    found = R.extrapolated_runs(synth.match)
    for k in np.flatnonzero(~found.detected):
        player, last = int(found.player[k]), int(found.start_frame[k] + found.length[k] - 1)
        run = next(
            r for r in RUNS if r.player_id == player and r.start_frame == found.start_frame[k]
        )
        closes = last < PERIODS[run.period][1]
        if closes:
            (x0, y0), (x1, y1) = where[(f"fb:{player}", last)], where[(f"fb:{player}", last + 1)]
            assert found.jump[k] == pytest.approx(math.hypot(x1 - x0, y1 - y0))
        else:
            assert math.isnan(found.jump[k])
        assert bool(found.left_closed[k]) == (found.start_frame[k] > PERIODS[run.period][0])


def test_unlisted_frames_end_a_run_but_not_in_the_plan_definition(synth: Synthetic) -> None:
    # Player 81 has a run that ends a period and one that starts the next, 10 frames apart.
    plain = R.extrapolated_runs(synth.match)
    bridged = R.extrapolated_runs(synth.match, bridge_holes=True)
    mine = lambda r, p: sorted(  # noqa: E731
        r.length[(r.player == p) & ~r.detected].tolist()
    )
    assert mine(plain, 81) == [6, 10]
    assert mine(bridged, 81) == [15]  # the first frame of the second period is not counted
    assert mine(plain, 72) == [3, 3] and mine(bridged, 72) == [2, 3]  # likewise for 72


def test_the_run_summary_counts_the_planted_runs_by_band(synth: Synthetic) -> None:
    summary = R.run_summary(R.extrapolated_runs(synth.match))
    assert summary["runs"]["n"] == len(RUNS)  # type: ignore[index]
    assert summary["runs"]["frames"] == sum(r.length for r in RUNS)  # type: ignore[index]
    by_band = summary["by_band"]
    cuts = [(0, 10), (10, 50), (50, 200), (200, 10**9)]
    for (name, _), (lo, hi) in zip(R.BANDS, cuts, strict=True):
        assert by_band[name]["n"] == sum(lo < r.length <= hi for r in RUNS)  # type: ignore[index]


# --- visibility --------------------------------------------------------------------------------


def test_detection_shares_are_the_planted_fraction(synth: Synthetic) -> None:
    shares = detection_shares(synth.match)
    total = 120 * len(PLAYERS)
    assert shares["player_rows"] == total
    assert shares["player_detected"] == pytest.approx(1 - sum(r.length for r in RUNS) / total)
    assert shares["ball_detected"] == 1.0


def test_detection_by_ball_distance_samples_one_frame_in_ten(synth: Synthetic) -> None:
    out = detection_by_ball_distance(synth.match)
    sampled = [f for p in PERIODS.values() for f in range(p[0], p[1] + 1) if f % 10 == 0]
    assert sum(b["n"] for b in out.values()) == len(sampled) * len(PLAYERS)  # type: ignore[index]
    hits = sum(not in_run(p, f) for p in PLAYERS for f in sampled)
    seen = sum(b["n"] * b["detected"] for b in out.values() if b["n"])  # type: ignore[index]
    assert seen == pytest.approx(hits)


def test_reception_and_block_detection_follow_the_events(synth: Synthetic) -> None:
    possessions = [e for e in synth.events.to_pylist() if e["native_family"] == "player_possession"]
    assert len(possessions) == 6
    carriers = [
        not in_run(int(e["player_id"].split(":")[1]), e["frame_start"]) for e in possessions
    ]
    out = reception_detection(synth.match)
    assert out["events"] == 6
    assert out["carrier_detected"] == pytest.approx(sum(carriers) / 6)
    phases = [e for e in synth.events.to_pylist() if e["native_family"] == "phases_of_play"]
    want = []
    for e in phases:
        team = int(e["team_id"].split(":")[1])
        others = [p for p in PLAYERS if TEAM[p] != team]
        want.append(sum(not in_run(p, e["frame_start"]) for p in others) / len(others))
    got = block_detection(synth.match)
    assert got["phases"] == 4
    assert got["detected"] == pytest.approx(sum(want) / 4)
    assert got["all_detected"] == pytest.approx(sum(w == 1 for w in want) / 4)


# --- sensitivity -------------------------------------------------------------------------------

TRACKED = (71, 81)
WINDOWS = [(s, s + 5) for s in range(0, 60, 6)]  # ten windows of six frames in period 1


def mean_x(window: WindowFrames) -> Reading | None:
    """Mean x of players 71 and 81 over the window: the value any real metric would be."""
    rows = [i for i, p in enumerate(window.player_ids) if int(p) in TRACKED]
    return Reading(float(np.nanmean(window.x[rows])), TRACKED)


def run_sensitivity(synth: Synthetic, table: pa.Table | None = None) -> Sensitivity:
    windows = [Window(synth.match_id, a, b) for a, b in WINDOWS]
    return sensitivity(mean_x, table if table is not None else synth.long, windows)[synth.match_id]


def test_sensitivity_counts_follow_the_planted_runs(synth: Synthetic) -> None:
    result = run_sensitivity(synth)
    hit = [[p for p in TRACKED if any(in_run(p, f) for f in range(a, b + 1))] for a, b in WINDOWS]
    assert result.n_units == len(WINDOWS) and result.n_skipped == 0
    assert result.v0.n == 10
    assert result.v1.n == sum(not h for h in hit) == 4
    want = {k: sum(len(TRACKED) - len(h) == k for h in hit) for k in (0, 1, 2)}
    assert {s.detected_players: s.n for s in result.v2} == {k: n for k, n in want.items() if n}
    cells = [(p, f) for a, b in WINDOWS for p in TRACKED for f in range(a, b + 1)]
    planted = [(p, f) for p, f in cells if in_run(p, f)]
    assert result.player_frames == len(cells) == 120
    assert result.extrapolated_fraction == pytest.approx(len(planted) / len(cells))
    assert result.absent_fraction == 0.0
    gaps = [true_gap(p, period_of(f), f) for p, f in planted]
    assert result.gap_len.n == len(gaps)
    assert result.gap_len.median == pytest.approx(float(np.median(gaps)))
    assert result.gap_len.p90 == pytest.approx(float(np.quantile(gaps, 0.9)))
    assert result.gap_len.max == max(gaps)


def test_sensitivity_values_are_the_means_of_the_rows(synth: Synthetic) -> None:
    x = {(r["entity_id"], r["frame_native"]): r["x_m"] for r in synth.frames.to_pylist()}

    def value(a: int, b: int) -> float:
        return float(np.mean([x[(f"fb:{p}", f)] for p in TRACKED for f in range(a, b + 1)]))

    result = run_sensitivity(synth)
    every = [value(a, b) for a, b in WINDOWS]
    clean = [
        value(a, b)
        for a, b in WINDOWS
        if not any(in_run(p, f) for p in TRACKED for f in range(a, b + 1))
    ]
    assert result.v0.mean == pytest.approx(float(np.mean(every)))
    assert result.v1.mean == pytest.approx(float(np.mean(clean)))
    assert result.v0.mean != pytest.approx(result.v1.mean)  # the selection moves the metric


def test_a_sensitivity_that_ignored_is_detected_would_give_v0_equal_v1(synth: Synthetic) -> None:
    # The control of the mutation: with every row marked detected, V1 is V0 and nothing is
    # extrapolated; with the real flags it is not. A sensitivity that ignored the flag would
    # behave as the first table on the second.
    real = run_sensitivity(synth)
    all_seen = synth.long.set_column(
        synth.long.schema.get_field_index("is_detected"),
        "is_detected",
        pa.array([True] * synth.long.num_rows),
    )
    forced = run_sensitivity(synth, all_seen)
    assert forced.v1.n == forced.v0.n == 10 and forced.v1.mean == forced.v0.mean
    assert forced.extrapolated_fraction == 0.0
    assert real.v1.n < real.v0.n and real.v1.mean != real.v0.mean
    assert real.extrapolated_fraction and real.extrapolated_fraction > 0


def test_without_windows_every_frame_is_a_unit(synth: Synthetic) -> None:
    def x_of_71(window: WindowFrames) -> Reading | None:
        i = list(window.player_ids).index(71)
        return Reading(float(window.x[i, 0]), (71,))

    result = sensitivity(x_of_71, synth.long)[synth.match_id]
    assert result.v0.n == 120
    assert result.v1.n == 120 - len(planted_frames(71))
    assert {s.detected_players: s.n for s in result.v2} == {
        0: len(planted_frames(71)),
        1: 120 - len(planted_frames(71)),
    }


def test_units_the_metric_cannot_measure_are_skipped(synth: Synthetic) -> None:
    result = sensitivity(
        lambda w: None, synth.long, [Window(synth.match_id, a, b) for a, b in WINDOWS]
    )[synth.match_id]
    assert (result.n_units, result.n_skipped, result.v0.mean) == (0, 10, None)


def test_a_player_the_provider_does_not_list_counts_as_absent(synth: Synthetic) -> None:
    gone = synth.long.filter(
        pc.invert(pc.and_(pc.equal(synth.long["player_id"], 71), pc.less(synth.long["frame"], 6)))
    )
    result = sensitivity(
        mean_x, gone, [Window(synth.match_id, 0, 5), Window(synth.match_id, 6, 11)]
    )[synth.match_id]
    assert result.absent_fraction == pytest.approx(6 / 24)  # 71 in the first window
    assert result.v1.n == 0  # the first window lacks 71; the second has planted frames of 71
