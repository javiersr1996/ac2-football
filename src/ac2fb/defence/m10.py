"""The plan's probe m10, re-derived in code, and the comparison with the tables it printed.

m10 (2026-10-17, the ten calibration matches only) measured what comes before a reception
``t``: the ball's distance to the carrier at ``t``, the line's displacement in ``[t - 10, t]``
and ``[t - 20, t]`` frames (1 s and 2 s) by pressure and by direction of the incoming ball, and
the line's visibility at ``t``. Its definitions are kept here, not S2's: windows of 10 and 20
frames instead of ``W``, the direction of the ball over 10 frames (forward over +2 m along the
attack, backward under -2 m, else lateral) with no third or length, and every
``player_possession`` event whatever its label. One thing differs and cannot be kept: m10 left
out the goalkeepers of the roster, this code the proxy of
:func:`ac2fb.reliability.visibility.goalkeepers` (the same player in the 40 period-team pairs
of the calibration matches, per the plan).

The population of the line figures is m10's: units whose line is listed at ``t``, ``t - 10``
and ``t - 20``, with the carrier and a rival at ``t`` and the ball at ``t`` and ``t - 10``.

:data:`M10_PER_MATCH` and :data:`M10_POOLED` hold what m10 printed, each value with the decimals
it was rounded to (``None``: an exact count). :func:`compare` says, figure by figure, whether
the code gives that number to those decimals. Nothing is adjusted when one does not reproduce:
the plan is corrected instead.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

from ac2fb.defence.line import LineReception, Unit
from ac2fb.reliability.inventory import leaf
from ac2fb.reliability.match import MatchData, locate_rows

__all__ = [
    "DIRECTION_CUT",
    "LAGS",
    "M10_POOLED",
    "M10_PER_MATCH",
    "ball_carrier",
    "compare",
    "direction",
    "m10_units",
    "match_figures",
    "pooled_figures",
]

LAGS = (10, 20)  # frames: m10's 1 s and 2 s
DIRECTION_CUT = 2.0  # metres of ball displacement along the attack over 10 frames
_DIRECTIONS = ("back", "fwd", "lat")

_Printed = tuple[float, int | None]  # the value m10 printed, and the decimals it rounded to

_MATCHES = (
    1874553,
    1886347,
    1925299,
    1959846,
    1996435,
    1996436,
    2007448,
    2010085,
    2011166,
    2015213,
)
# m10 table (a): n, median, p90, share <= 2 m, share <= 1 m
_BALL = (
    (956, 1.18, 2.16, 0.866, 0.381), (987, 1.26, 2.51, 0.831, 0.339),
    (1050, 1.23, 2.55, 0.827, 0.347), (945, 1.26, 2.4, 0.839, 0.333),
    (997, 1.21, 2.55, 0.822, 0.357), (785, 1.28, 2.62, 0.817, 0.321),
    (862, 1.25, 2.49, 0.818, 0.323), (935, 1.27, 2.44, 0.824, 0.317),
    (755, 1.33, 2.85, 0.764, 0.325), (881, 1.37, 2.79, 0.765, 0.286),
)  # fmt: skip
# m10 table (b): n, pre1 pressed, pre1 free, diff1, diff2, sd pre1, sd pre2, share pressed
_PRESSURE = (
    (925, -0.004, -0.005, 0.0, 0.034, 1.803, 3.482, 0.415),
    (964, 0.082, -0.168, 0.25, 0.624, 1.79, 3.457, 0.423),
    (1037, -0.042, -0.155, 0.113, 0.187, 1.676, 3.266, 0.385),
    (919, 0.261, -0.239, 0.5, 1.04, 1.855, 3.526, 0.457),
    (981, 0.121, -0.164, 0.285, 0.58, 1.905, 3.62, 0.435),
    (772, 0.331, 0.083, 0.247, 0.511, 1.798, 3.5, 0.521),
    (848, 0.081, -0.287, 0.368, 0.694, 1.795, 3.476, 0.433),
    (921, -0.063, -0.435, 0.372, 0.711, 1.673, 3.198, 0.395),
    (729, -0.039, -0.118, 0.079, 0.199, 1.961, 3.749, 0.587),
    (863, -0.076, -0.498, 0.423, 0.851, 1.894, 3.638, 0.458),
)  # fmt: skip
# m10 table (c): ball displacement pressed, free; share forward pressed, free
_CONFOUNDER = (
    (1.45, -0.53, 0.484, 0.335), (1.54, -0.61, 0.471, 0.327), (1.79, -1.32, 0.519, 0.304),
    (1.35, -0.87, 0.46, 0.315), (1.55, -0.77, 0.461, 0.341), (1.51, -0.69, 0.465, 0.308),
    (1.26, -1.52, 0.466, 0.26), (1.14, -1.51, 0.445, 0.284), (0.55, -0.94, 0.414, 0.316),
    (1.06, -1.56, 0.433, 0.265),
)  # fmt: skip
# m10 table (b'): per direction back, fwd, lat: n, diff1, pre1 of all, sd
_DIRECTION = (
    ((368, -0.341, -1.031, 1.303), (367, -0.266, 1.033, 1.869), (190, -0.335, -0.02, 1.304)),
    ((349, 0.421, -1.097, 1.298), (374, -0.437, 0.934, 1.924), (241, 0.054, -0.11, 1.247)),
    ((427, 0.054, -0.933, 1.354), (401, -0.648, 0.798, 1.76), (209, -0.14, -0.178, 1.139)),
    ((372, 0.181, -1.037, 1.275), (350, 0.136, 1.158, 1.983), (197, 0.38, -0.149, 1.252)),
    ((396, 0.355, -1.094, 1.379), (386, -0.433, 1.049, 2.007), (199, 0.069, -0.054, 1.348)),
    ((274, 0.041, -0.797, 1.342), (301, -0.189, 1.163, 1.91), (197, -0.106, 0.163, 1.346)),
    ((364, 0.249, -1.079, 1.322), (296, -0.366, 0.879, 1.921), (188, 0.146, 0.13, 1.393)),
    ((418, 0.162, -1.151, 1.218), (320, -0.116, 0.775, 1.793), (183, 0.088, -0.177, 1.182)),
    ((294, -0.066, -1.207, 1.352), (272, -0.479, 1.113, 2.098), (163, 0.112, 0.0, 1.387)),
    ((381, 0.352, -1.211, 1.465), (295, 0.115, 0.776, 2.028), (187, -0.465, -0.164, 1.48)),
)  # fmt: skip


def _per_match(i: int) -> dict[str, _Printed]:
    n, med, p90, le2, le1 = _BALL[i]
    m, pp, pf, d1, d2, s1, s2, share = _PRESSURE[i]
    bp, bf, fp, ff = _CONFOUNDER[i]
    out: dict[str, _Printed] = {
        "ball.n": (n, None),
        "ball.median": (med, 2),
        "ball.p90": (p90, 2),
        "ball.le2": (le2, 3),
        "ball.le1": (le1, 3),
        "units.n": (m, None),
        "pressure.pre1_pressed": (pp, 3),
        "pressure.pre1_free": (pf, 3),
        "pressure.diff1": (d1, 3),
        "pressure.diff2": (d2, 3),
        "pressure.sd_pre1": (s1, 3),
        "pressure.sd_pre2": (s2, 3),
        "pressure.share_pressed": (share, 3),
        "confounder.dball_pressed": (bp, 2),
        "confounder.dball_free": (bf, 2),
        "confounder.fwd_pressed": (fp, 3),
        "confounder.fwd_free": (ff, 3),
    }
    for name, (dn, diff, pre, sd) in zip(_DIRECTIONS, _DIRECTION[i], strict=True):
        out[f"direction.{name}.n"] = (dn, None)
        out[f"direction.{name}.diff1"] = (diff, 3)
        out[f"direction.{name}.pre1_all"] = (pre, 3)
        out[f"direction.{name}.sd"] = (sd, 3)
    return out


M10_PER_MATCH: dict[int, dict[str, _Printed]] = {m: _per_match(i) for i, m in enumerate(_MATCHES)}

# m10's pooled tables over the ten matches.
M10_POOLED: dict[str, _Printed] = {
    "possessions": (9178, None),
    "units": (8959, None),
    **{
        f"direction_pressure.{d}.{g}.{k}": (v, digits)
        for d, g, row in (
            ("back", "free", (2382, -1.114, -1.847, 1.252)),
            ("back", "pressed", (1261, -0.978, -1.455, 1.475)),
            ("fwd", "free", (1519, 1.112, 1.734, 1.867)),
            ("fwd", "pressed", (1843, 0.846, 1.356, 1.97)),
            ("lat", "free", (1064, -0.055, -0.235, 1.225)),
            ("lat", "pressed", (890, -0.063, -0.043, 1.405)),
        )
        for k, v, digits in zip(("n", "pre1", "pre2", "sd1"), row, (None, 3, 3, 3), strict=True)
    },
    **{
        f"label.{name}.{k}": (v, digits)
        for name, row in (
            ("medium_pressure", (2222, 0.69, 4.58)),
            ("no_pressure", (2181, 0.0, 11.62)),
            ("high_pressure", (1670, 1.35, 2.57)),
            ("low_pressure", (1668, 0.2, 6.85)),
            ("null", (872, 0.88, 4.18)),
            ("very_high_pressure", (346, 1.72, 1.32)),
        )
        for k, v, digits in zip(("n", "n5_mean", "dmin_median"), row, (None, 2, 2), strict=True)
    },
    **{
        f"visibility.{g}.{k}": (v, digits)
        for g, row in (("free", (4965, 1.78, 0.286)), ("pressed", (3994, 2.51, 0.439)))
        for k, v, digits in zip(("n", "ndet", "all4"), row, (None, 2, 3), strict=True)
    },
}


def direction(along: float) -> str:
    """m10's direction of the incoming ball from its displacement along the attack."""
    return "fwd" if along > DIRECTION_CUT else "back" if along < -DIRECTION_CUT else "lat"


