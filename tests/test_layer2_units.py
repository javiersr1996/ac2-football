"""Layer 2 on hand-made matches: each number a test expects is built into the match."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from layer2_helpers import Row, event, line, make_match

from ac2fb.reliability import inventory
from ac2fb.reliability import runs as R
from ac2fb.reliability.match import locate_rows, players_at
from ac2fb.reliability.report import render_report
from ac2fb.reliability.visibility import (
    defensive_line_detection,
    engager_detection,
    goalkeepers,
    reception_detection,
)

SEEDS = (1, 2, 3, 4, 5)


def walk(seed: int, frames: range, speed: float, noise: float, detected: bool) -> list[Row]:
    """A path at constant velocity plus noise; ``noise`` 0 is exactly straight."""
    rng = np.random.default_rng(seed)
    angle = rng.uniform(0, 2 * math.pi)
    return [
        (
            f,
            round(10 + speed * i * math.cos(angle) + rng.normal(0, noise), 2),
            round(5 + speed * i * math.sin(angle) + rng.normal(0, noise), 2),
            detected,
        )
        for i, f in enumerate(frames)
    ]


# --- acceleration and steps --------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_extrapolated_straight_lines_sit_at_the_rounding_floor_and_noisy_detections_above(
    seed: int,
) -> None:
    straight = walk(seed, range(100, 160), 0.2, 0.0, False)
    noisy = walk(seed, range(160, 220), 0.2, 0.15, True)
    match = make_match({1: straight + noisy}, {1: 10})
    out = R.acceleration_summary(match)
    floor = R.linear_rounding_floor()
    # Interior frames of each stretch: 58 straight, 58 noisy (the frame 159/160 triples mix).
    assert out["extrapolated"]["n"] == 58  # type: ignore[index]
    assert out["detected"]["n"] == 58  # type: ignore[index]
    assert out["extrapolated"]["p50"] <= floor["p99"]  # type: ignore[index]
    assert out["detected"]["p50"] > 5 * floor["p99"]  # type: ignore[index]
    band = out["extrapolated_by_band"]["5_20s"]  # type: ignore[index]
    assert band["n"] == 58  # a 60-frame run is in the 5 to 20 s band
    assert out["extrapolated_by_band"]["le_1s"]["n"] == 0  # type: ignore[index]


def test_the_rounding_floor_is_small_and_reproducible() -> None:
    first, second = R.linear_rounding_floor(3), R.linear_rounding_floor(3)
    assert first == second and 0 < first["p50"] < first["p90"] < first["p99"] < 0.05


def test_steps_are_split_by_the_transition_between_consecutive_frames() -> None:
    rows: list[Row] = [(0, 0.0, 0.0, True), (1, 0.3, 0.0, True), (2, 0.5, 0.0, False)]
    rows += [(3, 0.6, 0.0, False), (4, 0.8, 0.0, True)]
    rows += [(10, 5.0, 0.0, True)]  # frames 5 to 9 are not listed: no step into it
    out = R.step_summary(make_match({1: rows}, {1: 10}))
    expect = {
        "detected_to_detected": (1, 0.3),
        "detected_to_extrapolated": (1, 0.2),
        "extrapolated_to_extrapolated": (1, 0.1),
        "extrapolated_to_detected": (1, 0.2),
    }
    for name, (n, p50) in expect.items():
        assert out[name]["n"] == n  # type: ignore[index]
        assert out[name]["p50"] == pytest.approx(p50)  # type: ignore[index]


def test_a_run_ends_at_an_unlisted_frame_unless_the_plan_definition_bridges_it() -> None:
    rows = [(f, 0.0, 0.0, True) for f in range(0, 5)]
    rows += [(f, 0.0, 0.0, False) for f in range(5, 8)]
    rows += [(f, 0.0, 0.0, False) for f in range(20, 24)]  # after 12 unlisted frames
    rows += [(f, 0.0, 1.0, True) for f in range(24, 30)]
    match = make_match({1: rows}, {1: 10})
    plain = R.extrapolated_runs(match)
    assert plain.length[~plain.detected].tolist() == [3, 4]
    assert plain.left_closed[~plain.detected].tolist() == [True, False]
    assert not np.isnan(plain.jump[~plain.detected][1]) and np.isnan(plain.jump[~plain.detected][0])
    assert plain.jump[~plain.detected][1] == pytest.approx(1.0)
    bridged = R.extrapolated_runs(match, bridge_holes=True)
    # The row at frame 20 follows no listed frame, so it is left out; the rest join the first.
    assert bridged.length[~bridged.detected].tolist() == [3 + 3]


def test_unlisted_stretches_are_counted_inside_a_period_with_the_kind_of_frame_on_each_side() -> (
    None
):
    rows: list[Row] = [(f, 0.0, 0.0, True) for f in range(0, 3)]
    rows += [(f, 0.0, 0.0, False) for f in range(10, 12)]  # 7 frames unlisted after a detection
    rows += [(f, 0.0, 0.0, False) for f in range(100, 103)]  # 88 unlisted, between extrapolated
    rows += [(f, 0.0, 0.0, True) for f in range(103, 105)]
    rows += [(f, 0.0, 0.0, True) for f in range(110, 112)]  # 5 unlisted, between detected
    match = make_match({1: rows}, {1: 10})
    out = R.unlisted_stretches(match)
    assert (out["n"], out["frames"], out["longer_than_50_frames"]) == (3, 7 + 88 + 5, 1)
    assert out["sides"] == {
        "detected_detected": 1,
        "detected_extrapolated": 1,
        "extrapolated_detected": 0,
        "extrapolated_extrapolated": 1,
    }
    assert out["length_median"] == 7


def test_locate_rows_and_players_at() -> None:
    match = make_match({1: line(range(0, 3), 0, 0), 2: line(range(1, 4), 1, 1)}, {1: 10, 2: 20})
    found = locate_rows(match, np.array([1, 1, 2, 2, 9]), np.array([0, 3, 1, 4, 0]))
    assert found[0] >= 0 and found[2] >= 0 and found[1] == found[3] == found[4] == -1
    assert match.player[found[2]] == 2 and match.frame[found[2]] == 1
    assert sorted(match.player[players_at(match, 1)].tolist()) == [1, 2]
    assert match.player[players_at(match, 0)].tolist() == [1]
    assert len(players_at(match, 99)) == 0


# --- events ------------------------------------------------------------------------------------


def test_engager_detection_counts_the_start_and_the_window() -> None:
    seen = [(f, 0.0, 0.0, f != 105) for f in range(90, 121)]  # undetected only at 105
    never = [(f, 0.0, 0.0, True) for f in range(90, 121)]
    match = make_match(
        {5: seen, 6: never},
        {5: 20, 6: 20},
        events=[
            event("on_ball_engagement", 100, 110, 20, 5),  # window 90 to 120: 105 undetected
            event("on_ball_engagement", 105, 106, 20, 5),  # undetected at its start
            event("on_ball_engagement", 100, 110, 20, 6),  # all detected
            event("on_ball_engagement", 300, 310, 20, 6),  # no frames of the player
        ],
    )
    out = engager_detection(match)
    assert out["events"] == 4 and out["at_start_n"] == 3 and out["window_n"] == 3
    assert out["at_start"] == pytest.approx(2 / 3)
    assert out["window_whole"] == pytest.approx(1 / 3)
    first = 30 / 31  # one undetected of 31 frames in [90, 120]; 21 of 22 in [95, 116]
    assert out["window_mean"] == pytest.approx((first + (1 - 1 / 22) + 1.0) / 3)


def test_reception_detection_measures_rivals_by_distance_to_the_carrier() -> None:
    f = range(50, 51)
    match = make_match(
        {
            1: line(f, 0, 0),  # carrier, team 10, detected
            2: line(f, 3, 0),  # rival at 3 m, detected
            3: line(f, 0, 12, detected=False),  # rival at 12 m, extrapolated
            4: line(f, 25, 0),  # rival at 25 m, detected
            5: line(f, 1, 1),  # a team mate: never a rival
        },
        {1: 10, 2: 20, 3: 20, 4: 20, 5: 10},
        events=[event("player_possession", 50, 60, 10, 1)],
    )
    out = reception_detection(match)
    assert out["events"] == 1 and out["carrier_detected"] == 1.0
    within = out["rivals_within"]
    assert (within["5"]["n"], within["5"]["detected"]) == (1, 1.0)  # type: ignore[index]
    assert (within["20"]["n"], within["20"]["detected"]) == (2, 0.5)  # type: ignore[index]
    assert out["rivals_beyond_20"] == {"n": 1, "detected": 1.0}
    assert out["no_rival_within_5"] == 0.0 and out["with_extrapolated_rival_within_5"] == 0.0
    assert out["with_extrapolated_rival_within_10"] == 0.0
    assert out["events_with_rival_within_10"] == 1
    assert out["no_rival_within_10"] == 0.0


def test_the_line_is_the_four_deepest_outfield_defenders_without_the_goalkeeper() -> None:
    f = range(50, 51)
    depths = {20: 50.0, 21: 30.0, 22: 20.0, 23: 10.0, 24: 0.0, 25: -10.0}  # team 20 defends +x
    detected = {20: True, 21: True, 22: False, 23: True, 24: True, 25: False}
    players = {p: line(f, x, 0, detected[p]) for p, x in depths.items()}
    players[1] = line(f, -20, 0)  # attacker, team 10
    # Wider frames so the goalkeeper stands deepest on average: 20 at x=50 all along.
    players[20] = line(range(0, 100), 50.0, 0, detected=False)  # the keeper is not seen
    teams = {p: 20 for p in depths} | {1: 10}
    match = make_match(
        players, teams, events=[event("player_possession", 50, 60, 10, 1)], signs={10: 1, 20: -1}
    )
    assert goalkeepers(match) == {(1, 20): 20, (1, 10): 1}
    out = defensive_line_detection(match)
    # Deepest four without 20: 21 (30, seen), 22 (20, not), 23 (10, seen), 24 (0, seen).
    assert out["events"] == 1
    assert out["detected"] == pytest.approx(3 / 4)
    assert out["all_detected"] == 0.0 and out["deepest_detected"] == 1.0
    assert out["detected_count"] == {"0": 0, "1": 0, "2": 0, "3": 1, "4": 0}


# --- the report and the inventory ------------------------------------------------------------


def test_the_report_text_has_sorted_keys_rounded_numbers_lf_and_no_nan() -> None:
    text = render_report({"b": 1.23456789, "a": {"z": float("nan"), "y": [1, 2]}, "c": None})
    assert text == (
        '{\n  "a": {\n    "y": [\n      1,\n      2\n    ],\n    "z": null\n  },\n'
        '  "b": 1.234568,\n  "c": null\n}\n'
    )
    assert "\r" not in text and json.loads(text)["b"] == 1.234568
    with pytest.raises(TypeError):
        render_report({"a": object()})


def test_the_inventory_comparison_flags_a_figure_outside_the_plans_range() -> None:
    key = "engager.at_start"
    planted = {1874553: {"engager": {"at_start": 0.95}}, 2015213: {"engager": {"at_start": 0.5}}}
    out = inventory.compare(planted, {})
    entry = out["ranges_of_20_matches"][key]  # type: ignore[index]
    assert entry["inside_plan_range"] is False and entry["calibration_low"] == 0.5
    assert inventory.compare({1: {"engager": {"at_start": 0.95}}}, {})["ranges_of_20_matches"][
        key  # type: ignore[index]
    ]["inside_plan_range"]
    assert inventory.leaf({"a": {"b": 2}}, "a.b") == 2.0
    assert inventory.leaf({"a": {"b": None}}, "a.b") is None
    assert inventory.leaf({"a": {}}, "a.b.c") is None


def test_the_inventory_has_ten_matches_and_four_bands() -> None:
    assert len(inventory.MATCH) == len(inventory.M11_PER_MATCH) == 10
    assert set(inventory.M11_POOLED) == {"le_1s", "1_5s", "5_20s", "gt_20s"}
    assert sum(v[0] for v in inventory.M11_POOLED.values()) == 48594
    # Per-match long gaps add up to the pooled long gaps of the table.
    total = sum(
        v["reacquisition.by_band.gt_20s.n_with_jump"] for v in inventory.M11_PER_MATCH.values()
    )
    assert total == inventory.M11_POOLED["gt_20s"][0]
