"""Task 19 on hand-made matches: the protocol's units, exclusion, groups, V1 and pre-trend.

Every expected number is planted here. Mutations, each annotated with the test that kills it:

* an exclusion with ``<`` for ``<=``, across periods, only within a team, or judged against the
  kept unit before instead of the design unit before: ``test_exclusion_by_hand`` and
  ``test_the_exclusion_ignores_a_period_break_and_the_team``; judged against every labelled
  reception instead of the design units: ``test_a_reception_that_is_not_a_unit_excludes_nothing``;
* the pre statistic or the stratum read without the attack sign, or with the sign of another
  period: ``test_a_mirrored_pitch_in_the_second_period_gives_the_same_units``;
* a cut with ``>`` for ``>=`` (a unit at exactly the cut): ``test_the_cut_is_at_or_above``;
* a V1 that ignores the carrier, or V2 classes that count the rivals outside the radius:
  ``test_v1_needs_the_carrier_and_v2_counts_the_extrapolated_players``;
* a unit that reads a frame after ``t``: ``test_nothing_after_t_moves_a_design_unit``;
* kept units whose instants still fall in another's window:
  ``test_no_kept_instant_lies_in_the_window_of_another``;
* a pre-trend in metres standardised, or the floor without the ratio or the absolute value:
  ``test_pooled_pretrend_in_sd_and_metres_by_hand``;
* a proxy that is the index, or an index that is the proxy: ``test_the_proxy_is_not_the_index``.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest
from layer2_helpers import Row, frames_table, make_match

from ac2fb.defence import design, power, probe_s1
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.defence.pressure import PRESSED_INDEX, Reception
from ac2fb.reliability.long import long_table

Plan = tuple[int, tuple[float, float], tuple[float, float], bool, bool, bool]
# (t, rival 11 xy, rival 12 xy, rival 11 detected, rival 12 detected, carrier detected)


def world(
    plans: list[Plan], advances: list[float] | None = None, after: float = 0.0
) -> tuple[power.C1Inputs, list[Reception]]:
    """One reception per plan; the carrier (team 1, attacking +x) at the centre, detected or not.

    The ball moves by the planted advance (6 m forward by default) along x from ``t - W`` to
    ``t``. Every row after the last ``t`` is put at ``after``. Possessions: two receptions each.
    Levels cycle 1 to 5.
    """
    series: dict[int, list[Row]] = {1: [], 11: [], 12: []}
    ball: list[Row] = []
    receptions: list[Reception] = []
    advances = advances or [6.0] * len(plans)
    for k, ((t, r11, r12, seen11, seen12, carrier), advance) in enumerate(
        zip(plans, advances, strict=True)
    ):
        series[1].append((t, 0.0, 0.0, carrier))
        series[11].append((t, r11[0], r11[1], seen11))
        series[12].append((t, r12[0], r12[1], seen12))
        ball += [(t - W, -advance, 0.5, True), (t, 0.0, 0.5, True)]
        receptions.append(Reception(f"e{k}", 1, t, 1, 1, k % 5 + 1))
    last = max(t for t, *_ in plans)
    for p in series:
        series[p] += [(last + j, after, -after, False) for j in (1, 5, W)]
    ball += [(last + j, after, after, True) for j in (1, 5, W)]
    teams = {1: 1, 11: 2, 12: 2}
    match = make_match(series, teams, ball=ball, signs={1: 1, 2: -1})
    s1 = probe_s1.MatchInputs(
        match, long_table(frames_table(series, teams, ball)), tuple(receptions), len(receptions)
    )
    possessions = {f"e{k}": f"p{k // 2}" for k in range(len(plans))}
    return power.C1Inputs(s1, possessions), receptions


FAR = (-30.0, 0.0)  # rival 12 well outside the radius


def plan(t: int, d: float, seen: bool = True, carrier: bool = True, behind: bool = False) -> Plan:
    """Rival 11 at ``d`` metres straight ahead (or behind) of the carrier."""
    return (t, (-d if behind else d, 0.0), FAR, seen, True, carrier)


# --- the exclusion -----------------------------------------------------------------------------


def test_exclusion_by_hand() -> None:
    # Gaps 10 (excluded), 13 (excluded: at the gap), 17 (kept), 60 (kept); the unit at 123 is
    # judged against 110 although 110 is itself excluded.
    inputs, _ = world([plan(t, 3.0) for t in (100, 110, 123, 140, 200)])
    units = design.design_units(inputs)
    assert [u.frame for u in units] == [100, 110, 123, 140, 200]
    assert [u.excluded for u in units] == [False, True, True, False, False]
    kept = design.power_units(units, "index")
    assert [u.frame for u in kept] == [100, 140, 200]
    counts = design.match_counts(inputs, units)
    assert (counts["design"], counts["excluded_gap"], counts["kept"]) == (5, 2, 3)
    assert counts["overlap_design"]["within_w"] == 2 == counts["excluded_gap"]
    assert counts["overlap_kept"]["within_w"] == 0


def test_the_exclusion_ignores_a_period_break_and_the_team() -> None:
    receptions = [
        Reception("a", 1, 100, 1, 7, 3),
        Reception("b", 1, 110, 2, 8, 3),  # the other team, 10 after: excluded
        Reception("c", 1, 200, 1, 7, 3),
        Reception("d", 2, 205, 1, 7, 3),  # a new period: never excluded
        Reception("e", 2, 218, 2, 8, 3),  # exactly W after: excluded
        Reception("f", 2, 232, 1, 7, 3),  # W + 1 after: kept
    ]
    got = design.excluded_by_gap(list(reversed(receptions)))
    assert got == {(1, 110), (2, 218)}
    assert design.EXCLUSION_GAP == W == 13
    assert design.excluded_by_gap([]) == set()


def test_a_reception_that_is_not_a_unit_excludes_nothing() -> None:
    # The reception at 100 has no ball row at t - W: no stratum, not a design unit. The one at
    # 110 is judged against the design unit before it (none), not against 100: it stays.
    inputs, _ = world([plan(t, 3.0) for t in (100, 110, 200)])
    m = inputs.s1.match
    keep = m.ball_frame != 100 - W
    ball = ("ball_frame", "ball_period", "ball_x", "ball_y", "ball_detected", "ball_gap")
    m = dataclasses.replace(m, **{f: getattr(m, f)[keep] for f in ball})
    s1 = dataclasses.replace(inputs.s1, match=m)
    units = design.design_units(dataclasses.replace(inputs, s1=s1))
    assert [u.frame for u in units] == [110, 200]
    assert [u.excluded for u in units] == [False, False]


def test_no_kept_instant_lies_in_the_window_of_another() -> None:
    rng = np.random.default_rng(19)
    for _ in range(20):
        frames = sorted(set(rng.integers(100, 2000, size=80).tolist()))
        receptions = [Reception(f"e{k}", 1, t, 1, 7, 3) for k, t in enumerate(frames)]
        excluded = design.excluded_by_gap(receptions)
        kept = [t for t in frames if (1, t) not in excluded]
        assert all(b - a > W for a, b in zip(kept, kept[1:], strict=False))
        # And no more than needed: a kept unit's predecessor in the design is more than W away.
        for t in kept:
            before = [s for s in frames if s < t]
            assert not before or t - before[-1] > W


# --- the groups --------------------------------------------------------------------------------


def test_the_cut_is_at_or_above() -> None:
    # One rival straight ahead: index 1 - d / 10. At 5 m exactly 0.5: pressed; a hair more: free.
    inputs, _ = world([plan(100, 5.0), plan(200, 5.0001), plan(300, 3.0), plan(400, 8.0)])
    units = design.design_units(inputs)
    assert [round(u.index, 6) for u in units] == [0.5, 0.49999, 0.7, 0.2]
    assert [u.pressed for u in units] == [True, False, True, False]
    assert PRESSED_INDEX == 0.5
    assert design.power_units(units, "index")[1].group is False


def test_the_proxy_is_not_the_index() -> None:
    # 4 m straight behind: index 0 (free) but within 5 m (proxy pressed). Two rivals 6 m ahead
    # (0.4 each): index 0.8 (pressed) but none within 5 m (proxy free).
    plans: list[Plan] = [
        plan(100, 4.0, behind=True),
        (200, (6.0, 0.0), (6.0, 0.0), True, True, True),
        plan(300, 3.0),
    ]
    inputs, _ = world(plans)
    units = design.design_units(inputs)
    assert [u.pressed for u in units] == [False, True, True]
    assert [u.proxy_pressed for u in units] == [True, False, True]
    assert [u.index for u in units] == pytest.approx([0.0, 0.8, 0.7])
    proxy = design.power_units(units, "proxy")
    assert [u.group for u in proxy] == [True, False, True]
    counts = design.match_counts(inputs, units)
    assert counts["proxy"] == {"pressed": 2, "free": 1, "agrees_with_index": pytest.approx(1 / 3)}
    with pytest.raises(ValueError, match="unknown cause"):
        design.power_units(units, "label")


# --- V1 and V2 ---------------------------------------------------------------------------------


def test_v1_needs_the_carrier_and_v2_counts_the_extrapolated_players() -> None:
    plans: list[Plan] = [
        plan(100, 3.0),  # all seen: V1
        plan(200, 3.0, seen=False),  # near rival unseen: 1
        plan(300, 3.0, carrier=False),  # carrier unseen: 1
        (400, (3.0, 0.0), (4.0, 1.0), False, False, False),  # both near rivals and carrier: 3
        (500, (3.0, 0.0), (-30.0, 0.0), True, False, True),  # rival 12 outside the radius: V1
    ]
    inputs, _ = world(plans)
    units = design.design_units(inputs)
    assert [u.extrapolated_players for u in units] == [0, 1, 1, 3, 0]
    assert [u.v1 for u in design.power_units(units, "index")] == [True, False, False, False, True]
    counts = design.match_counts(inputs, units)
    assert counts["kept_v1"] == 2 and counts["v2_classes"] == {"0": 2, "1": 2, "2_or_more": 1}
    assert counts["kept_pressed"] == 5 and counts["kept_v1_pressed"] == 2
    assert counts["by_level"]["no_pressure"] == {"kept": 1, "pressed": 1, "v1": 1, "v1_pressed": 1}
    assert counts["by_level"]["low_pressure"] == {"kept": 1, "pressed": 1, "v1": 0, "v1_pressed": 0}
    assert counts["by_stratum"] == {
        "forward/middle/short": {"kept": 5, "pressed": 5, "v1": 2, "v1_pressed": 2}
    }
    assert counts["ball_extrapolated_at_t"] == 0.0


# --- nothing after t ---------------------------------------------------------------------------


@pytest.mark.parametrize("p", [plan(100, 3.0), plan(100, 8.0, seen=False), plan(100, 4.0)])
def test_nothing_after_t_moves_a_design_unit(p: Plan) -> None:
    a, _ = world([p], after=1.0)
    b, _ = world([p], after=-45.0)
    assert design.design_units(a) == design.design_units(b)
    assert design.match_counts(a, design.design_units(a)) == design.match_counts(
        b, design.design_units(b)
    )


def test_a_mirrored_pitch_in_the_second_period_gives_the_same_units() -> None:
    # The carrier's team attacking -x in period 2: every x flipped, the signs flipped, the
    # period changed. Nothing the design measures may move (forward, backward, lateral ball).
    inputs, _ = world(
        [plan(100, 3.0), plan(200, 4.0, behind=True), plan(300, 7.0)], advances=[6.0, -5.0, 1.0]
    )
    m = inputs.s1.match
    mirrored = dataclasses.replace(
        m,
        x=-m.x,
        ball_x=-m.ball_x,
        period=np.full_like(m.period, 2),
        ball_period=np.full_like(m.ball_period, 2),
        attack_sign={(2, team): -sign for (_, team), sign in m.attack_sign.items()},
    )
    s1 = dataclasses.replace(
        inputs.s1,
        match=mirrored,
        receptions=tuple(dataclasses.replace(r, period=2) for r in inputs.s1.receptions),
    )
    want = design.design_units(inputs)
    got = design.design_units(dataclasses.replace(inputs, s1=s1))
    assert [u.pre for u in want] == [6.0, -5.0, 1.0]
    assert [u.stratum.split("/")[0] for u in want] == ["forward", "backward", "lateral"]
    assert [dataclasses.replace(u, period=1) for u in got] == want


def test_a_unit_needs_a_possession() -> None:
    inputs, _ = world([plan(100, 3.0)])
    with pytest.raises(ValueError, match="team possession"):
        design.design_units(power.C1Inputs(inputs.s1, {}))


def test_units_are_ordered_and_carry_the_pre_statistic() -> None:
    inputs, _ = world([plan(300, 3.0), plan(100, 3.0)], advances=[-4.0, 12.0])
    units = design.design_units(inputs)
    assert [u.frame for u in units] == [100, 300]
    assert [u.pre for u in units] == pytest.approx([12.0, -4.0])
    assert [u.stratum for u in units] == ["forward/middle/long", "backward/middle/short"]
    assert [u.possession for u in units] == ["p0", "p0"]


# --- the pre-trend -----------------------------------------------------------------------------


def unit(stratum: str, group: bool, pre: float, k: int, v1: bool = True) -> power.Unit:
    return power.Unit(k, stratum, group, f"p{k}", pre, v1)


def test_pooled_pretrend_in_sd_and_metres_by_hand() -> None:
    # Match 1: one cell, pressed 2..6 against free 0..4 (difference +2 m). Match 2: pressed
    # 0..9 against free 1..10 (-1 m); a cell "b" under the minimum never enters; a unit without
    # a pre value is left out.
    one = [unit("a", True, v, k) for k, v in enumerate([2, 3, 4, 5, 6])]
    one += [unit("a", False, v, 10 + k) for k, v in enumerate([0, 1, 2, 3, 4])]
    two = [unit("a", True, v, k, v1=k < 5) for k, v in enumerate(range(10))]
    two += [unit("a", False, v, 10 + k) for k, v in enumerate(range(1, 11))]
    two += [unit("b", True, 50.0, 30 + k) for k in range(4)]
    two += [unit("b", False, 0.0, 40 + k) for k in range(6)]
    two.append(power.Unit(99, "a", True, "p99", None, True))
    s1 = float(np.std([2, 3, 4, 5, 6, 0, 1, 2, 3, 4], ddof=1))
    s2 = float(np.std([*range(10), *range(1, 11)], ddof=1))
    w1, w2 = 2.5, 5.0
    got = design.pooled_pretrend({1: one, 2: two}, "V0")
    sd = (w1 * 2 / s1 + w2 * -1 / s2) / (w1 + w2)
    metres = (w1 * 2 + w2 * -1) / (w1 + w2)
    assert got["sd"] == pytest.approx(sd) and got["metres"] == pytest.approx(metres)
    assert got["d3_abs_effect_must_exceed_sd"] == pytest.approx(abs(sd) / 0.5)
    assert got["d3_abs_effect_must_exceed_m"] == pytest.approx(abs(metres) / 0.5)
    assert (got["cells_used"], got["units_used"]) == (2, 30)
    assert got["matches"]["1"] == {
        "sd": pytest.approx(2 / s1),
        "metres": pytest.approx(2.0),
        "cells_used": 1,
    }
    assert got["matches"]["2"]["metres"] == pytest.approx(-1.0)
    # V1 keeps the units flagged v1: match 2's pressed 0..4 against free 1..10 (-3.5 m).
    v1 = design.pooled_pretrend({1: one, 2: two}, "V1")
    assert v1["matches"]["2"]["metres"] == pytest.approx(-3.5)
    assert v1["matches"]["2"]["cells_used"] == 1
    # The sd figure is task 17's pooled pre-trend on the same units.
    simulated = power.candidate_power({1: one, 2: two}, "t", True, replicates=10)
    assert simulated["variants"]["V0"]["pretrend"]["pooled_sd"] == pytest.approx(got["sd"])  # type: ignore[index]
    empty = design.pooled_pretrend({1: []}, "V0")
    assert empty["sd"] is None and empty["d3_abs_effect_must_exceed_m"] is None


def test_the_design_report_on_a_hand_made_half(monkeypatch: pytest.MonkeyPatch) -> None:
    worlds = {
        1001: world([plan(t, d) for t, d in ((100, 3.0), (110, 3.0), (200, 8.0), (300, 2.0))])[0],
        1002: world([plan(t, d) for t, d in ((100, 9.0), (160, 1.0))])[0],
    }
    monkeypatch.setattr(power, "load_c1", lambda m: worlds[m])
    monkeypatch.setattr(power.bar, "POWER_REPLICATES", 4)
    report = design.design_report([1001, 1002])
    assert report["matches"] == [1001, 1002]
    assert set(report["constants"]) >= {"pressed_index", "exclusion_gap_frames", "window_frames"}  # type: ignore[arg-type]
    units = report["units"]
    assert units["1001"]["kept"] == 3 and units["1001"]["excluded_gap"] == 1  # type: ignore[index]
    assert units["1002"]["kept"] == 2 and units["1002"]["kept_pressed"] == 1  # type: ignore[index]
    index = report["index_cause"]
    assert set(index["power"]["variants"]) == {"V0", "V1"}  # type: ignore[index]
    assert set(index["pretrend"]) == {"V0", "V1"}  # type: ignore[index]
    assert set(report["proxy_cause"]["pretrend"]) == {"V0", "V1"}  # type: ignore[index]
    assert not math.isnan(float(index["power"]["variants"]["V0"]["null_pass_rate"]))  # type: ignore[index]


def test_two_units_in_one_frame_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs, receptions = world([plan(100, 3.0)])
    twice = probe_s1.MatchInputs(inputs.s1.match, inputs.s1.long, (*receptions, receptions[0]), 2)
    monkeypatch.setattr(power, "load_c1", lambda m: power.C1Inputs(twice, inputs.possessions))
    with pytest.raises(ValueError, match="share a frame"):
        design.design_report([1])
