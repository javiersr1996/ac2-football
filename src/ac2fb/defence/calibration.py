"""The calibration half under the protocol: effects, null, bars and the verdict D1 to D5.

The ``reading_order`` of ``protocol/protocol.json``, in code. The first module that computes an
outcome on a real match, through the one reader of it
(:func:`ac2fb.defence.effect.read_outcome`), with the estimator validated on synthetic worlds
first (``tests/test_effect.py``). Its report, ``reports/calibration.json``, says whether the
protocol may be frozen for the one reading of the held-out (``ac2fb heldout read``) or the
question dies here (D5, branch B). Nothing in it moves a threshold: every number it judges with
is a constant that ``ac2fb protocol --check`` ties to the protocol.

**Order** (protocol ``reading_order``). (1) The design of each match, before any outcome: the
units of :func:`ac2fb.defence.design.design_units`; D1's contrast, the median index by label
level (:func:`ac2fb.defence.pressure.level_contrast` on every scored reception: probe S1's rule
and code, so the calibration's D1 is probe S1's verdict, recomputed); the correlation of ``x``,
the blocking decision and the MDE80 of V0 and V1 (:func:`ac2fb.defence.power.candidate_power` on
the kept units under the index cut, with the random stream of ``reports/design.json``, so the
MDE80 is that report's, re-printed). (2) The outcomes of the kept units
(:func:`ac2fb.defence.effect.effect_units`), with the undefined ones and those with the ball
extrapolated at ``t`` or ``t + W`` counted per match and group. (3) V0 and V1: the effect, the
permutation null of the half (blocked if the rule says so) and the calibration bar; beside
them, deciding nothing, V0 on the units with the ball detected at both ends and the V2 classes.
(4) The criteria: :func:`d1`, :func:`d2`, :func:`ac2fb.defence.effect.d3`,
:func:`ac2fb.defence.effect.d4` and :func:`d5`, which passes the half only when V0 passes the
bar and none of D1 to D4 kills.

**The variance factor** (reported beside the null, which stays the protocol's, decided before
any outcome). Permuting ``G`` inside a cell with ``x`` fixed ignores the correlation ``r`` of
``G`` and ``x`` there: the variance of the adjusted coefficient is larger by ``1 / (1 - r^2)``.
From a cell's reported figures, ``r^2 = P_c^2 w_c / (n_c - 1)`` (``Sgx = w_c x_diff``,
``Sxx = (n_c - 1) sd_x^2``, ``Sgg = w_c``); a cell with ``x`` constant has no covariate and a
factor of 1. :func:`variance_factor` gives its ``w``-weighted mean, median and maximum over the
cells of a variant: a diagnostic that decides nothing.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from ac2fb.defence import bar, design, effect, power, pressure, probe_s1
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.reliability.report import JsonCheck, check_json, render_report

__all__ = [
    "HALF",
    "NOT_TESTABLE_IN_SEEN",
    "REPORT_NAME",
    "calibration_report",
    "check",
    "d1",
    "d2",
    "d5",
    "variance_factor",
    "write_calibration_report",
]

REPORT_NAME = "calibration.json"
HALF = "calibration"  # the half of the null's random stream
NOT_TESTABLE_IN_SEEN = "not testable in what was seen"  # protocol D2: V1 over the MDE80 limit


def variance_factor(result: effect.Effect) -> dict[str, float | int | None]:
    """``1 / (1 - r^2)`` of ``G`` and ``x`` per cell: its ``w``-weighted mean, median and max."""
    factors = [
        1.0
        if c.pretrend is None
        else 1.0 / (1.0 - c.pretrend**2 * c.w / (c.n_pressed + c.n_free - 1))
        for c in result.cells
    ]
    if not factors:
        return {"cells": 0, "weighted_mean": None, "median": None, "max": None}
    f, w = np.array(factors), np.array([c.w for c in result.cells])
    return {
        "cells": len(factors),
        "weighted_mean": float(f @ w / w.sum()),
        "median": float(np.median(f)),
        "max": float(f.max()),
    }


def d1(increasing: Mapping[int, bool]) -> effect.Criterion:
    """D1 kills unless the index grows with the label in enough matches of a whole half."""
    survives = probe_s1.verdict(increasing)["c1_survives_probe"]
    return effect.Criterion(
        "D1",
        survives is not True,
        survives is not None,
        {"matches_increasing": sum(increasing.values()), "min_matches": probe_s1.MIN_MATCHES},
    )


def d2(mde80_v0: float | None) -> effect.Criterion:
    """D2 kills when V0's MDE80 exceeds the limit or no effect of the grid reaches the power."""
    return effect.Criterion(
        "D2",
        mde80_v0 is None or mde80_v0 > power.MDE_LIMIT,
        True,
        {"mde80_sd": mde80_v0, "limit_sd": power.MDE_LIMIT},
    )


