"""Probe S3: block width and length, the definitions, the selection rule and the visibility figures.

Every expected number is built here from planted geometry, never from the code under test. The
synthetic world: two teams, each with a goalkeeper 45 m behind its own line and ten outfield
players at depths of -35 to +5 m and widths of -30 to +30 m, seen with probability 0.7 (the
goalkeeper always). The provider's numbers are planted with ``reference``, an independent,
loop-based implementation of the eight definitions, so a probe that picks the wrong one, or
measures a definition wrongly, fails.

Mutations, each annotated with the test that kills it:

* the goalkeeper kept when the definition leaves him out, or left out when it keeps him:
  ``test_each_planted_definition_is_the_one_chosen`` (the plan's mutation: with the goalkeeper
  in, the length of an outfield block is off by about ten metres and the reproduction breaks;
  ``test_the_other_goalkeeper_choice_breaks_the_reproduction`` checks it by itself);
* a percentile block measured as extremes, or the reverse: the same test, and
  ``test_measure_by_hand``;
* a block that ignores which players are detected: the same test (population ``detected``);
* width read from ``x`` and length from ``y``: ``test_measure_by_hand``;
* a selection that does not break ties by the difference with the provider, or by position:
  ``test_the_selection_rule``;
* a verdict rule other than 9 of 10: ``test_the_verdict_follows_the_written_rule``;
* any figure that reads a position after the phase's start frame:
  ``test_nothing_after_the_start_frame_is_read``;
* a fixer share that counts the wrong players, or a V1 that ignores detection:
  ``test_the_fixers_of_each_end_by_hand``;
* a rank correlation without tie handling or with the wrong sign: ``test_spearman`` and
  ``test_a_block_that_looks_wider_when_more_is_seen_shows_the_bias``.

The source mutations (script outside the repository) are listed in the plan's record.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pyarrow as pa
import pytest
from layer2_helpers import Row, frames_table, make_match

from ac2fb.defence import block, probe_s3
from ac2fb.defence.block import DEFINITIONS, Definition, measure, name_of, spearman
from ac2fb.defence.probe_s3 import MatchInputs, Phase
from ac2fb.reliability.long import long_table
from ac2fb.reliability.report import render_report

SEEDS = (1, 2, 3, 4, 5)
HOME, AWAY = 100, 200
SIGN = {HOME: 1, AWAY: -1}
KEEPER = {HOME: 1, AWAY: 21}
GAP = 100  # frames between two phases


@dataclass(frozen=True)
class Player:
    id: int
    team: int
    x: float
    y: float
    detected: bool
    keeper: bool


# --- the independent reference of the eight definitions -----------------------------------------


def reference(players: Sequence[Player], d: Definition) -> tuple[float, float]:
    """Width and length of a block under ``d``, with plain loops and sorted lists."""
    pool = [
        p
        for p in players
        if (d.goalkeeper or not p.keeper) and (d.population == "listed" or p.detected)
    ]

    def span(values: list[float]) -> float:
        v = sorted(values)
        if d.extent == "extremes":
            return v[-1] - v[0]

        def quantile(q: float) -> float:
            pos = round(q * (len(v) - 1), 9)
            lo = int(math.floor(pos))
            hi = min(lo + 1, len(v) - 1)
            return v[lo] + (v[hi] - v[lo]) * (pos - lo)

        return quantile(0.95) - quantile(0.05)

    return span([p.y for p in pool]), span([p.x for p in pool])


# --- the synthetic world ------------------------------------------------------------------------


def block_of(rng: np.random.Generator, team: int) -> list[Player]:
    """Eleven players of ``team``: the keeper deep, ten outfield spread at random."""
    ids = range(KEEPER[team], KEEPER[team] + 11)
    out = [
        Player(
            i,
            team,
            SIGN[team] * (-45.0 if i == KEEPER[team] else rng.uniform(-35, 5)),
            float(rng.uniform(-5, 5) if i == KEEPER[team] else rng.uniform(-30, 30)),
            True if i == KEEPER[team] else bool(rng.random() < 0.7),
            i == KEEPER[team],
        )
        for i in ids
    ]
    return out


def build(
    phases: Sequence[tuple[int, list[Player], list[Player]]],
    provider: Sequence[tuple[float | None, float | None]],
    *,
    after: bool = False,
) -> MatchInputs:
    """A match from ``(team_in, home players, away players)`` per phase and the provider numbers.

    Phase ``i`` starts at frame ``GAP * i + 10``. With ``after`` every player also has rows at
    the next two frames, at absurd positions and undetected (a detected one would move
    ``gap_len``, which reads flags and not positions).
    """
    series: dict[int, list[Row]] = {}
    teams: dict[int, int] = {}
    listed: list[Phase] = []
    for i, ((team_in, home, away), (width, length)) in enumerate(
        zip(phases, provider, strict=True)
    ):
        frame = GAP * i + 10
        for p in [*home, *away]:
            teams[p.id] = p.team
            rows = series.setdefault(p.id, [])
            rows.append((frame, p.x, p.y, p.detected))
            if after:
                rows += [(frame + k, 1e4, -1e4, False) for k in (1, 2)]
        listed.append(Phase(i, 1, frame, team_in, width, length))
    match = make_match(series, teams, signs=dict(SIGN))
    flat = frames_table(series, teams)
    return MatchInputs(match=match, phases=tuple(listed), long=long_table(flat))


def world(
    seed: int,
    planted: Definition | None,
    *,
    n: int = 120,
    after: bool = False,
) -> MatchInputs:
    """``n`` phases; the provider's numbers are the reference under ``planted`` (None: noise)."""
    rng = np.random.default_rng(seed)
    phases: list[tuple[int, list[Player], list[Player]]] = []
    provider: list[tuple[float | None, float | None]] = []
    for i in range(n):
        team_in = HOME if i % 2 == 0 else AWAY
        home, away = block_of(rng, HOME), block_of(rng, AWAY)
        out = away if team_in == HOME else home
        phases.append((team_in, home, away))
        if planted is None:
            provider.append((float(rng.uniform(20, 60)), float(rng.uniform(20, 60))))
        else:
            provider.append(reference(out, planted))
    return build(phases, provider, after=after)


