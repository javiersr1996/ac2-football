"""The estimator of the protocol: outcome, adjusted effect, pre-trend, null, bars and criteria.

Task 20 (``protocol/protocol.json``). The design of a half (:mod:`ac2fb.defence.design`) reads
everything at ``t`` or before it; this module is the first that reads after ``t``, and only in
:func:`read_outcome`, the one reader of the outcome. Everything else takes
:class:`EffectUnit`\\ s, plain data, so the estimator is a pure function of the units of a half
and nothing here opens a file. It was validated on synthetic worlds (``tests/test_effect.py``)
before it touched a real match; the code that judges the calibration half is the code that
judges the held-out half.

**Outcome** (protocol ``outcome``). ``y = sign * (ball_x(t + W) - ball_x(t))`` in metres, the
ball rows listed at ``t`` and ``t + W`` whatever their ``is_detected`` flag; ``None`` without a
row at either end or with the two in different periods (:func:`read_outcome`). Whether the ball
is detected at both ends travels with it (``ball_detected``): the effect on those units,
:data:`BALL_DETECTED`, is reported beside V0 and decides nothing. :func:`effect_units` joins the
kept units of the design with their outcome.

**Variants** (protocol ``variants``; :func:`select_units`). V0 every unit; V1 the units with no
extrapolated player among the carrier and the near rivals at ``t``; V2 the classes
:data:`V2_CLASSES` of that count (:func:`v2_effects`), whose ``|T|`` should shrink as it grows.

**The statistic** (protocol ``statistic``; :func:`estimate`). A *cell* is a (match, stratum) of
one half and one variant with at least :data:`~ac2fb.defence.bar.MIN_CELL` pressed and as many
free units that have both ``y`` and the pre statistic ``x``, and a positive sample sd of ``y``.
In a cell, with ``G`` 1 for pressed and 0 for free, ``tau_c`` is the least-squares coefficient
of ``G`` in ``y = a + b x + tau G``. With the cell's centred sums ``Sxx, Sgg, Sgx, Sxy, Sgy``
(``Sgg = n_p n_f / n``) the normal equations are two, and

    det = Sxx Sgg - Sgx^2,  tau = (Sxx Sgy - Sgx Sxy) / det,  b = (Sgg Sxy - Sgx Sgy) / det.

If ``x`` is constant in the cell, ``b = 0`` and ``tau = Sgy / Sgg``, the plain difference of
means. ``z_c = tau_c / s_c`` with ``s_c`` the sample sd (ddof 1) of ``y`` in the cell,
``w_c = n_p n_f / (n_p + n_f)``. ``E_m`` is the ``w``-weighted mean of ``z_c`` over the cells of
match ``m`` (``None`` for a match without a cell: it never agrees in sign), ``T`` the same mean
over every cell. Units left out are counted per match and group, by reason: ``no_outcome``,
``no_pre``, ``small_cell``, ``flat_outcome`` and ``collinear_cell``.

**The pre-trend** (protocol ``pretrend``). ``P_c`` is the mean of ``x`` over the pressed units
minus the mean over the free ones, over the sample sd of ``x`` in the cell; a cell with that sd
zero is left out of ``P`` (it stays in ``T``). ``P`` pools the ``P_c`` with the weights of the
effect, per match too; ``pretrend_m`` is the same pooling of the unstandardised differences, in
metres, over the same cells. D3 (:func:`d3`) kills when ``|P| >= D3_RATIO |T|`` in V0.

**The null** (protocol ``null``; :func:`null_effects`). The pressed labels of each cell are
permuted at random among its units, ``x`` and ``y`` staying with their unit, and ``tau_c``,
``z_c``, ``E_m`` and ``T`` are recomputed on every draw, in closed form and for all the draws of
a chunk at once: only ``Sgx`` and ``Sgy`` depend on the labels (``Sxx, Sxy, Sgg`` do not), and
each is a sum of ``G`` times a centred value per cell. The stream is
``default_rng([SEED, crc32(f"{half}/{variant}")])``, one per half and variant, drawn once; the
units of a half are put in the order (match, stratum, period, frame) first, so the draws do not
depend on the order the caller lists them in. The two-sided ``p`` is
``(1 + #{|T*| >= |T|}) / (1 + draws)`` (:func:`p_value`); a draw counts when it is within
:data:`TIE` of ``|T|`` from below, so that a draw that reproduces the observed labels is not
lost to the last bit of a sum.

*Blocked by team possession* (when the protocol says so, :func:`null_effects` with
``blocked=True``). In a cell, ``tau`` is linear in ``y``: ``tau_c = sum_i a_i (y_i - ybar_c)``
with ``a`` the ``G`` row of ``(X'X)^-1 X'`` for ``X = [1, x, G]``, that is
``a_i = (Sxx gc_i - Sgx xc_i) / det`` (``gc, xc`` centred; ``a_i = gc_i / Sgg`` when ``x`` is
constant). The weights of ``T`` are fixed by the units, so ``T = sum_i c_i`` with
``c_i = (w_c / sum w) a_i (y_i - ybar_c) / s_c``. The contributions of the units of one team
possession add to ``S_k`` (:func:`possession_contributions`), the ``S_k`` add to ``T``, and the
null flips the sign of each ``S_k`` at random on every draw (``T* = sum_k e_k S_k``, ``e_k`` of
+1 or -1), so the units of one possession never move apart: the flip null of
:mod:`ac2fb.defence.bar`, here for the adjusted statistic. ``E_m`` flips the same way with the
weights of its match.

**The bars and criteria** (protocol ``bars``, ``death_criteria``), pure functions of the
results. :func:`calibration_bar`: ``T`` has the sign of ``E_m`` in at least
:data:`~ac2fb.defence.bar.BAR_SAME_SIGN` matches (``T = 0`` never passes) and ``p`` is at most
:data:`~ac2fb.defence.bar.BAR_P`. :func:`heldout_bars`: the same sign condition and Holm over
{V0, V1} at :data:`HELDOUT_ALPHA` (:func:`holm`). :func:`d3` and :func:`d4` kill on the
protocol's rule. A criterion that cannot be evaluated (no cell) kills: nothing is shown to
survive.
"""

