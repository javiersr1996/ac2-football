"""The cadence probe against paths whose cadence is planted, five seeds.

A planted path is a polyline with a vertex every ``c`` frames (a real update every ``c`` frames,
straight lines between), rounded to the provider's 1 cm grid. Every expected number comes from
``c`` (or, for the gap rule, from a brute-force reference written here), never from the code
under test.

Mutations, each annotated with the test that kills it:

* an estimator with no threshold (``KINK_THRESHOLD = 0``): rounding noise makes every frame a
  kink, the cadence reads 1: ``test_without_a_threshold_the_planted_cadence_is_lost``;
* a threshold below the rounding noise (the simulated p50 of the floor): about half of the
  frames are kinks, the cadence reads 1: ``test_a_threshold_inside_the_noise_loses_the_cadence``;
* a gap that ignores breaks (counts gaps across an extrapolated frame):
  ``test_gaps_match_a_brute_force_reference_on_broken_series``.
"""

from __future__ import annotations

import numpy as np
import pytest
from layer2_helpers import Row, make_match

from ac2fb.reliability import cadence, runs
from ac2fb.reliability.match import MatchData

SEEDS = (1, 2, 3, 4, 5)
FRAMES = 600


def planted_path(rng: np.random.Generator, c: int, offset: int) -> list[Row]:
    """A detected path with a velocity change of at least 0.1 m per frame every ``c`` frames."""
    velocity = rng.normal(0, 0.25, 2)
    point = rng.uniform(-30, 30, 2)
    rows: list[Row] = []
    for f in range(FRAMES):
        if f % c == offset:
            while True:  # a new velocity that differs from the old by at least 0.1 m per frame
                angle, speed = rng.uniform(0, 2 * np.pi), rng.uniform(0.05, 0.5)
                new = speed * np.array([np.cos(angle), np.sin(angle)])
                if np.hypot(*(new - velocity)) >= 0.1:
                    break
            velocity = new
        rows.append((f, round(float(point[0]), 2), round(float(point[1]), 2), True))
        point = point + velocity
    return rows


def planted_match(seed: int, c: int) -> MatchData:
    rng = np.random.default_rng(seed)
    players = {p: planted_path(rng, c, int(rng.integers(0, c))) for p in range(1, 9)}
    return make_match(players, {p: 1 + p % 2 for p in players})


def estimated(match: MatchData, threshold: float = cadence.KINK_THRESHOLD) -> int | None:
    return cadence.cadence_of(cadence.kink_gaps(match, threshold))


# --- the threshold sits above the rounding noise --------------------------------------------------


def test_the_threshold_is_above_the_worst_case_of_the_grid_and_the_simulated_floor() -> None:
    floor = runs.linear_rounding_floor(n=50_000)
    assert abs(cadence.ROUNDING_BOUND - 0.02 * np.sqrt(2)) < 1e-12
    assert floor["p99"] < cadence.ROUNDING_BOUND < cadence.KINK_THRESHOLD
    # An exactly straight rounded path is never a kink: the bound holds on a large sample.
    rng = np.random.default_rng(0)
    start, step = rng.uniform(-50, 50, (100_000, 2)), rng.uniform(-0.7, 0.7, (100_000, 2))
    points = np.round(np.stack([start + k * step for k in range(3)]), 2)
    second = np.hypot(*(points[2] - 2 * points[1] + points[0]).T)
    assert second.max() <= cadence.ROUNDING_BOUND + 1e-9


# --- the planted cadence is recovered -------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("c", [3, 5, 8])
def test_the_planted_cadence_is_recovered(seed: int, c: int) -> None:
    assert estimated(planted_match(seed, c)) == c


