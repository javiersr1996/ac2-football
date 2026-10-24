"""Power of the calibration bar for each candidate alive after its probe (task 17).

The power is simulated on the real design of each candidate in the calibration matches: its
units, their incoming-ball stratum, their cause group and their team possession, read at ``t``
or before it. Outcomes are simulated (:mod:`ac2fb.defence.bar`); no outcome of any candidate is
computed. The within-possession correlation that the simulated noise carries is measured on the
statistic **before** ``t``, over ``[t - W, t]``, through readers that only take a lag of 0 or more
(:func:`ball_advance`, :func:`block_before`): the outcome window ``(t, t + W]`` cannot be asked
for. Everything below was written before any power was computed.

**Which candidates.** The verdicts of the three probes, read by the command line from
``probe_s1.json``, ``probe_s2.json`` and ``probe_s3.json`` and passed in. A candidate that died
in its probe is not simulated.
C2's simulation is not written (it died in probe S2); if its verdict said it survived, this
module refuses to build the report rather than leave it out.

**C1** (units of probe S1: the labelled receptions with a defined incoming-ball stratum). Cause
group: *pressed*, a rival listed at ``t`` within :data:`~ac2fb.defence.line.PRESSED_RADIUS`
metres of the carrier (the proxy of m10 and probe S2; the protocol may refine the cause from the
index). Strata: the 18 incoming-ball strata of probe S1. Team possession: the base's
``possession_id`` of the ``player_possession`` event (the provider's first-of-team-possession
flag, and every period break). Statistic before ``t``: the ball's advance along the attack over
``[t - W, t]``. V1: every rival within 10 m of the carrier detected at ``t`` (probe S1's V1). The
pre-trend within stratum (pressed minus free of that statistic, in sd, pooled as in probe S2) is
reported per match: probe S1 did not measure it. Per variant, it is also pooled over every
(match, stratum) cell with the bar's weights (the plan's D3 takes it "pooled by stratum"), with
the effect D3 lets through: D3 kills when ``|pre-trend| >= D3_RATIO |effect|``, so the effect
must exceed ``|pre-trend| / D3_RATIO``; and with the count of matches over probe S2's bar for
a pre-trend, which C1's probe did not have. Per match, :func:`window_overlap` counts the units
whose instant falls in the outcome window of the unit before (design, not outcome: instants
only).

**C3** (phases of probe S3 whose block is measured at ``frame_start`` under the definition probe
S3 chose, :data:`C3_DEFINITION`). The plan does not fix C3's contrast; for the power it is the
block of a ``low_block`` phase against that of a ``high_block`` one
(``team_out_of_possession_phase_type``; *pressed* is the low block). Two outcomes, width and
length, each with its V1 (the players fixing its two ends detected at ``t``). Strata: the
incoming-ball strata with the ball in the place of the carrier (direction and length of the ball
over ``[t - W, t]`` along the attack of the team in possession, third of the ball at ``t``), and,
as a lower bound of the MDE, none. Team possession: a run of consecutive phases of one team in
possession inside a period. Statistic before ``t``: the same block measured at ``t - W``. No
pre-trend is computed for C3: its outcome is a level at ``t``, and the level at ``t - W`` is
nearly the outcome itself.

The low and the high block never share a third of the ball (:func:`phase_types_by_third`
counts the phase types by third), so inside the strata that contrast has no cell by
construction. :data:`C3_CONTIGUOUS` adds the two contrasts of neighbouring blocks that do share
one, each restricted to its third (the deeper block first): low against medium with the ball in
the middle third, medium against high with the ball in the own third of the team in
possession. Same strata, bar, correlation and null as the low against high contrast. Which
contrast C3 would use is CP1's choice; this module only gives each one's power.

**The correlation and the null.** Per match and variant,
:func:`ac2fb.defence.bar.within_possession_correlation` of the statistic before ``t`` over every
unit with it (for C3 every phase type, not only the two of the contrast). The noise of a match
carries the larger of 0, its V0 correlation and, for V1, its V1 correlation when that rests on
at least :data:`MIN_RHO_PAIRS` pairs. The bar's null is blocked by team possession when the
pooled V0 correlation (the mean of the matches' V0 correlations weighted by their pairs) exceeds
:data:`~ac2fb.defence.bar.BLOCK_RHO`: one number, as the protocol asks, and not the largest of
twenty estimates, which noise alone pushes over the threshold.

**The rule of CP1** (the plan's, applied in :func:`cp1_rule`): C2 first if it survived S2 and its
MDE80 in V1 is at most :data:`MDE_LIMIT`; otherwise C1 if alive; C3 only as a backup; none alive,
branch B. It recommends; CP1 decides. ``testable_v0`` lists every design simulated within the
strata (C1, and each contrast and outcome of C3).
"""

