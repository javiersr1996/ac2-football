"""Probe S3 (candidate C3): does our block geometry reproduce the provider's, and who sets it?

The probe measures the width and length of the team out of possession at the start of each
``phases_of_play`` phase, looks for the definition of :mod:`ac2fb.defence.block` that the
provider uses, and measures how much of the winner the camera saw. It computes no outcome of
any candidate: nothing here is read after the frame ``frame_start`` of a phase. Everything below
was written before the data was read.

**What is compared.** Per calibration match and per definition (the eight of
:data:`~ac2fb.defence.block.DEFINITIONS`), our width and length at ``frame_start`` against the
provider's ``team_out_of_possession_width_start`` and ``..._length_start``, over the phases that
have both. The team out of possession is the one that is not ``team_in_possession_id``.

**A definition reproduces the provider in a match** when, for width and for length, there are at
least :data:`MIN_PAIRS` phases with both numbers, the Pearson correlation is at least
:data:`MIN_R` and the median absolute difference is at most :data:`MAX_MEDIAN_DIFF` metres.

**Choosing the definition** (the rule, written before the data). Over the matches given: the
definition that reproduces in the most matches; ties go to the one with the lowest mean, over
the matches, of the median absolute difference of width plus that of length (a match where it
could not be computed counts as infinite); a remaining tie goes to the earlier one in
:data:`~ac2fb.defence.block.DEFINITIONS`.

**The rule that kills C3 in the probe.** *C3 dies if the chosen definition reproduces the
provider's metric in fewer than* :data:`MIN_REPRODUCED` *of the* :data:`CALIBRATION_MATCHES`
*calibration matches.* The thresholds are not moved after the data is read. If C3 survives, the
numbers below say how much of the block the camera saw; they decide nothing.

**What is reported for the chosen definition, per match.**

- *Extrapolated share of the players that fix each end* (``fixers``): through
  :func:`ac2fb.reliability.sensitivity.sensitivity`, one metric per end (``x_low``, ``x_high``,
  ``y_low``, ``y_high``) plus width and length (both of their ends), on one-frame windows at
  ``frame_start``. Its V1 is the phases whose fixers are all detected; V2 splits them by how many.
- *Visibility bias* (``visibility_bias``): the Spearman rank correlation, per match, between
  the fraction of the block's players that are detected at ``frame_start`` and our width and
  length (and the provider's), and between the fraction of the *fixers* that are detected and
  our own extent. A block that looks wider when more of it is seen is a bias of the camera, not
  of the team.
- *Block detected* (``block_detected``): the mean fraction of the block's players detected.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

from ac2fb.defence.block import (
    DEFINITIONS,
    ENDS,
    Block,
    Definition,
    measure,
    name_of,
    spearman,
)
from ac2fb.protocol import data
from ac2fb.reliability.long import long_table
from ac2fb.reliability.match import MatchData, build_match, players_at
from ac2fb.reliability.report import render_report
from ac2fb.reliability.sensitivity import Metric, Reading, Window, WindowFrames, sensitivity
from ac2fb.reliability.visibility import goalkeepers

__all__ = [
    "CALIBRATION_MATCHES",
    "MAX_MEDIAN_DIFF",
    "METRICS",
    "MIN_PAIRS",
    "MIN_R",
    "MIN_REPRODUCED",
    "REPORT_NAME",
    "MatchInputs",
    "Observed",
    "Phase",
    "definition_stats",
    "load_inputs",
    "make_metric",
    "match_figures",
    "observe",
    "phases_from",
    "s3_report",
    "select_definition",
    "verdict",
    "write_s3_report",
]

REPORT_NAME = "probe_s3.json"
CALIBRATION_MATCHES = 10
MIN_PAIRS = 100  # phases with our number and the provider's, for width and for length
MIN_R = 0.95  # Pearson correlation with the provider's number
MAX_MEDIAN_DIFF = 1.0  # metres: median absolute difference with the provider's number
MIN_REPRODUCED = 9  # matches in which the chosen definition must reproduce the provider's

# The layer 2 metrics of the winner: name -> the ends whose fixers back it. The value is the
# width when the ends are on y and the length when they are on x.
METRICS: dict[str, tuple[str, ...]] = {
    "width": ("y_low", "y_high"),
    "length": ("x_low", "x_high"),
    "x_low": ("x_low",),
    "x_high": ("x_high",),
    "y_low": ("y_low",),
    "y_high": ("y_high",),
}

_FRAME_COLUMNS = [
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
]
_EVENT_COLUMNS = [
    "native_family",
    "native_subtype",
    "frame_start",
    "frame_end",
    "period",
    "team_id",
    "player_id",
]
_PHASE_COLUMNS = [
    "index",
    "period",
    "frame_start",
    "team_in_possession_id",
    "team_out_of_possession_width_start",
    "team_out_of_possession_length_start",
]


@dataclass(frozen=True)
class Phase:
    """A ``phases_of_play`` phase: the team in possession and the provider's block numbers."""

    index: int
    period: int
    frame: int
    team_in: int
    width: float | None
    length: float | None


