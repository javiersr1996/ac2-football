"""Task 20: the estimator of the protocol, on hand-made cases and on four planted worlds.

Nothing here touches a real match. The first half is the statistic, its pre-trend, its null,
the bars and the criteria on cases whose numbers are planted or computed by an independent
route (``numpy.linalg.lstsq``, ``design.pooled_pretrend``, a hand-drawn permutation). The second
half plants a world and asks the estimator for it, five seeds each, at the level the claim lives
in: the statistic (a planted effect, a planted pre-trend) or the tracking through the real
pipeline (a confounder the strata cancel, players interpolated in a gap, a cause read late).

Mutations, each annotated with the test that kills it:

* the cause read one second after ``t`` (the index at ``t + 10`` frames):
  ``test_a_cause_read_at_t_finds_no_effect_in_reverse_causation`` (and the mutated reading, built
  in ``cause_read_late``, is shown to pass the bar and the pre-trend by
  ``test_the_cause_read_a_second_late_passes_the_bar_and_the_pretrend``);
* no strata (the incoming-ball stratum a constant): ``test_the_strata_cancel_the_confounder``;
* the covariate dropped (a plain difference): ``test_the_coefficient_adjusts_for_what_came_before``
  and ``test_a_planted_pretrend_is_caught_by_d3``;
* the sd with ddof 0: ``test_a_flat_x_cell_is_the_plain_difference_by_hand``;
* the labels permuted across cells instead of inside them:
  ``test_the_null_permutes_inside_the_cell``;
* a draw stream that does not depend on (half, variant), or on the order of the units:
  ``test_the_stream_is_the_protocols`` and ``test_the_draws_do_not_depend_on_the_order_of_units``;
* the sign condition counting a match whose effect is 0 when ``T`` is 0, or p compared with ``<``:
  ``test_t_zero_never_passes``, ``test_the_calibration_bar_by_hand``;
* a pre-trend over the cells with a constant ``x`` or in the wrong units:
  ``test_the_pretrend_by_hand`` and ``test_the_pretrend_agrees_with_the_design_module``;
* a window read across a period break (the ball row's period not checked at ``t - W``, ``t`` or
  ``t + W``): ``test_no_window_crosses_a_period_break``;
* the outcome read without the attack sign, or with the sign of another period:
  ``test_a_mirrored_pitch_in_the_second_period_gives_the_same_outcomes``.
"""

from __future__ import annotations

import dataclasses
import functools
import math
import zlib
from collections.abc import Sequence

import numpy as np
import pytest
from effect_helpers import (
    FAR,
    LATE,
    Rival,
    Spec,
    ahead,
    cause_read_late,
    collapse_strata,
    confounded_world,
    extrapolated_world,
    plain_difference,
    planted_units,
    reverse_world,
    through_the_pipeline,
    tracking_match,
)

from ac2fb.defence import bar, design, effect, power, pressure
from ac2fb.defence.effect import EffectUnit
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.reliability import runs

SEEDS = [0, 1, 2, 3, 4]


def planted_z(tau: float, persistence: float, shift: float, share: float = 0.4) -> float:
    """The effect in sd of the cell that ``planted_units`` plants (its closed form)."""
    pq = share * (1 - share)
    var_x = 1 + shift**2 * pq
    var_y = 1 + persistence**2 * var_x + tau**2 * pq + 2 * persistence * tau * shift * pq
    return tau / math.sqrt(var_y)


def mk(
    m: int,
    stratum: str,
    pressed: bool,
    pre: float | None,
    outcome: float | None,
    k: int,
    possession: str | None = None,
    extra: int = 0,
    ball: bool = True,
) -> EffectUnit:
    return EffectUnit(
        match=m,
        period=1,
        frame=100 + 40 * k,
        stratum=stratum,
        pressed=pressed,
        possession=possession or f"p{k}",
        pre=pre,
        outcome=outcome,
        extrapolated_players=extra,
        ball_detected=None if outcome is None else ball,
    )


def cell(
    m: int, stratum: str, pressed: list[tuple[float, float]], free: list[tuple[float, float]]
) -> list[EffectUnit]:
    """A cell from (x, y) pairs of the pressed and of the free units."""
    rows = [(True, x, y) for x, y in pressed] + [(False, x, y) for x, y in free]
    return [mk(m, stratum, g, x, y, k) for k, (g, x, y) in enumerate(rows)]


def random_cells(seed: int) -> list[EffectUnit]:
    """Three matches, four strata each, random sizes, groups, ``x`` and ``y``."""
    rng = np.random.default_rng([30, seed])
    units: list[EffectUnit] = []
    k = 0
    for m in (1, 2, 3):
        for s in range(4):
            n = int(rng.integers(14, 40))
            g = rng.random(n) < rng.uniform(0.3, 0.6)
            x = rng.normal(0, 1.5, n) + 0.7 * g
            y = 2.0 * s + 0.8 * x - 0.6 * g + rng.normal(0, 1.2, n)
            for i in range(n):
                units.append(mk(m, f"s{s}", bool(g[i]), float(x[i]), float(y[i]), k, f"p{k // 3}"))
                k += 1
    return units