from __future__ import annotations

import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from ac2fb.defence import bar, line, pressure, probe_s1, probe_s2, probe_s3
from ac2fb.defence.block import DEFINITIONS, Block, Definition, measure, name_of
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.defence.pressure import Reception
from ac2fb.defence.probe_s3 import Phase
from ac2fb.protocol import data
from ac2fb.reliability.match import MatchData, locate_rows, players_at
from ac2fb.reliability.report import JsonCheck, check_json, render_report
from ac2fb.reliability.visibility import goalkeepers

__all__ = [
    "C3_CONTIGUOUS",
    "C3_CONTRAST",
    "C3_DEFINITION",
    "D3_RATIO",
    "MDE_LIMIT",
    "MIN_RHO_PAIRS",
    "REPORT_NAME",
    "SEED",
    "VARIANTS",
    "C1Inputs",
    "C3Inputs",
    "Unit",
    "ball_advance",
    "block_before",
    "c1_units",
    "c3_units",
    "check",
    "candidate_power",
    "cp1_rule",
    "design_of",
    "load_c1",
    "load_c3",
    "phase_runs",
    "phase_stratum",
    "phase_types_by_third",
    "possessions_from",
    "power_report",
    "pressed_at",
    "probe_verdicts",
    "window_overlap",
    "write_power_report",
]

REPORT_NAME = "power.json"
SEED = 20261018
VARIANTS: tuple[str, ...] = ("V0", "V1")
MIN_RHO_PAIRS = 30  # pairs a V1 correlation needs before the noise may take it
MDE_LIMIT = 0.3  # sd: the plan's testability limit (D2, and CP1's rule for C2)
C3_DEFINITION = "with_gk_extremes_listed"  # chosen_definition of reports/probe_s3.json
C3_CONTRAST: tuple[str, str] = ("low_block", "high_block")  # the pressed group first
# Neighbouring blocks that share a third of the ball: (deeper, higher, third of the ball).
C3_CONTIGUOUS: dict[str, tuple[str, str, str]] = {
    "low_vs_medium_in_middle": ("low_block", "medium_block", "middle"),
    "medium_vs_high_in_own": ("medium_block", "high_block", "own"),
}
D3_RATIO = 0.5  # D3: |pre-trend| >= D3_RATIO |effect| in V0, pooled by stratum, kills
_THIRDS = ("own", "middle", "final", "undefined")
_PROBES = {"C1": "probe_s1.json", "C2": "probe_s2.json", "C3": "probe_s3.json"}


@dataclass(frozen=True)
class Unit:
    """One unit of a candidate at its instant ``t`` (``frame``).

    ``group`` is the cause group (``True`` pressed, or the low block for C3), ``None`` for a unit
    outside the contrast; ``pre`` is the statistic over ``[t - W, t]`` (``None`` when it cannot
    be read); ``v1`` whether the unit is in variant V1.
    """

    frame: int
    stratum: str
    group: bool | None
    possession: str
    pre: float | None
    v1: bool


@dataclass(frozen=True)
class C1Inputs:
    """A match of probe S1 and the team possession of each of its ``player_possession`` events."""

    s1: probe_s1.MatchInputs
    possessions: dict[str, str]


@dataclass(frozen=True)
class C3Inputs:
    """A match of probe S3 and the out-of-possession phase type of each phase index."""

    s3: probe_s3.MatchInputs
    types: dict[int, str | None]