@dataclass(frozen=True)
class MatchInputs:
    """One match ready for the probe: its arrays, its phases and its long table."""

    match: MatchData
    phases: tuple[Phase, ...]
    long: pa.Table


@dataclass(frozen=True)
class Observed:
    """The out-of-possession team at the start of a phase."""

    phase: Phase
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    detected: NDArray[np.bool_]
    ids: NDArray[np.int64]
    keeper: int | None


def phases_from(bronze: pa.Table) -> list[Phase]:
    """The phases of bronze ``phases_of_play``; a row without period, frame or team is skipped."""
    found: list[Phase] = []
    for row in bronze.to_pylist():
        if row["period"] is None or row["frame_start"] is None:
            continue
        if row["team_in_possession_id"] is None:
            continue
        width = row["team_out_of_possession_width_start"]
        length = row["team_out_of_possession_length_start"]
        found.append(
            Phase(
                index=int(row["index"]),
                period=int(row["period"]),
                frame=int(row["frame_start"]),
                team_in=int(row["team_in_possession_id"]),
                width=None if width is None else float(width),
                length=None if length is None else float(length),
            )
        )
    return found


def load_inputs(match_id: int) -> MatchInputs:
    """Read one match through the guarded door (bronze included) and prepare it.

    Raises :class:`~ac2fb.protocol.data.HeldOutLocked` for a held-out match while locked.
    """
    ids = [match_id]
    frames = data.read_frames(ids, columns=_FRAME_COLUMNS)
    events = data.read_events(ids, columns=_EVENT_COLUMNS)
    phases = data.read_bronze_phases(ids, columns=_PHASE_COLUMNS)
    team_periods = data.read_dim("dim_team_period", ids)
    return MatchInputs(
        match=build_match(match_id, frames, events, team_periods),
        phases=tuple(phases_from(phases)),
        long=long_table(frames),
    )


# --- the block at the start of each phase ------------------------------------------------------


def observe(match: MatchData, phases: Sequence[Phase]) -> list[Observed]:
    """The out-of-possession team at ``frame_start`` of each phase that has players listed there."""
    keepers = goalkeepers(match)
    seen: list[Observed] = []
    for phase in phases:
        rows = players_at(match, phase.frame)
        out = rows[match.team[rows] != phase.team_in]
        if len(out) == 0:
            continue
        seen.append(
            Observed(
                phase=phase,
                x=match.x[out],
                y=match.y[out],
                detected=match.detected[out],
                ids=match.player[out],
                keeper=keepers.get((phase.period, int(match.team[out[0]]))),
            )
        )
    return seen


def _block(s: Observed, definition: Definition) -> Block | None:
    return measure(s.x, s.y, s.detected, s.ids, s.keeper, definition)


def _agreement(ours: Sequence[float], theirs: Sequence[float]) -> dict[str, object]:
    """Pearson r, median (absolute) difference of ours minus theirs, and whether it passes."""
    n = len(ours)
    if n == 0:
        return {
            "n": 0,
            "pearson_r": None,
            "median_abs_diff": None,
            "median_diff": None,
            "pass": False,
        }
    a, b = np.asarray(ours, dtype=np.float64), np.asarray(theirs, dtype=np.float64)
    r: float | None = None
    if n > 1 and a.std() > 0 and b.std() > 0:
        r = float(np.corrcoef(a, b)[0, 1])
    diff = a - b
    median_abs = float(np.median(np.abs(diff)))
    passed = r is not None and r >= MIN_R and median_abs <= MAX_MEDIAN_DIFF and n >= MIN_PAIRS
    return {
        "n": n,
        "pearson_r": r,
        "median_abs_diff": median_abs,
        "median_diff": float(np.median(diff)),
        "pass": bool(passed),
    }


