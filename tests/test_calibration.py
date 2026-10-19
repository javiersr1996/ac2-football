"""Task 21 on hand-made halves: the calibration report, its criteria and the variance factor.

Every expected number is planted here; no real match is read. The halves come out of the real
pipeline (``tracking_match`` of the effect helpers, then ``design``, ``effect`` and ``power``):
ten matches, one rival straight ahead of the carrier at ``d`` metres, pressed at 5 m or closer,
the ball leaving with noise of sd 2 m plus the planted effect when pressed. Mutations, each
annotated with the test that kills it:

* a variance factor without the square, without the cell weight, or weighted by ``n``:
  ``test_variance_factor_by_hand``;
* D1 judged on fewer matches than a half, or on 8 of 10: ``test_d1_needs_enough_matches_of_a_half``;
  D5 that ignores D1: ``test_levels_unrelated_to_the_index_kill_by_d1``;
* D2 with ``>=``, or that lets a missing MDE80 through: ``test_d2_kills_above_the_limit_only``;
* D5 that ignores the bar or a criterion: ``test_d5_by_hand``;
* the null on the held-out stream: ``test_no_effect_dies_by_d5``; blocked against the rule:
  ``test_a_planted_effect_passes_the_calibration``; never blocked:
  ``test_a_correlated_possession_blocks_the_null``; V1's null drawn on V0's units:
  ``test_the_v1_null_permutes_only_the_v1_units``;
* D3 or D4 left out of the verdict: ``test_a_pretrend_kills_by_d3``,
  ``test_an_effect_in_extrapolated_rivals_kills_by_d4``;
* D2 fed V1's MDE80 instead of V0's: ``test_a_small_half_dies_by_d2``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest
from effect_helpers import FAR, Rival, Spec, ahead, tracking_match

from ac2fb.defence import bar, calibration, design, effect, power
from ac2fb.reliability.report import render_report


def with_levels(inputs: power.C1Inputs, distances: list[float]) -> power.C1Inputs:
    """The provider's level grows as the rival comes closer: 5 under 2.8 m, 1 from 8.2 m."""
    receptions = tuple(
        dataclasses.replace(r, level=5 - min(4, int((d - 1.0) / 1.8)))
        for r, d in zip(inputs.s1.receptions, distances, strict=True)
    )
    return power.C1Inputs(dataclasses.replace(inputs.s1, receptions=receptions), inputs.possessions)


def half(
    seed: int,
    *,
    effect_m: float = -1.0,
    n: int = 200,
    graded: bool = True,
    shift: bool = False,
    unseen_only: bool = False,
    paired: bool = False,
) -> dict[int, power.C1Inputs]:
    """Ten matches of ``n`` receptions with the rival at ``d`` uniform in 1 to 9.9 m.

    ``graded``: the label grows with the index (D1 passes); otherwise it cycles over the five
    levels. ``shift``: the pressed receptions come after more forward ball (6 to 9.5 m against
    2.5 to 6, one forward stratum), a pre-trend the outcome does not keep; otherwise the
    incoming ball is lateral. ``unseen_only``: the rival is detected with chance one half and
    the effect acts only when it is not (the effect lives in the extrapolated positions).
    ``paired``: the two receptions of a possession share their incoming ball (``x`` correlated
    within the possession, so the null is blocked).
    """
    worlds: dict[int, power.C1Inputs] = {}
    for m in range(1, 11):
        rng = np.random.default_rng([21, seed, m])
        specs: list[Spec] = []
        distances: list[float] = []
        for _ in range(n):
            d = float(rng.uniform(1.0, 9.9))
            pressed = d <= 5.0
            seen = not unseen_only or bool(rng.random() < 0.5)
            low, high = ((6.0, 9.5) if pressed else (2.5, 6.0)) if shift else (-1.5, 1.5)
            hit = pressed and (not unseen_only or not seen)
            in_adv = float(rng.uniform(low, high))
            if paired and len(specs) % 2:
                in_adv = specs[-1].in_adv
            specs.append(
                Spec(
                    in_adv=in_adv,
                    out_adv=float(effect_m * hit + rng.normal(0.0, 2.0)),
                    rivals=(Rival(pos=ahead(d), detected=seen), FAR),
                )
            )
            distances.append(d)
        inputs = tracking_match(m, specs)
        worlds[m] = with_levels(inputs, distances) if graded else inputs
    return worlds


def judged(monkeypatch: pytest.MonkeyPatch, worlds: dict[int, power.C1Inputs]) -> dict[str, Any]:
    monkeypatch.setattr(power, "load_c1", lambda m: worlds[m])
    return calibration.calibration_report(list(worlds))


def kept_units(worlds: dict[int, power.C1Inputs]) -> list[effect.EffectUnit]:
    return [
        u for i in worlds.values() for u in effect.effect_units(design.design_units(i), i.s1.match)
    ]


SEEDS = range(5)


# --- the variance factor -----------------------------------------------------------------------


