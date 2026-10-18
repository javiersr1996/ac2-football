"""The one door to the base's silver data, and the guard on the held-out matches.

Every read of the base's silver from ``ac2fb`` goes through this module: no other module of
the package imports ``ftbase`` or opens a Parquet file, and ``tests/test_single_door.py``
walks the code to keep it so. The readers (:func:`read_frames`, :func:`read_events`,
:func:`read_dim`, :func:`read_bronze_events` and :func:`read_bronze_phases`) take match ids,
look each one up in ``protocol/split.json`` and refuse a held-out id with
:class:`HeldOutLocked` before any file is opened. An id outside the split is refused too
(:class:`ValueError`). Calibration matches are served in every stage.

The held-out opens when, and only when, all of this holds in the git checkout the package runs
from (:func:`guard_status` says which part fails):

1. ``protocol/protocol.json``, as committed at ``HEAD``, is in stage ``frozen`` (the single
   reading) or ``read`` (the reading is committed; from then on it is reproduced);
2. :func:`code_tree_sha` at ``HEAD`` equals the ``code_tree_sha`` that file records, so
   everything that reaches the frozen code is frozen: the whole of ``src`` (this door and the
   CLI included), ``pyproject.toml`` and ``uv.lock`` (the pinned base and libraries) and
   ``.python-version`` (the interpreter);
3. the working tree is clean: ``git status`` lists nothing, untracked files included, and no
   tracked file is hidden from it by ``assume-unchanged`` or ``skip-worktree``.

The split and the stage are read from ``HEAD``, never from the working tree, so an uncommitted
edit cannot move a match into calibration or open the held-out.

Where the data lives: :func:`data_dir`.
"""

from __future__ import annotations

import hashlib
import json
import operator
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from ftbase import silver as _silver
from ftbase.bronze.common import bronze_path
from ftbase.silver.read import DimName

__all__ = [
    "DATA_ROOT_ENV",
    "GUARDED_CODE",
    "OPEN_STAGES",
    "GuardStatus",
    "HeldOutLocked",
    "Split",
    "code_tree_sha",
    "data_dir",
    "guard_status",
    "load_split",
    "read_bronze_events",
    "read_bronze_phases",
    "read_dim",
    "read_events",
    "read_frames",
]

DATA_ROOT_ENV = "FTBASE_DATA_ROOT"
SPLIT_PATH = "protocol/split.json"
PROTOCOL_PATH = "protocol/protocol.json"
# In the order of `git ls-tree`: the whole package and the three files that pin what runs it.
GUARDED_CODE: tuple[str, ...] = (".python-version", "pyproject.toml", "src", "uv.lock")
OPEN_STAGES: tuple[str, ...] = ("frozen", "read")
_ID_PREFIX = "fb:"  # silver's match_id is ``fb:<native_match_id>``


class HeldOutLocked(PermissionError):
    """A held-out match was asked for while the held-out is locked."""


@dataclass(frozen=True)
class Split:
    """The two sets of ``protocol/split.json``, as committed at ``HEAD``."""

    calibration: tuple[int, ...]
    heldout: tuple[int, ...]


@dataclass(frozen=True)
class GuardStatus:
    """The state the guard decides on; ``open`` is true when ``reasons`` is empty."""

    head: str | None
    stage: str | None
    frozen_code_tree_sha: str | None
    code_tree_sha: str | None
    dirty: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def open(self) -> bool:
        return not self.reasons


def _repo_root() -> Path:
    """The checkout this package runs from (``src/ac2fb/protocol/data.py`` is three below)."""
    return Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    """Where the base's data lives: ``$FTBASE_DATA_ROOT`` when set, else ``data/`` here.

    The variable is the base's own, so one setting moves what ``ftbase`` builds and what this
    package reads. Unset, it is ``data/`` at the root of this checkout (git-ignored), which is
    where ``uv run ftbase ...`` writes when run from that root.
    """
    value = os.environ.get(DATA_ROOT_ENV)
    return Path(value) if value else _repo_root() / "data"


def _git(*args: str) -> bytes:
    root = _repo_root()
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if done.returncode != 0:
        message = done.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {root}: {message}")
    return done.stdout


