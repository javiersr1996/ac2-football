"""Probe S2 (candidate C2): is the last line an instrument, and how large is its pre-trend?

The probe measures the instrument and what comes before the reception ``t``. It computes no
outcome of any candidate: no position after ``t`` enters any figure. What is read after ``t``
is whether the line's players are detected in ``(t, t + W]`` (item e, the selection of V1), a
count of visibility, never where they went; and the goalkeeper proxy's mean position over the
period, a role (see :mod:`ac2fb.defence.line`). The line, the pressure at ``t`` and what is read
are defined in :mod:`ac2fb.defence.line`; the incoming-ball strata in
:mod:`ac2fb.defence.pressure`. Everything below was written before the data was read.

**Window and units.** ``W`` = :data:`~ac2fb.defence.pressure.INCOMING_WINDOW` frames (the
shortest admissible window of ``reports/probe_cadence.json``), ``K`` = :data:`VELOCITY_FRAMES`.
Every ``player_possession`` event with a player and a team is a reception, labelled or not.
Variant V0 holds the receptions whose line is listed at ``t``, ``t - K``, ``t - W`` and
``t - W - K`` and whose incoming-ball stratum is defined (ball rows at ``t - W`` and ``t``).

**Statistics before the reception** (``L`` is the line height; + is the line retreating):

- raw pre-trend ``P = L(t) - L(t - W)``;
- residual pre-trend ``R = P - W * v(t - W)``, with ``v(s) = (L(s) - L(s - K)) / K`` per
  frame: the C2 outcome (displacement in ``[t, t + W]`` minus what the velocity at ``t``
  predicted) moved back by ``W``, so it reads nothing after ``t``;
- velocity at ``t``, ``(L(t) - L(t - K)) / (K * 0.1 s)`` in m/s (item d; reported, decides
  nothing).

**The items.** (a) Concordance of ``L(t)`` with the provider's ``last_defensive_line_x_start``
over the receptions with a line at ``t`` and a provider value. (b) The line follows the incoming
ball: mean ``P`` by direction. (c) Pre-trend within stratum: pressed minus free in each of the
18 strata (direction by third by length), in sd of the statistic in the stratum, pooled with
:func:`~ac2fb.defence.line.within_strata`; strata with fewer than :data:`MIN_CELL` pressed or
free receptions are left out. (d) Velocity at ``t`` by group. (e) Receptions of V0 whose four
line players are detected in every frame of ``[t - W, t + W]`` (V1), and by how many of the four
are (V2), by stratum, group and mean distance of the line to the ball at ``t``. (f) Share of V0
with the ball unlisted or not detected in some frame of ``[t - W, t]``.

**The rule that kills C2 in the probe.** Per calibration match, thresholds not moved after the
data is read:

1. *Instrument.* A match passes when (a) the Pearson correlation of ``L(t)`` with
   ``last_defensive_line_x_start`` is at least :data:`MIN_R` over at least :data:`MIN_GROUP`
   pairs, and (b) the mean ``P`` is negative after a backward ball and positive after a
   forward one, each over at least :data:`MIN_GROUP` receptions of V0. **C2 dies if fewer than
   :data:`MIN_INSTRUMENT` of the :data:`CALIBRATION_MATCHES` pass.**
2. *Pre-trend within stratum.* A match is over when the pooled pressed-minus-free difference
   of ``P`` or of ``R`` exceeds :data:`MAX_PRETREND_SD` sd in absolute value (a match with no
   stratum to pool is over too). **C2 dies if more than :data:`MAX_OVER` matches are over.**
3. *Visibility.* **C2 dies if any calibration match has fewer than :data:`MIN_V1` receptions in
   V1.**

C2 survives the probe when none of the three kills it. Pressed and free use the m10 proxy (a
rival within 5 m at ``t``); the protocol may refine the cause, not this rule. The plan marks the
100 of criterion 3 as a hypothesis that the power analysis (task 17) revisits; the probe
applies it as written, in every match.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from ac2fb.defence import line as line_module
from ac2fb.defence import m10
from ac2fb.defence.line import LINE_SIZE, LineReception, Unit
from ac2fb.defence.pressure import INCOMING_WINDOW as W
from ac2fb.protocol import data
from ac2fb.reliability.match import MatchData, build_match
from ac2fb.reliability.report import render_report
from ac2fb.reliability.visibility import BALL_DISTANCE_EDGES

__all__ = [
    "CALIBRATION_MATCHES",
    "FRAME_SECONDS",
    "LAGS",
    "MAX_OVER",
    "MAX_PRETREND_SD",
    "MIN_CELL",
    "MIN_GROUP",
    "MIN_INSTRUMENT",
    "MIN_R",
    "MIN_V1",
    "REPORT_NAME",
    "VELOCITY_FRAMES",
    "MatchInputs",
    "line_receptions",
    "load_inputs",
    "match_report",
    "s2_report",
    "verdict",
    "write_s2_report",
]

REPORT_NAME = "probe_s2.json"
CALIBRATION_MATCHES = 10
MIN_R = 0.9  # Pearson correlation of the line with the provider's, per match
MIN_GROUP = 30  # pairs for (a); receptions after a backward and after a forward ball for (b)
MIN_INSTRUMENT = 9  # matches whose instrument passes
MAX_PRETREND_SD = 0.15  # |pre-trend within stratum| in sd of the stratum
MAX_OVER = 2  # matches allowed over MAX_PRETREND_SD
MIN_CELL = 5  # pressed and free receptions a stratum needs to enter the pooled pre-trend
MIN_V1 = 100  # receptions with the whole line seen in [t - W, t + W], in every match
VELOCITY_FRAMES = 5  # K: frames behind an instant over which its velocity is measured
FRAME_SECONDS = 0.1
LAGS: tuple[int, ...] = tuple(sorted({VELOCITY_FRAMES, W, W + VELOCITY_FRAMES, *m10.LAGS}))

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
    "native_event_id",
    "frame_start",
    "frame_end",
    "period",
    "team_id",
    "player_id",
]
_BRONZE_COLUMNS = [
    "event_id",
    "event_type",
    "last_defensive_line_x_start",
    "overall_pressure_start",
]
_DISTANCE_BINS = ("00_05", "05_10", "10_20", "20_30", "30_40", "40_plus")


@dataclass(frozen=True)
class MatchInputs:
    """One match ready for the probe: its arrays and its receptions."""

    match: MatchData
    receptions: tuple[LineReception, ...]
    possessions: int  # player_possession events, with a player and a team or not


def _native(value: str | None) -> int | None:
    return None if value is None else int(value.split(":", 1)[1])


def line_receptions(events: pa.Table, bronze: pa.Table) -> tuple[int, list[LineReception]]:
    """Every reception with the provider's line and label, and the ``player_possession`` count.

    ``events`` are the silver events, ``bronze`` the provider's ``dynamic_events``; they join on
    silver's ``native_event_id`` = bronze's ``event_id``. An event without a player or a team is
    not a reception; one missing from bronze keeps null provider fields.
    """
    provider: dict[str, tuple[float | None, str | None]] = {}
    for row in bronze.filter(pc.equal(bronze["event_type"], "player_possession")).to_pylist():
        value = row["last_defensive_line_x_start"]
        provider[row["event_id"]] = (
            None if value is None else float(value),
            row["overall_pressure_start"],
        )
    mine = events.filter(pc.equal(events["native_family"], "player_possession")).to_pylist()
    found: list[LineReception] = []
    for row in mine:
        player, team = _native(row["player_id"]), _native(row["team_id"])
        if player is None or team is None:
            continue
        value, label = provider.get(row["native_event_id"], (None, None))
        found.append(
            LineReception(
                event_id=row["native_event_id"],
                period=row["period"],
                frame=row["frame_start"],
                team=team,
                player=player,
                provider_line=value,
                label=label,
            )
        )
    return len(mine), found


def load_inputs(match_id: int) -> MatchInputs:
    """Read one match through the guarded door (bronze included) and prepare it.

    Raises :class:`~ac2fb.protocol.data.HeldOutLocked` for a held-out match while locked.
    """
    ids = [match_id]
    frames = data.read_frames(ids, columns=_FRAME_COLUMNS)
    events = data.read_events(ids, columns=_EVENT_COLUMNS)
    bronze = data.read_bronze_events(ids, columns=_BRONZE_COLUMNS)
    team_periods = data.read_dim("dim_team_period", ids)
    possessions, found = line_receptions(events, bronze)
    return MatchInputs(
        match=build_match(match_id, frames, events, team_periods),
        receptions=tuple(found),
        possessions=possessions,
    )


# --- the statistics before t -------------------------------------------------------------------


def _v0(units: Sequence[Unit]) -> list[Unit]:
    need = (VELOCITY_FRAMES, W, W + VELOCITY_FRAMES)
    return [
        u
        for u in units
        if u.stratum != "undefined" and all(math.isfinite(u.depth[lag]) for lag in need)
    ]


def _raw(u: Unit) -> float:
    return u.depth[0] - u.depth[W]


def _residual(u: Unit) -> float:
    velocity = (u.depth[W] - u.depth[W + VELOCITY_FRAMES]) / VELOCITY_FRAMES
    return _raw(u) - W * velocity


def _velocity(u: Unit) -> float:
    return (u.depth[0] - u.depth[VELOCITY_FRAMES]) / (VELOCITY_FRAMES * FRAME_SECONDS)


def _summary(values: Sequence[float]) -> dict[str, object]:
    return {
        "n": len(values),
        "mean": float(np.mean(values)) if len(values) else None,
        "sd": float(np.std(values, ddof=1)) if len(values) > 1 else None,
    }


def _direction(stratum: str) -> str:
    return stratum.split("/", 1)[0]


# --- the items ---------------------------------------------------------------------------------


def _concordance(units: Sequence[Unit]) -> dict[str, object]:
    pairs = [u for u in units if u.reception.provider_line is not None]
    theirs = [float(u.reception.provider_line) for u in pairs]  # type: ignore[arg-type]
    line = line_module.concordance([u.depth[0] for u in pairs], theirs)
    deepest = line_module.concordance([u.deepest for u in pairs], theirs)
    r = line["pearson_r"]
    passed = isinstance(r, float) and r >= MIN_R and len(pairs) >= MIN_GROUP
    return {"line": line, "deepest_player": deepest, "pass": passed}


def _follows_ball(v0: Sequence[Unit]) -> dict[str, object]:
    raw = {
        name: [_raw(u) for u in v0 if _direction(u.stratum) == name]
        for name in ("backward", "forward", "lateral")
    }
    back, fwd = raw["backward"], raw["forward"]
    passed = (
        len(back) >= MIN_GROUP
        and len(fwd) >= MIN_GROUP
        and float(np.mean(back)) < 0
        and float(np.mean(fwd)) > 0
    )
    return {"by_direction": {k: _summary(v) for k, v in raw.items()}, "pass": passed}


def _crude(values: Sequence[float], pressed: Sequence[bool]) -> dict[str, object]:
    a = [v for v, p in zip(values, pressed, strict=True) if p]
    b = [v for v, p in zip(values, pressed, strict=True) if not p]
    if not a or not b:
        return {"m": None, "sd": None}
    d = float(np.mean(a) - np.mean(b))
    sd = float(np.std(values, ddof=1))
    return {"m": d, "sd": d / sd if sd > 0 else None}


def _pretrend(v0: Sequence[Unit]) -> dict[str, object]:
    pressed = [u.pressed for u in v0]
    strata = [u.stratum for u in v0]
    out: dict[str, object] = {}
    over = False
    for name, stat in (("raw", _raw), ("residual", _residual)):
        values = [stat(u) for u in v0]
        pooled = line_module.within_strata(values, pressed, strata, MIN_CELL)
        sd = pooled["sd"]
        over |= sd is None or abs(float(sd)) > MAX_PRETREND_SD  # type: ignore[arg-type]
        out[name] = {"within_strata": pooled, "crude": _crude(values, pressed)}
    out["over"] = over
    return out


def _velocity_item(v0: Sequence[Unit]) -> dict[str, object]:
    values = [_velocity(u) for u in v0]
    return {
        "pressed": _summary([v for v, u in zip(values, v0, strict=True) if u.pressed]),
        "free": _summary([v for v, u in zip(values, v0, strict=True) if not u.pressed]),
        "within_strata": {
            k: v
            for k, v in line_module.within_strata(
                values, [u.pressed for u in v0], [u.stratum for u in v0], MIN_CELL
            ).items()
            if k != "by_stratum"
        },
    }


def _distance_bin(d: float) -> str:
    return _DISTANCE_BINS[int(np.searchsorted(np.array(BALL_DISTANCE_EDGES), d, side="right"))]


def _visibility(match: MatchData, v0: Sequence[Unit]) -> dict[str, object]:
    seen = [
        line_module.seen_through(match, u.line, u.reception.frame - W, u.reception.frame + W)
        for u in v0
    ]
    whole = [s == LINE_SIZE for s in seen]

    def tally(keys: Sequence[str]) -> dict[str, object]:
        cells: dict[str, dict[str, int]] = {}
        for key, u, w in zip(keys, v0, whole, strict=True):
            row = cells.setdefault(
                key, {"v0_pressed": 0, "v0_free": 0, "v1_pressed": 0, "v1_free": 0}
            )
            group = "pressed" if u.pressed else "free"
            row[f"v0_{group}"] += 1
            row[f"v1_{group}"] += int(w)
        return dict(sorted(cells.items()))

    return {
        "v0": len(v0),
        "v1": sum(whole),
        "by_detected": {str(k): seen.count(k) for k in range(LINE_SIZE + 1)},
        "by_group": tally(["pressed" if u.pressed else "free" for u in v0]),
        "by_stratum": tally([u.stratum for u in v0]),
        "by_ball_distance": tally([_distance_bin(u.ball_to_line) for u in v0]),
    }


def _ball(match: MatchData, v0: Sequence[Unit]) -> dict[str, object]:
    window = [
        line_module.ball_extrapolated(match, u.reception.frame - W, u.reception.frame) for u in v0
    ]
    ends = [
        line_module.ball_extrapolated(match, u.reception.frame - W, u.reception.frame - W)
        or line_module.ball_extrapolated(match, u.reception.frame, u.reception.frame)
        for u in v0
    ]

    def share(flags: Sequence[bool]) -> float | None:
        return sum(flags) / len(flags) if flags else None

    return {
        "n": len(v0),
        "extrapolated_in_window": share(window),
        "extrapolated_at_ends": share(ends),
        "extrapolated_in_window_by_group": {
            group: share([w for w, u in zip(window, v0, strict=True) if u.pressed is flag])
            for group, flag in (("pressed", True), ("free", False))
        },
    }


def match_report(inputs: MatchInputs) -> dict[str, object]:
    """Every S2 figure of one match, with its instrument and pre-trend verdicts and m10's tables."""
    return _match_report(inputs, *line_module.build_units(inputs.match, inputs.receptions, LAGS))