from __future__ import annotations

import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ac2fb.defence import bar, power
from ac2fb.defence.design import DesignUnit
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.reliability.match import MatchData

__all__ = [
    "BALL_DETECTED",
    "D4_RATIO",
    "HALVES",
    "HELDOUT_ALPHA",
    "LEFT_OUT_REASONS",
    "SEED",
    "V2_CLASSES",
    "VARIANTS",
    "Bar",
    "Cell",
    "Criterion",
    "Effect",
    "EffectUnit",
    "MatchEffect",
    "Null",
    "Outcome",
    "Result",
    "V2Effects",
    "calibration_bar",
    "d3",
    "d4",
    "effect_units",
    "estimate",
    "extreme_draws",
    "heldout_bars",
    "holm",
    "null_effects",
    "p_value",
    "permutation_test",
    "possession_contributions",
    "read_outcome",
    "select_units",
    "sign_agreement",
    "v2_effects",
]

SEED = 19  # protocol null.seed
HELDOUT_ALPHA = 0.01  # protocol bars.heldout.alpha: the level of the Holm family
D4_RATIO = 0.5  # protocol death_criteria.D4.ratio: V1 keeps at least this share of V0's effect
HALVES: tuple[str, ...] = ("calibration", "heldout")
VARIANTS: tuple[str, ...] = power.VARIANTS  # the variants with a null and a p: V0 and V1
BALL_DETECTED = "V0_ball_detected"  # V0 on the units with the ball detected at both ends
V2_CLASSES: tuple[str, ...] = ("0", "1", "2_or_more")  # extrapolated players, as in design.py
LEFT_OUT_REASONS: tuple[str, ...] = (
    "no_outcome",
    "no_pre",
    "small_cell",
    "flat_outcome",
    "collinear_cell",
)
TIE = 1e-9  # a null draw this close below |T| still counts as equal to it (float noise)
COLLINEAR = 1e-12  # 1 - r^2 of x and G in a cell below this: tau is not identified
CHUNK = 250  # null draws handled at once (rows of the same random stream, so not a parameter)

Floats = NDArray[np.float64]
Ints = NDArray[np.int64]


@dataclass(frozen=True)
class Outcome:
    """The ball's advance over ``[t, t + W]`` and whether the ball is detected at both ends."""

    advance: float
    ball_detected: bool


