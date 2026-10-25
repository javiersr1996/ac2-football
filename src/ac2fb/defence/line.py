"""The defending team's last line at a reception, followed in time, and the units of probe S2.

A *reception* is the ``frame_start`` ``t`` of a provider ``player_possession`` event, as in
:mod:`ac2fb.defence.pressure`. Everything here is written before the data was read.

**The line.** For a carrier whose team attacks along ``s`` (+1 or -1: the direction of x it
attacks in that period), the *depth* of a point is ``x * s``: larger is nearer the goal the
other team defends. At ``t`` the line is the :data:`LINE_SIZE` deepest outfield players of the
other team listed at ``t`` (its goalkeeper left out, by the proxy of
:func:`ac2fb.reliability.visibility.goalkeepers`). Its height ``L(t')`` at a frame ``t'`` is the
mean depth of those same players at ``t'``, defined only when all of them are listed there
(detected or not): they are chosen once, at ``t``, and never re-ranked. A displacement
``L(b) - L(a)`` is positive when the line retreats towards its own goal and negative when it
steps up. The provider's event coordinates are attack-normalised (the team in possession
attacks +x), so ``L(t)`` and ``last_defensive_line_x_start`` lie on one axis.

**Pressure at t.** A reception is *pressed* when at least one rival listed at ``t`` (goalkeeper
included) is within :data:`PRESSED_RADIUS` metres of the carrier: the proxy of the plan's probe
m10.

**What is read.** Positions at ``t`` and before it, through the ``lags`` asked for. Two things
look past ``t``: :func:`seen_through`, which reads whether a player is listed and detected,
never where; and the goalkeeper proxy, a role taken from each player's mean position over the
whole period, which says who is left out of the line and measures no movement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ac2fb.defence import pressure
from ac2fb.reliability.match import MatchData, locate_rows, players_at
from ac2fb.reliability.visibility import goalkeepers

__all__ = [
    "LINE_SIZE",
    "PRESSED_RADIUS",
    "LineReception",
    "Unit",
    "ball_extrapolated",
    "build_units",
    "concordance",
    "seen_through",
    "within_strata",
]

LINE_SIZE = 4  # outfield players in the last line
PRESSED_RADIUS = 5.0  # metres: a rival this close to the carrier at t makes the reception pressed


@dataclass(frozen=True)
class LineReception:
    """A ``player_possession`` start with the provider's line and pressure label (may be null)."""

    event_id: str
    period: int
    frame: int
    team: int
    player: int
    provider_line: float | None  # last_defensive_line_x_start
    label: str | None  # overall_pressure_start; only the m10 re-derivation reads it


@dataclass(frozen=True)
class Unit:
    """A reception with its line and what came before it.

    ``depth`` maps a lag in frames (0 is ``t``) to ``L(t - lag)``, NaN where not all the line
    is listed. ``ball_along`` maps a lag to the ball's displacement along the attack over
    ``[t - lag, t]`` (NaN without a ball row at both ends). ``ball_to_line`` is the mean
    distance of the line's players to the ball at ``t`` (NaN without a ball row at ``t``).
    """

    reception: LineReception
    sign: int
    line: tuple[int, ...]  # the line's player ids, deepest first
    depth: dict[int, float]
    deepest: float  # depth of the deepest of them at t
    detected_at_t: int  # how many of them are detected at t
    near: int  # rivals within PRESSED_RADIUS of the carrier at t
    nearest: float  # distance to the nearest rival at t
    pressed: bool
    ball_along: dict[int, float]
    ball_to_line: float
    stratum: str  # pressure.incoming_ball: direction/third/length, or "undefined"


def _ball_row(match: MatchData, frame: int) -> int:
    pos = int(np.searchsorted(match.ball_frame, frame))
    return pos if pos < len(match.ball_frame) and match.ball_frame[pos] == frame else -1


def build_units(
    match: MatchData, receptions: Sequence[LineReception], lags: Sequence[int]
) -> tuple[list[Unit], dict[str, int]]:
    """The unit of each reception with a line at ``t``, and why the others were left out.

    A reception is left out when the attack direction of its team in that period is unknown
    (``no_side``), its carrier has no row at ``t`` (``no_carrier``), no rival is listed at ``t``
    (``no_rival``) or fewer than :data:`LINE_SIZE` outfield rivals are (``no_line``). The line
    height and the ball are read at ``t`` and at ``t - lag`` for each lag; nothing after ``t``.
    """
    keepers = goalkeepers(match)
    units: list[Unit] = []
    dropped = {"no_side": 0, "no_carrier": 0, "no_rival": 0, "no_line": 0}
    all_lags = sorted({0, *lags})
    ball_now = {r.frame: _ball_row(match, r.frame) for r in receptions}
    for r in receptions:
        sign = match.attack_sign.get((r.period, r.team))
        if sign is None:
            dropped["no_side"] += 1
            continue
        carrier = int(locate_rows(match, np.array([r.player]), np.array([r.frame]))[0])
        if carrier < 0:
            dropped["no_carrier"] += 1
            continue
        rows = players_at(match, r.frame)
        rivals = rows[match.team[rows] != r.team]
        if len(rivals) == 0:
            dropped["no_rival"] += 1
            continue
        keeper = keepers.get((r.period, int(match.team[rivals[0]])))
        outfield = rivals[match.player[rivals] != keeper]
        line = outfield[np.argsort(-(match.x[outfield] * sign), kind="stable")[:LINE_SIZE]]
        if len(line) < LINE_SIZE:
            dropped["no_line"] += 1
            continue
        ids = match.player[line]
        depth: dict[int, float] = {}
        for lag in all_lags:
            found = locate_rows(match, ids, np.full(len(ids), r.frame - lag, dtype=np.int64))
            depth[lag] = (
                float(np.mean(match.x[found] * sign)) if (found >= 0).all() else float("nan")
            )
        cx, cy = float(match.x[carrier]), float(match.y[carrier])
        dist = np.hypot(match.x[rivals] - cx, match.y[rivals] - cy)
        near = int((dist <= PRESSED_RADIUS).sum())
        now = ball_now[r.frame]
        along: dict[int, float] = {}
        for lag in all_lags:
            then = _ball_row(match, r.frame - lag)
            along[lag] = (
                sign * float(match.ball_x[now] - match.ball_x[then])
                if now >= 0 and then >= 0
                else float("nan")
            )
        to_line = (
            float(
                np.mean(
                    np.hypot(match.x[line] - match.ball_x[now], match.y[line] - match.ball_y[now])
                )
            )
            if now >= 0
            else float("nan")
        )
        units.append(
            Unit(
                reception=r,
                sign=sign,
                line=tuple(int(p) for p in ids),
                depth=depth,
                deepest=float(match.x[line[0]] * sign),
                detected_at_t=int(match.detected[line].sum()),
                near=near,
                nearest=float(dist.min()),
                pressed=near >= 1,
                ball_along=along,
                ball_to_line=to_line,
                stratum=pressure.incoming_ball(match, r.frame, sign, cx),
            )
        )
    return units, dropped