def reference(units: Sequence[EffectUnit]) -> dict[str, object]:
    """The statistic by ``lstsq`` cell by cell, with plain loops: the independent route."""
    cells: dict[tuple[int, str], list[EffectUnit]] = {}
    for u in units:
        cells.setdefault((u.match, u.stratum), []).append(u)
    rows = []
    for (m, s), us in sorted(cells.items()):
        g = np.array([u.pressed for u in us], dtype=float)
        x = np.array([u.pre for u in us], dtype=float)
        y = np.array([u.outcome for u in us], dtype=float)
        n_p, n_f = g.sum(), (1 - g).sum()
        if n_p < 5 or n_f < 5:
            continue
        design_matrix = np.column_stack([np.ones_like(g), x, g])
        coef = np.linalg.lstsq(design_matrix, y, rcond=None)[0]
        rows.append((m, s, coef[2], coef[1], np.std(y, ddof=1), n_p * n_f / (n_p + n_f)))
    z = {(r[0], r[1]): r[2] / r[4] for r in rows}
    w = {(r[0], r[1]): r[5] for r in rows}
    t = sum(w[k] * z[k] for k in z) / sum(w.values())
    by_match = {}
    for m in {k[0] for k in z}:
        keys = [k for k in z if k[0] == m]
        by_match[m] = sum(w[k] * z[k] for k in keys) / sum(w[k] for k in keys)
    return {"rows": rows, "t": t, "by_match": by_match}


# --- the outcome -------------------------------------------------------------------------------


def test_the_outcome_by_hand() -> None:
    specs = [
        Spec(2.0, 7.5, (Rival(pos=ahead(3.0)), Rival(pos=(-30.0, 0.0))), ball_end_detected=False),
        Spec(2.0, -4.0, (Rival(pos=ahead(3.0)), Rival(pos=(-30.0, 0.0)))),
    ]
    match = tracking_match(5, specs).s1.match
    first, second = 100, 140
    got = effect.read_outcome(match, first, 1)
    assert got == effect.Outcome(advance=7.5, ball_detected=False)  # extrapolated end still counts
    assert effect.read_outcome(match, first, -1) == effect.Outcome(-7.5, False)
    assert effect.read_outcome(match, second, 1) == effect.Outcome(-4.0, True)
    assert effect.read_outcome(match, second, -1) == effect.Outcome(4.0, True)
    assert effect.read_outcome(match, first + W, 1) is None  # no ball row at t + 2 W
    assert effect.read_outcome(match, first + 1, 1) is None  # no ball row at t itself


def test_no_window_crosses_a_period_break() -> None:
    # In five calibration matches the break between periods is shorter than W, so the ball row
    # at t + W (or t - W) can belong to the other period: the period ended, nothing is read.
    match = tracking_match(5, [Spec(2.0, 7.5, (Rival(pos=ahead(3.0)), FAR))]).s1.match
    t = 100
    assert effect.read_outcome(match, t, 1) == effect.Outcome(7.5, True)
    assert power.ball_advance(match, t, 1, W) == 2.0
    assert pressure.incoming_ball(match, t, 1, 0.0) == "lateral/middle/short"
    after = dataclasses.replace(match, ball_period=np.where(match.ball_frame > t, 2, 1))
    assert effect.read_outcome(after, t, 1) is None
    assert power.ball_advance(after, t, 1, W) == 2.0  # [t - W, t] is still one period
    before = dataclasses.replace(match, ball_period=np.where(match.ball_frame < t, 1, 2))
    assert effect.read_outcome(before, t, 1) == effect.Outcome(7.5, True)
    assert power.ball_advance(before, t, 1, W) is None
    assert pressure.incoming_ball(before, t, 1, 0.0) == "undefined"


def test_effect_units_keep_the_kept_units_with_their_outcome() -> None:
    specs = [
        Spec(float(i), 3.0 * i, (Rival(pos=ahead(3.0 + i)), Rival(pos=(-30.0, 0.0))))
        for i in range(1, 4)
    ]
    inputs = tracking_match(9, specs)
    units = design.design_units(inputs)
    units[1] = dataclasses.replace(units[1], excluded=True)  # dropped by the overlap rule
    units[2] = dataclasses.replace(units[2], frame=units[2].frame + 1)  # no ball row at t + W
    got = effect.effect_units(units, inputs.s1.match)
    assert [u.match for u in got] == [9, 9]
    assert [u.frame for u in got] == [100, 181]
    assert [u.outcome for u in got] == [3.0, None]
    assert [u.ball_detected for u in got] == [True, None]
    assert [u.pre for u in got] == [units[0].pre, units[2].pre] == [1.0, 3.0]
    assert [u.pressed for u in got] == [units[0].pressed, units[2].pressed]


def test_a_mirrored_pitch_in_the_second_period_gives_the_same_outcomes() -> None:
    # The carrier's team attacking -x in period 2 (+x in period 1): every x flipped, the period
    # changed. The outcome must take the sign of the unit's own period, forward or backward.
    inputs = tracking_match(
        5, [Spec(2.0, out, (Rival(pos=ahead(3.0)), FAR)) for out in (7.5, -4.0)]
    )
    m = inputs.s1.match
    mirrored = dataclasses.replace(
        m,
        x=-m.x,
        ball_x=-m.ball_x,
        period=np.full_like(m.period, 2),
        ball_period=np.full_like(m.ball_period, 2),
        attack_sign={
            **m.attack_sign,
            **{(2, team): -sign for (_, team), sign in m.attack_sign.items()},
        },
    )
    s1 = dataclasses.replace(
        inputs.s1,
        match=mirrored,
        receptions=tuple(dataclasses.replace(r, period=2) for r in inputs.s1.receptions),
    )
    want = effect.effect_units(design.design_units(inputs), m)
    got = effect.effect_units(design.design_units(dataclasses.replace(inputs, s1=s1)), mirrored)
    assert [u.outcome for u in want] == [7.5, -4.0]
    assert [dataclasses.replace(u, period=1) for u in got] == want


def test_the_variants_select_by_their_definition() -> None:
    units = [
        mk(1, "s", True, 0.0, 1.0, 0, extra=0),
        mk(1, "s", True, 0.0, 1.0, 1, extra=1, ball=False),
        mk(1, "s", False, 0.0, None, 2, extra=0),
        mk(1, "s", False, 0.0, 1.0, 3, extra=2),
    ]
    assert len(effect.select_units(units, "V0")) == 4
    assert [u.frame for u in effect.select_units(units, "V1")] == [100, 180]
    assert [u.frame for u in effect.select_units(units, effect.BALL_DETECTED)] == [100, 220]
    with pytest.raises(ValueError, match="unknown variant"):
        effect.select_units(units, "V2")