def _head() -> str:
    """HEAD's commit, after checking that the package runs from the top of its checkout."""
    top = Path(_git("rev-parse", "--show-toplevel").decode("utf-8").strip())
    if top.resolve() != _repo_root().resolve():
        raise RuntimeError(f"ac2fb reads data only from its own git checkout, not from {top}")
    return _git("rev-parse", "HEAD").decode("ascii").strip()


def _committed_json(commit: str, path: str) -> Any:
    return json.loads(_git("show", f"{commit}:{path}").decode("utf-8"))


def _ids(values: Iterable[Any]) -> tuple[int, ...]:
    return tuple(operator.index(v) for v in values)


def load_split() -> Split:
    """``protocol/split.json`` as committed at ``HEAD`` (the working tree copy is ignored)."""
    raw = _committed_json(_head(), SPLIT_PATH)
    split = Split(calibration=_ids(raw["calibration"]), heldout=_ids(raw["heldout"]))
    both = split.calibration + split.heldout
    if not split.calibration or not split.heldout or len(set(both)) != len(both):
        raise RuntimeError(f"{SPLIT_PATH} must hold two non-empty, disjoint sets of match ids")
    return split


def code_tree_sha(rev: str = "HEAD") -> str:
    """The sha256 of ``git ls-tree <rev> -- .python-version pyproject.toml src uv.lock``.

    That output names the git tree of ``src`` and the blob of each of the three files, so the
    hash changes with any byte of the package's code (``src/ac2fb`` whole: the analysis, this
    door and the CLI), of its dependencies as pinned (``pyproject.toml`` and ``uv.lock``, where
    the base's version lives) or of the interpreter pin, and with nothing else. From a shell::

        git ls-tree HEAD -- .python-version pyproject.toml src uv.lock | sha256sum
    """
    listing = _git("ls-tree", rev, "--", *GUARDED_CODE)
    names = [line.split("\t", 1)[-1] for line in listing.decode("utf-8").splitlines()]
    if names != list(GUARDED_CODE):
        raise RuntimeError(f"{rev} does not hold all of {GUARDED_CODE}: only {names}")
    return hashlib.sha256(listing).hexdigest()


def _dirty() -> tuple[str, ...]:
    """What keeps the working tree from being clean, one entry per path."""
    status = _git("status", "--porcelain", "--untracked-files=all").decode("utf-8").splitlines()
    # `ls-files -v` tags a tracked file `H`; `S` (skip-worktree) and lowercase tags
    # (assume-unchanged) mark files whose edits `git status` would not show.
    hidden = [
        f"hidden from git status: {line[2:]}"
        for line in _git("ls-files", "-v").decode("utf-8").splitlines()
        if not line.startswith("H ")
    ]
    return tuple(status + hidden)


def guard_status() -> GuardStatus:
    """Whether the held-out is open, and every reason it is not."""
    head: str | None = None
    stage: Any = None
    frozen: Any = None
    current: str | None = None
    dirty: tuple[str, ...] = ()
    try:
        head = _head()
        protocol = _committed_json(head, PROTOCOL_PATH)
        stage, frozen = protocol.get("stage"), protocol.get("code_tree_sha")
        current = code_tree_sha(head)
        dirty = _dirty()
    except (RuntimeError, ValueError, AttributeError) as exc:
        return GuardStatus(head, stage, frozen, current, dirty, (f"cannot check: {exc}",))
    reasons: list[str] = []
    if stage not in OPEN_STAGES:
        reasons.append(f"{PROTOCOL_PATH} at HEAD is in stage {stage!r}, not one of {OPEN_STAGES}")
    if not isinstance(frozen, str) or frozen != current:
        reasons.append(
            f"code_tree_sha of {' and '.join(GUARDED_CODE)} at HEAD is {current}; "
            f"the protocol records {frozen}"
        )
    if dirty:
        reasons.append(f"the working tree is not clean ({len(dirty)}: {list(dirty[:3])})")
    return GuardStatus(head, stage, frozen, current, dirty, tuple(reasons))