# --- the readers before t ----------------------------------------------------------------------


def _ball_row(match: MatchData, frame: int) -> int:
    pos = int(np.searchsorted(match.ball_frame, frame))
    return pos if pos < len(match.ball_frame) and match.ball_frame[pos] == frame else -1


def ball_advance(match: MatchData, frame: int, sign: int, lag: int) -> float | None:
    """The ball's advance along the attack (``sign``) from ``frame - lag`` to ``frame``.

    ``lag`` must be 0 or more: nothing after ``frame`` can be read. ``None`` without a ball row
    at either end or with the two rows in different periods.
    """
    if lag < 0:
        raise ValueError(f"lag {lag} reads after t: only the statistic before t is measured")
    then, now = _ball_row(match, frame - lag), _ball_row(match, frame)
    if then < 0 or now < 0 or match.ball_period[then] != match.ball_period[now]:
        return None
    return sign * float(match.ball_x[now] - match.ball_x[then])


def block_before(
    match: MatchData,
    keepers: Mapping[tuple[int, int], int],
    phase: Phase,
    lag: int,
    definition: Definition,
) -> Block | None:
    """The block of the team out of possession of ``phase`` at ``frame_start - lag``.

    ``lag`` must be 0 or more: nothing after the phase's start can be read. ``None`` when the
    block cannot be measured there.
    """
    if lag < 0:
        raise ValueError(f"lag {lag} reads after t: only the statistic before t is measured")
    rows = players_at(match, phase.frame - lag)
    out = rows[match.team[rows] != phase.team_in]
    if len(out) == 0:
        return None
    keeper = keepers.get((phase.period, int(match.team[out[0]])))
    return measure(
        match.x[out], match.y[out], match.detected[out], match.player[out], keeper, definition
    )


def pressed_at(match: MatchData, reception: Reception) -> bool:
    """A rival listed at ``t`` within ``line.PRESSED_RADIUS`` of the carrier (m10's proxy)."""
    carrier = int(locate_rows(match, np.array([reception.player]), np.array([reception.frame]))[0])
    if carrier < 0:
        raise ValueError(f"no carrier row at frame {reception.frame}")
    rows = players_at(match, reception.frame)
    rivals = rows[match.team[rows] != reception.team]
    d = np.hypot(match.x[rivals] - match.x[carrier], match.y[rivals] - match.y[carrier])
    return bool((d <= line.PRESSED_RADIUS).any())


def phase_stratum(match: MatchData, phase: Phase) -> str:
    """The incoming-ball stratum at a phase start, the ball in the place of the carrier."""
    sign = match.attack_sign.get((phase.period, phase.team_in))
    now = _ball_row(match, phase.frame)
    if sign is None or now < 0:
        return "undefined"
    return pressure.incoming_ball(match, phase.frame, sign, float(match.ball_x[now]))


def phase_runs(phases: Sequence[Phase]) -> dict[int, str]:
    """Each phase index's team possession: a run of consecutive phases of one team in a period."""
    runs: dict[int, str] = {}
    previous: tuple[int, int] | None = None
    count = 0
    for phase in sorted(phases, key=lambda p: (p.period, p.frame, p.index)):
        key = (phase.period, phase.team_in)
        if key != previous:
            count += 1
            previous = key
        runs[phase.index] = f"run:{count}"
    return runs


def phase_types_by_third(inputs: C3Inputs) -> dict[str, dict[str, int]]:
    """Every phase of a match by its out-of-possession type and the third of the ball at its start.

    The third is the one of :func:`phase_stratum` (along the attack of the team in possession);
    a phase without a type counts as ``none``. Instants and labels only: no block is measured.
    """
    counts: dict[str, dict[str, int]] = {}
    for phase in inputs.s3.phases:
        stratum = phase_stratum(inputs.s3.match, phase)
        third = "undefined" if stratum == "undefined" else stratum.split("/")[1]
        kind = inputs.types.get(phase.index) or "none"
        counts.setdefault(kind, dict.fromkeys(_THIRDS, 0))[third] += 1
    return dict(sorted(counts.items()))