def stats_of(inputs: MatchInputs) -> dict[str, dict[str, object]]:
    seen = probe_s3.observe(inputs.match, inputs.phases)
    return {name_of(d): probe_s3.definition_stats(seen, d) for d in DEFINITIONS}


# --- the definitions are found ------------------------------------------------------------------


@pytest.mark.parametrize("planted", DEFINITIONS, ids=name_of)
@pytest.mark.parametrize("seed", SEEDS)
def test_each_planted_definition_is_the_one_chosen(planted: Definition, seed: int) -> None:
    report = probe_s3.s3_report([world(seed, planted)])
    assert report["chosen_definition"] == name_of(planted)
    [match] = report["matches"].values()  # type: ignore[attr-defined]
    assert match["definitions"][name_of(planted)]["reproduces"]
    assert match["definitions"][name_of(planted)]["abs_diff_sum"] == pytest.approx(0, abs=1e-9)


@pytest.mark.parametrize("planted", DEFINITIONS, ids=name_of)
def test_the_other_goalkeeper_choice_breaks_the_reproduction(planted: Definition) -> None:
    # The plan's mutation: with the goalkeeper 45 m back, the length of an outfield block is
    # off by about ten metres, and a block with him is not what an outfield one reproduces.
    flipped = Definition(not planted.goalkeeper, planted.extent, planted.population)
    for seed in SEEDS:
        stats = stats_of(world(seed, planted))
        assert stats[name_of(planted)]["reproduces"]
        other = stats[name_of(flipped)]
        assert not other["reproduces"], (seed, name_of(flipped))
        assert other["length"]["median_abs_diff"] > probe_s3.MAX_MEDIAN_DIFF  # type: ignore[index, operator]


def test_a_provider_that_is_noise_is_reproduced_by_no_definition() -> None:
    stats = stats_of(world(1, None))
    assert not any(s["reproduces"] for s in stats.values())
    report = probe_s3.s3_report([world(1, None)])
    assert report["ranking"][0]["matches_reproducing"] == 0  # type: ignore[index]


