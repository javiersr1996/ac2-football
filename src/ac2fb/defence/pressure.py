"""The geometric pressure index at a reception, and the incoming-ball strata.

A *reception* is the ``frame_start`` of a provider ``player_possession`` event (the carrier
touches the ball; the cut at that instant is the one the plan's inventory confirmed). Everything
here is read at frame ``t`` or before it: the index uses the positions at ``t`` and the strata
the ball in ``[t - W, t]``. Nothing looks at a frame after ``t``.

**The index** (written before the data was read). For a carrier of a team that attacks in
direction ``sign`` of x, the goal it attacks is the point ``(sign * 52.5, 0)``. Each rival
listed at ``t`` (every player of the other team, goalkeeper included) at distance ``d`` metres
from the carrier adds

    weight = (1 - d / 10) * (1 + cos(theta)) / 2        for d <= 10, else 0,

where ``theta`` is the angle at the carrier between the rival and the goal: a rival straight
between carrier and goal weighs its distance weight in full, one level with the carrier half of
it, one behind none. The index is the sum over rivals, in "rival equivalents" (0 with nobody
within 10 m; a rival touching the carrier in front is 1). The goalkeeper is not left out, as
in the inventory's counts of rivals near the carrier. The extrapolated share of an index is the
part of that sum that comes from rivals with ``is_detected`` false at ``t``.

**The cause** (task 19, ``protocol/protocol.json`` ``cause.treatment``, written before any
outcome). A reception is *pressed* when its index is at least :data:`PRESSED_INDEX`: the index
of one rival at half the radius straight between the carrier and the goal, which is the 5 m
proxy of m10 on the goal side. The cut is not moved after the data is read.

**Incoming ball strata.** With ``W`` = :data:`INCOMING_WINDOW` frames (the shortest admissible
window of ``reports/probe_cadence.json``), the ball displacement from ``t - W`` to ``t`` is
split by direction of attack (backward under -2 m, forward over +2 m, else lateral), by third
of the pitch of the carrier at ``t`` (the 35 m in the middle, the others own and final) and by
length (the straight distance under 10 m: short; else long). A reception whose ball has no row
at ``t - W`` or ``t``, or has the two in different periods, is ``undefined``. These are counts
of what came before the reception.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ac2fb.reliability.match import MatchData, locate_rows, players_at
from ac2fb.reliability.sensitivity import Metric, Reading, WindowFrames

__all__ = [
    "BACKWARD_CUT",
    "GOAL_X",
    "INCOMING_WINDOW",
    "LEVELS",
    "LONG_BALL",
    "NEAR_WEIGHT",
    "PRESSED_INDEX",
    "RADIUS",
    "THIRD_CUT",
    "TIE",
    "Reception",
    "Scored",
    "distance_weight",
    "extrapolated_share",
    "goal_side_weight",
    "incoming_ball",
    "level_contrast",
    "make_metric",
    "rival_weights",
    "score_receptions",
    "stratum_counts",
]

GOAL_X = 52.5  # half of a 105 m pitch: the goal the carrier attacks is (sign * GOAL_X, 0)
RADIUS = 10.0  # metres; rivals farther from the carrier weigh nothing
PRESSED_INDEX = 0.5  # rival equivalents; the protocol's cause: pressed at or above it (task 19)
INCOMING_WINDOW = 13  # frames; decision.w_min_frames of reports/probe_cadence.json
BACKWARD_CUT = 2.0  # metres of ball displacement along the attack that make it not lateral
THIRD_CUT = 17.5  # metres from the centre line: the middle third is 35 m of 105
LONG_BALL = 10.0  # metres of straight displacement from which the incoming ball is long
NEAR_WEIGHT = 1e-12  # a rival is near from this weight: float noise is below 1e-15, data above 1e-9
TIE = 1e-9  # values closer than this are equal: floating-point noise neither grows nor cuts
LEVELS: dict[int, str] = {
    1: "no_pressure",
    2: "low_pressure",
    3: "medium_pressure",
    4: "high_pressure",
    5: "very_high_pressure",
}  # the provider's overall_pressure_start, in order of its overall_pressure_start_id


@dataclass(frozen=True)
class Reception:
    """A ``player_possession`` start with the provider's pressure level (1 to 5)."""

    event_id: str
    period: int
    frame: int
    team: int
    player: int
    level: int


