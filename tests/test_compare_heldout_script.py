"""The script that compares the held-out reading with its reproduction, run on copies of the files.

``scripts/compare_heldout_reading.sh`` reads no data and no git, so it runs here on temporary
copies of ``reports/heldout/``: the same files say OK, and each way of differing says FAILED with
the file named. The CI step that calls it is the only place the reproduction exists.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "compare_heldout_reading.sh"
COMMITTED = ROOT / "reports" / "heldout"
BASH = shutil.which("bash")

if BASH is None:
    pytest.skip(
        "bash is not installed here: the comparison script cannot run", allow_module_level=True
    )


PINNED = ROOT / "scripts" / "heldout_linux_diff.txt"
# The four values the Linux reproduction changes: one player-frame crosses the 10 m band edge.
LINUX_CHANGES = [
    ('"detected": 0.847193,', '"detected": 0.847209,'),
    ('"n": 9620\n', '"n": 9621\n'),
    ('"detected": 0.793839,', '"detected": 0.793831,'),
    ('"n": 25126\n', '"n": 25125\n'),
]


def run(
    reproduced: str, committed: Path, cwd: Path, expect: Path | None = None
) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    flag = ["--expect-diff", expect.as_posix()] if expect else []
    return subprocess.run(
        [BASH, SCRIPT.as_posix(), *flag, reproduced, committed.as_posix()],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    committed, reproduced = tmp_path / "committed", tmp_path / "reproduced"
    shutil.copytree(COMMITTED, committed)
    shutil.copytree(COMMITTED, reproduced)
    return committed, reproduced


def test_identical_directories_are_verified(pair: tuple[Path, Path], tmp_path: Path) -> None:
    committed, reproduced = pair
    done = run(reproduced.as_posix(), committed, tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "verified: 3 files byte for byte" in done.stdout and "heldout: OK" in done.stdout


def test_a_relative_reproduced_directory_is_read_from_where_it_was_given(
    pair: tuple[Path, Path], tmp_path: Path
) -> None:
    committed, _ = pair
    done = run("reproduced", committed, tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "heldout: OK" in done.stdout


def test_one_changed_value_fails_and_names_the_file_and_the_line(
    pair: tuple[Path, Path], tmp_path: Path
) -> None:
    committed, reproduced = pair
    target = reproduced / "reliability.csv"
    lines = target.read_bytes().split(b"\n")
    lines[1] = lines[1] + b"0"
    target.write_bytes(b"\n".join(lines))
    done = run(reproduced.as_posix(), committed, tmp_path)
    assert done.returncode == 1
    assert "reliability.csv: differs from the reproduction" in done.stdout
    assert lines[1].decode() in done.stdout and "heldout: FAILED (3 files compared)" in done.stdout


def test_a_missing_file_fails(pair: tuple[Path, Path], tmp_path: Path) -> None:
    committed, reproduced = pair
    (reproduced / "layer2.json").unlink()
    done = run(reproduced.as_posix(), committed, tmp_path)
    assert done.returncode == 1
    assert "layer2.json: committed, but not reproduced" in done.stdout


@pytest.mark.parametrize("extra", ["extra.csv", ".hidden"])
def test_an_extra_file_fails_even_when_it_is_hidden(
    pair: tuple[Path, Path], tmp_path: Path, extra: str
) -> None:
    committed, reproduced = pair
    (reproduced / extra).write_bytes(b"x\n")
    done = run(reproduced.as_posix(), committed, tmp_path)
    assert done.returncode == 1
    assert f"{extra}: reproduced, but not committed" in done.stdout


def test_an_empty_pair_has_nothing_to_compare(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    done = run((tmp_path / "a").as_posix(), tmp_path / "b", tmp_path)
    assert done.returncode == 1 and "no file to compare" in done.stdout


def change(path: Path, pairs: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    path.write_bytes(text.encode("utf-8"))


# Mutations planted in the script and seen to fail these tests (2026-10-24), then restored:
# ignoring the expected file (`! cmp -s` -> `false`): 4 fail; comparing only its first line: 2 fail;
# not failing a difference when the option is absent: 2 fail (one old test, one new).


def test_the_pinned_difference_passes_with_the_option(
    pair: tuple[Path, Path], tmp_path: Path
) -> None:
    committed, reproduced = pair
    change(reproduced / "layer2.json", LINUX_CHANGES)
    done = run(reproduced.as_posix(), committed, tmp_path, PINNED)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "exactly those pinned" in done.stdout and "heldout: OK" in done.stdout


def test_the_pinned_difference_without_the_option_fails(
    pair: tuple[Path, Path], tmp_path: Path
) -> None:
    committed, reproduced = pair
    change(reproduced / "layer2.json", LINUX_CHANGES)
    done = run(reproduced.as_posix(), committed, tmp_path)
    assert done.returncode == 1 and "heldout: FAILED" in done.stdout


def test_the_pinned_difference_plus_one_more_changed_value_fails(
    pair: tuple[Path, Path], tmp_path: Path
) -> None:
    committed, reproduced = pair
    change(
        reproduced / "layer2.json",
        LINUX_CHANGES
        + [
            (
                '"00_05": {\n          "detected": 0.847922,',
                '"00_05": {\n          "detected": 0.847923,',
            )
        ],
    )
    done = run(reproduced.as_posix(), committed, tmp_path, PINNED)
    assert done.returncode == 1 and "not exactly those pinned" in done.stdout


def test_one_more_difference_in_another_file_fails(pair: tuple[Path, Path], tmp_path: Path) -> None:
    committed, reproduced = pair
    change(reproduced / "layer2.json", LINUX_CHANGES)
    target = reproduced / "amputation.csv"
    target.write_bytes(target.read_bytes() + b"x\n")
    done = run(reproduced.as_posix(), committed, tmp_path, PINNED)
    assert done.returncode == 1 and "not exactly those pinned" in done.stdout


def test_a_different_change_of_the_same_lines_fails(
    pair: tuple[Path, Path], tmp_path: Path
) -> None:
    committed, reproduced = pair
    other = [(old, new) for old, new in LINUX_CHANGES]
    other[0] = (other[0][0], '"detected": 0.847210,')
    change(reproduced / "layer2.json", other)
    done = run(reproduced.as_posix(), committed, tmp_path, PINNED)
    assert done.returncode == 1 and "not exactly those pinned" in done.stdout


def test_identical_files_with_the_option_fail(pair: tuple[Path, Path], tmp_path: Path) -> None:
    committed, reproduced = pair
    done = run(reproduced.as_posix(), committed, tmp_path, PINNED)
    assert done.returncode == 1 and "not exactly those pinned" in done.stdout