def seen_through(match: MatchData, players: Sequence[int], first: int, last: int) -> int:
    """How many of ``players`` are listed and detected in every frame ``first`` to ``last``.

    Reads the detection flags only (``match.key`` and ``match.detected``), never a position, so
    it may look past the reception: it counts visibility, not what the players did.
    """
    frames = np.arange(first, last + 1, dtype=np.int64)
    seen = 0
    for p in players:
        rows = locate_rows(match, np.full(len(frames), p, dtype=np.int64), frames)
        seen += int((rows >= 0).all() and match.detected[rows].all())
    return seen


def ball_extrapolated(match: MatchData, first: int, last: int) -> bool:
    """Whether the ball is unlisted or not detected in some frame ``first`` to ``last``."""
    lo = int(np.searchsorted(match.ball_frame, first, side="left"))
    hi = int(np.searchsorted(match.ball_frame, last, side="right"))
    return hi - lo < last - first + 1 or not bool(match.ball_detected[lo:hi].all())


def concordance(ours: Sequence[float], theirs: Sequence[float]) -> dict[str, object]:
    """How two measures of the same line agree: Pearson r, Lin's CCC and the differences.

    ``ccc`` is ``2 cov / (var_a + var_b + (mean_a - mean_b)^2)`` with population moments, so
    an offset or a different scale lowers it where ``r`` stays. ``n`` pairs; r and ccc are
    ``None`` below three pairs or with a constant series.
    """
    a, b = np.asarray(ours, dtype=np.float64), np.asarray(theirs, dtype=np.float64)
    n = len(a)
    diff = a - b
    out: dict[str, object] = {
        "n": n,
        "median_diff": float(np.median(diff)) if n else None,
        "median_abs_diff": float(np.median(np.abs(diff))) if n else None,
        "pearson_r": None,
        "ccc": None,
    }
    if n >= 3 and a.std() > 0 and b.std() > 0:
        cov = float(np.mean((a - a.mean()) * (b - b.mean())))
        out["pearson_r"] = cov / float(a.std() * b.std())
        out["ccc"] = 2 * cov / float(a.var() + b.var() + (a.mean() - b.mean()) ** 2)
    return out


def within_strata(
    values: Sequence[float], pressed: Sequence[bool], strata: Sequence[str], min_cell: int
) -> dict[str, object]:
    """Pressed minus free inside each stratum, in metres and in sd of the stratum, pooled.

    In each stratum with at least ``min_cell`` pressed and ``min_cell`` free units: the
    difference of the means ``d``, the sample sd ``s`` of all its units and ``z = d / s``.
    Pooled over those strata with weights ``n_p * n_f / (n_p + n_f)``: ``sd`` is the weighted
    mean of ``z``, ``m`` of ``d``. A stratum below the minimum, or with ``s`` zero, is left out
    and its units counted in ``units_left_out``.
    """
    v = np.asarray(values, dtype=np.float64)
    p = np.asarray(pressed, dtype=np.bool_)
    s = np.asarray(strata, dtype=object)
    cells: dict[str, object] = {}
    num_z = num_d = weight = 0.0
    used = left = 0
    for cell in sorted(set(strata)):
        mask = s == cell
        a, b = v[mask & p], v[mask & ~p]
        sd = float(np.std(v[mask], ddof=1)) if mask.sum() > 1 else 0.0
        ok = len(a) >= min_cell and len(b) >= min_cell and sd > 0
        d = float(a.mean() - b.mean()) if len(a) and len(b) else None
        cells[cell] = {"n_pressed": len(a), "n_free": len(b), "diff": d, "sd": sd, "used": ok}
        if not ok or d is None:
            left += int(mask.sum())
            continue
        w = len(a) * len(b) / (len(a) + len(b))
        num_z += w * d / sd
        num_d += w * d
        weight += w
        used += int(mask.sum())
    return {
        "sd": num_z / weight if weight else None,
        "m": num_d / weight if weight else None,
        "strata_used": sum(bool(c["used"]) for c in cells.values()),  # type: ignore[index]
        "units_used": used,
        "units_left_out": left,
        "by_stratum": cells,
    }