@dataclass(frozen=True)
class Scored:
    """A reception with its index, the rivals within the radius and its incoming-ball stratum.

    ``near_*`` list the rivals with weight above :data:`NEAR_WEIGHT` at ``t`` (ids, weights,
    ``is_detected``).
    """

    reception: Reception
    index: float
    near_players: tuple[int, ...]
    near_weights: tuple[float, ...]
    near_detected: tuple[bool, ...]
    carrier_detected: bool
    stratum: str


def distance_weight(d: NDArray[np.float64]) -> NDArray[np.float64]:
    """Weight of a rival at distance ``d`` metres, for ``d <= RADIUS``: 1 at contact, 0 at 10 m."""
    return np.asarray(1.0 - d / RADIUS, dtype=np.float64)


def goal_side_weight(cos_theta: NDArray[np.float64]) -> NDArray[np.float64]:
    """1 for a rival straight towards the goal, 0.5 level with the carrier, 0 straight behind."""
    return np.asarray((1.0 + cos_theta) / 2.0, dtype=np.float64)


def rival_weights(
    carrier: tuple[float, float], rivals: NDArray[np.float64], sign: int
) -> NDArray[np.float64]:
    """The weight of each rival (rows of ``rivals``: x, y) for a carrier attacking along sign."""
    dx, dy = rivals[:, 0] - carrier[0], rivals[:, 1] - carrier[1]
    d = np.hypot(dx, dy)
    gx, gy = sign * GOAL_X - carrier[0], -carrier[1]
    norm = d * np.hypot(gx, gy)
    cos = np.divide(dx * gx + dy * gy, norm, out=np.zeros_like(d), where=norm > 0)
    inside = d <= RADIUS
    return np.where(inside, distance_weight(d) * goal_side_weight(cos), 0.0)


