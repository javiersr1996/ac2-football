"""The reliability map: ``reports/reliability.csv``, one row per match, metric, stratum and variant.

For each match and each metric of :data:`~ac2fb.reliability.metrics.METRICS`, the metric in
V0 (every unit), V1 (the units whose players were detected throughout the window) and V2 (one
row per ``k`` of ``n``: ``k`` of the ``n`` players the metric was computed from detected
throughout, ``V2_3of4``, sorted by ``n`` and then ``k``, since units with another ``n`` are not
the same thing), as :func:`~ac2fb.reliability.sensitivity.sensitivity_by_size` gives them, over
all its units (``ball_stratum`` ``all``). The line's reaction is also given within each direction
of the incoming ball (:func:`~ac2fb.reliability.metrics.reaction_strata`), so V0 and V1 are compared
inside a stratum: V1 keeps what is near the ball, and the line follows the ball (m10). ``n`` and
``mean`` are those of the row's variant. The remaining columns describe the V0 units of the row's
stratum and repeat on each row of the group: units kept and skipped, player-frames behind the
metric, the fraction of them extrapolated and the fraction the provider does not list, and the
``gap_len`` of the extrapolated ones (count, median, 90th percentile, maximum, in frames).

The file has LF line endings, floats rounded to six decimals and an empty cell for "no value".
:func:`check` recomputes it and compares every cell with the file on disk.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from ac2fb.reliability import metrics
from ac2fb.reliability.match import load_with_long
from ac2fb.reliability.sensitivity import Sensitivity, SizedStratum, sensitivity_by_size

__all__ = [
    "COLUMNS",
    "REPORT_NAME",
    "Check",
    "cell",
    "check",
    "check_csv",
    "match_rows",
    "render",
    "render_csv",
    "write_table",
]

REPORT_NAME = "reliability.csv"
_DECIMALS = 6
COLUMNS: tuple[str, ...] = (
    "match_id",
    "metric",
    "ball_stratum",
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
_KEY = 4  # match_id, metric, ball_stratum and variant name a row


def cell(value: float | int | None) -> str:
    """A CSV cell: an int as it is, a float to six decimals, empty for no value or a NaN."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    if isinstance(value, int):
        return str(value)
    return repr(round(value, _DECIMALS))


def _rows(
    metric: str, stratum: str, s: Sensitivity, sized: Sequence[SizedStratum]
) -> list[list[str]]:
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
    variants += [(f"V2_{k.detected_players}of{k.players}", k.n, k.mean) for k in sized]
    return [
        [str(s.match_id), metric, stratum, name, *map(cell, [n, mean, *shared])]
        for name, n, mean in variants
    ]


def match_rows(match_id: int) -> list[list[str]]:
    """The rows of one match, read through the guarded door, metrics in :data:`METRICS` order."""
    match, long = load_with_long(match_id)
    rows: list[list[str]] = []
    for name, (metric, windows) in metrics.metric_units(match).items():
        rows += _rows(name, "all", *sensitivity_by_size(metric, long, windows)[match_id])
        if name == "line_reaction_m":
            for direction, part in metrics.reaction_strata(match).items():
                rows += _rows(name, direction, *sensitivity_by_size(metric, long, part)[match_id])
    return rows


def render_csv(columns: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """The CSV text of the rows under the header: LF line endings, one final LF."""
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)
    return out.getvalue()


def render(rows: Sequence[Sequence[str]]) -> str:
    """The CSV text of reliability rows under :data:`COLUMNS`."""
    return render_csv(COLUMNS, rows)


def write_table(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Write ``reports_dir/reliability.csv`` for the matches, sorted by match id; return it."""
    rows = [row for m in sorted(match_ids) for row in match_rows(m)]
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render(rows).encode("utf-8"))
    return path


@dataclass(frozen=True)
class Check:
    """What a check verified and what it found."""

    matches: int
    rows: int
    cells: int
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def check_csv(
    name: str,
    columns: Sequence[str],
    key: int,
    match_ids: Sequence[int],
    rows_of: Callable[[int], list[list[str]]],
    raw: bytes | None,
) -> Check:
    """Recompute the rows of the matches and compare every cell with the bytes of a CSV report.

    ``rows_of`` gives the rows of one match. ``raw`` is the file ``name`` as the command line
    read it (``None``: there is none), so nothing here opens a file; the first ``key`` columns
    name a row. Problems: the file is
    missing, has a carriage return or another header, lacks rows of a match, has rows the code
    does not produce, or differs in a cell (named by its key and column). ``rows`` and ``cells``
    count what was compared.
    """
    if raw is None:
        return Check(0, 0, 0, (f"{name} does not exist",))
    problems: list[str] = []
    if b"\r" in raw:
        problems.append("the file has a carriage return")
    parsed = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))
    if not parsed or tuple(parsed[0]) != tuple(columns):
        return Check(0, 0, 0, (*problems, "the header is not the one the code writes"))
    wanted = {str(m) for m in match_ids}
    on_disk = [row for row in parsed[1:] if row[:1] and row[0] in wanted]
    fresh = [row for m in sorted(match_ids) for row in rows_of(m)]
    disk = {tuple(row[:key]): row for row in on_disk}
    code = {tuple(row[:key]): row for row in fresh}
    if len(disk) != len(on_disk):
        problems.append(f"the file repeats a ({', '.join(columns[:key])})")
    problems += [f"missing from the file: {'/'.join(k)}" for k in code if k not in disk]
    problems += [f"not produced by the code: {'/'.join(k)}" for k in disk if k not in code]
    cells = 0
    for k, row in code.items():
        if k not in disk:
            continue
        if len(disk[k]) != len(columns):
            problems.append(f"{'/'.join(k)}: {len(disk[k])} cells, not {len(columns)}")
            continue
        for column, ours, theirs in zip(columns, row, disk[k], strict=True):
            cells += 1
            if ours != theirs:
                problems.append(f"{'/'.join(k)} {column}: file {theirs!r}, code {ours!r}")
    return Check(len(wanted), len(code), cells, tuple(problems))


def check(match_ids: Sequence[int], raw: bytes | None) -> Check:
    """Recompute the reliability rows of the matches and compare every cell with ``raw``."""
    return check_csv(REPORT_NAME, COLUMNS, _KEY, match_ids, match_rows, raw)
