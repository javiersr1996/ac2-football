"""The long Parquet of decision 4, and ``gap_len``.

One row per entity (player or ball) and frame of a match, as the base's silver has it, plus
``gap_len``: the number of frames between the row and the nearest detected frame of the same
entity in the same period (0 when the row is detected itself). It is computed here, never in
the base, and written under ``<data root>/layer2/frames_long/<native match id>.parquet``.

Columns (``LONG_SCHEMA``): ``match_id`` (string, ``fb:<native id>``), ``period`` (int16),
``frame`` (int64, the provider's frame number), ``player_id`` (int64, null for the ball),
``team_id`` (int64, null for the ball), ``x`` and ``y`` (float64 metres, the provider's
frame, not oriented to attack), ``is_detected`` (bool), ``gap_len`` (int32, null when the
entity has no detected frame in that period). Rows are sorted by entity (the ball first) and
frame. A frame the provider does not list for an entity has no row; distances count frame
numbers, not rows.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from numpy.typing import NDArray

from ac2fb.protocol import data

__all__ = [
    "LONG_COLUMNS",
    "LONG_SCHEMA",
    "NO_DETECTION",
    "gap_len",
    "long_dir",
    "long_table",
    "write_long",
]

LONG_COLUMNS = (
    "match_id",
    "period",
    "frame",
    "player_id",
    "team_id",
    "x",
    "y",
    "is_detected",
    "gap_len",
)
LONG_SCHEMA = pa.schema(
    [
        ("match_id", pa.string()),
        ("period", pa.int16()),
        ("frame", pa.int64()),
        ("player_id", pa.int64()),
        ("team_id", pa.int64()),
        ("x", pa.float64()),
        ("y", pa.float64()),
        ("is_detected", pa.bool_()),
        ("gap_len", pa.int32()),
    ]
)
NO_DETECTION = -1  # ``gap_len`` of a row whose series holds no detected frame
_SOURCE_COLUMNS = (
    "match_id",
    "native_match_id",
    "period",
    "frame_native",
    "entity_id",
    "entity_kind",
    "team_id",
    "x_m",
    "y_m",
    "is_detected",
)
_BALL = -1  # entity code of the ball while sorting


def gap_len(
    series: NDArray[np.int64], frame: NDArray[np.int64], detected: NDArray[np.bool_]
) -> NDArray[np.int64]:
    """Frames to the nearest detected row of the same series (0 if detected).

    ``series`` identifies each series (equal values are contiguous) and rows are sorted by
    ``frame`` inside a series. A series with no detected row gets :data:`NO_DETECTION`.
    """
    n = len(frame)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    idx = np.arange(n)
    starts = np.maximum.accumulate(np.where(np.r_[True, series[1:] != series[:-1]], idx, 0))
    ends = np.minimum.accumulate(np.where(np.r_[series[1:] != series[:-1], True], idx, n)[::-1])[
        ::-1
    ]
    prev = np.maximum.accumulate(np.where(detected, idx, -1))
    nxt = np.minimum.accumulate(np.where(detected, idx, n)[::-1])[::-1]
    big = np.iinfo(np.int64).max
    back = np.where(prev >= starts, frame - frame[np.maximum(prev, 0)], big)
    ahead = np.where(nxt <= ends, frame[np.minimum(nxt, n - 1)] - frame, big)
    nearest = np.minimum(back, ahead)
    return np.where(nearest == big, NO_DETECTION, nearest).astype(np.int64)


def _ids(column: pa.ChunkedArray, keep: pa.ChunkedArray) -> pa.Array:
    """``fb:123`` to 123 where ``keep``, null elsewhere."""
    digits = pc.utf8_slice_codeunits(pc.if_else(keep, column, "fb:0"), 3)
    return pc.if_else(keep, pc.cast(digits, pa.int64()), pa.scalar(None, pa.int64()))


def long_table(frames: pa.Table) -> pa.Table:
    """The long table of decision 4 for the given silver frames (any number of matches).

    ``frames`` needs the columns of the base's silver ``frames`` named in ``_SOURCE_COLUMNS``.
    """
    missing = [c for c in _SOURCE_COLUMNS if c not in frames.column_names]
    if missing:
        raise ValueError(f"frames lack the columns {missing}")
    is_player = pc.equal(frames["entity_kind"], "player")
    player = _ids(frames["entity_id"], is_player)
    team = _ids(frames["team_id"], pc.and_(is_player, pc.is_valid(frames["team_id"])))
    entity = pc.fill_null(player, _BALL).to_numpy(zero_copy_only=False).astype(np.int64)
    match = frames["native_match_id"].to_numpy().astype(np.int64)
    frame = frames["frame_native"].to_numpy().astype(np.int64)
    period = frames["period"].to_numpy().astype(np.int64)
    detected = frames["is_detected"].to_numpy(zero_copy_only=False).astype(np.bool_)
    order = np.lexsort((frame, entity, match))
    match, entity, frame, period, detected = (
        a[order] for a in (match, entity, frame, period, detected)
    )
    changed = np.r_[True, (match[1:] != match[:-1]) | (entity[1:] != entity[:-1])]
    changed |= np.r_[True, period[1:] != period[:-1]]
    gaps = gap_len(np.cumsum(changed), frame, detected)

    rows = pa.array(order)

    def take(column: pa.ChunkedArray | pa.Array) -> pa.ChunkedArray | pa.Array:
        return column.take(rows)

    return pa.table(
        {
            "match_id": take(frames["match_id"]),
            "period": take(frames["period"]).cast(pa.int16()),
            "frame": pa.array(frame),
            "player_id": take(player),
            "team_id": take(team),
            "x": take(frames["x_m"]).cast(pa.float64()),
            "y": take(frames["y_m"]).cast(pa.float64()),
            "is_detected": pa.array(detected),
            "gap_len": pa.array(gaps.astype(np.int32), mask=gaps == NO_DETECTION),
        },
        schema=LONG_SCHEMA,
    )


def long_dir() -> Path:
    """Where the long Parquet files go: ``<data root>/layer2/frames_long``."""
    return data.data_dir() / "layer2" / "frames_long"


def write_long(match_ids: list[int], out_dir: Path | None = None) -> list[Path]:
    """Write the long Parquet of each match (read through the guarded door); return the paths.

    A held-out id raises :class:`~ac2fb.protocol.data.HeldOutLocked` before anything is read.
    """
    target = out_dir if out_dir is not None else long_dir()
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for match_id in match_ids:
        frames = data.read_frames([match_id], columns=list(_SOURCE_COLUMNS))
        path = target / f"{match_id}.parquet"
        pq.write_table(long_table(frames), path, compression="zstd")
        written.append(path)
    return written