@dataclass(frozen=True)
class EffectUnit:
    """One kept unit of the design with its outcome: all the estimator reads.

    ``pre`` is ``x``, ``outcome`` is ``y`` (``None`` when undefined), ``ball_detected`` is
    ``None`` without an outcome, ``extrapolated_players`` the carrier and near rivals not
    detected at ``t``. ``possession`` is read inside its match only.
    """

    match: int
    period: int
    frame: int
    stratum: str
    pressed: bool
    possession: str
    pre: float | None
    outcome: float | None
    extrapolated_players: int
    ball_detected: bool | None


@dataclass(frozen=True)
class Cell:
    """One (match, stratum) cell of the statistic, as the protocol asks them reported.

    ``x_diff`` is the pressed minus free mean of ``x`` in metres and ``pretrend`` that over
    ``sd_x`` (``None`` when ``x`` is constant in the cell).
    """

    match: int
    stratum: str
    n_pressed: int
    n_free: int
    tau: float
    b: float
    s: float
    z: float
    w: float
    sd_x: float
    x_diff: float
    pretrend: float | None


@dataclass(frozen=True)
class MatchEffect:
    """A match: ``effect`` is ``E_m`` (``None`` without a cell), its pre-trend, counts."""

    match: int
    effect: float | None
    pretrend: float | None
    pretrend_m: float | None
    cells: int
    units: int
    used: int
    left_out: dict[str, dict[str, int]]


@dataclass(frozen=True)
class Effect:
    """The statistic on the units of one half and variant.

    ``t`` is ``T`` and ``weight`` the sum of the cell weights (``None`` and 0 without a cell);
    ``pretrend`` is ``P`` in sd and ``pretrend_m`` in metres; ``left_out`` maps each reason of
    :data:`LEFT_OUT_REASONS` to the units left out, by group (``pressed`` and ``free``).
    """

    t: float | None
    weight: float
    pretrend: float | None
    pretrend_m: float | None
    cells: tuple[Cell, ...]
    matches: dict[int, MatchEffect]
    units: int
    used: int
    left_out: dict[str, dict[str, int]]


@dataclass(frozen=True)
class Null:
    """The null draws: ``pooled`` is ``T*`` per draw, ``match[:, j]`` the ``E*`` of match j."""

    matches: tuple[int, ...]
    pooled: Floats
    match: Floats


@dataclass(frozen=True)
class Result:
    """A permutation test: the effect, the count of draws as extreme as ``T`` and ``p``.

    ``p`` and ``extreme`` are ``None`` when there is no cell (no ``T`` to test).
    """

    half: str
    variant: str
    blocked: bool
    draws: int
    effect: Effect
    extreme: int | None
    p: float | None


@dataclass(frozen=True)
class Bar:
    """A bar on one variant: matches agreeing in sign, the p condition, and the verdict."""

    variant: str
    agreeing: int
    matches: int
    sign_ok: bool
    p: float | None
    p_ok: bool
    passed: bool


@dataclass(frozen=True)
class Criterion:
    """A death criterion: ``kills`` it, whether it could be ``evaluable``, and its figures."""

    name: str
    kills: bool
    evaluable: bool
    values: dict[str, float | None]


@dataclass(frozen=True)
class V2Effects:
    """The effect in each class of extrapolated players, and whether ``|T|`` shrinks.

    ``shrinks`` is true when ``|T|`` falls strictly from each class to the next among the
    classes that have a cell, false when it does not, ``None`` with fewer than two classes.
    """

    classes: dict[str, Effect]
    abs_effect: dict[str, float | None]
    shrinks: bool | None


# --- the outcome and the units -----------------------------------------------------------------


def _ball_row(match: MatchData, frame: int) -> int:
    pos = int(np.searchsorted(match.ball_frame, frame))
    return pos if pos < len(match.ball_frame) and match.ball_frame[pos] == frame else -1