# --- the statistic -----------------------------------------------------------------------------


def test_a_flat_x_cell_is_the_plain_difference_by_hand() -> None:
    # Pressed 3..7 against free 1..5, x constant: tau is the difference of means (2), s the sample
    # sd of the ten values (sum of squares 30 over 9: ddof 1), z = tau / s and w = 25 / 10.
    pressed = [(1.0, float(y)) for y in range(3, 8)]
    free = [(1.0, float(y)) for y in range(1, 6)]
    got = effect.estimate(cell(1, "a", pressed, free))
    (c,) = got.cells
    assert (c.n_pressed, c.n_free, c.b) == (5, 5, 0.0)
    assert c.tau == pytest.approx(2.0)
    assert c.s == pytest.approx(math.sqrt(30 / 9))  # a ddof 0 sd would be sqrt(30 / 10)
    assert c.z == pytest.approx(2.0 / math.sqrt(30 / 9))
    assert c.w == pytest.approx(2.5)
    assert got.t == pytest.approx(c.z) and got.matches[1].effect == pytest.approx(c.z)
    assert got.pretrend is None and got.pretrend_m is None  # x is constant: no pre-trend


def test_the_coefficient_adjusts_for_what_came_before() -> None:
    # y = 1 + 2 x + 3 G without noise; the pressed received 1 m more forward ball. The
    # coefficient is 3 and the slope 2, the plain difference would be 3 + 2 * 1 = 5.
    xs_p, xs_f = [1.0, 2.0, 3.0, 4.0, 5.0], [0.0, 1.0, 2.0, 3.0, 4.0]
    pressed = [(x, 1 + 2 * x + 3) for x in xs_p]
    free = [(x, 1 + 2 * x) for x in xs_f]
    got = effect.estimate(cell(1, "a", pressed, free))
    (c,) = got.cells
    assert c.tau == pytest.approx(3.0) and c.b == pytest.approx(2.0)
    plain = np.mean([y for _, y in pressed]) - np.mean([y for _, y in free])
    assert plain == pytest.approx(5.0)
    # The pre-trend: a difference of 1 m over the sd of x (22.5 over 9 is its variance).
    assert c.x_diff == pytest.approx(1.0) and c.sd_x == pytest.approx(math.sqrt(2.5))
    assert c.pretrend == pytest.approx(1.0 / math.sqrt(2.5))
    assert got.pretrend == pytest.approx(c.pretrend) and got.pretrend_m == pytest.approx(1.0)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_statistic_agrees_with_lstsq(seed: int) -> None:
    units = random_cells(seed)
    got, want = effect.estimate(units), reference(units)
    assert len(got.cells) == len(want["rows"])  # type: ignore[arg-type]
    for c, (m, s, tau, b, sd, w) in zip(got.cells, want["rows"], strict=True):  # type: ignore[arg-type]
        assert (c.match, c.stratum) == (m, s)
        assert c.tau == pytest.approx(tau, abs=1e-9) and c.b == pytest.approx(b, abs=1e-9)
        assert c.s == pytest.approx(sd) and c.w == pytest.approx(w)
        assert c.z == pytest.approx(tau / sd, abs=1e-9)
    assert got.t == pytest.approx(want["t"], abs=1e-9)  # type: ignore[arg-type]
    for m, e in want["by_match"].items():  # type: ignore[attr-defined]
        assert got.matches[m].effect == pytest.approx(e, abs=1e-9)


def test_cells_need_both_groups_a_spread_and_an_identified_coefficient() -> None:
    ok = cell(
        1,
        "ok",
        [(float(i), float(i % 3)) for i in range(6)],
        [(i + 0.5, 1.0 * (i % 4)) for i in range(6)],
    )
    small = cell(
        1,
        "small",
        [(float(i), float(i)) for i in range(4)],
        [(float(i), float(i)) for i in range(6)],
    )
    flat = cell(
        1, "flat", [(float(i), 2.0) for i in range(5)], [(float(i + 1), 2.0) for i in range(5)]
    )
    # x = G exactly: the coefficient of G cannot be told from the slope of x.
    collinear = cell(
        1, "collinear", [(1.0, float(i)) for i in range(5)], [(0.0, float(i + 1)) for i in range(5)]
    )
    lonely = cell(
        2,
        "small",
        [(float(i), float(i)) for i in range(3)],
        [(float(i), float(i)) for i in range(7)],
    )
    shifted = [
        dataclasses.replace(u, frame=u.frame + 4000 * j)
        for j, us in enumerate([ok, small, flat, collinear, lonely])
        for u in us
    ]
    extra = [
        mk(1, "ok", True, 1.0, None, 90),  # no outcome
        mk(1, "ok", False, None, 3.0, 91),  # outcome but no pre statistic
        mk(2, "none", False, None, None, 92),  # neither: counted once, as no outcome
    ]
    got = effect.estimate([*shifted, *extra])
    assert [(c.match, c.stratum) for c in got.cells] == [(1, "ok")]
    assert (got.units, got.used) == (len(shifted) + 3, 12)
    assert got.left_out["no_outcome"] == {"pressed": 1, "free": 1}
    assert got.left_out["no_pre"] == {"pressed": 0, "free": 1}
    assert got.left_out["small_cell"] == {"pressed": 4 + 3, "free": 6 + 7}
    assert got.left_out["flat_outcome"] == {"pressed": 5, "free": 5}
    assert got.left_out["collinear_cell"] == {"pressed": 5, "free": 5}
    # The same counts per match; match 2 has no cell: no effect, and it never agrees.
    assert got.matches[2].effect is None and got.matches[2].cells == 0
    assert got.matches[2].left_out["small_cell"] == {"pressed": 3, "free": 7}
    assert got.matches[1].used == 12 and got.matches[1].cells == 1
    assert effect.sign_agreement(got) == 1  # only match 1 can agree with T