def ball_carrier(match: MatchData, receptions: Sequence[LineReception]) -> dict[str, object]:
    """Distance from the ball to the carrier at ``t``, where both have a row (m10's table a)."""
    found: list[float] = []
    for r in receptions:
        carrier = int(locate_rows(match, np.array([r.player]), np.array([r.frame]))[0])
        pos = int(np.searchsorted(match.ball_frame, r.frame))
        if carrier < 0 or pos >= len(match.ball_frame) or match.ball_frame[pos] != r.frame:
            continue
        found.append(
            float(
                np.hypot(match.ball_x[pos] - match.x[carrier], match.ball_y[pos] - match.y[carrier])
            )
        )
    d = np.asarray(found)
    return {
        "n": len(d),
        "median": float(np.median(d)) if len(d) else None,
        "p90": float(np.quantile(d, 0.9)) if len(d) else None,
        "le2": float(np.mean(d <= 2)) if len(d) else None,
        "le1": float(np.mean(d <= 1)) if len(d) else None,
    }


def m10_units(units: Sequence[Unit]) -> list[Unit]:
    """m10's population: the line listed at ``t - 10`` and ``t - 20``, the ball at ``t - 10``."""
    return [
        u
        for u in units
        if all(math.isfinite(u.depth[lag]) for lag in LAGS) and math.isfinite(u.ball_along[10])
    ]