def read_outcome(match: MatchData, frame: int, sign: int) -> Outcome | None:
    """The ball's advance along the attack (``sign``) from ``frame`` to ``frame + W``.

    The ball rows listed at both frames, detected or not; ``None`` without a row at either
    (the provider lists no ball there) or with the two rows in different periods (the period
    ends before ``frame + W``: the break between periods can be shorter than ``W``). This is
    the only function of the package that reads after ``t``.
    """
    now, end = _ball_row(match, frame), _ball_row(match, frame + W)
    if now < 0 or end < 0 or match.ball_period[now] != match.ball_period[end]:
        return None
    return Outcome(
        advance=sign * float(match.ball_x[end] - match.ball_x[now]),
        ball_detected=bool(match.ball_detected[now] and match.ball_detected[end]),
    )


def effect_units(units: Sequence[DesignUnit], match: MatchData) -> list[EffectUnit]:
    """The kept units of a match (not excluded by the window overlap) with their outcome."""
    out: list[EffectUnit] = []
    for u in units:
        if u.excluded:
            continue
        read = read_outcome(match, u.frame, match.attack_sign[(u.period, u.team)])
        out.append(
            EffectUnit(
                match=match.match_id,
                period=u.period,
                frame=u.frame,
                stratum=u.stratum,
                pressed=u.pressed,
                possession=u.possession,
                pre=u.pre,
                outcome=None if read is None else read.advance,
                extrapolated_players=u.extrapolated_players,
                ball_detected=None if read is None else read.ball_detected,
            )
        )
    return out


def select_units(units: Sequence[EffectUnit], variant: str) -> list[EffectUnit]:
    """The units of a variant: V0 all, V1 none extrapolated, V0 with the ball detected both ends."""
    if variant == "V0":
        return list(units)
    if variant == "V1":
        return [u for u in units if u.extrapolated_players == 0]
    if variant == BALL_DETECTED:
        return [u for u in units if u.ball_detected]
    raise ValueError(f"unknown variant {variant!r}: one of {(*VARIANTS, BALL_DETECTED)}")


def _v2_class(count: int) -> str:
    return V2_CLASSES[min(count, 2)]


# --- the statistic -----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Prepared:
    """The units of the cells that enter the statistic, ordered by cell, with the cell sums.

    Per unit: ``x``, ``xc``, ``yc`` (centred in the cell), ``g`` (1 pressed), ``cell`` and
    ``cluster`` (match and team possession). Per cell: size, groups, weight, ``Sxx``, ``Sxy``,
    ``Sgg``, ``s``, whether ``x`` is constant and its ``sd``. ``starts`` are the first unit of
    each cell, ``match_starts`` the first cell of each match that has cells.
    """

    matches: tuple[int, ...]
    cell_keys: tuple[tuple[int, str], ...]
    starts: Ints
    cell: Ints
    cluster: Ints
    cluster_keys: tuple[tuple[int, str], ...]
    x: Floats
    xc: Floats
    yc: Floats
    g: Floats
    n: Floats
    n_p: Floats
    n_f: Floats
    w: Floats
    sxx: Floats
    sxy: Floats
    sgg: Floats
    s: Floats
    flat_x: NDArray[np.bool_]
    sd_x: Floats
    match_ids: tuple[int, ...]
    match_starts: Ints
    cell_match: Ints
    left_out: dict[int, dict[str, dict[str, int]]]
    unit_counts: dict[int, int]


def _empty_left() -> dict[str, dict[str, int]]:
    return {r: {"pressed": 0, "free": 0} for r in LEFT_OUT_REASONS}


def _count(left: dict[int, dict[str, dict[str, int]]], u: EffectUnit, reason: str) -> None:
    left[u.match][reason]["pressed" if u.pressed else "free"] += 1