def d5(v0_bar: effect.Bar, criteria: Sequence[effect.Criterion]) -> dict[str, object]:
    """D5 kills unless V0 passes the calibration bar and none of ``criteria`` (D1 to D4) kills."""
    killing = [c.name for c in criteria if c.kills]
    return {
        "name": "D5",
        "kills": not v0_bar.passed or bool(killing),
        "v0_bar_passed": v0_bar.passed,
        "killing": killing,
    }


def _effect(e: effect.Effect) -> dict[str, object]:
    return {
        "t": e.t,
        "weight": e.weight,
        "pretrend_sd": e.pretrend,
        "pretrend_m": e.pretrend_m,
        "agreeing": effect.sign_agreement(e),
        "units": e.units,
        "used": e.used,
        "left_out": e.left_out,
        "cells": [dataclasses.asdict(c) for c in e.cells],
        "matches": {str(m): dataclasses.asdict(x) for m, x in e.matches.items()},
    }


def _outcomes(units: Sequence[effect.EffectUnit]) -> dict[str, object]:
    """Kept units, undefined outcomes and the ball extrapolated at an end, by group."""
    out: dict[str, object] = {}
    for group, pressed in (("pressed", True), ("free", False)):
        mine = [u for u in units if u.pressed == pressed]
        defined = [u for u in mine if u.outcome is not None]
        extrapolated = sum(not u.ball_detected for u in defined)
        out[group] = {
            "kept": len(mine),
            "undefined": len(mine) - len(defined),
            "ball_extrapolated": extrapolated,
            "ball_extrapolated_share": extrapolated / len(defined) if defined else None,
        }
    return out


