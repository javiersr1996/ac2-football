"""How much of what a metric reads the camera saw: detection by match, distance, line and block.

Every function takes one :class:`~ac2fb.reliability.match.MatchData` and returns plain numbers
(shares in 0..1, counts, metres). All of it describes visibility at instants given by the
provider's events (the frame where an engagement, a possession or a phase starts); none of it
looks at what happens after those instants.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ac2fb.reliability.match import MatchData, locate_rows, players_at

__all__ = [
    "BALL_DISTANCE_EDGES",
    "block_detection",
    "defensive_line_detection",
    "detection_by_ball_distance",
    "detection_shares",
    "engager_detection",
    "goalkeepers",
    "reception_detection",
]

BALL_DISTANCE_EDGES = (5.0, 10.0, 20.0, 30.0, 40.0)  # metres; bins: <5, <10, <20, <30, <40, 40+
_BALL_BINS = ("00_05", "05_10", "10_20", "20_30", "30_40", "40_plus")
RADII = (2.0, 5.0, 10.0, 20.0)
_SPAN = 1 << 32  # the key of MatchData is player * 2**32 + frame


def _share(hits: int | np.integer, total: int | np.integer) -> float | None:
    return float(hits) / float(total) if total else None


def detection_shares(match: MatchData) -> dict[str, object]:
    """Share of player rows and of ball rows with ``is_detected`` true."""
    return {
        "player_rows": int(len(match.frame)),
        "player_detected": _share(match.detected.sum(), len(match.frame)),
        "ball_rows": int(len(match.ball_frame)),
        "ball_detected": _share(match.ball_detected.sum(), len(match.ball_frame)),
    }


def detection_by_ball_distance(match: MatchData, every: int = 10) -> dict[str, object]:
    """Share of players detected by distance to the ball, in one frame of every ``every``.

    Only frames where the ball has a row count (detected or not).
    """
    pick = np.flatnonzero(match.frame % every == 0)
    pos = np.searchsorted(match.ball_frame, match.frame[pick])
    safe = np.minimum(pos, max(len(match.ball_frame) - 1, 0))
    has = (pos < len(match.ball_frame)) & (match.ball_frame[safe] == match.frame[pick])
    rows, ball = pick[has], safe[has]
    dist = np.hypot(match.x[rows] - match.ball_x[ball], match.y[rows] - match.ball_y[ball])
    which = np.searchsorted(np.array(BALL_DISTANCE_EDGES), dist, side="right")
    out: dict[str, object] = {}
    for i, name in enumerate(_BALL_BINS):
        mask = which == i
        hits = match.detected[rows][mask].sum()
        out[name] = {"n": int(mask.sum()), "detected": _share(hits, mask.sum())}
    return out


def engager_detection(match: MatchData, margin: int = 10) -> dict[str, object]:
    """Detection of the player who engages the ball carrier (``on_ball_engagement`` events).

    ``at_start``: detected at ``frame_start``. Window: the frames of the engager in
    ``[frame_start - margin, frame_end + margin]``; ``window_mean`` is the mean share of them
    detected over events, ``window_whole`` the share of events with all of them detected.
    """
    events = [e for e in match.events if e.family == "on_ball_engagement" and e.player is not None]
    players = np.array([e.player for e in events], dtype=np.int64)
    start = np.array([e.frame_start for e in events], dtype=np.int64)
    end = np.array([e.frame_end for e in events], dtype=np.int64)
    rows = locate_rows(match, players, start)
    at_start = match.detected[rows[rows >= 0]]
    lo = np.searchsorted(match.key, players * _SPAN + start - margin, side="left")
    hi = np.searchsorted(match.key, players * _SPAN + end + margin, side="right")
    cum = np.r_[0, np.cumsum(match.detected)]
    count, seen = hi - lo, cum[hi] - cum[lo]
    ok = count > 0
    frac = seen[ok] / count[ok]
    return {
        "events": len(events),
        "at_start_n": int(len(at_start)),
        "at_start": _share(at_start.sum(), len(at_start)),
        "window_n": int(ok.sum()),
        "window_mean": float(frac.mean()) if len(frac) else None,
        "window_whole": _share((frac == 1).sum(), len(frac)),
    }


def reception_detection(match: MatchData) -> dict[str, object]:
    """Detection around the carrier at the start of each ``player_possession`` event.

    Counts the events whose carrier has a row at ``frame_start`` and who have at least one
    rival row there. ``rivals_within``: rivals (players of the other team, goalkeeper
    included) within each radius of the carrier. ``rivals_beyond_20``: the rest.
    """
    carrier_det: list[bool] = []
    dist_all: list[NDArray[np.float64]] = []
    det_all: list[NDArray[np.bool_]] = []
    ev_of: list[NDArray[np.int64]] = []
    for e in (e for e in match.events if e.family == "player_possession"):
        if e.player is None or e.team is None:
            continue
        car = locate_rows(match, np.array([e.player]), np.array([e.frame_start]))[0]
        rows = players_at(match, e.frame_start)
        riv = rows[match.team[rows] != e.team]
        if car < 0 or len(riv) == 0:
            continue
        carrier_det.append(bool(match.detected[car]))
        dist_all.append(np.hypot(match.x[riv] - match.x[car], match.y[riv] - match.y[car]))
        det_all.append(match.detected[riv])
        ev_of.append(np.full(len(riv), len(carrier_det) - 1, dtype=np.int64))
    n = len(carrier_det)
    if n == 0:
        return {"events": 0}
    dist, det, ev = np.concatenate(dist_all), np.concatenate(det_all), np.concatenate(ev_of)
    out: dict[str, object] = {"events": n, "carrier_detected": _share(sum(carrier_det), n)}
    within: dict[str, object] = {}
    for r in RADII:
        pick = dist <= r
        within[f"{r:g}"] = {"n": int(pick.sum()), "detected": _share(det[pick].sum(), pick.sum())}
    out["rivals_within"] = within
    far = dist > 20
    out["rivals_beyond_20"] = {"n": int(far.sum()), "detected": _share(det[far].sum(), far.sum())}
    for r in (5.0, 10.0):
        near = dist <= r
        has = np.bincount(ev[near], minlength=n) > 0
        extrapolated = np.bincount(ev[near & ~det], minlength=n) > 0
        out[f"no_rival_within_{r:g}"] = _share((~has).sum(), n)
        out[f"events_with_rival_within_{r:g}"] = int(has.sum())
        out[f"with_extrapolated_rival_within_{r:g}"] = _share(extrapolated[has].sum(), has.sum())
    return out


def goalkeepers(match: MatchData) -> dict[tuple[int, int], int]:
    """The goalkeeper of each ``(period, team)``: the player whose mean position is deepest in
    their own half. The base's silver carries no player roles, so this is a proxy."""
    found: dict[tuple[int, int], int] = {}
    for (period, team), sign in match.attack_sign.items():
        rows = np.flatnonzero((match.period == period) & (match.team == team))
        if len(rows) == 0:
            continue
        who, inverse = np.unique(match.player[rows], return_inverse=True)
        mean = np.bincount(inverse, weights=match.x[rows] * sign) / np.bincount(inverse)
        found[(period, team)] = int(who[np.argmin(mean)])
    return found


