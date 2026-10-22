"""The amputation reference: the error a metric carries when its players' gaps are filled by a
straight line between the detections on either side.

``reports/amputation.csv``, one row per match, metric and gap band. The units are the V1 units
of each metric of :data:`~ac2fb.reliability.metrics.METRICS` (its players detected in every frame
of the window), so the value read there is what the camera saw. In each unit, each of the
metric's players is hidden as the camera hides players in that match:

- with the probability that a player at its distance from the ball at ``t`` is not detected
  (the sample of :func:`~ac2fb.reliability.visibility.detection_by_ball_distance`, the figures
  of ``layer2.json``), on its own draw;
- if hidden, its gap is copied from a real extrapolated player-frame of the same match at the
  same distance from the ball, drawn among those with a detection before and after it in the
  period: the frames back to that previous detection and ahead to that next one. ``gap_len``
  so has the match's distribution, weighted by length as a frame lives it;
- the gap is put around ``t`` with those two numbers, its ends move out to the nearest frames
  where this player is detected (the provider fills between detections, task 12), and the
  frames of the window inside it get the straight line between the two ends.

The metric is computed again on the window so filled; the error is that value minus the seen
one. A unit goes to the band of :data:`~ac2fb.reliability.runs.BANDS` of its longest gap,
counted in frames between the two detections; ``none`` holds the units where nobody was hidden,
``all`` every unit. A unit is skipped when the ball has no row at ``t``, when a hidden player has
no detection on one side of its gap in the period, or when the metric cannot be computed after
the fill.

Declared: the straight line is a bound, not the provider's model (its fill is smoother than a
seen path, but not a line: task 12); only the metric's players are hidden, each on its own draw,
so any other player keeps its listed position; the units are those the camera saw whole, which
are near the ball; the end of a gap is read after ``t`` (layer 2 is descriptive and computes no
outcome). The draws come from a generator seeded by :data:`SEED`, the match and the metric, so
the file is the same on every machine and no match moves another.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from ac2fb.reliability import metrics
from ac2fb.reliability.match import MatchData, load_with_long, locate_rows
from ac2fb.reliability.runs import BANDS, band_of
from ac2fb.reliability.sensitivity import Metric, Reading, Window, WindowFrames, window_frames
from ac2fb.reliability.table import Check, cell, check_csv, render_csv
from ac2fb.reliability.visibility import BALL_DISTANCE_EDGES

__all__ = [
    "BAND_NAMES",
    "COLUMNS",
    "EVERY",
    "REPORT_NAME",
    "SEED",
    "Amputation",
    "Ends",
    "Hiding",
    "amputate",
    "check",
    "detected_sides",
    "ends_of",
    "fill",
    "hiding",
    "match_rows",
    "write_table",
]

REPORT_NAME = "amputation.csv"
SEED = 20261022  # with the match and the metric: one stream of draws each
EVERY = 10  # frames: the sample of visibility.detection_by_ball_distance
_SPAN = 1 << 32  # the key of MatchData is player * 2**32 + frame
BAND_NAMES: tuple[str, ...] = ("none", *(name for name, _ in BANDS), "all")
COLUMNS: tuple[str, ...] = (
    "match_id",
    "metric",
    "band",
    "n",
    "mean_error",
    "mean_abs_error",
    "p90_abs_error",
    "max_abs_error",
    "n_units",
    "n_skipped",
)
_KEY = 3  # match_id, metric and band name a row


@dataclass(frozen=True)
class Hiding:
    """How the camera hides a player in one match, by bin of distance to the ball.

    The bins are those of :data:`~ac2fb.reliability.visibility.BALL_DISTANCE_EDGES`. For each:
    the share of sampled player-frames not detected, and, for each sampled extrapolated
    player-frame with a detection before and after it in the period, the frames back to the
    first and ahead to the second.
    """

    probability: tuple[float, ...]
    back: tuple[NDArray[np.int64], ...]
    ahead: tuple[NDArray[np.int64], ...]


@dataclass(frozen=True)
class Ends:
    """The two detections of one player around a gap: their frames and positions."""

    lo: int
    lo_x: float
    lo_y: float
    hi: int
    hi_x: float
    hi_y: float


@dataclass(frozen=True)
class Amputation:
    """One metric in one match: its V1 units, those skipped, and the band and error of the rest."""

    n_units: int
    n_skipped: int
    bands: tuple[str, ...]
    errors: tuple[float, ...]


def detected_sides(match: MatchData) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """For each player row, the row of the nearest detection at or before it and at or after it,
    in the same player's period (-1 where there is none)."""
    n = len(match.frame)
    idx = np.arange(n)
    new = np.r_[
        True, (match.player[1:] != match.player[:-1]) | (match.period[1:] != match.period[:-1])
    ]
    first = np.maximum.accumulate(np.where(new, idx, 0))
    last = np.minimum.accumulate(np.where(np.r_[new[1:], True], idx, n)[::-1])[::-1]
    before = np.maximum.accumulate(np.where(match.detected, idx, -1))
    after = np.minimum.accumulate(np.where(match.detected, idx, n)[::-1])[::-1]
    return (
        np.where(before >= first, before, -1).astype(np.int64),
        np.where(after <= last, after, -1).astype(np.int64),
    )