def _prepare(units: Sequence[EffectUnit]) -> _Prepared:
    ordered = sorted(units, key=lambda u: (u.match, u.stratum, u.period, u.frame))
    matches = tuple(sorted({u.match for u in units}))
    left = {m: _empty_left() for m in matches}
    unit_counts = dict.fromkeys(matches, 0)
    groups: dict[tuple[int, str], list[EffectUnit]] = {}
    for u in ordered:
        unit_counts[u.match] += 1
        if u.outcome is None:
            _count(left, u, "no_outcome")
        elif u.pre is None:
            _count(left, u, "no_pre")
        else:
            groups.setdefault((u.match, u.stratum), []).append(u)
    keys: list[tuple[int, str]] = []
    cols: dict[str, list[Floats]] = {k: [] for k in ("x", "xc", "yc", "g")}
    scalar: dict[str, list[float]] = {
        k: [] for k in ("n", "n_p", "n_f", "w", "sxx", "sxy", "sgg", "s", "sd_x")
    }
    flats: list[bool] = []
    used_units: list[EffectUnit] = []
    cell_of: list[int] = []
    for key, us in groups.items():
        g = np.array([u.pressed for u in us], dtype=np.float64)
        y = np.array([u.outcome for u in us], dtype=np.float64)
        x = np.array([u.pre for u in us], dtype=np.float64)
        n, n_p = float(len(us)), float(g.sum())
        n_f = n - n_p
        reason = None
        if n_p < bar.MIN_CELL or n_f < bar.MIN_CELL:
            reason = "small_cell"
        elif float(np.ptp(y)) == 0.0:
            reason = "flat_outcome"
        xc, yc, gc = x - x.mean(), y - y.mean(), g - n_p / n
        sxx, sgg, sgx = float(xc @ xc), n_p * n_f / n, float(gc @ xc)
        flat = float(np.ptp(x)) == 0.0
        if reason is None and not flat and sxx * sgg - sgx * sgx <= COLLINEAR * sxx * sgg:
            reason = "collinear_cell"
        if reason is not None:
            for u in us:
                _count(left, u, reason)
            continue
        cols["x"].append(x)
        cols["xc"].append(xc)
        cols["yc"].append(yc)
        cols["g"].append(g)
        for name, value in (
            ("n", n),
            ("n_p", n_p),
            ("n_f", n_f),
            ("w", n_p * n_f / n),
            ("sxx", 0.0 if flat else sxx),
            ("sxy", float(xc @ yc)),
            ("sgg", sgg),
            ("s", float(np.std(y, ddof=1))),
            ("sd_x", float(np.std(x, ddof=1))),
        ):
            scalar[name].append(value)
        flats.append(flat)
        keys.append(key)
        used_units.extend(us)
        cell_of.extend([len(keys) - 1] * len(us))

    def cat(name: str) -> Floats:
        return np.concatenate(cols[name]) if cols[name] else np.zeros(0)

    def per(name: str) -> Floats:
        return np.array(scalar[name], dtype=np.float64)

    cell = np.array(cell_of, dtype=np.int64)
    sizes = per("n").astype(np.int64)
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int64) if len(keys) else cell
    cluster_index: dict[tuple[int, str], int] = {}
    cluster = np.array(
        [cluster_index.setdefault((u.match, u.possession), len(cluster_index)) for u in used_units],
        dtype=np.int64,
    )
    match_ids = tuple(sorted({k[0] for k in keys}))
    cell_match = np.array([match_ids.index(k[0]) for k in keys], dtype=np.int64)
    match_starts = (
        np.flatnonzero(np.r_[True, cell_match[1:] != cell_match[:-1]]).astype(np.int64)
        if len(keys)
        else cell
    )
    return _Prepared(
        matches=matches,
        cell_keys=tuple(keys),
        starts=starts,
        cell=cell,
        cluster=cluster,
        cluster_keys=tuple(cluster_index),
        x=cat("x"),
        xc=cat("xc"),
        yc=cat("yc"),
        g=cat("g"),
        n=per("n"),
        n_p=per("n_p"),
        n_f=per("n_f"),
        w=per("w"),
        sxx=per("sxx"),
        sxy=per("sxy"),
        sgg=per("sgg"),
        s=per("s"),
        flat_x=np.array(flats, dtype=np.bool_),
        sd_x=per("sd_x"),
        match_ids=match_ids,
        match_starts=match_starts,
        cell_match=cell_match,
        left_out=left,
        unit_counts=unit_counts,
    )


