"""The layer 2 report: what the camera saw of each match, written to ``reports/layer2.json``.

One JSON for all the matches asked for, with the figures of each match under ``matches`` (no
match is merged into another), the minimum, median and maximum over those matches under
``summary`` (the plan's way of quoting a spread), the pooled figures of the plan-definition
runs under ``pooled`` and the comparison with the plan's inventory under ``inventory``. The
file has sorted keys, rounded floats, LF line endings and no NaN.

Everything in it describes visibility at the instants of the provider's events and the shape of
the extrapolated runs. It contains no outcome of any candidate question. :func:`check` recomputes
it and compares every value with the file on disk.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ac2fb.reliability import inventory, runs, visibility
from ac2fb.reliability.match import MatchData, load_match

__all__ = [
    "REPORT_NAME",
    "Check",
    "JsonCheck",
    "check",
    "check_json",
    "layer2_report",
    "match_report",
    "render_report",
    "write_report",
]

REPORT_NAME = "layer2.json"
_DECIMALS = 6


def match_report(match: MatchData) -> dict[str, object]:
    """Every layer 2 figure of one match, as nested dicts of numbers."""
    return {
        "acceleration": runs.acceleration_summary(match),
        "ball_distance": visibility.detection_by_ball_distance(match),
        "block": visibility.block_detection(match),
        "detection": visibility.detection_shares(match),
        "engager": visibility.engager_detection(match),
        "line": visibility.defensive_line_detection(match),
        "reacquisition": runs.run_summary(runs.extrapolated_runs(match, bridge_holes=True)),
        "reception": visibility.reception_detection(match),
        "runs": runs.run_summary(runs.extrapolated_runs(match)),
        "steps": runs.step_summary(match),
        "unlisted": runs.unlisted_stretches(match),
    }


def _leaves(node: object, prefix: str = "") -> dict[str, float]:
    if isinstance(node, Mapping):
        found: dict[str, float] = {}
        for key, value in node.items():
            found.update(_leaves(value, f"{prefix}.{key}" if prefix else str(key)))
        return found
    if isinstance(node, bool) or not isinstance(node, int | float):
        return {}
    return {prefix: float(node)}


def _summary(per_match: Mapping[int, Mapping[str, object]]) -> dict[str, object]:
    """Min, median and max over the matches of every numeric figure, with how many had it."""
    table: dict[str, list[float]] = {}
    for report in per_match.values():
        for path, value in _leaves(report).items():
            table.setdefault(path, []).append(value)
    return {
        path: {
            "n_matches": len(v),
            "min": min(v),
            "median": statistics.median(v),
            "max": max(v),
        }
        for path, v in sorted(table.items())
    }


def _pooled_bands(
    matches: Sequence[MatchData],
) -> tuple[dict[str, tuple[float, ...]], dict[str, object]]:
    """Plan-definition runs pooled over the matches: jump by gap band, run lengths."""
    jumps: list[list[float]] = [[] for _ in runs.BANDS]
    inside: list[list[float]] = [[] for _ in runs.BANDS]
    lengths: list[int] = []
    for match in matches:
        found = runs.extrapolated_runs(match, bridge_holes=True)
        extrapolated = ~found.detected
        lengths += found.length[extrapolated].tolist()
        band = runs.band_of(found.length)
        for i in range(len(runs.BANDS)):
            pick = extrapolated & (band == i) & ~np.isnan(found.jump)
            jumps[i] += found.jump[pick].tolist()
            inside[i] += found.mean_step[pick & ~np.isnan(found.mean_step)].tolist()
    bands = {
        name: (
            len(jumps[i]),
            *(float(np.quantile(jumps[i], q)) for q in (0.5, 0.9, 0.99)),
            float(np.median(inside[i])),
        )
        for i, (name, _) in enumerate(runs.BANDS)
        if jumps[i]
    }
    pooled = {
        "gap_bands": {
            name: {
                "n": b[0],
                "jump_median": b[1],
                "jump_p90": b[2],
                "jump_p99": b[3],
                "inside_step_median": b[4],
            }
            for name, b in bands.items()
        },
        "runs": {
            "n": len(lengths),
            "length_median": float(np.median(lengths)),
            "length_p90": float(np.quantile(lengths, 0.9)),
            "length_p99": float(np.quantile(lengths, 0.99)),
        },
    }
    return bands, pooled


def layer2_report(match_ids: Sequence[int]) -> dict[str, object]:
    """Read each match through the guarded door and build the report of all of them."""
    matches = [load_match(m) for m in match_ids]
    per_match = {m.match_id: match_report(m) for m in matches}
    bands, pooled = _pooled_bands(matches)
    return {
        "about": (
            "Layer 2: visibility of the tracking per match. Descriptive only; no outcome of "
            "any question. Runs under 'reacquisition' and 'pooled' follow the plan's probes "
            "(unlisted frames do not end a run); 'runs' ends a run at a frame the provider "
            "does not list."
        ),
        "matches": {str(k): v for k, v in per_match.items()},
        "summary": _summary(per_match),
        "pooled": pooled,
        "inventory": inventory.compare(per_match, bands),
    }


def _clean(node: object) -> object:
    if isinstance(node, Mapping):
        return {str(k): _clean(v) for k, v in node.items()}
    if isinstance(node, list | tuple):
        return [_clean(v) for v in node]
    if isinstance(node, bool | str) or node is None:
        return node
    if isinstance(node, int | np.integer):
        return int(node)
    if isinstance(node, float | np.floating):
        return None if np.isnan(node) else round(float(node), _DECIMALS)
    raise TypeError(f"cannot write a {type(node).__name__} to the report")


def render_report(report: Mapping[str, object]) -> str:
    """The JSON text of a report: sorted keys, two-space indent, rounded, one final LF."""
    return json.dumps(_clean(report), indent=2, sort_keys=True, allow_nan=False) + "\n"


def write_report(report: Mapping[str, object], reports_dir: Path) -> Path:
    """Write ``reports_dir/layer2.json`` with LF line endings; return its path."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path


