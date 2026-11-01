"""The metrics of the reliability map, each as a layer 2 metric of ``reliability.sensitivity``.

Seven metrics, all read at the instant ``t`` of a provider event (the last frame of the window)
or, for the line's reaction, in the ``W`` frames before it. Nothing is read after ``t``. Every
one is a function of one unit (a window of frames) that returns a value and the players it was
computed from, so V1 keeps the units whose players were detected throughout the window and V2
splits them by how many of those were (k) out of how many the unit has (n).

Units come from the match's events, not from any report: a *possession* is a provider
``player_possession`` event with a team and a player (``t`` = its ``frame_start``, the carrier
is its player); a *phase* is a ``phases_of_play`` event with a team (``t`` = its
``frame_start``, the team in possession is its team, the block is the other one).

- ``pressure_index``: the geometric index of ``ac2fb.defence.pressure`` at ``t``, from the
  rivals within :data:`RADIUS` metres of the carrier (weight above :data:`NEAR_WEIGHT`).
- ``nearest_rival_m``: distance in metres from the carrier to the nearest rival listed at ``t``.
- ``line_height_m``: mean depth (x times the carrier team's attack sign, so larger is nearer
  the rivals' own goal) of the :data:`LINE_SIZE` deepest outfield rivals at ``t``, goalkeeper
  left out by the proxy of ``visibility.goalkeepers``; the line is chosen at ``t`` and never
  re-ranked.
- ``line_reaction_m``: that line's depth at ``t`` minus its depth at ``t - W``, positive when
  it retreats, the line's reaction to the ball that came in; the window is ``[t - W, t]`` and the
  unit needs the four listed at both ends, in the same period (a break shorter than ``W`` would
  otherwise read the other period's positions with this one's sign). The line follows the ball
  (m10), so its units are also split by the direction of the ball in the same window
  (:func:`reaction_strata`): the direction of the incoming-ball stratum of probe S2, without its
  third and length.
- ``block_width_m`` / ``block_length_m`` / ``block_area_m2``: extent of ``y`` / extent of ``x``
  / their product, over every player of the team out of possession listed at ``t``, goalkeeper
  included, between the extreme players (the definition ``with_gk_extremes_listed`` that probe
  S3 chose); at least :data:`MIN_BLOCK` players. The area is the bounding rectangle, not a hull;
  its players are the four that fix the ends.

These are the definitions of ``defence/`` (``pressure``, ``line``, ``block``) written again here
because the reading of the held-out (``ac2fb heldout read``) may run no code of ``defence/``; the
tests hold each of them equal to the original on synthetic worlds and, in ``realdata``, on the
real matches. One difference: ``defence/`` subtracts the height at ``t - W`` without asking for
the same period at both ends; here the unit has no value if they differ.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from ac2fb.reliability.match import Event, MatchData, locate_rows
from ac2fb.reliability.sensitivity import Metric, Reading, Window, WindowFrames
from ac2fb.reliability.visibility import goalkeepers

__all__ = [
    "BACKWARD_CUT",
    "DIRECTIONS",
    "GOAL_X",
    "INCOMING_WINDOW",
    "LINE_SIZE",
    "METRICS",
    "MIN_BLOCK",
    "NEAR_WEIGHT",
    "RADIUS",
    "TIE",
    "block_extent",
    "incoming_direction",
    "line_height",
    "line_reaction",
    "metric_units",
    "nearest_rival",
    "phases",
    "possessions",
    "pressure_index",
    "reaction_strata",
    "rival_weights",
]

GOAL_X = 52.5  # half of a 105 m pitch: the goal a team attacks is (sign * GOAL_X, 0)
RADIUS = 10.0  # metres; rivals farther from the carrier weigh nothing
NEAR_WEIGHT = 1e-12  # a rival weighs something from here: floating-point noise is below 1e-15
INCOMING_WINDOW = 13  # W, frames: the shortest admissible window of reports/probe_cadence.json
LINE_SIZE = 4  # outfield players in the last line
MIN_BLOCK = 5  # a block with fewer players is not measured
BACKWARD_CUT = 2.0  # metres of ball displacement along the attack that make it not lateral
TIE = 1e-9  # values closer than this are equal: floating-point noise neither grows nor cuts
DIRECTIONS = ("backward", "forward", "lateral", "undefined")  # of the incoming ball

METRICS: tuple[str, ...] = (
    "pressure_index",
    "nearest_rival_m",
    "line_height_m",
    "block_width_m",
    "block_length_m",
    "block_area_m2",
    "line_reaction_m",
)


def possessions(events: Sequence[Event]) -> list[Event]:
    """The ``player_possession`` events with a team and a player; two at one frame are an error."""
    found = [
        e
        for e in events
        if e.family == "player_possession" and e.team is not None and e.player is not None
    ]
    if len({e.frame_start for e in found}) != len(found):
        raise ValueError("two possessions start at the same frame")
    return found


def phases(events: Sequence[Event]) -> list[Event]:
    """The ``phases_of_play`` events with a team; two at one frame are an error."""
    found = [e for e in events if e.family == "phases_of_play" and e.team is not None]
    if len({e.frame_start for e in found}) != len(found):
        raise ValueError("two phases start at the same frame")
    return found


def rival_weights(
    carrier: tuple[float, float], rivals: NDArray[np.float64], sign: int
) -> NDArray[np.float64]:
    """Weight of each rival (rows x, y): ``(1 - d / 10) * (1 + cos theta) / 2`` within 10 m.

    ``theta`` is the angle at the carrier between the rival and the goal it attacks.
    """
    dx, dy = rivals[:, 0] - carrier[0], rivals[:, 1] - carrier[1]
    d = np.hypot(dx, dy)
    gx, gy = sign * GOAL_X - carrier[0], -carrier[1]
    norm = d * np.hypot(gx, gy)
    cos = np.divide(dx * gx + dy * gy, norm, out=np.zeros_like(d), where=norm > 0)
    weight = (1.0 - d / RADIUS) * ((1.0 + cos) / 2.0)
    return np.asarray(np.where(d <= RADIUS, weight, 0.0), dtype=np.float64)


def _carrier_and_rivals(
    window: WindowFrames, e: Event
) -> tuple[tuple[float, float], NDArray[np.int64]] | None:
    """The carrier's position at the last frame and the rows of the rivals listed there."""
    mine = np.flatnonzero(window.player_ids == e.player)
    rivals = np.flatnonzero((window.team_ids != e.team) & window.present[:, -1])
    if len(mine) == 0 or not window.present[mine[0], -1] or len(rivals) == 0:
        return None
    return (float(window.x[mine[0], -1]), float(window.y[mine[0], -1])), rivals


