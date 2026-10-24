"""Task 28: ``--check`` of every command that writes a report, driven through the command line.

Each command writes its report for the synthetic calibration match, then checks it: the check
recomputes the report from the silver and compares every value. A value of the file changed in a
copy must make the check fail and name the value; a missing file, a held-out match and a check
that writes must behave as the task says. The wiring is what these tests protect: the report
each check recomputes, the file it reads, the matches it says it verified. The comparison itself
is :func:`ac2fb.reliability.report.check_json`, tested in ``test_layer2_check.py`` through
``layer2``.

Mutations of the code, each killed here, are in ``scripts/mutations/mutate28.py`` and the task's
record.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from gate_helpers import CAL, HELD, Checkout

from ac2fb import cli
from ac2fb.reliability import report

REPORTS = Path(__file__).resolve().parent.parent / "reports"
FILES = {
    "cadence": "probe_cadence.json",
    "s1": "probe_s1.json",
    "s2": "probe_s2.json",
    "s3": "probe_s3.json",
    "power": "power.json",
    "design": "design.json",
    "calibration": "calibration.json",
}
LAYER3_ONLY = "this artefact has no held-out half: layer 3 died before any held-out reading"


def run(
    capsys: pytest.CaptureFixture[str], command: str, where: Path, *flags: str, match: int = CAL
) -> tuple[int, str, str]:
    code = cli.main([command, "--match", str(match), "--reports-dir", str(where), *flags])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def prepared(command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    """A directory with the command's report written by the command, beside the probe reports."""
    where = tmp_path / "reports"
    where.mkdir()
    for name in cli._PROBE_REPORTS:  # power reads the probe verdicts beside its file
        shutil.copy(REPORTS / name, where / name)
    code, out, _ = run(capsys, command, where)
    assert code == 0 and (where / FILES[command]).is_file(), out
    return where


def leaves(path: Path) -> dict[str, object]:
    return report._flat(json.loads(path.read_text(encoding="utf-8")))


def mutate(path: Path, leaf: str, value: object) -> None:
    """Set one value of the JSON by its path and write it back as the code renders it."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    node = doc
    *parents, last = leaf.split(".")
    for key in parents:
        node = node[int(key)] if isinstance(node, list) else node[key]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value
    path.write_bytes(report.render_report(doc).encode("utf-8"))


@pytest.mark.parametrize("command", FILES)
def test_the_check_passes_says_how_much_and_writes_nothing(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    where = prepared(command, tmp_path, capsys)
    path = where / FILES[command]
    before = {p.name: p.read_bytes() for p in where.iterdir()}
    code, out, err = run(capsys, command, where, "--check")
    assert code == 0 and err == "", out
    assert f"verified: {len(leaves(path))} values, 1 matches" in out
    assert f"PARTIAL 1/20 matches: {LAYER3_ONLY}" in out
    assert out.rstrip().endswith(f"{command}: OK")
    assert {p.name: p.read_bytes() for p in where.iterdir()} == before


@pytest.mark.parametrize("command", FILES)
@pytest.mark.parametrize("which", ["first_number", "last_number", "a_string"])
def test_a_mutated_value_makes_the_check_fail_and_names_it(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, which: str
) -> None:
    where = prepared(command, tmp_path, capsys)
    path = where / FILES[command]
    found = leaves(path)
    plain = (int, float)
    numbers = [k for k, v in found.items() if isinstance(v, plain) and not isinstance(v, bool)]
    strings = [k for k, v in found.items() if isinstance(v, str)]
    leaf = {"first_number": numbers[0], "last_number": numbers[-1], "a_string": strings[0]}[which]
    old = found[leaf]
    mutate(path, leaf, "mutated" if isinstance(old, str) else old + 1)
    changed = path.read_bytes()
    code, out, _ = run(capsys, command, where, "--check")
    assert code == 1, out
    assert f"  - {leaf}: file " in out and f"{command}: FAILED" in out
    assert path.read_bytes() == changed  # the check does not repair the file


@pytest.mark.parametrize("command", FILES)
def test_a_missing_or_extra_value_and_a_missing_file_fail_the_check(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    where = prepared(command, tmp_path, capsys)
    path = where / FILES[command]
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["extra"] = 1
    path.write_bytes(report.render_report(doc).encode("utf-8"))
    code, out, _ = run(capsys, command, where, "--check")
    assert code == 1 and "not produced by the code: extra" in out
    path.unlink()
    code, out, _ = run(capsys, command, where, "--check")
    assert code == 1 and f"{FILES[command]} does not exist" in out and f"{command}: FAILED" in out


@pytest.mark.parametrize("command", FILES)
def test_the_check_refuses_a_heldout_match_and_prints_no_verdict(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    where = prepared(command, tmp_path, capsys)
    code, out, err = run(capsys, command, where, "--check", match=HELD)
    assert code == 2 and "held-out" in err and "OK" not in out and "verified" not in out


def test_power_checks_against_the_probe_reports_beside_its_file(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    where = prepared("power", tmp_path, capsys)
    probe = where / "probe_s1.json"
    doc = json.loads(probe.read_text(encoding="utf-8"))
    flipped = not doc["verdict"]["c1_survives_probe"]
    doc["verdict"]["c1_survives_probe"] = flipped
    probe.write_bytes(report.render_report(doc).encode("utf-8"))
    code, out, _ = run(capsys, "power", where, "--check")
    assert code == 1 and "  - probes.C1: file " in out


@pytest.mark.parametrize("command", ["layer2", "reliability", "amputation"])
def test_the_earlier_checks_say_what_share_they_verified(
    gate: Checkout, tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str
) -> None:
    where = tmp_path / "reports"
    where.mkdir()
    code, out, _ = run(capsys, command, where)
    assert code == 0, out
    code, out, err = run(capsys, command, where, "--check")
    assert code == 0 and err == "", out
    assert (
        "PARTIAL 1/20 matches: the 10 held-out ones reproduce only from the reading commit" in out
    )
    assert out.rstrip().endswith(f"{command}: OK")
