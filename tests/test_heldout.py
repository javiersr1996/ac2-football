"""Task 23b: the single reading of the held-out, for layer 2 only (``ac2fb heldout read``).

On a throwaway checkout whose split holds the two synthetic matches (``CAL`` calibration,
``HELD`` held-out) and whose ``uv.lock`` is the real one, so the installed environment matches
it. The reading is committed before any figure is computed, reproduces in stage ``read``
without a new commit, runs only the commands ``layer2.json`` lists and no code of layer 3, and
is refused, unrecorded and unopened, when any condition fails. Its commands are those of
``ac2fb.reliability.reading`` (a test sets its own there). Task 23c adds what shuts the
held-out after the reading (an edited ``layer2.json``, a second reading), the freeze as the
commit the record names, and the interpreter and the imports. Mutations in the tasks' record.
"""

from __future__ import annotations

import csv
import importlib.machinery
import importlib.util
import inspect
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import FrameType
from typing import Any

import pytest
from gate_helpers import CAL, HELD, ROOT, Checkout

import ac2fb.defence
import ac2fb.reliability
from ac2fb import cli
from ac2fb.protocol import data, lock
from ac2fb.protocol.data import Command, HeldOutLocked
from ac2fb.reliability import reading as reads

LAYER2_FILE = ROOT / "protocol" / "layer2.json"


@pytest.fixture
def reading(gate: Checkout) -> Checkout:
    """The gate's checkout with the real lock and interpreter pin and a split of the two
    synthetic matches."""
    gate.write("uv.lock", (ROOT / "uv.lock").read_text(encoding="utf-8"))
    gate.write(".python-version", (ROOT / ".python-version").read_text(encoding="utf-8"))
    gate.write("protocol/split.json", json.dumps({"calibration": [CAL], "heldout": [HELD]}) + "\n")
    gate.commit("real lock and pin, synthetic split")
    return gate


def head(checkout: Checkout) -> str:
    return checkout.git("rev-parse", "HEAD").strip()


def layer2_at_head(checkout: Checkout) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(checkout.git("show", "HEAD:protocol/layer2.json"))
    return loaded


def probe(
    checkout: Checkout, seen: list[dict[str, Any]], name: str = "probe.json"
) -> Callable[[list[int], Path], Path]:
    """A command of the reading that records what it saw when it ran, and reads the held-out."""

    def command(ids: list[int], reports_dir: Path) -> Path:
        rows = data.read_frames([HELD], columns=["native_match_id"]).num_rows
        stage = layer2_at_head(checkout)["stage"]
        seen.append({"ids": ids, "stage": stage, "head": head(checkout), "rows": rows})
        reports_dir.mkdir(parents=True, exist_ok=True)
        out = reports_dir / name
        out.write_text(json.dumps({"ids": ids}), encoding="utf-8")
        return out

    return command


def run(mp: pytest.MonkeyPatch, commands: Mapping[str, Command], out: Path) -> data.HeldOutReading:
    """The reading with ``commands`` as the package's own."""
    mp.setattr(reads, "LAYER2_READS", commands)
    return data.read_heldout(out)


# --- from frozen: the reading is committed, then computed ----------------------------------------