@pytest.mark.parametrize("seed", SEEDS)
def test_every_gap_of_a_planted_cadence_of_five_is_a_multiple_of_five(seed: int) -> None:
    gaps = cadence.kink_gaps(planted_match(seed, 5))
    assert len(gaps) > 8 * (FRAMES // 5 - 5)
    assert (gaps % 5 == 0).all()
    assert (gaps == 5).mean() > 0.9  # a vertex only hides when two velocity changes cancel


@pytest.mark.parametrize("seed", SEEDS)
def test_the_planted_report_reads_five_and_a_window_of_ten_frames(seed: int) -> None:
    report = cadence.cadence_report([planted_match(seed, 5)])
    decision = report["decision"]
    assert decision["cadence_frames"] == 5  # type: ignore[index]
    assert decision["g_frames"] == 5  # type: ignore[index]
    assert decision["w_min_frames"] == 10  # type: ignore[index]
    assert decision["w_min_seconds"] == pytest.approx(1.0)  # type: ignore[index]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("c", [3, 5, 8])
def test_the_first_rise_of_the_histogram_is_at_the_planted_cadence(seed: int, c: int) -> None:
    assert cadence.match_cadence(planted_match(seed, c))["first_rise"] == c


@pytest.mark.parametrize("seed", SEEDS)
def test_without_a_threshold_the_planted_cadence_is_lost(seed: int) -> None:
    # Mutation: no threshold. Rounding noise makes (almost) every frame a kink.
    assert estimated(planted_match(seed, 5), 0.0) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_a_threshold_inside_the_noise_loses_the_cadence(seed: int) -> None:
    # Mutation: a threshold below the noise (the simulated median of the floor).
    inside = runs.linear_rounding_floor(n=50_000)["p50"]
    assert inside < cadence.ROUNDING_BOUND
    assert estimated(planted_match(seed, 5), inside) != 5


def test_a_path_that_never_bends_has_no_kink_at_the_chosen_threshold() -> None:
    rng = np.random.default_rng(3)
    players: dict[int, list[Row]] = {}
    for p in range(1, 7):
        start, step = rng.uniform(-30, 30, 2), rng.uniform(-0.5, 0.5, 2)
        players[p] = [
            (f, *(round(float(v), 2) for v in start + f * step), True) for f in range(FRAMES)
        ]
    match = make_match(players, {p: 1 for p in players})
    assert len(cadence.kink_gaps(match)) == 0
    assert len(cadence.kink_gaps(match, 0.0)) > 1000  # rounding alone makes kinks at 0


# --- the gap rule, against a brute-force reference ------------------------------------------------


def reference_gaps(match: MatchData, threshold: float) -> list[int]:
    """Gaps between kinks, written on dicts: a gap counts when every frame between is a centre."""
    out: list[int] = []
    for player in sorted(set(match.player.tolist())):
        rows = match.player == player
        at = {
            int(f): (float(x), float(y), bool(d))
            for f, x, y, d in zip(
                match.frame[rows], match.x[rows], match.y[rows], match.detected[rows], strict=True
            )
        }

        def is_centre(f: int, at: dict[int, tuple[float, float, bool]] = at) -> bool:
            return all(g in at and at[g][2] for g in (f - 1, f, f + 1))

        def second(f: int, at: dict[int, tuple[float, float, bool]] = at) -> float:
            return float(
                np.hypot(
                    at[f + 1][0] - 2 * at[f][0] + at[f - 1][0],
                    at[f + 1][1] - 2 * at[f][1] + at[f - 1][1],
                )
            )

        kinks = [f for f in sorted(at) if is_centre(f) and second(f) > threshold]
        for a, b in zip(kinks, kinks[1:], strict=False):
            if all(is_centre(g) for g in range(a, b + 1)):
                out.append(b - a)
    return out


@pytest.mark.parametrize("seed", SEEDS)
def test_gaps_match_a_brute_force_reference_on_broken_series(seed: int) -> None:
    rng = np.random.default_rng(seed)
    players: dict[int, list[Row]] = {}
    for p in range(1, 7):
        rows = planted_path(rng, int(rng.integers(2, 7)), 0)
        keep: list[Row] = []
        for f, x, y, _ in rows:
            if 200 <= f < 200 + int(rng.integers(1, 30)) and p % 2:  # frames the provider drops
                continue
            keep.append((f, x, y, not (f % 97 < 9 and p % 3 == 0)))  # runs of extrapolation
        players[p] = keep
    match = make_match(players, {p: 1 for p in players})
    for threshold in (0.0, 0.014, cadence.KINK_THRESHOLD):
        got = sorted(cadence.kink_gaps(match, threshold).tolist())
        assert got == sorted(reference_gaps(match, threshold))
    assert len(reference_gaps(match, cadence.KINK_THRESHOLD)) > 100


def test_a_kink_across_an_extrapolated_stretch_makes_no_gap() -> None:
    # Kinks at 10 and 30, the frames 18 to 22 extrapolated between them: no gap of 20.
    def path(det: dict[int, bool]) -> list[Row]:
        x, vx, rows = 0.0, 0.2, []
        for f in range(50):
            if f in (10, 30):
                vx = -vx
            rows.append((f, round(x, 2), 0.0, det.get(f, True)))
            x += vx
        return rows

    gapless = make_match({1: path({f: False for f in range(18, 23)})}, {1: 1})
    whole = make_match({1: path({})}, {1: 1})
    assert cadence.kink_gaps(gapless).tolist() == []
    assert cadence.kink_gaps(whole).tolist() == [20]


# --- the window rule ------------------------------------------------------------------------------


def test_min_window_is_the_larger_of_twice_the_cadence_and_the_p90_gap() -> None:
    assert cadence.min_window([5, 3], [4, 4]) == 10
    assert cadence.min_window([1, 1, 2], [3, 14, 6]) == 14
    assert cadence.min_window([None, 1], [None, 1]) == 2
    with pytest.raises(ValueError):
        cadence.min_window([None], [None])


def test_cadence_of_takes_the_smallest_on_a_tie_and_none_without_gaps() -> None:
    assert cadence.cadence_of(np.array([5, 5, 2, 2, 9], dtype=np.int64)) == 2
    assert cadence.cadence_of(np.array([], dtype=np.int64)) is None
