"""How much a team metric moves when it is computed from what the camera saw.

A *metric* is a function of one unit, a window of frames of one match (:class:`WindowFrames`),
that returns a value and the players it was computed from (:class:`Reading`), or ``None`` when
the unit cannot be measured. :func:`sensitivity` runs it over the units of a long table (see
:mod:`ac2fb.reliability.long`) and reports, per match, the three variants of decision 6:

- **V0**: every unit.
- **V1**: the units whose players are all detected in every frame of the window (a declared
  selection: it keeps what is near the ball and in view).
- **V2**: the units split by how many of those players are detected in the whole window, so a
  metric that depends on what is extrapolated changes monotonically with that count.

Alongside: the fraction of the player-frames behind the metric that are extrapolated, and the
``gap_len`` of those frames. A player-frame the provider does not list counts as not detected
(and is reported separately as absent).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
from numpy.typing import NDArray

__all__ = [
    "GapSummary",
    "Metric",
    "Reading",
    "Sensitivity",
    "Stratum",
    "Variant",
    "Window",
    "WindowFrames",
    "sensitivity",
]


@dataclass(frozen=True)
class Window:
    """Frames ``frame_start`` to ``frame_end`` (both included) of one match (native id)."""

    match_id: int
    frame_start: int
    frame_end: int


@dataclass(frozen=True)
class WindowFrames:
    """The players of one window as matrices (players by frames).

    ``x`` and ``y`` are NaN where the provider lists no row; ``present`` marks the rows;
    ``detected`` is false where absent; ``gap_len`` is -1 where absent or undefined.
    """

    window: Window
    frames: NDArray[np.int64]
    player_ids: NDArray[np.int64]
    team_ids: NDArray[np.int64]
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    present: NDArray[np.bool_]
    detected: NDArray[np.bool_]
    gap_len: NDArray[np.int64]


@dataclass(frozen=True)
class Reading:
    """A metric's value for a unit and the ids of the players it was computed from."""

    value: float
    player_ids: tuple[int, ...]


Metric = Callable[[WindowFrames], Reading | None]


@dataclass(frozen=True)
class Variant:
    """Mean of the metric over ``n`` units."""

    n: int
    mean: float | None


@dataclass(frozen=True)
class Stratum:
    """Units where exactly ``detected_players`` of the metric's players are detected throughout."""

    detected_players: int
    n: int
    mean: float | None


@dataclass(frozen=True)
class GapSummary:
    """``gap_len`` over the extrapolated player-frames behind the metric (frames)."""

    n: int
    median: float | None
    p90: float | None
    max: int | None


@dataclass(frozen=True)
class Sensitivity:
    """One match: the metric in V0, V1 and V2, and how much of it is extrapolated."""

    match_id: int
    n_units: int
    n_skipped: int
    v0: Variant
    v1: Variant
    v2: tuple[Stratum, ...]
    player_frames: int
    extrapolated_fraction: float | None
    absent_fraction: float | None
    gap_len: GapSummary


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _matrices(
    window: Window,
    players: NDArray[np.int64],
    starts: NDArray[np.int64],
    ends: NDArray[np.int64],
    cols: dict[str, NDArray[Any]],
) -> WindowFrames | None:
    frames = np.arange(window.frame_start, window.frame_end + 1, dtype=np.int64)
    frame_col = cols["frame"]
    keep: list[int] = []
    rows: list[NDArray[np.int64]] = []
    cell: list[NDArray[np.int64]] = []
    for i in range(len(players)):
        lo = starts[i] + np.searchsorted(frame_col[starts[i] : ends[i]], window.frame_start)
        hi = starts[i] + np.searchsorted(
            frame_col[starts[i] : ends[i]], window.frame_end, side="right"
        )
        if hi > lo:
            keep.append(i)
            rows.append(np.arange(lo, hi))
            cell.append(frame_col[lo:hi] - window.frame_start)
    if not keep:
        return None
    shape = (len(keep), len(frames))
    x, y = np.full(shape, np.nan), np.full(shape, np.nan)
    present = np.zeros(shape, dtype=np.bool_)
    detected = np.zeros(shape, dtype=np.bool_)
    gap = np.full(shape, -1, dtype=np.int64)
    for k, (r, c) in enumerate(zip(rows, cell, strict=True)):
        x[k, c], y[k, c] = cols["x"][r], cols["y"][r]
        present[k, c], detected[k, c] = True, cols["detected"][r]
        gap[k, c] = cols["gap"][r]
    return WindowFrames(
        window=window,
        frames=frames,
        player_ids=players[keep],
        team_ids=np.array([cols["team"][starts[i]] for i in keep], dtype=np.int64),
        x=x,
        y=y,
        present=present,
        detected=detected,
        gap_len=gap,
    )


