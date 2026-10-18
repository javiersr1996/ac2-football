"""The figures of the plan's inventory (``tasks/todo.md``, 2026-10-17), and the comparison.

Two kinds of figure, compared differently:

- ``RANGES``: min, median and max over the **20** matches (probes m3 to m6 and m9). The
  calibration set is ten of those twenty, so its per-match values are expected to lie inside
  the range; the medians are of a different set of matches and are listed, never compared.
- ``M11_*``: the 10 calibration matches only (probe m11), so they are compared one to one,
  to the third decimal, and the pooled counts exactly.

``compare`` returns a verdict per figure. Nothing is adjusted when a figure does not
reproduce: the verdict says so and the plan is corrected instead.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = ["M11_PER_MATCH", "M11_POOLED", "RANGES", "Planned", "compare", "leaf"]

_PLAN = "tasks/todo.md"


@dataclass(frozen=True)
class Planned:
    """A figure of the plan: where it is in the per-match report, and its 20-match range."""

    key: str
    low: float
    median: float | None
    high: float
    plan_line: int


# Shares as fractions (the plan writes percentages). Lines are those of tasks/todo.md at 4e2f1a4.
RANGES: tuple[Planned, ...] = (
    Planned("engager.at_start", 0.925, None, 0.968, 79),
    Planned("engager.window_whole", 0.767, 0.862, 0.911, 80),
    Planned("reception.carrier_detected", 0.936, 0.968, 0.982, 81),
    Planned("reception.rivals_within.5.detected", 0.931, 0.970, 0.986, 82),
    Planned("reception.rivals_within.20.detected", 0.877, None, 0.962, 82),
    Planned("reception.rivals_beyond_20.detected", 0.330, 0.469, 0.621, 83),
    Planned("reception.no_rival_within_5", 0.423, None, 0.684, 83),
    Planned("reception.with_extrapolated_rival_within_5", 0.018, 0.036, 0.085, 84),
    Planned("line.detected", 0.374, 0.517, 0.697, 86),
    Planned("line.all_detected", 0.196, 0.343, 0.561, 86),
    Planned("line.deepest_detected", 0.286, 0.433, 0.601, 87),
    Planned("block.detected", 0.511, 0.582, 0.692, 88),
    Planned("block.all_detected", 0.005, 0.028, 0.059, 89),
    Planned("ball_distance.00_05.detected", 0.825, 0.863, 0.914, 91),
    Planned("ball_distance.05_10.detected", 0.789, 0.838, 0.893, 91),
    Planned("ball_distance.10_20.detected", 0.709, 0.774, 0.841, 91),
    Planned("ball_distance.20_30.detected", 0.439, 0.577, 0.708, 92),
    Planned("ball_distance.30_40.detected", 0.260, 0.364, 0.518, 92),
    Planned("ball_distance.40_plus.detected", 0.116, 0.161, 0.269, 92),
    Planned("steps.detected_to_detected.p50", 0.184, 0.200, 0.218, 96),
    Planned("steps.extrapolated_to_extrapolated.p50", 0.112, 0.129, 0.140, 97),
    Planned("steps.extrapolated_to_detected.p50", 0.136, 0.171, 0.200, 97),
)

# probe m11, per calibration match (its printed tables). Order of the lists is MATCH order.
MATCH = (1874553, 1886347, 1925299, 1959846, 1996435, 1996436, 2007448, 2010085, 2011166, 2015213)
_DD_MED = (0.211, 0.214, 0.192, 0.197, 0.2, 0.184, 0.2, 0.197, 0.194, 0.214)
_DD_P90 = (0.447, 0.461, 0.424, 0.453, 0.446, 0.437, 0.45, 0.436, 0.471, 0.474)
_J_SHORT = (0.216, 0.221, 0.165, 0.184, 0.237, 0.211, 0.191, 0.215, 0.233, 0.246)
_J_LONG = (0.212, 0.231, 0.201, 0.211, 0.204, 0.174, 0.202, 0.202, 0.19, 0.206)
_J_LONG_P90 = (0.459, 0.481, 0.407, 0.466, 0.427, 0.375, 0.411, 0.412, 0.437, 0.476)
_N_LONG = (400, 368, 416, 395, 318, 412, 413, 408, 389, 539)
_SHARES = (
    (0.004, 0.175, 0.447, 0.374),
    (0.004, 0.175, 0.419, 0.403),
    (0.004, 0.167, 0.437, 0.392),
    (0.004, 0.173, 0.464, 0.360),
    (0.003, 0.195, 0.406, 0.396),
    (0.004, 0.180, 0.419, 0.397),
    (0.003, 0.165, 0.452, 0.380),
    (0.006, 0.177, 0.468, 0.349),
    (0.005, 0.169, 0.443, 0.383),
    (0.005, 0.158, 0.443, 0.394),
)
_BANDS = ("le_1s", "1_5s", "5_20s", "gt_20s")

# Paths into the per-match report of the plan-definition runs (``reacquisition``).
M11_PER_MATCH: dict[int, dict[str, float]] = {}
for _i, _m in enumerate(MATCH):
    M11_PER_MATCH[_m] = {
        "steps.detected_to_detected.p50": _DD_MED[_i],
        "steps.detected_to_detected.p90": _DD_P90[_i],
        "reacquisition.by_band.le_1s.jump_median": _J_SHORT[_i],
        "reacquisition.by_band.gt_20s.jump_median": _J_LONG[_i],
        "reacquisition.by_band.gt_20s.jump_p90": _J_LONG_P90[_i],
        "reacquisition.by_band.gt_20s.n_with_jump": float(_N_LONG[_i]),
        **{
            f"reacquisition.by_band.{_b}.frame_share": _SHARES[_i][_k]
            for _k, _b in enumerate(_BANDS)
        },
    }

# probe m11, pooled over the ten calibration matches, per gap band: n, median, p90, p99 of the
# jump and median step inside the gap.
M11_POOLED: dict[str, tuple[int, float, float, float, float]] = {
    "le_1s": (2601, 0.212, 0.446, 0.700, 0.205),
    "1_5s": (23091, 0.156, 0.418, 0.689, 0.146),
    "5_20s": (18844, 0.175, 0.412, 0.659, 0.167),
    "gt_20s": (4058, 0.202, 0.438, 0.664, 0.137),
}


def leaf(tree: Mapping[str, object], path: str) -> float | None:
    """The number at a dotted path of nested dicts, or ``None`` if missing or null."""
    node: object = tree
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return float(node) if isinstance(node, int | float) else None


def _same(value: float | None, planned: float) -> bool:
    return value is not None and math.isclose(round(value, 3), planned, abs_tol=1e-9)


def compare(
    per_match: Mapping[int, Mapping[str, object]],
    pooled_bands: Mapping[str, Sequence[float]],
) -> dict[str, object]:
    """Compare the calibration figures with the plan's inventory; nothing is adjusted.

    ``per_match`` maps a match id to its report; ``pooled_bands`` holds, per gap band of the
    plan-definition runs, the pooled ``(n, jump median, p90, p99, inside-step median)``.
    """
    ranges: dict[str, object] = {}
    for item in RANGES:
        values = {m: leaf(r, item.key) for m, r in per_match.items()}
        known = [v for v in values.values() if v is not None]
        # The plan rounds twice (probe output to four decimals, then the text to one): 0.001 slack.
        slack = 0.001
        inside = bool(known) and all(item.low - slack <= v <= item.high + slack for v in known)
        ranges[item.key] = {
            "plan_line": item.plan_line,
            "plan_low": item.low,
            "plan_high": item.high,
            "plan_median_of_20": item.median,
            "calibration_low": min(known) if known else None,
            "calibration_median": sorted(known)[len(known) // 2] if known else None,
            "calibration_high": max(known) if known else None,
            "inside_plan_range": inside,
        }
    one_to_one: dict[str, object] = {}
    for match_id, planned in M11_PER_MATCH.items():
        report = per_match.get(match_id)
        if report is None:
            continue
        one_to_one[str(match_id)] = {
            key: {
                "plan": want,
                "measured": leaf(report, key),
                "same": _same(leaf(report, key), want),
            }
            if "n_with_jump" not in key
            else {
                "plan": want,
                "measured": leaf(report, key),
                "same": leaf(report, key) == want,
            }
            for key, want in planned.items()
        }
    pooled: dict[str, object] = {}
    for band, (n, med, p90, p99, inner) in M11_POOLED.items():
        got = pooled_bands.get(band)
        pooled[band] = {
            "plan": {
                "n": n,
                "jump_median": med,
                "jump_p90": p90,
                "jump_p99": p99,
                "inside": inner,
            },
            "measured": None if got is None else list(got),
            "same": got is not None
            and got[0] == n
            and all(_same(g, w) for g, w in zip(got[1:], (med, p90, p99, inner), strict=True)),
        }
    every = [c["same"] for m in one_to_one.values() for c in m.values()]  # type: ignore[attr-defined]
    return {
        "source": f"{_PLAN} (inventory of 2026-10-17); probe m11 tables for the one-to-one part",
        "ranges_of_20_matches": ranges,
        "ranges_all_inside": all(r["inside_plan_range"] for r in ranges.values()),  # type: ignore[index]
        "m11_per_match": one_to_one,
        "m11_pooled": pooled,
        "m11_all_same": all(every) and all(p["same"] for p in pooled.values()),  # type: ignore[index]
    }
