"""The one door to the base's silver data, and the guard on the held-out matches.

Every read of the base's silver from ``ac2fb`` goes through this module: no other module of
the package imports ``ftbase`` or opens a Parquet file, and ``tests/test_single_door.py``
walks the code to keep it so. The readers (:func:`read_frames`, :func:`read_events`,
:func:`read_dim`, :func:`read_bronze_events`, :func:`read_bronze_phases`,
:func:`read_bronze_players` and :func:`read_bronze_frames`) take match ids, look each one up
in ``protocol/split.json`` and refuse a held-out id with :class:`HeldOutLocked` before any file
is opened. An id outside the split is refused too (:class:`ValueError`). Calibration matches are
served in every stage.

Layer 3 died in calibration (``protocol/protocol.json`` in stage ``dead``, D5, branch B), so
the held-out is read once, for layer 2 only, under ``protocol/layer2.json``. It is served
only inside :func:`read_heldout` (the command ``ac2fb heldout read``), which runs the layer 2
commands that file lists and nothing else, and only when all of this holds in the git checkout
the package runs from (:func:`guard_status` says which part fails):

1. ``protocol/protocol.json``, as committed at ``HEAD``, is in stage ``dead``;
2. ``protocol/layer2.json``, as committed at ``HEAD``, is in stage ``read``: the reading is
   committed before any figure is computed, and from then on it is reproduced. In ``frozen``
   the held-out never opens: :func:`read_heldout` moves it to ``read`` first;
3. :func:`code_tree_sha` at ``HEAD`` equals the ``code_tree_sha`` that ``layer2.json``
   records, so everything that reaches the frozen code is frozen: the whole of ``src`` (this
   door and the CLI included), ``pyproject.toml`` and ``uv.lock`` (the pinned base and
   libraries) and ``.python-version`` (the interpreter);
4. the history holds the freeze and at most one reading (:func:`_freeze`): the code and
   ``protocol/`` are those of the freeze, the last commit that moved ``layer2.json`` to
   ``frozen``, and in ``read`` the reading is the one commit since that changed them, only in
   ``layer2.json``, so editing that file after the reading shuts the held-out;
5. the working tree is clean: ``git status`` lists nothing, untracked files included, and no
   tracked file is hidden from it by ``assume-unchanged`` or ``skip-worktree``.

Outside :func:`read_heldout`, every route refuses the held-out in every stage. The split and
the stages are read from ``HEAD``, never from the working tree, so an uncommitted edit cannot
move a match into calibration or open the held-out.

Where the data lives: :func:`data_dir`.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import operator
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from ftbase import silver as _silver
from ftbase.bronze.common import bronze_path
from ftbase.silver.read import DimName

from ac2fb.protocol import lock

__all__ = [
    "DATA_ROOT_ENV",
    "GUARDED_CODE",
    "OPEN_STAGES",
    "READ_MESSAGE",
    "GuardStatus",
    "HeldOutLocked",
    "HeldOutReading",
    "Split",
    "code_tree_sha",
    "data_dir",
    "guard_status",
    "load_split",
    "read_bronze_events",
    "read_bronze_frames",
    "read_bronze_phases",
    "read_bronze_players",
    "read_dim",
    "read_events",
    "read_frames",
    "read_heldout",
]

DATA_ROOT_ENV = "FTBASE_DATA_ROOT"
SPLIT_PATH = "protocol/split.json"
PROTOCOL_PATH = "protocol/protocol.json"
LAYER2_PATH = "protocol/layer2.json"
# In the order of `git ls-tree`: the whole package and the three files that pin what runs it.
GUARDED_CODE: tuple[str, ...] = (".python-version", "pyproject.toml", "src", "uv.lock")
# The stages of layer2.json in which the held-out is served (inside the reading only).
OPEN_STAGES: tuple[str, ...] = ("read",)
_READABLE_STAGES = ("frozen", "read")  # the stages read_heldout starts from
_LAYER3_DEAD = "dead"
READ_MESSAGE = "Read the held-out for layer 2: the single reading"
_ID_PREFIX = "fb:"  # silver's match_id is ``fb:<native_match_id>``
# True only while read_heldout runs the commands of layer2.json.
_READING: ContextVar[bool] = ContextVar("ac2fb_reading_heldout", default=False)

# A layer 2 command of the reading: it takes the held-out ids and the reports directory and
# returns the artefact it wrote.
Command = Callable[[list[int], Path], Path]


class HeldOutLocked(PermissionError):
    """A held-out match was asked for while the held-out is locked."""


@dataclass(frozen=True)
class Split:
    """The two sets of ``protocol/split.json``, as committed at ``HEAD``."""

    calibration: tuple[int, ...]
    heldout: tuple[int, ...]


@dataclass(frozen=True)
class GuardStatus:
    """The state the guard decides on; ``open`` is true when ``reasons`` is empty.

    ``stage`` and ``frozen_code_tree_sha`` are those of ``protocol/layer2.json``;
    ``protocol_stage`` is the stage of ``protocol/protocol.json`` (layer 3); ``frozen_commit``
    is the commit of the freeze (:func:`_freeze`). Open means the held-out may be served inside
    :func:`read_heldout`, and nowhere else.
    """

    head: str | None
    protocol_stage: str | None
    stage: str | None
    frozen_code_tree_sha: str | None
    code_tree_sha: str | None
    dirty: tuple[str, ...]
    reasons: tuple[str, ...]
    frozen_commit: str | None = None

    @property
    def open(self) -> bool:
        return not self.reasons


@dataclass(frozen=True)
class HeldOutReading:
    """What :func:`read_heldout` did: the commit of the reading and the artefacts written."""

    commit: str
    frozen_commit: str
    heldout: tuple[int, ...]
    written: tuple[Path, ...]
    reproduced: bool


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


def _stage_at(commit: str) -> Any:
    """The stage of ``layer2.json`` at ``commit``; ``None`` where it is gone or not a mapping."""
    try:
        return _committed_json(commit, LAYER2_PATH).get("stage")
    except (RuntimeError, ValueError, AttributeError):
        return None


def _layer2_history(*revs: str, full: bool = False) -> list[tuple[str, str, Any]]:
    """The commits reachable from ``revs`` that changed ``layer2.json``, newest first, with their
    subject and the stage they left it in. ``full`` follows every parent of a merge
    (``--full-history``), so a side a merge discarded still counts; without it, git's simplified
    history, where a merge that kept one parent's ``layer2.json`` changed nothing."""
    flags = ("--full-history",) if full else ()
    log = _git("log", *flags, "--format=%H%x00%s", *revs, "--", LAYER2_PATH)
    history = []
    for line in log.decode("utf-8").splitlines():
        commit, subject = line.split("\0", 1)
        history.append((commit, subject, _stage_at(commit)))
    return history


