"""Task 26: the amputation reference and ``reports/amputation.csv``, on planted and random worlds.

Every expected number is written here from the planted geometry: a player on a straight path is
filled exactly; one on a parabola ``x = x0 + c (f - t)^2``, hidden in a gap with its detections
``b`` frames before ``t`` and ``a`` after, is filled ``c a b`` metres off at ``t`` (the chord of
the parabola), so the line it belongs to is ``c a b / 4`` off.

Mutations, each with the test that kills it (script and log in the task's record):

* a fill that holds the last detected position instead of the straight line:
  ``test_the_fill_is_the_straight_line_between_the_detections``,
  ``test_a_curved_path_gives_the_analytic_error``;
* ends that stay at ``t - back`` and ``t + ahead`` when the player is not detected there, or
  that cross the break between periods: ``test_the_ends_move_out_to_the_nearest_detection``;
* a hiding probability that is the detected share, or a pool that keeps the open gaps or every
  sampled frame: ``test_the_hiding_is_the_match_s_own``;
* a unit binned by its shortest gap: ``test_a_unit_goes_to_the_band_of_its_longest_gap``;
* every V0 unit amputated, not only V1: ``test_only_the_v1_units_are_amputated``;
* one stream of draws for all the matches or all the metrics:
  ``test_the_draws_are_fixed_and_no_match_or_metric_moves_another``;
* a check that compares fewer columns, misses a row or a carriage return, or does not say how
  much it verified: the tests of the check below.
"""

from __future__ import annotations

import csv
import dataclasses
import io
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
from layer2_helpers import Row, event, make_match
from test_reliability_metrics import long_of, random_world

from ac2fb import cli
from ac2fb.reliability import amputate, metrics, visibility
from ac2fb.reliability.amputate import Ends, Hiding
from ac2fb.reliability.match import MatchData
from ac2fb.reliability.sensitivity import Window, sensitivity, window_frames
from ac2fb.reliability.table import render_csv

T = 200  # the frame of the one possession of the planted world
FRAMES = range(100, 301)
STILL = {  # player: (x, y); the carrier (1, team 1) attacks +x, the rivals are team 2
    1: (0.0, 0.0),
    11: (30.0, 0.0),
    12: (25.0, 5.0),
    13: (20.0, -5.0),
    14: (15.0, 0.0),
    15: (5.0, 2.0),  # the fifth outfield rival: not in the line
    20: (45.0, 0.0),  # the goalkeeper
}
TEAMS = {1: 1, **{p: 2 for p in STILL if p != 1}}

Trajectory = Callable[[int], tuple[float, float]]


def planted(
    paths: dict[int, Trajectory] | None = None,
    hidden: Sequence[tuple[int, range]] = (),
    period_two_from: int | None = None,
) -> MatchData:
    """Everyone still (or on ``paths``), detected but in ``hidden``; the ball on the carrier."""
    moving = paths or {}
    rows: dict[int, list[Row]] = {}
    for p, (x0, y0) in STILL.items():
        where = moving.get(p, lambda f, x0=x0, y0=y0: (x0, y0))
        rows[p] = [
            (f, *where(f), not any(p == q and f in span for q, span in hidden)) for f in FRAMES
        ]
    ball: list[Row] = [(f, 0.0, 0.0, True) for f in FRAMES]
    match = make_match(
        rows,
        TEAMS,
        ball=ball,
        events=[event("player_possession", T, T, 1, 1)],
        signs={1: 1, 2: -1},
    )
    if period_two_from is None:
        return match
    sides = {**match.attack_sign, **{(2, t): -s for (_, t), s in match.attack_sign.items()}}
    return dataclasses.replace(
        match,
        period=np.where(match.frame >= period_two_from, 2, 1).astype(np.int64),
        ball_period=np.where(match.ball_frame >= period_two_from, 2, 1).astype(np.int64),
        attack_sign=sides,
    )


def every_bin(back: int, ahead: int, probability: float = 1.0) -> Hiding:
    """Every player hidden with ``probability``, its gap ``back`` frames back, ``ahead`` ahead."""
    k = len(visibility.BALL_DISTANCE_EDGES) + 1
    return Hiding(
        (probability,) * k,
        (np.array([back], dtype=np.int64),) * k,
        (np.array([ahead], dtype=np.int64),) * k,
    )


def line_at_t(match: MatchData, hide: Hiding) -> amputate.Amputation:
    held = metrics.possessions(match.events)
    return amputate.amputate(
        match,
        window_frames(long_of(match)),
        metrics.line_height(match, held),
        [Window(match.match_id, T, T)],
        hide,
        np.random.default_rng(0),
    )


# --- the fill -------------------------------------------------------------------------------------