def test_no_cell_means_no_effect() -> None:
    got = effect.estimate(cell(1, "a", [(0.0, 1.0)] * 3, [(0.0, 2.0)] * 3))
    assert got.t is None and got.cells == () and got.pretrend is None and got.weight == 0.0
    assert effect.estimate([]).t is None
    result = effect.permutation_test(
        cell(1, "a", [(0.0, 1.0)] * 3, [(0.0, 2.0)] * 3), "calibration", "V0", draws=20
    )
    assert result.p is None and result.extreme is None
    assert not effect.calibration_bar(result).passed
    assert effect.d3(got).kills and not effect.d3(got).evaluable
    assert effect.d4(got, got).kills and not effect.d4(got, got).evaluable


def test_t_zero_never_passes() -> None:
    # Pressed and free have the same outcomes, x is constant: tau is exactly 0 in the one cell.
    same = [(1.0, float(y)) for y in range(5)]
    got = effect.estimate(cell(1, "a", same, same))
    assert got.t == 0.0 and got.matches[1].effect == 0.0
    assert effect.sign_agreement(got) == 0  # a match whose effect is 0 does not "agree" with 0
    fake = effect.Result("calibration", "V0", False, 2000, got, 0, 1 / 2001)
    bar_ = effect.calibration_bar(fake)
    assert not bar_.sign_ok and not bar_.passed and bar_.p_ok


def test_the_pretrend_by_hand() -> None:
    # Match 1: x pressed 2..6 against free 0..4 (+2 m; sd of the ten values sqrt(25/9 * ...)).
    one = cell(
        1,
        "a",
        [(float(v), float(v % 2)) for v in range(2, 7)],
        [(float(v), float(v % 3)) for v in range(5)],
    )
    # Match 2: a cell with constant x (left out of P, in T) and one with x 0..9 against 1..10.
    flat = cell(
        2, "flat", [(5.0, float(v)) for v in range(5)], [(5.0, float(v + 1)) for v in range(5)]
    )
    wide = cell(
        2,
        "wide",
        [(float(v), float(v % 4)) for v in range(10)],
        [(float(v), float(v % 5)) for v in range(1, 11)],
    )
    units = [
        dataclasses.replace(u, frame=u.frame + 4000 * j)
        for j, us in enumerate([one, flat, wide])
        for u in us
    ]
    got = effect.estimate(units)
    s1 = float(np.std([2, 3, 4, 5, 6, 0, 1, 2, 3, 4], ddof=1))
    s2 = float(np.std([*range(10), *range(1, 11)], ddof=1))
    w1, w2 = 2.5, 5.0
    assert len(got.cells) == 3
    assert got.pretrend == pytest.approx((w1 * 2 / s1 + w2 * -1 / s2) / (w1 + w2))
    assert got.pretrend_m == pytest.approx((w1 * 2 + w2 * -1) / (w1 + w2))
    assert got.matches[1].pretrend == pytest.approx(2 / s1)
    assert got.matches[1].pretrend_m == pytest.approx(2.0)
    assert got.matches[2].pretrend == pytest.approx(-1 / s2)  # the flat cell is not in it
    assert got.matches[2].cells == 2
    assert [c.pretrend is None for c in got.cells] == [False, True, False]
    # T does use the flat cell: its weight is in the match's effect and in the pooled one.
    assert got.weight == pytest.approx(w1 + 2.5 + w2)
    (flat_cell,) = [c for c in got.cells if c.stratum == "flat"]
    assert flat_cell.z == pytest.approx(-1.0 / flat_cell.s)  # plain difference: 0..4 against 1..5


@pytest.mark.parametrize("seed", SEEDS)
def test_the_pretrend_agrees_with_the_design_module(seed: int) -> None:
    # design.pooled_pretrend (task 19) is another implementation of the same pooling.
    units = random_cells(seed)
    by_match: dict[int, list[power.Unit]] = {}
    for u in units:
        by_match.setdefault(u.match, []).append(
            power.Unit(u.frame, u.stratum, u.pressed, u.possession, u.pre, True)
        )
    want = design.pooled_pretrend(by_match, "V0")
    got = effect.estimate(units)
    assert got.pretrend == pytest.approx(want["sd"]) and got.pretrend_m == pytest.approx(
        want["metres"]
    )
    for m, e in got.matches.items():
        assert e.pretrend == pytest.approx(want["matches"][str(m)]["sd"])  # type: ignore[index]


# --- the null ----------------------------------------------------------------------------------


def test_the_p_value_formula() -> None:
    null = np.array([0.5, -1.2, 0.3, 1.0, -2.0])
    assert effect.extreme_draws(1.0, null) == 3  # |-1.2|, |1.0| (a tie counts), |-2.0|
    assert effect.p_value(1.0, null) == pytest.approx(4 / 6)
    assert effect.p_value(-1.0, null) == pytest.approx(4 / 6)  # two-sided
    assert effect.p_value(5.0, null) == pytest.approx(1 / 6)  # the observed one is never absent
    assert effect.p_value(0.0, null) == 1.0
    assert effect.p_value(1.0 + 1e-12, null) == pytest.approx(4 / 6)  # float noise is not a gap
    assert effect.p_value(1.0 + 1e-6, null) == pytest.approx(3 / 6)


def small_cell() -> list[EffectUnit]:
    rng = np.random.default_rng(3)
    g = np.array([True] * 7 + [False] * 9)
    y = rng.normal(0, 1, 16) + 0.5 * g
    return [mk(1, "a", bool(g[i]), 1.0, float(y[i]), i) for i in range(16)]