@dataclass(frozen=True)
class Check:
    """What :func:`check` verified and what it found."""

    matches: int
    values: int
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def _flat(node: object, prefix: str = "") -> dict[str, object]:
    """Every value of a parsed JSON by its path (``a.b.0``): numbers, strings, booleans, nulls."""
    if isinstance(node, dict):
        items = list(node.items())
    elif isinstance(node, list):
        items = list(enumerate(node))
    else:
        return {prefix: node}
    found: dict[str, object] = {}
    for key, value in items:
        found.update(_flat(value, f"{prefix}.{key}" if prefix else str(key)))
    return found


def check(match_ids: Sequence[int], raw: bytes | None) -> Check:
    """Recompute the report of the matches and compare every value with the bytes of the file.

    ``raw`` is ``layer2.json`` as the command line read it (``None``: there is none), so nothing
    here opens a file. The summary, pooled and inventory figures are over all the matches, so the
    matches must be those of the file. Problems: the file is missing, has a carriage return, lacks
    a value the code writes, has one it does not, differs in one (named by its path), or is not
    rendered as the code renders it. ``values`` counts what was compared.
    """
    result = check_json(REPORT_NAME, render_report(layer2_report(match_ids)), raw)
    return Check(len(match_ids), result.values, result.problems)


@dataclass(frozen=True)
class JsonCheck:
    """What :func:`check_json` compared (``values``) and what it found."""

    values: int
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def check_json(name: str, fresh: str, raw: bytes | None) -> JsonCheck:
    """Compare every value of a recomputed report (``fresh``, as rendered) with the bytes of a file.

    ``raw`` is the file ``name`` as the command line read it (``None``: there is none), so nothing
    here opens a file. Problems: the file is missing, has a carriage return, lacks a value the
    code writes, has one it does not, differs in one (named by its path), or is not rendered as
    the code renders it.
    """
    if raw is None:
        return JsonCheck(0, (f"{name} does not exist",))
    problems = ["the file has a carriage return"] if b"\r" in raw else []
    code, disk = _flat(json.loads(fresh)), _flat(json.loads(raw.decode("utf-8")))
    problems += [f"missing from the file: {p}" for p in code if p not in disk]
    problems += [f"not produced by the code: {p}" for p in disk if p not in code]
    compared = [p for p in code if p in disk]
    problems += [f"{p}: file {disk[p]!r}, code {code[p]!r}" for p in compared if disk[p] != code[p]]
    if not problems and raw.decode("utf-8") != fresh:
        problems.append("the file is not rendered as the code renders it")
    return JsonCheck(len(compared), tuple(problems))
