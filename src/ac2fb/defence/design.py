"""The protocol's design on a half, before any outcome: units, groups, exclusions, pre-trend, power.

Task 19 (``protocol/protocol.json``). Everything here is read at ``t`` or before it: the
outcome window ``(t, t + W]`` is never asked for (the only reader of the ball's advance refuses a
negative lag, :func:`ac2fb.defence.power.ball_advance`). The report it writes,
``reports/design.json``, gives the figures the protocol's choices change and that task 17's
``power.json`` cannot give: the units left after the window-overlap exclusion, the groups under
the index cut, the V1 of the protocol, and on those units the correlation of the pre statistic,
the blocking decision, the MDE80 and the pooled pre-trend in sd (D3's floor) and in metres.
Written before any of it was computed on a real match.

**Units** (protocol ``units``). The *design* of a match is the labelled receptions of probe S1
scored by :func:`ac2fb.defence.pressure.score_receptions` with a defined incoming-ball stratum
(task 17's units). The *kept* units are those the window-overlap rule does not exclude: a unit
whose instant lies :data:`EXCLUSION_GAP` frames or fewer after the instant of the preceding
design unit of the same period (either team) is excluded, whether or not that preceding unit is
itself excluded (:func:`excluded_by_gap`). On the kept units no instant lies in the outcome
window of another kept unit.

**Groups** (protocol ``cause``). Pressed when the index is at least
:data:`~ac2fb.defence.pressure.PRESSED_INDEX`. The 5 m proxy of task 17 (a rival within
:data:`~ac2fb.defence.line.PRESSED_RADIUS` at ``t``) is carried beside it as ``proxy`` so that
the pre-trend that cause gives on the same units is printed next to the protocol's.

**V1 and V2** (protocol ``variants``). The players of the metric are the carrier and the near
rivals (positive weight at ``t``); ``extrapolated_players`` counts those not detected at ``t``;
V1 is the kept units with none, V2's classes are 0, 1 and 2 or more.

**What is written.** Per match the counts at every step, the overlap on the design (task 17's
count, :func:`ac2fb.defence.power.window_overlap`) and on the kept units, the kept units by label
level and by stratum with their pressed and V1 counts (V1's declared selection), the V2 classes,
the share with the ball not detected at ``t``, the proxy's groups and their agreement with the
index; and :func:`ac2fb.defence.power.candidate_power` on the kept units under the index cut
(correlation, blocking, MDE80, pooled pre-trend in sd with D3's floor, per variant) with the
pre-trend in metres beside it (:func:`pooled_pretrend`), and the same pre-trend under the proxy.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ac2fb.defence import bar, line, power, pressure
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.defence.pressure import LEVELS, Reception
from ac2fb.reliability.report import render_report

__all__ = [
    "CAUSES",
    "EXCLUSION_GAP",
    "REPORT_NAME",
    "DesignUnit",
    "design_report",
    "design_units",
    "excluded_by_gap",
    "match_counts",
    "pooled_pretrend",
    "power_units",
    "write_design_report",
]

REPORT_NAME = "design.json"
EXCLUSION_GAP = W  # frames: protocol units.exclusion.gap_frames_at_most, the window itself
CAUSES: tuple[str, ...] = ("index", "proxy")  # the protocol's cause, and task 17's beside it
_LABEL = "C1/design/ball_advance/incoming_ball"  # the random stream of the power simulation


@dataclass(frozen=True)
class DesignUnit:
    """One design unit of a match at its instant ``t``, with everything read at or before ``t``.

    ``pressed`` is the protocol's group (index cut), ``proxy_pressed`` task 17's (5 m);
    ``extrapolated_players`` counts the carrier and the near rivals not detected at ``t``;
    ``pre`` is the ball's advance over ``[t - W, t]`` (``None`` without a ball row at ``t - W``);
    ``excluded`` whether the window-overlap rule drops the unit.
    """

    event_id: str
    period: int
    frame: int
    team: int
    level: int
    stratum: str
    index: float
    pressed: bool
    proxy_pressed: bool
    possession: str
    pre: float | None
    extrapolated_players: int
    ball_extrapolated_at_t: bool
    excluded: bool


def excluded_by_gap(receptions: Sequence[Reception]) -> set[tuple[int, int]]:
    """The ``(period, frame)`` of every reception within :data:`EXCLUSION_GAP` of the one before.

    The receptions are ordered by period and frame; a gap is measured to the immediately
    preceding one of the same period, of either team, excluded or not. The first of a period
    never counts.
    """
    ordered = sorted(receptions, key=lambda r: (r.period, r.frame))
    out: set[tuple[int, int]] = set()
    for before, after in zip(ordered, ordered[1:], strict=False):
        if before.period == after.period and after.frame - before.frame <= EXCLUSION_GAP:
            out.add((after.period, after.frame))
    return out


def design_units(inputs: power.C1Inputs) -> list[DesignUnit]:
    """Every design unit of a match, flagged by the exclusion rule, in order of period and frame.

    Raises ``ValueError`` when a unit has no team possession (as task 17's units do).
    """
    match = inputs.s1.match
    scored = [
        s
        for s in pressure.score_receptions(match, inputs.s1.receptions)
        if s.stratum != "undefined"
    ]
    receptions = [s.reception for s in scored]
    excluded = excluded_by_gap(receptions)
    units: list[DesignUnit] = []
    for s in sorted(scored, key=lambda s: (s.reception.period, s.reception.frame)):
        r = s.reception
        if r.event_id not in inputs.possessions:
            raise ValueError(f"reception {r.event_id} has no team possession")
        sign = match.attack_sign[(r.period, r.team)]
        units.append(
            DesignUnit(
                event_id=r.event_id,
                period=r.period,
                frame=r.frame,
                team=r.team,
                level=r.level,
                stratum=s.stratum,
                index=s.index,
                pressed=s.index >= pressure.PRESSED_INDEX,
                proxy_pressed=power.pressed_at(match, r),
                possession=inputs.possessions[r.event_id],
                pre=power.ball_advance(match, r.frame, sign, W),
                extrapolated_players=int(not s.carrier_detected)
                + sum(not d for d in s.near_detected),
                ball_extrapolated_at_t=line.ball_extrapolated(match, r.frame, r.frame),
                excluded=(r.period, r.frame) in excluded,
            )
        )
    return units


def power_units(units: Sequence[DesignUnit], cause: str) -> list[power.Unit]:
    """The kept units as task 17's units, grouped by ``cause`` (``index`` or ``proxy``)."""
    if cause not in CAUSES:
        raise ValueError(f"unknown cause {cause!r}: one of {CAUSES}")
    return [
        power.Unit(
            frame=u.frame,
            stratum=u.stratum,
            group=u.pressed if cause == "index" else u.proxy_pressed,
            possession=u.possession,
            pre=u.pre,
            v1=u.extrapolated_players == 0,
        )
        for u in units
        if not u.excluded
    ]


def _within(units: Sequence[power.Unit], cells: Sequence[str]) -> dict[str, object]:
    pick = [(u, c) for u, c in zip(units, cells, strict=True) if u.pre is not None]
    return line.within_strata(
        [float(u.pre) for u, _ in pick],  # type: ignore[arg-type]
        [bool(u.group) for u, _ in pick],
        [c for _, c in pick],
        bar.MIN_CELL,
    )


def pooled_pretrend(units: Mapping[int, Sequence[power.Unit]], variant: str) -> dict[str, object]:
    """The pre-trend pooled over every (match, stratum) cell with the bar's weights, sd and metres.

    ``sd`` is the figure D3 judges (task 17's ``pretrend.pooled_sd``); ``metres`` the same
    pooling of the unstandardised differences; each with the floor D3 sets on the effect,
    ``|pre-trend| / D3_RATIO``, in its own unit. Per match too.
    """
    pick = [(m, u) for m in units for u in units[m] if variant == "V0" or u.v1]
    pooled = _within([u for _, u in pick], [f"{m}/{u.stratum}" for m, u in pick])
    by_match = {
        str(m): _within(
            [u for u in units[m] if variant == "V0" or u.v1],
            [u.stratum for u in units[m] if variant == "V0" or u.v1],
        )
        for m in units
    }

    def floor(value: object) -> float | None:
        return None if value is None else abs(float(value)) / power.D3_RATIO  # type: ignore[arg-type]

    return {
        "sd": pooled["sd"],
        "metres": pooled["m"],
        "d3_abs_effect_must_exceed_sd": floor(pooled["sd"]),
        "d3_abs_effect_must_exceed_m": floor(pooled["m"]),
        "cells_used": pooled["strata_used"],
        "units_used": pooled["units_used"],
        "matches": {
            m: {"sd": w["sd"], "metres": w["m"], "cells_used": w["strata_used"]}
            for m, w in by_match.items()
        },
    }


def match_counts(inputs: power.C1Inputs, units: Sequence[DesignUnit]) -> dict[str, object]:
    """The counts of one match at every step of the protocol's design, and the overlap."""
    kept = [u for u in units if not u.excluded]
    v1 = [u for u in kept if u.extrapolated_players == 0]
    by_frame = {r.frame: r for r in inputs.s1.receptions}

    def group(items: Sequence[DesignUnit]) -> dict[str, int]:
        return {
            "kept": len(items),
            "pressed": sum(u.pressed for u in items),
            "v1": sum(u.extrapolated_players == 0 for u in items),
            "v1_pressed": sum(u.pressed and u.extrapolated_players == 0 for u in items),
        }

    return {
        "possessions": inputs.s1.possessions,
        "labelled": len(inputs.s1.receptions),
        "design": len(units),
        "excluded_gap": sum(u.excluded for u in units),
        "kept": len(kept),
        "kept_pressed": sum(u.pressed for u in kept),
        "kept_free": sum(not u.pressed for u in kept),
        "kept_v1": len(v1),
        "kept_v1_pressed": sum(u.pressed for u in v1),
        "kept_v1_free": sum(not u.pressed for u in v1),
        "pre_undefined": sum(u.pre is None for u in kept),
        "v2_classes": {
            "0": len(v1),
            "1": sum(u.extrapolated_players == 1 for u in kept),
            "2_or_more": sum(u.extrapolated_players >= 2 for u in kept),
        },
        "by_level": {name: group([u for u in kept if u.level == k]) for k, name in LEVELS.items()},
        "by_stratum": {
            s: group([u for u in kept if u.stratum == s]) for s in sorted({u.stratum for u in kept})
        },
        "ball_extrapolated_at_t": (
            sum(u.ball_extrapolated_at_t for u in kept) / len(kept) if kept else None
        ),
        "overlap_design": power.window_overlap([by_frame[u.frame] for u in units]),
        "overlap_kept": power.window_overlap([by_frame[u.frame] for u in kept]),
        "proxy": {
            "pressed": sum(u.proxy_pressed for u in kept),
            "free": sum(not u.proxy_pressed for u in kept),
            "agrees_with_index": (
                sum(u.proxy_pressed == u.pressed for u in kept) / len(kept) if kept else None
            ),
        },
    }


def design_report(match_ids: Sequence[int]) -> dict[str, object]:
    """Read each match through the guarded door and build the design report of the half."""
    loaded = {m: power.load_c1(m) for m in match_ids}
    units = {m: design_units(i) for m, i in loaded.items()}
    for m, us in units.items():
        frames = {u.frame for u in us}
        if len(frames) != len(us):
            raise ValueError(f"two units of match {m} share a frame")
    index = {m: power_units(us, "index") for m, us in units.items()}
    proxy = {m: power_units(us, "proxy") for m, us in units.items()}
    simulated = power.candidate_power(index, _LABEL, with_pretrend=True)
    return {
        "about": (
            "Task 19: the protocol's design on the calibration half, before any outcome. The "
            "units left after the window-overlap exclusion, grouped by the index cut; on them "
            "the correlation of the pre statistic, the blocking decision, the MDE80 and the "
            "pooled pre-trend in sd (D3's floor) and in metres; the same pre-trend under task "
            "17's 5 m proxy beside it. Nothing after t is read. Definitions in "
            "ac2fb.defence.design and protocol/protocol.json."
        ),
        "constants": {
            "causes": list(CAUSES),
            "d3_ratio": power.D3_RATIO,
            "exclusion_gap_frames": EXCLUSION_GAP,
            "min_cell": bar.MIN_CELL,
            "pressed_index": pressure.PRESSED_INDEX,
            "proxy_radius_m": line.PRESSED_RADIUS,
            "replicates": bar.POWER_REPLICATES,
            "seed": power.SEED,
            "window_frames": W,
        },
        "matches": [int(m) for m in match_ids],
        "units": {str(m): match_counts(loaded[m], units[m]) for m in match_ids},
        "index_cause": {
            "power": simulated,
            "pretrend": {v: pooled_pretrend(index, v) for v in power.VARIANTS},
        },
        "proxy_cause": {"pretrend": {v: pooled_pretrend(proxy, v) for v in power.VARIANTS}},
    }


def write_design_report(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Build the report and write ``reports_dir/design.json`` (LF); return its path."""
    report = design_report(match_ids)
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path