def test_the_stream_is_the_protocols() -> None:
    units = small_cell()
    y = np.array([u.outcome for u in units])
    g = np.array([u.pressed for u in units])
    s = np.std(y, ddof=1)
    for half, variant in [("calibration", "V0"), ("heldout", "V1"), ("calibration", "V1")]:
        rng = np.random.default_rng([19, zlib.crc32(f"{half}/{variant}".encode())])
        # 600 draws are three chunks of the code; the stream is the same as one call of 600 rows.
        labels = g[np.argsort(rng.random((600, 16)), axis=1)]
        tau = (labels * y).sum(axis=1) / 7 - ((1 - labels) * y).sum(axis=1) / 9
        got = effect.null_effects(units, half, variant, draws=600)
        assert got.matches == (1,)
        assert got.pooled == pytest.approx(tau / s, abs=1e-9)
        assert got.match[:, 0] == pytest.approx(got.pooled)  # one match: E* is T*
    a = effect.null_effects(units, "calibration", "V0", draws=50).pooled
    for other in (("heldout", "V0"), ("calibration", "V1")):
        assert not np.allclose(a, effect.null_effects(units, *other, draws=50).pooled)
    assert np.array_equal(a, effect.null_effects(units, "calibration", "V0", draws=50).pooled)
    assert effect.SEED == 19
    with pytest.raises(ValueError, match="unknown half"):
        effect.null_effects(units, "train", "V0", draws=5)
    with pytest.raises(ValueError, match="no null for variant"):
        effect.null_effects(units, "calibration", effect.BALL_DETECTED, draws=5)


def test_the_draws_do_not_depend_on_the_order_of_units() -> None:
    units = random_cells(1)
    shuffled = list(np.random.default_rng(0).permutation(np.array(units, dtype=object)))
    for blocked in (False, True):
        a = effect.null_effects(units, "heldout", "V0", blocked, draws=40)
        b = effect.null_effects(shuffled, "heldout", "V0", blocked, draws=40)
        assert np.array_equal(a.pooled, b.pooled) and np.array_equal(a.match, b.match)


def unequal_cells() -> list[EffectUnit]:
    """Two cells with very different levels and group sizes (5 against 15, 15 against 5)."""
    rng = np.random.default_rng(8)
    units: list[EffectUnit] = []
    for m, (level, n_p) in enumerate([(100.0, 5), (0.0, 15)]):
        for i in range(20):
            units.append(mk(1, f"c{m}", i < n_p, 0.0, float(level + rng.normal(0, 1)), 100 * m + i))
    return units


def test_the_null_permutes_inside_the_cell() -> None:
    # With x constant, T* has mean 0 and variance 1 / sum(w) exactly when the labels move inside
    # a cell (the permutation variance of a difference of means is s^2 (1/n_p + 1/n_f)); labels
    # moved across the two cells (whose sizes of group differ) give another variance.
    units = unequal_cells()
    observed = effect.estimate(units)
    assert observed.weight == pytest.approx(2 * 5 * 15 / 20)
    null = effect.null_effects(units, "calibration", "V0", draws=bar.N_PERMUTATIONS).pooled
    assert abs(null.mean()) < 4 / math.sqrt(observed.weight * bar.N_PERMUTATIONS)
    assert null.var() == pytest.approx(1 / observed.weight, rel=0.12)


def test_the_null_recomputes_tau_with_the_covariate() -> None:
    # The adjusted statistic is recomputed on every draw: with a planted x that explains y, the
    # null is narrower than the plain-difference null of the same labels.
    rng = np.random.default_rng(4)
    x = rng.normal(0, 1, 40)
    y = 3 * x + rng.normal(0, 0.3, 40)
    g = np.arange(40) < 16
    adjusted = [mk(1, "a", bool(g[i]), float(x[i]), float(y[i]), i) for i in range(40)]
    plain = [dataclasses.replace(u, pre=1.0) for u in adjusted]
    narrow = effect.null_effects(adjusted, "calibration", "V0", draws=1000).pooled
    wide = effect.null_effects(plain, "calibration", "V0", draws=1000).pooled
    assert narrow.std() < 0.5 * wide.std()


def test_the_blocked_contributions_add_up_to_t() -> None:
    for seed in SEEDS:
        units = [
            dataclasses.replace(u, possession=f"q{u.frame // 120}") for u in random_cells(seed)
        ]
        s = effect.possession_contributions(units)
        assert sum(s.values()) == pytest.approx(effect.estimate(units).t, abs=1e-9)  # type: ignore[arg-type]
        assert {k[0] for k in s} == {1, 2, 3}
        # Match by match: the contributions of one match add to its share of T.
        e = effect.estimate(units)
        for m in (1, 2, 3):
            share = sum(v for k, v in s.items() if k[0] == m)
            weight = sum(c.w for c in e.cells if c.match == m)
            assert share == pytest.approx(e.matches[m].effect * weight / e.weight, abs=1e-9)  # type: ignore[operator]
    # A cell with a constant x uses the plain difference's contributions.
    flat = small_cell()
    assert sum(effect.possession_contributions(flat).values()) == pytest.approx(
        effect.estimate(flat).t
    )  # type: ignore[arg-type]
    assert effect.possession_contributions([]) == {}