def window_overlap(receptions: Sequence[Reception]) -> dict[str, float | int | None]:
    """How often a unit's instant falls close after the instant of the unit before it.

    The units are sorted by period and frame; ``g`` is the frames from the unit before in the
    same period (the first of a period has none). ``within_w`` counts the units with
    ``g <= W``: their instant ``t``, so their cause and the end of their window before, lies in
    ``(t_prev, t_prev + W]``, the outcome window of the unit before. ``within_2w`` counts those
    with ``g <= 2 W``: their window before, ``[t - W, t]``, meets that outcome window.
    ``*_same_team``: and the unit before is of the same team. Shares are over every unit.
    """
    ordered = sorted(receptions, key=lambda r: (r.period, r.frame))
    counts = dict.fromkeys(
        ("within_w", "within_w_same_team", "within_2w", "within_2w_same_team"), 0
    )
    for before, after in zip(ordered, ordered[1:], strict=False):
        if before.period != after.period:
            continue
        gap = after.frame - before.frame
        for key, limit in (("within_w", W), ("within_2w", 2 * W)):
            if gap <= limit:
                counts[key] += 1
                counts[f"{key}_same_team"] += before.team == after.team
    n = len(ordered)
    shares = {f"{k}_share": (c / n if n else None) for k, c in counts.items()}
    return {"units": n, **counts, **shares}


# --- the units ---------------------------------------------------------------------------------


def possessions_from(events: pa.Table) -> dict[str, str]:
    """``native_event_id`` to ``possession_id`` of the ``player_possession`` events."""
    rows = events.filter(pc.equal(events["native_family"], "player_possession")).to_pylist()
    return {r["native_event_id"]: r["possession_id"] for r in rows if r["possession_id"]}


def c1_units(inputs: C1Inputs) -> tuple[list[Unit], dict[str, int]]:
    """The units of C1 in one match, and the counts that tie them to probe S1."""
    match = inputs.s1.match
    scored = pressure.score_receptions(match, inputs.s1.receptions)
    units: list[Unit] = []
    for s in scored:
        if s.stratum == "undefined":
            continue
        r = s.reception
        if r.event_id not in inputs.possessions:
            raise ValueError(f"reception {r.event_id} has no team possession")
        units.append(
            Unit(
                frame=r.frame,
                stratum=s.stratum,
                group=pressed_at(match, r),
                possession=inputs.possessions[r.event_id],
                pre=ball_advance(match, r.frame, match.attack_sign[(r.period, r.team)], W),
                v1=all(s.near_detected),
            )
        )
    counts = {
        "scored": len(scored),
        "stratum_undefined": sum(s.stratum == "undefined" for s in scored),
        "v1_scored": sum(all(s.near_detected) for s in scored),
    }
    return units, counts


def _definition() -> Definition:
    return next(d for d in DEFINITIONS if name_of(d) == C3_DEFINITION)


def c3_units(
    inputs: C3Inputs,
    outcome: str,
    stratified: bool,
    contrast: tuple[str, str] = C3_CONTRAST,
    third: str | None = None,
) -> list[Unit]:
    """The units of C3 for one outcome (``width`` or ``length``) in one match.

    Every phase whose block is measured at its start, of any type (``group`` is ``None`` outside
    ``contrast``, whose first type is the cause group, and outside ``third`` when one is given:
    the third of the ball in the stratum); with ``stratified`` false every phase is in one
    stratum, ``all``, and no third can be asked for.
    """
    if outcome not in ("width", "length"):
        raise ValueError(f"unknown outcome {outcome!r}")
    if third is not None and not stratified:
        raise ValueError("a third of the ball needs the incoming-ball strata")
    match = inputs.s3.match
    keepers = goalkeepers(match)
    definition = _definition()
    runs = phase_runs(inputs.s3.phases)
    ends = ("y_low", "y_high") if outcome == "width" else ("x_low", "x_high")
    units: list[Unit] = []
    for phase in sorted(inputs.s3.phases, key=lambda p: (p.period, p.frame, p.index)):
        now = block_before(match, keepers, phase, 0, definition)
        if now is None:
            continue
        stratum = phase_stratum(match, phase) if stratified else "all"
        if stratum == "undefined":
            continue
        kind = inputs.types.get(phase.index)
        group = True if kind == contrast[0] else False if kind == contrast[1] else None
        if third is not None and stratum.split("/")[1] != third:
            group = None
        rows = players_at(match, phase.frame)
        detected = dict(
            zip(match.player[rows].tolist(), match.detected[rows].tolist(), strict=True)
        )
        fixers = {p for end in ends for p in now.fixers[end]}
        before = block_before(match, keepers, phase, W, definition)
        pre = None if before is None else before.width if outcome == "width" else before.length
        units.append(
            Unit(
                frame=phase.frame,
                stratum=stratum,
                group=group,
                possession=runs[phase.index],
                pre=pre,
                v1=all(detected[p] for p in fixers),
            )
        )
    return units