def _fit(p: _Prepared, labels: Floats) -> tuple[Floats, Floats, Floats]:
    """``tau``, ``b`` and ``Sgx`` per draw (rows of ``labels``) and cell, in closed form."""
    sgx = np.add.reduceat(labels * p.xc, p.starts, axis=1)
    sgy = np.add.reduceat(labels * p.yc, p.starts, axis=1)
    det = p.sxx * p.sgg - sgx * sgx
    ok = ~p.flat_x & (det > COLLINEAR * p.sxx * p.sgg)
    safe = np.where(ok, det, 1.0)
    adjusted = (p.sxx * sgy - sgx * p.sxy) / safe
    slope = (p.sgg * p.sxy - sgx * sgy) / safe
    tau = np.where(p.flat_x, sgy / p.sgg, np.where(ok, adjusted, 0.0))
    b = np.where(p.flat_x, 0.0, np.where(ok, slope, 0.0))
    return tau, b, sgx


def _pool(p: _Prepared, tau: Floats) -> tuple[Floats, Floats]:
    """``T`` per draw and ``E_m`` per draw and match with cells, from ``tau`` per draw and cell."""
    wz = p.w * tau / p.s
    pooled: Floats = wz.sum(axis=1) / p.w.sum()
    by_match = np.add.reduceat(wz, p.match_starts, axis=1) / np.add.reduceat(p.w, p.match_starts)
    return pooled, by_match


def _weighted(values: Floats, weights: Floats, mask: NDArray[np.bool_]) -> float | None:
    total = float(weights[mask].sum())
    return float((weights[mask] * values[mask]).sum() / total) if total > 0 else None


def estimate(units: Sequence[EffectUnit]) -> Effect:
    """The statistic on the given units (one half, already restricted to the variant)."""
    p = _prepare(units)
    left: dict[str, dict[str, int]] = _empty_left()
    for per_match in p.left_out.values():
        for reason, groups in per_match.items():
            for group, count in groups.items():
                left[reason][group] += count
    match_effects: dict[int, MatchEffect] = {}
    if len(p.cell_keys) == 0:
        for m in p.matches:
            match_effects[m] = MatchEffect(
                m, None, None, None, 0, p.unit_counts[m], 0, p.left_out[m]
            )
        return Effect(None, 0.0, None, None, (), match_effects, len(units), 0, left)
    tau, b, sgx = _fit(p, p.g[None, :])
    pooled, by_match = _pool(p, tau)
    tau, b, sgx = tau[0], b[0], sgx[0]
    z = tau / p.s
    x_diff = sgx * (1.0 / p.n_p + 1.0 / p.n_f)  # mean of xc over pressed minus over free
    pre = np.where(p.flat_x, 0.0, x_diff / np.where(p.flat_x, 1.0, p.sd_x))
    has_pre = ~p.flat_x
    cells = tuple(
        Cell(
            match=p.cell_keys[c][0],
            stratum=p.cell_keys[c][1],
            n_pressed=int(p.n_p[c]),
            n_free=int(p.n_f[c]),
            tau=float(tau[c]),
            b=float(b[c]),
            s=float(p.s[c]),
            z=float(z[c]),
            w=float(p.w[c]),
            sd_x=float(p.sd_x[c]),
            x_diff=float(x_diff[c]),
            pretrend=float(pre[c]) if has_pre[c] else None,
        )
        for c in range(len(p.cell_keys))
    )
    for m in p.matches:
        if m not in p.match_ids:
            match_effects[m] = MatchEffect(
                m, None, None, None, 0, p.unit_counts[m], 0, p.left_out[m]
            )
            continue
        j = p.match_ids.index(m)
        mine = p.cell_match == j
        match_effects[m] = MatchEffect(
            match=m,
            effect=float(by_match[0, j]),
            pretrend=_weighted(pre, p.w, mine & has_pre),
            pretrend_m=_weighted(x_diff, p.w, mine & has_pre),
            cells=int(mine.sum()),
            units=p.unit_counts[m],
            used=int(p.n[mine].sum()),
            left_out=p.left_out[m],
        )
    return Effect(
        t=float(pooled[0]),
        weight=float(p.w.sum()),
        pretrend=_weighted(pre, p.w, has_pre),
        pretrend_m=_weighted(x_diff, p.w, has_pre),
        cells=cells,
        matches=match_effects,
        units=len(units),
        used=int(p.n.sum()),
        left_out=left,
    )


# --- the null ----------------------------------------------------------------------------------


