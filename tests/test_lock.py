"""Task 23b: what is installed against what ``uv.lock`` pins (``ac2fb.protocol.lock``).

The real environment matches the real lock; each kind of difference is found on an installed
map built from the lock itself, so a change to the lock does not break these tests. Rules 3
and 4 (task 23c) on the real environment, on a module shadowed from ``PYTHONPATH``, on a
distribution built here and on interpreter versions. Mutations in the tasks' record.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from ac2fb.protocol import lock

ROOT = Path(__file__).resolve().parent.parent
LOCK_TEXT = (ROOT / "uv.lock").read_text(encoding="utf-8")


def as_locked() -> dict[str, lock.Installed]:
    """An installed map that is exactly the lock: every package at its version and commit."""
    return {
        name: lock.Installed(str(p.version), p.commit)
        for name, p in lock.locked_packages(LOCK_TEXT).items()
    }


def test_the_running_environment_matches_the_lock() -> None:
    assert lock.lock_mismatches(LOCK_TEXT, lock.installed_packages()) == []


def test_the_lock_is_read_with_the_base_commit_and_the_needs_of_the_package() -> None:
    locked = lock.locked_packages(LOCK_TEXT)
    commit = re.search(r"football-tracking-base\?tag=[^#\"]+#([0-9a-f]{40})", LOCK_TEXT)
    assert commit is not None and locked["ftbase"].commit == commit.group(1)
    assert set(locked["ac2fb"].needs) == {"ftbase", "matplotlib", "numpy", "pyarrow"}
    assert locked["numpy"].commit is None
    # pytest needs colorama only on Windows: an edge with a marker is not followed.
    assert "colorama" not in locked["pytest"].needs and "colorama" in locked


def test_an_installed_map_equal_to_the_lock_matches() -> None:
    assert lock.lock_mismatches(LOCK_TEXT, as_locked()) == []


@pytest.mark.parametrize(
    ("change", "words"),
    [
        ({"numpy": lock.Installed("0.0", None)}, "numpy is installed at 0.0; uv.lock pins"),
        ({"ftbase": "commit"}, "ftbase is installed from " + "0" * 40),
        ({"ftbase": "no commit"}, "ftbase is installed from None"),
        ({"leftpad": lock.Installed("1.0", None)}, "leftpad 1.0 is installed but not in uv.lock"),
        ({"numpy": None}, "numpy is needed at run time"),
        ({"duckdb": None}, "duckdb is needed at run time"),  # through the base
        ({"ac2fb": None}, "ac2fb is needed at run time"),
    ],
)
def test_each_difference_is_named(change: dict[str, object], words: str) -> None:
    installed = as_locked()
    for name, value in change.items():
        if value is None:
            del installed[name]
        elif value == "commit":
            installed[name] = lock.Installed(installed[name].version, "0" * 40)
        elif value == "no commit":
            installed[name] = lock.Installed(installed[name].version, None)
        else:
            assert isinstance(value, lock.Installed)
            installed[name] = value
    found = lock.lock_mismatches(LOCK_TEXT, installed)
    assert len(found) == 1 and words in found[0], found


@pytest.mark.parametrize("name", ["colorama", "mypy", "pytest", "ruff"])
def test_a_package_outside_the_run_time_closure_may_be_absent(name: str) -> None:
    # colorama hangs from a marker (Windows); the others are the development group.
    installed = as_locked()
    del installed[name]
    assert lock.lock_mismatches(LOCK_TEXT, installed) == []


def test_names_are_compared_normalised() -> None:
    assert lock.normalise("Typing_Extensions") == lock.normalise("typing.extensions")
    assert lock.normalise("Typing_Extensions") == "typing-extensions"


def test_the_installed_commit_is_read_from_direct_url(tmp_path: Path) -> None:
    info = tmp_path / "Some_Pkg-1.2.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: Some_Pkg\nVersion: 1.2\n")
    vcs = {"url": "https://x.invalid", "vcs_info": {"vcs": "git", "commit_id": "ab" * 20}}
    (info / "direct_url.json").write_text(json.dumps(vcs))
    plain = tmp_path / "plain-3.0.dist-info"
    plain.mkdir()
    (plain / "METADATA").write_text("Metadata-Version: 2.1\nName: plain\nVersion: 3.0\n")
    dists = [importlib.metadata.PathDistribution(p) for p in (info, plain)]
    assert lock.installed_packages(dists) == {
        "some-pkg": lock.Installed("1.2", "ab" * 20),
        "plain": lock.Installed("3.0", None),
    }


# --- rule 3: imported from its own distribution, unedited if from git ---------------------------


def test_the_running_environment_imports_from_its_distributions() -> None:
    assert lock.import_mismatches(LOCK_TEXT) == []


@pytest.mark.parametrize("dist_info", [False, True], ids=["bare", "with its dist-info"])
def test_a_base_shadowed_from_the_path_is_found(tmp_path: Path, dist_info: bool) -> None:
    # With its own dist-info (``pip install --target``), the shadow's RECORD would hash itself.
    (tmp_path / "ftbase").mkdir()
    (tmp_path / "ftbase" / "__init__.py").write_bytes(b"")
    if dist_info:
        (tmp_path / "ftbase-9.9.dist-info").mkdir()
        meta = b"Metadata-Version: 2.1\nName: ftbase\nVersion: 9.9\n"
        (tmp_path / "ftbase-9.9.dist-info" / "METADATA").write_bytes(meta)
    code = (
        "import pathlib, sys; from ac2fb.protocol import lock; "
        "text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'); "
        "print(*lock.import_mismatches(text), sep=chr(10))"
    )
    env = os.environ | {"PYTHONPATH": str(tmp_path)}
    done = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "uv.lock")],
        capture_output=True,
        check=True,
        env=env,
    )
    out = done.stdout.decode("utf-8")
    assert f"ftbase is imported from {tmp_path / 'ftbase'}" in out
    assert ("not once in site-packages" in out) == dist_info


def test_one_place_seen_twice_is_one_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    # A `lib64 -> lib` link puts site-packages twice on sys.path: every distribution twice.
    dists = list(importlib.metadata.distributions())
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: iter(dists + dists))
    assert lock.import_mismatches(LOCK_TEXT) == []


def _distribution(site: Path, body: bytes) -> importlib.metadata.Distribution:
    """A distribution ``pkg`` 1.0 installed under ``site``, its RECORD hashing ``body``."""
    (site / "pkg").mkdir(parents=True)
    (site / "pkg" / "__init__.py").write_bytes(body)
    info = site / "pkg-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_bytes(b"Metadata-Version: 2.1\nName: pkg\nVersion: 1.0\n")
    digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=").decode()
    record = f"pkg/__init__.py,sha256={digest},{len(body)}\npkg-1.0.dist-info/RECORD,,\n"
    (info / "RECORD").write_bytes(record.encode("ascii"))
    return importlib.metadata.PathDistribution(info)


def test_a_file_edited_or_gone_since_install_is_found(tmp_path: Path) -> None:
    dist = _distribution(tmp_path, b"x = 1\n")
    assert lock._edited(dist) == []
    (tmp_path / "pkg" / "__init__.py").write_bytes(b"x = 2\n")
    assert lock._edited(dist) == ["pkg/__init__.py"]
    (tmp_path / "pkg" / "__init__.py").unlink()
    assert lock._edited(dist) == ["pkg/__init__.py"]


# --- rule 4: the interpreter ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pin", "running", "ok"),
    [
        ("3.13\n", "3.13.5", True),
        ("3.13", "3.13.0", True),
        ("3.13.5", "3.13.5", True),
        ("3.13", "3.12.9", False),
        ("3.13", "3.130.1", False),
        ("3.13.5", "3.13.6", False),
    ],
)
def test_the_interpreter_is_held_to_the_pin(pin: str, running: str, ok: bool) -> None:
    found = lock.python_mismatches(pin, running)
    assert found == ([] if ok else [f"Python {running} runs; .python-version pins {pin.strip()}"])


def test_the_running_interpreter_is_the_pinned_one() -> None:
    assert lock.python_mismatches((ROOT / ".python-version").read_text(encoding="utf-8")) == []