def load_c1(match_id: int) -> C1Inputs:
    """Probe S1's inputs and the team possessions, through the guarded door."""
    events = data.read_events(
        [match_id], columns=["native_family", "native_event_id", "possession_id"]
    )
    return C1Inputs(s1=probe_s1.load_inputs(match_id), possessions=possessions_from(events))


def load_c3(match_id: int) -> C3Inputs:
    """Probe S3's inputs and the out-of-possession phase types, through the guarded door."""
    phases = data.read_bronze_phases(
        [match_id], columns=["index", "team_out_of_possession_phase_type"]
    )
    types = {
        int(r["index"]): r["team_out_of_possession_phase_type"]
        for r in phases.to_pylist()
        if r["index"] is not None
    }
    return C3Inputs(s3=probe_s3.load_inputs(match_id), types=types)


# --- the power of one candidate ----------------------------------------------------------------


def design_of(units: Mapping[int, Sequence[Unit]], variant: str) -> bar.Design:
    """The bar's design: the units in the contrast (and in V1 for ``V1``), every match listed."""
    matches = tuple(units)
    kept = [
        (i, u)
        for i, m in enumerate(matches)
        for u in units[m]
        if u.group is not None and (variant == "V0" or u.v1)
    ]
    return bar.Design(
        matches=matches,
        match=np.array([i for i, _ in kept], dtype=np.int64),
        stratum=tuple(u.stratum for _, u in kept),
        pressed=np.array([bool(u.group) for _, u in kept], dtype=np.bool_),
        possession=tuple(u.possession for _, u in kept),
    )


def _correlation(units: Sequence[Unit], variant: str) -> bar.Correlation:
    pick = [u for u in units if u.pre is not None and (variant == "V0" or u.v1)]
    return bar.within_possession_correlation(
        [float(u.pre) for u in pick],  # type: ignore[arg-type]
        [u.stratum for u in pick],
        [u.possession for u in pick],
    )


def _pretrend(units: Sequence[Unit], variant: str) -> float | None:
    pick = [
        u for u in units if u.group is not None and u.pre is not None and (variant == "V0" or u.v1)
    ]
    pooled = line.within_strata(
        [float(u.pre) for u in pick],  # type: ignore[arg-type]
        [bool(u.group) for u in pick],
        [u.stratum for u in pick],
        bar.MIN_CELL,
    )
    sd = pooled["sd"]
    return None if sd is None else float(sd)  # type: ignore[arg-type]