def _stream(half: str, variant: str) -> np.random.Generator:
    if half not in HALVES:
        raise ValueError(f"unknown half {half!r}: one of {HALVES}")
    if variant not in VARIANTS:
        raise ValueError(f"no null for variant {variant!r}: one of {VARIANTS}")
    return np.random.default_rng([SEED, zlib.crc32(f"{half}/{variant}".encode())])


def _contributions(p: _Prepared) -> Floats:
    """``c_i``: the share of ``T`` that unit ``i`` carries (they add to ``T``)."""
    cell = p.cell
    sgx = np.add.reduceat(p.g * p.xc, p.starts)
    det = p.sxx * p.sgg - sgx * sgx
    ok = ~p.flat_x & (det > COLLINEAR * p.sxx * p.sgg)
    gc = p.g - (p.n_p / p.n)[cell]
    adjusted = (p.sxx[cell] * gc - sgx[cell] * p.xc) / np.where(ok, det, 1.0)[cell]
    a = np.where(p.flat_x[cell], gc / p.sgg[cell], np.where(ok[cell], adjusted, 0.0))
    out: Floats = (p.w / p.w.sum() / p.s)[cell] * a * p.yc
    return out


def possession_contributions(units: Sequence[EffectUnit]) -> dict[tuple[int, str], float]:
    """``S_k``: the part of ``T`` each (match, team possession) carries; they add to ``T``."""
    p = _prepare(units)
    if len(p.cell_keys) == 0:
        return {}
    sums = np.bincount(p.cluster, weights=_contributions(p), minlength=len(p.cluster_keys))
    return {key: float(s) for key, s in zip(p.cluster_keys, sums, strict=True)}


def null_effects(
    units: Sequence[EffectUnit],
    half: str,
    variant: str,
    blocked: bool = False,
    draws: int = bar.N_PERMUTATIONS,
) -> Null:
    """``draws`` draws of ``T*`` and ``E*_m`` for ``variant`` of the units of ``half``.

    ``units`` are the kept units of the half; the variant is selected here. Unblocked: labels
    permuted inside each cell. Blocked: the sign of each possession's contribution flipped.
    """
    rng = _stream(half, variant)
    p = _prepare(select_units(units, variant))
    if len(p.cell_keys) == 0:
        return Null((), np.zeros(0), np.zeros((0, 0)))
    if blocked:
        sums = np.bincount(p.cluster, weights=_contributions(p), minlength=len(p.cluster_keys))
        cluster_match = np.array([p.match_ids.index(k[0]) for k in p.cluster_keys], dtype=np.int64)
        match_weight = np.add.reduceat(p.w, p.match_starts)
        onehot = np.zeros((len(sums), len(p.match_ids)))
        onehot[np.arange(len(sums)), cluster_match] = sums * p.w.sum() / match_weight[cluster_match]
        signs = (rng.integers(0, 2, size=(draws, len(sums))) * 2 - 1).astype(np.float64)
        return Null(p.match_ids, signs @ sums, signs @ onehot)
    pooled = np.zeros(draws)
    by_match = np.zeros((draws, len(p.match_ids)))
    for lo in range(0, draws, CHUNK):
        rows = min(CHUNK, draws - lo)
        keys = rng.random((rows, len(p.g))) + 2.0 * p.cell
        labels = p.g[np.argsort(keys, axis=1)]
        tau, _, _ = _fit(p, labels)
        pooled[lo : lo + rows], by_match[lo : lo + rows] = _pool(p, tau)
    return Null(p.match_ids, pooled, by_match)


def extreme_draws(observed: float, pooled: Floats) -> int:
    """How many null draws are as extreme as ``observed`` in absolute value (within :data:`TIE`)."""
    return int((np.abs(pooled) >= abs(observed) - TIE).sum())


def p_value(observed: float, pooled: Floats) -> float:
    """The two-sided permutation p, ``(1 + #{|T*| >= |T|}) / (1 + draws)``."""
    return (1 + extreme_draws(observed, pooled)) / (1 + len(pooled))


def permutation_test(
    units: Sequence[EffectUnit],
    half: str,
    variant: str,
    blocked: bool = False,
    draws: int = bar.N_PERMUTATIONS,
) -> Result:
    """The effect of ``variant`` on the kept units of ``half`` and its permutation p."""
    effect = estimate(select_units(units, variant))
    null = null_effects(units, half, variant, blocked, draws)
    if effect.t is None:
        return Result(half, variant, blocked, draws, effect, None, None)
    return Result(
        half,
        variant,
        blocked,
        draws,
        effect,
        extreme_draws(effect.t, null.pooled),
        p_value(effect.t, null.pooled),
    )