def test_too_few_phases_do_not_reproduce() -> None:
    d = DEFINITIONS[0]
    stats = stats_of(world(1, d, n=99))  # the plan-level minimum is 100 pairs
    assert not stats[name_of(d)]["reproduces"]
    assert stats[name_of(d)]["width"]["pearson_r"] == pytest.approx(1)  # type: ignore[index]
    assert stats_of(world(1, d, n=100))[name_of(d)]["reproduces"]


def test_a_difference_over_the_limit_does_not_reproduce() -> None:
    d = DEFINITIONS[0]
    base = world(2, d)
    off = [
        Phase(p.index, p.period, p.frame, p.team_in, p.width + 1.5, p.length)  # type: ignore[operator]
        for p in base.phases
    ]
    shifted = MatchInputs(base.match, tuple(off), base.long)
    stats = stats_of(shifted)[name_of(d)]
    assert stats["width"]["pearson_r"] == pytest.approx(1)  # type: ignore[index]
    assert stats["width"]["median_abs_diff"] == pytest.approx(1.5)  # type: ignore[index]
    assert not stats["reproduces"]


def test_a_few_large_errors_break_the_correlation_but_not_the_median() -> None:
    # 70 % of the provider's lengths are exact and 30 % are off by 10 m: the median difference
    # is 0, so only the correlation (about 0.8) can tell, and both numbers must pass.
    d = DEFINITIONS[0]
    base = world(5, d, n=150)
    rng = np.random.default_rng(0)
    off = [
        Phase(
            p.index,
            p.period,
            p.frame,
            p.team_in,
            p.width,
            p.length + (10.0 * rng.choice([-1, 1]) if rng.random() < 0.3 else 0.0),  # type: ignore[operator]
        )
        for p in base.phases
    ]
    stats = stats_of(MatchInputs(base.match, tuple(off), base.long))[name_of(d)]
    assert stats["length"]["median_abs_diff"] == pytest.approx(0)  # type: ignore[index]
    assert 0.5 < stats["length"]["pearson_r"] < probe_s3.MIN_R  # type: ignore[index, operator]
    assert stats["width"]["pass"] and not stats["length"]["pass"]  # type: ignore[index]
    assert not stats["reproduces"]


def test_phases_without_the_providers_numbers_are_left_out() -> None:
    d = DEFINITIONS[0]
    base = world(3, d, n=150)
    blank = tuple(
        Phase(p.index, p.period, p.frame, p.team_in, None, None) if p.index < 30 else p
        for p in base.phases
    )
    stats = stats_of(MatchInputs(base.match, blank, base.long))[name_of(d)]
    assert stats["width"]["n"] == len(base.phases) - 30  # type: ignore[index]
    assert stats["reproduces"]


# --- the selection rule -------------------------------------------------------------------------


def fake(
    reproduces: dict[str, bool], sums: dict[str, float | None]
) -> dict[str, dict[str, object]]:
    return {
        name_of(d): {
            "reproduces": reproduces.get(name_of(d), False),
            "abs_diff_sum": sums.get(name_of(d), 5.0),
        }
        for d in DEFINITIONS
    }


def test_the_selection_rule() -> None:
    a, b, c, d = (name_of(DEFINITIONS[i]) for i in (0, 1, 2, 3))
    # Most matches reproducing first, whatever the difference.
    stats = {1: fake({a: True, b: True}, {a: 0.1, b: 0.9}), 2: fake({b: True}, {a: 0.1, b: 0.9})}
    assert name_of(probe_s3.select_definition(stats)[0]) == b
    # A tie goes to the lowest mean difference.
    stats = {
        1: fake({a: True, b: True}, {a: 0.9, b: 0.4}),
        2: fake({a: True, b: True}, {a: 0.9, b: 0.4}),
    }
    assert name_of(probe_s3.select_definition(stats)[0]) == b
    # A definition not computable in some match counts as infinite.
    stats = {
        1: fake({a: True, c: True}, {a: None, c: 3.0}),
        2: fake({a: True, c: True}, {a: 0.0, c: 3.0}),
    }
    chosen, ranking = probe_s3.select_definition(stats)
    assert name_of(chosen) == c
    assert [r["definition"] for r in ranking[:2]] == [c, a]
    assert next(r for r in ranking if r["definition"] == a)["mean_abs_diff_sum"] is None
    # A remaining tie goes to the earlier one in DEFINITIONS.
    stats = {1: fake({d: True, c: True}, {d: 1.0, c: 1.0})}
    assert name_of(probe_s3.select_definition(stats)[0]) == c
    with pytest.raises(ValueError):
        probe_s3.select_definition({})


