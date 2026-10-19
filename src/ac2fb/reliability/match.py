"""One match as arrays: the players of the long table, the ball, the events and the sides.

:func:`load_match` reads through the guarded door (:mod:`ac2fb.protocol.data`), so a held-out
match is refused there; :func:`build_match` takes the tables and does not read anything. Player
rows are sorted by player and frame; ``locate_rows`` and ``players_at`` find rows in them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
from numpy.typing import NDArray

from ac2fb.protocol import data
from ac2fb.reliability.long import long_table

__all__ = [
    "Event",
    "MatchData",
    "build_match",
    "load_match",
    "locate_rows",
    "players_at",
]

_FRAME_SPAN = 1 << 32  # key = player * span + frame; frames and player ids fit in 32 bits
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
    "frame_start",
    "frame_end",
    "period",
    "team_id",
    "player_id",
]


@dataclass(frozen=True)
class Event:
    """A provider event: ``family`` is its native family (``on_ball_engagement``, ...)."""

    family: str
    subtype: str | None
    frame_start: int
    frame_end: int
    period: int
    team: int | None
    player: int | None


@dataclass(frozen=True)
class MatchData:
    """The arrays of one match.

    Player rows (``player``, ``team``, ``period``, ``frame``, ``x``, ``y``, ``detected``,
    ``gap``) are sorted by player and frame; ``gap`` is ``gap_len`` (-1: none in the period).
    ``key`` is ``player * 2**32 + frame``, sorted. ``frame_order`` lists the player rows by
    frame and ``frame_sorted`` their frames. The ball has its own rows, sorted by frame, with
    their period (``ball_period``: the break between periods can be shorter than a window).
    ``attack_sign`` maps ``(period, team)`` to +1 or -1: the direction of x the team attacks.
    """

    match_id: int
    player: NDArray[np.int64]
    team: NDArray[np.int64]
    period: NDArray[np.int64]
    frame: NDArray[np.int64]
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    detected: NDArray[np.bool_]
    gap: NDArray[np.int64]
    key: NDArray[np.int64]
    frame_order: NDArray[np.int64]
    frame_sorted: NDArray[np.int64]
    ball_frame: NDArray[np.int64]
    ball_period: NDArray[np.int64]
    ball_x: NDArray[np.float64]
    ball_y: NDArray[np.float64]
    ball_detected: NDArray[np.bool_]
    ball_gap: NDArray[np.int64]
    events: tuple[Event, ...]
    attack_sign: dict[tuple[int, int], int]


def _number(column: pa.ChunkedArray, dtype: type) -> NDArray[Any]:
    return np.asarray(column.to_numpy(), dtype=dtype)


def _strip(value: str | None) -> int | None:
    return None if value is None else int(value.split(":", 1)[1])


def _events(table: pa.Table) -> tuple[Event, ...]:
    rows = table.select(_EVENT_COLUMNS).to_pylist()
    return tuple(
        Event(
            family=r["native_family"],
            subtype=r["native_subtype"],
            frame_start=r["frame_start"],
            frame_end=r["frame_end"],
            period=r["period"],
            team=_strip(r["team_id"]),
            player=_strip(r["player_id"]),
        )
        for r in rows
    )


def build_match(
    match_id: int, frames: pa.Table, events: pa.Table, team_periods: pa.Table
) -> MatchData:
    """Arrays of one match from its silver frames, events and ``dim_team_period`` rows."""
    if set(frames["native_match_id"].to_pylist()) != {match_id}:
        raise ValueError(f"frames hold rows other than match {match_id}")
    long = long_table(frames)
    is_player = pc.is_valid(long["player_id"])
    players = long.filter(is_player)
    ball = long.filter(pc.invert(is_player))
    player = _number(players["player_id"], np.int64)
    frame = _number(players["frame"], np.int64)
    order = np.argsort(frame, kind="stable")
    signs = {
        (int(r["period"]), int(_strip(r["team_id"]) or 0)): int(r["attack_sign"])
        for r in team_periods.to_pylist()
    }
    return MatchData(
        match_id=match_id,
        player=player,
        team=_number(players["team_id"], np.int64),
        period=_number(players["period"], np.int64),
        frame=frame,
        x=_number(players["x"], np.float64),
        y=_number(players["y"], np.float64),
        detected=_number(players["is_detected"], np.bool_),
        gap=_number(pc.fill_null(players["gap_len"], -1), np.int64),
        key=player * _FRAME_SPAN + frame,
        frame_order=order,
        frame_sorted=frame[order],
        ball_frame=_number(ball["frame"], np.int64),
        ball_period=_number(ball["period"], np.int64),
        ball_x=_number(ball["x"], np.float64),
        ball_y=_number(ball["y"], np.float64),
        ball_detected=_number(ball["is_detected"], np.bool_),
        ball_gap=_number(pc.fill_null(ball["gap_len"], -1), np.int64),
        events=_events(events),
        attack_sign=signs,
    )


def load_match(match_id: int) -> MatchData:
    """Read one match through the guarded door and build its arrays.

    Raises :class:`~ac2fb.protocol.data.HeldOutLocked` for a held-out match while locked.
    """
    ids = [match_id]
    return build_match(
        match_id,
        data.read_frames(ids, columns=_FRAME_COLUMNS),
        data.read_events(ids, columns=_EVENT_COLUMNS),
        data.read_dim("dim_team_period", ids),
    )


def locate_rows(
    match: MatchData, players: NDArray[np.int64], frames: NDArray[np.int64]
) -> NDArray[np.int64]:
    """Row index of each ``(player, frame)`` pair in the player rows, -1 where there is none."""
    wanted = players.astype(np.int64) * _FRAME_SPAN + frames.astype(np.int64)
    pos = np.searchsorted(match.key, wanted)
    safe = np.minimum(pos, len(match.key) - 1)
    return np.where((pos < len(match.key)) & (match.key[safe] == wanted), pos, -1)


def players_at(match: MatchData, frame: int) -> NDArray[np.int64]:
    """Indices of the player rows of one frame (every player the provider lists there)."""
    lo = np.searchsorted(match.frame_sorted, frame, side="left")
    hi = np.searchsorted(match.frame_sorted, frame, side="right")
    return match.frame_order[lo:hi]
