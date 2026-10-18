"""Probe S2: the line, its concordance, the pre-trend within strata, visibility and the rule.

Every expected number is built here from the planted geometry, never from the code under
test. The synthetic world: team 1 carries the ball at the origin; team 2 defends with a
goalkeeper at depth 50, four line players at a base height ``h`` (20 to 35 m) that move as a
block, and one presser at 3 m (pressed) or 8 m (free) in front of the carrier. The incoming
ball travels 6 m forward or backward in ``[t - 13, t]``, so every reception falls in the stratum
``forward/middle/short`` or ``backward/middle/short``. The line moves by the planted ``P`` in
``[t - 13, t]`` (+1 m after a forward ball, -1 m after a backward one, plus a noise that is the
same, value for value, among the pressed and the free of each stratum). **The confounder of the
plan's m10 is planted**: 60 % of the receptions after a forward ball are pressed and 40 % after
a backward one, so pressed minus free is +0.4 m overall and exactly 0 inside each stratum.

Mutations, each annotated with the test that kills it:

* strata shuffled or ignored (the pre-trend becomes the crude +0.4 m, in m10's range of +0.0 to
  +0.5 m): ``test_the_strata_absorb_the_planted_confounder`` (the plan's mutation; the same
  test also shows the crude figure with the strata collapsed);
* a depth that ignores the attack direction: ``test_a_mirrored_world_gives_the_same_report``;
* a line re-ranked at each frame: ``test_the_line_is_chosen_at_t_and_never_reranked``;
* the goalkeeper in the line: ``test_the_line_height_is_the_planted_one``;
* a visibility window that stops at ``t``: ``test_visibility_counts_the_whole_window``;
* a seen player that only needs a row, not a detection: ``test_an_extrapolated_frame_breaks_v1``;
* any statistic that reads a position after ``t``: ``test_nothing_after_t_is_read_but_detection``;
* a pre-trend verdict on the raw statistic only:
  ``test_a_pretrend_only_in_the_residual_still_counts``;
* a concordance without its minimum of pairs: ``test_too_few_pairs_fail_the_concordance``;
* a ball contrast on one side only or without its minimum:
  ``test_each_side_of_the_ball_contrast_is_needed``;
* a pooled pre-trend with weights of 1, not in sd, or a minimum on one group only:
  ``test_within_strata_by_hand``;
* a ball window that starts late or misses an unlisted ball row:
  ``test_the_ball_extrapolated_before_t``;
* a rule with 8 of 10, 3 matches over, or one short match allowed in V1:
  ``test_the_verdict_follows_the_written_rule``.

The source mutations (31, script outside the repository) are listed in the plan's record.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
from layer2_helpers import Row, make_match

from ac2fb.defence import line, m10, pressure, probe_s2
from ac2fb.defence.line import LineReception
from ac2fb.defence.probe_s2 import MatchInputs
from ac2fb.reliability.report import render_report

ROOT = Path(__file__).resolve().parent.parent
SEEDS = (1, 2, 3, 4, 5)
W = 13
N = 40  # receptions after a forward ball, and as many after a backward one
PRESSED = {"forward": 24, "backward": 16}  # of N: the planted confounder
LINE = (21, 22, 23, 24)
LINE_Y = (-15.0, -5.0, 5.0, 15.0)
TEAMS = {1: 1, 2: 1, 20: 2, 21: 2, 22: 2, 23: 2, 24: 2, 25: 2}


def plan(seed: int) -> list[tuple[str, bool, float, float]]:
    """Per reception: direction, pressed, planted P and base height h (in reception order)."""
    rng = np.random.default_rng(seed)
    a = 0.3 + 0.1 * seed
    rows: list[tuple[str, bool, float, float]] = []
    for direction, sign in (("forward", 1.0), ("backward", -1.0)):
        for pressed, count in ((True, PRESSED[direction]), (False, N - PRESSED[direction])):
            for k in range(count):
                noise = a if k % 2 == 0 else -a  # the same multiset in each group
                rows.append((direction, pressed, sign + noise, 0.0))
    order = rng.permutation(len(rows))
    return [
        (d, p, value, 20.0 + 15.0 * ((i * 7) % 11) / 10.0)
        for i, (d, p, value, _) in enumerate(rows[j] for j in order)
    ]


def world(
    seed: int,
    *,
    mirror: bool = False,
    before: float = 0.0,
    before_pressed: float | None = None,
    after: float = 0.05,
    hidden: dict[int, list[tuple[int, int]]] | None = None,
    unlisted: dict[int, list[tuple[int, int]]] | None = None,
    ball_hidden: dict[int, list[int]] | None = None,
    ball_unlisted: dict[int, list[int]] | None = None,
    late_flags: bool = True,
    provider: str = "line",
) -> MatchInputs:
    """The synthetic match. ``hidden``/``unlisted``: per reception, (player, frame offset) not
    detected / without a row. ``ball_hidden``/``ball_unlisted``: per reception, ball frame
    offsets not detected / without a row.
    ``before``: line velocity per frame before ``t - 13`` (``before_pressed`` for the pressed
    receptions, when given); ``after``: after ``t``.
    ``late_flags``: whether the frames after ``t`` are detected. ``provider``: ``line``
    (the planted height plus a little noise), ``negated``, ``none`` or ``few`` (the planted
    one for the first 29 receptions only)."""
    s = -1.0 if mirror else 1.0
    series: dict[int, list[Row]] = {p: [] for p in TEAMS}
    ball: list[Row] = []
    receptions: list[LineReception] = []
    for i, (direction, pressed, p_value, h) in enumerate(plan(seed)):
        t = 100 + 60 * i
        slope = before_pressed if before_pressed is not None and pressed else before
        series[1].append((t, 0.0, 0.0, True))
        series[2].append((t, s * -20.0, 0.0, True))
        series[25].append((t, s * (3.0 if pressed else 8.0), 0.0, True))
        for f in range(t - 20, t + W + 3):
            series[20].append((f, s * 50.0, 0.0, True))
            if f <= t - W:
                offset = slope * (f - (t - W))
            elif f <= t:
                offset = p_value * (f - (t - W)) / W
            else:
                offset = p_value + after * (f - t)
            for player, y in zip(LINE, LINE_Y, strict=True):
                if (player, f - t) in (unlisted or {}).get(i, []):
                    continue
                seen = (player, f - t) not in (hidden or {}).get(i, [])
                seen = seen and (late_flags or f <= t)
                series[player].append((f, s * (h + offset), s * y, seen))
        start = -6.0 if direction == "forward" else 6.0
        for f in range(t - 20, t + 1):
            if f - t in (ball_unlisted or {}).get(i, []):
                continue
            x = start - start * (f - (t - W)) / W
            ball.append((f, s * x, 0.0, f - t not in (ball_hidden or {}).get(i, [])))
        planted = h + p_value + 0.3 * math.sin(i)
        value = {
            "line": planted,
            "negated": -(h + p_value),
            "none": None,
            "few": planted if i < 29 else None,
        }
        receptions.append(LineReception(f"e{i}", 1, t, 1, 1, value[provider], None))
    match = make_match(series, TEAMS, ball=ball, signs={1: int(s), 2: -int(s)})
    return MatchInputs(match, tuple(receptions), len(receptions))


def report(inputs: MatchInputs) -> dict[str, object]:
    return probe_s2.match_report(inputs)


def at(tree: object, path: str) -> object:
    for part in path.split("."):
        tree = tree[part]  # type: ignore[index]
    return tree


# --- the line itself -----------------------------------------------------------------------------


def test_the_line_height_is_the_planted_one() -> None:
    # Mutation: the goalkeeper (depth 50) in the line moves every height by about +5 m.
    inputs = world(1, before=0.04)
    units, dropped = line.build_units(inputs.match, inputs.receptions, probe_s2.LAGS)
    assert len(units) == 2 * N and dropped == dict.fromkeys(dropped, 0)
    for u, (_, _, p_value, h) in zip(units, plan(1), strict=True):
        assert set(u.line) == set(LINE)
        assert u.depth[0] == pytest.approx(h + p_value, abs=1e-9)
        assert u.depth[W] == pytest.approx(h, abs=1e-9)
        assert u.depth[W + 5] == pytest.approx(h - 0.04 * 5, abs=1e-9)
        assert u.depth[10] == pytest.approx(h + p_value * 3 / W, abs=1e-9)


def test_the_line_is_chosen_at_t_and_never_reranked() -> None:
    # A fifth defender is shallow at t but deeper than the line at t - 13 and before. Mutation:
    # re-ranking the line at each lag puts him in it at t - 13.
    inputs = world(2)
    t = inputs.receptions[0].frame
    series: dict[int, list[Row]] = {1: [(t, 0.0, 0.0, True)], 25: [(t, 3.0, 0.0, True)]}
    series[20] = [(f, 50.0, 0.0, True) for f in range(t - 20, t + 1)]
    series[26] = [(f, 45.0 if f < t else 10.0, 20.0, True) for f in range(t - 20, t + 1)]
    for player, y in zip(LINE, LINE_Y, strict=True):
        series[player] = [(f, 30.0, y, True) for f in range(t - 20, t + 1)]
    teams = {1: 1, 20: 2, 21: 2, 22: 2, 23: 2, 24: 2, 25: 2, 26: 2}
    rebuilt = make_match(series, teams, signs={1: 1, 2: -1})
    [unit], _ = line.build_units(rebuilt, inputs.receptions[:1], (W,))
    assert set(unit.line) == set(LINE) and unit.depth[W] == pytest.approx(30.0)


def test_a_reception_without_a_line_is_left_out_and_counted() -> None:
    inputs = world(3)
    t = inputs.receptions[0].frame
    series: dict[int, list[Row]] = {
        1: [(t, 0.0, 0.0, True)],
        20: [(t, 50.0, 0.0, True)],
        21: [(t, 30.0, 0.0, True)],
        22: [(t, 30.0, 5.0, True)],
        23: [(t, 30.0, 9.0, True)],
    }
    short = make_match(series, {1: 1, 20: 2, 21: 2, 22: 2, 23: 2}, signs={1: 1, 2: -1})
    units, dropped = line.build_units(short, inputs.receptions[:1], (W,))
    assert units == [] and dropped["no_line"] == 1


def test_a_mirrored_world_gives_the_same_report() -> None:
    # The team attacks -x and every position is rotated: depth = x * sign gives the same line.
    # Mutation: a depth that ignores the sign picks other players and changes everything.
    for seed in SEEDS:
        assert report(world(seed)) == report(world(seed, mirror=True))


# --- (a) concordance and (b) the line following the ball ----------------------------------------


def test_the_planted_line_agrees_with_the_provider() -> None:
    for seed in SEEDS:
        conc = at(report(world(seed)), "instrument.concordance")
        assert conc["pass"] is True  # type: ignore[index]
        assert conc["line"]["n"] == 2 * N  # type: ignore[index]
        assert conc["line"]["pearson_r"] > 0.99  # type: ignore[index]


def test_a_provider_line_that_disagrees_fails_the_instrument() -> None:
    out = report(world(1, provider="negated"))
    assert at(out, "instrument.concordance.line.pearson_r") == pytest.approx(-1.0)
    assert at(out, "instrument.concordance.pass") is False and at(out, "instrument.pass") is False


def test_without_provider_values_there_are_no_pairs() -> None:
    out = report(world(1, provider="none"))
    assert at(out, "instrument.concordance.line.n") == 0
    assert at(out, "instrument.concordance.pass") is False


def test_too_few_pairs_fail_the_concordance() -> None:
    # Mutation: a concordance without the minimum of pairs passes on 29 near-perfect ones.
    conc = at(report(world(1, provider="few")), "instrument.concordance")
    assert conc["line"]["n"] == 29 and conc["line"]["pearson_r"] > 0.99  # type: ignore[index]
    assert conc["pass"] is False  # type: ignore[index]


def test_concordance_by_hand() -> None:
    got = line.concordance([1.0, 2.0, 3.0, 4.0], [3.0, 4.0, 5.0, 6.0])
    assert got["pearson_r"] == pytest.approx(1.0)
    # ccc = 2 * 1.25 / (1.25 + 1.25 + 2^2)
    assert got["ccc"] == pytest.approx(2.5 / 6.5)
    assert got["median_diff"] == -2.0 and got["median_abs_diff"] == 2.0
    assert line.concordance([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])["pearson_r"] is None


def test_the_line_follows_the_planted_ball() -> None:
    by = at(report(world(4)), "instrument.follows_ball")
    assert by["pass"] is True  # type: ignore[index]
    assert by["by_direction"]["forward"]["mean"] == pytest.approx(1.0, abs=1e-9)  # type: ignore[index]
    assert by["by_direction"]["backward"]["mean"] == pytest.approx(-1.0, abs=1e-9)  # type: ignore[index]
    assert by["by_direction"]["lateral"]["n"] == 0  # type: ignore[index]


def test_a_line_that_does_not_follow_the_ball_fails() -> None:
    inputs = world(4)
    # The same world seen from the other side of the ball: the stratum flips, the line does not.
    monkey = {"forward": "backward", "backward": "forward"}
    units, _ = line.build_units(inputs.match, inputs.receptions, probe_s2.LAGS)
    flipped = [
        line.Unit(**{**u.__dict__, "stratum": monkey[u.stratum.split("/")[0]] + "/middle/short"})
        for u in units
    ]
    assert probe_s2._follows_ball(flipped)["pass"] is False


@pytest.mark.parametrize(
    ("side", "shift", "drop"), [("backward", 1.5, 0), ("forward", -1.5, 0), ("backward", 0.0, 11)]
)
def test_each_side_of_the_ball_contrast_is_needed(side: str, shift: float, drop: int) -> None:
    # Mutations: a contrast that checks only one side, or no minimum count per side. Here the
    # backward line retreats on average, or the forward one steps up, or 29 backward are left.
    inputs = world(4)
    units, _ = line.build_units(inputs.match, inputs.receptions, probe_s2.LAGS)
    kept: list[line.Unit] = []
    for u in units:
        if u.stratum.startswith(side):
            if drop:
                drop -= 1
                continue
            u = line.Unit(**{**u.__dict__, "depth": {**u.depth, 0: u.depth[0] + shift}})
        kept.append(u)
    assert probe_s2._follows_ball(units)["pass"] is True
    assert probe_s2._follows_ball(kept)["pass"] is False


# --- (c) the pre-trend within strata, against the planted confounder ----------------------------


def test_the_strata_absorb_the_planted_confounder(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mutation (the plan's): strata shuffled or ignored. Then the pre-trend is the crude one,
    # +0.4 m (inside m10's +0.0 to +0.5 m), well above 0.15 sd, and the first asserts fail.
    for seed in SEEDS:
        pre = at(report(world(seed)), "pretrend")
        for name in ("raw", "residual"):
            assert abs(pre[name]["within_strata"]["m"]) < 1e-9  # type: ignore[index]
            assert abs(pre[name]["within_strata"]["sd"]) < 1e-9  # type: ignore[index]
            assert pre[name]["within_strata"]["strata_used"] == 2  # type: ignore[index]
            assert pre[name]["crude"]["m"] == pytest.approx(0.4, abs=1e-9)  # type: ignore[index]
        assert pre["over"] is False  # type: ignore[index]
    # The same worlds with the strata collapsed (a shuffle that keeps nothing of the ball).
    monkeypatch.setattr(pressure, "incoming_ball", lambda *_: "forward/middle/short")
    for seed in SEEDS:
        pre = at(report(world(seed)), "pretrend")
        within, crude = pre["raw"]["within_strata"], pre["raw"]["crude"]  # type: ignore[index]
        assert within["m"] == pytest.approx(0.4, abs=1e-9)
        assert within["sd"] == pytest.approx(crude["sd"]) and within["sd"] > 0.15
        assert pre["over"] is True  # type: ignore[index]


def test_shuffled_strata_do_not_recover_zero() -> None:
    inputs = world(1)
    units, _ = line.build_units(inputs.match, inputs.receptions, probe_s2.LAGS)
    values = [u.depth[0] - u.depth[W] for u in units]
    pressed = [u.pressed for u in units]
    strata = [u.stratum for u in units]
    assert line.within_strata(values, pressed, strata, 5)["m"] == pytest.approx(0.0, abs=1e-9)
    for seed in SEEDS:
        shuffled = list(np.random.default_rng(seed).permutation(strata))
        assert abs(line.within_strata(values, pressed, shuffled, 5)["m"]) > 1e-3  # type: ignore[arg-type]


def test_within_strata_by_hand() -> None:
    # A: pressed 3, 5; free 1, 1 -> d = 3, sd of {3, 5, 1, 1} = sqrt(11/3), w = 2 * 2 / 4 = 1.
    # B: pressed 2, 2; free 0 -> one free, below min_cell 2 (d = 2, sd sqrt(4/3), w = 2/3).
    # C: pressed 4; free 1, 3 -> one pressed, below min_cell 2 (d = 2, sd sqrt(7/3), w = 2/3).
    # Mutations: weights of 1, d not divided by the sd, a minimum on one group only.
    values = [3.0, 5.0, 1.0, 1.0, 2.0, 2.0, 0.0, 4.0, 1.0, 3.0]
    pressed = [True, True, False, False, True, True, False, True, False, False]
    strata = ["A"] * 4 + ["B"] * 3 + ["C"] * 3
    got = line.within_strata(values, pressed, strata, 2)
    assert got["m"] == pytest.approx(3.0)
    assert got["sd"] == pytest.approx(3.0 / math.sqrt(11 / 3))
    assert got["units_used"] == 4 and got["units_left_out"] == 6 and got["strata_used"] == 1
    every = line.within_strata(values, pressed, strata, 1)
    w = (1.0, 2 / 3, 2 / 3)
    d = (3.0, 2.0, 2.0)
    sd = (math.sqrt(11 / 3), math.sqrt(4 / 3), math.sqrt(7 / 3))
    assert every["m"] == pytest.approx(sum(a * b for a, b in zip(w, d, strict=True)) / sum(w))
    assert every["sd"] == pytest.approx(
        sum(a * b / c for a, b, c in zip(w, d, sd, strict=True)) / sum(w)
    )


def test_a_pretrend_only_in_the_residual_still_counts() -> None:
    # The pressed lines already moved 0.05 m per frame before t - 13, the free ones did not; in
    # [t - 13, t] they move alike. Raw: 0 within strata; residual: 13 * 0.05 = 0.65 m less for
    # the pressed. Mutation: a pre-trend verdict on the raw statistic alone misses it.
    pre = at(report(world(2, before_pressed=0.05)), "pretrend")
    assert abs(pre["raw"]["within_strata"]["m"]) < 1e-9  # type: ignore[index]
    assert pre["residual"]["within_strata"]["m"] == pytest.approx(-0.65)  # type: ignore[index]
    assert pre["over"] is True  # type: ignore[index]


def test_no_stratum_to_pool_counts_as_over() -> None:
    assert probe_s2._pretrend([])["over"] is True


def test_the_residual_and_the_velocity_by_hand() -> None:
    # Before t - 13 the line moves 0.04 m per frame: the residual takes 13 * 0.04 off P; the
    # velocity at t is P * 5 / 13 over 0.5 s.
    inputs = world(5, before=0.04)
    units, _ = line.build_units(inputs.match, inputs.receptions, probe_s2.LAGS)
    for u, (_, _, p_value, _) in zip(units, plan(5), strict=True):
        assert probe_s2._raw(u) == pytest.approx(p_value, abs=1e-9)
        assert probe_s2._residual(u) == pytest.approx(p_value - W * 0.04, abs=1e-9)
        assert probe_s2._velocity(u) == pytest.approx(p_value * 5 / W / 0.5, abs=1e-9)
    vel = at(report(inputs), "velocity")
    pressed_p = [p for _, pr, p, _ in plan(5) if pr]
    assert vel["pressed"]["mean"] == pytest.approx(np.mean(pressed_p) * 5 / W / 0.5)  # type: ignore[index]


# --- (e) visibility and (f) the ball --------------------------------------------------------------


def test_visibility_counts_the_whole_window() -> None:
    # Mutation: a window that stops at t misses the frame t + 13.
    base = at(report(world(1)), "visibility")
    assert base["v0"] == base["v1"] == 2 * N  # type: ignore[index]
    late = at(report(world(1, hidden={3: [(21, W)], 7: [(22, -W)]})), "visibility")
    assert late["v1"] == 2 * N - 2  # type: ignore[index]
    assert late["by_detected"] == {"0": 0, "1": 0, "2": 0, "3": 2, "4": 2 * N - 2}  # type: ignore[index]
    outside = at(report(world(1, hidden={3: [(21, W + 1)], 7: [(22, -W - 1)]})), "visibility")
    assert outside["v1"] == 2 * N  # type: ignore[index]


def test_an_extrapolated_frame_breaks_v1() -> None:
    # Mutation: a player counted as seen because he has rows, detected or not.
    out = at(report(world(2, hidden={0: [(21, 5), (22, 5), (23, 0)]})), "visibility")
    assert out["by_detected"]["1"] == 1 and out["v1"] == 2 * N - 1  # type: ignore[index]
    gone = at(report(world(2, unlisted={0: [(24, 4)]})), "visibility")
    assert gone["v1"] == 2 * N - 1  # type: ignore[index]


def test_visibility_tallies_by_group_stratum_and_distance() -> None:
    inputs = world(3, hidden={k: [(21, 1)] for k in range(0, 2 * N, 5)})
    vis = at(report(inputs), "visibility")
    rows = plan(3)
    seen = [k % 5 != 0 for k in range(2 * N)]
    for group, flag in (("pressed", True), ("free", False)):
        want_v0 = sum(p is flag for _, p, _, _ in rows)
        want_v1 = sum(p is flag and s for (_, p, _, _), s in zip(rows, seen, strict=True))
        assert vis["by_group"][group][f"v0_{group}"] == want_v0  # type: ignore[index]
        assert vis["by_group"][group][f"v1_{group}"] == want_v1  # type: ignore[index]
    fwd = vis["by_stratum"]["forward/middle/short"]  # type: ignore[index]
    assert fwd["v0_pressed"] + fwd["v0_free"] == N
    # Distance of the line to the ball at t (the ball is at the origin), binned by hand.
    edges = (5.0, 10.0, 20.0, 30.0, 40.0)
    names = ("00_05", "05_10", "10_20", "20_30", "30_40", "40_plus")
    want: dict[str, int] = {}
    for _, _, p_value, h in rows:
        d = float(np.mean([math.hypot(h + p_value, y) for y in LINE_Y]))
        key = names[sum(d >= e for e in edges)]
        want[key] = want.get(key, 0) + 1
    got = {k: v["v0_pressed"] + v["v0_free"] for k, v in vis["by_ball_distance"].items()}  # type: ignore[attr-defined]
    assert got == want


def test_the_ball_extrapolated_before_t() -> None:
    # Mutations: a window that starts late, or one that misses a ball row the provider omits.
    inputs = world(
        4, ball_hidden={0: [-5], 1: [-W], 2: [0], 3: [-W - 1]}, ball_unlisted={4: [-3], 5: [-14]}
    )
    ball = at(report(inputs), "ball")
    assert ball["n"] == 2 * N  # type: ignore[index]
    assert ball["extrapolated_in_window"] == pytest.approx(4 / (2 * N))  # type: ignore[index]
    assert ball["extrapolated_at_ends"] == pytest.approx(2 / (2 * N))  # type: ignore[index]


def test_nothing_after_t_is_read_but_detection() -> None:
    # Mutation: any item but visibility that reads a position after t changes here.
    a, b = report(world(1, after=0.05)), report(world(1, after=-2.0))
    assert a == b
    flags = report(world(1, late_flags=False))
    assert {k: v for k, v in flags.items() if k != "visibility"} == {
        k: v for k, v in a.items() if k != "visibility"
    }
    assert at(flags, "visibility.v1") == 0 and at(a, "visibility.v1") == 2 * N


# --- the receptions from the events and the provider -------------------------------------------


def test_line_receptions_join_the_provider_and_keep_the_unlabelled() -> None:
    def possession(event: str, frame: int, player: str | None = "fb:9") -> dict[str, object]:
        return {
            "native_family": "player_possession",
            "native_event_id": event,
            "frame_start": frame,
            "period": 1,
            "team_id": "fb:3",
            "player_id": player,
        }

    rows = [possession("a", 10), possession("b", 10), possession("c", 30, None)]
    rows.append({**possession("d", 40), "native_family": "on_ball_engagement"})
    events = pa.table({k: [r[k] for r in rows] for k in rows[0]})
    bronze = pa.table(
        {
            "event_id": ["a", "b", "d"],
            "event_type": ["player_possession", "player_possession", "on_ball_engagement"],
            "last_defensive_line_x_start": pa.array([31.5, None, 2.0], pa.float64()),
            "overall_pressure_start": ["low_pressure", None, None],
        }
    )
    total, found = probe_s2.line_receptions(events, bronze)
    assert total == 3
    assert found == [
        LineReception("a", 1, 10, 3, 9, 31.5, "low_pressure"),
        LineReception("b", 1, 10, 3, 9, None, None),
    ]


# --- the rule -----------------------------------------------------------------------------------


def test_the_verdict_follows_the_written_rule() -> None:
    def made(instrument: int = 10, over: int = 0, v1: list[int] | None = None, n: int = 10):  # type: ignore[no-untyped-def]
        counts = v1 or [150] * n
        return probe_s2.verdict(
            {i: i < instrument for i in range(n)},
            {i: i < over for i in range(n)},
            {i: counts[i] for i in range(n)},
        )

    assert made()["c2_survives_probe"] is True
    assert made(instrument=9)["c2_survives_probe"] is True
    assert made(instrument=8)["c2_survives_probe"] is False
    assert made(over=2)["c2_survives_probe"] is True
    assert made(over=3)["c2_survives_probe"] is False
    assert made(v1=[150] * 9 + [99])["c2_survives_probe"] is False
    assert made(v1=[150] * 9 + [99])["v1_short_matches"] == [9]
    assert made(v1=[150] * 9 + [100])["c2_survives_probe"] is True
    partial = made(n=9)
    assert partial["c2_survives_probe"] is None and partial["complete"] is False
    assert made(instrument=8, over=3)["criteria"] == {
        "instrument": False,
        "pretrend": False,
        "visibility": True,
    }


def test_the_constants_are_the_ones_the_plan_and_the_artifacts_say() -> None:
    cadence = json.loads((ROOT / "reports" / "probe_cadence.json").read_text("utf-8"))
    assert pressure.INCOMING_WINDOW == W == cadence["decision"]["w_min_frames"]
    split = json.loads((ROOT / "protocol" / "split.json").read_text("utf-8"))
    assert probe_s2.CALIBRATION_MATCHES == len(split["calibration"])
    assert sorted(m10.M10_PER_MATCH) == sorted(split["calibration"])
    assert (probe_s2.MIN_INSTRUMENT, probe_s2.MAX_OVER, probe_s2.MIN_V1) == (9, 2, 100)
    assert probe_s2.MAX_PRETREND_SD == 0.15 and probe_s2.MIN_R == 0.9
    assert line.PRESSED_RADIUS == 5.0 and line.LINE_SIZE == 4
    assert probe_s2.LAGS == (5, 10, 13, 18, 20)


# --- m10 re-derived -----------------------------------------------------------------------------


def test_m10_direction_and_figures_on_the_planted_world() -> None:
    assert [m10.direction(v) for v in (2.01, 2.0, -2.0, -2.01)] == ["fwd", "lat", "lat", "back"]
    inputs = world(2)
    units, _ = line.build_units(inputs.match, inputs.receptions, probe_s2.LAGS)
    figures = m10.match_figures(units)
    rows = plan(2)
    assert at(figures, "units.n") == 2 * N
    # pre1 is P * 10 / 13 (the line moves linearly in [t - 13, t]); the ball moves 6 * 10 / 13.
    pre1 = [p * 10 / W for _, _, p, _ in rows]
    fwd = [v for v, (d, _, _, _) in zip(pre1, rows, strict=True) if d == "forward"]
    assert at(figures, "direction.fwd.n") == N and at(figures, "direction.lat.n") == 0
    assert at(figures, "direction.fwd.pre1_all") == pytest.approx(np.mean(fwd))
    assert at(figures, "direction.fwd.sd") == pytest.approx(np.std(fwd, ddof=1))
    assert at(figures, "direction.fwd.diff1") == pytest.approx(0.0, abs=1e-9)
    assert at(figures, "pressure.diff1") == pytest.approx(0.4 * 10 / W)
    assert at(figures, "pressure.share_pressed") == pytest.approx(0.5)
    assert at(figures, "confounder.dball_pressed") == pytest.approx((24 - 16) / 40 * 6 * 10 / W)
    assert at(figures, "confounder.fwd_pressed") == pytest.approx(24 / 40)


def test_m10_ball_carrier_by_hand() -> None:
    t = 100
    series: dict[int, list[Row]] = {1: [(t, 0.0, 0.0, True)], 2: [(t + 50, 0.0, 0.0, True)]}
    ball: list[Row] = [(t, 0.6, 0.8, True), (t + 50, 3.0, 4.0, True)]
    match = make_match(series, {1: 1, 2: 1}, ball=ball, signs={1: 1})
    got = m10.ball_carrier(
        match,
        [
            LineReception("a", 1, t, 1, 1, None, None),
            LineReception("b", 1, t + 50, 1, 2, None, None),
            LineReception("c", 1, t + 70, 1, 2, None, None),  # no carrier row
        ],
    )
    assert got == {"n": 2, "median": 3.0, "p90": pytest.approx(4.6), "le2": 0.5, "le1": 0.5}


def test_m10_compare_uses_the_printed_decimals() -> None:
    match_id = 1874553
    printed = m10.M10_PER_MATCH[match_id]
    figures: dict[str, object] = {}
    for key, (value, digits) in printed.items():
        node = figures
        *parents, last = key.split(".")
        for part in parents:
            node = node.setdefault(part, {})  # type: ignore[assignment]
        # Off by just under half a unit of the last printed decimal: still the same.
        node[last] = value if digits is None else value + 0.49 * 10.0**-digits
    out = m10.compare({match_id: figures}, None)
    assert out["figures"] == len(printed) and out["same"] == len(printed) and out["differ"] == []
    figures["ball"]["median"] = printed["ball.median"][0] + 0.006  # type: ignore[index]
    figures["units"]["n"] = printed["units.n"][0] + 1  # type: ignore[index]
    out = m10.compare({match_id: figures}, None)
    assert out["differ"] == [f"{match_id}.ball.median", f"{match_id}.units.n"]
    assert out["pooled"] is None


# --- the report ---------------------------------------------------------------------------------


def test_the_report_is_per_match_with_the_verdict_and_writes_lf(tmp_path: Path) -> None:
    out = probe_s2.s2_report([world(1), world(2)])
    assert set(out) == {"about", "constants", "m10_inventory", "matches", "verdict"}
    assert list(out["matches"]) == ["7"]  # type: ignore[arg-type]  # both worlds are match 7
    assert out["verdict"]["c2_survives_probe"] is None  # type: ignore[index]
    assert out["m10_inventory"]["pooled"] is None  # type: ignore[index]
    path = tmp_path / probe_s2.REPORT_NAME
    path.write_bytes(render_report(out).encode("utf-8"))
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert json.loads(raw)["constants"]["window_frames"] == W