def _bin(distance: NDArray[np.float64]) -> NDArray[np.int64]:
    return np.searchsorted(np.array(BALL_DISTANCE_EDGES), distance, side="right")


def hiding(match: MatchData) -> Hiding:
    """The hiding of one match, from the player-frames of one frame in :data:`EVERY` with a ball
    row (the sample of ``detection_by_ball_distance``)."""
    pick = np.flatnonzero(match.frame % EVERY == 0)
    pos = np.searchsorted(match.ball_frame, match.frame[pick])
    safe = np.minimum(pos, max(len(match.ball_frame) - 1, 0))
    has = (pos < len(match.ball_frame)) & (match.ball_frame[safe] == match.frame[pick])
    rows, ball = pick[has], safe[has]
    which = _bin(np.hypot(match.x[rows] - match.ball_x[ball], match.y[rows] - match.ball_y[ball]))
    before, after = detected_sides(match)
    gone = ~match.detected[rows]
    closed = gone & (before[rows] >= 0) & (after[rows] >= 0)
    probability: list[float] = []
    back: list[NDArray[np.int64]] = []
    ahead: list[NDArray[np.int64]] = []
    for k in range(len(BALL_DISTANCE_EDGES) + 1):
        in_bin = which == k
        n = int(in_bin.sum())
        probability.append(int(gone[in_bin].sum()) / n if n else 0.0)
        mine = rows[in_bin & closed]
        back.append(match.frame[mine] - match.frame[before[mine]])
        ahead.append(match.frame[after[mine]] - match.frame[mine])
    return Hiding(tuple(probability), tuple(back), tuple(ahead))


def ends_of(
    match: MatchData,
    sides: tuple[NDArray[np.int64], NDArray[np.int64]],
    player: int,
    t: int,
    back: int,
    ahead: int,
) -> Ends | None:
    """The detections of ``player`` around a gap put at ``t``: the last at or before ``t - back``
    and the first at or after ``t + ahead``, both in the period of its row at ``t``.

    ``sides`` is :func:`detected_sides` of the match. ``None`` when one of them is missing or the
    player has no row at ``t``.
    """
    before, after = sides
    (here,) = locate_rows(match, np.array([player]), np.array([t]))
    if here < 0:
        return None
    lo = int(np.searchsorted(match.key, player * _SPAN + t - back, side="right")) - 1
    hi = int(np.searchsorted(match.key, player * _SPAN + t + ahead, side="left"))
    lo = int(before[lo]) if lo >= 0 and match.player[lo] == player else -1
    hi = int(after[hi]) if hi < len(match.key) and match.player[hi] == player else -1
    if lo < 0 or hi < 0 or not match.period[lo] == match.period[here] == match.period[hi]:
        return None
    return Ends(
        int(match.frame[lo]),
        float(match.x[lo]),
        float(match.y[lo]),
        int(match.frame[hi]),
        float(match.x[hi]),
        float(match.y[hi]),
    )


def fill(window: WindowFrames, ends: Mapping[int, Ends]) -> WindowFrames:
    """The window with each player of ``ends`` on the straight line between its two detections,
    and not detected, in the frames strictly between them; everything else as it was."""
    x, y, detected = window.x.copy(), window.y.copy(), window.detected.copy()
    for row, player in enumerate(window.player_ids):
        e = ends.get(int(player))
        if e is None:
            continue
        inside = (window.frames > e.lo) & (window.frames < e.hi)
        w = (window.frames[inside] - e.lo) / (e.hi - e.lo)
        x[row, inside] = e.lo_x + w * (e.hi_x - e.lo_x)
        y[row, inside] = e.lo_y + w * (e.hi_y - e.lo_y)
        detected[row, inside] = False
    return dataclasses.replace(window, x=x, y=y, detected=detected)