def unit(
    match: int, stratum: str, pressed: bool, pre: float, outcome: float, k: int
) -> effect.EffectUnit:
    return effect.EffectUnit(
        match, 1, 100 + 40 * k, stratum, pressed, f"p{k}", pre, outcome, 0, True
    )


def test_variance_factor_by_hand() -> None:
    rng = np.random.default_rng(21)
    cells = {
        (1, "a"): ([3, 4, 5, 6, 7, 8], [0, 1, 2, 3, 4, 5]),  # strong pre-trend
        (1, "b"): ([1.0] * 5, [1.0] * 7),  # x constant: no covariate
        (2, "a"): ([0, 2, 1, 3, 2, 4, 1], [1, 0, 2, 1, 3, 0, 2, 1, 2]),  # weak
    }
    units, expected, weights = [], [], []
    for (m, s), (xp, xf) in cells.items():
        x = np.array([*xp, *xf], dtype=float)
        g = np.array([1] * len(xp) + [0] * len(xf), dtype=float)
        units += [
            unit(m, s, bool(gi), float(xi), float(rng.normal()), len(units) + i)
            for i, (gi, xi) in enumerate(zip(g, x, strict=True))
        ]
        r = 0.0 if np.ptp(x) == 0 else float(np.corrcoef(g, x)[0, 1])
        expected.append(1.0 / (1.0 - r * r))
        weights.append(len(xp) * len(xf) / len(x))
    got = calibration.variance_factor(effect.estimate(units))
    e, w = np.array(expected), np.array(weights)
    assert expected[1] == 1.0 and expected[0] > 1.5 > expected[2]
    assert got == {
        "cells": 3,
        "weighted_mean": pytest.approx(float(e @ w / w.sum())),
        "median": pytest.approx(float(np.median(e))),
        "max": pytest.approx(float(e.max())),
    }
    assert calibration.variance_factor(effect.estimate([])) == {
        "cells": 0,
        "weighted_mean": None,
        "median": None,
        "max": None,
    }


# --- the criteria by hand ----------------------------------------------------------------------


def test_d1_needs_enough_matches_of_a_half() -> None:
    nine = {m: m != 10 for m in range(1, 11)}
    eight = {m: m < 9 for m in range(1, 11)}
    short = {m: True for m in range(1, 10)}
    assert (calibration.d1(nine).kills, calibration.d1(nine).evaluable) == (False, True)
    assert calibration.d1(nine).values == {"matches_increasing": 9, "min_matches": 9}
    assert (calibration.d1(eight).kills, calibration.d1(eight).evaluable) == (True, True)
    assert (calibration.d1(short).kills, calibration.d1(short).evaluable) == (True, False)


def test_d2_kills_above_the_limit_only() -> None:
    assert power.MDE_LIMIT == 0.3
    assert not calibration.d2(0.3).kills
    assert calibration.d2(0.31).kills
    assert calibration.d2(None).kills
    assert calibration.d2(0.13).values == {"mde80_sd": 0.13, "limit_sd": 0.3}


def a_bar(passed: bool) -> effect.Bar:
    return effect.Bar("V0", 10 if passed else 7, 10, passed, 0.0005, True, passed)


def test_d5_by_hand() -> None:
    alive = effect.Criterion("D3", False, True, {})
    dead = effect.Criterion("D4", True, True, {})
    assert calibration.d5(a_bar(True), [alive])["kills"] is False
    assert calibration.d5(a_bar(False), [alive]) == {
        "name": "D5",
        "kills": True,
        "v0_bar_passed": False,
        "killing": [],
    }
    assert calibration.d5(a_bar(True), [alive, dead])["killing"] == ["D4"]
    assert calibration.d5(a_bar(True), [alive, dead])["kills"] is True


# --- whole halves ------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_a_planted_effect_passes_the_calibration(
    seed: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    worlds = half(seed)
    got = judged(monkeypatch, worlds)
    v0 = got["variants"]["V0"]
    # -1 m on an outcome of sd about 2.06 inside the cell: about -0.49 sd.
    assert -0.65 < v0["t"] < -0.3
    assert v0["agreeing"] == 10 and v0["bar"]["passed"] and v0["null"]["p"] <= bar.BAR_P
    assert got["verdict"]["calibration_passes"] is True
    assert [got["criteria"][c]["kills"] for c in ("D1", "D2", "D3", "D4", "D5")] == [False] * 5
    assert got["criteria"]["D1"]["values"]["matches_increasing"] == 10
    assert got["criteria"]["D2"]["v1"]["label"] is None
    # Unblocked, as the rule says on this design.
    assert got["design"]["null"]["blocked"] is (got["design"]["null"]["rho_v0_pooled"] > 0.1)
    assert v0["null"]["blocked"] is False and v0["null"]["draws"] == 2000
    # Every rival is detected and every ball row too: V1 is V0, nothing is undefined.
    assert got["variants"]["V1"]["t"] == pytest.approx(v0["t"])
    assert all(
        o[g]["undefined"] == 0 and o[g]["ball_extrapolated"] == 0
        for o in got["outcomes"].values()
        for g in ("pressed", "free")
    )
    assert 1.0 <= v0["variance_factor"]["weighted_mean"] <= v0["variance_factor"]["max"]
    path = calibration.write_calibration_report(list(worlds), tmp_path)
    assert path.read_bytes() == render_report(got).encode("utf-8")
    assert b"\r" not in path.read_bytes()