def _one_match(
    match_id: int, table: pa.Table, metric: Metric, windows: Sequence[Window] | None
) -> Sensitivity:
    keep = table.filter(pc.is_valid(table["player_id"]))
    player = keep["player_id"].to_numpy().astype(np.int64)
    frame = keep["frame"].to_numpy().astype(np.int64)
    order = np.lexsort((frame, player))
    cols: dict[str, NDArray[Any]] = {
        "frame": frame[order],
        "x": keep["x"].to_numpy(zero_copy_only=False).astype(np.float64)[order],
        "y": keep["y"].to_numpy(zero_copy_only=False).astype(np.float64)[order],
        "detected": keep["is_detected"].to_numpy(zero_copy_only=False).astype(np.bool_)[order],
        "gap": pc.fill_null(keep["gap_len"], -1).to_numpy().astype(np.int64)[order],
        "team": pc.fill_null(keep["team_id"], -1).to_numpy().astype(np.int64)[order],
    }
    sorted_player = player[order]
    players, starts = np.unique(sorted_player, return_index=True)
    ends = np.r_[starts[1:], len(sorted_player)]
    if windows is None:
        windows = [Window(match_id, int(f), int(f)) for f in np.unique(cols["frame"])]
    values: list[float] = []
    kept: list[float] = []
    by_count: dict[int, list[float]] = {}
    skipped = cells = extrapolated = absent = 0
    gaps: list[NDArray[np.int64]] = []
    for window in windows:
        data = _matrices(window, players, starts, ends, cols)
        reading = metric(data) if data is not None else None
        if data is None or reading is None:
            skipped += 1
            continue
        index = {int(p): i for i, p in enumerate(data.player_ids)}
        mine = [index[p] for p in reading.player_ids if p in index]
        whole = data.present[mine].all(axis=1) & data.detected[mine].all(axis=1)
        values.append(reading.value)
        by_count.setdefault(int(whole.sum()), []).append(reading.value)
        if len(mine) == len(reading.player_ids) and whole.all():
            kept.append(reading.value)
        unlisted = (len(reading.player_ids) - len(mine)) * len(data.frames)
        cells += data.present[mine].size + unlisted
        absent += int((~data.present[mine]).sum()) + unlisted
        gone = data.present[mine] & ~data.detected[mine]
        extrapolated += int(gone.sum())
        gaps.append(data.gap_len[mine][gone])
    pooled = np.concatenate(gaps) if gaps else np.zeros(0, dtype=np.int64)
    pooled = pooled[pooled >= 0]
    return Sensitivity(
        match_id=match_id,
        n_units=len(values),
        n_skipped=skipped,
        v0=Variant(len(values), _mean(values)),
        v1=Variant(len(kept), _mean(kept)),
        v2=tuple(Stratum(k, len(v), _mean(v)) for k, v in sorted(by_count.items())),
        player_frames=cells,
        extrapolated_fraction=extrapolated / cells if cells else None,
        absent_fraction=absent / cells if cells else None,
        gap_len=GapSummary(
            n=len(pooled),
            median=float(np.median(pooled)) if len(pooled) else None,
            p90=float(np.quantile(pooled, 0.9)) if len(pooled) else None,
            max=int(pooled.max()) if len(pooled) else None,
        ),
    )


def sensitivity(
    metric: Metric, frames: pa.Table, windows: Sequence[Window] | None = None
) -> dict[int, Sensitivity]:
    """The metric in V0, V1 and V2 for each match of ``frames``, a long table.

    ``frames`` is the table of :func:`~ac2fb.reliability.long.long_table` (its Parquet
    files have the same columns). ``windows`` gives the units (each names its match); without
    it every frame of every match is a unit, which is slow on a real match: pass windows.
    Units for which ``metric`` returns ``None`` are skipped and counted in ``n_skipped``.
    """
    native = {m: int(m.split(":", 1)[1]) for m in set(frames["match_id"].to_pylist())}
    out: dict[int, Sensitivity] = {}
    for label, match_id in sorted(native.items(), key=lambda kv: kv[1]):
        part = frames.filter(pc.equal(frames["match_id"], label))
        mine = None if windows is None else [w for w in windows if w.match_id == match_id]
        out[match_id] = _one_match(match_id, part, metric, mine)
    return out
