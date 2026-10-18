"""Hand-made matches for the layer 2 tests: every number a test expects is built in here."""

from __future__ import annotations

from collections.abc import Sequence

import pyarrow as pa

from ac2fb.reliability.match import MatchData, build_match

MATCH_ID = 7

FRAME_COLUMNS = {
    "match_id": pa.string(),
    "native_match_id": pa.int64(),
    "period": pa.int16(),
    "frame_native": pa.int64(),
    "entity_id": pa.string(),
    "entity_kind": pa.string(),
    "team_id": pa.string(),
    "x_m": pa.float64(),
    "y_m": pa.float64(),
    "is_detected": pa.bool_(),
}
EVENT_COLUMNS = {
    "native_family": pa.string(),
    "native_subtype": pa.string(),
    "frame_start": pa.int64(),
    "frame_end": pa.int64(),
    "period": pa.int16(),
    "team_id": pa.string(),
    "player_id": pa.string(),
}

Row = tuple[int, float, float, bool]  # frame, x, y, is_detected


def frames_table(
    players: dict[int, Sequence[Row]], teams: dict[int, int], ball: Sequence[Row] = ()
) -> pa.Table:
    rows: list[dict[str, object]] = []
    for player, series in players.items():
        for frame, x, y, det in series:
            rows.append(_row(frame, f"fb:{player}", "player", f"fb:{teams[player]}", x, y, det))
    for frame, x, y, det in ball:
        rows.append(_row(frame, "fb:ball", "ball", None, x, y, det))
    cols = {name: [r[name] for r in rows] for name in FRAME_COLUMNS}
    return pa.table(cols, schema=pa.schema(list(FRAME_COLUMNS.items())))


def _row(
    frame: int, entity: str, kind: str, team: str | None, x: float, y: float, det: bool
) -> dict[str, object]:
    return {
        "match_id": f"fb:{MATCH_ID}",
        "native_match_id": MATCH_ID,
        "period": 1,
        "frame_native": frame,
        "entity_id": entity,
        "entity_kind": kind,
        "team_id": team,
        "x_m": x,
        "y_m": y,
        "is_detected": det,
    }


def event(
    family: str, start: int, end: int, team: int | None, player: int | None
) -> dict[str, object]:
    return {
        "native_family": family,
        "native_subtype": None,
        "frame_start": start,
        "frame_end": end,
        "period": 1,
        "team_id": None if team is None else f"fb:{team}",
        "player_id": None if player is None else f"fb:{player}",
    }


def make_match(
    players: dict[int, Sequence[Row]],
    teams: dict[int, int],
    *,
    ball: Sequence[Row] = (),
    events: Sequence[dict[str, object]] = (),
    signs: dict[int, int] | None = None,
) -> MatchData:
    """A one-period match. ``signs`` maps a team to the direction of x it attacks."""
    table = pa.table(
        {name: [e[name] for e in events] for name in EVENT_COLUMNS},
        schema=pa.schema(list(EVENT_COLUMNS.items())),
    )
    sides = signs or {}
    dims = pa.table(
        {
            "match_id": [f"fb:{MATCH_ID}"] * len(sides),
            "period": pa.array([1] * len(sides), pa.int16()),
            "team_id": [f"fb:{t}" for t in sides],
            "attack_sign": list(sides.values()),
        }
    )
    return build_match(MATCH_ID, frames_table(players, teams, ball), table, dims)


def line(frames: range, x: float, y: float, detected: bool = True) -> list[Row]:
    """A player standing still."""
    return [(f, x, y, detected) for f in frames]