def calibration_report(match_ids: Sequence[int]) -> dict[str, object]:
    """Read each match through the guarded door and judge the half (the module docstring)."""
    loaded = {m: power.load_c1(m) for m in match_ids}
    # (1) The design, before any outcome.
    units = {m: design.design_units(i) for m, i in loaded.items()}
    contrast = {
        m: pressure.level_contrast(
            pressure.score_receptions(i.s1.match, i.s1.receptions), probe_s1.MIN_PER_LEVEL
        )
        for m, i in loaded.items()
    }
    simulated = power.candidate_power(
        {m: design.power_units(us, "index") for m, us in units.items()},
        design.POWER_LABEL,
        with_pretrend=False,
    )
    blocked = bool(simulated["blocked"])
    variants: dict[str, dict[str, object]] = simulated["variants"]  # type: ignore[assignment]
    mde80: dict[str, float | None] = {v: variants[v]["mde80_sd"] for v in effect.VARIANTS}  # type: ignore[misc]
    # (2) The outcomes of the kept units.
    kept = {m: effect.effect_units(units[m], i.s1.match) for m, i in loaded.items()}
    every = [u for us in kept.values() for u in us]
    # (3) The effects, the nulls and the bars.
    results = {v: effect.permutation_test(every, HALF, v, blocked) for v in effect.VARIANTS}
    bars = {v: effect.calibration_bar(r) for v, r in results.items()}
    v2 = effect.v2_effects(every)
    # (4) The criteria and the verdict.
    criteria = (
        d1({m: bool(c["increasing"]) for m, c in contrast.items()}),
        d2(mde80["V0"]),
        effect.d3(results["V0"].effect),
        effect.d4(results["V0"].effect, results["V1"].effect),
    )
    verdict = d5(bars["V0"], criteria)
    testable_in_seen = mde80["V1"] is not None and mde80["V1"] <= power.MDE_LIMIT
    named = {c.name: dataclasses.asdict(c) for c in criteria}
    named["D2"]["v1"] = {
        "mde80_sd": mde80["V1"],
        "label": None if testable_in_seen else NOT_TESTABLE_IN_SEEN,
    }
    return {
        "about": (
            "Task 21: the calibration half judged by the protocol, in its reading order. The "
            "design before any outcome (D1's contrast, the blocking decision, the MDE80 of "
            "reports/design.json re-printed); the outcomes; per variant the effect T, E_m per "
            "match and every cell, the pre-trend P in sd and metres, the permutation p and the "
            "calibration bar, with the variance factor 1 / (1 - r^2) of G and x as a diagnostic; "
            "V0 with the ball detected at both ends and the V2 classes beside them, deciding "
            "nothing; D1 to D5, mechanical. No threshold is moved. Definitions in "
            "ac2fb.defence.calibration, ac2fb.defence.effect and protocol/protocol.json."
        ),
        "constants": {
            "bar_p": bar.BAR_P,
            "bar_same_sign": bar.BAR_SAME_SIGN,
            "block_rho": bar.BLOCK_RHO,
            "d1_min_matches": probe_s1.MIN_MATCHES,
            "d1_min_per_level": probe_s1.MIN_PER_LEVEL,
            "d3_ratio": power.D3_RATIO,
            "d4_ratio": effect.D4_RATIO,
            "half": HALF,
            "mde_limit_sd": power.MDE_LIMIT,
            "min_cell": bar.MIN_CELL,
            "n_permutations": bar.N_PERMUTATIONS,
            "pressed_index": pressure.PRESSED_INDEX,
            "seed": effect.SEED,
            "window_frames": W,
        },
        "matches": [int(m) for m in match_ids],
        "design": {
            "units": {
                str(m): {
                    "design": len(us),
                    "excluded_gap": sum(u.excluded for u in us),
                    "kept": sum(not u.excluded for u in us),
                    "kept_pressed": sum(u.pressed and not u.excluded for u in us),
                    "kept_v1": sum(u.extrapolated_players == 0 and not u.excluded for u in us),
                }
                for m, us in units.items()
            },
            "d1_contrast": {str(m): c for m, c in contrast.items()},
            "null": {"rho_v0_pooled": simulated["rho_v0_pooled"], "blocked": blocked},
            "mde80_sd": mde80,
        },
        "outcomes": {str(m): _outcomes(us) for m, us in kept.items()},
        "variants": {
            v: {
                **_effect(r.effect),
                "null": {"blocked": r.blocked, "draws": r.draws, "extreme": r.extreme, "p": r.p},
                "bar": dataclasses.asdict(bars[v]),
                "variance_factor": variance_factor(r.effect),
            }
            for v, r in results.items()
        },
        "beside": {
            effect.BALL_DETECTED: _effect(
                effect.estimate(effect.select_units(every, effect.BALL_DETECTED))
            ),
            "V2": {
                "classes": {c: _effect(e) for c, e in v2.classes.items()},
                "abs_effect": v2.abs_effect,
                "shrinks": v2.shrinks,
            },
        },
        "criteria": {**named, "D5": verdict},
        "verdict": {
            "calibration_passes": not verdict["kills"],
            "next": (
                "the held-out stays shut: the negative is published per match (D5, branch B)"
                if verdict["kills"]
                else "the protocol may be frozen for the one reading of the held-out (task 23)"
            ),
        },
    }


def write_calibration_report(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Build the report and write ``reports_dir/calibration.json`` (LF); return its path."""
    report = calibration_report(match_ids)
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path


def check(match_ids: Sequence[int], raw: bytes | None) -> JsonCheck:
    """Recompute ``calibration.json`` of the matches and compare every value with ``raw``."""
    return check_json(REPORT_NAME, lambda: render_report(calibration_report(match_ids)), raw)