def test_the_verdict_follows_the_written_rule() -> None:
    ten = {m: True for m in range(10)}
    assert probe_s3.verdict(ten)["c3_survives_probe"] is True
    assert probe_s3.verdict({**ten, 0: False})["c3_survives_probe"] is True
    assert probe_s3.verdict({**ten, 0: False, 1: False})["c3_survives_probe"] is False
    assert probe_s3.verdict({m: True for m in range(9)})["c3_survives_probe"] is None
    assert probe_s3.verdict({m: True for m in range(9)})["complete"] is False


# --- measure and rank correlation, by hand ------------------------------------------------------


def arrays(
    xs: Sequence[float], ys: Sequence[float], det: Sequence[bool] | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(xs)
    return (
        np.array(xs, dtype=float),
        np.array(ys, dtype=float),
        np.array(det if det is not None else [True] * n, dtype=bool),
        np.arange(1, n + 1, dtype=np.int64),
    )


def test_measure_by_hand() -> None:
    # Players (id: x, y): 1: 9, 0; 2: 2, 10; 3: 3, 20; 4: 5, 30; 5: 7, 40; 6: 1, 100 (unsorted).
    ids = np.array([3, 1, 6, 2, 5, 4], dtype=np.int64)
    x = np.array([3.0, 9.0, 1.0, 2.0, 7.0, 5.0])
    y = np.array([20.0, 0.0, 100.0, 10.0, 40.0, 30.0])
    det = np.ones(6, dtype=bool)
    m = measure(x, y, det, ids, None, Definition(True, "extremes", "listed"))
    assert m is not None
    assert m.width == pytest.approx(100.0)  # y from 0 (player 1) to 100 (player 6)
    assert m.length == pytest.approx(8.0)  # x from 1 (player 6) to 9 (player 1)
    assert m.players == 6
    assert m.fixers == {"x_low": (6,), "x_high": (1,), "y_low": (1,), "y_high": (6,)}
    pct = measure(x, y, det, ids, None, Definition(True, "p5_p95", "listed"))
    assert pct is not None
    # y sorted 0 10 20 30 40 100 (players 1 to 6): position 0.25 -> 2.5, position 4.75 -> 85.
    assert pct.width == pytest.approx(82.5)
    # x sorted 1 2 3 5 7 9 (players 6 2 3 4 5 1): 1.25 and 7 + 0.75 * 2 = 8.5.
    assert pct.length == pytest.approx(7.25)
    assert pct.fixers == {"x_low": (2, 6), "x_high": (1, 5), "y_low": (1, 2), "y_high": (5, 6)}


def test_measure_keeper_and_detection() -> None:
    x, y, det, ids = arrays([0, 1, 2, 3, 4, 5, 6], [0, 1, 2, 3, 4, 5, -500], [True] * 6 + [True])
    keeper = int(ids[-1])
    without = measure(x, y, det, ids, keeper, Definition(False, "extremes", "listed"))
    with_gk = measure(x, y, det, ids, keeper, Definition(True, "extremes", "listed"))
    assert without is not None and with_gk is not None
    assert (without.width, with_gk.width) == (pytest.approx(5.0), pytest.approx(505.0))
    assert without.players == 6 and with_gk.players == 7
    # Only detected players: one undetected extreme drops out and the width shrinks.
    seen = det.copy()
    seen[5] = False
    only = measure(x, y, seen, ids, keeper, Definition(False, "extremes", "detected"))
    assert only is not None and only.width == pytest.approx(4.0) and only.players == 5
    assert measure(x, y, seen, ids, keeper, Definition(False, "extremes", "listed")) is not None


def test_measure_needs_enough_players_and_finite_coordinates() -> None:
    x, y, det, ids = arrays(range(block.MIN_PLAYERS - 1), range(block.MIN_PLAYERS - 1))
    d = Definition(True, "extremes", "listed")
    assert measure(x, y, det, ids, None, d) is None
    x, y, det, ids = arrays(range(block.MIN_PLAYERS), range(block.MIN_PLAYERS))
    assert measure(x, y, det, ids, None, d) is not None
    assert measure(x, y, det, ids, int(ids[0]), Definition(False, "extremes", "listed")) is None
    y[0] = np.nan
    assert measure(x, y, det, ids, None, d) is None


def test_the_eight_definitions_are_distinct_and_named() -> None:
    assert len(DEFINITIONS) == 8 and len(set(DEFINITIONS)) == 8
    assert len({name_of(d) for d in DEFINITIONS}) == 8
    assert name_of(Definition(False, "extremes", "listed")) == "outfield_extremes_listed"
    assert name_of(Definition(True, "p5_p95", "detected")) == "with_gk_p5_p95_detected"


def average_ranks(values: Sequence[float]) -> list[float]:
    out = []
    for v in values:
        below = sum(w < v for w in values)
        equal = sum(w == v for w in values)
        out.append(below + (equal + 1) / 2)
    return out


def test_spearman() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert spearman(a, a * 10) == pytest.approx(1.0)
    assert spearman(a, -a) == pytest.approx(-1.0)
    # With ties: compared with the definition, Pearson of loop-made average ranks.
    p = [1, 1, 2, 3, 3, 3, 7, 8]
    q = [5, 3, 3, 9, 1, 1, 2, 8]
    expected = float(np.corrcoef(average_ranks(p), average_ranks(q))[0, 1])
    assert spearman(np.array(p, dtype=float), np.array(q, dtype=float)) == pytest.approx(expected)
    assert spearman(np.array([1.0, 1.0, 1.0]), np.array([1.0, 2.0, 3.0])) is None
    assert spearman(np.array([1.0, 2.0]), np.array([1.0, 2.0])) is None
    with pytest.raises(ValueError):
        spearman(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0]))