def test_the_blocked_null_flips_each_possession() -> None:
    units = [dataclasses.replace(u, possession=f"q{u.frame // 200}") for u in random_cells(2)]
    s = np.array(list(effect.possession_contributions(units).values()))
    got = effect.null_effects(units, "calibration", "V0", blocked=True, draws=bar.N_PERMUTATIONS)
    assert got.pooled.shape == (bar.N_PERMUTATIONS,) and got.match.shape == (bar.N_PERMUTATIONS, 3)
    assert got.pooled.var() == pytest.approx((s**2).sum(), rel=0.12)  # exact variance of a flip
    assert np.all(np.abs(got.pooled) <= np.abs(s).sum() + 1e-9)
    # T* is the weighted mean of the E*_m, as T is of the E_m.
    e = effect.estimate(units)
    weights = np.array([sum(c.w for c in e.cells if c.match == m) for m in got.matches])
    assert (got.match @ weights) / e.weight == pytest.approx(got.pooled, abs=1e-9)
    # One possession holding every unit: T* is +T or -T, so every draw is as extreme as T.
    one = [dataclasses.replace(u, possession="all") for u in small_cell()]
    r = effect.permutation_test(one, "calibration", "V0", blocked=True, draws=100)
    assert r.p == 1.0 and r.extreme == 100 and r.blocked


# --- the bars and the criteria ----------------------------------------------------------------


def fake_effect(
    t: float | None, matches: Sequence[float | None], pre: float | None = 0.0
) -> effect.Effect:
    return effect.Effect(
        t=t,
        weight=1.0,
        pretrend=pre,
        pretrend_m=None,
        cells=(),
        matches={
            i: effect.MatchEffect(i, e, None, None, 1, 0, 0, {}) for i, e in enumerate(matches)
        },
        units=0,
        used=0,
        left_out={},
    )


def fake_result(
    variant: str, t: float | None, matches: Sequence[float | None], p: float | None
) -> effect.Result:
    return effect.Result("calibration", variant, False, 2000, fake_effect(t, matches), None, p)


def test_the_calibration_bar_by_hand() -> None:
    eight = [-1.0] * 8 + [1.0, None]
    seven = [-1.0] * 7 + [1.0, 1.0, None]
    pass_p = bar.BAR_COUNT_AT_MOST + 1  # draws as extreme, plus the observed one
    assert pass_p / 2001 <= bar.BAR_P < (pass_p + 1) / 2001
    ok = effect.calibration_bar(fake_result("V0", -0.3, eight, pass_p / 2001))
    assert (ok.agreeing, ok.matches, ok.sign_ok, ok.p_ok, ok.passed) == (8, 10, True, True, True)
    assert not effect.calibration_bar(fake_result("V0", -0.3, seven, 1 / 2001)).passed  # 7 of 10
    assert not effect.calibration_bar(fake_result("V0", -0.3, eight, (pass_p + 1) / 2001)).passed
    assert not effect.calibration_bar(fake_result("V0", -0.3, eight, None)).passed
    # The sign is the pooled effect's: eight matches of the other sign do not agree with it.
    assert not effect.calibration_bar(fake_result("V0", 0.3, eight, 1 / 2001)).passed
    assert effect.calibration_bar(fake_result("V0", 0.3, [1.0] * 8 + [-1.0] * 2, 1 / 2001)).passed


def test_holm_by_hand() -> None:
    assert effect.holm({"V0": 0.004, "V1": 0.009}, 0.01) == {"V0": True, "V1": True}
    assert effect.holm({"V0": 0.009, "V1": 0.004}, 0.01) == {"V0": True, "V1": True}
    assert effect.holm({"V0": 0.006, "V1": 0.009}, 0.01) == {"V0": False, "V1": False}
    assert effect.holm({"V0": 0.004, "V1": 0.011}, 0.01) == {"V0": True, "V1": False}
    assert effect.holm({"V0": 0.005, "V1": 0.5}, 0.01) == {"V0": True, "V1": False}  # at alpha / 2
    assert effect.holm({"V0": 0.004, "V1": None}, 0.01) == {"V0": True, "V1": False}
    assert effect.holm({"V0": None, "V1": None}, 0.01) == {"V0": False, "V1": False}
    assert effect.holm({"a": 0.001, "b": 0.01, "c": 0.04}, 0.05) == {
        "a": True,
        "b": True,
        "c": True,
    }
    assert effect.holm({"a": 0.001, "b": 0.03, "c": 0.04}, 0.05) == {
        "a": True,
        "b": False,
        "c": False,
    }
    assert effect.HELDOUT_ALPHA == 0.01


def test_the_heldout_bars_need_sign_and_holm() -> None:
    eight = [-1.0] * 8 + [1.0, 1.0]
    both = effect.heldout_bars(
        {"V0": fake_result("V0", -0.3, eight, 0.004), "V1": fake_result("V1", -0.3, eight, 0.009)}
    )
    assert both["V0"].passed and both["V1"].passed
    mixed = effect.heldout_bars(
        {"V0": fake_result("V0", -0.3, eight, 0.004), "V1": fake_result("V1", -0.3, eight, 0.02)}
    )
    assert mixed["V0"].passed and not mixed["V1"].passed and mixed["V1"].sign_ok
    seven = effect.heldout_bars(
        {
            "V0": fake_result("V0", -0.3, [-1.0] * 7 + [1.0] * 3, 0.001),
            "V1": fake_result("V1", -0.3, eight, 0.001),
        }
    )
    assert not seven["V0"].passed and seven["V0"].p_ok and seven["V1"].passed
    with pytest.raises(ValueError, match="Holm family"):
        effect.heldout_bars({"V0": fake_result("V0", -0.3, eight, 0.001)})


def test_d3_by_hand() -> None:
    kills = effect.d3(fake_effect(-0.30, [], pre=0.15))  # exactly half: the rule is >=
    assert kills.kills and kills.evaluable and kills.values["floor"] == pytest.approx(0.30)
    assert not effect.d3(fake_effect(-0.30, [], pre=0.1499)).kills
    assert effect.d3(fake_effect(0.30, [], pre=-0.2)).kills  # absolute values
    assert not effect.d3(fake_effect(-0.5, [], pre=0.0)).kills
    assert effect.d3(fake_effect(-0.5, [], pre=None)).kills  # no pre-trend to show it is small


