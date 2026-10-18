"""Extrapolated runs: their length, the jump when the detection comes back, the second difference.

A run is a maximal stretch of consecutive frames of one player with the same ``is_detected``.
A frame the provider does not list ends a run. Gap bands (frames at 10 Hz): up to 1 s, up to
5 s, up to 20 s, longer. Steps are metres between consecutive frames (0.1 s).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ac2fb.reliability.match import MatchData

__all__ = [
    "BANDS",
    "Runs",
    "acceleration_summary",
    "band_of",
    "extrapolated_runs",
    "linear_rounding_floor",
    "run_summary",
    "second_differences",
    "step_summary",
    "unlisted_stretches",
]

BANDS: tuple[tuple[str, int], ...] = (
    ("le_1s", 10),
    ("1_5s", 50),
    ("5_20s", 200),
    ("gt_20s", 1 << 40),
)


@dataclass(frozen=True)
class Runs:
    """All runs of a match, in player and frame order.

    ``jump`` is the step from the run's last frame to the next frame when that next frame
    is the very next frame number, of the same player and detected (else NaN); ``mean_step``
    is the mean step into the frames of the run (NaN when none has a previous consecutive
    frame); ``left_closed`` says the run starts on the frame after a frame of the other kind.
    A run with ``left_closed`` and a ``jump`` is a closed gap: detected on both sides.
    """

    player: NDArray[np.int64]
    detected: NDArray[np.bool_]
    start_frame: NDArray[np.int64]
    length: NDArray[np.int64]
    left_closed: NDArray[np.bool_]
    jump: NDArray[np.float64]
    mean_step: NDArray[np.float64]


def band_of(length: NDArray[np.int64]) -> NDArray[np.int64]:
    """Index into :data:`BANDS` of each run length (frames)."""
    cuts = np.array([cut for _, cut in BANDS[:-1]])
    return np.searchsorted(cuts, length, side="left")


def _steps(match: MatchData) -> tuple[NDArray[np.bool_], NDArray[np.float64]]:
    """``consecutive[i]``: row i directly follows row i-1 of the same player; and its step."""
    consecutive = np.zeros(len(match.frame), dtype=np.bool_)
    consecutive[1:] = (match.player[1:] == match.player[:-1]) & (
        match.frame[1:] == match.frame[:-1] + 1
    )
    step = np.full(len(match.frame), np.nan)
    step[1:] = np.hypot(np.diff(match.x), np.diff(match.y))
    return consecutive, np.where(consecutive, step, np.nan)


def extrapolated_runs(match: MatchData, *, bridge_holes: bool = False) -> Runs:
    """Every run of a match, detected and extrapolated, with the jump after it.

    By default a run is a stretch of consecutive frame numbers, so a stretch of frames the
    provider does not list for the player ends it. With ``bridge_holes`` the definition is
    the one of the plan's probes (m6 and m11): only rows that follow a listed frame count,
    and a run ends only where ``is_detected`` changes, so two stretches with unlisted frames
    between them are one run; a run that mixes both kinds takes the kind of its last row. It
    exists to reproduce those figures.
    """
    consecutive, step = _steps(match)
    use = np.flatnonzero(consecutive) if bridge_holes else np.arange(len(match.frame))
    player, det = match.player[use], match.detected[use]
    boundary = np.ones(len(use), dtype=np.bool_)
    if bridge_holes:
        # The probes compared each row with the row just before it in the player's series,
        # which may be a row the probes left out of the count.
        before = match.detected[np.maximum(use - 1, 0)]
        boundary[1:] = (player[1:] != player[:-1]) | (det[1:] != before[1:])
    else:
        boundary[1:] = (player[1:] != player[:-1]) | (det[1:] != det[:-1]) | ~consecutive[use][1:]
    firsts = np.flatnonzero(boundary)
    lasts = np.r_[firsts[1:] - 1, len(use) - 1]
    first, last = use[firsts], use[lasts]
    length = lasts - firsts + 1
    nxt = np.r_[first[1:], len(match.frame)]
    joins = (
        (lasts + 1 < len(use))
        & (match.player[np.minimum(nxt, len(match.frame) - 1)] == match.player[last])
        & (match.frame[np.minimum(nxt, len(match.frame) - 1)] == match.frame[last] + 1)
    )
    jump = np.where(joins, step[np.minimum(nxt, len(match.frame) - 1)], np.nan)
    step_used = step[use]
    csum = np.r_[0.0, np.cumsum(np.nan_to_num(step_used))]
    valid = np.r_[0, np.cumsum(~np.isnan(step_used))]
    seen = valid[lasts + 1] - valid[firsts]
    inside = np.where(seen > 0, (csum[lasts + 1] - csum[firsts]) / np.maximum(seen, 1), np.nan)
    return Runs(
        player=match.player[first],
        detected=match.detected[last],
        start_frame=match.frame[first],
        length=length,
        left_closed=consecutive[first],
        jump=jump,
        mean_step=inside,
    )


def _quantiles(values: NDArray[np.float64], qs: tuple[float, ...]) -> list[float | None]:
    clean = values[~np.isnan(values)]
    if len(clean) == 0:
        return [None] * len(qs)
    return [float(v) for v in np.quantile(clean, qs)]


def run_summary(runs: Runs) -> dict[str, object]:
    """Extrapolated runs of a match: count, length, jump and share of frames, by gap band.

    ``jump_*`` are over the runs that end on a detected frame; ``closed_*`` over those that
    also start on the frame after a detected one (detected on both sides).
    """
    out: dict[str, object] = {}
    ex = ~runs.detected
    q = _quantiles(runs.length[ex].astype(np.float64), (0.5, 0.9, 0.99))
    out["runs"] = {
        "n": int(ex.sum()),
        "frames": int(runs.length[ex].sum()),
        "length_median": q[0],
        "length_p90": q[1],
        "length_p99": q[2],
    }
    bands = band_of(runs.length)
    total = float(runs.length[ex].sum())
    by_band: dict[str, object] = {}
    for i, (name, _) in enumerate(BANDS):
        pick = ex & (bands == i)
        jq = _quantiles(runs.jump[pick], (0.5, 0.9, 0.99))
        mq = _quantiles(runs.mean_step[pick], (0.5,))
        closed = pick & runs.left_closed
        cq = _quantiles(runs.jump[closed], (0.5, 0.9))
        by_band[name] = {
            "n": int(pick.sum()),
            "n_with_jump": int((pick & ~np.isnan(runs.jump)).sum()),
            "n_closed": int((closed & ~np.isnan(runs.jump)).sum()),
            "frame_share": float(runs.length[pick].sum()) / total if total else None,
            "jump_median": jq[0],
            "jump_p90": jq[1],
            "jump_p99": jq[2],
            "closed_jump_median": cq[0],
            "closed_jump_p90": cq[1],
            "inside_step_median": mq[0],
        }
    out["by_band"] = by_band
    return out


def step_summary(match: MatchData) -> dict[str, object]:
    """Step per 0.1 s by detection transition (previous frame to this one) of the match."""
    consecutive, step = _steps(match)
    prev = np.r_[False, match.detected[:-1]]
    kinds = {
        "detected_to_detected": prev & match.detected,
        "detected_to_extrapolated": prev & ~match.detected,
        "extrapolated_to_detected": ~prev & match.detected,
        "extrapolated_to_extrapolated": ~prev & ~match.detected,
    }
    out: dict[str, object] = {}
    for name, mask in kinds.items():
        pick = mask & consecutive
        q = _quantiles(step[pick], (0.5, 0.9, 0.95, 0.99))
        out[name] = {"n": int(pick.sum()), "p50": q[0], "p90": q[1], "p95": q[2], "p99": q[3]}
    return out


def linear_rounding_floor(seed: int = 0, n: int = 200_000) -> dict[str, float]:
    """Second difference of an exactly straight, constant-speed path rounded to 0.01 m.

    The provider's coordinates are on a 1 cm grid, so even a perfectly linear path has a
    second difference above zero. Simulated, not measured: ``n`` paths of three points, a
    random start, a speed up to 0.7 m per frame and a random direction, from a seeded
    generator. It is the value an exactly interpolated stretch would show.
    """
    rng = np.random.default_rng(seed)
    start = rng.uniform(-50, 50, (n, 2))
    speed = rng.uniform(0, 0.7, n)
    angle = rng.uniform(0, 2 * np.pi, n)
    step = np.stack([speed * np.cos(angle), speed * np.sin(angle)], axis=1)
    points = np.round(np.stack([start + k * step for k in range(3)]), 2)
    accel = np.hypot(*(points[2] - 2 * points[1] + points[0]).T)
    return {
        "p50": float(np.quantile(accel, 0.5)),
        "p90": float(np.quantile(accel, 0.9)),
        "p99": float(np.quantile(accel, 0.99)),
    }


def unlisted_stretches(match: MatchData) -> dict[str, object]:
    """Stretches of frames, inside one period, where the provider lists no row for a player.

    ``sides`` counts them by the kind of frame on each side (``is_detected`` of the last row
    before and the first row after); ``length`` is in frames. A player first listed after the
    start of a period, or last listed before its end, has no stretch there.
    """
    before = np.flatnonzero(
        (match.player[1:] == match.player[:-1])
        & (match.period[1:] == match.period[:-1])
        & (match.frame[1:] > match.frame[:-1] + 1)
    )
    length = (match.frame[before + 1] - match.frame[before] - 1).astype(np.float64)
    q = _quantiles(length, (0.5, 0.9, 0.99))
    kinds = {
        "detected_detected": (True, True),
        "detected_extrapolated": (True, False),
        "extrapolated_detected": (False, True),
        "extrapolated_extrapolated": (False, False),
    }
    sides = {
        name: int(((match.detected[before] == a) & (match.detected[before + 1] == b)).sum())
        for name, (a, b) in kinds.items()
    }
    return {
        "n": int(len(before)),
        "frames": int(length.sum()),
        "length_median": q[0],
        "length_p90": q[1],
        "length_p99": q[2],
        "longer_than_50_frames": int((length > 50).sum()),
        "sides": sides,
    }


def second_differences(match: MatchData) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Second difference ``|p(t+1) - 2 p(t) + p(t-1)|`` (m per frame squared) of every player row.

    ``centre[i]`` is true where rows i-1, i and i+1 are consecutive frames of one player; the
    second difference is NaN elsewhere.
    """
    n = len(match.frame)
    consecutive, _ = _steps(match)
    centre = np.zeros(n, dtype=np.bool_)
    centre[1:-1] = consecutive[1:-1] & consecutive[2:]
    accel = np.full(n, np.nan)
    accel[1:-1] = np.hypot(
        match.x[2:] - 2 * match.x[1:-1] + match.x[:-2],
        match.y[2:] - 2 * match.y[1:-1] + match.y[:-2],
    )
    return accel, centre