# --- who fixes the ends, and the bias of the camera ---------------------------------------------


def hand_world() -> MatchInputs:
    """One phase: AWAY defends. Outfield 22..27 at y = -20 -10 0 5 10 25 and x = 3 6 1 2 5 4."""
    ys = {22: -20.0, 23: -10.0, 24: 0.0, 25: 5.0, 26: 10.0, 27: 25.0}
    xs = {22: 3.0, 23: 6.0, 24: 1.0, 25: 2.0, 26: 5.0, 27: 4.0}
    seen = {22: False, 24: False}  # the fixers of y_low and of x_low are not seen
    away = [Player(21, AWAY, 45.0, 0.0, True, True)] + [
        Player(i, AWAY, xs[i], ys[i], seen.get(i, True), False) for i in ys
    ]
    home = [Player(i, HOME, -10.0 - i, float(i), True, i == 1) for i in range(1, 7)]
    return build([(HOME, home, away)], [(45.0, 5.0)])


def test_the_fixers_of_each_end_by_hand() -> None:
    inputs = hand_world()
    d = Definition(False, "extremes", "listed")
    figures = probe_s3.match_figures(inputs, d)["fixers"]  # type: ignore[index]
    expected = {
        "y_low": 1.0,
        "y_high": 0.0,
        "x_low": 1.0,
        "x_high": 0.0,
        "width": 0.5,
        "length": 0.5,
    }
    for name, share in expected.items():
        sens = figures[name]  # type: ignore[index]
        assert sens["n_units"] == 1, name
        assert sens["v0"]["n"] == 1, name
        assert sens["extrapolated_fraction"] == pytest.approx(share), name
        assert sens["v1"]["n"] == (1 if share == 0 else 0), name
    assert figures["width"]["v0"]["mean"] == pytest.approx(45.0)  # type: ignore[index]
    assert figures["length"]["v0"]["mean"] == pytest.approx(5.0)  # type: ignore[index]
    assert figures["y_high"]["v0"]["mean"] == pytest.approx(45.0)  # type: ignore[index]
    # The same block under the goalkeeper-in definition has a longer length and the same shares.
    longer = probe_s3.match_figures(inputs, Definition(True, "extremes", "listed"))["fixers"]
    assert longer["length"]["v0"]["mean"] == pytest.approx(44.0)  # type: ignore[index]