def test_a_gap_of_nothing_changes_nothing() -> None:
    match = planted()
    window = window_frames(long_of(match))(Window(7, T - 13, T))
    assert window is not None
    same = amputate.fill(window, {})
    for name in ("x", "y", "detected", "present"):
        assert np.array_equal(getattr(same, name), getattr(window, name)), name
    got = line_at_t(match, every_bin(30, 50, probability=0.0))
    assert (got.n_units, got.n_skipped, got.bands, got.errors) == (1, 0, ("none",), (0.0,))


@pytest.mark.parametrize(("velocity", "back", "ahead"), [(0.05, 30, 50), (-0.3, 1, 1), (0.2, 7, 2)])
def test_the_fill_is_the_straight_line_between_the_detections(
    velocity: float, back: int, ahead: int
) -> None:
    # Player 11 on a straight path: the fill lands on it, the line height does not move.
    match = planted({11: lambda f: (30.0 + velocity * (f - T), 0.0)})
    got = line_at_t(match, every_bin(back, ahead))
    assert got.n_units == 1 and got.bands[0] != "none"
    assert got.errors[0] == pytest.approx(0.0, abs=1e-12)
    window = window_frames(long_of(match))(Window(7, T - 13, T))
    assert window is not None
    row = int(np.flatnonzero(window.player_ids == 11)[0])
    lo, hi = T - back, T + ahead
    filled = amputate.fill(
        window, {11: Ends(lo, 30.0 - velocity * back, 0.0, hi, 30.0 + velocity * ahead, 0.0)}
    )
    inside = (window.frames > lo) & (window.frames < hi)
    assert np.allclose(filled.x[row], window.x[row], atol=1e-12)
    assert not filled.detected[row, inside].any() and filled.detected[row, ~inside].all()


@pytest.mark.parametrize(("c", "back", "ahead"), [(0.001, 30, 50), (-0.002, 12, 3), (0.004, 1, 9)])
def test_a_curved_path_gives_the_analytic_error(c: float, back: int, ahead: int) -> None:
    match = planted({11: lambda f: (30.0 + c * (f - T) ** 2, 0.0)})
    got = line_at_t(match, every_bin(back, ahead))
    assert got.errors[0] == pytest.approx(c * back * ahead / 4, rel=1e-9)


# --- the ends of a gap ----------------------------------------------------------------------------


def test_the_ends_move_out_to_the_nearest_detection() -> None:
    match = planted(hidden=[(11, range(T - 40, T - 25)), (11, range(T + 50, T + 60))])
    sides = amputate.detected_sides(match)
    found = amputate.ends_of(match, sides, 11, T, 30, 50)
    assert found is not None and (found.lo, found.hi) == (T - 41, T + 60)
    assert amputate.ends_of(match, sides, 11, T, 20, 40) == Ends(
        T - 20, 30.0, 0.0, T + 40, 30.0, 0.0
    )
    # no detection before the gap in the player's period: frames before 120 are another period
    split = planted(hidden=[(11, range(120, T - 5))])
    split = dataclasses.replace(split, period=np.where(split.frame < 120, 0, 1).astype(np.int64))
    assert amputate.ends_of(split, amputate.detected_sides(split), 11, T, 10, 5) is None
    # nor after it: from 230 the match is in period 2
    later = planted(period_two_from=230)
    assert amputate.ends_of(later, amputate.detected_sides(later), 11, T, 5, 29) is not None
    assert amputate.ends_of(later, amputate.detected_sides(later), 11, T, 5, 30) is None
    # and a curved path is filled between the ends that moved out
    c = 0.001
    curved = planted({11: lambda f: (30.0 + c * (f - T) ** 2, 0.0)}, [(11, range(T - 40, T - 25))])
    assert line_at_t(curved, every_bin(30, 50)).errors[0] == pytest.approx(c * 41 * 50 / 4)


def test_a_unit_whose_hidden_player_has_no_detection_on_one_side_is_skipped() -> None:
    match = planted(hidden=[(11, range(T + 1, 301))])
    got = line_at_t(match, every_bin(3, 4))
    assert (got.n_units, got.n_skipped, got.errors) == (1, 1, ())


def test_a_unit_without_the_ball_at_t_is_skipped() -> None:
    match = planted()
    keep = match.ball_frame != T
    match = dataclasses.replace(
        match,
        **{f: getattr(match, f)[keep] for f in ("ball_frame", "ball_period", "ball_x", "ball_y")},
        ball_detected=match.ball_detected[keep],
        ball_gap=match.ball_gap[keep],
    )
    got = line_at_t(match, every_bin(3, 4))
    assert (got.n_units, got.n_skipped) == (1, 1)