def _freeze(head: str, stage: Any, reading: Any) -> tuple[str | None, list[str]]:
    """The commit of the freeze that ``layer2.json`` at ``head`` stands on, and why it fails.

    A reading is a commit with :data:`READ_MESSAGE` that left ``layer2.json`` in ``read``; they
    are looked for on every ref and through every parent of a merge (``--all``, ``full``), so a
    branch from the freeze or a merge that discarded the reading cannot read again. In
    ``frozen``, there is none, and the freeze is the last commit of ``head`` that changed
    ``layer2.json``. In ``read``, there is one, and it is that last commit; the one before it is
    the freeze, and the record names it. A later edit of ``layer2.json`` on another branch does
    not count, so a worktree at the reading reproduces it. Since the freeze nothing of the code
    or of ``protocol/`` changed, save ``layer2.json`` in ``read``. A shallow clone, whose
    history is cut, is refused. Other stages have no freeze. The readings that this clone has
    not fetched are out of its sight: a declared limit, not a check.
    """
    if stage not in _READABLE_STAGES:
        return None, []
    if _git("rev-parse", "--is-shallow-repository").strip() != b"false":
        return None, ["the clone is shallow: the history of layer2.json is cut"]
    history = _layer2_history(head)
    every = _layer2_history("--all", full=True)
    readings = [commit for commit, subject, s in every if subject == READ_MESSAGE and s == "read"]
    if stage == "frozen":
        if readings:
            return None, [f"{LAYER2_PATH} was read at {readings[0]}: it is read once"]
        freeze, allowed = history[0][0], []
    else:
        (last, _, _), *before = history
        if readings != [last] or not before or before[0][2] != "frozen":
            return None, [f"{LAYER2_PATH} at HEAD is not the single reading made on its freeze"]
        freeze, allowed = before[0][0], [LAYER2_PATH]
        if not isinstance(reading, dict) or reading.get("frozen_commit") != freeze:
            return freeze, [f"the reading in {LAYER2_PATH} does not name its freeze {freeze}"]
    watched = (*GUARDED_CODE, "protocol")
    changed = _git("diff", "--name-only", freeze, head, "--", *watched).decode("utf-8").split()
    if changed != allowed:
        others = [path for path in changed if path not in allowed]
        return freeze, [f"{others} changed since the freeze {freeze}"]
    return freeze, []


