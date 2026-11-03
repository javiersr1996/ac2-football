"""The page's second reception: the earliest of the match whose units all count in V1.

The page draws the video's reception (``ac2fb.clip.choose``, ``reports/clip/clip.json``), which
counts for V0 only: its back four were all filled in. This module picks a second reception of the
same match, one that counts in V1, by a rule written here and committed before any candidate was
looked at (:func:`describe` puts it in words, with its numbers, into the page's sidecar). It lives
in ``scripts/`` because ``src/`` is frozen (``GUARDED_CODE`` of ``ac2fb.protocol.data``); it
reuses the clip's window (``clip._complete``, ``clip._scene``) and layer 2's units
(``ac2fb.reliability.metrics.metric_units``), so the window and the units are theirs, not copies.

What "counts in V1" means is ``ac2fb.reliability.sensitivity``'s (``_one_match``): a unit is a
window for which the metric returns a reading, and it counts in V1 when every player of the
reading has a row in the window and is present and detected in every frame of it
(:func:`counts_in_v1`). A reading of no player (a pressure with no rival within its radius) counts,
as it does there. The four units are the ones the page draws (:data:`UNITS`), each a one-frame
window as ``metric_units`` has it: the line, the pressure and the nearest rival at the reception,
the block at the start of the phase of play that holds it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ac2fb import clip
from ac2fb.reliability import metrics
from ac2fb.reliability.match import Event, MatchData, locate_rows, players_at
from ac2fb.reliability.sensitivity import Metric, Reading, Window, WindowFrames

__all__ = [
    "REASONS",
    "UNITS",
    "Found",
    "NoReception",
    "choose",
    "counts_in_v1",
    "describe",
    "holding",
    "reading",
]

#: The units the page draws: its name for each, the layer 2 metric, and where it is read (the
#: reception's frame, or the first frame of the phase of play that holds the reception).
UNITS: tuple[tuple[str, str, str], ...] = (
    ("line", "line_height_m", "reception"),
    ("block", "block_length_m", "phase"),
    ("pressure", "pressure_index", "reception"),
    ("nearest", "nearest_rival_m", "reception"),
)
#: Why a reception was turned down, in the order the rule tests: the clip's candidates (receiver,
#: ball and enough rivals detected), the clip's window, the camera's corners, the phase, a unit
#: with no reading, a unit that does not count in V1.
REASONS = ("seen", "window", "corners", "phase", "unit", "v1")

Windows = Callable[[Window], WindowFrames | None]
Corners = Callable[[NDArray[np.int64]], bool]


class NoReception(ValueError):
    """No reception of the match passes the rule."""


@dataclass(frozen=True)
class Found:
    """The reception the rule picks: the clip's scene of it, the phase that holds it, its units
    (name to frame, the window's matrices and the reading) and how many receptions before it, in
    the rule's order, were turned down and why (:data:`REASONS`)."""

    scene: clip.Scene
    phase: Event
    units: dict[str, tuple[int, WindowFrames, Reading]]
    rejected: dict[str, int]


def describe(rule: clip.Rule = clip.DEFAULT_RULE) -> str:
    """The rule in words, with its numbers: it goes into the sidecar."""
    at = [m for _, m, where in UNITS if where == "reception"]
    phase = [m for _, m, where in UNITS if where == "phase"]
    return (
        "Receptions are the player_possession events with a team and a player whose receiver and "
        f"the ball are detected at the first frame and with at least {rule.min_seen} rivals "
        "detected there, as in the clip's rule, taken by period and frame, the earliest first. "
        "The first that passes three tests wins. Its window is the clip's and is complete: "
        f"{rule.frames} frames at {clip.HZ} Hz from {rule.before} frames before the reception, "
        "inside one period, with the receiver, the ball and each rival present and each rival "
        "with a gap_len in every frame, and the camera's four corners in every frame. Exactly one "
        "phases_of_play event of the receiver's team holds the reception, and it starts inside "
        "the window. Each unit the page draws is a unit of layer 2 that counts in V1, as "
        "ac2fb.reliability.sensitivity counts V1 (every player the metric reads listed and "
        "detected at the unit's frame; a unit that reads no player counts): "
        f"{', '.join(at[:-1])} and {at[-1]} at the reception, {' and '.join(phase)} at the start "
        "of that phase. Defenders are the receiver's rivals, goalkeeper included."
    )


def counts_in_v1(frames: WindowFrames, found: Reading) -> bool:
    """Whether a unit counts in V1, as ``sensitivity._one_match`` decides it."""
    index = {int(p): i for i, p in enumerate(frames.player_ids)}
    mine = [index[p] for p in found.player_ids if p in index]
    whole = frames.present[mine].all(axis=1) & frames.detected[mine].all(axis=1)
    return len(mine) == len(found.player_ids) and bool(whole.all())


def holding(match: MatchData, team: int, period: int, frame: int) -> list[Event]:
    """The phases of play of ``team`` in ``period`` that hold ``frame``."""
    return [
        e
        for e in metrics.phases(match.events)
        if e.team == team and e.period == period and e.frame_start <= frame <= e.frame_end
    ]


def reading(
    units_of: Mapping[str, tuple[Metric, list[Window]]],
    windows: Windows,
    match_id: int,
    metric: str,
    frame: int,
) -> tuple[WindowFrames, Reading] | None:
    """The unit of ``metric`` at ``frame`` (a one-frame window, as ``metric_units`` has it): the
    window's matrices and the reading, or None where the metric gives none."""
    fn, _ = units_of[metric]
    frames = windows(Window(match_id, frame, frame))
    found = None if frames is None else fn(frames)
    return None if frames is None or found is None else (frames, found)


def _verdict(
    match: MatchData,
    windows: Windows,
    corners: Corners,
    units_of: Mapping[str, tuple[Metric, list[Window]]],
    rule: clip.Rule,
    e: Event,
) -> tuple[str, None] | tuple[None, Found]:
    """Why the rule turns ``e`` down (a reason of :data:`REASONS`), or what it found."""
    assert e.player is not None and e.team is not None
    key = e.frame_start
    car = locate_rows(match, np.array([e.player]), np.array([key]))[0]
    ball = int(np.searchsorted(match.ball_frame, key))
    if car < 0 or not match.detected[car] or ball >= len(match.ball_frame):
        return "seen", None
    if match.ball_frame[ball] != key or not match.ball_detected[ball]:
        return "seen", None
    rows = players_at(match, key)
    rival = rows[match.team[rows] != e.team]
    if int(match.detected[rival].sum()) < rule.min_seen:
        return "seen", None
    ids = np.sort(match.player[rival])
    frames = np.arange(key - rule.before, key - rule.before + rule.frames, dtype=np.int64)
    window = clip._complete(match, frames, e.period, e.player, ids)
    if window is None:
        return "window", None
    if not corners(frames):
        return "corners", None
    team = int(match.team[car])
    held = holding(match, team, e.period, key)
    if len(held) != 1 or not frames[0] <= held[0].frame_start <= frames[-1]:
        return "phase", None
    units: dict[str, tuple[int, WindowFrames, Reading]] = {}
    for name, metric, where in UNITS:
        frame = key if where == "reception" else held[0].frame_start
        got = reading(units_of, windows, match.match_id, metric, frame)
        if got is None:
            return "unit", None
        if not counts_in_v1(*got):
            return "v1", None
        units[name] = (frame, *got)
    scene = clip._scene(match, rule, e.period, key, e.player, team, e.subtype, frames, ids, window)
    return None, Found(scene, held[0], units, {})


def choose(
    match: MatchData, windows: Windows, corners: Corners, rule: clip.Rule = clip.DEFAULT_RULE
) -> Found:
    """The reception the rule picks (:func:`describe`); :class:`NoReception` if none passes.

    ``windows`` gives the matrices of a window of the match (``sensitivity.window_frames`` of its
    long table); ``corners`` says whether the camera's frame has its four corners in every frame
    of a window (the page cannot draw a frame without them).
    """
    units_of = metrics.metric_units(match)
    rejected = dict.fromkeys(REASONS, 0)
    candidates = sorted(
        (
            e
            for e in match.events
            if e.family == "player_possession" and e.player is not None and e.team is not None
        ),
        key=lambda e: (e.period, e.frame_start),
    )
    for e in candidates:
        why, found = _verdict(match, windows, corners, units_of, rule, e)
        if found is not None:
            return Found(found.scene, found.phase, found.units, rejected)
        assert why is not None
        rejected[why] += 1
    raise NoReception(
        f"no reception of match {match.match_id} passes the rule ({len(candidates)} looked at: "
        + ", ".join(f"{k} {v}" for k, v in rejected.items())
        + ")"
    )
