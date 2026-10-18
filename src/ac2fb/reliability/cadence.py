"""Cadence probe: how often the detected players' paths bend, and the shortest admissible window.

The provider publishes 10 frames per second, but a path could still be refreshed less often than
that (a real update every ``c`` frames, straight lines between). If so, the second difference of
a detected player is rounding noise except at the update frames, and the gap between bends is
``c``. This module measures that gap on detected players only, per match.

**Definitions.** A *centre* is a player row whose neighbours are the previous and next frame of
the same player (:func:`ac2fb.reliability.runs.second_differences`) and all three are detected.
A *kink* is a centre whose second difference is above :data:`KINK_THRESHOLD`. The *gap* between
two kinks of one player is their frame difference, counted only when every row between them is a
centre (a stretch with an extrapolated or unlisted frame never hides a kink inside a gap).
Gaps next to a break are not counted, so long gaps are under-represented (right-censoring).

**Threshold.** Coordinates are on a 1 cm grid, so a perfectly straight path still has a second
difference above zero. Each coordinate is off by at most 0.005 m, so the second difference of a
coordinate is off by at most ``0.005 * (1 + 2 + 1) = 0.02`` m and the 2-D one by at most
``0.02 * sqrt(2) = 0.0283`` m per frame squared (:data:`ROUNDING_BOUND`). :data:`KINK_THRESHOLD`
is 0.03, above that bound, so rounding alone never makes a kink. The report prints the simulated
rounding floor of :func:`ac2fb.reliability.runs.linear_rounding_floor` beside it, and the
cadence the same estimator reads with no threshold and with the simulated p99 of that floor.

**Rule for the shortest admissible window (written before the data was looked at).**

1. The cadence of a match is ``c``, the most frequent gap (the smallest on a tie).
2. The cadence of the calibration set is the largest ``c`` over its matches.
3. ``W_min`` (frames) is ``max(2 * c, G)``, with ``G`` the largest over the matches of the 90th
   percentile of the gap (the ``higher`` percentile, a whole number of frames).

Why: an outcome measured as displacement over ``[t, t + W]`` minus what the velocity at ``t``
predicted is zero for a path that does not bend, so the window has to be long enough to hold a
bend in most cases (``G``), and to hold at least three real updates, one at each end and one
between (``2 * c``). ``W_min`` in seconds is ``W_min / 10``. It is a floor: the protocol (task
19) may choose a longer window, never a shorter one.

Nothing here is an outcome of any candidate question: only the shape of detected paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from ac2fb.reliability import runs
from ac2fb.reliability.match import MatchData, load_match
from ac2fb.reliability.report import render_report

__all__ = [
    "KINK_THRESHOLD",
    "REPORT_NAME",
    "ROUNDING_BOUND",
    "cadence_of",
    "cadence_report",
    "kink_gaps",
    "match_cadence",
    "min_window",
    "write_cadence_report",
]

REPORT_NAME = "probe_cadence.json"
GRID = 0.01  # the provider's coordinate grid, metres
ROUNDING_BOUND = 4 * (GRID / 2) * float(np.sqrt(2))  # 0.0283 m per frame squared
KINK_THRESHOLD = 0.03
MAX_GAP = 30  # gaps up to this many frames get their own histogram bin
FRAME_SECONDS = 0.1


def _kinks(
    match: MatchData, threshold: float
) -> tuple[NDArray[np.int64], NDArray[np.bool_], NDArray[np.int64]]:
    """Row indices of the kinks, the detected centres, and the unbroken-stretch id of each row."""
    accel, centre = runs.second_differences(match)
    seen = np.zeros(len(match.frame), dtype=np.bool_)
    seen[1:-1] = match.detected[:-2] & match.detected[1:-1] & match.detected[2:]
    valid = centre & seen
    kinks = np.flatnonzero(valid & (accel > threshold))
    return kinks, valid, np.cumsum(~valid)  # ids equal when every row between is a centre


def kink_gaps(match: MatchData, threshold: float = KINK_THRESHOLD) -> NDArray[np.int64]:
    """Frames between successive kinks of the same detected player, over unbroken stretches."""
    kinks, _, unbroken = _kinks(match, threshold)
    same = unbroken[kinks[1:]] == unbroken[kinks[:-1]]
    return np.asarray(np.diff(match.frame[kinks])[same], dtype=np.int64)


def cadence_of(gaps: NDArray[np.int64]) -> int | None:
    """The most frequent gap, the smallest on a tie; ``None`` without gaps."""
    if len(gaps) == 0:
        return None
    return int(np.argmax(np.bincount(gaps)))


def _percentile(gaps: NDArray[np.int64], q: float) -> int | None:
    return int(np.quantile(gaps, q, method="higher")) if len(gaps) else None


def min_window(cadences: list[int | None], p90s: list[int | None]) -> int:
    """The shortest admissible window in frames: ``max(2 * c, G)`` of the module rule."""
    known_c = [c for c in cadences if c is not None]
    known_g = [g for g in p90s if g is not None]
    if not known_c or not known_g:
        raise ValueError("no match has a gap between kinks")
    return max(2 * max(known_c), max(known_g))


def match_cadence(match: MatchData, threshold: float = KINK_THRESHOLD) -> dict[str, object]:
    """The gaps between kinks of one match: histogram, cadence and percentiles.

    ``first_rise`` is the first gap above 1 whose share is larger than the share of the gap
    before it (``None`` when the shares only fall up to the last bin): a hidden cadence ``c``
    shows as a rise at ``c`` or before.
    """
    kinks, valid, _ = _kinks(match, threshold)
    gaps = kink_gaps(match, threshold)
    shown = np.bincount(np.minimum(gaps, MAX_GAP + 1), minlength=MAX_GAP + 2)[1:]
    share = shown / len(gaps) if len(gaps) else np.full(len(shown), np.nan)
    histogram = {f"gap_{i + 1:02d}": float(v) for i, v in enumerate(share[:MAX_GAP])}
    histogram[f"gap_gt_{MAX_GAP}"] = float(share[MAX_GAP])
    rises = [g + 1 for g in range(1, MAX_GAP) if share[g] > share[g - 1]]
    return {
        "cadence": cadence_of(gaps),
        "first_rise": rises[0] if rises else None,
        "gap_p50": _percentile(gaps, 0.5),
        "gap_p90": _percentile(gaps, 0.9),
        "gap_p99": _percentile(gaps, 0.99),
        "histogram": histogram,
        "kink_share": float(len(kinks) / valid.sum()) if valid.any() else None,
        "n_centres": int(valid.sum()),
        "n_gaps": int(len(gaps)),
        "n_kinks": int(len(kinks)),
    }


def cadence_report(matches: list[MatchData]) -> dict[str, object]:
    """Per-match cadence at the chosen threshold, two comparison thresholds, and the decision."""
    floor = runs.linear_rounding_floor()
    compared = {"none": 0.0, "rounding_p99": floor["p99"]}
    per_match: dict[str, object] = {}
    cadences: list[int | None] = []
    p90s: list[int | None] = []
    for match in matches:
        chosen = match_cadence(match)
        cadences.append(chosen["cadence"])  # type: ignore[arg-type]
        p90s.append(chosen["gap_p90"])  # type: ignore[arg-type]
        others: dict[str, object] = {}
        for name, value in compared.items():
            other = match_cadence(match, value)
            others[name] = {k: other[k] for k in ("cadence", "gap_p90", "n_gaps", "kink_share")}
        per_match[str(match.match_id)] = {**chosen, "other_thresholds": others}
    window = min_window(cadences, p90s)
    return {
        "about": (
            "Cadence probe: gaps between kinks (second difference above the threshold) of "
            "detected players. Descriptive only; no outcome of any question. The rule for "
            "w_min is in the docstring of ac2fb.reliability.cadence."
        ),
        "decision": {
            "cadence_frames": max(c for c in cadences if c is not None),
            "g_frames": max(g for g in p90s if g is not None),
            "rule": "w_min = max(2 * cadence, g); cadence = largest per-match mode of the gap; "
            "g = largest per-match p90 of the gap",
            "w_min_frames": window,
            "w_min_seconds": window * FRAME_SECONDS,
        },
        "matches": per_match,
        "threshold": {
            "chosen": KINK_THRESHOLD,
            "compared": compared,
            "rounding_bound": ROUNDING_BOUND,
            "simulated_floor": floor,
        },
    }


def write_cadence_report(match_ids: list[int], reports_dir: Path) -> Path:
    """Read each match through the guarded door, write ``probe_cadence.json`` (LF); return it."""
    report = cadence_report([load_match(m) for m in match_ids])
    return _write(report, reports_dir)


def _write(report: Mapping[str, object], reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path