def _match_report(
    inputs: MatchInputs, units: Sequence[Unit], dropped: Mapping[str, int]
) -> dict[str, object]:
    v0 = _v0(units)
    concordance = _concordance(units)
    follows = _follows_ball(v0)
    return {
        "counts": {
            "possessions": inputs.possessions,
            "receptions": len(inputs.receptions),
            "left_out": dropped,
            "line_at_t": len(units),
            "with_provider_line": sum(u.reception.provider_line is not None for u in units),
            "stratum_undefined": sum(u.stratum == "undefined" for u in units),
            "v0": len(v0),
        },
        "instrument": {
            "concordance": concordance,
            "follows_ball": follows,
            "pass": bool(concordance["pass"]) and bool(follows["pass"]),
        },
        "pretrend": _pretrend(v0),
        "velocity": _velocity_item(v0),
        "visibility": _visibility(inputs.match, v0),
        "ball": _ball(inputs.match, v0),
        "m10": {
            "ball": m10.ball_carrier(inputs.match, inputs.receptions),
            **m10.match_figures(units),
        },
    }


def verdict(
    instrument: Mapping[int, bool], over: Mapping[int, bool], v1: Mapping[int, int]
) -> dict[str, object]:
    """C2's verdict in the probe from the per-match items (the rule of the module docstring).

    ``c2_survives_probe`` is ``None`` unless all :data:`CALIBRATION_MATCHES` matches are given.
    """
    complete = all(len(x) == CALIBRATION_MATCHES for x in (instrument, over, v1))
    passed = sum(instrument.values())
    n_over = sum(over.values())
    short = sorted(m for m, n in v1.items() if n < MIN_V1)
    criteria = {
        "instrument": passed >= MIN_INSTRUMENT,
        "pretrend": n_over <= MAX_OVER,
        "visibility": not short,
    }
    return {
        "c2_survives_probe": all(criteria.values()) if complete else None,
        "complete": complete,
        "criteria": criteria,
        "instrument_passes": passed,
        "pretrend_over": n_over,
        "v1_short_matches": short,
        "per_match": {
            str(m): {"instrument": instrument[m], "pretrend_over": over[m], "v1": v1[m]}
            for m in sorted(instrument)
        },
        "thresholds": {
            "max_over": MAX_OVER,
            "max_pretrend_sd": MAX_PRETREND_SD,
            "min_group": MIN_GROUP,
            "min_instrument": MIN_INSTRUMENT,
            "min_r": MIN_R,
            "min_v1": MIN_V1,
        },
        "rule": (
            "C2 dies if the instrument (r >= min_r with the provider's line and the line "
            "following the incoming ball) passes in fewer than min_instrument matches, if the "
            "pre-trend within stratum (raw or residual) exceeds max_pretrend_sd sd in more than "
            "max_over matches, or if any match has fewer than min_v1 receptions with the whole "
            "line seen in [t - W, t + W]"
        ),
    }


