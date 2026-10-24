"""V0 against V1 and the amputation error of a metric, on a synthetic match.

Run it with ``uv run python examples/sensitivity.py``. It builds, in memory, a match in the shape
of the base's silver (frames, events, ``dim_team_period``) and sends it down the same public path
a reuser's own silver takes: ``long_table`` (the long Parquet, with ``gap_len``), the metric
units, ``sensitivity`` (V0, V1, V2) and ``amputate`` (the error of filling a gap with a straight
line). It reads no file and never touches ``data/``.

Swap :func:`synthetic_silver` for ``ac2fb.protocol.data.read_frames`` / ``read_events`` /
``read_dim`` on your own data root (``FTBASE_DATA_ROOT``) to run it on a real match; those readers
are the guarded door to the silver and refuse the held-out matches of ``protocol/split.json``.
The numbers this prints are for the synthetic match: they are not findings.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa

from ac2fb.reliability import amputate, metrics
from ac2fb.reliability.long import long_table
from ac2fb.reliability.match import build_match
from ac2fb.reliability.sensitivity import sensitivity, window_frames

MATCH_ID = 1
FRAMES = 2000
METRIC = "line_height_m"
DISCLAIMER = "synthetic numbers, not findings"


def synthetic_silver() -> tuple[pa.Table, pa.Table, pa.Table]:
    """Silver ``frames``, ``events`` and ``dim_team_period`` of one 11 v 11 match, one period.

    Players move on smooth curved paths; a gap hides a player now and then and the "provider"
    fills it with the straight line between the detections on either side, so a gap costs
    accuracy exactly where the path curves.
    """
    rng = np.random.default_rng(7)
    frame = np.arange(FRAMES)
    team_of = {p: 1 if p <= 11 else 2 for p in range(1, 23)}
    path: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    detected: dict[int, np.ndarray] = {}
    for p in team_of:
        base = rng.uniform(-35, 35)
        phase, period = rng.uniform(0, 6.3, 2), rng.uniform(60, 140, 2)
        x = base + 8 * np.sin(2 * np.pi * frame / period[0] + phase[0])
        y = rng.uniform(-25, 25) + 6 * np.sin(2 * np.pi * frame / period[1] + phase[1])
        seen = np.ones(FRAMES, dtype=bool)
        for start in range(0, FRAMES - 60, 100):
            if rng.random() < 0.4:
                seen[start + 20 : start + 20 + int(rng.integers(10, 40))] = False
        seen[[0, -1]] = True
        path[p] = (
            np.interp(frame, frame[seen], x[seen]) * ~seen + x * seen,  # the provider's fill
            np.interp(frame, frame[seen], y[seen]) * ~seen + y * seen,
        )
        detected[p] = seen
        path[-p] = (x, y)  # the truth, used only to put the ball on the carrier
    rows: list[dict[str, object]] = []
    carrier = {f: 1 + int(rng.integers(11)) + 11 * ((f // 400) % 2) for f in range(100, 1900, 40)}
    at = np.maximum.accumulate(np.where(np.isin(frame, list(carrier)), frame, 0))
    held = np.array([carrier.get(int(a), 1) for a in at])
    for f in frame:
        for p, team in team_of.items():
            rows.append(
                _row(f, f"fb:{p}", "player", f"fb:{team}", *_at(path[p], f), detected[p][f])
            )
        x, y = path[-int(held[f])]
        rows.append(_row(f, "fb:ball", "ball", None, x[f], y[f], True))
    frames = pa.Table.from_pylist(rows)
    events = [_event("player_possession", f, 1 if p <= 11 else 2, p) for f, p in carrier.items()]
    events += [_event("phases_of_play", f, 1 + (f // 200) % 2, None) for f in range(100, 1900, 200)]
    dims = pa.table(
        {
            "match_id": [f"fb:{MATCH_ID}"] * 2,
            "period": pa.array([1, 1], pa.int16()),
            "team_id": ["fb:1", "fb:2"],
            "attack_sign": [1, -1],
        }
    )
    return frames, pa.Table.from_pylist(events), dims


def _at(xy: tuple[np.ndarray, np.ndarray], f: int) -> tuple[float, float]:
    return float(xy[0][f]), float(xy[1][f])


def _row(
    f: int, entity: str, kind: str, team: str | None, x: float, y: float, seen: bool
) -> dict[str, object]:
    return {
        "match_id": f"fb:{MATCH_ID}",
        "native_match_id": MATCH_ID,
        "period": 1,
        "frame_native": int(f),
        "entity_id": entity,
        "entity_kind": kind,
        "team_id": team,
        "x_m": x,
        "y_m": y,
        "is_detected": bool(seen),
    }


def _event(family: str, frame: int, team: int, player: int | None) -> dict[str, object]:
    return {
        "native_family": family,
        "native_subtype": None,
        "frame_start": frame,
        "frame_end": frame,
        "period": 1,
        "team_id": f"fb:{team}",
        "player_id": None if player is None else f"fb:{player}",
    }


def main() -> str:
    frames, events, dims = synthetic_silver()
    match = build_match(MATCH_ID, frames, events, dims)
    metric, windows = metrics.metric_units(match)[METRIC]
    long = long_table(frames)
    seen = sensitivity(metric, long, windows)[MATCH_ID]
    cut = amputate.amputate(
        match,
        window_frames(long),
        metric,
        windows,
        amputate.hiding(match),
        np.random.default_rng(amputate.SEED),
    )
    error = np.abs(np.array(cut.errors))
    mean_v0 = "n/a" if seen.v0.mean is None else f"{seen.v0.mean:.2f}"
    mean_v1 = "n/a" if seen.v1.mean is None else f"{seen.v1.mean:.2f}"
    return (
        f"{METRIC}: V0 n={seen.v0.n} mean={mean_v0} m, V1 n={seen.v1.n} mean={mean_v1} m, "
        f"extrapolated={seen.extrapolated_fraction:.3f}, amputation n={len(error)} "
        f"mean_abs_error={error.mean():.3f} m ({DISCLAIMER})"
    )


if __name__ == "__main__":
    print(main())