def defensive_line_detection(match: MatchData, size: int = 4) -> dict[str, object]:
    """Detection of the ``size`` deepest outfield defenders when a ``player_possession`` starts.

    Depth is ``x`` times the attacking team's sign; the goalkeeper is left out (see
    :func:`goalkeepers`). ``detected_count`` is how many of them are detected, 0 to ``size``:
    the strata of variant V2.
    """
    keepers = goalkeepers(match)
    shares: list[float] = []
    deepest: list[bool] = []
    counts = np.zeros(size + 1, dtype=np.int64)
    for e in (e for e in match.events if e.family == "player_possession"):
        if e.team is None:
            continue
        sign = match.attack_sign.get((e.period, e.team))
        rows = players_at(match, e.frame_start)
        riv = rows[match.team[rows] != e.team]
        if sign is None or len(riv) == 0:
            continue
        keeper = keepers.get((e.period, int(match.team[riv[0]])))
        riv = riv[match.player[riv] != keeper]
        if len(riv) < size:
            continue
        top = riv[np.argsort(-(match.x[riv] * sign), kind="stable")[:size]]
        seen = int(match.detected[top].sum())
        counts[seen] += 1
        shares.append(seen / size)
        deepest.append(bool(match.detected[top[0]]))
    n = len(shares)
    return {
        "events": n,
        "detected": float(np.mean(shares)) if n else None,
        "all_detected": _share(counts[size], n),
        "deepest_detected": _share(sum(deepest), n),
        "detected_count": {str(k): int(counts[k]) for k in range(size + 1)},
    }


def block_detection(match: MatchData) -> dict[str, object]:
    """Detection of the team out of possession at the start of each ``phases_of_play`` phase."""
    shares: list[float] = []
    for e in (e for e in match.events if e.family == "phases_of_play"):
        if e.team is None:
            continue
        rows = players_at(match, e.frame_start)
        out = rows[match.team[rows] != e.team]
        if len(out):
            shares.append(float(match.detected[out].mean()))
    n = len(shares)
    return {
        "phases": n,
        "detected": float(np.mean(shares)) if n else None,
        "all_detected": _share(sum(s == 1.0 for s in shares), n),
    }