def definition_stats(seen: Sequence[Observed], definition: Definition) -> dict[str, object]:
    """How well one definition reproduces the provider's width and length in one match."""
    ours: dict[str, list[float]] = {"width": [], "length": []}
    theirs: dict[str, list[float]] = {"width": [], "length": []}
    for s in seen:
        block = _block(s, definition)
        if block is None:
            continue
        for name, ours_value, their_value in (
            ("width", block.width, s.phase.width),
            ("length", block.length, s.phase.length),
        ):
            if their_value is not None:
                ours[name].append(ours_value)
                theirs[name].append(their_value)
    width, length = (
        _agreement(ours["width"], theirs["width"]),
        _agreement(ours["length"], theirs["length"]),
    )
    total = None
    if width["median_abs_diff"] is not None and length["median_abs_diff"] is not None:
        total = float(width["median_abs_diff"]) + float(length["median_abs_diff"])  # type: ignore[arg-type]
    return {
        "width": width,
        "length": length,
        "abs_diff_sum": total,
        "reproduces": bool(width["pass"]) and bool(length["pass"]),
    }


def select_definition(
    stats: Mapping[int, Mapping[str, Mapping[str, object]]],
) -> tuple[Definition, list[dict[str, object]]]:
    """The chosen definition and the ranking of all of them (the rule of the module docstring).

    ``stats`` is, per match, :func:`definition_stats` by definition name.
    """
    if not stats:
        raise ValueError("name at least one match")
    rows: list[tuple[tuple[int, float, int], dict[str, object]]] = []
    for position, definition in enumerate(DEFINITIONS):
        name = name_of(definition)
        per = [stats[m][name] for m in sorted(stats)]
        reproducing = sum(bool(p["reproduces"]) for p in per)
        sums = [math.inf if p["abs_diff_sum"] is None else float(p["abs_diff_sum"]) for p in per]  # type: ignore[arg-type]
        mean = float(np.mean(sums))
        rows.append(
            (
                (-reproducing, mean, position),
                {
                    "definition": name,
                    "matches_reproducing": reproducing,
                    "mean_abs_diff_sum": None if math.isinf(mean) else mean,
                },
            )
        )
    ranking = [row for _, row in sorted(rows, key=lambda r: r[0])]
    chosen = next(d for d in DEFINITIONS if name_of(d) == ranking[0]["definition"])
    return chosen, ranking


# --- the chosen definition: who fixes the ends, and the bias of the camera ---------------------


def make_metric(
    match: MatchData, phases: Sequence[Phase], definition: Definition, name: str
) -> Metric:
    """One of :data:`METRICS` of the chosen definition as a layer 2 metric of one-frame windows.

    The players behind a unit are the ones that fix the ends of that metric, so V1 keeps the
    phases whose fixers are all detected and V2 splits them by how many are.
    """
    ends = METRICS[name]
    by_frame = {p.frame: p for p in phases}
    if len(by_frame) != len(phases):
        raise ValueError("two phases start at the same frame")
    keepers = goalkeepers(match)

    def metric(window: WindowFrames) -> Reading | None:
        phase = by_frame.get(window.window.frame_start)
        if phase is None:
            return None
        out = np.flatnonzero((window.team_ids != phase.team_in) & window.present[:, 0])
        if len(out) == 0:
            return None
        keeper = keepers.get((phase.period, int(window.team_ids[out[0]])))
        block = measure(
            window.x[out, 0],
            window.y[out, 0],
            window.detected[out, 0],
            window.player_ids[out],
            keeper,
            definition,
        )
        if block is None:
            return None
        value = block.width if ends[0].startswith("y") else block.length
        fixers = sorted({p for end in ends for p in block.fixers[end]})
        return Reading(value, tuple(fixers))

    return metric


def _bias(seen: Sequence[Observed], definition: Definition) -> dict[str, object]:
    """Rank correlations of how much of the block is detected with its measured extent."""
    frac: list[float] = []
    fixed: dict[str, list[float]] = {"width": [], "length": []}
    ours: dict[str, list[float]] = {"width": [], "length": []}
    theirs: dict[str, list[float]] = {"width": [], "length": []}
    their_frac: dict[str, list[float]] = {"width": [], "length": []}
    for s in seen:
        block = _block(s, definition)
        if block is None:
            continue
        listed = np.ones(len(s.ids), dtype=np.bool_)
        if not definition.goalkeeper and s.keeper is not None:
            listed = s.ids != s.keeper
        share = float(s.detected[listed].mean())
        frac.append(share)
        seen_by_id = dict(zip(s.ids.tolist(), s.detected.tolist(), strict=True))
        for name, ends, provider in (
            ("width", ("y_low", "y_high"), s.phase.width),
            ("length", ("x_low", "x_high"), s.phase.length),
        ):
            who = sorted({p for end in ends for p in block.fixers[end]})
            fixed[name].append(sum(seen_by_id[p] for p in who) / len(who))
            ours[name].append(block.width if name == "width" else block.length)
            if provider is not None:
                theirs[name].append(provider)
                their_frac[name].append(share)
    out: dict[str, object] = {"n": len(frac)}
    for name in ("width", "length"):
        out[name] = {
            "block_detected_vs_own": spearman(np.array(frac), np.array(ours[name])),
            "block_detected_vs_provider": spearman(
                np.array(their_frac[name]), np.array(theirs[name])
            ),
            "fixers_detected_vs_own": spearman(np.array(fixed[name]), np.array(ours[name])),
            "n_provider": len(theirs[name]),
        }
    out["block_detected"] = float(np.mean(frac)) if frac else None
    return out