@pytest.mark.parametrize("seed", SEEDS)
def test_no_effect_dies_by_d5(seed: int, monkeypatch: pytest.MonkeyPatch) -> None:
    worlds = half(seed, effect_m=0.0)
    got = judged(monkeypatch, worlds)
    assert abs(got["variants"]["V0"]["t"]) < 0.15
    # The null is the calibration half's stream: a p away from the floor tells the two apart.
    every = kept_units(worlds)
    p = got["variants"]["V0"]["null"]["p"]
    assert p == effect.permutation_test(every, "calibration", "V0").p
    assert p != effect.permutation_test(every, "heldout", "V0").p
    assert got["variants"]["V0"]["bar"]["passed"] is False
    assert got["criteria"]["D5"]["v0_bar_passed"] is False
    assert got["verdict"]["calibration_passes"] is False


@pytest.mark.parametrize("seed", range(3))
def test_levels_unrelated_to_the_index_kill_by_d1(
    seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    got = judged(monkeypatch, half(seed, graded=False))
    assert got["variants"]["V0"]["bar"]["passed"] is True
    assert got["criteria"]["D1"]["kills"] is True
    assert got["criteria"]["D5"]["killing"] == ["D1"]
    assert got["verdict"]["calibration_passes"] is False


@pytest.mark.parametrize("seed", range(3))
def test_a_pretrend_kills_by_d3(seed: int, monkeypatch: pytest.MonkeyPatch) -> None:
    got = judged(monkeypatch, half(seed, shift=True))
    v0 = got["variants"]["V0"]
    assert v0["pretrend_sd"] > 1.0 and v0["pretrend_m"] > 2.5
    assert got["criteria"]["D3"]["kills"] is True
    assert got["criteria"]["D3"]["values"]["floor"] == pytest.approx(2 * v0["pretrend_sd"])
    assert "D3" in got["criteria"]["D5"]["killing"]
    assert got["verdict"]["calibration_passes"] is False


@pytest.mark.parametrize("seed", range(3))
def test_an_effect_in_extrapolated_rivals_kills_by_d4(
    seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    got = judged(monkeypatch, half(seed, effect_m=-2.0, unseen_only=True))
    t0, t1 = got["variants"]["V0"]["t"], got["variants"]["V1"]["t"]
    assert got["variants"]["V0"]["bar"]["passed"] is True
    assert abs(t1) < 0.5 * abs(t0)
    assert got["criteria"]["D4"]["kills"] is True
    assert got["criteria"]["D5"]["killing"] == ["D4"]
    # V2: the class with the extrapolated rival carries the effect, so |T| does not shrink.
    assert got["beside"]["V2"]["shrinks"] is False
    assert got["verdict"]["calibration_passes"] is False


def test_a_correlated_possession_blocks_the_null(monkeypatch: pytest.MonkeyPatch) -> None:
    got = judged(monkeypatch, half(0, paired=True))
    assert got["design"]["null"]["rho_v0_pooled"] > bar.BLOCK_RHO
    assert got["design"]["null"]["blocked"] is True
    assert all(v["null"]["blocked"] is True for v in got["variants"].values())


def test_the_v1_null_permutes_only_the_v1_units() -> None:
    units = kept_units(half(0, effect_m=0.0, n=60, unseen_only=True))
    v1 = effect.select_units(units, "V1")
    assert 0 < len(v1) < len(units)
    for blocked in (False, True):
        got = effect.null_effects(units, calibration.HALF, "V1", blocked, draws=200)
        want = effect.null_effects(v1, calibration.HALF, "V1", blocked, draws=200)
        np.testing.assert_array_equal(got.pooled, want.pooled)


def test_a_small_half_dies_by_d2(monkeypatch: pytest.MonkeyPatch) -> None:
    # Half the rivals extrapolated: V1 holds half the units, so its MDE80 is not V0's.
    got = judged(monkeypatch, half(0, n=20, unseen_only=True))
    mde80 = got["design"]["mde80_sd"]
    assert mde80["V0"] is None or mde80["V0"] > 0.3
    assert mde80["V0"] != mde80["V1"]
    assert got["criteria"]["D2"]["values"]["mde80_sd"] == mde80["V0"]
    assert got["criteria"]["D2"]["kills"] is True
    assert "D2" in got["criteria"]["D5"]["killing"]
    assert got["criteria"]["D2"]["v1"]["label"] == calibration.NOT_TESTABLE_IN_SEEN