def _guard(open_stages: tuple[str, ...]) -> GuardStatus:
    """The guard, with ``layer2.json`` taken as open in ``open_stages``."""
    head: str | None = None
    protocol_stage: Any = None
    stage: Any = None
    frozen: Any = None
    current: str | None = None
    dirty: tuple[str, ...] = ()
    try:
        head = _head()
        dirty = _dirty()
        protocol_stage = _committed_json(head, PROTOCOL_PATH).get("stage")
        layer2 = _committed_json(head, LAYER2_PATH)
        stage, frozen = layer2.get("stage"), layer2.get("code_tree_sha")
        current = code_tree_sha(head)
        freeze, reasons = _freeze(head, stage, layer2.get("reading"))
    except (RuntimeError, ValueError, AttributeError) as exc:
        reason = (f"cannot check: {exc}",)
        return GuardStatus(head, protocol_stage, stage, frozen, current, dirty, reason)
    if protocol_stage != _LAYER3_DEAD:
        reasons.append(
            f"{PROTOCOL_PATH} at HEAD is in stage {protocol_stage!r}, not {_LAYER3_DEAD!r}: "
            "layer 2 reads the held-out only once layer 3 is dead"
        )
    if stage not in open_stages:
        reasons.append(f"{LAYER2_PATH} at HEAD is in stage {stage!r}, not one of {open_stages}")
    if not isinstance(frozen, str) or frozen != current:
        reasons.append(
            f"code_tree_sha of {' and '.join(GUARDED_CODE)} at HEAD is {current}; "
            f"{LAYER2_PATH} records {frozen}"
        )
    if dirty:
        reasons.append(f"the working tree is not clean ({len(dirty)}: {list(dirty[:3])})")
    return GuardStatus(head, protocol_stage, stage, frozen, current, dirty, tuple(reasons), freeze)


def guard_status() -> GuardStatus:
    """Whether the held-out may be served inside the reading, and every reason it may not."""
    return _guard(OPEN_STAGES)


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
        reasons = list(guard_status().reasons)
        if not _READING.get():
            reasons.append("the held-out is served only inside `ac2fb heldout read`")
        if reasons:
            raise HeldOutLocked(f"held-out match(es) {held} refused: " + "; ".join(reasons))
    return ids


