"""Probe S1: the pressure index, the contrast, the extrapolated share and the strata.

Every expected number is built here from the planted geometry (trigonometry written in the
test), never from the code under test. The synthetic world has ten matches (seeds 1 to 10): in
each, five levels of the provider's label with 15 receptions each, three rivals within 10 m at
fixed bearings whose distance shrinks with the level, and two far ones.

Mutations, each annotated with the test that kills it:

* an index without the distance weight (every rival within 10 m counts the same): the medians
  by level are equal, no match grows, C1 would die on data that does have pressure:
  ``test_an_index_without_distance_weight_breaks_the_contrast``;
* an index without the goal-side weight: ``test_a_rival_behind_the_carrier_weighs_nothing``;
* a contrast that does not demand ``MIN_PER_LEVEL`` receptions:
  ``test_a_level_with_too_few_receptions_cannot_show_an_increase``;
* a rule that counts 8 of 10 as a pass: ``test_the_verdict_needs_nine_of_ten``;
* a stratum or an index that reads a frame after ``t``:
  ``test_nothing_after_the_reception_is_read``;
* a stratum cut that lets floating-point noise decide a value exactly at the cut (2 m that is
  -2.0000000000000004, 10 m that is 9.999999999999998): ``test_the_stratum_of_the_incoming_ball``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest
from layer2_helpers import Row, frames_table, make_match

from ac2fb.defence import pressure, probe_s1
from ac2fb.defence.pressure import LEVELS, Reception
from ac2fb.defence.probe_s1 import MatchInputs
from ac2fb.reliability.long import long_table
from ac2fb.reliability.match import MatchData
from ac2fb.reliability.report import render_report
from ac2fb.reliability.sensitivity import Window, sensitivity

ROOT = Path(__file__).resolve().parent.parent
SEEDS = tuple(range(1, 11))
PER_LEVEL = 15
BEARINGS = (0.0, 50.0, -50.0)  # degrees from the attack direction, +x
TEAMS = {1: 1, 2: 1, 11: 2, 12: 2, 13: 2, 14: 2, 15: 2}


def at(bearing: float, d: float) -> tuple[float, float]:
    """The point at distance ``d`` and ``bearing`` degrees from the origin, 0 degrees along +x."""
    a = math.radians(bearing)
    return round(d * math.cos(a), 6), round(d * math.sin(a), 6)


def expected_weight(bearing: float, d: float) -> float:
    """The weight of a rival of a carrier at the origin attacking +x, by the written formula."""
    return (1 - d / 10) * (1 + math.cos(math.radians(bearing))) / 2 if d <= 10 else 0.0


def distances(level: int, rng: np.random.Generator) -> list[float]:
    """Three near distances that shrink by 1.7 m per level, with a little jitter."""
    return [round(9.0 - 1.7 * (level - 1) + float(rng.uniform(-0.15, 0.15)), 3) for _ in BEARINGS]


def world(
    seed: int, hidden: set[int] | None = None
) -> tuple[MatchInputs, dict[int, list[tuple[float, float]]]]:
    """A synthetic match; ``hidden`` are the indices of receptions whose rival 13 is extrapolated.

    Also returns, per reception index, the planted ``(bearing, distance)``-weights of the near
    rivals as ``(weight, rival id)`` pairs, for the test to sum itself.
    """
    rng = np.random.default_rng(seed)
    series: dict[int, list[Row]] = {p: [] for p in TEAMS}
    receptions: list[Reception] = []
    planted: dict[int, list[tuple[float, float]]] = {}
    order = [(level, k) for level in LEVELS for k in range(PER_LEVEL)]
    rng.shuffle(order)  # type: ignore[arg-type]
    for i, (level, _) in enumerate(order):
        frame = 100 + 50 * i
        series[1].append((frame, 0.0, 0.0, True))
        series[2].append((frame, -10.0, 4.0, True))
        near = distances(level, rng)
        planted[i] = []
        for p, bearing, d in zip((11, 12, 13), BEARINGS, near, strict=True):
            x, y = at(bearing, d)
            seen = not (p == 13 and i in (hidden or set()))
            series[p].append((frame, x, y, seen))
            planted[i].append((expected_weight(bearing, d), float(p)))
        for p in (14, 15):  # beyond 10 m, anywhere: they must not count
            x, y = at(float(rng.uniform(-180, 180)), float(rng.uniform(15, 40)))
            series[p].append((frame, x, y, True))
        receptions.append(Reception(f"e{i}", 1, frame, 1, 1, level))
    match = make_match(series, TEAMS, signs={1: 1, 2: -1})
    long = long_table(frames_table(series, TEAMS))
    return MatchInputs(match, long, tuple(receptions), len(receptions) + 7), planted


# --- the index, by hand ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rival", "sign", "expected"),
    [
        ((5.0, 0.0), 1, 0.5),  # straight ahead at 5 m: (1 - 0.5) * 1
        ((-5.0, 0.0), 1, 0.0),  # straight behind: no goal-side weight
        ((0.0, 5.0), 1, 0.25),  # level with the carrier: (1 - 0.5) * 0.5
        ((10.0, 0.0), 1, 0.0),  # at the radius the distance weight is 0
        ((10.01, 0.0), 1, 0.0),  # beyond it, out
        ((0.0, 0.0), 1, 0.5),  # on the carrier: distance weight 1, direction unknown, cos = 0
        ((-5.0, 0.0), -1, 0.5),  # the other team attacks -x: this rival is ahead of it
    ],
)
def test_the_weight_of_one_rival(rival: tuple[float, float], sign: int, expected: float) -> None:
    got = pressure.rival_weights((0.0, 0.0), np.array([rival]), sign)
    assert got[0] == pytest.approx(expected, abs=1e-12)


def test_the_goal_is_a_point_not_a_direction() -> None:
    # A carrier on the goal line, 5 m off the post: the goal is the point (52.5, 0), to its left
    # (towards -y); a rival at (52.5, 3) is between them (cos = 1), one at (52.5, 8) is behind.
    carrier = (52.5, 5.0)
    ahead = pressure.rival_weights(carrier, np.array([[52.5, 3.0]]), 1)[0]
    behind = pressure.rival_weights(carrier, np.array([[52.5, 8.0]]), 1)[0]
    assert ahead == pytest.approx((1 - 0.2) * 1.0)
    assert behind == pytest.approx(0.0, abs=1e-12)


def test_a_rival_behind_the_carrier_weighs_nothing() -> None:
    # Mutation: an index without the goal-side weight gives 0.5 here.
    assert pressure.rival_weights((0.0, 0.0), np.array([[-3.0, 0.0]]), 1)[0] == 0.0


# --- the contrast on the synthetic world ----------------------------------------------------------


def increasing_matches() -> int:
    return sum(bool(probe_s1.match_report(world(s)[0])["contrast"]["increasing"]) for s in SEEDS)  # type: ignore[index]


def test_the_index_grows_with_the_label_in_every_planted_match() -> None:
    for seed in SEEDS:
        report = probe_s1.match_report(world(seed)[0])
        contrast = report["contrast"]
        assert contrast["evaluable"] and contrast["increasing"], seed  # type: ignore[index]
        assert contrast["n"] == {name: PER_LEVEL for name in LEVELS.values()}  # type: ignore[index]
        medians = list(contrast["median"].values())  # type: ignore[index]
        assert medians == sorted(medians)
    assert increasing_matches() == len(SEEDS)


def test_an_index_without_distance_weight_breaks_the_contrast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mutation: every rival within 10 m weighs the same. The planted rivals are the same three
    # at the same bearings at every level, so the medians are equal and nothing grows.
    monkeypatch.setattr(pressure, "distance_weight", lambda d: np.ones_like(d))
    assert increasing_matches() == 0
    verdict = probe_s1.verdict(
        {s: bool(probe_s1.match_report(world(s)[0])["contrast"]["increasing"]) for s in SEEDS}  # type: ignore[index]
    )
    assert verdict["c1_survives_probe"] is False


def test_the_planted_medians_are_the_hand_computed_ones() -> None:
    inputs, planted = world(3)
    scored = pressure.score_receptions(inputs.match, inputs.receptions)
    assert len(scored) == len(inputs.receptions)
    for i, s in enumerate(scored):
        assert s.index == pytest.approx(sum(w for w, _ in planted[i]), abs=1e-5)
        assert set(s.near_players) == {11, 12, 13}  # the two far rivals never count


def test_a_level_with_too_few_receptions_cannot_show_an_increase() -> None:
    # Mutation: a contrast without MIN_PER_LEVEL would call this an increase.
    inputs, _ = world(1)
    top = [r for r in inputs.receptions if r.level == 5][: probe_s1.MIN_PER_LEVEL - 1]
    kept = tuple(r for r in inputs.receptions if r.level != 5) + tuple(top)
    scored = pressure.score_receptions(inputs.match, kept)
    contrast = pressure.level_contrast(scored, probe_s1.MIN_PER_LEVEL)
    assert contrast["n"]["very_high_pressure"] == probe_s1.MIN_PER_LEVEL - 1  # type: ignore[index]
    assert contrast["evaluable"] is False and contrast["increasing"] is False
    assert pressure.level_contrast(scored, 1)["increasing"] is True  # the shape itself is fine


def test_a_level_that_does_not_grow_is_not_an_increase() -> None:
    inputs, _ = world(2)
    flat = [pressure.Scored(**{**s.__dict__, "index": 1.0}) for s in _scored(inputs)]
    assert pressure.level_contrast(flat, 1)["increasing"] is False


def _scored(inputs: MatchInputs) -> list[pressure.Scored]:
    return pressure.score_receptions(inputs.match, inputs.receptions)


def test_the_verdict_needs_nine_of_ten() -> None:
    # Mutation: a rule that lets 8 of 10 through.
    def made(k: int, n: int = 10) -> dict[str, object]:
        return probe_s1.verdict({i: i < k for i in range(n)})

    assert made(10)["c1_survives_probe"] is True
    assert made(9)["c1_survives_probe"] is True
    assert made(8)["c1_survives_probe"] is False
    assert made(0)["c1_survives_probe"] is False
    partial = made(9, n=9)
    assert partial["c1_survives_probe"] is None and partial["complete"] is False
    assert made(9)["matches_increasing"] == 9


def test_the_constants_are_the_ones_the_plan_and_the_artifacts_say() -> None:
    cadence = json.loads((ROOT / "reports" / "probe_cadence.json").read_text("utf-8"))
    assert pressure.INCOMING_WINDOW == cadence["decision"]["w_min_frames"]
    split = json.loads((ROOT / "protocol" / "split.json").read_text("utf-8"))
    assert probe_s1.CALIBRATION_MATCHES == len(split["calibration"])
    assert probe_s1.MIN_MATCHES == 9 and probe_s1.MIN_PER_LEVEL == 10


# --- the extrapolated share and the layer 2 variants ----------------------------------------------


def test_the_extrapolated_share_is_the_planted_one() -> None:
    hidden = {i for i in range(5 * PER_LEVEL) if i % 3 == 0}
    inputs, planted = world(4, hidden)
    scored = _scored(inputs)
    total = sum(w for i in planted for w, _ in planted[i])
    gone = sum(w for i in hidden for w, p in planted[i] if p == 13.0)
    share = pressure.extrapolated_share(scored)
    assert share["overall"] == pytest.approx(gone / total, abs=1e-5)
    live = len(planted)
    assert share["receptions_with_near_rival"] == live
    assert share["receptions_with_any"] == pytest.approx(len(hidden) / live)
    for level, name in LEVELS.items():
        idx = [i for i, r in enumerate(inputs.receptions) if r.level == level]
        want = sum(w for i in idx if i in hidden for w, p in planted[i] if p == 13.0) / sum(
            w for i in idx for w, _ in planted[i]
        )
        assert share["by_level"][name] == pytest.approx(want, abs=1e-5)  # type: ignore[index]


def test_the_extrapolated_share_is_zero_when_everyone_is_seen() -> None:
    inputs, _ = world(5)
    share = pressure.extrapolated_share(_scored(inputs))
    assert share["overall"] == 0.0 and share["receptions_with_any"] == 0.0


def test_the_layer2_variants_agree_with_the_direct_computation() -> None:
    hidden = {i for i in range(5 * PER_LEVEL) if i % 3 == 0}
    inputs, planted = world(6, hidden)
    report = probe_s1.match_report(inputs)
    sens = report["sensitivity"]
    n = len(planted)
    mean = float(np.mean([sum(w for w, _ in planted[i]) for i in planted]))
    assert sens["n_units"] == n  # type: ignore[index]
    assert sens["v0"] == {"n": n, "mean": pytest.approx(mean, abs=1e-5)}  # type: ignore[index]
    seen = [i for i in planted if i not in hidden]
    assert sens["v1"]["n"] == len(seen)  # type: ignore[index]
    assert sens["v1"]["mean"] == pytest.approx(  # type: ignore[index]
        float(np.mean([sum(w for w, _ in planted[i]) for i in seen])), abs=1e-5
    )
    strata = {s["detected_players"]: s["n"] for s in sens["v2"]}  # type: ignore[index]
    assert strata == {2: len(hidden), 3: len(seen)}
    assert sens["extrapolated_fraction"] == pytest.approx(len(hidden) / (3 * n))  # type: ignore[index]


def test_v1_contrast_keeps_only_the_receptions_with_every_near_rival_seen() -> None:
    hidden = {i for i in range(5 * PER_LEVEL) if i % 3 == 0}
    inputs, _ = world(6, hidden)
    report = probe_s1.match_report(inputs)
    assert sum(report["contrast_v1"]["n"].values()) == 5 * PER_LEVEL - len(hidden)  # type: ignore[index]


def test_the_sensitivity_metric_and_the_direct_score_give_the_same_index() -> None:
    inputs, _ = world(7)
    scored = {s.reception.frame: s.index for s in _scored(inputs)}
    kept = [s.reception for s in _scored(inputs)]
    windows = [Window(7, r.frame, r.frame) for r in kept]
    metric = pressure.make_metric(inputs.match, kept)
    out = sensitivity(metric, inputs.long, windows)[7]
    assert out.v0.mean == pytest.approx(float(np.mean(list(scored.values()))), abs=1e-12)


# --- the strata, and nothing after the reception --------------------------------------------------


def with_ball(
    ball_then: tuple[float, float], ball_now: tuple[float, float], carrier_x: float, sign: int = 1
) -> str:
    """The stratum of one reception at frame 100 with the ball where the test says."""
    t = 100
    series: dict[int, list[Row]] = {
        1: [(t, carrier_x, 0.0, True)],
        11: [(t, carrier_x + sign * 4, 0.0, True)],
    }
    ball: list[Row] = [(t - 13, *ball_then, True), (t, *ball_now, True)]
    match = make_match(series, {1: 1, 11: 2}, ball=ball, signs={1: sign, 2: -sign})
    [only] = pressure.score_receptions(match, [Reception("e", 1, t, 1, 1, 3)])
    return only.stratum


@pytest.mark.parametrize(
    ("then", "now", "carrier_x", "sign", "expected"),
    [
        ((0, 0), (-3, 0), 0.0, 1, "backward/middle/short"),
        ((0, 0), (15, 0), 0.0, 1, "forward/middle/long"),
        ((0, 0), (1.9, 5), -20.0, 1, "lateral/own/short"),
        ((0, 0), (0, 12), 30.0, 1, "lateral/final/long"),
        ((0, 0), (2.0, 0), 0.0, 1, "lateral/middle/short"),  # exactly 2 m is still lateral
        ((3.15, 0), (5.15, 0), 0.0, -1, "lateral/middle/short"),  # -2.0000000000000004 in floats
        ((6.08, 0), (16.08, 0), 0.0, 1, "forward/middle/long"),  # 9.999999999999998 in floats
        ((0, 0), (2.01, 0), 0.0, 1, "forward/middle/short"),
        ((0, 0), (-2.01, 0), 0.0, 1, "backward/middle/short"),
        ((0, 0), (-6, 0), -30.0, -1, "forward/final/short"),  # a team attacking -x
        ((0, 0), (-10, 0), 17.5, -1, "forward/middle/long"),  # the third cut belongs to middle
        ((0, 0), (9.99, 0), 0.0, 1, "forward/middle/short"),
        ((0, 0), (10, 0), 0.0, 1, "forward/middle/long"),
    ],
)
def test_the_stratum_of_the_incoming_ball(
    then: tuple[float, float], now: tuple[float, float], carrier_x: float, sign: int, expected: str
) -> None:
    assert with_ball(then, now, carrier_x, sign) == expected


def test_a_ball_without_a_row_at_either_end_is_undefined() -> None:
    t = 100
    series: dict[int, list[Row]] = {1: [(t, 0.0, 0.0, True)], 11: [(t, 4.0, 0.0, True)]}
    for ball in ([(t, 1.0, 0.0, True)], [(t - 13, 1.0, 0.0, True)], [], [(t - 12, 0, 0, True)]):
        match = make_match(series, {1: 1, 11: 2}, ball=ball, signs={1: 1, 2: -1})
        [only] = pressure.score_receptions(match, [Reception("e", 1, t, 1, 1, 3)])
        assert only.stratum == "undefined"


def test_nothing_after_the_reception_is_read() -> None:
    # Mutation: an index or stratum that reads a later frame changes when the later frames do.
    def build(after: float) -> MatchData:
        t = 100
        series: dict[int, list[Row]] = {
            1: [(t - 13, 0.0, 0.0, True), (t, 0.0, 0.0, True), (t + 13, after, after, True)],
            11: [(t, 4.0, 0.0, True), (t + 1, after, after, False), (t + 13, after, 1.0, True)],
            12: [(t, -6.0, 3.0, False), (t + 5, after, -after, True)],
        }
        ball: list[Row] = [(t - 13, 0, 0, True), (t, 5, 0, True), (t + 13, after, after, False)]
        return make_match(series, {1: 1, 11: 2, 12: 2}, ball=ball, signs={1: 1, 2: -1})

    a = pressure.score_receptions(build(1.0), [Reception("e", 1, 100, 1, 1, 3)])
    b = pressure.score_receptions(build(-40.0), [Reception("e", 1, 100, 1, 1, 3)])
    assert a == b and a[0].stratum == "forward/middle/short"


def test_stratum_counts_split_by_level_and_leave_the_undefined_apart() -> None:
    inputs, _ = world(8)  # the world has no ball: every reception is undefined
    counts = pressure.stratum_counts(_scored(inputs))
    assert counts == {"undefined": 5 * PER_LEVEL, "strata": {}}


def test_stratum_counts_tally_each_cell() -> None:
    def scored(stratum: str, level: int) -> pressure.Scored:
        return pressure.Scored(Reception("e", 1, 1, 1, 1, level), 0.0, (), (), (), True, stratum)

    cells = [("forward/own/long", 1)] * 3 + [("forward/own/long", 5)] + [("undefined", 2)]
    counts = pressure.stratum_counts([scored(s, k) for s, k in cells])
    assert counts["undefined"] == 1
    assert counts["strata"]["forward/own/long"]["n"] == 4  # type: ignore[index]
    assert counts["strata"]["forward/own/long"]["by_level"]["no_pressure"] == 3  # type: ignore[index]
    assert counts["strata"]["forward/own/long"]["by_level"]["very_high_pressure"] == 1  # type: ignore[index]


# --- the receptions from the events and the label -------------------------------------------------


def events_table(rows: list[dict[str, object]]) -> pa.Table:
    names = ["native_family", "native_event_id", "frame_start", "period", "team_id", "player_id"]
    return pa.table({n: [r.get(n) for r in rows] for n in names})


def bronze_table(rows: list[tuple[str, str, str | None, int | None]]) -> pa.Table:
    return pa.table(
        {
            "event_id": [r[0] for r in rows],
            "event_type": [r[1] for r in rows],
            "overall_pressure_start": [r[2] for r in rows],
            "overall_pressure_start_id": pa.array([r[3] for r in rows], pa.int64()),
        }
    )


def possession(event: str, frame: int, player: str | None = "fb:9") -> dict[str, object]:
    return {
        "native_family": "player_possession",
        "native_event_id": event,
        "frame_start": frame,
        "period": 1,
        "team_id": "fb:3",
        "player_id": player,
    }


def test_receptions_join_the_label_and_drop_what_has_none() -> None:
    events = events_table(
        [
            possession("a", 10),
            possession("b", 20),
            possession("c", 30, player=None),
            possession("d", 40),
            {**possession("e", 50), "native_family": "on_ball_engagement"},
        ]
    )
    bronze = bronze_table(
        [
            ("a", "player_possession", "high_pressure", 4),
            ("b", "player_possession", None, None),
            ("c", "player_possession", "low_pressure", 2),
            ("e", "on_ball_engagement", "no_pressure", 1),
        ]
    )
    total, found = probe_s1.receptions_from(events, bronze)
    assert total == 4  # the four player_possession events; the engagement is not one
    assert found == [Reception("a", 1, 10, 3, 9, 4)]  # b unlabelled, c no player, d not in bronze


def test_a_label_that_disagrees_with_its_id_is_an_error() -> None:
    events = events_table([possession("a", 10)])
    bronze = bronze_table([("a", "player_possession", "low_pressure", 4)])
    with pytest.raises(ValueError, match="pressure id 4"):
        probe_s1.receptions_from(events, bronze)


def test_two_receptions_in_one_frame_are_an_error() -> None:
    events = events_table([possession("a", 10), possession("b", 10)])
    bronze = bronze_table(
        [
            ("a", "player_possession", "low_pressure", 2),
            ("b", "player_possession", "low_pressure", 2),
        ]
    )
    with pytest.raises(ValueError, match="frame 10"):
        probe_s1.receptions_from(events, bronze)


# --- the report -----------------------------------------------------------------------------------


def test_the_report_is_per_match_with_the_verdict_and_writes_lf(tmp_path: Path) -> None:
    inputs = [world(s)[0] for s in (1, 2)]
    report = probe_s1.s1_report(inputs)
    assert set(report) == {"about", "constants", "matches", "verdict"}
    assert list(report["matches"]) == ["7"]  # type: ignore[arg-type]  # both worlds are match 7
    assert report["verdict"]["c1_survives_probe"] is None  # type: ignore[index]
    path = tmp_path / probe_s1.REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    raw = path.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    assert json.loads(raw)["constants"]["incoming_window_frames"] == 13
