"""Task 17 on hand-made matches: the units of C1 and C3, the statistic before t, the rule.

Every expected number is planted here. Mutations, each annotated with the test that kills it:

* a reader that takes a negative lag (the outcome window ``(t, t + W]``):
  ``test_the_readers_refuse_a_lag_after_t``;
* a statistic, stratum, group or V1 that reads a frame after ``t`` (``ball_advance`` at
  ``frame + lag``, ``block_before`` at ``frame + lag``):
  ``test_nothing_after_t_moves_a_c1_unit`` and ``test_nothing_after_t_moves_a_c3_unit``;
* the C1 cause read with another radius, or V1 that ignores the detection of the near rivals:
  ``test_c1_units_carry_the_planted_design``;
* the C3 contrast with the groups swapped, or V1 of length checked on the width's fixers:
  ``test_c3_units_carry_the_planted_design``;
* a possession that does not break on a change of team or period:
  ``test_phase_runs_break_on_team_and_period``;
* a null that never blocks, or that blocks below the threshold:
  ``test_the_null_is_blocked_above_the_threshold``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
from layer2_helpers import Row, frames_table, make_match

from ac2fb.defence import bar, power, probe_s1, probe_s3
from ac2fb.defence.block import DEFINITIONS, name_of
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.defence.pressure import Reception
from ac2fb.defence.probe_s3 import Phase
from ac2fb.reliability.long import long_table

T0 = 100
STEP = 60  # frames between two instants: no window overlaps another


# --- C1 ------------------------------------------------------------------------------------------


def c1_world(
    plans: list[tuple[float, float, bool]], after: float = 0.0
) -> tuple[power.C1Inputs, list[Reception]]:
    """One reception per plan ``(rival distance, ball advance, rival detected)``.

    The carrier (team 1, attacking +x) stands at the centre; rival 11 straight ahead at the
    planted distance, rival 12 at 30 m. The ball moves by the planted advance along x from
    ``t - W`` to ``t``. Every row after the last ``t`` is put at ``after``. Possessions: two
    receptions each.
    """
    series: dict[int, list[Row]] = {1: [], 11: [], 12: []}
    ball: list[Row] = []
    receptions: list[Reception] = []
    for k, (distance, advance, seen) in enumerate(plans):
        t = T0 + STEP * k
        series[1].append((t, 0.0, 0.0, True))
        series[11].append((t, distance, 0.0, seen))
        series[12].append((t, -30.0, 0.0, True))
        ball += [(t - W, -advance, 0.5, True), (t, 0.0, 0.5, True)]
        receptions.append(Reception(f"e{k}", 1, t, 1, 1, 3))
    last = T0 + STEP * (len(plans) - 1)
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


def test_c1_units_carry_the_planted_design() -> None:
    plans = [(3.0, 6.0, True), (8.0, -4.0, True), (4.9, 0.5, False), (5.1, 12.0, True)]
    inputs, _ = c1_world(plans)
    units, counts = power.c1_units(inputs)
    assert [u.group for u in units] == [True, False, True, False]  # within 5 m or not
    assert [u.pre for u in units] == pytest.approx([6.0, -4.0, 0.5, 12.0])
    assert [u.stratum for u in units] == [
        "forward/middle/short",
        "backward/middle/short",
        "lateral/middle/short",
        "forward/middle/long",
    ]
    assert [u.v1 for u in units] == [True, True, False, True]  # rival 11 within 10 m, unseen
    assert [u.possession for u in units] == ["p0", "p0", "p1", "p1"]
    assert counts == {"scored": 4, "stratum_undefined": 0, "v1_scored": 3}


def test_c1_needs_a_possession_for_every_unit() -> None:
    inputs, _ = c1_world([(3.0, 6.0, True)])
    with pytest.raises(ValueError, match="team possession"):
        power.c1_units(power.C1Inputs(inputs.s1, {}))


@pytest.mark.parametrize("plan", [(3.0, 6.0, True), (8.0, -4.0, False), (4.0, 15.0, True)])
def test_nothing_after_t_moves_a_c1_unit(plan: tuple[float, float, bool]) -> None:
    a, _ = c1_world([plan], after=1.0)
    b, _ = c1_world([plan], after=-45.0)
    assert power.c1_units(a) == power.c1_units(b)


def test_the_readers_refuse_a_lag_after_t() -> None:
    inputs, receptions = c1_world([(3.0, 6.0, True)])
    match = inputs.s1.match
    assert power.ball_advance(match, receptions[0].frame, 1, W) == pytest.approx(6.0)
    with pytest.raises(ValueError, match="after t"):
        power.ball_advance(match, receptions[0].frame, 1, -W)
    phase = Phase(0, 1, receptions[0].frame, 1, None, None)
    definition = DEFINITIONS[0]
    with pytest.raises(ValueError, match="after t"):
        power.block_before(match, {}, phase, -1, definition)


def test_pressed_at_uses_the_m10_radius() -> None:
    inputs, receptions = c1_world([(5.0, 6.0, True), (5.0001, 6.0, True)])
    match = inputs.s1.match
    assert power.pressed_at(match, receptions[0]) is True
    assert power.pressed_at(match, receptions[1]) is False


# --- C3 ------------------------------------------------------------------------------------------

# Each team has six players: two fix the y ends, two the x ends, two stand inside.
SHAPE = {0: ("y", -1), 1: ("y", 1), 2: ("x", -1), 3: ("x", 1), 4: ("in", 0), 5: ("in", 0)}


def shape(width: float, length: float, centre: float) -> list[tuple[float, float]]:
    out = []
    for role, side in SHAPE.values():
        if role == "y":
            out.append((centre, side * width / 2))
        elif role == "x":
            out.append((centre + side * length / 2, 0.0))
        else:
            out.append((centre + side, 1.0))
    return out


def c3_world(
    plans: list[tuple[int, str | None, float, float, bool, bool]], after: float = 0.0
) -> power.C3Inputs:
    """One phase per plan ``(team in possession, type, width at t, length at t, y fixers seen,
    x fixers seen)``; the block at ``t - W`` is 2 m narrower and 3 m shorter than at ``t``.

    Team 1 attacks +x and team 2 -x; both teams take the planted shape. The ball goes 6 m along
    team 1's attack from ``t - W`` to ``t``. Every row after the last ``t`` is put at ``after``.
    """
    players = {10 * team + j: team for team in (1, 2) for j in range(6)}
    series: dict[int, list[Row]] = {p: [] for p in players}
    ball: list[Row] = []
    phases: list[Phase] = []
    types: dict[int, str | None] = {}
    for k, (team_in, kind, width, length, y_seen, x_seen) in enumerate(plans):
        t = T0 + STEP * k
        for frame, w, ln in ((t - W, width - 2.0, length - 3.0), (t, width, length)):
            for team in (1, 2):
                for j, (x, y) in enumerate(shape(w, ln, 5.0)):
                    role = SHAPE[j][0]
                    seen = frame != t or (
                        y_seen if role == "y" else x_seen if role == "x" else True
                    )
                    series[10 * team + j].append((frame, x, y, seen))
        ball += [(t - W, -6.0, 0.0, True), (t, 0.0, 0.0, True)]
        phases.append(Phase(k, 1, t, team_in, None, None))
        types[k] = kind
    last = T0 + STEP * (len(plans) - 1)
    for p in series:
        series[p] += [(last + j, after * (1 + p % 7), -after * (p % 5), False) for j in (1, 5, W)]
    ball += [(last + j, after, -after, True) for j in (1, W)]
    match = make_match(series, players, ball=ball, signs={1: 1, 2: -1})
    long = long_table(frames_table(series, players, ball))
    return power.C3Inputs(probe_s3.MatchInputs(match, tuple(phases), long), types)


PLANS = [
    (1, "low_block", 30.0, 40.0, True, True),
    (1, "high_block", 44.0, 52.0, False, True),
    (2, "medium_block", 36.0, 45.0, True, False),
    (2, "high_block", 41.0, 50.0, True, False),
    (1, None, 33.0, 47.0, True, True),
]


def test_c3_units_carry_the_planted_design() -> None:
    inputs = c3_world(PLANS)
    width = power.c3_units(inputs, "width", stratified=False)
    length = power.c3_units(inputs, "length", stratified=False)
    assert [u.group for u in width] == [True, False, None, False, None]
    assert [u.pre for u in width] == pytest.approx([28.0, 42.0, 34.0, 39.0, 31.0])
    assert [u.pre for u in length] == pytest.approx([37.0, 49.0, 42.0, 47.0, 44.0])
    assert [u.v1 for u in width] == [True, False, True, True, True]
    assert [u.v1 for u in length] == [True, True, False, False, True]
    assert {u.stratum for u in width} == {"all"}
    assert [u.possession for u in width] == ["run:1", "run:1", "run:2", "run:2", "run:3"]
    strata = [u.stratum for u in power.c3_units(inputs, "width", stratified=True)]
    # The ball goes 6 m along +x: forward for team 1, backward for team 2; it ends at x = 0.
    assert strata == [
        "forward/middle/short",
        "forward/middle/short",
        "backward/middle/short",
        "backward/middle/short",
        "forward/middle/short",
    ]
    with pytest.raises(ValueError, match="unknown outcome"):
        power.c3_units(inputs, "area", stratified=False)


@pytest.mark.parametrize("outcome", ["width", "length"])
@pytest.mark.parametrize("stratified", [False, True])
def test_nothing_after_t_moves_a_c3_unit(outcome: str, stratified: bool) -> None:
    a = power.c3_units(c3_world(PLANS[-1:], after=1.0), outcome, stratified)
    b = power.c3_units(c3_world(PLANS[-1:], after=-40.0), outcome, stratified)
    assert a == b and len(a) == 1


def test_the_c3_definition_is_one_of_the_eight() -> None:
    assert power.C3_DEFINITION in {name_of(d) for d in DEFINITIONS}


def test_phase_runs_break_on_team_and_period() -> None:
    phases = [
        Phase(0, 1, 10, 1, None, None),
        Phase(1, 1, 20, 1, None, None),
        Phase(2, 1, 30, 2, None, None),
        Phase(3, 2, 5, 2, None, None),  # same team, new period
        Phase(4, 2, 15, 2, None, None),
        Phase(5, 2, 25, 1, None, None),
    ]
    assert power.phase_runs(list(reversed(phases))) == {
        0: "run:1",
        1: "run:1",
        2: "run:2",
        3: "run:3",
        4: "run:3",
        5: "run:4",
    }


def test_possessions_from_reads_the_player_possessions() -> None:
    events = pa.table(
        {
            "native_family": ["player_possession", "passing_option", "player_possession"],
            "native_event_id": ["a", "b", "c"],
            "possession_id": ["p1", "p1", None],
        }
    )
    assert power.possessions_from(events) == {"a": "p1"}


# --- design, null and rule -----------------------------------------------------------------------


def units_of(rho: float, seed: int) -> dict[int, list[power.Unit]]:
    """Ten matches of 60 possessions of 3 units with a planted correlation of the pre value."""
    rng = np.random.default_rng(seed)
    out: dict[int, list[power.Unit]] = {}
    for m in range(10):
        units = []
        for k in range(60):
            shared = rng.standard_normal() * math.sqrt(rho)
            for j in range(3):
                pre = float(shared + rng.standard_normal() * math.sqrt(1 - rho))
                units.append(power.Unit(k, "s", (k + j) % 2 == 0, f"p{k}", pre, j != 2))
        out[1000 + m] = units
    return out


def test_design_of_keeps_the_contrast_and_v1() -> None:
    units = {
        1: [power.Unit(1, "a", True, "p", 0.0, True), power.Unit(2, "a", None, "p", 0.0, True)],
        2: [power.Unit(3, "b", False, "q", None, False)],
        3: [],
    }
    v0, v1 = power.design_of(units, "V0"), power.design_of(units, "V1")
    assert v0.matches == (1, 2, 3) and v0.match.tolist() == [0, 1]
    assert v0.pressed.tolist() == [True, False] and v0.possession == ("p", "q")
    assert v1.match.tolist() == [0] and v1.stratum == ("a",)


@pytest.mark.parametrize(("rho", "blocked"), [(0.0, False), (0.4, True)])
def test_the_null_is_blocked_above_the_threshold(rho: float, blocked: bool) -> None:
    result = power.candidate_power(units_of(rho, 3), "test", True, replicates=500)
    assert result["blocked"] is blocked
    v0 = result["variants"]["V0"]  # type: ignore[index]
    one = v0["matches"]["1000"]
    assert one["n"] == 180 and one["pressed"] == 90 and one["free"] == 90
    assert one["possessions"] == 60 and one["cells_used"] == 1 and one["units_used"] == 180
    assert one["weight"] == pytest.approx(45.0)
    assert one["rho"]["value"] == pytest.approx(rho, abs=0.15)
    assert one["rho"]["pairs"] == 180 and "pretrend_sd" in one
    assert v0["mde80_sd"] is not None and v0["null_pass_rate"] < 0.01
    assert result["variants"]["V1"]["matches"]["1000"]["n"] == 120  # type: ignore[index]


def test_cp1_rule_follows_the_plan() -> None:
    both = power.cp1_rule({"C1": True, "C2": False, "C3": True}, {"C1": 0.2, "C3": None})
    assert both["recommended_first"] == "C1" and both["backup"] == "C3"
    assert both["testable_v0"] == {"C1": True, "C3": False}
    assert power.cp1_rule({"C1": False, "C2": False, "C3": True}, {})["recommended_first"] == "C3"
    none = power.cp1_rule({"C1": False, "C2": False, "C3": False}, {})
    assert none["recommended_first"] == "branch_B" and none["backup"] is None
    assert power.cp1_rule({"C1": True, "C2": False, "C3": False}, {"C1": 0.31})["testable_v0"] == {
        "C1": False
    }
    with pytest.raises(NotImplementedError):
        power.cp1_rule({"C1": True, "C2": True, "C3": True}, {})


def test_probe_verdicts_reads_the_three_reports(tmp_path: Path) -> None:
    for name, key, value in (
        ("probe_s1.json", "c1_survives_probe", True),
        ("probe_s2.json", "c2_survives_probe", False),
        ("probe_s3.json", "c3_survives_probe", True),
    ):
        (tmp_path / name).write_text(json.dumps({"verdict": {key: value}}), encoding="utf-8")
    assert power.probe_verdicts(tmp_path) == {"C1": True, "C2": False, "C3": True}
    (tmp_path / "probe_s3.json").write_text(
        json.dumps({"verdict": {"c3_survives_probe": None}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="no complete verdict"):
        power.probe_verdicts(tmp_path)


def test_the_bar_constants_are_the_plans() -> None:
    assert (bar.BAR_SAME_SIGN, bar.BAR_P, bar.N_PERMUTATIONS) == (8, 0.00135, 2000)
    assert (bar.POWER_REPLICATES, bar.BLOCK_RHO, power.MDE_LIMIT) == (2500, 0.1, 0.3)