def _by_frame(events: Sequence[Event]) -> dict[int, Event]:
    return {e.frame_start: e for e in events}


def pressure_index(match: MatchData, events: Sequence[Event]) -> Metric:
    """The index at ``t`` of each possession; its players are the rivals within the radius."""
    by_frame = _by_frame(events)

    def metric(window: WindowFrames) -> Reading | None:
        e = by_frame.get(window.window.frame_end)
        if e is None:
            return None
        sign = match.attack_sign.get((e.period, int(e.team or 0)))
        found = _carrier_and_rivals(window, e)
        if sign is None or found is None:
            return None
        carrier, rivals = found
        xy = np.column_stack([window.x[rivals, -1], window.y[rivals, -1]])
        weights = rival_weights(carrier, xy, sign)
        near = weights > NEAR_WEIGHT
        return Reading(float(weights.sum()), tuple(int(p) for p in window.player_ids[rivals][near]))

    return metric


def nearest_rival(events: Sequence[Event]) -> Metric:
    """Distance from the carrier to the nearest rival at ``t``; its player is that rival."""
    by_frame = _by_frame(events)

    def metric(window: WindowFrames) -> Reading | None:
        e = by_frame.get(window.window.frame_end)
        found = None if e is None else _carrier_and_rivals(window, e)
        if found is None:
            return None
        carrier, rivals = found
        d = np.hypot(window.x[rivals, -1] - carrier[0], window.y[rivals, -1] - carrier[1])
        nearest = int(np.argmin(d))
        return Reading(float(d[nearest]), (int(window.player_ids[rivals][nearest]),))

    return metric


def _line(
    window: WindowFrames, e: Event, sign: int, keepers: dict[tuple[int, int], int]
) -> NDArray[np.int64] | None:
    """Rows of the four deepest outfield rivals listed at the last frame, deepest first."""
    rivals = np.flatnonzero((window.team_ids != e.team) & window.present[:, -1])
    if len(rivals) == 0:
        return None
    keeper = keepers.get((e.period, int(window.team_ids[rivals[0]])))
    outfield = rivals[window.player_ids[rivals] != keeper]
    line = outfield[np.argsort(-(window.x[outfield, -1] * sign), kind="stable")[:LINE_SIZE]]
    return line if len(line) == LINE_SIZE else None


def _one_period(match: MatchData, window: WindowFrames, line: NDArray[np.int64]) -> bool:
    """Whether the first player of ``line`` is in the same period at both ends of the window."""
    ends = np.array([window.window.frame_start, window.window.frame_end])
    rows = locate_rows(match, np.full(2, window.player_ids[line[0]], dtype=np.int64), ends)
    return bool((rows >= 0).all() and match.period[rows[0]] == match.period[rows[1]])