# --- the bars and the criteria -----------------------------------------------------------------


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def sign_agreement(effect: Effect) -> int:
    """Matches whose ``E_m`` has the sign of ``T``; none when ``T`` is 0 or absent."""
    if effect.t is None or effect.t == 0.0:
        return 0
    return sum(
        m.effect is not None and _sign(m.effect) == _sign(effect.t) for m in effect.matches.values()
    )


def _bar(result: Result, p_ok: bool) -> Bar:
    agreeing = sign_agreement(result.effect)
    sign_ok = agreeing >= bar.BAR_SAME_SIGN
    return Bar(
        variant=result.variant,
        agreeing=agreeing,
        matches=len(result.effect.matches),
        sign_ok=sign_ok,
        p=result.p,
        p_ok=p_ok,
        passed=sign_ok and p_ok,
    )


def calibration_bar(result: Result) -> Bar:
    """The calibration bar on one variant: sign in enough matches and ``p <= BAR_P``."""
    return _bar(result, result.p is not None and result.p <= bar.BAR_P)


def holm(p_values: Mapping[str, float | None], alpha: float) -> dict[str, bool]:
    """Holm's step-down: which hypotheses are rejected at ``alpha`` over the family.

    The ``i``-th smallest p (1-based) is compared with ``alpha / (m - i + 1)``, ``m`` the size
    of the family; the first that fails stops the procedure. A missing p is never rejected.
    """
    m = len(p_values)
    order = sorted(p_values, key=lambda k: (p_values[k] is None, p_values[k] or 0.0))
    rejected = dict.fromkeys(p_values, False)
    for i, key in enumerate(order):
        p = p_values[key]
        if p is None or p > alpha / (m - i):
            break
        rejected[key] = True
    return rejected


def heldout_bars(results: Mapping[str, Result]) -> dict[str, Bar]:
    """The held-out bar of V0 and V1 from one reading: sign in enough matches and Holm."""
    if set(results) != set(VARIANTS):
        raise ValueError(f"the Holm family is {VARIANTS}, got {sorted(results)}")
    rejected = holm({v: r.p for v, r in results.items()}, HELDOUT_ALPHA)
    return {v: _bar(results[v], rejected[v]) for v in VARIANTS}


def d3(v0: Effect) -> Criterion:
    """D3 kills when ``|P| >= D3_RATIO |T|`` in V0 (both in sd of their cell)."""
    t, pre = v0.t, v0.pretrend
    if t is None or pre is None:
        return Criterion("D3", True, False, {"pretrend": pre, "effect": t, "floor": None})
    kills = abs(pre) >= power.D3_RATIO * abs(t)
    return Criterion(
        "D3", kills, True, {"pretrend": pre, "effect": t, "floor": abs(pre) / power.D3_RATIO}
    )


def d4(v0: Effect, v1: Effect) -> Criterion:
    """D4 kills when V1's effect changes sign or falls below ``D4_RATIO`` of V0's."""
    t0, t1 = v0.t, v1.t
    if t0 is None or t1 is None:
        return Criterion("D4", True, False, {"t_v0": t0, "t_v1": t1})
    kills = _sign(t1) != _sign(t0) or abs(t1) < D4_RATIO * abs(t0)
    return Criterion("D4", kills, True, {"t_v0": t0, "t_v1": t1})


def v2_effects(units: Sequence[EffectUnit]) -> V2Effects:
    """The effect in each class of extrapolated players (0, 1, 2 or more) and whether it shrinks."""
    classes = {
        c: estimate([u for u in units if _v2_class(u.extrapolated_players) == c])
        for c in V2_CLASSES
    }
    abs_effect = {c: None if e.t is None else abs(e.t) for c, e in classes.items()}
    present = [v for v in abs_effect.values() if v is not None]
    shrinks = (
        None
        if len(present) < 2
        else all(a > b for a, b in zip(present[:-1], present[1:], strict=True))
    )
    return V2Effects(classes, abs_effect, shrinks)