def _pre(u: Unit, lag: int) -> float:
    return u.depth[0] - u.depth[lag]


def _mean(values: Sequence[float]) -> float | None:
    return float(np.mean(values)) if len(values) else None


def _sd(values: Sequence[float]) -> float | None:
    return float(np.std(values, ddof=1)) if len(values) > 1 else None


def _gap(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def match_figures(units: Sequence[Unit]) -> dict[str, object]:
    """m10's per-match tables (b), (c) and (b') over its population of ``units``."""
    us = m10_units(units)
    pressed = [u for u in us if u.pressed]
    free = [u for u in us if not u.pressed]

    def pre(group: Sequence[Unit], lag: int) -> float | None:
        return _mean([_pre(u, lag) for u in group])

    out: dict[str, object] = {
        "units": {"n": len(us)},
        "pressure": {
            "pre1_pressed": pre(pressed, 10),
            "pre1_free": pre(free, 10),
            "diff1": _gap(pre(pressed, 10), pre(free, 10)),
            "diff2": _gap(pre(pressed, 20), pre(free, 20)),
            "sd_pre1": _sd([_pre(u, 10) for u in us]),
            "sd_pre2": _sd([_pre(u, 20) for u in us]),
            "share_pressed": len(pressed) / len(us) if us else None,
        },
        "confounder": {
            "dball_pressed": _mean([u.ball_along[10] for u in pressed]),
            "dball_free": _mean([u.ball_along[10] for u in free]),
            "fwd_pressed": _mean([direction(u.ball_along[10]) == "fwd" for u in pressed]),
            "fwd_free": _mean([direction(u.ball_along[10]) == "fwd" for u in free]),
        },
    }
    by_dir: dict[str, object] = {}
    for name in _DIRECTIONS:
        cell = [u for u in us if direction(u.ball_along[10]) == name]
        by_dir[name] = {
            "n": len(cell),
            "diff1": _gap(
                pre([u for u in cell if u.pressed], 10), pre([u for u in cell if not u.pressed], 10)
            ),
            "pre1_all": pre(cell, 10),
            "sd": _sd([_pre(u, 10) for u in cell]),
        }
    out["direction"] = by_dir
    return out


def pooled_figures(units: Sequence[Unit], possessions: int) -> dict[str, object]:
    """m10's pooled tables over the units of every match given, and the possession count."""
    us = m10_units(units)
    out: dict[str, object] = {"possessions": possessions, "units": len(us)}
    table: dict[str, object] = {}
    for name in _DIRECTIONS:
        row: dict[str, object] = {}
        for group, flag in (("pressed", True), ("free", False)):
            cell = [u for u in us if direction(u.ball_along[10]) == name and u.pressed is flag]
            row[group] = {
                "n": len(cell),
                "pre1": _mean([_pre(u, 10) for u in cell]),
                "pre2": _mean([_pre(u, 20) for u in cell]),
                "sd1": _sd([_pre(u, 10) for u in cell]),
            }
        table[name] = row
    out["direction_pressure"] = table
    labels: dict[str, object] = {}
    for name in sorted({u.reception.label or "null" for u in us}):
        cell = [u for u in us if (u.reception.label or "null") == name]
        labels[name] = {
            "n": len(cell),
            "n5_mean": _mean([u.near for u in cell]),
            "dmin_median": float(np.median([u.nearest for u in cell])),
        }
    out["label"] = labels
    out["visibility"] = {
        group: {
            "n": len(cell),
            "ndet": _mean([u.detected_at_t for u in cell]),
            "all4": _mean([u.detected_at_t == len(u.line) for u in cell]),
        }
        for group, cell in (
            ("pressed", [u for u in us if u.pressed]),
            ("free", [u for u in us if not u.pressed]),
        )
    }
    return out


def _same(value: float | None, printed: _Printed) -> bool:
    want, digits = printed
    if value is None:
        return False
    if digits is None:
        return value == want
    return abs(value - want) <= 0.5 * 10.0**-digits + 1e-9


def _check(
    figures: Mapping[str, object], printed: Mapping[str, _Printed]
) -> dict[str, dict[str, object]]:
    return {
        key: {
            "m10": want[0],
            "decimals": want[1],
            "code": leaf(figures, key),
            "same": _same(leaf(figures, key), want),
        }
        for key, want in printed.items()
    }


def compare(
    per_match: Mapping[int, Mapping[str, object]], pooled: Mapping[str, object] | None
) -> dict[str, object]:
    """Each printed m10 figure against the code's: ``same`` when equal to the printed decimals.

    ``per_match`` maps a match id to its m10 figures (``ball`` merged with :func:`match_figures`);
    ``pooled`` is :func:`pooled_figures` over the ten matches, or ``None`` when not all ten
    were given (the pooled tables are then not compared).
    """
    matches = {
        str(m): _check(per_match[m], printed)
        for m, printed in M10_PER_MATCH.items()
        if m in per_match
    }
    pooled_check = None if pooled is None else _check(pooled, M10_POOLED)
    flat = {f"{m}.{k}": bool(c["same"]) for m, table in matches.items() for k, c in table.items()}
    if pooled_check is not None:
        flat |= {f"pooled.{k}": bool(c["same"]) for k, c in pooled_check.items()}
    every = list(flat.values())
    differ = sorted(k for k, same in flat.items() if not same)
    return {
        "source": "probe m10 of the plan (tasks/todo.md, inventory of 2026-10-17), printed tables",
        "matches": matches,
        "pooled": pooled_check,
        "figures": len(every),
        "same": sum(every),
        "differ": differ,
    }
