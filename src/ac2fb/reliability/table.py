"""The reliability map: ``reports/reliability.csv``, one row per match, metric and variant.

For each match and each metric of :data:`~ac2fb.reliability.metrics.METRICS`, the metric in
V0 (every unit), V1 (the units whose players were detected throughout the window) and V2 (one
row per number of those players detected, ``V2_0``, ``V2_1``, ...), as
:func:`~ac2fb.reliability.sensitivity.sensitivity` gives them. ``n`` and ``mean`` are those of
the row's variant. The remaining columns describe the metric's V0 units and repeat on each row of
the pair: units kept and skipped, player-frames behind the metric, the fraction of them
extrapolated and the fraction the provider does not list, and the ``gap_len`` of the
extrapolated ones (count, median, 90th percentile, maximum, in frames).

The file has LF line endings, floats rounded to six decimals and an empty cell for "no value".
:func:`check` recomputes it and compares every cell with the file on disk.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ac2fb.reliability import metrics
from ac2fb.reliability.match import load_with_long
from ac2fb.reliability.sensitivity import Sensitivity, sensitivity

__all__ = ["COLUMNS", "REPORT_NAME", "Check", "check", "match_rows", "render", "write_table"]

REPORT_NAME = "reliability.csv"
_DECIMALS = 6
COLUMNS: tuple[str, ...] = (
    "match_id",
    "metric",
    "variant",
    "n",
    "mean",
    "n_units",
    "n_skipped",
    "player_frames",
    "extrapolated_fraction",
    "absent_fraction",
    "gap_len_n",
    "gap_len_median",
    "gap_len_p90",
    "gap_len_max",
)


def _cell(value: float | int | None) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    if isinstance(value, int):
        return str(value)
    return repr(round(value, _DECIMALS))


def _rows(metric: str, s: Sensitivity) -> list[list[str]]:
    shared = [
        s.n_units,
        s.n_skipped,
        s.player_frames,
        s.extrapolated_fraction,
        s.absent_fraction,
        s.gap_len.n,
        s.gap_len.median,
        s.gap_len.p90,
        s.gap_len.max,
    ]
    variants = [("V0", s.v0.n, s.v0.mean), ("V1", s.v1.n, s.v1.mean)]
    variants += [(f"V2_{k.detected_players}", k.n, k.mean) for k in s.v2]
    return [
        [str(s.match_id), metric, name, *map(_cell, [n, mean, *shared])]
        for name, n, mean in variants
    ]


def match_rows(match_id: int) -> list[list[str]]:
    """The rows of one match, read through the guarded door, metrics in :data:`METRICS` order."""
    match, long = load_with_long(match_id)
    rows: list[list[str]] = []
    for name, (metric, windows) in metrics.metric_units(match).items():
        rows += _rows(name, sensitivity(metric, long, windows)[match_id])
    return rows


def render(rows: Sequence[Sequence[str]]) -> str:
    """The CSV text of the rows under the header: LF line endings, one final LF."""
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return out.getvalue()


def write_table(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Write ``reports_dir/reliability.csv`` for the matches, sorted by match id; return it."""
    rows = [row for m in sorted(match_ids) for row in match_rows(m)]
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render(rows).encode("utf-8"))
    return path


@dataclass(frozen=True)
class Check:
    """What :func:`check` verified and what it found."""

    matches: int
    rows: int
    cells: int
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def check(match_ids: Sequence[int], raw: bytes | None) -> Check:
    """Recompute the rows of the matches and compare every cell with the bytes of the file.

    ``raw`` is ``reliability.csv`` as the command line read it (``None``: there is none), so
    nothing here opens a file. Problems: the file is missing, has a carriage return or another
    header, lacks rows of a match, has rows the code does not produce, or differs in a cell
    (named by match, metric, variant and column). ``rows`` and ``cells`` count what was compared.
    """
    if raw is None:
        return Check(0, 0, 0, (f"{REPORT_NAME} does not exist",))
    problems: list[str] = []
    if b"\r" in raw:
        problems.append("the file has a carriage return")
    parsed = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))
    if not parsed or tuple(parsed[0]) != COLUMNS:
        return Check(0, 0, 0, (*problems, "the header is not the one the code writes"))
    wanted = {str(m) for m in match_ids}
    on_disk = [row for row in parsed[1:] if row[:1] and row[0] in wanted]
    fresh = [row for m in sorted(match_ids) for row in match_rows(m)]
    disk = {tuple(row[:3]): row for row in on_disk}
    code = {tuple(row[:3]): row for row in fresh}
    if len(disk) != len(on_disk):
        problems.append("the file repeats a (match, metric, variant)")
    problems += [f"missing from the file: {'/'.join(k)}" for k in code if k not in disk]
    problems += [f"not produced by the code: {'/'.join(k)}" for k in disk if k not in code]
    cells = 0
    for k, row in code.items():
        if k not in disk:
            continue
        if len(disk[k]) != len(COLUMNS):
            problems.append(f"{'/'.join(k)}: {len(disk[k])} cells, not {len(COLUMNS)}")
            continue
        for column, ours, theirs in zip(COLUMNS, row, disk[k], strict=True):
            cells += 1
            if ours != theirs:
                problems.append(f"{'/'.join(k)} {column}: file {theirs!r}, code {ours!r}")
    return Check(len(wanted), len(code), cells, tuple(problems))