def _pretrend_pooled(
    units: Mapping[int, Sequence[Unit]], variant: str, mde80: float | None
) -> dict[str, object]:
    """The pre-trend pooled over every (match, stratum) cell, D3's floor and probe S2's bar.

    D3 kills when ``|pre-trend| >= D3_RATIO |effect|``: the effect must exceed, in absolute
    value, ``|pre-trend| / D3_RATIO``. Probe S2's bar: more than ``MAX_OVER`` matches with a
    pre-trend over ``MAX_PRETREND_SD`` in absolute value.
    """
    pick = [
        (m, u)
        for m in units
        for u in units[m]
        if u.group is not None and u.pre is not None and (variant == "V0" or u.v1)
    ]
    sd = line.within_strata(
        [float(u.pre) for _, u in pick],  # type: ignore[arg-type]
        [bool(u.group) for _, u in pick],
        [f"{m}/{u.stratum}" for m, u in pick],
        bar.MIN_CELL,
    )["sd"]
    pooled = None if sd is None else float(sd)  # type: ignore[arg-type]
    by_match = [_pretrend(units[m], variant) for m in units]
    over = sum(p is not None and abs(p) > probe_s2.MAX_PRETREND_SD for p in by_match)
    floor = None if pooled is None else abs(pooled) / D3_RATIO
    return {
        "pooled_sd": pooled,
        "d3_abs_effect_must_exceed_sd": floor,
        "d3_floor_over_mde80": None if floor is None or not mde80 else floor / mde80,
        "s2_bar": {
            "limit_sd": probe_s2.MAX_PRETREND_SD,
            "matches_over": over,
            "max_over": probe_s2.MAX_OVER,
            "would_die": over > probe_s2.MAX_OVER,
        },
    }


def candidate_power(
    units: Mapping[int, Sequence[Unit]],
    label: str,
    with_pretrend: bool,
    replicates: int = bar.POWER_REPLICATES,
) -> dict[str, object]:
    """Correlation, null, design and power of one candidate outcome, by variant and match."""
    matches = list(units)
    corr = {v: {m: _correlation(units[m], v) for m in matches} for v in VARIANTS}

    def carried(m: int, variant: str) -> float:
        values = [0.0, corr["V0"][m].rho or 0.0]
        own = corr[variant][m]
        if variant != "V0" and own.rho is not None and own.pairs >= MIN_RHO_PAIRS:
            values.append(own.rho)
        return max(values)

    rho = {v: [carried(m, v) for m in matches] for v in VARIANTS}
    measured = [(c.rho, c.pairs) for c in corr["V0"].values() if c.rho is not None]
    pairs = sum(n for _, n in measured)
    pooled = sum(r * n for r, n in measured) / pairs if pairs else None
    blocked = pooled is not None and pooled > bar.BLOCK_RHO
    variants: dict[str, object] = {}
    for v in VARIANTS:
        design = design_of(units, v)
        prepared = bar.prepare(design)
        power = bar.mde80(
            design, rho[v], blocked, (SEED, zlib.crc32(f"{label}/{v}".encode())), replicates
        )
        n_cells = len(prepared.weight)
        cells = np.bincount(prepared.cell_match, minlength=len(matches)) if n_cells else None
        weight = (
            np.bincount(prepared.cell_match, weights=prepared.weight, minlength=len(matches))
            if n_cells
            else None
        )
        used = np.bincount(prepared.unit_match, minlength=len(matches))
        per_match: dict[str, object] = {}
        for i, m in enumerate(matches):
            mine = [u for u in units[m] if u.group is not None and (v == "V0" or u.v1)]
            c = corr[v][m]
            per_match[str(m)] = {
                "n": len(mine),
                "pressed": sum(bool(u.group) for u in mine),
                "free": sum(not u.group for u in mine),
                "possessions": len({u.possession for u in mine}),
                "cells_used": int(cells[i]) if cells is not None else 0,
                "units_used": int(used[i]),
                "weight": float(weight[i]) if weight is not None else 0.0,
                "rho": {"value": c.rho, "pairs": c.pairs, "units": c.units, "carried": rho[v][i]},
                **({"pretrend_sd": _pretrend(units[m], v)} if with_pretrend else {}),
            }
        variants[v] = {
            "matches": per_match,
            "mde80_sd": power.mde80,
            "null_pass_rate": power.pass_rate[0],
            "pass_rate": {
                f"{e:.2f}": r for e, r in zip(power.effects, power.pass_rate, strict=True)
            },
            "replicates": power.replicates,
            "seed": [SEED, zlib.crc32(f"{label}/{v}".encode())],
            **({"pretrend": _pretrend_pooled(units, v, power.mde80)} if with_pretrend else {}),
        }
    return {"blocked": blocked, "rho_v0_pooled": pooled, "variants": variants}