def _whole(data: WindowFrames, reading: Reading) -> bool:
    """V1: every player of the reading listed and detected in every frame of the window."""
    index = {int(p): i for i, p in enumerate(data.player_ids)}
    mine = [index[p] for p in reading.player_ids if p in index]
    return len(mine) == len(reading.player_ids) and bool(
        (data.present[mine] & data.detected[mine]).all()
    )


def amputate(
    match: MatchData,
    frames: Callable[[Window], WindowFrames | None],
    metric: Metric,
    windows: Sequence[Window],
    hide: Hiding,
    rng: np.random.Generator,
) -> Amputation:
    """Hide the players of ``metric`` in its V1 units as the module says, and measure the error.

    ``frames`` builds the matrices of a window (:func:`~ac2fb.reliability.sensitivity.
    window_frames` of the match's long table); ``hide`` is :func:`hiding` of the match.
    """
    sides = detected_sides(match)
    bands: list[str] = []
    errors: list[float] = []
    units = skipped = 0
    for window in windows:
        data = frames(window)
        seen = None if data is None else metric(data)
        if data is None or seen is None or not _whole(data, seen):
            continue
        units += 1
        t = window.frame_end
        ball = int(np.searchsorted(match.ball_frame, t))
        if ball >= len(match.ball_frame) or match.ball_frame[ball] != t:
            skipped += 1
            continue
        index = {int(p): i for i, p in enumerate(data.player_ids)}
        ends: dict[int, Ends] = {}
        lost = False  # a hidden player without a detection on one side of its gap
        for player in seen.player_ids:
            at = index[player]
            dx, dy = data.x[at, -1] - match.ball_x[ball], data.y[at, -1] - match.ball_y[ball]
            k = int(_bin(np.hypot(dx, dy)))
            if rng.random() >= hide.probability[k] or len(hide.back[k]) == 0:
                continue
            j = int(rng.integers(len(hide.back[k])))
            found = ends_of(match, sides, player, t, int(hide.back[k][j]), int(hide.ahead[k][j]))
            if found is None:
                lost = True
                break
            ends[player] = found
        filled = None if lost else metric(fill(data, ends))
        if filled is None:
            skipped += 1
            continue
        longest = max((e.hi - e.lo - 1 for e in ends.values()), default=0)
        bands.append(BAND_NAMES[1 + int(band_of(np.array([longest]))[0])] if ends else "none")
        errors.append(filled.value - seen.value)
    return Amputation(units, skipped, tuple(bands), tuple(errors))


def _rows(match_id: int, metric: str, a: Amputation) -> list[list[str]]:
    rows: list[list[str]] = []
    for name in BAND_NAMES:
        picked = [e for b, e in zip(a.bands, a.errors, strict=True) if name in ("all", b)]
        figures: list[float | None] = [None] * 4
        if picked:
            error = np.array(picked, dtype=np.float64)
            size = np.abs(error)
            figures = [float(v) for v in (error.mean(), size.mean(), np.quantile(size, 0.9))]
            figures.append(float(size.max()))
        values = [len(picked), *figures, a.n_units, a.n_skipped]
        rows.append([str(match_id), metric, name, *map(cell, values)])
    return rows


def match_rows(match_id: int) -> list[list[str]]:
    """The rows of one match, read through the guarded door, metrics in :data:`METRICS` order."""
    match, long = load_with_long(match_id)
    frames = window_frames(long)
    hide = hiding(match)
    rows: list[list[str]] = []
    for name, (metric, windows) in metrics.metric_units(match).items():
        rng = np.random.default_rng([SEED, match_id, metrics.METRICS.index(name)])
        rows += _rows(match_id, name, amputate(match, frames, metric, windows, hide, rng))
    return rows


def write_table(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Write ``reports_dir/amputation.csv`` for the matches, sorted by match id; return it."""
    rows = [row for m in sorted(match_ids) for row in match_rows(m)]
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_csv(COLUMNS, rows).encode("utf-8"))
    return path


def check(match_ids: Sequence[int], raw: bytes | None) -> Check:
    """Recompute the amputation rows of the matches and compare every cell with ``raw``."""
    return check_csv(REPORT_NAME, COLUMNS, _KEY, match_ids, match_rows, raw)
