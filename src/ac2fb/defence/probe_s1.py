"""Probe S1 (candidate C1): does the geometric pressure index track the provider's pressure label?

The probe measures the instrument and what comes before the reception. It computes no outcome
of any candidate: nothing at a frame after ``t`` (the reception) is read, and the strata are
counts of the incoming ball in ``[t - W, t]``. The index is defined in
:mod:`ac2fb.defence.pressure`.

**Forced-direction contrast and the rule that kills C1 in the probe (written before the data
was read).** The provider labels each reception ``no_pressure``, ``low``, ``medium``, ``high``
or ``very_high`` (``overall_pressure_start``, ids 1 to 5). A pressure index that means pressure
must grow with the label. For each match, the median index among the receptions of each level
must be strictly increasing over the five levels, ``no < low < medium < high < very_high``
(each median above the one before by more than 1e-9, so rounding noise is not an increase),
and every level must hold at least :data:`MIN_PER_LEVEL` receptions (a match that cannot fill
a level cannot show the increase and counts as a failure). **C1 survives the probe if at least
:data:`MIN_MATCHES` of the :data:`CALIBRATION_MATCHES` calibration matches pass; if not, C1 dies
in the probe.** The thresholds are not moved after the data is read. The label is only a
contrast of the instrument, never an outcome. The verdict is on the whole population of
labelled receptions (variant V0); the same contrast on the receptions whose near rivals are
all detected (V1) is reported beside it and decides nothing.

**What enters.** Receptions with a provider pressure label, a carrier row at ``t``, a known
attack direction for the carrier's team in that period, and at least one rival row at ``t``.
Variant V0 is all of them; V1 and V2 come from :func:`ac2fb.reliability.sensitivity.sensitivity`
with one-frame windows and the rivals within 10 m as the players behind each unit.

**Extrapolated share.** The part of the summed index carried by rivals with ``is_detected``
false at ``t`` (overall and by level), and the share of receptions with some near rival
extrapolated.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from ac2fb.defence import pressure
from ac2fb.defence.pressure import LEVELS, Reception, Scored
from ac2fb.protocol import data
from ac2fb.reliability.long import long_table
from ac2fb.reliability.match import MatchData, build_match
from ac2fb.reliability.report import JsonCheck, check_json, render_report
from ac2fb.reliability.sensitivity import Window, sensitivity

__all__ = [
    "CALIBRATION_MATCHES",
    "MIN_MATCHES",
    "MIN_PER_LEVEL",
    "REPORT_NAME",
    "MatchInputs",
    "load_inputs",
    "check",
    "match_report",
    "receptions_from",
    "s1_report",
    "verdict",
    "write_s1_report",
]

REPORT_NAME = "probe_s1.json"
CALIBRATION_MATCHES = 10
MIN_MATCHES = 9
MIN_PER_LEVEL = 10

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
_BRONZE_COLUMNS = ["event_id", "event_type", "overall_pressure_start", "overall_pressure_start_id"]


@dataclass(frozen=True)
class MatchInputs:
    """One match ready to score: its arrays, its long table and its labelled receptions."""

    match: MatchData
    long: pa.Table
    receptions: tuple[Reception, ...]
    possessions: int  # player_possession events, labelled or not


def _native(value: str | None) -> int | None:
    return None if value is None else int(value.split(":", 1)[1])


def receptions_from(events: pa.Table, bronze: pa.Table) -> tuple[int, list[Reception]]:
    """The labelled receptions, and how many ``player_possession`` events there were.

    ``events`` are the silver events, ``bronze`` the provider's ``dynamic_events`` with its
    pressure label; they join on silver's ``native_event_id`` = bronze's ``event_id``. An event
    without a label, a player or a team is not a reception here. Two receptions in the same
    frame of a period are an error (the metric is keyed by frame).
    """
    labels: dict[str, tuple[int, str]] = {}
    for row in bronze.filter(pc.equal(bronze["event_type"], "player_possession")).to_pylist():
        if row["overall_pressure_start_id"] is not None:
            labels[row["event_id"]] = (
                int(row["overall_pressure_start_id"]),
                row["overall_pressure_start"],
            )
    mine = events.filter(pc.equal(events["native_family"], "player_possession")).to_pylist()
    found: list[Reception] = []
    seen: set[tuple[int, int]] = set()
    for row in mine:
        label = labels.get(row["native_event_id"])
        player, team = _native(row["player_id"]), _native(row["team_id"])
        if label is None or player is None or team is None:
            continue
        if LEVELS.get(label[0]) != label[1]:
            raise ValueError(f"pressure id {label[0]} comes with the label {label[1]!r}")
        key = (row["period"], row["frame_start"])
        if key in seen:
            raise ValueError(f"two receptions start at frame {key[1]} of period {key[0]}")
        seen.add(key)
        found.append(
            Reception(
                event_id=row["native_event_id"],
                period=row["period"],
                frame=row["frame_start"],
                team=team,
                player=player,
                level=label[0],
            )
        )
    return len(mine), found


def load_inputs(match_id: int) -> MatchInputs:
    """Read one match through the guarded door (the bronze reader included) and prepare it.

    Raises :class:`~ac2fb.protocol.data.HeldOutLocked` for a held-out match while locked.
    """
    ids = [match_id]
    frames = data.read_frames(ids, columns=_FRAME_COLUMNS)
    events = data.read_events(ids, columns=_EVENT_COLUMNS)
    bronze = data.read_bronze_events(ids, columns=_BRONZE_COLUMNS)
    team_periods = data.read_dim("dim_team_period", ids)
    possessions, found = receptions_from(events, bronze)
    return MatchInputs(
        match=build_match(match_id, frames, events, team_periods),
        long=long_table(frames),
        receptions=tuple(found),
        possessions=possessions,
    )


def match_report(inputs: MatchInputs) -> dict[str, object]:
    """Every S1 figure of one match: contrast, extrapolated share, sensitivity and strata."""
    match = inputs.match
    scored: list[Scored] = pressure.score_receptions(match, inputs.receptions)
    kept = [s.reception for s in scored]
    windows = [Window(match.match_id, r.frame, r.frame) for r in kept]
    sens = sensitivity(pressure.make_metric(match, kept), inputs.long, windows)[match.match_id]
    all_seen = [s for s in scored if all(s.near_detected)]
    return {
        "contrast": pressure.level_contrast(scored, MIN_PER_LEVEL),
        "contrast_v1": pressure.level_contrast(all_seen, MIN_PER_LEVEL),
        "extrapolated_share": pressure.extrapolated_share(scored),
        "incoming_ball": pressure.stratum_counts(scored),
        "receptions": {
            "carrier_detected": (
                sum(s.carrier_detected for s in scored) / len(scored) if scored else None
            ),
            "labelled": len(inputs.receptions),
            "left_out": len(inputs.receptions) - len(scored),
            "possessions": inputs.possessions,
            "scored": len(scored),
            "unlabelled": inputs.possessions - len(inputs.receptions),
        },
        "sensitivity": dataclasses.asdict(sens),
    }


def verdict(increasing: Mapping[int, bool]) -> dict[str, object]:
    """C1's verdict in the probe from the per-match contrast (the rule of the module docstring).

    ``c1_survives_probe`` is ``None`` unless all :data:`CALIBRATION_MATCHES` matches are given.
    """
    passed = sum(increasing.values())
    complete = len(increasing) == CALIBRATION_MATCHES
    return {
        "c1_survives_probe": passed >= MIN_MATCHES if complete else None,
        "complete": complete,
        "matches_increasing": passed,
        "min_matches": MIN_MATCHES,
        "min_per_level": MIN_PER_LEVEL,
        "n_matches": len(increasing),
        "per_match": {str(k): v for k, v in sorted(increasing.items())},
        "rule": (
            "median index strictly increasing over the five levels of overall_pressure_start, "
            "at least min_per_level receptions in each level, in at least min_matches of the "
            "calibration matches; otherwise C1 dies in the probe"
        ),
    }


def s1_report(inputs: Sequence[MatchInputs]) -> dict[str, object]:
    """The per-match figures and the verdict."""
    per_match = {i.match.match_id: match_report(i) for i in inputs}
    increasing = {m: bool(r["contrast"]["increasing"]) for m, r in per_match.items()}  # type: ignore[index]
    return {
        "about": (
            "Probe S1 (C1): the geometric pressure index at the reception against the "
            "provider's pressure label, its extrapolated share and the incoming-ball strata. "
            "No outcome of any question: nothing after the reception frame. The rule and the "
            "index are in the docstrings of ac2fb.defence.probe_s1 and ac2fb.defence.pressure."
        ),
        "constants": {
            "goal_x": pressure.GOAL_X,
            "incoming_window_frames": pressure.INCOMING_WINDOW,
            "long_ball_m": pressure.LONG_BALL,
            "radius_m": pressure.RADIUS,
            "third_cut_m": pressure.THIRD_CUT,
        },
        "matches": {str(m): r for m, r in per_match.items()},
        "verdict": verdict(increasing),
    }


def write_s1_report(match_ids: Sequence[int], reports_dir: Path) -> Path:
    """Read each match through the guarded door, write ``probe_s1.json`` (LF); return it."""
    report = s1_report([load_inputs(m) for m in match_ids])
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / REPORT_NAME
    path.write_bytes(render_report(report).encode("utf-8"))
    return path


def check(match_ids: Sequence[int], raw: bytes | None) -> JsonCheck:
    """Recompute ``probe_s1.json`` of the matches and compare every value with ``raw``."""
    return check_json(
        REPORT_NAME, lambda: render_report(s1_report([load_inputs(m) for m in match_ids])), raw
    )