# --- the probes, the rule and the report -------------------------------------------------------


def probe_verdicts(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    """Whether each candidate survived its probe, from the parsed probe reports by file name.

    The module reads no file: the command line reads the three reports and passes them in.
    """
    found: dict[str, bool] = {}
    for candidate, name in _PROBES.items():
        value = reports[name]["verdict"][f"{candidate.lower()}_survives_probe"]
        if not isinstance(value, bool):
            raise ValueError(f"{name} has no complete verdict")
        found[candidate] = value
    return found


def cp1_rule(alive: Mapping[str, bool], mde80_v0: Mapping[str, float | None]) -> dict[str, object]:
    """The plan's rule of CP1 on the verdicts and the V0 MDE80s: what goes first, and why.

    C2 never reaches here alive (its power is not written). ``mde80_v0`` holds the simulated
    designs, keyed by candidate (and, for C3, by contrast and outcome); ``testable_v0`` says
    whether their V0 MDE80 is at most :data:`MDE_LIMIT`. Which contrast C3 would use is CP1's.
    """
    if alive.get("C2"):
        raise NotImplementedError("C2 survived probe S2: its power is not written")
    first = "C1" if alive.get("C1") else "C3" if alive.get("C3") else "branch_B"
    return {
        "recommended_first": first,
        "backup": "C3" if alive.get("C3") and first != "C3" else None,
        "testable_v0": {k: (v is not None and v <= MDE_LIMIT) for k, v in sorted(mde80_v0.items())},
        "rule": (
            "C2 first if it survived probe S2 and its V1 MDE80 is at most mde_limit; otherwise "
            "C1 if alive; C3 only as a backup; none alive, branch B. CP1 decides, also which "
            "contrast C3 would use."
        ),
    }


def power_report(match_ids: Sequence[int], alive: Mapping[str, bool]) -> dict[str, object]:
    """Read each match through the guarded door and simulate the power of the live candidates.

    ``alive`` is :func:`probe_verdicts` of the committed probe reports.
    """
    if alive["C2"]:
        raise NotImplementedError("C2 survived probe S2: its power is not written")
    candidates: dict[str, object] = {}
    mde: dict[str, float | None] = {}
    counts: dict[str, object] = {}
    if alive["C1"]:
        c1: dict[int, list[Unit]] = {}
        overlap: dict[str, object] = {}
        for m in match_ids:
            loaded = load_c1(m)
            c1[m], counts[str(m)] = c1_units(loaded)
            frames = {u.frame for u in c1[m]}  # one reception per frame (probe S1's load)
            if len(frames) != len(c1[m]):
                raise ValueError(f"two units of match {m} share a frame")
            overlap[str(m)] = window_overlap([r for r in loaded.s1.receptions if r.frame in frames])
        result = candidate_power(c1, "C1/ball_advance/incoming_ball", with_pretrend=True)
        candidates["C1"] = {
            "outcomes": {"ball_advance": {"incoming_ball": result}},
            "probe_counts": counts,
            "status": "simulated",
            "window_overlap": overlap,
        }
        mde["C1"] = result["variants"]["V0"]["mde80_sd"]  # type: ignore[index]
    else:
        candidates["C1"] = {"status": "died_in_probe"}
    candidates["C2"] = {"status": "died_in_probe"}
    if alive["C3"]:
        inputs = {m: load_c3(m) for m in match_ids}
        outcomes: dict[str, object] = {}
        every: dict[str, dict[int, list[Unit]]] = {}
        for outcome in ("width", "length"):
            every[outcome] = {m: c3_units(i, outcome, False) for m, i in inputs.items()}
            stratified = {m: c3_units(i, outcome, True) for m, i in inputs.items()}
            outcomes[outcome] = {
                strata: candidate_power(units, f"C3/{outcome}/{strata}", with_pretrend=False)
                for strata, units in (("incoming_ball", stratified), ("none", every[outcome]))
            }
            mde[f"C3/low_vs_high/{outcome}"] = outcomes[outcome]["incoming_ball"]["variants"][  # type: ignore[index]
                "V0"
            ]["mde80_sd"]
        contiguous: dict[str, object] = {}
        for name, (deeper, higher, third) in C3_CONTIGUOUS.items():
            by_outcome: dict[str, object] = {}
            for outcome in ("width", "length"):
                units = {
                    m: c3_units(i, outcome, True, contrast=(deeper, higher), third=third)
                    for m, i in inputs.items()
                }
                by_outcome[outcome] = candidate_power(
                    units, f"C3/{name}/{outcome}", with_pretrend=False
                )
                mde[f"C3/{name}/{outcome}"] = by_outcome[outcome]["variants"]["V0"]["mde80_sd"]  # type: ignore[index]
            contiguous[name] = {
                "contrast": [deeper, higher],
                "outcomes": by_outcome,
                "third": third,
            }
        types = {str(m): phase_types_by_third(i) for m, i in inputs.items()}
        total: dict[str, dict[str, int]] = {}
        for per_match in types.values():
            for kind, thirds in per_match.items():
                for third, n in thirds.items():
                    total.setdefault(kind, dict.fromkeys(_THIRDS, 0))[third] += n
        candidates["C3"] = {
            "contiguous": contiguous,
            "outcomes": outcomes,
            "phase_types_by_third": {"matches": types, "total": dict(sorted(total.items()))},
            "probe_counts": {
                str(m): {
                    "measured": len(every["width"][m]),
                    "v1_length": sum(u.v1 for u in every["length"][m]),
                    "v1_width": sum(u.v1 for u in every["width"][m]),
                }
                for m in match_ids
            },
            "status": "simulated",
        }
    else:
        candidates["C3"] = {"status": "died_in_probe"}
    return {
        "about": (
            "Task 17: power of the calibration bar (same sign in at least 8 of 10 matches and a "
            "two-sided permutation p at most 0.00135 over 2000 null draws) for each candidate "
            "alive after its probe, simulated on the real design of the calibration matches "
            "with the within-possession correlation of the statistic before t ([t - W, t]). "
            "Effects in sd of the noise. No outcome of any candidate is computed. Definitions "
            "in the docstrings of ac2fb.defence.power and ac2fb.defence.bar."
        ),
        "constants": {
            "bar_count_at_most": bar.BAR_COUNT_AT_MOST,
            "bar_p": bar.BAR_P,
            "bar_same_sign": bar.BAR_SAME_SIGN,
            "block_rho": bar.BLOCK_RHO,
            "c3_contiguous": {k: list(v) for k, v in C3_CONTIGUOUS.items()},
            "c3_contrast": list(C3_CONTRAST),
            "c3_definition": C3_DEFINITION,
            "chunk": bar.CHUNK,
            "coarse_step_sd": bar.COARSE_STEP,
            "d3_ratio": D3_RATIO,
            "fine_step_sd": bar.FINE_STEP,
            "max_effect_sd": bar.MAX_EFFECT,
            "mde_limit_sd": MDE_LIMIT,
            "min_cell": bar.MIN_CELL,
            "min_rho_pairs": MIN_RHO_PAIRS,
            "n_permutations": bar.N_PERMUTATIONS,
            "power_target": bar.POWER_TARGET,
            "pressed_radius_m": line.PRESSED_RADIUS,
            "replicates": bar.POWER_REPLICATES,
            "seed": SEED,
            "window_frames": W,
        },
        "matches": [int(m) for m in match_ids],
        "probes": dict(alive),
        "candidates": candidates,
        "cp1_rule": cp1_rule(alive, mde),
    }


def write_power_report(
    match_ids: Sequence[int], reports_dir: Path, alive: Mapping[str, bool]
) -> Path:
    """Build the report and write ``reports_dir/power.json`` (LF); return its path."""
    report = power_report(match_ids, alive)
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path


def check(match_ids: Sequence[int], alive: Mapping[str, bool], raw: bytes | None) -> JsonCheck:
    """Recompute ``power.json`` of the matches and compare every value with ``raw``."""
    return check_json(REPORT_NAME, render_report(power_report(match_ids, alive)), raw)