def _record(layer2: Mapping[str, Any], frozen_commit: str, heldout: Sequence[int]) -> bytes:
    reading = {
        "frozen_commit": frozen_commit,
        "heldout": list(heldout),
        "date": datetime.datetime.now(datetime.UTC).date().isoformat(),
    }
    body = {**layer2, "stage": "read", "reading": reading}
    return (json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def read_heldout(reports_dir: Path) -> HeldOutReading:
    """The single reading of the held-out, for layer 2 only; in stage ``read``, its reproduction.

    The commands are those of :data:`ac2fb.reliability.reading.LAYER2_READS`, never the
    caller's; their names must be exactly the ``reads`` of ``protocol/layer2.json`` at
    ``HEAD``, and they run in that order, each on the held-out ids. Nothing else runs while the
    held-out is served. Each writes into a staging directory
    outside the checkout and returns the path of its artefact there; once all have run, the
    staging directory is copied under ``reports_dir``. A command that fails leaves the reading
    recorded and ``reports_dir`` untouched: running again reproduces it.

    From stage ``frozen``: with ``protocol.json`` dead, the frozen code tree at ``HEAD``, a
    clean tree and an environment that matches ``uv.lock`` and ``.python-version``
    (:func:`lock.lock_mismatches`, :func:`lock.import_mismatches`,
    :func:`lock.python_mismatches`), it commits ``layer2.json`` in stage ``read`` with the
    commit of the freeze, the held-out ids and the date (:data:`READ_MESSAGE`) *before*
    computing any figure, and then runs the commands.
    From stage ``read``: the same checks, no new commit, the same commands. Anything else is
    refused with :class:`HeldOutLocked` before a file of the held-out is opened.
    """
    from ac2fb.reliability.reading import LAYER2_READS as commands  # it imports this module

    status = _guard(_READABLE_STAGES)
    if not status.open:
        raise HeldOutLocked("the reading is refused: " + "; ".join(status.reasons))
    head = str(status.head)
    layer2 = _committed_json(head, LAYER2_PATH)  # a mapping: the guard read it
    heldout = load_split().heldout
    reproduced = status.stage == "read"
    problems: list[str] = []
    reads = layer2.get("reads")
    if not (
        isinstance(reads, list)
        and all(isinstance(r, str) for r in reads)
        and len(set(reads)) == len(reads)
        and set(reads) == set(commands)
    ):
        problems.append(f"{LAYER2_PATH} reads {reads}; the code offers {sorted(commands)}")
    reading = layer2.get("reading")
    if reproduced and not (isinstance(reading, dict) and reading.get("heldout") == list(heldout)):
        problems.append(f"{LAYER2_PATH} is in stage read without the record of its reading")
    if not reproduced and reading is not None:
        problems.append(f"{LAYER2_PATH} is in stage frozen with a reading already recorded")
    locked = _git("show", f"{head}:uv.lock").decode("utf-8")
    problems += lock.lock_mismatches(locked, lock.installed_packages())
    problems += lock.import_mismatches(locked)
    problems += lock.python_mismatches(_git("show", f"{head}:.python-version").decode("utf-8"))
    if problems:
        raise HeldOutLocked("the reading is refused: " + "; ".join(problems))
    frozen_commit = str(status.frozen_commit)  # the guard found it: the reading is on it
    if not reproduced:
        (_repo_root() / LAYER2_PATH).write_bytes(_record(layer2, frozen_commit, heldout))
        _git("add", "--", LAYER2_PATH)
        _git("commit", "-q", "-m", READ_MESSAGE, "--", LAYER2_PATH)
    after = guard_status()
    if not after.open:
        raise HeldOutLocked("the reading is recorded but shut: " + "; ".join(after.reasons))
    # The commands write outside the checkout, so the tree stays clean while the held-out is
    # served; their artefacts are copied under reports_dir once every command has run.
    with tempfile.TemporaryDirectory(prefix="ac2fb-heldout-") as tmp:
        staging = Path(tmp)
        token = _READING.set(True)
        try:
            staged = [commands[name](list(heldout), staging) for name in reads]
        finally:
            _READING.reset(token)
        shutil.copytree(staging, reports_dir, dirs_exist_ok=True)
        written = tuple(reports_dir / path.relative_to(staging) for path in staged)
    return HeldOutReading(str(after.head), frozen_commit, heldout, written, reproduced)


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
    return _read_bronze("dynamic_events", match_ids, columns)


def _read_bronze(kind: str, match_ids: Sequence[int], columns: Sequence[str] | None) -> pa.Table:
    """The bronze files of one kind for the admitted matches, stacked in ascending id order."""
    ids = _admit(match_ids)
    cols = None if columns is None else list(columns)
    files = [bronze_path(data_dir(), "football", kind, m) for m in ids]
    return pa.concat_tables([pq.read_table(f, columns=cols) for f in files])


def read_bronze_phases(
    match_ids: Sequence[int], *, columns: Sequence[str] | None = None
) -> pa.Table:
    """The provider's own ``phases_of_play`` columns (bronze) of the given matches, guarded.

    Silver keeps a phase as an event without the provider's block width and length at its
    start; they stay in bronze. Rows are in file order; the files of the matches are stacked in
    ascending id order. Only the files of the admitted matches are opened.
    """
    return _read_bronze("phases_of_play", match_ids, columns)


def read_bronze_players(
    match_ids: Sequence[int], *, columns: Sequence[str] | None = None
) -> pa.Table:
    """The provider's roster (bronze ``match_players``) of the given matches, guarded.

    Silver keeps a player as an entity without the provider's role; the role (the goalkeeper
    among them) stays in bronze. Rows are in file order; the files of the matches are stacked in
    ascending id order. Only the files of the admitted matches are opened.
    """
    return _read_bronze("match_players", match_ids, columns)


def read_bronze_frames(
    match_ids: Sequence[int], *, columns: Sequence[str] | None = None
) -> pa.Table:
    """The provider's per-frame columns (bronze ``tracking_frames``) of the given matches, guarded.

    Silver keeps the ball and the players of a frame; the frame's own columns stay in bronze,
    among them the ball's height and the four corners of the camera's image on the pitch
    (``x_`` / ``y_`` ``bottom`` / ``top`` ``left`` / ``right``, metres in silver's frame). Rows
    are in file order; the files of the matches are stacked in ascending id order. Only the
    files of the admitted matches are opened.
    """
    return _read_bronze("tracking_frames", match_ids, columns)


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