def _admit(match_ids: Sequence[int]) -> list[int]:
    """The ids, sorted and unique, once every one of them may be read."""
    ids = sorted(set(_ids(match_ids)))
    if not ids:
        raise ValueError("name at least one match id")
    split = load_split()
    unknown = [m for m in ids if m not in split.calibration and m not in split.heldout]
    if unknown:
        raise ValueError(f"match(es) {unknown} are not in {SPLIT_PATH}")
    held = [m for m in ids if m in split.heldout]
    if held:
        status = guard_status()
        if not status.open:
            raise HeldOutLocked(f"held-out match(es) {held} refused: " + "; ".join(status.reasons))
    return ids


def read_frames(
    match_ids: Sequence[int], *, columns: Sequence[str] | None = None, attacking: bool = False
) -> pa.Table:
    """Silver frames of the given matches: :func:`ftbase.silver.read_frames`, guarded.

    The columns, the order and ``attacking`` are the base's (its docstring holds the
    contract); the data come from :func:`data_dir`.
    """
    ids = _admit(match_ids)
    return _silver.read_frames(ids, columns=columns, attacking=attacking, data_dir=data_dir())


def read_events(match_ids: Sequence[int], *, columns: Sequence[str] | None = None) -> pa.Table:
    """Silver events of the given matches: :func:`ftbase.silver.read_events`, guarded."""
    ids = _admit(match_ids)
    return _silver.read_events(ids, columns=columns, data_dir=data_dir())


def read_bronze_events(
    match_ids: Sequence[int], *, columns: Sequence[str] | None = None
) -> pa.Table:
    """The provider's own event columns (bronze ``dynamic_events``) of the given matches, guarded.

    Silver keeps only the columns that mean the same in every event family; the rest, such as
    the provider's pressure label, stay in bronze and join back to a silver event on
    ``(native_match_id, native_family, native_event_id)``, which is bronze's
    ``(match_id, event_type, event_id)``. Rows are in file order; the files of the matches are
    stacked in ascending id order. Only the files of the admitted matches are opened.
    """
    ids = _admit(match_ids)
    cols = None if columns is None else list(columns)
    files = [bronze_path(data_dir(), "football", "dynamic_events", m) for m in ids]
    return pa.concat_tables([pq.read_table(f, columns=cols) for f in files])


def read_bronze_phases(
    match_ids: Sequence[int], *, columns: Sequence[str] | None = None
) -> pa.Table:
    """The provider's own ``phases_of_play`` columns (bronze) of the given matches, guarded.

    Silver keeps a phase as an event without the provider's block width and length at its
    start; they stay in bronze. Rows are in file order; the files of the matches are stacked in
    ascending id order. Only the files of the admitted matches are opened.
    """
    ids = _admit(match_ids)
    cols = None if columns is None else list(columns)
    files = [bronze_path(data_dir(), "football", "phases_of_play", m) for m in ids]
    return pa.concat_tables([pq.read_table(f, columns=cols) for f in files])


def _keep(table: pa.Table, column: str, values: Iterable[str]) -> pa.Table:
    return table.filter(pc.is_in(table[column], value_set=pa.array(sorted(values), pa.string())))


def read_dim(name: DimName, match_ids: Sequence[int]) -> pa.Table:
    """One silver dimension, cut to the rows of the given matches.

    The base keeps each dimension in one file for every match, so the file is read whole and
    only the rows of ``match_ids`` come back: by ``match_id`` where the dimension has one,
    the two teams of those matches for ``dim_team``; ``dim_sport`` holds no match and comes
    back whole.
    """
    ids = _admit(match_ids)
    keys = {f"{_ID_PREFIX}{m}" for m in ids}
    table = _silver.read_dim(name, data_dir=data_dir())
    if "match_id" in table.column_names:
        return _keep(table, "match_id", keys)
    if name == "dim_team":
        matches = _keep(_silver.read_dim("dim_match", data_dir=data_dir()), "match_id", keys)
        teams = matches["home_team_id"].to_pylist() + matches["away_team_id"].to_pylist()
        return _keep(table, "team_id", teams)
    return table