def test_d4_by_hand() -> None:
    v0 = fake_effect(-0.40, [])
    assert not effect.d4(v0, fake_effect(-0.20, [])).kills  # exactly half survives
    assert effect.d4(v0, fake_effect(-0.1999, [])).kills
    assert effect.d4(v0, fake_effect(0.40, [])).kills  # sign change
    assert effect.d4(v0, fake_effect(0.0, [])).kills
    assert not effect.d4(v0, fake_effect(-0.9, [])).kills  # larger in V1 is no death
    assert effect.d4(v0, fake_effect(None, [])).kills


def test_v2_classes_by_hand() -> None:
    def block(extra: int, gain: float, start: int) -> list[EffectUnit]:
        pressed = [(1.0, 10.0 + gain + (i % 3)) for i in range(6)]
        free = [(1.0, 10.0 + (i % 3)) for i in range(6)]
        return [
            dataclasses.replace(u, extrapolated_players=extra, frame=u.frame + start)
            for u in cell(1, "a", pressed, free)
        ]

    shrinking = [
        *block(0, -4.0, 0),
        *block(1, -2.0, 4000),
        *block(3, -1.0, 8000),
        *block(2, -0.5, 12000),
    ]
    got = effect.v2_effects(shrinking)
    assert set(got.classes) == set(effect.V2_CLASSES)
    assert got.classes["2_or_more"].used == 24  # three and two extrapolated players: 2 or more
    a = got.abs_effect
    assert a["0"] is not None and a["1"] is not None and a["2_or_more"] is not None
    assert a["0"] > a["1"] > a["2_or_more"] and got.shrinks is True
    growing = [*block(0, -1.0, 0), *block(1, -2.0, 4000)]
    assert effect.v2_effects(growing).shrinks is False
    alone = effect.v2_effects(block(0, -1.0, 0))
    assert alone.shrinks is None and alone.abs_effect["1"] is None and alone.classes["1"].t is None


# --- a planted effect is recovered (a) ----------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_a_planted_effect_is_recovered(seed: int) -> None:
    # tau = -0.5 sd of the noise; the cell's sd includes the effect (1 + 0.25 * 0.4 * 0.6).
    planted = -0.5 / math.sqrt(1 + 0.25 * 0.4 * 0.6)
    units = planted_units(seed, tau=-0.5)
    result = effect.permutation_test(units, "calibration", "V0")
    assert result.effect.t == pytest.approx(planted, abs=0.08)  # sd of T is about 0.04
    assert len(result.effect.cells) == 30 and result.effect.used == 2700
    assert abs(result.effect.pretrend or 0.0) < 0.1  # nothing planted before t
    bar_ = effect.calibration_bar(result)
    assert bar_.agreeing >= 9 and bar_.passed
    assert not effect.d3(result.effect).kills


@pytest.mark.parametrize("seed", SEEDS)
def test_a_null_world_is_not_found(seed: int) -> None:
    result = effect.permutation_test(planted_units(seed, tau=0.0), "calibration", "V0")
    assert abs(result.effect.t or 0.0) < 0.1
    assert result.p is not None and result.p > 0.05
    assert not effect.calibration_bar(result).passed


# --- a planted pre-trend is caught by D3 (b) ----------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_a_planted_pretrend_is_caught_by_d3(seed: int) -> None:
    # The pressed receive 0.8 more forward ball and the outcome keeps 0.6 of it: no effect of
    # pressure, a plain difference of 0.6 * 0.8 / sd(y). The pre-trend is 0.8 / sd(x) in sd.
    units = planted_units(seed, persistence=0.6, shift=0.8)
    result = effect.permutation_test(units, "calibration", "V0")
    got = result.effect
    assert got.pretrend == pytest.approx(0.8 / math.sqrt(1 + 0.64 * 0.24), abs=0.06)
    crit = effect.d3(got)
    assert crit.kills and crit.evaluable
    # The covariate removes the bias: the plain difference is a third of an sd, the coefficient 0.
    plain = plain_difference(units)
    assert plain > 0.3
    assert abs(got.t or 0.0) < 0.25 * plain
    assert not effect.calibration_bar(result).passed
    # The plain difference alone would have been read as an effect of the wrong sign; D3 sees it.
    assert abs(got.pretrend or 0.0) >= power.D3_RATIO * plain


@pytest.mark.parametrize("seed", SEEDS)
def test_a_real_effect_with_no_pretrend_survives_d3(seed: int) -> None:
    units = planted_units(seed, tau=-0.5, persistence=0.6, shift=0.0)
    got = effect.permutation_test(units, "calibration", "V0").effect
    assert not effect.d3(got).kills
    assert got.t == pytest.approx(planted_z(-0.5, 0.6, 0.0), abs=0.1)


@pytest.mark.parametrize("seed", SEEDS)
def test_a_real_effect_riding_on_a_small_pretrend_is_adjusted(seed: int) -> None:
    # Persistence and a pre-trend of 0.15 plus a true effect: the coefficient still finds tau.
    units = planted_units(seed, tau=-0.8, persistence=0.6, shift=0.15)
    got = effect.estimate(units)
    assert got.t == pytest.approx(planted_z(-0.8, 0.6, 0.15), abs=0.1)
    assert abs(plain_difference(units) - got.t) > 0.03  # the plain difference is moved by it
    assert not effect.d3(got).kills


# --- a confounder the strata cancel (c), through the real pipeline -----------------------------


@functools.cache
def confounded_units(seed: int) -> tuple[EffectUnit, ...]:
    return tuple(through_the_pipeline(confounded_world(seed)))


