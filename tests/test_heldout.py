"""Task 23b: the single reading of the held-out, for layer 2 only (``ac2fb heldout read``).

On a throwaway checkout whose split holds the two synthetic matches (``CAL`` calibration,
``HELD`` held-out) and whose ``uv.lock`` is the real one, so the installed environment matches
it. The reading is committed before any figure is computed, reproduces in stage ``read``
without a new commit, runs only the commands ``layer2.json`` lists and no code of layer 3, and
is refused, unrecorded and unopened, when any condition fails. Mutations in the task's record.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from typing import Any

import pytest
from gate_helpers import CAL, HELD, ROOT, Checkout

import ac2fb.defence
import ac2fb.reliability
from ac2fb import cli
from ac2fb.protocol import data, lock
from ac2fb.protocol.data import HeldOutLocked

LAYER2_FILE = ROOT / "protocol" / "layer2.json"


@pytest.fixture
def reading(gate: Checkout) -> Checkout:
    """The gate's checkout with the real lock and a split of the two synthetic matches."""
    gate.write("uv.lock", (ROOT / "uv.lock").read_text(encoding="utf-8"))
    gate.write("protocol/split.json", json.dumps({"calibration": [CAL], "heldout": [HELD]}) + "\n")
    gate.commit("real lock, synthetic split")
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


# --- from frozen: the reading is committed, then computed ----------------------------------------


def test_from_frozen_the_reading_is_committed_before_any_figure(
    reading: Checkout, tmp_path: Path
) -> None:
    reading.freeze("frozen", reads=("probe",))
    frozen_head, frozen_body = head(reading), layer2_at_head(reading)
    seen: list[dict[str, Any]] = []
    result = data.read_heldout({"probe": probe(reading, seen)}, tmp_path / "out")
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
    reading: Checkout, tmp_path: Path
) -> None:
    reading.freeze("frozen", reads=("probe",))
    seen: list[dict[str, Any]] = []
    first = data.read_heldout({"probe": probe(reading, seen)}, tmp_path)
    again = data.read_heldout({"probe": probe(reading, seen)}, tmp_path)
    assert again.reproduced and not first.reproduced
    assert again.commit == first.commit == head(reading)
    assert again.frozen_commit == first.frozen_commit
    assert [s["stage"] for s in seen] == ["read", "read"]
    # A code change after the reading shuts the reproduction too.
    reading.write("src/ac2fb/cli.py", "# changed after the reading\n")
    reading.commit("change code")
    with pytest.raises(HeldOutLocked, match="code_tree_sha"):
        data.read_heldout({"probe": probe(reading, seen)}, tmp_path)
    assert len(seen) == 2


def test_commands_that_write_inside_the_checkout_do_not_shut_the_next_one(
    reading: Checkout,
) -> None:
    # The artefacts are staged outside the checkout while the held-out is served: one command's
    # report in the tree would make it dirty, and the guard would refuse the next command.
    reading.freeze("frozen", reads=("first", "second"))
    out = reading.root / "reports" / "heldout"
    seen: list[dict[str, Any]] = []
    commands = {name: probe(reading, seen, f"{name}.json") for name in ("first", "second")}
    result = data.read_heldout(commands, out)
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


REFUSALS: dict[str, tuple[Callable[[Checkout, pytest.MonkeyPatch], None], str]] = {
    "layer2.json in design": (lambda c, mp: None, "stage 'design'"),
    "layer 3 not dead": (_not_dead, "not 'dead'"),
    "code changed after the freeze": (_code_changed, "code_tree_sha"),
    "dirty tree": (_dirty, "not clean"),
    "reads that are not the code's": (
        lambda c, mp: c.freeze("frozen", ("probe", "other")),
        "reads ['probe', 'other']",
    ),
    "frozen with a reading recorded": (
        lambda c, mp: c.set_layer2("frozen", c.tree_sha(), ("probe",), reading={"x": 1}),
        "already recorded",
    ),
    "read without its record": (
        lambda c, mp: c.set_layer2("read", c.tree_sha(), ("probe",)),
        "without the record",
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
}


@pytest.mark.parametrize("case", list(REFUSALS))
def test_a_reading_that_cannot_hold_is_refused_unrecorded_and_unopened(
    reading: Checkout, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    prepare, words = REFUSALS[case]
    prepare(reading, monkeypatch)
    before = head(reading)
    seen: list[dict[str, Any]] = []
    with pytest.raises(HeldOutLocked, match=re.escape(words)):
        data.read_heldout({"probe": probe(reading, seen)}, tmp_path / "out")
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


# --- the committed layer2.json ------------------------------------------------------------------


def test_the_committed_layer2_protocol_is_in_design_and_lists_the_codes_commands() -> None:
    raw = LAYER2_FILE.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    doc = json.loads(raw.decode("utf-8"))
    assert doc["stage"] == "design" and doc["code_tree_sha"] is None and "reading" not in doc
    assert doc["reads"] == list(cli.LAYER2_READS)
    assert doc["writes_under"] == "reports/heldout"
    args = cli.build_parser().parse_args(["heldout", "read"])
    assert args.reports_dir == ROOT / "reports" / "heldout"