def _line_metric(match: MatchData, events: Sequence[Event], back: int) -> Metric:
    by_frame = _by_frame(events)
    keepers = goalkeepers(match)

    def metric(window: WindowFrames) -> Reading | None:
        e = by_frame.get(window.window.frame_end)
        if e is None:
            return None
        sign = match.attack_sign.get((e.period, int(e.team or 0)))
        found = _carrier_and_rivals(window, e)
        if sign is None or found is None:
            return None
        line = _line(window, e, sign, keepers)
        if line is None:
            return None
        height = float(np.mean(window.x[line, -1] * sign))
        if back:
            if not window.present[line, 0].all() or not _one_period(match, window, line):
                return None
            height -= float(np.mean(window.x[line, 0] * sign))
        return Reading(height, tuple(int(p) for p in window.player_ids[line]))

    return metric


def line_height(match: MatchData, events: Sequence[Event]) -> Metric:
    """Mean depth of the last line at ``t`` (window: the frame ``t``)."""
    return _line_metric(match, events, 0)


def line_reaction(match: MatchData, events: Sequence[Event]) -> Metric:
    """Depth at ``t`` minus that at ``t - W`` of the line chosen at ``t`` (window ``[t-W, t]``)."""
    return _line_metric(match, events, INCOMING_WINDOW)


def block_extent(events: Sequence[Event], what: str) -> Metric:
    """``width``, ``length`` or ``area`` of the team out of possession at the start of a phase."""
    if what not in ("width", "length", "area"):
        raise ValueError(f"unknown block measure {what!r}")
    by_frame = _by_frame(events)

    def metric(window: WindowFrames) -> Reading | None:
        e = by_frame.get(window.window.frame_end)
        if e is None:
            return None
        out = np.flatnonzero((window.team_ids != e.team) & window.present[:, 0])
        xs, ys = window.x[out, 0], window.y[out, 0]
        if len(out) < MIN_BLOCK or not (np.isfinite(xs).all() and np.isfinite(ys).all()):
            return None
        ids = window.player_ids[out]
        extents: dict[str, tuple[float, list[int]]] = {}
        for name, values in (("length", xs), ("width", ys)):
            order = np.argsort(values, kind="stable")
            extents[name] = (
                float(values[order[-1]] - values[order[0]]),
                [int(ids[order[0]]), int(ids[order[-1]])],
            )
        width, length = extents["width"], extents["length"]
        if what == "area":
            return Reading(width[0] * length[0], tuple(sorted({*width[1], *length[1]})))
        value, fixers = extents[what]
        return Reading(value, tuple(sorted(set(fixers))))

    return metric


def incoming_direction(match: MatchData, frame: int, sign: int) -> str:
    """Direction along the attack of the ball in ``[frame - W, frame]``, or ``undefined``.

    ``undefined`` without a ball row at either end or with the two rows in different periods.
    """
    rows = np.searchsorted(match.ball_frame, [frame - INCOMING_WINDOW, frame])
    if (
        rows.max() >= len(match.ball_frame)
        or not np.array_equal(match.ball_frame[rows], [frame - INCOMING_WINDOW, frame])
        or match.ball_period[rows[0]] != match.ball_period[rows[1]]
    ):
        return "undefined"
    dx = sign * float(match.ball_x[rows[1]] - match.ball_x[rows[0]])
    cut = BACKWARD_CUT + TIE
    return "backward" if dx < -cut else "forward" if dx > cut else "lateral"


def reaction_strata(match: MatchData) -> dict[str, list[Window]]:
    """The windows of ``line_reaction_m`` by the direction of the incoming ball.

    Keys in :data:`DIRECTIONS` order; a possession whose team has no attack direction in its
    period is ``undefined``.
    """
    strata: dict[str, list[Window]] = {d: [] for d in DIRECTIONS}
    for e in possessions(match.events):
        sign = match.attack_sign.get((e.period, int(e.team or 0)))
        direction = "undefined" if sign is None else incoming_direction(match, e.frame_start, sign)
        strata[direction].append(
            Window(match.match_id, e.frame_start - INCOMING_WINDOW, e.frame_start)
        )
    return strata


def metric_units(match: MatchData) -> dict[str, tuple[Metric, list[Window]]]:
    """Each metric of :data:`METRICS` with the windows of its units, for one match."""
    held = possessions(match.events)
    blocks = phases(match.events)
    at = [Window(match.match_id, e.frame_start, e.frame_start) for e in held]
    before = [Window(match.match_id, e.frame_start - INCOMING_WINDOW, e.frame_start) for e in held]
    start = [Window(match.match_id, e.frame_start, e.frame_start) for e in blocks]
    return {
        "pressure_index": (pressure_index(match, held), at),
        "nearest_rival_m": (nearest_rival(held), at),
        "line_height_m": (line_height(match, held), at),
        "block_width_m": (block_extent(blocks, "width"), start),
        "block_length_m": (block_extent(blocks, "length"), start),
        "block_area_m2": (block_extent(blocks, "area"), start),
        "line_reaction_m": (line_reaction(match, held), before),
    }