def acceleration_summary(match: MatchData) -> dict[str, object]:
    """Second difference (metres per frame squared) of extrapolated against detected frames.

    The second difference ``|p(t+1) - 2 p(t) + p(t-1)|`` is taken where the three frames are
    consecutive frames of one player and all detected or all extrapolated. Extrapolated rows
    are banded by the length of their run; detected rows are pooled and also banded by the
    length of their own run, with the same cuts.
    """
    consecutive, _ = _steps(match)
    accel, centre = second_differences(match)
    same = np.zeros(len(match.frame), dtype=np.bool_)
    same[1:-1] = (match.detected[:-2] == match.detected[1:-1]) & (
        match.detected[2:] == match.detected[1:-1]
    )
    pick = centre & same
    runs = extrapolated_runs(match)
    run_of = (
        np.cumsum(np.r_[True, ~consecutive[1:] | (match.detected[1:] != match.detected[:-1])]) - 1
    )
    band = band_of(runs.length)[run_of]

    def stats(mask: NDArray[np.bool_]) -> dict[str, object]:
        q = _quantiles(accel[mask], (0.5, 0.9, 0.99))
        return {"n": int(mask.sum()), "p50": q[0], "p90": q[1], "p99": q[2]}

    extrapolated = pick & ~match.detected
    detected = pick & match.detected
    return {
        "linear_floor": linear_rounding_floor(),
        "detected": stats(detected),
        "extrapolated": stats(extrapolated),
        "extrapolated_by_band": {
            name: stats(extrapolated & (band == i)) for i, (name, _) in enumerate(BANDS)
        },
        "detected_by_run_band": {
            name: stats(detected & (band == i)) for i, (name, _) in enumerate(BANDS)
        },
    }