def s2_report(inputs: Sequence[MatchInputs]) -> dict[str, object]:
    """The per-match figures, the verdict and the re-derivation of m10."""
    per_match: dict[int, dict[str, object]] = {}
    every_unit: list[Unit] = []
    for i in inputs:
        units, dropped = line_module.build_units(i.match, i.receptions, LAGS)
        per_match[i.match.match_id] = _match_report(i, units, dropped)
        every_unit += units
    possessions = sum(i.possessions for i in inputs)
    ten = set(per_match) == set(m10.M10_PER_MATCH)
    m10_figures = {m: r["m10"] for m, r in per_match.items()}
    return {
        "about": (
            "Probe S2 (C2): the last line at the reception against the provider's line, the "
            "line following the incoming ball, the pre-trend within incoming-ball strata, the "
            "line's velocity at t, the selection of V1 and the ball extrapolated before t. No "
            "outcome of any question: no position after the reception frame enters a figure; "
            "only the detection flags of the line in (t, t + W] are read there. The rule is in "
            "the docstring of ac2fb.defence.probe_s2."
        ),
        "constants": {
            "frame_seconds": FRAME_SECONDS,
            "lags_frames": list(LAGS),
            "line_size": LINE_SIZE,
            "pressed_radius_m": line_module.PRESSED_RADIUS,
            "velocity_frames": VELOCITY_FRAMES,
            "window_frames": W,
            "min_cell": MIN_CELL,
        },
        "matches": {str(m): r for m, r in per_match.items()},
        "m10_inventory": m10.compare(
            m10_figures,  # type: ignore[arg-type]
            m10.pooled_figures(every_unit, possessions) if ten else None,
        ),
        "verdict": verdict(
            {m: bool(r["instrument"]["pass"]) for m, r in per_match.items()},  # type: ignore[index]
            {m: bool(r["pretrend"]["over"]) for m, r in per_match.items()},  # type: ignore[index]
            {m: int(r["visibility"]["v1"]) for m, r in per_match.items()},  # type: ignore[index]
        ),
    }


def write_s2_report(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Read each match through the guarded door, write ``probe_s2.json`` (LF); return it."""
    report = s2_report([load_inputs(m) for m in match_ids])
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path
