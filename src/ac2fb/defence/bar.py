"""The calibration bar of the protocol, its null, and its power on a fixed design of units.

Nothing here reads data. A :class:`Design` lists, for each unit of one candidate and variant, its
match, its stratum, its cause group and its team possession; the functions below put simulated
outcomes on it. Everything in this module was written before any power was computed.

**The statistic** (the pooling of :func:`ac2fb.defence.line.within_strata`). A *cell* is a
(match, stratum) with at least :data:`MIN_CELL` units in each group; the units of the other
cells are left out. In a cell, ``d`` is the mean of the cause group (``pressed``) minus the mean
of the rest, ``s`` the sample sd (ddof 1) of all its units, ``z = d / s`` and
``w = n_p n_f / (n_p + n_f)``. A match's effect ``E_m`` is the ``w``-weighted mean of the ``z``
of its cells; the pooled effect ``T`` is the ``w``-weighted mean over every cell of every match.

**The bar** (the calibration bar the plan fixes for the protocol of task 19): ``T`` has the sign
of the effect ``E_m`` of at least :data:`BAR_SAME_SIGN` matches (a match without a cell never
agrees, and no match agrees with a ``T`` of 0), and the two-sided permutation p,
``(1 + #{|T*| >= |T|}) / (1 + N_PERMUTATIONS)``, is at most :data:`BAR_P`: at most
:data:`BAR_COUNT_AT_MOST` of the :data:`N_PERMUTATIONS` null draws may be as extreme as ``T``.

**The null**, always inside a match. *Unblocked*: the cause label is permuted inside each cell.
*Blocked by team possession* (the protocol blocks when the within-possession correlation measured
by task 17 exceeds :data:`BLOCK_RHO`): with ``T = sum_i a_i y_i``, each possession contributes
``S_k = sum over its units of a_i (y_i - mean of the unit's cell)`` (the ``S_k`` add up to ``T``),
and the null flips the sign of each ``S_k`` at random, so the units of one possession never move
apart. A permutation of labels by blocks is not defined when one possession holds both groups;
the flip is the block null of tracklab's P5.

**The approximation** (only to avoid drawing :data:`N_PERMUTATIONS` nulls in each replicate).
Under the unblocked null ``T`` has mean 0 and variance exactly ``1 / sum w`` (in a cell the
permutation variance of ``d`` is ``s^2 (1/n_p + 1/n_f)``); under the flip, ``sum S_k^2``. With
``Z`` the ratio of ``T`` to the root of that variance and ``q = 2 Phi(-|Z|)``, the count of null
draws as extreme as ``T`` is taken as Binomial(``N_PERMUTATIONS``, ``q``), and the permutation
part of the bar passes with probability P(count <= :data:`BAR_COUNT_AT_MOST`)
(:func:`pass_probability`). ``tests/test_bar.py`` contrasts it with the full permutation.

**The power.** Each unit's outcome is ``y = effect * pressed + noise``, the noise of unit
variance with the within-possession correlation ``rho`` of its match:
``sqrt(rho) u_k + sqrt(1 - rho) e_i``, one ``u`` per team possession. The effect is in sd of
the noise. The pass rate of an effect is the mean over the replicates of the sign condition times
the pass probability of the permutation part; the noise is common to every effect of a call
(common random numbers), so the curve is smooth in the effect. :func:`mde80` gives the smallest
effect on the grid whose pass rate is at least :data:`POWER_TARGET`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "BAR_COUNT_AT_MOST",
    "BAR_P",
    "BAR_SAME_SIGN",
    "BLOCK_RHO",
    "CHUNK",
    "COARSE_STEP",
    "FINE_STEP",
    "MAX_EFFECT",
    "MIN_CELL",
    "N_PERMUTATIONS",
    "POWER_REPLICATES",
    "POWER_TARGET",
    "Correlation",
    "Design",
    "Power",
    "Prepared",
    "bar_probability",
    "draw_noise",
    "full_passes",
    "mde80",
    "null_draws",
    "pass_probability",
    "pass_rates",
    "prepare",
    "within_possession_correlation",
]

MIN_CELL = 5  # units of each group a cell needs to enter the statistic (probe S2's minimum)
BAR_SAME_SIGN = 8  # matches whose effect must share the sign of the pooled effect
BAR_P = 0.00135  # two-sided permutation p at most this (the plan's calibration bar)
N_PERMUTATIONS = 2000  # null draws of the protocol
BAR_COUNT_AT_MOST = max(
    c for c in range(N_PERMUTATIONS + 1) if (1 + c) / (1 + N_PERMUTATIONS) <= BAR_P
)  # derived, never a second literal: 1 of 2000
BLOCK_RHO = 0.1  # the protocol blocks the team possession above this correlation
POWER_REPLICATES = 2500
POWER_TARGET = 0.8
COARSE_STEP = 0.05  # sd; the curve is drawn on this grid from 0 to MAX_EFFECT
FINE_STEP = 0.01  # sd; the MDE80 is refined on this grid inside the bracketing coarse step
MAX_EFFECT = 2.0  # sd
CHUNK = 250  # replicates drawn at once; part of the random stream, so fixed

Floats = NDArray[np.float64]
Ints = NDArray[np.int64]
Bools = NDArray[np.bool_]


@dataclass(frozen=True)
class Design:
    """The units of one candidate and variant.

    ``matches`` lists every match of the design, also one left without units; ``match`` indexes
    it per unit. ``stratum`` and ``possession`` are labels per unit; a possession label is read
    inside its match only, so two matches may reuse one.
    """

    matches: tuple[int, ...]
    match: Ints
    stratum: tuple[str, ...]
    pressed: Bools
    possession: tuple[str, ...]


@dataclass(frozen=True)
class Prepared:
    """A design reduced to the cells that enter the statistic, with the index arrays it needs.

    The kept units are ordered by possession, then cell, then group, so that a *combo* (one
    possession's units of one group of one cell) is a contiguous run, and so is each possession
    over the combos. ``by_cell`` reorders them by cell and group: each cell is two runs, its free
    units then its pressed ones, starting at ``cell_group_starts``.
    """

    n_matches: int
    unit_match: Ints
    unit_cluster: Ints
    unit_group: Bools
    cell_match: Ints
    cell_onehot: Floats
    cell_n1: Floats
    cell_n0: Floats
    weight: Floats
    by_cell: Ints
    by_cell_cell: Ints
    cell_group_starts: Ints
    combo_starts: Ints
    combo_cell: Ints
    combo_group: Bools
    combo_n: Floats
    cluster_starts: Ints
    cluster_match: Ints


@dataclass(frozen=True)
class Power:
    """Pass rate of the bar by effect (sd), and the smallest effect with at least the target."""

    effects: tuple[float, ...]
    pass_rate: tuple[float, ...]
    mde80: float | None
    replicates: int


@dataclass(frozen=True)
class Correlation:
    """Pairwise within-possession correlation of a statistic standardised inside each cell.

    ``rho`` is ``None`` without a pair of units in one possession. ``units`` entered (cells of at
    least two units with a positive sd), ``pairs`` of units share a possession, ``possessions``
    hold two units or more.
    """

    rho: float | None
    pairs: int
    units: int
    possessions: int


# --- the design --------------------------------------------------------------------------------


def _codes(labels: Sequence[object]) -> Ints:
    index: dict[object, int] = {}
    return np.array([index.setdefault(v, len(index)) for v in labels], dtype=np.int64)


def prepare(design: Design) -> Prepared:
    """Keep the cells with :data:`MIN_CELL` units of each group and build the index arrays."""
    n = len(design.match)
    if not (len(design.stratum) == len(design.pressed) == len(design.possession) == n):
        raise ValueError("every unit needs a match, a stratum, a group and a possession")
    match = np.asarray(design.match, dtype=np.int64)
    group = np.asarray(design.pressed, dtype=np.bool_)
    cell_all = _codes(list(zip(match.tolist(), design.stratum, strict=True)))
    cluster_all = _codes(list(zip(match.tolist(), design.possession, strict=True)))
    n_cells_all = int(cell_all.max()) + 1 if n else 0
    n1_all = np.bincount(cell_all[group], minlength=n_cells_all)
    n0_all = np.bincount(cell_all[~group], minlength=n_cells_all)
    used = (n1_all >= MIN_CELL) & (n0_all >= MIN_CELL)
    keep = used[cell_all] if n else np.zeros(0, dtype=np.bool_)
    renumber = np.cumsum(used) - 1
    cell = renumber[cell_all[keep]].astype(np.int64)
    cluster = _codes(cluster_all[keep].tolist())
    group, match = group[keep], match[keep]
    order = np.lexsort((group, cell, cluster))  # by cluster, then cell, then group
    cell, cluster, group, match = cell[order], cluster[order], group[order], match[order]
    n_cells = int(used.sum())
    cell_match = np.zeros(n_cells, dtype=np.int64)
    cell_match[cell] = match
    cell_onehot = np.zeros((n_cells, len(design.matches)))
    cell_onehot[np.arange(n_cells), cell_match] = 1.0
    n1 = np.bincount(cell[group], minlength=n_cells).astype(np.float64)
    n0 = np.bincount(cell[~group], minlength=n_cells).astype(np.float64)
    by_cell = np.lexsort((group, cell)).astype(np.int64)
    sizes = np.column_stack([n0, n1]).ravel().astype(np.int64)  # free then pressed, per cell
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int64)
    combo_key = np.column_stack([cluster, cell, group.astype(np.int64)])
    new_combo = np.ones(len(cell), dtype=np.bool_)
    if len(cell) > 1:
        new_combo[1:] = (combo_key[1:] != combo_key[:-1]).any(axis=1)
    combo_starts = np.flatnonzero(new_combo).astype(np.int64)
    combo_cluster = cluster[combo_starts]
    new_cluster = np.ones(len(combo_starts), dtype=np.bool_)
    if len(combo_starts) > 1:
        new_cluster[1:] = combo_cluster[1:] != combo_cluster[:-1]
    cluster_starts = np.flatnonzero(new_cluster).astype(np.int64)
    n_clusters = int(cluster.max()) + 1 if len(cluster) else 0
    cluster_match = np.zeros(n_clusters, dtype=np.int64)
    cluster_match[cluster] = match
    return Prepared(
        n_matches=len(design.matches),
        unit_match=match,
        unit_cluster=cluster,
        unit_group=group,
        cell_match=cell_match,
        cell_onehot=cell_onehot,
        cell_n1=n1,
        cell_n0=n0,
        weight=n1 * n0 / (n1 + n0) if n_cells else np.zeros(0),
        by_cell=by_cell,
        by_cell_cell=cell[by_cell],
        cell_group_starts=starts,
        combo_starts=combo_starts,
        combo_cell=cell[combo_starts],
        combo_group=group[combo_starts],
        combo_n=np.diff(np.append(combo_starts, len(cell))).astype(np.float64),
        cluster_starts=cluster_starts,
        cluster_match=cluster_match,
    )


def draw_noise(
    prepared: Prepared, rho_by_match: Sequence[float], replicates: int, rng: np.random.Generator
) -> Floats:
    """``replicates`` rows of unit-variance noise with the within-possession correlation.

    ``rho_by_match`` is indexed like ``Design.matches``; a negative value is taken as 0. One
    shared draw per team possession carries ``rho`` of the variance, one per unit the rest.
    """
    rho = np.clip(np.asarray(rho_by_match, dtype=np.float64), 0.0, 1.0 - 1e-12)
    n_clusters = len(prepared.cluster_match)
    shared = rng.standard_normal((replicates, n_clusters)) * np.sqrt(rho[prepared.cluster_match])
    own = rng.standard_normal((replicates, len(prepared.unit_match)))
    noise: Floats = shared[:, prepared.unit_cluster] + own * np.sqrt(1.0 - rho[prepared.unit_match])
    return noise


# --- the statistic and the bar -----------------------------------------------------------------


@dataclass(frozen=True)
class _Sums:
    """Per replicate, sums of the noise alone: by cell and group, squared by cell, by combo.

    The effect enters every outcome linearly, so these give the statistic at any effect.
    """

    free: Floats
    pressed: Floats
    squares: Floats
    combo: Floats


@dataclass(frozen=True)
class _Stats:
    """Per replicate: the pooled effect, the sign condition, and each cell's mean and sd."""

    pooled: Floats
    agrees: Bools
    mean: Floats
    sd: Floats


def _sums(prepared: Prepared, noise: Floats) -> _Sums:
    r = noise.shape[0]
    if len(prepared.weight) == 0:
        empty = np.zeros((r, 0))
        return _Sums(empty, empty, empty, empty)
    ordered = noise[:, prepared.by_cell]
    sums = np.add.reduceat(ordered, prepared.cell_group_starts, axis=1)
    squares = np.add.reduceat(ordered * ordered, prepared.cell_group_starts, axis=1)
    combo = np.add.reduceat(noise, prepared.combo_starts, axis=1)
    return _Sums(sums[:, 0::2], sums[:, 1::2], squares[:, 0::2] + squares[:, 1::2], combo)


def _stats(prepared: Prepared, sums: _Sums, effect: float) -> _Stats:
    n1, n0 = prepared.cell_n1, prepared.cell_n0
    n = n1 + n0
    sum1 = sums.pressed + effect * n1
    sum0 = sums.free
    squares = sums.squares + 2.0 * effect * sums.pressed + effect * effect * n1
    mean = (sum0 + sum1) / n
    var = (squares - n * mean * mean) / (n - 1.0)
    sd = np.sqrt(np.maximum(var, 1e-300))
    wz = prepared.weight * (sum1 / n1 - sum0 / n0) / sd
    match_weight = prepared.weight @ prepared.cell_onehot
    has_cell = match_weight > 0
    per_match = (wz @ prepared.cell_onehot)[:, has_cell] / match_weight[has_cell]
    pooled = wz.sum(axis=1) / prepared.weight.sum()
    agreeing = (np.sign(per_match) == np.sign(pooled)[:, None]).sum(axis=1)
    agrees = (agreeing >= BAR_SAME_SIGN) & (pooled != 0.0)
    return _Stats(pooled, agrees, mean, sd)


def _possession_sums(prepared: Prepared, sums: _Sums, stats: _Stats, effect: float) -> Floats:
    """``S_k`` per replicate and team possession (see the module docstring); they add to ``T``."""
    scale = (prepared.weight / prepared.weight.sum()) / stats.sd
    cell = prepared.combo_cell
    alpha = scale[:, cell] * np.where(
        prepared.combo_group, 1.0 / prepared.cell_n1[cell], -1.0 / prepared.cell_n0[cell]
    )
    combo = sums.combo + effect * prepared.combo_n * prepared.combo_group
    centred = combo - prepared.combo_n * stats.mean[:, cell]
    out: Floats = np.add.reduceat(alpha * centred, prepared.cluster_starts, axis=1)
    return out


def _probability(prepared: Prepared, sums: _Sums, effect: float, blocked: bool) -> Floats:
    if len(prepared.weight) == 0:
        return np.zeros(sums.free.shape[0])
    stats = _stats(prepared, sums, effect)
    if blocked:
        flips = _possession_sums(prepared, sums, stats, effect)
        z = stats.pooled / np.sqrt((flips * flips).sum(axis=1))
    else:
        z = stats.pooled * math.sqrt(float(prepared.weight.sum()))
    out: Floats = stats.agrees * pass_probability(z)
    return out


def pass_probability(z: Floats) -> Floats:
    """P(count <= BAR_COUNT_AT_MOST) for a count Binomial(N_PERMUTATIONS, 2 Phi(-|z|)).

    The chance that the permutation part of the bar passes on a data set whose standardised
    pooled effect is ``z``, by the normal approximation of the null.
    """
    flat = np.ravel(np.asarray(z, dtype=np.float64))
    q = np.array([math.erfc(abs(float(v)) / math.sqrt(2.0)) for v in flat])
    q = np.clip(q, 1e-300, 1.0)
    n = N_PERMUTATIONS
    with np.errstate(divide="ignore"):
        log_q, log_rest = np.log(q), np.log1p(-q)
    total = np.zeros_like(q)
    for c in range(BAR_COUNT_AT_MOST + 1):
        total += np.exp(math.log(math.comb(n, c)) + c * log_q + (n - c) * log_rest)
    probability: Floats = np.clip(total, 0.0, 1.0).reshape(np.shape(z))
    return probability


def bar_probability(prepared: Prepared, noise: Floats, effect: float, blocked: bool) -> Floats:
    """Per replicate: the sign condition times the pass probability of the permutation part."""
    return _probability(prepared, _sums(prepared, noise), effect, blocked)


def null_draws(
    prepared: Prepared, blocked: bool, rng: np.random.Generator, draws: int = N_PERMUTATIONS
) -> NDArray[np.generic]:
    """The protocol's null draws for the full permutation of :func:`full_passes`.

    Unblocked: ``draws`` permutations of the cause label inside each cell, as the groups of the
    units in ``by_cell`` order (rows of booleans). Blocked: ``draws`` rows of signs, one per
    team possession.
    """
    if blocked:
        signs: NDArray[np.generic] = (
            rng.integers(0, 2, size=(draws, len(prepared.cluster_match))) * 2 - 1
        ).astype(np.float64)
        return signs
    keys = rng.random((draws, len(prepared.by_cell))) + 2.0 * prepared.by_cell_cell
    order = np.argsort(keys, axis=1, kind="stable")
    labels: NDArray[np.generic] = prepared.unit_group[prepared.by_cell][order]
    return labels


def full_passes(
    prepared: Prepared,
    noise: Floats,
    effect: float,
    blocked: bool,
    draws: NDArray[np.generic],
) -> Bools:
    """Per replicate, whether the bar passes with the permutation p counted over ``draws``."""
    if len(prepared.weight) == 0:
        return np.zeros(noise.shape[0], dtype=np.bool_)
    sums = _sums(prepared, noise)
    stats = _stats(prepared, sums, effect)
    if blocked:
        flips = _possession_sums(prepared, sums, stats, effect)
        null = flips @ np.asarray(draws, dtype=np.float64).T
    else:
        labels = np.asarray(draws, dtype=np.bool_)
        cell = prepared.by_cell_cell
        share = prepared.weight[cell] / prepared.weight.sum()
        coefficients = share * np.where(
            labels, 1.0 / prepared.cell_n1[cell], -1.0 / prepared.cell_n0[cell]
        )
        y = noise + effect * prepared.unit_group
        null = (y[:, prepared.by_cell] / stats.sd[:, cell]) @ coefficients.T
    count = (np.abs(null) >= np.abs(stats.pooled)[:, None]).sum(axis=1)
    passes: Bools = stats.agrees & (count <= BAR_COUNT_AT_MOST)
    return passes


# --- the power ---------------------------------------------------------------------------------


def pass_rates(
    design: Design,
    rho_by_match: Sequence[float],
    blocked: bool,
    effects: Sequence[float],
    seed: Sequence[int],
    replicates: int = POWER_REPLICATES,
) -> tuple[float, ...]:
    """The bar's pass rate at each effect (sd), over ``replicates`` simulated data sets.

    The noise comes from ``numpy.random.default_rng(seed)`` in chunks of :data:`CHUNK`
    replicates and is shared by every effect, so two calls with one seed see the same data.
    """
    prepared = prepare(design)
    rng = np.random.default_rng(list(seed))
    total = np.zeros(len(effects))
    done = 0
    while done < replicates:
        r = min(CHUNK, replicates - done)
        sums = _sums(prepared, draw_noise(prepared, rho_by_match, r, rng))
        for j, effect in enumerate(effects):
            total[j] += float(_probability(prepared, sums, effect, blocked).sum())
        done += r
    return tuple(float(v) for v in total / replicates)


def mde80(
    design: Design,
    rho_by_match: Sequence[float],
    blocked: bool,
    seed: Sequence[int],
    replicates: int = POWER_REPLICATES,
) -> Power:
    """The pass-rate curve on the coarse grid and the MDE80, refined on the fine grid.

    The MDE80 is the smallest effect whose pass rate reaches :data:`POWER_TARGET`, looked for on
    the coarse grid (0 to :data:`MAX_EFFECT` by :data:`COARSE_STEP`) and then by
    :data:`FINE_STEP` inside the coarse step that brackets it, with the same simulated data.
    ``None`` when no effect of the grid reaches it.
    """
    steps = round(MAX_EFFECT / COARSE_STEP)
    coarse = [round(COARSE_STEP * i, 2) for i in range(steps + 1)]
    rates = pass_rates(design, rho_by_match, blocked, coarse, seed, replicates)
    first = next((i for i, rate in enumerate(rates) if rate >= POWER_TARGET), None)
    effects, curve = list(coarse), list(rates)
    mde: float | None = None
    if first is not None:
        mde = coarse[first]
        if first > 0:
            per_step = round(COARSE_STEP / FINE_STEP)
            fine = [round(coarse[first - 1] + FINE_STEP * k, 2) for k in range(1, per_step)]
            fine_rates = pass_rates(design, rho_by_match, blocked, fine, seed, replicates)
            mde = next(
                (e for e, rate in zip(fine, fine_rates, strict=True) if rate >= POWER_TARGET),
                mde,
            )
            effects += fine
            curve += fine_rates
    pairs = sorted(zip(effects, curve, strict=True))
    return Power(
        effects=tuple(e for e, _ in pairs),
        pass_rate=tuple(r for _, r in pairs),
        mde80=mde,
        replicates=replicates,
    )


# --- the within-possession correlation ---------------------------------------------------------


def within_possession_correlation(
    values: Sequence[float], strata: Sequence[str], possessions: Sequence[str]
) -> Correlation:
    """The pairwise correlation of ``values`` between two units of one team possession.

    Each value is standardised inside its stratum (minus the stratum's mean, over its sample
    sd); a stratum of one unit or with sd 0 is left out. Then, over every pair of units that
    share a possession, the mean product of the two standardised values over their mean square.
    Give the units of one match.
    """
    v = np.asarray(values, dtype=np.float64)
    if not (len(v) == len(strata) == len(possessions)):
        raise ValueError("every value needs a stratum and a possession")
    cell = _codes(list(strata))
    keep = np.zeros(len(v), dtype=np.bool_)
    e = np.zeros(len(v))
    for c in range(int(cell.max()) + 1 if len(v) else 0):
        mask = cell == c
        if mask.sum() < 2:
            continue
        sd = float(np.std(v[mask], ddof=1))
        if sd <= 0:
            continue
        e[mask] = (v[mask] - v[mask].mean()) / sd
        keep |= mask
    e = e[keep]
    cluster = _codes([p for p, k in zip(possessions, keep.tolist(), strict=True) if k])
    if len(e) == 0:
        return Correlation(None, 0, 0, 0)
    sums = np.bincount(cluster, weights=e)
    squares = np.bincount(cluster, weights=e * e)
    size = np.bincount(cluster)
    cross = float(((sums * sums - squares) / 2.0).sum())
    pairs = int((size * (size - 1) // 2).sum())
    mean_square = float((e * e).mean())
    rho = cross / (pairs * mean_square) if pairs and mean_square > 0 else None
    return Correlation(rho, pairs, len(e), int((size >= 2).sum()))