def test_from_frozen_the_reading_is_committed_before_any_figure(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reading.freeze("frozen", reads=("probe",))
    frozen_head, frozen_body = head(reading), layer2_at_head(reading)
    seen: list[dict[str, Any]] = []
    result = run(monkeypatch, {"probe": probe(reading, seen)}, tmp_path / "out")
    # One commit on top of the freeze, holding layer2.json only, with the fixed message.
    assert reading.git("rev-parse", "HEAD~1").strip() == frozen_head != head(reading)
    assert reading.git("log", "-1", "--format=%s").strip() == data.READ_MESSAGE
    assert reading.git("show", "--name-only", "--format=", "HEAD").split() == [
        "protocol/layer2.json"
    ]
    # The command ran after that commit, on the held-out ids, and was served the held-out.
    assert seen == [
        {"ids": [HELD], "stage": "read", "head": head(reading), "rows": seen[0]["rows"]}
    ]
    assert seen[0]["rows"] > 0
    # The record: stage read, the frozen commit, the ids and the date; nothing else changed.
    record = layer2_at_head(reading)
    assert record["stage"] == "read"
    assert record["reading"]["frozen_commit"] == frozen_head
    assert record["reading"]["heldout"] == [HELD]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", record["reading"]["date"])
    assert {k: v for k, v in record.items() if k not in ("stage", "reading")} == {
        k: v for k, v in frozen_body.items() if k != "stage"
    }
    assert (reading.root / "protocol" / "layer2.json").read_bytes().count(b"\r") == 0
    assert result == data.HeldOutReading(
        head(reading), frozen_head, (HELD,), (tmp_path / "out" / "probe.json",), False
    )
    # The code tree did not move, the tree is clean, and outside the reading it stays refused.
    assert data.guard_status().open
    with pytest.raises(HeldOutLocked, match="only inside"):
        data.read_frames([HELD])


def test_in_stage_read_the_reading_is_reproduced_without_a_new_commit(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reading.freeze("frozen", reads=("probe",))
    seen: list[dict[str, Any]] = []
    first = run(monkeypatch, {"probe": probe(reading, seen)}, tmp_path)
    again = data.read_heldout(tmp_path)
    assert again.reproduced and not first.reproduced
    assert again.commit == first.commit == head(reading)
    assert again.frozen_commit == first.frozen_commit
    assert [s["stage"] for s in seen] == ["read", "read"]
    # A code change after the reading shuts the reproduction too.
    reading.write("src/ac2fb/cli.py", "# changed after the reading\n")
    reading.commit("change code")
    with pytest.raises(HeldOutLocked, match="code_tree_sha"):
        data.read_heldout(tmp_path)
    assert len(seen) == 2


def test_the_record_names_the_freeze_not_a_later_commit(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A commit outside the code and protocol/ between the freeze and the reading (the record
    # of CP2, say) leaves the reading open, and the record names the freeze, not that commit.
    reading.freeze("frozen", reads=("probe",))
    freeze = head(reading)
    reading.write("README.md", "CP2 approved\n")
    reading.commit("record CP2")
    later = head(reading)
    result = run(monkeypatch, {"probe": probe(reading, [])}, tmp_path)
    assert result.frozen_commit == freeze != later
    assert layer2_at_head(reading)["reading"]["frozen_commit"] == freeze
    assert reading.git("rev-parse", "HEAD~1").strip() == later


def _new_code_recorded(c: Checkout) -> None:
    """New code after the reading, with its sha written into the record of the reading."""
    c.write("src/ac2fb/cli.py", "# changed after the reading\n")
    c.commit("change code")
    body = layer2_at_head(c) | {"code_tree_sha": c.tree_sha()}
    c.write("protocol/layer2.json", json.dumps(body, indent=2) + "\n")
    c.commit("record the new code")


def _frozen_again(c: Checkout) -> None:
    """New code after the reading, and layer2.json frozen again on it."""
    c.write("src/ac2fb/cli.py", "# changed after the reading\n")
    c.commit("change code")
    c.set_layer2("frozen", c.tree_sha(), ("probe",))


def _split_swapped(c: Checkout) -> None:
    c.write("protocol/split.json", json.dumps({"calibration": [HELD], "heldout": [CAL]}) + "\n")
    c.commit("swap the split after the reading")


AFTER_THE_READING: dict[str, tuple[Callable[[Checkout], None], str]] = {
    "new code with its sha in layer2.json": (_new_code_recorded, "not the single reading"),
    "layer2.json frozen again on new code": (_frozen_again, "it is read once"),
    "the split changed after the reading": (_split_swapped, "['protocol/split.json'] changed"),
    "a second reading by hand on new code": (
        lambda c: (_frozen_again(c), c.record_reading()),
        "not the single reading",
    ),
}


@pytest.mark.parametrize("case", list(AFTER_THE_READING))
def test_after_the_reading_editing_layer2_does_not_open_it_again(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    reading.freeze("frozen", reads=("probe",))
    seen: list[dict[str, Any]] = []
    run(monkeypatch, {"probe": probe(reading, seen)}, tmp_path / "first")
    edit, words = AFTER_THE_READING[case]
    edit(reading)
    before = head(reading)
    assert not data.guard_status().open
    with pytest.raises(HeldOutLocked, match=re.escape(words)):
        data.read_heldout(tmp_path / "again")
    assert head(reading) == before and len(seen) == 1 and not (tmp_path / "again").exists()


# --- git routes around the single reading, and the one route it must keep -----------------------


def _read_then_branch(c: Checkout, mp: pytest.MonkeyPatch, out: Path) -> str:
    """The reading on the main branch, then a branch from its freeze with new code refrozen;
    returns the main branch."""
    c.freeze("frozen", reads=("probe",))
    freeze = head(c)
    main = c.git("rev-parse", "--abbrev-ref", "HEAD").strip()
    run(mp, {"probe": probe(c, [])}, out)
    c.git("switch", "-q", "-c", "retry", freeze)
    _frozen_again(c)
    return main


def test_a_branch_from_the_freeze_cannot_read_again(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _read_then_branch(reading, monkeypatch, tmp_path / "first")
    with pytest.raises(HeldOutLocked, match="it is read once"):
        data.read_heldout(tmp_path / "again")


def test_a_merge_that_discards_the_reading_cannot_read_again(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `merge -s ours` keeps the reading in the history and its layer2.json out of the tree: the
    # simplified `git log -- layer2.json` of HEAD no longer lists it.
    main = _read_then_branch(reading, monkeypatch, tmp_path / "first")
    reading.git("merge", "-q", "-s", "ours", "--no-edit", main)
    reading.git("branch", "-q", "-D", main)
    assert layer2_at_head(reading)["stage"] == "frozen"
    with pytest.raises(HeldOutLocked, match="it is read once"):
        data.read_heldout(tmp_path / "again")


def test_a_shallow_clone_is_refused(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reading.freeze("frozen", reads=("probe",))
    shallow = Checkout(tmp_path / "shallow")
    url = reading.root.as_uri()
    subprocess.run(["git", "clone", "-q", "--depth", "1", url, str(shallow.root)], check=True)
    monkeypatch.setattr(data, "_repo_root", lambda: shallow.root)
    seen: list[dict[str, Any]] = []
    with pytest.raises(HeldOutLocked, match="shallow"):
        run(monkeypatch, {"probe": probe(shallow, seen)}, tmp_path / "out")
    assert seen == []


def test_a_worktree_at_the_reading_reproduces_it_after_main_moves_on(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The plan's route once code changes after the reading: reproduce from the reading's commit.
    reading.freeze("frozen", reads=("probe",))
    freeze = head(reading)
    seen: list[dict[str, Any]] = []
    first = run(monkeypatch, {"probe": probe(reading, seen)}, tmp_path / "first")
    reading.write("src/ac2fb/cli.py", "# the figures, after the reading\n")
    reading.commit("code after the reading")
    body = layer2_at_head(reading) | {"note": "edited on main"}
    reading.write("protocol/layer2.json", json.dumps(body, indent=2) + "\n")
    reading.commit("edit layer2.json on main")
    tree = Checkout(tmp_path / "at-the-reading")
    reading.git("worktree", "add", "-q", "--detach", str(tree.root), first.commit)
    monkeypatch.setattr(data, "_repo_root", lambda: tree.root)
    again = data.read_heldout(tmp_path / "again")
    assert again.reproduced and (again.commit, again.frozen_commit) == (first.commit, freeze)
    assert len(seen) == 2


def test_the_reading_takes_no_function_from_its_caller() -> None:
    assert list(inspect.signature(data.read_heldout).parameters) == ["reports_dir"]


def test_commands_that_write_inside_the_checkout_do_not_shut_the_next_one(
    reading: Checkout, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The artefacts are staged outside the checkout while the held-out is served: one command's
    # report in the tree would make it dirty, and the guard would refuse the next command.
    reading.freeze("frozen", reads=("first", "second"))
    out = reading.root / "reports" / "heldout"
    seen: list[dict[str, Any]] = []
    commands = {name: probe(reading, seen, f"{name}.json") for name in ("first", "second")}
    result = run(monkeypatch, commands, out)
    assert [s["rows"] > 0 for s in seen] == [True, True]
    assert result.written == (out / "first.json", out / "second.json")
    assert all(json.loads(p.read_text(encoding="utf-8")) == {"ids": [HELD]} for p in result.written)


# --- refused, unrecorded and unopened -----------------------------------------------------------


def _frozen(c: Checkout) -> None:
    c.freeze("frozen", ("probe",))


def _not_dead(c: Checkout, mp: pytest.MonkeyPatch) -> None:
    _frozen(c)
    c.set_protocol("design")


def _code_changed(c: Checkout, mp: pytest.MonkeyPatch) -> None:
    _frozen(c)
    c.write("src/ac2fb/cli.py", "# changed after the freeze\n")
    c.commit("change code")


def _dirty(c: Checkout, mp: pytest.MonkeyPatch) -> None:
    _frozen(c)
    c.write("notes.txt", "x\n")


def _installed(**changes: lock.Installed | None) -> Callable[[Checkout, pytest.MonkeyPatch], None]:
    """Frozen, with the installed environment changed: a name set to ``None`` is uninstalled."""
    real = lock.installed_packages()
    fake = {k: v for k, v in real.items() if changes.get(k, real[k]) is not None}
    fake |= {k: v for k, v in changes.items() if v is not None}

    def prepare(c: Checkout, mp: pytest.MonkeyPatch) -> None:
        _frozen(c)
        mp.setattr(lock, "installed_packages", lambda: fake)

    return prepare


def _split_changed(c: Checkout, mp: pytest.MonkeyPatch) -> None:
    _frozen(c)
    c.write("protocol/split.json", json.dumps({"calibration": [HELD], "heldout": [CAL]}) + "\n")
    c.commit("swap the split after the freeze")


def _python(version: str) -> Callable[[Checkout, pytest.MonkeyPatch], None]:
    def prepare(c: Checkout, mp: pytest.MonkeyPatch) -> None:
        _frozen(c)
        mp.setattr(lock.platform, "python_version", lambda: version)

    return prepare


def _shadowed(c: Checkout, mp: pytest.MonkeyPatch) -> None:
    """Frozen, with ``ftbase`` found on a path outside its distribution."""
    _frozen(c)
    real = importlib.util.find_spec
    elsewhere = str(c.root / "elsewhere" / "ftbase" / "__init__.py")

    def find_spec(name: str, package: str | None = None) -> importlib.machinery.ModuleSpec | None:
        if name == "ftbase":
            return importlib.machinery.ModuleSpec("ftbase", None, origin=elsewhere)
        return real(name, package)

    mp.setattr(lock.importlib.util, "find_spec", find_spec)


def _edited(name: str) -> Callable[[Checkout, pytest.MonkeyPatch], None]:
    """Frozen, with one file of the run-time package ``name`` edited since install."""

    def prepare(c: Checkout, mp: pytest.MonkeyPatch) -> None:
        _frozen(c)
        edited = {name: [f"{name}/__init__.py"]}
        mp.setattr(lock, "_edited", lambda d: edited.get(lock.normalise(d.metadata["Name"]), []))

    return prepare


REFUSALS: dict[str, tuple[Callable[[Checkout, pytest.MonkeyPatch], None], str]] = {
    "layer2.json in design": (lambda c, mp: None, "stage 'design'"),
    "layer 3 not dead": (_not_dead, "not 'dead'"),
    "code changed after the freeze": (_code_changed, "code_tree_sha"),
    "dirty tree": (_dirty, "not clean"),
    "reads that are not the code's": (
        lambda c, mp: c.freeze("frozen", ("probe", "other")),
        "reads ['probe', 'other']",
    ),
    "fewer reads than the code's": (
        lambda c, mp: (
            _frozen(c),
            mp.setattr(reads, "LAYER2_READS", {"probe": probe(c, []), "other": probe(c, [])}),
        ),
        "reads ['probe']; the code offers ['other', 'probe']",
    ),
    "a read listed twice": (
        lambda c, mp: c.freeze("frozen", ("probe", "probe")),
        "reads ['probe', 'probe']",
    ),
    "the split changed after the freeze": (_split_changed, "['protocol/split.json'] changed"),
    "frozen with a reading recorded": (
        lambda c, mp: c.set_layer2("frozen", c.tree_sha(), ("probe",), reading={"x": 1}),
        "already recorded",
    ),
    "read without its record": (
        lambda c, mp: c.set_layer2("read", c.tree_sha(), ("probe",)),
        "not the single reading",
    ),
    "a reading made by hand with other ids": (
        lambda c, mp: (_frozen(c), c.record_reading(heldout=[CAL])),
        "without the record",
    ),
    "a reading not made by the command": (
        lambda c, mp: (_frozen(c), c.record_reading(message="read it by hand")),
        "not the single reading",
    ),
    "a reading with no freeze before it": (
        lambda c, mp: c.record_reading(),
        "not the single reading",
    ),
    "a reading that names another freeze": (
        lambda c, mp: (_frozen(c), c.record_reading(frozen_commit="0" * 40)),
        "does not name its freeze",
    ),
    "a library at another version": (
        _installed(numpy=lock.Installed("0.0", None)),
        "numpy is installed at 0.0",
    ),
    "the base from another commit": (
        _installed(ftbase=lock.Installed(lock.installed_packages()["ftbase"].version, "0" * 40)),
        "ftbase is installed from 0000",
    ),
    "a run-time package missing": (_installed(pyarrow=None), "pyarrow is needed at run time"),
    "another interpreter": (_python("3.12.9"), "Python 3.12.9 runs; .python-version pins"),
    "the base imported from elsewhere": (_shadowed, "ftbase is imported from"),
    "the base edited since install": (_edited("ftbase"), "ftbase has 1 file(s) edited"),
    "a library edited since install": (_edited("numpy"), "numpy has 1 file(s) edited"),
}


@pytest.mark.parametrize("case", list(REFUSALS))
def test_a_reading_that_cannot_hold_is_refused_unrecorded_and_unopened(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    prepare, words = REFUSALS[case]
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(reads, "LAYER2_READS", {"probe": probe(reading, seen)})
    prepare(reading, monkeypatch)
    before = head(reading)
    with pytest.raises(HeldOutLocked, match=re.escape(words)):
        data.read_heldout(tmp_path / "out")
    assert head(reading) == before and seen == [] and not (tmp_path / "out").exists()


# --- the command line runs layer 2 and nothing of layer 3 ---------------------------------------


def test_the_command_runs_the_layer2_commands_and_no_layer3_code(
    reading: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reading.freeze("frozen")  # reads: the commands of ac2fb.cli
    layer3 = Path(ac2fb.defence.__file__).resolve().parent
    layer2 = Path(ac2fb.reliability.__file__).resolve().parent
    called: set[Path] = set()

    def profile(frame: FrameType, event: str, arg: object) -> None:
        if event == "call":
            called.add(Path(frame.f_code.co_filename).resolve().parent)

    sys.setprofile(profile)
    try:
        code = cli.main(["heldout", "read", "--reports-dir", str(tmp_path)])
    finally:
        sys.setprofile(None)
    out = capsys.readouterr()
    assert code == 0, out.err
    assert layer2 in called and layer3 not in called
    report = json.loads((tmp_path / "layer2.json").read_text(encoding="utf-8"))
    assert set(report["matches"]) == {str(HELD)}
    table = list(
        csv.DictReader((tmp_path / "reliability.csv").read_text(encoding="utf-8").splitlines())
    )
    assert table and {row["match_id"] for row in table} == {str(HELD)}
    assert f"read 1 held-out matches at {head(reading)}" in out.out
    assert layer2_at_head(reading)["stage"] == "read"


def test_the_command_says_why_it_refuses(
    reading: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = head(reading)
    assert cli.main(["heldout", "read", "--reports-dir", str(tmp_path)]) == 2
    assert "refused: the reading is refused" in capsys.readouterr().err
    assert head(reading) == before


def test_the_command_says_a_failure_is_not_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fails(reports_dir: Path) -> data.HeldOutReading:
        raise RuntimeError("a command failed after the record")

    monkeypatch.setattr(cli, "read_heldout", fails)
    assert cli.main(["heldout", "read", "--reports-dir", str(tmp_path)]) == 1
    assert "failed: a command failed after the record" in capsys.readouterr().err


# --- the committed layer2.json ------------------------------------------------------------------


def test_the_committed_layer2_protocol_is_in_design_and_lists_the_codes_commands() -> None:
    raw = LAYER2_FILE.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    doc = json.loads(raw.decode("utf-8"))
    assert doc["stage"] == "design" and doc["code_tree_sha"] is None and "reading" not in doc
    assert doc["reads"] == list(reads.LAYER2_READS) == list(cli.LAYER2_READS)
    assert doc["writes_under"] == "reports/heldout"
    args = cli.build_parser().parse_args(["heldout", "read"])
    assert args.reports_dir == ROOT / "reports" / "heldout"