def match_figures(inputs: MatchInputs, definition: Definition) -> dict[str, object]:
    """The visibility figures of one match under the chosen definition."""
    seen = observe(inputs.match, inputs.phases)
    windows = [Window(inputs.match.match_id, p.frame, p.frame) for p in inputs.phases]
    fixers = {
        name: dataclasses.asdict(
            sensitivity(
                make_metric(inputs.match, inputs.phases, definition, name), inputs.long, windows
            )[inputs.match.match_id]
        )
        for name in METRICS
    }
    return {"fixers": fixers, "visibility_bias": _bias(seen, definition)}


# --- verdict and report ------------------------------------------------------------------------


def verdict(reproduces: Mapping[int, bool]) -> dict[str, object]:
    """C3's verdict in the probe from whether the chosen definition reproduces, per match.

    ``c3_survives_probe`` is ``None`` unless all :data:`CALIBRATION_MATCHES` matches are given.
    """
    complete = len(reproduces) == CALIBRATION_MATCHES
    passed = sum(reproduces.values())
    return {
        "c3_survives_probe": passed >= MIN_REPRODUCED if complete else None,
        "complete": complete,
        "matches_reproducing": passed,
        "per_match": {str(m): reproduces[m] for m in sorted(reproduces)},
        "thresholds": {
            "max_median_diff_m": MAX_MEDIAN_DIFF,
            "min_pairs": MIN_PAIRS,
            "min_r": MIN_R,
            "min_reproduced": MIN_REPRODUCED,
        },
        "rule": (
            "C3 dies if the chosen definition of the block reproduces the provider's width and "
            "length (Pearson r >= min_r, median absolute difference <= max_median_diff_m, at "
            "least min_pairs phases) in fewer than min_reproduced matches"
        ),
    }


def s3_report(inputs: Sequence[MatchInputs]) -> dict[str, object]:
    """The per-match figures, the chosen definition, its ranking and the verdict."""
    seen = {i.match.match_id: observe(i.match, i.phases) for i in inputs}
    stats = {m: {name_of(d): definition_stats(s, d) for d in DEFINITIONS} for m, s in seen.items()}
    chosen, ranking = select_definition(stats)
    chosen_name = name_of(chosen)
    matches: dict[str, object] = {}
    for i in inputs:
        m = i.match.match_id
        matches[str(m)] = {
            "counts": {
                "phases": len(i.phases),
                "observed": len(seen[m]),
                "with_provider_width_and_length": sum(
                    p.width is not None and p.length is not None for p in i.phases
                ),
            },
            "definitions": stats[m],
            "chosen": match_figures(i, chosen),
        }
    return {
        "about": (
            "Probe S3 (C3): our block width and length at the start of each phase against the "
            "provider's, under eight fixed definitions; the chosen one, who fixes its ends and "
            "how much of it the camera saw. No outcome of any question: nothing after the "
            "phase's start frame. The rule is in the docstring of ac2fb.defence.probe_s3."
        ),
        "constants": {
            "ends": list(ENDS),
            "max_median_diff_m": MAX_MEDIAN_DIFF,
            "min_pairs": MIN_PAIRS,
            "min_r": MIN_R,
        },
        "chosen_definition": chosen_name,
        "ranking": ranking,
        "matches": matches,
        "verdict": verdict(
            {
                i.match.match_id: bool(stats[i.match.match_id][chosen_name]["reproduces"])
                for i in inputs
            }
        ),
    }


def write_s3_report(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Read each match through the guarded door, write ``probe_s3.json`` (LF); return it."""
    report = s3_report([load_inputs(m) for m in match_ids])
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path
