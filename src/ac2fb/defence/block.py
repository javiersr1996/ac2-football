"""Width and length of a team's block, under a small fixed set of definitions.

The provider's ``team_out_of_possession_width_start`` and ``..._length_start`` do not say how
they are computed. Probe S3 looks for the definition that reproduces them, among the eight
below, which were fixed before the data was read: the product of three binary choices.

- *goalkeeper*: the block includes the goalkeeper or leaves him out (the proxy of
  :func:`ac2fb.reliability.visibility.goalkeepers`; the silver has no roles);
- *extent*: the span between the extreme players (``extremes``, maximum minus minimum) or
  between the 5th and the 95th percentile of the coordinate (``p5_p95``, linear interpolation
  between order statistics, numpy's default);
- *population*: every player the provider lists at the frame (``listed``) or only those with
  ``is_detected`` true (``detected``).

Width is the extent of ``y`` (across the pitch), length the extent of ``x`` (along it), both in
metres, at one frame. The players that *fix* an extent are the ones whose coordinate sets each
end: the extreme player for ``extremes``, the two players whose order statistics are
interpolated for ``p5_p95`` (one when the position falls on a single player). They are what the
layer 2 sensitivity needs to say how much of the number was seen.

Nothing here reads data; it works on the arrays of one frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "DEFINITIONS",
    "ENDS",
    "LOW_PERCENTILE",
    "HIGH_PERCENTILE",
    "MIN_PLAYERS",
    "Block",
    "Definition",
    "measure",
    "name_of",
    "spearman",
]

LOW_PERCENTILE = 5.0
HIGH_PERCENTILE = 95.0
MIN_PLAYERS = 5  # a block with fewer players under a definition is not measured
ENDS: tuple[str, ...] = ("x_low", "x_high", "y_low", "y_high")  # the four ends of the block


@dataclass(frozen=True)
class Definition:
    """One way of measuring a block: with or without the goalkeeper, span, who counts."""

    goalkeeper: bool
    extent: str  # "extremes" | "p5_p95"
    population: str  # "listed" | "detected"


@dataclass(frozen=True)
class Block:
    """A block measured under one definition.

    ``fixers`` maps each end of :data:`ENDS` to the ids of the players that fix it; ``players``
    is how many entered the measure.
    """

    width: float
    length: float
    players: int
    fixers: dict[str, tuple[int, ...]]


# Fixed order: it breaks the last tie of the selection rule of probe S3.
DEFINITIONS: tuple[Definition, ...] = tuple(
    Definition(goalkeeper, extent, population)
    for goalkeeper, extent, population in product(
        (False, True), ("extremes", "p5_p95"), ("listed", "detected")
    )
)


def name_of(definition: Definition) -> str:
    """A stable name such as ``outfield_extremes_listed`` or ``with_gk_p5_p95_detected``."""
    who = "with_gk" if definition.goalkeeper else "outfield"
    return f"{who}_{definition.extent}_{definition.population}"


def _end_players(
    values: NDArray[np.float64], ids: NDArray[np.int64], definition: Definition
) -> tuple[tuple[int, ...], tuple[int, ...], float]:
    """Players fixing the low and the high end of ``values``, and the extent."""
    order = np.argsort(values, kind="stable")
    sorted_values = values[order]
    if definition.extent == "extremes":
        return (
            (int(ids[order[0]]),),
            (int(ids[order[-1]]),),
            float(sorted_values[-1] - sorted_values[0]),
        )
    ends: list[tuple[int, ...]] = []
    for percentile in (LOW_PERCENTILE, HIGH_PERCENTILE):
        position = round(percentile / 100.0 * (len(values) - 1), 9)
        lo, hi = int(np.floor(position)), int(np.ceil(position))
        ends.append(tuple(sorted({int(ids[order[lo]]), int(ids[order[hi]])})))
    extent = float(np.percentile(values, HIGH_PERCENTILE) - np.percentile(values, LOW_PERCENTILE))
    return ends[0], ends[1], extent


def measure(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    detected: NDArray[np.bool_],
    ids: NDArray[np.int64],
    keeper: int | None,
    definition: Definition,
) -> Block | None:
    """Width and length of the players given (one team, one frame) under ``definition``.

    ``keeper`` is the goalkeeper's id, left out unless the definition keeps him. Returns
    ``None`` with fewer than :data:`MIN_PLAYERS` players or a non-finite coordinate.
    """
    keep = np.ones(len(ids), dtype=np.bool_)
    if not definition.goalkeeper and keeper is not None:
        keep &= ids != keeper
    if definition.population == "detected":
        keep &= detected
    if keep.sum() < MIN_PLAYERS:
        return None
    xs, ys, who = x[keep], y[keep], ids[keep]
    if not (np.isfinite(xs).all() and np.isfinite(ys).all()):
        return None
    x_low, x_high, length = _end_players(xs, who, definition)
    y_low, y_high, width = _end_players(ys, who, definition)
    return Block(
        width=width,
        length=length,
        players=int(keep.sum()),
        fixers={"x_low": x_low, "x_high": x_high, "y_low": y_low, "y_high": y_high},
    )


def _average_ranks(values: NDArray[np.float64]) -> NDArray[np.float64]:
    unique, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    last = np.cumsum(counts)
    first = last - counts + 1
    return np.asarray(((first + last) / 2.0)[inverse], dtype=np.float64)


def spearman(a: NDArray[np.float64], b: NDArray[np.float64]) -> float | None:
    """Rank correlation (Pearson of the average ranks, so ties are handled); ``None`` if undefined.

    Undefined means fewer than three pairs or one of the two series constant.
    """
    if len(a) != len(b):
        raise ValueError("the two series must have the same length")
    if len(a) < 3:
        return None
    ra, rb = (
        _average_ranks(np.asarray(a, dtype=np.float64)),
        _average_ranks(np.asarray(b, dtype=np.float64)),
    )
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])