def test_a_unit_goes_to_the_band_of_its_longest_gap() -> None:
    # Every line player gets the gap (4 back, 5 ahead): 8 frames, up to 1 s. Player 12 is not
    # detected from t - 30 to t - 4, so its gap opens at t - 31: 35 frames, 1 to 5 s.
    alone = line_at_t(planted(), every_bin(4, 5))
    assert alone.bands == ("le_1s",)
    longer = line_at_t(planted(hidden=[(12, range(T - 30, T - 3))]), every_bin(4, 5))
    assert longer.bands == ("1_5s",)


# --- the hiding of a match ------------------------------------------------------------------------


def test_the_hiding_is_the_match_s_own() -> None:
    # Rival 15 (5.4 m from the ball, bin 05_10) is lost from 103 to 111, detected at 102 and
    # 112, and lost again from 290 to the end (no detection after: an open gap, not in the pool).
    match = planted(hidden=[(15, range(103, 112)), (15, range(290, 301))])
    hide = amputate.hiding(match)
    shares = visibility.detection_by_ball_distance(match, amputate.EVERY)
    for k, figures in enumerate(shares.values()):
        seen = figures["detected"]  # type: ignore[index]
        assert hide.probability[k] == pytest.approx(0.0 if seen is None else 1 - seen)
    assert hide.probability[1] == pytest.approx(3 / 21)  # 110, 290 and 300 of 21 sampled frames
    assert [b.tolist() for b in hide.back] == [[], [8], [], [], [], []]
    assert [a.tolist() for a in hide.ahead] == [[], [2], [], [], [], []]


# --- the units ------------------------------------------------------------------------------------


def with_ball(match: MatchData, seed: int) -> MatchData:
    """The random world with a ball that wanders, listed in every frame, detected or not."""
    rng = np.random.default_rng(seed + 100)
    frames = np.arange(80, 301, dtype=np.int64)
    walk = np.cumsum(rng.normal(0.0, 1.0, (len(frames), 2)), axis=0)
    return dataclasses.replace(
        match,
        ball_frame=frames,
        ball_period=np.ones(len(frames), dtype=np.int64),
        ball_x=walk[:, 0],
        ball_y=walk[:, 1],
        ball_detected=rng.random(len(frames)) < 0.8,
        ball_gap=np.zeros(len(frames), dtype=np.int64),
    )


@pytest.mark.parametrize("seed", (1, 2, 3, 4, 5))
def test_only_the_v1_units_are_amputated(seed: int) -> None:
    match = with_ball(random_world(seed)[0], seed)
    long = long_of(match)
    hide = amputate.hiding(match)
    assert sum(len(b) for b in hide.back) > 0
    # the match's own hiding, and the same gaps with everyone hidden, so some unit is hidden
    always = dataclasses.replace(hide, probability=(1.0,) * len(hide.probability))
    hidden = 0
    for name, (metric, windows) in metrics.metric_units(match).items():
        v1 = sensitivity(metric, long, windows)[7].v1.n
        for how in (hide, always):
            rng = np.random.default_rng(seed)
            got = amputate.amputate(match, window_frames(long), metric, windows, how, rng)
            assert got.n_units == v1, name
            assert got.n_skipped + len(got.errors) == got.n_units
            pairs = zip(got.bands, got.errors, strict=True)
            assert all(e == 0.0 for b, e in pairs if b == "none")
            hidden += sum(b != "none" for b in got.bands) if how is always else 0
    assert hidden > 0


# --- the table ------------------------------------------------------------------------------------

WORLDS = {7: 1, 8: 2}  # match id: seed of its random world


def world_of(match_id: int) -> tuple[MatchData, pa.Table]:
    match = dataclasses.replace(
        with_ball(random_world(WORLDS[match_id])[0], match_id), match_id=match_id
    )
    return match, long_of(match)


@pytest.fixture
def worlds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(amputate, "load_with_long", world_of)


def rows_in(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline="")))


def test_the_table_has_every_metric_and_band_in_order(worlds: None, tmp_path: Path) -> None:
    rows = rows_in(amputate.write_table([8, 7], tmp_path))
    assert tuple(rows[0]) == amputate.COLUMNS
    keys = [tuple(r[:3]) for r in rows[1:]]
    assert keys == [
        (str(m), name, band)
        for m in (7, 8)
        for name in metrics.METRICS
        for band in amputate.BAND_NAMES
    ]
    by = {tuple(r[:3]): dict(zip(amputate.COLUMNS, r, strict=True)) for r in rows[1:]}
    for m in ("7", "8"):
        for name in metrics.METRICS:
            parts = [int(by[m, name, b]["n"]) for b in amputate.BAND_NAMES[:-1]]
            whole = by[m, name, "all"]
            assert sum(parts) == int(whole["n"]) == int(whole["n_units"]) - int(whole["n_skipped"])
            none = by[m, name, "none"]
            assert none["n"] == "0" or (none["mean_abs_error"], none["max_abs_error"]) == (
                "0.0",
                "0.0",
            )
    raw = (tmp_path / amputate.REPORT_NAME).read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n") and b"nan" not in raw.lower()