@pytest.mark.parametrize("seed", SEEDS)
def test_the_confounded_world_has_the_five_strata(seed: int) -> None:
    cells = effect.estimate(list(confounded_units(seed))).cells
    assert len(cells) >= 45  # five strata in each of ten matches
    assert {u.stratum for u in confounded_units(seed)} == {
        "backward/middle/long",
        "backward/middle/short",
        "lateral/middle/short",
        "forward/middle/short",
        "forward/middle/long",
    }


@pytest.mark.parametrize("seed", SEEDS)
def test_the_strata_cancel_the_confounder(seed: int) -> None:
    # Pressure comes with a forward incoming ball and the outgoing ball keeps going forward;
    # pressure itself does nothing. Within the incoming-ball stratum there is no effect.
    units = list(confounded_units(seed))
    result = effect.permutation_test(units, "calibration", "V0")
    assert abs(result.effect.t or 0.0) < 0.1
    assert not effect.calibration_bar(result).passed


@pytest.mark.parametrize("seed", SEEDS)
def test_the_confounder_is_real_without_the_strata(seed: int) -> None:
    # The mutation 'no strata', made here on the same units: the bar passes on a spurious
    # effect, so the previous test is not passing for want of a confounder.
    units = collapse_strata(confounded_units(seed))
    result = effect.permutation_test(units, "calibration", "V0")
    assert (result.effect.t or 0.0) > 0.12
    assert effect.calibration_bar(result).passed
    assert (result.effect.pretrend or 0.0) > 0.5  # the pressed got more forward ball: D3 sees it


# --- interpolated players (d), through the real pipeline ---------------------------------------


@functools.cache
def extrapolated_units(seed: int) -> tuple[EffectUnit, ...]:
    return tuple(through_the_pipeline(extrapolated_world(seed)))


@pytest.mark.parametrize("seed", SEEDS)
def test_interpolated_players_have_zero_residual(seed: int) -> None:
    match = extrapolated_world(seed, matches=1)[1].s1.match
    accel, centre = runs.second_differences(match)  # layer 2's residual of a row
    listed = centre & ~match.detected
    assert listed.sum() > 1000
    assert np.nanmax(accel[listed]) < 1e-9  # a straight line between two detections
    seen = centre & match.detected
    assert np.nanmax(accel[seen]) > 0.1  # the measure is not blind: detected stretches kink


@pytest.mark.parametrize("seed", SEEDS)
def test_extrapolation_attenuates_the_effect_and_v2_shrinks(seed: int) -> None:
    units = list(extrapolated_units(seed))
    classes = [u.extrapolated_players for u in units]
    assert min(classes) == 0 and max(classes) == 2
    v2 = effect.v2_effects(units)
    assert all(len(e.cells) >= 8 for e in v2.classes.values())  # every class has its cells
    a = v2.abs_effect
    assert a["0"] is not None and a["1"] is not None and a["2_or_more"] is not None
    assert a["0"] > 2 * a["1"] > 4 * a["2_or_more"]
    assert v2.shrinks is True
    # V0 mixes the classes, so it is attenuated against V1 (the detected units alone).
    v0 = effect.estimate(effect.select_units(units, "V0")).t
    v1 = effect.estimate(effect.select_units(units, "V1")).t
    assert v0 is not None and v1 is not None
    assert v1 < v0 < 0 and abs(v0) < 0.8 * abs(v1)
    assert v2.classes["0"].t == pytest.approx(v1, abs=1e-9)
    # Attenuation, not a model artefact: D4 does not kill (V1 keeps more than half of V0).
    assert not effect.d4(
        effect.estimate(units), effect.estimate(effect.select_units(units, "V1"))
    ).kills


# --- the cause read at t + 1 s (the mutation of the plan) --------------------------------------


@functools.cache
def reverse_units(seed: int) -> tuple[EffectUnit, ...]:
    return tuple(through_the_pipeline(reverse_world(seed)))


@pytest.mark.parametrize("seed", SEEDS)
def test_a_cause_read_at_t_finds_no_effect_in_reverse_causation(seed: int) -> None:
    # The defenders close in after the ball failed to advance. At t nothing has happened.
    result = effect.permutation_test(list(reverse_units(seed)), "calibration", "V0")
    assert result.effect.t is not None and len(result.effect.cells) >= 10
    assert abs(result.effect.t or 0.0) < 0.15
    assert abs(result.effect.pretrend or 0.0) < 0.15
    assert not effect.calibration_bar(result).passed


@pytest.mark.parametrize("seed", SEEDS)
def test_the_cause_read_a_second_late_passes_the_bar_and_the_pretrend(seed: int) -> None:
    # The mutation, made here with the real reader: the index LATE (10) frames after t. It
    # 'finds' a large effect, and the pre-trend [t - W, t] cannot tell: D3 lets it through.
    units = cause_read_late(reverse_world(seed))
    result = effect.permutation_test(units, "calibration", "V0")
    assert (result.effect.t or 0.0) < -1.0
    bar_ = effect.calibration_bar(result)
    assert bar_.passed and bar_.agreeing == 10
    crit = effect.d3(result.effect)
    assert not crit.kills  # |P| is far below half of |T|
    assert abs(result.effect.pretrend or 0.0) < 0.2 * abs(result.effect.t or 0.0)
    assert LATE == 10


# --- the whole thing on a planted world, end to end --------------------------------------------


def test_the_variants_of_a_planted_world_run_end_to_end() -> None:
    units = planted_units(0, tau=-0.5)
    results = {v: effect.permutation_test(units, "heldout", v) for v in effect.VARIANTS}
    bars = effect.heldout_bars(results)
    assert bars["V0"].passed and bars["V1"].passed
    assert effect.d4(results["V0"].effect, results["V1"].effect).kills is False
    assert effect.v2_effects(units).classes["0"].t == pytest.approx(results["V1"].effect.t)