def test_two_phases_at_the_same_frame_are_refused() -> None:
    base = hand_world()
    twice = (*base.phases, Phase(9, 1, base.phases[0].frame, HOME, None, None))
    with pytest.raises(ValueError, match="same frame"):
        probe_s3.make_metric(base.match, twice, DEFINITIONS[0], "width")


def wide_when_seen(seed: int, n: int = 120) -> tuple[MatchInputs, list[int]]:
    """Phases where the detected outfield players spread over +-3k m and the others stand at 0."""
    rng = np.random.default_rng(seed)
    phases: list[tuple[int, list[Player], list[Player]]] = []
    counts: list[int] = []
    for _ in range(n):
        k = 5 + int(rng.integers(0, 6))  # detected outfield players of the defending team
        counts.append(k)
        away = [Player(21, AWAY, 45.0, 0.0, True, True)]
        spread = np.linspace(-3 * k, 3 * k, k)
        for j in range(10):
            seen = j < k
            away.append(
                Player(
                    22 + j,
                    AWAY,
                    (-35.0, 5.0)[j] if j < 2 else float(rng.uniform(-35, 5)),  # fixed length
                    float(spread[j]) if seen else 0.0,
                    seen,
                    False,
                )
            )
        phases.append((HOME, block_of(rng, HOME), away))
    return build(phases, [(40.0, 40.0)] * n), counts


def bias(inputs: MatchInputs, d: Definition) -> dict[str, object]:
    return probe_s3.match_figures(inputs, d)["visibility_bias"]  # type: ignore[return-value]


def test_a_block_that_looks_wider_when_more_is_seen_shows_the_bias() -> None:
    for seed in SEEDS:
        inputs, counts = wide_when_seen(seed)
        planted = bias(inputs, Definition(False, "extremes", "detected"))
        assert planted["width"]["block_detected_vs_own"] == pytest.approx(1.0)  # type: ignore[index]
        assert planted["block_detected"] == pytest.approx(np.mean(counts) / 10)
        # The length is 40 m however many are seen: a constant has no rank correlation.
        assert planted["length"]["block_detected_vs_own"] is None  # type: ignore[index]


def test_a_block_independent_of_what_is_seen_shows_no_bias() -> None:
    for seed in SEEDS:
        inputs = world(seed, None, n=200)
        d = Definition(False, "extremes", "listed")
        b = bias(inputs, d)
        assert abs(b["width"]["block_detected_vs_own"]) < 0.35  # type: ignore[index]
        assert abs(b["length"]["block_detected_vs_own"]) < 0.35  # type: ignore[index]
        assert b["width"]["n_provider"] == 200  # type: ignore[index]


def test_nothing_after_the_start_frame_is_read() -> None:
    for planted in (DEFINITIONS[0], DEFINITIONS[5]):
        plain = probe_s3.s3_report([world(4, planted)])
        later = probe_s3.s3_report([world(4, planted, after=True)])
        assert render_report(plain) == render_report(later)


# --- the provider's phases ----------------------------------------------------------------------


def test_phases_from_bronze() -> None:
    table = pa.table(
        {
            "index": [0, 1, 2, 3],
            "period": [1, 1, None, 2],
            "frame_start": [10, 20, 30, None],
            "team_in_possession_id": [100, None, 100, 200],
            "team_out_of_possession_width_start": [41.5, 1.0, 2.0, 3.0],
            "team_out_of_possession_length_start": [None, 2.0, 3.0, 4.0],
        }
    )
    assert probe_s3.phases_from(table) == [Phase(0, 1, 10, 100, 41.5, None)]