def incoming_ball(match: MatchData, frame: int, sign: int, carrier_x: float) -> str:
    """``direction/third/length`` of the ball in ``[frame - W, frame]``, or ``undefined``.

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
    straight = float(
        np.hypot(
            match.ball_x[rows[1]] - match.ball_x[rows[0]],
            match.ball_y[rows[1]] - match.ball_y[rows[0]],
        )
    )
    cut = BACKWARD_CUT + TIE
    direction = "backward" if dx < -cut else "forward" if dx > cut else "lateral"
    depth = sign * carrier_x  # a listed x times 1 or -1: exact, so no tolerance at its cut
    third = "own" if depth < -THIRD_CUT else "final" if depth > THIRD_CUT else "middle"
    return f"{direction}/{third}/{'long' if straight >= LONG_BALL - TIE else 'short'}"


def score_receptions(match: MatchData, receptions: Sequence[Reception]) -> list[Scored]:
    """Index and stratum of each reception whose carrier and a rival are listed at ``t``.

    A reception is left out when its carrier has no row at ``t``, the attack direction of its
    team in that period is unknown, or no rival is listed at ``t``.
    """
    scored: list[Scored] = []
    for r in receptions:
        sign = match.attack_sign.get((r.period, r.team))
        carrier = locate_rows(match, np.array([r.player]), np.array([r.frame]))[0]
        rows = players_at(match, r.frame)
        rivals = rows[match.team[rows] != r.team]
        if sign is None or carrier < 0 or len(rivals) == 0:
            continue
        xy = np.column_stack([match.x[rivals], match.y[rivals]])
        weights = rival_weights((float(match.x[carrier]), float(match.y[carrier])), xy, sign)
        near = weights > NEAR_WEIGHT
        scored.append(
            Scored(
                reception=r,
                index=float(weights.sum()),
                near_players=tuple(int(p) for p in match.player[rivals][near]),
                near_weights=tuple(float(w) for w in weights[near]),
                near_detected=tuple(bool(d) for d in match.detected[rivals][near]),
                carrier_detected=bool(match.detected[carrier]),
                stratum=incoming_ball(match, r.frame, sign, float(match.x[carrier])),
            )
        )
    return scored


def make_metric(match: MatchData, receptions: Sequence[Reception]) -> Metric:
    """The index as a layer 2 metric of one-frame windows (see ``reliability.sensitivity``).

    The players behind a unit are the rivals within the radius, so V1 keeps the receptions
    whose near rivals are all detected and V2 splits them by how many are.
    """
    by_frame = {r.frame: r for r in receptions}

    def metric(window: WindowFrames) -> Reading | None:
        r = by_frame.get(window.window.frame_start)
        if r is None:
            return None
        mine = np.flatnonzero(window.player_ids == r.player)
        sign = match.attack_sign.get((r.period, r.team))
        rivals = np.flatnonzero((window.team_ids != r.team) & window.present[:, 0])
        if sign is None or len(mine) == 0 or not window.present[mine[0], 0] or len(rivals) == 0:
            return None
        carrier = (float(window.x[mine[0], 0]), float(window.y[mine[0], 0]))
        xy = np.column_stack([window.x[rivals, 0], window.y[rivals, 0]])
        weights = rival_weights(carrier, xy, sign)
        near = weights > NEAR_WEIGHT
        return Reading(float(weights.sum()), tuple(int(p) for p in window.player_ids[rivals][near]))

    return metric


def level_contrast(scored: Sequence[Scored], min_per_level: int) -> dict[str, object]:
    """Median index by pressure level, and whether it grows strictly over the five levels.

    Strictly means each median exceeds the one before by more than :data:`TIE`.

    ``evaluable`` needs ``min_per_level`` receptions in every level; without it the match
    cannot show an increase and ``increasing`` is false.
    """
    n: dict[str, int] = {}
    medians: dict[str, float | None] = {}
    for level, name in LEVELS.items():
        values = [s.index for s in scored if s.reception.level == level]
        n[name] = len(values)
        medians[name] = float(np.median(values)) if values else None
    ordered = [medians[name] for name in LEVELS.values()]
    evaluable = all(count >= min_per_level for count in n.values())
    increasing = evaluable and all(
        a is not None and b is not None and b - a > TIE
        for a, b in zip(ordered[:-1], ordered[1:], strict=True)
    )
    return {"evaluable": evaluable, "increasing": increasing, "median": medians, "n": n}


def extrapolated_share(scored: Sequence[Scored]) -> dict[str, object]:
    """The part of the summed index that rivals with ``is_detected`` false at ``t`` carry.

    Overall and by level; ``receptions_with_any`` is the share of receptions with an index
    above zero in which at least one near rival is extrapolated.
    """

    def share(items: Sequence[Scored]) -> float | None:
        total = sum(sum(s.near_weights) for s in items)
        gone = sum(
            w
            for s in items
            for w, seen in zip(s.near_weights, s.near_detected, strict=True)
            if not seen
        )
        return gone / total if total else None

    live = [s for s in scored if s.near_weights]
    return {
        "overall": share(scored),
        "by_level": {
            name: share([s for s in scored if s.reception.level == k]) for k, name in LEVELS.items()
        },
        "receptions_with_any": (
            sum(not all(s.near_detected) for s in live) / len(live) if live else None
        ),
        "receptions_with_near_rival": len(live),
    }


def stratum_counts(scored: Sequence[Scored]) -> dict[str, object]:
    """Receptions per incoming-ball stratum, and within each stratum per pressure level."""
    cells: dict[str, dict[str, int]] = {}
    for s in (s for s in scored if s.stratum != "undefined"):
        row = cells.setdefault(s.stratum, {name: 0 for name in LEVELS.values()})
        row[LEVELS[s.reception.level]] += 1
    return {
        "undefined": sum(s.stratum == "undefined" for s in scored),
        "strata": {k: {"n": sum(v.values()), "by_level": v} for k, v in sorted(cells.items())},
    }
