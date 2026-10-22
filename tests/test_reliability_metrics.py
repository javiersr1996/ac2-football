"""Task 25: the metrics of the reliability map, on hand-made and random worlds.

Every expected number is written here from the planted geometry, never taken from the code under
test. The definitions are written again in ``reliability.metrics`` (the reading of the held-out
may run no code of ``defence/``), so each one is also held equal to its original in ``defence/``
on random worlds (seeds 1 to 5), and the constants are compared.

Mutations, each with the test that kills it (script and log in the task's record):

* a line that keeps the goalkeeper, or that ranks by x without the attack sign:
  ``test_the_line_height_and_its_reaction_are_the_planted_ones``;
* a metric that reports no players, or a sensitivity that ignores ``is_detected`` (V1 = V0):
  ``test_the_variants_follow_who_was_detected``;
* a reader that takes the sign of another period or team (the sign of period 1, of team 1, or of
  the first key): ``test_both_teams_in_both_periods_give_the_same_metric``, which moves the long
  table too, for ``pressure.make_metric`` and for each metric that reads ``attack_sign``;
* a near rival that is any weight above zero, or a tolerance as large as a real weight:
  ``test_the_near_cut_is_between_float_noise_and_a_real_weight``;
* a block of fewer than five players, extremes that are not the extreme players, or fixers
  that swap their ties: ``test_the_block_is_the_planted_one``,
  ``test_the_ends_of_the_block_break_ties_like_the_original``.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Sequence

import numpy as np
import pyarrow as pa
import pytest
from effect_helpers import OFFSET, mixed
from layer2_helpers import Row, event, make_match

from ac2fb.defence import block, line, power, pressure, probe_s1, probe_s3
from ac2fb.defence.line import LineReception
from ac2fb.defence.pressure import Reception
from ac2fb.reliability import metrics
from ac2fb.reliability.match import Event, MatchData
from ac2fb.reliability.sensitivity import (
    Metric,
    Reading,
    Sensitivity,
    Window,
    WindowFrames,
    sensitivity,
)

W = metrics.INCOMING_WINDOW
FIRSTS = (100, 200)  # the frames t of the two possessions of the planted world
SEEDS = (1, 2, 3, 4, 5)

# --- the planted world: a carrier, a goalkeeper, six outfield rivals ---------------------------

AT_T = {  # player: (x, y) at t; the carrier (1, team 1) attacks +x, the rivals are team 2
    1: (0.0, 0.0),
    11: (30.0, 0.0),
    12: (25.0, 5.0),
    13: (20.0, -5.0),
    14: (3.0, 0.0),
    15: (6.0, 2.0),
    16: (-5.0, 0.0),
    20: (45.0, 0.0),  # the goalkeeper: the deepest of the team, not in the line
}
BACK = {11: 3.0, 12: 2.0, 13: 1.0}  # metres shallower than at t, W frames before t
TEAMS = {1: 1, **{p: 2 for p in AT_T if p != 1}}
INDEX = 0.7 + (1 - math.hypot(6, 2) / 10) * (1 + 6 / math.hypot(6, 2)) / 2  # rivals 14 and 15


def planted_match(
    not_detected: Sequence[tuple[int, int]] = (), unlisted: Sequence[tuple[int, int]] = ()
) -> MatchData:
    """Both possessions, every player listed from t - W to t; ``(player, frame)`` to hide."""
    rows: dict[int, list[Row]] = {p: [] for p in AT_T}
    for t in FIRSTS:
        for p, (x, y) in AT_T.items():
            for f in range(t - W, t + 1):
                if (p, f) not in unlisted:
                    shallow = BACK.get(p, 0.0) * (1 - (f - (t - W)) / W)
                    rows[p].append((f, x - shallow, y, (p, f) not in not_detected))
    events = [event("player_possession", t, t, 1, 1) for t in FIRSTS]
    return make_match(rows, TEAMS, events=events, signs={1: 1, 2: -1})


def long_of(match: MatchData) -> pa.Table:
    """The long table of a match from its arrays (so a world that was moved moves it too)."""
    k = len(match.ball_frame)
    return pa.table(
        {
            "match_id": [f"fb:{match.match_id}"] * (len(match.player) + k),
            "period": pa.array(np.r_[match.period, match.ball_period], pa.int16()),
            "frame": np.r_[match.frame, match.ball_frame],
            "player_id": pa.array([*match.player.tolist(), *[None] * k], pa.int64()),
            "team_id": pa.array([*match.team.tolist(), *[None] * k], pa.int64()),
            "x": np.r_[match.x, match.ball_x],
            "y": np.r_[match.y, match.ball_y],
            "is_detected": np.r_[match.detected, match.ball_detected],
            "gap_len": pa.array(np.r_[match.gap, match.ball_gap], pa.int32()),
        }
    )


def run(match: MatchData, metric: Metric, windows: Sequence[Window]) -> Sensitivity:
    return sensitivity(metric, long_of(match), windows)[match.match_id]


def reading(match: MatchData, metric: Metric, window: Window) -> Reading | None:
    """What the metric returns for one window, captured through the real sensitivity."""
    seen: list[Reading | None] = []

    def spy(frames: WindowFrames) -> Reading | None:
        seen.append(metric(frames))
        return seen[-1]

    sensitivity(spy, long_of(match), [window])
    return seen[0]


def at_t(events: Sequence[Event], match_id: int) -> list[Window]:
    return [Window(match_id, e.frame_start, e.frame_start) for e in events]


def before_t(events: Sequence[Event], match_id: int) -> list[Window]:
    return [Window(match_id, e.frame_start - W, e.frame_start) for e in events]


def test_the_pressure_and_the_nearest_rival_are_the_planted_ones() -> None:
    match = planted_match()
    held = metrics.possessions(match.events)
    window = Window(match.match_id, 100, 100)
    got = reading(match, metrics.pressure_index(match, held), window)
    assert got is not None and got.value == pytest.approx(INDEX)
    assert got.player_ids == (14, 15)  # 16 is straight behind the carrier: weight 0, not near
    assert reading(match, metrics.nearest_rival(held), window) == Reading(3.0, (14,))


def test_the_line_height_and_its_reaction_are_the_planted_ones() -> None:
    # The line is 11, 12, 13 and 15 (depths 30, 25, 20, 6); the goalkeeper (45) is left out.
    match = planted_match()
    held = metrics.possessions(match.events)
    height = reading(match, metrics.line_height(match, held), Window(match.match_id, 100, 100))
    assert height == Reading(81 / 4, (11, 12, 13, 15))
    ahead = reading(match, metrics.line_reaction(match, held), Window(match.match_id, 100 - W, 100))
    assert ahead == Reading(1.5, (11, 12, 13, 15))  # (3 + 2 + 1 + 0) / 4 metres: it retreats


def test_a_line_needs_the_four_listed_at_both_ends() -> None:
    match = planted_match(unlisted=[(13, 100 - W)])
    held = metrics.possessions(match.events)
    assert reading(match, metrics.line_reaction(match, held), before_t(held, 7)[0]) is None
    assert reading(match, metrics.line_height(match, held), at_t(held, 7)[0]) is not None


def test_the_block_is_the_planted_one() -> None:
    # Team 2 out of possession at t: y from -20 to 30 (width 50), x from 10 to 55 (length 45).
    xs = [10.0, 20.0, 25.0, 33.0, 40.0, 55.0]
    ys = [-20.0, -5.0, 0.0, 8.0, 15.0, 30.0]
    rivals = {20 + i: [(100, x, y, True)] for i, (x, y) in enumerate(zip(xs, ys, strict=True))}
    pool = {1: [(100, 0.0, 0.0, True)], **rivals}
    teams = {1: 1, **{p: 2 for p in rivals}}
    events = [event("phases_of_play", 100, 100, 1, None)]
    window = Window(7, 100, 100)

    def block_of(who: Sequence[int], what: str) -> Reading | None:
        match = make_match(
            {p: pool[p] for p in who},
            {p: teams[p] for p in who},
            events=events,
            signs={1: 1, 2: -1},
        )
        return reading(match, metrics.block_extent(metrics.phases(match.events), what), window)

    everyone = (1, 20, 21, 22, 23, 24, 25)
    assert block_of(everyone, "width") == Reading(50.0, (20, 25))  # lowest y, highest y
    assert block_of(everyone, "length") == Reading(45.0, (20, 25))  # lowest x, highest x
    assert block_of(everyone, "area") == Reading(2250.0, (20, 25))
    assert block_of((1, 20, 21, 22, 23), "width") is None  # four players are not a block
    assert block_of((1, 20, 21, 22, 23, 24), "width") is not None


def test_the_ends_of_the_block_break_ties_like_the_original() -> None:
    # Two players at the lowest x and two at the highest: the stable sort takes the first of the
    # lowest and the last of the highest, in the order of the ids.
    ys = {20: 0.0, 21: 1.0, 22: 2.0, 23: 3.0, 24: 4.0, 25: 5.0}
    xs = {20: 10.0, 21: 10.0, 22: 20.0, 23: 30.0, 24: 40.0, 25: 40.0}
    rows = {p: [(100, xs[p], ys[p], True)] for p in ys}
    match = make_match(
        {1: [(100, 0.0, 0.0, True)], **rows},
        {1: 1, **{p: 2 for p in rows}},
        events=[event("phases_of_play", 100, 100, 1, None)],
        signs={1: 1, 2: -1},
    )
    got = reading(
        match, metrics.block_extent(metrics.phases(match.events), "length"), Window(7, 100, 100)
    )
    assert got == Reading(30.0, (20, 25))


def test_the_variants_follow_who_was_detected() -> None:
    # Rival 15 (near, in the line) is not detected at frame 195, W - 5 frames before the second
    # possession: the unit leaves V1 of every metric whose window reaches it.
    match = planted_match(not_detected=[(15, 195)])
    held = metrics.possessions(match.events)
    index = metrics.pressure_index(match, held)
    here = run(match, index, at_t(held, 7))
    assert (here.v0.n, here.v1.n, here.extrapolated_fraction) == (2, 2, 0.0)
    wide = run(match, index, [Window(7, e.frame_start - 5, e.frame_start) for e in held])
    assert (wide.v0.n, wide.v1.n) == (2, 1)
    assert [(s.detected_players, s.n) for s in wide.v2] == [(1, 1), (2, 1)]
    reaction = run(match, metrics.line_reaction(match, held), before_t(held, 7))
    assert (reaction.v0.n, reaction.v1.n) == (2, 1)
    assert [(s.detected_players, s.n) for s in reaction.v2] == [(3, 1), (4, 1)]
    assert reaction.extrapolated_fraction == pytest.approx(1 / (4 * (W + 1) * 2))
    assert reaction.gap_len.max == 1


# --- the signs: both teams in both periods, the long table moved too ---------------------------


def to_events(receptions: Sequence[Reception]) -> list[Event]:
    return [
        Event("player_possession", None, r.frame, r.frame, r.period, r.team, r.player)
        for r in receptions
    ]


# name: (build the metric from the match, the receptions and their events; the windows of a unit)
SIGNED: dict[str, tuple[Callable[..., Metric], Callable[[Sequence[Event], int], list[Window]]]] = {
    "pressure.make_metric": (lambda m, recs, ev: pressure.make_metric(m, recs), at_t),
    "pressure_index": (lambda m, recs, ev: metrics.pressure_index(m, ev), at_t),
    "line_height": (lambda m, recs, ev: metrics.line_height(m, ev), at_t),
    "line_reaction": (lambda m, recs, ev: metrics.line_reaction(m, ev), before_t),
}


def planted_inputs(not_detected: Sequence[tuple[int, int]]) -> power.C1Inputs:
    match = planted_match(not_detected)
    receptions = tuple(Reception(f"e{k}", 1, t, 1, 1, 1) for k, t in enumerate(FIRSTS))
    s1 = probe_s1.MatchInputs(match, long_of(match), receptions, len(receptions))
    return power.C1Inputs(s1, {r.event_id: f"p{k}" for k, r in enumerate(receptions)})


def renumbered(inputs: power.C1Inputs) -> power.C1Inputs:
    """The world of :func:`mixed` with every player of quadrant ``k`` renumbered by ``+ 1000 k``.

    The long table gives a player the team of its first row, so a player must keep one team in
    the whole match, which ``mixed`` (the same ids on both sides) does not.
    """
    m = inputs.s1.match
    player = m.player + 1000 * (m.frame // OFFSET)
    order = np.lexsort((m.frame, player))
    rows = {
        f: getattr(m, f)[order] for f in ("team", "period", "frame", "x", "y", "detected", "gap")
    }
    frame_order = np.argsort(rows["frame"], kind="stable")
    match = dataclasses.replace(
        m,
        player=player[order],
        **rows,
        key=player[order] * (1 << 32) + rows["frame"],
        frame_order=frame_order,
        frame_sorted=rows["frame"][frame_order],
    )
    receptions = tuple(
        dataclasses.replace(r, player=r.player + 1000 * (r.frame // OFFSET))
        for r in inputs.s1.receptions
    )
    return dataclasses.replace(
        inputs, s1=dataclasses.replace(inputs.s1, match=match, receptions=receptions)
    )


@pytest.mark.parametrize("other", [2, 7])
@pytest.mark.parametrize("name", list(SIGNED))
def test_both_teams_in_both_periods_give_the_same_metric(name: str, other: int) -> None:
    # One match, one attack_sign as a real one lists it (``mixed``: the carrier's team and the
    # other, in both periods, the long table rebuilt from the moved arrays). Each unit must read
    # the sign of its own period and team: the four copies of the base unit give the base metric.
    build, windows = SIGNED[name]
    base = planted_inputs([(15, 195)])
    both = renumbered(mixed(base, other))
    got_match = both.s1.match
    want = run(
        base.s1.match,
        build(base.s1.match, base.s1.receptions, to_events(base.s1.receptions)),
        windows(to_events(base.s1.receptions), base.s1.match.match_id),
    )
    events = to_events(both.s1.receptions)
    got = run(
        got_match,
        build(got_match, both.s1.receptions, events),
        windows(events, got_match.match_id),
    )
    assert want.v0.n == 2 and want.v0.mean is not None and want.v0.mean > 0
    assert (got.n_units, got.v0.n, got.v1.n) == (4 * want.n_units, 4 * want.v0.n, 4 * want.v1.n)
    assert got.v0.mean == pytest.approx(want.v0.mean, rel=1e-12)
    assert got.v1.mean == pytest.approx(want.v1.mean, rel=1e-12)
    assert [(s.detected_players, s.n) for s in got.v2] == [
        (s.detected_players, 4 * s.n) for s in want.v2
    ]
    assert got.extrapolated_fraction == pytest.approx(want.extrapolated_fraction, rel=1e-12)


# --- the near cut: between float noise and a real weight ---------------------------------------

CARRIER = (2.3, -16.4)  # the rival below is exactly behind it on the line to the goal (52.5, 0)
BEHIND = (-5.23, -18.86)


def lone_rival(rival: tuple[float, float], carrier: tuple[float, float] = (0.0, 0.0)) -> MatchData:
    return make_match(
        {1: [(100, *carrier, True)], 11: [(100, *rival, True)]},
        {1: 1, 11: 2},
        events=[event("player_possession", 100, 100, 1, 1)],
        signs={1: 1, 2: -1},
    )


NEAR_CASES = [
    ("collinear behind: weight 0 on paper, 1e-17 in floats", CARRIER, BEHIND, ()),
    ("a hair inside the radius: 1e-14, still noise", (0.0, 0.0), (10 - 1e-13, 0.0), ()),
    ("exactly at the radius", (0.0, 0.0), (10.0, 0.0), ()),
    ("a real weight, 1e-10", (0.0, 0.0), (10 - 1e-9, 0.0), (11,)),
    ("straight ahead at 3 m", (0.0, 0.0), (3.0, 0.0), (11,)),
]


@pytest.mark.parametrize("name", ["pressure.make_metric", "pressure_index"])
@pytest.mark.parametrize(("why", "carrier", "rival", "near"), NEAR_CASES)
def test_the_near_cut_is_between_float_noise_and_a_real_weight(
    name: str,
    why: str,
    carrier: tuple[float, float],
    rival: tuple[float, float],
    near: tuple[int, ...],
) -> None:
    match = lone_rival(rival, carrier)
    receptions = [Reception("e", 1, 100, 1, 1, 1)]
    build = SIGNED[name][0]
    got = reading(match, build(match, receptions, to_events(receptions)), Window(7, 100, 100))
    assert got is not None and got.player_ids == near, why


@pytest.mark.parametrize(("why", "carrier", "rival", "near"), NEAR_CASES)
def test_the_scored_receptions_cut_the_near_rivals_the_same_way(
    why: str, carrier: tuple[float, float], rival: tuple[float, float], near: tuple[int, ...]
) -> None:
    match = lone_rival(rival, carrier)
    (scored,) = pressure.score_receptions(match, [Reception("e", 1, 100, 1, 1, 1)])
    assert scored.near_players == near, why


def test_the_collinear_rival_really_weighs_noise_not_nothing() -> None:
    # The case above would not test the cut if the float weight were exactly zero.
    weights = metrics.rival_weights(CARRIER, np.array([BEHIND]), 1)
    assert 0 < weights[0] < 1e-15 < metrics.NEAR_WEIGHT < 1e-9


# --- the definitions equal the originals --------------------------------------------------------


def random_world(seed: int) -> tuple[MatchData, list[Event], list[Event]]:
    """Two teams of eleven that wander (rows missing, players undetected); possessions, phases."""
    rng = np.random.default_rng(seed)
    teams = {p: 1 if p <= 11 else 2 for p in range(1, 23)}
    pos = rng.uniform([-40.0, -28.0], [40.0, 28.0], size=(22, 2))
    pos[10], pos[21] = (-48.0, 0.0), (48.0, 0.0)  # the goalkeepers: players 11 and 22
    rows: dict[int, list[Row]] = {p: [] for p in teams}
    for f in range(80, 301):
        pos = pos + rng.normal(0.0, 0.5, size=(22, 2))
        for i, p in enumerate(teams):
            if rng.random() < 0.97:
                rows[p].append((f, float(pos[i, 0]), float(pos[i, 1]), bool(rng.random() < 0.75)))
    held, phases = [], []
    for k, t in enumerate((120, 160, 200, 240, 280)):
        team = 1 + k % 2
        carrier = int(rng.integers(1, 12)) + 11 * (team - 1)
        held.append(event("player_possession", t, t, team, carrier))
        phases.append(event("phases_of_play", t - 7, t - 7, 1 + (k + 1) % 2, None))
    match = make_match(rows, teams, events=held + phases, signs={1: 1, 2: -1})
    return match, metrics.possessions(match.events), metrics.phases(match.events)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_definitions_equal_the_originals(seed: int) -> None:
    match, held, phases = random_world(seed)
    mid = match.match_id
    # the index
    receptions = [
        Reception(str(i), e.period, e.frame_start, e.team or 0, e.player or 0, 1)
        for i, e in enumerate(held)
    ]
    assert run(match, pressure.make_metric(match, receptions), at_t(held, mid)) == run(
        match, metrics.pressure_index(match, held), at_t(held, mid)
    )
    # the line, against the units of defence/line.py
    units, _ = line.build_units(
        match,
        [
            LineReception(str(i), e.period, e.frame_start, e.team or 0, e.player or 0, None, None)
            for i, e in enumerate(held)
        ],
        [0, W],
    )
    by_frame = {u.reception.frame: u for u in units}
    assert len(by_frame) >= 3

    def original(kind: str) -> Metric:
        def metric(window: WindowFrames) -> Reading | None:
            u = by_frame.get(window.window.frame_end)
            if u is None or (kind == "reaction" and not math.isfinite(u.depth[W])):
                return None
            return Reading(u.depth[0] - (u.depth[W] if kind == "reaction" else 0.0), u.line)

        return metric

    for kind, mine, windows in (
        ("height", metrics.line_height(match, held), at_t(held, mid)),
        ("reaction", metrics.line_reaction(match, held), before_t(held, mid)),
    ):
        got = run(match, mine, windows)
        assert got == run(match, original(kind), windows)
        assert got.v0.n >= 3
    # the block, against probe S3 under the definition it chose
    definition = next(d for d in block.DEFINITIONS if block.name_of(d) == power.C3_DEFINITION)
    originals = [
        probe_s3.Phase(i, e.period, e.frame_start, e.team or 0, None, None)
        for i, e in enumerate(phases)
    ]
    for what in ("width", "length"):
        windows = at_t(phases, mid)
        theirs = probe_s3.make_metric(match, originals, definition, what)
        got = run(match, metrics.block_extent(phases, what), windows)
        assert got == run(match, theirs, windows) and got.v0.n >= 3


@pytest.mark.parametrize("seed", SEEDS)
def test_the_weights_equal_the_originals(seed: int) -> None:
    rng = np.random.default_rng(seed)
    rivals = rng.uniform([-52.0, -34.0], [52.0, 34.0], size=(400, 2))
    rivals[:50] = np.round(rivals[:50], 0)  # lattice points: ties, zero norms and exact cuts
    for sign in (1, -1):
        for carrier in ((0.0, 0.0), (52.5 * sign, 0.0), (-10.5, 7.25), (3.0, -4.0)):
            assert np.array_equal(
                metrics.rival_weights(carrier, rivals, sign),
                pressure.rival_weights(carrier, rivals, sign),
            )


def test_the_constants_equal_the_originals() -> None:
    assert metrics.GOAL_X == pressure.GOAL_X and metrics.RADIUS == pressure.RADIUS
    assert metrics.NEAR_WEIGHT == pressure.NEAR_WEIGHT
    assert metrics.INCOMING_WINDOW == pressure.INCOMING_WINDOW
    assert metrics.LINE_SIZE == line.LINE_SIZE
    assert metrics.MIN_BLOCK == block.MIN_PLAYERS
    assert power.C3_DEFINITION == "with_gk_extremes_listed"


def test_two_events_at_one_frame_are_an_error() -> None:
    twice = [Event("player_possession", None, 5, 5, 1, 1, p) for p in (1, 2)]
    with pytest.raises(ValueError, match="same frame"):
        metrics.possessions(twice)
    with pytest.raises(ValueError, match="same frame"):
        metrics.phases([dataclasses.replace(twice[0], family="phases_of_play")] * 2)