def test_the_draws_are_fixed_and_no_match_or_metric_moves_another(
    worlds: None, tmp_path: Path
) -> None:
    both = rows_in(amputate.write_table([7, 8], tmp_path))[1:]
    assert both == rows_in(amputate.write_table([7, 8], tmp_path))[1:]
    alone = rows_in(amputate.write_table([8], tmp_path))[1:]
    assert [r for r in both if r[0] == "8"] == alone
    # each metric has its own stream: the seed, the match and the metric's place in METRICS
    match, long = world_of(8)
    name = "line_height_m"
    metric, windows = metrics.metric_units(match)[name]
    rng = np.random.default_rng([amputate.SEED, 8, metrics.METRICS.index(name)])
    hide = amputate.hiding(match)
    one = amputate.amputate(match, window_frames(long), metric, windows, hide, rng)
    assert amputate._rows(8, name, one) == [r for r in alone if r[1] == name]
    assert any(b != "none" for b in one.bands)


def checked(directory: Path, ids: Sequence[int] = (7,)) -> amputate.Check:
    return amputate.check(list(ids), (directory / amputate.REPORT_NAME).read_bytes())


def edit(path: Path, change: Callable[[list[list[str]]], object]) -> None:
    rows = rows_in(path)
    change(rows)
    path.write_bytes(render_csv(amputate.COLUMNS, rows[1:]).encode("utf-8"))


def test_the_check_passes_and_counts_what_it_compared(worlds: None, tmp_path: Path) -> None:
    rows = rows_in(amputate.write_table([7], tmp_path))
    got = checked(tmp_path)
    assert got.ok and got.matches == 1
    assert got.rows == len(rows) - 1 and got.cells == (len(rows) - 1) * len(amputate.COLUMNS)


@pytest.mark.parametrize("column", amputate.COLUMNS)
def test_the_check_sees_a_mutated_cell_in_every_column(
    worlds: None, tmp_path: Path, column: str
) -> None:
    amputate.write_table([7], tmp_path)
    j = amputate.COLUMNS.index(column)
    edit(tmp_path / amputate.REPORT_NAME, lambda rows: rows[-1].__setitem__(j, rows[-1][j] + "9"))
    got = checked(tmp_path)
    assert not got.ok
    words = " {column}: file " if j >= 3 else "the code: " if j in (1, 2) else ""
    assert any(words.format(column=column) in p for p in got.problems), got.problems


def test_the_check_sees_a_missing_extra_or_repeated_row_and_a_cr(
    worlds: None, tmp_path: Path
) -> None:
    path = amputate.write_table([7], tmp_path)
    edit(path, lambda rows: rows.pop(5))
    assert any("missing from the file" in p for p in checked(tmp_path).problems)
    amputate.write_table([7], tmp_path)
    edit(path, lambda rows: rows.append([*rows[1][:2], "gt_99s", *rows[1][3:]]))
    assert any("not produced by the code" in p for p in checked(tmp_path).problems)
    amputate.write_table([7], tmp_path)
    edit(path, lambda rows: rows.append(list(rows[1])))
    assert any("repeats" in p for p in checked(tmp_path).problems)
    good = amputate.write_table([7], tmp_path).read_bytes()
    path.write_bytes(good.replace(b"\n", b"\r\n"))
    assert any("carriage return" in p for p in checked(tmp_path).problems)
    path.write_bytes(good.replace(b"band", b"bands", 1))
    assert not checked(tmp_path).ok
    assert "does not exist" in amputate.check([7], None).problems[0]


def test_the_command_writes_and_checks_and_says_how_much_it_verified(
    worlds: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["amputation", "--match", "7", "--reports-dir", str(tmp_path)]) == 0
    assert "wrote" in capsys.readouterr().out
    rows = len(rows_in(tmp_path / amputate.REPORT_NAME)) - 1
    args = ["amputation", "--check", "--match", "7", "--reports-dir", str(tmp_path)]
    assert cli.main(args) == 0
    out = capsys.readouterr().out
    assert f"verified: {rows} rows, {rows * len(amputate.COLUMNS)} cells, 1 matches" in out
    assert "amputation: OK" in out
    edit(tmp_path / amputate.REPORT_NAME, lambda rows: rows[1].__setitem__(8, "123"))
    assert cli.main(args) == 1
    out = capsys.readouterr().out
    assert "amputation: FAILED" in out and " n_units: file " in out
    assert rows_in(tmp_path / amputate.REPORT_NAME)[1][8] == "123"  # --check wrote nothing


def test_the_reading_runs_the_amputation() -> None:
    assert cli.LAYER2_READS["amputation"] is amputate.write_table
